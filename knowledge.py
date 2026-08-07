"""The ONLY facts about TJM Labs the agent may state.

All company facts below are invented placeholders for this take-home
(flagged in the README). The agent is allowed to speak from exactly three
sources: the pharmacy API record, what the caller said, and this file.
Everything else gets FALLBACK.
"""

COMPANY = "TJM Labs"
REP_NAME = "Alex"

FACTS = {
    "what_we_do": (
        "TJM Labs makes a pharmacy operations platform that automates refill "
        "reminders, inventory forecasting, and insurance pre-checks."
    ),
    "pricing": (
        "Pricing starts at $299 per month per location, with volume discounts "
        "above 1,000 monthly prescriptions."
    ),
    "onboarding": (
        "Onboarding takes about two weeks and includes free data migration "
        "from your current system."
    ),
    "results": (
        "Pharmacies using TJM Labs report roughly 30% less time spent on "
        "manual insurance paperwork."
    ),
}

FALLBACK = (
    "I don't have that information on hand - I can send you the details by "
    "email or schedule a callback with a specialist. Which works better?"
)

# Monthly scripts. Live data clusters at 0 / 55-100 / 3000-4000, so 1000
# cleanly separates the high-volume pharmacies.
HIGH_VOLUME_THRESHOLD = 1000
