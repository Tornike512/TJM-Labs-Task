# Design — TJM Labs Pharmacy Sales Agent

A simulated inbound sales call: a pharmacy dials TJM Labs, a text-based
agent answers. This document describes what was built, why it is shaped
this way, and what would change on the way to production.

## 1. Goals and non-goals

**Goals**

- Identify an inbound caller by phone number against the pharmacy API; greet known callers with what we already know (name, city, Rx volume).
- Collect name and volume conversationally when the caller is unknown.
- Run a short discovery → pitch → follow-up arc that uses the pharmacy's name and tailors the close to prescription volume (threshold: 1,000 scripts/month).
- Never state a fact the system cannot ground; funnel every unanswerable question into a follow-up email or a specialist callback (the two tools).
- Degrade gracefully: API outage, junk records, refusals, denials, EOF.

**Non-goals (for this exercise)**

- Real telephony, speech, or an actual LLM call — the conversation is text over stdin/stdout and intent detection is deterministic (see §7).
- Persistence, CRM writes, multi-call memory — tools are print-mocks.
- Natural-language coverage beyond a sales-call happy path plus the failure modes listed in `tests.py`.

## 2. Explicit assumptions

- The task prompt supplies **no approved product knowledge**, so the agent makes **no company-specific claims** (pricing, features, onboarding, results). This is deliberate — see §8.
- "Alex" is a placeholder persona name; the company name "TJM Labs" comes from the task.
- High-volume threshold = 1,000 scripts/month, chosen from the live data's clusters (0 / 55–100 / 3,000–4,000).
- Phone identity is sufficient identification for a demo; production would need verification (§10).
- The shared mock API contains junk test records (letter phones, null names, empty volume arrays); the client must tolerate all of them.

## 3. Call flows

**Known caller** (phone matches a record with a usable name):

```
start ─ "Thanks for calling TJM Labs… Am I speaking with <name> in <city>?"
      ─ "<volume>" mentioned when the record has it
confirm ─ yes → volume known? → DISCOVERY   |  volume unknown? → ask volume
        ─ no  → treat as unknown (below), keep nothing from the record
```

**Unknown caller** (no match, API down, or a null-name record):

```
start ─ "Thanks for calling TJM Labs… Could I get your pharmacy's name?"
name → volume (accepts digits, word forms, a refusal, or two failed
parses → move on with volume unknown) → DISCOVERY
```

Both flows converge: DISCOVERY asks one open question (biggest time
sink), PITCH acknowledges the answer and tailors one line to volume,
FOLLOW_UP offers email vs. callback, runs the chosen tool, and loops on
"anything else?" until a goodbye.

## 4. State and data model

States: `IDENTIFY → DISCOVERY → PITCH → FOLLOW_UP → END`, held in
`Agent.state`. Within a state, `Agent.awaiting` names the specific
pending question — either a **value slot** expecting free text (`name`,
`volume`, `pain_point`, `callback_time`, `email_address`) or a **choice
slot** expecting yes/no/one-of (`confirm_identity`, `followup_choice`,
`anything_else`).

Collected data lives on the `Agent`: `pharmacy_name`, `city`, `volume`,
`email` (each from the API record or the caller), `caller_notes`
(quotable things the caller said), `last_topic` (what a follow-up email
should cover, e.g. the exact out-of-scope question), and `pending_tool`
(a tool requested before we knew the pharmacy's name).

Dispatch order in `Agent.handle()` is the core correctness mechanism:

1. goodbye → close;
2. a pending value slot consumes plain statements (so "Call me tomorrow
   at 10" is a *time*, not a new callback request);
3. explicit tool requests — directed wording ("email **me**", "could you
   call **us**"), or a bare "email"/"callback" only while awaiting
   `followup_choice`;
4. the agent's own identity ("who is this?") — the one direct answer;
5. any other question → safe fallback;
6. choice-slot handling; then a generic funnel line.

## 5. Architecture

Five stdlib-only modules, one file each (see README for the map):
`main.py` (I/O loop) → `agent.py` (state machine) → `api.py` (data),
`tools.py` (actions), `knowledge.py` (grounding boundary). `tests.py`
covers the API client, parsers, and conversation behavior (27 tests).
No frameworks: the exercise is conversation design, and a visible,
auditable state machine demonstrates it better than a dependency would.

## 6. API and tool integration

`api.py` fetches `GET /pharmacies` once per process (10s timeout, any
failure → empty list → unknown-caller flow). Live-data quirks handled:

- **Two record shapes**: seed records carry `prescriptions: [{drug,
  count}]` (volume = sum); newer records carry flat `rxVolume`.
  `rx_volume()` reads both, returns `None` when neither exists.
- **Phone normalization**: digits only, leading US "1" dropped, minimum
  7 digits to match — so `555 123 4567` finds `+1-555-123-4567` and the
  `+1-555-NEW-LEAD-TEST` junk records can never match anything.
- **Null names**: treated as unknown callers.

`tools.py` mocks the two actions as prints. The agent supplies real
context: the email tool gets a topic (default, or the caller's exact
unanswered question), the callback tool gets the extracted time phrase.
In production these become CRM/ticket writes with idempotency keys.

## 7. LLM strategy

This implementation is deliberately LLM-free: intent detection is
keyword- and pattern-based, and every agent utterance is a template over
grounded values. That makes the no-hallucination property *structural* —
there is no component capable of inventing a fact.

The upgrade path keeps that property: an LLM would replace the *ears*,
not the *mouth*. Caller utterances would go to a small model returning
structured output (intent enum + slot values, JSON-schema constrained);
the state machine remains the sole authority on state transitions, tool
execution, and which template is spoken. Response wording could later be
LLM-paraphrased from template output with a post-check that no entities
or numbers were added. Guardrails stay deterministic in both steps.

## 8. Hallucination guardrails

Three allowed sources: the API record, the caller's own words, and
`knowledge.py`. Because the task supplies no approved product facts,
`knowledge.py` deliberately contains none — so pricing, integration,
onboarding, feature, and results questions all route to one fallback
line that offers the two tools. The pitch grounds itself only in
collected data ("At about 2,500 prescriptions a month, Sunrise Pharmacy
is a high-volume operation…"). Earlier iterations shipped invented
placeholder facts ($299 pricing, a 30% stat); they were removed because
a running agent presenting invented numbers as true is exactly the
failure the no-hallucination requirement describes.

Guardrail edge: tool intents are state-aware, so "Do you send email
reminders?" is a capability question (fallback), while "email me the
details" or "can you email me?" is a directed request (tool). Directed
patterns require the me/us object; question forms qualify only when they
start with a request modal (can/could/would/will/please).

## 9. Failure handling

- API unreachable / non-list payload → empty list, one console note, unknown-caller flow.
- Unparseable volume → one polite reprompt, then proceed with volume unknown; explicit refusals accepted immediately.
- Identity denial → apologize, drop all record data, re-collect.
- Blank input → re-ask the pending question; EOF/Ctrl-C → treated as goodbye, clean exit.
- Tool requests before the name is known → `pending_tool`, collect name first, then run the tool.

## 10. Privacy and security

Held data is business-contact PII (pharmacy name, phone, email, volume),
kept in process memory only and printed only as part of the call itself;
nothing is persisted. No secrets exist in the repo (the mock API is
public). For production: verify caller identity before reading account
data aloud (caller-ID is spoofable), encrypt transcripts at rest, apply
retention limits and access control to caller notes, redact PII from
logs, and treat all caller input as untrusted when it reaches real
email/CRM systems (escaping, allow-listed recipients, rate limits).

## 11. Observability

Today: transcripts are the observable, plus `[TOOL CALLED]` markers and
the API-outage notice. The state machine gives natural structured-log
points — every `handle()` could emit `(state, awaiting, intent_matched,
tool_fired)`. The metrics that matter: fallback rate (grounding pressure
gauge), tool conversion rate, identification hit rate, and unparsed-slot
rate. Evaluation: replay a corpus of scripted calls (the `tests.py`
conversations are the seed) and fail CI on any grounding violation —
i.e. an agent line containing a number or entity not traceable to the
three sources.

## 12. Tradeoffs

- **Keyword intents vs. an LLM**: chosen for determinism and zero
  dependencies; the cost is brittleness to paraphrase ("ring the shop
  Thursday" won't parse). §7 is the mitigation path.
- **Statement-first slot filling**: makes "Call me tomorrow at 10" work
  while a time is pending, at the cost of occasionally capturing an odd
  slot value ("schedule a callback" as a time). Chosen because a wrong
  slot value is recoverable in-conversation; a double-fired tool is not.
- **No claims at all vs. labeled placeholder claims**: honesty over
  demo-flash. The transcript sells the *process* (grounded pitch +
  specialist funnel) instead of invented numbers.
- **Single-process, fetch-once**: right for a demo; production needs
  caching with TTL and retries.

## 13. Rollout plan

1. **Shadow**: run the agent against recorded/live call text with tools
   stubbed; measure fallback rate and grounding violations (target: 0).
2. **Assisted**: agent drafts replies and tool calls; a human approves
   each send/schedule. Approval edits become evaluation data.
3. **Autonomous within rails**: agent speaks and fires tools itself for
   the narrow flows proven in shadow; anything off-script transfers to a
   human. Expand scope only as approved knowledge is added to
   `knowledge.py` with an owner and a review date per fact.

## 14. Open questions

- What product facts *are* approved, and who owns keeping them current?
- Is caller-ID identification acceptable before quoting account data
  (Rx volume) aloud, or is a verification step required first?
- Where do tool actions land in production (CRM, ticketing, calendar),
  and what are the idempotency/retry semantics there?
- Should volume tiers be finer than one threshold (e.g. 0–500 /
  500–1,500 / 1,500+), and does the specialist team want the raw pain
  -point quote or a category?
