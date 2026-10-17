from django.db import models

from common.models import TimeStampedModel


class AnnualProductionTarget(TimeStampedModel):
    """연간 목표 생산량 (웹 입력)"""

    year = models.PositiveIntegerField("연도", unique=True)
    target_quantity = models.PositiveIntegerField("연간 목표 생산량(대)")

    class Meta:
        verbose_name = "연간 목표 생산량"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.year}년 목표 {self.target_quantity}대"


class ManufacturingRecord(TimeStampedModel):
    """제조내역 (제조내역 엑셀 1행 = 제품 1대)

    엑셀 셀에는 짧은 값만 있고 앞부분은 셀 표시 형식에 들어 있다
    (예: 일련번호 셀 '0001' + 형식 "N8226" → N82260001). 저장할 때는 화면에 보이는 전체 값으로 저장한다.
    specs/05-production.md 4절 "샘플 파일 분석 결과" 참고.
    """

    serial_full = models.CharField("전체 일련번호", max_length=20, unique=True)  # 예: N82260001
    serial_short = models.CharField("일련번호 4자리", max_length=4, db_index=True)  # 예: 0001
    model_name = models.CharField("모델명", max_length=30, blank=True)  # 예: NTI-04
    bush_machining = models.CharField("부시 가공", max_length=10, blank=True)  # 숫자 6자리, 예: 301008
    rpm = models.CharField("rpm", max_length=20, blank=True)
    power = models.CharField("전원", max_length=30, blank=True)  # 예: 380/3/60
    manufactured_date = models.DateField("제조년월", null=True, blank=True)  # 월간 생산량 집계 기준
    inspection_date = models.DateField("검사일자", null=True, blank=True)
    inspection_no = models.CharField("검사번호", max_length=20, blank=True)  # 예: NTK26001
    po_no = models.CharField("뉴토크 PO번호", max_length=20, blank=True)  # 예: 26006 (#은 화면에서 붙임)
    so_no = models.CharField("SO번호", max_length=30, blank=True)
    customer_order_no = models.CharField("거래처 주문번호", max_length=50, blank=True)
    customer = models.CharField("거래처", max_length=100, blank=True)
    final_orderer = models.CharField("최종발주처", max_length=100, blank=True)
    project_name = models.CharField("사업명", max_length=200, blank=True)
    due_date = models.DateField("납기일", null=True, blank=True)  # 납기 캘린더 기준
    shipped_date = models.DateField("출고일", null=True, blank=True)
    note = models.CharField("비고", max_length=200, blank=True)
    source_sheet = models.CharField("읽어 온 시트", max_length=50, blank=True)  # 예: 2026(NTI)

    class Meta:
        verbose_name = "제조내역"
        verbose_name_plural = verbose_name
        ordering = ["serial_full"]

    def __str__(self):
        return self.serial_full
