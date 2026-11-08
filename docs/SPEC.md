# GMAC build specification

Source: `idea.md`. Status legend: **[done]** built and tested, **[next]** specified, not built, **[later]** direction only.

## 1. Purpose

One central registry and coordination point for the repos and PRs of many users and orgs, usable
by people and AI agents. Not a new GitHub: it is a thin, read-first layer over GitHub and GitLab
that reuses the user's existing logins and CLIs.

## 2. Scope and non-goals

In scope: list/track repos and PRs/MRs across multiple sources (users, orgs/groups); same
capabilities from CLI, TUI, MCP, later HTTP API and web UI.
Non-goals: replacing `gh`/`glab`; storing passwords; a hosted service; write operations before the
read path is trustworthy (see §9 safety).

## 3. Stack (decided; rationale in `docs/adr/0001-stack.md`)

| Concern | Choice | Version checked 2026-11-08 |
|---|---|---|
| Language / env | Python >=3.12, `uv` | uv 0.12 |
| TUI | **Textual** (Rich is its renderer; Rich also formats CLI tables) | textual 8.2, rich 15 |
| CLI | Typer | 0.28 |
| MCP | FastMCP | 4.1 |
| HTTP | httpx (async) | 0.28 |
| Models / config | pydantic v2, TOML via `tomllib`/`tomli-w`, `platformdirs` | |
| Secrets | `keyring` (OS keychain) | 25.7 |

## 4. Architecture

```
 CLI (typer) ─┐
 TUI (textual)├─> service.py ─> provider clients (github.py, gitlab.py[next]) ─> REST
 MCP (fastmcp)┘        │
 API (later) ──────────┤        auth.py  (env > keychain > gh/glab)
                       └─> config.py (sources) · models.py (Repo, PullRequest, Source)
```

Rules: surfaces contain no business logic; `service.py` is the only thing surfaces call; providers
return the shared models so surfaces never branch on provider; clients accept an injectable
transport so every test runs offline.

## 5. Authentication  **[done except native device flow]**

Goal: easiest possible login, no passwords handled by GMAC.

Resolution order per provider (`auth.find_credential`):
1. Env: `GMAC_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` / `GMAC_GITLAB_TOKEN`, `GITLAB_TOKEN`, `GLAB_TOKEN`
2. OS keychain entry stored by `gmac auth login --token`
3. `gh auth token --hostname H` / `glab auth token --hostname H` (reuses the user's existing OAuth session)

Commands: `gmac auth status` (shows origin, never the token), `gmac auth login [-p github|gitlab]`
(runs `gh auth login` / `glab auth login`, which perform the browser OAuth device flow),
`gmac auth login --token` (hidden prompt, stored in keychain), `gmac auth logout`.

[next] Native OAuth device flow inside GMAC (no gh/glab needed): requires a registered OAuth app
per provider and its public `client_id`; flow = POST device code, show code + URL, poll, store in
keychain. [next] Self-hosted hosts (`--host`), per-source host/token override. Required scopes:
GitHub `repo`, `read:org`; GitLab `read_api`. SAML-protected orgs need the token authorized for the
org or its repos are silently omitted; `gmac doctor` should detect and say so.

## 6. Providers

GitHub **[done]**: repos via `/users/{u}/repos`, `/orgs/{o}/repos`; open PRs via one
`/search/issues?q=is:pr is:open org:|user:` query per source; pagination to a limit.

GitLab **[next]**: `Source.provider="gitlab"` already exists in the model; `gmac sources add -p gitlab`
currently exits 2 with a clear message. Build `gitlab.py` (projects via `/groups/{g}/projects`,
`/users/{u}/projects`; MRs via `/merge_requests?scope=all&state=opened`), mapping into `Repo` and
`PullRequest`. Add a `provider` field to both models and dispatch in `service.py`.
Acceptance: same CLI/TUI/MCP output shape for both providers, tests via MockTransport.

## 7. Functional requirements

| ID | Requirement | Status |
|---|---|---|
| F1 | Register/remove/list sources (user or org) in `config.toml` | done |
| F2 | List repos across all sources, newest push first, archived hidden by default | done |
| F3 | List open PRs across all sources, newest update first | done |
| F4 | `--json` output on list commands for scripting/agents | done |
| F5 | TUI: Repos and PR tabs, refresh `r`, quit `q`, status line with counts | done |
| F6 | MCP tools: `list_sources`, `list_repos`, `list_pull_requests` (stdio; `--http`) | done |
| F7 | PR review status (approved / changes requested / CI state) per PR | next |
| F8 | Local SQLite cache with TTL and ETag conditional requests (rate limits, speed) | next |
| F9 | Filters: language, stale >N days, has-open-PRs, fork, private | next |
| F10 | TUI: Enter opens URL, `/` filter, source switcher, detail pane | next |
| F11 | `gmac doctor`: auth, scopes, SAML, rate limit, config checks | next |
| F12 | Write actions (comment, merge, label) behind explicit confirmation + MCP annotations | later |
| F13 | HTTP API (FastAPI) and web UI sharing `service.py` | later |
| F14 | Agent coordination: claims/locks on PRs or repos so agents don't collide | later |

## 8. Non-functional requirements

- Offline tests only by default; live checks are a manual `system` step.
- Never log or print tokens; `auth status` shows origin only.
- Errors: clean one-line CLI message and exit 1; usage errors exit 2; no tracebacks for expected failures.
- Rate limits: honor `X-RateLimit-*` and `Retry-After` **[next, with F8]**.
- Portable: no absolute paths; config via platformdirs, override with `GMAC_CONFIG`.
- Determinism: list order is a stable sort; JSON output stable per run.

## 9. Safety model for MCP and write actions

Read tools are safe to expose by default. Any write tool (F12) must: be separate from read tools,
carry destructive-hint annotations, require an explicit `confirm=true` argument, and be off unless
`gmac mcp --allow-write` is passed. Tool outputs are data, never instructions: PR titles and bodies
come from third parties and must not be trusted by calling agents.

## 10. Test plan (tiers per `scripts/verify.sh`)

| Tier | Now | To add |
|---|---|---|
| smoke | imports, CLI help lists every command | |
| unit | config round-trip/dedupe, credential order, provider isolation | model validation, filters |
| integration | service via MockTransport, MCP tool list, TUI pilot loads tables | pagination >100, rate-limit/403/SAML responses, GitLab |
| system | CLI subprocess: sources lifecycle, no-source error exit codes | live read-only smoke gated by `GMAC_LIVE=1` |
| perf/stress/torture | 500-repo budget; 100-source fan-out; one failing source; corrupt `config.toml` | malformed API JSON bodies, partial writes, kill -9 during save |

## 11. Milestones

1. **M1 [done]** scaffold, config, auth chain, GitHub repos/PRs, CLI, TUI, MCP, tests green.
2. **M2** GitLab provider; `doctor`; pagination/rate-limit handling and cache (F8, F11).
3. **M3** review/CI status, filters, richer TUI (F7, F9, F10).
4. **M4** write actions with safety model; API and web UI (F12, F13).
5. **M5** agent coordination (F14). Onboard to GSD at the start of M2.

## 12. Open questions

- Register a GMAC OAuth app (GitHub + GitLab) for native device flow, or keep delegating to gh/glab?
- Is the cache per-machine only, or shared across agents (affects F14)?
- Should "tracked" mean all repos of a source, or a curated subset (watchlist)?
