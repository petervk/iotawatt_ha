"""Tests for the ``last_reset`` attribute of the energy sensors.

Home Assistant's long-term statistics look at ``last_reset`` on every state of a
``total`` sensor. A state without it, followed by a state with it, can look like
a counter reset and inflate the statistics ``sum`` by the sensor's whole value.
These tests make sure the attribute is present from the very first state.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from iotawattpy.sensor import Sensor
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
    do_adhoc_statistics,
    statistics_during_period,
)

from custom_components.iotawatt.const import DOMAIN
from custom_components.iotawatt.sensor import (
    ENTITY_DESCRIPTION_KEY_MAP,
    IotaWattSensor,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

MAC = "A848FAF087FD"
MIDNIGHT = "2026-10-20T00:00:00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Replace the conftest fixture of the same name.

    The recorder fixture must be created before ``hass``, so the one test that
    needs both requests ``enable_custom_integrations`` itself, after them.
    """


def _sensor(
    channel: str,
    name: str,
    unit: str,
    suffix: str | None,
    from_start: bool,
    value: float | None = 1000.0,
    begin: str | None = MIDNIGHT,
) -> Sensor:
    sensor = Sensor(channel, name, suffix, "Input", unit, value, None, MAC, from_start)
    sensor.setBegin(begin)
    return sensor


def _energy(begin: str | None = MIDNIGHT) -> Sensor:
    return _sensor("14", "solar_iotawatt", "WattHours", ".wh", True, begin=begin)


def _entity(data: Sensor) -> tuple[IotaWattSensor, MagicMock]:
    coordinator = MagicMock()
    coordinator.data = {"sensors": {"key": data}}
    entity = IotaWattSensor(
        coordinator, "key", ENTITY_DESCRIPTION_KEY_MAP[data.getUnit()]
    )
    return entity, coordinator


def test_last_reset_is_present_before_any_update() -> None:
    """The first state written must already carry last_reset."""
    entity, _ = _entity(_energy())

    assert entity.last_reset == datetime(2026, 10, 20, 0, 0)
    assert entity.state_attributes == {"last_reset": MIDNIGHT}


def test_last_reset_follows_the_data() -> None:
    """A new reset window (midnight rollover) is picked up without extra state."""
    data = _energy()
    entity, _ = _entity(data)

    data.setBegin("2026-10-21T00:00:00")

    assert entity.last_reset == datetime(2026, 10, 21, 0, 0)
    assert entity.state_attributes == {"last_reset": "2026-10-21T00:00:00"}


def test_no_last_reset_when_the_device_reports_no_window() -> None:
    """No begin timestamp means no last_reset (and no invalid attribute)."""
    entity, _ = _entity(_energy(begin=None))

    assert entity.last_reset is None
    assert entity.state_attributes is None


def test_power_sensor_has_no_last_reset() -> None:
    """Instantaneous sensors never expose last_reset."""
    data = _sensor("14", "solar_iotawatt", "Watts", None, False, begin=None)
    entity, _ = _entity(data)

    assert entity.last_reset is None
    assert entity.state_attributes is None


def test_only_total_sensors_expose_last_reset() -> None:
    """last_reset on a non-total sensor is invalid in Home Assistant.

    The reactive energy sensor (VARh) has a begin timestamp but the
    ``measurement`` state class. Exposing it would make Home Assistant raise
    when it builds the state attributes.
    """
    data = _sensor("14", "solar_iotawatt", "VARh", ".varh", True)
    entity, _ = _entity(data)

    assert entity.last_reset is None
    assert entity.state_attributes is None


async def test_every_state_carries_last_reset_through_a_restart(
    recorder_mock, hass: HomeAssistant, enable_custom_integrations, freezer
) -> None:
    """A restart must not inflate the long-term statistics.

    Reproduces the real incident: the first state after the sensors come back
    from ``unavailable`` is the last one of its five minute statistics window.
    Without ``last_reset`` on it, the next window looks like a counter reset
    and the statistics ``sum`` jumps by the full value of the sensor.
    """
    energy = _energy()

    class FakeApi:
        """Stands in for the library; serves ``energy`` as the live value."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def connect(self) -> bool:
            return True

        async def update(self, lastUpdate=None) -> None:
            return None

        def getSensors(self) -> dict[str, Any]:
            return {"sensors": {"input_14_total_energy": energy}}

    def move_to(timestamp: str) -> None:
        freezer.move_to(timestamp)

    move_to("2026-10-20 16:00:00+00:00")
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "iotawatt.local"})
    entry.add_to_hass(hass)

    with patch("custom_components.iotawatt.coordinator.Iotawatt", FakeApi):
        # Window 16:00-16:05: running normally, value 1000 -> 1050.
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{MAC}-input-14-WattHours"
        )
        assert entity_id

        move_to("2026-10-20 16:00:30+00:00")
        energy.setValue(1010.0)
        await entry.runtime_data.async_refresh()
        move_to("2026-10-20 16:04:30+00:00")
        energy.setValue(1050.0)
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        # Restart: unload, the device keeps counting while Home Assistant is down.
        move_to("2026-10-20 16:05:00+00:00")
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        energy.setValue(1400.0)

        # Window 16:05-16:10: the first state after the restart is its last one.
        move_to("2026-10-20 16:09:40+00:00")
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "1400.0"
        assert hass.states.get(entity_id).attributes.get("last_reset")

        # Window 16:10-16:15: normal operation again.
        move_to("2026-10-20 16:10:10+00:00")
        energy.setValue(1410.0)
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    start = dt_util.parse_datetime("2026-10-20 16:00:00+00:00")
    assert start is not None
    for window in range(3):
        do_adhoc_statistics(hass, start=start + timedelta(minutes=5 * window))
        await async_wait_recording_done(hass)

    stats = statistics_during_period(
        hass, start, None, {entity_id}, "5minute", None, {"sum", "state"}
    )[entity_id]
    sums = [round(row["sum"], 3) for row in stats]

    # 1050 - 1000 while running; +350 for the energy used during the outage
    # (1400 - 1050); +10 afterwards. Never a jump of a whole counter value.
    assert sums == [50.0, 400.0, 410.0]
