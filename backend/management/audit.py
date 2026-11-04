"""변경 기록 넣기·읽기 도우미 (조원 저장소 src/shared/audit/*, management/audit-fields.ts, history/labels.ts 를 옮김)

- 원래 저장과 같은 transaction.atomic() 안에서 부른다 → 기록이 실패하면 저장도 함께 취소된다
- 바뀐 칸만, 화면 표기 그대로의 글자로 ("12,500,000원"). 수정인데 바뀐 칸이 없으면 기록하지 않는다
- 비밀번호·해시·토큰 같은 칸 이름이 들어오면 저장하지 않고 오류 (두 번째 안전장치)
"""

import re

from django.utils import timezone

from .models import AuditLog, MonthlyFinance
from .serializers import VALUE_FIELDS

# 동작 → 화면 표기
ACTION_LABELS = {
    "CREATE": "추가",
    "UPDATE": "수정",
    "DELETE": "삭제",
    "CONFIRM": "확정",
    "UPDATE_CONFIRMED": "확정 후 수정",
    "UNCONFIRM": "확정 취소",
    "COLLECT": "수금 처리",
    "UNCOLLECT": "수금 취소",
    "HIDE": "숨김",
    "RESTORE": "복구",
    "IMPORT": "엑셀 이관",
    "EXPORT": "엑셀 다운로드",
}
# 기록하는 화면 → 화면 표기
SCREEN_LABELS = {
    "entry": "월간 입력",
    "entry-export": "월간 입력 엑셀 다운로드",
    "targets": "목표 설정",
    "expense-categories": "지출 항목",
    "targets-export": "목표 대비 실적 엑셀 다운로드",
    "receivables": "미수금 건별 기록",
    "receivables-export": "미수금 엑셀 다운로드",
    "ledger": "경영지원 관리",
    "ledger-copy": "경영지원 관리 지난달 불러오기",
    "ledger-import": "경영지원 관리 엑셀 이관",
}

_FORBIDDEN = re.compile(r"pass(word|wd)?|hash|token|secret|session|salt|credential|apikey|api_key", re.I)


class AuditForbiddenFieldError(ValueError):
    pass


def _forbidden_keys(value, path=""):
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            here = f"{path}.{k}" if path else str(k)
            if _FORBIDDEN.search(str(k)):
                found.append(here)
            found += _forbidden_keys(v, here)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            found += _forbidden_keys(v, f"{path}[{i}]")
    return found


def won(value):
    """금액 → "12,500,000원" (빈 값은 None)"""
    return None if value is None else f"{value:,}원"


def record_audit(*, actor, screen, action, target_type, target_id, target_label, changes=(), meta=None):
    changes = list(changes)
    forbidden = [c["field"] for c in changes if _FORBIDDEN.search(c["field"])] + _forbidden_keys(meta or {}, "meta")
    if forbidden:
        raise AuditForbiddenFieldError(f"변경 기록에 넣을 수 없는 칸이 있습니다: {', '.join(forbidden)}")
    if action in ("UPDATE", "UPDATE_CONFIRMED") and not changes:
        return None  # 수정인데 바뀐 칸이 없으면 기록하지 않는다
    return AuditLog.objects.create(
        occurred_at=timezone.now(),
        actor=actor,
        actor_username=actor.username,
        screen=screen,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        target_label=target_label,
        changes=changes,
        meta=meta,
    )


# ---------- 월간 입력 ----------

STATUS_LABELS = dict(MonthlyFinance.Status.choices)
VALUE_LABELS = {f: MonthlyFinance._meta.get_field(f).verbose_name for f in VALUE_FIELDS}


def monthly_label(year, month):
    return f"{year}년 {month}월 월간 입력"


def monthly_snapshot(finance):
    """저장 전 그 달 값 (변경 기록의 "바뀌기 전"). 처음 입력하는 달은 None"""
    if finance is None:
        return None
    return {
        "status": finance.status,
        "values": {f: getattr(finance, f) for f in VALUE_FIELDS},
        "others": {e.category_id: e.amount for e in finance.other_expenses.all()},
        "cash_balance": finance.cash_balance,
    }


def monthly_changes(before, after, category_names):
    """상태, 금액 6칸, 월말 통장 잔액, 그 외 지출 항목별로 바뀐 칸만"""
    changes = []

    def add(field, label, b, a):
        if b != a:
            changes.append({"field": field, "label": label, "before": b, "after": a})

    status = lambda s: STATUS_LABELS.get(s) if s else None  # noqa: E731
    add("status", "상태", status(before and before["status"]), status(after["status"]))
    for f in VALUE_FIELDS:
        add(f, VALUE_LABELS[f], won(before["values"][f]) if before else None, won(after["values"][f]))
    add("cash_balance", "월말 통장 잔액", won(before and before["cash_balance"]), won(after["cash_balance"]))
    ids = set(before["others"] if before else {}) | set(after["others"])
    for cid in sorted(ids):
        b = won(before["others"].get(cid)) if before else None
        a = won(after["others"].get(cid))
        if (b or "0원") == (a or "0원"):  # 0원 ↔ 빈 값은 화면에서 같게 보이므로 기록하지 않음
            continue
        add("other_expense", f"그 외 지출 · {category_names.get(cid, '(삭제된 항목)')}", b, a)
    return changes


# ---------- 공통: 기록할 칸 목록(허용 목록)에 있는 칸만, 바뀐 칸만 ----------


def diff_fields(before, after, fields):
    """before/after: 칸 이름 → 값 (추가는 before=None, 삭제는 after=None). fields: [(칸, 화면 이름, 표기 함수)]"""
    changes = []
    for key, label, fmt in fields:
        b = fmt(before[key]) if before else None
        a = fmt(after[key]) if after else None
        if b != a:
            changes.append({"field": key, "label": label, "before": b, "after": a})
    return changes


def text(value):
    return None if value in (None, "") else str(value)


# ---------- 목표 설정 ----------


def _quarter(value):
    return "자동 배분" if value is None else won(value)


TARGET_FIELDS = [
    ("target_amount", "연간 목표매출액", won),
    ("q1_target", "1분기 목표", _quarter),
    ("q2_target", "2분기 목표", _quarter),
    ("q3_target", "3분기 목표", _quarter),
    ("q4_target", "4분기 목표", _quarter),
    ("headcount", "직원 수", lambda v: None if v is None else f"{v}명"),
]


def target_label(year):
    return f"{year}년 목표"


# ---------- 그 외 지출 항목 ----------

COST_TYPE_LABELS = {"fixed": "고정비", "variable": "변동비"}
CATEGORY_FIELDS = [
    ("name", "항목 이름", text),
    ("cost_type", "고정비/변동비", lambda v: COST_TYPE_LABELS.get(v) if v else None),
    ("is_active", "사용", lambda v: "사용" if v else "비활성"),
]


# ---------- 미수금 건별 기록 ----------


def _date(value):
    return None if value is None else value.isoformat()


RECEIVABLE_FIELDS = [
    ("customer_name", "거래처", text),
    ("occurred_on", "발생일", _date),
    ("amount", "금액", won),
    ("due_on", "수금 예정일", _date),
    ("note", "비고", text),
    ("is_collected", "상태", lambda v: "수금 완료" if v else "미수"),
    ("collected_on", "수금일", _date),
]


def receivable_snapshot(r):
    return {f: getattr(r, f) for f, _, _ in RECEIVABLE_FIELDS}


def receivable_label(r):
    return f"{r.customer_name} · {r.occurred_on.isoformat()} 발생"


# ---------- 경영지원 관리 장부 ----------


def ledger_fields(kind):
    """구분마다 화면에 있는 칸만 (거래처코드·상태는 외상매출금, 매입유형은 외상매입금, 비용유형·자동이체는 업체)"""
    from .models import LedgerEntry as L

    word = "수금" if kind == L.Kind.AR else "지급"
    fields = []
    if kind == L.Kind.AR:
        fields += [("partner_code", "코드", text), ("ar_status", "상태", lambda v: dict(L.ArStatus.choices).get(v) if v else None)]
    if kind == L.Kind.AP:
        fields += [("purchase_type", "매입유형", lambda v: dict(L.PurchaseType.choices).get(v) if v else None)]
    if kind == L.Kind.ACCRUED_VENDOR:
        fields += [
            ("expense_type", "비용유형", lambda v: dict(L.ExpenseType.choices).get(v) if v else None),
            ("auto_transfer", "자동이체", lambda v: "자동이체" if v else None),
        ]
    return fields + [
        ("partner_name", "거래처명", text),
        ("amount", "잔액", won),
        ("note", "적요", text),
        ("due_on", f"{word} 예정일", _date),
        ("settled_on", f"{word} 완료일", _date),
    ]


LEDGER_SNAPSHOT_FIELDS = (
    "ar_status", "purchase_type", "expense_type", "auto_transfer", "partner_code",
    "partner_name", "amount", "note", "due_on", "settled_on",
)


def ledger_snapshot(e):
    return {f: getattr(e, f) for f in LEDGER_SNAPSHOT_FIELDS}


def ledger_label(e):
    # 예: "2026-10 외상매출금 · 가나상사"
    return f"{e.year}-{e.month:02d} {e.get_kind_display()} · {e.partner_name}"


# ---------- 화면 표시 ----------


def _actor_text(log):
    user = log.actor
    name = f"{user.last_name}{user.first_name}" if user else ""
    return f"{name}({log.actor_username})" if name else log.actor_username


def _meta_line(log):
    m = log.meta or {}
    if log.screen == "ledger-copy":
        parts = [
            f"{m['from']} → {m['month']}" if m.get("from") else None,
            f"{m['saved_rows']}행 저장" if isinstance(m.get("saved_rows"), int) else None,
            f"당월 수금 {m['collected_rows']}행 {m.get('include_collected', '')}".strip() if m.get("collected_rows") else None,
        ]
        return " · ".join(p for p in parts if p) or None
    if log.screen == "ledger-import":
        parts = [
            m.get("month"),
            m.get("mode"),
            f"{m['saved_rows']}행 저장" if isinstance(m.get("saved_rows"), int) else None,
            f"숨긴 기존 행 {m['hidden_rows']}" if isinstance(m.get("hidden_rows"), int) else None,
            f"제외 {m['excluded_rows']}행" if m.get("excluded_rows") else None,
            m.get("file_name"),
        ]
        return " · ".join(p for p in parts if p) or None
    if log.action == "EXPORT":
        parts = [
            m.get("period"),
            f"시트 {m['sheet_count']}장" if isinstance(m.get("sheet_count"), int) else None,
            m.get("file_name"),
        ]
        return " · ".join(p for p in parts if p) or None
    return None


def present(log):
    lines = [f"{c['label']}: {c['before'] or '(없음)'} → {c['after'] or '(없음)'}" for c in log.changes or []]
    meta = _meta_line(log)
    return {
        "id": log.id,
        "occurred_at": timezone.localtime(log.occurred_at).strftime("%Y-%m-%d %H:%M"),
        "actor": _actor_text(log),
        "screen": SCREEN_LABELS.get(log.screen, log.screen),
        "action": ACTION_LABELS.get(log.action, log.action),
        "target": log.target_label,
        "lines": lines + ([meta] if meta else []),
    }
