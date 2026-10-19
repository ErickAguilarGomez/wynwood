import contextvars
import logging
import re
import time
import uuid

request_id_context = contextvars.ContextVar("request_id", default="")
logger = logging.getLogger("http")


class ContentSecurityPolicyMiddleware:
    policy = "; ".join(
        (
            "default-src 'self'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "img-src 'self' data: https:",
            "font-src 'self'",
            "style-src 'self'",
            "script-src 'self'",
            "connect-src 'self'",
        )
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = self.policy
        return response


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", "")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", request_id):
            request_id = uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_context.set(request_id)
        started = time.monotonic()
        try:
            response = self.get_response(request)
        finally:
            request_id_context.reset(token)
        response["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": getattr(getattr(request, "resolver_match", None), "route", ""),
                "status_code": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            },
        )
        return response
