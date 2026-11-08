from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.command import CommandPalette
from textual.widgets import DataTable, Footer, Header, TabbedContent, TabPane

from . import service
from .config import Config
from .models import PullRequest, Repo
from .screens import GmacTable, PullsScreen, RepoScreen


class GmacApp(App):
    TITLE = "GMAC"
    BINDINGS = [("r", "refresh", "Refresh"), ("q", "quit", "Quit")]
    CSS = """
    TabbedContent { height: 1fr; }
    TabPane { height: 1fr; padding: 0; }
    #repo-table, #pr-table { height: 1fr; }
    """

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.repos: list[Repo] = []
        self.prs: list[PullRequest] = []

    def action_command_palette(self) -> None:
        """Ctrl+P toggles the palette (Textual's default only opens it; Esc also closes it)."""
        if CommandPalette.is_open(self):
            self.screen.dismiss(None)
        else:
            super().action_command_palette()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Repos", id="repos"):
                yield GmacTable(id="repo-table", cursor_type="row", zebra_stripes=True)
            with TabPane("Pull requests", id="prs"):
                yield GmacTable(id="pr-table", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#repo-table", DataTable).add_columns(
            "repo", "lang", "★", "issues", "pushed"
        )
        self.query_one("#pr-table", DataTable).add_columns(
            "repo", "#", "title", "author", "updated"
        )
        self.query_one("#repo-table", DataTable).focus()
        self.action_refresh()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        table = "#repo-table" if event.pane.id == "repos" else "#pr-table"
        self.query_one(table, DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        i = int(str(event.row_key.value))
        if event.data_table.id == "repo-table":
            self.push_screen(RepoScreen(self.repos[i], self.cfg))
        else:
            self.push_screen(PullsScreen(self.prs[i].repo))

    def action_refresh(self) -> None:
        self.sub_title = "loading…"
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        try:
            repos = await service.list_repos(self.cfg)
            prs = await service.list_pulls(self.cfg)
        except Exception as e:
            self.sub_title = f"error: {e}"
            return
        self.repos, self.prs = repos, prs
        rt = self.query_one("#repo-table", DataTable)
        pt = self.query_one("#pr-table", DataTable)
        rt.clear()
        pt.clear()
        for i, r in enumerate(repos):
            rt.add_row(
                *map(
                    Text,
                    (
                        r.full_name,
                        r.language or "",
                        str(r.stars),
                        str(r.open_issues),
                        r.pushed_at.strftime("%Y-%m-%d") if r.pushed_at else "",
                    ),
                ),
                key=str(i),
            )
        for i, p in enumerate(prs):
            pt.add_row(
                *map(
                    Text,
                    (
                        p.repo,
                        str(p.number),
                        p.title,
                        p.author,
                        p.updated_at.strftime("%Y-%m-%d") if p.updated_at else "",
                    ),
                ),
                key=str(i),
            )
        self.sub_title = (
            f"{len(repos)} repos · {len(prs)} open PRs · {len(self.cfg.sources)} sources"
        )
