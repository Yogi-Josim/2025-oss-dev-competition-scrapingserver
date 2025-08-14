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
    && rm -rf /var/lib/apt/lists/*

RUN if [ "$TARGETARCH" = "amd64" ]; then \
        echo "Installing chromium-driver for amd64 via apt-get..."; \
        apt-get update && apt-get install -y chromium-driver --no-install-recommends && rm -rf /var/lib/apt/lists/*; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        echo "Downloading and installing chromedriver for arm64 manually..."; \
        CHROME_DRIVER_VERSION=$(wget -q -O - https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/LATEST_RELEASE_STABLE); \
        wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux-arm64/chromedriver-linux-arm64.zip" -P /tmp; \
        unzip /tmp/chromedriver-linux-arm64.zip -d /usr/bin; \
        chmod +x /usr/bin/chromedriver; \
        rm /tmp/chromedriver-linux-arm64.zip; \
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
