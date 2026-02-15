from __future__ import annotations

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
from .models import Player, TeamRecord


class TeamSelection(BaseModel):
    team_name: str


class StrategySelection(BaseModel):
    strategy: str = "balanced"
    use_coach: bool = True


class GameModeSelection(BaseModel):
    mode: str = "both"


class SimService:
    def __init__(self) -> None:
        self._init_fresh_state()
        self._lock = Lock()

    def _init_fresh_state(self) -> None:
        teams = build_default_teams()
        self.simulator = LeagueSimulator(teams=teams, games_per_matchup=2)
        self.user_team_name = teams[0].name if teams else ""
        self.user_strategy = "balanced"
        self.use_coach = True
        self.game_mode = "both"
        self.daily_results: list[dict[str, Any]] = []

    def _team_slug(self, team_name: str) -> str:
        return team_name.lower().replace(" ", "_")

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

    def _serialize_games(self, day_results: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        rng = getattr(self.simulator, "_rng", None)
        for result in day_results:
            home_rec = standings.get(result.home.name)
            away_rec = standings.get(result.away.name)
            home_point_pct = home_rec.point_pct if home_rec is not None else 0.5
            away_point_pct = away_rec.point_pct if away_rec is not None else 0.5
            base_attendance = 14600
            quality_bump = int((home_point_pct - 0.5) * 8500 + (away_point_pct - 0.5) * 3200)
            rivalry_bump = 900 if result.home.division == result.away.division else (350 if result.home.conference == result.away.conference else 0)
            noise = rng.randint(-700, 1150) if rng is not None else 0
            attendance = max(8200, min(21200, base_attendance + quality_bump + rivalry_bump + noise))
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
                    "three_stars": self._three_stars(result),
                    "attendance": attendance,
                }
            )
        return out

    def _player_to_dict(self, player: Player) -> dict[str, Any]:
        return {
            "team": player.team_name,
            "name": player.name,
            "age": player.age,
            "position": player.position,
            "gp": player.games_played,
            "g": player.goals,
            "a": player.assists,
            "p": player.points,
            "injured": player.is_injured,
            "injured_games_remaining": player.injured_games_remaining,
        }

    def _goalie_to_dict(self, player: Player) -> dict[str, Any]:
        return {
            "team": player.team_name,
            "name": player.name,
            "age": player.age,
            "gp": player.goalie_games,
            "w": player.goalie_wins,
            "l": player.goalie_losses,
            "otl": player.goalie_ot_losses,
            "gaa": round(player.gaa, 2),
            "sv_pct": round(player.save_pct, 3),
        }

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
        return {
            "teams": teams,
            "team_logos": {team: f"/api/team-logo/{self._team_slug(team)}" for team in teams},
            "conferences": self.simulator.get_conferences(),
            "divisions": self.simulator.get_divisions(),
            "strategies": self.simulator.strategies,
            "user_team": self.user_team_name,
            "user_team_logo": f"/api/team-logo/{self._team_slug(self.user_team_name)}" if self.user_team_name else "",
            "user_strategy": self.user_strategy,
            "use_coach": self.use_coach,
            "game_mode": self.game_mode,
            "user_coach_name": user_team.coach_name if user_team is not None else "",
            "user_coach_rating": round(user_team.coach_rating, 2) if user_team is not None else 0.0,
            "user_coach_style": user_team.coach_style if user_team is not None else "",
            "season": self.simulator.season_number,
            "day": self.simulator.current_day,
            "total_days": self.simulator.total_days,
            "in_playoffs": self.simulator.has_playoff_session(),
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
        if scope == "team":
            if not team:
                raise HTTPException(status_code=400, detail="team is required for team scope")
            return [self._player_to_dict(p) for p in self.simulator.get_player_stats(team_name=team)]
        return [self._player_to_dict(p) for p in self.simulator.get_player_stats()]

    def goalies(self, scope: str, team: str | None) -> list[dict[str, Any]]:
        if scope == "team":
            if not team:
                raise HTTPException(status_code=400, detail="team is required for team scope")
            return [self._goalie_to_dict(p) for p in self.simulator.get_goalie_stats(team_name=team)]
        return [self._goalie_to_dict(p) for p in self.simulator.get_goalie_stats()]

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

        leaders_p, leaders_g, leaders_a, leaders_w = self._franchise_leaders(team_name)
        return {
            "team": team_name,
            "history": history_rows,
            "leaders": {
                "points": leaders_p,
                "goals": leaders_g,
                "assists": leaders_a,
                "goalie_wins": leaders_w,
            },
            "coaches": coach_rows,
        }

    def advance(self) -> dict[str, Any]:
        if not self.user_team_name:
            raise HTTPException(status_code=400, detail="No user team selected")

        if not self.simulator.is_complete():
            day_num = self.simulator.current_day
            results = self.simulator.simulate_next_day(
                user_team_name=self.user_team_name,
                user_strategy=self.user_strategy,
                use_user_coach=self.use_coach,
            )
            serialized = self._serialize_games(results)
            self.daily_results = [d for d in self.daily_results if int(d.get("season", 0)) != self.simulator.season_number]
            self.daily_results.append(
                {
                    "season": self.simulator.season_number,
                    "day": day_num,
                    "games": serialized,
                }
            )
            return {
                "phase": "regular",
                "season": self.simulator.season_number,
                "day": day_num,
                "total_days": self.simulator.total_days,
                "games": serialized,
                "season_complete": self.simulator.is_complete(),
            }

        if not self.simulator.has_playoff_session():
            self.simulator.start_playoffs()
        if not self.simulator.playoffs_finished():
            playoff_day = self.simulator.simulate_next_playoff_day()
            return {
                "phase": "playoffs",
                "day": playoff_day.get("day_number", 0),
                "total_days": playoff_day.get("total_days", 0),
                "round": playoff_day.get("day", {}).get("round", ""),
                "games": playoff_day.get("day", {}).get("games", []),
                "playoffs_complete": bool(playoff_day.get("complete", False)),
            }

        offseason = self.simulator.finalize_offseason_after_playoffs()
        if not offseason.get("advanced"):
            raise HTTPException(status_code=500, detail="Could not finalize offseason")
        return {
            "phase": "offseason",
            "completed_season": offseason.get("completed_season"),
            "next_season": offseason.get("next_season"),
            "champion": offseason.get("champion"),
        }

    def day_board(self, day: int) -> dict[str, Any]:
        season = self.simulator.season_number
        total_days = self.simulator.total_days
        completed_days = len([d for d in self.daily_results if int(d.get("season", 0)) == season])
        if day <= 0:
            safe_day = completed_days if completed_days > 0 else max(1, min(self.simulator.current_day, total_days))
        else:
            safe_day = max(1, min(day, total_days))
        played = next(
            (
                d
                for d in self.daily_results
                if int(d.get("season", 0)) == season and int(d.get("day", 0)) == safe_day
            ),
            None,
        )
        if played is not None:
            return {
                "season": season,
                "day": safe_day,
                "total_days": total_days,
                "completed_days": completed_days,
                "status": "played",
                "games": played.get("games", []),
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
        latest_day = -1
        for day_row in reversed(self.daily_results):
            if int(day_row.get("season", 0)) != self.simulator.season_number:
                continue
            games = day_row.get("games", [])
            if not isinstance(games, list):
                continue
            for game in games:
                if not isinstance(game, dict):
                    continue
                if str(game.get("home", "")) == team.name or str(game.get("away", "")) == team.name:
                    latest_game = dict(game)
                    latest_day = int(day_row.get("day", 0))
                    break
            if latest_game is not None:
                break

        payload: dict[str, Any] = {
            "team": team.name,
            "logo_url": f"/api/team-logo/{self._team_slug(team.name)}",
            "season": self.simulator.season_number,
            "day": self.simulator.current_day,
            "coach": {
                "name": team.coach_name,
                "rating": round(team.coach_rating, 2),
                "style": team.coach_style,
                "offense": round(team.coach_offense, 2),
                "defense": round(team.coach_defense, 2),
                "goalie_dev": round(team.coach_goalie_dev, 2),
                "tenure_seasons": team.coach_tenure_seasons,
                "changes_recent": round(team.coach_changes_recent, 2),
                "honeymoon_games_remaining": team.coach_honeymoon_games_remaining,
            },
            "control": {
                "user_strategy": self.user_strategy,
                "use_coach": self.use_coach,
                "game_mode": self.game_mode,
            },
            "latest_game_day": latest_day if latest_day > 0 else None,
            "latest_game": latest_game,
        }
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        rec = standings.get(team.name)
        div_rows = self.simulator.get_division_standings(team.division)
        div_rank = next((i + 1 for i, row in enumerate(div_rows) if row.team.name == team.name), 0)
        payload["team_summary"] = {
            "record": f"{rec.wins}-{rec.losses}-{rec.ot_losses}" if rec is not None else "0-0-0",
            "division": team.division,
            "division_rank": div_rank,
            "points": rec.points if rec is not None else 0,
        }
        payload["special_teams"] = {
            "pp_pct": round(rec.pp_pct, 3) if rec is not None else 0.0,
            "pk_pct": round(rec.pk_pct, 3) if rec is not None else 0.0,
        }
        return payload

    def reset(self) -> dict[str, Any]:
        temp = LeagueSimulator(teams=build_default_teams(), games_per_matchup=2)
        temp.reset_persistent_history()
        self._init_fresh_state()
        return self.meta()

    def fire_coach(self, team_name: str | None = None) -> dict[str, Any]:
        if self.game_mode == "coach":
            raise HTTPException(status_code=403, detail="Coach mode cannot fire coaches")
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        result = self.simulator.fire_coach(chosen)
        if not bool(result.get("fired", False)):
            raise HTTPException(status_code=400, detail="Unable to fire coach")
        return {"ok": True, "result": result}

    def set_game_mode(self, mode: str) -> dict[str, Any]:
        normalized = mode.lower().strip()
        if normalized not in {"gm", "coach", "both"}:
            raise HTTPException(status_code=400, detail="Unknown game mode")
        self.game_mode = normalized
        if normalized in {"gm", "coach"}:
            self.use_coach = True
        return {"ok": True, "game_mode": self.game_mode, "use_coach": self.use_coach}


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
        return {"ok": True, "user_team": service.user_team_name}


@app.post("/api/strategy")
def set_strategy(payload: StrategySelection) -> dict[str, Any]:
    with service._lock:
        strategy = payload.strategy.lower().strip()
        if strategy not in service.simulator.strategies:
            raise HTTPException(status_code=400, detail=f"Unknown strategy '{payload.strategy}'")
        service.user_strategy = strategy
        if service.game_mode in {"gm", "coach"}:
            service.use_coach = True
        else:
            service.use_coach = bool(payload.use_coach)
        return {
            "ok": True,
            "strategy": service.user_strategy,
            "use_coach": service.use_coach,
            "game_mode": service.game_mode,
        }


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
def fire_coach(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.fire_coach(team_name=team)


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


@app.get("/api/playoffs")
def playoffs() -> dict[str, Any]:
    with service._lock:
        return service.playoff_data()


@app.get("/api/franchise")
def franchise(team: str) -> dict[str, Any]:
    with service._lock:
        return service.franchise(team_name=team)


@app.get("/api/day-board")
def day_board(day: int = 0) -> dict[str, Any]:
    with service._lock:
        return service.day_board(day=day)


@app.get("/api/home")
def home_panel() -> dict[str, Any]:
    with service._lock:
        return service.home_panel()
