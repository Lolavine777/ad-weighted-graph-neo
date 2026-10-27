# SEAMLESS: boundary principals và 551 Group trong BloodHound Legacy 4.0.3

- Ngày đo: 2026-10-01. Phạm vi: [#139](https://github.com/nairyuuu/ad-weighted-graph/issues/139).
- Dataset `seamless-v1`; raw schema-v3 nguyên bản, không convert.
- Project revision: `8c15993b2ac2ed491eda5dc4655e08e2eb478ec1`, HEAD của `origin/develop` khi tạo checkout nghiên cứu.
- Đối chứng: BloodHound Legacy **4.0.3**, Neo4j **4.1.13**. Đã truy vấn native database của **cả hai** clean runs trong [PR #130](https://github.com/nairyuuu/ad-weighted-graph/pull/130), không import Legacy lại.
- [Artifact quan sát đã lọc](../../reports/research/issue-139-seamless-boundary-legacy-403.json), [gói truy vấn chỉ đọc](../../reports/research/issue-139-seamless-boundary-legacy-403-queries.json), [helper đối soát Group](../../scripts/research/compare_group_identity_sets.py).

## 1. Tóm tắt điều hành

**Legacy lưu cả INTERACTIVE và IUSR dưới dạng placeholder có labels `[Base, Group]`, với identity nguyên dạng `SEAMLESS.INTERNAL-S-1-5-4` và `SEAMLESS.INTERNAL-S-1-5-17`.** Mỗi node chỉ có property `objectid`; không có `name`, `domain`, `is_boundary` hay raw provenance. Đây là node được materialize từ reference, không phải first-class object đã thu thập. Kết quả exact query và membership giống nhau trong hai database độc lập.

**551 Group được giải thích đầy đủ bằng tập định danh (identity set):** raw có 550 records nhưng chỉ 549 `ObjectIdentifier` duy nhất. Users xuất hiện hai lần tại `#/groups/6` và `#/groups/549`. Legacy giữ đủ 549 collected identities và bổ sung đúng hai identity referenced-but-uncollected nói trên: **550 − 1 + 2 = 551**. Không còn raw-only Group identity hoặc Legacy-only Group identity ngoài hai principal này.

Project cũng có 549 collected Group và hai boundary principal, nhưng identity và thông tin ngữ nghĩa khác cách lưu của Legacy. Project dùng SID toàn cục cho hai principal, `domain=NT AUTHORITY`, `is_boundary=true`, label INTERACTIVE/IUSR và provenance của cạnh. Khi so chuỗi ID nguyên dạng, chỉ **517/551** Group khớp. Sau **34 mapping có bằng chứng**, đủ 551 identity có đối ứng một-một, không dư/thiếu. Equality sau mapping chỉ áp dụng cho population Group đã đo; không chứng minh equality của metadata, toàn bộ node population hoặc tập cạnh.

Hai membership raw đều có trong Legacy: INTERACTIVE → Builtin Users (`S-1-5-32-545`), IUSR → IIS_IUSRS (`S-1-5-32-568`). Mỗi principal có một `MemberOf` đi ra, không có `MemberOf` đi vào, không có quan hệ trực tiếp khác. Hai cạnh cũng tồn tại trong canonical/project Neo4j, nên đóng góp vào chênh lệch **15.917 − 13.324 = 2.593** là **0**, sau mapping endpoints. Nguồn gốc phần chênh còn lại thuộc [#47](https://github.com/nairyuuu/ad-weighted-graph/issues/47), chưa được giải thích trong thí nghiệm này.

Chưa biết rejected-record count, thời lượng import và lịch sử xử lý từng cạnh của Legacy. Không có provenance raw trong Legacy để chứng minh bằng runtime trace mỗi lần `MERGE`. Không suy Group-shaped IUSR thành AD Group. Không sửa parser/Graph Contract để bắt chước đối chứng.

## 2. Câu hỏi nghiên cứu

| Câu hỏi | Kết luận và phạm vi bằng chứng |
| --- | --- |
| RQ1 — INTERACTIVE được biểu diễn thế nào? | `materialized_placeholder`: native node `[Base, Group]`, exact `objectid=SEAMLESS.INTERNAL-S-1-5-4`, chỉ property `objectid`; không bị drop hoặc fold vào Users. |
| RQ2 — IUSR được biểu diễn thế nào? | Đo độc lập cho thấy cùng dạng placeholder, exact `objectid=SEAMLESS.INTERNAL-S-1-5-17`. Không có `User` label; đây là biểu diễn importer, không xác nhận literal AD object type. |
| RQ3 — membership thực tế? | Một cạnh từ mỗi principal tới exact parent raw; `isacl=false`, incoming rỗng, mọi quan hệ trực tiếp khác rỗng. Project giữ cùng hai directed triples sau mapping. |
| RQ4 — tại sao 551 Group? | Hai lần export toàn tập chứng minh `549 collected + 2 placeholder = 551`; duplicate Users chỉ chiếm một stored identity. Giả thuyết duplicate-collapse + materialization của cả hai principal được xác nhận. |

RQ1 không dựa vào tên hiển thị: `name` thực tế là `null`. Chuỗi exact `objectid`, absence trong collected identity set và cạnh tới exact Users identity cùng xác định node INTERACTIVE cần điều tra.

RQ2 được kiểm tra riêng, gồm exact properties và cả hai chiều membership. Việc hai principal có cùng shape không biến IUSR thành một nhóm directory; SID và tài liệu Microsoft vẫn là căn cứ ngữ nghĩa.

RQ3 xác nhận chiều principal → parent bằng `startNode(r)`/`endNode(r)`, rồi đối chiếu parent với `ObjectIdentifier` của chính record chứa occurrence. Source importer hỗ trợ diễn giải đây là membership lấy trực tiếp từ `Members[]`; stored graph không có lịch sử xử lý để loại trừ mọi writer có thể đã `MERGE` cùng cặp.

RQ4 được chứng minh bằng difference sets, không suy từ tổng count. Tập `Legacy Group objectid − raw unique Group ObjectIdentifier` chỉ gồm hai qualified principals; tập ngược lại rỗng. Mapping canonical là bước đối soát riêng, không làm biến đổi input của Legacy.

## 3. Mô hình bằng chứng

Thí nghiệm dùng năm lớp bằng chứng, mỗi lớp trả lời một loại câu hỏi:

1. **Raw snapshot bất biến:** checksum, record và occurrence xác định điều gì thật sự được export. Nó không tự xác định semantics Windows hay trạng thái AD hiện tại.
2. **Project canonical:** loader/adaptation theo snapshot, reconciliation, normalization, builder và Contract validation cho biết dự án chấp nhận identity/quan hệ nào. [Scope audit](seamless-scope-identity.md) và [Graph Contract 1.3.0](../../configs/contract.yml) xác định policy đã chấp nhận.
3. **Project Neo4j:** structural projection của canonical nodes/edges; kiểm chứng stored endpoints, `graph_digest`, boundary properties và provenance. Assessment không phải cạnh traversal.
4. **Legacy Neo4j:** quan sát độc lập trên cùng raw, giữ nguyên identity strings và stored multiplicity. Nó cho biết importer đã lưu gì, không định nghĩa policy dự án hoặc chứng minh toàn bộ raw được diễn giải đúng.
5. **Microsoft:** chuẩn ngữ nghĩa SID/account/group giúp diễn giải shape của graph; không thay thế quan sát trên snapshot.

Hai track độc lập:

```text
Track A: raw SEAMLESS → loader/adaptation → reconciliation → normalization
         → canonical graph → Contract validation → project Neo4j
Track B: raw SEAMLESS unchanged → BloodHound Legacy 4.0.3 → Neo4j 4.1.13
```

Canonical output chỉ phục vụ Track A và phép đối soát; không được dùng làm input cho Legacy. BloodHound là **observational reference**, không phải ground truth, không tham gia production parser path. [Ontology identity/asset](identity-asset-ontology.md) là tài liệu nghiên cứu riêng; không dùng các semantic facets đề xuất để đổi structural kind của thí nghiệm.

## 4. Môi trường và khả năng tái lập

| Thành phần | Giá trị đã pin / nguồn |
| --- | --- |
| Snapshot | `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` |
| Manifest | `data/samples/manifests/seamless-raw-v1.json`, sáu file, 11.371.828 bytes |
| Raw local | Checkout gốc `data/raw/SEAMLESS`; worktree truy cập qua `../../data/raw/SEAMLESS` |
| Project | `8c15993b2ac2ed491eda5dc4655e08e2eb478ec1`, Contract `1.3.0`, profile `unit`, `fail_fast` |
| Canonical JSON mới | SHA-256 `f70c773c828bce481acec1f416c6272718bb4bf4798150c4642642b75bfa8944` |
| Project Neo4j | `2026.08.1`, image ID `sha256:d8f4c156caa3af76499134947deb11d13042e471d9733060449f2a01eb7a248e`; container riêng `issue139-project-neo4j`, HTTP/Bolt `37474/37687` |
| Legacy release | `BloodHound-linux-x64.zip` 4.0.3, SHA-256 `2321bcf59fc695ef50c4c540af7c4f76343e9ea8d1989ed0d30f33b705147d25`; cache local đã hash lại và khớp PR #130 |
| Source Legacy | [`b54c418ef83fe5856ae3fe6317a20f2368a6378c`](https://github.com/SpecterOps/BloodHound-Legacy/tree/b54c418ef83fe5856ae3fe6317a20f2368a6378c), `package.json` ghi 4.0.3 |
| Legacy Neo4j | `4.1.13`, `neo4j@sha256:1f08dd79d877776e2501ba77d8b4c5354e8953d603fcae31df6b7b2c61685bc0`; Docker inspect và `dbms.components()` khớp |
| Legacy initial | `bh-legacy-403-neo4j`, container `c6d35fa9bfbd6b9b67bc4090c943a4090f6c377ec1239307085e44faf2eee865`, tạo `2026-09-27T16:30:43.480665505Z`, HTTP/Bolt `17474/17687` |
| Legacy clean rerun | `bh-legacy-403-neo4j-rerun`, container `644315813dbf44ba39b8299dee14d0ae8fc6a1d26a4d1d8176a90f81b8bd4ea4`, HTTP/Bolt `27474/27687`; thời điểm tạo có trong artifact |
| Baseline cũ | [Report compatibility ở head PR #130](https://github.com/nairyuuu/ad-weighted-graph/blob/32a9b49573b09431ec13f6a6e823923ed366e164/docs/research/seamless-legacy-pre41-compatibility.md), [artifact hai clean runs](https://github.com/nairyuuu/ad-weighted-graph/blob/32a9b49573b09431ec13f6a6e823923ed366e164/reports/baselines/seamless-legacy-403-unchanged.json) |

Manifest verification trước phân tích trả nguyên output `{"issues": [], "status": "verified"}`. Collection time trong manifest là `null`. Project dùng policy `assumed`, timestamp `2026-10-01T00:00:00Z`; đây là mốc quy ước tái lập, không phải thời gian thu thập được quan sát. `--created-at` chỉ ghi thời gian export. Không lấy timestamp từ tên file hoặc filesystem.

Docker ban đầu chưa chạy; sau khi chủ repo bật Docker, hai container/volume Legacy cũ được tìm thấy và khởi động lại. Không có upload/convert/import Legacy mới. Binding input/version của run gốc lấy từ #130; identity/membership hiện tại được kiểm tra trực tiếp ở cả hai database. Database không tự lưu snapshot hash nên phải giữ evidence chain từ run gốc, container identity và kết quả kiểm tra lại; count trùng không tự thay thế chain này.

Project service có sẵn không có `Canonical` nodes lúc kiểm tra. Do đó phép đo mới dùng **container riêng**, import canonical JSON đã validate; không ghi graph mới vào service chung. [PR #148](https://github.com/nairyuuu/ad-weighted-graph/pull/148) vẫn là bằng chứng lịch sử theo revision đã ghi: pre-merge JSON `01a68b08...` đã import, final JSON `41fdff96...` chưa reimport ở run ấy. Không đổi nhãn các digest này thành digest của phép đo hiện tại.

**Lịch sử 4.0.1 được giữ nguyên.** `docs/research/issue-139-seamless-bloodhound-401.md` không tồn tại trong current `develop` hoặc lịch sử Git local tìm được; fetch file ở revision được comment cũ nêu trả 404. [Comment kết quả 401](https://github.com/nairyuuu/ad-weighted-graph/issues/139#issuecomment-5882620524) và [bổ sung runtime 401](https://github.com/nairyuuu/ad-weighted-graph/issues/139#issuecomment-5882656862) là liên kết lịch sử: fail-fast lỗi ở revision cũ, diagnostic 3.366/53.703 và native 401 chưa chạy. Báo cáo này không dựng lại file đã mất, không rewrite hoặc relabel kết quả đó thành 403.

## 5. Bằng chứng từ raw data

| Principal | Occurrence exact | Quan sát | Parent exact |
| --- | --- | --- | --- |
| INTERACTIVE | `20210920185958_groups.json#/groups/6/Members/3/MemberId` | `MemberId=SEAMLESS.INTERNAL-S-1-5-4`, `MemberType=Group` | `SEAMLESS.INTERNAL-S-1-5-32-545`, `USERS@SEAMLESS.INTERNAL` |
| IUSR | `20210920185958_groups.json#/groups/8/Members/1/MemberId` | `MemberId=SEAMLESS.INTERNAL-S-1-5-17`, `MemberType=Group` | `SEAMLESS.INTERNAL-S-1-5-32-568`, `IIS_IUSRS@SEAMLESS.INTERNAL` |

Kiểm tra `ObjectIdentifier` và `Properties.objectid` của toàn bộ 3.369 first-class records trong sáu file cho cả bare SID và qualified ID: **0 collected objects** cho mỗi principal. Điều này không có nghĩa identity không tồn tại trong Windows; nó chỉ không có object record riêng trong snapshot này.

Parent Users có DN `CN=Users,CN=Builtin,DC=seamless,DC=internal`; IIS_IUSRS có DN `CN=IIS_IUSRS,CN=Builtin,DC=seamless,DC=internal`. Parent membership được xác định bằng record `ObjectIdentifier`, occurrence chứa `MemberId`, SID và DN; tên hiển thị chỉ hỗ trợ đọc. Các mảng `Members` có lần lượt 4 và 2 phần tử; chỉ một phần tử ở mỗi parent trỏ tới principal đang nghiên cứu.

Duplicate Users ở `#/groups/549` có cùng `ObjectIdentifier`, nhưng `Members=[]`; `#/groups/6` chứa bốn members và occurrence INTERACTIVE. Reconciliation hiện tại giữ hai representations, đều phân loại `full`, với `duplicate_cause=unknown`. Không suy nó là supplemental record có nguồn gốc đã xác minh. Loader/reconciler chọn `#/groups/549` làm provenance đại diện trước `#/groups/6`; **locator đại diện không phải locator của membership**. Nguyên nhân upstream tạo duplicate vẫn chưa biết, dù tác động count/identity đã đo được.

## 6. Biểu diễn của project

Project resolve collected canonical IDs/aliases trước. Chỉ khi không có collected node phù hợp, builder mới materialize principal trong allowlist được hỗ trợ. Nếu collected kind mâu thuẫn hoặc reference không hỗ trợ/thiếu scope, pipeline vẫn fail closed. Không tạo boundary chung cho mọi SID chỉ để hoàn tất import.

Hai node canonical thực tế:

```json
[
  {"domain":"NT AUTHORITY","id":"S-1-5-17","is_boundary":true,"kind":"Group","label":"IUSR"},
  {"domain":"NT AUTHORITY","id":"S-1-5-4","is_boundary":true,"kind":"Group","label":"INTERACTIVE"}
]
```

SID toàn cục của hai principal không cần DNS prefix. `domain=NT AUTHORITY` diễn đạt authority/ngữ nghĩa Windows; `is_boundary=true` công bố endpoint chưa được thu thập first-class. Node không có GUID, DN hoặc metadata thu thập giả.

`kind=Group` là **vai trò endpoint cấu trúc** từ `MemberType=Group`. Microsoft xác định INTERACTIVE là special identity cho interactive logon, còn IUSR là account dùng cho IIS; [MS-DTYP Well-Known SID Structures](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/81d92bba-d22b-4a8c-908a-554ab29148ab) phân biệt hai nghĩa này. [MS-ADTS IIS_IUSRS Group Object](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6108abed-3fb7-4c6a-b5fc-a755d60922f4) mô tả membership của `NT AUTHORITY\IUSR` trong IIS_IUSRS. Policy IUSR chỉ hỗ trợ source của `MemberOf` từ `Members[].MemberId` với `MemberType=Group`; không mở rộng nó thành arbitrary Group ACE principal. [Special Identity Groups](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-special-identities-groups) cung cấp ngữ cảnh Windows bổ sung.

Users/IIS_IUSRS là collected Builtin Groups; canonical parent dùng scope Domain SID quan sát được:

```text
S-1-5-4  -> domain:sid:S-1-5-21-1271839998-3495686680-2211690266:S-1-5-32-545
S-1-5-17 -> domain:sid:S-1-5-21-1271839998-3495686680-2211690266:S-1-5-32-568
```

Đây là composite namespace key của project, không phải Windows SID bị nối thêm Domain SID. Scope rule và boundary rule giải quyết hai vấn đề khác nhau: Builtin identities cần namespace của collected object; hai globally well-known principals có SID riêng.

Hai canonical edge IDs lần lượt là `sha256:4eee7e7329d4152c4474f3ec1d131cb1e34c7d8a634c14c34c6da777533c8516` và `sha256:56fa22e80f7a76622f1c7a60d1663706e7d59033071feedca0b9c39754bdc2f6`. Mỗi cạnh có một positive provenance: snapshot-bound `raw_file`, parent `record_id`, `attribute=Members[].MemberId`, collector `sharphound`, timestamp/status/reason. Không có `derivation` trên hai cạnh này.

Canonical provenance không trực tiếp chứa JSON array index. Exact pointer `/groups/6/Members/3` và `/groups/8/Members/1` là kết quả audit raw sidecar trong báo cáo/artifact, không được giả là property sẵn có của graph. Với duplicate Users, phải mở đúng raw record/lineage; không chỉ dùng representative locator.

Projection mới lưu `[Canonical, Group]`, `id`, `kind`, `label`, `domain`, `is_boundary`, `snapshot_id`, `graph_digest`; cạnh giữ `source`, `target`, ID và `provenance_json`. Query cho thấy đủ **53.774/53.774** relationships có provenance, và tất cả 3.370 nodes/53.774 relationships mang digest `f70c773c...`. Tập 551 Group IDs trong Neo4j bằng canonical current. Ba `unknown` assessments không được nhập Neo4j; digest của assessments hiện tại là `cd1a285802ff98c51df23c2581bb0d6847673c2a74f438cbd2877f4d6377ec16`.

## 7. Biểu diễn của Legacy 4.0.3

Discovery `CONTAINS` trả đúng một candidate cho mỗi SID trong rerun. Sau đó mọi query dùng exact `objectid`; initial được kiểm tra riêng bằng các exact IDs đã phát hiện.

Output exact node query ở cả hai runs:

```json
[
  {"labels":["Base","Group"],"objectid":"SEAMLESS.INTERNAL-S-1-5-4","name":null,
   "properties":{"objectid":"SEAMLESS.INTERNAL-S-1-5-4"}}
]
```

```json
[
  {"labels":["Base","Group"],"objectid":"SEAMLESS.INTERNAL-S-1-5-17","name":null,
   "properties":{"objectid":"SEAMLESS.INTERNAL-S-1-5-17"}}
]
```

Output outgoing query cho INTERACTIVE:

```json
[
  {"labels":["Base","Group"],"objectid":"SEAMLESS.INTERNAL-S-1-5-4","name":null,
   "type":"MemberOf","parent_labels":["Base","Group"],
   "parent_objectid":"SEAMLESS.INTERNAL-S-1-5-32-545",
   "parent_name":"USERS@SEAMLESS.INTERNAL","relationship_properties":{"isacl":false}}
]
```

Output outgoing query cho IUSR:

```json
[
  {"labels":["Base","Group"],"objectid":"SEAMLESS.INTERNAL-S-1-5-17","name":null,
   "type":"MemberOf","parent_labels":["Base","Group"],
   "parent_objectid":"SEAMLESS.INTERNAL-S-1-5-32-568",
   "parent_name":"IIS_IUSRS@SEAMLESS.INTERNAL","relationship_properties":{"isacl":false}}
]
```

**Incoming query trả `[]` cho từng principal ở từng run.** All-direct query trả một row mỗi principal: `type=MemberOf`, source chính là qualified principal, target chính là qualified parent trên, `other_labels=[Base,Group]`, cùng `parent_name` ở trường `other_name`, `relationship_properties={isacl:false}`. Output đầy đủ với exact keys được lưu trong `legacy_observations.principals` của artifact. Không có cạnh trực tiếp khác hoặc cạnh đảo chiều.

Phân loại chính **`materialized_placeholder`**: node hiện hữu trong stored graph, chưa có first-class raw object, thiếu mọi descriptive properties ngoài `objectid`. Phân loại phụ **`implicit_principal`**: principal được biểu diễn thông qua reference trước khi có collected object. Không phân loại `collected_identity`, `relationship_dropped` hoặc `rejected`: node/cạnh native đã quan sát được. `external_representation` không được coi là trạng thái Legacy đã khai báo, vì không có property external/boundary. Prefix thể hiện namespace của stored identity; không chứng minh `domain=SEAMLESS.INTERNAL` là property hoặc authority Windows của node.

Source 4.0.3 củng cố cơ chế: [`buildGroupJsonNew`](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js#L3) gom `Members` theo `MemberType`, dùng `MemberId` làm source và `ObjectIdentifier` của Group làm target, tạo `MemberOf` với `isacl=false`. Template [`baseInsertStatement`](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js#L525) thực hiện `MERGE` endpoints theo `objectid`, rồi gán labels theo type trước khi `MERGE` cạnh. Vì vậy endpoint có thể có `Group` label dù không có object record để nạp `Properties`. Property-only Group import cũng `MERGE` theo `objectid`, phù hợp với duplicate collapse.

Đây là diễn giải kết hợp **raw + stored graph + source đã pin**, không chỉ suy từ display name. Không có importer instrumentation của run cũ; source code không thay thế log chứng minh từng thao tác ở runtime hoặc rejected-record counter.

## 8. Ánh xạ identity và trace từ đầu đến cuối

Mapping exact của hai principal có bằng chứng raw occurrence + globally well-known SID + exact Legacy query. Không dùng discovery substring làm mapping cuối; không có heuristic cắt mọi prefix tới SID cuối.

### INTERACTIVE / `S-1-5-4`

| Khía cạnh | Raw SEAMLESS | Project canonical | Project Neo4j | Legacy 4.0.3 |
| --- | --- | --- | --- | --- |
| Principal | Reference INTERACTIVE theo SID | INTERACTIVE | `label=INTERACTIVE` | `name=null`; xác định bằng exact identity |
| Raw locator | `groups.json#/groups/6/Members/3/MemberId`¹ | Audit sidecar trỏ occurrence đó | Theo graph digest và provenance cạnh; không có pointer property | Không lưu raw locator |
| `MemberId` quan sát được | `SEAMLESS.INTERNAL-S-1-5-4` | Adapt thành SID toàn cục | `source=S-1-5-4` | Stored `objectid` bằng nguyên raw reference |
| `MemberType` | `Group` | Vai trò structural Group | `kind=Group` | Group label từ type importer |
| Có first-class raw object | Không, count 0 | Boundary; không giả collected | Không bổ sung object evidence | Placeholder; không có `Properties` collected |
| Canonical/stored identity | Qualified reference | `S-1-5-4` | `id=S-1-5-4` | `objectid=SEAMLESS.INTERNAL-S-1-5-4` |
| Label/kind | Không có object record | `Group`, INTERACTIVE | `[Canonical,Group]` | `[Base,Group]` |
| Domain/namespace | Prefix `SEAMLESS.INTERNAL` | `NT AUTHORITY` | `domain=NT AUTHORITY` | Qualified namespace; property domain vắng mặt |
| Boundary/external status | Uncollected reference | `is_boundary=true` | `is_boundary=true` | Không có property tương ứng; không suy false |
| Parent membership target | `SEAMLESS.INTERNAL-S-1-5-32-545` | Domain-SID-scoped Users key | Cùng canonical parent ID | Cùng qualified raw parent ID |
| Hướng membership | Member thuộc parent chứa array | INTERACTIVE → Users | Một cạnh đi ra; không incoming | Một cạnh đi ra; không incoming |
| Khả năng truy provenance | Pointer exact ở raw | Một positive provenance, snapshot/record/attribute | `provenance_json`, `graph_digest` | Chỉ `isacl=false` trên cạnh; không raw provenance |
| Diễn giải | Membership reference | Boundary có ngữ nghĩa công bố | Projection giữ nguyên boundary | `materialized_placeholder` / `implicit_principal` |
| Trạng thái bằng chứng | Đã đo | Đã chạy/validate | Đã import/query current | Đã query native cả hai runs |

¹ `groups.json` trong hai bảng là cách viết gọn của `20210920185958_groups.json`, không phải input đã đổi tên.

### IUSR / `S-1-5-17`

| Khía cạnh | Raw SEAMLESS | Project canonical | Project Neo4j | Legacy 4.0.3 |
| --- | --- | --- | --- | --- |
| Principal | Reference IUSR theo SID | IUSR | `label=IUSR` | `name=null`; xác định bằng exact identity |
| Raw locator | `groups.json#/groups/8/Members/1/MemberId` | Audit sidecar trỏ occurrence đó | Theo provenance cạnh/digest; không lưu pointer | Không lưu raw locator |
| `MemberId` quan sát được | `SEAMLESS.INTERNAL-S-1-5-17` | Adapt thành SID toàn cục | `source=S-1-5-17` | Stored `objectid` bằng nguyên reference |
| `MemberType` | `Group` | Group-shaped membership source | `kind=Group` | Group label từ importer type |
| Có first-class raw object | Không, count 0 | Boundary, không collected AD Group | Không có GUID/DN giả | Placeholder, không có collected properties |
| Canonical/stored identity | Qualified reference | `S-1-5-17` | `id=S-1-5-17` | `objectid=SEAMLESS.INTERNAL-S-1-5-17` |
| Label/kind | Không có object record | `Group`, IUSR | `[Canonical,Group]` | `[Base,Group]`; không có `User` label |
| Domain/namespace | Prefix `SEAMLESS.INTERNAL` | `NT AUTHORITY` | `domain=NT AUTHORITY` | Qualified namespace; domain property vắng mặt |
| Boundary/external status | Uncollected reference | `is_boundary=true` | `is_boundary=true` | Property vắng mặt, không suy false |
| Parent membership target | `SEAMLESS.INTERNAL-S-1-5-32-568` | Domain-SID-scoped IIS_IUSRS key | Cùng canonical parent ID | Cùng qualified raw parent ID |
| Hướng membership | Member thuộc parent chứa array | IUSR → IIS_IUSRS | Một cạnh đi ra; không incoming | Một cạnh đi ra; không incoming |
| Khả năng truy provenance | Pointer exact | Một positive provenance; không ACE extrapolation | `provenance_json` và digest | Không raw provenance |
| Diễn giải | IIS account bị export như Group endpoint | Vai trò membership hạn chế; không literal AD type | Projection giữ policy đã chấp nhận | Placeholder theo Group reference; không định nghĩa lại IUSR |
| Trạng thái bằng chứng | Đã đo | Đã chạy/validate | Đã import/query current | Đã query riêng ở cả hai runs |

Mapping parent dựa trên **observed collected Group + observed Domain SID** trong cùng snapshot, qua adapter/normalizer đang được chấp nhận. Không dùng display name Users/IIS_IUSRS để quyết định identity. Với 549 collected Group, cặp raw/adapted records giữ original `ObjectIdentifier` và canonical ID; duplicate representations cùng ánh xạ một identity trước khi so tập. Với hai boundary, mapping bổ sung riêng theo evidence trên, không nhập chúng vào collected population.

## 9. Phân tích forensic về 551 Group nodes

### 9.1 Population và duplicate

| Phép đo | Giá trị | Căn cứ |
| --- | ---: | --- |
| Raw Group records | 550 | Độ dài `groups[]`, manifest verified |
| Raw unique Group `ObjectIdentifier` | 549 | Set comparison chuỗi nguyên dạng |
| Representation dư do duplicate identity | 1 | Users ở indices 6 và 549 |
| Project collected Group | 549 | Reconciliation/normalization; `is_boundary=false` |
| Project boundary Group | 2 | SID `S-1-5-4`, `S-1-5-17`; `is_boundary=true` |
| Project total Group | 551 | Hai population trên được báo riêng |
| Legacy stored Group | 551 | Full query ở mỗi database, 551 `objectid` duy nhất |
| Raw collected identities thiếu ở Legacy | 0 | `raw unique IDs − Legacy IDs = ∅` |
| Legacy IDs ngoài raw collected | 2 | Chỉ qualified INTERACTIVE và IUSR |

`Legacy − raw` thực tế:

```json
["SEAMLESS.INTERNAL-S-1-5-17", "SEAMLESS.INTERNAL-S-1-5-4"]
```

`raw − Legacy` thực tế: `[]`. Mọi collected raw identity có một Legacy Group counterpart; Users trùng chỉ có một stored `objectid`. Không có Group thứ ba được materialize trong difference set của snapshot này.

```text
550 raw Group records
→ 549 unique collected identities (Users có 2 representations)
→ 549 identities đều có trong Legacy
→ thêm 2 referenced-but-uncollected placeholders
→ 551 stored Legacy Group identities
```

Đây là chứng minh **nguồn gốc population** bằng raw/stored identity sets. Nguyên nhân collector tạo duplicate, thứ tự property overwrite bên trong run Legacy và lịch sử từng `MERGE` vẫn chưa được đo; không cần biết những điều đó để chứng minh phép đếm tập.

### 9.2 So tập project/Legacy trước và sau mapping

| Lớp đối soát | Common | Project-only | Legacy-only | Mapping chưa giải |
| --- | ---: | ---: | ---: | ---: |
| Chuỗi ID lưu nguyên dạng | 517 | 34 | 34 | Chưa áp dụng mapping |
| Sau mapping một-một đã kiểm toán | 551 | 0 | 0 | 0 |
| Trong common đã map: collected | 549 | 0 | 0 | 0 |
| Trong common đã map: boundary | 2 | 0 | 0 | 0 |

34 identity strings khác nhau được giải thích riêng:

- **29 collected Builtin Groups:** qualified raw/Legacy ID → canonical `domain:sid:<observed-domain-sid>:<sid>`. Scope còn nguyên ở canonical target; không cắt thành bare Builtin SID.
- **3 collected globally well-known Groups:** qualified `S-1-5-9`, `S-1-1-0`, `S-1-5-11` → SID toàn cục. Đây là collected records, khác population với hai boundary.
- **2 boundary principals:** qualified `S-1-5-4`, `S-1-5-17` → SID toàn cục; mapping có raw relationship evidence nhưng không có first-class object.

517 strings đã giống nhau được giữ nguyên. Tổng: `517 + 29 + 3 + 2 = 551`. Không mất namespace trong bảng input; full mapping giữ cả source string và target string, lưu local tại `.cache/identity-mapping.json`.

Digest tập được tính bằng `sha256(json.dumps(sorted(exact_strings), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))`, không newline, không đổi hoa/thường hoặc trim:

| Tập | SHA-256 |
| --- | --- |
| Raw unique collected Group IDs | `6558d70de958be9294b683cfe5736fddadb5ee5fe6273337ea4993d1f09831d8` |
| Project collected | `1ac31dadc6fdf29f754888b4660e1282d80179c7067f697f25c5b702b8b81ff3` |
| Project boundary | `8cd9493687b4b2a70801460d1fc13767c9a372f219dded52ca1a265165a1ef9b` |
| Project total / Legacy sau mapping | `41d8c593b33785b8024f1d5960fa37284d99d17b22246d0b3ad75e8bbf3cd606` |
| Legacy stored nguyên dạng | `9417099e7a3aa6b4439c58c7c428d6e5f73dac62244461e614227a39f0a45f1d` |

Cả hai native Legacy exports có cùng Group identity set. Digest equality sau mapping xác nhận kết quả set comparison đã thực hiện; checksum không tự xác nhận mapping đúng. Bằng chứng mapping nằm ở raw/adapter/contract và exact queries.

**`same total count != same identity set`:** cardinality chỉ cho biết số phần tử. Hai tập cùng 551 có thể thay identity A bằng B và vẫn cùng count. Ở thí nghiệm này, đã đo 34 khác biệt biểu diễn nguyên dạng và giải quyết chúng bằng mapping có scope; equality về Group counterparts được chứng minh thêm bằng difference sets. Nó vẫn không chứng minh node properties tương đương: hai placeholders Legacy không có `domain`/`is_boundary`/label diễn giải như project.

## 10. So sánh membership

| Population / phép đo | Project canonical và Neo4j mới | Legacy mỗi run | Kết luận |
| --- | ---: | ---: | --- |
| Toàn bộ stored `MemberOf` | 13.324 | 15.917 | Chênh count 2.593; khác lớp semantics có thể tồn tại |
| INTERACTIVE outgoing `MemberOf` | 1 | 1 | Cùng parent Users sau mapping |
| IUSR outgoing `MemberOf` | 1 | 1 | Cùng parent IIS_IUSRS sau mapping |
| Incoming `MemberOf` tới hai principal | 0 | 0 | Đo trực tiếp, không đổi unknown thành 0 |
| Mọi cạnh khác trực tiếp quanh hai principal | 0 | 0 | All-direct query / canonical edge scan |
| Boundary unique directed triples | 2 | 2 | Không có stored multiplicity bổ sung trong subset |
| Boundary project-only / Legacy-only triples sau mapping | 0 / 0 | 0 / 0 | Subset equality có bằng chứng |

Trong full Legacy export `MemberOf`, 15.917 stored rows cũng là 15.917 unique `(source,target)` pairs. Điều này loại trừ duplicate storage pairs trong export đo được, **không** xác nhận tất cả đều là direct raw membership. Project Contract định nghĩa `MemberOf` là direct-only; broader Legacy semantics chưa được review ở #47.

Hai raw occurrences được giữ thành hai canonical edges và hai Legacy edges. Node materialization là thao tác importer-derived; **không vì node là placeholder mà tự gọi membership là inferred/effective**. Membership pairs tương ứng trực tiếp với raw `Members[]`, và source 4.0.3 sinh chính các cặp ấy. Stored `isacl=false` chỉ xác định đây không phải ACL edge; nó không mã hóa provenance hoặc chứng minh direct semantics của mọi `MemberOf` khác.

Đóng góp cô lập vào chênh count:

```text
Δboundary = 2 Legacy − 2 project = 0
Δcòn_lại = (15.917 − 2) − (13.324 − 2) = 15.915 − 13.322 = 2.593
```

Không có thêm membership quanh hai principal để giải thích phần chênh này. Full MemberOf rows đã lưu local phục vụ #47; cần mapping mọi endpoint, raw traces, direct/effective/derived classification và scope review trước khi công bố full difference sets. Không gán toàn bộ 2.593 cho membership closure, collector/session time hoặc parser bug bằng phỏng đoán.

## 11. Các insight quan trọng

1. **Cùng 3.370 nodes chỉ là equality về cardinality.** Cả hai Legacy runs và current project có tổng này, nhưng 34 Group ID strings khác nhau ngay trong subset đã đo. Group counterpart equality cần mapping và full set comparison; toàn bộ identity population ngoài Group vẫn chưa được đối soát. #82 phải lưu population và mapping, không dùng tổng node count làm acceptance thay thế.
2. **551 Group che giấu phép cộng và trừ ở các tầng khác nhau.** Raw có 550 records, reconciliation có 549 collected identities, còn stored graph có 551 sau thêm hai referenced principals. Giả thuyết được xác nhận bằng `Legacy−raw`/`raw−Legacy`, không chỉ bằng phép tính khớp số. Demo nên trình bày cả ba tầng.
3. **Importer output có thể có identity không có first-class raw object.** Hai Legacy nodes chỉ có `objectid`, incoming rỗng, outgoing trỏ đúng raw parents. Source endpoint `MERGE` giải thích placeholder được tạo từ relationship reference. Vì vậy việc node tồn tại trong Neo4j không chứng minh collector đã lấy LDAP object tương ứng hoặc nạp đầy đủ properties.
4. **Node có Group label vẫn có thể thiếu semantic metadata.** Không có Base-only nodes trong baseline nhưng hai placeholders vẫn thiếu `name`, `domain`, boundary flag. Label coverage không phải object completeness. Chuyển absence `is_boundary` thành `false` sẽ làm sai đối soát metadata với project.
5. **Provenance cho phép kiểm toán boundary materialization nhưng cần hiểu độ hạt.** Hai project edges giữ snapshot/parent/attribute và file digest; raw audit truy được exact member occurrence. Duplicate representative `#/groups/549` không chứa INTERACTIVE. Canonical provenance không lưu array index nên báo cáo sidecar/lineage là phần quan trọng của chain; không được hứa khả năng drill-down pointer có sẵn trong Legacy hoặc graph property.
6. **Xem IUSR như literal AD Group làm mất nghĩa account/authority và giới hạn evidence.** Microsoft xác định account IIS, raw export cho `MemberType=Group`, project chỉ giữ endpoint role trong membership. Legacy cũng gán Group label từ type; đây không phải bằng chứng độc lập xác nhận AD object class. Suy thêm ACE permissions từ shape này sẽ vượt policy được chấp nhận ở #148.
7. **Scope và namespace khác biệt là khác biệt biểu diễn có thể đối soát.** 29 scoped Builtin mappings giữ observed Domain SID; 5 qualified global mappings phân biệt 3 collected và 2 boundary. Cắt mọi ID về SID cuối sẽ phá scope khi có nhiều domain/host. #47 cần mapping tường minh và giữ raw string, không tự normalize bằng suffix.
8. **Hai boundary principals không giải thích discrepancy MemberOf.** Exact directed subset giống nhau và không có cạnh khác quanh chúng, nên contribution là 0. Đây là measurement đủ an toàn để #47 loại subset này khỏi phần chưa giải; nguyên nhân 2.593 còn lại vẫn unknown.
9. **Legacy là reference có giới hạn, không phải oracle correctness.** Tập Group counterpart đã khớp nhưng properties/provenance khác nhau; Legacy còn lưu relationship kinds ngoài M1. Difference về namespace, boundary annotation và metadata thiếu là khác biệt policy/representation, chưa phải implementation bug của project. Không có failing reproduction vi phạm accepted Contract được phát hiện trong scope này; điều đó không chứng minh toàn parser đúng.
10. **Demo có thể kết luận hẹp, có thể kiểm chứng.** #48 có thể cho thấy snapshot unchanged, `550−1+2`, mapping 34 ID strings, hai exact memberships và provenance project. Nó không thể dùng kết quả này để nghiệm thu full #47 reconciliation, engine/ranking integration, toàn Week 3 hoặc CE parity; scope #48 hiện hành còn các hard gates riêng.

## 12. Giới hạn và các điểm chưa biết

- Legacy DB đã truy cập được ở phiên này; không còn blocker thiếu native node-level observations. Khả năng chạy GUI mới không được thử và không cần cho phép đo trên stored DB.
- Version/input binding của import gốc dựa trên evidence #130 và container lưu lại; Neo4j không tự giữ manifest/snapshot hash. Hash release cache và image/runtime được xác nhận lại; không giả claim đã tracing lại upload trong 2026-10-01.
- Legacy không có raw provenance hoặc importer event history trên hai nodes/edges; không giả lập các trường đó. Kết hợp source/raw/graph giải thích direct pair emission, chưa chứng minh từng internal operation trong run cũ.
- `name=null`, `domain` và `is_boundary` thiếu ở Legacy là trạng thái không có dữ liệu; không suy domain từ prefix thành property, không chuyển boundary thành `false`.
- Duplicate identity đã chứng minh và collapse đã đo; `duplicate_cause=unknown` ở project, nguồn gốc upstream/collector và property overwrite order của Legacy vẫn chưa biết.
- Collection time raw, rejected-record count, import duration là unknown/null. Policy timestamp của project là `assumed`, không phải observed collection time.
- Phần 2.593 MemberOf ngoài boundary, discrepancy GenericAll và các quan hệ khác chưa có disposition trong #139. Full node population ngoài Group và full edge identity sets chưa được đối soát/review.
- Không chứng minh trạng thái AD hiện tại, quyền thực thi IIS hoặc domain compromise; không xác nhận CE parity.
- Full exports/mapping chứa identities nên giữ local theo [data policy](../../data/README.md). Artifact commit chỉ giữ aggregates/digests và hai well-known references/parents đã thuộc scope công bố; không có tên user, session, IP, ACE dump hoặc credential.
- Helper chỉ so exact Group identity và partition project. Nếu mapping thiếu, `project_only`/`legacy_only` là phần **chưa ghép**, không tự chứng minh absence; `status=unknown`. Nó không chấp nhận nhiều source map vào một target, không thay canonical ID đã khớp, không tự sửa khoảng trắng hoặc scope.

## 13. Bàn giao

### Cho #82

[#82](https://github.com/nairyuuu/ad-weighted-graph/issues/82) có thể dùng Legacy 4.0.3/Neo4j 4.1.13 unchanged baseline, 3.370/71.596 aggregate từ hai clean runs, và phép đo native mới: cả hai Group sets bằng nhau; exact principal properties và memberships bằng nhau; `549 collected counterparts + 2 placeholders = 551`. Current Track A có canonical/Neo4j digest pin riêng và 549/2 partition. Không dùng các count này để tick full baseline acceptance nếu exports chung, semantics hoặc review còn thiếu. PR #130 còn mở khi đọc scope.

### Cho #47

[#47](https://github.com/nairyuuu/ad-weighted-graph/issues/47) nhận full Group export và mapping **local** `.cache/legacy-groups.json`, `.cache/identity-mapping.json`, `.cache/group-comparison.json`; toàn MemberOf rows nằm trong `.cache/legacy-rerun-observations.json` dưới `memberof`. Chuyển qua nơi riêng được cấp phép; không commit export này. Digests và lệnh tái lập có trong artifact. Canonical current nằm `.cache/project-current.json`.

Disposition đã đủ bằng chứng: 34 raw string differences được map; Group identity-only difference sets sau map rỗng; hai boundary MemberOf triples common; contribution của boundary vào ΔMemberOf là 0. Disposition chưa đủ: full 2.593 difference, metadata absence của Legacy, membership ngoài subset và population ngoài Group. Không điền `is_boundary=false` cho placeholder để làm comparator chạy.

Comparator [reconcile_graph_baseline.py](../../scripts/reconcile_graph_baseline.py) hiện yêu cầu metadata/scope được review, gồm direct `MemberOf` semantics. Không tự khai báo toàn Legacy export là `m1-structural-v1`/direct để có verdict `MATCH`. Helper Group mới chỉ là analysis adapter độc lập, không thay gate này. #47 cần nhận all-node/all-edge exports hoặc truy vấn bổ sung cho các relationship kinds đang đối soát, kiểm toán ánh xạ endpoints, raw trace và stored multiplicity trước khi nghiệm thu full sets.

### Cho #48

Năm phát hiện an toàn để trình bày:

1. Sáu raw files unchanged, manifest/hash xác minh; hai track độc lập.
2. `550 records → 549 collected identities → +2 placeholders → 551 Group` có difference-set evidence ở cả hai Legacy runs.
3. 517 ID strings giống nhau, 34 cần mapping có scope; sau map Group counterpart sets khớp nhưng metadata không tương đương.
4. Hai exact memberships có ở cả hai bên, không đóng góp vào chênh MemberOf 2.593.
5. Project công bố boundary/provenance/assumed time, Legacy placeholder thiếu properties; IUSR Group-shaped không phải xác nhận AD Group.

Không claim: “BloodHound là ground truth”; “same node count means parity”; “551 Groups means identical Groups”; “Legacy behavior defines project policy”; “Legacy baseline is CE parity”; “đã giải thích toàn bộ MemberOf discrepancy”; “hai edges chứng minh AD hiện tại hoặc khả năng compromise”; “research report này hoàn tất #48”. [Scope #48 hiện hành](https://github.com/nairyuuu/ad-weighted-graph/issues/48) sau audit #158 yêu cầu full reviewed #47 reconciliation và final integrated develop package cùng các model/parameter/engine gates; báo cáo này chỉ đáp ứng handoff boundary identity.

### Trạng thái nghiệm thu #139

| Tiêu chí kỹ thuật hiện hành | Bằng chứng / trạng thái |
| --- | --- |
| Pin/verify snapshot và runtime | Đạt: manifest, cache release hash, inspect image và native version queries |
| Current fail_fast canonical validation/projection | Đạt: current develop revision, Contract 1.3.0, graph digest, isolated projection; assessments ngoài Neo4j |
| Native observations cho cả hai principal | Đạt ở cả hai databases, exact IDs/properties và membership hai chiều |
| Identity mapping và membership comparison | Đạt trong Group population và hai boundary memberships; full graph ngoài scope |
| Extra Group investigation | Đạt: full Group set difference, duplicate evidence, derivation `550−1+2` |
| Report/handoff, giữ lịch sử, không claim CE parity | Đạt: báo cáo 403 độc lập; lịch sử 401 chỉ cross-link, không relabel |
| Policy fail closed và raw unchanged | Không sửa production policy; raw verify trước/sau; tests accepted boundary được giữ nguyên |

Các deliverables kỹ thuật trong scope #139 đã có; **nghiệm thu workflow vẫn cần cross-review**, không tự đóng issue hoặc nghiệm thu #82/#47/#48. Không dùng việc đã giải quyết RQ1–RQ4 để chuyển unknown ngoài scope thành resolved.

## 14. Phụ lục tái lập

### 14.1 Checkout và inputs

Các lệnh đã chạy từ checkout gốc, giữ nguyên nhánh đang có và thay đổi chưa commit:

```powershell
git fetch origin develop
git worktree add .worktrees/issue-139 -b docs/139-seamless-legacy-403 origin/develop
```

Từ worktree, Python dùng virtual environment checkout gốc. Phiên bản interpreter/dependencies thực tế được ghi ở worklog kiểm chứng. Lệnh xác minh và CLI đã chạy:

```powershell
../../.venv/Scripts/python.exe -X utf8 scripts/snapshot_manifest.py verify ../../data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
../../.venv/Scripts/python.exe -X utf8 -m src.parser.cli --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 --raw-dir ../../data/raw/SEAMLESS --manifest-dir data/samples/manifests --time-policy .cache/time-policy.json --created-at 2026-10-01T00:00:00Z --error-policy fail_fast --output .cache/project-current.json --summary
```

Nội dung `.cache/time-policy.json` cần tạo trước, UTF-8, thư mục `.cache` giữ local:

```json
{"timestamp":"2026-10-01T00:00:00Z","status":"assumed","reason":"Mốc quy ước để tái lập phép đo #139; manifest không xác định thời gian thu thập, không suy từ tên file hoặc thời gian filesystem."}
```

CLI thực tế: `Nodes: 3370`, `Edges: 53774`, `Assessments: 3 (unknown=3)`, `warnings: 0; errors: 0`, profile `unit`; validate_graph đã chạy và pass. Digest bytes phụ thuộc revision/time policy/serialization; các identity set digests và edge IDs được so riêng.

### 14.2 Khởi động database lưu lại và xác minh release

```powershell
docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}'
docker inspect bh-legacy-403-neo4j-rerun bh-legacy-403-neo4j --format '{{.Name}}|{{.Id}}|{{.Image}}|{{json .Mounts}}|{{json .HostConfig.PortBindings}}'
docker start bh-legacy-403-neo4j-rerun ad-weighted-graph-neo4j-1
docker start bh-legacy-403-neo4j
Get-FileHash ../../.cache/.legacy-bloodhound/official-4.0.3/BloodHound-linux-x64.zip -Algorithm SHA256
```

Output: hai Legacy image IDs khớp pin, volumes còn tồn tại, containers khởi động thành công, release SHA-256 khớp bảng môi trường. Không in hoặc đưa Docker env chứa auth vào artifact. Khi tái lập ở máy không có databases cũ, dùng hướng dẫn clean native import tại report #130 đã pin: verify sáu raw files, database mới 0/0, official 4.0.3 upload nguyên sáu files, ghi run/input/version trước truy vấn. Không thay bằng canonical/converted input.

### 14.3 Exact Cypher của Legacy và kết quả

Gói truy vấn JSON giữ nguyên mọi statement/parameters đã dùng và tách `track=legacy`/`project`. Queries tổng hợp:

```cypher
CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;
MATCH (n) RETURN count(n) AS nodes, count(DISTINCT n.objectid) AS unique_objectids;
MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY labels;
MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY type;
MATCH (g:Group)
RETURN g.objectid AS objectid, g.name AS name, labels(g) AS labels, properties(g) AS properties
ORDER BY objectid;
MATCH (n) RETURN n.objectid AS objectid, labels(n) AS labels ORDER BY objectid;
MATCH (s)-[r:MemberOf]->(t)
RETURN s.objectid AS source, t.objectid AS target, properties(r) AS properties
ORDER BY source, target;
```

Kết quả ở mỗi Legacy database: `Neo4j Kernel`, `versions=[4.1.13]`, `edition=community`; nodes/unique_objectids `3370/3370`; labels Computer 100, Domain 1, GPO 2, Group 551, OU 223, User 2493, luôn kèm Base. Relationship type counts: AdminTo 5, AllExtendedRights 2499, CanPSRemote 2, CanRDP 3, Contains 2816, ExecuteDCOM 1, GenericAll 37034, GenericWrite 3166, GetChanges 3, GetChangesAll 2, GpLink 2, MemberOf 15917, Owns 3362, WriteDacl 3392, WriteOwner 3392; tổng 71596. Full Group/all-node rows chứa identities và giữ local; không dán toàn bảng vào report. Membership rows: 15917, unique pairs 15917.

Discovery, với `$sid` lần lượt `S-1-5-4`, `S-1-5-17`:

```cypher
MATCH (n) WHERE toString(n.objectid) CONTAINS $sid
RETURN labels(n) AS labels, n.objectid AS objectid, n.name AS name, properties(n) AS properties
ORDER BY objectid;
```

Mỗi lần trả một row, trùng exact node outputs ở mục 7. Chỉ sau đó dùng `$exact_objectid` lần lượt `SEAMLESS.INTERNAL-S-1-5-4`, `SEAMLESS.INTERNAL-S-1-5-17`:

```cypher
MATCH (n) WHERE n.objectid = $exact_objectid
RETURN labels(n) AS labels, n.objectid AS objectid, n.name AS name, properties(n) AS properties;

MATCH (n) WHERE n.objectid = $exact_objectid
OPTIONAL MATCH (n)-[r:MemberOf]->(parent)
RETURN labels(n) AS labels, n.objectid AS objectid, n.name AS name, type(r) AS type,
  labels(parent) AS parent_labels, parent.objectid AS parent_objectid, parent.name AS parent_name,
  properties(r) AS relationship_properties ORDER BY parent_objectid;

MATCH (child)-[r:MemberOf]->(n) WHERE n.objectid = $exact_objectid
RETURN labels(child) AS child_labels, child.objectid AS child_objectid, child.name AS child_name,
  type(r) AS type, labels(n) AS labels, n.objectid AS objectid, n.name AS name,
  properties(r) AS relationship_properties ORDER BY child_objectid;

MATCH (n)-[r]-(m) WHERE n.objectid = $exact_objectid
RETURN n.objectid AS objectid, type(r) AS type,
  startNode(r).objectid AS source, endNode(r).objectid AS target,
  labels(m) AS other_labels, m.objectid AS other_objectid, m.name AS other_name,
  properties(r) AS relationship_properties ORDER BY type, source, target;
```

Exact/outgoing outputs được in ở mục 7 và lưu nguyên trong artifact. Incoming `[]`; all-direct một row mỗi node, chính cặp source/target mục 7, không có type khác. Initial/rerun node/property/membership outputs bằng nhau; full Group identity sets bằng nhau.

### 14.4 Thu output qua HTTP mà không phụ thuộc GUI

Trong phiên nghiên cứu, truy vấn dùng Python `urllib.request`, POST `{"statements":[{"statement":...,"parameters":...}]}` tới `/db/neo4j/tx/commit`; credential chỉ giữ trong bộ nhớ local. Đo lại bằng gói query đã commit với PowerShell tương đương sau. `Get-Credential` nhập credential trên máy, không ghi mật khẩu vào command/file:

```powershell
$queryPackage139 = Get-Content -Raw -Encoding UTF8 reports/research/issue-139-seamless-boundary-legacy-403-queries.json | ConvertFrom-Json
$credential139 = Get-Credential -UserName neo4j -Message 'Thông tin đăng nhập Neo4j local'
$token139 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(('neo4j:' + $credential139.GetNetworkCredential().Password)))
$headers139 = @{Authorization = ('Basic ' + $token139)}
$observations139 = @{}
foreach ($query139 in ($queryPackage139.queries | Where-Object track -eq legacy)) {
    $body139 = @{statements = @(@{statement = $query139.statement; parameters = $query139.parameters})} | ConvertTo-Json -Depth 30
    $response139 = Invoke-RestMethod -Uri 'http://127.0.0.1:27474/db/neo4j/tx/commit' -Method Post -ContentType 'application/json' -Headers $headers139 -Body ([Text.Encoding]::UTF8.GetBytes($body139))
    if ($response139.errors.Count -ne 0) { throw 'Neo4j từ chối query; kiểm tra lỗi local' }
    $table139 = $response139.results[0]
    $rows139 = @($table139.data | ForEach-Object {
        $row139 = [ordered]@{}
        for ($index139 = 0; $index139 -lt $table139.columns.Count; $index139++) {
            $row139[$table139.columns[$index139]] = $_.row[$index139]
        }
        [pscustomobject]$row139
    })
    $observations139[$query139.id] = $rows139
}
$output139 = $observations139 | ConvertTo-Json -Depth 60
[IO.File]::WriteAllText((Join-Path (Get-Location) '.cache/legacy-collected.json'), $output139, [Text.UTF8Encoding]::new($false))
$groupOutput139 = ConvertTo-Json -InputObject @($observations139['groups']) -Depth 30
[IO.File]::WriteAllText((Join-Path (Get-Location) '.cache/legacy-groups.json'), $groupOutput139, [Text.UTF8Encoding]::new($false))
```

Lặp lại với HTTP `17474` và filename riêng cho initial. Chạy discovery riêng trước và xác nhận candidate IDs phù hợp package trước khi chạy toàn bộ exact queries; nếu khác, giữ unknown và chuẩn bị package mới có exact IDs thực tế. Với project, chọn `track=project`, endpoint `37474`. Không chạy Legacy queries trên project hoặc dùng kết quả project giả làm reference.

### 14.5 Raw analysis và tạo mapping bằng code đã chấp nhận

Đo raw count/duplicates/first-class absence bằng Python JSON parser trên sáu manifest-bound files, không sửa file. Để tái lập mapping local và canonical validation, lưu đoạn sau thành `.cache/prepare-group-mapping.py` rồi chạy `../../.venv/Scripts/python.exe -X utf8 .cache/prepare-group-mapping.py` từ worktree. Thêm repo root vào `sys.path` trước import khi script nằm trong `.cache`:

```python
import json
import sys
from collections import Counter
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root))
import yaml
from scripts.check_contract import validate_graph
from src.parser import IdentityNormalizer, ManifestRawDataLoader
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.cli import load_time_policy

raw_root = root / "../../data/raw/SEAMLESS"
loader = ManifestRawDataLoader(
    root / "data/samples/manifests/seamless-raw-v1.json",
    time_policy=load_time_policy(root / ".cache/time-policy.json"),
)
original = tuple(loader.load(raw_root))
adapted = adapt_bloodhound_v3_records(original)
normalizer = IdentityNormalizer()
reconciled = normalizer.normalize_records(adapted)
mapping = {}
raw_groups = []
for before, after in zip(original, adapted, strict=True):
    normalized = normalizer.normalize(after)
    if normalized.kind == "Group":
        source = before.data["ObjectIdentifier"]
        if source in mapping:
            assert mapping[source] == normalized.id
        mapping[source] = normalized.id
        raw_groups.append(source)
for sid in ("S-1-5-4", "S-1-5-17"):
    assert not any(
        record.data.get("ObjectIdentifier") in (sid, "SEAMLESS.INTERNAL-" + sid)
        or record.data.get("Properties", {}).get("objectid") in (sid, "SEAMLESS.INTERNAL-" + sid)
        for record in original
    )
    mapping["SEAMLESS.INTERNAL-" + sid] = sid
graph = json.loads((root / ".cache/project-current.json").read_bytes())
validate_graph(graph, yaml.safe_load((root / "configs/contract.yml").read_text(encoding="utf-8")))
(root / ".cache/identity-mapping.json").write_text(
    json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(len(raw_groups), len(set(raw_groups)))
print({key: count for key, count in Counter(raw_groups).items() if count > 1})
print(Counter(record.kind for record in reconciled))
```

Kết quả đã đo bằng cùng API: `550 549`, duplicate qualified Users count 2, normalized Group 549; toàn normalized collected nodes 3.368. Hai boundary mappings được thêm **sau** kiểm tra first-class absence và phải giữ evidence exact queries/SID ở mục 8. Với snapshot khác, không tái sử dụng assumption hai boundary IDs mà không kiểm tra raw/Legacy.

Chạy helper read-only:

```powershell
../../.venv/Scripts/python.exe -X utf8 scripts/research/compare_group_identity_sets.py --project .cache/project-current.json --legacy-groups .cache/legacy-groups.json --mapping .cache/identity-mapping.json --output .cache/group-comparison.json
```

Output thực tế: `status=measured`, collected 549, boundary 2, total/Legacy 551, literal common 517, mapped common 551, unresolved/difference lists rỗng. Full output chỉ local. Helper reject malformed JSON, mapping collisions, duplicate IDs, missing fields và output ghi đè input; tests synthetic không cần live GUI/DB.

### 14.6 Project projection và truy vấn kiểm chứng

Container project riêng được tạo bằng image ID trong bảng môi trường, bind localhost `37474:7474`, `37687:7687`, heap 256–512 MiB/pagecache 256 MiB. Credential chỉ truyền local; target mới chưa có node. Lệnh importer đã chạy với `NEO4J_URL=http://127.0.0.1:37474/db/neo4j/tx/commit` và `NEO4J_PASSWORD` trong environment:

```powershell
../../.venv/Scripts/python.exe -X utf8 scripts/import_canonical_graph.py .cache/project-current.json --structural-projection
```

Output thực tế có `nodes=3370`, `edges=53774`, `boundary_nodes=2`, `assessments_in_graph=3`, `assessments_in_neo4j=0`, đúng graph/assessment digests mục 4/6. Không chạy importer lên Legacy database. Để tạo target sạch ở máy khác, dùng command sau với `NEO4J_PASSWORD` đã đặt local và tên/cổng chưa được dùng:

```powershell
docker run -d --name issue139-project-neo4j -p 127.0.0.1:37474:7474 -p 127.0.0.1:37687:7687 -e "NEO4J_AUTH=neo4j/$env:NEO4J_PASSWORD" -e NEO4J_server_memory_heap_initial__size=256m -e NEO4J_server_memory_heap_max__size=512m -e NEO4J_server_memory_pagecache_size=256m sha256:d8f4c156caa3af76499134947deb11d13042e471d9733060449f2a01eb7a248e
```

Image ID này được xác minh trên máy nghiên cứu; nếu registry không resolve được ID trên máy khác, lấy `neo4j:2026.08.1`, ghi digest thực tế và kiểm tra version trước khi tái lập, không tuyên bố đã dùng đúng image cũ. Không xóa/reuse database có dữ liệu để làm target sạch.

Exact project queries đã chạy, cũng nằm trong query package:

```cypher
CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;
MATCH (n:Canonical) RETURN count(n) AS nodes, count(DISTINCT n.id) AS unique_ids;
MATCH (:Canonical)-[r]->(:Canonical) RETURN type(r) AS type, count(r) AS count ORDER BY type;
MATCH (n:Canonical:Group)
RETURN n.id AS id, n.label AS label, n.domain AS domain, n.is_boundary AS is_boundary ORDER BY id;
MATCH (n:Canonical) WHERE n.is_boundary = true
RETURN labels(n) AS labels, properties(n) AS properties ORDER BY n.id;
MATCH (n:Canonical)-[r]-(m:Canonical) WHERE n.is_boundary = true
RETURN n.id AS id, type(r) AS type, startNode(r).id AS source,
  endNode(r).id AS target, properties(r) AS properties ORDER BY id;
MATCH (n:Canonical)
RETURN n.graph_digest AS graph_digest, n.snapshot_id AS snapshot_id, count(n) AS count;
MATCH (:Canonical)-[r]->(:Canonical)
RETURN r.graph_digest AS graph_digest, r.snapshot_id AS snapshot_id, count(r) AS count;
MATCH (:Canonical)-[r]->(:Canonical)
RETURN count(r) AS count,
  sum(CASE WHEN r.provenance_json IS NOT NULL THEN 1 ELSE 0 END) AS with_provenance;
```

Results: kernel `2026.08.1`, counts `3370/3370`, type counts khớp canonical, 551 Group rows, đúng hai boundary nodes/cạnh mục 6/8. Một node-digest row có count 3370; một edge-digest row có count 53774, đều cùng snapshot/digest đã pin. Provenance count `53774/53774`. Raw provenance/property outputs của hai principals được giữ đầy đủ trong artifact.

### 14.7 Kiểm chứng repository và lưu trữ evidence

```powershell
../../.venv/Scripts/python.exe -m pytest tests/test_compare_group_identity_sets.py -q
../../.venv/Scripts/python.exe -m ruff check .
../../.venv/Scripts/python.exe -m ruff format --check .
../../.venv/Scripts/python.exe -m yamllint .
../../.venv/Scripts/python.exe -X utf8 scripts/check_contract.py
../../.venv/Scripts/python.exe -X utf8 scripts/check_repository.py
git diff --check
../../.venv/Scripts/python.exe -X utf8 scripts/snapshot_manifest.py verify ../../data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
```

Kết quả cụ thể và kiểm tra JSON/tiếng Việt/history/data policy được ghi trong [worklog #139](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-10-01-ttsB-issue139.md). Không chạy lại expensive unchanged Legacy import. `.cache` giữ full exports, mapping và các script đo local; để tái lập không phụ thuộc các script local ấy, dùng query package và code/commands phụ lục trên. Bản JSON commit giữ query output an toàn, snapshot/revision/runtime/run identifiers, input/set digests và limitations; không giữ toàn bộ raw identity exports.
