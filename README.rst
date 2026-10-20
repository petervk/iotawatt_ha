=======================================
IoTaWatt integration for Home Assistant
=======================================

A HACS-installable fork of the Home Assistant core IoTaWatt integration that
gives **every** sensor, including outputs, a unique ID and a device.

Core only gives unique IDs to inputs, which means outputs cannot be renamed,
assigned to an area or used in the UI. See `core issue #87182`_.

.. _core issue #87182: https://github.com/home-assistant/core/issues/87182


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
