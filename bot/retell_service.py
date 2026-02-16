"""
Retell AI service layer — replaces all Bland.ai API calls.
Singleton client pattern for the Retell SDK.
"""
import logging
from retell import Retell
from django.conf import settings

logger = logging.getLogger(__name__)

_client = None


def get_retell_client():
    """Get or create the Retell SDK client singleton."""
    global _client
    if _client is None:
        api_key = settings.RETELL_API_KEY
        if not api_key:
            raise ValueError("RETELL_API_KEY is not configured")
        _client = Retell(api_key=api_key)
        logger.info("Retell client initialized")
    return _client
