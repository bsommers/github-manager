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
    assert names == {
        "list_sources",
        "list_repos",
        "list_pull_requests",
        "repo_local_info",
        "list_issues",
        "list_repo_pull_requests",
        "get_pull_request",
    }


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


async def test_tui_shows_error_in_subtitle(monkeypatch):
    from gmac import tui

    async def boom(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr(tui.service, "list_repos", boom)
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        assert app.sub_title == "error: offline"


async def test_tui_refresh_key_reloads(monkeypatch, gh):
    from gmac import tui

    real_repos, real_pulls = service.list_repos, service.list_pulls
    loads = []

    async def repos(cfg, *a, **k):
        loads.append(1)
        return await real_repos(cfg, gh=gh)

    async def pulls(cfg, *a, **k):
        return await real_pulls(cfg, gh=gh)

    monkeypatch.setattr(tui.service, "list_repos", repos)
    monkeypatch.setattr(tui.service, "list_pulls", pulls)
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("r")
        await pilot.pause(0.3)
        assert len(loads) == 2
        assert app.query_one("#repo-table").row_count == 2  # cleared, not duplicated


async def test_tui_renders_bracket_titles_literally(monkeypatch):
    from gmac import tui
    from gmac.models import PullRequest

    async def repos(cfg, *a, **k):
        return []

    async def pulls(cfg, *a, **k):
        return [PullRequest(repo="o/r", number=1, title="[WIP] [/bad] x", author="a")]

    monkeypatch.setattr(tui.service, "list_repos", repos)
    monkeypatch.setattr(tui.service, "list_pulls", pulls)
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.4)
        table = app.query_one("#pr-table")
        assert app.sub_title.startswith("0 repos")
        assert table.get_row_at(0)[2].plain == "[WIP] [/bad] x"
