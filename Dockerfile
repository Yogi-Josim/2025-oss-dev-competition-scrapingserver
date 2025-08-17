# =================================================================
# Stage 1: Base with OS Dependencies (20분 걸리는 무거운 작업)
# 이 단계는 내용이 바뀌지 않는 한, 캐시에 저장되어 재사용됩니다.
# =================================================================
FROM python:3.10-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# =================================================================
# Stage 2: Python Dependencies
# requirements.txt 파일이 바뀌지 않는 한, 이 단계도 캐시됩니다.
# =================================================================
FROM base AS python-deps

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =================================================================
# Stage 3: Final Image (매우 빠른 최종 조립)
# 파이썬 코드만 복사하므로, 이 단계는 몇 초 안에 끝납니다.
# =================================================================
FROM python-deps

WORKDIR /app
COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
