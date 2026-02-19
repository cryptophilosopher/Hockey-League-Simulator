import json

import pytest

from hockey_sim.app import build_default_teams
from hockey_sim.league import LeagueSimulator


def _sim(tmp_path, **overrides) -> LeagueSimulator:
    kwargs = {
        "teams": build_default_teams(),
        "games_per_matchup": 1,
        "seed": 101,
        "state_path": str(tmp_path / "league_state.json"),
        "history_path": str(tmp_path / "season_history.json"),
        "career_history_path": str(tmp_path / "career_history.json"),
        "hall_of_fame_path": str(tmp_path / "hall_of_fame.json"),
    }
    kwargs.update(overrides)
    return LeagueSimulator(**kwargs)


@pytest.mark.regression
def test_loads_legacy_list_season_history(tmp_path) -> None:
    history_path = tmp_path / "season_history.json"
    history_path.write_text(json.dumps([{"season": 1, "note": "legacy"}]), encoding="utf-8")
    sim = _sim(tmp_path, history_path=str(history_path))
    assert len(sim.season_history) == 1
    assert sim.season_history[0]["season"] == 1


@pytest.mark.regression
def test_loads_legacy_dict_career_history(tmp_path) -> None:
    career_path = tmp_path / "career_history.json"
    career_path.write_text(
        json.dumps({"Player Example": [{"season": 1, "team": "Aurora"}]}),
        encoding="utf-8",
    )
    sim = _sim(tmp_path, career_history_path=str(career_path))
    assert "Player Example" in sim.career_history
    assert sim.career_history["Player Example"][0]["season"] == 1


@pytest.mark.regression
def test_loads_legacy_list_hall_of_fame(tmp_path) -> None:
    hof_path = tmp_path / "hall_of_fame.json"
    hof_path.write_text(json.dumps([{"name": "Legend"}]), encoding="utf-8")
    sim = _sim(tmp_path, hall_of_fame_path=str(hof_path))
    assert len(sim.hall_of_fame) == 1
    assert sim.hall_of_fame[0]["name"] == "Legend"


@pytest.mark.regression
def test_rejects_future_save_version_with_clear_error(tmp_path) -> None:
    history_path = tmp_path / "season_history.json"
    history_path.write_text(
        json.dumps({"save_version": 999, "season_history": [{"season": 1}]}),
        encoding="utf-8",
    )
    sim = _sim(tmp_path, history_path=str(history_path))
    assert sim.season_history == []
    assert "Unsupported season history version" in sim.last_load_error


@pytest.mark.regression
def test_state_save_includes_save_version_and_backup(tmp_path) -> None:
    sim = _sim(tmp_path)
    state_path = tmp_path / "league_state.json"
    backup_path = tmp_path / "league_state.json.bak"

    # First write creates the primary file.
    sim._save_state()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["save_version"] == LeagueSimulator.SAVE_VERSION

    # Second write should create/refresh backup.
    sim._save_state()
    assert backup_path.exists()
