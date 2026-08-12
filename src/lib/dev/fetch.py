# lib/dev/fetch.py
import argparse
import re
import shlex
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

from lib.db import raw_store
from lib.system import config_mgr, ui

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
fetch_parser = argparse.ArgumentParser(prog="fetch", add_help=False)
fetch_parser.add_argument("--source", type=str, required=True)
fetch_parser.add_argument("--limit", type=str, default="50")

USER_AGENT = "codyssey-news-pipeline/0.1 (edu project)"
DEFAULT_TIMEOUT_SEC = 10


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _resolve_sources(source_name):
    """config.json의 news_sources 중 이름이 일치하는(또는 all이면 전체) 소스 목록을 돌려준다."""
    sources = config_mgr.load_config().get("news_sources", [])
    sources = [s for s in sources if s.get("name")]
    if source_name == "all":
        return sources
    return [s for s in sources if s.get("name") == source_name]


def fetch_via_rss(source, timeout=DEFAULT_TIMEOUT_SEC):
    """RSS 피드 XML을 요청/파싱해서 뉴스 항목을 딕셔너리 리스트로 추출한다.

    통신 실패(타임아웃/DNS/HTTP 에러 등)는 예외를 올리지 않고
    (records, error_message) 형태로 돌려줘서 호출부가 소스 하나의 실패로
    전체 수집이 죽지 않도록 한다.
    """
    url = source.get("url") or source.get("uri") or ""
    if not url:
        return [], "등록된 URL이 없습니다."

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except requests.Timeout:
        return [], f"요청 시간 초과({timeout}초)"
    except requests.RequestException as e:
        return [], f"요청 실패: {e}"

    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        return [], f"RSS 파싱 실패: {feed.bozo_exception}"

    records = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if not title:
            continue
        records.append({
            "source_name": source.get("name", ""),
            "method": "rss",
            "category": source.get("category", "종합"),
            "title": title,
            "content": entry.get("summary", title),
            "url": entry.get("link", ""),
            "published_at": entry.get("published", None),
            "collected_at": _now_iso(),
        })
    return records, None


_RELATIVE_DATE_RE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")


def _parse_relative_date(text):
    """본문에 '8월 12일'처럼 상대적인 날짜 표기가 있으면 올해 기준 ISO 날짜로 변환한다.

    크롤링 대상(위키백과류 목록 페이지)은 RSS와 달리 발행일 필드가 따로 없고
    항목 텍스트 안에 날짜가 섞여 있는 경우가 많아, 없으면 None을 돌려주고
    clean 단계의 날짜 결측값 처리(수집 시각 -> 오늘 날짜 순 대체)에 맡긴다.
    """
    m = _RELATIVE_DATE_RE.search(text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = datetime.now(timezone.utc).year
    try:
        return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def fetch_via_crawl(source, timeout=DEFAULT_TIMEOUT_SEC):
    """위키백과류 목록 페이지(div.mw-parser-output 안의 <li>)를 크롤링해서
    뉴스 항목을 딕셔너리 리스트로 추출한다.

    RSS와 달리 정해진 스펙이 없어 HTML 구조를 직접 가정한다(이 프로젝트에서는
    '포털:최근 사건' 같은 위키백과류 페이지 구조를 기준으로 검증함). 등록한
    소스의 HTML 구조가 다르면 결과가 비거나 품질이 떨어질 수 있다 — 이게
    크롤링 방식의 근본적인 한계다(RSS/API처럼 구조가 보장되지 않음).
    """
    url = source.get("url") or source.get("uri") or ""
    if not url:
        return [], "등록된 URL이 없습니다."

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except requests.Timeout:
        return [], f"요청 시간 초과({timeout}초)"
    except requests.RequestException as e:
        return [], f"요청 실패: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")
    content_div = soup.select_one("div.mw-parser-output")
    if not content_div:
        return [], "콘텐츠 영역(div.mw-parser-output)을 찾지 못했습니다."

    records = []
    for li in content_div.find_all("li"):
        bold_link = li.select_one("b a")
        if bold_link:
            title = bold_link.get_text(strip=True)
            link_url = bold_link.get("href", url)
        else:
            first_link = li.find("a")
            title = li.get_text(" ", strip=True)[:80]
            link_url = first_link.get("href", url) if first_link else url

        text = li.get_text(" ", strip=True)
        if not title or not text:
            continue

        records.append({
            "source_name": source.get("name", ""),
            "method": "crawl",
            "category": source.get("category", "종합"),
            "title": title,
            "content": text,
            "url": link_url,
            "published_at": _parse_relative_date(text),
            "collected_at": _now_iso(),
        })
    return records, None


FETCH_HANDLERS = {"rss": fetch_via_rss, "crawl": fetch_via_crawl}


def run_menu_show():
    """
    설명 영역 / 등록된 피드 목록 / 메뉴 영역 / 명령어 입력 영역을 분리하고,
    번호 선택과 명령어 입력을 동시에 처리하는 메인 루프입니다.
    """
    while True:
        ui.clear_screen()
        w = ui.get_width()
        
        # ==========================================
        # [1] 상단 헤더 및 가이드라인
        # ==========================================
        ui.draw_header(" 뉴스 데이터 수집 (Fetch) 제어소 ")
        print(f"{ui.FG}  현재 등록된 뉴스 피드 목록을 확인하고, 수집을 실행할 수 있습니다.\n")
        
        # ==========================================
        # [2] 등록된 뉴스 피드 정보 표시 영역 (신규 추가)
        # ==========================================
        config = config_mgr.load_config()
        sources = config.get("news_sources", [])
        
        print(f"{ui.HL}  [ 현재 등록된 뉴스 피드 현황 ]{ui.FG}")
        if not sources:
            print("  (등록된 뉴스 소스가 없습니다. 환경 설정 메뉴에서 먼저 등록해주세요.)")
        else:
            for s in sources:
                name = s.get("name", "이름없음")
                method = (s.get("method") or "rss").upper()
                url = s.get("url") or s.get("uri") or "URL 없음"
                category = s.get("category", "종합")
                status = "활성" if s.get("enabled", True) else "비활성"
                print(f"  - [{name}] 방식: {method} | 카테고리: {category} | 상태: {status}")
                print(f"    주소: {url}")
        print()
        
        # ==========================================
        # [3] 메뉴 영역
        # ==========================================
        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 뉴스 수집 실행 (대화형 파라미터 입력)")
        print("  2. 현재 수집된 데이터 수 확인")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")
        
        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  fetch --source [소스명] [--limit 숫자]")
        print("  (입력 예: fetch --source naver_it --limit 20 또는 fetch --source all)")
        
        print("-" * w)
        
        # ==========================================
        # [4] 명령어 입력 영역 (CLI / TUI 공존 프롬프트)
        # ==========================================
        user_input = input(f"\n{ui.HL}Codyssey/fetch > {ui.FG}").strip()
        
        if not user_input:
            continue
            
        # 4-1. 메뉴 번호 처리 (TUI 모드)
        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_fetch_interactive()
        elif user_input == '2':
            show_data_status()
            
        # 4-2. 명령어 직접 입력 처리 (CLI 모드)
        elif user_input.startswith("fetch"):
            run_fetch_cli(user_input)
            
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")

def run_fetch_cli(command_str):
    """
    사용자가 직접 입력한 'fetch --source naver --limit 20' 문자열을
    shlex로 쪼개서 argparse로 파싱하고 실행하는 함수.
    """
    try:
        args_list = shlex.split(command_str)
        args, unknown = fetch_parser.parse_known_args(args_list[1:])
        
        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return
            
        source = args.source
        limit = args.limit
        
        execute_fetch_logic(source, limit, is_cli=True)
        
    except SystemExit:
        print("\n[오류] 필수 파라미터가 누락되었습니다. '--source'를 반드시 포함하세요.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        print(f"\n[오류] 명령어 파싱 중 에러 발생: {e}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")

def run_fetch_interactive():
    """
    1번 메뉴를 선택했을 때 대화형으로 입력받는 함수
    """
    print(f"\n{ui.HL}[ 대화형 뉴스 수집 설정 ]{ui.FG}")
    print("안내: 입력을 취소하고 메뉴로 돌아가려면 언제든 'q'를 입력하세요.\n")
    
    source = ui.safe_input("▶ 수집할 소스명 입력 (필수, 예: naver_it 또는 all) [q:취소]: ")
    if not source or source.lower() == 'q': return
    
    print("\n  [옵션 추천] '--limit' 파라미터 (미입력 시 기본값 50 적용)")
    limit = ui.safe_input("▶ 수집 제한 건수 입력 (건너뛰려면 Enter) [q:취소]: ")
    if limit and limit.lower() == 'q': return
    
    limit_val = limit.strip() if limit.strip() else "50"
    
    execute_fetch_logic(source, limit_val, is_cli=False)

def execute_fetch_logic(source, limit, is_cli=False):
    """
    대화형(TUI) 방식이든 CLI 직접 입력 방식이든
    최종적으로 이 함수를 거쳐 동일한 비즈니스 로직을 수행하도록 중앙화.
    """
    print("\n" + "=" * 50)
    mode_text = "[CLI 모드]" if is_cli else "[대화형 모드]"
    print(f"{ui.HL}>> {mode_text} 뉴스 데이터 수집을 시작합니다...{ui.FG}")
    print(f"   (적용된 옵션: source={source}, limit={limit})")

    targets = _resolve_sources(source)
    if not targets:
        print(f"\n{ui.ERR}'{source}' 이름의 등록된 소스를 찾을 수 없습니다.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        limit_int = 50

    timeout = config_mgr.load_config().get("fetch", {}).get("timeout_sec", DEFAULT_TIMEOUT_SEC)

    total = 0
    total_fail = 0
    for src in targets:
        method = src.get("method", "rss")
        handler = FETCH_HANDLERS.get(method)
        if handler is None:
            print(f"   [건너뜀] {src.get('name')}: '{method}' 수집 방식은 아직 지원하지 않습니다.")
            continue

        print(f"   [진행] {src.get('name')} {method} 수집 중...")
        records, error = handler(src, timeout=timeout)
        if error:
            print(f"   {ui.ERR}[실패] {src.get('name')}: {error}{ui.FG}")
            total_fail += 1
            continue

        records = records[:limit_int]
        for r in records:
            raw_store.append(src.get("name", ""), r)
            print(f"      - {r['title']}")
        print(f"   [진행] {src.get('name')}: {len(records)}건 추출 및 raw 저장 완료")
        total += len(records)

    print(f"\n{ui.HL}>> 수집 작업이 완료되었습니다! (총 {total}건 추출, 실패 소스 {total_fail}건){ui.FG}")
    print("=" * 50)
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")

def show_data_status():
    print(f"\n{ui.HL}[ 현재 수집 데이터 상태 ]{ui.FG}")
    sources = raw_store.list_sources()
    if not sources:
        print("  아직 수집된 raw 데이터가 없습니다.")
    else:
        total = 0
        latest = None
        for name in sources:
            records = raw_store.read_all(name)
            total += len(records)
            for r in records:
                collected_at = r.get("collected_at")
                if collected_at and (latest is None or collected_at > latest):
                    latest = collected_at
            print(f"  - {name}.jsonl: {len(records)}건 보관 중")
        print(f"  - 전체: {total}건")
        print(f"  - 최근 수집 시각: {latest or '알 수 없음'}")
    ui.pause("\n[Enter]를 눌러 서브메뉴로 돌아갑니다...")