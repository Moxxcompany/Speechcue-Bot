# Speechcad Telegram Bot — Complete User Flow & Retell AI Feature Mapping

---

## Table of Contents
1. [Onboarding Flow](#1-onboarding-flow)
2. [Main Menu & Navigation](#2-main-menu--navigation)
3. [IVR Flow Builder (Advanced)](#3-ivr-flow-builder-advanced)
4. [IVR Flow Builder (AI-Assisted)](#4-ivr-flow-builder-ai-assisted)
5. [Single IVR Call](#5-single-ivr-call)
6. [Bulk IVR Calls](#6-bulk-ivr-calls)
7. [Campaign Management](#7-campaign-management)
8. [Call Status Monitoring](#8-call-status-monitoring)
9. [DTMF Inbox](#9-dtmf-inbox)
10. [User Feedback / Transcripts](#10-user-feedback--transcripts)
11. [Billing & Subscription](#11-billing--subscription)
12. [Wallet & Crypto Payments](#12-wallet--crypto-payments)
13. [Account & Settings](#13-account--settings)
14. [Background Tasks (Celery/Huey)](#14-background-tasks-celeryhuey)

---

## 1. Onboarding Flow

### User Journey
```
/start → Language Selection (EN/HI/CN/FR)
  → Enter Name → Enter Email → Enter Mobile Number
    → DynoPay Wallet Setup → Terms & Conditions
      → Choose Subscription Plan (Free/Prime/Elite/Ultra)
        → Main Menu
```

### Bland.ai Usage: **NONE**
### Retell AI Impact: **NONE** — This flow is purely Telegram + DynoPay. No migration needed.

---

## 2. Main Menu & Navigation

### Menu Structure
```
Main Menu:
├── Top Up 💰           → Crypto payment to wallet
├── Billing & Sub 📅    → View/upgrade subscription, check wallet
├── IVR Call 📲         → Single IVR / Bulk IVR / Call Status
├── IVR Flow 📞         → AI-Assisted / Advanced flow builder
├── Campaign Mgmt 📊    → Scheduled / Active campaigns
├── DTMF Inbox 📥       → View DTMF responses from calls
├── Account 👤          → Profile / Settings / Feedback
```

### Bland.ai Usage: **NONE** (menu system is purely Telegram keyboard-based)
### Retell AI Impact: **NONE**

---

## 3. IVR Flow Builder (Advanced)

### User Journey
```
IVR Flow → Advanced User Flow → Create/View/Delete Flow

CREATE FLOW:
  → Enter Flow Name → Enter Flow Description
    → Bland.ai creates pathway → Get pathway_id
      → Add First Node (Greeting - Play Message)
        → Select Voice Gender → Select Voice → Enter Text
          → Node created via Bland.ai API
            → Continue Adding Nodes OR Done
              → Add Edges (connect nodes)
                → Validate Edges → Flow Complete

NODE TYPES AVAILABLE:
  ├── Play Message ▶️     → TTS node that speaks text to caller
  ├── End Call 🛑         → Terminates the call
  ├── Call Transfer 🔄    → Transfers call to a live number (paid plans only)
  ├── Get DTMF Input 📞  → Captures keypad input from caller
  ├── Menu 📋            → Multi-option menu node
  ├── Feedback Node       → Asks feedback questions
  └── Question            → Asks question & extracts answer to variable
```

### Bland.ai API Calls in this Flow:

| Step | Bland.ai Function | What It Does |
|------|-------------------|-------------|
| Create flow | `handle_create_flow()` | `POST /v1/convo_pathway/create` — creates empty pathway |
| Add Play Message node | `play_message()` | Adds Default/End Call node with text, voice |
| Add Question node | `question_type()` | Adds Default node with `extractVars` for answer capture |
| Add Menu node | `handle_menu_node()` | Adds Default node with prompt |
| Add DTMF node | `handle_dtmf_input_node()` | Adds Default node for DTMF capture |
| Add End Call node | `handle_end_call()` | Adds End Call type node |
| Add Transfer Call node | `handle_transfer_call_node()` | Adds Transfer Call node with phone number |
| Update pathway (any node) | `handle_add_node()` | `POST /v1/convo_pathway/{id}` — sends full nodes+edges payload |
| View single flow | `handle_view_single_flow()` | `GET /v1/convo_pathway/{id}` — retrieve pathway data |
| View all flows | `handle_view_flows()` | `GET /v1/convo_pathway` — list all pathways |
| Delete flow | `handle_delete_flow()` | `DELETE /v1/convo_pathway/{id}` |
| Delete node | (inline handler) | Removes node from payload, re-sends to API |
| Empty nodes | `empty_nodes()` | Resets pathway to no nodes |
| Get voices | `get_voices()` | `GET /v1/voices` — list available TTS voices |

### Retell AI Equivalent:

| Step | Retell AI Approach | How It Works |
|------|-------------------|-------------|
| Create flow | `client.agent.create()` | Creates a Retell Agent. Requires `voice_id` + `response_engine`. The agent IS the flow. |
| Add nodes | `client.agent.update()` | Retell uses **Conversation Flow** mode. Nodes are configured within agent settings as flow nodes. |
| Node: Play Message | **General Node** | Set node `text` field. Voice is set at agent level (`voice_id`). |
| Node: Question | **General Node** with dynamic variables | Use `retell_llm_dynamic_variables` or function calling to extract answers. |
| Node: Menu | **General Node** with condition edges | Define menu options as edge conditions from the node. |
| Node: DTMF Input | **Press Digits Node** | Retell has native DTMF support: `enable_user_dtmf: true`, `user_dtmf_options: {digit_limit, termination_key, timeout_ms}` |
| Node: End Call | **End Call Node** | Direct equivalent in Retell conversation flow. |
| Node: Transfer Call | **Transfer Call Node** | Direct equivalent. Supports warm transfer to phone number or another Retell agent. |
| View flow | `client.agent.retrieve(agent_id)` | Returns full agent config including conversation flow. |
| List flows | `client.agent.list()` | Returns all agents. |
| Delete flow | `client.agent.delete(agent_id)` | Deletes agent. |
| Get voices | `client.voice.list()` | Returns available voices (ElevenLabs, PlayHT, etc.) |

### Retell Supports This? **YES — Full parity available.**
- Retell's Conversation Flow mode maps 1:1 to Bland.ai pathways
- All node types have direct equivalents
- DTMF support is **native and enhanced** in Retell (configurable digit limits, timeouts)
- Voice selection is similar but uses `voice_id` strings instead of voice objects
- **Bonus**: Retell adds post-call analysis, recording URLs, and knowledge base support

---

## 4. IVR Flow Builder (AI-Assisted)

### User Journey
```
IVR Flow → AI-Assisted Flow → Create/View/Delete Task

CREATE AI TASK:
  → Enter Task Name → Enter Task Description (natural language prompt)
    → Saved as AI_Assisted_Tasks in DB
    → Used as `base_prompt` in Bland.ai calls (no pathway needed)
```

### Bland.ai API Calls:
- **NONE at creation** — The task description is stored locally and sent as `task`/`base_prompt` parameter when making calls
- Used in `send_task_through_call()` → `POST /v1/calls` with `task` field instead of `pathway_id`
- Used in `bulk_ivr_flow()` → `POST /v1/batches` with `base_prompt` field

### Retell AI Equivalent:
| Feature | Retell Approach |
|---------|----------------|
| Task as prompt | Create a **Single-Prompt Agent** with the task description as the agent's `prompt`/instructions |
| Per-call task | Use `agent_override` parameter in `create_phone_call` to override agent prompt per call |
| Dynamic variables | Use `retell_llm_dynamic_variables` to inject context |

### Retell Supports This? **YES — Even better.**
- Retell's single-prompt agent mode is purpose-built for this use case
- Agent prompt = Bland.ai's `task`/`base_prompt`
- Per-call overrides allow dynamic prompts without creating new agents
- **Bonus**: Retell's Response Engine supports GPT-4o, custom LLMs, function calling

---

## 5. Single IVR Call

### User Journey
```
IVR Call → Single IVR
  → Check subscription is active
    → Choose task source:
      ├── AI-Made Tasks (select existing task)
      ├── Custom-Made Tasks (select existing pathway)
      └── Create Task (new task/flow)
    → Enter phone number to call
    → Select Caller ID (if available)
    → Confirm call details
      → YES: Initiate call
        → Bland.ai API sends call → Get call_id
          → Save to CallLogsTable
```

### Bland.ai API Calls:

| Function | API | Purpose |
|----------|-----|---------|
| `send_call_through_pathway()` | `POST /v1/calls` with `pathway_id` | Call using a built pathway flow |
| `send_task_through_call()` | `POST /v1/calls` with `task` | Call using AI task prompt |

### Key Parameters Sent to Bland.ai:
```python
{
    "phone_number": "+1234567890",   # Destination
    "pathway_id": "xxx",             # OR "task": "prompt text"
    "from": "+1987654321",           # Optional caller ID
    "webhook": "https://xxx/call_details",
    "max_duration": "5"              # For free plan users
}
```

### Retell AI Equivalent:
```python
call = client.call.create_phone_call(
    from_number="+1987654321",           # Was "from"
    to_number="+1234567890",             # Was "phone_number"
    override_agent_id="agent_xxx",       # Was "pathway_id"
    # OR for AI task: use agent with task as prompt
    metadata={"user_id": "123"},         # Custom tracking
)
```

### Retell Supports This? **YES — Direct equivalent.**
- `create_phone_call` endpoint maps directly
- Pathway calls → Use `override_agent_id` to specify which agent/flow
- Task calls → Create or use a single-prompt agent
- Caller ID → `from_number` (must be a number registered in Retell)
- Webhook → Configured at agent or number level (not per-call)
- **Note**: `max_duration` for free plan → Retell supports `max_call_duration_ms` at agent level

---

## 6. Bulk IVR Calls

### User Journey
```
IVR Call → Bulk IVR
  → Check subscription (needs bulk minutes)
    → Choose task source (same as single)
    → Enter Campaign Name
    → Enter phone numbers (one by one or batch)
    → Select Caller ID
    → Choose: Start Now OR Schedule for Later
      ├── Start Now → bulk_ivr_flow() → Bland.ai Batch API
      └── Schedule → Enter city/timezone → Enter date/time → Set reminder
```

### Bland.ai API Calls:

| Function | API | Purpose |
|----------|-----|---------|
| `bulk_ivr_flow()` | `POST /v1/batches` | Send batch of calls |
| (inside bulk_ivr_flow) | `GET /v1/batches/{batch_id}` | Get batch details after creation |
| `get_call_list_from_batch()` | `GET /v1/batches/{batch_id}` | Extract individual call_ids from batch |

### Key Parameters:
```python
{
    "call_data": [{"phone_number": "+1..."}, {"phone_number": "+2..."}],
    "pathway_id": "xxx",        # OR "base_prompt": "task text"
    "from": "+1987654321",      # Caller ID
    "campaign_id": "campaign_uuid",
    "test_mode": False
}
```

### Retell AI Equivalent:
```python
batch = client.batch_call.create_batch_call(
    from_number="+1987654321",
    tasks=[
        {"to_number": num, "override_agent_id": agent_id}
        for num in phone_numbers
    ]
)
```

### Retell Supports This? **YES — With batch call API.**
- Retell has a batch calling API for multiple simultaneous calls
- Each call in the batch can have different agent overrides and dynamic variables
- Campaign tracking → Use `metadata` field per call
- **Bonus**: Retell provides per-call cost breakdown, recording URLs, and transcripts
- **Difference**: Bland.ai returns a single `batch_id` to track all calls. Retell may return individual `call_id`s. Need to build a local campaign→calls mapping.

---

## 7. Campaign Management

### User Journey
```
Campaign Management:
├── Scheduled Campaigns
│   → View list of pending scheduled campaigns
│   → Select campaign → View details (name, task, time, recipients)
│   → Options: Cancel Campaign / Start Now / Go Back
│     ├── Cancel → Revoke Huey task → Mark canceled
│     └── Start Now → Execute bulk_ivr_flow immediately
│
└── Active Campaigns
    → View list of running campaigns (call_status=True)
    → View details (name, task, start time, total calls)
    → "Active campaigns cannot be modified"
```

### Bland.ai API Calls:
- `bulk_ivr_flow()` when starting a scheduled campaign
- `stop_active_batch_calls()` → `POST /v1/batches/{batch_id}/stop` (implicit, if needed)

### Retell AI Equivalent:
- Starting campaign → Same as bulk call flow above
- Stopping campaign → Stop individual calls via `client.call.delete(call_id)` for each active call
- Campaign tracking is handled in local DB (CampaignLogs, ScheduledCalls) — no change needed

### Retell Supports This? **YES**
- Campaign scheduling is done via Huey/Celery (local) — no Bland/Retell dependency
- The actual call execution uses bulk call API (covered above)
- Stopping: Need to iterate active calls since Retell doesn't have "stop batch" endpoint

---

## 8. Call Status Monitoring

### User Journey
```
IVR Call → Call Status
  → View list of user's calls (from CallLogsTable)
  → Select a call → Show status
    → Calls Bland.ai GET /v1/calls/{call_id}
    → Shows: queue_status, duration, etc.
```

### Bland.ai API Calls:

| Function | API | Purpose |
|----------|-----|---------|
| `get_call_details()` | `GET /v1/calls/{call_id}` | Full call details |
| `get_call_status()` | Calls `get_call_details()` → extracts `queue_status` | Quick status check |

### Bland.ai Response Fields Used:
```python
queue_status  # "new", "queued", "started", "complete"
started_at    # ISO datetime string
end_at        # ISO datetime string
call_length   # Float, minutes
transcripts   # [{user: "assistant"/"user", text: "..."}]
variables     # Extracted variables from pathway
```

### Retell AI Equivalent:
```python
call = client.call.retrieve(call_id)
# Field mapping:
call.call_status       # "registered", "ongoing", "ended", "error"
call.start_timestamp   # Epoch milliseconds
call.end_timestamp     # Epoch milliseconds
call.duration_ms       # Integer milliseconds
call.transcript_object # [{role: "agent"/"user", content: "..."}]
call.collected_dynamic_variables  # Extracted variables
call.call_analysis     # Sentiment, summary, success (BONUS!)
call.recording_url     # Call recording (BONUS!)
```

### Retell Supports This? **YES — With enhanced data.**
- All status fields have equivalents (need value mapping utility)
- Transcripts are richer (include word-level timestamps)
- **Bonuses over Bland.ai**:
  - `call_analysis`: AI-generated summary, sentiment, success evaluation
  - `recording_url`: Full call recording
  - `disconnection_reason`: Detailed reason why call ended
  - `call_cost`: Per-call cost breakdown

---

## 9. DTMF Inbox

### User Journey
```
DTMF Inbox → Select Phone Number → Select Pathway → Select Call ID
  → View DTMF input received during that call
  → Shows: Phone Number, DTMF Input digits, Timestamp
```

### Bland.ai Connection:
- DTMF data flows via **webhook** (`call_details_webhook` in webhooks.py)
- When a call ends, Bland.ai sends call data to webhook URL
- `extract_call_details()` parses: `to`, `call_id`, `pathway_id`, `end_at`, and DTMF digits from `concatenated_transcript`
- Also populated by `process_call_logs` Celery task that polls `get_call_details()` for each call

### Retell AI Equivalent:
- Retell supports DTMF natively via `enable_user_dtmf` and `user_dtmf_options`
- DTMF inputs are captured in `collected_dynamic_variables`
- Webhook events: `call_ended` event includes full call data with any DTMF inputs
- Can also use function calling to explicitly handle DTMF collection

### Retell Supports This? **YES — Natively supported.**
- Configure `enable_user_dtmf: true` on agent
- Set `user_dtmf_options: {digit_limit: 4, termination_key: "#", timeout_ms: 5000}`
- DTMF captured in call variables / webhook payload
- **Bonus**: Retell's DTMF is more configurable (digit limits, terminators, timeouts)

---

## 10. User Feedback / Transcripts

### User Journey
```
Account → User Feedback
  → Enter date range (start year→month→day, end year→month→day)
    → Show calls within date range
      → Select call → get_transcript()
        → Fetches Bland.ai call details
        → Matches feedback questions against transcript
        → Shows Q&A pairs
```

### Bland.ai API Calls:
```python
# get_transcript() calls get_call_details() which hits:
# GET /v1/calls/{call_id}
# Then parses transcripts[] array to find feedback answers
```

### Transcript Parsing Logic:
```python
# Current Bland.ai format:
for transcript in data["transcripts"]:
    if transcript["user"] == "assistant":
        # Match question text
    # Next entry = user's answer
```

### Retell AI Equivalent:
```python
# Retell format:
call = client.call.retrieve(call_id)
for utterance in call.transcript_object:
    if utterance.role == "agent":
        # Match question
    elif utterance.role == "user":
        # User's answer
    # Also has: utterance.words[].start, .end (timestamps per word)
```

### Retell Supports This? **YES — With richer transcripts.**
- Transcript structure is slightly different (`role` vs `user`, `content` vs `text`) but functionally identical
- **Bonuses**:
  - Word-level timestamps in transcripts
  - `call_analysis.call_summary` — AI-generated summary
  - `call_analysis.user_sentiment` — Positive/Negative/Neutral
  - `recording_url` — Listen to actual audio

---

## 11. Billing & Subscription

### User Journey
```
Billing & Subscription:
├── View Subscription → Shows current plan details
├── Upgrade Subscription → Plan selection → Duration → Auto-renewal → Payment
└── Check Wallet → Shows balance → Top Up option
```

### Plans:
| Plan | Price | Bulk Minutes | Single IVR | Call Transfer | Validity |
|------|-------|-------------|------------|---------------|----------|
| Free | $0 | 0 | Limited | No | 2 days |
| Prime | $10-$30 | 100-500 | Unlimited | No | 1-30 days |
| Elite | $15-$35 | 150-600 | Unlimited | Yes | 1-30 days |
| Ultra | $20-$40 | 200-800 | Unlimited | Yes | 1-30 days |

### Bland.ai Usage: **NONE** — Billing is entirely DynoPay + local DB
### Retell AI Impact: **NONE** — Subscription system is independent of voice API

---

## 12. Wallet & Crypto Payments

### User Journey
```
Top Up → Select Cryptocurrency:
  ├── Bitcoin (BTC)
  ├── Ethereum (ETH)
  ├── TRC-20 USDT
  ├── ERC-20 USDT
  ├── Litecoin (LTC)
  ├── Dogecoin
  ├── Bitcoin Cash
  └── TRON
→ Enter amount → DynoPay generates payment address
→ Send crypto → Payment confirmed → Wallet credited
```

### Bland.ai Usage: **NONE**
### Retell AI Impact: **NONE**

---

## 13. Account & Settings

### Features
```
Account:
├── Profile 👤        → Username, plan, balance
├── Settings ⚙       → Change Language (EN/HI/CN/FR)
├── User Feedback     → View call transcripts by date
└── View Variables    → See extracted variables from calls
```

### Bland.ai Usage:
- **View Variables** → `get_variables(call_id)` → calls `get_call_details()` → extracts `variables` dict
- **User Feedback** → `get_transcript()` → calls `get_call_details()` → parses transcripts

### Retell AI Equivalent:
- Variables → `call.collected_dynamic_variables`
- Transcripts → `call.transcript_object`

### Retell Supports This? **YES**

---

## 14. Background Tasks (Celery/Huey)

### Celery Tasks

| Task | Schedule | Bland.ai Usage | Purpose |
|------|----------|---------------|---------|
| `check_call_status` | Periodic | `GET /v1/calls/{id}` for each active batch call | Monitor bulk call durations, stop if exceeded |
| `call_status_free_plan` | Periodic | `GET /v1/calls/{id}` for free plan calls | Stop free plan calls if time limit reached |
| `charge_user_for_additional_minutes` | Periodic | NONE | Bill users for overage |
| `notify_users` | Periodic | NONE | Send billing notifications |
| `check_subscription_status` | Periodic | NONE | Handle expired subscriptions |
| `process_call_logs` | Periodic | `GET /v1/calls/{id}` for each call | Extract DTMF data from completed calls |

### Huey Tasks

| Task | Bland.ai Usage | Purpose |
|------|---------------|---------|
| `execute_bulk_ivr` | `bulk_ivr_flow()` → `POST /v1/batches` | Execute scheduled campaign |
| `send_reminder` | NONE | Send reminder before scheduled call |
| `cancel_scheduled_call` | NONE | Revoke scheduled task |

### Retell AI Migration for Tasks:

| Task | Current Approach | Retell Approach |
|------|-----------------|----------------|
| `check_call_status` | Poll Bland API per call | Poll Retell API per call OR **use `call_ended` webhook** (recommended) |
| `call_status_free_plan` | Poll Bland API per call | Same — poll or webhook. Use `max_call_duration_ms` on agent to auto-limit |
| `process_call_logs` | Poll for DTMF data | Use `call_ended` webhook to get all data at once |
| `execute_bulk_ivr` | Bland batch API | Retell batch call API |

### Retell Supports This? **YES — And can eliminate polling tasks.**
- **Key improvement**: Retell webhooks (`call_started`, `call_ended`, `call_analyzed`) can replace ALL polling tasks
- `max_call_duration_ms` on agent eliminates need for manual call termination for free plan
- `call_ended` webhook delivers transcript, DTMF, variables, cost, recording — ALL in one event

---

## Summary: Feature-by-Feature Retell AI Support

| # | Feature | Bland.ai Functions Used | Retell AI Support | Migration Complexity |
|---|---------|------------------------|-------------------|---------------------|
| 1 | **Create IVR Flow** | `handle_create_flow`, `handle_add_node` | `agent.create` + `agent.update` | **HIGH** — Node format translation needed |
| 2 | **Play Message Node** | `play_message()` | General Node with text | **LOW** — Direct mapping |
| 3 | **End Call Node** | `handle_end_call()` | End Call Node | **LOW** — Direct mapping |
| 4 | **Transfer Call Node** | `handle_transfer_call_node()` | Transfer Call Node | **LOW** — Direct mapping |
| 5 | **DTMF Input Node** | `handle_dtmf_input_node()` | Press Digits Node + `enable_user_dtmf` | **MEDIUM** — Different config approach |
| 6 | **Menu Node** | `handle_menu_node()` | General Node with edge conditions | **MEDIUM** — Edge mapping needed |
| 7 | **Question Node** | `question_type()` | General Node + dynamic variables | **MEDIUM** — Variable extraction differs |
| 8 | **View/Delete Flows** | `handle_view_flows`, `handle_delete_flow` | `agent.list()`, `agent.delete()` | **LOW** |
| 9 | **Voice Selection** | `get_voices()` | `voice.list()` | **LOW** — Different format |
| 10 | **Single IVR Call** | `send_call_through_pathway`, `send_task_through_call` | `call.create_phone_call` | **MEDIUM** — Param mapping |
| 11 | **Bulk IVR Calls** | `bulk_ivr_flow()` | `batch_call.create_batch_call` | **MEDIUM** — Response structure differs |
| 12 | **Call Status** | `get_call_details`, `get_call_status` | `call.retrieve()` | **MEDIUM** — Field mapping needed |
| 13 | **Stop Call** | `stop_single_active_call`, `stop_all_active_calls`, `stop_active_batch_calls` | `call.delete()` per call | **MEDIUM** — No batch stop |
| 14 | **Transcripts** | `get_transcript()` → parse transcripts array | `call.transcript_object` | **LOW** — Format change |
| 15 | **Variables** | `get_variables()` → extract from call details | `call.collected_dynamic_variables` | **LOW** |
| 16 | **DTMF Inbox** | Webhook + `process_call_logs` polling | Webhook `call_ended` event | **MEDIUM** — Webhook format change |
| 17 | **Call Duration Monitoring** | `check_call_status` Celery task | Webhook or `max_call_duration_ms` | **HIGH** — Architecture change (polling→webhook) |
| 18 | **Free Plan Call Limits** | `call_status_free_plan` + `stop_single_active_call` | `max_call_duration_ms` on agent | **LOW** — Retell handles natively |
| 19 | **Scheduled Campaigns** | Huey task → `bulk_ivr_flow()` | Same architecture, different API call | **LOW** |
| 20 | **AI-Assisted Tasks** | `task` param in calls | Single-prompt agent or `agent_override` | **LOW** |

---

## New Capabilities Gained from Retell AI

| Feature | Description | Business Value |
|---------|-------------|---------------|
| **Call Recordings** | `recording_url` for every call | Quality assurance, compliance, disputes |
| **Post-Call Analysis** | AI summary, sentiment, success evaluation | Automated QA without manual transcript review |
| **Word-Level Timestamps** | Per-word timing in transcripts | Precise analysis, audio-text alignment |
| **Disconnection Reasons** | 25+ specific reasons (user_hangup, voicemail_reached, etc.) | Better debugging, call quality metrics |
| **Per-Call Cost Tracking** | Detailed cost breakdown per call | Precise billing reconciliation |
| **Webhook-Based Events** | Real-time call_started, call_ended, call_analyzed | Eliminate polling tasks, instant updates |
| **Max Call Duration** | `max_call_duration_ms` at agent level | Automatic free plan limits without polling |
| **Knowledge Base** | RAG-based context for agents | Richer IVR flows with dynamic knowledge |
| **PII Redaction** | Automatic PII scrubbing in transcripts/recordings | HIPAA/compliance support |
| **Agent Versioning** | Version control for agents | Safe deployments, A/B testing |
