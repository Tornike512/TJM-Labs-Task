"""Conversation-behavior tests for the Agent state machine."""

import unittest
from unittest.mock import patch

from pharmacy_agent import knowledge
from pharmacy_agent.agent import Agent

from tests.fixtures import KNOWN, NULL_NAME, flat_text


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
        self.assertNotIn("$", pitch)
        self.assertNotIn("%", pitch)

    def test_out_of_scope_question_gets_safe_fallback(self):
        a = self._pitched_agent()
        reply = a.handle("Do you integrate with PioneerRx?")
        self.assertEqual(reply, [knowledge.FALLBACK])

    def test_email_capability_question_does_not_fire_tool(self):
        with patch("pharmacy_agent.tools.send_follow_up_email") as em:
            a = self._pitched_agent()
            reply = a.handle("Do you send email reminders?")
        self.assertEqual(reply, [knowledge.FALLBACK])
        em.assert_not_called()

    def test_callback_capability_question_does_not_fire_tool(self):
        with patch("pharmacy_agent.tools.schedule_callback") as cb:
            a = self._pitched_agent()
            reply = a.handle("Do you call us back if we leave a message?")
        self.assertEqual(reply, [knowledge.FALLBACK])
        cb.assert_not_called()

    def test_callback_choice_then_time_fires_tool_exactly_once(self):
        with patch("pharmacy_agent.tools.schedule_callback") as cb:
            a = self._pitched_agent()
            a.handle("A callback works")
            self.assertEqual(cb.call_count, 0)
            reply = flat_text(a.handle("Call me tomorrow at 10"))
        cb.assert_called_once_with("HealthFirst Pharmacy", "tomorrow at 10")
        self.assertIn("tomorrow at 10", reply)

    def test_explicit_email_request_fires_tool_once(self):
        with patch("pharmacy_agent.tools.send_follow_up_email") as em:
            a = self._pitched_agent()
            reply = flat_text(a.handle("Email me the details"))
        em.assert_called_once()
        self.assertIn("contact@healthfirst.com", reply)

    def test_polite_question_form_request_still_fires_tool(self):
        with patch("pharmacy_agent.tools.send_follow_up_email") as em:
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
        with patch("pharmacy_agent.tools.send_follow_up_email") as em:
            a = Agent(None)
            a.start()
            reply = flat_text(a.handle("Email me the details"))
            self.assertIsNone(a.pharmacy_name)
            self.assertEqual(a.pending_tool, "email")
            self.assertIn("name", reply)
            em.assert_not_called()
            reply = flat_text(a.handle("Sunrise Pharmacy"))
            self.assertEqual(a.pharmacy_name, "Sunrise Pharmacy")
            self.assertIn("email address", reply)
            em.assert_not_called()
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
        with patch("pharmacy_agent.tools.schedule_callback") as cb:
            a = self._pitched_agent()
            a.handle("A callback works")
            reply = flat_text(a.handle("not sure"))
            cb.assert_not_called()
        self.assertIn("No problem", reply)
        self.assertEqual(a.awaiting, "followup_choice")
        with patch("pharmacy_agent.tools.send_follow_up_email") as em:
            a.handle("email")
        em.assert_called_once()

    def test_callback_time_refusal_then_no_thanks_reaches_close(self):
        with patch("pharmacy_agent.tools.schedule_callback") as cb:
            a = self._pitched_agent()
            a.handle("A callback works")
            a.handle("never mind")
            a.handle("no thanks")
            a.handle("no")
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
