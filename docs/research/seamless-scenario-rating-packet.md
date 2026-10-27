# Gói định mức độc lập và brief tái lập SEAMLESS

- Phiên bản scenario: 1.1.0; ngày sửa: 2026-10-02.
- Trạng thái: ADR-0013, Interface 1.0.0 quy chuẩn và Scoped Parameter Bundle 1.0.0 đã được TTS A và TTS B chấp thuận trong phạm vi PR #165 (Approval #5387665338, commit fdf5928); hai phiếu chấm người thật tiếp tục bảo lưu pending.
- Chủ trì: A @Lolavine777; reviewer: B @nairyuuu.
- Refs [PR #165](https://github.com/nairyuuu/ad-weighted-graph/pull/165), [#163](https://github.com/nairyuuu/ad-weighted-graph/pull/163), [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [PR #159](https://github.com/nairyuuu/ad-weighted-graph/pull/159), #42, #48.
- Quy chiếu: [ADR-0013](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md), [Interface Specification 1.0.0](path-ranking-interface-specification.md), [Scoped Parameter Bundle 1.0.0](../../tests/fixtures/ranking/seamless_parameter_bundle.json), [governance 1.0.0](evidence-rating-governance.md), [acceptance disposition](path-ranking-acceptance-disposition.md).

## 1. Scope, foothold và outcome

Đây là candidate structure quan sát trong snapshot SEAMLESS công khai, một topology AD tổng hợp; không phải telemetry tấn công production.
Người chuẩn bị chọn scope/route và đề xuất assumptions; actual independent ratings của A/B hoặc hai người phù hợp, design acceptance và nghiệm thu integration vẫn pending.
Không có tham số sản phẩm, calibration thực nghiệm hay live attack trong lượt này.

| Scope | Query / scenario | Foothold | Routes được cung cấp |
| --- | --- | --- | --- |
| Source A | `query-seamless-host-to-dc-v1` / `scenario-seamless-host-to-dc`, version 1.1.0 | `S-1-5-21-1271839998-3495686680-2211690266-4131`, `computers.json#/computers/46` | `route_seamless_01` qua LIDIA; `route_seamless_02` qua JOSEFA, VA-JER, OLLIE |
| Source B | `query-seamless-source-b-to-dc-v1` / `scenario-seamless-source-b-to-dc`, version 1.1.0 | `S-1-5-21-1271839998-3495686680-2211690266-4157`, `computers.json#/computers/67` | `route_seamless_source_b_01` qua OLLIE |

Mỗi scope giả định foothold LocalSystem có thể dùng danh tính máy tính cho kết nối miền, theo [Microsoft LocalSystem](https://learn.microsoft.com/en-us/windows/win32/services/localsystem-account).
Đây là điều kiện khởi đầu cần B review, không phải quan sát trạng thái foothold trong snapshot.
Horizon `24h`, boundary `intra_forest`, budget 6 active work units được giữ riêng trong metadata từng query.
Không so sánh Pareto hoặc dùng conditional bounds chung giữa hai footholds.

Đích duy nhất là `S-1-5-21-1271839998-3495686680-2211690266-1000` (BADBLOOD), raw `20210920185958_computers.json#/computers/0`.
`terminal_compromise_seamless_dc` nghĩa là thực thi lệnh thành công trong ngữ cảnh quản trị được nâng quyền trên DC qua endpoint WinRM đã chọn.
Không claim SYSTEM, RPC execution, Golden Ticket hoặc domain compromise chỉ từ việc có credentials/DA entitlement.
Goal predicate là `admin_control_badblood`; nhóm DA `...-512` là entitlement trung gian, không phải tài sản đích thứ hai.

## 2. Pins và căn cứ cấu trúc

| Thành phần | Pin / provenance |
| --- | --- |
| Reviewed head / parser code revision | `4822e95045e7ebbe99316ddb56ac1b1d4e2dc30f` |
| develop / merge PR #157 | `8c15993b2ac2ed491eda5dc4655e08e2eb478ec1`; `49f591f` là merge develop vào branch #157, không phải merge #157 |
| Snapshot / manifest | `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; `data/samples/manifests/seamless-raw-v1.json`, cả 6 files, 11,371,828 bytes |
| Upstream | `mike-nolan-councilman/Bloodhound_Data@8c3107421bb910e5e2b4d16631e243ddb0756ca5`; archive `20210920185958_BloodHound.zip`, SHA-256 `b8e9f003dd51a98838be86d8f98b0844a19a7876aad0a81b525f19e110105813` |
| Contract / semantics / governance | Graph Contract `1.3.0`; `attack_semantics.yml` version `0.2`; governance `1.0.0` Proposed; interface `1.0.0-draft` Proposed |
| Graph build | Official `src.parser.cli`, `unit` profile, `fail_fast`, fixed export `created_at=2026-10-01T00:00:00Z` |
| Collection-time policy | [seamless_time_policy.json](../../tests/fixtures/ranking/seamless_time_policy.json): `2021-09-20T18:59:58Z`, status `assumed`, filename convention; manifest collected_at remains null |
| Canonical graph byte digest | `sha256:5781a365b3a44c57bc2b30f11a98d1f60242ca515ceca411e9c6e34cefd5518a`; graph stays local in `data/processed/` |
| Predicate bindings | [seamless_predicate_bindings.json](../../tests/fixtures/ranking/seamless_predicate_bindings.json): mỗi observed predicate khóa node/property hoặc source/target/kind, không chỉ kiểm tập cạnh gộp |
| Executed evidence | [seamless_evidence_manifest.json](../../tests/fixtures/ranking/seamless_evidence_manifest.json): code/file/dependency/policy digests, expected/actual case matrix and verified route counts |

Timestamp đồ thị là research assumption tường minh; filename và export time không phải observed collection time.
Các định danh domain dùng SID `S-1-5-21-1271839998-3495686680-2211690266` đã audit tại [seamless-scope-identity.md](seamless-scope-identity.md).
`unit` edge weights là structural conformance profile, không phải effort/probability/risk của packet.

| Mã định danh cạnh chuẩn tắc (Canonical Edge ID) | Nút nguồn (Source Node) | Quan hệ (Kind) | Nút đích (Target Node) | Tập tin dữ liệu thô và con trỏ JSON (Raw Locator) |
| --- | --- | --- | --- | --- |
| `sha256:add3ecb3858d5426d003da9ecdba89274ea02d5c7d9e99e3e10ece6a5d077932` | `...-4131`<br>(`TSTWVIR1000001`) | `GenericAll` | `...-3398`<br>(`LIDIA_ALFORD`) | `20210920185958_users.json`<br>Con trỏ: `#/users/2310/Aces/3` |
| `sha256:e44b0f47456908b5209f670f2cf0889ae4695e9efd24c82bbda4da1ae043cb48` | `...-3398`<br>(`LIDIA_ALFORD`) | `MemberOf` | `...-512`<br>(`DOMAIN ADMINS`) | `20210920185958_groups.json`<br>Con trỏ: `#/groups/40/Members/0` |
| `sha256:57a246b4f71dff94a59b59addcf4e9aa6bd1bdb5d78817c1f733cc2ee197b2b9` | `...-512`<br>(`DOMAIN ADMINS`) | `GenericAll` | `...-1000`<br>(`BADBLOOD`) | `20210920185958_computers.json`<br>Con trỏ: `#/computers/0/Aces/1` |
| `sha256:e6e5d605be1a120753808f94017202855a53fdd9a6b9831ac3421d09fbba1538` | `...-4131`<br>(`TSTWVIR1000001`) | `GenericAll` | `...-1766`<br>(`JOSEFA_GONZALES`) | `20210920185958_users.json`<br>Con trỏ: `#/users/666/Aces/3` |
| `sha256:f8b6da6bcbda61ddab0d8184c957e39809ed4e444d5dee181f2309cf0e682173` | `...-1766`<br>(`JOSEFA_GONZALES`) | `MemberOf` | `...-3790`<br>(`VA-JER-ADMINGROUP1`) | `20210920185958_groups.json`<br>Con trỏ: `#/groups/246/Members/14` |
| `sha256:3b30de3caac96bad3b7b1980c323661cba1cbeccd3c676d20ce2eb15f4a67689` | `...-3790`<br>(`VA-JER-ADMINGROUP1`) | `GenericAll` | `...-2014`<br>(`OLLIE_LONG`) | `20210920185958_users.json`<br>Con trỏ: `#/users/917/Aces/3` |
| `sha256:250b099e406031037200bdf0d23277cc7d4fe7cc6f6ddad0d310a6be7f904d75` | `...-2014`<br>(`OLLIE_LONG`) | `MemberOf` | `...-512`<br>(`DOMAIN ADMINS`) | `20210920185958_groups.json`<br>Con trỏ: `#/groups/40/Members/3` |
| `sha256:b1ba7341c1075b25a3e1a096006b2ca01901d347fc4b9b9d7494402f480b7b1b` | `...-4157`<br>(`FINWVIR1000001`) | `GenericAll` | `...-2014`<br>(`OLLIE_LONG`) | `20210920185958_users.json`<br>Con trỏ: `#/users/917/Aces/11` |


## 3. Bốn buckets bằng chứng và ba predicate layers

Bốn buckets `observed_facts`, `false_facts`, `assumed_facts`, `unknown_facts` mô tả tình trạng bằng chứng.
Chúng không phải bốn tầng thẩm quyền; goal cũng không phải một tầng.

| Predicate layer | Vai trò trong interface | Binding trong packet |
| --- | --- | --- |
| 1 | Snapshot authorization bất biến, cần positive provenance | GenericAll, MemberOf |
| 2 | Capability/hygiene bất biến khi replay | `enabled_*`, raw pointer đến `Properties/enabled` |
| 3 | Runtime context và attacker state; assumptions có giải trình chỉ được dùng ở scenario mode | Foothold control, password/write acceptance, KDC/authentication, usable group token/scope, WinRM reachability/listener/endpoint/context, credentials và effects |

`predicate_layers` khai báo thẩm quyền cho mọi requires/adds/goal, độc lập với bucket.
Missing Layer 1/2 giữ unknown và không được bù bằng assumption hay effect.
`membership_security_group_usable_*` là điều kiện sử dụng entitlement trong token/runtime tại resource, không phải một snapshot `groupType` predicate hoặc một hành động sửa nhóm.
Raw không chứa groupType: không suy security-enabled, token freshness hoặc scope usability chỉ từ MemberOf.
Scenario giả định token có entitlement của security group tương thích; B phải review điều kiện này, thiếu nó giữ unknown và explicit false chặn closure.
Nếu cần một predicate cấu hình `groupType` riêng ở Layer 2 trong integration, nó phải có evidence riêng hoặc giữ unknown, không chuyển thành runtime effect.

Bucket `false_facts` của hai query nền rỗng vì packet không có provenance phủ định runtime tương ứng.
Không có collected HasSession connection để materialize cạnh; điều này không chứng minh không có session runtime.
`session_badblood` giữ unknown ở Layer 3; có thể giải quyết bằng declared scenario assumption nhưng không tạo HasSession edge.
Các đường đã cung cấp không dùng session hoặc DCSync.
Không suy quyền DCSync false hoặc credential access từ structural absence.
Known-false veto chỉ được kiểm chứng bằng negative variants có nhãn `synthetic_negative`, không gọi chúng là quan sát SEAMLESS thật.

Mọi assumption trong query có `truth_value=true`, Layer 3 và rationale cụ thể; trạng thái phê duyệt vẫn `pending_B_review`.
Không mặc định “Windows Server nên service chạy”, không đồng nhất reachability với write/authentication accepted.
EDR/telemetry chưa có evidence vẫn unknown; không tự gán EDR absent.
Scenario gói này dùng horizon đơn điệu, chưa model retry/expiry/revocation; rater phải ghi residual uncertainty dưới đúng scope đó.

## 4. Action bindings, rule sources và route/work mapping

Nguồn kỹ thuật xác lập cơ chế và prerequisites, không cung cấp numeric probability hoặc xác nhận runtime ở snapshot.
Catalog chuẩn được đối chiếu là [attack_semantics.yml](../../configs/attack_semantics.yml), không sửa catalog/parser/engine trong PR này.

| Rule | Primary technical source và điều kiện |
| --- | --- |
| R1 | [ActiveDirectoryRights](https://learn.microsoft.com/en-us/dotnet/api/system.directoryservices.activedirectoryrights?view=windowsdesktop-9.0): GenericAll là quyền trên AD object; dùng cho reset user, không suy host execution |
| R2 | [SetPassword](https://learn.microsoft.com/en-us/windows/win32/api/iads/nf-iads-iadsuser-setpassword) và [Reset Password extended right](https://learn.microsoft.com/en-us/windows/win32/adschema/r-user-force-change-password): cần quyền reset, password policy và authenticated/protected directory channel được phép; packet bind `password_policy_accepts_*`, `directory_write_allowed_*` và reachability |
| R3 | [Kerberos authentication](https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-authentication-overview): credentials không tự là token/ticket đã được chấp nhận; cần KDC, account/authentication context tương thích |
| R4 | [AD security groups](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-groups): entitlement đòi security-group/token/scope usable; DA mặc định thuộc host Administrators, nhưng scenario phải khai báo default mapping vẫn áp dụng |
| R5 | [Remote requirements](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_remote_requirements): endpoint security descriptor và cấu hình xác định ai có thể connect; cần listener/transport/authentication/endpoint authorization riêng |
| R6 | [Session configurations](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_session_configurations): execution context của endpoint phải cho phép administrative commands; restricted endpoint hoặc giảm quyền không chứng minh terminal admin control |

`genericall_reset_password` map R1/R2; `propagate_group_entitlement` map R4.
Activation là bước xác thực explicit R3; WinRM gộp yêu cầu `open_winrm_remote_session` và `obtain_admin_execution_on_host` qua R4/R5/R6.
Trong predicate bindings, source_authorized cho reset được chứng minh bằng ACE và actor/entitlement control; actor_enabled/target_enabled dùng Layer 2.
Terminal host authorization dùng rule DA mặc định với assumption `da_host_admin_mapping`, accepted auth, endpoint ACL và administrative execution context; không dùng `genericall_da_badblood` làm prerequisite thực thi.
Cạnh DA GenericAll DC vẫn được bảo toàn trong route/evidence audit với vai trò quyền AD object, không tạo AdminTo/CanPSRemote edge.

Bảng sau là mapping chính xác tới wire; mọi `requires` đều bắt buộc, mọi `adds` chỉ là Layer 3 và chỉ áp dụng khi action thành công.

| Action ID | Structural basis / rule | Required predicates | Effects | Work alias / routes |
| --- | --- | --- | --- | --- |
| `action_reset_lidia` | Observed GenericAll ACE; R1/R2 | `enabled_tstwvir`, `enabled_lidia`, `genericall_tstwvir_lidia`, `network_rpc_reachable`, `password_policy_accepts_lidia`, `directory_write_allowed_lidia`, `foothold_controlled_tstwvir` | `credentials_lidia` | WU_RESET_LIDIA; route_seamless_01 |
| `action_activate_lidia` | Credentials effect từ reset; R3 | `credentials_lidia`, `enabled_lidia`, `network_kdc_reachable`, `authentication_accepted_lidia` | `actor_controlled_lidia` | WU_ACTIVATE_LIDIA; route_seamless_01 |
| `action_closure_lidia_da` | Observed MemberOf + controlled actor; R4 | `actor_controlled_lidia`, `memberof_lidia_da`, `enabled_lidia`, `membership_security_group_usable_lidia_da` | `effective_member_da_lidia` | passive, không work unit; route_seamless_01 |
| `action_winrm_badblood_lidia` | Observed DA membership + proposed default DA admin mapping; R4/R5/R6; computer ACE chỉ là disclosure | `effective_member_da_lidia`, `network_winrm_reachable`, `service_winrm_running`, `enabled_badblood`, `actor_controlled_lidia`, `enabled_lidia`, `da_host_admin_mapping`, `winrm_authentication_accepted_lidia`, `endpoint_authorized_lidia`, `admin_execution_context_lidia` | `admin_control_badblood` | WU_WINRM_DC_LIDIA; route_seamless_01 |
| `action_reset_josefa` | Observed GenericAll ACE; R1/R2 | `enabled_tstwvir`, `enabled_josefa`, `genericall_tstwvir_josefa`, `network_rpc_reachable`, `password_policy_accepts_josefa`, `directory_write_allowed_josefa`, `foothold_controlled_tstwvir` | `credentials_josefa` | WU_RESET_JOSEFA; route_seamless_02 |
| `action_activate_josefa` | Credentials effect từ reset; R3 | `credentials_josefa`, `enabled_josefa`, `network_kdc_reachable`, `authentication_accepted_josefa` | `actor_controlled_josefa` | WU_ACTIVATE_JOSEFA; route_seamless_02 |
| `action_closure_josefa_vajer` | Observed MemberOf + controlled actor; R4 | `actor_controlled_josefa`, `memberof_josefa_vajer`, `enabled_josefa`, `membership_security_group_usable_josefa_vajer` | `effective_member_vajer_josefa` | passive, không work unit; route_seamless_02 |
| `action_reset_ollie` | Observed GenericAll ACE; R1/R2 | `effective_member_vajer_josefa`, `enabled_ollie`, `genericall_vajer_ollie`, `network_rpc_reachable`, `password_policy_accepts_ollie`, `directory_write_allowed_ollie`, `actor_controlled_josefa`, `enabled_josefa` | `credentials_ollie` | WU_RESET_OLLIE; route_seamless_02 |
| `action_activate_ollie` | Credentials effect từ reset; R3 | `credentials_ollie`, `enabled_ollie`, `network_kdc_reachable`, `authentication_accepted_ollie` | `actor_controlled_ollie` | WU_ACTIVATE_OLLIE; route_seamless_02, route_seamless_source_b_01 |
| `action_closure_ollie_da` | Observed MemberOf + controlled actor; R4 | `actor_controlled_ollie`, `memberof_ollie_da`, `enabled_ollie`, `membership_security_group_usable_ollie_da` | `effective_member_da_ollie` | passive, không work unit; route_seamless_02, route_seamless_source_b_01 |
| `action_winrm_badblood_ollie` | Observed DA membership + proposed default DA admin mapping; R4/R5/R6; computer ACE chỉ là disclosure | `effective_member_da_ollie`, `network_winrm_reachable`, `service_winrm_running`, `enabled_badblood`, `actor_controlled_ollie`, `enabled_ollie`, `da_host_admin_mapping`, `winrm_authentication_accepted_ollie`, `endpoint_authorized_ollie`, `admin_execution_context_ollie` | `admin_control_badblood` | WU_WINRM_DC_OLLIE; route_seamless_02, route_seamless_source_b_01 |
| `action_reset_ollie_from_b` | Observed GenericAll ACE; R1/R2 | `foothold_controlled_finwvir`, `enabled_finwvir`, `enabled_ollie`, `genericall_finwvir_ollie`, `network_rpc_reachable`, `password_policy_accepts_ollie`, `directory_write_allowed_ollie` | `credentials_ollie` | WU_RESET_OLLIE_FROM_B; route_seamless_source_b_01 |

Membership closure là suy diễn thụ động có điều kiện: 0 active effort và không thêm conditional-factor row khi prerequisites đều true.
Nếu usability false/unknown, closure bị blocked/unknown; không tự điền `[1,1]` để che mất điều kiện.

## 5. Canonical work IDs và overlap

Canonical ID tuân cú pháp `technique:actor:target:context:boundary:ledger_version` đã dùng bởi reconciliation helper.
WU là alias để đọc; wire ledger keys, action `referenced_work_unit_ids`, likelihood `prefix` và effort `work_unit_id` luôn dùng đầy đủ ID bên dưới.
Không dùng WU alias làm wire ID.

| Alias | Canonical work ID |
| --- | --- |
| `WU_RESET_LIDIA` | `reset_password:S-1-5-21-1271839998-3495686680-2211690266-4131:S-1-5-21-1271839998-3495686680-2211690266-3398:default:intra_forest:1.0.0` |
| `WU_ACTIVATE_LIDIA` | `acquire_ticket:S-1-5-21-1271839998-3495686680-2211690266-3398:S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0` |
| `WU_WINRM_DC_LIDIA` | `remote_exec_winrm:S-1-5-21-1271839998-3495686680-2211690266-3398:S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0` |
| `WU_RESET_JOSEFA` | `reset_password:S-1-5-21-1271839998-3495686680-2211690266-4131:S-1-5-21-1271839998-3495686680-2211690266-1766:default:intra_forest:1.0.0` |
| `WU_ACTIVATE_JOSEFA` | `acquire_ticket:S-1-5-21-1271839998-3495686680-2211690266-1766:S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0` |
| `WU_RESET_OLLIE` | `reset_password:S-1-5-21-1271839998-3495686680-2211690266-1766:S-1-5-21-1271839998-3495686680-2211690266-2014:default:intra_forest:1.0.0` |
| `WU_ACTIVATE_OLLIE` | `acquire_ticket:S-1-5-21-1271839998-3495686680-2211690266-2014:S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0` |
| `WU_WINRM_DC_OLLIE` | `remote_exec_winrm:S-1-5-21-1271839998-3495686680-2211690266-2014:S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0` |
| `WU_RESET_OLLIE_FROM_B` | `reset_password:S-1-5-21-1271839998-3495686680-2211690266-4157:S-1-5-21-1271839998-3495686680-2211690266-2014:default:intra_forest:1.0.0` |

Có 9 unique active work IDs: Source A ledger 8, Source B ledger 3, hai work activate/WinRM OLLIE dùng cùng technique/actor/target/context.
Effort identity có thể tái sử dụng chỉ khi context/boundary/rationale tương thích; không tái sử dụng conditional likelihood vì foothold/history khác nhau.
Persistent work dedup chỉ tính một ID một lần trong một candidate; không cộng effort qua nhiều candidate thay cho effort của từng route.
Shared preparation/overlap chưa được người chấm review: ledger để `unresolved_overlap`, effort/rubric null và `unrated`.
Không tự khấu trừ cost, không gọi nominal step count là rated effort.

| Candidate | Structural edges | Bound actions | Active units | Passive closures |
| --- | --- | --- | --- | --- |
| `cand_seamless_01_direct_lidia` (A) | 3 | 4 | 3 | 1 |
| `cand_seamless_02_alt_vajer_ollie` (A) | 5 | 7 | 5 | 2 |
| `cand_seamless_source_b_01_ollie` (B) | 3 | 4 | 3 | 1 |

## 6. Câu hỏi conditional likelihood

Mỗi hàng chấm đại lượng sau, với `E_i` là outcome thành công của active action ở hàng đó:

$$q_i = P(E_i\text{ succeeds} \mid F,S,E_1,\ldots,E_{i-1}\text{ succeeded}).$$

`F` là foothold query; `S` gồm scenario/version, snapshot, 24h, boundary, goal và toàn bộ conditions/assumptions được chấp thuận.
Outcome reset là credentials mới có được sau directory write; outcome activate là authenticated ticket/context điều khiển actor; outcome WinRM là `admin_control_badblood` trong endpoint context đã bind.
Lịch sử gồm mọi active event trước đó và các deterministic closures được bind dưới S; không lược bỏ bước reset/activate trung gian.
`ordered_work_prefix` / wire `prefix` gồm lịch sử active canonical IDs và ID hiện tại như lookup key cho `q_i`; nó không phải đại lượng cumulative.
Mọi rows dưới đây có câu hỏi outcome/history riêng, horizon 24h; alias được mở thành canonical ID theo Mục 5 và hai JSON sheets.

| Question ID | F / S scope | E_i outcome action | Previous active events succeeded | Inclusive lookup prefix (aliases) | Lower / upper / rationale |
| --- | --- | --- | --- | --- | --- |
| `cand_seamless_01_direct_lidia:q1` | A, query/scenario Mục 1 | `action_reset_lidia` succeeds | Không có previous event; chỉ F,S | (WU_RESET_LIDIA) | PENDING / PENDING / PENDING |
| `cand_seamless_01_direct_lidia:q2` | A, query/scenario Mục 1 | `action_activate_lidia` succeeds | WU_RESET_LIDIA | (WU_RESET_LIDIA, WU_ACTIVATE_LIDIA) | PENDING / PENDING / PENDING |
| `cand_seamless_01_direct_lidia:q3` | A, query/scenario Mục 1 | `action_winrm_badblood_lidia` succeeds | WU_RESET_LIDIA, WU_ACTIVATE_LIDIA | (WU_RESET_LIDIA, WU_ACTIVATE_LIDIA, WU_WINRM_DC_LIDIA) | PENDING / PENDING / PENDING |
| `cand_seamless_02_alt_vajer_ollie:q1` | A, query/scenario Mục 1 | `action_reset_josefa` succeeds | Không có previous event; chỉ F,S | (WU_RESET_JOSEFA) | PENDING / PENDING / PENDING |
| `cand_seamless_02_alt_vajer_ollie:q2` | A, query/scenario Mục 1 | `action_activate_josefa` succeeds | WU_RESET_JOSEFA | (WU_RESET_JOSEFA, WU_ACTIVATE_JOSEFA) | PENDING / PENDING / PENDING |
| `cand_seamless_02_alt_vajer_ollie:q3` | A, query/scenario Mục 1 | `action_reset_ollie` succeeds | WU_RESET_JOSEFA, WU_ACTIVATE_JOSEFA | (WU_RESET_JOSEFA, WU_ACTIVATE_JOSEFA, WU_RESET_OLLIE) | PENDING / PENDING / PENDING |
| `cand_seamless_02_alt_vajer_ollie:q4` | A, query/scenario Mục 1 | `action_activate_ollie` succeeds | WU_RESET_JOSEFA, WU_ACTIVATE_JOSEFA, WU_RESET_OLLIE | (WU_RESET_JOSEFA, WU_ACTIVATE_JOSEFA, WU_RESET_OLLIE, WU_ACTIVATE_OLLIE) | PENDING / PENDING / PENDING |
| `cand_seamless_02_alt_vajer_ollie:q5` | A, query/scenario Mục 1 | `action_winrm_badblood_ollie` succeeds | WU_RESET_JOSEFA, WU_ACTIVATE_JOSEFA, WU_RESET_OLLIE, WU_ACTIVATE_OLLIE | (WU_RESET_JOSEFA, WU_ACTIVATE_JOSEFA, WU_RESET_OLLIE, WU_ACTIVATE_OLLIE, WU_WINRM_DC_OLLIE) | PENDING / PENDING / PENDING |
| `cand_seamless_source_b_01_ollie:q1` | B, query/scenario Mục 1 | `action_reset_ollie_from_b` succeeds | Không có previous event; chỉ F,S | (WU_RESET_OLLIE_FROM_B) | PENDING / PENDING / PENDING |
| `cand_seamless_source_b_01_ollie:q2` | B, query/scenario Mục 1 | `action_activate_ollie` succeeds | WU_RESET_OLLIE_FROM_B | (WU_RESET_OLLIE_FROM_B, WU_ACTIVATE_OLLIE) | PENDING / PENDING / PENDING |
| `cand_seamless_source_b_01_ollie:q3` | B, query/scenario Mục 1 | `action_winrm_badblood_ollie` succeeds | WU_RESET_OLLIE_FROM_B, WU_ACTIVATE_OLLIE | (WU_RESET_OLLIE_FROM_B, WU_ACTIVATE_OLLIE, WU_WINRM_DC_OLLIE) | PENDING / PENDING / PENDING |

Sau review và đối soát, lower/upper là rational strings, `0 <= lower <= upper <= 1`; copy canonical `ordered_work_prefix` sang wire record `{"prefix": [...], "lower": "...", "upper": "..."}` trong đúng query.
Pending rows không được đưa vào `conditional_bounds_table`, hiện bảng này rỗng; không đổi null thành số mặc định.
Scoring nhân các factors theo chain rule: `P(program succeeds | F,S)=product(q_i)`; interval enclosure `[product(l_i), product(u_i)]` cho đúng conditional questions, không giả định independence.

### Ví dụ tính tay SYNTHETIC, không phải SEAMLESS rating

Giả sử ba cumulative prefix probabilities là `4/5`, `3/5`, `3/10` dưới một F,S tổng hợp.
Factors đúng lần lượt là `q1=4/5`, `q2=(3/5)/(4/5)=3/4`, `q3=(3/10)/(3/5)=1/2`.
Wire lookup keys `(W1)`, `(W1,W2)`, `(W1,W2,W3)` chứa factors `4/5`, `3/4`, `1/2`.
Tính tay `4/5 * 3/4 * 1/2 = 3/10`, bằng cumulative probability cuối.
Nhập nhầm cumulative `4/5`, `3/5`, `3/10` rồi nhân sẽ ra `18/125`, sai đại lượng cần chấm.
Các số này chỉ dùng conformance test; tất cả rows thật vẫn pending.

## 7. Hai phiếu độc lập và quy trình đối soát

Hai artifacts điền độc lập có đầy đủ dữ liệu, không yêu cầu người thứ hai sao chép sheet thứ nhất:

- [seamless_rater_1.json](../../tests/fixtures/ranking/seamless_rater_1.json).
- [seamless_rater_2.json](../../tests/fixtures/ranking/seamless_rater_2.json).

Mỗi sheet có rater identity/organization/competence/independence/timestamp/signature null, hai scope bindings, 1 impact record, 11 conditional records, 9 effort records và WU-to-canonical mapping đầy đủ.
Giữ null là chưa chấm; sheet không phải wire query hoặc versioned parameter bundle.
A/B hoặc hai người phù hợp trong nhóm có thể là independent raters theo [clarification #143/#158](https://github.com/nairyuuu/ad-weighted-graph/pull/159#issuecomment-5927555315), ghi danh tính và năng lực/phạm vi thực tế.
Không cần tuyển panel ngoài hoặc chứng chỉ; organization/signature là metadata audit tùy chọn, `signature_required=false` trong sheets.
A gửi riêng cùng packet cho mỗi người; không chia sẻ raw scores/rationale trước khi hoàn tất independent scoring.
Người đánh giá điền identity và competence/scope, evaluator vào từng record, thời điểm, numeric/rationale/source fields và independence declaration; review trace lưu bằng issue/PR decision, chữ ký tùy chọn.

Nhánh research/LLM-assisted scenario estimates cho phép tìm primary sources, tổng hợp prerequisites và đề xuất conditional assumptions/rationale dưới scope được công bố.
Mọi nguồn phải được người chuẩn bị mở và kiểm chứng; technical description hoặc model confidence không tự chứng minh numeric probability.
Estimate phải giữ đúng q_i/outcome/full-history/F/S, basis/provenance, uncertainty, scope, sensitivity và A/B review disposition; không lấy synthetic fixture values làm default.
Hai prompts/models không là hai người chấm và không chứng minh human agreement; nhãn AI-assisted research/scenario estimate khác human rating và empirical calibration.
Có thể triển khai, tích hợp và kiểm thử dưới declared assumptions khi human agreement pending; acceptance số vẫn xét reviewed basis/validation/sensitivity và coverage trong scope.
Lượt này không điền estimates hoặc actual ratings: numeric fields/rater identity/time/rationale vẫn null và reasons là `pending_independent_ratings`.

Impact có thang `Low < Medium < High < Critical`, không dùng CIA supremum C0-C3 hoặc Tier0/CrownJewel làm điểm.
Context nghiệp vụ giả định: DC hỗ trợ dịch vụ định danh doanh nghiệp trong horizon; khả năng ảnh hưởng confidentiality/integrity/availability của dịch vụ cần rater đánh giá và giải trình.
Snapshot không chứng minh ngân hàng, khách hàng, critical SLA hoặc đây là DC duy nhất.
Không điền trước Critical để neo người chấm; record impact vẫn null.

Effort dùng governance rubric `T1,T2 in {1,2,3}`, `C=T1+T2-2 in [0,4]`, không phải giờ lao động.
T1: công cụ tiêu chuẩn/chuyên dụng/tùy biến nâng cao; T2: ma sát thấp/trung bình/cao.
Người chấm phải disposition shared preparation/overlap, không tự suy independence từ ID khác nhau.

| Construct | Governance 1.0.0 Proposed | Record phải giữ |
| --- | --- | --- |
| Impact | Cohen's Kappa reference `0.70` khi defined; N=0 -> `empty_ratings`; zero variance -> `degenerate_zero_variance`, Kappa null; N<5 -> warning | Raw ratings trước reconciliation, rationale, observed agreement, raw confusion matrix, sample size, warning và A/B review disposition |
| Likelihood | IoU reference `0.50`; identical points -> 1, distinct points -> 0; width>0.50 -> `high_epistemic_uncertainty` | Hai raw intervals/basis, IoU/widths, disagreement và reviewed final interval riêng |
| Effort | Absolute cost delta reference <=1, rubric consistency và overlap review | Raw T1/T2/C và rationale từng người, delta, unresolved overlap và disposition |

Với chỉ một target và cả hai người chấm cùng category, Kappa không defined nhưng observed agreement=1, confusion matrix vẫn phải được giữ.
Không yêu cầu Kappa defined hoặc vượt threshold cho mọi dataset; A/B đối soát một-target/small-sample/degenerate evidence theo governance, không cần panel ngoài.
Mọi thresholds là policy references Proposed, không phải validated constants hoặc acceptance tự động.
Consensus cuối không xóa bất đồng hoặc raw ratings ban đầu; rater không đủ basis được phép giữ unrated.

`reconcile_expert_ratings(record1, record2)` chỉ kiểm tra binding/rubric và đề xuất reconciliation theo từng construct; `compute_kappa_with_fallback(raw_impact_1, raw_impact_2)` tính descriptive agreement trên raw impact list.
Hai JSON sheets đã được kiểm tra bằng bản sao điền synthetic trong test, không thay đổi artifacts pending.
A phải kiểm tra query/foothold/snapshot/scenario versions/horizon khớp giữa records trước khi gọi helper; helper likelihood hiện không tự khóa mọi trường scope ngoài scenario/prefix/horizon/population.
Chỉ gọi reconciliation trên records có evaluator thật hoặc bản sao explicit synthetic; không ghi synthetic result thành actual human agreement.
Helper không xác minh chữ ký/chứng chỉ và không dùng chúng làm gate; test PASS không bật production_ready/calibrated.

## 8. Luồng E2E đã chạy và lệnh tái lập

| Bước | Phần người làm | Hàm/script và kết quả |
| --- | --- | --- |
| Chọn/bind scenario | A chọn routes, đề xuất conditions; B review vẫn pending | Hai query artifacts giữ scopes tách riêng; chưa có numeric ratings |
| Build structural graph | Policy collection time giả định được khai báo explicit | Manifest loader -> v3 adapter -> IdentityNormalizer/reconciliation -> DirectGraphBuilder/inference -> serialize/validate Graph Contract qua `src.parser.cli` |
| Extract/validate | Không chọn cạnh để bù missing evidence | `seamless_packet_evidence` xác minh mọi segment của cả 3 routes, canonical hash, raw locator và positive canonical provenance, kể cả computer-target ACL |
| Replay | Expected feasibility dựa trên declared conditions; negative variants synthetic | `execute_ranking_roundtrip`: decode -> sequential assess -> scoped frontier -> encode -> decode; 78 expected/actual cases, 14 observed locators |
| Rate/reconcile | A/B hoặc hai người phù hợp chấm độc lập, review business basis và overlap; chữ ký tùy chọn | Pending; chỉ test cơ chế bằng synthetic copies, không phải actual human agreement |
| Integrate/validate params | A cung cấp reviewed bundle/oracle khi có ratings; B sở hữu bounded integration | Pending #145/#155/#48, không implement engine/search trong helper |

`raw_path_probe.py` chỉ là research projection ba files và không giữ computer-target ACL; không dùng nó làm bằng chứng toàn route.
Canonical graph chạy hai lần cùng code/policy/export time cho byte-identical output.
Helper kiểm tra mỗi raw locator khớp explicit predicate binding, gồm đúng actor/target/kind hoặc property-owning node; swap ACE/property locator bị từ chối.
Helper lưu manifest chỉ gồm pins/digests/case summaries, không export raw records hoặc toàn graph vào Git.

Điều kiện tái lập: raw archive công khai đã giải nén nguyên vẹn tại `data/raw/SEAMLESS/`; quyền truy cập raw là prerequisite local, không commit raw/graph output.
Dependencies dùng [requirements-dev.txt](../../requirements-dev.txt), Python 3.14.2 trong `.venv`; install bằng `.venv/bin/python -m pip install -r requirements-dev.txt` khi cần.
Để graph code metadata/digest giống run đã pin, build ở exact reviewed parser revision trong checkout riêng, còn helper chạy từ PR head đã sửa:

```bash
# Chạy từ root của PR #159 đã cập nhật; dùng venv của root cho mọi Python invocation.
ADWG_PACKET_ROOT="$PWD"
ADWG_PARSER_PIN="$(mktemp -d /tmp/adwg-pr159-parser-XXXXXX)"
git worktree add --detach "$ADWG_PARSER_PIN" 4822e95045e7ebbe99316ddb56ac1b1d4e2dc30f
.venv/bin/python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
(
  cd "$ADWG_PARSER_PIN"
  "$ADWG_PACKET_ROOT/.venv/bin/python" -m src.parser.cli \
    --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 \
    --raw-dir "$ADWG_PACKET_ROOT/data/raw/SEAMLESS" \
    --profile unit --error-policy fail_fast \
    --time-policy "$ADWG_PACKET_ROOT/tests/fixtures/ranking/seamless_time_policy.json" \
    --created-at 2026-10-01T00:00:00Z \
    --output "$ADWG_PACKET_ROOT/data/processed/pr159-canonical-graph.json" --summary
)
git worktree remove "$ADWG_PARSER_PIN"
.venv/bin/python -m scripts.research.seamless_packet_evidence \
  --graph data/processed/pr159-canonical-graph.json --raw-dir data/raw/SEAMLESS \
  --output reports/generated/pr159-packet-evidence.json
.venv/bin/python -m pytest tests/test_seamless_packet.py tests/test_path_ranking_interface.py -q
```

Các lệnh snapshot/parser/helper ở trên đã thực chạy; worklog ghi kết quả và checks đầy đủ.
Để kiểm tra determinism, lặp invocation parser với output `pr159-canonical-graph-repeat.json` rồi `cmp data/processed/pr159-canonical-graph.json data/processed/pr159-canonical-graph-repeat.json`.
Graph byte digest phải bằng pin Mục 2; helper fail nếu digest/code/snapshot/provenance hoặc expected/actual khác.
Cases dương dùng proposed assumptions, không phải measured execution: feasible nhưng chưa có likelihood/impact, nên frontier rỗng và Min-Effort vẫn unrated.
Search coverage chỉ gồm ba supplied routes trong hai queries; không claim toàn không gian SEAMLESS, global optimum hoặc integrated B engine.

## 9. Status gates và missing evidence

Ma trận authoritative dùng chung ở [acceptance disposition Mục 2](path-ranking-acceptance-disposition.md).
Quy trình hướng dẫn chi tiết cho hai người chấm độc lập, schema phiếu và hiện trạng công cụ đối soát được quy định tại [evidence-rating-governance.md Mục 3.5](evidence-rating-governance.md#sec-independent-rating-instructions).
Design/interface và Scoped Parameter Bundle 1.0.0 đã được TTS A và TTS B chấp thuận trong phạm vi PR #165 (Review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338), commit `fdf5928`).
Actual human ratings, bounded integration, structural reconciliation và product E2E là các cổng riêng tiếp tục mở theo #158.
SEAMLESS predictive-ranking verdict hiện Insufficient Evidence vì bảng chấm người thật độc lập và đối soát tham số thực tế chưa hoàn tất (dữ liệu hiệu chuẩn thực nghiệm là hạng mục bằng chứng tùy chọn trong tương lai, không phải cổng chặn bắt buộc).

| Missing item | Owner | Evidence / unblock |
| --- | --- | --- |
| Design/interface explicit acceptance | A + B | **Accepted for PR #165 scope** (TTS A & TTS B phê duyệt tại #5387665338, commit `fdf5928`) |
| Scenario assumptions/bindings | A đề xuất, B review | **Accepted for PR #165 scope** (26 giả thiết runtime đã được rà soát và chấp thuận trong gói tham số 1.0.0) |
| Independent ratings / raw records | A/B hoặc hai người phù hợp trong nhóm | Hai phiếu `seamless_rater_1.json` và `seamless_rater_2.json` bảo lưu pending; quy trình chấm và luồng helper tại [governance Mục 3.5](evidence-rating-governance.md#sec-independent-rating-instructions) |
| Research-assisted scenario estimates | A chuẩn bị, A/B review | **Released in Bundle 1.0.0** (Căn cứ kỹ thuật và giả thiết công bố, digest `sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`) |
| Agreement/overlap/reconciliation | A + raters, B review | Helper đối soát theo bản ghi `reconcile_expert_ratings` và `compute_kappa_with_fallback` sẵn sàng; đối soát thực hiện giữa người với người khi có hai phiếu chấm thật; bảo lưu bảng chấm pending |
| Versioned parameter bundle + validation/sensitivity | A, B review | **Hypothesis Bundle Validated in PR #165** (Script `seamless_parameter_validation.py` xác thực 100% traces, sensitivity và conformance cho Bundle 1.0.0; việc nghiệm thu tham số cuối cùng sau đánh giá con người vẫn tiếp tục mở) |
| B bounded integration / product E2E | B implementation, A/B acceptance | Final #145->#155 adapter và positive/false/unknown outputs trên final integrated revision, coverage và clean-checkout evidence #48 |
| Legacy reconciliation | B baseline, A comparison | Same-snapshot export/scope/provenance và reviewed differences #82/#47, không thay gate ratings |

[#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) tiếp tục mở.
Scalable search, Top-K và full parity thuộc phạm vi sau theo #158; không là requirement của PR này.
