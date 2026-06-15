# AI tools report

This document records how AI tools were used while building Synapse, across every phase of
development: planning, coding, testing, CI/CD, and documentation.

A note on scope to avoid confusion: Synapse is itself an AI product — its three-agent pipeline
(**Scout** / **Scribe** / **Critic**) calls LLMs via OpenRouter and Exa for web search. That is the
*product*, not a development tool, and is documented in [ARCHITECTURE.md](ARCHITECTURE.md). This
report covers AI used as part of the *engineering process*.

## Tools used

| Tool | Type | Where it shows up in the repo |
| --- | --- | --- |
| **Claude Code** | Agentic coding assistant (plan → edit → run → verify in the terminal) | `CLAUDE.md` → `AGENTS.md` (the operating manual written for AI agents), `.claude/` settings, plan files |
| **GitHub Copilot** | Automated pull-request code review | Review-response commits, e.g. `2b843e7` ("address copilot review …"), `a1128f2` ("address copilot review …") |

`AGENTS.md` is the single source of truth that constrains every AI tool: code style, repository
layout, testing rules, commit conventions, and "ask, don't guess" boundaries (schema/migration
changes, new dependencies, auth, cost). Keeping the rules in one checked-in file means the same
guardrails apply whether a human or an agent is making the change.

## By development phase

### 1. Planning

- **Claude Code** was used to turn issues and user stories (`docs/USER_STORIES.md`, the GitHub
  project board via `scripts/project.sh`) into concrete implementation plans before any code was
  written — listing files to touch and flagging risks such as DB migrations, codegen drift, and
  breaking API changes.
- Decisions with real trade-offs (e.g. orphan-vs-cascade on job deletion, pagination strategy for
  history) were settled explicitly with the developer before implementation, not guessed.
- This phase is human-led: the AI proposes a plan; the developer approves or redirects it.

### 2. Coding

- **Claude Code** implemented features end-to-end across the stack (FastAPI routes, SQLAlchemy
  persistence, React/TanStack Query hooks and pages), editing files directly and re-running the
  linters and type-checkers in the loop.
- All generated code is held to the project's standards from `AGENTS.md`: `ruff` + `mypy --strict`
  on the backend, `prettier` + `eslint` + `tsc` on the frontend. The agent does not hand-format;
  the formatters are authoritative.
- **GitHub Copilot** reviewed pull requests automatically; its comments led to concrete fixes
  (input-validation hardening, an SSRF guard, dead-CSS removal, tighter regexes — see
  `a1128f2`, `2b843e7`).
- Generated code is treated as a draft to be reviewed, not as trusted output. Human review and the
  automated checks are the gate.

### 3. Testing

- New behaviour ships with tests and bug fixes ship with regression tests, per `AGENTS.md`.
  **Claude Code** wrote unit and integration tests alongside the features — `pytest`
  (`asyncio_mode = "auto"`, split into `unit/` / `integration/` / `evals/`) on the backend and
  `vitest` + `@testing-library/react` on the frontend.
- Tests follow the project rule of asserting *behaviour, not implementation*, and mock external
  services (`respx` on the backend, fetch mocks on the frontend) so CI never touches real APIs.
- The test suite is also how AI mistakes get caught: more than once, agent-generated code looked
  correct but failed under `mypy` or `pytest`, which is exactly why the checks run before anything
  is considered done.

### 4. CI/CD

- The GitHub Actions pipeline (`.github/workflows/ci.yml`) — lint, format-check, tests with
  coverage, `api:check` for codegen drift, and Docker builds — is deterministic and **not** AI:
  it is the objective gate that every AI-assisted change must pass.
- **Claude Code** was used to author and maintain the workflow files themselves, and to diagnose
  CI failures (for example a `format:check` failure on a generated hook, and a codegen-drift
  failure caused by a `@hey-api/openapi-ts` version mismatch against the lockfile).
- **GitHub Copilot's** PR review runs as part of the merge process, giving a second automated pass
  before human approval.
- A separate, manually-triggered LLM-as-judge eval workflow (`.github/workflows/evals.yml`) exists
  for the *product's* agents; it is gated behind `workflow_dispatch` because it is slow,
  non-deterministic, and costs API credits.

### 5. Documentation

- **Claude Code** produced the architecture diagrams in [ARCHITECTURE.md](ARCHITECTURE.md) (four
  Mermaid diagrams: component architecture, agent pipeline, data flow, and the database ERD), the
  `README.md` Architecture section, and this report.
- Documentation is written to the same "senior-engineer comment" bar set in `AGENTS.md`: explain
  *why*, document invariants, link to issues/RFCs — no restating the code, no diary comments.

## Working practices and limitations

What worked:

- **Rules as code.** Putting the standards in `AGENTS.md` made AI output consistent and reviewable.
- **Verify before "done".** Running `ruff`/`mypy`/`pytest` and `lint`/`typecheck`/`test` after every
  change caught plausible-looking but wrong code early.
- **Human in the loop on irreversible decisions.** Schema/migration changes, new dependencies, and
  anything affecting auth or cost were confirmed with the developer, not decided by the agent.

Limitations observed:

- An agent is only as correct as its assumptions about the current state of the code. A change can
  be written perfectly against a stale or wrong base and only surface as a type error later — so the
  base, not just the diff, has to be verified.
- AI suggestions still require human and automated review; they are an accelerator, not a
  replacement for the test suite, the type-checker, or code review.
