# 뉴스 AI 파이프라인 미션 — 준비 & 작업 계획서

> 대상: Python/프로그래밍 초보자
> 목표: 막막함을 줄이고, 매일 "오늘 뭘 해야 하는지" 알 수 있게 만드는 문서

---

## 1. 시작 전 반드시 알아야 할 개념 (모르면 검색해서라도 이해하고 시작하기)

이 미션은 새로운 걸 발명하는 게 아니라, 아래 개념들을 **순서대로 이어 붙이는 것**입니다. 하나씩 짚어볼게요.

| 개념 | 왜 알아야 하나 | 한 줄 설명 |
|---|---|---|
| **파이프라인(Pipeline)** | 전체 그림 이해 | 수집 → 정제 → 분석 → 리포트 순서로 데이터가 흘러가는 구조 |
| **CLI (Command Line Interface)** | 이 프로젝트의 실행 방식 | `python main.py fetch --limit 20` 처럼 터미널 명령어로 프로그램을 조작 |
| **argparse 서브커맨드** | CLI 설계의 핵심 | `fetch`, `clean`, `summarize` 등 명령어별로 다른 동작을 하게 만드는 표준 라이브러리 |
| **raw / clean 데이터 분리** | 데이터 정제 이유 | raw = 원본 그대로 보관(나중에 재가공 가능), clean = 검증·정규화된 데이터. 원본을 지우면 나중에 정제 로직이 틀렸을 때 복구 불가 |
| **SQLite** | 영구 저장소 | 파일 하나로 동작하는 가벼운 DB. `sqlite3`는 Python 기본 내장 모듈이라 설치 불필요 |
| **환경변수 / .env** | API 키 보안 | 코드에 키를 직접 쓰지 않고 `.env` 파일이나 시스템 환경변수에서 불러옴 (`python-dotenv` 사용) |
| **requests / HTTP 타임아웃** | 외부 API 호출 | 네트워크 요청이 응답 없이 무한 대기하지 않도록 `timeout=` 설정 |
| **BeautifulSoup** | 크롤링 | HTML을 파싱해서 원하는 텍스트(제목, 본문)만 추출 |
| **AI API 호출 (Anthropic/OpenAI)** | 요약·분석 담당 | 텍스트를 보내고 결과를 받는 것 자체는 requests 한 번 호출과 비슷함 |
| **matplotlib** | 시각화 | 숫자 데이터를 막대그래프/선그래프로 그림, 한글 폰트 별도 설정 필요 |
| **모듈 분리** | 코드 구조 요구사항 | 기능별로 파일을 나눔 (예: `collector.py`, `db.py`, `ai.py`, `report.py`) — 한 파일에 다 쓰면 안 됨 |
| **logging 모듈** | 디버깅/운영 | `print()` 대신 레벨(INFO/WARNING/ERROR)별로 기록 남기기 |

> 💡 이 중 하나라도 "처음 듣는다" 싶으면, 해당 개념만 딱 30분~1시간 정도 검색해서 간단한 예제 코드를 직접 쳐보고 넘어가는 걸 추천해요. 완벽히 이해하지 않아도 "이런 게 있구나" 정도만 알면 실전에서 막히지 않습니다.

---

## 2. 준비물 체크리스트

### 2-1. 개발 환경
- [ ] Python 3.10 이상 설치 확인 (`python --version`)
- [ ] 코드 에디터: VS Code 추천 (Python 확장 설치)
- [ ] 가상환경 사용법 숙지
  ```bash
  python -m venv venv
  source venv/bin/activate      # Mac/Linux
  venv\Scripts\activate         # Windows
  ```

### 2-2. 필요한 라이브러리 (미리 설치 목록만 파악)
```bash
pip install requests beautifulsoup4 pandas matplotlib openpyxl python-dotenv anthropic
```
- `requests` — API 호출, 크롤링용 HTTP 요청
- `beautifulsoup4` — HTML 파싱(크롤링)
- `pandas` — 데이터 집계/CSV·엑셀 내보내기
- `matplotlib` — 차트 생성
- `openpyxl` — 엑셀 파일 저장 (pandas가 내부적으로 사용)
- `python-dotenv` — .env 파일에서 API 키 읽기
- `anthropic` (또는 `openai`) — AI 요약/분석 SDK
- `sqlite3` — **설치 불필요**, Python 기본 내장

### 2-3. 계정/키 준비
- [ ] 뉴스 데이터 소스 선택 및 키 발급
  - 가장 쉬운 경로: **RSS 피드** (키 불필요, 예: 네이버 뉴스 RSS, 언론사 RSS)
  - 또는 **네이버 오픈 API** (검색 API, 클라이언트 ID/Secret 발급 필요)
- [ ] AI API 키 발급 (Anthropic Console 또는 OpenAI)
- [ ] 위 키들을 저장할 `.env` 파일 준비 (코드에 직접 쓰지 않기)

### 2-4. 기타
- [ ] 한글 폰트 파일 확보 (matplotlib 한글 깨짐 방지) — 예: 나눔고딕(`NanumGothic.ttf`), OS에 이미 있는 경우도 많음
- [ ] (선택) Git/GitHub 기본 사용법 — 버전 관리하면 실수 복구가 쉬움

---

## 3. 미리 그려보는 프로젝트 폴더 구조

작업을 시작하기 전에 폴더 구조를 먼저 스케치해두면 "모듈 최소 4개 분리" 요구사항을 자연스럽게 만족합니다.

```
news_pipeline/
├── main.py                # argparse 진입점 (서브커맨드 라우팅만)
├── config.json             # API 소스, 중복정책 등 설정
├── .env                     # API 키 (git에는 올리지 않기)
├── requirements.txt
├── src/
│   ├── collector.py        # fetch: API/RSS + 크롤링
│   ├── cleaner.py          # clean: 정제, 중복처리
│   ├── db.py                # SQLite 연결/CRUD 공통 함수
│   ├── summarizer.py       # summarize: AI 요약
│   ├── analyzer.py         # analyze: AI 인사이트 분석
│   ├── visualizer.py       # 차트 생성 (matplotlib)
│   ├── reporter.py         # report: 리포트 생성
│   └── exporter.py         # export: CSV/JSONL/Excel
├── data/
│   ├── raw/                 # 원본 저장 (또는 SQLite 테이블로 대체 가능)
│   └── clean/
├── reports/                 # 리포트 결과물(txt/md), 차트 png
└── logs/
    └── app.log
```

---

## 4. 단계별 작업 계획 (권장 순서)

핵심 원칙: **"돌아가는 가장 작은 것부터"** 만들고 점점 살을 붙여갑니다. 처음부터 완벽하게 만들려 하지 말고, 각 단계가 끝날 때마다 실제로 실행해서 눈으로 결과를 확인하세요.

### Phase 0. 환경 세팅 (약 0.5~1일)
- 가상환경 생성, 라이브러리 설치
- `.env`에 API 키 넣고, `python-dotenv`로 잘 읽히는지만 테스트
- 폴더 구조 뼈대 생성 (빈 파일들만)

### Phase 1. CLI 뼈대 + 설정/로깅 (1일)
- `main.py`에 argparse로 서브커맨드 6개(`fetch, clean, summarize, analyze, report, export`) 등록만 하고, 각 서브커맨드는 `print("fetch 실행됨")` 정도만 찍히게
- `config.json` 읽어오는 함수 작성
- `logging` 기본 설정 (콘솔 + 파일 출력)
- ✅ 완료 기준: `python main.py fetch` 등 6개 명령어가 모두 에러 없이 실행됨

### Phase 2. 저장소(SQLite) 설계 (1~2일)
- 테이블 설계: news 테이블 최소 컬럼 — id, title, content, category, source, collected_at, method(api/crawl), status(summarized 여부), summary, is_clean 등
- `db.py`에 연결/생성/삽입/조회 함수만 먼저 작성
- ✅ 완료 기준: 더미 데이터 1건을 직접 insert → select로 확인 가능

### Phase 3. 뉴스 수집 - fetch (2~3일, 가장 오래 걸리는 구간)
- **먼저 RSS 방식**부터 구현 (제일 쉬움, 키 불필요)
- 이후 **API 또는 크롤링** 방식 추가
- `requests` 호출 시 `timeout=`, `try/except`로 에러 처리
- 수집 결과를 raw 저장소(SQLite 또는 별도 테이블/파일)에 저장
- ✅ 완료 기준: `python main.py fetch --limit 20` 실행 시 실제 뉴스 20건이 DB에 쌓임

### Phase 4. 데이터 정제 - clean (1~2일)
- 필수 필드 검증(제목/본문 없으면 제외), 텍스트 정규화(공백/특수문자 정리), 날짜 포맷 통일
- 중복 처리(skip 또는 upsert) 로직
- ✅ 완료 기준: raw 데이터 중 정상 데이터만 clean 상태로 표시/저장됨

### Phase 5. AI 요약 - summarize (2일)
- AI API에 본문 하나 보내서 요약 받아오는 최소 기능부터 (뉴스 1건 대상 하드코딩 테스트)
- 이후 `--all`, `--id`, `--unsummarized` 옵션 연결
- 실패 시 로깅 후 스킵 처리
- ✅ 완료 기준: `summarize --unsummarized --limit 5` 실행 시 5건 요약되어 DB에 저장됨

### Phase 6. AI 인사이트 분석 - analyze (2일)
- 기간/카테고리로 뉴스 여러 건을 모아 하나의 프롬프트로 AI에 전달
- 트렌드/키워드/시사점 등 2개 이상 항목 추출
- 결과 저장(별도 테이블 또는 JSON 파일)
- ✅ 완료 기준: 콘솔에 인사이트 결과가 보기 좋게 출력됨

### Phase 7. 시각화 (1~2일)
- matplotlib으로 카테고리별 뉴스 수(막대그래프), 일자별 수집 추이(선그래프)
- 한글 폰트 설정 (`plt.rcParams['font.family']`)
- PNG로 저장
- ✅ 완료 기준: `reports/` 폴더에 차트 이미지 2개 생성

### Phase 8. 리포트 생성 - report (1일)
- 품질 지표(예: 수집 성공률, 정제율) 2개 이상
- TOP N 집계(예: 카테고리별 상위 키워드) 1개 이상
- analyze 결과 포함
- 콘솔 출력 + txt/md 파일 저장
- ✅ 완료 기준: `report` 실행 시 `.md` 파일 하나가 완성된 형태로 생성

### Phase 9. 내보내기 - export (1일)
- CSV, JSONL, Excel 중 2개 이상 (pandas의 `to_csv`, `to_excel` 활용하면 빠름)
- `--status summarized` 같은 필터 옵션
- ✅ 완료 기준: 실제 파일이 열려서 데이터가 보임

### Phase 10. 마무리 (1~2일)
- README.md 작성 (설치법, 실행법, 폴더 구조 설명)
- 전체 흐름 한 번에 실행해보며 버그 수정
- (여유 있으면) 보너스 과제: list/show 조회 CLI, 감성분석, cron 스케줄링 문서화

---

## 5. 예상 전체 기간

| 구분 | 기간 |
|---|---|
| 최소 기능 완성 (Phase 0~9) | 약 12~17일 (초보자 기준, 매일 2~3시간 투입 가정) |
| 보너스 포함 마무리 | +2~3일 |

물론 개인차가 크니, 이 일정은 "감을 잡기 위한 참고용"으로만 봐주세요. 막히는 구간(특히 Phase 3 수집, Phase 5 AI 연동)에서 시간이 더 걸리는 건 자연스러운 일입니다.

---

## 6. 막힐 때 대처 팁

- **한 번에 다 만들려 하지 말기** — 각 Phase마다 "돌아가는 최소 버전"을 먼저 만들고, 그다음 옵션/예외처리를 추가
- **에러 메시지를 읽기** — Python 에러는 대부분 마지막 줄에 원인이 나옵니다. 그대로 검색하면 대부분 해결됨
- **더미 데이터로 먼저 테스트** — 실제 API/크롤링이 안 될 때는 가짜 데이터를 리스트로 만들어 DB 저장/조회 로직부터 검증
- **하루 끝에 커밋(선택)** — Git을 쓴다면 매일 작업 끝에 커밋해두면 실수해도 되돌리기 쉬움

---

이 계획서는 뼈대이니, 실제로 진행하시면서 각 Phase에 대한 구체적인 코드 작성이나 막히는 부분이 생기면 그때그때 편하게 질문해 주세요. 원하시면 Phase 0~1(환경설정 + CLI 뼈대)부터 같이 코드로 만들어볼 수도 있습니다.
