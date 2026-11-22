# IoTaWatt for Home Assistant

A custom version of the Home Assistant [IoTaWatt](https://iotawatt.com) integration. It gives **every** sensor a unique ID and a device, including outputs, which the built-in integration does not. It also includes a few fixes that make the energy statistics more reliable.

Apart from these changes it follows the built-in integration and uses the same library (`ha-iotawattpy`).

## Unique IDs for outputs

The built-in integration gives unique IDs only to inputs. Without a unique ID, an output cannot be renamed, assigned to an area or managed in the UI ([core issue #87182](https://github.com/home-assistant/core/issues/87182)). This integration gives outputs a unique ID and attaches all sensors to the IoTaWatt device.

- **Inputs** use the same unique ID as the built-in integration: `{mac}-input-{channel}-{unit}`.
- **Outputs** use `{MAC}_Output_{name}`, the format of the earlier `kuralabs/iotawatt_ha` fork.

> [!WARNING]
> **Home Assistant does not accept this change, and it is not expected to.** An IoTaWatt output has no permanent identifier, so its unique ID is built from the output's name. Home Assistant requires unique IDs that never change, and a name can change ([core PR #86834](https://github.com/home-assistant/core/pull/86834#issuecomment-1470576966), [developer documentation](https://developers.home-assistant.io/docs/entity_registry_index/)). A permanent output ID would have to come from the IoTaWatt firmware ([IoTaWatt feature request](https://community.iotawatt.com/t/feature-request-unique-identification-of-outputs/5444/3)). Read "Known problems" below before installing.

### Known problems

- **Renaming a channel or output on the IoTaWatt creates a new entity.** The old entity stops updating, and so do its history, dashboards, automations, helpers and Energy dashboard entries until you point them at the new one. Rename entities in Home Assistant instead, and avoid renaming channels and outputs on the device.
- **Going back to the built-in integration orphans the outputs.** It does not create output sensors, so they become unavailable. Inputs carry over with their history. The fixes below are also lost.

## Fixes over the built-in integration

These fixes are not tied to the output IDs. Details, limits and tests are in [docs/fixes.md](docs/fixes.md).

- **Statistics no longer jump after a restart.** The built-in integration can add an energy sensor's whole reading to its statistics after a restart, causing a one-off spike on the Energy dashboard. Here every energy reading carries its reset time (`last_reset`), including the first one after a restart.
- **Impossible readings are ignored.** An unstable IoTaWatt can send values such as -1e17 W. Readings far beyond any real value, and energy readings with an impossible reset time, make the sensor show *unknown* for that update instead of a garbage number.
- **Sensors that briefly disappear are kept.** If the IoTaWatt leaves a sensor out of one answer, the sensor shows *unavailable* instead of being deleted. It is removed only if it stays missing for about 5 minutes.
- **One retry before sensors go unavailable.** If an update from the IoTaWatt fails, it is tried once more after 2 seconds, so one dropped request no longer makes every sensor unavailable for 30 seconds.

## Installing

Requires Home Assistant 2026.11 or newer.

1. As an administrator, go to **Settings → Marketplace** and select **Add from link**.
2. Enter `https://github.com/petervk/iotawatt_ha` and select **Add**. If asked for the type, choose *Integration*.
3. Open **IoTaWatt (unique IDs + other fixes)** and select **Install**. This integration replaces the built-in IoTaWatt integration (it uses the same `iotawatt` domain), and Home Assistant asks you to confirm that.
4. Restart Home Assistant when asked.
5. If you are not already using IoTaWatt, add it under **Settings → Devices & services → Add integration**.

Back up Home Assistant before installing or updating.

**Already using the built-in integration?** Remove your existing IoTaWatt entry before installing. If you have a manual copy in `custom_components/iotawatt`, delete that folder first.

**Updating:** new versions appear as an update in Home Assistant. Each release's notes on the [Releases page](https://github.com/petervk/iotawatt_ha/releases) list the changes and the minimum Home Assistant version.

## Coming from `kuralabs/iotawatt_ha`

Installs that started from the `kuralabs/iotawatt_ha` 1.0.0 fork are migrated automatically on first start. Two things change: the per-period `_wh_last` sensors are no longer created, and input unique IDs are rewritten to the built-in format. Back up first. See [docs/migrating-from-kuralabs.md](docs/migrating-from-kuralabs.md) for the details.

### Outdated library (installs that started from `kuralabs/iotawatt_ha`)

If Home Assistant shows the repair notice "Outdated IoTaWatt library", see [Outdated library](docs/migrating-from-kuralabs.md#outdated-library) in the migration guide. It is harmless, and nothing needs to be done urgently.

## Reporting a problem

Please report problems with this integration [here, using the issue form](https://github.com/petervk/iotawatt_ha/issues/new/choose), not to Home Assistant or the IoTaWatt project. Include your versions and any IoTaWatt lines from the Home Assistant log.

## Credits

This integration is derived from the Home Assistant core IoTaWatt integration by Greg Diehl, Stefan Agner, Jean-Yves Avenard and Charles Garwood. The unique ID change for outputs comes from the [`kuralabs/iotawatt_ha`](https://github.com/kuralabs/iotawatt_ha) fork. An older version is at [`gtdiehl/iotawatt_ha`](https://github.com/gtdiehl/iotawatt_ha).

## License

Licensed under the [Apache License, Version 2.0](LICENSE). Modifications copyright (C) 2026 petervk. The original code's copyright remains with its authors (see Credits).
