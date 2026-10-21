# Comparison contract M1 với BloodHound Legacy 4.0.3

Ngày: 2026-10-05; TTS A: @Lolavine777; reviewer TTS B: @nairyuuu.
Refs [#195](https://github.com/nairyuuu/ad-weighted-graph/issues/195), [#47](https://github.com/nairyuuu/ad-weighted-graph/issues/47), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48), [#194](https://github.com/nairyuuu/ad-weighted-graph/pull/194).
Đây là source of truth cho comparison semantics và disposition của tám relation M1, tên tài liệu scope là `seamless-legacy-403-m1-common-v1`.
TTS A chốt các disposition dưới đây để B review ở #195; shared A/B acceptance chỉ có hiệu lực khi human review xác nhận, không suy từ CI hoặc evidence acceptance của #194.
Tên scope này chỉ định danh contract tài liệu, không phải giá trị `comparison_scope.id` mới mà CLI đã hỗ trợ.
Không thay [Graph Contract 1.3.0](../../configs/contract.yml), parser, engine, ranking hoặc canonical materialization policy.

## 1. Evidence binding và ranh giới phép so

BloodHound Legacy 4.0.3 là observational reference trong declared scope, không phải ground truth tuyệt đối.
Reuse nguyên evidence accepted của [#194](https://github.com/nairyuuu/ad-weighted-graph/pull/194), [report phép đo](issue-47-seamless-legacy-403-reconciliation.md) và [sanitized artifact](../../reports/research/issue-47-seamless-legacy-403-reconciliation.json).
Không rerun raw CLI, import Legacy, capture database hoặc viết lại reconciliation trong #195.

| Binding | Giá trị / nguồn |
| --- | --- |
| Base làm tài liệu #195 | Latest integrated `develop@f1c4fcaeea6c012a9b381b3937a80db281e5b33f` |
| Revision project thực sự được đo ở #194 | `294cba3e2882e4b7a5fbd867aadb8434124612c3`, sau fix #189 |
| Snapshot | `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` |
| Legacy | 4.0.3; importer tag revision `b54c418ef83fe5856ae3fe6317a20f2368a6378c`; retained native exports của #184 |
| Exact MemberOf proof | Artifact `full_memberof_proof`, `raw_set_proofs`, `by_kind.MemberOf`; không dùng Members-only view lịch sử |
| Remaining deltas | Artifact `m1_difference_ledger`, `raw_set_proofs`, `project_relation_evidence`, `sample_ledger` |
| Zero observations | Artifact `no_observation_limits`; đây là limitation, không phải decoder/session equivalence |

So exact canonical directed triples `(source, kind, target)` sau explicit one-to-one identity mapping của #183/#194.
Population gồm collected và boundary nodes: 3.370 identities, 3.368 collected + 2 boundary.
Không đoán mapping bằng display name hoặc SID suffix, không bỏ boundary để tạo equality.
Kind/domain/boundary identity checks vẫn phải giữ; Legacy domain/boundary metadata được gán từ project/raw mapping không phải independent metadata measurement.
Stored counts, unique triples và provenance occurrences là ba tầng đo riêng.
Exact equality phải dựa trên raw source selection độc lập ở cả hai phía và hai difference sets, không chọn intersection làm scope hoặc suy matching từ tổng counts.

## 2. Verdict vocabulary và unknown/false policy

| Wording dùng trong contract/report/demo | Nghĩa và điều kiện |
| --- | --- |
| `equivalent_in_accepted_scope` | Exact directed sets bằng nhau trong positive structural slice đã định nghĩa và được A/B accepted, với source/direction/identity đúng và có observations; không khẳng định full implementation hoặc runtime equivalence |
| `accepted_policy_difference` | Delta có full raw/lineage/assessment evidence và được chấp nhận là khác materialization policy; giữ delta trong full ledger, không sửa input/canonical graph để ép count |
| `not_measurable` | Zero observations, thiếu required evidence, scope chưa accepted hoặc eligibility không đạt; không gọi equivalent, false hoặc parity |
| `requires_fix` | Evidence chứng minh violation của declared semantics, ví dụ sai direction/identity, thiếu direct positive fact hoặc materialize unknown thành positive; cần correctness follow-up, không chỉ vì lệch count |
| `unsupported` | Relation/feature nằm ngoài claimed M1 scope; ghi thêm `out_of_scope`, không tính vào M1 correctness verdict |

Các nhãn disposition trong matrix là quyết định A đề nghị B accept ở #195, không phải output mới của comparator.
Khi trích trước human acceptance, report/demo phải ghi rõ trạng thái review này.
`unknown` không phải `false`: missing field, method-not-run, StatusAccessDenied hoặc incomplete collection không chứng minh negative.
`false` chỉ có căn cứ khi đúng required primitive được collect thành công/đầy đủ và có negative-known evidence hoặc deny evidence phù hợp rule.
Vắng edge, array rỗng không có completeness proof, hoặc zero stored observations không tự tạo negative-known evidence.
Project assessment `unknown`/`rejected` không được nâng thành traversable edge và không được so như positive Legacy edge.
Runtime như service/listener/firewall/endpoint/authentication và session còn sống không được suy từ structural equality.
Policy này kế thừa [ADR-0003](../adr/ADR-0003-host-access-inference-policy.md); direction kế thừa [ADR-0002](../adr/ADR-0002-edge-directionality-semantics.md).

## 3. Source-of-truth matrix cho tám relation

Mỗi hàng xác định raw source, direction, direct/derived selection, unknown/false treatment và disposition.
Số liệu chỉ trích observation #194, không phải phép đo mới tại base #195.

| Relation | Raw source và direction | Direct / derived và common slice | Unknown / false policy | Disposition theo evidence #194 |
| --- | --- | --- | --- | --- |
| `MemberOf` | `Groups.Members[].MemberId -> Group.ObjectIdentifier` union `User/Computer.ObjectIdentifier -> PrimaryGroupSid` | Full direct union `Members[] ∪ PrimaryGroupSid`; deduplicate triples; không closure/effective/derived MemberOf | Thiếu membership field không chứng minh không là thành viên; không suy primary membership từ count | `equivalent_in_accepted_scope`: 15.917 exact matching, differences 0/0; direct union được chọn để accept, không quay lại Members-only |
| `GenericAll` | `Object.Aces[]`, `RightName=GenericAll`; `PrincipalSID -> ObjectIdentifier` | Direct raw ACE, giữ inheritance attribute; common slice là non-self ở cả hai phía; không group expansion | Missing/denied/incomplete ACL là unknown, không phủ định quyền; self-ACE là positive raw evidence, không gán false | Non-self 37.034: `equivalent_in_accepted_scope`; 10 project-only self-ACE: `accepted_policy_difference` vì project giữ raw ACE, Legacy filter self |
| `WriteDacl` | `Object.Aces[]`, `RightName=WriteDacl`; `PrincipalSID -> ObjectIdentifier` | Cùng direct non-self ACE slice và inheritance treatment như GenericAll | Cùng ACL policy; self-ACE không phải unknown/false hoặc raw duplicate removal | Non-self 3.392: `equivalent_in_accepted_scope`; 3 project-only self-ACE: `accepted_policy_difference` |
| `AdminTo` | `Computer.LocalAdmins[]`: listed principal `-> Computer.ObjectIdentifier`; nested lineage dùng direct MemberOf + host-local evidence | Common slice là direct LocalAdmins support, kể cả edge có cả direct provenance và derivation; derived-only project edges ghi riêng, không yêu cầu Legacy effective closure | Required host-local/membership evidence thiếu là unknown; runtime unavailable không xóa positive structural fact | 5 direct matching: `equivalent_in_accepted_scope`; 4 derived-only: `accepted_policy_difference`, không claim full effective equality |
| `CanPSRemote` | `Computer.PSRemoteUsers[]`: listed principal `-> Computer.ObjectIdentifier` | Common slice là direct structural membership; không có derived/GPO observations ở snapshot này, không suy chúng equivalent | Missing membership evidence là unknown; endpoint ACL và WinRM runtime chưa được đo, không suy true/false runtime | 2 direct exact matching: `equivalent_in_accepted_scope` chỉ về structure; runtime `not_measurable` |
| `CanRDP` | `Computer.RemoteDesktopUsers[]`: listed principal `-> Computer.ObjectIdentifier`; project còn cần host-bound UserRights | Legacy materializes direct membership edge; project cần effective membership + allow `SeRemoteInteractiveLogonRight` + known-negative deny `SeDenyRemoteInteractiveLogonRight`; không có common positive-edge equality claim | Thiếu UserRights tạo unknown, không phải false/denied; positive requires đủ rule, deny có precedence khi đã có evidence | `accepted_policy_difference`: 3 Legacy edges tương ứng đúng 3 project unknown assessments, 0 project edges; runtime `not_measurable` |
| `ForceChangePassword` | `User.Aces[]`: principal `-> User`; project decode `RightName=ForceChangePassword`, Legacy decode `AceType=User-Force-Change-Password` và filter self | Direct ACE only; không remap AllExtendedRights; decoder/self-policy equivalence chưa được đo | Zero observations không chứng minh permission false hoặc decoder tương đương | `not_measurable`: 0/0 stored observations, không dùng `equivalent_in_accepted_scope` |
| `HasSession` | Computer session arrays; host `-> UserSID`; project đọc `Sessions/PrivilegedSessions/RegistrySessions` | Direct snapshot observation, không group closure; chưa accept session-flavor mapping hoặc time equivalence vì không có rows | Zero/missing sessions không chứng minh không có active session; assumed timestamp không thành observed | `not_measurable`: 0/0 stored observations, không dùng `equivalent_in_accepted_scope` |

Self-ACE disposition giữ positive raw provenance của project; không yêu cầu xóa self edges, không kết luận exploitation value của self transition.
Legacy self filter và ACE decoder được pin bằng [official importer source](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js#L562-L626) và full raw decomposition ở #194.
ACL inheritance là attribute của direct raw ACE, không phải nested-membership derivation.
AdminTo direct selection phải dựa trên raw LocalAdmins support, không chỉ `derivation is None`: một trong năm matching direct edges cũng có nested lineage đã coalesce.
Không biến selection bất đối xứng của historical MemberOf view thành contract mới; full proof 13.324 explicit + 2.593 primary, overlap 0 là authoritative.
Không có remaining observed M1 delta nào ở #194 được disposition `requires_fix`; nhãn này vẫn dành cho violation có evidence ở scope đã định nghĩa.
PrimaryGroupSid gap lịch sử đã được #189 sửa và #194 kiểm chứng, không mở lại correctness gap bằng Members-only view.

## 4. Legacy relations ngoài M1

Full ledger giữ nguyên 15.243 observations ngoài M1 trên snapshot #194.
Disposition của từng kind dưới đây là `unsupported` / `out_of_scope` trong phép so M1, không phải verdict về chất lượng implementation Legacy.

| Legacy kind | Stored observations #194 |
| --- | ---: |
| `AllExtendedRights` | 2.499 |
| `Contains` | 2.816 |
| `ExecuteDCOM` | 1 |
| `GenericWrite` | 3.166 |
| `GetChanges` | 3 |
| `GetChangesAll` | 2 |
| `GpLink` | 2 |
| `Owns` | 3.362 |
| `WriteOwner` | 3.392 |

Mọi kind khác không thuộc tám relation của matrix, gồm các `GetChanges*` khác nếu gặp ở snapshot khác, cũng là out-of-scope.
Danh sách quan sát trên không phải exhaustive catalog tính năng BloodHound.
Không remap kind ngoài scope để bù zero observations, không tính chúng thành M1 discrepancy hoặc claim full BloodHound parity.

## 5. Comparator, report và demo phải giữ gate

[Comparator CLI](../../scripts/reconcile_graph_baseline.py) hiện chỉ hỗ trợ machine scope `m1-structural-v1`, gồm cả derived AdminTo và positive composite CanRDP theo project policy.
Contract tài liệu này chốt các common slices và accepted differences; nó không làm Legacy full export thỏa machine scope đó.
Giữ nguyên `export_complete=false`, historical artifact verdict, input/output digests và full difference ledger của #194.
Không đổi flag thành true chỉ vì export đầy đủ rows hoặc A/B accept một policy difference; các semantics khác nhau vẫn khác nhau.
Full comparator tiếp tục `NOT_MEASURABLE` / exit 2; không tự nâng thành `MATCH`, parity hoặc full M1 equivalence từ five matching slices.

| Output hiện có | Cách diễn giải theo contract |
| --- | --- |
| `MATCH` / exit 0 | Exact equality của declared machine scope sau eligibility; không tự chứng minh human acceptance, runtime hoặc zero-observation decoder equivalence |
| `DISCREPANCY` / exit 1 | Observation delta cần disposition bằng matrix/evidence; không tự đồng nghĩa `requires_fix` |
| `NOT_MEASURABLE` / exit 2 | `not_measurable` cho phép so tổng; giữ nguyên kể cả MemberOf hoặc narrow slice bằng nhau |
| `INVALID_INPUT` / exit 2 | Input/mapping cần sửa trước khi diễn giải; không phải policy difference hoặc verdict parity |

Report và demo dùng matrix này cùng evidence #194, ghi rõ slice và review status khi dùng verdict wording.
Không gọi research audit source-rule `MATCH` là output comparator mới hoặc full-kind equivalence.
Giữ historical `A_source_rule_view_pending_B_review` trong artifact; review semantics hiện hành theo #195, không sửa retrospective status thành accepted.
Không có machine-readable policy hoặc logic mới để bảo vệ, nên không thêm tests đọc lại Markdown hoặc tests mirror matrix.
Existing eligibility regressions đã kiểm tra exact input nhưng thiếu scope/`export_complete=false` vẫn trả `NOT_MEASURABLE`; chạy lại các checks này cho PR docs.

## 6. Handoff và acceptance

Request @nairyuuu review direction/identity, full direct MemberOf union, self-ACE, direct/derived AdminTo, structural-only CanPSRemote và CanRDP unknown/materialization difference.
Hai zero-observation relations vẫn `not_measurable` sau khi contract được accepted.
Kết quả #195 được cross-link qua contract/report/worklog/PR tới #47/#48; không tự đóng #47/#48/#158.
Final clean-checkout cross-reproduction thuộc [#196](https://github.com/nairyuuu/ad-weighted-graph/issues/196), sau human acceptance của #195 tại revision nghiệm thu.
PR này không thực hiện #196 và không claim Week 3 complete.
