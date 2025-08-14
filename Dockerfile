FROM python:3.10-bullseye

RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    wget gnupg ca-certificates unzip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# chromium 브라우저만 apt로 설치하고, chromedriver는 직접 다운로드
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && CHROME_DRIVER_VERSION=$(wget -q -O - https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE) \
    && echo "Latest Stable ChromeDriver version: $CHROME_DRIVER_VERSION" \
    && wget -q https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip -P /tmp \
    && unzip /tmp/chromedriver-linux64.zip -d /tmp \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm /tmp/chromedriver-linux64.zip \
    && rm -rf /tmp/chromedriver-linux64

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
