# Inbound Pharmacy Sales Agent

A pharmacy calls TJM Labs. The program looks up the caller by phone number
in the pharmacy API, greets known pharmacies by name, and runs a short text
conversation that can end with a mock follow-up email or a mock specialist
callback. The implementation is deliberately small and deterministic.

## Run

```
python main.py
python main.py --phone "+1-555-000-9999"
python -m unittest
```

The first command calls in from a known API number (HealthFirst Pharmacy);
the second exercises the unknown-caller path. You type the pharmacy's side
of the call; `bye` hangs up. Python 3.9+, standard library only.

## What it does

- Phone-normalized lookup against the supplied pharmacy API.
- Separate flows for known and unknown callers.
- Collects the pharmacy name and monthly prescription volume when missing.
- Treats pharmacies above 1,000 prescriptions per month as high-volume and tailors the close.
- Answers unsupported questions with a safe fallback that offers email or a specialist callback.
- Mock email and callback actions, printed as `[TOOL CALLED]` lines.

## Example

Unknown caller, high volume, out-of-scope question:

```
Agent: Thanks for calling TJM Labs, this is Alex.
Agent: Could I get your pharmacy's name?
You: Sunrise Pharmacy
Agent: Nice to meet you, Sunrise Pharmacy! Roughly how many prescriptions do you fill in a month?
You: two thousand
...
Agent: At about 2,000 prescriptions a month, Sunrise Pharmacy is a high-volume operation - I'll flag that for our specialist so the follow-up is tailored to your scale.
...
You: Do you integrate with PioneerRx?
Agent: I don't have that information on hand - I can send you the details by email or schedule a callback with a specialist. Which works better?
You: callback
Agent: Absolutely - when's a good time for one of our specialists to call Sunrise Pharmacy?
You: Call me tomorrow at 10
[TOOL CALLED] Callback scheduled with Sunrise Pharmacy for tomorrow at 10
```

## Project structure

```
pharmacy_agent/
  agent.py
  api.py
  cli.py
  knowledge.py
  tools.py
tests/
main.py
DESIGN.md
```

`main.py` is the entry point; the conversation state machine and all call
state live in `pharmacy_agent/agent.py`. Tests are split by API client,
parsing, and agent behavior.

## Design choices

The call is driven by a deterministic state machine. The exercise permits a
simple text loop, and deterministic output is easy to test: every reply is
a template over three sources, the API record, what the caller said, and a
small knowledge file.

The task supplies no approved TJM Labs product facts, so the agent does not
invent any. Questions about pricing, products, onboarding, results, or
integrations get the safe fallback and are routed to a human specialist by
email or callback instead of receiving made-up answers.

The API client normalizes phone numbers before matching and tolerates both
record shapes in the live data. If the API is unreachable, the program
notes it and continues through the unknown-caller flow.

See [DESIGN.md](DESIGN.md) for the full system design, LLM strategy,
tradeoffs, and production considerations.

## Tests

```
python -m unittest
```

31 tests covering API lookup, parsing, conversation state, safe fallbacks,
and tool calls. No network access is needed except one deliberate
unreachable-host failure test.
