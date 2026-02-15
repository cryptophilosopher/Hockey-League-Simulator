# Hockey League Simulator

A simple Python project to simulate a hockey league season.

## Features
- GUI mode for team control and day-by-day simulation
- 24 teams across 4 divisions (6 teams per division)
- Team color styling in standings and stat tables for fast visual distinction
- 22-player roster per team (20 dressed + 2 extras)
- Roster dressing controls (`Toggle Dress`, `Auto Best Lineup`)
- Full player tables with age, injury status, and remaining games out
- Click any team in standings to jump to that team roster/stats
- Dedicated goalie stats table (`GP`, `W`, `L`, `OTL`, `GAA`, `SV%`)
- Separate standings tabs for each division plus overall standings
- Multi-season progression with offseason logic:
  - players age after each season
  - age curve is player-specific with prime around age 27-28 (configurable)
  - retirements occur over time
  - draft refills rosters back to 22 players and stores picks by team
  - completed season records are persisted to `season_history.json`
- Team strength derived from dressed, healthy player ratings
- Injury simulation with strategy impact (`aggressive` is riskier)
- Standings table with points (W=2, OTL=1)

## Quick start
1. Create and activate a virtual environment.
2. Install project in editable mode:
   `py -3 -m pip install -e .`
3. Run the simulator:
   `py -3 -m hockey_sim`

GUI controls:
- `Start Season`
- `Sim Next Day`
- Team dropdown (`Your Team`)
- Strategy dropdown (`aggressive`, `balanced`, `defensive`)
- `My Team Stats` and `League Leaders`
- `My Team Goalies` and `League Goalies`
- `Season History` to view champions from previous completed seasons
- `Toggle Dress` on selected player
- `Auto Best Lineup` to restore strongest valid 20-player dressed roster

## Web UI (React + FastAPI)
Phase 1 web stack is now scaffolded:
- Backend API: `src/hockey_sim/api.py`
- Frontend app: `web/`

### Run backend API
1. Install/update dependencies:
   `py -3 -m pip install -e .`
2. Start API server:
   `py -3 -m uvicorn hockey_sim.api:app --reload --host 127.0.0.1 --port 8000`

### Run frontend
1. In a second terminal:
   `cd web`
2. Install frontend deps:
   `npm install`
3. Start frontend:
   `npm run dev`
4. Open:
   `http://127.0.0.1:5173`

## Injury model notes
- Baseline injury event rate and average games missed are calibrated from 2024-25 NHL team-level injury totals and man-games lost.
- Aggressive strategy increases injury probability and average time out.
- Defensive strategy lowers injury probability.

## Run tests
Install pytest and run:
`py -3 -m pip install pytest`
`py -3 -m pytest`
