"""Current request context and trusted client-IP extraction."""
from __future__ import annotations

import ipaddress
import os
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


def _trusted_proxy_networks():
    networks = []
    for value in os.environ.get("ITAM_TRUSTED_PROXY_IPS", "").split(","):
        value = value.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            # Invalid proxy entries fail closed: they never grant trust.
            continue
    return networks


def client_ip(request=None) -> str | None:
    """Use X-Forwarded-For only when REMOTE_ADDR is an explicitly trusted proxy.

    Walk the forwarded chain from right to left, skipping trusted proxies. This
    avoids accepting a client-supplied leftmost XFF value when the trusted proxy
    appends the actual client address.
    """
    request = request or get_current_request()
    if request is None:
        return None

    remote_text = (request.META.get("REMOTE_ADDR", "") or "").strip()
    try:
        remote = ipaddress.ip_address(remote_text)
    except ValueError:
        return None

    trusted_networks = _trusted_proxy_networks()
    if not any(remote in network for network in trusted_networks):
        return str(remote)

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    for value in reversed(forwarded.split(",")):
        candidate_text = value.strip()
        if not candidate_text:
            continue
        try:
            candidate = ipaddress.ip_address(candidate_text)
        except ValueError:
            continue
        if any(candidate in network for network in trusted_networks):
            continue
        return str(candidate)

    return str(remote)


def client_user_agent(request=None) -> str:
    request = request or get_current_request()
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT", "") or "")[:300]


class CurrentUserMiddleware:
    """Expose the current request/user to audit helpers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try:
            return self.get_response(request)
        finally:
            clear_current_request()
