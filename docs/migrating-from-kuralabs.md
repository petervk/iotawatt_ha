# Coming from `kuralabs/iotawatt_ha`

## Breaking changes from `kuralabs/iotawatt_ha` 1.0.0

- **The per-period `_wh_last` energy sensors are no longer created**, matching core. Existing `_wh_last` entities are not deleted by this integration; they remain in the entity registry and show as unavailable until you remove them yourself. Check that nothing (dashboards, automations, alerts, YAML) uses them first.
- **Input unique IDs are rewritten to core's format on startup.** Entity IDs, names, history and settings are kept.

## Migration

Supported starting point: **`kuralabs/iotawatt_ha` 1.0.0 only.** Other versions are untested.

On startup, the integration rewrites the unique ID of each existing input sensor from `{MAC}_Input_{name}[.wh]` to core's `{mac}-input-{channel}-{unit}`. The migration:

- changes unique IDs only, never entity IDs;
- never deletes anything;
- skips and logs a warning when the new ID already exists on another entity (for example, duplicated entities from an earlier channel rename), so you can sort those out by hand;
- leaves renamed or no-longer-present channels alone;
- is safe to run repeatedly.

Back up before upgrading. Old versions of this integration do not recognise the new input IDs, so rolling back means restoring the backup.

If you later switch to core, input sensors keep their entities and history. Only outputs are affected, because core does not create them.


## Outdated library

The original integration installed an old `iotawattpy` 0.1.0 package. It contains the same Python module as `ha-iotawattpy`, which this integration needs, and Home Assistant never removes old packages. On such installs the old code can end up loaded instead of the new one.

Since v2.1.1 the integration detects this and works around it, so it keeps running and you do not have to do anything. A Repair notice ("Outdated IoTaWatt library") tells you it happened. It is harmless, but you are running older library code than core does.

To remove the old package (optional, advanced), run this inside the Home Assistant core container, then restart Home Assistant:

```
docker exec homeassistant pip uninstall -y iotawattpy
docker exec homeassistant pip install --force-reinstall --no-deps ha-iotawattpy==0.3.0
```

Versions 2.1.0 and earlier fail to start (or silently use the old code) on such installs, so use v2.1.1 or newer.

