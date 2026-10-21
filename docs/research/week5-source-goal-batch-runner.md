# Source adapter và batch runner (#275)

Runner dùng `AttackQuery → materialize_query → run_attack_query`, rating resolver
và mapper/policy của #268. Mỗi ô source×goal là một giả định compromise **độc lập**.
Reachability chạy được ngay khi chưa có numeric basis; C thiếu là `null`, P thiếu
là `unrated`. Không yêu cầu người dùng viết paths, action mappings hoặc packets
cho từng path.

## Trạng thái tích hợp

Baseline chuẩn bị: develop `7368cac505b3d19331cb8a688114107e91134f25` cùng
handoff #270 `9b262f9559113f88084506f55f67db7bbd959d6d`. #270 chưa merge tại
thời điểm bắt đầu. Nhánh này giữ 4 schemas, fixtures/oracles và tài liệu của
handoff; reference module/test chỉ được chuẩn hóa bằng Ruff 0.16.8 cho Python
3.14. Không sửa expected fixtures, scoring, search hay technique semantics.
Đã merge develop `28236f234a8eba40db0a0f47b70034f27543e063` chứa #270 và
#272 vào PR #276. Hai conflict add/add của reference module/test chỉ khác
formatting; AST được đối chiếu bằng nhau, giữ format Ruff bắt buộc. Merge commit:
`43f965a0d634dc3a458b4014586d1542b111885c`. A cross-review/cross-run và final
integration acceptance vẫn pending. Evidence trước merge được giữ nguyên;
`reports/research/issue275-conflict-integration.json` pin baseline/checks mới và
xác nhận executable batch cùng source pins không đổi tại bước merge đó. Sau
review P1/P2, helper/request boundary đã thay đổi; evidence mới ở
`reports/research/issue275-review-evidence.json` pin fixed source và native replay
trước/sau sửa. Các reports raw/synthetic ban đầu vẫn là lịch sử của source `2e4790b`.

Đã tích hợp develop `8de3e0431f65a57fa5d9d357e48bfe178a07458b`, gồm #278
(locator EA đúng `/groups/18`), #274 và public Top-K #273, qua merge
`e0279df43da5f94d967021390fd69630b14e4a2a`. Reviewer đã approve head `a564a65`
và resolve cả P1/P2 trước lần tích hợp này; head mới cần được xem lại.
Conflict ở mutable Week 4 acceptance manifest được xử lý bằng replay deterministic
trên source tích hợp, giữ semantic digest cũ và các frozen baselines.

Source `bb5f335fb385d2d73aac85807d35193eee7fa903` sửa lỗi transport mới phát hiện:
typed `AttackQuery.top_k=None` phải được serialize thành trường vắng, vì public
Mapping từ chối explicit `top_k: null`. Worker có timeout và query trong trace
dùng cùng serialization; query replay và direct/worker parity được kiểm chứng
cho scenario/evidence-only có rating. Public validation của explicit null vẫn giữ.

Public Top-K đã có trong baseline; batch request chưa expose per-cell K hoặc
Top-K source/destination. Runner không coi `max_paths=K` là K-best.
#267 không tự được adopt và không được load ngầm. Remediation #269/viewer #224
có thể consume refs/matrix, nhưng chưa được triển khai trong runner này.

## Lệnh từ checkout sạch

Python 3.14:

```sh
python -m pip install -r requirements-batch.txt
python -m src.engine batch \
  --batch-request tests/fixtures/batch_contracts/batch_request_example.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json \
  --label synthetic --discover \
  --output reports/generated/batch-result.json
```

`python -m src.engine query ...` chuyển tới CLI public cũ; batch dùng cùng engine.
`python -m src.engine.batch_cli ...` là cùng batch command, không có engine khác.

- `--target-manifest manifest.json`: thay manifest nhúng, vẫn phải đúng snapshot.
- Không chọn đích, `null`, `[]`, hoặc `--discover`: dùng default discovery goals
  trong manifest; manifest không có default thì dùng toàn targets của manifest.
- `--goal GOAL_ID`: drilldown; có thể lặp. Unknown/duplicate IDs bị từ chối.
- `--snapshot snapshot.json`: envelope `snapshot-facts/1`; giữ static evidence.
  `--graph` chỉ có structural records, không được gọi là đầy đủ snapshot facts.
- `--runtime-facts facts.json`: observed/authoritative runtime facts; assumption
  vẫn ở từng source. Batch boundary từ chối `declared_assumption`, `unspecified`
  hoặc invalid origin trước mọi cell/cache execution, cho cả Mapping và RuntimeFact.
  Mapping không có origin giữ public default `observed_evidence`; explicit unknown
  vẫn là unknown. Public fact resolver giữ TRUE/FALSE và unknown-only policy.
- `--rating-resolution config.json`: optional registries/policy/scope của public
  resolver. Chỉ scope query/cell được bind; không rewrite numeric records,
  applicability, context hoặc ordered-history bindings để làm chúng phù hợp.
- `--technique TECHNIQUE_ID`: lặp để công bố technique scope; không có structural
  prefilter. Không truyền option này thì dùng public catalog hiện có.
- Private/SEAMLESS: cần `--label seamless` hoặc `private` cùng ít nhất một
  `--prerequisite` file. CLI pin bytes, không coi label là chứng nhận quyền dùng.

Public Python single-source helper nhận **toàn request**, không tái tạo request
từ source/manifest với default semantics:

```python
from src.engine.batch import discover_source

# one_source_request là BatchQueryRequest hoặc Mapping theo schema đã công bố.
result = discover_source(one_source_request, graph)
# Với multi-source request, chọn rõ một source đã khai báo:
result = discover_source(batch_request, graph, source_id="src-alice-usable")
```

Helper chỉ thay `sources`; giữ batch ID, evaluation mode, common/custom budgets,
target selection/manifest/snapshot, prioritization policy và rating_resolution.
Request đặt `target_goal_ids=null`/`[]` cho discovery hoặc IDs cho drilldown.
Execution options (facts, technique scope, global budgets, checkpoint/resume) được
forward nguyên tới cùng runner. Multi-source không có selector/unknown selector bị
từ chối. Đây là sửa API experimental trước acceptance; thay lời gọi cũ
`discover_source(source, manifest, graph)` bằng request đầy đủ để tránh mất scope.

## Profiles và mục tiêu

Canonical source ID/kind, target ID/kind, duplicate IDs và snapshot binding được
validate trước query. Adapter dùng `BatchSourceItem.to_foothold_profile(graph=...)`.
`user_leaked_password` cần context Computer tồn tại: missing/empty context trả
`MISSING_AUTHENTICATION_CONTEXT`; context User/Group/không tồn tại trả
`INVALID_AUTHENTICATION_CONTEXT`. Các trường hợp này là `unsupported_source`,
không phải proven no-path. Password chỉ là credential artifact đến khi activation
thành công; không cấp trước usable identity hay host admin.

`user_usable_identity`, `computer_control_admin`, `computer_control_user` giữ
đúng declared initial state của #268. Group/Domain/OU/GPO/Container vẫn là typed
unsupported sources. “Node bất kỳ” chưa được hỗ trợ đủ. Source declaration và
assumptions không phải observed compromise; provenance nằm trong public trace.

Manifest tách `effective_member` của DA/EA và `admin_control` của host/DC. Checkpoint
không trở thành host takeover. Hiện engine còn giới hạn endpoint cho một số goals
như User usable-identity sau activation ở Computer context; runner không sửa hoặc
che giới hạn semantic search đó. Pilot sử dụng entitlement và host-admin goals.

## Matrix, trace và source summary

Output validate `batch-query-result/1.0.0`; request validate
`batch-query-request/1.0.0`. Không tạo parallel request/result schema. Metadata
execution phiên bản `source-goal-execution/1.0.0` dùng các object extensible đã có:

| Vị trí | Nội dung |
| --- | --- |
| `reproducibility.inputs` | normalized request, graph/facts digest, config/source pins, technique scope, observed facts và `scope_digest` |
| `reproducibility.inputs.public_queries[REF]` | exact public query, materialized state/context/rejected assumptions, candidates/attempts/action traces, rating/coverage và guarantees |
| cell diagnostic `PUBLIC_QUERY_TRACE` | `trace_ref` và digest để kiểm tra exact trace |
| `min_effort_path` | witness steps riêng với C; selected candidate ID và trace ref |
| source diagnostic `SOURCE_SCOPE` | representative goal ID, declared và not-run goals |
| `summary` | declared/evaluated/not-run cells, success, C/P-rated denominators, statuses và policy |
| `reproducibility.runtime` | volatile elapsed/runtime, execution budget, executed/reused counts và CLI file references |

Candidate IDs `generated_NNNN` ánh xạ tới public `paths[N-1]`; best candidate là
authoritative Min-Effort result, không chọn P từ candidate khác. Zero-action đã
đạt mục tiêu có C=0 theo public semantic zero-work, không có P tự mặc định.

Tên wire policy của accepted #268 là `min_effort_impact_pareto` (ý tưởng
`impact_min_effort_pareto` trong #275): impact → C → blast radius → conditional
P nếu rated → steps → source ID. Đây là adopted **defensive display policy** của
contract, không phải xác suất chiếm cả hệ thống hoặc exact Top-K nguồn/đích.
Không cộng P các paths. Steps chỉ dùng tie/display, không làm effort.

Runner giữ priority/representative của policy và bổ sung disposition cho toàn row:
success ở một goal không xóa error/truncation/indeterminate hoặc goal chưa chạy.
Không gọi nguồn unrated/incomplete là an toàn. Một cell thành công nhưng capped
giữ witness cùng guarantee subset, không được claim global Min-Effort.

## Budgets và resume

Per-query logical caps dùng `common_budget`/`custom_budget` của accepted request.
Global `--max-cells N`, `--global-max-expansions N` là logical budgets. Global
expansion budget giảm public expansion cap của ô tiếp theo; giữ toàn denominator
và `CELL_NOT_RUN` khi hết budget. Mỗi ô error độc lập; không hủy cả batch.

`--query-seconds S`/`--global-seconds S` là wall limits optional. Query chạy trong
spawned isolated process; timeout terminate worker, trả `truncated_incomplete`,
`QUERY_TIMEOUT`, không cache negative. Engine chưa có streaming partial witness:
wall-killed worker chưa gửi completed result sẽ không có witness nhận được.
Witness của native logical truncation vẫn được giữ đầy đủ. Wall timeout boundaries
phụ thuộc máy/startup và **không** được dùng để claim deterministic timeout parity.

```sh
python -m src.engine batch --batch-request tests/fixtures/batch_contracts/batch_request_example.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --label synthetic \
  --max-cells 1 --checkpoint reports/generated/checkpoint.json \
  --output reports/generated/partial.json
python -m src.engine batch --batch-request tests/fixtures/batch_contracts/batch_request_example.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --label synthetic \
  --resume --checkpoint reports/generated/checkpoint.json \
  --output reports/generated/resumed.json
```

Checkpoint `source-goal-checkpoint/1.0.0` chứa scope/cell fingerprints, content
digests và completed cell/trace. Chỉ reuse matching completed cells; error,
wall timeout, native truncated và cells chạy bằng reduced global cap được rerun.
Đổi graph/facts/snapshot, source/profile/context/assumptions, targets, basis,
evaluation mode, technique scope, per-query timeout, Python hay executable bytes
thì reject `CHECKPOINT_SCOPE_MISMATCH`. Không trộn khác scope.
Global budgets có thể tăng khi resume; reused cells không trừ budget cho công việc
mới. Chưa có parallel scheduling; serial, single-source và resumed completed runs
được kiểm chứng semantic parity. Timestamps/elapsed/reuse metadata tách khỏi semantic
matrix/priority/diagnostics; không so toàn JSON bytes có runtime volatile.

## Evidence và tái lập

```sh
python -m pip install -r requirements-tests.txt
python -m pytest tests/test_source_goal_batch_contract.py tests/test_source_goal_batch_runner.py
python -m scripts.research.run_source_goal_batch_pilot \
  --raw-dir data/raw/SEAMLESS \
  --output-dir reports/generated/issue275-seamless \
  --sanitized-report reports/generated/issue275-seamless-pilot.json
```

Pilot verify toàn 6 raw files theo manifest trước và sau, build full canonical
graph và snapshot facts; 5 profiles/source scenarios × 3 default goals, 4 techniques,
caps 10 paths/6 steps/100 expansions mỗi cell. Chạy scenario và evidence-only riêng;
không load proposed numeric catalog. Không phải full-source batch hay scalability
benchmark. Private request/snapshot/matrix ở output-dir; chỉ aggregate aliases,
locators, pins/caps/denominators/runtime được phép đưa vào sanitized evidence.
RSS được báo khi chạy Linux; Windows báo chưa đo, không thay bằng con số giả.

Finite fixtures/oracles #268 byte-preserved; expected reachability/status được so với
runner thật. Finite numeric fixtures dùng published identity formulas trước search,
hardcode độc lập C=1/P=3/4 và shared work C=2/P=3/8; không lấy expected từ output.
Local PASS, remote CI và A cross-run là ba kết quả riêng. Worklog ghi trạng thái
thực tế; #275 giữ open tới integrated acceptance.

Sau #278, `reports/research/issue275-seamless-corrected-pilot.json` là fresh pilot
trên source tích hợp với manifest EA đã sửa. Report này supersede evidence locator
của `reports/research/issue275-seamless-pilot.json`; file cũ giữ nguyên như lịch sử
của source `2e4790b`, không dùng làm bằng chứng binding hiện tại. Raw requests,
request/scope digests được tạo lại từ manifest hiện hành, cùng verify sáu raw files
trước/sau. Checkpoint cũ phải được thay: manifest/source khác làm resume từ chối
`CHECKPOINT_SCOPE_MISMATCH`. Không sửa digest của artifact lịch sử để giả thành
một lần chạy mới.
