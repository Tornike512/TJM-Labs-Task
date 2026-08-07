"""Standard-library tests: python -m unittest  (or: python -m unittest -v tests)

No network access needed except one test that points at an unreachable
host to prove the API failure path degrades gracefully.
"""

import unittest
from unittest.mock import patch

import api
import knowledge
from agent import Agent, _extract_time, _parse_volume

KNOWN = {
    "id": 1,
    "name": "HealthFirst Pharmacy",
    "phone": "+1-555-123-4567",
    "email": "contact@healthfirst.com",
    "city": "New York",
    "state": "NY",
    "prescriptions": [{"drug": "Lisinopril", "count": 60},
                      {"drug": "Metformin", "count": 40}],
}
FLAT = {"id": "6", "name": "Test New Pharmacy",
        "phone": "+1-555-NEW-LEAD-TEST", "rxVolume": 4000}
NULL_NAME = {"id": "19", "name": None, "phone": "+1-555-509-7008"}
FIXTURES = [KNOWN, FLAT, NULL_NAME]


def flat_text(lines):
    return " ".join(lines)


class ApiTests(unittest.TestCase):
    def test_normalize_phone_variants(self):
        for raw in ("+1 555-123-4567", "555 123 4567", "(555) 123-4567",
                    "1-555-123-4567"):
            self.assertEqual(api.normalize_phone(raw), "5551234567")

    def test_find_by_phone_matches_loosely_formatted_number(self):
        self.assertIs(api.find_by_phone(FIXTURES, "555.123.4567"), KNOWN)

    def test_find_by_phone_unknown_returns_none(self):
        self.assertIsNone(api.find_by_phone(FIXTURES, "999-999-9999"))

    def test_letter_phone_junk_never_matches(self):
        self.assertIsNone(api.find_by_phone(FIXTURES, "+1-555-NEW-LEAD-TEST"))

    def test_rx_volume_sums_prescriptions(self):
        self.assertEqual(api.rx_volume(KNOWN), 100)

    def test_rx_volume_reads_flat_field(self):
        self.assertEqual(api.rx_volume(FLAT), 4000)

    def test_rx_volume_missing_is_none(self):
        self.assertIsNone(api.rx_volume(NULL_NAME))

    def test_unreachable_api_returns_empty_list(self):
        self.assertEqual(api.get_pharmacies("https://invalid.invalid/x"), [])


class ParsingTests(unittest.TestCase):
    def test_parse_volume_digit_forms(self):
        self.assertEqual(_parse_volume("2500"), 2500)
        self.assertEqual(_parse_volume("2,500"), 2500)
        self.assertEqual(_parse_volume("about 2,500 a month"), 2500)

    def test_parse_volume_word_forms(self):
        self.assertEqual(_parse_volume("two thousand"), 2000)
        self.assertEqual(_parse_volume("around twenty five hundred"), 2500)
        self.assertEqual(_parse_volume("a thousand or so"), 1000)

    def test_parse_volume_rejects_non_quantities(self):
        self.assertIsNone(_parse_volume("honestly it varies"))
        self.assertIsNone(_parse_volume("thousands of reasons"))

    def test_extract_time_strips_request_verb(self):
        self.assertEqual(_extract_time("Call me tomorrow at 10"),
                         "tomorrow at 10")
        self.assertEqual(_extract_time("Tomorrow at 10 am"),
                         "Tomorrow at 10 am")


class ConversationTests(unittest.TestCase):
    def _pitched_agent(self):
        """Known caller advanced through discovery to the follow-up choice."""
        a = Agent(KNOWN)
        a.start()
        a.handle("yes")
        a.handle("insurance paperwork")
        return a

    def test_known_greeting_is_inbound_with_name_city_volume(self):
        opening = flat_text(Agent(KNOWN).start())
        self.assertIn("Thanks for calling TJM Labs", opening)
        self.assertIn("HealthFirst Pharmacy", opening)
        self.assertIn("New York", opening)
        self.assertIn("100", opening)
        self.assertNotIn("calling from", opening)

    def test_null_name_record_treated_as_unknown(self):
        opening = flat_text(Agent(NULL_NAME).start())
        self.assertIn("Could I get your pharmacy's name?", opening)
        self.assertNotIn("None", opening)

    def test_unknown_high_volume_pitch_is_grounded(self):
        a = Agent(None)
        a.start()
        a.handle("Sunrise Pharmacy")
        a.handle("We fill about 2,500 a month")
        pitch = flat_text(a.handle("inventory mostly"))
        self.assertIn("Sunrise Pharmacy", pitch)
        self.assertIn("high-volume operation", pitch)
        self.assertIn("2,500", pitch)
        # No invented pricing/percentage claims anywhere in the pitch.
        self.assertNotIn("$", pitch)
        self.assertNotIn("%", pitch)

    def test_out_of_scope_question_gets_safe_fallback(self):
        a = self._pitched_agent()
        reply = a.handle("Do you integrate with PioneerRx?")
        self.assertEqual(reply, [knowledge.FALLBACK])

    def test_email_capability_question_does_not_fire_tool(self):
        with patch("tools.send_follow_up_email") as em:
            a = self._pitched_agent()
            reply = a.handle("Do you send email reminders?")
        self.assertEqual(reply, [knowledge.FALLBACK])
        em.assert_not_called()

    def test_callback_capability_question_does_not_fire_tool(self):
        with patch("tools.schedule_callback") as cb:
            a = self._pitched_agent()
            reply = a.handle("Do you call us back if we leave a message?")
        self.assertEqual(reply, [knowledge.FALLBACK])
        cb.assert_not_called()

    def test_callback_choice_then_time_fires_tool_exactly_once(self):
        with patch("tools.schedule_callback") as cb:
            a = self._pitched_agent()
            a.handle("A callback works")
            self.assertEqual(cb.call_count, 0)  # still collecting the time
            reply = flat_text(a.handle("Call me tomorrow at 10"))
        cb.assert_called_once_with("HealthFirst Pharmacy", "tomorrow at 10")
        self.assertIn("tomorrow at 10", reply)

    def test_explicit_email_request_fires_tool_once(self):
        with patch("tools.send_follow_up_email") as em:
            a = self._pitched_agent()
            reply = flat_text(a.handle("Email me the details"))
        em.assert_called_once()
        self.assertIn("contact@healthfirst.com", reply)

    def test_polite_question_form_request_still_fires_tool(self):
        with patch("tools.send_follow_up_email") as em:
            a = self._pitched_agent()
            a.handle("Can you email me the details?")
        em.assert_called_once()

    def test_unparseable_volume_reprompts_then_moves_on(self):
        a = Agent(None)
        a.start()
        a.handle("Riverside Drugs")
        reply = flat_text(a.handle("hmm let me think"))
        self.assertIn("ballpark", reply)
        reply = flat_text(a.handle("it really varies"))
        self.assertIn("refills, inventory, or insurance paperwork", reply)
        self.assertIsNone(a.volume)

    def test_volume_refusal_continues_gracefully(self):
        a = Agent(None)
        a.start()
        a.handle("Riverside Drugs")
        reply = flat_text(a.handle("I'd rather not say"))
        self.assertIn("No problem", reply)
        self.assertIn("refills, inventory, or insurance paperwork", reply)
        self.assertIsNone(a.volume)

    def test_word_form_volume_is_parsed(self):
        a = Agent(None)
        a.start()
        a.handle("Riverside Drugs")
        a.handle("around two thousand a month")
        self.assertEqual(a.volume, 2000)

    def test_tool_request_while_awaiting_name_is_not_stored_as_name(self):
        with patch("tools.send_follow_up_email") as em:
            a = Agent(None)
            a.start()
            reply = flat_text(a.handle("Email me the details"))
            self.assertIsNone(a.pharmacy_name)  # never stored as the name
            self.assertEqual(a.pending_tool, "email")
            self.assertIn("name", reply)  # re-asks for the pharmacy name
            em.assert_not_called()
            reply = flat_text(a.handle("Sunrise Pharmacy"))
            self.assertEqual(a.pharmacy_name, "Sunrise Pharmacy")
            self.assertIn("email address", reply)  # email flow resumed
            em.assert_not_called()  # still waiting on the address
            a.handle("desk@sunrisepharmacy.com")
        em.assert_called_once()

    def test_callback_request_while_awaiting_name_parks_pending_tool(self):
        for request in ("Call me back", "Schedule a callback"):
            a = Agent(None)
            a.start()
            a.handle(request)
            self.assertIsNone(a.pharmacy_name)
            self.assertEqual(a.pending_tool, "callback")
            reply = flat_text(a.handle("Lakeside Pharmacy"))
            self.assertEqual(a.pharmacy_name, "Lakeside Pharmacy")
            self.assertIn("when's a good time", reply.lower())

    def test_callback_time_refusal_does_not_schedule(self):
        with patch("tools.schedule_callback") as cb:
            a = self._pitched_agent()
            a.handle("A callback works")
            reply = flat_text(a.handle("not sure"))
            cb.assert_not_called()
        self.assertIn("No problem", reply)  # refusal acknowledged
        self.assertEqual(a.awaiting, "followup_choice")
        with patch("tools.send_follow_up_email") as em:
            a.handle("email")  # email is still on offer afterwards
        em.assert_called_once()

    def test_callback_time_refusal_then_no_thanks_reaches_close(self):
        with patch("tools.schedule_callback") as cb:
            a = self._pitched_agent()
            a.handle("A callback works")
            a.handle("never mind")
            a.handle("no thanks")  # declines the email-instead offer
            a.handle("no")  # nothing else -> polite close
            cb.assert_not_called()
        self.assertTrue(a.done)

    def test_identity_denial_recollects_name(self):
        a = Agent(KNOWN)
        a.start()
        reply = flat_text(a.handle("No, this is Lakeside Pharmacy"))
        self.assertIn("Could I get your pharmacy's name?", reply)
        a.handle("Lakeside Pharmacy")
        self.assertEqual(a.pharmacy_name, "Lakeside Pharmacy")

    def test_blank_input_reprompts(self):
        a = Agent(KNOWN)
        a.start()
        reply = flat_text(a.handle("   "))
        self.assertIn("HealthFirst Pharmacy", reply)
        self.assertFalse(a.done)

    def test_bye_and_not_interested_close_politely(self):
        for farewell in ("bye", "Not interested, thanks"):
            a = Agent(KNOWN)
            a.start()
            reply = flat_text(a.handle(farewell))
            self.assertTrue(a.done)
            self.assertIn("Thanks for calling", reply)


if __name__ == "__main__":
    unittest.main()
