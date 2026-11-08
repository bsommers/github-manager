import configparser
import os
import subprocess
from pathlib import Path

import pytest

from gmac import local
from gmac.models import GitStatus

pytestmark = pytest.mark.unit

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


@pytest.fixture(autouse=True)
def _git_env(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


def git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    ).stdout


def init(path: Path, remote: str | None = None, commit: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    if remote:
        git(path, "remote", "add", "origin", remote)
    if commit:
        (path / "f.txt").write_text("x")
        git(path, "add", "f.txt")
        git(path, "commit", "-q", "-m", "init")
    return path


@pytest.mark.parametrize(
    ("url", "want"),
    [
        ("git@github.com:Owner/Repo.git", "owner/repo"),
        ("https://github.com/Owner/Repo", "owner/repo"),
        ("https://github.com/o/r.git", "o/r"),
        ("https://github.com/o/r/", "o/r"),
        ("ssh://git@github.com/o/r.git", "o/r"),
        ("  https://github.com/o/r.git \n", "o/r"),
        ("garbage", None),
        ("", None),
    ],
)
def test_parse_remote(url, want):
    assert local.parse_remote(url) == want


def test_read_origin(tmp_path):
    assert local.read_origin(tmp_path) is None  # missing file
    (tmp_path / ".git").mkdir()
    cfg = tmp_path / ".git" / "config"
    cfg.write_text("[core]\nbare = false\n")
    assert local.read_origin(tmp_path) is None  # no origin
    cfg.write_text('[remote "origin"]\n\turl = git@github.com:o/r.git\n')
    assert local.read_origin(tmp_path) == "git@github.com:o/r.git"
    cfg.write_text("this is not [ valid\n")
    assert local.read_origin(tmp_path) is None  # malformed


def test_read_origin_swallows_configparser_error(tmp_path, monkeypatch):
    def boom(self, *a, **k):
        raise configparser.Error("bad")

    monkeypatch.setattr(configparser.ConfigParser, "read", boom)
    assert local.read_origin(tmp_path) is None


def test_scan_rules(tmp_path):
    a = init(tmp_path / "a", "git@github.com:o/a.git", commit=False)
    deep = init(tmp_path / "x" / "y" / "z" / "deep", "https://github.com/o/deep", commit=False)
    too_deep = init(tmp_path / "1" / "2" / "3" / "4" / "5" / "r", "https://github.com/o/far", False)
    skipped = init(tmp_path / "node_modules" / "pkg", "https://github.com/o/skip", commit=False)
    hidden = init(tmp_path / ".hid" / "r", "https://github.com/o/hidden", commit=False)
    nested = init(a / "sub" / "nested", "https://github.com/o/nested", commit=False)
    noremote = init(tmp_path / "plain", commit=False)
    junk = init(tmp_path / "junk", "garbage", commit=False)
    (tmp_path / "file.txt").write_text("not a dir")
    (tmp_path / "link").symlink_to(a, target_is_directory=True)
    found = local.scan([tmp_path, tmp_path / "missing-root"])
    assert found["o/a"] == [(a, "git@github.com:o/a.git")]
    assert "o/deep" in found
    assert not ({"o/far", "o/skip", "o/hidden", "o/nested"} & found.keys())
    assert all(p not in (noremote, junk) for v in found.values() for p, _ in v)
    assert too_deep.exists() and skipped.exists() and hidden.exists() and nested.exists()
    assert deep.exists()


def test_scan_unreadable_dir(tmp_path):
    d = tmp_path / "locked"
    d.mkdir()
    d.chmod(0)
    try:
        assert local.scan([tmp_path]) == {}
    finally:
        d.chmod(0o755)


def test_git_status_clean_and_dirty(tmp_path):
    r = init(tmp_path / "r")
    assert local.git_status(r) == GitStatus(branch="main")
    assert local.git_status(r).clean
    (r / "f.txt").write_text("changed")
    (r / "new.txt").write_text("n")
    (r / "staged.txt").write_text("s")
    git(r, "add", "staged.txt")
    st = local.git_status(r)
    assert (st.staged, st.modified, st.untracked) == (1, 1, 1)
    assert not st.clean


def test_git_status_ahead_behind(tmp_path):
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    a = init(tmp_path / "a", str(bare))
    git(a, "push", "-q", "origin", "main")
    git(a, "branch", "--set-upstream-to=origin/main", "main")
    b = tmp_path / "b"
    subprocess.run(["git", "clone", "-q", str(bare), str(b)], check=True)
    (b / "g.txt").write_text("g")
    git(b, "add", "g.txt")
    git(b, "commit", "-q", "-m", "g")
    git(b, "push", "-q", "origin", "main")
    (a / "h.txt").write_text("h")
    git(a, "add", "h.txt")
    git(a, "commit", "-q", "-m", "h")
    git(a, "fetch", "-q")
    st = local.git_status(a)
    assert (st.branch, st.ahead, st.behind) == ("main", 1, 1)


def test_git_status_no_commits_and_detached(tmp_path):
    r = init(tmp_path / "empty", commit=False)
    assert local.git_status(r).branch == "main"
    r2 = init(tmp_path / "det")
    git(r2, "checkout", "-q", "--detach")
    assert local.git_status(r2).branch == "HEAD (no branch)"


def test_git_status_empty_output_is_unknown(monkeypatch, tmp_path):
    class R:
        stdout = ""

    monkeypatch.setattr(local.subprocess, "run", lambda *a, **k: R())
    assert local.git_status(tmp_path).branch == "(unknown)"


def test_locate(tmp_path):
    assert local.locate("o/r", [str(tmp_path)]).clones == []
    r = init(tmp_path / "r", "https://github.com/O/R.git")
    info = local.locate("o/R", [str(tmp_path)])
    assert info.clones == [r]
    assert info.remote == "https://github.com/O/R.git"
    assert info.status and info.status.branch == "main"


def test_locate_git_failure(tmp_path, monkeypatch):
    init(tmp_path / "r", "https://github.com/o/r")

    def boom(path):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(local, "git_status", boom)
    info = local.locate("o/r", [str(tmp_path)])
    assert info.status is None and "git status failed" in (info.error or "")


def test_fsmonitor_hook_is_not_executed(tmp_path):
    r = init(tmp_path / "evil", "https://github.com/o/evil")
    marker = tmp_path / "PWNED"
    hook = tmp_path / "hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    git(r, "config", "core.fsmonitor", str(hook))
    (r / "f.txt").write_text("dirty")
    st = local.git_status(r)
    assert st.modified == 1
    assert not marker.exists()
