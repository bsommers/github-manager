import stat
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.system
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install.sh"


def sh(*args, path: str, env_extra=None):
    env = {"PATH": path, "HOME": "/nonexistent", **(env_extra or {})}
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False
    )


@pytest.fixture
def fake_bin(tmp_path):
    """A PATH holding a stub `uv` that records its arguments and nothing else."""
    b = tmp_path / "bin"
    b.mkdir()
    log = tmp_path / "uv.log"
    uv = b / "uv"
    uv.write_text(f'#!/bin/sh\necho "$@" >> {log}\n[ "$1 $2" = "tool dir" ] && echo {b}\nexit 0\n')
    uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
    return b, log


BASE = "/usr/bin:/bin"


def test_syntax_and_help():
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0
    r = sh("--help", path=BASE)
    assert r.returncode == 0 and "--uninstall" in r.stdout


def test_unknown_option_exits_2():
    r = sh("--bogus", path=BASE)
    assert r.returncode == 2 and "unknown option" in r.stderr


def test_missing_uv_fails_with_guidance_and_does_not_download():
    r = sh(path=BASE)
    assert r.returncode == 1 and "--install-uv" in r.stdout


def test_dry_run_changes_nothing_even_without_uv():
    r = sh("--dry-run", path=BASE)
    assert r.returncode == 0 and "[dry-run] uv tool install --editable --force" in r.stdout
    r = sh("--dry-run", "--install-uv", path=BASE)
    assert "[dry-run] curl" in r.stdout


def test_editable_install_uses_this_clone(fake_bin):
    b, log = fake_bin
    r = sh(path=f"{b}:{BASE}")
    assert r.returncode == 0
    assert f"tool install --editable --force {ROOT}" in log.read_text()
    assert "uv tool update-shell" in r.stdout  # stub gmac is not on PATH


def test_git_mode_with_ref_and_uninstall(fake_bin):
    b, log = fake_bin
    sh("--git", "v1.2.3", path=f"{b}:{BASE}")
    sh("--uninstall", path=f"{b}:{BASE}")
    text = log.read_text()
    assert "tool install --force git+https://github.com/bsommers/github-manager@v1.2.3" in text
    assert "tool uninstall gmac" in text


def test_reports_login_status_when_gmac_present(fake_bin):
    b, _ = fake_bin
    g = b / "gmac"
    g.write_text("#!/bin/sh\necho github ok via gh\n")
    g.chmod(g.stat().st_mode | stat.S_IEXEC)
    r = sh(path=f"{b}:{BASE}")
    assert "Installed:" in r.stdout and "github ok via gh" in r.stdout
