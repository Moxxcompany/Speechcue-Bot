"""
Webhook handlers for Retell AI call events.
Retell sends call_started, call_ended, call_analyzed events.
"""
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bot.tasks import update_dtmf_inbox

logger = logging.getLogger(__name__)


def extract_call_details_retell(data):
    """
    Extract call details from Retell webhook payload.
    Maps to the same format expected by update_dtmf_inbox.
    """
    call = data.get("data", data)

    phone_number = call.get("to_number", call.get("to", "Unknown"))
    call_id = call.get("call_id", "Unknown")
    agent_id = call.get("agent_id", call.get("pathway_id", "Unknown"))

    # Convert epoch ms to ISO string
    timestamp = "Unknown"
    if call.get("end_timestamp"):
        from datetime import datetime, timezone
        timestamp = datetime.fromtimestamp(
            call["end_timestamp"] / 1000, tz=timezone.utc
        ).isoformat()

    # Extract DTMF from transcript
    dtmf_input = []
    transcript_obj = call.get("transcript_object", [])
    for entry in transcript_obj:
        if entry.get("role") == "user":
            text = entry.get("content", "")
            if "Pressed Button: " in text:
                number = text.split("Pressed Button: ")[1].strip()
                if number.isdigit():
                    dtmf_input.append(number)

    # Also check collected_dynamic_variables for DTMF
    dynamic_vars = call.get("retell_llm_dynamic_variables", {})
    for key, value in dynamic_vars.items():
        if "dtmf" in key.lower() and str(value).isdigit():
            dtmf_input.append(str(value))

    dtmf_input_result = "".join(dtmf_input) if dtmf_input else "No DTMF input found"

    return {
        "phone_number": phone_number,
        "call_id": call_id,
        "pathway_id": agent_id,
        "timestamp": timestamp,
        "dtmf_input": dtmf_input_result,
    }


@csrf_exempt
def call_details_webhook(request):
    """
    Handle Retell AI webhook events (call_started, call_ended, call_analyzed).
    """
    if request.method == "POST":
        try:
            call_data = json.loads(request.body)
            event = call_data.get("event", "")

            logger.info(f"Retell webhook received: event={event}")

            if event in ("call_ended", "call_analyzed", ""):
                # Extract details and update DTMF inbox
                extracted_details = extract_call_details_retell(call_data)
                update_dtmf_inbox(extracted_details)

            return JsonResponse({"status": "success"})
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "failed"})
