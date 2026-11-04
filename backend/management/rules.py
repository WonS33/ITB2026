"""월간 입력 규칙 (조원 저장소 src/modules/management/entry/rules.ts 를 옮김)

- 미래 달: 입력 불가 / 이번 달: 임시저장만 ("월이 끝난 뒤 확정") / 지난 달: 확정까지
- 확정된 달: 확정 상태 그대로 수정하거나 확정 취소
- 권한: 경영지원팀 수정 권한(대표·관리자·경영지원팀 소속)이면 임시저장·확정 모두 가능
"""

FUTURE, CURRENT, CLOSED = "future", "current", "closed"
NEW, DRAFT, CONFIRMED = "new", "draft", "confirmed"


def month_state(year, month, today):
    target = year * 12 + month
    current = today.year * 12 + today.month
    if target > current:
        return FUTURE
    if target == current:
        return CURRENT
    return CLOSED


def entry_abilities(user, status, state):
    """화면 버튼과 저장 API가 같이 쓰는 "할 수 있는 일" 목록"""
    none = {
        "can_save_draft": False,
        "can_confirm": False,
        "can_edit_confirmed": False,
        "can_unconfirm": False,
        "read_only": True,
        "notice": None,
    }
    if state == FUTURE:
        return {**none, "notice": "미래 달은 입력할 수 없습니다."}
    if not user.can_edit("management"):
        return {**none, "notice": "입력 권한이 없습니다. (열람만 가능)"}
    if status == CONFIRMED:
        return {**none, "can_edit_confirmed": True, "can_unconfirm": True, "read_only": False}
    if state == CURRENT:
        return {
            **none,
            "can_save_draft": True,
            "read_only": False,
            "notice": "이번 달은 임시저장만 할 수 있습니다. 월이 끝난 뒤 확정할 수 있습니다.",
        }
    return {**none, "can_save_draft": True, "can_confirm": True, "read_only": False}


# 저장 요청(intent) → 필요한 능력
INTENT_ABILITY = {
    "draft": "can_save_draft",
    "confirm": "can_confirm",
    "update_confirmed": "can_edit_confirmed",
}
