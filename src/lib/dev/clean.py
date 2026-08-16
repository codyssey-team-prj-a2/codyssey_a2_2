# src/lib/dev/clean.py
import shlex
import argparse
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from lib.system import ui, config_mgr, logger_mgr, help_mgr
from lib.db import raw_store
from lib.db import sqlite_mgr as db

logger = logger_mgr.get_logger(__name__)

clean_parser = argparse.ArgumentParser(prog="clean", add_help=False)
clean_parser.add_argument("--policy", choices=["skip", "upsert"], default=None)

def _normalize_date(published_at, collected_at):
    for parser in (parsedate_to_datetime, datetime.fromisoformat):
        if not published_at: break
        try: return parser(published_at).strftime("%Y-%m-%d")
        except (TypeError, ValueError): continue

    if collected_at:
        try: return datetime.fromisoformat(collected_at).strftime("%Y-%m-%d")
        except (TypeError, ValueError): pass

    # [수정] timezone.utc 대신 로컬 타임존(KST) 기반으로 날짜 생성
    return datetime.now().astimezone().strftime("%Y-%m-%d")

def clean_record(raw):
    """Fetch가 추출한 텍스트를 기반으로 데이터 품질을 검증하고, 잔여 HTML을 안전하게 제거한다."""
    
    title = raw.get("title", "").strip()
    
    content = raw.get("content", "").strip()
    
    # [핵심 수정] 구버전 JSONL 파일이나 예상치 못한 HTML 태그가 남아있을 경우를 대비한 2차 안전망
    if "<" in title and ">" in title:
        title = BeautifulSoup(title, "html.parser").get_text(separator=" ", strip=True)
    if "<" in content and ">" in content:
        content = BeautifulSoup(content, "html.parser").get_text(separator=" ", strip=True)
        
    title = re.sub(r"\s+", " ", title)
    content = re.sub(r"\s+", " ", content) 
    
    if not content:
        content = title

    url = (raw.get("url") or "").strip()

    if not title or not url:
        return None

    # [핵심 수정] DB의 CURRENT_TIMESTAMP(UTC)를 무시하고 파이썬에서 로컬(KST) 시각을 직접 꽂아 넣음
    kst_now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "news_id": url,
        "source": raw.get("source_name", ""),
        "category": raw.get("category", "종합"),
        "title": title,
        "content": content,
        "pub_date": _normalize_date(raw.get("published_at"), raw.get("collected_at")),
        "created_at": kst_now  # 명시적인 로컬 타임스탬프 전달
    }

def run_clean_preview():
    raw_records = raw_store.read_all()
    if not raw_records:
        print(f"\n{ui.ERR}정제할 raw 데이터가 없습니다. 먼저 뉴스 수집(fetch)을 실행하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    valid, invalid = [], 0
    for raw in raw_records:
        cleaned = clean_record(raw)
        if cleaned is None: invalid += 1
        else: valid.append(cleaned)

    print(f"\n{ui.HL}[ 정제 미리보기 ]{ui.FG}")
    print(f"  - raw 전체: {len(raw_records)}건")
    print(f"  - 필수 필드(제목/URL) 누락으로 제외: {invalid}건")
    print(f"  - 정제 통과: {len(valid)}건")
    for c in valid[:5]:
        print(f"      - [{c['category']}] {c['title']}\n        └ {c['content'][:50]}...")
    if len(valid) > 5:
        print(f"      ... 외 {len(valid) - 5}건")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")

def run_clean(policy=None):
    policy = policy or config_mgr.load_config().get("fetch", {}).get("duplicate_policy", "skip")
    if policy not in ("skip", "upsert"):
        logger.error(f"알 수 없는 중복 정책으로 인해 정제 작업을 중단합니다: {policy}")
        print(f"\n{ui.ERR}알 수 없는 중복 정책입니다: {policy} (skip 또는 upsert만 가능){ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    db.initialize_db()
    raw_records = raw_store.read_all()
    if not raw_records:
        logger.warning("정제할 raw 데이터가 존재하지 않아 작업을 건너뜁니다.")
        print(f"\n{ui.ERR}정제할 raw 데이터가 없습니다. 먼저 뉴스 수집(fetch)을 실행하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    logger.info(f"데이터 정제 작업을 시작합니다. (대상: {len(raw_records)}건, 정책: {policy})")

    invalid, inserted, duplicate_skipped = 0, 0, 0
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

    try:
        saved = db.upsert_clean_news(to_save) if to_save else 0
        logger.info(f"데이터 정제 완료: 총 {len(raw_records)}건 중 {saved}건 DB 저장 성공 (필드 누락 제외: {invalid}건, 중복 스킵: {duplicate_skipped}건)")
    except Exception as e:
        logger.error(f"정제된 데이터 DB 저장 중 오류 발생: {e}")
        saved = 0

    print(f"\n{ui.HL}[ 정제 결과 (정책: {policy}) ]{ui.FG}")
    print(f"  - raw 대상: {len(raw_records)}건")
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
        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}\n  1. 정제 미리보기 (DB 저장 안 함)\n  2. 정제 실행 및 DB 저장 (skip/upsert 정책 적용)\n  p. 이전 메뉴로 돌아가기\n")
        print(f"{ui.HL}  [ CLI 입력 (H : 도움말) ]{ui.FG}\n  clean --policy [skip|upsert]\n")
        print("-" * w)

        user_input = input(f"\n{ui.HL}Codyssey/clean > {ui.FG}").strip()

        if not user_input: continue
        if user_input.lower() == 'p': break
        elif user_input == 'h': help_mgr.show_help("clean")
        elif user_input == '1': run_clean_preview()
        elif user_input == '2': run_clean()
        elif user_input.startswith("clean"): run_clean_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")

def run_clean_cli(command_str):
    try:
        args_list = shlex.split(command_str)
        args, unknown = clean_parser.parse_known_args(args_list[1:])
        if unknown: return
        run_clean(policy=args.policy)
    except SystemExit: pass