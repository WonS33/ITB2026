from django.core.management.base import BaseCommand
from django.utils import timezone

from common.periods import make_period
from management import ai_comment as ai
from management.metrics import management_summary
from management.models import AiComment

QUARTERS = 8  # 끝난 분기 중 최근 8개 (seed_management 24개월 범위)


class Command(BaseCommand):
    help = (
        "가상 데이터로 계산한 숫자로 AI 분석 '예시'를 넣는다 (외부 AI 호출 없음). "
        "끝난 분기 중 확정된 달이 있는 최근 8개 분기. 여러 번 실행해도 분기마다 하나만 (내용 갱신). "
        "--remove 로 예시만 지움 — 실제 기업 데이터를 넣기 전에는 지운다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="예시 분석만 지운다 (다른 분석 기록은 그대로)")

    def handle(self, *args, **options):
        if options["remove"]:
            count, _ = AiComment.objects.filter(model=ai.EXAMPLE_MODEL).delete()
            self.stdout.write(self.style.SUCCESS(f"예시 분석 {count}건을 지웠습니다. (다른 분석 기록은 그대로)"))
            return

        today = timezone.localdate()
        year, quarter = today.year, (today.month - 1) // 3 + 1
        saved = 0
        for _ in range(QUARTERS):
            year, quarter = (year - 1, 4) if quarter == 1 else (year, quarter - 1)
            summary = management_summary(make_period("quarter", year, quarter=quarter), today)
            if not summary["confirmation"]["has_data"]:
                self.stdout.write(f"- {year}년 {quarter}분기: 확정 데이터가 없어 건너뜀")
                continue
            data = ai.build_input(summary, quarter)
            normalized = ai.normalize(ai.example_comment(summary, quarter))
            if normalized is None or normalized[1]["truncated"] or normalized[1]["dropped"]:
                raise ValueError(f"{year}년 {quarter}분기 예시가 형식을 넘음: {normalized and normalized[1]}")
            values = {
                "input_summary": data,
                "result": {**normalized[0], **ai.annotations(summary, quarter)},
                "input_hash": ai.hash_input(data),
                "prompt_version": ai.PROMPT_VERSION,
            }
            # 다시 실행할 때는 내용만 갱신하고 생성 시각은 그대로 (그 사이 [다시 분석]한 기록이 계속 최신으로 남게)
            row = AiComment.objects.filter(year=year, quarter=quarter, model=ai.EXAMPLE_MODEL).first()
            if row:
                AiComment.objects.filter(pk=row.pk).update(**values)
            else:
                AiComment.objects.create(year=year, quarter=quarter, model=ai.EXAMPLE_MODEL, **values)
            saved += 1
            self.stdout.write(f"- {year}년 {quarter}분기")
        self.stdout.write(self.style.SUCCESS(f"예시 분석 {saved}건을 넣었습니다. 대시보드에서 위 분기를 고르면 \"예시\"로 보입니다."))
