"""Migration test built from a real install's registry (MAC address replaced).

The registry below mirrors what kuralabs/iotawatt_ha 1.0.0 left behind on a
live system before the first migration: 69 IotaWatt entries, 32 enabled and 37
disabled. The expected unique IDs are written out by hand, not computed with the
code under test, so a change to the ID format fails here.

Shape of the data:
* 12 input channels (3 to 14), each with a power and an energy sensor (24).
* 4 outputs (grid_export, grid_import, mains_iotawatt, total_iotawatt), each
  with a power and an energy sensor (8). These must never change.
* 31 disabled ``.wh_last`` entries: 16 for live channels or outputs, 15 stale.
* 4 disabled stale entries for removed channels (main_1, main_2).
* A collision: a core-format ``input_0`` and a fork-format ``input_0_2``.
"""

import logging

from iotawattpy.sensor import Sensor
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iotawatt.const import DOMAIN
from custom_components.iotawatt.migrate import async_migrate_unique_ids
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

MAC = "AABBCCDDEEFF"

# channel, library name, power entity object id, energy entity object id
INPUTS = [
    (
        3,
        "hvac_heat_pump_iotawatt",
        "hvac_heat_pump_iotawatt",
        "hvac_heat_pump_iotawatt_wh",
    ),
    (4, "dryer_iotawatt", "dryer_iotawatt", "dryer_iotawatt_wh"),
    (5, "garage_iotawatt", "garage_iotawatt", "garage_iotawatt_wh"),
    (6, "dishwasher_iotawatt", "dishwasher_iotawatt", "dishwasher_iotawatt_wh"),
    (
        7,
        "kitchen_range_hood_iotawatt",
        "kitchen_range_hood_iotawatt",
        "kitchen_range_hood_iotawatt_wh",
    ),
    (8, "evse_iotawatt", "evse_power", "evse_energy"),
    (
        9,
        "basement_dishwasher_iotawatt",
        "basement_dishwasher_iotawatt",
        "basement_dishwasher_iotawatt_wh",
    ),
    (
        10,
        "hvac_electric_heat_iotawatt",
        "hvac_electric_heat_iotawatt",
        "hvac_electric_heat_iotawatt_wh",
    ),
    (
        11,
        "hvac_water_heater_iotawatt",
        "hvac_water_heater_iotawatt",
        "hvac_water_heater_iotawatt_wh",
    ),
    (
        12,
        "basement_range_iotawatt",
        "basement_range_iotawatt",
        "basement_range_iotawatt_wh",
    ),
    (13, "range_iotawatt", "range_iotawatt", "range_iotawatt_wh"),
    (14, "solar_iotawatt", "solar_iotawatt", "solar_iotawatt_wh"),
]

# library name, power entity object id, energy entity object id
OUTPUTS = [
    ("grid_export", "grid_export", "grid_export_wh"),
    ("grid_import", "grid_import", "grid_import_wh"),
    ("mains_iotawatt", "mains_iotawatt", "mains_iotawatt_wh"),
    ("total_iotawatt", "total_iotawatt", "total_iotawatt_wh"),
]

# Names of the 15 stale .wh_last entries (channel or output no longer exists)
STALE_LAST = [
    "main_1_iotawatt",
    "main_2_iotawatt",
    "hvac_air_conditioner_iotawatt",
    "hvac_furnace_iotawatt",
    "hvac_ventilator_iotawatt",
    "fridge_2_iotawatt",
    "peters_office_iotawatt",
    "breaker_23b_iotawatt",
    "breaker_20_iotawatt",
    "hvac_iotawatt",
    "import_iotawatt",
    "misc_iotawatt",
    "import_negative",
    "import_positive",
    "esve_iotawatt",
]

# Disabled entries for removed channels: (unique ID suffix, object id)
STALE_PLAIN = [
    ("Input_main_1_iotawatt", "main_1_iotawatt"),
    ("Input_main_1_iotawatt.wh", "main_1_iotawatt_wh"),
    ("Input_main_2_iotawatt", "main_2_iotawatt"),
    ("Input_main_2_iotawatt.wh", "main_2_iotawatt_wh"),
]


def _input(channel: int, name: str, unit: str = "Watts", suffix=None, from_start=False):
    return Sensor(str(channel), name, suffix, "Input", unit, 1.0, None, MAC, from_start)


def _output(name: str, unit: str = "Watts", suffix=None, from_start=False):
    return Sensor("N/A", name, suffix, "Output", unit, 1.0, None, MAC, from_start)


def _live_sensors() -> dict[str, Sensor]:
    """Live data as the library returns it with includeNonTotalSensors=False."""
    sensors: dict[str, Sensor] = {}
    for channel, name, _power, _energy in INPUTS:
        sensors[f"input_{channel}"] = _input(channel, name)
        sensors[f"input_{channel}_total_energy"] = _input(
            channel, name, "WattHours", ".wh", True
        )
    for name, _power, _energy in OUTPUTS:
        sensors[f"output_{name}"] = _output(name)
        sensors[f"output_{name}_total_energy"] = _output(name, "WattHours", ".wh", True)
    return sensors


def _expected_input_ids() -> dict[str, tuple[str, str]]:
    """object id -> (old unique ID, new core unique ID), written out by hand."""
    expected = {}
    for channel, name, power, energy in INPUTS:
        expected[power] = (
            f"{MAC}_Input_{name}",
            f"{MAC}-input-{channel}-Watts",
        )
        expected[energy] = (
            f"{MAC}_Input_{name}.wh",
            f"{MAC}-input-{channel}-WattHours",
        )
    return expected


def _expected_output_ids() -> dict[str, str]:
    """object id -> unique ID that must stay as it is."""
    expected = {}
    for name, power, energy in OUTPUTS:
        expected[power] = f"{MAC}_Output_{name}"
        expected[energy] = f"{MAC}_Output_{name}.wh"
    return expected


def _expected_last_ids() -> dict[str, str]:
    """object id -> unique ID of the 31 disabled .wh_last entries."""
    expected = {}
    for _channel, name, _power, _energy in INPUTS:
        expected[f"{name}_wh_last"] = f"{MAC}_Input_{name}.wh_last"
    for name, _power, _energy in OUTPUTS:
        expected[f"{name}_wh_last"] = f"{MAC}_Output_{name}.wh_last"
    for name in STALE_LAST:
        expected[f"{name}_wh_last"] = f"{MAC}_Input_{name}.wh_last"
    return expected


def _build_registry(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, str]:
    """Create the 69-entry registry. Returns object id -> unique ID."""
    registry = er.async_get(hass)
    disabled = er.RegistryEntryDisabler.INTEGRATION
    created: dict[str, str] = {}

    def add(object_id: str, unique_id: str, is_disabled: bool) -> None:
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            config_entry=entry,
            suggested_object_id=object_id,
            disabled_by=disabled if is_disabled else None,
        )
        created[object_id] = unique_id

    for object_id, (old_id, _new_id) in _expected_input_ids().items():
        add(object_id, old_id, False)
    for object_id, unique_id in _expected_output_ids().items():
        add(object_id, unique_id, False)
    for object_id, unique_id in _expected_last_ids().items():
        add(object_id, unique_id, True)
    for suffix, object_id in STALE_PLAIN:
        add(object_id, f"{MAC}_{suffix}", True)
    # The collision: core-format volts input and the fork-format duplicate
    add("input_0", f"{MAC}-input-0-Volts", True)
    add("input_0_2", f"{MAC}_Input_Input_0", True)
    return created


def _snapshot(registry, entry) -> dict[str, tuple[str, str | None]]:
    """entity id -> (unique ID, disabled_by) for every entry of the config entry."""
    return {
        e.entity_id: (e.unique_id, e.disabled_by)
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


async def test_registry_shape_matches_real_install(hass: HomeAssistant) -> None:
    """The fixture itself has the 69 / 32 / 37 shape of the real registry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _build_registry(hass, entry)
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)

    assert len(entries) == 69
    assert sum(1 for e in entries if e.disabled_by is None) == 32
    assert sum(1 for e in entries if e.disabled_by is not None) == 37
    assert len(_expected_last_ids()) == 31


async def test_all_24_live_inputs_move_to_core_ids(hass: HomeAssistant) -> None:
    """Every live input entity gets exactly its core unique ID."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _build_registry(hass, entry)
    registry = er.async_get(hass)

    async_migrate_unique_ids(hass, entry, _live_sensors())

    expected = _expected_input_ids()
    assert len(expected) == 24
    for object_id, (_old_id, new_id) in expected.items():
        entity = registry.async_get(f"sensor.{object_id}")
        assert entity is not None, object_id
        assert entity.unique_id == new_id, object_id
        assert entity.disabled_by is None, object_id


async def test_outputs_stay_exactly_as_they_are(hass: HomeAssistant) -> None:
    """The 8 output entities keep {MAC}_Output_{name}; the Energy dashboard needs them."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _build_registry(hass, entry)
    registry = er.async_get(hass)

    async_migrate_unique_ids(hass, entry, _live_sensors())

    expected = _expected_output_ids()
    assert len(expected) == 8
    for object_id, unique_id in expected.items():
        entity = registry.async_get(f"sensor.{object_id}")
        assert entity is not None, object_id
        assert entity.unique_id == unique_id, object_id


async def test_wh_last_and_stale_entries_are_untouched(hass: HomeAssistant) -> None:
    """31 .wh_last and 4 stale entries keep their IDs and stay disabled."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _build_registry(hass, entry)
    registry = er.async_get(hass)

    async_migrate_unique_ids(hass, entry, _live_sensors())

    untouched = dict(_expected_last_ids())
    untouched.update(
        {object_id: f"{MAC}_{suffix}" for suffix, object_id in STALE_PLAIN}
    )
    assert len(untouched) == 35
    for object_id, unique_id in untouched.items():
        entity = registry.async_get(f"sensor.{object_id}")
        assert entity is not None, object_id
        assert entity.unique_id == unique_id, object_id
        assert entity.disabled_by is not None, object_id


async def test_collision_input_0_2_is_skipped_with_one_warning(
    hass: HomeAssistant, caplog
) -> None:
    """input_0_2 collides with the core-format input_0: skip it and warn once."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _build_registry(hass, entry)
    registry = er.async_get(hass)
    sensors = _live_sensors()
    # Channel 0 volts is reported by the device; the library does not mark it live
    # with includeNonTotalSensors=False, but the migration must handle it if it is.
    sensors["input_0"] = _input(0, "Input_0", "Volts")

    with caplog.at_level(logging.WARNING, logger="custom_components.iotawatt.migrate"):
        async_migrate_unique_ids(hass, entry, sensors)

    assert registry.async_get("sensor.input_0").unique_id == f"{MAC}-input-0-Volts"
    assert registry.async_get("sensor.input_0_2").unique_id == f"{MAC}_Input_Input_0"
    warnings = [r for r in caplog.records if "Not migrating" in r.getMessage()]
    assert len(warnings) == 1
    assert "sensor.input_0_2" in warnings[0].getMessage()


async def test_nothing_added_removed_or_re_enabled(hass: HomeAssistant) -> None:
    """69 entries before and after; entity IDs and disabled state unchanged."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _build_registry(hass, entry)
    registry = er.async_get(hass)
    before = _snapshot(registry, entry)

    async_migrate_unique_ids(hass, entry, _live_sensors())

    after = _snapshot(registry, entry)
    assert len(after) == 69
    assert set(after) == set(before)
    assert {k: v[1] for k, v in after.items()} == {k: v[1] for k, v in before.items()}
    changed = {k for k in after if after[k][0] != before[k][0]}
    assert len(changed) == 24


async def test_second_run_changes_nothing(hass: HomeAssistant, caplog) -> None:
    """The migration runs on every start; a second run is a no-op and silent."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _build_registry(hass, entry)
    registry = er.async_get(hass)

    async_migrate_unique_ids(hass, entry, _live_sensors())
    first = _snapshot(registry, entry)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="custom_components.iotawatt.migrate"):
        async_migrate_unique_ids(hass, entry, _live_sensors())

    assert _snapshot(registry, entry) == first
    assert "Migrating unique ID" not in caplog.text
