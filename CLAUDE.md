# GMAC

- Gate: `scripts/verify.sh --quick` prints one line (`PASS n/n` or `FAIL ... -> path`); on FAIL read only the named file.
- Surfaces (`cli.py`, `tui.py`, `mcp_server.py`) stay thin; logic goes in `service.py`. Spec: `docs/SPEC.md`.
- Tests are offline (httpx `MockTransport`); never hit the network or real keychain in tests.
- Never print or log tokens.
- NEVER commit or push secrets (tokens, keys, .env). Check the staged diff before every commit; tests use fake values only.
