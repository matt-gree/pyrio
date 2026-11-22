# pyrio

```
pip install projectrio
```

The distribution is **`projectrio`**; the import is `pyrio`. (`pip install pyrio`
installs an unrelated library.)

pyrio is Python for [Project Rio](https://www.projectrio.online/), the online layer
over Mario Superstar Baseball. It reads the stat files Rio writes after every game
into typed objects, wraps the Rio web API, and carries the game's own data and math:
characters and their attributes, stadium geometry, the hit simulation, ratings and
derived stats.

`import pyrio` needs nothing outside the standard library. Each heavier job is an
optional extra:

| Extra | Adds | For |
|---|---|---|
| `projectrio[web]` | httpx | `pyrio.web`, the API client |
| `projectrio[pandas]` | pandas | `pyrio.pandas.frame()` |
| `projectrio[plot]` | matplotlib | `pyrio.plot` |
| `projectrio[all]` | all three | |

Python 3.11 or later.

## Stat files

```python
import pyrio

game = pyrio.read_game("20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json")
game.stadium                # <Stadium.BOWSER_CASTLE: 4>
game.result.winner          # <Side.HOME: 'Home'>
game.home.captain.character # <Character.MARIO: 0>
game.home.batting.ops       # 1.138...

for event in game.events:
    if event.is_hit and event.contact:
        print(event.batter.label, event.result.label, event.contact.power)
```

`read_game` takes a path, an open file or an already-parsed dict, and reads any
client from 0.1.7 on, encoded or decoded. Every per-version difference (the 1.9.2
home/away flip, hex and decimal game ids, the pre-2.3.0 result labels, renamed keys)
is handled once, in the decoder, so the objects you get are the same whatever wrote
the file. `read_hud` reads a live HUD file the same way.

From the command line:

```
pyrio decode GAME.json            # box score
pyrio decode GAME.json --events   # and every event
pyrio decode GAME.json --json     # the whole model as JSON
```

## Characters and the game's vocabulary

Every coded value in the game is an enum: `Character`, `Stadium`, `PitchType`,
`AtBatResult`, `Position` and about twenty more, each with the game's own id and label.

```python
from pyrio import Character, CharacterFamily

Character.parse("dry bones gray")       # <Character.DRY_BONES_GY: 48>
Character.parse("koopa r").family        # <CharacterFamily.KOOPA: ...>
bowser = Character.BOWSER.attributes
bowser.slap_hit_power                    # 60
bowser.with_superstar().slap_hit_power   # 100
bowser.captain_star                      # <CaptainStar.KILLER_BALL: ...>
```

`parse` accepts labels, nicknames, spacing and case variations, and suggests the
nearest names when nothing matches.

## Stat lines

`BattingLine` and `PitchingLine` hold the counts, add together with `+` or `sum()`,
and give the derived stats as properties (unrounded; `nan` where the denominator is
zero):

```python
from pyrio import BattingLine, format_batting_line

season = sum((spot.batting for spot in game.home.roster), BattingLine())
season.avg, season.obp, season.slg, season.ops
format_batting_line(game.home.roster[3].batting)   # '3-for-5, HR, 2B, RBI'
```

## The web API

```python
from pyrio.web import RioClient

with RioClient.from_env() as rio:          # reads PYRIO_API_KEY if set
    games = rio.games(tags=["S13 Superstars Off"], limit=50)
    rows = rio.stats(users=["MattGree"], by_character=True)
```

Responses are frozen models that reuse the core enums and stat lines. Errors are
`pyrio.web.APIError` subclasses, which are `pyrio.RioError`s. `AsyncRioClient` has the
same methods for asyncio, and `DiskCache` keeps Rio web's reference data (tags,
communities, users) on disk between runs.

## Simulation and geometry

```python
from pyrio.sim import HitInputs, simulate_contacts, simulate_hit, find_highlights
from pyrio.geometry import wall_at, boundary

contacts = simulate_contacts(game)     # every contact, re-simulated from its RNG
find_highlights(contacts, stadium=game.stadium).deepest_robbery

wall_at(game.stadium, 0.0).height      # the centre-field wall
```

`pyrio.sim` reproduces the game's contact stage exactly from the three RNG values a
stat file records, flies the ball, and (`play_out`) plays it on against each stadium's
collision mesh and hazards. `pyrio.geometry` holds the stadiums: walls, boundary,
collision triangles, hazards, fielder starting spots and lockouts.

## Drawing and DataFrames

```python
import pyrio.svg, pyrio.plot, pyrio.pandas

svg = pyrio.svg.spray_chart(game.events, stadium=game.stadium)   # str, no dependencies
ax = pyrio.plot.spray_chart(game.events, stadium=game.stadium)   # matplotlib Axes
events = pyrio.pandas.frame(game.events)   # one row per event, enums as categoricals
```

`frame()` takes any one model type: events, roster spots, games, web responses or
simulated contacts.

## Ratings

```python
from pyrio.ratings import Rating, update, win_probability

after = update(Rating(), [(Rating(1600), 1.0)])   # beat a 1600 player
win_probability(after, Rating(1500))
```

Glicko-2 with Rio web's parameters (tau 0.5, starting RD 300), following Glickman's
paper.

## Examples

[`examples/`](examples) has four runnable scripts: a box score, an SVG spray chart, a
pandas table of batting by character, and a broadcast-style game summary graphic. The
test suite runs each of them.

## Development

```
pip install -e . --group dev
ruff check . && ruff format --check . && pyright && lint-imports && pytest
```

[`CLAUDE.md`](CLAUDE.md) has the layout and conventions, and
[`CHANGELOG.md`](CHANGELOG.md) what changed.
