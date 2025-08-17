# =================================================================
# Stage 1: Builder
# 크롬 브라우저와 드라이버를 다운로드하고 준비하는 역할만 담당합니다.
# 이 단계는 내용이 바뀌지 않는 한 캐시되어 재사용됩니다.
# =================================================================
FROM python:3.10-slim AS builder

# 다운로드에 필요한 최소한의 도구만 설치합니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 빌드 환경의 아키텍처를 인자로 받습니다.
ARG TARGETARCH

# 아키텍처에 따라 다른 URL에서 크롬과 크롬 드라이버를 다운로드하고 압축을 해제합니다.
RUN CHROME_VERSION=$(wget -q -O - https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | grep -oP '"linux64":.*?"version": "\K[^"]+') && \
    if [ "$TARGETARCH" = "arm64" ]; then \
        CHROME_URL=$(wget -q -O - https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | grep -oP '"chrome", "platform": "linux-arm64", "url": "\K[^"]+'); \
        DRIVER_URL=$(wget -q -O - https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | grep -oP '"chromedriver", "platform": "linux-arm64", "url": "\K[^"]+'); \
    else \
        CHROME_URL=$(wget -q -O - https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | grep -oP '"chrome", "platform": "linux64", "url": "\K[^"]+'); \
        DRIVER_URL=$(wget -q -O - https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | grep -oP '"chromedriver", "platform": "linux64", "url": "\K[^"]+'); \
    fi && \
    wget -O chrome.zip $CHROME_URL && \
    wget -O chromedriver.zip $DRIVER_URL && \
    unzip chrome.zip && \
    unzip chromedriver.zip

# =================================================================
# Stage 2: Final Image
# 실제 애플리케이션이 실행될 최종 환경입니다.
# =================================================================
FROM python:3.10-slim

WORKDIR /app

# 헤드리스 크롬 실행에 필요한 최소한의 라이브러리만 설치합니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libnss3 libgconf-2-4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libgtk-3-0 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# [핵심 수정] Builder 스테이지에서 준비된 파일을 복사할 때, 와일드카드(*)를 사용하여
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
