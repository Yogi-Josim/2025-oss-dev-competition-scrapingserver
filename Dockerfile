FROM python:3.10-bullseye

# 기본 의존성 패키지 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    wget unzip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Docker 빌드 아키텍처 변수
ARG TARGETARCH

# Chromium 브라우저 설치
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Chromedriver 설치
# 각 아키텍처에 맞는 가장 안정적인 방법으로 설치합니다.
RUN set -ex; \
    \
    # amd64의 경우, 구글에서 직접 다운로드합니다.
    if [ "$TARGETARCH" = "amd64" ]; then \
        echo "Downloading chromedriver for amd64..."; \
        CHROME_DRIVER_VERSION="126.0.6478.126"; \
        DOWNLOAD_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip"; \
        wget -q --no-check-certificate -O /tmp/chromedriver.zip "$DOWNLOAD_URL"; \
        unzip -q /tmp/chromedriver.zip -d /tmp; \
        mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver; \
    \
    # arm64의 경우, apt-get으로 설치하고 심볼릭 링크를 생성합니다.
    elif [ "$TARGETARCH" = "arm64" ]; then \
        echo "Installing chromium-driver for arm64 via apt-get..."; \
        apt-get update && apt-get install -y chromium-driver --no-install-recommends; \
        # [수정] -f (force) 옵션을 추가하여, 링크가 이미 존재하더라도 덮어쓰도록 합니다.
        ln -sf /usr/lib/chromium-driver/chromedriver /usr/bin/chromedriver; \
    \
    else \
        echo "Unsupported architecture: $TARGETARCH" >&2; \
        exit 1; \
    fi; \
    \
    # 임시 파일 정리 및 권한 설정
    chmod +x /usr/bin/chromedriver; \
    rm -rf /tmp/* /var/lib/apt/lists/*; \
    echo "ChromeDriver installed successfully for ${TARGETARCH}.";

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
