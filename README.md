# GMAC: Git Manager Admin Console

One registry for the GitHub repos and PRs of many users and orgs, usable by humans and AI agents
through a CLI, a TUI and an MCP server. All three are thin wrappers over one core (`src/gmac/service.py`).

**Status:** scaffold + first vertical slice (repos and open PRs). Specs: [docs/SPEC.md](docs/SPEC.md).

## Layout

| Path | Holds |
|---|---|
| `src/gmac/` | core (`service`, `github`, `config`, `models`) and surfaces (`cli`, `tui`, `mcp_server`) |
| `tests/` | tiered suites: smoke, unit, integration, system, perf, stress, torture |
| `scripts/verify.sh` | one-line gate; reports in `target/verify/` |
| `docs/` | `SPEC.md`, `ARCHITECTURE.md`, `adr/` |
| `input/`, `output/` | ignored data dirs (see their READMEs) |

## Quickstart

```bash
uv sync
uv run gmac auth status                    # reuses gh/glab login, env tokens or keychain
uv run gmac auth login                     # browser login via gh (-p gitlab for glab)
uv run gmac sources add <your-user>        # add --org for organizations
uv run gmac repos                          # or: gmac prs, gmac tui
uv run gmac mcp                            # stdio MCP server
scripts/verify.sh --quick
```

Auth order: env token (`GMAC_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`), OS keychain, then your `gh`/`glab` session. Details: [docs/SPEC.md §5](docs/SPEC.md). GitLab sources are specified but not built yet. Changes: [CHANGELOG.md](CHANGELOG.md). Never commit tokens.

## License

Apache License 2.0, see [LICENSE](LICENSE).
