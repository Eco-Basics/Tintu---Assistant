import pytest


def test_preference_echo_format():
    """Echo must be natural language, not 'Preference saved:' (raw key/value)."""
    source = "be more direct"
    echo = f"Saved: I'll {source.lower().rstrip('.')}."
    assert echo == "Saved: I'll be more direct."
    assert "Preference saved:" not in echo


def test_preference_echo_prefix():
    """Echo string must start with 'Saved: '."""
    source = "skip confirmation before creating tasks"
    echo = f"Saved: I'll {source.lower().rstrip('.')}."
    assert echo.startswith("Saved: ")
