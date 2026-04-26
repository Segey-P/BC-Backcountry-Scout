# Claude Context — [Project Name]

> Copy this file into each new project. Fill in the sections marked [like this].

## Project Overview

- **Name:** [Project Name]
- **Status:** Discovery
- **Repo:** github.com/Segey-P/[repo-slug]
- **Purpose:** [One or two sentence description.]
- **Stack:** [e.g. Streamlit + PostgreSQL]
- **Deploy:** Streamlit Community Cloud

## User Profile

- **Role:** Senior IT Consultant (Banking sector), Canadian (Squamish, BC — Pacific Time)
- **Style:** Direct, precise, no softening. Tables and bullet points.
- **Technical level:** Not a developer — use plain language when explaining options.
- **Workflow:** Cloud-first via Claude Code web. Minimize local machine dependency.

## Before Making Changes

1. Read `TODO.md` — current next actions and priorities.
2. Read all files in `specs/` if present.
3. Never commit secrets or credentials.

## AI Agent Rules

1. Push directly to `main` — no feature branches unless the change is large and risky.
2. Prefer editing existing files over creating new ones.
3. No unnecessary dependencies — keep the stack minimal.
4. No comments explaining *what* code does — only *why*, when non-obvious.
5. No premature abstractions. Three similar lines beats a helper function.
6. No half-finished implementations. Either do it or don't.
7. Keep `TODO.md` updated with relevant next actions throughout the session.
8. Update specs in `specs/` at the end of every session and after any major change in requirements or behaviour.

## TODO.md Convention

`TODO.md` at the repo root is the source of truth for what's next.
The Project Hub dashboard reads it automatically. Keep it updated.

Format:

[] Next action
[] Another action

Up to 6 items are shown in the dashboard.

## Key Files

| File | Purpose |
|---|---|
| `TODO.md` | Current next steps (read by Project Hub dashboard) |
| `CLAUDE.md` | AI agent instructions (this file) |
| `AGENTS.md` | Agent-neutral mirror of CLAUDE.md |
| `specs/` | Authoritative spec documents |

