FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TERM=xterm-256color \
    PYTHONPATH=/app/src

# 1. 시스템 패키지 및 Chromium 설치 (아키텍처 충돌 없는 Debian 공식 패키지 사용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-nanum \
    cron \
    wget \
    unzip \
    ca-certificates \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. 파이썬 라이브러리 복사 및 설치 (사용자님의 기존 경로 유지)
COPY ../src/requirements.txt .
COPY ../src/requirements-dev.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-dev.txt

# 3. 소스 코드 복사
COPY src/ ./src/

# 4. 로그 폴더 생성, 크론 등록 및 진입점 설정
RUN mkdir -p /app/logs \
    && echo "*/10 * * * * /bin/bash /app/script/scheduled_fetch.sh >> /app/logs/cron_fetch.log 2>&1\n" > /etc/cron.d/codyssey-cron \
    && chmod 0644 /etc/cron.d/codyssey-cron \
    && crontab /etc/cron.d/codyssey-cron \
    && echo '#!/bin/bash\nservice cron start\nexec "$@"' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

WORKDIR /app/src

ENTRYPOINT ["/app/entrypoint.sh"]

# 대화형 환경 진입
CMD ["/bin/bash"]