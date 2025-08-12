FROM python:3.10-slim

ARG TARGETARCH

RUN apt-get update && apt-get install -y wget gnupg ca-certificates --no-install-recommends \
    && if [ "$TARGETARCH" = "amd64" ]; then \
        echo "Installing Google Chrome for amd64"; \
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg; \
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list; \
        apt-get update && apt-get install -y google-chrome-stable --no-install-recommends; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        echo "Installing Chromium and Chromium-driver for arm64"; \
        apt-get update && apt-get install -y chromium chromium-driver --no-install-recommends; \
    fi \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]