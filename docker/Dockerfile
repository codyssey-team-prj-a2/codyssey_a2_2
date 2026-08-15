# /docker/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    fonts-nanum \
    cron \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TERM=xterm-256color \
    PYTHONPATH=/app/src

WORKDIR /app

# 컨텍스트가 루트(project_root)이므로 src/ 내의 파일 경로를 명시
COPY ../src/requirements.txt .
COPY ../src/requirements-dev.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# 루트에 있는 src 폴더 전체 복사
COPY src/ ./src/

# 2. 10분마다 실행되는 크론탭 파일 생성 및 등록 (스크립트명 변경 반영, 마지막 개행 \n 필수)
RUN echo "*/10 * * * * /bin/bash /app/script/scheduled_fetch.sh >> /app/logs/cron_fetch.log 2>&1\n" > /etc/cron.d/codyssey-cron
RUN chmod 0644 /etc/cron.d/codyssey-cron && crontab /etc/cron.d/codyssey-cron

# 3. 컨테이너 실행 시 cron 서비스를 시작하게 만드는 진입점(Entrypoint) 설정
RUN echo '#!/bin/bash\nservice cron start\nexec "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

WORKDIR /app/src

ENTRYPOINT ["/app/entrypoint.sh"]

# 대화형 환경 진입
CMD ["/bin/bash"]