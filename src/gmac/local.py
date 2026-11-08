"""Find a repo's clone on disk and read its git state. Read-only; never runs repo-supplied code."""

from __future__ import annotations

import configparser
import os
import re
import subprocess
from pathlib import Path

from .models import GitStatus, LocalInfo

SKIP = {"node_modules", ".venv", "venv", "target", "__pycache__", ".cache", "Library"}
_REMOTE = re.compile(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$")
_BRANCH = re.compile(
    r"^## (?:No commits yet on |Initial commit on )?(?P<b>HEAD \(no branch\)|[^. ]+(?:\.[^. ]+)*?)"
    r"(?:\.\.\.\S+)?(?: \[(?P<t>[^\]]+)\])?$"
)


def parse_remote(url: str) -> str | None:
    """'git@github.com:o/r.git' or 'https://github.com/o/r' -> 'o/r' (lowercased)."""
    m = _REMOTE.search(url.strip())
    return f"{m[1]}/{m[2]}".lower() if m else None


def read_origin(repo: Path) -> str | None:
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cfg.read(repo / ".git" / "config")
        return cfg.get('remote "origin"', "url", fallback=None)
    except configparser.Error:
        return None


def scan(roots: list[Path], max_depth: int = 4) -> dict[str, list[tuple[Path, str]]]:
    """Map 'owner/name' (lowercase) -> [(clone dir, origin url)]. Does not descend into clones."""
    found: dict[str, list[tuple[Path, str]]] = {}

    def walk(d: Path, depth: int) -> None:
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        if any(e.name == ".git" and e.is_dir(follow_symlinks=False) for e in entries):
            url = read_origin(d)
            if url and (key := parse_remote(url)):
                found.setdefault(key, []).append((d, url))
            return
        if depth >= max_depth:
            return
        for e in entries:
            if (
                e.is_dir(follow_symlinks=False)
                and e.name not in SKIP
                and not e.name.startswith(".")
            ):
                walk(Path(e.path), depth + 1)

    for r in roots:
        walk(r, 0)
    return found


def git_status(path: Path) -> GitStatus:
    # core.fsmonitor=false: a hostile clone's config could otherwise run a command on `status`.
    out = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(path), "status", "--porcelain=v1", "-b"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    ).stdout.splitlines()
    head = _BRANCH.match(out[0]) if out else None
    st = GitStatus(branch=head["b"] if head else "(unknown)")
    for part in (head["t"] if head and head["t"] else "").split(", "):
        if part.startswith("ahead "):
            st.ahead = int(part[6:])
        elif part.startswith("behind "):
            st.behind = int(part[7:])
    for line in out[1:]:
        x, y = line[0], line[1]
        if x == "?":
            st.untracked += 1
            continue
        st.staged += x not in " !"
        st.modified += y not in " !"
    return st


def locate(full_name: str, roots: list[str]) -> LocalInfo:
    index = scan([Path(r).expanduser() for r in roots])
    hits = index.get(full_name.lower())
    if not hits:
        return LocalInfo()
    info = LocalInfo(clones=[p for p, _ in hits], remote=hits[0][1])
    try:
        info.status = git_status(hits[0][0])
    except (OSError, subprocess.SubprocessError) as e:
        info.error = f"git status failed: {e}"
    return info
