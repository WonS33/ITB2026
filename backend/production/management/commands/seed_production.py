import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from production.models import AnnualProductionTarget, ManufacturingRecord, SalesOrder, SalesOrderItem

VIRTUAL_SHEET = "가상데이터"  # 가상 데이터 표시 (실제 업로드 데이터와 구분)

# 개발·시연용 가상 거래처 (실제 기업 아님)
CUSTOMERS = ["가람상수도사업소", "나래정수센터", "다온발전", "라온가스", "마루플랜트", "바다석유화학"]
MODELS = ["NTI-01", "NTI-02", "NTI-03", "NTI-04", "NTI-05"]
# 가상 수주서: (판매처, 사업구분 원문) — 사업구분은 산업 분야 대응표 확인용
ORDER_CUSTOMERS = [
    ("가람상수도사업소", "상하수도(지자체)"), ("나래정수센터", "상하수도(지자체)"), ("다온발전", "발전소"),
    ("라온가스", "가스"), ("마루플랜트", "민간 플랜트"), ("바다석유화학", "석유화학"), ("사랑오일", "오일"),
    ("아름엔지니어링", "건축"),
]
PRODUCTS = ["제수 150A: NTI-03", "제수 200A: NTI-04", "버터플라이 300A: NTI-05", "게이트 100A: NTI-02"]


class Command(BaseCommand):
    help = "개발·시연용 가상 제조내역·수주서와 연간 목표 생산량을 만든다 (그 연도의 기존 가상 데이터는 지우고 다시 만듦)."

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
                # 제조일은 오늘을 넘지 않게 (이번 달은 오늘까지만). 납기일은 미래여도 정상
                today = date.today()
                last_day = today.day if (year, month) == (today.year, today.month) else 28
                made = date(year, month, rng.randint(1, last_day))
                due = made + timedelta(days=rng.randint(5, 20))
                # 출고일: 납기 2일 전. 아직 오지 않은 날은 출고 전(빈 값)으로 두고,
                # 최근 1주일 안의 납기는 일부를 출고 전으로 남겨 "납기 지남·미출고"를 시연할 수 있게 한다
                shipped = due - timedelta(days=2)
                late = due >= today - timedelta(days=7) and rng.random() < 0.4
                shipped = None if shipped > today or late else shipped
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
                        shipped_date=shipped,
                        source_sheet=VIRTUAL_SHEET,
                    )
                )
                seq += 1
        ManufacturingRecord.objects.bulk_create(records)
        AnnualProductionTarget.objects.update_or_create(year=year, defaults={"target_quantity": target})

        orders = self.seed_orders(rng, year, yy, last_month)

        self.stdout.write(
            f"가상 제조내역: 기존 {deleted}건 삭제, {len(records)}건 생성 ({year}년 1~{last_month}월). "
            f"가상 수주서: {orders}건. {year}년 목표 생산량: {target}대"
        )

    def seed_orders(self, rng, year, yy, last_month):
        # 가상 수주서 판매번호는 V를 넣어 실제 번호와 구분한다 (예: NTK-SO-V26001)
        from production.industry_map import to_industry

        SalesOrder.objects.filter(sales_no__startswith=f"NTK-SO-V{yy}").delete()
        count = 0
        for month in range(1, last_month + 1):
            for _ in range(rng.randint(3, 7)):
                count += 1
                customer, business_type = rng.choice(ORDER_CUSTOMERS)
                due = date(year, month, rng.randint(1, 28))
                order = SalesOrder.objects.create(
                    sales_no=f"NTK-SO-V{yy}{count:03d}",
                    order_doc_no=f"{yy}{rng.randint(1, 300):03d}",
                    order_date=due - timedelta(days=rng.randint(20, 60)),
                    business_type_raw=business_type,
                    industry=to_industry(business_type),
                    customer=customer,
                    final_orderer=customer,
                    project_name="가상 사업",
                    due_date=due,
                )
                for product in rng.sample(PRODUCTS, rng.randint(1, 2)):
                    SalesOrderItem.objects.create(order=order, product_name=product, quantity=rng.randint(1, 6),
                                                  power="380/3/60", flange="F10A", rpm_ot="29")
        return count
