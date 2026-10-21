# Claim-to-Field Traceability and Semantic Remediation

Generated inventories under `reports/generated/` are local outputs, absent from a clean checkout.
Use the reproduction commands below to create them; they are not tracked repository links.

## 1. Phạm vi

Đây là Phase 3 của issue #94.
Tài liệu trace các claim semantic đang có trong repository xuống raw source, field, qualifier, giả định completeness, provenance và confidence.
Phase này không sửa parser, graph builder, `configs/attack_semantics.yml`, metric production hoặc lineage serialization.

Invariant được áp dụng xuyên suốt:

Issue #81 implements the missing machine-readable provenance for this trace:
catalog expectations now carry authoritative evidence references, while actual
telemetry observations require manifest-backed dataset/file/record references.
The measured corpus availability discussed below remains observed corpus evidence
and is intentionally not placed in the semantic evidence registry. Correlation is
still only a candidate result and does not establish a structural edge or a
confirmed attack.

```text
Structural Relationship != Attack Technique / transition != Observed Activity
```

Raw audit Phase 1 và Phase 2 được giữ nguyên.
Các kết luận dưới đây dùng chúng làm evidence foundation; không dùng current code hoặc tên field làm source-of-truth.

## 2. Evidence sources

| Dataset | Snapshot | Raw source | Audit/inventory | Phạm vi đã đo |
| --- | --- | --- | --- | --- |
| SEAMLESS | `seamless-v1`, `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` | sáu envelope JSON, gồm `20210920185958_computers.json`, `..._groups.json`, `..._users.json` | [SEAMLESS raw audit](seamless-raw-field-audit.md), `reports/generated/seamless-raw-field-inventory.json` | 3.369 raw records, 3.368 unique identifiers, 71.786 reference-shaped observations; 2 unresolved `Group.Members[].MemberId`; không có collection status/error fields |
| Windows telemetry | `telemetry-raw-v1`, `sha256:4203d3f13e42aa7a84f32762b78bfe87267f66318267a7cf80b9f23c620cc9c1` | `evtx_data.csv` | [Windows telemetry raw audit](windows-telemetry-raw-field-audit.md), `reports/generated/windows-telemetry-raw-field-inventory.json` | 4.633 rows, 326 columns; provider/channel/event qualifier audit; `EVTX_Tactic` là upstream annotation |

Machine-readable source của bảng claim là `reports/generated/claim-traceability.json`, được tạo bởi [`scripts/claim_traceability.py`](../../scripts/claim_traceability.py).
JSON chỉ chứa field names, safe counts/metadata và diễn giải; không chứa raw payload values.

## 3. Claim taxonomy

* `structural`: topology hoặc primitive permission/membership được collector xuất.
* `runtime`: capability/predicate cần account state, effective rights, service,
reachability, authentication hoặc temporal state.
* `telemetry`: event/provider observation từ Windows logs.
* `evaluation`: count, label, coverage hoặc correlation claim.

Status không bị thay thế bởi confidence:

| Status | Cách dùng |
| --- | --- |
| `SUPPORTED` | Exact raw fields và qualifiers đủ cho claim ở đúng semantic layer. |
| `PARTIALLY_SUPPORTED` | Có primitive nhưng thiếu qualifier, identity, provenance hoặc completeness. |
| `TOO_STRONG` | Có evidence nhưng wording/kết luận vượt quá evidence. |
| `UNSUPPORTED` | Không có raw evidence cần thiết hoặc mapping sai semantic layer. |
| `UNRESOLVED` | Có evidence nhưng collector/schema/identity/completeness chưa đủ xác minh. |

Confidence trong inventory dùng `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`.
Ví dụ `UNSUPPORTED + HIGH` nghĩa là audit chắc chắn claim không được raw support; không phải claim được chấp nhận với độ tin cậy cao.

## 4. Structural relationship != runtime predicate != observed activity

Một raw field có thể support một primitive nhưng không support mọi tầng sau đó:

```text
raw field / collector primitive
  -> structural evidence
  -> approved capability rule + runtime predicates
  -> observed activity (nếu event thực sự xảy ra)
  -> evaluation claim (chỉ với denominator/ground truth hợp lệ)
```

Ví dụ `Group.Members[].MemberId` là direct membership evidence.
Nó không cần `4732` để tồn tại; `4732` chỉ là member-added activity.
Tương tự, `Aces[].RightName` với `WriteDacl` là ACE-derived capability evidence, còn `5136` với `AttributeLDAPDisplayName=nTSecurityDescriptor` là ACL-change-shaped activity.

`StatusAccessDenied`, missing required primitive, method-not-run, incomplete collection, unresolved identity và schema absence đều là `unknown/incomplete`; không được tự normalize thành `false`.
Với snapshot SEAMLESS hiện tại, collection status fields không xuất hiện nên các empty array findings chỉ là measured empty/unobserved, không phải negative fact.

## 5. Canonical relationship cards

### MemberOf

#### Current repo claim

`Group.Members[]` được EDA đọc thành cạnh `MemberOf`; ADR-0009 yêu cầu canonical graph lưu direct edge, còn transitive membership được resolve khi query/inference.

#### Structural raw primitive

`20210920185958_groups.json`: `Group.ObjectIdentifier`, `Members[].MemberId`, `Members[].MemberType`.
Raw storage/container direction là containing Group -> member reference; canonical graph direction sau resolution là member principal -> containing Group (`Principal --MemberOf--> Group`).
Phase 1 quan sát 13.324 elements, 545/550 Group records có element; 2 reference chưa exact-match được.

#### Phase 1 finding

Đây là direct membership reference từ Group container tới principal child.
`MemberType` là collector object-kind label; `Group` member có thể biểu diễn nesting.
Direct edge, transitive closure và primary-group reference không được collapse.

#### Runtime predicates

Effective membership cần token/group-scope/security-enabled và domain/boundary policy.
Nó là derived traversal, không phải raw direct edge mới.
Unresolved reference hoặc collection failure là `unknown`, không phải false.

#### Telemetry evidence available

Windows `4732` có 2 rows với `SubjectUser*`, `Target*`, `MemberSid`, `MemberName`; đây là observed member-added event.
Các `4728`, `4729`, `4733`, `4756` không xuất hiện trong corpus hiện tại.

#### What telemetry can corroborate

Một membership modification event cụ thể với actor, target group, member, host và time.
Nó có thể corroborate activity của transition thay đổi membership.

#### What telemetry cannot validate

`4732` không phải prerequisite cho direct membership đang tồn tại, không chứng minh full closure, effective authorization hoặc attack success.

#### Current status

Direct raw evidence: `SUPPORTED`; mọi claim “all canonical direct edges resolved”: `PARTIALLY_SUPPORTED` do 2 unresolved references, duplicate Group identifier và thiếu collection status.

#### Remediation

Giữ direct evidence và provenance; route identity/reconciliation cho #44/#45.

### AdminTo

#### Current repo claim

EDA reports `Computer.LocalAdmins[]` as host-scoped raw membership/evidence and keeps
empty or unobserved hosts unknown (`scripts/eda_dataset_analysis.py` host-access helpers).

#### Structural raw primitive

`computers.json`: `Computer.ObjectIdentifier`, `LocalAdmins[].MemberId`, `LocalAdmins[].MemberType`.
Có 5 elements trên 1/100 Computer records.

#### Phase 1 finding

Đây là host-scoped local Administrators membership evidence.
Nó không mở rộng thành arbitrary SYSTEM execution.

#### Runtime predicates

Admin channel, host reachability, authentication acceptance, UAC/endpoint policy và successful administrative action là các lớp runtime riêng.

#### Telemetry evidence available

`4624` và `4672` tồn tại, nhưng lần lượt là logon và special-privilege assignment; không có discriminator đủ để biến chúng thành `AdminTo` validation.

#### What telemetry can corroborate

Một administrative logon/action-shaped observation nếu có provider, subject/target, host, channel và time context phù hợp.

#### What telemetry cannot validate

Không thể từ `4672` suy ra local admin membership, SYSTEM execution hoặc successful remote admin action.

#### Current status

`LocalAdmins[]` positive membership là `SUPPORTED` canonical `AdminTo` structural evidence theo ADR-0003/#80 sau identity/host resolution.
Empty or unobserved coverage remains `unknown` if completeness evidence is unavailable, and `AdminTo` does not imply runtime execution.

#### Remediation

EDA downgrade is complete; production identity resolution and graph-builder handling remain
owned by #44/#45.

### GenericAll

#### Current repo claim

`Aces[].RightName == "GenericAll"` được EDA đếm thành GenericAll và semantic catalog dispatch theo target kind.

#### Structural raw primitive

`ObjectIdentifier`, `Aces[].PrincipalSID`, `Aces[].PrincipalType`, `Aces[].RightName`, `Aces[].IsInherited`.
`RightName` là collector-normalized label, không phải raw Windows access mask.

#### Phase 1 finding

`GenericAll` là candidate permission evidence trên object hiện tại.
Principal resolution hiện exact-match tốt trong inventory, nhưng effective allow/deny order, security descriptor đầy đủ và exploitability không nằm trong claim này.

#### Runtime predicates

Target kind, selected operation, effective ACL, actor control, account state và directory write policy phải được kiểm tra bởi transition cụ thể.
Một GenericAll edge không phải một attack technique duy nhất.

#### Telemetry evidence available

`5136` và `4662` xuất hiện; raw audit chỉ support ACL-change-shaped hoặc object-access observation với qualifiers phù hợp.

#### What telemetry can corroborate

Một transition cụ thể như directory attribute/ACL modification nếu giữ `AttributeLDAPDisplayName`, `ObjectDN`, `OperationType`, `AttributeValue`, actor và time.

#### What telemetry cannot validate

Không thể map Event ID trực tiếp thành effective GenericAll edge, arbitrary control, hoặc successful abuse.

#### Current status

Collector-normalized structural permission evidence: `SUPPORTED`; “unconditional effective control” hoặc “telemetry confirms GenericAll”: `TOO_STRONG`/`UNSUPPORTED`.

#### Remediation

Giữ relation ở structural layer; parser/builder primitive policy thuộc #44/#45 và semantic/activity revalidation thuộc #79/#80.

### WriteDacl

#### Current repo claim

`Aces[].RightName == "WriteDacl"` được đếm thành WriteDacl và semantic catalog mô hình hóa graph mutation.

#### Structural raw primitive

`ObjectIdentifier`, `Aces[].PrincipalSID`, `Aces[].PrincipalType`, `Aces[].RightName`, `Aces[].IsInherited`.

#### Phase 1 finding

Đây là ACE-derived permission-shaped evidence.
Nó không phải observed ACL modification.

#### Runtime predicates

Mutation cần selected transition, effective DACL, directory write, target/object context và operation outcome.
Nếu sinh capability mới thì đó là derived state riêng.

#### Telemetry evidence available

`5136` có 42 rows; chỉ tổ hợp `AttributeLDAPDisplayName=nTSecurityDescriptor` cùng `ObjectDN`, `OperationType`, `AttributeValue`, `SubjectUser*` là ACL-change-shaped.
`4662` có 33 object-access rows; `4670` không được quan sát.

#### What telemetry can corroborate

Một ACL change/object operation cụ thể nếu audit/SACL và value/operation correlation đủ.

#### What telemetry cannot validate

Không validate canonical WriteDacl edge, effective DACL hay attacker capability từ `5136`/`4662` đứng riêng.

#### Current status

Structural permission evidence: `SUPPORTED`; “WriteDacl đã được thực thi”: `TOO_STRONG`.

#### Remediation

Tách ACE evidence khỏi activity evidence; route semantic/evaluation mapping #79/#80, parser/builder #44/#45.

### ForceChangePassword

#### Current repo claim

Một số historical inventory/report mô tả `RightName == "ForceChangePassword"` và EDA có nhánh đếm field này.

#### Structural raw primitive

Current verified SEAMLESS inventory chỉ quan sát các `Aces[].RightName` categorical như `ExtendedRight`, `GenericAll`, `WriteDacl`...; không có explicit `ForceChangePassword` value.
`ExtendedRight` không đủ nếu thiếu object-specific GUID và security-descriptor/schema evidence.

#### Phase 1 finding

Có thể báo “0 explicit match trong snapshot đã audit” nhưng không báo “môi trường không có capability”.
Historical Dataset A/B counts không được gán sang SEAMLESS.

#### Runtime predicates

Structural extended right, target User, account enabled, password policy và directory write là các predicate/transition khác nhau.

#### Telemetry evidence available

Corpus có 1 `4724` row; đây là password-reset attempt/activity event.
Không có 4724 để làm structural prerequisite.

#### What telemetry can corroborate

Một reset attempt với provider, subject, target, host và time context.

#### What telemetry cannot validate

Không validate static ForceChangePassword ACE, reset success, password usability hoặc account takeover.

#### Current status

Claim explicit structural ForceChangePassword trong SEAMLESS: `UNSUPPORTED` với confidence `HIGH`; measured zero explicit label: `SUPPORTED` nhưng completeness không đo được.

#### Remediation

Remove current-SEAMLESS explicit-right wording; route extended-right decoding/parser handling #44/#45 và activity semantics #79/#80.

### CanRDP

#### Current repo claim

EDA reports `RemoteDesktopUsers[]` as `RemoteDesktopUsers_raw_memberships` and never
materializes it as verified `CanRDP`.

#### Structural raw primitive

`Computer.ObjectIdentifier`, `RemoteDesktopUsers[].MemberId`, `RemoteDesktopUsers[].MemberType`; 3 elements trên 1/100 Computer records.

#### Phase 1 finding

Đây chỉ là host-scoped Remote Desktop Users membership evidence.
Canonical project rule được giữ nguyên: effective RDU membership **và** `SeRemoteInteractiveLogonRight` **và** không có `SeDenyRemoteInteractiveLogonRight`.

#### Runtime predicates

RDP service state, network reachability, authentication acceptance và actual session là runtime predicates; không tạo structural edge chỉ vì chúng xảy ra.

#### Telemetry evidence available

`4624` có 69 rows, chỉ 2 rows có `LogonType=10`; `1149` có 11 rows với provider và user/domain/client tuple.

#### What telemetry can corroborate

RemoteInteractive-shaped logon (`ProviderName/Channel`, `EventID=4624`, `LogonType=10`, host/identity/time) hoặc RDP listener authentication-shaped event 1149.

#### What telemetry cannot validate

Không validate CanRDP structural edge, malicious RDP, persistence hoặc attack success.

#### Current status

Raw RDU membership is `SUPPORTED` as a primitive; verified effective `CanRDP` is
`unknown`/not materialized because UserRights allow/deny and completeness evidence are
absent from the current SEAMLESS snapshot.

#### Remediation

EDA count/label remediation is complete; effective production host-access inference remains
owned by #45.

### CanPSRemote

#### Current repo claim

EDA reports `PSRemoteUsers[]` as raw RMU membership and modeled BloodHound-compatible
`CanPSRemote` evidence; `4104`/`4624` remain descriptive telemetry signals only.

#### Structural raw primitive

`Computer.ObjectIdentifier`, `PSRemoteUsers[].MemberId`, `PSRemoteUsers[].MemberType`; 2 elements trên 1/100 Computer records.

#### Phase 1 finding

Đây là host-scoped Remote Management Users membership evidence.
Theo ADR-0003/#80, positive effective membership này là BloodHound-compatible structural evidence cho `CanPSRemote`.
Custom endpoint authorization, service/listener, reachability, authentication và PowerShell execution vẫn là các lớp riêng.

#### Runtime predicates

WinRM service/listener, network reachability và authentication acceptance là runtime predicates, không phải điều kiện tồn tại structural edge.
Custom endpoint ACL có thể giới hạn execution và phải có evidence riêng nếu claim independently verified endpoint access.

#### Telemetry evidence available

`4104` có 3 PowerShell Script Block rows; WinRM EventID 169 có authentication mechanism và username, 193 là lifecycle payload, 91 có error/payload context.

#### What telemetry can corroborate

PowerShell logging hoặc WinRM provider activity-shaped observations nếu giữ provider, channel, payload, identity, host và time.

#### What telemetry cannot validate

`4104` không validate WinRM hoặc CanPSRemote; không event nào ở corpus tự validate canonical structural edge hay successful remote command.

#### Current status

Positive effective `PSRemoteUsers[]` membership -> modeled `CanPSRemote`: `SUPPORTED` theo ADR-0003/#80.
Claim successful/custom-endpoint WinRM execution từ membership alone: `TOO_STRONG`; `4104 => CanPSRemote`: `UNSUPPORTED`.

#### Remediation

EDA mapping now separates membership evidence from WinRM/runtime activity; further parser
and telemetry work remains routed to #44/#45/#79.

### HasSession

#### Current repo claim

EDA reports populated `Computer.Sessions[]` as `Sessions_raw_observations`/observed
`HasSession` evidence; empty arrays remain unknown and telemetry rows do not imply
credential recovery.

#### Structural raw primitive

`Computer.ObjectIdentifier`, `Sessions[].UserId` hoặc `Sessions[].UserSID`.
Current SEAMLESS có `Sessions` array ở 100/100 Computer nhưng rỗng cả 100.

#### Phase 1 finding

Nếu populated, primitive chỉ biểu diễn collector-observed host-scoped session reference.
Empty không phân biệt no session, method not run, access denied hay incomplete collection.

#### Runtime predicates

Session freshness, source host admin control, credential accessibility và credential access outcome là predicates/transition state khác nhau.

#### Telemetry evidence available

`4624` có `TargetLogonId`, `LogonGuid`, `LogonType`; `4634` có một logoff row; RDP events và Sysmon rows có session/logon identifiers ở nơi provider ghi.

#### What telemetry can corroborate

Logon/connection/session-related observation sau khi có host/identity/time correlation, logon-logoff handling và source/target policy.

#### What telemetry cannot validate

Một row đơn lẻ không tạo static HasSession; HasSession không phải credential accessible, credential dumped hay credential material exists.

#### Current status

Primitive semantics: `PARTIALLY_SUPPORTED`; “empty Sessions means absence” and
“HasSession proves credentials” remain rejected interpretations.

#### Remediation

EDA remediation is complete; defer temporal/session correlation and ordered lineage to
#92, with semantic policy remaining separate from raw observation reporting.

## 6. Telemetry claim audit

### RDP

* `4624` alone là `UNSUPPORTED` cho RDP/CanRDP.
* `ProviderName/Channel + EventID=4624 + LogonType=10 + Computer + target/source
context + SystemTime` là `SUPPORTED` cho **RemoteInteractive-shaped observation**.
* `1149` với TerminalServices provider và `{Event_NS}Param1/2/3` là
`PARTIALLY_SUPPORTED` cho listener authentication-shaped observation.
* Không claim nào trong ba dòng trên validate structural `CanRDP`, maliciousness,
persistence hoặc lateral movement.

### PowerShell / WinRM

`4104` với PowerShell provider/channel, `ScriptBlockId`, `MessageNumber/Total` và `ScriptBlockText` chỉ support script-block logging observation.
WinRM phải dùng provider/event-specific fields: EventID 169 có `authenticationMechanism` và `username`, 193 có lifecycle payload, 91 có `ErrorCode`/`EventPayload`.
Vì vậy `4104 => WinRM`, `4104 => CanPSRemote` đều `UNSUPPORTED`.

### Credential access

Sysmon 10 có `SourceImage`, `TargetImage`, `GrantedAccess`, `CallTrace`, process context; chỉ support process-access-shaped evidence.
`TargetImage=lsass.exe` là qualifier cần cho LSASS-access-shaped wording, nhưng không chứng minh extraction.
`4672` là special-privilege assignment, `4648` là explicit-credential use context, `4624` là logon; không claim nào tự chứng minh credential theft.

### Group modification

`4732` với `SubjectUser*`, `Target*`, `MemberSid`, `MemberName`, host và time support observed member-added activity cho local security group.
Nó không phải evidence bắt buộc cho direct/passive `MemberOf`; `4728/4729/4733/4756` không xuất hiện trong corpus không được diễn giải thành negative fact về môi trường.

### ACL / directory change

`5136 + AttributeLDAPDisplayName=nTSecurityDescriptor + ObjectDN + OperationType + AttributeValue + SubjectUser*` support ACL-change-shaped directory evidence.
Các `5136` với `versionNumber` là loại khác.
`4662` với `ObjectName`, `ObjectType`, `AccessList`, `AccessMask`, `OperationType`, `Properties`, `SubjectUser*` là object-access evidence; `4670` không observed trong corpus.
Không mapping nào validate canonical `WriteDacl`/`GenericAll`.

### Session observations

`4624`, `4634`, RDP 1149/131/68/168/104 và Sysmon `LogonId`/`TerminalSessionId` chỉ support session/logon/connection-shaped observations.
Canonical/derived HasSession cần identity resolution, host resolution, time correlation, logon/logoff handling và source/target policy.
`UserID=S-1-5-20` trên provider row không tự là login identity.

## 7. Current EDA claim audit

| Current behavior | Raw evidence | Vì sao quá mạnh | Semantic level đúng | Owner |
| --- | --- | --- | --- | --- |
| `LocalAdmins[]` summed as `AdminTo` | `Computer.ObjectIdentifier`, `LocalAdmins[].MemberId/MemberType` | positive mapping là hợp lệ theo ADR-0003; chỉ phần empty/completeness và runtime execution không được suy quá mức | canonical `AdminTo` cho positive resolved membership; empty remains unknown nếu thiếu completeness | #44/#45 |
| `RemoteDesktopUsers[]` summed as `CanRDP` | `RemoteDesktopUsers[].MemberId/MemberType` | thiếu hai UserRights allow/deny qualifiers | RDU membership primitive; canonical rule cần RDU + allow - deny | #80 |
| `PSRemoteUsers[]` summed as `CanPSRemote` | `PSRemoteUsers[].MemberId/MemberType` | positive effective RMU membership là modeled structural evidence; không chứng minh custom endpoint/runtime execution | canonical modeled `CanPSRemote` cho positive effective membership; runtime/endpoint evidence riêng | #44/#45 |
| empty `Sessions[]` interpreted as no sessions | `Sessions` present but empty 100/100 | empty != false; method/error/completeness không có | unobserved/incomplete snapshot session evidence | #80/#92 |
| `Aces[].RightName` used as effective capability | `PrincipalSID`, `RightName`, `IsInherited` | normalized label không encode full DACL allow/deny/effective semantics | ACE-derived structural permission evidence | #44/#45/#80 |
| `EventID` counts read as relation/attack counts | `EventID`, `EVTX_Tactic`, provider fields | row count không phải edge count, attack count hoặc ground truth | corpus event distribution and upstream annotation inventory only | #47/#79 |

Không sửa `scripts/eda_dataset_analysis.py` trong Phase 3.
Những dòng trên là remediation findings, không phải implementation của remediation.

## 8. Attack semantics claim audit

`configs/attack_semantics.yml` hiện có nhiều điểm đúng ở transition layer: target kind, action-required, runtime prerequisites, `unknown`/`indeterminate`, và `expected_telemetry` không tạo observed activity.
Các điểm cần giữ:

* `MemberOf` là entitlement propagation, không phải event/technique modification.
* `AdminTo` là host-admin capability; không đồng nghĩa arbitrary SYSTEM execution.
* `GenericAll` dispatch theo target/operation, không phải một technique duy nhất.
* `WriteDacl` là graph-mutation transition; ACE không phải mutation đã quan sát.
* `ForceChangePassword` structural capability tách khỏi `4724` reset activity.
* `CanRDP` transition có thể yêu cầu `4624` `LogonType=10` như expected evidence,
nhưng expected không phải observed và không phải structural edge.
* Structural `CanPSRemote` có thể đến từ positive effective RMU membership theo ADR-0003/#80; WinRM-specific evidence cần cho runtime/activity claims, và `4104` chỉ là PowerShell logging.
* `HasSession` không phải credential material; credential access cần predicate/activity
riêng.

EDA/report trước Phase B1 từng liệt kê các mapping relation-level như `AdminTo -> 4672/4624`, `GenericAll -> 5136/4662`, `CanPSRemote -> 4104/4624`, `HasSession -> 4624/4634/10`.
Phase B1 đã bỏ matrix đó khỏi generator; corpus distribution hiện tại không gán EventID cho structural edge hoặc attack transition.
Không rewrite SSOT semantic config trong task này.

## 9. Evaluation claim audit

Một metric chỉ defensible khi có: ground truth được định nghĩa, raw field/qualifier trace được, denominator cùng semantic layer, identity/time scope và cách xử lý unknown.

Hiện tại:

* `reports/eda_summary.json` có corpus EventID distribution, upstream tactic annotation distribution và structural counts; đây không phải precision, recall, detected attack hoặc telemetry-confirmed edge.
* 4.633 rows và 8 upstream tactic annotation labels là local measurements.
  Claim external `6,432 events / 11 tactics` được report đánh dấu external-unverified, không phải local ground truth.
* `EVTX_Tactic` không được nâng thành Windows-native evidence.
* SEAMLESS và telemetry không có shared environment, identity namespace và time
context để entity-join; ADR-0007 yêu cầu đánh giá telemetry độc lập ở technique / relation-class level.
* Unknown do missing primitive, access denied, method not run, incomplete collection
hoặc unresolved identity không được tính là false negative.

Vì vậy các claim kiểu “X% CanRDP edges observed”, “EventID count = attack count” hoặc “telemetry validates structural edge” hiện `UNSUPPORTED` hoặc `UNRESOLVED`, route tới #47.

## 10. Claim-to-field traceability matrix

Bảng này là index ngắn của toàn bộ claim records; diễn giải đầy đủ và provenance requirements nằm trong `reports/generated/claim-traceability.json`.

| Claim | Lớp | Raw source | Raw fields | Required qualifiers | Observed availability | Completeness assumption | Status | Remediation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Direct Group membership | structural | SEAMLESS `..._groups.json` | `ObjectIdentifier`; `Members[].MemberId/MemberType` | exact identity; direct only | 13,324 refs; 2 unresolved | no closure; collection status absent | SUPPORTED | #44/#45 |
| Every direct MemberOf canonical/resolved | structural | SEAMLESS inventory | `Members[].MemberId/MemberType` | resolution, duplicate policy, scope | 71,784/71,786 refs resolved | exact matching only | PARTIALLY_SUPPORTED | #44/#45 |
| `LocalAdmins[] => AdminTo` | structural | `..._computers.json` | `ObjectIdentifier`; `LocalAdmins[].MemberId/MemberType` | identity + host scope | 5 refs / 1 host | positive supported; empty != false | SUPPORTED | #44/#45 |
| ACE `GenericAll` primitive | structural | all SEAMLESS ACE files | `PrincipalSID`, `PrincipalType`, `RightName`, `IsInherited` | identity; effective ACL policy | explicit label observed | normalized label; completeness absent | SUPPORTED | #44/#45 |
| GenericAll = unconditional object control | structural | SEAMLESS `Aces[]` | same ACE fields | target kind; operation; effective ACL | primitive exists | runtime/effective access absent | TOO_STRONG | #80 |
| ACE `WriteDacl` primitive | structural | all SEAMLESS ACE files | `PrincipalSID`, `RightName`, `IsInherited` | identity; approved ACE policy | explicit label observed | activity not implied | SUPPORTED | #44/#45 |
| WriteDacl = observed ACL mutation | structural | SEAMLESS ACE + telemetry | ACE fields; `5136` qualifier fields | operation/value correlation | `5136` 42 rows, 20 nTSecurityDescriptor | telemetry independent | TOO_STRONG | #79/#80 |
| Explicit SEAMLESS ForceChangePassword ACE | structural | SEAMLESS `Aces[]` | `RightName`, `PrincipalSID`, `ObjectIdentifier` | explicit right/GUID | no explicit value observed | ExtendedRight unresolved; completeness absent | UNSUPPORTED | #44/#45 |
| SEAMLESS explicit ForceChangePassword count is zero | structural | SEAMLESS inventory | `Aces[].RightName` | scope = analyzed snapshot | zero explicit matches | not universal absence | SUPPORTED | #80 |
| `Sessions[]` host-scoped primitive | structural | `..._computers.json` | `ObjectIdentifier`, `Sessions[].UserId/UserSID` | identity + collection time | array empty on 100/100 hosts | empty != false | PARTIALLY_SUPPORTED | #80/#92 |
| HasSession = credential material | runtime | session primitive | `Sessions[]` | admin control; freshness; access | no elements in current snapshot | credential outcome absent | TOO_STRONG | #80 |
| `enabled=false` removes topology | runtime | SEAMLESS `Properties.enabled` | `Properties.enabled` + relationship field | transition-specific enabled predicate | field observed | state separate from topology | SUPPORTED (keep opposite) | #80 |
| RDU alone = CanRDP | runtime | Computer RDU fields | `RemoteDesktopUsers[].MemberId/MemberType` | allow right + no deny right | RDU 3 refs; UserRights absent | endpoint completeness unknown | PARTIALLY_SUPPORTED | #80 |
| Positive PSRemote membership = modeled CanPSRemote | structural | Computer PSRemote fields | `PSRemoteUsers[].MemberId/MemberType` | identity + effective host-bound RMU membership | 2 refs | positive supported; empty != false; runtime separate | SUPPORTED | #44/#45 |
| `4624` alone = RDP | telemetry | `evtx_data.csv` | `ProviderName`, `Channel`, `EventID`, `LogonType` | provider + `LogonType=10` + host/time | 69 rows; mixed logon types | row is not capability | UNSUPPORTED | #79 |
| `4624 + LogonType=10` observation | telemetry | `evtx_data.csv` | provider/context, `EventID`, `LogonType`, identity, host, time | all listed qualifiers | 2/69 qualified rows | not malicious/structural | SUPPORTED | #79 |
| `1149` RDP listener observation | telemetry | `evtx_data.csv` | provider, `EventID`, `{Event_NS}Param1/2/3`, host/time | TerminalServices context | 11 rows | no desktop success | PARTIALLY_SUPPORTED | #79 |
| `4104 => CanPSRemote/WinRM` | telemetry | `evtx_data.csv` | provider/channel, `EventID`, script-block fields | PowerShell context only | 3 rows | no WinRM/action proof | UNSUPPORTED | #79 |
| WinRM provider observation | telemetry | `evtx_data.csv` | provider, 169/193/91 payload/status fields | provider-specific interpretation | 169/193/91 present | lifecycle/status differs | PARTIALLY_SUPPORTED | #79 |
| Sysmon 10 = credential theft | telemetry | `evtx_data.csv` | `TargetImage`, `SourceImage`, `GrantedAccess`, `CallTrace` | Sysmon; target/context | 140 process-access rows | no extraction outcome | UNSUPPORTED | #79 |
| `4672` = credential access | telemetry | `evtx_data.csv` | subject, privilege, host/time | provider/context | 12 rows | privilege assignment only | UNSUPPORTED | #79 |
| `4648` = stolen credentials | telemetry | `evtx_data.csv` | subject/target/process/host/time | explicit-credential context | 7 rows | origin/success absent | UNSUPPORTED | #79 |
| `4732` validates MemberOf | telemetry | `evtx_data.csv` | subject, target, member, host/time | member-added event qualifiers | 2 rows | activity != passive membership | UNSUPPORTED | #79/#80 |
| `5136/4662` validates WriteDacl/GenericAll | telemetry | `evtx_data.csv` | nTSecurityDescriptor/ObjectDN/OperationType/AttributeValue; object access fields | event-specific ACL/object qualifiers | 20 ACL-shaped 5136; 33 4662 | no effective edge | UNSUPPORTED | #79/#80 |
| `4670` observed | telemetry | `evtx_data.csv` | `EventID`, provider/channel | observed row | empty in corpus | absence != environment negative | UNSUPPORTED | #79 |
| `4724` validates ForceChangePassword | telemetry | `evtx_data.csv` | subject/target/host/time | reset activity context | 1 row | attempt != static right/success | UNSUPPORTED | #79/#80 |
| Event rows = static HasSession | telemetry | `evtx_data.csv` | `4624/4634/1149/...`, logon/session IDs, time | identity/host/time lifecycle correlation | fields available; no policy | single row insufficient | PARTIALLY_SUPPORTED | #79/#92 |
| `EVTX_Tactic` = Windows ground truth | evaluation | `evtx_data.csv` | `EVTX_Tactic` + native provider/event fields | annotation provenance | 4,633 annotated rows | annotation not native truth | UNSUPPORTED | #47 |
| EDA host arrays = verified edge counts | evaluation | EDA + SEAMLESS | `LocalAdmins`, RDU, PSRemote, Sessions | canonical rules/completeness | arrays sparse/empty | empty/error unknown | TOO_STRONG | #80/#45 |
| EventID distribution = attack counts | evaluation | EDA + telemetry | `EventID`, `EVTX_Tactic`, qualifiers | ground truth/denominator | row counts measured | event ID not attack | UNSUPPORTED | #47 |
| SEAMLESS ↔ telemetry entity-level validation | evaluation | two snapshots | identity/host/time fields | shared environment/namespace/time | not available | join policy absent | UNRESOLVED | #47 |
| Reproducible claim provenance tuple | evaluation | manifests, audits, contract | dataset/snapshot/file/field/collector/rule | all tuple members retained | field-scoped inventory available | locator/status contract incomplete | PARTIALLY_SUPPORTED | #81 |
| Provenance bag = ordered derivation lineage | evaluation | contract + raw audits | raw file/collector/timestamp/evidence | ordered step schema | field provenance available | sequence absent | UNSUPPORTED | #92 |

## 11. Claims cần downgrade

* “`RemoteDesktopUsers[]` là `CanRDP`” → “host-scoped RDU membership evidence”; chỉ
canonicalize khi có RDU + `SeRemoteInteractiveLogonRight` + không có deny right.
* Positive `LocalAdmins[]` có thể materialize canonical `AdminTo` theo ADR-0003/#80 sau identity/host resolution; chỉ bỏ các wording suy ra arbitrary SYSTEM/runtime execution.
* Positive effective `PSRemoteUsers[]` membership có thể materialize modeled `CanPSRemote`; custom endpoint authorization và runtime WinRM execution vẫn cần evidence/predicates riêng.
* EDA now reports raw RDU/RMU/local-admin/session primitives separately from canonical/effective relationship claims; empty or unobserved coverage remains unknown.
* “`4624` indicates RDP” → “`4624` là successful logon; chỉ `LogonType=10` với
provider/context support RemoteInteractive-shaped observation.”
* “`4104` indicates WinRM/CanPSRemote” → PowerShell Script Block Logging observation;
WinRM phải có provider-specific evidence.
* “`5136`/`4662` validate GenericAll/WriteDacl” → ACL-change-shaped/object-access
activity; không validate structural edge.
* “`HasSession` gives credential access” → observed session/opportunity only, không phải
credential material.

## 12. Claims cần remove

* `4732` là điều kiện để passive structural `MemberOf` tồn tại.
* EventID-only mappings `4624 => RDP`, `4104 => CanPSRemote`, `4672 => credential
access`, `4648 => stolen credentials`, `Sysmon 10 => credential theft`.
* Current-SEAMLESS claim rằng explicit `Aces[].RightName=ForceChangePassword` đã được
quan sát; raw inventory chỉ có `ExtendedRight` và không có discriminator đủ.
* `EVTX_Tactic` là Windows-native ground truth hoặc confirmed attack label.
* EventID/row counts là attack counts, validated edges hoặc precision/recall evidence.

“Remove” ở đây là remove wording/semantic assertion khỏi downstream claim surface khi remediation được thực hiện; Phase 3 không sửa production code.

## 13. Claims cần defer

* Canonical `CanRDP`/`CanPSRemote` cho tới khi có approved effective-right and runtime
policy.
* Static/derived `HasSession` từ event correlation cho tới khi có identity, host, time,
logon/logoff policy; ordered lineage route #92.
* Entity-level join SEAMLESS ↔ telemetry vì thiếu shared environment/identity/time.
* Precision/recall/coverage của telemetry-confirmed edges cho tới khi #47 định nghĩa
ground truth, denominator và unknown treatment.
* Extended-right decoding cho ForceChangePassword khi chưa có GUID/schema primitive.

## 14. Claims được giữ nguyên

* SEAMLESS `Group.Members[]` là direct membership evidence; group nesting không tự là
transitive edge.
* `Aces[]` với `PrincipalSID`, `PrincipalType`, `RightName`, `IsInherited` là
collector-normalized ACE-shaped/candidate permission evidence.
* Disabled account state không xóa raw structural topology.
* `CanRDP` canonical rule hiện tại giữ đồng thời effective RDU membership, allow right
và absence of deny right.
* `HasSession` chỉ có nghĩa observed session; không phải credential possession.
* `4624 + LogonType=10` là RemoteInteractive-shaped observation ở telemetry layer.
* `5136 + nTSecurityDescriptor` với ObjectDN/OperationType/AttributeValue là
ACL-change-shaped evidence, không phải effective ACL.
* `EVTX_Tactic` là upstream annotation và corpus population metadata.

## 15. Remediation Matrix

| Finding | Current problem | Required change | Owner issue | Blocking? |
| --- | --- | --- | --- | --- |
| Raw RDU treated as CanRDP | Remediated: EDA now names the raw primitive and reports effective `CanRDP` separately | Keep the composite RDU + allow + no-deny rule and unknown completeness semantics for #45 | #80/#45 | No for EDA; yes for production canonical builder |
| Telemetry claim too strong | EventID/annotation bị đọc thành relation, technique hoặc attack | Provider + event-specific qualifier; tách expected/observed/confirmed | #79 | Yes for telemetry validation |
| Provenance contract missing | Claim mất dataset/snapshot/raw record/field/interpretation lineage | Bổ sung provenance contract và preserve evidence identity | #81 | Yes for reproducibility |
| Parser requires semantic-safe primitive handling | `Aces`, membership, empty/missing/reference state dễ bị normalize quá mạnh | Parse raw primitive, preserve missing/null/empty/unknown, explicit identity scope | #44 | Yes for safe ingestion |
| Graph builder requires approved canonical rules | Primitive host/ACE evidence bị materialize như verified edge | Chỉ build canonical edge theo approved relationship rule; không collapse layers | #45 | Yes for canonical graph |
| Evaluation metric invalid / mismatched layer | Event rows so với structural edge hoặc `EVTX_Tactic` so với native truth | Định nghĩa ground truth/denominator/unknown; đánh giá đúng semantic layer | #47 | Yes for precision/recall/coverage |
| Derived edge lineage ordering required | Evidence bag không serialize được chain/step order | Ordered derivation lineage schema và deterministic serialization | #92 | No for direct raw edges; yes for derived edges |

Không phát hiện owner issue mới trong scope này.
Các gap chưa có đủ evidence được ghi `UNRESOLVED`, không invent issue number.

## 16. Inputs to downstream issues

* **#79** nhận telemetry field/qualifier policy: provider/channel trước EventID,
`LogonType=10`, Script Block vs WinRM, Sysmon 10 qualifiers, group/ACL event discriminators và session correlation prerequisites.
* **#80** nhận semantic downgrade: structural/runtime/activity separation, RDU/rights
rule, membership vs effective capability, disabled-account policy, HasSession meaning.
* **#81** nhận provenance tuple: dataset, snapshot, raw file, record/row locator, field,
collector/parser layer, interpretation rule; bag không đồng nghĩa ordered lineage.
* **#44/#45** nhận raw primitive preservation, unresolved identity, empty/null/status
semantics, ACE/extended-right handling và direct-vs-derived relationship boundary.
* **#47** nhận evaluation prohibition: no EventID-as-attack, no annotation-as-ground-truth,
no cross-environment entity join, unknown không tự thành false negative.
* **#92** nhận nhu cầu ordered derivation/session lineage nếu sau này materialize derived
edges hoặc temporal correlation.

## 17. Remaining unresolved questions

1. SEAMLESS collector status/error/access-denied metadata ở đâu để tách empty from
method-not-run/incomplete collection?
2. `ExtendedRight` có object-specific GUID/schema nào đủ để identify
`User-Force-Change-Password` trong snapshot không?
3. UserRights evidence của từng host có `SeRemoteInteractiveLogonRight` và
`SeDenyRemoteInteractiveLogonRight` ở cùng scope/snapshot không?
4. WinRM event schema/payload nào đủ để define success, endpoint authorization và
actor/target identity?
5. Policy nào resolve telemetry logon IDs, host names, SIDs, time windows và logoff
events thành observed session mà không biến activity thành static topology?
6. Historical `data-inventory.md`, `data-quality-report.md` và BloodHound baselines
có scope A/B khác SEAMLESS; mọi reuse phải giữ dataset/snapshot boundary và không gọi historical counts là current SEAMLESS evidence.

## 18. Completion assessment for #94

Sau Phase 1, Phase 2 và Phase 3, repository đã có:

* SEAMLESS raw anatomy và field-level missing/null/empty/reference analysis;
* Windows telemetry raw anatomy, provider/channel/event qualifiers và safe inventory;
* field meaning và identity/reference semantics;
* explicit distinction giữa missing/null/empty và collection completeness;
* Windows-native fields tách khỏi upstream annotation `EVTX_Tactic`;
* claim-to-field traceability machine-readable và document table;
* concrete remediation matrix map tới #79/#80/#81/#44/#45/#47/#92;
* reproducible generator/tests/checks không copy sensitive raw values.

Vì vậy:

```text
#94 research work is evidence-complete.
```

Còn lại chỉ là downstream implementation/research work: parser/builder semantic handling (#44/#45), telemetry semantics (#79), approved canonical rules (#80), provenance contract (#81), evaluation redesign (#47) và ordered lineage (#92).
Phase 3 không tự triển khai hoặc close các issue đó.
