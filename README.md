# IoTaWatt integration for Home Assistant

A HACS-installable fork of the Home Assistant core IoTaWatt integration that gives **every** sensor, including outputs, a unique ID and a device.

Core only gives unique IDs to inputs, which means outputs cannot be renamed, assigned to an area or used in the UI. See [core issue #87182](https://github.com/home-assistant/core/issues/87182).

> [!IMPORTANT]
> **Version 2.2.0 and newer REQUIRE Home Assistant 2026.11.0 or newer.** Do not install or update to it on an older Home Assistant: the integration will fail to load. On 2026.10.x, stay on version 2.1.2.

> [!WARNING]
> **This fork deliberately does something Home Assistant core does not allow, and the change is not expected to ever be accepted into core.** Read the section "Known problems" before installing.

> [!NOTE]
> **About this project:** This integration was written by Claude, an AI assistant made by Anthropic, at the request of the repository owner, who is not a programmer. It has been tested only on one home setup. No one here has the experience to support it as a professional would, so please read "Known problems" and keep backups.

## What is different from core

There are four functional differences. Everything else is identical to core (`ha-iotawattpy` 0.3.0, config entry `runtime_data`, reactive power device class, guarded updates, no per-period `_wh_last` sensors).

1. **Outputs also get a unique ID and a device.** Not expected to be accepted by core, see "Known problems".
2. **The energy sensors carry `last_reset` on every state, including the first one after a restart.** This fixes a statistics problem in core, see "Improvement over core" below. It is intended to be proposed to core.
3. **Impossible readings are rejected: the sensor shows unknown instead of the garbage number.** See "Rejecting impossible readings" below. The limits are a guess.
4. **Sensors that briefly vanish from the IoTaWatt's answer are kept instead of deleted.** See "Keeping sensors that briefly vanish" below. The waiting time is a guess.

Unique IDs:

- **Inputs** use exactly the same unique ID as core: `{mac}-input-{channel}-{unit}`.
- **Outputs** use `{MAC}_Output_{name}`, the ID format of `kuralabs/iotawatt_ha` 1.0.0. This is the one thing core does not do.
- All sensors are attached to the IoTaWatt device.

The output ID is based on the output name configured on the IoTaWatt, so renaming an output on the device creates a new entity.

### Improvement over core: statistics no longer inflate after a restart

**The problem in core.** The IoTaWatt energy sensors have the `total` state class, so Home Assistant needs a `last_reset` timestamp on every state to compile their long-term statistics (which feed the Energy dashboard). Core only sets `last_reset` when the first data update arrives, so the **first state written after Home Assistant starts has no `last_reset`**, and the following states do.

Home Assistant's statistics compiler stores `last_reset` for a five-minute window only if the window's last state has it. If the first state after a restart happens to be the last state of its window, the next window starts without a known `last_reset`, sees the attribute appear, and treats it as a counter reset. It then adds the sensor's **entire reading** to the statistics sum. The live sensor values stay correct; only the statistics (and so the Energy dashboard and any statistics-based card) show a large one-off jump, for every energy sensor at once. Whether it happens depends on timing, roughly one restart in ten with the default 30 second update interval.

Seen on a real install after a restart following a 7 minute outage: the solar energy statistics gained about 16.3 kWh in one five-minute window, grid import (which was idle) gained 8.7 kWh, and every other energy sensor gained roughly its own reading. A brand-new installation is affected the same way: its first statistics window is inflated.

**The fix here.** `last_reset` is a property computed from the current coordinator data each time a state is written, instead of a value stored on the first update. Every state, including the first, carries it. It is also only reported for sensors with the `total` state class, which is the only class where Home Assistant allows it.

**How it is tested.** `tests/test_last_reset.py` includes a test that runs Home Assistant's real recorder and statistics compiler through a restart. It fails on the core behaviour (the statistics sum jumps by the sensor's full value) and passes with this fix.

**What the fix does not do.** It prevents new occurrences. It does not repair statistics that were already inflated before you installed it.

### Rejecting impossible readings

> [!IMPORTANT]
> **The limits below are a guess.** They are not IoTaWatt specifications and were not checked against the hardware. They are deliberately set **far beyond any normal reading**, so a healthy installation should never come near them. If you ever see a rejection warning in the log for a reading that was real, please report it, because that means a limit is too low.

**The problem.** An unstable IoTaWatt can return impossible numbers, for example about -1e17 W or 9.7e18 Wh. The integration used to pass these straight through, and they then ruined power graphs, long-term statistics, the Energy dashboard and any helper built on the sensors (sums, Riemann integrals, costs).

**What happens now.** If a reading is beyond the limit for its type, that one sensor reports **unknown** for that update, and a warning is written to the log (at most once an hour per sensor). The next valid reading restores it. Other sensors are not affected. Negative readings stay allowed where they are real, such as power flowing back to the grid.

| Reading | Rejected when | How the limit was chosen (all guesses) |
| --- | --- | --- |
| Voltage | above 1,200 V | 600 V as a base number, doubled |
| Current | above 10,000 A | 5,000 A as a base number, doubled |
| Power, apparent power, reactive power | absolute value above 10.4 MW | 600 V x 5,000 A x 1.732 (three phase) = 5.2 MW, doubled |
| Energy (Wh) and reactive energy (VARh) | absolute value above 250 MWh | 5.2 MW for 24 hours = 125 MWh (the energy sensors reset daily), doubled |
| Frequency | below 0 Hz or above 100 Hz | mains is 50 or 60 Hz |
| Power factor | absolute value above 1.1 | a real power factor cannot exceed 1 |

The limits are each doubled on their own, so they are **not** consistent with each other as a product: 1,200 V x 10,000 A is much more than 10.4 MW. That does not matter in practice, because the garbage seen so far (around 1e17) is billions of times above every limit.

NaN and infinite values are rejected too. Sensors with no limit (any unit this integration does not know) are left alone.

**What this does not do.**
- It does not repair statistics that already contain garbage.
- It does not stop the IoTaWatt from crashing or producing bad data; it only keeps the bad data out of Home Assistant.
**The reset time is checked too (energy sensors only).** Each energy reading comes with the time its daily count started (`last_reset`). If that time changed to something wrong, Home Assistant's statistics would see a counter reset and add the sensor's whole reading, even if the reading itself looked normal. So a reset time that cannot be read, is more than 48 hours in the past or is more than 15 hours in the future is rejected the same way: the sensor reports unknown for that update, and the last good reset time is kept. The window is wide because the IoTaWatt reports its own local time and its time zone is not known to the integration. **These two numbers are guesses as well**, and a wrong reset time inside the window (for example yesterday's midnight in place of today's) is not caught. Whether an unstable IoTaWatt ever sends a wrong reset time is not known; this is a precaution.

- It does not catch a wrong value that is still inside the limits. A plausible but incorrect reading passes.
- Helpers built on the sensors (sum groups, Riemann integrals) will see unknown for the affected update. How they treat that depends on their own settings.

The limits live in `custom_components/iotawatt/limits.py` and are covered by `tests/test_limits.py`. The check is kept in its own small module so it could be proposed to core separately from the other changes in this fork.

### Keeping sensors that briefly vanish

> [!IMPORTANT]
> **The waiting time below is a guess.** It was not derived from how the IoTaWatt actually behaves. This problem was found by reading the code and reproduced in a test; it has not been seen on a real installation.

**The problem (also in core, for inputs).** On every update the IoTaWatt sends the list of its channels and outputs. A sensor missing from that list is treated as removed from the device, and its entity is deleted from Home Assistant. If an unstable IoTaWatt sends one incomplete list, the entities are deleted, and they do not come back until Home Assistant restarts or the integration is reloaded. In core this affects inputs; in this fork it would also affect outputs, because they have unique IDs.

**What happens now.** A sensor missing from the list is kept and shown as **unavailable**. If it is back on a later update, it simply continues. Only after it has been missing for **10 successful updates in a row (about 5 minutes)** is the entity deleted, which is what should happen when you really remove or rename a channel or output on the IoTaWatt. A warning is written to the log when a sensor goes missing and when it is finally removed. A sensor that returns after being removed is created again without a restart.

**What changes for you.** After you remove or rename a channel or output on the IoTaWatt, the old entity stays for about 5 minutes as unavailable before it disappears. Before, it disappeared at the next update.

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
- **Leaving this fork also brings back the statistics problem** described under "Improvement over core", until it is fixed in core.
- **It replaces the core integration** (same `iotawatt` domain). Home Assistant will log a warning that a custom integration is not tested.
- **It tracks one core release.** The code is ported from core 2026.11.0 and is not synced automatically. A future Home Assistant release can break it until the fork is updated, and core fixes and improvements arrive only when they are ported.
- **No support from Home Assistant or the IoTaWatt project.** Do not report problems with this fork to them.
- **Limited testing.** It is maintained for one home setup. Back up before installing, and keep a copy of any previous `custom_components/iotawatt` folder so you can roll back.
- **It needs a recent Python.** The code needs Python 3.14, which Home Assistant 2026.11 already uses.

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

This custom integration uses the same `iotawatt` domain as core and replaces it entirely. **Requires Home Assistant 2026.11.0 or newer** (version 2.2.0 and later). On Home Assistant 2026.10.x, use version 2.1.2.

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
