# Fixes over the built-in integration

These four changes are independent of the unique IDs for outputs. Each could be proposed to Home Assistant core on its own.

## Statistics no longer jump after a restart

**The problem in core.** The IoTaWatt energy sensors have the `total` state class, so Home Assistant needs a `last_reset` timestamp on every state to compile their long-term statistics (which feed the Energy dashboard). Core only sets `last_reset` when the first data update arrives, so the **first state written after Home Assistant starts has no `last_reset`**, and the following states do.

Home Assistant's statistics compiler stores `last_reset` for a five-minute window only if the window's last state has it. If the first state after a restart happens to be the last state of its window, the next window starts without a known `last_reset`, sees the attribute appear, and treats it as a counter reset. It then adds the sensor's **entire reading** to the statistics sum. The live sensor values stay correct; only the statistics (and so the Energy dashboard and any statistics-based card) show a large one-off jump, for every energy sensor at once. Whether it happens depends on timing, roughly one restart in ten with the default 30 second update interval.

Seen on a real install after a restart following a 7 minute outage: the solar energy statistics gained about 16.3 kWh in one five-minute window, grid import (which was idle) gained 8.7 kWh, and every other energy sensor gained roughly its own reading. A brand-new installation is affected the same way: its first statistics window is inflated.

**The fix here.** `last_reset` is a property computed from the current coordinator data each time a state is written, instead of a value stored on the first update. Every state, including the first, carries it. It is also only reported for sensors with the `total` state class, which is the only class where Home Assistant allows it.

**How it is tested.** `tests/test_last_reset.py` includes a test that runs Home Assistant's real recorder and statistics compiler through a restart. It fails on the core behaviour (the statistics sum jumps by the sensor's full value) and passes with this fix.

**What the fix does not do.** It prevents new occurrences. It does not repair statistics that were already inflated before you installed it.

## Rejecting impossible readings

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

**The reset time is checked too (energy sensors only).** Each energy reading comes with the time its daily count started (`last_reset`). If that time changed to something wrong, Home Assistant's statistics would see a counter reset and add the sensor's whole reading, even if the reading itself looked normal. So a reset time that cannot be read, is more than 48 hours in the past or is more than 15 hours in the future is rejected the same way: the sensor reports unknown for that update, and the last good reset time is kept. The window is wide because the IoTaWatt reports its own local time and its time zone is not known to the integration. **These two numbers are guesses as well**, and a wrong reset time inside the window (for example yesterday's midnight in place of today's) is not caught. Whether an unstable IoTaWatt ever sends a wrong reset time is not known; this is a precaution.

**What this does not do.**
- It does not repair statistics that already contain garbage.
- It does not stop the IoTaWatt from crashing or producing bad data; it only keeps the bad data out of Home Assistant.
- It does not catch a wrong value that is still inside the limits. A plausible but incorrect reading passes.
- Helpers built on the sensors (sum groups, Riemann integrals) will see unknown for the affected update. How they treat that depends on their own settings.

The limits live in `custom_components/iotawatt/limits.py` and are covered by `tests/test_limits.py`. The check is kept in its own small module so it could be proposed to core separately from the other changes in this fork.

## Keeping sensors that briefly vanish

> [!IMPORTANT]
> **The waiting time below is a guess.** It was not derived from how the IoTaWatt actually behaves. This problem was found by reading the code and reproduced in a test; it has not been seen on a real installation.

**The problem (also in core, for inputs).** On every update the IoTaWatt sends the list of its channels and outputs. A sensor missing from that list is treated as removed from the device, and its entity is deleted from Home Assistant. If an unstable IoTaWatt sends one incomplete list, the entities are deleted, and they do not come back until Home Assistant restarts or the integration is reloaded. In core this affects inputs; in this fork it would also affect outputs, because they have unique IDs.

**What happens now.** A sensor missing from the list is kept and shown as **unavailable**. If it is back on a later update, it simply continues. Only after it has been missing for **10 successful updates in a row (about 5 minutes)** is the entity deleted, which is what should happen when you really remove or rename a channel or output on the IoTaWatt. A warning is written to the log when a sensor goes missing and when it is finally removed. A sensor that returns after being removed is created again without a restart.

**What changes for you.** After you remove or rename a channel or output on the IoTaWatt, the old entity stays for about 5 minutes as unavailable before it disappears. Before, it disappeared at the next update.

## One retry before sensors go unavailable

**The problem (also in core).** The integration asks the IoTaWatt for new readings every 30 seconds. If one request fails (a dropped Wi-Fi packet, a timeout, a garbled answer), the whole update fails and **every** IoTaWatt sensor shows unavailable until the next update 30 seconds later. Helpers built on the sensors (sums, roll-ups, costs) see that gap. On a real install with a weak Wi-Fi signal this happened several times a week, each time for about 31 seconds.

**What happens now.** A failed request is tried **once more after 2 seconds** within the same update. If the second try works, the update succeeds with fresh readings and nothing goes unavailable. If it fails too, the sensors go unavailable exactly as in core. Old readings are never shown as current: this follows Home Assistant's rule that sensors must be unavailable when the device cannot be read.

**What changes for you.** At most one extra request to the IoTaWatt when a request fails, and nothing at all when it works. A failed update now takes about 2 seconds longer before the sensors go unavailable. Recovered retries are logged at debug level only; enable debug logging for `custom_components.iotawatt` to see them.

**How it is tested.** `tests/test_retry.py`: one failure is retried and gives fresh values; two failures make the sensors unavailable and the next good update restores them; a healthy update makes exactly one request.
