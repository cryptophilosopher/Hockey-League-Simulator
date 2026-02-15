from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

try:
    from PIL import Image, ImageFilter, ImageOps, ImageTk
except ImportError:
    Image = None
    ImageFilter = None
    ImageOps = None
    ImageTk = None

from .app import build_default_teams
from .league import LeagueSimulator
from .models import Player, Team


class HockeySimGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Hockey League Simulator")
        self.root.geometry("1720x980")
        self.root.minsize(1500, 900)

        self.simulator: LeagueSimulator | None = None
        self.user_team_name: str | None = None
        self.player_row_to_name: dict[str, str] = {}
        self.player_row_to_team: dict[str, str] = {}
        self.goalie_row_to_name: dict[str, str] = {}
        self.goalie_row_to_team: dict[str, str] = {}
        self.players: ttk.Treeview | None = None
        self.goalies: ttk.Treeview | None = None
        self.standings_views: dict[str, ttk.Treeview] = {}
        self.standings_view_scope: dict[str, tuple[str, str | None]] = {}
        self.standings_section_frames: dict[str, ttk.Frame] = {}
        self.standings_row_to_team: dict[str, dict[str, str]] = {}
        self.team_logo_images: dict[tuple[str, int], tk.PhotoImage | None] = {}
        self.main_team_logo_label: ttk.Label | None = None
        self.main_coach_label: ttk.Label | None = None
        self._stats_scope = "team"
        self.player_popup: tk.Toplevel | None = None
        self.player_popup_summary: ttk.Treeview | None = None
        self.player_popup_career: ttk.Treeview | None = None
        self.player_popup_player: Player | None = None
        self.player_popup_career_map: dict[str, dict[str, object]] = {}
        self.user_stats_popup: tk.Toplevel | None = None
        self.user_stats_players: ttk.Treeview | None = None
        self.user_stats_goalies: ttk.Treeview | None = None
        self.user_stats_team_label: ttk.Label | None = None
        self.user_stats_goalie_row_to_name: dict[str, str] = {}
        self.user_stats_goalie_row_to_team: dict[str, str] = {}
        self.user_stats_scope: str = "team"
        self.user_stats_row_to_name: dict[str, str] = {}
        self.user_stats_row_to_team: dict[str, str] = {}
        self.hof_popup: tk.Toplevel | None = None
        self.hof_tree: ttk.Treeview | None = None
        self.history_tree: ttk.Treeview | None = None
        self.hof_title_label: ttk.Label | None = None
        self.hof_points_tree: ttk.Treeview | None = None
        self.hof_goals_tree: ttk.Treeview | None = None
        self.hof_assists_tree: ttk.Treeview | None = None
        self.hof_goalie_wins_tree: ttk.Treeview | None = None
        self.hof_coach_tree: ttk.Treeview | None = None
        self.hof_retired_section: ttk.Frame | None = None
        self.hof_history_section: ttk.Frame | None = None
        self.champion_popup: tk.Toplevel | None = None
        self.bracket_popup: tk.Toplevel | None = None
        self.results_context_label: ttk.Label | None = None

        self._configure_styles()
        self._build_layout()
        self.start_season()

    def _configure_styles(self) -> None:
        self.palette = {
            "bg": "#eef2f7",
            "card": "#ffffff",
            "text": "#13233a",
            "muted": "#4b617d",
            "accent": "#0f4c81",
            "accent_hover": "#135d9b",
            "border": "#ccd7e6",
            "stripe_a": "#ffffff",
            "stripe_b": "#f6f9fd",
            "result_bg": "#f8fbff",
            "result_border": "#d6e2f0",
        }
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg=self.palette["bg"])
        style.configure(".", background=self.palette["bg"], foreground=self.palette["text"], font=("Segoe UI", 10))
        style.configure("Card.TFrame", background=self.palette["card"], borderwidth=1, relief="solid")
        style.configure("TLabel", background=self.palette["bg"], foreground=self.palette["text"])
        style.configure("Muted.TLabel", background=self.palette["bg"], foreground=self.palette["muted"])
        style.configure("CardTitle.TLabel", background=self.palette["card"], foreground=self.palette["text"], font=("Segoe UI Semibold", 10))
        style.configure("AppTitle.TLabel", background=self.palette["bg"], foreground=self.palette["accent"], font=("Cambria", 13, "bold"))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(10, 5), borderwidth=0)
        style.map("TButton", background=[("active", self.palette["accent_hover"]), ("!disabled", self.palette["accent"])], foreground=[("!disabled", "#ffffff")])
        style.configure("TCombobox", fieldbackground="#ffffff", bordercolor=self.palette["border"], lightcolor=self.palette["border"], darkcolor=self.palette["border"])
        style.configure(
            "Treeview",
            background=self.palette["stripe_a"],
            fieldbackground=self.palette["stripe_a"],
            foreground=self.palette["text"],
            rowheight=22,
            bordercolor=self.palette["border"],
            lightcolor=self.palette["border"],
            darkcolor=self.palette["border"],
        )
        style.map("Treeview", background=[("selected", "#c9def7")], foreground=[("selected", self.palette["text"])])
        style.configure("Treeview.Heading", background="#dfe9f6", foreground=self.palette["text"], font=("Segoe UI Semibold", 10))
        style.configure("TNotebook", background=self.palette["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI Semibold", 10), padding=(14, 6), background="#d8e4f3", foreground=self.palette["text"])
        style.map("TNotebook.Tab", background=[("selected", "#ffffff"), ("active", "#e8f0fa")])

    def _table_row_tag(self, row_idx: int) -> str:
        return "row_even" if row_idx % 2 == 0 else "row_odd"

    def _apply_table_row_styles(self, tree: ttk.Treeview) -> None:
        tree.tag_configure("row_even", background=self.palette["stripe_a"])
        tree.tag_configure("row_odd", background=self.palette["stripe_b"])

    def _set_hof_view(self, view: str) -> None:
        if self.hof_retired_section is None or self.hof_history_section is None:
            return
        self.hof_retired_section.pack_forget()
        self.hof_history_section.pack_forget()
        if view == "history":
            self.hof_history_section.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        else:
            self.hof_retired_section.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def _build_layout(self) -> None:
        controls = ttk.Frame(self.root, padding=10)
        controls.pack(fill=tk.X)

        top_row = ttk.Frame(controls)
        top_row.pack(fill=tk.X)
        bottom_row = ttk.Frame(controls)
        bottom_row.pack(fill=tk.X, pady=(8, 0))

        header_badge = ttk.Frame(top_row)
        header_badge.pack(side=tk.LEFT, anchor=tk.W, padx=(0, 14))
        self.main_team_logo_label = ttk.Label(header_badge, text="", style="CardTitle.TLabel")
        self.main_team_logo_label.pack(side=tk.LEFT)

        ttk.Label(top_row, text="Your Team:").pack(side=tk.LEFT)
        self.team_var = tk.StringVar()
        self.team_combo = ttk.Combobox(top_row, textvariable=self.team_var, state="readonly", width=22)
        self.team_combo.pack(side=tk.LEFT, padx=(6, 14))
        self.team_combo.bind("<<ComboboxSelected>>", self.on_team_change)
        self.main_coach_label = ttk.Label(top_row, text="Coach: -", style="Muted.TLabel")
        self.main_coach_label.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(top_row, text="Strategy:").pack(side=tk.LEFT)
        self.strategy_var = tk.StringVar(value="balanced")
        self.strategy_combo = ttk.Combobox(
            top_row,
            textvariable=self.strategy_var,
            state="readonly",
            values=["aggressive", "balanced", "defensive"],
            width=12,
        )
        self.strategy_combo.pack(side=tk.LEFT, padx=(6, 14))

        ttk.Label(top_row, text="Starting Goalie:").pack(side=tk.LEFT)
        self.goalie_var = tk.StringVar()
        self.goalie_combo = ttk.Combobox(top_row, textvariable=self.goalie_var, state="readonly", width=20)
        self.goalie_combo.pack(side=tk.LEFT, padx=(6, 14))
        self.goalie_combo.bind("<<ComboboxSelected>>", self.on_goalie_change)
        self.use_coach_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top_row, text="Use Coach Decisions", variable=self.use_coach_var, command=self.on_coach_mode_toggle).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Button(bottom_row, text="Sim Next Day", command=self.sim_next_day).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom_row, text="My Team Stats", command=lambda: self.open_user_stats_window("team")).pack(side=tk.LEFT)
        ttk.Button(bottom_row, text="League Leaders", command=lambda: self.open_user_stats_window("league")).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom_row, text="Franchise", command=self.show_hall_of_fame).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom_row, text="Season History", command=self.show_season_history).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom_row, text="Playoff Bracket", command=self.show_playoff_bracket).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom_row, text="Fire Coach", command=self.fire_selected_coach).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom_row, text="Reset Stats", command=self.reset_stats).pack(side=tk.LEFT, padx=6)

        self.day_label = ttk.Label(bottom_row, text="Day: -")
        self.season_label = ttk.Label(bottom_row, text="Season: -")

        mid = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = ttk.Frame(mid, style="Card.TFrame", padding=10)
        right = ttk.Frame(mid, style="Card.TFrame", padding=10)
        mid.add(left, weight=1)
        mid.add(right, weight=3)

        ttk.Label(left, text="Day Results", style="CardTitle.TLabel").pack(anchor=tk.W)
        results_controls = ttk.Frame(left)
        results_controls.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(results_controls, text="Show:", style="Muted.TLabel").pack(side=tk.LEFT)
        self.results_filter_var = tk.StringVar(value="My Team Events")
        self.results_filter_combo = ttk.Combobox(
            results_controls,
            textvariable=self.results_filter_var,
            state="readonly",
            values=["All League Events", "My Team Events"],
            width=18,
        )
        self.results_filter_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.results_context_label = ttk.Label(results_controls, text="Season - Day -", style="Muted.TLabel")
        self.results_context_label.pack(side=tk.RIGHT)
        self.results_text = tk.Text(left, height=20, wrap="word")
        self.results_text.configure(
            bg=self.palette["result_bg"],
            fg=self.palette["text"],
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=self.palette["result_border"],
            highlightcolor=self.palette["result_border"],
            font=("Consolas", 10),
            padx=8,
            pady=8,
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)

        standings_frame = ttk.Frame(right)
        standings_frame.pack(fill=tk.X)
        standings_header = ttk.Frame(standings_frame)
        standings_header.pack(fill=tk.X)
        ttk.Label(standings_header, text="Standings", style="CardTitle.TLabel").pack(side=tk.LEFT, anchor=tk.W)
        ttk.Label(standings_header, text="View:", style="Muted.TLabel").pack(side=tk.RIGHT, padx=(0, 6))
        self.standings_mode_var = tk.StringVar(value="Division")
        self.standings_mode_combo = ttk.Combobox(
            standings_header,
            textvariable=self.standings_mode_var,
            state="readonly",
            values=["League", "Conference", "Division", "Wild Card"],
            width=12,
        )
        self.standings_mode_combo.pack(side=tk.RIGHT)
        self.standings_mode_combo.bind("<<ComboboxSelected>>", self.on_standings_mode_change)
        self.standings_sections_container = ttk.Frame(standings_frame)
        self.standings_sections_container.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(right, text="Player and goalie stats are available in pop-up windows.", style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 0))

        self._set_results("Season loaded. Click 'Sim Next Day' to begin.")

    def _create_standings_view(self, parent: tk.Widget, height: int = 9) -> ttk.Treeview:
        tree = ttk.Treeview(
            parent,
            columns=("Team", "GP", "W", "L", "OTL", "PTS", "HOME", "AWAY", "GF", "DA", "DIFF", "L10", "STRK"),
            show="tree headings",
            height=height,
        )
        tree.heading("#0", text="")
        tree.column("#0", width=42, minwidth=42, anchor=tk.CENTER, stretch=False)
        for col, w in [
            ("Team", 180),
            ("GP", 45),
            ("W", 40),
            ("L", 40),
            ("OTL", 50),
            ("PTS", 50),
            ("HOME", 85),
            ("AWAY", 85),
            ("GF", 45),
            ("DA", 45),
            ("DIFF", 60),
            ("L10", 70),
            ("STRK", 60),
        ]:
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor=tk.CENTER)
        tree.tag_configure("group_header", background="#e8eef7", foreground=self.palette["accent"], font=("Segoe UI Semibold", 10))
        tree.tag_configure("group_cutline", background="#f3f6fb", foreground=self.palette["muted"], font=("Segoe UI Semibold", 9))
        self._apply_table_row_styles(tree)
        tree.bind("<<TreeviewSelect>>", self.on_standings_team_select)
        tree.pack(fill=tk.X)
        return tree

    def _team_tag(self, team_name: str) -> str:
        return f"team_{team_name.lower().replace(' ', '_')}"

    def _team_logo_image(self, team_name: str, target_px: int = 20) -> tk.PhotoImage | None:
        cache_key = (team_name, target_px)
        if cache_key in self.team_logo_images:
            return self.team_logo_images[cache_key]

        base_assets = Path(__file__).resolve().parents[2] / "assets"
        stem = team_name.lower().replace(" ", "_")
        candidate_paths = [
            base_assets / "team_logos" / f"{stem}.png",
            base_assets / f"{stem}.png",
            base_assets / "team_logos" / f"{stem}.jpg",
            base_assets / f"{stem}.jpg",
            base_assets / "team_logos" / f"{stem}.jpeg",
            base_assets / f"{stem}.jpeg",
        ]
        logo_path = next((p for p in candidate_paths if p.exists()), None)
        if logo_path is None:
            self.team_logo_images[cache_key] = None
            return None

        if Image is not None and ImageTk is not None:
            try:
                with Image.open(logo_path) as src:
                    image = src.convert("RGBA")
                    # Keep aspect ratio and center on transparent square canvas.
                    fit = ImageOps.contain(image, (target_px, target_px), method=Image.Resampling.LANCZOS)
                    canvas = Image.new("RGBA", (target_px, target_px), (0, 0, 0, 0))
                    x = (target_px - fit.width) // 2
                    y = (target_px - fit.height) // 2
                    canvas.alpha_composite(fit, (x, y))
                    if ImageFilter is not None and target_px >= 28:
                        canvas = canvas.filter(ImageFilter.UnsharpMask(radius=1.4, percent=120, threshold=2))
                    tk_image = ImageTk.PhotoImage(canvas)
                    self.team_logo_images[cache_key] = tk_image
                    return tk_image
            except Exception:
                pass

        # Fallback if Pillow is unavailable or failed.
        try:
            image = tk.PhotoImage(file=str(logo_path))
        except tk.TclError:
            self.team_logo_images[cache_key] = None
            return None
        width = max(1, image.width())
        height = max(1, image.height())
        shrink = max((width + target_px - 1) // target_px, (height + target_px - 1) // target_px, 1)
        if shrink > 1:
            image = image.subsample(shrink, shrink)
        self.team_logo_images[cache_key] = image
        return image

    def _team_display_name(self, team: Team) -> str:
        return team.name

    def _player_lookup(self, team_name: str, player_name: str) -> Player | None:
        if self.simulator is None:
            return None
        team = self.simulator.get_team(team_name)
        if team is None:
            return None
        for player in team.roster:
            if player.name == player_name:
                return player
        return None

    def _open_player_popup(self, player_name: str | None, team_name: str | None) -> None:
        if not player_name or not team_name:
            return
        player = self._player_lookup(team_name, player_name)
        if player is None:
            return
        self._show_player_popup(player)

    def _build_standings_tabs(self) -> None:
        for child in self.standings_sections_container.winfo_children():
            child.destroy()
        self.standings_views.clear()
        self.standings_view_scope.clear()
        self.standings_section_frames.clear()
        if self.simulator is None:
            return

        mode = self.standings_mode_var.get()
        if mode == "Conference":
            for conference in self.simulator.get_conferences():
                section = ttk.Frame(self.standings_sections_container)
                section.pack(fill=tk.X, pady=(0, 6))
                ttk.Label(section, text=conference, style="CardTitle.TLabel").pack(anchor=tk.W)
                self.standings_views[conference] = self._create_standings_view(section, height=12)
                self.standings_view_scope[conference] = ("conference", conference)
                self.standings_section_frames[conference] = section
            return

        if mode == "Division":
            for division in self.simulator.get_divisions():
                section = ttk.Frame(self.standings_sections_container)
                section.pack(fill=tk.X, pady=(0, 6))
                ttk.Label(section, text=division, style="CardTitle.TLabel").pack(anchor=tk.W)
                self.standings_views[division] = self._create_standings_view(section, height=6)
                self.standings_view_scope[division] = ("division", division)
                self.standings_section_frames[division] = section
            return

        if mode == "Wild Card":
            for conference in self.simulator.get_conferences():
                section = ttk.Frame(self.standings_sections_container)
                section.pack(fill=tk.X, pady=(0, 6))
                ttk.Label(section, text=f"{conference} Wild Card", style="CardTitle.TLabel").pack(anchor=tk.W)
                self.standings_views[conference] = self._create_standings_view(section, height=14)
                self.standings_view_scope[conference] = ("wildcard", conference)
                self.standings_section_frames[conference] = section
            return

        section = ttk.Frame(self.standings_sections_container)
        section.pack(fill=tk.X)
        ttk.Label(section, text="League", style="CardTitle.TLabel").pack(anchor=tk.W)
        self.standings_views["League"] = self._create_standings_view(section, height=24)
        self.standings_view_scope["League"] = ("league", None)
        self.standings_section_frames["League"] = section

    def on_standings_mode_change(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self._build_standings_tabs()
        self.refresh_standings()

    def _set_results(self, text: str) -> None:
        self.results_text.configure(state=tk.NORMAL)
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert(tk.END, text.strip() + "\n")
        self.results_text.configure(state=tk.DISABLED)

    def _append_results(self, text: str) -> None:
        self.results_text.configure(state=tk.NORMAL)
        self.results_text.insert(tk.END, text + "\n")
        self.results_text.see(tk.END)
        self.results_text.configure(state=tk.DISABLED)

    def _append_game_result_colored(self, away_name: str, away_goals: int, home_goals: int, home_name: str, overtime: bool) -> None:
        if self.simulator is None:
            self._append_results(f"{away_name} {away_goals} - {home_goals} {home_name}")
            return
        away_team = self.simulator.get_team(away_name)
        home_team = self.simulator.get_team(home_name)
        suffix = " (OT)" if overtime else ""
        away_tag = self._team_tag(away_name)
        home_tag = self._team_tag(home_name)
        away_score_tag = f"{away_tag}_score"
        home_score_tag = f"{home_tag}_score"

        self.results_text.configure(state=tk.NORMAL)
        if away_team is not None:
            self.results_text.tag_configure(away_tag, foreground=away_team.primary_color)
            self.results_text.tag_configure(away_score_tag, foreground=away_team.primary_color)
        if home_team is not None:
            self.results_text.tag_configure(home_tag, foreground=home_team.primary_color)
            self.results_text.tag_configure(home_score_tag, foreground=home_team.primary_color)

        self.results_text.insert(tk.END, away_name, away_tag)
        self.results_text.insert(tk.END, " ")
        self.results_text.insert(tk.END, str(away_goals), away_score_tag)
        self.results_text.insert(tk.END, " - ")
        self.results_text.insert(tk.END, str(home_goals), home_score_tag)
        self.results_text.insert(tk.END, " ")
        self.results_text.insert(tk.END, home_name, home_tag)
        self.results_text.insert(tk.END, suffix + "\n")
        self.results_text.see(tk.END)
        self.results_text.configure(state=tk.DISABLED)

    def _game_three_stars(self, game) -> list[tuple[str, str]]:
        skater_lines: dict[str, dict[str, object]] = {}

        def add_goal_event_team(events: list, team_name: str) -> None:
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

        candidates: list[tuple[float, str, str]] = []
        for line in skater_lines.values():
            player = line["player"]
            goals = int(line["g"])
            assists = int(line["a"])
            points = goals + assists
            # NHL-style star weighting: point production first, goals slightly more valuable than assists.
            score = points * 52.0 + goals * 18.0 + assists * 8.0
            if points >= 3:
                score += 18.0
            if goals >= 2:
                score += 12.0
            summary = f"{player.name} ({line['team']}) {goals}G {assists}A"
            candidates.append((score, summary, "skater"))

        def goalie_star_score(saves: int, shots: int, goals_against: int, won: bool, overtime: bool) -> float:
            if shots <= 0:
                return 0.0
            sv = saves / shots
            score = saves * 2.0

            # Save percentage tiers similar to pro-game star narratives.
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

            # Workload matters: high-volume nights get extra credit.
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

            # Penalize high GA unless it came under very heavy volume.
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
            candidates.append(
                (
                    score,
                    f"{game.home_goalie.name} ({game.home.name}) {game.home_goalie_saves}/{game.home_goalie_shots} SV",
                    "goalie",
                )
            )
        if game.away_goalie is not None and game.away_goalie_shots > 0:
            score = goalie_star_score(
                saves=game.away_goalie_saves,
                shots=game.away_goalie_shots,
                goals_against=game.home_goals,
                won=game.away_goals > game.home_goals,
                overtime=game.overtime,
            )
            candidates.append(
                (
                    score,
                    f"{game.away_goalie.name} ({game.away.name}) {game.away_goalie_saves}/{game.away_goalie_shots} SV",
                    "goalie",
                )
            )

        candidates.sort(key=lambda row: row[0], reverse=True)
        out: list[tuple[str, str]] = []
        labels = ["1st Star", "2nd Star", "3rd Star"]
        for idx, (_, summary, _kind) in enumerate(candidates[:3]):
            out.append((labels[idx], summary))
        return out

    def _current_team(self) -> Team | None:
        if self.simulator is None:
            return None
        return self.simulator.get_team(self.team_var.get())

    def _display_injury(self, player: Player) -> tuple[str, int]:
        return ("Y" if player.is_injured else "N", player.injured_games_remaining)

    def _refresh_main_team_badge(self) -> None:
        if self.main_team_logo_label is None:
            return
        team = self._current_team()
        if team is None:
            self.main_team_logo_label.config(text="", image="")
            if self.main_coach_label is not None:
                self.main_coach_label.config(text="Coach: -")
            return
        logo_image = self._team_logo_image(team.name, target_px=104)
        badge_text = "" if logo_image else f"{team.logo}  {team.name}"
        self.main_team_logo_label.config(
            text=badge_text,
            image=(logo_image or ""),
            compound=tk.LEFT,
            foreground=team.primary_color,
        )
        if self.main_coach_label is not None:
            self.main_coach_label.config(
                text=f"Coach: {team.coach_name} ({team.coach_rating:.2f}, {team.coach_style})",
                foreground=team.primary_color,
            )

    def on_team_change(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self.user_team_name = self.team_var.get() or self.user_team_name
        self._refresh_main_team_badge()
        self.show_my_team_stats()
        self.show_my_goalie_stats()
        self.refresh_goalie_selector()
        self.refresh_user_stats_window()
        self._refresh_hof_window()

    def on_coach_mode_toggle(self) -> None:
        self.refresh_goalie_selector()

    def on_goalie_change(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        team = self._current_team()
        if team is None:
            return
        if self.use_coach_var.get():
            # Coach mode controls starter.
            team.set_starting_goalie(None)
            return
        if self.goalie_var.get() == "Auto Rotate":
            team.set_starting_goalie(None)
        else:
            team.set_starting_goalie(self.goalie_var.get())

    def start_season(self) -> None:
        teams = build_default_teams()
        self.team_logo_images.clear()
        self.simulator = LeagueSimulator(teams=teams, games_per_matchup=2)
        self.use_coach_var.set(True)
        self.team_combo["values"] = [t.name for t in teams]
        if not self.team_var.get():
            self.team_var.set(teams[0].name)
        self.user_team_name = self.team_var.get()
        self._refresh_main_team_badge()

        self._build_standings_tabs()
        self._refresh_season_day_labels()
        self._set_results(
            f"Season {self.simulator.season_number} started. You control {self.user_team_name}.\nPress 'Sim Next Day'."
        )
        self.refresh_standings()
        self.refresh_goalie_selector()
        self.refresh_user_stats_window()
        self._refresh_hof_window()
        if self._stats_scope == "league":
            self.show_league_stats()
            self.show_league_goalie_stats()
        else:
            self.show_my_team_stats()
            self.show_my_goalie_stats()

    def _refresh_season_day_labels(self) -> None:
        if self.simulator is None:
            return
        self.season_label.config(text=f"Season: {self.simulator.season_number}")
        self.day_label.config(text=f"Day: {self.simulator.current_day} / {self.simulator.total_days}")
        if self.results_context_label is not None:
            self.results_context_label.config(
                text=f"Season {self.simulator.season_number} Day {self.simulator.current_day}/{self.simulator.total_days}"
            )

    def refresh_goalie_selector(self) -> None:
        team = self._current_team()
        if team is None:
            self.goalie_combo["values"] = []
            self.goalie_var.set("")
            return
        goalies = [p.name for p in team.roster if p.position == "G" and not p.is_injured and team.is_dressed(p)]
        goalie_choices = ["Auto Rotate"] + goalies
        self.goalie_combo["values"] = goalie_choices
        current = team.starting_goalie_name
        if current in goalies:
            self.goalie_var.set(current)
        elif goalies:
            team.set_starting_goalie(None)
            self.goalie_var.set("Auto Rotate")
        else:
            team.set_starting_goalie(None)
            self.goalie_var.set("")
        if self.use_coach_var.get():
            team.set_starting_goalie(None)
            if goalies:
                self.goalie_var.set("Auto Rotate")

    def _handle_end_of_season(self) -> None:
        if self.simulator is None:
            return
        offseason = self.simulator.finalize_offseason_after_playoffs()
        if not offseason.get("advanced"):
            offseason = self.simulator.advance_to_next_season()
        if not offseason.get("advanced"):
            return

        retired = offseason.get("retired", [])
        drafted = offseason.get("drafted", {})
        drafted_details = offseason.get("drafted_details", {})
        self._append_results("")
        self._append_results(
            f"Season {offseason['completed_season']} complete. Champion: {offseason['champion']}."
        )
        playoffs = offseason.get("playoffs", {})
        cup_name = str(playoffs.get("cup_name", "Founders Cup")) if isinstance(playoffs, dict) else "Founders Cup"
        self._show_champion_popup(
            champion=str(offseason.get("champion", "")),
            season=int(offseason.get("completed_season", self.simulator.season_number)),
            cup_name=cup_name,
        )
        if isinstance(playoffs, dict) and playoffs:
            self._append_playoff_summary(playoffs)
        if retired:
            self._append_results(f"RETIREMENTS ({len(retired)}):")
        else:
            self._append_results("RETIREMENTS: none")
        if retired:
            for line in list(retired)[:10]:
                self._append_results(f"RETIREMENT: {line}")
        if drafted:
            self._append_results("DRAFT RESULTS:")
            if isinstance(drafted_details, dict) and drafted_details:
                for team_name, picks in drafted_details.items():
                    if not isinstance(picks, list) or not picks:
                        continue
                    formatted: list[str] = []
                    for pick in picks:
                        if not isinstance(pick, dict):
                            continue
                        name = str(pick.get("name", ""))
                        overall = pick.get("overall")
                        round_no = pick.get("round")
                        if overall is not None and round_no is not None:
                            formatted.append(f"{name} (R{round_no} #{overall})")
                        else:
                            formatted.append(name)
                    if formatted:
                        self._append_results(f"{team_name}: {', '.join(formatted)}")
            else:
                for team_name, picks in drafted.items():
                    if picks:
                        self._append_results(f"{team_name}: {', '.join(picks)}")
        your_picks = drafted.get(self.team_var.get(), []) if isinstance(drafted, dict) else []
        if your_picks:
            self._append_results(f"YOUR TEAM DRAFTED: {', '.join(your_picks)}")
        self._append_results(f"Starting Season {offseason['next_season']}.")
        if len(retired) > 10:
            self._append_results("Additional offseason moves saved to season history.")

        self._refresh_season_day_labels()
        self.refresh_standings()
        self.refresh_goalie_selector()
        self.refresh_user_stats_window()
        self._refresh_hof_window()
        if self._stats_scope == "league":
            self.show_league_stats()
            self.show_league_goalie_stats()
        else:
            self.show_my_team_stats()
            self.show_my_goalie_stats()

    def _on_champion_popup_close(self) -> None:
        if self.champion_popup is not None:
            self.champion_popup.destroy()
        self.champion_popup = None

    def _show_champion_popup(self, champion: str, season: int, cup_name: str) -> None:
        if self.champion_popup is not None and self.champion_popup.winfo_exists():
            self.champion_popup.destroy()
            self.champion_popup = None

        popup = tk.Toplevel(self.root)
        popup.title(f"{cup_name} Champions")
        popup.geometry("920x650")
        popup.minsize(820, 580)
        popup.configure(bg=self.palette["bg"])
        popup.transient(self.root)
        popup.protocol("WM_DELETE_WINDOW", self._on_champion_popup_close)

        frame = ttk.Frame(popup, padding=14, style="Card.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"{cup_name} Champions", style="AppTitle.TLabel").pack(anchor=tk.CENTER, pady=(2, 4))
        ttk.Label(frame, text=f"Season {season}", style="Muted.TLabel").pack(anchor=tk.CENTER, pady=(0, 8))

        canvas = tk.Canvas(
            frame,
            width=860,
            height=470,
            bg="#081a33",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#1e3e66",
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        champ_logo = self._team_logo_image(champion, target_px=136)

        for i in range(22):
            shade = 26 + i * 2
            color = f"#{shade:02x}{(shade + 14):02x}{(shade + 36):02x}"
            y0 = i * 22
            canvas.create_rectangle(0, y0, 900, y0 + 22, fill=color, outline=color)

        for i in range(12):
            x = 40 + i * 72
            height = 110 + (i % 3) * 22
            canvas.create_polygon(
                x,
                430,
                x + 24,
                430 - height,
                x + 48,
                430,
                fill="#153f73",
                outline="",
            )

        confetti_colors = ("#ffd166", "#ef476f", "#06d6a0", "#118ab2", "#f4a261", "#e9c46a")
        for i in range(40):
            x = 26 + ((i * 43) % 820)
            y = 26 + ((i * 67) % 190)
            color = confetti_colors[i % len(confetti_colors)]
            size = 5 + (i % 5)
            canvas.create_oval(x, y, x + size, y + size, fill=color, outline="")

        cup_x = 430
        canvas.create_polygon(
            cup_x - 95,
            172,
            cup_x + 95,
            172,
            cup_x + 62,
            284,
            cup_x - 62,
            284,
            fill="#f5d76e",
            outline="#d6a933",
            width=3,
        )
        canvas.create_arc(
            cup_x - 146,
            180,
            cup_x - 44,
            286,
            start=70,
            extent=225,
            style=tk.ARC,
            outline="#d6a933",
            width=10,
        )
        canvas.create_arc(
            cup_x + 44,
            180,
            cup_x + 146,
            286,
            start=-115,
            extent=225,
            style=tk.ARC,
            outline="#d6a933",
            width=10,
        )
        canvas.create_rectangle(cup_x - 16, 284, cup_x + 16, 330, fill="#e8c358", outline="#d6a933", width=2)
        canvas.create_rectangle(cup_x - 70, 330, cup_x + 70, 360, fill="#d4a939", outline="#b98d26", width=2)
        canvas.create_rectangle(cup_x - 116, 360, cup_x + 116, 392, fill="#b98d26", outline="#8f6c1f", width=2)
        canvas.create_oval(cup_x - 38, 185, cup_x + 38, 222, fill="#fff0a8", outline="")

        canvas.create_text(
            cup_x,
            94,
            text="LEAGUE CHAMPIONS",
            fill="#f5f8ff",
            font=("Segoe UI Semibold", 22),
        )
        canvas.create_oval(672, 36, 848, 212, fill="#0f2748", outline="#2f5d8e", width=3)
        if champ_logo is not None:
            canvas.create_image(760, 124, image=champ_logo)
        else:
            canvas.create_text(760, 124, text="TEAM", fill="#d8e9ff", font=("Segoe UI", 24, "bold"))
        canvas.create_text(
            cup_x,
            426,
            text=champion.upper(),
            fill="#fff7da",
            font=("Cambria", 30, "bold"),
        )

        ttk.Button(frame, text="Continue", command=self._on_champion_popup_close).pack(anchor=tk.CENTER, pady=(10, 0))

        self.champion_popup = popup
        self.champion_popup.deiconify()
        self.champion_popup.lift()
        self.champion_popup.focus_force()

    def _sim_next_playoff_day(self) -> None:
        if self.simulator is None:
            return
        if not self.simulator.has_playoff_session():
            started = self.simulator.start_playoffs()
            if not started.get("started"):
                return

        result = self.simulator.simulate_next_playoff_day()
        if not result.get("advanced"):
            return

        day = result.get("day", {})
        if not isinstance(day, dict):
            return
        round_name = str(day.get("round", "Playoffs"))
        game_number = int(day.get("game_number", 1))
        day_number = int(result.get("day_number", 1))
        total_days = int(result.get("total_days", 1))

        self._append_results("")
        self._append_results("-" * 62)
        self._append_results(
            f"SEASON {self.simulator.season_number}  PLAYOFF DAY {day_number}/{total_days}  {round_name} G{game_number}"
        )
        self._append_results("-" * 62)
        if self.results_context_label is not None:
            self.results_context_label.config(
                text=f"Season {self.simulator.season_number} Playoffs {day_number}/{total_days}"
            )

        games = day.get("games", [])
        show_all = self.results_filter_var.get() == "All League Events"
        if isinstance(games, list):
            for idx, game in enumerate(games, start=1):
                if not isinstance(game, dict):
                    continue
                home_name = str(game.get("home", ""))
                away_name = str(game.get("away", ""))
                is_user_game = self.user_team_name in {home_name, away_name}
                if not show_all and not is_user_game:
                    continue
                status = "FINAL/OT" if game.get("overtime") else "FINAL"
                series_high = str(game.get("series_higher_seed", ""))
                series_low = str(game.get("series_lower_seed", ""))
                series_game_no = int(game.get("game", game_number))
                if is_user_game:
                    self._append_results(f"Playoff Game {idx} [G{series_game_no} {status}] <<< YOUR TEAM >>>")
                else:
                    self._append_results(f"Playoff Game {idx} [G{series_game_no} {status}]")
                if series_high and series_low:
                    high_wins = int(game.get("series_high_wins", 0))
                    low_wins = int(game.get("series_low_wins", 0))
                    if high_wins == low_wins:
                        lead_text = f"Series tied {high_wins}-{low_wins}"
                    elif high_wins >= 4:
                        lead_text = f"{series_high} won the series {high_wins} to {low_wins}"
                    elif low_wins >= 4:
                        lead_text = f"{series_low} won the series {low_wins} to {high_wins}"
                    elif high_wins > low_wins:
                        lead_text = f"{series_high} leads {high_wins}-{low_wins}"
                    else:
                        lead_text = f"{series_low} leads {low_wins}-{high_wins}"
                    self._append_results(f"  Series: {series_high} vs {series_low} | {lead_text}")
                self._append_game_result_colored(
                    away_name=away_name,
                    away_goals=int(game.get("away_goals", 0)),
                    home_goals=int(game.get("home_goals", 0)),
                    home_name=home_name,
                    overtime=bool(game.get("overtime")),
                )

        if result.get("complete"):
            self._append_results("Playoffs complete. Click 'Sim Next Day' for offseason + next season.")

    def sim_next_day(self) -> None:
        if self.simulator is None:
            self.start_season()
            return

        self.user_team_name = self.team_var.get() or self.user_team_name

        if self.simulator.is_complete():
            if not self.simulator.has_playoff_session() or not self.simulator.playoffs_finished():
                self._sim_next_playoff_day()
                return
            self._handle_end_of_season()
            return

        strategy = self.strategy_var.get() or "balanced"
        user_team = self._current_team()
        coach_mode = self.use_coach_var.get()
        use_user_coach_for_game = coach_mode
        effective_strategy = strategy
        manual_goalie = self.goalie_var.get() or "Auto Rotate"
        if user_team is not None:
            if use_user_coach_for_game:
                effective_strategy = user_team.coach_style
                user_team.set_starting_goalie(None)
                manual_goalie = "Auto Rotate"
            else:
                if manual_goalie == "Auto Rotate":
                    user_team.set_starting_goalie(None)
                else:
                    user_team.set_starting_goalie(manual_goalie)

        day_num = self.simulator.current_day
        schedule = self.simulator.get_day_schedule()
        self._append_results("")
        self._append_results("-" * 62)
        self._append_results(f"SEASON {self.simulator.season_number}  DAY {day_num}/{self.simulator.total_days}")
        self._append_results("-" * 62)
        self._append_results(f"Today's schedule ({len(schedule)} games):")
        for home, away in schedule:
            marker = " <<< YOUR TEAM >>>" if self.user_team_name in {home.name, away.name} else ""
            self._append_results(f"  {away.name} @ {home.name}{marker}")

        your_matchup = next(
            ((h, a) for h, a in schedule if h.name == self.user_team_name or a.name == self.user_team_name),
            None,
        )
        if your_matchup is not None:
            your_team = your_matchup[0] if your_matchup[0].name == self.user_team_name else your_matchup[1]
            starter = your_team.starting_goalie_name or "Auto Rotate"
            mode = "Coach" if use_user_coach_for_game else "Manual"
            self._append_results(
                f"Your game: {your_matchup[1].name} @ {your_matchup[0].name} | "
                f"Mode={mode} | Strategy={effective_strategy} | Coach={your_team.coach_name} ({your_team.coach_rating:.2f}) | Goalie={starter}"
            )

        results = self.simulator.simulate_next_day(
            user_team_name=self.user_team_name,
            user_strategy=effective_strategy,
            use_user_coach=use_user_coach_for_game,
        )
        standings_map = {rec.team.name: rec for rec in self.simulator.get_standings()}

        def _record_line(team_name: str) -> str:
            rec = standings_map.get(team_name)
            if rec is None:
                return "0-0-0"
            return f"{rec.wins}-{rec.losses}-{rec.ot_losses}"

        show_all = self.results_filter_var.get() == "All League Events"
        for idx, game in enumerate(results, start=1):
            is_user_game = self.user_team_name in {game.home.name, game.away.name}
            if not show_all and not is_user_game:
                continue
            status = "FINAL/OT" if game.overtime else "FINAL"
            if is_user_game:
                self._append_results(f"Game {idx} [{status}] <<< YOUR TEAM >>>")
            else:
                self._append_results(f"Game {idx} [{status}]")
            self._append_results(
                f"  Records: {game.away.name} ({_record_line(game.away.name)}) | "
                f"{game.home.name} ({_record_line(game.home.name)})"
            )
            self._append_game_result_colored(
                away_name=game.away.name,
                away_goals=game.away_goals,
                home_goals=game.home_goals,
                home_name=game.home.name,
                overtime=game.overtime,
            )
            self._append_results(
                f"  Goalies: {game.away.name}={game.away_goalie.name if game.away_goalie else 'N/A'} | "
                f"{game.home.name}={game.home_goalie.name if game.home_goalie else 'N/A'}"
            )
            injuries = game.home_injuries + game.away_injuries
            if injuries:
                self._append_results("  Injuries:")
                for ev in injuries:
                    self._append_results(
                        f"    {ev.player.team_name}: {ev.player.name} ({ev.player.position}) out {ev.games_out} games"
                    )
            else:
                self._append_results("  Injuries: none")
            stars = self._game_three_stars(game)
            if stars:
                self._append_results("  Three Stars:")
                for label, line in stars:
                    self._append_results(f"    {label}: {line}")

        if self.simulator.is_complete():
            self.day_label.config(text=f"Day: {self.simulator.total_days} / {self.simulator.total_days} (Complete)")
            if self.results_context_label is not None:
                self.results_context_label.config(
                    text=f"Season {self.simulator.season_number} Day {self.simulator.total_days}/{self.simulator.total_days} (Complete)"
                )
            self._append_results("Regular season complete. Click 'Sim Next Day' to start playoffs.")
        else:
            self._refresh_season_day_labels()

        self.refresh_standings()
        self.refresh_goalie_selector()
        self.refresh_user_stats_window()
        self._refresh_hof_window()
        self.show_my_team_stats()
        self.show_my_goalie_stats()

    def refresh_standings(self) -> None:
        if self.simulator is None:
            return

        league_standings = self.simulator.get_standings()
        clinched = self.simulator.get_playoff_clinch_status()
        self.standings_row_to_team.clear()
        league_rank: dict[str, int] = {}
        conf_rank: dict[str, int] = {}
        div_rank: dict[str, int] = {}
        conf_count: dict[str, int] = {}
        div_count: dict[str, int] = {}
        for idx, rec in enumerate(league_standings, start=1):
            league_rank[rec.team.name] = idx
            conf = rec.team.conference
            div = rec.team.division
            conf_count[conf] = conf_count.get(conf, 0) + 1
            div_count[div] = div_count.get(div, 0) + 1
            conf_rank[rec.team.name] = conf_count[conf]
            div_rank[rec.team.name] = div_count[div]

        mode = self.standings_mode_var.get()
        for section, tree in self.standings_views.items():
            tree_key = str(tree)
            self.standings_row_to_team[tree_key] = {}
            scope = self.standings_view_scope.get(section, ("league", None))
            scope_kind, scope_value = scope
            if scope_kind == "conference" and scope_value is not None:
                rows = self.simulator.get_conference_standings(scope_value)
            elif scope_kind == "division" and scope_value is not None:
                rows = self.simulator.get_division_standings(scope_value)
            elif scope_kind == "wildcard" and scope_value is not None:
                conf_rows = self.simulator.get_conference_standings(scope_value)
                divisions = sorted({r.team.division for r in conf_rows})
                rows = []
                if len(divisions) == 2:
                    div_a, div_b = divisions[0], divisions[1]
                    a_rows = [r for r in conf_rows if r.team.division == div_a]
                    b_rows = [r for r in conf_rows if r.team.division == div_b]
                    a_top = a_rows[:3]
                    b_top = b_rows[:3]
                    qualified_names = {r.team.name for r in a_top + b_top}
                    wildcard_race = [r for r in conf_rows if r.team.name not in qualified_names]

                    rows.append(("header", f"{div_a.upper()} TOP 3", None))
                    rows.extend([("team", "", r) for r in a_top])
                    rows.append(("header", f"{div_b.upper()} TOP 3", None))
                    rows.extend([("team", "", r) for r in b_top])
                    rows.append(("header", "WILD CARD", None))
                    wc_in = wildcard_race[:2]
                    wc_out = wildcard_race[2:]
                    for i, r in enumerate(wc_in, start=1):
                        rows.append(("team", f"WC{i}", r))
                    if wc_out:
                        rows.append(("cutline", "---- CUT LINE ----", None))
                        rows.extend([("team", "", r) for r in wc_out])
                else:
                    rows = [("team", "", r) for r in conf_rows]
            else:
                rows = league_standings

            for row in tree.get_children():
                tree.delete(row)
            for idx, row_data in enumerate(rows):
                row_kind = "team"
                seed_prefix = ""
                rec = row_data
                if scope_kind == "wildcard" and isinstance(row_data, tuple):
                    row_kind = str(row_data[0])
                    seed_prefix = str(row_data[1])
                    rec = row_data[2]
                if row_kind == "header":
                    tree.insert(
                        "",
                        tk.END,
                        values=(seed_prefix, "", "", "", "", "", "", "", "", "", "", "", ""),
                        tags=("group_header",),
                    )
                    continue
                if row_kind == "cutline":
                    tree.insert(
                        "",
                        tk.END,
                        values=(seed_prefix, "", "", "", "", "", "", "", "", "", "", "", ""),
                        tags=("group_cutline",),
                    )
                    continue
                if not hasattr(rec, "team"):
                    continue
                team_label = self._team_display_name(rec.team)
                if clinched.get(rec.team.name, False):
                    team_label = f"x-{team_label}"
                if seed_prefix:
                    team_label = f"{seed_prefix} {team_label}"
                if rec.goal_diff > 0:
                    diff_display = f"+{rec.goal_diff}"
                elif rec.goal_diff < 0:
                    diff_display = f"{rec.goal_diff}"
                else:
                    diff_display = "0"
                row_id = tree.insert(
                    "",
                    tk.END,
                    image=(self._team_logo_image(rec.team.name, target_px=26) or ""),
                    values=(
                        team_label,
                        rec.games_played,
                        rec.wins,
                        rec.losses,
                        rec.ot_losses,
                        rec.points,
                        rec.home_record,
                        rec.away_record,
                        rec.goals_for,
                        rec.goals_against,
                        diff_display,
                        rec.last10,
                        rec.streak,
                    ),
                    tags=(self._table_row_tag(idx),),
                )
                self.standings_row_to_team[tree_key][row_id] = rec.team.name

    def refresh_roster(self) -> None:
        if self._stats_scope == "team":
            self.show_my_team_stats()

    def _render_players(self, players: list[Player], limit: int) -> None:
        if self.players is None:
            return
        for row in self.players.get_children():
            self.players.delete(row)
        self.player_row_to_name.clear()
        self.player_row_to_team.clear()
        for idx, p in enumerate(players[:limit]):
            team = self.simulator.get_team(p.team_name) if self.simulator else None
            injured, out_games = self._display_injury(p)
            drafted_names = set()
            if self.simulator is not None:
                drafted_names = set(self.simulator.last_offseason_drafted.get(p.team_name, []))
            row = self.players.insert(
                "",
                tk.END,
                values=(
                    p.team_name,
                    p.name,
                    p.age,
                    p.position,
                    p.games_played,
                    p.goals,
                    p.assists,
                    p.points,
                    "Y" if team and team.is_dressed(p) else "N",
                    "Y" if p.name in drafted_names else "N",
                    injured,
                    out_games,
                ),
                tags=(self._table_row_tag(idx), self._team_tag(p.team_name)),
            )
            if team is not None:
                self.players.tag_configure(self._team_tag(p.team_name), foreground=team.primary_color)
            self.player_row_to_name[row] = p.name
            self.player_row_to_team[row] = p.team_name

    def _render_goalies(self, goalies: list[Player], limit: int) -> None:
        if self.goalies is None:
            return
        for row in self.goalies.get_children():
            self.goalies.delete(row)
        self.goalie_row_to_name.clear()
        self.goalie_row_to_team.clear()
        for idx, goalie in enumerate(goalies[:limit]):
            team = self.simulator.get_team(goalie.team_name) if self.simulator else None
            row = self.goalies.insert(
                "",
                tk.END,
                values=(
                    goalie.team_name,
                    goalie.name,
                    goalie.age,
                    goalie.goalie_games,
                    goalie.goalie_wins,
                    goalie.goalie_losses,
                    goalie.goalie_ot_losses,
                    f"{goalie.gaa:.2f}",
                    f"{goalie.save_pct:.3f}",
                ),
                tags=(self._table_row_tag(idx), self._team_tag(goalie.team_name)),
            )
            if team is not None:
                self.goalies.tag_configure(self._team_tag(goalie.team_name), foreground=team.primary_color)
            self.goalie_row_to_name[row] = goalie.name
            self.goalie_row_to_team[row] = goalie.team_name

    def on_standings_team_select(self, event: tk.Event[tk.Misc]) -> None:
        if self.simulator is None:
            return
        tree = event.widget
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0], "values")
        if not values:
            return
        columns = list(tree["columns"])
        if "Team" not in columns:
            return
        team_name = self.standings_row_to_team.get(str(tree), {}).get(selection[0], "")
        if not team_name:
            team_idx = columns.index("Team")
            if team_idx >= len(values):
                return
            team_name = str(values[team_idx]).strip()
        if self.simulator.get_team(team_name) is None:
            return
        self.team_var.set(team_name)
        self.user_team_name = team_name
        self._refresh_main_team_badge()
        self._stats_scope = "team"
        self.refresh_goalie_selector()
        self.show_my_team_stats()
        self.show_my_goalie_stats()

    def toggle_selected_player_dressed(self) -> None:
        team = self._current_team()
        if team is None:
            return
        selected = self.players.selection() if self.players is not None else ()
        row_to_name = self.player_row_to_name
        row_to_team = self.player_row_to_team
        if self.user_stats_players is not None and self.user_stats_popup is not None and self.user_stats_popup.winfo_exists():
            popup_selected = self.user_stats_players.selection()
            if popup_selected:
                selected = popup_selected
                row_to_name = self.user_stats_row_to_name
                row_to_team = self.user_stats_row_to_team
        if not selected:
            self._append_results("Select a player in Player Stats first.")
            return
        selected_row = selected[0]
        player_name = row_to_name.get(selected_row)
        player_team = row_to_team.get(selected_row)
        if player_name is None:
            return
        if player_team != team.name:
            self._append_results("You can only change dress status for your currently selected team.")
            return
        success = team.toggle_dressed_status(player_name)
        if not success:
            self._append_results(
                f"Cannot change dress status for {player_name}. Keep at least 12F/6D/2G dressed and max 20 total."
            )
        self.refresh_goalie_selector()
        self.show_my_team_stats()
        self.refresh_user_stats_window()

    def auto_best_lineup(self) -> None:
        team = self._current_team()
        if team is None:
            return
        team.set_default_lineup()
        self._append_results(f"Auto-selected best lineup for {team.name}.")
        self.refresh_goalie_selector()
        self.show_my_team_stats()
        self.refresh_user_stats_window()

    def show_my_team_stats(self) -> None:
        if self.simulator is None:
            return
        team = self.team_var.get()
        self._stats_scope = "team"
        self._render_players(self.simulator.get_player_stats(team_name=team), limit=80)
        self.refresh_user_stats_window()

    def show_league_stats(self) -> None:
        if self.simulator is None:
            return
        self._stats_scope = "league"
        self._render_players(self.simulator.get_player_stats(), limit=450)
        self.refresh_user_stats_window()

    def show_my_goalie_stats(self) -> None:
        if self.simulator is None:
            return
        team = self.team_var.get()
        if self._stats_scope != "league":
            self._stats_scope = "team"
        self._render_goalies(self.simulator.get_goalie_stats(team_name=team), limit=10)
        self.refresh_user_stats_window()

    def show_league_goalie_stats(self) -> None:
        if self.simulator is None:
            return
        self._stats_scope = "league"
        self._render_goalies(self.simulator.get_goalie_stats(), limit=60)
        self.refresh_user_stats_window()

    def _on_hof_close(self) -> None:
        if self.hof_popup is not None:
            self.hof_popup.destroy()
        self.hof_popup = None
        self.hof_tree = None
        self.history_tree = None
        self.hof_title_label = None
        self.hof_points_tree = None
        self.hof_goals_tree = None
        self.hof_assists_tree = None
        self.hof_goalie_wins_tree = None
        self.hof_coach_tree = None
        self.hof_retired_section = None
        self.hof_history_section = None

    def _franchise_leaders(
        self,
        team_name: str,
    ) -> tuple[
        list[tuple[str, int, str]],
        list[tuple[str, int, str]],
        list[tuple[str, int, str]],
        list[tuple[str, int, str]],
    ]:
        if self.simulator is None:
            return ([], [], [], [])
        totals: dict[str, dict[str, object]] = {}

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
                career_w = sum(int(s.get("goalie_w", 0)) for s in player.career_seasons if isinstance(s, dict)) + player.goalie_wins
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

        points = sorted(
            [(str(v["name"]), int(v["p"]), str(v.get("status", "Retired"))) for v in totals.values() if int(v["p"]) > 0],
            key=lambda x: (x[1], x[0]),
            reverse=True,
        )[:10]
        goals = sorted(
            [(str(v["name"]), int(v["g"]), str(v.get("status", "Retired"))) for v in totals.values() if int(v["g"]) > 0],
            key=lambda x: (x[1], x[0]),
            reverse=True,
        )[:10]
        assists = sorted(
            [(str(v["name"]), int(v["a"]), str(v.get("status", "Retired"))) for v in totals.values() if int(v["a"]) > 0],
            key=lambda x: (x[1], x[0]),
            reverse=True,
        )[:10]
        goalie_wins = sorted(
            [(str(v["name"]), int(v["w"]), str(v.get("status", "Retired"))) for v in totals.values() if int(v["w"]) > 0],
            key=lambda x: (x[1], x[0]),
            reverse=True,
        )[:10]
        return (points, goals, assists, goalie_wins)

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
                teams = {
                    str(series.get("higher_seed", "")),
                    str(series.get("lower_seed", "")),
                }
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

    def _refresh_hof_window(self) -> None:
        if self.hof_popup is None or not self.hof_popup.winfo_exists():
            return
        if (
            self.simulator is None
            or self.hof_tree is None
            or self.history_tree is None
            or self.hof_points_tree is None
            or self.hof_goals_tree is None
            or self.hof_assists_tree is None
            or self.hof_goalie_wins_tree is None
            or self.hof_coach_tree is None
        ):
            return
        team_name = self.team_var.get()
        team = self.simulator.get_team(team_name)
        logo_image = self._team_logo_image(team_name, target_px=56) if team is not None else None
        title_text = f"{team_name} Franchise" if logo_image else f"{team.logo if team is not None else 'TM'}  {team_name} Franchise"
        if self.hof_title_label is not None:
            self.hof_title_label.config(
                text=title_text,
                image=(logo_image or ""),
                compound=tk.LEFT,
                foreground=(team.primary_color if team is not None else self.palette["text"]),
            )

        for row in self.hof_tree.get_children():
            self.hof_tree.delete(row)
        team_hof = [e for e in self.simulator.hall_of_fame if str(e.get("team_at_retirement", "")) == team_name]
        team_hof = sorted(team_hof, key=lambda e: (int(e.get("career_p", 0)), int(e.get("goalie_w", 0))), reverse=True)
        for idx, entry in enumerate(team_hof):
            self.hof_tree.insert(
                "",
                tk.END,
                values=(
                    entry.get("name", ""),
                    entry.get("position", ""),
                    entry.get("age_at_retirement", 0),
                    entry.get("seasons_played", 0),
                    entry.get("career_gp", 0),
                    entry.get("career_g", 0),
                    entry.get("career_a", 0),
                    entry.get("career_p", 0),
                    entry.get("goalie_w", 0),
                    entry.get("goalie_l", 0),
                    entry.get("goalie_otl", 0),
                    entry.get("goalie_gaa", 0.0),
                    entry.get("goalie_sv_pct", 0.0),
                    entry.get("retired_after_season", 0),
                ),
                tags=(self._table_row_tag(idx),),
            )

        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        for idx, season in enumerate(self.simulator.season_history):
            standings = season.get("standings", [])
            if not isinstance(standings, list):
                continue
            team_row = next((r for r in standings if isinstance(r, dict) and str(r.get("team", "")) == team_name), None)
            if team_row is None:
                continue
            league_rows = [r for r in standings if isinstance(r, dict)]
            league_rank = next((i + 1 for i, r in enumerate(league_rows) if str(r.get("team", "")) == team_name), 0)
            conference = str(team_row.get("conference", team.conference if team else ""))
            division = str(team_row.get("division", ""))
            conf_rows = [r for r in league_rows if str(r.get("conference", "")) == conference]
            div_rows = [r for r in league_rows if str(r.get("division", "")) == division]
            conf_rank = next((i + 1 for i, r in enumerate(conf_rows) if str(r.get("team", "")) == team_name), 0)
            div_rank = next((i + 1 for i, r in enumerate(div_rows) if str(r.get("team", "")) == team_name), 0)
            div_title = "Y" if div_rank == 1 else ""
            cup_winner = "Y" if str(season.get("champion", "")) == team_name else ""
            playoffs_made, playoff_result = self._playoff_outcome_for_team(season, team_name)
            conference_champ = "Y" if playoff_result == "Cup Final" else ""
            self.history_tree.insert(
                "",
                tk.END,
                values=(
                    season.get("season", ""),
                    team_row.get("gp", 0),
                    team_row.get("wins", 0),
                    team_row.get("losses", 0),
                    team_row.get("ot_losses", 0),
                    team_row.get("points", 0),
                    league_rank,
                    conf_rank,
                    div_rank,
                    div_title,
                    playoffs_made,
                    playoff_result,
                    conference_champ,
                    cup_winner,
                ),
                tags=(self._table_row_tag(idx),),
            )

        points, goals, assists, goalie_wins = self._franchise_leaders(team_name)
        for tree in (self.hof_points_tree, self.hof_goals_tree, self.hof_assists_tree, self.hof_goalie_wins_tree):
            for row in tree.get_children():
                tree.delete(row)
        for idx, (name, val, status) in enumerate(points, start=1):
            self.hof_points_tree.insert("", tk.END, values=(idx, name, val, status), tags=(self._table_row_tag(idx - 1),))
        for idx, (name, val, status) in enumerate(goals, start=1):
            self.hof_goals_tree.insert("", tk.END, values=(idx, name, val, status), tags=(self._table_row_tag(idx - 1),))
        for idx, (name, val, status) in enumerate(assists, start=1):
            self.hof_assists_tree.insert("", tk.END, values=(idx, name, val, status), tags=(self._table_row_tag(idx - 1),))
        for idx, (name, val, status) in enumerate(goalie_wins, start=1):
            self.hof_goalie_wins_tree.insert("", tk.END, values=(idx, name, val, status), tags=(self._table_row_tag(idx - 1),))

        for row in self.hof_coach_tree.get_children():
            self.hof_coach_tree.delete(row)
        for idx, season in enumerate(self.simulator.season_history):
            coaches = season.get("coaches", [])
            coach_row = None
            if isinstance(coaches, list):
                coach_row = next(
                    (
                        r
                        for r in coaches
                        if isinstance(r, dict) and str(r.get("team", "")) == team_name
                    ),
                    None,
                )
            if coach_row is None:
                standings = season.get("standings", [])
                team_row = (
                    next((r for r in standings if isinstance(r, dict) and str(r.get("team", "")) == team_name), None)
                    if isinstance(standings, list)
                    else None
                )
                if team_row is None:
                    continue
                coach_row = {
                    "coach": "-",
                    "coach_rating": "-",
                    "coach_style": "-",
                    "wins": team_row.get("wins", 0),
                    "losses": team_row.get("losses", 0),
                    "ot_losses": team_row.get("ot_losses", 0),
                    "points": team_row.get("points", 0),
                    "point_pct": round((float(team_row.get("point_pct", 0.0)) if team_row.get("point_pct") is not None else 0.0), 3),
                }
            self.hof_coach_tree.insert(
                "",
                tk.END,
                values=(
                    season.get("season", ""),
                    coach_row.get("coach", "-"),
                    coach_row.get("coach_rating", "-"),
                    coach_row.get("coach_style", "-"),
                    coach_row.get("wins", 0),
                    coach_row.get("losses", 0),
                    coach_row.get("ot_losses", 0),
                    coach_row.get("points", 0),
                    coach_row.get("point_pct", 0.0),
                    "Y" if str(season.get("champion", "")) == team_name else "",
                ),
                tags=(self._table_row_tag(idx),),
            )


    def show_hall_of_fame(self) -> None:
        if self.simulator is None:
            self._append_results("Start a season first.")
            return
        if self.hof_popup is None or not self.hof_popup.winfo_exists():
            popup = tk.Toplevel(self.root)
            popup.title("Franchise History")
            popup.geometry("1500x860")
            popup.minsize(1200, 700)
            popup.configure(bg=self.palette["bg"])
            popup.transient(self.root)
            popup.protocol("WM_DELETE_WINDOW", self._on_hof_close)

            frame = ttk.Frame(popup, padding=10, style="Card.TFrame")
            frame.pack(fill=tk.BOTH, expand=True)

            title = ttk.Label(frame, text="Franchise", style="CardTitle.TLabel")
            title.pack(anchor=tk.W)

            section_controls = ttk.Frame(frame)
            section_controls.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(section_controls, text="Retired Players", command=lambda: self._set_hof_view("retired")).pack(side=tk.LEFT)
            ttk.Button(section_controls, text="Season History", command=lambda: self._set_hof_view("history")).pack(side=tk.LEFT, padx=(6, 0))

            retired_section = ttk.Frame(frame)
            history_section = ttk.Frame(frame)

            ttk.Label(retired_section, text="Hall of Fame (Retired Players)", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 0))
            hof_tree = ttk.Treeview(
                retired_section,
                columns=("Name", "Pos", "Age", "Seasons", "GP", "G", "A", "P", "W", "L", "OTL", "GAA", "SV%", "RetS"),
                show="headings",
                height=12,
            )
            for col, width in [
                ("Name", 190),
                ("Pos", 45),
                ("Age", 50),
                ("Seasons", 70),
                ("GP", 50),
                ("G", 50),
                ("A", 50),
                ("P", 55),
                ("W", 50),
                ("L", 50),
                ("OTL", 55),
                ("GAA", 60),
                ("SV%", 60),
                ("RetS", 60),
            ]:
                hof_tree.heading(col, text=col)
                hof_tree.column(col, width=width, anchor=tk.CENTER)
            self._apply_table_row_styles(hof_tree)
            hof_tree.pack(fill=tk.X)

            ttk.Label(retired_section, text="Franchise Top 10 Leaders", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(10, 0))
            leaders_wrap = ttk.Frame(retired_section)
            leaders_wrap.pack(fill=tk.X, pady=(2, 6))

            def _leader_tree(parent: tk.Widget, value_col: str) -> ttk.Treeview:
                tree = ttk.Treeview(parent, columns=("Rk", "Player", value_col, "Status"), show="headings", height=10)
                tree.heading("Rk", text="Rk")
                tree.heading("Player", text="Player")
                tree.heading(value_col, text=value_col)
                tree.heading("Status", text="Status")
                tree.column("Rk", width=40, anchor=tk.CENTER)
                tree.column("Player", width=155, anchor=tk.W)
                tree.column(value_col, width=80, anchor=tk.CENTER)
                tree.column("Status", width=85, anchor=tk.CENTER)
                self._apply_table_row_styles(tree)
                return tree

            col1 = ttk.Frame(leaders_wrap)
            col2 = ttk.Frame(leaders_wrap)
            col3 = ttk.Frame(leaders_wrap)
            col4 = ttk.Frame(leaders_wrap)
            col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
            col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
            col3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
            col4.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            ttk.Label(col1, text="Points", style="Muted.TLabel").pack(anchor=tk.W)
            points_tree = _leader_tree(col1, "P")
            points_tree.pack(fill=tk.BOTH, expand=True)

            ttk.Label(col2, text="Goals", style="Muted.TLabel").pack(anchor=tk.W)
            goals_tree = _leader_tree(col2, "G")
            goals_tree.pack(fill=tk.BOTH, expand=True)

            ttk.Label(col3, text="Assists", style="Muted.TLabel").pack(anchor=tk.W)
            assists_tree = _leader_tree(col3, "A")
            assists_tree.pack(fill=tk.BOTH, expand=True)

            ttk.Label(col4, text="Goalie Wins", style="Muted.TLabel").pack(anchor=tk.W)
            goalie_wins_tree = _leader_tree(col4, "W")
            goalie_wins_tree.pack(fill=tk.BOTH, expand=True)

            ttk.Label(history_section, text="Season by Season Franchise History", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 0))
            history_tree = ttk.Treeview(
                history_section,
                columns=(
                    "Season",
                    "Games Played",
                    "Wins",
                    "Losses",
                    "OT Losses",
                    "Points",
                    "League Rank",
                    "Conference Rank",
                    "Division Rank",
                    "Division Title",
                    "Playoff",
                    "Playoff Result",
                    "Conference Champ",
                    "Cup Winner",
                ),
                show="headings",
                height=14,
            )
            for col, width in [
                ("Season", 70),
                ("Games Played", 95),
                ("Wins", 55),
                ("Losses", 60),
                ("OT Losses", 75),
                ("Points", 60),
                ("League Rank", 85),
                ("Conference Rank", 110),
                ("Division Rank", 95),
                ("Division Title", 95),
                ("Playoff", 65),
                ("Playoff Result", 130),
                ("Conference Champ", 120),
                ("Cup Winner", 95),
            ]:
                history_tree.heading(col, text=col)
                history_tree.column(col, width=width, anchor=tk.CENTER)
            self._apply_table_row_styles(history_tree)
            history_tree.pack(fill=tk.BOTH, expand=True)

            ttk.Label(history_section, text="Coaches Over Time", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(10, 0))
            coach_tree = ttk.Treeview(
                history_section,
                columns=("Season", "Coach", "Rate", "Style", "W", "L", "OTL", "Pts", "P%", "Champ"),
                show="headings",
                height=10,
            )
            for col, width in [
                ("Season", 70),
                ("Coach", 210),
                ("Rate", 60),
                ("Style", 90),
                ("W", 50),
                ("L", 50),
                ("OTL", 55),
                ("Pts", 55),
                ("P%", 60),
                ("Champ", 70),
            ]:
                coach_tree.heading(col, text=col)
                coach_tree.column(col, width=width, anchor=tk.CENTER if col != "Coach" else tk.W)
            self._apply_table_row_styles(coach_tree)
            coach_tree.pack(fill=tk.X)

            self.hof_popup = popup
            self.hof_tree = hof_tree
            self.history_tree = history_tree
            self.hof_title_label = title
            self.hof_points_tree = points_tree
            self.hof_goals_tree = goals_tree
            self.hof_assists_tree = assists_tree
            self.hof_goalie_wins_tree = goalie_wins_tree
            self.hof_coach_tree = coach_tree
            self.hof_retired_section = retired_section
            self.hof_history_section = history_section
            self._set_hof_view("retired")
        else:
            self.hof_popup.deiconify()
            self.hof_popup.lift()
            self.hof_popup.focus_force()
        self._refresh_hof_window()

    def show_season_history(self) -> None:
        if self.simulator is None:
            self._append_results("Start a season first.")
            return
        history = self.simulator.season_history
        if not history:
            self._append_results("No completed seasons in history yet.")
            return
        self._append_results("")
        self._append_results("=== Season History ===")
        for season in history[-10:]:
            playoffs = season.get("playoffs", {})
            cup_name = str(playoffs.get("cup_name", "Cup")) if isinstance(playoffs, dict) else "Cup"
            self._append_results(f"Season {season['season']}: {cup_name} Champion {season['champion']}")
            retired = season.get("retired", [])
            if isinstance(retired, list):
                self._append_results(f"  Retired: {len(retired)}")
            draft_details = season.get("draft_details", {})
            if isinstance(draft_details, dict) and draft_details:
                for team_name, picks in draft_details.items():
                    if not isinstance(picks, list) or not picks:
                        continue
                    out: list[str] = []
                    for pick in picks:
                        if not isinstance(pick, dict):
                            continue
                        name = str(pick.get("name", ""))
                        overall = pick.get("overall")
                        round_no = pick.get("round")
                        if overall is not None and round_no is not None:
                            out.append(f"{name} (R{round_no} #{overall})")
                        else:
                            out.append(name)
                    if out:
                        self._append_results(f"  Draft {team_name}: {', '.join(out)}")
            else:
                draft = season.get("draft", {})
                if isinstance(draft, dict):
                    for team_name, picks in draft.items():
                        if picks:
                            self._append_results(f"  Draft {team_name}: {', '.join(picks)}")

    def fire_selected_coach(self) -> None:
        if self.simulator is None:
            self._append_results("Start a season first.")
            return
        team_name = self.team_var.get()
        team = self.simulator.get_team(team_name)
        if team is None:
            return
        record = next((r for r in self.simulator.get_standings() if r.team.name == team_name), None)
        point_pct = record.point_pct if record is not None and record.games_played > 0 else 0.0
        rec_text = (
            f"{record.wins}-{record.losses}-{record.ot_losses}"
            if record is not None
            else "0-0-0"
        )
        confirmed = messagebox.askyesno(
            "Fire Coach",
            (
                f"{team.name} coach: {team.coach_name} (rating {team.coach_rating:.2f}, style {team.coach_style}).\n"
                f"Current record: {rec_text} (P% {point_pct:.3f}).\n\n"
                "Fire this coach and hire a replacement?"
            ),
        )
        if not confirmed:
            return
        result = self.simulator.fire_coach(team_name)
        if not result.get("fired"):
            self._append_results("Unable to change coach.")
            return
        self._append_results(
            f"COACHING CHANGE ({team_name}): "
            f"{result.get('old_name')} ({result.get('old_rating')}) -> "
            f"{result.get('new_name')} ({result.get('new_rating')}, {result.get('new_style')})"
        )
        self._refresh_main_team_badge()
        self.show_my_team_stats()
        self.refresh_goalie_selector()
        self.refresh_user_stats_window()
        self._refresh_hof_window()

    def reset_stats(self) -> None:
        confirmed = messagebox.askyesno(
            "Reset Stats",
            "This will delete saved season history, career history, and hall of fame data, and restart from Season 1. Continue?",
        )
        if not confirmed:
            return

        if self.simulator is None:
            temp = LeagueSimulator(teams=build_default_teams(), games_per_matchup=2)
            temp.reset_persistent_history()
        else:
            self.simulator.reset_persistent_history()

        self._set_results("Saved season and career stats were reset. Starting a fresh league.")
        self.start_season()

    def on_player_select(self, _event: tk.Event[tk.Misc]) -> None:
        if self.simulator is None or self.players is None:
            return
        selection = self.players.selection()
        if not selection:
            return
        row = selection[0]
        self._open_player_popup(self.player_row_to_name.get(row), self.player_row_to_team.get(row))

    def on_goalie_select(self, _event: tk.Event[tk.Misc]) -> None:
        if self.simulator is None or self.goalies is None:
            return
        selection = self.goalies.selection()
        if not selection:
            return
        row = selection[0]
        self._open_player_popup(self.goalie_row_to_name.get(row), self.goalie_row_to_team.get(row))

    def _on_user_stats_close(self) -> None:
        if self.user_stats_popup is not None:
            self.user_stats_popup.destroy()
        self.user_stats_popup = None
        self.user_stats_players = None
        self.user_stats_goalies = None
        self.user_stats_team_label = None
        self.user_stats_row_to_name.clear()
        self.user_stats_row_to_team.clear()
        self.user_stats_goalie_row_to_name.clear()
        self.user_stats_goalie_row_to_team.clear()

    def _on_user_stats_player_select(self, _event: tk.Event[tk.Misc]) -> None:
        if self.user_stats_players is None:
            return
        selection = self.user_stats_players.selection()
        if not selection:
            return
        row = selection[0]
        self._open_player_popup(self.user_stats_row_to_name.get(row), self.user_stats_row_to_team.get(row))

    def _on_user_stats_goalie_select(self, _event: tk.Event[tk.Misc]) -> None:
        if self.user_stats_goalies is None:
            return
        selection = self.user_stats_goalies.selection()
        if not selection:
            return
        row = selection[0]
        self._open_player_popup(
            self.user_stats_goalie_row_to_name.get(row),
            self.user_stats_goalie_row_to_team.get(row),
        )

    def refresh_user_stats_window(self) -> None:
        if self.user_stats_popup is None or not self.user_stats_popup.winfo_exists():
            return
        if self.simulator is None or self.user_stats_players is None or self.user_stats_goalies is None:
            return
        team_name = self.team_var.get()
        scope = self.user_stats_scope
        team_obj = self.simulator.get_team(team_name)
        logo_image = self._team_logo_image(team_name, target_px=56) if (team_obj is not None and scope == "team") else None
        title_target = (
            team_name if logo_image else f"{team_obj.logo if team_obj is not None else 'TM'}  {team_name}"
        ) if scope == "team" else "League: All Teams"
        if scope == "team" and team_obj is not None:
            title_target = f"{title_target}  |  Coach: {team_obj.coach_name} ({team_obj.coach_rating:.2f}, {team_obj.coach_style})"
            standings = self.simulator.get_standings()
            rec = next((r for r in standings if r.team.name == team_name), None)
            if rec is not None:
                pp_sorted = sorted(standings, key=lambda r: (r.pp_pct, r.pp_goals, -r.pp_chances), reverse=True)
                pk_sorted = sorted(standings, key=lambda r: (r.pk_pct, -r.pk_goals_against, -r.pk_chances_against), reverse=True)
                pp_rank = next((idx for idx, row in enumerate(pp_sorted, start=1) if row.team.name == team_name), 0)
                pk_rank = next((idx for idx, row in enumerate(pk_sorted, start=1) if row.team.name == team_name), 0)
                title_target = (
                    f"{title_target}  |  "
                    f"PP%: {rec.pp_pct * 100:.1f} (#{pp_rank})  "
                    f"PK%: {rec.pk_pct * 100:.1f} (#{pk_rank})"
                )
        if self.user_stats_team_label is not None:
            self.user_stats_team_label.config(
                text=title_target,
                image=(logo_image or ""),
                compound=tk.LEFT,
                foreground=(team_obj.primary_color if team_obj and scope == "team" else self.palette["text"]),
            )
        if scope == "team":
            players = self.simulator.get_player_stats(team_name=team_name)
            goalies = self.simulator.get_goalie_stats(team_name=team_name)
        else:
            players = self.simulator.get_player_stats()
            goalies = self.simulator.get_goalie_stats()

        for row in self.user_stats_players.get_children():
            self.user_stats_players.delete(row)
        self.user_stats_row_to_name.clear()
        self.user_stats_row_to_team.clear()
        drafted_names = set(self.simulator.last_offseason_drafted.get(team_name, []))
        for idx, p in enumerate(players):
            team = self.simulator.get_team(p.team_name)
            injured, out_games = self._display_injury(p)
            row = self.user_stats_players.insert(
                "",
                tk.END,
                values=(
                    p.team_name,
                    p.name,
                    p.age,
                    p.position,
                    p.games_played,
                    p.goals,
                    p.assists,
                    p.points,
                    "Y" if team and team.is_dressed(p) else "N",
                    "Y" if (scope == "team" and p.name in drafted_names) else "N",
                    injured,
                    out_games,
                ),
                tags=(self._table_row_tag(idx),),
            )
            self.user_stats_row_to_name[row] = p.name
            self.user_stats_row_to_team[row] = p.team_name

        for row in self.user_stats_goalies.get_children():
            self.user_stats_goalies.delete(row)
        self.user_stats_goalie_row_to_name.clear()
        self.user_stats_goalie_row_to_team.clear()
        for idx, goalie in enumerate(goalies):
            row = self.user_stats_goalies.insert(
                "",
                tk.END,
                values=(
                    goalie.team_name,
                    goalie.name,
                    goalie.age,
                    goalie.goalie_games,
                    goalie.goalie_wins,
                    goalie.goalie_losses,
                    goalie.goalie_ot_losses,
                    f"{goalie.gaa:.2f}",
                    f"{goalie.save_pct:.3f}",
                ),
                tags=(self._table_row_tag(idx),),
            )
            self.user_stats_goalie_row_to_name[row] = goalie.name
            self.user_stats_goalie_row_to_team[row] = goalie.team_name

    def open_user_stats_window(self, scope: str = "team") -> None:
        if self.simulator is None:
            return
        self.user_stats_scope = "league" if scope == "league" else "team"
        if self.user_stats_popup is None or not self.user_stats_popup.winfo_exists():
            popup = tk.Toplevel(self.root)
            popup.title("User Team Stats + Lineup")
            popup.geometry("1600x900")
            popup.minsize(1280, 760)
            popup.configure(bg=self.palette["bg"])
            popup.transient(self.root)
            popup.protocol("WM_DELETE_WINDOW", self._on_user_stats_close)

            frame = ttk.Frame(popup, padding=10, style="Card.TFrame")
            frame.pack(fill=tk.BOTH, expand=True)

            top = ttk.Frame(frame)
            top.pack(fill=tk.X, pady=(0, 6))
            team_label = ttk.Label(top, text=f"Team: {self.team_var.get()}", style="CardTitle.TLabel")
            team_label.pack(side=tk.LEFT)
            ttk.Button(top, text="Toggle Dress", command=self.toggle_selected_player_dressed).pack(side=tk.RIGHT)
            ttk.Button(top, text="Auto Best Lineup", command=self.auto_best_lineup).pack(side=tk.RIGHT, padx=6)

            ttk.Label(frame, text="Player Stats + Dress Status", style="CardTitle.TLabel").pack(anchor=tk.W)
            players = ttk.Treeview(
                frame,
                columns=("Team", "Player", "Age", "Pos", "GP", "G", "A", "P", "Dress", "Draft", "Injured", "Out"),
                show="headings",
                height=22,
            )
            for col, w in [
                ("Team", 160),
                ("Player", 220),
                ("Age", 45),
                ("Pos", 45),
                ("GP", 45),
                ("G", 45),
                ("A", 45),
                ("P", 45),
                ("Dress", 60),
                ("Draft", 60),
                ("Injured", 70),
                ("Out", 50),
            ]:
                players.heading(col, text=col)
                players.column(col, width=w, anchor=tk.CENTER)
            self._apply_table_row_styles(players)
            players.pack(fill=tk.BOTH, expand=True)
            players.bind("<<TreeviewSelect>>", self._on_user_stats_player_select)

            ttk.Label(frame, text="Goalie Stats", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(8, 0))
            goalies = ttk.Treeview(
                frame,
                columns=("Team", "Goalie", "Age", "GP", "W", "L", "OTL", "GAA", "SV%"),
                show="headings",
                height=8,
            )
            for col, w in [
                ("Team", 160),
                ("Goalie", 220),
                ("Age", 45),
                ("GP", 45),
                ("W", 45),
                ("L", 45),
                ("OTL", 50),
                ("GAA", 60),
                ("SV%", 60),
            ]:
                goalies.heading(col, text=col)
                goalies.column(col, width=w, anchor=tk.CENTER)
            self._apply_table_row_styles(goalies)
            goalies.pack(fill=tk.X)
            goalies.bind("<<TreeviewSelect>>", self._on_user_stats_goalie_select)

            self.user_stats_popup = popup
            self.user_stats_players = players
            self.user_stats_goalies = goalies
            self.user_stats_team_label = team_label
        else:
            self.user_stats_popup.deiconify()
            self.user_stats_popup.lift()
            self.user_stats_popup.focus_force()
        self.refresh_user_stats_window()

    def _on_player_popup_close(self) -> None:
        if self.player_popup is not None:
            self.player_popup.destroy()
        self.player_popup = None
        self.player_popup_summary = None
        self.player_popup_career = None
        self.player_popup_player = None
        self.player_popup_career_map = {}

    def _current_season_row(self, player: Player) -> dict[str, object]:
        return {
            "season": self.simulator.season_number if self.simulator else "-",
            "team": player.team_name,
            "age": player.age,
            "position": player.position,
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
            "__current": True,
        }

    def _summary_rows(self, player: Player, season_row: dict[str, object] | None = None) -> list[tuple[str, str]]:
        is_goalie = player.position == "G"
        if season_row is None:
            draft_label = "Undrafted"
            if player.draft_overall is not None and player.draft_round is not None:
                draft_label = f"S{player.draft_season} R{player.draft_round} #{player.draft_overall} ({player.draft_team})"
            rows: list[tuple[str, str]] = [
                ("Team", player.team_name),
                ("Position", player.position),
                ("Age", str(player.age)),
                ("Season", str(self.simulator.season_number) if self.simulator else "-"),
                ("Draft", draft_label),
                ("Skater GP/G/A/P", f"{player.games_played} / {player.goals} / {player.assists} / {player.points}"),
                ("Injuries / Games Missed / Out", f"{player.injuries} / {player.games_missed_injury} / {player.injured_games_remaining}"),
                ("Ratings SHT/PM/DEF/G/PHY/DUR", f"{player.shooting:.2f} / {player.playmaking:.2f} / {player.defense:.2f} / {player.goaltending:.2f} / {player.physical:.2f} / {player.durability:.2f}"),
            ]
            if is_goalie:
                rows.insert(
                    5,
                    ("Goalie GP / W-L-OTL", f"{player.goalie_games} / {player.goalie_wins}-{player.goalie_losses}-{player.goalie_ot_losses}"),
                )
                rows.insert(6, ("Goalie GAA / SV%", f"{player.gaa:.2f} / {player.save_pct:.3f}"))
            return rows

        draft_text = "Undrafted"
        if season_row.get("draft_overall") is not None and season_row.get("draft_round") is not None:
            draft_text = (
                f"S{season_row.get('draft_season', '-')}"
                f" R{season_row.get('draft_round', '-')}"
                f" #{season_row.get('draft_overall', '-')}"
                f" ({season_row.get('draft_team', '-')})"
            )
        rows = [
            ("Team", str(season_row.get("team", ""))),
            ("Position", str(season_row.get("position", player.position))),
            ("Age", str(season_row.get("age", ""))),
            ("Season", str(season_row.get("season", ""))),
            ("Draft", draft_text),
            ("Skater GP/G/A/P", f"{season_row.get('gp', 0)} / {season_row.get('g', 0)} / {season_row.get('a', 0)} / {season_row.get('p', 0)}"),
            ("Injuries / Games Missed", f"{season_row.get('injuries', 0)} / {season_row.get('games_missed', 0)}"),
            (
                "Ratings SHT/PM/DEF/G/PHY/DUR",
                (
                    f"{season_row.get('rating_shooting', round(player.shooting, 2))} / "
                    f"{season_row.get('rating_playmaking', round(player.playmaking, 2))} / "
                    f"{season_row.get('rating_defense', round(player.defense, 2))} / "
                    f"{season_row.get('rating_goaltending', round(player.goaltending, 2))} / "
                    f"{season_row.get('rating_physical', round(player.physical, 2))} / "
                    f"{season_row.get('rating_durability', round(player.durability, 2))}"
                ),
            ),
        ]
        if is_goalie:
            rows.insert(
                5,
                (
                    "Goalie GP / W-L-OTL",
                    f"{season_row.get('goalie_gp', 0)} / {season_row.get('goalie_w', 0)}-{season_row.get('goalie_l', 0)}-{season_row.get('goalie_otl', 0)}",
                ),
            )
            rows.insert(
                6,
                ("Goalie GAA / SV%", f"{season_row.get('gaa', 0.0)} / {season_row.get('sv_pct', 0.0)}"),
            )
        return rows

    def _render_popup_summary(self, player: Player, season_row: dict[str, object] | None = None) -> None:
        if self.player_popup_summary is None:
            return
        for row in self.player_popup_summary.get_children():
            self.player_popup_summary.delete(row)
        for idx, (stat, value) in enumerate(self._summary_rows(player, season_row)):
            self.player_popup_summary.insert("", tk.END, values=(stat, value), tags=(self._table_row_tag(idx),))

    def on_popup_career_select(self, _event: tk.Event[tk.Misc]) -> None:
        if self.player_popup_career is None or self.player_popup_player is None:
            return
        selection = self.player_popup_career.selection()
        if not selection:
            self._render_popup_summary(self.player_popup_player, None)
            return
        season_row = self.player_popup_career_map.get(selection[0])
        self._render_popup_summary(self.player_popup_player, season_row)

    def _show_player_popup(self, player: Player) -> None:
        title_name = player.name
        is_goalie = player.position == "G"
        recreate = False
        if self.player_popup is not None and self.player_popup.winfo_exists():
            existing_kind = str(self.player_popup_career["columns"])
            goalie_columns = "GGP" in existing_kind
            if goalie_columns != is_goalie:
                recreate = True
        if recreate:
            self._on_player_popup_close()

        if self.player_popup is None or not self.player_popup.winfo_exists():
            popup = tk.Toplevel(self.root)
            popup.title(f"Player Details - {title_name}")
            popup.geometry("1080x620")
            popup.configure(bg=self.palette["bg"])
            popup.transient(self.root)
            popup.protocol("WM_DELETE_WINDOW", self._on_player_popup_close)

            frame = ttk.Frame(popup, padding=10, style="Card.TFrame")
            frame.pack(fill=tk.BOTH, expand=True)

            summary_label = ttk.Label(frame, text="Season Snapshot", style="CardTitle.TLabel")
            summary_label.pack(anchor=tk.W)
            summary = ttk.Treeview(frame, columns=("Stat", "Value"), show="headings", height=11)
            summary.heading("Stat", text="Stat")
            summary.heading("Value", text="Value")
            summary.column("Stat", width=240, anchor=tk.W)
            summary.column("Value", width=800, anchor=tk.W)
            self._apply_table_row_styles(summary)
            summary.pack(fill=tk.X, pady=(0, 10))

            career_label = ttk.Label(frame, text="Career by Season", style="CardTitle.TLabel")
            career_label.pack(anchor=tk.W)
            career_wrap = ttk.Frame(frame)
            career_wrap.pack(fill=tk.BOTH, expand=True)
            career_scroll = ttk.Scrollbar(career_wrap, orient=tk.VERTICAL)
            career_cols = (
                ("Season", "Team", "Age", "Pos", "GP", "G", "A", "P", "Inj", "Missed", "GGP", "W", "L", "OTL", "GAA", "SV%")
                if is_goalie
                else ("Season", "Team", "Age", "Pos", "GP", "G", "A", "P", "Inj", "Missed")
            )
            career = ttk.Treeview(
                career_wrap,
                columns=career_cols,
                show="headings",
            )
            career_layout = [
                ("Season", 70),
                ("Team", 170),
                ("Age", 50),
                ("Pos", 50),
                ("GP", 50),
                ("G", 50),
                ("A", 50),
                ("P", 50),
                ("Inj", 55),
                ("Missed", 70),
            ]
            if is_goalie:
                career_layout.extend(
                    [("GGP", 55), ("W", 50), ("L", 50), ("OTL", 55), ("GAA", 60), ("SV%", 60)]
                )
            for col, width in career_layout:
                career.heading(col, text=col)
                career.column(col, width=width, anchor=tk.CENTER)
            self._apply_table_row_styles(career)
            career.configure(yscrollcommand=career_scroll.set)
            career_scroll.config(command=career.yview)
            career_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            career.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            career.bind("<<TreeviewSelect>>", self.on_popup_career_select)

            self.player_popup = popup
            self.player_popup_summary = summary
            self.player_popup_career = career
        else:
            self.player_popup.title(f"Player Details - {title_name}")
            self.player_popup.deiconify()
            self.player_popup.lift()
            self.player_popup.focus_force()

        self.player_popup_player = player
        self._render_popup_summary(player, None)

        if self.player_popup_career is not None:
            for row in self.player_popup_career.get_children():
                self.player_popup_career.delete(row)
            self.player_popup_career_map.clear()
            current_row = self._current_season_row(player)
            if is_goalie:
                current_values = (
                    f"{current_row.get('season', '')} (Current)",
                    current_row.get("team", ""),
                    current_row.get("age", ""),
                    current_row.get("position", ""),
                    current_row.get("gp", ""),
                    current_row.get("g", ""),
                    current_row.get("a", ""),
                    current_row.get("p", ""),
                    current_row.get("injuries", ""),
                    current_row.get("games_missed", ""),
                    current_row.get("goalie_gp", ""),
                    current_row.get("goalie_w", ""),
                    current_row.get("goalie_l", ""),
                    current_row.get("goalie_otl", ""),
                    current_row.get("gaa", ""),
                    current_row.get("sv_pct", ""),
                )
            else:
                current_values = (
                    f"{current_row.get('season', '')} (Current)",
                    current_row.get("team", ""),
                    current_row.get("age", ""),
                    current_row.get("position", ""),
                    current_row.get("gp", ""),
                    current_row.get("g", ""),
                    current_row.get("a", ""),
                    current_row.get("p", ""),
                    current_row.get("injuries", ""),
                    current_row.get("games_missed", ""),
                )
            current_id = self.player_popup_career.insert("", tk.END, values=current_values, tags=(self._table_row_tag(0),))
            self.player_popup_career_map[current_id] = current_row

            for idx, season in enumerate(player.career_seasons, start=1):
                if is_goalie:
                    values = (
                        season.get("season", ""),
                        season.get("team", ""),
                        season.get("age", ""),
                        season.get("position", ""),
                        season.get("gp", ""),
                        season.get("g", ""),
                        season.get("a", ""),
                        season.get("p", ""),
                        season.get("injuries", ""),
                        season.get("games_missed", ""),
                        season.get("goalie_gp", ""),
                        season.get("goalie_w", ""),
                        season.get("goalie_l", ""),
                        season.get("goalie_otl", ""),
                        season.get("gaa", ""),
                        season.get("sv_pct", ""),
                    )
                else:
                    values = (
                        season.get("season", ""),
                        season.get("team", ""),
                        season.get("age", ""),
                        season.get("position", ""),
                        season.get("gp", ""),
                        season.get("g", ""),
                        season.get("a", ""),
                        season.get("p", ""),
                        season.get("injuries", ""),
                        season.get("games_missed", ""),
                    )
                row = self.player_popup_career.insert("", tk.END, values=values, tags=(self._table_row_tag(idx),))
                self.player_popup_career_map[row] = season

    def _format_playoff_game(self, game_row: dict[str, object]) -> str:
        home = str(game_row.get("home", ""))
        away = str(game_row.get("away", ""))
        home_goals = int(game_row.get("home_goals", 0))
        away_goals = int(game_row.get("away_goals", 0))
        ot = " OT" if game_row.get("overtime") else ""
        return f"G{game_row.get('game', '?')}: {away} {away_goals} at {home} {home_goals}{ot}"

    def _append_playoff_summary(self, playoffs: dict[str, object]) -> None:
        self._append_results("PLAYOFFS:")
        cup_name = str(playoffs.get("cup_name", "Cup"))
        cup_champ = str(playoffs.get("cup_champion", playoffs.get("champion", "")))
        if cup_champ:
            self._append_results(f"  {cup_name} Champion: {cup_champ}")
        for seed in playoffs.get("seeds", []):
            if not isinstance(seed, dict):
                continue
            self._append_results(
                f"  {seed.get('conference', '?')} {seed.get('division', '?')} #{seed.get('seed', '?')}: "
                f"{seed.get('team', '?')} ({seed.get('points', 0)} pts)"
            )

        rounds = playoffs.get("rounds", [])
        for round_row in rounds:
            if not isinstance(round_row, dict):
                continue
            self._append_results(f"  {round_row.get('name', 'Round')}:")
            for series in round_row.get("series", []):
                if not isinstance(series, dict):
                    continue
                self._append_results(
                    f"    {series.get('higher_seed', '?')} vs {series.get('lower_seed', '?')} -> "
                    f"{series.get('winner', '?')} ({series.get('winner_wins', 0)}-{series.get('loser_wins', 0)})"
                )
                for game_row in series.get("games", []):
                    if isinstance(game_row, dict):
                        self._append_results(f"      {self._format_playoff_game(game_row)}")

    def _current_playoff_status_map(self, playoffs: dict[str, object]) -> dict[tuple[str, str, str], dict[str, object]]:
        status: dict[tuple[str, str, str], dict[str, object]] = {}
        rounds = playoffs.get("rounds", [])
        if isinstance(rounds, list):
            for round_row in rounds:
                if not isinstance(round_row, dict):
                    continue
                round_name = str(round_row.get("name", "Round"))
                for series in round_row.get("series", []):
                    if not isinstance(series, dict):
                        continue
                    high = str(series.get("higher_seed", ""))
                    low = str(series.get("lower_seed", ""))
                    key = (round_name, high, low)
                    status[key] = {"high_wins": 0, "low_wins": 0, "winner": ""}

        if self.simulator is None:
            return status

        pending = getattr(self.simulator, "pending_playoff_days", [])
        seen_days = int(getattr(self.simulator, "pending_playoff_day_index", 0))
        if not isinstance(pending, list):
            return status
        for day in pending[:seen_days]:
            if not isinstance(day, dict):
                continue
            round_name = str(day.get("round", "Round"))
            games = day.get("games", [])
            if not isinstance(games, list):
                continue
            for game in games:
                if not isinstance(game, dict):
                    continue
                high = str(game.get("series_higher_seed", ""))
                low = str(game.get("series_lower_seed", ""))
                winner = str(game.get("winner", ""))
                key = (round_name, high, low)
                row = status.setdefault(key, {"high_wins": 0, "low_wins": 0, "winner": ""})
                if winner == high:
                    row["high_wins"] = int(row.get("high_wins", 0)) + 1
                elif winner == low:
                    row["low_wins"] = int(row.get("low_wins", 0)) + 1
                high_wins = int(row.get("high_wins", 0))
                low_wins = int(row.get("low_wins", 0))
                if high_wins >= 4:
                    row["winner"] = high
                elif low_wins >= 4:
                    row["winner"] = low
        return status

    def show_playoff_bracket(self) -> None:
        if self.simulator is None:
            self._append_results("Start a season first.")
            return

        playoffs: dict[str, object] | None = None
        live_mode = False
        if isinstance(self.simulator.pending_playoffs, dict) and self.simulator.pending_playoffs:
            playoffs = self.simulator.pending_playoffs
            live_mode = True
        elif self.simulator.season_history:
            latest = self.simulator.season_history[-1]
            raw = latest.get("playoffs", {})
            if isinstance(raw, dict) and raw:
                playoffs = raw
        if playoffs is None:
            self._append_results("No playoff bracket available yet.")
            return

        if self.bracket_popup is not None and self.bracket_popup.winfo_exists():
            self.bracket_popup.destroy()

        popup = tk.Toplevel(self.root)
        popup.title("Playoff Bracket")
        popup.geometry("1500x900")
        popup.minsize(1200, 700)
        popup.configure(bg=self.palette["bg"])
        popup.transient(self.root)
        self.bracket_popup = popup

        wrap = ttk.Frame(popup, padding=10, style="Card.TFrame")
        wrap.pack(fill=tk.BOTH, expand=True)

        cup_name = str(playoffs.get("cup_name", "Cup"))
        champion = str(playoffs.get("cup_champion", playoffs.get("champion", "")))
        subtitle = "Live bracket (revealed games only)" if live_mode else "Completed bracket"
        ttk.Label(wrap, text=f"{cup_name} Playoff Bracket", style="AppTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(wrap, text=subtitle, style="Muted.TLabel").pack(anchor=tk.W, pady=(2, 8))

        if champion and (not live_mode or self.simulator.playoffs_finished()):
            ttk.Label(wrap, text=f"Champion: {champion}", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 8))

        status_map = self._current_playoff_status_map(playoffs) if live_mode else {}
        rounds = playoffs.get("rounds", [])
        if not isinstance(rounds, list):
            rounds = []
        canvas = tk.Canvas(wrap, bg="#fdfefe", highlightthickness=0)
        x_scroll = ttk.Scrollbar(wrap, orient=tk.HORIZONTAL, command=canvas.xview)
        y_scroll = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(fill=tk.X)

        def _round_stage(round_name: str) -> int:
            name = round_name.lower()
            if "first round" in name or "quarterfinal" in name:
                return 1
            if "division finals" in name or "semifinal" in name:
                return 2
            if "conference final" in name:
                return 3
            if "cup final" in name:
                return 4
            return 9

        def _conference_key(round_name: str) -> str:
            markers = (
                " First Round",
                " Division Finals",
                " Conference Quarterfinal",
                " Conference Semifinal",
                " Conference Final",
            )
            for marker in markers:
                if marker in round_name:
                    return round_name.split(marker)[0].strip()
            return ""

        def _clip_team(name: str, limit: int = 22) -> str:
            if len(name) <= limit:
                return name
            return name[: max(6, limit - 3)].rstrip() + "..."

        def _series_state(round_name: str, series: dict[str, object]) -> tuple[str, str]:
            high = str(series.get("higher_seed", "?"))
            low = str(series.get("lower_seed", "?"))
            if live_mode:
                row = status_map.get((round_name, high, low), {"high_wins": 0, "low_wins": 0, "winner": ""})
                high_w = int(row.get("high_wins", 0))
                low_w = int(row.get("low_wins", 0))
                winner = str(row.get("winner", ""))
                if winner == high:
                    return (f"Final {high_w}-{low_w}", winner)
                if winner == low:
                    return (f"Final {low_w}-{high_w}", winner)
                return (f"Series {high_w}-{low_w}", "")
            winner = str(series.get("winner", "?"))
            ww = int(series.get("winner_wins", 0))
            lw = int(series.get("loser_wins", 0))
            return (f"Final {ww}-{lw}", winner)

        def _draw_series_box(
            x: float,
            y_center: float,
            top: str,
            bottom: str,
            status: str,
            winner: str,
            box_w: int,
            box_h: int,
        ) -> None:
            y0 = y_center - box_h / 2
            y1 = y_center + box_h / 2
            mid = y0 + (box_h / 2)
            top_fill = "#ffffff"
            bottom_fill = "#ffffff"
            border = self.palette["border"]
            if winner == top:
                top_fill = "#eaf6ee"
                border = "#83b892"
            elif winner == bottom:
                bottom_fill = "#eaf6ee"
                border = "#83b892"

            canvas.create_rectangle(x, y0, x + box_w, mid, fill=top_fill, outline="")
            canvas.create_rectangle(x, mid, x + box_w, y1, fill=bottom_fill, outline="")
            canvas.create_rectangle(x, y0, x + box_w, y1, fill="", outline=border, width=2)
            canvas.create_line(x, mid, x + box_w, mid, fill=self.palette["border"])
            top_color = self.palette["accent"] if winner == top else self.palette["text"]
            bottom_color = self.palette["accent"] if winner == bottom else self.palette["text"]
            canvas.create_text(x + 8, y0 + 18, text=_clip_team(top), anchor="w", fill=top_color, font=("Segoe UI Semibold", 10))
            canvas.create_text(x + 8, y0 + 18 + (box_h / 2), text=_clip_team(bottom), anchor="w", fill=bottom_color, font=("Segoe UI Semibold", 10))
            canvas.create_text(x + (box_w / 2), y1 + 12, text=status, anchor="n", fill=self.palette["muted"], font=("Segoe UI", 9))

        def _build_y_positions(count: int, top: int, slot: int) -> list[float]:
            return [top + (slot * i) for i in range(count)]

        conference_rounds: dict[str, list[dict[str, object]]] = {}
        cup_round: dict[str, object] | None = None
        for row in rounds:
            if not isinstance(row, dict):
                continue
            rn = str(row.get("name", "Round"))
            if "cup final" in rn.lower():
                cup_round = row
                continue
            conf = _conference_key(rn)
            if conf:
                conference_rounds.setdefault(conf, []).append(row)

        for conf in conference_rounds:
            conference_rounds[conf].sort(key=lambda r: _round_stage(str(r.get("name", ""))))

        if len(conference_rounds) >= 2 and cup_round is not None:
            conferences = sorted(conference_rounds.keys())
            left_conf = conferences[0]
            right_conf = conferences[1]
            left_cols = conference_rounds[left_conf]
            right_cols = conference_rounds[right_conf]

            box_w = 250
            box_h = 70
            col_gap = 120
            row_slot = 120
            top_y = 140
            left_margin = 60
            max_cols = max(len(left_cols), len(right_cols))
            cup_x = left_margin + max_cols * (box_w + col_gap)
            cup_y = top_y + row_slot * 1.5

            if left_cols and isinstance(left_cols[-1].get("series", []), list):
                left_final_series = left_cols[-1].get("series", [])
                if isinstance(left_final_series, list) and left_final_series:
                    cup_y = _build_y_positions(len(left_final_series), top_y, row_slot * (2 ** (len(left_cols) - 1)))[0]
            if right_cols and isinstance(right_cols[-1].get("series", []), list):
                right_final_series = right_cols[-1].get("series", [])
                if isinstance(right_final_series, list) and right_final_series:
                    right_y = _build_y_positions(len(right_final_series), top_y, row_slot * (2 ** (len(right_cols) - 1)))[0]
                    cup_y = (cup_y + right_y) / 2

            def _draw_side(cols: list[dict[str, object]], side: str, conf_name: str) -> tuple[float, float]:
                prev_centers: list[float] = []
                prev_x: float | None = None
                final_anchor_x = 0.0
                final_anchor_y = cup_y
                for c_idx, col in enumerate(cols):
                    round_name = str(col.get("name", f"Round {c_idx + 1}"))
                    series_rows = col.get("series", [])
                    if not isinstance(series_rows, list):
                        series_rows = []
                    count = max(1, len(series_rows))
                    slot = row_slot * (2 ** c_idx)
                    centers = _build_y_positions(count, top_y, slot)

                    if side == "left":
                        x = left_margin + c_idx * (box_w + col_gap)
                    else:
                        x = cup_x + box_w + (len(cols) - 1 - c_idx) * (box_w + col_gap)

                    if c_idx == 0:
                        canvas.create_text(
                            x + box_w / 2,
                            58,
                            text=f"{conf_name}",
                            anchor="center",
                            fill=self.palette["accent"],
                            font=("Segoe UI Semibold", 11),
                        )
                    canvas.create_text(
                        x + box_w / 2,
                        84,
                        text=round_name,
                        anchor="center",
                        fill=self.palette["muted"],
                        font=("Segoe UI", 9),
                    )

                    for s_idx, series in enumerate(series_rows):
                        if not isinstance(series, dict):
                            continue
                        high = str(series.get("higher_seed", "?"))
                        low = str(series.get("lower_seed", "?"))
                        status, winner = _series_state(round_name, series)
                        cy = centers[s_idx]
                        _draw_series_box(x, cy, high, low, status, winner, box_w, box_h)

                        if c_idx > 0 and prev_x is not None and prev_centers:
                            prev_idx = min(s_idx // 2, len(prev_centers) - 1)
                            py = prev_centers[prev_idx]
                            if side == "left":
                                x1 = prev_x + box_w
                                x2 = x
                                xm = x1 + col_gap / 2
                            else:
                                x1 = prev_x
                                x2 = x + box_w
                                xm = x2 + col_gap / 2
                            canvas.create_line(x1, py, xm, py, fill=self.palette["accent"], width=2)
                            canvas.create_line(xm, py, xm, cy, fill=self.palette["accent"], width=2)
                            canvas.create_line(xm, cy, x2, cy, fill=self.palette["accent"], width=2)

                    prev_centers = centers
                    prev_x = x
                    if c_idx == len(cols) - 1 and centers:
                        if side == "left":
                            final_anchor_x = x + box_w
                        else:
                            final_anchor_x = x
                        final_anchor_y = centers[0]
                return (final_anchor_x, final_anchor_y)

            left_anchor = _draw_side(left_cols, "left", left_conf)
            right_anchor = _draw_side(right_cols, "right", right_conf)

            cup_series_rows = cup_round.get("series", [])
            cup_series = cup_series_rows[0] if isinstance(cup_series_rows, list) and cup_series_rows else {}
            if not isinstance(cup_series, dict):
                cup_series = {}
            cup_top = str(cup_series.get("higher_seed", "?"))
            cup_bottom = str(cup_series.get("lower_seed", "?"))
            cup_status, cup_winner = _series_state(str(cup_round.get("name", "Cup Final")), cup_series)

            canvas.create_text(
                cup_x + box_w / 2,
                58,
                text=str(cup_round.get("name", "Cup Final")),
                anchor="center",
                fill=self.palette["accent"],
                font=("Segoe UI Semibold", 11),
            )
            _draw_series_box(cup_x, cup_y, cup_top, cup_bottom, cup_status, cup_winner, box_w, box_h)

            left_mid_x = cup_x - 38
            right_mid_x = cup_x + box_w + 38
            if left_anchor[0] > 0:
                canvas.create_line(left_anchor[0], left_anchor[1], left_mid_x, left_anchor[1], fill=self.palette["accent"], width=2)
                canvas.create_line(left_mid_x, left_anchor[1], left_mid_x, cup_y, fill=self.palette["accent"], width=2)
                canvas.create_line(left_mid_x, cup_y, cup_x, cup_y, fill=self.palette["accent"], width=2)
            if right_anchor[0] > 0:
                canvas.create_line(right_anchor[0], right_anchor[1], right_mid_x, right_anchor[1], fill=self.palette["accent"], width=2)
                canvas.create_line(right_mid_x, right_anchor[1], right_mid_x, cup_y, fill=self.palette["accent"], width=2)
                canvas.create_line(right_mid_x, cup_y, cup_x + box_w, cup_y, fill=self.palette["accent"], width=2)

            bbox = canvas.bbox("all")
            if bbox is not None:
                canvas.configure(scrollregion=(0, 0, bbox[2] + 80, bbox[3] + 80))
        else:
            box_w = 250
            box_h = 70
            col_gap = 120
            row_gap = 110
            left_margin = 60
            top_y = 120
            prev_centers: list[float] = []
            prev_x: float | None = None
            for idx, round_row in enumerate(rounds):
                if not isinstance(round_row, dict):
                    continue
                round_name = str(round_row.get("name", f"Round {idx + 1}"))
                series_rows = round_row.get("series", [])
                if not isinstance(series_rows, list):
                    series_rows = []
                x = left_margin + idx * (box_w + col_gap)
                canvas.create_text(
                    x + box_w / 2,
                    86,
                    text=round_name,
                    anchor="center",
                    fill=self.palette["accent"],
                    font=("Segoe UI Semibold", 10),
                )
                centers = _build_y_positions(max(1, len(series_rows)), top_y, row_gap * (2 ** idx))
                for s_idx, series in enumerate(series_rows):
                    if not isinstance(series, dict):
                        continue
                    high = str(series.get("higher_seed", "?"))
                    low = str(series.get("lower_seed", "?"))
                    status, winner = _series_state(round_name, series)
                    cy = centers[s_idx]
                    _draw_series_box(x, cy, high, low, status, winner, box_w, box_h)
                    if idx > 0 and prev_x is not None and prev_centers:
                        prev_idx = min(s_idx // 2, len(prev_centers) - 1)
                        py = prev_centers[prev_idx]
                        x1 = prev_x + box_w
                        xm = x1 + col_gap / 2
                        canvas.create_line(x1, py, xm, py, fill=self.palette["accent"], width=2)
                        canvas.create_line(xm, py, xm, cy, fill=self.palette["accent"], width=2)
                        canvas.create_line(xm, cy, x, cy, fill=self.palette["accent"], width=2)
                prev_centers = centers
                prev_x = x
            bbox = canvas.bbox("all")
            if bbox is not None:
                canvas.configure(scrollregion=(0, 0, bbox[2] + 80, bbox[3] + 80))

    def run(self) -> None:
        self.root.mainloop()


def run_gui() -> None:
    HockeySimGUI().run()
