"""Fetch and search the pharmacy list from the mock API."""

import json
import urllib.request

DEFAULT_API_URL = "https://67e14fb758cc6bf785254550.mockapi.io/pharmacies"

# Some records carry junk phones like "+1-555-NEW-LEAD-TEST" that normalize to
# almost nothing; requiring a minimum digit count keeps them from matching.
_MIN_MATCH_DIGITS = 7


def get_pharmacies(api_url=DEFAULT_API_URL):
    """Fetch all pharmacies once. Returns [] if the API is unreachable."""
    try:
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.load(resp)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def normalize_phone(raw):
    """Digits only, US country code dropped: '+1 555-123-4567' -> '5551234567'."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def find_by_phone(pharmacies, number):
    """Return the pharmacy whose phone matches `number`, else None."""
    target = normalize_phone(number)
    if len(target) < _MIN_MATCH_DIGITS:
        return None
    for pharmacy in pharmacies:
        if normalize_phone(pharmacy.get("phone")) == target:
            return pharmacy
    return None


def rx_volume(pharmacy):
    """Monthly Rx volume, tolerant of both record shapes in the API.

    Older records list prescriptions as [{drug, count}, ...]; newer ones have a
    flat rxVolume number. Returns None when the record carries no volume info.
    """
    if not pharmacy:
        return None
    flat = pharmacy.get("rxVolume")
    if isinstance(flat, (int, float)):
        return int(flat)
    scripts = pharmacy.get("prescriptions")
    if isinstance(scripts, list) and scripts:
        total = sum(
            item.get("count", 0)
            for item in scripts
            if isinstance(item, dict) and isinstance(item.get("count"), (int, float))
        )
        return int(total)
    return None
