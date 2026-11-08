"""Read-only local JSON API and static web UI. A thin wrapper over `service`, like the other surfaces."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import service
from .config import Config
from .github import GitHub, GitHubError

WEB_DIR = Path(__file__).parent / "web"
ASSETS = {"app.js": "text/javascript", "style.css": "text/css"}
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}

_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
_NAME = re.compile(r"(?!\.+$)[A-Za-z0-9._-]{1,100}")
_NUMBER = re.compile(r"[1-9][0-9]{0,8}")
_SOURCE = re.compile(r"[A-Za-z0-9._-]{1,100}")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Cache-Control": "no-store",
}


class BadRequest(ValueError):
    """Client-supplied parameter failed validation."""


def host_allowed(header: str | None) -> bool:
    """True when the Host header names this machine's loopback (DNS-rebinding defense)."""
    if not header:
        return False
    if header.startswith("["):
        host = header[1:].split("]", 1)[0]
    else:
        host = header.rsplit(":", 1)[0] if header.count(":") == 1 else header
    return host.lower() in ALLOWED_HOSTS


def _full_name(owner: str, name: str) -> str:
    if not (_OWNER.fullmatch(owner) and _NAME.fullmatch(name)):
        raise BadRequest("invalid repository name")
    return f"{owner}/{name}"


def _number(raw: str) -> int:
    if not _NUMBER.fullmatch(raw):
        raise BadRequest("invalid pull request number")
    return int(raw)


def _source(raw: str | None) -> str | None:
    if raw is not None and not _SOURCE.fullmatch(raw):
        raise BadRequest("invalid source")
    return raw


def _json(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def _dump(items: list[Any]) -> list[dict]:
    return [i.model_dump(mode="json") for i in items]


def create_app(cfg: Config, gh: GitHub | None = None) -> FastAPI:
    app = FastAPI(title="GMAC", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        if not host_allowed(request.headers.get("host")):
            response: Response = _json({"error": "forbidden host"}, 403)
        else:
            response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        return _json({"error": str(exc)}, 400)

    @app.exception_handler(GitHubError)
    async def _github_error(request: Request, exc: GitHubError) -> JSONResponse:
        return _json({"error": str(exc)}, 502)

    @app.exception_handler(httpx.HTTPError)
    async def _http_error(request: Request, exc: httpx.HTTPError) -> JSONResponse:
        return _json({"error": "could not reach GitHub"}, 502)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _json({"error": "invalid request"}, 400)

    @app.exception_handler(StarletteHTTPException)
    async def _http_status(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _json({"error": str(exc.detail)}, exc.status_code)

    @app.get("/", include_in_schema=False)
    async def index() -> Response:
        return Response((WEB_DIR / "index.html").read_bytes(), media_type="text/html")

    @app.get("/static/{name}", include_in_schema=False)
    async def asset(name: str) -> Response:
        if name not in ASSETS:  # explicit allowlist: never serve any other file
            return _json({"error": "not found"}, 404)
        return Response((WEB_DIR / name).read_bytes(), media_type=ASSETS[name])

    @app.get("/api/sources")
    async def sources() -> JSONResponse:
        return _json([s.model_dump(mode="json") for s in cfg.sources])

    @app.get("/api/repos")
    async def repos(source: str | None = None, archived: bool = False) -> JSONResponse:
        rows = await service.list_repos(cfg, _source(source), archived, gh=gh)
        return _json(_dump(rows))

    @app.get("/api/pulls")
    async def pulls(source: str | None = None) -> JSONResponse:
        return _json(_dump(await service.list_pulls(cfg, _source(source), gh=gh)))

    @app.get("/api/repos/{owner}/{name}/local")
    async def local(owner: str, name: str) -> JSONResponse:
        info = await service.local_info(cfg, _full_name(owner, name))
        data = info.model_dump(mode="json")
        if info.status is not None:
            data["status"]["clean"] = info.status.clean
        return _json(data)

    @app.get("/api/repos/{owner}/{name}/issues")
    async def issues(owner: str, name: str) -> JSONResponse:
        return _json(_dump(await service.list_issues(_full_name(owner, name), gh=gh)))

    @app.get("/api/repos/{owner}/{name}/pulls")
    async def repo_pulls(owner: str, name: str) -> JSONResponse:
        return _json(_dump(await service.list_repo_pulls(_full_name(owner, name), gh=gh)))

    @app.get("/api/repos/{owner}/{name}/pulls/{number}")
    async def pull(owner: str, name: str, number: str) -> JSONResponse:
        repo = _full_name(owner, name)
        detail = await service.get_pull(repo, _number(number), gh=gh)
        return _json(detail.model_dump(mode="json"))

    return app
