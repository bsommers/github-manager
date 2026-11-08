import httpx
import pytest
from fastapi.testclient import TestClient

from gmac import api, service
from gmac.config import Config
from gmac.github import GitHub
from gmac.models import GitStatus, LocalInfo, Source

pytestmark = pytest.mark.integration

REPO = {
    "full_name": "o/r",
    "owner": {"login": "o"},
    "private": False,
    "archived": False,
    "fork": False,
    "language": "Python",
    "stargazers_count": 3,
    "open_issues_count": 1,
    "pushed_at": "2026-01-02T03:04:05Z",
    "html_url": "https://github.com/o/r",
}
ISSUE = {
    "number": 5,
    "title": "<img src=x onerror=alert(1)>",
    "user": {"login": "me"},
    "labels": [{"name": "bug"}],
    "comments": 2,
    "body": "[x] **not markdown**",
    "updated_at": "2026-01-02T03:04:05Z",
    "html_url": "https://github.com/o/r/issues/5",
}
PULL = {
    "number": 7,
    "title": "Fix",
    "user": {"login": "me"},
    "draft": False,
    "updated_at": "2026-01-02T03:04:05Z",
    "html_url": "https://github.com/o/r/pull/7",
    "head": {"ref": "feat"},
    "base": {"ref": "main"},
    "body": "body text",
    "additions": 4,
    "deletions": 1,
    "changed_files": 2,
    "commits": 3,
}
SEARCH_PR = {
    "repository_url": "https://api.github.com/repos/o/r",
    "number": 7,
    "title": "Fix",
    "user": {"login": "me"},
    "updated_at": "2026-01-02T03:04:05Z",
    "html_url": "https://github.com/o/r/pull/7",
}


def handler(request: httpx.Request) -> httpx.Response:
    p = request.url.path
    if p == "/search/issues":
        return httpx.Response(200, json={"items": [SEARCH_PR]})
    if p == "/users/o/repos":
        return httpx.Response(200, json=[REPO, {**REPO, "full_name": "o/old", "archived": True}])
    if p == "/repos/o/r/issues":
        return httpx.Response(200, json=[ISSUE, {**ISSUE, "number": 6, "pull_request": {}}])
    if p == "/repos/o/r/pulls":
        return httpx.Response(200, json=[PULL])
    if p == "/repos/o/r/pulls/7":
        return httpx.Response(200, json=PULL)
    if p == "/repos/o/down/issues":
        raise httpx.ConnectError("offline")
    return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def client(tmp_path):
    cfg = Config(sources=[Source(name="o")], roots=[str(tmp_path)])
    gh = GitHub("fake-token", transport=httpx.MockTransport(handler))
    return TestClient(api.create_app(cfg, gh), base_url="http://127.0.0.1:8765")


def test_sources(client):
    assert client.get("/api/sources").json() == [
        {"name": "o", "kind": "user", "provider": "github"}
    ]


def test_repos_and_archived_and_source(client):
    assert [r["full_name"] for r in client.get("/api/repos").json()] == ["o/r"]
    both = client.get("/api/repos?archived=true&source=O").json()
    assert {r["full_name"] for r in both} == {"o/r", "o/old"}


def test_pulls(client):
    rows = client.get("/api/pulls").json()
    assert rows[0]["repo"] == "o/r" and rows[0]["number"] == 7


def test_issues_keep_hostile_text_verbatim(client):
    rows = client.get("/api/repos/o/r/issues").json()
    assert [i["number"] for i in rows] == [5]
    assert rows[0]["title"] == "<img src=x onerror=alert(1)>"
    assert rows[0]["labels"] == ["bug"]


def test_repo_pulls_and_detail(client):
    assert [p["number"] for p in client.get("/api/repos/o/r/pulls").json()] == [7]
    d = client.get("/api/repos/o/r/pulls/7").json()
    assert (d["head"], d["base"], d["additions"], d["body"]) == ("feat", "main", 4, "body text")


def test_local_no_clone(client):
    assert client.get("/api/repos/o/r/local").json() == {
        "clones": [],
        "remote": None,
        "status": None,
        "error": None,
    }


def test_local_with_status(client, monkeypatch):
    async def fake(cfg, full):
        assert full == "o/r"
        return LocalInfo(
            clones=["/home/me/src/r"], remote="o/r", status=GitStatus(branch="main", modified=1)
        )

    monkeypatch.setattr(service, "local_info", fake)
    d = client.get("/api/repos/o/r/local").json()
    assert d["clones"] == ["/home/me/src/r"]
    assert d["status"]["branch"] == "main" and d["status"]["clean"] is False


def test_github_error_maps_to_502_json(client):
    r = client.get("/api/repos/o/missing/pulls/7")
    assert r.status_code == 502
    assert r.json()["error"].startswith("404 on /repos/o/missing/pulls/7")
    assert "Traceback" not in r.text and "fake-token" not in r.text


def test_network_failure_maps_to_502(client):
    r = client.get("/api/repos/o/down/issues")
    assert r.status_code == 502 and r.json() == {"error": "could not reach GitHub"}


def test_service_value_error_maps_to_400(client):
    r = client.get("/api/repos?source=nobody")
    assert r.status_code == 400
    assert r.json() == {"error": "no sources match 'nobody'"}


def test_no_sources_configured_is_400():
    c = TestClient(api.create_app(Config(sources=[], roots=[])), base_url="http://localhost")
    r = c.get("/api/pulls")
    assert r.status_code == 400 and "no sources configured" in r.json()["error"]
    assert c.get("/api/sources").json() == []
