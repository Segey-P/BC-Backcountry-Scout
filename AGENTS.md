# AGENTS.md

Operational context for autonomous coding agents working in AI_workspace.

Primary goals:
- maximize reasoning quality
- minimize unnecessary complexity
- preserve maintainability
- operate autonomously where safe
- minimize token and dependency overhead

# User Preferences

- Direct, precise communication
- Prefer tables and bullet points
- Avoid hedging and filler
- Default to complete answers over ultra-short replies
- Prefer complete technically useful answers over artificially brief responses. Concise does not mean shallow.

# Environment

| Item | Value |
|---|---|
| OS | macOS Apple Silicon |
| Shell | fish |
| Package Manager | Homebrew |
| Default Language | Python |

# Workflow

- GitHub is the source of truth
- Cloud-first development preferred
- Local machine is fallback only
- Prefer lightweight, maintainable solutions
- Avoid unnecessary dependencies

# Execution Rules

1. Read relevant specs before editing code
2. Prefer autonomous execution over repeated confirmations
3. Parallelize independent work when safe
4. Keep changes scoped and reversible
5. Do not rewrite specs to match implementation
6. Update status sections only unless explicitly instructed
7. Preserve existing architecture unless there is a strong reason to change it

# Spec Rules

# Critical Constraints

- Financial calculations must use high-precision decimals
- Default to Canadian financial/tax assumptions where relevant
- Prefer Streamlit Community Cloud compatible solutions
- Mobile accessibility matters for user-facing dashboards

Additional specialized guidance exists under docs/agents/.
Load only when relevant to the current task.

# Testing Guidance

Focus on:
- edge cases
- financial precision
- integration safety
- reproducible tests
