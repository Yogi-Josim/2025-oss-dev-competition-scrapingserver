# =================================================================
# Stage 1: Builder
# 크롬 브라우저와 드라이버를 다운로드하고 준비하는 역할만 담당합니다.
# 이 단계는 내용이 바뀌지 않는 한 캐시되어 재사용됩니다.
# =================================================================
FROM python:3.10-slim AS builder

# [수정] 다운로드 스크립트의 안정성을 위해 JSON 파서(jq)를 추가로 설치합니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    unzip \
    jq \
    && rm -rf /var/lib/apt/lists/*

# 빌드 환경의 아키텍처를 인자로 받습니다.
ARG TARGETARCH

# [수정] 불안정한 grep 대신, 표준 JSON 파서인 jq를 사용하여 다운로드 URL을 안정적으로 추출합니다.
RUN JSON_URL="https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" && \
    if [ "$TARGETARCH" = "arm64" ]; then \
        PLATFORM="linux-arm64"; \
    else \
        PLATFORM="linux64"; \
    fi && \
    CHROME_URL=$(wget -qO- $JSON_URL | jq -r ".channels.Stable.downloads.chrome[] | select(.platform==\"$PLATFORM\") | .url") && \
    DRIVER_URL=$(wget -qO- $JSON_URL | jq -r ".channels.Stable.downloads.chromedriver[] | select(.platform==\"$PLATFORM\") | .url") && \
    wget -O chrome.zip "$CHROME_URL" && \
    wget -O chromedriver.zip "$DRIVER_URL" && \
    unzip chrome.zip && \
    unzip chromedriver.zip

# =================================================================
# Stage 2: Final Image
# 실제 애플리케이션이 실행될 최종 환경입니다.
# =================================================================
FROM python:3.10-slim

WORKDIR /app

# 헤드리스 크롬 실행에 필요한 최소한의 라이브러리 목록입니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Builder 스테이지에서 준비된 파일을 복사할 때, 와일드카드(*)를 사용하여
# arm64와 amd64 환경 모두에서 올바른 폴더를 찾도록 수정했습니다.
COPY --from=builder /chrome-*/chrome /usr/local/bin/
COPY --from=builder /chromedriver-*/chromedriver /usr/local/bin/

# requirements.txt 파일을 컨테이너에 복사합니다.
COPY requirements.txt .

# requirements.txt에 명시된 패키지들을 설치합니다.
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 코드를 컨테이너에 복사합니다.
COPY ./app /app/app

# 8000번 포트를 외부에 노출하도록 설정합니다.
EXPOSE 8000

# 컨테이너가 시작될 때 실행할 명령어를 정의합니다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
