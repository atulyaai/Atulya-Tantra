### Speech Visibility & Idle Initiative ✅
- [x] Implementation plan approved (with tightenings)
- [x] Implement `_speak()` in `core/engine.py`
- [x] Integrate `_speak()` in `run_task` (Thoughts & Outcome)

### Persistent Goals (Memory Continuity) ✅
- [x] Implementation plan approved
- [x] Implement core/goals.py
- [x] Implement memory/goals.json
- [x] Engine integration (minimal)
- [x] Verify source guard (user-only creation)
- [x] Verify persistence (survives restart)
- [x] All tests PASS

### Action Confidence Ledger (Trust Anchor) ✅
- [x] Implement core/action_ledger.py
- [x] Implement memory/action_ledger.json
- [x] Engine integration (record outcomes)
- [x] Unit/Integration Tests PASS

### Shadow Suggestions (The Intuition) ✅
- [x] Implement core/shadow_suggestions.py
- [x] Integrate into Engine (Input Trigger "what next")
- [x] Unit Tests PASS (No Execution Guard)
- [x] Verification (Speech format confirmed)

## Phase E3: Refinement & Polish
- [x] Ensure no regression in Engine startup
- [x] Verify all artifacts updated
- [x] **PROJECT COMPLETE**

## Phase H: Controlled Agency (Approval-Based) ✅
**Objective**: Allow execution of Shadow Suggestions ONLY with explicit user confirmation ("Yes, do it").
**Constraints**: Whitelisted actions only. Per-action permission.

- [x] Create Implementation Plan (Option B)
- [x] Modify `ShadowSuggester` to return structured plans (Action + Outcome)
- [x] Modify `Engine` to track `pending_suggestion` state
- [x] Implement `APPROVE_ACTIONS` whitelist (Safe Sandbox)
- [x] Implement "Yes/No" approval logic in `run_task`
- [x] Verify: Suggestion -> "Yes" -> Execution
- [x] Verify: Suggestion -> "No" -> Clear State
- [x] Verify: Whitelist Enforcement (No dangerous ops suggested)

## Phase I: Operational Observability (Live Dashboard) ✅
**Objective**: Read-only Terminal Dashboard for real-time system status.
**Constraint**: ZERO Autonomy impact. Passive observer only.

- [x] Create Implementation Plan
- [x] Implement `core/event_bus.py` (Simple Pub/Sub)
- [x] Instrument `Engine` to emit events (State, Speech, Ledger)
- [x] Implement `core/dashboard.py` (Terminal Renderer)
- [x] Update `start.py` to launch Dashboard (Demo script created)
- [x] Verify: Live updates without blocking Engine

## Phase I-2: Local Web Dashboard (Option C) ✅
**Objective**: Browser-based Mission Control (localhost only)
**Constraint**: No external dependencies (use http.server).

- [x] Create Implementation Plan
- [x] Implement `core/web_server.py` (Simple JSON API)
- [x] Create `dashboard/index.html` (UI/JS)
- [x] Integrate into `run_atulya_tantra.py`
- [x] Integrate into `run_atulya_tantra.py`
- [x] Verify: Browser access to localhost:8000

## Phase F: Soak Verification (24h Reliability)
**Objective**: Prove stability over time. No new features.
**Metrics**: Memory stability, Thread stability, Pulse consistency.

- [x] Implement `experiments/soak_test.py`
- [x] Implement Metrics Collector (Memory/Threads/Goals)
- [x] Verify: Short run (5 mins)
- [x] Execute: Long run (User initiated)

## Phase G: Optimization & Cleanup (Deeper)
**Objective**: Remove redundant code, reduce file count, standardize headers.
- [x] Inline `tools/file_ops` and `search_ops` into Executor.
- [x] Inline `core/interpreter` into Engine.
- [x] Consolidate tests into `tests/performance`.
- [x] Verify System Startup.

**PROJECT FINALIZED**
