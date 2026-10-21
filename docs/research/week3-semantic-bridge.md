# Semantic bridge Week 3 — #180

Trạng thái: đề xuất implementation để A review. Refs #155, #174, #48; API #179 đã merge vào develop tại `63fd005c16d8cc2e7323da2ff9da1f0b836d8bb2`. Không thay release #176 hoặc tiêu chí nghiệm thu của #179.

## Ownership, capability và actor

Catalog 0.3 thêm hai quan hệ capability `AuthenticationControl` và `DeclaredHostAdmin` trong tầng search/state. Chúng không phải edge kind của canonical graph; contract 1.3.0 và raw không đổi. `scenario_reset_password` giữ owner của bước reset trong rubric và thêm qualifier reset-password cùng directory-channel gate; owner cũ vẫn tương thích.

| Query / action | Owner | Prerequisite và layer | Effect / actor tiếp theo | Căn cứ |
| --- | --- | --- | --- | --- |
| source_a / `action_reset_lidia` | `scenario_reset_password` | L1 GenericAll; L2 enabled; L3 foothold/identity, password policy, directory write/channel | authentication_control + reset_password_control(target); actor chưa đổi | [MS-ADTS unicodePwd][reset] |
| source_a / `action_activate_lidia` | `acquire_reset_identity` | Branch reset_password_control; L2 actor enabled; L3 KDC reachability + authentication accepted | usable_identity(actor, authentication_context); chọn actor đó trên cùng branch | [Kerberos][kerberos] |
| source_a / `action_closure_lidia_da` | `propagate_group_entitlement` | L1 MemberOf; usable identity ở context đã chọn; L3 security-group/token usability | effective_member(actor, group); giữ actor; không thêm work | [Access tokens][tokens] |
| source_a / `action_winrm_badblood_lidia` | `scenario_winrm_admin` | L1 route GenericAll được giữ làm evidence; effective membership; L3 host mapping, network/listener, authentication, endpoint ACL, elevated unrestricted context; L2 actor/target enabled | admin_control(target); mới đạt terminal | [DA defaults][da], [WinRM][winrm] |
| source_a / `action_reset_josefa` | `scenario_reset_password` | L1 GenericAll; L2 enabled; L3 foothold/identity, password policy, directory write/channel | authentication_control + reset_password_control(target); actor chưa đổi | [MS-ADTS unicodePwd][reset] |
| source_a / `action_activate_josefa` | `acquire_reset_identity` | Branch reset_password_control; L2 actor enabled; L3 KDC reachability + authentication accepted | usable_identity(actor, authentication_context); chọn actor đó trên cùng branch | [Kerberos][kerberos] |
| source_a / `action_closure_josefa_vajer` | `propagate_group_entitlement` | L1 MemberOf; usable identity ở context đã chọn; L3 security-group/token usability | effective_member(actor, group); giữ actor; không thêm work | [Access tokens][tokens] |
| source_a / `action_reset_ollie` | `scenario_reset_password` | L1 GenericAll; L2 enabled; L3 foothold/identity, password policy, directory write/channel | authentication_control + reset_password_control(target); actor chưa đổi | [MS-ADTS unicodePwd][reset] |
| source_a / `action_activate_ollie` | `acquire_reset_identity` | Branch reset_password_control; L2 actor enabled; L3 KDC reachability + authentication accepted | usable_identity(actor, authentication_context); chọn actor đó trên cùng branch | [Kerberos][kerberos] |
| source_a / `action_closure_ollie_da` | `propagate_group_entitlement` | L1 MemberOf; usable identity ở context đã chọn; L3 security-group/token usability | effective_member(actor, group); giữ actor; không thêm work | [Access tokens][tokens] |
| source_a / `action_winrm_badblood_ollie` | `scenario_winrm_admin` | L1 route GenericAll được giữ làm evidence; effective membership; L3 host mapping, network/listener, authentication, endpoint ACL, elevated unrestricted context; L2 actor/target enabled | admin_control(target); mới đạt terminal | [DA defaults][da], [WinRM][winrm] |
| source_b / `action_reset_ollie_from_b` | `scenario_reset_password` | L1 GenericAll; L2 enabled; L3 foothold/identity, password policy, directory write/channel | authentication_control + reset_password_control(target); actor chưa đổi | [MS-ADTS unicodePwd][reset] |
| source_b / `action_activate_ollie` | `acquire_reset_identity` | Branch reset_password_control; L2 actor enabled; L3 KDC reachability + authentication accepted | usable_identity(actor, authentication_context); chọn actor đó trên cùng branch | [Kerberos][kerberos] |
| source_b / `action_closure_ollie_da` | `propagate_group_entitlement` | L1 MemberOf; usable identity ở context đã chọn; L3 security-group/token usability | effective_member(actor, group); giữ actor; không thêm work | [Access tokens][tokens] |
| source_b / `action_winrm_badblood_ollie` | `scenario_winrm_admin` | L1 route GenericAll được giữ làm evidence; effective membership; L3 host mapping, network/listener, authentication, endpoint ACL, elevated unrestricted context; L2 actor/target enabled | admin_control(target); mới đạt terminal | [DA defaults][da], [WinRM][winrm] |

## Phạm vi và giả định

- `usable_identity(user, context)` cho phép authenticated directory actor trong một context của scenario, không khẳng định có process control trên máy của user. Giữ foothold trong state; không tự chuyển authentication_control tổng quát thành quyền điều khiển.
- Acquire-ticket dùng actor/source = user mới, target = DC/context của action đã chấm. Derived trace trỏ về reset đã tạo qualifier. Không tạo cạnh cấu trúc hoặc action/work mới cho bookkeeping.
- Membership closure dùng đúng actor và group entitlement trên branch. Reset tiếp theo qua group yêu cầu effective_member(actor, group).
- WinRM dùng GenericAll group→computer chỉ để bảo toàn route evidence của release. Quyền remote admin đến từ declared DA host mapping + các gate runtime; không suy ra WinRM từ GenericAll và không tạo AdminTo/CanPSRemote.
- Không có rating mới, không đổi work-unit ID, full-prefix binding hoặc exact rational values. Extra histories không có basis giữ diagnostics/unrated. Không mô hình ticket lifetime/renewal hoặc cross-context propagation.

## Hai evidence view cần A review

| Case | Exact evidence rút | Search decision | Audit |
| --- | --- | --- | --- |
| `w3-source-a-structural-missing` | Provenance `20210920185958_users.json#/users/2310/Aces/3` của cạnh GenericAll foothold→Lidia | `relationship_exists` unknown khi không còn support khác | Verified raw pointer → ObjectIdentifier / PrincipalSID / RightName → canonical raw_file, record_id, attribute; giữ record gốc trong delta |
| `w3-source-a-telemetry-missing` | Observation `20210920185958_users.json#/users/2310/Properties/enabled` | Reset `target_enabled` và acquire `actor_enabled` unknown; nhánh khác giữ nguyên | Verified raw pointer→identity; pop enabled chỉ trên copy, không default true; known-false không được rút |

`counterfactual_view` ghi baseline/view/delta digests và exact locator. Canonical baseline/raw bất biến. Nếu edge còn independent support, giữ cạnh và không biến nó thành unknown. Nếu raw bị sửa/checksum mismatch, mapping fail-closed. Không công bố mapping là reviewed cho tới khi A duyệt exact head.

## Lệnh tái lập và tích hợp #179

```bash
python -m src.parser.cli --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 --raw-dir data/raw/SEAMLESS --manifest-dir data/samples/manifests --time-policy data/samples/parser-demo/time-policy.json --error-policy fail_fast --created-at 2026-10-03T14:17:10Z --output data/processed/graphs/week3-180-canonical.json --summary
python scripts/research/week3_semantic_bridge_probe.py --graph data/processed/graphs/week3-180-canonical.json --raw-dir data/raw/SEAMLESS --case-id w3-source-a-positive --output reports/generated/week3-180/source-a-positive.json
python -m pytest tests/test_week3_semantic_bridge.py -q
```

Probe gọi generate_attack_paths thật, bind exact transition identity rồi dùng adapter/evaluator canonical hiện có. Supplied programs chỉ đối chiếu ordered action/work identity, không inject/replay vào generator. Probe chưa thay final acceptance harness #179; negative completion/pins/case expectations vẫn thuộc #179.

Handoff #179: dùng `semantic-bridge-plan.json` làm source plan; gọi `counterfactual_view` trước EngineGraph; truyền `runtime_for_projection` context có authentication_context/withheld_relationships; giữ terminal predicate target + admin_control(target). Ownership/bindings được cung cấp cho cả hai query. Consume `search-integration-plan.json` đã accepted và merge qua #179; bridge chỉ tham chiếu artifact này, không sao chép pins.

Source A dùng caps 25 paths / 10 steps / 60000 expansions, Source B cùng caps. Actual source A có thể truncated; không suy global optimum hay global no-path từ tập sinh được. Full AD outputs giữ local theo data policy; handoff #48 gồm report files, graph/raw/runtime/revision pins và hai deterministic runs.

[reset]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6e803168-f140-4d23-b2d3-c3a8ab5917d2
[kerberos]: https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-authentication-overview
[tokens]: https://learn.microsoft.com/en-us/windows/win32/secauthz/access-tokens
[da]: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/security-best-practices/appendix-b--privileged-accounts-and-groups-in-active-directory
[winrm]: https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/winrm-security


## Acceptance artifact đã accepted từ #179

Bridge plan schema 1.3.0 chỉ giữ `acceptance_manifest.accepted_plan_path` trỏ đến
`search-integration-plan.json`; không copy blob/source-revision pins riêng.
Probe đọc pin từ accepted plan, kiểm tra exact Git blob bytes, canonical digest,
release digest và tập case IDs trước khi dùng fixture hoặc chạy search.
Report ghi accepted-plan file/canonical digests và manifest pins thực sự đã kiểm tra.

Artifact hiện được accepted có source revision `6d06dc7bb9352db568eb7dc6deb92285a8d32489`,
blob `fa60208cfd4d9621f2ee22edc3489eb960a6a686` và canonical digest
`sha256:73048e3f93be293556e65dc0e8c950255d7b77b9194b150f86b85b6cfc254c28`.
Source revision mô tả nguồn artifact; baseline/harness API reference của bridge là
merged develop `63fd005c16d8cc2e7323da2ff9da1f0b836d8bb2`.
Runtime scope và structural/capability type boundary đã được thống nhất như bên dưới.

## Runtime policy chung và type boundary

`projection_runtime.context_for_projection` là runtime builder chung của bridge và
harness #179. Declared assumptions giữ `query_metadata.horizon`; blocked/unknown
facts dùng `scenario_id`; observed evidence có `scope=None`. Known-false overlay
có ưu tiên veto dù assumption true cũ còn trong ledger; override không nâng false
thành true/unknown. Foothold, authentication_context và withheld evidence vẫn do
bridge gắn vào context/state riêng.

`RelationshipKind`/`StructuralRelationshipKind` chỉ chứa tám structural kinds.
`CapabilityRelationshipKind` chứa AuthenticationControl/DeclaredHostAdmin;
`Technique.relationship` dùng `SemanticRelationshipKind` rộng hơn. Search và
evaluator dùng `CapabilityRelationship` cho hai trigger này. Constructors của
structural relationship/state/withheld evidence từ chối capability. Canonical
contract, raw graph và rating/release/oracle giữ nguyên.

Regression gồm scope parity trên cả tám actual release cases, assumption horizon,
false/unknown scenario scope, known-false veto và rejection tại structural state
boundary. Đây không thay actual raw/probe acceptance trên head mới.
