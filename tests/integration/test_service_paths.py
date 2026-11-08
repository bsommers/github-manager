import httpx
import pytest

from conftest import handler
from gmac import service
from gmac.config import Config
from gmac.github import GitHub
from gmac.models import PullRequest, Repo, Source

pytestmark = pytest.mark.integration
CFG = Config(sources=[Source(name="o", kind="org")])


async def test_service_builds_and_closes_its_own_client(monkeypatch):
    made, closed = [], []

    class Spy(GitHub):
        async def aclose(self):
            closed.append(1)
            await super().aclose()

    def factory(token):
        made.append(token)
        return Spy(token, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(service, "GitHub", factory)
    monkeypatch.setattr(service, "resolve_token", lambda provider: "fake")
    assert len(await service.list_repos(CFG)) == 1
    assert len(await service.list_pulls(CFG)) == 1
    assert made == ["fake", "fake"] and len(closed) == 2


async def test_service_closes_client_on_error(monkeypatch):
    closed = []

    class Spy(GitHub):
        async def aclose(self):
            closed.append(1)
            await super().aclose()

    monkeypatch.setattr(
        service,
        "GitHub",
        lambda t: Spy(t, transport=httpx.MockTransport(lambda r: httpx.Response(500, json={}))),
    )
    monkeypatch.setattr(service, "resolve_token", lambda provider: None)
    with pytest.raises(Exception, match="500"):
        await service.list_repos(CFG)
    assert closed == [1]


async def test_sorting_newest_first_and_none_dates_last(gh, monkeypatch):
    async def fake_repos(self, s, limit=500):
        return [
            Repo(full_name="a", owner="o"),
            Repo(full_name="b", owner="o", pushed_at="2026-01-01T00:00:00Z"),
            Repo(full_name="c", owner="o", pushed_at="2026-06-01T00:00:00Z"),
        ]

    async def fake_pulls(self, s, limit=200):
        return [
            PullRequest(repo="r", number=1, title="t", author="a"),
            PullRequest(
                repo="r", number=2, title="t", author="a", updated_at="2026-03-01T00:00:00Z"
            ),
        ]

    monkeypatch.setattr(GitHub, "repos", fake_repos)
    monkeypatch.setattr(GitHub, "pulls", fake_pulls)
    assert [r.full_name for r in await service.list_repos(CFG, gh=gh)] == ["c", "b", "a"]
    assert [p.number for p in await service.list_pulls(CFG, gh=gh)] == [2, 1]


async def test_source_filter_is_case_insensitive(gh):
    assert len(await service.list_repos(CFG, "O", gh=gh)) == 1
