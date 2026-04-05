import os
from functools import wraps

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer, BadSignature


APP_USERNAME = os.getenv("APP_USERNAME", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me")

COOKIE_NAME = "worksheet_session"


def get_serializer():
    return URLSafeSerializer(SESSION_SECRET, salt="worksheet-login")


def create_session_value(username: str) -> str:
    s = get_serializer()
    return s.dumps({"username": username})


def read_session_value(cookie_value: str):
    s = get_serializer()
    return s.loads(cookie_value)


def is_logged_in(request: Request) -> bool:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return False

    try:
        data = read_session_value(cookie)
        return data.get("username") == APP_USERNAME
    except BadSignature:
        return False


def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def credentials_are_valid(username: str, password: str) -> bool:
    return username == APP_USERNAME and password == APP_PASSWORD