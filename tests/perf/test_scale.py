import time

import httpx
import pytest

from conftest import REPO
from gmac import service
from gmac.config import Config
from gmac.github import GitHub
from gmac.models import Source

pytestmark = pytest.mark.perf


async def test_2000_repos_listed_and_sorted_under_budget():
    def h(req):
        page = int(req.url.params["page"])
        return httpx.Response(
            200,
            json=[
                {
                    **REPO,
                    "full_name": f"o/r{page}-{i}",
                    "pushed_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
                }
                for i in range(100)
            ],
        )

    gh = GitHub("fake", transport=httpx.MockTransport(h))
    t = time.perf_counter()
    repos = await service.list_repos(Config(sources=[Source(name="o")]), gh=gh)
    elapsed = time.perf_counter() - t
    await gh.aclose()
    assert len(repos) == 500  # default per-source cap
    assert elapsed < 2.0, f"took {elapsed:.2f}s"
    assert [r.pushed_at for r in repos] == sorted((r.pushed_at for r in repos), reverse=True)
