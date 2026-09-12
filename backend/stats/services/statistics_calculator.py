"""Authoritative player / leaderboard statistics from match events."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from awards.models import Award, AwardRecipient
from matches.models import GoalEvent, Match, MatchParticipant
from players.models import Player
from stats.scoring import calculate_match_performance_score, performance_to_rating


def _defensive_stats(match: Match, player: Player) -> tuple[bool | None, int | None]:
    """
    (clean_sheet, goals_conceded) for this player in this match, if team
    side + score were entered that day. (None, None) otherwise — most days
    won't have this, since team/score entry is optional.
    """
    if not match.has_team_scores:
        return None, None
    participant = match.participants.filter(player=player).first()
    if participant is None or participant.side is None:
        return None, None
    conceded = match.team_b_score if participant.side == MatchParticipant.Side.A else match.team_a_score
    return conceded == 0, conceded


@dataclass
class PlayerStats:
    player_id: int
    name: str
    profile_photo: str | None = None
    position: str | None = None
    matches_played: int = 0
    goals: int = 0
    assists: int = 0
    goal_contributions: int = 0
    clean_sheets: int = 0
    potw: int = 0
    rating: float = 0.0  # career average out of 5.0

    def to_dict(self) -> dict:
        data = asdict(self)
        data['rating'] = round(self.rating, 1)
        return data


def _finalized_matches():
    return Match.objects.filter(
        status=Match.Status.COMPLETED,
        finalized_at__isnull=False,
    )


def calculate_player_stats(player: Player) -> PlayerStats:
    matches = _finalized_matches().filter(participants__player=player).distinct()
    photo = player.profile_photo.url if player.profile_photo else None
    stats = PlayerStats(
        player_id=player.id,
        name=player.name,
        profile_photo=photo,
        position=player.position,
    )

    rating_total = Decimal('0')

    for match in matches.prefetch_related('goals'):
        stats.matches_played += 1
        match_goals = match.goals.filter(scorer=player).count()
        match_assists = match.goals.filter(assister=player).count()
        clean_sheet, goals_conceded = _defensive_stats(match, player)
        if clean_sheet:
            stats.clean_sheets += 1
        raw = calculate_match_performance_score(
            goals=match_goals,
            assists=match_assists,
            position=player.position,
            clean_sheet=clean_sheet,
            goals_conceded=goals_conceded,
        )
        rating_total += performance_to_rating(raw)

    stats.goals = GoalEvent.objects.filter(
        scorer=player,
        match__finalized_at__isnull=False,
    ).count()
    stats.assists = GoalEvent.objects.filter(
        assister=player,
        match__finalized_at__isnull=False,
    ).count()
    stats.goal_contributions = stats.goals + stats.assists
    stats.potw = AwardRecipient.objects.filter(
        player=player,
        award__award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
        award__is_confirmed=True,
    ).count()

    if stats.matches_played:
        stats.rating = float(
            (rating_total / Decimal(stats.matches_played)).quantize(Decimal('0.1'))
        )
    return stats


def leaderboard(ordering: str = '-goals') -> list[dict]:
    allowed = {
        'goals', '-goals',
        'assists', '-assists',
        'goal_contributions', '-goal_contributions',
        'clean_sheets', '-clean_sheets',
        'potw', '-potw',
        'matches_played', '-matches_played',
        'rating', '-rating',
        'name', '-name',
    }
    if ordering not in allowed:
        ordering = '-goals'

    rows = [calculate_player_stats(p) for p in Player.objects.filter(is_active=True)]
    reverse = ordering.startswith('-')
    key = ordering.lstrip('-')
    rows.sort(key=lambda r: getattr(r, key), reverse=reverse)

    result = []
    for rank, row in enumerate(rows, start=1):
        item = row.to_dict()
        item['rank'] = rank
        result.append(item)
    return result


def player_match_history(player: Player) -> list[dict]:
    history = []
    matches = _finalized_matches().filter(participants__player=player).order_by('-match_date')
    for match in matches:
        goals = match.goals.filter(scorer=player).count()
        assists = match.goals.filter(assister=player).count()
        clean_sheet, goals_conceded = _defensive_stats(match, player)
        is_potw = AwardRecipient.objects.filter(
            player=player,
            award__match=match,
            award__award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
        ).exists()
        raw = calculate_match_performance_score(
            goals=goals,
            assists=assists,
            position=player.position,
            clean_sheet=clean_sheet,
            goals_conceded=goals_conceded,
        )

        history.append({
            'match_id': match.id,
            'match_date': match.match_date,
            'goals': goals,
            'assists': assists,
            'clean_sheet': clean_sheet,
            'goals_conceded': goals_conceded,
            'potw': is_potw,
            'rating': float(performance_to_rating(raw)),
        })
    return history


def match_player_performance(match: Match, player: Player) -> Decimal:
    clean_sheet, goals_conceded = _defensive_stats(match, player)
    return calculate_match_performance_score(
        goals=match.goals.filter(scorer=player).count(),
        assists=match.goals.filter(assister=player).count(),
        position=player.position,
        clean_sheet=clean_sheet,
        goals_conceded=goals_conceded,
    )


def dashboard_summary() -> dict:
    players = Player.objects.filter(is_active=True)
    matches = _finalized_matches().order_by('-match_date', '-id')
    latest = matches.first()
    board = leaderboard('-goals')

    def top(metric: str):
        ordered = sorted(board, key=lambda r: r[metric], reverse=True)
        return ordered[0] if ordered else None

    latest_potw = (
        AwardRecipient.objects.filter(
            award__award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
            award__is_confirmed=True,
        )
        .select_related('player', 'award__match')
        .order_by('-award__match__match_date')
        .first()
    )

    latest_match_potw = None
    latest_match_goals = None
    if latest:
        recipients = AwardRecipient.objects.filter(
            award__match=latest,
            award__award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
        ).select_related('player')
        if recipients:
            latest_match_potw = ', '.join(r.player.name for r in recipients)
        latest_match_goals = latest.goals.count()

    return {
        'total_players': players.count(),
        'total_matches': matches.count(),
        'latest_match': (
            {
                'id': latest.id,
                'match_date': latest.match_date,
                'goals': latest_match_goals,
                'potw': latest_match_potw,
            }
            if latest
            else None
        ),
        'latest_potw': (
            {
                'player': latest_potw.player.name,
                'match_date': latest_potw.award.match.match_date if latest_potw.award.match else None,
            }
            if latest_potw
            else None
        ),
        'top_scorer': top('goals'),
        'top_assister': top('assists'),
        'top_rated': top('rating'),
        'most_potw': top('potw'),
    }
