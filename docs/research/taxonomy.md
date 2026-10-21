# Taxonomy Cạnh Đồ Thị Tấn Công Active Directory: Phiên Bản v1.0

Trạng thái: M1 historical taxonomy đã được realign theo accepted #79 Phase A/B1, #80 và #94; các phần còn lại được đánh dấu theo tầng bằng chứng và owner.
Chủ trì: Thực tập sinh A (@Lolavine777).
Reviewer: Thực tập sinh B (@nairyuuu).
Liên kết nhiệm vụ: Refs #1, Refs #2, Refs #3, Refs #4, Refs #5, Refs #53, Refs #79, Refs #80.
Phiên bản schema: historical contract v0.1.0 reference; contract hien hanh la v1.0.0.
Chiến lược hiện hành: [ADR-0007](../adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md), [Attack Semantics](attack-semantics.md).
Quyết định direct-only: [ADR-0009](../adr/ADR-0009-direct-memberof-transitive-resolution.md).

Tài liệu này ghi lại tám relationship M1 và phân biệt structural evidence hiện hành với các ví dụ kỹ thuật, traversal và weighting lịch sử.
Quy tắc runtime nằm trong [catalog](../../configs/attack_semantics.yml), còn nguồn raw-field và confidence của từng claim nằm trong [evidence matrix](m1-evidence-audit.md) và [#94 audit](claim-to-field-traceability.md).

## Pham vi va ranh gioi hien hanh

Taxonomy nay mo ta structural relationship va raw-evidence associations cua M1.
`Structural Relationship != Attack Technique != Observed Activity`.
Attack Semantics so huu mapping ky thuat, runtime predicate/effect va expected telemetry.
Structural graph van static, telemetry nam o semantic/evaluation layer va khong duoc entity-level join voi SEAMLESS khi khac environment.
`maut_v1` chỉ là historical experimental profile; `unit` là baseline kiểm thử tính đúng M2.
Production cost ownership giữa relationship, transition hoặc composition chưa được quyết định và thuộc successor #42.
[Evidence matrix #79 Phase A](m1-evidence-audit.md) và [accepted #80 audit](host-access-semantics-audit.md) là căn cứ cho amendments dưới đây.
Mapping field/completeness của từng raw schema phải dùng [#94 raw-field audit](seamless-raw-field-audit.md); tên field không đủ chứng minh effective authorization.
RODC/DCSync wording ở mục 2.4 đã được reconciled bởi [PR #96](https://github.com/nairyuuu/ad-weighted-graph/pull/96), hiện đã merge vào `develop`.
Ranh gioi nay khong thay doi contract, parser hay engine behavior hien hanh.

---

## 1. Bảng Tổng Hợp 8 Loại Cạnh M1 Chuẩn Hóa

Bảng này chỉ mô tả structural relationships; kỹ thuật, runtime predicates và ExpectedTelemetry tra tại [catalog](../../configs/attack_semantics.yml).
Các raw-field associations trong [inventory](data-inventory.md) là descriptive evidence; không mặc định mọi occurrence thành canonical edge.

| Cạnh | Loại nguồn -> đích | Ý nghĩa cấu trúc | Điều kiện bằng chứng / giới hạn | Căn cứ đã chấp nhận |
| --- | --- | --- | --- | --- |
| `MemberOf` | User/Group/Computer -> Group | Quan hệ thành viên trực tiếp | Giữ source-backed membership cả khi principal disabled; không materialize transitive closure | ADR-0009; matrix #79 |
| `AdminTo` | User/Group/Computer -> Computer | Quyền quản trị local có bằng chứng gắn host | Effective local Administrators membership; domain RID riêng lẻ không đủ; network/service là runtime | ADR-0003 amended; #80 C3 |
| `GenericAll` | User/Group/Computer -> loại đích hợp lệ theo contract/catalog | Quyền FullControl trên đối tượng | Phân biệt generic bit `0x10000000` với mapped AD FullControl `0xF01FF`; không bảo đảm một technique cụ thể thành công | Matrix #79 và MS-DTYP/MS-ADTS được dẫn tại đó |
| `WriteDacl` | User/Group/Computer -> loại đích hợp lệ theo contract/catalog | Quyền sửa DACL | Mutation là transition riêng; SDProp là điều kiện persistence, không tự phủ nhận quyền đang có | Matrix #79 |
| `ForceChangePassword` | User/Group/Computer -> User | Extended right reset password | Có quyền không có nghĩa password đã được reset; runtime policy/effect do catalog xác định | Matrix #79 |
| `CanPSRemote` | User/Group/Computer -> Computer | RMU authorization theo mô hình BloodHound của repo | Cần host-bound effective evidence; WinRM availability và custom endpoint ACL assessment tách riêng | #80 C4; ADR-0003 amended |
| `CanRDP` | User/Group/Computer -> Computer | Composite remote-interactive authorization | Effective RDU membership AND allow-right AND NOT deny-right; thiếu bằng chứng bắt buộc là unknown; không sinh từ AdminTo | #80 C2; ADR-0003 amended |
| `HasSession` | Computer -> User | Session observation có timestamp / credential opportunity | Không yêu cầu đã control host để lưu observation; credential extraction và freshness là semantic/runtime concerns | #80 C8; matrix #79 |

---

## 2. Nghiên Cứu Chuyên Sâu Theo Từng Nhóm Nhiệm Vụ
 
<a id="21-nhom-identity-memberof-va-hassession-giai-quyet-issue-1"></a>
### 2.1. Nhóm Identity: MemberOf và HasSession (Giải quyết Issue #1)

#### A. Cạnh `MemberOf`

Hướng cấu trúc là `User/Group/Computer -> Group` theo direct membership evidence.
ADR-0009 giữ direct-only edges; traversal/query giải quan hệ bắc cầu với cycle guard.
Passive entitlement propagation không phải group modification, không có ATT&CK action và catalog đặt `expected_telemetry: []`.
Authentication hoặc resource access dùng entitlement vẫn có thể tạo operational audit events.
Events 4728/4729 mô tả thay đổi membership, không phải traversal; ExpectedTelemetry cụ thể thuộc technique trong catalog.

#### B. Cạnh `HasSession`

Hướng `Computer -> User` biểu diễn session observation tại một thời điểm.
Observation không khẳng định credential/token đã bị đánh cắp hoặc có thể truy xuất.
Technique `recover_session_credential_material` là transition riêng với quyền kiểm soát host, freshness và credential-accessibility predicates trong catalog.
Credential Guard / Protected Users ảnh hưởng khả năng thực thi technique, không xóa bằng chứng session khỏi structural graph.
Không dùng event ID riêng lẻ của telemetry độc lập để tạo HasSession trong SEAMLESS.

---

<a id="22-nhom-remote-access-adminto-canrdp-canpsremote-giai-quyet-issue-2"></a>
### 2.2. Nhóm Remote Access: AdminTo, CanRDP, CanPSRemote (Giải quyết Issue #2)

#### Ranh giới structural authorization và runtime

| Quan hệ | Structural authorization | Runtime predicates / giới hạn |
| --- | --- | --- |
| AdminTo | Effective local Administrators (`S-1-5-32-544`) trên host đích | Management channel, network/service reachability, authentication và Remote UAC |
| CanRDP | Effective RDU (`S-1-5-32-555`) AND `SeRemoteInteractiveLogonRight` AND NOT `SeDenyRemoteInteractiveLogonRight` | RDP service/network/authentication; không mặc định privileged execution |
| CanPSRemote | Effective RMU (`S-1-5-32-580`) theo accepted #80 | WinRM service/network/authentication; custom endpoint authorization cần assessment riêng |

Cổng 445/3389/5985/5986 hoặc trạng thái dịch vụ không phải structural-edge existence gates.
Domain Admins (`<DOMAIN-SID>-512`) là member principal tiềm năng, không thay thế host-bound local Administrators evidence.
Khả năng administrator dùng RDP là channel dưới AdminTo, không tự sinh CanRDP.
`StatusAccessDenied`, missing required primitives hoặc incomplete collection giữ `unknown`, không tự sinh positive edge.
GPO link/scope riêng lẻ chưa chứng minh resultant host state; chỉ khi applicability, effective state và toàn bộ primitive bắt buộc được chứng minh mới có positive derived authorization theo ADR-0003.
Canonical serialization của ordered derivation còn chờ #92; `assessment.status=inferred` vẫn không traversable.

---

<a id="23-nhom-ad-acl-genericall-writedacl-forcechangepassword-giai-quyet-issue-3"></a>
### 2.3. Nhóm AD ACL: GenericAll, WriteDacl, ForceChangePassword (Giải quyết Issue #3)

#### Ví dụ technique ở semantic layer, không phải thuộc tính của edge

Các ví dụ dưới đây giải thích việc sử dụng capability, không định nghĩa structural-edge existence hoặc telemetry đã quan sát.
Technique IDs, prerequisites, effects và ExpectedTelemetry lấy từ catalog; matrix #79 chứa nguồn tham chiếu và confidence.

1. **`GenericAll`:** Một ACE được giải nghĩa thành structural capability, còn reset password, thay đổi group membership và cấp quyền DACL là các transition riêng trong catalog.
   Target kind, effective ACL, account state và thao tác đã chọn quyết định applicability; edge tự nó không chứng minh thao tác nào đã xảy ra.
2. **`WriteDacl`:** Structural permission cho phép xét một transition sửa DACL khi runtime predicates được đáp ứng.
   Quyền đang có không chứng minh DACL mutation đã xảy ra hoặc một `GenericAll` edge mới đã tồn tại trong snapshot.
3. **`ForceChangePassword`:** Structural extended right và password-reset activity là hai lớp riêng.
   Event 4724 có thể là ExpectedTelemetry của một reset attempt đủ qualifier; nó không chứng minh static right, kết quả thành công hoặc fixed cost.

---

<a id="24-chinh-sach-loc-bien-va-xu-ly-ngoai-le---pruning-policy-giai-quyet-issue-4"></a>
### 2.4. Chính Sách Lọc Biên và Xử Lý Ngoại Lệ: Pruning Policy (Giải quyết Issue #4)

Structural graph bảo toàn quan hệ có bằng chứng; applicability của hành vi thuộc semantic/runtime layer.

#### 1. Tài khoản disabled / expired: amendment #80

M1 từng coi disabled accounts là terminal nodes và xóa outgoing edges.
Quyết định đó đã bị accepted #80/PR #90 supersede: không prune structural relationships chỉ vì account state.
`actor_enabled` và các account/runtime predicates được đánh giá khi thực thi semantic transition.
Không suy `out_degree == 0` từ `enabled: false` hoặc `accountExpires`; giữ incoming và outgoing evidence hợp lệ.

#### 2. Self-loops, duplicate evidence và group cycles

M1 từng đề xuất bỏ self-loop, chọn cạnh có fixed weight nhỏ nhất và phát cảnh báo parser cho group cycle.
Đó là sketch lịch sử, không phải GraphBuilder hoặc weighting contract hiện hành.
#44 sở hữu canonical identity, hướng cạnh và deterministic aggregation của duplicate raw evidence; #45 sở hữu traversal/inference với cycle guard.
Các relationship kind khác nhau giữa cùng cặp nút vẫn khác nhau về cấu trúc, nhưng policy path cost phải chờ successor của #42.
Không suy một cạnh mới từ traversal hoặc biến unknown/rejected evidence thành traversable edge.

#### 3. Xử lý các đối tượng hệ thống đặc thù

Các ghi chú M1 dưới đây là lịch sử, không cho phép prune structural evidence theo account role hoặc sinh synthetic goal edges.
PR #96 đã thay thế RODC/DCSync wording; canonical boundary fields theo Graph Contract 1.0.0 là `domain`/`is_boundary`, không phải trường `is_external` lịch sử.

- **Tài khoản `KRBTGT` (RID 502):**
  M1 từng đề xuất loại bỏ hầu hết relationship theo account role.
  Theo #80, role hoặc trạng thái disabled không cho phép prune structural evidence; applicability của từng transition cần predicate và bằng chứng riêng.
- **Bộ điều khiển miền chỉ đọc (Read-Only Domain Controllers - RODC):**
  RODC là máy chủ điều khiển miền chỉ đọc triển khai tại các chi nhánh có mức độ bảo mật vật lý thấp.
  Với cấu hình quyền nhân bản mặc định, PRP giới hạn các mật khẩu được sao chép về RODC.
  Không được suy ra một lệnh cấm DCSync tuyệt đối từ vai trò RODC hoặc danh sách PRP mặc định; quyền `Replicating Directory Changes All` được cấp sai có thể mở rộng khả năng nhân bản (xem [Microsoft KB 4050867](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/rodc-replicates-passwords-grant-incorrect-permissions)).
  Theo ADR-0008 và Graph Contract 1.0.0, đồ thị cấu trúc không chứa cạnh `ControlsDomain` hay `DCSync`.
  DCSync, nếu được mô hình hóa, thuộc tầng semantic/runtime; applicability phải dựa trên effective replication rights, PRP và bằng chứng snapshot/runtime.
  Khi thiếu bằng chứng bắt buộc, kết quả phải là `unknown` hoặc `indeterminate`, không hard-code `false` từ vai trò RODC.
  Các đối tượng RODC được định danh thông qua thuộc tính `msDS-isRODC = true` (trên đối tượng Computer) hoặc `primaryGroupID = 521` (nhóm Read-only Domain Controllers) kết hợp với cờ UAC `SERVER_TRUST_ACCOUNT`.
  Việc đánh giá phạm vi chiếm quyền phải kiểm tra quyền nhân bản hiệu lực và PRP thực tế, không chỉ cấu hình PRP sai lệch.
- **SID ngoại lai từ Forest cha (Foreign SIDs):**
  M1 từng đề xuất gắn `is_external: true` theo SID prefix và cô lập cạnh ngoài miền.
  Graph Contract 1.0.0 dùng `domain`/`is_boundary`; #44 phải resolve identity và trust scope, không suy boundary chỉ từ prefix hoặc tạo cạnh traversable khi identity chưa giải được.

---

### 2.5. Quy chuẩn Semantics và Biểu diễn Group Nesting (Giải quyết Issue #53)

Dựa trên kết quả khảo sát thực nghiệm tại [group-nesting-findings.md](group-nesting-findings.md), quan hệ lồng nhóm (Group Nesting) chiếm tới gần 40% tổng số quan hệ thành viên trong dữ liệu thực tế (15/42 ở Dataset A và 63/161 ở Dataset B).
Phần này diễn giải quy chuẩn taxonomy theo [ADR-0009](../adr/ADR-0009-direct-memberof-transitive-resolution.md):

#### 1. Quyết định lưu trữ Direct-Only (Không materialize transitive MemberOf)
- **Quyết định:** Structural graph chỉ lưu `MemberOf` trực tiếp (direct-only), sau identity resolution và reconciliation của source-backed evidence; không mặc định raw occurrences ánh xạ 1:1 thành canonical edges.
- **Căn cứ khoa học và thực nghiệm:**
  1. *Baseline lịch sử:* Dataset A/B ghi nhận 42 và 161 direct `MemberOf` observations trong phạm vi đã khảo sát; đó không phải same-snapshot SEAMLESS parity hoặc quy tắc cho current builder.
  2. *Không tạo đường tắt không có bằng chứng:* Materialize cạnh bắc cầu sẽ che khuất số bước và provenance của chuỗi raw relationship.
    Chính sách weighting, nếu được dùng trong một evaluation sau này, phải được quyết định riêng và không suy ra từ quy tắc direct-only.
  3. *Bảo toàn audit provenance:* Direct evidence cần trỏ về raw file, record và field; collection time thiếu hoặc suy ra phải giữ trạng thái theo #91/#97, không bịa timestamp.
    Derived traversal cần ordered lineage theo #92 nếu được serialize; nó không có một raw source record độc lập tương đương direct edge.
- **Quy tắc phân tầng:** Direct `MemberOf` được lưu riêng; transitive entitlement là traversal/inference, không materialize thành direct source edge.

#### 2. Xử lý chu trình nhóm (Group Cycles)
- **Hiện trạng dữ liệu:** Dữ liệu thực tế Dataset A và Dataset B đều không có chu trình nhóm (0 cycles).
- **Quy tắc phòng vệ (Cycle Guard):**
  Direct evidence của chu trình có thể được giữ sau resolution; traversal/inference phải tránh lặp vô hạn và không giả định đã có parser warning cụ thể.

#### 3. Xử lý đa đường kế thừa (Multiple Inheritance Paths / Diamond Pattern)
- **Hiện trạng dữ liệu:** Xuất hiện phổ biến trong Dataset B (ví dụ nhóm `EXCHANGE-ADMINS` kế thừa `EXCHANGE SERVERS` qua cả 2 nhánh trực tiếp và trung gian).
- **Quy tắc xử lý:**
  - Trên structural graph: Cả hai nhánh direct edges đều được giữ nguyên độc lập để phản ánh đúng hai kênh truyền quyền trong AD.
  - Khi suy luận đặc quyền host (M2-06): Nhiều nhánh cần deterministic assessment và ordered derivation theo #92; chưa emit canonical derived traversable edge trước khi contract lineage được chấp nhận.

#### 4. Lồng nhóm xuyên miền (Cross-Domain Nesting / Foreign Security Principal)
- **Quan sát lịch sử:** Dataset A/B có foreign-principal shaped references, nhưng khả năng traversal xuyên miền cần identity, trust và scope resolution theo #44/#45.
- **Cơ chế định danh:** Không cắt bỏ prefix hoặc làm phẳng domain context khi canonical identity chưa được chứng minh.

#### 5. Sử dụng Group Nesting trong suy luận quyền truy cập Host (AdminTo, CanRDP, CanPSRemote)
- **Quy tắc suy luận ngược (Backward Transitive Traversal):**
  - Quyền truy cập host thường được gán vào Local Groups của máy tính đích (`S-1-5-32-544`, `S-1-5-32-555`, `S-1-5-32-580`).
  - #45 là implementation kế tiếp cho effective membership resolution; chưa coi module inference là đã triển khai.
  - Đường membership chỉ là một primitive; phải kiểm đủ điều kiện từng quan hệ theo #80, đặc biệt allow/deny của CanRDP, rồi bảo toàn ordered derivation theo quyết định #92.

#### 6. Nguyên tắc bằng chứng không đầy đủ (Incomplete Evidence)
- **Quy tắc:** Khi một mắt xích trong chuỗi group nesting bị thiếu (unresolved SID, missing group record hoặc thu thập thất bại), hệ thống tuyệt đối KHÔNG được coi là `false` (không có quyền).
  Trạng thái này phải được ghi nhận là `unknown` và không sinh cạnh truy cập giả tạo.

---

## 3. Dữ Liệu Mẫu Tổng Hợp (Synthetic Fixtures)

Ví dụ dưới đây là sketch M1 lịch sử với bốn quan hệ, không phải Graph Contract 1.0.0 fixture hợp lệ.
Các ID và provenance shorthand (đặc biệt `inferred:scoped_gpo`) không được dùng làm serialization contract hoặc chứng minh positive derived edge.
Fixture chuẩn hiện hành: [m1-fixtures.json](../../data/samples/m1-fixtures.json); ordered derivation chờ #92.

```json
{
  "metadata": {
    "contract_version": "0.1.0",
    "synthetic": true
  },
  "nodes": [
    {"id": "USER_ATTACKER", "kind": "User", "label": "Attacker Foothold"},
    {"id": "GROUP_OPERATORS", "kind": "Group", "label": "Server Operators"},
    {"id": "COMP_MEMBER", "kind": "Computer", "label": "Member Workstation"},
    {"id": "USER_ADMIN", "kind": "User", "label": "Tier-1 Administrator"},
    {"id": "GROUP_DA", "kind": "Group", "label": "Domain Admins"}
  ],
  "edges": [
    {
      "id": "EDGE_01",
      "source": "USER_ATTACKER",
      "target": "GROUP_OPERATORS",
      "kind": "MemberOf",
      "provenance": "synthetic:active_directory:member"
    },
    {
      "id": "EDGE_02",
      "source": "GROUP_OPERATORS",
      "target": "COMP_MEMBER",
      "kind": "CanRDP",
      "provenance": "synthetic:inferred:scoped_gpo:S-1-5-32-555"
    },
    {
      "id": "EDGE_03",
      "source": "COMP_MEMBER",
      "target": "USER_ADMIN",
      "kind": "HasSession",
      "provenance": "synthetic:memory:registry_session"
    },
    {
      "id": "EDGE_04",
      "source": "USER_ADMIN",
      "target": "GROUP_DA",
      "kind": "MemberOf",
      "provenance": "synthetic:active_directory:member"
    }
  ]
}
```
