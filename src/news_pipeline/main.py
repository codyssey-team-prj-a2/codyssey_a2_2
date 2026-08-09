import sys

from src import config_loader, db, raw_store
from src import logger as logger_mod

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

config_loader.load_env()
_config = config_loader.load_config()

# cli/menu를 import하기 전에 먼저 적용해야 한다: menu.py가 import되면서
# 연쇄적으로 여러 모듈이 get_logger()를 호출해 로깅 설정이 그 시점에 굳어버리기 때문.
logger_mod.configure(_config.get("logging", {}))
db.configure(_config.get("storage", {}).get("db_path"))
raw_store.configure(_config.get("storage", {}).get("raw_dir"))

from src import cli, menu  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) == 1:
        menu.run_menu()
    else:
        cli.main()
