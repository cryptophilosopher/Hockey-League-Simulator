from __future__ import annotations

import json
import random
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .app import build_default_teams
from .engine import GameResult
from .league import LeagueSimulator
from .models import (
    ALL_LINE_SLOTS,
    GOALIE_POSITIONS,
    Player,
    TeamRecord,
)


class TeamSelection(BaseModel):
    team_name: str


class StrategySelection(BaseModel):
    strategy: str = "balanced"
    override_coach_for_strategy: bool | None = None


class ControlOverrideSelection(BaseModel):
    override_coach_for_lines: bool
    override_coach_for_strategy: bool


class GameModeSelection(BaseModel):
    mode: str = "both"


class LinesSelection(BaseModel):
    team_name: str | None = None
    assignments: dict[str, str] = {}


class DraftNeedSelection(BaseModel):
    focus: str = "auto"
    team_name: str | None = None


class SimService:
    def __init__(self) -> None:
        self._init_fresh_state()
        self._load_runtime_state()
        self._lock = Lock()

    def _init_fresh_state(self) -> None:
        teams = build_default_teams()
        self.simulator = LeagueSimulator(teams=teams, games_per_matchup=2)
        self.runtime_state_path = Path("api_runtime_state.json")
        self.user_team_name = teams[0].name if teams else ""
        self.user_strategy = "balanced"
        self.override_coach_for_lines = False
        self.override_coach_for_strategy = False
        self.game_mode = "gm"
        self.daily_results: list[dict[str, Any]] = []
        self.news_feed: list[dict[str, Any]] = []
        self.coach_pool: list[dict[str, Any]] = self._build_initial_coach_pool()

    def _load_runtime_state(self) -> None:
        if not self.runtime_state_path.exists():
            return
        try:
            raw = json.loads(self.runtime_state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(raw, dict):
            return

        daily = raw.get("daily_results", [])
        news = raw.get("news_feed", [])
        if isinstance(daily, list):
            self.daily_results = [row for row in daily if isinstance(row, dict)]
        if isinstance(news, list):
            self.news_feed = [row for row in news if isinstance(row, dict)]

        team_name = raw.get("user_team_name")
        if isinstance(team_name, str) and team_name:
            self.user_team_name = team_name
        strategy = raw.get("user_strategy")
        if isinstance(strategy, str) and strategy:
            self.user_strategy = strategy.lower()
        mode = raw.get("game_mode")
        if isinstance(mode, str) and mode in {"gm", "coach", "both"}:
            self.game_mode = mode
        self.override_coach_for_lines = bool(raw.get("override_coach_for_lines", self.override_coach_for_lines))
        self.override_coach_for_strategy = bool(raw.get("override_coach_for_strategy", self.override_coach_for_strategy))

    def _save_runtime_state(self) -> None:
        payload = {
            "user_team_name": self.user_team_name,
            "user_strategy": self.user_strategy,
            "override_coach_for_lines": self.override_coach_for_lines,
            "override_coach_for_strategy": self.override_coach_for_strategy,
            "game_mode": self.game_mode,
            "daily_results": self.daily_results[-600:],
            "news_feed": self.news_feed[:250],
        }
        try:
            self.runtime_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _add_news(
        self,
        kind: str,
        headline: str,
        details: str = "",
        team: str | None = None,
        season: int | None = None,
        day: int | None = None,
    ) -> None:
        row = {
            "kind": kind,
            "headline": headline,
            "details": details,
            "team": team or "",
            "season": int(self.simulator.season_number if season is None else season),
            "day": int(day or 0),
        }
        self.news_feed.insert(0, row)
        self.news_feed = self.news_feed[:250]
        self._save_runtime_state()

    def _injury_news_from_results(self, day_num: int, results: list[GameResult]) -> None:
        for result in results:
            for inj in result.home_injuries:
                self._add_news(
                    kind="injury",
                    headline=f"Injury: {inj.player.name} ({result.home.name})",
                    details=f"Expected out {inj.games_out} games after vs {result.away.name}.",
                    team=result.home.name,
                    day=day_num,
                )
            for inj in result.away_injuries:
                self._add_news(
                    kind="injury",
                    headline=f"Injury: {inj.player.name} ({result.away.name})",
                    details=f"Expected out {inj.games_out} games after at {result.home.name}.",
                    team=result.away.name,
                    day=day_num,
                )

    def _draft_news_from_offseason(
        self,
        completed_season: int,
        drafted_details: dict[str, list[dict[str, object]]],
    ) -> None:
        display_season = completed_season + 1
        picks: list[tuple[int, str, str, int]] = []
        for team_name, rows in drafted_details.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                overall = int(row.get("overall") or 0)
                round_no = int(row.get("round") or 0)
                name = str(row.get("name", "")).strip()
                if overall <= 0 or round_no <= 0 or not name:
                    continue
                picks.append((overall, team_name, name, round_no))
        picks.sort(key=lambda x: x[0])
        for overall, team_name, name, round_no in picks[:24]:
            self._add_news(
                kind="draft",
                headline=f"Draft: Pick #{overall} {name} to {team_name}",
                details=f"Season {completed_season} Entry Draft Round {round_no}.",
                team=team_name,
                season=display_season,
                day=0,
            )

        user_team = str(self.user_team_name).strip()
        if user_team and isinstance(drafted_details.get(user_team), list):
            user_rows = [r for r in drafted_details.get(user_team, []) if isinstance(r, dict)]
            if user_rows:
                user_rows = sorted(user_rows, key=lambda r: int(r.get("overall") or 0))
                summary_parts: list[str] = []
                for row in user_rows[:6]:
                    name = str(row.get("name", "")).strip()
                    pos = str(row.get("position", "")).strip()
                    overall = int(row.get("overall") or 0)
                    if not name or overall <= 0:
                        continue
                    summary_parts.append(f"#{overall} {name} ({pos})")
                if summary_parts:
                    self._add_news(
                        kind="draft",
                        headline=f"{user_team} Draft Class",
                        details=", ".join(summary_parts),
                        team=user_team,
                        season=display_season,
                        day=0,
                    )

    def news(self, limit: int = 80) -> list[dict[str, Any]]:
        return [dict(row) for row in self.news_feed[: max(1, min(limit, 250))]]

    def _coach_history_totals(self) -> dict[str, dict[str, int]]:
        totals: dict[str, dict[str, int]] = {}
        for season in self.simulator.season_history:
            coaches = season.get("coaches", [])
            if not isinstance(coaches, list):
                continue
            for row in coaches:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("coach", "")).strip()
                if not name:
                    continue
                item = totals.setdefault(name, {"w": 0, "l": 0, "otl": 0, "cups": 0})
                item["w"] += int(row.get("wins", 0))
                item["l"] += int(row.get("losses", 0))
                item["otl"] += int(row.get("ot_losses", 0))
                if bool(row.get("champion", False)):
                    item["cups"] += 1
        return totals

    def _build_initial_coach_pool(self) -> list[dict[str, Any]]:
        totals = self._coach_history_totals()
        active_names = {t.coach_name for t in self.simulator.teams}
        pool: list[dict[str, Any]] = []
        for name, hist in totals.items():
            if name in active_names:
                continue
            rating = round(2.4 + min(2.1, hist["w"] / 220.0 + hist["cups"] * 0.35), 2)
            style = self.simulator._rating_to_style(rating)
            pool.append(
                {
                    "name": name,
                    "rating": rating,
                    "style": style,
                    "offense": rating,
                    "defense": rating,
                    "goalie_dev": rating,
                    "w": hist["w"],
                    "l": hist["l"],
                    "otl": hist["otl"],
                    "cups": hist["cups"],
                    "source": "former",
                }
            )
        while len(pool) < 14:
            rating = self.simulator._generate_coach_rating(lower=2.2, upper=4.8)
            pool.append(
                {
                    "name": self.simulator._generate_coach_name(),
                    "rating": rating,
                    "style": self.simulator._rating_to_style(rating),
                    "offense": self.simulator._generate_coach_rating(lower=2.0, upper=4.9),
                    "defense": self.simulator._generate_coach_rating(lower=2.0, upper=4.9),
                    "goalie_dev": self.simulator._generate_coach_rating(lower=2.0, upper=4.9),
                    "w": 0,
                    "l": 0,
                    "otl": 0,
                    "cups": 0,
                    "source": "new",
                }
            )
        pool.sort(key=lambda c: (int(c.get("cups", 0)), float(c.get("rating", 0.0))), reverse=True)
        return pool

    def _active_coach_names(self) -> set[str]:
        return {str(t.coach_name) for t in self.simulator.teams}

    def _coach_cup_count(self, coach_name: str) -> int:
        return int(
            sum(
                1
                for season in self.simulator.season_history
                for row in season.get("coaches", [])
                if isinstance(row, dict)
                and str(row.get("coach", "")) == coach_name
                and bool(row.get("champion", False))
            )
        )

    def _ensure_coach_pool_depth(self, min_size: int = 14) -> None:
        active = self._active_coach_names()
        seen: set[str] = set()
        clean_pool: list[dict[str, Any]] = []
        for row in self.coach_pool:
            name = str(row.get("name", "")).strip()
            if not name or name in active or name in seen:
                continue
            seen.add(name)
            clean_pool.append(row)
        self.coach_pool = clean_pool

        while len(self.coach_pool) < min_size:
            rating = self.simulator._generate_coach_rating(lower=2.2, upper=4.8)
            name = self.simulator._generate_coach_name()
            if name in active or any(str(c.get("name", "")) == name for c in self.coach_pool):
                continue
            self.coach_pool.append(
                {
                    "name": name,
                    "rating": rating,
                    "style": self.simulator._rating_to_style(rating),
                    "offense": self.simulator._generate_coach_rating(lower=2.0, upper=4.9),
                    "defense": self.simulator._generate_coach_rating(lower=2.0, upper=4.9),
                    "goalie_dev": self.simulator._generate_coach_rating(lower=2.0, upper=4.9),
                    "w": 0,
                    "l": 0,
                    "otl": 0,
                    "cups": 0,
                    "source": "new",
                }
            )
        self.coach_pool.sort(key=lambda c: (int(c.get("cups", 0)), float(c.get("rating", 0.0))), reverse=True)

    def _replace_team_coach(
        self,
        team_name: str,
        hire_name: str | None = None,
        source: str = "fired",
    ) -> dict[str, Any]:
        team = self.simulator.get_team(team_name)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        standings_map = {rec.team.name: rec for rec in self.simulator.get_standings()}
        rec = standings_map.get(team_name)

        old_name = team.coach_name
        old_rating = float(team.coach_rating)
        fired_row = {
            "name": old_name,
            "rating": round(old_rating, 2),
            "style": team.coach_style,
            "offense": round(team.coach_offense, 2),
            "defense": round(team.coach_defense, 2),
            "goalie_dev": round(team.coach_goalie_dev, 2),
            "w": int(rec.wins if rec is not None else 0),
            "l": int(rec.losses if rec is not None else 0),
            "otl": int(rec.ot_losses if rec is not None else 0),
            "cups": self._coach_cup_count(old_name),
            "source": source,
        }
        if all(str(c.get("name", "")) != old_name for c in self.coach_pool):
            self.coach_pool.append(fired_row)

        self._ensure_coach_pool_depth()
        active_names = self._active_coach_names()
        available = [c for c in self.coach_pool if str(c.get("name", "")) not in active_names]
        if hire_name:
            hire = next((c for c in available if str(c.get("name", "")) == hire_name), None)
            if hire is None:
                raise HTTPException(status_code=404, detail="Selected coach not found in candidate pool")
        else:
            if not available:
                self._ensure_coach_pool_depth(min_size=18)
                active_names = self._active_coach_names()
                available = [c for c in self.coach_pool if str(c.get("name", "")) not in active_names]
            if not available:
                raise HTTPException(status_code=400, detail="No available coaches")
            top_pool = sorted(
                available,
                key=lambda c: (int(c.get("cups", 0)), float(c.get("rating", 0.0))),
                reverse=True,
            )[:6]
            rng = getattr(self.simulator, "_rng", random.Random())
            hire = rng.choice(top_pool)

        self.coach_pool = [c for c in self.coach_pool if str(c.get("name", "")) != str(hire.get("name", ""))]
        team.coach_name = str(hire.get("name", "Coach"))
        team.coach_rating = float(hire.get("rating", 3.0))
        team.coach_style = str(hire.get("style", "balanced"))
        team.coach_offense = float(hire.get("offense", team.coach_rating))
        team.coach_defense = float(hire.get("defense", team.coach_rating))
        team.coach_goalie_dev = float(hire.get("goalie_dev", team.coach_rating))
        team.coach_tenure_seasons = 0
        team.coach_changes_recent = min(5.0, max(0.0, team.coach_changes_recent) + 1.0)
        team.coach_honeymoon_games_remaining = 24
        team.set_default_lineup()
        self.simulator._save_state()
        self._add_news(
            kind="coach_change",
            headline=f"Coach Change: {team.name}",
            details=f"{old_name} out, {team.coach_name} hired.",
            team=team.name,
            day=int(self.simulator.current_day),
        )
        return {
            "team": team.name,
            "old_name": old_name,
            "old_rating": round(old_rating, 2),
            "new_name": team.coach_name,
            "new_rating": round(team.coach_rating, 2),
            "new_style": team.coach_style,
            "new_offense": round(team.coach_offense, 2),
            "new_defense": round(team.coach_defense, 2),
            "new_goalie_dev": round(team.coach_goalie_dev, 2),
        }

    def _cpu_gm_review(self, day: int, phase: str = "regular") -> list[dict[str, Any]]:
        if phase != "regular" or day < 28:
            return []
        # Weekly cadence so AI GMs don't churn constantly.
        if day % 7 != 0:
            return []
        standings = self.simulator.get_standings()
        rec_map = {r.team.name: r for r in standings}
        rng = getattr(self.simulator, "_rng", random.Random())
        moves: list[dict[str, Any]] = []

        for team in self.simulator.teams:
            if team.name == self.user_team_name:
                continue
            rec = rec_map.get(team.name)
            if rec is None or rec.games_played < 18:
                continue
            if team.coach_honeymoon_games_remaining > 0:
                continue

            div_rows = self.simulator.get_division_standings(team.division)
            div_rank = next((idx + 1 for idx, row in enumerate(div_rows) if row.team.name == team.name), len(div_rows))
            point_pct = float(rec.point_pct)
            goal_diff_pg = rec.goal_diff / max(1, rec.games_played)

            # Build multi-season playoff context so successful coaches get realistic leash.
            recent_playoff_security = 0.0
            recent_tags: list[str] = []
            for season in reversed(self.simulator.season_history[-3:]):
                if not isinstance(season, dict):
                    continue
                made, result = self._playoff_outcome_for_team(season, team.name)
                if made != "Y":
                    continue
                if result == "Champion":
                    recent_playoff_security += 1.25
                    recent_tags.append("Champion")
                elif result == "Cup Final":
                    recent_playoff_security += 0.95
                    recent_tags.append("Cup Final")
                elif result == "Conference Final":
                    recent_playoff_security += 0.70
                    recent_tags.append("Conference Final")
                elif result == "Second Round":
                    recent_playoff_security += 0.35
                    recent_tags.append("Second Round")
                elif result == "First Round":
                    recent_playoff_security += 0.12
                    recent_tags.append("First Round")
            recent_playoff_security = min(1.6, recent_playoff_security)

            hot_seat = 0.0
            hot_seat += max(0.0, 0.52 - point_pct) * 1.35
            hot_seat += max(0.0, -goal_diff_pg) * 0.16
            hot_seat += max(0.0, 3.15 - team.coach_rating) * 0.34
            hot_seat += 0.14 if div_rank >= max(4, len(div_rows) - 1) else 0.0
            hot_seat += min(0.25, team.coach_changes_recent * 0.03)
            # Recent deep playoff success strongly suppresses firing odds.
            hot_seat = max(0.0, hot_seat - recent_playoff_security * 0.82)

            fire_probability = max(0.0, min(0.55, hot_seat * 0.16))

            # Require meaningful sustained underperformance before serious risk appears.
            if point_pct < 0.420 and rec.games_played >= 40:
                fire_probability += 0.10
            if point_pct < 0.390 and rec.games_played >= 54:
                fire_probability += 0.12
            if point_pct < 0.360 and rec.games_played >= 60:
                fire_probability += 0.16

            # Recent Cup/Conference finalists almost never get fired unless collapse is severe.
            if "Champion" in recent_tags or "Cup Final" in recent_tags:
                if not (point_pct < 0.390 and rec.games_played >= 54):
                    fire_probability *= 0.10
                else:
                    fire_probability *= 0.35
            elif "Conference Final" in recent_tags:
                if not (point_pct < 0.405 and rec.games_played >= 48):
                    fire_probability *= 0.22
                else:
                    fire_probability *= 0.55

            fire_probability = min(0.62, max(0.0, fire_probability))

            if rng.random() < fire_probability:
                result = self._replace_team_coach(team_name=team.name, source="cpu_fired")
                moves.append(
                    {
                        "type": "coach_change",
                        "team": team.name,
                        "old_coach": result["old_name"],
                        "new_coach": result["new_name"],
                        "old_rating": result["old_rating"],
                        "new_rating": result["new_rating"],
                        "reason": (
                            f"CPU GM move on Day {day} "
                            f"({rec.wins}-{rec.losses}-{rec.ot_losses}, Div {div_rank}, PCT {point_pct:.3f})"
                        ),
                    }
                )
        return moves

    def _team_slug(self, team_name: str) -> str:
        return team_name.lower().replace(" ", "_")

    def _flag_emoji(self, country_code: str) -> str:
        code = country_code.upper().strip()
        if len(code) != 2 or not code.isalpha():
            return ""
        base = 127397
        return chr(base + ord(code[0])) + chr(base + ord(code[1]))

    def _player_bio_row(self, player: Player) -> dict[str, Any]:
        rng = random.Random(f"bio:{player.player_id}")
        if player.position in GOALIE_POSITIONS:
            height_inches = rng.randint(72, 78)
            weight = rng.randint(180, 235)
        elif player.position in {"C", "LW", "RW"}:
            height_inches = rng.randint(68, 77)
            weight = rng.randint(165, 225)
        else:
            height_inches = rng.randint(70, 79)
            weight = rng.randint(175, 240)
        feet = height_inches // 12
        inches = height_inches % 12
        shot = "L" if rng.random() < 0.68 else "R"
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        year = max(1965, 2026 - int(player.age))
        country = str(player.birth_country or "Canada")
        country_code = str(player.birth_country_code or "CA").upper()
        return {
            "team": player.team_name,
            "name": player.name,
            "position": player.position,
            "age": player.age,
            "height": f"{feet}' {inches}\"",
            "weight_lbs": weight,
            "shot": shot,
            "birth_place": f"{country} ({country_code})",
            "birthdate": f"{month:02d}/{day:02d}/{str(year)[-2:]}",
            "country": country,
            "country_code": country_code,
            "injured": player.is_injured,
            "injured_games_remaining": player.injured_games_remaining,
        }

    def _team_logo_path(self, team_name: str):
        base_assets = Path(__file__).resolve().parents[2] / "assets"
        slug = self._team_slug(team_name)
        candidates = [
            base_assets / "team_logos" / f"{slug}.png",
            base_assets / f"{slug}.png",
            base_assets / "team_logos" / f"{slug}.jpg",
            base_assets / f"{slug}.jpg",
            base_assets / "team_logos" / f"{slug}.jpeg",
            base_assets / f"{slug}.jpeg",
        ]
        return next((p for p in candidates if p.exists()), None)

    def _record_to_dict(self, rec: TeamRecord) -> dict[str, Any]:
        return {
            "team": rec.team.name,
            "logo_url": f"/api/team-logo/{self._team_slug(rec.team.name)}",
            "conference": rec.team.conference,
            "division": rec.team.division,
            "gp": rec.games_played,
            "w": rec.wins,
            "l": rec.losses,
            "otl": rec.ot_losses,
            "pts": rec.points,
            "home": rec.home_record,
            "away": rec.away_record,
            "gf": rec.goals_for,
            "ga": rec.goals_against,
            "diff": rec.goal_diff,
            "l10": rec.last10,
            "strk": rec.streak,
            "pp_pct": round(rec.pp_pct, 3),
            "pk_pct": round(rec.pk_pct, 3),
        }

    def _three_stars(self, game: GameResult) -> list[dict[str, str]]:
        skater_lines: dict[str, dict[str, object]] = {}

        def add_goal_event_team(events: list[Any], team_name: str) -> None:
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

        add_goal_event_team(game.home_goal_events, game.home.name)
        add_goal_event_team(game.away_goal_events, game.away.name)

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

        def goalie_star_score(saves: int, shots: int, goals_against: int, won: bool, overtime: bool) -> float:
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
                if overtime:
                    score += 8.0
            if goals_against == 0:
                score += 135.0
            if goals_against >= 5:
                score -= 60.0
            elif goals_against == 4:
                score -= 32.0
            if shots >= 38 and goals_against >= 4:
                score += 15.0
            return max(0.0, score)

        if game.home_goalie is not None and game.home_goalie_shots > 0:
            score = goalie_star_score(
                saves=game.home_goalie_saves,
                shots=game.home_goalie_shots,
                goals_against=game.away_goals,
                won=game.home_goals > game.away_goals,
                overtime=game.overtime,
            )
            candidates.append((score, f"{game.home_goalie.name} ({game.home.name}) {game.home_goalie_saves}/{game.home_goalie_shots} SV"))
        if game.away_goalie is not None and game.away_goalie_shots > 0:
            score = goalie_star_score(
                saves=game.away_goalie_saves,
                shots=game.away_goalie_shots,
                goals_against=game.home_goals,
                won=game.away_goals > game.home_goals,
                overtime=game.overtime,
            )
            candidates.append((score, f"{game.away_goalie.name} ({game.away.name}) {game.away_goalie_saves}/{game.away_goalie_shots} SV"))

        candidates.sort(key=lambda row: row[0], reverse=True)
        labels = ["1st Star", "2nd Star", "3rd Star"]
        return [{"label": labels[idx], "summary": summary} for idx, (_, summary) in enumerate(candidates[:3])]

    def _period_box_score(self, game: GameResult, rng: Any) -> list[dict[str, Any]]:
        periods: list[dict[str, Any]] = [
            {"label": "1", "home": 0, "away": 0},
            {"label": "2", "home": 0, "away": 0},
            {"label": "3", "home": 0, "away": 0},
        ]
        regulation_weights = [0.30, 0.34, 0.36]

        def distribute(goals: int, side: str) -> None:
            for _ in range(max(0, goals)):
                if rng is not None:
                    idx = int(rng.choices([0, 1, 2], weights=regulation_weights, k=1)[0])
                else:
                    idx = 2
                periods[idx][side] += 1

        home_reg_goals = game.home_goals
        away_reg_goals = game.away_goals
        home_won = game.home_goals > game.away_goals
        if game.overtime:
            if home_won:
                home_reg_goals = max(0, game.home_goals - 1)
            else:
                away_reg_goals = max(0, game.away_goals - 1)

        distribute(home_reg_goals, "home")
        distribute(away_reg_goals, "away")

        if game.overtime:
            ot = {"label": "OT", "home": 1 if home_won else 0, "away": 0 if home_won else 1}
            periods.append(ot)
        return periods

    def _game_commentary(
        self, game: GameResult, periods: list[dict[str, Any]], stars: list[dict[str, str]]
    ) -> list[str]:
        lines: list[str] = []
        home_won = game.home_goals > game.away_goals
        winner = game.home.name if home_won else game.away.name
        loser = game.away.name if home_won else game.home.name
        lead = (
            f"{winner} edged {loser} {game.home_goals}-{game.away_goals}{' in overtime' if game.overtime else ''}."
            if home_won
            else f"{winner} edged {loser} {game.away_goals}-{game.home_goals}{' in overtime' if game.overtime else ''}."
        )

        home_after_two = int(periods[0]["home"]) + int(periods[1]["home"])
        away_after_two = int(periods[0]["away"]) + int(periods[1]["away"])
        flow_parts: list[str] = []
        if home_won and home_after_two < away_after_two:
            flow_parts.append(f"{game.home.name} erased a {away_after_two}-{home_after_two} deficit after 40 minutes")
        elif (not home_won) and away_after_two < home_after_two:
            flow_parts.append(f"{game.away.name} erased a {home_after_two}-{away_after_two} deficit after 40 minutes")
        elif home_after_two == away_after_two:
            flow_parts.append("the teams were level through two periods")

        third_home = int(periods[2]["home"]) if len(periods) >= 3 else 0
        third_away = int(periods[2]["away"]) if len(periods) >= 3 else 0
        if third_home != third_away:
            push_team = game.home.name if third_home > third_away else game.away.name
            flow_parts.append(
                f"{push_team} controlled the third period {max(third_home, third_away)}-{min(third_home, third_away)}"
            )
        if len(periods) >= 4:
            flow_parts.append("a single finish in overtime settled it")

        if flow_parts:
            lines.append(f"{lead} In game flow terms, " + "; ".join(flow_parts) + ".")
        else:
            lines.append(lead)

        details: list[str] = []
        if game.home_pp_chances > 0 or game.away_pp_chances > 0:
            details.append(
                f"Special teams: {game.home.name} {game.home_pp_goals}/{game.home_pp_chances} PP, "
                f"{game.away.name} {game.away_pp_goals}/{game.away_pp_chances} PP."
            )

        if game.home_goalie is not None and game.away_goalie is not None:
            home_sv = (
                f"{game.home_goalie_saves}/{game.home_goalie_shots}"
                if game.home_goalie_shots > 0
                else "0/0"
            )
            away_sv = (
                f"{game.away_goalie_saves}/{game.away_goalie_shots}"
                if game.away_goalie_shots > 0
                else "0/0"
            )
            details.append(
                f"Goalies: {game.home_goalie.name} {home_sv} SV, {game.away_goalie.name} {away_sv} SV."
            )
            total_shots = game.home_goalie_shots + game.away_goalie_shots
            details.append(
                f"Shot profile: {total_shots} total shots in a {'high-event' if total_shots >= 58 else 'controlled'} contest."
            )

        injuries = len(game.home_injuries) + len(game.away_injuries)
        if injuries > 0:
            details.append(f"Injury report: {injuries} player{'s' if injuries != 1 else ''} left banged up.")

        if details:
            lines.append("Notebook: " + " ".join(details))

        if stars:
            lines.append(
                "Three Stars: " + " | ".join(f"{s.get('label', '')}: {s.get('summary', '')}" for s in stars[:3])
            )
        return lines

    def _serialize_games(self, day_results: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        rng = getattr(self.simulator, "_rng", None)
        for result in day_results:
            home_rec = standings.get(result.home.name)
            away_rec = standings.get(result.away.name)
            home_point_pct = home_rec.point_pct if home_rec is not None else 0.5
            away_point_pct = away_rec.point_pct if away_rec is not None else 0.5
            arena_capacity = max(9500, int(getattr(result.home, "arena_capacity", 16000)))
            home_fan_score = float(self._fan_sentiment(result.home.name, self._recent_regular_team_games(result.home.name, limit=6))["score"])
            away_fan_score = float(self._fan_sentiment(result.away.name, self._recent_regular_team_games(result.away.name, limit=6))["score"])
            base_attendance = int(arena_capacity * (0.58 + home_fan_score / 230.0))
            quality_bump = int((home_point_pct - 0.5) * 5200 + (away_point_pct - 0.5) * 1800 + (away_fan_score - 50.0) * 28.0)
            rivalry_bump = 900 if result.home.division == result.away.division else (350 if result.home.conference == result.away.conference else 0)
            noise = rng.randint(-500, 700) if rng is not None else 0
            attendance = max(8200, min(arena_capacity, base_attendance + quality_bump + rivalry_bump + noise))
            stars = self._three_stars(result)
            periods = self._period_box_score(result, rng)
            commentary = self._game_commentary(result, periods, stars)
            out.append(
                {
                    "home": result.home.name,
                    "away": result.away.name,
                    "home_goals": result.home_goals,
                    "away_goals": result.away_goals,
                    "overtime": result.overtime,
                    "home_record": (
                        f"{home_rec.wins}-{home_rec.losses}-{home_rec.ot_losses}" if home_rec is not None else ""
                    ),
                    "away_record": (
                        f"{away_rec.wins}-{away_rec.losses}-{away_rec.ot_losses}" if away_rec is not None else ""
                    ),
                    "home_goalie": result.home_goalie.name if result.home_goalie is not None else "",
                    "away_goalie": result.away_goalie.name if result.away_goalie is not None else "",
                    "home_goalie_sv": (
                        f"{result.home_goalie_saves}/{result.home_goalie_shots}" if result.home_goalie is not None and result.home_goalie_shots > 0 else ""
                    ),
                    "away_goalie_sv": (
                        f"{result.away_goalie_saves}/{result.away_goalie_shots}" if result.away_goalie is not None and result.away_goalie_shots > 0 else ""
                    ),
                    "three_stars": stars,
                    "periods": periods,
                    "commentary": commentary,
                    "attendance": attendance,
                    "arena_capacity": arena_capacity,
                }
            )
        return out

    def _player_to_dict(self, player: Player, team_goal_diff: float = 0.0) -> dict[str, Any]:
        gp = max(1, player.games_played)
        position = player.position
        country_code = str(player.birth_country_code or "CA").upper()
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

        if position == "D":
            toi_per_game = 18.0 + player.defense * 1.55 + player.playmaking * 0.25
        elif position == "G":
            toi_per_game = 0.0
        else:
            toi_per_game = 11.2 + player.scoring_weight * 2.05 + player.defense * 0.35
        toi_per_game = round(max(0.0, min(30.0, toi_per_game)), 1)

        plus_minus = int(round((player.points / gp - 0.55) * gp * 0.34 + team_goal_diff * 0.18))
        pim = int(round(gp * (0.24 + player.physical * 0.40)))
        return {
            "team": player.team_name,
            "name": player.name,
            "country": player.birth_country,
            "country_code": country_code,
            "flag": self._flag_emoji(country_code),
            "age": player.age,
            "position": player.position,
            "gp": player.games_played,
            "g": player.goals,
            "a": player.assists,
            "p": player.points,
            "plus_minus": plus_minus,
            "pim": pim,
            "toi_g": toi_per_game,
            "ppg": ppg,
            "ppa": ppa,
            "shg": shg,
            "sha": sha,
            "shots": shots,
            "shot_pct": round(shot_pct, 1),
            "injured": player.is_injured,
            "injured_games_remaining": player.injured_games_remaining,
        }

    def _cup_count(self, team_name: str) -> int:
        return sum(1 for s in self.simulator.season_history if str(s.get("champion", "")) == team_name)

    def _cup_seasons(self, team_name: str) -> list[int]:
        seasons: list[int] = []
        for season in self.simulator.season_history:
            if str(season.get("champion", "")) == team_name:
                seasons.append(int(season.get("season", 0)))
        return seasons

    def _serialize_playoff_games(self, games: list[dict[str, Any]], round_name: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        rng = getattr(self.simulator, "_rng", None)
        for game in games:
            if not isinstance(game, dict):
                continue
            home = str(game.get("home", ""))
            away = str(game.get("away", ""))
            home_goals = int(game.get("home_goals", 0))
            away_goals = int(game.get("away_goals", 0))
            overtime = bool(game.get("overtime", False))
            fake = type("PlayoffGameStub", (), {})()
            fake.home_goals = home_goals
            fake.away_goals = away_goals
            fake.overtime = overtime
            fake.home_pp_chances = 0
            fake.home_pp_goals = 0
            fake.away_pp_chances = 0
            fake.away_pp_goals = 0
            fake.home_goalie = None
            fake.away_goalie = None
            fake.home_goalie_saves = 0
            fake.home_goalie_shots = 0
            fake.away_goalie_saves = 0
            fake.away_goalie_shots = 0
            fake.home_injuries = []
            fake.away_injuries = []
            fake.home = type("TeamRef", (), {"name": home})()
            fake.away = type("TeamRef", (), {"name": away})()
            periods = self._period_box_score(fake, getattr(self.simulator, "_rng", None))
            winner = str(game.get("winner", ""))
            game_no = int(game.get("game", 0))
            home_team = self.simulator.get_team(home)
            away_team = self.simulator.get_team(away)
            home_goalie_name = str(game.get("home_goalie", "")).strip()
            away_goalie_name = str(game.get("away_goalie", "")).strip()
            if not home_goalie_name and home_team is not None:
                if home_team.starting_goalie_name:
                    home_goalie_name = home_team.starting_goalie_name
                else:
                    goalies = home_team.dressed_goalies() or home_team.active_goalies()
                    home_goalie_name = goalies[0].name if goalies else ""
            if not away_goalie_name and away_team is not None:
                if away_team.starting_goalie_name:
                    away_goalie_name = away_team.starting_goalie_name
                else:
                    goalies = away_team.dressed_goalies() or away_team.active_goalies()
                    away_goalie_name = goalies[0].name if goalies else ""
            arena_capacity = int(game.get("arena_capacity") or (max(9500, int(getattr(home_team, "arena_capacity", 16000))) if home_team is not None else 16000))
            if game.get("attendance") is not None:
                attendance = int(game.get("attendance") or 0)
            else:
                # Deterministic fallback for older saves that did not persist attendance.
                token = f"{self.simulator.season_number}:{round_name}:{game_no}:{home}:{away}"
                stable = sum(ord(ch) for ch in token)
                base_attendance = int(arena_capacity * 0.93)
                rivalry_bump = (
                    1000
                    if home_team is not None and away_team is not None and home_team.division == away_team.division
                    else 450
                )
                noise = (stable % 1250) - 500
                attendance = max(8600, min(arena_capacity, base_attendance + rivalry_bump + noise))
            commentary = [
                (
                    f"{winner} took Game {game_no} of the {round_name} series, winning {away} at {home} {away_goals}-{home_goals}{' in overtime' if overtime else ''}."
                    if winner == away
                    else f"{winner} took Game {game_no} of the {round_name} series, winning {away} at {home} {home_goals}-{away_goals}{' in overtime' if overtime else ''}."
                ),
                "The series pressure remained high as each shift carried elimination-level intensity.",
            ]
            out.append(
                {
                    "home": home,
                    "away": away,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "overtime": overtime,
                    "home_goalie": home_goalie_name,
                    "away_goalie": away_goalie_name,
                    "home_goalie_sv": "",
                    "away_goalie_sv": "",
                    "attendance": attendance,
                    "arena_capacity": arena_capacity,
                    "periods": periods,
                    "commentary": commentary,
                    "three_stars": [],
                    "round": round_name,
                    "game_number": game_no,
                    "winner": winner,
                    "series_higher_seed": str(game.get("series_higher_seed", "")),
                    "series_lower_seed": str(game.get("series_lower_seed", "")),
                    "series_high_wins": int(game.get("series_high_wins", 0)),
                    "series_low_wins": int(game.get("series_low_wins", 0)),
                }
            )
        return out

    def _goalie_to_dict(self, player: Player) -> dict[str, Any]:
        country_code = str(player.birth_country_code or "CA").upper()
        return {
            "team": player.team_name,
            "name": player.name,
            "country": player.birth_country,
            "country_code": country_code,
            "flag": self._flag_emoji(country_code),
            "age": player.age,
            "gp": player.goalie_games,
            "w": player.goalie_wins,
            "l": player.goalie_losses,
            "otl": player.goalie_ot_losses,
            "so": player.goalie_shutouts,
            "gaa": round(player.gaa, 2),
            "sv_pct": round(player.save_pct, 3),
            "injured": player.is_injured,
            "injured_games_remaining": player.injured_games_remaining,
        }

    def lines(self, team_name: str | None = None) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")

        # If user is not overriding lines, keep coach-generated combinations current.
        if team.name == self.user_team_name and not self.override_coach_for_lines:
            team.set_default_lineup()
        elif not team.line_assignments:
            team.set_default_lineup()

        def _player_row(p: Player) -> dict[str, Any]:
            country_code = str(p.birth_country_code or "CA").upper()
            return {
                "name": p.name,
                "pos": p.position,
                "country": p.birth_country,
                "country_code": country_code,
                "flag": self._flag_emoji(country_code),
                "age": p.age,
                "shooting": round(p.shooting, 2),
                "playmaking": round(p.playmaking, 2),
                "defense": round(p.defense, 2),
                "goaltending": round(p.goaltending, 2),
                "physical": round(p.physical, 2),
                "durability": round(p.durability, 2),
            }

        by_name = {p.name: p for p in team.roster}

        def _slot_player(slot: str) -> dict[str, Any] | None:
            player_name = str(team.line_assignments.get(slot, "")).strip()
            if not player_name:
                return None
            player = by_name.get(player_name)
            if player is None:
                return None
            row = _player_row(player)
            expected = "D" if slot.startswith("LD") or slot.startswith("RD") else ("G" if slot.startswith("G") else slot[:-1])
            row["slot"] = slot
            row["expected_pos"] = expected
            row["out_of_position"] = player.position != expected
            return row

        units: list[dict[str, Any]] = []
        for i in range(1, 5):
            units.append(
                {
                    "unit": f"U{i}",
                    "LW": _slot_player(f"LW{i}"),
                    "C": _slot_player(f"C{i}"),
                    "RW": _slot_player(f"RW{i}"),
                    "LD": _slot_player(f"LD{i}") if i <= 3 else None,
                    "RD": _slot_player(f"RD{i}") if i <= 3 else None,
                    "G": _slot_player(f"G{i}") if i <= 2 else None,
                }
            )

        candidates = [_player_row(p) for p in sorted(team.active_players(), key=lambda p: (p.position, p.name))]
        assigned_names = {str(team.line_assignments.get(slot, "")).strip() for slot in ALL_LINE_SLOTS}
        assigned_names.discard("")
        extra_players = [
            _player_row(p)
            for p in sorted(team.roster, key=lambda x: (x.position, x.name))
            if (not p.is_injured) and (p.name not in assigned_names)
        ]
        injuries = [
            {
                "name": p.name,
                "pos": p.position,
                "country": p.birth_country,
                "country_code": str(p.birth_country_code or "CA").upper(),
                "flag": self._flag_emoji(str(p.birth_country_code or "CA").upper()),
                "games_remaining": p.injured_games_remaining,
            }
            for p in sorted(team.roster, key=lambda x: (x.injured_games_remaining * -1, x.name))
            if p.is_injured
        ]

        return {
            "team": team.name,
            "coach": {
                "name": team.coach_name,
                "rating": round(team.coach_rating, 2),
                "style": team.coach_style,
            },
            "override_coach_for_lines": bool(team.name == self.user_team_name and self.override_coach_for_lines),
            "position_penalty": round(team.lineup_position_penalty(), 3),
            "assignments": {slot: str(team.line_assignments.get(slot, "")) for slot in ALL_LINE_SLOTS},
            "units": units,
            "candidates": candidates,
            "extra_players": extra_players,
            "injuries": injuries,
        }

    def set_lines(self, team_name: str | None, assignments: dict[str, str]) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        if chosen != self.user_team_name:
            raise HTTPException(status_code=403, detail="Can only edit lines for your team")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        clean: dict[str, str] = {}
        for slot in ALL_LINE_SLOTS:
            raw = assignments.get(slot, "")
            clean[slot] = str(raw).strip()
        team.set_line_assignments(clean)
        return self.lines(team_name=team.name)

    def _wildcard_rows(self, conference: str) -> list[dict[str, Any]]:
        conf_rows = self.simulator.get_conference_standings(conference)
        divisions = sorted({r.team.division for r in conf_rows})
        if len(divisions) != 2:
            return [self._record_to_dict(r) for r in conf_rows]

        div_a, div_b = divisions[0], divisions[1]
        a_rows = [r for r in conf_rows if r.team.division == div_a]
        b_rows = [r for r in conf_rows if r.team.division == div_b]
        a_top = a_rows[:3]
        b_top = b_rows[:3]
        qualified = {r.team.name for r in a_top + b_top}
        wild = [r for r in conf_rows if r.team.name not in qualified]

        out: list[dict[str, Any]] = []
        out.append({"kind": "header", "label": f"{div_a} Top 3"})
        out.extend([{"kind": "team", **self._record_to_dict(r)} for r in a_top])
        out.append({"kind": "header", "label": f"{div_b} Top 3"})
        out.extend([{"kind": "team", **self._record_to_dict(r)} for r in b_top])
        out.append({"kind": "header", "label": "Wild Card"})
        for idx, r in enumerate(wild, start=1):
            row = {"kind": "team", **self._record_to_dict(r)}
            row["wc"] = f"WC{idx}" if idx <= 2 else ""
            out.append(row)
            if idx == 2 and len(wild) > 2:
                out.append({"kind": "cutline", "label": "Cut Line"})
        return out

    def meta(self) -> dict[str, Any]:
        teams = [t.name for t in self.simulator.teams]
        user_team = self.simulator.get_team(self.user_team_name) if self.user_team_name else None
        in_playoffs = self.simulator.has_playoff_session()
        reg_total = self.simulator.total_days
        playoff_total = len(self.simulator.pending_playoff_days)
        playoff_day = int(self.simulator.pending_playoff_day_index)
        display_day = self.simulator.current_day
        display_total = reg_total
        if in_playoffs:
            display_day = reg_total + max(0, playoff_day)
            display_total = reg_total + max(0, playoff_total)
        return {
            "teams": teams,
            "team_logos": {team: f"/api/team-logo/{self._team_slug(team)}" for team in teams},
            "conferences": self.simulator.get_conferences(),
            "divisions": self.simulator.get_divisions(),
            "strategies": self.simulator.strategies,
            "user_team": self.user_team_name,
            "user_team_logo": f"/api/team-logo/{self._team_slug(self.user_team_name)}" if self.user_team_name else "",
            "user_strategy": self.user_strategy,
            "use_coach": not (self.override_coach_for_lines or self.override_coach_for_strategy),
            "override_coach_for_lines": self.override_coach_for_lines,
            "override_coach_for_strategy": self.override_coach_for_strategy,
            "game_mode": self.game_mode,
            "user_coach_name": user_team.coach_name if user_team is not None else "",
            "user_coach_rating": round(user_team.coach_rating, 2) if user_team is not None else 0.0,
            "user_coach_style": user_team.coach_style if user_team is not None else "",
            "draft_focus": self.simulator.get_draft_focus(self.user_team_name) if self.user_team_name else "auto",
            "draft_focus_options": list(self.simulator.DRAFT_FOCUS_OPTIONS),
            "season": self.simulator.season_number,
            "day": display_day,
            "total_days": display_total,
            "in_playoffs": in_playoffs,
        }

    def standings(self, mode: str, value: str | None) -> dict[str, Any]:
        if mode == "conference":
            if not value:
                raise HTTPException(status_code=400, detail="conference value is required")
            rows = [self._record_to_dict(r) for r in self.simulator.get_conference_standings(value)]
            return {"mode": mode, "rows": rows}
        if mode == "division":
            if not value:
                raise HTTPException(status_code=400, detail="division value is required")
            rows = [self._record_to_dict(r) for r in self.simulator.get_division_standings(value)]
            return {"mode": mode, "rows": rows}
        if mode == "wildcard":
            if not value:
                groups = {
                    conference: self._wildcard_rows(conference) for conference in self.simulator.get_conferences()
                }
                return {"mode": mode, "groups": groups}
            return {"mode": mode, "rows": self._wildcard_rows(value)}
        rows = [self._record_to_dict(r) for r in self.simulator.get_standings()]
        return {"mode": "league", "rows": rows}

    def players(self, scope: str, team: str | None) -> list[dict[str, Any]]:
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        if scope == "team":
            if not team:
                raise HTTPException(status_code=400, detail="team is required for team scope")
            rows = [p for p in self.simulator.get_player_stats(team_name=team) if p.position != "G"]
            return [
                self._player_to_dict(
                    p,
                    team_goal_diff=(standings.get(p.team_name).goal_diff if standings.get(p.team_name) is not None else 0.0),
                )
                for p in rows
            ]
        rows = [p for p in self.simulator.get_player_stats() if p.position != "G"]
        return [
            self._player_to_dict(
                p,
                team_goal_diff=(standings.get(p.team_name).goal_diff if standings.get(p.team_name) is not None else 0.0),
            )
            for p in rows
        ]

    def goalies(self, scope: str, team: str | None) -> list[dict[str, Any]]:
        if scope == "team":
            if not team:
                raise HTTPException(status_code=400, detail="team is required for team scope")
            return [self._goalie_to_dict(p) for p in self.simulator.get_goalie_stats(team_name=team)]
        return [self._goalie_to_dict(p) for p in self.simulator.get_goalie_stats()]

    def minor_league(self, team_name: str | None = None) -> list[dict[str, Any]]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")

        rows: list[dict[str, Any]] = []
        for p in sorted(
            team.minor_roster,
            key=lambda x: (
                0 if x.position in GOALIE_POSITIONS else 1,
                -(x.goaltending if x.position in GOALIE_POSITIONS else (x.shooting + x.playmaking + x.defense)),
                x.name,
            ),
        ):
            country_code = str(p.birth_country_code or "CA").upper()
            rows.append(
                {
                    "team": team.name,
                    "name": p.name,
                    "position": p.position,
                    "age": p.age,
                    "country": p.birth_country,
                    "country_code": country_code,
                    "flag": self._flag_emoji(country_code),
                    "tier": p.prospect_tier,
                    "seasons_to_nhl": p.seasons_to_nhl,
                    "overall": round(
                        p.goaltending
                        if p.position in GOALIE_POSITIONS
                        else (p.shooting * 0.36 + p.playmaking * 0.30 + p.defense * 0.24 + p.physical * 0.10),
                        2,
                    ),
                    "injured": p.is_injured,
                    "injured_games_remaining": p.injured_games_remaining,
                }
            )
        return rows

    def roster(self, team_name: str | None = None) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")

        groups: dict[str, list[dict[str, Any]]] = {
            "Centers": [],
            "Left Wings": [],
            "Right Wings": [],
            "Defensemen": [],
            "Goalies": [],
        }
        for p in sorted(team.roster, key=lambda x: (x.position, x.name)):
            row = self._player_bio_row(p)
            if p.position == "C":
                groups["Centers"].append(row)
            elif p.position == "LW":
                groups["Left Wings"].append(row)
            elif p.position == "RW":
                groups["Right Wings"].append(row)
            elif p.position == "D":
                groups["Defensemen"].append(row)
            else:
                groups["Goalies"].append(row)
        return {
            "team": team.name,
            "captain": team.captain_name,
            "assistants": list(team.assistant_names),
            "groups": groups,
        }

    def set_draft_focus(self, team_name: str | None, focus: str) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        if chosen != self.user_team_name:
            raise HTTPException(status_code=403, detail="Can only set draft focus for your team")
        try:
            selected = self.simulator.set_draft_focus(chosen, focus)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "team": chosen,
            "focus": selected,
            "options": list(self.simulator.DRAFT_FOCUS_OPTIONS),
        }

    def _current_career_row(self, player: Player) -> dict[str, Any]:
        country_code = str(player.birth_country_code or "CA").upper()
        return {
            "season": self.simulator.season_number,
            "team": player.team_name,
            "age": player.age,
            "position": player.position,
            "country": player.birth_country,
            "country_code": country_code,
            "flag": self._flag_emoji(country_code),
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
            "gaa": round(player.gaa, 2),
            "sv_pct": round(player.save_pct, 3),
            "is_current": True,
        }

    def player_career(self, team_name: str, player_name: str) -> dict[str, Any]:
        team = self.simulator.get_team(team_name)
        if team is None:
            team = next((t for t in self.simulator.teams if t.name.lower() == team_name.lower()), None)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        player = next((p for p in [*team.roster, *team.minor_roster] if p.name == player_name), None)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        history_rows = [row for row in player.career_seasons if isinstance(row, dict)]
        draft_label = "Undrafted"
        if player.draft_overall is not None and player.draft_round is not None and player.draft_season is not None:
            draft_label = f"S{player.draft_season} R{player.draft_round} #{player.draft_overall} ({player.draft_team or team.name})"
        country_code = str(player.birth_country_code or "CA").upper()
        return {
            "player": {
                "team": player.team_name,
                "name": player.name,
                "age": player.age,
                "position": player.position,
                "country": player.birth_country,
                "country_code": country_code,
                "flag": self._flag_emoji(country_code),
                "draft_label": draft_label,
            },
            "career": [self._current_career_row(player), *history_rows],
        }

    def _fan_sentiment(self, team_name: str, recent_games: list[dict[str, Any]]) -> dict[str, Any]:
        if not recent_games:
            recent_games = self._recent_regular_team_games(team_name=team_name, limit=6)
        team = self.simulator.get_team(team_name)
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        rec = standings.get(team_name)
        score = 50.0
        if rec is not None:
            score += (rec.point_pct - 0.5) * 42.0
            score += max(-6.0, min(10.0, rec.goal_diff / max(1.0, rec.games_played) * 3.2))
        if team is not None:
            score += (team.coach_rating - 3.0) * 3.0

        trend_points: list[int] = []
        for g in recent_games[:6]:
            home = str(g.get("home", ""))
            away = str(g.get("away", ""))
            hg = int(g.get("home_goals", 0))
            ag = int(g.get("away_goals", 0))
            if home == team_name:
                won = hg > ag
                diff = hg - ag
            else:
                won = ag > hg
                diff = ag - hg
            trend_points.append((5 if won else -4) + max(-2, min(3, diff)))
        score += sum(trend_points) * 0.9
        score = max(0.0, min(100.0, score))

        if score >= 75:
            mood = "Buzzing"
        elif score >= 62:
            mood = "Optimistic"
        elif score >= 46:
            mood = "Steady"
        elif score >= 33:
            mood = "Restless"
        else:
            mood = "Frustrated"
        recent_three = trend_points[:3]
        trend_total = sum(recent_three)
        trend = "Rising" if trend_total >= 4 else ("Falling" if trend_total <= -4 else "Flat")
        return {
            "score": round(score, 1),
            "mood": mood,
            "trend": trend,
            "summary": f"{mood} fan mood ({trend.lower()} trend) based on recent results and season form.",
        }

    def _recent_regular_team_games(self, team_name: str, limit: int = 6) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for day_row in reversed(self.daily_results):
            if int(day_row.get("season", 0)) != self.simulator.season_number:
                continue
            if str(day_row.get("phase", "regular")) != "regular":
                continue
            games = day_row.get("games", [])
            if not isinstance(games, list):
                continue
            for g in games:
                if not isinstance(g, dict):
                    continue
                if str(g.get("home", "")) == team_name or str(g.get("away", "")) == team_name:
                    rows.append(dict(g))
            if len(rows) >= limit:
                break
        return rows[:limit]

    def _locker_room_sentiment(self, team_name: str, recent_games: list[dict[str, Any]]) -> dict[str, Any]:
        team = self.simulator.get_team(team_name)
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        rec = standings.get(team_name)
        score = 55.0
        if rec is not None:
            score += (rec.point_pct - 0.5) * 30.0
        if team is not None:
            injuries = sum(1 for p in team.roster if p.is_injured)
            score -= injuries * 2.2
            score -= max(0.0, team.coach_changes_recent) * 1.6
            score += max(0.0, team.coach_honeymoon_games_remaining) * 0.12

        trend_points: list[int] = []
        for g in recent_games[:6]:
            home = str(g.get("home", ""))
            away = str(g.get("away", ""))
            hg = int(g.get("home_goals", 0))
            ag = int(g.get("away_goals", 0))
            if home == team_name:
                won = hg > ag
                diff = hg - ag
            else:
                won = ag > hg
                diff = ag - hg
            trend_points.append((4 if won else -3) + max(-2, min(2, diff)))
        score += sum(trend_points) * 0.7
        score = max(0.0, min(100.0, score))

        if score >= 74:
            mood = "Locked In"
        elif score >= 62:
            mood = "Confident"
        elif score >= 48:
            mood = "Neutral"
        elif score >= 35:
            mood = "Tense"
        else:
            mood = "Shaken"
        recent_three = trend_points[:3]
        trend_total = sum(recent_three)
        trend = "Rising" if trend_total >= 3 else ("Falling" if trend_total <= -3 else "Flat")
        return {
            "score": round(score, 1),
            "mood": mood,
            "trend": trend,
            "summary": f"{mood} room ({trend.lower()} trend) shaped by results, injuries, and staff stability.",
        }

    def playoff_data(self) -> dict[str, Any]:
        if isinstance(self.simulator.pending_playoffs, dict) and self.simulator.pending_playoffs:
            return {
                "source": "live",
                "revealed_days": self.simulator.pending_playoff_day_index,
                "total_days": len(self.simulator.pending_playoff_days),
                "playoffs": self.simulator.pending_playoffs,
            }
        if self.simulator.season_history:
            latest = self.simulator.season_history[-1]
            raw = latest.get("playoffs", {})
            if isinstance(raw, dict) and raw:
                return {
                    "source": "last_completed",
                    "season": latest.get("season"),
                    "playoffs": raw,
                }
        return {"source": "none", "playoffs": {}}

    def _playoff_outcome_for_team(self, season: dict[str, object], team_name: str) -> tuple[str, str]:
        playoffs = season.get("playoffs", {})
        if not isinstance(playoffs, dict):
            return ("N", "-")
        rounds = playoffs.get("rounds", [])
        if not isinstance(rounds, list):
            return ("N", "-")
        appeared = False
        best_stage = 0
        champion = str(season.get("champion", "")) == team_name
        if champion:
            return ("Y", "Champion")
        for round_row in rounds:
            if not isinstance(round_row, dict):
                continue
            round_name = str(round_row.get("name", ""))
            series_rows = round_row.get("series", [])
            if not isinstance(series_rows, list):
                continue
            for series in series_rows:
                if not isinstance(series, dict):
                    continue
                teams = {str(series.get("higher_seed", "")), str(series.get("lower_seed", ""))}
                if team_name not in teams:
                    continue
                appeared = True
                stage = 1
                if "Division Final" in round_name or "Conference Semifinal" in round_name:
                    stage = 2
                elif "Conference Final" in round_name:
                    stage = 3
                elif "Cup Final" in round_name:
                    stage = 4
                best_stage = max(best_stage, stage)
        if not appeared:
            return ("N", "-")
        if best_stage >= 4:
            return ("Y", "Cup Final")
        if best_stage == 3:
            return ("Y", "Conference Final")
        if best_stage == 2:
            return ("Y", "Second Round")
        return ("Y", "First Round")

    def _franchise_leaders(
        self, team_name: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        totals: dict[str, dict[str, Any]] = {}
        for entry in self.simulator.hall_of_fame:
            if str(entry.get("team_at_retirement", "")) != team_name:
                continue
            player_id = str(entry.get("player_id", entry.get("name", "")))
            row = totals.setdefault(
                player_id,
                {
                    "name": str(entry.get("name", "")),
                    "g": int(entry.get("career_g", 0)),
                    "a": int(entry.get("career_a", 0)),
                    "p": int(entry.get("career_p", 0)),
                    "w": int(entry.get("goalie_w", 0)),
                    "status": "Retired",
                },
            )
            row["g"] = max(int(row["g"]), int(entry.get("career_g", 0)))
            row["a"] = max(int(row["a"]), int(entry.get("career_a", 0)))
            row["p"] = max(int(row["p"]), int(entry.get("career_p", 0)))
            row["w"] = max(int(row["w"]), int(entry.get("goalie_w", 0)))

        team = self.simulator.get_team(team_name)
        if team is not None:
            for player in team.roster:
                career_g = sum(int(s.get("g", 0)) for s in player.career_seasons if isinstance(s, dict)) + player.goals
                career_a = sum(int(s.get("a", 0)) for s in player.career_seasons if isinstance(s, dict)) + player.assists
                career_p = sum(int(s.get("p", 0)) for s in player.career_seasons if isinstance(s, dict)) + player.points
                career_w = (
                    sum(int(s.get("goalie_w", 0)) for s in player.career_seasons if isinstance(s, dict))
                    + player.goalie_wins
                )
                row = totals.setdefault(
                    player.player_id,
                    {"name": player.name, "g": 0, "a": 0, "p": 0, "w": 0, "status": "Retired"},
                )
                row["name"] = player.name
                row["g"] = max(int(row["g"]), career_g)
                row["a"] = max(int(row["a"]), career_a)
                row["p"] = max(int(row["p"]), career_p)
                row["w"] = max(int(row["w"]), career_w)
                row["status"] = "Active"

        def top(metric: str) -> list[dict[str, Any]]:
            ranked = sorted(
                [v for v in totals.values() if int(v.get(metric, 0)) > 0],
                key=lambda x: (int(x.get(metric, 0)), str(x.get("name", ""))),
                reverse=True,
            )[:10]
            return [
                {"name": str(v.get("name", "")), "value": int(v.get(metric, 0)), "status": str(v.get("status", ""))}
                for v in ranked
            ]

        return (top("p"), top("g"), top("a"), top("w"))

    def _season_team_points_leaders(self, season_no: int) -> dict[str, tuple[str, int]]:
        leaders: dict[str, tuple[str, int]] = {}
        for entries in self.simulator.career_history.values():
            if not isinstance(entries, list):
                continue
            for row in entries:
                if not isinstance(row, dict):
                    continue
                if int(row.get("season", 0)) != int(season_no):
                    continue
                team_name = str(row.get("team", "")).strip()
                if not team_name:
                    continue
                points = int(row.get("p", 0))
                name = str(row.get("name", "")).strip()
                if not name:
                    continue
                current = leaders.get(team_name)
                if current is None or points > current[1] or (points == current[1] and name < current[0]):
                    leaders[team_name] = (name, points)
        return leaders

    def cup_history(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for season in sorted(
            [s for s in self.simulator.season_history if isinstance(s, dict)],
            key=lambda s: int(s.get("season", 0)),
            reverse=True,
        ):
            season_no = int(season.get("season", 0))
            winner = str(season.get("champion", "")).strip()
            playoffs = season.get("playoffs", {})
            runner_up = ""
            if isinstance(playoffs, dict):
                rounds = playoffs.get("rounds", [])
                if isinstance(rounds, list):
                    cup_round = next(
                        (r for r in rounds if isinstance(r, dict) and str(r.get("name", "")).strip() == "Cup Final"),
                        None,
                    )
                    if isinstance(cup_round, dict):
                        series_rows = cup_round.get("series", [])
                        if isinstance(series_rows, list) and series_rows:
                            s0 = series_rows[0] if isinstance(series_rows[0], dict) else {}
                            runner_up = str(s0.get("loser", "")).strip()
                            if not runner_up:
                                high = str(s0.get("higher_seed", "")).strip()
                                low = str(s0.get("lower_seed", "")).strip()
                                if winner and high and low:
                                    runner_up = low if winner == high else high

            coaches = season.get("coaches", [])
            winner_coach = "-"
            runner_coach = "-"
            if isinstance(coaches, list):
                w_row = next((r for r in coaches if isinstance(r, dict) and str(r.get("team", "")) == winner), None)
                if isinstance(w_row, dict):
                    winner_coach = str(w_row.get("coach", "-"))
                r_row = next((r for r in coaches if isinstance(r, dict) and str(r.get("team", "")) == runner_up), None)
                if isinstance(r_row, dict):
                    runner_coach = str(r_row.get("coach", "-"))

            leadership = season.get("leadership", [])
            leader_map: dict[str, dict[str, Any]] = {}
            if isinstance(leadership, list):
                for row in leadership:
                    if not isinstance(row, dict):
                        continue
                    tname = str(row.get("team", "")).strip()
                    if tname:
                        leader_map[tname] = row
            winner_captain = str(leader_map.get(winner, {}).get("captain", "-")) if winner else "-"
            runner_captain = str(leader_map.get(runner_up, {}).get("captain", "-")) if runner_up else "-"
            playoffs_mvp = ""
            if isinstance(playoffs, dict):
                mvp_row = playoffs.get("mvp", {})
                if isinstance(mvp_row, dict):
                    mvp_name = str(mvp_row.get("name", "")).strip()
                    mvp_summary = str(mvp_row.get("summary", "")).strip()
                    if mvp_name and mvp_summary:
                        playoffs_mvp = f"{mvp_name} - {mvp_summary}"
                    elif mvp_name:
                        playoffs_mvp = mvp_name
            mvp_label = playoffs_mvp or "-"

            rows.append(
                {
                    "season": season_no,
                    "winner": winner,
                    "winner_logo_url": f"/api/team-logo/{self._team_slug(winner)}" if winner else "",
                    "winner_captain": winner_captain,
                    "winner_coach": winner_coach,
                    "runner_up": runner_up,
                    "runner_logo_url": f"/api/team-logo/{self._team_slug(runner_up)}" if runner_up else "",
                    "runner_captain": runner_captain,
                    "runner_coach": runner_coach,
                    "mvp": mvp_label,
                }
            )
        return rows

    def franchise(self, team_name: str) -> dict[str, Any]:
        team = self.simulator.get_team(team_name)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")

        history_rows: list[dict[str, Any]] = []
        for season in self.simulator.season_history:
            standings = season.get("standings", [])
            if not isinstance(standings, list):
                continue
            team_row = next((r for r in standings if isinstance(r, dict) and str(r.get("team", "")) == team_name), None)
            if team_row is None:
                continue
            league_rows = [r for r in standings if isinstance(r, dict)]
            league_rank = next((i + 1 for i, r in enumerate(league_rows) if str(r.get("team", "")) == team_name), 0)
            conference = str(team_row.get("conference", team.conference))
            division = str(team_row.get("division", team.division))
            conf_rows = [r for r in league_rows if str(r.get("conference", "")) == conference]
            div_rows = [r for r in league_rows if str(r.get("division", "")) == division]
            conf_rank = next((i + 1 for i, r in enumerate(conf_rows) if str(r.get("team", "")) == team_name), 0)
            div_rank = next((i + 1 for i, r in enumerate(div_rows) if str(r.get("team", "")) == team_name), 0)
            playoffs_made, playoff_result = self._playoff_outcome_for_team(season, team_name)
            history_rows.append(
                {
                    "season": season.get("season", ""),
                    "gp": team_row.get("gp", 0),
                    "w": team_row.get("wins", 0),
                    "l": team_row.get("losses", 0),
                    "otl": team_row.get("ot_losses", 0),
                    "pts": team_row.get("points", 0),
                    "league_rank": league_rank,
                    "conference_rank": conf_rank,
                    "division_rank": div_rank,
                    "division_title": "Y" if div_rank == 1 else "",
                    "playoff": playoffs_made,
                    "playoff_result": playoff_result,
                    "conference_champ": "Y" if playoff_result == "Cup Final" else "",
                    "cup_winner": "Y" if str(season.get("champion", "")) == team_name else "",
                }
            )

        coach_rows: list[dict[str, Any]] = []
        for season in self.simulator.season_history:
            coaches = season.get("coaches", [])
            if not isinstance(coaches, list):
                continue
            row = next(
                (r for r in coaches if isinstance(r, dict) and str(r.get("team", "")) == team_name),
                None,
            )
            if row is None:
                continue
            coach_rows.append(
                {
                    "season": season.get("season", ""),
                    "coach": row.get("coach", "-"),
                    "rating": row.get("coach_rating", "-"),
                    "style": row.get("coach_style", "-"),
                    "w": row.get("wins", 0),
                    "l": row.get("losses", 0),
                    "otl": row.get("ot_losses", 0),
                    "pts": row.get("points", 0),
                    "point_pct": row.get("point_pct", 0.0),
                    "champion": "Y" if str(season.get("champion", "")) == team_name else "",
                }
            )

        retired_rows: list[dict[str, Any]] = []
        draft_rows: list[dict[str, Any]] = []
        for season in reversed(self.simulator.season_history):
            season_no = int(season.get("season", 0))
            retired = season.get("retired", [])
            if isinstance(retired, list):
                for entry in retired:
                    text = str(entry)
                    if text.endswith(f"({team_name})"):
                        retired_rows.append({"season": season_no, "entry": text})
            draft_details = season.get("draft_details", {})
            if isinstance(draft_details, dict):
                picks = draft_details.get(team_name, [])
                if isinstance(picks, list):
                    for p in picks:
                        if not isinstance(p, dict):
                            continue
                        draft_rows.append(
                            {
                                "season": season_no,
                                "name": str(p.get("name", "")),
                                "position": str(p.get("position", "")),
                                "country": str(p.get("country", "")),
                                "country_code": str(p.get("country_code", "")),
                                "flag": self._flag_emoji(str(p.get("country_code", ""))),
                                "round": int(p.get("round") or 0),
                                "overall": int(p.get("overall") or 0),
                            }
                        )

        leaders_p, leaders_g, leaders_a, leaders_w = self._franchise_leaders(team_name)
        return {
            "team": team_name,
            "cup_count": self._cup_count(team_name),
            "history": history_rows,
            "leaders": {
                "points": leaders_p,
                "goals": leaders_g,
                "assists": leaders_a,
                "goalie_wins": leaders_w,
            },
            "coaches": coach_rows,
            "retired": retired_rows[:60],
            "draft_picks": draft_rows[:120],
        }

    def advance(self) -> dict[str, Any]:
        if not self.user_team_name:
            raise HTTPException(status_code=400, detail="No user team selected")

        if not self.simulator.is_complete():
            day_num = self.simulator.current_day
            results = self.simulator.simulate_next_day(
                user_team_name=self.user_team_name,
                user_strategy=self.user_strategy,
                use_user_lines=self.override_coach_for_lines,
                use_user_strategy=self.override_coach_for_strategy,
            )
            self._injury_news_from_results(day_num=day_num, results=results)
            serialized = self._serialize_games(results)
            self.daily_results = [
                d
                for d in self.daily_results
                if not (
                    int(d.get("season", 0)) == self.simulator.season_number
                    and int(d.get("day", 0)) == day_num
                )
            ]
            self.daily_results.append(
                {
                    "season": self.simulator.season_number,
                    "day": day_num,
                    "phase": "regular",
                    "games": serialized,
                }
            )
            gm_moves = self._cpu_gm_review(day=day_num, phase="regular")
            self._save_runtime_state()
            return {
                "phase": "regular",
                "season": self.simulator.season_number,
                "day": day_num,
                "total_days": self.simulator.total_days,
                "games": serialized,
                "gm_moves": gm_moves,
                "season_complete": self.simulator.is_complete(),
            }

        if not self.simulator.has_playoff_session():
            self.simulator.start_playoffs()
        if not self.simulator.playoffs_finished():
            playoff_day = self.simulator.simulate_next_playoff_day()
            day_no = int(playoff_day.get("day_number", 0))
            day_data = playoff_day.get("day", {})
            round_name = str(day_data.get("round", "Playoffs")) if isinstance(day_data, dict) else "Playoffs"
            raw_games = day_data.get("games", []) if isinstance(day_data, dict) else []
            serialized = self._serialize_playoff_games(raw_games if isinstance(raw_games, list) else [], round_name)
            self.daily_results = [
                d
                for d in self.daily_results
                if not (
                    int(d.get("season", 0)) == self.simulator.season_number
                    and int(d.get("day", 0)) == day_no
                )
            ]
            self.daily_results.append(
                {
                    "season": self.simulator.season_number,
                    "day": day_no,
                    "phase": "playoffs",
                    "round": round_name,
                    "games": serialized,
                }
            )
            self._save_runtime_state()
            return {
                "phase": "playoffs",
                "day": day_no,
                "total_days": playoff_day.get("total_days", 0),
                "round": round_name,
                "games": serialized,
                "playoffs_complete": bool(playoff_day.get("complete", False)),
            }

        offseason = self.simulator.finalize_offseason_after_playoffs()
        if not offseason.get("advanced"):
            raise HTTPException(status_code=500, detail="Could not finalize offseason")
        completed = int(offseason.get("completed_season", self.simulator.season_number))
        drafted_details = offseason.get("drafted_details", {})
        if isinstance(drafted_details, dict):
            self._draft_news_from_offseason(completed_season=completed, drafted_details=drafted_details)
        self._save_runtime_state()
        return {
            "phase": "offseason",
            "completed_season": offseason.get("completed_season"),
            "next_season": offseason.get("next_season"),
            "champion": offseason.get("champion"),
        }

    def day_board(self, day: int) -> dict[str, Any]:
        season = self.simulator.season_number
        in_playoffs = self.simulator.has_playoff_session()
        total_days = len(self.simulator.pending_playoff_days) if in_playoffs else self.simulator.total_days
        completed_days = len(
            [
                d
                for d in self.daily_results
                if int(d.get("season", 0)) == season
                and str(d.get("phase", "regular")) == ("playoffs" if in_playoffs else "regular")
            ]
        )
        if day <= 0:
            if completed_days > 0:
                safe_day = completed_days
            else:
                fallback_day = self.simulator.pending_playoff_day_index if in_playoffs else self.simulator.current_day
                safe_day = max(1, min(max(1, fallback_day), max(1, total_days)))
        else:
            safe_day = max(1, min(day, max(1, total_days)))
        played = next(
            (
                d
                for d in self.daily_results
                if int(d.get("season", 0)) == season and int(d.get("day", 0)) == safe_day
                and str(d.get("phase", "regular")) == ("playoffs" if in_playoffs else "regular")
            ),
            None,
        )
        if played is not None:
            return {
                "season": season,
                "day": safe_day,
                "total_days": total_days,
                "completed_days": completed_days,
                "phase": str(played.get("phase", "regular")),
                "round": str(played.get("round", "")),
                "status": "played",
                "games": played.get("games", []),
            }

        if in_playoffs:
            pending = self.simulator.pending_playoff_days
            idx = safe_day - 1
            if 0 <= idx < len(pending):
                day_row = pending[idx]
                round_name = str(day_row.get("round", "Playoffs"))
                raw_games = day_row.get("games", [])
                games = self._serialize_playoff_games(raw_games if isinstance(raw_games, list) else [], round_name)
                return {
                    "season": season,
                    "day": safe_day,
                    "total_days": total_days,
                    "completed_days": completed_days,
                    "phase": "playoffs",
                    "round": round_name,
                    "status": "scheduled",
                    "games": games,
                }

        day_idx = safe_day - 1
        if 0 <= day_idx < len(self.simulator._season_days):
            games = self.simulator._season_days[day_idx]
            return {
                "season": season,
                "day": safe_day,
                "total_days": total_days,
                "completed_days": completed_days,
                "status": "scheduled",
                "games": [{"home": home.name, "away": away.name} for home, away in games],
            }
        return {
            "season": season,
            "day": safe_day,
            "total_days": total_days,
            "completed_days": completed_days,
            "status": "none",
            "games": [],
        }

    def home_panel(self) -> dict[str, Any]:
        team = self.simulator.get_team(self.user_team_name)
        if team is None:
            raise HTTPException(status_code=404, detail="User team not found")

        latest_game: dict[str, Any] | None = None
        latest_day_games: list[dict[str, Any]] = []
        latest_day = -1
        for day_row in reversed(self.daily_results):
            if int(day_row.get("season", 0)) != self.simulator.season_number:
                continue
            if str(day_row.get("phase", "regular")) != "regular":
                continue
            games = day_row.get("games", [])
            if not isinstance(games, list):
                continue
            team_games = [
                g
                for g in games
                if isinstance(g, dict)
                and (str(g.get("home", "")) == team.name or str(g.get("away", "")) == team.name)
            ]
            if team_games:
                latest_day_games = [dict(g) for g in team_games]
                for tg in latest_day_games:
                    tg["game_day"] = int(day_row.get("day", 0))
            for game in games:
                if not isinstance(game, dict):
                    continue
                if str(game.get("home", "")) == team.name or str(game.get("away", "")) == team.name:
                    latest_game = dict(game)
                    latest_day = int(day_row.get("day", 0))
                    latest_game["game_day"] = latest_day
                    break
            if latest_game is not None:
                break

        recent_team_games: list[dict[str, Any]] = []
        for day_row in reversed(self.daily_results):
            if int(day_row.get("season", 0)) != self.simulator.season_number:
                continue
            if str(day_row.get("phase", "regular")) != "regular":
                continue
            games = day_row.get("games", [])
            if not isinstance(games, list):
                continue
            for g in games:
                if not isinstance(g, dict):
                    continue
                if str(g.get("home", "")) == team.name or str(g.get("away", "")) == team.name:
                    row = dict(g)
                    row["game_day"] = int(day_row.get("day", 0))
                    recent_team_games.append(row)
            if len(recent_team_games) >= 6:
                break

        upcoming_game: dict[str, Any] | None = None
        upcoming_game_day: int | None = None
        upcoming_phase = "regular"
        upcoming_round: str | None = None
        if self.simulator.has_playoff_session():
            pending = self.simulator.pending_playoff_days
            start_idx = int(self.simulator.pending_playoff_day_index)
            for day_idx in range(start_idx, len(pending)):
                day_row = pending[day_idx]
                round_name = str(day_row.get("round", "Playoffs"))
                serialized = self._serialize_playoff_games(
                    day_row.get("games", []) if isinstance(day_row.get("games", []), list) else [],
                    round_name,
                )
                game = next(
                    (g for g in serialized if str(g.get("home", "")) == team.name or str(g.get("away", "")) == team.name),
                    None,
                )
                if game is not None:
                    upcoming_game = game
                    upcoming_game_day = day_idx + 1
                    upcoming_phase = "playoffs"
                    upcoming_round = round_name
                    break
        else:
            for idx in range(int(self.simulator._day_index), len(self.simulator._season_days)):
                day_games = self.simulator._season_days[idx]
                for home, away in day_games:
                    if home.name == team.name or away.name == team.name:
                        upcoming_game = {"home": home.name, "away": away.name}
                        upcoming_game_day = idx + 1
                        break
                if upcoming_game is not None:
                    break

        payload: dict[str, Any] = {
            "team": team.name,
            "logo_url": f"/api/team-logo/{self._team_slug(team.name)}",
            "cup_count": self._cup_count(team.name),
            "cup_seasons": self._cup_seasons(team.name),
            "season": self.simulator.season_number,
            "day": self.simulator.current_day,
            "coach": {
                "name": team.coach_name,
                "rating": round(team.coach_rating, 2),
                "style": team.coach_style,
                "offense": round(team.coach_offense, 2),
                "defense": round(team.coach_defense, 2),
                "goalie_dev": round(team.coach_goalie_dev, 2),
                "record": "0-0-0",
                "tenure_seasons": team.coach_tenure_seasons,
                "changes_recent": round(team.coach_changes_recent, 2),
                "honeymoon_games_remaining": team.coach_honeymoon_games_remaining,
            },
            "control": {
                "user_strategy": self.user_strategy,
                "use_coach": not (self.override_coach_for_lines or self.override_coach_for_strategy),
                "override_coach_for_lines": self.override_coach_for_lines,
                "override_coach_for_strategy": self.override_coach_for_strategy,
                "game_mode": self.game_mode,
            },
            "latest_game_day": latest_day if latest_day > 0 else None,
            "latest_game": latest_game,
            "latest_day_games": latest_day_games,
            "recent_team_games": recent_team_games[:6],
            "upcoming_game_day": upcoming_game_day,
            "upcoming_phase": upcoming_phase if upcoming_game is not None else None,
            "upcoming_round": upcoming_round,
            "upcoming_game": upcoming_game,
        }
        if self.simulator.has_playoff_session():
            seen = int(self.simulator.pending_playoff_day_index)
            pending_days = self.simulator.pending_playoff_days
            latest_team_playoff_game: dict[str, Any] | None = None
            latest_playoff_day = 0
            for day_idx in range(min(seen, len(pending_days)) - 1, -1, -1):
                day_row = pending_days[day_idx]
                round_name = str(day_row.get("round", "Playoffs"))
                serialized = self._serialize_playoff_games(
                    day_row.get("games", []) if isinstance(day_row.get("games", []), list) else [],
                    round_name,
                )
                for g in serialized:
                    if str(g.get("home", "")) == team.name or str(g.get("away", "")) == team.name:
                        latest_team_playoff_game = g
                        latest_playoff_day = day_idx + 1
                        break
                if latest_team_playoff_game is not None:
                    break
            payload["playoffs"] = {
                "active": True,
                "day": seen,
                "total_days": len(pending_days),
                "latest_team_game_day": latest_playoff_day if latest_playoff_day > 0 else None,
                "latest_team_game": latest_team_playoff_game,
            }
        else:
            payload["playoffs"] = {"active": False}
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        rec = standings.get(team.name)
        div_rows = self.simulator.get_division_standings(team.division)
        div_rank = next((i + 1 for i, row in enumerate(div_rows) if row.team.name == team.name), 0)
        payload["team_summary"] = {
            "record": f"{rec.wins}-{rec.losses}-{rec.ot_losses}" if rec is not None else "0-0-0",
            "division": team.division,
            "division_rank": div_rank,
            "points": rec.points if rec is not None else 0,
            "pp_pct": round(rec.pp_pct, 3) if rec is not None else 0.0,
            "pk_pct": round(rec.pk_pct, 3) if rec is not None else 0.0,
        }
        payload["coach"]["record"] = payload["team_summary"]["record"]
        payload["special_teams"] = {
            "pp_pct": round(rec.pp_pct, 3) if rec is not None else 0.0,
            "pk_pct": round(rec.pk_pct, 3) if rec is not None else 0.0,
        }
        payload["fan_sentiment"] = self._fan_sentiment(team.name, recent_team_games)
        payload["locker_room"] = self._locker_room_sentiment(team.name, recent_team_games)
        season_news = [dict(row) for row in self.news_feed if int(row.get("season", 0)) == int(self.simulator.season_number)]
        if season_news:
            latest_news_day = max(int(row.get("day", 0)) for row in season_news)
            payload["news"] = [row for row in season_news if int(row.get("day", 0)) == latest_news_day][:60]
        else:
            payload["news"] = []
        return payload

    def reset(self) -> dict[str, Any]:
        temp = LeagueSimulator(teams=build_default_teams(), games_per_matchup=2)
        temp.reset_persistent_history()
        self._init_fresh_state()
        try:
            self.runtime_state_path.unlink(missing_ok=True)
        except OSError:
            pass
        return self.meta()

    def coach_candidates(self) -> list[dict[str, Any]]:
        self._ensure_coach_pool_depth()
        return [dict(row) for row in self.coach_pool[:20]]

    def fire_coach(self, team_name: str | None = None, hire_name: str | None = None) -> dict[str, Any]:
        if self.game_mode == "coach":
            raise HTTPException(status_code=403, detail="Coach mode cannot fire coaches")
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        result = self._replace_team_coach(team_name=chosen, hire_name=hire_name, source="fired")
        return {
            "ok": True,
            "result": {
                "fired": True,
                "team": result["team"],
                "old_name": result["old_name"],
                "old_rating": result["old_rating"],
                "new_name": result["new_name"],
                "new_rating": result["new_rating"],
                "new_style": result["new_style"],
                "new_offense": result["new_offense"],
                "new_defense": result["new_defense"],
                "new_goalie_dev": result["new_goalie_dev"],
            },
        }

    def set_game_mode(self, mode: str) -> dict[str, Any]:
        normalized = mode.lower().strip()
        if normalized not in {"gm", "coach", "both"}:
            raise HTTPException(status_code=400, detail="Unknown game mode")
        self.game_mode = normalized
        self._save_runtime_state()
        return {
            "ok": True,
            "game_mode": self.game_mode,
            "override_coach_for_lines": self.override_coach_for_lines,
            "override_coach_for_strategy": self.override_coach_for_strategy,
        }

    def set_control_overrides(
        self,
        override_coach_for_lines: bool,
        override_coach_for_strategy: bool,
    ) -> dict[str, Any]:
        self.override_coach_for_lines = bool(override_coach_for_lines)
        self.override_coach_for_strategy = bool(override_coach_for_strategy)
        self._save_runtime_state()
        return {
            "ok": True,
            "override_coach_for_lines": self.override_coach_for_lines,
            "override_coach_for_strategy": self.override_coach_for_strategy,
            "game_mode": self.game_mode,
        }


service = SimService()
app = FastAPI(title="Hockey Sim API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    with service._lock:
        return service.meta()


@app.get("/api/standings")
def standings(mode: str = "league", value: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.standings(mode=mode.lower(), value=value)


@app.post("/api/user-team")
def set_user_team(payload: TeamSelection) -> dict[str, Any]:
    with service._lock:
        team = service.simulator.get_team(payload.team_name)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        service.user_team_name = team.name
        service._save_runtime_state()
        return {"ok": True, "user_team": service.user_team_name}


@app.post("/api/strategy")
def set_strategy(payload: StrategySelection) -> dict[str, Any]:
    with service._lock:
        strategy = payload.strategy.lower().strip()
        if strategy not in service.simulator.strategies:
            raise HTTPException(status_code=400, detail=f"Unknown strategy '{payload.strategy}'")
        service.user_strategy = strategy
        if payload.override_coach_for_strategy is not None:
            service.override_coach_for_strategy = bool(payload.override_coach_for_strategy)
        service._save_runtime_state()
        return {
            "ok": True,
            "strategy": service.user_strategy,
            "override_coach_for_lines": service.override_coach_for_lines,
            "override_coach_for_strategy": service.override_coach_for_strategy,
            "game_mode": service.game_mode,
        }


@app.post("/api/control-overrides")
def set_control_overrides(payload: ControlOverrideSelection) -> dict[str, Any]:
    with service._lock:
        return service.set_control_overrides(
            override_coach_for_lines=payload.override_coach_for_lines,
            override_coach_for_strategy=payload.override_coach_for_strategy,
        )


@app.post("/api/game-mode")
def set_game_mode(payload: GameModeSelection) -> dict[str, Any]:
    with service._lock:
        return service.set_game_mode(mode=payload.mode)


@app.post("/api/advance")
def advance() -> dict[str, Any]:
    with service._lock:
        return service.advance()


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    with service._lock:
        return service.reset()


@app.post("/api/fire-coach")
def fire_coach(team: str | None = None, hire: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.fire_coach(team_name=team, hire_name=hire)


@app.get("/api/coach-candidates")
def coach_candidates() -> list[dict[str, Any]]:
    with service._lock:
        return service.coach_candidates()


@app.get("/api/team-logo/{team_slug}")
def team_logo(team_slug: str):
    team_name = team_slug.replace("_", " ")
    team = service.simulator.get_team(team_name.title()) or service.simulator.get_team(team_name)
    if team is None:
        for t in service.simulator.teams:
            if service._team_slug(t.name) == team_slug:
                team = t
                break
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    path = service._team_logo_path(team.name)
    if path is None:
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path)


@app.get("/api/players")
def players(scope: str = "league", team: str | None = None) -> list[dict[str, Any]]:
    with service._lock:
        return service.players(scope=scope.lower(), team=team)


@app.get("/api/goalies")
def goalies(scope: str = "league", team: str | None = None) -> list[dict[str, Any]]:
    with service._lock:
        return service.goalies(scope=scope.lower(), team=team)


@app.get("/api/minor-league")
def minor_league(team: str | None = None) -> list[dict[str, Any]]:
    with service._lock:
        return service.minor_league(team_name=team)


@app.get("/api/roster")
def roster(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.roster(team_name=team)


@app.get("/api/lines")
def lines(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.lines(team_name=team)


@app.post("/api/lines")
def set_lines(payload: LinesSelection) -> dict[str, Any]:
    with service._lock:
        return service.set_lines(team_name=payload.team_name, assignments=payload.assignments)


@app.get("/api/player-career")
def player_career(team: str, name: str) -> dict[str, Any]:
    with service._lock:
        return service.player_career(team_name=team, player_name=name)


@app.get("/api/playoffs")
def playoffs() -> dict[str, Any]:
    with service._lock:
        return service.playoff_data()


@app.get("/api/franchise")
def franchise(team: str) -> dict[str, Any]:
    with service._lock:
        return service.franchise(team_name=team)


@app.get("/api/cup-history")
def cup_history() -> list[dict[str, Any]]:
    with service._lock:
        return service.cup_history()


@app.get("/api/day-board")
def day_board(day: int = 0) -> dict[str, Any]:
    with service._lock:
        return service.day_board(day=day)


@app.get("/api/home")
def home_panel() -> dict[str, Any]:
    with service._lock:
        return service.home_panel()


@app.post("/api/draft-need")
def set_draft_need(payload: DraftNeedSelection) -> dict[str, Any]:
    with service._lock:
        return service.set_draft_focus(team_name=payload.team_name, focus=payload.focus)


@app.get("/api/news")
def news(limit: int = 80) -> list[dict[str, Any]]:
    with service._lock:
        return service.news(limit=limit)
