"""One-time unique ID migration for users coming from kuralabs/iotawatt_ha 1.0.0.

That release used ``{MAC}_{Type}_{name}`` for every sensor. This integration
uses Home Assistant core's ID format for inputs, so leaving this fork for core
only affects outputs. The migration is safe to run on every start: it only
rewrites registry entries whose unique ID still has the old format, and it never
deletes anything.
"""

import logging

from iotawattpy.sensor import Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .unique_id import input_unique_id

_LOGGER = logging.getLogger(__name__)


@callback
def async_migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, sensors: dict[str, Sensor]
) -> None:
    """Rewrite old input unique IDs to the core format using live sensor data."""
    mapping: dict[str, str] = {}
    for data in sensors.values():
        if data.getType() != "Input":
            continue
        old_id = data.getSensorID()
        new_id = input_unique_id(data)
        if old_id != new_id:
            mapping[old_id] = new_id

    if not mapping:
        return

    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.platform != DOMAIN or entity_entry.domain != "sensor":
            continue
        new_id = mapping.get(entity_entry.unique_id)
        if new_id is None:
            continue
        if registry.async_get_entity_id("sensor", DOMAIN, new_id) is not None:
            _LOGGER.warning(
                "Not migrating %s: unique ID %s is already used by another entity. "
                "Remove the duplicate entity manually",
                entity_entry.entity_id,
                new_id,
            )
            continue
        _LOGGER.info(
            "Migrating unique ID of %s from %s to %s",
            entity_entry.entity_id,
            entity_entry.unique_id,
            new_id,
        )
        registry.async_update_entity(entity_entry.entity_id, new_unique_id=new_id)
