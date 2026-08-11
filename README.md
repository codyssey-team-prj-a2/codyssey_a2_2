# codyssey_a2_2

---

## 코디세이 팀프로젝트A2_2 News project

---

## History

8/10 23:40 - 각종 문서 업로드 (Staging)  
8/11 03:00 - ui 설계 및 코드 템플릿 업로드  
8/12 12:51 - docker setting 완료

### 코드 템플릿 요점

```

docker 실행하기
    *  docker 디렉토리로 이동
    * ./run.sh 실행
    * python3 main.py 실행

```

```
main.py 는 라우터 기능만 함
각 lib 모듈을 호출하는 것은 아래와 같이 동일한 함수명으로 되어 있음
run_menu_show()

AI 에게 코드 생성 요청시 아래 조건을 같이 넣어주세요.
1. 파일명은 cli 명과 동일 clean -> lib/dev/clean.py
2. clean.py 내에 run_menu_show() 를 꼭 생성
3. 참고 파일은 lib/dev/fetch.py

빠진 명령어는 추가해주면 됩니다.

 if choice == '2': fetch.run_menu_show()
            elif choice == '3': clean.run_menu_show()
            elif choice == '4': summarize.run_menu_show()
            elif choice == '5': analyze.run_menu_show()
            elif choice == '6': report.run_menu_show()
            elif choice == '7': export.run_menu_show()
```

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

## 실행방법

- cd src/
- python3 main.py

---

## 디렉토리 구조

```text
📦 project_root
 ┣ 📂 documentation
 ┃ ┣ 📂 project            # 프로젝트 진행 과정에 필요한 문서
 ┃ ┗ 📂 result             # 산출물
 ┃   ┣ 📜 요구사항 관련 산출물
 ┃   ┣ 📜 필수 제출 산출물
 ┃   ┗ 📜 테스트 시트
 ┣ 📂 images               # 캡쳐 이미지들
 ┣ 📂 src                  # 개발 코드
 ┃ ┣ 📂 lib
 ┃ ┃ ┣ 📂 db               # [신규] DB 관련 파일 모음
 ┃ ┃ ┃ ┣ 📜 schema.sql     # [신규] 테이블 생성 쿼리 (DDL)
 ┃ ┃ ┃ ┗ 📜 sqlite_mgr.py  # [신규] DB 연결 및 실행 제어 모듈
 ┃ ┃ ┣ 📂 system
 ┃ ┃ ┃ ┣ 📜 config_mgr.py  # 환경 설정 제어
 ┃ ┃ ┃ ┗ 📜 ui.py          # 기본 UI, 색상 등
 ┃ ┃ ┣ 📂 common
 ┃ ┃ ┃ ┗ 📜 helpers.py     # 서브메뉴 헤더 생성, 공통 입력 프롬프트 등
 ┃ ┃ ┗ 📂 dev
 ┃ ┃   ┣ 📜 fetch.py       # 2. 수집 메뉴 화면 및 로직
 ┃ ┃   ┣ 📜 clean.py       # 3. 정제 메뉴 화면 및 로직
 ┃ ┃   ┣ 📜 summarize.py   # 4. 요약 메뉴 화면 및 로직
 ┃ ┃   ┣ 📜 analyze.py     # 5. 분석 메뉴 화면 및 로직
 ┃ ┃   ┣ 📜 report.py      # 6. 리포트 메뉴 화면 및 로직
 ┃ ┃   ┗ 📜 export.py      # 7. 데이터 내보내기 메뉴 및 로직
 ┃ ┗ 📜 main.py            # 라우터
 ┗ 📜 .gitignore           # Git 제외 설정
```

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

```

```
