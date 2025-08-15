FROM python:3.10-bullseye

# [수정] 웹 브라우저 관련 의존성을 모두 제거하여 이미지를 가볍게 만듭니다.
RUN apt-get update && apt-get install -y \
    # 기본 실행에 필요한 최소한의 라이브러리만 남깁니다.
    libglib2.0-0 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
