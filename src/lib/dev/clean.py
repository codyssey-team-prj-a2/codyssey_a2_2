from lib.system import ui
from lib.common import helpers

def run_menu_show():
    print("\n해당 기능은 아직 개발 중입니다.")
    input("[Enter]를 눌러 메인 메뉴로 돌아갑니다...")






"""
DB 연동 샘플
from lib.db import sqlite_mgr

def run_clean_logic():
    # 1. 원본 데이터 정제 로직 실행 (생략)
    # ...
    
    # 2. 정제된 데이터를 딕셔너리 리스트로 준비
    my_clean_data = [
        {
            "news_id": "https://naver.com/news/123",
            "source": "Naver",
            "category": "IT",
            "title": "애플 새 아이폰 발표",
            "content": "애플이 새로운 아이폰을...",
            "pub_date": "2026-08-11"
        },
        # ... 여러 건 ...
    ]
    
    # 3. 끝! 함수 호출 한 번으로 DB 저장(Upsert) 완료
    inserted_count = sqlite_mgr.upsert_clean_news(my_clean_data)
    print(f">> {inserted_count}건의 기사가 성공적으로 저장(Upsert)되었습니다.")
"""