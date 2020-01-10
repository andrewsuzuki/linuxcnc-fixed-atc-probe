# `fixed_atc_probe` for LinuxCNC 

HAL component containing ATC (Automatic Tool Changer) and tool probing routines for LinuxCNC. Assumes a fixed tool rack and touchoff probe within the machine boundary.

Written in Python 2 (LinuxCNC does not yet support Python 3; see LinuxCNC/linuxcnc#403). Uses `transitions` for finite state machine and `PySimpleGUI` for the GUI.

Made for the Gerber CNC wood router at Makehaven (makerspace in New Haven, CT).

## Credits

- Andrew Suzuki ([andrewsuzuki.com](https://andrewsuzuki.com))

## Pins

- `fixed_atc_probe.number` IN FLOAT
- `fixed_atc_probe.tool_prepare` IN BIT (internally looped to `prepared`)
- `fixed_atc_probe.tool_change` IN BIT
- `fixed_atc_probe.probe` IN BIT
- `fixed_atc_probe.prepared` OUT BIT (internally looped to `tool_prepare`)
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

- Put tool in pocket after probing
- save/restore modal state (M70 and M72)
- tool table updates (G43 or G20) after probing
- state.is_changed output
- More GUI
  - "Continue" functionality
- Tweak feeds

## Configuration

See `config.json` as an example.

- `probe_retract_offset_z`: Relative z offset after probe touchoff.
- `pocket_side_offset`: Relative x/y offset (map) for pocket sides (where it
  will slow down for insertion/removal), calculated from individual pockets.
- `pocket_above_collet_offset_z`: Relative z offset from individual pockets
  where the chuck will open/close (depending on if it's retrieving/returning).
- `pocket_above_clearance_offset_z`: Relative z offset from individual pockets
  where the chuck is free to move in the xy plane (towards/away from the tool
  rack). Must account for height of the tool holder and pull stud above the pocket.
- `collet_seconds`: Time in seconds where the collet will remain open after
  reaching the pocket.
- `loading`: absolute x/y/z coordinate (map) of the loading position. x/y SHOULD be equal to
  the x/y of `probe_limit` (below)
- `probe_limit`: absolute x/y/z coordinate (map) of the probe position (the
  farthest down it should go). x/y SHOULD be equal to the x/y of `loading` (above)
- `safe`: absolute x/y/z coordinate (map) of an arbitrary position near the tool
  rack (should be "in front" of it)
- `pocket_default`: absolute x/y/z coordinate (map) of the default pocket.
  This will be merged into the actual pocket coordinates (below), allowing, say
  a default Y/Z but variable X.
- `pockets`: map of tool/pocket number strings to absolute [x]/[y]/[z]
  coordinates (maps). Will use `pocket_default` as default x/y/z.
