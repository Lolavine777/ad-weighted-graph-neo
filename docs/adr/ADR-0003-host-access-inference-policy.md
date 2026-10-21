# ADR-0003: Chinh sach suy luan canh truy cap may tram (Host Access Inference)

- Ngay: 2026-09-14
- Trang thai: Accepted, amended by issue #80 (2026-09-22), observational-boundary clarification (2026-09-25)
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #2, Refs #5, Refs #80, Refs #92

## Boi canh

Khi khảo sát tập dữ liệu thô xuất ra từ BloodHound, các cạnh `AdminTo`, `CanRDP`, `CanPSRemote` không phải là AD object ACLs trong `Aces[]` mà phụ thuộc vào bằng chứng host-local như local-group membership, user-right assignment và policy áp dụng lên máy đích.

M2 sau đó chọn SEAMLESS (BloodHound v3-style) làm primary structural dataset và ADR-0008 tách canonical Structural Relationship khỏi Attack Semantics/runtime state. Issue #80 revalidated ADR này vì một số rule cũ đang trộn collector representation, runtime reachability và structural edge existence.

Hai nguyên tắc nền sau amendment:

1. **Preserve structural evidence.** Trạng thái runtime như account disabled, service stopped, port blocked hoặc `Connectable=false` không xóa bằng chứng structural đã thu thập thành công.
2. **Unknown is not false.** `StatusAccessDenied`, method-not-run, missing field hoặc incomplete collection không chứng minh quan hệ không tồn tại.
3. **Evaluation graph is a positive-evidence projection of the input SoT.** Khi input được chọn làm Source of Truth cho lần đánh giá, canonical graph chỉ materialize relationship có đủ positive evidence theo rule hiện hành. Nếu evidence bắt buộc thiếu hoặc unknown thì không có traversable edge; assessment vẫn ghi limitation. Sự vắng mặt của edge chỉ có nghĩa input SoT này chưa chứng minh connection, không phải chân lý rằng connection ngoài thực tế không tồn tại.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| 1. Chỉ trích xuất specialized arrays như `LocalAdmins`/`RemoteDesktopUsers` | Parser đơn giản | Dễ đánh đồng raw membership với effective access; không xử lý user-right/deny/completeness | Raw collector schema |
| 2. Suy luận mở dựa trên RID/global privileged group | Tạo nhiều đường đi | False positive cao; không host-bound | Kiểm thử sơ bộ |
| 3. Suy luận có bằng chứng gắn host + tri-state completeness + runtime separation | Phù hợp Windows/BloodHound semantics và ADR-0008 | Cần adapter/inference riêng; ordered derivation serialization cần decision riêng | Microsoft + SpecterOps + #80 audit |

## Quyet dinh va he qua

Chọn phương án 3.

### 1. Full well-known SID + host scope

Bắt buộc đối chiếu SID well-known đầy đủ:

- Local Administrators: `S-1-5-32-544`.
- Remote Desktop Users: `S-1-5-32-555`.
- Remote Management Users: `S-1-5-32-580`.

`<DOMAIN-SID>-512` chỉ xác định Domain Admins của domain. RID `-512` hoặc việc group đó tồn tại/high-value không tự tạo `AdminTo` tới host bất kỳ. Cần bằng chứng host-bound cho effective local Administrators membership.

### 2. Host-bound evidence

Host-access relation chỉ được materialize từ positive evidence gắn với target host, ví dụ:

- direct collector evidence: specialized v3 arrays hoặc `LocalGroups[]`/`UserRights[]` của chính host;
- effective nested membership được resolve từ direct membership chain;
- fully resolved resultant/effective GPO state theo rule ở mục 7.

Raw collector array là evidence primitive, không mặc nhiên là universal Windows truth.

### 3. `CanRDP` composite rule

Canonical BloodHound-compatible `CanRDP(principal, host)` chỉ được materialize khi:

```text
effective_member(principal, Host\Remote Desktop Users)
AND effective_right(principal, host, SeRemoteInteractiveLogonRight)
AND NOT effective_right(principal, host, SeDenyRemoteInteractiveLogonRight)
```

Quy tắc:

- Nested security-group membership phải được tính trong effective membership/right evaluation.
- Effective deny có precedence so với allow.
- Bất kỳ required primitive nào `unknown` thì kết quả `CanRDP` là `unknown`, không có traversable edge.
- `RemoteDesktopUsers[]` hoặc membership `S-1-5-32-555` một mình chỉ là membership evidence, không phải verified `CanRDP`.
- Allow-right một mình cũng không tạo canonical `CanRDP` edge. Nếu principal có local-admin authorization, relation đó thuộc `AdminTo`; việc chọn RDP làm technique/channel thuộc Attack Semantics.

### 4. `AdminTo`

`AdminTo(principal, host)` biểu diễn effective local-administrator authorization trên host đó.

Positive evidence có thể đến từ:

- direct `LocalAdmins[]`;
- `LocalGroups[]` của `S-1-5-32-544`;
- nested membership chain dẫn tới local Administrators;
- fully resolved resultant/effective policy tạo ra local-admin state.

Không yêu cầu SMB/RPC/RDP/WinRM availability để edge structural tồn tại.

### 5. `CanPSRemote`

Effective host-bound membership trong Remote Management Users (`S-1-5-32-580`) được chấp nhận là BloodHound-compatible structural evidence cho `CanPSRemote`.

Tuy nhiên, Windows PowerShell remoting endpoint có thể bị giới hạn thêm bởi session-configuration security descriptor. Vì vậy:

- RMU membership không được mô tả là independently verified custom-endpoint access nếu endpoint ACL không được collect;
- explicit endpoint ACL evidence, nếu có, là evidence mạnh hơn và có thể xác nhận/reject modeled relation;
- WinRM service/listener/firewall/network availability thuộc runtime Attack Semantics, không phải edge-existence rule.

### 6. Tri-state collection semantics

Mỗi primitive cần được đánh giá ít nhất theo ba trạng thái:

- `positive`: có bằng chứng dương;
- `negative-known`: collection của đúng primitive thành công/đầy đủ và chứng minh không có assignment;
- `unknown`: `StatusAccessDenied`, method-not-run, field missing mà không có completeness proof, unresolved SID, incomplete collection hoặc trạng thái tương đương.

Không được collapse `unknown` thành `false`.

Positive evidence của một primitive vẫn được giữ dù primitive khác chưa collect đầy đủ.

### 7. GPO-derived host access: hybrid promotion

Scoped GPO không còn được xử lý bằng một rule blanket.

**Non-traversable assessment** nếu mới chỉ biết một hoặc nhiều điều sau:

- GPO chứa setting liên quan;
- có link đến Site/Domain/OU;
- target có vẻ nằm trong scope;
- static/modeling step chưa resolve hết applicability/effective result.

**Positive derived structural evidence** chỉ khi resolver chứng minh resultant/effective host state sau các yếu tố cần thiết, bao gồm khi applicable:

```text
GPO setting
-> active link
-> target scope
-> security filtering
-> WMI filtering
-> inheritance / Enforced / Block Inheritance / link order
-> relevant client-side extension semantics
-> resultant local-group or user-right state
-> derived host-access relation
```

Derived traversable relation vẫn phải dựa trên positive evidence. Tại thời điểm ADR này được phê duyệt, **Graph Contract 1.0.0 chưa có canonical field để serialize ordered derivation lineage**: `edge_optional: []` và edge `provenance` chỉ là tập raw evidence records, không phải ordered causal path. ADR-0011 / Contract 1.1.0 là successor serialization decision cho boundary này.

Do đó amendment này chốt **semantic requirement**; Contract 1.1.0/ADR-0011 hiện cung cấp representation cho #92. Inference code vẫn phải giữ derivation evidence nội bộ và không được giả vờ unordered provenance bag là complete ordered lineage.

`assessment.status=inferred`/`unknown` vẫn non-traversable.

### 8. Runtime/network/service separation

Các điều kiện sau không tạo/xóa structural edge:

- account enabled/disabled;
- `Connectable`;
- TCP reachability;
- RDP/TermService state;
- WinRM service/listener/firewall state;
- NLA/authentication acceptance;
- management-channel availability.

Chúng thuộc Attack Semantics predicates như `actor_enabled`, `rdp_available`, `winrm_available`, `admin_channel`, `authentication_accepted`.

`Connectable=false` không được phủ quyết positive evidence đã thu thập thành công.

### 9. `HasSession` boundary

`HasSession(Computer -> User)` là structural observation rằng qualifying user session đã được collector quan sát trên host tại `collected_at`.

Nó không khẳng định:

- credential material hiện còn tồn tại;
- attacker có local admin/SYSTEM;
- LSASS/token access thành công;
- Credential Guard hoặc endpoint control bị bypass;
- credential dumping đã xảy ra.

Các điều kiện đó thuộc Attack Semantics/runtime. Session source kind (`Sessions`, `PrivilegedSessions`, `RegistrySessions`) và timestamp/provenance nên được giữ khi adapter hỗ trợ.

## Schema mapping consequence

### SEAMLESS BloodHound v3-style

- `LocalAdmins[]`: local-admin membership primitive.
- `RemoteDesktopUsers[]`: RDU membership primitive; không verified `CanRDP` một mình.
- `PSRemoteUsers[]`: RMU membership primitive.
- `Sessions[]`: session observation primitive.
- Missing specialized arrays hoặc empty arrays không tự chứng minh negative nếu snapshot không có collection-completeness/error evidence.

### Historical SharpHound/BloodHound.py A/B

- `LocalGroups[]`: host-local-group primitive; match full `S-1-5-32-*` SID + host scope.
- `UserRights[]`: required input cho effective `CanRDP` khi collector cung cấp.
- `Sessions`, `PrivilegedSessions`, `RegistrySessions`: distinct session evidence sources.
- Per-primitive status/failure metadata phải được preserve; `StatusAccessDenied` => `unknown`.

Dataset schema chỉ cho biết snapshot chứa gì; không định nghĩa universal Windows behavior.

## Hệ quả cho implementation

- #44 không được prune structural node/edge vì `enabled == false`.
- #44 mô tả `HasSession` như session observation, không phải credential-dumping guarantee.
- #45 phải dùng tri-state primitive handling và composite `CanRDP` rule.
- #45 không gate edge existence bằng ports/services/`Connectable`.
- GPO resolver chỉ có thể promote traversable edge khi resultant/effective state được chứng minh **và** canonical serialization của derived lineage đã được chốt theo #92.
- #92 blocks serialization của nested/GPO-derived traversable edges; direct host-access evidence không cần chờ representation này.
- EDA/reporting phải phân biệt raw RDU/RMU membership count với verified effective host-access edge count.

## Nguon authoritative

- SpecterOps CanRDP: https://bloodhound.specterops.io/resources/edges/can-rdp
- SpecterOps AdminTo: https://bloodhound.specterops.io/resources/edges/admin-to
- SpecterOps CanPSRemote: https://bloodhound.specterops.io/resources/edges/can-ps-remote
- SpecterOps HasSession: https://bloodhound.specterops.io/resources/edges/has-session
- Microsoft Allow log on through Remote Desktop Services: https://learn.microsoft.com/en-us/windows/device-security/security-policy-settings/allow-log-on-through-remote-desktop-services
- Microsoft Deny log on through Remote Desktop Services: https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/security-policy-settings/deny-log-on-through-remote-desktop-services
- Microsoft Group Policy processing: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing
- Microsoft Group Policy Modeling/Results: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-modeling-results

## Kiem chung va dieu kien xem lai

- Regression không được enforce `disabled => out_degree == 0`; phải chứng minh một disabled principal có positive outgoing structural edge vẫn tạo graph contract-valid.
- Synthetic #45 tests phải cover: membership+allow+no-deny, deny precedence, membership-only, right-only, nested membership, `StatusAccessDenied`, successful-empty primitive, `Connectable=false`, GPO unresolved/effective cases.
- Derived-edge serialization tests thuộc #92 trước khi nested/GPO-derived positive edges được phát hành theo canonical Graph contract.
- Chạy `uv run pytest`, Ruff, yamllint, `uv run python scripts/check_contract.py`, `uv run python scripts/check_repository.py`, `git diff --check`.
- Điều kiện xem lại: collector bổ sung endpoint ACL/RSoP evidence hoặc taxonomy canonical edge set thay đổi qua ADR mới.
