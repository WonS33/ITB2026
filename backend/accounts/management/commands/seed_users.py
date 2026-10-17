import os

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User

P = User.Team.PRODUCTION
S = User.Team.SERVICE

# 개발·시연용 가상 계정 (실제 직원 정보 아님)
SEED_USERS = [
    # username, 성, 이름, 역할, 열람 팀, 수정 팀
    ("admin", "관", "리자", User.Role.ADMIN, [], []),
    ("prod_leader", "김", "생산", User.Role.LEADER, [P], [P]),
    ("prod_member", "이", "생산", User.Role.MEMBER, [P], []),
    ("svc_leader", "박", "서비스", User.Role.LEADER, [S], [S]),
    ("svc_member", "최", "서비스", User.Role.MEMBER, [S], []),
    ("dual_member", "정", "겸직", User.Role.MEMBER, [P, S], []),
]


class Command(BaseCommand):
    help = "개발·시연용 가상 계정을 만든다. 비밀번호는 .env의 SEED_USER_PASSWORD를 쓴다."

    def handle(self, *args, **options):
        password = os.environ.get("SEED_USER_PASSWORD")
        if not password:
            raise CommandError(".env에 SEED_USER_PASSWORD를 먼저 적어 주세요.")

        for username, last, first, role, view, edit in SEED_USERS:
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    "last_name": last,
                    "first_name": first,
                    "role": role,
                    "view_teams": view,
                    "edit_teams": edit,
                    "must_change_password": True,
                    # admin 계정만 Django 기본 관리 화면에 들어갈 수 있게 한다
                    "is_staff": role == User.Role.ADMIN,
                    "is_superuser": role == User.Role.ADMIN,
                },
            )
            user.set_password(password)  # 해시로 저장 (Django 기본 기능)
            user.save()
            self.stdout.write(f"{'생성' if created else '갱신'}: {username} ({user.get_role_display()})")
