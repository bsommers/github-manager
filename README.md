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

```bash
scripts/install.sh                 # from a clone: puts `gmac` on your PATH (editable)
scripts/install.sh --install-uv    # same, installing uv first if you don't have it
scripts/install.sh --git           # from GitHub, no clone (--git v0.1.0 for a tag)
scripts/install.sh --dry-run       # show what would happen; --uninstall removes it
```

It wraps `uv tool install` (uv supplies Python and all dependencies), never touches credentials, and prints
your login status at the end. Re-run it after pulling to pick up new dependencies. Manual equivalent:
`uv tool install --editable --force .`

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
