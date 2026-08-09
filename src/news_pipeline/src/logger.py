"""파일 로깅 설정 (화면 출력은 담당하지 않음, 화면은 ui.py/rich가 담당)."""
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "app.log"

_configured = False
_level_name = "INFO"


def configure(logging_cfg: dict) -> None:
    """main.py가 기동 시 config.json의 logging.* 로 덮어쓰기 위해 호출한다.

    setup_logging()보다 먼저(= cli/menu를 import하기 전에) 호출해야 적용된다.
    다른 모듈들이 import 시점에 get_logger()를 호출해 setup_logging()을 이미
    실행시켜버리면 그 뒤에 configure()를 불러도 소용없기 때문.
    """
    global LOG_PATH, _level_name
    file = logging_cfg.get("file")
    if file:
        LOG_PATH = BASE_DIR / file
    level = logging_cfg.get("level")
    if level:
        _level_name = level


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("news_pipeline")
    root.setLevel(getattr(logging, _level_name, logging.INFO))
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"news_pipeline.{name}")
