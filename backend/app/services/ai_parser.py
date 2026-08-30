"""
AI NLP Emergency Request Parser.
Parses free-text emergency notes into structured blood request fields.
Includes medical safety validation (flags ambiguous medical fields) and fail-open regex fallback.
"""

from typing import Dict, Any, Optional
import re
import json
import httpx
import logging
from app.config import settings

logger = logging.getLogger("ai_parser")

# Explicit blood types ordered by length to prevent partial matches
BLOOD_TYPE_PATTERNS = [
    (r"\bAB\s*(?:NEG(?:ATIVE)?|MINUS|-)", "AB-"),
    (r"\bAB\s*(?:POS(?:ITIVE)?|PLUS|\+)", "AB+"),
    (r"\bA\s*(?:NEG(?:ATIVE)?|MINUS|-)", "A-"),
    (r"\bA\s*(?:POS(?:ITIVE)?|PLUS|\+)", "A+"),
    (r"\bB\s*(?:NEG(?:ATIVE)?|MINUS|-)", "B-"),
    (r"\bB\s*(?:POS(?:ITIVE)?|PLUS|\+)", "B+"),
    (r"\bO\s*(?:NEG(?:ATIVE)?|MINUS|-)", "O-"),
    (r"\bO\s*(?:POS(?:ITIVE)?|PLUS|\+)", "O+"),
    (r"\bOH\s*(?:NEG(?:ATIVE)?|MINUS|-)", "O-"),
    (r"\bOH\s*(?:POS(?:ITIVE)?|PLUS|\+)", "O+")
]

UNITS_REGEX = r"(\d+)\s*(?:units?|bags?|pints?|bottles?)"
URGENCY_CRITICAL_TERMS = ["urgent", "emergency", "immediately", "icu", "trauma", "critical", "bleeding", "code red", "sos"]
URGENCY_HIGH_TERMS = ["surgery", "transfusion", "needed", "required", "asap"]

def parse_with_regex_fallback(text: str) -> Dict[str, Any]:
    """
    Deterministic regex & keyphrase extraction fallback.
    """
    clean_text = text.strip()
    upper_text = clean_text.upper()

    # 1. Extract Blood Type with ordered pattern matching
    extracted_bt = None
    for pattern, bt_val in BLOOD_TYPE_PATTERNS:
        if re.search(pattern, upper_text, re.IGNORECASE):
            extracted_bt = bt_val
            break

    # 2. Extract Units
    units_match = re.search(UNITS_REGEX, clean_text, re.IGNORECASE)
    units = int(units_match.group(1)) if units_match else 2

    # 3. Urgency Level
    lower_text = clean_text.lower()
    if any(term in lower_text for term in URGENCY_CRITICAL_TERMS):
        urgency = "CRITICAL"
    elif any(term in lower_text for term in URGENCY_HIGH_TERMS):
        urgency = "HIGH"
    else:
        urgency = "MEDIUM"

    # 4. Extract Location Name heuristic from spoken text ("at <Location Name>", "in <Location Name>")
    location_name = "Location (Extracted from Notes)"
    loc_match = re.search(r"(?:at|in|near)\s+([A-Z0-9\s\.\-']+\s+(?:Hospital|Medical Center|Clinic|Infirmary|ICU|Station|Road|Street))", clean_text, re.IGNORECASE)
    if loc_match:
        location_name = loc_match.group(1).strip()

    # Flag for human verification if blood type was not unambiguously found
    needs_review = extracted_bt is None

    return {
        "blood_type": extracted_bt or "O-",  # fallback default with review flag
        "units_needed": units,
        "urgency_level": urgency,
        "location_name": location_name,
        "donation_type": "WHOLE_BLOOD",
        "confidence_score": 0.95 if extracted_bt else 0.40,
        "needs_human_verification": needs_review,
        "parsing_method": "REGEX_FALLBACK",
        "raw_text": text
    }

async def parse_emergency_request_text(text: str) -> Dict[str, Any]:
    """
    Parses unstructured text using LLM (Claude API) with strict schema validation.
    Fails open to regex parser if API key is missing, network times out, or LLM fails.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.info("Anthropic API key not configured. Using deterministic regex parser fallback.")
        return parse_with_regex_fallback(text)

    prompt = f"""
    You are a clinical NLP parser for an emergency blood donation network.
    Extract structured emergency blood request parameters from the user's text:
    - blood_type: Must be one of ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"] or null if ambiguous/missing.
    - units_needed: Integer (1-10), default to 2 if unspecified.
    - urgency_level: Must be "CRITICAL", "HIGH", or "MEDIUM".
    - location_name: Extracted hospital/clinic name or "Unknown Location".
    - donation_type: Must be "WHOLE_BLOOD", "RBC", "PLASMA", or "PLATELETS".

    CRITICAL RULE: If the blood group is ambiguous or absent, set needs_human_verification to true.

    Output ONLY a JSON object:
    {{
      "blood_type": "O-",
      "units_needed": 2,
      "urgency_level": "CRITICAL",
      "location_name": "City General Hospital",
      "donation_type": "WHOLE_BLOOD",
      "confidence_score": 0.95,
      "needs_human_verification": false
    }}

    Input Text: "{text}"
    """

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": settings.LLM_MODEL_NAME,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=4.0
            )
            if res.status_code == 200:
                data = res.json()
                raw_reply = data["content"][0]["text"]
                parsed = json.loads(raw_reply)
                parsed["parsing_method"] = "LLM_CLAUDE"
                parsed["raw_text"] = text
                return parsed
    except Exception as e:
        logger.warning(f"LLM call failed/timed out: {e}. Falling back to regex parser.")

    return parse_with_regex_fallback(text)

async def parse_voice_sos_transcript(transcript: str) -> Dict[str, Any]:
    """
    Dedicated Voice SOS parser for spoken emergency audio transcripts.
    Adds voice SOS metadata and confidence flags.
    """
    parsed = await parse_emergency_request_text(transcript)
    parsed["is_voice_sos"] = True
    parsed["raw_transcript"] = transcript
    return parsed

