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



# =============================================================================
# Phone Number Management
# =============================================================================

def purchase_phone_number(area_code=None, country_code="US", toll_free=False, nickname=""):
    """
    Purchase a phone number via Retell API.
    Returns the PhoneNumberResponse or None on failure.
    Cost: $2/mo (US local), $5/mo (toll-free), $2/mo (CA).
    """
    client = get_retell_client()
    kwargs = {}
    if area_code:
        kwargs["area_code"] = int(area_code)
    if country_code:
        kwargs["country_code"] = country_code
    if toll_free:
        kwargs["toll_free"] = True
    if nickname:
        kwargs["nickname"] = nickname

    try:
        result = client.phone_number.create(**kwargs)
        logger.info(f"Purchased phone number: {result.phone_number}")
        return result
    except Exception as e:
        logger.error(f"Failed to purchase phone number: {e}")
        return None


def release_phone_number(phone_number):
    """Release/delete a phone number from Retell."""
    client = get_retell_client()
    try:
        client.phone_number.delete(phone_number=phone_number)
        logger.info(f"Released phone number: {phone_number}")
        return True
    except Exception as e:
        logger.error(f"Failed to release phone number {phone_number}: {e}")
        return False


def update_phone_number_agent(phone_number, outbound_agent_id=None, inbound_agent_id=None, nickname=None):
    """Update agent assignment for a phone number."""
    client = get_retell_client()
    kwargs = {}
    if outbound_agent_id is not None:
        kwargs["outbound_agent_id"] = outbound_agent_id
    if inbound_agent_id is not None:
        kwargs["inbound_agent_id"] = inbound_agent_id
    if nickname is not None:
        kwargs["nickname"] = nickname
    try:
        result = client.phone_number.update(phone_number=phone_number, **kwargs)
        logger.info(f"Updated phone number {phone_number}: {kwargs}")
        return result
    except Exception as e:
        logger.error(f"Failed to update phone number {phone_number}: {e}")
        return None


def list_retell_phone_numbers():
    """List all phone numbers in the Retell account."""
    client = get_retell_client()
    try:
        return client.phone_number.list()
    except Exception as e:
        logger.error(f"Failed to list phone numbers: {e}")
        return []
