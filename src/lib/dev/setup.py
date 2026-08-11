# lib/dev/setup.py
from lib.system import config_mgr, ui

def run_menu_show():
    """환경 설정 서브메뉴 메인 루프"""
    while True:
        ui.clear_screen()
        cfg = config_mgr.load_config()
        ui.draw_header("시스템 환경 설정 메뉴")
        
        ai_st = "완료" if cfg.get("setup_ai") else "미완료"
        news_st = "완료" if cfg.get("setup_news") else "미완료"
        log_st = "완료" if cfg.get("setup_log") else "미완료"

        print(f"  1. AI 환경 설정      [{ai_st}]")
        print(f"  2. News Feed 설정    [{news_st}]")
        print(f"  3. Log 수준 설정     [{log_st}]")
        print("\n  P. 메인 화면으로 돌아가기\n")
        
        ui.draw_line("─")
        choice = input(f"{ui.HL}설정할 번호를 선택하세요 > {ui.FG}").strip().lower()
        if choice == 'p': 
            break
            
        if choice == '1':
            _setup_ai(cfg)
        elif choice == '2':
            _setup_news(cfg)
        elif choice == '3':
            _setup_log(cfg)

def _setup_ai(cfg):
    """AI 플랫폼 및 API Key 설정"""
    print("\n[ AI 설정 ]")
    curr_prov = config_mgr.get_env("LLM_PROVIDER") or "없음"
    curr_model = config_mgr.get_env("LLM_MODEL") or "없음"
    curr_key = config_mgr.get_env("LLM_API_KEY") or "없음"
    
    print(f"  * 현재 플랫폼: {curr_prov}")
    print(f"  * 현재 모델명: {curr_model}")
    print(f"  * 현재 API Key: {curr_key[:5]}...{curr_key[-3:] if curr_key != '없음' else ''}\n")
    
    print("  [플랫폼 선택]")
    print("  1) Gemini (Google)")
    print("  2) GPT (OpenAI)")
    print("  3) Claude (Anthropic)")
    prov_choice = ui.safe_input("번호 선택 (1-3) [변경 안 함: C ]: ")
    if prov_choice.lower() == "c": return
    
    provider_map = {"1": "gemini", "2": "openai", "3": "anthropic"}
    provider = provider_map.get(prov_choice, curr_prov if curr_prov != "없음" else None)
    
    if not provider:
        print("유효한 플랫폼이 선택되지 않았습니다.")
        input("[Enter]를 눌러 다시 시도하세요...")
        return
    
    model = ui.safe_input(f"모델명 입력 (예: gemini-1.5-flash) [현재: {curr_model}]: ")
    if model is None: return
    model = model if model else curr_model
    
    key = ui.safe_input("API Key 입력 (화면에 표시됨) [변경 안 함: C ]: ")
    if key.lower() == "c": return
    key = key if key else curr_key
    
    config_mgr.set_env("LLM_PROVIDER", provider)
    config_mgr.set_env("LLM_MODEL", model)
    config_mgr.set_env("LLM_API_KEY", key)
    cfg["setup_ai"] = True
    config_mgr.save_config(cfg)
    print(f"\n{ui.HL}>> AI 설정이 저장되었습니다!{ui.FG}")
    input("[Enter]를 누르세요...")

def _setup_news(cfg):
    """뉴스 피드 원천 RSS 설정"""
    print("\n[ News Feed 설정 ]")
    sources = cfg.get("news_sources", [])
    print(f"  * 현재 등록된 피드: {len(sources)}개")
    for s in sources:
        print(f"    - {s.get('name')}: {s.get('uri')}")
    print()
    
    name = ui.safe_input("추가할 피드명 (예: 네이버 IT) [C : 취소]: ")
    if name.lower() == "c": return
    if not name: return
    uri = ui.safe_input("추가할 URI (예: rss.naver.com/it.xml) [C : 취소]: ")
    if uri.lower() == "c": return
    if not uri: return

    if "news_sources" not in cfg:
        cfg["news_sources"] = []
    
    cfg["news_sources"].append({"name": name, "uri": uri})
    cfg["setup_news"] = True
    config_mgr.save_config(cfg)
    print(f"\n{ui.HL}>> 피드가 추가되었습니다!{ui.FG}")
    input("[Enter]를 누르세요...")

def _setup_log(cfg):
    """로그 기록 수준 설정"""
    print("\n[ Log 설정 ]")
    curr_log = cfg.get("log_level", "없음")
    print(f"  * 현재 로그 수준: {curr_log}")
    print("  * 기록 파일 위치: ./logs/app.log\n")
    
    print("  [로그 수준 선택]")
    print("  1) DEBUG   : 시스템의 모든 세부 흐름과 개발 정보를 낱낱이 기록합니다.")
    print("  2) INFO    : 일반적인 실행 흐름, 시작/종료 등 상태 변화를 기록합니다. (권장)")
    print("  3) WARNING : 당장 멈추지는 않지만, 잠재적인 문제나 주의 사항을 기록합니다.")
    print("  4) ERROR   : 심각한 에러나 예외가 발생하여 실패한 경우만 기록합니다.")
    
    log_choice = ui.safe_input("번호 선택 (1-4) [변경 안 함: C ]: ")
    if log_choice.lower() == "c": return
    
    log_map = {"1": "DEBUG", "2": "INFO", "3": "WARNING", "4": "ERROR"}
    level = log_map.get(log_choice, curr_log if curr_log != "없음" else None)
    
    if not level:
        print("유효한 로그 수준이 선택되지 않았습니다.")
        input("[Enter]를 눌러 다시 시도하세요...")
        return
    
    cfg["log_level"] = level
    cfg["setup_log"] = True
    config_mgr.save_config(cfg)
    print(f"\n{ui.HL}>> 로그 수준이 [{level}]로 변경되었습니다!{ui.FG}")
    input("[Enter]를 누르세요...")