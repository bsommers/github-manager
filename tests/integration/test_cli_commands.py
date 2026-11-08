import json
import runpy
import sys

import pytest
from typer.testing import CliRunner

from gmac import auth, cli
from gmac.models import PullRequest, Repo

pytestmark = pytest.mark.integration
run = CliRunner().invoke

REPOS = [
    Repo(
        full_name="o/pub",
        owner="o",
        language="Python",
        stars=2,
        open_issues=1,
        pushed_at="2026-02-03T00:00:00Z",
    ),
    Repo(full_name="o/priv", owner="o", private=True),  # no language, no push date
]
PRS = [
    PullRequest(
        repo="o/pub",
        number=3,
        title="Add x",
        author="me",
        draft=True,
        updated_at="2026-02-03T00:00:00Z",
    ),
    PullRequest(repo="o/pub", number=4, title="Fix y", author="you"),  # no date
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAC_CONFIG", str(tmp_path / "c.toml"))

    async def repos(cfg, source=None, archived=False):
        env.calls.append(("repos", source, archived))
        return REPOS

    async def pulls(cfg, source=None):
        env.calls.append(("prs", source))
        return PRS

    env.calls = []
    monkeypatch.setattr(cli.service, "list_repos", repos)
    monkeypatch.setattr(cli.service, "list_pulls", pulls)
    return env


def test_sources_remove_missing_exits_1(env):
    r = run(cli.app, ["sources", "remove", "nobody"])
    assert r.exit_code == 1 and "not tracked" in r.output


def test_sources_add_list_remove_flow(env):
    assert run(cli.app, ["sources", "add", "me"]).exit_code == 0
    assert run(cli.app, ["sources", "add", "acme", "--org"]).exit_code == 0
    out = run(cli.app, ["sources", "list"]).output
    assert "user  me" in out and "org   acme" in out
    assert run(cli.app, ["sources", "remove", "ME"]).exit_code == 0
    assert "user  me" not in run(cli.app, ["sources", "list"]).output


def test_repos_table_marks_private_and_blanks(env):
    r = run(cli.app, ["repos", "-s", "o", "--archived"])
    assert r.exit_code == 0
    assert "o/pub" in r.output and "🔒" in r.output and "2026-02-03" in r.output
    assert env.calls == [("repos", "o", True)]


def test_repos_json_is_valid_and_complete(env):
    r = run(cli.app, ["repos", "--json"])
    data = json.loads(r.output)
    assert [d["full_name"] for d in data] == ["o/pub", "o/priv"]
    assert data[1]["private"] is True


def test_prs_table_and_json(env):
    r = run(cli.app, ["prs"])
    assert "Add x [draft]" in r.output and "Fix y" in r.output
    data = json.loads(run(cli.app, ["prs", "--json", "-s", "o"]).output)
    assert [d["number"] for d in data] == [3, 4]


def test_service_error_becomes_clean_exit_1(env, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("kaput")

    monkeypatch.setattr(cli.service, "list_repos", boom)
    r = run(cli.app, ["repos"])
    assert r.exit_code == 1 and "kaput" in r.output and "Traceback" not in r.output


def test_tui_and_mcp_commands_dispatch(env, monkeypatch):
    import gmac.mcp_server as m
    import gmac.tui as t

    ran = []
    monkeypatch.setattr(t.GmacApp, "run", lambda self: ran.append("tui"))
    monkeypatch.setattr(m.server, "run", lambda **k: ran.append(("mcp", k)))
    assert run(cli.app, ["tui"]).exit_code == 0
    assert run(cli.app, ["mcp"]).exit_code == 0
    assert run(cli.app, ["mcp", "--http"]).exit_code == 0
    assert ran == ["tui", ("mcp", {}), ("mcp", {"transport": "http"})]


def test_auth_status_never_prints_token(env, monkeypatch):
    monkeypatch.setattr(
        auth,
        "find_credential",
        lambda p, host=None: auth.Credential("fake-secret", "gh") if p == "github" else None,
    )
    r = run(cli.app, ["auth", "status"])
    assert "via gh" in r.output and "none" in r.output and "fake-secret" not in r.output


def test_auth_login_token_stores_in_keychain(env, monkeypatch):
    stored = []
    monkeypatch.setattr(auth, "store_token", lambda p, t: stored.append((p, t)))
    r = run(cli.app, ["auth", "login", "-p", "gitlab", "--token"], input="fake-pat\n")
    assert r.exit_code == 0 and stored == [("gitlab", "fake-pat")]
    assert "fake-pat" not in r.output  # hidden prompt


def test_auth_login_browser_delegates_and_propagates_exit(env, monkeypatch):
    monkeypatch.setattr(auth, "cli_login", lambda p: 0)
    assert run(cli.app, ["auth", "login"]).exit_code == 0
    monkeypatch.setattr(auth, "cli_login", lambda p: 3)
    assert run(cli.app, ["auth", "login"]).exit_code == 3


def test_auth_login_missing_cli_and_bad_provider(env, monkeypatch):
    def missing(p):
        raise RuntimeError("`gh` not installed")

    monkeypatch.setattr(auth, "cli_login", missing)
    r = run(cli.app, ["auth", "login"])
    assert r.exit_code == 1 and "not installed" in r.output
    r = run(cli.app, ["auth", "login", "-p", "bitbucket"])
    assert r.exit_code == 2


def test_auth_logout(env, monkeypatch):
    monkeypatch.setattr(auth, "forget_token", lambda p: True)
    assert "removed" in run(cli.app, ["auth", "logout"]).output
    monkeypatch.setattr(auth, "forget_token", lambda p: False)
    assert "nothing stored" in run(cli.app, ["auth", "logout"]).output


def test_cli_main_module_invokes_app(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["gmac", "--help"])
    sys.modules.pop("gmac.cli_main", None)
    with pytest.raises(SystemExit) as e:
        runpy.run_module("gmac.cli_main", run_name="__main__")
    assert e.value.code == 0
    assert "Usage" in capsys.readouterr().out


def test_gitlab_source_rejected_with_exit_2(env):
    r = run(cli.app, ["sources", "add", "x", "-p", "gitlab"])
    assert r.exit_code == 2 and "not implemented" in r.output


def test_sources_list_empty_hint(env):
    assert "none configured" in run(cli.app, ["sources", "list"]).output


def test_bracket_text_is_shown_literally_not_eaten_as_markup(env, monkeypatch):
    async def pulls(cfg, source=None):
        return [PullRequest(repo="o/[x]", number=1, title="[WIP] fix [/oops]", author="a[b]")]

    async def boom(cfg, source=None, archived=False):
        raise RuntimeError("bad [/unclosed] thing")

    monkeypatch.setattr(cli.service, "list_pulls", pulls)
    monkeypatch.setattr(cli.service, "list_repos", boom)
    out = run(cli.app, ["prs"]).output
    assert "[WIP] fix [/oops]" in out and "o/[x]" in out and "a[b]" in out
    r = run(cli.app, ["repos"])  # would crash with MarkupError if unescaped
    assert r.exit_code == 1 and "bad [/unclosed] thing" in r.output


def test_cli_main_import_does_not_run_app():
    runpy.run_module("gmac.cli_main", run_name="not_main")
