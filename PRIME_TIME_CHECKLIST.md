# Prime Time Readiness Checklist

This checklist tracks what must be done before paid release.

## 1) Save + Migration Safety
- [x] Add `save_version` to persisted state payloads in `src/hockey_sim/league.py`.
- [x] Add runtime `save_version` for `api_runtime_state.json`.
- [~] Add migration-compatible load path (current status: backward-compatible loaders + version gate; full explicit `vN -> vN+1` migrators still pending) for:
  - [~] `league_state.json`
  - [~] `career_history.json`
  - [~] `season_history.json`
  - [~] `hall_of_fame.json`
  - [~] `api_runtime_state.json`
- [~] Add backup safety (current status: backup-on-write before overwrite; backup-before-migrate still pending once explicit migrators are added).
- [x] Add clear error + recovery path for corrupted/mismatched saves.

## 2) Regression Test Coverage
- [ ] Add full-season simulation test (`regular -> playoffs -> offseason`) in `tests/`.
- [ ] Add transaction consistency tests (trade appears once, callup/demotion logs once).
- [ ] Add roster compliance tests (22 active cap with IR/LTIR/DTD edge cases).
- [ ] Add API response shape tests for:
  - [ ] `/api/home`
  - [ ] `/api/standings`
  - [ ] `/api/transactions`
  - [ ] `/api/franchise`
  - [ ] `/api/career`

## 3) Core Sim Consistency
- [ ] Verify mid-season trade stat handling (carry season totals + split team season rows).
- [ ] Verify franchise records count only stats earned with that franchise.
- [ ] Verify DTD/IR/LTIR/Season-ending behavior in regular season and playoffs.
- [ ] Verify CPU and user teams follow same roster/compliance rules.

## 4) UI/UX Stability Pass
- [ ] Resolve remaining table overlap/wrap issues across key pages.
- [ ] Ensure all clickable player rows are consistent in every table/list.
- [ ] Confirm nav/team switch never desyncs content.
- [ ] Add concise tooltip legend where symbols/tags are used (clinch tags, injury chips).

## 5) Packaging + Release
- [ ] Add production build script for backend + web.
- [ ] Package Windows build (`PyInstaller`) and smoke test on clean machine.
- [ ] Add release versioning + changelog process.
- [ ] Add backup notice for save files before upgrades.

## 6) Store + Legal Readiness
- [ ] Confirm all logos/names/assets are safe for commercial use.
- [ ] Add Terms/Privacy/Support policy docs.
- [ ] Prepare store assets: screenshots, trailer, short + long description.

---

## Recommended Next Sprint (Do This Next)
**Goal:** Regression safety net.

Why first:
- Recent progress added many cross-system behaviors (trades, standings tags, clickable history, injury/status logic).
- Fast regression checks will stop re-breaks and speed up future feature work.
- It is the highest leverage for release confidence right now.

### Sprint Tasks
- [ ] Add full-season sim test (`regular -> playoffs -> offseason`).
- [ ] Add transaction integrity tests (single trade event, team feed visibility, carryover season stats).
- [ ] Add roster compliance tests (22 active cap with IR/LTIR/DTD edge cases).
- [ ] Add API response shape tests for `/api/home`, `/api/standings`, `/api/transactions`, `/api/franchise`, `/api/career`.
