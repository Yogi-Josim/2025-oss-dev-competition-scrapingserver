FROM python:3.10-bullseye

# 기본 의존성 패키지 설치 (curl, unzip 포함)
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
# 이 방법은 apt-get의 불안정성을 피하고, 두 아키텍처 모두에 일관된 설치를 보장합니다.
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
    CHROME_DRIVER_VERSION=$(curl -sSL https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE); \
    echo "Downloading ChromeDriver v${CHROME_DRIVER_VERSION} for ${TARGETARCH}..."; \
    \
    curl -sSL "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/${DRIVER_ARCH}/chromedriver-${DRIVER_ARCH}.zip" -o /tmp/chromedriver.zip; \
    unzip -q /tmp/chromedriver.zip -d /tmp; \
    mv "/tmp/chromedriver-${DRIVER_ARCH}/chromedriver" /usr/bin/chromedriver; \
    chmod +x /usr/bin/chromedriver; \
    \
    rm -rf /tmp/*;

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
