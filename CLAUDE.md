# pyrio

Python library for working with **Project Rio** (the online layer over Mario Superstar Baseball) — its web API, its stat files, and the domain math built on top (ratings, derived stats, fielding geometry).

This file is the working agreement for contributors and for Claude. It documents what the library currently is, what it's aiming to become, and the conventions we'd like new code to follow. When current code disagrees with a target convention, the target wins for new work — but don't churn unrelated files just to align them. Refactor opportunistically, in a focused commit.

---

## Audience and scope

**Who uses this:** a small community of Rio developers writing tools, bots, dashboards, and ad-hoc analyses against Project Rio data. Not a general public package (yet).

**What belongs in this library:**
- Anything that wraps a *stable external contract* — the Project Rio web API, the stat file JSON schema, character/stadium IDs.
- Domain primitives that any consumer would re-derive otherwise — derived batting/pitching stats, Glicko-2 ratings, character lookups, team-name resolution.
- Geometry and constants tied to the game itself (fielder starting positions, stadium layouts, lockout values).

**What does NOT belong here — keep it in user code:**
- One-off analysis scripts, notebook glue, plotting choices for a specific report.
- Personal API keys, tournament-specific tag lists, hard-coded usernames.
- Bot/UI logic (Discord handlers, web frontends, CLI wrappers).
- Schema-on-read assumptions for *one* downstream use case. If only your project needs that column, compute it in your project.

When in doubt: would a *second, unrelated* Rio tool benefit from this code? If yes, library. If no, user code.

---

## Domain glossary

Terms you'll see throughout the codebase. Use these spellings.

- **Project Rio** — the online service / mod layer for Mario Superstar Baseball. The web API lives at `api.projectrio.app`.
- **MSSB** — Mario Superstar Baseball, the underlying GameCube game.
- **Stat file** — JSON file produced by a Rio client at the end of a game. Parsed by `stat_file_parser.py`.
- **Character** — one of the playable Mario-universe characters. Identified by an integer `char_id` and a canonical name (see `CharNames.csv` / `lookup.py`).
- **Captain** — a character who can lead a team. Subset of all characters; see `CAPTAINS` in `lookup.py`.
- **Roster spot** — index 0–8 of a player on a team's 9-character roster.
- **Team num** — `0` or `1`. **Pre-1.9.2:** 0 = home, 1 = away. **1.9.2+:** 0 = away, 1 = home. This flip is a known footgun — always note which era a caller is in.
- **Tag** — a label attached to games (e.g. tournament name, ranked mode). Used for filtering API queries.
- **Game mode / community** — Rio groupings of games; resolved via `CompleterCache` in `web_caching.py`.
- **Star chance / star swing / star pitch** — special-move mechanics in MSSB; surfaced by the API as event attributes.
- **HUD** — per-character heads-up display data inside a stat file (handedness, name, etc.); see `HudObj`.
- **Event** — a single in-game pitch/contact/result row. Events are the atomic unit of stat-file analysis.
- **Glicko-2** — the rating system used for player skill estimates. Implementation in `glicko2.py`, win-probability helper in `glicko_calculator.py`.
- **Coded value** — a Project Rio id paired with its canonical name (char, stadium, pitch type, hand, …). Modelled as a `RioValue` subclass (`Character`, `Stadium`, …) in `rio_value.py`; build one with `Cls.from_raw(id_or_name)`. The raw id→name tables live in `rio_value.Tables`; `lookup()` does bidirectional dict translation.
- **Captain** — a character who can lead a team. Sourced from the `Captain Character` column of the character-attribute table (`Character.attributes.is_captain` / `is_captain(name)`), not a standalone list.
- **Character attribute** — a per-character stat/ability/flag from `constants/character_attributes.csv`. Each is described by an `AttributeSpec` in the `ATTRIBUTES` registry (`constants/character_data.py`), which drives CSV parsing, the superstar conversion, and categorical decoding. `CharacterAttributes` is the typed star-OFF record; `.with_superstar()` gives star-ON.

---

## Module map

Current layout (flat, at repo root) and the role each module is *meant* to play. If you find yourself adding something that doesn't fit any of these, that's a signal — either it belongs in a new module or it belongs in user code.

| Module | Role |
|---|---|
| `api.py` | Endpoint constants and `ParameterList` dataclasses. **No I/O.** Pure description of what the API accepts. |
| `rio_web.py` | `RioWeb` client — HTTP, auth, response shaping into DataFrames. The only module that talks to the network. |
| `web_caching.py` | `CompleterCache` — local disk cache for slow lookups (game modes, usernames). |
| `stat_file/` | Stat-file parsing package: `stat_obj.py` (`StatObj`), `event.py` (`EventObj`), `event_search.py` (`EventSearch`), `hud.py` (`HudObj`), `runner.py` (`RunnerObj`). Read-only views over decoded stat-file JSON. `stat_file_parser.py` is a back-compat shim re-exporting these. |
| `stat_formatters.py` | Pure functions: derived stats (AVG, OPS, ERA, …) and human-readable line formatters. |
| `rio_value.py` | Coded-value layer: `Tables` (ID→name tables), `RioValue` value objects + `from_raw`, and the `lookup()` / `create_translated_columns()` translation helpers. Data + translator; imports nothing from `rio_web`/`stat_file`. |
| `constants/character_data.py` | `AttributeSpec` + the `ATTRIBUTES` registry and the `CharacterAttributes` record loaded from `character_attributes.csv`. Single source of truth for per-character attributes (parsing, superstar, decoding). |
| `live_ball.py` | Live-ball physics after contact — bounces, walls and stadium hazards — cast against the real collision mesh (`constants/collision/`, `constants/parks/`). Ported from RioVisualizer's `physics.py`, which stays the reference; `tools/check_live_ball_parity.py` holds the port to exact agreement. Standard library only. |
| `team_name_algo.py` | Heuristic for naming a team from its captain/roster. |
| `glicko2.py`, `glicko_calculator.py` | Rating math. Self-contained. |
| `exceptions.py` | `RioAPIError` hierarchy and `raise_for_status`. |
| `helpers.py` | **Legacy grab-bag** — currently fielder-geometry calculations. Target: dissolve this. New code should not land here. |
| `draw/` | Stadium plotting helpers. |
| `constants/collision/`, `constants/parks/` | The game's stadium collision meshes (gzipped, ~300KB) and hazard sheets, read by `live_ball`. Copied from RioVisualizer's extraction; `MANIFEST.json` records each mesh's sha256 so a damaged copy is caught. |

**Boundaries we want to hold:**
- `api.py` knows nothing about HTTP. `rio_web.py` owns all network calls.
- `stat_formatters.py` is pure — no I/O, no DataFrames in/out unless trivially so. Inputs are numbers, outputs are numbers or strings.
- The `stat_file/` package parses; it does not compute derived stats. Derivations belong in `stat_formatters.py`.
- `rio_value.py` is data + a translator. It does not import from `rio_web` or `stat_file`. (It reads `constants/character_data.py` only lazily, inside `Character.attributes`, to avoid an import cycle with `constants`.)

**Target direction:** move sources under `src/pyrio/` (the package skeleton already exists) so editable installs and imports are unambiguous. Not a near-term priority, but new files should be written with that move in mind (no top-level-only imports).

---

## Conventions

Guidelines, with the reasoning so you can judge edge cases. Existing code violates some of these; that's fine — fix as you touch.

### Naming
- **snake_case** for functions, methods, variables, and module names. *Why:* PEP 8, matches most of the codebase.
- **PascalCase** for classes (`RioWeb`, `StatObj`, `EventSearch`).
- **UPPER_SNAKE** for module-level constants (`BASE_URL`).
- The `stat_file/` modules still use `camelCase` in places (`teamNum`, `gameID`, `statJson`). This is a known wart inherited from the original `RioStatLib`. *Don't add more camelCase.* When meaningfully refactoring a method, rename — but don't do a bulk rename PR without a plan, since these names are part of the public surface today.
- Use the domain glossary spellings: `char_id`, `team_num`, `roster_spot`, `game_id`, `stat_file`.

### Types and signatures
- Public functions get type hints. *Why:* this is a library; downstream IDEs depend on them.
- Prefer concrete types over `Any`. `Optional[List[int]]` over `list`.
- Dataclasses (`@dataclass`) for parameter bags and simple records. `ParameterList` subclasses are the established pattern — follow it for new endpoints.

### Errors
- Network/API failures: raise from the `RioAPIError` hierarchy in `exceptions.py`. Add a subclass if a new status class deserves one.
- Argument validation: raise a plain `ValueError` or `TypeError` (not `Exception`, and not a `RioError`). `RioError` subclasses are for bad *data* (unknown ids, malformed stat files, bad API responses), which callers catch; a bad argument is a bug they fix.
- Do not `print()` warnings from library code except at client construction (where it's a usability signal, like the missing-API-key warning). Use `warnings.warn` if a real warning is needed.

### I/O and side effects
- Library functions should not read environment variables or files except at clearly marked entry points (`RioWeb.__init__`, cache constructors). *Why:* makes the library testable and predictable inside other tools.
- No implicit network calls from `__init__` or import time.

### Public surface
- The top-level `__init__.py` is the public API. If it's not re-exported there, treat it as internal.
- Adding something to `__init__.py` is a commitment. Prefer to let things bake in a module first.

### Comments and docstrings
- Docstrings on public classes and any non-obvious function. One short sentence is usually enough; explain *why* when behavior is surprising (the team-num era flip is the canonical example).
- Don't comment what the code obviously does. Don't leave commented-out code — delete it; git remembers.

---

## Testing, releases, contribution

**Current state (1.0 rebuild, step 1 of `docs/v1.0.0-audit.md` section 9):** `pyproject.toml` with hatchling, Python ≥ 3.11 and the `web`/`pandas`/`plot` extras. Set up with `pip install -e . --group dev`, then run `ruff check .`, `ruff format --check .`, `pyright` (strict on `src/`), `lint-imports` (the section 7 layering) and `pytest`. CI (`.github/workflows/ci.yml`) runs all of these on 3.11–3.14, tests the built wheel in a clean venv, and runs the canonical-parity test against a ProjectRio checkout. The pre-1.0 files are excluded from ruff and pyright by an explicit list in `pyproject.toml`; a file leaves the list when a rebuild step rewrites it, and nothing is ever added to it.

**Target state — adopt as we go, not all at once:**

1. **Tests.** `pytest` under `tests/`, mirroring the module layout. Start with the pure modules (`stat_formatters`, `lookup`, `glicko2`, `team_name_algo`) where unit tests are cheap and high-value. `rio_web` tests should mock `requests`, not hit the network.
2. **Packaging.** Move sources under `src/pyrio/`, switch `setup.py` to `pyproject.toml`. Until then, don't write code that assumes the flat layout is permanent.
3. **Versioning.** Semantic versioning. The library has external users (Rio community tools), so a breaking change to a public symbol is a minor bump pre-1.0 and a major bump post-1.0. Note breaking changes in commit messages.
4. **Branches and PRs.** Work on feature branches, PR into `main`. Keep PRs focused — refactors, new features, and bug fixes in separate PRs when reasonable.
5. **Commits.** Imperative subject lines, present tense ("Add X", "Fix Y"). Match the existing log style.

When you do any of the above for the first time, update this section to reflect what's actually in place.

---

## Working with Claude on this repo

- Default to *guidelines + rationale* over hard rules. If a convention here gets in the way, say so and we'll revise it rather than working around it silently.
- For non-trivial changes, propose the approach before writing code — especially if it crosses module boundaries or touches the public surface.
- When asked to "clean up" something, scope it tightly. Don't rename a public symbol or move a file as a side effect of an unrelated change.
- If you spot library-vs-user-code scope creep (a function that only makes sense for one downstream project), flag it.
