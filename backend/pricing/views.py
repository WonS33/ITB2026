"""제품 단가·원가 API — 대표·관리자·경영지원팀만 (원가·마진·커미션은 대외비, 2026-11-02 사용자 결정)

GET /api/pricing/products/?exchange_rate=&margin=&option=&base=assembly|complete
    모델별 단계별 금액 + 커미션·이익. 쿼리로 값을 바꾸면 저장하지 않고 다시 계산만 한다(시뮬레이션)
GET /api/pricing/commission/?model=&sale_amount=
    판매금액을 넣어 이익·커미션·커미션 차감 이익·마진율 계산 (현재 기준값)
GET/POST /api/pricing/settings/
    기준값 변경 기록(적용일별) / 화면에서 기준값을 바꿔 새 적용일로 저장 (2026-11-02)
GET /api/pricing/access-log/
    대외비 화면 열람 기록 최근 100건 (2026-11-02)
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFullAccess

from .engine import STEPS, compute_commission, compute_steps, won
from .models import PricingAccessLog, ProductModel, ProductOption, ProductPriceSetting
from .serializers import SettingChangeSerializer

BASES = {"assembly": "Assembly", "complete": "Complete"}


class PricingApiView(APIView):
    permission_classes = [IsFullAccess]

    def finalize_response(self, request, response, *args, **kwargs):
        # 원가 자료가 브라우저·중간 서버 캐시에 남지 않게
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


def log_access(user):
    """열람 기록: 같은 사람은 10분에 한 번만 (시뮬레이션 값을 바꿀 때마다 API를 부르므로)"""
    recent = timezone.now() - timedelta(minutes=10)
    if not PricingAccessLog.objects.filter(user=user, viewed_at__gte=recent).exists():
        PricingAccessLog.objects.create(user=user)


def user_name(user):
    return (f"{user.last_name}{user.first_name}" or user.username) if user else ""


def _current_setting():
    setting = ProductPriceSetting.current()
    if setting is None:
        raise NotFound("제품 가격 기준값이 없습니다. 관리자가 가격 계산표를 먼저 넣어야 합니다.")
    return setting


def _decimal_param(params, name, low, high):
    raw = params.get(name)
    if raw in (None, ""):
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValidationError({name: f"{name}는 숫자여야 합니다."})
    if not low < value <= high:
        raise ValidationError({name: f"{name}는 {low}보다 크고 {high} 이하여야 합니다."})
    return value


def _setting_values(setting):
    return {
        "exchange_rate": setting.exchange_rate,
        "customs_factor": setting.customs_factor,
        "sga_rate": setting.sga_rate,
        "margin": setting.margin,
        "special_discount_rate": setting.special_discount_rate,
        "price_round_unit": setting.price_round_unit,
    }


def _setting_json(setting):
    return {
        "effective_date": setting.effective_date,
        "exchange_rate": float(setting.exchange_rate),
        "customs_factor": float(setting.customs_factor),
        "sga_rate": float(setting.sga_rate),
        "margin": float(setting.margin),
        "special_discount_rate": float(setting.special_discount_rate),
        "price_round_unit": setting.price_round_unit,
        "commission_rate": float(setting.commission_rate),
        "commission_unit": setting.commission_unit,
    }


class ProductPriceView(PricingApiView):
    def get(self, request):
        log_access(request.user)
        setting = _current_setting()
        params = request.query_params
        base_values = _setting_values(setting)

        # 시뮬레이션: 쿼리로 받은 값만 바꿔 다시 계산 (저장하지 않음)
        exchange_rate = _decimal_param(params, "exchange_rate", Decimal(0), Decimal(100000))
        margin = _decimal_param(params, "margin", Decimal(0), Decimal(1))
        base = params.get("base") or "assembly"
        if base not in BASES:
            raise ValidationError({"base": "base는 assembly 또는 complete여야 합니다."})
        option = None
        if params.get("option"):
            option = ProductOption.objects.filter(name=params["option"]).first()
            if option is None:
                raise ValidationError({"option": "없는 옵션입니다."})
        sim_values = {**base_values,
                      **({"exchange_rate": exchange_rate} if exchange_rate is not None else {}),
                      **({"margin": margin} if margin is not None else {})}
        simulating = exchange_rate is not None or margin is not None or base != "assembly" or option is not None

        rows, commissions = [], []
        for m in ProductModel.objects.all():
            usd = m.complete_usd if base == "complete" else m.assembly_usd
            standard = compute_steps(m.assembly_usd, **base_values)
            if usd is None:
                rows.append({"model_name": m.model_name, "series": m.series, "usd": None, "steps": None,
                             "standard_sale_price": standard["sale_price"], "change": None})
                continue
            steps = compute_steps(usd, option_usd=option.price_usd if option else Decimal(0), **sim_values)
            rows.append({
                "model_name": m.model_name,
                "series": m.series,
                "usd": float(usd),
                "steps": {key: won(steps[key]) for key, _ in STEPS},
                "standard_sale_price": standard["sale_price"],  # 시뮬레이션 전 기준 판매가
                "change": steps["sale_price"] - standard["sale_price"],
            })
            if m.sale_price:
                commissions.append({"model_name": m.model_name, **compute_commission(
                    m.sale_price, standard["margin_price"], commission_rate=setting.commission_rate,
                    commission_unit=setting.commission_unit)})

        return Response({
            "setting": _setting_json(setting),
            "simulation": {
                "active": simulating,
                "exchange_rate": float(sim_values["exchange_rate"]),
                "margin": float(sim_values["margin"]),
                "base": base,
                "option": option.name if option else "",
            },
            "steps": [{"key": k, "label": label} for k, label in STEPS],
            "options": [{"name": o.name, "price_usd": float(o.price_usd)} for o in ProductOption.objects.all()],
            "margin_choices": setting.margin_choices,
            # 순서를 지키며 중복 제거 (order_by와 distinct를 함께 쓰면 DB에서 중복이 남는다)
            "series": list(dict.fromkeys(ProductModel.objects.values_list("series", flat=True))),
            "models": rows,
            "commissions": commissions,  # 커미션 표 (계산표에 판매금액이 있는 모델만, 현재 기준값)
        })


class CommissionCalcView(PricingApiView):
    def get(self, request):
        log_access(request.user)
        setting = _current_setting()
        model = ProductModel.objects.filter(model_name=request.query_params.get("model", "")).first()
        if model is None:
            raise ValidationError({"model": "모델을 골라 주세요."})
        sale_amount = _decimal_param(request.query_params, "sale_amount", Decimal(0), Decimal(10_000_000_000))
        if sale_amount is None:
            raise ValidationError({"sale_amount": "판매금액을 입력해 주세요."})
        margin_price = compute_steps(model.assembly_usd, **_setting_values(setting))["margin_price"]
        return Response({"model_name": model.model_name, **compute_commission(
            sale_amount, margin_price, commission_rate=setting.commission_rate, commission_unit=setting.commission_unit)})


# 화면에서 바꿀 수 있는 기준값 (반올림·버림 단위와 마진 선택 목록은 지금 값을 그대로 이어 쓴다)
EDITABLE = [("exchange_rate", "환율"), ("customs_factor", "통관 배수"), ("sga_rate", "판관비율"), ("margin", "마진 값"),
            ("special_discount_rate", "특별할인율"), ("commission_rate", "커미션율")]


class SettingHistoryView(PricingApiView):
    def get(self, request):
        settings = list(ProductPriceSetting.objects.select_related("created_by").order_by("-effective_date"))
        rows = []
        for i, s in enumerate(settings):
            previous = settings[i + 1] if i + 1 < len(settings) else None
            rows.append({
                "id": s.id,
                **_setting_json(s),
                "note": s.note,
                "created_by": user_name(s.created_by) or "계산표 파일",
                "created_at": s.created_at,
                # 바로 전 적용일 대비 바뀐 값
                "changes": [
                    {"label": label, "old": float(getattr(previous, key)), "new": float(getattr(s, key))}
                    for key, label in EDITABLE if previous and getattr(previous, key) != getattr(s, key)
                ],
            })
        return Response({"fields": [{"key": k, "label": label} for k, label in EDITABLE], "settings": rows})

    def post(self, request):
        serializer = SettingChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        base = _current_setting()
        values = {key: data[key] for key, _ in EDITABLE}
        if all(values[key] == getattr(base, key) for key in values):
            return Response({"detail": "바뀐 값이 없습니다."}, status=400)
        if data["effective_date"] < base.effective_date:
            return Response({"detail": f"적용일은 지금 기준값 적용일({base.effective_date}) 이후여야 합니다."}, status=400)
        # 같은 적용일이 있으면 그 줄을 고치고, 없으면 새 줄 (예전 적용일 값은 기록으로 남는다)
        ProductPriceSetting.objects.update_or_create(
            effective_date=data["effective_date"],
            defaults={**values, "note": data.get("note", ""), "created_by": request.user,
                      "price_round_unit": base.price_round_unit, "commission_unit": base.commission_unit,
                      "margin_choices": base.margin_choices},
        )
        return self.get(request)


class AccessLogView(PricingApiView):
    def get(self, request):
        logs = PricingAccessLog.objects.select_related("user")[:100]
        return Response({"logs": [
            {"user": user_name(log.user), "username": log.user.username, "role": log.user.get_role_display(),
             "viewed_at": log.viewed_at}
            for log in logs
        ]})
