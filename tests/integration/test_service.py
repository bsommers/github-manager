import pytest

from gmac import service
from gmac.config import Config
from gmac.github import GitHubError
from gmac.models import Source

pytestmark = pytest.mark.integration
CFG = Config(sources=[Source(name="o", kind="org"), Source(name="u")])


async def test_repos_hide_archived_by_default(gh):
    repos = await service.list_repos(CFG, gh=gh)
    assert {r.full_name for r in repos} == {"o/r"}
    assert len(await service.list_repos(CFG, include_archived=True, gh=gh)) == 4


async def test_pulls_parse_repo_and_draft(gh):
    prs = await service.list_pulls(CFG, "o", gh=gh)
    assert (prs[0].repo, prs[0].number, prs[0].draft) == ("o/r", 7, True)


async def test_no_sources_is_clear_error(gh):
    with pytest.raises(ValueError, match="no sources"):
        await service.list_repos(Config(), gh=gh)
    with pytest.raises(ValueError, match="no sources match"):
        await service.list_repos(CFG, "zzz", gh=gh)


async def test_http_error_surfaces(gh):
    with pytest.raises(GitHubError, match="404"):
        await gh._get("/nope")


async def test_mcp_tools_registered():
    from fastmcp import Client

    from gmac.mcp_server import server

    async with Client(server) as c:
        names = {t.name for t in await c.list_tools()}
    assert names == {"list_sources", "list_repos", "list_pull_requests"}


async def test_tui_loads_tables(monkeypatch, gh):
    from gmac import tui

    real_repos, real_pulls = (
        service.list_repos,
        service.list_pulls,
    )  # tui.service is the same module

    async def repos(cfg, *a, **k):
        return await real_repos(cfg, gh=gh)

    async def pulls(cfg, *a, **k):
        return await real_pulls(cfg, gh=gh)

    monkeypatch.setattr(tui.service, "list_repos", repos)
    monkeypatch.setattr(tui.service, "list_pulls", pulls)
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        assert app.sub_title.startswith("2 repos"), app.sub_title
        assert app.query_one("#repo-table").row_count == 2
        assert app.query_one("#pr-table").row_count == 2
