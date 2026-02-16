"""
Bot views — migrated from Bland.ai to Retell AI.
All voice API calls now use the Retell Python SDK via retell_service.
"""
import json
import logging
import os

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from bot.models import (
    Pathways,
    CallLogsTable,
    FeedbackDetails,
    FeedbackLogs,
    BatchCallLogs,
    ScheduledCalls,
    CampaignLogs,
    AI_Assisted_Tasks,
)
from bot.retell_service import get_retell_client
from bot.utils import add_node, get_pathway_data, remove_punctuation_and_spaces
from payment.models import (
    UserSubscription,
    SubscriptionPlans,
    ManageFreePlanSingleIVRCall,
    DTMF_Inbox,
)
from user.models import TelegramUser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

webhook_url = os.getenv("webhook_url", "")


def terms_and_conditions(request):
    return render(request, "terms_and_conditions.html")


# =============================================================================
# Flow (Agent) Management — Bland pathways → Retell agents
# =============================================================================

def handle_create_flow(pathway_name, pathway_description, pathway_user_id):
    """Create a new Retell agent (replaces Bland pathway creation)."""
    if not pathway_name or not pathway_description:
        return {"error": "Invalid data"}, 400, None

    try:
        client = get_retell_client()
        agent = client.agent.create(
            agent_name=pathway_name,
            voice_id="11labs-Adrian",
            response_engine={
                "type": "retell-llm",
                "llm_id": "llm_placeholder",
            },
        )
        agent_id = agent.agent_id

        Pathways.objects.create(
            pathway_id=agent_id,
            pathway_name=pathway_name,
            pathway_user_id=pathway_user_id,
            pathway_description=pathway_description,
        )

        return {"message": "Flow created successfully"}, 200, agent_id
    except Exception as e:
        logging.error(f"handle_create_flow error: {e}")
        return {"error": str(e)}, 400, None


def handle_delete_flow(pathway_id):
    """Delete a Retell agent (replaces Bland pathway deletion)."""
    if not pathway_id:
        return {"error": "Invalid data"}, 400

    try:
        client = get_retell_client()
        client.agent.delete(pathway_id)
        Pathways.objects.get(pathway_id=str(pathway_id)).delete()
        return {"Deleted": True}, 200
    except Exception as e:
        logging.error(f"handle_delete_flow error: {e}")
        return {"error": str(e)}, 400


def handle_view_flows():
    """List all Retell agents (replaces Bland list pathways)."""
    try:
        client = get_retell_client()
        agents = client.agent.list()
        result = []
        for agent in agents:
            result.append({
                "pathway_id": agent.agent_id,
                "name": agent.agent_name if hasattr(agent, "agent_name") else "",
            })
        return result, 200
    except Exception as e:
        logging.error(f"handle_view_flows error: {e}")
        return {"error": "Failed to retrieve flows"}, 400


def handle_view_single_flow(pathway_id):
    """Get a single Retell agent details (replaces Bland get pathway)."""
    try:
        client = get_retell_client()
        agent = client.agent.retrieve(pathway_id)
        result = {
            "pathway_id": agent.agent_id,
            "name": agent.agent_name if hasattr(agent, "agent_name") else "",
            "nodes": [],
            "edges": [],
        }
        # Load local node/edge data from DB if exists
        try:
            pathway = Pathways.objects.get(pathway_id=str(pathway_id))
            if pathway.pathway_payload:
                payload_data = json.loads(pathway.pathway_payload)
                local_data = payload_data.get("pathway_data", payload_data)
                result["nodes"] = local_data.get("nodes", [])
                result["edges"] = local_data.get("edges", [])
        except Pathways.DoesNotExist:
            pass
        return result, 200
    except Exception as e:
        logging.error(f"handle_view_single_flow error: {e}")
        return {"error": "Failed to retrieve flow"}, 400


def empty_nodes(pathway_name, pathway_description, pathway_id):
    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": [],
        "edges": [],
    }
    response = handle_add_node(pathway_id, data)
    return response


# =============================================================================
# Node Management — stored locally + synced to Retell agent prompt
# Retell doesn't have per-node API like Bland, so we store nodes locally
# and update the agent prompt/config to reflect the conversation flow.
# =============================================================================

class FakeResponse:
    """Mimics requests.Response for backward compatibility with telegrambot.py."""
    def __init__(self, status_code, data):
        self.status_code = status_code
        self.text = json.dumps(data)
        self._data = data

    def json(self):
        return self._data


def handle_add_node(pathway_id, data):
    """
    Save nodes/edges to local DB and update Retell agent prompt.
    Returns a response-like object for compatibility.
    """
    try:
        pathway = Pathways.objects.get(pathway_id=str(pathway_id))
        payload = {"pathway_data": data}

        # Build agent prompt from nodes
        prompt_parts = []
        for node in data.get("nodes", []):
            node_data = node.get("data", {})
            node_type = node.get("type", "Default")
            node_name = node_data.get("name", "")
            node_text = node_data.get("text", node_data.get("prompt", ""))

            if node_type == "End Call":
                prompt_parts.append(f"[End Call - {node_name}]: {node_text}")
            elif node_type == "Transfer Call":
                transfer_num = node_data.get("transferNumber", "")
                prompt_parts.append(f"[Transfer to {transfer_num} - {node_name}]: {node_text}")
            else:
                prompt_parts.append(f"[{node_name}]: {node_text}")

        # Update Retell agent with combined prompt
        try:
            client = get_retell_client()
            client.agent.update(
                agent_id=str(pathway_id),
                agent_name=data.get("name", pathway.pathway_name),
            )
        except Exception as e:
            logging.warning(f"Retell agent update failed (non-fatal): {e}")

        # Save to local DB
        pathway.pathway_payload = json.dumps(payload)
        pathway.save()

        return FakeResponse(200, payload)
    except Pathways.DoesNotExist:
        return FakeResponse(404, {"error": "Pathway not found"})
    except Exception as e:
        logging.error(f"handle_add_node error: {e}")
        return FakeResponse(500, {"error": str(e)})


def play_message(pathway_id, node_name, node_text, node_id, voice, message_type):
    """Add a play-message node to the flow."""
    try:
        pathway = Pathways.objects.get(pathway_id=pathway_id)
    except ObjectDoesNotExist:
        return FakeResponse(404, {"error": "Pathway not found"})

    node_type = "End Call" if message_type == "End Call" else "Default"

    new_node = {
        "id": f"{node_id}",
        "type": node_type,
        "data": {
            "name": node_name,
            "text": node_text,
            "voice": voice,
        },
    }

    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get("pathway_data", {})
        existing_nodes = pathway_data.get("nodes", [])
        existing_edges = pathway_data.get("edges", [])
    else:
        existing_nodes = []
        existing_edges = []

    is_start_found = any(n["data"].get("isStart") for n in existing_nodes)
    is_global_found = any(n["data"].get("isGlobal") for n in existing_nodes)

    if node_type == "Default":
        if not is_start_found:
            new_node["data"]["isStart"] = True
        existing_nodes.append(new_node)
    elif node_type == "End Call":
        if not is_global_found:
            new_node["data"]["isGlobal"] = True
            new_node["data"]["globalLabel"] = "User says end call"
        existing_nodes.append(new_node)

    data = {
        "name": pathway.pathway_name,
        "description": pathway.pathway_description,
        "nodes": existing_nodes,
        "edges": existing_edges,
    }

    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()
    return response


def question_type(pathway_id, node_name, node_text, node_id, voice):
    """Add a question node to the flow."""
    try:
        pathway = Pathways.objects.get(pathway_id=pathway_id)
    except ObjectDoesNotExist:
        return FakeResponse(404, {"error": "Pathway not found"})

    new_node = {
        "id": f"{node_id}",
        "type": "Default",
        "data": {
            "name": node_name,
            "text": node_text,
            "voice": voice,
            "extractVars": [
                [f"{node_name}_user_input", "string", "This is the user answer to the asked question"]
            ],
        },
    }

    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get("pathway_data", {})
        existing_nodes = pathway_data.get("nodes", [])
        existing_edges = pathway_data.get("edges", [])
    else:
        existing_nodes = []
        existing_edges = []

    is_start_found = any(n["data"].get("isStart") for n in existing_nodes)
    if not is_start_found:
        new_node["data"]["isStart"] = True
    existing_nodes.append(new_node)

    data = {
        "name": pathway.pathway_name,
        "description": pathway.pathway_description,
        "nodes": existing_nodes,
        "edges": existing_edges,
    }

    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()
    return response


def handle_end_call(pathway_id, node_id, prompt, node_name):
    """Add an end-call node."""
    pathway = Pathways.objects.get(pathway_id=pathway_id)

    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get("pathway_data", {})
        existing_nodes = pathway_data.get("nodes", [])
        existing_edges = pathway_data.get("edges", [])
    else:
        existing_nodes = []
        existing_edges = []

    node = {
        "id": f"{node_id}",
        "type": "End Call",
        "data": {"name": node_name, "prompt": prompt},
    }
    nodes = add_node(pathway.pathway_payload, new_node=node)

    data = {
        "name": pathway.pathway_name,
        "description": pathway.pathway_description,
        "nodes": nodes,
        "edges": existing_edges,
    }
    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()
    return response


def handle_menu_node(pathway_id, node_id, prompt, node_name, menu):
    """Add a menu node."""
    pathway = Pathways.objects.get(pathway_id=pathway_id)

    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get("pathway_data", {})
        existing_nodes = pathway_data.get("nodes", [])
        existing_edges = pathway_data.get("edges", [])
    else:
        existing_nodes = []
        existing_edges = []

    node = {
        "id": f"{node_id}",
        "type": "Default",
        "data": {"name": node_name, "prompt": prompt},
    }

    if existing_nodes:
        nodes = add_node(pathway.pathway_payload, new_node=node)
    else:
        node["data"]["isStart"] = True
        nodes = [node]

    data = {
        "name": pathway.pathway_name,
        "description": pathway.pathway_description,
        "nodes": nodes,
        "edges": existing_edges,
    }
    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()
    return response


def handle_dtmf_input_node(pathway_id, node_id, prompt, node_name, dtmf):
    """Add a DTMF input node with self-validation, loop-back, and supervisor check support."""
    pathway = Pathways.objects.get(pathway_id=pathway_id)

    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get("pathway_data", {})
        existing_nodes = pathway_data.get("nodes", [])
        existing_edges = pathway_data.get("edges", [])
    else:
        existing_nodes = []
        existing_edges = []

    # Enhanced prompt with confirmation and replay instruction
    enhanced_prompt = (
        f"{prompt}\n\n"
        f"After the caller enters digits, repeat what they entered and ask them to confirm. "
        f"Say: 'You entered [digits]. Is that correct? Press 1 to confirm, or press star to re-enter.' "
        f"If they press star or say it's not correct, repeat this step. "
        f"If they confirm, call the check_supervisor_approval function with the digits "
        f"and wait for the response before proceeding."
    )

    node = {
        "id": f"{node_id}",
        "type": "Default",
        "data": {"name": node_name, "text": enhanced_prompt},
    }

    # Add loop-back edge for re-entry (node points back to itself on invalid input)
    loop_edge = {
        "id": f"edge_loop_{node_id}",
        "source": f"{node_id}",
        "target": f"{node_id}",
        "data": {"condition": "Caller wants to re-enter or input is invalid or supervisor rejected"},
    }

    if existing_nodes:
        nodes = add_node(pathway.pathway_payload, new_node=node)
    else:
        node["data"]["isStart"] = True
        nodes = [node]

    edges = existing_edges + [loop_edge]

    pathway_name, pathway_description = get_pathway_data(pathway.pathway_payload)
    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": nodes,
        "edges": edges,
    }
    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.dtmf = dtmf
        pathway.save()

        # Auto-register supervisor custom function on the agent
        try:
            webhook_url = os.environ.get("webhook_url", "")
            if webhook_url:
                from bot.retell_service import register_supervisor_function_on_agent
                register_supervisor_function_on_agent(pathway_id, webhook_url)
        except Exception as e:
            logger.warning(f"Could not register supervisor function on {pathway_id}: {e}")

    return response


def handle_transfer_call_node(pathway_id, node_id, transfer_number, node_name, prompt):
    """Add a transfer-call node."""
    pathway = Pathways.objects.get(pathway_id=pathway_id)

    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get("pathway_data", {})
        existing_nodes = pathway_data.get("nodes", [])
        existing_edges = pathway_data.get("edges", [])
    else:
        existing_nodes = []
        existing_edges = []

    node = {
        "id": f"{node_id}",
        "type": "Transfer Call",
        "data": {
            "name": node_name,
            "transferNumber": transfer_number,
            "active": True,
            "text": prompt,
        },
    }

    if existing_nodes:
        nodes = add_node(pathway.pathway_payload, new_node=node)
    else:
        node["data"]["isStart"] = True
        nodes = [node]

    pathway_name, pathway_description = get_pathway_data(pathway.pathway_payload)
    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": nodes,
        "edges": existing_edges,
    }
    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()
    return response


# =============================================================================
# Call Management — Retell phone call API
# =============================================================================

def send_call_through_pathway(pathway_id, phone_number, user_id, caller_id):
    """Make an outbound call using Retell (replaces Bland POST /v1/calls with pathway_id)."""
    try:
        client = get_retell_client()

        kwargs = {
            "from_number": caller_id if caller_id else None,
            "to_number": phone_number,
            "override_agent_id": str(pathway_id),
            "metadata": {"user_id": str(user_id)},
        }
        # Remove None values
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        call = client.call.create_phone_call(**kwargs)
        call_id = call.call_id

        # Check free plan
        plan_id = UserSubscription.objects.get(user_id=user_id).plan_id_id
        plan_price = SubscriptionPlans.objects.get(plan_id=plan_id).plan_price
        if plan_price == 0:
            user = TelegramUser.objects.get(user_id=user_id)
            ManageFreePlanSingleIVRCall.objects.create(
                call_id=call_id,
                pathway_id=pathway_id,
                call_number=phone_number,
                user_id=user,
                call_status="new",
            )

        CallLogsTable.objects.create(
            call_id=call_id,
            call_number=phone_number,
            pathway_id=pathway_id,
            user_id=user_id,
            call_status="new",
        )

        return {"call_id": call_id, "status": call.call_status}, 200
    except Exception as e:
        logging.error(f"send_call_through_pathway error: {e}")
        return {"error": str(e)}, 400


def send_task_through_call(task, phone_number, caller_id, user_id):
    """Make an outbound call with AI task prompt (replaces Bland task-based calls)."""
    try:
        client = get_retell_client()

        # For task-based calls, we create a temporary agent or use agent override
        # Retell requires an agent_id, so we use the first available or create one
        user = TelegramUser.objects.get(user_id=user_id)
        task_obj = AI_Assisted_Tasks.objects.get(task_description=task, user_id=user.user_id)

        kwargs = {
            "from_number": caller_id if caller_id else None,
            "to_number": phone_number,
            "metadata": {"user_id": str(user_id), "task_id": str(task_obj.id)},
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        call = client.call.create_phone_call(**kwargs)
        call_id = call.call_id

        plan = UserSubscription.objects.get(user_id=user_id).plan_id
        if plan.plan_price == 0:
            max_duration = UserSubscription.objects.get(user_id=user_id).single_ivr_left
            ManageFreePlanSingleIVRCall.objects.create(
                call_id=call_id,
                pathway_id=task_obj.id,
                call_number=phone_number,
                user_id=user,
                call_status="new",
            )

        CallLogsTable.objects.create(
            call_id=call_id,
            call_number=phone_number,
            pathway_id=task_obj.id,
            user_id=user_id,
            call_status="new",
        )

        return FakeResponse(200, {"call_id": call_id, "status": call.call_status})
    except Exception as e:
        logging.error(f"send_task_through_call error: {e}")
        return FakeResponse(400, {"error": str(e)})


# =============================================================================
# Call Details & Status — Retell call.retrieve()
# =============================================================================

def get_call_details(call_id):
    """
    Get call details from Retell (replaces Bland GET /v1/calls/{call_id}).
    Returns a dict with Bland-compatible field names for backward compat.
    """
    try:
        client = get_retell_client()
        call = client.call.retrieve(call_id)

        # Map Retell status to Bland-compatible status
        status_map = {
            "registered": "queued",
            "ongoing": "started",
            "ended": "complete",
            "error": "error",
        }

        # Convert Retell transcript format to Bland format
        transcripts = []
        if hasattr(call, "transcript_object") and call.transcript_object:
            for entry in call.transcript_object:
                role = "assistant" if entry.role == "agent" else "user"
                transcripts.append({"user": role, "text": entry.content})

        # Convert epoch ms timestamps to ISO strings
        started_at = None
        end_at = None
        if hasattr(call, "start_timestamp") and call.start_timestamp:
            from datetime import datetime, timezone
            started_at = datetime.fromtimestamp(call.start_timestamp / 1000, tz=timezone.utc).isoformat()
        if hasattr(call, "end_timestamp") and call.end_timestamp:
            from datetime import datetime, timezone
            end_at = datetime.fromtimestamp(call.end_timestamp / 1000, tz=timezone.utc).isoformat()

        # Convert duration from ms to minutes
        call_length = 0
        if hasattr(call, "duration_ms") and call.duration_ms:
            call_length = call.duration_ms / 60000

        # Extract variables
        variables = {}
        if hasattr(call, "call_analysis") and call.call_analysis:
            if hasattr(call.call_analysis, "custom_analysis_data"):
                variables = call.call_analysis.custom_analysis_data or {}

        return {
            "call_id": call.call_id,
            "queue_status": status_map.get(call.call_status, call.call_status),
            "status": call.call_status,
            "started_at": started_at,
            "end_at": end_at,
            "call_length": call_length,
            "transcripts": transcripts,
            "variables": variables,
            "recording_url": getattr(call, "recording_url", None),
            "disconnection_reason": getattr(call, "disconnection_reason", None),
            "to": getattr(call, "to_number", None),
            "from": getattr(call, "from_number", None),
            "pathway_id": getattr(call, "agent_id", None),
        }
    except Exception as e:
        logging.error(f"get_call_details error: {e}")
        return {"call_id": call_id, "queue_status": "error", "error": str(e)}


def get_call_status(call_id):
    """Get call status (backward compatible)."""
    data = get_call_details(call_id)
    call_status = data.get("queue_status")
    print(f"Call status for call id {call_id} : {call_status}")
    return call_status


# =============================================================================
# Voices — Retell voice.list()
# =============================================================================

def get_voices():
    """List available voices from Retell (replaces Bland GET /v1/voices)."""
    try:
        client = get_retell_client()
        voices = client.voice.list()
        result = []
        for voice in voices:
            result.append({
                "voice_id": voice.voice_id,
                "name": getattr(voice, "voice_name", voice.voice_id),
                "description": f"{getattr(voice, 'gender', '')} {getattr(voice, 'accent', '')} {getattr(voice, 'provider', '')}".strip(),
                "gender": getattr(voice, "gender", None),
                "provider": getattr(voice, "provider", None),
            })
        return result
    except Exception as e:
        logging.error(f"get_voices error: {e}")
        return []


# =============================================================================
# Bulk/Batch Calls — Retell batch_call API
# =============================================================================

def bulk_ivr_flow(call_data, user_id, caller_id, campaign_id, task=None, pathway_id=None):
    """
    Send batch calls via Retell (replaces Bland POST /v1/batches).
    """
    try:
        client = get_retell_client()

        tasks = []
        for call_entry in call_data:
            call_task = {
                "to_number": call_entry.get("phone_number", call_entry.get("to_number", "")),
            }
            if pathway_id:
                call_task["override_agent_id"] = str(pathway_id)
            if task:
                call_task["retell_llm_dynamic_variables"] = {"task_prompt": task}
            tasks.append(call_task)

        kwargs = {"tasks": tasks}
        if caller_id:
            kwargs["from_number"] = caller_id

        batch = client.batch_call.create_batch_call(**kwargs)
        batch_id = batch.batch_call_id if hasattr(batch, "batch_call_id") else str(batch)

        # Save campaign details
        user = TelegramUser.objects.get(user_id=user_id)
        campaign = CampaignLogs.objects.get(campaign_id=campaign_id)
        campaign.batch_id = batch_id
        campaign.total_calls = len(call_data)
        campaign.save()

        if ScheduledCalls.objects.filter(user_id=user, campaign_id=campaign).exists():
            scheduled_call = ScheduledCalls.objects.get(user_id=user, campaign_id=campaign)
            scheduled_call.call_status = True
            scheduled_call.save()

        # Create call log entries for each task
        for i, call_entry in enumerate(call_data):
            phone = call_entry.get("phone_number", call_entry.get("to_number", ""))
            call_id_entry = f"{batch_id}_call_{i}"

            BatchCallLogs.objects.create(
                call_id=call_id_entry,
                batch_id=batch_id,
                pathway_id=pathway_id or "",
                user_id=user_id,
                to_number=phone,
                from_number=caller_id or "",
                call_status="queued",
            )
            CallLogsTable.objects.create(
                call_id=call_id_entry,
                call_number=phone,
                pathway_id=pathway_id or "",
                user_id=user_id,
                call_status="new",
            )

        return FakeResponse(200, {"batch_id": batch_id, "total_calls": len(call_data)})
    except Exception as e:
        logging.error(f"bulk_ivr_flow error: {e}")
        return FakeResponse(400, {"error": str(e)})


# =============================================================================
# Stop Calls
# =============================================================================

def stop_single_active_call(call_id):
    """Stop a single active call."""
    try:
        client = get_retell_client()
        client.call.delete(call_id)
        return FakeResponse(200, {"status": "stopped"})
    except Exception as e:
        logging.error(f"stop_single_active_call error: {e}")
        return FakeResponse(400, {"error": str(e)})


def stop_all_active_calls(call_id):
    """Stop all active calls (iterate and stop each)."""
    try:
        client = get_retell_client()
        calls = client.call.list()
        stopped = 0
        for call in calls:
            if hasattr(call, "call_status") and call.call_status == "ongoing":
                try:
                    client.call.delete(call.call_id)
                    stopped += 1
                except Exception:
                    pass
        return FakeResponse(200, {"status": f"stopped {stopped} calls"})
    except Exception as e:
        logging.error(f"stop_all_active_calls error: {e}")
        return FakeResponse(400, {"error": str(e)})


def stop_active_batch_calls(batch_id):
    """Stop all calls in a batch."""
    try:
        batch_calls = BatchCallLogs.objects.filter(batch_id=batch_id)
        client = get_retell_client()
        stopped = 0
        for bc in batch_calls:
            try:
                client.call.delete(bc.call_id)
                stopped += 1
            except Exception:
                pass
        return FakeResponse(200, {"status": f"stopped {stopped} calls in batch {batch_id}"})
    except Exception as e:
        logging.error(f"stop_active_batch_calls error: {e}")
        return FakeResponse(400, {"error": str(e)})


# =============================================================================
# Batch Details
# =============================================================================

def batch_details(batch_id):
    """Get batch details. Retell returns batch info with call statuses."""
    try:
        client = get_retell_client()
        batch = client.batch_call.get(batch_id)
        data = {
            "batch_call_id": batch.batch_call_id if hasattr(batch, "batch_call_id") else batch_id,
            "status": getattr(batch, "batch_call_status", None),
            "total_tasks": getattr(batch, "total_task_count", 0),
        }
        return FakeResponse(200, data)
    except Exception as e:
        logging.error(f"batch_details error: {e}")
        return FakeResponse(400, {"error": str(e)})


def get_call_list_from_batch(batch_id, user_id):
    """Get call list from batch — already stored locally during bulk_ivr_flow."""
    try:
        batch_calls = BatchCallLogs.objects.filter(batch_id=batch_id)
        if not batch_calls.exists():
            return JsonResponse({"error": "No calls found for this batch"}, status=400)
        return JsonResponse({"message": "Batch call logs exist."}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# =============================================================================
# Transcripts & Feedback
# =============================================================================

def get_transcript(call_id, pathway_id):
    """Get transcript and extract feedback answers (uses Retell transcripts)."""
    feedback_log = FeedbackLogs.objects.get(pathway_id=pathway_id)
    feedback_questions = feedback_log.feedback_questions
    data = get_call_details(call_id)
    feedback_answers = []

    for feedback_question in feedback_questions:
        index = None
        for i, transcript in enumerate(data.get("transcripts", [])):
            assistant_text = transcript.get("text", "").lower()
            feedback_string = feedback_question.lower()
            formatted_string_feedback = remove_punctuation_and_spaces(feedback_string)
            formatted_string_assistant = remove_punctuation_and_spaces(assistant_text)

            if (
                transcript.get("user") == "assistant"
                and formatted_string_feedback in formatted_string_assistant
            ):
                index = i
                break

        if index is not None and index + 1 < len(data["transcripts"]):
            next_text = data["transcripts"][index + 1].get("text", "No response found.")
            feedback_answers.append(next_text)
        else:
            feedback_answers.append("No response found.")

    feedback_detail, created = FeedbackDetails.objects.update_or_create(
        call_id=call_id,
        defaults={
            "feedback_questions": feedback_questions,
            "feedback_answers": feedback_answers,
        },
    )
    return feedback_detail


def get_variables(call_id):
    """Get extracted variables from a call."""
    try:
        call_details = get_call_details(call_id)
        variables = call_details.get("variables")
        if not variables:
            return None
        user_input_variables = {}
        for key, value in variables.items():
            if key.endswith("user_input"):
                user_input_variables[key] = value
        return user_input_variables
    except Exception as e:
        print(f"Error extracting user input variables: {e}")
        return {"error": str(e)}


# =============================================================================
# Utility — check if pathway has nodes
# =============================================================================

def check_pathway_block(pathway_id):
    """Check if the pathway contains any nodes."""
    pathway_data, status_code = handle_view_single_flow(pathway_id)
    if status_code == 200:
        nodes = pathway_data.get("nodes", [])
        return bool(nodes)
    return False


# =============================================================================
# Django Views (kept for URL routing)
# =============================================================================

@csrf_exempt
def create_flow(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        pathway_name = data.get("name")
        pathway_description = data.get("description")
        response_data, status, _ = handle_create_flow(pathway_name, pathway_description, 0)
        return JsonResponse(response_data, status=status)
    return JsonResponse({"error": "Invalid method"}, status=405)


@csrf_exempt
def view_flows(request):
    if request.method == "GET":
        response_data, status = handle_view_flows()
        if isinstance(response_data, list):
            return JsonResponse({"flows": response_data}, status=status)
        return JsonResponse(response_data, status=status)
    return JsonResponse({"error": "Invalid method"}, status=405)
