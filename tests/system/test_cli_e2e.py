import subprocess
import sys

import pytest

pytestmark = pytest.mark.system


def gmac(*args, cfg):
    return subprocess.run(
        [sys.executable, "-m", "gmac.cli_main", *args],
        capture_output=True,
        text=True,
        env={"GMAC_CONFIG": str(cfg), "PATH": ""},
    )


def test_sources_lifecycle_and_empty_repos_error(tmp_path):
    cfg = tmp_path / "c.toml"
    assert gmac("sources", "list", cfg=cfg).stdout.startswith("none configured")
    assert gmac("sources", "add", "acme", "--org", cfg=cfg).returncode == 0
    assert "org   acme" in gmac("sources", "list", cfg=cfg).stdout
    assert gmac("sources", "add", "x", "-p", "gitlab", cfg=cfg).returncode == 2
    assert gmac("sources", "remove", "acme", cfg=cfg).returncode == 0
    r = gmac("repos", "--json", cfg=cfg)
    assert r.returncode == 1 and "no sources configured" in r.stderr
