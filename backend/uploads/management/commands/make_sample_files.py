from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from uploads.sample_files import build_manufacturing_workbook

OUT_DIR = Path(settings.BASE_DIR) / "sample_data"


class Command(BaseCommand):
    help = "시연용 가상 업로드 파일을 backend/sample_data/ 에 만든다 (실제 기업 데이터 아님)."

    def handle(self, *args, **options):
        OUT_DIR.mkdir(exist_ok=True)
        rows = []
        for i in range(1, 11):
            made = date(2026, 10, i)
            rows.append({"no": i, "model": f"0{i % 5 + 1}", "made": made, "inspected": made,
                         "due": made + timedelta(days=10), "shipped": made + timedelta(days=8),
                         "po": f"26{i + 400:03d}", "bush": 301008 if i == 1 else None})
        # 시연용: 오류 행(제조년월 없음) 1개, 이미 저장된 번호(seed_production의 5001번) 1개
        rows.append({"no": 11, "model": "03", "made": None, "due": date(2026, 10, 25)})
        rows.append({"no": 5001, "model": "02", "made": date(2026, 1, 5)})

        path = OUT_DIR / "가상_제조내역.xlsx"
        path.write_bytes(build_manufacturing_workbook(rows))
        self.stdout.write(f"생성: {path} (정상 10행, 제조년월 누락 1행, 중복 1행, 일련번호 없는 행 3행)")
