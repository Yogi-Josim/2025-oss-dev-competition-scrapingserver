# =================================================================
# 최종 안정화 버전
# =================================================================
FROM python:3.10-slim

# [핵심 수정] 복잡한 다운로드 스크립트를 모두 제거하고,
# Debian 공식 저장소에서 제공하는 가장 안정적이고 호환성이 보장된
# chromium과 chromium-driver를 직접 설치합니다.
# 이 방식은 arm64와 amd64 아키텍처를 자동으로 지원합니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

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
