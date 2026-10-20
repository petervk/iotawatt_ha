# IoTaWatt integration for Home Assistant

A HACS-installable fork of the Home Assistant core IoTaWatt integration that gives **every** sensor, including outputs, a unique ID and a device.

Core only gives unique IDs to inputs, which means outputs cannot be renamed, assigned to an area or used in the UI. See [core issue #87182](https://github.com/home-assistant/core/issues/87182).

> [!WARNING]
> **This fork deliberately does something Home Assistant core does not allow, and the change is not expected to ever be accepted into core.** Read the section "Known problems" before installing.

> [!NOTE]
> **About this project:** This integration was written by Claude, an AI assistant made by Anthropic, at the request of the repository owner, who is not a programmer. It has been tested only on one home setup. No one here has the experience to support it as a professional would, so please read "Known problems" and keep backups.

## What is different from core

The only functional change is that **outputs also get a unique ID and a device**. Everything else is identical to core (`ha-iotawattpy` 0.3.0, config entry `runtime_data`, reactive power device class, guarded updates, no per-period `_wh_last` sensors).

- **Inputs** use exactly the same unique ID as core: `{mac}-input-{channel}-{unit}`.
- **Outputs** use `{MAC}_Output_{name}`, the ID format of `kuralabs/iotawatt_ha` 1.0.0. This is the one thing core does not do.
- All sensors are attached to the IoTaWatt device.

The output ID is based on the output name configured on the IoTaWatt, so renaming an output on the device creates a new entity.

### Breaking changes from `kuralabs/iotawatt_ha` 1.0.0

- **The per-period `_wh_last` energy sensors are no longer created**, matching core. Existing `_wh_last` entities are not deleted by this integration; they remain in the entity registry and show as unavailable until you remove them yourself. Check that nothing (dashboards, automations, alerts, YAML) uses them first.
- **Input unique IDs are rewritten to core's format on startup.** Entity IDs, names, history and settings are kept.

### Migration

Supported starting point: **`kuralabs/iotawatt_ha` 1.0.0 only.** Other versions are untested.

On startup, the integration rewrites the unique ID of each existing input sensor from `{MAC}_Input_{name}[.wh]` to core's `{mac}-input-{channel}-{unit}`. The migration:

- changes unique IDs only, never entity IDs;
- never deletes anything;
- skips and logs a warning when the new ID already exists on another entity (for example, duplicated entities from an earlier channel rename), so you can sort those out by hand;
- leaves renamed or no-longer-present channels alone;
- is safe to run repeatedly.

Back up before upgrading. Old versions of this integration do not recognise the new input IDs, so rolling back means restoring the backup.

If you later switch to core, input sensors keep their entities and history. Only outputs are affected, because core does not create them.

## Known problems

### Why core rejects this

Home Assistant requires an entity's unique ID to be unique, consistent and immutable. Its [developer documentation](https://developers.home-assistant.io/docs/entity_registry_index/) lists a device name as an unacceptable source. IoTaWatt outputs have no hardware or firmware identifier, so the output name is the only key available. This fork builds the ID from the MAC address plus that name. Core maintainers rejected exactly this approach in [core PR #86834](https://github.com/home-assistant/core/pull/86834) because the name is mutable. This fork does not change that reasoning, and it is not expected to be accepted upstream.

### What can go wrong

- **Renaming a channel or output on the IoTaWatt creates a new entity.** The old entity is left behind, so its history, dashboards, automations, helpers and Energy dashboard entries stop updating until you repoint them. Rename the entity in Home Assistant instead, and avoid renaming channels on the device.
- **Leaving this fork affects outputs.** Core does not create output sensors, so after switching back to core they become unavailable orphans. Inputs carry over, because they use core's ID format.
- **It replaces the core integration** (same `iotawatt` domain). Home Assistant will log a warning that a custom integration is not tested.
- **It tracks one core release.** The code is ported from core 2026.10.2 and is not synced automatically. A future Home Assistant release can break it until the fork is updated, and core fixes and improvements arrive only when they are ported.
- **No support from Home Assistant or the IoTaWatt project.** Do not report problems with this fork to them.
- **Limited testing.** It is maintained for one home setup. Back up before installing, and keep a copy of any previous `custom_components/iotawatt` folder so you can roll back.
- **It needs a recent Python.** The `ha-iotawattpy` 0.3.0 library requires Python 3.13.

### Outdated library (installs that started from `kuralabs/iotawatt_ha`)

The original integration installed an old `iotawattpy` 0.1.0 package. It contains the same Python module as `ha-iotawattpy`, which this integration needs, and Home Assistant never removes old packages. On such installs the old code can end up loaded instead of the new one.

Since v2.1.1 the integration detects this and works around it, so it keeps running and you do not have to do anything. A Repair notice ("Outdated IoTaWatt library") tells you it happened. It is harmless, but you are running older library code than core does.

To remove the old package (optional, advanced), run this inside the Home Assistant core container, then restart Home Assistant:

```
docker exec homeassistant pip uninstall -y iotawattpy
docker exec homeassistant pip install --force-reinstall --no-deps ha-iotawattpy==0.3.0
```

Versions 2.1.0 and earlier fail to start (or silently use the old code) on such installs, so use v2.1.1 or newer.

A proper fix would be a persistent ID for each output in the IoTaWatt firmware. That does not exist today.

## Installing

1.  In HACS, add `https://github.com/petervk/iotawatt_ha` as a custom repository of type *Integration*.
2.  Download it and restart Home Assistant.
3.  If you already use the core integration, remove your existing IoTaWatt entry first, or migrate from a manual `custom_components/iotawatt` copy by deleting that folder before installing through HACS.

This custom integration uses the same `iotawatt` domain as core and replaces it entirely. Requires Home Assistant 2026.10.2 or newer.

## Why

- <https://github.com/home-assistant/core/issues/87182>
- <https://github.com/home-assistant/core/pull/86834#issuecomment-1470576966>
- <https://community.iotawatt.com/t/feature-request-unique-identification-of-outputs/5444/3>

## Credits

All credits go to the authors of this integration:

- Greg Diehl
- Stefan Agner
- Jean-Yves Avenard
- Charles Garwood

The unique ID change originates from the `kuralabs/iotawatt_ha` fork.

An older version of this integration can be found here:

- <https://github.com/gtdiehl/iotawatt_ha>
- <https://github.com/kuralabs/iotawatt_ha>

## License

This project is licensed under the Apache License, Version 2.0. The `LICENSE` file contains the full text.

Modifications Copyright (C) 2026 petervk. Original code copyright remains with its authors (see Credits above); this fork is derived from the Home Assistant core IoTaWatt integration and the `kuralabs/iotawatt_ha` fork, both Apache 2.0.

The standard license notice from the original project:

```
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
```
