from __future__ import annotations

from typing import Iterable

from .models import Team


def _single_round_days(teams: list[Team]) -> list[list[tuple[Team, Team]]]:
    """Build one full round-robin split into days."""
    if len(teams) < 2:
        return []

    # Circle method: each team plays at most once per day.
    rotating = list(teams)
    ghost: Team | None = None
    if len(rotating) % 2 == 1:
        ghost = Team(name="BYE")
        rotating.append(ghost)

    rounds = len(rotating) - 1
    half = len(rotating) // 2
    days: list[list[tuple[Team, Team]]] = []

    for _ in range(rounds):
        day_games: list[tuple[Team, Team]] = []
        for idx in range(half):
            home = rotating[idx]
            away = rotating[-(idx + 1)]
            if home is ghost or away is ghost:
                continue
            day_games.append((home, away))
        days.append(day_games)

        # Keep first fixed, rotate the rest.
        rotating = [rotating[0], rotating[-1], *rotating[1:-1]]

    return days


def build_round_robin_days(
    teams: Iterable[Team],
    games_per_matchup: int = 2,
    calendar_density: float = 0.60,
) -> list[list[tuple[Team, Team]]]:
    team_list = list(teams)
    if len(team_list) < 2 or games_per_matchup < 1:
        return []

    # Convert full slates into calendar days so not every team plays nightly.
    target_games_per_day = max(2, int((len(team_list) * max(0.35, min(calendar_density, 1.0))) / 2))

    base_days = _single_round_days(team_list)
    season_days: list[list[tuple[Team, Team]]] = []

    def _spread_day(day_games: list[tuple[Team, Team]]) -> list[list[tuple[Team, Team]]]:
        if len(day_games) <= target_games_per_day:
            return [day_games]
        chunks: list[list[tuple[Team, Team]]] = []
        for idx in range(0, len(day_games), target_games_per_day):
            chunk = day_games[idx : idx + target_games_per_day]
            if chunk:
                chunks.append(chunk)
        return chunks

    for matchup_index in range(games_per_matchup):
        flip_home_away = matchup_index % 2 == 1
        for day in base_days:
            raw_day = ([(away, home) for home, away in day] if flip_home_away else list(day))
            season_days.extend(_spread_day(raw_day))
    return season_days


def build_round_robin(teams: Iterable[Team], games_per_matchup: int = 2) -> list[tuple[Team, Team]]:
    return [game for day in build_round_robin_days(teams, games_per_matchup) for game in day]
