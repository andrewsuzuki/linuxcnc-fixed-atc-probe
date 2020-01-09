# `fixed_atc_probe` for LinuxCNC 

HAL component containing ATC (Automatic Tool Changer) and tool probing routines for LinuxCNC. Assumes a fixed tool rack and touchoff probe within the machine boundary.

Written in Python 2 (LinuxCNC does not yet support Python 3; see LinuxCNC/linuxcnc#403). Uses `transitions` for finite state machine and `PySimpleGUI` for the GUI.

Made for the Gerber CNC wood router at Makehaven (makerspace in New Haven, CT).

## Credits

- Andrew Suzuki ([andrewsuzuki.com](https://andrewsuzuki.com))

## Pins

- `fixed_atc_probe.number` IN FLOAT
- `fixed_atc_probe.tool_prepare` IN BIT (looped to `prepared`)
- `fixed_atc_probe.tool_change` IN BIT
- `fixed_atc_probe.probe` IN BIT
- `fixed_atc_probe.prepared` OUT BIT (looped to `tool_prepare`)
- `fixed_atc_probe.changed` OUT BIT
- `fixed_atc_probe.chuck` OUT BIT

## Notes

- All moves must avoid the tool rack. Strategy?
- Tool loading and return can be dangerous if there is already a tool in the
  pocket.
- Whenever the machine will be picking up a new tool (atc tool retrieval or
  operator tool unloading), the chuck should briefly open to drop any tool
  already in the chuck.

## TODO

- Finalize fsm2
- Configuration:
  - Pocket locations
  - Tool rack bounding box coordinates
  - ...more...

# States

TODO update to fsm2

- Waiting for Startup
- Idle
- Probing/Insert: moving to probe LoadingXY
- Probing/Insert: waiting at probe LoadingXY, Collet closed
- Probing/Insert: waiting at probe LoadingXY, Collet open (operator inserts tool)
- Probing/Insert: downwards
- Probing/Insert: touching
- Probing/Insert: retracting
- Probing/Insert: done
- Toolchange: Moving to safe (from work area)
- Toolchange: At safe
- Toolchange: Returning: Moving to pocket (fast, towards side)
- Toolchange: Returning: Inserting into pocket (from side)
- Toolchange: Returning: Collet open
- Toolchange: Returning: Retracting (from top) -- collet open
- Toolchange: Returning: Retracting (from top) -- collet closed
- Toolchange: Returning: Moving to safe (Z first, then LoadingXY)
- Toolchange: Retrieving: Moving to pocket (fast, towards top)
- Toolchange: Retrieving: Slow moving to pocket, Collet open (from top)
- Toolchange: Retrieving: At tool, Collet closed
- Toolchange: Retrieving: Retracting (from side)
- Toolchange: Retrieving: Moving to safe (LoadingXY first, then Z)
