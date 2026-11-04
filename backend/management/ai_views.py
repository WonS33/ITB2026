"""AI 분석 코멘트 API (조원 저장소 ai/actions.ts·load-comment.ts 를 옮김)

GET  /api/management/ai-comment/?(기간)  — 저장된 최신 코멘트만 읽는다 (AI 호출 없음)
POST /api/management/ai-comment/         — {year, quarter, expected_latest_id, consent} → 분석 생성·저장
     권한·끝난 분기·허락·동시 생성을 모두 서버에서 다시 확인한다
"""

import logging
import threading

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from common.periods import make_period, period_from_params

from . import ai_client
from . import ai_comment as ai
from .metrics import management_summary
from .models import AiComment
from .views import Conflict, ManagementApiView

logger = logging.getLogger(__name__)
CONFLICT_MESSAGE = "다른 사용자가 방금 이 분기를 분석했습니다. 화면을 새로 불러오세요."

# 같은 분기를 동시에 두 번 생성하지 않도록 (API 비용 중복 방지, 서버 프로세스 단위)
_in_flight = set()
_in_flight_lock = threading.Lock()


class GenerateSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    quarter = serializers.IntegerField(min_value=1, max_value=4)
    expected_latest_id = serializers.IntegerField(allow_null=True)  # 화면을 열 때 본 최신 코멘트 id (없으면 null)
    consent = serializers.BooleanField(required=False, default=False)  # 관리자(대표)가 외부 AI 전송 확인창에서 [확인]


def _latest_id(year, quarter):
    row = ai.latest_comment(year, quarter)
    return row.id if row else None


class AiCommentView(ManagementApiView):
    def get(self, request):
        today = timezone.localdate()
        period = period_from_params(request.query_params)
        return Response(ai.comment_view(request.user, period, management_summary(period, today), today))

    def post(self, request):
        s = GenerateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        year, quarter, expected, consent = (s.validated_data[k] for k in ("year", "quarter", "expected_latest_id", "consent"))
        today = timezone.localdate()
        summary = management_summary(make_period("quarter", year, quarter=quarter), today)
        abilities = ai.current_abilities(request.user, year, quarter, today, summary)
        if not abilities["can_generate"]:
            if abilities["notice"]:
                raise ValidationError({"detail": abilities["notice"]})
            raise PermissionDenied("AI 분석을 실행할 권한이 없습니다.")
        # 관리자(대표)가 허락 전 차단을 넘어 실행 — 확인창 [확인] 없이는 보내지 않는다
        if abilities.get("consent_notice"):
            if not consent:
                raise ValidationError({"detail": "외부 AI 전송 확인이 필요합니다. 다시 눌러 주세요."})
            logger.info("[ai-comment] %s-Q%s 관리자(대표) 확인으로 분석", year, quarter)
        if _latest_id(year, quarter) != expected:
            raise Conflict(CONFLICT_MESSAGE)

        key = (year, quarter)
        with _in_flight_lock:
            if key in _in_flight:
                raise Conflict("이 분기는 이미 분석 중입니다. 잠시 후 확인하세요.")
            _in_flight.add(key)
        try:
            data = ai.build_input(summary, quarter)
            try:
                response, model = ai_client.request_ai(
                    ai.SYSTEM_PROMPT, ai.user_message(data), ai.RESPONSE_SCHEMA, lambda: ai.mock_comment(data)
                )
                normalized = ai.normalize(response)
                if normalized is None:
                    raise ai_client.AiError("invalid-output", "매출 현황 문장이 없음")
            except ai_client.AiError as error:
                # 원인 추적용 (키·입력 데이터는 남기지 않는다)
                logger.error("[ai-comment] %s-Q%s 실패: %s %s", year, quarter, error.kind, error)
                return Response({"detail": error.message, "code": "AI_ERROR", "retryable": error.retryable}, status=502)
            result, report = normalized
            if report["truncated"] or report["dropped"]:
                logger.warning("[ai-comment] %s-Q%s 응답 정리: %s문장 자름, %s문장 버림", year, quarter, report["truncated"], report["dropped"])
            with transaction.atomic():
                # AI 응답을 기다리는 사이 다른 사람이 저장했으면 버린다
                if _latest_id(year, quarter) != expected:
                    raise Conflict(CONFLICT_MESSAGE)
                AiComment.objects.create(
                    year=year, quarter=quarter, input_summary=data, result={**result, **ai.annotations(summary, quarter)},
                    input_hash=ai.hash_input(data), model=model, prompt_version=ai.PROMPT_VERSION, created_by=request.user,
                )
        finally:
            with _in_flight_lock:
                _in_flight.discard(key)
        return Response({"message": f"{year}년 {quarter}분기 AI 분석을 저장했습니다."})
