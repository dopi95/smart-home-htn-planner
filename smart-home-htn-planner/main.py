#  Smart Home HTN Planner  –  Entry Point
#  Run:  python main.py            → full desktop GUI
#        python main.py --no-gui   → terminal fallback (no display needed)
import sys

if "--no-gui" in sys.argv:
    from domain     import initial_state
    from htn_engine import htn_plan, TreeNode
    from tree_viz   import print_tree

    SCENARIOS = [
        ("Morning Routine",        ["MorningRoutine"],  {}),
        ("Evening – Nobody Home",  ["EveningRoutine"],  {"someone_home": False}),
        ("Power Outage",           ["ComfortSetup"],    {"power_available": False}),
        ("Broken Coffee Maker",    ["MorningRoutine"],  {"coffee_maker_ok": False}),
        ("Guest Mode Evening",     ["EveningRoutine"],  {"guest_mode": True, "someone_home": False}),
        ("Door Already Locked",    ["SecureHome"],      {"door_locked": True, "someone_home": False}),
    ]

    for title, goal, patch in SCENARIOS:
        state = {**initial_state(), **patch}
        root  = TreeNode("GOAL", kind="compound", method="root")
        plan, _ = htn_plan(goal, state, root)
        print(f"\n{'='*50}")
        print(f"Scenario : {title}")
        print(f"Goal     : {goal}")
        print(f"Plan     : {plan if plan else 'FAILED'}")
        print("Tree:")
        print_tree(root)
else:
    from ui import HTNApp
    app = HTNApp()
    app.mainloop()
