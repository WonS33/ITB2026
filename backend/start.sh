#!/usr/bin/env bash
# Render 서버가 켜질 때마다 실행되는 시작 스크립트 (Dockerfile의 CMD)
# 무료 플랜은 Shell·배포 전 명령(Pre-Deploy)을 못 쓰므로 DB 준비를 여기서 한다
set -e

# 1) DB 테이블 만들기·변경 반영 (이미 반영된 것은 건너뜀)
python manage.py migrate --noinput

# 2) 시연용 가상 데이터 넣기 — Render 환경 변수 SEED_DEMO_DATA=True 일 때만,
#    그리고 계정이 하나도 없을 때(첫 배포)만 실행한다.
#    무료 서버는 쉬다가 다시 켜질 때도 이 스크립트를 실행하므로, 매번 비밀번호가 초기화되지 않게 막는 것이다
if [ "$SEED_DEMO_DATA" = "True" ]; then
  if python manage.py shell -c "import sys; from accounts.models import User; sys.exit(1 if User.objects.exists() else 0)"; then
    echo "계정이 없어 시연용 가상 데이터를 넣습니다."
    python manage.py seed_users
    python manage.py seed_production
    python manage.py seed_service
    python manage.py seed_part_prices
  else
    echo "이미 계정이 있어 가상 데이터 넣기를 건너뜁니다."
  fi
fi

# 3) 웹 서버 실행. gunicorn은 배포용 파이썬 웹 서버다 (runserver는 개발용이라 배포에 쓰지 않음)
#    PORT는 Render가 정해 주는 포트 번호
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 2
