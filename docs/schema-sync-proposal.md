# Proposal: a single source of truth for the Rio stat-file schema

**Status:** draft for discussion with the Project Rio maintainers
**Author:** pyrio maintainers
**Date:** 2026-06-20

## Problem

The Mario Superstar Baseball stat/HUD file format — its **field names** and its
**id↔name enum maps** (characters, stadiums, positions, results, …) — is
currently re-encoded by hand in at least three places:

| Repo | Role | Holds a copy of… |
|---|---|---|
| **ProjectRio** (C++ `MSB_StatTracker`) | *writes* the files | field names + enum maps (`cCharIdToCharName`, `cManualSelectDecode`, …) — the real source |
| **ProjectRio-web** | *ingests* → DB, *recreates* files | `consts.py` enums/aliases, `models.py` columns, `populate_db.py` field reads |
| **pyrio** | *reads* the files | `LookupDicts` enum tables + field-name literals in accessors |

Because these are maintained independently, **a change in the C++ client
silently makes the consumers wrong.** Rename a field or add a character in
`MSB_StatTracker` and both pyrio and the web layer keep using the old contract
until someone notices at runtime.

## What pyrio already does (the pattern)

pyrio treats `MSB_StatTracker.h/.cpp` as the **source of truth** and validates
against it at test time (no runtime coupling — the library stays standalone):

- **Table parity** — `tests/test_canonical_parity.py` parses every
  `std::map` in the header and asserts pyrio's `LookupDicts` match. This already
  caught real bugs (inverted `HAND`, a `STEAL_TYPE` typo, `MANUAL_SELECT`).
- **Field parity** — the same test parses the field names the tracker emits and
  asserts every field pyrio reads exists in canonical, catching renames.

Both skip cleanly when a Project Rio checkout isn't present, so they don't gate
CI that lacks the C++ source.

## Proposal

Make ProjectRio (the only repo that *defines* the format) **emit a small,
machine-readable schema artifact**, and have every consumer validate against it.

1. **ProjectRio** generates `schema/stat_file_schema.json` from
   `MSB_StatTracker` (a tiny build/CI step, or a committed generated file):
   ```jsonc
   {
     "version": "2.2.0",
     "fields": ["GameID", "TagSetID", "StadiumID", "...": "..."],
     "enums": {
       "CharName":      { "0": "Mario", "1": "Luigi", "...": "..." },
       "ManualSelect":  { "0": "No Selected Char", "1": "Pitcher" },
       "...": "..."
     }
   }
   ```
2. **pyrio** and **ProjectRio-web** consume that one artifact — pyrio's parity
   tests point at `schema.json` instead of parsing C++; the web layer validates
   `consts.py`/`populate_db.py` against the same file.
3. A schema change in the client becomes a **single reviewed diff** in
   `schema.json` that fans out to red tests in every consumer until they update.

### Why not tighter coupling?

- **No runtime imports across repos.** pyrio is a standalone library and must
  not pull in Flask/SQLAlchemy (web) or the Dolphin tree (client). Validation
  stays at test time.
- **No code-gen of pyrio from C++.** Generating pyrio's tables from the header
  would couple pyrio's build to the C++ repo layout; a published `schema.json`
  is a stable contract instead.

## Migration path

1. **Now (pyrio-side, done):** parity tests against `MSB_StatTracker` guard the
   pyrio half today.
2. **Short term:** ProjectRio commits/generates `schema.json`; pyrio repoints
   its parity tests at it (trivial change).
3. **Medium term:** ProjectRio-web adds equivalent validation of `consts.py`
   against `schema.json`, collapsing the third copy into a validated mirror.

The end state: **one schema defined where the format lives, two validators that
fail loudly on drift** — instead of three hand-maintained copies that drift
silently.
