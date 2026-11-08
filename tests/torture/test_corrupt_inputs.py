import pytest
from typer.testing import CliRunner

from gmac import cli
from gmac.config import Config, ConfigError

pytestmark = pytest.mark.torture


@pytest.mark.parametrize(
    "content",
    [
        b"not = [valid toml",
        b"\xff\xfe\x00garbage",
        b'sources = "string not list"',
        b'[[sources]]\nname = 1\nkind = "alien"',
    ],
)
def test_corrupt_config_is_config_error_not_crash(tmp_path, content):
    p = tmp_path / "c.toml"
    p.write_bytes(content)
    with pytest.raises(ConfigError, match="cannot read"):
        Config.load(p)


@pytest.mark.parametrize(
    "argv",
    [["sources", "list"], ["sources", "add", "x"], ["repos"], ["prs"], ["sources", "remove", "x"]],
)
def test_cli_reports_corrupt_config_cleanly(tmp_path, monkeypatch, argv):
    p = tmp_path / "c.toml"
    p.write_text("[[[")
    monkeypatch.setenv("GMAC_CONFIG", str(p))
    r = CliRunner().invoke(cli.app, argv)
    assert r.exit_code == 1 and "cannot read" in r.output and "Traceback" not in r.output
    assert p.read_text() == "[[" + "["  # never overwritten by a failed load
