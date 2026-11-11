"""Sanity limits for the readings the IoTaWatt reports.

The IoTaWatt sometimes returns impossible numbers (for example around
-1e17 W or 9.7e18 Wh) when it is unstable. Those values would otherwise flow
into the Energy dashboard, long-term statistics and any helper built on top.

THE LIMITS BELOW ARE A GUESS. They are deliberately set far beyond any real
reading, so that a normal installation never comes close to them. They are
not IoTaWatt specifications and were not checked against the hardware. They
start from two round base numbers (see README, "Rejecting impossible
readings"), and every limit is then doubled to leave room for unusual
installations:

* voltage: 600 V base, doubled                                      -> 1,200 V
* current: 5,000 A base, doubled                                    -> 10,000 A
* power: 600 V x 5,000 A x sqrt(3) = 5.2 MW, doubled               -> 10.4 MW
* energy: 5.2 MW for 24 h = 125 MWh (sensors reset daily), doubled  -> 250 MWh

The limits are each doubled on their own, so the power limit is NOT the
product of the voltage and current limits (that would be four times the base,
not twice). They are generous on purpose: the garbage seen so far is around
1e17, billions of times above every limit here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import math

MAX_VOLTS = 1_200.0
MAX_AMPS = 10_000.0
MAX_POWER = 10_400_000.0  # W, VA and VAR
MAX_ENERGY = 250_000_000.0  # Wh and VARh
MIN_HZ = 0.0
MAX_HZ = 100.0
MAX_ABS_POWER_FACTOR = 1.1  # a real power factor cannot exceed 1

# The energy sensors reset daily, so the reset time the IoTaWatt reports is its
# own local midnight: at most 24 hours ago on its clock. The IoTaWatt's time
# zone is not known here, and local time can be up to 12 hours behind or 14
# hours ahead of UTC, so the window is wide. THESE ARE GUESSES TOO.
MAX_RESET_AGE = timedelta(hours=48)
MAX_RESET_AHEAD = timedelta(hours=15)

# Largest allowed absolute value per IoTaWatt unit. Negative readings stay
# allowed where they are real (for example power flowing back to the grid).
_MAX_ABS: dict[str, float] = {
    "Volts": MAX_VOLTS,
    "Amps": MAX_AMPS,
    "Watts": MAX_POWER,
    "VA": MAX_POWER,
    "VAR": MAX_POWER,
    "WattHours": MAX_ENERGY,
    "VARh": MAX_ENERGY,
    "PF": MAX_ABS_POWER_FACTOR,
}


def is_plausible(unit: str, value: float | None) -> bool:
    """Return False when a reading is impossible and must be rejected.

    ``None`` is returned as plausible: it means "no value" and is handled by
    the caller as before. Units without a limit are always plausible.
    """
    if value is None:
        return True
    try:
        number = float(value)
    except TypeError, ValueError:
        return False
    if not math.isfinite(number):
        return False
    if unit == "Hz":
        return MIN_HZ <= number <= MAX_HZ
    if (limit := _MAX_ABS.get(unit)) is None:
        return True
    return abs(number) <= limit


def is_plausible_reset(reset: datetime | None, now: datetime) -> bool:
    """Return False when a reported reset time cannot be right.

    ``reset`` is the start of the energy sensors' counting period as reported
    by the IoTaWatt (usually without a time zone); ``now`` must be time zone
    aware. ``None`` (the text could not be read as a time) is not plausible.
    """
    if reset is None:
        return False
    if reset.tzinfo is None:
        reset = reset.replace(tzinfo=UTC)
    return now - MAX_RESET_AGE <= reset <= now + MAX_RESET_AHEAD
