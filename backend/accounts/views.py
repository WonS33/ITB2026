from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, MeSerializer, PasswordChangeSerializer


class LoginView(APIView):
    """POST /api/auth/login/ — 아이디·비밀번호로 로그인하고 세션을 만든다."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            return Response(
                {"detail": "아이디 또는 비밀번호가 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    """POST /api/auth/logout/ — 세션을 지운다."""

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """GET /api/auth/me/ — 내 정보와 권한.

    화면이 처음 열릴 때 호출한다. 이때 CSRF 쿠키(위조 요청 방지용 토큰)도 함께 내려준다.
    로그인하지 않았으면 401을 돌려준다.
    """

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class PasswordChangeView(APIView):
    """POST /api/auth/password/ — 본인 비밀번호 변경 (specs/02-users-permissions.md 5절)

    현재 비밀번호를 확인한 뒤 새 비밀번호를 해시로 저장하고(set_password), 첫 로그인 안내를 끈다.
    """

    def post(self, request):
        user = request.user
        serializer = PasswordChangeSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, user)  # 비밀번호를 바꿔도 지금 로그인은 유지
        return Response(MeSerializer(user).data)
