FROM python:3.10-bullseye

# 1단계: 기본 의존성 패키지 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    wget gnupg ca-certificates unzip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Docker가 빌드 시점에 자동으로 채워주는 아키텍처 변수 선언
ARG TARGETARCH

# 2단계: Chromium 브라우저 설치 (별도 레이어)
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 3단계: 빌드 아키텍처에 따라 다른 방식으로 Chromedriver 설치
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        echo "Installing chromium-driver for amd64 via apt-get..."; \
        apt-get update && apt-get install -y chromium-driver --no-install-recommends && rm -rf /var/lib/apt/lists/*; \
        # [수정!] 파일 시스템 전체에서 드라이버를 찾아 심볼릭 링크 생성
        DRIVER_PATH=$(find / -name chromedriver 2>/dev/null | head -n 1); \
        if [ -n "$DRIVER_PATH" ]; then \
            echo "Chromedriver found at $DRIVER_PATH. Creating symlink..."; \
            ln -s "$DRIVER_PATH" /usr/bin/chromedriver; \
        else \
            echo "Chromedriver not found for amd64 after installation."; \
            exit 1; \
        fi; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        echo "Downloading and installing chromedriver for arm64 manually..."; \
        CHROME_DRIVER_VERSION=$(wget -q -O - https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE); \
        echo "Latest Stable ChromeDriver version: $CHROME_DRIVER_VERSION for architecture: $TARGETARCH"; \
        DRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux-arm64/chromedriver-linux-arm64.zip"; \
        ZIP_FILE="chromedriver-linux-arm64.zip"; \
        INNER_DIR="chromedriver-linux-arm64"; \
        wget -q "$DRIVER_URL" -P /tmp; \
        unzip "/tmp/$ZIP_FILE" -d /tmp; \
        mv "/tmp/$INNER_DIR/chromedriver" /usr/bin/chromedriver; \
        chmod +x /usr/bin/chromedriver; \
        rm "/tmp/$ZIP_FILE"; \
        rm -rf "/tmp/$INNER_DIR"; \
    else \
        echo "Unsupported architecture: $TARGETARCH"; \
        exit 1; \
    fi

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
