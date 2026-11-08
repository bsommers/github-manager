# ADR 0001: Textual for the TUI, Typer CLI, FastMCP, httpx

Status: accepted 2026-11-08.

**Textual over Rich-only.** Rich renders; it cannot do focus, tabs, key bindings or async workers.
The TUI needs tabs, row selection and background refresh, which Textual (built on Rich) provides.
Rich stays for CLI tables. **Alternative rejected:** Rich Live, because interactivity would be hand-built.

**Direct REST via httpx over shelling out to `gh`/`glab`.** Typed, testable with `MockTransport`,
one code path for tokens from any source. `gh`/`glab` are used only for credentials and login.
**Alternative rejected:** wrapping `gh api`, which makes tests need the CLI and a live session.

**FastMCP** as requested; tools return pydantic models directly. **Typer** for typed commands
and completion. **uv** + hatchling for a reproducible env.
