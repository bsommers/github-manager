# Changelog

## Unreleased (2026-11-08)

### Added
- Scaffold, tiered tests, `scripts/verify.sh` gate.
- GitHub provider: repos and open PRs across tracked users/orgs.
- Surfaces: CLI (`sources`, `repos`, `prs`, `tui`, `mcp`, `auth`), Textual TUI, FastMCP server.
- Credential chain env > keychain > gh/glab; `gmac auth status|login|logout`.
- Docs: `docs/SPEC.md`, `docs/ARCHITECTURE.md`, ADR 0001; docs-sync test.

### Not yet
- GitLab provider, native OAuth, cache, PR review status (see SPEC §7, §11).

Verification: `scripts/verify.sh --tier smoke,unit,integration,system` -> PASS.
