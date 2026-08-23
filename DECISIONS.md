# Decisions

Append-only. One entry per choice that could reasonably have gone another way.
Future-you and future-agent will not remember why, and the guide's defaults are
starting points, not conclusions.

Format:

```
## YYYY-MM-DD — <the choice>
**Decided:** what was chosen
**Alternatives:** what else was considered
**Why:** the reasoning
**Revisit if:** the condition that would change this
```

<!-- Agent: append new decisions below. Do not edit existing entries. -->

## 2026-08-23 — Packaging via hatchling under uv
**Decided:** `pyproject.toml` uses hatchling and packages `src/` with zero runtime dependencies; CLI is stdlib argparse only.
**Alternatives:** setuptools; add click/typer for the CLI.
**Why:** Phase 0 forbids unnecessary packages; argparse is enough for stub subcommands; uv + hatchling is a common minimal layout.
**Revisit if:** a later phase needs a richer CLI framework and the user approves the package.

## 2026-08-23 — Stub phase numbers on subcommands
**Decided:** not-implemented messages map update→1, clean→3, train→5, project→8, evaluate→9, audit→3.
**Alternatives:** a single generic "not implemented" with no phase number.
**Why:** `build/00-setup.md` asks for `not implemented — phase N builds this`; numbers align with when AGENTS.md introduces real behavior for those commands.
**Revisit if:** a later phase owns a different subcommand than this map assumes.
