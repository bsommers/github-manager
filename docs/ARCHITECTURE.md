# Architecture

See the diagram and rules in [SPEC.md §4](SPEC.md). Module map:

| Module | Role |
|---|---|
| `models.py` | `Source`, `Repo`, `PullRequest` (pydantic) shared by every surface |
| `config.py` | `config.toml` load/save (`GMAC_CONFIG` overrides path) |
| `auth.py` | credential chain env > keychain > gh/glab; login helpers |
| `github.py` | async GitHub REST client, injectable transport |
| `service.py` | fan-out across sources, merge, sort; the only API surfaces call |
| `cli.py` `tui.py` `mcp_server.py` | thin surfaces |
| `cli_main.py` | `python -m gmac.cli_main` entry used by system tests |
