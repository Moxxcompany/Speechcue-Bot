"""
Recording utilities — token generation, verification, and download.
"""
import hashlib
import hmac
import logging
import os
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RECORDING_FEE = 0.02  # $0.02 per call
BATCH_THRESHOLD = 5   # batch size threshold for consolidated vs individual delivery

_SECRET = settings.SECRET_KEY.encode()


def generate_recording_token(call_id, user_id):
    """Generate HMAC-signed token for secure recording access."""
    payload = f"{call_id}:{user_id}:{int(time.time())}"
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]
    token = f"{sig}_{call_id[:20]}_{user_id}"
    return token


def generate_batch_token(batch_id, user_id):
    """Generate HMAC-signed token for secure batch recordings page."""
    payload = f"batch:{batch_id}:{user_id}:{int(time.time())}"
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]
    token = f"b_{sig}_{batch_id[:20]}_{user_id}"
    return token


def verify_recording_token(token):
    """Verify a recording token and extract call_id + user_id.
    Returns (call_id, user_id) or (None, None).
    """
    from bot.models import CallRecording
    try:
        rec = CallRecording.objects.filter(token=token).first()
        if rec:
            return rec.call_id, rec.user_id
    except Exception:
        pass
    return None, None


def download_recording(call_id, retell_url):
    """Download recording from Retell and save locally.
    Returns the local file path on success, or empty string on failure.
    """
    if not retell_url:
        return ""

    media_dir = os.path.join(settings.MEDIA_ROOT, "recordings")
    os.makedirs(media_dir, exist_ok=True)

    file_path = os.path.join(media_dir, f"{call_id}.wav")

    try:
        resp = requests.get(retell_url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"[recording] Downloaded {call_id} -> {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"[recording] Download failed for {call_id}: {e}")
        return ""


def get_recording_url(token):
    """Build the public URL for a recording given its token."""
    webhook_url = os.getenv("webhook_url", "")
    return f"{webhook_url}/api/recordings/{token}/"


def get_batch_recordings_url(token):
    """Build the public URL for a batch recordings page."""
    webhook_url = os.getenv("webhook_url", "")
    return f"{webhook_url}/api/recordings/batch/{token}/"


def format_duration(duration_ms):
    """Format milliseconds into human-readable duration string."""
    if not duration_ms:
        return "0s"
    total_seconds = int(duration_ms / 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def mask_phone_number(phone):
    """Mask a phone number for display: +1-XXX-XXX-1234 -> +1-***-***-1234"""
    if not phone:
        return "Unknown"
    if len(phone) > 4:
        return phone[:-4].replace(phone[:-4], "*" * len(phone[:-4])) + phone[-4:]
    return phone
