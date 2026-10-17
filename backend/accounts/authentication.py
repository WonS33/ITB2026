from rest_framework.authentication import SessionAuthentication


class SessionAuthentication401(SessionAuthentication):
    """세션 인증. 로그인하지 않은 요청에 403 대신 401을 돌려준다.

    DRF 기본 SessionAuthentication은 "인증 방법 안내(WWW-Authenticate)"를 주지 않아서
    미로그인 요청도 403으로 응답한다. specs/08-api.md 규칙(미로그인 401, 권한 없음 403)에
    맞추기 위해 안내 값을 돌려주도록 바꾼다.
    """

    def authenticate_header(self, request):
        return "Session"
