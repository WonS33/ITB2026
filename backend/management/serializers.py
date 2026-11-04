from rest_framework import serializers

# 금액 최대 15자리 (999조 원 미만, 화면 입력칸과 같은 제한)
MAX_AMOUNT = 10**15 - 1

VALUE_FIELDS = (
    "product_sales",
    "merchandise_sales",
    "service_sales",
    "merchandise_purchase",
    "material_purchase",
    "expense",
)


def amount_field(**kwargs):
    return serializers.IntegerField(
        min_value=0,
        max_value=MAX_AMOUNT,
        error_messages={
            "min_value": "금액은 0원 이상이어야 합니다.",
            "max_value": "금액은 15자리까지 입력할 수 있습니다.",
            "invalid": "금액은 숫자만 입력할 수 있습니다.",
        },
        **kwargs,
    )


class MonthlyValuesSerializer(serializers.Serializer):
    product_sales = amount_field()
    merchandise_sales = amount_field()
    service_sales = amount_field()
    merchandise_purchase = amount_field()
    material_purchase = amount_field()
    expense = amount_field()


class OtherExpenseInputSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    amount = amount_field()


class MonthlySaveSerializer(serializers.Serializer):
    """월간 입력 저장 요청 (화면 값은 믿지 않고 서버에서 다시 검사)"""

    # draft: 임시저장 / confirm: 확정 / update_confirmed: 확정된 달 수정(확정 유지)
    intent = serializers.ChoiceField(choices=["draft", "confirm", "update_confirmed"])
    values = MonthlyValuesSerializer()
    other_expenses = OtherExpenseInputSerializer(many=True, required=False, default=list)
    cash_balance = amount_field(required=False, allow_null=True, default=None)
    # 동시 수정 확인: 화면을 불러올 때 받은 updated_at 그대로 (처음 입력하는 달은 null)
    expected_updated_at = serializers.DateTimeField(allow_null=True)


class UnconfirmSerializer(serializers.Serializer):
    expected_updated_at = serializers.DateTimeField()


class TargetSaveSerializer(serializers.Serializer):
    """연간 목표 저장: 연간 목표매출액(필수, 0원 초과) + 분기 목표 4개(빈칸 = 자동 배분) + 직원 수(선택)"""

    target_amount = amount_field()
    quarters = serializers.ListField(child=amount_field(allow_null=True), min_length=4, max_length=4)
    headcount = serializers.IntegerField(
        min_value=1, max_value=9999, allow_null=True, required=False, default=None,
        error_messages={"min_value": "직원 수는 1명 이상입니다.", "max_value": "직원 수는 4자리까지 입력할 수 있습니다."},
    )
    expected_updated_at = serializers.DateTimeField(allow_null=True)

    def validate_target_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("연간 목표매출액을 입력하세요.")
        return value


NAME_MAX = 30


class CategoryItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)  # null = 새 항목
    name = serializers.CharField(allow_blank=True, trim_whitespace=True)
    cost_type = serializers.ChoiceField(choices=["fixed", "variable", ""], allow_blank=True)
    is_active = serializers.BooleanField()

    def validate_name(self, value):
        value = " ".join(value.split())  # 앞뒤 공백 제거, 연속 공백 하나로
        if not value:
            raise serializers.ValidationError("항목 이름을 입력하세요.")
        if len(value) > NAME_MAX:
            raise serializers.ValidationError(f"항목 이름은 {NAME_MAX}자까지 입력할 수 있습니다.")
        return value


class CategoriesSaveSerializer(serializers.Serializer):
    """그 외 지출 항목 저장: 화면 순서대로 전체 목록 + 지울 항목 id + 불러올 때의 version(동시 수정 확인)"""

    items = CategoryItemSerializer(many=True, max_length=100)
    deleted_ids = serializers.ListField(child=serializers.IntegerField(), max_length=100, default=list)
    version = serializers.CharField()

    def validate_items(self, items):
        seen = set()
        for item in items:
            key = item["name"].lower()
            if key in seen:
                raise serializers.ValidationError(f'같은 이름의 항목이 있습니다: "{item["name"]}"')
            seen.add(key)
        return items


class ReceivableSerializer(serializers.Serializer):
    """미수금 등록·수정 (수금 완료 건을 수정할 때만 collected_on)"""

    customer_name = serializers.CharField(max_length=60, trim_whitespace=True)
    occurred_on = serializers.DateField(error_messages={"invalid": "날짜 형식이 올바르지 않습니다."})
    amount = amount_field()
    due_on = serializers.DateField(allow_null=True, required=False, default=None)
    note = serializers.CharField(max_length=200, allow_blank=True, required=False, default="", trim_whitespace=True)
    collected_on = serializers.DateField(allow_null=True, required=False, default=None)
    expected_updated_at = serializers.DateTimeField(required=False, allow_null=True, default=None)

    def validate_customer_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("거래처를 입력하세요.")
        if len(value) > 50:
            raise serializers.ValidationError("거래처는 50자까지 입력할 수 있습니다.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("금액을 입력하세요.")
        return value


class ReceivableActionSerializer(serializers.Serializer):
    """수금 처리(collected_on 필수)·수금 취소·숨김·복구"""

    expected_updated_at = serializers.DateTimeField()
    collected_on = serializers.DateField(allow_null=True, required=False, default=None)


class LedgerFieldsSerializer(serializers.Serializer):
    """경영지원 관리 한 행 — 구분(kind)마다 쓰는 칸이 다르다 (조원 저장소 ledger/schemas.ts)

    외상매출금: 상태(필수)·거래처코드(선택, 숫자 10자리) / 외상매입금: 매입유형(필수) / 업체: 비용유형(필수)·자동이체
    구분에 맞지 않는 칸은 빈 값으로 바꿔 저장한다
    """

    kind = serializers.ChoiceField(choices=["ar", "ap", "accrued_staff", "accrued_vendor"])
    ar_status = serializers.ChoiceField(choices=["long_overdue", "collected", "scheduled"], allow_blank=True, required=False, default="")
    purchase_type = serializers.ChoiceField(choices=["goods", "raw_material"], allow_blank=True, required=False, default="")
    expense_type = serializers.ChoiceField(choices=["advertising", "entertainment", "other"], allow_blank=True, required=False, default="")
    auto_transfer = serializers.BooleanField(required=False, default=False)
    partner_code = serializers.CharField(allow_blank=True, required=False, default="", trim_whitespace=True)
    partner_name = serializers.CharField(max_length=60, allow_blank=True, trim_whitespace=True)
    amount = amount_field()
    note = serializers.CharField(max_length=200, allow_blank=True, required=False, default="", trim_whitespace=True)
    due_on = serializers.DateField(allow_null=True, required=False, default=None)
    settled_on = serializers.DateField(allow_null=True, required=False, default=None)

    def validate(self, d):
        name = " ".join(d["partner_name"].split())
        if not name:
            raise serializers.ValidationError({"partner_name": "거래처명을 입력하세요."})
        if len(name) > 50:
            raise serializers.ValidationError({"partner_name": "거래처명은 50자까지 입력할 수 있습니다."})
        if d["amount"] <= 0:
            raise serializers.ValidationError({"amount": "잔액을 입력하세요."})
        kind = d["kind"]
        if kind == "ar" and not d["ar_status"]:
            raise serializers.ValidationError({"ar_status": "상태를 고르세요."})
        if kind == "ap" and not d["purchase_type"]:
            raise serializers.ValidationError({"purchase_type": "매입유형을 고르세요."})
        if kind == "accrued_vendor" and not d["expense_type"]:
            raise serializers.ValidationError({"expense_type": "비용유형을 고르세요."})
        code = d["partner_code"] if kind == "ar" else ""
        if code and not (len(code) == 10 and code.isdigit()):
            raise serializers.ValidationError({"partner_code": "거래처코드는 숫자 10자리로 입력하세요. (예: 0000000087)"})
        return {
            **d,
            "partner_name": name,
            "partner_code": code,
            "ar_status": d["ar_status"] if kind == "ar" else "",
            "purchase_type": d["purchase_type"] if kind == "ap" else "",
            "expense_type": d["expense_type"] if kind == "accrued_vendor" else "",
            "auto_transfer": d["auto_transfer"] if kind == "accrued_vendor" else False,
        }
