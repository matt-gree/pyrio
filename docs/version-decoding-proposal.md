# Proposal: one version-aware decode layer

**Status:** draft, for discussion
**Date:** 2026-11-19
**Companion to:** [`schema-sync-proposal.md`](schema-sync-proposal.md)

## Problem

`schema-sync-proposal.md` addresses a **spatial** problem: one format, re-encoded
by hand in several repos. This is the **temporal** one: one repo reading files
written by a dozen different versions of the format.

Rio has shipped roughly thirteen releases that write stat files, and 2.3.0 adds
the largest batch of format corrections so far. pyrio's knowledge of what
changed when is currently spread across six mechanisms that don't know about
each other:

| Mechanism | Location | Shape |
|---|---|---|
| `VERSION_LIST_HOME_AWAY_FLIPPED` | `stat_file/stat_obj.py:63` | exact-string list of 5 versions |
| `VERSION_LIST_OLD_TEAM_STRUCTURE` | `stat_file/stat_obj.py:141` | exact-string list of 8 versions |
| `versionBefore(maj, min, patch)` | added in the 2.3 work | regex + tuple comparison |
| `versionBefore2_3()` | added in the 2.3 work | hard-coded call to the above |
| ad-hoc gates | `result_of_AB`, `contact_result_primary`, `contact_result_secondary`, `charge_type`, `five_star_swing`, `_inputs_from_event` | inline `if` per field |
| key fallbacks | `battersPerPosition`, `earnedRuns`, `wasQuit` | `if key in stats` per accessor |

Three concrete costs:

1. **The lists don't mean what their comments say.** The comment above
   `VERSION_LIST_HOME_AWAY_FLIPPED` says "pre 1.9.2", but the list is five exact
   strings ending at `1.9.1`. A file written by `1.8.0` or `1.9.0` gets **no
   flip**, silently reporting the wrong team. The regex helper added for 2.3
   would express this correctly and isn't used for it.
2. **Adding a version means editing code in six places.** 2.3 required new
   branches in five accessors. 2.4 will require more, in different ones.
3. **Nothing enumerates what pyrio believes about any given version.** There is
   no way to ask "how will you read a 1.9.4 file?" or to test that answer.

## Three kinds of version-dependence

These need different machinery, and conflating them is why the current code is
scattered. Every case I know of is one of:

**(a) Key naming** — the value is present and correct, under a different key.
*Examples:* `"Team 0 Roster 0"` → `"Away Roster 0"` (changed in the 1.9.x line);
`"Pitches Per Position"` → `"Batters Per Position"`; `"Earned Runs"` absent
before some version.
*Resolution:* read the first key that exists, newest name first.

**(b) Value correction** — right key, wrong value, recoverable.
*Examples:* at-bat results 5 and 6 swapped before 2.3.0; `"Error - Input"` →
`"Error"`; a force out logged as `"Out-tag"` and a tag out as `"Foul"`; a foul
that landed first logged as fair; `"Unable to Decode. Invalid Value (1)."` for a
charged captain star.
*Resolution:* a correction applied on read, gated on a version range.

**(c) Capability gate** — the file cannot answer the question at all.
*Examples:* a bunt before 1.9.6 (swing `0` doesn't distinguish a bunt from an
ordinary swing); `"Fair"` vs `"Fielded"` before 2.3.0 (the original value was
overwritten and is not in the file); an unresolved play whose secondary result
was written as a bare `255`.
*Resolution:* raise or return a documented "unknown", never guess.

The current code implements all three with the same tool — an inline `if` — which
is why (c) sometimes silently behaves like (b).

## Proposal

### 1. `FileVersion`, a comparable value object

Replace the string lists and the ad-hoc regex with one type, in the idiom
`rio_value.py` already uses:

```python
v = FileVersion.from_raw(stat_json.get("Version"))   # missing → PRE_0_1_7
v < FileVersion(2, 3, 0)      # real comparison, not string matching
v in VersionRange(None, "1.9.2")
```

It owns the parsing quirks in one place: the `"Pre 0.1.7"` prefix, the `"0.1.7a"`
suffix, a missing key, and — currently a latent `TypeError` — an explicit
`"Version": null`. An unparseable version must resolve to a **documented**
policy; today it silently returns "before everything", which applies every
correction to a file we know nothing about. I'd argue it should be a distinct
`UNKNOWN` that gates capabilities rather than triggering corrections.

### 2. Corrections as data, not control flow

One table, one entry per known change, each tagged with its kind from above:

```python
CORRECTIONS = (
    KeyRename(field="roster_key",  until="1.9.5",
              old="Team {team} Roster {slot}", new="{side} Roster {slot}"),
    KeyRename(field="Batters Per Position", until=...,  old="Pitches Per Position"),
    ValueSwap(field="Result of AB", until="2.3.0",
              pairs=(("Caught", "Caught line-drive"),),
              because="ids 5 and 6 were labelled the wrong way round"),
    ValueRename(field="Result of AB", always=True,
                mapping={"Error - Input": "Error",
                         "Error - Chem": "Fielders Choice"}),
    Capability(field="bunt_simulation", requires="1.9.6",
               because="swing 0 did not uniquely mean a bunt"),
)
```

Two properties worth keeping:

- **`always=True` vs a version bound is a real distinction, not laziness.** A
  pure rename (`"Error - Input"`) needs no gate, because that string can only
  have come from an old file. A *swap* (`"Caught"`) must be gated, because the
  same string is valid in both eras and means something different in each. The
  2.3 work already got this right; the table should make it explicit rather than
  leaving it to be re-derived.
- **Every entry carries its `because`.** The force/tag off-by-one is
  incomprehensible without knowing that Rio wrote `secondary = out_type`.

### 3. One application point

Corrections apply where raw JSON becomes a value, not inside each accessor.
This matters specifically on `v1.0.0-prep`: `RioValue.__eq__` is value-to-value
only, so `result_of_AB() == "Strikeout"` is **always `False`** once accessors
return value objects. Any correction written as a string comparison inside an
accessor is already broken there. Correcting the raw string *before*
`FinalResult.from_raw()` sidesteps that entirely.

### 4. Make it introspectable and testable

```python
StatObj(f).decode_report()
# → version 1.9.4; corrections applied: roster_key, result_of_AB swap;
#   capabilities unavailable: bunt_simulation
```

That turns "how do we read a 1.9.4 file?" into a function call, and lets the test
suite assert the matrix of (version × correction) directly instead of hand-built
fixtures per case. It also gives downstream tools — PRSH, RioVisualizer, the
website — a way to say *why* a number looks odd.

### 5. Feed it from the schema artifact

`schema-sync-proposal.md` proposes Rio emit `schema/stat_file_schema.json`. If
that artifact is emitted **per release**, this correction table is largely
derivable rather than hand-maintained: diffing consecutive schema versions
yields the key renames and label changes in categories (a) and (b) mechanically.
Only (c), the capability gates, needs human judgement, because "the file cannot
answer this" is not visible in a schema diff.

## Known gaps this should close

Found while reviewing the 2.3 work, none currently handled:

- Pre-2.3 unresolved plays carry the literal string
  `"Unable to Decode. Invalid Value (255)."` in `"Contact Result - Secondary"`
  (Rio wrote `0xFF` and its table had no `0xFF` entry). A 2.3 file reads
  `"None"`. Category (b).
- 2.3 added an `out_type == CAUGHT → "Out-caught"` branch for infield flies,
  which the game calls out *without* a catch. Older files don't have it.
  Category (b), currently missing.
- The game's own enum names id `0x10` `CAUGHT_INFIELD_FLY`; Rio and pyrio both
  say `"Foul catch"`. That's a straight table error, not version-dependent — but
  it belongs in the same audit.
- `"Version": null` raises `TypeError`; an unparseable version silently applies
  every correction. Category: policy, above.

## Findings from the version review (complete: 0.1.0 → 2.3.0)

Verified against every release tag in a local ProjectRio checkout — 25 releases
from `0.1.0` to `2.2.0`, plus the unreleased `2.3.0_release` branch.

### The version lists have two outright bugs

Rio shipped more early releases than the tag list suggests at a glance: `0.1.0`
through `0.1.9` including `0.1.4.a` and `0.1.7.a`. Reading `RIO_REV_STR` out of
`Common/Version.cpp` at each tag gives the exact string that lands in the
`"Version"` key:

| release | string written |
|---|---|
| 0.1.0–0.1.3 | `"0.1.0(Alpha)"` … `"0.1.3(Alpha)"` — **never written to a file** (no `Version` key before 0.1.7) |
| 0.1.4 – 0.1.6 | `"0.1.4"`, `"0.1.4.a"`, `"0.1.5"`, `"0.1.6"` — also never written |
| 0.1.7 | `"0.1.7"` |
| 0.1.7.a | `"0.1.7.a"` |
| 0.1.8, 0.1.9, 1.9.1 | `"0.1.8"`, `"0.1.9"`, `"1.9.1"` |

Against that:

1. **`"0.1.7a"` in both lists is a typo.** The real string is `"0.1.7.a"`, with a
   dot. As written, every `0.1.7.a` file falls through both lists.
2. **`"0.1.7"` is absent from both lists**, yet 0.1.7 uses the old `0 = home`
   numbering *and* `"Team N Roster M"` keys. Those files are misread today.
3. **`"Pre 0.1.7"` in `OLD_TEAM_STRUCTURE` is wrong for 0.1.0–0.1.5.** Those
   files have no `"Character Game Stats"` object at all — they use
   `"Away/Home Team Roster"` arrays plus a `"Player Stats"` array with string
   `"Team": "Away"/"Home"` labels. `"Team N Roster M"` first appears in 0.1.6.
   So pyrio claims to handle them and would raise `KeyError` instead. That is a
   capability gate, category (c), not a key rename.

I previously suspected these lists were wrong because a `1.8.0` file would fall
through. That was wrong — Rio went `0.1.9` → `1.9.1`, so no such release exists.
The lists are wrong for the three reasons above instead.

| # | Change | Range | Kind | pyrio today |
|---|---|---|---|---|
| A | No `"Character Game Stats"` object: rosters are `"Away/Home Team Roster"` arrays plus a `"Player Stats"` array with string `"Team"` labels | **0.1.0–0.1.5** | (c) | claims support via `"Pre 0.1.7"`; raises `KeyError` |
| B | No `"Version"` key at all | **0.1.0–0.1.6** | (a) | defaults to `"Pre 0.1.7"` — correct |
| C | Top-level scores: quoted strings → bare numbers | at **0.1.6** | (b) | `safe_int` absorbs it |
| D | `"Quitter Team"` is a bare bool with **no "nobody quit" value** — `(quitter_port == away_port)`, emitted `"0"`/`"1"`, then decoded `"Home"`/`"Away"` from 0.1.8 | **0.1.6–0.1.9** | (c) | **`wasQuit()` returns `True` for every game** |
| E | Event `"Away Stars"` / `"Home Stars"` written from each other's source | **0.1.6** only | (b) | **not handled** |
| F | `"0.1.7"` and `"0.1.7.a"` fall through both version lists | — | (a)/(b) | **bug** (see above) |
| 1 | Bunt swing byte: `aAB_Miss_SwingOrBunt` (`2=bunt`) → `aAB_AnySwing` (`0/1` only) | at **1.9.5** | (c) | gate is `versionBefore(1,9,6)` — **off by one release** |
| 2 | `Captain` flag inverted in the stat file | **1.9.2–1.9.4** | (b) | **not handled** |
| 3 | `"Ball Max Height"` source: software running max → memory read `0x8089250c` | at **1.9.2** | (b)/(c) | **not handled** |
| 4 | `"TagSetID"` emitted as a bare empty value → invalid JSON | **1.9.5** only | (c) | **not handled** (file won't parse) |
| 5 | `"TagSetID"` is `""` or a bare integer — mixed type in one key | **1.9.6+** | (a) | **not handled** |
| 6 | Roster key `"Team N Roster M"` → `"Away/Home Roster M"` | at **1.9.5** | (a) | correct |
| 7 | Team index `0 = home` → `0 = away` | at **1.9.2** | (b) | correct |
| 8 | `"Pitches Per Position"` → `"Batters Per Position"` | at **1.9.2** | (a) | correct |
| 9 | `"Ranked"` removed | at **1.9.5** | (a) | n/a |
| 10 | `"Pitch Result"`, `"Multi-out"`, pitch-level `"Ball/Batter Position - X/Z"`, `"Ball Angle"`, `"Ball Vertical/Horizontal Power"` all removed; `"Ball Power"`/`"Vert Angle"`/`"Horiz Angle"`, `"RNG1-3"`, contact positions, `"Ball Hang Time"`, `"Num Outs During Play"`, `"In Strikezone"` all added | at **1.9.2** | (a) | partial |
| 11 | `"Bat Contact Pos - Y"` and `"Ball Contact Pos - Y"` removed | at **1.9.3** | (a) | n/a |
| 12 | `"GameID"` is a quoted **decimal** string; 2.3.0 switches to lowercase **hex** via `gameIDToHex` | decimal **≤2.2.0**, hex **2.3.0+** | (b) | **`gameID()` always parses base 16** — wrong for every file that exists today |
| 13 | Stadium names renamed: `"Bowser's Castle"` → `"Bowser Castle"`, and the same for Wario, Yoshi (also → `"Yoshi Park"`), Peach and DK | at **2.1.0** | (b) | only the Bowser alias exists; the other four are unhandled |
| 14 | `"Pitches Per Position"` gone, `"Batters Per Position"` in its place | at **1.9.2** | (a) | **prep reads the old key with no fallback → `KeyError` on every file since 1.9.2** |
| 15 | `"Quitter Team"` sentinel `0xFF` → raw `255` / decoded `"None"`; `2` means `"Crash"` | **1.9.1+** | (b) | **prep's `!= ""` → `wasQuit()` is `True` for every game**; `"Crash"` unmapped |
| 16 | `"Dead Ball Reason"` added (event + HUD) | at **2.2.0** | (a) | tolerated via `.get` |
| 17 | HUD gains a header block: `GameID`, `Away/Home Port`, `Away/Home Logo`, `Fielding Position`, `Star Skills On`, `Mercy On`, `First Batting Team`, inning-score arrays | at **2.2.0** | (a) | **direct indexing → `KeyError` on any pre-2.2.0 HUD** |
| 18 | Raw `hud.json` written alongside `decoded.hud.json` | at **2.2.0** | (a) | n/a |
| 19 | Ongoing-game payload restructured: `"Runner 1B"` (0/1 flag) → `"Runner 1B Roster"` (roster index, or `-1`); `CharID` scalars → arrays; `Pitcher`/`Batter` → `… Roster Loc` | at **2.2.0** | (b) | not parsed (no consumer in pyrio) |

Three of these need acting on before anything else:

**#1 is a live bug in the 2.3 work.** The gate source changed at **1.9.5**, not
1.9.6 — and 1.9.5 and 1.9.6 are byte-identical in that logic. So
`versionBefore(1, 9, 6)` rejects an entire release's bunts that behave exactly
like the ones it accepts. It should be `versionBefore(1, 9, 5)`. Note also that
`aAB_AnySwing` is documented `0=No swing, 1=swing` — it does not track bunts at
all — which is *why* a bunt reads as swing `0` from 1.9.5 onward, and is the
premise the whole bunt feature rests on.

**#2 affects team naming, not just a flag.** `team_name_algo` resolves a team's
name from its captain, so a 1.9.2–1.9.4 file can produce the wrong team name,
not merely the wrong `captain()`.

**#4 explains a known symptom.** The 2.3 PR reports "9 are older files with
invalid JSON (`"TagSetID": ,`)" out of 1,534 real files. That is this bug, and
it is bounded to 1.9.5 — which means it is recoverable with a targeted repair on
read rather than being written off as corrupt.

**#12 is the worst one found, and it is live on every branch.** `gameID()` does
`int(self.statJson["GameID"].replace(',', ''), 16)`, but Rio emits GameID as a
quoted *decimal* string in every release up to 2.2.0. Tested against the
fixture in this repo, whose filename carries the same id:

```
GameID in file : '3896251267'
gameID()       : 243037180519     # int(x, 16)
correct        : 3896251267       # int(x)
```

Wrong by a factor of ~62, silently, for every stat file that exists. Any join
against server records keyed on GameID fails. It is also a textbook case for
this proposal: 2.3.0 switches to hex, so base-16 becomes *correct* for files
written from then on. The parse is version-dependent and currently isn't.

**#14 and #15 are live on `v1.0.0-prep` specifically.** The 2.3 PR fixes both
(`battersPerPosition` with a fallback, and `wasQuit` excluding `255`/`"None"`),
but prep has neither, so on prep `pitchesPerPosition()` raises on every file
since 1.9.2 and `wasQuit()` is unconditionally `True`. That is an argument for
landing the 2.3 work onto prep rather than main.

**One retraction.** `safe_int`'s comma stripping has no target. Two independent
sweeps of the tracker across all 25 releases found no `imbue`, no locale, and no
grouped numeric output anywhere — every number goes through `std::to_string` or
default stream formatting. The real type hazard is the opposite one: integers
emitted *inside quotes*, which is stable across every release and affects
`GameID`, `Team`, `Event Num`, `Ball Power`, `Vert/Horiz Angle`, `RNG1-3` and
`Ball Hang Time`. Comma stripping is harmless, but it is defending against
something that has never been written.

One thing this review *retracted*: I suspected the hard-coded version lists were
wrong because a `1.8.0` or `1.9.0` file would fall through them. No such release
exists — Rio went `0.1.9` → `1.9.1` — so both lists are correct for every
version that was actually shipped. The lists are still the wrong *mechanism*
(they cannot express a range), but they are not currently wrong about data.

## Open questions

1. Is `UNKNOWN` the right default for an unparseable version, given that it would
   make such files refuse capabilities rather than quietly return corrected-ish
   numbers?
2. Should corrections be *opt-out*? A tool comparing pyrio's output to Rio's raw
   files may want the uncorrected value.
3. Where does this live under the module map — `stat_file/` (it decodes) or
   alongside `rio_value.py` (it's schema knowledge)? The boundary in `CLAUDE.md`
   suggests the latter, since `stat_file/` is meant to parse, not interpret.
