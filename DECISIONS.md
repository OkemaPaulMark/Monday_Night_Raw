# Technical decisions for Monday Night Raw
# Keep this short; expand only when a choice is non-obvious.

## Naming
- Django app `stats` instead of `statistics` (stdlib conflict).

## Auth
- DRF TokenAuthentication for the SPA (simple, sufficient for a private group of classmates).
- Roles on `accounts.User.role`: ADMIN | PLAYER.

## Matchdays: no teams, no score, no squad step
- Turnout is dynamic — one week it's 12 people in 2 teams, the next it's 20+ across 3
  informal teams formed on the pitch. The app never tracks teams or a match score: a
  matchday just records who scored/assisted (`GoalEvent`). There is no
  `MatchTeam`/`MatchTeamPlayer`, no `Match.team_a_score`/`team_b_score`, and `GoalEvent` has
  no team-side attribution.
- This was a deliberate rework (moving from an earlier fixed-2-team, score-tracked model)
  after a real matchday had 20+ turnout and 3 teams, which the old fixed-squad-size (10–14),
  even-split, 2-team model couldn't represent at all.
- There's also no separate "pick who's playing" step: `MatchParticipant` rows are derived
  automatically in `match_service.replace_goals()` from whoever appears as a scorer or
  assister, plus an optional `also_played` list of pure attendees (no goal involvement) sent
  in the same request — admin picks both from the full registered player list, on one page.
  `also_played` exists specifically so Team of the Week has enough people to rank on a
  low-scoring day (see below); without it, `matches_played` would only count scorers/assisters.
- No squad-size limit either — finalize accepts any participant count; the only real
  requirement is at least one (enforced naturally by `generate_weekly_awards_for_match`,
  which needs someone to award).
- Consequently there are no clean sheets, wins, draws, or losses — none of those have a basis
  without a team side and a score. Performance score is goals + assists only
  (`stats/scoring.py`), and `PlayerStats` has no win/loss/clean-sheet fields.
- No Team A/B standings page/endpoint either, for the same reason.

## Data integrity
- Match events (`GoalEvent`) are the source of truth for goals/assists.
- No separate "Player of the Match" concept: with one match per week, POTM and Player of the Week
  are always the same player, so `finalize_match` only ever computes Player of the Week (ties
  supported) — there is no `Match.player_of_the_match` field.
- Weekly/monthly awards stored as `Award` + `AwardRecipient` (supports ties).
- **Team of the Week is fixed at `TOTW_SIZE = 7`** (`awards/services/award_calculator.py`),
  not "half of that day's attendees" — with dynamic turnout, half of 22 attendees isn't a
  realistic team size. Capped to the participant count on a small-turnout day. Ranking is by
  performance score descending, then **name ascending as a deterministic tie-break** — matters
  most for "also played" attendees who all sit at 0 and need a stable, explainable fill order
  for the remaining spots (not random, not insertion order).
- Monthly uniqueness applies only when `match IS NULL` so weekly awards can share a calendar month.
- Monthly awards regenerate automatically whenever a match in that month is finalized or reopened
  (`sync_monthly_awards_for_month`), not just via the manual "generate" admin action.

## Scoring
- Weights centralized in `settings.PERFORMANCE_SCORE_WEIGHTS` and `stats/scoring.py`. Just
  `GOAL_WEIGHT`/`ASSIST_WEIGHT` (plus `RATING_POINTS_FOR_FIVE`) — no clean-sheet/win/draw
  weights, since none of those have a basis anymore.

## Database
- SQLite only (WAL mode) — no separate DB server/container. Chosen over Postgres for the
  production deploy target: a memory-constrained (1GB) single-box VM, ~14 users, roughly one
  match a week. Eliminates an entire container/process from the stack.
- WAL mode + `busy_timeout` (`config/settings.py`) let reads proceed while a write is in
  progress; production runs gunicorn with a single worker process (multiple threads) rather
  than several, since SQLite allows only one writer at a time and one process avoids
  cross-process lock contention on the db file.
- `SQLITE_DB_PATH` env var overrides the db file location — used in `docker-compose.prod.yml`
  to point it at a mounted volume so it survives container recreation.
