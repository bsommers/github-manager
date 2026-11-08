import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.smoke


def test_imports_and_cli_help():
    from gmac.cli import app

    r = CliRunner().invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("repos", "prs", "tui", "mcp", "sources", "auth"):
        assert cmd in r.output
