"""Tolerate an outdated copy of the IoTaWatt library.

The original ``kuralabs/iotawatt_ha`` integration required the old ``iotawattpy``
0.1.0 package. It installs the same ``iotawattpy`` module as ``ha-iotawattpy``,
so on installs that started from it the old code can end up loaded instead of
the library this integration requires. The old code does not accept the
``includeNonTotalSensors`` option that Home Assistant core uses.

Home Assistant cannot uninstall a package, so instead of failing, this module
makes the integration work with either library:

* the option is only passed when the loaded library accepts it, and
* otherwise the per-period (``_wh_last``) sensors are removed from the data
  here, which gives the same result as the option.

A Repair issue tells the user the outdated copy is present.
"""

import inspect
import logging
from typing import Any

from iotawattpy.iotawatt import Iotawatt

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_ID = "outdated_library"

OPTION = "includeNonTotalSensors"


def library_supports_option() -> bool:
    """Return True if the loaded library accepts includeNonTotalSensors."""
    return OPTION in inspect.signature(Iotawatt.__init__).parameters


def api_options() -> dict[str, bool]:
    """Return the extra options to pass to the library."""
    return {OPTION: False} if library_supports_option() else {}


def filter_sensors(data: dict[str, Any]) -> dict[str, Any]:
    """Drop per-period energy sensors if the library cannot do it itself."""
    if library_supports_option():
        return data
    sensors = {
        key: sensor
        for key, sensor in data["sensors"].items()
        if not (
            sensor.getUnit() == "WattHours"
            and sensor.getSuffix() == ".wh"
            and not sensor.getFromStart()
        )
    }
    return {**data, "sensors": sensors}


def async_check_library(hass: HomeAssistant) -> None:
    """Create or clear the Repair issue about an outdated library."""
    if library_supports_option():
        ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)
        return
    _LOGGER.warning(
        "An outdated IoTaWatt library (the old 'iotawattpy' package) is loaded. "
        "The integration is working around it; see the README to remove it"
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_ID,
    )
