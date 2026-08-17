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

# newspaper3k 라이브러리 임포트
try:
    from newspaper import Article, Config
except ImportError:
    Article = None
    Config = None

logger = logger_mgr.get_logger(__name__)

fetch_parser = argparse.ArgumentParser(prog="fetch", add_help=False)
fetch_parser.add_argument("--source", type=str, required=True)
fetch_parser.add_argument("--limit", type=str, default="20")

# =====================================================================
# [중요 설정] 로봇 배제 표준(robots.txt) 무시 여부 (기본값: True)
# True로 설정 시, 모든 사이트의 robots.txt를 무시하고 본문 수집을 강행합니다.
# 윤리적 수집을 원할 경우 False로 변경하세요.
# =====================================================================
IGNORE_ROBOTS_TXT = True

# 대중적인 브라우저처럼 보이도록 User-Agent 설정
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 CodysseyNewsBot/1.0"
DEFAULT_TIMEOUT_SEC = 10
_robot_cache = {}


def _is_allowed_by_robots(url, user_agent=USER_AGENT):
    """대상 URL이 robots.txt 정책에 따라 크롤링이 허용되는지 확인한다."""
    # 상수 설정에 따라 로봇 확인 패스
    if IGNORE_ROBOTS_TXT:
        return True
        
    try:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        if domain not in _robot_cache:
            rp = RobotFileParser()
            rp.set_url(f"{domain}/robots.txt")
            try:
                resp = requests.get(f"{domain}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=5)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
            except Exception:
                pass
            _robot_cache[domain] = rp
            
        return _robot_cache[domain].can_fetch(user_agent, url)
    except Exception:
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


def _resolve_google_news_url(driver, url, timeout=10):
    """
    [핵심] 구글 뉴스 RSS의 'inject.js' 다단계 리다이렉트를 대기하거나 강제로 뚫어
    최종 언론사 주소로 넘어갈 때까지 추적합니다.
    """
    if "news.google.com" not in url:
        return url
        
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        
        # 1. 자연스러운 리다이렉트 대기 (inject.js 실행 대기)
        start_time = time.time()
        while time.time() - start_time < timeout:
            current = driver.current_url
            if "news.google.com" not in current:
                time.sleep(1.0) # 페이지 렌더링 대기
                return driver.current_url
            time.sleep(0.5)
            
        # 2. 타임아웃까지 리다이렉트가 안 됐다면, 화면의 HTML을 뒤져 강제로 넘깁니다.
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 2-1) 메타 리프레시 확인
        meta = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
        if meta:
            content = meta.get('content', '')
            match = re.search(r'url=([^;]+)', content, re.I)
            if match:
                real_url = match.group(1).strip("'\" ")
                if not real_url.startswith('http'):
                    real_url = urljoin(driver.current_url, real_url)
                driver.get(real_url)
                time.sleep(2.0)
                return driver.current_url
                
        # 2-2) 외부로 나가는 a 태그 강제 클릭
        a_tag = soup.find("a", href=re.compile(r"^https?://(?!news\.google\.com)"))
        if a_tag and a_tag.get("href"):
            driver.get(a_tag["href"])
            time.sleep(2.0)
            return driver.current_url
            
        return driver.current_url
    except Exception as e:
        logger.debug(f"구글 뉴스 강제 리다이렉트 추적 실패: {e}")
        return getattr(driver, "current_url", url)


def _extract_article_text(driver, url, timeout):
    """위키피디아 및 API 크롤링용 Selenium + BeautifulSoup 추출 로직"""
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
    uri = source.get("uri")
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
            
            google_url = entry.get("link", "")
            raw_summary = entry.get("summary", "")
            clean_summary = BeautifulSoup(raw_summary, "html.parser").get_text(separator=" ", strip=True)
            
            full_content = ""
            final_url = google_url
            fetch_status = "미시도"
            
            if google_url:
                if not driver:
                    try: driver = _create_driver()
                    except Exception: pass
                
                print(f"    [{count}/{limit}] {title[:30]}... 수집 중", end="", flush=True)
                
                # 1. Selenium을 이용해 구글 뉴스 강제 리다이렉트 추적
                if driver:
                    final_url = _resolve_google_news_url(driver, google_url, timeout)
                
                # 2. 로봇 정책 검사
                if not _is_allowed_by_robots(final_url):
                    fetch_status = "실패: robots.txt 차단"
                else:
                    # 3. newspaper3k 활용 본문 추출
                    if Article:
                        try:
                            config = Config()
                            config.browser_user_agent = USER_AGENT
                            config.request_timeout = timeout
                            config.fetch_images = False
                            
                            article = Article(final_url, config=config, language='ko')
                            if driver and driver.current_url == final_url:
                                article.set_html(driver.page_source)
                            else:
                                article.download()
                                
                            article.parse()
                            full_content = article.text.strip()
                            
                            if len(full_content) > 50:
                                fetch_status = "성공 (newspaper3k)"
                        except Exception as e:
                            pass
                            
                    # 4. newspaper3k 실패 시 기존 BS4 로직으로 Fallback
                    if not full_content and driver and driver.current_url == final_url:
                        soup = BeautifulSoup(driver.page_source, 'html.parser')
                        paragraphs = soup.find_all('p')
                        full_content = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                        if len(full_content) > 50:
                            fetch_status = "성공 (BS4 Fallback)"
                        else:
                            fetch_status = "실패: 본문 길이 부족"
                            
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
                "url": google_url,
                "final_url": final_url,
                "fetch_status": fetch_status,
                "published_at": entry.get("published", None),
                "collected_at": _now_iso(),
            })
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass
    return records, None


def fetch_via_api(source, limit=20, timeout=DEFAULT_TIMEOUT_SEC):
    base_uri = source.get("uri")
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
            fetch_status = "미시도"

            if external_url:
                if not driver:
                    try: driver = _create_driver()
                    except Exception: pass
                
                if driver:
                    full_content, resolved_url = _extract_article_text(driver, external_url, timeout)
                    if resolved_url: final_url = resolved_url
                    if full_content: 
                        content = full_content
                        fetch_status = "성공"
                    else:
                        fetch_status = "실패: 내용 부족 또는 차단"

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
                "url": external_url if external_url else final_url,
                "final_url": final_url,
                "fetch_status": fetch_status,
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
    uri = source.get("uri")
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
            fetch_status = "성공" if full_content else "실패"
            
            print(f"\r    [{count}/{limit}] {title[:30]}... 완료!      ")
            count += 1
            
            records.append({
                "source_name": source.get("name", ""),
                "method": "crawl",
                "category": source.get("category", "종합"),
                "title": title,
                "content": full_content,
                "url": link_url,
                "final_url": resolved_url if resolved_url else link_url,
                "fetch_status": fetch_status,
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
                name, method, uri, category, status = s.get("name", "이름없음"), (s.get("method") or "rss").upper(), s.get("uri", "URI 없음"), s.get("category", "종합"), "활성" if s.get("enabled", True) else "비활성"
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