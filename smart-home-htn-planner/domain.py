
#  Smart Home HTN Domain
#  State keys and what each primitive/compound task does
#  Allowed libraries: none (pure Python)
#  4 Compound Tasks: MorningRoutine, SecureHome, ComfortSetup, EveningRoutine
#  7 Primitive Tasks: turn_on_lights, lock_door, set_thermostat,
#                     start_coffee_maker, close_blinds, turn_off_devices, send_alert
# Initial world state

def initial_state():
    return {
        "lights_on":        False,
        "door_locked":      False,
        "thermostat_set":   False,
        "coffee_ready":     False,
        "blinds_closed":    False,
        "devices_off":      False,
        "alert_sent":       False,
        "power_available":  True,   # drives method choice in ComfortSetup
        "someone_home":     True,   # drives method choice in SecureHome
        "coffee_maker_ok":  True,   # drives method choice in MorningRoutine
        "guest_mode":       False,  # drives method choice in EveningRoutine
    }


# Primitive tasks 
# Each returns (success, new_state)

def turn_on_lights(state):
    s = dict(state); s["lights_on"] = True;       return True, s

def lock_door(state):
    # Fails if door is already locked — exercises the primitive failure path
    if state["door_locked"]:
        return False, state
    s = dict(state); s["door_locked"] = True;     return True, s

def set_thermostat(state):
    s = dict(state); s["thermostat_set"] = True;  return True, s

def start_coffee_maker(state):
    s = dict(state); s["coffee_ready"] = True;    return True, s

def close_blinds(state):
    s = dict(state); s["blinds_closed"] = True;   return True, s

def turn_off_devices(state):
    s = dict(state); s["devices_off"] = True;     return True, s

def send_alert(state):
    s = dict(state); s["alert_sent"] = True;      return True, s


# Primitive task registry
PRIMITIVES = {
    "turn_on_lights":   turn_on_lights,
    "lock_door":        lock_door,
    "set_thermostat":   set_thermostat,
    "start_coffee_maker": start_coffee_maker,
    "close_blinds":     close_blinds,
    "turn_off_devices": turn_off_devices,
    "send_alert":       send_alert,
}


# Compound task methods
# Format: { compound_name: [ (method_name, precondition_fn, subtask_list), ... ] }
#
# The planner tries methods in order and picks the FIRST whose precondition holds.

METHODS = {

    # MorningRoutine 
    # Method 1: coffee maker works  → lights + coffee + thermostat
    # Method 2: coffee maker broken → lights + thermostat only
    "MorningRoutine": [
        (
            "with_coffee",
            lambda s: s["coffee_maker_ok"],
            ["turn_on_lights", "start_coffee_maker", "set_thermostat"],
        ),
        (
            "no_coffee",
            lambda s: not s["coffee_maker_ok"],
            ["turn_on_lights", "set_thermostat"],
        ),
    ],

    # SecureHome
    # Method 1: nobody home, door not yet locked → full lock + blinds + devices
    # Method 2: nobody home, door already locked → blinds + devices only
    # Method 3: someone home → just lock the door
    "SecureHome": [
        (
            "full_security",
            lambda s: not s["someone_home"] and not s["door_locked"],
            ["lock_door", "close_blinds", "turn_off_devices"],
        ),
        (
            "door_already_locked",
            lambda s: not s["someone_home"] and s["door_locked"],
            ["close_blinds", "turn_off_devices"],
        ),
        (
            "light_security",
            lambda s: s["someone_home"],
            ["lock_door"],
        ),
    ],

    # ComfortSetup 
    # Method 1: power available → thermostat + lights
    # Method 2: power out       → send alert only
    "ComfortSetup": [
        (
            "normal_comfort",
            lambda s: s["power_available"],
            ["set_thermostat", "turn_on_lights"],
        ),
        (
            "power_outage",
            lambda s: not s["power_available"],
            ["send_alert"],
        ),
    ],

    # EveningRoutine
    # Method 1: guest mode active → only secure home (skip comfort setup)
    # Method 2: normal evening    → secure home then comfort setup
    "EveningRoutine": [
        (
            "guest_evening",
            lambda s: s["guest_mode"],
            ["SecureHome"],
        ),
        (
            "standard_evening",
            lambda s: not s["guest_mode"],
            ["SecureHome", "ComfortSetup"],
        ),
    ],
}
