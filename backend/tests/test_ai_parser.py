"""
Unit Tests for AI NLP Emergency Request Parser.
Verifies regex fallback, blood group extraction, unit counting, and fail-open mechanism.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app.services.ai_parser import parse_with_regex_fallback, parse_emergency_request_text

def test_parse_with_regex_fallback_explicit_blood_type():
    text = "URGENT! Need 3 units of O negative blood at UCSF hospital for trauma patient!"
    res = parse_with_regex_fallback(text)

    assert res["blood_type"] == "O-"
    assert res["units_needed"] == 3
    assert res["urgency_level"] == "CRITICAL"
    assert res["needs_human_verification"] is False
    assert res["parsing_method"] == "REGEX_FALLBACK"

def test_parse_with_regex_fallback_ab_positive():
    text = "Scheduled surgery tomorrow at City Hospital. Need 2 units AB positive blood."
    res = parse_with_regex_fallback(text)

    assert res["blood_type"] == "AB+"
    assert res["units_needed"] == 2
    assert res["urgency_level"] == "HIGH"
    assert res["needs_human_verification"] is False

def test_parse_ambiguous_text_flags_human_verification():
    text = "Emergency patient admitted at General Ward bed 12. Please send blood immediately."
    res = parse_with_regex_fallback(text)

    assert res["needs_human_verification"] is True
    assert res["confidence_score"] < 0.50

@pytest.mark.asyncio
async def test_parse_emergency_request_text_async_fallback():
    text = "Critical need! 4 bags A- blood required at Manipal Hospital!"
    res = await parse_emergency_request_text(text)

    assert res["blood_type"] == "A-"
    assert res["units_needed"] == 4
    assert res["urgency_level"] == "CRITICAL"

@pytest.mark.asyncio
async def test_parse_voice_sos_transcript_spoken_dictation():
    from app.services.ai_parser import parse_voice_sos_transcript
    spoken_text = "Urgent! Need 3 bags of O negative blood at UCSF hospital immediately for trauma patient!"
    res = await parse_voice_sos_transcript(spoken_text)

    assert res["blood_type"] == "O-"
    assert res["units_needed"] == 3
    assert res["urgency_level"] == "CRITICAL"
    assert res["is_voice_sos"] is True
    assert res["hospital_name"] == "UCSF hospital"

@pytest.mark.asyncio
async def test_parse_voice_sos_spoken_ab_minus():
    from app.services.ai_parser import parse_voice_sos_transcript
    spoken_text = "Code Red! Need 2 units of AB MINUS blood at Zuckerberg SF General Hospital asap!"
    res = await parse_voice_sos_transcript(spoken_text)

    assert res["blood_type"] == "AB-"
    assert res["units_needed"] == 2
    assert res["is_voice_sos"] is True

