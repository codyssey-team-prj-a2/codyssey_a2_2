-- src/lib/db/schema.sql

-- =========================================================
-- 1. clean_news: 정제된 개별 뉴스 데이터 및 요약문
-- =========================================================
CREATE TABLE IF NOT EXISTS clean_news (
    news_id TEXT PRIMARY KEY,           -- 기사 고유 식별자 (예: URL). 중복 처리(Upsert) 기준
    source TEXT NOT NULL,               -- 언론사 또는 피드 출처
    category TEXT NOT NULL,             -- 카테고리 (예: IT, 경제) [--category 옵션 검색용]
    title TEXT NOT NULL,                -- 기사 제목
    content TEXT NOT NULL,              -- 정제가 완료된 기사 본문
    pub_date TEXT NOT NULL,             -- 발행일 (YYYY-MM-DD 형식) [--date 옵션 검색용]
    
    ai_summary TEXT,                    -- AI가 생성한 3줄 요약문 (초기엔 NULL)
    is_summarized INTEGER DEFAULT 0,    -- 요약 완료 여부 (0: 안됨, 1: 완료) [--unsummarized 필터링용]
    sentiment TEXT,                     -- AI가 분석한 감정 (긍정, 부정, 중립)
    sentiment_reason TEXT,              -- 감정 분석 근거 문장 (최대 200자)
    created_at TEXT DEFAULT (datetime('now', 'localtime')) -- DB 저장 시각
);

-- 검색 속도 향상을 위한 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_clean_news_category ON clean_news(category);
CREATE INDEX IF NOT EXISTS idx_clean_news_pub_date ON clean_news(pub_date);
CREATE INDEX IF NOT EXISTS idx_clean_news_is_summarized ON clean_news(is_summarized);


-- =========================================================
-- 2. ai_insight: 기간별/카테고리별 AI 종합 분석 결과
-- =========================================================
CREATE TABLE IF NOT EXISTS ai_insight (
    insight_id INTEGER PRIMARY KEY AUTOINCREMENT, -- 분석 결과 고유 번호
    target_category TEXT NOT NULL,                -- 분석 대상 카테고리 (예: IT, ALL)
    period_from TEXT NOT NULL,                    -- 분석 대상 시작일 (YYYY-MM-DD)
    period_to TEXT NOT NULL,                      -- 분석 대상 종료일 (YYYY-MM-DD)
    
    main_trend TEXT NOT NULL,                     -- AI가 추출한 주요 트렌드
    core_keywords TEXT NOT NULL,                  -- 콤마(,)로 구분된 핵심 키워드 목록
    implications TEXT NOT NULL,                   -- 비즈니스 시사점 및 공통/차이점
    
    created_at TEXT DEFAULT (datetime('now', 'localtime')),    -- 분석 수행 시각
    
    -- 동일 기간, 동일 카테고리에 대한 중복 분석 결과 방지
    UNIQUE(target_category, period_from, period_to)
);

-- 리포트 출력 시 기간 및 카테고리 검색을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_ai_insight_period ON ai_insight(target_category, period_from, period_to);