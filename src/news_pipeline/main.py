import sys

from src.config_loader import load_env
from src import cli, menu

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

load_env()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        menu.run_menu()
    else:
        cli.main()
