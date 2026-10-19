"""파일 종류별 업로드 규칙의 공통 틀

파일 종류마다 UploadHandler를 하나 만들고 아래 일을 정의한다.
- parse(file): 파일에서 행을 뽑는다 (DB에 저장하지 않음)
- validate(values): 한 행의 누락·형식 오류를 찾는다
- duplicate_key(values) / existing_keys(keys): 중복 확인 기준 번호
- save(rows, user): 확인이 끝난 행을 DB에 저장한다

추출 결과(rows)의 한 행 모양:
    {"row_no": 10, "sheet": "2026(NTI)", "values": {...}, "errors": {"필드": "메시지"},
     "duplicate": False, "excluded": False}
"""

from datetime import date


class UploadHandler:
    kind = ""
    team = ""  # 이 업로드를 할 수 있는 팀 (수정 권한 확인용)
    allowed_extensions = ()
    columns = []  # 확인 화면 표의 열: [(key, label), ...] 또는 (key, label, {"choices": [...], "multiline": True})
    key_field = ""  # 중복 확인 기준 번호가 들어 있는 열
    # True: 중복으로 잡힌 행을 사람이 "중복 아님"으로 확인하면 저장할 수 있다.
    # 기준이 고유 번호가 아닌 종류만 켠다 (예: 출장보고서 = 시작일+요청처). 일련번호·판매번호는 끈다.
    allow_duplicate_override = False

    def parse(self, file):
        """반환: (rows, skipped_count)"""
        raise NotImplementedError

    def validate(self, values):
        raise NotImplementedError

    def duplicate_key(self, values):
        return (values.get(self.key_field) or "").strip() or None

    def existing_keys(self, keys):
        raise NotImplementedError

    def validate_all(self, active_rows):
        """여러 행을 함께 봐야 하는 검사 (필요한 종류만 다시 정의). row["errors"]에 직접 추가한다."""

    def save(self, rows, user):
        """오류·중복·제외가 아닌 행(rows)을 DB에 저장하고 저장한 개수를 돌려준다."""
        raise NotImplementedError


def check_rows(handler, rows):
    """모든 행을 다시 검사해서 errors·duplicate를 채운다. 제외(excluded)한 행은 검사하지 않는다."""
    active = [r for r in rows if not r.get("excluded")]
    keys = [handler.duplicate_key(r["values"]) for r in active]
    existing = handler.existing_keys({k for k in keys if k})

    seen = set()
    for row, key in zip(active, keys):
        errors = handler.validate(row["values"])
        # 사람이 "중복 아님"으로 확인한 행 (허용하는 종류만)
        override = handler.allow_duplicate_override and bool(row.get("allow_duplicate"))
        row["in_file_duplicate"] = bool(key and key in seen)
        row["matches_existing"] = bool(key and key in existing)
        if row["in_file_duplicate"] and not override and handler.key_field not in errors:
            errors[handler.key_field] = "파일 안에서 같은 기준 번호가 이미 나왔습니다."
        if key:
            seen.add(key)
        row["duplicate"] = row["matches_existing"] and not override  # 이미 DB에 있음 → 저장 때 건너뜀
        # 건너뛸 행은 고칠 필요가 없으므로 오류를 표시하지 않는다
        row["errors"] = {} if row["duplicate"] else errors
    handler.validate_all([r for r in active if not r["duplicate"]])
    for row in rows:
        if row.get("excluded"):
            row["errors"], row["duplicate"] = {}, False
            row["matches_existing"] = row["in_file_duplicate"] = False
    return rows


def column_specs(handler):
    """확인 화면에 보낼 열 정보. choices가 있으면 선택 목록, multiline이면 여러 줄 입력으로 보여준다.
    choices_by가 있으면 같은 행의 다른 칸 값에 따라 choices_map[그 값] 목록을 보여준다 (예: 시·도 → 시·군)."""
    specs = []
    for key, label, *options in handler.columns:
        specs.append({"key": key, "label": label, **(options[0] if options else {})})
    return specs


def column_keys(handler):
    return [column[0] for column in handler.columns]


def summarize(rows, skipped_count=0):
    active = [r for r in rows if not r.get("excluded")]
    return {
        "total": len(rows),
        "error_rows": sum(1 for r in active if r["errors"]),
        "duplicate_rows": sum(1 for r in active if r["duplicate"] and not r["errors"]),
        "excluded_rows": len(rows) - len(active),
        "to_save": sum(1 for r in active if not r["errors"] and not r["duplicate"]),
        "skipped_rows": skipped_count,  # 추출 단계에서 건너뛴 행 (예: 일련번호 없는 행)
    }


def parse_iso_date(text):
    """'YYYY-MM-DD' 문자열 → date. 빈 값이면 None, 형식이 틀리면 ValueError."""
    text = (text or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)
