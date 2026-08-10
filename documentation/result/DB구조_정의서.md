### DB 구조

: jsonl 과 sqlite 를 모두 사용하여 raw data 와 infomation 을 구분함

**DB : SQLite**

**clean_news (정제된 newsfeed)**

| **컬럼명 (필드)** | **자료형 (Type)** | **제약조건**                | **설명 (용도)**                                                                    |
| ----------------- | ----------------- | --------------------------- | ---------------------------------------------------------------------------------- |
| **news_id**       | `TEXT`            | **PK**                      | 기사의 고유 식별자 (예: URL 또는 해시값). 중복 처리(Upsert)의 기준이 됨            |
| **source**        | `TEXT`            | `NOT NULL`                  | 언론사 또는 피드 출처 (예: 'Naver', 'Daum')                                        |
| **category**      | `TEXT`            | `NOT NULL`                  | 카테고리 (예: 'IT', '경제'). `--category` 옵션 검색용                              |
| **title**         | `TEXT`            | `NOT NULL`                  | 기사 제목                                                                          |
| **content**       | `TEXT`            | `NOT NULL`                  | 정제(텍스트 정규화)가 완료된 본문                                                  |
| **pub_date**      | `TEXT`            | `NOT NULL`                  | 통일된 날짜 포맷 (YYYY-MM-DD). `--date` 옵션 검색용                                |
| **ai_summary**    | `TEXT`            | `NULL`                      | AI가 생성한 3줄 요약문. (초기엔 비어있음)                                          |
| **is_summarized** | `INTEGER`         | `DEFAULT 0`                 | 요약 완료 여부 (0: 안됨, 1: 완료). `--unsummarized` 옵션 필터링을 위한 핵심 플래그 |
| **created_at**    | `TEXT`            | `DEFAULT CURRENT_TIMESTAMP` | DB에 저장된 시각                                                                   |

**ai_insight** (분석결과)

| **컬럼명 (필드)**   | **자료형 (Type)** | **제약조건**                | **설명 (용도)**                      |
| ------------------- | ----------------- | --------------------------- | ------------------------------------ |
| **insight_id**      | `INTEGER`         | **PK (Auto)**               | 분석 결과 고유 번호 (자동 증가)      |
| **target_category** | `TEXT`            | `NOT NULL`                  | 분석 대상 카테고리 (예: 'IT', 'ALL') |
| **period_from**     | `TEXT`            | `NOT NULL`                  | 분석 대상 시작일 (예: '2026-08-01')  |
| **period_to**       | `TEXT`            | `NOT NULL`                  | 분석 대상 종료일 (예: '2026-08-07')  |
| **main_trend**      | `TEXT`            | `NOT NULL`                  | AI가 추출한 주요 트렌드              |
| **core_keywords**   | `TEXT`            | `NOT NULL`                  | 콤마(,)로 구분된 핵심 키워드 목록    |
| **implications**    | `TEXT`            | `NOT NULL`                  | 비즈니스 시사점 및 공통/차이점       |
| **created_at**      | `TEXT`            | `DEFAULT CURRENT_TIMESTAMP` | 분석 수행 시각 (리포트 출력 시 활용) |

---
