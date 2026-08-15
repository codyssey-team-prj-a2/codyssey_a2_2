# README 및 운영 가이드 (README & Operations Manual)

- **프로젝트명**: Python CLI 기반 AI 뉴스 데이터 파이프라인 & 인사이트 리포트 자동화 서비스[cite: 1]
- **대상 레포지토리**: `codyssey-team-prj-a2/codyssey_a2_2` (`main` 브랜치)[cite: 1]
- **문서 버전**: v1.0.0[cite: 1]
- **작성일**: 2026-08-14[cite: 1]

---

## 1. 프로젝트 개요 (Overview)

### 1.1 서비스 소개

본 서비스는 외부 뉴스 소스(RSS 피드, 웹 크롤링)로부터 데이터를 자동 수집, 정제, LLM 기반 요약 및 인사이트 분석, 시각화 차트 및 리포트 생성, 데이터 내보내기까지의 전체 데이터 파이프라인을 CLI 및 대화형 콘솔 환경에서 일괄 수행하는 Python 애플리케이션이다[cite: 1].

### 1.2 핵심 특징

1. **이중 인터페이스 (Dual Interface in `main.py`)**: 단일 실행 파일에서 대화형 콘솔 메뉴(TUI)와 CLI 서브커맨드 직접 실행 모드를 동시에 지원한다[cite: 1].
2. **하이브리드 저장소 (Hybrid Storage)**: 원본 무결성 보존을 위한 JSONL(Raw) 저장소와 빠른 조회/Upsert/집계 연산을 위한 SQLite(Clean) DB를 조합하여 활용한다[cite: 1].
3. **Multi-LLM 연동 지원**: Gemini, OpenAI, Anthropic 등 다양한 AI 프로바이더 연동과 함께, 재시도 백오프(Exponential Backoff) 및 WAF 차단 방어 로직을 내장하고 있다[cite: 1].
4. **기업형 배포 파이프라인**: Agile 방법론 기반으로 개발자별 브랜치(`dev-*`) $\rightarrow$ `staging` (단위 테스트) $\rightarrow$ `main` (통합 테스트) 구조를 준수한다[cite: 1].

---

## 2. 개발 및 실행 환경 구축 (Environment Setup)

### 2.1 시스템 요구사항

- **Python**: Python 3.10 이상[cite: 1]
- **Docker / Docker Compose**: 최신 컨테이너 런타임 환경 지원[cite: 1]

### 2.2 Docker 기반 실행 방법 (권장)

컨테이너 환경에서 실행 시 환경 의존성 없이 즉시 빌드 및 구동이 가능하다[cite: 1].

```bash
# 1. docker 디렉토리로 이동
cd docker

# 2. Docker 이미지 빌드 및 실행 스크립트 권한 부여 후 실행
chmod +x run.sh
./run.sh

# 4. 컨테이너 내부(app/src)에서 메인 애플리케이션 실행
python3 main.py
```

- `docker-compose.yml`을 통해 호스트의 `src/`, `data/`, `logs/`, `script/` 폴더가 컨테이너 내부로 실시간 마운트된다[cite: 1].

---

## 3. 프로그램 실행 및 사용 가이드 (User Guide)

### 3.1 대화형 콘솔 메뉴 (TUI Mode)

인자 없이 `python3 main.py`를 실행하면 메인 대화형 메뉴로 진입하며, 숫자를 입력하여 각 기능 서브메뉴로 이동한다[cite: 1].

```text
=================================================
  코디세이(Codyssey) 뉴스 데이터 분석 플랫폼
=================================================
  0. 환경 설정 (4/4 완료 - AI:O | 뉴스:O | DB:O | 로그:O)
───────────────────────────────────────────────────
  1. 뉴스 수집 (fetch)
  2. 데이터 정제 (clean)
  3. AI 3줄 요약 (summarize)
  4. AI 종합 인사이트 분석 (analyze)
───────────────────────────────────────────────────
  5. 뉴스 목록 조회 (list)
  6. 품질 지표 및 시각화 차트 출력 (report)
  7. AI 감성 분석 (sentiment)
───────────────────────────────────────────────────
  8. 데이터 내보내기 (export)

  Q. 시스템 종료
───────────────────────────────────────────────────
```

- 실행 화면 예시 [실행화면 링크](./documentation/result/7.ui-example.md)

### 3.2 CLI 서브커맨드 직접 실행 명령어 예시

각 서브메뉴 제어소(`Codyssey/<모듈명> >`)에 접속 후 CLI 명령어를 직접 입력하여 빠르게 파이프라인을 실행할 수 있다[cite: 1].

1. **뉴스 데이터 수집 (`fetch`)**:
   ```bash
   Codyssey/fetch > fetch --source google_news_it_rss --limit 20
   ```
2. **데이터 정제 (`clean`)**:
   ```bash
   Codyssey/clean > clean --policy upsert
   ```
3. **AI 3줄 요약 (`summarize`)**:
   ```bash
   Codyssey/summarize > summarize --unsummarized --limit 10
   ```
4. **AI 종합 인사이트 분석 (`analyze`)**:
   ```bash
   Codyssey/analyze > analyze --date-from 2026-08-01 --date-to 2026-08-13 --category IT
   ```
5. **AI 감성 분석 (`sentiment`)**:
   ```bash
   Codyssey/sentiment > sentiment --unanalyzed --limit 10
   ```
6. **품질 지표 및 리포트/차트 생성 (`report`)**:
   ```bash
   Codyssey/report > report --format console
   # 또는 Markdown 파일 저장
   Codyssey/report > report --format md --date-from 2026-08-01 --date-to 2026-08-13
   ```
7. **데이터 내보내기 (`export`)**:
   ```bash
   Codyssey/export > export --format csv --status all
   Codyssey/export > export --format excel --status all
   Codyssey/export > export --format jsonl --status all
   ```
8. **뉴스 목록 및 상세 조회 (`list`, `show`)**:
   ```bash
   Codyssey/list > list --page 1 --size 10 --category IT
   Codyssey/show > show --no 20
   ```

---

## 4. 환경 설정 및 비밀키 관리 (Configuration)

### 4.1 설정 파일 (`src/config.json`)

뉴스 수집 피드, DB 저장 경로 및 로그 설정을 관리한다[cite: 1]. TUI 1번 메뉴(환경 설정)를 통해 UI 상에서 안전하게 수정 가능하다[cite: 1].

```json
{
	"setup_step": 4,
	"news_sources": [
		{
			"name": "google_news_it_rss",
			"method": "rss",
			"url": "[https://news.google.com/rss/search?q=IT&hl=ko&gl=KR&ceid=KR:ko](https://news.google.com/rss/search?q=IT&hl=ko&gl=KR&ceid=KR:ko)",
			"category": "IT",
			"enabled": true
		},
		{
			"name": "wikipedia_current_events_crawl",
			"method": "crawl",
			"url": "[https://ko.wikipedia.org/wiki/%ED%8F%AC%ED%84%B8:%EC%B5%9C%EA%B7%BC_%EC%82%AC%EA%B1%B4](https://ko.wikipedia.org/wiki/%ED%8F%AC%ED%84%B8:%EC%B5%9C%EA%B7%BC_%EC%82%AC%EA%B1%B4)",
			"category": "종합",
			"enabled": true
		}
	],
	"storage": {
		"db_path": "./data/codyssey.db"
	},
	"logging": {
		"file": "./logs/app.log",
		"level": "INFO"
	}
}
```

### 4.2 환경 변수 파일 (`src/.env`)

API 키 등 민감 정보는 `.env` 파일에 분리 저장되며, Git 추적 대상에서 제외된다[cite: 1].

```ini
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.4-nano-chat
LLM_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://your-custom-gateway-url/v1
```

---

## 5. 팀 R&R 및 협업 프로세스 (Team Workflow)

### 5.1 역할 분담 (R&R)

- **PM (박순몽)**: 프로젝트 운영, 일정 관리(WBS/간트차트), 전체 스켈레톤 코드 작성 및 라우팅/설계[cite: 1]
- **개발자 1, 2 (김병국, 이원일)**: 수집, 정제, AI 연동, 시각화, 내보내기 등 모듈별 기능 분담 개발[cite: 1]
- **QA (김정진)**: 단위/통합 테스트 시트 작성, 예외 상황 검증 및 크래시 테스트 피드백, 미팅록 작성[cite: 1]

### 5.2 Agile 협업 기법 및 프로젝트 관리 툴 (WBS, Gantt, Kanban)

단기 프로젝트의 특성에 맞춰 기획부터 제출까지 빠른 프로토타이핑과 점진적 고도화를 위해 **애자일(Agile) - 스프린트 방법론**을 채택하였으며, **GitHub Projects**를 단일 도구(Single Source of Truth)로 활용하였다[cite: 1].

1. **WBS (Work Breakdown Structure / List View)**[cite: 1]:
   - 프로젝트 생애주기 단계별 1-Depth(Phase)부터 3-Depth(Task)까지 세부 태스크를 체계적으로 분류하고 이슈를 등록하여 담당자, 진행 상황, 우선순위를 투명하게 관리[cite: 1].
2. **간트 차트 (Gantt / Timeline View)**[cite: 1]:
   - 환경 세팅 ➔ 핵심 파이프라인 개발 ➔ QA 및 최종 통합 테스트로 이어지는 시계열 일정을 가시화하여 프로젝트 데드라인을 사수[cite: 1].
3. **칸반 보드 (Kanban View)**[cite: 1]:
   - `해야할 일` ➔ `작업중` ➔ `작업완료` ➔ `검토중` ➔ `최종완료` 상태 흐름을 시각화하여 병목(Blocker) 구간을 즉시 파악하고, 데일리 스크럼 진행 및 피드백 안건으로 활용[cite: 1].

   [**프로젝트 진행 설계 상세**](./documentation/draft/프로젝트진행_설계_전략.md)

### 5.3 Git 브랜치 운영 전략

```text
개인 작업 브랜치 (dev-*)
   └── 작업 완료 후 Commit & Push
          │
          ▼ PR & Merge
Staging 브랜치 (staging)
   └── 단위 테스트 (Unit Test) 및 Docker 환경 검증
          │
          ▼ PR & Merge
Main 브랜치 (main)
   └── 전체 파이프라인 E2E 통합 라이브 테스트 검증 후 최종 제출
```

---

## 6. 문제 해결 및 트러블슈팅 (Troubleshooting)

1. **Gemini 요약 결과 잘림 현상**:
   - **원인**: Gemini 2.5 Flash 등의 모델이 내부 추론(Thinking) 과정에 출력 토큰 예산을 소모하여 요약 응답이 끊어짐[cite: 1].
   - **해결**: `ai_client.py` 호출 시 `thinking_budget=0` 옵션을 지정하여 토큰 예산이 실제 답변에만 쓰이도록 조치함[cite: 1].
2. **OpenAI SDK 헤더 차단 (WAF 403 Error)**:
   - **원인**: 특정 API 게이트웨이 WAF가 OpenAI 공식 SDK의 기본 헤더 지문을 차단함[cite: 1].
   - **해결**: `ai_client.py` 내 OpenAI 호출부를 SDK 대신 `requests` 라이브러리로 직접 통신하도록 구현하여 성공적 연동 처리[cite: 1].
3. **잘못된 파라미터 입력 시 크래시**:
   - **해결**: CLI 인자 파싱 시 음수/문자열 limit 또는 잘못된 포맷의 날짜 입력 시 에러 안내 후 기본값(20건/10건/최근 7일)으로 안전하게 폴백(Fallback)되도록 구현됨[cite: 1].

## 7. 프로젝트 산출 문서 - 링크 확인 (documentation/result|test 확인)

1. [**요구사항 정의서**](./documentation/result/1.요구사항_정의서.md)
2. [**시스템 아키텍쳐**](./documentation/result/2.시스템아키텍처.md)
3. [**데이터 파이프라인 & DB 설계서**](./documentation/result/3.데이터파이프라인_DB설계서.md)
4. [**CLI 및 AI 프롬프트 명세서**](./documentation/result/4.CLI_및_AI_프롬프트명세서.md)
5. [**테스트 계획 및 시나리오 정의서**](./documentation/result/5.테스트계획_및_시나리오정의서.md)
6. [**테스트 시트**](./documentation/test/QA_체크리스트_환경설정테스트.xlsx)
7. [**정기 실행 스케줄링 가이드**](./documentation/result/6-1.정기실행_스케줄링_가이드.md)
