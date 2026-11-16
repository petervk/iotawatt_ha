"""Tests for keeping sensors that briefly vanish from the device's answer."""

from typing import Any
from unittest.mock import patch

from iotawattpy.sensor import Sensor
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.iotawatt.const import DOMAIN
from custom_components.iotawatt.missing import (
    MISSING_POLLS_BEFORE_REMOVAL,
    MissingSensorTracker,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

MAC = "AABBCCDDEEFF"
INPUT_ID = f"{MAC}-input-3-Watts"
OUTPUT_ID = f"{MAC}_Output_grid"


def _sensors() -> dict[str, Sensor]:
    return {
        "input_3": Sensor("3", "heat_pump", None, "Input", "Watts", 100.0, None, MAC),
        "output_grid": Sensor("N/A", "grid", None, "Output", "Watts", 5.0, None, MAC),
    }


def test_tracker_holds_then_lets_go() -> None:
    """A missing sensor is kept for a limited number of polls, then dropped."""
    tracker = MissingSensorTracker()
    data = _sensors()
    live = {"input_3": data["input_3"]}

    for _ in range(MISSING_POLLS_BEFORE_REMOVAL - 1):
        data = tracker.merge(data, live)
        assert "output_grid" in data
        assert tracker.is_missing("output_grid")
        assert not tracker.is_missing("input_3")

    data = tracker.merge(data, live)
    assert "output_grid" not in data
    assert not tracker.is_missing("output_grid")


def test_tracker_resets_when_the_sensor_returns() -> None:
    """Coming back clears the count; a later gap starts from zero."""
    tracker = MissingSensorTracker()
    full = _sensors()
    live = {"input_3": full["input_3"]}

    data = tracker.merge(full, live)
    data = tracker.merge(data, full)
    assert not tracker.is_missing("output_grid")

    for _ in range(MISSING_POLLS_BEFORE_REMOVAL - 1):
        data = tracker.merge(data, live)
    assert "output_grid" in data


def test_tracker_returns_a_copy() -> None:
    """The library editing its own dict must not change the returned data."""
    tracker = MissingSensorTracker()
    live = _sensors()

    data = tracker.merge({}, live)
    live.clear()

    assert set(data) == {"input_3", "output_grid"}


class _Device:
    """Stands in for the library; ``sensors`` is edited in place like it does."""

    def __init__(self) -> None:
        self.sensors = _sensors()
        self.fail = False

    def api(self) -> type:
        device = self

        class FakeApi:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def connect(self) -> bool:
                return True

            async def update(self, lastUpdate=None) -> None:
                if device.fail:
                    raise IndexError("series list shorter than the inputs")

            def getSensors(self) -> dict[str, Any]:
                return {"sensors": device.sensors}

        return FakeApi


async def _setup(hass: HomeAssistant, device: _Device) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "iotawatt.local"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _poll(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


@pytest.mark.parametrize("poll_fails", [False, True])
async def test_one_incomplete_answer_does_not_delete_entities(
    hass: HomeAssistant, poll_fails: bool
) -> None:
    """One bad poll leaves the entities in place; the next good poll restores them."""
    device = _Device()
    registry = er.async_get(hass)
    with patch("custom_components.iotawatt.coordinator.Iotawatt", device.api()):
        entry = await _setup(hass, device)
        input_entity = registry.async_get_entity_id("sensor", DOMAIN, INPUT_ID)
        output_entity = registry.async_get_entity_id("sensor", DOMAIN, OUTPUT_ID)
        assert input_entity
        assert output_entity

        backup = dict(device.sensors)
        device.sensors.clear()
        device.fail = poll_fails
        await _poll(hass, entry)

        for entity_id in (input_entity, output_entity):
            assert registry.async_get(entity_id) is not None
            assert hass.states.get(entity_id).state == "unavailable"

        device.fail = False
        device.sensors.update(backup)
        await _poll(hass, entry)

        assert hass.states.get(input_entity).state == "100.0"
        assert hass.states.get(output_entity).state == "5.0"


async def test_a_sensor_that_stays_away_is_removed_and_can_return(
    hass: HomeAssistant,
) -> None:
    """A really removed output is deleted after the hold, and re-created later."""
    device = _Device()
    registry = er.async_get(hass)
    with patch("custom_components.iotawatt.coordinator.Iotawatt", device.api()):
        entry = await _setup(hass, device)
        output_entity = registry.async_get_entity_id("sensor", DOMAIN, OUTPUT_ID)
        assert output_entity

        removed = device.sensors.pop("output_grid")
        for _ in range(MISSING_POLLS_BEFORE_REMOVAL - 1):
            await _poll(hass, entry)
            assert registry.async_get(output_entity) is not None

        await _poll(hass, entry)
        assert registry.async_get(output_entity) is None
        assert registry.async_get_entity_id("sensor", DOMAIN, INPUT_ID)

        device.sensors["output_grid"] = removed
        await _poll(hass, entry)

        assert registry.async_get_entity_id("sensor", DOMAIN, OUTPUT_ID)
        assert hass.states.get(output_entity).state == "5.0"
