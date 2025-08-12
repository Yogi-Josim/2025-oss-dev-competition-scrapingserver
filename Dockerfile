# scraper-api-repo/Dockerfile

FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    curl \
    --no-install-recommends \
    && apt-get -y install google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app 폴더 전체를 컨테이너의 /app/app 경로로 복사
COPY ./app /app/app

EXPOSE 8000

# uvicorn 실행 경로를 app.main의 app 객체로 지정
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]