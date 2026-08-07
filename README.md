# TJM Labs — Pharmacy Sales Agent

A simulated **inbound** sales agent for TJM Labs. A pharmacy calls in; the
agent identifies the caller against a live pharmacy API, runs a short
discovery conversation, tailors its close to the pharmacy's prescription
volume, and can queue a follow-up email or schedule a specialist callback
(mock tools). See `DESIGN.md` for the full design write-up.

## How to run

Python 3.9+ — standard library only, nothing to install.

```
python main.py                                   # known caller (HealthFirst Pharmacy)
python main.py --phone "+1-555-000-9999"         # unknown caller
python main.py --api-url "https://bad.invalid/"  # simulate the API being down
python -m unittest                               # run the test suite (31 tests)
```

Type replies as the pharmacy; `bye` / `quit` ends the call. You can also
pipe a scripted call in — each line is one caller turn, and input is
echoed so the transcript shows both sides:

```
cat script.txt | python3 main.py                 # macOS / Linux
Get-Content script.txt | python main.py          # Windows PowerShell
```

## Architecture (5 lines)

- `main.py` — CLI entry point; reads caller lines, prints agent lines.
- `api.py` — fetches the pharmacy list once; phone-normalized lookup; Rx-volume extraction across both record shapes in the data.
- `agent.py` — the conversation state machine: `IDENTIFY → DISCOVERY → PITCH → FOLLOW_UP → END`, with state-aware intent detection.
- `tools.py` — mock actions: `send_follow_up_email`, `schedule_callback` (print `[TOOL CALLED]` markers).
- `knowledge.py` — the grounding boundary: deliberately empty of product claims, plus the safe fallback line and the high-volume threshold.

`tests.py` holds the unittest suite.

## How hallucination is prevented

The agent may only state facts from three sources:

1. the caller's API record (name, city, Rx volume, email),
2. what the caller said on this call (name, volume, pain point),
3. `knowledge.py` — which deliberately contains **no product knowledge**.

That third point is a design decision, not an omission: the task prompt
supplies no approved facts about TJM Labs' product, pricing, onboarding,
or results, so the agent makes **no company-specific claims at all**
rather than inventing plausible ones. Every agent line is a template over
the three sources; there is no generative step.

Questions about pricing, integrations, onboarding, features, or results
therefore get one safe fallback — *"I don't have that information on hand
— I can send you the details by email or schedule a callback with a
specialist"* — which doubles as a funnel into the two follow-up tools and
a human who is allowed to make claims. The pitch itself is grounded
purely in collected data, e.g.: *"At about 2,500 prescriptions a month,
Sunrise Pharmacy is a high-volume operation — I'll flag that for our
specialist so the follow-up is tailored to your scale."*

Unmatched *statements* (e.g. the answer to the discovery question) are
stored as caller-provided context instead of triggering the fallback, so
the agent never stonewalls its own open questions. Tool intents are
state-aware: "email me the details" or a bare "email" right after the
email-or-callback question invokes the tool, while capability questions
like "Do you send email reminders?" get the fallback.

## Assumptions

- **No product claims by design** — see above. "Alex" is a placeholder persona name.
- **Phone matching** compares digits only and drops a leading US country code, so `555 123 4567` matches `+1-555-123-4567`. Junk records with letter phones (`+1-555-NEW-LEAD-TEST`) normalize to almost nothing; a minimum-digit guard keeps them from ever matching.
- **Two record shapes** exist in the API: seed records with a `prescriptions: [{drug, count}]` array (volume = sum of counts) and newer records with a flat `rxVolume` number. Both are handled; records with neither report volume as unknown and the agent simply asks.
- **High-volume threshold = 1,000 scripts/month.** The live data clusters at 0 / 55–100 / 3,000–4,000, so 1,000 cleanly separates the tiers.
- **Records with a null name** (several exist) are treated as unknown callers rather than greeting someone as "None".
- **API down ≠ crash**: the fetch is wrapped in try/except; the caller is just treated as unknown.

## Sample transcripts (real runs)

### Known caller — inbound greeting from the API record, pricing question → fallback, email tool

```
--- Incoming call from +1-555-123-4567 ---
Agent: Thanks for calling TJM Labs, this is Alex. Am I speaking with HealthFirst Pharmacy in New York?
Agent: I see you're filling around 100 scripts a month.
You: Yes, speaking
Agent: Thanks! Quick question so I don't waste your time, HealthFirst Pharmacy: what eats up most of your team's day right now - refills, inventory, or insurance paperwork?
You: Mostly insurance paperwork, the rejections eat hours
Agent: Insurance paperwork - understood.
Agent: I'll make sure our specialist knows HealthFirst Pharmacy fills about 100 scripts a month and what you just told me, so the follow-up fits your operation.
Agent: For specifics - pricing, product details - our specialist team is the right source. Would details by email or a specialist callback work better for you?
You: What does it cost?
Agent: I don't have that information on hand - I can send you the details by email or schedule a callback with a specialist. Which works better?
You: Send me the details by email
[TOOL CALLED] Email queued to HealthFirst Pharmacy re: your question "What does it cost?"
Agent: Done - I've queued an email to contact@healthfirst.com about your question "What does it cost?". Anything else I can help with?
You: No, that's all - thanks!
Agent: Thanks for calling, HealthFirst Pharmacy. Have a great day!
--- Call ended ---
```

### Unknown caller — high-volume grounded pitch, out-of-scope question → fallback, callback tool

```
--- Incoming call from +1-555-000-9999 ---
Agent: Thanks for calling TJM Labs, this is Alex.
Agent: Could I get your pharmacy's name?
You: Sunrise Pharmacy
Agent: Nice to meet you, Sunrise Pharmacy! Roughly how many prescriptions do you fill in a month?
You: We fill about 2,500 a month
Agent: Thanks! Quick question so I don't waste your time, Sunrise Pharmacy: what eats up most of your team's day right now - refills, inventory, or insurance paperwork?
You: Honestly inventory, we're always short or overstocked
Agent: Inventory - understood.
Agent: At about 2,500 prescriptions a month, Sunrise Pharmacy is a high-volume operation - I'll flag that for our specialist so the follow-up is tailored to your scale.
Agent: For specifics - pricing, product details - our specialist team is the right source. Would details by email or a specialist callback work better for you?
You: Do you integrate with PioneerRx?
Agent: I don't have that information on hand - I can send you the details by email or schedule a callback with a specialist. Which works better?
You: A callback works
Agent: Absolutely - when's a good time for one of our specialists to call Sunrise Pharmacy?
You: Call me tomorrow at 10
[TOOL CALLED] Callback scheduled with Sunrise Pharmacy for tomorrow at 10
Agent: You're all set - a specialist will call Sunrise Pharmacy tomorrow at 10. Anything else I can help with?
You: Bye
Agent: Thanks for calling, Sunrise Pharmacy. Have a great day!
--- Call ended ---
```

Note the second-to-last exchange: "Call me tomorrow at 10" contains
callback keywords, but because the agent is already collecting a callback
time, the utterance fills that slot — the tool fires exactly once.

## Verification scenarios

All covered by `python -m unittest` (31 tests) and/or scripted CLI runs:

1. Known caller gets an inbound greeting with name, city, and known volume.
2. Unknown caller's name and stated high volume drive a grounded pitch with no invented claims.
3. "Do you integrate with PioneerRx?" → safe fallback.
4. "Do you send email reminders?" → safe fallback, email tool **not** called.
5. "A callback works" then "Call me tomorrow at 10" → callback tool fires exactly once with the extracted time.
6. Explicit email request → email tool fires once.
7. API outage → graceful note, unknown-caller flow continues.
8. Unparseable volume → polite reprompt, then moves on; "two thousand" parses; "I'd rather not say" accepted.
9. `bye`, blank input, identity denial, and "not interested" all behave safely.
10. All files are stdlib-only and compile cleanly (`python -m compileall .`).

## If I had 3 more hours

1. **More automated tests** — property-style tests for the intent matcher (random paraphrase corpus), a transcript golden-file harness, and CI via GitHub Actions.
2. **Production telephony + CRM** — replace the stdin loop with a real voice/telephony webhook (e.g. Twilio), and make the tools write to a CRM/ticket queue with idempotency keys instead of printing.
3. **LLM intent extraction with deterministic guardrails** — swap keyword matching for a small LLM that returns structured intents/slots (JSON schema), while keeping this state machine as the authority on what may be *said* and when tools fire, so hallucination guarantees survive the upgrade.
4. **Observability + evaluation** — structured logs of state transitions, intent hits, fallback rate, and tool calls; an offline eval set of scripted calls scored for grounding violations.
5. **Security & privacy** — redact caller PII in logs, add retention limits for collected data, and validate/escape everything sent to the mocked external systems.
