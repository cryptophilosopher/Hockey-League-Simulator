from __future__ import annotations

import random
from dataclasses import dataclass

from .models import Player, Team

# Injury baseline derived from 2024-25 team-level NHL man-games lost and injuries.
# Rotowire table totals imply ~0.01357 injury events per player-game and ~8.04 games missed per injury.
BASE_INJURY_EVENT_RATE = 0.01357
BASE_GAMES_MISSED_PER_INJURY = 8.04

STRATEGY_EFFECTS: dict[str, dict[str, float]] = {
    "balanced": {"offense": 0.0, "defense": 0.0, "injury_mult": 1.00},
    "aggressive": {"offense": 0.40, "defense": -0.20, "injury_mult": 1.35},
    "defensive": {"offense": -0.15, "defense": 0.30, "injury_mult": 0.82},
}


@dataclass(slots=True)
class GoalEvent:
    scorer: Player
    assists: list[Player]


@dataclass(slots=True)
class InjuryEvent:
    player: Player
    games_out: int


@dataclass(slots=True)
class GameResult:
    home: Team
    away: Team
    home_goals: int
    away_goals: int
    overtime: bool
    home_goal_events: list[GoalEvent]
    away_goal_events: list[GoalEvent]
    home_injuries: list[InjuryEvent]
    away_injuries: list[InjuryEvent]
    home_goalie: Player | None
    away_goalie: Player | None
    home_goalie_shots: int = 0
    home_goalie_saves: int = 0
    away_goalie_shots: int = 0
    away_goalie_saves: int = 0
    home_pp_goals: int = 0
    home_pp_chances: int = 0
    away_pp_goals: int = 0
    away_pp_chances: int = 0


def _sample_goals(strength: float, rng: random.Random, randomness_scale: float = 1.0) -> int:
    # Poisson-like scoring tuned near recent NHL scoring environment.
    jitter = 0.18 * max(0.5, randomness_scale)
    lam = max(1.5, min(3.5, strength + rng.uniform(-jitter, jitter)))
    l = pow(2.718281828459045, -lam)
    k = 0
    p = 1.0
    while p > l:
        k += 1
        p *= rng.random()
    return max(0, k - 1)


def _avg(values: list[float], fallback: float) -> float:
    if not values:
        return fallback
    return sum(values) / len(values)


def _line_deployment(team: Team) -> dict[str, list[Player]]:
    forwards = team.dressed_forwards() or team.active_forwards()
    defensemen = team.dressed_defense() or team.active_defense()
    forwards = sorted(forwards, key=lambda p: (p.shooting * 0.58 + p.playmaking * 0.32 + p.defense * 0.10), reverse=True)
    defensemen = sorted(defensemen, key=lambda p: (p.defense * 0.50 + p.playmaking * 0.30 + p.physical * 0.20), reverse=True)
    return {
        "top6": forwards[:6],
        "mid6": forwards[6:12],
        "depth_f": forwards[12:],
        "pair1": defensemen[:2],
        "pair2": defensemen[2:4],
        "pair3": defensemen[4:6],
        "depth_d": defensemen[6:],
    }


def _deployment_usage(team: Team) -> dict[str, float]:
    deployment = _line_deployment(team)
    usage: dict[str, float] = {}
    for p in deployment["top6"]:
        usage[p.player_id] = 1.25
    for p in deployment["mid6"]:
        usage[p.player_id] = 0.95
    for p in deployment["depth_f"]:
        usage[p.player_id] = 0.72
    for p in deployment["pair1"]:
        usage[p.player_id] = 1.15
    for p in deployment["pair2"]:
        usage[p.player_id] = 0.95
    for p in deployment["pair3"]:
        usage[p.player_id] = 0.78
    for p in deployment["depth_d"]:
        usage[p.player_id] = 0.66
    return usage


def _team_offense(team: Team) -> float:
    deployment = _line_deployment(team)
    forwards = team.dressed_forwards() or team.active_forwards()
    defensemen = team.dressed_defense() or team.active_defense()
    # Weighted to top players so elite skaters drive team offense more like pro usage.
    fw_scores = sorted(
        [(p.shooting * 0.64 + p.playmaking * 0.36 + p.physical * 0.10) for p in forwards],
        reverse=True,
    )
    d_scores = sorted(
        [(p.shooting * 0.36 + p.playmaking * 0.64 + p.defense * 0.08) for p in defensemen],
        reverse=True,
    )

    fw_top6 = _avg([p.shooting * 0.64 + p.playmaking * 0.36 + p.physical * 0.10 for p in deployment["top6"]], _avg(fw_scores[:6], 3.0))
    fw_mid6 = _avg([p.shooting * 0.58 + p.playmaking * 0.34 + p.physical * 0.08 for p in deployment["mid6"]], fw_top6 * 0.92)
    fw_depth = _avg([p.shooting * 0.56 + p.playmaking * 0.34 + p.physical * 0.10 for p in deployment["depth_f"]], fw_mid6 * 0.90)
    d_top = _avg([p.shooting * 0.36 + p.playmaking * 0.64 + p.defense * 0.08 for p in deployment["pair1"] + deployment["pair2"]], _avg(d_scores[:4], 2.9))
    d_depth = _avg([p.shooting * 0.32 + p.playmaking * 0.60 + p.defense * 0.08 for p in deployment["pair3"] + deployment["depth_d"]], d_top * 0.90)
    # Sharper separation: top-end skill should drive goals more strongly.
    fw_off = fw_top6 * 0.56 + fw_mid6 * 0.29 + fw_depth * 0.15
    d_off = d_top * 0.72 + d_depth * 0.28
    top_heavy_gap = max(0.0, fw_top6 - fw_depth)
    fatigue_penalty = min(0.10, top_heavy_gap * 0.03)
    return fw_off * 0.84 + d_off * 0.16 - fatigue_penalty


def _team_defense(team: Team) -> float:
    deployment = _line_deployment(team)
    defensemen = deployment["pair1"] + deployment["pair2"] + deployment["pair3"] + deployment["depth_d"]
    forwards = deployment["top6"] + deployment["mid6"] + deployment["depth_f"]
    goalies = team.dressed_goalies() or team.active_goalies()

    d_pair1 = _avg([p.defense for p in deployment["pair1"]], 3.1)
    d_pair2 = _avg([p.defense for p in deployment["pair2"]], 3.0)
    d_pair3 = _avg([p.defense for p in deployment["pair3"] + deployment["depth_d"]], 2.8)
    d_def = d_pair1 * 0.42 + d_pair2 * 0.35 + d_pair3 * 0.23
    f_top = _avg([p.defense for p in deployment["top6"]], 2.9)
    f_mid = _avg([p.defense for p in deployment["mid6"]], 2.9)
    f_depth = _avg([p.defense for p in deployment["depth_f"]], 2.8)
    f_def = f_top * 0.42 + f_mid * 0.35 + f_depth * 0.23
    g_def = _avg([p.goaltending for p in goalies], 2.7)
    return d_def * 0.45 + g_def * 0.35 + f_def * 0.20


def _special_teams_ratings(team: Team) -> tuple[float, float, float]:
    deployment = _line_deployment(team)
    pp_forwards = deployment["top6"][:4] if deployment["top6"] else (deployment["mid6"][:4] if deployment["mid6"] else [])
    pp_def = (deployment["pair1"][:1] + deployment["pair2"][:1]) if (deployment["pair1"] or deployment["pair2"]) else []
    pk_forwards = deployment["mid6"][:3] + deployment["depth_f"][:1]
    pk_def = deployment["pair1"] + deployment["pair2"][:1]
    goalies = team.dressed_goalies() or team.active_goalies()
    goalie = max(goalies, key=lambda g: g.goaltending) if goalies else None

    pp = _avg([(p.shooting * 0.50 + p.playmaking * 0.44 + p.defense * 0.06) for p in (pp_forwards + pp_def)], 2.8)
    pk = _avg([(p.defense * 0.62 + p.playmaking * 0.22 + p.physical * 0.16) for p in (pk_forwards + pk_def)], 2.8)
    goalie_term = goalie.goaltending if goalie is not None else 2.7
    return (pp, pk, goalie_term)


def _apply_special_teams_goals(
    home: Team,
    away: Team,
    home_strategy: str,
    away_strategy: str,
    home_goals: int,
    away_goals: int,
    rng: random.Random,
    home_offense_bonus: float = 0.0,
    away_offense_bonus: float = 0.0,
) -> tuple[int, int, int, int, int, int]:
    home_pp, home_pk, home_goalie = _special_teams_ratings(home)
    away_pp, away_pk, away_goalie = _special_teams_ratings(away)

    strat_pen = {"aggressive": 0.95, "balanced": 0.0, "defensive": -0.45}
    home_discipline = _avg([(p.durability * 0.48 + p.defense * 0.30 - p.physical * 0.10) for p in (home.dressed_players() or home.active_players())], 2.9)
    away_discipline = _avg([(p.durability * 0.48 + p.defense * 0.30 - p.physical * 0.10) for p in (away.dressed_players() or away.active_players())], 2.9)
    ref_var = rng.uniform(-0.45, 0.55)

    home_pen_taken = max(0, int(round(2.6 + strat_pen.get(home_strategy, 0.0) + (3.0 - home_discipline) * 0.70 + ref_var)))
    away_pen_taken = max(0, int(round(2.6 + strat_pen.get(away_strategy, 0.0) + (3.0 - away_discipline) * 0.70 - ref_var * 0.35)))
    home_pp_chances = away_pen_taken
    away_pp_chances = home_pen_taken

    home_pp_rate = 0.135 + (home_pp - 3.0) * 0.024 - (away_pk - 3.0) * 0.020 - (away_goalie - 3.0) * 0.015 + home_offense_bonus * 0.05
    away_pp_rate = 0.135 + (away_pp - 3.0) * 0.024 - (home_pk - 3.0) * 0.020 - (home_goalie - 3.0) * 0.015 + away_offense_bonus * 0.05
    home_pp_rate = max(0.05, min(0.31, home_pp_rate))
    away_pp_rate = max(0.05, min(0.31, away_pp_rate))

    home_pp_goals = 0
    away_pp_goals = 0
    for _ in range(home_pp_chances):
        if rng.random() < home_pp_rate:
            home_goals += 1
            home_pp_goals += 1
    for _ in range(away_pp_chances):
        if rng.random() < away_pp_rate:
            away_goals += 1
            away_pp_goals += 1
    return (
        home_goals,
        away_goals,
        home_pp_goals,
        home_pp_chances,
        away_pp_goals,
        away_pp_chances,
    )


def _choose_weighted(players: list[Player], weights: list[float], rng: random.Random) -> Player:
    if not players:
        raise ValueError("No players available for weighted selection.")
    return rng.choices(players, weights=weights, k=1)[0]


def _starting_goalie(team: Team, rng: random.Random) -> Player | None:
    goalies = team.dressed_goalies() or team.active_goalies()
    if not goalies:
        return None
    if team.starting_goalie_name:
        chosen = next((g for g in goalies if g.name == team.starting_goalie_name), None)
        if chosen is not None:
            return chosen

    # AI rotation: bias toward best goalie but avoid starting same goalie every night.
    return max(
        goalies,
        key=lambda p: (p.goaltending * 0.80) - (p.goalie_games * 0.045) + (rng.random() * 0.04),
    )


def _record_goalie_stats(
    goalie: Player | None,
    goals_against: int,
    overtime: bool,
    is_win: bool,
    rng: random.Random,
) -> tuple[int, int]:
    if goalie is None:
        return (0, 0)
    goalie.goalie_games += 1
    goalie.goals_against += goals_against

    # Tune shot/goal balance closer to NHL goaltending environment (~.900 team SV%).
    base_shots = 22 + int(goals_against * 1.6) + rng.randrange(0, 10)
    skill_mod = int((3.5 - goalie.goaltending) * 1.0)
    shots = max(goals_against + 8, base_shots + skill_mod)
    saves = max(0, shots - goals_against)
    goalie.shots_against += shots
    goalie.saves += saves

    if is_win:
        goalie.goalie_wins += 1
        if goals_against == 0:
            goalie.goalie_shutouts += 1
    elif overtime:
        goalie.goalie_ot_losses += 1
    else:
        goalie.goalie_losses += 1
    return (shots, saves)


def _record_goal(team: Team, rng: random.Random, usage: dict[str, float] | None = None) -> GoalEvent:
    skaters = [p for p in team.dressed_skaters() if p.position != "G"]
    if not skaters:
        skaters = [p for p in team.active_skaters() if p.position != "G"]
    if not skaters:
        skaters = team.dressed_players() or team.active_players()

    scorer_weights = []
    for p in skaters:
        # Strongly skill-driven scorer share: elite shooters create much more production.
        role_mod = 1.10 if p.position in {"C", "LW", "RW"} else 0.68
        toi_mod = usage.get(p.player_id, 1.0) if usage else 1.0
        weighted = max(0.15, p.scoring_weight * role_mod * toi_mod)
        scorer_weights.append(max(0.1, weighted ** 2.25))
    scorer = _choose_weighted(skaters, scorer_weights, rng)
    scorer.goals += 1

    remaining = [p for p in skaters if p is not scorer]
    assists: list[Player] = []

    if remaining and rng.random() < 0.79:
        primary = _choose_weighted(
            remaining,
            [
                max(
                    0.1,
                    (p.playmaking * (1.08 if p.position in {"C", "D"} else 1.0) + p.defense * 0.05) ** 1.55,
                )
                for p in remaining
            ],
            rng,
        )
        primary.assists += 1
        assists.append(primary)
        remaining = [p for p in remaining if p is not primary]

    if remaining and rng.random() < 0.43:
        secondary = _choose_weighted(
            remaining,
            [max(0.1, (p.playmaking * 0.95 + p.defense * 0.08) ** 1.35) for p in remaining],
            rng,
        )
        secondary.assists += 1
        assists.append(secondary)

    return GoalEvent(scorer=scorer, assists=assists)


def _build_goal_events(
    team: Team,
    goals: int,
    rng: random.Random,
    record_stats: bool,
    usage: dict[str, float] | None = None,
) -> list[GoalEvent]:
    events: list[GoalEvent] = []
    if goals <= 0:
        return events
    if record_stats:
        return [_record_goal(team, rng, usage=usage) for _ in range(goals)]

    skaters = [p for p in team.dressed_skaters() if p.position != "G"]
    if not skaters:
        skaters = [p for p in team.active_skaters() if p.position != "G"]
    if not skaters:
        skaters = team.dressed_players() or team.active_players()
    if not skaters:
        return events

    scorer_weights = []
    for p in skaters:
        role_mod = 1.10 if p.position in {"C", "LW", "RW"} else 0.68
        toi_mod = usage.get(p.player_id, 1.0) if usage else 1.0
        weighted = max(0.15, p.scoring_weight * role_mod * toi_mod)
        scorer_weights.append(max(0.1, weighted ** 2.25))
    for _ in range(goals):
        scorer = _choose_weighted(skaters, scorer_weights, rng)
        remaining = [p for p in skaters if p is not scorer]
        assists: list[Player] = []
        if remaining and rng.random() < 0.79:
            primary = _choose_weighted(
                remaining,
                [
                    max(
                        0.1,
                        (p.playmaking * (1.08 if p.position in {"C", "D"} else 1.0) + p.defense * 0.05) ** 1.55,
                    )
                    for p in remaining
                ],
                rng,
            )
            assists.append(primary)
            remaining = [p for p in remaining if p is not primary]
        if remaining and rng.random() < 0.43:
            secondary = _choose_weighted(
                remaining,
                [max(0.1, (p.playmaking * 0.95 + p.defense * 0.08) ** 1.35) for p in remaining],
                rng,
            )
            assists.append(secondary)
        events.append(GoalEvent(scorer=scorer, assists=assists))
    return events


def _sample_games_missed(rng: random.Random, strategy_mult: float) -> int:
    # Geometric-like distribution with mean near NHL observed games missed per injury.
    target_mean = BASE_GAMES_MISSED_PER_INJURY * (0.92 + 0.16 * strategy_mult)
    stop_probability = 1.0 / max(2.0, target_mean)
    games = 1
    while rng.random() > stop_probability and games < 30:
        games += 1
    return games


def _apply_injuries(team: Team, strategy: str, rng: random.Random) -> list[InjuryEvent]:
    strategy_effect = STRATEGY_EFFECTS.get(strategy, STRATEGY_EFFECTS["balanced"])
    injury_mult = strategy_effect["injury_mult"]
    events: list[InjuryEvent] = []

    dressed = team.dressed_players() or team.active_players()
    for player in dressed:
        durability_mod = max(0.55, 1.35 - player.durability / 10.0)
        position_mod = 0.65 if player.position == "G" else 1.0
        probability = BASE_INJURY_EVENT_RATE * injury_mult * durability_mod * position_mod

        if rng.random() < probability:
            games_out = _sample_games_missed(rng, injury_mult)
            player.injuries += 1
            player.injured_games_remaining = max(player.injured_games_remaining, games_out)
            player.games_missed_injury += games_out
            events.append(InjuryEvent(player=player, games_out=games_out))

    return events


def simulate_game(
    home: Team,
    away: Team,
    home_strategy: str = "balanced",
    away_strategy: str = "balanced",
    home_coach_offense_bonus: float = 0.0,
    away_coach_offense_bonus: float = 0.0,
    home_coach_defense_bonus: float = 0.0,
    away_coach_defense_bonus: float = 0.0,
    home_context_bonus: float = 0.0,
    away_context_bonus: float = 0.0,
    randomness_scale: float = 1.0,
    rng: random.Random | None = None,
    record_player_stats: bool = True,
    apply_injuries: bool = True,
    home_injury_mult: float = 1.0,
    away_injury_mult: float = 1.0,
    record_goalie_stats: bool = True,
) -> GameResult:
    rng = rng or random.Random()
    home_goalie = _starting_goalie(home, rng)
    away_goalie = _starting_goalie(away, rng)

    home_effect = STRATEGY_EFFECTS.get(home_strategy, STRATEGY_EFFECTS["balanced"])
    away_effect = STRATEGY_EFFECTS.get(away_strategy, STRATEGY_EFFECTS["balanced"])

    home_usage = _deployment_usage(home)
    away_usage = _deployment_usage(away)
    home_usage_mean = _avg(list(home_usage.values()), 1.0)
    away_usage_mean = _avg(list(away_usage.values()), 1.0)
    home_usage_peak = max(home_usage.values()) if home_usage else 1.0
    away_usage_peak = max(away_usage.values()) if away_usage else 1.0
    home_fatigue = min(0.12, max(0.0, (home_usage_peak - home_usage_mean) * 0.10))
    away_fatigue = min(0.12, max(0.0, (away_usage_peak - away_usage_mean) * 0.10))

    # Slightly lower scoring baseline to better match modern pro-hockey game totals.
    home_strength = _team_offense(home) * 0.55 + (5.0 - _team_defense(away)) * 0.36 - 0.08
    away_strength = _team_offense(away) * 0.55 + (5.0 - _team_defense(home)) * 0.36 - 0.22

    home_strength += home_effect["offense"] - away_effect["defense"]
    away_strength += away_effect["offense"] - home_effect["defense"]
    home_strength += home_coach_offense_bonus - away_coach_defense_bonus
    away_strength += away_coach_offense_bonus - home_coach_defense_bonus
    home_strength += home_context_bonus
    away_strength += away_context_bonus
    home_strength -= home_fatigue
    away_strength -= away_fatigue

    # Emergency goalie handling: a non-goalie in net should make winning very unlikely.
    if home_goalie is None:
        away_strength += 1.15
        home_strength -= 0.12
    elif home_goalie.position != "G":
        away_strength += 0.95
        home_strength -= 0.10
    if away_goalie is None:
        home_strength += 1.15
        away_strength -= 0.12
    elif away_goalie.position != "G":
        home_strength += 0.95
        away_strength -= 0.10

    home_goals = _sample_goals(home_strength, rng, randomness_scale=randomness_scale)
    away_goals = _sample_goals(away_strength, rng, randomness_scale=randomness_scale)
    home_goals, away_goals, home_pp_goals, home_pp_chances, away_pp_goals, away_pp_chances = _apply_special_teams_goals(
        home=home,
        away=away,
        home_strategy=home_strategy,
        away_strategy=away_strategy,
        home_goals=home_goals,
        away_goals=away_goals,
        rng=rng,
        home_offense_bonus=home_coach_offense_bonus,
        away_offense_bonus=away_coach_offense_bonus,
    )

    overtime = False
    if home_goals == away_goals:
        overtime = True
        if rng.random() < 0.52:
            home_goals += 1
        else:
            away_goals += 1

    if record_player_stats:
        for player in (home.dressed_players() or home.active_players()):
            player.games_played += 1
        for player in (away.dressed_players() or away.active_players()):
            player.games_played += 1

    home_goal_events = _build_goal_events(home, home_goals, rng, record_player_stats, usage=home_usage)
    away_goal_events = _build_goal_events(away, away_goals, rng, record_player_stats, usage=away_usage)

    home_injuries: list[InjuryEvent] = []
    away_injuries: list[InjuryEvent] = []
    if apply_injuries:
        home_injuries = _apply_injuries(home, home_strategy, rng)
        away_injuries = _apply_injuries(away, away_strategy, rng)
        if home_injury_mult != 1.0:
            for injury in home_injuries:
                adjusted = max(1, int(round(injury.games_out * home_injury_mult)))
                delta = adjusted - injury.games_out
                injury.games_out = adjusted
                injury.player.injured_games_remaining = max(injury.player.injured_games_remaining, adjusted)
                injury.player.games_missed_injury += delta
        if away_injury_mult != 1.0:
            for injury in away_injuries:
                adjusted = max(1, int(round(injury.games_out * away_injury_mult)))
                delta = adjusted - injury.games_out
                injury.games_out = adjusted
                injury.player.injured_games_remaining = max(injury.player.injured_games_remaining, adjusted)
                injury.player.games_missed_injury += delta

    home_win = home_goals > away_goals
    home_goalie_shots = 0
    home_goalie_saves = 0
    away_goalie_shots = 0
    away_goalie_saves = 0
    if record_goalie_stats:
        home_goalie_shots, home_goalie_saves = _record_goalie_stats(
            home_goalie, away_goals, overtime, home_win, rng
        )
        away_goalie_shots, away_goalie_saves = _record_goalie_stats(
            away_goalie, home_goals, overtime, not home_win, rng
        )
    else:
        if home_goalie is not None:
            base_shots = 22 + int(away_goals * 1.6) + rng.randrange(0, 10)
            skill_mod = int((3.5 - home_goalie.goaltending) * 1.0)
            home_goalie_shots = max(away_goals + 8, base_shots + skill_mod)
            home_goalie_saves = max(0, home_goalie_shots - away_goals)
        if away_goalie is not None:
            base_shots = 22 + int(home_goals * 1.6) + rng.randrange(0, 10)
            skill_mod = int((3.5 - away_goalie.goaltending) * 1.0)
            away_goalie_shots = max(home_goals + 8, base_shots + skill_mod)
            away_goalie_saves = max(0, away_goalie_shots - home_goals)

    return GameResult(
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        overtime=overtime,
        home_goal_events=home_goal_events,
        away_goal_events=away_goal_events,
        home_injuries=home_injuries,
        away_injuries=away_injuries,
        home_goalie=home_goalie,
        away_goalie=away_goalie,
        home_goalie_shots=home_goalie_shots,
        home_goalie_saves=home_goalie_saves,
        away_goalie_shots=away_goalie_shots,
        away_goalie_saves=away_goalie_saves,
        home_pp_goals=home_pp_goals,
        home_pp_chances=home_pp_chances,
        away_pp_goals=away_pp_goals,
        away_pp_chances=away_pp_chances,
    )
