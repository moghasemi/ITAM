"""کاربر جاری و نشانی IP در طول پردازش درخواست."""
from __future__ import annotations

import ipaddress

import threading

_state = threading.local()

ANONYMOUS_LABEL = "کاربر ناشناس"


def set_current_request(request):
    _state.request = request
    _state.user = getattr(request, "user", None)


def clear_current_request():
    _state.request = None
    _state.user = None


def get_current_user():
    return getattr(_state, "user", None)


def get_current_request():
    return getattr(_state, "request", None)


def client_ip(request=None) -> str | None:
    """استخراج نشانی IP کاربر با در نظر گرفتن پروکسی معکوس."""
    request = request or get_current_request()
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = (
        forwarded.split(",", 1)[0].strip()
        if forwarded
        else (request.META.get("REMOTE_ADDR", "") or "").strip()
    )
    if not candidate:
        return None
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def client_user_agent(request=None) -> str:
    request = request or get_current_request()
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT", "") or "")[:300]


class CurrentUserMiddleware:
    """کاربر و درخواست جاری را برای استفاده در مدل‌ها و لاگ‌ها ذخیره می‌کند."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try:
            response = self.get_response(request)
        finally:
            clear_current_request()
        return response
