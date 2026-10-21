# Tích hợp search candidate với PathRankingEngine

- Ngày cập nhật: 2026-10-04.
- Phạm vi: Issue #155, #180; final acceptance harness và handoff sang Issue #48.
- Trạng thái: **Semantic bridge và evidence views đã tích hợp hoàn toàn vào acceptance harness; toàn bộ 8 acceptance cases được kiểm chứng bằng real search và exact ranking conformance**. PR #179 đã merge real-search acceptance harness, PR #181 đã merge semantic bridge/evidence views, và đợt tích hợp này hợp nhất hai luồng vào `scripts/research/week3_engine_acceptance.py`.

## Luồng dữ liệu

```text
pinned raw SEAMLESS
  → parser CLI / canonical Graph JSON (snapshot-pinned)
  → case-specific evidence view / runtime projection (#181)
  → real bounded structural/semantic search: generate_attack_paths() (#145)
  → PathResult + exact transition edge IDs + coverage metadata
  → adapt_search_candidate (versioned boundary)
  → PathRankingQuery candidate envelopes
  → PathRankingEngine.evaluate(...)
  → candidate assessments + diagnostics + Pareto + Min-Effort + audit trace
```

Graph/search sở hữu topology, node/edge IDs, candidate order, transition decisions và completeness. Query packet sở hữu declared scenario, fact classification, assumptions/evidence, action catalog, human/research ratings, target consequence/success event và parameter basis. Adapter chỉ gắn các binding đã khai báo và kiểm tra route; evaluator tính replay, likelihood bằng rational chính xác, work ledger/dedup, consequence eligibility, Pareto và Min-Effort. Integration `search_audit` giữ nguyên fact ledger; canonical `parameter_audit` giữ nguyên schema của evaluator.

Adapter không tạo action khi thiếu mapping từ technique ID, không suy success từ reachability và không tạo probability/rating. Candidate thiếu/mâu thuẫn binding được giữ trong `diagnostics` với mã `adapter_ineligible`; candidate đó không vào frontier. Fact ledger nguyên bản được giữ trong `search_audit`; trace giữ target/success event, scenario reference, runtime fact values và từng decision/failed/unknown predicate. Typed `RuntimeFact` của #146 được flatten thành JSON-safe audit record nhưng vẫn giữ `value`, `origin`, `scope`, `rationale`, `provenance_reference` và assumption metadata. Observed, assumed, known-false và unknown tiếp tục được phân giải bởi evaluator theo authoritative layers. Known-false là veto; assumed facts không ghi đè false; unknown và unrated không đủ điều kiện xếp hạng.

Structural route lưu node order và exact edge IDs chỉ từ transition quan sát được; semantic trace lưu toàn bộ transition theo thứ tự, gồm derived steps có `edge_id: null`. Provenance records/lineage được gắn theo edge ID tương ứng. Nếu đưa `--graph`, CLI xác thực Graph Contract, pin `snapshot_id` với query rồi tra từng exact edge ID trong canonical graph; parallel edges không bị gộp theo endpoints. Query xác thực riêng target impact và success event cụ thể. Không suy consequence từ nhãn Tier0/Domain Admin.

`search_metadata` và `min_effort_to_da_baseline.baseline_coverage` giữ caps/truncation từ search. Helper `coverage_from_search_result(search_result, budget)` chuyển `AttackSearchResult.paths/expansions/truncated/truncation_reason` và `SearchBudget.max_paths/max_steps/max_expansions` sang ranking coverage. Khi #146 cung cấp `truncation_reason`, adapter dùng trực tiếp nguyên nhân đã được search xác định: `path_limit_reached` được map sang tên ranking `candidate_limit_reached`, còn `expansion_limit_reached` và `step_limit_reached` được giữ nguyên. Search budget `max_paths` được chuẩn hóa thành canonical `max_candidates`; cùng normalization áp dụng cho raw/API/CLI coverage. Nếu `max_paths` và `max_candidates` cùng xuất hiện nhưng khác giá trị thì validation fail closed. `max_steps` và `max_expansions` được bảo toàn trong cả `search_metadata.caps_applied` và Min-Effort `baseline_coverage`. Chỉ với shape cũ không có reason, adapter mới suy từ counter candidate/expansion và fail closed nếu không có bằng chứng. Khi nguồn không cung cấp coverage, output dùng `unspecified_subset`; empty result khi đó không chứng minh không có path. Khi search bị truncate, frontier và Min-Effort chỉ mô tả tập ứng viên đã đánh giá, không phải optimum toàn cục.

## Giao diện PathResult

`adapt_search_candidate(...)` cô lập contract khỏi class nội bộ #145; legacy name `convert_path_result_to_candidate_envelope(...)` tiếp tục tương thích. Candidate JSON cho CLI có dạng:

```json
{
  "candidate_id": "candidate-001",
  "target_asset_id": "<canonical target node id>",
  "route_id": "route-001",
  "action_mapping": ["<action_id for transition step 0>"],
  "path_result": {
    "nodes": ["<foothold id>", "<target id>"],
    "transition_history": [
      {
        "edge_id": "sha256:<64 lowercase hex chars>",
        "result": {
          "request": {
            "technique_id": "<technique id>",
            "source": "<edge source id>",
            "target": "<edge target id>"
          },
          "status": "applicable",
          "failed": [],
          "unknown": []
        }
      }
    ],
    "scenario_reference": "<scenario id>"
  }
}
```

`action_mapping` có thể đặt trong từng candidate hoặc truyền bằng file `--action-mapping`. Một mapping object `technique_id → action_id` chỉ hợp lệ khi mỗi technique xuất hiện tối đa một lần trong transition history; nếu technique lặp, dùng ordered JSON array với đúng một `action_id` cho mỗi step. Mọi ID phải tồn tại trong catalog; adapter đối chiếu actor, target và declared edge ID của action với transition context.

Structural transition quan sát được bắt buộc giữ exact `edge_id` để tra provenance; non-canonical transition của #146 được giữ dưới dạng `edge_id: null` và `derived_from_step`, không nhận edge/provenance giả. Do `generate_attack_paths()` là semantic/state program chứ không phải topology walker, source của observed edge kế tiếp không bắt buộc bằng target của observed edge trước. Adapter vì vậy giữ full `transition_lineage` theo step và tách observed evidence thành các structural segment nội bộ liên tục; mỗi segment dùng `action_step_indices` để bind exact edge về step tương ứng. Validator kiểm tra endpoints/edge ID của từng segment với lineage và yêu cầu hợp segment cover đúng một lần toàn bộ observed steps. Quan hệ initial `AttackState` vẫn có thể hợp lệ với `edge_id: null`, `derived_from_step: null`; path hoàn toàn semantic giữ `[foothold]` với `edge_ids: []` và lineage phải kết thúc ở target. Không có canonical edge giả và không suy continuity không tồn tại. Thiếu mapping, target hoặc query scope, action không tồn tại/sai context, derived step thiếu origin hợp lệ, hay canonical candidate validation thất bại sẽ tạo diagnostic riêng cho candidate; candidate hợp lệ khác vẫn được chấm. Query packet phải khai báo success-event trong `target_impact_assessments`; binding kết quả được lấy từ record đó và kiểm tra với `target_goal`. `bundle_id`, `bundle_version`, `bundle_digest` cùng governance giữ nguyên trong query audit khi packet có versioned parameter bundle; evaluator không nâng trạng thái pending thành accepted.

## Chạy lại

Parser tiếp tục là nguồn tạo canonical graph, không đổi parser internals. Với manifest/raw snapshot đang được cấp quyền trong checkout, lệnh parser chuẩn có dạng:

```powershell
python -X utf8 -m src.parser.cli `
  --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 `
  --raw-dir data/raw/SEAMLESS `
  --manifest-dir data/samples/manifests `
  --created-at 2026-10-01T00:00:00Z `
  --output .cache/canonical-graph.json `
  --summary
```

Chuẩn bị ba input do owner tương ứng cấp: `path-ranking-query.json` (canonical query/scenario/action/rating packet), `path-ranking-candidates.json` (JSON array theo shape ở trên, từ bounded search hoặc explicit candidates), và `path-ranking-coverage.json` (metadata search, gồm `is_truncated`, `truncation_reasons`, `completeness_scope`, `caps_applied`). Sau đó:

```powershell
python -X utf8 -m src.engine.ranking.cli `
  --query .cache/path-ranking-query.json `
  --search-candidates .cache/path-ranking-candidates.json `
  --graph .cache/canonical-graph.json `
  --action-mapping .cache/technique-action-map.json `
  --coverage .cache/path-ranking-coverage.json `
  --output .cache/path-ranking-result.json
```

Không cần ghép hoặc sửa tay query JSON: CLI đọc query packet, candidate array, mapping, coverage và graph từ các file riêng. Nếu chạy evaluator độc lập với graph, bỏ `--graph`; edge records khi đó phải có sẵn trong `path_result.edges`. --search-candidates vẫn là explicit-candidate bridge cho replay/debug. Product acceptance không được dùng bridge này thay cho search thật: generate_and_evaluate_attack_paths(...) gọi trực tiếp generate_attack_paths(), bind từng transition bằng identity (technique_id, actor, source, target), truyền coverage thật vào evaluator và ghi candidate_source=generate_attack_paths.

Khi cần orchestration search thật, dùng helper đã merge trong boundary #155:

```python
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths

ranked = generate_and_evaluate_attack_paths(
    query_packet,
    canonical_graph,
    actor=foothold_id,
    initial_state=initial_state,
    runtime_context=runtime_context,
    budget=search_budget,
    action_bindings=exact_transition_action_bindings,
    catalog=selected_catalog,
)
```

Helper chỉ rank path do generator vừa sinh. Path có transition chưa có exact action binding bị loại khỏi ranking và giữ trong search_audit.binding_diagnostics; không tự chọn action theo tên gần giống và không replay candidate supplied để lấp gap.

## Kết quả và giới hạn

`path-ranking-result.json` giữ output canonical v1.0.0: eligible assessments, diagnostics, Pareto frontier conservative, exact rational likelihood, effort/work-unit basis, target consequence, separate Min-Effort-to-DA và coverage. Extension `search_trace`/`search_audit` bổ sung evidence handoff mà không thay evaluator hay tạo total order.

Fixture synthetic xác minh positive, authoritative false, unknown, missing action mapping, unrated likelihood, parallel edge identity, canonical graph/snapshot hydration, coverage propagation, parameter bundle version audit và deterministic serialization. Các oracle dominance, incomparability, exact tie, effort tie-break, dedup/overlap, first-goal trimming và Min-Effort tiếp tục do canonical conformance suite hiện có sở hữu. Kết quả này không xác nhận empirical probabilities, completed human ratings, global optimality hoặc final SEAMLESS ranking.

## Harness nghiệm thu release Week 3 (#155)

scripts/research/week3_engine_acceptance.py là entrypoint release-consuming. Nó thực hiện các boundary sau theo đúng thứ tự:

1. verify reviewed-release.json bằng exporter/replay hiện hành và pin digest #176;
2. dùng đúng hai projection source_a và source_b, không trộn foothold;
3. nhận canonical graph đã tạo sẵn bằng --graph, hoặc tự gọi parser pipeline với --raw-dir;
4. tạo AttackState/RuntimeContext từ search-integration-plan.json và variant được chọn;
5. gọi generate_attack_paths() thật, dùng budget đã pin;
6. bind transition theo exact (technique_id, actor, source, target);
7. chỉ đưa path đã bind được vào canonical ranking evaluator;
8. so action sequence sinh được với supplied reviewed candidates như oracle, không dùng supplied candidates làm search output;
9. ghi release/plan/graph pins, caps/truncation, attempts/status, binding diagnostics, frontier và Min-Effort vào report deterministic.

Chạy trên canonical graph đã export:

~~~powershell
python -X utf8 scripts/research/week3_engine_acceptance.py --case-id w3-source-a-positive --graph data/processed/graphs/seamless-canonical.json --output .cache/week3-positive.json
~~~

Hai flow veto/unknown dùng cùng release và graph, chỉ thay overlay có tên:

~~~powershell
python -X utf8 scripts/research/week3_engine_acceptance.py --case-id w3-source-a-known-false --graph data/processed/graphs/seamless-canonical.json --output .cache/week3-known-false.json

python -X utf8 scripts/research/week3_engine_acceptance.py --case-id w3-source-b-runtime-unknown --graph data/processed/graphs/seamless-canonical.json --output .cache/week3-missing-unknown.json
~~~

Có thể chạy raw -> graph -> search -> ranking trong cùng entrypoint bằng --raw-dir, --manifest-dir, --time-policy và một --created-at cố định. --require-complete trả exit code 4 nếu semantic ownership hoặc reviewed candidate generation chưa đủ để nghiệm thu.

### Trạng thái tích hợp cuối cùng (#155, #180 và chuyển giao #48)

Sau khi PR #181 merge semantic bridge và counterfactual evidence views vào `develop`, acceptance harness `scripts/research/week3_engine_acceptance.py` đã hợp nhất trọn vẹn cả hai luồng:

1. **Semantic bridge & Catalog 0.3**: Toàn bộ 15/15 action semantic owners trong `search-integration-plan.json` đều được map thành `catalog_transition` trực tiếp từ catalog 0.3 đã accepted (gồm `acquire_reset_identity`, `propagate_group_entitlement`, `scenario_reset_password`, `scenario_winrm_admin`). Không còn semantic coverage gap.
2. **Missing-evidence mappings**: Hai ca `w3-source-a-structural-missing` (withhold `users/2310/Aces/3`) và `w3-source-a-telemetry-missing` (withhold `users/2310/Properties/enabled`) được map hoàn chỉnh sang `counterfactual_view()`, áp dụng provenance delta trên case-specific graph/context mà không mutate baseline canonical graph.
3. **Độc lập danh tính ranking với Oracle IDs**: `generate_and_evaluate_attack_paths()` gán candidate ID hoàn toàn độc lập từ search generator (`generated_0001`, `generated_0002`). Không inject oracle IDs vào quá trình ranking; tie-breaking equal-effort và Pareto frontier được bảo toàn nguyên vẹn theo search order. Việc đối chiếu với reviewed oracle IDs chỉ diễn ra hậu đánh giá trong acceptance audit và report.
4. **Nghiệm thu toàn bộ 8 cases**: Toàn bộ 8/8 acceptance cases (Source A: positive, known-false, runtime-unknown, structural-missing, telemetry-missing; Source B: positive, known-false, runtime-unknown) chạy qua real search, pass toàn bộ kỳ vọng về feasible candidates, metrics, Pareto frontier, Min-Effort và designated negative/missing decision evidence.
5. **Handoff boundary**: #155 và #180 đã hoàn thành đầy đủ mục tiêu tích hợp và đóng lại khi merge PR này; Issue #48 tiêu thụ handoff tích hợp hoàn chỉnh này.

---

### Các checkpoint lịch sử đã được thay thế (Superseded Historical Checkpoints)

Các mục dưới đây ghi lại các phát hiện và trạng thái trung gian trong quá trình phát triển, hiện đã được thay thế bởi trạng thái tích hợp cuối cùng ở trên:

#### Checkpoint PR #179 (Superseded)
*Trạng thái lịch sử*: Tại thời điểm PR #179 vừa merge, harness chạy real-search nhưng chưa có semantic bridge và evidence views từ #181. Khi đó:
- Positive harness tạm thời trả `blocked_semantic_coverage` do các bước actor-switch/capability sau reset và WinRM chưa có production catalog owners trong Week 3 baseline (được phân loại là gap #174).
- Hai ca `w3-source-a-structural-missing` và `w3-source-a-telemetry-missing` tạm thời trả `blocked_acceptance_case_mapping` do chưa có counterfactual view contract.
*Hiện trạng*: Toàn bộ các blocker này đã được giải quyết triệt để sau khi PR #181 merge và được harness consume trực tiếp.

#### Checkpoint Cross-Review 5401172214 & 5401381383 (Hardening đã áp dụng)
- Đồng bộ manifest #178 tại develop `6d06dc7bb9352db568eb7dc6deb92285a8d32489`. Pin blob manifest `fa60208cfd4d9621f2ee22edc3489eb960a6a686`, kiểm tra byte/blob và canonical digest.
- Search terminal yêu cầu đồng thời target asset và state `admin_control(target)` (tương ứng `admin_control_badblood`), ngăn chặn việc terminate sớm ở intermediate DC reachability.
- Chuẩn hóa scope: `context_for()` đặt `RuntimeFact.scope` của `blocked_evidence` và `unknown` bằng `query_metadata.scenario_id`, đúng scope của search binding trong manifest #178. Scope của `declared_assumption` là `query_metadata.horizon`. Evaluator giữ fact và orchestration serialize scope này.
- Kiểm tra designated negative decision: không chỉ kiểm tra absence đơn thuần mà xác minh exact technique, actor, source, target, predicate, status `blocked`/`indeterminate`, origin, value, scope và rationale.
