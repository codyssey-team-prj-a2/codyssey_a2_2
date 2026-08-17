# src/lib/dev/fetch.py
import argparse
import re
import shlex
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from lib.db import raw_store
from lib.system import config_mgr, ui, logger_mgr, help_mgr

logger = logger_mgr.get_logger(__name__)

fetch_parser = argparse.ArgumentParser(prog="fetch", add_help=False)
fetch_parser.add_argument("--source", type=str, required=True)
fetch_parser.add_argument("--limit", type=str, default="20")

# [원칙 4] 투명한 User-Agent 설정 (개인 연구 및 수집 봇 명시)
USER_AGENT = "CodysseyNewsBot/1.0 (Personal Research & News Aggregator Project)"
DEFAULT_TIMEOUT_SEC = 10

# [원칙 1] 도메인별 robots.txt 파서 캐시 (중복 다운로드 방지)
_robot_cache = {}

def _is_allowed_by_robots(url, user_agent="*"):
    """대상 URL이 robots.txt 정책에 따라 크롤링이 허용되는지 확인한다."""
    try:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        if domain not in _robot_cache:
            rp = RobotFileParser()
            rp.set_url(f"{domain}/robots.txt")
            try:
                rp.read()
            except Exception:
                # robots.txt가 없거나 접근 불가한 경우 기본 허용(Allow) 처리
                pass
            _robot_cache[domain] = rp
            
        # '*' 또는 특정 봇 이름으로 허용 여부 판정
        return _robot_cache[domain].can_fetch(user_agent, url)
    except Exception:
        # 파싱 중 예외 발생 시 안전하게 허용 처리
        return True


def _now_iso():
    return datetime.now().astimezone().isoformat()

def _resolve_sources(source_name):
    sources = config_mgr.load_config().get("news_sources", [])
    sources = [s for s in sources if s.get("name")]
    if source_name == "all": return sources
    return [s for s in sources if s.get("name") == source_name]

def _create_driver():
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument('--blink-settings=imagesEnabled=false')
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def _extract_article_text(driver, url, timeout):
    """Selenium을 통해 외부 기사 페이지에 접속하여 순수 본문 텍스트를 심층 추출합니다."""
    # [원칙 1] 크롤링 전 robots.txt 준수 여부 엄격 검증
    if not _is_allowed_by_robots(url):
        logger.warning(f"robots.txt 정책에 의해 수집이 차단된 URL입니다: {url}")
        return "", url

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        time.sleep(1.5)
        
        html = driver.page_source
        if "http-equiv=\"refresh\"" in html.lower() or "http-equiv='refresh'" in html.lower():
            soup = BeautifulSoup(html, "html.parser")
            meta_refresh = soup.find("meta", attrs={"http-equiv": lambda x: x and x.lower() == "refresh"})
            if meta_refresh:
                match = re.search(r'url=([^;]+)', meta_refresh.get("content", ""), re.I)
                if match:
                    real_url = match.group(1).strip("'\" ")
                    if not real_url.startswith("http"): real_url = urljoin(url, real_url)
                    
                    # 리다이렉트된 주소도 robots.txt 검증
                    if not _is_allowed_by_robots(real_url):
                        return "", url
                        
                    driver.get(real_url)
                    time.sleep(1.5)
                    html = driver.page_source

        final_url = driver.current_url
        soup = BeautifulSoup(html, "html.parser")
                
        for tag in soup(["script", "style", "header", "footer", "nav", "aside", "form", "iframe"]):
            tag.decompose()
            
        patterns = re.compile(r'(dic_area|newsct_article|article.*view|body.*area|articeBody|articleBody|mw-parser-output|news_txt|content_area|story-content|post-content)', re.I)
        main_content = soup.find(id=patterns) or soup.find(["div", "article", "section"], class_=patterns)
            
        if main_content:
            paragraphs = main_content.find_all("p")
            if paragraphs:
                valid_texts = [p.get_text(separator=" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 10]
                text = " ".join(valid_texts).strip()
                if len(text) > 50: return text, final_url
            text = main_content.get_text(separator=" ", strip=True)
            if len(text) > 50: return text, final_url

        paragraphs = soup.find_all("p")
        valid_texts = [p.get_text(separator=" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        extracted = " ".join(valid_texts).strip()
        
        if len(extracted) > 50: return extracted, final_url
        return "", final_url
    except Exception as e:
        logger.debug(f"본문 추출 실패 ({url}): {e}")
        return "", url

def fetch_via_rss(source, limit=20, timeout=DEFAULT_TIMEOUT_SEC):
    uri = source.get("uri") or source.get("url") or ""
    if not uri: return [], "등록된 URI가 없습니다."

    try:
        resp = requests.get(uri, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        return [], "서버 응답 오류 (네트워크 지연/거부)"

    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries: return [], "RSS 파싱 실패"

    records = []
    driver = None
    count = 1
    
    try:
        for entry in feed.entries:
            if len(records) >= limit: break
            title = entry.get("title", "").strip()
            if not title: continue
            
            link_url = entry.get("link", "")
            raw_summary = entry.get("summary", "")
            clean_summary = BeautifulSoup(raw_summary, "html.parser").get_text(separator=" ", strip=True)
            
            full_content = ""
            final_url = link_url
            
            if link_url:
                if not driver:
                    try: driver = _create_driver()
                    except Exception as e: return records, "Selenium 브라우저 구동 실패"
                
                print(f"    [{count}/{limit}] {title[:30]}... 수집 중", end="", flush=True)
                full_content, resolved_url = _extract_article_text(driver, link_url, timeout)
                if resolved_url: final_url = resolved_url
                print(f"\r    [{count}/{limit}] {title[:30]}... 완료!      ")
                count += 1
                
            final_content = full_content if len(full_content) > len(clean_summary) else clean_summary
            if not final_content: final_content = title

            records.append({
                "source_name": source.get("name", ""),
                "method": "rss",
                "category": source.get("category", "종합"),
                "title": title,
                "content": final_content,
                "url": final_url,
                "published_at": entry.get("published", None),
                "collected_at": _now_iso(),
            })
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass
    return records, None


def fetch_via_api(source, limit=20, timeout=DEFAULT_TIMEOUT_SEC):
    base_uri = source.get("uri") or ""
    if not base_uri: return [], "등록된 URI가 없습니다."

    base_uri = base_uri.rstrip("/")

    try:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        resp = session.get(f"{base_uri}/topstories.json", timeout=timeout)
        resp.raise_for_status()
        story_ids = resp.json()[:limit]
    except Exception as e:
        logger.error(f"[{source.get('name')}] API 스토리 목록 조회 실패: {e}")
        return [], "API 서버 연결 실패"

    records = []
    driver = None
    count = 1
    
    for s_id in story_ids:
        try:
            item_resp = session.get(f"{base_uri}/item/{s_id}.json", timeout=timeout)
            if item_resp.status_code != 200: continue
            item = item_resp.json()
            
            if not item or not item.get("title"): continue

            title = item.get("title").strip()
            print(f"    [{count}/{limit}] {title[:30]}... 수집 중", end="", flush=True)

            external_url = item.get("url")
            raw_text = item.get("text", "")
            
            content = ""
            final_url = external_url

            if external_url:
                if not driver:
                    try: driver = _create_driver()
                    except Exception: pass
                
                if driver:
                    full_content, resolved_url = _extract_article_text(driver, external_url, timeout)
                    if resolved_url: final_url = resolved_url
                    if full_content: content = full_content

            if not content and raw_text:
                content = BeautifulSoup(raw_text, "html.parser").get_text(separator=" ", strip=True)

            if not content: content = title
            if not final_url: final_url = f"https://news.ycombinator.com/item?id={s_id}"

            pub_time = item.get("time")
            pub_date = datetime.fromtimestamp(pub_time, tz=timezone.utc).isoformat() if pub_time else None

            records.append({
                "source_name": source.get("name", ""),
                "method": "api",
                "category": source.get("category", "IT"),
                "title": title,
                "content": content,
                "url": final_url,
                "published_at": pub_date,
                "collected_at": _now_iso(),
            })
            print(f"\r    [{count}/{limit}] {title[:30]}... 완료!      ")
            count += 1
        except Exception as e:
            logger.error(f"해커뉴스 아이템({s_id}) 파싱 오류: {e}")
            continue

    if driver:
        try: driver.quit()
        except Exception: pass

    if not records: return [], "수집된 API 데이터가 없습니다."
    return records, None


_RELATIVE_DATE_RE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")

def _parse_relative_date(text):
    m = _RELATIVE_DATE_RE.search(text)
    if not m: return None
    month, day = int(m.group(1)), int(m.group(2))
    local_now = datetime.now().astimezone()
    try: return local_now.replace(month=month, day=day, hour=0, minute=0, second=0, microsecond=0).isoformat()
    except ValueError: return None

def fetch_via_crawl(source, limit=20, timeout=DEFAULT_TIMEOUT_SEC):
    uri = source.get("uri") or source.get("url") or ""
    if not uri: return [], "등록된 URI가 없습니다."

    driver = None
    try:
        try: driver = _create_driver()
        except Exception: return [], "Selenium 브라우저 구동 실패"
        try:
            driver.set_page_load_timeout(timeout)
            driver.get(uri)
            WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            html = driver.page_source
        except Exception: return [], "메인 페이지 연결 실패"

        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=True)
        records = []
        seen_urls = set()
        count = 1
        
        for a in links:
            if len(records) >= limit: break
            title = a.get_text(strip=True)
            if len(title) < 15: continue
            raw_href = a['href']
            if raw_href.startswith("javascript") or raw_href.startswith("#"): continue
            
            link_url = urljoin(uri, raw_href)
            if link_url in seen_urls: continue
            seen_urls.add(link_url)
            
            print(f"    [{count}/{limit}] {title[:30]}... 수집 중", end="", flush=True)
            full_content, resolved_url = _extract_article_text(driver, link_url, timeout)
            print(f"\r    [{count}/{limit}] {title[:30]}... 완료!      ")
            count += 1
            
            records.append({
                "source_name": source.get("name", ""),
                "method": "crawl",
                "category": source.get("category", "종합"),
                "title": title,
                "content": full_content,
                "url": resolved_url if resolved_url else link_url,
                "published_at": _parse_relative_date(title),
                "collected_at": _now_iso(),
            })
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass
    return records, None

FETCH_HANDLERS = {
    "rss": fetch_via_rss,
    "crawl": fetch_via_crawl,
    "api": fetch_via_api
}

def execute_fetch_logic(source, limit, is_cli=False):
    print()
    ui.draw_line("━")
    mode_text = "[CLI 모드]" if is_cli else "[대화형 모드]"
    logger.info(f"뉴스 수집 파이프라인 시작 (소스: {source}, 최대 제한: {limit}건, 모드: {mode_text})")
    
    print(f"{ui.HL}>> {mode_text} 뉴스 데이터 수집을 시작합니다...{ui.FG}")
    print(f"   (적용 옵션: source={source}, limit={limit})\n   💡 안내: robots.txt 정책 검증 및 본문 심층 추출을 진행합니다.")

    targets = _resolve_sources(source)
    if not targets:
        print(f"{ui.ERR}'{source}' 이름의 등록된 소스를 찾을 수 없습니다.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    try:
        limit_int = int(limit)
        if limit_int <= 0: raise ValueError
    except (TypeError, ValueError):
        print(f"{ui.ERR}[오류] 올바른 수집 제한 건수(양의 정수)가 아니므로 기본값 20건을 적용합니다.{ui.FG}")
        limit_int = 20

    timeout = config_mgr.load_config().get("fetch", {}).get("timeout_sec", DEFAULT_TIMEOUT_SEC)
    total, total_fail = 0, 0
    
    for src in targets:
        method = src.get("method", "rss")
        handler = FETCH_HANDLERS.get(method)
        if handler is None: continue

        print(f"  [수집 진행] {src.get('name')} ({method.upper()}) 데이터 요청 중...")
        try: records, error = handler(src, limit=limit_int, timeout=timeout)
        except Exception as e:
            error = f"수집 모듈 내부 시스템 오류 발생: {e}"
            records = []

        if error:
            print(f"  {ui.ERR}[실패] {src.get('name')}: {error}{ui.FG}\n")
            total_fail += 1
            continue

        for r in records: raw_store.append(src.get("name", ""), r)
        print(f"  └─ [{src.get('name')}] {len(records)}건 수집 및 적재 완료\n")
        total += len(records)

    ui.draw_line("─")
    print(f"{ui.HL}>> 수집 작업이 완료되었습니다! (총 {total}건 추출, 실패 {total_fail}건){ui.FG}")
    ui.draw_line("━")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")

def run_menu_show():
    while True:
        ui.clear_screen()
        ui.draw_header(" 뉴스 데이터 수집 (Fetch) 제어소 ")
        config = config_mgr.load_config()
        sources = config.get("news_sources", [])
        
        ui.draw_line("─")
        print(f"{ui.HL}  [ 현재 등록된 뉴스 피드 현황 ]{ui.FG}")
        if not sources: print("  (등록된 뉴스 소스가 없습니다. 환경 설정 메뉴에서 먼저 등록해주세요.)")
        else:
            for idx, s in enumerate(sources, 1):
                name, method, uri, category, status = s.get("name", "이름없음"), (s.get("method") or "rss").upper(), s.get("uri") or s.get("url") or "URI 없음", s.get("category", "종합"), "활성" if s.get("enabled", True) else "비활성"
                print(f"  {idx}. {ui.HL}{name}{ui.FG}\n     ├─ [방식] {ui.HL}{method:<5}{ui.FG} │  [카테고리] {category:<6} │  [상태] {status}\n     └─ [URI ] {uri}")
        ui.draw_line("─")
        print(f"\n{ui.HL}  [ 대화형 메뉴 ]{ui.FG}\n  1. 뉴스 수집 실행\n  2. 수집 현황 확인\n")
        print(f"{ui.HL}  [ CLI 입력 (H : 도움말) ]{ui.FG} fetch --source [소스명|all] [--limit 20]\n")
        print(f"  {ui.FG}💡 번호 선택 또는 CLI 명령어 입력  |  {ui.HL}P{ui.FG} : 상위 메뉴")
        ui.draw_line("─")

        user_input = input(f"{ui.HL} Codyssey/fetch > {ui.FG}").strip()
        
        if not user_input: continue
        if user_input.lower() == 'p': break
        elif user_input.lower() == 'h': help_mgr.show_help("fetch")
        elif user_input == '1': run_fetch_interactive()
        elif user_input == '2': show_data_status()
        elif user_input.startswith("fetch"): run_fetch_cli(user_input)
        else:
            print(f"\n{ui.ERR}올바르지 않은 명령어나 번호입니다.{ui.FG}")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")

def run_fetch_cli(command_str):
    try:
        args_list = shlex.split(command_str)
        args, unknown = fetch_parser.parse_known_args(args_list[1:])
        if unknown: return
        execute_fetch_logic(args.source, args.limit, is_cli=True)
    except SystemExit: pass
    except Exception: pass

def run_fetch_interactive():
    config = config_mgr.load_config()
    sources = config.get("news_sources", [])
    if not sources: return
    selected_source = None
    while True:
        ui.clear_screen()
        ui.draw_header(" 대화형 뉴스 수집 설정 ")
        print(f"{ui.HL}  [ 수집할 뉴스 소스 선택 ]{ui.FG}\n  0) 전체 수집 (all)")
        source_map = {"0": "all"}
        for idx, s in enumerate(sources, 1):
            name = s.get("name", f"source_{idx}")
            print(f"  {idx}) {name} (방식: {(s.get('method') or 'rss').upper()} / 카테고리: {s.get('category', '종합')})")
            source_map[str(idx)] = name
        print("\n C) 취소\n")
        ui.draw_line("─")
        sel = input(f"{ui.FG}▶ 번호 선택 [C: 취소] > {ui.HL}").strip()
        if sel.lower() in ['c']: return
        if sel in source_map:
            selected_source = source_map[sel]
            break
            
    limit_val = "20"
    while True:
        ui.draw_line("─")
        limit_input = input(f"{ui.FG}▶ 제한 건수 [기본 20] [C: 취소] > {ui.HL}").strip()
        if limit_input.lower() in ['c']: return
        if not limit_input: break
        if limit_input.isdigit() and int(limit_input) > 0:
            limit_val = limit_input
            break

    execute_fetch_logic(selected_source, limit_val, is_cli=False)

def show_data_status():
    ui.clear_screen()
    ui.draw_header(" 수집 데이터 현황 ")
    sources = raw_store.list_sources()
    if not sources: print("\n  데이터가 없습니다.")
    else:
        total, latest = 0, None
        print()
        for name in sources:
            records = raw_store.read_all(name)
            total += len(records)
            for r in records:
                if r.get("collected_at") and (latest is None or r.get("collected_at") > latest):
                    latest = r.get("collected_at")
            print(f"  • {name}.jsonl  : {len(records)}건")
        ui.draw_line("─")
        print(f"  * 총합 : {total}건\n  * 최근 : {latest or '알 수 없음'}")
    ui.draw_line("━")
    ui.pause("\n[Enter]를 눌러 서브메뉴로 돌아갑니다...")