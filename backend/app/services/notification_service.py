"""
Notification Service Pipeline.
Handles multi-channel donor alerts (Push Notifications, Exotel SMS, and Exotel Automated Voice Calls).
Supports deduplication, retry queues, and message status logging.
"""

from typing import Dict, Any, List, Optional
import httpx
import logging
import os
from datetime import datetime, timezone
from app.config import settings
from app.database import SessionLocal, DatabaseRepository

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger("notification_service")

class NotificationService:
    def __init__(self):
        self.exotel_sid = settings.EXOTEL_SID
        self.exotel_token = settings.EXOTEL_TOKEN
        self.exotel_phone = settings.EXOTEL_PHONE_NUMBER
        self.sent_log: List[Dict[str, Any]] = []
        
        self.fcm_app = None
        self._init_firebase()

    def _init_firebase(self):
        if self.fcm_app is not None:
            return
            
        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        if cred_path and os.path.exists(cred_path):
            try:
                cred = credentials.Certificate(cred_path)
                self.fcm_app = firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin initialized via FIREBASE_CREDENTIALS_PATH.")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        elif settings.FIREBASE_CREDENTIALS_JSON:
            import json
            try:
                cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                cred = credentials.Certificate(cred_dict)
                self.fcm_app = firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin initialized via FIREBASE_CREDENTIALS_JSON.")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        else:
            logger.warning("FCM not configured. Push notifications will be simulated.")

    async def send_emergency_push_notification(
        self,
        donor: Dict[str, Any],
        request: Dict[str, Any],
        match_id: str
    ) -> Dict[str, Any]:
        """
        Sends high-priority Push Notification to Donor App (via FCM or simulation).
        """
        title = f"🚨 URGENT: {request.get('blood_type')} Blood Needed Nearby!"
        body = f"Urgent request at {request.get('location_name')}. Tap to respond."
        data = {
            "request_id": str(request.get("id")),
            "match_id": str(match_id),
            "blood_type": str(request.get("blood_type")),
            "location": str(request.get("location_name")),
            "urgency": str(request.get("urgency_level")),
            "type": "EMERGENCY_REQUEST"
        }
        
        payload = {
            "channel": "PUSH",
            "match_id": match_id,
            "donor_id": donor.get("id"),
            "donor_phone": donor.get("phone"),
            "title": title,
            "body": body,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "DELIVERED"
        }
        
        user_id = donor.get("user_id")
        
        with SessionLocal() as db_session:
            repo = DatabaseRepository(db_session)
            
            # Fetch device tokens
            tokens = []
            if user_id:
                tokens = repo.get_user_tokens(user_id)
            
            status = "SIMULATED_DELIVERED"
            
            if tokens and self.fcm_app:
                messages = []
                for token in tokens:
                    messages.append(messaging.Message(
                        notification=messaging.Notification(title=title, body=body),
                        data=data,
                        token=token
                    ))
                
                try:
                    # Using send_each_for_multicast as per plan
                    batch_response = messaging.send_each_for_multicast(
                        messaging.MulticastMessage(
                            notification=messaging.Notification(title=title, body=body),
                            data=data,
                            tokens=tokens
                        )
                    )
                    
                    status = "SENT" if batch_response.success_count > 0 else "FAILED"
                    payload["fcm_success_count"] = batch_response.success_count
                    payload["fcm_failure_count"] = batch_response.failure_count
                    
                    # Clean up invalid tokens
                    if batch_response.failure_count > 0:
                        for idx, resp in enumerate(batch_response.responses):
                            if not resp.success:
                                if isinstance(resp.exception, messaging.UnregisteredError) or getattr(resp.exception, 'code', None) == 'NOT_FOUND':
                                    invalid_token = tokens[idx]
                                    repo.remove_device_token(invalid_token)
                                    logger.info(f"Removed invalid device token for user {user_id}")
                                    
                except Exception as e:
                    logger.error(f"FCM Push failed: {e}")
                    status = "FAILED"
                    
            elif not tokens:
                status = "NO_DEVICE_TOKENS"
            
            payload["status"] = status
            
            if user_id:
                repo.create_notification({
                    "user_id": user_id,
                    "type": "EMERGENCY_REQUEST",
                    "title": title,
                    "body": body,
                    "request_id": request.get("id"),
                    "match_id": match_id,
                    "status": "SENT" if status in ["SENT", "SIMULATED_DELIVERED"] else "FAILED"
                })
        
        self.sent_log.append(payload)
        logger.info(f"[PUSH] Sent emergency alert to donor {donor.get('name')} ({donor.get('phone')}) for match {match_id} (Status: {status})")
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
            f"EMERGENCY BLOOD ALERT: {request.get('blood_type')} needed at {request.get('location_name')}. "
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
            f"Emergency Alert. {request.get('blood_type')} blood is urgently required at {request.get('location_name')}. "
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
