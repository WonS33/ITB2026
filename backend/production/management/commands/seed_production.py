import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from production.industry_map import to_industry
from production.models import AnnualProductionTarget, ManufacturingRecord, SalesOrder, SalesOrderItem

VIRTUAL_SHEET = "가상데이터"  # 가상 데이터 표시 (실제 업로드 데이터와 구분)

# 개발·시연용 가상 수주서 판매처: (판매처, 사업구분 원문) — 사업구분은 산업 분야 대응표 확인용 (실제 기업 아님)
ORDER_CUSTOMERS = [
    ("가람상수도사업소", "상하수도(지자체)"), ("나래정수센터", "상하수도(지자체)"), ("다온발전", "발전소"),
    ("라온가스", "가스"), ("마루플랜트", "민간 플랜트"), ("바다석유화학", "석유화학"), ("사랑오일", "오일"),
    ("아름엔지니어링", "건축"),
]
# 품명 "…: 모델명" — 제조내역의 모델명은 품명의 ":" 뒤에서 가져온다
PRODUCTS = ["버터플라이 80A: NTI-01", "게이트 100A: NTI-02", "제수 150A: NTI-03", "제수 200A: NTI-04", "버터플라이 300A: NTI-05"]
FIRST_ORDER_NO = 501  # 가상 수주서 번호 (예: 26501). 실제 수주서류 번호(26001~)와 겹치지 않게 501번부터


class Command(BaseCommand):
    help = (
        "개발·시연용 가상 수주서·제조내역과 연간 목표 생산량을 만든다 (그 연도의 기존 가상 데이터는 지우고 다시 만듦). "
        "제조내역은 수주서 수량만큼 만들고 PO번호·거래처를 수주서에서 그대로 가져온다 → 모두 수주서와 연결된다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=date.today().year)
        parser.add_argument("--target", type=int, default=300, help="연간 목표 생산량(대)")

    def handle(self, *args, year, target, **options):
        rng = random.Random(year)  # 실행할 때마다 같은 가상 데이터가 나오도록 고정
        yy = str(year)[2:]
        deleted, _ = ManufacturingRecord.objects.filter(
            source_sheet=VIRTUAL_SHEET, manufactured_date__year=year
        ).delete()
        # 가상 수주서 판매번호는 V를 넣어 실제 번호와 구분한다 (예: NTK-SO-V26501)
        SalesOrder.objects.filter(sales_no__startswith=f"NTK-SO-V{yy}").delete()

        today = date.today()
        last_month = today.month if year == today.year else 12
        records, order_no, seq = [], FIRST_ORDER_NO, 5001  # 일련번호도 실제 샘플 번호(0001~)와 겹치지 않게 5001번부터
        for month in range(1, last_month + 1):
            # 제조일은 오늘을 넘지 않게 (이번 달은 오늘까지만). 납기일은 미래여도 정상
            last_day = today.day if (year, month) == (today.year, today.month) else 28
            remaining = rng.randint(15, 35)  # 이번 달 생산 대수
            while remaining > 0:
                customer, business_type = rng.choice(ORDER_CUSTOMERS)
                # 수주서 1건 = 품목 1~2개, 품목마다 1~6대 (달의 남은 대수를 넘지 않게)
                items = []
                for product in rng.sample(PRODUCTS, rng.randint(1, 2)):
                    quantity = min(rng.randint(1, 6), remaining)
                    if quantity:
                        items.append((product, quantity))
                        remaining -= quantity
                made_days = [rng.randint(1, last_day) for _ in range(sum(q for _, q in items))]
                due = date(year, month, max(made_days)) + timedelta(days=rng.randint(5, 20))
                # 출고일: 납기 2일 전 (한 수주서는 함께 출고). 아직 오지 않은 날은 출고 전(빈 값)으로 두고,
                # 최근 1주일 안의 납기는 일부를 출고 전으로 남겨 "납기 지남·미출고"를 시연할 수 있게 한다
                shipped = due - timedelta(days=2)
                late = due >= today - timedelta(days=7) and rng.random() < 0.4
                shipped = None if shipped > today or late else shipped

                po_no = f"{yy}{order_no:03d}"
                order = SalesOrder.objects.create(
                    sales_no=f"NTK-SO-V{po_no}",
                    order_doc_no=po_no,  # 판매번호 끝 숫자와 같은 번호 → 제조내역 PO번호와 이어진다
                    order_date=date(year, month, min(made_days)) - timedelta(days=rng.randint(20, 60)),
                    business_type_raw=business_type,
                    industry=to_industry(business_type),
                    customer=customer,
                    final_orderer=customer,
                    project_name="가상 사업",
                    due_date=due,
                )
                order_no += 1
                days = iter(made_days)
                for product, quantity in items:
                    SalesOrderItem.objects.create(order=order, product_name=product, quantity=quantity,
                                                  power="380/3/60", flange="F10A", rpm_ot="29")
                    for _ in range(quantity):
                        made = date(year, month, next(days))
                        short = f"{seq:04d}"
                        records.append(
                            ManufacturingRecord(
                                serial_full=f"N82{yy}{short}",
                                serial_short=short,
                                model_name=product.split(": ", 1)[1],
                                manufactured_date=made,
                                inspection_date=made,
                                inspection_no=f"NTK{yy}{seq % 1000:03d}",
                                po_no=po_no,
                                customer=customer,
                                final_orderer=customer,
                                project_name="가상 사업",
                                due_date=due,
                                shipped_date=shipped,
                                source_sheet=VIRTUAL_SHEET,
                            )
                        )
                        seq += 1
        ManufacturingRecord.objects.bulk_create(records)
        AnnualProductionTarget.objects.update_or_create(year=year, defaults={"target_quantity": target})

        self.stdout.write(
            f"가상 제조내역: 기존 {deleted}건 삭제, {len(records)}건 생성 ({year}년 1~{last_month}월). "
            f"가상 수주서: {order_no - FIRST_ORDER_NO}건. {year}년 목표 생산량: {target}대"
        )
