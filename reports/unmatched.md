# Unmatched report

Generated: `2026-08-23T15:38:29Z` (UTC)

## Match rate summary

- Odds rows in `prop_results`: **795**
- Matched (player_game found): **0** (0.0%)
- Matched non-void (outcome-eligible): **0**
- Voided (kept, outcome nulled): **0**
- Name-mapped (player_id set, may still lack player_game): **795** (100.0%)

### By book

| Book | Rows | Matched | Rate |
|---|---:|---:|---:|
| betonlineag | 156 | 0 | 0.0% |
| betrivers | 234 | 0 | 0.0% |
| draftkings | 153 | 0 | 0.0% |
| fanduel | 159 | 0 | 0.0% |
| williamhill_us | 93 | 0 | 0.0% |

### By month (game_date_et)

| Month | Rows | Matched | Rate |
|---|---:|---:|---:|
| 2026-08 | 795 | 0 | 0.0% |

### By team

| Team | Rows | Matched | Rate |
|---|---:|---:|---:|
| unmatched | 795 | 0 | 0.0% |

## Odds rows with no player-game

Every unmatched odds row is retained in `prop_results` with `player_id` null or set and a `reason_code` (never silently dropped).

| Raw name | Date (ET) | Book | Reason | Count |
|---|---|---|---|---:|
| A'ja Wilson | 2026-08-23 | betrivers | no_player_game | 9 |
| Aliyah Boston | 2026-08-23 | betrivers | no_player_game | 9 |
| Caitlin Clark | 2026-08-23 | betrivers | no_player_game | 9 |
| Carla Leite | 2026-08-23 | betrivers | no_player_game | 9 |
| Flau'jae Johnson | 2026-08-23 | betrivers | no_player_game | 9 |
| Jackie Young | 2026-08-23 | betrivers | no_player_game | 9 |
| Jessica Shepard | 2026-08-23 | betrivers | no_player_game | 9 |
| Kelsey Mitchell | 2026-08-23 | betrivers | no_player_game | 9 |
| Kiki Iriafen | 2026-08-23 | betrivers | no_player_game | 9 |
| Laura Juskaite | 2026-08-23 | betrivers | no_player_game | 9 |
| Megan DiLeo | 2026-08-23 | betrivers | no_player_game | 9 |
| NaLyssa Smith | 2026-08-23 | betrivers | no_player_game | 9 |
| Natisha Hiedeman | 2026-08-23 | betrivers | no_player_game | 9 |
| Paige Bueckers | 2026-08-23 | betrivers | no_player_game | 9 |
| A'ja Wilson | 2026-08-23 | fanduel | no_player_game | 7 |
| Alanna Smith | 2026-08-23 | betrivers | no_player_game | 6 |
| Arike Ogunbowale | 2026-08-23 | betrivers | no_player_game | 6 |
| Azura Stevens | 2026-08-23 | betrivers | no_player_game | 6 |
| Bridget Carleton | 2026-08-23 | betrivers | no_player_game | 6 |
| Chelsea Gray | 2026-08-23 | betrivers | no_player_game | 6 |
| Dominique Malonga | 2026-08-23 | betrivers | no_player_game | 6 |
| Emily Engstler | 2026-08-23 | betrivers | no_player_game | 6 |
| Ezi Magbegor | 2026-08-23 | betrivers | no_player_game | 6 |
| Isabelle Harrison | 2026-08-23 | betrivers | no_player_game | 6 |
| Jade Melbourne | 2026-08-23 | betrivers | no_player_game | 6 |
| Kamilla Cardoso | 2026-08-23 | betrivers | no_player_game | 6 |
| Kiki Rice | 2026-08-23 | betrivers | no_player_game | 6 |
| Natasha Cloud | 2026-08-23 | betrivers | no_player_game | 6 |
| Odyssey Sims | 2026-08-23 | betrivers | no_player_game | 6 |
| Shakira Austin | 2026-08-23 | betrivers | no_player_game | 6 |
| Sonia Citron | 2026-08-23 | betrivers | no_player_game | 6 |
| Sydney Taylor | 2026-08-23 | betrivers | no_player_game | 6 |
| A'ja Wilson | 2026-08-23 | draftkings | no_player_game | 5 |
| A'ja Wilson | 2026-08-23 | betonlineag | no_player_game | 3 |
| A'ja Wilson | 2026-08-23 | williamhill_us | no_player_game | 3 |
| Alanna Smith | 2026-08-23 | betonlineag | no_player_game | 3 |
| Alanna Smith | 2026-08-23 | draftkings | no_player_game | 3 |
| Alanna Smith | 2026-08-23 | fanduel | no_player_game | 3 |
| Alanna Smith | 2026-08-23 | williamhill_us | no_player_game | 3 |
| ... | ... | ... | ... | (truncated; full list on clean run) |

## Top 20 unmatched names by frequency

| Raw name | Unmatched rows |
|---|---:|
| A'ja Wilson | 27 |
| Aliyah Boston | 21 |
| Caitlin Clark | 21 |
| Carla Leite | 21 |
| Flau'jae Johnson | 21 |
| Jackie Young | 21 |
| Jessica Shepard | 21 |
| Kelsey Mitchell | 21 |
| Kiki Iriafen | 21 |
| Laura Juskaite | 21 |
| NaLyssa Smith | 21 |
| Paige Bueckers | 21 |
| Alanna Smith | 18 |
| Arike Ogunbowale | 18 |
| Azura Stevens | 18 |
| Bridget Carleton | 18 |
| Chelsea Gray | 18 |
| Dominique Malonga | 18 |
| Emily Engstler | 18 |
| Ezi Magbegor | 18 |

## Player-games with no odds (expected)

Total player-games without a matched prop row: **44114** (not everyone gets props; showing up to 200 most recent).

(Full per-row listing regenerates on `python run.py clean`.)

## Fuzzy proposals (needs approval - NOT auto-applied)

_No fuzzy proposals this run._

## Reason code legend

| Code | Meaning |
|---|---|
| `matched` | Joined to a player_game on game_date_et |
| `missing_event_meta` | No commence_time/teams in odds_events for odds game_id |
| `no_name_match` | Could not map raw name to player_id |
| `needs_fuzzy_approval` | Fuzzy candidates printed; awaiting `--approve` |
| `ambiguous_team_date` | Multiple roster hits for team+date |
| `no_player_game` | Name mapped but no player_game on that ET date |
