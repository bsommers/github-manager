from __future__ import annotations

from datetime import datetime
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
