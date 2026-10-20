"""Tests for the unique ID helpers and the kuralabs 1.0.0 migration."""

import logging
from unittest.mock import MagicMock

from iotawattpy.sensor import Sensor
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iotawatt.const import DOMAIN
from custom_components.iotawatt.migrate import async_migrate_unique_ids
from custom_components.iotawatt.sensor import (
    ENTITY_DESCRIPTION_KEY_MAP,
    IotaWattSensor,
)
from custom_components.iotawatt.unique_id import (
    input_unique_id,
    output_unique_id,
    sensor_unique_id,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

MAC = "A848FAF087FD"


def _input(channel: str, name: str, unit: str = "Watts", suffix=None, from_start=False):
    return Sensor(channel, name, suffix, "Input", unit, 1.0, None, MAC, from_start)


def _output(name: str, unit: str = "Watts", suffix=None, from_start=False):
    return Sensor("N/A", name, suffix, "Output", unit, 1.0, None, MAC, from_start)


def _live_sensors() -> dict[str, Sensor]:
    """Live data as returned by the library with includeNonTotalSensors=False."""
    return {
        "input_14": _input("14", "solar_iotawatt"),
        "input_14_total_energy": _input(
            "14", "solar_iotawatt", "WattHours", ".wh", True
        ),
        "input_6": _input("6", "dishwasher_iotawatt"),
        "input_6_total_energy": _input(
            "6", "dishwasher_iotawatt", "WattHours", ".wh", True
        ),
        "output_grid_import": _output("grid_import"),
        "output_grid_import_total_energy": _output(
            "grid_import", "WattHours", ".wh", True
        ),
    }


def _add(registry, entry, unique_id, suggested, **kwargs):
    return registry.async_get_or_create(
        "sensor",
        DOMAIN,
        unique_id,
        config_entry=entry,
        suggested_object_id=suggested,
        **kwargs,
    )


def _kuralabs_registry(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, str]:
    """Create a registry as left by kuralabs/iotawatt_ha 1.0.0."""
    registry = er.async_get(hass)
    ids = {
        "solar_power": f"{MAC}_Input_solar_iotawatt",
        "solar_energy": f"{MAC}_Input_solar_iotawatt.wh",
        "solar_last": f"{MAC}_Input_solar_iotawatt.wh_last",
        "dishwasher_power": f"{MAC}_Input_dishwasher_iotawatt",
        "dishwasher_energy": f"{MAC}_Input_dishwasher_iotawatt.wh",
        "grid_import_power": f"{MAC}_Output_grid_import",
        "grid_import_energy": f"{MAC}_Output_grid_import.wh",
        "grid_import_last": f"{MAC}_Output_grid_import.wh_last",
        "stale_last": f"{MAC}_Input_hvac_furnace_iotawatt.wh_last",
    }
    for object_id, unique_id in ids.items():
        _add(registry, entry, unique_id, object_id)
    return ids


def test_input_id_matches_core_format() -> None:
    """Inputs use core's {mac}-input-{channel}-{unit}."""
    assert input_unique_id(_input("14", "solar_iotawatt")) == f"{MAC}-input-14-Watts"
    energy = _input("14", "solar_iotawatt", "WattHours", ".wh", True)
    assert input_unique_id(energy) == f"{MAC}-input-14-WattHours"
    assert sensor_unique_id(energy) == f"{MAC}-input-14-WattHours"


def test_output_id_keeps_fork_format() -> None:
    """Outputs keep {MAC}_Output_{name}, as in kuralabs 1.0.0."""
    power = _output("grid_import")
    energy = _output("grid_import", "WattHours", ".wh", True)
    assert output_unique_id(power) == f"{MAC}_Output_grid_import"
    assert sensor_unique_id(energy) == f"{MAC}_Output_grid_import.wh"


def test_entity_gets_id_and_device() -> None:
    """Both inputs and outputs get a unique ID and device info."""
    sensors = _live_sensors()
    coordinator = MagicMock()
    coordinator.data = {"sensors": sensors}
    for key, expected in (
        ("input_14", f"{MAC}-input-14-Watts"),
        ("output_grid_import", f"{MAC}_Output_grid_import"),
    ):
        entity = IotaWattSensor(
            coordinator, key, _description_for(sensors[key])
        )
        assert entity.unique_id == expected
        assert entity.device_info is not None
        assert ("mac", MAC) in entity.device_info["connections"]


def _description_for(data: Sensor):
    """Return the description the platform would pick for this sensor."""
    return ENTITY_DESCRIPTION_KEY_MAP[data.getUnit()]


async def test_migrates_kuralabs_inputs_only(hass: HomeAssistant) -> None:
    """Inputs move to core IDs; outputs, _last and stale entries are untouched."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    ids = _kuralabs_registry(hass, entry)
    registry = er.async_get(hass)
    before = {e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}

    async_migrate_unique_ids(hass, entry, _live_sensors())

    def uid(object_id):
        return registry.async_get(f"sensor.{object_id}").unique_id

    assert uid("solar_power") == f"{MAC}-input-14-Watts"
    assert uid("solar_energy") == f"{MAC}-input-14-WattHours"
    assert uid("dishwasher_power") == f"{MAC}-input-6-Watts"
    assert uid("dishwasher_energy") == f"{MAC}-input-6-WattHours"
    # Outputs unchanged
    assert uid("grid_import_power") == ids["grid_import_power"]
    assert uid("grid_import_energy") == ids["grid_import_energy"]
    # _last entries and stale entries untouched, nothing deleted
    assert uid("solar_last") == ids["solar_last"]
    assert uid("grid_import_last") == ids["grid_import_last"]
    assert uid("stale_last") == ids["stale_last"]
    after = {e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert after == before


async def test_migration_is_idempotent(hass: HomeAssistant) -> None:
    """Running the migration again changes nothing."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _kuralabs_registry(hass, entry)
    registry = er.async_get(hass)

    async_migrate_unique_ids(hass, entry, _live_sensors())
    first = {e.entity_id: e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    async_migrate_unique_ids(hass, entry, _live_sensors())
    second = {e.entity_id: e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert first == second


async def test_collision_is_skipped_and_logged(
    hass: HomeAssistant, caplog
) -> None:
    """If the core ID already exists, skip, warn and delete nothing."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    _add(registry, entry, f"{MAC}-input-0-Volts", "input_0")
    _add(registry, entry, f"{MAC}_Input_Input_0", "input_0_2")
    sensors = {"input_0": _input("0", "Input_0", "Volts")}

    with caplog.at_level(logging.WARNING):
        async_migrate_unique_ids(hass, entry, sensors)

    assert registry.async_get("sensor.input_0").unique_id == f"{MAC}-input-0-Volts"
    assert registry.async_get("sensor.input_0_2").unique_id == f"{MAC}_Input_Input_0"
    assert "Not migrating sensor.input_0_2" in caplog.text


async def test_core_style_registry_is_left_alone(hass: HomeAssistant) -> None:
    """Someone who came from core already has core IDs: nothing changes."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    _add(registry, entry, f"{MAC}-input-14-Watts", "solar_power")
    _add(registry, entry, f"{MAC}-input-14-WattHours", "solar_energy")

    async_migrate_unique_ids(hass, entry, _live_sensors())

    assert registry.async_get("sensor.solar_power").unique_id == f"{MAC}-input-14-Watts"
    assert (
        registry.async_get("sensor.solar_energy").unique_id
        == f"{MAC}-input-14-WattHours"
    )


async def test_other_entries_and_platforms_untouched(hass: HomeAssistant) -> None:
    """Only this config entry's iotawatt sensors are rewritten."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    other = MockConfigEntry(domain=DOMAIN)
    other.add_to_hass(hass)
    registry = er.async_get(hass)
    old = f"{MAC}_Input_solar_iotawatt"
    # Same old-format ID but on a different config entry
    registry.async_get_or_create(
        "sensor", "othervendor", old, config_entry=other, suggested_object_id="foreign"
    )
    _add(registry, other, f"{MAC}_Input_dishwasher_iotawatt", "other_entry_sensor")

    async_migrate_unique_ids(hass, entry, _live_sensors())

    assert registry.async_get("sensor.foreign").unique_id == old
    assert (
        registry.async_get("sensor.other_entry_sensor").unique_id
        == f"{MAC}_Input_dishwasher_iotawatt"
    )


async def test_enabled_last_entities_are_kept(hass: HomeAssistant) -> None:
    """An enabled _wh_last entity is never deleted or rewritten."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    last_id = f"{MAC}_Input_solar_iotawatt.wh_last"
    _add(registry, entry, last_id, "solar_last")

    async_migrate_unique_ids(hass, entry, _live_sensors())

    entity = registry.async_get("sensor.solar_last")
    assert entity is not None
    assert entity.unique_id == last_id
    assert entity.disabled_by is None


async def test_entity_ids_unchanged_by_migration(hass: HomeAssistant) -> None:
    """The migration changes only unique IDs, never entity IDs."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _kuralabs_registry(hass, entry)
    registry = er.async_get(hass)
    before = sorted(e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id))

    async_migrate_unique_ids(hass, entry, _live_sensors())

    after = sorted(e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id))
    assert before == after
