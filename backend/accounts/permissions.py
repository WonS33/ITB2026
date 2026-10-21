from rest_framework.permissions import SAFE_METHODS, BasePermission


class TeamPermission(BasePermission):
    """팀 데이터 권한 검사. 뷰에 `team = "production"`처럼 팀 이름을 지정해서 쓴다.

    - 조회(GET 등): 그 팀 열람 권한이 있어야 한다
    - 입력·수정·삭제(POST, PUT, PATCH, DELETE): 그 팀 수정 권한이 있어야 한다
    - 대표·관리자·경영지원팀 소속은 항상 통과한다 (User.has_full_access)
    """

    message = "이 팀 데이터에 대한 권한이 없습니다."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        team = view.team
        if request.method in SAFE_METHODS:
            return user.can_view(team)
        return user.can_edit(team)


class IsFullAccess(BasePermission):
    """대표·관리자·경영지원팀 소속만 통과한다 (관리자 페이지, 경영지원팀 메인 등)."""

    message = "대표·관리자·경영지원팀만 사용할 수 있습니다."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_full_access)
