# main.py
import sys
from lib.system import config_mgr, ui

# 분리된 각 개발 모듈 임포트
from lib.dev import fetch, clean, summarize, analyze, report, export

def run_setup_menu():
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
        print("\n  p. 메인 화면으로 돌아가기")
        
        choice = input(f"\n{ui.HL}설정할 번호를 선택하세요 > {ui.FG}").strip().lower()
        if choice == 'p': break
        
        # ----------------------------------------------------
        # [1] AI 설정
        # ----------------------------------------------------
        if choice == '1':
            print("\n[ AI 설정 ]")
            # 1. 기존 값 표시
            curr_prov = config_mgr.get_env("LLM_PROVIDER") or "없음"
            curr_model = config_mgr.get_env("LLM_MODEL") or "없음"
            curr_key = config_mgr.get_env("LLM_API_KEY") or "없음"
            
            print(f"  * 현재 플랫폼: {curr_prov}")
            print(f"  * 현재 모델명: {curr_model}")
            print(f"  * 현재 API Key: {curr_key[:5]}...{curr_key[-3:] if curr_key != '없음' else ''}\n")
            
            # 2. 객관식 플랫폼 선택
            print("  [플랫폼 선택]")
            print("  1) Gemini (Google)")
            print("  2) GPT (OpenAI)")
            print("  3) Claude (Anthropic)")
            prov_choice = ui.safe_input("번호 선택 (1-3) [변경 안 함: 공백]: ")
            if prov_choice is None: continue
            
            provider_map = {"1": "gemini", "2": "openai", "3": "anthropic"}
            provider = provider_map.get(prov_choice, curr_prov if curr_prov != "없음" else None)
            
            if not provider:
                print("유효한 플랫폼이 선택되지 않았습니다.")
                input("[Enter]를 눌러 다시 시도하세요...")
                continue
            
            model = ui.safe_input(f"모델명 입력 (예: gemini-1.5-flash) [현재: {curr_model}]: ")
            if model is None: continue
            model = model if model else curr_model
            
            key = ui.safe_input("API Key 입력 (화면에 표시됨) [변경 안 함: 공백]: ")
            if key is None: continue
            key = key if key else curr_key
            
            config_mgr.set_env("LLM_PROVIDER", provider)
            config_mgr.set_env("LLM_MODEL", model)
            config_mgr.set_env("LLM_API_KEY", key)
            cfg["setup_ai"] = True
            config_mgr.save_config(cfg)
            print(f"\n{ui.HL}>> AI 설정이 저장되었습니다!{ui.FG}")
            input("[Enter]를 누르세요...")
            
        # ----------------------------------------------------
        # [2] News Feed 설정
        # ----------------------------------------------------
        elif choice == '2':
            print("\n[ News Feed 설정 ]")
            # 기존 값 리스트 출력
            sources = cfg.get("news_sources", [])
            print(f"  * 현재 등록된 피드: {len(sources)}개")
            for s in sources:
                print(f"    - {s.get('name')}: {s.get('uri')}")
            print()
            
            name = ui.safe_input("추가할 피드명 (예: 네이버 IT): ")
            if not name: continue
            uri = ui.safe_input("추가할 URI (예: rss.naver.com/it.xml): ")
            if not uri: continue
            
            cfg["news_sources"].append({"name": name, "uri": uri})
            cfg["setup_news"] = True
            config_mgr.save_config(cfg)
            print(f"\n{ui.HL}>> 피드가 추가되었습니다!{ui.FG}")
            input("[Enter]를 누르세요...")
            
        # ----------------------------------------------------
        # [3] Log 설정
        # ----------------------------------------------------
        elif choice == '3':
            print("\n[ Log 설정 ]")
            curr_log = cfg.get("log_level", "없음")
            print(f"  * 현재 로그 수준: {curr_log}")
            print("  * 기록 파일 위치: ./logs/app.log\n")
            
            # 3. 4단계 로그 수준 설명 및 객관식 선택
            print("  [로그 수준 선택]")
            print("  1) DEBUG   : 시스템의 모든 세부 흐름과 개발 정보를 낱낱이 기록합니다.")
            print("  2) INFO    : 일반적인 실행 흐름, 시작/종료 등 상태 변화를 기록합니다. (권장)")
            print("  3) WARNING : 당장 멈추지는 않지만, 잠재적인 문제나 주의 사항을 기록합니다.")
            print("  4) ERROR   : 심각한 에러나 예외가 발생하여 실패한 경우만 기록합니다.")
            
            log_choice = ui.safe_input("번호 선택 (1-4) [변경 안 함: 공백]: ")
            if log_choice is None: continue
            
            log_map = {"1": "DEBUG", "2": "INFO", "3": "WARNING", "4": "ERROR"}
            level = log_map.get(log_choice, curr_log if curr_log != "없음" else None)
            
            if not level:
                print("유효한 로그 수준이 선택되지 않았습니다.")
                input("[Enter]를 눌러 다시 시도하세요...")
                continue
            
            cfg["log_level"] = level
            cfg["setup_log"] = True
            config_mgr.save_config(cfg)
            print(f"\n{ui.HL}>> 로그 수준이 [{level}]로 변경되었습니다!{ui.FG}")
            input("[Enter]를 누르세요...")

def run_tui():
    while True:
        ui.clear_screen()
        w = ui.get_width()
        cnt, total = config_mgr.get_setup_progress()
        setup_ok = (cnt == total)
        
        ui.draw_header("코디세이(Codyssey) 파이프라인 제어소")
        status = f"환경설정 ({cnt}/{total} 완료)"
        print(f"{ui.HL}" + ui.pad_text(f"  상태: {status}", w) + f"{ui.FG}\n")
        
        # 1. 요구사항 전체 리스트 표시
        print("  1. 환경 설정 " + ("(완료)" if setup_ok else "(진행필요)"))
        print("  2. 뉴스 수집 (fetch)")
        print("  3. 데이터 정제 (clean)")
        print("  4. AI 3줄 요약 (summarize)")
        print("  5. AI 종합 인사이트 분석 (analyze)")
        print("  6. 품질 지표 및 시각화 차트 출력 (report)")
        print("  7. 데이터 내보내기 (export)")
        print("\n  q. 시스템 종료")
        
        choice = input(f"\n{ui.HL}실행할 번호를 선택하세요 > {ui.FG}").strip().lower()
        if choice == 'q':
            print(f"{ui.RESET}")
            sys.exit(0)
            
        elif choice == '1':
            run_setup_menu()
            
        elif choice in ['2', '3', '4', '5', '6', '7']:
            if not setup_ok:
                input("\n[차단] 환경설정을 3/3까지 모두 완료해야 합니다. [Enter]")
                continue
                
            # 3. 모듈 라우팅 (main.py는 여기서 임무를 다하고 각 파일로 제어권을 넘김)
            if choice == '2': fetch.run_menu_show()
            elif choice == '3': clean.run_menu_show()
            elif choice == '4': summarize.run_menu_show()
            elif choice == '5': analyze.run_menu_show()
            elif choice == '6': report.run_menu_show()
            elif choice == '7': export.run_menu_show()
            
        else:
            input("\n잘못된 입력입니다. [Enter]")

if __name__ == "__main__":
    try:
        run_tui()
    except KeyboardInterrupt:
        print(f"{ui.RESET}\n강제 종료되었습니다.")