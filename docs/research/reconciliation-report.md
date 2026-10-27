# Đối soát cấu trúc và bàn giao bằng chứng #47 / #48

- Cập nhật: 2026-10-05; A: @Lolavine777; reviewer: @nairyuuu.
- Real reconciliation rerun tại integrated `develop@294cba3e2882e4b7a5fbd867aadb8434124612c3`, sau merge #189; reuse script/report/Legacy exports của #184.
- Contract 1.3.0; #195 chỉ chốt comparison semantics/docs/worklog, reuse evidence #194, không sửa parser/engine/rating model hoặc comparator.
- Synthetic coverage dưới đây đến từ [PR #157](https://github.com/nairyuuu/ad-weighted-graph/pull/157); giữ riêng với observation thật.

**Evidence #194 xác nhận full MemberOf exact-equal; [comparison contract #195](seamless-legacy-403-comparison-contract.md) là source of truth cho semantics và disposition của tám relation M1.**
Contract chốt lựa chọn của A để @nairyuuu review; không coi accepted evidence #194 là human acceptance của common-semantics contract.
Xem [report thật và reproduction](issue-47-seamless-legacy-403-reconciliation.md), [machine evidence](../../reports/research/issue-47-seamless-legacy-403-reconciliation.json) và [worklog mới](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-10-05-ttsA-issue47-post189-reconciliation.md).
Rerun verify raw manifest và reuse native Legacy 4.0.3 full exports của #184, khớp đúng ba handoff digests #183.
Full MemberOf có 15.917 matching, 0/0 differences; full comparator giữ `NOT_MEASURABLE` vì `export_complete=false` và full machine scope không tương đương các common slices đã chọn.
Không claim parity hoặc đóng #47/#48.

## 1. Ma trận từng ca từ đầu vào đến kết quả

Dữ liệu mới nằm tại [raw_input](../../tests/fixtures/reconciliation/raw_input/), gồm bốn file JSON synthetic bất biến khi chạy test.
Snapshot sinh bởi manifest generator là `sha256:b70656467f4709e948495175430dc9245ce668d92d91cfeb3be96b81728b810d`.
Trong bảng, U1/U2/G/H lần lượt là `S-1-5-21-700-800-900-{1101,1102,2101,3101}`.
Ca `test_raw_cli_all_m1_relationships_have_independent_directed_expectations` trong [test_structural_boundary_cases.py](../../tests/test_structural_boundary_cases.py) chạy subprocess CLI thật, qua manifest/loader/adapter/normalizer/builder/serialization/contract.
Kỳ vọng là tập chín bộ ba được viết bằng literal, không tính bằng helper của comparator hoặc builder.
Kết quả đo được và các bản ghi trích nguyên từ output nằm trong [parser_cli_evidence.json](../../tests/fixtures/reconciliation/parser_cli_evidence.json).

| Quan hệ / ca | Đầu vào synthetic cụ thể | Kỳ vọng độc lập | Kết quả CLI thực tế | Quan sát SEAMLESS và nguồn |
| --- | --- | --- | --- | --- |
| `MemberOf` | `groups.json`: G.Members chứa U1 | U1 -> G; không tạo closure MemberOf | Đúng 1 bộ ba | Real sau #189: 15.917 matching, 0/0 difference; 2.593 primary edges có direct positive raw provenance |
| `AdminTo` | H.LocalAdmins chứa G; U1 thuộc G | G -> H và U1 -> H, giữ bằng chứng dẫn xuất | Đúng 2 bộ ba | Real: 5 matching direct, 4 project-only nested AdminTo; raw/derivation đã trace |
| `GenericAll` | U2.Aces: U1/GenericAll | U1 -> U2 | Đúng 1 bộ ba | Real: 37.034 matching non-self, 10 project-only self-ACE; pinned Legacy filter |
| `WriteDacl` | U2.Aces: U1/WriteDacl | U1 -> U2, khác kind với GenericAll | Đúng 1 bộ ba | Real: 3.392 matching non-self, 3 project-only self-ACE |
| `ForceChangePassword` | U2.Aces: U1/ForceChangePassword | U1 -> U2 (User) | Đúng 1 bộ ba | Real full exports: 0 observed ở cả hai; decoder equivalence unknown, không remap AllExtendedRights |
| `CanRDP` | H.RemoteDesktopUsers chứa U1; allow right có U1; deny right thu thập đầy đủ và rỗng | U1 -> H | Đúng 1 bộ ba | Real: 3 Legacy-only direct memberships; project 3 unknown assessments, thiếu UserRights |
| `CanPSRemote` | H.PSRemoteUsers chứa U1 | U1 -> H theo cấu trúc quyền quản lý từ xa | Đúng 1 bộ ba | Real: 2 exact matching direct memberships; runtime endpoint unknown |
| `HasSession` | H.Sessions có UserSID=U2 | H -> U2; gắn snapshot; thời gian assumed từ policy | Đúng 1 bộ ba; timestamp `2026-09-24T00:00:00Z`, `timestamp_status=assumed` | Real full exports: 0 observed ở cả hai; raw không có sessions, không suy active-session absence |

Tổng output: 6 node, 9 cạnh, 0 assessment; không có warning/error.
Đây là coverage của những ca được liệt kê, chưa chứng minh mọi biến thể đầu vào hoặc toàn bộ SEAMLESS.
Các ca đã có vẫn được tái sử dụng: `test_rich_demo_exports_reconciled_graph_and_unknown_rdp` và các ca negative trong [test_parser_demo.py](../../tests/test_parser_demo.py), direct ACL trong [test_builder_direct.py](../../tests/test_builder_direct.py), cùng các ca allow/deny, chu trình và quyền thiếu trong [test_inference.py](../../tests/test_inference.py).
[test_m1_fixtures.py](../../tests/test_m1_fixtures.py) kiểm tra Graph JSON đã dựng sẵn và contract; không phải bằng chứng từ raw qua parser.

| Tầng / ca và nguồn test | Đầu vào và ranh giới phép thử | Kỳ vọng | Kết quả thực tế / phần chưa kiểm chứng |
| --- | --- | --- | --- |
| 1: `test_cli_preserves_scoped_nodes_and_edge_endpoints`, comparator tests | Hai domain-SID hoặc hai GUID scope domain/host; baseline thiếu một node/cạnh | Giữ hai ID và chiều cạnh; DISCREPANCY | CLI giữ đủ hai node; không cắt SID cuối chuỗi |
| 1: `test_same_local_sid_in_two_scopes_never_collides`, `test_domain_sid_is_typed_stable_scope_and_separates_domains`, normalizer tests | RawRecord có stable scope khác nhau | ID canonical khác nhau | Các test raw -> normalizer đạt; không phải Legacy export |
| 1: `test_layer1_foreign_security_principal_boundary_group_membership`, boundary tests | NormalizedRecord đã gán foreign `is_boundary=true` | Giữ flag/domain và foreign user -> group | Builder giữ 2 node/1 MemberOf; không chứng minh tự phân loại FSP từ raw |
| 2: ca raw CLI M1 ở trên | Snapshot manifest và time policy assumed; created_at khác collection timestamp | Session H -> U2; raw_file gắn đúng snapshot; assumed không thành observed | Đạt các assertion snapshot, timestamp, timestamp_status và attribute |
| 2: `test_manifest_snapshot_reference_must_match_record_snapshot_id`, `test_graph_snapshot_metadata_must_match_manifest_record_snapshot`, builder tests | Snapshot raw_file/record/graph mâu thuẫn | Từ chối snapshot khác | Test negative đã có đạt; không suy phiên còn sống từ snapshot |
| 3: `test_layer3_missing_userrights_creates_unknown_assessment_not_attack_edge`, boundary tests | NormalizedRecord + RemoteDesktopUsers; bỏ UserRights | Không cạnh RDP; 1 unknown | Builder đạt; ca này không đưa StatusAccessDenied vào input |
| 3: `test_raw_cli_access_denied_keeps_unknown_and_no_canrdp_edge`, boundary tests | Bản sao local của raw fixture: UserRights.Status và UserRightsStatus là StatusAccessDenied, Complete=false; manifest mới | 8 cạnh, 1 CanRDP unknown U1 -> H, không cạnh CanRDP | CLI đạt; provenance có UserRights, evidence_type=unknown |
| 4: `test_layer4_domain_record_with_trusts_builds_domain_node_without_spurious_edges`, boundary tests | NormalizedRecord Domain; raw Trusts có SidFilteringEnabled true/false | 1 Domain, không cạnh/assessment suy đoán | Builder đạt; Trusts và SidFilteringEnabled không được xuất vào node |
| 4: ca raw CLI M1 và `test_layer4_boundary_domain_node_preserves_external_boundary_flag` | Domain external có flag true do fixture khai báo; Trusts ở Domain local | Giữ external domain/flag; không sinh cạnh trust ngoài M1 | CLI và builder đạt; chưa chứng minh tự khám phá Domain external hoặc bảo toàn thuộc tính trust trong Graph JSON |

Boundary identity handoff đã có; trust/runtime, raw rejection và full common-semantics acceptance vẫn giữ giới hạn ở [#82](https://github.com/nairyuuu/ad-weighted-graph/issues/82) / [#139](https://github.com/nairyuuu/ad-weighted-graph/issues/139).
Không mở rộng parser hoặc trust model để làm cho ma trận có nhãn đầy đủ.

## 2. Điều kiện và phạm vi comparator

[scripts/reconcile_graph_baseline.py](../../scripts/reconcile_graph_baseline.py) nhận Graph JSON với `nodes` và đúng một mảng `edges` hoặc `relationships`.
Node cần ID, kind, domain và boolean boundary; các tên alias được hỗ trợ phải nhất quán.
Dạng export có `properties.objectid`, `labels`, `properties.domain` và `properties.is_boundary` được hỗ trợ; labels phải xác định đúng một kind được hỗ trợ.
Endpoint phải trỏ tới node thực sự có trong export, dùng cùng raw ID.
Thiếu record, alias mâu thuẫn, sai kiểu, endpoint không giải được hoặc provenance đã khai báo nhưng lỗi đều bị từ chối; không bỏ bản ghi rồi so phần còn lại.
JSON trùng key hoặc số NaN/Infinity cũng bị từ chối trước khi chúng có thể làm mất dữ liệu.

ID được chuẩn hóa theo grammar parser/contract: SID không mơ hồ, GUID chữ thường và scoped SID giữ nguyên scope.
Builtin/service SID cần scope không được chấp nhận ở dạng unscoped.
Legacy `DOMAIN-SID` cần ánh xạ JSON tường minh, không có heuristic lấy SID cuối.
Ánh xạ không được thay danh tính đã canonical; mọi target phải là canonical ID hợp lệ.
Hai raw node ID cùng ánh xạ một ID bị `INVALID_INPUT`, kể cả metadata giống nhau: alias equivalence còn cần điều tra.
Node lặp y hệt được giữ một danh tính và công bố `duplicate_node_records`; node lặp có record khác bị từ chối.
Kind và tên domain không phân biệt chữ hoa/thường; không suy DNS domain tương đương Domain SID, không suy alias miền theo tên hiển thị.
Cờ boundary, kind và domain sai khác trên cùng ID đều ảnh hưởng verdict và có danh sách chẩn đoán riêng.

Hai bên phải khai báo metadata sau, với `snapshot_id` SHA-256 hợp lệ và bằng nhau:

```json
{
  "snapshot_id": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "synthetic": true,
  "export_complete": true,
  "source_evidence": "tests/fixtures/reconciliation/candidate_graph.json",
  "comparison_scope": {
    "id": "m1-structural-v1",
    "node_population": "collected_and_boundary",
    "relationship_kinds": ["MemberOf", "AdminTo", "GenericAll", "WriteDacl", "ForceChangePassword", "CanRDP", "CanPSRemote", "HasSession"],
    "memberof_semantics": "direct"
  }
}
```

Đây là ví dụ synthetic; source_evidence thực tế phải tham chiếu manifest/run/export và tài liệu kiểm toán quy tắc so sánh.
B đã bàn giao [export #82](seamless-legacy-403-reconciliation-handoff.md) trên hai retained Legacy databases.
Common semantics hiện hành theo [contract #195](seamless-legacy-403-comparison-contract.md), còn `m1-structural-v1` dưới đây là machine scope hiện có, không phải tên khác cho các common slices.
Cả hai bên phải khai báo cùng chế độ synthetic hoặc cùng chế độ dữ liệu đo được; synthetic không bỏ qua snapshot/scope validation.
`export_complete=true` là cam kết của bên xuất dữ liệu đã kiểm toán phạm vi, không phải một phép đo rejected records của comparator.
Công cụ kiểm tra khai báo, ID, endpoint và provenance snapshot khi có; nó không tự chứng minh file export đầy đủ so với database hay raw.
Metadata thiếu/khác, scope chưa xác minh hoặc status không đo được trả `NOT_MEASURABLE`, không có verdict khớp toàn bộ.

Ngữ nghĩa của `m1-structural-v1`:

| Kind | Ngữ nghĩa bắt buộc khi khai báo scope |
| --- | --- |
| MemberOf | Full direct `Members[] ∪ PrimaryGroupSid`; không so closure/effective membership như cạnh trực tiếp |
| AdminTo | Quyền quản trị local từ membership, gồm dẫn xuất nested membership có căn cứ |
| GenericAll / WriteDacl | Quyền ACE tương ứng; bảo toàn source principal -> target object |
| ForceChangePassword | ACE áp dụng cho User target; không tự coi AllExtendedRights tương đương |
| CanRDP | Membership + allow right + known-negative deny theo semantics dự án |
| CanPSRemote | Quyền quản lý từ xa theo cấu trúc membership; không xác nhận runtime endpoint |
| HasSession | Computer -> User quan sát trên snapshot; không kết luận phiên đang hoạt động |

Scope này chỉ được khai báo verified-complete cho Legacy khi có bằng chứng ngữ nghĩa tương ứng cho toàn scope.
Acceptance của policy difference ở #195 không làm full positive CanRDP hoặc derived AdminTo của Legacy thỏa scope này.
Giữ nguyên Legacy `export_complete=false`; không dùng contract tài liệu làm machine scope mới hoặc bật flag để ép MATCH.
Comparator hiện hỗ trợ đúng scope đã tài liệu hóa này; scope khác hoặc subset chưa có định nghĩa phải giữ NOT_MEASURABLE.
Report/demo diễn giải theo [verdict vocabulary #195](seamless-legacy-403-comparison-contract.md#2-verdict-vocabulary-và-unknownfalse-policy): scoped structural equality là `equivalent_in_accepted_scope`, self-ACE/nested-admin/CanRDP là `accepted_policy_difference`, zero observations là `not_measurable`.
Các nhãn scoped/disposition của A còn cần human acceptance ở #195; không tự nâng full `NOT_MEASURABLE` thành parity từ narrow views.
`MATCH` chỉ có nghĩa cùng tập node/metadata chuẩn hóa và bộ ba trong scope khai báo, không là parity giữa sản phẩm hoặc nghiệm thu #47.

`Contains` và mọi kind ngoài M1 được giữ nguyên trong `out_of_scope` với counts, lý do và full observations.
Chúng không nằm trong Jaccard, counts hay verdict so sánh M1.
`all_observed` vẫn đếm toàn bộ cạnh đã xuất, gồm các quan sát ngoài scope.

`stored_edges` đếm số relationship records; `unique_triples` đếm bộ ba có hướng duy nhất; multiplicity là stored/unique.
`stored_evidence_occurrences` chỉ cộng số phần tử provenance được xuất khi mọi cạnh trong phạm vi đo có mảng provenance không rỗng và hợp lệ.
Đó là số occurrence bằng chứng được export, không chứng minh số raw records độc lập hoặc nguồn gốc multiplicity trong Legacy.
Provenance có thể được dùng lại giữa các cạnh dẫn xuất; không diễn giải tổng này thành số raw facts duy nhất.
Provenance không rỗng được kiểm tra bằng validate_provenance của contract, bao gồm collector, timestamp/status và evidence_type=positive.
Derivation được kiểm tra bằng validate_derivation; MemberOf direct không được mang lineage dẫn xuất.
Thiếu/rỗng/partial provenance trả `null`, `evidence_status=not_measurable` cùng lý do; không tự cộng 1 cho cạnh.

Artifact giữ full `candidate_only` / `baseline_only` cho node và bộ ba, cùng sổ MemberOf/GenericAll/các kind khác.
Mỗi sai lệch cạnh có exact triple, graph/JSON pointer, edge ID nếu có, provenance/ref và derivation nếu được export, `reason_status=unresolved`.
Legacy thiếu provenance giữ null/not_measurable; không tạo raw locator giả.
Samples giới hạn chỉ phục vụ hiển thị; counts dùng toàn bộ tập.
Exit codes: MATCH=0, DISCREPANCY=1, NOT_MEASURABLE hoặc INVALID_INPUT=2.
Lỗi đọc JSON trả 2 và diagnostic stderr, không tạo báo cáo so sánh từ input không giải mã được.

## 3. Bằng chứng SEAMLESS thật hiện hành

[Handoff #183](seamless-legacy-403-reconciliation-handoff.md) đã cung cấp identity mapping, full directed rows, multiplicity, runtime/snapshot/digests và query/raw-locator tooling.
A không còn coi thiếu exports là blocker: native recreation ở máy A đã khớp full export bytes của B.
Project CLI chạy thật trên `294cba3`, manifest verified, fail_fast: 3.370 nodes, 56.367 edges, 3 unknown CanRDP assessments, warning/error = 0.
Exact identity/kind sets bằng nhau; boundary/collected mapping là metadata được gán theo accepted handoff, không phải independent Legacy metadata parity.

| Real evidence | Kết quả / giới hạn |
| --- | --- |
| MemberOf full decomposition | Project = Legacy = raw Members union PrimaryGroupSid: 15.917 matching, difference sets rỗng; đủ 2.593 primary direct edges có positive provenance |
| GenericAll full decomposition | Project = raw unique ACE triples; Legacy = non-self subset; 10 self-ACE project-only |
| WriteDacl | Cùng self-ACE filter; 3 project-only |
| AdminTo | 5 matching direct + 4 project-only nested materializations có validated lineage/raw pointers |
| CanPSRemote | 2 matching raw direct memberships; không chứng minh endpoint runtime |
| CanRDP | 3 Legacy-only memberships; 3 project unknown assessments do thiếu UserRights, 0 project traversal edges |
| ForceChangePassword / HasSession | `not_measurable`: 0 stored observations ở cả hai; không gọi source-rule equivalence |
| Multiplicity / raw duplicates | Stored/unique ratio = 1 ở cả hai; raw GenericAll duplicates 164, WriteDacl duplicates 2; Legacy provenance count null |
| Outside M1 | 15.243 Legacy observations giữ nguyên ngoài scope, không remap |
| Full comparator | `NOT_MEASURABLE` / tổng `not_measurable`; Legacy export_complete=false, không nâng gate bằng common slice equality |

Full exact differences và raw traces ở ignored local evidence; committed artifact giữ per-kind set hashes/counts, đủ 20 hashed M1 delta entries, 11 hashed samples và revision/input/output bindings.
Full MemberOf exact-equal và bốn narrow source-rule views vẫn exact-equal: non-self GenericAll/WriteDacl, direct LocalAdmins/PSRemoteUsers.
Members-only view của audit #184 lọc primary chỉ ở Legacy nên báo 2.593 project-unexpected sau #189; output được giữ nguyên và annotated, không coi là full-kind discrepancy.
Các views này hẹp hơn full `m1-structural-v1`; [matrix #195](seamless-legacy-403-comparison-contract.md#3-source-of-truth-matrix-cho-tám-relation) chốt direct union, non-self và direct-only selections, giữ full ledger.
Primary-group gap đã được B fix ở #189 và A kiểm chứng bằng exact raw union.
B review disposition `accepted_policy_difference` cho self-ACE, derived-only AdminTo và CanRDP, cùng mapping/provenance và hai `not_measurable` relations ở #195.
Historical importer write errors/rejected records/import duration của B giữ null; native import measurements của A giữ ngày 2026-10-04.
Phiên rerun không có Docker daemon, không import/capture mới hoặc đo runtime mới.
[#47](https://github.com/nairyuuu/ad-weighted-graph/issues/47) / [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) giữ mở.
Final integrated revision và clean-checkout cross-reproduction thuộc #196 sau acceptance #195, không thực hiện trong PR này.

## 4. Truy vết từ output CLI synthetic thực tế

[parser_cli_evidence.json](../../tests/fixtures/reconciliation/parser_cli_evidence.json) được trích bằng script từ output parser CLI, không viết hash bằng tay.
Mẫu rich dùng manifest `parser-demo-rich-v1.json`, snapshot `sha256:1f76e5bdeffbc474fa55872fe328806faf35a23f29525d8adfeecc1f6484a5d4`, source revision `49f591fa4feef390e62252509352ac2d8a5f7a88`.
Kết quả CLI: 6 nodes, 10 edges, 1 unknown assessment, warning/error=0.
Artifact lưu nguyên ba bản ghi được chọn và metadata/lệnh chạy.
Chúng chỉ có locator ở mức file/record/attribute, không cung cấp offset để truy từng byte.

| Bản ghi output | Kết quả chính xác | Truy vết / giới hạn |
| --- | --- | --- |
| U_A -> Helpdesk / MemberOf | ID `sha256:1298fa6fa72ae0d5f131bba62397b460d971641e618d004b0787e229c4de55bd` | 2 provenance tại groups.json và groups-repeat.json; attribute `Members[].MemberId`, timestamp_status=assumed |
| U_A -> Host / AdminTo | `derivation.kind=nested_membership`; ba bước được lưu nguyên trong artifact | U_A -> Helpdesk -> Operators -> Host; evidence_refs trỏ provenance có thực, không suy từ tên hiển thị |
| U_A -> Host / CanRDP unknown | `reason=required UserRights evidence is incomplete` | Assessment có evidence_type=unknown; không có cạnh CanRDP tương ứng; không gọi đây là StatusAccessDenied |

TTS A xác định phạm vi so sánh và giải thích sai lệch dựa trên policy/ADR đã chấp nhận.
Comparator áp dụng mapping do handoff khai báo; nó không quyết định policy boundary hoặc tự gán `is_boundary`.
Parser áp dụng semantics và xuất provenance; Legacy là nguồn quan sát độc lập, không là ground truth.
Nguồn gốc chênh multiplicity, Group bổ sung hoặc absence quan hệ phải có evidence điều tra; counts tự chúng không giải thích nguyên nhân.

## 5. Lệnh tái lập và kiểm chứng

Các lệnh sau là synthetic regression của checkpoint #157; thay PY bằng virtual environment thực tế của checkout.
Lệnh real SEAMLESS mới nằm tại [report rerun 2026-10-05](issue-47-seamless-legacy-403-reconciliation.md#5-tái-lập).

```bash
PY=/absolute/path/to/project/.venv/bin/python
"$PY" -m pytest tests/test_reconcile_graph_baseline.py tests/test_structural_boundary_cases.py -q
"$PY" scripts/reconcile_graph_baseline.py \
  --candidate tests/fixtures/reconciliation/candidate_graph.json \
  --baseline tests/fixtures/reconciliation/baseline_exact_graph.json \
  --mapping tests/fixtures/reconciliation/identity_mapping.json \
  --output /tmp/pr157-exact.json --summary
"$PY" -m src.parser.cli \
  --snapshot-id sha256:1f76e5bdeffbc474fa55872fe328806faf35a23f29525d8adfeecc1f6484a5d4 \
  --raw-dir data/samples/parser-demo-rich-input \
  --manifest-dir data/samples/manifests \
  --time-policy data/samples/parser-demo/time-policy.json \
  --created-at 2026-09-25T00:00:00Z --error-policy fail_fast \
  --output /tmp/pr157-rich.json --summary
```

Ca raw CLI M1/denied trong pytest tái sử dụng `generate_manifest` / `write_manifest`, tạo snapshot vào thư mục tạm và chạy subprocess với cùng virtual environment.
Fixture comparator có 10 node, 13 unique triples; baseline multiplicity có 17 stored edges / 13 unique triples, ratio=1.3077.
Candidate có 14 exported provenance occurrences; baseline không có provenance nên count=null.
Các edge ID comparator fixture là tên minh họa synthetic, không được mô tả là canonical parser output.
SID synthetic cũ có subauthority `000` đã được đổi thành `100` hợp lệ; raw_file snapshot prefix rút gọn được sửa thành binding SHA-256 đầy đủ.

Những ca CLI trước sửa đã tái hiện mất scope, false MATCH do metadata/input, Contains ngoài scope, ledger 12 còn 10 và evidence count 13 không có provenance.
Các regression sau sửa kiểm tra exit/verdict, danh tính và counts bằng kỳ vọng độc lập; lỗi input có stderr rõ, không traceback.
Kết quả kiểm chứng cuối và giới hạn môi trường được ghi tại [worklog](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-10-01-ttsA-reconciliation.md).
