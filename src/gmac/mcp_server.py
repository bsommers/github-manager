from __future__ import annotations

from fastmcp import FastMCP

from . import service
from .config import Config
from .models import PullRequest, Repo

server = FastMCP("gmac", instructions="Registry of GitHub repos and PRs across tracked users/orgs.")


@server.tool
def list_sources() -> list[dict]:
    """Tracked GitHub users/orgs."""
    return [s.model_dump() for s in Config.load().sources]


@server.tool
async def list_repos(source: str | None = None, include_archived: bool = False) -> list[Repo]:
    """Repos across tracked sources (optionally one), newest push first."""
    return await service.list_repos(Config.load(), source, include_archived)


@server.tool
async def list_pull_requests(source: str | None = None) -> list[PullRequest]:
    """Open PRs across tracked sources (optionally one), newest update first."""
    return await service.list_pulls(Config.load(), source)
