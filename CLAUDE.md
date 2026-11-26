# pyrio

Python library for working with **Project Rio** (the online layer over Mario Superstar Baseball) — its stat files, its web API, and the game data and math built on top (characters, stadium geometry, the hit simulation, ratings, derived stats).

Published as **`projectrio`** on PyPI, imported as **`pyrio`**. This file is the working agreement for contributors and for Claude: what the library is, how it's laid out, and the conventions new code follows. The design reasoning behind the 1.0 layout is in [`docs/v1.0.0-audit.md`](docs/v1.0.0-audit.md); when this file and that plan disagree about what exists, the code and this file win.

---

## Audience and scope

**Who uses this:** a small community of Rio developers writing tools, bots, dashboards, and ad-hoc analyses against Project Rio data.

**What belongs in this library:**
- Anything that wraps a *stable external contract* — the Project Rio web API, the stat file JSON schema, character/stadium IDs.
- Domain primitives that any consumer would re-derive otherwise — derived batting/pitching stats, Glicko-2 ratings, character lookups, team-name resolution.
- Geometry and constants tied to the game itself (fielder starting positions, stadium layouts, lockout values). Domain data is a deliverable: tables like `CAPTAIN_TEAMS` stay public.

**What does NOT belong here — keep it in user code:**
- One-off analysis scripts, notebook glue, plotting choices for a specific report.
- Personal API keys, tournament-specific tag lists, hard-coded usernames.
- Bot/UI logic (Discord handlers, web frontends).
- Schema-on-read assumptions for *one* downstream use case. If only your project needs that column, compute it in your project.

When in doubt: would a *second, unrelated* Rio tool benefit from this code? If yes, library. If no, user code.

---

## Domain glossary

Terms you'll see throughout the codebase. Use these spellings.

- **Project Rio** — the online service / mod layer for Mario Superstar Baseball. The web API lives at `api.projectrio.app`; its server is ProjectRio-web ("Rio web").
- **MSSB** — Mario Superstar Baseball, the underlying GameCube game.
- **Stat file** — JSON file a Rio client writes at the end of a game, *encoded* (ids) or *decoded* (labels). Read by `pyrio.read_game`. Encoded ids are the source of truth: decoded labels have shifted between versions.
- **Client version** — the Rio release that wrote a file, as a comparable `Version`. Every per-version rule lives in `_decode.py` (see [`docs/version-decoding-proposal.md`](docs/version-decoding-proposal.md)); nothing else branches on version.
- **Side** — `Side.AWAY` or `Side.HOME`. Stat files say this with a team number whose meaning flipped at 1.9.2 (0 = home before, 0 = away since); the decoder applies the flip once, so no public API takes a team number.
- **Character** — one of the playable characters, a `Character` enum member with the game's id and label. Colour variants share a `CharacterFamily`.
- **Captain** — a character who can lead a team: `Character.is_captain`, from the `Captain Character` column of `_data/character_attributes.csv`.
- **Character attributes** — per-character stats, abilities and flags, as a `CharacterAttributes` record (`Character.attributes`, star-off; `.with_superstar()` for star-on).
- **Coded value** — any id the game writes with a label (stadium, pitch type, result, position, …). Each is a `CodeEnum` subclass in `_codes.py` or `_characters.py`, with `.id` and `.label`; `Cls(id)` or `Cls(label)` builds one, and `parse()` (characters, families, stadiums) takes what people type.
- **Roster spot** — index 0–8 of a team's nine-character roster: `RosterSpot`, which carries the spot's character, flags and stat lines.
- **Event** — one pitch (or dead ball) and what came of it. Events are the atomic unit of stat-file analysis.
- **Stat line** — `BattingLine` / `PitchingLine`: counts that add with `+` and `sum()`, derived stats as properties.
- **Tag / tag set / community** — Rio web's labels and groupings of games, used to filter API queries.
- **Star chance / star swing / star pitch** — special-move mechanics in MSSB.
- **HUD** — the live file a client writes during a game; read by `pyrio.read_hud` into a `HUDSnapshot`.
- **Glicko-2** — the rating system for player skill; `pyrio.ratings`.

---

## Module map

Sources live under `src/pyrio/`. **`import pyrio` is the core**; each separate job is a **public submodule** imported by name; **every other module is private** (leading underscore) and reached only through a public namespace.

| Module | Role |
|---|---|
| `__init__.py` | The core's public API: an explicit `__all__`, re-exports only, no logic. |
| `__main__.py` | The `pyrio` command (`pyrio decode FILE`), argparse. |
| `_errors.py` | `RioError`, `UnknownCodeError`, `UnknownNameError`, `StatFileError`. |
| `_float32.py` | `f32`: single-precision rounding for the ports of the game's float math (characters, hit, live ball, running). |
| `_enum.py` | `CodeEnum`: id/label enums, lookup by either, ordering. |
| `_codes.py` | The game's coded values (`Stadium`, `PitchType`, `AtBatResult`, `Position`, …), plus `Side`, `Bases`, `InputDirection`. |
| `_characters.py` | `Character`, `CharacterFamily`, `CharacterAttributes` and its enums, read from `_data/character_attributes.csv`. |
| `_names.py` | The resolver behind `parse()`: normalisation, nicknames (`_data/nicknames.toml`), suggestions. |
| `_stats.py` | `BattingLine`, `PitchingLine`, `format_batting_line`, `format_pitching_line`. |
| `_team_names.py` | `team_name(roster, captain)`, `CAPTAIN_TEAMS`. |
| `_game.py` | The model: `Game`, `Team`, `RosterSpot`, `Event`, `GameState`, `Pitch`, `Contact`, `Fielding`, `Runner`, `GameResult`, `HUDSnapshot`, `Version`. Frozen dataclasses, no parsing. |
| `_decode.py` | `read_game`, `read_hud`: the version-aware decoder. The only place that knows the stat-file format or any per-version rule. |
| `_serialize.py` | `to_jsonable`. |
| `geometry/` | Stadium geometry from the game's data (`geometry/_data/`): walls, boundary, collision triangles, hazards, physics; and what's the same at every park: the bases, fielder starts, lockouts and `fielder_reach`. Every per-stadium function takes a `Stadium`. |
| `sim/` | `simulate_hit` and friends, `HitInputs.from_event`, `simulate_contacts`, `play_out` (the live ball), highlights, and `simulate_run` (baserunning). The hit and live ball are ported from RioVisualizer and held to it by `tools/check_live_ball_parity.py`, the running from the frontend's running model by `tools/check_running_parity.py`; `tests/sim/test_goldens.py` and `test_running.py` hold them to recorded results. |
| `web/` | `RioClient`, `AsyncRioClient`, `DiskCache`, response models, `APIError` hierarchy. The only code that touches the network, and the only importer of httpx. Provisional until Rio web 2.0 settles. |
| `ratings.py` | `Rating`, `update`, `win_probability` (Glicko-2, Rio web's parameters). |
| `svg.py` | Stadium drawings and spray charts as SVG strings. Standard library only. |
| `plot.py` | The same drawings on matplotlib axes (`plot` extra). |
| `pandas.py` | `frame(items)`: a DataFrame from any one model type (`pandas` extra). |

Outside the package: `tests/` (mirrors the public namespaces, shares `tests/fixtures/`), `examples/` (run by `tests/test_examples.py`), `tools/` (developer scripts, never shipped), `docs/`.

**Boundaries, enforced by import-linter (`lint-imports`, contracts in `pyproject.toml`):**
- Core layers import one way: `_errors`/`_float32` ← `_enum` ← `_codes`/`_characters`/`_names` ← `_stats`/`_team_names` ← `_game` ← `_decode`/`_serialize`.
- The core imports no public submodule. `geometry` sits on the core, `sim` and `svg` on `geometry`, and `web`, `plot`, `pandas` and `ratings` on top.
- The core, `geometry`, `sim`, `svg` and `ratings` need only the standard library.
- Only `pyrio.web` imports httpx, only `pyrio.pandas` imports pandas, only `pyrio.plot` imports matplotlib. Nothing imports `pyrio.web`.
- `Stadium` knows nothing about meshes: geometry functions take a `Stadium`, not the other way round.

Data sits beside the code that reads it in a `_data/` folder (not `data/`, which `.gitignore` ignores), loaded lazily through `importlib.resources` behind `functools.cache`. Importing pyrio opens no data file.

---

## Conventions

Guidelines, with the reasoning so you can judge edge cases.

### Naming
- **snake_case** for functions, methods, variables and modules; **PascalCase** for classes; **UPPER_SNAKE** for module-level constants. Ruff's `N` rules enforce it.
- One word per concept, and the glossary's spelling: `game_id`, `roster_spot`, `side`, `stadium`. `kind`, not `type`, for a field that classifies (ruff's `A` rules catch shadowed builtins).
- Booleans read as predicates: `is_captain`, `is_hit`, `has_wall_splat`.

### Types and signatures
- Public functions get full type hints; pyright runs strict on `src/`. *Why:* this is a library, and downstream IDEs depend on them.
- Records are frozen, slotted dataclasses (`@dataclass(frozen=True, slots=True, kw_only=True)`). Coded values are enums, never bare ints or strings.
- Optional or rarely-used parameters are keyword-only.

### Errors
- Bad *data* — an unknown id or name, a malformed stat file, a bad API response — raises a `pyrio.RioError` subclass, which callers catch. Put a new one with the code that raises it (core errors in `_errors.py`, HTTP errors in `web/_errors.py`).
- A bad *argument* raises a plain `ValueError` or `TypeError`: it's a bug the caller fixes, not a condition they handle.
- Library code never `print()`s. Use `warnings.warn` if a real warning is needed.

### I/O and side effects
- Library functions don't read environment variables or files except at clearly marked entry points (`RioClient.from_env`, `DiskCache`, `read_game` given a path). *Why:* testable and predictable inside other tools.
- No network calls and no data-file reads at import time.

### Public surface
- A name is public only if it's in a public namespace's `__all__`. `tests/test_public_api.py` pins every namespace's names, so adding or removing one shows up in review. Adding a name is a commitment: prefer to let it bake privately first.
- One public spelling per name: `pyrio.Character`, never `pyrio._characters.Character`.

### Comments and docstrings
- Docstrings on public classes and any non-obvious function. One short sentence is usually enough; explain *why* when behaviour is surprising (the decoder's version rules are the canonical example).
- Don't comment what the code obviously does. Don't leave commented-out code; git remembers.

---

## Testing, releases, contribution

**In place:**
- `pyproject.toml` with hatchling, Python ≥ 3.11, no required dependencies, and the `web` / `pandas` / `plot` / `all` extras.
- Set up with `pip install -e . --group dev`, then run `ruff check .`, `ruff format --check .`, `pyright`, `lint-imports` and `pytest`. Nothing is excluded from ruff or pyright.
- CI (`.github/workflows/ci.yml`) runs all of these on 3.11–3.14, builds the sdist and wheel, `twine check`s them, runs the suite against the installed wheel in a clean venv, and runs the canonical-parity test against a ProjectRio checkout.
- Tests: a fixture matrix of real and synthetic stat files across client versions (`tests/fixtures/stat_files/`), web responses recorded from ProjectRio-web (`tests/fixtures/web/`, mocked with respx; nothing hits the live API), and the simulation's recorded results (`tests/fixtures/sim_goldens.json.gz`, rewritten deliberately with `python tests/sim/test_goldens.py`). Tests that scan files assert they found some.
- Versioning: semantic versioning from 1.0.0. The version lives only in `pyproject.toml`; `pyrio.__version__` reads the installed distribution. Changes go in `CHANGELOG.md` (Keep a Changelog).
- Commits: imperative subject lines, present tense ("Add X", "Fix Y"). Note breaking changes in the message.

**Releasing:** bump `version` in `pyproject.toml`, date the `CHANGELOG.md` entry, merge to `main`, and push a `vX.Y.Z` tag. `.github/workflows/publish.yml` reruns CI, checks the tag matches the version, and publishes to PyPI by trusted publishing (no token). The wheel job also runs `pyright --verifytypes pyrio`, so every public name stays fully typed.

**Still to do (from the plan):** mkdocs-material API docs with a cookbook page.

**Branches and PRs.** Work on feature branches, PR into `main`. Keep PRs focused — refactors, features and fixes separately when reasonable. (The 1.0 rebuild is the exception: it lands as one branch, `v1.0.0-prep`.)

---

## Working with Claude on this repo

- Default to *guidelines + rationale* over hard rules. If a convention here gets in the way, say so and we'll revise it rather than working around it silently.
- For non-trivial changes, propose the approach before writing code — especially if it crosses module boundaries or touches the public surface.
- When asked to "clean up" something, scope it tightly. Don't rename a public symbol or move a file as a side effect of an unrelated change.
- If you spot library-vs-user-code scope creep (a function that only makes sense for one downstream project), flag it.
