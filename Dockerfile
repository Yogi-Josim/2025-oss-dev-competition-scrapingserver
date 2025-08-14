FROM python:3.10-bullseye

# 기본 의존성 패키지 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    curl unzip \
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
# 'set -e'로 스크립트 실행 중 오류 발생 시 즉시 중단시킵니다.
RUN set -e; \
    \
    # 아키텍처에 따라 변수 설정
    if [ "$TARGETARCH" = "amd64" ]; then \
        DRIVER_ARCH="linux64"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        DRIVER_ARCH="linux-arm64"; \
    else \
        echo "Unsupported architecture: $TARGETARCH"; \
        exit 1; \
    fi; \
    \
    # 최신 드라이버 버전 확인
    CHROME_DRIVER_VERSION=$(curl -sSL https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE); \
    echo "Downloading ChromeDriver v${CHROME_DRIVER_VERSION} for ${TARGETARCH}..."; \
    \
    # 드라이버 다운로드 및 설치
    curl -sSL "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/${DRIVER_ARCH}/chromedriver-${DRIVER_ARCH}.zip" -o /tmp/chromedriver.zip; \
    unzip -q /tmp/chromedriver.zip -d /tmp; \
    mv "/tmp/chromedriver-${DRIVER_ARCH}/chromedriver" /usr/bin/chromedriver; \
    chmod +x /usr/bin/chromedriver; \
    \
    # 임시 파일 정리
    rm /tmp/chromedriver.zip; \
    rm -rf "/tmp/chromedriver-${DRIVER_ARCH}";

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
