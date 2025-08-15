FROM python:3.10-bullseye

# 기본 의존성 패키지 설치
# Playwright가 필요로 하는 라이브러리들을 포함합니다.
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# [수정] requirements.txt에 playwright를 추가해야 합니다.
# playwright를 설치합니다.
RUN pip install --no-cache-dir -r requirements.txt && pip install playwright

# [수정] Playwright가 필요한 브라우저(chromium)를 직접 설치하도록 합니다.
# 이 한 줄이 모든 드라이버 버전/경로 문제를 해결합니다.
RUN playwright install chromium

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
