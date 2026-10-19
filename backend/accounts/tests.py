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
        self.assertEqual(res.data["view_teams"], [P, S])
        self.assertEqual(res.data["edit_teams"], [P, S])

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
            (make_user("mgmt", User.Role.MANAGEMENT), 200, 200),
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
