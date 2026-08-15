#!/bin/bash
# /script/scheduled_fetch.sh

# cron 환경은 기본 환경변수가 없으므로 명시적 지정
export PYTHONPATH=/app/src
export PYTHONUNBUFFERED=1

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 정기 뉴스 수집 스케줄러 작동 시작"

cd /app/src

# 비대화형(automation.py) 파일로 수집 명령 실행
/usr/local/bin/python3 automation.py fetch --source all --limit 20