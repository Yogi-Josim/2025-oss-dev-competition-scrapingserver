FROM python:3.10-bullseye

RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libgtk-3-0 libasound2 \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# requirements.txt에 webdriver-manager가 이미 포함되어 있습니다.
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
