from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar
from uuid import uuid4

FORWARD_POSITIONS = {"C", "LW", "RW"}
DEFENSE_POSITIONS = {"D"}
GOALIE_POSITIONS = {"G"}


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
    player_id: str = field(default_factory=lambda: uuid4().hex)
    age: int = 24
    prime_age: int = 27
    games_played: int = 0
    goals: int = 0
    assists: int = 0
    injuries: int = 0
    injured_games_remaining: int = 0
    games_missed_injury: int = 0
    goalie_games: int = 0
    goalie_wins: int = 0
    goalie_losses: int = 0
    goalie_ot_losses: int = 0
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
    career_seasons: list[dict[str, object]] = field(default_factory=list)

    @property
    def points(self) -> int:
        return self.goals + self.assists

    @property
    def is_injured(self) -> bool:
        return self.injured_games_remaining > 0

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
    roster: list[Player] = field(default_factory=list)
    dressed_player_names: set[str] = field(default_factory=set)
    starting_goalie_name: str | None = None
    coach_name: str = "Staff Coach"
    coach_rating: float = 3.0
    coach_style: str = "balanced"
    coach_offense: float = 3.0
    coach_defense: float = 3.0
    coach_goalie_dev: float = 3.0
    coach_tenure_seasons: int = 0
    coach_changes_recent: float = 0.0
    coach_honeymoon_games_remaining: int = 0

    MAX_ROSTER_SIZE: ClassVar[int] = 22
    DRESSED_ROSTER_SIZE: ClassVar[int] = 20
    DRESSED_FORWARDS: ClassVar[int] = 12
    DRESSED_DEFENSE: ClassVar[int] = 6
    DRESSED_GOALIES: ClassVar[int] = 2

    def __post_init__(self) -> None:
        if len(self.roster) > self.MAX_ROSTER_SIZE:
            raise ValueError(f"{self.name} roster exceeds max of {self.MAX_ROSTER_SIZE}.")
        if not self.dressed_player_names:
            self.set_default_lineup()

    def _lineup_noise(self, seed_text: str) -> float:
        token = sum(ord(ch) for ch in seed_text)
        return ((token % 37) - 18) / 18.0

    def _healthy(self, players: list[Player]) -> list[Player]:
        return [p for p in players if not p.is_injured]

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
        if player is None or player.position != "G" or player.is_injured or not self.is_dressed(player):
            return False
        self.starting_goalie_name = player.name
        return True

    def is_dressed(self, player: Player) -> bool:
        return player.name in self.dressed_player_names

    def dressed_players(self) -> list[Player]:
        return [p for p in self.roster if p.name in self.dressed_player_names and not p.is_injured]

    def dressed_skaters(self) -> list[Player]:
        return [p for p in self.dressed_players() if p.position != "G"]

    def dressed_forwards(self) -> list[Player]:
        return [p for p in self.dressed_players() if p.position in FORWARD_POSITIONS]

    def dressed_defense(self) -> list[Player]:
        return [p for p in self.dressed_players() if p.position in DEFENSE_POSITIONS]

    def dressed_goalies(self) -> list[Player]:
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

        selected = (
            forwards[: self.DRESSED_FORWARDS]
            + defense[: self.DRESSED_DEFENSE]
            + goalies[: self.DRESSED_GOALIES]
        )
        self.dressed_player_names = {p.name for p in selected}

    def can_dress_player(self, player: Player) -> bool:
        if player.is_injured:
            return False
        if self.is_dressed(player):
            return True
        if len(self.dressed_players()) >= self.DRESSED_ROSTER_SIZE:
            return False
        return True

    def toggle_dressed_status(self, player_name: str) -> bool:
        player = self._player_by_name(player_name)
        if player is None or player.is_injured:
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
        for result in reversed(self.recent_results[:-1]):
            if result != last:
                break
            count += 1
        return f"{last}{count}"

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
        if len(self.recent_results) > 10:
            self.recent_results = self.recent_results[-10:]
