#!/usr/bin/env python

import PySimpleGUI as sg
import json
import sys
import linuxcnc
import hal
from transitions import Machine, State

# Constants

StateStartup = "StateStartup"
StateIdle = "StateIdle"
StatePIMovingToLoadingXY = "StatePIMovingToLoadingXY"
StatePIAtLoadingXYClosed = "StatePIAtLoadingXYClosed"
StatePIAtLoadingXYOpen = "StatePIAtLoadingXYOpen"
StatePIMovingDownwards = "StatePIMovingDownwards"
StatePIRetracting = "StatePIRetracting"
StateUnloadMovingToLoadingXY = "StateUnloadMovingToLoadingXY"
StateUnloadAtLoadingXYClosed = "StateUnloadAtLoadingXYClosed"
StateUnloadAtLoadingXYOpen = "StateUnloadAtLoadingXYOpen"
StateUnloadAtLoadingXYClosed  = "StateUnloadAtLoadingXYClosed "
StateUnloadAtLoadingXYDropCheckOpen = "StateUnloadAtLoadingXYDropCheckOpen"
StateUnloadAtLoadingXYDropCheckClosed = "StateUnloadAtLoadingXYDropCheckClosed"
StateATCMovingToSafe = "StateATCMovingToSafe"
StateATCAtSafe = "StateATCAtSafe"
StateATCReturningMovingToPocketFast = "StateATCReturningMovingToPocketFast"
StateATCReturningInsertingIntoPocket = "StateATCReturningInsertingIntoPocket"
StateATCReturningAtToolOpen = "StateATCReturningAtToolOpen"
StateATCReturningRetractingOpen = "StateATCReturningRetractingOpen"
StateATCReturningRetractingClosed = "StateATCReturningRetractingClosed"
StateATCReturningMovingToSafe = "StateATCReturningMovingToSafe"
StateATCRetrievingDropCheckOpen = "StateATCRetrievingDropCheckOpen"
StateATCRetrievingMovingToPocketFast = "StateATCRetrievingMovingToPocketFast"
StateATCRetrievingApproachingPocketOpen = "StateATCRetrievingApproachingPocketOpen"
StateATCRetrievingAtToolClosed = "StateATCRetrievingAtToolClosed"
StateATCRetrievingRetracting = "StateATCRetrievingRetracting"
StateATCRetrievingMovingToSafe = "StateATCRetrievingMovingToSafe"

EventMdiNotReady = "EventMdiNotReady"
EventMdiReady = "EventMdiReady"
EventInPosition = "EventInPosition"
EventRequestLoadTool = "EventRequestLoadTool"
EventRequestUnloadTool = "EventRequestUnloadTool"
EventRequestOpenCollet = "EventRequestOpenCollet"
EventRequestCloseCollet = "EventRequestCloseCollet"
EventRequestContinue = "EventRequestContinue"
EventTouchoffTouching = "EventTouchoffTouching"
EventDropCheckComplete = "EventDropCheckComplete"
EventUnloadCompleted = "EventUnloadCompleted"
EventRequestToolChange = "EventRequestToolChange"
EventPocketTimerComplete = "EventEventRetrievingPocketTimerComplete"
EventChangeCompleted = "EventChangeCompleted"
EventIsReturning = "EventIsReturning"
EventIsRetrieving = "EventIsRetrieving"

def panic():
    """Panic by logging fatal error and exiting"""
    print "fixed_atc_probe encountered a fatal error. Stopping."
    sys.exit(1)

# Config
config = None
with open('config.json') as config_file:
    config = json.load(config_file)

def merge_coords(coords):
    """Merge and validate coordinate dicts from config"""
    base = {}
    for coord in coords:
        base.update(coord)
    # Validate
    if not (getattr(base, 'x', None) and getattr(base, 'y', None) and getattr(base, 'z', None)):
        raise AttributeError
    return base

def add_coords(a_coord, b_coord):
    """Perform a + b on coordinates, where a is fully-formed"""
    return {
        "x": a_coord.x + getattr(b_coord, 'x', 0),
        "y": a_coord.y + getattr(b_coord, 'y', 0),
        "z": a_coord.z + getattr(b_coord, 'z', 0)
    }

def get_pocket_coord(number, coord_type):
    """Get {x,y,z} coordinate tuple for a given pocket and coordinate type"""
    pocket = config.pockets[str(number)]
    if not pocket:
        raise ValueError

    base = merge_coords([config.pocket_default, pocket])

    if coord_type == 'pocket':
        return base
    if coord_type == 'side':
        return add_coords(base, config.pocket_side_offset)
    if coord_type == 'above-collet':
        return add_coords(base, {'z': config.pocket_above_collet_offset_z})
    if coord_type == 'above-clearance':
        return add_coords(base, {'z': config.pocket_above_clearance_offset_z})
    raise ValueError

class StateMachine(object):
    """Finite state machine for ATC and probe"""

    states = [
        State(name=StateStartup, on_enter=None, on_exit=None),
        State(name=StateIdle, on_enter=None, on_exit=None),

        State(name=StatePIMovingToLoadingXY, on_enter=['move_pi_loading'], on_exit=None),
        State(name=StatePIAtLoadingXYClosed, on_enter=None, on_exit=None),
        State(name=StatePIAtLoadingXYOpen, on_enter=['open_collet'], on_exit=['close_collet']),
        State(name=StatePIMovingDownwards, on_enter=['move_pi_touchoff'], on_exit=None),
        State(name=StatePIRetracting, on_enter=['move_pi_retract'], on_exit=None),

        State(name=StateUnloadMovingToLoadingXY, on_enter=['move_pi_loading'], on_exit=None),
        State(name=StateUnloadAtLoadingXYClosed, on_enter=None, on_exit=None),
        State(name=StateUnloadAtLoadingXYOpen, on_enter=['open_collet'], on_exit=['close_collet']),
        State(name=StateUnloadAtLoadingXYDropCheckOpen, on_enter=['open_collet'], on_exit=['close_collet']),
        # TODO on enter: dispatch EventDropCheckComplete
        State(name=StateUnloadAtLoadingXYDropCheckClosed, on_enter=None, on_exit=None),

        State(name=StateATCMovingToSafe, on_enter=['move_atc_safe'], on_exit=None),
        # TODO on enter: dispatch one of three events (EventIsReturning, EventIsReceiving, EventChangeCompleted) depending on state
        State(name=StateATCAtSafe, on_enter=None, on_exit=None),

        # TODO on enter: move to pocket side
        State(name=StateATCReturningMovingToPocketFast, on_enter=None, on_exit=None),
        # TODO on enter: move to pocket
        State(name=StateATCReturningInsertingIntoPocket, on_enter=None, on_exit=None),
        # TODO on enter: start ~0.5s timer that will dispatch EventPocketTimerComplete (though it will continue to be open)
        State(name=StateATCReturningAtToolOpen, on_enter=['open_collet'], on_exit=None),
        # TODO on enter: move to pocket collet location
        State(name=StateATCReturningRetractingOpen, on_enter=None, on_exit=['close_collet']),
        # TODO on enter: move to pocket clearance location
        State(name=StateATCReturningRetractingClosed, on_enter=None, on_exit=None),
        # TODO on enter: move to safe
        State(name=StateATCReturningMovingToSafe, on_enter=None, on_exit=None),

        # TODO on enter: start timer that will dispatch EventDropCheckComplete
        State(name=StateATCRetrievingDropCheckOpen, on_enter=['open_collet'], on_exit=['close_collet']),
        # TODO on enter: move to pocket clearance location
        State(name=StateATCRetrievingMovingToPocketFast, on_enter=None, on_exit=None),
        # TODO on enter: move to pocket collet location
        State(name=StateATCRetrievingApproachingPocketOpen, on_enter=['open_collet'], on_exit=['close_collet']),
        # TODO on enter: start ~0.5s timer that will dispatch EventPocketTimerComplete
        State(name=StateATCRetrievingAtToolClosed, on_enter=None, on_exit=None),
        # TODO on enter: move to pocket side
        State(name=StateATCRetrievingRetracting, on_enter=None, on_exit=None),
        # TODO on enter: move to safe
        State(name=StateATCRetrievingMovingToSafe, on_enter=None, on_exit=None),
    ]

    current_tool_number = -1 # Derived from linuxcnc status TODO what is "no tool"?
    is_changing_tool = None # None (not currently executing tool change) or integer (tool number)
    tool_table = () # Derived from linuxcnc status
    is_ok_for_mdi = False # Derived from linuxcnc status
    is_touching = False # Pin input
    is_chuck_open = False # Pin output
    is_changed = False # Pin output

    transitions = [
        # The state machine should "restart" to StateStartup if Mdi becomes unavailable.
        {'trigger': EventMdiNotReady, 'source': '*', 'dest': StateStartup},
        # When Mdi is ready, go to StateIdle.
        {'trigger': EventMdiReady, 'source': StateStartup, 'dest': StateIdle},

        # PI
        # The operator requests loading a tool (from an empty pocket...)
        {'trigger': EventRequestLoadTool, 'source': StateIdle, 'dest': StatePIMovingToLoadingXY},
        # The machine reaches LoadingXY. Wait.
        {'trigger': EventInPosition, 'source': StatePIMovingToLoadingXY, 'dest': StatePIAtLoadingXYClosed},
        # The operator requests opening the collet.
        {'trigger': EventRequestOpenCollet, 'source': StatePIAtLoadingXYClosed, 'dest': StatePIAtLoadingXYOpen},
        # The operator requests closing the collet.
        {'trigger': EventRequestCloseCollet, 'source': StatePIAtLoadingXYOpen, 'dest': StatePIAtLoadingXYClosed},
        # The operator, having loaded the tool, requests continuing the procedure.
        {'trigger': EventRequestContinue, 'source': StatePIAtLoadingXYClosed, 'dest': StatePIMovingDownwards},
        # The tool begins moving downwards until it touches off
        {'trigger': EventTouchoffTouching, 'source': StatePIMovingDownwards, 'dest': StatePIRetracting},
        # The tool retracts until it is in position
        {'trigger': EventInPosition, 'source': StatePIRetracting, 'dest': StateATCMovingToSafe},

        # Unload
        {'trigger': EventRequestUnloadTool, 'source': StateIdle, 'dest': StateUnloadMovingToLoadingXY},
        {'trigger': EventInPosition, 'source': StateUnloadMovingToLoadingXY, 'dest': StateUnloadAtLoadingXYClosed},
        {'trigger': EventRequestOpenCollet, 'source': StateUnloadAtLoadingXYClosed, 'dest': StateUnloadAtLoadingXYOpen},
        {'trigger': EventRequestCloseCollet, 'source': StateUnloadAtLoadingXYOpen, 'dest': StateUnloadAtLoadingXYClosed},
        {'trigger': EventRequestContinue, 'source': StateUnloadAtLoadingXYClosed , 'dest': StateUnloadAtLoadingXYDropCheckOpen},
        {'trigger': EventDropCheckComplete, 'source': StateUnloadAtLoadingXYDropCheckOpen, 'dest': StateUnloadAtLoadingXYDropCheckClosed},
        {'trigger': EventUnloadCompleted, 'source': StateUnloadAtLoadingXYDropCheckClosed, 'dest': StateIdle}, # internal

        # General ATC
        {'trigger': EventRequestToolChange, 'source': StateIdle, 'dest': StateATCMovingToSafe},
        {'trigger': EventInPosition, 'source': StateATCMovingToSafe, 'dest': StateATCAtSafe},
        {'trigger': EventChangeCompleted, 'source': StateATCAtSafe, 'dest': StateIdle}, # internal

        # ATC Returning
        {'trigger': EventIsReturning, 'source': StateATCAtSafe, 'dest': StateATCReturningMovingToPocketFast},
        {'trigger': EventInPosition, 'source': StateATCReturningMovingToPocketFast, 'dest': StateATCReturningInsertingIntoPocket},
        {'trigger': EventInPosition, 'source': StateATCReturningInsertingIntoPocket, 'dest': StateATCReturningAtToolOpen},
        {'trigger': EventInPosition, 'source': StateATCReturningAtToolOpen, 'dest': StateATCReturningRetractingOpen},
        {'trigger': EventInPosition, 'source': StateATCReturningRetractingOpen, 'dest': StateATCReturningRetractingClosed},
        {'trigger': EventInPosition, 'source': StateATCReturningRetractingClosed, 'dest': StateATCReturningMovingToSafe},
        {'trigger': EventInPosition, 'source': StateATCReturningMovingToSafe, 'dest': StateATCAtSafe},

        # ATC Retrieving
        {'trigger': EventIsRetrieving, 'source': StateATCAtSafe, 'dest': StateATCRetrievingDropCheckOpen}, # internal
        {'trigger': EventDropCheckComplete, 'source': StateATCRetrievingDropCheckOpen, 'dest': StateATCRetrievingMovingToPocketFast},
        {'trigger': EventInPosition, 'source': StateATCRetrievingMovingToPocketFast, 'dest': StateATCRetrievingApproachingPocketOpen},
        {'trigger': EventInPosition, 'source': StateATCRetrievingApproachingPocketOpen, 'dest': StateATCRetrievingAtToolClosed},
        {'trigger': EventPocketTimerComplete, 'source': StateATCRetrievingAtToolClosed, 'dest': StateATCRetrievingRetracting},
        {'trigger': EventInPosition, 'source': StateATCRetrievingRetracting, 'dest': StateATCRetrievingMovingToSafe},
        {'trigger': EventInPosition, 'source': StateATCRetrievingMovingToSafe, 'dest': StateATCAtSafe},
    ]

    def __init__(self):
        """
        Initialize the state machine
        """
        self.machine = Machine(
            model=self,
            queued=True,
            states=StateMachine.states,
            transitions=StateMachine.transitions,
            initial=StateStartup
        )

    def request_load_tool(self, tool):
        pass  # TODO

    def request_unload_tool(self, tool):
        pass  # TODO

    def set_tool_change(self, is_tool_change, number, changed):
        # Derive
        is_changing_tool = None
        if is_tool_change and number and not changed:
            is_changing_tool = number

        # If changed...
        if is_changing_tool != self.is_changing_tool:
            self.is_changing_tool = is_changing_tool
            if self.is_changing_tool:
                self.machine.dispatch(EventRequestToolChange)
            else:
                # TODO ? Could possibly dispatch a end-of-atc type of event

    def set_is_touching(self, is_touching):
        if is_touching != self.is_touching:
            self.is_touching = is_touching
            self.machine.dispatch(EventTouchoffTouching)

    def set_current_tool_number(self, tool):
        self.current_tool_number = tool

    def set_tool_table(self, tool_table):
        self.tool_table = tool_table

    def set_is_ok_for_mdi(self, is_ok_for_mdi):
        # If changed...
        if is_ok_for_mdi != self.is_ok_for_mdi:
            self.is_ok_for_mdi = is_ok_for_mdi
            # Dispatch appropriate event
            if self.is_ok_for_mdi:
                self.machine.dispatch(EventMdiReady)
            else:
                self.machine.dispatch(EventMdiNotReady)
                panic()

    def open_collet(self):
        self.is_chuck_open = True

    def close_collet(self):
        self.is_chuck_open = False

    def move_coord_absolute(self, coord, feed=3600, dispatch_in_position=True):
        send_gcode("G21 G53 G0 F{} X{} Y{} Z{}".format(feed, coord.x, coord.y, coord.z))
        if dispatch_in_position:
            self.machine.dispatch(EventInPosition)

    def move_coord_relative(self, coord, feed=3600, dispatch_in_position=True):
        send_gcode("G21 G91 G0 F{} X{} Y{} Z{}".format(feed, coord.x, coord.y, coord.z))
        if dispatch_in_position:
            self.machine.dispatch(EventInPosition)

    def move_pi_loading(self):
        # TODO avoid tool rack boundary
        self.move_coord_absolute(config.loading)

    def move_pi_touchoff(self):
        # TODO tweak feedrate
        self.move_coord_absolute(config.probe_limit, feed=10)

    def move_pi_retract(self):
        coord = {"x": 0, "y": 0, "z": config.probe_retract_offset_z}
        self.move_coord_relative(coord)

    def move_atc_safe(self):
        # TODO avoid tool rack boundary
        self.move_coord_absolute(config.safe)

    def move_atc_pocket_side(self):
        coord = get_pocket_coord(self.is_changing_tool, 'side')
        self.move_coord_absolute(coord)

    def move_atc_pocket(self):
        coord = get_pocket_coord(self.is_changing_tool, 'pocket')
        self.move_coord_absolute(coord)

    def move_atc_collet(self):
        coord = get_pocket_coord(self.is_changing_tool, 'collet')
        self.move_coord_absolute(coord)

    def move_atc_clearance(self):
        # TODO avoid tool rack boundary (when returning)
        coord = get_pocket_coord(self.is_changing_tool, 'clearance')
        self.move_coord_absolute(coord)

# Configure HAL Component
h = hal.component("fixed_atc_probe")
# IN:
h.newpin("number", hal.HAL_FLOAT, hal.HAL_IN)
h.newpin("tool_prepare", hal.HAL_BIT, hal.HAL_IN)  # looped to `prepared`
h.newpin("tool_change", hal.HAL_BIT, hal.HAL_IN)
h.newpin("probe", hal.HAL_BIT, hal.HAL_IN)
# OUT:
h.newpin("prepared", hal.HAL_BIT, hal.HAL_OUT)  # looped to `tool_prepare`
h.newpin("changed", hal.HAL_BIT, hal.HAL_OUT)
h.newpin("chuck", hal.HAL_BIT, hal.HAL_OUT)
h.ready()

# Configure GUI window
sg.theme('SystemDefaultForReal')
layout = [[sg.Text('Tool # = Pocket #')],
          [sg.Text('Load/Probe Tool #'), sg.InputText(key='InputLoad',
                                                      size=(3, 1), do_not_clear=False), sg.Button('Load')],
          [sg.Text('Unload Tool #'), sg.InputText(key='InputUnload',
                                                  size=(3, 1), do_not_clear=False), sg.Button('Unload')],
          # output for stdout/stderr
          [sg.Output(size=(50, 10))]]
window = sg.Window('Tool Changer and Probe', layout)

def send_gcode(gcode):
    """G-code sender"""
    c = linuxcnc.command()
    c.mode(linuxcnc.MODE_MDI)
    c.wait_complete()
    # TODO does this block? if yes, remove wait_complete below. if no, increase wait time
    c.mdi(gcode)
    c.wait_complete()

def status_routine(state, status):
    """Status routine (for main loop)"""

    # Poll status channel
    try:
        status.poll()
    except linuxcnc.error as ex:
        print ex
        panic()

    # Read status into state
    state.set_current_tool_number(status.tool_in_spindle)  # integer
    state.set_tool_table(status.tool_table)  # array
    state.set_is_ok_for_mdi(not status.estop and status.enabled and status.homed and (
        status.interp_state == linuxcnc.INTERP_IDLE))
    # state.set_task_mode(status.task_mode) # mdi, auto, manual
    # state.set_is_in_position(status.inpos != 0)
    # state.set_spindle_enabled(status.spindle_enabled)
    # state.set_spindle_speed(status.spindle_speed)
    # state.set_file(status.file)

def hal_routine(state):
    """HAL Routine (for main loop)"""

    # input pins
    state.set_tool_change(h.tool_change == 1, h.number, h.changed == 1)
    state.set_is_touching(h.probe == 1)
    # ouput pins
    h.chuck = 1 if state.is_chuck_open else 0
    h.changed = 1 if state.is_changed else 0
    # loop `prepared` to `tool_prepare`
    h.prepared = h.tool_prepare

def gui_routine(state):
    """GUI routing (for main loop)"""

    event, values = window.read()
    i = None
    if event == 'Load':
        try:
            i = int(values['InputLoad'])
        except ValueError:
            print 'Bad input'

        if i is not None and i >= 0:
            state.request_load_tool(i)
    elif event == 'Unload':
        try:
            i = int(values['InputUnload'])
        except ValueError:
            print 'Bad input'

        if i is not None and i >= 0:
            state.request_unload_tool(i)


# Initialize state machine
state = StateMachine()

# Create connection to LinuxCNC status channel
status = linuxcnc.stat()

# Main loop
while True:
    status_routine(state, status)
    hal_routine(state)
    gui_routine(state)
