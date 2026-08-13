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
fetch_parser.add_argument("--limit", type=str, default="20")

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
    """RSS 피드 XML을 요청/파싱해서 뉴스 항목을 추출한다."""
    uri = source.get("uri") or source.get("url") or ""
    if not uri:
        return [], "등록된 URI가 없습니다."

    try:
        resp = requests.get(uri, timeout=timeout, headers={"User-Agent": USER_AGENT})
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
    """크롤링 방식으로 뉴스 항목을 추출한다."""
    uri = source.get("uri") or source.get("url") or ""
    if not uri:
        return [], "등록된 URI가 없습니다."

    try:
        resp = requests.get(uri, timeout=timeout, headers={"User-Agent": USER_AGENT})
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
            link_url = bold_link.get("href", uri)
        else:
            first_link = li.find("a")
            title = li.get_text(" ", strip=True)[:80]
            link_url = first_link.get("href", uri) if first_link else uri

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
    """메인 메뉴 루프"""
    while True:
        ui.clear_screen()
        
        # [1] 상단 헤더
        ui.draw_header(" 뉴스 데이터 수집 (Fetch) 제어소 ")
        print(f"{ui.FG}  등록된 뉴스 피드를 조회하고 데이터 수집 파이프라인을 실행합니다.\n")
        
        # [2] 등록된 뉴스 피드 현황 (5번 수정사항: 구분감 및 가독성 극대화)
        config = config_mgr.load_config()
        sources = config.get("news_sources", [])
        
        ui.draw_line("─")
        print(f"{ui.HL}  [ 현재 등록된 뉴스 피드 현황 ]{ui.FG}")
        if not sources:
            print("  (등록된 뉴스 소스가 없습니다. 환경 설정 메뉴에서 먼저 등록해주세요.)")
        else:
            for idx, s in enumerate(sources, 1):
                name = s.get("name", "이름없음")
                method = (s.get("method") or "rss").upper()
                uri = s.get("uri") or s.get("url") or "URI 없음"
                category = s.get("category", "종합")
                status = "활성" if s.get("enabled", True) else "비활성"
                
                print(f"  {idx}. {ui.HL}{name}{ui.FG}")
                print(f"     ├─ [방식] {ui.HL}{method:<5}{ui.FG} │  [카테고리] {category:<6} │  [상태] {status}")
                print(f"     └─ [URI ] {uri}")
        ui.draw_line("─")
        print()
        
        # [3] 대화형 메뉴 (1번 수정사항: 메뉴 번호 직관성 확보)
        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 뉴스 수집 실행 (등록 소스 목록 선택)")
        print("  2. 현재 수집된 데이터 수 확인")
        print("  P. 상위 메뉴로 이동\n")
        
        # [1번 수정사항] CLI 직접 입력 가이드는 메뉴 하단 보조 안내문으로 이동
        print(f"{ui.FG}  ※ CLI 직접 입력 예시: fetch --source [소스명|all] [--limit 20]")
        ui.draw_line("─")
        
        # [4] 명령어 입력 프롬프트 (3번/4번 수정사항 반영)
        user_input = input(f"\n{ui.HL}입력 (메뉴번호 / CLI ) > {ui.FG}").strip()
        
        if not user_input:
            continue
            
        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_fetch_interactive()
        elif user_input == '2':
            show_data_status()
        elif user_input.startswith("fetch"):
            run_fetch_cli(user_input)
        else:
            print(f"\n{ui.ERR}올바르지 않은 명령어나 번호입니다.{ui.FG}")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")


def run_fetch_cli(command_str):
    """CLI 직접 입력 명령 파싱"""
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
    """1번 메뉴 선택 시: 등록된 소스 객관식 선택 & 제한 건수 입력 (2번/3번/4번 수정사항 적용)"""
    config = config_mgr.load_config()
    sources = config.get("news_sources", [])
    
    if not sources:
        ui.clear_screen()
        ui.draw_header(" 대화형 뉴스 수집 설정 ")
        print(f"\n{ui.ERR}등록된 뉴스 소스가 없습니다. 환경 설정 메뉴에서 먼저 등록해주세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    # [1] 소스 선택 루프 (잘못된 입력 시 상위 메뉴로 안 튕기고 안내 후 재입력)
    selected_source = None
    while True:
        ui.clear_screen()
        ui.draw_header(" 대화형 뉴스 수집 설정 ")
        
        print(f"{ui.HL}  [ 수집할 뉴스 소스 선택 ]{ui.FG}")
        print("  0) 전체 수집 (all)")
        source_map = {"0": "all"}
        
        for idx, s in enumerate(sources, 1):
            name = s.get("name", f"source_{idx}")
            method = (s.get("method") or "rss").upper()
            category = s.get("category", "종합")
            print(f"  {idx}) {name} (방식: {method} / 카테고리: {category})")
            source_map[str(idx)] = name
            
        print("\n C) 취소\n")
        ui.draw_line("─")
        
        sel = input(f"{ui.FG}▶ 수집할 소스 번호를 선택하세요 [C: 취소] > {ui.HL}").strip()
        
        # 3번/4번 반영: p, c, C 입력 시 취소하고 돌아가기
        if sel.lower() in ['c']:
            print(f"\n{ui.HL}>> 수집 설정을 취소하고 상위 메뉴로 돌아갑니다.{ui.FG}")
            return
            
        if sel in source_map:
            selected_source = source_map[sel]
            break
        else:
            # 2번 반영: 상위 메뉴로 돌아가지 않고 재입력 요구
            print(f"\n{ui.ERR}[오류] 잘못된 번호입니다. 등록된 소스 번호(0~{len(sources)})를 입력해 주세요.{ui.FG}")
            ui.pause("다시 입력하려면 [Enter]를 누르세요...")

    print(f"\n{ui.HL}>> 선택된 소스: [{selected_source}]{ui.FG}\n")

    # [2] 수집 제한 건수 입력 루프 (2번/3번/4번 수정사항 적용)
    limit_val = "20"
    while True:
        ui.draw_line("─")
        limit_input = input(f"{ui.FG}▶ 수집 제한 건수 입력 [기본값: 20 (Enter)] [C: 취소] > {ui.HL}").strip()
        
        if limit_input.lower() in ['c']:
            print(f"\n{ui.HL}>> 수집 설정을 취소하고 상위 메뉴로 돌아갑니다.{ui.FG}")
            return
            
        if not limit_input:
            limit_val = "20"
            print(f"\n{ui.HL}>> 기본값 20건으로 설정하여 수집을 진행합니다.{ui.FG}")
            break
            
        if limit_input.isdigit() and int(limit_input) > 0:
            limit_val = limit_input
            break
        else:
            # 2번 반영: 숫자가 아닐 경우 안내 후 재입력
            print(f"\n{ui.ERR}[오류] 올바른 수집 제한 건수(양의 정수)를 입력해 주세요.{ui.FG}")
            ui.pause("다시 입력하려면 [Enter]를 누르세요...")

    execute_fetch_logic(selected_source, limit_val, is_cli=False)


def execute_fetch_logic(source, limit, is_cli=False):
    """수집 실행 결과 화면 출력"""
    print()
    ui.draw_line("━")
    mode_text = "[CLI 모드]" if is_cli else "[대화형 모드]"
    print(f"{ui.HL}>> {mode_text} 뉴스 데이터 수집을 시작합니다...{ui.FG}")
    print(f"   (적용 옵션: source={source}, limit={limit})\n")

    targets = _resolve_sources(source)
    if not targets:
        print(f"{ui.ERR}'{source}' 이름의 등록된 소스를 찾을 수 없습니다.{ui.FG}")
        ui.draw_line("━")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    try:
        limit_int = int(limit)
        if limit_int <= 0:
            raise ValueError
    except (TypeError, ValueError):
        print(f"{ui.ERR}[오류] 올바른 수집 제한 건수(양의 정수)가 아니므로 기본값 20건을 적용합니다.{ui.FG}")
        limit_int = 20

    timeout = config_mgr.load_config().get("fetch", {}).get("timeout_sec", DEFAULT_TIMEOUT_SEC)

    total = 0
    total_fail = 0
    for src in targets:
        method = src.get("method", "rss")
        handler = FETCH_HANDLERS.get(method)
        if handler is None:
            print(f"  [건너뜀] {src.get('name')}: '{method}' 수집 방식은 아직 지원하지 않습니다.\n")
            continue

        print(f"  [수집 진행] {src.get('name')} ({method.upper()}) 데이터 요청 중...")
        records, error = handler(src, timeout=timeout)
        if error:
            print(f"  {ui.ERR}[실패] {src.get('name')}: {error}{ui.FG}\n")
            total_fail += 1
            continue

        records = records[:limit_int]
        for r in records:
            raw_store.append(src.get("name", ""), r)
            print(f"    - {r['title']}")
        print(f"  └─ [{src.get('name')}] {len(records)}건 추출 및 raw 저장 완료\n")
        total += len(records)

    ui.draw_line("─")
    print(f"{ui.HL}>> 수집 작업이 완료되었습니다! (총 {total}건 추출, 실패 {total_fail}건){ui.FG}")
    ui.draw_line("━")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def show_data_status():
    """현재 수집된 Raw 데이터 상태 출력"""
    ui.clear_screen()
    ui.draw_header(" 현재 수집 데이터 보관 현황 ")
    
    sources = raw_store.list_sources()
    if not sources:
        print("\n  아직 수집된 raw 데이터가 없습니다.")
    else:
        total = 0
        latest = None
        print()
        for name in sources:
            records = raw_store.read_all(name)
            total += len(records)
            for r in records:
                collected_at = r.get("collected_at")
                if collected_at and (latest is None or collected_at > latest):
                    latest = collected_at
            print(f"  • {name}.jsonl  : {len(records)}건 보관 중")
            
        ui.draw_line("─")
        print(f"  * 전체 수집 데이터 수 : {total}건")
        print(f"  * 최근 수집 완료 시각 : {latest or '알 수 없음'}")
        
    ui.draw_line("━")
    ui.pause("\n[Enter]를 눌러 서브메뉴로 돌아갑니다...")