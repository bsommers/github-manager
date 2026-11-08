"""Docs stay in sync with the code: links resolve, no machine paths, every command is documented."""

import re
from pathlib import Path

import pytest
import typer.main

from gmac.cli import app

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
DOCS = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "CLAUDE.md", *ROOT.glob("docs/**/*.md")]


def test_relative_links_resolve():
    for f in DOCS:
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", f.read_text()):
            if "://" in target:
                continue
            assert (f.parent / target).exists(), f"{f.name}: broken link {target}"


def test_no_absolute_machine_paths():
    for f in DOCS:
        assert not re.search(r"/(Users|home)/\w+", f.read_text()), f.name


def test_every_cli_command_is_in_readme_or_spec():
    text = (ROOT / "README.md").read_text() + (ROOT / "docs/SPEC.md").read_text()
    group = typer.main.get_group(app)
    names = set(group.commands)
    for sub in group.commands.values():
        if hasattr(sub, "commands"):
            names |= {f"{sub.name} {c}" for c in sub.commands}
    missing = {n for n in names if n not in text and n.split()[0] not in text}
    assert not missing, f"undocumented commands: {missing}"
    for sub in ("auth login", "auth status", "auth logout"):
        assert sub.split()[1] in text


def test_spec_names_every_mcp_tool():
    spec = (ROOT / "docs/SPEC.md").read_text()
    for tool in ("list_sources", "list_repos", "list_pull_requests"):
        assert tool in spec
