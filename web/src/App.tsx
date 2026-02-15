import { useEffect, useMemo, useState } from "react";

type MainNavKey = "home" | "scores" | "team_stats" | "league_stats" | "standings" | "franchise";
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
    three_stars?: Array<{ label: string; summary: string }>;
  }>;
};

type HomePanel = {
  team: string;
  logo_url: string;
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
    game_mode: "gm" | "coach" | "both";
  };
  special_teams?: {
    pp_pct: number;
    pk_pct: number;
  };
  latest_game_day: number | null;
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
    three_stars: Array<{ label: string; summary: string }>;
  } | null;
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
  const [standingsMode, setStandingsMode] = useState<"league" | "conference" | "division">("league");
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
  const [loading, setLoading] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const [error, setError] = useState("");

  const summary = useMemo(() => {
    if (!meta) return "Loading...";
    return `Season ${meta.season} Day ${meta.day}/${meta.total_days}${meta.in_playoffs ? " | Playoffs" : ""}`;
  }, [meta]);

  async function loadMeta() {
    const m = await fetchJson<Meta>("/meta");
    setMeta(m);
    return m;
  }

  async function loadStandings(mode = standingsMode) {
    if (mode === "league") {
      const s = await fetchJson<StandingsResponse>("/standings?mode=league");
      setRows(s.rows ?? []);
      setGroupRows({});
      return;
    }
    if (!meta) return;
    const values = mode === "conference" ? meta.conferences : meta.divisions;
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
        loadStandings(standingsMode),
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

  async function setUserTeam(teamName: string) {
    await fetchJson("/user-team", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_name: teamName }),
    });
    await refreshAll();
  }

  async function setCoachSettings(strategy: string, useCoach: boolean) {
    await fetchJson("/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy, use_coach: useCoach }),
    });
    await refreshAll();
  }

  async function fireCoach() {
    await fetchJson("/fire-coach", { method: "POST" });
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
    await refreshAll();
  }

  async function advanceDay() {
    setSimBusy(true);
    setError("");
    try {
      await fetchJson<AdvanceResponse>("/advance", { method: "POST" });
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
            onChange={(e) => void setCoachSettings(e.target.value, meta?.use_coach ?? true)}
            disabled={!meta || meta.game_mode === "gm"}
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
              checked={meta?.use_coach ?? true}
              onChange={(e) => void setCoachSettings(meta?.user_strategy ?? "balanced", e.target.checked)}
              disabled={!meta || meta.game_mode !== "both"}
            />
            Use Coach
          </label>
          <select
            value={meta?.game_mode ?? "both"}
            onChange={(e) => void setGameMode(e.target.value as "gm" | "coach" | "both")}
            disabled={!meta}
          >
            <option value="gm">GM</option>
            <option value="coach">Coach</option>
            <option value="both">Both</option>
          </select>
          <button onClick={() => void fireCoach()} disabled={!meta || meta.game_mode === "coach"}>
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
          ["franchise", "Franchise"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={mainNav === key ? "top-nav-btn active" : "top-nav-btn"}
            onClick={() => {
              if (key === "scores") setScoreDay(0);
              if (key === "team_stats") void loadLeaders("team");
              if (key === "league_stats") void loadLeaders("league");
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
          <div className="split">
            <div><h3>Players</h3><table><thead><tr><th>Team</th><th>Player</th><th>Pos</th><th>GP</th><th>G</th><th>A</th><th>P</th></tr></thead><tbody>
              {players.slice(0, 40).map((p) => <tr key={`${p.team}-${p.name}`}><td>{p.team}</td><td>{p.name}</td><td>{p.position}</td><td>{p.gp}</td><td>{p.g}</td><td>{p.a}</td><td>{p.p}</td></tr>)}
            </tbody></table></div>
            <div><h3>Goalies</h3><table><thead><tr><th>Team</th><th>Goalie</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>GAA</th><th>SV%</th></tr></thead><tbody>
              {goalies.slice(0, 30).map((g) => <tr key={`${g.team}-${g.name}`}><td>{g.team}</td><td>{g.name}</td><td>{g.gp}</td><td>{g.w}</td><td>{g.l}</td><td>{g.otl}</td><td>{g.gaa.toFixed(2)}</td><td>{g.sv_pct.toFixed(3)}</td></tr>)}
            </tbody></table></div>
          </div>
        </section>
      ) : null}

      {mainNav === "team_stats" ? (
        <section className="card leaders">
          <div className="section-head">
            <h2>{meta?.user_team ?? "My Team"} Stats</h2>
          </div>
          <div className="split">
            <div><h3>Skaters</h3><table><thead><tr><th>Player</th><th>Pos</th><th>GP</th><th>G</th><th>A</th><th>P</th></tr></thead><tbody>
              {players.map((p) => <tr key={`${p.team}-${p.name}`}><td>{p.name}</td><td>{p.position}</td><td>{p.gp}</td><td>{p.g}</td><td>{p.a}</td><td>{p.p}</td></tr>)}
            </tbody></table></div>
            <div><h3>Goalies</h3><table><thead><tr><th>Goalie</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>GAA</th><th>SV%</th></tr></thead><tbody>
              {goalies.map((g) => <tr key={`${g.team}-${g.name}`}><td>{g.name}</td><td>{g.gp}</td><td>{g.w}</td><td>{g.l}</td><td>{g.otl}</td><td>{g.gaa.toFixed(2)}</td><td>{g.sv_pct.toFixed(3)}</td></tr>)}
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
          <p className="muted">Season {scoreBoard?.season ?? "-"} | {scoreBoard?.status === "played" ? "Most Recent Finals" : "Scheduled Games"}</p>
          <div className="score-list">
            {(scoreBoard?.games ?? []).map((g, idx) => (
              <div key={`score-${idx}`} className="score-card">
                <div className="score-main">
                  <div className="score-teams">
                    <div>{g.away} {g.away_record ? `(${g.away_record})` : ""}</div>
                    <div>{g.home} {g.home_record ? `(${g.home_record})` : ""}</div>
                  </div>
                  <div className="muted small">Goalies: {g.away_goalie || "-"} {g.away_goalie_sv || ""} | {g.home_goalie || "-"} {g.home_goalie_sv || ""}</div>
                  <div className="muted small">Attendance: {typeof g.attendance === "number" ? g.attendance.toLocaleString() : "-"}</div>
                  {(g.three_stars ?? []).length > 0 ? (
                    <div className="muted small">
                      {(g.three_stars ?? []).map((s) => `${s.label}: ${s.summary}`).join(" | ")}
                    </div>
                  ) : null}
                </div>
                <div className="score-values">
                  <div>{g.away_goals ?? "-"}</div>
                  <div>{g.home_goals ?? "-"}</div>
                </div>
                <div className="muted small">{g.overtime ? "OT" : ""}</div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {mainNav === "franchise" ? (
        <section className="card franchise">
          <h2>{meta?.user_team ?? "Team"} Franchise</h2>
          {franchise ? (
            <>
              <h3>Season History</h3>
              <table><thead><tr><th>Season</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>Pts</th><th>Conf Rank</th><th>Div Rank</th><th>Playoff</th><th>Playoff Result</th><th>Cup</th></tr></thead>
                <tbody>{franchise.history.map((h) => <tr key={`h-${h.season}`}><td>{h.season}</td><td>{h.gp}</td><td>{h.w}</td><td>{h.l}</td><td>{h.otl}</td><td>{h.pts}</td><td>{h.conference_rank}</td><td>{h.division_rank}</td><td>{h.playoff}</td><td>{h.playoff_result}</td><td>{h.cup_winner}</td></tr>)}</tbody>
              </table>
            </>
          ) : <p>Loading franchise data...</p>}
        </section>
      ) : null}

      {mainNav === "home" ? (
        <section className="card">
          <h2>{homePanel?.team ?? meta?.user_team ?? "Team"} Home</h2>
          <p className="muted">
            Record {homePanel?.team_summary?.record ?? "-"} | {homePanel?.team_summary?.division ?? "-"} Division: {homePanel?.team_summary?.division_rank ?? "-"} place | {homePanel?.team_summary?.points ?? 0} pts
          </p>
          {homePanel ? (
            <div className="split">
              <div>
                <h3>Latest Team Game</h3>
                {homePanel.latest_game ? (
                  <>
                    <div className="home-matchup">
                      <div className="home-matchup-team">
                        {meta?.team_logos?.[homePanel.latest_game.away] ? (
                          <img className="table-logo" src={logoUrl(meta.team_logos[homePanel.latest_game.away])} alt={homePanel.latest_game.away} />
                        ) : null}
                        <span>{homePanel.latest_game.away}</span>
                      </div>
                      <div className="home-matchup-score">
                        {homePanel.latest_game.away_goals} - {homePanel.latest_game.home_goals}{homePanel.latest_game.overtime ? " OT" : ""}
                      </div>
                      <div className="home-matchup-team">
                        {meta?.team_logos?.[homePanel.latest_game.home] ? (
                          <img className="table-logo" src={logoUrl(meta.team_logos[homePanel.latest_game.home])} alt={homePanel.latest_game.home} />
                        ) : null}
                        <span>{homePanel.latest_game.home}</span>
                      </div>
                    </div>
                    <p className="muted">
                      Day {homePanel.latest_game_day} | {homePanel.latest_game.away} {homePanel.latest_game.away_goals} at {homePanel.latest_game.home} {homePanel.latest_game.home_goals}
                      {homePanel.latest_game.overtime ? " (OT)" : ""}
                    </p>
                    <p className="muted">
                      Goalies: {homePanel.latest_game.away_goalie} {homePanel.latest_game.away_goalie_sv} | {homePanel.latest_game.home_goalie} {homePanel.latest_game.home_goalie_sv}
                    </p>
                    <div className="results">
                      {(homePanel.latest_game.three_stars ?? []).map((s) => (
                        <div key={`${s.label}-${s.summary}`} className="line">{s.label}: {s.summary}</div>
                      ))}
                    </div>
                  </>
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
                  Strategy: {homePanel.control.user_strategy} | Coach Decisions: {homePanel.control.use_coach ? "On" : "Off"}
                </p>
                <p className="muted">
                  Game Mode: {homePanel.control.game_mode.toUpperCase()} | PP% {(homePanel.special_teams?.pp_pct ?? 0).toFixed(3)} | PK% {(homePanel.special_teams?.pk_pct ?? 0).toFixed(3)}
                </p>
              </div>
            </div>
          ) : (
            <p>Loading home details...</p>
          )}
        </section>
      ) : null}
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
