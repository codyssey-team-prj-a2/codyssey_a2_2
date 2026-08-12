# lib/dev/setup.py
from pathlib import Path
from lib.system import config_mgr, ui

DEFAULT_MODELS = {
    "gemini": "gemini-1.5-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20240620"
}

PROVIDER_LABELS = {
    "gemini": "Gemini (Google)",
    "openai": "GPT (OpenAI)",
    "anthropic": "Claude (Anthropic)"
}

METHOD_LABELS = {"rss": "RSS", "api": "API", "crawl": "크롤링"}


def _prompt(msg, current_val=None, allow_enter_keep=True):
    """공통 프롬프트 (readline 겹침 방지 ui.rl_color 적용)"""
    hints = ["C: 취소"]
    if allow_enter_keep and current_val is not None and current_val != "":
        hints.append("Enter: 현재 설정 유지")
    elif allow_enter_keep:
        hints.append("Enter: 기본값 적용")
        
    hint_str = f" [{ ' | '.join(hints) }]"
    
    ui.draw_line("─")
    # ui.rl_color를 적용하여 입력 중 글자 겹침 버그 방지
    prompt_str = f"{ui.rl_color(ui.FG)}{msg}{ui.rl_color(ui.HL)}{hint_str} > {ui.rl_color(ui.FG)}"
    val = input(prompt_str).strip()
    
    if val.lower() == 'c':
        print(f"\n{ui.HL}>> 작업을 취소했습니다.{ui.FG}")
        return None
    if val == '' and allow_enter_keep:
        return current_val
    return val


def run_menu_show():
    """TUI 환경 설정 메인 메뉴 루프 (실제 데이터 기반 상태 체크)"""
    while True:
        ui.clear_screen()
        cfg = config_mgr.load_config()
        
        # [수정] 플래그가 아닌 실제 데이터 검증 결과 사용
        status_map = config_mgr.get_setup_status()
        
        ui.draw_header("시스템 환경 설정 메뉴")
        
        ai_st = "완료" if status_map["setup_ai"] else "미완료"
        news_cnt = len(cfg.get("news_sources", []))
        news_st = f"완료 ({news_cnt}개)" if status_map["setup_news"] else "미완료"
        log_st = "완료" if status_map["setup_log"] else "미완료"

        print(f"  1. AI 환경 설정 (플랫폼/모델/Key) [{ai_st}]")
        print(f"  2. 뉴스 소스 관리 (목록/추가/수정/삭제) [{news_st}]")
        print(f"  3. DB 저장 폴더 경로 설정")
        print(f"  4. 로그 폴더 경로/수준 설정     [{log_st}]")
        print("\n  p. 메인 화면으로 돌아가기\n")
        
        choice = _prompt("설정할 번호를 선택하세요", allow_enter_keep=False)
        if choice is None or choice.lower() == 'p': 
            break
            
        if choice == '1':
            _set_api_key(cfg)
        elif choice == '2':
            _manage_news_sources(cfg)
        elif choice == '3':
            _set_db_path(cfg)
        elif choice == '4':
            _set_log_config(cfg)


def _set_api_key(cfg):
    """AI 환경 설정 메인 현황 조회"""
    while True:
        ui.clear_screen()
        ui.draw_header(" AI 환경 설정 ")
        
        curr_prov = config_mgr.get_env("LLM_PROVIDER") or ""
        curr_model = config_mgr.get_env("LLM_MODEL") or ""
        curr_key = config_mgr.get_env("LLM_API_KEY") or ""
        
        # 실제 데이터 유효성 판단
        has_existing = config_mgr.is_ai_setup_complete()
        
        ui.draw_line("─")
        print(f"{ui.HL}  [ 현재 AI 환경 설정 내용 ]{ui.FG}")
        masked_key = (curr_key[:4] + "*" * max(len(curr_key) - 4, 0)) if curr_key else "미설정"
        prov_label = PROVIDER_LABELS.get(curr_prov, curr_prov if curr_prov else "미설정")
        print(f"  • AI 플랫폼 : {prov_label}")
        print(f"  • 사용 모델 : {curr_model or '미설정'}")
        print(f"  • API Key   : {masked_key}")
        ui.draw_line("─")
        print()
        
        if has_existing:
            print("  1. AI 환경 설정 변경")
            print("  p. 상위 메뉴로 이동\n")
            ui.draw_line("─")
            prompt_str = f"{ui.rl_color(ui.HL)}입력 (1: 설정 변경 / p: 상위 메뉴로) > {ui.rl_color(ui.FG)}"
            cmd = input(prompt_str).strip().lower()
            
            if cmd == 'p':
                break
            elif cmd == '1':
                _edit_api_key_wizard(cfg, curr_prov, curr_model, curr_key)
            else:
                print(f"\n{ui.ERR}[오류] 올바른 번호(1) 또는 'p'를 입력해 주세요.{ui.FG}")
                ui.pause("다시 시도하려면 [Enter]를 누르세요...")
        else:
            print("  1. AI 환경 신규 설정")
            print("  p. 상위 메뉴로 이동\n")
            ui.draw_line("─")
            prompt_str = f"{ui.rl_color(ui.HL)}입력 (1: 신규 설정 진행 / p: 상위 메뉴로) > {ui.rl_color(ui.FG)}"
            cmd = input(prompt_str).strip().lower()
            
            if cmd == 'p':
                break
            elif cmd in ['1', '']:
                _edit_api_key_wizard(cfg, "", "", "")
            else:
                print(f"\n{ui.ERR}[오류] 올바른 번호(1) 또는 'p'를 입력해 주세요.{ui.FG}")
                ui.pause("다시 시도하려면 [Enter]를 누르세요...")


def _edit_api_key_wizard(cfg, curr_prov, curr_model, curr_key):
    """AI 설정 변경 절차"""
    ui.clear_screen()
    ui.draw_header(" AI 환경 설정 변경 ")
    
    prov_label = PROVIDER_LABELS.get(curr_prov, "")
    print(f"{ui.HL}  [ AI 플랫폼 선택 ]{ui.FG}")
    print("  1) Gemini (Google)")
    print("  2) GPT (OpenAI)")
    print("  3) Claude (Anthropic)\n")
    
    print(f"{ui.FG}▶ 사용할 AI 플랫폼 번호를 선택하세요.")
    ui.draw_line("─")
    
    if curr_prov:
        hint_str = f"[p: 상위 메뉴로 | C: 취소 | Enter: 현재 설정 유지 ({prov_label})]"
    else:
        hint_str = "[p: 상위 메뉴로 | C: 취소]"
        
    prompt_str = f"{ui.rl_color(ui.HL)}{hint_str} > {ui.rl_color(ui.FG)}"
    prov_choice = input(prompt_str).strip()
    
    if prov_choice.lower() in ['p', 'c']:
        print(f"\n{ui.HL}>> 변경 작업을 취소했습니다.{ui.FG}")
        ui.pause("[Enter]를 누르세요...")
        return
        
    if not prov_choice:
        if curr_prov:
            provider = curr_prov
        else:
            print(f"\n{ui.ERR}[오류] 설정된 플랫폼이 없으므로 번호를 반드시 선택해야 합니다.{ui.FG}")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")
            return
    else:
        provider_map = {"1": "gemini", "2": "openai", "3": "anthropic"}
        if prov_choice not in provider_map:
            print(f"\n{ui.ERR}[오류] 잘못된 선택입니다. 1~3 번호 중에서 선택해 주세요.{ui.FG}")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")
            return
        provider = provider_map[prov_choice]

    # 모델명 입력
    print()
    if curr_model and provider == curr_prov:
        print(f"{ui.FG}▶ 사용할 모델명을 입력하세요.")
        ui.draw_line("─")
        prompt_str = f"{ui.rl_color(ui.HL)}[p: 상위 메뉴로 | C: 취소 | Enter: 현재 설정 유지 ({curr_model})] > {ui.rl_color(ui.FG)}"
        model_input = input(prompt_str).strip()
        
        if model_input.lower() in ['p', 'c']:
            print(f"\n{ui.HL}>> 변경 작업을 취소했습니다.{ui.FG}")
            ui.pause("[Enter]를 누르세요...")
            return
        model = curr_model if not model_input else model_input
    else:
        default_m = DEFAULT_MODELS.get(provider, "gemini-1.5-flash")
        print(f"{ui.FG}▶ 사용할 모델명을 입력하세요 (추천: {default_m}).")
        ui.draw_line("─")
        prompt_str = f"{ui.rl_color(ui.HL)}[p: 상위 메뉴로 | C: 취소 | Enter: 추천 모델 ({default_m}) 적용] > {ui.rl_color(ui.FG)}"
        model_input = input(prompt_str).strip()
        
        if model_input.lower() in ['p', 'c']:
            print(f"\n{ui.HL}>> 변경 작업을 취소했습니다.{ui.FG}")
            ui.pause("[Enter]를 누르세요...")
            return
        model = default_m if not model_input else model_input

    # API Key 입력
    print()
    print(f"{ui.FG}▶ API Key를 입력하세요 (마스킹되어 저장됩니다).")
    ui.draw_line("─")
    if curr_key:
        prompt_str = f"{ui.rl_color(ui.HL)}[p: 상위 메뉴로 | C: 취소 | Enter: 현재 설정 유지] > {ui.rl_color(ui.FG)}"
        key_input = input(prompt_str).strip()
        if key_input.lower() in ['p', 'c']:
            print(f"\n{ui.HL}>> 변경 작업을 취소했습니다.{ui.FG}")
            ui.pause("[Enter]를 누르세요...")
            return
        key = curr_key if not key_input else key_input
    else:
        prompt_str = f"{ui.rl_color(ui.HL)}[p: 상위 메뉴로 | C: 취소] > {ui.rl_color(ui.FG)}"
        key_input = input(prompt_str).strip()
        if key_input.lower() in ['p', 'c']:
            print(f"\n{ui.HL}>> 변경 작업을 취소했습니다.{ui.FG}")
            ui.pause("[Enter]를 누르세요...")
            return
        if not key_input:
            print(f"\n{ui.ERR}[오류] API Key는 필수 입력 항목입니다. 비워둘 수 없습니다.{ui.FG}")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")
            return
        key = key_input

    # 변경사항 저장
    config_mgr.set_env("LLM_PROVIDER", provider)
    config_mgr.set_env("LLM_MODEL", model)
    config_mgr.set_env("LLM_API_KEY", key)
    
    # 동적 검증으로 대체되었으므로 보조 플래그만 기록
    cfg["setup_ai"] = True
    config_mgr.save_config(cfg)
    
    print(f"\n{ui.HL}>> AI 환경 설정이 성공적으로 저장되었습니다!{ui.FG}")
    ui.pause("[Enter]를 누르면 AI 환경 설정 현황으로 돌아갑니다...")


def _manage_news_sources(cfg):
    while True:
        ui.clear_screen()
        ui.draw_header("뉴스 소스 관리")
        sources = cfg.setdefault("news_sources", [])
        
        ui.draw_line("─")
        print(f"{ui.HL}  [ 현재 등록된 뉴스 소스 목록 ]{ui.FG}")
        if not sources:
            print("  (등록된 뉴스 소스가 없습니다. 신규 추가를 진행해주세요.)")
        else:
            for idx, s in enumerate(sources, 1):
                m_label = METHOD_LABELS.get(s.get("method"), s.get("method", "RSS"))
                status = "활성" if s.get("enabled", True) else "비활성"
                uri_val = s.get("uri") or s.get("url") or "URI 없음"
                print(f"  {idx}. {ui.HL}{s.get('name', '이름없음')}{ui.FG}")
                print(f"     ├─ [방식] {m_label} │ [카테고리] {s.get('category', '종합')} │ [상태] {status}")
                print(f"     └─ [URI ] {uri_val}")
        ui.draw_line("─")
        print()
        
        print("  1. 신규 뉴스 소스 추가")
        print("  2. 기존 뉴스 소스 수정")
        print("  3. 기존 뉴스 소스 삭제")
        print("  p. 메인 설정 메뉴로 돌아가기\n")
        
        choice = _prompt("작업할 번호를 선택하세요", allow_enter_keep=False)
        if choice is None or choice.lower() == 'p':
            break
            
        if choice == '1':
            _add_source_action(cfg)
        elif choice == '2':
            _edit_source_action(cfg)
        elif choice == '3':
            _delete_source_action(cfg)


def _add_source_action(cfg):
    print("\n[ 신규 뉴스 소스 추가 ]")
    sources = cfg.get("news_sources", [])
    
    name = _prompt("소스 이름 입력 (예: naver_it_rss)")
    if not name: return
    
    if any(s.get("name") == name for s in sources):
        print(f"\n{ui.ERR}이미 등록된 소스 이름입니다: {name}{ui.FG}")
        ui.pause("[Enter]를 누르세요...")
        return
        
    print("\n  [ 수집 방식 선택 ] 1) RSS  2) API  3) 크롤링")
    m_choice = _prompt("번호 선택 (1-3)", "1")
    if m_choice is None: return
    
    method_map = {"1": "rss", "2": "api", "3": "crawl"}
    method = method_map.get(m_choice, "rss")
    
    uri = _prompt("주소 (URI) 입력")
    if not uri: return
    
    category = _prompt("카테고리 입력", "종합")
    if category is None: return
    
    sources.append({
        "name": name,
        "method": method,
        "uri": uri,
        "url": uri,
        "category": category,
        "enabled": True
    })
    cfg["setup_news"] = True
    config_mgr.save_config(cfg)
    print(f"\n{ui.HL}>> 뉴스 소스 [{name}]이(가) 추가되었습니다!{ui.FG}")
    ui.pause("[Enter]를 누르세요...")


def _edit_source_action(cfg):
    sources = cfg.get("news_sources", [])
    if not sources:
        print("\n수정할 뉴스 소스가 없습니다.")
        ui.pause("[Enter]를 누르세요...")
        return
        
    print("\n[ 뉴스 소스 수정 ]")
    idx_str = _prompt(f"수정할 소스 번호를 선택하세요 (1~{len(sources)})")
    if not idx_str: return
    
    try:
        idx = int(idx_str) - 1
        if not (0 <= idx < len(sources)):
            print("\n유효하지 않은 번호입니다.")
            ui.pause("[Enter]를 누르세요...")
            return
    except ValueError:
        print("\n숫자를 입력해 주세요.")
        ui.pause("[Enter]를 누르세요...")
        return
        
    target = sources[idx]
    print(f"\n선택된 소스: {target.get('name', '이름없음')}")
    
    new_name = _prompt("새 소스 이름", target.get('name', ''))
    if new_name is None: return
    
    print("\n  [ 수집 방식 선택 ] 1) RSS  2) API  3) 크롤링")
    curr_m_num = {"rss": "1", "api": "2", "crawl": "3"}.get(target.get('method'), "1")
    m_choice = _prompt("번호 선택 (1-3)", curr_m_num)
    if m_choice is None: return
    
    method = {"1": "rss", "2": "api", "3": "crawl"}.get(m_choice, target.get('method', 'rss'))
    
    curr_uri = target.get('uri') or target.get('url') or ''
    new_uri = _prompt("새 주소 (URI)", curr_uri)
    if new_uri is None: return
    
    new_cat = _prompt("새 카테고리", target.get('category', '종합'))
    if new_cat is None: return
    
    target.update({
        "name": new_name,
        "method": method,
        "uri": new_uri,
        "url": new_uri,
        "category": new_cat
    })
    config_mgr.save_config(cfg)
    print(f"\n{ui.HL}>> 소스 [{new_name}] 수정이 완료되었습니다!{ui.FG}")
    ui.pause("[Enter]를 누르세요...")


def _delete_source_action(cfg):
    sources = cfg.get("news_sources", [])
    if not sources:
        print("\n삭제할 뉴스 소스가 없습니다.")
        ui.pause("[Enter]를 누르세요...")
        return
        
    print("\n[ 뉴스 소스 삭제 ]")
    idx_str = _prompt(f"삭제할 소스 번호를 선택하세요 (1~{len(sources)})")
    if not idx_str: return
    
    try:
        idx = int(idx_str) - 1
        if 0 <= idx < len(sources):
            removed_name = sources[idx].get("name", "소스")
            del sources[idx]
            if not sources:
                cfg["setup_news"] = False
            config_mgr.save_config(cfg)
            print(f"\n{ui.HL}>> 소스 [{removed_name}]이(가) 삭제되었습니다!{ui.FG}")
        else:
            print("\n유효하지 않은 번호입니다.")
    except ValueError:
        print("\n숫자를 입력해 주세요.")
        
    ui.pause("[Enter]를 누르세요...")


def _set_db_path(cfg):
    ui.clear_screen()
    ui.draw_header("DB 저장 폴더 경로 설정")
    
    storage = cfg.setdefault("storage", {})
    curr_path = storage.get("db_path", "src/data/news_pipeline.db")
    
    ui.draw_line("─")
    print(f"{ui.HL}  [ 현재 DB 저장 경로 설정 내용 ]{ui.FG}")
    print(f"  • 현재 DB 경로 : {curr_path}")
    print(f"  • 안내 : DB 파일명(news_pipeline.db)은 고정되며 폴더 위치만 설정합니다.")
    ui.draw_line("─")
    print("\n  예시) 'data' 또는 'src/data' 입력 시 -> src/data/news_pipeline.db 로 지정됩니다.")
    
    new_dir = _prompt("새로운 DB 저장 폴더 입력", str(Path(curr_path).parent))
    if new_dir is None: return
    
    p = Path(new_dir.strip())
    if not str(p).startswith("src"):
        p = Path("src") / p
        
    final_db_path = str(p / "news_pipeline.db")
    storage["db_path"] = final_db_path
    config_mgr.save_config(cfg)
    
    print(f"\n{ui.HL}>> DB 저장 경로가 [{final_db_path}]로 설정되었습니다!{ui.FG}")
    ui.pause("[Enter]를 누르세요...")


def _set_log_config(cfg):
    ui.clear_screen()
    ui.draw_header("로그 폴더 경로 및 수준 설정")
    
    logging_cfg = cfg.setdefault("logging", {})
    curr_file = logging_cfg.get("file", "src/logs/app.log")
    curr_level = logging_cfg.get("level", "INFO")
    
    ui.draw_line("─")
    print(f"{ui.HL}  [ 현재 로그 설정 내용 ]{ui.FG}")
    print(f"  • 현재 로그 파일 경로 : {curr_file}")
    print(f"  • 현재 기록 로그 수준 : {curr_level}")
    print(f"  • 안내 : 로그 파일명(app.log)은 고정되며 폴더 위치만 설정합니다.")
    ui.draw_line("─")
    print("\n  예시) 'logs' 또는 'src/logs' 입력 시 -> src/logs/app.log 로 지정됩니다.")
    
    new_dir = _prompt("새로운 로그 폴더 입력", str(Path(curr_file).parent))
    if new_dir is None: return
    
    p = Path(new_dir.strip())
    if not str(p).startswith("src"):
        p = Path("src") / p
    final_log_file = str(p / "app.log")
    
    print("\n  [ 기록할 로그 수준 선택 ]")
    print("  1) DEBUG   : 세부 개발 및 분석 데이터 포함 모든 정보 기록")
    print("  2) INFO    : 일반적인 실행 흐름 기록 (권장)")
    print("  3) WARNING : 당장 멈추지는 않는 주의 사항 기록")
    print("  4) ERROR   : 에러 발생 시에만 기록")
    
    curr_level_num = {"DEBUG": "1", "INFO": "2", "WARNING": "3", "ERROR": "4"}.get(curr_level, "2")
    level_choice = _prompt("로그 수준 선택 (1-4)", curr_level_num)
    if level_choice is None: return
    
    level_map = {"1": "DEBUG", "2": "INFO", "3": "WARNING", "4": "ERROR"}
    selected_level = level_map.get(level_choice, curr_level)
    
    logging_cfg["file"] = final_log_file
    logging_cfg["level"] = selected_level
    cfg["setup_log"] = True
    config_mgr.save_config(cfg)
    
    print(f"\n{ui.HL}>> 로그 경로 [{final_log_file}], 수준 [{selected_level}]로 저장되었습니다!{ui.FG}")
    ui.pause("[Enter]를 누르세요...")