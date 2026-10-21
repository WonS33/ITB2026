from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    """본인 비밀번호 변경. 새 비밀번호는 Django 기본 규칙(settings.AUTH_PASSWORD_VALIDATORS)으로 검사한다."""

    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["user"].check_password(value):
            raise serializers.ValidationError("현재 비밀번호가 올바르지 않습니다.")
        return value

    def validate(self, data):
        if data["current_password"] == data["new_password"]:
            raise serializers.ValidationError({"new_password": "현재 비밀번호와 다른 비밀번호를 입력해 주세요."})
        try:
            # 8자 이상, 흔한 비밀번호·숫자만·아이디와 비슷한 비밀번호 금지
            validate_password(data["new_password"], user=self.context["user"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return data


class MeSerializer(serializers.ModelSerializer):
    """로그인한 사용자 정보. 화면은 이 값으로 메뉴와 버튼을 보여줄지 정한다.

    view_teams, edit_teams는 실제 적용되는 권한을 돌려준다.
    (대표·관리자·경영지원팀 소속은 저장된 값과 관계없이 모든 팀)
    """

    name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    view_teams = serializers.SerializerMethodField()
    edit_teams = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "name",
            "role",
            "role_display",
            "has_full_access",
            "view_teams",
            "edit_teams",
            "must_change_password",
        ]

    def get_name(self, user):
        # 한국어 이름은 성+이름을 붙여 쓴다
        return f"{user.last_name}{user.first_name}" or user.username

    def get_view_teams(self, user):
        return [team for team in User.Team.values if user.can_view(team)]

    def get_edit_teams(self, user):
        return [team for team in User.Team.values if user.can_edit(team)]


class AdminUserSerializer(MeSerializer):
    """관리자 페이지 직원 목록 한 줄. 내 정보 항목에 마지막 로그인 시각을 더한다.

    view_teams, edit_teams는 체크박스에 쓰도록 DB에 저장된 값을 그대로 돌려준다.
    (대표·관리자·경영지원팀 소속은 저장된 값과 관계없이 전체 권한 → 화면에 "전체"로 표시)
    """

    view_teams = serializers.ListField(read_only=True)
    edit_teams = serializers.ListField(read_only=True)

    class Meta(MeSerializer.Meta):
        fields = MeSerializer.Meta.fields + ["last_login"]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """관리자가 직원의 역할·열람 범위·수정 권한을 바꿀 때 (PATCH, 보낸 항목만 바뀜)"""

    class Meta:
        model = User
        fields = ["role", "view_teams", "edit_teams"]

    def _clean_teams(self, value):
        # 중복을 없애고 생산팀 → 서비스팀 순서로 정리
        return [team for team in User.Team.values if team in value]

    def validate_view_teams(self, value):
        return self._clean_teams(value)

    def validate_edit_teams(self, value):
        return self._clean_teams(value)

    def validate(self, data):
        user = self.instance
        view_teams = data.get("view_teams", user.view_teams)
        edit_teams = data.get("edit_teams", user.edit_teams)
        if any(team not in view_teams for team in edit_teams):
            raise serializers.ValidationError({"edit_teams": "수정 권한이 있는 팀은 열람 권한도 있어야 합니다."})
        role = data.get("role", user.role)
        if user.pk == self.context["request"].user.pk and not User.is_full_access(role, view_teams):
            # 실수로 본인의 관리자 페이지 권한을 없애 아무도 관리할 수 없게 되는 일을 막는다
            raise serializers.ValidationError({"role": "본인의 전체 권한(관리자 페이지 사용)은 없앨 수 없습니다."})
        return data
