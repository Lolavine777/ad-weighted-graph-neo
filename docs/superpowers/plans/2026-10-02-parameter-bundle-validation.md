# Scoped Parameter Bundle and Explicit Disposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete explicit design/interface/version decisions for Issue #143, establish the versioned scoped parameter bundle for the SEAMLESS scenario, and execute reproducible validation/sensitivity analysis while keeping actual human ratings pending.

**Architecture:** Encapsulate the SEAMLESS scenario parameter basis into a versioned canonical bundle (`seamless_parameter_bundle.json`), enhance `seamless_parameter_validation.py` to validate and run sensitivity sweeps directly on the bundle, extend `test_seamless_parameter_proposal.py` with rigorous bundle verification tests, and finalize the explicit decision and disposition records in `path-ranking-acceptance-disposition.md`, `ADR-0013`, and `path-ranking-interface-specification.md`.

**Tech Stack:** Python 3.14, stdlib `Fraction`, `pytest`, `ruff`, JSON serialization.

## Global Constraints

- Never use the em dash "—". Use plain dash "-" instead.
- When writing commit messages, NEVER auto-add agent name as co-author.
- Never manually modify CHANGELOG.md files or auto-generated files.
- When writing or substantially editing long Markdown files, put each full sentence on its own line.
- Do not modify B-owned engine/parser (`src/engine/`, `src/parser/`).
- Always run Python scripts using `.venv/bin/python` from the virtual environment.
- Keep actual human ratings in `seamless_rater_1.json` and `seamless_rater_2.json` strictly unrated and pending.
- Use branch, PR, and truthful worklog; no self-merge.

---

### Task 1: Create Scoped Parameter Bundle Artifact

**Files:**
- Create: `tests/fixtures/ranking/seamless_parameter_bundle.json`

**Interfaces:**
- Consumes: `docs/research/seamless-parameter-basis-proposal.md`, `tests/fixtures/ranking/seamless_proposed_query_input.json`, `tests/fixtures/ranking/seamless_source_b_proposed_query_input.json`
- Produces: `tests/fixtures/ranking/seamless_parameter_bundle.json` with metadata, target impact, 9 canonical work units, 11 conditional bounds, 25 declared runtime assumptions, 3 candidate envelopes with structural routes and provenance locators, and analytical expectations.

- [ ] **Step 1: Construct the canonical parameter bundle JSON**
  Create `tests/fixtures/ranking/seamless_parameter_bundle.json` containing:
  - `bundle_metadata`: `bundle_id: "bundle-seamless-host-to-dc-v1"`, `bundle_version: "1.0.0"`, `schema_version: "1.0.0"`, `scenario_id: "scenario-seamless-host-to-dc"`, `scenario_version: "1.1.0"`, `snapshot_id: "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"`.
  - `governance`: `basis_category: "research_assisted_scenario_hypotheses"`, `status: "pending_independent_human_ratings"`, `human_agreement_status: "pending"`, `empirical_calibration_status: "none"`, `raters: []`.
  - `target_impact_assessments`: Target DC consequence rating `High`, event `terminal_compromise_seamless_dc`, rationale.
  - `work_units_ledger`: 9 canonical work units with rubric scores ($T_1, T_2, C$, formula `"base"`), `overlap_state: "independent"`, `rating_status: "rated"`, and detailed technical rationale.
  - `conditional_bounds_table`: 11 conditional bounds questions with prefix, lower/upper string fractions, outcome action, required predicates, technical source, residual uncertainty rationale.
  - `scenario_assumptions`: 25 unique declared runtime assumptions ($S$) across Source A and B with predicate, layer 3, truth value True, rationale.
  - `candidate_envelopes`: Source A (Cand 1, Cand 2) and Source B (Cand B) with scope bindings, structural routes, and provenance locators.
  - `analytical_baseline`: Expected calculation traces, Pareto frontier, Min-Effort-to-DA.

- [ ] **Step 2: Validate JSON syntax and structure**
  Run: `.venv/bin/python -m json.tool tests/fixtures/ranking/seamless_parameter_bundle.json > /dev/null`
  Expected: Exit code 0.

---

### Task 2: Enhance Parameter Validation Script for Parameter Bundle

**Files:**
- Modify: `scripts/research/seamless_parameter_validation.py`

**Interfaces:**
- Consumes: `tests/fixtures/ranking/seamless_parameter_bundle.json`, `tests/fixtures/ranking/seamless_proposed_query_input.json`
- Produces: CLI support for `--bundle`, validation of bundle structure against query inputs, analytical trace checks, sensitivity analysis execution, and report generation.

- [ ] **Step 1: Write failing test for bundle validation in `test_seamless_parameter_proposal.py`**
  Add `test_seamless_parameter_bundle_schema_and_completeness` and `test_parameter_bundle_cli_validation`.
  Run: `.venv/bin/python -m pytest tests/test_seamless_parameter_proposal.py -k test_seamless_parameter_bundle -v`
  Expected: FAIL because bundle validation logic is missing.

- [ ] **Step 2: Implement bundle validation in `seamless_parameter_validation.py`**
  Add `verify_parameter_bundle(bundle_payload)` function.
  Update `main()` to accept `--bundle` (defaulting to `tests/fixtures/ranking/seamless_parameter_bundle.json`) or `--input`.
  Ensure calculation traces and sensitivity suite can evaluate from bundle payload.

- [ ] **Step 3: Run pytest to verify tests pass**
  Run: `.venv/bin/python -m pytest tests/test_seamless_parameter_proposal.py -k test_seamless_parameter_bundle -v`
  Expected: PASS.

- [ ] **Step 4: Regenerate validation report from bundle**
  Run: `.venv/bin/python scripts/research/seamless_parameter_validation.py --bundle tests/fixtures/ranking/seamless_parameter_bundle.json --output reports/research/seamless-parameter-validation-report.json`
  Expected: PASS with report written.

---

### Task 3: Add Comprehensive Automated Tests for Parameter Bundle

**Files:**
- Modify: `tests/test_seamless_parameter_proposal.py`

**Interfaces:**
- Consumes: `seamless_parameter_bundle.json`, `seamless_parameter_validation.py`, `seamless_proposed_query_input.json`, `seamless_source_b_proposed_query_input.json`
- Produces: 5+ new automated unit/integration tests verifying bundle integrity, query projection consistency, calculation traces, and sensitivity sweeps.

- [ ] **Step 1: Add new test functions to `test_seamless_parameter_proposal.py`**
  - `test_seamless_parameter_bundle_schema_and_completeness`: checks metadata, all 9 work units, all 11 conditional bounds, all 25 runtime assumptions, and target impact assessment.
  - `test_parameter_bundle_matches_query_fixtures`: verifies that `seamless_proposed_query_input.json` and `seamless_source_b_proposed_query_input.json` are exact projections of the bundle.
  - `test_parameter_bundle_calculation_traces_and_pareto`: verifies analytical calculation traces and conservative Pareto frontier from the bundle.
  - `test_parameter_bundle_cli_validation`: verifies CLI invocation with `--bundle`.
  - `test_parameter_bundle_governance_and_human_sheets_safeguard`: asserts human sheets remain pristine and unrated while bundle governance is declared as research assumptions pending human agreement.

- [ ] **Step 2: Run pytest to ensure all tests pass**
  Run: `.venv/bin/python -m pytest tests/test_seamless_parameter_proposal.py -v`
  Expected: All 30 tests pass.

---

### Task 4: Complete Explicit Design, Interface, Version, and Migration Decisions in Documentation

**Files:**
- Modify: `docs/research/path-ranking-acceptance-disposition.md`
- Modify: `docs/adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md`
- Modify: `docs/research/path-ranking-interface-specification.md`
- Modify: `docs/research/evidence-rating-governance.md`
- Modify: `docs/research/weighting-direction.md`

**Interfaces:**
- Documents: Explicit decision record from TTS A for Gate 1 (ADR-0013 Scoped Conservative Pareto Ranking), Gate 2 (Interface 1.0.0 Specification & Canonical Migration Boundary), Gate 3 (Route vs. Work Identity), Gate 4 (Scenario Bindings & Assumptions), Gate 5 (Predictive Verdict - Insufficient Evidence), Gate 6 (Official Disposition Record), and Section 5.8 (Scoped Parameter Bundle 1.0.0 Release).
- Updates: Status matrix, Interface Spec version promoted from `1.0.0-draft` to `1.0.0`, ADR-0013 documented acceptance from TTS A.

- [ ] **Step 1: Update `path-ranking-acceptance-disposition.md`**
  Finalize Section 5 and Section 2.
  Add Section 5.8 recording the release and explicit acceptance of the versioned parameter bundle `1.0.0`.
  Update status matrix to record TTS A explicit acceptance while keeping actual human ratings pending and predictive verdict as Insufficient Evidence.

- [ ] **Step 2: Update `path-ranking-interface-specification.md`**
  Promote version from `1.0.0-draft` to `1.0.0`.
  Document the migration boundary and canonical layout dispatch established in #162/#163.

- [ ] **Step 3: Update `ADR-0013-scoped-path-ranking-and-pareto-frontier.md`**
  Record TTS A's explicit acceptance of the scoped architecture and disposition.

- [ ] **Step 4: Update `evidence-rating-governance.md` and `weighting-direction.md`**
  Align with the versioned parameter bundle `1.0.0` and explicit disposition.

---

### Task 5: Static Checks, Full Verification, and Truthful Worklog

**Files:**
- Create: `docs/worklog/2026-10-02-ttsA-parameter-bundle-validation.md`

- [ ] **Step 1: Run full automated test suite**
  Run: `.venv/bin/python -m pytest tests/test_engine_path_ranking_conformance.py tests/test_path_ranking_interface.py tests/test_seamless_packet.py tests/test_seamless_parameter_proposal.py -q`
  Expected: 235+ tests pass cleanly.

- [ ] **Step 2: Run linters and contract checks**
  Run: `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python scripts/check_contract.py && .venv/bin/python scripts/check_repository.py`
  Expected: All checks pass.

- [ ] **Step 3: Write truthful worklog**
  Create `docs/worklog/2026-10-02-ttsA-parameter-bundle-validation.md` in Vietnamese.
  Adhere to single sentence per line in markdown.
  Document exact actions, results, limitations, and governance commitments.

- [ ] **Step 4: Git commit and push**
  Commit with clean commit message (no co-author tag).
  Push branch to `upstream` (or `origin` if appropriate).
  Open Pull Request via `gh pr create` with reference to #143, #158, #42, #48.
  Do not self-merge!
