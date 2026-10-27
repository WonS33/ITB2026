from django.db import models

from common.models import TimeStampedModel


class UploadBatch(TimeStampedModel):
    """업로드 기록 1건 = 파일 1개 (specs/07-data-model.md 5절)

    업로드 → 추출(extracted) → 사람이 확인·수정 → 저장(saved) 또는 취소(cancelled)
    원본 파일은 보관하지 않고, 추출 결과만 extracted_data(JSON)에 둔다.
    created_by(TimeStampedModel)가 업로드한 사람이다.
    """

    class Kind(models.TextChoices):
        MANUFACTURING_EXCEL = "manufacturing_excel", "제조내역 엑셀"
        SALES_ORDER_PDF = "sales_order_pdf", "수주서 PDF"
        TRIP_REPORT_PDF = "trip_report_pdf", "출장보고서 PDF"
        QUOTE_PDF = "quote_pdf", "견적서 PDF"
        TRIP_REPORT_EXCEL = "trip_report_excel", "출장보고서 엑셀"
        HISTORY_EXCEL = "history_excel", "과거 데이터 엑셀"

    class Status(models.TextChoices):
        EXTRACTED = "extracted", "확인 대기"
        SAVED = "saved", "저장 완료"
        CANCELLED = "cancelled", "취소"

    kind = models.CharField("종류", max_length=30, choices=Kind.choices)
    file_name = models.CharField("원본 파일 이름", max_length=255)
    status = models.CharField("상태", max_length=20, choices=Status.choices, default=Status.EXTRACTED)
    extracted_data = models.JSONField("추출 결과", default=dict)
    saved_count = models.PositiveIntegerField("저장한 행 수", default=0)

    class Meta:
        verbose_name = "업로드 기록"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.file_name} ({self.get_status_display()})"
