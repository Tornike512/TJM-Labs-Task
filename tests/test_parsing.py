"""Tests for the volume and callback-time parsers."""

import unittest

from pharmacy_agent.agent import _extract_time, _parse_volume


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
