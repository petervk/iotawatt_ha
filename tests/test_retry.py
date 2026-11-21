"""Tests for trying a failed request once more before the poll fails."""

from typing import Any
from unittest.mock import patch

import httpx2
from iotawattpy.sensor import Sensor
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.iotawatt.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

MAC = "AABBCCDDEEFF"
INPUT_ID = f"{MAC}-input-3-Watts"


class _Device:
    """Stands in for the library; fails the next ``failures`` update calls."""

    def __init__(self) -> None:
        self.sensors = {
            "input_3": Sensor(
                "3", "heat_pump", None, "Input", "Watts", 100.0, None, MAC
            ),
        }
        self.failures = 0
        self.calls = 0

    def api(self) -> type:
        device = self

        class FakeApi:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def connect(self) -> bool:
                return True

            async def update(self, lastUpdate=None) -> None:
                device.calls += 1
                if device.failures:
                    device.failures -= 1
                    raise httpx2.ConnectTimeout("timed out")

            def getSensors(self) -> dict[str, Any]:
                return {"sensors": device.sensors}

        return FakeApi


@pytest.fixture(autouse=True)
def no_retry_delay():
    """Do not wait between the two tries in tests."""
    with patch("custom_components.iotawatt.coordinator.RETRY_DELAY", 0):
        yield


async def _setup(hass: HomeAssistant) -> tuple[MockConfigEntry, _Device, str]:
    device = _Device()
    patcher = patch("custom_components.iotawatt.coordinator.Iotawatt", device.api())
    patcher.start()
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "iotawatt.local"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, INPUT_ID)
    assert entity_id
    device.calls = 0
    entry.async_on_unload(patcher.stop)
    return entry, device, entity_id


async def _poll(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_one_failed_request_is_retried(hass: HomeAssistant) -> None:
    """A single failure is retried and the poll succeeds with fresh data."""
    entry, device, entity_id = await _setup(hass)

    device.failures = 1
    device.sensors["input_3"].setValue(250.0)
    await _poll(hass, entry)

    assert device.calls == 2
    assert entry.runtime_data.last_update_success
    assert hass.states.get(entity_id).state == "250.0"


async def test_two_failures_make_the_poll_fail(hass: HomeAssistant) -> None:
    """If the second try fails too, the sensors go unavailable as in core."""
    entry, device, entity_id = await _setup(hass)

    device.failures = 2
    await _poll(hass, entry)

    assert device.calls == 2
    assert not entry.runtime_data.last_update_success
    assert hass.states.get(entity_id).state == "unavailable"

    await _poll(hass, entry)

    assert entry.runtime_data.last_update_success
    assert hass.states.get(entity_id).state == "100.0"


async def test_no_retry_when_the_first_request_works(hass: HomeAssistant) -> None:
    """A healthy poll makes exactly one request."""
    entry, device, entity_id = await _setup(hass)

    await _poll(hass, entry)

    assert device.calls == 1
    assert hass.states.get(entity_id).state == "100.0"
