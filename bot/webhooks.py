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
    ActiveCall,
    UserPhoneNumber,
    PendingDTMFApproval,
    SMSInbox,
)
from bot.utils import get_user_subscription_by_call_id, get_user_language
from bot.call_gate import classify_destination, US_CA_OVERAGE_RATE
from payment.models import (
    ManageFreePlanSingleIVRCall,
    UserSubscription,
    DTMF_Inbox,
)
from payment.views import debit_wallet, credit_wallet_balance
from user.models import TelegramUser

logger = logging.getLogger(__name__)

# Track last seen transcript index per call to avoid duplicate messages
_transcript_cursor = {}


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
    """
    Update call status to 'started' in local DB.
    Register ActiveCall for real-time billing and pre-deduct 2 minutes from wallet.
    """
    call_id = call_data.get("call_id", "")
    to_number = call_data.get("to_number", "")
    from_number = call_data.get("from_number", "")
    logger.info(f"[call_started] call_id={call_id}")

    # Update BatchCallLogs
    BatchCallLogs.objects.filter(call_id=call_id).update(call_status="started")

    # Update CallLogsTable
    CallLogsTable.objects.filter(call_id=call_id).update(call_status="started")

    # Update free plan tracking
    ManageFreePlanSingleIVRCall.objects.filter(call_id=call_id).update(call_status="started")

    # ---- Register ActiveCall for real-time billing ----
    call_log = CallLogsTable.objects.filter(call_id=call_id).first()
    if not call_log:
        logger.warning(f"[call_started] No CallLogsTable entry for {call_id}, skipping ActiveCall")
        return

    user_id = call_log.user_id
    region, rate, is_domestic = classify_destination(to_number)

    # Determine billing source
    billing_source = "plan"
    effective_rate = Decimal("0.00")

    if not is_domestic:
        billing_source = "wallet"
        effective_rate = rate
    else:
        # Check if user has plan minutes, otherwise wallet overage
        try:
            sub = UserSubscription.objects.get(user_id=user_id)
            if sub.subscription_status == "active" and sub.plan_id and sub.plan_id.plan_price > 0:
                billing_source = "plan"
                effective_rate = Decimal("0.00")
            else:
                billing_source = "wallet"
                effective_rate = US_CA_OVERAGE_RATE
        except UserSubscription.DoesNotExist:
            billing_source = "wallet"
            effective_rate = US_CA_OVERAGE_RATE

    # Determine call type
    batch_call = BatchCallLogs.objects.filter(call_id=call_id).exists()
    call_type = "bulk" if batch_call else "single"

    now = timezone.now()
    ActiveCall.objects.update_or_create(
        call_id=call_id,
        defaults={
            "user_id": user_id,
            "to_number": to_number,
            "from_number": from_number or "",
            "region": region,
            "rate_per_minute": effective_rate,
            "call_type": call_type,
            "billing_source": billing_source,
            "start_time": now,
            "last_billed_at": now,
            "total_billed": Decimal("0.00"),
            "warning_sent": False,
            "is_active": True,
        },
    )

    # Pre-deduct 2 minutes for wallet-billed calls
    if billing_source == "wallet" and effective_rate > 0:
        pre_hold = effective_rate * 2
        result = debit_wallet(
            user_id, float(pre_hold),
            description=f"Pre-hold: {region} call ({call_id[:12]})",
            tx_type="OVR",
        )
        if result["status"] == 200:
            ActiveCall.objects.filter(call_id=call_id).update(total_billed=pre_hold)
            logger.info(f"[call_started] Pre-deducted ${pre_hold} for {region} call {call_id}")
        else:
            logger.warning(f"[call_started] Pre-deduct failed for {call_id}: {result}")

    logger.info(f"[call_started] ActiveCall registered: {call_id} region={region} rate=${effective_rate} billing={billing_source}")


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

    # ---- 5. Reconcile real-time billing via ActiveCall ----
    _reconcile_active_call(call_id, to_number, duration_minutes)


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



def _reconcile_active_call(call_id, to_number, duration_minutes):
    """
    Reconcile billing when call ends:
    - Calculate final cost based on actual duration
    - Compare with what was already billed during the call
    - Charge shortfall or refund overpayment
    - Mark ActiveCall as inactive
    """
    try:
        active_call = ActiveCall.objects.filter(call_id=call_id, is_active=True).first()
        if not active_call:
            # No active call record — might be a plan-only call or old call
            # Fall back to simple international billing
            if to_number and duration_minutes > 0:
                region, rate, is_domestic = classify_destination(to_number)
                if not is_domestic:
                    _bill_international_fallback(call_id, to_number, duration_minutes)
            return

        user_id = active_call.user_id
        effective_rate = active_call.rate_per_minute
        already_billed = active_call.total_billed

        # Calculate final cost
        if effective_rate > 0:
            final_cost = effective_rate * Decimal(str(round(duration_minutes, 4)))
        else:
            final_cost = Decimal("0.00")

        difference = final_cost - already_billed

        if difference > Decimal("0.01"):
            # Under-billed — charge the shortfall
            result = debit_wallet(
                user_id, float(difference),
                description=f"Call settle: {active_call.region} ({call_id[:12]}) +${difference:.2f}",
                tx_type="OVR",
            )
            if result["status"] == 200:
                logger.info(f"[reconcile] Charged shortfall ${difference:.2f} for {call_id}")
            else:
                logger.warning(f"[reconcile] Shortfall charge failed for {call_id}: {result}")

        elif difference < Decimal("-0.01"):
            # Over-billed — refund the excess
            refund_amount = abs(difference)
            result = credit_wallet_balance(
                user_id, float(refund_amount),
                description=f"Call refund: {active_call.region} ({call_id[:12]}) -${refund_amount:.2f}",
                tx_type="RFD",
            )
            if result["status"] == 200:
                logger.info(f"[reconcile] Refunded ${refund_amount:.2f} for {call_id}")

        # Mark call as inactive
        active_call.is_active = False
        active_call.total_billed = final_cost if final_cost > already_billed else already_billed
        active_call.save()

        # Notify user of final charge
        if effective_rate > 0:
            try:
                user = TelegramUser.objects.get(user_id=user_id)
                bot.send_message(
                    user_id,
                    f"📞 Call to {active_call.region} ended.\n"
                    f"⏱ Duration: {duration_minutes:.2f} min\n"
                    f"💳 Total charged: ${final_cost:.2f} (${effective_rate}/min)\n"
                    f"💰 Wallet balance: ${user.wallet_balance:.2f}",
                )
            except Exception:
                pass

        logger.info(
            f"[reconcile] Call {call_id} settled: final=${final_cost:.2f}, "
            f"pre-billed=${already_billed:.2f}, diff=${difference:.2f}"
        )

    except Exception as e:
        logger.error(f"[reconcile] Error for {call_id}: {e}")


def _bill_international_fallback(call_id, to_number, duration_minutes):
    """Fallback billing for international calls without ActiveCall record."""
    try:
        region, rate, is_domestic = classify_destination(to_number)
        if is_domestic:
            return

        call_log = CallLogsTable.objects.filter(call_id=call_id).first()
        if not call_log:
            return

        user_id = call_log.user_id
        charge = rate * Decimal(str(round(duration_minutes, 2)))

        result = debit_wallet(
            user_id, float(charge),
            description=f"Intl call to {region}: {duration_minutes:.2f}min @ ${rate}/min",
            tx_type="OVR",
        )

        if result["status"] == 200:
            logger.info(f"[intl_fallback] Charged ${charge:.2f} for {region} call {call_id}")
        else:
            logger.warning(f"[intl_fallback] Charge failed for {call_id}: {result}")
    except Exception as e:
        logger.error(f"[intl_fallback] Error for {call_id}: {e}")


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
# transcript_updated — real-time DTMF streaming to bot user
# =============================================================================

def _handle_transcript_updated(call_data):
    """
    Process real-time transcript updates to detect DTMF presses
    and stream them to the bot user via Telegram instantly.
    Only applicable for single IVR calls (not bulk campaigns).
    """
    call_id = call_data.get("call_id", "")
    transcript_obj = call_data.get("transcript_with_tool_calls") or call_data.get("transcript_object", [])

    if not transcript_obj:
        return

    # Get cursor position — only process new entries
    cursor = _transcript_cursor.get(call_id, 0)
    new_entries = transcript_obj[cursor:]
    _transcript_cursor[call_id] = len(transcript_obj)

    if not new_entries:
        return

    # Look up user — skip bulk campaign calls
    call_log = CallLogsTable.objects.filter(call_id=call_id).first()
    if not call_log:
        return
    user_id = call_log.user_id

    # Skip bulk calls — supervisor check is single-call only
    if BatchCallLogs.objects.filter(call_id=call_id).exists():
        return

    for entry in new_entries:
        if entry.get("role") != "user":
            continue
        text = entry.get("content", "")

        # Detect DTMF presses — Retell formats as "Pressed Button: X"
        if "Pressed Button: " in text:
            digit = text.split("Pressed Button: ")[1].strip()
            try:
                bot.send_message(
                    user_id,
                    f"🔢 *DTMF Input Detected*\nCaller pressed: `{digit}`\nCall: `{call_id[:12]}...`",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning(f"[transcript_updated] Failed to notify user {user_id}: {e}")


def _deliver_recording_to_user(call_data):
    """Send call recording to bot user via Telegram after call ends."""
    call_id = call_data.get("call_id", "")
    recording_url = call_data.get("recording_url", "")
    if not recording_url:
        return

    call_log = CallLogsTable.objects.filter(call_id=call_id).first()
    if not call_log:
        return

    user_id = call_log.user_id
    to_number = call_data.get("to_number", "")
    from_number = call_data.get("from_number", "")
    duration_ms = call_data.get("duration_ms", 0) or 0
    duration_min = duration_ms / 60000.0
    direction = call_data.get("direction", "outbound")

    # Check if this is an inbound call to user's purchased number
    is_inbound = False
    if direction == "inbound" or UserPhoneNumber.objects.filter(
        phone_number=to_number, user__user_id=user_id, is_active=True
    ).exists():
        is_inbound = True

    try:
        if is_inbound:
            msg = (
                f"📬 *Inbound Call Recording*\n"
                f"From: `{from_number}`\n"
                f"To: `{to_number}`\n"
                f"Duration: {duration_min:.1f} min\n"
                f"🎙 [Listen to recording]({recording_url})"
            )
        else:
            msg = (
                f"🎙 *Call Recording Available*\n"
                f"To: `{to_number}`\n"
                f"Duration: {duration_min:.1f} min\n"
                f"🔗 [Listen to recording]({recording_url})"
            )
        bot.send_message(user_id, msg, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.warning(f"[recording] Failed to send recording to user {user_id}: {e}")


# =============================================================================
# Supervisor DTMF Check — called by Retell custom function mid-call
# =============================================================================

@csrf_exempt
def dtmf_supervisor_check(request):
    """
    Endpoint called by Retell custom function tool during single IVR calls.
    Receives DTMF digits, notifies bot user, polls for approval/rejection.
    Only for single calls, NOT bulk campaigns.

    POST /api/dtmf/supervisor-check
    Body: {"call_id": "...", "args": {"digits": "123456", "node_name": "Enter PIN"}}
    """
    if request.method != "POST":
        return JsonResponse({"status": "method_not_allowed"}, status=405)

    try:
        payload = json.loads(request.body)
        call_id = payload.get("call_id", "")
        args = payload.get("args", {})
        digits = args.get("digits", "")
        node_name = args.get("node_name", "DTMF Input")

        if not call_id or not digits:
            return JsonResponse({"result": "proceed", "message": "Missing data, proceeding."})

        # Look up user
        call_log = CallLogsTable.objects.filter(call_id=call_id).first()
        if not call_log:
            return JsonResponse({"result": "proceed", "message": "Call not found, proceeding."})

        user_id = call_log.user_id

        # Skip bulk campaign calls — proceed without supervisor check
        if BatchCallLogs.objects.filter(call_id=call_id).exists():
            return JsonResponse({"result": "proceed", "message": "Bulk call, auto-approved."})

        # Create pending approval
        approval = PendingDTMFApproval.objects.create(
            call_id=call_id,
            user_id=user_id,
            digits=digits,
            node_name=node_name,
            status="pending",
        )

        # Notify bot user
        from telebot import types
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"dtmf_approve_{approval.id}"),
            types.InlineKeyboardButton("❌ Re-enter", callback_data=f"dtmf_reject_{approval.id}"),
        )
        try:
            bot.send_message(
                user_id,
                f"🔔 *Supervisor Check*\n\n"
                f"Step: *{node_name}*\n"
                f"Caller entered: `{digits}`\n"
                f"Call: `{call_id[:16]}...`\n\n"
                f"⏱ Respond within 20 seconds or it will auto-approve.",
                reply_markup=markup,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"[supervisor] Failed to notify user {user_id}: {e}")
            return JsonResponse({"result": "proceed", "message": "Notification failed, auto-approved."})

        # Poll for response — up to 20 seconds
        import time
        for _ in range(10):
            time.sleep(2)
            approval.refresh_from_db()
            if approval.status == "approved":
                return JsonResponse({"result": "proceed", "message": "Supervisor approved."})
            elif approval.status == "rejected":
                return JsonResponse({"result": "re_enter", "message": "Supervisor rejected. Ask caller to re-enter."})

        # Timeout — auto-approve
        approval.status = "timeout"
        approval.resolved_at = timezone.now()
        approval.save()
        return JsonResponse({"result": "proceed", "message": "Timeout, auto-approved."})

    except json.JSONDecodeError:
        return JsonResponse({"result": "proceed", "message": "Invalid JSON."})
    except Exception as e:
        logger.error(f"[supervisor] Error: {e}")
        return JsonResponse({"result": "proceed", "message": f"Error: {str(e)}"})


# =============================================================================
# Inbound SMS Webhook — delivers SMS to bot user's Telegram
# =============================================================================

@csrf_exempt
def inbound_sms_webhook(request):
    """
    Receives inbound SMS forwarded from Retell's inbound webhook.
    Stores in SMSInbox and delivers to bot user via Telegram.

    POST /api/webhook/sms
    Body: {"to_number": "+1...", "from_number": "+1...", "message": "Hello...", ...}
    """
    if request.method != "POST":
        return JsonResponse({"status": "method_not_allowed"}, status=405)

    try:
        payload = json.loads(request.body)
        to_number = payload.get("to_number", payload.get("to", ""))
        from_number = payload.get("from_number", payload.get("from", ""))
        message_text = payload.get("message", payload.get("text", payload.get("content", "")))

        if not to_number or not from_number:
            return JsonResponse({"status": "error", "message": "Missing number fields"}, status=400)

        # Find the user who owns this number
        phone_record = UserPhoneNumber.objects.filter(
            phone_number=to_number, is_active=True
        ).first()

        if not phone_record:
            logger.warning(f"[sms] Received SMS for unregistered number: {to_number}")
            return JsonResponse({"status": "ok", "message": "Number not assigned to any user"})

        user_id = phone_record.user.user_id

        # Store in SMS Inbox
        SMSInbox.objects.create(
            user=phone_record.user,
            phone_number=to_number,
            from_number=from_number,
            message=message_text or "(empty message)",
        )

        # Deliver to bot user via Telegram
        try:
            bot.send_message(
                user_id,
                f"📩 *New SMS Received*\n\n"
                f"From: `{from_number}`\n"
                f"To: `{to_number}`\n"
                f"Message:\n{message_text or '(empty)'}",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"[sms] Failed to deliver SMS to user {user_id}: {e}")

        logger.info(f"[sms] SMS from {from_number} to {to_number} delivered to user {user_id}")
        return JsonResponse({"status": "ok"})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"[sms] Error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


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
            _deliver_recording_to_user(call_data)
            # Clean up transcript cursor
            _transcript_cursor.pop(call_data.get("call_id", ""), None)
        elif event == "call_analyzed":
            _handle_call_analyzed(call_data)
        elif event == "transcript_updated":
            _handle_transcript_updated(call_data)
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
