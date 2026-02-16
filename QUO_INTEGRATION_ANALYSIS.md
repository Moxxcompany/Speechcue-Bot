# Quo Voice Provider Integration Analysis

## Document Purpose
This document provides a comprehensive analysis of integrating Quo (formerly OpenPhone) as a voice provider to replace the existing Bland.ai integration in the Speechcad Telegram IVR Bot, and outlines a multi-tenant architecture design.

---

## 1. Current Architecture: Bland.ai Integration

### 1.1 Bland.ai Features Currently Used

The application currently uses Bland.ai as its sole voice provider. The integration is spread across `bot/views.py`, `bot/tasks.py`, and `bot/webhooks.py`.

| Feature | Bland.ai Endpoint | Files |
|---|---|---|
| **Create IVR Pathway** | `POST /v1/convo_pathway/create` | `views.py:handle_create_flow()` |
| **Update Pathway (Add Nodes)** | `POST /v1/convo_pathway/{id}` | `views.py:handle_add_node()` |
| **View All Pathways** | `GET /v1/convo_pathway` | `views.py:handle_view_flows()` |
| **View Single Pathway** | `GET /v1/convo_pathway/{id}` | `views.py:handle_view_single_flow()` |
| **Delete Pathway** | `DELETE /v1/convo_pathway/{id}` | `views.py:handle_delete_flow()` |
| **Single Outbound Call (via pathway)** | `POST /v1/calls` | `views.py:send_call_through_pathway()` |
| **Single Outbound Call (via task/prompt)** | `POST /v1/calls` | `views.py:send_task_through_call()` |
| **Bulk/Batch Calls** | `POST /v1/batches` | `views.py:bulk_ivr_flow()` |
| **Get Call Details** | `GET /v1/calls/{id}` | `views.py:get_call_details()` |
| **Stop Single Call** | `POST /v1/calls/{id}/stop` | `views.py:stop_single_active_call()` |
| **Stop All Active Calls** | `POST /v1/calls/active/stop` | `views.py:stop_all_active_calls()` |
| **Stop Batch Calls** | `POST /v1/batches/{id}/stop` | `views.py:stop_active_batch_calls()` |
| **Get Batch Details** | `GET /v1/batches/{id}` | `views.py:batch_details()` |
| **Get Voices** | `GET /v1/voices` | `views.py:get_voices()` |
| **Transcripts** | Embedded in call details response | `views.py:get_transcript()` |
| **Variable Extraction** | Embedded in call details response | `views.py:get_variables()` |
| **DTMF Detection** | Parsed from transcript text | `utils.py:extract_call_details()` |
| **Webhook (Call Details)** | Configured per-call | `webhooks.py:call_details_webhook()` |

### 1.2 Bland.ai Authentication
- Simple API key in `Authorization` header (no Bearer prefix)
- Single key (`BLAND_API_KEY`) stored in Django settings
- Base URL: `https://api.bland.ai`

### 1.3 Core Workflow
```
User -> Telegram Bot -> Creates IVR Pathway (nodes/edges) -> Initiates Call via Bland.ai
                                                          -> Bland.ai AI Agent executes pathway
                                                          -> Webhook returns call data
                                                          -> Call details/transcripts/DTMF stored in DB
```

---

## 2. Quo API Analysis

### 2.1 Quo API Overview
- **Base URL:** `https://api.openphone.com`
- **Auth:** API key in `Authorization` header (NOT Bearer token)
- **Rate Limit:** 10 requests per second
- **API Version:** v1

### 2.2 Verified Workspace Details
Using the provided API key `tul7jVf2oQHGPMp211neCYcWoKMxAOzt`:

| Property | Value |
|---|---|
| Phone Number | +18886033870 |
| Phone Number ID | PNHNMitFtw |
| Owner User ID | USSX7fbpdt |
| Owner Email | moxxcompany@gmail.com |
| Owner Name | Moxx Technologies |
| Group ID | GRM6A6DKFG |
| US Calling | Unrestricted |
| CA Calling | Unrestricted |
| Intl Calling | Restricted |
| US Messaging | Restricted (requires carrier registration) |

### 2.3 Available Quo API Endpoints

#### Calls (READ-ONLY)
| Endpoint | Method | Description |
|---|---|---|
| `/v1/calls` | GET | List calls (filter by phoneNumberId, participants, date range) |
| `/v1/calls/{callId}` | GET | Get a single call by ID |
| `/v1/call-recordings/{callId}` | GET | Get recordings for a call |
| `/v1/call-summaries/{callId}` | GET | Get AI-generated call summary (Business/Scale plans) |
| `/v1/call-transcripts/{id}` | GET | Get call transcript (Business/Scale plans) |

#### Messages
| Endpoint | Method | Description |
|---|---|---|
| `/v1/messages` | POST | Send a text message |
| `/v1/messages` | GET | List messages |
| `/v1/messages/{messageId}` | GET | Get a message by ID |

#### Phone Numbers
| Endpoint | Method | Description |
|---|---|---|
| `/v1/phone-numbers` | GET | List all phone numbers in workspace |
| `/v1/phone-numbers/{id}` | GET | Get a phone number by ID |

#### Contacts
| Endpoint | Method | Description |
|---|---|---|
| `/v1/contacts` | GET | List contacts |
| `/v1/contacts` | POST | Create a contact |

#### Webhooks
| Endpoint | Method | Description |
|---|---|---|
| `/v1/webhooks/calls` | POST | Create webhook for call events |
| `/v1/webhooks/messages` | POST | Create webhook for message events |
| `/v1/webhooks/call-summaries` | POST | Create webhook for call summary events |
| `/v1/webhooks/call-transcripts` | POST | Create webhook for transcript events |

#### Webhook Events
- `call.ringing` - Call starts ringing
- `call.completed` - Call is completed
- `call.recording.completed` - Call recording is ready
- `call.summary.completed` - AI summary is ready
- `call.transcript.completed` - Transcript is ready
- `message.received` - Incoming message
- `message.delivered` - Message delivered

---

## 3. GAP ANALYSIS: Bland.ai vs Quo

### 3.1 Critical Gaps (Features with NO Quo Equivalent)

| # | Bland.ai Feature | Quo Equivalent | Impact |
|---|---|---|---|
| 1 | **Programmatic Outbound Call Initiation** (`POST /v1/calls`) | **NONE** - Quo has no API to initiate outbound calls | **BLOCKER** - The core IVR functionality (making calls) cannot be replicated |
| 2 | **Conversational Pathways / IVR Flow Builder** | **NONE** - No pathway/node/edge concept | **BLOCKER** - The entire IVR flow creation feature has no equivalent |
| 3 | **AI Voice Agent** (follows pathways, TTS, voice selection) | **NONE** - Quo's Sona AI exists but is NOT programmable via API | **BLOCKER** - No way to have AI conduct conversations per pathway |
| 4 | **Bulk/Batch Call Execution** (`POST /v1/batches`) | **NONE** | **BLOCKER** - Campaign management cannot function |
| 5 | **Call Stop/Termination** (`POST /v1/calls/{id}/stop`) | **NONE** | HIGH - Cannot enforce call duration limits |
| 6 | **DTMF Input Handling** (from transcript) | **NONE** - Quo transcripts don't include DTMF data | HIGH - DTMF inbox feature breaks |
| 7 | **Variable Extraction** (from call `variables` field) | **NONE** | MEDIUM - Question-type nodes can't extract answers |
| 8 | **Voice Selection** (`GET /v1/voices`) | **NONE** | MEDIUM - No TTS voice customization |
| 9 | **Webhook per-call** (configured in call payload) | Separate webhook registration (global) | LOW - Different architecture but achievable |

### 3.2 Features Quo CAN Provide (Partial or Complementary)

| # | Feature | How Quo Handles It | Mapping Potential |
|---|---|---|---|
| 1 | **Call History / Logs** | `GET /v1/calls` - Lists call history | Can supplement call logging |
| 2 | **Call Recordings** | `GET /v1/call-recordings/{callId}` | Can retrieve recordings for completed calls |
| 3 | **Call Transcripts** | `GET /v1/call-transcripts/{id}` + webhook | Can get dialogue transcripts post-call |
| 4 | **Call Summaries** | `GET /v1/call-summaries/{callId}` + webhook | AI-generated summaries (Business+ plans) |
| 5 | **SMS/Text Messaging** | `POST /v1/messages` | New capability not in Bland.ai |
| 6 | **Contact Management** | `GET/POST /v1/contacts` | Can sync/manage contacts |
| 7 | **Real-time Call Events** | Webhooks for `call.ringing`, `call.completed` | Can track inbound call lifecycle |
| 8 | **Phone Number Management** | `GET /v1/phone-numbers` | Can list workspace phone numbers |

### 3.3 Summary Verdict

> **Quo CANNOT replace Bland.ai as the voice/IVR provider.** Quo is a business phone system API focused on **reading call data, managing contacts, and sending messages**. It does NOT provide programmable outbound calling, AI voice agents, or IVR flow execution -- which are the core features of the current application.

---

## 4. Recommended Integration Strategy

Given the critical gaps, there are **three viable strategies**:

### Strategy A: Quo as Complementary Provider (RECOMMENDED)
Keep Bland.ai (or similar programmable voice API) for core IVR functionality, and use Quo for:
- **Caller ID management** - Use Quo phone numbers as caller IDs
- **SMS notifications** - Send text updates to call recipients before/after calls
- **Contact sync** - Manage contacts between the bot and Quo workspace
- **Call monitoring** - Use webhooks to track inbound calls to Quo numbers
- **Call recordings & transcripts** - Retrieve post-call recordings and AI transcripts
- **Inbound call handling** - React to calls coming INTO Quo numbers

**Architecture:**
```
Telegram Bot
    |
    +-> Bland.ai (Outbound IVR, Pathways, AI Voice Agent)
    |       |
    |       +-> Webhooks -> App -> DB
    |
    +-> Quo API (Caller ID, SMS, Contacts, Recordings, Inbound Monitoring)
            |
            +-> Webhooks -> App -> DB
```

### Strategy B: Full Provider Replacement
Replace Bland.ai with a provider that offers similar programmable voice capabilities:
- **Twilio** (Programmable Voice + TwiML for IVR flows)
- **Vonage/Nexmo** (Voice API with NCCO for call flows)
- **Plivo** (Outbound calls + XML-based IVR)
- **Retell AI** (AI voice agents, similar to Bland.ai)
- **Vapi** (Voice AI platform, similar to Bland.ai)

### Strategy C: Hybrid with Custom AI Layer
Use Quo's phone numbers + a separate AI/TTS service:
- Quo for phone number management and call tracking
- Build custom AI voice agent using a real-time voice API
- Requires significant development effort

---

## 5. Quo Integration Implementation Plan (Strategy A)

If proceeding with Strategy A (Quo as complementary), here's the implementation plan:

### 5.1 New Environment Variables
```
QUO_API_KEY=tul7jVf2oQHGPMp211neCYcWoKMxAOzt
QUO_BASE_URL=https://api.openphone.com
QUO_PHONE_NUMBER_ID=PNHNMitFtw
QUO_USER_ID=USSX7fbpdt
QUO_PHONE_NUMBER=+18886033870
```

### 5.2 New Module: `bot/quo_client.py`
A dedicated client module for all Quo API interactions:

```python
class QuoClient:
    def __init__(self, api_key, base_url="https://api.openphone.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }

    # Phone Numbers
    def list_phone_numbers(self) -> dict
    def get_phone_number(self, phone_number_id: str) -> dict

    # Calls (read-only)
    def list_calls(self, phone_number_id: str, participants: list, **kwargs) -> dict
    def get_call(self, call_id: str) -> dict
    def get_call_recordings(self, call_id: str) -> dict
    def get_call_summary(self, call_id: str) -> dict
    def get_call_transcript(self, call_id: str) -> dict

    # Messages
    def send_message(self, from_number: str, to: str, content: str, **kwargs) -> dict
    def list_messages(self, phone_number_id: str, participants: list, **kwargs) -> dict

    # Contacts
    def list_contacts(self, **kwargs) -> dict
    def create_contact(self, first_name: str, last_name: str, phone: str, **kwargs) -> dict

    # Webhooks
    def create_call_webhook(self, url: str, events: list, **kwargs) -> dict
    def create_message_webhook(self, url: str, events: list, **kwargs) -> dict
```

### 5.3 New Webhook Endpoints
```python
# bot/quo_webhooks.py
@csrf_exempt
def quo_call_webhook(request):
    """Handle Quo call events (ringing, completed, recording.completed)"""

@csrf_exempt
def quo_message_webhook(request):
    """Handle Quo message events (received, delivered)"""

@csrf_exempt
def quo_transcript_webhook(request):
    """Handle Quo call transcript completed events"""
```

### 5.4 Features to Implement with Quo
1. **Pre-call SMS**: Send SMS to recipients before IVR calls
2. **Post-call SMS**: Send follow-up messages after calls complete
3. **Caller ID from Quo**: Use Quo phone numbers as caller IDs in Bland.ai calls
4. **Inbound call tracking**: Monitor inbound calls to Quo numbers
5. **Contact enrichment**: Sync campaign contacts with Quo contacts
6. **Call recording retrieval**: Fetch recordings from Quo for analysis
7. **Transcript retrieval**: Get post-call transcripts for review

### 5.5 Database Changes Required
```python
# New model for Quo integration tracking
class QuoCallLog(models.Model):
    quo_call_id = models.CharField(max_length=255, primary_key=True)
    bland_call_id = models.CharField(max_length=255, null=True)  # Link to Bland.ai call
    phone_number_id = models.CharField(max_length=255)
    direction = models.CharField(max_length=20)  # incoming/outgoing
    status = models.CharField(max_length=50)
    duration = models.IntegerField(null=True)
    recording_url = models.URLField(null=True)
    transcript = models.TextField(null=True)
    summary = models.TextField(null=True)
    created_at = models.DateTimeField()

class QuoMessageLog(models.Model):
    quo_message_id = models.CharField(max_length=255, primary_key=True)
    direction = models.CharField(max_length=20)
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    content = models.TextField()
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField()
```

---

## 6. Multi-Tenancy Architecture Design

### 6.1 Approach: Shared Database, Shared Schema with Tenant ID

This is the most practical approach for this application:
- Single database, single schema
- Every table gets a `tenant_id` foreign key
- All queries are scoped by tenant
- Each tenant has their own API keys (Bland.ai, Quo, DynoPay)

### 6.2 New Tenant Model

```python
# user/models.py (or new app: tenants/models.py)
class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Per-tenant API keys
    bland_api_key = encrypt(models.CharField(max_length=500, null=True))
    quo_api_key = encrypt(models.CharField(max_length=500, null=True))
    quo_phone_number_id = models.CharField(max_length=255, null=True)
    quo_phone_number = models.CharField(max_length=20, null=True)
    dynopay_api_key = encrypt(models.CharField(max_length=500, null=True))
    telegram_bot_token = encrypt(models.CharField(max_length=500, null=True))

    # Billing & usage
    max_users = models.IntegerField(default=10)
    max_calls_per_month = models.IntegerField(default=1000)
```

### 6.3 Models Requiring `tenant_id` FK

| Model | App | Current PK | Change Required |
|---|---|---|---|
| `TelegramUser` | user | `user_id` (BigInt) | Add `tenant_id` FK |
| `Pathways` | bot | `pathway_id` (Text) | Add `tenant_id` FK |
| `CallLogsTable` | bot | `call_id` (Text) | Add `tenant_id` FK |
| `CallDetails` | bot | `call_id` (Text) | Add `tenant_id` FK |
| `TransferCallNumbers` | bot | `num_id` (UUID) | Add `tenant_id` FK |
| `FeedbackLogs` | bot | `pathway_id` (Text) | Add `tenant_id` FK |
| `FeedbackDetails` | bot | `call_id` (Text) | Add `tenant_id` FK |
| `CallDuration` | bot | `call_id` (Char) | Add `tenant_id` FK |
| `BatchCallLogs` | bot | `call_id` (Text) | Add `tenant_id` FK |
| `AI_Assisted_Tasks` | bot | `id` (UUID) | Add `tenant_id` FK |
| `CallerIds` | bot | `caller_id` (Char) | Add `tenant_id` FK |
| `CampaignLogs` | bot | `campaign_id` (UUID) | Add `tenant_id` FK |
| `ScheduledCalls` | bot | Auto ID | Add `tenant_id` FK |
| `ReminderTable` | bot | Auto ID | Add `tenant_id` FK |
| `SubscriptionPlans` | payment | `plan_id` (UUID) | Add `tenant_id` FK (or keep global) |
| `UserSubscription` | payment | Auto ID | Add `tenant_id` FK |
| `UserTransactionLogs` | payment | `transaction_id` (UUID) | Add `tenant_id` FK |
| `OveragePricingTable` | payment | `pricing_unit` (Char) | Keep global OR add `tenant_id` |
| `ManageFreePlanSingleIVRCall` | payment | `call_id` (Char) | Add `tenant_id` FK |
| `DTMF_Inbox` | payment | `call_id` (Text) | Add `tenant_id` FK |

### 6.4 Tenant Resolution Strategy

For a Telegram bot, tenant resolution works differently than web apps:

```
1. User sends message to Telegram Bot
2. Bot looks up TelegramUser by user_id
3. TelegramUser has tenant_id -> resolves tenant
4. All subsequent queries scoped to that tenant
5. API keys fetched from Tenant model
```

For a multi-bot setup (each tenant has their own bot):
```
1. Each Tenant has its own Telegram Bot Token
2. Webhook URL includes tenant identifier: /webhook/{tenant_slug}/
3. Tenant resolved from URL path
4. All operations scoped to that tenant
```

### 6.5 Implementation Pattern: Tenant-Aware Managers

```python
class TenantManager(models.Manager):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

class Pathways(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    # ... existing fields ...
    objects = TenantManager()

# Usage:
pathways = Pathways.objects.for_tenant(current_tenant).all()
```

### 6.6 API Key Isolation

Instead of using global `settings.BLAND_API_KEY`, each API call should use the tenant's key:

```python
# Before (single-tenant):
headers = {"Authorization": f"{settings.BLAND_API_KEY}"}

# After (multi-tenant):
headers = {"Authorization": f"{tenant.bland_api_key}"}
```

### 6.7 Migration Strategy

1. **Phase 1**: Create `Tenant` model, create default tenant, add nullable `tenant_id` to all models
2. **Phase 2**: Backfill all existing records with the default tenant's ID
3. **Phase 3**: Make `tenant_id` non-nullable, add database constraints
4. **Phase 4**: Update all queries to filter by tenant
5. **Phase 5**: Update views/tasks to resolve tenant from context
6. **Phase 6**: Move API keys from settings to Tenant model

---

## 7. File-by-File Change Impact

### High Impact (Major Rewrites)
| File | Changes |
|---|---|
| `bot/views.py` | Every Bland.ai function needs tenant-aware API key; new Quo client calls |
| `bot/tasks.py` | All Celery tasks need tenant context; API keys from tenant model |
| `bot/models.py` | Add `tenant_id` FK to all models; add TenantManager |
| `user/models.py` | Add `tenant_id` to TelegramUser; add Tenant model |
| `payment/models.py` | Add `tenant_id` to subscription, transaction, and DTMF models |

### Medium Impact (Significant Changes)
| File | Changes |
|---|---|
| `bot/telegrambot.py` | Bot command handlers need tenant context |
| `bot/callback_query_handlers.py` | Callback handlers need tenant context |
| `bot/utils.py` | Utility functions need tenant parameter |
| `bot/webhooks.py` | Webhook handler needs tenant resolution |
| `payment/views.py` | Payment functions need tenant context |
| `TelegramBot/settings.py` | Add Quo settings; tenant-aware config |

### New Files Required
| File | Purpose |
|---|---|
| `bot/quo_client.py` | Quo API client class |
| `bot/quo_webhooks.py` | Quo-specific webhook handlers |
| `bot/middleware.py` | Tenant resolution middleware |
| `tenants/models.py` | Tenant model (if separate app) |
| `tenants/admin.py` | Tenant admin interface |

---

## 8. Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Quo cannot initiate outbound calls | **CRITICAL** | Must keep Bland.ai or alternative for IVR core |
| Multi-tenancy migration breaks existing data | HIGH | Phased migration with default tenant; thorough testing |
| Per-tenant bot tokens require multiple bot instances | HIGH | Use webhook mode, not polling; dynamic bot routing |
| Quo rate limit (10 req/sec) with multiple tenants | MEDIUM | Request queuing; per-tenant rate limiting |
| Quo messaging restricted (needs carrier registration) | MEDIUM | Complete US carrier registration before SMS features |
| Increased complexity of API key management | MEDIUM | Encrypt all keys; admin interface for key management |

---

## 9. Conclusion

### Key Takeaways

1. **Quo is NOT a replacement for Bland.ai** - It lacks programmable outbound calling, IVR flow execution, and AI voice agent capabilities.

2. **Quo is best positioned as a COMPLEMENTARY service** - It excels at phone number management, SMS messaging, contact management, and post-call data retrieval (recordings, transcripts, summaries).

3. **The recommended approach is Strategy A** (dual-provider) where Bland.ai handles core IVR and Quo handles communication enhancements (SMS, contacts, caller ID, call monitoring).

4. **Multi-tenancy is achievable** using shared-schema with tenant ID columns, but requires careful phased migration to avoid data issues.

### Recommended Next Steps

1. **Decision Point**: Confirm with stakeholders whether to proceed with Strategy A (Quo as complementary) or Strategy B (full provider replacement with Twilio/Vapi/Retell).
2. If Strategy A: Implement `quo_client.py` module and SMS notification features first.
3. Begin multi-tenancy migration Phase 1 (Tenant model + nullable FKs).
4. Complete US carrier registration for Quo SMS capabilities.
