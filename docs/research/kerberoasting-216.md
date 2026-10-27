# Issue #216: semantic model và nghiệm thu

Base cuối: develop `adee089` (#221/#222/#223/#225 đã merge bởi upstream).
Worktree khởi đầu tại `ae778cd`, sau đó merge develop mới; không dùng branch phụ thuộc.
Không có AGENTS.md trong repo/parent; theo CONTRIBUTING và engine review checklist.

## AC → baseline → gap (chốt trước code)

| AC | Baseline reuse | Gap triển khai |
| --- | --- | --- |
| SPN true/false/missing, provenance | SnapshotFacts.lookup; EngineGraph.from_snapshot | Request đọc facts, không edge giả |
| Query tự generate | run_attack_query; bounded branch search | Producers từ knowledge/facts/artifact |
| Auth/context/KDC | usable_identity(principal,context); runtime resolver/veto | Kerberos qualification gate; explicit unknown availability |
| Material/recovery/activation | immutable AttackState; reset bridge giữ riêng | Typed artifact; 3 owners; activation không reset qualifier |
| Replay/ranking | adapter_145; evaluate_search_candidates; replay_candidate_sequence | Preserve fact/artifact lineage; executable exact bindings |
| Reuse/caps/determinism | history/budget/owner catalog | Suppress work khi output đã có đúng scope |
| Oracle/baseline | #218 mục 5–8 | Freeze synthetic reasoning, K-OVERLAP, hai run |
| SEAMLESS | manifest + raw locators User11/Group30/User917/Group40/Computer0 | Actual trace + missing runtime disposition |
| CI/review | repository checks + GitHub CI | Exact head green; A cross-review pending |

## Transition matrix (exact implemented API)

| Owner / trigger | Snapshot evidence | Capability | Runtime gates | Effect | False / missing | Ranking |
| --- | --- | --- | --- | --- | --- | --- |
| kerberoast_request / RoastTarget | canonical User has_spn; required nonempty SPN values | known_identity target; usable actor/H | kerberos_authentication_usable(actor,H), network_kdc_reachable(actor,target), service_ticket_request_accepted(actor,target) | service_ticket_material artifact target/H | false blocked; missing indeterminate; no effects | request work; missing C/P unrated |
| recover_ticket_secret / TicketMaterial | artifact acquisition lineage | service_ticket_material target/H | recovery_success actor/target with method,budget,horizon metadata | recovered_secret target/H, password form | false/unknown no secret | recovery event; no inferred password strength/P |
| activate_recovered_identity / RecoveredSecret | canonical enabled owner + artifact lineage | recovered_secret owner/H, password form | secret_valid(owner,H), authentication_accepted(owner,H), network_kdc_reachable(owner,H) | usable_identity(owner,H) | false/unknown no actor switch | distinct activation work; no Week3 copied numbers |
| Existing membership/reset/WinRM owners | canonical relationships/provenance | usable target/H and derived entitlements | existing gates | final admin_control(asset) | DA checkpoint ≠ asset goal | passive closure no work; asset I unrated without basis |

Supported scope: canonical Users, one declared authentication context (canonical Computer),
password recovery only. Missing auth is closed-world blocked; explicit authentication_unknown
pair declares availability unknown, never creates usable identity. Material/secret artifacts
bind owner/context/form/provenance; no real password bytes. Runtime outcomes remain
scenario assumptions or evidence, never inferred from flags, SPN count or topology.

## Oracle rationale frozen before implementation output

Small fixture X/U/V/G/C has only request → recovery → activation → membership → host
admin owners. U/H is initially usable; V is known with SPN evidence. Each rule supplies the
next rule prerequisite, hence exactly one first-hit program of five steps; projections:
initial, material, secret, usable V/H, entitlement G, admin C (six states). A false/missing
step retains only earlier effects. Initial material/secret/identity removes corresponding
prefix work. K-NO-AUTH/K-MATERIAL/K-FACT consume #218 expectations. K-OVERLAP adds
shared reset U→R→reset D→G→C and V→R→reset D; baseline already reaches C. New route cannot
prove new C coverage. These are synthetic expectations, not measured SEAMLESS success.
A must review this new executable mapping and independent rationale.

## API thực hiện và boundary

Catalog **0.4** thêm đúng ba owners trong matrix; structural contract vẫn 1.3.0,
8 edge kinds. `CredentialArtifact(owner, context, form, provenance)` được export ở
`src.engine.semantics`; forms accepted là `kerberos_service_ticket` và `password`.
`AttackState.service_ticket_material` / `recovered_secret` chứa artifact, không byte
bí mật; `credential_material` cũ không tự thỏa hai loại mới. `known_identity` là
knowledge độc lập; `authentication_unknown={(actor,H)}` khai báo availability chưa
biết. Absence trong scoped state là known absence; không seed từ Computer control.

Các runtime keys dùng `(predicate, subject, target)`: request dùng actor/target User,
Kerberos qualification dùng actor/H; recovery dùng actor/owner với metadata
`method`, `budget`, `horizon` và `scope` bắt buộc; activation dùng owner/H. H là
canonical Computer trong supported scope. Metadata tùy chọn `authentication_context`
phải khớp H. RuntimeContext và query resolver giữ known-false veto/rejected ledger.
SPN và SPN values chỉ đọc `SnapshotFacts.lookup(canonical_id, name)`, không override
bằng runtime assumption. SPN values required nonempty; missing indeterminate, empty
blocked. Reconciliation conflicts vẫn do fact API reject trước search.

Producer xét các identity attacker đã biết, filter canonical User, lookup facts tại
semantic evaluation. False/missing được giữ thành attempted blocked/indeterminate
để audit; không có applicable acquisition khi SPN false. Artifact/usable identity
đúng H suppress prefix work đã có. Initial usable identities trong H có thể được
search xét như actor; activation chỉ switch sau applicable. Secret là khả năng
thử authentication, chưa là identity/control. Query có thể khai báo initial actor
là secret owner khi artifact đúng H để bắt đầu activation mà không seed control.

Action history có stable owner/actor/source/target, cùng context cố định của query;
producers dùng cùng caps/history với relationships. Source index chỉ giảm scanning
các nguồn mà authorization filter không thể xét; sorting/attempt ordering giữ
lexical deterministic. Canonical nodes/edges/provenance không bị sửa; snapshot
fact lineage và artifact provenance được transport kể cả `edge_id=None`.

## Query, output và lệnh nghiệm thu

Input executable: [query](../../tests/fixtures/kerberoasting/query.json) và
[snapshot envelope](../../tests/fixtures/kerberoasting/snapshot.json), đều synthetic.
Query chỉ khai báo source/actor, known identities, capabilities, context, gates,
asset predicate, owners và caps. Không có ordered path/roast request/victim program.

```python
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
import json
from pathlib import Path

folder = Path("tests/fixtures/kerberoasting")
graph = EngineGraph.from_snapshot((folder / "snapshot.json").read_text(encoding="utf-8"))
query = json.loads((folder / "query.json").read_text(encoding="utf-8"))
result = run_attack_query(query, graph)
assert result.final_goal_reached
```

```bash
python scripts/research/kerberoasting_probe.py --code-version <source-pin>
python scripts/research/kerberoasting_probe.py --code-version <source-pin> --snapshot tests/fixtures/kerberoasting/snapshot.json --query tests/fixtures/kerberoasting/query.json --output <local-output.json>
python scripts/research/kerberoasting_probe.py --code-version <source-pin> --raw-dir <private-SEAMLESS-root> --output <local-output.json>
python -m pytest tests/test_kerberoasting.py tests/test_snapshot_facts.py tests/test_attack_semantics_catalog.py tests/test_attack_semantics_transitions.py tests/test_query_boundary_regressions.py tests/test_week3_semantic_bridge.py tests/test_week4_query_materialization.py tests/test_week4_scenarios.py tests/test_week4_scoring.py tests/test_path_ranking_interface.py
```

Positive expected: `status=success`, conditional dưới outcome assumptions,
`asset_goal=true`, checkpoint=true; owners request/recovery/activation/membership/
WinRM admin. Material stage không secret/usable identity; secret stage không reset
control; activation không admin. SPN=false hoặc KDC=false: blocked, không effect.
SPN/KDC missing: indeterminate. Recovery missing: material tồn tại, secret/identity
vắng. Authentication missing/false: secret tồn tại, usable identity vắng. Asset
missing/false giữ checkpoint nhưng chưa đạt goal. Tests đối chiếu rationale độc lập
ở trên và #218 K-NO-AUTH/K-MATERIAL/K-FACT/K-OVERLAP; A review mapping còn pending.

`--raw-dir` thiếu trả SEAMLESS SKIP/exit 2; không dùng synthetic PASS thay actual.
Errors ở private probe chỉ xuất stage/type/line, không dump identities. Output
SEAMLESS chỉ aliases/locators/counts/digests/owner labels, không private mapping.
`--snapshot/--query` là minimal handoff cho #213, không redesign CLI của integration.

## Replay, binding và scoring

`replay_path(path, EngineGraph, catalog=None)` re-evaluate requests với branch state
và facts sidecar, so effects/gates/lineage và final state. Canonical ranking adapter
consume typed generated paths; `generate_and_evaluate_attack_paths` và
`evaluate_search_candidates` nhận optional `snapshot_facts=graph.snapshot_facts`.
Khi có new owner, semantic replay xảy ra trước adapter; lost sidecar làm request
unresolved và candidate được giữ ở diagnostics, không rated success.
`to_canonical()` vẫn chỉ trả topology; transport graph+facts dùng `serialize_snapshot` /
`EngineGraph.from_snapshot`; caller phải truyền facts ở ranking boundary.
Serialized PathResult mới chưa có deserializer; dùng typed path + snapshot envelope,
không tự tin serialized lineage như bằng chứng evaluation.

Harness `ranking_inputs` cung cấp exact action/owner/context/event bindings và
Layer 3 material→secret→usable→member→admin replay. Unique work units: request,
recovery, activation và asset action; membership passive không charge work. Reuse
initial material/secret/identity bỏ prefix work tương ứng (4/3/2/1 active units).
Không có conditional numeric bounds hoặc numeric effort/impact trong gói này.
Canonical evaluator giữ `effort_status=unrated`, effort/likelihood/impact=null;
semantic labels không tự là probability factors. Unknown action không tạo effects;
absence của goal Layer 3 chưa đạt không override unknown action thành blocked.

K-OVERLAP so cùng snapshot/query state/shared facts/assumptions/asset/budget; chỉ
extension owner allow-list đổi. Reset baseline U→holder→reset D→activation D→asset
được giữ. Routes tăng không chứng minh asset mới. Caps/truncation chỉ cho phép
báo generated-scope delta, không global optimum/no-path hoặc measured coverage.
Numeric basis mới cần A review event/target/context/horizon; không copy Week 3,
không suy từ password age, encryption flag hay SPN count.

## SEAMLESS và handoff

Raw locators: U=User1580, V_K=User11, V_D=User917, G31/G548/G30, DA=Group40,
C0=Computer0 theo #218. Manifest verify full six files trước normalize/build.
Trace kiểm SPN + enabled, ordered membership support, GenericAll→V_D, DA membership
và inferred AdminTo→C0 với provenance; so full graph/raw/normalized trước/sau.

Raw mode có initial usable U/H0 **do scenario khai báo**, không observed credential;
KDC/request/recovery/activation/asset runtime chưa được raw chứng minh. Assumed
baseline/extension giữ cùng inputs, metadata và caps; extension-only assumptions
được liệt kê riêng theo predicate/alias/scope/method/budget/horizon. Một witness
riêng giữ U membership gates withheld để cô lập Kerberoasting→reset→asset route;
witness khác scope, tuyệt đối không dùng cho baseline coverage comparison.
SEAMLESS PASS là trace/invariants, không exploit/cracking success hoặc P measurement.

Reusable cho AS-REP sau này: typed recovered password artifact, context-scoped
activation, secret validity/authentication gates, lineage/replay, exact bindings và
missing-basis disposition. Kerberoasting-specific: SPN facts/values, required initial
Kerberos auth, service-ticket material/request producer. Chưa có AS-REP/RBCD trigger.

Catalog rebind: đối chiếu toàn bộ 13 entries và evidence registry của `ae778cd` với
catalog mới bằng structural equality; chỉ thêm owners và version 0.4. Week 3/4
expected programs/states/ratings không regenerate; chỉ version/hash metadata được
rebind. Các capability exclusion tests mở rộng tới 3 triggers mới, structural 8 kinds
giữ nguyên. A cần cross-review exact API, independent oracle mapping và evidence.

Public ranking sau upstream #223: `run_attack_query(query, graph,
action_bindings=bindings, ranking_query=payload)` giữ facts sidecar tại semantic
replay + canonical evaluator. Harness consume entry point này. `optimization_scope`
cho positive unrated là best_in_rated_subset; minimum/proof false. Các follow-up
correctness của #212 được upstream theo dõi riêng; PR này không claim global optimum.

## Bằng chứng thực chạy

[Hai outputs/digests và lệnh reproduction](evidence/kerberoasting-216/README.md)
pin source `afd0f68`; clean suite 1977 passed / 11 skipped. Actual SEAMLESS có
manifest-verified trace, raw unknown, same-input comparison và witness đủ tới C0
dưới assumptions ở scope riêng. [Worklog](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-10-07-ttsB-issue216-kerberoasting.md)
ghi checks/skips và phần A cần cross-review. Exact PR head CI được bàn giao trong PR.

## Review #230: ranh giới semantic replay và initial actor set

Candidate JSON có `snapshot_evidence` không tự trở thành source-backed evidence.
`evaluate_search_candidates` replay typed path với canonical graph và SnapshotFacts
đã bind, rồi tạo `SemanticReplayBinding` bất biến trong process. Binding gắn exact
query metadata, candidate ID, scope, target, action IDs, transition lineage và
structural routes; được truyền qua validation, ranking assessment và action replay.
Binding không nằm trong wire payload và không thể tạo bằng candidate JSON. Generic
`PathRankingEngine.evaluate`/`execute_ranking_roundtrip` không có binding từ replay
sẽ reject các credential extension transitions, kể cả khi inline evidence đầy đủ.
Graph/facts không khớp hoặc lineage/scope bị sửa sau replay đều fail closed.

Query foothold vẫn là U. Với `usable_identity(V,H)` có sẵn đúng authentication
context, path bắt đầu thực thi bằng V có thể reuse membership/host semantics và
được ranking cùng query U. Chỉ replay thành công với declared initial state cho
phép first actor khác foothold; lineage giữ actor V và scope binding vẫn giữ U.
Recovered password cũng cho phép owner thực hiện scoped activation; secret không
trở thành usable identity trước activation. Không thêm structural edge hoặc work
unit giả cho prefix đã có. Các test reuse giữ nguyên initial_actor U ở cả identity
và secret cases, kiểm tra số active work units tương ứng 1 và 2.

Khi canonical `enabled` vắng mặt, activation vẫn indeterminate và decision origin
là `UNKNOWN`, không ghi observed evidence cho thuộc tính không tồn tại.
