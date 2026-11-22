# Rio web contract fixtures

These responses were **derived from ProjectRio-web's route code at `d4bf233`**
(`app/views/*.py`, its models' `to_dict()` methods and its own tests under
`app/tests/`), not recorded from the live API. Each file is shaped exactly as
that code builds its response: the same keys, nesting and value types, with
`null` wherever a LEFT JOIN or nullable column allows it, and the empty `{}`
that `/landing_data/` and `/star_chances/` return when no event matches. The
values are made up.

They should be **replaced by recorded responses**, captured once from
`api.projectrio.app` with public read-only queries and stripped of user data
(docs/v1.0.0-audit.md, section 4a, rule 6). Keep the file names: the tests in
`tests/web/` load them by name.

| File | Route | Request it answers |
|---|---|---|
| `games.json` | `GET /games/` | `include_linescore=1&include_scoring_plays=1` |
| `games_plain.json` | `GET /games/` | no `include_*` flags |
| `stats.json` | `GET /stats/` | no `by_*` flags |
| `stats_by_character.json` | `GET /stats/` | `by_char=1` |
| `stats_by_user_swing.json` | `GET /stats/` | `by_user=1&by_swing=1&include_runs_scored=1&include_pitcher_wins=1&exclude_fielding=1&exclude_misc=1` |
| `stats_by_game_spot_hand.json` | `GET /stats/` | `by_game=1&by_roster_order=1&by_batting_hand=1&by_fielding_hand=1` |
| `events.json` | `GET /events/` | any |
| `star_chances.json` | `GET /star_chances/` | no `by_inning` |
| `star_chances_by_inning.json` | `GET /star_chances/` | `by_inning=true` |
| `landing_data.json` | `GET /landing_data/` | any |
| `tags.json` | `POST /tag/list` | any |
| `tag_sets.json` | `POST /tag_set/list` | any |
| `tag_set.json` | `GET /tag_set/<id>` | |
| `ladder.json` | `POST /tag_set/ladder/` | |
| `ladder_games.json` | `GET /ladder/games/` | |
| `ongoing_games.json` | `GET /populate_db/ongoing_game/` | |
| `users.json` | `GET /user/all/` | |
| `communities.json` | `POST /community/list` | |
| `members.json` | `POST /community/members` | |
| `community_key.json` | `POST /community/key` | `action=generate` |
