print("main.py started")

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

print("about to import ui.main_window")
from ui.main_window import run_app
print("imported run_app from:", run_app)

if __name__ == "__main__":
    print("calling run_app() now")
    run_app()
    print("run_app() returned")
