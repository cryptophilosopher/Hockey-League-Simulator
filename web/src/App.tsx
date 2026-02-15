import { useEffect, useMemo, useState } from "react";

type MainNavKey = "home" | "scores" | "team_stats" | "league_stats" | "standings" | "lines" | "franchise";
type StandingsTab = "standings" | "wildcard" | "playoffs";

type Meta = {
  teams: string[];
  team_logos: Record<string, string>;
  conferences: string[];
  divisions: string[];
  strategies: string[];
  user_team: string;
  user_team_logo: string;
  user_strategy: string;
  use_coach: boolean;
  override_coach_for_lines: boolean;
  override_coach_for_strategy: boolean;
  game_mode: "gm" | "coach" | "both";
  user_coach_name: string;
  user_coach_rating: number;
  user_coach_style: string;
  season: number;
  day: number;
  total_days: number;
  in_playoffs: boolean;
};

type StandingRow = {
  team: string;
  logo_url: string;
  conference: string;
  division: string;
  gp: number;
  w: number;
  l: number;
  otl: number;
  pts: number;
  home: string;
  away: string;
  gf: number;
  ga: number;
  diff: number;
  l10: string;
  strk: string;
};

type WildCardRow = {
  kind: "header" | "team" | "cutline";
  label?: string;
  wc?: string;
  team?: string;
  gp?: number;
  w?: number;
  l?: number;
  otl?: number;
  pts?: number;
  diff?: number;
};

type StandingsResponse = {
  mode: string;
  rows?: StandingRow[];
  groups?: Record<string, WildCardRow[]>;
};

type PlayerRow = {
  team: string;
  name: string;
  age: number;
  position: string;
  gp: number;
  g: number;
  a: number;
  p: number;
  plus_minus: number;
  pim: number;
  toi_g: number;
  ppg: number;
  ppa: number;
  shg: number;
  sha: number;
  shots: number;
  shot_pct: number;
};

type GoalieRow = {
  team: string;
  name: string;
  age: number;
  gp: number;
  w: number;
  l: number;
  otl: number;
  gaa: number;
  sv_pct: number;
};

type CareerRow = {
  season: number | string;
  team: string;
  age: number;
  position: string;
  gp: number;
  g: number;
  a: number;
  p: number;
  injuries: number;
  games_missed: number;
  goalie_gp: number;
  goalie_w: number;
  goalie_l: number;
  goalie_otl: number;
  gaa: number;
  sv_pct: number;
  is_current?: boolean;
};

type PlayerCareerPayload = {
  player: {
    team: string;
    name: string;
    age: number;
    position: string;
    draft_label?: string;
  };
  career: CareerRow[];
};

type PlayoffPayload = {
  source: string;
  revealed_days?: number;
  total_days?: number;
  season?: number;
  playoffs?: {
    cup_name?: string;
    champion?: string;
    cup_champion?: string;
    rounds?: Array<{
      name: string;
      series: Array<{
        higher_seed: string;
        lower_seed: string;
        winner?: string;
        winner_wins?: number;
        loser_wins?: number;
      }>;
    }>;
  };
};

type FranchisePayload = {
  team: string;
  cup_count?: number;
  history: Array<{
    season: number;
    gp: number;
    w: number;
    l: number;
    otl: number;
    pts: number;
    conference_rank: number;
    division_rank: number;
    playoff: string;
    playoff_result: string;
    cup_winner: string;
  }>;
  leaders: {
    points: Array<{ name: string; value: number; status: string }>;
    goals: Array<{ name: string; value: number; status: string }>;
    assists: Array<{ name: string; value: number; status: string }>;
    goalie_wins: Array<{ name: string; value: number; status: string }>;
  };
  retired?: Array<{ season: number; entry: string }>;
  draft_picks?: Array<{ season: number; name: string; position: string; round: number; overall: number }>;
};

type AdvanceResponse = {
  phase: string;
  day?: number;
  total_days?: number;
  games?: Array<{
    home: string;
    away: string;
    home_goals: number;
    away_goals: number;
    overtime: boolean;
  }>;
};

type DayBoard = {
  season: number;
  day: number;
  total_days: number;
  completed_days: number;
  phase?: string;
  round?: string;
  status: "played" | "scheduled" | "none";
  games: Array<{
    home: string;
    away: string;
    home_goals?: number;
    away_goals?: number;
    overtime?: boolean;
    home_record?: string;
    away_record?: string;
    home_goalie?: string;
    away_goalie?: string;
    home_goalie_sv?: string;
    away_goalie_sv?: string;
    attendance?: number;
    arena_capacity?: number;
    periods?: Array<{ label: string; home: number; away: number }>;
    commentary?: string[];
    three_stars?: Array<{ label: string; summary: string }>;
  }>;
};

type HomePanel = {
  team: string;
  logo_url: string;
  cup_count?: number;
  season: number;
  day: number;
  team_summary?: {
    record: string;
    division: string;
    division_rank: number;
    points: number;
  };
  coach: {
    name: string;
    rating: number;
    style: string;
    offense: number;
    defense: number;
    goalie_dev: number;
    tenure_seasons: number;
    changes_recent: number;
    honeymoon_games_remaining: number;
  };
  control: {
    user_strategy: string;
    use_coach: boolean;
    override_coach_for_lines: boolean;
    override_coach_for_strategy: boolean;
    game_mode: "gm" | "coach" | "both";
  };
  special_teams?: {
    pp_pct: number;
    pk_pct: number;
  };
  fan_sentiment?: {
    score: number;
    mood: string;
    trend: string;
    summary: string;
  };
  latest_game_day: number | null;
  upcoming_game_day?: number | null;
  upcoming_phase?: string | null;
  upcoming_round?: string | null;
  latest_game: {
    home: string;
    away: string;
    home_goals: number;
    away_goals: number;
    overtime: boolean;
    home_record: string;
    away_record: string;
    home_goalie: string;
    away_goalie: string;
    home_goalie_sv: string;
    away_goalie_sv: string;
    attendance?: number;
    arena_capacity?: number;
    game_day?: number;
    periods?: Array<{ label: string; home: number; away: number }>;
    commentary?: string[];
    three_stars: Array<{ label: string; summary: string }>;
  } | null;
  latest_day_games?: Array<{
    home: string;
    away: string;
    home_goals: number;
    away_goals: number;
    overtime: boolean;
    home_record: string;
    away_record: string;
    home_goalie: string;
    away_goalie: string;
    home_goalie_sv: string;
    away_goalie_sv: string;
    attendance?: number;
    arena_capacity?: number;
    game_day?: number;
    periods?: Array<{ label: string; home: number; away: number }>;
    commentary?: string[];
    three_stars: Array<{ label: string; summary: string }>;
  }>;
  recent_team_games?: Array<{
    home: string;
    away: string;
    home_goals: number;
    away_goals: number;
    overtime: boolean;
    home_record: string;
    away_record: string;
    home_goalie: string;
    away_goalie: string;
    home_goalie_sv: string;
    away_goalie_sv: string;
    attendance?: number;
    arena_capacity?: number;
    game_day?: number;
    periods?: Array<{ label: string; home: number; away: number }>;
    commentary?: string[];
    three_stars?: Array<{ label: string; summary: string }>;
  }>;
  upcoming_game?: {
    home: string;
    away: string;
    game_number?: number;
  } | null;
  playoffs?: {
    active: boolean;
    day?: number;
    total_days?: number;
    latest_team_game_day?: number | null;
    latest_team_game?: {
      home: string;
      away: string;
      home_goals: number;
      away_goals: number;
      overtime: boolean;
      periods?: Array<{ label: string; home: number; away: number }>;
      commentary?: string[];
      round?: string;
      game_number?: number;
      winner?: string;
      home_record?: string;
      away_record?: string;
      home_goalie?: string;
      away_goalie?: string;
      home_goalie_sv?: string;
      away_goalie_sv?: string;
      attendance?: number;
      three_stars?: Array<{ label: string; summary: string }>;
    } | null;
  };
};

type CoachCandidate = {
  name: string;
  rating: number;
  style: string;
  offense: number;
  defense: number;
  goalie_dev: number;
  w: number;
  l: number;
  otl: number;
  cups: number;
  source: string;
};

type LinesPayload = {
  team: string;
  coach: { name: string; rating: number; style: string };
  override_coach_for_lines: boolean;
  position_penalty: number;
  assignments: Record<string, string>;
  units: Array<{
    unit: string;
    LW: { name: string; pos: string; out_of_position?: boolean } | null;
    C: { name: string; pos: string; out_of_position?: boolean } | null;
    RW: { name: string; pos: string; out_of_position?: boolean } | null;
    LD: { name: string; pos: string; out_of_position?: boolean } | null;
    RD: { name: string; pos: string; out_of_position?: boolean } | null;
    G: { name: string; pos: string; out_of_position?: boolean } | null;
  }>;
  candidates: Array<{ name: string; pos: string }>;
};

const API_BASE = "http://127.0.0.1:8000/api";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as T;
}

function logoUrl(path: string) {
  return `http://127.0.0.1:8000${path}`;
}

export default function App() {
  const [mainNav, setMainNav] = useState<MainNavKey>("standings");
  const [standingsTab, setStandingsTab] = useState<StandingsTab>("standings");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [standingsMode, setStandingsMode] = useState<"league" | "conference" | "division">("division");
  const [rows, setRows] = useState<StandingRow[]>([]);
  const [groupRows, setGroupRows] = useState<Record<string, StandingRow[]>>({});
  const [wildGroups, setWildGroups] = useState<Record<string, WildCardRow[]>>({});
  const [players, setPlayers] = useState<PlayerRow[]>([]);
  const [goalies, setGoalies] = useState<GoalieRow[]>([]);
  const [playoffs, setPlayoffs] = useState<PlayoffPayload | null>(null);
  const [franchise, setFranchise] = useState<FranchisePayload | null>(null);
  const [homePanel, setHomePanel] = useState<HomePanel | null>(null);
  const [scoreDay, setScoreDay] = useState(0);
  const [scoreBoard, setScoreBoard] = useState<DayBoard | null>(null);
  const [playerCareer, setPlayerCareer] = useState<PlayerCareerPayload | null>(null);
  const [coachCandidates, setCoachCandidates] = useState<CoachCandidate[]>([]);
  const [selectedCoachName, setSelectedCoachName] = useState("");
  const [showCoachModal, setShowCoachModal] = useState(false);
  const [linesData, setLinesData] = useState<LinesPayload | null>(null);
  const [lineAssignments, setLineAssignments] = useState<Record<string, string>>({});
  const [gameModeLocal, setGameModeLocal] = useState<"gm" | "coach" | "both">("both");
  const [loading, setLoading] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const [error, setError] = useState("");

  const summary = useMemo(() => {
    if (!meta) return "Loading...";
    if (mainNav === "scores" && scoreBoard) {
      const label = scoreBoard.phase === "playoffs"
        ? `Playoffs${scoreBoard.round ? ` - ${scoreBoard.round}` : ""}`
        : "Regular Season";
      return `Season ${scoreBoard.season} Day ${scoreBoard.day}/${scoreBoard.total_days} | ${label}`;
    }
    return `Season ${meta.season} Day ${meta.day}/${meta.total_days}${meta.in_playoffs ? " | Playoffs" : ""}`;
  }, [meta, mainNav, scoreBoard]);

  async function loadMeta() {
    const m = await fetchJson<Meta>("/meta");
    setMeta(m);
    setGameModeLocal(m.game_mode);
    return m;
  }

  async function loadStandings(mode = standingsMode, metaSnapshot: Meta | null = meta) {
    if (mode === "league") {
      const s = await fetchJson<StandingsResponse>("/standings?mode=league");
      setRows(s.rows ?? []);
      setGroupRows({});
      return;
    }
    if (!metaSnapshot) return;
    const values = mode === "conference" ? metaSnapshot.conferences : metaSnapshot.divisions;
    const entries = await Promise.all(
      values.map(async (value) => {
        const s = await fetchJson<StandingsResponse>(`/standings?mode=${mode}&value=${encodeURIComponent(value)}`);
        return [value, s.rows ?? []] as const;
      }),
    );
    setRows([]);
    setGroupRows(Object.fromEntries(entries));
  }

  async function loadWildCard() {
    const data = await fetchJson<StandingsResponse>("/standings?mode=wildcard");
    setWildGroups(data.groups ?? {});
  }

  async function loadLeaders(scope: "league" | "team") {
    const teamQuery = scope === "team" ? `&team=${encodeURIComponent(meta?.user_team ?? "")}` : "";
    const [p, g] = await Promise.all([
      fetchJson<PlayerRow[]>(`/players?scope=${scope}${teamQuery}`),
      fetchJson<GoalieRow[]>(`/goalies?scope=${scope}${teamQuery}`),
    ]);
    setPlayers(p);
    setGoalies(g);
  }

  async function loadPlayoffs() {
    setPlayoffs(await fetchJson<PlayoffPayload>("/playoffs"));
  }

  async function loadFranchise() {
    if (!meta?.user_team) return;
    setFranchise(await fetchJson<FranchisePayload>(`/franchise?team=${encodeURIComponent(meta.user_team)}`));
  }

  async function loadHome() {
    setHomePanel(await fetchJson<HomePanel>("/home"));
  }

  async function loadLines() {
    if (!meta?.user_team) return;
    const payload = await fetchJson<LinesPayload>(`/lines?team=${encodeURIComponent(meta.user_team)}`);
    setLinesData(payload);
    setLineAssignments(payload.assignments ?? {});
  }

  async function loadDayBoards(sDay = scoreDay) {
    const scores = await fetchJson<DayBoard>(`/day-board?day=${sDay}`);
    setScoreBoard(scores);
  }

  async function refreshAll() {
    setLoading(true);
    setError("");
    try {
      const m = await loadMeta();
      const scoreTarget = scoreDay > 0 ? scoreDay : 0;
      const leaderTarget = mainNav === "team_stats" ? "team" : "league";
      await Promise.all([
        loadStandings(standingsMode, m),
        loadWildCard(),
        loadLeaders(leaderTarget),
        loadPlayoffs(),
        loadFranchise(),
        loadHome(),
        loadDayBoards(scoreTarget),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function openPlayerCareer(team: string, name: string) {
    try {
      const data = await fetchJson<PlayerCareerPayload>(
        `/player-career?team=${encodeURIComponent(team)}&name=${encodeURIComponent(name)}`,
      );
      setPlayerCareer(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function setUserTeam(teamName: string) {
    await fetchJson("/user-team", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_name: teamName }),
    });
    await refreshAll();
  }

  async function setCoachSettings(strategy: string, overrideCoachForStrategy: boolean) {
    await fetchJson("/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy, override_coach_for_strategy: overrideCoachForStrategy }),
    });
    await refreshAll();
  }

  async function setControlOverrides(overrideCoachForLines: boolean, overrideCoachForStrategy: boolean) {
    await fetchJson("/control-overrides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        override_coach_for_lines: overrideCoachForLines,
        override_coach_for_strategy: overrideCoachForStrategy,
      }),
    });
    await refreshAll();
  }

  async function saveLines() {
    await fetchJson("/lines", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assignments: lineAssignments }),
    });
    await loadLines();
    await loadHome();
  }

  async function loadCoachCandidates() {
    const rows = await fetchJson<CoachCandidate[]>("/coach-candidates");
    setCoachCandidates(rows);
    if (rows.length > 0) setSelectedCoachName(rows[0].name);
  }

  async function fireCoach(hireName?: string) {
    const q = hireName ? `?hire=${encodeURIComponent(hireName)}` : "";
    await fetchJson(`/fire-coach${q}`, { method: "POST" });
    setShowCoachModal(false);
    await refreshAll();
  }

  async function resetLeague() {
    await fetchJson("/reset", { method: "POST" });
    setScoreDay(0);
    await refreshAll();
  }

  async function setGameMode(mode: "gm" | "coach" | "both") {
      await fetchJson("/game-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
    setGameModeLocal(mode);
    await refreshAll();
  }

  async function advanceDay() {
    setSimBusy(true);
    setError("");
    try {
      await fetchJson<AdvanceResponse>("/advance", { method: "POST" });
      setScoreDay(0);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSimBusy(false);
    }
  }

  useEffect(() => {
    void refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!meta) return;
    void loadStandings(standingsMode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [standingsMode, meta?.conferences.join(","), meta?.divisions.join(",")]);

  useEffect(() => {
    if (scoreDay >= 0) void loadDayBoards(scoreDay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scoreDay]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          {meta?.user_team_logo ? <img className="team-logo" src={logoUrl(meta.user_team_logo)} alt={meta.user_team} /> : null}
          <div>
            <h1>Hockey Sim Web</h1>
            <p>{summary}</p>
          </div>
        </div>
        <div className="actions">
          <select value={meta?.user_team ?? ""} onChange={(e) => void setUserTeam(e.target.value)} disabled={!meta}>
            {(meta?.teams ?? []).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            value={meta?.user_strategy ?? "balanced"}
            onChange={(e) => void setCoachSettings(e.target.value, meta?.override_coach_for_strategy ?? false)}
            disabled={!meta || !(meta.override_coach_for_strategy ?? false)}
          >
            {(meta?.strategies ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={meta?.override_coach_for_lines ?? false}
              onChange={(e) => void setControlOverrides(e.target.checked, meta?.override_coach_for_strategy ?? false)}
              disabled={!meta}
            />
            Override Coach For Lines
          </label>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={meta?.override_coach_for_strategy ?? false}
              onChange={(e) => void setControlOverrides(meta?.override_coach_for_lines ?? false, e.target.checked)}
              disabled={!meta}
            />
            Override Coach For Strategy
          </label>
          <select
            value={meta?.game_mode ?? gameModeLocal}
            onChange={(e) => void setGameMode(e.target.value as "gm" | "coach" | "both")}
            disabled={!meta}
          >
            <option value="gm">GM</option>
            <option value="coach">Coach</option>
            <option value="both">Both</option>
          </select>
          <button
            onClick={() => {
              void loadCoachCandidates();
              setShowCoachModal(true);
            }}
            disabled={!meta || meta.game_mode === "coach"}
          >
            Fire Coach
          </button>
          <button onClick={() => void advanceDay()} disabled={simBusy || loading}>
            {simBusy ? "Simulating..." : "Sim Next Day"}
          </button>
          <button
            className="reset-btn"
            onClick={() => {
              if (window.confirm("Reset saved season history and restart from Season 1?")) void resetLeague();
            }}
            disabled={loading || simBusy}
          >
            Reset
          </button>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <nav className="top-nav">
        {[
          ["home", "Home"],
          ["scores", "Scores"],
          ["team_stats", "Team Stats"],
          ["league_stats", "League Stats"],
          ["standings", "Standings"],
          ["lines", "Lines"],
          ["franchise", "Franchise"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={mainNav === key ? "top-nav-btn active" : "top-nav-btn"}
            onClick={() => {
              if (key === "scores") setScoreDay(0);
              if (key === "team_stats") void loadLeaders("team");
              if (key === "league_stats") void loadLeaders("league");
              if (key === "lines") void loadLines();
              setMainNav(key as MainNavKey);
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {mainNav === "standings" ? (
        <>
          <nav className="tabs">
            {[
              ["standings", "Standings"],
              ["wildcard", "Wild Card"],
              ["playoffs", "Playoffs"],
            ].map(([key, label]) => (
              <button key={key} className={standingsTab === key ? "tab active" : "tab"} onClick={() => setStandingsTab(key as StandingsTab)}>
                {label}
              </button>
            ))}
          </nav>

          {standingsTab === "standings" ? (
            <section className="card standings">
              <div className="section-head">
                <h2>Standings</h2>
                <div className="inline-controls">
                  <select value={standingsMode} onChange={(e) => setStandingsMode(e.target.value as "league" | "conference" | "division")}>
                    <option value="league">League</option>
                    <option value="conference">Conference</option>
                    <option value="division">Division</option>
                  </select>
                </div>
              </div>
              {standingsMode === "league" ? (
                <StandingsTable rows={rows} />
              ) : (
                <div className="standings-scroll">
                  {Object.entries(groupRows).map(([group, list]) => (
                    <div key={group} className="standings-group">
                      <h3>{group}</h3>
                      <StandingsTable rows={list} />
                    </div>
                  ))}
                </div>
              )}
            </section>
          ) : null}

          {standingsTab === "wildcard" ? (
            <section className="card standings">
              <h2>Wild Card</h2>
              {Object.entries(wildGroups).map(([conference, wr]) => (
                <div key={conference} className="wc-group">
                  <h3>{conference}</h3>
                  <table>
                    <thead>
                      <tr>
                        <th>Team</th>
                        <th>GP</th>
                        <th>W</th>
                        <th>L</th>
                        <th>OTL</th>
                        <th>PTS</th>
                        <th>DIFF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {wr.map((r, idx) => {
                        if (r.kind === "header") return <tr key={`${conference}-h-${idx}`} className="group-header"><td colSpan={7}>{r.label}</td></tr>;
                        if (r.kind === "cutline") return <tr key={`${conference}-c-${idx}`} className="group-cutline"><td colSpan={7}>{r.label}</td></tr>;
                        return (
                          <tr key={`${conference}-t-${r.team}-${idx}`}>
                            <td>{r.wc ? `${r.wc} ${r.team}` : r.team}</td>
                            <td>{r.gp}</td><td>{r.w}</td><td>{r.l}</td><td>{r.otl}</td><td>{r.pts}</td>
                            <td className={(r.diff ?? 0) > 0 ? "pos" : (r.diff ?? 0) < 0 ? "neg" : ""}>{(r.diff ?? 0) > 0 ? `+${r.diff}` : r.diff}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </section>
          ) : null}

          {standingsTab === "playoffs" ? (
            <section className="card">
              <h2>Playoff Bracket</h2>
              {playoffs?.source === "none" ? <p>No playoff data yet.</p> : null}
              {playoffs?.playoffs?.rounds?.map((round) => (
                <div key={round.name} className="round-card">
                  <h3>{round.name}</h3>
                  {round.series.map((s, idx) => (
                    <div key={`${round.name}-${idx}`} className="series-row">
                      <span>{s.higher_seed}</span><span>vs</span><span>{s.lower_seed}</span>
                      <span className="series-result">{s.winner ? `${s.winner} (${s.winner_wins}-${s.loser_wins})` : "In Progress"}</span>
                    </div>
                  ))}
                </div>
              ))}
            </section>
          ) : null}
        </>
      ) : null}

      {mainNav === "league_stats" ? (
        <section className="card leaders">
          <div className="section-head">
            <h2>League Stats</h2>
          </div>
          <div className="leaders-grid">
            <div>
              <h3>Skating Leaders</h3>
              <LeaderBlock
                title="Points"
                valueLabel="PTS"
                rows={players}
                getValue={(p) => p.p}
                formatValue={(v) => `${v}`}
                onPick={(p) => void openPlayerCareer(p.team, p.name)}
              />
              <LeaderBlock
                title="Goals"
                valueLabel="G"
                rows={players}
                getValue={(p) => p.g}
                formatValue={(v) => `${v}`}
                onPick={(p) => void openPlayerCareer(p.team, p.name)}
              />
              <LeaderBlock
                title="Plus/Minus"
                valueLabel="+/-"
                rows={players}
                getValue={(p) => p.plus_minus}
                formatValue={(v) => `${v}`}
                onPick={(p) => void openPlayerCareer(p.team, p.name)}
              />
            </div>
            <div>
              <h3>Goaltending Leaders</h3>
              <LeaderBlock
                title="Goals Against Avg"
                valueLabel="GAA"
                rows={goalies}
                getValue={(g) => g.gaa}
                sortAsc
                formatValue={(v) => Number(v).toFixed(2)}
                onPick={(g) => void openPlayerCareer(g.team, g.name)}
              />
              <LeaderBlock
                title="Save Percentage"
                valueLabel="SVPCT"
                rows={goalies}
                getValue={(g) => g.sv_pct}
                formatValue={(v) => Number(v).toFixed(3).replace(/^0/, "")}
                onPick={(g) => void openPlayerCareer(g.team, g.name)}
              />
              <LeaderBlock
                title="Wins"
                valueLabel="W"
                rows={goalies}
                getValue={(g) => g.w}
                formatValue={(v) => `${v}`}
                onPick={(g) => void openPlayerCareer(g.team, g.name)}
              />
            </div>
          </div>
        </section>
      ) : null}

      {mainNav === "team_stats" ? (
        <section className="card leaders">
          <div className="section-head">
            <h2>{meta?.user_team ?? "My Team"} Stats</h2>
          </div>
          <div className="split">
            <div><h3>Skaters</h3><table><thead><tr><th>Player</th><th>Pos</th><th>GP</th><th>G</th><th>A</th><th>P</th><th>+/-</th><th>PIM</th><th>TOI/G</th><th>PPG</th><th>PPA</th><th>SHG</th><th>SHA</th><th>S</th><th>S%</th></tr></thead><tbody>
              {players.map((p) => (
                <tr key={`${p.team}-${p.name}`} className="row-clickable" onClick={() => void openPlayerCareer(p.team, p.name)}>
                  <td>{p.name}</td><td>{p.position}</td><td>{p.gp}</td><td>{p.g}</td><td>{p.a}</td><td>{p.p}</td><td>{p.plus_minus}</td><td>{p.pim}</td><td>{p.toi_g.toFixed(1)}</td><td>{p.ppg}</td><td>{p.ppa}</td><td>{p.shg}</td><td>{p.sha}</td><td>{p.shots}</td><td>{p.shot_pct.toFixed(1)}</td>
                </tr>
              ))}
            </tbody></table></div>
            <div><h3>Goalies</h3><table><thead><tr><th>Goalie</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>GAA</th><th>SV%</th></tr></thead><tbody>
              {goalies.map((g) => (
                <tr key={`${g.team}-${g.name}`} className="row-clickable" onClick={() => void openPlayerCareer(g.team, g.name)}>
                  <td>{g.name}</td><td>{g.gp}</td><td>{g.w}</td><td>{g.l}</td><td>{g.otl}</td><td>{g.gaa.toFixed(2)}</td><td>{g.sv_pct.toFixed(3)}</td>
                </tr>
              ))}
            </tbody></table></div>
          </div>
        </section>
      ) : null}

      {mainNav === "scores" ? (
        <section className="card">
          <div className="section-head">
            <h2>Scoreboard</h2>
            <div className="inline-controls">
              <button
                onClick={() =>
                  setScoreDay((d) =>
                    Math.max(scoreBoard?.completed_days ?? 1, (scoreBoard?.day ?? (d > 0 ? d : 1)) - 1),
                  )
                }
                disabled={(scoreBoard?.day ?? 1) <= (scoreBoard?.completed_days ?? 1)}
              >
                Prev
              </button>
              <span className="muted">Day {scoreBoard?.day ?? "-"}</span>
              <button onClick={() => setScoreDay((d) => Math.min(scoreBoard?.total_days ?? (d > 0 ? d : 1), (scoreBoard?.day ?? (d > 0 ? d : 1)) + 1))}>Next</button>
              <button onClick={() => setScoreDay(0)}>Latest</button>
            </div>
          </div>
          <p className="muted">
            Season {scoreBoard?.season ?? "-"} | {scoreBoard?.phase === "playoffs" ? `Playoffs${scoreBoard?.round ? ` - ${scoreBoard.round}` : ""}` : "Regular Season"} | {scoreBoard?.status === "played" ? "Most Recent Finals" : "Scheduled Games"}
          </p>
          <div className="score-list">
            {(scoreBoard?.games ?? []).map((g, idx) => (
              <GameSummaryCard
                key={`score-${idx}`}
                game={g}
                teamLogos={meta?.team_logos}
                showCommentary={false}
                showTeamLabels={false}
              />
            ))}
          </div>
        </section>
      ) : null}

      {mainNav === "lines" ? (
        <section className="card">
          <h2>{linesData?.team ?? (meta?.user_team ?? "Team")} Lines</h2>
          <p className="muted">
            Coach: {linesData?.coach.name ?? "-"} ({linesData ? linesData.coach.rating.toFixed(2) : "-"}, {linesData?.coach.style ?? "-"})
          </p>
          <p className="muted">
            Position Penalty: {(linesData?.position_penalty ?? 0).toFixed(3)} | {linesData?.override_coach_for_lines ? "Manual Lines Enabled" : "Coach Controls Lines"}
          </p>
          {linesData?.override_coach_for_lines ? (
            <div className="inline-controls">
              <button onClick={() => void saveLines()} disabled={!linesData}>Save Lines</button>
              <button onClick={() => void loadLines()} disabled={!linesData}>Reset To Current</button>
            </div>
          ) : null}
          <h3>Line Combinations</h3>
          <table>
            <thead>
              <tr>
                <th>Unit</th>
                <th>LW</th>
                <th>C</th>
                <th>RW</th>
                <th>LD</th>
                <th>RD</th>
                <th>G</th>
              </tr>
            </thead>
            <tbody>
              {(linesData?.units ?? []).map((unit, idx) => {
                const slotId = (col: "LW" | "C" | "RW" | "LD" | "RD" | "G") => {
                  if (col === "LD" || col === "RD") return idx < 3 ? `${col}${idx + 1}` : "";
                  if (col === "G") return idx < 2 ? `G${idx + 1}` : "";
                  return `${col}${idx + 1}`;
                };
                const renderCell = (col: "LW" | "C" | "RW" | "LD" | "RD" | "G", item: { name: string; pos: string; out_of_position?: boolean } | null) => {
                  const id = slotId(col);
                  if (!id) return "-";
                  if (!(linesData?.override_coach_for_lines ?? false)) {
                    if (!item) return "-";
                    return (
                      <span className={item.out_of_position ? "neg" : ""}>
                        {item.name} ({item.pos})
                      </span>
                    );
                  }
                  return (
                    <select
                      value={lineAssignments[id] ?? ""}
                      onChange={(e) => setLineAssignments((prev) => ({ ...prev, [id]: e.target.value }))}
                    >
                      <option value="">-</option>
                      {(linesData?.candidates ?? []).map((c) => (
                        <option key={`${id}-${c.name}`} value={c.name}>
                          {c.name} ({c.pos})
                        </option>
                      ))}
                    </select>
                  );
                };
                return (
                  <tr key={`unit-${idx}`}>
                    <td>{unit.unit}</td>
                    <td>{renderCell("LW", unit.LW)}</td>
                    <td>{renderCell("C", unit.C)}</td>
                    <td>{renderCell("RW", unit.RW)}</td>
                    <td>{renderCell("LD", unit.LD)}</td>
                    <td>{renderCell("RD", unit.RD)}</td>
                    <td>{renderCell("G", unit.G)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ) : null}

      {mainNav === "franchise" ? (
        <section className="card franchise">
          <h2>
            {meta?.user_team ?? "Team"} Franchise
            <span className="cup-badges">{Array.from({ length: franchise?.cup_count ?? 0 }).map((_, i) => <span key={`fc-${i}`}>🏆</span>)}</span>
          </h2>
          {franchise ? (
            <>
              <h3>Season History</h3>
              <table><thead><tr><th>Season</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>Pts</th><th>Conf Rank</th><th>Div Rank</th><th>Playoff</th><th>Playoff Result</th><th>Cup</th></tr></thead>
                <tbody>{franchise.history.map((h) => <tr key={`h-${h.season}`}><td>{h.season}</td><td>{h.gp}</td><td>{h.w}</td><td>{h.l}</td><td>{h.otl}</td><td>{h.pts}</td><td>{h.conference_rank}</td><td>{h.division_rank}</td><td>{h.playoff}</td><td>{h.playoff_result}</td><td>{h.cup_winner}</td></tr>)}</tbody>
              </table>
              <div className="split">
                <div>
                  <h3>Draft Results</h3>
                  <table>
                    <thead><tr><th>Season</th><th>Player</th><th>Pos</th><th>Pick</th></tr></thead>
                    <tbody>
                      {(franchise.draft_picks ?? []).slice(0, 30).map((d, idx) => (
                        <tr key={`d-${idx}-${d.season}-${d.name}`}>
                          <td>{d.season}</td><td>{d.name}</td><td>{d.position}</td><td>R{d.round} #{d.overall}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <h3>Retired Players</h3>
                  <table>
                    <thead><tr><th>Season</th><th>Player</th></tr></thead>
                    <tbody>
                      {(franchise.retired ?? []).slice(0, 30).map((r, idx) => (
                        <tr key={`r-${idx}-${r.season}-${r.entry}`}>
                          <td>{r.season}</td><td>{r.entry}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : <p>Loading franchise data...</p>}
        </section>
      ) : null}

      {mainNav === "home" ? (
        <section className="card">
          <h2>
            {homePanel?.team ?? meta?.user_team ?? "Team"} Home
            <span className="cup-badges">{Array.from({ length: homePanel?.cup_count ?? 0 }).map((_, i) => <span key={`hc-${i}`}>🏆</span>)}</span>
          </h2>
          <p className="muted">
            Record {homePanel?.team_summary?.record ?? "-"} | {homePanel?.team_summary?.division ?? "-"} Division: {homePanel?.team_summary?.division_rank ?? "-"} place | {homePanel?.team_summary?.points ?? 0} pts
          </p>
          {homePanel ? (
            <div className="split">
              <div>
                <h3>Latest Team Game</h3>
                {homePanel.latest_game ? (
                  <>
                    <GameSummaryCard game={homePanel.latest_game} teamLogos={meta?.team_logos} />
                    <p className="muted">
                      Day {homePanel.latest_game_day} | {homePanel.latest_game.away} {homePanel.latest_game.away_goals} at {homePanel.latest_game.home} {homePanel.latest_game.home_goals}
                      {homePanel.latest_game.overtime ? " (OT)" : ""}
                    </p>
                    {(homePanel.recent_team_games ?? []).length > 0 ? (
                      <div>
                        <h3>Recent Team Games</h3>
                        <div className="score-list">
                          {(homePanel.recent_team_games ?? [])
                            .filter(
                              (g) =>
                                !homePanel.latest_game
                                || g.home !== homePanel.latest_game.home
                                || g.away !== homePanel.latest_game.away
                                || g.home_goals !== homePanel.latest_game.home_goals
                                || g.away_goals !== homePanel.latest_game.away_goals,
                            )
                            .map((g, idx) => (
                            <div key={`home-day-${idx}-${g.away}-${g.home}`}>
                              <p className="muted">Day {g.game_day ?? "-"}</p>
                              <GameSummaryCard game={g} teamLogos={meta?.team_logos} />
                            </div>
                            ))}
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
                {homePanel.playoffs?.active && homePanel.playoffs.latest_team_game ? (
                  <div>
                    <h3>Latest Playoff Result</h3>
                    <p className="muted">
                      Playoff Day {homePanel.playoffs.latest_team_game_day ?? "-"} / {homePanel.playoffs.total_days ?? "-"}
                      {homePanel.playoffs.latest_team_game.round ? ` | ${homePanel.playoffs.latest_team_game.round}` : ""}
                      {homePanel.playoffs.latest_team_game.game_number ? ` | Game ${homePanel.playoffs.latest_team_game.game_number}` : ""}
                    </p>
                    <GameSummaryCard game={homePanel.playoffs.latest_team_game} teamLogos={meta?.team_logos} />
                  </div>
                ) : null}
                {homePanel.upcoming_game ? (
                  <div>
                    <h3>Upcoming Game</h3>
                    <p className="muted">
                      {homePanel.upcoming_phase === "playoffs" ? "Playoff" : "Regular"} Day {homePanel.upcoming_game_day ?? "-"}
                      {homePanel.upcoming_round ? ` | ${homePanel.upcoming_round}` : ""}
                      {homePanel.upcoming_game.game_number ? ` | Game ${homePanel.upcoming_game.game_number}` : ""}
                    </p>
                    <div className="score-card">
                      <div className="score-main">
                        <div className="score-team-row">
                          {meta?.team_logos?.[homePanel.upcoming_game.away] ? <img className="mini-logo" src={logoUrl(meta.team_logos[homePanel.upcoming_game.away])} alt={homePanel.upcoming_game.away} /> : null}
                          <span>{homePanel.upcoming_game.away}</span>
                        </div>
                        <div className="score-team-row">
                          {meta?.team_logos?.[homePanel.upcoming_game.home] ? <img className="mini-logo" src={logoUrl(meta.team_logos[homePanel.upcoming_game.home])} alt={homePanel.upcoming_game.home} /> : null}
                          <span>{homePanel.upcoming_game.home}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
              <div>
                <h3>Coach</h3>
                <p className="muted">{homePanel.coach.name}</p>
                <p className="muted">Rating {homePanel.coach.rating.toFixed(2)} | Style {homePanel.coach.style}</p>
                <p className="muted">
                  Off {homePanel.coach.offense.toFixed(2)} | Def {homePanel.coach.defense.toFixed(2)} | Goalie Dev {homePanel.coach.goalie_dev.toFixed(2)}
                </p>
                <p className="muted">
                  Strategy: {homePanel.control.user_strategy} | Override Lines: {homePanel.control.override_coach_for_lines ? "On" : "Off"} | Override Strategy: {homePanel.control.override_coach_for_strategy ? "On" : "Off"}
                </p>
                <p className="muted">
                  Game Mode: {homePanel.control.game_mode.toUpperCase()} | PP% {(homePanel.special_teams?.pp_pct ?? 0).toFixed(3)} | PK% {(homePanel.special_teams?.pk_pct ?? 0).toFixed(3)}
                </p>
                <p className="muted">
                  Fan Sentiment: {homePanel.fan_sentiment?.score?.toFixed(1) ?? "-"} / 100 ({homePanel.fan_sentiment?.mood ?? "Unknown"}, {homePanel.fan_sentiment?.trend ?? "Flat"})
                </p>
                <p className="muted">{homePanel.fan_sentiment?.summary ?? ""}</p>
              </div>
            </div>
          ) : (
            <p>Loading home details...</p>
          )}
        </section>
      ) : null}

      {showCoachModal ? (
        <div className="modal-overlay" onClick={() => setShowCoachModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Hire Coach</h3>
            <div className="inline-controls">
              <select value={selectedCoachName} onChange={(e) => setSelectedCoachName(e.target.value)}>
                {coachCandidates.map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
              <button onClick={() => void fireCoach(selectedCoachName)} disabled={!selectedCoachName}>Hire Selected</button>
              <button onClick={() => setShowCoachModal(false)}>Cancel</button>
            </div>
            <div className="modal-lines">
              <table>
                <thead><tr><th>Coach</th><th>Rating</th><th>Style</th><th>W-L-OTL</th><th>Cups</th><th>Source</th></tr></thead>
                <tbody>
                  {coachCandidates.map((c) => (
                    <tr key={`coach-${c.name}`} className={selectedCoachName === c.name ? "row-clickable" : ""} onClick={() => setSelectedCoachName(c.name)}>
                      <td>{c.name}</td><td>{c.rating.toFixed(2)}</td><td>{c.style}</td><td>{c.w}-{c.l}-{c.otl}</td><td>{c.cups}</td><td>{c.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}

      {playerCareer ? (
        <div className="modal-overlay" onClick={() => setPlayerCareer(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>{playerCareer.player.name}</h3>
            <p className="muted">
              Position: {playerCareer.player.position} | Team: {playerCareer.player.team} | Draft: {playerCareer.player.draft_label ?? "Undrafted"}
            </p>
            <div className="modal-lines">
              <table>
                <thead>
                  <tr>
                    <th>Season</th><th>Team</th><th>Age</th><th>Pos</th><th>GP</th><th>G</th><th>A</th><th>P</th><th>Inj</th><th>Missed</th><th>GGP</th><th>W</th><th>L</th><th>OTL</th><th>GAA</th><th>SV%</th>
                  </tr>
                </thead>
                <tbody>
                  {playerCareer.career.map((row, idx) => (
                    <tr key={`${playerCareer.player.team}-${playerCareer.player.name}-${row.season}-${idx}`}>
                      <td>{row.is_current ? `${row.season} (Current)` : row.season}</td>
                      <td>{row.team}</td>
                      <td>{row.age}</td>
                      <td>{row.position}</td>
                      <td>{row.gp}</td>
                      <td>{row.g}</td>
                      <td>{row.a}</td>
                      <td>{row.p}</td>
                      <td>{row.injuries}</td>
                      <td>{row.games_missed}</td>
                      <td>{row.goalie_gp}</td>
                      <td>{row.goalie_w}</td>
                      <td>{row.goalie_l}</td>
                      <td>{row.goalie_otl}</td>
                      <td>{Number(row.gaa ?? 0).toFixed(2)}</td>
                      <td>{Number(row.sv_pct ?? 0).toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button onClick={() => setPlayerCareer(null)}>Close</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function GameSummaryCard({
  game,
  teamLogos,
  showCommentary = true,
  showTeamLabels = true,
}: {
  game: {
    home: string;
    away: string;
    home_goals?: number;
    away_goals?: number;
    overtime?: boolean;
    home_record?: string;
    away_record?: string;
    home_goalie?: string;
    away_goalie?: string;
    home_goalie_sv?: string;
    away_goalie_sv?: string;
    attendance?: number;
    arena_capacity?: number;
    periods?: Array<{ label: string; home: number; away: number }>;
    commentary?: string[];
    three_stars?: Array<{ label: string; summary: string }>;
  };
  teamLogos?: Record<string, string>;
  showCommentary?: boolean;
  showTeamLabels?: boolean;
}) {
  return (
    <div className="score-card">
      <div className="score-main">
        <div className="score-teams">
          <div className="score-team-row">
            {teamLogos?.[game.away] ? <img className="mini-logo" src={logoUrl(teamLogos[game.away])} alt={game.away} /> : null}
            <span>{showTeamLabels ? <strong>Away:</strong> : null} {game.away} {game.away_record ? `(${game.away_record})` : ""}</span>
          </div>
          <div className="score-team-row">
            {teamLogos?.[game.home] ? <img className="mini-logo" src={logoUrl(teamLogos[game.home])} alt={game.home} /> : null}
            <span>{showTeamLabels ? <strong>Home:</strong> : null} {game.home} {game.home_record ? `(${game.home_record})` : ""}</span>
          </div>
        </div>
        <div className="muted small">Goalies: {game.away_goalie || "-"} {game.away_goalie_sv || ""} | {game.home_goalie || "-"} {game.home_goalie_sv || ""}</div>
        <div className="muted small">
          Attendance: {typeof game.attendance === "number" ? game.attendance.toLocaleString() : "-"}
          {typeof game.arena_capacity === "number" ? `/${game.arena_capacity.toLocaleString()}` : ""}
        </div>
        {(game.periods ?? []).length > 0 ? (
          <table className="period-table">
            <thead>
              <tr>
                <th>Team</th>
                {(game.periods ?? []).map((p) => <th key={`h-${game.home}-${game.away}-${p.label}`}>{p.label}</th>)}
                <th>T</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{game.away}</td>
                {(game.periods ?? []).map((p) => <td key={`a-${game.away}-${p.label}`}>{p.away}</td>)}
                <td className="total-goals">{game.away_goals ?? "-"}</td>
              </tr>
              <tr>
                <td>{game.home}</td>
                {(game.periods ?? []).map((p) => <td key={`h-${game.home}-${p.label}`}>{p.home}</td>)}
                <td className="total-goals">{game.home_goals ?? "-"}</td>
              </tr>
            </tbody>
          </table>
        ) : null}
        {showCommentary && (game.commentary ?? []).length > 0 ? (
          <div className="results">
            {(game.commentary ?? []).map((line, idx) => (
              <div key={`c-${idx}-${line}`} className="line">{line}</div>
            ))}
          </div>
        ) : null}
        {(game.three_stars ?? []).length > 0 ? (
          <div className="muted small">
            {(game.three_stars ?? []).map((s) => `${s.label}: ${s.summary}`).join(" | ")}
          </div>
        ) : null}
      </div>
      <div className="muted small">{game.overtime ? "OT" : ""}</div>
    </div>
  );
}

function StandingsTable({ rows }: { rows: StandingRow[] }) {
  return (
    <table>
      <thead>
        <tr><th>Team</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>PTS</th><th>HOME</th><th>AWAY</th><th>GF</th><th>GA</th><th>DIFF</th><th>L10</th><th>STRK</th></tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.team}-${r.conference}-${r.division}`}>
            <td className="team-cell"><img className="table-logo" src={logoUrl(r.logo_url)} alt={r.team} /><span>{r.team}</span></td>
            <td>{r.gp}</td><td>{r.w}</td><td>{r.l}</td><td>{r.otl}</td><td>{r.pts}</td><td>{r.home}</td><td>{r.away}</td><td>{r.gf}</td><td>{r.ga}</td>
            <td className={r.diff > 0 ? "pos" : r.diff < 0 ? "neg" : ""}>{r.diff > 0 ? `+${r.diff}` : r.diff}</td>
            <td>{r.l10}</td><td>{r.strk}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LeaderBlock<T extends { name: string; team: string }>({
  title,
  valueLabel,
  rows,
  getValue,
  formatValue,
  sortAsc = false,
  onPick,
}: {
  title: string;
  valueLabel: string;
  rows: T[];
  getValue: (row: T) => number;
  formatValue: (value: number) => string;
  sortAsc?: boolean;
  onPick: (row: T) => void;
}) {
  const sorted = [...rows].sort((a, b) => (sortAsc ? getValue(a) - getValue(b) : getValue(b) - getValue(a)));
  const topRows = sorted.slice(0, 5);

  function rankAt(idx: number): number {
    if (idx <= 0) return 1;
    const cur = getValue(topRows[idx]);
    const prev = getValue(topRows[idx - 1]);
    if (cur === prev) return rankAt(idx - 1);
    return idx + 1;
  }

  return (
    <section className="leader-block">
      <header className="leader-head">
        <span>{title}</span>
        <span>{valueLabel}</span>
      </header>
      <div>
        {topRows.map((row, idx) => (
          <div key={`${row.team}-${row.name}-${title}`} className="leader-row row-clickable" onClick={() => onPick(row)}>
            <span className="leader-rank">{rankAt(idx)}</span>
            <span className="leader-player">{row.name} <small>{row.team.slice(0, 3).toUpperCase()}</small></span>
            <span className="leader-value">{formatValue(getValue(row))}</span>
          </div>
        ))}
      </div>
      <div className="leader-link">Complete Leaders</div>
    </section>
  );
}
