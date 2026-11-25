# Changelog

All notable changes to pyrio are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and pyrio uses
[semantic versioning](https://semver.org/) from 1.0.0 on.

## [1.0.0] - Unreleased

A rebuild, planned in [`docs/v1.0.0-audit.md`](docs/v1.0.0-audit.md). Nothing from
0.1.0 is kept for compatibility: every module was rewritten or deleted. The table at
the end maps the old names to the new.

### Added

- **Typed game model.** `pyrio.read_game()` reads any stat file from Rio 0.1.7 on,
  encoded or decoded, into frozen dataclasses: `Game`, `Team`, `RosterSpot`, `Event`,
  `GameState`, `Pitch`, `Contact`, `Fielding`, `Runner`, `GameResult`. `read_hud()` reads
  live HUD files into a `HUDSnapshot`. Every per-version rule lives in the decoder: the
  1.9.2 home/away flip (as `Side`, never a team number), the 1.9.2–1.9.4 crossed
  captain flags, hex and decimal game ids, the pre-2.3.0 swapped result labels and
  contact results, renamed keys and comma-grouped numbers. Pre-0.1.9 files read
  too: a bobbling fielder's uninitialised position is `None`, a pitch with no
  recorded swing is `SwingType.NONE`, 0.1.7's raw star-pitch byte is read as a
  flag, and the trailing commas in 0.1.7–0.1.8 crash files are repaired.
- **Enums for every coded value** (`Character`, `Stadium`, `PitchType`, `AtBatResult`,
  `Position` and about twenty more), each with the game's id and label, checked
  against ProjectRio's own tables by a parity test. `Character.parse()`,
  `CharacterFamily.parse()` and `Stadium.parse()` accept what people type and suggest
  near misses. `CharacterFamily` groups colour variants.
- **`BattingLine` and `PitchingLine`**: counts that add with `+` and `sum()`, derived
  stats as properties (`avg`, `obp`, `slg`, `ops`, `era`, `whip`, ...), and
  `format_batting_line` / `format_pitching_line`.
- **Live HUD files read as the game sees them.** On the file Rio writes when a play
  ends, `HUDSnapshot.play` is that play as a full `Event` (pitch, contact, fielding,
  runners with where they ended, result, RBI and runs), the same `Event` the stat file
  records for it. `Team.score`, the stat lines and the inning runs count that play;
  `state` stays the situation before it. `HUDSnapshot.is_game_over` says when the play
  ended the game (walk-off, a decided last half, the mercy rule), which nothing else
  can, since Rio writes no file after the last play. Also `is_play_over`, the players'
  controller ports (`away_port`, `home_port`, `port(side)`) and `fielder(position)`.
- **`AtBat.star_chance_winner`**: the side that won a star chance, by the game's own rule
  (a strikeout or a ball in play that made an out goes to the fielders), and
  **`RosterSpot.star_swing_cost`** (2 stars for a character who could captain but isn't).
- **Fuller live games.** `LiveGame` adds the runners' roster spots, the batter's hand, the
  batter's and pitcher's lines so far, chemistry links and `batter` / `pitcher`;
  `LiveTeam` adds the captain, superstars, fielding positions (`fielder(position)`) and
  the team logo.
- **`Game.inning_runs(side)`**: a line score, `None` for a half never batted.
- **`AtBat`, `Game.at_bats` and `HalfInning.at_bats`**: events grouped by plate
  appearance, every event in exactly one. An at-bat ends on a result, or with none when
  the next event has a new batter or half inning (a third out made on the bases), so
  unfinished at-bats are kept with `is_complete` False. `AtBat` gives the `final`
  event, `result`, `state` at the start, `pitches`, `runs`, `rbi` and
  `is_star_chance` (the game sets it as the at-bat begins and holds it to the end).
- **Event predicates** for searches: `Event.is_star_pitch`, `is_star_swing`,
  `is_moonshot`, `has_bobble` and `has_wall_jump`, each `False` where the event has no
  pitch, contact or fielder.
- **Run values**: `pyrio.run_expectancy(games)` builds the RE24 table
  (`RunExpectancy`), and `pyrio.linear_weights(games)` gives each `AtBatResult`'s
  average run value (`LinearWeights`). `LinearWeights.woba()`, `wraa()` and `wrc()`
  score at-bats or a `BattingLine`. Only half innings that ran to three outs count, and
  bottom halves where a walk-off was possible are left out. wOBA is unscaled, over Rio's
  box-score plate appearances. This replaces the two versions in MSB League Tools, which
  differed from each other and from this. The comparison is in the commit message.
- `GameState.away_stars` / `home_stars` are `None` where a client wrote 255 for the
  whole game (seen 2.0.1–2.1.1, games with no tag set): the count wasn't recorded.
- **`pyrio.team_name(roster, captain)`** and the `CAPTAIN_TEAMS` table.
- **`pyrio decode FILE`** (also `python -m pyrio`), printing a box score, the events
  (`--events`) or the whole model as JSON (`--json`); `pyrio.to_jsonable()` underneath.
- **`pyrio.web`**: `RioClient` and `AsyncRioClient` on httpx, with retries, an opt-in
  `DiskCache`, frozen response models that reuse the core enums and stat lines, and
  `APIError` subclasses (`AuthenticationError`, `NotFoundError`, `APIResponseError`,
  `APIConnectionError`, `APITimeoutError`). Marked provisional until Rio web 2.0's API
  settles.
- **`pyrio.sim`**: `simulate_hit`, `simulate_trajectory` and `simulate_all_zones`,
  typed with the enums; a `HitResult` keeps the `inputs` that made it. `play_out(hit)`
  carries a hit on against its stadium's collision mesh and hazards until the play
  settles (`play_out_flight` for any other flight), ending at a fielder (`stop_at`) or
  in a glove (`caught_at`). `HitInputs.from_event()` rebuilds a recorded contact;
  `simulate_contacts(game)` does a whole game, as `ContactRecord`s holding the event
  and the hit, and `ContactRecord.play_out()` replays one to how the stat file says it
  ended, picking hazard dice that agree with the record. Gecko codes a game was played
  with are `Mod`s, built from its Rio web tags with `TAG_TO_MOD` and passed as
  `simulate_contacts(game, mods=...)`: `REMOVE_SLICE` and `FIX_NON_RED_TOAD_REACH`
  change the hit, and `HAZARDS_OFF` plays the bare park (a stat file can't say a game
  had no hazards; `play_out(hazards=...)` still decides outright). Star swings resolve from
  `stars` and `is_captain`, as in the game. `find_highlights` and `best` for game
  summaries.
- **Per-character batting-box and fielding data** on `CharacterAttributes`, read from
  the game through the decomp by `tools/extract_character_tables.py`: the box ranges,
  bat offset and move speed, the hit-by-pitch box, dive range, `bat_reach` and
  `jogging_speed`.
- **`pyrio.geometry`**: walls, the field boundary, collision triangles, hazards and
  physics per stadium, fielder starting spots and lockout frames.
- **`pyrio.ratings`**: Glicko-2 as a frozen `Rating`, a pure `update()` and
  `win_probability()`, with Rio web's parameters (tau 0.5, starting RD 300).
- **`pyrio.svg`**: stadium drawings and spray charts as SVG strings, with no
  dependencies.
- **`pyrio.plot`**: the same drawings on matplotlib axes (`plot` extra).
- **`pyrio.pandas.frame()`**: a DataFrame from any one model type (`pandas` extra).
- `examples/`: a box score, an SVG spray chart, batting by character with pandas, and a
  game summary graphic, all run by the tests.
- `py.typed`, and type hints on the whole public API.

### Changed

- **The package is `projectrio` on PyPI and `pyrio` on import**, built with hatchling
  from a `src/` layout. Python 3.11 or later.
- **`import pyrio` needs only the standard library.** pandas, numpy, scipy, matplotlib
  and requests were all required; now httpx, pandas and matplotlib are the `web`,
  `pandas` and `plot` extras, and numpy and scipy aren't used.
- **Ratings match the official ladder.** pyrio's Glicko-2 used tau 1.2 and RD 350;
  it now uses Rio web's tau 0.5 and RD 300. pyrio follows Glickman's paper where Rio
  web's volatility step has a slip (`mu**2` for `phi**2`), and keeps a bisection step
  that always converges.
- **Derived stats are unrounded floats, `nan` for a zero denominator.** Rounding is for
  the formatters. `batting_avg(hit=3, at_bats=10)` used to return 0.0 by swallowing the
  misspelt keyword.
- **Errors**: bad data raises a `pyrio.RioError` subclass (`UnknownCodeError`,
  `UnknownNameError`, `StatFileError`, the web `APIError`s); a bad argument raises a
  plain `ValueError` or `TypeError`.

### Fixed

- Game ids from Rio 0.1.9 to 2.2.0 were parsed as hex, so every one was wrong.
- Files from before 1.9.2 reported the wrong team for 0.1.7 and 0.1.7.a, which fell
  through both hard-coded version lists.
- `wasQuit()` was true for every game.
- `pitchesPerPosition()` raised on every file since 1.9.2.
- 1.9.2–1.9.4 files gave each team the other team's captain, and so the wrong team
  name.
- `examples/game_summary.py` silently skipped the stadium outline.
- Building an `EventSearch` from an encoded file raised `KeyError: 2`.
- The hit simulation gave a superstar batter superstar power but not superstar contact
  size (a bug carried over from RioVisualizer's calculator), so it missed the contact
  quality, power and launch of nearly every superstar contact in Superstars-On games.
- The hit simulation always used the pitcher's own cursed ball. As in the game, a tired
  pitcher (stamina below 4) has none unless they threw a non-captain star pitch, and a
  captain star pitch is fully cursed. `HitInputs` gains `pitcher_stamina` and
  `is_star_pitch`, which `HitInputs.from_event` fills from the stat file.
- `HitInputs.from_event` passed on the full charge a stat file records for a pop fly or
  grounder star swing, which the game sets itself, so with five stars it replayed the
  swing as a moonshot attempt. A star swing that isn't a moonshot now held no charge.
- Bowser Castle's Thwomps (carried over from RioVisualizer's physics) slammed on any
  ball that came near and only once a play. As in the game, a Thwomp is now disarmed
  for the play the first frame the ball heads back toward home or aims more than 25
  units wide of it, slams again once back on its perch, and holds still a frame at the
  top of its rise.

### Removed

Everything from 0.1.0. Where it went:

| 0.1.0 | 1.0.0 |
|---|---|
| `StatObj`, `EventObj`, `HudObj`, `RunnerObj`, `load_stat_file`, `iter_stat_files` | `pyrio.read_game`, `pyrio.read_hud`, and the model's fields |
| `EventSearch` | a comprehension over `game.events` |
| `rio_value` (`Tables`, `RioValue`, `lookup`, `create_translated_columns`), `CharNames.csv` | the enums, `Character.parse`, `pyrio.pandas.frame` |
| `constants.character_data` (`AttributeSpec`, `character_attributes`) | `Character.attributes`, `CharacterAttributes` |
| `RioWeb`, `api` (`ParameterList`s, `Endpoint`), `web_caching` | `pyrio.web.RioClient`, `DiskCache` |
| `RioAPIError`, `RioAuthError`, `RioNotFoundError`, `UnknownRioValueError` | `pyrio.web.APIError` and subclasses, `pyrio.UnknownCodeError` |
| `stat_formatters` (`batting_avg`, `era`, `derive_batting`, ...) | `BattingLine` / `PitchingLine` properties, `format_*` |
| `glicko2.Player`, `glicko2_win_probability` | `pyrio.ratings` |
| `team_name_algo` | `pyrio.team_name` |
| `hit_simulation`, `hit_analysis` | `pyrio.sim` |
| `live_ball`, `stadiums`, `helpers` | `pyrio.sim.play_out`, `pyrio.geometry` |
| `draw.draw_stadium` | `pyrio.svg`, `pyrio.plot` |

## [0.1.0]

The first packaged release: stat-file parsing, the web client and the domain helpers
in a flat layout.

[1.0.0]: https://github.com/matt-gree/pyrio/compare/main...v1.0.0-prep
