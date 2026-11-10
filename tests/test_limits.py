"""Tests for rejecting impossible readings.

The garbage values below are the kind the IoTaWatt returned when it became
unstable (about -1e17 W and 9.7e18 Wh).
"""

import logging
from unittest.mock import MagicMock

from iotawattpy.sensor import Sensor
import pytest

from custom_components.iotawatt.limits import is_plausible
from custom_components.iotawatt.sensor import ENTITY_DESCRIPTION_KEY_MAP, IotaWattSensor

MAC = "AABBCCDDEEFF"


@pytest.mark.parametrize(
    ("unit", "value"),
    [
        ("Watts", 0),
        ("Watts", 1500.5),
        ("Watts", -3200.0),  # solar export / generation stays valid
        ("Watts", 10_400_000),  # exactly at the limit
        ("WattHours", 123_456.0),
        ("WattHours", 250_000_000),
        ("Volts", 121.4),
        ("Volts", 1_200),
        ("Amps", 38.2),
        ("Hz", 0),
        ("Hz", 60.01),
        ("Hz", 100),
        ("PF", 0.97),
        ("PF", -0.5),
        ("PF", 1.1),
        ("VA", 2500),
        ("VAR", -800),
        ("VARh", 5000),
        ("SomethingNew", 1e30),  # unknown units have no limit
        ("Watts", None),  # no value is not an impossible value
    ],
)
def test_plausible_readings_are_kept(unit: str, value: float | None) -> None:
    """Normal readings, including negative power, are never rejected."""
    assert is_plausible(unit, value)


@pytest.mark.parametrize(
    ("unit", "value"),
    [
        ("Watts", -1e17),
        ("Watts", -4e17),
        ("Watts", 4e17),
        ("Watts", 10_400_001),
        ("WattHours", 9.7e18),
        ("WattHours", 4.8e17),
        ("WattHours", 250_000_001),
        ("WattHours", -9.7e18),
        ("VARh", 1e18),
        ("Volts", 1_201),
        ("Volts", -1e17),
        ("Amps", 10_001),
        ("Hz", -0.1),
        ("Hz", 100.1),
        ("PF", 1.11),
        ("PF", -1e17),
        ("VA", 1e17),
        ("VAR", -1e17),
        ("Watts", float("nan")),
        ("Watts", float("inf")),
        ("Watts", "garbage"),
    ],
)
def test_impossible_readings_are_rejected(unit: str, value: object) -> None:
    """Garbage readings are rejected, in either direction."""
    assert not is_plausible(unit, value)  # type: ignore[arg-type]


def _entity(unit: str, value: float | None) -> tuple[IotaWattSensor, Sensor]:
    data = Sensor("14", "heat_pump", None, "Input", unit, value, None, MAC, False)
    coordinator = MagicMock()
    coordinator.data = {"sensors": {"key": data}}
    entity = IotaWattSensor(coordinator, "key", ENTITY_DESCRIPTION_KEY_MAP[unit])
    return entity, data


def test_sensor_passes_a_normal_value_through() -> None:
    """A normal reading is reported unchanged."""
    entity, _ = _entity("Watts", 1234.5)

    assert entity.native_value == 1234.5


def test_sensor_keeps_negative_power() -> None:
    """Real negative power (export) is still reported."""
    entity, _ = _entity("Watts", -2500.0)

    assert entity.native_value == -2500.0


def test_sensor_power_factor_is_still_a_percentage() -> None:
    """The existing x100 conversion still applies to a valid power factor."""
    entity, _ = _entity("PF", 0.95)

    assert entity.native_value == pytest.approx(95.0)


def test_sensor_is_unknown_for_garbage_then_recovers() -> None:
    """One garbage poll gives unknown; the next good poll gives a value again."""
    entity, data = _entity("Watts", -1.2e17)
    assert entity.native_value is None

    data.setValue(850.0)
    assert entity.native_value == 850.0


def test_sensor_energy_garbage_is_unknown() -> None:
    """Garbage energy never reaches the state (and so the statistics)."""
    entity, _ = _entity("WattHours", 9.7e18)

    assert entity.native_value is None


def test_garbage_power_factor_is_not_multiplied() -> None:
    """The rejection happens before the x100 conversion."""
    entity, _ = _entity("PF", 3e17)

    assert entity.native_value is None


def test_warning_is_logged_once_per_hour(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad stretch does not flood the log."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        "custom_components.iotawatt.sensor.monotonic", lambda: clock["now"]
    )
    entity, _ = _entity("Watts", -1.2e17)

    with caplog.at_level(logging.WARNING, logger="custom_components.iotawatt.sensor"):
        for _ in range(5):
            assert entity.native_value is None
        assert len(caplog.records) == 1
        assert "heat_pump" in caplog.records[0].getMessage()

        clock["now"] += 3601
        assert entity.native_value is None
        assert len(caplog.records) == 2
