# TJM Labs — Pharmacy Sales Agent

A simulated outbound-sales phone agent for TJM Labs. It "receives a call"
from a pharmacy, identifies the caller against a live pharmacy API, runs a
short discovery-and-pitch conversation, and can queue a follow-up email or
schedule a specialist callback (mock tools).

## How to run

Python 3.9+ — standard library only, nothing to install.

```
python main.py                                   # known caller (HealthFirst Pharmacy)
python main.py --phone "+1-555-000-9999"         # unknown caller
python main.py --api-url "https://bad.invalid/"  # simulate the API being down
```

Type replies as the pharmacy; `bye` / `quit` ends the call. You can also
pipe a scripted call in: `Get-Content script.txt | python main.py`
(each line is one caller turn; input is echoed so the transcript shows
both sides).

## Architecture (5 lines)

- `main.py` — CLI entry point; reads caller lines, prints agent lines.
- `api.py` — fetches the pharmacy list once; phone-normalized lookup; Rx-volume extraction across both record shapes in the data.
- `agent.py` — the conversation state machine: `IDENTIFY → DISCOVERY → PITCH → FOLLOW_UP → END`, with keyword intent detection.
- `tools.py` — mock actions: `send_follow_up_email`, `schedule_callback` (print `[TOOL CALLED]` markers).
- `knowledge.py` — the only company facts the agent may state, plus the safe fallback line and the high-volume threshold.

## How hallucination is prevented

The agent may only state facts from three sources:

1. the caller's API record (name, city, Rx volume, email),
2. what the caller said on this call (name, volume, pain point),
3. `knowledge.FACTS` — four placeholder facts about TJM Labs.

Every agent line is a template over those sources; there is no generative
step. A question that keyword-matches a fact gets that fact verbatim. Any
question that matches nothing gets one safe fallback — *"I don't have that
information on hand — I can send you the details by email or schedule a
callback with a specialist."* — which doubles as a funnel into the two
follow-up tools. Unmatched *statements* (e.g. the answer to the discovery
question) are stored as caller-provided context instead of triggering the
fallback, so the agent never stonewalls its own open questions.

## Assumptions

- **Company facts are invented placeholders** (pricing, onboarding time, the 30% stat) — clearly not real claims about TJM Labs.
- **Phone matching** compares digits only and drops a leading US country code, so `555 123 4567` matches `+1-555-123-4567`. Junk records with letter phones (`+1-555-NEW-LEAD-TEST`) normalize to almost nothing; a minimum-digit guard keeps them from ever matching.
- **Two record shapes** exist in the API: seed records with a `prescriptions: [{drug, count}]` array (volume = sum of counts) and newer records with a flat `rxVolume` number. Both are handled; records with neither report volume as unknown and the agent simply asks.
- **High-volume threshold = 1,000 scripts/month.** The live data clusters at 0 / 55–100 / 3,000–4,000, so 1,000 cleanly separates the tiers.
- **Records with a null name** (several exist) are treated as unknown callers rather than greeting someone as "None".
- **API down ≠ crash**: the fetch is wrapped in try/except; the caller is just treated as unknown.

## Sample transcripts (real runs)

### Known caller — identified from the API, pricing question, email tool

```
--- Incoming call from +1-555-123-4567 ---
Agent: Hi, is this HealthFirst Pharmacy in New York? This is Alex calling from TJM Labs.
Agent: I see you're filling around 100 scripts a month - impressive operation.
You: Yes, speaking
Agent: Thanks! Quick question so I don't waste your time, HealthFirst Pharmacy: what eats up most of your team's day right now - refills, inventory, or insurance paperwork?
You: Mostly insurance paperwork, the rejections eat hours
Agent: Insurance paperwork - that's the pain we hear about most.
Agent: TJM Labs makes a pharmacy operations platform that automates refill reminders, inventory forecasting, and insurance pre-checks.
Agent: Pharmacies using TJM Labs report roughly 30% less time spent on manual insurance paperwork.
Agent: Would it help if I emailed you the details, or should I schedule a callback with one of our specialists?
You: What does it cost?
Agent: Pricing starts at $299 per month per location, with volume discounts above 1,000 monthly prescriptions.
Agent: Would you prefer the details by email, or a callback from a specialist?
You: Send me the details by email
[TOOL CALLED] Email queued to HealthFirst Pharmacy re: pricing
Agent: Done - I've queued an email to contact@healthfirst.com with the pricing details. Anything else I can help with?
You: No, that's all - thanks!
Agent: Thanks for your time, HealthFirst Pharmacy. Have a great day!
--- Call ended ---
```

### Unknown caller — high-volume pitch, out-of-scope question → safe fallback, callback tool

```
--- Incoming call from +1-555-000-9999 ---
Agent: Hi, this is Alex calling from TJM Labs. Thanks for taking the call!
Agent: Could I get your pharmacy's name?
You: Sunrise Pharmacy
Agent: Nice to meet you, Sunrise Pharmacy! Roughly how many prescriptions do you fill in a month?
You: We fill about 2,500 a month
Agent: Thanks! Quick question so I don't waste your time, Sunrise Pharmacy: what eats up most of your team's day right now - refills, inventory, or insurance paperwork?
You: Honestly inventory, we're always short or overstocked
Agent: Inventory - keeping stock right is a constant battle.
Agent: TJM Labs makes a pharmacy operations platform that automates refill reminders, inventory forecasting, and insurance pre-checks.
Agent: For a pharmacy your size - about 2,500 scripts a month - it really adds up: Pharmacies using TJM Labs report roughly 30% less time spent on manual insurance paperwork. Your volume would also qualify for the discounts above 1,000 monthly prescriptions.
Agent: Would it help if I emailed you the details, or should I schedule a callback with one of our specialists?
You: Do you integrate with PioneerRx?
Agent: I don't have that information on hand - I can send you the details by email or schedule a callback with a specialist. Which works better?
You: A callback works
Agent: Absolutely - when's a good time for one of our specialists to call Sunrise Pharmacy?
You: Tomorrow at 10 am
[TOOL CALLED] Callback scheduled with Sunrise Pharmacy for Tomorrow at 10 am
Agent: You're all set - a specialist will call Sunrise Pharmacy Tomorrow at 10 am. Anything else I can help with?
You: Bye
Agent: Thanks for your time, Sunrise Pharmacy. Have a great day!
--- Call ended ---
```

## Test scenarios exercised

1. Known pharmacy (greeted by name, city, and volume from the API).
2. Unknown pharmacy (name + volume collected, used in the pitch).
3. Out-of-scope question → safe fallback (transcript above).
4. Both tools fire (`[TOOL CALLED]` lines above).
5. Extras: API unreachable (graceful), caller declines to give volume, caller denies the identity guess, blank input, "not interested" → polite close.
