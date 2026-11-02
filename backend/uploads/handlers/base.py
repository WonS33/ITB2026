"""파일 종류별 업로드 규칙의 공통 틀

파일 종류마다 UploadHandler를 하나 만들고 아래 일을 정의한다.
- parse(file): 파일에서 행을 뽑는다 (DB에 저장하지 않음)
- validate(values): 한 행의 누락·형식 오류를 찾는다
- duplicate_key(values) / existing_keys(keys): 중복 확인 기준 번호
- save(rows, user): 확인이 끝난 행을 DB에 저장한다
- (update_existing 종류만) existing_values(keys) / update(rows, user): 이미 있는 번호를 최신 값으로 고친다

추출 결과(rows)의 한 행 모양:
    {"row_no": 10, "sheet": "2026(NTI)", "values": {...}, "errors": {"필드": "메시지"},
     "duplicate": False, "excluded": False}
"""

from datetime import date


class UploadHandler:
    kind = ""
    team = ""  # 이 업로드를 할 수 있는 팀 (수정 권한 확인용)
    allowed_extensions = ()
    columns = []  # 확인 화면 표의 열: [(key, label), ...] 또는 (key, label, {"choices": [...], "multiline": True, "suggestions": 이름})
    key_field = ""  # 중복 확인 기준 번호가 들어 있는 열
    # True: 중복으로 잡힌 행을 사람이 "중복 아님"으로 확인하면 저장할 수 있다.
    # 기준이 고유 번호가 아닌 종류만 켠다 (예: 출장보고서 = 시작일+요청처). 일련번호·판매번호는 끈다.
    allow_duplicate_override = False
    # True: 이미 저장된 기준 번호가 다시 올라오면 건너뛰지 않고 **새로 올라온 값으로 갱신**한다 (최신 업로드 기준).
    # 같은 파일 안에서 같은 번호가 여러 번 나오면 **마지막 행만** 쓴다. 값이 하나도 안 바뀐 행은 건너뛴다.
    # (제조내역: 일련번호 기준, 2026-11-02 사용자 요청)
    update_existing = False

    def parse(self, file):
        """반환: (rows, skipped_count)"""
        raise NotImplementedError

    def validate(self, values):
        raise NotImplementedError

    def duplicate_key(self, values):
        return (values.get(self.key_field) or "").strip() or None

    def existing_keys(self, keys):
        raise NotImplementedError

    def existing_values(self, keys):
        """update_existing 종류만: {기준 번호: {칸: 지금 저장된 값(문자열)}}"""
        raise NotImplementedError

    def update(self, rows, user):
        """update_existing 종류만: 이미 있는 번호의 행을 새 값으로 고치고 고친 개수를 돌려준다."""
        raise NotImplementedError

    def validate_all(self, active_rows):
        """여러 행을 함께 봐야 하는 검사 (필요한 종류만 다시 정의). row["errors"]에 직접 추가한다."""

    def save(self, rows, user):
        """오류·중복·제외가 아닌 행(rows)을 DB에 저장하고 저장한 개수를 돌려준다."""
        raise NotImplementedError

    def suggestions(self):
        """확인 화면의 추천 목록 {이름: [값, ...]} — 열 옵션 {"suggestions": 이름}이 있는 종류만 다시 정의"""
        return {}


def check_rows(handler, rows):
    """모든 행을 다시 검사해서 errors·duplicate를 채운다. 제외(excluded)한 행은 검사하지 않는다."""
    if handler.update_existing:
        return _check_rows_latest(handler, rows)
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


def _check_rows_latest(handler, rows):
    """최신 업로드 기준 검사 (update_existing 종류)

    - superseded: 같은 파일 아래쪽에 같은 번호가 다시 나와 이 행은 쓰지 않음 (마지막 행 기준)
    - update: 이미 저장된 번호인데 값이 바뀜 → 저장할 때 새 값으로 갱신, changes에 바뀐 칸(이전 → 새 값)
    - duplicate: 저장할 때 건너뛰는 행 = superseded 이거나, 이미 저장된 번호인데 바뀐 값이 없음
    """
    active = [r for r in rows if not r.get("excluded")]
    keys = [handler.duplicate_key(r["values"]) for r in active]
    last = {key: i for i, key in enumerate(keys) if key}
    counts = {}
    for key in keys:
        if key:
            counts[key] = counts.get(key, 0) + 1
    existing = handler.existing_values({k for k in keys if k})

    for i, (row, key) in enumerate(zip(active, keys)):
        errors = handler.validate(row["values"])
        superseded = bool(key and last[key] != i)
        row["superseded"] = superseded
        row["in_file_duplicate"] = bool(key and counts[key] > 1)
        row["matches_existing"] = bool(key and key in existing)
        changes = {}
        if row["matches_existing"] and not superseded:
            for field, old in existing[key].items():
                new = (row["values"].get(field) or "").strip()
                if old != new:
                    changes[field] = {"old": old, "new": new}
        row["changes"] = changes
        row["update"] = row["matches_existing"] and bool(changes) and not superseded
        row["duplicate"] = superseded or (row["matches_existing"] and not changes)
        row["errors"] = {} if row["duplicate"] else errors  # 건너뛸 행은 고칠 필요가 없음
    handler.validate_all([r for r in active if not r["duplicate"]])
    for row in rows:
        if row.get("excluded"):
            row["errors"], row["duplicate"], row["changes"] = {}, False, {}
            row["matches_existing"] = row["in_file_duplicate"] = row["superseded"] = row["update"] = False
    return rows


def column_specs(handler):
    """확인 화면에 보낼 열 정보. choices가 있으면 선택 목록, multiline이면 여러 줄 입력으로 보여준다.
    choices_by가 있으면 같은 행의 다른 칸 값에 따라 choices_map[그 값] 목록을 보여준다 (예: 시·도 → 시·군).
    suggestions가 있으면 직접 입력하면서 고를 수 있는 추천 목록을 붙인다 (예: 견적서 품명 → 부품명)."""
    specs = []
    lists = None
    for key, label, *options in handler.columns:
        spec = {"key": key, "label": label, **(options[0] if options else {})}
        if "suggestions" in spec:
            lists = handler.suggestions() if lists is None else lists
            spec["suggestions"] = lists.get(spec["suggestions"], [])
        specs.append(spec)
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
        # 최신 업로드 기준 종류: 저장 예정 중 갱신할 행, 건너뛰는 행 중 파일 아래 행으로 대체된 행
        "update_rows": sum(1 for r in active if r.get("update") and not r["errors"]),
        "superseded_rows": sum(1 for r in active if r.get("superseded")),
        "skipped_rows": skipped_count,  # 추출 단계에서 건너뛴 행 (예: 일련번호 없는 행)
    }


def parse_iso_date(text):
    """'YYYY-MM-DD' 문자열 → date. 빈 값이면 None, 형식이 틀리면 ValueError."""
    text = (text or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)
