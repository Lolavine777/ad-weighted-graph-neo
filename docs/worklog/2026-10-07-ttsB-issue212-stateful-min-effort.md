# Worklog — 2026-10-07 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #212, #211, #206, #207 (PR #220); M3-B2 / Week 4. Reviewer @Lolavine777.
- Nhánh: `feat/212-stateful-min-effort`.
- Người thực hiện: @nairyuuu (TTS B).
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

Triển khai hoàn thiện Issue #212: Stateful Min-Effort search, checkpoint và asset-goal semantics qua public query API cho Week 4:

1. **Stateful Candidate Generation & Declarative Query**:
   - Query chỉ khai báo source foothold, capabilities ban đầu, facts/assumptions, target asset, target goal / security predicate, budget, action bindings và ranking configuration. Tuyệt đối **không truyền ordered attack path**.
   - Tìm kiếm bảo toàn branch-local `AttackState`, actor switching context, and canonical graph immutability. Các permissions/relationships dẫn xuất chỉ tồn tại trong branch state, không mutate raw graph hay provenance.
   - Known-false vetoes optimistic assumptions; missing facts không có assumption giữ indeterminate; unresolved transitions không apply success effects.

2. **Tách biệt DA Checkpoint và Final Asset Goal**:
   - Checkpoint Domain Admin (ví dụ `effective_member(Alice, Admins)`) là một mốc đặc quyền riêng biệt.
   - Final asset success đòi hỏi thỏa mãn bảo mật predicate (ví dụ `admin_control(C0)`).
   - Khi chạm DA checkpoint nhưng đường tới final asset bị blocked hoặc indeterminate, kết quả báo cáo chính xác:
     - `checkpoint_reached = True`, `final_goal_reached = False`.
     - `status`: `"checkpoint_reached_final_goal_blocked"` hoặc `"checkpoint_reached_final_goal_indeterminate"`.
     - Chẩn đoán chi tiết qua thuộc tính `checkpoint_diagnostics`.

3. **Min-Effort qua Canonical Evaluator (#207/ADR-0013)**:
   - Dùng lại toàn bộ bộ đánh giá canonical candidate program (`evaluate_search_candidates` từ `PathRankingEngine` v1.0.0). Không dùng structural Dijkstra hay đếm hop thô.
   - Min-Effort tính tổng effort của các work units duy nhất theo accepted identity/owner/target/context/event bindings.
   - Kiểm chứng chặt chẽ Counter-structural Min-Effort trên fixture A2 (`synthetic-a2-e.json`): Path 3 (2 hops, effort = 2) thắng Path 1 (1 hop, effort = 5).
   - Deduplication: Các work unit tái sử dụng trong cùng một attack program không bị tính lặp; các work unit khác target/context không bị gộp nhầm. Cạnh membership thụ động không sinh active work unit (effort = 0).
   - Deterministic tie-breaking: Trên Ledger T (`synthetic-a2-t.json`), cả 3 paths đạt effort = 2, tie được giải quyết ổn định 100% qua các lần chạy lặp lại (`all_best_paths` và `best_path`).

4. **Completeness & Optimization Scope Lattice**:
   - Thuộc tính `optimization_scope` phản ánh chính xác giới hạn của kết luận:
     - `"exhaustive_within_scope"`: Không gian tìm kiếm hữu hạn được duyệt đầy đủ, không bị cắt tỉa, toàn bộ candidates feasible đều được rated $\rightarrow$ `is_minimum_proven_over_scope = True`.
     - `"best_in_rated_subset"`: Không gian tìm kiếm hoàn chỉnh nhưng tồn tại feasible candidate unrated $\rightarrow$ `is_minimum_proven_over_scope = False`.
     - `"best_in_generated_subset"`: Tìm kiếm bị truncated bởi budget caps nhưng tìm được ứng viên $\rightarrow$ `is_minimum_proven_over_scope = False`.
     - `"truncated_incomplete"`: Tìm kiếm bị truncated và chưa có đường đi $\rightarrow$ `status = "truncated"`, `is_no_path_proven_over_scope = False`.
   - `is_no_path_proven_over_scope`: Chỉ khẳng định `True` khi scope hoàn chỉnh, untruncated, không có gate indeterminate, và không có đường đi tới đích.

5. **Bộ Kiểm thử Độc lập và Hồi quy**:
   - Thêm bộ test toàn diện `tests/test_week4_min_effort_search.py` (14/14 tests passed trong 1.39s).
   - Regression suites:
     - `tests/test_week4_min_effort_search.py` + `tests/test_week4_query_materialization.py`: 39/39 passed.
     - `tests/test_week3_engine_acceptance.py` + `tests/test_week3_semantic_bridge.py` + `tests/test_attack_semantics_transitions.py`: 103/103 passed.
     - Toàn bộ focused suite: 249 passed.
   - Linter `ruff check` và `ruff format --check`: All checks passed.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Stateful Min-Effort & Checkpoint API | `src/engine/query.py` | Hoàn thiện integration với `evaluate_search_candidates` |
| Conformance test suite #212 | `pytest tests/test_week4_min_effort_search.py -v` | 14/14 passed |
| Week 4 Query Materialization & Min-Effort | `pytest tests/test_week4_min_effort_search.py tests/test_week4_query_materialization.py -v` | 39/39 passed |
| Week 3 Engine Regression | `pytest tests/test_week3_engine_acceptance.py tests/test_week3_semantic_bridge.py tests/test_attack_semantics_transitions.py -q` | 103 passed |
| Focused Engine & Scenario Regression | `pytest tests/test_week4_min_effort_search.py tests/test_week4_query_materialization.py tests/test_query_boundary_regressions.py tests/test_week4_scoring.py tests/test_week4_scenarios.py tests/test_attack_scenarios.py tests/test_engine.py -q` | 249 passed |
| Documentation | `docs/research/week4-min-effort-search.md`, `docs/research/week4-query-api.md` | Hoàn thành docs tiếng Việt chi tiết |
| Linter & code quality | `ruff check src/ tests/`, `ruff format --check src/ tests/` | All checks passed |

## Xử lý Review của @Lolavine777 trên PR #223

### Vòng 1 (commit af54c357)
Reviewer @Lolavine777 đã thực hiện deep review tại commit `af54c357` và yêu cầu chỉnh sửa 3 điểm (2 blockers + 1 major):

1. **[BLOCKER 1] Generated paths thiếu action binding làm hạ scope claim và lưu vết diagnostics**:
   - Khi có ít nhất một generated semantic path thiếu action binding, `MaterializedQuery.run()` lưu vết đầy đủ trong `binding_diagnostics` (gồm candidate_id, lý do và chi tiết các bước chưa bind), đính kèm vào `ranking_result["search_audit"]` và expose qua `result.binding_diagnostics` cũng như `result.diagnostics`.
   - Bắt buộc hạ cấp scope claim xuống `best_in_bound_subset`, và đặt `is_minimum_proven_over_scope = False`.
   - Bổ sung regression test: `test_omitted_action_binding_on_lowest_effort_path_downgrades_scope`.

2. **[BLOCKER 2] Tách biệt hoàn toàn Min-Effort scope/ties với Risk/Pareto partitioning**:
   - Min-Effort ties (`all_best_paths`, `tie_count`, `all_best_candidate_ids`) và `best_path` được tính toán trên **toàn bộ assessed candidates** (`assessed_candidates`), không bị thu hẹp vào phân vùng `eligible_candidates` (vốn chỉ dành cho candidate đủ điều kiện risk ranking với cả likelihood và impact rated).
   - Ứng viên có effort rated nhưng impact/likelihood unrated vẫn được Min-Effort chọn và tie đúng.
   - Chỉ unrated effort mới hạ cấp Min-Effort completeness; unrated impact/likelihood không làm mất tính toàn vẹn của Min-Effort.
   - Bổ sung regression test: `test_min_effort_retains_candidate_with_unrated_impact_or_likelihood`.

3. **[MAJOR 3] Fail-closed khi có xung đột Alias vs Canonical trong `action_bindings`**:
   - Triển khai `_normalize_action_bindings()`: kiểm tra xung đột canonical key `(technique, actor, source, target)`.
   - Nếu hai khóa cùng resolve về một canonical key nhưng khác `action_id`, hệ thống fail-closed ném `ValueError`. Khai báo trùng lặp cùng `action_id` được deduplicate tường minh.
   - Bổ sung regression test: `test_action_bindings_alias_canonical_collision_fail_closed`.

### Vòng 2 (commit 000d419)
Reviewer @Lolavine777 rereview commit `000d419` xác nhận 3 điểm vòng trước đã sửa đúng, nhưng phát hiện thêm 2 blockers mới + 1 docs/API mismatch:

1. **[BLOCKER 1 - Rereview] Candidate bị canonical adapter/validator reject vẫn làm hạ completeness claim**:
   - Mọi candidate sinh ra không đi qua adapter/validator tới `assessed_candidates` (do unknown action ID, mismatched actor/target, hoặc invalid envelope) đều được coi là coverage gap.
   - Đưa vào `binding_diagnostics` với reason và diagnostic message từ adapter/validator; surface qua public `result.diagnostics` với `status: "rejected"`.
   - Scope claim hạ cấp về `best_in_bound_subset` (hoặc `no_bound_candidates` nếu không còn candidate nào), `is_minimum_proven_over_scope = False`.
   - Bổ sung regression test: `test_adapter_rejected_candidate_on_lowest_effort_path_downgrades_scope`.

2. **[BLOCKER 2 - Rereview] Tích hợp Min-Effort cho Zero-action / Initial-goal success**:
   - Khi `initial_state` đã thỏa mãn `target_goal` (kể cả khi foothold/actor khác target asset, ví dụ Alice đã có `admin_control(Host)`), search trả về 1 đường đi 0 bước.
   - Xử lý tường minh trong cả `MaterializedQuery.run()` và `generate_and_evaluate_attack_paths()` với ngữ nghĩa 0 work: `minimum_effort_value = 0.0`, `best_path.cost = 0.0`, `all_best_paths = (best_path,)`, `tie_count = 1`.
   - Khẳng định `exhaustive_within_scope` và `is_minimum_proven_over_scope = True`. Loại bỏ hoàn toàn hidden adapter rejection.
   - Bổ sung regression test: `test_zero_action_initial_goal_satisfaction_with_distinct_foothold_and_target`.

3. **[MAJOR 3 - Rereview] Đồng bộ Public Docs và PR Body với Exact Public API**:
   - `docs/research/week4-query-api.md`: Bổ sung toàn bộ các giá trị của scope lattice (`best_in_bound_subset`, `no_bound_candidates`, `no_rated_candidates`, v.v.), chuẩn hóa schema trường của `min_effort` (`minimum_effort_value`, `goal_id`, `best_candidate_id`, `associated_likelihood_interval`, `associated_impact`, `coverage_disclosure`, `baseline_coverage`), và mô tả zero-action semantics.
   - `docs/research/week4-min-effort-search.md`: Sửa các trường `min_effort` (loại bỏ `best_program_effort` và `effort_status` không tồn tại, thay bằng `minimum_effort_value`), cập nhật bảng 3.6 và thêm Section 3.7.
   - Cập nhật PR description trên GitHub PR #223.

## Điều học được / quyết định

- **Không dùng structural Dijkstra**: Min-Effort thực tế trên Active Directory không tương đồng với shortest path trên graph cấu trúc. Fixture A2 chứng minh đường 2 hops có effort thấp hơn đường 1 hop (effort 2 vs 5). Min-Effort phải được tính toán thông qua canonical whole-path candidate program assessment với đầy đủ identity/owner/target/context bindings từ scoring package #207.
- **Bảo toàn tính toàn vẹn toán học của Optimization Scope**: Khi search bị cắt tỉa do budget (`truncated=True`), có binding gap (`binding_diagnostics`), hoặc còn feasible program chưa có effort basis (`unrated`), kết luận chỉ được phép giới hạn ở `best_in_generated_subset`, `best_in_bound_subset` hoặc `best_in_rated_subset`. Tuyệt đối không tự suy diễn global minimum hoặc claim no-path.
- **Ranh giới Checkpoint vs Asset Success**: DA membership chỉ là một intermediate state; việc đạt DA không tự động đồng nghĩa với compromise asset mục tiêu nếu admin channel hoặc credential gate chưa thỏa mãn. Báo cáo trạng thái tách biệt kèm `checkpoint_diagnostics` giúp tooling thượng tầng (#213) dễ dàng phân tích root-cause.

## Trở ngại và việc kế tiếp

- Các hạng mục non-goals (#213 CLI packaging, #215 snapshot SPN fact store, #216 Kerberoasting) tiếp tục được giữ ngoài scope của PR #212.
- Commit, push bổ sung lên nhánh `feat/212-stateful-min-effort` và phản hồi rereview trên PR #223 để @Lolavine777 nghiệm thu.

## Review PR #232: zero-action validation boundary (2026-10-08)

- Phát hiện → fast path 0 bước bỏ qua query/snapshot validation và tự tạo likelihood `[1,1]`, impact và Pareto eligibility.
- Ảnh hưởng → payload sai snapshot/metadata có thể nhận kết luận effort 0 và canonical fully rated dù chưa được validate.
- Xử lý → dùng chung `evaluate_zero_action_initial_goal()` cho hai API; reuse canonical evaluator với zero envelopes để validate đầy đủ và giữ parameter audit. Kiểm tra actor/target binding; effort 0 được ghi riêng tại `zero_work_disposition`, không tạo assessed/eligible/Pareto candidates, không suy ra P/I.
- Regression → 16 cases mới cho hai entry points: snapshot sai, metadata thiếu/sai, section bắt buộc thiếu, actor/target sai, P/I đủ/thiếu basis; kiểm tra roundtrip, input immutability và canonical baseline không bị thay thế.
- Validation → Python 3.14.7, dependencies theo requirements-dev.txt: 338 tests engine/ranking/query pass; Ruff lint/format trên 3 file Python sửa đều pass.
