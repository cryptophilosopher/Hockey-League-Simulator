import { useEffect, useMemo, useRef, useState } from "react";

type MainNavKey = "home" | "schedule" | "legacy" | "trade_center" | "transactions" | "contracts" | "free_agents" | "scores" | "league_news" | "team_stats" | "league_stats" | "awards" | "standings" | "league_records" | "cup_history" | "roster" | "lines" | "callups" | "minors" | "franchise" | "records" | "banners";
type StandingsTab = "standings" | "wildcard" | "playoffs";
type NavScope = "league" | "team";
type TransactionFilter = "all" | "trades" | "callups" | "injuries" | "signings";

type Meta = {
  teams: string[];
  team_logos: Record<string, string>;
  conferences: string[];
  divisions: string[];
  strategies: string[];
  user_team: string;
  user_team_logo: string;
  user_team_primary_color?: string;
  user_team_secondary_color?: string;
  user_strategy: string;
  use_coach: boolean;
  override_coach_for_lines: boolean;
  override_coach_for_strategy: boolean;
  auto_injury_moves?: boolean;
  game_mode: "gm" | "coach" | "both";
  user_coach_name: string;
  user_coach_rating: number;
  user_coach_style: string;
  draft_focus?: string;
  draft_focus_options?: string[];
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
  clinch?: string[];
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
  jersey_number?: number | null;
  country?: string;
  country_code?: string;
  flag?: string;
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
  injured?: boolean;
  injured_games_remaining?: number;
  injury_status?: string;
};

type GoalieRow = {
  team: string;
  name: string;
  jersey_number?: number | null;
  country?: string;
  country_code?: string;
  flag?: string;
  age: number;
  gp: number;
  w: number;
  l: number;
  otl: number;
  so: number;
  gaa: number;
  sv_pct: number;
  injured?: boolean;
  injured_games_remaining?: number;
  injury_status?: string;
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
  goalie_so?: number;
  plus_minus?: number;
  pim?: number;
  toi_g?: number;
  ppg?: number;
  ppa?: number;
  shg?: number;
  sha?: number;
  shots?: number;
  shot_pct?: number;
  gaa: number;
  sv_pct: number;
  is_current?: boolean;
};

type PlayerCareerPayload = {
  player: {
    team: string;
    name: string;
    jersey_number?: number | null;
    overall?: number;
    age: number;
    position: string;
    country?: string;
    country_code?: string;
    flag?: string;
    draft_label?: string;
    height?: string;
    weight_lbs?: number;
    shot?: string;
    birth_place?: string;
    birthdate?: string;
    ratings?: {
      shooting: number;
      playmaking: number;
      defense: number;
      goaltending: number;
      physical: number;
      durability: number;
    };
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
  retired?: Array<{ season: number; entry: string; name?: string; team?: string }>;
  draft_picks?: Array<{ season: number; team?: string; name: string; position: string; country?: string; country_code?: string; flag?: string; round: number; overall: number }>;
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
    round?: string;
    game_number?: number;
    series_higher_seed?: string;
    series_lower_seed?: string;
    series_high_wins?: number;
    series_low_wins?: number;
  }>;
};

type HomePanel = {
  team: string;
  logo_url: string;
  cup_count?: number;
  cup_seasons?: number[];
  season: number;
  day: number;
  team_summary?: {
    record: string;
    division: string;
    division_rank: number;
    points: number;
    pp_pct?: number;
    pk_pct?: number;
  };
  coach: {
    name: string;
    age?: number;
    rating: number;
    style: string;
    offense: number;
    defense: number;
    goalie_dev: number;
    record?: string;
    overall_record?: string;
    cups?: number;
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
  locker_room?: {
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
  team_schedule?: Array<{
    game_day?: number;
    home: string;
    away: string;
    status?: "played" | "scheduled";
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
  upcoming_game?: {
    home: string;
    away: string;
    game_number?: number;
  } | null;
  news?: Array<{
    kind: string;
    headline: string;
    details: string;
    team?: string;
    season: number;
    day: number;
  }>;
  top_story?: {
    kind: string;
    headline: string;
    details: string;
    team?: string;
    season: number;
    day: number;
  } | null;
  gm_notifications?: Array<{
    season: number;
    day: number;
    headline: string;
    details: string;
  }>;
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
      series_higher_seed?: string;
      series_lower_seed?: string;
      series_high_wins?: number;
      series_low_wins?: number;
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
  age?: number;
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
  total_count?: number;
  active_count?: number;
  injured_count?: number;
  coach: { name: string; rating: number; style: string };
  override_coach_for_lines: boolean;
  position_penalty: number;
  assignments: Record<string, string>;
  units: Array<{
    unit: string;
    LW: { name: string; pos: string; flag?: string; out_of_position?: boolean } | null;
    C: { name: string; pos: string; flag?: string; out_of_position?: boolean } | null;
    RW: { name: string; pos: string; flag?: string; out_of_position?: boolean } | null;
    LD: { name: string; pos: string; flag?: string; out_of_position?: boolean } | null;
    RD: { name: string; pos: string; flag?: string; out_of_position?: boolean } | null;
    G: { name: string; pos: string; flag?: string; out_of_position?: boolean } | null;
  }>;
  candidates: Array<{ name: string; pos: string; flag?: string }>;
  extra_players?: Array<{ name: string; pos: string; flag?: string }>;
  injuries?: Array<{ name: string; pos: string; flag?: string; games_remaining: number; injury_type?: string; injury_status?: string }>;
};

type MinorPlayerRow = {
  team: string;
  name: string;
  jersey_number?: number | null;
  position: string;
  age: number;
  country?: string;
  country_code?: string;
  flag?: string;
  tier: string;
  seasons_to_nhl: number;
  overall: number;
  injured?: boolean;
  injured_games_remaining?: number;
};

type RosterBioRow = {
  team: string;
  name: string;
  jersey_number?: number | null;
  position: string;
  age: number;
  height: string;
  weight_lbs: number;
  shot: string;
  birth_place: string;
  birthdate: string;
  injured?: boolean;
  injured_games_remaining?: number;
  injury_status?: string;
};

type RosterPayload = {
  team: string;
  captain?: string;
  assistants?: string[];
  groups: Record<string, RosterBioRow[]>;
};

type CupHistoryRow = {
  season: number;
  winner: string;
  winner_logo_url?: string;
  winner_captain: string;
  winner_coach: string;
  runner_up: string;
  runner_logo_url?: string;
  runner_captain: string;
  runner_coach: string;
  series?: string;
  mvp: string;
};

type InboxEvent = {
  id: number;
  season: number;
  day: number;
  type: string;
  title: string;
  details: string;
  options: Array<{ id: string; label: string; description: string }>;
  payload?: Record<string, unknown>;
  expires_day: number;
  resolved: boolean;
  resolution?: { choice_id?: string; auto?: boolean; season?: number; day?: number } | null;
  result_note?: string;
};
type InboxResolveResponse = { ok: boolean; event: InboxEvent };

type CallupsPayload = {
  team: string;
  total_count?: number;
  active_count: number;
  injured_count?: number;
  max_active: number;
  projected_next_day_active?: number;
  injuries: Array<{ name: string; position: string; injury_type?: string; injury_status?: string; games_out: number }>;
  returning_tomorrow?: Array<{ name: string; position: string; injury_type?: string; injury_status?: string }>;
  roster: Array<{
    name: string;
    position: string;
    age: number;
    injured: boolean;
    games_out: number;
    dressed: boolean;
    temporary_replacement_for?: string;
    overall: number;
  }>;
  minors: Array<{
    name: string;
    position: string;
    age: number;
    injured: boolean;
    games_out: number;
    tier: string;
    seasons_to_nhl: number;
    overall: number;
  }>;
};

type TransactionRow = {
  kind: string;
  headline: string;
  details: string;
  team?: string;
  season: number;
  day: number;
};

type RecordsPayload = {
  team: string;
  league: Array<{
    key: string;
    label: string;
    rows: Array<{ name: string; team: string; position: string; status: string; value: number }>;
  }>;
  franchise: Array<{
    key: string;
    label: string;
    rows: Array<{ name: string; team: string; position: string; status: string; value: number }>;
  }>;
};

type BannersPayload = {
  team: string;
  logo_url?: string;
  primary_color?: string;
  secondary_color?: string;
  banners: Array<{
    season: number;
    kind: string;
    title: string;
    team: string;
    number?: number;
    player?: string;
    start_year?: number;
    end_year?: number;
  }>;
};

type AwardsSkaterRow = {
  name: string;
  team: string;
  position: string;
  gp: number;
  g: number;
  a: number;
  p: number;
  plus_minus?: number;
};

type AwardsGoalieRow = {
  name: string;
  team: string;
  position: string;
  gp: number;
  w: number;
  so: number;
  gaa: number;
  sv_pct: number;
};

type AwardsPayload = {
  season: number;
  team: string;
  races: {
    hart: AwardsSkaterRow[];
    rocket: AwardsSkaterRow[];
    vezina: AwardsGoalieRow[];
  };
  playoff_mvp_race: Array<{ name: string; team: string; position: string; summary: string; score?: number }>;
  record_chases: {
    league: Array<{ category: string; record_holder: string; record_value: number; challenger: string; challenger_team: string; challenger_value: number; gap: number }>;
    franchise: Array<{ category: string; record_holder: string; record_value: number; challenger: string; challenger_team: string; challenger_value: number; gap: number }>;
  };
  milestones: Array<{ kind: string; headline: string; details: string; season: number; day: number }>;
  storylines: string[];
};

type ContractsPayload = {
  team: string;
  cap_limit: number;
  cap_used: number;
  cap_space: number;
  active_count: number;
  max_active: number;
  active: Array<{
    team: string;
    name: string;
    position: string;
    age: number;
    years_left: number;
    cap_hit: number;
    contract_type: string;
    is_rfa: boolean;
    injured: boolean;
    injured_games_remaining: number;
  }>;
  minors: Array<{
    team: string;
    name: string;
    position: string;
    age: number;
    years_left: number;
    cap_hit: number;
    contract_type: string;
    is_rfa: boolean;
    injured: boolean;
    injured_games_remaining: number;
  }>;
};

type FreeAgentsPayload = {
  team: string;
  cap_limit: number;
  cap_used: number;
  cap_space: number;
  rows: Array<{
    name: string;
    position: string;
    age: number;
    overall: number;
    ask_years: number;
    ask_cap_hit: number;
    contract_type: string;
    is_rfa: boolean;
    origin_team?: string;
    is_user_origin?: boolean;
  }>;
};

type TradeAssetRow = {
  name: string;
  position: string;
  age: number;
  overall: number;
  trade_value: number;
  gp?: number;
  g?: number;
  a?: number;
  p?: number;
  w?: number;
  l?: number;
  so?: number;
  gaa?: number;
  sv_pct?: number;
  on_trade_block?: boolean;
  trade_preference?: "available" | "shop" | "untouchable";
};

type TeamNeeds = {
  team: string;
  scores: Record<string, number>;
  auto_scores?: Record<string, number>;
  primary_need: string;
  window: string;
  target_position: string;
  mode?: "auto" | "manual";
  source?: "auto" | "manual";
};

type TradeMarketPayload = {
  team: string;
  partners: string[];
  my_assets: TradeAssetRow[];
  my_trade_block?: string[];
  my_trade_preferences?: Record<string, "available" | "shop" | "untouchable">;
  my_needs?: TeamNeeds;
  partner_team: string;
  partner_assets: TradeAssetRow[];
  partner_needs?: TeamNeeds;
  partner_trade_block?: string[];
  partner_trade_preferences?: Record<string, "available" | "shop" | "untouchable">;
};

type TradeProposalResult = {
  ok: boolean;
  reason?: string;
  team?: string;
  partner_team?: string;
  give_player?: string;
  receive_player?: string;
  user_eval?: {
    net_value: number;
    min_net: number;
  };
  partner_eval?: {
    net_value: number;
    min_net: number;
  };
};

type TradeInsight = {
  verdict?: string;
  accept_probability?: number;
  reasons?: string[];
  need_fit?: {
    user_primary_need?: string;
    partner_primary_need?: string;
    receive_matches_user_need?: boolean;
    give_matches_partner_need?: boolean;
  };
  value?: {
    user_net?: number;
    user_min?: number;
    partner_net?: number;
    partner_min?: number;
  };
  comparison?: {
    give?: {
      name?: string; position?: string; age?: number; overall?: number; cap_hit?: number; years_left?: number;
      stats?: Record<string, unknown>;
      ratings?: Record<string, unknown>;
    };
    receive?: {
      name?: string; position?: string; age?: number; overall?: number; cap_hit?: number; years_left?: number;
      stats?: Record<string, unknown>;
      ratings?: Record<string, unknown>;
    };
    delta?: { overall?: number; age?: number; cap_hit?: number; years_left?: number };
  };
};

type TradeEvaluateResult = {
  ok: boolean;
  reason?: string;
  team?: string;
  partner_team?: string;
  give_player?: string;
  receive_player?: string;
  insight?: TradeInsight;
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
  const [minorPlayers, setMinorPlayers] = useState<MinorPlayerRow[]>([]);
  const [rosterData, setRosterData] = useState<RosterPayload | null>(null);
  const [cupHistoryRows, setCupHistoryRows] = useState<CupHistoryRow[]>([]);
  const [inboxEvents, setInboxEvents] = useState<InboxEvent[]>([]);
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [transactionFilter, setTransactionFilter] = useState<TransactionFilter>("all");
  const [transactionSeason, setTransactionSeason] = useState<string>("auto");
  const [tradeMarket, setTradeMarket] = useState<TradeMarketPayload | null>(null);
  const [tradeBlockPlayers, setTradeBlockPlayers] = useState<string[]>([]);
  const [tradePreferences, setTradePreferences] = useState<Record<string, "available" | "shop" | "untouchable">>({});
  const [tradePartner, setTradePartner] = useState("");
  const [tradeGivePlayer, setTradeGivePlayer] = useState("");
  const [tradeReceivePlayer, setTradeReceivePlayer] = useState("");
  const [tradeReceivePool, setTradeReceivePool] = useState<"all" | "shop" | "available">("all");
  const [tradePreview, setTradePreview] = useState<TradeEvaluateResult | null>(null);
  const [needsMode, setNeedsMode] = useState<"auto" | "manual">("auto");
  const [needsDraft, setNeedsDraft] = useState<Record<string, number>>({});
  const [contractsData, setContractsData] = useState<ContractsPayload | null>(null);
  const [freeAgentsData, setFreeAgentsData] = useState<FreeAgentsPayload | null>(null);
  const [leagueNews, setLeagueNews] = useState<TransactionRow[]>([]);
  const [recordsData, setRecordsData] = useState<RecordsPayload | null>(null);
  const [bannersData, setBannersData] = useState<BannersPayload | null>(null);
  const [awardsData, setAwardsData] = useState<AwardsPayload | null>(null);
  const [callupsData, setCallupsData] = useState<CallupsPayload | null>(null);
  const [navScope, setNavScope] = useState<NavScope>("league");
  const [legacyTab, setLegacyTab] = useState<"history" | "banners" | "records">("history");
  const [gameModeLocal, setGameModeLocal] = useState<"gm" | "coach" | "both">("gm");
  const [showCoachDetails, setShowCoachDetails] = useState(false);
  const [autoActionToast, setAutoActionToast] = useState("");
  const [loading, setLoading] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const [error, setError] = useState("");
  const leadersRequestId = useRef(0);

  const summary = useMemo(() => {
    if (!meta) return "Loading...";
    if (scoreBoard) {
      const label = scoreBoard.phase === "playoffs"
        ? `Playoffs${scoreBoard.round ? ` - ${scoreBoard.round}` : ""}`
        : "Regular Season";
      return `Season ${scoreBoard.season} Day ${scoreBoard.day}/${scoreBoard.total_days} | ${label}`;
    }
    return `Season ${meta.season} Day ${meta.day}/${meta.total_days}${meta.in_playoffs ? " | Playoffs" : ""}`;
  }, [meta, mainNav, scoreBoard]);

  const teamPlayers = useMemo(
    () => players.filter((p) => p.team === (meta?.user_team ?? p.team)),
    [players, meta?.user_team],
  );
  const teamGoalies = useMemo(
    () => goalies.filter((g) => g.team === (meta?.user_team ?? g.team)),
    [goalies, meta?.user_team],
  );
  const standingsRecordMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const r of rows) map.set(r.team, `${r.w}-${r.l}-${r.otl}`);
    for (const grp of Object.values(groupRows)) {
      for (const r of grp) map.set(r.team, `${r.w}-${r.l}-${r.otl}`);
    }
    return map;
  }, [rows, groupRows]);

  const teamLeaders = useMemo(() => {
    const defs = [
      { key: "points", label: "Points", pick: (p: PlayerRow) => p.p, fmt: (v: number) => `${v}` },
      { key: "goals", label: "Goals", pick: (p: PlayerRow) => p.g, fmt: (v: number) => `${v}` },
      { key: "assists", label: "Assists", pick: (p: PlayerRow) => p.a, fmt: (v: number) => `${v}` },
      { key: "pim", label: "PIM", pick: (p: PlayerRow) => p.pim, fmt: (v: number) => `${v}` },
      { key: "plusminus", label: "+/-", pick: (p: PlayerRow) => p.plus_minus, fmt: (v: number) => (v > 0 ? `+${v}` : `${v}`) },
    ] as const;

    return defs.map((d) => {
      const best = [...teamPlayers].sort((a, b) => d.pick(b) - d.pick(a) || b.p - a.p || b.g - a.g || a.name.localeCompare(b.name))[0] ?? null;
      return {
        key: d.key,
        label: d.label,
        player: best,
        value: best ? d.fmt(d.pick(best)) : "-",
      };
    });
  }, [teamPlayers]);

  const isActiveRosterFull = (callupsData?.active_count ?? 0) >= (callupsData?.max_active ?? 22);

  const transactionSeasons = useMemo(() => {
    const seasons = new Set<number>();
    for (const t of transactions) {
      if (Number.isFinite(t.season)) seasons.add(t.season);
    }
    return Array.from(seasons).sort((a, b) => b - a);
  }, [transactions]);

  useEffect(() => {
    if (transactionSeasons.length === 0) return;
    if (transactionSeason === "auto") {
      setTransactionSeason(String(transactionSeasons[0]));
      return;
    }
    if (transactionSeason === "all") return;
    const wanted = Number(transactionSeason);
    if (!transactionSeasons.includes(wanted)) {
      setTransactionSeason(String(transactionSeasons[0]));
    }
  }, [transactionSeason, transactionSeasons]);

  const filteredTransactions = useMemo(() => {
    const seasonFiltered = transactionSeason === "all" || transactionSeason === "auto"
      ? transactions
      : transactions.filter((t) => t.season === Number(transactionSeason));
    if (transactionFilter === "all") return seasonFiltered;
    return seasonFiltered.filter((t) => {
      const text = `${t.kind} ${t.headline} ${t.details}`.toLowerCase();
      if (transactionFilter === "trades") return text.includes("trade");
      if (transactionFilter === "callups") {
        return (
          text.includes("called up")
          || text.includes("recalled")
          || text.includes("assigned")
          || text.includes("promoted")
          || text.includes("demoted")
          || text.includes("send down")
          || text.includes("sent down")
          || text.includes("waiver")
        );
      }
      if (transactionFilter === "injuries") return text.includes("injury") || text.includes("ir");
      if (transactionFilter === "signings") {
        return text.includes("sign") || text.includes("signed") || text.includes("contract");
      }
      return true;
    });
  }, [transactions, transactionFilter, transactionSeason]);

  const scheduleGames = useMemo(() => {
    const list = [...(homePanel?.team_schedule ?? [])];
    return list.sort((a, b) => (a.game_day ?? 9999) - (b.game_day ?? 9999));
  }, [homePanel]);

  function trendArrow(trend?: string): string {
    if (trend === "Rising") return "\u25B2";
    if (trend === "Falling") return "\u25BC";
    return "\u25A0";
  }

  function moodFace(mood?: string): string {
    const m = (mood ?? "").toLowerCase();
    if (m.includes("buzz") || m.includes("locked")) return "\uD83D\uDE04";
    if (m.includes("optim") || m.includes("confident")) return "\uD83D\uDE42";
    if (m.includes("steady") || m.includes("neutral")) return "\uD83D\uDE10";
    if (m.includes("restless") || m.includes("tense")) return "\uD83D\uDE1F";
    return "\uD83D\uDE20";
  }

  function playerLabel(name: string, jerseyNumber?: number | null) {
    return (
      <>
        {name}
        {jerseyNumber ? <span className="player-num"> {jerseyNumber}</span> : null}
      </>
    );
  }

  function topStarName(summary?: string): string {
    const text = String(summary ?? "").trim();
    const closeParen = text.indexOf(")");
    if (closeParen > 0) return text.slice(0, closeParen + 1);
    return text;
  }

  function formatScheduleResult(game: {
    home: string;
    away: string;
    home_goals?: number;
    away_goals?: number;
    overtime?: boolean;
  }, teamName: string): string {
    if (typeof game.home_goals !== "number" || typeof game.away_goals !== "number") return "-";
    const isHome = game.home === teamName;
    const gf = isHome ? game.home_goals : game.away_goals;
    const ga = isHome ? game.away_goals : game.home_goals;
    const wl = gf > ga ? "W" : "L";
    const ot = game.overtime ? " OT" : "";
    return `${wl} ${gf}-${ga}${ot}`;
  }

  function needLabel(key: string): string {
    const map: Record<string, string> = {
      top6_f: "Top-6 F",
      top4_d: "Top-4 D",
      starter_g: "Starter G",
      depth_f: "Depth F",
      depth_d: "Depth D",
      cap_relief: "Cap Relief",
    };
    return map[key] ?? key;
  }

  function needKeys(needs?: TeamNeeds): string[] {
    const keys = Object.keys(needs?.scores ?? {});
    if (keys.length > 0) return keys;
    return ["top6_f", "top4_d", "starter_g", "depth_f", "depth_d", "cap_relief"];
  }

  function injuryStatusKey(status?: string, injured?: boolean): "dtd" | "ir" | "ltir" | "season" | "none" {
    const s = (status ?? "").trim().toUpperCase();
    if (s.includes("DTD")) return "dtd";
    if (!injured) return "none";
    if (s.includes("SEASON")) return "season";
    if (s.includes("LTIR")) return "ltir";
    return "ir";
  }

  function injuryStatusLabel(status?: string, injured?: boolean): string {
    const key = injuryStatusKey(status, injured);
    if (key === "dtd") return "DTD";
    if (key === "ltir") return "LTIR";
    if (key === "season") return "SEASON";
    if (key === "ir") return "IR";
    return "";
  }

  function renderInjuryChip(status?: string, injured?: boolean) {
    const key = injuryStatusKey(status, injured);
    if (key === "none") return null;
    return <span className={`status-chip ${key}`}>{injuryStatusLabel(status, injured)}</span>;
  }

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

  async function loadLeaders(scope: "league" | "team", teamName?: string) {
    const selectedTeam = teamName ?? meta?.user_team ?? "";
    const teamQuery = scope === "team" ? `&team=${encodeURIComponent(selectedTeam)}` : "";
    const reqId = ++leadersRequestId.current;
    const [p, g] = await Promise.all([
      fetchJson<PlayerRow[]>(`/players?scope=${scope}${teamQuery}`),
      fetchJson<GoalieRow[]>(`/goalies?scope=${scope}${teamQuery}`),
    ]);
    if (reqId !== leadersRequestId.current) return;
    setPlayers(p);
    setGoalies(g);
  }

  async function loadPlayoffs() {
    setPlayoffs(await fetchJson<PlayoffPayload>("/playoffs"));
  }

  async function loadFranchise(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    setFranchise(await fetchJson<FranchisePayload>(`/franchise?team=${encodeURIComponent(chosen)}`));
  }

  async function loadHome() {
    setHomePanel(await fetchJson<HomePanel>("/home"));
  }

  async function loadLines(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    const payload = await fetchJson<LinesPayload>(`/lines?team=${encodeURIComponent(chosen)}`);
    setLinesData(payload);
    setLineAssignments(payload.assignments ?? {});
  }

  async function loadMinorLeague(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    setMinorPlayers(await fetchJson<MinorPlayerRow[]>(`/minor-league?team=${encodeURIComponent(chosen)}`));
  }

  async function loadRoster(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    setRosterData(await fetchJson<RosterPayload>(`/roster?team=${encodeURIComponent(chosen)}`));
  }

  async function loadCupHistory() {
    setCupHistoryRows(await fetchJson<CupHistoryRow[]>("/cup-history"));
  }

  async function loadInbox() {
    setInboxEvents(await fetchJson<InboxEvent[]>("/inbox?resolved=false&limit=80"));
  }

  async function loadCallups(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    setCallupsData(await fetchJson<CallupsPayload>(`/callups?team=${encodeURIComponent(chosen)}`));
  }

  async function loadTransactions(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    setTransactions(await fetchJson<TransactionRow[]>(`/transactions?team=${encodeURIComponent(chosen)}&limit=5000`));
  }

  async function loadTradeBlock(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    const payload = await fetchJson<{ team: string; players: string[]; preferences?: Record<string, "available" | "shop" | "untouchable"> }>(`/trade-block?team=${encodeURIComponent(chosen)}`);
    setTradeBlockPlayers(payload.players ?? []);
    setTradePreferences(payload.preferences ?? {});
  }

  async function loadTradeMarket(teamName?: string, partnerName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    const partner = partnerName ?? tradePartner;
    const query = `/trade-market?team=${encodeURIComponent(chosen)}${partner ? `&partner=${encodeURIComponent(partner)}` : ""}`;
    const payload = await fetchJson<TradeMarketPayload>(query);
    setTradeMarket(payload);
    setTradeBlockPlayers(payload.my_trade_block ?? []);
    setTradePreferences(payload.my_trade_preferences ?? {});
    const firstPartner = payload.partner_team || payload.partners[0] || "";
    if (!tradePartner && firstPartner) {
      setTradePartner(firstPartner);
    }
    if (!tradeGivePlayer && payload.my_assets.length > 0) {
      setTradeGivePlayer(payload.my_assets[0].name);
    }
    if (!tradeReceivePlayer && payload.partner_assets.length > 0) {
      setTradeReceivePlayer(payload.partner_assets[0].name);
    }
  }

  async function loadContracts(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    setContractsData(await fetchJson<ContractsPayload>(`/contracts?team=${encodeURIComponent(chosen)}`));
  }

  async function loadFreeAgents(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    if (!chosen) return;
    setFreeAgentsData(await fetchJson<FreeAgentsPayload>(`/free-agents?team=${encodeURIComponent(chosen)}`));
  }

  async function loadLeagueNews() {
    setLeagueNews(await fetchJson<TransactionRow[]>("/news?limit=180"));
  }

  async function loadRecords(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    const query = chosen ? `?team=${encodeURIComponent(chosen)}` : "";
    setRecordsData(await fetchJson<RecordsPayload>(`/records${query}`));
  }

  async function loadBanners(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    const query = chosen ? `?team=${encodeURIComponent(chosen)}` : "";
    setBannersData(await fetchJson<BannersPayload>(`/banners${query}`));
  }

  async function loadAwards(teamName?: string) {
    const chosen = teamName ?? meta?.user_team;
    const query = chosen ? `?team=${encodeURIComponent(chosen)}` : "";
    setAwardsData(await fetchJson<AwardsPayload>(`/awards${query}`));
  }

  async function loadDayBoards(sDay = scoreDay) {
    const scores = await fetchJson<DayBoard>(`/day-board?day=${sDay}`);
    setScoreBoard(scores);
  }

  async function refreshAll(options?: { forceLatestScoreDay?: boolean }) {
    setLoading(true);
    setError("");
    try {
      const m = await loadMeta();
      const scoreTarget = options?.forceLatestScoreDay ? 0 : (scoreDay > 0 ? scoreDay : 0);
      const leaderTarget = mainNav === "team_stats" ? "team" : "league";
      await Promise.all([
        loadStandings(standingsMode, m),
        loadWildCard(),
        loadLeaders(leaderTarget, m.user_team),
        loadPlayoffs(),
        loadFranchise(m.user_team),
        loadHome(),
        loadInbox(),
        loadTradeBlock(m.user_team),
        (mainNav === "league_news" ? loadLeagueNews() : Promise.resolve()),
        (mainNav === "transactions" ? loadTransactions(m.user_team) : Promise.resolve()),
        (mainNav === "trade_center" ? loadTradeMarket(m.user_team, tradePartner) : Promise.resolve()),
        (mainNav === "contracts" ? loadContracts(m.user_team) : Promise.resolve()),
        (mainNav === "free_agents" ? loadFreeAgents(m.user_team) : Promise.resolve()),
        (mainNav === "callups" ? loadCallups(m.user_team) : Promise.resolve()),
        ((mainNav === "legacy" || mainNav === "league_records") ? loadRecords(m.user_team) : Promise.resolve()),
        (mainNav === "legacy" ? loadBanners(m.user_team) : Promise.resolve()),
        (mainNav === "awards" ? loadAwards(m.user_team) : Promise.resolve()),
        (mainNav === "cup_history" ? loadCupHistory() : Promise.resolve()),
        loadDayBoards(scoreTarget),
        (mainNav === "roster" ? loadRoster(m.user_team) : Promise.resolve()),
        (mainNav === "lines" ? loadLines(m.user_team) : Promise.resolve()),
        (mainNav === "minors" ? loadMinorLeague(m.user_team) : Promise.resolve()),
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
    setError("");
    try {
      await fetchJson("/user-team", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team_name: teamName }),
      });
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      await loadMeta();
    }
  }

  async function setCoachSettings(strategy: string, overrideCoachForStrategy: boolean) {
    await fetchJson("/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy, override_coach_for_strategy: overrideCoachForStrategy }),
    });
    await refreshAll();
  }

  async function setControlOverrides(
    overrideCoachForLines: boolean,
    overrideCoachForStrategy: boolean,
    autoInjuryMoves: boolean = meta?.auto_injury_moves ?? false,
  ) {
    await fetchJson("/control-overrides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        override_coach_for_lines: overrideCoachForLines,
        override_coach_for_strategy: overrideCoachForStrategy,
        auto_injury_moves: autoInjuryMoves,
      }),
    });
    await refreshAll();
  }

  async function setDraftFocus(focus: string) {
    await fetchJson("/draft-need", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ focus }),
    });
    await refreshAll();
  }

  async function onChangeTradePartner(partnerName: string) {
    setTradePartner(partnerName);
    setTradeReceivePlayer("");
    setTradePreview(null);
    if (!meta?.user_team) return;
    await loadTradeMarket(meta.user_team, partnerName);
  }

  async function evaluateTrade() {
    if (!meta?.user_team || !tradePartner || !tradeGivePlayer || !tradeReceivePlayer) {
      setTradePreview(null);
      return;
    }
    try {
      const result = await fetchJson<TradeEvaluateResult>("/trade/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          team_name: meta.user_team,
          partner_team: tradePartner,
          give_player: tradeGivePlayer,
          receive_player: tradeReceivePlayer,
        }),
      });
      setTradePreview(result);
    } catch (err) {
      setTradePreview(null);
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function proposeTrade() {
    if (!meta?.user_team || !tradePartner || !tradeGivePlayer || !tradeReceivePlayer) return;
    const result = await fetchJson<TradeProposalResult>("/trade/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_name: meta.user_team,
        partner_team: tradePartner,
        give_player: tradeGivePlayer,
        receive_player: tradeReceivePlayer,
      }),
    });
    if (!result.ok) {
      const reason = result.reason ?? "trade_rejected";
      const partnerNet = result.partner_eval?.net_value;
      const partnerMin = result.partner_eval?.min_net;
      const explain = (partnerNet !== undefined && partnerMin !== undefined)
        ? ` (partner net ${partnerNet.toFixed(2)} vs min ${partnerMin.toFixed(2)})`
        : "";
      setError(`Trade rejected: ${reason}${explain}`);
      await loadTradeMarket(meta.user_team, tradePartner);
      return;
    }
    setError("");
    await Promise.all([
      loadTransactions(meta.user_team),
      loadTradeMarket(meta.user_team, tradePartner),
      loadHome(),
      loadLeaders("team", meta.user_team),
      loadRoster(meta.user_team),
      loadLines(meta.user_team),
    ]);
    setTradePreview(null);
  }

  async function saveTeamNeeds(modeArg?: "auto" | "manual") {
    if (!meta?.user_team) return;
    const mode = modeArg ?? needsMode;
    const payload: Record<string, unknown> = {
      team_name: meta.user_team,
      mode,
    };
    if (mode === "manual") {
      payload.scores = needsDraft;
    }
    await fetchJson("/team-needs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadTradeMarket(meta.user_team, tradePartner);
  }

  async function updateTradeBlock(
    playerName: string,
    action: "add" | "remove" | "toggle" | "shop" | "available" | "untouchable" = "toggle",
  ) {
    if (!meta?.user_team || !playerName) return;
    await fetchJson("/trade-block", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_name: meta.user_team,
        player_name: playerName,
        action,
      }),
    });
    await Promise.all([
      loadTradeBlock(meta.user_team),
      (mainNav === "trade_center" ? loadTradeMarket(meta.user_team, tradePartner) : Promise.resolve()),
    ]);
  }

  async function resolveInboxEvent(eventId: number, choiceId: string) {
    const resp = await fetchJson<InboxResolveResponse>("/inbox/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: eventId, choice_id: choiceId }),
    });
    await refreshAll();
    if (choiceId === "auto_call_up" || choiceId === "auto_send_down" || choiceId === "auto_best_send_down") {
      setAutoActionToast(resp?.event?.result_note || "Auto roster move completed.");
      window.setTimeout(() => setAutoActionToast(""), 5000);
    }
  }

  async function loadIncomingTradeOffer(ev: InboxEvent) {
    if (!meta?.user_team) return;
    const payload = (ev.payload ?? {}) as Record<string, unknown>;
    const partner = String(payload.partner_team ?? "").trim();
    const give = String(payload.give_player ?? "").trim();
    const receive = String(payload.receive_player ?? "").trim();
    if (!partner || !give || !receive) return;
    setTradePartner(partner);
    setTradeReceivePool("all");
    await loadTradeMarket(meta.user_team, partner);
    setTradeGivePlayer(give);
    setTradeReceivePlayer(receive);
    setMainNav("trade_center");
  }

  async function promoteCallup(playerName: string) {
    await fetchJson("/callups/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_name: meta?.user_team, player_name: playerName }),
    });
    await refreshAll();
  }

  async function demoteRosterPlayer(playerName: string) {
    await fetchJson("/callups/demote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_name: meta?.user_team, player_name: playerName }),
    });
    await refreshAll();
  }

  async function signFreeAgent(playerName: string, years: number, capHit: number) {
    await fetchJson("/free-agents/sign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_name: meta?.user_team,
        player_name: playerName,
        years,
        cap_hit: capHit,
      }),
    });
    await refreshAll();
  }

  async function extendContract(playerName: string) {
    await fetchJson("/contracts/extend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_name: meta?.user_team,
        player_name: playerName,
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

  async function autoSetBestLines() {
    if (!meta?.user_team) return;
    const payload = await fetchJson<LinesPayload>("/lines/auto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_name: meta.user_team }),
    });
    setLinesData(payload);
    setLineAssignments(payload.assignments ?? {});
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
      await refreshAll({ forceLatestScoreDay: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      try {
        await refreshAll();
      } catch {
        // Keep original error visible; refresh can fail independently.
      }
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
    if (mainNav !== "trade_center") return;
    const firstOffer = inboxEvents.find((ev) => ev.type === "trade_offer");
    if (!firstOffer) return;
    void loadIncomingTradeOffer(firstOffer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mainNav, inboxEvents]);

  useEffect(() => {
    if (scoreDay >= 0) void loadDayBoards(scoreDay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scoreDay]);

  useEffect(() => {
    if (mainNav !== "trade_center") return;
    if (!meta?.user_team) return;
    if (!tradePartner) return;
    void loadTradeMarket(meta.user_team, tradePartner);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mainNav, meta?.user_team, tradePartner]);

  useEffect(() => {
    if (mainNav !== "trade_center") return;
    if (!meta?.user_team || !tradePartner || !tradeGivePlayer || !tradeReceivePlayer) {
      setTradePreview(null);
      return;
    }
    void evaluateTrade();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mainNav, meta?.user_team, tradePartner, tradeGivePlayer, tradeReceivePlayer]);

  useEffect(() => {
    const needs = tradeMarket?.my_needs;
    if (!needs) return;
    const mode = (needs.mode === "manual" ? "manual" : "auto");
    setNeedsMode(mode);
    setNeedsDraft({ ...(needs.scores ?? {}) });
  }, [tradeMarket?.my_needs]);

  const tradePrefOf = (playerName: string): "available" | "shop" | "untouchable" => {
    return tradePreferences[playerName] ?? "available";
  };
  const shopNames = Object.entries(tradePreferences)
    .filter(([, pref]) => pref === "shop")
    .map(([name]) => name)
    .sort();
  const untouchableNames = Object.entries(tradePreferences)
    .filter(([, pref]) => pref === "untouchable")
    .map(([name]) => name)
    .sort();
  const availableCount = Object.entries(tradePreferences)
    .filter(([, pref]) => pref === "available").length;
  const partnerPrefEntries = Object.entries(tradeMarket?.partner_trade_preferences ?? {});
  const partnerShopLine = partnerPrefEntries
    .filter(([, pref]) => pref === "shop")
    .map(([name]) => {
      const p = (tradeMarket?.partner_assets ?? []).find((a) => a.name === name);
      return p ? `${name} (${p.position})` : name;
    })
    .join(", ");
  const partnerAvailableCount = partnerPrefEntries.filter(([, pref]) => pref === "available").length;
  const filteredPartnerAssets = (tradeMarket?.partner_assets ?? []).filter((p) => {
    if (tradeReceivePool === "all") return true;
    return (p.trade_preference ?? "available") === tradeReceivePool;
  });

  useEffect(() => {
    if (!tradeMarket?.partner_assets) return;
    if (filteredPartnerAssets.length === 0) {
      setTradeReceivePlayer("");
      return;
    }
    const exists = filteredPartnerAssets.some((p) => p.name === tradeReceivePlayer);
    if (!exists) {
      setTradeReceivePlayer(filteredPartnerAssets[0].name);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradeReceivePool, tradeMarket?.partner_assets, tradePartner]);

  const leagueNav: Array<[MainNavKey, string]> = [
    ["scores", "Scores"],
    ["league_news", "League News"],
    ["league_stats", "Stats"],
    ["awards", "Awards"],
    ["standings", "Standings"],
    ["cup_history", "Cup History"],
    ["league_records", "League Records"],
  ];
  const teamNav: Array<[MainNavKey, string]> = [
    ["home", `Home${inboxEvents.length > 0 ? ` (${inboxEvents.length})` : ""}`],
    ["schedule", "Schedule"],
    ["trade_center", "Trades"],
    ["transactions", "Transactions"],
    ["contracts", "Contracts"],
    ["free_agents", "Free Agents"],
    ["team_stats", "Team Stats"],
    ["roster", "Roster"],
    ["lines", "Lines"],
    ["callups", "Call Ups"],
    ["minors", "Minor League"],
    ["legacy", "Legacy"],
  ];

  function handleNavSelect(key: MainNavKey) {
    if (key === "scores") setScoreDay(0);
    if (key === "league_news") void loadLeagueNews();
    if (key === "team_stats") void loadLeaders("team", meta?.user_team);
    if (key === "league_stats") void loadLeaders("league");
    if (key === "legacy" || key === "league_records") void loadRecords();
    if (key === "legacy") void loadBanners();
    if (key === "legacy") setLegacyTab("history");
    if (key === "awards") void loadAwards();
    if (key === "cup_history") void loadCupHistory();
    if (key === "trade_center") {
      const firstOffer = inboxEvents.find((ev) => ev.type === "trade_offer");
      if (firstOffer) {
        void loadIncomingTradeOffer(firstOffer);
      } else {
        void loadTradeMarket();
      }
    }
    if (key === "transactions") {
      void loadTransactions();
    }
    if (key === "contracts") void loadContracts();
    if (key === "free_agents") void loadFreeAgents();
    if (key === "roster") void loadRoster();
    if (key === "lines") void loadLines();
    if (key === "callups") void loadCallups();
    if (key === "minors") void loadMinorLeague();
    setNavScope(leagueNav.some(([k]) => k === key) ? "league" : "team");
    setMainNav(key);
  }

  function handleScopeChange(nextScope: NavScope) {
    if (nextScope === navScope) return;
    const navList = nextScope === "league" ? leagueNav : teamNav;
    const hasCurrent = navList.some(([k]) => k === mainNav);
    setNavScope(nextScope);
    if (!hasCurrent) {
      handleNavSelect(nextScope === "league" ? "scores" : "home");
    }
  }

  function openCallupsPage() {
    setNavScope("team");
    setMainNav("callups");
    void loadCallups();
  }

  function openHomePage() {
    setNavScope("team");
    setMainNav("home");
    void loadHome();
    void loadInbox();
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          {meta?.user_team_logo ? (
            <div className="logo-stack">
              <img className="team-logo" src={logoUrl(meta.user_team_logo)} alt={meta.user_team} />
              <div className="logo-bars">
                <span
                  className="logo-bar primary"
                  style={{ background: meta.user_team_primary_color ?? "#1f3a93" }}
                />
                <span
                  className="logo-bar secondary"
                  style={{ background: meta.user_team_secondary_color ?? "#d7e1f5" }}
                />
              </div>
            </div>
          ) : null}
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
          <select
            value={meta?.draft_focus ?? "auto"}
            onChange={(e) => void setDraftFocus(e.target.value)}
            disabled={!meta}
          >
            {(meta?.draft_focus_options ?? ["auto", "F", "C", "LW", "RW", "D", "G"]).map((f) => (
              <option key={`df-${f}`} value={f}>
                Draft {String(f).toUpperCase()}
              </option>
            ))}
          </select>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={meta?.override_coach_for_lines ?? false}
              onChange={(e) =>
                void setControlOverrides(
                  e.target.checked,
                  meta?.override_coach_for_strategy ?? false,
                  meta?.auto_injury_moves ?? false,
                )
              }
              disabled={!meta}
            />
            Override Coach For Lines
          </label>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={meta?.override_coach_for_strategy ?? false}
              onChange={(e) =>
                void setControlOverrides(
                  meta?.override_coach_for_lines ?? false,
                  e.target.checked,
                  meta?.auto_injury_moves ?? false,
                )
              }
              disabled={!meta}
            />
            Override Coach For Strategy
          </label>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={meta?.auto_injury_moves ?? false}
              onChange={(e) =>
                void setControlOverrides(
                  meta?.override_coach_for_lines ?? false,
                  meta?.override_coach_for_strategy ?? false,
                  e.target.checked,
                )
              }
              disabled={!meta}
            />
            Auto Injury Moves
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
      {autoActionToast ? <div className="card">{autoActionToast}</div> : null}

      <nav className="top-nav-shell">
        <div className="scope-toggle">
          <button className={navScope === "league" ? "scope-btn active" : "scope-btn"} onClick={() => handleScopeChange("league")}>
            League
          </button>
          <button className={navScope === "team" ? "scope-btn active" : "scope-btn"} onClick={() => handleScopeChange("team")}>
            Team{inboxEvents.length > 0 ? ` (${inboxEvents.length})` : ""}
          </button>
        </div>
        {navScope === "league" && inboxEvents.length > 0 ? (
          <button className="tab" onClick={() => openHomePage()}>
            Tasks ({inboxEvents.length})
          </button>
        ) : null}
        <div className="top-nav">
          {(navScope === "league" ? leagueNav : teamNav).map(([key, label]) => (
            <button
              key={key}
              className={mainNav === key ? "top-nav-btn active" : "top-nav-btn"}
              onClick={() => handleNavSelect(key)}
            >
              {label}
            </button>
          ))}
        </div>
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
              <p className="muted small">Clinch: X playoffs | Y division | Z conference | P best league record</p>
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

      {mainNav === "cup_history" ? (
        <section className="card">
          <h2>Cup Champion History</h2>
          <table>
            <thead>
              <tr>
                <th>Season</th><th>Winner</th><th>Captain</th><th>Coach</th><th>Runner-Up</th><th>Captain</th><th>Coach</th><th>Series</th><th>MVP</th>
              </tr>
            </thead>
            <tbody>
              {cupHistoryRows.map((r) => (
                <tr key={`cup-${r.season}`}>
                  <td>{r.season}</td>
                  <td className="team-cell">{r.winner_logo_url ? <img className="table-logo" src={logoUrl(r.winner_logo_url)} alt={r.winner} /> : null}<span>{r.winner}</span></td>
                  <td>{r.winner_captain}</td>
                  <td>{r.winner_coach}</td>
                  <td className="team-cell">{r.runner_logo_url ? <img className="table-logo" src={logoUrl(r.runner_logo_url)} alt={r.runner_up} /> : null}<span>{r.runner_up}</span></td>
                  <td>{r.runner_captain}</td>
                  <td>{r.runner_coach}</td>
                  <td>{r.series ?? "-"}</td>
                  <td>{r.mvp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {mainNav === "league_news" ? (
        <section className="card">
          <h2>League News</h2>
          {leagueNews.length === 0 ? (
            <p>No league news posted yet.</p>
          ) : (
            <div className="results">
              {leagueNews.map((n, idx) => (
                <div key={`league-news-${idx}-${n.headline}`} className="line">
                  S{n.season} {n.day > 0 ? `D${n.day}` : "Offseason"} | {n.headline}{n.details ? ` - ${n.details}` : ""}
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {mainNav === "league_stats" ? (
        <section className="card leaders">
          <div className="section-head">
            <h2>Stats</h2>
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
              <LeaderBlock
                title="Shutouts"
                valueLabel="SO"
                rows={goalies}
                getValue={(g) => g.so}
                formatValue={(v) => `${v}`}
                onPick={(g) => void openPlayerCareer(g.team, g.name)}
              />
            </div>
          </div>
        </section>
      ) : null}

      {mainNav === "awards" ? (
        <section className="card">
          <h2>Season {awardsData?.season ?? meta?.season ?? "-"} Awards & Storylines</h2>
          <div className="split">
            <div>
              <h3>Hart Trophy Race</h3>
              <table className="banded">
                <thead><tr><th>Player</th><th>Team</th><th>GP</th><th>G</th><th>A</th><th>P</th><th>+/-</th></tr></thead>
                <tbody>
                  {(awardsData?.races?.hart ?? []).map((r, idx) => (
                    <tr key={`hart-${r.team}-${r.name}-${idx}`}>
                      <td className="text-link" onClick={() => void openPlayerCareer(r.team, r.name)}>{r.name}</td>
                      <td>{r.team}</td><td>{r.gp}</td><td>{r.g}</td><td>{r.a}</td><td>{r.p}</td><td>{r.plus_minus ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3>Rocket Richard Race</h3>
              <table className="banded">
                <thead><tr><th>Player</th><th>Team</th><th>G</th><th>P</th></tr></thead>
                <tbody>
                  {(awardsData?.races?.rocket ?? []).map((r, idx) => (
                    <tr key={`rocket-${r.team}-${r.name}-${idx}`}>
                      <td className="text-link" onClick={() => void openPlayerCareer(r.team, r.name)}>{r.name}</td>
                      <td>{r.team}</td><td>{r.g}</td><td>{r.p}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h3>Vezina Trophy Race</h3>
              <table className="banded">
                <thead><tr><th>Goalie</th><th>Team</th><th>GP</th><th>W</th><th>SO</th><th>GAA</th><th>SV%</th></tr></thead>
                <tbody>
                  {(awardsData?.races?.vezina ?? []).map((r, idx) => (
                    <tr key={`vezina-${r.team}-${r.name}-${idx}`}>
                      <td className="text-link" onClick={() => void openPlayerCareer(r.team, r.name)}>{r.name}</td>
                      <td>{r.team}</td><td>{r.gp}</td><td>{r.w}</td><td>{r.so}</td><td>{r.gaa.toFixed(2)}</td><td>{r.sv_pct.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3>Playoff MVP Watch</h3>
              {(awardsData?.playoff_mvp_race ?? []).length === 0 ? (
                <p className="muted">Starts once playoff games are played.</p>
              ) : (
                <table className="banded">
                  <thead><tr><th>Player</th><th>Team</th><th>Summary</th></tr></thead>
                  <tbody>
                    {(awardsData?.playoff_mvp_race ?? []).map((r, idx) => (
                      <tr key={`mvpwatch-${r.team}-${r.name}-${idx}`}>
                        <td>{r.name}</td><td>{r.team}</td><td>{r.summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
          <div className="split">
            <div>
              <h3>Season Storylines</h3>
              {(awardsData?.storylines ?? []).length === 0 ? (
                <p className="muted">No major storyline flagged right now.</p>
              ) : (
                <ul>
                  {(awardsData?.storylines ?? []).map((s, idx) => <li key={`story-${idx}`}>{s}</li>)}
                </ul>
              )}
              <h3>Record Chases (League)</h3>
              {(awardsData?.record_chases?.league ?? []).length === 0 ? (
                <p className="muted">No active league record chases in range.</p>
              ) : (
                <table className="banded">
                  <thead><tr><th>Category</th><th>Challenger</th><th>Gap</th><th>Record</th></tr></thead>
                  <tbody>
                    {(awardsData?.record_chases?.league ?? []).map((r, idx) => (
                      <tr key={`leaguechase-${idx}`}>
                        <td>{r.category}</td><td>{r.challenger} ({r.challenger_team})</td><td>{r.gap}</td><td>{r.record_holder} ({r.record_value})</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <h3>Record Chases (Franchise)</h3>
              {(awardsData?.record_chases?.franchise ?? []).length === 0 ? (
                <p className="muted">No active franchise record chases in range.</p>
              ) : (
                <table className="banded">
                  <thead><tr><th>Category</th><th>Challenger</th><th>Gap</th><th>Record</th></tr></thead>
                  <tbody>
                    {(awardsData?.record_chases?.franchise ?? []).map((r, idx) => (
                      <tr key={`franchisechase-${idx}`}>
                        <td>{r.category}</td><td>{r.challenger}</td><td>{r.gap}</td><td>{r.record_holder} ({r.record_value})</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div>
              <h3>Recent Milestones</h3>
              {(awardsData?.milestones ?? []).length === 0 ? (
                <p className="muted">No milestones logged yet this season.</p>
              ) : (
                <div className="results">
                  {(awardsData?.milestones ?? []).map((m, idx) => (
                    <div key={`mile-${idx}`} className="line">
                      S{m.season} {m.day > 0 ? `D${m.day}` : "Offseason"} | {m.headline}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      ) : null}

      {mainNav === "team_stats" ? (
        <section className="card leaders">
          <div className="section-head">
            <h2>{meta?.user_team ?? "My Team"} Stats</h2>
          </div>
          <h3>Team Leaders</h3>
          <div className="team-leaders-strip">
            {teamLeaders.map((leader) => (
              <div
                key={`tl-${leader.key}`}
                className={`team-leader-card ${leader.player ? "row-clickable" : ""}`}
                onClick={() => {
                  if (leader.player) void openPlayerCareer(leader.player.team, leader.player.name);
                }}
              >
                <div className="muted small">{leader.label}</div>
                <div className="team-leader-name">{leader.player?.name ?? "-"}</div>
                <div className="team-leader-value">{leader.value}</div>
              </div>
            ))}
          </div>
          <div className="split team-stats-split">
            <div><h3>Skaters</h3><table className="banded skaters-table"><thead><tr><th>Player</th><th>Pos</th><th>GP</th><th>G</th><th>A</th><th>P</th><th>+/-</th><th>PIM</th><th>TOI/G</th><th>PPG</th><th>PPA</th><th>SHG</th><th>SHA</th><th>S</th><th>S%</th><th>Out</th></tr></thead><tbody>
              {teamPlayers.map((p) => (
                <tr key={`${p.team}-${p.name}`} className="row-clickable" onClick={() => void openPlayerCareer(p.team, p.name)}>
                  <td className="name-cell nowrap">{renderInjuryChip(p.injury_status, p.injured)}{playerLabel(p.name, p.jersey_number)}</td><td>{p.position}</td><td>{p.gp}</td><td>{p.g}</td><td>{p.a}</td><td>{p.p}</td><td>{p.plus_minus}</td><td>{p.pim}</td><td>{p.toi_g.toFixed(1)}</td><td>{p.ppg}</td><td>{p.ppa}</td><td>{p.shg}</td><td>{p.sha}</td><td>{p.shots}</td><td>{p.shot_pct.toFixed(1)}</td><td>{(p.injured || (p.injury_status ?? "").toUpperCase().includes("DTD")) ? <span className="neg">{p.injured_games_remaining ?? 0}</span> : "-"}</td>
                </tr>
              ))}
            </tbody></table></div>
            <div><h3>Goalies</h3><table className="banded goalies-table"><thead><tr><th>Goalie</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>SO</th><th>GAA</th><th>SV%</th><th>Out</th></tr></thead><tbody>
              {teamGoalies.map((g) => (
                <tr key={`${g.team}-${g.name}`} className="row-clickable" onClick={() => void openPlayerCareer(g.team, g.name)}>
                  <td className="name-cell nowrap">{renderInjuryChip(g.injury_status, g.injured)}{playerLabel(g.name, g.jersey_number)}</td><td>{g.gp}</td><td>{g.w}</td><td>{g.l}</td><td>{g.otl}</td><td>{g.so}</td><td>{g.gaa.toFixed(2)}</td><td>{g.sv_pct.toFixed(3)}</td><td>{(g.injured || (g.injury_status ?? "").toUpperCase().includes("DTD")) ? <span className="neg">{g.injured_games_remaining ?? 0}</span> : "-"}</td>
                </tr>
              ))}
            </tbody></table></div>
          </div>
        </section>
      ) : null}

      {mainNav === "legacy" ? (
        <section className="card">
          <div className="section-head">
            <h2>{meta?.user_team ?? "Team"} Legacy</h2>
            <div className="inline-controls">
              <button className={legacyTab === "history" ? "active" : ""} onClick={() => setLegacyTab("history")}>History</button>
              <button className={legacyTab === "banners" ? "active" : ""} onClick={() => setLegacyTab("banners")}>Banners</button>
              <button className={legacyTab === "records" ? "active" : ""} onClick={() => setLegacyTab("records")}>Records</button>
            </div>
          </div>
          {legacyTab === "history" ? (
            <>
              <h3>Season History</h3>
              <table>
                <thead><tr><th>Season</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>Pts</th><th>Conf Rank</th><th>Div Rank</th><th>Playoff</th><th>Playoff Result</th><th>Cup</th></tr></thead>
                <tbody>{(franchise?.history ?? []).map((h) => <tr key={`legacy-h-${h.season}`}><td>{h.season}</td><td>{h.gp}</td><td>{h.w}</td><td>{h.l}</td><td>{h.otl}</td><td>{h.pts}</td><td>{h.conference_rank}</td><td>{h.division_rank}</td><td>{h.playoff}</td><td>{h.playoff_result}</td><td>{h.cup_winner}</td></tr>)}</tbody>
              </table>
              <div className="split">
                <div>
                  <h3>Draft Results</h3>
                  <table>
                    <thead><tr><th>Season</th><th>Player</th><th>Pos</th><th>Pick</th></tr></thead>
                    <tbody>
                      {(franchise?.draft_picks ?? []).slice(0, 30).map((d, idx) => (
                        <tr key={`legacy-d-${idx}-${d.season}-${d.name}`} className="row-clickable" onClick={() => void openPlayerCareer(d.team ?? (meta?.user_team ?? ""), d.name)}>
                          <td>{d.season}</td><td><span className="text-link">{d.name}</span></td><td>{d.position}</td><td>R{d.round} #{d.overall}</td>
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
                      {(franchise?.retired ?? []).slice(0, 30).map((r, idx) => (
                        <tr key={`legacy-r-${idx}-${r.season}-${r.entry}`} className={r.name ? "row-clickable" : ""} onClick={() => (r.name ? void openPlayerCareer(r.team ?? (meta?.user_team ?? ""), r.name) : undefined)}>
                          <td>{r.season}</td><td>{r.name ? <span className="text-link">{r.entry}</span> : r.entry}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}
          {legacyTab === "banners" ? (
            <>
              <h3>{bannersData?.team ?? (meta?.user_team ?? "Team")} Arena Banners</h3>
              {(bannersData?.banners ?? []).length > 0 ? (
                <div className="banner-grid">
                  {(bannersData?.banners ?? []).map((b, idx) => (
                    <div key={`legacy-banner-${b.kind}-${b.season}-${idx}`} className="arena-banner">
                      <div className="banner-hang" />
                      <div
                        className="banner-fabric"
                        style={
                          {
                            "--banner-primary": bannersData?.primary_color ?? "#1f3a93",
                            "--banner-secondary": bannersData?.secondary_color ?? "#d7e1f5",
                          } as Record<string, string>
                        }
                      >
                        {b.kind === "retired_number" ? (
                          <>
                            <div className="retired-player">{(b.player ?? "").toUpperCase()}</div>
                            <div className="retired-number">{b.number ?? "-"}</div>
                            <div className="retired-stripe" />
                            <div className="retired-years">
                              <span>{typeof b.start_year === "number" ? `S${b.start_year}` : "-"}</span>
                              {bannersData?.logo_url ? <img className="retired-mini-logo" src={logoUrl(bannersData.logo_url)} alt={b.team} /> : null}
                              <span>{typeof b.end_year === "number" ? `S${b.end_year}` : "-"}</span>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="banner-team">{b.team.toUpperCase()}</div>
                            {bannersData?.logo_url ? <img className="banner-logo" src={logoUrl(bannersData.logo_url)} alt={b.team} /> : null}
                            <div className="banner-title">{b.title.toUpperCase()}</div>
                            <div className="banner-season">SEASON {b.season}</div>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No banners yet for this franchise.</p>
              )}
            </>
          ) : null}
          {legacyTab === "records" ? (
            <>
              <h3>{recordsData?.team ?? (meta?.user_team ?? "Team")} Franchise Records</h3>
              {(recordsData?.franchise ?? []).map((table) => (
                <div key={`legacy-rec-${table.key}`}>
                  <h3>{table.label}</h3>
                  <table className="banded">
                    <thead>
                      <tr><th>Player</th><th>Pos</th><th>Value</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row) => (
                        <tr key={`legacy-rec-row-${table.key}-${row.team}-${row.name}`}>
                          <td>
                            <span className="text-link" onClick={() => void openPlayerCareer(row.team, row.name)}>{row.name}</span>
                          </td>
                          <td>{row.position}</td>
                          <td>{row.value}</td>
                          <td>{row.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </>
          ) : null}
        </section>
      ) : null}

      {mainNav === "records" ? (
        <section className="card">
          <h2>{recordsData?.team ?? (meta?.user_team ?? "Team")} Franchise Records</h2>
          {(recordsData?.franchise ?? []).map((table) => (
            <div key={`franchise-rec-${table.key}`}>
              <h3>{table.label}</h3>
              <table className="banded">
                <thead>
                  <tr><th>Player</th><th>Pos</th><th>Value</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {table.rows.map((row) => (
                    <tr key={`franchise-rec-row-${table.key}-${row.team}-${row.name}`}>
                      <td>
                        <span className="text-link" onClick={() => void openPlayerCareer(row.team, row.name)}>{row.name}</span>
                      </td>
                      <td>{row.position}</td>
                      <td>{row.value}</td>
                      <td>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>
      ) : null}

      {mainNav === "league_records" ? (
        <section className="card">
          <h2>League Records</h2>
          {(recordsData?.league ?? []).map((table) => (
            <div key={`league-rec-${table.key}`}>
              <h3>{table.label}</h3>
              <table className="banded">
                <thead>
                  <tr><th>Player</th><th>Team</th><th>Pos</th><th>Value</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {table.rows.map((row) => (
                    <tr key={`league-rec-row-${table.key}-${row.team}-${row.name}`}>
                      <td>
                        <span className="text-link" onClick={() => void openPlayerCareer(row.team, row.name)}>{row.name}</span>
                      </td>
                      <td>{row.team}</td>
                      <td>{row.position}</td>
                      <td>{row.value}</td>
                      <td>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>
      ) : null}

      {mainNav === "banners" ? (
        <section className="card">
          <h2>{bannersData?.team ?? (meta?.user_team ?? "Team")} Arena Banners</h2>
          {(bannersData?.banners ?? []).length > 0 ? (
            <div className="banner-grid">
              {(bannersData?.banners ?? []).map((b, idx) => (
                <div key={`banner-${b.kind}-${b.season}-${idx}`} className="arena-banner">
                  <div className="banner-hang" />
                  <div
                    className="banner-fabric"
                      style={
                        {
                          "--banner-primary": bannersData?.primary_color ?? "#1f3a93",
                        "--banner-secondary": bannersData?.secondary_color ?? "#d7e1f5",
                      } as Record<string, string>
                    }
                  >
                    {b.kind === "retired_number" ? (
                      <>
                        <div className="retired-player">{(b.player ?? "").toUpperCase()}</div>
                        <div className="retired-number">{b.number ?? "-"}</div>
                        <div className="retired-stripe" />
                        <div className="retired-years">
                          <span>{typeof b.start_year === "number" ? `S${b.start_year}` : "-"}</span>
                          {bannersData?.logo_url ? <img className="retired-mini-logo" src={logoUrl(bannersData.logo_url)} alt={b.team} /> : null}
                          <span>{typeof b.end_year === "number" ? `S${b.end_year}` : "-"}</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="banner-team">{b.team.toUpperCase()}</div>
                        {bannersData?.logo_url ? <img className="banner-logo" src={logoUrl(bannersData.logo_url)} alt={b.team} /> : null}
                        <div className="banner-title">{b.title.toUpperCase()}</div>
                        <div className="banner-season">SEASON {b.season}</div>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">No banners yet for this franchise.</p>
          )}
        </section>
      ) : null}

      {mainNav === "trade_center" ? (
        <section className="card">
          <div className="section-head">
            <h2>{meta?.user_team ?? "Team"} Trade Center</h2>
          </div>
          <div className="split">
            <div className="trade-box">
              <h3>Your Team Needs</h3>
              <p className="muted small">
                Window: {tradeMarket?.my_needs?.window ?? "-"} | Primary: {needLabel(tradeMarket?.my_needs?.primary_need ?? "-")}
              </p>
              <div className="inline-controls">
                <label>
                  Mode{" "}
                  <select
                    value={needsMode}
                    onChange={(e) => setNeedsMode(e.target.value as "auto" | "manual")}
                  >
                    <option value="auto">Auto</option>
                    <option value="manual">Manual</option>
                  </select>
                </label>
                <button onClick={() => void saveTeamNeeds(needsMode)}>
                  Save Needs
                </button>
                <button onClick={() => void saveTeamNeeds("auto")}>
                  Reset Auto
                </button>
              </div>
              <div className="needs-grid">
                {needKeys(tradeMarket?.my_needs).map((k) => (
                  <div key={`my-need-${k}`} className="need-row">
                    <span>{needLabel(k)}</span>
                    {needsMode === "manual" ? (
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        value={Number(needsDraft[k] ?? 0).toFixed(2)}
                        onChange={(e) => {
                          const next = Number.parseFloat(e.target.value);
                          const normalized = Number.isFinite(next) ? Math.max(0, Math.min(1, next)) : 0;
                          setNeedsDraft((prev) => ({ ...prev, [k]: Number(normalized.toFixed(3)) }));
                        }}
                      />
                    ) : (
                      <strong>{Number((tradeMarket?.my_needs?.scores ?? {})[k] ?? 0).toFixed(2)}</strong>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="trade-box">
              <h3>Partner Needs</h3>
              <p className="muted small">
                Team: {tradeMarket?.partner_team || "-"} | Window: {tradeMarket?.partner_needs?.window ?? "-"} | Primary: {needLabel(tradeMarket?.partner_needs?.primary_need ?? "-")}
              </p>
              <p className="muted small">
                Partner Shop: {partnerShopLine || "None published"}
                {" | "}Partner Available: {partnerAvailableCount}
              </p>
              <div className="needs-grid">
                {Object.entries(tradeMarket?.partner_needs?.scores ?? {}).map(([k, v]) => (
                  <div key={`partner-need-${k}`} className="need-row">
                    <span>{needLabel(k)}</span>
                    <strong>{Number(v).toFixed(2)}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="trade-box">
            <h3>Propose Trade</h3>
            <p className="muted small">
              Shop: {shopNames.length > 0 ? shopNames.join(", ") : "None"}
              {" | "}Available: {availableCount}
            </p>
            <div className="inline-controls">
              <label>
                Partner{" "}
                <select
                  value={tradePartner}
                  onChange={(e) => { void onChangeTradePartner(e.target.value); }}
                >
                  <option value="">Select Team</option>
                  {(tradeMarket?.partners ?? []).map((name) => (
                    <option key={`trade-partner-${name}`} value={name}>{name}</option>
                  ))}
                </select>
              </label>
              <label>
                You Send{" "}
                <select
                  value={tradeGivePlayer}
                  onChange={(e) => setTradeGivePlayer(e.target.value)}
                >
                  <option value="">Select Player</option>
                  {(tradeMarket?.my_assets ?? []).map((p) => (
                    <option key={`trade-give-${p.name}`} value={p.name}>
                      {p.name} ({p.position}) OVR {p.overall.toFixed(2)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                You Receive{" "}
                <select
                  value={tradeReceivePlayer}
                  onChange={(e) => setTradeReceivePlayer(e.target.value)}
                  disabled={!tradePartner}
                >
                  <option value="">Select Player</option>
                  {filteredPartnerAssets.map((p) => (
                    <option key={`trade-receive-${p.name}`} value={p.name}>
                      {p.name} ({p.position}) OVR {p.overall.toFixed(2)} [{(p.trade_preference ?? "available").toUpperCase()}]
                    </option>
                  ))}
                </select>
              </label>
              <div className="inline-controls">
                <span className="muted small">Receive Pool</span>
                {([
                  ["all", "All"],
                  ["shop", "Shop"],
                  ["available", "Available"],
                ] as const).map(([key, label]) => (
                  <button
                    key={`receive-pool-${key}`}
                    className={tradeReceivePool === key ? "btn-chip active" : "btn-chip"}
                    onClick={() => setTradeReceivePool(key)}
                    type="button"
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => void evaluateTrade()}
                disabled={!tradePartner || !tradeGivePlayer || !tradeReceivePlayer}
              >
                Evaluate Trade
              </button>
              <button
                onClick={() => void proposeTrade()}
                disabled={!tradePartner || !tradeGivePlayer || !tradeReceivePlayer}
              >
                Propose Trade
              </button>
            </div>
            <p className="muted small">Offers are scored against the same team-needs model used by CPU GMs.</p>
            {tradePreview && !tradePreview.ok ? (
              <p className="muted small">Cannot evaluate this offer right now: {tradePreview.reason ?? "invalid offer"}.</p>
            ) : null}
            {tradePreview?.ok && tradePreview.insight ? (
              <div className="trade-offer-eval">
                {(() => {
                  const insight = tradePreview.insight as TradeInsight;
                  const comparison = insight.comparison ?? {};
                  const give = comparison.give ?? {};
                  const receive = comparison.receive ?? {};
                  const delta = comparison.delta ?? {};
                  const needFit = insight.need_fit ?? {};
                  const value = insight.value ?? {};
                  const reasons = Array.isArray(insight.reasons) ? insight.reasons : [];
                  const renderDetailStats = (player: { position?: unknown; stats?: unknown }) => {
                    const pos = String(player.position ?? "");
                    const stats = (player.stats ?? {}) as Record<string, unknown>;
                    if (pos === "G") {
                      return `GP ${Number(stats.gp ?? 0)} | W ${Number(stats.w ?? 0)} | L ${Number(stats.l ?? 0)} | SO ${Number(stats.so ?? 0)} | GAA ${Number(stats.gaa ?? 0).toFixed(2)} | SV% ${Number(stats.sv_pct ?? 0).toFixed(3)}`;
                    }
                    return `GP ${Number(stats.gp ?? 0)} | G ${Number(stats.g ?? 0)} | A ${Number(stats.a ?? 0)} | P ${Number(stats.p ?? 0)} | +/- ${Number(stats.plus_minus ?? 0)} | PIM ${Number(stats.pim ?? 0)}`;
                  };
                  const renderRatings = (player: { ratings?: unknown }) => {
                    const r = (player.ratings ?? {}) as Record<string, unknown>;
                    return `Shot ${Number(r.shooting ?? 0).toFixed(2)} | Play ${Number(r.playmaking ?? 0).toFixed(2)} | Def ${Number(r.defense ?? 0).toFixed(2)} | Glt ${Number(r.goaltending ?? 0).toFixed(2)} | Phys ${Number(r.physical ?? 0).toFixed(2)} | Dur ${Number(r.durability ?? 0).toFixed(2)}`;
                  };
                  return (
                    <>
                      <div className="trade-offer-head">
                        <strong>{String(insight.verdict ?? "Offer")}</strong>
                        <span className="muted small">Accept odds: {(Number(insight.accept_probability ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="trade-compare-grid">
                        <div className="trade-compare-card">
                          <div className="muted small">You Send</div>
                          <div className="text-link" onClick={() => void openPlayerCareer(String(meta?.user_team ?? ""), String(give.name ?? ""))}>{String(give.name ?? "-")}</div>
                          <div className="muted small">{String(give.position ?? "-")} | Age {String(give.age ?? "-")} | OVR {Number(give.overall ?? 0).toFixed(2)}</div>
                          <div className="muted small">Cap ${Number(give.cap_hit ?? 0).toFixed(2)}M | Years {String(give.years_left ?? "-")}</div>
                          <div className="muted small">{renderDetailStats(give)}</div>
                          <div className="muted small">{renderRatings(give)}</div>
                        </div>
                        <div className="trade-compare-card">
                          <div className="muted small">You Receive</div>
                          <div className="text-link" onClick={() => void openPlayerCareer(String(tradePartner), String(receive.name ?? ""))}>{String(receive.name ?? "-")}</div>
                          <div className="muted small">{String(receive.position ?? "-")} | Age {String(receive.age ?? "-")} | OVR {Number(receive.overall ?? 0).toFixed(2)}</div>
                          <div className="muted small">Cap ${Number(receive.cap_hit ?? 0).toFixed(2)}M | Years {String(receive.years_left ?? "-")}</div>
                          <div className="muted small">{renderDetailStats(receive)}</div>
                          <div className="muted small">{renderRatings(receive)}</div>
                        </div>
                      </div>
                      <div className="muted small">
                        Delta: OVR {(Number(delta.overall ?? 0) >= 0 ? "+" : "") + Number(delta.overall ?? 0).toFixed(2)}
                        {" | "}Age {(Number(delta.age ?? 0) >= 0 ? "+" : "") + String(delta.age ?? 0)}
                        {" | "}Cap {(Number(delta.cap_hit ?? 0) >= 0 ? "+" : "") + Number(delta.cap_hit ?? 0).toFixed(2)}M
                        {" | "}Years {(Number(delta.years_left ?? 0) >= 0 ? "+" : "") + String(delta.years_left ?? 0)}
                      </div>
                      <div className="muted small">
                        Need fit: You need {needLabel(String(needFit.user_primary_need ?? "-"))}
                        {Boolean(needFit.receive_matches_user_need) ? " (matched)" : " (not matched)"}
                        {" | "}Partner needs {needLabel(String(needFit.partner_primary_need ?? "-"))}
                        {Boolean(needFit.give_matches_partner_need) ? " (matched)" : " (not matched)"}
                      </div>
                      <div className="muted small">
                        Model value: You {Number(value.user_net ?? 0) >= 0 ? "+" : ""}{Number(value.user_net ?? 0).toFixed(2)} vs min {Number(value.user_min ?? 0) >= 0 ? "+" : ""}{Number(value.user_min ?? 0).toFixed(2)}
                        {" | "}Partner {Number(value.partner_net ?? 0) >= 0 ? "+" : ""}{Number(value.partner_net ?? 0).toFixed(2)} vs min {Number(value.partner_min ?? 0) >= 0 ? "+" : ""}{Number(value.partner_min ?? 0).toFixed(2)}
                      </div>
                      {reasons.length > 0 ? (
                        <ul className="trade-reasons">
                          {reasons.map((r, idx) => <li key={`trade-preview-reason-${idx}`}>{r}</li>)}
                        </ul>
                      ) : null}
                    </>
                  );
                })()}
              </div>
            ) : null}
          </div>

          <div className="trade-box">
            <h3>Incoming Trade Offers</h3>
            {inboxEvents.filter((ev) => ev.type === "trade_offer").length === 0 ? (
              <p className="muted">No active trade offers right now.</p>
            ) : (
              <div className="score-list">
                {inboxEvents.filter((ev) => ev.type === "trade_offer").map((ev) => (
                  <article key={`trade-center-inbox-${ev.id}`} className="score-card">
                    <h3>{ev.title}</h3>
                    <div className="muted small">S{ev.season} D{ev.day} | Expires D{ev.expires_day}</div>
                    <p>{ev.details}</p>
                    <div className="inline-controls">
                      <button onClick={() => void loadIncomingTradeOffer(ev)}>Review In Evaluation</button>
                      {ev.options.map((opt) => (
                        <span key={`${ev.id}-${opt.id}`} title={opt.description}>
                          <button onClick={() => void resolveInboxEvent(ev.id, opt.id)}>
                            {opt.label}
                          </button>
                        </span>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      ) : null}

      {mainNav === "transactions" ? (
        <section className="card">
          <div className="section-head">
            <h2>{meta?.user_team ?? "Team"} Transactions</h2>
            <label>
              Season{" "}
              <select
                value={transactionSeason}
                onChange={(e) => setTransactionSeason(e.target.value)}
              >
                <option value="all">All</option>
                {transactionSeasons.map((s) => (
                  <option key={`tx-season-${s}`} value={String(s)}>S{s}</option>
                ))}
              </select>
            </label>
          </div>
          <nav className="tabs">
            {[
              ["all", "All"],
              ["trades", "Trades"],
              ["callups", "Call Ups"],
              ["injuries", "Injuries"],
              ["signings", "Signings"],
            ].map(([key, label]) => (
              <button
                key={`tx-filter-${key}`}
                className={transactionFilter === key ? "tab active" : "tab"}
                onClick={() => setTransactionFilter(key as TransactionFilter)}
              >
                {label}
              </button>
            ))}
          </nav>
          {filteredTransactions.length === 0 ? (
            <p>No transactions logged for your team yet.</p>
          ) : (
            <div className="results">
              {filteredTransactions.map((t, idx) => (
                <div key={`tx-${idx}-${t.headline}`} className="line">
                  S{t.season} {t.day > 0 ? `D${t.day}` : "Offseason"} | {t.headline}{t.details ? ` - ${t.details}` : ""}
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {mainNav === "contracts" ? (
        <section className="card">
          <div className="section-head">
            <h2>{contractsData?.team ?? (meta?.user_team ?? "Team")} Contracts</h2>
          </div>
          <p className="muted">
            Cap: ${contractsData?.cap_used?.toFixed(2) ?? "0.00"}M / ${contractsData?.cap_limit?.toFixed(2) ?? "0.00"}M
            {" | "}Space: ${contractsData?.cap_space?.toFixed(2) ?? "0.00"}M
            {" | "}Active: {contractsData?.active_count ?? 0}/{contractsData?.max_active ?? 22}
          </p>
          <div className="split">
            <div>
              <h3>Active Roster Contracts</h3>
              <table className="banded">
                <thead>
                  <tr><th>Player</th><th>Pos</th><th>Age</th><th>Years</th><th>AAV</th><th>Type</th><th>RFA</th><th>Action</th></tr>
                </thead>
                <tbody>
                  {(contractsData?.active ?? []).map((r) => (
                    <tr key={`ctr-a-${r.name}`} className="row-clickable" onClick={() => void openPlayerCareer(r.team, r.name)}>
                      <td>{r.name}</td>
                      <td>{r.position}</td>
                      <td>{r.age}</td>
                      <td>{r.years_left}</td>
                      <td>${r.cap_hit.toFixed(2)}M</td>
                      <td>{r.contract_type}</td>
                      <td>{r.is_rfa ? "Y" : "N"}</td>
                      <td>
                        {r.years_left <= 1 ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              void extendContract(r.name);
                            }}
                          >
                            Extend
                          </button>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h3>Minor League Contracts</h3>
              <table className="banded">
                <thead>
                  <tr><th>Player</th><th>Pos</th><th>Age</th><th>Years</th><th>AAV</th><th>Type</th><th>RFA</th><th>Action</th></tr>
                </thead>
                <tbody>
                  {(contractsData?.minors ?? []).map((r) => (
                    <tr key={`ctr-m-${r.name}`} className="row-clickable" onClick={() => void openPlayerCareer(r.team, r.name)}>
                      <td>{r.name}</td>
                      <td>{r.position}</td>
                      <td>{r.age}</td>
                      <td>{r.years_left}</td>
                      <td>${r.cap_hit.toFixed(2)}M</td>
                      <td>{r.contract_type}</td>
                      <td>{r.is_rfa ? "Y" : "N"}</td>
                      <td>
                        {r.years_left <= 1 ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              void extendContract(r.name);
                            }}
                          >
                            Extend
                          </button>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {mainNav === "free_agents" ? (
        <section className="card">
          <div className="section-head">
            <h2>Free Agents</h2>
          </div>
          <p className="muted">
            Team: {freeAgentsData?.team ?? (meta?.user_team ?? "-")}
            {" | "}Cap: ${freeAgentsData?.cap_used?.toFixed(2) ?? "0.00"}M / ${freeAgentsData?.cap_limit?.toFixed(2) ?? "0.00"}M
            {" | "}Space: ${freeAgentsData?.cap_space?.toFixed(2) ?? "0.00"}M
          </p>
          <table className="banded">
            <thead>
              <tr><th>Player</th><th>Pos</th><th>Age</th><th>OVR</th><th>Ask</th><th>Type</th><th>From</th><th>Action</th></tr>
            </thead>
            <tbody>
              {(freeAgentsData?.rows ?? []).map((r) => (
                <tr key={`fa-${r.name}`}>
                  <td>{r.name}</td>
                  <td>{r.position}</td>
                  <td>{r.age}</td>
                  <td>{r.overall.toFixed(2)}</td>
                  <td>{r.ask_years}y @ ${r.ask_cap_hit.toFixed(2)}M</td>
                  <td>{r.contract_type}</td>
                  <td>{r.origin_team ? `${r.origin_team}${r.is_user_origin ? " (Your rights)" : ""}` : "-"}</td>
                  <td>
                    <button onClick={() => void signFreeAgent(r.name, r.ask_years, r.ask_cap_hit)}>
                      Sign
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {mainNav === "callups" ? (
        <section className="card">
          <h2>{callupsData?.team ?? (meta?.user_team ?? "Team")} Call Ups</h2>
          <p className="muted">
            Manage promotions from minors and send-downs when injuries hit.
            {" | "}Roster total: {callupsData?.total_count ?? 0}
            {" | "}Injured: {callupsData?.injured_count ?? 0}
            {" | "}Active roster: {callupsData?.active_count ?? 0}/{callupsData?.max_active ?? 22}
            {" | "}Projected next day: {callupsData?.projected_next_day_active ?? (callupsData?.active_count ?? 0)}/{callupsData?.max_active ?? 22}
          </p>
          {isActiveRosterFull ? <p className="neg small">Active roster is full. Send a player down before calling someone up.</p> : null}
          {(callupsData?.returning_tomorrow ?? []).length > 0 ? (
            <div>
              <h3>Returning Next Game Day</h3>
              <table className="banded">
                <thead><tr><th>Player</th><th>Pos</th><th>Type</th><th>Status</th></tr></thead>
                <tbody>
                  {(callupsData?.returning_tomorrow ?? []).map((r) => (
                    <tr key={`ret-${r.name}`}>
                      <td>{r.name}</td><td>{r.position}</td><td>{r.injury_type ?? "-"}</td><td>{r.injury_status ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <h3>Injury List</h3>
          {(callupsData?.injuries ?? []).length === 0 ? (
            <p className="muted">No active injuries.</p>
          ) : (
            <table className="banded">
              <thead><tr><th>Player</th><th>Pos</th><th>Type</th><th>Status</th><th>Games Out</th></tr></thead>
              <tbody>
                {(callupsData?.injuries ?? []).map((r) => (
                  <tr key={`inj-${r.name}`}>
                    <td>{r.name}</td><td>{r.position}</td><td>{r.injury_type ?? "-"}</td><td>{r.injury_status ?? "-"}</td><td className="neg">{r.games_out}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="split">
            <div>
              <h3>Roster</h3>
              <table className="banded">
                <thead><tr><th>Player</th><th>Pos</th><th>Age</th><th>OVR</th><th>Status</th><th>Action</th></tr></thead>
                <tbody>
                  {(callupsData?.roster ?? []).map((r) => (
                    <tr key={`roster-move-${r.name}`}>
                      <td><button onClick={() => void openPlayerCareer(String(meta?.user_team ?? ""), r.name)}>{r.name}</button></td>
                      <td>{r.position}</td>
                      <td>{r.age}</td>
                      <td>{r.overall.toFixed(2)}</td>
                      <td>{r.injured ? `IR ${r.games_out}` : (r.temporary_replacement_for ? `Temp for ${r.temporary_replacement_for}` : (r.dressed ? "Dressed" : "Active"))}</td>
                      <td><button onClick={() => void demoteRosterPlayer(r.name)}>Send Down</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h3>Minor League</h3>
              <table className="banded">
                <thead><tr><th>Player</th><th>Pos</th><th>Age</th><th>Tier</th><th>Years</th><th>OVR</th><th>Action</th></tr></thead>
                <tbody>
                  {(callupsData?.minors ?? []).map((r) => (
                    <tr key={`minor-move-${r.name}`}>
                      <td><button onClick={() => void openPlayerCareer(String(meta?.user_team ?? ""), r.name)}>{r.name}</button></td>
                      <td>{r.position}</td>
                      <td>{r.age}</td>
                      <td>{r.tier}</td>
                      <td>{r.seasons_to_nhl}</td>
                      <td>{r.overall.toFixed(2)}</td>
                      <td>
                        <button
                          onClick={() => void promoteCallup(r.name)}
                          disabled={r.injured || isActiveRosterFull}
                          title={isActiveRosterFull ? "Active roster full. Send a player down first." : ""}
                        >
                          Call Up
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {mainNav === "roster" ? (
        <section className="card">
          <h2>{rosterData?.team ?? (meta?.user_team ?? "Team")} Roster</h2>
          <p className="muted">
            Captain: {rosterData?.captain ?? "-"} | Assistants: {(rosterData?.assistants ?? []).length > 0 ? (rosterData?.assistants ?? []).join(", ") : "-"}
            {" | "}Shop: {shopNames.length > 0 ? shopNames.join(", ") : "None"}
            {" | "}Untouchable: {untouchableNames.length > 0 ? untouchableNames.join(", ") : "None"}
          </p>
          {rosterData ? (
            Object.entries(rosterData.groups).map(([groupName, rows]) => (
              <div key={`rg-${groupName}`}>
                <h3>{groupName}</h3>
                <table className="banded">
                  <thead>
                    <tr>
                      <th>Name</th><th>Age</th><th>HT</th><th>WT</th><th>Shot</th><th>Birth Place</th><th>Birthdate</th><th>Out</th><th>Trade Pref</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={`r-${groupName}-${r.name}`} className="row-clickable" onClick={() => void openPlayerCareer(r.team, r.name)}>
                        <td>{renderInjuryChip(r.injury_status, r.injured)}{playerLabel(r.name, r.jersey_number)}</td>
                        <td>{r.age}</td>
                        <td>{r.height}</td>
                        <td>{r.weight_lbs} lbs</td>
                        <td>{r.shot}</td>
                        <td>{r.birth_place}</td>
                        <td>{r.birthdate}</td>
                        <td>{r.injured ? <span className="neg">{r.injured_games_remaining ?? 0}</span> : "-"}</td>
                        <td>
                          <select
                            className={`trade-pref-select ${tradePrefOf(r.name)}`}
                            value={tradePrefOf(r.name)}
                            onChange={(e) => {
                              e.stopPropagation();
                              void updateTradeBlock(
                                r.name,
                                e.target.value as "shop" | "available" | "untouchable",
                              );
                            }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <option value="available">Available</option>
                            <option value="shop">Shop</option>
                            <option value="untouchable">Untouchable</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))
          ) : (
            <p>Loading roster...</p>
          )}
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
            Season {scoreBoard?.season ?? "-"} | {scoreBoard?.phase === "playoffs" ? `Playoffs${scoreBoard?.round ? ` - ${scoreBoard.round}` : ""}` : "Regular Season"} | {scoreBoard?.status === "played" ? "Final Scores" : "Scheduled Games"}
          </p>
          <div className="score-list">
            {(scoreBoard?.games ?? []).map((g, idx) => (
              <GameSummaryCard
                key={`score-${idx}`}
                game={g}
                teamLogos={meta?.team_logos}
                showCommentary={false}
                showTeamLabels={false}
                emphasizePlayoffSeries={true}
                seriesLineTop={true}
                omitSeriesRound={true}
              />
            ))}
          </div>
        </section>
      ) : null}

      {mainNav === "schedule" ? (
        <section className="card">
          <h2>{meta?.user_team ?? "Team"} Schedule</h2>
          {homePanel?.upcoming_game ? (
            <div className="score-card">
              <h3>Upcoming Game</h3>
              <p className="muted">
                {homePanel.upcoming_phase === "playoffs" ? "Playoff" : "Regular"} Day {homePanel.upcoming_game_day ?? "-"}
                {homePanel.upcoming_round ? ` | ${homePanel.upcoming_round}` : ""}
                {homePanel.upcoming_game.game_number ? ` | Game ${homePanel.upcoming_game.game_number}` : ""}
              </p>
              <p className="muted">
                {homePanel.upcoming_game.away} ({standingsRecordMap.get(homePanel.upcoming_game.away) ?? "-"}) at {homePanel.upcoming_game.home} ({standingsRecordMap.get(homePanel.upcoming_game.home) ?? "-"})
              </p>
            </div>
          ) : null}
          <table className="banded">
            <thead>
              <tr>
                <th>Day</th>
                <th>Opponent</th>
                <th>Result</th>
                <th>W-L-OTL</th>
                <th>{meta?.user_team ?? "Team"} Goalie</th>
                <th>Opponent Goalie</th>
                <th>3 Stars</th>
              </tr>
            </thead>
            <tbody>
              {scheduleGames.map((g, idx) => {
                const userTeam = meta?.user_team ?? "";
                const isHome = g.home === userTeam;
                const opponent = isHome ? g.away : g.home;
                const side = isHome ? "vs" : "@";
                const record = isHome ? (g.home_record ?? "-") : (g.away_record ?? "-");
                const teamGoalie = isHome ? (g.home_goalie || "-") : (g.away_goalie || "-");
                const oppGoalie = isHome ? (g.away_goalie || "-") : (g.home_goalie || "-");
                const starsText = (g.three_stars ?? [])
                  .slice(0, 3)
                  .map((s, sIdx) => `${"★".repeat(Math.min(3, sIdx + 1))} ${topStarName(s.summary)}`)
                  .join(" | ");
                return (
                  <tr key={`schedule-row-${idx}-${g.game_day ?? "x"}-${g.away}-${g.home}`}>
                    <td>{g.game_day ?? "-"}</td>
                    <td>
                      <div className="team-cell">
                        <span>{side} {opponent}</span>
                        {meta?.team_logos?.[opponent] ? <img className="mini-logo" src={logoUrl(meta.team_logos[opponent])} alt={opponent} /> : null}
                      </div>
                    </td>
                    <td>{formatScheduleResult(g, userTeam)}</td>
                    <td>{record}</td>
                    <td>{teamGoalie}</td>
                    <td>{oppGoalie}</td>
                    <td>{starsText || "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ) : null}

      {mainNav === "lines" ? (
        <section className="card">
          <h2>{linesData?.team ?? (meta?.user_team ?? "Team")} Lines</h2>
          <p className="muted">
            Coach: {linesData?.coach.name ?? "-"} ({linesData ? linesData.coach.rating.toFixed(2) : "-"}, {linesData?.coach.style ?? "-"})
          </p>
          <p className="muted">
            Roster total: {linesData?.total_count ?? 0} | Injured: {linesData?.injured_count ?? 0} | Active: {linesData?.active_count ?? 0}
          </p>
          <p className="muted">
            Position Penalty: {(linesData?.position_penalty ?? 0).toFixed(3)} | {linesData?.override_coach_for_lines ? "Manual Lines Enabled" : "Coach Controls Lines"}
          </p>
          <div className="inline-controls">
            {linesData?.override_coach_for_lines ? <button onClick={() => void saveLines()} disabled={!linesData}>Save Lines</button> : null}
            <button onClick={() => void autoSetBestLines()} disabled={!linesData}>Auto-Set Best Lines</button>
            {linesData?.override_coach_for_lines ? <button onClick={() => void loadLines()} disabled={!linesData}>Reset To Current</button> : null}
          </div>
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
                const linesTeam = linesData?.team ?? meta?.user_team ?? "";
                const slotId = (col: "LW" | "C" | "RW" | "LD" | "RD" | "G") => {
                  if (col === "LD" || col === "RD") return idx < 3 ? `${col}${idx + 1}` : "";
                  if (col === "G") return idx < 2 ? `G${idx + 1}` : "";
                  return `${col}${idx + 1}`;
                };
                const renderCell = (col: "LW" | "C" | "RW" | "LD" | "RD" | "G", item: { name: string; pos: string; flag?: string; out_of_position?: boolean } | null) => {
                  const id = slotId(col);
                  if (!id) return "-";
                  if (!(linesData?.override_coach_for_lines ?? false)) {
                    if (!item) return "-";
                      return (
                        <span
                          className={`text-link ${item.out_of_position ? "neg" : ""}`.trim()}
                          onClick={() => linesTeam ? void openPlayerCareer(linesTeam, item.name) : undefined}
                        >
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
          <h3>Extra Players</h3>
          {(linesData?.extra_players ?? []).length > 0 ? (
            <table>
              <thead>
                <tr><th>Player</th><th>Pos</th></tr>
              </thead>
              <tbody>
                {(linesData?.extra_players ?? []).map((p) => (
                  <tr key={`extra-${p.name}`} className="row-clickable" onClick={() => linesData?.team ? void openPlayerCareer(linesData.team, p.name) : undefined}>
                    <td>{p.name}</td>
                    <td>{p.pos}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No extra healthy players available.</p>
          )}
          <h3>Injury Report</h3>
          {(linesData?.injuries ?? []).length > 0 ? (
            <table>
              <thead>
                <tr><th>Player</th><th>Pos</th><th>Type</th><th>Out (Games)</th></tr>
              </thead>
              <tbody>
                {(linesData?.injuries ?? []).map((inj) => (
                  <tr key={`inj-${inj.name}`} className="row-clickable" onClick={() => linesData?.team ? void openPlayerCareer(linesData.team, inj.name) : undefined}>
                    <td className="name-cell nowrap">{renderInjuryChip(inj.injury_status, true)}{inj.name}</td>
                    <td>{inj.pos}</td>
                    <td>{inj.injury_type ?? "-"}</td>
                    <td>{inj.games_remaining}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No current injuries.</p>
          )}
        </section>
      ) : null}

      {mainNav === "minors" ? (
        <section className="card">
          <h2>{meta?.user_team ?? "Team"} Minor League</h2>
          <p className="muted">Farm-system players available for call-ups.</p>
          <table>
            <thead>
              <tr>
                <th>Player</th><th>Pos</th><th>Age</th><th>Tier</th><th>NHL ETA</th><th>Overall</th><th>Out</th>
              </tr>
            </thead>
            <tbody>
              {minorPlayers.map((p) => (
                <tr key={`minor-${p.team}-${p.name}`} className="row-clickable" onClick={() => void openPlayerCareer(p.team, p.name)}>
                  <td>{p.injured ? <span className="neg">IR </span> : null}{playerLabel(p.name, p.jersey_number)}</td>
                  <td>{p.position}</td>
                  <td>{p.age}</td>
                  <td>{p.tier}</td>
                  <td>{p.seasons_to_nhl}</td>
                  <td>{p.overall.toFixed(2)}</td>
                  <td>{p.injured ? <span className="neg">{p.injured_games_remaining ?? 0}</span> : "-"}</td>
                </tr>
              ))}
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
                        <tr key={`d-${idx}-${d.season}-${d.name}`} className="row-clickable" onClick={() => void openPlayerCareer(d.team ?? (meta?.user_team ?? ""), d.name)}>
                          <td>{d.season}</td><td><span className="text-link">{d.name}</span></td><td>{d.position}</td><td>R{d.round} #{d.overall}</td>
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
                        <tr key={`r-${idx}-${r.season}-${r.entry}`} className={r.name ? "row-clickable" : ""} onClick={() => (r.name ? void openPlayerCareer(r.team ?? (meta?.user_team ?? ""), r.name) : undefined)}>
                          <td>{r.season}</td><td>{r.name ? <span className="text-link">{r.entry}</span> : r.entry}</td>
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
          <div className="home-header">
            <div>
          <h2>
            {homePanel?.team ?? meta?.user_team ?? "Team"} Home
            <span className="cup-badges">
              {(homePanel?.cup_seasons ?? []).map((s) => <span key={`hc-${s}`} title={`Champion Season ${s}`}>🏆S{s}</span>)}
            </span>
          </h2>
          <p className="muted">
            Record {homePanel?.team_summary?.record ?? "-"} | {homePanel?.team_summary?.division ?? "-"} Division: {homePanel?.team_summary?.division_rank ?? "-"} place | {homePanel?.team_summary?.points ?? 0} pts
            {" | "}PP% {(homePanel?.team_summary?.pp_pct ?? 0).toFixed(3)} | PK% {(homePanel?.team_summary?.pk_pct ?? 0).toFixed(3)}
          </p>
            </div>
            <div className="home-sentiments">
              <div className="home-sentiment-card">
                <h3>Fan Sentiment</h3>
                <p className="muted">
                  <span>{moodFace(homePanel?.fan_sentiment?.mood)} </span>
                  {homePanel?.fan_sentiment?.score?.toFixed(1) ?? "-"} / 100 ({homePanel?.fan_sentiment?.mood ?? "Unknown"}){" "}
                  <span className={homePanel?.fan_sentiment?.trend === "Rising" ? "pos" : homePanel?.fan_sentiment?.trend === "Falling" ? "neg" : ""}>
                    {trendArrow(homePanel?.fan_sentiment?.trend)} {homePanel?.fan_sentiment?.trend ?? "Flat"}
                  </span>
                </p>
              </div>
              <div className="home-sentiment-card">
                <h3>Locker Room</h3>
                <p className="muted">
                  <span>{moodFace(homePanel?.locker_room?.mood)} </span>
                  {homePanel?.locker_room?.score?.toFixed(1) ?? "-"} / 100 ({homePanel?.locker_room?.mood ?? "Unknown"}){" "}
                  <span className={homePanel?.locker_room?.trend === "Rising" ? "pos" : homePanel?.locker_room?.trend === "Falling" ? "neg" : ""}>
                    {trendArrow(homePanel?.locker_room?.trend)} {homePanel?.locker_room?.trend ?? "Flat"}
                  </span>
                </p>
              </div>
            </div>
          </div>
          {homePanel?.top_story ? (
            <div className="score-card">
              <h3>Top Stories</h3>
              <p className="muted">
                S{homePanel.top_story.season ?? "-"} {((homePanel.top_story.day ?? 0) > 0) ? `D${homePanel.top_story.day}` : "Offseason"}
                {" | "}
                {homePanel.top_story.headline ?? ""}
                {homePanel.top_story.details ? ` - ${homePanel.top_story.details}` : ""}
              </p>
            </div>
          ) : null}
          {homePanel ? (
            <div className="split">
              <div>
                <div className="latest-game-head">
                  <h3>Team Game Spotlight</h3>
                </div>
                {(() => {
                  const latestGame = (homePanel.playoffs?.active && homePanel.playoffs.latest_team_game)
                    ? homePanel.playoffs.latest_team_game
                    : homePanel.latest_game;
                  const latestShownDay = homePanel.playoffs?.active
                    ? (homePanel.playoffs.latest_team_game_day ?? null)
                    : homePanel.latest_game_day;
                  const showLatest = Boolean(latestGame && latestShownDay != null);
                  const showUpcoming = Boolean(
                    homePanel.upcoming_game
                    && (
                      latestShownDay == null
                      || homePanel.upcoming_game_day == null
                      || homePanel.upcoming_game_day > latestShownDay
                    ),
                  );
                  const renderUpcomingCard = () => {
                    const upcomingGame = homePanel.upcoming_game;
                    if (!upcomingGame) return null;
                    const awayRec = standingsRecordMap.get(upcomingGame.away) ?? "-";
                    const homeRec = standingsRecordMap.get(upcomingGame.home) ?? "-";
                    return (
                      <div className="score-card">
                        <div className="score-main">
                          <p className="muted">
                            {homePanel.upcoming_phase === "playoffs" ? "Playoff" : "Regular"} Day {homePanel.upcoming_game_day ?? "-"}
                            {homePanel.upcoming_round ? ` | ${homePanel.upcoming_round}` : ""}
                            {upcomingGame.game_number ? ` | Game ${upcomingGame.game_number}` : ""}
                          </p>
                          <div className="score-teams">
                            <div className="score-team-row">
                              {meta?.team_logos?.[upcomingGame.away] ? <img className="mini-logo mini-logo-large" src={logoUrl(meta.team_logos[upcomingGame.away])} alt={upcomingGame.away} /> : null}
                              <div className="score-team-text">
                                <div className="score-team-name">{upcomingGame.away}</div>
                                <div className="score-team-record">{awayRec}</div>
                              </div>
                            </div>
                            <div className="score-team-row">
                              {meta?.team_logos?.[upcomingGame.home] ? <img className="mini-logo mini-logo-large" src={logoUrl(meta.team_logos[upcomingGame.home])} alt={upcomingGame.home} /> : null}
                              <div className="score-team-text">
                                <div className="score-team-name">{upcomingGame.home}</div>
                                <div className="score-team-record">{homeRec}</div>
                              </div>
                            </div>
                          </div>
                          <div className="results narrative-full">
                            <div className="line">
                              Preview: {upcomingGame.away} ({awayRec}) at {upcomingGame.home} ({homeRec}).
                              {homePanel.upcoming_round ? ` ${homePanel.upcoming_round}.` : ""}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  };
                  if (showLatest && latestGame) {
                    return (
                      <>
                        <GameSummaryCard
                          game={latestGame}
                          teamLogos={meta?.team_logos}
                          showTeamLabels={false}
                          emphasizePlayoffSeries={Boolean(homePanel.playoffs?.active && homePanel.playoffs.latest_team_game)}
                          seriesLineTop={Boolean(homePanel.playoffs?.active && homePanel.playoffs.latest_team_game)}
                          starsTopRight={true}
                          largeLogos={true}
                        />
                        {showUpcoming ? renderUpcomingCard() : null}
                      </>
                    );
                  }
                  if (!showLatest && homePanel.upcoming_game) {
                    return renderUpcomingCard();
                  }
                  return <p className="muted">No latest or upcoming game available.</p>;
                })()}
              </div>
              <div>
                <div>
                  <h3>✉ Inbox</h3>
                  {inboxEvents.length === 0 ? (
                    <p className="muted">No unresolved inbox events right now.</p>
                  ) : (
                    <div className="score-list">
                      {inboxEvents.slice(0, 4).map((ev) => (
                        <article key={`home-inbox-${ev.id}`} className="score-card">
                          <h3>{ev.title}</h3>
                          <div className="muted small">S{ev.season} D{ev.day} | Expires D{ev.expires_day}</div>
                          <p>{ev.details}</p>
                          <div className="inline-controls">
                            {ev.options.map((opt) => (
                              <span key={`${ev.id}-${opt.id}`} title={opt.description}>
                                <button onClick={() => void resolveInboxEvent(ev.id, opt.id)}>
                                  {opt.label}
                                </button>
                              </span>
                            ))}
                            {String(ev.payload?.navigate_to ?? "") === "callups" ? (
                              <button onClick={() => openCallupsPage()}>Go to Call Ups</button>
                            ) : null}
                            {ev.type === "trade_offer" ? (
                              <button onClick={() => handleNavSelect("trade_center")}>Open Trades</button>
                            ) : null}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <h3>Coach</h3>
                  <button onClick={() => setShowCoachDetails((v) => !v)}>
                    {homePanel.coach.name}
                  </button>
                </div>
                {showCoachDetails ? (
                  <div>
                    <p className="muted">
                      Overall Record {homePanel.coach.overall_record ?? "-"} | Cups {homePanel.coach.cups ?? 0}
                    </p>
                    <p className="muted">Age {homePanel.coach.age ?? "-"} | Rating {homePanel.coach.rating.toFixed(2)} | Style {homePanel.coach.style}</p>
                    <p className="muted">
                      Off {homePanel.coach.offense.toFixed(2)} | Def {homePanel.coach.defense.toFixed(2)} | Goalie Dev {homePanel.coach.goalie_dev.toFixed(2)}
                    </p>
                    <p className="muted">
                      Strategy: {homePanel.control.user_strategy} | Override Lines: {homePanel.control.override_coach_for_lines ? "On" : "Off"} | Override Strategy: {homePanel.control.override_coach_for_strategy ? "On" : "Off"}
                    </p>
                    <p className="muted">
                      Game Mode: {homePanel.control.game_mode.toUpperCase()}
                    </p>
                  </div>
                ) : null}
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
                <thead><tr><th>Coach</th><th>Age</th><th>Rating</th><th>Style</th><th>W-L-OTL</th><th>Cups</th><th>Source</th></tr></thead>
                <tbody>
                  {coachCandidates.map((c) => (
                    <tr key={`coach-${c.name}`} className={selectedCoachName === c.name ? "row-clickable" : ""} onClick={() => setSelectedCoachName(c.name)}>
                      <td>{c.name}</td><td>{c.age ?? "-"}</td><td>{c.rating.toFixed(2)}</td><td>{c.style}</td><td>{c.w}-{c.l}-{c.otl}</td><td>{c.cups}</td><td>{c.source}</td>
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
            <h3>{playerLabel(playerCareer.player.name, playerCareer.player.jersey_number)}</h3>
            <p className="muted">
              <span className="ovr-chip">OVR {Number(playerCareer.player.overall ?? 0).toFixed(2)}</span>
            </p>
            <p className="muted">
              Position: {playerCareer.player.position} | Team: {playerCareer.player.team} | Country: {playerCareer.player.country ?? "-"} | Draft: {playerCareer.player.draft_label ?? "Undrafted"}
            </p>
            <p className="muted">
              Age: {playerCareer.player.age} | HT: {playerCareer.player.height ?? "-"} | WT: {playerCareer.player.weight_lbs ?? "-"} lbs | Shot: {playerCareer.player.shot ?? "-"} | Birth Place: {playerCareer.player.birth_place ?? "-"} | Birthdate: {playerCareer.player.birthdate ?? "-"}
            </p>
            {playerCareer.player.ratings ? (
              <p className="muted">
                Ratings: SHT {playerCareer.player.ratings.shooting.toFixed(2)} | PMK {playerCareer.player.ratings.playmaking.toFixed(2)} | DEF {playerCareer.player.ratings.defense.toFixed(2)} | G {playerCareer.player.ratings.goaltending.toFixed(2)} | PHY {playerCareer.player.ratings.physical.toFixed(2)} | DUR {playerCareer.player.ratings.durability.toFixed(2)}
              </p>
            ) : null}
            <div className="modal-lines">
              {playerCareer.player.position === "G" ? (
                <table>
                  <thead>
                    <tr>
                      <th>Season</th><th>Team</th><th>Age</th><th>Pos</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>SO</th><th>GAA</th><th>SV%</th><th>Inj</th><th>Missed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {playerCareer.career.map((row, idx) => (
                      <tr key={`${playerCareer.player.team}-${playerCareer.player.name}-${row.season}-${idx}`}>
                        <td>{row.is_current ? `${row.season} (Current)` : row.season}</td>
                        <td>{row.team}</td>
                        <td>{row.age}</td>
                        <td>{row.position}</td>
                        <td>{row.goalie_gp}</td>
                        <td>{row.goalie_w}</td>
                        <td>{row.goalie_l}</td>
                        <td>{row.goalie_otl}</td>
                        <td>{row.goalie_so ?? 0}</td>
                        <td>{Number(row.gaa ?? 0).toFixed(2)}</td>
                        <td>{Number(row.sv_pct ?? 0).toFixed(3)}</td>
                        <td>{row.injuries}</td>
                        <td>{row.games_missed}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table>
                <thead>
                  <tr>
                    <th>Season</th><th>Team</th><th>Age</th><th>Pos</th><th>GP</th><th>G</th><th>A</th><th>P</th><th>+/-</th><th>PIM</th><th>TOI/G</th><th>PPG</th><th>PPA</th><th>SHG</th><th>SHA</th><th>S</th><th>S%</th><th>Inj</th><th>Missed</th>
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
                      <td>{(row.plus_minus ?? 0) > 0 ? `+${row.plus_minus}` : (row.plus_minus ?? 0)}</td>
                      <td>{row.pim ?? 0}</td>
                      <td>{Number(row.toi_g ?? 0).toFixed(1)}</td>
                      <td>{row.ppg ?? 0}</td>
                      <td>{row.ppa ?? 0}</td>
                      <td>{row.shg ?? 0}</td>
                      <td>{row.sha ?? 0}</td>
                      <td>{row.shots ?? 0}</td>
                      <td>{Number(row.shot_pct ?? 0).toFixed(1)}</td>
                      <td>{row.injuries}</td>
                      <td>{row.games_missed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              )}
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
  emphasizePlayoffSeries = false,
  seriesLineTop = false,
  omitSeriesRound = false,
  starsTopRight = false,
  largeLogos = false,
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
    round?: string;
    game_number?: number;
    series_higher_seed?: string;
    series_lower_seed?: string;
    series_high_wins?: number;
    series_low_wins?: number;
  };
  teamLogos?: Record<string, string>;
  showCommentary?: boolean;
  showTeamLabels?: boolean;
  emphasizePlayoffSeries?: boolean;
  seriesLineTop?: boolean;
  omitSeriesRound?: boolean;
  starsTopRight?: boolean;
  largeLogos?: boolean;
}) {
  const awayScore = typeof game.away_goals === "number" ? ` ${game.away_goals}` : "";
  const homeScore = typeof game.home_goals === "number" ? ` ${game.home_goals}` : "";
  const commentaryLines = (game.commentary ?? []).filter((line) => !/^three stars:/i.test(String(line).trim()));
  const stars = (game.three_stars ?? []).slice(0, 3);
  const roundLabel = omitSeriesRound ? "" : (game.round ?? "Playoffs");
  const playoffSeriesLine = game.series_higher_seed && game.series_lower_seed
    ? `${roundLabel ? `${roundLabel} | ` : ""}${game.game_number ? `Game ${game.game_number} | ` : ""}Series: ${game.series_higher_seed} ${game.series_high_wins ?? 0}-${game.series_low_wins ?? 0} ${game.series_lower_seed}`
    : "";
  const starGlyphs = (label: string, idx: number) => {
    const text = String(label).toLowerCase();
    if (text.includes("1st")) return "★";
    if (text.includes("2nd")) return "★★";
    if (text.includes("3rd")) return "★★★";
    return "★".repeat(Math.min(3, Math.max(1, idx + 1)));
  };
  const parseStarSummary = (summary: string): { playerLine: string; statLine: string } => {
    const text = String(summary ?? "").trim();
    const closeParen = text.indexOf(")");
    if (closeParen > 0) {
      return {
        playerLine: text.slice(0, closeParen + 1),
        statLine: text.slice(closeParen + 1).trim(),
      };
    }
    return { playerLine: text, statLine: "" };
  };
  const showTopStars = showCommentary && stars.length > 0 && starsTopRight;
  return (
    <div className="score-card">
      <div className="score-main">
        {seriesLineTop && playoffSeriesLine ? <div className={emphasizePlayoffSeries ? "series-line-bold" : "muted small"}>{playoffSeriesLine}</div> : null}
        <div className={showTopStars ? "score-head-grid" : undefined}>
          <div className={showTopStars ? "score-head-left" : undefined}>
            <div className="score-teams">
              <div className="score-team-row">
                {teamLogos?.[game.away] ? <img className={`mini-logo${largeLogos ? " mini-logo-large" : ""}`} src={logoUrl(teamLogos[game.away])} alt={game.away} /> : null}
                <div className="score-team-text">
                  <div className="score-team-name">
                    {showTeamLabels ? <strong>Away:</strong> : null} {game.away}<strong>{awayScore}</strong>
                  </div>
                  {game.away_record ? <div className="score-team-record">{game.away_record}</div> : null}
                </div>
              </div>
              <div className="score-team-row">
                {teamLogos?.[game.home] ? <img className={`mini-logo${largeLogos ? " mini-logo-large" : ""}`} src={logoUrl(teamLogos[game.home])} alt={game.home} /> : null}
                <div className="score-team-text">
                  <div className="score-team-name">
                    {showTeamLabels ? <strong>Home:</strong> : null} {game.home}<strong>{homeScore}</strong>
                  </div>
                  {game.home_record ? <div className="score-team-record">{game.home_record}</div> : null}
                </div>
              </div>
            </div>
            <div className="muted small game-meta">Goalies: {game.away_goalie || "-"} {game.away_goalie_sv || ""} | {game.home_goalie || "-"} {game.home_goalie_sv || ""}</div>
            {!seriesLineTop && playoffSeriesLine ? <div className={emphasizePlayoffSeries ? "series-line-bold" : "muted small"}>{playoffSeriesLine}</div> : null}
            <div className="muted small game-meta">
              Attendance: {typeof game.attendance === "number" ? game.attendance.toLocaleString() : "-"}
              {typeof game.arena_capacity === "number" ? `/${game.arena_capacity.toLocaleString()}` : ""}
            </div>
          </div>
          {showTopStars ? (
            <div className="stars-block stars-top-right">
              <div className="stars-title">Stars of the Game</div>
              <div className="stars-list">
                {stars.map((s, idx) => {
                  const parsed = parseStarSummary(s.summary);
                  return (
                    <div key={`star-top-${idx}-${s.summary}`} className="star-row">
                      <div className="star-rank">{starGlyphs(s.label, idx)}</div>
                      <div className="star-text">
                        <div className="star-player">{parsed.playerLine}</div>
                        {parsed.statLine ? <div className="star-stats">{parsed.statLine}</div> : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
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
        {showCommentary && starsTopRight && commentaryLines.length > 0 ? (
          <div className="results narrative-full">
            {commentaryLines.map((line, idx) => (
              <div key={`c-${idx}-${line}`} className="line">{line}</div>
            ))}
          </div>
        ) : null}
        {showCommentary && !starsTopRight && (commentaryLines.length > 0 || stars.length > 0) ? (
          <div className="game-detail-grid">
            {commentaryLines.length > 0 ? (
              <div className="results">
                {commentaryLines.map((line, idx) => (
                  <div key={`c-${idx}-${line}`} className="line">{line}</div>
                ))}
              </div>
            ) : <div />}
            {stars.length > 0 ? (
              <div className="stars-block">
                <div className="stars-title">Stars of the Game</div>
                <div className="stars-list">
                  {stars.map((s, idx) => {
                    const parsed = parseStarSummary(s.summary);
                    return (
                      <div key={`star-${idx}-${s.summary}`} className="star-row">
                        <div className="star-rank">{starGlyphs(s.label, idx)}</div>
                        <div className="star-text">
                          <div className="star-player">{parsed.playerLine}</div>
                          {parsed.statLine ? <div className="star-stats">{parsed.statLine}</div> : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
        {!showCommentary && stars.length > 0 ? (
          <div className="muted small">
            {stars.map((s) => `${s.label}: ${s.summary}`).join(" | ")}
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
            <td className="team-cell">
              <img className="table-logo" src={logoUrl(r.logo_url)} alt={r.team} />
              <span>{r.team}</span>
              {(r.clinch ?? []).length > 0 ? (
                <span className="clinch-tags" title={`Clinch: ${(r.clinch ?? []).join(", ").toUpperCase()}`}>
                  {(r.clinch ?? []).map((tag) => (
                    <span key={`${r.team}-clinch-${tag}`} className="clinch-tag">{tag.toUpperCase()}</span>
                  ))}
                </span>
              ) : null}
            </td>
            <td>{r.gp}</td><td>{r.w}</td><td>{r.l}</td><td>{r.otl}</td><td>{r.pts}</td><td>{r.home}</td><td>{r.away}</td><td>{r.gf}</td><td>{r.ga}</td>
            <td className={r.diff > 0 ? "pos" : r.diff < 0 ? "neg" : ""}>{r.diff > 0 ? `+${r.diff}` : r.diff}</td>
            <td>{r.l10}</td><td>{r.strk}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LeaderBlock<T extends { name: string; team: string; flag?: string }>({
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
  const [showAll, setShowAll] = useState(false);
  const sorted = [...rows].sort((a, b) => (sortAsc ? getValue(a) - getValue(b) : getValue(b) - getValue(a)));
  const visibleRows = showAll ? sorted : sorted.slice(0, 5);

  function rankAt(idx: number): number {
    if (idx <= 0) return 1;
    const cur = getValue(visibleRows[idx]);
    const prev = getValue(visibleRows[idx - 1]);
    if (cur === prev) return rankAt(idx - 1);
    return idx + 1;
  }

  return (
    <section className="leader-block">
      <header className="leader-head">
        <span>{title}</span>
        {rows.length > 5 ? (
          <button className="leader-head-toggle" onClick={() => setShowAll((v) => !v)}>
            {showAll ? "Show Top 5" : "Complete Leaders"}
          </button>
        ) : (
          <span />
        )}
        <span>{valueLabel}</span>
      </header>
      <div className={showAll ? "leader-list full" : "leader-list"}>
        {visibleRows.map((row, idx) => (
          <div key={`${row.team}-${row.name}-${title}`} className="leader-row row-clickable" onClick={() => onPick(row)}>
            <span className="leader-rank">{rankAt(idx)}</span>
            <span className="leader-player">{row.name} <small>{row.team.slice(0, 3).toUpperCase()}</small></span>
            <span className="leader-value">{formatValue(getValue(row))}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
