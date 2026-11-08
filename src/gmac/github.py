from __future__ import annotations

from typing import Any

import httpx

from .models import Issue, PullDetail, PullRequest, Repo, Source

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


def _login(user: dict | None) -> str:
    return (user or {}).get("login", "ghost")  # deleted accounts come back as null


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
                author=_login(i["user"]),
                draft=i.get("draft", False),
                updated_at=i["updated_at"],
                url=i["html_url"],
            )
            for i in raw
        ]

    async def issues(self, repo: str, limit: int = 200) -> list[Issue]:
        raw = await self._paged(f"/repos/{repo}/issues", limit, state="open", sort="updated")
        return [
            Issue(
                repo=repo,
                number=i["number"],
                title=i["title"],
                author=_login(i["user"]),
                labels=[lbl["name"] for lbl in i["labels"]],
                comments=i["comments"],
                body=i["body"] or "",
                updated_at=i["updated_at"],
                url=i["html_url"],
            )
            for i in raw
            if "pull_request" not in i  # the issues endpoint also returns PRs
        ]

    async def repo_pulls(self, repo: str, limit: int = 200) -> list[PullDetail]:
        raw = await self._paged(
            f"/repos/{repo}/pulls", limit, state="open", sort="updated", direction="desc"
        )
        return [self._pull(repo, p) for p in raw]

    async def pull(self, repo: str, number: int) -> PullDetail:
        return self._pull(repo, await self._get(f"/repos/{repo}/pulls/{number}"))

    @staticmethod
    def _pull(repo: str, p: dict) -> PullDetail:
        return PullDetail(
            repo=repo,
            number=p["number"],
            title=p["title"],
            author=_login(p["user"]),
            draft=p.get("draft", False),
            updated_at=p["updated_at"],
            url=p["html_url"],
            head=p["head"]["ref"],
            base=p["base"]["ref"],
            body=p.get("body") or "",
            created_at=p.get("created_at"),
            additions=p.get("additions", 0),
            deletions=p.get("deletions", 0),
            changed_files=p.get("changed_files", 0),
            commits=p.get("commits", 0),
            comments=p.get("comments", 0) + p.get("review_comments", 0),
            mergeable_state=p.get("mergeable_state") or "",
        )
