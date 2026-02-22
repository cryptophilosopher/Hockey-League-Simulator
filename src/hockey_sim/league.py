from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import random
import shutil
from typing import Any

from .config import PLAYER_BIRTH_COUNTRIES
from .engine import GameResult, STRATEGY_EFFECTS, simulate_game
from .models import DEFENSE_POSITIONS, FORWARD_POSITIONS, GOALIE_POSITIONS, Player, Team, TeamRecord
from .names import COACH_FIRST_NAMES, COACH_LAST_NAMES, NameGenerator
from .schedule import build_round_robin_days


@dataclass(slots=True)
class LeagueResult:
    standings: list[TeamRecord]


class LeagueSimulator:
    SAVE_VERSION = 2
    DRAFT_FOCUS_OPTIONS = ("auto", "F", "C", "LW", "RW", "D", "G")
    TEAM_NEED_KEYS = ("top6_f", "top4_d", "starter_g", "depth_f", "depth_d", "cap_relief")
    COACH_FIRST_NAMES = COACH_FIRST_NAMES
    COACH_LAST_NAMES = COACH_LAST_NAMES
    def __init__(
        self,
        teams: list[Team],
        games_per_matchup: int = 2,
        seed: int | None = None,
        history_path: str | None = None,
        career_history_path: str | None = None,
        hall_of_fame_path: str | None = None,
        state_path: str | None = None,
        prime_age_min: int = 27,
        prime_age_max: int = 28,
    ) -> None:
        self.games_per_matchup = games_per_matchup
        self._rng = random.Random(seed)
        self.state_path = Path(state_path or "league_state.json")
        self.last_load_error: str = ""
        loaded_state = self._load_state()
        loaded_teams = self._deserialize_teams(loaded_state.get("teams", [])) if loaded_state else []
        self.teams = loaded_teams if loaded_teams else teams
        self.free_agents: list[Player] = []
        self._name_generator = NameGenerator(seed=seed)
        self._name_generator.reserve([p.name for t in self.teams for p in [*t.roster, *t.minor_roster]])
        self.season_number = int(loaded_state.get("season_number", 1)) if loaded_state else 1
        self.prime_age_min = min(prime_age_min, prime_age_max)
        self.prime_age_max = max(prime_age_min, prime_age_max)
        self._ensure_minor_roster_depth()
        self._migrate_legacy_birth_countries()
        self._migrate_team_branding()
        self._ensure_team_coaches()
        self._ensure_team_leadership()
        self._ensure_team_player_numbers()
        self._ensure_player_contracts()
        self.history_path = Path(history_path or "season_history.json")
        self.career_history_path = Path(career_history_path or "career_history.json")
        self.hall_of_fame_path = Path(hall_of_fame_path or "hall_of_fame.json")
        self.season_history: list[dict[str, object]] = self._load_history()
        self.career_history: dict[str, list[dict[str, object]]] = self._load_career_history()
        self.hall_of_fame: list[dict[str, object]] = self._load_hall_of_fame()
        self._apply_career_history_to_rosters()
        if self.season_history and not loaded_state:
            self.season_number = int(self.season_history[-1]["season"]) + 1

        self._records = self._deserialize_records(loaded_state.get("records", {})) if loaded_teams else {
            team.name: TeamRecord(team=team) for team in self.teams
        }
        self._season_days = build_round_robin_days(self.teams, self.games_per_matchup)
        if loaded_teams:
            saved_day = int(loaded_state.get("day_index", 0))
            self._day_index = max(0, min(saved_day, len(self._season_days)))
            raw_free_agents = loaded_state.get("free_agents", [])
            self.free_agents = (
                [self._deserialize_player(p) for p in raw_free_agents if isinstance(p, dict)]
                if isinstance(raw_free_agents, list)
                else []
            )
            raw_retired = loaded_state.get("last_offseason_retired", [])
            self.last_offseason_retired = list(raw_retired) if isinstance(raw_retired, list) else []
            raw_retired_numbers = loaded_state.get("last_offseason_retired_numbers", [])
            self.last_offseason_retired_numbers = (
                [row for row in raw_retired_numbers if isinstance(row, dict)]
                if isinstance(raw_retired_numbers, list)
                else []
            )
            raw_drafted = loaded_state.get("last_offseason_drafted", {})
            self.last_offseason_drafted = dict(raw_drafted) if isinstance(raw_drafted, dict) else {}
            raw_drafted_details = loaded_state.get("last_offseason_drafted_details", {})
            self.last_offseason_drafted_details = dict(raw_drafted_details) if isinstance(raw_drafted_details, dict) else {}
            raw_focus = loaded_state.get("draft_focus_by_team", {})
            self.draft_focus_by_team = (
                {str(k): str(v).lower() for k, v in raw_focus.items() if isinstance(k, str)}
                if isinstance(raw_focus, dict)
                else {}
            )
            raw_team_needs = loaded_state.get("team_needs_by_team", {})
            self.team_needs_by_team = (
                self._deserialize_team_needs_config(raw_team_needs)
                if isinstance(raw_team_needs, dict)
                else {}
            )
        else:
            self._day_index = 0
            self.free_agents = []
            self.last_offseason_retired = []
            self.last_offseason_retired_numbers = []
            self.last_offseason_drafted = {}
            self.last_offseason_drafted_details = {}
            self.draft_focus_by_team = {}
            self.team_needs_by_team = {}
        raw_pending_playoffs = loaded_state.get("pending_playoffs")
        self.pending_playoffs: dict[str, object] | None = raw_pending_playoffs if isinstance(raw_pending_playoffs, dict) else None
        raw_pending_days = loaded_state.get("pending_playoff_days")
        self.pending_playoff_days: list[dict[str, object]] = (
            [d for d in raw_pending_days if isinstance(d, dict)] if isinstance(raw_pending_days, list) else []
        )
        raw_pending_idx = loaded_state.get("pending_playoff_day_index", 0)
        try:
            self.pending_playoff_day_index = int(raw_pending_idx)
        except (TypeError, ValueError):
            self.pending_playoff_day_index = 0
        self.pending_playoff_day_index = max(0, min(self.pending_playoff_day_index, len(self.pending_playoff_days)))
        self._normalize_team_needs_config()
        self._save_state()

    @property
    def total_days(self) -> int:
        return len(self._season_days)

    @property
    def current_day(self) -> int:
        total = len(self._season_days)
        if total <= 0:
            return 1
        return max(1, min(self._day_index + 1, total))

    @property
    def strategies(self) -> list[str]:
        return list(STRATEGY_EFFECTS.keys())

    def _load_history(self) -> list[dict[str, object]]:
        if not self.history_path.exists():
            return []
        try:
            raw = json.loads(self.history_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                version = int(raw.get("save_version", 1) or 1)
                if version > self.SAVE_VERSION:
                    self.last_load_error = (
                        f"Unsupported season history version {version}; app supports up to {self.SAVE_VERSION}."
                    )
                    return []
                payload = raw.get("season_history", [])
                if isinstance(payload, list):
                    return payload
                self.last_load_error = "Season history payload is invalid; starting with empty history."
                return []
            if isinstance(raw, list):
                return raw
            self.last_load_error = "Season history file has invalid format; starting with empty history."
        except (json.JSONDecodeError, OSError) as exc:
            self.last_load_error = f"Failed to load season history ({exc}); starting with empty history."
            return []
        return []

    def _save_history(self) -> None:
        payload = {
            "save_version": self.SAVE_VERSION,
            "season_history": self.season_history,
        }
        self._write_json_with_backup(self.history_path, payload)

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                version = int(raw.get("save_version", 1) or 1)
                if version > self.SAVE_VERSION:
                    self.last_load_error = (
                        f"Unsupported league state version {version}; app supports up to {self.SAVE_VERSION}."
                    )
                    return {}
                return raw
            self.last_load_error = "League state file has invalid format; starting with defaults."
        except (json.JSONDecodeError, OSError) as exc:
            self.last_load_error = f"Failed to load league state ({exc}); starting with defaults."
            return {}
        return {}

    def _save_state(self) -> None:
        state = {
            "save_version": self.SAVE_VERSION,
            "season_number": self.season_number,
            "day_index": self._day_index,
            "teams": [self._serialize_team(team) for team in self.teams],
            "free_agents": [self._serialize_player(player) for player in self.free_agents],
            "records": self._serialize_records(),
            "last_offseason_retired": self.last_offseason_retired,
            "last_offseason_retired_numbers": self.last_offseason_retired_numbers,
            "last_offseason_drafted": self.last_offseason_drafted,
            "last_offseason_drafted_details": self.last_offseason_drafted_details,
            "draft_focus_by_team": self.draft_focus_by_team,
            "team_needs_by_team": self.team_needs_by_team,
            "pending_playoffs": self.pending_playoffs,
            "pending_playoff_days": self.pending_playoff_days,
            "pending_playoff_day_index": self.pending_playoff_day_index,
        }
        # Routine autosave is called frequently during sim; skip per-save backup copy for speed.
        self._write_json_with_backup(self.state_path, state, with_backup=False)

    def _normalize_need_scores(self, raw_scores: Any) -> dict[str, float]:
        scores: dict[str, float] = {}
        if not isinstance(raw_scores, dict):
            return scores
        for key in self.TEAM_NEED_KEYS:
            try:
                val = float(raw_scores.get(key, 0.0))
            except (TypeError, ValueError):
                val = 0.0
            scores[key] = round(max(0.0, min(1.0, val)), 3)
        return scores

    def _deserialize_team_needs_config(self, raw: dict[str, Any]) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        valid_names = {team.name for team in self.teams}
        for team_name, entry in raw.items():
            if not isinstance(team_name, str) or team_name not in valid_names or not isinstance(entry, dict):
                continue
            mode = str(entry.get("mode", "auto")).lower()
            if mode not in {"auto", "manual"}:
                mode = "auto"
            parsed: dict[str, object] = {"mode": mode}
            if mode == "manual":
                parsed["scores"] = self._normalize_need_scores(entry.get("scores", {}))
            out[team_name] = parsed
        return out

    def _normalize_team_needs_config(self) -> None:
        valid_names = {team.name for team in self.teams}
        current = self._deserialize_team_needs_config(self.team_needs_by_team)
        self.team_needs_by_team = {k: v for k, v in current.items() if k in valid_names}

    def _load_career_history(self) -> dict[str, list[dict[str, object]]]:
        if not self.career_history_path.exists():
            return {}
        try:
            raw = json.loads(self.career_history_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                version = int(raw.get("save_version", 1) or 1)
                if version > self.SAVE_VERSION:
                    self.last_load_error = (
                        f"Unsupported career history version {version}; app supports up to {self.SAVE_VERSION}."
                    )
                    return {}
                payload = raw.get("career_history", raw)
                if not isinstance(payload, dict):
                    self.last_load_error = "Career history payload is invalid; starting empty."
                    return {}
                out: dict[str, list[dict[str, object]]] = {}
                for player_name, seasons in payload.items():
                    if isinstance(player_name, str) and isinstance(seasons, list):
                        out[player_name] = [entry for entry in seasons if isinstance(entry, dict)]
                return out
            self.last_load_error = "Career history file has invalid format; starting empty."
        except (json.JSONDecodeError, OSError) as exc:
            self.last_load_error = f"Failed to load career history ({exc}); starting empty."
            return {}
        return {}

    def _save_career_history(self) -> None:
        payload = {
            "save_version": self.SAVE_VERSION,
            "career_history": self.career_history,
        }
        self._write_json_with_backup(self.career_history_path, payload)

    def _load_hall_of_fame(self) -> list[dict[str, object]]:
        if not self.hall_of_fame_path.exists():
            return []
        try:
            raw = json.loads(self.hall_of_fame_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                version = int(raw.get("save_version", 1) or 1)
                if version > self.SAVE_VERSION:
                    self.last_load_error = (
                        f"Unsupported hall of fame version {version}; app supports up to {self.SAVE_VERSION}."
                    )
                    return []
                payload = raw.get("hall_of_fame", [])
                if isinstance(payload, list):
                    return [entry for entry in payload if isinstance(entry, dict)]
                self.last_load_error = "Hall of fame payload is invalid; starting empty."
                return []
            if isinstance(raw, list):
                return [entry for entry in raw if isinstance(entry, dict)]
            self.last_load_error = "Hall of fame file has invalid format; starting empty."
        except (json.JSONDecodeError, OSError) as exc:
            self.last_load_error = f"Failed to load hall of fame ({exc}); starting empty."
            return []
        return []

    def _save_hall_of_fame(self) -> None:
        payload = {
            "save_version": self.SAVE_VERSION,
            "hall_of_fame": self.hall_of_fame,
        }
        self._write_json_with_backup(self.hall_of_fame_path, payload)

    def _write_json_with_backup(self, path: Path, payload: Any, *, with_backup: bool = True) -> None:
        if with_backup and path.exists():
            backup = path.with_suffix(path.suffix + ".bak")
            try:
                shutil.copy2(path, backup)
            except OSError:
                pass
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _apply_career_history_to_rosters(self) -> None:
        for team in self.teams:
            for player in [*team.roster, *team.minor_roster]:
                player.career_seasons = list(self.career_history.get(player.player_id, []))

    def _serialize_player(self, player: Player) -> dict[str, Any]:
        return {
            "player_id": player.player_id,
            "team_name": player.team_name,
            "name": player.name,
            "position": player.position,
            "jersey_number": player.jersey_number,
            "birth_country": player.birth_country,
            "birth_country_code": player.birth_country_code,
            "shooting": player.shooting,
            "playmaking": player.playmaking,
            "defense": player.defense,
            "goaltending": player.goaltending,
            "physical": player.physical,
            "durability": player.durability,
            "age": player.age,
            "prime_age": player.prime_age,
            "games_played": player.games_played,
            "goals": player.goals,
            "assists": player.assists,
            "injuries": player.injuries,
            "injured_games_remaining": player.injured_games_remaining,
            "games_missed_injury": player.games_missed_injury,
            "injury_type": player.injury_type,
            "injury_status": player.injury_status,
            "dtd_play_today": player.dtd_play_today,
            "temporary_replacement_for": player.temporary_replacement_for,
            "goalie_games": player.goalie_games,
            "goalie_wins": player.goalie_wins,
            "goalie_losses": player.goalie_losses,
            "goalie_ot_losses": player.goalie_ot_losses,
            "goalie_shutouts": player.goalie_shutouts,
            "shots_against": player.shots_against,
            "saves": player.saves,
            "goals_against": player.goals_against,
            "draft_season": player.draft_season,
            "draft_round": player.draft_round,
            "draft_overall": player.draft_overall,
            "draft_team": player.draft_team,
            "prospect_tier": player.prospect_tier,
            "seasons_to_nhl": player.seasons_to_nhl,
            "prospect_potential": player.prospect_potential,
            "prospect_boom_chance": player.prospect_boom_chance,
            "prospect_bust_chance": player.prospect_bust_chance,
            "prospect_resolved": player.prospect_resolved,
            "contract_years_left": player.contract_years_left,
            "cap_hit": player.cap_hit,
            "contract_type": player.contract_type,
            "is_rfa": player.is_rfa,
            "free_agent_origin_team": player.free_agent_origin_team,
            "career_seasons": player.career_seasons,
        }

    def _deserialize_player(self, raw: dict[str, Any]) -> Player:
        player_id = str(raw.get("player_id") or f"legacy_{raw.get('name', '')}_{self._rng.random():.9f}")
        has_country = raw.get("birth_country") is not None or raw.get("birth_country_code") is not None
        sampled_country, sampled_code = self._sample_birth_country()
        return Player(
            player_id=player_id,
            team_name=str(raw.get("team_name", "")),
            name=str(raw.get("name", "")),
            position=str(raw.get("position", "C")),
            jersey_number=(int(raw.get("jersey_number")) if raw.get("jersey_number") is not None else None),
            birth_country=(str(raw.get("birth_country", sampled_country)) if has_country else sampled_country),
            birth_country_code=(str(raw.get("birth_country_code", sampled_code)).upper() if has_country else sampled_code),
            shooting=float(raw.get("shooting", 2.5)),
            playmaking=float(raw.get("playmaking", 2.5)),
            defense=float(raw.get("defense", 2.5)),
            goaltending=float(raw.get("goaltending", 0.3)),
            physical=float(raw.get("physical", 2.5)),
            durability=float(raw.get("durability", 2.5)),
            age=int(raw.get("age", 24)),
            prime_age=int(raw.get("prime_age", 27)),
            games_played=int(raw.get("games_played", 0)),
            goals=int(raw.get("goals", 0)),
            assists=int(raw.get("assists", 0)),
            injuries=int(raw.get("injuries", 0)),
            injured_games_remaining=int(raw.get("injured_games_remaining", 0)),
            games_missed_injury=int(raw.get("games_missed_injury", 0)),
            injury_type=str(raw.get("injury_type", "")),
            injury_status=str(raw.get("injury_status", "Healthy")),
            dtd_play_today=bool(raw.get("dtd_play_today", False)),
            temporary_replacement_for=str(raw.get("temporary_replacement_for", "")),
            goalie_games=int(raw.get("goalie_games", 0)),
            goalie_wins=int(raw.get("goalie_wins", 0)),
            goalie_losses=int(raw.get("goalie_losses", 0)),
            goalie_ot_losses=int(raw.get("goalie_ot_losses", 0)),
            goalie_shutouts=int(raw.get("goalie_shutouts", 0)),
            shots_against=int(raw.get("shots_against", 0)),
            saves=int(raw.get("saves", 0)),
            goals_against=int(raw.get("goals_against", 0)),
            draft_season=(int(raw.get("draft_season")) if raw.get("draft_season") is not None else None),
            draft_round=(int(raw.get("draft_round")) if raw.get("draft_round") is not None else None),
            draft_overall=(int(raw.get("draft_overall")) if raw.get("draft_overall") is not None else None),
            draft_team=(str(raw.get("draft_team")) if raw.get("draft_team") is not None else None),
            prospect_tier=str(raw.get("prospect_tier", "NHL")),
            seasons_to_nhl=int(raw.get("seasons_to_nhl", 0)),
            prospect_potential=float(raw.get("prospect_potential", 0.5)),
            prospect_boom_chance=float(raw.get("prospect_boom_chance", 0.08)),
            prospect_bust_chance=float(raw.get("prospect_bust_chance", 0.10)),
            prospect_resolved=bool(raw.get("prospect_resolved", False)),
            contract_years_left=int(raw.get("contract_years_left", 2)),
            cap_hit=float(raw.get("cap_hit", 1.2)),
            contract_type=str(raw.get("contract_type", "entry")),
            is_rfa=bool(raw.get("is_rfa", True)),
            free_agent_origin_team=str(raw.get("free_agent_origin_team", "")),
            career_seasons=list(raw.get("career_seasons", [])),
        )

    def _serialize_team(self, team: Team) -> dict[str, Any]:
        return {
            "name": team.name,
            "division": team.division,
            "conference": team.conference,
            "logo": team.logo,
            "primary_color": team.primary_color,
            "secondary_color": team.secondary_color,
            "arena_capacity": team.arena_capacity,
            "starting_goalie_name": team.starting_goalie_name,
            "coach_name": team.coach_name,
            "coach_age": team.coach_age,
            "coach_rating": team.coach_rating,
            "coach_style": team.coach_style,
            "coach_offense": team.coach_offense,
            "coach_defense": team.coach_defense,
            "coach_goalie_dev": team.coach_goalie_dev,
            "coach_tenure_seasons": team.coach_tenure_seasons,
            "coach_changes_recent": team.coach_changes_recent,
            "coach_honeymoon_games_remaining": team.coach_honeymoon_games_remaining,
            "captain_name": team.captain_name,
            "assistant_names": list(team.assistant_names),
            "retired_numbers": list(team.retired_numbers),
            "dressed_player_names": sorted(list(team.dressed_player_names)),
            "line_assignments": dict(team.line_assignments),
            "roster": [self._serialize_player(player) for player in team.roster],
            "minor_roster": [self._serialize_player(player) for player in team.minor_roster],
        }

    def _deserialize_teams(self, raw_teams: list[Any]) -> list[Team]:
        teams: list[Team] = []
        for raw_team in raw_teams:
            if not isinstance(raw_team, dict):
                continue
            roster_raw = raw_team.get("roster", [])
            roster = [self._deserialize_player(p) for p in roster_raw if isinstance(p, dict)]
            minor_roster_raw = raw_team.get("minor_roster", [])
            minor_roster = [self._deserialize_player(p) for p in minor_roster_raw if isinstance(p, dict)]

            # Backward-compatible load repair:
            # older saves can carry >22 healthy players on active roster.
            active_roster = [p for p in roster if not p.is_injured]
            overflow = len(active_roster) - Team.MAX_ROSTER_SIZE
            if overflow > 0:
                def _load_value(player: Player) -> float:
                    if player.position in GOALIE_POSITIONS:
                        return player.goaltending * 0.72 + player.durability * 0.18 + player.defense * 0.10
                    return player.shooting * 0.38 + player.playmaking * 0.32 + player.defense * 0.22 + player.physical * 0.08

                non_goalie = [p for p in active_roster if p.position not in GOALIE_POSITIONS]
                demote_pool = sorted(non_goalie, key=lambda p: (_load_value(p), p.age, p.name))
                if len(demote_pool) < overflow:
                    remaining = [p for p in active_roster if p not in demote_pool]
                    demote_pool.extend(
                        sorted(remaining, key=lambda p: (_load_value(p), p.age, p.name))[: overflow - len(demote_pool)]
                    )
                for player in demote_pool[:overflow]:
                    if player in roster:
                        roster.remove(player)
                        minor_roster.append(player)

            dressed_raw = raw_team.get("dressed_player_names", [])
            dressed = {str(name) for name in dressed_raw} if isinstance(dressed_raw, list) else set()
            roster_names = {p.name for p in roster}
            dressed = {name for name in dressed if name in roster_names}
            teams.append(
                Team(
                    name=str(raw_team.get("name", "")),
                    division=str(raw_team.get("division", "Independent")),
                    conference=str(
                        raw_team.get(
                            "conference",
                            self._default_conference_for_division(str(raw_team.get("division", "Independent"))),
                        )
                    ),
                    logo=str(raw_team.get("logo", "ðŸ’")),
                    primary_color=str(raw_team.get("primary_color", "#1f3a93")),
                    secondary_color=str(raw_team.get("secondary_color", "#d7e1f5")),
                    arena_capacity=int(raw_team.get("arena_capacity", 16000)),
                    roster=roster,
                    minor_roster=minor_roster,
                    dressed_player_names=dressed,
                    line_assignments=(
                        {str(k): str(v) for k, v in raw_team.get("line_assignments", {}).items()}
                        if isinstance(raw_team.get("line_assignments", {}), dict)
                        else {}
                    ),
                    starting_goalie_name=(
                        str(raw_team.get("starting_goalie_name"))
                        if raw_team.get("starting_goalie_name") is not None
                        else None
                    ),
                    coach_name=str(raw_team.get("coach_name", "Staff Coach")),
                    coach_age=int(raw_team.get("coach_age", 52)),
                    coach_rating=float(raw_team.get("coach_rating", 3.0)),
                    coach_style=str(raw_team.get("coach_style", "balanced")),
                    coach_offense=float(raw_team.get("coach_offense", 3.0)),
                    coach_defense=float(raw_team.get("coach_defense", 3.0)),
                    coach_goalie_dev=float(raw_team.get("coach_goalie_dev", 3.0)),
                    coach_tenure_seasons=int(raw_team.get("coach_tenure_seasons", 0)),
                    coach_changes_recent=float(raw_team.get("coach_changes_recent", 0.0)),
                    coach_honeymoon_games_remaining=int(raw_team.get("coach_honeymoon_games_remaining", 0)),
                    captain_name=str(raw_team.get("captain_name", "")),
                    assistant_names=(
                        [str(x) for x in raw_team.get("assistant_names", []) if str(x).strip()]
                        if isinstance(raw_team.get("assistant_names", []), list)
                        else []
                    ),
                    retired_numbers=(
                        [row for row in raw_team.get("retired_numbers", []) if isinstance(row, dict)]
                        if isinstance(raw_team.get("retired_numbers", []), list)
                        else []
                    ),
                )
            )
        return teams

    def _default_conference_for_division(self, division: str) -> str:
        if division in {"East", "Central"}:
            return "Eastern"
        if division in {"West", "North"}:
            return "Western"
        return "Independent"

    def _coach_name_taken(self, coach_name: str) -> bool:
        return any(t.coach_name == coach_name for t in self.teams)

    def _generate_coach_name(self) -> str:
        for _ in range(120):
            first = self._rng.choice(self.COACH_FIRST_NAMES)
            last = self._rng.choice(self.COACH_LAST_NAMES)
            candidate = f"{first} {last}"
            if not self._coach_name_taken(candidate):
                return candidate
        return f"Coach {self._rng.randrange(100, 999)}"

    def _generate_coach_rating(self, lower: float = 2.2, upper: float = 4.8) -> float:
        return round(self._rng.uniform(lower, upper), 2)

    def _rating_to_style(self, rating: float) -> str:
        if rating >= 4.0:
            return "aggressive"
        if rating <= 2.6:
            return "defensive"
        return self._rng.choice(["balanced", "aggressive", "defensive"])

    def _ensure_team_coaches(self) -> None:
        ages_before = [int(getattr(t, "coach_age", 0) or 0) for t in self.teams]
        for team in self.teams:
            had_default_name = (not team.coach_name) or (team.coach_name == "Staff Coach")
            if had_default_name:
                team.coach_name = self._generate_coach_name()
                team.coach_age = int(self._rng.randint(43, 59))
                team.coach_rating = self._generate_coach_rating()
                team.coach_style = self._rating_to_style(team.coach_rating)
                team.coach_offense = self._generate_coach_rating(lower=2.1, upper=4.9)
                team.coach_defense = self._generate_coach_rating(lower=2.1, upper=4.9)
                team.coach_goalie_dev = self._generate_coach_rating(lower=2.1, upper=4.9)
                continue
            # Backfill older saves where all coaches ended up at baseline 3.00/balanced.
            if abs(team.coach_rating - 3.0) < 1e-9 and team.coach_style == "balanced":
                team.coach_rating = self._generate_coach_rating()
                team.coach_style = self._rating_to_style(team.coach_rating)
            if team.coach_offense <= 0 or team.coach_defense <= 0 or team.coach_goalie_dev <= 0:
                team.coach_offense = self._generate_coach_rating(lower=2.1, upper=4.9)
                team.coach_defense = self._generate_coach_rating(lower=2.1, upper=4.9)
                team.coach_goalie_dev = self._generate_coach_rating(lower=2.1, upper=4.9)
            if team.coach_rating <= 0:
                team.coach_rating = self._generate_coach_rating()
            if int(getattr(team, "coach_age", 0)) <= 0:
                team.coach_age = int(self._rng.randint(43, 59))
            team.coach_style = team.coach_style if team.coach_style in STRATEGY_EFFECTS else self._rating_to_style(team.coach_rating)

        # Legacy-save repair: older saves had no coach age and loaded every coach as 52 (or 53 after one offseason).
        # If all coach ages are identical and in that fallback band, spread them to realistic NHL-style ranges.
        unique_ages_before = {a for a in ages_before if a > 0}
        if len(self.teams) >= 6 and len(unique_ages_before) == 1 and next(iter(unique_ages_before)) in {52, 53}:
            for team in self.teams:
                team.coach_age = int(self._rng.randint(43, 63))

    def _coach_retirement_probability(self, team: Team) -> float:
        age = int(max(1, team.coach_age))
        if age < 58:
            base = 0.0
        elif age < 62:
            base = 0.01 + (age - 58) * 0.01
        elif age < 66:
            base = 0.06 + (age - 62) * 0.02
        elif age < 70:
            base = 0.14 + (age - 66) * 0.06
        else:
            base = 0.42 + (age - 70) * 0.12
        base += max(0.0, team.coach_tenure_seasons - 6) * 0.01
        base += max(0.0, team.coach_changes_recent) * 0.005
        base -= max(0.0, team.coach_rating - 3.6) * 0.02
        return max(0.0, min(0.95, base))

    def _replace_retired_coach(self, team: Team) -> dict[str, object]:
        old_name = team.coach_name
        old_age = int(team.coach_age)
        old_rating = float(team.coach_rating)
        team.coach_name = self._generate_coach_name()
        team.coach_age = int(self._rng.randint(42, 57))
        team.coach_rating = self._generate_coach_rating(lower=2.4, upper=4.85)
        team.coach_style = self._rating_to_style(team.coach_rating)
        team.coach_offense = self._generate_coach_rating(lower=2.0, upper=4.9)
        team.coach_defense = self._generate_coach_rating(lower=2.0, upper=4.9)
        team.coach_goalie_dev = self._generate_coach_rating(lower=2.0, upper=4.9)
        team.coach_tenure_seasons = 0
        team.coach_changes_recent = min(5.0, max(0.0, team.coach_changes_recent) + 0.8)
        team.coach_honeymoon_games_remaining = 24
        team.set_default_lineup()
        return {
            "team": team.name,
            "old_name": old_name,
            "old_age": old_age,
            "old_rating": round(old_rating, 2),
            "new_name": team.coach_name,
            "new_age": int(team.coach_age),
            "new_rating": round(team.coach_rating, 2),
            "new_style": team.coach_style,
        }

    def _ensure_minor_roster_depth(self) -> None:
        for team in self.teams:
            while len(team.minor_roster) < Team.MIN_MINOR_ROSTER_SIZE:
                position = self._rng.choice(["C", "LW", "RW", "D", "D", "G"])
                depth_player = self._create_draft_player(
                    team_name=team.name,
                    position=position,
                    quality=self._rng.uniform(0.38, 0.68),
                    draft_round=None,
                    draft_overall=None,
                )
                depth_player.prospect_tier = "AHL"
                depth_player.draft_season = None
                depth_player.draft_round = None
                depth_player.draft_overall = None
                depth_player.draft_team = None
                if depth_player.seasons_to_nhl <= 0:
                    depth_player.seasons_to_nhl = 1
                team.minor_roster.append(depth_player)

    def _leadership_score(self, player: Player) -> float:
        skater_score = player.shooting + player.playmaking + player.defense + player.physical + player.durability
        age_bonus = min(8.0, max(0.0, (player.age - 21) * 0.7))
        goalie_penalty = 4.0 if player.position in GOALIE_POSITIONS else 0.0
        return skater_score + age_bonus - goalie_penalty

    def _ensure_team_leadership(self) -> None:
        for team in self.teams:
            core = [p for p in team.roster if not p.is_injured]
            if not core:
                core = list(team.roster)
            if not core:
                team.captain_name = ""
                team.assistant_names = []
                continue
            ranked = sorted(core, key=lambda p: (self._leadership_score(p), p.age, p.name), reverse=True)
            current_names = {p.name for p in core}
            captain_valid = team.captain_name in current_names
            assistants_valid = [name for name in team.assistant_names if name in current_names and name != team.captain_name]
            if not captain_valid:
                team.captain_name = ranked[0].name
            if len(assistants_valid) < 2:
                picked = [p.name for p in ranked if p.name != team.captain_name]
                team.assistant_names = [*assistants_valid, *[n for n in picked if n not in assistants_valid][: max(0, 2 - len(assistants_valid))]]
            else:
                team.assistant_names = assistants_valid[:2]

    def _number_pool_for_position(self, position: str) -> list[int]:
        if position in GOALIE_POSITIONS:
            return [1, *list(range(30, 40)), 41, 50, 60, 70, 80, 90]
        return [*list(range(2, 30)), *list(range(40, 100))]

    def _retired_number_set(self, team: Team) -> set[int]:
        out: set[int] = set()
        for row in team.retired_numbers:
            if not isinstance(row, dict):
                continue
            value = row.get("number")
            if value is None:
                continue
            try:
                num = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= num <= 99:
                out.add(num)
        return out

    def _assign_team_player_numbers(self, team: Team) -> None:
        used: set[int] = set()
        retired_reserved = self._retired_number_set(team)
        all_players = [*team.roster, *team.minor_roster]

        # Keep valid unique existing numbers first.
        for player in all_players:
            n = player.jersey_number
            if n is None:
                continue
            if not (1 <= int(n) <= 99):
                player.jersey_number = None
                continue
            if int(n) in retired_reserved:
                player.jersey_number = None
                continue
            if int(n) in used:
                player.jersey_number = None
                continue
            used.add(int(n))

        # Assign missing/invalid numbers with position-aware defaults.
        for player in all_players:
            if player.jersey_number is not None:
                continue
            assigned: int | None = None
            for candidate in self._number_pool_for_position(player.position):
                if candidate not in used and candidate not in retired_reserved:
                    assigned = candidate
                    break
            if assigned is None:
                for candidate in range(1, 100):
                    if candidate not in used and candidate not in retired_reserved:
                        assigned = candidate
                        break
            if assigned is None:
                assigned = 99
            player.jersey_number = assigned
            used.add(assigned)

    def _ensure_team_player_numbers(self) -> None:
        for team in self.teams:
            self._assign_team_player_numbers(team)
        for player in self.free_agents:
            if not (player.jersey_number is None or 1 <= int(player.jersey_number) <= 99):
                player.jersey_number = None

    def normalize_player_numbers(self) -> None:
        self._ensure_team_player_numbers()
        self._save_state()

    def _ensure_player_contracts(self) -> None:
        for team in self.teams:
            for player in [*team.roster, *team.minor_roster]:
                years = int(getattr(player, "contract_years_left", 0) or 0)
                cap_hit = float(getattr(player, "cap_hit", 0.0) or 0.0)
                contract_type = str(getattr(player, "contract_type", "") or "").strip().lower()
                needs_backfill = years <= 0 or cap_hit <= 0.0 or contract_type not in {"entry", "bridge", "core", "veteran"}
                legacy_like = (
                    years == 2
                    and abs(cap_hit - 1.2) < 1e-9
                    and contract_type in {"", "entry"}
                    and player.age >= 24
                )
                if not (needs_backfill or legacy_like):
                    continue
                y, cap, ctype, rfa = self._estimate_contract_offer(player)
                self._assign_contract_terms(player, years=y, cap_hit=cap, contract_type=ctype, is_rfa=rfa)
        for player in self.free_agents:
            years = int(getattr(player, "contract_years_left", 0) or 0)
            cap_hit = float(getattr(player, "cap_hit", 0.0) or 0.0)
            contract_type = str(getattr(player, "contract_type", "") or "").strip().lower()
            needs_backfill = years <= 0 or cap_hit <= 0.0 or contract_type not in {"entry", "bridge", "core", "veteran"}
            if not needs_backfill:
                continue
            y, cap, ctype, rfa = self._estimate_contract_offer(player)
            self._assign_contract_terms(player, years=y, cap_hit=cap, contract_type=ctype, is_rfa=rfa)

    def _migrate_legacy_birth_countries(self) -> None:
        for team in self.teams:
            org_players = [*team.roster, *team.minor_roster]
            if len(org_players) < 10:
                continue
            valid_codes = [str(p.birth_country_code or "").upper() for p in org_players if str(p.birth_country_code or "").strip()]
            unique_codes = {c for c in valid_codes if len(c) == 2}
            if unique_codes == {"CA"}:
                for player in org_players:
                    country, code = self._sample_birth_country()
                    player.birth_country = country
                    player.birth_country_code = code

    def _migrate_team_branding(self) -> None:
        branding: dict[str, tuple[str, str]] = {
            "Timberwolves": ("#166534", "#d4af37"),
            "Polar Caps": ("#0c2340", "#c0c0c0"),
            "Silver Pines": ("#1f6f50", "#c0c0c0"),
            "Harbor Kings": ("#5b2c83", "#d8c7a0"),
            "Liberty Blades": ("#c1121f", "#1d4ed8"),
            "Iron Rangers": ("#1f2937", "#c1121f"),
        }
        for team in self.teams:
            colors = branding.get(team.name)
            if colors is not None:
                team.primary_color, team.secondary_color = colors

    def _coach_matchup_preference(self, team: Team, opponent: Team) -> str:
        team_top = sorted([p.scoring_weight for p in team.active_skaters()], reverse=True)[:6]
        opp_top = sorted([p.scoring_weight for p in opponent.active_skaters()], reverse=True)[:6]
        team_off = sum(team_top) / max(1, len(team_top))
        opp_off = sum(opp_top) / max(1, len(opp_top))
        if team_off - opp_off > 0.16:
            return "aggressive"
        if opp_off - team_off > 0.16:
            return "defensive"
        return "balanced"

    def _coach_modifiers(self, team: Team, chosen_strategy: str, opponent: Team) -> tuple[float, float, float]:
        style = chosen_strategy if chosen_strategy in STRATEGY_EFFECTS else "balanced"
        rating_delta = team.coach_rating - 3.0
        coach_quality = max(0.0, min(1.0, (team.coach_rating - 2.0) / 3.0))
        offense_specialty = (team.coach_offense - 3.0) * 0.06
        defense_specialty = (team.coach_defense - 3.0) * 0.06
        preferred = self._coach_matchup_preference(team, opponent)
        style_match = style == team.coach_style
        matchup_match = style == preferred

        tactical = 0.00
        if style_match:
            tactical += 0.05
        else:
            tactical -= 0.02
        if matchup_match:
            tactical += 0.06 * coach_quality
        else:
            tactical -= 0.03 * (1.0 - coach_quality)

        base = rating_delta * 0.12 + tactical
        if style == "aggressive":
            offense_bonus = base * 1.12 + 0.03 + offense_specialty
            defense_bonus = base * 0.78 - 0.02 + defense_specialty * 0.75
            injury_mult = max(0.75, 1.05 - coach_quality * 0.08)
        elif style == "defensive":
            offense_bonus = base * 0.82 - 0.02 + offense_specialty * 0.75
            defense_bonus = base * 1.16 + 0.03 + defense_specialty
            injury_mult = max(0.72, 0.96 - coach_quality * 0.10)
        else:
            offense_bonus = base + offense_specialty * 0.90
            defense_bonus = base + defense_specialty * 0.90
            injury_mult = max(0.74, 1.00 - coach_quality * 0.09)

        instability = min(0.30, max(0.0, team.coach_changes_recent) * 0.06)
        tenure_buffer = min(0.10, max(0, team.coach_tenure_seasons) * 0.015)
        net_instability = max(0.0, instability - tenure_buffer)
        if net_instability > 0:
            offense_bonus -= net_instability * 0.55
            defense_bonus -= net_instability * 0.55
            injury_mult = min(1.35, injury_mult + net_instability * 0.22)

        if team.coach_honeymoon_games_remaining > 0:
            honeymoon_factor = min(1.0, team.coach_honeymoon_games_remaining / 24.0)
            honeymoon_boost = 0.08 * honeymoon_factor * (0.85 + coach_quality * 0.30)
            offense_bonus += honeymoon_boost * 0.60
            defense_bonus += honeymoon_boost * 0.60
            injury_mult = max(0.70, injury_mult - honeymoon_boost * 0.10)
        return (offense_bonus, defense_bonus, injury_mult)

    def _consume_coach_game_effect(self, team: Team) -> None:
        if team.coach_honeymoon_games_remaining > 0:
            team.coach_honeymoon_games_remaining -= 1

    def _schedule_context_modifiers(
        self,
        team: Team,
        opponent: Team,
        played_yesterday: set[str],
        is_away: bool,
    ) -> tuple[float, float]:
        offense_pen = 0.0
        injury_mult = 1.0
        if team.name in played_yesterday:
            offense_pen += 0.06
            injury_mult += 0.06
            if is_away:
                offense_pen += 0.02
                injury_mult += 0.02
            if team.conference != opponent.conference:
                offense_pen += 0.03
                injury_mult += 0.03
            elif team.division != opponent.division:
                offense_pen += 0.015
                injury_mult += 0.015
        return (-offense_pen, injury_mult)

    def _goalie_selection_value(self, player: Player) -> float:
        # Blend raw talent with in-season form.
        sv_sample = player.save_pct if player.shots_against >= 120 else 0.900
        gaa_sample = player.gaa if player.goalie_games >= 4 else 2.95
        return (
            player.goaltending * 0.72
            + sv_sample * 2.05
            + (3.30 - gaa_sample) * 0.32
        )

    def _coach_choose_playoff_goalie(
        self,
        team: Team,
        series_games: list[dict[str, object]],
        elimination_game: bool = False,
    ) -> Player | None:
        goalies = team.dressed_goalies() or team.active_goalies()
        if not goalies:
            return None
        if len(goalies) == 1:
            return goalies[0]

        ranked = sorted(goalies, key=self._goalie_selection_value, reverse=True)
        starter = ranked[0]
        backup = ranked[1]

        recent_starts: list[dict[str, float]] = []
        for game in reversed(series_games):
            is_home = str(game.get("home", "")) == team.name
            is_away = str(game.get("away", "")) == team.name
            if not is_home and not is_away:
                continue
            if is_home:
                goalie = str(game.get("home_goalie", ""))
                shots = int(game.get("home_goalie_shots", 0))
                saves = int(game.get("home_goalie_saves", 0))
                ga = int(game.get("away_goals", 0))
            else:
                goalie = str(game.get("away_goalie", ""))
                shots = int(game.get("away_goalie_shots", 0))
                saves = int(game.get("away_goalie_saves", 0))
                ga = int(game.get("home_goals", 0))
            sv = (saves / shots) if shots > 0 else 0.0
            recent_starts.append({"goalie": goalie, "sv": sv, "ga": float(ga)})
            if len(recent_starts) >= 8:
                break

        if not recent_starts:
            return starter

        def _goalie_rows(name: str) -> list[dict[str, float]]:
            return [row for row in recent_starts if str(row.get("goalie", "")) == name]

        def _avg_sv(rows: list[dict[str, float]]) -> float:
            if not rows:
                return 0.0
            return sum(float(r.get("sv", 0.0)) for r in rows) / max(1, len(rows))

        starter_rows = _goalie_rows(starter.name)
        backup_rows = _goalie_rows(backup.name)
        starter_last_two = starter_rows[:2]
        starter_bad_streak = (
            len(starter_last_two) >= 2
            and _avg_sv(starter_last_two) < 0.885
        )
        starter_last = starter_rows[0] if starter_rows else None
        starter_single_disaster = bool(
            starter_last is not None
            and float(starter_last.get("sv", 0.0)) < 0.860
            and float(starter_last.get("ga", 0.0)) >= 4.0
        )
        starter_series_struggle = (
            len(starter_rows) >= 3
            and _avg_sv(starter_rows) < 0.890
        )
        backup_hot = (
            len(backup_rows) >= 1
            and _avg_sv(backup_rows[:2]) >= 0.905
        )

        # Playoff switch trigger: starter struggles and backup has shown enough form.
        if starter_bad_streak or starter_single_disaster:
            return backup
        if starter_series_struggle and backup_hot:
            return backup

        # If backup already took over and is running well, stick with him.
        last_goalie = str(recent_starts[0].get("goalie", ""))
        if last_goalie == backup.name:
            backup_last = backup_rows[0] if backup_rows else None
            if backup_last is not None and float(backup_last.get("sv", 0.0)) >= 0.895:
                return backup
            # In elimination games, only move off backup after a clearly poor outing.
            if elimination_game and backup_last is not None and float(backup_last.get("sv", 0.0)) >= 0.875:
                return backup

        return starter

    def _coach_choose_starting_goalie(
        self,
        team: Team,
        playoff_mode: bool = False,
        played_yesterday: bool = False,
    ) -> Player | None:
        goalies = team.dressed_goalies() or team.active_goalies()
        if not goalies:
            return None
        if len(goalies) == 1:
            return goalies[0]

        coach_quality = max(0.0, min(1.0, (team.coach_rating - 2.0) / 3.0))

        ranked = sorted(goalies, key=self._goalie_selection_value, reverse=True)
        starter = ranked[0]
        backup = ranked[1]

        # Playoffs: ride the starter unless unavailable (handled by dressed_goalies/active_goalies).
        if playoff_mode:
            return starter

        # In regular season back-to-backs, coaches should usually rest the starter.
        if not playoff_mode and played_yesterday:
            quality_gap = self._goalie_selection_value(starter) - self._goalie_selection_value(backup)
            starter_override_chance = 0.10
            if quality_gap > 0.85:
                starter_override_chance = 0.22
            elif quality_gap > 0.55:
                starter_override_chance = 0.16
            if self._rng.random() > starter_override_chance:
                return backup

        # Good coaches lean heavily on their best goalie, especially in playoffs.
        base_starter_share = 0.70 + coach_quality * (0.16 if playoff_mode else 0.12)
        # If workload gap gets too high, schedule in backup starts occasionally.
        workload_gap = starter.goalie_games - backup.goalie_games
        fatigue_threshold = 12 if playoff_mode else 6
        fatigue_penalty = max(0.0, (workload_gap - fatigue_threshold) * (0.014 if playoff_mode else 0.024))
        if not playoff_mode and workload_gap >= 12:
            fatigue_penalty += 0.08
        starter_share = max(0.52, min(0.94, base_starter_share - fatigue_penalty))

        if self._rng.random() <= starter_share:
            return starter
        return backup

    def _coach_set_dtd_decisions(
        self,
        team: Team,
        opponent: Team,
        playoff_mode: bool = False,
        elimination_game: bool = False,
    ) -> None:
        coach_quality = max(0.0, min(1.0, (team.coach_rating - 2.0) / 3.0))
        style = team.coach_style if team.coach_style in {"aggressive", "balanced", "defensive"} else "balanced"
        team_rec = self._records.get(team.name)
        opp_rec = self._records.get(opponent.name)
        underdog_push = 0.0
        if team_rec is not None and opp_rec is not None and team_rec.point_pct + 0.015 < opp_rec.point_pct:
            underdog_push = 0.04
        healthy_by_pos: dict[str, int] = {"C": 0, "LW": 0, "RW": 0, "D": 0, "G": 0}
        for p in team.roster:
            if p.injured_games_remaining <= 0:
                healthy_by_pos[p.position] = healthy_by_pos.get(p.position, 0) + 1

        for player in team.roster:
            if not player.is_dtd:
                player.dtd_play_today = False
                continue

            healthy_depth_count = max(0, healthy_by_pos.get(player.position, 0))
            has_healthy_depth = healthy_depth_count > 0
            if player.position in GOALIE_POSITIONS and not has_healthy_depth:
                player.dtd_play_today = True
                continue

            if player.position in GOALIE_POSITIONS:
                impact = player.goaltending
            else:
                impact = player.shooting * 0.40 + player.playmaking * 0.34 + player.defense * 0.20 + player.physical * 0.06
            impact_push = max(0.0, impact - 3.3) * 0.08
            severity = min(1.0, max(0.0, player.injured_games_remaining / 3.0))
            severity_penalty = 0.14 * severity

            play_probability = 0.34 + coach_quality * 0.22 + underdog_push + impact_push
            if style == "aggressive":
                play_probability += 0.08
            elif style == "defensive":
                play_probability -= 0.07
            if not has_healthy_depth:
                play_probability += 0.20
            else:
                play_probability -= 0.05
            if playoff_mode:
                play_probability += 0.11
            if elimination_game:
                play_probability += 0.10
            play_probability -= severity_penalty
            play_probability = self._clamp(play_probability, 0.12, 0.94)
            player.dtd_play_today = self._rng.random() < play_probability

    def fire_coach(self, team_name: str) -> dict[str, object]:
        team = self.get_team(team_name)
        if team is None:
            return {"fired": False, "reason": "team_not_found"}
        old_name = team.coach_name
        old_rating = team.coach_rating
        standings_map = {rec.team.name: rec for rec in self.get_standings()}
        rec = standings_map.get(team_name)
        point_pct = rec.point_pct if rec is not None and rec.games_played > 0 else 0.5
        upside = 0.18 if point_pct < 0.50 else 0.0
        churn_penalty = min(0.22, max(0.0, team.coach_changes_recent) * 0.05)
        new_rating = self._generate_coach_rating(lower=2.3 + upside - churn_penalty, upper=4.85 - churn_penalty * 0.8)
        team.coach_name = self._generate_coach_name()
        team.coach_age = int(self._rng.randint(42, 58))
        team.coach_rating = new_rating
        team.coach_style = self._rating_to_style(new_rating)
        team.coach_offense = self._generate_coach_rating(lower=2.0, upper=4.9)
        team.coach_defense = self._generate_coach_rating(lower=2.0, upper=4.9)
        team.coach_goalie_dev = self._generate_coach_rating(lower=2.0, upper=4.9)
        team.coach_tenure_seasons = 0
        team.coach_changes_recent = min(5.0, max(0.0, team.coach_changes_recent) + 1.0)
        team.coach_honeymoon_games_remaining = 24
        team.set_default_lineup()
        self._save_state()
        return {
            "fired": True,
            "team": team.name,
            "old_name": old_name,
            "old_rating": round(old_rating, 2),
            "new_name": team.coach_name,
            "new_rating": round(team.coach_rating, 2),
            "new_style": team.coach_style,
            "new_offense": round(team.coach_offense, 2),
            "new_defense": round(team.coach_defense, 2),
            "new_goalie_dev": round(team.coach_goalie_dev, 2),
            "instability": round(team.coach_changes_recent, 2),
            "point_pct": round(point_pct, 3),
        }

    def _serialize_records(self) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for team_name, rec in self._records.items():
            out[team_name] = {
                "wins": rec.wins,
                "losses": rec.losses,
                "ot_losses": rec.ot_losses,
                "goals_for": rec.goals_for,
                "goals_against": rec.goals_against,
                "home_wins": rec.home_wins,
                "home_losses": rec.home_losses,
                "home_ot_losses": rec.home_ot_losses,
                "away_wins": rec.away_wins,
                "away_losses": rec.away_losses,
                "away_ot_losses": rec.away_ot_losses,
                "pp_goals": rec.pp_goals,
                "pp_chances": rec.pp_chances,
                "pk_goals_against": rec.pk_goals_against,
                "pk_chances_against": rec.pk_chances_against,
                "recent_results": list(rec.recent_results),
            }
        return out

    def _deserialize_records(self, raw_records: Any) -> dict[str, TeamRecord]:
        records: dict[str, TeamRecord] = {team.name: TeamRecord(team=team) for team in self.teams}
        if not isinstance(raw_records, dict):
            return records
        for team in self.teams:
            raw = raw_records.get(team.name)
            if not isinstance(raw, dict):
                continue
            records[team.name] = TeamRecord(
                team=team,
                wins=int(raw.get("wins", 0)),
                losses=int(raw.get("losses", 0)),
                ot_losses=int(raw.get("ot_losses", 0)),
                goals_for=int(raw.get("goals_for", 0)),
                goals_against=int(raw.get("goals_against", 0)),
                home_wins=int(raw.get("home_wins", 0)),
                home_losses=int(raw.get("home_losses", 0)),
                home_ot_losses=int(raw.get("home_ot_losses", 0)),
                away_wins=int(raw.get("away_wins", 0)),
                away_losses=int(raw.get("away_losses", 0)),
                away_ot_losses=int(raw.get("away_ot_losses", 0)),
                pp_goals=int(raw.get("pp_goals", 0)),
                pp_chances=int(raw.get("pp_chances", 0)),
                pk_goals_against=int(raw.get("pk_goals_against", 0)),
                pk_chances_against=int(raw.get("pk_chances_against", 0)),
                recent_results=list(raw.get("recent_results", []))[-10:] if isinstance(raw.get("recent_results", []), list) else [],
            )
        return records

    def _serialize_standings(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for rec in self.get_standings():
            out.append(
                {
                    "team": rec.team.name,
                    "conference": rec.team.conference,
                    "division": rec.team.division,
                    "gp": rec.games_played,
                    "points": rec.points,
                    "point_pct": round(rec.point_pct, 3),
                    "wins": rec.wins,
                    "losses": rec.losses,
                    "ot_losses": rec.ot_losses,
                    "home": rec.home_record,
                    "away": rec.away_record,
                    "l10": rec.last10,
                    "strk": rec.streak,
                    "gf": rec.goals_for,
                    "ga": rec.goals_against,
                    "gd": rec.goal_diff,
                    "pp_pct": round(rec.pp_pct, 3),
                    "pk_pct": round(rec.pk_pct, 3),
                }
            )
        return out

    def _serialize_top_scorers(self, limit: int = 20) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for p in self.get_player_stats()[:limit]:
            out.append(
                {
                    "team": p.team_name,
                    "player": p.name,
                    "age": p.age,
                    "gp": p.games_played,
                    "g": p.goals,
                    "a": p.assists,
                    "p": p.points,
                }
            )
        return out

    def _serialize_top_goalies(self, limit: int = 12) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for p in self.get_goalie_stats()[:limit]:
            out.append(
                {
                    "team": p.team_name,
                    "goalie": p.name,
                    "age": p.age,
                    "gp": p.goalie_games,
                    "w": p.goalie_wins,
                    "l": p.goalie_losses,
                    "otl": p.goalie_ot_losses,
                    "so": p.goalie_shutouts,
                    "sv_pct": round(p.save_pct, 3),
                    "gaa": round(p.gaa, 2),
                }
            )
        return out

    def get_day_schedule(self) -> list[tuple[Team, Team]]:
        if self.is_complete():
            return []
        return self._season_days[self._day_index]

    def get_standings(self) -> list[TeamRecord]:
        return sorted(
            self._records.values(),
            key=lambda r: (r.points, r.goal_diff, r.goals_for),
            reverse=True,
        )

    def get_division_standings(self, division: str) -> list[TeamRecord]:
        return [rec for rec in self.get_standings() if rec.team.division == division]

    def get_divisions(self) -> list[str]:
        return sorted({team.division for team in self.teams})

    def get_conference_standings(self, conference: str) -> list[TeamRecord]:
        return [rec for rec in self.get_standings() if rec.team.conference == conference]

    def get_conferences(self) -> list[str]:
        return sorted({team.conference for team in self.teams})

    def _team_total_games(self) -> dict[str, int]:
        totals: dict[str, int] = {team.name: 0 for team in self.teams}
        for day in self._season_days:
            for home, away in day:
                totals[home.name] = totals.get(home.name, 0) + 1
                totals[away.name] = totals.get(away.name, 0) + 1
        return totals

    def get_playoff_clinch_status(self) -> dict[str, bool]:
        clinched: dict[str, bool] = {team.name: False for team in self.teams}
        total_games = self._team_total_games()
        for conference in self.get_conferences():
            conf_rows = self.get_conference_standings(conference)
            if not conf_rows:
                continue
            spots = min(8, len(conf_rows))
            if spots <= 0:
                continue
            for rank_idx, rec in enumerate(conf_rows, start=1):
                if rank_idx > spots:
                    continue
                teams_that_can_reach_or_pass = 0
                for other in conf_rows:
                    if other.team.name == rec.team.name:
                        continue
                    other_total = total_games.get(other.team.name, rec.games_played)
                    other_remaining = max(0, other_total - other.games_played)
                    other_max_points = other.points + (2 * other_remaining)
                    if other_max_points >= rec.points:
                        teams_that_can_reach_or_pass += 1
                if teams_that_can_reach_or_pass < spots:
                    clinched[rec.team.name] = True
        return clinched

    def get_team(self, team_name: str) -> Team | None:
        for team in self.teams:
            if team.name == team_name:
                return team
        return None

    def get_player_stats(self, team_name: str | None = None) -> list[Player]:
        players: list[Player] = []
        for team in self.teams:
            if team_name is None or team.name == team_name:
                players.extend(team.roster)
        return sorted(
            players,
            key=lambda p: (-p.points, -p.goals, -p.assists, -p.games_played, p.age, p.name),
        )

    def get_goalie_stats(self, team_name: str | None = None) -> list[Player]:
        goalies: list[Player] = []
        for team in self.teams:
            if team_name is None or team.name == team_name:
                goalies.extend([p for p in team.roster if p.position in GOALIE_POSITIONS])
        return sorted(
            goalies,
            key=lambda p: (-p.goalie_wins, p.gaa, -p.save_pct, -p.goalie_games, p.name),
        )

    def is_complete(self) -> bool:
        return self._day_index >= len(self._season_days)

    def has_playoff_session(self) -> bool:
        return self.pending_playoffs is not None

    def playoffs_finished(self) -> bool:
        return self.pending_playoffs is not None and self.pending_playoff_day_index >= len(self.pending_playoff_days)

    def _build_playoff_reveal_days(self, playoffs: dict[str, object]) -> list[dict[str, object]]:
        days: list[dict[str, object]] = []
        rounds = playoffs.get("rounds", [])
        if not isinstance(rounds, list):
            return days
        stage_groups: dict[str, list[dict[str, object]]] = {}
        stage_order: list[str] = []

        def _stage_name(round_name: str) -> str:
            suffixes = (
                " First Round",
                " Division Finals",
                " Conference Final",
                " Conference Quarterfinal",
                " Conference Semifinal",
            )
            for suffix in suffixes:
                if round_name.endswith(suffix):
                    return suffix.strip()
            return round_name

        for round_row in rounds:
            if not isinstance(round_row, dict):
                continue
            round_name = str(round_row.get("name", "Round"))
            stage = _stage_name(round_name)
            if stage not in stage_groups:
                stage_groups[stage] = []
                stage_order.append(stage)
            stage_groups[stage].append(round_row)

        for stage in stage_order:
            grouped_rounds = stage_groups.get(stage, [])
            all_series: list[dict[str, object]] = []
            for round_row in grouped_rounds:
                series_rows = round_row.get("series", [])
                if isinstance(series_rows, list):
                    all_series.extend([s for s in series_rows if isinstance(s, dict)])
            max_games = 0
            for series in all_series:
                games = series.get("games", [])
                if isinstance(games, list):
                    max_games = max(max_games, len(games))
            for game_no in range(1, max_games + 1):
                day_games: list[dict[str, object]] = []
                for series in all_series:
                    games = series.get("games", [])
                    if not isinstance(games, list):
                        continue

                    def _game_no(row: dict[str, object]) -> int:
                        try:
                            return int(row.get("game", 0))
                        except (TypeError, ValueError):
                            return 0

                    game_row = next((g for g in games if isinstance(g, dict) and _game_no(g) == game_no), None)
                    if game_row is None:
                        continue
                    series_high = str(series.get("higher_seed", ""))
                    series_low = str(series.get("lower_seed", ""))
                    high_wins = 0
                    low_wins = 0
                    for prior in games:
                        if not isinstance(prior, dict) or _game_no(prior) > game_no:
                            continue
                        winner = str(prior.get("winner", ""))
                        if winner == series_high:
                            high_wins += 1
                        elif winner == series_low:
                            low_wins += 1
                    entry = dict(game_row)
                    entry["series_higher_seed"] = series_high
                    entry["series_lower_seed"] = series_low
                    entry["series_high_wins"] = high_wins
                    entry["series_low_wins"] = low_wins
                    day_games.append(entry)
                if day_games:
                    days.append({"round": stage, "game_number": game_no, "games": day_games})
        return days

    def start_playoffs(self) -> dict[str, object]:
        if not self.is_complete():
            return {"started": False, "reason": "season_not_complete"}
        if self.pending_playoffs is None:
            playoffs = self._run_playoffs()
            self.pending_playoffs = playoffs
            self.pending_playoff_days = self._build_playoff_reveal_days(playoffs)
            self.pending_playoff_day_index = 0
            self._save_state()
        return {
            "started": True,
            "total_days": len(self.pending_playoff_days),
            "playoffs": self.pending_playoffs,
        }

    def simulate_next_playoff_day(self) -> dict[str, object]:
        if self.pending_playoffs is None:
            return {"advanced": False, "reason": "playoffs_not_started"}
        if self.pending_playoff_day_index >= len(self.pending_playoff_days):
            return {
                "advanced": False,
                "reason": "playoffs_complete",
                "complete": True,
                "playoffs": self.pending_playoffs,
            }
        # Decay injury timers per revealed playoff day so UI injury status stays in sync.
        # Playoffs are pre-simulated for outcomes, but user-facing recovery must still tick.
        self._advance_recovery_day()
        self._ensure_team_player_numbers()
        day = self.pending_playoff_days[self.pending_playoff_day_index]
        self.pending_playoff_day_index += 1
        complete = self.pending_playoff_day_index >= len(self.pending_playoff_days)
        self._save_state()
        return {
            "advanced": True,
            "day_number": self.pending_playoff_day_index,
            "total_days": len(self.pending_playoff_days),
            "day": day,
            "complete": complete,
            "playoffs": self.pending_playoffs,
        }

    def _advance_recovery_day(self) -> None:
        for team in self.teams:
            for player in [*team.roster, *team.minor_roster]:
                player.dtd_play_today = False
                if player.injured_games_remaining > 0:
                    player.injured_games_remaining -= 1
                    if player.injured_games_remaining <= 0:
                        player.injury_type = ""
                        player.injury_status = "Healthy"

    def _record_gp_snapshot(self) -> dict[str, int]:
        return {
            team_name: int(rec.games_played)
            for team_name, rec in self._records.items()
        }

    def _snapshot_team_records(self) -> dict[str, dict[str, object]]:
        snapshot: dict[str, dict[str, object]] = {}
        for team_name, rec in self._records.items():
            snapshot[team_name] = {
                "wins": int(rec.wins),
                "losses": int(rec.losses),
                "ot_losses": int(rec.ot_losses),
                "goals_for": int(rec.goals_for),
                "goals_against": int(rec.goals_against),
                "home_wins": int(rec.home_wins),
                "home_losses": int(rec.home_losses),
                "home_ot_losses": int(rec.home_ot_losses),
                "away_wins": int(rec.away_wins),
                "away_losses": int(rec.away_losses),
                "away_ot_losses": int(rec.away_ot_losses),
                "pp_goals": int(rec.pp_goals),
                "pp_chances": int(rec.pp_chances),
                "pk_goals_against": int(rec.pk_goals_against),
                "pk_chances_against": int(rec.pk_chances_against),
                "recent_results": list(rec.recent_results),
            }
        return snapshot

    def _restore_team_records(self, snapshot: dict[str, dict[str, object]]) -> None:
        for team_name, rec in self._records.items():
            saved = snapshot.get(team_name)
            if not isinstance(saved, dict):
                continue
            rec.wins = int(saved.get("wins", rec.wins))
            rec.losses = int(saved.get("losses", rec.losses))
            rec.ot_losses = int(saved.get("ot_losses", rec.ot_losses))
            rec.goals_for = int(saved.get("goals_for", rec.goals_for))
            rec.goals_against = int(saved.get("goals_against", rec.goals_against))
            rec.home_wins = int(saved.get("home_wins", rec.home_wins))
            rec.home_losses = int(saved.get("home_losses", rec.home_losses))
            rec.home_ot_losses = int(saved.get("home_ot_losses", rec.home_ot_losses))
            rec.away_wins = int(saved.get("away_wins", rec.away_wins))
            rec.away_losses = int(saved.get("away_losses", rec.away_losses))
            rec.away_ot_losses = int(saved.get("away_ot_losses", rec.away_ot_losses))
            rec.pp_goals = int(saved.get("pp_goals", rec.pp_goals))
            rec.pp_chances = int(saved.get("pp_chances", rec.pp_chances))
            rec.pk_goals_against = int(saved.get("pk_goals_against", rec.pk_goals_against))
            rec.pk_chances_against = int(saved.get("pk_chances_against", rec.pk_chances_against))
            recent = saved.get("recent_results", [])
            rec.recent_results = list(recent) if isinstance(recent, list) else list(rec.recent_results)

    def simulate_next_day(
        self,
        user_team_name: str | None = None,
        user_strategy: str = "balanced",
        use_user_lines: bool = False,
        use_user_strategy: bool = False,
    ) -> list[GameResult]:
        if self.is_complete():
            return []

        # Integrity guard: standings cannot be ahead of calendar day before sim.
        max_allowed_gp = max(0, int(self._day_index))
        for rec in self._records.values():
            if int(rec.games_played) > max_allowed_gp:
                raise ValueError(
                    f"Inconsistent state detected before sim: {rec.team.name} has {rec.games_played} GP "
                    f"while calendar day index is {self._day_index}."
                )

        self._ensure_team_player_numbers()
        self._advance_recovery_day()

        user_strategy = user_strategy.lower()
        if user_strategy not in STRATEGY_EFFECTS:
            user_strategy = "balanced"

        day_games = self._season_days[self._day_index]
        # Schedule integrity: a team may play at most one game per regular-season day.
        scheduled_names: set[str] = set()
        scheduled_day_teams: set[str] = set()
        for home, away in day_games:
            if home.name in scheduled_names or away.name in scheduled_names:
                raise ValueError(f"Invalid schedule day: duplicate team assignment on day {self.current_day}.")
            scheduled_names.add(home.name)
            scheduled_names.add(away.name)
            scheduled_day_teams.add(home.name)
            scheduled_day_teams.add(away.name)
        gp_before = self._record_gp_snapshot()
        records_before = self._snapshot_team_records()
        played_yesterday: set[str] = set()
        if self._day_index > 0:
            for home_prev, away_prev in self._season_days[self._day_index - 1]:
                played_yesterday.add(home_prev.name)
                played_yesterday.add(away_prev.name)
        day_results: list[GameResult] = []
        try:
            for home, away in day_games:
                self._ensure_team_depth(home)
                self._ensure_team_depth(away)
                self._coach_set_dtd_decisions(home, away, playoff_mode=False)
                self._coach_set_dtd_decisions(away, home, playoff_mode=False)
                if home.name != user_team_name or not use_user_lines:
                    home.set_default_lineup()
                if away.name != user_team_name or not use_user_lines:
                    away.set_default_lineup()

                home_coach_controls = home.name != user_team_name or not use_user_lines
                away_coach_controls = away.name != user_team_name or not use_user_lines
                if home_coach_controls:
                    home_goalie = self._coach_choose_starting_goalie(
                        home,
                        playoff_mode=False,
                        played_yesterday=(home.name in played_yesterday),
                    )
                    home.set_starting_goalie(home_goalie.name if home_goalie is not None else None)
                if away_coach_controls:
                    away_goalie = self._coach_choose_starting_goalie(
                        away,
                        playoff_mode=False,
                        played_yesterday=(away.name in played_yesterday),
                    )
                    away.set_starting_goalie(away_goalie.name if away_goalie is not None else None)

                home_strategy = home.coach_style
                away_strategy = away.coach_style
                if home.name == user_team_name and use_user_strategy:
                    home_strategy = user_strategy
                if away.name == user_team_name and use_user_strategy:
                    away_strategy = user_strategy
                home_off_bonus, home_def_bonus, home_injury_mult = self._coach_modifiers(home, home_strategy, away)
                away_off_bonus, away_def_bonus, away_injury_mult = self._coach_modifiers(away, away_strategy, home)
                if home.name == user_team_name:
                    position_penalty = home.lineup_position_penalty()
                    home_off_bonus -= position_penalty * 0.45
                    home_def_bonus -= position_penalty * 0.50
                if away.name == user_team_name:
                    position_penalty = away.lineup_position_penalty()
                    away_off_bonus -= position_penalty * 0.45
                    away_def_bonus -= position_penalty * 0.50
                home_sched_bonus, home_sched_injury = self._schedule_context_modifiers(
                    home, away, played_yesterday, is_away=False
                )
                away_sched_bonus, away_sched_injury = self._schedule_context_modifiers(
                    away, home, played_yesterday, is_away=True
                )
                home_off_bonus += home_sched_bonus
                away_off_bonus += away_sched_bonus
                home_injury_mult *= home_sched_injury
                away_injury_mult *= away_sched_injury
                result = simulate_game(
                    home=home,
                    away=away,
                    home_strategy=home_strategy,
                    away_strategy=away_strategy,
                    home_coach_offense_bonus=home_off_bonus,
                    away_coach_offense_bonus=away_off_bonus,
                    home_coach_defense_bonus=home_def_bonus,
                    away_coach_defense_bonus=away_def_bonus,
                    home_context_bonus=0.012,
                    away_context_bonus=-0.006,
                    home_injury_mult=home_injury_mult,
                    away_injury_mult=away_injury_mult,
                    rng=self._rng,
                )
                self._records[home.name].register_game(
                    result.home_goals,
                    result.away_goals,
                    result.overtime,
                    is_home=True,
                    pp_goals=result.home_pp_goals,
                    pp_chances=result.home_pp_chances,
                    pk_goals_against=result.away_pp_goals,
                    pk_chances_against=result.away_pp_chances,
                )
                self._records[away.name].register_game(
                    result.away_goals,
                    result.home_goals,
                    result.overtime,
                    is_home=False,
                    pp_goals=result.away_pp_goals,
                    pp_chances=result.away_pp_chances,
                    pk_goals_against=result.home_pp_goals,
                    pk_chances_against=result.home_pp_chances,
                )
                self._consume_coach_game_effect(home)
                self._consume_coach_game_effect(away)
                day_results.append(result)

            # Post-sim integrity: each scheduled team +1 GP, others unchanged.
            for team_name, rec in self._records.items():
                before = int(gp_before.get(team_name, 0))
                after = int(rec.games_played)
                delta = after - before
                expected = 1 if team_name in scheduled_day_teams else 0
                if delta != expected:
                    raise ValueError(
                        f"Invalid GP delta for {team_name} on day {self.current_day}: "
                        f"delta={delta}, expected={expected}."
                    )
        except Exception:
            self._restore_team_records(records_before)
            raise
        self._day_index += 1
        self._save_state()
        return day_results

    def _create_draft_player(
        self,
        team_name: str,
        position: str,
        quality: float,
        draft_round: int | None = None,
        draft_overall: int | None = None,
    ) -> Player:
        quality = self._clamp(quality, 0.35, 1.0)
        birth_country, birth_country_code = self._sample_birth_country()
        if quality >= 0.82:
            tier = "NHL"
            seasons_to_nhl = 0
        elif quality >= 0.62:
            tier = "AHL"
            seasons_to_nhl = 1
        else:
            tier = "Junior"
            seasons_to_nhl = 2 + (1 if self._rng.random() < 0.33 else 0)

        if self._rng.random() < 0.10 and tier != "NHL":
            tier = "NHL"
            seasons_to_nhl = 0

        shooting = 1.45 + quality * 3.00 + self._rng.uniform(-0.12, 0.12)
        playmaking = 1.45 + quality * 2.95 + self._rng.uniform(-0.12, 0.12)
        defense = 1.55 + quality * 2.90 + self._rng.uniform(-0.10, 0.10)
        physical = 1.60 + quality * 2.55 + self._rng.uniform(-0.12, 0.12)
        durability = 1.95 + quality * 2.25 + self._rng.uniform(-0.12, 0.12)
        goaltending = 0.3
        if position == "G":
            goaltending = 2.00 + quality * 2.65 + self._rng.uniform(-0.10, 0.10)
            shooting = 0.4
            playmaking = 0.95 + quality * 1.55 + self._rng.uniform(-0.10, 0.10)
        return Player(
            team_name=team_name,
            name=self._name_generator.next_name(birth_country_code),
            position=position,
            birth_country=birth_country,
            birth_country_code=birth_country_code,
            shooting=shooting,
            playmaking=playmaking,
            defense=defense,
            goaltending=goaltending,
            physical=physical,
            durability=durability,
            age=18 + self._rng.randrange(0, 3),
            prime_age=self._rng.randint(self.prime_age_min - 1, self.prime_age_max + 1),
            draft_season=self.season_number,
            draft_round=draft_round,
            draft_overall=draft_overall,
            draft_team=team_name,
            prospect_tier=tier,
            seasons_to_nhl=seasons_to_nhl,
            prospect_potential=self._clamp(0.42 + quality * 0.55 + self._rng.uniform(-0.08, 0.08), 0.25, 0.98),
            prospect_boom_chance=self._clamp(0.05 + quality * 0.08 + self._rng.uniform(-0.02, 0.03), 0.03, 0.22),
            prospect_bust_chance=self._clamp(0.16 - quality * 0.10 + self._rng.uniform(-0.03, 0.03), 0.04, 0.24),
            prospect_resolved=False,
            contract_years_left=3,
            cap_hit=0.95 + quality * 0.45,
            contract_type="entry",
            is_rfa=True,
        )

    def _clear_season_player_stats(self) -> None:
        def _reset(player: Player) -> None:
            player.games_played = 0
            player.goals = 0
            player.assists = 0
            player.injuries = 0
            player.games_missed_injury = 0
            player.injured_games_remaining = 0
            player.goalie_games = 0
            player.goalie_wins = 0
            player.goalie_losses = 0
            player.goalie_ot_losses = 0
            player.goalie_shutouts = 0
            player.shots_against = 0
            player.saves = 0
            player.goals_against = 0

        for team in self.teams:
            for player in [*team.roster, *team.minor_roster]:
                _reset(player)

        # Free agents persist across seasons; clear their live season stats too.
        for player in self.free_agents:
            _reset(player)

    def _record_career_season_stats(self, completed_season: int) -> None:
        for team in self.teams:
            team_record = self._records.get(team.name)
            team_goal_diff = float(team_record.goal_diff) if team_record is not None else 0.0
            for player in [*team.roster, *team.minor_roster]:
                entry = self._build_career_season_entry(
                    player=player,
                    completed_season=completed_season,
                    team_name=team.name,
                    team_goal_diff=team_goal_diff,
                )
                player.career_seasons.append(entry)
                self.career_history[player.player_id] = list(player.career_seasons)

    def _build_career_season_entry(
        self,
        player: Player,
        completed_season: int,
        team_name: str,
        team_goal_diff: float,
    ) -> dict[str, object]:
        gp = max(1, int(player.games_played))
        position = player.position
        if position == "D":
            toi_per_game = 18.0 + player.defense * 1.55 + player.playmaking * 0.25
        elif position == "G":
            toi_per_game = 0.0
        else:
            toi_per_game = 11.2 + player.scoring_weight * 2.05 + player.defense * 0.35
        toi_per_game = round(max(0.0, min(30.0, toi_per_game)), 1)

        shot_rate = 1.15 + player.shooting * 0.68 + (0.18 if position in {"C", "LW", "RW"} else (-0.22 if position == "D" else -0.65))
        shots = max(player.goals, int(round(gp * max(0.4, shot_rate))))
        shot_pct = (player.goals / shots * 100.0) if shots > 0 else 0.0
        pp_share = min(0.68, max(0.12, 0.26 + (player.playmaking + player.shooting - 5.2) * 0.07))
        pp_points = min(player.points, int(round(player.points * pp_share)))
        goal_share = player.goals / max(1, player.points)
        ppg = min(player.goals, int(round(pp_points * goal_share * 0.92)))
        ppa = max(0, pp_points - ppg)
        sh_cap = max(0, player.points - pp_points)
        sh_points = min(sh_cap, int(round(gp * max(0.0, 0.02 + player.defense * 0.03))))
        shg = min(player.goals - ppg, max(0, int(round(sh_points * goal_share))))
        sha = max(0, sh_points - shg)
        plus_minus = int(round((player.points / gp - 0.55) * gp * 0.34 + team_goal_diff * 0.18))
        pim = int(round(gp * (0.24 + player.physical * 0.40)))

        return {
            "season": completed_season,
            "team": team_name,
            "age": player.age,
            "position": player.position,
            "birth_country": player.birth_country,
            "birth_country_code": player.birth_country_code,
            "gp": player.games_played,
            "g": player.goals,
            "a": player.assists,
            "p": player.points,
            "injuries": player.injuries,
            "games_missed": player.games_missed_injury,
            "goalie_gp": player.goalie_games,
            "goalie_w": player.goalie_wins,
            "goalie_l": player.goalie_losses,
            "goalie_otl": player.goalie_ot_losses,
            "goalie_so": player.goalie_shutouts,
            "plus_minus": plus_minus,
            "pim": pim,
            "toi_g": toi_per_game,
            "ppg": ppg,
            "ppa": ppa,
            "shg": shg,
            "sha": sha,
            "shots": shots,
            "shot_pct": round(shot_pct, 1),
            "gaa": round(player.gaa, 2),
            "sv_pct": round(player.save_pct, 3),
            "rating_shooting": round(player.shooting, 2),
            "rating_playmaking": round(player.playmaking, 2),
            "rating_defense": round(player.defense, 2),
            "rating_goaltending": round(player.goaltending, 2),
            "rating_physical": round(player.physical, 2),
            "rating_durability": round(player.durability, 2),
            "draft_season": player.draft_season,
            "draft_round": player.draft_round,
            "draft_overall": player.draft_overall,
            "draft_team": player.draft_team,
        }

    def snapshot_trade_season_split(self, player: Player, from_team_name: str) -> None:
        played_any = (
            int(player.games_played) > 0
            or int(player.goalie_games) > 0
            or int(player.goals) > 0
            or int(player.assists) > 0
            or int(player.goalie_wins) > 0
            or int(player.games_missed_injury) > 0
            or int(player.injuries) > 0
        )
        if not played_any:
            return
        team_record = self._records.get(from_team_name)
        team_goal_diff = float(team_record.goal_diff) if team_record is not None else 0.0
        entry = self._build_career_season_entry(
            player=player,
            completed_season=int(self.season_number),
            team_name=from_team_name,
            team_goal_diff=team_goal_diff,
        )
        player.career_seasons.append(entry)
        self.career_history[player.player_id] = list(player.career_seasons)
        player.games_played = 0
        player.goals = 0
        player.assists = 0
        player.injuries = 0
        player.games_missed_injury = 0
        player.goalie_games = 0
        player.goalie_wins = 0
        player.goalie_losses = 0
        player.goalie_ot_losses = 0
        player.goalie_shutouts = 0
        player.shots_against = 0
        player.saves = 0
        player.goals_against = 0

    def _clamp(self, value: float, low: float, high: float = 5.0) -> float:
        return min(high, max(low, value))

    def _sample_birth_country(self) -> tuple[str, str]:
        roll = self._rng.random()
        cumulative = 0.0
        for country, code, weight in PLAYER_BIRTH_COUNTRIES:
            cumulative += weight
            if roll <= cumulative:
                return country, code
        country, code, _weight = PLAYER_BIRTH_COUNTRIES[0]
        return country, code

    def set_draft_focus(self, team_name: str, focus: str) -> str:
        normalized = focus.strip().lower()
        if normalized not in self.DRAFT_FOCUS_OPTIONS:
            raise ValueError(f"Invalid draft focus '{focus}'")
        if normalized == "auto":
            self.draft_focus_by_team.pop(team_name, None)
        else:
            self.draft_focus_by_team[team_name] = normalized
        self._save_state()
        return self.get_draft_focus(team_name)

    def get_draft_focus(self, team_name: str) -> str:
        return self.draft_focus_by_team.get(team_name, "auto")

    def _team_focus_position(self, team: Team) -> str | None:
        focus = self.get_draft_focus(team.name)
        if focus == "auto":
            return None
        if focus == "f":
            return self._rng.choice(["C", "LW", "RW"])
        if focus in {"c", "lw", "rw", "d", "g"}:
            return focus.upper()
        return None

    def _promote_from_minors(self, team: Team, player: Player, replacement_for: str = "") -> bool:
        if player not in team.minor_roster:
            return False
        def _value(p: Player) -> float:
            if p.position in GOALIE_POSITIONS:
                return p.goaltending * 0.72 + p.durability * 0.18 + p.defense * 0.10
            return p.shooting * 0.38 + p.playmaking * 0.32 + p.defense * 0.22 + p.physical * 0.08

        def _demotion_priority(candidate: Player, incoming_position: str) -> int:
            if incoming_position in GOALIE_POSITIONS:
                return 0 if candidate.position not in GOALIE_POSITIONS else 1
            if incoming_position in DEFENSE_POSITIONS:
                if candidate.position in FORWARD_POSITIONS:
                    return 0
                if candidate.position in DEFENSE_POSITIONS:
                    return 1
                return 2
            if candidate.position in DEFENSE_POSITIONS:
                return 0
            if candidate.position in FORWARD_POSITIONS:
                return 1
            return 2

        active_count = len([p for p in team.roster if not p.is_injured])
        if active_count >= Team.MAX_ROSTER_SIZE:
            healthy_goalies = len([p for p in team.roster if p.position in GOALIE_POSITIONS and not p.is_injured])
            demote_candidates = [
                p
                for p in team.roster
                if not p.is_injured and (p.position not in GOALIE_POSITIONS or healthy_goalies > 1)
            ]
            if player.position in GOALIE_POSITIONS:
                non_goalie = [p for p in demote_candidates if p.position not in GOALIE_POSITIONS]
                if non_goalie:
                    demote_candidates = non_goalie
            demote = min(
                demote_candidates,
                key=lambda p: (
                    _demotion_priority(p, player.position),
                    _value(p),
                    -p.age,
                    p.name,
                ),
                default=None,
            )

            if demote is None:
                return False
            team.roster.remove(demote)
            team.minor_roster.append(demote)
            team.dressed_player_names.discard(demote.name)
            if team.starting_goalie_name == demote.name:
                team.starting_goalie_name = None
        team.minor_roster.remove(player)
        player.team_name = team.name
        player.temporary_replacement_for = replacement_for.strip()
        team.roster.append(player)
        return True

    def promote_minor_player(self, team_name: str, player_name: str, replacement_for: str = "") -> bool:
        team = self.get_team(team_name)
        if team is None:
            return False
        player = next((p for p in team.minor_roster if p.name == player_name), None)
        if player is None:
            return False
        moved = self._promote_from_minors(team, player, replacement_for=replacement_for)
        if not moved:
            return False
        self._assign_team_player_numbers(team)
        team.set_default_lineup()
        self._ensure_team_leadership()
        self._save_state()
        return True

    def demote_roster_player(self, team_name: str, player_name: str) -> bool:
        team = self.get_team(team_name)
        if team is None:
            return False
        player = next((p for p in team.roster if p.name == player_name), None)
        if player is None:
            return False

        healthy_goalies = len([p for p in team.roster if p.position in GOALIE_POSITIONS and not p.is_injured])

        if not player.is_injured:
            if player.position in GOALIE_POSITIONS and healthy_goalies <= 1:
                return False

        team.roster.remove(player)
        player.temporary_replacement_for = ""
        team.minor_roster.append(player)
        team.dressed_player_names.discard(player.name)
        if team.starting_goalie_name == player.name:
            team.starting_goalie_name = None
        self._assign_team_player_numbers(team)
        team.set_default_lineup()
        self._ensure_team_leadership()
        self._save_state()
        return True

    def _ensure_team_depth(self, team: Team) -> None:
        if not team.minor_roster:
            self._ensure_team_leadership()
            return

        needs_payload = self.get_team_needs(team.name)
        scores = needs_payload.get("scores", {}) if isinstance(needs_payload, dict) else {}
        target = str(needs_payload.get("target_position", "ANY")) if isinstance(needs_payload, dict) else "ANY"

        def _healthy_count(pool: list[Player], positions: set[str]) -> int:
            return len([p for p in pool if p.position in positions and not p.is_injured])

        def _fill_goalies() -> None:
            while _healthy_count(team.roster, GOALIE_POSITIONS) < Team.DRESSED_GOALIES:
                candidates = [p for p in team.minor_roster if p.position in GOALIE_POSITIONS and not p.is_injured]
                if not candidates:
                    break
                promote = max(candidates, key=lambda p: p.goaltending)
                injured_goalies = [p for p in team.roster if p.position in GOALIE_POSITIONS and p.is_injured]
                replacement_for = injured_goalies[0].name if injured_goalies else ""
                if not self._promote_from_minors(team, promote, replacement_for=replacement_for):
                    break

        def _fill_forwards() -> None:
            while _healthy_count(team.roster, FORWARD_POSITIONS) < Team.DRESSED_FORWARDS:
                candidates = [p for p in team.minor_roster if p.position in FORWARD_POSITIONS and not p.is_injured]
                if not candidates:
                    break
                if float(scores.get("top6_f", 0.0)) >= float(scores.get("depth_f", 0.0)):
                    promote = max(candidates, key=lambda p: (p.shooting + p.playmaking + p.defense))
                else:
                    promote = max(candidates, key=lambda p: (p.defense + p.durability + p.physical))
                injured_forwards = [p for p in team.roster if p.position in FORWARD_POSITIONS and p.is_injured]
                replacement_for = injured_forwards[0].name if injured_forwards else ""
                if not self._promote_from_minors(team, promote, replacement_for=replacement_for):
                    break

        def _fill_defense() -> None:
            while _healthy_count(team.roster, DEFENSE_POSITIONS) < Team.DRESSED_DEFENSE:
                candidates = [p for p in team.minor_roster if p.position in DEFENSE_POSITIONS and not p.is_injured]
                if not candidates:
                    break
                promote = max(candidates, key=lambda p: (p.defense + p.playmaking + p.physical))
                injured_defense = [p for p in team.roster if p.position in DEFENSE_POSITIONS and p.is_injured]
                replacement_for = injured_defense[0].name if injured_defense else ""
                if not self._promote_from_minors(team, promote, replacement_for=replacement_for):
                    break

        ordered_fillers = []
        if target == "G":
            ordered_fillers = [_fill_goalies, _fill_defense, _fill_forwards]
        elif target == "D":
            ordered_fillers = [_fill_defense, _fill_goalies, _fill_forwards]
        elif target == "F":
            ordered_fillers = [_fill_forwards, _fill_goalies, _fill_defense]
        else:
            ordered_fillers = [_fill_goalies, _fill_forwards, _fill_defense]

        for fill in ordered_fillers:
            fill()

        # Safety pass to ensure minimum dressed structure is met.
        _fill_goalies()
        _fill_forwards()
        _fill_defense()

        team.set_default_lineup()
        self._ensure_team_leadership()

    def _apply_injury_wear(self, player: Player) -> None:
        season_injuries = max(0, player.injuries)
        season_games_missed = max(0, player.games_missed_injury)
        recent = player.career_seasons[-3:]
        recent_injuries = sum(int(row.get("injuries", 0)) for row in recent)
        recent_games_missed = sum(int(row.get("games_missed", 0)) for row in recent)

        # Baseline wear rises with both severity (games missed) and repeat injuries.
        wear_score = (
            season_injuries * 0.48
            + (season_games_missed / 7.0) * 0.34
            + recent_injuries * 0.10
            + (recent_games_missed / 35.0) * 0.08
        )
        if wear_score <= 0.25:
            return

        major_season = season_games_missed >= 20 or season_injuries >= 3
        repeat_history = recent_games_missed >= 35 or recent_injuries >= 5
        volatility = self._rng.uniform(0.92, 1.10)
        impact = wear_score * 0.030 * volatility
        if major_season:
            impact *= 1.28
        if repeat_history:
            impact *= 1.22

        durability_drop = impact * (1.28 + 0.08 * season_injuries)
        physical_drop = impact * (0.70 + 0.02 * season_games_missed)

        player.durability = self._clamp(player.durability - durability_drop, 0.6)
        player.physical = self._clamp(player.physical - physical_drop, 0.7)

        if player.position in GOALIE_POSITIONS:
            goalie_drop = impact * (0.74 + 0.03 * season_injuries)
            defense_drop = impact * (0.34 + 0.01 * season_games_missed)
            player.goaltending = self._clamp(player.goaltending - goalie_drop, 0.6)
            player.defense = self._clamp(player.defense - defense_drop, 0.7)
            player.playmaking = self._clamp(player.playmaking - impact * 0.16, 0.7)
        else:
            skill_drop = impact * (0.42 + 0.015 * season_injuries)
            defense_drop = impact * (0.36 + 0.010 * season_games_missed)
            player.shooting = self._clamp(player.shooting - skill_drop, 0.7)
            player.playmaking = self._clamp(player.playmaking - skill_drop * 0.92, 0.7)
            player.defense = self._clamp(player.defense - defense_drop, 0.7)
            player.goaltending = self._clamp(player.goaltending - impact * 0.04, 0.3)

    def _apply_aging_curve(self, player: Player, team: Team, team_games: int) -> None:
        age = player.age
        goalie = player.position in GOALIE_POSITIONS
        team_games = max(1, team_games)
        usage_ratio = (player.goalie_games / team_games) if goalie else (player.games_played / team_games)
        coach_quality = max(0.0, min(1.0, (team.coach_rating - 2.0) / 3.0))
        goalie_dev_quality = max(0.0, min(1.0, (team.coach_goalie_dev - 2.0) / 3.0))
        churn_penalty = min(0.20, max(0.0, team.coach_changes_recent) * 0.035)

        if age <= 20:
            dev = 0.10 if not goalie else 0.08
        elif age <= 22:
            dev = 0.07 if not goalie else 0.06
        elif age <= 24:
            dev = 0.04 if not goalie else 0.05
        elif age <= 27:
            dev = 0.015 if not goalie else 0.02
        elif age <= 29:
            dev = 0.0 if not goalie else 0.01
        elif age <= 32:
            dev = -0.025 if not goalie else -0.015
        elif age <= 35:
            dev = -0.05 if not goalie else -0.03
        else:
            dev = -0.08 if not goalie else -0.05

        shift = dev + self._rng.uniform(-0.012, 0.012)
        shift *= 0.92 + coach_quality * 0.22

        if age <= 24:
            if usage_ratio >= 0.65:
                shift += 0.020 + coach_quality * 0.010
            elif usage_ratio >= 0.45:
                shift += 0.008 + coach_quality * 0.006
            elif usage_ratio <= 0.22:
                shift -= 0.018 + (1.0 - coach_quality) * 0.010
            if churn_penalty > 0:
                shift -= churn_penalty * 0.65
        elif age <= 29:
            if usage_ratio <= 0.25:
                shift -= 0.004
        else:
            if usage_ratio >= 0.78:
                shift -= 0.008

        if player.seasons_to_nhl > 0:
            # Prospect tracks mostly develop off-NHL usage until they are ready.
            minor_dev = 0.010 + player.prospect_potential * 0.028 + coach_quality * 0.010
            if player.prospect_tier == "Junior":
                minor_dev += 0.006
            elif player.prospect_tier == "AHL":
                minor_dev += 0.003
            shift += minor_dev
            if usage_ratio >= 0.45:
                # Rushing prospects into heavy NHL usage can hurt growth.
                shift -= 0.012 + (0.55 - min(0.55, coach_quality * 0.55))
            player.seasons_to_nhl = max(0, player.seasons_to_nhl - 1)

        if player.seasons_to_nhl == 0 and not player.prospect_resolved and age <= 24:
            # One-time boom/bust transition when prospect becomes NHL-ready.
            coach_dev = max(0.0, min(1.0, (team.coach_goalie_dev - 2.0) / 3.0))
            boom = self._clamp(player.prospect_boom_chance + coach_dev * 0.05, 0.02, 0.30)
            bust = self._clamp(player.prospect_bust_chance - coach_dev * 0.05, 0.01, 0.24)
            roll = self._rng.random()
            if roll < boom:
                shift += 0.050 + player.prospect_potential * 0.035
            elif roll < boom + bust:
                shift -= 0.045 + (0.55 - player.prospect_potential) * 0.030
            player.prospect_resolved = True

        if goalie:
            shift *= 0.94 + goalie_dev_quality * 0.18
            player.goaltending = min(5.0, max(0.8, player.goaltending + shift * 1.2))
            player.defense = min(5.0, max(0.8, player.defense + shift * 0.6))
            player.playmaking = min(5.0, max(0.8, player.playmaking + shift * 0.4))
            player.shooting = min(5.0, max(0.4, player.shooting + shift * 0.1))
            player.physical = min(5.0, max(0.8, player.physical + shift * 0.5))
        else:
            player.shooting = min(5.0, max(0.8, player.shooting + shift * 1.0))
            player.playmaking = min(5.0, max(0.8, player.playmaking + shift * 0.9))
            player.defense = min(5.0, max(0.8, player.defense + shift * 0.8))
            player.goaltending = min(5.0, max(0.3, player.goaltending + shift * 0.05))
            player.physical = min(5.0, max(0.8, player.physical + shift * 0.75))
        player.durability = min(5.0, max(0.8, player.durability + shift * 0.6))

    def _should_retire_jersey(self, player: Player, team_name: str) -> bool:
        seasons = list(player.career_seasons)
        if not seasons:
            return False
        team_seasons = [s for s in seasons if str(s.get("team", "")) == team_name]
        if len(team_seasons) < 6:
            return False
        gp = sum(int(s.get("gp", 0)) for s in team_seasons)
        goals = sum(int(s.get("g", 0)) for s in team_seasons)
        assists = sum(int(s.get("a", 0)) for s in team_seasons)
        points = goals + assists
        goalie_gp = sum(int(s.get("goalie_gp", 0)) for s in team_seasons)
        goalie_w = sum(int(s.get("goalie_w", 0)) for s in team_seasons)
        goalie_so = sum(int(s.get("goalie_so", 0)) for s in team_seasons)
        cups = self._cup_count_for_team_up_to_season(team_name, self.season_number)

        if player.position in GOALIE_POSITIONS:
            if goalie_w >= 350 or goalie_so >= 55:
                return True
            if goalie_gp >= 450 and (goalie_w >= 250 or goalie_so >= 35):
                return True
            if cups >= 2 and goalie_w >= 220:
                return True
            return False

        if points >= 950 or goals >= 500:
            return True
        if gp >= 700 and (points >= 650 or goals >= 280):
            return True
        if cups >= 2 and points >= 620:
            return True
        return False

    def _retire_jersey_if_eligible(self, team: Team, player: Player) -> dict[str, object] | None:
        if player.jersey_number is None:
            return None
        number = int(player.jersey_number)
        if not (1 <= number <= 99):
            return None
        if number in self._retired_number_set(team):
            return None
        if not self._should_retire_jersey(player, team.name):
            return None
        entry = {
            "season": self.season_number,
            "number": number,
            "player": player.name,
            "team": team.name,
            "kind": "retired_number",
            "title": f"Number {number} Retired",
        }
        team.retired_numbers.append(entry)
        return entry

    def _cup_count_for_team_up_to_season(self, team_name: str, season_no: int) -> int:
        total = 0
        for season in self.season_history:
            if not isinstance(season, dict):
                continue
            s_no = int(season.get("season", 0))
            if s_no > season_no:
                continue
            playoffs = season.get("playoffs", {})
            if not isinstance(playoffs, dict):
                continue
            champion = str(playoffs.get("champion") or playoffs.get("cup_champion") or "").strip()
            if champion == team_name:
                total += 1
        return total

    def _age_and_retire_players(self) -> tuple[list[str], list[dict[str, object]]]:
        retired: list[str] = []
        retired_numbers: list[dict[str, object]] = []
        for team in self.teams:
            team_games = self._records.get(team.name, TeamRecord(team=team)).games_played
            remaining: list[Player] = []
            minor_remaining: list[Player] = []
            for player in [*team.roster, *team.minor_roster]:
                player.age += 1
                self._apply_injury_wear(player)
                self._apply_aging_curve(player, team, team_games)

                retire_prob = 0.0
                if player.position in GOALIE_POSITIONS:
                    if player.age >= 37:
                        retire_prob = min(0.90, 0.08 + (player.age - 37) * 0.10)
                    elif player.age >= 34:
                        retire_prob = 0.03 + (player.age - 34) * 0.025
                else:
                    if player.age >= 35:
                        retire_prob = min(0.92, 0.10 + (player.age - 35) * 0.12)
                    elif player.age >= 32:
                        retire_prob = 0.03 + (player.age - 32) * 0.03
                if self._rng.random() < retire_prob:
                    retired.append(f"{player.name} ({team.name})")
                    self._add_hall_of_fame_entry(player, team.name, self.season_number)
                    team.dressed_player_names.discard(player.name)
                    retired_number = self._retire_jersey_if_eligible(team, player)
                    if retired_number is not None:
                        retired_numbers.append(retired_number)
                else:
                    if player in team.roster:
                        remaining.append(player)
                    else:
                        minor_remaining.append(player)
            team.roster = remaining
            team.minor_roster = minor_remaining
        return retired, retired_numbers

    def _add_hall_of_fame_entry(self, player: Player, team_name: str, retired_after_season: int) -> None:
        seasons = list(player.career_seasons)
        total_gp = sum(int(s.get("gp", 0)) for s in seasons)
        total_g = sum(int(s.get("g", 0)) for s in seasons)
        total_a = sum(int(s.get("a", 0)) for s in seasons)
        total_p = sum(int(s.get("p", 0)) for s in seasons)
        total_inj = sum(int(s.get("injuries", 0)) for s in seasons)
        total_missed = sum(int(s.get("games_missed", 0)) for s in seasons)
        total_ggp = sum(int(s.get("goalie_gp", 0)) for s in seasons)
        total_gw = sum(int(s.get("goalie_w", 0)) for s in seasons)
        total_gl = sum(int(s.get("goalie_l", 0)) for s in seasons)
        total_gotl = sum(int(s.get("goalie_otl", 0)) for s in seasons)
        first_season = min([int(s.get("season", retired_after_season)) for s in seasons], default=retired_after_season)
        last_season = max([int(s.get("season", retired_after_season)) for s in seasons], default=retired_after_season)
        goalie_gaa = 0.0
        goalie_sv = 0.0
        if total_ggp > 0:
            weighted_gaa = sum(float(s.get("gaa", 0.0)) * max(1, int(s.get("goalie_gp", 0))) for s in seasons)
            weighted_sv = sum(float(s.get("sv_pct", 0.0)) * max(1, int(s.get("goalie_gp", 0))) for s in seasons)
            goalie_gaa = round(weighted_gaa / total_ggp, 2)
            goalie_sv = round(weighted_sv / total_ggp, 3)

        entry = {
            "player_id": player.player_id,
            "name": player.name,
            "team_at_retirement": team_name,
            "position": player.position,
            "retired_after_season": retired_after_season,
            "age_at_retirement": player.age,
            "seasons_played": len(seasons),
            "first_season": first_season,
            "last_season": last_season,
            "career_gp": total_gp,
            "career_g": total_g,
            "career_a": total_a,
            "career_p": total_p,
            "career_injuries": total_inj,
            "career_games_missed": total_missed,
            "goalie_gp": total_ggp,
            "goalie_w": total_gw,
            "goalie_l": total_gl,
            "goalie_otl": total_gotl,
            "goalie_gaa": goalie_gaa,
            "goalie_sv_pct": goalie_sv,
            "seasons": seasons,
        }
        self.hall_of_fame = [e for e in self.hall_of_fame if str(e.get("player_id", "")) != player.player_id]
        self.hall_of_fame.append(entry)

    def _choose_draft_position(self, team: Team) -> str:
        focus_position = self._team_focus_position(team)
        if focus_position is not None and self._rng.random() < 0.82:
            return focus_position
        org_players = [*team.roster, *team.minor_roster]
        counts = {
            "F": len([p for p in org_players if p.position in FORWARD_POSITIONS]),
            "D": len([p for p in org_players if p.position in DEFENSE_POSITIONS]),
            "G": len([p for p in org_players if p.position in GOALIE_POSITIONS]),
        }
        if counts["G"] < 2:
            return "G"
        if counts["D"] < 7:
            return "D"
        return "C" if self._rng.random() < 0.45 else ("LW" if self._rng.random() < 0.5 else "RW")

    def _draft_quality_for_pick(self, overall_pick: int, total_teams: int) -> float:
        # Worst teams pick earlier, but individual outcomes still vary (busts/steals).
        normalized = (overall_pick - 1) / max(1, total_teams - 1)
        baseline = 0.90 - normalized * 0.34
        noise = self._rng.uniform(-0.07, 0.07)
        bust_roll = self._rng.random()
        if bust_roll < 0.10:
            noise -= self._rng.uniform(0.06, 0.13)
        elif bust_roll > 0.90:
            noise += self._rng.uniform(0.04, 0.10)
        return self._clamp(baseline + noise, 0.35, 0.99)

    def _run_draft(self) -> tuple[dict[str, list[str]], dict[str, list[dict[str, object]]]]:
        drafted: dict[str, list[str]] = {}
        drafted_name_set: dict[str, set[str]] = {}
        draft_details: dict[str, list[dict[str, object]]] = {}
        standings_worst_to_best = list(reversed(self.get_standings()))
        total_teams = len(standings_worst_to_best)

        # Round 1: strict reverse-standings order with numbered picks.
        for pick_idx, rec in enumerate(standings_worst_to_best, start=1):
            team = rec.team
            drafted.setdefault(team.name, [])
            drafted_name_set.setdefault(team.name, set())
            draft_details.setdefault(team.name, [])
            position = self._choose_draft_position(team)
            drafted_player = self._create_draft_player(
                team_name=team.name,
                position=position,
                quality=self._draft_quality_for_pick(pick_idx, total_teams),
                draft_round=1,
                draft_overall=pick_idx,
            )
            team.minor_roster.append(drafted_player)
            drafted[team.name].append(drafted_player.name)
            drafted_name_set[team.name].add(drafted_player.name)
            draft_details[team.name].append(
                {
                    "name": drafted_player.name,
                    "position": drafted_player.position,
                    "country": drafted_player.birth_country,
                    "country_code": drafted_player.birth_country_code,
                    "round": 1,
                    "overall": pick_idx,
                }
            )

        # Keep NHL roster filled to cap with best available players from minors/free-agents.
        for rec in standings_worst_to_best:
            team = rec.team
            drafted.setdefault(team.name, [])
            drafted_name_set.setdefault(team.name, set())
            draft_details.setdefault(team.name, [])
            while len(team.roster) < Team.MAX_ROSTER_SIZE and team.minor_roster:
                if len([p for p in team.roster if p.position in GOALIE_POSITIONS]) < 2:
                    promote_pool = [p for p in team.minor_roster if p.position in GOALIE_POSITIONS]
                    if not promote_pool:
                        promote_pool = list(team.minor_roster)
                else:
                    promote_pool = list(team.minor_roster)
                promote = max(
                    promote_pool,
                    key=lambda p: (
                        p.goaltending if p.position in GOALIE_POSITIONS else (p.shooting + p.playmaking + p.defense),
                        p.durability,
                    ),
                )
                self._promote_from_minors(team, promote, replacement_for="")

            while len(team.roster) < Team.MAX_ROSTER_SIZE:
                position = self._choose_draft_position(team)
                drafted_player = self._create_draft_player(
                    team_name=team.name,
                    position=position,
                    quality=self._rng.uniform(0.42, 0.74),
                )
                team.roster.append(drafted_player)
                drafted[team.name].append(drafted_player.name)
                drafted_name_set[team.name].add(drafted_player.name)
                draft_details[team.name].append(
                    {
                        "name": drafted_player.name,
                        "position": drafted_player.position,
                        "country": drafted_player.birth_country,
                        "country_code": drafted_player.birth_country_code,
                        "round": None,
                        "overall": None,
                    }
                )

            while len(team.minor_roster) < Team.MIN_MINOR_ROSTER_SIZE:
                position = self._choose_draft_position(team)
                depth_player = self._create_draft_player(
                    team_name=team.name,
                    position=position,
                    quality=self._rng.uniform(0.38, 0.68),
                )
                team.minor_roster.append(depth_player)

            while len(team.roster) > Team.MAX_ROSTER_SIZE:
                # Remove weakest aging player first to maintain cap after guaranteed draft picks.
                protected = drafted_name_set.get(team.name, set())
                cut_pool = [p for p in team.roster if p.name not in protected]
                if not cut_pool:
                    cut_pool = list(team.roster)
                cut_player = min(cut_pool, key=lambda p: (p.shooting + p.playmaking + p.defense + p.goaltending + p.durability, -p.age))
                team.roster.remove(cut_player)
                team.dressed_player_names.discard(cut_player.name)
                if team.starting_goalie_name == cut_player.name:
                    team.starting_goalie_name = None
                team.minor_roster.append(cut_player)
            team.set_default_lineup()

        return (
            {team_name: picks for team_name, picks in drafted.items() if picks},
            {team_name: rows for team_name, rows in draft_details.items() if rows},
        )

    def _contract_player_value(self, player: Player) -> float:
        if player.position in GOALIE_POSITIONS:
            return player.goaltending * 0.72 + player.durability * 0.18 + player.defense * 0.10
        return player.shooting * 0.38 + player.playmaking * 0.32 + player.defense * 0.22 + player.physical * 0.08

    def _assign_contract_terms(self, player: Player, years: int, cap_hit: float, contract_type: str, is_rfa: bool) -> None:
        player.contract_years_left = max(1, int(years))
        player.cap_hit = round(max(0.65, float(cap_hit)), 2)
        player.contract_type = contract_type
        player.is_rfa = bool(is_rfa)

    def _estimate_contract_offer(self, player: Player) -> tuple[int, float, str, bool]:
        value = self._contract_player_value(player)
        if player.age <= 23:
            years = 3
            contract_type = "entry"
            cap = 0.9 + value * 0.18
            return years, cap, contract_type, True
        if player.age <= 27:
            years = 3 if value >= 2.95 else 2
            contract_type = "bridge" if value < 3.3 else "core"
            cap = 1.15 + value * 0.34
            return years, cap, contract_type, False
        if player.age <= 31:
            years = 3 if value >= 3.35 else 2
            contract_type = "core" if value >= 3.35 else "veteran"
            cap = 1.35 + value * 0.36
            return years, cap, contract_type, False
        years = 1 if player.age >= 35 else 2
        contract_type = "veteran"
        cap = 0.95 + value * 0.29
        return years, cap, contract_type, False

    def _team_cap_limit(self, team: Team) -> float:
        return 86.0

    def _team_cap_used(self, team: Team) -> float:
        return round(sum(float(getattr(p, "cap_hit", 0.0)) for p in [*team.roster, *team.minor_roster]), 2)

    def _goalie_value(self, player: Player) -> float:
        return player.goaltending * 0.72 + player.durability * 0.18 + player.defense * 0.10

    def _team_point_pct(self, team: Team) -> float:
        rec = self._records.get(team.name)
        if rec is None or rec.games_played <= 0:
            return 0.5
        return rec.point_pct

    def _raw_team_needs(self, team: Team) -> dict[str, float]:
        active = [p for p in team.roster if not p.is_injured]
        forwards = sorted([p for p in active if p.position in FORWARD_POSITIONS], key=self._contract_player_value, reverse=True)
        defense = sorted([p for p in active if p.position in DEFENSE_POSITIONS], key=self._contract_player_value, reverse=True)
        goalies = sorted([p for p in active if p.position in GOALIE_POSITIONS], key=self._goalie_value, reverse=True)

        def _avg(players: list[Player], n: int, fn) -> float:
            sample = players[:n]
            if not sample:
                return 0.0
            return sum(fn(p) for p in sample) / len(sample)

        top6_f_avg = _avg(forwards, 6, self._contract_player_value)
        top4_d_avg = _avg(defense, 4, self._contract_player_value)
        starter_g = _avg(goalies, 1, self._goalie_value)

        injured_f = len([p for p in team.roster if p.position in FORWARD_POSITIONS and p.is_injured])
        injured_d = len([p for p in team.roster if p.position in DEFENSE_POSITIONS and p.is_injured])
        injured_g = len([p for p in team.roster if p.position in GOALIE_POSITIONS and p.is_injured])

        f_short = max(0, Team.DRESSED_FORWARDS - len(forwards))
        d_short = max(0, Team.DRESSED_DEFENSE - len(defense))
        g_short = max(0, Team.DRESSED_GOALIES - len(goalies))

        f_age = _avg(forwards, 8, lambda p: float(p.age))
        d_age = _avg(defense, 5, lambda p: float(p.age))
        g_age = _avg(goalies, 2, lambda p: float(p.age))

        top6_f = max(0.0, (3.20 - top6_f_avg) * 0.42) + f_short * 0.19 + injured_f * 0.07 + max(0.0, (f_age - 29.5) * 0.03)
        top4_d = max(0.0, (3.25 - top4_d_avg) * 0.45) + d_short * 0.22 + injured_d * 0.08 + max(0.0, (d_age - 30.0) * 0.03)
        starter_g = max(0.0, (3.35 - starter_g) * 0.58) + g_short * 0.32 + injured_g * 0.12 + max(0.0, (g_age - 31.0) * 0.03)
        depth_f = f_short * 0.44 + max(0.0, (2.65 - _avg(forwards, 12, self._contract_player_value)) * 0.22) + injured_f * 0.06
        depth_d = d_short * 0.52 + max(0.0, (2.70 - _avg(defense, 6, self._contract_player_value)) * 0.24) + injured_d * 0.06

        cap_used = self._team_cap_used(team)
        cap_limit = self._team_cap_limit(team)
        cap_ratio = cap_used / max(1e-6, cap_limit)
        old_expensive = len([p for p in team.roster if p.age >= 31 and float(getattr(p, "cap_hit", 0.0)) >= 4.2 and not p.is_injured])
        cap_relief = max(0.0, (cap_ratio - 0.90) * 1.3) + old_expensive * 0.06

        point_pct = self._team_point_pct(team)
        if point_pct >= 0.58:
            top6_f += 0.06
            top4_d += 0.06
            starter_g += 0.05
            cap_relief *= 0.88
        elif point_pct <= 0.45:
            cap_relief += 0.10
            top6_f *= 0.94
            top4_d *= 0.94

        return {
            "top6_f": top6_f,
            "top4_d": top4_d,
            "starter_g": starter_g,
            "depth_f": depth_f,
            "depth_d": depth_d,
            "cap_relief": cap_relief,
        }

    def get_team_needs(self, team_name: str) -> dict[str, object]:
        team = self.get_team(team_name)
        if team is None:
            return {"team": team_name, "scores": {}, "primary_need": "", "window": "balanced", "target_position": "ANY"}
        raw = self._raw_team_needs(team)
        auto_scores = {k: round(max(0.0, min(1.0, float(v))), 3) for k, v in raw.items()}
        config = self.team_needs_by_team.get(team.name, {})
        mode = str(config.get("mode", "auto")).lower()
        if mode == "manual":
            manual_scores = self._normalize_need_scores(config.get("scores", {}))
            scores = {k: float(manual_scores.get(k, auto_scores.get(k, 0.0))) for k in self.TEAM_NEED_KEYS}
            source = "manual"
        else:
            scores = auto_scores
            source = "auto"
        primary_need = max(scores.items(), key=lambda kv: kv[1])[0] if scores else ""
        point_pct = self._team_point_pct(team)
        if point_pct >= 0.60:
            window = "contend"
        elif point_pct <= 0.44:
            window = "retool"
        else:
            window = "balanced"
        target_position = "ANY"
        if primary_need in {"top6_f", "depth_f"}:
            target_position = "F"
        elif primary_need in {"top4_d", "depth_d"}:
            target_position = "D"
        elif primary_need == "starter_g":
            target_position = "G"
        elif primary_need == "cap_relief":
            target_position = "CAP"
        return {
            "team": team.name,
            "scores": scores,
            "auto_scores": auto_scores,
            "primary_need": primary_need,
            "window": window,
            "target_position": target_position,
            "mode": mode if mode in {"auto", "manual"} else "auto",
            "source": source,
        }

    def set_team_needs_override(
        self,
        team_name: str,
        *,
        mode: str = "auto",
        scores: dict[str, float] | None = None,
    ) -> dict[str, object]:
        team = self.get_team(team_name)
        if team is None:
            return {"team": team_name, "scores": {}, "primary_need": "", "window": "balanced", "target_position": "ANY"}
        normalized_mode = str(mode or "auto").lower()
        if normalized_mode not in {"auto", "manual"}:
            normalized_mode = "auto"
        if normalized_mode == "auto":
            self.team_needs_by_team[team.name] = {"mode": "auto"}
        else:
            if scores is None:
                current_auto = self.get_team_needs(team.name).get("auto_scores", {})
                parsed_scores = self._normalize_need_scores(current_auto)
            else:
                parsed_scores = self._normalize_need_scores(scores)
            self.team_needs_by_team[team.name] = {
                "mode": "manual",
                "scores": parsed_scores,
            }
        self._save_state()
        return self.get_team_needs(team.name)

    def _team_fa_needs(self, team: Team) -> dict[str, int]:
        active = [p for p in team.roster if not p.is_injured]
        f_count = len([p for p in active if p.position in FORWARD_POSITIONS])
        d_count = len([p for p in active if p.position in DEFENSE_POSITIONS])
        g_count = len([p for p in active if p.position in GOALIE_POSITIONS])
        total = len(active)
        needs_model = self.get_team_needs(team.name)
        scores = needs_model.get("scores", {}) if isinstance(needs_model, dict) else {}
        return {
            "F": max(0, 12 - f_count),
            "D": max(0, 6 - d_count),
            "G": max(0, 2 - g_count),
            "ANY": max(0, Team.MAX_ROSTER_SIZE - total),
            "score_top6_f": int(round(float(scores.get("top6_f", 0.0)) * 1000)),
            "score_top4_d": int(round(float(scores.get("top4_d", 0.0)) * 1000)),
            "score_starter_g": int(round(float(scores.get("starter_g", 0.0)) * 1000)),
            "score_depth_f": int(round(float(scores.get("depth_f", 0.0)) * 1000)),
            "score_depth_d": int(round(float(scores.get("depth_d", 0.0)) * 1000)),
            "score_cap_relief": int(round(float(scores.get("cap_relief", 0.0)) * 1000)),
        }

    def _can_sign_player(self, team: Team, player: Player, *, max_cap_hit: float | None = None) -> bool:
        if len([p for p in team.roster if not p.is_injured]) >= Team.MAX_ROSTER_SIZE:
            return False
        years, cap_hit, contract_type, is_rfa = self._estimate_contract_offer(player)
        if max_cap_hit is not None and cap_hit > max_cap_hit:
            return False
        cap_space = self._team_cap_limit(team) - self._team_cap_used(team)
        if cap_hit > cap_space:
            return False
        self._assign_contract_terms(player, years=years, cap_hit=cap_hit, contract_type=contract_type, is_rfa=is_rfa)
        return True

    def _run_contract_and_free_agency(self, user_team_name: str | None = None) -> dict[str, object]:
        signings: list[dict[str, object]] = []
        re_signings: list[dict[str, object]] = []
        expiring_free_agents: list[Player] = []
        protected_free_agent_ids: set[str] = set()

        for team in self.teams:
            keep_roster: list[Player] = []
            keep_minors: list[Player] = []
            for player in [*team.roster, *team.minor_roster]:
                player.contract_years_left = max(0, int(player.contract_years_left) - 1)
                if player.contract_years_left > 0:
                    if player in team.roster:
                        keep_roster.append(player)
                    else:
                        keep_minors.append(player)
                    continue

                value = self._contract_player_value(player)
                age_factor = max(0.0, min(1.0, (34 - player.age) / 12.0))
                retain_chance = min(0.92, 0.34 + value * 0.12 + age_factor * 0.22)
                allow_auto_resign = not user_team_name or team.name != user_team_name
                if allow_auto_resign and self._rng.random() < retain_chance:
                    years, cap_hit, contract_type, is_rfa = self._estimate_contract_offer(player)
                    self._assign_contract_terms(player, years=years, cap_hit=cap_hit, contract_type=contract_type, is_rfa=is_rfa)
                    re_signings.append(
                        {
                            "team": team.name,
                            "player": player.name,
                            "years": years,
                            "cap_hit": round(cap_hit, 2),
                        }
                    )
                    if player in team.roster:
                        keep_roster.append(player)
                    else:
                        keep_minors.append(player)
                else:
                    player.free_agent_origin_team = team.name
                    player.team_name = "Free Agents"
                    expiring_free_agents.append(player)
                    if user_team_name and team.name == user_team_name:
                        protected_free_agent_ids.add(player.player_id)
                    team.dressed_player_names.discard(player.name)
                    if team.starting_goalie_name == player.name:
                        team.starting_goalie_name = None

            team.roster = keep_roster
            team.minor_roster = keep_minors

        free_agents = sorted(
            expiring_free_agents,
            key=lambda p: (self._contract_player_value(p), p.age, p.name),
            reverse=True,
        )

        cpu_teams = [t for t in self.teams if not (user_team_name and t.name == user_team_name)]
        max_rounds = 10
        fa_round = 0
        while free_agents and fa_round < max_rounds:
            fa_round += 1
            offers: list[dict[str, object]] = []
            for team in sorted(cpu_teams, key=lambda t: t.name):
                needs = self._team_fa_needs(team)
                if needs["ANY"] <= 0:
                    continue
                cap_space = self._team_cap_limit(team) - self._team_cap_used(team)
                if cap_space < 0.65:
                    continue

                cap_relief_score = needs.get("score_cap_relief", 0) / 1000.0
                score_f = max(needs["F"] * 0.22, needs.get("score_top6_f", 0) / 1000.0, needs.get("score_depth_f", 0) / 1000.0)
                score_d = max(needs["D"] * 0.24, needs.get("score_top4_d", 0) / 1000.0, needs.get("score_depth_d", 0) / 1000.0)
                score_g = max(needs["G"] * 0.30, needs.get("score_starter_g", 0) / 1000.0)
                position_weights = {
                    "C": score_f,
                    "LW": score_f,
                    "RW": score_f,
                    "D": score_d,
                    "G": score_g,
                }
                preferred = sorted(position_weights.items(), key=lambda kv: kv[1], reverse=True)
                wanted_positions: list[str] = [pos for pos, w in preferred if w > 0.01]
                if not wanted_positions:
                    wanted_positions = ["C", "LW", "RW", "D", "G"]

                cap_limit_for_signing: float | None = None
                if cap_relief_score >= 0.45:
                    cap_limit_for_signing = max(0.75, 2.2 - (cap_relief_score - 0.45) * 2.0)

                offer_added = False
                for pos in wanted_positions:
                    pos_candidates = [
                        p for p in free_agents
                        if p.position == pos and p.player_id not in protected_free_agent_ids
                    ]
                    pos_candidates = sorted(
                        pos_candidates,
                        key=lambda p: (self._contract_player_value(p), -p.age, p.name),
                        reverse=True,
                    )[:20]
                    for candidate in pos_candidates:
                        years, cap_hit, contract_type, is_rfa = self._estimate_contract_offer(candidate)
                        if cap_limit_for_signing is not None and cap_hit > cap_limit_for_signing:
                            continue
                        if cap_hit > cap_space:
                            continue
                        fit_bonus = float(position_weights.get(candidate.position, 0.0))
                        contender_bonus = max(0.0, min(0.12, (self._team_point_pct(team) - 0.5) * 0.6))
                        offer_score = cap_hit * years + fit_bonus * 0.65 + contender_bonus + self._rng.random() * 0.05
                        offers.append(
                            {
                                "team": team,
                                "player": candidate,
                                "years": years,
                                "cap_hit": cap_hit,
                                "contract_type": contract_type,
                                "is_rfa": is_rfa,
                                "score": offer_score,
                            }
                        )
                        offer_added = True
                        break
                    if offer_added:
                        break

            if not offers:
                break

            offers_by_player: dict[str, list[dict[str, object]]] = {}
            for offer in offers:
                player_obj = offer["player"]
                if not isinstance(player_obj, Player):
                    continue
                offers_by_player.setdefault(player_obj.player_id, []).append(offer)

            signed_team_names: set[str] = set()
            signed_player_ids: set[str] = set()
            for player_id, player_offers in offers_by_player.items():
                best_offer = max(player_offers, key=lambda o: float(o.get("score", 0.0)))
                team_obj = best_offer["team"]
                player_obj = best_offer["player"]
                if not isinstance(team_obj, Team) or not isinstance(player_obj, Player):
                    continue
                if team_obj.name in signed_team_names or player_id in signed_player_ids:
                    continue
                if player_obj not in free_agents:
                    continue
                if len([p for p in team_obj.roster if not p.is_injured]) >= Team.MAX_ROSTER_SIZE:
                    continue
                cap_hit = float(best_offer.get("cap_hit", 0.0))
                if cap_hit > (self._team_cap_limit(team_obj) - self._team_cap_used(team_obj)):
                    continue

                self._assign_contract_terms(
                    player_obj,
                    years=int(best_offer.get("years", 1)),
                    cap_hit=cap_hit,
                    contract_type=str(best_offer.get("contract_type", "veteran")),
                    is_rfa=bool(best_offer.get("is_rfa", False)),
                )
                free_agents.remove(player_obj)
                player_obj.team_name = team_obj.name
                player_obj.free_agent_origin_team = ""
                team_obj.roster.append(player_obj)
                signings.append(
                    {
                        "team": team_obj.name,
                        "player": player_obj.name,
                        "years": int(player_obj.contract_years_left),
                        "cap_hit": float(player_obj.cap_hit),
                        "round": fa_round,
                    }
                )
                signed_team_names.add(team_obj.name)
                signed_player_ids.add(player_id)

        for team in self.teams:
            team.set_default_lineup()

        self.free_agents = list(free_agents)
        user_pending_re_signs = [
            {
                "name": p.name,
                "position": p.position,
                "age": p.age,
                "overall": round(self._contract_player_value(p), 2),
            }
            for p in free_agents
            if user_team_name and p.player_id in protected_free_agent_ids
        ]
        remaining_free_agents = [
            {
                "name": p.name,
                "position": p.position,
                "age": p.age,
                "overall": round(self._contract_player_value(p), 2),
            }
            for p in free_agents[:120]
        ]
        return {
            "re_signings": re_signings,
            "signings": signings,
            "user_pending_re_signs": user_pending_re_signs,
            "remaining_free_agents": remaining_free_agents,
        }

    def get_free_agents(self) -> list[Player]:
        return sorted(
            list(self.free_agents),
            key=lambda p: (self._contract_player_value(p), -p.age, p.name),
            reverse=True,
        )

    def sign_free_agent(
        self,
        team_name: str,
        player_name: str,
        years: int | None = None,
        cap_hit: float | None = None,
    ) -> dict[str, object]:
        team = self.get_team(team_name)
        if team is None:
            return {"ok": False, "reason": "team_not_found"}
        player = next((p for p in self.free_agents if p.name == player_name), None)
        if player is None:
            return {"ok": False, "reason": "player_not_found"}
        if len([p for p in team.roster if not p.is_injured]) >= Team.MAX_ROSTER_SIZE:
            return {"ok": False, "reason": "roster_full"}

        ask_years, ask_cap, ask_type, ask_rfa = self._estimate_contract_offer(player)
        offer_years = ask_years if years is None else max(1, min(8, int(years)))
        offer_cap = ask_cap if cap_hit is None else max(0.65, float(cap_hit))
        if offer_cap > (self._team_cap_limit(team) - self._team_cap_used(team)):
            return {"ok": False, "reason": "cap_space"}

        self._assign_contract_terms(
            player,
            years=offer_years,
            cap_hit=offer_cap,
            contract_type=ask_type,
            is_rfa=ask_rfa,
        )
        self.free_agents.remove(player)
        player.team_name = team.name
        player.free_agent_origin_team = ""
        team.roster.append(player)
        self._assign_team_player_numbers(team)
        team.set_default_lineup()
        self._ensure_team_leadership()
        self._save_state()
        return {
            "ok": True,
            "team": team.name,
            "player": player.name,
            "years": int(player.contract_years_left),
            "cap_hit": float(player.cap_hit),
        }

    def extend_player_contract(
        self,
        team_name: str,
        player_name: str,
        years: int | None = None,
        cap_hit: float | None = None,
    ) -> dict[str, object]:
        team = self.get_team(team_name)
        if team is None:
            return {"ok": False, "reason": "team_not_found"}
        player = next((p for p in [*team.roster, *team.minor_roster] if p.name == player_name), None)
        if player is None:
            return {"ok": False, "reason": "player_not_found"}
        if int(getattr(player, "contract_years_left", 0) or 0) <= 0:
            return {"ok": False, "reason": "contract_expired"}

        ask_years, ask_cap, ask_type, ask_rfa = self._estimate_contract_offer(player)
        offer_years = ask_years if years is None else max(1, min(8, int(years)))
        offer_cap = ask_cap if cap_hit is None else max(0.65, float(cap_hit))
        cap_space = self._team_cap_limit(team) - self._team_cap_used(team) + float(getattr(player, "cap_hit", 0.0))
        if offer_cap > cap_space:
            return {"ok": False, "reason": "cap_space"}

        self._assign_contract_terms(
            player,
            years=offer_years,
            cap_hit=offer_cap,
            contract_type=ask_type,
            is_rfa=ask_rfa,
        )
        self._save_state()
        return {
            "ok": True,
            "team": team.name,
            "player": player.name,
            "years": int(player.contract_years_left),
            "cap_hit": float(player.cap_hit),
        }

    def _series_home_team(self, game_number: int, higher_seed: Team, lower_seed: Team) -> Team:
        pattern = [higher_seed, higher_seed, lower_seed, lower_seed, higher_seed, lower_seed, higher_seed]
        return pattern[min(game_number - 1, len(pattern) - 1)]

    def _accumulate_playoff_game_stats(self, result: GameResult, tracker: dict[str, dict[str, object]]) -> None:
        def ensure_player(player: Player) -> dict[str, object]:
            row = tracker.get(player.player_id)
            if row is None:
                row = {
                    "player_id": player.player_id,
                    "name": player.name,
                    "team": player.team_name,
                    "position": player.position,
                    "gp": 0,
                    "g": 0,
                    "a": 0,
                    "p": 0,
                    "goalie_gp": 0,
                    "goalie_w": 0,
                    "goalie_losses": 0,
                    "goalie_shots": 0,
                    "goalie_saves": 0,
                    "goalie_ga": 0,
                }
                tracker[player.player_id] = row
            return row

        game_players: set[str] = set()
        for events in (result.home_goal_events, result.away_goal_events):
            for ev in events:
                scorer_row = ensure_player(ev.scorer)
                scorer_row["g"] = int(scorer_row["g"]) + 1
                scorer_row["p"] = int(scorer_row["p"]) + 1
                game_players.add(ev.scorer.player_id)
                for helper in ev.assists:
                    helper_row = ensure_player(helper)
                    helper_row["a"] = int(helper_row["a"]) + 1
                    helper_row["p"] = int(helper_row["p"]) + 1
                    game_players.add(helper.player_id)
        for pid in game_players:
            tracker[pid]["gp"] = int(tracker[pid]["gp"]) + 1

        home_win = result.home_goals > result.away_goals
        away_win = result.away_goals > result.home_goals
        if result.home_goalie is not None:
            row = ensure_player(result.home_goalie)
            row["goalie_gp"] = int(row["goalie_gp"]) + 1
            row["goalie_w"] = int(row["goalie_w"]) + (1 if home_win else 0)
            row["goalie_losses"] = int(row["goalie_losses"]) + (0 if home_win else 1)
            row["goalie_shots"] = int(row["goalie_shots"]) + int(result.home_goalie_shots)
            row["goalie_saves"] = int(row["goalie_saves"]) + int(result.home_goalie_saves)
            row["goalie_ga"] = int(row["goalie_ga"]) + int(result.away_goals)
        if result.away_goalie is not None:
            row = ensure_player(result.away_goalie)
            row["goalie_gp"] = int(row["goalie_gp"]) + 1
            row["goalie_w"] = int(row["goalie_w"]) + (1 if away_win else 0)
            row["goalie_losses"] = int(row["goalie_losses"]) + (0 if away_win else 1)
            row["goalie_shots"] = int(row["goalie_shots"]) + int(result.away_goalie_shots)
            row["goalie_saves"] = int(row["goalie_saves"]) + int(result.away_goalie_saves)
            row["goalie_ga"] = int(row["goalie_ga"]) + int(result.home_goals)

    def _select_playoff_mvp(self, champion: str, tracker: dict[str, dict[str, object]]) -> dict[str, object]:
        champion_rows = [r for r in tracker.values() if str(r.get("team", "")) == champion]
        if not champion_rows:
            return {"name": "", "team": champion, "position": "", "summary": ""}

        def score(row: dict[str, object]) -> float:
            position = str(row.get("position", ""))
            points = int(row.get("p", 0))
            goals = int(row.get("g", 0))
            gp = max(1, int(row.get("gp", 0)))
            base = points * 6.0 + goals * 2.2 + (points / gp) * 2.0
            if position in GOALIE_POSITIONS:
                ggp = max(1, int(row.get("goalie_gp", 0)))
                wins = int(row.get("goalie_w", 0))
                shots = max(1, int(row.get("goalie_shots", 0)))
                saves = int(row.get("goalie_saves", 0))
                ga = int(row.get("goalie_ga", 0))
                sv = saves / shots
                gaa = ga / ggp
                base = wins * 7.5 + sv * 75.0 - gaa * 1.8 + ggp * 0.8
            return base

        best = max(champion_rows, key=lambda r: (score(r), int(r.get("p", 0)), int(r.get("goalie_w", 0))))
        pos = str(best.get("position", ""))
        if pos in GOALIE_POSITIONS:
            shots = max(1, int(best.get("goalie_shots", 0)))
            saves = int(best.get("goalie_saves", 0))
            sv = saves / shots
            summary = f"{int(best.get('goalie_w', 0))}W, {sv:.3f} SV%, {int(best.get('goalie_gp', 0))} GP"
        else:
            summary = f"{int(best.get('p', 0))} pts ({int(best.get('g', 0))}G-{int(best.get('a', 0))}A) in {int(best.get('gp', 0))} GP"
        return {
            "name": str(best.get("name", "")),
            "team": champion,
            "position": pos,
            "summary": summary,
        }

    def _playoff_mvp_race(self, tracker: dict[str, dict[str, object]], limit: int = 10) -> list[dict[str, object]]:
        if not tracker:
            return []

        def score(row: dict[str, object]) -> float:
            position = str(row.get("position", ""))
            points = int(row.get("p", 0))
            goals = int(row.get("g", 0))
            gp = max(1, int(row.get("gp", 0)))
            base = points * 6.0 + goals * 2.2 + (points / gp) * 2.0
            if position in GOALIE_POSITIONS:
                ggp = max(1, int(row.get("goalie_gp", 0)))
                wins = int(row.get("goalie_w", 0))
                shots = max(1, int(row.get("goalie_shots", 0)))
                saves = int(row.get("goalie_saves", 0))
                ga = int(row.get("goalie_ga", 0))
                sv = saves / shots
                gaa = ga / ggp
                base = wins * 7.5 + sv * 75.0 - gaa * 1.8 + ggp * 0.8
            return base

        ranked = sorted(
            tracker.values(),
            key=lambda r: (score(r), int(r.get("p", 0)), int(r.get("goalie_w", 0))),
            reverse=True,
        )
        out: list[dict[str, object]] = []
        for row in ranked[: max(1, limit)]:
            pos = str(row.get("position", ""))
            if pos in GOALIE_POSITIONS:
                shots = max(1, int(row.get("goalie_shots", 0)))
                saves = int(row.get("goalie_saves", 0))
                sv = saves / shots
                summary = f"{int(row.get('goalie_w', 0))}W, {sv:.3f} SV%, {int(row.get('goalie_gp', 0))} GP"
            else:
                summary = f"{int(row.get('p', 0))} pts ({int(row.get('g', 0))}G-{int(row.get('a', 0))}A) in {int(row.get('gp', 0))} GP"
            out.append(
                {
                    "name": str(row.get("name", "")),
                    "team": str(row.get("team", "")),
                    "position": pos,
                    "summary": summary,
                    "score": round(score(row), 2),
                }
            )
        return out

    def _simulate_playoff_series(
        self,
        round_name: str,
        higher_seed: Team,
        lower_seed: Team,
        best_of: int = 7,
        playoff_tracker: dict[str, dict[str, object]] | None = None,
    ) -> dict[str, object]:
        wins_needed = best_of // 2 + 1
        high_wins = 0
        low_wins = 0
        games: list[dict[str, object]] = []
        game_number = 1

        while high_wins < wins_needed and low_wins < wins_needed:
            self._advance_recovery_day()
            home = self._series_home_team(game_number, higher_seed, lower_seed)
            away = lower_seed if home.name == higher_seed.name else higher_seed
            elimination_game = (
                high_wins == wins_needed - 1
                or low_wins == wins_needed - 1
            )
            self._coach_set_dtd_decisions(home, away, playoff_mode=True, elimination_game=elimination_game)
            self._coach_set_dtd_decisions(away, home, playoff_mode=True, elimination_game=elimination_game)
            self._ensure_team_depth(home)
            self._ensure_team_depth(away)
            home.set_default_lineup()
            away.set_default_lineup()
            home_goalie = self._coach_choose_playoff_goalie(
                home,
                series_games=games,
                elimination_game=elimination_game,
            )
            away_goalie = self._coach_choose_playoff_goalie(
                away,
                series_games=games,
                elimination_game=elimination_game,
            )
            home.set_starting_goalie(home_goalie.name if home_goalie is not None else None)
            away.set_starting_goalie(away_goalie.name if away_goalie is not None else None)
            home_strategy = home.coach_style if home.coach_style in STRATEGY_EFFECTS else "balanced"
            away_strategy = away.coach_style if away.coach_style in STRATEGY_EFFECTS else "balanced"
            home_off_bonus, home_def_bonus, home_injury_mult = self._coach_modifiers(home, home_strategy, away)
            away_off_bonus, away_def_bonus, away_injury_mult = self._coach_modifiers(away, away_strategy, home)

            # Playoff officiating tends to slightly favor home side on marginal calls.
            home_context_bonus = 0.024
            away_context_bonus = -0.012
            randomness_scale = 1.0
            if elimination_game:
                randomness_scale = 1.32
                if home.name == higher_seed.name:
                    home_context_bonus += 0.010
                else:
                    away_context_bonus += 0.010
            if game_number == 7:
                randomness_scale = max(randomness_scale, 1.40)

            result = simulate_game(
                home=home,
                away=away,
                home_strategy=home_strategy,
                away_strategy=away_strategy,
                home_coach_offense_bonus=home_off_bonus,
                away_coach_offense_bonus=away_off_bonus,
                home_coach_defense_bonus=home_def_bonus,
                away_coach_defense_bonus=away_def_bonus,
                home_context_bonus=home_context_bonus,
                away_context_bonus=away_context_bonus,
                randomness_scale=randomness_scale,
                home_injury_mult=home_injury_mult,
                away_injury_mult=away_injury_mult,
                rng=self._rng,
                record_player_stats=False,
                apply_injuries=True,
                record_goalie_stats=False,
            )
            if playoff_tracker is not None:
                self._accumulate_playoff_game_stats(result, playoff_tracker)
            higher_goals = result.home_goals if home.name == higher_seed.name else result.away_goals
            lower_goals = result.home_goals if home.name == lower_seed.name else result.away_goals
            higher_won = higher_goals > lower_goals
            if higher_won:
                high_wins += 1
            else:
                low_wins += 1
            home_rec = self._records.get(home.name)
            away_rec = self._records.get(away.name)
            home_pct = home_rec.point_pct if home_rec is not None else 0.5
            away_pct = away_rec.point_pct if away_rec is not None else 0.5
            arena_capacity = max(9500, int(getattr(home, "arena_capacity", 16000)))
            base_attendance = int(arena_capacity * 0.90)
            quality_bump = int((home_pct - 0.5) * 5400 + (away_pct - 0.5) * 2600)
            rivalry_bump = 950 if home.division == away.division else (450 if home.conference == away.conference else 200)
            elimination_bump = 650 if elimination_game else 0
            attendance_noise = self._rng.randint(-420, 620)
            attendance = max(8600, min(arena_capacity, base_attendance + quality_bump + rivalry_bump + elimination_bump + attendance_noise))
            stars = self._playoff_three_stars(result)
            games.append(
                {
                    "game": game_number,
                    "home": home.name,
                    "away": away.name,
                    "home_goals": result.home_goals,
                    "away_goals": result.away_goals,
                    "overtime": result.overtime,
                    "home_goalie": result.home_goalie.name if result.home_goalie is not None else "",
                    "away_goalie": result.away_goalie.name if result.away_goalie is not None else "",
                    "home_goalie_shots": int(result.home_goalie_shots),
                    "home_goalie_saves": int(result.home_goalie_saves),
                    "away_goalie_shots": int(result.away_goalie_shots),
                    "away_goalie_saves": int(result.away_goalie_saves),
                    "attendance": attendance,
                    "arena_capacity": arena_capacity,
                    "winner": higher_seed.name if higher_won else lower_seed.name,
                    "three_stars": stars,
                }
            )
            self._consume_coach_game_effect(higher_seed)
            self._consume_coach_game_effect(lower_seed)
            game_number += 1

        winner = higher_seed if high_wins > low_wins else lower_seed
        loser = lower_seed if winner.name == higher_seed.name else higher_seed
        return {
            "round": round_name,
            "higher_seed": higher_seed.name,
            "lower_seed": lower_seed.name,
            "winner": winner.name,
            "loser": loser.name,
            "winner_wins": max(high_wins, low_wins),
            "loser_wins": min(high_wins, low_wins),
            "games": games,
        }

    def _run_playoffs(self) -> dict[str, object]:
        standings = {rec.team.name: rec for rec in self.get_standings()}
        rounds: list[dict[str, object]] = []
        playoff_seeds: list[dict[str, object]] = []
        playoff_tracker: dict[str, dict[str, object]] = {}

        def _team_seed_key(team: Team) -> tuple[int, int, int]:
            rec = standings.get(team.name)
            if rec is None:
                return (0, 0, 0)
            return (rec.points, rec.goal_diff, rec.goals_for)

        conference_finalists: dict[str, Team] = {}
        for conference in self.get_conferences():
            conf_records = self.get_conference_standings(conference)
            if len(conf_records) < 2:
                continue
            divisions = sorted({rec.team.division for rec in conf_records})

            # NHL-style branch: exactly 2 divisions per conference.
            if len(divisions) == 2:
                division_top_three: dict[str, list[TeamRecord]] = {}
                for division in divisions:
                    division_rows = [rec for rec in conf_records if rec.team.division == division]
                    division_top_three[division] = division_rows[:3]
                qualified_names = {
                    rec.team.name
                    for division in divisions
                    for rec in division_top_three.get(division, [])
                }
                wildcard_candidates = [rec for rec in conf_records if rec.team.name not in qualified_names]
                wildcards = wildcard_candidates[:2]

                for division in divisions:
                    for idx, rec in enumerate(division_top_three.get(division, []), start=1):
                        playoff_seeds.append(
                            {
                                "conference": conference,
                                "division": division,
                                "seed": f"D{idx}",
                                "team": rec.team.name,
                                "points": rec.points,
                            }
                        )
                for idx, rec in enumerate(wildcards, start=1):
                    playoff_seeds.append(
                        {
                            "conference": conference,
                            "division": "Wildcard",
                            "seed": f"WC{idx}",
                            "team": rec.team.name,
                            "points": rec.points,
                        }
                    )

                div_a, div_b = divisions[0], divisions[1]
                a_top = division_top_three.get(div_a, [])
                b_top = division_top_three.get(div_b, [])
                a_wc: Team | None = None
                b_wc: Team | None = None
                if len(wildcards) == 2 and a_top and b_top:
                    higher_a = _team_seed_key(a_top[0].team)
                    higher_b = _team_seed_key(b_top[0].team)
                    if higher_a >= higher_b:
                        a_wc = wildcards[1].team
                        b_wc = wildcards[0].team
                    else:
                        a_wc = wildcards[0].team
                        b_wc = wildcards[1].team
                elif len(wildcards) == 1:
                    if a_top and b_top:
                        if _team_seed_key(a_top[0].team) >= _team_seed_key(b_top[0].team):
                            b_wc = wildcards[0].team
                        else:
                            a_wc = wildcards[0].team
                    elif a_top:
                        a_wc = wildcards[0].team
                    elif b_top:
                        b_wc = wildcards[0].team

                first_round_series: list[dict[str, object]] = []
                division_advancers: dict[str, list[Team]] = {div_a: [], div_b: []}

                if a_top and a_wc is not None:
                    series = self._simulate_playoff_series(f"{div_a} Division First Round", a_top[0].team, a_wc, best_of=7, playoff_tracker=playoff_tracker)
                    first_round_series.append(series)
                    winner_team = self.get_team(str(series["winner"]))
                    if winner_team is not None:
                        division_advancers[div_a].append(winner_team)
                elif a_top:
                    division_advancers[div_a].append(a_top[0].team)
                if len(a_top) >= 3:
                    series = self._simulate_playoff_series(f"{div_a} Division First Round", a_top[1].team, a_top[2].team, best_of=7, playoff_tracker=playoff_tracker)
                    first_round_series.append(series)
                    winner_team = self.get_team(str(series["winner"]))
                    if winner_team is not None:
                        division_advancers[div_a].append(winner_team)

                if b_top and b_wc is not None:
                    series = self._simulate_playoff_series(f"{div_b} Division First Round", b_top[0].team, b_wc, best_of=7, playoff_tracker=playoff_tracker)
                    first_round_series.append(series)
                    winner_team = self.get_team(str(series["winner"]))
                    if winner_team is not None:
                        division_advancers[div_b].append(winner_team)
                elif b_top:
                    division_advancers[div_b].append(b_top[0].team)
                if len(b_top) >= 3:
                    series = self._simulate_playoff_series(f"{div_b} Division First Round", b_top[1].team, b_top[2].team, best_of=7, playoff_tracker=playoff_tracker)
                    first_round_series.append(series)
                    winner_team = self.get_team(str(series["winner"]))
                    if winner_team is not None:
                        division_advancers[div_b].append(winner_team)

                if first_round_series:
                    rounds.append({"name": f"{conference} First Round", "series": first_round_series})

                division_final_series: list[dict[str, object]] = []
                division_champions: list[Team] = []
                for division in (div_a, div_b):
                    advancers = division_advancers.get(division, [])
                    if len(advancers) >= 2:
                        advancers = sorted(advancers, key=_team_seed_key, reverse=True)
                        series = self._simulate_playoff_series(f"{division} Division Final", advancers[0], advancers[1], best_of=7, playoff_tracker=playoff_tracker)
                        division_final_series.append(series)
                        winner_team = self.get_team(str(series["winner"]))
                        if winner_team is not None:
                            division_champions.append(winner_team)
                    elif len(advancers) == 1:
                        division_champions.append(advancers[0])

                if division_final_series:
                    rounds.append({"name": f"{conference} Division Finals", "series": division_final_series})

                if len(division_champions) >= 2:
                    division_champions = sorted(division_champions, key=_team_seed_key, reverse=True)
                    conference_final = self._simulate_playoff_series(
                        f"{conference} Conference Final",
                        division_champions[0],
                        division_champions[1],
                        best_of=7,
                        playoff_tracker=playoff_tracker,
                    )
                    rounds.append({"name": f"{conference} Conference Final", "series": [conference_final]})
                    conf_winner = self.get_team(str(conference_final["winner"]))
                    if conf_winner is not None:
                        conference_finalists[conference] = conf_winner
                elif len(division_champions) == 1:
                    conference_finalists[conference] = division_champions[0]
                continue

            # Fallback bracket for non-NHL conference formats.
            conference_qualifiers = conf_records[:8]
            for idx, rec in enumerate(conference_qualifiers, start=1):
                playoff_seeds.append(
                    {
                        "conference": conference,
                        "division": rec.team.division,
                        "seed": idx,
                        "team": rec.team.name,
                        "points": rec.points,
                    }
                )
            if len(conference_qualifiers) < 2:
                continue

            first_round_pairs = [(0, 7), (1, 6), (2, 5), (3, 4)]
            first_round_series: list[dict[str, object]] = []
            semifinal_teams: list[Team] = []
            for high_idx, low_idx in first_round_pairs:
                if high_idx >= len(conference_qualifiers) or low_idx >= len(conference_qualifiers):
                    continue
                high_team = conference_qualifiers[high_idx].team
                low_team = conference_qualifiers[low_idx].team
                series = self._simulate_playoff_series(f"{conference} Conference Quarterfinal", high_team, low_team, best_of=7, playoff_tracker=playoff_tracker)
                first_round_series.append(series)
                winner_team = self.get_team(str(series["winner"]))
                if winner_team is not None:
                    semifinal_teams.append(winner_team)
            if first_round_series:
                rounds.append({"name": f"{conference} Conference Quarterfinal", "series": first_round_series})

            semifinal_teams = sorted(semifinal_teams, key=_team_seed_key, reverse=True)
            semifinal_series: list[dict[str, object]] = []
            finalists: list[Team] = []
            if len(semifinal_teams) >= 2:
                while len(semifinal_teams) >= 2:
                    high = semifinal_teams.pop(0)
                    low = semifinal_teams.pop(-1)
                    series = self._simulate_playoff_series(f"{conference} Conference Semifinal", high, low, best_of=7, playoff_tracker=playoff_tracker)
                    semifinal_series.append(series)
                    winner_team = self.get_team(str(series["winner"]))
                    if winner_team is not None:
                        finalists.append(winner_team)
            if semifinal_series:
                rounds.append({"name": f"{conference} Conference Semifinal", "series": semifinal_series})

            finalists = sorted(finalists, key=_team_seed_key, reverse=True)
            if len(finalists) >= 2:
                conference_final = self._simulate_playoff_series(
                    f"{conference} Conference Final",
                    finalists[0],
                    finalists[1],
                    best_of=7,
                    playoff_tracker=playoff_tracker,
                )
                rounds.append({"name": f"{conference} Conference Final", "series": [conference_final]})
                conf_winner = self.get_team(str(conference_final["winner"]))
                if conf_winner is not None:
                    conference_finalists[conference] = conf_winner
            elif len(finalists) == 1:
                conference_finalists[conference] = finalists[0]

        finalists = list(conference_finalists.values())
        finalists = sorted(
            finalists,
            key=lambda t: (
                standings[t.name].points if t.name in standings else 0,
                standings[t.name].goal_diff if t.name in standings else 0,
                standings[t.name].goals_for if t.name in standings else 0,
            ),
            reverse=True,
        )
        if len(finalists) >= 2:
            cup_final = self._simulate_playoff_series("Cup Final", finalists[0], finalists[1], best_of=7, playoff_tracker=playoff_tracker)
            rounds.append({"name": "Cup Final", "series": [cup_final]})
            cup_champion = str(cup_final.get("winner", ""))
        elif finalists:
            cup_champion = finalists[0].name
        else:
            cup_champion = self.get_standings()[0].team.name if self.teams else ""

        return {
            "cup_name": "Founders Cup",
            "champion": cup_champion,
            "cup_champion": cup_champion,
            "mvp": self._select_playoff_mvp(cup_champion, playoff_tracker),
            "mvp_race": self._playoff_mvp_race(playoff_tracker, limit=12),
            "seeds": playoff_seeds,
            "rounds": rounds,
        }

    def _playoff_three_stars(self, result: GameResult) -> list[dict[str, str]]:
        skater_lines: dict[str, dict[str, object]] = {}

        def add_goal_events(events: list[Any], team_name: str) -> None:
            for ev in events:
                scorer = ev.scorer
                sid = scorer.player_id
                if sid not in skater_lines:
                    skater_lines[sid] = {"player": scorer, "team": team_name, "g": 0, "a": 0}
                skater_lines[sid]["g"] = int(skater_lines[sid]["g"]) + 1
                for helper in ev.assists:
                    aid = helper.player_id
                    if aid not in skater_lines:
                        skater_lines[aid] = {"player": helper, "team": team_name, "g": 0, "a": 0}
                    skater_lines[aid]["a"] = int(skater_lines[aid]["a"]) + 1

        add_goal_events(result.home_goal_events, result.home.name)
        add_goal_events(result.away_goal_events, result.away.name)

        candidates: list[tuple[float, str]] = []
        for line in skater_lines.values():
            player = line["player"]
            goals = int(line["g"])
            assists = int(line["a"])
            points = goals + assists
            score = points * 52.0 + goals * 18.0 + assists * 8.0
            if points >= 3:
                score += 18.0
            if goals >= 2:
                score += 12.0
            summary = f"{player.name} ({line['team']}) {goals}G {assists}A"
            candidates.append((score, summary))

        def goalie_score(saves: int, shots: int, goals_against: int, won: bool) -> float:
            if shots <= 0:
                return 0.0
            sv = saves / shots
            score = saves * 2.0
            if sv >= 0.960:
                score += 95.0
            elif sv >= 0.950:
                score += 78.0
            elif sv >= 0.940:
                score += 62.0
            elif sv >= 0.930:
                score += 46.0
            elif sv >= 0.920:
                score += 28.0
            elif sv >= 0.910:
                score += 12.0
            if shots >= 40:
                score += 36.0
            elif shots >= 35:
                score += 24.0
            elif shots >= 30:
                score += 14.0
            if won:
                score += 34.0
            if goals_against == 0:
                score += 135.0
            return max(0.0, score)

        if result.home_goalie is not None and result.home_goalie_shots > 0:
            candidates.append(
                (
                    goalie_score(
                        saves=result.home_goalie_saves,
                        shots=result.home_goalie_shots,
                        goals_against=result.away_goals,
                        won=result.home_goals > result.away_goals,
                    ),
                    f"{result.home_goalie.name} ({result.home.name}) {result.home_goalie_saves}/{result.home_goalie_shots} SV",
                )
            )
        if result.away_goalie is not None and result.away_goalie_shots > 0:
            candidates.append(
                (
                    goalie_score(
                        saves=result.away_goalie_saves,
                        shots=result.away_goalie_shots,
                        goals_against=result.home_goals,
                        won=result.away_goals > result.home_goals,
                    ),
                    f"{result.away_goalie.name} ({result.away.name}) {result.away_goalie_saves}/{result.away_goalie_shots} SV",
                )
            )

        candidates.sort(key=lambda row: row[0], reverse=True)
        labels = ["1st Star", "2nd Star", "3rd Star"]
        return [{"label": labels[idx], "summary": summary} for idx, (_, summary) in enumerate(candidates[:3])]

    def _start_new_season(self) -> None:
        self._records = {team.name: TeamRecord(team=team) for team in self.teams}
        self._season_days = build_round_robin_days(self.teams, self.games_per_matchup)
        self._day_index = 0

    def _complete_offseason_with_playoffs(
        self,
        playoffs: dict[str, object],
        user_team_name: str | None = None,
    ) -> dict[str, object]:
        champion = str(playoffs.get("champion", "")) if playoffs else (self.get_standings()[0].team.name if self.teams else "")
        coach_rows: list[dict[str, object]] = []
        leadership_rows: list[dict[str, object]] = []
        standings = self.get_standings()
        for rec in standings:
            coach_rows.append(
                {
                    "team": rec.team.name,
                    "coach": rec.team.coach_name,
                    "coach_age": int(rec.team.coach_age),
                    "coach_rating": round(rec.team.coach_rating, 2),
                    "coach_style": rec.team.coach_style,
                    "wins": rec.wins,
                    "losses": rec.losses,
                    "ot_losses": rec.ot_losses,
                    "points": rec.points,
                    "point_pct": round(rec.point_pct, 3),
                    "champion": rec.team.name == champion,
                }
            )
            leadership_rows.append(
                {
                    "team": rec.team.name,
                    "captain": rec.team.captain_name,
                    "assistants": list(rec.team.assistant_names),
                }
            )
        summary = {
            "season": self.season_number,
            "champion": champion,
            "standings": self._serialize_standings(),
            "coaches": coach_rows,
            "leadership": leadership_rows,
            "top_scorers": self._serialize_top_scorers(),
            "top_goalies": self._serialize_top_goalies(),
            "playoffs": playoffs,
        }

        self._record_career_season_stats(self.season_number)
        retired, retired_numbers = self._age_and_retire_players()
        drafted, drafted_details = self._run_draft()
        free_agency = self._run_contract_and_free_agency(user_team_name=user_team_name)
        self._clear_season_player_stats()
        self.last_offseason_retired = list(retired)
        self.last_offseason_retired_numbers = list(retired_numbers)
        self.last_offseason_drafted = {k: list(v) for k, v in drafted.items()}
        self.last_offseason_drafted_details = {k: list(v) for k, v in drafted_details.items()}
        retired_coaches: list[dict[str, object]] = []
        for team in self.teams:
            replaced = False
            team.coach_age += 1
            if self._rng.random() < self._coach_retirement_probability(team):
                retired_coaches.append(self._replace_retired_coach(team))
                replaced = True
            if not replaced:
                team.coach_tenure_seasons += 1
            team.coach_changes_recent = max(0.0, team.coach_changes_recent * 0.72)
            team.coach_honeymoon_games_remaining = 0
        self._ensure_team_leadership()

        summary["retired"] = retired
        summary["retired_numbers"] = retired_numbers
        summary["draft"] = drafted
        summary["draft_details"] = drafted_details
        summary["free_agency"] = free_agency
        summary["retired_coaches"] = retired_coaches
        self.season_history.append(summary)
        self._save_history()
        self._save_career_history()
        self._save_hall_of_fame()

        self.season_number += 1
        self._start_new_season()
        self.pending_playoffs = None
        self.pending_playoff_days = []
        self.pending_playoff_day_index = 0
        self._save_state()
        return {
            "advanced": True,
            "retired": retired,
            "retired_numbers": retired_numbers,
            "drafted": drafted,
            "drafted_details": drafted_details,
            "free_agency": free_agency,
            "retired_coaches": retired_coaches,
            "champion": champion,
            "playoffs": playoffs,
            "completed_season": summary["season"],
            "next_season": self.season_number,
        }

    def finalize_offseason_after_playoffs(self, user_team_name: str | None = None) -> dict[str, object]:
        if not self.is_complete():
            return {"advanced": False, "reason": "season_not_complete"}
        if self.pending_playoffs is None:
            return {"advanced": False, "reason": "playoffs_not_started"}
        if self.pending_playoff_day_index < len(self.pending_playoff_days):
            return {"advanced": False, "reason": "playoffs_not_complete"}
        return self._complete_offseason_with_playoffs(self.pending_playoffs, user_team_name=user_team_name)

    def advance_to_next_season(self, user_team_name: str | None = None) -> dict[str, object]:
        if not self.is_complete():
            return {"advanced": False, "reason": "season_not_complete"}
        if self.pending_playoffs is None:
            self.start_playoffs()
        self.pending_playoff_day_index = len(self.pending_playoff_days)
        self._save_state()
        return self.finalize_offseason_after_playoffs(user_team_name=user_team_name)

    def reset_persistent_history(self) -> None:
        self.season_history = []
        self.career_history = {}
        self.hall_of_fame = []
        self.last_offseason_retired = []
        self.last_offseason_retired_numbers = []
        self.last_offseason_drafted = {}
        self.last_offseason_drafted_details = {}
        self.free_agents = []
        self.draft_focus_by_team = {}
        self.pending_playoffs = None
        self.pending_playoff_days = []
        self.pending_playoff_day_index = 0
        self.season_number = 1
        for team in self.teams:
            for player in [*team.roster, *team.minor_roster]:
                player.career_seasons = []
        try:
            if self.history_path.exists():
                self.history_path.unlink()
        except OSError:
            pass
        try:
            if self.career_history_path.exists():
                self.career_history_path.unlink()
        except OSError:
            pass
        try:
            if self.state_path.exists():
                self.state_path.unlink()
        except OSError:
            pass
        try:
            if self.hall_of_fame_path.exists():
                self.hall_of_fame_path.unlink()
        except OSError:
            pass

    def run_season(self) -> LeagueResult:
        while not self.is_complete():
            self.simulate_next_day()
        return LeagueResult(standings=self.get_standings())

