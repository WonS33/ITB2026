from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models


class User(AbstractUser):
    """직원 계정. 역할(role)과 열람·수정 가능한 팀 목록으로 권한을 구분한다.

    specs/02-users-permissions.md 참고.
    """

    class Role(models.TextChoices):
        CEO = "ceo", "대표"
        ADMIN = "admin", "관리자"
        LEADER = "leader", "팀장"
        MEMBER = "member", "팀원"

    class Team(models.TextChoices):
        MANAGEMENT = "management", "경영지원팀"
        PRODUCTION = "production", "생산팀"
        SERVICE = "service", "서비스팀"

    # 이 역할은 팀 목록과 관계없이 전체 열람·전체 수정·관리자 페이지 사용 가능
    FULL_ACCESS_ROLES = (Role.CEO, Role.ADMIN)
    # 이 팀 소속(열람 범위에 포함)이면 팀장·팀원 모두 전체 권한 (권한표: 경영지원팀 = 전체 열람·수정·관리자 페이지)
    FULL_ACCESS_TEAM = Team.MANAGEMENT

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

    @staticmethod
    def is_full_access(role, view_teams):
        """역할과 열람 팀 목록만으로 전체 권한인지 판단 (저장 전 값 검사에도 쓴다)"""
        return role in User.FULL_ACCESS_ROLES or User.FULL_ACCESS_TEAM in view_teams

    @property
    def has_full_access(self):
        return self.is_full_access(self.role, self.view_teams)

    def can_view(self, team):
        return self.has_full_access or team in self.view_teams

    def can_edit(self, team):
        return self.has_full_access or team in self.edit_teams
