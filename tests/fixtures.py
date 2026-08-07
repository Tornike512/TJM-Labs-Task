"""Shared pharmacy records and helpers for the test suite."""

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
