import shlex
import argparse
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from lib.system import ui, config_mgr
from lib.db import raw_store
from lib.db import sqlite_mgr as db

clean_parser = argparse.ArgumentParser(prog="clean", add_help=False)
clean_parser.add_argument("--policy", choices=["skip", "upsert"], default=None)


def _strip_html(text):
    """HTML 태그를 제거하고 연속 공백/개행을 하나로 합친다."""
    text = BeautifulSoup(text or "", "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def _normalize_date(published_at, collected_at):
    """발행일을 'YYYY-MM-DD' 형식으로 통일한다.

    published_at은 RSS마다 형식이 제각각(RFC822, ISO8601 등)이라 두 방식을
    순서대로 시도하고, 둘 다 실패하거나 값 자체가 없으면(결측값) 수집 시각
    (collected_at)의 날짜로 대체한다. 그마저도 없으면 오늘 날짜를 쓴다.
    """
    for parser in (parsedate_to_datetime, datetime.fromisoformat):
        if not published_at:
            break
        try:
            return parser(published_at).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            continue

    if collected_at:
        try:
            return datetime.fromisoformat(collected_at).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def clean_record(raw):
    """raw 레코드 1건을 정제한다. 제목/본문/URL 중 하나라도 비어있으면 None(무효)."""
    title = _strip_html(raw.get("title"))
    content = _strip_html(raw.get("content"))
    url = (raw.get("url") or "").strip()

    if not title or not content or not url:
        return None

    return {
        "news_id": url,
        "source": raw.get("source_name", ""),
        "category": raw.get("category", "종합"),
        "title": title,
        "content": content,
        "pub_date": _normalize_date(raw.get("published_at"), raw.get("collected_at")),
    }


def run_clean_preview():
    """raw 저장소 전체를 읽어 정제 결과를 미리 보여준다(아직 DB 저장은 하지 않음)."""
    raw_records = raw_store.read_all()
    if not raw_records:
        print(f"\n{ui.ERR}정제할 raw 데이터가 없습니다. 먼저 뉴스 수집(fetch)을 실행하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    valid, invalid = [], 0
    for raw in raw_records:
        cleaned = clean_record(raw)
        if cleaned is None:
            invalid += 1
        else:
            valid.append(cleaned)

    print(f"\n{ui.HL}[ 정제 미리보기 ]{ui.FG}")
    print(f"  - raw 전체: {len(raw_records)}건")
    print(f"  - 필수 필드(제목/본문/URL) 누락으로 제외: {invalid}건")
    print(f"  - 정제 통과: {len(valid)}건")
    for c in valid[:5]:
        print(f"      - [{c['category']}] {c['title']}")
    if len(valid) > 5:
        print(f"      ... 외 {len(valid) - 5}건")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_clean(policy=None):
    """raw 저장소를 읽어 정제 후 clean_news 테이블에 저장한다.

    policy가 'skip'이면 이미 저장된 news_id(URL)는 건드리지 않고 건너뛰고,
    'upsert'면 title/content를 최신 내용으로 덮어쓴다. 미지정 시
    config.json의 fetch.duplicate_policy(기본값 'skip')를 따른다.
    """
    policy = policy or config_mgr.load_config().get("fetch", {}).get("duplicate_policy", "skip")
    if policy not in ("skip", "upsert"):
        print(f"\n{ui.ERR}알 수 없는 중복 정책입니다: {policy} (skip 또는 upsert만 가능){ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    db.initialize_db()
    raw_records = raw_store.read_all()
    if not raw_records:
        print(f"\n{ui.ERR}정제할 raw 데이터가 없습니다. 먼저 뉴스 수집(fetch)을 실행하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    invalid = 0
    inserted = 0
    duplicate_skipped = 0
    to_save = []

    for raw in raw_records:
        cleaned = clean_record(raw)
        if cleaned is None:
            invalid += 1
            continue

        existing = db.get_by_news_id(cleaned["news_id"])
        if existing and policy == "skip":
            duplicate_skipped += 1
            continue

        inserted += 1
        to_save.append(cleaned)

    saved = db.upsert_clean_news(to_save) if to_save else 0

    print(f"\n{ui.HL}[ 정제 결과 (정책: {policy}) ]{ui.FG}")
    print(f"  - raw 전체: {len(raw_records)}건")
    print(f"  - 필수 필드 누락(제외): {invalid}건")
    print(f"  - 중복 스킵: {duplicate_skipped}건")
    print(f"  - DB 저장(신규/갱신): {saved}건")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" 데이터 정제 (Clean) 제어소 ")
        print(f"{ui.FG}  아래 메뉴 번호를 선택하거나, CLI 명령어를 직접 입력하여 실행할 수 있습니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 정제 미리보기 (HTML 태그 정제 + 빈 필드 제외, DB 저장 안 함)")
        print("  2. 정제 실행 및 DB 저장 (skip/upsert 정책 적용)")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  clean --policy [skip|upsert]")
        print("  (입력 예: clean --policy upsert)")

        print("-" * w)

        user_input = input(f"\n{ui.HL}Codyssey/clean > {ui.FG}").strip()

        if not user_input:
            continue
        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_clean_preview()
        elif user_input == '2':
            run_clean()
        elif user_input.startswith("clean"):
            run_clean_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")


def run_clean_cli(command_str):
    try:
        args_list = shlex.split(command_str)
        args, unknown = clean_parser.parse_known_args(args_list[1:])
        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return
        run_clean(policy=args.policy)
    except SystemExit:
        print("\n[오류] 옵션 파싱에 실패했습니다.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")