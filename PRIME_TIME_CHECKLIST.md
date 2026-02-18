# Prime Time Readiness Checklist

This checklist tracks what must be done before paid release.

## 1) Save + Migration Safety
- [ ] Add `save_version` to all persisted state payloads in `src/hockey_sim/league.py`.
- [ ] Add migration handlers in load path (`vN -> vN+1`) for:
  - [ ] `league_state.json`
  - [ ] `career_history.json`
  - [ ] `season_history.json`
  - [ ] `hall_of_fame.json`
  - [ ] `api_runtime_state.json`
- [ ] Add backup-on-load before migration.
- [ ] Add clear error + recovery path for corrupted/mismatched saves.

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
**Goal:** Save/version safety first.

Why first:
- It protects player progress.
- It prevents update fear.
- It reduces support burden before launch.

### Sprint Tasks
- [ ] Add `save_version` constants and write them to every state file.
- [ ] Implement migration entrypoint in simulator/service startup.
- [ ] Add migration unit tests for at least one previous schema.
- [ ] Add `README` section: save compatibility + rollback instructions.

