"""config 서브커맨드: API 키 / 소스 대화형 등록·조회·삭제."""
from src import config_loader, prompt, ui
from src.logger import get_logger

log = get_logger("setup")

METHOD_LABELS = {"rss": "RSS", "api": "API", "crawl": "크롤링"}
METHOD_CHOICES = [("rss", "RSS"), ("api", "API"), ("crawl", "크롤링")]


def set_api_key() -> None:
    key = prompt.ask_password("Gemini API 키를 입력하세요 (화면에 표시되지 않습니다)").strip()
    if not key:
        ui.print_error("빈 값은 저장하지 않습니다.")
        return
    config_loader.set_env_var("GEMINI_API_KEY", key)
    masked = key[:4] + "*" * max(len(key) - 4, 0)
    ui.print_success(f"API 키가 .env 에 저장되었습니다 ({masked})")
    log.info("GEMINI_API_KEY 등록됨")


def add_source() -> None:
    config = config_loader.load_config()
    name = prompt.ask_text("소스 이름 (예: naver_it_rss)").strip()
    if not name:
        ui.print_error("소스 이름은 비워둘 수 없습니다.")
        return
    if any(s["name"] == name for s in config["sources"]):
        ui.print_error(f"이미 등록된 소스 이름입니다: {name}")
        return
    method = prompt.ask_select("수집 방식을 고르세요", METHOD_CHOICES, allow_back=False)
    url = prompt.ask_text("주소 (URL)").strip()
    category = prompt.ask_text("카테고리", default="종합").strip()

    source = {"name": name, "method": method, "url": url, "category": category, "enabled": True}
    config["sources"].append(source)
    config_loader.save_config(config)
    ui.print_success(f"소스 등록 완료: {name} ({METHOD_LABELS[method]})")
    log.info(f"소스 등록: {source}")
    list_sources()


def list_sources() -> None:
    config = config_loader.load_config()
    sources = config.get("sources", [])
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
    before = len(config["sources"])
    config["sources"] = [s for s in config["sources"] if s["name"] != name]
    if len(config["sources"]) == before:
        ui.print_error(f"해당 이름의 소스를 찾을 수 없습니다: {name}")
        return
    config_loader.save_config(config)
    ui.print_success(f"소스 삭제 완료: {name}")
    log.info(f"소스 삭제: {name}")
