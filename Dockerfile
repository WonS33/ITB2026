# Render 배포용 Dockerfile
# 서버 하나에서 Django가 API와 Vue 화면을 함께 내보낸다.

# ---------- 1단계: Vue 화면 빌드 (Node.js) ----------
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 2단계: Django 서버 (Python) ----------
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# 1단계에서 만든 Vue 빌드 결과를 settings.FRONTEND_DIST 위치(/app/frontend/dist)로 복사
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# 관리 화면(django-admin) CSS 등 정적 파일 모으기. 빌드할 때는 진짜 비밀 키가 필요 없어 임시 값을 쓴다
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

# Windows에서 만든 파일의 줄바꿈(CRLF)이 섞여도 리눅스에서 실행되도록 정리
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh
CMD ["./start.sh"]
