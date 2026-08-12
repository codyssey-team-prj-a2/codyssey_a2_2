# /docker/Dockerfile
FROM python:3.12-slim

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

WORKDIR /app/src

# 대화형 환경 진입
CMD ["/bin/bash"]