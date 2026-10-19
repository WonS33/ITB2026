from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import IsFullAccess
from .serializers import (
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
)
from .validators import generate_temporary_password


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


class AdminUserListView(APIView):
    """GET /api/admin/users/ — 직원 목록 (specs/02-users-permissions.md 6절)"""

    permission_classes = [IsFullAccess]

    def get(self, request):
        users = User.objects.order_by("username")
        return Response(AdminUserSerializer(users, many=True).data)


class AdminUserDetailView(APIView):
    """PATCH /api/admin/users/{id}/ — 역할·열람 범위·수정 권한 변경

    권한은 요청마다 DB에서 다시 읽으므로, 저장하는 즉시 그 직원의 API 권한에 반영된다.
    (그 직원의 화면 메뉴는 새로고침하거나 다시 로그인하면 바뀐다)
    """

    permission_classes = [IsFullAccess]

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(user).data)


class AdminPasswordResetView(APIView):
    """POST /api/admin/users/{id}/reset-password/ — 비밀번호 초기화

    서버가 임시 비밀번호를 만들어 해시로 저장하고, 원문은 이 응답에서 한 번만 돌려준다(DB에는 원문이 남지 않음).
    must_change_password=True로 바꿔 그 직원이 다음 로그인 때 비밀번호 변경 안내를 받게 한다.
    비밀번호 해시가 바뀌므로 그 직원이 이미 로그인해 있던 세션은 자동으로 끊긴다.
    """

    permission_classes = [IsFullAccess]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            return Response(
                {"detail": "본인 비밀번호는 [비밀번호 변경] 메뉴에서 바꿔 주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        temporary_password = generate_temporary_password(user)
        user.set_password(temporary_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        response = Response({"user": AdminUserSerializer(user).data, "temporary_password": temporary_password})
        response["Cache-Control"] = "no-store"  # 임시 비밀번호가 브라우저 캐시에 남지 않게
        return response
