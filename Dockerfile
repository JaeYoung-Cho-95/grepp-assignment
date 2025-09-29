# --- 베이스 이미지 설정
# Python 3.11 slim 이미지를 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# Python 환경 변수 설정
# PYTHONDONTWRITEBYTECODE=1: .pyc 파일 생성 방지
# PYTHONUNBUFFERED=1: Python 출력 버퍼링 비활성화
# PIP_DISABLE_PIP_VERSION_CHECK=1: pip 버전 체크 비활성화 
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# --- 라이브러리 설치
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# --- 애플리케이션 소스 코드 복사
COPY . /app/

# --- 네트워크 설정
# Django 기본 포트 8000번 노출
EXPOSE 8000

# --- 컨테이너 실행: Gunicorn 멀티 워커로 Django WSGI 실행
CMD ["gunicorn", "assignment.wsgi:application", "-b", "0.0.0.0:8000", "-w", "4", "--worker-class", "gthread", "--threads", "2", "--timeout", "60"]