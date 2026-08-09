# 뉴스 AI 파이프라인

뉴스를 자동으로 수집하고, AI로 요약·분석한 뒤, 시각화와 리포트로 만들어내는 CLI 기반 데이터 파이프라인입니다.

## 관련 문서

- [완료 보고서](docs/완료보고서.md) — 요구사항 충족 현황, Phase별 결과, 실행 검증 근거
- [이슈 노트](docs/이슈노트.md) — 개발 중 실제로 부딪힌 문제와 해결 과정
- [학습 가이드](docs/학습가이드.md) — 과제 목표 기준으로 실제 코드를 예시 삼아 설명하는 학습 자료

## 주요 기능

- **뉴스 수집** — RSS, 공개 API, 크롤링 세 가지 방식을 모두 지원. `config.json`에 소스를 등록해두면 자동으로 해당 방식으로 수집
- **raw / clean 데이터 분리 저장** — 원본은 `data/raw/*.jsonl`에 그대로 보존, 정제된 데이터만 `data/news.db`(SQLite)에 저장
- **중복 뉴스 처리** — URL 기준(트래킹 파라미터 정규화 후) 판별, `skip`(무시) 또는 `upsert`(갱신) 정책 선택 가능
- **AI 기반 뉴스 요약** — 전체/특정 ID/미요약분만 선택해서 요약 가능
- **AI 기반 인사이트 분석** — 기간·카테고리별 트렌드, 핵심 키워드, 시사점 도출
- **시각화** — 카테고리별 뉴스 분포(막대), 일자별 수집 추이(선), 감성 분포(파이) 차트(PNG)
- **리포트 생성** — 품질 지표, TOP N 집계, AI 인사이트를 콘솔 및 `.md`/`.txt` 파일로 출력
- **데이터 내보내기** — CSV, JSONL, Excel 지원
- **대화형 CLI** — 인자 없이 실행하면 번호 선택형 메인 메뉴 제공, 커맨드 모드도 동시 지원
- **[보너스] 뉴스 조회** — `list`/`show`로 목록·상세 조회, 필터링/페이지네이션(기본 정렬: 발행일 최신순)
- **[보너스] 감성 분석** — 뉴스별 긍정/부정/중립 분류 및 시각화
- **[보너스] 정기 실행** — 스케줄러를 이용한 자동 수집

## 기술 스택

- Python 3.10+
- requests, feedparser, beautifulsoup4 (수집)
- sqlite3 (내장, clean 데이터 저장)
- pandas, openpyxl (집계/내보내기)
- matplotlib (시각화)
- rich (CLI 화면 표시)
- python-dotenv (환경변수 관리)
- openai / anthropic / google-genai (요약/인사이트 분석/감성 분석 — `.env`의 `LLM_PROVIDER`로 선택)

## 설치

```bash
git clone <repo-url>
cd news_pipeline
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 초기 설정

API 키와 뉴스 소스는 CLI 안에서 대화형으로 등록합니다. `config.json`을 직접 편집해도 됩니다.

```bash
# AI 플랫폼(GPT/Gemini/Claude) → 모델명 → API 키 순으로 등록 (.env에 저장, 화면에 노출되지 않음)
python main.py config set-api-key

# 뉴스 소스 등록 (이름 → 방식[rss/api/crawl] → 주소 → 카테고리 순으로 입력)
python main.py config add-source

# 등록된 소스 확인
python main.py config list

# DB/로그 저장 폴더 경로, 로그 기록 수준 변경(선택)
python main.py config set-db-path
python main.py config set-log
```

`config set-api-key`에서 고를 수 있는 플랫폼:

| 플랫폼 | `LLM_PROVIDER` 값 | API 키 발급처 |
|---|---|---|
| GPT (OpenAI) | `openai` | https://platform.openai.com |
| Gemini (Google) | `google` | https://aistudio.google.com (무료 티어 있음) |
| Claude (Anthropic) | `anthropic` | https://console.anthropic.com |

`config.json`에는 예시로 키가 필요 없는 소스 4개가 기본 등록되어 있습니다.

| 이름 | 방식 | 설명 |
|---|---|---|
| `google_news_it_rss` | rss | Google 뉴스 RSS 검색(키 불필요) |
| `hackernews_api` | api | Hacker News 공개 API(키 불필요) |
| `wikipedia_current_events_crawl` | crawl | 위키백과 "포털:최근 사건" 페이지 크롤링 |
| `ArXiv cs.AI` | rss | ArXiv cs.AI 분야 논문 RSS(키 불필요) |

## 사용법

### 메뉴 모드 (초보자 추천)

```bash
python main.py
```
인자 없이 실행하면 번호 선택형 메뉴가 뜹니다. 번호를 고르면 필요한 값을 순서대로 물어봅니다.

### 커맨드 모드 (자동화/숙련자용)

```bash
python main.py fetch --source all --limit 20
python main.py clean --policy skip
python main.py summarize --unsummarized --limit 10
python main.py analyze --date-from 2026-08-01 --date-to 2026-08-06 --category IT
python main.py report --format md
python main.py export --format csv --status summarized --date-from 2026-08-01 --date-to 2026-08-07
python main.py list --category IT --page 1
python main.py show --id 42
python main.py sentiment --unanalyzed --limit 10
```

## 프로젝트 구조

```
news_pipeline/
├── main.py
├── config.json
├── .env
├── requirements.txt
├── src/
│   ├── cli.py
│   ├── menu.py
│   ├── config_loader.py
│   ├── setup.py
│   ├── ui.py
│   ├── logger.py
│   ├── db.py
│   ├── raw_store.py
│   ├── normalize.py
│   ├── collector.py
│   ├── cleaner.py
│   ├── ai_client.py
│   ├── summarizer.py
│   ├── analyzer.py
│   ├── sentiment.py
│   ├── visualizer.py
│   ├── reporter.py
│   ├── exporter.py
│   └── viewer.py
├── data/
│   ├── raw/
│   └── news.db
├── reports/
│   ├── charts/
│   └── exports/
└── logs/
    └── app.log
```

## 정기 실행 (스케줄링)

### Linux/Mac — cron

매시 정각에 뉴스를 자동 수집하려면 crontab에 아래를 등록합니다.

```bash
crontab -e
```
```
0 * * * * cd /path/to/news_pipeline && venv/bin/python main.py fetch --source all --limit 20 >> logs/cron.log 2>&1
```

### Windows — 작업 스케줄러(Task Scheduler)

1. `작업 스케줄러` 실행 → `작업 만들기`
2. `트리거` 탭: "매일" 반복, 원하는 시간마다 반복하도록 설정
3. `동작` 탭: 프로그램/스크립트에 `venv\Scripts\python.exe`, 인수에 `main.py fetch --source all --limit 20`, 시작 위치에 프로젝트 폴더 경로 입력
4. 또는 PowerShell에서 직접 등록:

```powershell
$action = New-ScheduledTaskAction -Execute "D:\path\to\news_pipeline\venv\Scripts\python.exe" `
    -Argument "main.py fetch --source all --limit 20" `
    -WorkingDirectory "D:\path\to\news_pipeline"
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -TaskName "NewsPipelineFetch" -Action $action -Trigger $trigger
```

## 코드 품질 가드 (개발용)

복잡도가 너무 높아지거나 모듈끼리 순환 참조가 생기는 것을 자동으로 잡아줍니다. 앱 실행에는 필요 없고, 개발할 때만 씁니다.

```bash
pip install -r requirements-dev.txt

ruff check .          # 복잡도(10 초과)·인자개수(5개 초과)·기본 린트
lint-imports          # 모듈 레이어 순환 참조 검사 (pyproject.toml의 [tool.importlinter])
```

## AI API 사용 시 주의사항

플랫폼(OpenAI/Google/Anthropic)마다 레이트리밋이 다릅니다. `config.json`의 `ai.request_delay_sec` 값으로 AI 호출 간 지연을, `ai.max_tokens`로 응답 최대 토큰(비용 방어용)을 조절할 수 있고, 429(요청 제한)나 5xx(일시적 서버 과부하) 응답 시 지수 백오프로 자동 재시도합니다.

개발 중 Google Gemini에서 실제로 확인한 사례: `gemini-2.5-flash`는 계정에 따라 **일일 20회**로 제한될 수 있습니다(에러 메시지의 `quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`로 확인 가능). 이 한도에 걸리면 `config set-api-key`로 `gemini-3.5-flash-lite`처럼 별도 쿼터를 쓰는 다른 모델로 바꾸거나, 아예 다른 플랫폼(OpenAI/Anthropic)으로 전환해보세요. 정확한 한도는 계정/플랫폼마다 다르므로 각 플랫폼의 공식 rate-limit 페이지에서 실시간으로 확인하는 것이 가장 정확합니다.

짧은 시간에 대량으로 요약/분석을 돌리면 제한에 걸릴 수 있으니 `--limit` 옵션으로 건수를 조절하세요.

## 주의사항

- API 키는 코드나 `config.json`에 직접 작성하지 않습니다. 반드시 `.env`(`LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`) 또는 환경변수로 관리합니다.
- 크롤링 시 사이트 정책을 준수하고, 요청 간 지연(`config.json`의 `fetch.request_delay_sec`)을 반드시 둡니다.
