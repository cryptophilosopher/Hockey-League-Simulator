from hockey_sim.app import build_default_teams
from hockey_sim.league import LeagueSimulator


def test_division_and_team_count() -> None:
    teams = build_default_teams()
    assert len(teams) == 24
    division_counts: dict[str, int] = {}
    for team in teams:
        division_counts[team.division] = division_counts.get(team.division, 0) + 1
    assert set(division_counts.keys()) == {"North", "East", "Central", "West"}
    assert all(count == 6 for count in division_counts.values())
    assert all(team.primary_color.startswith("#") for team in teams)
    assert all(team.secondary_color.startswith("#") for team in teams)


def test_roster_size_and_default_dressed_count() -> None:
    teams = build_default_teams()
    for team in teams:
        assert len(team.roster) == 22
        dressed_count = len(team.dressed_players())
        assert dressed_count == 20


def test_player_names_are_league_unique() -> None:
    teams = build_default_teams()
    names = [player.name for team in teams for player in team.roster]
    assert len(names) == len(set(names))


def test_last_names_are_varied_within_team() -> None:
    teams = build_default_teams()
    for team in teams:
        last_names = {player.name.split()[-1] for player in team.roster}
        assert len(last_names) > 1


def test_offseason_advances_age_and_persists_history(tmp_path) -> None:
    teams = build_default_teams()
    history_file = tmp_path / "season_history.json"
    sim = LeagueSimulator(teams=teams, games_per_matchup=1, seed=11, history_path=str(history_file))

    initial_ages = {player.name: player.age for team in sim.teams for player in team.roster}
    while not sim.is_complete():
        sim.simulate_next_day()

    offseason = sim.advance_to_next_season()
    assert offseason["advanced"] is True
    assert len(offseason["drafted"]) == 24
    assert all(len(picks) >= 1 for picks in offseason["drafted"].values())
    assert history_file.exists()
    assert sim.season_number == 2
    assert len(sim.season_history) == 1
    assert sim.season_history[0]["season"] == 1
    assert "draft" in sim.season_history[0]

    for team in sim.teams:
        assert len(team.roster) == 22
        for player in team.roster:
            if player.name in initial_ages:
                assert player.age == initial_ages[player.name] + 1


def test_goalie_stats_accumulate() -> None:
    teams = build_default_teams()
    sim = LeagueSimulator(teams=teams, games_per_matchup=1, seed=9)
    sim.simulate_next_day()
    goalies = sim.get_goalie_stats()
    assert goalies
    assert any(g.goalie_games > 0 for g in goalies)


def test_playoffs_include_cup_final_and_champion(tmp_path) -> None:
    teams = build_default_teams()
    history_file = tmp_path / "season_history.json"
    sim = LeagueSimulator(
        teams=teams,
        games_per_matchup=1,
        seed=17,
        history_path=str(history_file),
        state_path=str(tmp_path / "league_state.json"),
        career_history_path=str(tmp_path / "career_history.json"),
        hall_of_fame_path=str(tmp_path / "hall_of_fame.json"),
    )
    while not sim.is_complete():
        sim.simulate_next_day()

    offseason = sim.advance_to_next_season()
    playoffs = offseason.get("playoffs", {})
    assert isinstance(playoffs, dict)
    assert playoffs.get("cup_name") == "Founders Cup"
    assert isinstance(playoffs.get("cup_champion"), str)
    assert playoffs.get("cup_champion")
    rounds = playoffs.get("rounds", [])
    assert isinstance(rounds, list)
    assert any(isinstance(r, dict) and r.get("name") == "Cup Final" for r in rounds)


def test_round_one_draft_order_and_player_pick_tracking(tmp_path) -> None:
    teams = build_default_teams()
    history_file = tmp_path / "season_history.json"
    sim = LeagueSimulator(
        teams=teams,
        games_per_matchup=1,
        seed=23,
        history_path=str(history_file),
        state_path=str(tmp_path / "league_state.json"),
        career_history_path=str(tmp_path / "career_history.json"),
        hall_of_fame_path=str(tmp_path / "hall_of_fame.json"),
    )
    while not sim.is_complete():
        sim.simulate_next_day()

    standings = sim.get_standings()
    worst_team = standings[-1].team.name
    best_team = standings[0].team.name

    offseason = sim.advance_to_next_season()
    drafted_details = offseason.get("drafted_details", {})
    assert isinstance(drafted_details, dict)
    assert worst_team in drafted_details
    assert best_team in drafted_details

    worst_first = drafted_details[worst_team][0]
    best_first = drafted_details[best_team][0]
    assert worst_first.get("overall") == 1
    assert best_first.get("overall") == len(teams)
    assert worst_first.get("round") == 1
    assert best_first.get("round") == 1

    round_one = []
    for team in sim.teams:
        for player in team.roster:
            if player.draft_round == 1:
                round_one.append(player)
    assert len(round_one) >= len(teams)
    assert any(p.draft_overall == 1 for p in round_one)
