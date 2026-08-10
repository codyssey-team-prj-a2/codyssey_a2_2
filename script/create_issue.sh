#!/bin/bash

# 1. 라벨(Label) 자동 생성
LABELS=("ai" "db" "개발" "문서화" "설계" "테스트" "프로젝트")
for label in "${LABELS[@]}"; do
  gh label create "$label" -c "0075ca" 2>/dev/null
done

TYPES=("type:업무" "type:개발-기능" "type:문서화" "type:테스트" "type:설계" "type:프로젝트")
for type in "${TYPES[@]}"; do
  gh label create "$type" -c "d73a4a" 2>/dev/null
done

echo "라벨 세팅이 완료되었습니다. 부모-자식 구조 이슈 생성을 시작합니다..."
echo "======================================================"

# WBS 데이터 
ISSUES="
1. 환경 및 구조 세팅|1.1 GitHub 세팅|1.1.1 GitHub Repo, Projects 보드(Kanban) 세팅|type:프로젝트|프로젝트
1. 환경 및 구조 세팅|1.1 GitHub 세팅|1.1.2 이슈(Issue) 목록 생성 및 PR 템플릿 등록|type:프로젝트|프로젝트
1. 환경 및 구조 세팅|1.2 CLI 뼈대 및 설정 환경|1.2.1 argparse 기반 CLI 서브커맨드 6개 뼈대 작성|type:설계|개발
1. 환경 및 구조 세팅|1.2 CLI 뼈대 및 설정 환경|1.2.2 초기 설정 여부 검사 로직(check_setup) 구현|type:개발-기능|개발
1. 환경 및 구조 세팅|1.2 CLI 뼈대 및 설정 환경|1.2.3 대화형(PC 통신 스타일) 설정 환경 UI 구현|type:개발-기능|개발
1. 환경 및 구조 세팅|1.3 저장소 계층 (하이브리드)|1.3.1 raw 저장소 (JSONL) append 로직 구현|type:개발-기능|db
1. 환경 및 구조 세팅|1.3 저장소 계층 (하이브리드)|1.3.2 clean 저장소 (SQLite) 스키마 DDL 작성|type:설계|db
1. 환경 및 구조 세팅|1.3 저장소 계층 (하이브리드)|1.3.3 SQLite 중복 처리 (upsert 정책) 로직 구현|type:개발-기능|db
2. 핵심 파이프라인 개발|2.1 데이터 수집 (fetch)|2.1.1 RSS 피드 XML 파싱 및 딕셔너리 추출|type:개발-기능|개발
2. 핵심 파이프라인 개발|2.1 데이터 수집 (fetch)|2.1.2 통신 타임아웃 방어 및 HTTP 에러 예외 처리|type:개발-기능|개발
2. 핵심 파이프라인 개발|2.1 데이터 수집 (fetch)|2.1.3 수집 시각, 소스 메타데이터와 함께 raw 저장|type:개발-기능|db
2. 핵심 파이프라인 개발|2.2 데이터 정제 (clean)|2.2.1 raw 읽기, 빈칸 제거 및 HTML 태그 정제|type:개발-기능|개발
2. 핵심 파이프라인 개발|2.2 데이터 정제 (clean)|2.2.2 날짜 형식 통일 (YYYY-MM-DD) 및 결측값 예외처리|type:개발-기능|개발
2. 핵심 파이프라인 개발|2.2 데이터 정제 (clean)|2.2.3 skip/upsert 설정 분기 및 SQLite 최종 저장|type:개발-기능|db
2. 핵심 파이프라인 개발|2.3 AI 연동 (summarize)|2.3.1 LLM SDK 연동 (Gemini/OpenAI 등 분기 처리)|type:개발-기능|ai
2. 핵심 파이프라인 개발|2.3 AI 연동 (summarize)|2.3.2 3줄 요약 프롬프트 튜닝 및 API 통신|type:업무|ai
2. 핵심 파이프라인 개발|2.3 AI 연동 (summarize)|2.3.3 --unsummarized 플래그 적용 및 결과 DB 업데이트|type:개발-기능|db
2. 핵심 파이프라인 개발|2.4 인사이트 도출 (analyze)|2.4.1 분석 기간(date-from) 및 카테고리 필터링 쿼리|type:개발-기능|db
2. 핵심 파이프라인 개발|2.4 인사이트 도출 (analyze)|2.4.2 프롬프트: 트렌드, 키워드, 시사점 추출 요청|type:개발-기능|ai
3. 리포팅 및 보너스 과제|3.1 시각화 및 리포트 (report)|3.1.1 matplotlib 2종 차트 생성 (카테고리별, 일자별)|type:개발-기능|개발
3. 리포팅 및 보너스 과제|3.1 시각화 및 리포트 (report)|3.1.2 품질 지표(정제율, 성공률) 및 TOP N 집계 SQL 구현|type:개발-기능|db
3. 리포팅 및 보너스 과제|3.1 시각화 및 리포트 (report)|3.1.3 콘솔 UI 포맷 및 텍스트 리포트 파일 저장 처리|type:개발-기능|개발
3. 리포팅 및 보너스 과제|3.2 내보내기 (export)|3.2.1 CSV/Excel/JSONL 파일 저장 로직 및 포맷팅|type:개발-기능|개발
3. 리포팅 및 보너스 과제|3.3 보너스 과제|3.3.1 CLI 데이터 탐색(list, show) 페이징/상세조회 구현|type:개발-기능|개발
3. 리포팅 및 보너스 과제|3.3 보너스 과제|3.3.2 감성 분석 AI 연동 및 차트 결과물 반영|type:개발-기능|ai
4. QA 및 최종 마감|4.1 품질 보증 (QA)|4.1.1 과제목표 검증 시나리오 5종 (장단점 비교, 에러 처리 등)|type:설계|테스트
4. QA 및 최종 마감|4.1 품질 보증 (QA)|4.1.2 설정 파일 파괴 테스트 및 크래시(Crash) 검증|type:테스트|테스트
4. QA 및 최종 마감|4.2 문서화 (Docs)|4.2.1 프로젝트 아키텍처 및 파이프라인 흐름도 정리|type:문서화|문서화
4. QA 및 최종 마감|4.2 문서화 (Docs)|4.2.2 자동화 스케줄링(cron) 가이드라인 문서화|type:문서화|문서화
4. QA 및 최종 마감|4.2 문서화 (Docs)|4.2.3 최종 버그 리팩토링 및 main 브랜치 머지|type:업무|프로젝트
"

CURRENT_DEPTH1=""
PARENT_ID=""
CHILD_TASKS=""

# 부모 이슈에 자식 이슈 체크리스트를 묶어서 업데이트하는 함수
update_parent_issue() {
  if [ -n "$PARENT_ID" ]; then
    echo ">> 🔄 부모 이슈(#$PARENT_ID)에 자식 이슈들을 연결(Tasklist)합니다..."
    gh issue edit "$PARENT_ID" --body "## 🚩 $CURRENT_DEPTH1
이 단계(Phase)에 포함된 세부 작업(Task) 목록입니다. 각 이슈를 완료(Close)하면 진척도(%)가 자동으로 올라갑니다.

$CHILD_TASKS"
    sleep 1
  fi
}

# 데이터를 한 줄씩 읽으며 처리
while IFS='|' read -r depth1 depth2 depth3 type label; do
  if [ -n "$depth3" ]; then
    
    # 1. 1-Depth가 바뀔 때마다 새로운 부모 이슈 먼저 생성
    if [ "$CURRENT_DEPTH1" != "$depth1" ]; then
      # 이전 그룹이 있었다면 Tasklist 업데이트 실행
      update_parent_issue
      
      CURRENT_DEPTH1="$depth1"
      CHILD_TASKS=""
      
      echo ">> 📁 부모 이슈(1-Depth) 생성 중: $depth1"
      PARENT_URL=$(gh issue create --title "🚀 [Phase] $depth1" --body "생성 중..." --label "type:프로젝트" --label "프로젝트")
      PARENT_ID=${PARENT_URL##*/}
      sleep 1.5
    fi
    
    # 2. 자식 이슈(2-Depth, 3-Depth) 생성
    ISSUE_TITLE="[$depth2] $depth3"
    ISSUE_BODY="### 📌 작업 그룹
* **Phase (1-Depth):** $depth1
* **Group (2-Depth):** $depth2

### 📋 세부 작업 내용
- $depth3

### 🔗 상위(부모) 이슈
* Tracked by #$PARENT_ID"

    echo "  >> 📄 자식 이슈 생성 중: $ISSUE_TITLE"
    CHILD_URL=$(gh issue create --title "$ISSUE_TITLE" --body "$ISSUE_BODY" --label "$type" --label "$label")
    CHILD_ID=${CHILD_URL##*/}
    
    # 3. 부모 이슈 업데이트를 위해 자식 이슈 번호(#ID) 누적 저장
    CHILD_TASKS="${CHILD_TASKS}- [ ] #${CHILD_ID}"$'\n'
    
    sleep 1.5
  fi
done <<< "$ISSUES"

# 반복문 종료 후 마지막 그룹 업데이트
update_parent_issue

echo "======================================================"
echo "모든 WBS 이슈가 부모-자식 관계로 완벽하게 등록되었습니다!"
