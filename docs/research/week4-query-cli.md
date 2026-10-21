# CLI query Week 4 và package tái lập — #213

## Current-state amendment - 09/10/2026

Core CLI #233/#213 đã merge; câu PR draft trong snapshot bàn giao bên dưới là lịch sử.
Transport vẫn schema `week4-query-result/0.2.0`; các strings pending trong envelope là metadata hiện hành của CLI, không là live issue status.
[SEAMLESS scenario đã freeze và chạy](week4-seamless-scenario.md) bằng public entry point này, có actual generation, controls, identical-input comparison và local semantic replay.
Human-independent reproduction/full final acceptance trong #208 còn pending; không sửa envelope/schema B ở PR tài liệu.
Actions billing chặn trước runner, không claim CI PASS.

Branch đã merge `origin/develop@4330f35` theo CONTRIBUTING, không rewrite lịch sử.
#211/#221, #215/#222, synthetic oracle/mapping #206/#214/#225 và scoring #207/#220
đã merge. Dependency correctness #212 đã giải quyết qua
[PR #232](https://github.com/nairyuuu/ad-weighted-graph/pull/232), merged tại `1c1d0d6`;
develop cũng đã có #230. CLI consume shared zero-work disposition và exclusion/proof fixes.
PR #213 vẫn **draft**, chờ human review, independent reproduction #208 và actual
private/SEAMLESS reproduction. Synthetic PASS không là full Week 4 acceptance.
Schema `week4-query-result/0.2.0` thay acceptance contract 0.1: bỏ gate
`experimental_pending_212`/`dependency`, thêm `experimental_pending_213_208`,
`resolved_dependencies` và `pending_acceptance`. Compare harness chỉ nhận version hiện hành.

## Prerequisites và chạy từ clean checkout

Python **3.14.x**, Git; cài `python -m pip install -r requirements-dev.txt` trong
venv theo README. Không cần Neo4j/BloodHound cho synthetic. Các lệnh dưới dùng
`python` của venv, chạy từ repo root.

Test environment hiện hành dùng `python -m pip install -r requirements-tests.txt`,
bao gồm dependency schema validation; `requirements-dev.txt` giữ bytes đã pin
trong bằng chứng Week 3.

```text
python -m src.engine.query_cli --query tests/fixtures/query_cli/two-routes-query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --ranking-query docs/research/ratings/week4/synthetic-a2-e.json --label synthetic --output reports/generated/query-run1.json
python -m src.engine.query_cli --query tests/fixtures/query_cli/two-routes-query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --ranking-query docs/research/ratings/week4/synthetic-a2-e.json --label synthetic --output reports/generated/query-run2.json
python -m scripts.research.compare_query_runs reports/generated/query-run1.json reports/generated/query-run2.json
python -m pytest tests/test_query_cli.py -q
```

Ví dụ được lấy từ declarative input của accepted `week4-v1.json`; fixture CLI
không chứa ordered path/expected. Generator tự sinh D, M/D, M/I; oracle independent
kiểm exact transition sets; Ledger E kiểm effort D=5, M/I=2. Số 2 là **synthetic
work-unit effort**, không là score SEAMLESS. Runtime/timestamp vẫn có trong từng
run. Harness so semantic, revision, source/config/input digests; cho phép input
reference khác thư mục checkout nhưng bytes phải giống. Exit 0 equal, 1 khác,
2 lỗi package/digest. Không tự regenerate expected bằng actual.

CLI không có `--output` thì stdout chỉ có JSON UTF-8 parse được trực tiếp, cả khi
redirect trên Windows. Lỗi ra stderr: exit 1 invalid query/graph/ranking/run,
exit 2 thiếu prerequisite hoặc usage sai. File input/output UTF-8.

`--compact-output` chỉ bỏ whitespace của JSON, giữ toàn bộ attempts, diagnostics,
ratings, provenance và proof flags. Parse thành cùng package và semantic digest;
không phải summary hoặc sampled audit. Mặc định vẫn JSON indent 2 như trước.

## Input contract và options

`--query` nhận **public AttackQuery mapping** theo
[query API](week4-query-api.md). Chọn đúng một `--graph` (structural canonical JSON)
hoặc `--snapshot` (supported `snapshot-facts/1` envelope). CLI gọi
`materialize_query` → `run_attack_query` → stateful generator → canonical evaluator.
Không có search/ranking framework thứ hai hoặc supplied candidate replay.
Inline graph, custom typed catalog và supplied candidates không được nhận qua CLI.

Query có `initial_actor`, `source_foothold`, `initial_state`, `authentication_context`,
`target`, `target_goal.required_state`, `checkpoint_goal`, `runtime_facts`,
`assumptions`, `aliases`, `scenario_reference`, `evaluation_mode`, `active_scope`,
`allowed_techniques`, `budget` và tùy chọn `ranking_query`, `action_bindings`.
Giữ public normalization/validation hiện hành. Callable goal không biểu diễn được
qua JSON; dùng declarative required state. Default budgets của public API hiện là
1000 paths / 12 steps / 100000 expansions; package giữ **effective caps**.
State/budget phải là JSON object; malformed arrays không được silently dùng default.
CLI từ chối `initial_state={}`, `initial_capabilities={}` và file `--initial-state`
chứa `{}` (exit 1, stderr, không xuất result). Public materializer hiện coi mapping
rỗng là không khai báo và cấp control mặc định; CLI chặn trước khi gọi engine.
Muốn không có capability, dùng `{"control":[]}`; các capability còn lại cũng rỗng.
Nếu bỏ cả hai fields state, public API mặc định control source foothold nếu có,
hoặc initial actor. Trong two-routes, `{"control":[]}` không tới asset, còn
`{"control":["Alice"]}` hoặc bỏ state sinh ba đường. Đây là limitation transport
của API hiện hành, không phải thay đổi correctness engine #212.
Ranking payload rỗng vẫn được truyền tường minh vào public materializer/validator,
không bị truthiness fallback coi là caller không yêu cầu scoring.
File `--ranking-query` hỗ trợ package wrapper có key `query` hoặc PathRankingQuery
không bọc. Nếu có key `query`, nested value bắt buộc là JSON object: null, array,
string, number và boolean bị từ chối rõ ràng; `{}` đi qua authoritative validation
và cũng bị từ chối. Exit 1, stderr diagnostic, stdout rỗng, không tạo output artifact.
Bỏ ranking input vẫn chạy semantic query không scoring.

| Muốn đổi | Input/options |
| --- | --- |
| Source, actor | `--source OtherHost --actor Alice` hoặc fields query |
| Capability ban đầu | `--initial-state state.json` (JSON object) |
| Auth context | `--context Host` hoặc `authentication_context` |
| Target và goal | `--target OtherHost --target-goal goal.json`; goal phải reference target mới |
| Runtime, assumptions | `--runtime-facts facts.json --assumptions assumptions.json` (arrays) |
| Techniques/view/mode/checkpoint | Fields query `allowed_techniques`, `active_scope`, `evaluation_mode`, `checkpoint_goal` |
| Caps | `--max-paths 10 --max-steps 6 --max-expansions 1000` |
| Scoring | `--ranking-query package.json` (package có `query`, hoặc PathRankingQuery) |

Ví dụ `state.json` cho foothold khác và danh tính usable riêng:

```json
{"control":["OtherHost"],"usable_identity":[["Alice","Host"]]}
```

```text
python -m src.engine.query_cli --query tests/fixtures/query_cli/two-routes-query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --label synthetic --source OtherHost --initial-state state.json --context Host
```

Thay `--context OtherHost` sẽ blocked trong accepted two-routes case. Không suy
control(Computer) thành usable domain identity. Khi đổi actor/target/context/scenario,
caller phải cung cấp ranking basis/bindings đúng scope; không tái dùng Ledger E cho
private/context khác. CLI kiểm authoritative ranking-query/graph snapshot validation
trước search kể cả zero-action/no-path/unbound, và kiểm actor/target binding. Semantic
goal và ranking success event vẫn cần reviewer xác nhận mapping đúng; không tự suy
hai mô tả là tương đương.

`action_bindings` dùng JSON sequence public API đã hỗ trợ:

```json
[[["obtain_admin_execution_on_host","Alice","Alice","Host"],"action_direct_admin"]]
```

Đây là transition identity → accepted action/work-unit binding, **không là ordered
attack program**. Không truyền binding thì public engine có thể reuse unique
edge/technique matching từ bound-actions catalog; ambiguity/missing giữ diagnostics.

## Output contract và cách đọc

[JSON Schema envelope](week4-query-result.schema.json) mô tả version thử nghiệm.
Các trường engine bên trong được chuyển nguyên tên/value từ API hiện hành;
`minimum_effort_value`, không invent `best_program_effort`.

| Phần | Nội dung / ý nghĩa |
| --- | --- |
| `schema_version`, `acceptance` | 0.2; resolved dependency #232 và pending #213/#208/private riêng; synthetic không là full acceptance |
| `reproducibility` | HEAD revision, tracked changes, file references + SHA-256 bytes, effective query digest, source/config digests, semantic digest |
| `runtime` | Python/platform, UTC timestamp, duration; không đưa vào so semantic |
| `semantic.query`, `materialized` | Effective input; canonical actor/state/context/target/catalog/caps, bindings và rejected-assumption ledger |
| `semantic.snapshot_metadata`, `snapshot_facts` | Metadata và sidecar đã loader resolve; graph-only thì `snapshot_facts=null` |
| `semantic.candidates` | IDs `generated_0001…`, nodes/edges/provenance, ordered `transition_history`, final state/context |
| `semantic.attempts`, `diagnostics` | Các attempts applicable/blocked/indeterminate engine có cung cấp; request, before/additions/after, failed/unknown/satisfied, prerequisite decisions |
| Trace `assumption_backed_facts`, `evidence_backed_facts` | Facts thực sự hỗ trợ satisfied gates; không phải numeric rating basis |
| `checkpoint_reached`, `final_goal_reached`, `status` | DA/effective entitlement checkpoint độc lập final asset success; có thể chỉ đạt một trong hai |
| `binding_diagnostics`, `ranking_result.diagnostics` | Missing binding, adapter/validator exclusion và assessment/missing-basis reasons theo canonical evaluator |
| `ranking_result`, `min_effort` | Work-unit effort, likelihood/impact status, Pareto/order khi có accepted basis; giữ cả scoring query/ledger provenance |
| `ranking_disposition` | `unrated` nếu chưa có ranking result; `evaluated` chỉ nghĩa evaluator đã chạy, không bảo đảm fully rated |
| `caps`, `complete`, `truncated`, `truncation_reason` | Coverage của generator, không tự coi là completeness của assessed/rated set |
| `engine_reported_guarantees` | Scope/proof flags từ engine đã sửa #212, giới hạn declared scope và assessed coverage; không là global optimum/Top-K |

Object keys sort ổn định; unordered state sets sort theo canonical JSON; tuple/list
giữ thứ tự engine, đặc biệt ordered actions và ranking order. Candidate IDs bám
enumeration public engine. `cost=null` của generated semantic path không tự được
điền bằng hop count; effort đọc từ canonical assessment/`min_effort`.

Zero-action goal đã đạt trong initial state (kể cả target khác actor) có
`ranking_result.zero_work_disposition` và `min_effort` tương ứng: semantic zero work,
`ranking_status=not_applicable`, effort 0, likelihood/impact null. Không tạo assessed
candidate, ordinary Pareto hay rating basis. Invalid ranking metadata/snapshot bị
từ chối cả zero-action và no-path qua authoritative preflight. Generator complete
không đồng nghĩa mọi candidate đã được đánh giá: adapter/validator exclusions giữ
diagnostics/audit counts và hạ scope/proof, đặc biệt khi loại đường effort thấp nhất.

Blocked/indeterminate không thành success nhờ score. Assumption true chỉ giúp
scenario gate, không sinh C/P/I. Missing basis giữ `unrated`, null quantities,
reason/diagnostics; không tự đặt C/P/I hoặc likelihood `[1,1]`. Truncated search
không chứng minh exhaustive no-path, global optimum hoặc Top-K. `max_paths=K` chỉ
là cap, không là K-best. Completeness within scope cũng không là global guarantee.

## Snapshot trust boundary và private/SEAMLESS

`--snapshot` reuse `EngineGraph.from_snapshot`/`deserialize_snapshot`: validate graph,
snapshot ID/full graph binding, canonical subjects và re-resolve evidence. Graph-only
JSON không carry SPN/pre-auth facts. Full **envelope byte digest** được lưu riêng;
graph hash không là chữ ký xác thực toàn fact payload. Sidecar giữ collector/source,
locator/time/snapshot provenance; CLI không verify raw-to-envelope lineage thay loader
hoặc manifest probe. RuntimeContext và AttackState không nhận static directory facts.

```text
python -m src.engine.query_cli --query <private-query.json> --snapshot <verified-snapshot.json> --label seamless --prerequisite <private-manifest.json> --prerequisite <private-users.json> --output <local-result.json>
```

Private/seamless bắt buộc caller khai báo file prerequisite. Thiếu file → exit 2;
graph gắn `synthetic=true` không được label private/seamless. Hash prerequisite chỉ
record bytes, không chứng minh đã verify manifest hay query observed runtime. Người
chạy phải kiểm raw manifest/source/time policy qua tooling hiện có và giữ evidence
local. `--label` là declaration của caller, không là certification. Result private
có thể chứa identities, SPN, full provenance; không commit/publish private output.

**Chưa chạy actual private/SEAMLESS Week 4 query trong #213**: chưa có accepted private
query/bindings/input handoff #206 cho CLI này. Synthetic PASS và việc có `raw.zip`
trong workspace không thay prerequisite/acceptance. Không claim CE parity hoặc
observed attack execution; technique tasks #216/#228/#229 độc lập core package.

## Handoff và acceptance còn chờ

#208: checkout exact PR head, chạy hai commands + compare harness và integration
suite; consume independent expected từ #206/#225 và Ledger E #207/#220, giữ semantic
digest/inputs/revision cùng runtime của cả hai run. Không viết report #208 ở đây.

#224: đọc envelope/version, gate `acceptance.status`, đọc ordered candidate trace,
rejected assumptions, checkpoint/final asset riêng, diagnostics/unrated và caps.
Không dùng generated path count làm ranking completeness. Schema 0.2 thay acceptance
contract 0.1; các fields authoritative của engine không được rename trong viewer.

Dependency #232/#212 đã merge và được consume bằng CLI regressions cụ thể: zero-work
khác actor/target, invalid zero-action/no-path metadata/snapshot, missing P/I không
Pareto, adapter/validator exclusions hạ proof và caps không claim optimum/Top-K.
Còn chờ @Lolavine777 review exact head và acceptance #213, cross-reproduction #208,
actual private/SEAMLESS inputs/bindings/lineage verification và run. PR giữ draft,
không đóng #213. Các tests synthetic không thay những acceptance còn chờ này.

Limitations API: attempts chưa có branch IDs/unique attempt IDs; package không tạo
branch trace/evidence giả. Checkpoint hiện là aggregate query disposition, không có
standalone checkpoint witness path ID authoritative. Goal callable không export được
qua JSON. Numeric rating/accepted private basis thiếu thì explicit unrated/pending.
README chỉ thêm entry point này; #210, techniques, viewer, Top-K, choke point,
BloodHound comparator giữ scope riêng.
# CLI Top-K theo C #226

`--top-k K` mở rộng public query hiện có, không thay `--max-paths`. Output dùng
transport 0.4 và `semantic.top_k`: selected candidate references, C/work ledger,
identity/tie policy, coverage/exclusions và scoped guarantee. Explicit packet,
automatic rating và semantic-only đều hỗ trợ; thiếu C giữ diagnostics/subset claim.
Các mode không yêu cầu Top-K giữ transport version hiện hành.
Xem [Top-K contract và lệnh tái lập](week4-top-k-search.md).

# CLI rating tự động #250

Từ repository root, Python 3.14, tạo thư mục output trước khi chạy:

```powershell
New-Item -ItemType Directory -Force reports/generated/issue250 | Out-Null
python -m src.engine.query_cli --query tests/fixtures/rating_resolution/query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --rating-resolution tests/fixtures/rating_resolution/complete.json --label synthetic --output reports/generated/issue250/complete.json
python -m src.engine.query_cli --query tests/fixtures/rating_resolution/query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --rating-resolution tests/fixtures/rating_resolution/missing.json --label synthetic --output reports/generated/issue250/missing.json
```

Không cần candidate IDs, action mapping hay ranking packet theo path.
`complete.json` là test basis gắn nhãn `synthetic_test_only`, không phải production
numeric release. `missing.json` giữ ba generated paths, đưa qua evaluator và
liệt kê mọi C/P/I request chưa có số. Đủ C nhưng thiếu P/I vẫn có Min-Effort;
Pareto chỉ có candidate đủ basis và hợp lệ qua canonical evaluator.

Output automatic dùng [`week4-query-result/0.3.0`](week4-query-result-0.3.schema.json),
coverage có cả ở `semantic.rating_coverage` và
`semantic.ranking_result.rating_coverage`. Explicit packet/semantic-only cũ giữ
transport `0.2.0`. Các lệnh lịch sử bên dưới vẫn thuộc mode cũ.

Metadata `0.3.0` ghi core CLI #213/#233 đã merge, cùng dependency #212/#232.
Status là `experimental_pending_245_250_251_208`: resolver release/cross-review
#245/#250, independent cross-reproduction #251 và integrated acceptance #208
còn pending. Không suy nghiệm thu numeric/private từ synthetic PASS.
Metadata/schema `0.2.0` giữ contract lịch sử. Tests validate coverage và toàn bộ
package `0.3.0` theo hai schema đã commit, kể cả missing/refused, truncated,
zero-action và empty search; API, orchestration và hai subprocess runs phải khớp.

`--rating-resolution` nhận cùng JSON như API. Có thể đặt trực tiếp
`rating_resolution` trong query, nhưng không đồng thời cả option và field.
Automatic cùng `--ranking-query` hoặc explicit action bindings là lỗi input;
không silently override. Exit 0 có thể gồm unrated/refused provider diagnostics;
exit 1 dành cho malformed/config integrity/context conflict làm run không hợp lệ;
exit 2 dành cho thiếu file prerequisite. Numeric registry malformed mà provider
trả structured refusal vẫn ở exit 0, với reason `malformed_input`; đây không phải
missing basis. Không tự fallback qua refusal.

Production policy mặc định từ chối số synthetic. Việc đặt `review_status: accepted`
trong file không thay thế review A/B; caller phải cung cấp artifact đúng scope đã
review. Repository proposed C/I catalogs vẫn pending. Chi tiết fields, canonical
digests và preparation rules ở [API](week4-query-api.md).

Reproduction package trên committed source:

```powershell
$env:PYTHONUTF8 = "1"
python -m scripts.research.issue250_public_probe --output reports/research/issue250-goal-binding-public-probe-v3.json
# Thêm --seamless-raw <manifest-verified-private-raw-dir> để chạy frozen #243.
```

Probe dùng source-provenance guard hiện có; phải commit source và fixture trước
khi chạy. Hai lượt CLI chỉ loại block `runtime` (started_at, duration và runtime
environment), giữ nguyên toàn bộ semantic/reproducibility fields. Probe cũng so
API/orchestration với CLI. Private full outputs chỉ ở thư mục ignored; report
commit chỉ chứa counts, technique programs, diagnostics codes và command paths.
Không cung cấp private raw thì frozen probe ghi `NOT EXECUTED/BLOCKED`.

Config fixtures hiện dùng `public-rating-resolution/1.1.0`; output coverage dùng
`public-rating-coverage/1.1.0`, transport vẫn `0.3.0`. Descriptor được sinh từ
`target_goal.required_state` trong query, không có option CLI để giả descriptor.
Automatic I mapping phải review đúng descriptor, goal ID và snapshot; đổi từ
admin sang interactive session trong cùng graph không tái dùng được admin I.
Refusal này vẫn exit 0, giữ generated paths và effort-only khi đủ C; Pareto
không nhận candidate thiếu I. Xem [API và ví dụ orchestration](week4-query-api.md#binding-goalconsequence-sau-review-258).

Thiếu `scenario_reference` không cấm semantic search, nhưng không cấp authority
cho scoped numeric records. Coverage ghi `scenario_authority.status: absent`
và từng provider attempt/gap. Reference khác scope là lỗi input (exit 1).


## Known semantic coverage gaps

For a declared usable-identity goal, reachable untyped `credential_material` without a same-owner/context password or usable identity emits `UNTYPED_CREDENTIAL_ACTIVATION_UNSUPPORTED`. Completed negative search is `unsupported`; Unknown gates and budget truncation keep their statuses and retain this diagnostic. `complete` still describes enumeration of the implemented model; negative/minimum proof flags are withheld across this known coverage gap. A valid witness remains success, and a material-only goal remains supported. The diagnostic does not assert that the owner has a route to the target, and is not an exhaustive unsupported-technique detector.

Discovery maps this to `unsupported_semantics`, priority Unknown, under `batch-query-result/1.1.0`; legacy result1.0 rejects this new status. Other result serialization stays1.0. Remediation carries `unsupported` reachability rather than proven_unreachable. No automatic conversion from session telemetry or a free-form password claim is implemented. See the [finite experiment and examples](awg-r04/ITERATION-12.md).
