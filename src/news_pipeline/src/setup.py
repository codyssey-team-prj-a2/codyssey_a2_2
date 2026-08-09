"""config 서브커맨드: AI 설정 / 소스 / DB·로그 경로 대화형 등록·조회·삭제."""
from pathlib import Path

from src import ai_client, config_loader, prompt, ui
from src.logger import get_logger

log = get_logger("setup")

METHOD_LABELS = {"rss": "RSS", "api": "API", "crawl": "크롤링"}
METHOD_CHOICES = [("rss", "RSS"), ("api", "API"), ("crawl", "크롤링")]

PROVIDER_LABELS = {
    "openai": "GPT (OpenAI)", "google": "Gemini (Google)", "anthropic": "Claude (Anthropic)"
}
PROVIDER_CHOICES = list(PROVIDER_LABELS.items())

LOG_LEVEL_CHOICES = [
    ("DEBUG", "DEBUG (모든 개발 정보 기록)"),
    ("INFO", "INFO (일반적인 실행 흐름 기록 - 권장)"),
    ("WARNING", "WARNING (경고 이상만 기록)"),
    ("ERROR", "ERROR (에러 발생 시에만 기록)"),
]


def set_api_key() -> None:
    provider = prompt.ask_select(
        "AI 서비스를 제공할 플랫폼을 선택하세요", PROVIDER_CHOICES, allow_back=False
    )
    default_model = ai_client.DEFAULT_MODELS[provider]
    model = prompt.ask_text(
        f"사용할 모델명을 입력하세요 (예: {default_model})", default=default_model
    ).strip() or default_model
    key = prompt.ask_password("API Key를 입력하세요 (화면에 표시되지 않습니다)").strip()
    if not key:
        ui.print_error("빈 값은 저장하지 않습니다.")
        return

    config_loader.set_env_var("LLM_PROVIDER", provider)
    config_loader.set_env_var("LLM_MODEL", model)
    config_loader.set_env_var("LLM_API_KEY", key)
    masked = key[:4] + "*" * max(len(key) - 4, 0)
    ui.print_success(
        f"[{PROVIDER_LABELS[provider]} / {model}] 설정이 .env 파일에 저장되었습니다 (키: {masked})"
    )
    log.info(f"LLM 설정 등록: provider={provider} model={model}")


def set_db_path() -> None:
    config = config_loader.load_config()
    storage = config.setdefault("storage", {})
    current_dir = str(Path(storage.get("db_path", "data/news_pipeline.db")).parent)
    ui.print_info(
        "안내: 파일명(news_pipeline.db)은 고정되며, 저장될 디렉토리 경로만 설정합니다.\n"
        f"현재 경로: {current_dir}/"
    )
    new_dir = prompt.ask_text(
        "새로운 DB 폴더 경로를 입력하세요 (현재 경로 유지는 Enter)", default=""
    ).strip()
    if not new_dir:
        ui.print_info("변경하지 않았습니다.")
        return
    storage["db_path"] = str(Path(new_dir) / "news_pipeline.db")
    config_loader.save_config(config)
    ui.print_success(f"DB 경로가 [{storage['db_path']}/] 로 변경되었습니다. (다음 실행부터 적용)")
    log.info(f"DB 경로 변경: {storage['db_path']}")


def set_log_config() -> None:
    config = config_loader.load_config()
    logging_cfg = config.setdefault("logging", {})
    current_dir = str(Path(logging_cfg.get("file", "logs/app.log")).parent)
    ui.print_info(
        "안내: 파일명(app.log)은 고정되며, 저장될 디렉토리 경로만 설정합니다.\n"
        f"현재 경로: {current_dir}/"
    )
    new_dir = prompt.ask_text(
        "새로운 로그 폴더 경로를 입력하세요 (현재 경로 유지는 Enter)", default=""
    ).strip()
    level = prompt.ask_select(
        "기록할 로그 수준을 선택하세요", LOG_LEVEL_CHOICES, allow_back=False
    )
    if new_dir:
        logging_cfg["file"] = str(Path(new_dir) / "app.log")
    logging_cfg["level"] = level
    config_loader.save_config(config)
    ui.print_success(
        f"로그 경로 [{logging_cfg['file']}], 수준 [{level}] 로 변경되었습니다. (다음 실행부터 적용)"
    )
    log.info(f"로그 설정 변경: {logging_cfg}")


def add_source() -> None:
    config = config_loader.load_config()
    name = prompt.ask_text("소스 이름 (예: naver_it_rss)").strip()
    if not name:
        ui.print_error("소스 이름은 비워둘 수 없습니다.")
        return
    if any(s["name"] == name for s in config["news_sources"]):
        ui.print_error(f"이미 등록된 소스 이름입니다: {name}")
        return
    method = prompt.ask_select("수집 방식을 고르세요", METHOD_CHOICES, allow_back=False)
    url = prompt.ask_text("주소 (URL)").strip()
    category = prompt.ask_text("카테고리", default="종합").strip()

    source = {"name": name, "method": method, "url": url, "category": category, "enabled": True}
    config["news_sources"].append(source)
    config_loader.save_config(config)
    ui.print_success(f"소스 등록 완료: {name} ({METHOD_LABELS[method]})")
    log.info(f"소스 등록: {source}")
    list_sources()


def list_sources() -> None:
    config = config_loader.load_config()
    sources = config.get("news_sources", [])
    if not sources:
        ui.print_warning("등록된 소스가 없습니다. config add-source 로 추가하세요.")
        return
    rows = [
        [
            s["name"], METHOD_LABELS.get(s["method"], s["method"]), s["url"],
            ui.category_badge(s["category"]), ui.yes_no_badge(s.get("enabled", True)),
        ]
        for s in sources
    ]
    ui.print_table("등록된 뉴스 소스", ["이름", "방식", "주소", "카테고리", "활성화"], rows)


def remove_source(name: str) -> None:
    config = config_loader.load_config()
    before = len(config["news_sources"])
    config["news_sources"] = [s for s in config["news_sources"] if s["name"] != name]
    if len(config["news_sources"]) == before:
        ui.print_error(f"해당 이름의 소스를 찾을 수 없습니다: {name}")
        return
    config_loader.save_config(config)
    ui.print_success(f"소스 삭제 완료: {name}")
    log.info(f"소스 삭제: {name}")
