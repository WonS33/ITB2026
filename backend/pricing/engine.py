"""제품 가격 계산 (specs/09-metrics.md 5절) — 기업 계산표를 그대로 재현한 순서

1. 원화 = 원재료(USD) × 환율                       (원재료: Assembly 기본, Complete 선택)
2. 옵션 반영 = 원화 + 옵션(USD) × 환율              (옵션 단위·단계는 확인 필요, 기본 옵션 없음)
3. 통관 = 옵션 반영 × 통관 배수
4. 원가(판관비 반영) = 통관 × (1 + 판관비율 ÷ 100)
5. 마진 반영 = 원가 ÷ 마진 값
6. 판매가 = 마진 반영을 올림 단위(천원)로 올림
7. 특별할인가 = 판매가 × (1 − 특별할인율 ÷ 100)을 올림 단위로 올림

커미션(판매금액 기준):
- 이익 = 판매금액 − 마진 반영 금액(계산표의 "원가" 칸)
- 커미션 = 판매금액 × 커미션율 ÷ 100을 버림 단위(만원)로 버림
- 커미션 차감 이익 = 이익 − 커미션
- 마진율(제안, 확인 필요) = 커미션 차감 이익 ÷ 판매금액 × 100
중간 금액은 소수까지 정확히 계산하고, 화면에는 원 단위 반올림으로 보여 준다.
"""

import csv
import io
import re
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

STEPS = [
    ("krw", "원화 환산"),
    ("with_option", "옵션 반영"),
    ("customs", "통관"),
    ("cost", "원가(판관비 반영)"),
    ("margin_price", "마진 반영"),
    ("sale_price", "판매가"),
    ("special_price", "특별할인가"),
]


def won(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_to(value, unit, rounding):
    unit = Decimal(unit)
    return int((Decimal(value) / unit).quantize(Decimal("1"), rounding=rounding) * unit)


def compute_steps(usd, *, exchange_rate, customs_factor, sga_rate, margin, special_discount_rate,
                  price_round_unit=1000, option_usd=Decimal(0)):
    """원재료(USD) → 단계별 금액 (소수까지 정확한 값)"""
    rate = Decimal(exchange_rate)
    krw = Decimal(usd) * rate
    with_option = krw + Decimal(option_usd) * rate
    customs = with_option * Decimal(customs_factor)
    cost = customs * (1 + Decimal(sga_rate) / 100)
    margin_price = cost / Decimal(margin)
    sale_price = _round_to(margin_price, price_round_unit, ROUND_CEILING)
    special_price = _round_to(Decimal(sale_price) * (1 - Decimal(special_discount_rate) / 100), price_round_unit,
                              ROUND_CEILING)
    return {"krw": krw, "with_option": with_option, "customs": customs, "cost": cost,
            "margin_price": margin_price, "sale_price": sale_price, "special_price": special_price}


def compute_commission(sale_amount, margin_price, *, commission_rate, commission_unit=10000):
    sale_amount = Decimal(sale_amount)
    profit = sale_amount - Decimal(margin_price)
    commission = _round_to(sale_amount * Decimal(commission_rate) / 100, commission_unit, ROUND_FLOOR)
    net = profit - commission
    return {
        "sale_amount": won(sale_amount),
        "supply_price": won(margin_price),
        "profit": won(profit),
        "commission": commission,
        "net_profit": won(net),
        "margin_rate": float((net / sale_amount * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) if sale_amount else None,
    }


# ── 기업 계산표 CSV 읽기 (import_product_prices 명령) ─────────────────


def _decode(raw):
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 인코딩을 읽을 수 없습니다 (UTF-8 또는 CP949로 저장해 주세요).")


def _rows(raw):
    return [[c.strip() for c in row] + [""] * 10 for row in csv.reader(io.StringIO(_decode(raw)))]


def to_decimal(text):
    """' 1,234 ' → 1234, '12%' → 12, 빈칸·'-'·'N/A' → None"""
    value = (text or "").strip().replace(",", "").replace("%", "")
    if value in ("", "-", "N/A"):
        return None
    try:
        return Decimal(value)
    except Exception:
        raise ValueError(f"숫자로 읽을 수 없습니다: {text!r}")


MODEL_RE = re.compile(r"^([A-Z]+)-[0-9A-Z.]+$")  # 예: NTI-01, NTI-09.1, NTI-10G


def parse_product_sheet(raw):
    """제품 계산표 → (기준값, [모델별 원재료 USD와 파일에 적힌 단계별 금액])

    기준값 줄: 첫 칸이 비고 둘째 칸이 'Assembly'인 줄 (환율, 옵션, 통관 배수, 판관비율, 마진, 금액작성, 특별할인율)
    """
    rows = _rows(raw)
    params = next((r for r in rows if not r[0] and r[1] == "Assembly"), None)
    if params is None:
        raise ValueError("기준값 줄(Assembly·환율·통관…)을 찾지 못했습니다. 제품 계산표인지 확인해 주세요.")
    setting = {
        "exchange_rate": to_decimal(params[2]),
        "customs_factor": to_decimal(params[4]),
        "sga_rate": to_decimal(params[5]),
        "margin": to_decimal(params[6]),
        "special_discount_rate": to_decimal(params[8]),
    }
    if any(v is None for v in setting.values()):
        raise ValueError("기준값 중 빈 칸이 있습니다.")
    models = []
    for r in rows:
        m = MODEL_RE.match(r[0])
        if not m:
            continue
        models.append({
            "model_name": r[0], "series": m.group(1), "assembly_usd": to_decimal(r[1]),
            "file": {"krw": to_decimal(r[2]), "with_option": to_decimal(r[3]), "customs": to_decimal(r[4]),
                     "cost": to_decimal(r[5]), "margin_price": to_decimal(r[6]), "sale_price": to_decimal(r[7]),
                     "special_price": to_decimal(r[8])},
        })
    return setting, models


def parse_data_sheet(raw):
    """선택 목록 표 → (모델별 Complete·Assembly USD, 마진 선택 목록, 옵션 가격 목록)"""
    usd, margins, options = {}, [], []
    for r in _rows(raw):
        if MODEL_RE.match(r[0]):
            usd[r[0]] = {"complete_usd": to_decimal(r[1]), "assembly_usd": to_decimal(r[2])}
        margin = to_decimal(r[4]) if r[4] and r[4] != "마진" else None
        if margin is not None:
            margins.append(float(margin))
        if r[6] and r[6] not in ("옵션", "0", "N/A") and r[7] != "":  # N/A = 옵션 없음
            price = to_decimal(r[7])
            if price is not None:
                options.append({"name": r[6], "price_usd": price})
    return usd, margins, options


def parse_commission_sheet(raw):
    """커미션 표 → 모델별 판매금액과 파일에 적힌 원가·이익·커미션·차감 이익"""
    result = []
    for r in _rows(raw):
        if MODEL_RE.match(r[0]):
            result.append({"model_name": r[0], "sale_amount": to_decimal(r[1]), "file": {
                "supply_price": to_decimal(r[2]), "profit": to_decimal(r[3]),
                "commission": to_decimal(r[4]), "net_profit": to_decimal(r[5])}})
    return result


def verify(setting, models, commissions, commission_rate, commission_unit=10000, price_round_unit=1000):
    """파일에 적힌 금액과 다시 계산한 금액이 같은지 확인 → 다른 곳 목록 (금액은 적지 않음)

    중간 단계(원화~마진 반영)는 파일이 원 단위로 반올림해 보여 주므로 1원까지 차이는 허용, 판매가·특별할인가·커미션은 정확히 같아야 한다.
    """
    problems = []
    margin_prices = {}
    for m in models:
        steps = compute_steps(m["assembly_usd"], price_round_unit=price_round_unit, **setting)
        margin_prices[m["model_name"]] = steps["margin_price"]
        for key, label in STEPS:
            expected = m["file"].get(key)
            if expected is None:
                continue
            exact = key in ("sale_price", "special_price")
            if (Decimal(steps[key]) != expected) if exact else abs(Decimal(steps[key]) - expected) > 1:
                problems.append(f"{m['model_name']} {label}")
    for c in commissions:
        if c["model_name"] not in margin_prices or c["sale_amount"] is None:
            problems.append(f"{c['model_name']} 커미션: 제품 계산표에 없는 모델이거나 판매금액이 비어 있음")
            continue
        got = compute_commission(c["sale_amount"], margin_prices[c["model_name"]],
                                 commission_rate=commission_rate, commission_unit=commission_unit)
        for key, label in (("supply_price", "원가"), ("profit", "이익"), ("commission", "커미션"), ("net_profit", "차감 이익")):
            expected = c["file"][key]
            if expected is not None and abs(Decimal(got[key]) - expected) > (0 if key == "commission" else 1):
                problems.append(f"{c['model_name']} {label}")
    return problems
