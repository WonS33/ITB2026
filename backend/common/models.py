from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """모든 테이블에 공통으로 두는 생성일·수정일·입력자 (specs/07-data-model.md 공통 규칙)"""

    created_at = models.DateTimeField("생성일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="입력자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        abstract = True
