from __future__ import annotations

import random
from typing import Iterable

from .league import LeagueSimulator
from .models import Player, Team
from .names import NameGenerator

PLAYER_BIRTH_COUNTRIES: tuple[tuple[str, str, float], ...] = (
    ("Canada", "CA", 0.37),
    ("United States", "US", 0.23),
    ("Sweden", "SE", 0.08),
    ("Finland", "FI", 0.06),
    ("Russia", "RU", 0.08),
    ("Czechia", "CZ", 0.05),
    ("Slovakia", "SK", 0.03),
    ("Germany", "DE", 0.03),
    ("Switzerland", "CH", 0.03),
    ("Latvia", "LV", 0.02),
    ("Denmark", "DK", 0.02),
)


def _clamp_rating(value: float, low: float = 0.3, high: float = 5.0) -> float:
    return max(low, min(high, value))


def _sample_quality(rng: random.Random, tier_plan: list[tuple[float, float, float]]) -> float:
    roll = rng.random()
    cumulative = 0.0
    for weight, low, high in tier_plan:
        cumulative += weight
        if roll <= cumulative:
            return rng.uniform(low, high)
    return rng.uniform(tier_plan[-1][1], tier_plan[-1][2])


def _sample_birth_country(rng: random.Random) -> tuple[str, str]:
    roll = rng.random()
    cumulative = 0.0
    for country, code, weight in PLAYER_BIRTH_COUNTRIES:
        cumulative += weight
        if roll <= cumulative:
            return country, code
    country, code, _weight = PLAYER_BIRTH_COUNTRIES[0]
    return country, code


def _make_roster(
    team_name: str,
    offense_bias: float,
    defense_bias: float,
    physical_bias: float,
    name_gen: NameGenerator,
) -> list[Player]:
    roster: list[Player] = []
    rng = random.Random(f"{team_name}:{offense_bias:.3f}:{defense_bias:.3f}:{physical_bias:.3f}")

    # Pro-style talent pyramid: very few stars, more middle/depth players.
    forward_positions = ["C", "C", "C", "C", "C", "LW", "LW", "LW", "LW", "RW", "RW", "RW", "RW"]
    forward_tiers = (
        [(0.08, 0.90, 1.00), (0.22, 0.74, 0.89), (0.42, 0.56, 0.73), (0.28, 0.38, 0.55)]
    )
    for pos in forward_positions:
        quality = _sample_quality(rng, forward_tiers)
        birth_country, birth_country_code = _sample_birth_country(rng)
        role = rng.choice(["sniper", "playmaker", "two-way", "depth"])
        shoot_adj = 0.22 if role == "sniper" else (-0.10 if role == "playmaker" else 0.02)
        make_adj = 0.22 if role == "playmaker" else (-0.10 if role == "sniper" else 0.02)
        def_adj = 0.18 if role == "two-way" else (-0.06 if role in {"sniper", "playmaker"} else 0.10)
        phy_adj = 0.16 if role == "depth" else (0.06 if role == "two-way" else -0.02)
        roster.append(
            Player(
                team_name=team_name,
                name=name_gen.next_name(birth_country_code),
                position=pos,
                birth_country=birth_country,
                birth_country_code=birth_country_code,
                shooting=_clamp_rating(1.55 + quality * 3.20 + offense_bias * 0.80 + shoot_adj + rng.uniform(-0.12, 0.12)),
                playmaking=_clamp_rating(1.55 + quality * 3.10 + offense_bias * 0.75 + make_adj + rng.uniform(-0.12, 0.12)),
                defense=_clamp_rating(1.45 + quality * 2.95 + defense_bias * 0.85 + def_adj + rng.uniform(-0.10, 0.10)),
                goaltending=0.3,
                physical=_clamp_rating(1.50 + quality * 2.65 + physical_bias * 0.90 + phy_adj + rng.uniform(-0.12, 0.12)),
                durability=_clamp_rating(1.80 + quality * 2.35 + rng.uniform(-0.15, 0.15)),
                age=rng.randint(20, 35),
                prime_age=rng.randint(25, 29),
            )
        )

    defense_tiers = (
        [(0.07, 0.88, 1.00), (0.24, 0.72, 0.87), (0.41, 0.55, 0.71), (0.28, 0.38, 0.54)]
    )
    for _idx in range(7):
        quality = _sample_quality(rng, defense_tiers)
        birth_country, birth_country_code = _sample_birth_country(rng)
        role = rng.choice(["shutdown", "two-way", "offensive", "depth"])
        shoot_adj = 0.16 if role == "offensive" else (-0.05 if role == "shutdown" else 0.02)
        make_adj = 0.18 if role == "offensive" else (0.06 if role == "two-way" else -0.04)
        def_adj = 0.28 if role == "shutdown" else (0.10 if role == "two-way" else -0.06)
        phy_adj = 0.18 if role in {"shutdown", "depth"} else 0.05
        roster.append(
            Player(
                team_name=team_name,
                name=name_gen.next_name(birth_country_code),
                position="D",
                birth_country=birth_country,
                birth_country_code=birth_country_code,
                shooting=_clamp_rating(1.40 + quality * 2.75 + offense_bias * 0.60 + shoot_adj + rng.uniform(-0.10, 0.10)),
                playmaking=_clamp_rating(1.55 + quality * 2.95 + offense_bias * 0.65 + make_adj + rng.uniform(-0.10, 0.10)),
                defense=_clamp_rating(1.85 + quality * 3.05 + defense_bias * 1.00 + def_adj + rng.uniform(-0.10, 0.10)),
                goaltending=0.3,
                physical=_clamp_rating(1.65 + quality * 2.70 + physical_bias * 1.00 + phy_adj + rng.uniform(-0.12, 0.12)),
                durability=_clamp_rating(1.90 + quality * 2.30 + rng.uniform(-0.12, 0.12)),
                age=rng.randint(20, 36),
                prime_age=rng.randint(26, 30),
            )
        )

    # One starter + one backup with realistic skill gap.
    starter_quality = _sample_quality(rng, [(0.08, 0.90, 1.00), (0.35, 0.76, 0.89), (0.57, 0.58, 0.75)])
    backup_quality = _sample_quality(rng, [(0.02, 0.88, 0.96), (0.18, 0.72, 0.87), (0.80, 0.48, 0.71)])
    for idx, quality in enumerate([starter_quality, backup_quality]):
        birth_country, birth_country_code = _sample_birth_country(rng)
        roster.append(
            Player(
                team_name=team_name,
                name=name_gen.next_name(birth_country_code),
                position="G",
                birth_country=birth_country,
                birth_country_code=birth_country_code,
                shooting=0.4,
                playmaking=_clamp_rating(1.00 + quality * 1.70 + rng.uniform(-0.08, 0.08)),
                defense=_clamp_rating(1.80 + quality * 2.20 + defense_bias * 0.45 + rng.uniform(-0.08, 0.08)),
                goaltending=_clamp_rating(2.05 + quality * 2.55 + defense_bias * 0.65 + (0.14 if idx == 0 else -0.10) + rng.uniform(-0.08, 0.08)),
                physical=_clamp_rating(1.55 + quality * 2.00 + physical_bias * 0.55 + rng.uniform(-0.08, 0.08)),
                durability=_clamp_rating(2.05 + quality * 2.00 + (0.10 if idx == 0 else -0.05) + rng.uniform(-0.08, 0.08)),
                age=rng.randint(22, 36),
                prime_age=rng.randint(27, 32),
            )
        )

    return roster


def _make_minor_roster(
    team_name: str,
    offense_bias: float,
    defense_bias: float,
    physical_bias: float,
    name_gen: NameGenerator,
) -> list[Player]:
    rng = random.Random(f"minor:{team_name}:{offense_bias:.3f}:{defense_bias:.3f}:{physical_bias:.3f}")
    roster: list[Player] = []
    positions = ["C", "LW", "RW", "C", "LW", "RW", "D", "D", "D", "G"]
    for pos in positions:
        quality = rng.uniform(0.36, 0.72)
        birth_country, birth_country_code = _sample_birth_country(rng)
        shooting = 1.20 + quality * 2.40 + offense_bias * 0.60 + rng.uniform(-0.10, 0.10)
        playmaking = 1.20 + quality * 2.35 + offense_bias * 0.55 + rng.uniform(-0.10, 0.10)
        defense = 1.30 + quality * 2.30 + defense_bias * 0.70 + rng.uniform(-0.10, 0.10)
        physical = 1.35 + quality * 2.10 + physical_bias * 0.75 + rng.uniform(-0.10, 0.10)
        goaltending = 0.3
        if pos == "G":
            goaltending = 1.70 + quality * 2.25 + defense_bias * 0.55 + rng.uniform(-0.08, 0.08)
            shooting = 0.4
            playmaking = 0.90 + quality * 1.45 + rng.uniform(-0.08, 0.08)
        roster.append(
            Player(
                team_name=team_name,
                name=name_gen.next_name(birth_country_code),
                position=pos,
                birth_country=birth_country,
                birth_country_code=birth_country_code,
                shooting=_clamp_rating(shooting),
                playmaking=_clamp_rating(playmaking),
                defense=_clamp_rating(defense),
                goaltending=_clamp_rating(goaltending),
                physical=_clamp_rating(physical),
                durability=_clamp_rating(1.80 + quality * 2.00 + rng.uniform(-0.10, 0.10)),
                age=rng.randint(18, 24),
                prime_age=rng.randint(25, 29),
                prospect_tier="AHL",
                seasons_to_nhl=rng.randint(0, 2),
                prospect_potential=_clamp_rating(0.35 + quality * 0.60 + rng.uniform(-0.06, 0.06), low=0.25, high=0.98),
                prospect_boom_chance=_clamp_rating(0.05 + quality * 0.10 + rng.uniform(-0.02, 0.02), low=0.03, high=0.22),
                prospect_bust_chance=_clamp_rating(0.16 - quality * 0.11 + rng.uniform(-0.02, 0.02), low=0.04, high=0.24),
                prospect_resolved=False,
            )
        )
    return roster


def build_default_teams() -> list[Team]:
    team_logos: dict[str, str] = {
        "Aurora": "??",
        "Icebreakers": "??",
        "Timberwolves": "??",
        "Glaciers": "???",
        "Polar Caps": "??",
        "Silver Pines": "??",
        "Harbor Kings": "?",
        "Liberty Blades": "??",
        "Metro Sparks": "?",
        "Atlantic Wolves": "??",
        "Capital Foxes": "??",
        "Bay Comets": "??",
        "Prairie Storm": "???",
        "Iron Rangers": "???",
        "Lake Vipers": "??",
        "Granite Bears": "??",
        "Steel River": "??",
        "Red Hawks": "??",
        "Desert Fire": "??",
        "Pacific Tide": "??",
        "Summit Eagles": "??",
        "Canyon Coyotes": "??",
        "Emerald Orcas": "??",
        "Golden Peaks": "??",
    }
    divisions: dict[str, list[tuple[str, float, float, float, str, str]]] = {
        "North": [
            ("Aurora", 0.30, 0.15, 0.08, "#4cc9f0", "#bdefff"),
            ("Icebreakers", 0.22, 0.25, 0.12, "#1d4ed8", "#dbeafe"),
            ("Timberwolves", 0.18, 0.28, 0.16, "#166534", "#d4af37"),
            ("Glaciers", 0.12, 0.32, 0.10, "#0f766e", "#ccfbf1"),
            ("Polar Caps", 0.26, 0.14, 0.20, "#0c2340", "#c0c0c0"),
            ("Silver Pines", 0.16, 0.24, 0.18, "#1f6f50", "#c0c0c0"),
        ],
        "East": [
            ("Harbor Kings", 0.28, 0.10, 0.14, "#5b2c83", "#d8c7a0"),
            ("Liberty Blades", 0.24, 0.22, 0.12, "#c1121f", "#1d4ed8"),
            ("Metro Sparks", 0.34, 0.08, 0.10, "#f97316", "#ffedd5"),
            ("Atlantic Wolves", 0.20, 0.20, 0.16, "#4338ca", "#e0e7ff"),
            ("Capital Foxes", 0.14, 0.30, 0.15, "#b45309", "#fef3c7"),
            ("Bay Comets", 0.25, 0.16, 0.13, "#0369a1", "#e0f2fe"),
        ],
        "Central": [
            ("Prairie Storm", 0.22, 0.20, 0.22, "#0891b2", "#cffafe"),
            ("Iron Rangers", 0.18, 0.30, 0.24, "#1f2937", "#c1121f"),
            ("Lake Vipers", 0.26, 0.16, 0.18, "#0f766e", "#ccfbf1"),
            ("Granite Bears", 0.14, 0.28, 0.25, "#7f1d1d", "#fee2e2"),
            ("Steel River", 0.20, 0.24, 0.20, "#334155", "#e2e8f0"),
            ("Red Hawks", 0.30, 0.12, 0.18, "#dc2626", "#fee2e2"),
        ],
        "West": [
            ("Desert Fire", 0.32, 0.08, 0.12, "#ea580c", "#ffedd5"),
            ("Pacific Tide", 0.24, 0.18, 0.16, "#2563eb", "#dbeafe"),
            ("Summit Eagles", 0.21, 0.22, 0.19, "#0f766e", "#ccfbf1"),
            ("Canyon Coyotes", 0.19, 0.24, 0.21, "#92400e", "#ffedd5"),
            ("Emerald Orcas", 0.27, 0.14, 0.14, "#059669", "#d1fae5"),
            ("Golden Peaks", 0.23, 0.20, 0.17, "#ca8a04", "#fef9c3"),
        ],
    }

    name_gen = NameGenerator(seed=7)
    teams: list[Team] = []
    for division, entries in divisions.items():
        conference = "Eastern" if division in {"East", "Central"} else "Western"
        for team_name, offense, defense, physical, primary, secondary in entries:
            roster = _make_roster(team_name, offense, defense, physical, name_gen)
            minor_roster = _make_minor_roster(team_name, offense, defense, physical, name_gen)
            arena_rng = random.Random(f"arena:{team_name}")
            teams.append(
                Team(
                    name=team_name,
                    division=division,
                    conference=conference,
                    logo=team_logos.get(team_name, "TM"),
                    primary_color=primary,
                    secondary_color=secondary,
                    arena_capacity=arena_rng.randint(11000, 21500),
                    roster=roster,
                    minor_roster=minor_roster,
                )
            )
    return teams


def format_standings(simulator: LeagueSimulator) -> str:
    lines = ["Pos Team             Div      Pts  W  L OTL  GF  GA  GD"]
    for idx, rec in enumerate(simulator.get_standings(), start=1):
        lines.append(
            f"{idx:>3} {rec.team.name:<16} {rec.team.division:<8} {rec.points:>3} {rec.wins:>2} {rec.losses:>2}"
            f" {rec.ot_losses:>3} {rec.goals_for:>3} {rec.goals_against:>3} {rec.goal_diff:>3}"
        )
    return "\n".join(lines)


def format_player_stats(players: Iterable[Player], title: str, limit: int = 20) -> str:
    lines = [title, "Team             Player                Age Pos GP  G  A  P InjOut"]
    for player in list(players)[:limit]:
        lines.append(
            f"{player.team_name:<16} {player.name:<20} {player.age:>3} {player.position:<3} {player.games_played:>2}"
            f" {player.goals:>2} {player.assists:>2} {player.points:>2} {player.injured_games_remaining:>6}"
        )
    return "\n".join(lines)


