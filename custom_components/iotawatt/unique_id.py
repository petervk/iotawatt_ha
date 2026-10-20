"""Unique ID helpers for the IoTaWatt integration.

Inputs use exactly the same format as Home Assistant core. Outputs have no
stable identifier on the device, so this fork builds their ID from the hub MAC
address and the output name. That is the only deviation from core, and it is
the one core does not accept because an output name can be changed by the user.
"""

from iotawattpy.sensor import Sensor


def input_unique_id(data: Sensor) -> str:
    """Return the core-compatible unique ID of an input sensor."""
    return f"{data.hub_mac_address}-input-{data.getChannel()}-{data.getUnit()}"


def output_unique_id(data: Sensor) -> str:
    """Return the fork unique ID of an output sensor: {MAC}_Output_{name}."""
    return data.getSensorID()


def sensor_unique_id(data: Sensor) -> str:
    """Return the unique ID for any sensor."""
    if data.getType() == "Input":
        return input_unique_id(data)
    return output_unique_id(data)
