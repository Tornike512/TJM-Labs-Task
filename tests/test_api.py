"""API client tests. One test points at an unreachable host to prove the
failure path degrades gracefully; everything else runs offline."""

import unittest

from pharmacy_agent import api

from tests.fixtures import FIXTURES, FLAT, KNOWN, NULL_NAME


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
