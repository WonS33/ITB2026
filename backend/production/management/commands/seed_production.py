import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from production.models import AnnualProductionTarget, ManufacturingRecord

VIRTUAL_SHEET = "가상데이터"  # 가상 데이터 표시 (실제 업로드 데이터와 구분)

# 개발·시연용 가상 거래처 (실제 기업 아님)
CUSTOMERS = ["가람상수도사업소", "나래정수센터", "다온발전", "라온가스", "마루플랜트", "바다석유화학"]
MODELS = ["NTI-01", "NTI-02", "NTI-03", "NTI-04", "NTI-05"]


class Command(BaseCommand):
    help = "개발·시연용 가상 제조내역과 연간 목표 생산량을 만든다 (그 연도의 기존 가상 데이터는 지우고 다시 만듦)."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=date.today().year)
        parser.add_argument("--target", type=int, default=300, help="연간 목표 생산량(대)")

    def handle(self, *args, year, target, **options):
        rng = random.Random(year)  # 실행할 때마다 같은 가상 데이터가 나오도록 고정
        deleted, _ = ManufacturingRecord.objects.filter(
            source_sheet=VIRTUAL_SHEET, manufactured_date__year=year
        ).delete()

        yy = str(year)[2:]
        last_month = date.today().month if year == date.today().year else 12
        records, seq = [], 5001  # 실제 샘플 번호(0001~)와 겹치지 않게 5001번부터
        for month in range(1, last_month + 1):
            for _ in range(rng.randint(15, 35)):
                made = date(year, month, rng.randint(1, 28))
                due = made + timedelta(days=rng.randint(5, 20))
                short = f"{seq:04d}"
                records.append(
                    ManufacturingRecord(
                        serial_full=f"N82{yy}{short}",
                        serial_short=short,
                        model_name=rng.choice(MODELS),
                        manufactured_date=made,
                        inspection_date=made,
                        inspection_no=f"NTK{yy}{seq % 1000:03d}",
                        po_no=f"{yy}{rng.randint(1, 300):03d}",
                        customer=rng.choice(CUSTOMERS),
                        project_name="가상 사업",
                        due_date=due,
                        shipped_date=due - timedelta(days=2),
                        source_sheet=VIRTUAL_SHEET,
                    )
                )
                seq += 1
        ManufacturingRecord.objects.bulk_create(records)
        AnnualProductionTarget.objects.update_or_create(year=year, defaults={"target_quantity": target})

        self.stdout.write(
            f"가상 제조내역: 기존 {deleted}건 삭제, {len(records)}건 생성 ({year}년 1~{last_month}월). "
            f"{year}년 목표 생산량: {target}대"
        )
