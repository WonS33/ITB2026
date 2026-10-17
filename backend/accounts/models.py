from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models


class User(AbstractUser):
    """직원 계정. 역할(role)과 열람·수정 가능한 팀 목록으로 권한을 구분한다.

    specs/02-users-permissions.md 참고.
    """

    class Role(models.TextChoices):
        CEO = "ceo", "대표"
        MANAGEMENT = "management", "경영지원팀"
        ADMIN = "admin", "관리자"
        LEADER = "leader", "팀장"
        MEMBER = "member", "팀원"

    class Team(models.TextChoices):
        PRODUCTION = "production", "생산팀"
        SERVICE = "service", "서비스팀"

    # 이 역할은 팀 목록과 관계없이 전체 열람·전체 수정·관리자 페이지 사용 가능
    FULL_ACCESS_ROLES = (Role.CEO, Role.MANAGEMENT, Role.ADMIN)

    role = models.CharField("역할", max_length=20, choices=Role.choices, default=Role.MEMBER)
    view_teams = ArrayField(
        models.CharField(max_length=20, choices=Team.choices),
        verbose_name="열람 가능한 팀",
        default=list,
        blank=True,
    )
    edit_teams = ArrayField(
        models.CharField(max_length=20, choices=Team.choices),
        verbose_name="수정 가능한 팀",
        default=list,
        blank=True,
    )
    must_change_password = models.BooleanField("첫 로그인 비밀번호 변경 안내", default=True)

    @property
    def has_full_access(self):
        return self.role in self.FULL_ACCESS_ROLES

    def can_view(self, team):
        return self.has_full_access or team in self.view_teams

    def can_edit(self, team):
        return self.has_full_access or team in self.edit_teams
