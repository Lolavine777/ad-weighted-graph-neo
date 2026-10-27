# Attack Semantics cho weighted AD graph

Trạng thái: Implemented architecture reference (research v0.1) + M3 predictive-state decision proposal.
Liên kết nhiệm vụ: Refs #58, #63, #70, #145, #174, #180, PR #66, PR #173.
Quyết định kiến trúc: [ADR-0008](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0008-structural-graph-attack-semantics-layering.md); data/telemetry evaluation scope: [ADR-0007](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md).
Contract tham chiếu: `configs/contract.yml` v1.2.0 (graphs v1.0.0/1.1.0 vẫn tương thích ngược; legacy timestamp status là `unknown_legacy`).
Phạm vi: 8 canonical edge kinds của M1.

## Amendment theo #174: predictive attacker capability

Research M3 của #174 chốt abstraction authentication ở mức capability thay vì mô phỏng protocol. Decision chi tiết nằm tại [Predictive state transitions](attack-semantics-predictive-state-transitions.md).

Disposition chính:

- state bridge khái niệm mặc định là `CredentialPossession(principal, form) -> activate_identity(principal, authentication_context) -> UsableIdentity(principal, authentication_context)`;
- current implementation `usable_identity` vẫn authoritative ở dạng `(principal, authentication_context)`; mọi shorthand `UsableIdentity(principal)` không được hiểu là context-free/global capability;
- actor switching chỉ được phép khi tuple identity/context khớp `RuntimeContext.authentication_context`; target/service-specific predicates vẫn được đánh giá riêng, nên không phải blanket guarantee rằng authentication sẽ thành công;
- `acquire_ticket` của Week 3/PR #173 được giữ như ranking/work-unit compatibility alias, không là persistent semantic state và không ép mọi path phải có TGT/service ticket;
- ticket-specific state chỉ materialize khi một technique cụ thể thực sự cần artifact đó; pre-secret AS-REP/Kerberoast ciphertext phải ở phase recoverable material riêng và không được map thẳng thành credential/usable identity;
- lifetime/timestamps không nằm trong core `AttackState`; retry/deadline/horizon thuộc scenario/evaluator trừ khi một future ADR chứng minh cần state thời gian;
- known-false prerequisite trả `blocked`; thiếu required evidence trả `indeterminate`; explicit `RuntimeContext` chỉ giải quyết unknown được policy cho phép và không override known-false;
- transition effects chỉ tạo derived attacker state/scenario overlay, **không mutate canonical snapshot hoặc provenance**;
- Semantics sở hữu applicability + derived capability + rationale/evidence/assumptions; whole-path evaluator sở hữu probability, time/cost, impact, risk và numeric detection penalty.

Corrections quan trọng so với wording research cũ:

- administrative password reset dựa trên `User-Force-Change-Password`; target disabled không tự làm thao tác reset impossible, mà là blocker cho việc sử dụng identity ở bước authentication;
- `WriteDacl` không phải direct reset evidence: phải có ACL-modification transition riêng trước khi sinh right/capability mới;
- `adminCount=1`/AdminSDHolder không là blanket blocker cho một reset right hiện hữu;
- Remote Management Users/remoting access không tự suy ra `local_admin`; privilege output phải được endpoint/token/scenario evidence chứng minh;
- RDP deny-right không được dùng như alias cho WinRM authorization;
- không hardcode "10 giờ" làm semantic horizon và không biến expected Event ID thành numeric detection weight.

Decision này dùng applicability/whole-path boundaries của #145, reuse scoped bridge đã accepted ở #180 và không yêu cầu rewrite graph loader/search foundation. Current `AttackState` buckets (`credential_material`, `authentication_control`, `reset_password_control`, context-scoped `usable_identity`, `admin_control`, `remote_command_execution`, v.v.) giữ implementation meaning hiện hành; compatibility/migration disposition đầy đủ nằm trong decision document. Đặc biệt, `credential_material` hiện là coarse untyped bucket và không tự alias sang typed `CredentialPossession`; `HostExecution` chỉ là conceptual umbrella, không replace `admin_control` hoặc `remote_command_execution` trong #174.

## Amendment theo #79 Phase A và accepted #80

[Evidence matrix](m1-evidence-audit.md) phân tách structural evidence, semantic transition, runtime predicate, expected telemetry, observed telemetry và weighting status.
[configs/attack_semantics.yml](../../configs/attack_semantics.yml) là nguồn runtime semantics duy nhất; các ví dụ research dưới đây không phải catalog/schema bổ sung.
#94/PR #99 cung cấp raw-field và qualifier evidence đã accepted; #80/PR #101 đã sửa EDA host-access semantics, #79 B1/PR #102 đã sửa telemetry inventory, và #81/PR #103 đã bổ sung structured provenance cho semantic mappings/ObservedActivity.
PR #106 bổ sung whole-snapshot verification, correlation-construction invariants và evidence coverage của Events 4728/4756 cho provenance contract.
Không dùng các ví dụ để claim corpus-observed technique, canonical serialization readiness hoặc production cost ownership.

## Amendment theo #81: provenance contract (catalog v0.2)

`configs/attack_semantics.yml` v0.2 là catalog semantic normative. Mỗi mục
`expected_telemetry` khác rỗng phải có `evidence_refs` trỏ tới
`evidence_registry`. Registry ghi rõ claim mà nguồn hỗ trợ, source/locator,
rationale áp dụng và confidence. Đây là semantic mapping evidence; nó không
phải dữ liệu cho biết event đó đã xuất hiện trong corpus. `MemberOf` tiếp tục là
transition thụ động nên có `expected_telemetry: []` và không cần evidence ref.

Catalog v0.1 không được tự động đọc như mapping normative nữa. Migration là
manual: thêm registry, thêm refs cho từng expected signal, rồi đổi version thành
v0.2. `src.engine.semantics.catalog.validate_catalog()` reject version cũ,
missing refs, refs không tồn tại và confidence/type không hợp lệ. Structural
Structural Graph Contract là v1.2.0; graphs v1.0.0 và v1.1.0 vẫn được hỗ trợ.

### ObservedActivity provenance

Mỗi `ObservedActivity` phải mang `TelemetryRecordRef` immutable gồm:

```text
dataset_id + snapshot_id + snapshot:<snapshot-hash>/<relative-file>
  + record_locator(csv_row hoặc content_hash)
```

`TelemetryRecordRef.from_manifest()` và
`validate_telemetry_record_ref()` dùng manifest v1 hiện hành, verified file bytes
và CSV parsing để xác nhận dataset, snapshot, file membership và record locator.
`csv_row` là row 1-based trong immutable CSV snapshot; `content_hash` là SHA-256
of the canonical parsed row and must identify exactly one row. Đây là
repository-defined locator, không phải Windows-native EventRecordID. Nonexistent
rows, unmatched hashes và ambiguous duplicate hashes đều bị reject.
Không có `unknown`, `generated` hay placeholder provenance. Nếu reference không
resolve được tới manifest thì activity là invalid.

### Correlation và confirmation

`correlate_activity()` chỉ làm compatibility gate cho environment, identity
namespace và time window. `correlate_candidate()` tạo `CorrelationRecord` có
status `candidate` hoặc `rejected`; nó không tạo structural edge và không tạo
`ConfirmedAttack`. `confirm_candidate()` chỉ tạo kết luận confirmed khi caller
cung cấp `ConfirmationBasis` tường minh (analyst review hoặc independent
evidence). Vì vậy các lớp sau vẫn độc lập:

```text
Structural Provenance
!= Semantic Mapping Evidence
!= Observed Activity Provenance
!= Correlation Result
!= Confirmed Attack
```

Ordered derived-edge lineage của #92, collection-time canonical serialization
của #97 và structural Graph Contract redesign đều nằm ngoài #81.

## 1. Mục tiêu

Tài liệu này định nghĩa lớp trung gian giữa topology Active Directory và hành vi tấn công có thể xảy ra trong thực tế.

Điểm cốt lõi là không ánh xạ trực tiếp một permission edge thành một attack step duy nhất.
Relationship chi la capability structure va co the co nhieu candidate technique; khong candidate nao mac dinh da duoc chon, kha dung, thuc hien hay quan sat.

```text
Structural relationship
        |
        v
Attack technique / semantic transition
        |
        +--> Preconditions
        +--> State transition / effect
        +--> Expected telemetry
        +--> Failure conditions
```

Ba khái niệm bắt buộc phải được tách biệt:

1. **AD relationship**: sự thật cấu trúc hoặc quyền hạn thu được từ snapshot, ví dụ `A --GenericAll--> B`.
2. **Attack technique**: cách một principal đang bị kiểm soát có thể tận dụng relationship đó để tạo ra trạng thái bảo mật mới.
3. **Observed activity**: bằng chứng runtime như Windows Security Events, PowerShell logs hoặc telemetry khác cho thấy một hành vi thực tế có thể đã xảy ra.

Relationship mô tả `what can happen`; attack semantics mô tả `how that capability can change security state`; telemetry mô tả `what evidence may be observable if a technique is exercised`.

## 2. Không thay đổi canonical edge contract trong #58

Issue #58 là research issue.
Tài liệu này không thay đổi schema cạnh hiện tại:

```yaml
edge_required: [id, source, target, kind, provenance]
```

Canonical edge tiếp tục chỉ biểu diễn topology và provenance.
Các trường như ATT&CK technique, prerequisite, telemetry, effect hoặc attack cost không được nhét trực tiếp vào mỗi edge instance.

Lý do:

- một edge có thể hỗ trợ nhiều technique khác nhau;
- cùng một technique có thể có nhiều failure conditions theo môi trường;
- telemetry là dữ liệu runtime, không phải thuộc tính bất biến của topology;
- một technique có thể sinh derived capability/scenario overlay mới nhưng không mutate canonical snapshot/provenance;
- weight theo edge kind đơn thuần có thể quá thô khi cùng relationship có nhiều đường abuse với chi phí khác nhau.

Proposal của #58 là một **semantic catalog độc lập** nằm trên structural graph.

## 3. Mô hình bốn lớp

### 3.1. Layer 1: Structural graph

Nguồn: AD snapshot / BloodHound-style collection đã normalize theo contract.

Ví dụ:

```text
Alice --GenericAll--> Bob
Helpdesk --AdminTo--> SRV01
SRV01 --HasSession--> Carol
```

Layer này trả lời principal nào có relationship gì với asset/identity nào.

### 3.2. Layer 2: Attack Semantics catalog

Catalog ánh xạ relationship sang một hoặc nhiều semantic transitions.

Ví dụ `GenericAll -> User` có thể hỗ trợ các hướng như password reset, thay đổi thuộc tính phục vụ authentication abuse, hoặc thay đổi ACL.
Chúng có prerequisite, effect và telemetry khác nhau nên không được gộp thành một bước duy nhất.

### 3.3. Layer 3: Runtime attack state

Attack-path engine đánh giá technique trong một state cụ thể.

Ví dụ:

```text
State S0:
  control(Alice)
  GenericAll(Alice, Bob)

Transition T:
  abuse = reset_target_password

Preconditions:
  control(Alice)
  GenericAll(Alice, Bob)
  Bob.enabled == true

Effect S1:
  authentication_control(Bob)
```

State vocabulary tối thiểu được đề xuất:

- `control(principal)`
- `effective_member(principal, group)`
- `permission(principal, relationship, target)`
- `admin_control(computer)`
- `interactive_session(principal, computer)`
- `remote_command_execution(principal, computer)`
- `credential_material(user)`
- `authentication_control(user)`
- `relationship_added(source, kind, target)`

Đây là research vocabulary, chưa phải contract v0.1.0.

### 3.4. Layer 4: Observed activity

Observed activity gồm các event thực tế từ cùng environment và một time window có ý nghĩa.

Ví dụ:

```text
expected_telemetry(reset_target_password):
  - Security Event 4724

observed_activity:
  - environment_id
  - host/domain
  - timestamp
  - actor SID
  - target SID
  - event_id
```

`expected_telemetry` không đồng nghĩa với `observed_activity`.

Một event không tự tạo ra structural edge.
Ngược lại, một structural edge cũng không chứng minh abuse đã xảy ra.

## 4. Taxonomy cho 8 canonical M1 edges

| Relationship | Semantic class | Action cần thiết khi traverse | Representative semantic effect | Telemetry chỉ xuất hiện khi nào |
| --- | --- | --- | --- | --- |
| `MemberOf` | Entitlement propagation | Không | Principal thừa hưởng authorization của security group | Không có telemetry chỉ vì membership tồn tại; thay đổi membership là hành vi khác |
| `AdminTo` | Host admin capability | Có | Đạt execution/control với quyền quản trị trên host nếu runtime prerequisites thỏa mãn | Khi attacker thực sự xác thực/exercise admin channel |
| `GenericAll` | Object-control capability | Có | Có nhiều khả năng thay đổi target, tùy target kind và kỹ thuật chọn | Khi có object/account/ACL modification hoặc authentication activity |
| `WriteDacl` | Graph-mutation capability | Có | Tạo quyền mới bằng cách thay đổi DACL | Khi DACL thực sự bị sửa và auditing phù hợp được bật |
| `ForceChangePassword` | Identity takeover capability | Có | Đặt credential mới cho target account | Khi password reset thực sự được thực hiện |
| `CanRDP` | Remote interactive access capability | Có | Tạo remote interactive session; không mặc định là admin | Khi RDP session/logon thực sự xảy ra |
| `CanPSRemote` | Remote command/session capability | Có | Tạo PowerShell remoting session theo quyền của principal | Khi WinRM/PowerShell remoting thực sự được sử dụng |
| `HasSession` | Credential/session opportunity | Có và có điều kiện | Từ quyền kiểm soát host có thể thu được credential/token của logged-on user | Khi credential access được thực hiện; bản thân session observation không đồng nghĩa credential theft |

Bốn semantic classes trên giúp tránh coi mọi traversable edge là cùng một loại hành động.

## 5. `MemberOf`: edge còn thiếu trong research Attack Semantics

### 5.1. Structural meaning

M1 chấp nhận principal `User`, `Group` hoặc `Computer` làm source và `Group` làm target:

```text
Principal --MemberOf--> Group
```

Hướng graph biểu diễn authorization flow.
Windows access tokens có thể chứa SID của direct và nested security groups, và Microsoft mô tả `tokenGroups` là tập SID của các nhóm direct và indirect mà account thuộc về.
Vì vậy nested group membership tạo transitive authorization path.

Ví dụ:

```text
Alice --MemberOf--> Helpdesk
Helpdesk --MemberOf--> ServerAdmins
ServerAdmins --AdminTo--> SRV01
```

Nếu `Alice` đã bị kiểm soát, `MemberOf` không yêu cầu attacker chạy thêm một exploitation primitive để "chiếm" group.
Nó biểu diễn entitlement đã có.

### 5.2. Semantic transition

Đề xuất canonical transition:

```text
transition_id: propagate_group_entitlement
relationship: MemberOf
action_required: false

preconditions:
  - control(source_principal)
  - source_principal is effective security principal
  - relationship MemberOf(source_principal, target_group) exists

effect:
  - effective_member(source_principal, target_group)
```

Nested group:

```text
effective_member(Alice, Helpdesk)
+ MemberOf(Helpdesk, ServerAdmins)
-> effective_member(Alice, ServerAdmins)
```

### 5.3. Vì sao không map `MemberOf` trực tiếp sang MITRE ATT&CK technique

Một membership đang tồn tại không phải một adversary action.
MITRE ATT&CK `T1069.002 - Permission Groups Discovery: Domain Groups` mô tả hành vi **enumerate** domain groups, không phải việc hưởng quyền từ group đã tồn tại.

Do đó:

- `MemberOf` không cần ATT&CK technique để traverse authorization state;
- nếu attacker enumerate group membership, đó là một observed/discovery technique riêng (`T1069.002`);
- nếu attacker **thay đổi** membership, hành động đó phải được sinh từ một capability khác như quyền control group, không được gán ngược cho structural `MemberOf` edge.

### 5.4. Telemetry policy cho `MemberOf`

Không có event runtime chỉ vì `Alice` đã là thành viên của `Helpdesk` trong snapshot.

Nếu membership bị thay đổi, Windows có thể ghi các account-management events tùy group scope, ví dụ:

- `4728`: member added to security-enabled global group;
- `4732`: member added to security-enabled local group;
- `4756`: member added to security-enabled universal group.

Các event trên mô tả **group membership modification**, không phải traversal của edge tồn tại.

### 5.5. Failure / edge cases

Attack engine cần lưu ý:

- disabled principal không nên tự động trở thành useful starting state;
- nested groups có thể tạo cycle, nên entitlement closure phải chống vòng lặp;
- distribution group không phải security authorization group dù có thể xuất hiện trong một số directory relationships;
- token freshness và phiên đăng nhập hiện tại có thể ảnh hưởng lúc quyền mới có hiệu lực sau một thay đổi membership;
- scope/type của group ảnh hưởng authorization across domain/forest boundaries;
- older research wording trong `taxonomy.md` chỉ ghi `User/Group -> Group`, trong khi current M1 fixtures chấp nhận `Computer -> Group`; tài liệu M2 phải theo implementation hiện tại.

## 6. Object-control semantics

### 6.1. `GenericAll`

`GenericAll` là broad object-control capability, không phải một technique duy nhất.

Attack Semantics cần dispatch theo target kind và available operation.
Ví dụ với `User`, các semantic transitions có thể bao gồm:

- đặt/reset authentication secret nếu right thực tế cho phép;
- thay đổi thuộc tính account có tác động tới authentication;
- thay đổi DACL để tạo quyền mới;
- thay đổi SPN hoặc thuộc tính khác nếu use case nghiên cứu yêu cầu.

Với `Group`, effect có thể là thay đổi membership.
Với `Computer`, effect có thể khác và cần target-specific semantics.

Do đó không nên định nghĩa:

```text
GenericAll -> control(target)
```

một cách vô điều kiện.

Thay vào đó:

```text
GenericAll(source, target)
  -> choose technique compatible with target.kind
  -> validate prerequisites
  -> produce explicit state transition
```

### 6.2. `WriteDacl`

Các ví dụ `relationship_added` / graph mutation trong phần này chỉ cập nhật scenario capability state, không sửa structural topology snapshot bất biến theo ADR-0008.


`WriteDacl` là ví dụ rõ nhất về **graph mutation**.

Structural edge:

```text
Alice --WriteDacl--> Target
```

không nhất thiết trực tiếp cho Alice quyền sử dụng mọi capability của Target.
Technique thực tế có thể sửa DACL để tạo ra một relationship mới:

```text
WriteDacl(Alice, Target)
  -> modify DACL
  -> relationship_added(Alice, GenericAll, Target)
```

Hoặc một right hẹp hơn tùy target và mục tiêu.

Attack-path engine tương lai vì vậy cần hỗ trợ transition làm thay đổi capability graph thay vì chỉ traverse static graph.

Expected telemetry cho directory modification có thể bao gồm Security Event `5136` khi Audit Directory Service Changes và SACL phù hợp được cấu hình.
Không được giả định `5136` luôn tồn tại.

### 6.3. `ForceChangePassword`

Semantic transition đại diện:

```text
preconditions:
  - control(source)
  - ForceChangePassword(source, target_user)
  - password reset operation is allowed by the directory/password policy

effect:
  - authentication_control(target_user)

# target_user disabled/expired không tự block administrative reset;
# account/authentication restrictions được đánh giá khi activation/authentication ở bước sau.
```

Expected telemetry đại diện: Security Event `4724` khi một account attempt reset password của account khác.

Failure/impact considerations:

- password policy có thể làm reset thất bại;
- account state có thể làm credential mới không hữu ích;
- reset có thể gây side effect vận hành và tạo dấu hiệu rõ ràng;
- việc reset credential không nên đồng nhất với việc có toàn bộ historical session/token của target.

## 7. Host-access semantics

### 7.1. `AdminTo`

`AdminTo` biểu diễn administrative capability trên target computer.
Nó mạnh hơn quyền remote logon đơn thuần nhưng vẫn cần runtime channel phù hợp.

Semantic transition abstract:

```text
preconditions:
  - control(source_principal)
  - AdminTo(source_principal, target_computer)
  - at least one supported management/execution path reachable
  - target accepts the authentication context

effect:
  - admin_control(target_computer)
```

Network reachability, host firewall, service availability, Remote UAC, local-vs-domain account behavior và endpoint controls là environment predicates, không phải structural edge fields.

Không gắn một ATT&CK sub-technique duy nhất với `AdminTo`, vì actual technique phụ thuộc execution channel được dùng.

### 7.2. `CanRDP`

Accepted #80 yêu cầu effective RDU membership AND `SeRemoteInteractiveLogonRight` AND NOT effective `SeDenyRemoteInteractiveLogonRight` cho canonical CanRDP.
Membership-only, right-only hoặc thiếu required evidence không đủ tạo positive edge.
AdminTo có thể hỗ trợ RDP như một management channel nhưng không tự sinh CanRDP.
CanRDP không bảo đảm privileged execution.

Semantic transition:

```text
preconditions:
  - control(source_principal)
  - CanRDP(source_principal, target_computer)
  - RDP reachable and enabled
  - authentication accepted

effect:
  - interactive_session(source_principal, target_computer)
```

Nếu source principal chỉ có quyền thấp, engine không được tự động sinh `admin_control(target_computer)`.

ATT&CK reference phù hợp cho actual use là `T1021.001 - Remote Services: Remote Desktop Protocol`.

Expected telemetry đại diện: successful logon event `4624` với Logon Type `10` cho RemoteInteractive sessions, cùng các Terminal Services logs tùy cấu hình.

### 7.3. `CanPSRemote`

`CanPSRemote` biểu diễn khả năng mở PowerShell remoting session tới target khi WinRM/runtime prerequisites thỏa mãn.
SpecterOps cũng lưu ý edge này không tự bảo đảm privileged execution.

Semantic transition:

```text
preconditions:
  - control(source_principal)
  - CanPSRemote(source_principal, target_computer)
  - WinRM reachable and configured
  - authentication accepted

effect:
  - remote_command_execution(source_principal, target_computer)
```

ATT&CK reference phù hợp cho actual use là `T1021.006 - Remote Services: Windows Remote Management`.

Expected telemetry phụ thuộc audit configuration và có thể gồm logon, WinRM operational logs và PowerShell logging.
Không được hard-code một Event ID duy nhất như bằng chứng bắt buộc.

## 8. `HasSession`: opportunity chứ không phải compromise guarantee

Structural edge hiện tại:

```text
Computer --HasSession--> User
```

mô tả rằng một user session được collector quan sát trên computer.

Để biến opportunity này thành identity control, attack state cần thêm điều kiện:

```text
preconditions:
  - admin_control(source_computer)
  - HasSession(source_computer, target_user)
  - session still present
  - useful credential/token material is accessible

effect_stage_1:
  - credential_material(target_user)

conditional_effect_stage_2:
  - authentication_control(target_user)
```

Không phải mọi session đều cung cấp credential material có thể tái sử dụng.
Credential Guard, protected authentication configuration, session freshness, user logoff và endpoint security có thể làm transition thất bại.

MITRE `T1003 - OS Credential Dumping` có thể là một technique family khi attacker thực sự truy cập credential material, nhưng `HasSession` edge tự nó không đồng nghĩa `T1003` đã xảy ra.

Đây là edge cần uncertainty/temporal semantics mạnh nhất trong 8 cạnh M1.

## 9. Proposed Attack Semantics schema v0

Đề xuất dưới đây là research artifact, chưa phải contract change:

```yaml
version: "0.1"
relationship: GenericAll
semantic_class: object_control
source_kinds: [User, Group, Computer]
target_kinds: [User]

techniques:
  - id: reset_target_password
    action_required: true
    prerequisites:
      - control(source)
      - relationship(GenericAll, source, target)
      - target.enabled
    effects:
      - authentication_control(target)
    expected_telemetry:
      - provider: Microsoft-Windows-Security-Auditing
        event_id: 4724
        requirement: audit_policy_dependent
    failure_conditions:
      - password_policy_rejects_change
      - target_not_authentication_usable
    confidence: high
```

Recommended fields cho mỗi technique:

| Field | Mục đích |
| --- | --- |
| `id` | stable semantic technique identifier nội bộ |
| `relationship` | canonical M1 edge kind cần thiết |
| `semantic_class` | entitlement, object-control, host-access, credential-opportunity |
| `source_kinds`, `target_kinds` | guard theo loại node |
| `action_required` | phân biệt propagation với active abuse |
| `prerequisites` | state predicates bắt buộc |
| `effects` | explicit state transition |
| `failure_conditions` | điều kiện làm relationship không usable trong runtime |
| `expected_telemetry` | evidence có thể xuất hiện nếu technique thực sự được exercise |
| `attack_refs` | MITRE/SpecterOps/Microsoft references, không bắt buộc 1:1 |
| `confidence` | mức chắc chắn của mapping |
| `cost_factors` | input cho weighting model tương lai, chưa phải final weight |
| `remediation` | metadata phục vụ giải thích và defensive prioritization |

## 10. Implication đối với weighted graph

`maut_v1` là historical experimental profile (`production_ready: false`), không phải production weighting; `unit` là baseline M2 correctness.
ADR-0008 chỉ coi `cost_factors` là descriptive research input.
Ownership cuối cùng của cost giữa structural relationship, semantic transition hoặc composition vẫn unresolved và thuộc successor decision #42.
Các giả thuyết về technique, environment, detectability hoặc uncertainty không chọn trước đơn vị cost và không hiệu chuẩn bằng independent telemetry.
#83 đã đóng sau PR #96; #42 chỉ triển khai sau khi #79 hoàn tất và successor decision về cost ownership được chấp thuận.
PR #51 không phải authority để áp dụng lại historical design.

## 11. Telemetry policy cho weighted graph

### 11.1. Same environment

Nếu AD snapshot và Windows Security Logs thuộc cùng environment, có identity keys đáng tin cậy và time ranges tương thích, telemetry có thể được dùng để:

- xác thực một activity đã xảy ra;
- tăng confidence cho technique hypothesis;
- phân tích runtime path;
- hỗ trợ reverse reasoning từ event về capability path có thể liên quan.

Correlation phải lưu uncertainty và time context.

### 11.2. Independent datasets

Nếu AD snapshot và security logs đến từ hai dataset độc lập:

- không join entity-level bằng username/SID giả định;
- không dùng event để claim một edge của snapshot đã bị exploit;
- chỉ dùng logs để xây expected telemetry taxonomy hoặc đánh giá generic detection coverage;
- mọi conclusion phải ghi rõ không có same-environment causal evidence.

### 11.3. Telemetry không phải structural truth

Các rule bắt buộc:

```text
ExpectedTelemetry != ObservedActivity
ObservedActivity != StructuralRelationship
StructuralRelationship != ConfirmedAttack
```

## 12. Relationship-to-technique mapping v0

| Relationship | Representative semantic technique | Effect | ATT&CK relationship |
| --- | --- | --- | --- |
| `MemberOf` | `propagate_group_entitlement` | effective authorization inherited | Không map trực tiếp; group enumeration nếu xảy ra là `T1069.002` |
| `AdminTo` | `obtain_admin_execution_on_host` | admin control of computer | Actual technique phụ thuộc remote/service channel |
| `GenericAll` | target-specific object manipulation | account/object control hoặc capability mới | Context dependent, không 1:1 |
| `WriteDacl` | `grant_new_object_right` | mutate graph bằng quyền mới | Context dependent; directory modification telemetry quan trọng |
| `ForceChangePassword` | `reset_target_password` | authentication control of user | Account manipulation family, mapping phụ thuộc use case |
| `CanRDP` | `open_remote_interactive_session` | interactive session | `T1021.001` khi được sử dụng |
| `CanPSRemote` | `open_winrm_remote_session` | remote command/session capability | `T1021.006` khi được sử dụng |
| `HasSession` | `recover_session_credential_material` | credential material, rồi conditional identity control | `T1003` family nếu credential dumping thực sự xảy ra |

Bảng này là taxonomy research.
Nó không nói rằng tồn tại relationship đồng nghĩa ATT&CK technique đã được thực hiện.

## 13. Testable semantic invariants cho implementation tương lai

Một implementation issue tiếp theo nên có regression tests tối thiểu:

1.
  Passive `MemberOf` propagation không có dedicated group-modification telemetry hoặc ATT&CK action; authentication/resource access sau đó vẫn có thể tạo operational events.
2.
  Nested `MemberOf` hỗ trợ transitive entitlement và terminate đúng khi có group cycle.
3. `CanRDP` tạo `interactive_session`, không tự tạo `admin_control` nếu principal không có admin capability.
4. `CanPSRemote` fail khi WinRM/runtime predicate false.
5.
  Technique `recover_session_credential_material` cần control source computer; structural HasSession observation không đòi hỏi attacker đã có quyền này.
6.
  Credential-extraction transition kiểm freshness/availability và không auto-convert structural session observation thành target identity control.
7. `WriteDacl` có thể sinh capability/relationship mới trong derived attack state.
8. `GenericAll` dispatch theo target kind và không collapse thành một unconditional technique.
9.
  Independent telemetry dataset không được entity-join với snapshot khi thiếu common environment identity.
10.
  Missing expected telemetry không được dùng như bằng chứng rằng technique chắc chắn không xảy ra, vì audit policy có thể không thu thập event.

## 14. Out of scope của #58

Các relationship sau đáng nghiên cứu tiếp nhưng không thuộc canonical M1 contract hiện tại:

- `GenericWrite`;
- delegation relationships;
- AD CS relationships;
- domain/forest trust relationships;
- GPO-derived control primitives ngoài 8 M1 edges.

Không mở rộng canonical edge list trong #58.

## 15. Acceptance criteria mapping

### Phân biệt AD relationship, attack technique, observed activity

Đạt thông qua mô hình bốn lớp và telemetry policy.

### Mapping làm nền tảng cho weighted attack-path model

Đạt thông qua taxonomy 8 edges, explicit preconditions/effects và proposed semantic schema v0.

### Nêu rõ giới hạn khi AD snapshot và security logs không cùng environment

Đạt thông qua Section 11.2: không entity-level join và không suy luận causal exploit từ dataset độc lập.

### Deliverable

Tài liệu này là `docs/research/attack-semantics.md` theo Issue #58.

## 16. Quyết định research

Kết luận của #58:

1.
  Giữ structural edge contract M1 như hiện tại.
2.
  Không coi canonical relationship là attack step cuối cùng.
3.
  Bổ sung một Attack Semantics catalog độc lập để ánh xạ relationship sang semantic transitions.
4. `MemberOf` được xử lý như entitlement propagation, không phải active exploit.
5. `WriteDacl` cần scenario capability-state updates; structural snapshot không bị mutate theo ADR-0008.
6. `HasSession` cần temporal uncertainty và prerequisite mạnh hơn static edges.
7.
  Telemetry là expected/observed evidence layer riêng, không được trộn với topology.
8.
  Tại thời điểm #58, weighting theo semantic transition là giả thuyết nghiên cứu.
  Cost ownership giữa structural relationship, semantic transition và composition chưa được quyết định; successor của #42 phải quyết định trước production profile, còn `unit` là baseline tính đúng.

## 17. Nguồn tham khảo

### Internal project baseline

- [`taxonomy.md`](taxonomy.md)
- [`weight-model.md`](weight-model.md)
- [`ADR-0002-edge-directionality-semantics.md`](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0002-edge-directionality-semantics.md)
- [`contract.yml`](../../configs/contract.yml)
- Issue #58: `https://github.com/nairyuuu/ad-weighted-graph/issues/58`

### Microsoft

- Active Directory Security Groups: `https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-groups`
- User Security Attributes / `tokenGroups`: `https://learn.microsoft.com/en-us/windows/win32/ad/security-properties`
- MS-AUTHSOD Nested Groups: `https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-authsod/d3ca79c3-0386-42f8-979b-4376977dcd5e`
- Windows Security Event 4724: `https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4724`
- Audit Directory Service Changes / Event 5136: `https://learn.microsoft.com/windows/security/threat-protection/auditing/audit-directory-service-changes`
- Advanced Audit Policy group membership events: `https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/security-best-practices/advanced-audit-policy-configuration`
- Windows Security Event 4624 logon types: `https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4624`

### SpecterOps / BloodHound

- CanRDP: `https://bloodhound.specterops.io/resources/edges/can-rdp`
- CanPSRemote: `https://bloodhound.specterops.io/resources/edges/can-ps-remote`
- MemberOfLocalGroup: `https://bloodhound.specterops.io/resources/edges/member-of-local-group`

### MITRE ATT&CK

- Permission Groups Discovery: Domain Groups, T1069.002: `https://attack.mitre.org/techniques/T1069/002/`
- Remote Services: `https://attack.mitre.org/techniques/T1021/`
- OS Credential Dumping: `https://attack.mitre.org/techniques/T1003/`
