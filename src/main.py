print("MAIN: starting")

import sys
from pathlib import Path
print("MAIN: file =", __file__)
print("MAIN: before path =", sys.path[:3])

sys.path.append(str(Path(__file__).resolve().parent))
print("MAIN: after path add =", sys.path[:3])

print("MAIN: importing ui.main_window...")
from ui.main_window import run_app
print("MAIN: imported run_app =", run_app)

if __name__ == "__main__":
    print("MAIN: calling run_app()")
    run_app()
    print("MAIN: run_app() returned")
