from __future__ import annotations

import os
import tomllib
from pathlib import Path

import tomli_w
from platformdirs import user_config_dir
from pydantic import BaseModel, Field

from .models import Source


def config_path() -> Path:
    override = os.environ.get("GMAC_CONFIG")
    return Path(override) if override else Path(user_config_dir("gmac")) / "config.toml"


class Config(BaseModel):
    sources: list[Source] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or config_path()
        if not path.exists():
            return cls()
        return cls.model_validate(tomllib.loads(path.read_text()))

    def save(self, path: Path | None = None) -> Path:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomli_w.dumps(self.model_dump(mode="json")))
        return path

    def add(self, source: Source) -> None:
        if not any(s.name.lower() == source.name.lower() for s in self.sources):
            self.sources.append(source)

    def remove(self, name: str) -> bool:
        before = len(self.sources)
        self.sources = [s for s in self.sources if s.name.lower() != name.lower()]
        return len(self.sources) != before
