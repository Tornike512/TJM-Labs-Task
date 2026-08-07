"""Conversation logic: a small state machine for the sales call.

States: IDENTIFY -> DISCOVERY -> PITCH -> FOLLOW_UP -> END
"""

import re

import api
import knowledge

IDENTIFY = "IDENTIFY"
DISCOVERY = "DISCOVERY"
PITCH = "PITCH"
FOLLOW_UP = "FOLLOW_UP"
END = "END"

_YES_WORDS = {"yes", "yeah", "yep", "yup", "correct", "right", "speaking", "sure"}
_NO_WORDS = {"no", "nope", "nah", "wrong", "incorrect"}
_QUESTION_STARTERS = {
    "do", "does", "can", "could", "what", "when", "where", "who", "whom",
    "how", "is", "are", "will", "would", "why", "which",
}


def _has_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def _is_question(text):
    stripped = text.strip().lower()
    if stripped.endswith("?"):
        return True
    first = stripped.split()[0] if stripped.split() else ""
    return first in _QUESTION_STARTERS


def _parse_volume(text):
    """Pull a monthly script count out of free text ('about 2,500 a month')."""
    match = re.search(r"\d[\d,]*", text)
    if not match:
        return None
    return int(match.group().replace(",", ""))


class Agent:
    """Holds call state; handle() maps one caller utterance to reply lines."""

    def __init__(self, pharmacy):
        self.state = IDENTIFY
        self.awaiting = None  # sub-question within a state
        self.pharmacy_name = None
        self.city = None
        self.volume = None
        self.caller_notes = []  # things the caller told us, quotable
        self.record = None

        # A record with no usable name is treated as an unknown caller, but we
        # keep whatever fields it does have.
        if pharmacy and pharmacy.get("name"):
            self.record = pharmacy
            self.pharmacy_name = pharmacy["name"]
            self.city = pharmacy.get("city")
            self.volume = api.rx_volume(pharmacy)

    @property
    def done(self):
        return self.state == END

    # ---- openers -----------------------------------------------------------

    def start(self):
        """Opening line(s) of the call."""
        if self.pharmacy_name:
            where = f" in {self.city}" if self.city else ""
            lines = [
                f"Hi, is this {self.pharmacy_name}{where}? This is "
                f"{knowledge.REP_NAME} calling from {knowledge.COMPANY}."
            ]
            if self.volume is not None:
                lines.append(
                    f"I see you're filling around {self.volume:,} scripts a "
                    "month - impressive operation."
                )
            self.awaiting = "confirm_identity"
            return lines
        self.awaiting = "name"
        return [
            f"Hi, this is {knowledge.REP_NAME} calling from "
            f"{knowledge.COMPANY}. Thanks for taking the call!",
            "Could I get your pharmacy's name?",
        ]

    # ---- main dispatch -----------------------------------------------------

    def handle(self, text):
        """Advance the conversation one turn; returns a list of reply lines."""
        cleaned = text.strip()
        if not cleaned:
            return [self._reprompt()]
        lowered = cleaned.lower()

        if self._is_goodbye(lowered):
            return self._close()

        if self.awaiting in ("name", "volume"):
            return self._fill_slot(cleaned, lowered)

        if self.awaiting == "confirm_identity":
            return self._confirm_identity(lowered)

        return [self._reprompt()]

    # ---- identification ----------------------------------------------------

    def _confirm_identity(self, lowered):
        words = set(re.findall(r"[a-z']+", lowered))
        if words & _NO_WORDS:
            self.record = None
            self.pharmacy_name = None
            self.city = None
            self.volume = None
            self.awaiting = "name"
            return [
                "Apologies for the mix-up! Could I get your pharmacy's name?"
            ]
        # Anything that isn't a denial we take as confirmation.
        if self.volume is None:
            self.awaiting = "volume"
            return [
                f"Great, thanks! And roughly how many prescriptions does "
                f"{self.pharmacy_name} fill in a month?"
            ]
        return self._begin_discovery()

    def _fill_slot(self, cleaned, lowered):
        if self.awaiting == "name":
            self.pharmacy_name = cleaned
            self.awaiting = "volume"
            return [
                f"Nice to meet you, {self.pharmacy_name}! Roughly how many "
                "prescriptions do you fill in a month?"
            ]
        # awaiting == "volume"
        volume = _parse_volume(cleaned)
        if volume is not None:
            self.volume = volume
            self.caller_notes.append(f"fills about {volume:,} scripts a month")
        return self._begin_discovery()

    def _begin_discovery(self):
        self.state = DISCOVERY
        self.awaiting = "pain_point"
        return [
            f"Thanks! Quick question so I don't waste your time, "
            f"{self.pharmacy_name}: what eats up most of your team's day "
            "right now - refills, inventory, or insurance paperwork?"
        ]

    # ---- helpers -----------------------------------------------------------

    def _is_goodbye(self, lowered):
        return _has_any(
            lowered,
            ["bye", "goodbye", "quit", "exit", "hang up", "gotta go",
             "not interested"],
        )

    def _close(self):
        self.state = END
        name = self.pharmacy_name or "you"
        return [
            f"Thanks for your time, {name}. Have a great day!"
        ]

    def _reprompt(self):
        prompts = {
            "confirm_identity": "Sorry, is this " + str(self.pharmacy_name) + "?",
            "name": "Could I get your pharmacy's name?",
            "volume": "Roughly how many prescriptions do you fill in a month?",
            "pain_point": (
                "What eats up most of your team's day - refills, inventory, "
                "or insurance paperwork?"
            ),
        }
        return prompts.get(self.awaiting, "Sorry, could you say that again?")
