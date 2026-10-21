# Stateful Min-Effort Search, Checkpoint và Asset Semantics (Week 4)

Refs #212, PR #221, #206, #207 (PR #220), #204, #205.
Tài liệu đặc tả hành vi thực tế của stateful Min-Effort search, DA checkpoint vs final asset goal, và optimization scope lattice cho Week 4.

---

## 1. Mục tiêu và Kiến trúc

Triển khai hoàn thiện yêu cầu của Issue #212:
1. **Declarative query**: Caller khai báo source foothold, capabilities ban đầu, facts/assumptions, target asset, target goal / security predicate, search budget, action bindings và ranking query; **không truyền ordered attack path**.
2. **Stateful Candidate Generation**: Tự động sinh semantic transitions bảo toàn branch-local `AttackState`, canonical graph immutability, actor switching context và provenance.
3. **Phân tách Checkpoint DA vs Final Asset Compromise**: Checkpoint đạt không đồng nghĩa compromised final asset. Hỗ trợ diagnostics chuyên biệt (`checkpoint_diagnostics`).
4. **Min-Effort qua Canonical Evaluator**: Sử dụng canonical whole-path evaluator (PathRankingEngine v1.0.0 từ #207) và accepted work-unit/cost bindings. Không dùng structural Dijkstra.
5. **Completeness & Optimization Scope Lattice**: Giới hạn kết luận tối ưu/no-path nghiêm ngặt theo finite completeness, unrated elements, và truncation limits.

---

## 2. API Public và Cách Sử Dụng

### 2.1 Khởi tạo và Thực thi Query

```python
from src.engine import AttackQuery, run_attack_query

# Query hoàn chỉnh với action_bindings và ranking_query
query = AttackQuery(
    initial_actor="Alice",
    initial_state={"control": ["Alice"]},
    target="Host",
    target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
    checkpoint_goal={
        "target": "Admins",
        "required_state": {"effective_member": [["Alice", "Admins"]]},
    },
    aliases={"Alice": "S-1-5-21-1000", "Host": "S-1-5-21-3000", "Admins": "S-1-5-21-2000"},
    runtime_facts=runtime_facts,
    action_bindings={
        ("obtain_admin_execution_on_host", "Alice", "Alice", "Host"): "act-exec-direct",
        ("propagate_group_entitlement", "Alice", "Alice", "Admins"): "act-member-direct",
    },
    ranking_query=ranking_payload,
    budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
)

# Chạy stateful search và Min-Effort ranking
result = run_attack_query(query, graph)
```

### 2.2 Các Trường Kết Quả Bổ Sung trong `AttackQueryResult`

- `min_effort`: Dict chuẩn theo canonical baseline (#207/Spec 3.4), bao gồm:
  - `goal_id`: ID mục tiêu đánh giá.
  - `best_candidate_id`: ID ứng viên tối ưu (chuỗi hoặc `None`).
  - `minimum_effort_value`: Giá trị effort tối thiểu (float/int hoặc `None`).
  - `associated_likelihood_interval`: Khoảng xác suất likelihood của ứng viên tối ưu.
  - `associated_impact`: Điểm đánh giá consequence impact của asset mục tiêu.
  - `coverage_disclosure`: Thông báo bảo đảm hoặc giới hạn toán học cho baseline.
  - `baseline_coverage`: Dict chứa `is_truncated`, `truncation_reasons`, `completeness_scope`, `caps_applied`.
  - `all_best_candidate_ids`: Danh sách tất cả candidate IDs đạt cùng mức minimum effort.
  - `tie_count`: Số lượng ứng viên tie ở mức minimum effort.
- `best_path`: `PathResult` tương ứng với chương trình tấn công có effort tối thiểu (với `path.cost` phản ánh `minimum_effort_value`).
- `all_best_paths`: Tuple chứa tất cả `PathResult` đạt cùng mức effort tối thiểu (đồng nhất cost, hỗ trợ phân tích đa phương án).
- `ranking_result`: Toàn bộ output chuẩn hóa từ `evaluate_search_candidates()`.
- `binding_diagnostics`: Dict ghi nhận các candidate programs bị loại khỏi ranking do thiếu action binding (`explicit_action_binding_missing`) hoặc bị canonical ranking adapter / envelope validator reject (`adapter_ineligible`, `canonical_candidate_invalid`), kèm lý do và thông điệp diagnostic.
- `optimization_scope`: Trạng thái phạm vi tối ưu hóa:
  - `"exhaustive_within_scope"`: Không gian tìm kiếm hữu hạn được duyệt cạn kiệt, không bị cắt tỉa do budget, không có binding/adapter gap, toàn bộ feasible candidates đều có effort rated.
  - `"best_in_bound_subset"`: Tồn tại candidate bị loại khỏi ranking do thiếu action binding hoặc bị adapter/validator reject; tối ưu chỉ bảo đảm trên tập con bound/validated.
  - `"best_in_rated_subset"`: 100% candidate sinh ra đều được bind/validate, nhưng tồn tại feasible candidate chưa có effort rated (do thiếu work-unit basis).
  - `"best_in_generated_subset"`: Tìm kiếm bị cắt tỉa (truncated do `max_paths`, `max_steps`, hoặc `max_expansions`) nhưng đã tìm thấy ít nhất một đường đi khả dĩ.
  - `"truncated_incomplete"`: Tìm kiếm bị cắt tỉa do budget và chưa tìm thấy đường đi nào.
  - `"no_bound_candidates"`: Search tìm thấy paths nhưng toàn bộ bị loại do thiếu action binding hoặc adapter rejection.
  - `"no_rated_candidates"`: Có candidate bound/validated nhưng không có candidate nào rated effort.
- `is_minimum_proven_over_scope` (bool): `True` khi và chỉ khi `optimization_scope == "exhaustive_within_scope"`, không có binding/adapter gaps (`not binding_diagnostics`), và `minimum_effort_value` được xác định cụ thể.
- `is_no_path_proven_over_scope` (bool): `True` khi và chỉ khi không gian tìm kiếm hoàn chỉnh (`complete=True`, `truncated=False`), không có gate nào indeterminate/unknown, và `final_goal_reached=False`.
- `checkpoint_diagnostics`: Danh sách các diagnostics (blocked / indeterminate) cụ thể giải thích tại sao sau khi chạm DA checkpoint lại không thể tiến tới final asset goal.

---

## 3. Quy Tắc Ngữ Nghĩa và Tính Toán

### 3.1 Min-Effort vs Structural Dijkstra
- Min-Effort phản ánh tổng effort của các work units duy nhất theo accepted identity/owner/target/context/event bindings (#207).
- Không dùng số bước (hop count) hay Dijkstra trọng số tĩnh trên cạnh graph thô:
  - Fixture A2 (Ledger E): Path 3 (2 hops qua Group Membership + Inherited Admin, tổng effort = 2) đánh bại hoàn toàn Path 1 (1 hop trực tiếp Direct Admin, effort = 5) dù Path 1 ngắn hơn về số hops.
- Passive group membership edges không tự sinh active work unit (incur effort = 0).

### 3.2 Tách biệt Min-Effort vs Risk/Pareto Partitioning
- `compute_min_effort_baseline()` và việc tính `all_best_paths` / `tie_count` xét trên **toàn bộ assessed candidates** (cả partition `eligible_candidates` lẫn `diagnostics`).
- Ứng viên có `effort_status == "rated"` nhưng `impact_status` hoặc `likelihood_status` chưa rated vẫn được chọn và tie đầy đủ trong Min-Effort.
- Tính đầy đủ của Min-Effort (`exhaustive_within_scope`) chỉ phụ thuộc vào `effort`; unrated impact hoặc likelihood thuộc về bài toán risk ranking của ADR-0013 và không hạ cấp completeness của Min-Effort.

### 3.3 Chống Xung Đột Action Bindings (Fail-Closed)
- Khi normalize `action_bindings`, các khóa 4-tuple `(technique, actor, source, target)` được resolve alias sang canonical SID.
- Nếu hai mục khai báo khác nhau (ví dụ một dùng alias `"Alice"`, một dùng SID canonical) nhưng resolve thành cùng canonical key với **action ID khác nhau**, hệ thống bắt buộc báo lỗi fail-closed (`ValueError`).
- Khai báo trùng lặp với cùng một action ID được deduplicate tường minh.

### 3.4 Anti-Double-Counting và Ngữ Cảnh Work Unit
- Các work units trùng lặp trong cùng một candidate program được tự động deduplicate theo identity/owner/target/context/event bindings.
- Work units có target hoặc context khác nhau (ví dụ `TargetHost` vs `OtherHost`) tuyệt đối không bị gộp nhầm, giữ nguyên chi phí độc lập.

### 3.5 Phân Tách DA Checkpoint và Final Asset Goal
- Checkpoint Domain Admin chỉ là mốc đặc quyền trung gian (ví dụ `effective_member(Alice, Admins)`).
- Final asset success đòi hỏi thỏa mãn đầy đủ security predicate đối với asset mục tiêu (ví dụ `admin_control(C0)`).
- Báo cáo trạng thái rõ ràng:
  - Checkpoint đạt, asset gate blocked $\rightarrow$ `checkpoint_reached_final_goal_blocked`.
  - Checkpoint đạt, asset gate missing/unknown $\rightarrow$ `checkpoint_reached_final_goal_indeterminate`.
  - Checkpoint đạt, không có route tới asset $\rightarrow$ `checkpoint_reached_final_goal_no_path`.
  - Cả hai cùng đạt $\rightarrow$ `success`.

### 3.6 Quy Tắc Completeness và Giới Hạn Kết Luận Tối Ưu
Bảng chuyển trạng thái và quyền công bố kết luận:

| Điều kiện Tìm kiếm | Trạng thái Bindings | Đánh giá Effort | `optimization_scope` | `is_minimum_proven` | `is_no_path_proven` |
| --- | --- | --- | --- | --- | --- |
| Complete, Untruncated | 100% Paths Bound/Validated | 100% Feasible Rated | `exhaustive_within_scope` | **True** | False |
| Complete, Untruncated | Zero-Action Initial Goal | Effort = 0 (0 work) | `exhaustive_within_scope` | **True** | False |
| Complete, Untruncated | Có Binding Gap / Adapter Reject | $\ge 1$ Valid Candidates Rated | `best_in_bound_subset` | **False** | False |
| Complete, Untruncated | 100% Paths Unbound/Rejected | 0 Candidates Bound | `no_bound_candidates` | **False** | False |
| Complete, Untruncated | 100% Paths Bound/Validated | Có Feasible Unrated | `best_in_rated_subset` | **False** | False |
| Complete, Untruncated | Không có paths | N/A (No indeterminate) | `exhaustive_within_scope` | False | **True** |
| Complete, Untruncated | Không có paths | N/A (Có indeterminate) | `exhaustive_within_scope` | False | **False** |
| Truncated (Budget hit) | $\ge 1$ paths tìm thấy | Bất kỳ | `best_in_generated_subset` | **False** | False |
| Truncated (Budget hit) | 0 paths tìm thấy | Bất kỳ | `truncated_incomplete` | False | **False** |

> **Cấm Tuyệt Đối**:
> - Không bao giờ claim "no path exists" khi search bị truncated hoặc còn indeterminate gate.
> - Không bao giờ claim "global minimum" khi search bị truncated, còn feasible path unrated, hoặc tồn tại candidate bị adapter/validator reject.
> - Không gán score mặc định/zero cho unrated basis để ép ra kết luận tối ưu.
> - Giữ Min-Effort tách biệt với risk/Pareto ranking của ADR-0013; không gộp Complexity/Privilege/Impact thành một scalar duy nhất.

### 3.7 Xử Lý Zero-Action / Initial Goal Satisfaction
- Khi declared goal / security predicate đã được thỏa mãn ngay tại `initial_state` (kể cả khi foothold/actor khác target asset, ví dụ Alice đã nắm `admin_control(Host)`):
  - Semantic search trả về một `PathResult` 0 bước với `nodes=(target,)`, `edges=()`, `transition_history=()`.
  - Không đòi hỏi action binding cho các bước chuyển dịch (do 0 transitions).
  - Min-Effort được xác định tường minh với ngữ nghĩa 0 work: `minimum_effort_value = 0.0`, `best_path.cost = 0.0`, `all_best_paths = (best_path,)`, `tie_count = 1`.
  - Phân tích toán học: khi mục tiêu đã đạt tại trạng thái ban đầu, chi phí tối thiểu để đạt mục tiêu là 0 work; `optimization_scope` là `"exhaustive_within_scope"` và `is_minimum_proven_over_scope = True`.
  - Tránh triệt để việc adapter ranking từ chối ngầm (hidden adapter rejection) do khác biệt giữa singleton node và foothold ID.

- Khi có `ranking_query`, cả hai API đi qua query decoder, graph contract và kiểm tra snapshot; actor/target phải khớp metadata và thuộc canonical graph. Payload sai bị reject, kể cả đường 0 bước.
- `run_attack_query().min_effort` cho trường hợp này là disposition riêng có `disposition="semantic_initial_goal_zero_work"`, `ranking_status="not_applicable"`; nó cũng xuất hiện tại `ranking_result["zero_work_disposition"]`. Đây là bảo đảm **0 công việc mới theo declared semantic goal / initial AttackState**, không phải assessment của ranking success event.
- `associated_likelihood_interval=None`, `associated_impact=None`; không tự gán `[1,1]` hay consequence rating. `eligible_candidates={}`, `pareto_frontier=[]`, `assessed_candidates=[]`, `search_metadata.candidates_evaluated=0`.
- Canonical `min_effort_to_da_baseline` giữ kết quả của evaluator với zero candidates (`minimum_effort_value=None`); không thay thế bằng disposition semantic. `generate_and_evaluate_attack_paths()` expose effort 0 tại `result_payload["zero_work_disposition"]` / `roundtrip_result["zero_work_disposition"]`.
- Query/basis đã validate vẫn có `parameter_audit`; P/I thiếu basis hợp lệ không biến đường 0 bước thành candidate Pareto fully rated.

---

## 4. Handoff cho #206 (TTS A) và #213 (TTS B)

### 4.1 Handoff cho TTS A (#206 - Independent Oracle)
- Interface query đã tích hợp sẵn sàng với fixtures và scoring package A2 (`synthetic-a2-e.json`, `synthetic-a2-t.json`, `synthetic-a2-diagnostics.json`).
- Kết quả Min-Effort từ `run_attack_query()` đã được kiểm chứng khớp 100% với independent oracle:
  - Ledger E: Best effort = 2 (`cand_mid_path` / Path 3).
  - Ledger T: Best effort = 2 (Tất cả 3 paths tie, deterministic selection chọn `cand_direct_path` / `generated_0001`).
- Khi TTS A bổ sung thêm runtime test fixtures hoặc freeze các SEAMLESS queries trong tương lai, `run_attack_query()` có thể consume trực tiếp mà không cần sửa đổi API signature.

### 4.2 Handoff cho TTS B (#213 - CLI Packaging)
- Module CLI đóng gói có thể gọi trực tiếp `run_attack_query(query_dict, graph_dict)` hoặc `materialize_query()`.
- CLI query payload schema chỉ cần bổ sung tùy chọn 2 fields:
  - `action_bindings`: Mapping từ `(technique_id, actor, source, target)` sang `action_id`.
  - `ranking_query`: Mapping chứa cấu hình ranking (hoặc để trống để engine dùng default catalog).
- Kết quả trả về `AttackQueryResult` cung cấp sẵn mọi trường tóm tắt CLI cần:
  - `result.status`: Status chuỗi rõ nghĩa.
  - `result.checkpoint_reached`, `result.final_goal_reached`.
  - `result.min_effort`: Dict đầy đủ thông số effort tối ưu và tie count.
  - `result.optimization_scope`: Phạm vi bảo đảm toán học cho kết luận.
  - `result.diagnostics`, `result.checkpoint_diagnostics`: Dữ liệu cho verbose diagnostics CLI.
