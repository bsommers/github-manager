"""Drill-down modals for the TUI. All user-derived text is rendered as literal `Text`."""

from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.markup import escape
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Link, Static

from . import service
from .config import Config
from .models import Issue, LocalInfo, PullDetail, Repo

CSS = """
_Modal { align: center middle; }
_Modal > #box { width: 90%; height: 90%; border: round $accent; background: $surface; padding: 0 1; }
_Modal DataTable { height: 1fr; }
_Modal VerticalScroll { height: 1fr; }
"""


class GmacTable(DataTable):
    """Row table where Home/End jump to the first/last row (stock Home/End scroll sideways)."""

    BINDINGS = [
        Binding("home,ctrl+home", "first_row", "First", show=False),
        Binding("end,ctrl+end", "last_row", "Last", show=False),
    ]

    def action_first_row(self) -> None:
        self.move_cursor(row=0)

    def action_last_row(self) -> None:
        self.move_cursor(row=self.row_count - 1)


def _when(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


def _link(url: str, id: str) -> Link:
    return Link(escape(url), url=url, id=id)


class _Modal(ModalScreen[None]):
    DEFAULT_CSS = CSS
    BINDINGS = [Binding("escape", "close", "Back")]
    url = ""

    def action_close(self) -> None:
        self.dismiss(None)

    def action_open(self) -> None:
        if self.url:
            self.app.open_url(self.url)

    def _status(self, msg: str) -> None:
        self.query_one("#status", Static).update(Text(msg))


class RepoScreen(_Modal):
    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("o", "open", "Open in browser"),
        Binding("i", "issues", "Issues"),
    ]

    def __init__(self, repo: Repo, cfg: Config):
        super().__init__()
        self.repo = repo
        self.cfg = cfg
        self.url = repo.url or f"https://github.com/{repo.full_name}"

    def compose(self) -> ComposeResult:
        r = self.repo
        flags = [
            n
            for n, on in (("private", r.private), ("archived", r.archived), ("fork", r.fork))
            if on
        ]
        facts = Text()
        facts.append(r.full_name + "\n", style="bold")
        facts.append(
            f"language: {r.language or '-'}   stars: {r.stars}   open issues: {r.open_issues}\n"
        )
        facts.append(f"flags: {', '.join(flags) or 'public'}\n")
        facts.append(f"last push: {_when(r.pushed_at)}")
        with Vertical(id="box"):
            with VerticalScroll():
                yield Static(facts, id="facts")
                yield _link(self.url, "repo-url")
                yield Static(Text("local: loading…"), id="status")
            yield Button("Issues (i)", id="issues-btn")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        try:
            info = await service.local_info(self.cfg, self.repo.full_name)
        except Exception as e:
            self._status(f"error: {e}")
            return
        self._status(self._render_local(info))

    @staticmethod
    def _render_local(info: LocalInfo) -> str:
        if not info.clones:
            return "local: not cloned under roots"
        lines = ["local: " + ", ".join(str(p) for p in info.clones), f"remote: {info.remote}"]
        if info.error:
            lines.append(f"git status: {info.error}")
        elif s := info.status:
            lines.append(f"branch: {s.branch}  ahead {s.ahead}  behind {s.behind}")
            lines.append(
                "clean"
                if s.clean
                else f"staged {s.staged}  modified {s.modified}  untracked {s.untracked}"
            )
        return "\n".join(lines)

    def action_issues(self) -> None:
        self.app.push_screen(IssuesScreen(self.repo.full_name))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_issues()


class IssuesScreen(_Modal):
    def __init__(self, repo: str):
        super().__init__()
        self.repo = repo
        self.issues: list[Issue] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(Text(f"Issues: {self.repo}", style="bold"))
            yield Static(Text("loading…"), id="status")
            yield GmacTable(id="issue-table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        t = self.query_one("#issue-table", DataTable)
        t.add_columns("#", "title", "author", "labels", "comments", "updated")
        t.focus()
        self.run_worker(self._load())

    async def _load(self) -> None:
        try:
            self.issues = await service.list_issues(self.repo)
        except Exception as e:
            self._status(f"error: {e}")
            return
        t = self.query_one("#issue-table", DataTable)
        for i, x in enumerate(self.issues):
            t.add_row(
                *map(
                    Text,
                    (
                        str(x.number),
                        x.title,
                        x.author,
                        ", ".join(x.labels),
                        str(x.comments),
                        _when(x.updated_at),
                    ),
                ),
                key=str(i),
            )
        self._status("" if self.issues else "no open issues")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        self.app.push_screen(IssueScreen(self.issues[int(str(event.row_key.value))]))


class IssueScreen(_Modal):
    BINDINGS = [Binding("escape", "close", "Back"), Binding("o", "open", "Open in browser")]

    def __init__(self, issue: Issue):
        super().__init__()
        self.issue = issue
        self.url = issue.url

    def compose(self) -> ComposeResult:
        x = self.issue
        head = Text()
        head.append(f"#{x.number} {x.title}\n", style="bold")
        head.append(
            f"{x.repo}  by {x.author}  comments {x.comments}  updated {_when(x.updated_at)}\n"
        )
        head.append(f"labels: {', '.join(x.labels) or '-'}")
        with Vertical(id="box"):
            with VerticalScroll():
                yield Static(head, id="head")
                yield _link(x.url, "issue-url")
                yield Static(Text(x.body or "(no description)"), id="body")


class PullsScreen(_Modal):
    def __init__(self, repo: str):
        super().__init__()
        self.repo = repo
        self.pulls: list[PullDetail] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(Text(f"Open pull requests: {self.repo}", style="bold"))
            yield Static(Text("loading…"), id="status")
            yield GmacTable(id="repo-pr-table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        t = self.query_one("#repo-pr-table", DataTable)
        t.add_columns("#", "title", "author", "draft", "updated")
        t.focus()
        self.run_worker(self._load())

    async def _load(self) -> None:
        try:
            self.pulls = await service.list_repo_pulls(self.repo)
        except Exception as e:
            self._status(f"error: {e}")
            return
        t = self.query_one("#repo-pr-table", DataTable)
        for i, p in enumerate(self.pulls):
            t.add_row(
                *map(
                    Text,
                    (
                        str(p.number),
                        p.title,
                        p.author,
                        "draft" if p.draft else "",
                        _when(p.updated_at),
                    ),
                ),
                key=str(i),
            )
        self._status("" if self.pulls else "no open pull requests")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        p = self.pulls[int(str(event.row_key.value))]
        self.app.push_screen(PullScreen(self.repo, p.number))


class PullScreen(_Modal):
    BINDINGS = [Binding("escape", "close", "Back"), Binding("o", "open", "Open in browser")]

    def __init__(self, repo: str, number: int):
        super().__init__()
        self.repo = repo
        self.number = number

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            with VerticalScroll():
                yield Static(Text("loading…"), id="status")
                yield Static(Text(""), id="head")
                yield Static(Text(""), id="body")
                yield Link("", id="pull-url")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        try:
            p = await service.get_pull(self.repo, self.number)
        except Exception as e:
            self._status(f"error: {e}")
            return
        self.url = p.url
        self._status("")
        head = Text()
        head.append(f"#{p.number} {p.title}\n", style="bold")
        head.append(f"{p.repo}  by {p.author}  {p.head} -> {p.base}\n")
        head.append(f"draft: {'yes' if p.draft else 'no'}  mergeable: {p.mergeable_state or '-'}\n")
        head.append(f"created {_when(p.created_at)}  updated {_when(p.updated_at)}\n")
        head.append(
            f"+{p.additions} -{p.deletions}  files {p.changed_files}  commits {p.commits}"
            f"  comments {p.comments}"
        )
        self.query_one("#head", Static).update(head)
        self.query_one("#body", Static).update(Text(p.body or "(no description)"))
        link = self.query_one("#pull-url", Link)
        link.url = p.url
        link.update(escape(p.url))
