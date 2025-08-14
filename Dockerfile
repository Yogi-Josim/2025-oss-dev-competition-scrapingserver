# =================================================================
# 스테이지 1: 모든 아키텍처의 Chromedriver를 미리 다운로드하는 통합 스테이지
# =================================================================
FROM debian:bullseye-slim as builder
RUN apt-get update && apt-get install -y wget unzip --no-install-recommends && rm -rf /var/lib/apt/lists/*

# 각 아키텍처별 디렉토리 생성
RUN mkdir -p /drivers/amd64 && mkdir -p /drivers/arm64

# AMD64용 드라이버 다운로드 및 배치
RUN CHROME_DRIVER_VERSION_AMD64=$(wget -q -O - https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION_AMD64}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver-amd64.zip && \
    unzip /tmp/chromedriver-amd64.zip -d /tmp/amd64 && \
    mv /tmp/amd64/chromedriver-linux64/chromedriver /drivers/amd64/chromedriver && \
    rm -rf /tmp/*

# ARM64용 드라이버 다운로드 및 배치
RUN CHROME_DRIVER_VERSION_ARM64=$(wget -q -O - https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION_ARM64}/linux-arm64/chromedriver-linux-arm64.zip" -O /tmp/chromedriver-arm64.zip && \
    unzip /tmp/chromedriver-arm64.zip -d /tmp/arm64 && \
    mv /tmp/arm64/chromedriver-linux-arm64/chromedriver /drivers/arm64/chromedriver && \
    rm -rf /tmp/*

# =================================================================
# 최종 어플리케이션 이미지 빌드 스테이지
# =================================================================
FROM python:3.10-bullseye

# 기본 의존성 패키지 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Chromium 브라우저 설치
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Docker가 빌드 시점에 자동으로 채워주는 아키텍처 변수 선언
ARG TARGETARCH

# [수정] 통합 빌더 스테이지에서 아키텍처에 맞는 드라이버를 복사
COPY --from=builder /drivers/${TARGETARCH}/chromedriver /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
