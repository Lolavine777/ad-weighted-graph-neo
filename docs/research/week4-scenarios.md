# Ca Week 4 và oracle độc lập - gói A2 v1.0.0

## Current-state amendment - 09/10/2026

A2 core #214 và public-query mapping #225 đã accepted; core/CLI/Kerberoasting/AS-REP/RBCD hiện đã merge.
Các mục pending-interface/A2-review/deferred trong snapshot gốc phía dưới là lịch sử.
[Freeze SEAMLESS mới](week4-seamless-scenario.md) consume accepted APIs, nguồn X khác asset C0, initial request capability tách host control/usable identity.
Independent expected được commit trước public execution; một generated four-step program đạt final asset dưới assumptions, RAW/missing/false-veto/OFF/capability/cap controls khớp.
Không sửa oracle core hoặc harness/schema B; không ép ba techniques vào cùng đường, không chấm numeric basis thiếu.
#206 còn OPEN chờ B cross-review và disposition handoff; #239/#208 tiếp nhận same frozen inputs/results và human-independent reproduction.

Ngày 06/10/2026; owner TTS A (@Lolavine777); reviewer TTS B (@nairyuuu).
Chỉ thực hiện [#206](https://github.com/nairyuuu/ad-weighted-graph/issues/206), từ `develop@15720560cfc2ea03a3350335042f704751c83253` sau merge #209 và nghiệm thu tài liệu #205.
Đọc cùng [Week 4 plan](../reports/week4-plan.md) và [query contract](week4-query-contract.md).
Gói này là đầu vào/kỳ vọng để review, chưa là nghiệm thu runtime #208 hoặc hoàn tất Week 4.
B đã nhận bàn giao kế hoạch; mapping máy/danh tính, goal DA và xử lý assumption xung đột vẫn là dependency triển khai.

## Audit reuse và delta

Audit source/tests/golden tại baseline trên; kết quả chạy mới ghi trong worklog, không lấy số liệu lịch sử làm bằng chứng hiện hành.
Không sửa expected nền, schema, harness, parser, catalog, engine hoặc ratings của B.

| Yêu cầu #206 | Ca/test hiện có | Phần tái sử dụng | Gap và disposition |
| --- | --- | --- | --- |
| Source=target / initial goal | `no-route/initial-success`; `test_initial_success_is_zero_action_with_unique_target`; `test_structural_queries_are_directed_deterministic_and_cycle_safe` | Zero-action goal và topology nguồn=đích | Đủ nền; không thêm ca trùng |
| Nhiều đường | `two-routes/positive`, `membership-cycle-diamond/positive`; `test_search_accepts_remaining_valid_alternative` | Graph, facts, owner IDs, cơ chế alternative | Nền chỉ kiểm causal alternatives; delta W4-M kiểm toàn bộ exact programs và trạng thái |
| Cạnh song song, cycle/nesting | `test_shortest_path_uses_edge_local_additive_costs_and_exact_parallel_edge`, `test_semantic_cycle_is_finite_and_obeys_required_expansion_budget`; `membership-cycle-diamond` | Multigraph structural và finite stateful scope | Đủ nền; không nhân bản graph/test |
| Ít bước nhưng công sức lớn hơn; ties | Dijkstra additive tests; Week 3 whole-path/ranking tests | Dijkstra giữ riêng; whole-path evaluator, work-unit model ở #207 | Manual ledger W4-E/T dưới đây; chưa có numeric ranking binding mới được B nhận |
| Đổi nguồn / capability / context | `acl-auth-host/no-foothold`, `session-material/without-host-admin`; `test_scoped_assumptions_and_identity_do_not_authorize_other_context`, `test_wrong_scoped_initial_identity_cannot_use_inherited_right` | Mất foothold/host admin và sai context đã kiểm | W4-I thêm initial entitlement và host-only trên graph nhiều đường; X→Y qua public query interface pending B |
| Đổi target cùng graph | Nền no-route ở graph khác; success-state vượt node reachability đã kiểm | Predicate/target field hiện có | W4-TARGET đổi riêng target trên graph W4-M; public machine query vẫn pending |
| DA checkpoint khác asset success | `acl-auth-host/winrm-host_admin_mapping-false`, `...-missing`; `test_terminal_success_state_matches_reviewed_goal_not_node_reachability` | Trạng thái usable identity/membership trước asset; asset gate false/unknown | W4-C có oracle semantic dưới đây; mapping role G-DA và goal DA pending, không gọi `Admins` synthetic là DA đã resolve |
| Missing → assumption → false veto | `psremote-command/ps-winrm_available-missing`, `/positive`, `/ps-winrm_available-false`; `test_known_false_snapshot_veto_and_contradictory_runtime_rejected`; Week 3 negative manifest | U/A/F ở evaluator; constructor reject contradiction và snapshot false veto | W4-G reuse đúng ba ca; ledger rejected assumption + blocked qua query interface pending B; exception riêng chưa đủ |
| Missing structural khác unknown/unsupported | `test_direction_and_kind_are_not_interchangeable`, `test_removing_causal_owner_prevents_host_success`; Week 3 structural-missing/telemetry-missing | Evidence view và designated decision/exclusion | Reuse; không nâng unknown thành cạnh canonical, không gọi unsupported là observed false |
| No-path complete và truncation | `no-route/positive`; `test_truncation_is_incomplete_and_harness_rejects_no_path_claim`; structural cap tests, semantic cap tests | Complete no-path và reject incomplete oracle | W4-N reuse; W4-P/E/S khai báo các cap riêng trên W4-M, probe bằng API hiện hành, không sửa golden schema để chứa truncated |
| Scoring độc lập reachability | Week 3 missing-basis/binding, `test_whole_path_evaluator_receives_stateful_path_and_returns_model_value_unchanged` | Semantic generator trước numeric evaluator | Chi tiết C/P/I, sensitivity và binding thuộc [#207](https://github.com/nairyuuu/ad-weighted-graph/issues/207); không chấm mới tại đây |
| SEAMLESS và replay | `seamless.json`, `attack_scenarios_seamless.py`, Week 3 acceptance manifest | Snapshot, accepted Source B program, raw-to-canonical trace | Recheck raw và trace nền; Week 4 machine/DA queries pending mapping; CE/roasting deferred |

## Gói đầu vào/kỳ vọng và digest

[week4-v1.json](../../tests/fixtures/attack_scenarios/week4-v1.json) dùng nguyên schema golden `1.0.0` của [runner hiện hành](../../scripts/research/attack_scenarios.py).
Package version là `v1.0.0`; `schema_version` và `scenario.version` giữ đúng giá trị được validator hiện hành nhận.
[week4-v1.sha256](../../tests/fixtures/attack_scenarios/week4-v1.sha256) là manifest SHA-256 của byte file, kiểm bằng `sha256sum -c` từ root repo.
Manifest pin expected suite, tài liệu oracle này, test consumer, graph tái sử dụng, golden nền, contract/catalog, query handoff, harness và SEAMLESS bindings/release/plans/raw manifest.
Graph digest trong suite dùng canonical JSON SHA-256 của runner; không nhầm với file-byte SHA-256 trong manifest.
Graph `two-routes` có canonical digest `sha256:01ce6844293f3d5532a132c3c3a00799e2c1a5390003bd45f89b1068536f2c79`.
Giá trị chính thức phải đọc từ `graphs.two-routes.digest` trong suite và kiểm với runner; nếu bản handoff thay đổi thì review oracle, tăng package version và tạo manifest mới, không chỉ refresh hash để bỏ qua mismatch.
Không tạo schema scenario manifest mới hoặc sửa schema/harness của B.
Các ca pending được mô tả semantic tại đây và được pin bằng digest tài liệu; không serialize thành executable request hoặc freeze interface chưa accepted.

Delta có hai scenario với tổng bốn biến thể; dùng nguyên graph `graphs/two-routes.json`, aliases và evidence của golden nền.
`w4-two-routes-exact` gồm `positive`, `initial-entitlement`, `host-control-only`; `w4-other-target/positive` đổi riêng target.
Không yêu cầu input cung cấp ordered path: `steps`/`acceptable_paths` là oracle của harness; generator nhận graph/state/facts/target/owners và tự sinh paths.
Không đưa `steps` hoặc `acceptable_paths` vào query production như đầu vào tìm đường.
Caps reuse `max_paths=1000`, `max_steps=12`, `max_expansions=100000`; chúng đủ cho scope nhỏ được duyệt ở dưới, chưa là caps accepted cho query interface mới.
Các facts true đều là `declared_assumption` synthetic, scope `two-routes:fixed-snapshot-window`; không có runtime exploit observation hoặc xác suất thành công mặc định.

## Oracle đầy đủ trên fixture nhỏ

Trong phần này U = Alice, G = Admins, C0 = Host, X = OtherHost là alias của fixture synthetic hiện có.
G chỉ là Group được khai báo trong fixture, không có binding role DA.
Initial actor U và `control(U)` là abstraction legacy accepted của fixture; không được suy đó là public query source Computer X hoặc initial `usable_identity(U,H0)`.
Auth context của fixture này là `null`; toàn bộ mapping machine/identity Week 4 giữ ở mục pending.

Graph có đúng ba cạnh trong scope: U→AdminTo→C0, U→MemberOf→G, G→AdminTo→C0; các node còn lại không có cạnh.
Owner subset có đúng `obtain_admin_execution_on_host` và `propagate_group_entitlement`.
Định danh hành động là tuple `(technique_id, actor, source, target)` cùng edge ID trong suite; không gộp direct với inherited vì cùng target/state effect.
Mỗi action key chỉ dùng một lần trong một branch, state đơn điệu, không actor-switch; dừng chương trình thành công tại lần đầu đạt target và required state.
Đây là scope finite của generator hiện hành, không là mọi attack program ngoài đời.

| Ký hiệu / step | Request theo alias | Structural support | Prerequisites và effect |
| --- | --- | --- | --- |
| D / `direct` | `(obtain_admin_execution_on_host,U,U,C0)` | Cạnh U→AdminTo→C0, edge ID `8f30ad…` trong suite | U controlled/enabled, source chính U, admin channel + authentication true; thêm `admin_control(C0)` |
| M / `member` | `(propagate_group_entitlement,U,U,G)` | Cạnh U→MemberOf→G, edge ID `e2cd3c…` | U controlled/enabled, security group + membership usable true; thêm `effective_member(U,G)`, không control G |
| I / `inherited` | `(obtain_admin_execution_on_host,U,G,C0)` | Cạnh G→AdminTo→C0, edge ID `96f8b4…` | Phải có effective membership của U ở G; cùng admin/auth gates; thêm `admin_control(C0)` |

Gọi S0 = `{control(U)}`, S1 = S0 + `{effective_member(U,G)}`, S2 = S0 + `{admin_control(C0)}`, S3 = S1 + `{admin_control(C0)}`.
Các field không nêu đều rỗng, bao gồm usable identity, reset control, credential material, permission và relationship_added.
State equality không xóa path identity: M/D và M/I kết thúc cùng S3 nhưng là hai programs khác.

| Ca | Initial / target / thay đổi | Toàn bộ allowed successful programs | Toàn bộ reachable states / terminal states | Expected verdict |
| --- | --- | --- | --- | --- |
| W4-M | S0 → C0; graph/facts baseline | D; M/D; M/I | Reachable `{S0,S1,S2,S3}`; terminal `{S2,S3}` | Success dưới assumptions; exact set, complete trong scope |
| W4-I/E | S1 → C0; chỉ thêm initial effective membership | D; I; M/D; M/I | Reachable `{S1,S3}`; terminal `{S3}` | Success; tập programs thay đổi theo initial capability |
| W4-I/H | `{admin_control(X)}` → C0; không control/usable U | Không có | Chỉ initial state; terminal success rỗng; D/M blocked `actor_controlled`, không apply effects | Complete no-path trong scope; host control không tự cấp identity |
| W4-TARGET | S0 → X; chỉ đổi target/required state | Không có | Reachable `{S0,S1,S2,S3}`; success terminal rỗng | Complete no-path tới X; có quyền C0 không chứng minh quyền X |

Chứng minh completeness W4-M: ở S0 chỉ D hoặc M có thể advance; I chưa được source-authorized.
D đạt goal nên dừng; M tới S1, M không được reuse, chỉ D hoặc I còn khả thi, cả hai đạt goal và dừng.
Không có cạnh/owner khác hoặc identity activation; do đó ba programs và bốn states ở bảng là toàn bộ tập trong scope.
W4-I/E bắt đầu S1 nên D/I có thể kết thúc ngay; M vẫn có thể được evaluated một lần với effect đã có, rồi D/I kết thúc.
Không loại history M chỉ vì state effect là no-op; action reuse policy hiện hành cho phép lịch sử này, nên phải giữ cả bốn programs.
W4-I/H không có prerequisite actor capability của D/M; I cũng không có membership, không branch nào advance được.

W4-TARGET không dừng ở C0 vì target là X; mọi history hợp lệ gồm ε, D, M, D/M, M/D, M/I, D/M/I, M/D/I, M/I/D.
I phải sau M; D/M/I mỗi action tối đa một lần; đây là mọi prefix của ba hoán vị hợp lệ thỏa M trước I.
D hoặc I thứ hai có thể không thêm state mới nhưng action key khác; vẫn là valid history trong scope.
Các histories kết thúc không còn action unused là D/M/I, M/D/I, M/I/D, đều S3 và đều không đạt target X.
Độ sâu tối đa 3, nhiều nhất 9 histories kể cả ε và tối đa 27 evaluations nếu xét cả ba requests tại mỗi history; caps baseline dư cho tập này.
`required_reachable` trong schema là projections; oracle equality toàn bộ states là bảng trên, không suy completeness chỉ từ một count hoặc tập projections.

## Oracle công sức và ties, độc lập với reachability

Ledger dưới đây là giá trị synthetic do A khai báo để kiểm phép tính, chưa được B review như numeric ranking input và không là rating/production parameter.
Effort chỉ tính sau khi program đủ điều kiện theo quyền, state, facts và owner scope; không dùng C/P/I để quyết định transition khả thi.
Dùng tổng công việc duy nhất theo ID, không tính cùng work unit hai lần trong một program; các programs khác vẫn được đánh giá riêng.
M là passive entitlement nên không gán công việc tấn công mới cho việc đi qua cạnh membership.

| Work ID | Ranh giới công việc giả lập | D | M | I | E: giá trị | T: giá trị |
| --- | --- | --- | --- | --- | --- | --- |
| `w-auth-context` | Chuẩn bị một context xác thực dùng chung trên cùng U/C0 | Có | Không | Có | 1 | 1 |
| `w-direct-admin` | Thao tác admin của nhánh direct sau context | Có | Không | Không | 4 | 1 |
| `w-inherited-admin` | Thao tác admin của nhánh inherited sau context | Không | Không | Có | 1 | 1 |

| Program W4-M | Union work IDs | E: tổng effort | T: tổng effort |
| --- | --- | --- | --- |
| D | `{w-auth-context,w-direct-admin}` | 5 | 2 |
| M/D | `{w-auth-context,w-direct-admin}` | 5 | 2 |
| M/I | `{w-auth-context,w-inherited-admin}` | 2 | 2 |

Minimum E là 2 với đúng program M/I, dù D chỉ có một bước và M/I hai bước.
Minimum T là 2 với tie set `{D,M/D,M/I}`; history dư M vẫn thuộc scope nên không được âm thầm xóa khỏi tie set.
W4-I/E có programs D, I, M/D, M/I: minimum E = 2 với `{I,M/I}`, minimum T = 2 với cả bốn programs.
W4-I/H và W4-TARGET không có goal-success program nên minimum effort tới goal là không xác định, không phải 0.
History M/D/I của W4-TARGET dùng `w-auth-context` một lần: E = 1+4+1 = 6, không phải 7; đây là ledger cho history hợp lệ, không là kết quả thành công tới X.
Nếu effort basis thực tế thiếu thì vẫn giữ semantic paths và `unrated`, không dùng các số synthetic này để lấp basis.

Dijkstra với graph `unit` chọn structural U→C0, cost 1; topology qua G có cost 2.
Nó không biết context/work reuse hay passive membership; không gọi cost 1 là effort 1 hoặc dùng topology optimum thay stateful oracle E.
Nếu muốn kiểm additive custom costs thì phải dùng bảng edge-local riêng và nêu đó là bài toán khác.
[#207](https://github.com/nairyuuu/ad-weighted-graph/issues/207) sở hữu chi tiết C/P/I, full-history rating bindings, shared work, ordering/Pareto, sensitivity và disposition thiếu basis.
A2 bàn giao ledger này làm expected calculation để #207/B nối vào model hiện hành; chưa tạo action binding/parameter release mới hoặc claim numeric evaluator đã chạy delta.

## U/A/F và coverage caps tái sử dụng

| Ca | Nguồn/đích và input | Allowed action / terminal | Expected verdict / evidence |
| --- | --- | --- | --- |
| W4-G/U | U→C0; reuse `psremote-command/ps-winrm_available-missing`, authentication true, bỏ đúng winrm_available | `ps` attempt indeterminate; không additions; reachable initial, không remote execution/admin | Indeterminate; diagnostic winrm_available unknown |
| W4-G/A | Cùng query; reuse `/positive`, assumption true đúng U/C0/scope, rationale/evidence trong suite | Program `ps`; terminal initial + remote_command_execution(U,C0), không admin_control | Applicable dưới assumption; không observed exploit success |
| W4-G/F | Cùng query; reuse `/ps-winrm_available-false`, giữ false authoritative | `ps` blocked, không additions; không remote execution/admin | Blocked; query phải giữ riêng attempted assumption true bị reject/conflict; bước query này pending B |
| W4-N | Reuse `no-route/positive`, owner set rỗng được khai báo, không unresolved gates | Chỉ initial, không successful programs | Complete no-path chỉ scope fixture, không nói AD thực không có đường |
| W4-P | W4-M baseline, chỉ `max_paths=1` | Generated subset của oracle; cap không là Top-1 | Truncated, `path_limit_reached`; không claim optimum/no-path |
| W4-E | W4-M baseline, chỉ `max_expansions=1` | Chưa duyệt hết các requests đã biết | Truncated, `expansion_limit_reached`; lưu counter/attempts |
| W4-S | W4-M baseline, chỉ `max_steps=1` | D có thể được tìm; M còn continuation D/I ngoài cap | Truncated, `step_limit_reached`; tìm được D không chứng minh minimum E |

Schema golden hiện hành chỉ nhận finite complete expected outcomes; runner cố ý reject truncated.
P/E/S reuse `SearchBudget` và `generate_attack_paths` trong [test consumer A2](../../tests/test_week4_scenarios.py), không ghi false no-path expected vào suite hoặc sửa schema/harness để nhận partial.
False/unknown requests giữ diagnostics và không apply success effects; canonical graph/digest giữ nguyên ở cả U/A/F.
Trong F, không truyền hai facts trái giá trị vào `RuntimeContext`: constructor hiện reject contradiction, không tự tạo blocked/conflict query report.
B cần mapping ledger trước evaluation để giữ false authoritative và ghi rejected assumption riêng; chỉ constructor exception không đáp ứng kỳ vọng query Week 4.

## Semantic cases pending B, chưa freeze executable interface

Các dòng sau là input/expected semantic requirements được pin trong tài liệu, không là tên API/action mới.
Reuse scenario/owner/state vocabulary accepted; chỉ chuyển thành executable package sau B nhận mapping và query contract.

| Ca / dependency | Input để B map | Allowed programs/states và expected verdict độc lập | Evidence / việc chưa có |
| --- | --- | --- | --- |
| W4-X/S: thay nguồn | Cùng canonical graph; Computer X→Y, giữ principal U, initial capability, H0, horizon/facts; chưa tạo X→U edge | B phải khai báo source có ảnh hưởng thế nào tới auth/network/context; graph nền hiện không có host-specific evidence để quyết định paths đổi chỉ từ X→Y | Pending machine/source binding; chưa bịa expected path khác nếu source chưa có causal constraint |
| W4-X/I: bỏ usable identity | X controlled giữ nguyên; bỏ duy nhất usable(U,H0), không còn control(U) được khai báo ngầm | Không dùng quyền U từ host control X; không actor-switch bằng identity chưa active; blocked hoặc conditional chỉ khi có supported acquisition branch riêng | Reuse W4-I/H và scoped identity tests; public interface pending |
| W4-X/H: sai context | U vẫn usable ở H0; request H1 khác H0, các input khác giữ nguyên | Các bước đòi authenticated H1 bị blocked; không kế thừa usable U/H0 sang H1 | Reuse scoped context tests; pending machine/auth mapping |
| W4-DA: goal DA | Synthetic group G cần được B bind role G-DA; fixture `acl-auth-host` chain tới Bob usable/entitled; goal usable(V,H0) và effective(V,G-DA) | Trước asset step, expected prefix helpdesk/dacl/reset/authenticate/admins; state gồm reset control, usable V/H0, effective membership V/G; chưa admin C0 | Prefix/state đã khai báo trong suite; không lấy display name Admins làm DA; DA goal predicate/terminal rule pending |
| W4-C/F: checkpoint đạt, asset denied | Reuse `acl-auth-host/winrm-host_admin_mapping-false`; giả sử role binding DA được B nhận, các gates trước giữ baseline | Checkpoint state có usable V/H0 + effective V/G-DA; winrm blocked host_admin_mapping; final asset-success set rỗng, không admin C0 | Asset negative oracle đã có; report hai goal/DA mapping pending |
| W4-C/U: checkpoint đạt, asset missing | Chỉ bỏ host_admin_mapping, reuse `...-missing` | Cùng checkpoint; asset attempt indeterminate; không admin C0, không gọi no-path complete khi còn gate chưa biết | Existing missing oracle; pending combined checkpoint/asset report |
| W4-G/conflict | Observed/blocked fact winrm_available false tại U/C0; attempted assumption true cùng scope giữ trong rejected ledger | False vẫn block `ps`, state không advance; rejected assumption có provenance/reason; không overwrite fact | Query resolution/ledger interface pending B; existing schema cấm duplicate fact |
| W4-SCORE/REPLAY | Same generated paths, exact bindings/basis nếu có, package/caps/head/runtime/policy pins | Missing rating giữ unrated; missing binding có exclusion; hai lượt actual phải so digest/trace, không đổi expected theo actual | #207 cung cấp basis, #208 chạy actual; không dùng supplied candidate replay như generated query |

AS-REP/Kerberoasting và CE ngoài core gói này theo #205 đã accepted.
Không hardcode future roast/recover/activate APIs, không dùng reset_password_control làm alias recovered secret; không gọi deferred extension đã triển khai hoặc được mentor nhận.
Không thêm CE converter/parity gate hoặc công việc #207/#208 vào PR #206.

## SEAMLESS: trace thật và phần chưa chạy

Reuse [binding accepted](../../tests/fixtures/attack_scenarios/seamless.json) và [runner raw-to-canonical](../../scripts/research/attack_scenarios_seamless.py), public chỉ gọi Source B, V, G-DA và C0 theo aliases của accepted input.
Snapshot raw pin `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`, gồm sáu file; manifest chứa file-byte digest/size, collection time chưa biết.
Binding integration lịch sử pin graph digest `sha256:41fdff96d00562c0ff096efcc1b585c189e707c8b8f61b199b6197bc7feceae0`; runner này reject graph current head vì metadata `code_version` cũng tham gia digest.
Parser CLI chính thức tại baseline #206, với created-at/time-policy cố định của handoff, tạo graph digest `sha256:09b117c2db7c4a6433aea0ca83a47190112099eb492f14cda50a1869f7c41561`; không sửa metadata để giả pin lịch sử hoặc cập nhật binding của B.
Fresh trace current dùng `raw_edge_trace` hiện hành trên graph mới và reviewed Source B candidate, cùng current Week 3 acceptance CLI; không gọi narrow pinned runner đã PASS khi chính nó reject input.
Full private identities, mapping, runtime facts và trace output giữ local trong ignored directories; không commit raw, recovered secrets hoặc full output.

Expected causal program nền là reset quyền User → activate reset identity đúng H0 → effective membership DA → declared host mapping + WinRM gates → admin_control(C0).
Raw ACL reset, membership và Group→Computer support được kiểm theo exact reviewed locators của release; capability activation phải truy về step reset, không raw edge giả.
DA role dựa trên ID/role/raw membership binding của accepted release, không display name; host authorization còn cần declared mapping và runtime assumptions.
Các runtime gates trong scenario positive không là telemetry chứng minh khai thác thành công; raw trace chỉ chứng minh quyền/structural support và provenance.
Không dùng C/P/I để kiểm reachability trong runner này.

Raw local đã verify khớp manifest trong lượt #206; current raw trace xác minh ba structural bindings và fresh Source B acceptance CLI đạt trong scope accepted.
Đây là bằng chứng tái sử dụng nền, không là query machine-source/goal DA Week 4 mới; worklog ghi commands, digest và giới hạn.
Machine source X/Y và mapping initial usable identity/DA goal Week 4 chưa được B triển khai/nhận, nên SEAMLESS query Week 4 mới ghi **chưa chạy, pending mapping/interface** dù raw snapshot nền có sẵn.
Nếu checkout khác thiếu raw hoặc private binding thì ghi **chưa chạy, thiếu prerequisite**, không dùng synthetic thay dữ liệu thật hoặc ghi trace PASS.
CE và roasting tiếp tục deferred; không có claim CE parity, extension success hoặc Min-Effort toàn SEAMLESS.

## Nguồn cơ chế và ranh giới

[AdminTo của SpecterOps](https://bloodhound.specterops.io/resources/edges/admin-to) hỗ trợ diễn giải quyền local administrator.
[Access tokens của Microsoft](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-tokens) hỗ trợ tách membership snapshot với authorization context hiệu lực.
[WinRM security của Microsoft](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/winrm-security) hỗ trợ tách authentication, user context và endpoint access; không suy remote session thành host admin.
Các nguồn trên được đọc lại ngày 06/10/2026; nguồn không cung cấp số effort synthetic của oracle hoặc chứng minh runtime outcome.
Các claim reset/identity/DA mapping và raw locators reuse [nguồn #175](attack-scenarios.md#primary-evidence-claim-mapping) và [research #203](attack-semantics-predictive-state-transitions.md), không tạo claim kỹ thuật mới về roasting.

## Disposition tiêu chí nghiệm thu #206

| AC | Đầu ra A2 hiện có | Gate còn lại |
| --- | --- | --- |
| Reachable-state/path sets và minimum effort độc lập | Full finite proof, exact programs/states, manual ledger E/T; consumer kiểm equality | B duyệt oracle/basis; DA executable goal còn pending |
| Reuse/gap và expected-data được B review | Ma trận reuse/gap và suite schema hiện hành, chỉ delta | B cross-review chờ PR; không đánh dấu AC này accepted |
| False/unknown/structural-missing/unsupported riêng | Bộ nền, W4-G và coverage/disposition; graph không thêm unknown edges | Query conflict normalization/ledger pending B |
| Explicit synthetic assumptions và provenance thật | Typed facts/rationale/evidence ở suite; raw snapshot và ba trace bindings current | Mapping machine queries mới chưa có; không observed exploit success |
| SEAMLESS handoff, prerequisite thiếu ghi chưa chạy | Snapshot/release/plans/binding pins và raw trace current, aliases | Week 4 mapping/interface chưa nhận nên query mới chưa chạy; roasting deferred |
| Reachability không phụ thuộc C/P/I | Oracle quyền/state trước effort; ledger synthetic tách riêng | #207/B nối numeric bindings, giữ unrated nếu thiếu |
| Source, asset boundary và immutable input/expected | Primary sources, package version, canonical/byte digests và SHA manifest | B review package freeze; raw local giữ checksum-pinned, không commit |
| Checks/CI và cross-review; nối harness/A4 | Delta consumer trong CI hiện có, lệnh tái lập và worklog | Remote CI/B approval sau mở PR; actual query/demo #208 pending |

## Tái lập và bàn giao review

Từ root repo, dùng Python trong `.venv` và manifest expected đã pin trước khi đọc actual:

```bash
sha256sum -c tests/fixtures/attack_scenarios/week4-v1.sha256
.venv/bin/python -m scripts.research.attack_scenarios \
  --suite tests/fixtures/attack_scenarios/week4-v1.json \
  --output reports/generated/issue206/delta-1.json
.venv/bin/python -m scripts.research.attack_scenarios \
  --suite tests/fixtures/attack_scenarios/week4-v1.json \
  --output reports/generated/issue206/delta-2.json
cmp reports/generated/issue206/delta-1.json reports/generated/issue206/delta-2.json
.venv/bin/python -m pytest -q tests/test_attack_scenarios.py \
  tests/test_attack_scenarios_seamless.py tests/test_engine.py \
  tests/test_week3_engine_acceptance.py tests/test_week4_scenarios.py
```

Đối chiếu exact paths/edge/action identity, reachable-state equality bảng oracle, terminal goal, graph immutability và diagnostics; report count riêng không đủ.
Commands dựng graph/acceptance nền dùng đúng time policy ở [final handoff Week 3](../reports/week3-final-handoff.md); actual outputs local, không thay pin lịch sử của runner SEAMLESS.
[Worklog #206](../worklog/2026-10-06-ttsA-issue206-scenarios.md) ghi lệnh cụ thể cho raw trace current, trạng thái checks và các dependency chưa chạy.
Trước nghiệm thu B cần review reuse/gap, proof finite scope, synthetic ledger/ties, exact input/expected digest và các pending rows; sau đó nhận task nối query/harness nếu cần; CI đã consume delta bằng test A2.
PR base develop yêu cầu B review; không tự merge/close #206 và không đánh dấu AC cross-review/runtime pending là đạt.
