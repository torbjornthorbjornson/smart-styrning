# Daly ↔ Victron research notes

Started 2026-08-30.

## Goal

Find a robust way to get data from five Daly BMS units in Katharina into Node-RED / Raspberry Pi / Venus OS, preferably without relying on unsupported direct Daly→Victron CAN integration.

## Current hardware/context

- Katharina uses several Daly Smart Active Balance BMS units, including model family R24TH / 8–17S / 60 A charge / 60 A discharge / 1 A active balancing.
- Daly app exposes inverter protocol choices including `VICTRONENERGY`, `SMA`, `PYLON`, `GOODWE`, `DEYE`, etc., with communication method `CAN`.
- One Daly has been verified by app readback to store `VICTRONENERGY` + `CAN`.
- Cerbo GX VE.Can pinout verified:
  - pin 3 = NET-C / V- / CAN ground
  - pin 7 = CAN-H
  - pin 8 = CAN-L
- T568B cable mapping used:
  - pin 3 = white/green
  - pin 7 = white/brown
  - pin 8 = brown
- Daly cable mapping verified from Daly documentation/label:
  - black = GND
  - green = CAN-H
  - blue = CAN-L
- Continuity through the homemade cable has been verified end-to-end.
- 120 ohm termination across H/L measured 119.99 ohm.
- Cerbo tested with 250 and 500 kbit/s. Direct CAN currently gives `RX packets = 0` and CAN receive errors / ERROR-PASSIVE.

## Important conclusion so far

Do **not** assume that five independent Daly BMS units on Cerbo CAN will automatically be understood as one parallel battery bank. Victron can select a controlling BMS, but aggregation of several independent BMS units is a separate problem.

The cleaner target architecture is likely one of:

1. Five Daly BMS → serial/RS485/UART → software aggregator → one virtual battery in Venus OS.
2. Five Daly BMS → serial/RS485/UART → Raspberry Pi / Node-RED only, while existing Victron ESS control remains separate.
3. A Daly-native multi-pack/master solution, but only if interoperability between the existing R24TH units is confirmed.

## Off-Grid Garage / dbus-serialbattery findings

Off-Grid Garage has extensive practical material on connecting non-Victron BMS units to Venus OS. The key project is `dbus-serialbattery`.

### dbus-serialbattery

Original repository:
- https://github.com/Louisvdw/dbus-serialbattery

The original repository is archived and points to continued development here:
- https://github.com/mr-manuel/venus-os_dbus-serialbattery

Key facts from project documentation:

- Runs on Victron GX devices and Raspberry Pi running Venus OS.
- Supports serial connections including RS232, RS485 and TTL UART.
- Daly is explicitly supported as a BMS type.
- Publishes BMS information onto Venus OS D-Bus so it can appear as a battery monitor and can expose charge/discharge limits.
- The project documentation explicitly recommends **serial** for stable installations; Bluetooth and CAN can be less stable on some systems.
- For multiple batteries the documentation says a **battery aggregator is required** if the full system power is to be used.
- Daly-specific settings include battery capacity, current inversion and automatic SOC reset options.
- Cell data can be published to D-Bus.

Useful references:
- https://github.com/Louisvdw/dbus-serialbattery
- https://github.com/Louisvdw/dbus-serialbattery/blob/master/docs/docs/general/install.md
- https://github.com/Louisvdw/dbus-serialbattery/blob/master/etc/dbus-serialbattery/config.default.ini

### Multi-BMS evidence

There are real-world reports of installations with multiple BMS units using dbus-serialbattery plus a battery aggregator. One discussion mentions a system with six Daly BMS units and Venus OS, showing that multi-Daly setups are feasible in principle, although version compatibility and discovery stability matter.

Important: do not yet assume one RS485 adapter can address all five existing R24TH units. Need to confirm whether these specific BMS units support unique RS485 addresses / Modbus addressing, or whether each requires an individual serial adapter.

### Daly CAN direct to Victron

Historical reports are mixed. Some users report CAN frames reaching Venus OS but Daly not being recognized as a managed battery. Other users needed Daly WNT/interface boards and additional configuration. This reinforces the idea that direct CAN is not the cleanest path for this installation.

## Research questions for next passes

1. Identify the exact serial protocol used by Daly R24TH Smart Active Balance BMS:
   - UART protocol?
   - RS485 protocol?
   - Modbus RTU?
   - addressing support?
   - baud rate?
2. Determine whether five R24TH BMS units can share **one RS485 bus** with unique addresses.
3. If not, determine the simplest reliable hardware topology:
   - five USB↔RS485 adapters,
   - five USB↔UART/TTL adapters,
   - powered USB hub,
   - isolated vs non-isolated interfaces.
4. Study `venus-os_dbus-serialbattery` current multi-battery / aggregator documentation.
5. Determine whether the aggregator can safely provide:
   - combined SOC,
   - summed current,
   - combined capacity,
   - conservative max charge current,
   - conservative max discharge current,
   - cell min/max across all packs,
   - alarms if any one BMS objects.
6. Determine how Node-RED can consume the same per-BMS data without fighting the Venus driver.
7. Check Off-Grid Garage tutorials/videos specifically for Daly multi-BMS, serialbattery and battery aggregation.
8. Avoid making the virtual battery controlling/DVCC BMS until failure behaviour and all limits are verified.

## Working hypothesis

The most promising route is currently:

```text
Daly 1 ─┐
Daly 2 ─┤
Daly 3 ─┼─ serial interfaces ─→ Cerbo GX or Raspberry Pi
Daly 4 ─┤                         │
Daly 5 ─┘                         ├─ per-BMS data to Node-RED/MQTT
                                  └─ battery aggregator → one Venus OS battery
```

This preserves individual pack/cell visibility while allowing Victron to see one coherent battery bank rather than five unrelated BMS devices.

## Caution

Do not yet change the production battery-control architecture based on these notes. The next research step is to prove reliable communication with **one** R24TH over serial, then scale to two, then five, and only after that test aggregation behaviour.
