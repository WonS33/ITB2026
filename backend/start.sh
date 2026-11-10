#!/usr/bin/env bash
# Render 서버가 켜질 때마다 실행되는 시작 스크립트 (Dockerfile의 CMD)
# 무료 플랜은 Shell·배포 전 명령(Pre-Deploy)을 못 쓰므로 DB 준비를 여기서 한다
set -e

# 1) DB 테이블 만들기·변경 반영 (이미 반영된 것은 건너뜀)
python manage.py migrate --noinput

# 2) 시연용 가상 데이터 넣기 — Render 환경 변수 SEED_DEMO_DATA=True 일 때만,
#    그리고 계정이 하나도 없을 때(첫 배포)만 실행한다.
#    무료 서버는 쉬다가 다시 켜질 때도 이 스크립트를 실행하므로, 매번 비밀번호가 초기화되지 않게 막는 것이다
# 생산·서비스 가상 데이터: 작년(전년 동기 비교용)과 올해. 두 명령 모두 그 연도의 가상 데이터만 지우고 다시 만든다
seed_production_service() {
  last_year=$(( $(date +%Y) - 1 ))
  python manage.py seed_production --year "$last_year" --target 280
  python manage.py seed_production
  python manage.py seed_service --year "$last_year"
  python manage.py seed_service
}

if [ "$SEED_DEMO_DATA" = "True" ]; then
  if python manage.py shell -c "import sys; from accounts.models import User; sys.exit(1 if User.objects.exists() else 0)"; then
    echo "계정이 없어 시연용 가상 데이터를 넣습니다."
    python manage.py seed_users
    seed_production_service
  else
    echo "이미 계정이 있어 가상 데이터 넣기를 건너뜁니다."
  fi
  # 예전 방식(2026-11-10 이전)으로 만든 가상 제조내역은 수주서와 이어지지 않아 "수주서 미연결"로 나온다.
  # 가상 제조내역 중 미연결이 하나라도 있으면 생산·서비스 가상 데이터를 한 번 다시 만든다 (고친 뒤에는 0이라 건너뜀)
  if python manage.py shell -c "import sys; from production.models import ManufacturingRecord as M; from production.metrics import industry_by_po, order_key; m = industry_by_po(); sys.exit(0 if any(order_key(p) not in m for p in M.objects.filter(source_sheet='가상데이터').values_list('po_no', flat=True)) else 1)"; then
    echo "수주서와 이어지지 않은 가상 제조내역이 있어 생산·서비스 가상 데이터를 다시 만듭니다."
    seed_production_service
  fi
  # 나중에 추가된 표(부품 단가표·제품 가격)는 이미 배포된 DB에도 가상 값이 들어가도록 매번 실행한다.
  # 두 명령 모두 데이터가 이미 있으면 아무것도 하지 않는다 (사람이 넣은 값을 덮어쓰지 않음).
  # seed_part_prices는 예전 가상 단가 이력(업체 없는 줄)도 지운다 — 값이 똑같은 줄만
  python manage.py seed_part_prices
  python manage.py seed_product_prices
  # 경영지원 가상 데이터·AI 분석 예시: 월별 실적이 하나도 없을 때만 넣는다.
  # seed_management는 실행할 때마다 같은 값으로 덮어쓰므로, 매번 실행하면 사람이 고친 값이 지워진다
  if python manage.py shell -c "import sys; from management.models import MonthlyFinance; sys.exit(1 if MonthlyFinance.objects.exists() else 0)"; then
    echo "경영지원 데이터가 없어 가상 데이터를 넣습니다."
    python manage.py seed_management
    python manage.py seed_ai_examples
  fi
fi

# 3) 웹 서버 실행. gunicorn은 배포용 파이썬 웹 서버다 (runserver는 개발용이라 배포에 쓰지 않음)
#    PORT는 Render가 정해 주는 포트 번호
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 2
