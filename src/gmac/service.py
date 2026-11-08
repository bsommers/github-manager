"""Surface-independent operations. CLI, TUI and MCP are thin wrappers over these."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from . import local
from .auth import resolve_token
from .config import Config
from .github import GitHub
from .models import Issue, LocalInfo, PullDetail, PullRequest, Repo, Source


def _sources(cfg: Config, only: str | None) -> list[Source]:
    chosen = [s for s in cfg.sources if only is None or s.name.lower() == only.lower()]
    if not chosen:
        raise ValueError(
            f"no sources match {only!r}"
            if only
            else "no sources configured; run `gmac sources add`"
        )
    return chosen


@asynccontextmanager
async def _client(gh: GitHub | None) -> AsyncIterator[GitHub]:
    """Use the injected client, or build one from the credential chain and always close it."""
    if gh is not None:
        yield gh
        return
    own = GitHub(resolve_token("github"))
    try:
        yield own
    finally:
        await own.aclose()


async def list_repos(
    cfg: Config,
    source: str | None = None,
    include_archived: bool = False,
    gh: GitHub | None = None,
) -> list[Repo]:
    async with _client(gh) as c:
        groups = await asyncio.gather(*(c.repos(s) for s in _sources(cfg, source)))
    repos = [r for g in groups for r in g if include_archived or not r.archived]
    return sorted(repos, key=lambda r: r.pushed_at.timestamp() if r.pushed_at else 0, reverse=True)


async def list_pulls(
    cfg: Config, source: str | None = None, gh: GitHub | None = None
) -> list[PullRequest]:
    async with _client(gh) as c:
        groups = await asyncio.gather(*(c.pulls(s) for s in _sources(cfg, source)))
    prs = [p for g in groups for p in g]
    return sorted(prs, key=lambda p: p.updated_at.timestamp() if p.updated_at else 0, reverse=True)


async def local_info(cfg: Config, full_name: str) -> LocalInfo:
    """Clone location, remote and git status; disk and git work runs off the event loop."""
    return await asyncio.to_thread(local.locate, full_name, cfg.roots)


async def list_issues(repo: str, gh: GitHub | None = None) -> list[Issue]:
    async with _client(gh) as c:
        return await c.issues(repo)


async def list_repo_pulls(repo: str, gh: GitHub | None = None) -> list[PullDetail]:
    async with _client(gh) as c:
        return await c.repo_pulls(repo)


async def get_pull(repo: str, number: int, gh: GitHub | None = None) -> PullDetail:
    async with _client(gh) as c:
        return await c.pull(repo, number)
