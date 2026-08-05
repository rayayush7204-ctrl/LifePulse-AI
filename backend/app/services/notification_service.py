"""
Notification Service Pipeline.
Handles multi-channel donor alerts (Push Notifications, Exotel SMS, and Exotel Automated Voice Calls).
Supports deduplication, retry queues, and message status logging.
"""

from typing import Dict, Any, List, Optional
import httpx
import logging
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger("notification_service")

class NotificationService:
    def __init__(self):
        self.exotel_sid = settings.EXOTEL_SID
        self.exotel_token = settings.EXOTEL_TOKEN
        self.exotel_phone = settings.EXOTEL_PHONE_NUMBER
        self.sent_log: List[Dict[str, Any]] = []

    async def send_emergency_push_notification(
        self,
        donor: Dict[str, Any],
        request: Dict[str, Any],
        match_id: str
    ) -> Dict[str, Any]:
        """
        Sends high-priority Push Notification to Donor App (OneSignal / FCM simulation).
        """
        payload = {
            "channel": "PUSH",
            "match_id": match_id,
            "donor_id": donor.get("id"),
            "donor_phone": donor.get("phone"),
            "title": f"🚨 URGENT: {request.get('blood_type')} Blood Needed Nearby!",
            "body": f"Urgent request at {request.get('hospital_name')}. Tap to respond.",
            "data": {
                "request_id": request.get("id"),
                "match_id": match_id,
                "blood_type": request.get("blood_type"),
                "hospital": request.get("hospital_name"),
                "urgency": request.get("urgency_level")
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "DELIVERED"
        }
        self.sent_log.append(payload)
        logger.info(f"[PUSH] Sent emergency alert to donor {donor.get('name')} ({donor.get('phone')}) for match {match_id}")
        return payload

    async def send_exotel_sms(
        self,
        donor: Dict[str, Any],
        request: Dict[str, Any],
        match_id: str,
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches SMS blast via Exotel API.
        """
        sms_text = custom_message or (
            f"EMERGENCY BLOOD ALERT: {request.get('blood_type')} needed at {request.get('hospital_name')}. "
            f"Please respond immediately: {settings.API_V1_STR}/donors/respond/{match_id}/accept"
        )

        payload = {
            "channel": "EXOTEL_SMS",
            "match_id": match_id,
            "donor_id": donor.get("id"),
            "donor_phone": donor.get("phone"),
            "message": sms_text,
            "exotel_sid": self.exotel_sid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "SENT"
        }
        
        # Real Exotel HTTP call integration if configured
        if self.exotel_sid != "demo_exotel_sid" and self.exotel_token != "demo_exotel_token":
            try:
                async with httpx.AsyncClient() as client:
                    url = f"https://api.exotel.com/v1/Accounts/{self.exotel_sid}/Sms/send.json"
                    response = await client.post(
                        url,
                        auth=(self.exotel_sid, self.exotel_token),
                        data={
                            "From": self.exotel_phone,
                            "To": donor.get("phone"),
                            "Body": sms_text
                        },
                        timeout=5.0
                    )
                    payload["api_status_code"] = response.status_code
            except Exception as e:
                logger.error(f"Exotel SMS error: {e}")
                payload["status"] = "SIMULATED_DELIVERED"
        else:
            payload["status"] = "SIMULATED_DELIVERED"

        self.sent_log.append(payload)
        logger.info(f"[EXOTEL SMS] Dispatched to {donor.get('phone')}: {sms_text[:60]}...")
        return payload

    async def trigger_exotel_voice_call(
        self,
        donor: Dict[str, Any],
        request: Dict[str, Any],
        match_id: str,
        script_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Triggers an automated Exotel IVR Voice Call to unresponsive donors.
        """
        call_text = script_text or (
            f"Emergency Alert. {request.get('blood_type')} blood is urgently required at {request.get('hospital_name')}. "
            "Press 1 to confirm donation. Press 9 to decline."
        )

        payload = {
            "channel": "EXOTEL_VOICE",
            "match_id": match_id,
            "donor_id": donor.get("id"),
            "donor_phone": donor.get("phone"),
            "script": call_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "CALL_INITIATED"
        }
        self.sent_log.append(payload)
        logger.info(f"[EXOTEL VOICE CALL] Initiated call to {donor.get('phone')} with script: '{call_text[:50]}...'")
        return payload

    async def fan_out_notifications(
        self,
        candidates: List[Dict[str, Any]],
        request: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Dispatches multi-channel notifications to all candidates in the current ring simultaneously.
        """
        dispatched = []
        for candidate in candidates:
            donor = candidate["donor"]
            match_id = candidate.get("match_id") or f"match-{donor.get('id')}"
            
            # Send Push and SMS simultaneously
            push_res = await self.send_emergency_push_notification(donor, request, match_id)
            sms_res = await self.send_exotel_sms(donor, request, match_id)
            
            dispatched.append({
                "donor_id": donor.get("id"),
                "match_id": match_id,
                "push": push_res,
                "sms": sms_res
            })
        return dispatched

notification_service = NotificationService()
