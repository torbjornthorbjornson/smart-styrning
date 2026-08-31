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

The cleaner target architecture is now increasingly likely to be:

1. Five Daly BMS → **one isolated RS485 adapter, if R24TH accepts unique board numbers** → `dbus-serialbattery` → five individual Venus D-Bus batteries.
2. Per-BMS data → MQTT JSON → Node-RED for logging, diagnostics and custom logic.
3. Five D-Bus batteries → battery aggregator → **one virtual bank** for Venus OS/Victron.
4. Keep direct Daly→Victron CAN as a secondary experiment rather than the main design path.

## Off-Grid Garage / dbus-serialbattery findings

Off-Grid Garage has extensive practical material on connecting non-Victron BMS units to Venus OS. The key project is `dbus-serialbattery`.

### dbus-serialbattery

Original repository:
- https://github.com/Louisvdw/dbus-serialbattery

Continued/current development:
- https://github.com/mr-manuel/venus-os_dbus-serialbattery
- https://mr-manuel.github.io/venus-os_dbus-serialbattery_docs/

Key facts from project documentation/source:

- Runs on Victron GX devices and Raspberry Pi running Venus OS.
- Supports serial connections including RS232, RS485 and TTL UART.
- Daly is explicitly supported as a BMS type.
- Publishes BMS information onto Venus OS D-Bus so it can appear as a battery monitor and can expose charge/discharge limits.
- Serial is explicitly recommended over Bluetooth for stable installations.
- For multiple batteries a **battery aggregator is required** if the whole system is to be represented/controlled as one bank.
- Daly-specific settings include battery capacity, current inversion and automatic SOC reset options.
- Cell data can be published to D-Bus.
- Current source code polls Daly at 9600 baud and has support for per-device addresses.

Useful references:
- https://github.com/mr-manuel/venus-os_dbus-serialbattery
- https://mr-manuel.github.io/venus-os_dbus-serialbattery_docs/general/connect/
- https://mr-manuel.github.io/venus-os_dbus-serialbattery_docs/general/install/
- https://github.com/mr-manuel/venus-os_dbus-serialbattery/blob/master/dbus-serialbattery/config.default.ini

### Multi-BMS evidence

There are real-world reports of installations with multiple BMS units using dbus-serialbattery plus a battery aggregator. More importantly, current `dbus-serialbattery` explicitly supports **multiple Daly BMS on the same RS485 adapter**. This feature was added in release `v1.5.20241202`.

The driver documentation requires each Daly to have a unique board number, set with Daly's **Windows BmsMonitor/BMS Tools**. It explicitly warns that setting the board number in the mobile `SMART BMS` app does **not** set it correctly for this purpose.

For five Daly units, the documented board/address mapping is:

| Daly board number | dbus-serialbattery address |
| --- | --- |
| 1 | `0x40` |
| 2 | `0x41` |
| 3 | `0x42` |
| 4 | `0x43` |
| 5 | `0x44` |

Proposed configuration if R24TH accepts these board numbers:

```ini
BMS_TYPE = Daly
BATTERY_ADDRESSES = 0x40, 0x41, 0x42, 0x43, 0x44
```

The source code confirms this is not merely documentation wording: the serial process iterates over all configured `BATTERY_ADDRESSES` on the **same serial port**, probes each address, and creates a separate D-Bus battery instance for every BMS found.

The Daly driver builds an `A5`-framed request and inserts the configured address byte into every command. The source comment explicitly notes `Board No 1 = 0x40; Board No 2 = 0x41, ...`. Therefore the implemented legacy Daly serial driver should not be described casually as ordinary register/function-code Modbus RTU even though the documentation groups it under RS485/Modbus and uses the wording "MODBUS address".

Before multi-pack use, the docs also say:

- set Daly `Sleep time(S)` to `65535` so the BMS does not sleep;
- give each BMS a different `Battery code`;
- set each BMS to a different board number using the Windows software.

Sources:
- https://mr-manuel.github.io/venus-os_dbus-serialbattery_docs/general/connect/
- https://github.com/mr-manuel/venus-os_dbus-serialbattery/releases/tag/v1.5.20241202
- https://github.com/mr-manuel/venus-os_dbus-serialbattery/blob/master/dbus-serialbattery/bms/daly.py
- https://github.com/mr-manuel/venus-os_dbus-serialbattery/blob/master/dbus-serialbattery/dbus-serialbattery.py

### Important correction to earlier Off-Grid Garage interpretation

Off-Grid Garage's phrase **“Only one device is necessary, even if you have parallel BMS!”** appears in the section about the Waveshare gateway used with **JK-Inverter BMS / Gobel Home Assistant integration**. It must **not** be used as evidence that one adapter automatically works with parallel Daly units.

The Daly/multi-Daly evidence instead comes from `dbus-serialbattery` itself.

Off-Grid Garage does provide strong practical support for the general path:

- his Venus OS workshop connects two JK BMS units and one Daly simultaneously through `dbus-serialbattery`;
- he has tested several USB↔RS485 adapters successfully;
- he states that a Daly USB-UART cable can connect a Daly Smart BMS to Venus OS without an additional protocol adapter;
- he shows building common data buses by paralleling suitable manufacturer-specific communication connectors.

Source:
- https://off-grid-garage.com/bms-communication/

### Daly CAN direct to Victron

Historical reports are mixed. Some users report CAN frames reaching Venus OS but Daly not being recognized as a managed battery. Other users needed Daly WNT/interface boards and additional configuration. This reinforces the idea that direct CAN is not the cleanest path for this installation.

`dbus-serialbattery` also contains a Daly CAN driver, so a future CAN experiment can be made through the software driver rather than assuming Daly's `VICTRONENERGY` inverter profile is natively understood by Venus OS.

## R24TH-specific status

The remaining uncertainty has narrowed substantially.

Secondary copies of Daly documentation for the R24TH / Smart Active Balance family describe UART, RS485 and CAN interfaces, with RS485 commonly at 9600 bit/s. This matches the communication method used by `dbus-serialbattery`'s Daly serial driver.

However, I have **not yet found a primary Daly document for the exact R24TH revision that proves its board number can be changed to 1…5 and that five R24TH units can share one RS485 pair**.

Therefore:

- one-adapter/five-address operation is now a **high-confidence test path**, because it is explicitly supported for Daly by the active driver;
- it is **not yet proven on these exact R24TH units** until two physical units successfully answer on `0x40` and `0x41` on the same A/B pair.

Current Daly Smart BMS material also describes RS485 multi-pack/addressed systems and Victron integration through a GX/custom-driver/protocol-converter approach, which supports the strategic direction, but broad Daly-family documentation must not be treated as exact R24TH proof.

## Clean Node-RED / MQTT path

A particularly clean architecture is available without letting two programs fight over the RS485 device.

`dbus-serialbattery` can publish **all battery data for every individual battery as one JSON message per battery** by enabling:

```ini
PUBLISH_BATTERY_DATA_AS_JSON = True
```

Each battery then gets its own Venus MQTT topic:

```text
/N/<VRM_ID>/battery/<BATTERY_INSTANCE>/JsonData
```

This is important for our design:

```text
5 x Daly R24TH
      │
      └─ RS485 bus ─ isolated USB/RS485 ─ Cerbo/Venus OS
                                          │
                                   dbus-serialbattery
                                    │   │   │   │   │
                                    B1  B2  B3  B4  B5
                                    │   │   │   │   │
                                    └──── MQTT JSON ───→ Node-RED
```

`dbus-serialbattery` should be the **only owner of the physical serial port**. Node-RED then consumes the already-decoded per-pack data over MQTT/D-Bus instead of opening the USB-RS485 device itself. This avoids serial-port contention and duplicates no Daly protocol work.

Useful sources:
- https://github.com/mr-manuel/venus-os_dbus-serialbattery/blob/master/dbus-serialbattery/config.default.ini
- https://github.com/mr-manuel/venus-os_dbus-mqtt-battery

## Battery aggregation in Venus OS

Venus OS can select only one battery as controlling BMS for CVL/CCL/DCL and only one battery for the main GUI/VRM representation. The `dbus-serialbattery` documentation therefore explicitly says a multi-battery installation needs an aggregator.

### Preferred first aggregator to evaluate: Dr-Gigavolt/dbus-aggregate-batteries

The dbus-serialbattery FAQ currently marks this as the **recommended** aggregator:
- https://github.com/Dr-Gigavolt/dbus-aggregate-batteries

It was created specifically to collect all `SerialBattery` D-Bus instances and publish a single combined battery back onto D-Bus.

Relevant behavior from its current README/source:

- all SerialBattery instances are discovered and combined;
- aggregated values are published once per second;
- if `OWN_SOC = False`, SOC is a capacity-weighted average of the individual BMS SOC values;
- with `OWN_CHARGE_PARAMETERS = False`, it combines the CVL/CCL/DCL information supplied by the individual serial-battery instances;
- if **any one BMS blocks charge**, aggregated allowed charge current becomes zero;
- if **any one BMS blocks discharge**, aggregated allowed discharge current becomes zero;
- it can calculate bank current from Victron sources or use a battery-mode SmartShunt as authoritative bank current.

The SmartShunt option is technically important in systems containing current sources the aggregator does not otherwise enumerate. Its README specifically mentions Orion DC-DC/external DC chargers as examples that can otherwise be missed. If a master SmartShunt exists and truly measures **all** bank current, it is the cleaner source; otherwise this setting must not be enabled.

### Alternative: Node-RED creates the virtual bank

`venus-os_dbus-mqtt-battery` can emulate a Venus battery from MQTT and explicitly supports the workflow:

```text
individual batteries → Node-RED aggregation → MQTT → virtual Venus battery
```

This gives maximum freedom but also makes **us responsible for every safety decision** around CVL, CCL, DCL, alarms, stale data and disconnect behavior. It is therefore a useful second experiment, not my first choice for production control.

The minimum control fields include:

```text
Dc.Power
Dc.Voltage
Soc
Info.MaxChargeVoltage
Info.MaxChargeCurrent
Info.MaxDischargeCurrent
```

Source:
- https://github.com/mr-manuel/venus-os_dbus-mqtt-battery

Another established alternative is:
- https://github.com/pulquero/BatteryAggregator

## Electrical isolation / interface safety

The current `dbus-serialbattery` connection guide strongly recommends **galvanic isolation** between GX and BMS. It warns that if the BMS switches the battery negative while the data interface shares ground, current can find a path through the communication cable and damage the GX/Pi/BMS.

For a non-isolated RS485 adapter the project's FAQ says to connect only **A and B**, not a shared ground. For a final installation an **isolated USB↔RS485 interface** is therefore strongly preferred.

Source:
- https://mr-manuel.github.io/venus-os_dbus-serialbattery_docs/general/connect/
- https://mr-manuel.github.io/venus-os_dbus-serialbattery_docs/faq/

## Disconnect/failsafe behavior to verify before control

Current `dbus-serialbattery` has configurable communication-loss behavior. Do not accept the defaults blindly before allowing the virtual battery to control DVCC.

Relevant settings include:

```ini
BLOCK_ON_DISCONNECT
BLOCK_ON_DISCONNECT_TIMEOUT_MINUTES
BLOCK_ON_DISCONNECT_VOLTAGE_MIN
BLOCK_ON_DISCONNECT_VOLTAGE_MAX
BMS_CABLE_ALARM
```

We must deliberately decide what Katharina should do if one of five BMS units disappears while the other four remain healthy.

## Proposed physical/software test sequence

Do not install all five at once.

### Stage 1 — one R24TH, monitoring only

1. Use an **isolated USB↔RS485 adapter**.
2. Connect one R24TH RS485 A/B.
3. Use Daly Windows BmsMonitor/BMS Tools.
4. Set `Sleep time(S) = 65535`.
5. Set a unique battery code.
6. Set board number `1`.
7. Configure `BMS_TYPE = Daly` and test address `0x40`.
8. Confirm voltage, current, SOC, all cell voltages, temperatures, FET states and alarms.
9. Do **not** make it controlling BMS yet.

### Stage 2 — prove multi-drop with two physical R24TH

1. Configure second R24TH with unique battery code and board number `2`.
2. Parallel only the RS485 A/B bus in proper line/daisy-chain topology.
3. Configure:

```ini
BATTERY_ADDRESSES = 0x40, 0x41
```

4. Verify two independent SerialBattery instances.
5. Let this run for hours and watch error/retry rate.
6. Deliberately disconnect/reconnect one BMS and document recovery behavior.

If this works, the major R24TH question is solved experimentally.

### Stage 3 — five R24TH

Scale to:

```ini
BATTERY_ADDRESSES = 0x40, 0x41, 0x42, 0x43, 0x44
```

Verify unique identity, no address collision and acceptable polling latency/error rate.

### Stage 4 — Node-RED visibility

Enable:

```ini
PUBLISH_BATTERY_DATA_AS_JSON = True
```

Build Node-RED monitoring for each pack independently:

- SOC
- pack voltage/current
- every cell voltage
- min/max cell and delta
- temperature
- charge/discharge FET state
- active balancing state where available
- BMS alarms
- communication age/heartbeat

### Stage 5 — aggregated battery, monitoring only

Install/test `dbus-aggregate-batteries` and select the aggregate as the **Battery Monitor only**, not immediately as controlling BMS.

Cross-check:

- aggregated SOC vs individual SOC/capacity;
- bank current vs trusted external measurement;
- cell extrema across the complete bank;
- aggregate CVL/CCL/DCL;
- one-pack-offline behavior.

### Stage 6 — fault injection before DVCC

Test at minimum:

- unplug one RS485 BMS;
- stop one BMS responding;
- one BMS blocks charge;
- one BMS blocks discharge;
- one pack has an abnormal high cell;
- one pack has an abnormal low cell;
- one temperature alarm;
- GX/driver restart while power system is operating.

Only when the aggregate reacts conservatively and predictably should it be considered for **Controlling BMS / DVCC**.

## Research questions for next passes

1. Find a **primary Daly R24TH-specific** manual/PC-software reference proving board-number/address configuration on this exact generation.
2. Identify exact R24TH RS485 connector/pinout and whether its RS485 port is already isolated internally.
3. Determine practical polling time for five Daly units at 9600 baud and whether Daly's known slow/occasionally missed replies are acceptable for control.
4. Study `dbus-aggregate-batteries` exact CVL/CCL/DCL merge formulas and stale/offline-pack handling.
5. Verify how the aggregator exposes per-pack cell extrema and whether Node-RED should add an independent heartbeat/fault watchdog.
6. Determine the cleanest isolated RS485 hardware for Cerbo GX and the correct RS485 bus termination for the physical cable length.
7. Verify whether the installed Cerbo/Venus OS version should use current stable `dbus-serialbattery` or a newer development version for the multi-Daly functions we need.
8. Keep checking Off-Grid Garage tutorials/videos for practical Daly-specific wiring or long-term reliability observations.

## Working hypothesis

The most promising route is now:

```text
Daly #1 (board 1 / 0x40) ─┐
Daly #2 (board 2 / 0x41) ─┤
Daly #3 (board 3 / 0x42) ─┼─ RS485 ─ isolated USB/RS485 ─ Cerbo GX / Venus OS
Daly #4 (board 4 / 0x43) ─┤                                │
Daly #5 (board 5 / 0x44) ─┘                                ├─ dbus-serialbattery → 5 D-Bus batteries
                                                           │           │
                                                           │           └─ MQTT JSON → Node-RED
                                                           │
                                                           └─ dbus-aggregate-batteries → 1 virtual bank
```

This preserves individual pack/cell visibility while allowing Victron to see one coherent battery bank rather than five unrelated BMS devices.

The key remaining hardware proof is simple and decisive: **can two of the actual R24TH units be given board numbers 1 and 2 and then be read simultaneously as `0x40` and `0x41` on one RS485 pair?**

## Caution

Do not yet change the production battery-control architecture based on these notes. The next practical step remains monitoring-only: prove reliable communication with one R24TH, then two on one RS485 bus, then five. Aggregation and DVCC/control come only after communication-loss and protection behavior have been deliberately tested.
