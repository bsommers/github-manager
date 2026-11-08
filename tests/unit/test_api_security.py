import importlib.resources
import re
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gmac import api, service
from gmac.config import Config
from gmac.models import Source

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "src" / "gmac" / "web"


@pytest.fixture
def client():
    cfg = Config(sources=[Source(name="o")], roots=[])
    return TestClient(api.create_app(cfg), base_url="http://localhost:8765")


@pytest.mark.parametrize(
    ("header", "ok"),
    [
        ("localhost", True),
        ("LocalHost:8765", True),
        ("127.0.0.1", True),
        ("127.0.0.1:80", True),
        ("[::1]", True),
        ("[::1]:8765", True),
        ("::1", True),
        (None, False),
        ("", False),
        ("evil.com", False),
        ("evil.com:8765", False),
        ("127.0.0.1.evil.com", False),
        ("localhost.evil.com", False),
        ("[::2]:1", False),
    ],
)
def test_host_allowed(header, ok):
    assert api.host_allowed(header) is ok


def test_foreign_host_rejected_everywhere(client):
    for path in ("/", "/static/app.js", "/api/sources", "/api/repos", "/nope"):
        r = client.get(path, headers={"Host": "evil.example"})
        assert r.status_code == 403
        assert r.json() == {"error": "forbidden host"}
        assert r.headers["x-content-type-options"] == "nosniff"


def test_rebinding_host_with_port_rejected(client):
    assert client.get("/api/sources", headers={"Host": "attacker.test:8765"}).status_code == 403


@pytest.mark.parametrize("path", ["/", "/static/app.js", "/api/sources", "/missing"])
def test_security_headers_and_no_cors(client, path):
    r = client.get(path, headers={"Origin": "http://evil.example"})
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert not any(k.lower().startswith("access-control-") for k in r.headers)


def test_options_preflight_gets_no_cors(client):
    r = client.options("/api/sources", headers={"Origin": "http://evil.example"})
    assert r.status_code == 405
    assert not any(k.lower().startswith("access-control-") for k in r.headers)


def test_static_assets_served_with_types(client):
    html = client.get("/")
    assert html.status_code == 200 and html.headers["content-type"].startswith("text/html")
    assert "<title>GMAC</title>" in html.text
    js = client.get("/static/app.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    css = client.get("/static/style.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")


@pytest.mark.parametrize(
    "name",
    ["index.html", "..%2f..%2fpyproject.toml", "%2e%2e/api.py", "%2e%2e", "api.py", "app.js%00"],
)
def test_static_never_serves_other_files(client, name):
    r = client.get(f"/static/{name}")
    assert r.status_code == 404
    assert "[project]" not in r.text and "create_app" not in r.text


def test_no_docs_or_openapi(client):
    for p in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(p).status_code == 404


def test_html_references_only_same_origin_assets():
    html = (WEB / "index.html").read_text()
    refs = re.findall(r'(?:src|href|action)="([^"]*)"', html)
    assert refs
    for ref in refs:
        assert ref.startswith("/static/"), ref
    assert not re.search(r"https?://|//cdn|@import|style=|\bon\w+=", html)
    css = (WEB / "style.css").read_text()
    assert "http" not in css and "url(" not in css and "@import" not in css


def test_js_never_uses_unsafe_dom_sinks():
    js = (WEB / "app.js").read_text()
    for bad in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "srcdoc",
    ):
        assert bad not in js
    assert "textContent" in js
    assert 'rel: "noopener noreferrer"' in js and 'target: "_blank"' in js
    assert not re.search(r"https?://", js)


def test_web_files_are_packaged():
    resources = importlib.resources.files("gmac") / "web"
    for name in ("index.html", "app.js", "style.css"):
        assert (resources / name).is_file()
    wheel = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["hatch"]["build"][
        "targets"
    ]["wheel"]
    assert "src/gmac" in wheel["packages"]
    assert "src/gmac/web/*" in wheel["artifacts"]


def test_deps_declared():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    assert any(d.startswith("fastapi") for d in deps)
    assert any(d.startswith("uvicorn") for d in deps)


@pytest.mark.parametrize(
    "path",
    [
        "/api/repos/%2e%2e/x/issues",
        "/api/repos/o/%2e%2e/issues",
        "/api/repos/o/%2e/issues",
        "/api/repos/o/a%20b/issues",
        "/api/repos/o/a%3Bb/local",
        "/api/repos/-bad/r/pulls",
        "/api/repos/o%20x/r/local",
        "/api/repos/" + "a" * 40 + "/r/issues",
        "/api/repos/o/" + "r" * 101 + "/issues",
        "/api/repos/o/r/pulls/0",
        "/api/repos/o/r/pulls/-1",
        "/api/repos/o/r/pulls/abc",
        "/api/repos/o/r/pulls/1%20",
        "/api/repos/o/r/pulls/1234567890",
        "/api/repos/o/..%2fx/issues",
        "/api/repos?source=a%20b",
        "/api/pulls?source=..%2f",
        "/api/repos?archived=maybe",
    ],
)
def test_bad_input_rejected_before_service(client, monkeypatch, path):
    async def boom(*a, **k):
        raise AssertionError("service must not be reached")

    for fn in (
        "list_repos",
        "list_pulls",
        "local_info",
        "list_issues",
        "list_repo_pulls",
        "get_pull",
    ):
        monkeypatch.setattr(service, fn, boom)
    r = client.get(path)
    assert r.status_code in (400, 404)
    assert "error" in r.json()
