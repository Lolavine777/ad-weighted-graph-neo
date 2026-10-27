# Kiến trúc và contract M2

```text
data/raw/ → src/parser/ → data/processed/ → src/engine/ → reports/generated/
                 ↑                              ↑
                 └──── configs/contract.yml ─────┘
data/samples/ ───────── kiểm thử không cần dữ liệu AD thật ────────────────┘
```

`src/parser/` đọc export qua manifest-bound loader, chuẩn hóa ID và quan hệ, giữ provenance, kiểm tra tham chiếu và xuất graph JSON. `ManifestRawDataLoader` xác thực toàn bộ snapshot manifest và JSON envelope trước khi yield `RawRecord`. CLI chính thức `python -m src.parser.cli` điều phối loader, normalization/reconciliation, direct builder cùng host-access inference, rồi validate và serialize Graph Contract 1.3.0 trước atomic output. Nếu manifest không có collection time, caller phải cấp policy rõ ràng; thời gian `--created-at` không được dùng làm collection time. `src/engine/` nhận graph structural mà không phụ thuộc đường dẫn raw hoặc cấu trúc export BloodHound. Neo4j là lựa chọn lưu trữ/quan sát; thuật toán có thể dùng graph trong bộ nhớ để test nhanh.

`notebooks/` dành cho khám phá; không là nguồn duy nhất của pipeline. Chuyển xử lý tái sử dụng sang `src/`. Parser CLI chạy từ repo bằng `python -m src.parser.cli`; engine hiện vẫn chưa cung cấp Dijkstra, Top-K hoặc choke-point analysis.

## Thống nhất trước khi viết parser

[contract.yml](../configs/contract.yml) là contract structural M2 phiên bản `1.3.0`; graph `1.0.0`, `1.1.0` và `1.2.0` vẫn được nạp tương thích ngược. Chỉ 1.0/1.1 thiếu timestamp status được hiểu là `unknown_legacy`; 1.2 yêu cầu `timestamp_status` trên từng provenance record. Contract giữ lineage dẫn xuất có thứ tự và status thời gian ở từng provenance record, đồng thời cho phép scope Domain bằng objectGUID hoặc SID có thẩm quyền. ADR-0011 và ADR-0012 ghi lại các chiều độc lập về lineage và time. [ADR-0010](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0010-identity-asset-semantic-facets.md) quy định `Identity`, `Asset`, `PrivilegeContainer` và `ControlPlane` là semantic facets, không phải `node.kind`, còn `security_labels` là chiều riêng. Semantic layer có thể tham chiếu graph structural mà không thay đổi schema này.

`unit` là baseline mọi cạnh bằng 1; `illustrative` và `maut_v1` chỉ là profile thử nghiệm, **không phải kết quả nghiên cứu hoặc xác suất thực tế**. Mọi profile hiện đều yêu cầu trọng số tối thiểu `1.0` và chưa production-ready.

| Thành phần | Quy ước |
| --- | --- |
| Node | `id` duy nhất/bất biến là SID không mơ hồ (ưu tiên), SID có scope, hoặc GUID chữ thường; bắt buộc có `kind`, `label`, `domain`, `is_boundary`; có thể có `enabled`, `admincount`, `distinguishedname` |
| Edge | `id` là SHA-256 ổn định từ `source`, `target`, `kind`; bắt buộc có `weight >= 1.0` và provenance với `evidence_type: positive`; cả hai đầu phải tồn tại |
| Hướng | Theo khả năng đi từ nguồn đã kiểm soát sang đích; mapping từng quan hệ cần research |
| Song song | Cho phép nhiều edge cùng source/target khác kỹ thuật; không ghi đè |
| Chi phí | Theo `metadata.weight_profile`; là số hữu hạn, `>= 1.0`, và phải khớp weight của kind trong profile |
| Provenance | Danh sách không rỗng của bằng chứng dương; mỗi record có raw file, collector, UTC timestamp và `evidence_type: positive` |
| Metadata | Bắt buộc `contract_version`, `weight_profile`, `snapshot_id`, `created_at`, `code_version` |
| Assessment | `unknown`, `inferred`, `rejected` nằm trong `assessments`, không nằm trong `edges` và không thể đi qua trong graph |
| Target | ID rõ ràng của tập đích; không suy ra theo display name |
| Đường đi | Trả cả node IDs, edge IDs, tổng chi phí, profile/version và lý do không có đường |

Khi một snapshot được chọn làm Source of Truth cho một evaluation, graph canonical là projection của positive evidence quan sát được trong snapshot đó.
Thiếu positive evidence bắt buộc hoặc collection state còn `unknown` thì connection không được materialize vào `edges`; limitation vẫn được giữ ở `assessments` hoặc evidence/quality reporting.
Do đó, "không có edge trong graph" phải được đọc là "input SoT này chưa chứng minh connection", không phải khẳng định connection ngoài thực tế chắc chắn không tồn tại.
Boundary này giữ traversal fail-closed mà không biến observational limitation thành false negative claim.

Quy tắc chuẩn hóa node và canonical ID cho parser:
- **Canonical ID không có scope**: Ưu tiên SID chuẩn (`S-1-...`) khi SID tự nó phân biệt identity; trường hợp không có SID thì dùng object GUID ổn định và chuyển toàn bộ ký tự GUID về chữ thường (lowercase). GUID viết hoa, có dấu ngoặc hoặc không đủ 128-bit đều bị từ chối.
- **Canonical ID có scope**: Identity namespace-relative phải dùng stable identity của đúng scope. ID GUID-scope hiện hữu giữ nguyên dạng tương thích `domain:<lowercase-guid>:<SID>` hoặc `host:<lowercase-guid>:<SID>`; Domain SID-scope mới dùng dạng rõ kiểu `domain:sid:<domain-sid>:<SID>`. Domain SID có cấu trúc AD `S-1-5-21-X-Y-Z`; DNS name không phải stable scope identity. Khi cả Domain objectGUID và Domain SID cùng có, ưu tiên objectGUID. Host scope vẫn bắt buộc stable Computer objectGUID và không bao giờ fallback sang Domain SID. S-1-5-18/19/20 luôn host-scoped. S-1-5-32-* chỉ nhận domain scope khi adapter xác định object Builtin Group trong record/context Domain; computer-local contexts cần host GUID. Namespace-relative SIDs không được bare.
- **Invariant của parser**: Cùng identity và cùng scope luôn sinh cùng ID; khác scope không được gộp. Parser bảo toàn scope từ prefix/source metadata thay vì strip về bare SID. Nếu không xác định được scope ổn định thì từ chối record thay vì đoán, dùng label/DN, hoặc sinh UUID ngẫu nhiên. Kiểm thử normalization thực tế thuộc parser #8.
- **Trường `domain`**: Phân định ranh giới miền, phục vụ xử lý tài khoản ngoại miền (Foreign Security Principal) và phân tích leo thang tin cậy liên miền (Cross-domain Trust). Trường bắt buộc trên mọi node và không được là `null`.
- **Boundary/stub node**: Node được tham chiếu nhưng chưa thu thập đầy đủ vẫn dùng một trong các kind structural hiện có. Node `Domain` đại diện miền ngoài snapshot; FSP dùng `User` hoặc `Group`, giữ domain external và canonical ID có scope ổn định. Cả hai đều đặt `is_boundary: true`; nếu không có stable ID/scope thì ghi assessment `rejected` thay vì tạo stub từ label.

### Domain SID làm stable scope identity

AD Domain SID (`S-1-5-21-X-Y-Z`) identifies the directory security namespace and separates namespace-relative domain identities across domains. It is therefore valid scope evidence when observed directly on the snapshot's Domain record and no Domain objectGUID is available. Domain objectGUID takes precedence when both are observed, so input order cannot change canonical IDs. DNS names are labels and may be renamed or reused; they are never substituted for a stable scope identity. Host-relative identities still require the host objectGUID. In particular, `S-1-5-18/19/20` always require host scope; `S-1-5-32-*` can use domain scope only when a matching Group object is present in the Domain export. Other unresolved scope cases fail closed. New IDs explicitly identify SID scope as `domain:sid:<domain-sid>:<sid>`; legacy GUID-scoped IDs remain valid and unchanged.

This permits older BloodHound exports that retain the authoritative Domain SID but omit Domain objectGUID to represent domain builtin groups without inventing identity data. Older contract versions and their existing IDs remain loadable.

`S-1-5-32-*` belongs natively to the Windows well-known Builtin domain (`S-1-5-32`). AD DS exposes those Builtin groups under each domain's `CN=Builtin` container. `domain:sid:<AD-domain-sid>:S-1-5-32-544` is a project-level composite canonical namespace key distinguishing an observed Builtin object by AD domain scope; it does not assert native Windows SID construction from the AD Domain SID plus a Builtin RID. Domain-relative security principals whose object SID is derived from the domain SID and a RID are a distinct semantic case. See Microsoft [MS-ADTS Builtin Container](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/64f3fef0-61c1-4b45-9407-5ccfb5385450), [Well-known SIDs](https://learn.microsoft.com/en-us/windows/win32/secauthz/well-known-sids), and [MS-ADTS Well-Known Domain-Relative Security Principals](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/06bf7793-8480-4a86-bf28-74f1d62f6955).

For unresolved references, the builder checks collected nodes and aliases first. Only an explicit set of authoritative, globally identified Windows well-known principals may then become structural boundary nodes. The current supported set is `S-1-5-4` (INTERACTIVE) and `S-1-5-17` (IUSR), represented as `Group` endpoints when collector membership evidence agrees, with `domain=NT AUTHORITY` and `is_boundary=true`. IUSR is a Windows account; `Group` here records only a collector `Members[].MemberId` source role in `MemberOf`, not an observed AD Group object or a general ACL principal kind. Unsupported contexts and conflicting references fail closed. The raw edge occurrence supplies provenance; no object record is invented. See [SEAMLESS evidence and Microsoft references](research/seamless-scope-identity.md#well-known-boundary-principal-resolution).

- **Trường `admincount`**: Chấp nhận cả kiểu boolean (`true`/`false` theo raw BloodHound CE/SharpHound để phân biệt đối tượng được bảo vệ bởi AdminSDHolder) lẫn mọi số nguyên (`INTEGER` theo đặc tả LDAP MS-ADTS), không chỉ `0`/`1`. Trường vắng mặt có nghĩa là chưa được cung cấp, không được ngầm mặc định thành `false`; explicit `null` bị từ chối như các trường optional khác.

Quan hệ AD không tự động đồng nghĩa với một bước khai thác khả thi. Phân biệt hướng quan hệ nguồn với hướng chuyển quyền; ghi điều kiện còn thiếu và loại cạnh không hỗ trợ. Không gộp các điều kiện đồng thời thành những cạnh độc lập nếu làm sinh đường đi giả. Các giới hạn này cần đi vào taxonomy và báo cáo.

### Định danh cạnh và provenance

Canonical edge ID được tính bằng cách tuần tự hóa `[source, target, kind]` thành JSON compact
không có khoảng trắng, mã hóa UTF-8, lấy SHA-256 chữ thường rồi thêm tiền tố `sha256:`. Vì
ID không phụ thuộc thứ tự đọc file, cùng một cạnh logic luôn có cùng ID. Hai kỹ thuật khác
nhau giữa cùng cặp node tạo hai ID riêng và được giữ dưới dạng cạnh song song.

`validate_graph()` xác thực canonical ID của mọi node trước khi kiểm tra cạnh;
`source` và `target` phải tham chiếu node đã hợp lệ. `validate_edge()` chỉ kiểm tra
contract riêng của cạnh, không thay thế bước xác thực toàn đồ thị.

`RawRecord.provenance` giữ `raw_file`, `collector`, `timestamp`, snapshot identity,
occurrence locator và các tham chiếu record/attribute; loader không phải kết luận
evidence là dương hay ngoại lệ. `record_id` identifies the logical object, while
`record_locator` (for example `#/data/0`) identifies one immutable occurrence in an
envelope. Khi
normalizer/builder tạo graph output, `provenance` của edge hoặc assessment mới bắt buộc
có `evidence_type`.

`provenance` là danh sách không rỗng. Mỗi record của traversable edge bắt buộc có
`raw_file`, `collector`, `timestamp` UTC dạng `YYYY-MM-DDTHH:MM:SSZ` và
`evidence_type: positive`; có thể thêm `record_id` và `attribute` để truy ngược tới bản ghi
hoặc thuộc tính tạo cạnh. Khi nhiều nguồn phát hiện cùng một cạnh logic, parser tương lai
phải gộp các record provenance duy nhất vào cạnh đó thay vì tạo ID ngẫu nhiên hoặc làm mất
bằng chứng audit.

Graph JSON luôn có `assessments: []`, kể cả khi snapshot không có ngoại lệ. Một assessment
có dạng `{id, status, reason, provenance}`; `status` chỉ nhận `unknown`, `inferred` hoặc
`rejected`, và provenance của nó dùng cùng timestamp/audit schema với evidence tương ứng.
`subject`, `target`, `kind` và `record_id` là các trường tùy chọn để liên kết assessment với
record đã biết. Record thiếu stable scope hoặc bị từ chối normalization có thể bỏ qua các
endpoint canonical và dùng `reason` cùng `provenance.record_id` để truy vết. Validator không
cho phép status assessment hoặc field assessment xuất hiện trong traversable edge.

## Parser interfaces và Error Policy (Issue #8)

Khung public API nằm trong `src/parser/__init__.py`, gồm ba abstract base class:

| Interface | Đầu vào → đầu ra | Trách nhiệm implementation |
| --- | --- | --- |
| `RawDataLoader.load` | `Path` → iterator `RawRecord` | Adapter manifest-bound; verify toàn bộ snapshot trước, kiểm tra JSON envelope, giữ đầy đủ thuộc tính và provenance |
| `Normalizer.normalize` | `RawRecord` → `NormalizedRecord` | Chuẩn hóa identity và node fields, giữ raw evidence, từ chối SID thiếu scope ổn định |
| `GraphBuilder.build` | iterable `NormalizedRecord` → `Graph` | Thu thập node trước, resolve quan hệ, chỉ xuất edge có positive evidence, ghi assessment và validate graph |

`RawRecord` chứa kind, data và `RawProvenance`; `NormalizedRecord` chứa canonical ID,
kind, attributes, raw record và toàn bộ `raw_provenance` của các occurrence đã hợp nhất.
`evidence_lineage` additionally maps each materialized relationship item to the raw
occurrence provenance that supplied it, so downstream edge construction does not attach
the first occurrence or every occurrence indiscriminately.
Các kiểu này mô tả giao diện, không tự validate dữ liệu. `AllowedToDelegate` và trạng
thái thu thập phải được giữ nguyên cho bước sau;
giá trị rỗng từ SharpHound không được xóa bằng chứng có trong bloodhound-python.
Các quan hệ chưa có trong contract chưa được xuất thành cạnh. `Graph` yêu cầu metadata
đủ năm trường định danh snapshot, `edges` có weight/provenance dương và `assessments` là
collection riêng cho unknown/inferred/rejected.

`process_records(records, transform, error_policy=...)` thực thi chính sách chung:

| Policy | Khi transform ném `RecordError` |
| --- | --- |
| `FAIL_FAST` (mặc định) | Ném lại lỗi gốc, dừng trước record kế tiếp |
| `SKIP_RECORD` | Bỏ record lỗi, tiếp tục, không log |
| `LOG_WARNING` | Bỏ record lỗi, tiếp tục, log warning có stage và record ID nếu có |

Chỉ lỗi dữ liệu ở cấp record được chuyển thành `RecordError`. Lỗi I/O, envelope
JSON hỏng, collector/contract không hỗ trợ, lỗi khi duyệt source và lỗi lập trình
luôn dừng pipeline. Không catch mọi `Exception` rồi bỏ qua. Message lỗi không chứa
raw payload; implementation validate record trước khi thay đổi trạng thái chung
để việc bỏ record không để lại node/edge dở dang.

```python
from src.parser import process_records

# loader, normalizer, builder là các implementation của ba interface.
raw_records = loader.load(source)
normalized_records = process_records(raw_records, normalizer.normalize)
graph = builder.build(normalized_records)
```

Builder phải tuân thủ [ADR-0002](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0002-edge-directionality-semantics.md)
và [ADR-0003](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0003-host-access-inference-policy.md): `MemberOf` đi từ
User/Group tới Group, `HasSession` từ Computer tới User. Suy luận quyền host cần
SID builtin đầy đủ và bằng chứng gắn host hoặc GPO có phạm vi hợp lệ; `CanRDP`
cần cả quyền allow và không có deny. `StatusAccessDenied` là `unknown`, không
tự sinh cạnh. Assessment `inferred` (ví dụ `reason: scoped_gpo`) và `rejected`
cũng tách khỏi cạnh; chỉ positive evidence có provenance hợp lệ mới được xuất
với weight theo profile.

[ADR-0009](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0009-direct-memberof-transitive-resolution.md) quy định canonical graph
chi luu direct `MemberOf` co raw provenance. Transitive/effective membership thuoc
traversal, query hoac host-access inference layer va phai giu chain, cycle guard va domain scope.

### Reconciliation raw representations (M2-04 / #52)

`reconcile_raw_records` is the single representation-level reconciliation boundary
between the loader and canonical identity normalization. It validates that input
records belong to one snapshot, preserves every raw occurrence and provenance, and
uses `record_locator` to distinguish duplicate records from the same JSON envelope.
Multiple records with no recoverable snapshot identity fail closed; callers with
legacy provenance may provide an explicit snapshot boundary.
For each unioned relationship item, `evidence_lineage` retains the canonical item key
and the exact raw occurrence provenance that contributed it.

The raw key is `(kind, ObjectIdentifier)` only when that identifier is scope-safe.
Bare namespace-relative local SIDs are grouped only with an explicit stable scope
GUID; otherwise they remain separate for the normalizer. Only documented
relationship fields (`Members`, `Aces`, `LocalGroups`, session/delegation/trust
fields) receive evidence-union semantics. Unknown list fields and conflicting
non-empty scalars raise `ReconciliationConflictError` rather than selecting a
deterministic but unauthoritative winner.

`duplicate_cause=verified_supplemental` is reserved for the narrowly documented
Dataset A shape: exactly one full and one supplemental occurrence from the same
raw file, a full record with non-empty `Properties`, `Members`, and `Aces`, and a
supplemental record containing only the expected empty fields plus `reconcile=false`.
Other duplicate causes remain `unknown` even when a `reconcile=false` representation
is present.
Canonical IDs, normalized identity uniqueness, and final scope validation remain
owned by #43. The normalizer must consume reconciled records and must not implement
a second raw duplicate merge path.

Phasing ban đầu qua #8, #38, #43 và #52 được giữ làm lịch sử kiến trúc. Các module loader,
normalizer/reconciliation, direct builder, inference và parser CLI hiện được kiểm thử cùng
nhau bằng manifest-backed synthetic fixture. CLI không bỏ qua loader policy: collection time
không rõ vẫn cần input tường minh. Đối chiếu cùng snapshot với bộ SEAMLESS thực tế và các
đánh giá M2 còn lại tiếp tục theo issue ownership riêng.

## Attack Semantics (Issue #63)

The implemented semantic layer lives in `src/engine/semantics/` and reads
[attack_semantics.yml](../configs/attack_semantics.yml). Its public interfaces,
runtime predicate meanings, limitations and acceptance-test mapping are documented in
[Attack Semantics implementation](attack-semantics-implementation.md).
The authoritative layering decision is [ADR-0008](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0008-structural-graph-attack-semantics-layering.md);
[ADR-0007](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md) owns the separate data/telemetry evaluation boundary.
Canonical structural graph records and `maut_v1` remain unchanged. The evaluator
returns explicit scenario effects; applying them creates a new attack state without
modifying the snapshot. This layer does not execute attacks or infer observed activity.

## Quyết định thuật toán cần chốt

Dijkstra yêu cầu chi phí không âm. Nếu dùng chi phí cộng, xác định ý nghĩa và thang đo. Nếu dùng `-log(p)`, cần `0 < p <= 1` và giải thích giả định khi cộng log qua các bước; không coi xác suất chủ quan là xác suất đo được. Chi phí không có đơn vị thời gian thì không diễn giải thành phút/giờ.

Chốt Top-K là K đường đơn phân biệt theo edge IDs hay node IDs, cách xử lý hòa chi phí và các cạnh song song. Chốt choke point dựa trên tập đường nào, tập nguồn/đích nào, có loại nguồn/đích khỏi danh sách ứng viên không. Không chỉ báo centrality rồi kết luận đó là biện pháp giảm rủi ro tốt nhất; đo lại sau khi bỏ node/cạnh.

## Thay đổi contract

A và B review cùng PR khi đổi schema/profile. Tăng version khi phá tương thích; cập nhật fixture, validator và tài liệu. Ghi ADR từ [mẫu](templates/adr.md), có phương án thay thế và hệ quả. Parser và engine cần từ chối profile/schema chưa hỗ trợ thay vì ngầm chọn giá trị mặc định.
