from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar
from uuid import uuid4

FORWARD_POSITIONS = {"C", "LW", "RW"}
DEFENSE_POSITIONS = {"D"}
GOALIE_POSITIONS = {"G"}
FORWARD_LINE_SLOTS = (
    "LW1", "C1", "RW1",
    "LW2", "C2", "RW2",
    "LW3", "C3", "RW3",
    "LW4", "C4", "RW4",
)
DEFENSE_LINE_SLOTS = ("LD1", "RD1", "LD2", "RD2", "LD3", "RD3")
GOALIE_LINE_SLOTS = ("G1", "G2")
ALL_LINE_SLOTS = FORWARD_LINE_SLOTS + DEFENSE_LINE_SLOTS + GOALIE_LINE_SLOTS


@dataclass(slots=True)
class Player:
    team_name: str
    name: str
    position: str
    shooting: float
    playmaking: float
    defense: float
    goaltending: float
    physical: float
    durability: float
    jersey_number: int | None = None
    birth_country: str = "Canada"
    birth_country_code: str = "CA"
    player_id: str = field(default_factory=lambda: uuid4().hex)
    age: int = 24
    prime_age: int = 27
    games_played: int = 0
    goals: int = 0
    assists: int = 0
    injuries: int = 0
    injured_games_remaining: int = 0
    games_missed_injury: int = 0
    injury_type: str = ""
    injury_status: str = "Healthy"
    dtd_play_today: bool = False
    temporary_replacement_for: str = ""
    goalie_games: int = 0
    goalie_wins: int = 0
    goalie_losses: int = 0
    goalie_ot_losses: int = 0
    goalie_shutouts: int = 0
    shots_against: int = 0
    saves: int = 0
    goals_against: int = 0
    draft_season: int | None = None
    draft_round: int | None = None
    draft_overall: int | None = None
    draft_team: str | None = None
    prospect_tier: str = "NHL"
    seasons_to_nhl: int = 0
    prospect_potential: float = 0.5
    prospect_boom_chance: float = 0.08
    prospect_bust_chance: float = 0.10
    prospect_resolved: bool = True
    contract_years_left: int = 2
    cap_hit: float = 1.2
    contract_type: str = "entry"
    is_rfa: bool = True
    free_agent_origin_team: str = ""
    career_seasons: list[dict[str, object]] = field(default_factory=list)

    @property
    def points(self) -> int:
        return self.goals + self.assists

    @property
    def is_injured(self) -> bool:
        return self.injured_games_remaining > 0 and self.injury_status != "DTD"

    @property
    def is_dtd(self) -> bool:
        return self.injured_games_remaining > 0 and self.injury_status == "DTD"

    @property
    def can_play_today(self) -> bool:
        if self.injured_games_remaining <= 0:
            return True
        if self.injury_status == "DTD":
            return self.dtd_play_today
        return False

    @property
    def scoring_weight(self) -> float:
        return max(0.1, self.shooting * 0.62 + self.playmaking * 0.38)

    @property
    def save_pct(self) -> float:
        if self.shots_against <= 0:
            return 0.0
        return self.saves / self.shots_against

    @property
    def gaa(self) -> float:
        if self.goalie_games <= 0:
            return 0.0
        return self.goals_against / self.goalie_games


@dataclass(slots=True)
class Team:
    name: str
    division: str = "Independent"
    conference: str = "Independent"
    logo: str = "🏒"
    primary_color: str = "#1f3a93"
    secondary_color: str = "#d7e1f5"
    arena_capacity: int = 16000
    roster: list[Player] = field(default_factory=list)
    minor_roster: list[Player] = field(default_factory=list)
    dressed_player_names: set[str] = field(default_factory=set)
    line_assignments: dict[str, str] = field(default_factory=dict)
    starting_goalie_name: str | None = None
    coach_name: str = "Staff Coach"
    coach_age: int = 52
    coach_rating: float = 3.0
    coach_style: str = "balanced"
    coach_offense: float = 3.0
    coach_defense: float = 3.0
    coach_goalie_dev: float = 3.0
    coach_tenure_seasons: int = 0
    coach_changes_recent: float = 0.0
    coach_honeymoon_games_remaining: int = 0
    captain_name: str = ""
    assistant_names: list[str] = field(default_factory=list)
    retired_numbers: list[dict[str, object]] = field(default_factory=list)

    MAX_ROSTER_SIZE: ClassVar[int] = 22
    MIN_MINOR_ROSTER_SIZE: ClassVar[int] = 10
    DRESSED_ROSTER_SIZE: ClassVar[int] = 20
    DRESSED_FORWARDS: ClassVar[int] = 12
    DRESSED_DEFENSE: ClassVar[int] = 6
    DRESSED_GOALIES: ClassVar[int] = 2

    def __post_init__(self) -> None:
        active_count = len([p for p in self.roster if not p.is_injured])
        if active_count > self.MAX_ROSTER_SIZE:
            raise ValueError(f"{self.name} active roster exceeds max of {self.MAX_ROSTER_SIZE}.")
        if self.line_assignments:
            self._refresh_dressed_from_assignments()
        elif not self.dressed_player_names:
            self.set_default_lineup()

    def _slot_expected_position(self, slot: str) -> str:
        if slot.startswith("LW"):
            return "LW"
        if slot.startswith("C"):
            return "C"
        if slot.startswith("RW"):
            return "RW"
        if slot.startswith("LD") or slot.startswith("RD"):
            return "D"
        if slot.startswith("G"):
            return "G"
        return ""

    def _overall_skater(self, player: Player) -> float:
        return player.shooting * 0.38 + player.playmaking * 0.32 + player.defense * 0.22 + player.physical * 0.08

    def _refresh_dressed_from_assignments(self) -> None:
        names = {name for name in self.line_assignments.values() if name}
        if names:
            self.dressed_player_names = names

    def _lineup_noise(self, seed_text: str) -> float:
        token = sum(ord(ch) for ch in seed_text)
        return ((token % 37) - 18) / 18.0

    def _healthy(self, players: list[Player]) -> list[Player]:
        return [p for p in players if p.can_play_today]

    def _player_by_name(self, player_name: str) -> Player | None:
        for player in self.roster:
            if player.name == player_name:
                return player
        return None

    def set_starting_goalie(self, player_name: str | None) -> bool:
        if not player_name:
            self.starting_goalie_name = None
            return True
        player = self._player_by_name(player_name)
        if player is None or player.position != "G" or not player.can_play_today or not self.is_dressed(player):
            return False
        self.starting_goalie_name = player.name
        return True

    def is_dressed(self, player: Player) -> bool:
        return player.name in self.dressed_player_names

    def dressed_players(self) -> list[Player]:
        return [p for p in self.roster if p.name in self.dressed_player_names and p.can_play_today]

    def dressed_skaters(self) -> list[Player]:
        return [p for p in self.dressed_players() if p.position != "G"]

    def dressed_forwards(self) -> list[Player]:
        used: set[str] = set()
        out: list[Player] = []
        for slot in FORWARD_LINE_SLOTS:
            name = self.line_assignments.get(slot, "")
            if not name or name in used:
                continue
            player = self._player_by_name(name)
            if player is None or not player.can_play_today:
                continue
            out.append(player)
            used.add(name)
        if out:
            return out
        return [p for p in self.dressed_players() if p.position in FORWARD_POSITIONS]

    def dressed_defense(self) -> list[Player]:
        used: set[str] = set()
        out: list[Player] = []
        for slot in DEFENSE_LINE_SLOTS:
            name = self.line_assignments.get(slot, "")
            if not name or name in used:
                continue
            player = self._player_by_name(name)
            if player is None or not player.can_play_today:
                continue
            out.append(player)
            used.add(name)
        if out:
            return out
        return [p for p in self.dressed_players() if p.position in DEFENSE_POSITIONS]

    def dressed_goalies(self) -> list[Player]:
        used: set[str] = set()
        out: list[Player] = []
        for slot in GOALIE_LINE_SLOTS:
            name = self.line_assignments.get(slot, "")
            if not name or name in used:
                continue
            player = self._player_by_name(name)
            if player is None or not player.can_play_today:
                continue
            out.append(player)
            used.add(name)
        if out:
            return out
        return [p for p in self.dressed_players() if p.position in GOALIE_POSITIONS]

    def active_players(self) -> list[Player]:
        return self._healthy(self.roster)

    def active_skaters(self) -> list[Player]:
        return [p for p in self.active_players() if p.position in FORWARD_POSITIONS or p.position in DEFENSE_POSITIONS]

    def active_forwards(self) -> list[Player]:
        return [p for p in self.active_players() if p.position in FORWARD_POSITIONS]

    def active_defense(self) -> list[Player]:
        return [p for p in self.active_players() if p.position in DEFENSE_POSITIONS]

    def active_goalies(self) -> list[Player]:
        return [p for p in self.active_players() if p.position in GOALIE_POSITIONS]

    def set_default_lineup(self) -> None:
        healthy = self.active_players()
        forwards = [p for p in healthy if p.position in FORWARD_POSITIONS]
        defense = [p for p in healthy if p.position in DEFENSE_POSITIONS]
        goalies = [p for p in healthy if p.position in GOALIE_POSITIONS]

        coach_quality = max(0.0, min(1.0, (self.coach_rating - 2.0) / 3.0))
        noise_scale = 0.55 * (1.0 - coach_quality)
        style = self.coach_style if self.coach_style in {"aggressive", "balanced", "defensive"} else "balanced"

        if style == "aggressive":
            forwards.sort(
                key=lambda p: (
                    p.shooting * 0.56
                    + p.playmaking * 0.30
                    + p.defense * 0.10
                    + p.physical * 0.04
                    + self._lineup_noise(f"F:{p.player_id}") * noise_scale
                ),
                reverse=True,
            )
            defense.sort(
                key=lambda p: (
                    p.playmaking * 0.45
                    + p.defense * 0.36
                    + p.shooting * 0.15
                    + p.physical * 0.04
                    + self._lineup_noise(f"D:{p.player_id}") * noise_scale
                ),
                reverse=True,
            )
        elif style == "defensive":
            forwards.sort(
                key=lambda p: (
                    p.defense * 0.44
                    + p.playmaking * 0.28
                    + p.shooting * 0.20
                    + p.physical * 0.08
                    + self._lineup_noise(f"F:{p.player_id}") * noise_scale
                ),
                reverse=True,
            )
            defense.sort(
                key=lambda p: (
                    p.defense * 0.56
                    + p.playmaking * 0.20
                    + p.physical * 0.16
                    + p.shooting * 0.08
                    + self._lineup_noise(f"D:{p.player_id}") * noise_scale
                ),
                reverse=True,
            )
        else:
            forwards.sort(
                key=lambda p: (
                    p.shooting * 0.40
                    + p.playmaking * 0.32
                    + p.defense * 0.20
                    + p.physical * 0.08
                    + self._lineup_noise(f"F:{p.player_id}") * noise_scale
                ),
                reverse=True,
            )
            defense.sort(
                key=lambda p: (
                    p.defense * 0.44
                    + p.playmaking * 0.28
                    + p.shooting * 0.12
                    + p.physical * 0.16
                    + self._lineup_noise(f"D:{p.player_id}") * noise_scale
                ),
                reverse=True,
            )
        goalies.sort(
            key=lambda p: (
                p.goaltending
                + self._lineup_noise(f"G:{p.player_id}") * (noise_scale * 0.55)
            ),
            reverse=True,
        )

        healthy_skaters = sorted(
            [p for p in healthy if p.position != "G"],
            key=lambda p: self._overall_skater(p),
            reverse=True,
        )
        healthy_goalies = sorted(
            goalies,
            key=lambda p: p.goaltending,
            reverse=True,
        )

        assignments: dict[str, str] = {}
        used: set[str] = set()

        def pick_best(
            preferred: list[Player],
            fallback: list[Player],
        ) -> Player | None:
            for pool in (preferred, fallback):
                for candidate in pool:
                    if candidate.name not in used and candidate.can_play_today:
                        return candidate
            return None

        for slot in FORWARD_LINE_SLOTS:
            expected = self._slot_expected_position(slot)
            preferred = [p for p in forwards if p.position == expected]
            chosen = pick_best(preferred, forwards)
            if chosen is None:
                chosen = pick_best([], healthy_skaters)
            if chosen is not None:
                assignments[slot] = chosen.name
                used.add(chosen.name)

        for slot in DEFENSE_LINE_SLOTS:
            preferred = defense
            chosen = pick_best(preferred, healthy_skaters)
            if chosen is not None:
                assignments[slot] = chosen.name
                used.add(chosen.name)

        for slot in GOALIE_LINE_SLOTS:
            chosen = pick_best(healthy_goalies, healthy_skaters)
            if chosen is not None:
                assignments[slot] = chosen.name
                used.add(chosen.name)

        self.line_assignments = assignments
        self._refresh_dressed_from_assignments()
        g1_name = self.line_assignments.get("G1")
        g1 = self._player_by_name(g1_name) if g1_name else None
        self.starting_goalie_name = g1.name if g1 is not None and g1.position == "G" else None

    def set_line_assignments(self, requested: dict[str, str]) -> None:
        self.set_default_lineup()
        auto_assignments = dict(self.line_assignments)
        healthy = [p for p in self.active_players()]
        healthy_sorted = sorted(
            healthy,
            key=lambda p: (p.goaltending if p.position == "G" else self._overall_skater(p)),
            reverse=True,
        )
        final: dict[str, str] = {}
        used: set[str] = set()
        requested = requested or {}

        for slot in ALL_LINE_SLOTS:
            chosen_name = ""
            req_name = str(requested.get(slot, "")).strip()
            if req_name:
                req_player = self._player_by_name(req_name)
                if req_player is not None and req_player.can_play_today and req_player.name not in used:
                    chosen_name = req_player.name
            if not chosen_name:
                auto_name = str(auto_assignments.get(slot, "")).strip()
                auto_player = self._player_by_name(auto_name) if auto_name else None
                if auto_player is not None and auto_player.can_play_today and auto_player.name not in used:
                    chosen_name = auto_player.name
            if not chosen_name:
                for p in healthy_sorted:
                    if p.name not in used:
                        chosen_name = p.name
                        break
            if chosen_name:
                final[slot] = chosen_name
                used.add(chosen_name)

        self.line_assignments = final
        self._refresh_dressed_from_assignments()
        g1_name = self.line_assignments.get("G1")
        g1 = self._player_by_name(g1_name) if g1_name else None
        self.starting_goalie_name = g1.name if g1 is not None and g1.position == "G" else None

    def lineup_position_penalty(self) -> float:
        penalty = 0.0
        for slot in ALL_LINE_SLOTS:
            name = self.line_assignments.get(slot, "")
            if not name:
                penalty += 0.08
                continue
            player = self._player_by_name(name)
            if player is None or not player.can_play_today:
                penalty += 0.08
                continue
            expected = self._slot_expected_position(slot)
            actual = player.position
            if expected == actual:
                continue
            if expected in FORWARD_POSITIONS and actual in FORWARD_POSITIONS:
                penalty += 0.03
            elif expected == "D" and actual in FORWARD_POSITIONS:
                penalty += 0.07
            elif expected in FORWARD_POSITIONS and actual == "D":
                penalty += 0.08
            elif expected == "G" and actual != "G":
                penalty += 0.25
            elif expected != "G" and actual == "G":
                penalty += 0.18
            else:
                penalty += 0.09
        return min(0.40, penalty)

    def can_dress_player(self, player: Player) -> bool:
        if not player.can_play_today:
            return False
        if self.is_dressed(player):
            return True
        if len(self.dressed_players()) >= self.DRESSED_ROSTER_SIZE:
            return False
        return True

    def toggle_dressed_status(self, player_name: str) -> bool:
        player = self._player_by_name(player_name)
        if player is None or not player.can_play_today:
            return False

        if player.name in self.dressed_player_names:
            position_group = (
                self.dressed_forwards()
                if player.position in FORWARD_POSITIONS
                else self.dressed_defense()
                if player.position in DEFENSE_POSITIONS
                else self.dressed_goalies()
            )
            minimum = (
                self.DRESSED_FORWARDS
                if player.position in FORWARD_POSITIONS
                else self.DRESSED_DEFENSE
                if player.position in DEFENSE_POSITIONS
                else self.DRESSED_GOALIES
            )
            if len(position_group) <= minimum:
                return False
            self.dressed_player_names.remove(player.name)
            return True

        if len(self.dressed_players()) >= self.DRESSED_ROSTER_SIZE:
            return False
        self.dressed_player_names.add(player.name)
        return True


@dataclass(slots=True)
class TeamRecord:
    team: Team
    wins: int = 0
    losses: int = 0
    ot_losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    home_wins: int = 0
    home_losses: int = 0
    home_ot_losses: int = 0
    away_wins: int = 0
    away_losses: int = 0
    away_ot_losses: int = 0
    pp_goals: int = 0
    pp_chances: int = 0
    pk_goals_against: int = 0
    pk_chances_against: int = 0
    recent_results: list[str] = field(default_factory=list)

    @property
    def points(self) -> int:
        return self.wins * 2 + self.ot_losses

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def games_played(self) -> int:
        return self.wins + self.losses + self.ot_losses

    @property
    def point_pct(self) -> float:
        gp = self.games_played
        if gp <= 0:
            return 0.0
        return self.points / (gp * 2)

    @property
    def home_record(self) -> str:
        return f"{self.home_wins}-{self.home_losses}-{self.home_ot_losses}"

    @property
    def away_record(self) -> str:
        return f"{self.away_wins}-{self.away_losses}-{self.away_ot_losses}"

    @property
    def last10(self) -> str:
        sample = self.recent_results[-10:]
        w = sample.count("W")
        l = sample.count("L")
        otl = sample.count("OTL")
        return f"{w}-{l}-{otl}"

    @property
    def streak(self) -> str:
        if not self.recent_results:
            return "-"
        last = self.recent_results[-1]
        count = 1
        if last == "W":
            target_set = {"W"}
            label = "W"
        else:
            # Match fan expectation: any consecutive non-win run is a losing streak.
            target_set = {"L", "OTL"}
            label = "L"
        for result in reversed(self.recent_results[:-1]):
            if result not in target_set:
                break
            count += 1
        return f"{label}{count}"

    @property
    def pp_pct(self) -> float:
        if self.pp_chances <= 0:
            return 0.0
        return self.pp_goals / self.pp_chances

    @property
    def pk_pct(self) -> float:
        if self.pk_chances_against <= 0:
            return 0.0
        killed = max(0, self.pk_chances_against - self.pk_goals_against)
        return killed / self.pk_chances_against

    def register_game(
        self,
        goals_for: int,
        goals_against: int,
        overtime: bool,
        is_home: bool,
        pp_goals: int = 0,
        pp_chances: int = 0,
        pk_goals_against: int = 0,
        pk_chances_against: int = 0,
    ) -> None:
        self.goals_for += goals_for
        self.goals_against += goals_against
        self.pp_goals += max(0, pp_goals)
        self.pp_chances += max(0, pp_chances)
        self.pk_goals_against += max(0, pk_goals_against)
        self.pk_chances_against += max(0, pk_chances_against)
        if goals_for > goals_against:
            self.wins += 1
            self.recent_results.append("W")
            if is_home:
                self.home_wins += 1
            else:
                self.away_wins += 1
        elif overtime:
            self.ot_losses += 1
            self.recent_results.append("OTL")
            if is_home:
                self.home_ot_losses += 1
            else:
                self.away_ot_losses += 1
        else:
            self.losses += 1
            self.recent_results.append("L")
            if is_home:
                self.home_losses += 1
            else:
                self.away_losses += 1
