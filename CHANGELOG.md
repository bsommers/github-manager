# Changelog

## Unreleased (2026-11-08)

### Added
- Scaffold, tiered tests, `scripts/verify.sh` gate.
- GitHub provider: repos and open PRs across tracked users/orgs.
- Surfaces: CLI (`sources`, `repos`, `prs`, `tui`, `mcp`, `auth`), Textual TUI, FastMCP server.
- Credential chain env > keychain > gh/glab; `gmac auth status|login|logout`.
- Docs: `docs/SPEC.md`, `docs/ARCHITECTURE.md`, ADR 0001; docs-sync test.

### Fixed
- `gmac auth login` always exited 1 after a successful login (`typer.Exit` is a `RuntimeError`).
- PR titles, repo names and errors containing `[brackets]` were swallowed as Rich markup (CLI) or could crash/blank (TUI).
- Non-JSON error bodies (e.g. HTML 502) raised `JSONDecodeError` instead of `GitHubError`.
- Corrupt `config.toml` produced a traceback; now a one-line error, file untouched.

### Tests
- Line and branch coverage gate at 100% (`uv run pytest --cov`); tiers smoke, unit, integration, system, perf, stress, torture.

### Not yet
- GitLab provider, native OAuth, cache, PR review status (see SPEC §7, §11).

Verification: `scripts/verify.sh --tier smoke,unit,integration,system` -> PASS.
