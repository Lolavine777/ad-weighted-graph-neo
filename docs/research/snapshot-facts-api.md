# Snapshot facts cho Attack Semantics — #215

Baseline: `develop` tại `7f2fd72`, đã merge #211/PR #221. Đã đối chiếu #174,
#200/PR #218 và #216. Extraction/fact view không phụ thuộc #212 hoặc implementation
roasting. Không có AGENTS.md ở repository hay các thư mục cha đã kiểm tra;
áp dụng CONTRIBUTING và repository/path instructions trong `.github/`.

## AC → baseline → gap được xử lý

| AC #215 | Code baseline | Gap / implementation |
| --- | --- | --- |
| Lookup canonical ID | `IdentityNormalizer.normalize_records` | `SnapshotFacts.lookup(id, name)` |
| Giữ SPN/pre-auth tới semantics | `NormalizedRecord.raw` còn merged Properties | `DirectGraphBuilder.build_snapshot` tạo graph + facts; giữ nguồn từng occurrence |
| Topology không đổi | `DirectGraphBuilder.build` | Giữ nguyên builder structural; so toàn bộ graph trước/sau |
| GraphNode 1.3.0 không đổi | `GraphNode`, `configs/contract.yml` | Sidecar; không thêm node/edge/property |
| True/false/missing | Collector values chỉ còn trong raw | Boolean strict, unknown không có default; SPN empty được giữ |
| Identity/provenance | Reconciliation giữ representations; normalization chỉ chuyển aggregate provenance/relationship lineage | Thêm `NormalizedRecord.raw_representations` để giữ field origins, không lấy riêng first/winning record |
| Runtime/state riêng | #211 query và semantics hiện hành | Facts gắn `EngineGraph`/`PreparedSemanticGraph`, không vào context/state |
| Tests evidence/duplicates/scope | Parser/identity/reconciliation suites | Synthetic tests bổ sung trong `test_snapshot_facts.py` |
| SEAMLESS integration | Manifest và raw probe #200 | `snapshot_facts_probe.py`, actual raw → adapter → reconciliation → graph → persisted engine → semantic view |
| Regression | Week 3/4 và contract suites | Full pytest cùng checks CI; kết quả tại worklog/PR |
| Docs/handoff | Kiến trúc #174, query #211 | Tài liệu này; #216 và AS-REP consume cùng sidecar |

## Bốn layer và nơi facts bị mất

Structural graph giữ canonical identities, attributes đã accepted như `enabled`,
và relationships có evidence. Snapshot facts giữ thuộc tính tĩnh của directory.
RuntimeContext giữ environment/runtime gates và authentication context.
AttackState giữ attacker capabilities riêng của từng branch.

Pipeline thực tế: manifest-backed raw loader → BloodHound v3 identity adapter →
duplicate reconciliation → identity normalization → structural builder → EngineGraph
→ query/search → PreparedSemanticGraph. Baseline giữ SPN/pre-auth trong merged raw,
nhưng `_node` projection của builder chỉ lấy canonical attributes được contract cho
phép. Relationship lineage không có field-level origins của Properties; aggregate
provenance không đủ chỉ ra source nào thật sự có field.

Lát này giữ tất cả raw representations sau reconciliation. Extraction diễn ra sau
canonical resolution và graph build, chỉ lấy User IDs đã được graph chấp nhận.
Không dùng name/DN/locator làm key. Locator chỉ phục vụ audit. Reconciled legacy
objects có nhiều provenance nhưng không có representations bị reject thay vì gán
mọi source cho merged value. Single-occurrence `normalize()` vẫn dùng raw của nó.

## API và policy

API public nằm ở `src.parser.snapshot_facts`:

```python
normalized = IdentityNormalizer().normalize_records(adapted_raw_records)
graph, facts = DirectGraphBuilder(metadata=metadata).build_snapshot(normalized)
engine = EngineGraph.from_canonical(graph, snapshot_facts=facts)
fact = engine.snapshot_facts.lookup(canonical_user_id, "has_spn")
```

`lookup` trả frozen `SnapshotFact(subject, name, status, value, evidence)`:

| Input collector | Kết quả |
| --- | --- |
| `Properties.hasspn: true/false` | `has_spn`, `known`, boolean chính xác |
| `Properties.dontreqpreauth: true/false` | `dontreqpreauth`, `known`, boolean chính xác |
| `Properties.serviceprincipalnames: ["HTTP/synthetic.test"]` | `service_principal_names`, `known`, tuple giữ values/order |
| SPN list `[]` | `known`, `()`; không suy `has_spn=false` |
| Field thiếu / subject không có facts | `unknown`, `None`, evidence rỗng |
| Null, sai type, SPN list có item không là non-blank string | `unknown`, `None`, evidence giữ input để audit |

Chỉ support đúng các collector paths viết trên. Không trim, parse service class,
bool-coerce string/integer hay derive fact. Tên fact chưa support gây `KeyError`.
`enabled` đọc qua `engine.node(id)`; missing canonical attribute vẫn là missing,
không tạo enabled authority thứ hai.

Reuse policy `reconcile_raw_records`: missing/empty không xóa non-empty evidence;
true/false conflict gây `ReconciliationConflictError`, không dựng snapshot rồi chọn
optimistic value. SPN lists non-empty khác nhau cũng conflict; field này không nằm
trong relationship evidence-union allow-list. Empty list chỉ thắng khi không có
valid non-empty list; evidence của empty vẫn được giữ. Không thêm precedence cho
collector/full/supplemental hay list union. Lookup không có trạng thái conflict vì
snapshot mâu thuẫn đã bị reject; transport load cũng reject known-value conflict.

`FactEvidence` giữ `value_json` (JSON của đúng field, kể cả malformed input), immutable
`provenance`, `classification="collector_normalized"`. Provenance copy các source
fields hiện hành: `raw_file`, `collector`, `timestamp`, snapshot reference,
`record_locator`/`record_id`, time provenance/reason và collector schema version nếu
có; `attribute` là path `Properties.<field>`. `hasspn` không được gọi là raw LDAP
attribute. Collection time assumed/derived vẫn giữ đúng classification/reason của
loader, không lấy export time thay collection time. Evidence không có field không
được gán làm nguồn hỗ trợ fact. Không có derived facts trong lát này.

Facts, evidence và SPN tuples không cho consumer sửa. Extraction không sửa raw,
normalized records, graph, context hay state; source sửa sau extraction không sửa
fact values/provenance đã copy. View sống cùng snapshot; graph đổi thì cần dựng lại.

## Boundary và persistence thực sự support

`EngineGraph.from_canonical(graph, snapshot_facts=facts)` kiểm binding rồi giữ facts.
Search chuyển cùng view tới `PreparedSemanticGraph`; consumer đọc
`semantic_graph.snapshot_facts.lookup(target_id, name)`. `run_attack_query(query,
engine)` và `MaterializedQuery.search(engine)` giữ wiring này. Probe integration
chạy query/search thật và consumer đọc fact trước evaluator hiện hành, không thêm
roasting transition.

```python
from pathlib import Path
from src.parser.snapshot_facts import serialize_snapshot

Path("snapshot.json").write_text(serialize_snapshot(graph, facts), encoding="utf-8")
engine = EngineGraph.from_snapshot(Path("snapshot.json").read_text(encoding="utf-8"))
# Truyền engine này tới run_attack_query; không chuyển lại thành structural mapping.
```

Envelope `snapshot-facts/1` chứa `graph`, `snapshot_id`, `graph_sha256`, `facts`.
Mỗi fact row có `subject`, `name`, `evidence`; mỗi evidence có `value_json`,
`provenance`, `classification`. Load validate Graph 1.3.0, source snapshot/field,
User subject, unique keys, graph binding và resolve lại values từ evidence.
Graph digest cover toàn bộ metadata/attributes/relationships/provenance/assessments,
chỉ normalize thứ tự ba top-level collections theo ID để tương thích builder/engine.
Digest là binding, không thay việc verify raw manifest hoặc chứng minh collector truth.

Parser CLI hiện tại vẫn export structural graph JSON. `serialize_graph`,
`EngineGraph.to_canonical()` và query nhận structural mapping riêng không vận chuyển
facts; `EngineGraph.from_canonical(graph)` có `snapshot_facts=None`. Persisted facts
được support qua envelope API ở trên, không claim CLI graph-only có static evidence.
Không thêm storage service hoặc thay GraphNode contract.

## Vì sao defer Service/SPN topology

Giữ rationale từ [comment #215](https://github.com/nairyuuu/ad-weighted-graph/issues/215#issuecomment-6028990398):
SEAMLESS chỉ collect sáu object kinds User/Group/Computer/Domain/OU/GPO. SPN,
PSRemoteUsers, RemoteDesktopUsers và DcomUsers không establish service entity độc
lập; snapshot không chứng minh listener/reachability/authentication acceptance,
SMB/LDAP signing/channel binding hoặc endpoint ACL/runtime policy. Tạo Service/SPN
nodes lúc này chủ yếu là inferred topology. Sidecar và runtime/state hiện đủ cho
lát Week 4, không thêm `HasSPN` edge.

Đây là defer, không cấm vĩnh viễn. Xem xét lại khi có service/endpoint inventory độc
lập có provenance; nhiều techniques cùng cần service entity với policies/relations
riêng; hoặc traversal thực sự phải đi qua service entity. Chưa mở ADR mới.

## Probe và handoff

```powershell
python scripts/research/snapshot_facts_probe.py --raw-dir <private-SEAMLESS-root> --code-version <commit>
```

Prerequisites: sáu private raw files khớp manifest `seamless-raw-v1.json`, pinned
snapshot `e0601d…9c812`; policy collection time ở
`tests/fixtures/ranking/seamless_time_policy.json`. Output chỉ aggregates/digests,
không names/SIDs/DNs/SPN values hay full mappings. Thiếu private inputs trả SKIP,
exit 2; manifest mismatch/probe failure exit 1. Synthetic PASS không thay actual
SEAMLESS evidence. Probe so full graph, raw và normalized records; transport/load
facts tới engine/semantic view. Số liệu actual và commands tại worklog/PR.

#216 consume `has_spn`/SPN tuple và canonical `enabled`; AS-REP issue riêng consume
`dontreqpreauth`. Known false/missing phải được consumer map sang blocked/indeterminate
đúng gate; snapshot fact không chứng minh request/recovery/activation thành công.
Delegation/encryption facts sau này cần thêm collector path, strict validator và
review reconciliation policy riêng; không tự áp union hoặc derive. Không cần #212
để consume fact view, không đưa directory property vào runtime assumptions/state.
