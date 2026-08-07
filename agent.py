"""Conversation logic: a small state machine for the inbound sales call.

States: IDENTIFY -> DISCOVERY -> PITCH -> FOLLOW_UP -> END

Anti-hallucination rule: the agent only ever states facts from three
sources - the pharmacy's API record, what the caller said on this call,
and knowledge.py. knowledge.py deliberately contains no product, pricing,
or performance claims (none were supplied), so every company-specific
question gets knowledge.FALLBACK, which funnels the caller toward the
follow-up tools and a human specialist.
"""

import re

import api
import knowledge
import tools

IDENTIFY = "IDENTIFY"
DISCOVERY = "DISCOVERY"
PITCH = "PITCH"
FOLLOW_UP = "FOLLOW_UP"
END = "END"

_YES_WORDS = {"yes", "yeah", "yep", "yup", "correct", "right", "speaking",
              "sure", "ok", "okay", "please"}
_NO_WORDS = {"no", "nope", "nah", "wrong", "incorrect"}
_NEGATIVE_PHRASES = ["that's all", "thats all", "that's it", "nothing else",
                     "all set", "we're good", "i'm good", "im good",
                     "no thanks", "no thank you", "not right now", "not sure"]
_GOODBYE_WORDS = {"bye", "goodbye", "quit", "exit"}
_GOODBYE_PHRASES = ["hang up", "gotta go", "have to go", "not interested"]
_QUESTION_STARTERS = {
    "do", "does", "can", "could", "what", "when", "where", "who", "whom",
    "how", "is", "are", "will", "would", "why", "which",
}

_EMAIL_PHRASES = ["email", "e-mail", "send me", "send the", "send it",
                  "send info", "send details", "send over", "mail me"]
_CALLBACK_PHRASES = ["call back", "callback", "call me", "ring me",
                     "call later", "phone me", "call us"]

# The agent's own identity is the one question it can answer directly.
_IDENTITY_TRIGGERS = ["who is this", "who's this", "who am i speaking",
                      "who are you", "who's calling", "who is calling"]

# Slots whose answer is a free-text value (vs. a yes/no/choice).
_VALUE_SLOTS = {"name", "volume", "pain_point", "callback_time",
                "email_address"}


def _has_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def _words(text):
    return set(re.findall(r"[a-z']+", text))


def _is_question(text):
    stripped = text.strip().lower()
    if stripped.endswith("?"):
        return True
    parts = stripped.split()
    return bool(parts) and parts[0] in _QUESTION_STARTERS


def _is_negative(lowered):
    return bool(_words(lowered) & _NO_WORDS) or _has_any(lowered,
                                                         _NEGATIVE_PHRASES)


def _is_positive(lowered):
    return bool(_words(lowered) & _YES_WORDS)


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
        self.awaiting = None  # sub-question we asked last
        self.pharmacy_name = None
        self.city = None
        self.volume = None
        self.email = None
        self.caller_notes = []  # things the caller told us, quotable
        self.last_topic = "TJM Labs details"  # for the follow-up email
        self.pending_tool = None  # tool requested before we knew the name
        self.record = None

        # A record with no usable name is treated as an unknown caller, but
        # we keep whatever fields it does have.
        if pharmacy and pharmacy.get("name"):
            self.record = pharmacy
            self.pharmacy_name = pharmacy["name"]
            self.city = pharmacy.get("city")
            self.volume = api.rx_volume(pharmacy)
            self.email = pharmacy.get("email")

    @property
    def done(self):
        return self.state == END

    # ---- openers -----------------------------------------------------------

    def start(self):
        """Opening line(s) of the call - the pharmacy is calling us."""
        if self.pharmacy_name:
            where = f" in {self.city}" if self.city else ""
            lines = [
                f"Thanks for calling {knowledge.COMPANY}, this is "
                f"{knowledge.REP_NAME}. Am I speaking with "
                f"{self.pharmacy_name}{where}?"
            ]
            if self.volume is not None:
                lines.append(
                    f"I see you're filling around {self.volume:,} scripts a "
                    "month."
                )
            self.awaiting = "confirm_identity"
            return lines
        self.awaiting = "name"
        return [
            f"Thanks for calling {knowledge.COMPANY}, this is "
            f"{knowledge.REP_NAME}.",
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

        if _has_any(lowered, _EMAIL_PHRASES):
            return self._request_tool("email")
        if _has_any(lowered, _CALLBACK_PHRASES):
            return self._request_tool("callback")

        question = _is_question(lowered)

        # A statement while we're waiting on a value answers that question.
        if self.awaiting in _VALUE_SLOTS and not question:
            return self._fill_slot(cleaned, lowered)

        if _has_any(lowered, _IDENTITY_TRIGGERS):
            lines = [f"This is {knowledge.REP_NAME} with {knowledge.COMPANY}."]
            reprompt = self._reprompt()
            if reprompt:
                lines.append(reprompt)
            return lines

        # A question we can't answer from our three sources -> safe fallback.
        if question:
            return self._fallback(cleaned)

        if self.awaiting == "confirm_identity":
            return self._confirm_identity(lowered)
        if self.awaiting == "followup_choice":
            return self._followup_choice(lowered)
        if self.awaiting == "anything_else":
            return self._anything_else(lowered)

        return [
            "Happy to help - I can send you details by email or schedule a "
            "callback with a specialist. Which works better?"
        ]

    # ---- identification ----------------------------------------------------

    def _confirm_identity(self, lowered):
        if _is_negative(lowered):
            self.record = None
            self.pharmacy_name = None
            self.city = None
            self.volume = None
            self.email = None
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

    # ---- value slots -------------------------------------------------------

    def _fill_slot(self, cleaned, lowered):
        slot = self.awaiting
        if slot == "name":
            self.pharmacy_name = cleaned
            if self.pending_tool:
                kind, self.pending_tool = self.pending_tool, None
                thanks = f"Thanks, {self.pharmacy_name}!"
                if kind == "email":
                    return [thanks] + self._start_email()
                return [thanks] + self._start_callback()
            self.awaiting = "volume"
            return [
                f"Nice to meet you, {self.pharmacy_name}! Roughly how many "
                "prescriptions do you fill in a month?"
            ]

        if slot == "volume":
            volume = _parse_volume(cleaned)
            if volume is not None:
                self.volume = volume
                self.caller_notes.append(
                    f"fills about {volume:,} scripts a month")
            return self._begin_discovery()

        if slot == "pain_point":
            self.caller_notes.append(f"biggest time sink: {cleaned}")
            return self._deliver_pitch(lowered)

        if slot == "callback_time":
            self.awaiting = "anything_else"
            tools.schedule_callback(self.pharmacy_name, cleaned)
            return [
                f"You're all set - a specialist will call "
                f"{self.pharmacy_name} {cleaned}. Anything else I can help "
                "with?"
            ]

        if slot == "email_address":
            self.email = cleaned
            self.awaiting = "anything_else"
            tools.send_follow_up_email(self.pharmacy_name, self.last_topic)
            return [
                f"Done - I've queued an email to {self.email} about "
                f"{self.last_topic}. Anything else I can help with?"
            ]

        return [self._reprompt()]

    # ---- discovery + pitch -------------------------------------------------

    def _begin_discovery(self):
        self.state = DISCOVERY
        self.awaiting = "pain_point"
        return [
            f"Thanks! Quick question so I don't waste your time, "
            f"{self.pharmacy_name}: what eats up most of your team's day "
            "right now - refills, inventory, or insurance paperwork?"
        ]

    def _deliver_pitch(self, lowered):
        """PITCH: acknowledge their pain point, grounded only in what the
        caller and the API told us - no product or pricing claims."""
        self.state = PITCH
        if "insurance" in lowered or "paperwork" in lowered:
            ack = "Insurance paperwork - understood."
        elif "refill" in lowered:
            ack = "Refills - got it."
        elif "inventory" in lowered or "stock" in lowered:
            ack = "Inventory - understood."
        else:
            ack = "Got it - thanks for sharing that."

        lines = [ack]
        if self.volume is not None and \
                self.volume >= knowledge.HIGH_VOLUME_THRESHOLD:
            lines.append(
                f"At about {self.volume:,} prescriptions a month, "
                f"{self.pharmacy_name} is a high-volume operation - I'll "
                "flag that for our specialist so the follow-up is tailored "
                "to your scale."
            )
        elif self.volume is not None:
            lines.append(
                f"I'll make sure our specialist knows {self.pharmacy_name} "
                f"fills about {self.volume:,} scripts a month and what you "
                "just told me, so the follow-up fits your operation."
            )
        else:
            lines.append(
                f"I'll pass your notes along so the follow-up is relevant "
                f"to {self.pharmacy_name}."
            )

        self.state = FOLLOW_UP
        self.awaiting = "followup_choice"
        lines.append(
            "For specifics - pricing, product details - our specialist team "
            "is the right source. Would details by email or a specialist "
            "callback work better for you?"
        )
        return lines

    # ---- follow-up ---------------------------------------------------------

    def _request_tool(self, kind):
        if not self.pharmacy_name:
            self.pending_tool = kind
            self.awaiting = "name"
            return ["Happy to - could I get your pharmacy's name first?"]
        if kind == "email":
            return self._start_email()
        return self._start_callback()

    def _start_email(self):
        self.state = FOLLOW_UP
        if self.email:
            self.awaiting = "anything_else"
            tools.send_follow_up_email(self.pharmacy_name, self.last_topic)
            return [
                f"Done - I've queued an email to {self.email} about "
                f"{self.last_topic}. Anything else I can help with?"
            ]
        self.awaiting = "email_address"
        return [
            f"Of course - what's the best email address for "
            f"{self.pharmacy_name}?"
        ]

    def _start_callback(self):
        self.state = FOLLOW_UP
        self.awaiting = "callback_time"
        return [
            f"Absolutely - when's a good time for one of our specialists to "
            f"call {self.pharmacy_name}?"
        ]

    def _followup_choice(self, lowered):
        if _is_negative(lowered):
            self.awaiting = "anything_else"
            return ["No problem at all. Anything else I can help with?"]
        if _is_positive(lowered):
            return [
                "Great - would you prefer the details by email, or a "
                "callback from a specialist?"
            ]
        return [self._reprompt()]

    def _anything_else(self, lowered):
        if _is_negative(lowered):
            return self._close()
        if _is_positive(lowered):
            self.awaiting = "followup_choice"
            return [
                "Sure - I can send you details by email or set up a "
                "specialist callback. Which works better?"
            ]
        return [self._reprompt()]

    # ---- fallback + closing ------------------------------------------------

    def _fallback(self, cleaned):
        """The one safe answer for anything outside our three sources."""
        self.last_topic = f'your question "{cleaned[:80]}"'
        self.state = FOLLOW_UP
        self.awaiting = "followup_choice"
        return [knowledge.FALLBACK]

    def _is_goodbye(self, lowered):
        return bool(_words(lowered) & _GOODBYE_WORDS) or \
            _has_any(lowered, _GOODBYE_PHRASES)

    def _close(self):
        self.state = END
        name = self.pharmacy_name or "you"
        return [f"Thanks for calling, {name}. Have a great day!"]

    def _reprompt(self):
        prompts = {
            "confirm_identity": f"Sorry, is this {self.pharmacy_name}?",
            "name": "Could I get your pharmacy's name?",
            "volume": "Roughly how many prescriptions do you fill in a month?",
            "pain_point": (
                "What eats up most of your team's day - refills, inventory, "
                "or insurance paperwork?"
            ),
            "followup_choice": (
                "Would you prefer the details by email, or a callback from a "
                "specialist?"
            ),
            "callback_time": "When's a good time for the callback?",
            "email_address": "What's the best email address for you?",
            "anything_else": "Anything else I can help with?",
        }
        return prompts.get(self.awaiting,
                           "Sorry, could you say that again?")
