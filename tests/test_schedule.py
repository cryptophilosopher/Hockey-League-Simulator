from hockey_sim.models import Team
from hockey_sim.schedule import build_round_robin


def test_round_robin_count() -> None:
    teams = [
        Team(name="A"),
        Team(name="B"),
        Team(name="C"),
        Team(name="D"),
    ]
    games = build_round_robin(teams, games_per_matchup=2)
    assert len(games) == 12
