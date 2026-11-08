import httpx
import pytest

from gmac.github import GitHub

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
PR = {
    "repository_url": "https://api.github.com/repos/o/r",
    "number": 7,
    "title": "Fix",
    "user": {"login": "me"},
    "draft": True,
    "updated_at": "2026-01-02T03:04:05Z",
    "html_url": "https://github.com/o/r/pull/7",
}


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/search/issues":
        return httpx.Response(200, json={"items": [PR]})
    if path.endswith("/repos"):
        return httpx.Response(200, json=[REPO, {**REPO, "full_name": "o/old", "archived": True}])
    return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def gh():
    return GitHub("tok", transport=httpx.MockTransport(handler))
