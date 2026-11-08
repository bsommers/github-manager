import pytest
from typer.testing import CliRunner

from gmac import cli

pytestmark = pytest.mark.system
run = CliRunner().invoke


@pytest.fixture
def stub(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAC_CONFIG", str(tmp_path / "c.toml"))
    calls = {"run": [], "open": []}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls["run"].append((app, kw)))
    monkeypatch.setattr("webbrowser.open", lambda url: calls["open"].append(url))
    return calls


def test_gui_defaults_bind_loopback_and_open_browser(stub):
    r = run(cli.app, ["gui"])
    assert r.exit_code == 0, r.output
    ((app, kw),) = stub["run"]
    assert kw["host"] == "127.0.0.1" and kw["port"] == 8765
    assert stub["open"] == ["http://127.0.0.1:8765/"]
    assert app.title == "GMAC"
    assert "http://127.0.0.1:8765/" in r.output


def test_gui_no_open_and_custom_port(stub):
    r = run(cli.app, ["gui", "--no-open", "--port", "9001", "--host", "::1"])
    assert r.exit_code == 0, r.output
    assert stub["open"] == []
    assert stub["run"][0][1]["port"] == 9001 and stub["run"][0][1]["host"] == "::1"
    assert "http://[::1]:9001/" in r.output


def test_gui_bad_config_exits_1(stub, tmp_path):
    (tmp_path / "c.toml").write_text("sources = 5")
    r = run(cli.app, ["gui", "--no-open"])
    assert r.exit_code == 1 and stub["run"] == []
