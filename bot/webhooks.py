"""
Retell AI Webhook Handlers — replaces Celery polling tasks.

Events handled:
  - call_started  → log call start time
  - call_ended    → process duration, billing, DTMF, update call logs
  - call_analyzed → extract variables, transcripts (post-processing)

Replaces these Celery polling tasks:
  - check_call_status       (batch call duration monitoring)
  - call_status_free_plan   (free plan call limit enforcement)
  - process_call_logs       (DTMF extraction)
"""
import json
import logging
from datetime import datetime, timezone as tz
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from bot.bot_config import bot
from bot.models import (
    CallDuration,
    BatchCallLogs,
    CallLogsTable,
)
from bot.utils import get_user_subscription_by_call_id, get_user_language
from bot.call_gate import classify_destination, US_CA_OVERAGE_RATE
from payment.models import (
    ManageFreePlanSingleIVRCall,
    UserSubscription,
    DTMF_Inbox,
)
from payment.views import debit_wallet
from user.models import TelegramUser

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================

def _epoch_ms_to_datetime(epoch_ms):
    """Convert Retell epoch milliseconds to timezone-aware datetime."""
    if not epoch_ms:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, tz=tz.utc)


def _extract_dtmf_from_transcript(transcript_object):
    """Extract DTMF digits from Retell transcript."""
    dtmf_digits = []
    if not transcript_object:
        return ""
    for entry in transcript_object:
        if entry.get("role") == "user":
            text = entry.get("content", "")
            # Retell marks DTMF as "Pressed Button: X"
            if "Pressed Button: " in text:
                digit = text.split("Pressed Button: ")[1].strip()
                if digit.isdigit():
                    dtmf_digits.append(digit)
    return "".join(dtmf_digits) if dtmf_digits else ""


# =============================================================================
# call_started — log the start of a call
# =============================================================================

def _handle_call_started(call_data):
    """Update call status to 'started' in local DB."""
    call_id = call_data.get("call_id", "")
    logger.info(f"[call_started] call_id={call_id}")

    # Update BatchCallLogs
    BatchCallLogs.objects.filter(call_id=call_id).update(call_status="started")

    # Update CallLogsTable
    CallLogsTable.objects.filter(call_id=call_id).update(call_status="started")

    # Update free plan tracking
    ManageFreePlanSingleIVRCall.objects.filter(call_id=call_id).update(call_status="started")


# =============================================================================
# call_ended — replaces check_call_status, call_status_free_plan, process_call_logs
# =============================================================================

def _handle_call_ended(call_data):
    """
    Process a completed call:
    1. Calculate duration & update subscription minutes
    2. Track overage for billing
    3. Extract DTMF data
    4. Update all call log tables
    """
    call_id = call_data.get("call_id", "")
    agent_id = call_data.get("agent_id", "")
    to_number = call_data.get("to_number", "")
    from_number = call_data.get("from_number", "")
    call_status = call_data.get("call_status", "ended")
    duration_ms = call_data.get("duration_ms", 0) or 0
    start_ts = call_data.get("start_timestamp")
    end_ts = call_data.get("end_timestamp")
    transcript_obj = call_data.get("transcript_object", [])
    disconnection_reason = call_data.get("disconnection_reason", "")
    recording_url = call_data.get("recording_url", "")

    started_at = _epoch_ms_to_datetime(start_ts)
    ended_at = _epoch_ms_to_datetime(end_ts)
    duration_minutes = duration_ms / 60000.0

    logger.info(
        f"[call_ended] call_id={call_id}, duration={duration_minutes:.2f}min, "
        f"reason={disconnection_reason}"
    )

    # ---- 1. Update BatchCallLogs (batch calls) ----
    batch_call = BatchCallLogs.objects.filter(call_id=call_id).first()
    if batch_call:
        batch_call.call_status = "complete"
        batch_call.save()

        # Process subscription minutes (replaces check_call_status)
        _process_batch_call_duration(
            call_id, agent_id, batch_call, started_at, ended_at,
            duration_minutes, duration_ms / 1000.0
        )

    # ---- 2. Update free plan calls (replaces call_status_free_plan) ----
    free_plan_call = ManageFreePlanSingleIVRCall.objects.filter(call_id=call_id).first()
    if free_plan_call:
        free_plan_call.call_status = "complete"
        free_plan_call.save()

        _process_free_plan_call_duration(
            call_id, agent_id, free_plan_call, started_at, ended_at,
            duration_minutes, duration_ms / 1000.0
        )

    # ---- 3. Update CallLogsTable ----
    CallLogsTable.objects.filter(call_id=call_id).update(call_status="complete")

    # ---- 4. Extract DTMF and update inbox (replaces process_call_logs) ----
    dtmf_input = _extract_dtmf_from_transcript(transcript_obj)
    if dtmf_input:
        try:
            dtmf_record = DTMF_Inbox.objects.filter(call_id=call_id).first()
            if dtmf_record:
                dtmf_record.dtmf_input = dtmf_input
                dtmf_record.timestamp = ended_at
                dtmf_record.save()
                logger.info(f"[call_ended] DTMF updated: {dtmf_input} for {call_id}")
        except Exception as e:
            logger.warning(f"[call_ended] DTMF update failed for {call_id}: {e}")

    # ---- 5. International call billing — debit wallet in real-time ----
    if to_number and duration_minutes > 0:
        _process_international_billing(call_id, to_number, duration_minutes)


def _process_batch_call_duration(call_id, agent_id, batch_call, started_at, ended_at, duration_minutes, duration_seconds):
    """
    Process batch call duration — deduct from subscription minutes, track overage.
    Replaces the 'complete' branch of check_call_status Celery task.
    """
    try:
        subscription_result = get_user_subscription_by_call_id(call_id)
        if subscription_result["status"] != "Success":
            logger.warning(f"No subscription for call {call_id}: {subscription_result['status']}")
            return

        user_subscription = subscription_result["user_subscription"]
        bulk_ivr_left = float(user_subscription.bulk_ivr_calls_left or 0)

        if duration_minutes > bulk_ivr_left:
            # Overage — track additional minutes for billing
            overage = duration_minutes - bulk_ivr_left
            CallDuration.objects.update_or_create(
                call_id=call_id,
                pathway_id=agent_id,
                defaults={
                    "start_time": started_at,
                    "end_time": ended_at,
                    "queue_status": "complete",
                    "duration_in_seconds": duration_seconds,
                    "additional_minutes": f"{overage}",
                    "user_id": subscription_result["user_id"],
                },
            )
            user_subscription.bulk_ivr_calls_left = 0
            user_subscription.save()
            logger.info(f"[batch] Overage {overage:.2f}min for call {call_id}")
        else:
            # Within limits
            remaining = bulk_ivr_left - duration_minutes
            CallDuration.objects.update_or_create(
                call_id=call_id,
                pathway_id=agent_id,
                defaults={
                    "start_time": started_at,
                    "end_time": ended_at,
                    "queue_status": "complete",
                    "duration_in_seconds": duration_seconds,
                    "additional_minutes": 0,
                    "user_id": subscription_result["user_id"],
                },
            )
            user_subscription.bulk_ivr_calls_left = Decimal(str(remaining))
            user_subscription.save()
            logger.info(f"[batch] {remaining:.2f}min remaining after call {call_id}")
    except Exception as e:
        logger.error(f"[batch] Duration processing error for {call_id}: {e}")


def _process_free_plan_call_duration(call_id, agent_id, free_call, started_at, ended_at, duration_minutes, duration_seconds):
    """
    Process free plan call duration — deduct from single IVR minutes.
    Replaces the 'complete' branch of call_status_free_plan Celery task.
    """
    try:
        subscription_result = get_user_subscription_by_call_id(call_id)
        if subscription_result["status"] != "Success":
            return

        user_subscription = subscription_result["user_subscription"]
        single_ivr_left = float(user_subscription.single_ivr_left or 0)

        if duration_minutes > single_ivr_left:
            overage = duration_minutes - single_ivr_left
            CallDuration.objects.update_or_create(
                call_id=call_id,
                pathway_id=agent_id,
                defaults={
                    "start_time": started_at,
                    "end_time": ended_at,
                    "queue_status": "complete",
                    "duration_in_seconds": duration_seconds,
                    "additional_minutes": f"{overage}",
                    "user_id": subscription_result["user_id"],
                },
            )
            user_subscription.single_ivr_left = 0
            user_subscription.save()
        else:
            remaining = single_ivr_left - duration_minutes
            CallDuration.objects.update_or_create(
                call_id=call_id,
                pathway_id=agent_id,
                defaults={
                    "start_time": started_at,
                    "end_time": ended_at,
                    "queue_status": "complete",
                    "duration_in_seconds": duration_seconds,
                    "additional_minutes": 0,
                    "user_id": subscription_result["user_id"],
                },
            )
            user_subscription.single_ivr_left = Decimal(str(remaining))
            user_subscription.save()
    except Exception as e:
        logger.error(f"[free_plan] Duration processing error for {call_id}: {e}")



def _process_international_billing(call_id, to_number, duration_minutes):
    """
    Bill international calls from wallet in real-time.
    US/Canada calls are handled by plan minutes/overage — skip here.
    """
    try:
        region, rate, is_domestic = classify_destination(to_number)
        if is_domestic:
            return  # US/Canada — handled by plan minutes or overage task

        # Find user_id from CallLogsTable
        call_log = CallLogsTable.objects.filter(call_id=call_id).first()
        if not call_log:
            logger.warning(f"[intl_billing] No call log for {call_id}")
            return

        user_id = call_log.user_id
        charge = rate * Decimal(str(round(duration_minutes, 2)))

        result = debit_wallet(
            user_id, float(charge),
            description=f"Intl call to {region}: {duration_minutes:.2f}min @ ${rate}/min",
            tx_type="OVR",
        )

        if result["status"] == 200:
            logger.info(
                f"[intl_billing] Charged ${charge:.2f} for {region} call "
                f"({duration_minutes:.2f}min) user={user_id} call={call_id}"
            )
            # Notify user
            try:
                lg = get_user_language(user_id)
                bot.send_message(
                    user_id,
                    f"📞 International call to {region} completed.\n"
                    f"⏱ Duration: {duration_minutes:.2f} min\n"
                    f"💳 Charged: ${charge:.2f} (${rate}/min)\n"
                    f"💰 Remaining balance: ${result['data']['balance']}",
                )
            except Exception:
                pass
        elif result["status"] == 402:
            logger.warning(
                f"[intl_billing] Insufficient balance for intl call: "
                f"user={user_id}, charge=${charge:.2f}, call={call_id}"
            )
            try:
                bot.send_message(
                    user_id,
                    f"⚠️ Insufficient wallet balance for international call charge.\n"
                    f"Amount due: ${charge:.2f} for {region} call.\n"
                    f"Please top up your wallet immediately.",
                )
            except Exception:
                pass
        else:
            logger.error(f"[intl_billing] Debit failed: {result}")
    except Exception as e:
        logger.error(f"[intl_billing] Error processing intl billing for {call_id}: {e}")


# =============================================================================
# call_analyzed — post-call analysis (bonus: Retell provides sentiment, summary)
# =============================================================================

def _handle_call_analyzed(call_data):
    """Process post-call analysis (sentiment, summary, success evaluation)."""
    call_id = call_data.get("call_id", "")
    call_analysis = call_data.get("call_analysis", {})

    if call_analysis:
        logger.info(
            f"[call_analyzed] call_id={call_id}, "
            f"sentiment={call_analysis.get('user_sentiment', 'N/A')}, "
            f"summary={call_analysis.get('call_summary', 'N/A')[:100]}"
        )
    # Future: store analysis in a CallAnalysis model for dashboard


# =============================================================================
# Webhook endpoints
# =============================================================================

@csrf_exempt
def retell_webhook(request):
    """
    Main Retell AI webhook — handles all call lifecycle events.
    Replaces: check_call_status, call_status_free_plan, process_call_logs
    """
    if request.method != "POST":
        return JsonResponse({"status": "method_not_allowed"}, status=405)

    try:
        payload = json.loads(request.body)
        event = payload.get("event", "")
        call_data = payload.get("data", payload)

        logger.info(f"[retell_webhook] event={event}, call_id={call_data.get('call_id', 'unknown')}")

        if event == "call_started":
            _handle_call_started(call_data)
        elif event == "call_ended":
            _handle_call_ended(call_data)
        elif event == "call_analyzed":
            _handle_call_analyzed(call_data)
        else:
            logger.warning(f"[retell_webhook] Unknown event: {event}")

        return JsonResponse({"status": "ok"})
    except json.JSONDecodeError:
        logger.error("[retell_webhook] Invalid JSON payload")
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"[retell_webhook] Error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def call_details_webhook(request):
    """Legacy webhook — redirects to retell_webhook for backward compat."""
    return retell_webhook(request)
