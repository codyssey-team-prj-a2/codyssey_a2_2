#!/bin/bash

# /run.sh
set -e

# docker-compose 파일 위치 지정 변수
COMPOSE_FILE="docker-compose.yml"

# 빌드 옵션
if [ "$1" == "build" ]; then
    echo "🐳 Docker 이미지를 빌드합니다..."
    docker compose -f $COMPOSE_FILE build
    shift
fi

# 인자 실행 분기
if [ $# -gt 0 ]; then
    echo "🚀 [명령어 실행] $@"
    docker compose -f $COMPOSE_FILE run --rm --remove-orphans app "$@"
else
    echo "📺 [Docker 대화형 터미널 접속]..."
    docker compose -f $COMPOSE_FILE run --rm --remove-orphans app /bin/bash
fi