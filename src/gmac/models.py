from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class Source(BaseModel):
    """A GitHub account whose repos/PRs GMAC tracks."""

    name: str
    kind: Literal["user", "org"] = "user"
    provider: Literal["github", "gitlab"] = "github"


class Repo(BaseModel):
    full_name: str
    owner: str
    private: bool = False
    archived: bool = False
    fork: bool = False
    language: str | None = None
    stars: int = 0
    open_issues: int = 0
    pushed_at: datetime | None = None
    url: str = ""


class PullRequest(BaseModel):
    repo: str
    number: int
    title: str
    author: str
    draft: bool = False
    updated_at: datetime | None = None
    url: str = ""


class Issue(BaseModel):
    repo: str
    number: int
    title: str
    author: str
    labels: list[str] = []
    comments: int = 0
    body: str = ""
    updated_at: datetime | None = None
    url: str = ""


class PullDetail(PullRequest):
    head: str = ""
    base: str = ""
    body: str = ""
    created_at: datetime | None = None
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    commits: int = 0
    comments: int = 0
    mergeable_state: str = ""


class GitStatus(BaseModel):
    branch: str
    ahead: int = 0
    behind: int = 0
    staged: int = 0
    modified: int = 0
    untracked: int = 0

    @property
    def clean(self) -> bool:
        return not (self.staged or self.modified or self.untracked)


class LocalInfo(BaseModel):
    """Where (if anywhere) a repo is cloned on this machine, and its git state."""

    clones: list[Path] = []
    remote: str | None = None
    status: GitStatus | None = None
    error: str | None = None
