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


def get_retell_phone_number_set():
    """Returns a set of all phone numbers registered in Retell (E.164 format)."""
    numbers = list_retell_phone_numbers()
    return {n.phone_number for n in numbers if hasattr(n, "phone_number")}


def sync_caller_ids_with_retell():
    """
    Validate CallerIds table against Retell's actual phone numbers.
    Removes entries that don't exist in Retell.
    Returns (kept_count, removed_count).
    """
    from bot.models import CallerIds

    retell_numbers = get_retell_phone_number_set()
    if not retell_numbers:
        logger.warning("sync_caller_ids: No numbers returned from Retell — skipping purge")
        return 0, 0

    all_caller_ids = CallerIds.objects.all()
    kept = 0
    removed = 0
    for cid in all_caller_ids:
        if cid.caller_id not in retell_numbers:
            logger.info(f"sync_caller_ids: Removing invalid CallerIds entry: {cid.caller_id}")
            cid.delete()
            removed += 1
        else:
            kept += 1

    logger.info(f"sync_caller_ids: kept={kept}, removed={removed}")
    return kept, removed


def register_supervisor_function_on_agent(agent_id, webhook_url):
    """
    Register the check_supervisor_approval custom function tool on a Retell agent.
    This enables the supervisor hold pattern for DTMF approval during single IVR calls.
    """
    client = get_retell_client()
    try:
        # Get existing agent config
        agent = client.agent.retrieve(agent_id)
        existing_tools = getattr(agent, "tools", []) or []

        # Check if already registered
        for tool in existing_tools:
            if hasattr(tool, "name") and tool.name == "check_supervisor_approval":
                logger.info(f"Supervisor function already registered on agent {agent_id}")
                return True

        # Build the custom function tool
        supervisor_tool = {
            "type": "custom_function",
            "name": "check_supervisor_approval",
            "description": (
                "After collecting DTMF keypad digits from the caller, call this function "
                "to send the digits for supervisor approval. Wait for the response. "
                "If response is 're_enter', ask the caller to re-enter the digits. "
                "If response is 'proceed', continue with the next step."
            ),
            "url": f"{webhook_url}/api/dtmf/supervisor-check",
            "speak_during_execution": True,
            "speak_after_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "digits": {
                        "type": "string",
                        "description": "The DTMF digits entered by the caller",
                    },
                    "node_name": {
                        "type": "string",
                        "description": "The name or description of the current step",
                    },
                },
                "required": ["digits"],
            },
        }

        # Append to existing tools
        new_tools = list(existing_tools) + [supervisor_tool]

        # Update agent
        client.agent.update(
            agent_id=agent_id,
            tools=new_tools,
        )
        logger.info(f"Supervisor function registered on agent {agent_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to register supervisor function on agent {agent_id}: {e}")
        return False


def update_agent_inbound_settings(agent_id, phone_record):
    """
    Auto-update a Retell agent's prompt/tools based on voicemail, forwarding,
    and business hours settings from the UserPhoneNumber record.
    Called whenever the user toggles these settings.
    """
    client = get_retell_client()
    try:
        agent = client.agent.retrieve(agent_id)
        existing_prompt = getattr(agent, "response_engine", {})  # noqa: F841
        general_prompt = getattr(agent, "general_prompt", "") or ""
        existing_tools = getattr(agent, "tools", []) or []

        # Build inbound instructions
        inbound_instructions = []

        # Voicemail
        if phone_record.voicemail_enabled:
            vm_msg = phone_record.voicemail_message
            inbound_instructions.append(
                f"VOICEMAIL MODE: If the call seems to be going to voicemail or if the caller "
                f"has been waiting and no one is available, say the following message: "
                f"\"{vm_msg}\" Then end the call politely."
            )

        # Call forwarding
        if phone_record.forwarding_enabled and phone_record.forwarding_number:
            fwd = phone_record.forwarding_number
            inbound_instructions.append(
                f"CALL FORWARDING: When you receive an inbound call, greet the caller briefly, "
                f"then immediately transfer the call to {fwd} using a warm transfer."
            )

        # Business hours
        if phone_record.business_hours_enabled and phone_record.business_hours_start and phone_record.business_hours_end:
            start = phone_record.business_hours_start.strftime("%H:%M")
            end = phone_record.business_hours_end.strftime("%H:%M")
            tz = phone_record.business_hours_timezone or "US/Eastern"
            inbound_instructions.append(
                f"BUSINESS HOURS: This line operates {start} to {end} ({tz}). "
                f"Call the get_current_time function to check the current time. "
                f"If the current time is outside business hours, inform the caller that "
                f"the office is closed and offer to take a voicemail message."
            )

        # Build final prompt addon
        inbound_addon = ""
        if inbound_instructions:
            inbound_addon = (
                "\n\n--- INBOUND CALL SETTINGS ---\n"
                + "\n\n".join(inbound_instructions)
                + "\n--- END INBOUND SETTINGS ---"
            )

        # Strip old inbound settings from the prompt
        if "--- INBOUND CALL SETTINGS ---" in general_prompt:
            general_prompt = general_prompt.split("--- INBOUND CALL SETTINGS ---")[0].rstrip()

        # Append new settings
        updated_prompt = general_prompt + inbound_addon

        # Ensure transfer_call tool exists if forwarding is enabled
        update_kwargs = {"general_prompt": updated_prompt}

        if phone_record.forwarding_enabled and phone_record.forwarding_number:
            has_transfer = any(
                (hasattr(t, "type") and t.type == "transfer_call") or
                (isinstance(t, dict) and t.get("type") == "transfer_call")
                for t in existing_tools
            )
            if not has_transfer:
                transfer_tool = {
                    "type": "transfer_call",
                    "name": "transfer_call",
                    "number": phone_record.forwarding_number,
                }
                new_tools = list(existing_tools) + [transfer_tool]
                update_kwargs["tools"] = new_tools

        client.agent.update(agent_id=agent_id, **update_kwargs)
        logger.info(f"Updated inbound settings on agent {agent_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update inbound settings on agent {agent_id}: {e}")
        return False
