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
    Team,
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


class InboxResolveSelection(BaseModel):
    event_id: int
    choice_id: str


class CallupSelection(BaseModel):
    team_name: str | None = None
    player_name: str


class FreeAgentSignSelection(BaseModel):
    team_name: str | None = None
    player_name: str
    years: int | None = None
    cap_hit: float | None = None


class SimService:
    def __init__(self) -> None:
        self.data_root = Path(__file__).resolve().parents[2]
        self._init_fresh_state()
        self._load_runtime_state()
        self._lock = Lock()

    def _init_fresh_state(self) -> None:
        teams = build_default_teams()
        self.simulator = LeagueSimulator(
            teams=teams,
            games_per_matchup=2,
            history_path=str(self.data_root / "season_history.json"),
            career_history_path=str(self.data_root / "career_history.json"),
            hall_of_fame_path=str(self.data_root / "hall_of_fame.json"),
            state_path=str(self.data_root / "league_state.json"),
        )
        self.runtime_state_path = self.data_root / "api_runtime_state.json"
        self.user_team_name = teams[0].name if teams else ""
        self.user_strategy = "balanced"
        self.override_coach_for_lines = False
        self.override_coach_for_strategy = False
        self.game_mode = "gm"
        self.daily_results: list[dict[str, Any]] = []
        self.news_feed: list[dict[str, Any]] = []
        self.inbox_events: list[dict[str, Any]] = []
        self.next_inbox_id: int = 1
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
        raw_inbox = raw.get("inbox_events", [])
        if isinstance(raw_inbox, list):
            self.inbox_events = [row for row in raw_inbox if isinstance(row, dict)]
        else:
            self.inbox_events = []
        try:
            self.next_inbox_id = int(raw.get("next_inbox_id", 1))
        except (TypeError, ValueError):
            self.next_inbox_id = 1
        self.next_inbox_id = max(1, self.next_inbox_id)

    def _save_runtime_state(self) -> None:
        payload = {
            "user_team_name": self.user_team_name,
            "user_strategy": self.user_strategy,
            "override_coach_for_lines": self.override_coach_for_lines,
            "override_coach_for_strategy": self.override_coach_for_strategy,
            "game_mode": self.game_mode,
            "daily_results": self.daily_results[-600:],
            "news_feed": self.news_feed[:250],
            "inbox_events": self.inbox_events[-300:],
            "next_inbox_id": self.next_inbox_id,
        }
        try:
            self.runtime_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _player_overall(self, player: Player) -> float:
        if player.position == "G":
            return player.goaltending * 0.72 + player.durability * 0.18 + player.defense * 0.10
        return player.shooting * 0.38 + player.playmaking * 0.32 + player.defense * 0.22 + player.physical * 0.08

    def _user_team(self):
        if not self.user_team_name:
            return None
        return self.simulator.get_team(self.user_team_name)

    def _add_inbox_event(
        self,
        day_num: int,
        event_type: str,
        title: str,
        details: str,
        options: list[dict[str, str]],
        payload: dict[str, Any] | None = None,
        expires_in_days: int = 5,
        auto_choice_id: str | None = None,
    ) -> None:
        event = {
            "id": self.next_inbox_id,
            "season": int(self.simulator.season_number),
            "day": int(day_num),
            "type": event_type,
            "title": title,
            "details": details,
            "options": options,
            "payload": payload or {},
            "expires_day": int(day_num + max(1, expires_in_days)),
            "auto_choice_id": auto_choice_id or (options[0]["id"] if options else ""),
            "resolved": False,
            "resolution": None,
        }
        self.next_inbox_id += 1
        self.inbox_events.insert(0, event)
        self.inbox_events = self.inbox_events[:300]

    def _find_inbox_event(self, event_id: int) -> dict[str, Any] | None:
        for event in self.inbox_events:
            if int(event.get("id", 0)) == int(event_id):
                return event
        return None

    def _inbox_event_exists(
        self,
        *,
        event_type: str,
        season: int,
        day: int,
        payload_key: str = "",
    ) -> bool:
        for event in self.inbox_events:
            if str(event.get("type", "")) != event_type:
                continue
            if int(event.get("season", 0)) != int(season):
                continue
            if int(event.get("day", 0)) != int(day):
                continue
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}
            if payload_key and str(payload.get("key", "")) != payload_key:
                continue
            return True
        return False

    def _resolve_inbox_event_internal(self, event: dict[str, Any], choice_id: str, auto: bool = False) -> dict[str, Any]:
        if bool(event.get("resolved", False)):
            return event
        event_type = str(event.get("type", ""))
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        team = self._user_team()

        if team is not None and event_type == "injury":
            injured_name = str(payload.get("injured_name", ""))
            if choice_id == "recall_and_rest" and injured_name:
                player = next((p for p in [*team.roster, *team.minor_roster] if p.name == injured_name), None)
                if player is not None and player.injured_games_remaining > 0:
                    player.injured_games_remaining = max(0, player.injured_games_remaining - 1)

        if team is not None and event_type == "coach_pressure":
            if choice_id == "back_coach":
                team.coach_honeymoon_games_remaining = max(team.coach_honeymoon_games_remaining, 6)
                team.coach_changes_recent = max(0.0, team.coach_changes_recent - 0.4)
            elif choice_id == "demand_results":
                team.coach_changes_recent = min(6.0, team.coach_changes_recent + 0.55)

        if team is not None and event_type == "trade_offer":
            partner_name = str(payload.get("partner_team", ""))
            give_name = str(payload.get("give_player", ""))
            receive_name = str(payload.get("receive_player", ""))
            if choice_id == "accept_trade" and partner_name and give_name and receive_name:
                partner = self.simulator.get_team(partner_name)
                if partner is not None:
                    give_player = next((p for p in team.roster if p.name == give_name), None)
                    recv_player = next((p for p in partner.roster if p.name == receive_name), None)
                    if give_player is not None and recv_player is not None:
                        team.roster.remove(give_player)
                        partner.roster.remove(recv_player)
                        give_player.team_name = partner.name
                        recv_player.team_name = team.name
                        partner.roster.append(give_player)
                        team.roster.append(recv_player)
                        self.simulator.normalize_player_numbers()
                        team.set_default_lineup()
                        partner.set_default_lineup()
                        self._add_news(
                            kind="transaction",
                            headline=f"Trade: {team.name} acquired {receive_player} from {partner.name}",
                            details=f"{team.name} sent {give_name} to {partner.name}.",
                            team=team.name,
                            day=self.simulator.current_day,
                        )

        if team is not None and event_type == "waiver":
            if choice_id == "claim_waiver":
                pos = str(payload.get("position", "C")).upper()
                quality = float(payload.get("quality", 0.66))
                waiver_player = self.simulator._create_draft_player(
                    team_name=team.name,
                    position=pos if pos in {"C", "LW", "RW", "D", "G"} else "C",
                    quality=max(0.40, min(0.88, quality)),
                )
                waiver_player.prospect_tier = "NHL"
                waiver_player.seasons_to_nhl = 0
                team.minor_roster.append(waiver_player)
                self._add_news(
                    kind="transaction",
                    headline=f"Transaction: {team.name} claimed {waiver_player.name}",
                    details=f"Waiver claim ({waiver_player.position}) added to minor-league depth.",
                    team=team.name,
                    day=self.simulator.current_day,
                )

        if team is not None and event_type == "prospect":
            prospect_name = str(payload.get("prospect_name", ""))
            prospect = next((p for p in team.minor_roster if p.name == prospect_name), None)
            if prospect is not None:
                if choice_id == "accelerate":
                    prospect.seasons_to_nhl = max(0, int(prospect.seasons_to_nhl) - 1)
                    prospect.durability = max(1.2, prospect.durability - 0.12)
                elif choice_id == "steady":
                    prospect.prospect_potential = min(0.99, prospect.prospect_potential + 0.03)

        if team is not None and event_type == "roster_limit":
            if choice_id.startswith("demote::"):
                demote_name = choice_id.split("::", 1)[1].strip()
                if demote_name:
                    ok = self.simulator.demote_roster_player(team.name, demote_name)
                    if ok:
                        self._add_news(
                            kind="transaction",
                            headline=f"Transaction: {team.name} assigned {demote_name}",
                            details=f"{demote_name} was sent to minors after IR return roster decision.",
                            team=team.name,
                            day=self.simulator.current_day,
                        )

        event["resolved"] = True
        event["resolution"] = {
            "choice_id": choice_id,
            "auto": bool(auto),
            "season": int(self.simulator.season_number),
            "day": int(self.simulator.current_day),
        }
        return event

    def _expire_inbox_events(self, day_num: int) -> None:
        changed = False
        for event in self.inbox_events:
            if bool(event.get("resolved", False)):
                continue
            expires_day = int(event.get("expires_day", 0))
            if expires_day > 0 and expires_day < int(day_num):
                choice_id = str(event.get("auto_choice_id", "")) or "ignore"
                self._resolve_inbox_event_internal(event, choice_id=choice_id, auto=True)
                changed = True
        if changed:
            self._save_runtime_state()

    def _generate_weekly_inbox(self, day_num: int) -> None:
        team = self._user_team()
        if team is None:
            return

        unresolved_count = sum(
            1 for row in self.inbox_events
            if int(row.get("season", 0)) == int(self.simulator.season_number) and not bool(row.get("resolved", False))
        )
        if unresolved_count >= 4:
            return

        records = self.simulator.get_standings()
        team_record = next((r for r in records if r.team.name == team.name), None)
        points_pct = (team_record.points / max(2, team_record.games_played * 2)) if team_record is not None else 0.5

        injured = sorted([p for p in team.roster if p.is_injured], key=lambda p: p.injured_games_remaining, reverse=True)
        if injured:
            # Injury handling now lives in the Call Ups screen.
            pass
        elif points_pct < 0.52 or self.simulator._rng.random() < 0.30:
            self._add_inbox_event(
                day_num=day_num,
                event_type="coach_pressure",
                title="Coach Pressure Check-In",
                details=f"Management wants direction after week {max(1, day_num // 7)}. Team form is under review.",
                options=[
                    {"id": "back_coach", "label": "Back Coach", "description": "Stability boost and longer runway."},
                    {"id": "demand_results", "label": "Demand Results", "description": "Higher pressure, quicker accountability."},
                ],
                payload={},
                auto_choice_id="demand_results" if points_pct < 0.47 else "back_coach",
            )

        # Secondary event lane: trade / waiver / prospect.
        roll = self.simulator._rng.random()
        if roll < 0.45 and len(self.simulator.teams) > 1:
            partners = [t for t in self.simulator.teams if t.name != team.name and t.roster]
            if partners and team.roster:
                partner = self.simulator._rng.choice(partners)
                give_pool = sorted([p for p in team.roster if p.position != "G"], key=self._player_overall)
                recv_pool = sorted([p for p in partner.roster if p.position != "G"], key=self._player_overall, reverse=True)
                if give_pool and recv_pool:
                    give_player = give_pool[0]
                    receive_player = recv_pool[0]
                    self._add_inbox_event(
                        day_num=day_num,
                        event_type="trade_offer",
                        title=f"Trade Offer: {partner.name}",
                        details=f"{partner.name} offers {receive_player.name} for {give_player.name}.",
                        options=[
                            {"id": "accept_trade", "label": "Accept", "description": "Complete the 1-for-1 trade."},
                            {"id": "reject_trade", "label": "Reject", "description": "Keep roster unchanged."},
                        ],
                        payload={
                            "partner_team": partner.name,
                            "give_player": give_player.name,
                            "receive_player": receive_player.name,
                        },
                        auto_choice_id="reject_trade",
                    )
        elif roll < 0.75:
            positions = ["C", "LW", "RW", "D", "G"]
            pos = positions[int(self.simulator._rng.random() * len(positions))]
            q = round(0.58 + self.simulator._rng.random() * 0.20, 3)
            self._add_inbox_event(
                day_num=day_num,
                event_type="waiver",
                title="Waiver Wire Alert",
                details=f"A {pos} depth player is available on waivers this week.",
                options=[
                    {"id": "claim_waiver", "label": "Claim", "description": "Add to minor-league depth chart."},
                    {"id": "pass_waiver", "label": "Pass", "description": "No roster action."},
                ],
                payload={"position": pos, "quality": q},
                auto_choice_id="pass_waiver",
            )
        else:
            prospects = [p for p in team.minor_roster if int(getattr(p, "seasons_to_nhl", 0)) > 0]
            if prospects:
                prospect = sorted(prospects, key=lambda p: (p.seasons_to_nhl, -p.prospect_potential))[0]
                self._add_inbox_event(
                    day_num=day_num,
                    event_type="prospect",
                    title=f"Prospect Update: {prospect.name}",
                    details=f"Development staff asks for direction on {prospect.name} ({prospect.position}).",
                    options=[
                        {"id": "accelerate", "label": "Accelerate", "description": "Push timeline, slightly higher wear risk."},
                        {"id": "steady", "label": "Steady Plan", "description": "Slow build with potential upside."},
                    ],
                    payload={"prospect_name": prospect.name},
                    auto_choice_id="steady",
                )

        self._save_runtime_state()

    def _active_roster_count(self, team_name: str) -> int:
        team = self.simulator.get_team(team_name)
        if team is None:
            return 0
        return len([p for p in team.roster if not p.is_injured])

    def _demotion_candidates(self, team_name: str) -> list[Player]:
        team = self.simulator.get_team(team_name)
        if team is None:
            return []
        healthy = [p for p in team.roster if not p.is_injured]
        if not healthy:
            return []
        # Keep minimum positional structure and demote lower-value depth first.
        healthy_forwards = len([p for p in healthy if p.position in {"C", "LW", "RW"}])
        healthy_defense = len([p for p in healthy if p.position == "D"])
        healthy_goalies = len([p for p in healthy if p.position == "G"])

        def can_demote(p: Player) -> bool:
            if p.position == "G":
                return healthy_goalies > 2
            if p.position == "D":
                return healthy_defense > 6
            return healthy_forwards > 12

        candidates = [p for p in healthy if can_demote(p)]
        if not candidates:
            candidates = healthy
        candidates.sort(
            key=lambda p: (
                self._player_overall(p),
                -p.age,
                p.name,
            )
        )
        return candidates

    def _queue_roster_limit_decisions(self, day_num: int, returned_players: list[str]) -> None:
        team = self._user_team()
        if team is None:
            return
        active_count = self._active_roster_count(team.name)
        overflow = max(0, active_count - Team.MAX_ROSTER_SIZE)
        # Handle one decision at a time to keep inbox choices clear.
        if overflow <= 0:
            return
        unresolved_existing = any(
            (not bool(ev.get("resolved", False)))
            and str(ev.get("type", "")) == "roster_limit"
            and int(ev.get("season", 0)) == int(self.simulator.season_number)
            for ev in self.inbox_events
        )
        if unresolved_existing:
            return
        candidates = self._demotion_candidates(team.name)[:8]
        if not candidates:
            return
        options = [
            {
                "id": f"demote::{p.name}",
                "label": f"Send {p.name}",
                "description": f"Assign {p.name} ({p.position}) to minors to restore {Team.MAX_ROSTER_SIZE}-player active limit.",
            }
            for p in candidates
        ]
        returned_label = ", ".join(returned_players[:3]) if returned_players else "an injured player"
        details = (
            f"Active roster is {active_count}/{Team.MAX_ROSTER_SIZE} after {returned_label} returned from IR. "
            "Choose a player to send down."
        )
        self._add_inbox_event(
            day_num=day_num,
            event_type="roster_limit",
            title="Roster Limit Decision",
            details=details,
            options=options,
            payload={"returned_players": returned_players},
            expires_in_days=3,
            auto_choice_id=options[0]["id"],
        )

    def _projected_active_count_next_day(self, team_name: str) -> int:
        team = self.simulator.get_team(team_name)
        if team is None:
            return 0
        active_now = len([p for p in team.roster if not p.is_injured])
        returning_next = len([p for p in team.roster if int(p.injured_games_remaining) == 1])
        return active_now + returning_next

    def inbox(self, include_resolved: bool = False, limit: int = 60) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.inbox_events]
        if not include_resolved:
            rows = [row for row in rows if not bool(row.get("resolved", False))]
        rows = [row for row in rows if int(row.get("season", 0)) == int(self.simulator.season_number)]
        return rows[: max(1, min(limit, 200))]

    def resolve_inbox(self, event_id: int, choice_id: str) -> dict[str, Any]:
        event = self._find_inbox_event(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Inbox event not found")
        if bool(event.get("resolved", False)):
            return {"ok": True, "event": dict(event)}
        option_ids = {str(opt.get("id", "")) for opt in event.get("options", []) if isinstance(opt, dict)}
        if choice_id not in option_ids:
            raise HTTPException(status_code=400, detail="Invalid inbox choice")
        resolved = self._resolve_inbox_event_internal(event, choice_id=choice_id, auto=False)
        self._save_runtime_state()
        return {"ok": True, "event": dict(resolved)}

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
                    details=f"{inj.injury_type} | {inj.injury_status} | Expected out {inj.games_out} games after vs {result.away.name}.",
                    team=result.home.name,
                    day=day_num,
                )
            for inj in result.away_injuries:
                self._add_news(
                    kind="injury",
                    headline=f"Injury: {inj.player.name} ({result.away.name})",
                    details=f"{inj.injury_type} | {inj.injury_status} | Expected out {inj.games_out} games after at {result.home.name}.",
                    team=result.away.name,
                    day=day_num,
                )

    def _injury_inbox_from_results(self, day_num: int, results: list[GameResult]) -> None:
        team = self._user_team()
        if team is None:
            return
        user_team_name = team.name
        for result in results:
            user_side_injuries = []
            if result.home.name == user_team_name:
                user_side_injuries = list(result.home_injuries)
            elif result.away.name == user_team_name:
                user_side_injuries = list(result.away_injuries)
            for inj in user_side_injuries:
                payload_key = f"{inj.player.player_id}:{day_num}:injury"
                if self._inbox_event_exists(
                    event_type="injury_alert",
                    season=self.simulator.season_number,
                    day=day_num,
                    payload_key=payload_key,
                ):
                    continue
                self._add_inbox_event(
                    day_num=day_num,
                    event_type="injury_alert",
                    title=f"Injury Report: {inj.player.name}",
                    details=(
                        f"{inj.injury_type} | {inj.injury_status} | Expected out {inj.games_out} games. "
                        "Open Call Ups to promote a replacement if needed."
                    ),
                    options=[
                        {
                            "id": "acknowledge",
                            "label": "Acknowledge",
                            "description": "Keep simming and manage roster as needed.",
                        }
                    ],
                    payload={
                        "key": payload_key,
                        "player_name": inj.player.name,
                        "injury_type": inj.injury_type,
                        "injury_status": inj.injury_status,
                        "games_out": inj.games_out,
                        "navigate_to": "callups",
                    },
                    expires_in_days=5,
                    auto_choice_id="acknowledge",
                )

    def _returning_soon_inbox(self, day_num: int) -> None:
        team = self._user_team()
        if team is None:
            return
        for p in sorted(team.roster, key=lambda x: x.name):
            if int(p.injured_games_remaining) != 1:
                continue
            payload_key = f"{p.player_id}:{day_num}:returning"
            if self._inbox_event_exists(
                event_type="injury_returning",
                season=self.simulator.season_number,
                day=day_num,
                payload_key=payload_key,
            ):
                continue
            temp_replacements = [rp.name for rp in team.roster if str(rp.temporary_replacement_for) == p.name]
            replacement_text = f" Temporary call-up: {', '.join(temp_replacements)}." if temp_replacements else ""
            self._add_inbox_event(
                day_num=day_num,
                event_type="injury_returning",
                title=f"Return Alert: {p.name}",
                details=(
                    f"{p.name} ({p.injury_type or 'Injury'} | {p.injury_status or 'IR'}) is expected back next game day."
                    f"{replacement_text} Open Call Ups to plan your roster move."
                ),
                options=[
                    {
                        "id": "acknowledge",
                        "label": "Acknowledge",
                        "description": "Review call-ups and roster decisions.",
                    }
                ],
                payload={
                    "key": payload_key,
                    "player_name": p.name,
                    "injury_type": p.injury_type,
                    "injury_status": p.injury_status,
                    "navigate_to": "callups",
                },
                expires_in_days=2,
                auto_choice_id="acknowledge",
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

    def _retired_number_news_from_offseason(
        self,
        completed_season: int,
        retired_numbers: list[dict[str, object]],
    ) -> None:
        if not isinstance(retired_numbers, list):
            return
        display_season = completed_season + 1
        for row in retired_numbers:
            if not isinstance(row, dict):
                continue
            team = str(row.get("team", "")).strip()
            player = str(row.get("player", "")).strip()
            number = row.get("number")
            if not team or not player or number is None:
                continue
            try:
                jersey_no = int(number)
            except (TypeError, ValueError):
                continue
            self._add_news(
                kind="retired_number",
                headline=f"Retired Number: {team} retired #{jersey_no}",
                details=f"Honoring {player}.",
                team=team,
                season=display_season,
                day=0,
            )

    def _free_agency_news_from_offseason(
        self,
        completed_season: int,
        free_agency: dict[str, object],
    ) -> None:
        if not isinstance(free_agency, dict):
            return
        display_season = completed_season + 1
        re_signings = free_agency.get("re_signings", [])
        signings = free_agency.get("signings", [])
        if isinstance(re_signings, list):
            for row in re_signings[:120]:
                if not isinstance(row, dict):
                    continue
                team = str(row.get("team", "")).strip()
                player = str(row.get("player", "")).strip()
                years = int(row.get("years", 0) or 0)
                cap_hit = float(row.get("cap_hit", 0.0) or 0.0)
                if not team or not player or years <= 0:
                    continue
                self._add_news(
                    kind="contract",
                    headline=f"Extension: {team} re-signed {player}",
                    details=f"{years} years, ${cap_hit:.2f}M AAV.",
                    team=team,
                    season=display_season,
                    day=0,
                )
        if isinstance(signings, list):
            for row in signings[:160]:
                if not isinstance(row, dict):
                    continue
                team = str(row.get("team", "")).strip()
                player = str(row.get("player", "")).strip()
                years = int(row.get("years", 0) or 0)
                cap_hit = float(row.get("cap_hit", 0.0) or 0.0)
                if not team or not player or years <= 0:
                    continue
                self._add_news(
                    kind="contract",
                    headline=f"Free Agency: {team} signed {player}",
                    details=f"{years} years, ${cap_hit:.2f}M AAV.",
                    team=team,
                    season=display_season,
                    day=0,
                )

    def news(self, limit: int = 80) -> list[dict[str, Any]]:
        return [dict(row) for row in self.news_feed[: max(1, min(limit, 250))]]

    def transactions(self, team_name: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            return []
        out: list[dict[str, Any]] = []
        for row in self.news_feed:
            if str(row.get("kind", "")).lower() != "transaction":
                continue
            row_team = str(row.get("team", ""))
            headline = str(row.get("headline", ""))
            details = str(row.get("details", ""))
            if row_team == chosen or chosen in headline or chosen in details:
                out.append(dict(row))
            if len(out) >= max(1, min(limit, 500)):
                break
        return out

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

        # CPU trade window: limited weekly 1-for-1 trades with sanity checks.
        cpu_teams = [t for t in self.simulator.teams if t.name != self.user_team_name]
        attempted: set[str] = set()
        max_trades = 2
        trade_count = 0
        for buyer in sorted(cpu_teams, key=lambda t: rec_map.get(t.name).point_pct if rec_map.get(t.name) is not None else 0.5):
            if trade_count >= max_trades:
                break
            if buyer.name in attempted:
                continue
            rec_buyer = rec_map.get(buyer.name)
            if rec_buyer is None or rec_buyer.games_played < 18:
                continue
            if rec_buyer.point_pct > 0.64:
                continue

            def _healthy_pos_players(team: Any, pos: str) -> list[Player]:
                return [p for p in team.roster if p.position == pos and not p.is_injured]

            need_positions = ["C", "LW", "RW", "D", "G"]
            need_positions.sort(
                key=lambda pos: (
                    sum(self._player_overall(p) for p in _healthy_pos_players(buyer, pos)) / max(1, len(_healthy_pos_players(buyer, pos))),
                    len(_healthy_pos_players(buyer, pos)),
                )
            )
            target_pos = need_positions[0]
            buyer_pool = sorted(_healthy_pos_players(buyer, target_pos), key=self._player_overall)
            if not buyer_pool:
                continue
            buyer_out = buyer_pool[0]
            buyer_score = self._player_overall(buyer_out)

            best_deal: tuple[Any, Player, float] | None = None
            for seller in cpu_teams:
                if seller.name == buyer.name or seller.name in attempted:
                    continue
                seller_pool = sorted(_healthy_pos_players(seller, target_pos), key=self._player_overall, reverse=True)
                if target_pos == "G" and len(seller_pool) < 2:
                    continue
                if target_pos in {"C", "LW", "RW"} and len(seller_pool) < 5:
                    continue
                if target_pos == "D" and len(seller_pool) < 4:
                    continue
                if not seller_pool:
                    continue
                # Avoid swapping obvious stars: pick seller's best *expendable* player.
                candidate_idx = 1 if len(seller_pool) > 1 else 0
                seller_out = seller_pool[candidate_idx]
                seller_score = self._player_overall(seller_out)
                gain = seller_score - buyer_score
                if gain < 0.18 or gain > 0.95:
                    continue
                if best_deal is None or gain > best_deal[2]:
                    best_deal = (seller, seller_out, gain)

            if best_deal is None:
                continue

            seller, seller_out, gain = best_deal
            # Buyer sends same-position depth piece back, preserving positional plausibility.
            seller_return_pool = sorted([p for p in seller.roster if p.position == target_pos and not p.is_injured], key=self._player_overall)
            buyer_return_pool = sorted([p for p in buyer.roster if p.position == target_pos and not p.is_injured], key=self._player_overall)
            if not seller_return_pool or not buyer_return_pool:
                continue
            buyer_send = buyer_return_pool[0]
            if buyer_send.name == buyer_out.name:
                buyer_send = buyer_out
            if seller_out.name == buyer_send.name:
                continue

            seller.roster.remove(seller_out)
            buyer.roster.remove(buyer_send)
            seller.roster.append(buyer_send)
            buyer.roster.append(seller_out)
            buyer_send.team_name = seller.name
            seller_out.team_name = buyer.name
            self.simulator.normalize_player_numbers()
            buyer.set_default_lineup()
            seller.set_default_lineup()

            self._add_news(
                kind="transaction",
                headline=f"Trade: {buyer.name} acquired {seller_out.name} from {seller.name}",
                details=f"{buyer.name} sent {buyer_send.name} to {seller.name}.",
                team=buyer.name,
                day=day,
            )
            moves.append(
                {
                    "type": "trade",
                    "buyer": buyer.name,
                    "seller": seller.name,
                    "buyer_gets": seller_out.name,
                    "seller_gets": buyer_send.name,
                    "position": target_pos,
                    "gain": round(gain, 3),
                }
            )
            attempted.add(buyer.name)
            attempted.add(seller.name)
            trade_count += 1
        return moves

    def _team_slug(self, team_name: str) -> str:
        return team_name.lower().replace(" ", "_")

    def _capture_roster_state(self) -> dict[str, dict[str, set[str]]]:
        state: dict[str, dict[str, set[str]]] = {}
        for team in self.simulator.teams:
            state[team.name] = {
                "roster": {p.name for p in team.roster},
                "minors": {p.name for p in team.minor_roster},
            }
        return state

    def _log_auto_roster_transactions(self, before: dict[str, dict[str, set[str]]], day_num: int) -> None:
        for team in self.simulator.teams:
            prev = before.get(team.name, {"roster": set(), "minors": set()})
            prev_roster = prev.get("roster", set())
            prev_minors = prev.get("minors", set())
            curr_roster = {p.name for p in team.roster}
            curr_minors = {p.name for p in team.minor_roster}

            recalls = sorted(list((curr_roster - prev_roster) & prev_minors))
            assigns = sorted(list((curr_minors - prev_minors) & prev_roster))
            for name in recalls:
                self._add_news(
                    kind="transaction",
                    headline=f"Transaction: {team.name} recalled {name}",
                    details=f"{name} was promoted from minors to active roster.",
                    team=team.name,
                    day=day_num,
                )
            for name in assigns:
                self._add_news(
                    kind="transaction",
                    headline=f"Transaction: {team.name} assigned {name}",
                    details=f"{name} was moved to the minor-league club.",
                    team=team.name,
                    day=day_num,
                )

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
            "jersey_number": player.jersey_number,
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
            "jersey_number": player.jersey_number,
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
        return sum(1 for s in self.simulator.season_history if self._season_champion(s) == team_name)

    def _cup_seasons(self, team_name: str) -> list[int]:
        seasons: list[int] = []
        for season in self.simulator.season_history:
            if self._season_champion(season) == team_name:
                seasons.append(int(season.get("season", 0)))
        return seasons

    def _season_champion(self, season: object) -> str:
        if not isinstance(season, dict):
            return ""
        for key in ("champion", "cup_champion"):
            name = str(season.get(key, "")).strip()
            if name:
                return name
        playoffs = season.get("playoffs", {})
        if isinstance(playoffs, dict):
            for key in ("champion", "cup_champion"):
                name = str(playoffs.get(key, "")).strip()
                if name:
                    return name
        return ""

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
            "jersey_number": player.jersey_number,
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
                "jersey_number": p.jersey_number,
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
                    "jersey_number": p.jersey_number,
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

    def contracts(self, team_name: str | None = None) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")

        cap_limit = float(self.simulator._team_cap_limit(team))
        cap_used = float(self.simulator._team_cap_used(team))
        active_count = len([p for p in team.roster if not p.is_injured])

        def _row(p: Player) -> dict[str, Any]:
            return {
                "team": team.name,
                "name": p.name,
                "position": p.position,
                "age": p.age,
                "years_left": int(getattr(p, "contract_years_left", 0)),
                "cap_hit": round(float(getattr(p, "cap_hit", 0.0)), 2),
                "contract_type": str(getattr(p, "contract_type", "entry")),
                "is_rfa": bool(getattr(p, "is_rfa", False)),
                "injured": p.is_injured,
                "injured_games_remaining": p.injured_games_remaining,
            }

        active_rows = [_row(p) for p in sorted(team.roster, key=lambda x: (-float(getattr(x, "cap_hit", 0.0)), x.position, x.name))]
        minor_rows = [_row(p) for p in sorted(team.minor_roster, key=lambda x: (-float(getattr(x, "cap_hit", 0.0)), x.position, x.name))]
        return {
            "team": team.name,
            "cap_limit": round(cap_limit, 2),
            "cap_used": round(cap_used, 2),
            "cap_space": round(cap_limit - cap_used, 2),
            "active_count": active_count,
            "max_active": Team.MAX_ROSTER_SIZE,
            "active": active_rows,
            "minors": minor_rows,
        }

    def free_agents(self, team_name: str | None = None) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        cap_limit = float(self.simulator._team_cap_limit(team))
        cap_used = float(self.simulator._team_cap_used(team))
        rows: list[dict[str, Any]] = []
        for p in self.simulator.get_free_agents():
            ask_years, ask_cap, ask_type, ask_rfa = self.simulator._estimate_contract_offer(p)
            rows.append(
                {
                    "name": p.name,
                    "position": p.position,
                    "age": p.age,
                    "overall": round(self._player_overall(p), 2),
                    "ask_years": int(ask_years),
                    "ask_cap_hit": round(float(ask_cap), 2),
                    "contract_type": ask_type,
                    "is_rfa": bool(ask_rfa),
                }
            )
        return {
            "team": team.name,
            "cap_limit": round(cap_limit, 2),
            "cap_used": round(cap_used, 2),
            "cap_space": round(cap_limit - cap_used, 2),
            "rows": rows[:220],
        }

    def sign_free_agent(
        self,
        team_name: str | None,
        player_name: str,
        years: int | None = None,
        cap_hit: float | None = None,
    ) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        if chosen != self.user_team_name:
            raise HTTPException(status_code=403, detail="Can only sign for your team")
        result = self.simulator.sign_free_agent(
            team_name=chosen,
            player_name=player_name,
            years=years,
            cap_hit=cap_hit,
        )
        if not bool(result.get("ok", False)):
            reason = str(result.get("reason", "failed"))
            if reason == "roster_full":
                raise HTTPException(status_code=400, detail="Roster is full. Demote or place player before signing.")
            if reason == "cap_space":
                raise HTTPException(status_code=400, detail="Not enough cap space for this deal.")
            if reason == "player_not_found":
                raise HTTPException(status_code=404, detail="Free agent not found.")
            raise HTTPException(status_code=400, detail=f"Could not sign player: {reason}")

        signed_player = str(result.get("player", player_name))
        deal_years = int(result.get("years", years or 1))
        deal_cap = float(result.get("cap_hit", cap_hit or 0.0))
        self._add_news(
            kind="contract",
            headline=f"Free Agency: {chosen} signed {signed_player}",
            details=f"{deal_years} years, ${deal_cap:.2f}M AAV.",
            team=chosen,
            day=self.simulator.current_day,
        )
        self._save_runtime_state()
        return {"ok": True, "result": result}

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
        standings = {r.team.name: r for r in self.simulator.get_standings()}
        team_goal_diff = standings.get(player.team_name).goal_diff if standings.get(player.team_name) is not None else 0.0
        skater_view = self._player_to_dict(player, team_goal_diff=team_goal_diff) if player.position not in GOALIE_POSITIONS else None
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
            "plus_minus": int(skater_view["plus_minus"]) if skater_view is not None else 0,
            "pim": int(skater_view["pim"]) if skater_view is not None else 0,
            "toi_g": float(skater_view["toi_g"]) if skater_view is not None else 0.0,
            "ppg": int(skater_view["ppg"]) if skater_view is not None else 0,
            "ppa": int(skater_view["ppa"]) if skater_view is not None else 0,
            "shg": int(skater_view["shg"]) if skater_view is not None else 0,
            "sha": int(skater_view["sha"]) if skater_view is not None else 0,
            "shots": int(skater_view["shots"]) if skater_view is not None else 0,
            "shot_pct": float(skater_view["shot_pct"]) if skater_view is not None else 0.0,
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
        bio = self._player_bio_row(player)
        def _career_row_with_defaults(row: dict[str, Any]) -> dict[str, Any]:
            out = dict(row)
            out.setdefault("plus_minus", 0)
            out.setdefault("pim", 0)
            out.setdefault("toi_g", 0.0)
            out.setdefault("ppg", 0)
            out.setdefault("ppa", 0)
            out.setdefault("shg", 0)
            out.setdefault("sha", 0)
            out.setdefault("shots", 0)
            out.setdefault("shot_pct", 0.0)
            out.setdefault("goalie_so", 0)
            return out
        return {
            "player": {
                "team": player.team_name,
                "name": player.name,
                "jersey_number": player.jersey_number,
                "age": player.age,
                "position": player.position,
                "country": player.birth_country,
                "country_code": country_code,
                "flag": self._flag_emoji(country_code),
                "draft_label": draft_label,
                "height": bio.get("height", ""),
                "weight_lbs": bio.get("weight_lbs", 0),
                "shot": bio.get("shot", ""),
                "birth_place": bio.get("birth_place", ""),
                "birthdate": bio.get("birthdate", ""),
                "ratings": {
                    "shooting": round(player.shooting, 2),
                    "playmaking": round(player.playmaking, 2),
                    "defense": round(player.defense, 2),
                    "goaltending": round(player.goaltending, 2),
                    "physical": round(player.physical, 2),
                    "durability": round(player.durability, 2),
                },
            },
            "career": [_career_row_with_defaults(self._current_career_row(player)), *[_career_row_with_defaults(r) for r in history_rows]],
        }

    def callups(self, team_name: str | None = None) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(chosen)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")

        injuries = [
            {
                "name": p.name,
                "jersey_number": p.jersey_number,
                "position": p.position,
                "injury_type": p.injury_type,
                "injury_status": p.injury_status,
                "games_out": p.injured_games_remaining,
            }
            for p in sorted(team.roster, key=lambda x: (-x.injured_games_remaining, x.name))
            if p.is_injured
        ]
        returning_tomorrow = [
            {
                "name": p.name,
                "position": p.position,
                "injury_type": p.injury_type,
                "injury_status": p.injury_status,
            }
            for p in sorted(team.roster, key=lambda x: x.name)
            if int(p.injured_games_remaining) == 1
        ]

        roster_rows = []
        for p in sorted(team.roster, key=lambda x: (x.position, x.name)):
            roster_rows.append(
                {
                    "name": p.name,
                    "jersey_number": p.jersey_number,
                    "position": p.position,
                    "age": p.age,
                    "injured": p.is_injured,
                    "games_out": p.injured_games_remaining,
                    "dressed": team.is_dressed(p),
                    "temporary_replacement_for": p.temporary_replacement_for,
                    "overall": round(
                        p.goaltending
                        if p.position in GOALIE_POSITIONS
                        else (p.shooting * 0.36 + p.playmaking * 0.30 + p.defense * 0.24 + p.physical * 0.10),
                        2,
                    ),
                }
            )

        minor_rows = []
        for p in sorted(team.minor_roster, key=lambda x: (x.position, x.name)):
            minor_rows.append(
                {
                    "name": p.name,
                    "jersey_number": p.jersey_number,
                    "position": p.position,
                    "age": p.age,
                    "injured": p.is_injured,
                    "games_out": p.injured_games_remaining,
                    "tier": p.prospect_tier,
                    "seasons_to_nhl": p.seasons_to_nhl,
                    "overall": round(
                        p.goaltending
                        if p.position in GOALIE_POSITIONS
                        else (p.shooting * 0.36 + p.playmaking * 0.30 + p.defense * 0.24 + p.physical * 0.10),
                        2,
                    ),
                }
            )

        return {
            "team": team.name,
            "active_count": len([p for p in team.roster if not p.is_injured]),
            "max_active": Team.MAX_ROSTER_SIZE,
            "projected_next_day_active": self._projected_active_count_next_day(team.name),
            "injuries": injuries,
            "returning_tomorrow": returning_tomorrow,
            "roster": roster_rows,
            "minors": minor_rows,
        }

    def callup_promote(self, team_name: str | None, player_name: str) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        if chosen != self.user_team_name:
            raise HTTPException(status_code=403, detail="Can only manage call ups for your team")
        team = self.simulator.get_team(chosen)
        if team is not None and len([p for p in team.roster if not p.is_injured]) >= Team.MAX_ROSTER_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Active roster is full ({Team.MAX_ROSTER_SIZE}/{Team.MAX_ROSTER_SIZE}). Send a player down first.",
            )
        replacement_for = ""
        if team is not None:
            injured_pool = [p for p in team.roster if p.is_injured]
            if injured_pool:
                injured_pool.sort(key=lambda p: (-p.injured_games_remaining, p.name))
                replacement_for = injured_pool[0].name
        ok = self.simulator.promote_minor_player(chosen, player_name, replacement_for=replacement_for)
        if not ok:
            team = self.simulator.get_team(chosen)
            active_count = len([p for p in team.roster if not p.is_injured]) if team is not None else 0
            raise HTTPException(
                status_code=400,
                detail=f"Unable to call up player. Active roster is {active_count}/{Team.MAX_ROSTER_SIZE}; send someone down first if needed.",
            )
        self._add_news(
            kind="transaction",
            headline=f"Transaction: {chosen} recalled {player_name}",
            details=(
                f"{player_name} was called up from the minor league club."
                + (f" Temporary replacement for {replacement_for}." if replacement_for else "")
            ),
            team=chosen,
            day=self.simulator.current_day,
        )
        self._save_runtime_state()
        return {"ok": True, "team": chosen, "player": player_name}

    def callup_demote(self, team_name: str | None, player_name: str) -> dict[str, Any]:
        chosen = (team_name or self.user_team_name).strip()
        if not chosen:
            raise HTTPException(status_code=400, detail="No team selected")
        if chosen != self.user_team_name:
            raise HTTPException(status_code=403, detail="Can only manage call ups for your team")
        ok = self.simulator.demote_roster_player(chosen, player_name)
        if not ok:
            raise HTTPException(status_code=400, detail="Unable to send player down")
        self._add_news(
            kind="transaction",
            headline=f"Transaction: {chosen} assigned {player_name}",
            details=f"{player_name} was sent down to the minor league club.",
            team=chosen,
            day=self.simulator.current_day,
        )
        self._save_runtime_state()
        return {"ok": True, "team": chosen, "player": player_name}

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
        champion = self._season_champion(season) == team_name
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

    def _career_player_totals(self) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}

        for entry in self.simulator.hall_of_fame:
            if not isinstance(entry, dict):
                continue
            player_id = str(entry.get("player_id", "")).strip()
            if not player_id:
                continue
            row = rows.setdefault(
                player_id,
                {
                    "player_id": player_id,
                    "name": str(entry.get("name", "")).strip(),
                    "team": str(entry.get("team_at_retirement", "")).strip(),
                    "position": str(entry.get("position", "")).strip(),
                    "status": "Retired",
                    "gp": 0,
                    "g": 0,
                    "a": 0,
                    "p": 0,
                    "pim": 0,
                    "goalie_w": 0,
                    "goalie_so": 0,
                },
            )
            row["name"] = str(entry.get("name", row["name"])).strip()
            row["team"] = str(entry.get("team_at_retirement", row["team"])).strip()
            row["position"] = str(entry.get("position", row["position"])).strip()
            row["gp"] = max(int(row["gp"]), int(entry.get("career_gp", 0)))
            row["g"] = max(int(row["g"]), int(entry.get("career_g", 0)))
            row["a"] = max(int(row["a"]), int(entry.get("career_a", 0)))
            row["p"] = max(int(row["p"]), int(entry.get("career_p", 0)))
            row["goalie_w"] = max(int(row["goalie_w"]), int(entry.get("goalie_w", 0)))
            row["goalie_so"] = max(int(row["goalie_so"]), int(entry.get("goalie_so", 0)))

        for team in self.simulator.teams:
            for player in [*team.roster, *team.minor_roster]:
                pid = str(player.player_id)
                season_rows = [s for s in player.career_seasons if isinstance(s, dict)]
                gp = sum(int(s.get("gp", 0)) for s in season_rows) + int(player.games_played)
                goals = sum(int(s.get("g", 0)) for s in season_rows) + int(player.goals)
                assists = sum(int(s.get("a", 0)) for s in season_rows) + int(player.assists)
                points = sum(int(s.get("p", 0)) for s in season_rows) + int(player.points)
                pim = sum(int(s.get("pim", 0)) for s in season_rows)
                goalie_w = sum(int(s.get("goalie_w", 0)) for s in season_rows) + int(player.goalie_wins)
                goalie_so = sum(int(s.get("goalie_so", 0)) for s in season_rows) + int(player.goalie_shutouts)

                row = rows.setdefault(
                    pid,
                    {
                        "player_id": pid,
                        "name": player.name,
                        "team": team.name,
                        "position": player.position,
                        "status": "Active",
                        "gp": 0,
                        "g": 0,
                        "a": 0,
                        "p": 0,
                        "pim": 0,
                        "goalie_w": 0,
                        "goalie_so": 0,
                    },
                )
                row["name"] = player.name
                row["team"] = team.name
                row["position"] = player.position
                row["status"] = "Active"
                row["gp"] = max(int(row["gp"]), gp)
                row["g"] = max(int(row["g"]), goals)
                row["a"] = max(int(row["a"]), assists)
                row["p"] = max(int(row["p"]), points)
                row["pim"] = max(int(row["pim"]), pim)
                row["goalie_w"] = max(int(row["goalie_w"]), goalie_w)
                row["goalie_so"] = max(int(row["goalie_so"]), goalie_so)

        return list(rows.values())

    def records(self, team_name: str | None = None) -> dict[str, Any]:
        selected_team = (team_name or self.user_team_name).strip()
        all_rows = self._career_player_totals()

        categories = [
            ("career_goals", "Career Goals", "g"),
            ("career_assists", "Career Assists", "a"),
            ("career_points", "Career Points", "p"),
            ("career_gp", "Career Games", "gp"),
            ("career_pim", "Career PIM", "pim"),
            ("career_goalie_wins", "Career Goalie Wins", "goalie_w"),
            ("career_shutouts", "Career Shutouts", "goalie_so"),
        ]

        def _top(rows: list[dict[str, Any]], stat_key: str, limit: int = 10) -> list[dict[str, Any]]:
            ranked = [r for r in rows if int(r.get(stat_key, 0)) > 0]
            ranked.sort(
                key=lambda r: (
                    int(r.get(stat_key, 0)),
                    str(r.get("name", "")),
                ),
                reverse=True,
            )
            return [
                {
                    "name": str(r.get("name", "")),
                    "team": str(r.get("team", "")),
                    "position": str(r.get("position", "")),
                    "status": str(r.get("status", "")),
                    "value": int(r.get(stat_key, 0)),
                }
                for r in ranked[:limit]
            ]

        league_tables = [
            {
                "key": key,
                "label": label,
                "rows": _top(all_rows, stat),
            }
            for key, label, stat in categories
        ]

        franchise_rows = [r for r in all_rows if str(r.get("team", "")) == selected_team] if selected_team else []
        franchise_tables = [
            {
                "key": key,
                "label": label,
                "rows": _top(franchise_rows, stat),
            }
            for key, label, stat in categories
        ]

        return {
            "team": selected_team,
            "league": league_tables,
            "franchise": franchise_tables,
        }

    def banners(self, team_name: str | None = None) -> dict[str, Any]:
        selected_team = (team_name or self.user_team_name).strip()
        if not selected_team:
            raise HTTPException(status_code=400, detail="No team selected")
        team = self.simulator.get_team(selected_team)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")

        def _rank_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
            return (
                int(row.get("points", 0)),
                int(row.get("wins", 0)),
                int(row.get("gd", 0)),
                str(row.get("team", "")),
            )

        banners: list[dict[str, Any]] = []
        seen: set[tuple[int, str, str]] = set()
        for season in self.simulator.season_history:
            if not isinstance(season, dict):
                continue
            season_no = int(season.get("season", 0))
            standings = season.get("standings", [])
            if not isinstance(standings, list):
                continue
            rows = [r for r in standings if isinstance(r, dict)]
            team_row = next((r for r in rows if str(r.get("team", "")) == selected_team), None)
            if team_row is None:
                continue

            def _add_banner(kind: str, title: str) -> None:
                key = (season_no, kind, title)
                if key in seen:
                    return
                seen.add(key)
                banners.append(
                    {
                        "season": season_no,
                        "kind": kind,
                        "title": title,
                        "team": selected_team,
                    }
                )

            if self._season_champion(season) == selected_team:
                _add_banner("cup", "Founders Cup Champions")

            sorted_league = sorted(rows, key=_rank_key, reverse=True)
            if sorted_league and str(sorted_league[0].get("team", "")) == selected_team:
                _add_banner("league_best", "Best Record In League")

            team_division = str(team_row.get("division", ""))
            division_rows = [r for r in rows if str(r.get("division", "")) == team_division]
            sorted_division = sorted(division_rows, key=_rank_key, reverse=True)
            if sorted_division and str(sorted_division[0].get("team", "")) == selected_team:
                _add_banner("division", f"{team_division} Division Champions")

            playoffs = season.get("playoffs", {})
            if isinstance(playoffs, dict):
                rounds = playoffs.get("rounds", [])
                if isinstance(rounds, list):
                    for round_row in rounds:
                        if not isinstance(round_row, dict):
                            continue
                        round_name = str(round_row.get("name", "")).strip()
                        if "Conference Final" not in round_name:
                            continue
                        series_rows = round_row.get("series", [])
                        if not isinstance(series_rows, list):
                            continue
                        for series in series_rows:
                            if not isinstance(series, dict):
                                continue
                            if str(series.get("winner", "")) != selected_team:
                                continue
                            conference_label = round_name.replace(" Final", "").strip()
                            _add_banner("conference", f"{conference_label} Champions")
                            break

        retired_numbers = getattr(team, "retired_numbers", [])
        if isinstance(retired_numbers, list):
            for row in retired_numbers:
                if not isinstance(row, dict):
                    continue
                number = row.get("number")
                player = str(row.get("player", "")).strip()
                if number is None:
                    continue
                try:
                    jersey_no = int(number)
                except (TypeError, ValueError):
                    continue
                season_no = int(row.get("season", 0))
                title = f"Number {jersey_no} Retired"
                key = (season_no, "retired_number", title)
                if key in seen:
                    continue
                seen.add(key)
                banners.append(
                    {
                        "season": season_no,
                        "kind": "retired_number",
                        "title": title,
                        "team": selected_team,
                        "number": jersey_no,
                        "player": player,
                    }
                )

        banners.sort(key=lambda r: int(r.get("season", 0)), reverse=True)
        return {
            "team": selected_team,
            "logo_url": f"/api/team-logo/{self._team_slug(selected_team)}",
            "primary_color": getattr(team, "primary_color", "#1f3a93"),
            "secondary_color": getattr(team, "secondary_color", "#d7e1f5"),
            "banners": banners,
        }

    def cup_history(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for season in sorted(
            [s for s in self.simulator.season_history if isinstance(s, dict)],
            key=lambda s: int(s.get("season", 0)),
            reverse=True,
        ):
            season_no = int(season.get("season", 0))
            winner = self._season_champion(season)
            playoffs = season.get("playoffs", {})
            runner_up = ""
            cup_series = "-"
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
                            try:
                                ww = int(s0.get("winner_wins", 0) or 0)
                                lw = int(s0.get("loser_wins", 0) or 0)
                                if ww > 0:
                                    cup_series = f"{ww}-{lw}"
                            except (TypeError, ValueError):
                                cup_series = "-"
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
                    "series": cup_series,
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
                    "cup_winner": "Y" if self._season_champion(season) == team_name else "",
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
                    "champion": "Y" if self._season_champion(season) == team_name else "",
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

        self._returning_soon_inbox(day_num=self.simulator.current_day)

        # Legacy cleanup: roster-limit inbox flow was replaced by direct sim-time validation.
        pre_len = len(self.inbox_events)
        self.inbox_events = [
            ev
            for ev in self.inbox_events
            if str(ev.get("type", "")) != "roster_limit"
        ]
        if len(self.inbox_events) != pre_len:
            self._save_runtime_state()

        projected_active = self._projected_active_count_next_day(self.user_team_name)
        if projected_active > Team.MAX_ROSTER_SIZE:
            now_active = self._active_roster_count(self.user_team_name)
            returns = projected_active - now_active
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Roster non-compliant for next game day: projected active roster is "
                    f"{projected_active}/{Team.MAX_ROSTER_SIZE} (about {returns} player(s) returning from IR). "
                    "Use Call Ups to send player(s) down before simming."
                ),
            )

        if not self.simulator.is_complete():
            day_num = self.simulator.current_day
            self._expire_inbox_events(day_num=day_num)
            user_team_before = self._user_team()
            injury_before = {
                p.name: int(p.injured_games_remaining)
                for p in [*(user_team_before.roster if user_team_before is not None else []), *(user_team_before.minor_roster if user_team_before is not None else [])]
            }
            roster_before = self._capture_roster_state()
            results = self.simulator.simulate_next_day(
                user_team_name=self.user_team_name,
                user_strategy=self.user_strategy,
                use_user_lines=self.override_coach_for_lines,
                use_user_strategy=self.override_coach_for_strategy,
            )
            user_team_after = self._user_team()
            returned_players: list[str] = []
            if user_team_after is not None:
                after_pool = [*user_team_after.roster, *user_team_after.minor_roster]
                for p in after_pool:
                    prev_left = int(injury_before.get(p.name, 0))
                    if prev_left > 0 and int(p.injured_games_remaining) <= 0:
                        returned_players.append(p.name)
            self._injury_news_from_results(day_num=day_num, results=results)
            self._injury_inbox_from_results(day_num=day_num, results=results)
            self._log_auto_roster_transactions(before=roster_before, day_num=day_num)
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
            if day_num % 7 == 0:
                self._generate_weekly_inbox(day_num=day_num)
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
        retired_numbers = offseason.get("retired_numbers", [])
        if isinstance(retired_numbers, list):
            self._retired_number_news_from_offseason(completed_season=completed, retired_numbers=retired_numbers)
        free_agency = offseason.get("free_agency", {})
        if isinstance(free_agency, dict):
            self._free_agency_news_from_offseason(completed_season=completed, free_agency=free_agency)
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
        temp = LeagueSimulator(
            teams=build_default_teams(),
            games_per_matchup=2,
            history_path=str(self.data_root / "season_history.json"),
            career_history_path=str(self.data_root / "career_history.json"),
            hall_of_fame_path=str(self.data_root / "hall_of_fame.json"),
            state_path=str(self.data_root / "league_state.json"),
        )
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


@app.get("/api/inbox")
def inbox(resolved: bool = False, limit: int = 60) -> list[dict[str, Any]]:
    with service._lock:
        return service.inbox(include_resolved=resolved, limit=limit)


@app.post("/api/inbox/resolve")
def resolve_inbox(payload: InboxResolveSelection) -> dict[str, Any]:
    with service._lock:
        return service.resolve_inbox(event_id=payload.event_id, choice_id=payload.choice_id)


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


@app.get("/api/callups")
def callups(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.callups(team_name=team)


@app.post("/api/callups/promote")
def callups_promote(payload: CallupSelection) -> dict[str, Any]:
    with service._lock:
        return service.callup_promote(team_name=payload.team_name, player_name=payload.player_name)


@app.post("/api/callups/demote")
def callups_demote(payload: CallupSelection) -> dict[str, Any]:
    with service._lock:
        return service.callup_demote(team_name=payload.team_name, player_name=payload.player_name)


@app.get("/api/roster")
def roster(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.roster(team_name=team)


@app.get("/api/contracts")
def contracts(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.contracts(team_name=team)


@app.get("/api/free-agents")
def free_agents(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.free_agents(team_name=team)


@app.post("/api/free-agents/sign")
def sign_free_agent(payload: FreeAgentSignSelection) -> dict[str, Any]:
    with service._lock:
        return service.sign_free_agent(
            team_name=payload.team_name,
            player_name=payload.player_name,
            years=payload.years,
            cap_hit=payload.cap_hit,
        )


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


@app.get("/api/records")
def records(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.records(team_name=team)


@app.get("/api/banners")
def banners(team: str | None = None) -> dict[str, Any]:
    with service._lock:
        return service.banners(team_name=team)


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


@app.get("/api/transactions")
def transactions(team: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with service._lock:
        return service.transactions(team_name=team, limit=limit)
