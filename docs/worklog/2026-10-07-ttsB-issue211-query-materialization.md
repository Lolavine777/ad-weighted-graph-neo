# Worklog — 2026-10-07 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #211, #204, #205; M3-B1 / Week 4. Reviewer @Lolavine777.
- Nhánh: `feat/211-week4-query-materialization`.
- Người thực hiện: @nairyuuu (TTS B).
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

Triển khai public query/scenario materialization và fact-resolution layer cho Week 4 theo yêu cầu Issue #211 và handoff A1 (#205):

1. **Public Materialization Entry Point**:
   - Thêm `src/engine/query.py` với các public classes và functions: `materialize_query()`, `run_attack_query()`, `resolve_scenario_facts()`, `AttackQuery`, `MaterializedQuery`, `AttackQueryResult`, `RejectedAssumption`.
   - Export qua `src/engine/__init__.py`.
   - Caller chỉ cần khai báo bài toán (source foothold, initial capabilities, facts/assumptions, target asset, target goal / security predicate, budget) mà **không phải truyền sẵn ordered attack path**.
   - Dùng lại 100% `generate_attack_paths()` và stateful search hiện hành của engine, không tạo search engine song song.

2. **Bảo toàn 7 Invariants bắt buộc**:
   - **Invariant 1 (Source foothold != usable identity)**: Khai báo `source_foothold` là Computer (Host) chỉ sinh `control(Host)`, không tự động suy diễn `usable_identity` của bất kỳ domain identity nào. Không cho phép actor-switch thành domain user khi không có credentials hợp lệ.
   - **Invariant 2 (AttackState != RuntimeContext)**: Tách biệt hoàn toàn attacker capabilities (`AttackState`: control, admin_control, usable_identity, permissions...) và environment/runtime conditions (`RuntimeContext`: facts, authentication_context, withheld evidence).
   - **Invariant 3 (Fact resolution trước semantic evaluation)**: Authoritative/observed facts luôn được ưu tiên hơn declared assumptions. Known-false vetoes bất kỳ assumption optimistic nào trong cùng key/scope (`value = False`, assumption bị reject, không bao giờ resolve thành True). Missing fact không có assumption giữ nguyên unknown/indeterminate, không mặc định True/False.
   - **Invariant 4 (Auditable rejected assumptions)**: Mọi rejected assumption được lưu vết cấu trúc trong `RejectedAssumption(predicate, subject, target, assumption_value, scope, reason, conflicting_fact, rationale)` và expose qua `materialized_query.rejected_assumptions`. Rejected assumptions không bao giờ đi vào `RuntimeContext` dưới dạng true fact.
   - **Invariant 5 (Context-scoped usable identity)**: `usable_identity` luôn được biểu diễn và bảo toàn dưới dạng tuple `(principal, authentication_context)`. Một credential tại HostA không thể dùng trong HostB context.
   - **Invariant 6 (Target asset != success)**: Phân biệt rõ target asset node và security success predicate (`admin_control`). Chạm node không được coi là thỏa mãn nếu state predicate chưa đạt. Bắt buộc caller khai báo target goal hoặc callable success predicate (fail-closed nếu thiếu). Khi có cả hai, áp dụng phép hội AND để callable không thể bypass `required_state`.
   - **Invariant 7 (DA checkpoint != final asset compromise)**: Hỗ trợ `checkpoint_state_predicate`. Khi đạt DA checkpoint nhưng gate vào final target asset bị blocked/indeterminate, checkpoint được ghi nhận là reached, nhưng final goal không đạt (`status != success`, paths = 0).

3. **Xử lý toàn diện phản hồi Review của @Lolavine777 trên PR #221**:
   - **Target-only fail-closed & Goal Conjunction**: Bắt buộc có `target_goal` hoặc `success_state_predicate`, kết hợp AND khi cả hai cùng xuất hiện.
   - **Outcome truncation explicit**: Search bị bounded/truncated trả về explicit status `"truncated"`, tuyệt đối không kết luận terminal `no_path` hay `blocked`.
   - **Conservative lattice aggregation**: Trong query outcome, `indeterminate` được ưu tiên hơn `blocked` khi có mixed attempts, ngăn chặn việc blocked noise ở dead-end branch che khuất nhánh khả dĩ đang indeterminate.
   - **Chống Assumption origin spoofing**: Kiểm tra nghiêm ngặt `origin`, bắt buộc `DECLARED_ASSUMPTION` và đầy đủ `scope`, `rationale`.
   - **Scope-aware isolation**: Hỗ trợ `active_scope`, cô lập view, ngăn cross-scope collapse và reject fail-closed khi có cross-scope mixing mà thiếu `active_scope`.
   - **Input Enum/Technique validation fail-closed**: Giới hạn `evaluation_mode` trong `{"scenario", "evidence_only"}` và kiểm tra mọi technique ID trong `allowed_techniques` với catalog.

4. **Kiểm thử tại revision `e249137` (trước vòng review bổ sung)**:
   - Bộ unit & integration suite `tests/test_week4_query_materialization.py`: 25/25 passed.
   - Kiểm tra hồi quy:
     - `tests/test_week4_scenarios.py`, `tests/test_week4_query_materialization.py`, `tests/test_engine.py`, `tests/test_contract.py`, `tests/test_repository.py` (229 passed).
     - `tests/test_attack_scenarios.py`, `tests/test_attack_scenarios_seamless.py`, `tests/test_week3_engine_acceptance.py` (158 passed).
     - Ruff linter & formatter: All checks passed.
     - `scripts/check_contract.py` và `scripts/check_repository.py`: All passed (441 tracked files).

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Implement materialization & review fixes | `src/engine/query.py`, `src/engine/__init__.py` | Đầy đủ `materialize_query()`, `run_attack_query()`, `resolve_scenario_facts()` |
| Cases A - H & Review regression tests | `pytest tests/test_week4_query_materialization.py -v` | 25/25 passed (2.48s) |
| Focused regression suite | `pytest tests/test_week4_scenarios.py tests/test_week4_query_materialization.py tests/test_engine.py tests/test_contract.py tests/test_repository.py -q` | 229 passed (12.33s) |
| Scenario foundation regression | `pytest tests/test_attack_scenarios.py tests/test_attack_scenarios_seamless.py tests/test_week3_engine_acceptance.py -q` | 158 passed (38.03s) |
| Linter & code quality | `ruff check src/ tests/`, `ruff format --check src/ tests/` | All checks passed |
| Contract & repository checks | `python scripts/check_contract.py`, `python scripts/check_repository.py` | Contract 2 fixtures validated; 441 tracked files passed |

## Điều học được / quyết định

- Không tạo thêm framework hoặc graph schema song song: adapter/materialization layer mỏng trong `src/engine/query.py` là hoàn toàn đủ để nối public query declarative với engine `generate_attack_paths()`.
- Fact resolution diễn ra tại materialization phase giải quyết triệt để vấn đề `RuntimeContext` exception trước khi semantic evaluation bắt đầu: facts contradictory giữa authoritative False và assumption True được giải quyết dứt khoát bằng known-false veto, assumption bị loại bỏ khỏi `RuntimeContext` và đưa vào rejected assumptions audit ledger.
- Conservative lattice là thiết kế đúng đắn: `indeterminate` phải ưu tiên hơn `blocked` ở mức query outcome aggregation để tránh false negative khi còn route khả dĩ phụ thuộc missing facts.
- Truncated outcome phải explicit để tránh overclaim tính bất khả thi khi search chỉ mới dừng vì hết budget.

## Trở ngại và việc kế tiếp

- Các non-goals (#212 Min-Effort, #213 CLI packaging, #215 snapshot SPN fact store, #216 Kerberoasting) được phân định rõ ràng và defer cho các task tiếp theo.
- Push commit bổ sung và cập nhật review trên PR #221.

## Bổ sung sau deep review PR #221

- Tách explicit scenario/view dimension qua `assumption_metadata.view_id`; `active_scope`
  chọn view này thay vì lọc theo raw `RuntimeFact.scope`. Untagged records thuộc query
  hiện tại và được giữ lại. Known-false dùng scenario ID vẫn veto assumption dùng horizon
  theo convention của `context_for_projection()`; nhiều authoritative views thiếu selector
  bị reject thay vì collapse. Selector rỗng/không tồn tại cũng bị reject.
- Intersect `allowed_techniques` với cả default/custom catalog; danh sách rỗng giữ nghĩa
  không cho phép kỹ thuật nào, không bật lại toàn bộ catalog.
- Validate checkpoint mapping/target/non-empty required state; checkpoint goal và callable
  dùng AND. Callable không bypass required state hoặc che malformed checkpoint.
- Tham số explicit `evaluation_mode` ưu tiên field query cho cả mapping/dataclass;
  không silently đổi mode/view của query đã materialize.
- Bắt buộc assumption có provenance reference hoặc metadata `declared_by`/`source`,
  trên cả typed/mapping và hai input channels. Ledger rejected giữ nguồn khai báo.
- Thêm [API notes](../research/week4-query-api.md) và 24 regression cases độc lập ở
  `tests/test_query_boundary_regressions.py`; cập nhật test input provenance/view labels.

Validation local: Python 3.12.14, pytest 9.1.1. Focused suites gồm query, Week 4 scenarios,
engine, contract, repository: **252 passed, 1 skipped** (thiếu private raw data).
`ruff check src/ tests/`, `ruff format --check src/ tests/`, `git diff --check`,
contract validator (2 fixtures) và repository checks (443 files) đều pass.
Full-suite collection local không chạy trên Python 3.12 vì source nền dùng syntax
Python 3.14; CI của repo dùng Python 3.14 để kiểm tra đầy đủ sau push.

CI Windows ở `77f201f` phát hiện test mới đọc fixture tiếng Việt bằng default cp1252.
Đã sửa cả hai `read_text()` của regression module thành explicit UTF-8 trước lượt CI kế tiếp.
