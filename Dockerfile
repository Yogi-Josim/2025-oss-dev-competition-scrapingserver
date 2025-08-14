# =================================================================
# 스테이지 1: 각 아키텍처용 Chromedriver 압축 파일을 '다운로드만' 하는 스테이지
# =================================================================
# [수정] 더 안정적인 buildpack-deps 이미지를 사용하고 curl로 교체
FROM buildpack-deps:bullseye-curl as builder

# 각 아키텍처별 zip 파일을 저장할 디렉토리 생성
RUN mkdir -p /drivers

# AMD64용 드라이버 zip 다운로드
RUN CHROME_DRIVER_VERSION_AMD64=$(curl -sSL https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    curl -sSL "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION_AMD64}/linux64/chromedriver-linux64.zip" -o /drivers/amd64.zip

# ARM64용 드라이버 zip 다운로드
RUN CHROME_DRIVER_VERSION_ARM64=$(curl -sSL https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    curl -sSL "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION_ARM64}/linux-arm64/chromedriver-linux-arm64.zip" -o /drivers/arm64.zip

# =================================================================
# 최종 어플리케이션 이미지 빌드 스테이지
# =================================================================
FROM python:3.10-bullseye

# 기본 의존성 패키지 및 unzip 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    unzip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Chromium 브라우저 설치
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Docker가 빌드 시점에 자동으로 채워주는 아키텍처 변수 선언
ARG TARGETARCH

# 빌더 스테이지에서 아키텍처에 맞는 'zip' 파일을 복사
COPY --from=builder /drivers/${TARGETARCH}.zip /tmp/chromedriver.zip

# 복사된 zip 파일의 압축을 풀고 드라이버 설치
RUN unzip /tmp/chromedriver.zip -d /tmp/driver_unzipped && \
    mv /tmp/driver_unzipped/*/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/driver_unzipped

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
