# Public query API Week 4

Refs #211, PR #221; yêu cầu bàn giao ở [query contract](week4-query-contract.md).
`materialize_query(query, graph)` chuẩn hóa input; `run_attack_query(query, graph)`
chuẩn hóa rồi gọi `generate_attack_paths()` hiện hành. Không truyền ordered path.
Input nhận mapping hoặc `AttackQuery`; graph nhận canonical mapping hoặc `EngineGraph`.

```python
from src.engine import AttackQuery, run_attack_query

query = AttackQuery(
    initial_actor="Alice",
    initial_state={"control": ["Alice"]},
    target="Host",
    target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
    aliases=aliases,  # alias -> canonical ID trong graph
    runtime_facts=runtime_facts,
    allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
    budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
)
result = run_attack_query(query, graph, evaluation_mode="evidence_only")
```

`source_foothold` khai báo control của node nguồn; không tự cấp domain identity.
`usable_identity` phải khai báo riêng dạng `(principal, authentication_context)`.
Aliases và references được resolve tại boundary; canonical graph không bị sửa.

## Facts, assumptions và view

`runtime_facts`/`assumptions` nhận mapping hoặc `RuntimeFact`.
Mỗi declared assumption phải có `scope`, `rationale`, và nguồn truy vết:
`provenance_reference` (`evidence_ref` là alias khi input là mapping), hoặc
`assumption_metadata.declared_by`/`assumption_metadata.source` là string không rỗng.
Rule áp dụng cả assumption được truyền trong `runtime_facts`.
Ledger rejected giữ rationale, provenance và assumption metadata; True bị known-false
veto không được đưa vào runtime context như fact True.

`RuntimeFact.scope` giữ nghĩa context/horizon hiện có, **không là view ID**.
Ví dụ projection hiện hành dùng horizon cho assumption và scenario ID cho
blocked/unknown evidence. Các record này vẫn cùng query, nên false phải veto True.
Caller phải dựng query cho một snapshot/context/horizon phù hợp.

Khi gom nhiều counterfactual views trong một input, gắn nhãn tường minh trên từng
record bằng `assumption_metadata.view_id`; `active_scope` chọn nhãn này:

```python
baseline_false = {
    "predicate": "admin_channel",
    "subject": "Alice",
    "target": "Host",
    "value": False,
    "origin": "blocked_evidence",
    "scope": "scenario-baseline",
    "provenance_reference": "fixture:baseline",
    "assumption_metadata": {"view_id": "baseline"},
}
counterfactual_true = {
    "predicate": "admin_channel",
    "subject": "Alice",
    "target": "Host",
    "value": True,
    "origin": "declared_assumption",
    "scope": "current_snapshot",
    "rationale": "Synthetic counterfactual channel availability",
    "provenance_reference": "fixture:counterfactual",
    "assumption_metadata": {"view_id": "counterfactual"},
}
```

Nhiều explicit views mà thiếu selector bị reject, kể cả input chỉ có authoritative
facts. Selector rỗng/không khớp view cũng bị reject. Record chưa gắn `view_id`
thuộc query hiện tại và luôn được giữ lại, nên selector không làm mất known-false.
Muốn điều kiện khác ở một counterfactual, caller phải gắn view rõ cho evidence đó;
không đổi raw scope để né veto hoặc sửa canonical/raw data.

## Mode, technique scope và goals

Mode chỉ nhận `scenario` hoặc `evidence_only`. Tham số hàm được truyền tường minh
ưu tiên hơn field query, giống nhau cho mapping và dataclass. Nếu không truyền,
dùng field query; default là `scenario`. Evidence-only không chấp nhận assumption
làm bằng chứng applicability. Đã materialize thì không đổi mode/view khi chạy;
cần dựng lại từ declarative query.

`allowed_techniques=None` dùng toàn bộ catalog được cung cấp/default.
Danh sách rỗng nghĩa là không cho phép technique nào. Catalog custom cũng luôn
được intersect với allow-list; unknown IDs bị reject trước search.

Final target phải có `target_goal` hoặc callable `success_state_predicate`.
Goal mapping phải có canonical-resolvable `target`, `required_state` không rỗng
và reference target đó. `checkpoint_goal` dùng cùng validation, độc lập với final
target. Nếu goal mapping và callable cùng được cung cấp, cả hai phải đúng (AND),
cho cả final goal lẫn checkpoint; callable không bỏ qua declared required state.

Result giữ `paths`, `attempts`, `checkpoint_reached`, `final_goal_reached`, `status`,
`complete`/`truncated` và ledger qua `materialized_query`.
Checkpoint đạt không tự là asset compromise. Search incomplete mà chưa đạt goal
trả `truncated`; unknown route giữ indeterminate dù route khác bị blocked.
Success chỉ chứng minh goal trong scenario được khai báo.

## Top-K theo công sức C (Refs #226)

Thêm `top_k: K` vào `AttackQuery`/mapping; K là số nguyên dương, độc lập search caps.
`MaterializedQuery.run()` và `run_attack_query()` trả `AttackQueryResult.top_k_result`.
Selector dùng whole-path C và canonical program identity, giữ programs thiếu P/I nếu
C đủ. K=1 dùng cùng tie policy với Min-Effort. Missing C/binding, unknown và truncation
hạ guarantee; không suy K-best từ việc đã có đủ K incumbents.
Xem [contract, worked example và lệnh tái lập](week4-top-k-search.md).

## Min-Effort search và Ranking kết quả (Refs #212)

Xem tài liệu chi tiết tại [week4-min-effort-search.md](week4-min-effort-search.md).

Query nhận thêm:
- `action_bindings`: Mapping từ `(technique_id, actor, source, target)` sang `action_id` (được resolve alias).
- `ranking_query`: Cấu hình đánh giá Min-Effort / scoring package.

Khi được cung cấp, `run_attack_query()` tự động ánh xạ các đường tấn công tìm được sang canonical candidate envelopes, đánh giá Min-Effort qua `evaluate_search_candidates()` (#207/ADR-0013), và bổ sung vào `AttackQueryResult`:
- `min_effort`: Dict chuẩn theo canonical baseline (#207/Spec 3.4):
  - `goal_id`: ID mục tiêu đánh giá.
  - `best_candidate_id`: ID ứng viên tối ưu (hoặc `None`).
  - `minimum_effort_value`: Giá trị effort tối thiểu (float/int hoặc `None`).
  - `associated_likelihood_interval`, `associated_impact`: Thông số likelihood/impact tương ứng.
  - `coverage_disclosure`, `baseline_coverage`: Thông tin kiểm toán completeness và caps.
  - `all_best_candidate_ids`: Danh sách tất cả candidate IDs đạt cùng mức minimum effort.
  - `tie_count`: Số lượng ứng viên tie ở mức minimum effort.
- `best_path`: `PathResult` có chi phí effort tối ưu (`path.cost` phản ánh `minimum_effort_value`).
- `all_best_paths`: Toàn bộ paths đạt cùng mức min effort (đồng nhất cost).
- `optimization_scope`: Trạng thái phạm vi tối ưu hóa:
  - `"exhaustive_within_scope"`: Finite scope hoàn chỉnh, untruncated, không có binding/adapter gap, 100% feasible candidates được rated effort.
  - `"best_in_bound_subset"`: Tồn tại candidate bị loại khỏi ranking do thiếu action binding hoặc bị adapter/validator reject; tối ưu chỉ đảm bảo trên tập con bound/validated.
  - `"best_in_rated_subset"`: 100% candidates được bind/validate, nhưng tồn tại feasible candidate chưa có effort rated.
  - `"best_in_generated_subset"`: Search bị cắt tỉa do budget (`max_paths`, `max_steps`, `max_expansions`) nhưng đã tìm thấy ít nhất một candidate khả dĩ.
  - `"truncated_incomplete"`: Search bị cắt tỉa do budget và chưa tìm thấy đường đi nào.
  - `"no_bound_candidates"`: Search tìm thấy paths nhưng toàn bộ bị loại do thiếu action binding hoặc adapter rejection.
  - `"no_rated_candidates"`: Có candidate bound/validated nhưng không có candidate nào rated effort.
- `is_minimum_proven_over_scope`: `True` khi và chỉ khi `complete=True`, `truncated=False`, không có `binding_diagnostics`, `optimization_scope == "exhaustive_within_scope"`, và `minimum_effort_value` được xác định.
- `is_no_path_proven_over_scope`: `True` khi scope hoàn chỉnh, untruncated, không có indeterminate gate, và không có đường đi tới đích.
- `binding_diagnostics`: Dict ghi nhận các candidate bị loại khỏi ranking do thiếu binding (`explicit_action_binding_missing`) hoặc bị adapter/validator reject (`adapter_ineligible`, `canonical_candidate_invalid`), kèm lý do và diagnostic chi tiết.
- `checkpoint_diagnostics`: Diagnostics giải thích lý do không tiến tới final goal sau khi đạt checkpoint.
- **Zero-action / Initial Goal Satisfaction**: Khi mục tiêu đã thỏa mãn ngay tại `initial_state` (kể cả foothold khác target asset), hệ thống trả về 1 đường đi 0 bước, `status="success"`, `min_effort` ghi nhận `minimum_effort_value=0.0`, `best_path.cost=0.0`, `optimization_scope="exhaustive_within_scope"`, và `is_minimum_proven_over_scope=True` mà không bị hidden adapter rejection.

### Zero-action: validation và disposition riêng (review #232)

- Khi có `ranking_query`, cả hai API đi qua query decoder, graph contract và kiểm tra snapshot; actor/target phải khớp metadata và thuộc canonical graph. Payload sai bị reject, kể cả đường 0 bước.
- `run_attack_query().min_effort` cho trường hợp này là disposition riêng có `disposition="semantic_initial_goal_zero_work"`, `ranking_status="not_applicable"`; nó cũng xuất hiện tại `ranking_result["zero_work_disposition"]`. Đây là bảo đảm **0 công việc mới theo declared semantic goal / initial AttackState**, không phải assessment của ranking success event.
- `associated_likelihood_interval=None`, `associated_impact=None`; không tự gán `[1,1]` hay consequence rating. `eligible_candidates={}`, `pareto_frontier=[]`, `assessed_candidates=[]`, `search_metadata.candidates_evaluated=0`.
- Canonical `min_effort_to_da_baseline` giữ kết quả của evaluator với zero candidates (`minimum_effort_value=None`); không thay thế bằng disposition semantic. `generate_and_evaluate_attack_paths()` expose effort 0 tại `result_payload["zero_work_disposition"]` / `roundtrip_result["zero_work_disposition"]`.
- Query/basis đã validate vẫn có `parameter_audit`; P/I thiếu basis hợp lệ không biến đường 0 bước thành candidate Pareto fully rated.
# Tích hợp rating tự động #250

Public type hiện tại là `MaterializedQuery`. Dùng `rating_resolution` trong
`AttackQuery` hoặc JSON query để yêu cầu chế độ automatic. Không có cấu hình này
thì giữ luồng semantic-only hoặc explicit packet cũ. Không truyền đồng thời
`ranking_query`/`action_bindings` và `rating_resolution`: engine báo lỗi, không
chọn basis thay caller.

Ví dụ chạy từ repository root với Python 3.14:

```python
import json
from pathlib import Path
from src.engine import materialize_query, run_attack_query
from src.engine.graph import EngineGraph


def read(name):
    return json.loads(Path(name).read_text(encoding="utf-8"))


query = read("tests/fixtures/rating_resolution/query.json")
query["rating_resolution"] = read("tests/fixtures/rating_resolution/complete.json")
graph = EngineGraph.from_canonical(read("tests/fixtures/attack_scenarios/graphs/two-routes.json"))
result = run_attack_query(query, graph)
assert result.min_effort["minimum_effort_value"] == 1
assert result.rating_coverage["numeric_requests"]["P"] == {"required": 2, "rated": 2}
assert materialize_query(query, graph).run(graph).rating_coverage == result.rating_coverage
```

Số trong ví dụ là `synthetic_test_only`, phục vụ kiểm thuật toán. Không dùng
fixture này làm production acceptance hoặc evidence thực nghiệm.

`public-rating-resolution/1.1.0` nhận `mode: automatic`, `policy: production`
(mặc định) hoặc `synthetic_test_only`, `scope`, `registries`. Scope bắt buộc có
query/scenario/version, snapshot digest, foothold, boundary, horizon,
`active_work_budget`, evaluation mode và target goal gồm asset/event/goal ID.
`active_work_budget` phải bằng `budget.max_steps`; recovery budget/horizon/method
thực tế nằm trong semantic fact metadata và optional `scope.recovery_metadata`,
không được coi search cap là số lần thử password. Snapshot, actor, asset,
scenario và evaluation mode phải khớp query. Engine sinh `required_predicates`
cho goal từ semantic success predicate; caller không cung cấp facts ledger.

Registries là object theo role `effort`, `likelihood`, `impact`, `impact_source`,
`empirical`, `work`. Mỗi envelope có đúng `version: 1.0.0`, `data`, `sha256`.
Digest là SHA-256 của JSON UTF-8, `sort_keys=True`, `ensure_ascii=False`,
`separators=(",", ":")`, không NaN. Hàm `canonical_digest` trong
`src.engine.ranking.resolution_service` tính digest này. Digest pin nội dung;
approval vẫn phải được reviewer xác nhận từ review references.

- `effort.data`: list native `WorkUnitClass` records. Optional
  `applicability.source_ids` giới hạn exact structural sources, không fuzzy matching.
  Named `semantic_predicate` chỉ nhận tên predicate đã đăng ký cho đúng class trong
  native inventory; không nạp code tùy ý. Status pending giữ unrated.
- `likelihood.data`: list native reviewed full-history records của #248.
  Ordered prefixes là registry basis có scope, không phải candidate/path packet.
  Cùng prefix được reuse cho các generated paths khác nhau, kể cả passive variants.
  Không có class-level marginal q tự nhân sang mọi lịch sử.
- `impact.data` và `impact_source.data`: registry equivalence #249 và source packet
  đã pin digest. Mapping pending/refused không bị bypass bằng fallback.
- `empirical.data`: manifest, dataset classification và optional native
  `TrialObservation` records. Provider #238/#248 giữ nguyên production gate;
  prototype không được xuất làm q production, kể cả khi có scenario fallback.
- `work.data`: optional reusable preparation rules theo techniques/method và
  exact scenario/boundary, có `preparation_technique`, `review_status: accepted`,
  `review_reference`, `basis_category`. Chỉ dùng khi semantic work decomposition
  đã review; không tự thêm preparation cho mỗi technique. Engine tự sinh prep ID
  từ actor/target/auth/resource/policy/scope/method, deduplicate khi reuse.

API, CLI và `generate_and_evaluate_attack_paths({}, ..., rating_resolution=config)`
cùng dùng `resolve_generated_rating_inputs`; orchestration automatic delegate
`MaterializedQuery.run`. Orchestration cần typed initial state/runtime context,
budget/catalog và semantic success predicate như search hiện hành.

Coverage có `public_coverage_version: public-rating-coverage/1.1.0`, giữ native
resolver `coverage_version: 1.0.0`. Đọc riêng semantic search, binding và numeric
requests; không suy completeness của search từ việc C/P/I đủ. Xem
[schema](public-rating-coverage.schema.json) và
[quyết định #250](issue-250-public-rating-integration-decisions.md).

Coverage public chỉ hoàn tất sau adapter và canonical validator/evaluator.
`binding.canonical_admitted_candidates` lấy từ `search_audit.candidates_adapted`,
bao gồm cả candidate thiếu numeric basis đã được đánh giá.
`binding.canonical_rejections` giữ đúng diagnostic của adapter/validator;
provider refusal không bị đổi thành lỗi binding. Initial goal/empty search có
zero admitted envelopes, không dựng canonical candidate hoặc q/I giả.

### Binding goal/consequence sau review #258

Engine chuẩn hóa `target_goal.required_state` thành `SemanticGoalDescriptor`
(`semantic-goal/1.0.0`), dùng canonical IDs, state sets đã sắp xếp và SHA-256
canonical JSON. Coverage xuất `semantic_goal.descriptor` cùng `sha256` để kiểm
tra. Asset/event/goal labels không tự chứng minh consequence: mapping I đã review
phải có `applicability.semantic_goal` bằng descriptor này, `goal_id`, `snapshot_id`
đúng scope và review reference. Registry digest vẫn phải pin toàn bộ mapping.
Đây là reusable mapping theo capabilities/snapshot/consequence, không theo path.

Lấy descriptor cho quá trình chuẩn bị/cross-review registry:

```python
materialized = materialize_query(query, graph)
descriptor = materialized.semantic_goal.to_dict()
assert (
    query["rating_resolution"]["registries"]["impact"]["data"]["mappings"][0]["applicability"][
        "semantic_goal"
    ]
    == descriptor
)
```

Không gắn descriptor mới vào mapping admin để cấp cùng consequence cho session
yếu hơn. Mapping khác cần review đúng consequence; ghi `accepted` không thay
thế review. Config 1.0.0 vẫn đọc được; mapping automatic thiếu binding mới có I
refused với `semantic_goal_binding_missing`, C/P và effort-only vẫn được đánh giá.
Explicit ranking packets giữ boundary/precedence cũ. Nếu khai báo
`required_predicates`, phải khớp predicate digest của descriptor; không dùng
asset-only predicate cũ để override semantic goal.

Orchestration phải truyền descriptor đã materialize để giữ cùng typed goal:

```python
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths

orchestrated = generate_and_evaluate_attack_paths(
    {},
    graph.to_canonical(),
    actor=materialized.initial_actor,
    initial_state=materialized.initial_attack_state,
    runtime_context=materialized.runtime_context,
    budget=materialized.budget,
    catalog=materialized.catalog,
    scenario_reference=materialized.scenario_reference,
    semantic_goal=materialized.semantic_goal,
    rating_resolution=query["rating_resolution"],
)
assert orchestrated["roundtrip_result"]["pareto_frontier"]
```

Callable bổ sung được AND với typed requirements, không thể làm yếu descriptor.
Callable thuần vẫn search và đánh giá C/P/effort; automatic I chưa thể xác minh
capabilities nên refused `semantic_goal_unverifiable`. Không veto mọi callable
hoặc mọi query không có scenario.

`scenario_authority` phân biệt semantic reference với rating reference. Thiếu
semantic reference không là wildcard cho C classes/P records/I mappings có
scenario scope: selected numeric result bị refused `scenario_authority_missing`.
Reviewed basis thực sự unscoped vẫn dùng được nếu đáp ứng các điều kiện khác.
Preparation rule scoped không được áp dụng khi thiếu authority; action C liên
quan cũng không được dùng để chứng minh minimum bỏ sót preparation. Conflicting
scenario là lỗi input riêng. Native provider refusal/integrity/governance luôn
được giữ trước các guard bổ sung; không fallback để che refusal.
