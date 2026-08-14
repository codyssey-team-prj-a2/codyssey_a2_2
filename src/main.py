# main.py
import sys
from lib.system import config_mgr, ui

# 1번부터 10번까지 모든 개발 모듈 일괄 임포트
from lib.dev import setup, fetch, clean, summarize, analyze, report, export, list_news, show, sentiment

# [라우터 맵] 선택 번호와 해당 모듈의 실행 함수 매핑
MODULE_MAP = {
    '1': setup.run_menu_show,
    '2': fetch.run_menu_show,
    '3': clean.run_menu_show,
    '4': summarize.run_menu_show,
    '5': analyze.run_menu_show,
    '6': report.run_menu_show,
    '7': export.run_menu_show,
    '8': list_news.run_menu_show,
    '9': show.run_menu_show,
    '10': sentiment.run_menu_show,
}

def run_tui():
    while True:
        ui.clear_screen()
        w = ui.get_width()
        cnt, total = config_mgr.get_setup_progress()
        st = config_mgr.get_setup_status()
        setup_ok = (cnt == total)
        
        ui.draw_header("코디세이(Codyssey) 뉴스 데이터 분석 플랫폼")
        
        # 1. 환경 설정이 미완료(진행중)일 때만 상단 상태 바 출력 (완료 시 숨김)
        if not setup_ok:
            status = f"  상태: 환경설정 진행 필요 ({cnt}/{total} 완료)"
            print(f"{ui.HL}" + ui.pad_text(status, w) + f"{ui.FG}\n")
        
        # 2. 세부 설정 항목별 O/X 상태 구성 (AI, 뉴스, DB, 로그)
        ai_s = "O" if st.get("setup_ai") else "X"
        news_s = "O" if st.get("setup_news") else "X"
        db_s = "O" if st.get("setup_db") else "X"
        log_s = "O" if st.get("setup_log") else "X"
        
        detail_str = f"AI:{ai_s} | 뉴스:{news_s} | DB:{db_s} | 로그:{log_s}"
        status_tag = f"({cnt}/{total} 완료 - {detail_str})" if setup_ok else f"({cnt}/{total} 진행중 - {detail_str})"
        
        # 3. 1번 메뉴 항목 출력 및 구분선
        print(f"  1. 환경 설정 {status_tag}")
        ui.draw_line("─")
        
        # 4. 2~7번 핵심 파이프라인 메뉴
        print("  2. 뉴스 수집 (fetch)")
        print("  3. 데이터 정제 (clean)")
        print("  4. AI 3줄 요약 (summarize)")
        print("  5. AI 종합 인사이트 분석 (analyze)")
        print("  6. 품질 지표 및 시각화 차트 출력 (report)")
        print("  7. 데이터 내보내기 (export)")
        ui.draw_line("─")
        
        # 5. 8~10번 보너스 기능 메뉴
        print("  8. 뉴스 목록 조회 (list) [보너스]")
        print("  9. 뉴스 상세 조회 (show) [보너스]")
        print(" 10. AI 감성 분석 (sentiment) [보너스]")
        print("\n  Q. 시스템 종료\n")
        
        ui.draw_line("─")
        choice = input(f"{ui.HL}실행할 번호를 선택하세요 > {ui.FG}").strip().lower()
        
        if choice == 'q':
            sys.exit(0)
            
        elif choice in MODULE_MAP:
            # 1번(환경설정) 외 기능은 4/4 설정 완료 시에만 허용
            if choice != '1' and not setup_ok:
                input(f"\n[차단] 환경설정을 {total}/{total}까지 모두 완료해야 합니다. [Enter]")
                continue
            
            # 동적 함수 호출 (setup.run_menu_show(), fetch.run_menu_show() 등)
            MODULE_MAP[choice]()
            
        else:
            input("\n잘못된 입력입니다. [Enter]")

if __name__ == "__main__":
    try:
        run_tui()
    except KeyboardInterrupt:
        print("\n강제 종료되었습니다.")
    finally:
        ui.reset_terminal()