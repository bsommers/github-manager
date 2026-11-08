"""Surface-independent operations. CLI, TUI and MCP are thin wrappers over these."""

from __future__ import annotations

import asyncio

from .auth import resolve_token
from .config import Config
from .github import GitHub
from .models import PullRequest, Repo, Source


def _sources(cfg: Config, only: str | None) -> list[Source]:
    chosen = [s for s in cfg.sources if only is None or s.name.lower() == only.lower()]
    if not chosen:
        raise ValueError(
            f"no sources match {only!r}"
            if only
            else "no sources configured; run `gmac sources add`"
        )
    return chosen


async def list_repos(
    cfg: Config,
    source: str | None = None,
    include_archived: bool = False,
    gh: GitHub | None = None,
) -> list[Repo]:
    own = gh is None
    gh = gh or GitHub(resolve_token("github"))
    try:
        groups = await asyncio.gather(*(gh.repos(s) for s in _sources(cfg, source)))
    finally:
        if own:
            await gh.aclose()
    repos = [r for g in groups for r in g if include_archived or not r.archived]
    return sorted(repos, key=lambda r: r.pushed_at.timestamp() if r.pushed_at else 0, reverse=True)


async def list_pulls(
    cfg: Config, source: str | None = None, gh: GitHub | None = None
) -> list[PullRequest]:
    own = gh is None
    gh = gh or GitHub(resolve_token("github"))
    try:
        groups = await asyncio.gather(*(gh.pulls(s) for s in _sources(cfg, source)))
    finally:
        if own:
            await gh.aclose()
    prs = [p for g in groups for p in g]
    return sorted(prs, key=lambda p: p.updated_at.timestamp() if p.updated_at else 0, reverse=True)
