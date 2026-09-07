# Technical decisions for Monday Night Raw
# Keep this short; expand only when a choice is non-obvious.

## Naming
- Django app `stats` instead of `statistics` (stdlib conflict).

## Auth
- DRF TokenAuthentication for the SPA (simple, sufficient for a private 14-player group).
- Roles on `accounts.User.role`: ADMIN | PLAYER.

## Data integrity
- Match events (`GoalEvent`) are the source of truth for goals/assists.
- Clean sheets are never stored; derived from score + team membership.
- No separate "Player of the Match" concept: with one match per week, POTM and Player of the Week
  are always the same player, so `finalize_match` only ever computes Player of the Week (ties
  supported) — there is no `Match.player_of_the_match` field.
- Weekly/monthly awards stored as `Award` + `AwardRecipient` (supports ties and TOTW of 7).
- Monthly uniqueness applies only when `match IS NULL` so weekly awards can share a calendar month.
- Monthly awards regenerate automatically whenever a match in that month is finalized or reopened
  (`sync_monthly_awards_for_month`), not just via the manual "generate" admin action.

## Teams
- `MatchTeam` side A/B is match-specific; standings use these labels as cumulative labels only.

## Scoring
- Weights centralized in `settings.PERFORMANCE_SCORE_WEIGHTS` and `stats/scoring.py`.

## Database
- PostgreSQL is primary. `USE_SQLITE=True` is an optional local smoke-test escape hatch only.
