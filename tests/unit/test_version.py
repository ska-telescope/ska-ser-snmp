"""This module tests the ska_low_itf_devices version."""

import ska_low_itf_devices


def test_version() -> None:
    """Test that the ska_low_itf_devices version is as expected."""
    assert ska_low_itf_devices.__version__ == "0.0.1"
