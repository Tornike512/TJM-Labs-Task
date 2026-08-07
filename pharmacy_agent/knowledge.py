"""Grounding boundary for the agent.

Deliberate design decision: the task prompt supplies no approved product
knowledge for TJM Labs, so this file contains NO product, pricing,
onboarding, integration, or performance claims - and therefore the agent
cannot state any. Questions on those topics get FALLBACK, which routes the
caller to a human specialist via the email / callback tools. The only
things the agent claims about itself are the company name and a
placeholder rep persona.
"""

COMPANY = "TJM Labs"
REP_NAME = "Alex"

FALLBACK = (
    "I don't have that information on hand - I can send you the details by "
    "email or schedule a callback with a specialist. Which works better?"
)

HIGH_VOLUME_THRESHOLD = 1000
