=======================================
IoTaWatt integration for Home Assistant
=======================================

A HACS-installable fork of the Home Assistant core IoTaWatt integration that
gives **every** sensor, including outputs, a unique ID and a device.

Core only gives unique IDs to inputs, which means outputs cannot be renamed,
assigned to an area or used in the UI. See `core issue #87182`_.

.. _core issue #87182: https://github.com/home-assistant/core/issues/87182


.. warning::

   **This fork deliberately does something Home Assistant core does not allow,
   and the change is not expected to ever be accepted into core.** Read the
   section "Known problems" before installing.

What is different from core
===========================

- Unique ID for every sensor, formatted ``{MAC}_{Type}_{name}``. This matches
  the ID format of the earlier ``kuralabs/iotawatt_ha`` 1.0.0 release, so
  entities from that version are preserved when you upgrade.
- All sensors are attached to the IoTaWatt device.
- Per-period (``_last``) energy sensors are kept. Core hides them.

Everything else tracks the core integration (``ha-iotawattpy`` 0.3.0, config
entry ``runtime_data``, reactive power device class, guarded updates).

Note that the ID is based on the channel name configured on the IoTaWatt, so
renaming a channel on the device creates a new entity.


Known problems
==============

Why core rejects this
---------------------

Home Assistant requires an entity's unique ID to be unique, consistent and
immutable. Its `developer documentation`_ lists a device name as an
unacceptable source. IoTaWatt outputs have no hardware or firmware identifier,
so the output name is the only key available. This fork builds the ID from the
MAC address plus that name. Core maintainers rejected exactly this approach in
`core PR #86834`_ because the name is mutable. This fork does not change that
reasoning, and it is not expected to be accepted upstream.

.. _developer documentation: https://developers.home-assistant.io/docs/entity_registry_index/
.. _core PR #86834: https://github.com/home-assistant/core/pull/86834

What can go wrong
-----------------

- **Renaming a channel or output on the IoTaWatt creates a new entity.** The
  old entity is left behind, so its history, dashboards, automations, helpers
  and Energy dashboard entries stop updating until you repoint them. Rename
  the entity in Home Assistant instead, and avoid renaming channels on the
  device.
- **Leaving this fork loses continuity.** Core uses a different ID format for
  inputs (``{mac}-input-{channel}-{unit}``) and none for outputs. Switching
  back to core creates new entities for inputs and unattached entities for
  outputs.
- **It replaces the core integration** (same ``iotawatt`` domain). Home Assistant
  will log a warning that a custom integration is not tested.
- **It tracks one core release.** The code is ported from core 2026.10.2 and is
  not synced automatically. A future Home Assistant release can break it until
  the fork is updated, and core fixes and improvements arrive only when they
  are ported.
- **No support from Home Assistant or the IoTaWatt project.** Do not report
  problems with this fork to them.
- **Limited testing.** It is maintained for one home setup. Back up before
  installing, and keep a copy of any previous ``custom_components/iotawatt``
  folder so you can roll back.
- **It needs a recent Python.** The ``ha-iotawattpy`` 0.3.0 library requires
  Python 3.13.

A proper fix would be a persistent ID for each output in the IoTaWatt
firmware. That does not exist today.


Installing
==========

1. In HACS, add ``https://github.com/petervk/iotawatt_ha`` as a custom
   repository of type *Integration*.
2. Download it and restart Home Assistant.
3. If you already use the core integration, remove your existing IoTaWatt
   entry first, or migrate from a manual ``custom_components/iotawatt`` copy
   by deleting that folder before installing through HACS.

This custom integration uses the same ``iotawatt`` domain as core and replaces
it entirely. Requires Home Assistant 2026.10.2 or newer.


Why
===

https://github.com/home-assistant/core/issues/87182
https://github.com/home-assistant/core/pull/86834#issuecomment-1470576966
https://community.iotawatt.com/t/feature-request-unique-identification-of-outputs/5444/3


Credits
=======

All credits goes to the autors of this integration:

- Greg Diehl
- Stefan Agner
- Jean-Yves Avenard
- Charles Garwood

The unique ID change originates from the ``kuralabs/iotawatt_ha`` fork.

An older version of this integration can be found here:

https://github.com/gtdiehl/iotawatt_ha
https://github.com/kuralabs/iotawatt_ha


License
=======

::

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
