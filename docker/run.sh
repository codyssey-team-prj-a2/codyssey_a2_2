#!/bin/bash

# /run.sh
set -e

# docker-compose 파일 및 해시 파일 위치 지정
COMPOSE_FILE="docker-compose.yml"
HASH_FILE=".build_hash"

# 빌드 관련 파일들의 해시(체크섬) 계산 함수 (Mac / Linux 공용)
calc_hash() {
    local files="Dockerfile $COMPOSE_FILE ../src/requirements.txt requirements.txt"
    if command -v md5sum > /dev/null 2>&1; then
        cat $files 2>/dev/null | md5sum | awk '{print $1}'
    elif command -v md5 > /dev/null 2>&1; then
        cat $files 2>/dev/null | md5
    else
        echo "none"
    fi
}

CURRENT_HASH=$(calc_hash)
IMAGE_ID=$(docker compose -f $COMPOSE_FILE images -q app 2>/dev/null || true)

# 1. 사용자가 명시적으로 './run.sh build'를 입력한 경우
if [ "$1" == "build" ]; then
    echo "🐳 [수동 빌드] Docker 이미지를 새로 빌드합니다..."
    docker compose -f $COMPOSE_FILE build
    echo "$CURRENT_HASH" > "$HASH_FILE"
    shift
# 2. 이미지가 로컬에 없거나 해시 파일이 없는 경우 (최초 실행)
elif [ -z "$IMAGE_ID" ] || [ ! -f "$HASH_FILE" ]; then
    echo "📦 Docker 이미지가 없거나 최초 실행입니다. 빌드를 진행합니다..."
    docker compose -f $COMPOSE_FILE build
    echo "$CURRENT_HASH" > "$HASH_FILE"
# 3. 설정 파일(Dockerfile, requirements.txt 등)의 변경사항이 감지된 경우
elif [ "$CURRENT_HASH" != "none" ] && [ "$CURRENT_HASH" != "$(cat "$HASH_FILE" 2>/dev/null)" ]; then
    echo "🔄 빌드 설정(Dockerfile / 의존성 파일) 변경 감지! 이미지를 다시 빌드합니다..."
    docker compose -f $COMPOSE_FILE build
    echo "$CURRENT_HASH" > "$HASH_FILE"
else
    echo "✅ 변경사항 없음: 기존 Docker 이미지를 그대로 사용합니다."
fi

# 인자 실행 분기
if [ $# -gt 0 ]; then
    echo "🚀 [명령어 실행] $@"
    docker compose -f $COMPOSE_FILE run --rm --remove-orphans app "$@"
else
    echo "📺 [Docker 대화형 터미널 접속]..."
    docker compose -f $COMPOSE_FILE run --rm --remove-orphans app /bin/bash
fi