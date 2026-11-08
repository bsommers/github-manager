import pytest

from gmac import auth
from gmac.config import Config
from gmac.models import Source

pytestmark = pytest.mark.unit


def test_config_roundtrip_and_dedupe(tmp_path):
    p = tmp_path / "c.toml"
    c = Config()
    c.add(Source(name="Acme", kind="org"))
    c.add(Source(name="acme"))  # case-insensitive duplicate ignored
    c.save(p)
    assert Config.load(p).sources == [Source(name="Acme", kind="org")]
    assert c.remove("ACME") and not c.remove("acme")


def test_missing_config_is_empty(tmp_path):
    assert Config.load(tmp_path / "none.toml").sources == []


def test_env_beats_keychain_beats_cli(monkeypatch):
    for v in sum(auth.ENV.values(), ()):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(auth, "_stored", lambda p, h: "kc")
    monkeypatch.setattr(auth, "_cli_token", lambda p, h: "cli")
    assert auth.find_credential("github").origin == "keychain"
    monkeypatch.setenv("GH_TOKEN", "env")
    assert auth.find_credential("github").origin == "env:GH_TOKEN"
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setattr(auth, "_stored", lambda p, h: None)
    assert auth.find_credential("github").origin == "gh"
    monkeypatch.setattr(auth, "_cli_token", lambda p, h: None)
    assert auth.find_credential("gitlab") is None


def test_providers_do_not_share_tokens(monkeypatch):
    for v in sum(auth.ENV.values(), ()):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(auth, "_stored", lambda p, h: None)
    monkeypatch.setattr(auth, "_cli_token", lambda p, h: None)
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    assert auth.resolve_token("gitlab") is None
