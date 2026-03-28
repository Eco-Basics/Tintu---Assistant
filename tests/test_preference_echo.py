import pytest


def test_preference_echo_format():
    """Echo must be natural language, not 'Preference saved:' (raw key/value)."""
    source = "be more direct"
    # Placeholder: will be implemented in Plan 04 (router.py wiring)
    pytest.fail("not implemented — router.py update_preference echo not yet wired")


def test_preference_echo_prefix():
    """Echo string must start with 'Saved: '."""
    source = "be more direct"
    # Placeholder: will be implemented in Plan 04 (router.py wiring)
    pytest.fail("not implemented — router.py update_preference not yet wired")
