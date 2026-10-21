# AS-REP Roasting → danh tính dùng được → tài sản (#228)

## Baseline và phạm vi bàn giao

Nhánh `feature/228-asrep-roasting` bắt đầu từ `develop@f4d1f97` (đã merge
#221/#222/#230/#232/#233). Đã đọc CONTRIBUTING, issue #228/#206 và handoff
#218; tại lúc bắt đầu các issue này không có comment mới, không có PR mở cho
#228. Repository và thư mục cha không có AGENTS.md. Worktree riêng giữ nguyên
nhánh và dữ liệu local của người khác.

Đây là implementation prediction trên public query và CLI schema
`week4-query-result/0.2.0`. Caller chọn source/target/state/facts/scope, engine
tự tìm ordered program. Không gửi request Kerberos thật hoặc chạy cracking.
[MITRE T1558.004](https://attack.mitre.org/techniques/T1558/004/) mô tả AS-REQ
không có preauthentication cho account phù hợp và material có thể được thử
recovery; nguồn này không cung cấp probability hay effort của fixture.

## Matrix exact API và ranh giới

Ký hiệu: X là source Computer, V là canonical User đích, H0 là Computer context,
G là group checkpoint, C là asset Computer. Fixture dùng X=H0. Các nhãn A1–A5
trong #218 chỉ là projection; owner IDs dưới đây là concrete proposal để A review.

| Projection / owner catalog 0.5 | Snapshot fact / initial capability | Runtime gate (subject,target) | Effect và binding |
| --- | --- | --- | --- |
| A1 `asrep_request` / `ASRepTarget` | canonical User V; canonical `enabled(V)=True` (`target_enabled`); `SnapshotFacts.lookup(V,"dontreqpreauth")` phải known true; `known_identity(V)`; `asrep_request_capability(X,H0)` | `network_kdc_reachable(X,V)`, `asrep_request_accepted(X,V)` | `asrep_material`: `CredentialArtifact(V,H0,"kerberos_asrep",provenance)` |
| A2 `recover_asrep_secret` / `ASRepMaterial` | branch material đúng V,H0, đúng form | `recovery_success(X,V)`; `recovery_scope`: outcome có scope và metadata `method`, `budget`, `horizon` không rỗng | `recovered_secret`: `CredentialArtifact(V,H0,"password",provenance)` |
| A3 `activate_recovered_identity` / `RecoveredSecret` | branch recovered password V,H0; canonical `enabled(V)` | `secret_valid(V,H0)`, `network_kdc_reachable(V,H0)`, `authentication_accepted(V,H0)` | chỉ `usable_identity(V,H0)` |
| A4 `propagate_group_entitlement` / `MemberOf` | usable V,H0; canonical MemberOf V→G, actor enabled, source authorized | `security_group(V,G)`, `membership_usable(V,G)` | `effective_member(V,G)`; passive closure, không active work unit |
| A5 `scenario_winrm_admin` / `DeclaredHostAdmin` | usable V,H0; canonical GenericAll G→C và entitlement V,G; target enabled | `host_admin_mapping(G,C)`, `network_winrm_reachable(V,C)`, `service_winrm_running(V,C)`, `winrm_authentication_accepted(V,C)`, `endpoint_authorized(V,C)`, `admin_execution_context(V,C)` | `admin_control(C)` là final goal; membership/DA checkpoint riêng |

Artifact evaluator còn kiểm endpoints, source/target kinds, source=actor ở A1/A2,
context tồn tại và là Computer, target=context ở A3. Actor của A1/A2 là X,
A3/A4/A5 là V. Runtime credential gates có metadata `authentication_context`
khác H0 giữ unknown. `dontreqpreauth=false` nghĩa preauthentication required,
không tạo material; missing/malformed fact giữ unknown. Fact conflict bị resolver
SnapshotFacts reject trước search, không chọn giá trị theo optimistic assumption.

SnapshotFacts giữ canonical identity, preauth policy và source field evidence;
`enabled` tiếp tục thuộc canonical node. RuntimeContext giữ acceptance/outcome
gates. AttackState giữ knowledge, request capability, artifacts, scoped identity
và entitlement/resource capabilities. Tất cả effects branch-local và immutable.

Source không cần AD credential: query dùng `initial_actor=X`, explicit
`control: []`, `known_identity: [V]`, `asrep_request_capability: [[X,H0]]`.
Generator tạo capability trigger từ knowledge; gate kiểm request capability đúng
context. Không cần structural edge X→V, SPN, initial usable identity hoặc grant
control. Source dạng User cũng được catalog cho phép; nếu khai source foothold
Computer nhưng actor là User thì invariant materializer hiện hành vẫn yêu cầu
capability danh tính/control của User. Cách biểu diễn source chưa authenticated
được kiểm chứng ở đây là Computer X thực hiện request.

Supported: canonical User target, password recovery prediction trong một declared
Computer context, existing membership/host actions và initial secret/identity reuse.
Material AS-REP và service-ticket có state field/form khác nhau; recovery dùng
chung gate/lineage implementation với #216 nhưng owner `recover_asrep_secret`
không tiêu thụ service-ticket. Không mô hình realm/service nodes mới, cross-context
credential portability, NT hash recovery, delegation, live exploit hay probability
measurement. Không nhận RBCD/Top-K/algorithm research/viewer/CE/Travel vào PR.

## Reuse và provenance

Reuse `run_attack_query`, `materialize_query`, `generate_attack_paths`,
SnapshotFacts/serialize_snapshot, `CredentialArtifact`, shared evaluator recovery
và activation, typed `replay_path`, `SemanticReplayBinding`, canonical ranking
adapter/evaluator, initial actor-set semantics của #230 và existing query CLI.
API mới: hai catalog owners/capability triggers, hai fields
`asrep_request_capability`/`asrep_material` và form `kerberos_asrep`.
`scripts/research/credential_bindings.py` tách reusable synthetic bindings từ
Kerberoasting probe; không thêm search/ranking engine hoặc execution runner.

Request provenance giữ `Properties.dontreqpreauth`, canonical V, snapshot source,
collector/timestamp/locator, request owner/endpoints, H0 và runtime declarations.
Recovery kế thừa material provenance; activation kế thừa recovered-password
provenance. Steps A1–A3 không có structural edge IDs giả; A2/A3 có
`derived_from_step=0/1` khi prefix được generated. Initial reuse giữ origin
`initial_attack_state`, không manufacture acquisition steps.

Ranking chỉ nhận snapshot-root lineage sau typed replay với graph và bound
SnapshotFacts. Validator chấp nhận đúng owner `asrep_request` và đúng evidence
name `dontreqpreauth` **khi đã có process-local semantic verification**. Inline
candidate JSON không mint được binding, dù tự khai complete snapshot evidence.
Binding kiểm query/snapshot/target/action/context/lineage; generic evaluator vẫn
reject credential envelope thiếu verified binding. Transport digest chỉ kiểm
consistency, không chứng thực mật mã source collector; caller phải cung cấp
snapshot đã verified. Đây là trust boundary #230, không phải trust vào candidate.

Known-false veto runtime optimistic assumptions; snapshot policy không đọc
inline runtime claim thay fact. Required missing giữ indeterminate. Blocked hoặc
unknown không apply effects, successful prefixes và independent branch còn được
giữ. Các biến thể preauth trong tests là **separate synthetic snapshot views**,
không sửa input snapshot. Chưa cung cấp public API để sửa policy raw/counterfactual
SEAMLESS; nếu cần A phải review view/trace riêng.

## Oracle mapping và nghiệm thu

Nguồn độc lập: [#218, mục 3](week4-extension-scenario-handoff.md),
[#206](https://github.com/nairyuuu/ad-weighted-graph/issues/206).
`tests/fixtures/asrep/oracle.json` được viết từ dependency proof của A trước khi
gọi engine. Không regenerate expected từ actual. Fixture có đúng X,V,G,C và hai
structural supports V→G / G→C; không có reset hoặc alternate acquisition path.

Oracle A-P: một minimal program A1,A2,A3,A4,A5; sáu projected states lần lượt
initial, material, material+secret, thêm usable V/H0, thêm member V/G, thêm admin C.
Mỗi step chỉ tạo prerequisite cho step sau. Tests đối chiếu exact programs,
actors, projected states, lineage parents và cutoffs, không chỉ terminal/count.

| Cases #218 / kiểm tra thêm | Expected độc lập |
| --- | --- |
| A-P | program 5 steps, 6 states; không control/reset/service-ticket effects |
| A-PRE-F/U; A-KDC-F/U; request acceptance F/U | cutoff 0; không material |
| A-REC-F/U; recovery scope thiếu horizon/sai context | giữ material; không secret/identity |
| A-AUTH-F/U; activation KDC F/U; enabled F/U | giữ secret; không usable identity |
| entitlement F/U | giữ usable, chưa member/admin |
| A-ASSET-F/U | giữ checkpoint; chưa admin asset |
| A-SECRET / A-IDENTITY | program A3–A5 / A4–A5, original `initial_actor=X` giữ nguyên |
| material reuse | program A2–A5; vẫn cần declared recovery outcome |
| A-CONTEXT | H1 không dùng như H0; cô lập owner scope A4/A5 đúng handoff |
| A-EXT-OFF | cùng inputs, chỉ bỏ A1–A3 khỏi allow-list; không asset goal |
| known-false veto / fabricated lineage | reject optimistic gate/evidence; không effect |
| independent blocked account | original success path được giữ; inputs/facts không đổi |
| caps | one-step/one-expansion chỉ material prefix; path cap giữ witness nhưng incomplete |

Exact executable mapping AS-REP chưa được A accepted. Các tests là B đối chiếu
logic #218; A cần freeze executable input/expected qua #206, cross-run qua #208.
Không tự ghi independent oracle accepted hoặc full Week 4 completed. Discrepancies
phát hiện trong triển khai là binding test dùng sai signature và metadata pins
baseline chưa rebind; đã sửa, không đổi domain expected để khớp actual.

Catalog 0.4→0.5: đã so structural equality của toàn bộ entries cũ và evidence
registry với `develop@f4d1f97`; chỉ thêm hai owners. Rebind version/hash trong golden
packages và narrow SEAMLESS pin, cập nhật manifest `.sha256`; giữ nguyên expected
programs/states và numeric ratings Week 3/4. Capability exclusion tests xác nhận
ASRepTarget/ASRepMaterial không lọt vào tám structural edge kinds.

## CLI và tái lập

Từ clean checkout đã install `requirements-dev.txt`, dùng Python 3.14:

```bash
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query.json --label synthetic --output run-1.json
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query.json --label synthetic --output run-2.json
python -m scripts.research.compare_query_runs run-1.json run-2.json
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query-off.json --label synthetic --output off.json
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query-raw.json --label synthetic --output unresolved.json
python -m pytest tests/test_asrep.py tests/test_kerberoasting.py tests/test_query_cli.py tests/test_week3_scope_and_types.py
```

Query có declarative ranking payload/action bindings, không ordered path/candidates.
ON/OFF giữ snapshot, source/target, initial state, assumptions, recovery scope,
budgets/goal và bindings; chỉ technique allow-list khác. Synthetic RAW giữ runtime
unresolved, không thay bằng declared positive. Compare contract #213 so semantic
ordering và revision/input/config/source digests; runtime timestamp/duration/platform
ở field riêng và không dùng để claim deterministic semantic output.

Whole-path evaluator consume typed generated paths qua supported replay/adapter.
Bốn active work units: request, recovery, activation, asset action; membership
passive không bị charge. Initial material/secret/identity bỏ prefix và còn 3/2/1
work units. Owner/context/success-event/method-budget-horizon bindings có provenance.
Không có numeric basis: effort/likelihood/impact null/unrated, không copy Week 3,
không P=1 từ synthetic true. Adapter exclusions hiện diagnostics và hạ proof;
unbound path hiện binding_diagnostics. Initial goal giữ validated zero-work
disposition, không tạo Pareto/P/I. Caps không cho global minimum/no-path/Top-K.

## SEAMLESS và phần pending

Reuse V_A locator `#/users/1700`, G_DA `#/groups/40` (membership entry 2), C0
`#/computers/0` của #218. `seamless_inputs(raw_dir,revision)` trong
`scripts/research/asrep_inputs.py` verify full pinned manifest
`e0601d76…c812`, normalize/build SnapshotFacts, resolve locator duy nhất, giữ
MemberOf và inferred AdminTo provenance counts. Hàm chỉ chuẩn bị input cho CLI
chung, không chạy exploitation/query. Returned graph/query chứa private canonical
IDs: chỉ lưu local, không commit; public aggregate trace dùng aliases/locators.

Hàm trả RAW không runtime outcomes và ASSUMED có scoped declarations, rationale,
source/method/budget/horizon. Source C0 chỉ có request capability do scenario khai
báo, không có admin/control/AD identity. Resource owner raw reuse
`obtain_admin_execution_on_host` với canonical AdminTo; asset path có thể không cần
DA checkpoint. Chưa có independent executable SEAMLESS mapping accepted cho owner
set này; không ép raw topology thành fixture A-P năm bước.

Actual SEAMLESS run **pending**: worktree này không có authorized,
manifest-verified private raw inputs. Không dùng file zip chưa verified hoặc
synthetic positive thay actual evidence. Missing directory/file báo prerequisite;
manifest mismatch fail closed. Khi có authorized input, lưu snapshot/query local,
dùng cùng `src.engine.query_cli --label seamless --prerequisite <private-file>` và
so hai runs; CLI prerequisite digest vẫn không tự chứng minh raw→snapshot lineage,
nên cần giữ manifest/locator trace từ hàm chuẩn bị. RAW runtime/recovery/auth outcomes
vẫn unresolved nếu raw chỉ chứa policy/entitlement. ASSUMED success chỉ conditional.

Ví dụ chuẩn bị input local sau khi được phép dùng private raw (chưa chạy tại phiên
này). Thư mục `reports/generated` được gitignore; không đẩy các files này lên PR:

```python
import json
from pathlib import Path
from scripts.research.asrep_inputs import seamless_inputs
from src.parser.snapshot_facts import serialize_snapshot

engine, raw, assumed, trace = seamless_inputs("<authorized-raw-root>", "<revision>")
folder = Path("reports/generated/asrep-228-private")
folder.mkdir(parents=True, exist_ok=True)
(folder / "snapshot.json").write_text(
    serialize_snapshot(engine.to_canonical(), engine.snapshot_facts), encoding="utf-8"
)
for name, value in (("raw", raw), ("assumed", assumed), ("trace", trace)):
    (folder / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
```

Sau đó chạy CLI chung với private snapshot/query và các `--prerequisite` files
đã được full manifest verify, giữ outputs local. `trace.json` chỉ là aggregate
locators/fact/support counts; cần retain bound snapshot/source provenance để A audit.

Bằng chứng actual synthetic, source pin, input/config digests và checks nằm trong
[gói evidence](evidence/asrep-228/README.md). #206 nhận mapping/input/expected đề
xuất và discrepancies; #208 sở hữu independent acceptance, private reproduction
và coverage delta. PR request @Lolavine777 review, không merge/đóng #228.

Kết quả lịch sử trước review tại source `1753a4e`: 2106 PASS, 11 SKIP,
48 subtests PASS. Evidence hiện hành đã thay bằng source `97aa41b`, xem gói
reproduction; review lại trên head mới vẫn pending.

## Sửa theo review PR #234 và tích hợp #231 (08/10)

Đã merge `origin/develop@d96f3f6`, giữ acceptance files của #231 và cả LF
policies cho AS-REP/acceptance. Không rewrite lịch sử nhánh đã chia sẻ.

A1 áp dụng **supported conservative eligibility boundary**: canonical User
phải có `enabled=True`. `enabled=False` veto cả optimistic
`asrep_request_accepted=True`; thiếu enabled giữ indeterminate, không tạo
material hoặc secret. Initial secret reuse vẫn kiểm enabled ở A3. Đây là phạm
vi prediction được hỗ trợ, không khẳng định Windows luôn từ chối disabled
account: [MS-KILE account policy](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/beb74443-2e5e-4cfa-917e-46ef701a5cb5)
quy định rejection khi `POLICY_KERBEROS_VALIDATE_CLIENT` được bật. Policy-off,
locked/expired/logon-hours và các policy khác chưa được mô hình riêng;
acceptance thực tế vẫn là runtime gate, enabled true không bảo đảm request.

`credential_ranking_inputs` giữ material/secret/usable/member/admin khai báo
ban đầu trong `assumed_facts`, Layer 3. Presence không phải positive telemetry;
absence không phải snapshot-confirmed negative. Resolver scenario cho
`permitted_runtime_assumption`/`assumed_false`; evidence-only giữ Unknown.
Tests kiểm buckets và resolved origins cho empty state cùng cả ba reuse cases.
Không nới validator hoặc gọi synthetic URI là authoritative observation.

Helper nhận `work_boundary`, `goal_id`, `provenance_root` để wrapper #216 giữ
`216-scoped-password-recovery`, `admin-216`, `synthetic://216/binding` và
`synthetic://216/event-binding`; regression test pin các giá trị này.

Case `W4-TECH-ASREP` của runner #231 nay chạy public query thật với exact owners
#228 thay placeholder `asrep_roasting`. Normative expected fields của oracle
A vẫn giữ nguyên; actual output/manifest được refresh riêng. PASS chỉ là scoped
synthetic checks, không tự chấp nhận domain mapping hoặc private replay.
Hai P1 cần review lại trên head mới; #206/#208 vẫn sở hữu mapping/cross-run và
private acceptance. SEAMLESS tiếp tục pending authorized manifest-verified
inputs; không có live exploitation/cracking hoặc private run.
