# Bland.ai → Retell AI Migration Analysis

## Executive Summary

This document provides a comprehensive analysis of migrating the Speechcad Telegram IVR Bot from **Bland.ai** to **Retell AI**. The migration covers all API endpoints, data models, webhook handling, and concept mapping between the two platforms.

---

## 1. Concept Mapping: Bland.ai vs Retell AI

| Bland.ai Concept | Retell AI Equivalent | Notes |
|---|---|---|
| **Pathway** (convo_pathway) | **Agent** (with Response Engine / Conversation Flow) | Bland pathways = Retell agents with built-in conversation flow nodes |
| **Pathway Nodes** (Default, End Call, Transfer Call) | **Conversation Flow Nodes** (General, End Call, Transfer Call, Press Digits) | Retell uses a visual conversation flow editor; nodes are configured in agent settings |
| **Pathway Edges** | **Conversation Flow Edges** | Same concept - connections between nodes |
| `pathway_id` | `agent_id` | Primary entity identifier changes |
| `call_id` | `call_id` | Same concept, different format (Retell uses alphanumeric string) |
| `batch_id` | Batch call API | Retell supports batch calling via API |
| `queue_status` (new/queued/started/complete) | `call_status` (registered/ongoing/ended/error) | Status values differ |
| `started_at` / `end_at` (ISO datetime) | `start_timestamp` / `end_timestamp` (epoch ms) | Timestamp format differs |
| `call_length` (minutes) | `duration_ms` (milliseconds) | Duration unit differs |
| `transcripts` (list of {user, text}) | `transcript_object` (list of {role, content, words}) | Transcript structure differs |
| Voice selection (by voice object) | `voice_id` (e.g., "11labs-Adrian") | Voice selection approach differs |
| `from` (caller ID) | `from_number` | Parameter name change |
| `phone_number` (destination) | `to_number` | Parameter name change |
| API Key via `Authorization` header | API Key via `Authorization: Bearer <key>` | Auth header format changes |
| Base URL: `https://api.bland.ai` | Base URL: `https://api.retellai.com` | Base URL changes |
| Webhook signing secret | Retell webhook signature (`X-Retell-Signature`) | Webhook verification method changes |
| `extractVars` (variable extraction) | `collected_dynamic_variables` / `retell_llm_dynamic_variables` | Variable extraction approach changes |
| DTMF via pathway nodes | `enable_user_dtmf` + `user_dtmf_options` on agent | DTMF configured at agent level |

---

## 2. API Endpoint Mapping

### 2.1 Pathway/Agent Management

| # | Bland.ai Endpoint | Retell AI Equivalent | Method |
|---|---|---|---|
| 1 | `POST /v1/convo_pathway/create` | `POST /v2/create-agent` | Create flow/agent |
| 2 | `POST /v1/convo_pathway/{id}` | `PATCH /v2/update-agent/{agent_id}` | Update pathway/agent nodes |
| 3 | `GET /v1/convo_pathway` | `GET /v2/list-agents` | List all flows |
| 4 | `GET /v1/convo_pathway/{id}` | `GET /v2/get-agent/{agent_id}` | Get single flow |
| 5 | `DELETE /v1/convo_pathway/{id}` | `DELETE /v2/delete-agent/{agent_id}` | Delete flow |

### 2.2 Call Management

| # | Bland.ai Endpoint | Retell AI Equivalent | Method |
|---|---|---|---|
| 6 | `POST /v1/calls` | `POST /v2/create-phone-call` | Single outbound call |
| 7 | `GET /v1/calls/{call_id}` | `GET /v2/get-call/{call_id}` | Get call details |
| 8 | `POST /v1/calls/{call_id}/stop` | `DELETE /v2/delete-call/{call_id}` (or end via agent logic) | Stop single call |
| 9 | `POST /v1/calls/active/stop` | No direct equivalent (iterate + stop individually) | Stop all active calls |
| 10 | `POST /v1/batches` | `POST /v2/create-batch-call` | Batch/bulk calls |
| 11 | `GET /v1/batches/{batch_id}` | `GET /v2/list-calls` (filter by batch) | Get batch details |
| 12 | `POST /v1/batches/{batch_id}/stop` | Stop individual calls in batch | Stop batch calls |

### 2.3 Voices

| # | Bland.ai Endpoint | Retell AI Equivalent | Method |
|---|---|---|---|
| 13 | `GET /v1/voices` | `GET /v2/list-voices` (SDK: `client.voice.list()`) | List available voices |

---

## 3. Files Requiring Changes

### 3.1 Core API Integration Files

| File | Bland.ai Functions | Change Scope |
|---|---|---|
| **`bot/views.py`** | `handle_create_flow`, `handle_delete_flow`, `handle_add_node`, `handle_view_flows`, `handle_view_single_flow`, `send_call_through_pathway`, `bulk_ivr_flow`, `get_call_details`, `get_call_status`, `get_voices`, `stop_single_active_call`, `stop_all_active_calls`, `stop_active_batch_calls`, `batch_details`, `send_task_through_call`, `play_message`, `question_type`, `handle_menu_node`, `handle_end_call`, `handle_dtmf_input_node`, `handle_transfer_call_node` | **MAJOR** - All API calls need rewriting |
| **`bot/tasks.py`** | `check_call_status`, `call_status_free_plan` (both call Bland API directly) | **MAJOR** - Response field mapping changes |
| **`bot/webhooks.py`** | `call_details_webhook` | **MODERATE** - Webhook payload structure changes |
| **`bot/utils.py`** | `extract_call_details`, `categorize_voices_by_description` | **MODERATE** - Response structure changes |

### 3.2 Configuration Files

| File | Change | Scope |
|---|---|---|
| **`TelegramBot/settings.py`** | Replace `BLAND_API_KEY`, `BLAND_WEBHOOK_SIGNING_SECRET` → `RETELL_API_KEY` | **MINOR** |
| **`.env`** | Replace env vars | **MINOR** |
| **`TelegramBot/English.py`** | Change `base_url` from `https://api.bland.ai` → `https://api.retellai.com` | **MINOR** |
| **`translations/translations.py`** | Change `base_url` dict values | **MINOR** |
| **`translations/Chinese.py`** | Change `base_url` | **MINOR** |
| **`translations/French.py`** | Change `base_url` | **MINOR** |
| **`translations/Hindi.py`** | Change `base_url` | **MINOR** |

### 3.3 Database Model Changes

| File | Change | Scope |
|---|---|---|
| **`bot/models.py`** | `Pathways.pathway_id` → conceptually becomes `agent_id`; consider adding `retell_agent_id` field | **MODERATE** |
| **`requirements.txt`** | Add `retell-sdk` | **MINOR** |

---

## 4. Detailed Function Migration Guide

### 4.1 `handle_create_flow()` → Create Retell Agent

**Before (Bland.ai):**
```python
endpoint = f"{base_url}/v1/convo_pathway/create"
headers = {"Authorization": f"{settings.BLAND_API_KEY}"}
payload = {"name": pathway_name, "description": pathway_description}
response = requests.post(endpoint, json=payload, headers=headers)
pathway_id = response.json().get("pathway_id")
```

**After (Retell AI):**
```python
from retell import Retell
client = Retell(api_key=settings.RETELL_API_KEY)

agent = client.agent.create(
    agent_name=pathway_name,
    voice_id="11labs-Adrian",  # Default voice, configurable
    response_engine={
        "type": "retell-llm",
        "llm_id": "your_llm_id"  # Pre-created Response Engine
    },
    # Conversation flow nodes can be set here or updated later
)
agent_id = agent.agent_id
```

**Key Difference:** Retell agents need a `voice_id` and `response_engine` at creation. The pathway description becomes the agent prompt/instructions. Conversation flow nodes are part of agent configuration, not separate entities.

### 4.2 `handle_add_node()` → Update Agent Conversation Flow

**Before (Bland.ai):**
```python
endpoint = f"{base_url}/v1/convo_pathway/{pathway_id}"
payload = {"name": name, "description": desc, "nodes": nodes, "edges": edges}
response = requests.post(endpoint, json=payload, headers=headers)
```

**After (Retell AI):**
Retell uses conversation flow configured within the agent. Nodes/edges map to Retell's conversation flow format:
```python
# Retell conversation flow is configured via agent update
# The exact node format differs - Retell uses its own node schema
client.agent.update(
    agent_id=agent_id,
    # Conversation flow is part of agent config
    # Nodes map to: General Node, End Call Node, Transfer Call Node, Press Digits Node
)
```

**Important:** This is the most complex mapping. Bland.ai pathways with nodes/edges need to be translated into Retell's conversation flow format. Consider using Retell's **single-prompt** or **multi-prompt** agent mode as an alternative to the node-based flow.

### 4.3 `send_call_through_pathway()` → Create Phone Call

**Before (Bland.ai):**
```python
endpoint = "https://api.bland.ai/v1/calls"
payload = {
    "phone_number": phone_number,
    "pathway_id": pathway_id,
    "webhook": "https://your-webhook.com/call_details",
}
if caller_id:
    payload["from"] = caller_id
response = requests.post(endpoint, json=payload, headers=headers)
call_id = response.json().get("call_id")
```

**After (Retell AI):**
```python
call_response = client.call.create_phone_call(
    from_number=caller_id,       # Was "from"
    to_number=phone_number,      # Was "phone_number"
    override_agent_id=agent_id,  # Was "pathway_id"
)
call_id = call_response.call_id
```

**Key Differences:**
- `phone_number` → `to_number`
- `from` → `from_number`
- `pathway_id` → `override_agent_id`
- Webhook configured at agent level, not per-call
- Response status code is `201` (not `200`)

### 4.4 `get_call_details()` → Get Call

**Before (Bland.ai):**
```python
endpoint = f"{base_url}/v1/calls/{call_id}"
response = requests.get(endpoint, headers=headers)
data = response.json()
queue_status = data.get("queue_status")
started_at = data.get("started_at")  # ISO datetime
end_at = data.get("end_at")          # ISO datetime
call_length = data.get("call_length") # minutes
transcripts = data.get("transcripts") # [{user: "assistant", text: "..."}]
```

**After (Retell AI):**
```python
call = client.call.retrieve(call_id)
call_status = call.call_status          # "registered"/"ongoing"/"ended"/"error"
start_timestamp = call.start_timestamp  # epoch milliseconds
end_timestamp = call.end_timestamp      # epoch milliseconds
duration_ms = call.duration_ms          # milliseconds
transcript_object = call.transcript_object  # [{role: "agent", content: "..."}]
```

**Critical Field Mappings:**
| Bland.ai Field | Retell AI Field | Transformation |
|---|---|---|
| `queue_status` = "complete" | `call_status` = "ended" | Value mapping required |
| `queue_status` = "started" | `call_status` = "ongoing" | Value mapping required |
| `queue_status` = "queued"/"new" | `call_status` = "registered" | Value mapping required |
| `started_at` (ISO string) | `start_timestamp` (epoch ms) | `datetime.fromtimestamp(ts/1000)` |
| `end_at` (ISO string) | `end_timestamp` (epoch ms) | `datetime.fromtimestamp(ts/1000)` |
| `call_length` (minutes float) | `duration_ms` (integer ms) | `duration_ms / 60000` |
| `transcripts[].user` | `transcript_object[].role` | "assistant"→"agent", "user"→"user" |
| `transcripts[].text` | `transcript_object[].content` | Direct mapping |
| `variables` | `collected_dynamic_variables` | Key name change |

### 4.5 `bulk_ivr_flow()` → Batch Calls

**Before (Bland.ai):**
```python
url = f"{base_url}/v1/batches"
payload = {
    "call_data": call_data,  # List of {phone_number: ...}
    "test_mode": False,
    "campaign_id": str(campaign_id),
    "pathway_id": str(pathway_id),
}
```

**After (Retell AI):**
```python
# Retell batch call API
batch_response = client.batch_call.create_batch_call(
    from_number=caller_id,
    tasks=[
        {
            "to_number": call["phone_number"],
            "override_agent_id": agent_id,
            "retell_llm_dynamic_variables": call.get("variables", {}),
        }
        for call in call_data
    ],
)
batch_id = batch_response.batch_call_id
```

### 4.6 `get_voices()` → List Voices

**Before (Bland.ai):**
```python
url = f"{base_url}/v1/voices"
response = requests.get(url, headers=headers)
# Returns list of voice objects with description field
```

**After (Retell AI):**
```python
voices = client.voice.list()
# Returns list of voice objects with voice_id, name, provider
```

### 4.7 `stop_single_active_call()` → End Call

**Before (Bland.ai):**
```python
url = f"https://api.bland.ai/v1/calls/{call_id}/stop"
response = requests.post(url, headers=headers)
```

**After (Retell AI):**
```python
# Retell doesn't have a direct "stop call" endpoint
# Use delete call or end via agent logic
# Check latest API for /v2/end-call/{call_id} or similar
response = client.call.delete(call_id)
```

### 4.8 Webhook Changes

**Before (Bland.ai):**
```python
# Webhook payload fields
data.get("to")          # phone number
data.get("call_id")
data.get("pathway_id")
data.get("end_at")
# Verification via HMAC with BLAND_WEBHOOK_SIGNING_SECRET
```

**After (Retell AI):**
```python
# Webhook events: call_started, call_ended, call_analyzed
# Payload includes full call object
# Verification via X-Retell-Signature header
import hmac, hashlib
def verify_retell_webhook(request):
    signature = request.headers.get("X-Retell-Signature")
    body = request.body
    expected = hmac.new(
        settings.RETELL_API_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

---

## 5. Environment Variable Changes

| Old (.env) | New (.env) |
|---|---|
| `BLAND_API_KEY=xxx` | `RETELL_API_KEY=key_01bfb1647fdf445baeb3159446b1` |
| `BLAND_WEBHOOK_SIGNING_SECRET=xxx` | *(Retell uses API key for webhook verification)* |

---

## 6. Dependency Changes

```diff
# requirements.txt
- # No Bland SDK (used raw requests)
+ retell-sdk>=4.0.0
```

---

## 7. Database Migration Considerations

The `Pathways` model stores `pathway_id` which maps to Bland.ai pathway IDs. Options:

**Option A (Recommended):** Add new field `retell_agent_id` to `Pathways` model, keep `pathway_id` for backward compatibility during migration.

**Option B:** Rename `pathway_id` → `agent_id` (breaking change, requires data migration for all related tables: `CallLogsTable`, `BatchCallLogs`, `CallDuration`, etc.)

---

## 8. Key Architectural Differences

### 8.1 Pathway Nodes vs Agent Configuration
- **Bland.ai**: Pathways with explicit nodes/edges via API, highly dynamic
- **Retell AI**: Agents with conversation flow configured at agent level. Two modes:
  - **Single/Multi-Prompt Agent**: Define behavior via LLM prompt (simpler)
  - **Conversation Flow Agent**: Visual node-based flow (closer to Bland pathways)

**Recommendation:** Use Retell's **Conversation Flow** mode to maintain feature parity with Bland.ai pathways. Each node type maps:
- Bland `Default` node → Retell `General` node
- Bland `End Call` node → Retell `End Call` node
- Bland `Transfer Call` node → Retell `Transfer Call` node
- Bland DTMF node → Retell `Press Digits` node

### 8.2 Batch Calling
- **Bland.ai**: `POST /v1/batches` with `call_data` array, returns `batch_id`
- **Retell AI**: Batch calling via API with `from_number` and `tasks` array

### 8.3 Call Status Monitoring
- **Bland.ai**: Poll `GET /v1/calls/{id}` for `queue_status`
- **Retell AI**: Poll `GET /v2/get-call/{id}` for `call_status` OR use webhooks (`call_started`, `call_ended`, `call_analyzed`)

**Recommendation:** Migrate from polling to Retell webhooks for real-time updates, reducing API calls and improving responsiveness.

---

## 9. Migration Steps (Recommended Order)

1. **Install retell-sdk** and add to requirements.txt
2. **Update .env** with `RETELL_API_KEY`
3. **Update settings.py** with new env vars
4. **Update base_url** in all translation files
5. **Create a Retell service layer** (`bot/retell_service.py`) that wraps Retell SDK calls
6. **Migrate `bot/views.py`** functions one by one using the service layer
7. **Migrate `bot/tasks.py`** call status polling with new field mappings
8. **Update `bot/webhooks.py`** for Retell webhook format
9. **Update `bot/utils.py`** for new response structures
10. **Add DB migration** for `retell_agent_id` field if needed
11. **Test each function** independently
12. **Run full integration tests**

---

## 10. Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Pathway/Node structure mismatch | **HIGH** | Use Retell Conversation Flow mode; may need manual flow recreation |
| Call status field mapping errors | **MEDIUM** | Create utility function for status mapping; thorough testing |
| Timestamp format differences | **MEDIUM** | Centralized conversion functions |
| Batch calling API differences | **MEDIUM** | Test with small batches first |
| Webhook payload structure changes | **LOW** | Update webhook handler + add logging |
| Voice selection changes | **LOW** | Map current voices to Retell voice IDs |

---

## 11. Retell AI Key Provided

```
RETELL_API_KEY=key_01bfb1647fdf445baeb3159446b1
```

This key should be added to `.env` and used across all Retell API calls.
