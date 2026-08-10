# codyssey_a2_2

---

## 코디세이 팀프로젝트A2_2 News project

---

## History

8/10 23:40 - 각종 문서 업로드 (Staging)

### staging 에 있는 내용을 dev-\* 로 가져오려면

    * 본인이 하던 업무를 저장 git add/commit
        * 만약에 commit 하기 애매하면 지우거나 git stash 로 잠깐 임시 저장소에 넣고 진행한다.
    * git fetch origin (staging 의 최신 정보 가져오기)
    * git pull origin staging  (staging 에 있는 정보 가져오기)

### 작업한 내용을 staging 으로 옮기려면

    * dev-* 각자 branch 에서 작업 후 (add/commit)
    * staging 으로 branch 변경
    * 누군가 staging 에 데이터를 업데이트 했을 수 있으니 git pull origin staging 으로 staging 동기화
    * git merge dev-* 자신의 branch merge
    * git push origin staging  으로 최종 반영

---

## 디렉토리 구조

- documentation
  - project - 프로젝트 진행 과정에 필요한 문서
  - result - 산출물
    - 요구사항 관련 산출물
    - 필수 제출 산출물
    - 테스트 시트
  - test - 테스트시트
- images - 캡쳐 이미지들
- src - 개발 코드

---

## R&R (1차)

- 프로젝트 진행 (일정관리, 진행관련 문서화) : 박순몽
- 로직 설계, 리뷰 및 관련 내용 보정 : 박순몽
- 개발 : 김병국, 이원일
- 개발관련 문서 : 김병국
- 테스트 및 시트작성, 피드백 : 김정진
- 미팅록 작성(프로젝트 관련 미팅 시 의사결정 내용 리스트 작성) : 김정진

---

## 일정 (draft)

- 5 : 미팅
- 6-7 : 환경 셋팅(WBS, 간트 차트 작성), 과업숙지
- 8-9 : 개별 수행, 로직 및 구조 확정
- 10-12 : 집중 업무 수행
- 13 : 최종 통합 테스트 수행 및 결과
