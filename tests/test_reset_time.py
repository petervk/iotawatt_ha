"""Tests for rejecting an impossible reset time on the energy sensors.

Home Assistant's statistics treat a changed ``last_reset`` as a counter reset
and add the sensor's whole value to the statistics sum, so a wrong reset time
from the device is as damaging as a wrong reading.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from iotawattpy.sensor import Sensor
import pytest

from custom_components.iotawatt.limits import is_plausible_reset
from custom_components.iotawatt.sensor import ENTITY_DESCRIPTION_KEY_MAP, IotaWattSensor

MAC = "AABBCCDDEEFF"
NOW = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)  # 15:00 in Toronto
MIDNIGHT = "2026-11-10T00:00:00"


@pytest.fixture(autouse=True)
def fixed_clock(freezer) -> None:
    """Set the clock used by the sensor."""
    freezer.move_to(NOW)


@pytest.mark.parametrize(
    "reset",
    [
        datetime(2026, 11, 10, 0, 0),  # today, device local time
        datetime(2026, 11, 9, 0, 0),  # yesterday (value kept over midnight)
        datetime(2026, 11, 11, 0, 0),  # device far east of UTC, already tomorrow
        datetime(2026, 11, 10, 5, 0, tzinfo=UTC),  # with a time zone
    ],
)
def test_plausible_reset_times_are_kept(reset: datetime) -> None:
    """Midnight today or yesterday, in any time zone, is accepted."""
    assert is_plausible_reset(reset, NOW)


@pytest.mark.parametrize(
    "reset",
    [
        None,  # could not be read as a time
        datetime(1970, 1, 1, 0, 0),
        datetime(2026, 11, 7, 0, 0),  # three days ago
        datetime(2026, 11, 12, 0, 0),  # more than a day ahead
        datetime(2106, 2, 7, 6, 28),
    ],
)
def test_impossible_reset_times_are_rejected(reset: datetime | None) -> None:
    """A reset time far in the past or the future is rejected."""
    assert not is_plausible_reset(reset, NOW)


def _entity(begin: object, unit: str = "WattHours") -> tuple[IotaWattSensor, Sensor]:
    data = Sensor("14", "solar", ".wh", "Input", unit, 1234.0, None, MAC, True)
    data.setBegin(begin)  # type: ignore[arg-type]
    coordinator = MagicMock()
    coordinator.data = {"sensors": {"key": data}}
    entity = IotaWattSensor(coordinator, "key", ENTITY_DESCRIPTION_KEY_MAP[unit])
    return entity, data


def test_normal_reset_time_passes_through() -> None:
    """A normal reading with a normal reset time is unchanged."""
    entity, _ = _entity(MIDNIGHT)

    assert entity.native_value == 1234.0
    assert entity.last_reset == datetime(2026, 11, 10, 0, 0)


@pytest.mark.parametrize(
    "begin", ["1970-01-01T00:00:00", "2106-02-07T06:28:15", "garbage", 123456789]
)
def test_impossible_reset_time_makes_the_sensor_unknown(begin: object) -> None:
    """The reading is rejected and the bad reset time is never reported."""
    entity, _ = _entity(begin)

    assert entity.native_value is None
    assert entity.last_reset is None


def test_last_good_reset_time_is_kept_and_the_sensor_recovers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """During a bad poll the last good reset time stays; then all is normal."""
    entity, data = _entity(MIDNIGHT)
    assert entity.last_reset == datetime(2026, 11, 10, 0, 0)

    data.setBegin("1970-01-01T00:00:00")
    assert entity.native_value is None
    assert entity.last_reset == datetime(2026, 11, 10, 0, 0)
    assert "reset time" in caplog.text
    assert "solar" in caplog.text

    data.setBegin(MIDNIGHT)
    assert entity.native_value == 1234.0
    assert entity.last_reset == datetime(2026, 11, 10, 0, 0)


def test_midnight_rollover_is_still_followed() -> None:
    """A real new day is accepted as the new reset time."""
    entity, data = _entity("2026-11-09T00:00:00")
    assert entity.last_reset == datetime(2026, 11, 9, 0, 0)

    data.setBegin(MIDNIGHT)

    assert entity.native_value == 1234.0
    assert entity.last_reset == datetime(2026, 11, 10, 0, 0)


def test_power_sensor_ignores_the_reset_time() -> None:
    """Only the energy sensors (state class total) have a reset time."""
    entity, _ = _entity("garbage", unit="Watts")

    assert entity.native_value == 1234.0
    assert entity.last_reset is None
