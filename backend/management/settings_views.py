"""목표·항목 설정 API (조원 저장소 settings/actions.ts 를 옮김)

- 저장과 변경 기록은 한 transaction: 기록이 실패하면 저장도 취소
- 동시 수정 확인: 불러올 때의 값(updated_at / version)과 지금이 다르면 409
"""

from django.db import IntegrityError, transaction
from django.db.models import Count
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import audit
from .models import AnnualSalesTarget, ExpenseCategory, OtherExpense
from .serializers import CategoriesSaveSerializer, TargetSaveSerializer
from .targets import allocate_quarter_targets
from .views import Conflict, ManagementApiView, _check_year_month, _name


def target_payload(year):
    target = AnnualSalesTarget.objects.filter(year=year).first()
    return {
        "year": year,
        "target_amount": target.target_amount if target else None,
        "quarters": target.quarter_targets if target else [None] * 4,
        "headcount": target.headcount if target else None,
        "updated_at": target.updated_at if target else None,
        "updated_by": _name(target.updated_by) if target and target.updated_by else None,
        # 빈 분기 자동 배분 결과 (화면 미리보기와 같은 규칙)
        "allocation": allocate_quarter_targets(target.target_amount, target.quarter_targets) if target else None,
    }


class TargetView(ManagementApiView):
    """GET/PUT /api/management/targets/{year}/ — 연간 목표매출 조회·저장 (분기 목표·직원 수는 선택)"""

    def get(self, request, year):
        _check_year_month(year, 1)
        return Response(target_payload(year))

    def put(self, request, year):
        _check_year_month(year, 1)
        serializer = TargetSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        values = {
            "target_amount": data["target_amount"],
            **{f"q{i}_target": q for i, q in enumerate(data["quarters"], start=1)},
            "headcount": data["headcount"],
        }
        try:
            with transaction.atomic():
                target = AnnualSalesTarget.objects.select_for_update().filter(year=year).first()
                if (target.updated_at if target else None) != data["expected_updated_at"]:
                    raise Conflict()
                before = {f: getattr(target, f) for f in values} if target else None
                if target is None:
                    target = AnnualSalesTarget(year=year, created_by=request.user)
                for field, value in values.items():
                    setattr(target, field, value)
                target.updated_by = request.user
                target.save()
                audit.record_audit(
                    actor=request.user,
                    screen="targets",
                    action="UPDATE" if before else "CREATE",
                    target_type="AnnualSalesTarget",
                    target_id=target.pk,
                    target_label=audit.target_label(year),
                    changes=audit.diff_fields(before, values, audit.TARGET_FIELDS),
                )
        except IntegrityError:
            raise Conflict()  # 새 연도를 두 사람이 동시에 만듦
        return Response({**target_payload(year), "message": f"{year}년 목표를 저장했습니다. 대시보드에 반영됩니다."})


def categories_version(categories):
    """동시 수정 확인용: 항목 수 + 가장 최근 수정 시각"""
    latest = max((c.updated_at for c in categories), default=None)
    return f"{len(categories)}:{latest.isoformat() if latest else ''}"


def categories_payload():
    categories = list(ExpenseCategory.objects.all())
    used = dict(
        OtherExpense.objects.exclude(amount=0)
        .values("category_id")
        .annotate(n=Count("id"))
        .values_list("category_id", "n")
    )
    return {
        "rows": [
            {
                "id": c.id,
                "name": c.name,
                "cost_type": c.cost_type,
                "is_active": c.is_active,
                "used_months": used.get(c.id, 0),  # 0원이 아닌 금액이 있는 달 수 — 0이면 삭제 가능
            }
            for c in categories
        ],
        "version": categories_version(categories),
    }


def _snapshot(category):
    return {"name": category.name, "cost_type": category.cost_type, "is_active": category.is_active}


class ExpenseCategoriesView(ManagementApiView):
    """GET/PUT /api/management/expense-categories/ — 그 외 지출 항목 관리

    PUT은 화면 목록 전체를 한 번에 저장한다: 추가·이름 변경·순서·고정/변동·비활성화·삭제(금액이 입력된 적 없는 항목만)
    """

    def get(self, request):
        return Response(categories_payload())

    def put(self, request):
        serializer = CategoriesSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["items"]
        deleted_ids = serializer.validated_data["deleted_ids"]

        def log(action, category_id, label, before, after):
            audit.record_audit(
                actor=request.user,
                screen="expense-categories",
                action=action,
                target_type="ExpenseCategory",
                target_id=category_id,
                target_label=label,
                changes=audit.diff_fields(before, after, audit.CATEGORY_FIELDS),
            )

        with transaction.atomic():
            current = {c.id: c for c in ExpenseCategory.objects.select_for_update()}
            if categories_version(list(current.values())) != serializer.validated_data["version"]:
                raise Conflict()
            kept_ids = [i["id"] for i in items if i["id"] is not None]
            # 화면에 없는 항목(그 사이 누가 추가)이나 모르는 id가 있으면 동시 수정으로 본다
            if set(kept_ids) | set(deleted_ids) != set(current) or set(kept_ids) & set(deleted_ids):
                raise Conflict()
            original_order = [c.id for c in sorted(current.values(), key=lambda c: (c.sort_order, c.id))]

            for cid in deleted_ids:
                if OtherExpense.objects.filter(category_id=cid).exclude(amount=0).exists():
                    raise ValidationError(
                        {"detail": f"「{current[cid].name}」은(는) 금액이 입력된 적이 있어 삭제할 수 없습니다. 비활성화하세요."}
                    )
                OtherExpense.objects.filter(category_id=cid).delete()  # 0원 행은 함께 지운다
                log("DELETE", cid, current[cid].name, _snapshot(current[cid]), None)
                current[cid].delete()

            # 이름 맞바꾸기(A↔B) 중 "같은 이름 금지"에 걸리지 않도록 남는 항목은 먼저 임시 이름으로
            for cid in kept_ids:
                ExpenseCategory.objects.filter(pk=cid).update(name=f"__renaming__{cid}")
            for order, item in enumerate(items, start=1):
                after = {"name": item["name"], "cost_type": item["cost_type"], "is_active": item["is_active"]}
                if item["id"] is None:
                    created = ExpenseCategory.objects.create(**after, sort_order=order)
                    log("CREATE", created.pk, item["name"], None, after)
                else:
                    category = current[item["id"]]
                    before = _snapshot(category)
                    for key, value in after.items():
                        setattr(category, key, value)
                    category.sort_order = order
                    category.save()
                    log("UPDATE", category.pk, item["name"], before, after)

            # 순서 변경은 항목마다가 아니라 한 건으로 (남아 있는 항목끼리 순서가 바뀌었을 때만)
            names = {i["id"]: i["name"] for i in items if i["id"] is not None}
            order_before = [names[cid] for cid in original_order if cid in names]
            order_after = [i["name"] for i in items if i["id"] is not None]
            if order_before != order_after:
                audit.record_audit(
                    actor=request.user,
                    screen="expense-categories",
                    action="UPDATE",
                    target_type="ExpenseCategoryOrder",
                    target_id="all",
                    target_label="그 외 지출 항목 순서",
                    changes=[
                        {"field": "order", "label": "순서", "before": ", ".join(order_before), "after": ", ".join(order_after)}
                    ],
                )
        return Response({**categories_payload(), "message": "그 외 지출 항목을 저장했습니다. 월간 입력 화면에 반영됩니다."})
