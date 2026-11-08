import pytest

from gmac import config
from gmac.config import Config
from gmac.models import Source

pytestmark = pytest.mark.unit


def test_config_path_env_override_and_default(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAC_CONFIG", str(tmp_path / "x.toml"))
    assert config.config_path() == tmp_path / "x.toml"
    monkeypatch.delenv("GMAC_CONFIG")
    assert config.config_path().name == "config.toml"
    assert "gmac" in str(config.config_path())


def test_save_creates_parent_dirs_and_default_path(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAC_CONFIG", str(tmp_path / "a" / "b" / "c.toml"))
    path = Config(sources=[Source(name="x", provider="gitlab")]).save()
    assert path.exists()
    assert Config.load().sources[0].provider == "gitlab"
