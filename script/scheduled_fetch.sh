#!/bin/bash
# script/scheduled_fetch.sh
#
# cron 등 비대화형(터미널 없는) 환경에서 뉴스 수집을 자동 실행하기 위한 래퍼.
# main.py가 아니라 automation.py를 실행한다 — main.py/setup.py는 팀과의 합의로
# 건드리지 않기로 했기 때문에, 비대화형 진입점을 별도 파일(src/automation.py)로
# 분리했다(documentation/result/7.정기실행_스케줄링_가이드.md 참고).
#
# 대화형 접속용 docker/run.sh와 거의 같지만, `-T`(pseudo-tty 비활성화)를 붙여서
# 터미널이 없는 스케줄러(cron/launchd)에서 실행해도 "the input device is not
# a TTY" 오류가 나지 않게 한다. cron/launchd는 로그인 셸과 PATH가 달라 `docker`
# 명령을 못 찾을 수 있으므로, 필요하면 DOCKER_BIN 환경변수로 절대경로를 지정한다
# (예: DOCKER_BIN=/usr/local/bin/docker).
set -e

DOCKER_BIN="${DOCKER_BIN:-docker}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/../docker"

cd "$DOCKER_DIR"
"$DOCKER_BIN" compose -f docker-compose.yml run --rm -T app python3 automation.py fetch --source all --limit 20

# 수집 뒤 정제까지 자동으로 이어서 하고 싶으면 아래 줄의 주석을 해제한다.
# (summarize/analyze/sentiment는 AI API 쿼터를 쓰므로 기본값으로는 자동 실행하지 않음)
# "$DOCKER_BIN" compose -f docker-compose.yml run --rm -T app python3 automation.py clean
