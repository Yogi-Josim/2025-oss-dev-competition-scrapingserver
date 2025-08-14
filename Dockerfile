FROM python:3.10-bullseye

RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    wget gnupg ca-certificates unzip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH

RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && CHROME_DRIVER_VERSION=$(wget -q -O - https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE) \
    && echo "Latest Stable ChromeDriver version: $CHROME_DRIVER_VERSION for architecture: $TARGETARCH" \
    && if [ "$TARGETARCH" = "amd64" ]; then \
        DRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip"; \
        ZIP_FILE="chromedriver-linux64.zip"; \
        INNER_DIR="chromedriver-linux64"; \
       elif [ "$TARGETARCH" = "arm64" ]; then \
        DRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux-arm64/chromedriver-linux-arm64.zip"; \
        ZIP_FILE="chromedriver-linux-arm64.zip"; \
        INNER_DIR="chromedriver-linux-arm64"; \
       else \
        echo "Unsupported architecture: $TARGETARCH"; \
        exit 1; \
       fi \
    && wget -q "$DRIVER_URL" -P /tmp \
    && unzip "/tmp/$ZIP_FILE" -d /tmp \
    && mv "/tmp/$INNER_DIR/chromedriver" /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm "/tmp/$ZIP_FILE" \
    && rm -rf "/tmp/$INNER_DIR"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
