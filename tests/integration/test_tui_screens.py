from datetime import UTC, datetime
from pathlib import Path

import pytest
from textual.widgets import Button, DataTable, Link, Static, TabbedContent

from gmac import service, tui
from gmac.config import Config
from gmac.models import (
    GitStatus,
    Issue,
    LocalInfo,
    PullDetail,
    PullRequest,
    Repo,
    Source,
)
from gmac.screens import IssueScreen, IssuesScreen, PullScreen, PullsScreen, RepoScreen

pytestmark = pytest.mark.integration
CFG = Config(sources=[Source(name="o")])
NOW = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
BAD = "[bold]x[/bold] [/bad] [link=http://evil]t"


def repo(name="o/r", **kw):
    return Repo(full_name=name, owner="o", url=f"https://github.com/{name}", **kw)


def pr(n=1, repo_="o/r", title="t"):
    return PullRequest(repo=repo_, number=n, title=title, author="a", updated_at=NOW)


def issue(n=1, **kw):
    kw = {"title": "bug", "author": "a", "repo": "o/r", "url": "https://x/i/1", **kw}
    return Issue(number=n, **kw)


def detail(**kw):
    kw = {"number": 1, "title": "T", "author": "a", "repo": "o/r", "url": "https://x/p/1", **kw}
    return PullDetail(**kw)


@pytest.fixture
def stub(monkeypatch):
    """Patch every service function the TUI uses; tests tweak the returned dict/callables."""
    s = {
        "repos": [repo()],
        "prs": [pr()],
        "local": LocalInfo(),
        "issues": [issue()],
        "pulls": [detail()],
        "pull": detail(),
    }

    def val(key):
        async def f(*a, **k):
            v = s[key]
            if isinstance(v, Exception):
                raise v
            return v

        return f

    monkeypatch.setattr(service, "list_repos", val("repos"))
    monkeypatch.setattr(service, "list_pulls", val("prs"))
    monkeypatch.setattr(service, "local_info", val("local"))
    monkeypatch.setattr(service, "list_issues", val("issues"))
    monkeypatch.setattr(service, "list_repo_pulls", val("pulls"))
    monkeypatch.setattr(service, "get_pull", val("pull"))
    return s


def txt(app, selector) -> str:
    w = app.screen.query_one(selector, Static)
    return str(w.render())


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(tui.GmacApp, "open_url", lambda self, url, **k: urls.append(url))
    return urls


async def test_tables_fill_and_scroll_300_rows(stub):
    stub["repos"] = [repo(f"o/r{i}") for i in range(300)]
    stub["prs"] = [pr(i) for i in range(300)]
    app = tui.GmacApp(CFG)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        rt = app.query_one("#repo-table", DataTable)
        assert app.focused is rt
        assert rt.size.height > 15  # fills the tab, not content height
        await pilot.press("end")
        await pilot.pause(0.2)
        assert rt.cursor_row == 299
        await pilot.press("home")
        await pilot.pause(0.2)
        assert rt.cursor_row == 0
        await pilot.press("pagedown")
        await pilot.pause(0.2)
        assert 0 < rt.cursor_row < 299
        app.query_one(TabbedContent).active = "prs"
        await pilot.pause(0.2)
        pt = app.query_one("#pr-table", DataTable)
        assert app.focused is pt
        await pilot.press("end")
        await pilot.pause(0.2)
        assert pt.cursor_row == 299
        app.query_one(TabbedContent).active = "repos"
        await pilot.pause(0.2)
        assert app.focused is rt


async def test_repo_drill_chain_and_escape(stub, opened):
    stub["repos"] = [repo(language="Python", stars=5, open_issues=2, private=True, fork=True)]
    stub["issues"] = [
        issue(1, title="first", labels=["bug", "ui"], comments=3, updated_at=NOW, body="BODY"),
        issue(2, title="second"),
    ]
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert isinstance(app.screen, RepoScreen)
        facts = txt(app, "#facts")
        assert "Python" in facts and "stars: 5" in facts and "private, fork" in facts
        assert "not cloned under roots" in txt(app, "#status")
        link = app.screen.query_one("#repo-url", Link)
        assert link.url == "https://github.com/o/r"
        await pilot.press("o")
        assert opened == ["https://github.com/o/r"]
        await pilot.press("i")
        await pilot.pause(0.3)
        assert isinstance(app.screen, IssuesScreen)
        t = app.screen.query_one("#issue-table", DataTable)
        assert t.row_count == 2
        assert t.get_row_at(0)[3].plain == "bug, ui"
        await pilot.press("down", "enter")
        await pilot.pause(0.2)
        assert isinstance(app.screen, IssueScreen)
        assert "#2 second" in txt(app, "#head")
        assert "(no description)" in txt(app, "#body")
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert isinstance(app.screen, IssuesScreen)
        await pilot.press("up", "enter")
        await pilot.pause(0.2)
        assert "BODY" in txt(app, "#body")
        await pilot.press("o")
        assert opened[-1] == "https://x/i/1"
        await pilot.press("escape", "escape", "escape")
        await pilot.pause(0.1)
        assert type(app.screen).__name__ == "Screen"  # back at main app


async def test_issues_button_opens_issues(stub):
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("enter")
        await pilot.pause(0.2)
        await pilot.click(Button)
        await pilot.pause(0.2)
        assert isinstance(app.screen, IssuesScreen)


async def test_local_info_rendering(stub):
    clone = Path("/src/o/r")
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        cases = [
            (
                LocalInfo(
                    clones=[clone], remote="git@github.com:o/r.git", status=GitStatus(branch="main")
                ),
                ["/src/o/r", "git@github.com:o/r.git", "branch: main", "clean"],
            ),
            (
                LocalInfo(
                    clones=[clone],
                    remote="u",
                    status=GitStatus(
                        branch="dev", ahead=2, behind=1, staged=3, modified=4, untracked=5
                    ),
                ),
                ["ahead 2", "behind 1", "staged 3", "modified 4", "untracked 5"],
            ),
            (
                LocalInfo(clones=[clone], remote="u", error=f"git status failed: {BAD}"),
                [f"git status failed: {BAD}"],
            ),
            (LocalInfo(clones=[clone], remote="u"), ["/src/o/r"]),
        ]
        for info, wants in cases:
            stub["local"] = info
            await pilot.press("enter")
            await pilot.pause(0.3)
            body = txt(app, "#status")
            for w in wants:
                assert w in body
            await pilot.press("escape")
            await pilot.pause(0.1)


async def test_repo_screen_error_and_bracket_text(stub):
    stub["repos"] = [repo("o/[bad]", language=BAD)]
    stub["local"] = RuntimeError(f"boom {BAD}")
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert txt(app, "#status") == f"error: boom {BAD}"
        assert BAD in txt(app, "#facts") and "o/[bad]" in txt(app, "#facts")


async def test_issue_screens_error_empty_and_brackets(stub, opened):
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("enter")
        await pilot.pause(0.2)
        stub["issues"] = RuntimeError(f"nope {BAD}")
        await pilot.press("i")
        await pilot.pause(0.3)
        assert txt(app, "#status") == f"error: nope {BAD}"
        await pilot.press("escape")
        stub["issues"] = []
        await pilot.press("i")
        await pilot.pause(0.3)
        assert txt(app, "#status") == "no open issues"
        assert app.screen.query_one("#issue-table", DataTable).row_count == 0
        await pilot.press("escape")
        stub["issues"] = [issue(title=BAD, body=BAD, author=BAD, labels=[BAD], url="")]
        await pilot.press("i")
        await pilot.pause(0.3)
        assert app.screen.query_one("#issue-table", DataTable).get_row_at(0)[1].plain == BAD
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert BAD in txt(app, "#body") and BAD in txt(app, "#head")
        await pilot.press("o")  # no url: nothing opens
        assert opened == []


async def test_pr_drill_chain(stub, opened):
    stub["prs"] = [pr(1, "o/r"), pr(2, "o/other")]
    stub["pulls"] = [detail(number=7, draft=True, updated_at=NOW), detail(number=8)]
    stub["pull"] = detail(
        number=8,
        title="Title",
        author="auth",
        head="feat",
        base="main",
        draft=False,
        mergeable_state="clean",
        created_at=NOW,
        updated_at=NOW,
        additions=11,
        deletions=22,
        changed_files=3,
        commits=4,
        comments=5,
        body="long body",
        url="https://github.com/o/r/pull/8",
    )
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        app.query_one(TabbedContent).active = "prs"
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert isinstance(app.screen, PullsScreen)
        t = app.screen.query_one("#repo-pr-table", DataTable)
        assert t.row_count == 2 and t.get_row_at(0)[3].plain == "draft"
        await pilot.press("down", "enter")
        await pilot.pause(0.3)
        assert isinstance(app.screen, PullScreen)
        head = txt(app, "#head")
        for w in (
            "#8 Title",
            "auth",
            "feat -> main",
            "draft: no",
            "mergeable: clean",
            "+11 -22",
            "files 3",
            "commits 4",
            "comments 5",
            "2026-01-02 03:04",
        ):
            assert w in head
        assert "long body" in txt(app, "#body")
        link = app.screen.query_one("#pull-url", Link)
        assert link.url == "https://github.com/o/r/pull/8"
        await pilot.press("o")
        assert opened == ["https://github.com/o/r/pull/8"]
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert isinstance(app.screen, PullsScreen)
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert type(app.screen).__name__ == "Screen"


async def test_pull_screens_error_empty_brackets(stub, opened):
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        app.query_one(TabbedContent).active = "prs"
        await pilot.pause(0.2)
        stub["pulls"] = RuntimeError(f"x {BAD}")
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert txt(app, "#status") == f"error: x {BAD}"
        await pilot.press("escape")
        stub["pulls"] = []
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert txt(app, "#status") == "no open pull requests"
        await pilot.press("escape")
        stub["pulls"] = [detail(title=BAD)]
        stub["pull"] = RuntimeError(f"gone {BAD}")
        await pilot.press("enter")
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert isinstance(app.screen, PullScreen)
        assert txt(app, "#status") == f"error: gone {BAD}"
        await pilot.press("o")  # nothing loaded: no url
        assert opened == []
        await pilot.press("escape")
        stub["pull"] = detail(title=BAD, body=BAD, head=BAD, url="https://x/[/bad]")
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert BAD in txt(app, "#head") and BAD in txt(app, "#body")
        assert app.screen.query_one("#pull-url", Link).url == "https://x/[/bad]"
        assert "(no description)" not in txt(app, "#body")


async def test_pull_screen_empty_body_and_no_mergeable(stub):
    stub["pull"] = detail(body="", mergeable_state="", draft=True)
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        app.query_one(TabbedContent).active = "prs"
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert "(no description)" in txt(app, "#body")
        assert "draft: yes  mergeable: -" in txt(app, "#head")


async def test_modal_row_selected_does_not_leak(stub):
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("enter", "i")
        await pilot.pause(0.3)
        await pilot.press("enter")
        await pilot.pause(0.3)
        names = [type(s).__name__ for s in app.screen_stack]
        assert names == ["Screen", "RepoScreen", "IssuesScreen", "IssueScreen"]


async def test_ctrl_p_palette_still_available(stub):
    app = tui.GmacApp(CFG)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("ctrl+p")
        await pilot.pause(0.3)
        assert type(app.screen).__name__ == "CommandPalette"
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Screen"
