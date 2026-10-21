# #250 — Quyết định tích hợp Rating Resolver vào public query

Ngày kiểm chứng: 2026-10-10. Reviewer cần cross-review: A; coding agent chạy các checks local.
Tài liệu này mô tả implementation và bằng chứng chạy, không phê duyệt numeric
catalogs/equivalence, không đóng acceptance gate #245/#250/#251.

Trạng thái hiện hành sau review tiếp: public config/coverage **1.1**, typed goal
binding và scenario authority theo phần G. Source implementation cuối của lượt
sửa review là `bfc3806864e0bc450739c1534329596bfdd5dc1b`; full suite và public probe
chạy trên `776f4493402ee50284c242666adeba226b8a4462` (chỉ thêm generated manifest).
Các kết quả lịch sử bên dưới giữ đúng revision của từng lượt.

## A. Kết quả và luồng hiện tại

Baseline chính xác: `94db074b5cd5c74b76b5e2555d59c5a952153b7e` từ `origin/develop`
sau `git fetch origin`. Contract #246 accepted qua #252 (`af28ccc...`), C provider
#253 (`d1ff1b3...`), I provider #255 (`8e34940...`) và P provider #254 (`94db074...`)
đều đã merge. Comment kickoff #250 cho phép integration bắt đầu; #256 làm basis
song song, không là prerequisite cho code. #247 C catalog và #249 equivalence
vẫn pending numeric review; implementation không đổi các status đó.

Workspace ban đầu: branch `feature/155-engine-path-ranking`, HEAD
`38b8f4e89851a6459f608195d54075c809d2b6cc`, không có tracked changes;
`.worktrees/` và `data/raw.zip` là untracked.
Tạo worktree riêng `.worktrees/issue-250`, branch
`feature/250-public-rating-integration` từ baseline trên; worktree mới sạch.
Không sửa dữ liệu hoặc các worktree có sẵn.

Source implementation/probe commit đầu tiên:
`d4a330fa77b911ccb0d2240573f66ea261f8fa32`. Các evidence artifacts ghi revision
thực đã execute; commit tài liệu/evidence sau đó không tự được coi là một lượt
chạy mới. Bảng kiểm chứng bên dưới phân biệt source revision và handoff artifact.

Trước thay đổi, public query cần packet/binding tương thích để rank; artifact
transitions không có structural edge thường không bind được bằng edge matching.
Sau thay đổi:

```text
semantic query + explicit scope + reusable registries/policy
→ search hiện có
→ typed semantic replay
→ resolve_generated_rating_inputs
→ bound actions + canonical work ledger + full-history C/P/I requests
→ adapt_search_candidate + semantic verification + canonical validation
→ PathRankingEngine: assessments, effort-only Min-Effort, Pareto
→ rating_coverage trên cùng result
```

Caller cung cấp semantic goal/state/context/caps như trước và
`rating_resolution` versioned. Không cần candidate IDs/action mapping/ranking
packet theo path. Native P registry vẫn phải có ordered full-history basis đúng
scope: không thay yêu cầu này bằng marginal q theo technique. Basis một prefix
được reuse cho nhiều paths có cùng active history, kể cả path khác passive steps.

Engine tự bind toàn bộ state atoms ở before/additions, runtime facts cùng origin,
semantic goal khi predicate thực sự đạt, auth/resource context và recovery method
từ typed history. Structural authorization/snapshot evidence vẫn được kiểm bằng
replay và canonical adapter; không được biến thành số từ assumptions.

`MaterializedQuery.run`, `run_attack_query`, query CLI dùng
[`resolve_generated_rating_inputs`](../../src/engine/ranking/resolution_service.py).
Generated orchestration automatic delegate `MaterializedQuery.run` nên cùng dùng
service và evaluator. Search/AttackState/math/Pareto không bị viết lại.

## B. Bảng quyết định thiết kế

Các phương án trong bảng là những lựa chọn đã cân nhắc khi triển khai. Trạng thái
“implemented; pending A cross-review” nói về review integration, không nói các
numeric decisions đang pending đã accepted.

| Vấn đề | Phương án cân nhắc | Lựa chọn và lý do/trade-off | Compatibility/hành vi | Code và kiểm chứng | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| Vị trí nối resolver | Rating logic riêng trong từng entry point; service giữa search và adapter | Service sau authentic search; replay typed history trước materialization. Tránh hai evaluator, chấp nhận thêm replay cost trong bounded scope | Không đổi search, evaluator hoặc score math | `resolution_service.py`; `test_all_entry_points_and_two_runs` | implemented; pending A cross-review |
| Public configuration | Engine tự đọc arbitrary file paths; embedded JSON thống nhất | API nhận JSON; CLI đọc file qua loader/provenance hiện có. Pin envelope version và canonical digest, scope/horizon/event do caller khai báo | Automatic opt-in qua `rating_resolution`; thiếu cấu hình giữ legacy semantic-only, tránh tự invent scenario/horizon | `load_resolution_config`; fixtures `rating_resolution/`; subprocess CLI probes | implemented; pending A cross-review |
| Explicit packet precedence | Ghép tự động registries với packet; chọn một nguồn ngầm; mode riêng | Automatic và explicit packet/bindings loại trừ nhau, báo lỗi khi cùng truyền. Legacy packet giữ đường cũ, không đổi số | Week 3/#207/#212 giữ mode cũ, transport 0.2.0; automatic transport 0.3.0 | `query.py`, `query_cli.py`; test conflict; existing CLI/scoring regressions | implemented |
| Predicate binding theo branch | Chỉ tuple technique/actor/source/target; locator riêng mỗi step | Thêm locator `(candidate_id, step_index)` ưu tiên cho binding nội bộ. Cùng tuple có thể có before-state khác; locator không làm đổi rating key | Tuple cũ vẫn hoạt động. IDs deterministic theo contract; không dùng index làm work identity | `resolver.py::_parse_candidate_structure`; generated passive+direct và inherited alternatives | implemented; pending A cross-review |
| Materialize semantic facts | Placeholder “target compromised”; serialize actual state/facts | Hash canonical state atoms, giữ before/additions và runtime origin; goal effect chỉ khi actual predicate đạt. Typed replay vẫn authoritative | Initial capability là khai báo trạng thái, không là telemetry hay q=1. Không mở false/unknown gates bằng số | `_state_atoms`, `resolve_generated_rating_inputs`; extension/gate tests | implemented; pending A cross-review |
| Registry applicability | Arbitrary callable từ JSON; fuzzy technique reuse; exact native metadata | Native classes + optional exact `source_ids`; named predicates chỉ allowlist đúng native class. Không nạp executable code từ registry | Absent `source_ids` giữ behavior/serialization cũ. Phân biệt direct/inherited bằng source thật, không bằng candidate ID | `effort_registry.py::ClassApplicability`; independent C fixture [4,4,1] | implemented; pending A cross-review |
| Shared preparation | Tự thêm prep từ technique name; reusable reviewed semantic decomposition | Optional `work` registry rules có accepted scoped review. Engine tự materialize context-bound prep ID và ledger; không pre-rate prep | Chỉ rules được caller review mới tạo extra work. Numeric provenance không đổi work identity; passive không tạo C/P | `shared_preparations`; shared probe C=[5,5,2], P=[1/8,1/8,3/8] | implemented; pending A cross-review |
| Schema/version coverage | Đổi native schema #246; một coverage percentage; envelope extension riêng | Giữ native 1.0.0; public coverage 1.1 tách search/binding/numeric, thêm typed goal và scenario authority ở phần G; không aggregate score/% | Đọc coverage 1.0 lịch sử; `semantic_status` lấy từ canonical assessment. `numeric_complete` không là search complete | public schema; `query.py::_evaluate_query_outcome`; count/conservation tests | implemented; pending A cross-review |
| Denominators | Cộng số step/path; đếm distinct work/prefix | Per candidate: distinct first-use work IDs, mọi ordered prefixes; toàn query: union C IDs/P prefixes và một I scope. Binding đếm step occurrences riêng | Passive vẫn hiện ở trace, không tạo cost/q event. Cùng prep dùng chung không cộng hai lần. Prefix thiếu đầu tiên không che prefix sau | `numeric_requests`, `denominators`, native coverage builder; shared/later-prefix tests | implemented |
| Missing với refused/malformed | Catch mọi lỗi thành missing; giữ native dispositions/errors | Missing numeric vẫn chuyển valid candidates qua evaluator. Refused/conflicting dừng provider chain; malformed config/digest/context là error, malformed numeric có structured provider refusal | CLI exit 0 có thể có unrated/refused; exit 1 cho invalid run; không dùng fallback che refusal | policy wrapper/native provider traces; context/integrity/prototype tests | implemented |
| C đủ, P/I thiếu | Chỉ xét fully rated candidates; dùng canonical effort-only assessment | Giữ Min-Effort từ tất cả feasible C-rated assessments, độc lập eligibility Pareto | Có thể chứng minh minimum effort trong complete declared scope khi mọi feasible alternative đủ C; mixed C chỉ best trong rated subset | existing evaluator + query guarantee logic; effort-only/mixed/cap tests | implemented |
| Zero-action/incomplete search | Empty product/default impact; minimum trên mọi generated subset | Zero-work disposition cũ, không tạo canonical/Pareto candidate hoặc P/I numeric. Giữ search caps/truncation và downgrade guarantees khi thiếu binding/C | `numeric_requests` bằng 0 khi không có active candidate, không là full numeric acceptance. Truncated không chứng minh minimum toàn scope | zero/cap tests; existing #212 regression | implemented |
| Reuse/mở rộng contract | Rewrite provider/evaluator; extension nhỏ tại public boundary | Reuse accepted providers/decoder/validator. Thêm public envelopes, step locator, optional source applicability. Không sửa canonical identity/formula | Cần A xác nhận extension và preparation decomposition; không đóng numeric gates #247/#249/#256 | contract appendix, API/CLI docs, focused tests | implemented; pending A cross-review |
| Empirical production | Import prototype bounds; native #238/#248 production gate | Native trials/manifest đi qua existing provider; prototype refusal giữ authority, scenario fallback không bypass | Không có production empirical claim hoặc SEAMLESS transfer từ test basis | prototype public API regression; native P regressions | implemented; empirical acceptance deferred |
| Historical evidence serialization | Serialize optional extension ngay cả khi None; bỏ riêng field mới khi inactive | Runner bỏ `rating_resolution` chỉ khi None; giữ nguyên các optional fields lịch sử. Full oracle regression phát hiện thêm field None làm đổi evidence digest dù scoring không đổi | Không rewrite fixture/oracle; automatic config vẫn được ghi khi có | `week4_acceptance_runner.py::query_evidence`; existing `test_week4_acceptance_manifest_semantic_reproduction` | implemented |

### Ý nghĩa cụ thể của coverage

`semantic_search` chứa complete/truncation/termination, allowed techniques và caps;
search “complete” chỉ trong finite declared scope hiện tại. `binding` chứa generated
step occurrences, bound actions/work IDs, passive count, canonical admissions và
rejections. `unsupported_work_units` dựa trên provider attempts; candidate vẫn
được đánh giá khi numeric class unsupported. Refusal của provider không đồng nghĩa
semantic action không tồn tại.

`numeric_requests.C/P` đếm request distinct toàn query; per-candidate counts có thể
cộng lại lớn hơn union vì các paths reuse work/prefix. `I.required=1` nghĩa một
asset/success-event/consequence request, không phải từng path có impact riêng.
Khi không có active candidate, I không applicable và required=0. Không suy
“đủ numeric” từ denominator rỗng. `providers_attempted` là trace thực; danh sách
configured/version được xuất riêng, cùng registry và configuration digests.

## C. Output thực tế đã chạy

Các đoạn dưới rút gọn từ CLI output local, revision được ghi trong evidence
runner. Chỉ bỏ các field không liên quan trong đoạn trích; không sửa số.

Đủ rating, test basis:

```json
{"numeric_requests":{"C":{"rated":2,"required":2},"P":{"rated":2,"required":2},"I":{"rated":1,"required":1}},"minimum_effort":1,"pareto_frontier":["generated_0003"]}
```

Có ba paths nhưng chỉ hai active work identities. Hai direct variants có C=4,
P=1/4; inherited có C=1, P=3/4, impact High. Đây là expected độc lập từ fixture
trước run, không lấy actual output làm oracle; nhánh inherited dominate direct.
Tất cả records giữ `synthetic_test_only`, không là empirical/business acceptance.

Thiếu numeric basis:

```json
{"numeric_requests":{"C":{"rated":0,"required":2},"P":{"rated":0,"required":2},"I":{"rated":0,"required":1}},"minimum_effort":null,"pareto_frontier":[],"gap_codes":["missing_evidence"]}
```

Ba generated candidates vẫn có canonical semantic assessment. Không có số để
kết luận effort/risk; unsupported class nằm trong provider trace/binding coverage.

Context mismatch/refusal:

```json
{"numeric_requests":{"C":{"rated":2,"required":2},"P":{"rated":1,"required":2},"I":{"rated":1,"required":1}},"gap":{"dimension":"P","disposition":"refused","reason_code":"out_of_scope"}}
```

Registry horizon 72h không khớp scope 24h ở direct prefix. Engine giữ exact refusal;
không bù số bằng fallback. Prefix inherited vẫn rated. Min-Effort vẫn là 1 nhờ C
đủ, nhưng coverage không được diễn giải thành toàn bộ risk alternatives đủ basis.
Digest mismatch khác hẳn: CLI exit 1, stderr
`Invalid input/run: Registry integrity digest mismatch: effort`, không tạo output.

Effort-only:

```json
{"numeric_requests":{"C":{"rated":2,"required":2},"P":{"rated":0,"required":2},"I":{"rated":0,"required":1}},"minimum_effort":1,"pareto_frontier":[]}
```

Đủ C cho complete small declared scope cho phép minimum effort; không cho phép
kết luận P/I hoặc tạo fake Pareto point. Shared preparation variant có union C=3,
P=3, mỗi candidate dùng hai units/prefixes; C=[5,5,2], P=[1/8,1/8,3/8].

## D. Bằng chứng kiểm chứng

Lệnh Python dưới đây chạy từ worktree root bằng interpreter Python 3.14 trong
workspace `.venv`; trên Windows đặt `PYTHONUTF8=1` để các tests lịch sử đọc UTF-8
đúng. Không coi exit code của một chuỗi PowerShell là exit code của từng check.

| Case | Command/test | Expected | Actual | Revision | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| Generated C/P/I và shared/passive work | `test_generated_effort_risk_and_passive_work` | C [4,4,1] hoặc [5,5,2]; exact Fraction P; frontier inherited | Khớp oracle; native evaluator được dùng | source commit trên | PASS synthetic |
| API/CLI/orchestration; deterministic | `test_all_entry_points_and_two_runs`; `python -m scripts.research.issue250_public_probe --output reports/research/issue250-public-probe-v1.json --seamless-raw <local-verified-raw-dir>` | Full ranking/coverage bằng nhau; hai CLI runs bằng nhau ngoài block runtime | 15/15 probes PASS; full ranking/coverage bằng nhau cho bảy synthetic cases hợp lệ | `7e8f9c4e0f32c3a43b9a6ad377f6dff7ef5251ed` | PASS |
| Missing/mixed/context/prototype/integrity | `tests/test_public_rating_integration.py` | Không mất paths; native gap/refusal; integrity error khác absence; không bypass prototype | 20 focused tests PASS; bộ liên quan 232 passed/3 skipped, exit 0 | `7e8f9c4e0f32c3a43b9a6ad377f6dff7ef5251ed` | PASS |
| Effort-only/caps/zero-action | focused tests + public probe | Min-Effort không cần P/I; no fake risk hoặc global guarantee | Các expected khớp | source commit trên | PASS synthetic |
| Core + AS-REP/Kerberoast/RBCD | `test_extensions_all_missing_prefixes_and_semantic_replay` | Mọi valid generated path có assessment; mọi prefix thiếu đều hiện | PASS trên fixtures extensions; không phải actual dataset | source commit trên | PASS synthetic |
| Accepted Week 3/#207/#212 | existing regression suite và `python -m scripts.research.week4_acceptance_runner --check-determinism --output reports/research/week4-acceptance-manifest.json` | Historical scoring, semantics và evidence digest giữ nguyên | Runner: 38 ca, 36 PASS, 0 unexpected failures, 1 NOT EXECUTED, 1 BLOCKED; digest `3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d` khớp accepted fixture; exit 0 | `9d6368fdd0cc50ba4551df8e35720448b796f65e` | PASS trong executable scope |
| Frozen #243 private | public probe `--seamless-raw` | Loader xác minh pinned raw manifest; semantic oracle nguyên vẹn; pending numeric không activate | 7/7 actual private cases PASS; mọi frozen semantic fields được assert; numeric vẫn unrated/refused | `7e8f9c4e0f32c3a43b9a6ad377f6dff7ef5251ed` | PASS |
| Required checks | ruff, format, yamllint, repository/contract checks, Compose config, full pytest | Theo CI workflow repository | Tất cả exit 0; full pytest 2.498 passed, 15 skipped, 48 subtests passed | `c6e337235c94ac864683bffebbde78b78cf9da2e` | PASS local Windows |
| Remote CI | Không dispatch/push trong task | Không claim local thành remote | NOT EXECUTED | — | NOT EXECUTED |

### Kết quả final

Public probe revision `7e8f9c4e0f32c3a43b9a6ad377f6dff7ef5251ed`: 15/15 case
PASS, exit 0; 30 subprocess CLI runs. Integrity-error case có exit codes [1,1]
đúng expected; các case còn lại [0,0]. Chỉ block `runtime` được loại khi so hai
runs. Bảy synthetic cases hợp lệ có full ranking/coverage bằng API/orchestration.
Synthetic ratings là algorithm tests, không phải production numeric acceptance.

Bảy case #243 dùng actual private SEAMLESS raw đã kiểm manifest, không dùng
synthetic thay thế. Frozen assumed có một path đạt goal, C=0/4, P=0/4, I=0/1;
đó là conditional semantic prediction và numeric refusal/gap, không phải observed
exploit hoặc empirical numeric evidence. Raw/missing_recovery, asset_veto, off,
no_request và step_cap khớp frozen expectations. Probe assert cả projected states,
successful prefixes, veto reason và caps. Full identities/snapshot/outputs giữ
local dưới ignored `reports/generated/issue250/`; report commit không chứa private SID.

Các checks tại `7e8f9c4e0f32c3a43b9a6ad377f6dff7ef5251ed`:
`python -m ruff check .`, `python -m ruff format --check .`,
`python -m yamllint .`, `python scripts/check_repository.py`,
`python scripts/check_contract.py` và
`docker compose --env-file .env.example --profile graph config --quiet`
(với `NEO4J_PASSWORD=ci-validation-placeholder`) đều exit 0.
`python -m pytest tests/test_public_rating_integration.py tests/test_rating_resolver.py tests/test_effort_rating_provider.py tests/test_rating_p_provider_chain.py tests/test_rating_p_review_regressions.py tests/test_query_cli.py -q`
đạt 232 passed, 3 skipped, exit 0. Ba skip là default private paths trong worktree;
actual private public probe ở trên vẫn đã execute.

Lượt full pytest đầu tại `d4a330fa77b911ccb0d2240573f66ea261f8fa32`:
2.491 passed, 15 skipped, 48 subtests passed, bốn failures từ
`W4-CLI-PACKAGE.clean_tracked_source` vì manifest vừa được runner cập nhật chưa
commit. Guard được giữ nguyên. Sau commit, full run tại
`679608bb7123c9780c9105ba9d3a2c2a58cb7331` phát hiện evidence digest mismatch;
dừng run để sửa (exit 1), không gọi là PASS. Focused manifest test xác nhận lỗi.
Semantic/scoring fields khớp; khác biệt chỉ là field `rating_resolution: null`
trong evidence của query legacy. Sửa serializer bỏ riêng extension inactive,
không sửa accepted fixture/oracle hoặc nới test. Digest `9eee...` trong lượt trước
là digest tái lập khi còn lỗi này, không phải accepted historical digest.
Accepted fixture có digest
`sha256:3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d`.

Sau public probe, executable query/resolver/provider behavior giữ nguyên; sửa ký
tự § trong docstring và serializer evidence lịch sử như trên. Manifest tiếp tục
được regenerate bằng runner chuẩn trên committed source. Remote CI chưa chạy.

### Kết quả required checks trên source cuối

Implementation source cuối: `9d6368fdd0cc50ba4551df8e35720448b796f65e`.
Manifest được runner sinh trên revision này, sau đó commit tại
`c6e337235c94ac864683bffebbde78b78cf9da2e`; tracked working tree sạch trước full
test. Bảng dưới là kết quả thực tại revision `c6e3372...`, Python 3.14.7/Windows.
Commit handoff tiếp theo chỉ cập nhật tài liệu này, không đổi source/input pins.

| Command | Expected | Actual / exit code | Trạng thái |
| --- | --- | --- | --- |
| `python -m pytest -xq` với `PYTHONUTF8=1` | Toàn suite không failure | 2.498 passed, 15 skipped, 48 subtests passed; 763,13 giây; exit 0 | PASS |
| `python -m ruff check --no-cache .` | Không lint error | All checks passed; exit 0 | PASS |
| `python -m ruff format --check --no-cache .` | Không file cần format | 400 files already formatted; exit 0 | PASS |
| `python -m yamllint .` | Không YAML error | exit 0 | PASS |
| `python scripts/check_repository.py` | Cấu trúc/links hợp lệ | 582 tracked/unignored files; exit 0 | PASS |
| `python scripts/check_contract.py` | Contract và synthetic fixtures hợp lệ | Contract and 2 synthetic fixtures validated; exit 0 | PASS |
| `docker compose --env-file .env.example --profile graph config --quiet` | Compose render hợp lệ, không khởi động services | `NEO4J_PASSWORD=ci-validation-placeholder`; exit 0 | PASS |

15 skips gồm 13 trường hợp thiếu dataset tại default paths của worktree và hai
điều kiện filesystem Windows. Không coi các skips đó là probes đã execute.
Legacy Week 4 runner giữ 1 NOT EXECUTED và 1 BLOCKED thuộc prerequisite/gate của
riêng runner; actual private #250 public probe là lượt riêng có đường dẫn raw
explicit, đã PASS bảy cases. Không suy dataset evidence hoặc numeric acceptance
từ synthetic tests.

[Report public đã lọc](../../reports/research/issue250-public-probe-v1.json) ghi
commands, từng subprocess exit code, revision, registry/source digests và kết quả
hai runs. [Manifest chuẩn](../../reports/research/week4-acceptance-manifest.json)
giữ exact source pins và accepted semantic digest. Remote CI: NOT EXECUTED;
không push/dispatch trong task này, không claim local checks là CI PASS.

## E. Handoff

#250 hoàn thành public automatic assembly, versioned registry/policy config,
shared resolution service, effort-only evaluation và explainable coverage; thêm
regressions và reproduction runner với committed-source guard. Usage docs có lệnh
chạy được cho API/CLI và fixtures test-only.

#256/#247/#249 vẫn sở hữu review/acceptance numeric catalogs, P full-history basis
và I consequence/equivalence. Không tự promote pending records. C đủ hoặc I đủ
cho frozen actual dataset chỉ có thể claim sau đúng review và scope; test fixtures
không thay thế decision đó. #237 empirical production campaign vẫn ngoài scope.

#251 cần clean-checkout cross-reproduce các pinned commands/basis và actual frozen
oracle, xác nhận full-history context/horizon, so sánh independent C/P/I expected,
review preparation rules và coverage schema. A cần xác nhận automatic opt-in,
exclusive packet mode, per-step binding locator, optional `source_ids`, declared
semantic event/consequence linkage và shared-work decomposition. Event labels/
review references do caller cung cấp phải thực sự được review; digest chỉ bảo vệ
nội dung, không tự chứng thực approval.

| Acceptance #250 | Mapping | Gap/handoff |
| --- | --- | --- |
| Public API/subprocess CLI không path packet | service, versioned fixtures, entry-point test/probe | A cross-review |
| Deterministic bindings cho generated transitions, extensions, #243 | resolver locator extension, typed history/replay, extension tests, private probe | Numeric scope acceptance riêng #256 |
| Equivalent results/coverage và hai lượt deterministic | common query.run orchestration; full ranking equality test; runner | B/#251 clean checkout khác |
| Mixed/missing/unsupported/context/prototype/integrity | native provider traces, policy, public regression suite | Không coi structured refusal là absence |
| Min-Effort/Pareto generated | independent fixtures; C/P/I/scoring tests và public probe | Production numeric release chưa accepted |
| False/unknown/replay/budget/dedup/incomplete/zero | new negative tests + existing suite/runner | Complete chỉ trong declared finite scope |
| Week 3/#207/#212 giữ nguyên | legacy exclusive mode + accepted tests/runner | Không mở lại oracle, không claim remote CI PASS |
| Historical #243 giữ nguyên | frozen spec/artifacts không sửa; output #250 path/schema riêng | Actual probes theo phần D; không commit private outputs |

Không merge/promote main, không phê duyệt catalog/equivalence hay đóng gate trong
handoff này.

## F. Sửa review PR #258 và đồng bộ #257 — 10/10/2026

Review A `5476923849` và comment `6092426880` yêu cầu coverage/schema, metadata
nghiệm thu và đồng bộ develop. Baseline PR là `09d6f9ae32e1219b283d0bd5bd3c33b2700dbb68`;
develop sau #257 là `036255ecd4b738f9e571cdb36dacdb49a25907f5`.
Hai nhánh không sửa trùng file; giữ lịch sử bằng merge parent, không force-push.

### Coverage sau canonical boundary

Kiểm tra implementation cũ cho thấy `_evaluate_query_outcome` đã bổ sung hai
fields sau resolver; 20 public integration tests baseline PASS trên Python
3.14.8/Linux. Vì vậy không thêm hằng số vào coverage ở giai đoạn materialization.
Tách bước hoàn thiện sang `finalize_generated_rating_coverage` trong service:

- `canonical_admitted_candidates` đọc trực tiếp `search_audit.candidates_adapted`
  của adapter/canonical validator, bỏ fallback mặc định 0 khi thiếu audit.
- `canonical_rejections` chỉ lấy diagnostics `adapter_ineligible` hoặc
  `canonical_candidate_invalid`, giữ reasons/message từ canonical outcome.
  Missing numeric basis/provider refusal vẫn là assessment đã admit.
- Candidate summaries nhận semantic status sau evaluation. API/CLI/orchestration
  vẫn cùng đường thực thi; zero-action và empty search không dựng envelope/q/I.

Tests mới validate coverage schema và package `0.3.0` bằng Draft 2020-12, kể cả
external coverage reference. Sáu modes complete/missing/production-refusal/
truncated/initial-goal/empty đều đối chiếu API, orchestration và hai CLI runs.
Hai negative tests làm hỏng mapping hoặc target sau materialization, rồi để
adapter/validator thật từ chối một trong ba candidates: admitted phải là 2,
rejection phải khớp canonical diagnostics và không chứng minh minimum toàn scope.
`jsonschema==4.26.0` chỉ là dependency kiểm thử trong requirements-tests;
wrapper này include requirements-dev, và CI/README dùng wrapper hiện hành.
Requirements-dev giữ nguyên bytes đã pin trong hồ sơ Week 3.

### Metadata và source pin sau đồng bộ

Transport automatic `0.3.0` ghi #213/#233 đã merge, chuyển pending gates sang
#245/#250/#251/#208 và independent private/SEAMLESS reproduction. Legacy `0.2.0`
giữ metadata/schema lịch sử; không sửa evidence cũ hoặc frozen #243 artifact.

#257 kiểm source pins và phát hiện resolver #250 khác baseline. Delta đã kiểm:
chỉ thêm `(candidate_id, step_index)` locator với fallback identity cũ cùng type
hints. Cập nhật một resolver source pin trong catalog và catalog digest trong
manifest; ghi amendment ở verification.md. Không đổi actions, tám P bindings,
intervals, release dispositions, oracle hoặc min-effort input; numeric activation
vẫn 0, pending provider vẫn refusal. Không nới verifier hoặc bỏ qua hash drift.

Lượt sửa dùng Python 3.14.8/Linux và dependencies theo requirements-dev.
Lượt full đầu phát hiện dependency/schema-test làm lệch Week 3 dependency pin,
và manifest Week 4 cũ còn pin source/docs trước review. Đã tách dependency vào
requirements-tests, giữ nguyên fixture và bằng chứng Week 3. Manifest mới là
`reports/research/issue250-review-acceptance-manifest-v2.json`; tests kiểm pins/
autocrlf hiện hành dùng artifact mới, vẫn đối chiếu đúng independent oracle cũ.
Không sửa `reports/research/week4-acceptance-manifest.json` từ head trước review.
Focused/full checks và revision cuối được ghi trên PR #258 sau khi source đã
commit sạch. Private SEAMLESS raw không có trong checkout này; không claim đã
chạy lại private probes, Windows, Docker/Compose hoặc remote CI. Historical
results ở phần D là lượt trước, không được trình bày thành verification mới.

## G. Ràng buộc consequence với semantic goal — review tiếp #258

Baseline lượt sửa này: PR head `3b46e097d954e8037060149513d64f3ff8d4910a`,
working tree sạch sau fast-forward từ `09d6f9a`. Giữ toàn bộ các sửa review đã
push bởi cộng tác viên; develop `036255ecd4b738f9e571cdb36dacdb49a25907f5`
đã là ancestor. Original checkout và private raw không bị sửa. Các kết quả Linux
ở phần F là lượt trước; lượt G dùng Python 3.14/Windows.

Review REQUEST_CHANGES và [maintainer clarification](https://github.com/nairyuuu/ad-weighted-graph/pull/258#issuecomment-6095666117)
chỉ ra hai authority gaps: I labels chưa chứng minh actual terminal capabilities,
và scenario reference vắng bị dùng như wildcard. Implementation đóng đúng các
boundary này, không mở numeric baseline mới hoặc thay search semantics.

### Các lựa chọn thực tế

| Vấn đề | Phương án đã cân nhắc | Lựa chọn triển khai và lý do/trade-off | Compatibility/hành vi | Code và kiểm chứng | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| Asset/event label không chứng minh admin vs session | Giữ labels; digest callable; typed required-state descriptor | `SemanticGoalDescriptor` chuẩn hóa necessary capabilities, canonical JSON/digest. Callable không có identity ổn định; typed requirements kiểm tra được trong search/replay | Declarative queries tự có descriptor, không cần packet theo path. Callable thêm chỉ narrow goal | `query.py::SemanticGoalDescriptor`, `is_success_state`; strong/weak goal regression qua ba entry points | implemented; pending A cross-review |
| Đúng I mapping do native provider đã chọn | Chọn lại mapping trong public layer; validate đúng selected provenance | Guard xác định mapping bằng native digest của mapping + source; kiểm tra descriptor, snapshot, goal ID, review reference. Native refusal chạy trước guard | Sai I vẫn giữ C/P và effort-only; không fallback hay cấp Pareto. Không thêm numeric consequence | `resolution_service.py::_impact_goal_guard`; spoofed vs legitimate session; native integrity regression | implemented; pending #249/#251 cross-review |
| Orchestration nhận callable không có typed guarantees | Từ chối mọi callable; chỉ tin caller labels; truyền typed descriptor và conjunction | Optional `semantic_goal` từ materialized query; enforce typed matches AND callable nếu có. Callable thuần giữ search/C/P, I unverifiable | Không blanket veto opaque query; typed goal + callable vẫn được rate I. Caller truyền descriptor để đạt parity API/CLI | `orchestration.py::generate_and_evaluate_attack_paths`; opaque/typed regression, public probe | implemented; pending A cross-review |
| Thiếu semantic scenario authority | Cấm mọi search; coi rating label là authority; chỉ từ chối scoped reuse | C/P/I scoped result refused với reason cụ thể; reviewed unscoped basis vẫn hợp lệ. Conflicting reference là input error | Không tự suy scenario. Preparation scoped không apply khi thiếu authority; C liên quan không chứng minh minimum bỏ sót prep | `_providers`, work-rule materialization; missing/conflicting/unscoped và unanchored preparation tests | implemented; pending A cross-review |
| Version public và migration | Đổi native contract; giữ output 1.0 với meaning mới; version public extension | Config/coverage public 1.1; descriptor 1.0. Native resolver/evaluator contract vẫn 1.0. Coverage schema đọc lịch sử 1.0 và yêu cầu fields mới cho 1.1 | Config 1.0 đọc được nhưng unbound I refused; explicit packets giữ nguyên. Asset-only required_predicates không override được goal | loader/schema; legacy automatic binding refusal, transport schema tests | implemented; pending A cross-review |

Coverage 1.1 thêm `semantic_goal` (descriptor/digest hoặc null cho callable thuần)
và `scenario_authority` (hai references, matched/absent, missing không wildcard).
Denominators C/P/I, canonical admission/rejection, passive closure và shared-work
dedup giữ như phần B/F. Không thêm coverage percentage, score tổng hợp hay numeric
defaults. Zero-action không tạo I/q; incomplete search vẫn không chứng minh
minimum toàn scope. Native refusal/integrity vẫn authoritative.

### Output ngắn từ regression thực thi

Cùng synthetic snapshot có AdminTo và CanRDP, ba generated paths mỗi goal.
Các giá trị dưới đây là **synthetic_test_only**, không là empirical evidence:

```json
{"case":"admin","paths":3,"C":{"required":2,"rated":2},"P":{"required":2,"rated":2},"I":{"required":1,"rated":1},"minimum_effort_value":1,"pareto_count":1}
{"case":"spoofed_session","paths":3,"C":{"required":2,"rated":2},"P":{"required":2,"rated":2},"I":{"required":1,"rated":0},"minimum_effort_value":1,"pareto_count":0,"reason_code":"out_of_scope","reason_detail":"semantic_goal_mismatch: reviewed I consequence binding"}
{"case":"reviewed_session","paths":3,"I":{"required":1,"rated":1},"minimum_effort_value":1,"pareto_count":1}
```

Các extracts lấy từ `goal_case`/public `run_attack_query`; regression còn so full
ranking/coverage với orchestration và hai subprocess CLI runs, validate schema,
chỉ loại block volatile `runtime`. Session hợp lệ nhận Low của riêng test mapping;
session giả labels admin không nhận High. C/P đủ không đồng nghĩa I đủ; I refused
không xóa semantic paths hay effort-only result.

### Handoff bổ sung

#250 đã nối typed goal authority với public rating boundary. A cần xác nhận
descriptor v1, exact consequence applicability và migration automatic I; #249
sở hữu policy equivalence, #259 baseline tương lai, #256/#247 numeric review.
Không tự đóng các quyết định numeric đó. #251 cần cross-reproduce strong/weak
goals, scoped/unscoped missing authority và exact-head probe mới. Historical #243,
Week 3 packets và #207/#212 scoring oracle vẫn là regression authorities.
Các lệnh/revision/kết quả lượt G được bổ sung sau khi chạy trên committed source;
không suy CI PASS từ kết quả local.

### Bằng chứng cuối của lượt G

Windows, Python **3.14.7**, dependencies theo `requirements-tests.txt`;
`PYTHONUTF8=1`. `python` trong bảng là interpreter của venv repository. Full suite
chạy trên tracked tree sạch; report mới chưa stage cho tới khi full suite kết thúc.

| Case | Command/test | Expected | Actual | Revision | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| Public goal/scenario binding, schema, native regressions | `python -m pytest -q tests/test_public_rating_integration.py tests/test_week4_query_materialization.py tests/test_query_boundary_regressions.py tests/test_rating_resolver_impact_equivalence.py tests/test_likelihood_catalog_v1.py` | Không spoof admin I; legitimate session I; C/P/effort giữ khi I refused | 158 passed, 3 skipped, exit 0; toàn bộ được chạy lại trong full suite | working tree trước `bfc3806`; full tại `776f449` | PASS synthetic; private cases trong suite này SKIPPED |
| Full regressions, Week 3, #207/#212, demo shell | `python -m pytest -xq` | Không regression | **2537 passed, 17 skipped, 48 subtests passed**, exit 0, 1137.33s | `776f4493402ee50284c242666adeba226b8a4462` | PASS local |
| Historical semantic oracle / determinism | `python -m scripts.research.week4_acceptance_runner --check-determinism --output reports/research/issue250-review-acceptance-manifest-v2.json` | Digest independent oracle không đổi; pending không thành PASS | 36 PASS, 0 unexpected, 1 NOT EXECUTED, 1 BLOCKED; exit 0; digest `sha256:3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d` | `bfc3806864e0bc450739c1534329596bfdd5dc1b` | PASS các cases đã execute; giữ hai prerequisite gaps |
| Public API/CLI/orchestration; synthetic deterministic | `python -m scripts.research.issue250_public_probe --output reports/research/issue250-goal-binding-public-probe-v3.json --seamless-raw <manifest-verified-private-raw-dir>` | Complete/shared/missing/effort-only/context/pending/production/integrity đúng contract | 8 synthetic cases PASS; exit 0 toàn runner; integrity case có CLI exits [1,1], các cases khác [0,0]; API/orchestration bằng CLI trên bảy cases valid | `776f4493402ee50284c242666adeba226b8a4462` | PASS synthetic_test_only |
| Actual dataset frozen #243 semantic controls | Cùng public probe, bảy `frozen243_*` cases | Giữ exact frozen expectations, known-false/unknown/recovery/cap | **7/7 PASS**, mỗi case hai CLI runs [0,0]; chỉ bỏ block runtime khi so deterministic | `776f4493402ee50284c242666adeba226b8a4462` | PASS actual private dataset conditional prediction; không phải numeric empirical acceptance |
| Source provenance của các CLI runs | Đối chiếu `reproducibility.revision` và `tracked_changes` trong 28 outputs hợp lệ | Cùng executed HEAD, không dirty source | 28/28 cùng `776f449...`, tracked_changes=[]; exit 0 | `776f4493402ee50284c242666adeba226b8a4462` | PASS |
| Static/contract checks | `python -m ruff check --no-cache .`; `python -m ruff format --check .`; `python -m yamllint .`; `python scripts/check_repository.py`; `python scripts/check_contract.py`; `git diff --check` | Không lint/schema/privacy drift | PASS, exits 0; 406 files formatted, contract + 2 synthetic fixtures validated | committed source `bfc3806`/`776f449`; artifacts/docs kiểm lại trước handoff | PASS local |
| Compose | `docker compose --env-file .env.example --profile graph config --quiet` với validation placeholder password | Config hợp lệ, không start services | Exit 0 | `bfc3806864e0bc450739c1534329596bfdd5dc1b` | PASS local |

17 skips của full suite gồm 15 private/local dataset prerequisites theo đường
dẫn mặc định và 2 filesystem cases không áp dụng trên Windows. Raw SEAMLESS đã
có ở original checkout, được cung cấp tường minh cho probe riêng ở trên; điều
này không biến các private provider/telemetry tests đã skip thành executed.
Không có telemetry campaign hoặc production numeric acceptance mới.

Lượt probe đầu bị dừng vì đã commit manifest evidence trong khi CLI chạy;
không dùng lượt đó làm bằng chứng. Runner được chạy lại hoàn chỉnh tại HEAD cố
định `776f449`, không sửa generated report bằng tay. Report v3 chỉ giữ sanitized
counts/programs/reason codes; full outputs/private identities nằm ở ignored local
directory. Manifest historical và frozen expectations không đổi.

Extracts từ report v3 tại revision trên:

```json
{"case":"missing","paths":3,"C":{"required":2,"rated":0},"P":{"required":2,"rated":0},"I":{"required":1,"rated":0},"minimum_effort":null,"pareto_frontier":[]}
{"case":"effort_only","paths":3,"C":{"required":2,"rated":2},"P":{"required":2,"rated":0},"I":{"required":1,"rated":0},"minimum_effort":1,"minimum_proven":true,"pareto_frontier":[]}
{"case":"context_refused","P":{"required":2,"rated":1},"gap":{"dimension":"P","disposition":"refused","reason_code":"out_of_scope"}}
```

`minimum_proven` ở effort-only nói về C trong finite semantic scope, không là
risk/Pareto guarantee. Pending-production C có `explicit_unrated_disposition`,
không activate; synthetic-production C/P/I có `prerequisite_gate_refusal`.
Không gộp hai dispositions đó thành một missing-basis fallback.

Remote CI của head trước vẫn FAILURE trước runner: annotation đọc trực tiếp
xác nhận billing/spending-limit refusal. Lượt remote của head handoff phải đọc
riêng sau push; local PASS không thay CI hoặc A review. Các quyết định descriptor
1.1, exact consequence binding và scoped/unscoped authority vẫn pending A
cross-review; không merge hoặc đóng acceptance gates trong lượt này.

## H. Sửa blocker empirical P — 10/10/2026

Review `5478640229` trên head `193a8d2b408a0865d423cc015eaa11f6842e2259`
phát hiện `likelihood_guard` chỉ gắn vào `ReviewedScenarioLikelihoodProvider`.
`EmpiricalLikelihoodProvider` cũng dùng scenario ID trong lookup key và manifest
`supported_scenario_ids`; rating scope do caller tự khai không phải semantic
scenario authority. Prototype quarantine hiện hành không chứng minh nhánh
reviewed empirical an toàn.

Sửa tối thiểu: gắn cùng guard vào cả hai P providers. Guard chỉ kiểm kết quả
`RATED` sau native applicability/governance, giữ nguyên native refusal và provider
precedence. Khi semantic query thiếu scenario reference, P scoped bị refused với
`missing_evidence` / `scenario_authority_missing`; không veto search, không xóa
C/I unscoped hoặc effort-only Min-Effort. Scenario khớp vẫn được dùng evidence;
scenario xung đột vẫn là input error. Không đổi contract/version, estimator,
catalogs, numeric defaults hoặc release status.

Regression `test_review_eligible_empirical_p_requires_semantic_scenario_authority`
chạy real estimator với 25 independent observations (20 success / 5 failure),
manifest review-eligible và đúng ordered AS-REP prefix. Đây là dữ liệu dựng trong
test, **không** phải telemetry thật hay evidence được duyệt để release. Positive
control thực sự đạt `RATED` từ empirical provider nên quarantine/unsupported
không che lỗi. Trước sửa, negative control fail vì P vẫn có một rated request;
sau sửa, cùng record bị refusal khi thiếu semantic scenario. Paths feasible,
C/I và minimum effort giữ nguyên. API/CLI/orchestration cùng ranking result;
CLI coverage/transport được validate schema; conflicting scenario có regression.

Focused local trên Python **3.14.8/Linux**, `requirements-tests.txt`:
`python -m pytest -q tests/test_public_rating_integration.py
tests/test_rating_p_provider_chain.py tests/test_empirical_qi_estimator.py` đạt
**95 passed, 1 skipped** (private SEAMLESS prerequisite), exit 0. Ruff lint/format,
yamllint, contract và repository checks đều PASS. Bằng chứng lượt H thuộc diff
trên baseline `193a8d2`; không thay evidence lịch sử ở phần G hay remote CI.

Full suite lượt đầu dừng ở kiểm checksum manifest v2: source resolver đã đổi nên
pin cũ không còn mô tả implementation hiện hành (2,401 passed trước điểm dừng).
Không sửa checksum/report lịch sử bằng tay. Sinh mới
`reports/research/issue250-review-acceptance-manifest-v4.json` bằng
`python -m scripts.research.week4_acceptance_runner --check-determinism --output
reports/research/issue250-review-acceptance-manifest-v4.json` trên source commit
**`cc5a663b6648259417f8d501d34a22e0e87111db`**, `checkout_dirty=false`,
`dirty_pinned_files=[]`. Hai test kiểm pins/check-out autocrlf trỏ bản v4;
manifest v2 và các expectations/oracles cũ giữ nguyên bytes.

Runner đạt **36 PASS, 0 unexpected failures, 1 NOT EXECUTED, 1 BLOCKED**, exit 0.
Semantic determinism digest vẫn là
`sha256:3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d`.
Hai prerequisites thiếu không được chuyển thành PASS; manifest mới không thay
human review hoặc numeric acceptance.
