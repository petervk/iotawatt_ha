"""Tests for working with an outdated copy of the library."""

from typing import ClassVar

from iotawattpy.sensor import Sensor
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iotawatt import compat
from custom_components.iotawatt.compat import (
    ISSUE_ID,
    api_options,
    async_check_library,
    filter_sensors,
)
from custom_components.iotawatt.const import DOMAIN
from custom_components.iotawatt.coordinator import IotawattUpdater
from custom_components.iotawatt.migrate import async_migrate_unique_ids
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

MAC = "A848FAF087FD"


class _OldApi:
    """Mimics iotawattpy 0.1.0: no includeNonTotalSensors option."""

    created_with: ClassVar[dict] = {}

    def __init__(
        self,
        device_name,
        ip,
        websession,
        username=None,
        password=None,
        integratedInterval="y",
    ):
        type(self).created_with = {"integratedInterval": integratedInterval}

    async def connect(self):
        return True

    async def update(self, lastUpdate=None):
        return None

    def getSensors(self):
        return {"sensors": _old_library_sensors()}


class _NewApi(_OldApi):
    """Mimics iotawattpy 0.3.0: accepts includeNonTotalSensors."""

    def __init__(
        self,
        device_name,
        ip,
        websession,
        username=None,
        password=None,
        integratedInterval="y",
        includeNonTotalSensors=True,
    ):
        type(self).created_with = {
            "integratedInterval": integratedInterval,
            "includeNonTotalSensors": includeNonTotalSensors,
        }

    def getSensors(self):
        return {"sensors": _new_library_sensors()}


def _s(channel, name, unit, suffix=None, from_start=False, io="Input"):
    return Sensor(channel, name, suffix, io, unit, 1.0, None, MAC, from_start)


def _new_library_sensors():
    """What 0.3.0 returns with includeNonTotalSensors=False."""
    return {
        "input_14": _s("14", "solar", "Watts"),
        "input_14_total_energy": _s("14", "solar", "WattHours", ".wh", True),
        "output_grid": _s("N/A", "grid", "Watts", io="Output"),
    }


def _old_library_sensors():
    """What 0.1.0 returns: the same plus per-period energy sensors."""
    return {
        **_new_library_sensors(),
        "input_14_energy": _s("14", "solar", "WattHours", ".wh"),
        "output_grid_energy": _s("N/A", "grid", "WattHours", ".wh", io="Output"),
    }


@pytest.fixture
def old_library(monkeypatch):
    monkeypatch.setattr(compat, "Iotawatt", _OldApi)
    monkeypatch.setattr("custom_components.iotawatt.coordinator.Iotawatt", _OldApi)
    return _OldApi


@pytest.fixture
def new_library(monkeypatch):
    monkeypatch.setattr(compat, "Iotawatt", _NewApi)
    monkeypatch.setattr("custom_components.iotawatt.coordinator.Iotawatt", _NewApi)
    return _NewApi


def test_option_passed_only_when_supported(old_library) -> None:
    """The option is left out for the old library."""
    assert api_options() == {}


def test_option_passed_when_supported(new_library) -> None:
    """The option is passed for the current library."""
    assert api_options() == {"includeNonTotalSensors": False}


def test_filter_removes_per_period_sensors_for_old_library(old_library) -> None:
    """Per-period energy sensors are removed, everything else is kept."""
    result = filter_sensors({"sensors": _old_library_sensors()})
    assert set(result["sensors"]) == {
        "input_14",
        "input_14_total_energy",
        "output_grid",
    }


def test_filter_is_noop_for_current_library(new_library) -> None:
    """With the current library the data is returned untouched."""
    data = {"sensors": _new_library_sensors()}
    assert filter_sensors(data) is data


async def _update(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    coordinator = IotawattUpdater(hass, entry)
    return await coordinator._async_update_data()


async def test_coordinator_with_old_library(hass: HomeAssistant, old_library) -> None:
    """The coordinator works with the old library and gets no per-period sensors."""
    data = await _update(hass)
    assert "includeNonTotalSensors" not in old_library.created_with
    assert set(data["sensors"]) == {
        "input_14",
        "input_14_total_energy",
        "output_grid",
    }


async def test_coordinator_with_current_library(
    hass: HomeAssistant, new_library
) -> None:
    """The coordinator passes the option to the current library."""
    data = await _update(hass)
    assert new_library.created_with["includeNonTotalSensors"] is False
    assert set(data["sensors"]) == {
        "input_14",
        "input_14_total_energy",
        "output_grid",
    }


async def test_repair_issue_created_and_cleared(
    hass: HomeAssistant, monkeypatch
) -> None:
    """The Repair issue exists only while the old library is loaded."""
    registry = ir.async_get(hass)
    monkeypatch.setattr(compat, "Iotawatt", _OldApi)
    async_check_library(hass)
    issue = registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_placeholders == {"readme_url": compat.README_URL}

    monkeypatch.setattr(compat, "Iotawatt", _NewApi)
    async_check_library(hass)
    assert registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_migration_ok_with_old_library_data(
    hass: HomeAssistant, old_library
) -> None:
    """After filtering, old-library data migrates without ID collisions."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for unique_id, object_id in (
        (f"{MAC}_Input_solar", "solar_power"),
        (f"{MAC}_Input_solar.wh", "solar_energy"),
    ):
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            config_entry=entry,
            suggested_object_id=object_id,
        )
    data = filter_sensors({"sensors": _old_library_sensors()})

    async_migrate_unique_ids(hass, entry, data["sensors"])

    assert registry.async_get("sensor.solar_power").unique_id == f"{MAC}-input-14-Watts"
    assert (
        registry.async_get("sensor.solar_energy").unique_id
        == f"{MAC}-input-14-WattHours"
    )
