# Implementation Plan: Independent Rating Packet & Governance Handoff (Refs #143, #42, #48)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuẩn bị gói định mức độc lập (Rating Packet) cho một scenario hẹp, cập nhật hồ sơ quản trị và điều kiện nghiệm thu ADR-0013 (Proposed), bổ sung helper đối soát, đồng bộ trạng thái bàn giao #48 và lập worklog ngày 2026-10-01 cho TTS A.

**Architecture:** Giữ nguyên trạng thái ADR-0013 là Proposed và đặc tả giao diện v1.0.0; đóng gói kịch bản hẹp với đầy đủ tài sản đích, giả định runtime tách rời cấu trúc quan sát, định danh chuẩn tắc đơn vị công việc chống đếm trùng; tạo hai phiếu chấm trống độc lập và biên bản đối soát với rater identity giữ pending; xuất các hàm tính độ đồng thuận (IoU, Cohen's Kappa fallback, epistemic uncertainty) sang wire adapter có test bảo vệ; cập nhật brief tiếng Việt và trạng thái handoff.

**Tech Stack:** Python 3.14 (.venv), stdlib `fractions.Fraction`, pytest, ruff, yamllint, Markdown (sentence-per-line).

**Spec:** Issue #143 comment 5922929926 (https://github.com/nairyuuu/ad-weighted-graph/issues/143#issuecomment-5922929926), ADR-0013, `evidence-rating-governance.md`, `path-ranking-interface-specification.md`.

## Global Constraints

- Never use em dash (—) or en dash (–). Use plain ASCII hyphen-minus (-) instead.
- When writing commit messages, NEVER auto-add agent name as co-author.
- Never manually modify CHANGELOG.md files or any files marked as auto-generated.
- When writing long Markdown files, put each full sentence on its own physical line.
- Always run Python scripts using the python executable from the virtual environment (.venv).
- Zero placeholders (no TODO, pass, ..., unverified stubs).
- Evidence before assertions: run verification commands and verify output.
- Do not fabricate rater identity, ratings, or consensus. Keep pending until real raters participate.
- Do not convert synthetic fixture numbers into production parameters.
- Do not change ADR-0013 from Proposed to Accepted without explicit disposition approval.
- Do not modify parser or engine code belonging to TTS B.

---

### Task 1: Cập nhật ADR-0013 với Bảng Checklist Nghiệm thu (Acceptance Disposition)

**Files:**
- Modify: `docs/adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md`

**Interfaces:**
- Consumes: ADR-0013 current proposed text and PR #152 merge state.
- Produces: Updated ADR-0013 retaining `Proposed` status with explicit disposition checklist and conditions for transitioning to `Accepted`.

- [ ] **Step 1: Check existing status and sections in ADR-0013**
- [ ] **Step 2: Add Acceptance Disposition Checklist to ADR-0013**
  Bổ sung bảng tiêu chí chuyển trạng thái từ Proposed sang Accepted, giải thích rõ ràng việc merge PR #152 chỉ chấp thuận proposal và đặc tả giao diện v1.0.0, chưa tự động coi ADR là Accepted.
- [ ] **Step 3: Verify formatting and sentence-per-line in ADR-0013**

---

### Task 2: Xuất các Hàm Quản trị Độ đồng thuận trong Wire Adapter và Viết Tests

**Files:**
- Modify: `scripts/research/path_ranking_wire_adapter.py`
- Modify: `tests/test_path_ranking_interface.py`

**Interfaces:**
- Consumes: Mathematical specifications of IoU, Epistemic Uncertainty, and Cohen's Kappa with degenerate zero-variance fallback from `evidence-rating-governance.md`.
- Produces: Exported functions `compute_interval_iou`, `check_epistemic_uncertainty`, `compute_kappa_with_fallback`, `reconcile_expert_ratings` in `path_ranking_wire_adapter.py`.

- [ ] **Step 1: Write test cases in `tests/test_path_ranking_interface.py` importing functions directly from `scripts.research.path_ranking_wire_adapter`**
- [ ] **Step 2: Run test to verify import failure**
  Run: `.venv/bin/python -m pytest tests/test_path_ranking_interface.py -k test_wire_adapter_governance_functions`
- [ ] **Step 3: Implement functions in `scripts/research/path_ranking_wire_adapter.py`**
- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/python -m pytest tests/test_path_ranking_interface.py -k test_wire_adapter_governance_functions`

---

### Task 3: Xây dựng Gói Định mức Độc lập (Rating Packet) cho Scenario Hẹp

**Files:**
- Create: `docs/research/scenario-rating-packet.md`

**Interfaces:**
- Consumes: Scenario contract from `week3-scenario-contract.md`, YAML rating schemas from `evidence-rating-governance.md`, bound actions catalog, and persistent work ledger conventions.
- Produces: Complete independent rating packet document containing:
  - Scenario scope, target asset `DC01$`, success event, and consequence criteria.
  - Separation between observed structural evidence (snapshot provenance) and runtime assumptions.
  - Bound actions catalog and persistent work units ledger with canonical IDs.
  - Anti-overlap rules and shared preparation tags.
  - Full-prefix conditional quantities requiring estimation.
  - Primary technical references with locators (MS-SAMR, MS-DRSR, MITRE ATT&CK).
  - Two blank independent rating sheets (Rater 1 and Rater 2) with status `PENDING`.
  - Sample raw rating records (YAML schemas for impact, likelihood, effort).
  - Reconciliation record template with agreement formulas and `PENDING` sign-off.

- [ ] **Step 1: Draft `docs/research/scenario-rating-packet.md` with complete sections**
- [ ] **Step 2: Verify no em dash, ensure sentence-per-line rule, and check all links**

---

### Task 4: Cập nhật Trạng thái Bàn giao #48 và Đồng bộ Tài liệu Hướng Trọng số

**Files:**
- Modify: `docs/research/weighting-direction.md`
- Modify: `docs/research/evidence-rating-governance.md`

**Interfaces:**
- Consumes: Current issue status across repository (#138, #140, #141, #142, #150 closed; #143, #42, #48 open).
- Produces: Updated status tables and matrices explicitly reflecting:
  - Proposal: Reviewed.
  - ADR: Proposed (ADR-0013).
  - Interface: Proposed (Reviewed via #152).
  - Rating Packet: Prepared (Pending Real Raters).
  - Parameters: Pending.
  - Integration: Pending (TTS B M3 / #145).
  - Structural E2E: Verified.
  - Reconciliation / BloodHound Parity: Pending (M4 / #47 / #82 / #48).

- [ ] **Step 1: Update status matrix and handover in `docs/research/weighting-direction.md`**
- [ ] **Step 2: Update status in `docs/research/evidence-rating-governance.md`**

---

### Task 5: Viết Brief Tiếng Việt Dễ Đọc và Ví dụ Tính Tay

**Files:**
- Modify: `docs/research/week3-scenario-cost-evidence.md`

**Interfaces:**
- Consumes: Worked example results from Experiment 6 and wire adapter arithmetic.
- Produces: 7-stage end-to-end explanation (Dữ liệu -> Cấu trúc -> Semantics -> Scenario -> Rating -> Tính toán -> So sánh Pareto -> Validation), distinction between human rating vs automated script calculations, and step-by-step hand calculation matching output.

- [ ] **Step 1: Add/expand section in `docs/research/week3-scenario-cost-evidence.md`**
- [ ] **Step 2: Verify hand calculation values match code exactly**

---

### Task 6: Lập Worklog TTS A Ngày 2026-10-01 và Chạy Toàn Bộ Bộ Kiểm Tra

**Files:**
- Create: `docs/worklog/2026-10-01-ttsA.md`

**Interfaces:**
- Consumes: Test and tool outputs from the current session.
- Produces: Complete daily worklog for TTS A on 2026-10-01 following repository standards.

- [ ] **Step 1: Run full test suite: pytest, ruff, yamllint, check_contract, check_repository, git diff --check**
- [ ] **Step 2: Write `docs/worklog/2026-10-01-ttsA.md`**
- [ ] **Step 3: Verify all repository checks pass cleanly**
