FROM seleniarm/standalone-chromium:124.0-chromedriver-124.0

RUN apt-get update && apt-get install -y python3 python3-pip

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]