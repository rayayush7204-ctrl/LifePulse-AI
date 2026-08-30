/**
 * API & WebSocket Client for Emergency Blood Donor Matcher.
 * Includes JWT authentication, fail-open client-side fallback for offline/network-down resilience.
 */

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

// Client-side fail-open logic has been removed to strictly enforce real PostgreSQL data usage.

// ── JWT Auth Helpers ────────────────────────────────────────────
function getAuthHeaders() {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function submitEmergencyRequest(data) {
  try {
    const res = await fetch(`${API_BASE}/requests/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data)
    });
    if (res.ok) {
      return await res.json();
    }
    const errData = await res.json().catch(() => ({ detail: 'Failed to submit request' }));
    throw new Error(errData.detail || 'Failed to submit request');
  } catch (err) {
    console.error("[API] Backend submitEmergencyRequest error:", err);
    throw err;
  }
}

export async function getRequestStatus(requestId) {
  try {
    const res = await fetch(`${API_BASE}/requests/${requestId}`);
    if (res.ok) return await res.json();
    throw new Error('Request not found');
  } catch (err) {
    console.error("[API] getRequestStatus fetch error:", err);
    throw err;
  }
}

export async function getRequestAudit(requestId) {
  try {
    const res = await fetch(`${API_BASE}/requests/${requestId}/audit`);
    if (res.ok) return await res.json();
    throw new Error('Audit logs not found');
  } catch (err) {
    console.error("[API] getRequestAudit fetch error:", err);
    throw err;
  }
}

export async function getRequestMatches(requestId) {
  try {
    const res = await fetch(`${API_BASE}/requests/${requestId}/matches`);
    if (res.ok) return await res.json();
    return [];
  } catch (err) {
    console.error("[API] getRequestMatches error:", err);
    return [];
  }
}

export async function respondDonorAction(matchId, action, etaMinutes = null, latitude = null, longitude = null) {
  try {
    const res = await fetch(`${API_BASE}/donors/respond`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        match_id: matchId,
        action: action,
        eta_minutes: etaMinutes,
        latitude: latitude,
        longitude: longitude
      })
    });
    if (res.ok) return await res.json();
    const errData = await res.json().catch(() => ({ detail: 'Failed to update status' }));
    throw new Error(errData.detail || 'Failed to update status');
  } catch (err) {
    console.error("[API] respondDonorAction error:", err);
    throw err;
  }
}


export function parseVoiceTranscriptClientSide(text) {
  const clean = (text || '').trim();
  const upper = clean.toUpperCase();

  const BLOOD_PATTERNS = [
    [/\bAB\s*(?:NEG(?:ATIVE)?|MINUS|-)/i, "AB-"],
    [/\bAB\s*(?:POS(?:ITIVE)?|PLUS|\+)/i, "AB+"],
    [/\bA\s*(?:NEG(?:ATIVE)?|MINUS|-)/i, "A-"],
    [/\bA\s*(?:POS(?:ITIVE)?|PLUS|\+)/i, "A+"],
    [/\bB\s*(?:NEG(?:ATIVE)?|MINUS|-)/i, "B-"],
    [/\bB\s*(?:POS(?:ITIVE)?|PLUS|\+)/i, "B+"],
    [/\bO\s*(?:NEG(?:ATIVE)?|MINUS|-)/i, "O-"],
    [/\bO\s*(?:POS(?:ITIVE)?|PLUS|\+)/i, "O+"],
    [/\bOH\s*(?:NEG(?:ATIVE)?|MINUS|-)/i, "O-"],
    [/\bOH\s*(?:POS(?:ITIVE)?|PLUS|\+)/i, "O+"]
  ];

  let bloodType = null;
  for (const [pattern, val] of BLOOD_PATTERNS) {
    if (pattern.test(upper)) {
      bloodType = val;
      break;
    }
  }

  const unitsMatch = clean.match(/(\d+)\s*(?:units?|bags?|pints?|bottles?)/i);
  const unitsNeeded = unitsMatch ? parseInt(unitsMatch[1]) : 2;

  const lower = clean.toLowerCase();
  let urgencyLevel = "MEDIUM";
  if (["urgent", "emergency", "immediately", "icu", "trauma", "critical", "bleeding", "code red", "sos"].some(term => lower.includes(term))) {
    urgencyLevel = "CRITICAL";
  } else if (["surgery", "transfusion", "needed", "required", "asap"].some(term => lower.includes(term))) {
    urgencyLevel = "HIGH";
  }

  let hospitalName = "Hospital (Extracted from Notes)";
  const hospMatch = clean.match(/(?:at|in|near)\s+([A-Z0-9\s\.\-']+\s+(?:Hospital|Medical Center|Clinic|Infirmary|ICU))/i);
  if (hospMatch) {
    hospitalName = hospMatch[1].trim();
  }

  return {
    blood_type: bloodType || "O-",
    units_needed: unitsNeeded,
    urgency_level: urgencyLevel,
    hospital_name: hospitalName,
    donation_type: "WHOLE_BLOOD",
    confidence_score: bloodType ? 0.95 : 0.40,
    needs_human_verification: !bloodType,
    parsing_method: "CLIENT_SIDE_FAILOPEN_FALLBACK",
    raw_text: clean,
    is_voice_sos: true
  };
}

export async function parseFreeTextWithAI(text) {
  try {
    const res = await fetch(`${API_BASE}/ai/parse-request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("[API] Backend AI parse call failed, using client-side fail-open parser:", err);
  }
  return parseVoiceTranscriptClientSide(text);
}

export async function parseVoiceSOS(transcript) {
  try {
    const res = await fetch(`${API_BASE}/ai/voice-sos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript, text: transcript })
    });
    if (res.ok) {
      return await res.json();
    }
    const fallbackRes = await fetch(`${API_BASE}/ai/parse-request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: transcript })
    });
    if (fallbackRes.ok) {
      const data = await fallbackRes.json();
      data.is_voice_sos = true;
      return data;
    }
  } catch (err) {
    console.warn("[API] Voice SOS backend fetch failed, utilizing fail-open client-side parser:", err);
  }
  return parseVoiceTranscriptClientSide(transcript);
}


export async function updateDonorLocation(donorId, latitude, longitude, requestId = null, speedKmh = 35.0, accuracy = null) {
  try {
    const body = {
      latitude,
      longitude,
      request_id: requestId,
      speed_kmh: speedKmh,
    };
    if (accuracy !== null) body.accuracy = accuracy;

    const res = await fetch(`${API_BASE}/donors/location?donor_id=${donorId}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    });
    if (res.ok) return await res.json();
    throw new Error('Failed to update location');
  } catch (err) {
    console.error("[API] Location update error:", err);
    throw err;
  }
}



export async function fetchBloodBanks() {
  try {
    const res = await fetch(`${API_BASE}/hospitals/`);
    if (res.ok) return await res.json();
    return [];
  } catch (err) {
    console.error("[API] fetchBloodBanks error:", err);
    return [];
  }
}

export async function fetchAllDonors() {
  try {
    const res = await fetch(`${API_BASE}/donors/`);
    if (res.ok) return await res.json();
    return [];
  } catch (err) {
    console.error("[API] fetchAllDonors error:", err);
    return [];
  }
}

export async function registerDonor(donorData) {
  try {
    const res = await fetch(`${API_BASE}/donors/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(donorData)
    });
    if (res.ok) return await res.json();
    const errData = await res.json().catch(() => ({ detail: 'Failed to register donor' }));
    throw new Error(errData.detail || 'Failed to register donor');
  } catch (err) {
    console.error("[API] registerDonor error:", err);
    throw err;
  }
}

export async function triggerManualEscalation(requestId) {
  try {
    const res = await fetch(`${API_BASE}/requests/${requestId}/escalate`, {
      method: 'POST'
    });
    if (res.ok) return await res.json();
    throw new Error('Failed to trigger escalation');
  } catch (err) {
    console.error("[API] triggerManualEscalation error:", err);
    throw err;
  }
}

// ── NEW: Fetch Nearby Active Requests ───────────────────────────
export async function fetchNearbyRequests(lat, lon, radiusKm = 50) {
  try {
    const res = await fetch(`${API_BASE}/requests/nearby?lat=${lat}&lon=${lon}&radius_km=${radiusKm}`);
    if (res.ok) return await res.json();
    return [];
  } catch (err) {
    console.error("[API] fetchNearbyRequests error:", err);
    return [];
  }
}

// ── NEW: Get Share Data ─────────────────────────────────────────
export async function getShareData(requestId) {
  try {
    const res = await fetch(`${API_BASE}/requests/${requestId}/share`);
    if (res.ok) return await res.json();
    return null;
  } catch (err) {
    console.error("[API] getShareData error:", err);
    return null;
  }
}

// ── Cancel Emergency Request ────────────────────────────────────
export async function cancelRequest(requestId) {
  try {
    const res = await fetch(`${API_BASE}/requests/${requestId}/cancel`, {
      method: 'PATCH',
      headers: getAuthHeaders()
    });
    const data = await safeJson(res);
    if (!res.ok) {
      throw new Error(data.detail || 'Failed to cancel request.');
    }
    return data;
  } catch (err) {
    console.error("[API] cancelRequest error:", err);
    throw err;
  }
}

// ── WebSocket Subscription ──────────────────────────────────────
export function subscribeToRequestWebsocket(requestId, onEvent) {
  const token = localStorage.getItem('token');
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  let base = import.meta.env.VITE_WS_URL || `${proto}//${window.location.host}/ws/requests`;
  base = base.replace(/^http:\/\//i, 'ws://').replace(/^https:\/\//i, 'wss://');
  if (window.location.protocol === 'https:' && base.startsWith('ws://')) {
    base = base.replace(/^ws:\/\//i, 'wss://');
  }
  const wsUrl = `${base}/${requestId}${token ? `?token=${token}` : ''}`;
  
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => console.log(`[WS] Connected to request ${requestId}`);
  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      onEvent(payload);
    } catch (e) {
      console.error('[WS] Parse error', e);
    }
  };
  ws.onclose = () => console.log(`[WS] Disconnected from request ${requestId}`);
  return ws;
}

// ── Authentication API ──────────────────────────────────────────

async function safeJson(res) {
  try {
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      if (Array.isArray(data.detail)) {
        // FastAPI 422 Validation Error
        data.detail = data.detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join(', ');
      }
    }
    return data;
  } catch (err) {
    return { detail: `Server error (${res.status}): Backend service did not return valid JSON.` };
  }
}

export async function signupUser(payload) {
  try {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) {
      throw new Error(data.detail || 'Signup failed.');
    }
    return data;
  } catch (err) {
    console.error("[API] signupUser error:", err);
    throw err;
  }
}

export async function loginUser(payload) {
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) {
      throw new Error(data.detail || 'Login failed.');
    }
    return data;
  } catch (err) {
    console.error("[API] loginUser error:", err);
    throw err;
  }
}

export async function getCurrentUser() {
  const token = localStorage.getItem('token');
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) return await safeJson(res);
    return null;
  } catch (err) {
    console.warn('[API] getCurrentUser error:', err);
    return null;
  }
}

export function logoutUser() {
  localStorage.removeItem('token');
}

// ── Medical Screening API ───────────────────────────────────────

export async function submitMedicalScreening(payload) {
  try {
    const res = await fetch(`${API_BASE}/donors/screening`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload)
    });
    if (res.ok) return await res.json();
    const errData = await res.json().catch(() => ({ detail: 'Screening submission failed' }));
    throw new Error(errData.detail || 'Screening submission failed');
  } catch (err) {
    console.warn('[API] submitMedicalScreening error:', err);
    throw err;
  }
}

export async function getDonorScreening(donorId) {
  try {
    const res = await fetch(`${API_BASE}/donors/${donorId}/screening`, {
      headers: getAuthHeaders()
    });
    if (res.ok) return await res.json();
    return null;
  } catch (err) {
    console.warn('[API] getDonorScreening error:', err);
    return null;
  }
}

export async function withdrawDonorMatch(matchId) {
  try {
    const res = await fetch(`${API_BASE}/donors/matches/${matchId}/withdraw`, {
      method: 'PATCH',
      headers: getAuthHeaders()
    });
    if (res.ok) return await res.json();
    const errData = await res.json().catch(() => ({ detail: 'Withdrawal failed' }));
    throw new Error(errData.detail || 'Withdrawal failed');
  } catch (err) {
    console.error("[API] withdrawDonorMatch fetch error:", err);
    throw err;
  }
}

export async function registerDeviceToken(token, platform = "web") {
  try {
    const res = await fetch(`${API_BASE}/notifications/device-token`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ token, platform })
    });
    if (res.ok) return await res.json();
    return null;
  } catch (err) {
    console.warn('[API] registerDeviceToken error:', err);
    return null;
  }
}
