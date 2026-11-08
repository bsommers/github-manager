from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import auth, service
from .config import Config, config_path
from .models import Source

app = typer.Typer(no_args_is_help=True, help="GMAC: Git Manager Admin Console.")
sources_app = typer.Typer(no_args_is_help=True, help="Manage tracked users/orgs.")
app.add_typer(sources_app, name="sources")
auth_app = typer.Typer(
    no_args_is_help=True, help="Credentials: reuse gh/glab, env tokens, or store one."
)
app.add_typer(auth_app, name="auth")
out = Console()
err = Console(stderr=True)

SourceOpt = Annotated[str | None, typer.Option("--source", "-s", help="Limit to one source.")]
JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable output.")]


def _run(coro):
    try:
        return asyncio.run(coro)
    except Exception as e:  # surface as a clean CLI error, not a traceback
        err.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e


@sources_app.command("add")
def sources_add(
    name: str,
    org: Annotated[bool, typer.Option("--org")] = False,
    provider: Annotated[str, typer.Option("--provider", "-p", help="github or gitlab")] = "github",
) -> None:
    """Track a user (default) or organization/group."""
    if provider == "gitlab":
        err.print("[red]gitlab sources are specced (docs/SPEC.md §6) but not implemented yet[/red]")
        raise typer.Exit(2)
    cfg = Config.load()
    cfg.add(Source(name=name, kind="org" if org else "user", provider=provider))
    out.print(f"saved to {cfg.save()}")


@sources_app.command("remove")
def sources_remove(name: str) -> None:
    cfg = Config.load()
    if not cfg.remove(name):
        err.print(f"[red]not tracked:[/red] {name}")
        raise typer.Exit(1)
    cfg.save()


@sources_app.command("list")
def sources_list() -> None:
    cfg = Config.load()
    for s in cfg.sources:
        out.print(f"{s.kind:5} {s.name}")
    if not cfg.sources:
        out.print(f"none configured ({config_path()})")


@app.command()
def repos(
    source: SourceOpt = None,
    archived: Annotated[bool, typer.Option("--archived")] = False,
    as_json: JsonOpt = False,
) -> None:
    """List repos across all tracked sources, most recently pushed first."""
    rows = _run(service.list_repos(Config.load(), source, archived))
    if as_json:
        typer.echo("[" + ",".join(r.model_dump_json() for r in rows) + "]")
        return
    t = Table("repo", "lang", "★", "issues", "pushed")
    for r in rows:
        t.add_row(
            r.full_name + (" 🔒" if r.private else ""),
            r.language or "",
            str(r.stars),
            str(r.open_issues),
            r.pushed_at.strftime("%Y-%m-%d") if r.pushed_at else "",
        )
    out.print(t)


@app.command()
def prs(source: SourceOpt = None, as_json: JsonOpt = False) -> None:
    """List open PRs across all tracked sources, most recently updated first."""
    rows = _run(service.list_pulls(Config.load(), source))
    if as_json:
        typer.echo("[" + ",".join(p.model_dump_json() for p in rows) + "]")
        return
    t = Table("repo", "#", "title", "author", "updated")
    for p in rows:
        t.add_row(
            p.repo,
            str(p.number),
            p.title + (" [draft]" if p.draft else ""),
            p.author,
            p.updated_at.strftime("%Y-%m-%d") if p.updated_at else "",
        )
    out.print(t)


@app.command()
def tui() -> None:
    """Interactive terminal UI."""
    from .tui import GmacApp

    GmacApp(Config.load()).run()


@app.command()
def mcp(
    http: Annotated[bool, typer.Option("--http", help="Serve over HTTP instead of stdio.")] = False,
) -> None:
    """Run the MCP server (stdio by default)."""
    from .mcp_server import server

    server.run(transport="http") if http else server.run()


ProviderOpt = Annotated[str, typer.Option("--provider", "-p", help="github or gitlab")]


@auth_app.command("status")
def auth_status() -> None:
    """Show where each provider's credential comes from (never prints the token)."""
    for provider in ("github", "gitlab"):
        c = auth.find_credential(provider)
        out.print(
            f"{provider:7} "
            + (f"[green]ok[/green] via {c.origin}" if c else "[yellow]none[/yellow]")
        )


@auth_app.command("login")
def auth_login(
    provider: ProviderOpt = "github",
    token: Annotated[
        bool, typer.Option("--token", help="Paste an API token instead of browser login.")
    ] = False,
) -> None:
    """Browser/OAuth login via gh or glab, or store a pasted personal access token in the keychain."""
    if provider not in auth.CLI:
        err.print("[red]provider must be github or gitlab[/red]")
        raise typer.Exit(2)
    if token:
        auth.store_token(provider, typer.prompt("Token", hide_input=True))
        out.print("stored in OS keychain")
        return
    try:
        raise typer.Exit(auth.cli_login(provider))
    except RuntimeError as e:
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e


@auth_app.command("logout")
def auth_logout(provider: ProviderOpt = "github") -> None:
    """Remove the token GMAC stored (does not touch gh/glab sessions)."""
    out.print("removed" if auth.forget_token(provider) else "nothing stored by gmac")
