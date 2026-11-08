import httpx
import pytest

from gmac import service
from gmac.github import GitHub
from gmac.models import GitStatus

pytestmark = pytest.mark.integration

ISSUE = {
    "number": 3,
    "title": "[bad] t",
    "user": {"login": "u"},
    "labels": [{"name": "bug"}],
    "comments": 2,
    "body": None,
    "updated_at": "2026-01-02T03:04:05Z",
    "html_url": "https://github.com/o/r/issues/3",
}
PULL = {
    "number": 9,
    "title": "P",
    "user": {"login": "u"},
    "draft": False,
    "updated_at": "2026-01-02T03:04:05Z",
    "html_url": "https://github.com/o/r/pull/9",
    "head": {"ref": "feat"},
    "base": {"ref": "main"},
    "body": None,
    "created_at": "2026-01-01T00:00:00Z",
    "additions": 5,
    "deletions": 2,
    "changed_files": 1,
    "commits": 3,
    "comments": 1,
    "review_comments": 2,
    "mergeable_state": "clean",
}


def handler(request: httpx.Request) -> httpx.Response:
    p = request.url.path
    if p == "/repos/o/r/issues":
        return httpx.Response(200, json=[ISSUE, {**ISSUE, "number": 4, "pull_request": {}}])
    if p == "/repos/o/r/pulls":
        return httpx.Response(200, json=[PULL])
    if p == "/repos/o/r/pulls/9":
        return httpx.Response(200, json=PULL)
    return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def client():
    return GitHub("tok", transport=httpx.MockTransport(handler))


async def test_issues_skip_prs(client):
    issues = await service.list_issues("o/r", gh=client)
    assert [i.number for i in issues] == [3]
    assert (issues[0].labels, issues[0].body, issues[0].comments) == (["bug"], "", 2)


async def test_repo_pulls_and_pull(client):
    pulls = await service.list_repo_pulls("o/r", gh=client)
    assert [p.number for p in pulls] == [9]
    d = await service.get_pull("o/r", 9, gh=client)
    assert (d.head, d.base, d.comments, d.additions, d.mergeable_state) == (
        "feat",
        "main",
        3,
        5,
        "clean",
    )
    assert d.body == ""


async def test_service_builds_and_closes_own_client(monkeypatch):
    made = []

    class Fake(GitHub):
        def __init__(self, token):
            super().__init__(token, transport=httpx.MockTransport(handler))
            made.append(self)

    monkeypatch.setattr(service, "GitHub", Fake)
    monkeypatch.setattr(service, "resolve_token", lambda provider: "tok")
    assert len(await service.list_issues("o/r")) == 1
    assert len(await service.list_repo_pulls("o/r")) == 1
    assert (await service.get_pull("o/r", 9)).number == 9
    assert len(made) == 3


async def test_local_info_runs_locate(monkeypatch, tmp_path):
    from gmac.config import Config

    info = await service.local_info(Config(roots=[str(tmp_path)]), "o/r")
    assert info.clones == []


def test_git_status_clean_property():
    assert GitStatus(branch="m").clean
    assert not GitStatus(branch="m", untracked=1).clean
