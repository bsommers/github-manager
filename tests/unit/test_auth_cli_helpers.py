import subprocess

import keyring
import keyring.errors
import pytest

from gmac import auth

pytestmark = pytest.mark.unit


class FakeKeyring:
    def __init__(self):
        self.d = {}

    def get_password(self, s, k):
        return self.d.get((s, k))

    def set_password(self, s, k, v):
        self.d[(s, k)] = v

    def delete_password(self, s, k):
        if (s, k) not in self.d:
            raise keyring.errors.PasswordDeleteError("missing")
        del self.d[(s, k)]


@pytest.fixture
def kr(monkeypatch):
    fake = FakeKeyring()
    for name in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(keyring, name, getattr(fake, name))
    return fake


def test_store_find_forget_roundtrip(kr, monkeypatch):
    for v in sum(auth.ENV.values(), ()):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(auth, "_cli_token", lambda p, h: None)
    auth.store_token("gitlab", "fake-token", host="gl.example.com")
    c = auth.find_credential("gitlab", "gl.example.com")
    assert (c.token, c.origin) == ("fake-token", "keychain")
    assert auth.find_credential("gitlab") is None  # different host
    assert auth.forget_token("gitlab", "gl.example.com") is True
    assert auth.forget_token("gitlab", "gl.example.com") is False


def test_stored_swallows_keyring_errors(monkeypatch):
    def boom(*a):
        raise keyring.errors.KeyringError("no backend")

    monkeypatch.setattr(keyring, "get_password", boom)
    assert auth._stored("github", "github.com") is None


def test_default_hosts():
    assert auth.default_host("github") == "github.com"
    assert auth.default_host("gitlab") == "gitlab.com"


def _run_result(code, out):
    return subprocess.CompletedProcess([], code, stdout=out, stderr="")


def test_cli_token_variants(monkeypatch):
    monkeypatch.setattr(auth.shutil, "which", lambda e: None)
    assert auth._cli_token("github", "github.com") is None  # CLI not installed

    monkeypatch.setattr(auth.shutil, "which", lambda e: "/bin/" + e)
    calls = []

    def ok(cmd, **k):
        calls.append(cmd)
        return _run_result(0, "fake-tok\n")

    monkeypatch.setattr(auth.subprocess, "run", ok)
    assert auth._cli_token("gitlab", "gl.example.com") == "fake-tok"
    assert calls[0] == ["glab", "auth", "token", "--hostname", "gl.example.com"]

    monkeypatch.setattr(auth.subprocess, "run", lambda c, **k: _run_result(1, "fake-tok"))
    assert auth._cli_token("github", "github.com") is None  # nonzero exit ignored

    monkeypatch.setattr(auth.subprocess, "run", lambda c, **k: _run_result(0, "  \n"))
    assert auth._cli_token("github", "github.com") is None  # empty output

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("gh", 10)

    monkeypatch.setattr(auth.subprocess, "run", boom)
    assert auth._cli_token("github", "github.com") is None


def test_cli_login(monkeypatch):
    monkeypatch.setattr(auth.shutil, "which", lambda e: None)
    with pytest.raises(RuntimeError, match="not installed"):
        auth.cli_login("github")
    monkeypatch.setattr(auth.shutil, "which", lambda e: "/bin/" + e)
    seen = []
    monkeypatch.setattr(auth.subprocess, "call", lambda cmd: seen.append(cmd) or 0)
    assert auth.cli_login("github") == 0
    assert auth.cli_login("gitlab", "gl.example.com") == 0
    assert seen == [
        ["gh", "auth", "login"],
        ["glab", "auth", "login", "--hostname", "gl.example.com"],
    ]
