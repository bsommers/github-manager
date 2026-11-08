from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.command import CommandPalette
from textual.widgets import DataTable, Footer, Header, TabbedContent, TabPane

from . import service
from .config import Config


class GmacApp(App):
    TITLE = "GMAC"
    BINDINGS = [("r", "refresh", "Refresh"), ("q", "quit", "Quit")]

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg

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
                yield DataTable(id="repo-table", cursor_type="row", zebra_stripes=True)
            with TabPane("Pull requests", id="prs"):
                yield DataTable(id="pr-table", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#repo-table", DataTable).add_columns(
            "repo", "lang", "★", "issues", "pushed"
        )
        self.query_one("#pr-table", DataTable).add_columns(
            "repo", "#", "title", "author", "updated"
        )
        self.action_refresh()

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
        rt = self.query_one("#repo-table", DataTable)
        pt = self.query_one("#pr-table", DataTable)
        rt.clear()
        pt.clear()
        for r in repos:
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
                )
            )
        for p in prs:
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
                )
            )
        self.sub_title = (
            f"{len(repos)} repos · {len(prs)} open PRs · {len(self.cfg.sources)} sources"
        )
