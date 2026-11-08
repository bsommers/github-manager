from __future__ import annotations

from typing import Any

import httpx

from .models import PullRequest, Repo, Source

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token: str | None, transport: httpx.AsyncBaseTransport | None = None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.AsyncClient(
            base_url=API, headers=headers, transport=transport, timeout=30, follow_redirects=True
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> GitHub:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _get(self, path: str, **params: Any) -> Any:
        r = await self._http.get(path, params=params)
        if r.status_code >= 400:
            try:
                detail = r.json().get("message", r.text)
            except ValueError:  # e.g. an HTML 502 page
                detail = r.text[:200]
            raise GitHubError(f"{r.status_code} on {path}: {detail}")
        return r.json()

    async def _paged(self, path: str, limit: int, **params: Any) -> list[Any]:
        items: list[Any] = []
        page = 1
        while len(items) < limit:
            batch = await self._get(path, per_page=100, page=page, **params)
            batch = batch["items"] if isinstance(batch, dict) else batch
            items += batch
            if len(batch) < 100:
                break
            page += 1
        return items[:limit]

    async def repos(self, source: Source, limit: int = 500) -> list[Repo]:
        path = (
            f"/orgs/{source.name}/repos" if source.kind == "org" else f"/users/{source.name}/repos"
        )
        raw = await self._paged(path, limit, sort="pushed")
        return [
            Repo(
                full_name=r["full_name"],
                owner=r["owner"]["login"],
                private=r["private"],
                archived=r["archived"],
                fork=r["fork"],
                language=r["language"],
                stars=r["stargazers_count"],
                open_issues=r["open_issues_count"],
                pushed_at=r["pushed_at"],
                url=r["html_url"],
            )
            for r in raw
        ]

    async def pulls(self, source: Source, limit: int = 200) -> list[PullRequest]:
        """Open PRs across every repo of a source, via one search query."""
        qualifier = "org" if source.kind == "org" else "user"
        raw = await self._paged(
            "/search/issues",
            limit,
            q=f"is:pr is:open archived:false {qualifier}:{source.name}",
            sort="updated",
        )
        return [
            PullRequest(
                repo=i["repository_url"].removeprefix(f"{API}/repos/"),
                number=i["number"],
                title=i["title"],
                author=i["user"]["login"],
                draft=i.get("draft", False),
                updated_at=i["updated_at"],
                url=i["html_url"],
            )
            for i in raw
        ]
