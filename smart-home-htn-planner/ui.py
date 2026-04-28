#  Smart Home HTN Planner  –  Desktop UI
#  Run:  python main.py   OR   python ui.py
#  Requires: tkinter (built-in), matplotlib, networkx
import tkinter as tk
from tkinter import ttk
import threading
import time

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from domain     import initial_state
from htn_engine import htn_plan, TreeNode
from tree_viz   import build_graph, hierarchy_pos, draw_tree_on_ax

# ── palette ───────────────────────────────────
BG         = "#1E1E2E"
PANEL_BG   = "#2A2A3E"
ACCENT     = "#7C3AED"
BTN_BG     = "#3B3B5C"
BTN_HOVER  = "#4C4C7A"
BTN_ACTIVE = "#7C3AED"
TEXT       = "#E2E8F0"
MUTED      = "#94A3B8"
GREEN      = "#22C55E"
ORANGE     = "#F59E0B"
BLUE       = "#3B82F6"
RED        = "#EF4444"
BORDER     = "#3F3F6E"
CARD_BG    = "#1A1A2E"
CARD_ACT   = "#2D1B69"
CARD_DONE  = "#14532D"

STATE_META = {
    "lights_on":       ("💡", "Lights"),
    "door_locked":     ("🔒", "Door"),
    "thermostat_set":  ("🌡️",  "Thermostat"),
    "coffee_ready":    ("☕", "Coffee"),
    "blinds_closed":   ("🪟", "Blinds"),
    "devices_off":     ("📴", "Devices"),
    "alert_sent":      ("🚨", "Alert"),
    "power_available": ("⚡", "Power"),
    "someone_home":    ("🏠", "Home"),
    "coffee_maker_ok": ("🔧", "Maker"),
    "guest_mode":      ("👤", "Guest"),
}

SCENARIOS = [
    {
        "title":       "Morning Routine",
        "subtitle":    "Coffee maker is working",
        "goal":        ["MorningRoutine"],
        "state_patch": {},
        "icon":        "🌅",
    },
    {
        "title":       "Evening – Nobody Home",
        "subtitle":    "Full security mode",
        "goal":        ["EveningRoutine"],
        "state_patch": {"someone_home": False},
        "icon":        "🌙",
    },
    {
        "title":       "Power Outage",
        "subtitle":    "No power – send alert",
        "goal":        ["ComfortSetup"],
        "state_patch": {"power_available": False},
        "icon":        "⚡",
    },
    {
        "title":       "Broken Coffee Maker",
        "subtitle":    "Skip coffee step",
        "goal":        ["MorningRoutine"],
        "state_patch": {"coffee_maker_ok": False},
        "icon":        "🔧",
    },
    {
        "title":       "Guest Mode Evening",
        "subtitle":    "Security only, skip comfort",
        "goal":        ["EveningRoutine"],
        "state_patch": {"guest_mode": True, "someone_home": False},
        "icon":        "👤",
    },
    {
        "title":       "Door Already Locked",
        "subtitle":    "lock_door fails → backtrack",
        "goal":        ["SecureHome"],
        "state_patch": {"door_locked": True, "someone_home": False},
        "icon":        "🚫",
    },
]

ACTION_META = {
    "turn_on_lights":     ("💡", "Turn On Lights",     "Turning on all lights",         ORANGE),
    "lock_door":          ("🔒", "Lock Door",          "Locking the front door",         BLUE),
    "set_thermostat":     ("🌡️",  "Set Thermostat",    "Setting thermostat to 22°C",     BLUE),
    "start_coffee_maker": ("☕", "Start Coffee Maker", "Starting the coffee maker",      ORANGE),
    "close_blinds":       ("🪟", "Close Blinds",       "Closing all window blinds",      BLUE),
    "turn_off_devices":   ("📴", "Turn Off Devices",   "Turning off all smart devices",  RED),
    "send_alert":         ("🚨", "Send Alert",         "Sending security alert to owner",RED),
}

TASK_TO_STATE = {
    "turn_on_lights":     "lights_on",
    "lock_door":          "door_locked",
    "set_thermostat":     "thermostat_set",
    "start_coffee_maker": "coffee_ready",
    "close_blinds":       "blinds_closed",
    "turn_off_devices":   "devices_off",
    "send_alert":         "alert_sent",
}


class HTNApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Smart Home HTN Planner")
        self.configure(bg=BG)
        self.geometry("1500x880")
        self.minsize(1200, 720)
        self.resizable(True, True)

        self._active_btn   = None
        self._anim_running = False
        self._step_cards   = []
        self._G            = None
        self._pos          = None
        self._sc_title     = ""
        self._run_id       = 0   # incremented each scenario; callbacks check this
        self._destroyed    = False

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_header()
        self._build_body()
        self._build_footer()

    # ── header ────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=ACCENT, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🏠  Smart Home HTN Planner",
                 bg=ACCENT, fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=20)
        tk.Label(hdr, text="Hierarchical Task Network · AI Planning Demo",
                 bg=ACCENT, fg="#DDD6FE",
                 font=("Segoe UI", 10)).pack(side="left", padx=6)

    # ── body: three columns ───────────────────
    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        self._build_left(body)
        self._build_center(body)
        self._build_right(body)

    # ── LEFT: scenarios + world state ─────────
    def _build_left(self, parent):
        left = tk.Frame(parent, bg=PANEL_BG, width=224,
                        highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        tk.Label(left, text="SCENARIOS", bg=PANEL_BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(pady=(12, 4), padx=12, anchor="w")

        self._scenario_btns = []
        for i, sc in enumerate(SCENARIOS):
            btn = self._make_scenario_btn(left, sc, i)
            btn.pack(fill="x", padx=8, pady=3)
            self._scenario_btns.append(btn)

        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", padx=10, pady=10)

        tk.Label(left, text="WORLD STATE", bg=PANEL_BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(pady=(0, 4), padx=12, anchor="w")

        self._badge_vars   = {}
        self._badge_labels = {}
        for key, (icon, name) in STATE_META.items():
            val0 = initial_state()[key]
            row  = tk.Frame(left, bg=PANEL_BG)
            row.pack(fill="x", padx=10, pady=1)
            tk.Label(row, text=icon, bg=PANEL_BG, fg=TEXT,
                     font=("Segoe UI", 10)).pack(side="left")
            tk.Label(row, text=f" {name}", bg=PANEL_BG, fg=TEXT,
                     font=("Segoe UI", 8), width=10, anchor="w").pack(side="left")
            var = tk.StringVar(value="ON" if val0 else "OFF")
            lbl = tk.Label(row, textvariable=var,
                           bg=GREEN if val0 else BTN_BG, fg="white",
                           font=("Segoe UI", 7, "bold"), width=4, padx=3)
            lbl.pack(side="right")
            self._badge_vars[key]   = var
            self._badge_labels[key] = lbl

    def _make_scenario_btn(self, parent, sc, idx):
        frame = tk.Frame(parent, bg=BTN_BG, cursor="hand2",
                         highlightbackground=BORDER, highlightthickness=1)
        tk.Label(frame, text=sc["icon"], bg=BTN_BG, fg=TEXT,
                 font=("Segoe UI", 16)).pack(side="left", padx=(8, 4), pady=6)
        info = tk.Frame(frame, bg=BTN_BG)
        info.pack(side="left", pady=4)
        tk.Label(info, text=sc["title"], bg=BTN_BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(anchor="w")
        tk.Label(info, text=sc["subtitle"], bg=BTN_BG, fg=MUTED,
                 font=("Segoe UI", 7), anchor="w").pack(anchor="w")
        for w in (frame, *frame.winfo_children(), *info.winfo_children()):
            w.bind("<Button-1>", lambda e, i=idx: self._run_scenario(i))
            w.bind("<Enter>",    lambda e, f=frame: self._hover(f, True))
            w.bind("<Leave>",    lambda e, f=frame: self._hover(f, False))
        return frame

    def _hover(self, frame, on):
        if frame is self._active_btn:
            return
        c = BTN_HOVER if on else BTN_BG
        frame.configure(bg=c)
        for w in frame.winfo_children():
            try:
                w.configure(bg=c)
                for ww in w.winfo_children():
                    ww.configure(bg=c)
            except tk.TclError:
                pass

    def _set_active_btn(self, idx):
        if self._active_btn:
            self._hover(self._active_btn, False)
            self._active_btn.configure(highlightbackground=BORDER)
        self._active_btn = self._scenario_btns[idx]
        self._active_btn.configure(bg=BTN_ACTIVE, highlightbackground=ACCENT)
        for w in self._active_btn.winfo_children():
            try:
                w.configure(bg=BTN_ACTIVE)
                for ww in w.winfo_children():
                    ww.configure(bg=BTN_ACTIVE)
            except tk.TclError:
                pass

    # ── CENTER: decomposition tree (zoomable + pannable) ─
    def _build_center(self, parent):
        """Build the center panel with the interactive decomposition tree.
        NavigationToolbar2Tk provides zoom, pan, and home-reset buttons.
        The tree is redrawn on every scenario run and on every animation step.
        """
        center = tk.Frame(parent, bg=PANEL_BG,
                          highlightbackground=BORDER, highlightthickness=1)
        center.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # panel header
        hdr = tk.Frame(center, bg=PANEL_BG)
        hdr.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(hdr, text="DECOMPOSITION TREE", bg=PANEL_BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._tree_sub = tk.Label(hdr, text="", bg=PANEL_BG, fg=ACCENT,
                                  font=("Segoe UI", 8, "bold"))
        self._tree_sub.pack(side="left", padx=6)

        # legend chips
        legend_row = tk.Frame(center, bg=PANEL_BG)
        legend_row.pack(fill="x", padx=14, pady=(0, 4))
        for color, label in (("#3B82F6","Goal"), ("#F59E0B","Compound"),
                              ("#22C55E","Primitive"), ("#FFFFFF","Executing")):
            chip = tk.Frame(legend_row, bg=color, width=10, height=10)
            chip.pack(side="left", padx=(0, 3))
            tk.Label(legend_row, text=label, bg=PANEL_BG, fg=MUTED,
                     font=("Segoe UI", 7)).pack(side="left", padx=(0, 10))

        # matplotlib figure – interactive (zoom + pan via toolbar)
        self._fig, self._ax = plt.subplots(figsize=(8, 5.5))
        self._fig.patch.set_facecolor(PANEL_BG)
        self._ax.set_facecolor(PANEL_BG)
        self._ax.axis("off")
        self._ax.text(0.5, 0.5, "← Select a scenario to generate the decomposition tree",
                      ha="center", va="center", color=MUTED,
                      fontsize=11, transform=self._ax.transAxes)

        self._canvas = FigureCanvasTkAgg(self._fig, master=center)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=6)

        # navigation toolbar (zoom / pan / reset)
        toolbar_frame = tk.Frame(center, bg="#13131F")
        toolbar_frame.pack(fill="x", padx=6, pady=(0, 6))
        toolbar = NavigationToolbar2Tk(self._canvas, toolbar_frame)
        toolbar.config(bg="#13131F")
        for child in toolbar.winfo_children():
            try:
                child.config(bg="#13131F", fg=TEXT,
                             activebackground=BTN_HOVER, relief="flat")
            except tk.TclError:
                pass
        toolbar.update()

    # ── RIGHT: step-by-step execution cards ───
    def _build_right(self, parent):
        right = tk.Frame(parent, bg=PANEL_BG, width=310,
                         highlightbackground=BORDER, highlightthickness=1)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)

        hdr = tk.Frame(right, bg=PANEL_BG)
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(hdr, text="EXECUTION STEPS", bg=PANEL_BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._step_lbl = tk.Label(hdr, text="", bg=PANEL_BG, fg=ACCENT,
                                  font=("Segoe UI", 8, "bold"))
        self._step_lbl.pack(side="right")

        # scrollable card area
        wrap = tk.Frame(right, bg=PANEL_BG)
        wrap.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self._ccanvas = tk.Canvas(wrap, bg=PANEL_BG, highlightthickness=0)
        vsb = tk.Scrollbar(wrap, orient="vertical", command=self._ccanvas.yview,
                           bg=PANEL_BG, troughcolor=PANEL_BG, activebackground=ACCENT)
        self._ccanvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._ccanvas.pack(side="left", fill="both", expand=True)

        self._cframe = tk.Frame(self._ccanvas, bg=PANEL_BG)
        self._cwin   = self._ccanvas.create_window((0, 0), window=self._cframe, anchor="nw")
        self._cframe.bind("<Configure>",
                          lambda e: self._ccanvas.configure(
                              scrollregion=self._ccanvas.bbox("all")))
        self._ccanvas.bind("<Configure>",
                           lambda e: self._ccanvas.itemconfig(self._cwin, width=e.width))

        # plan summary strip
        strip = tk.Frame(right, bg=CARD_BG,
                         highlightbackground=BORDER, highlightthickness=1)
        strip.pack(fill="x", padx=6, pady=(0, 6))
        tk.Label(strip, text="Plan:", bg=CARD_BG, fg=MUTED,
                 font=("Segoe UI", 7, "bold")).pack(side="left", padx=6, pady=4)
        self._plan_lbl = tk.Label(strip, text="—", bg=CARD_BG, fg=TEXT,
                                  font=("Segoe UI", 7), wraplength=230, justify="left")
        self._plan_lbl.pack(side="left", padx=4, pady=4)

    # ── footer ────────────────────────────────
    def _build_footer(self):
        foot = tk.Frame(self, bg="#13131F", height=32)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)

        self._status = tk.Label(foot, text="Ready  –  select a scenario to begin",
                                bg="#13131F", fg=MUTED, font=("Segoe UI", 8))
        self._status.pack(side="left", padx=12, pady=6)

        tk.Label(foot, text="HTN Engine · NetworkX · Matplotlib · Tkinter",
                 bg="#13131F", fg="#4A4A6A",
                 font=("Segoe UI", 7)).pack(side="right", padx=12)

        # progress bar
        self._pcanvas = tk.Canvas(foot, bg="#13131F", highlightthickness=0,
                                  width=180, height=8)
        self._pcanvas.pack(side="right", padx=(0, 6), pady=12)
        self._pcanvas.create_rectangle(0, 0, 180, 8, fill=BTN_BG, outline="")
        self._pbar = self._pcanvas.create_rectangle(0, 0, 0, 8, fill=ACCENT, outline="")

    def _on_close(self):
        self._destroyed = True
        self._run_id += 1   # stop any running animation
        self.destroy()

    def _safe(self, widget, **kw):
        """Configure a widget only if it still exists.
        Prevents TclError when animation callbacks fire after widgets are destroyed.
        """
        try:
            widget.configure(**kw)
        except tk.TclError:
            pass

    def _safe_coords(self, canvas, item, *coords):
        """Update canvas item coords only if canvas still exists.
        Prevents TclError when the progress bar canvas is gone.
        """
        try:
            canvas.coords(item, *coords)
        except tk.TclError:
            pass

    def _set_progress(self, frac):
        self._safe_coords(self._pcanvas, self._pbar,
                          0, 0, int(180 * max(0, min(1, frac))), 8)

    # ── run scenario ──────────────────────────
    def _run_scenario(self, idx):
        if self._anim_running:
            return
        self._run_id += 1   # invalidate any pending callbacks from previous run
        self._set_active_btn(idx)
        sc    = SCENARIOS[idx]
        state = {**initial_state(), **sc["state_patch"]}

        self._update_badges(state)
        self._set_progress(0)

        root = TreeNode("GOAL", kind="compound", method="root")
        plan, final_state = htn_plan(sc["goal"], state, root)

        if plan is None:
            self._status.configure(
                text=f"⚠  Planning failed for '{sc['title']}' – no applicable method or primitive failed.")
            self._plan_lbl.configure(text="Planning failed")
            self._tree_sub.configure(text=f"— {sc['title']} (failed)")
            return

        self._G       = build_graph(root)
        self._pos     = hierarchy_pos(self._G, root=0)
        self._sc_title = sc["title"]

        self._tree_sub.configure(text=f"— {sc['title']}")
        self._redraw_tree()
        self._plan_lbl.configure(text="  →  ".join(plan))
        self._status.configure(text=f"Running: {sc['title']}  |  {len(plan)} steps")

        self._build_cards(plan)

        threading.Thread(
            target=self._animate,
            args=(plan, final_state, self._run_id),
            daemon=True,
        ).start()

    # ── decomposition tree drawing ─────────────
    def _redraw_tree(self, active_nid=None):
        draw_tree_on_ax(
            self._G, self._pos, self._ax, self._sc_title,
            panel_bg=PANEL_BG, border=BORDER, active_nid=active_nid,
        )
        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()

    # ── step cards ────────────────────────────
    def _build_cards(self, plan):
        for w in self._cframe.winfo_children():
            w.destroy()
        self._step_cards = []
        for i, task in enumerate(plan):
            icon, label, desc, color = ACTION_META.get(task, ("▶", task, task, MUTED))
            card = self._make_card(i + 1, len(plan), icon, label, desc, color)
            card["frame"].pack(fill="x", padx=3, pady=3)
            self._step_cards.append(card)
        self._ccanvas.update_idletasks()
        self._ccanvas.configure(scrollregion=self._ccanvas.bbox("all"))

    def _make_card(self, step, total, icon, label, desc, color):
        frame = tk.Frame(self._cframe, bg=CARD_BG,
                         highlightbackground=BORDER, highlightthickness=1)
        # colored left stripe
        tk.Frame(frame, bg=color, width=4).pack(side="left", fill="y")

        body = tk.Frame(frame, bg=CARD_BG)
        body.pack(side="left", fill="both", expand=True, padx=8, pady=7)

        top = tk.Frame(body, bg=CARD_BG)
        top.pack(fill="x")
        tk.Label(top, text=f"Step {step}/{total}", bg=CARD_BG, fg=MUTED,
                 font=("Segoe UI", 7)).pack(side="left")
        status_lbl = tk.Label(top, text="⏳ Waiting", bg=CARD_BG, fg=MUTED,
                               font=("Segoe UI", 7))
        status_lbl.pack(side="right")

        title_lbl = tk.Label(body, text=f"{icon}  {label}", bg=CARD_BG, fg=TEXT,
                             font=("Segoe UI", 9, "bold"), anchor="w")
        title_lbl.pack(fill="x", pady=(2, 0))

        desc_lbl = tk.Label(body, text=desc, bg=CARD_BG, fg=MUTED,
                            font=("Segoe UI", 7), anchor="w")
        desc_lbl.pack(fill="x")

        bar_cv = tk.Canvas(body, bg=CARD_BG, highlightthickness=0, height=3)
        bar_cv.pack(fill="x", pady=(5, 0))
        bar_cv.create_rectangle(0, 0, 2000, 3, fill=BTN_BG, outline="")
        bar_fill = bar_cv.create_rectangle(0, 0, 0, 3, fill=color, outline="")

        return dict(frame=frame, body=body, status_lbl=status_lbl,
                    title_lbl=title_lbl, desc_lbl=desc_lbl,
                    bar_cv=bar_cv, bar_fill=bar_fill, color=color)

    def _card_set_active(self, idx):
        if idx >= len(self._step_cards):
            return
        c = self._step_cards[idx]
        for w in (c["frame"], c["body"], c["status_lbl"],
                  c["title_lbl"], c["desc_lbl"], c["bar_cv"]):
            self._safe(w, bg=CARD_ACT)
        self._safe(c["frame"], highlightbackground=ACCENT)
        self._safe(c["status_lbl"], text="▶ Running", fg=c["color"])
        # animate mini bar
        try:
            total_w = c["bar_cv"].winfo_width() or 270
        except tk.TclError:
            return
        run_id  = self._run_id
        def _tick(s, steps=18):
            if s > steps or self._run_id != run_id:
                return
            self._safe_coords(c["bar_cv"], c["bar_fill"],
                              0, 0, int(total_w * s / steps), 3)
            self.after(28, _tick, s + 1)
        _tick(0)
        # scroll into view
        try:
            self._ccanvas.update_idletasks()
            self._ccanvas.yview_moveto(idx / max(len(self._step_cards), 1))
        except tk.TclError:
            pass

    def _card_set_done(self, idx):
        if idx >= len(self._step_cards):
            return
        c = self._step_cards[idx]
        for w in (c["frame"], c["body"], c["status_lbl"],
                  c["title_lbl"], c["desc_lbl"], c["bar_cv"]):
            self._safe(w, bg=CARD_DONE)
        self._safe(c["frame"], highlightbackground=GREEN)
        self._safe(c["status_lbl"], text="✔ Done", fg=GREEN)
        try:
            total_w = c["bar_cv"].winfo_width() or 270
        except tk.TclError:
            return
        self._safe_coords(c["bar_cv"], c["bar_fill"], 0, 0, total_w, 3)

    # ── animation (background thread) ─────────
    def _animate(self, plan, final_state, run_id):
        """
        Runs in a daemon thread. For each step:
          1. Activates the step card (purple, animated bar)
          2. Highlights the matching primitive node on the tree (white ring)
          3. Flips the world-state badge to ON/green
        All UI updates go through self.after() to stay on the main thread.
        run_id guards against stale callbacks from a previous scenario run.
        """
        self._anim_running = True

        def _find_nid(task):
            for nid, data in self._G.nodes(data=True):
                if data["kind"] == "primitive" and task in data["label"]:
                    return nid
            return None

        for i, task in enumerate(plan):
            if self._run_id != run_id:   # scenario changed — abort
                break
            nid = _find_nid(task)

            def _on_activate(i=i, task=task, nid=nid, rid=run_id):
                if self._destroyed or self._run_id != rid:
                    return
                self._card_set_active(i)
                self._safe(self._step_lbl, text=f"Step {i+1}/{len(plan)}")
                self._safe(self._status,   text=f"▶  Step {i+1}/{len(plan)}: {task}")
                self._set_progress(i / len(plan))
                if nid is not None:
                    self._redraw_tree(active_nid=nid)

            self.after(0, _on_activate)
            time.sleep(1.2)

            if self._run_id != run_id:
                break

            def _on_done(i=i, task=task, rid=run_id):
                if self._destroyed or self._run_id != rid:
                    return
                self._card_set_done(i)
                key = TASK_TO_STATE.get(task)
                if key and key in self._badge_vars:
                    self._badge_vars[key].set("ON")
                    self._safe(self._badge_labels[key], bg=GREEN)

            self.after(0, _on_done)
            time.sleep(0.15)

        def _finish(rid=run_id):
            if self._destroyed or self._run_id != rid:
                return
            self._redraw_tree(active_nid=None)
            self._set_progress(1.0)
            self._safe(self._step_lbl, text="Done ✔")
            self._safe(self._status,
                       text=f"✔  Completed: {self._sc_title}  |  {len(plan)} actions executed")
            self._update_badges(final_state)

        self.after(0, _finish)
        self._anim_running = False

    # ── badge helper ──────────────────────────
    def _update_badges(self, state):
        for key, val in state.items():
            if key in self._badge_vars:
                self._badge_vars[key].set("ON" if val else "OFF")
                self._safe(self._badge_labels[key], bg=GREEN if val else BTN_BG)


if __name__ == "__main__":
    app = HTNApp()
    app.mainloop()
