from django.conf import settings
from django.http import Http404, HttpResponse


def spa_index(request):
    """Vue 화면 주소(/production, /admin 등)로 바로 들어오거나 새로고침하면 Vue의 index.html을 돌려준다.
    어떤 화면을 보여 줄지는 Vue Router가 브라우저에서 정한다. (배포용 — 개발 중에는 Vite가 이 역할을 한다)"""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("Vue 빌드 결과가 없습니다. frontend 폴더에서 npm run build 를 먼저 실행하세요.")
    return HttpResponse(index.read_text(encoding="utf-8"))
