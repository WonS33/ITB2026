"""AI 분석 코멘트 (조원 저장소 modules/management/ai/* 를 옮김)

- 끝난 분기 하나를 분석한다. 화면을 열 때는 저장된 코멘트만 읽고 AI 는 부르지 않는다 ([분석하기]를 눌러야 호출)
- AI 에 보내는 것은 집계된 합계 숫자뿐 (거래처명·직원 이름·건별 내역 제외). 금액·비율·차이는 미리 계산해 AI 가 계산하지 않게 한다
- 연간 목표 한 줄(headline)과 장기 미수금 거래처명은 AI 가 아니라 서버가 만들어 함께 저장한다
- 외부 AI 전송 허락(AI_ALLOW_REAL_DATA) 전에는 배포 서버·엑셀 이관 데이터 분기를 관리자(대표)만 확인창을 거쳐 분석
"""

import hashlib
import json

from django.conf import settings
from django.db.models import Sum

from accounts.models import User
from common.periods import make_period, quarter_of

from .metrics import management_summary, previous_period, same_period_last_year
from .models import AiComment, AuditLog, LedgerEntry

PROMPT_VERSION = "2026-11-04.1"
SENTENCE_PROMPT_MAX = 60  # 프롬프트는 문장당 60자
SENTENCE_MAX = 80  # 저장은 80자까지 — 넘으면 실패시키지 않고 잘라서 살린다
LONG_OVERDUE_MAX = 3
EXAMPLE_MODEL, MOCK_MODEL = "example", "mock"
METHOD_LABELS = {"ai": "AI 분석", "mock": "모의 응답", "example": "예시"}

UPLOADED_DATA_NOTICE = (
    "회사 재무 숫자를 외부 AI로 보내는 것은 대표님 허락이 필요합니다 — "
    "엑셀 이관 데이터가 들어간 분기는 관리자(대표) 계정만 분석할 수 있습니다."
)
REAL_DATA_BLOCKED_NOTICE = (
    "회사 재무 숫자를 외부 AI로 보내는 것은 대표님 허락이 필요합니다 — "
    "이 서버에서는 관리자(대표) 계정만 AI 분석을 실행할 수 있습니다."
)
ADMIN_CONSENT_NOTICE = (
    "회사 재무 합계 숫자(매출·지출·이익·목표 달성률·미수금)를 외부 AI(Anthropic)로 보내 분석합니다. "
    "거래처명·직원 이름·건별 내역은 보내지 않습니다.\n\n진행할까요?"
)


# ---------- 표기 ----------


def won_short(v):
    """7.09억원 / 6,668만원 / 5,000원 (AI 입력·예시 문장용)"""
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 100_000_000:
        return f"{sign}{a / 100_000_000:.2f}억원"
    if a >= 10_000:
        return f"{sign}{round(a / 10_000):,}만원"
    return f"{sign}{a:,}원"


def _pct(v):
    return "-" if v is None else f"{v:.1f}%"


def _signed(v):
    return f"{'+' if v >= 0 else ''}{v:.1f}%"


def _tenths(rate):
    """% 값 → 0.1%p 단위 정수 (82.35 → 824)"""
    return round(rate * 10)


def achievement_text(rate):
    """목표 대비 달성률(%): "82.4%로 17.6%p 부족" / "105.2%로 5.2%p 초과" / "100.0%로 목표 달성\""""
    t = _tenths(rate)
    diff = t - 1000
    if diff == 0:
        return f"{t / 10:.1f}%로 목표 달성"
    return f"{t / 10:.1f}%로 {abs(diff) / 10:.1f}%p {'부족' if diff < 0 else '초과'}"


def progress_text(rate, elapsed):
    """연간 진도: "연간 달성률 60.0%로 경과율 75.0% 대비 15.0%p 뒤처짐\""""
    t, e = _tenths(rate), _tenths(elapsed)
    head = f"연간 달성률 {t / 10:.1f}%로 경과율 {e / 10:.1f}%"
    diff = t - e
    if diff == 0:
        return f"{head}와 같음"
    return f"{head} 대비 {abs(diff) / 10:.1f}%p {'뒤처짐' if diff < 0 else '앞섬'}"


def amount_difference(target, actual):
    diff = target - actual
    if diff == 0:
        return "차이 없음"
    return f"{won_short(diff)} 부족" if diff > 0 else f"{won_short(-diff)} 초과"


CHANGE_REASON = {
    "no-current-data": "비교 불가 (이번 분기 확정 데이터 없음)",
    "no-data": "비교 불가 (비교 기간 확정 데이터 없음)",
    "zero-base": "비교 불가 (비교 기간 값이 0원)",
}


def _change_text(c):
    return CHANGE_REASON[c.get("reason") or "no-data"] if c["rate"] is None else _signed(c["rate"])


def _months_label(months):
    return ", ".join(f"{m['year']}년 {m['month']}월" for m in months)


# ---------- 어느 분기를, 지금 분석할 수 있는지 ----------


def target_quarter(period, summary):
    """카드가 보여 줄 분기: 분기 보기 = 그 분기 / 월 보기 = 그 달의 분기 / 연간 = 확정된 달이 있는 마지막 분기 (없으면 None)"""
    if period.kind in ("quarter", "month"):
        return period.year, quarter_of(period.months[0])
    last = max((m["month"] for m in summary["confirmation"]["confirmed_months"]), default=0)
    return (period.year, quarter_of(last)) if last else None


def input_months(year, quarter):
    """AI 입력에 쓰이는 달: 그 분기·직전 분기·전년 동기·그 해 1월~분기 말"""
    q = make_period("quarter", year, quarter=quarter)
    seen = []
    for p in (q, previous_period(q), same_period_last_year(q)):
        seen += [(p.year, m) for m in p.months]
    seen += [(year, m) for m in range(1, quarter * 3 + 1)]
    return sorted(set(seen))


def has_uploaded_input(year, quarter):
    """AI 입력에 쓰이는 달 중 경영지원 관리 엑셀 이관(실제 숫자일 수 있음)이 있었는지 — 변경 기록으로 확인"""
    months = [f"{y}-{m:02d}" for y, m in input_months(year, quarter)]
    return AuditLog.objects.filter(screen="ledger-import", action="IMPORT", target_id__in=months).exists()


def real_data_blocked():
    """배포 서버(DEBUG=False)는 대표님 허락(AI_ALLOW_REAL_DATA=True) 전까지 막는다 — 개발 서버는 가상 데이터라 막지 않음"""
    return not settings.DEBUG and not settings.AI_ALLOW_REAL_DATA


def uploaded_blocked(uploaded):
    return uploaded and not settings.AI_ALLOW_REAL_DATA


def abilities(user, year, quarter, today, has_data, uploaded=False, real_blocked=False):
    """[분석하기] 가능 여부 — 화면과 생성 API 가 같은 함수를 쓴다
    - 끝난 분기만 (진행 중이면 미수금 기준이 매일 바뀌어 결과가 금방 낡음)
    - 그 분기에 확정된 달이 있어야 함
    - 허락 전 차단은 관리자(대표)만 확인창(consent_notice)을 거쳐 넘을 수 있다"""
    end = make_period("quarter", year, quarter=quarter).end
    if end >= today:
        from datetime import timedelta

        start = end + timedelta(days=1)
        return {"can_generate": False, "notice": f"분기가 끝난 뒤({start.month}월 {start.day}일부터) 분석할 수 있습니다."}
    if not has_data:
        return {"can_generate": False, "notice": "이 분기에 확정된 달이 없어 분석할 수 없습니다."}
    if (uploaded or real_blocked) and user.role in User.FULL_ACCESS_ROLES:
        return {"can_generate": True, "notice": None, "consent_notice": ADMIN_CONSENT_NOTICE}
    if uploaded:
        return {"can_generate": False, "notice": UPLOADED_DATA_NOTICE}
    if real_blocked:
        return {"can_generate": False, "notice": REAL_DATA_BLOCKED_NOTICE}
    if not user.has_full_access:
        return {"can_generate": False, "notice": None}
    return {"can_generate": True, "notice": None}


def current_abilities(user, year, quarter, today, summary):
    return abilities(
        user, year, quarter, today, summary["confirmation"]["has_data"],
        uploaded_blocked(has_uploaded_input(year, quarter)), real_data_blocked(),
    )


# ---------- AI 입력 ----------


def _cumulative(targets, quarter):
    """1월 ~ 이번 분기 말 확정 매출 누적"""
    return sum(q["actual"] for q in targets["quarters"][:quarter])


def _comparison(c, labels):
    return {
        "basePeriod": c["label"],
        # 이번 분기에 확정 안 된 달이 있어 같은 순서의 달끼리만 비교한 경우
        "sameMonthsOnly": {"current": _months_label(c["aligned"]["current"]), "base": _months_label(c["aligned"]["base"])} if c["aligned"] else None,
        "basePartiallyConfirmed": c["is_partial"],
        "revenue": _change_text(c["revenue"]),
        "expense": _change_text(c["costs"]),
        "profitDiff": "비교 불가" if c["profit_diff"] is None else f"{'+' if c['profit_diff'] >= 0 else ''}{won_short(c['profit_diff'])}",
        "marginDiff": "비교 불가" if c["margin_diff"] is None else f"{'+' if c['margin_diff'] >= 0 else ''}{c['margin_diff']:.1f}%p",
        "revenueByItem": {labels[k]: _change_text(v) for k, v in c["revenue_items"].items()},
    }


def _amount_count(v):
    return {"amount": won_short(v["amount"]), "count": v["count"]}


def build_input(summary, quarter):
    """AI 에 보낼 입력 (이 dict 그대로 JSON 으로 보내고, 해시도 이것으로 계산). 오늘 날짜에 따라 바뀌는 값은 넣지 않는다"""
    revenue, costs, profit, targets, rec = summary["revenue"], summary["costs"], summary["profit"], summary["targets"], summary["receivables"]
    labels = {i["key"]: f"{i['label']} 매출" for i in revenue["items"]}
    shares = lambda items, suffix="": [  # noqa: E731
        {"item": f"{i['label']}{suffix}", "amount": won_short(i["amount"]), "share": _pct(i["ratio"])} for i in items
    ]
    cost_sum = lambda keys: sum(i["amount"] for i in costs["items"] if i["key"] in keys)  # noqa: E731
    confirmation = summary["confirmation"]

    target = "연간 목표 미설정"
    if targets:
        p, annual_target = targets["period"], targets["annual"]["target"]
        cumulative = _cumulative(targets, quarter)
        annual_rate = None if not annual_target else cumulative / annual_target * 100
        expected = annual_target * quarter // 4  # 기간 경과 기준 기대치 = 연간 목표 × 분기 수 ÷ 4
        target = {
            "quarterTarget": won_short(p["target"]),
            "quarterTargetSource": "직접 입력" if targets["quarters"][quarter - 1]["source"] == "input" else "연간 목표에서 자동 배분",
            "quarterActual": won_short(p["actual"]),
            "quarterAchievement": "비교 불가 (분기 목표가 0원)" if p["rate"] is None else achievement_text(p["rate"]),
            "quarterDifference": amount_difference(p["target"], p["actual"]),
            "annualTarget": won_short(annual_target),
            "cumulativeActualToQuarterEnd": won_short(cumulative),
            "annualProgress": "비교 불가 (연간 목표가 0원)" if annual_rate is None else progress_text(annual_rate, quarter / 4 * 100),
            "expectedToQuarterEnd": won_short(expected),
            "gapVsExpected": amount_difference(expected, cumulative),
        }

    receivables = {"basis": "경영지원 관리 외상매출금 — 미수 = 장기 미수금 + 당월 수금예정", "baseMonth": "입력 없음"}
    if rec["month"]:
        receivables.update({
            "baseMonth": f"{rec['month']['year']}년 {rec['month']['month']}월",
            "total": won_short(rec["total"]),
            "count": rec["count"],
            "longOverdue": _amount_count(rec["long_overdue"]),  # 담당자가 정한 "장기 미수금"
            "scheduled": _amount_count(rec["scheduled"]),
            "collectedThisMonth": _amount_count(rec["collected"]),  # 기준월에 받은 돈 (미수에 넣지 않음)
        })

    return {
        "period": summary["period"]["label"],
        "months": _months_label([{"year": summary["period"]["year"], "month": m} for m in summary["period"]["months"]]),
        "confirmation": {
            "confirmedMonths": _months_label(confirmation["confirmed_months"]),
            "unconfirmedMonths": [
                {"month": f"{m['year']}년 {m['month']}월", "reason": "임시저장(미확정)" if m["reason"] == "draft" else "입력 없음"}
                for m in confirmation["unconfirmed_months"]
            ],
            "partial": confirmation["is_partial"],
        },
        "revenue": {"total": won_short(revenue["total"]), "items": shares(revenue["items"], " 매출")},
        "expense": {
            "total": won_short(costs["total"]),
            "purchaseTotal": won_short(cost_sum({"merchandise_purchase", "material_purchase"})),  # 매입 = 상품 + 원재료
            "operatingTotal": won_short(cost_sum({"expense", "other_expense"})),  # 경비 = 경비 + 그 외 지출
            "items": shares(costs["items"]),
            "otherDetail": shares(costs["other_items"]),
        },
        "profit": {
            "estimatedProfit": won_short(profit["amount"]),
            "margin": _pct(profit["margin"]),
            "costBasis": "간이 이익 = 총매출 − 매입·지출 합계(상품·원재료 매입 + 경비 + 그 외 지출)",
        },
        "changes": {
            "previousQuarter": _comparison(summary["changes"]["previous"], labels),
            "sameQuarterLastYear": _comparison(summary["changes"]["last_year"], labels),
        },
        "target": target,
        "receivables": receivables,
    }


def hash_input(data):
    """키 순서와 무관하게 같은 값이면 같은 해시 (저장 후 데이터가 바뀌었는지 비교)"""
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def annotations(summary, quarter):
    """AI 에 보내지 않고 서버가 붙이는 내용: 연간 목표 한 줄 + 장기 미수금 거래처(금액 큰 순 3곳)"""
    targets = summary["targets"]
    if targets and targets["annual"]["target"]:
        annual = targets["annual"]["target"]
        cumulative = _cumulative(targets, quarter)
        headline = f"연간 목표 {won_short(annual)} 중 {won_short(cumulative)}({cumulative / annual * 100:.1f}%)를 달성했습니다."
    else:
        headline = f"{summary['period']['label']} 확정 매출은 {won_short(summary['revenue']['total'])}입니다. (연간 목표 미설정)"
    long_overdue = []
    month = summary["receivables"]["month"]
    if month:
        rows = (
            LedgerEntry.objects.filter(
                kind=LedgerEntry.Kind.AR, ar_status=LedgerEntry.ArStatus.LONG_OVERDUE, deleted_at__isnull=True, **month
            )
            .values("partner_name").annotate(total=Sum("amount")).order_by("-total", "partner_name")[:LONG_OVERDUE_MAX]
        )
        long_overdue = [{"name": r["partner_name"], "amount": won_short(r["total"])} for r in rows if r["total"] > 0]
    return {"headline": headline, "long_overdue": long_overdue}


# ---------- 프롬프트 (내용을 바꾸면 PROMPT_VERSION 도 올린다 → 화면에 "분석 기준이 바뀌었습니다") ----------

SYSTEM_PROMPT = f"""당신은 전동밸브조작기 제조사(직원 12명)의 경영지원팀을 돕는 매출 분석 보조자입니다.
주어진 분기 매출 데이터만 근거로, 경영지원 팀장이 30초 안에 읽을 수 있는 짧은 분석 코멘트를 작성합니다.
연간 목표 달성 한 줄 요약은 화면이 따로 보여주므로 쓰지 않습니다.

[작성 규칙]
1. 입력 데이터에 있는 숫자와 사실만 사용합니다. 데이터에 없는 원인(시장 상황, 경쟁사, 계절성 등)은 추측하지 않습니다.
2. 금액은 입력에 적힌 표기("7.09억원", "6,668만원")를 그대로 쓰고, 비율은 소수점 첫째 자리까지 씁니다.
3. 모든 판단에는 근거 숫자를 함께 씁니다. 예: "기대치 대비 3.80억원 부족(진도 90.5%)"
4. 부족한 점은 목표 미달, 경과율 대비 뒤처짐, 전 분기 대비 감소처럼 데이터로 확인되는 것만 고릅니다.
5. 개선 제안은 다음 분기에 경영지원팀이 실제로 확인하거나 실행할 수 있는 행동으로 씁니다. "노력이 필요합니다" 같은 일반론은 쓰지 않습니다.
6. 부족한 점이 없으면 억지로 만들지 말고 빈 배열로 둡니다.
7. 문체는 보고서체 평서문("~입니다", "~했습니다")으로, 한 문장은 {SENTENCE_PROMPT_MAX}자 이내로 씁니다.
8. confirmation.unconfirmedMonths가 비어 있지 않으면 summary에서 어느 달이 미확정이라 집계에서 빠졌는지 밝힙니다. 증감 비교에 sameMonthsOnly가 있으면 같은 달끼리만 비교했다고 밝힙니다.
9. 값이 "비교 불가"로 표시된 항목은 숫자를 만들지 않고 비교할 수 없다고만 씁니다. 입력에 없는 비율·금액을 새로 계산하지 않습니다.
10. 거래처 이름은 입력에 없으므로 쓰지 않고 "장기 미수금 거래처"라고 씁니다. 화면이 대상 거래처를 따로 붙여 보여줍니다.
11. 미수금(receivables)은 경영지원 관리 외상매출금의 기준월(baseMonth) 잔액입니다. 경과일로 나누지 않고 담당자가 정한 "장기 미수금"으로 씁니다. baseMonth가 "입력 없음"이면 미수금은 언급하지 않습니다.

[출력 형식]
- summary(이번 기간 현황): 2~3개. ① 분기 매출과 제품·상품·용역 구분(revenue) ② 전 분기 대비 증감률(changes.previousQuarter) ③ 매입·경비 합계와 간이 이익(expense.purchaseTotal, expense.operatingTotal, profit.estimatedProfit). 미확정 달이 있으면 그 사실을 이 안에 넣습니다.
- shortfalls(부족한 점·주의): 0~3개, 중요한 순서. 기간 경과 기준 기대치 대비 부족이면(target.gapVsExpected가 "부족") 부족액과 진도(target.annualProgress)를 쓰고, 장기 미수금(receivables.longOverdue)이 있으면 금액·건수를 씁니다.
- improvements(다음 분기 개선할 점): 1~3개. shortfalls의 각 항목에 대응하는 제안을 같은 순서로 하나씩 먼저 쓰고, 남는 자리에 추가 제안을 씁니다."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "array", "items": {"type": "string"}},
        "shortfalls": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "shortfalls", "improvements"],
    "additionalProperties": False,
}


def user_message(data):
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return f"{data['period']} 경영 지표 집계값입니다 (확정된 달만 집계).\n\n```json\n{body}\n```"


def _clean(sentences, report):
    """공백 정리, 빈 문장 제거, 80자 초과는 79자 + "…", 3개까지"""
    out = []
    for s in sentences:
        s = " ".join(str(s).split())
        if not s:
            continue
        if len(s) > SENTENCE_MAX:
            report["truncated"] += 1
            s = s[: SENTENCE_MAX - 1] + "…"
        out.append(s)
    if len(out) > 3:
        report["dropped"] += len(out) - 3
    return out[:3]


def normalize(response):
    """AI 응답 → 저장 형식. 매출 현황 문장이 하나도 없을 때만 None"""
    report = {"truncated": 0, "dropped": 0}
    try:
        result = {k: _clean(response[k], report) for k in ("summary", "shortfalls", "improvements")}
    except (KeyError, TypeError):
        return None
    return (result, report) if result["summary"] else None


# ---------- 모의 응답·예시 (외부 AI 를 부르지 않음) ----------


def _unconfirmed_text(data):
    return "·".join(m["month"].split(" ", 1)[1] for m in data["confirmation"]["unconfirmedMonths"])


def _item(data, label):
    return next((i["amount"] for i in data["revenue"]["items"] if i["item"] == label), "0원")


def mock_comment(data):
    """개발용 모의 응답 (AI_MOCK=true) — 입력 숫자를 정해진 문장에 끼워 넣은 것이며 [모의]로 표시"""
    target = data["target"] if isinstance(data["target"], dict) else None
    unconfirmed = _unconfirmed_text(data)
    previous = data["changes"]["previousQuarter"]["revenue"]
    unavailable = previous.startswith("비교 불가")
    summary = [
        f"[모의] 매출 {data['revenue']['total']}(제품 {_item(data, '제품 매출')}·상품 {_item(data, '상품 매출')}·용역 {_item(data, '용역 매출')})입니다.",
        (f"[모의] {unconfirmed} 미확정, 같은 달끼리 전 분기 대비 {previous}입니다." if unconfirmed and not unavailable
         else f"[모의] {unconfirmed} 미확정, 전 분기와는 비교할 수 없습니다." if unconfirmed
         else "[모의] 전 분기와는 비교할 수 없습니다." if unavailable
         else f"[모의] 전 분기 대비 매출이 {previous} 변했습니다."),
        f"[모의] 매입 {data['expense']['purchaseTotal']}·경비 {data['expense']['operatingTotal']}, 간이 이익 {data['profit']['estimatedProfit']}입니다.",
    ]
    pairs = []
    if target and target["gapVsExpected"].endswith("부족"):
        pairs.append((f"[모의] 기대치 대비 {target['gapVsExpected']}입니다.", "[모의] 부족분만큼 수주·출하 일정을 앞당겨 점검합니다."))
    long_overdue = data["receivables"].get("longOverdue")
    if long_overdue and long_overdue["count"]:
        pairs.append((f"[모의] 장기 미수금 {long_overdue['amount']}({long_overdue['count']}건)입니다.", "[모의] 장기 미수금 거래처에 수금 일정을 확인합니다."))
    improvements = [fix for _, fix in pairs]
    improvements.append(f"[모의] {unconfirmed} 실적을 확정해 분석을 갱신합니다." if unconfirmed else "[모의] 실제 분석은 API 키를 넣고 AI_MOCK을 끈 뒤 확인합니다.")
    return {"summary": summary, "shortfalls": [issue for issue, _ in pairs], "improvements": improvements}


def _abs_pct(rate):
    return f"{abs(rate):.1f}%"


def _extreme_item(summary, direction):
    """전 분기 대비 가장 많이 줄어든(down)/늘어난(up) 매출 항목"""
    changes = summary["changes"]["previous"]["revenue_items"]
    items = [(i["label"], changes[i["key"]]["rate"]) for i in summary["revenue"]["items"] if changes[i["key"]]["rate"] is not None]
    items = [i for i in items if (i[1] < 0 if direction == "down" else i[1] > 0)]
    items.sort(key=lambda i: i[1] if direction == "down" else -i[1])
    return items[0] if items else None


def example_comment(summary, quarter):
    """seed_ai_examples 용 예시 문장 — 숫자는 모두 서버 계산값, 문장 틀만 정해져 있다 (프롬프트 규칙을 따름)"""
    data = build_input(summary, quarter)
    q = f"{quarter}분기"
    previous = summary["changes"]["previous"]
    unconfirmed = _unconfirmed_text(data)
    targets = summary["targets"]
    period_target = targets["period"] if targets else None
    exceeded = period_target is not None and period_target["rate"] is not None and period_target["rate"] >= 100
    rate = previous["revenue"]["rate"]

    if unconfirmed and rate is not None:
        change = f"{unconfirmed} 미확정, 같은 달끼리 {previous['label']} 대비 {_abs_pct(rate)} {'증가' if rate >= 0 else '감소'}했습니다."
    elif rate is None:
        change = f"{previous['label']} 확정 데이터가 없어 비교할 수 없습니다."
    elif rate == 0:
        change = f"{previous['label']} 대비 매출 변동이 없습니다."
    else:
        change = f"{previous['label']} 대비 매출이 {_abs_pct(rate)} {'증가' if rate > 0 else '감소'}했습니다."
    summary_sentences = [
        f"{q} 매출은 {data['revenue']['total']}(제품 {_item(data, '제품 매출')}, 상품 {_item(data, '상품 매출')}, 용역 {_item(data, '용역 매출')})입니다.",
        change,
        f"분기 목표 {won_short(period_target['target'])}의 {_abs_pct(period_target['rate'])}로 초과 달성했습니다." if exceeded
        else f"매입·지출 합계는 {won_short(summary['costs']['total'])}, 간이 이익은 {won_short(summary['profit']['amount'])}입니다.",
    ]

    pairs = []
    if targets and targets["annual"]["target"]:
        expected = targets["annual"]["target"] * quarter // 4
        cumulative = _cumulative(targets, quarter)
        gap = expected - cumulative
        if gap > 0 and expected > 0:
            pairs.append((
                f"기간 경과 기대치보다 {won_short(gap)} 부족합니다(진도율 {cumulative / expected * 100:.1f}%).",
                f"분기 초 수주 잔고를 점검해 부족분 {won_short(gap)}을 월별로 배정합니다.",
            ))
    if not exceeded and period_target and period_target["rate"] is not None and not pairs:
        pairs.append((f"분기 목표 대비 {_abs_pct(period_target['rate'])}로 목표에 못 미쳤습니다.", "월별 수주 실적을 분기 목표와 매달 대조합니다."))
    down = _extreme_item(summary, "down") if rate is not None and rate < 0 else None
    if down:
        pairs.append((f"{down[0]} 매출이 {previous['label']} 대비 {_abs_pct(down[1])} 줄었습니다.", f"{down[0]} 매출 거래처별 발주 추이를 확인합니다."))
    long_overdue = data["receivables"].get("longOverdue")
    if long_overdue and long_overdue["count"]:
        pairs.append((
            f"장기 미수금이 {long_overdue['amount']}({long_overdue['count']}건)입니다.",
            f"장기 미수금 {long_overdue['count']}건의 수금 일정을 거래처별로 확정합니다.",
        ))
    top = pairs[:3]
    improvements = [fix for _, fix in top]
    if len(improvements) < 3:
        up = _extreme_item(summary, "up") if rate is not None else None
        improvements.append(
            f"{unconfirmed} 실적을 확정한 뒤 분석을 갱신합니다." if unconfirmed
            else f"증가 폭이 큰 {up[0]} 매출의 다음 분기 발주 계획을 미리 확인합니다." if up
            else "다음 분기 월별 수주 계획을 분기 목표에 맞춰 점검합니다."
        )
    return {"summary": summary_sentences, "shortfalls": [issue for issue, _ in top], "improvements": improvements}


# ---------- 화면 데이터 ----------


def latest_comment(year, quarter):
    return AiComment.objects.filter(year=year, quarter=quarter).select_related("created_by").order_by("-created_at", "-id").first()


def method_of(model):
    return "mock" if model == MOCK_MODEL else "example" if model == EXAMPLE_MODEL else "ai"


def comment_view(user, period, summary, today):
    """GET 응답: 분석 대상 분기, 최신 코멘트, 최신이 아닌 이유, 버튼 가능 여부"""
    target = target_quarter(period, summary)
    if target is None:
        return {"quarter": None, "notice": f"{period.label}에 확정된 달이 없어 분석할 분기가 없습니다."}
    year, quarter = target
    if period.kind != "quarter":
        summary = management_summary(make_period("quarter", year, quarter=quarter), today)
    row = latest_comment(year, quarter)
    stale = None
    if row:
        stale = "prompt" if row.prompt_version != PROMPT_VERSION else "data" if row.input_hash != hash_input(build_input(summary, quarter)) else None
    basis = (
        None if period.kind == "quarter"
        else f"{period.label}이 속한 분기의 분석입니다." if period.kind == "month"
        else f"{period.label} 중 확정된 달이 있는 마지막 분기의 분석입니다."
    )
    return {
        "year": year,
        "quarter": quarter,
        "quarter_label": f"{year}년 {quarter}분기",
        "basis_note": basis,
        "latest_id": row.id if row else None,
        "latest": {
            "id": row.id,
            "result": row.result,
            "created_at": row.created_at,
            "created_by": row.created_by.username if row.created_by else None,
            "method": method_of(row.model),
            "method_label": METHOD_LABELS[method_of(row.model)],
        } if row else None,
        "stale_reason": stale,
        "abilities": current_abilities(user, year, quarter, today, summary),
    }
