# script/scheduled_fetch.ps1
#
# Windows 작업 스케줄러에서 비대화형으로 뉴스 수집을 자동 실행하기 위한 래퍼.
# scheduled_fetch.sh(Mac/Linux cron)와 동일한 명령을 PowerShell로 옮긴 것.
# `-T`(pseudo-tty 비활성화)를 붙여서 로그온 세션 없이(트리거로) 실행돼도
# 안전하게 동작하게 한다. Docker Desktop이 미리 실행 중이어야 한다.
#
# main.py가 아니라 automation.py를 실행한다 — main.py/setup.py는 팀과의 합의로
# 건드리지 않기로 했기 때문에, 비대화형 진입점을 별도 파일(src/automation.py)로
# 분리했다(documentation/result/7.정기실행_스케줄링_가이드.md 참고).

$ErrorActionPreference = "Stop"

$DockerDir = Join-Path $PSScriptRoot "..\docker"
Set-Location $DockerDir

docker compose -f docker-compose.yml run --rm -T app python3 automation.py fetch --source all --limit 20
if ($LASTEXITCODE -ne 0) {
    throw "fetch 실행 실패 (exit code $LASTEXITCODE)"
}

# 수집 뒤 정제까지 자동으로 이어서 하고 싶으면 아래 줄의 주석을 해제한다.
# (summarize/analyze/sentiment는 AI API 쿼터를 쓰므로 기본값으로는 자동 실행하지 않음)
# docker compose -f docker-compose.yml run --rm -T app python3 automation.py clean
