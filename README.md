# Jackery Navi 2000 — local Bluetooth for Home Assistant

Reads a **Jackery Navi 2000** balcony storage system over Bluetooth, with no Jackery app, account or cloud.
It works through a Bluetooth adapter on the Home Assistant host **or an ESPHome Bluetooth proxy**, whichever
hears the Navi best. HA picks the route; the integration does not care.

**Status: 0.1.0, read-only.** Sensors only, no controls. Tested against one Navi 2000 (gateway firmware
V1.1.7, power board V0.0.7, Wi-Fi V0.1.0): directly with the probe script, and end to end in Home Assistant
2026.2 through a local adapter, covering discovery, setup and polling. Not yet run through an ESPHome proxy.

## Requirements

- Home Assistant with the **Bluetooth** integration set up.
- A connectable route to the Navi: a local adapter, or an **ESPHome Bluetooth proxy with active connections**
  (the default on ESP32: `bluetooth_proxy: active: true`) within a few metres of the Navi.
- Nothing else connected to the Navi over Bluetooth while it polls. The Navi accepts **one** Bluetooth
  client at a time; see *Limitations*.

## Install

Copy `custom_components/jackery_navi/` into your HA configuration directory, so that you have
`/config/custom_components/jackery_navi/manifest.json`, then restart Home Assistant. Use the Samba, SSH or
File Editor add-on.

Or take the archive attached to each [GitHub release](https://github.com/longsleep/ha-jackery-navi/releases),
or build it yourself, and unpack it there. Its files are owned by 0:0 and carry their path from
`custom_components/` down:

```sh
make        # dist/jackery_navi-<version>-<commits since tag>.tar.gz, or -g<short ref> without a tag
tar -xzf jackery_navi-0.1.0-0.tar.gz -C /config    # on the HA host
```

Or with HACS: add this repository as a custom repository, category *Integration*, install, restart.

## Add the Navi

Either way ends with the same device:

- **Discovered.** When an adapter or proxy hears an advert named `Jackery_HA…`, *Settings → Devices &
  services* shows **Discovered: Jackery_HA…**. Click *Add* and confirm.
- **By hand.** *Settings → Devices & services → Add integration → Jackery Navi 2000 (local Bluetooth)*. You get
  a list of every Navi currently heard, with address and signal strength, plus *Enter a Bluetooth address…*.
  If no Navi is heard, the address form comes up directly.

The serial is taken from the advertised name (`Jackery_<serial>`). The first poll runs during setup. If the
Navi is out of range then, setup is retried automatically.

## What you get

One device, **Jackery Navi 2000**, with its gateway firmware on the device page, polled every 30 s.

| Entity | Unit | Notes |
|---|---|---|
| PV power | W | both strings |
| PV1 power, PV2 power | W | |
| AC grid port power | W | the Navi's grid-side port: positive when it feeds the house, negative when it charges from it |
| Smart plug power | W | the enrolled Shelly plugs together |
| Battery | % | state of charge |
| Battery energy | Wh | energy remaining |
| Battery state | — | idle / charging / discharging |
| Battery voltage | V | |
| Battery current | A | positive while charging |
| Battery power | W | positive while charging |
| Grid voltage, Grid frequency | V, Hz | |
| **PV energy**, PV1 energy, PV2 energy | kWh | lifetime counters |
| **Battery energy charged**, **Battery energy discharged** | Wh | lifetime counters |
| **AC grid port energy in**, **AC grid port energy out** | kWh | lifetime counters |
| Charge limit, Discharge limit | % | diagnostic |
| Max feed-in | W | diagnostic |
| Work mode (raw), AC socket (raw) | — | diagnostic; raw device values, legend not yet mapped |
| Battery capacity | Wh | diagnostic |
| Conversion loss | W | diagnostic; power lost in conversion, e.g. ~110 W while charging at 1.2 kW |
| PCS heat sink temperature, PCS inverter temperature | °C | diagnostic |
| Power board firmware, Wi-Fi firmware | — | diagnostic |
| Wi-Fi signal, Grid power (PCS) | dBm, W | diagnostic, **disabled by default** |

Only readings whose meaning was cross-checked on a real Navi are included, most of them also against the
vendor's own property names. The Navi reports more, and some widely circulated labels turned out to be
wrong, so those stay out until they are understood.

**The Shelly plugs** the Navi controls are not exposed individually here. Add them with Home Assistant's
built-in **Shelly** integration, which talks to them directly and does not disturb their link to the Navi.

## Energy dashboard

The lifetime counters are kept by the Navi itself, so they survive Home Assistant restarts and missed polls.
In *Settings → Dashboards → Energy*:

| Section | Use |
|---|---|
| **Solar panels → Solar production** | *PV energy*, or *PV1 energy* and *PV2 energy* separately |
| **Home battery storage** | energy going in: *Battery energy charged*; energy coming out: *Battery energy discharged* |
| **Electricity grid** | your house meter, if HA has one (smart meter, Shelly 3EM …). The Navi has no meter of its own enrolled, so it cannot supply this. |
| **Individual devices** (optional) | *AC grid port energy out* (what the Navi delivered to the house) and *AC grid port energy in* (what it drew from the house circuit to charge) |

Without a house meter, the dashboard still shows solar production and battery flows. HA's grid and
self-consumption figures need the meter. The PV counters count energy into the Navi, before conversion
losses.

## Limitations

- **One Bluetooth client at a time.** Each poll holds the Navi's only Bluetooth connection for about 5 s.
  During that time the Jackery app cannot use its own Bluetooth mode. Its normal cloud mode is unaffected.
- **Read-only.** No mode, limit or socket control yet.
- **Navi 2000 only.** The HomePower 2000 Ultra (`Jackery_HL…`) speaks the same protocol, but its readings have
  not been mapped here, so it is not matched.

## How it talks to the Navi

The Navi's Bluetooth link is Espressif **BluFi**: GATT service `0xFFFF`, write `0xFF01` (with response only),
notify `0xFF02`. Jackery's JSON requests (`device_get`, `data_get`) travel unencrypted in BluFi custom-data
frames. Readings are numeric "meter IDs" per sub-device (`ems_`, `pcs_`, `bms1_` + serial). The details are in
`custom_components/jackery_navi/navi_ble.py`, which does not depend on Home Assistant.

## Debugging

```yaml
logger:
  logs:
    custom_components.jackery_navi: debug
```

This logs every frame in both directions as hex.

`scripts/probe.py` runs the integration's protocol code from any machine with Bluetooth, with no Home
Assistant, and prints the identity and every reading. It needs `bleak` and `bleak-retry-connector`. Stop
anything else polling the Navi first.

```sh
python scripts/probe.py 74:4D:BD:XX:XX:XX
```

## Acknowledgements

The protocol work started from public material:

- [Wlad2288/Ultra_Jack](https://github.com/Wlad2288/Ultra_Jack), a Bluetooth client for the HomePower 2000
  Ultra, which showed that Jackery's JSON commands travel in BluFi custom-data frames.
- [sdeigm/uni-meter issue #265](https://github.com/sdeigm/uni-meter/issues/265), where Navi owners shared a
  Bluetooth capture and notes on running the Navi locally.
- Espressif's [BluFi documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/ble/blufi.html),
  for the framing.

No code was copied from these. The meter IDs were mapped against a real Navi 2000.

## Licence

Licensed under the Apache License, Version 2.0 — see [LICENSE](LICENSE).

Copyright 2026 Simon Eisenmann. See [NOTICE](NOTICE). Not affiliated with or endorsed by Jackery; "Jackery"
and "Navi" are trademarks of their respective owners.
