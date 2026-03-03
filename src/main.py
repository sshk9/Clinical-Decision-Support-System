import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from ui.main_window import run_app

if __name__ == "__main__":
    run_app()
