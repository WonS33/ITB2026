import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from service.models import RequesterRegion, TripReport, TripReportCompanion, TripReportPart, TripReportProduct

VIRTUAL_PURPOSE = "가상 출장"  # 가상 데이터 표시 (실제 업로드 데이터와 구분)

# 개발·시연용 가상 요청처 → 시·도 (실제 기업 아님)
REQUESTERS = [
    ("가람정수장", "서울특별시"), ("나래하수처리장", "경기도"), ("다온산업단지", "충청북도"), ("라온발전소", "충청남도"),
    ("마루정수센터", "부산광역시"), ("바다가스기지", "울산광역시"), ("사랑하수처리장", "전라남도"),
    ("아름정수장", "경상북도"), ("자람배수지", "강원특별자치도"), ("하늘정수장", "제주특별자치도"),
    ("푸른처리장", "대전광역시"), ("새솔정수센터", "경상남도"),
]
PEOPLE = ["김가상 대리", "이가상 과장", "박가상 사원", "최가상 대리"]
MODELS = ["AVA01", "AVA03", "AVA05", "AVB02", "NTI-03"]
PARTS = ["Main Board", "Power Board", "Magnetic Contactor", "Control PCB", "Limit Switch", "Motor"]


class Command(BaseCommand):
    help = "개발·시연용 가상 출장보고서를 만든다 (그 연도의 기존 가상 출장보고서는 지우고 다시 만듦)."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=date.today().year)

    def handle(self, *args, year, **options):
        rng = random.Random(f"service-{year}")
        old = TripReport.objects.filter(purpose=VIRTUAL_PURPOSE, start_date__year=year)
        deleted = old.count()  # delete()의 숫자는 함께 지워지는 동행자·제품·부품까지 세므로 보고서 수를 따로 센다
        old.delete()
        for requester, region in REQUESTERS:
            RequesterRegion.objects.get_or_create(requester=requester, defaults={"region": region})
        region_of = dict(REQUESTERS)

        last_month = date.today().month if year == date.today().year else 12
        count = 0
        for month in range(1, last_month + 1):
            for _ in range(rng.randint(4, 10)):
                # 출장 시작일은 오늘을 넘지 않게 (이번 달은 오늘까지만)
                today = date.today()
                last_day = today.day if (year, month) == (today.year, today.month) else 28
                start = date(year, month, rng.randint(1, last_day))
                requester = rng.choice(REQUESTERS)[0]
                author = rng.choice(PEOPLE)
                report = TripReport.objects.create(
                    start_date=start,
                    end_date=start + timedelta(days=rng.choice([0, 0, 1, 2])),
                    extra_trip="없음",
                    paid_type=rng.choices(["유상", "무상"], weights=[6, 4])[0],
                    requester_type="검색 불가",
                    requester=requester,
                    region=region_of[requester],
                    work_type=rng.choice(["수리", "점검", "설치"]),
                    purpose=VIRTUAL_PURPOSE,
                    fault_description="1. 가상 고장 내용",
                    work_description="1. 가상 작업 내용",
                    work_result="정상작동",
                    author=author,
                )
                # 작성자가 동행자에도 들어가는 경우를 섞는다 (담당자 중복 집계 확인용)
                for name in rng.sample(PEOPLE, rng.randint(0, 2)):
                    TripReportCompanion.objects.create(report=report, name=name)
                TripReportProduct.objects.create(report=report, model_name=rng.choice(MODELS),
                                                 quantity=rng.randint(1, 3), serial_no_raw="A800" + str(rng.randint(10**7, 10**8)))
                for part in rng.sample(PARTS, rng.randint(0, 3)):
                    TripReportPart.objects.create(report=report, part_name=part)
                count += 1
        self.stdout.write(f"가상 출장보고서: 기존 {deleted}건 삭제, {count}건 생성 ({year}년 1~{last_month}월)")
