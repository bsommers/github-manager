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

## Install

One command puts `gmac` on your PATH (needs [uv](https://docs.astral.sh/uv/), which fetches Python and all dependencies itself):

```bash
uv tool install --editable .      # from a clone; later: uv tool upgrade gmac
# or straight from GitHub, no clone:
uv tool install git+https://github.com/bsommers/github-manager
```

## Quickstart

```bash
gmac auth status                    # reuses gh/glab login, env tokens or keychain
gmac auth login                     # browser login via gh (-p gitlab for glab)
gmac sources add <your-user>        # add --org for organizations
gmac repos                          # or: gmac prs, gmac tui
gmac gui                            # local web UI at http://127.0.0.1:8765 (read-only)
gmac mcp                            # stdio MCP server
scripts/verify.sh --quick
```

Auth order: env token (`GMAC_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`), OS keychain, then your `gh`/`glab` session. Details: [docs/SPEC.md §5](docs/SPEC.md). GitLab sources are specified but not built yet. Changes: [CHANGELOG.md](CHANGELOG.md). Never commit tokens.

## License

Apache License 2.0, see [LICENSE](LICENSE).
