import httpx
import pytest

from conftest import REPO
from gmac import service
from gmac.config import Config
from gmac.github import GitHub
from gmac.models import Source

pytestmark = pytest.mark.stress


async def test_100_sources_fan_out_concurrently_and_merge():
    seen = set()

    def h(req):
        seen.add(req.url.path)
        owner = req.url.path.split("/")[2]
        return httpx.Response(
            200, json=[{**REPO, "full_name": f"{owner}/r", "owner": {"login": owner}}]
        )

    cfg = Config(sources=[Source(name=f"s{i}") for i in range(100)])
    gh = GitHub("fake", transport=httpx.MockTransport(h))
    repos = await service.list_repos(cfg, gh=gh)
    await gh.aclose()
    assert len(repos) == 100 and len(seen) == 100


async def test_one_failing_source_fails_the_whole_call_loudly():
    def h(req):
        return (
            httpx.Response(500, json={"message": "boom"})
            if "bad" in req.url.path
            else httpx.Response(200, json=[])
        )

    cfg = Config(sources=[Source(name="ok"), Source(name="bad")])
    gh = GitHub("fake", transport=httpx.MockTransport(h))
    with pytest.raises(Exception, match="500"):
        await service.list_repos(cfg, gh=gh)
    await gh.aclose()
