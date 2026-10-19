import string

from django.core.exceptions import ValidationError

# 쓸 수 있는 특수기호: 키보드의 ASCII 특수기호 32개. 화면 안내 문구(frontend/src/passwordRules.js)와 같아야 한다.
SPECIAL_CHARS = string.punctuation  # !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~


class CharacterMixValidator:
    """영문·숫자·특수기호를 각각 1개 이상 섞어 쓰게 한다 (specs/02-users-permissions.md 5절).

    공백·한글처럼 위 세 종류가 아닌 글자는 쓸 수 없다(키보드 입력 실수·한영 전환 실수 방지).
    """

    def validate(self, password, user=None):
        errors = []
        if not any(c in string.ascii_letters for c in password):
            errors.append("영문자를 1개 이상 넣어 주세요.")
        if not any(c in string.digits for c in password):
            errors.append("숫자를 1개 이상 넣어 주세요.")
        if not any(c in SPECIAL_CHARS for c in password):
            errors.append("특수기호를 1개 이상 넣어 주세요.")
        allowed = string.ascii_letters + string.digits + SPECIAL_CHARS
        if any(c not in allowed for c in password):
            errors.append("영문·숫자·특수기호만 쓸 수 있습니다. 공백이나 한글은 쓸 수 없습니다.")
        if errors:
            raise ValidationError(errors, code="password_character_mix")

    def get_help_text(self):
        return f"영문·숫자·특수기호({SPECIAL_CHARS})를 각각 1개 이상 섞어 주세요."
