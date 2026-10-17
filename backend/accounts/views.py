from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, MeSerializer


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
