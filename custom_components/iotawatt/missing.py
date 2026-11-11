"""Keep sensors that briefly vanish from the IoTaWatt's answer.

The library drops a sensor as soon as its name is missing from the list of
series the IoTaWatt returns, and the sensor platform then deletes the entity
from the entity registry. A single incomplete answer from an unstable device
would therefore delete entities, and they would not come back until Home
Assistant restarts.

This module holds on to a missing sensor for a number of successful polls.
While it is held the entity is unavailable (its last value is stale). If the
sensor comes back, nothing was lost. Only when it stays away for the whole
period is it let go, which is what happens when a channel or output is really
removed or renamed on the IoTaWatt.

THE NUMBER OF POLLS BELOW IS A GUESS (10 polls is about 5 minutes at the
30 second update interval). It was not derived from observed device behaviour.
"""

import logging

from iotawattpy.sensor import Sensor

_LOGGER = logging.getLogger(__name__)

# Successful polls in a row a sensor must be missing before it is let go.
MISSING_POLLS_BEFORE_REMOVAL = 10


class MissingSensorTracker:
    """Track sensors that are missing from the device's latest answer."""

    def __init__(self) -> None:
        """Initialize the tracker."""
        self._missing: dict[str, int] = {}

    def is_missing(self, key: str) -> bool:
        """Return True while a sensor is held but absent from the device."""
        return key in self._missing

    def merge(
        self, previous: dict[str, Sensor], live: dict[str, Sensor]
    ) -> dict[str, Sensor]:
        """Return the live sensors plus the ones still being held.

        ``previous`` is what the last successful poll returned (including held
        sensors); ``live`` is what the device reports now. The result is always
        a new dict, so later changes the library makes to its own dict cannot
        remove anything from the data Home Assistant is using.
        """
        merged = dict(live)

        for key in [key for key in self._missing if key in live]:
            del self._missing[key]
            _LOGGER.info("IoTaWatt sensor %s is reported by the device again", key)

        for key, sensor in previous.items():
            if key in live:
                continue
            count = self._missing.get(key, 0) + 1
            if count >= MISSING_POLLS_BEFORE_REMOVAL:
                self._missing.pop(key, None)
                _LOGGER.warning(
                    "IoTaWatt sensor %s (%s) was missing from the device for %s "
                    "polls in a row and is being removed",
                    key,
                    sensor.getName(),
                    count,
                )
                continue
            if count == 1:
                _LOGGER.warning(
                    "IoTaWatt sensor %s (%s) is missing from the device's answer; "
                    "keeping it as unavailable for up to %s polls",
                    key,
                    sensor.getName(),
                    MISSING_POLLS_BEFORE_REMOVAL,
                )
            self._missing[key] = count
            merged[key] = sensor

        return merged
