"""Shared fixtures for the IoTaWatt fork tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow the custom integration to load in tests."""
    return
