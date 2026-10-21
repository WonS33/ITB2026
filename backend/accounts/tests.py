from django.contrib.auth.password_validation import validate_password
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from rest_framework.views import APIView

from .models import User
from .permissions import TeamPermission

P = User.Team.PRODUCTION
S = User.Team.SERVICE


def make_user(username, role, view=(), edit=()):
    user = User(username=username, role=role, view_teams=list(view), edit_teams=list(edit))
    user.set_password("test-pass-1234")
    user.save()
    return user


class AuthApiTests(APITestCase):
    def setUp(self):
        self.user = make_user("prod_leader", User.Role.LEADER, [P], [P])

    def test_me_requires_login_401(self):
        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 401)

    def test_login_success_returns_permissions(self):
        res = self.client.post("/api/auth/login/", {"username": "prod_leader", "password": "test-pass-1234"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["view_teams"], [P])
        self.assertEqual(res.data["edit_teams"], [P])

        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["username"], "prod_leader")

    def test_login_wrong_password_400(self):
        res = self.client.post("/api/auth/login/", {"username": "prod_leader", "password": "wrong"})
        self.assertEqual(res.status_code, 400)

    def test_logout(self):
        self.client.post("/api/auth/login/", {"username": "prod_leader", "password": "test-pass-1234"})
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_full_access_role_sees_all_teams(self):
        make_user("boss", User.Role.CEO)
        self.client.post("/api/auth/login/", {"username": "boss", "password": "test-pass-1234"})
        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.data["view_teams"], [User.Team.MANAGEMENT, P, S])
        self.assertEqual(res.data["edit_teams"], [User.Team.MANAGEMENT, P, S])

    def test_password_is_hashed(self):
        self.assertNotEqual(self.user.password, "test-pass-1234")
        self.assertTrue(self.user.check_password("test-pass-1234"))


class ProductionDummyView(APIView):
    """권한 검사만 확인하기 위한 테스트용 뷰"""

    team = P
    permission_classes = [TeamPermission]

    def get(self, request):
        return Response("ok")

    def post(self, request):
        return Response("ok")


class TeamPermissionTests(APITestCase):
    """specs/02-users-permissions.md 2절 권한표"""

    factory = APIRequestFactory()

    def status_for(self, user, method):
        request = getattr(self.factory, method)("/dummy/")
        force_authenticate(request, user=user)
        return ProductionDummyView.as_view()(request).status_code

    def test_permission_table(self):
        cases = [
            # 사용자, 조회 결과, 입력 결과
            (make_user("ceo", User.Role.CEO), 200, 200),
            (make_user("mgmt", User.Role.MEMBER, [User.Team.MANAGEMENT]), 200, 200),
            (make_user("adm", User.Role.ADMIN), 200, 200),
            (make_user("p_leader", User.Role.LEADER, [P], [P]), 200, 200),
            (make_user("p_member", User.Role.MEMBER, [P]), 200, 403),
            (make_user("s_leader", User.Role.LEADER, [S], [S]), 403, 403),
            (make_user("s_member", User.Role.MEMBER, [S]), 403, 403),
            (make_user("dual", User.Role.MEMBER, [P, S]), 200, 403),  # 겸직: 두 팀 열람
        ]
        for user, expected_get, expected_post in cases:
            with self.subTest(user=user.username):
                self.assertEqual(self.status_for(user, "get"), expected_get)
                self.assertEqual(self.status_for(user, "post"), expected_post)

    def test_anonymous_is_rejected(self):
        request = self.factory.get("/dummy/")
        self.assertEqual(ProductionDummyView.as_view()(request).status_code, 401)


class PasswordChangeTests(APITestCase):
    """specs/02-users-permissions.md 5절: 본인 비밀번호 변경, 첫 로그인 안내"""

    def setUp(self):
        self.user = make_user("prod_leader", User.Role.LEADER, [P], [P])  # 새 계정은 must_change_password=True
        self.client.post("/api/auth/login/", {"username": "prod_leader", "password": "test-pass-1234"})

    def change(self, current, new):
        return self.client.post("/api/auth/password/", {"current_password": current, "new_password": new})

    def test_new_account_needs_password_change(self):
        self.assertTrue(self.client.get("/api/auth/me/").data["must_change_password"])

    def test_change_password_keeps_session_and_clears_notice(self):
        res = self.change("test-pass-1234", "Blue-Valve-2026!")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["must_change_password"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)  # 로그인 유지
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Blue-Valve-2026!"))
        self.assertNotIn("Blue-Valve-2026!", self.user.password)  # 해시로 저장

        self.client.post("/api/auth/logout/")
        old = self.client.post("/api/auth/login/", {"username": "prod_leader", "password": "test-pass-1234"})
        self.assertEqual(old.status_code, 400)  # 옛 비밀번호로는 로그인 안 됨

    def test_wrong_current_password(self):
        res = self.change("wrong", "Blue-Valve-2026!")
        self.assertEqual(res.status_code, 400)
        self.assertIn("current_password", res.data)

    def test_weak_or_same_new_password(self):
        weak_passwords = (
            "1234", "12345678", "password", "prod_leader1", "test-pass-1234",
            "Valve2026",  # 특수기호 없음
            "Valve-Blue!",  # 숫자 없음
            "2026-10-19!",  # 영문 없음
            "Va1!",  # 8자 미만
            "Blue Valve 2026!",  # 공백
            "밸브Valve2026!",  # 한글
        )
        for weak in weak_passwords:
            with self.subTest(weak=weak):
                res = self.change("test-pass-1234", weak)
                self.assertEqual(res.status_code, 400)
                self.assertIn("new_password", res.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)  # 실패하면 안내도 그대로

    def test_anonymous_401(self):
        self.client.post("/api/auth/logout/")
        self.assertEqual(self.change("a", "b").status_code, 401)


class AdminPasswordResetTests(APITestCase):
    """specs/02-users-permissions.md 6절: 관리자 비밀번호 초기화 (서버가 임시 비밀번호 생성)"""

    def setUp(self):
        self.admin = make_user("admin", User.Role.ADMIN)
        self.target = make_user("prod_member", User.Role.MEMBER, [P])
        self.target.must_change_password = False
        self.target.save()

    def login(self, username):
        self.client.post("/api/auth/login/", {"username": username, "password": "test-pass-1234"})

    def reset(self, user):
        return self.client.post(f"/api/admin/users/{user.pk}/reset-password/")

    def test_only_full_access_roles(self):
        make_user("prod_leader", User.Role.LEADER, [P], [P])
        for username, list_code, reset_code in (("prod_leader", 403, 403), ("prod_member", 403, 403)):
            with self.subTest(username=username):
                self.login(username)
                self.assertEqual(self.client.get("/api/admin/users/").status_code, list_code)
                self.assertEqual(self.reset(self.admin).status_code, reset_code)
                self.client.post("/api/auth/logout/")
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 401)  # 로그인 안 함
        full_access = (
            ("ceo", User.Role.CEO, []),
            ("mgmt_leader", User.Role.LEADER, [User.Team.MANAGEMENT]),
            ("mgmt_member", User.Role.MEMBER, [User.Team.MANAGEMENT]),  # 경영지원팀은 팀원도 전체 권한
        )
        for username, role, view in full_access:
            with self.subTest(username=username):
                make_user(username, role, view)
                self.login(username)
                self.assertEqual(self.client.get("/api/admin/users/").status_code, 200)
                self.client.post("/api/auth/logout/")

    def test_list(self):
        self.login("admin")
        res = self.client.get("/api/admin/users/")
        self.assertEqual([u["username"] for u in res.data], ["admin", "prod_member"])
        self.assertNotIn("password", res.data[0])

    def test_reset_creates_valid_temporary_password(self):
        self.login("admin")
        res = self.reset(self.target)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Cache-Control"], "no-store")
        temp = res.data["temporary_password"]
        validate_password(temp, user=self.target)  # 새 비밀번호 규칙 통과

        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(temp))
        self.assertNotIn(temp, self.target.password)  # 해시로 저장
        self.assertTrue(self.target.must_change_password)  # 다음 로그인 때 변경 안내
        self.assertNotEqual(self.reset(self.target).data["temporary_password"], temp)  # 매번 다름

    def test_reset_logs_out_target_and_old_password_fails(self):
        target_client = self.client_class()
        target_client.post("/api/auth/login/", {"username": "prod_member", "password": "test-pass-1234"})
        self.login("admin")
        temp = self.reset(self.target).data["temporary_password"]

        self.assertEqual(target_client.get("/api/auth/me/").status_code, 401)  # 기존 세션 끊김
        old = target_client.post("/api/auth/login/", {"username": "prod_member", "password": "test-pass-1234"})
        self.assertEqual(old.status_code, 400)
        new = target_client.post("/api/auth/login/", {"username": "prod_member", "password": temp})
        self.assertEqual(new.status_code, 200)
        self.assertTrue(new.data["must_change_password"])

    def test_cannot_reset_self_or_unknown(self):
        self.login("admin")
        self.assertEqual(self.reset(self.admin).status_code, 400)
        self.assertEqual(self.client.post("/api/admin/users/99999/reset-password/").status_code, 404)


class AdminUserUpdateTests(APITestCase):
    """specs/02-users-permissions.md 6절: 관리자가 체크박스로 권한을 바꾸면 즉시 반영"""

    def setUp(self):
        self.admin = make_user("admin", User.Role.ADMIN)
        self.target = make_user("svc_member", User.Role.MEMBER, [S])
        self.client.post("/api/auth/login/", {"username": "admin", "password": "test-pass-1234"})

    def patch(self, user, data):
        return self.client.patch(f"/api/admin/users/{user.pk}/", data, format="json")

    def test_change_teams_applies_immediately(self):
        target_client = self.client_class()
        target_client.post("/api/auth/login/", {"username": "svc_member", "password": "test-pass-1234"})
        self.assertEqual(target_client.get("/api/production/dashboard/").status_code, 403)

        res = self.patch(self.target, {"view_teams": [S, P, P]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["view_teams"], [P, S])  # 중복 제거, 순서 정리

        # 다시 로그인하지 않아도 바로 생산팀 조회 가능
        self.assertEqual(target_client.get("/api/auth/me/").data["view_teams"], [P, S])
        self.assertNotEqual(target_client.get("/api/production/dashboard/").status_code, 403)

    def test_change_role(self):
        res = self.patch(self.target, {"role": User.Role.LEADER, "edit_teams": [S]})
        self.assertEqual(res.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.LEADER)
        self.assertEqual(self.target.edit_teams, [S])
        self.assertEqual(self.target.view_teams, [S])  # 보내지 않은 항목은 그대로

    def test_edit_requires_view(self):
        res = self.patch(self.target, {"edit_teams": [P]})
        self.assertEqual(res.status_code, 400)
        self.assertIn("edit_teams", res.data)

    def test_invalid_values(self):
        self.assertEqual(self.patch(self.target, {"view_teams": ["sales"]}).status_code, 400)
        self.assertEqual(self.patch(self.target, {"role": "king"}).status_code, 400)

    def test_cannot_remove_own_full_access(self):
        res = self.patch(self.admin, {"role": User.Role.MEMBER})
        self.assertEqual(res.status_code, 400)
        self.assertIn("role", res.data)
        self.assertEqual(self.patch(self.admin, {"role": User.Role.CEO}).status_code, 200)
        # 경영지원팀 소속이면 팀장·팀원으로 바꿔도 전체 권한이 남으므로 허용
        res = self.patch(self.admin, {"role": User.Role.MEMBER, "view_teams": [User.Team.MANAGEMENT]})
        self.assertEqual(res.status_code, 200)
        # 그 상태에서 경영지원팀 소속을 빼면 전체 권한이 사라지므로 막음
        self.assertEqual(self.patch(self.admin, {"view_teams": [P]}).status_code, 400)

    def test_only_full_access_roles(self):
        leader = make_user("svc_leader", User.Role.LEADER, [S], [S])
        other = self.client_class()
        other.post("/api/auth/login/", {"username": "svc_leader", "password": "test-pass-1234"})
        res = other.patch(f"/api/admin/users/{leader.pk}/", {"role": User.Role.ADMIN}, format="json")
        self.assertEqual(res.status_code, 403)
        leader.refresh_from_db()
        self.assertEqual(leader.role, User.Role.LEADER)  # 스스로 관리자가 될 수 없음

    def test_other_fields_are_ignored(self):
        self.patch(self.target, {"username": "hacked", "password": "x", "is_superuser": True})
        self.target.refresh_from_db()
        self.assertEqual(self.target.username, "svc_member")
        self.assertFalse(self.target.is_superuser)
