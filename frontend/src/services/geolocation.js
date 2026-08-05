/**
 * Geolocation Service — Browser GPS, reverse geocoding, distance math.
 * Uses Nominatim (OpenStreetMap) for free reverse geocoding.
 */

// ── Haversine Distance ──────────────────────────────────────────
export function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function formatDistance(km) {
  if (km < 1) return `${Math.round(km * 1000)}m`;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km)} km`;
}

export function estimateETA(distanceKm, speedKmh = 35) {
  const mins = Math.max(1, Math.round((distanceKm / speedKmh) * 60));
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

// ── Get Current Position (Promise) ──────────────────────────────
export function getCurrentPosition(options = {}) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation not supported'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          timestamp: pos.timestamp,
        }),
      (err) => reject(err),
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000,
        ...options,
      }
    );
  });
}

// ── Watch Position (continuous) ─────────────────────────────────
export function watchPosition(callback, errorCallback) {
  if (!navigator.geolocation) {
    errorCallback?.(new Error('Geolocation not supported'));
    return null;
  }
  const id = navigator.geolocation.watchPosition(
    (pos) =>
      callback({
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
        speed: pos.coords.speed,
        heading: pos.coords.heading,
        timestamp: pos.timestamp,
      }),
    (err) => errorCallback?.(err),
    { enableHighAccuracy: true, maximumAge: 5000 }
  );
  return () => navigator.geolocation.clearWatch(id);
}

// ── Reverse Geocode (Nominatim) ─────────────────────────────────
const geocodeCache = {};

export async function reverseGeocode(lat, lon) {
  const key = `${lat.toFixed(4)},${lon.toFixed(4)}`;
  if (geocodeCache[key]) return geocodeCache[key];

  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&addressdetails=1`,
      { headers: { 'Accept-Language': 'en' } }
    );
    if (!res.ok) throw new Error('Geocode failed');
    const data = await res.json();
    const addr = data.address || {};
    const result = {
      display: data.display_name || `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
      short:
        addr.road || addr.neighbourhood || addr.suburb || addr.city || data.display_name?.split(',')[0] || '',
      city: addr.city || addr.town || addr.village || addr.county || '',
      state: addr.state || '',
      country: addr.country || '',
      postcode: addr.postcode || '',
    };
    geocodeCache[key] = result;
    return result;
  } catch {
    return {
      display: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
      short: 'Unknown Location',
      city: '',
      state: '',
      country: '',
      postcode: '',
    };
  }
}

// ── Sort by distance from a point ───────────────────────────────
export function sortByDistance(items, lat, lon, latKey = 'lat', lonKey = 'lon') {
  return [...items]
    .map((item) => ({
      ...item,
      _distance: haversineDistance(lat, lon, item[latKey], item[lonKey]),
    }))
    .sort((a, b) => a._distance - b._distance);
}

// ── Open directions in maps app ─────────────────────────────────
export function openDirections(destLat, destLon, destName = 'Hospital') {
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  if (isIOS) {
    window.open(`maps://maps.apple.com/?daddr=${destLat},${destLon}&dirflg=d`, '_blank');
  } else {
    window.open(
      `https://www.google.com/maps/dir/?api=1&destination=${destLat},${destLon}&destination_place_id=${encodeURIComponent(destName)}&travelmode=driving`,
      '_blank'
    );
  }
}

// ── Notification Sound ──────────────────────────────────────────
let audioCtx = null;
export function playNotificationSound(type = 'accept') {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    if (type === 'accept') {
      osc.frequency.setValueAtTime(523, audioCtx.currentTime); // C5
      osc.frequency.setValueAtTime(659, audioCtx.currentTime + 0.12); // E5
      osc.frequency.setValueAtTime(784, audioCtx.currentTime + 0.24); // G5
    } else if (type === 'emergency') {
      osc.frequency.setValueAtTime(880, audioCtx.currentTime);
      osc.frequency.setValueAtTime(660, audioCtx.currentTime + 0.15);
      osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.3);
    } else {
      osc.frequency.setValueAtTime(440, audioCtx.currentTime);
    }

    gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
    osc.start(audioCtx.currentTime);
    osc.stop(audioCtx.currentTime + 0.5);
  } catch {
    // Audio not available
  }
}
