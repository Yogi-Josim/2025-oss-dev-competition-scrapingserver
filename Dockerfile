FROM python:3.10-bullseye

# 기본 의존성 패키지 설치 (wget, unzip, jq 포함)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    wget unzip jq \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Docker 빌드 아키텍처 변수
ARG TARGETARCH

# Chromium 브라우저 설치
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Chromedriver 설치 (모든 아키텍처에서 직접 다운로드)
# [수정] 안정적인 JSON 엔드포인트와 jq 파서를 사용하여 다운로드 안정성을 대폭 향상시켰습니다.
RUN set -ex; \
    \
    # 아키텍처에 따라 플랫폼 변수 설정
    if [ "$TARGETARCH" = "amd64" ]; then \
        DRIVER_PLATFORM="linux64"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        DRIVER_PLATFORM="linux-arm64"; \
    else \
        echo "Unsupported architecture: $TARGETARCH" >&2; \
        exit 1; \
    fi; \
    \
    # JSON 엔드포인트에서 다운로드 URL 확인 (5회 재시도)
    for i in $(seq 1 5); do \
        JSON_DATA=$(wget -q -O - --no-check-certificate https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json); \
        DOWNLOAD_URL=$(echo "$JSON_DATA" | jq -r --arg plat "$DRIVER_PLATFORM" '.versions[-1].downloads.chromedriver[] | select(.platform==$plat).url'); \
        [ -n "$DOWNLOAD_URL" ] && [ "$DOWNLOAD_URL" != "null" ] && break; \
        echo "Failed to get download URL, retrying in 5s... (${i}/5)"; \
        sleep 5; \
    done; \
    if [ -z "$DOWNLOAD_URL" ] || [ "$DOWNLOAD_URL" = "null" ]; then echo "Could not get download URL after 5 retries." >&2; exit 1; fi; \
    \
    echo "Downloading ChromeDriver for ${TARGETARCH} from ${DOWNLOAD_URL}..."; \
    \
    # 드라이버 다운로드 (5회 재시도)
    for i in $(seq 1 5); do \
        wget -q --no-check-certificate -O /tmp/chromedriver.zip "$DOWNLOAD_URL" && break; \
        echo "Download failed, retrying in 5s... (${i}/5)"; \
        sleep 5; \
    done; \
    if [ ! -f /tmp/chromedriver.zip ]; then echo "Failed to download driver after 5 retries." >&2; exit 1; fi; \
    \
    # 압축 해제 및 설치
    unzip -q /tmp/chromedriver.zip -d /tmp; \
    mv /tmp/chromedriver-*/chromedriver /usr/bin/chromedriver; \
    chmod +x /usr/bin/chromedriver; \
    rm -rf /tmp/*; \
    echo "ChromeDriver installed successfully.";

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
