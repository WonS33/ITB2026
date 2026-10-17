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
