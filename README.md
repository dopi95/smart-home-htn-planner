# Smart Home HTN Planner

A Python-based **Hierarchical Task Network (HTN)** planning engine applied to a Smart Home domain.  
The planner decomposes high-level goals into sequences of primitive actions, visualizes the full decomposition tree, and animates step-by-step execution — all inside a desktop GUI.

---

## How to Run

```bash
pip install matplotlib networkx
python main.py            # full desktop GUI
python main.py --no-gui   # terminal fallback (no display needed)
```

**Requirements:** Python 3.9+, `matplotlib`, `networkx` (both explicitly allowed by the assignment). `tkinter` is built into Python.

---

## Project Structure

```
smart-home-htn-planner/
├── main.py          # entry point — launches the UI
├── domain.py        # world state, primitive tasks, compound task methods
├── htn_engine.py    # recursive HTN planner + TreeNode
├── tree_viz.py      # decomposition tree → NetworkX graph → Matplotlib render
└── ui.py            # full desktop GUI (tkinter + matplotlib embedded)
```

---

## 1. Domain Overview

### Environment — Smart Home

The domain models an intelligent home automation system. The **world state** is a flat dictionary of boolean flags representing the current condition of every device and sensor in the house:

| State Key         | Meaning                                      | Initial Value |
|-------------------|----------------------------------------------|---------------|
| `lights_on`       | Whether the lights are on                    | `False`       |
| `door_locked`     | Whether the front door is locked             | `False`       |
| `thermostat_set`  | Whether the thermostat is configured         | `False`       |
| `coffee_ready`    | Whether the coffee maker has been started    | `False`       |
| `blinds_closed`   | Whether the window blinds are closed         | `False`       |
| `devices_off`     | Whether all smart devices are powered off    | `False`       |
| `alert_sent`      | Whether a security alert has been dispatched | `False`       |
| `power_available` | Whether mains power is available             | `True`        |
| `someone_home`    | Whether a resident is currently home         | `True`        |
| `coffee_maker_ok` | Whether the coffee maker is functional       | `True`        |
| `guest_mode`      | Whether guest mode is active                 | `False`       |

The last four keys (`power_available`, `someone_home`, `coffee_maker_ok`, `guest_mode`) are **condition flags** — they are never changed by actions, only read by method preconditions to decide which plan to execute.

---

### Primitive Tasks (7)

Primitive tasks are the atomic, directly executable actions. Each takes the current state and returns `(success, new_state)`.

| Task Name            | Effect                          |
|----------------------|---------------------------------|
| `turn_on_lights`     | Sets `lights_on = True`         |
| `lock_door`          | Sets `door_locked = True`       |
| `set_thermostat`     | Sets `thermostat_set = True`    |
| `start_coffee_maker` | Sets `coffee_ready = True`      |
| `close_blinds`       | Sets `blinds_closed = True`     |
| `turn_off_devices`   | Sets `devices_off = True`       |
| `send_alert`         | Sets `alert_sent = True`        |

---

### Compound Tasks (4)

Compound tasks are high-level goals that the planner decomposes into subtasks. Each has one or more **methods**, and the planner picks the first method whose precondition holds in the current state.

#### `MorningRoutine`
Prepares the house for the morning.

| Method        | Precondition               | Subtasks                                                    |
|---------------|----------------------------|-------------------------------------------------------------|
| `with_coffee` | `coffee_maker_ok == True`  | `turn_on_lights` → `start_coffee_maker` → `set_thermostat` |
| `no_coffee`   | `coffee_maker_ok == False` | `turn_on_lights` → `set_thermostat`                         |

#### `SecureHome`
Secures the house depending on occupancy and door state.

| Method               | Precondition                                      | Subtasks                                       |
|----------------------|---------------------------------------------------|------------------------------------------------|
| `full_security`      | `someone_home == False` and `door_locked == False` | `lock_door` → `close_blinds` → `turn_off_devices` |
| `door_already_locked`| `someone_home == False` and `door_locked == True`  | `close_blinds` → `turn_off_devices`            |
| `light_security`     | `someone_home == True`                            | `lock_door`                                    |

#### `ComfortSetup`
Sets up comfort systems, with a fallback for power failures.

| Method           | Precondition                | Subtasks                            |
|------------------|-----------------------------|-------------------------------------|
| `normal_comfort` | `power_available == True`   | `set_thermostat` → `turn_on_lights` |
| `power_outage`   | `power_available == False`  | `send_alert`                        |

#### `EveningRoutine`
Runs the evening sequence — branches based on guest mode.

| Method             | Precondition          | Subtasks                        |
|--------------------|-----------------------|----------------------------------|
| `guest_evening`    | `guest_mode == True`  | `SecureHome`                    |
| `standard_evening` | `guest_mode == False` | `SecureHome` → `ComfortSetup`   |

---

## 2. HTN Engine Design

The engine is implemented in `htn_engine.py` as a single recursive function `htn_plan(tasks, state, parent_node)`.

### Algorithm

```
htn_plan(tasks, state, parent):
    if tasks is empty → return ([], state)          # base case

    task = tasks[0]
    rest = tasks[1:]

    if task is PRIMITIVE:
        execute task → (success, new_state)
        if not success → return (None, None)
        attach primitive node to parent
        return [task] + htn_plan(rest, new_state, parent)

    if task is COMPOUND:
        for each method in METHODS[task]:
            if method.precondition(state):
                create compound node, attach to parent
                plan_sub = htn_plan(method.subtasks, state, compound_node)
                if plan_sub failed:
                    remove compound node from parent   ← backtracking
                    try next method
                plan_rest = htn_plan(rest, mid_state, parent)
                if plan_rest failed:
                    remove compound node from parent   ← backtracking
                    try next method
                return plan_sub + plan_rest
        return (None, None)   ← no method worked
```

### Key Design Decisions

- **Sibling vs. child attachment:** Primitive tasks and the `rest` of the task list are attached to `parent_node`, not to the compound node. Only the compound task's own subtasks become its children. This produces the correct tree structure.
- **State threading:** Each task receives the state produced by the previous task. The `mid_state` returned from subtask decomposition is passed forward to `rest`, so state changes propagate correctly across siblings.
- **Backtracking:** If a method's subtasks fail partway through, the partially-added node is removed from the tree (`parent_node.children.remove(node)`) and the next method is tried. This is correct depth-first backtracking.
- **`(success, new_state)` contract:** Every primitive returns this tuple. The engine propagates `(None, None)` upward on any failure, allowing future extension to tasks that can genuinely fail.

---

## 3. Planner Walkthrough — Evening Routine (Nobody Home)

This is the most complex scenario. The initial state has `someone_home = False`.

### Input

```python
goal  = ["EveningRoutine"]
state = { ..., "someone_home": False, "power_available": True, ... }
```

### Step-by-step Trace

```
htn_plan(["EveningRoutine"], state, GOAL)
│
│  "EveningRoutine" is compound → check methods
│  Method "standard_evening": precondition = True  ✓
│  Create node: EveningRoutine [standard_evening]
│  Attach to GOAL
│
├─ htn_plan(["SecureHome", "ComfortSetup"], state, EveningRoutine)
│  │
│  │  "SecureHome" is compound → check methods
│  │  Method "full_security": precondition = not someone_home = True  ✓
│  │  Create node: SecureHome [full_security]
│  │  Attach to EveningRoutine
│  │
│  ├─ htn_plan(["lock_door", "close_blinds", "turn_off_devices"], state, SecureHome)
│  │  │
│  │  ├─ "lock_door" is primitive → execute → door_locked = True
│  │  │   Attach to SecureHome
│  │  │
│  │  ├─ "close_blinds" is primitive → execute → blinds_closed = True
│  │  │   Attach to SecureHome
│  │  │
│  │  └─ "turn_off_devices" is primitive → execute → devices_off = True
│  │      Attach to SecureHome
│  │
│  │  plan_sub = ["lock_door", "close_blinds", "turn_off_devices"]  ✓
│  │
│  └─ htn_plan(["ComfortSetup"], mid_state, EveningRoutine)
│     │
│     │  "ComfortSetup" is compound → check methods
│     │  Method "normal_comfort": precondition = power_available = True  ✓
│     │  Create node: ComfortSetup [normal_comfort]
│     │  Attach to EveningRoutine  ← sibling of SecureHome, NOT its child
│     │
│     └─ htn_plan(["set_thermostat", "turn_on_lights"], mid_state, ComfortSetup)
│        │
│        ├─ "set_thermostat" is primitive → execute → thermostat_set = True
│        │   Attach to ComfortSetup
│        │
│        └─ "turn_on_lights" is primitive → execute → lights_on = True
│            Attach to ComfortSetup
│
│  plan_rest = ["set_thermostat", "turn_on_lights"]  ✓

Final plan: ["lock_door", "close_blinds", "turn_off_devices", "set_thermostat", "turn_on_lights"]
```

### Resulting Decomposition Tree

```
GOAL
└── EveningRoutine  [standard_evening]
    ├── SecureHome  [full_security]
    │   ├── lock_door          [primitive]
    │   ├── close_blinds       [primitive]
    │   └── turn_off_devices   [primitive]
    └── ComfortSetup  [normal_comfort]
        ├── set_thermostat     [primitive]
        └── turn_on_lights     [primitive]
```

This tree is exactly what the GUI renders in the **Decomposition Tree** panel. Each node type is color-coded: Goal (blue), Compound (orange), Primitive (green). During animation, the currently executing primitive node turns white with a purple ring.

### Final World State

| Key              | Before  | After   |
|------------------|---------|---------|
| `door_locked`    | `False` | `True`  |
| `blinds_closed`  | `False` | `True`  |
| `devices_off`    | `False` | `True`  |
| `thermostat_set` | `False` | `True`  |
| `lights_on`      | `False` | `True`  |

---

## 4. All Scenarios

The GUI provides six pre-built scenarios, each demonstrating a different branch of the domain:

| # | Scenario              | Key State Change                                  | Method(s) Chosen                          | Final Plan                                                                 |
|---|-----------------------|---------------------------------------------------|-------------------------------------------|----------------------------------------------------------------------------|
| 1 | Morning Routine       | `coffee_maker_ok = True`                          | `with_coffee`                             | `turn_on_lights` → `start_coffee_maker` → `set_thermostat`                |
| 2 | Evening – Nobody Home | `someone_home = False`                            | `standard_evening` + `full_security` + `normal_comfort` | `lock_door` → `close_blinds` → `turn_off_devices` → `set_thermostat` → `turn_on_lights` |
| 3 | Power Outage          | `power_available = False`                         | `power_outage`                            | `send_alert`                                                               |
| 4 | Broken Coffee Maker   | `coffee_maker_ok = False`                         | `no_coffee`                               | `turn_on_lights` → `set_thermostat`                                        |
| 5 | Guest Mode Evening    | `guest_mode = True`, `someone_home = False`       | `guest_evening` + `full_security`         | `lock_door` → `close_blinds` → `turn_off_devices`                         |
| 6 | Door Already Locked   | `door_locked = True`, `someone_home = False`      | `door_already_locked`                     | `close_blinds` → `turn_off_devices`                                        |

---

## 5. Visualization & Animation (Bonus)

### Decomposition Tree

Built in `tree_viz.py` using **NetworkX** (graph structure) and **Matplotlib** (rendering). The layout algorithm `hierarchy_pos` is implemented from scratch — no external layout library is used. It recursively divides horizontal space evenly among siblings to produce a clean top-down tree.

Node color coding:

| Color  | Node Type        |
|--------|------------------|
| Blue   | Goal (root)      |
| Orange | Compound Task    |
| Green  | Primitive Action |
| White  | Currently Executing (animation) |

### Step-by-step Animation

The GUI animates plan execution one primitive at a time:

1. Each primitive is highlighted in the decomposition tree (white node, purple ring).
2. The corresponding action card in the execution panel is highlighted.
3. The world state panel updates in real time to reflect the new state after each action.
4. A 1-second delay between steps makes the execution easy to follow.

Animation runs on a background thread (`threading.Thread`) to keep the GUI responsive. A `_run_id` counter ensures that switching scenarios mid-animation cancels the previous run cleanly.

---

## 6. Failure Cases and Limitations

### Handled Failure Cases

**No applicable method:** If no method's precondition holds for a compound task, `htn_plan` returns `(None, None)`. The UI displays "Planning failed – no applicable method." This cannot currently happen in the defined domain because every compound task has exhaustive preconditions (e.g., `coffee_maker_ok` and `not coffee_maker_ok` cover all cases), but the engine handles it correctly if the domain is extended.

**Primitive task failure:** Each primitive returns `(success, new_state)`. If `success` is `False`, the engine propagates `(None, None)` upward. Currently all primitives always succeed, but the mechanism is in place for tasks that could fail (e.g., a door that is already locked).

**Backtracking:** If a chosen method's subtasks fail partway through, the engine removes the partially-added node from the tree and tries the next method. This is correct depth-first backtracking.

---

### Known Limitations

**1. No task ordering constraints between siblings.**  
The planner executes subtasks strictly left-to-right in the order they appear in the method definition. There is no support for partial-order planning or expressing that two tasks can run in any order.

**2. Preconditions are evaluated once per compound task.**  
Method preconditions are evaluated against the state at the time the compound task is reached. If a subtask changes the state in a way that would affect a sibling compound task's method choice, that is handled correctly (because `mid_state` is passed forward). However, there is no re-planning if the world changes unexpectedly during execution.

**3. Limited real-world execution feedback.**  
Most primitive tasks always succeed. The `lock_door` primitive demonstrates failure handling (returns `False` if the door is already locked), and the engine correctly backtracks to try the next method. However, in a real smart home, many more tasks could fail unpredictably.

**4. State is fully observable and deterministic.**  
The planner has complete knowledge of the world state at all times. There is no support for uncertainty, partial observability, or probabilistic outcomes — all of which are common in real HTN applications.

**5. Fixed scenario set.**  
The six scenarios are hardcoded. There is no interface to define a custom initial state or goal at runtime without editing `domain.py` or `ui.py` directly.

**6. Single-goal planning only.**  
The engine plans for one top-level goal at a time. There is no support for goal prioritization, interleaved plans, or concurrent task execution.

**7. Cycle detection implemented.**  
The engine tracks the compound task call stack in `_visited` and fails planning if a cycle is detected. This prevents infinite recursion if a compound task's method decomposes into itself (directly or indirectly).

---

## Libraries Used

| Library      | Purpose                                      | Allowed by assignment |
|--------------|----------------------------------------------|-----------------------|
| `tkinter`    | Desktop GUI (built into Python)              | ✅ Built-in            |
| `matplotlib` | Rendering the decomposition tree             | ✅ Explicitly listed   |
| `networkx`   | Graph structure for the decomposition tree   | ✅ Explicitly listed   |
| `threading`  | Background animation thread (built-in)       | ✅ Built-in            |
| `time`       | Animation timing (built-in)                  | ✅ Built-in            |

The HTN engine, domain, layout algorithm (`hierarchy_pos`), and all UI logic are written entirely from scratch.
