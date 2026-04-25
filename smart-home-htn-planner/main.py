#  Smart Home HTN Planner  –  Entry Point
#  Run:  python main.py
#  Opens the full desktop UI (no terminal output)
from ui import HTNApp

if __name__ == "__main__":
    app = HTNApp()
    app.mainloop()
