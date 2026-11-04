"""외부 AI(Claude API) 호출 — 백엔드 전용 (조원 저장소 shared/ai/* 를 옮김)

- API 키는 .env 의 ANTHROPIC_API_KEY. 화면(프론트엔드)으로는 절대 보내지 않는다 (CLAUDE.md 7절)
- 응답은 JSON 스키마(구조화 출력)로 받아 형식이 어긋나지 않게 한다
- 개발용 모의 응답: .env AI_MOCK=true (실패 연습은 AI_MOCK=fail) — DEBUG 일 때만 동작
- 테스트(manage.py test) 중에는 실제 API 를 부르지 않는다 (테스트는 request_ai 를 바꿔 끼운다)
"""

import json
import sys
import time

from django.conf import settings

# 기본 모델 — 공식 문서의 현재 권장 모델 (2026-11 기준)
AI_MODEL = "claude-opus-5-5"
# 거절(refusal) 시 서버가 알맞은 다른 모델로 다시 시도하는 기능 (beta)
FALLBACK_BETA = "server-side-fallback-2026-07-01"

ERROR_MESSAGES = {
    "not-configured": "AI API 키가 설정되지 않았습니다. 관리자에게 .env 의 ANTHROPIC_API_KEY 설정을 요청하세요.",
    "auth": "AI API 키가 올바르지 않거나 권한이 없습니다. 관리자에게 키 확인을 요청하세요.",
    "rate-limit": "AI 사용량 한도에 걸렸습니다. 잠시 후 다시 시도하세요.",
    "overloaded": "AI 서버가 혼잡하거나 일시적인 오류가 있습니다. 잠시 후 다시 시도하세요.",
    "timeout": "AI 응답 시간이 초과되었습니다. 다시 시도하세요.",
    "connection": "AI 서버에 연결하지 못했습니다. 네트워크를 확인한 뒤 다시 시도하세요.",
    "bad-request": "AI 요청 형식에 문제가 있습니다. 개발 담당자에게 알려 주세요.",
    "refusal": "AI가 이번 요청에 응답하지 않았습니다. 다시 시도하세요.",
    "truncated": "AI 응답이 중간에 잘렸습니다. 다시 시도하세요.",
    "invalid-output": "AI 응답 형식이 올바르지 않습니다. 다시 시도하세요.",
    "unknown": "AI 분석 중 알 수 없는 오류가 발생했습니다. 다시 시도하세요.",
}
NOT_RETRYABLE = {"not-configured", "auth", "bad-request"}  # 다시 눌러도 같은 오류


class AiError(Exception):
    def __init__(self, kind, detail=""):
        super().__init__(detail or kind)
        self.kind = kind

    @property
    def message(self):
        return ERROR_MESSAGES[self.kind]

    @property
    def retryable(self):
        return self.kind not in NOT_RETRYABLE


def mock_mode():
    """off / success / fail — 개발 서버(DEBUG)에서만"""
    if not settings.DEBUG:
        return "off"
    value = settings.AI_MOCK.strip().lower()
    return {"true": "success", "fail": "fail"}.get(value, "off")


_client = None


def get_client():
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        raise RuntimeError("테스트에서는 실제 AI API 를 부를 수 없습니다. request_ai 를 바꿔 끼우세요.")
    if not settings.ANTHROPIC_API_KEY:
        raise AiError("not-configured")
    global _client
    if _client is None:
        import anthropic

        # 분석 1회는 보통 수십 초 — 너무 오래 기다리지 않게 90초, 재시도 1회
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=90.0, max_retries=1)
    return _client


def _to_ai_error(error):
    """SDK 오류 → 오류 종류 (구체적인 것부터)"""
    import anthropic

    if isinstance(error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return AiError("auth", str(error))
    if isinstance(error, anthropic.RateLimitError):
        return AiError("rate-limit", str(error))
    if isinstance(error, (anthropic.BadRequestError, anthropic.NotFoundError, anthropic.UnprocessableEntityError)):
        return AiError("bad-request", str(error))
    if isinstance(error, anthropic.APITimeoutError):
        return AiError("timeout", str(error))
    if isinstance(error, anthropic.APIConnectionError):
        return AiError("connection", str(error))
    if isinstance(error, anthropic.APIStatusError) and error.status_code >= 500:
        return AiError("overloaded", str(error))
    return AiError("unknown", str(error))


def generate_json(system, user, schema, effort="medium"):
    """JSON 스키마 응답 요청 → (dict, 실제 응답한 모델 이름)"""
    import anthropic

    client = get_client()
    try:
        response = client.beta.messages.create(
            model=AI_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.APIError as error:
        raise _to_ai_error(error) from error
    if response.stop_reason == "refusal":
        raise AiError("refusal")
    if response.stop_reason == "max_tokens":
        raise AiError("truncated")
    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        data = json.loads(text)
    except ValueError as error:
        raise AiError("invalid-output", "응답이 JSON 이 아님") from error
    return data, response.model


def request_ai(system, user, schema, mock_response):
    """모의 모드면 mock_response() 를, 아니면 실제 AI 를 부른다 → (dict, 모델 이름)"""
    mode = mock_mode()
    if mode == "success":
        time.sleep(1.5)  # 생성 중 표시를 확인할 수 있게 잠깐 기다린다
        return mock_response(), "mock"
    if mode == "fail":
        time.sleep(1.5)
        raise AiError("overloaded", "AI_MOCK=fail")
    return generate_json(system, user, schema)
