# Concurrency & Telephony Provider Analysis Report
## Speechcue — Twilio, Telnyx, and Retell AI Integration

---

## 1. The Problem: 20 Concurrent Call Limit

Retell AI's Pay-As-You-Go plan defaults to **20 concurrent calls** account-wide. When bot users upload 50+ numbers for batch calls, calls queue or fail once the limit is hit.

### Current Options Within Retell
| Option | Details | Cost |
|--------|---------|------|
| **Increase concurrency** | Upgrade via Retell Billing dashboard | ~$8/month per additional concurrent slot |
| **Concurrency Burst** | Temporarily burst to 3x your limit (or limit + 300) | $0.10/min surcharge on excess calls |
| **Enterprise plan** | Custom limits (10,000+ concurrent) | Contact Retell sales |

**Recommendation**: For immediate relief, enable **Concurrency Burst** in Retell dashboard. This handles spikes without permanent cost increases.

---

## 2. Using Twilio & Telnyx Alongside Retell

### How It Works (SIP Trunking)
Retell doesn't replace Twilio/Telnyx — it **sits on top** of them via SIP trunking. The flow:

```
Bot User → Retell AI (voice AI) → SIP Trunk → Twilio/Telnyx (telephony carrier) → PSTN → Callee
```

**Key insight**: The concurrency limit is on **Retell's side**, not Twilio/Telnyx. Adding more carrier numbers doesn't bypass Retell's 20-call limit. You need to either:
- A) Increase Retell concurrency (simplest)
- B) Use multiple Retell accounts (complex, not recommended)
- C) Use Twilio/Telnyx directly for overflow calls without Retell AI (loses AI features)

### Cost Comparison (Per 10,000 Minutes/Month)

| Provider | Telephony Cost | AI Processing | Total |
|----------|---------------|---------------|-------|
| **Retell-native numbers** | Included in $0.07-0.09/min | Included | ~$700-900 |
| **Retell + Twilio** | ~$130 (Twilio) + $0.05-0.07/min (Retell AI only) | Included | ~$630-830 |
| **Retell + Telnyx** | ~$70 (Telnyx) + $0.05-0.07/min (Retell AI only) | Included | ~$570-770 |

**Winner**: Telnyx is ~45% cheaper than Twilio for carrier costs. Use Telnyx for bulk/batch calls, Retell-native for simplicity on low volume.

---

## 3. Importing Numbers from Twilio/Telnyx to Retell (API)

### YES — Fully Programmable via Retell's Import API

**Retell Import Phone Number API** (`POST /import-phone-number`):

```json
{
  "phone_number": "+14155552671",
  "phone_number_type": "retell-twilio",  // or "retell-telnyx"
  "termination_uri": "yourtrunk.pstn.twilio.com",
  "sip_trunk_auth_username": "your_username",
  "sip_trunk_auth_password": "your_password",
  "inbound_agent_id": "agent_xxx",  // optional
  "nickname": "Batch Line 1"         // optional
}
```

### Setup Steps

#### For Twilio → Retell:
1. **In Twilio Console**: Create an Elastic SIP Trunk
   - Termination: Set URI (e.g., `yourname.pstn.twilio.com`) + credentials
   - Origination: Add `sip:sip.retellai.com` (for inbound routing to Retell)
2. **Via Retell API**: Import with `phone_number_type: "retell-twilio"` + termination URI + credentials
3. Number appears in Retell dashboard, usable for both inbound/outbound

#### For Telnyx → Retell:
1. **In Telnyx Portal**: Create SIP Connection with outbound auth credentials
2. **Via Retell API**: Import with `phone_number_type: "retell-telnyx"`, `termination_uri: "sip.telnyx.com"`, + credentials
3. Same result — number works in Retell

### Can You Port Numbers BETWEEN Providers?

| Direction | Programmatic API? | Timeline |
|-----------|------------------|----------|
| **Into Twilio** | YES (Porting API, Public Beta) — US local only, up to 1,000 numbers | 2-4 weeks |
| **Out of Twilio** | NO API — manual via Twilio Support + LOA | 2-6 weeks |
| **Into Telnyx** | YES (Porting Order API v2) — US, CA, 50+ countries | Same-day (FastPort) to weeks |
| **Out of Telnyx** | Manual — contact gaining carrier with LOA | 2-4 weeks |
| **Twilio/Telnyx → Retell** | NO PORTING needed — Import via SIP trunk (instant) | Instant (minutes) |

**Key**: You don't need to "port" numbers to Retell. You **import** them via SIP — the number stays with Twilio/Telnyx, and Retell handles the AI layer. This is instant and reversible.

---

## 4. Multi-Tenant / Sub-Account Architecture

### Should Speechcue Use Sub-Accounts?

**YES for Telnyx. OPTIONAL for Twilio. NOT NEEDED for Retell.**

### Telnyx: Managed Accounts (Recommended)

Telnyx **Managed Accounts** are purpose-built for multi-tenant SaaS:

| Feature | Details |
|---------|---------|
| **Separate billing** | Each managed account has its own balance, payment methods, invoices |
| **Scoped API keys** | Create API keys per managed account for tenant isolation |
| **Number provisioning** | Manager purchases numbers and assigns to specific accounts |
| **Default limit** | 1,000 sub-accounts (increase via support) |
| **Pricing** | Inherits manager's committed rates (tenants can't see pricing) |

**How Speechcue would use it:**
- Your Speechcue account = **Manager Account**
- Each bot user (or group of users) = **Managed Account**
- Buy numbers under the managed account → import to Retell via SIP
- Bill each tenant separately, or absorb costs and bill via DynoPay wallet

**Credentials needed:**
- Telnyx API Key (Manager level)
- Per-managed-account API keys (auto-generated)
- SIP Connection credentials (username + password per trunk)

### Twilio: Subaccounts (Optional)

Twilio subaccounts are useful but **less necessary** for Speechcue:

| Feature | Details |
|---------|---------|
| **Resource isolation** | Each subaccount has separate numbers, calls, logs |
| **Billing** | Rolls up to parent account (NO separate billing) |
| **API** | Each subaccount gets its own Account SID + Auth Token |
| **Limit** | Up to 1,000 subaccounts by default |
| **Concurrency** | SIP Trunking = unlimited concurrent after trial |

**How Speechcue would use it:**
- Main Twilio account = Speechcue
- Create subaccounts programmatically for tenant isolation
- Purchase numbers under subaccounts → SIP trunk to Retell
- All billing rolls up to your main Twilio account

**Credentials needed:**
- Twilio Account SID + Auth Token (master)
- Per-subaccount SID + Auth Token (auto-generated)
- Elastic SIP Trunk per subaccount (termination URI + credentials)

### Retell: Single Account (No Sub-Users)

Retell does NOT have a multi-tenant/sub-user model. All imported numbers, agents, and calls live under one Retell account. This means:
- You manage tenant isolation at the **application level** (your Django DB)
- All calls count toward your single concurrency limit
- All billing is under one Retell account

---

## 5. Credentials Summary

### What You Need

| Credential | Where to Get It | Purpose |
|------------|----------------|---------|
| **Retell API Key** | retellai.com → API Keys | Already have (`key_01bfb1...`) — manages agents, calls, numbers |
| **Twilio Account SID** | twilio.com → Console Dashboard | Master account identifier |
| **Twilio Auth Token** | twilio.com → Console Dashboard | API authentication |
| **Twilio SIP Trunk Termination URI** | twilio.com → Elastic SIP Trunking → Create Trunk | For Retell import (e.g., `yourname.pstn.twilio.com`) |
| **Twilio SIP Credentials** | twilio.com → SIP Trunk → Termination → Credentials | Username + password for SIP auth |
| **Telnyx API Key** | telnyx.com → Mission Control → API Keys | Master API access |
| **Telnyx SIP Connection Credentials** | telnyx.com → SIP Connections → Outbound | Username + password for SIP auth |
| **Telnyx Managed Account API Keys** | Created via API per managed account | Per-tenant access |

---

## 6. Recommended Architecture for Speechcue

```
┌─────────────────────────────────────────────────┐
│                  SPEECHCUE BOT                   │
│            (Django + Telegram Bot)                │
├─────────────────────────────────────────────────┤
│                                                   │
│  User buys number → Which provider?               │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Retell   │  │  Telnyx  │  │   Twilio      │   │
│  │  Native   │  │ (Cheap)  │  │ (Reliable)    │   │
│  │  $2/mo    │  │ $0.50/mo │  │ $1.15/mo      │   │
│  └────┬─────┘  └────┬─────┘  └─────┬────────┘   │
│       │              │               │             │
│       │         SIP Import      SIP Import         │
│       │              │               │             │
│       ▼              ▼               ▼             │
│  ┌──────────────────────────────────────────┐     │
│  │           RETELL AI (Voice AI)            │     │
│  │     Concurrency: 20 base + burst          │     │
│  │     All numbers managed here              │     │
│  └──────────────────────────────────────────┘     │
│                                                   │
│  Batch calls > 20? → Concurrency Burst ($0.10/min)│
│  Batch calls > 60? → Upgrade concurrency ($8/slot)│
│  Batch calls > 300? → Contact Retell Enterprise   │
│                                                   │
└─────────────────────────────────────────────────┘
```

### Phase 1 (Now): Quick Wins
1. Enable **Concurrency Burst** on Retell dashboard
2. Keep using Retell-native numbers for simplicity

### Phase 2 (When users scale): Add Telnyx
1. Create Telnyx Manager Account
2. Set up SIP Connection with auth credentials
3. Add `import_phone_number` function in `retell_service.py`
4. Bot offers "Buy number" → Telnyx (cheaper) or Retell (simpler)
5. All numbers imported to Retell via SIP for AI handling

### Phase 3 (High volume): Multi-Tenant
1. Create Telnyx Managed Accounts per power-user/enterprise customer
2. Separate billing per tenant via Telnyx
3. Increase Retell concurrency to match demand
4. Add Twilio as fallback carrier for redundancy

---

## 7. Bottom Line

| Question | Answer |
|----------|--------|
| **Can we handle >20 concurrent calls?** | Yes — enable Concurrency Burst (instant) or upgrade slots ($8/slot/mo) |
| **Should we use Twilio or Telnyx?** | **Telnyx first** (45% cheaper, better multi-tenant). Twilio as backup |
| **Can we transfer numbers to Retell via API?** | Yes — SIP import is instant and programmable (no porting needed) |
| **Multi-tenant sub-users?** | **Telnyx Managed Accounts** = best fit (separate billing + API keys). Twilio subaccounts optional |
| **What credentials do we need?** | Telnyx API Key + SIP creds. Optionally Twilio SID + Auth Token + SIP creds |
