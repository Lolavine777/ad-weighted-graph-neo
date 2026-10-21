# Windows telemetry raw anatomy và field-by-field forensic audit

Generated inventories under `reports/generated/` are local outputs, absent from a clean checkout.
Use the reproduction commands below to create them; they are not tracked repository links.

## 1. Phạm vi và kết luận ngắn

Đây là Phase 2 của #94.
Audit chỉ đọc các bytes đã được manifest xác minh của `data/raw/telemetry/evtx_data.csv`.
Không sửa graph builder, parser, canonical relationship semantics, hay #79 Phase B.
Không dùng Event ID đơn lẻ để gán ATT&CK technique hoặc structural relationship.

Kết luận quan trọng nhất: `evtx_data.csv` không phải một bảng Windows event có schema cố định theo một provider.
Đây là một CSV phẳng dạng union-schema của nhiều EVTX sample, provider và payload khác nhau.
Một row thường gồm:

```text
event/log context + System metadata + provider-specific EventData
                 + dataset annotations
```

Các cell CSV đều là chuỗi; cell rỗng là biểu diễn missing duy nhất quan sát được.
Vì vậy `EventID=1`, `Version=2`, `Task=...`, `AccessMask=...` phải được đọc cùng `ProviderName`, `Channel`, event-specific qualifiers và correlation context.

## 2. Raw bytes và population đã xác minh

| Thuộc tính | Giá trị đo từ bytes |
| --- | --- |
| Dataset | `telemetry-raw-v1` |
| Snapshot | `sha256:4203d3f13e42aa7a84f32762b78bfe87267f66318267a7cf80b9f23c620cc9c1` |
| Raw reference | `snapshot:4203d3f13e42aa7a84f32762b78bfe87267f66318267a7cf80b9f23c620cc9c1/evtx_data.csv` |
| File size | `4,262,506` bytes |
| SHA-256 | `9220b0725221244a6b61dff8dabbf382831c0fcc2ad9d261ae60cb1f2b082fff` |
| Encoding | UTF-8 with BOM |
| Data rows | `4,633` |
| CSV columns | `326` |
| Computers | `19` |
| EVTX filenames | `249` |
| Provider values | `24` |
| Channel values | `12` |
| Event IDs | `95` |
| `EVTX_Tactic` values | `8` |

`EVTX_Tactic` phân bố trên 8 nhãn (`Lateral Movement` 1.288, `Privilege Escalation` 1.088, `Execution` 533, `Command and Control` 432, `Defense Evasion` 431, `Persistence` 411, `Credential Access` 283, `Discovery` 167).
Đây là annotation của dataset, không phải field Windows native và không phải bằng chứng cho một event cụ thể đã thực hiện technique tương ứng.
Upstream repository mô tả mapping ở mức ATT&CK technique, không phải procedure; audit này giữ annotation đó tách khỏi raw event semantics ([upstream README](https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES)).

Full inventory gồm cả 326 header, presence, empty count, value shape và safe categorical values nằm ở `reports/generated/windows-telemetry-raw-field-inventory.json`.
Inventory được tạo bằng [audit_windows_telemetry_raw.py](../../scripts/audit_windows_telemetry_raw.py).

## 3. CSV đang biểu diễn gì?

### 3.1 Envelope và những điểm cần cảnh giác

- Cột đầu tiên có header rỗng, gồm đúng `0..4632`, unique trên 4.633 row. Đây là
row ordinal của CSV assembly, không phải EventRecordID, PID hay Windows identity.
- `Channel`, `Computer`, `EventID`, `EventRecordID`, `Guid`, `Keywords`, `Level`,
`Opcode`, `ProviderName`, `SystemTime`, `Task`, `ThreadID`, `Version` là nhóm event-envelope/System metadata được flatten vào CSV.
- Các field như `UtcTime`, `CommandLine`, `Image`, `TargetImage`, `ScriptBlockText`,
`ObjectDN` và `AccessMask` là provider/event-payload fields; chúng không hiện diện ở mọi row.
- Các tên có namespace, ví dụ `{Event_NS}Param1` hoặc
`{http://manifests.microsoft.com/...}SubjectUserName`, là tên payload được exporter giữ lại, không phải hai canonical field mới.
- `EVTX_FileName` là source sample locator/annotation. Nó không chứng minh row được
sinh trong cùng một host, cùng một phiên, hay cùng một thời điểm với row khác.
- `EVTX_Tactic` là upstream annotation. `RuleName` là provider/config label khi
xuất hiện trong Sysmon event; chuỗi `technique_id=...` trong field này không được nâng thành ground truth của hành vi.

Một số anomaly cho thấy union-schema không thể được đọc như schema typed:

- `EventRecordID` có `4.511` giá trị unique cho `4.633` row; nó là record number
trong từng source log/sample, không phải khóa toàn corpus.
- `Guid` chỉ present ở `4.244/4.633` row; absence không phải event failure.
- `SystemTime` present ở mọi row, nhưng `UtcTime` chỉ present ở `2.401` row; hai
field phải giữ provenance provider riêng.
- `Version` có cả giá trị integer-like và `9.01`, `10.42` trên Sysmon event `4`,
cho thấy cùng header có thể gom nhiều payload/context semantics.
- Có `5` row mà `ProviderName` mang tên như `"BotConsumer23"`, `"BotFilter82"` hoặc
`"ProbeScriptFint"`, trong khi channel/GUID vẫn trỏ về Sysmon.
Đây là dấu hiệu cần cross-check field alignment/provider context; không được dùng mọi cell `ProviderName` làm authority độc lập.

### 3.2 Provenance classification của từng column

| Class | Columns/shape | Ý nghĩa forensic |
| --- | --- | --- |
| `csv_transformation` | unnamed first column | Ordinal do bảng CSV; không có Windows semantics. |
| `event_envelope` | `Channel`, `Computer`, `EventID`, `EventRecordID`, `Guid`, `Keywords`, `Level`, `Opcode`, `ProcessID`, `ProviderName`, `SystemTime`, `Task`, `ThreadID`, `Version` | Metadata/log context lấy từ Event/System hoặc record context rồi flatten; phải giữ provider/channel khi diễn giải. |
| `event_payload_or_provider_field` | Phần lớn các column còn lại: `Subject*`, `Target*`, `Image`, `CommandLine`, `Access*`, `Object*`, `ScriptBlock*`, `ClientIP`, `authenticationMechanism`... | EventData/provider-specific value; ý nghĩa chỉ được chốt trong schema của event/provider tương ứng. |
| `parser_preserved_payload_name` | Column bắt đầu bằng `{...}` | XML namespace/name được giữ lại; không tự normalize thành field canonical. |
| `upstream_annotation` | `EVTX_FileName`, `EVTX_Tactic` | Annotation/locator của corpus, không phải Windows event evidence. |

### 3.3 Field families: đọc toàn bộ schema mà không biến tên field thành claim

Bảng này là bản đồ đọc cho toàn bộ union-schema.
Từng header cụ thể, index, số row present/empty và shape nằm trong inventory máy đọc được; tên field không xuất hiện ở family nào ngoài các nhóm dưới đây vẫn phải được đọc như `event_payload_or_provider_field` và kiểm tra theo provider/event.

| Family | Column tiêu biểu / thành viên | Row đang nói gì | Không được suy ra |
| --- | --- | --- | --- |
| Record locator | unnamed, `EVTX_FileName`, `EventRecordID` | ordinal CSV, tên sample, hoặc record number được xuất | cùng event/session giữa hai row, hoặc chronology toàn corpus |
| Event identity | `Channel`, `ProviderName`, `EventID`, `Guid`, `Version`, `Task`, `Opcode`, `Level`, `Keywords` | record thuộc log/provider nào và event metadata nào được xuất | Event ID có cùng nghĩa giữa các provider; severity = maliciousness |
| Host/time | `Computer`, `SystemTime`, `UtcTime`, `TimezoneBiasHour`, `TerminalSessionId` | host, timestamp/context do provider ghi | tất cả timestamp cùng timezone/clock; host names cùng một enterprise |
| Subject/target identity | `SubjectUserName`, `SubjectUserSid`, `SubjectDomainName`, `TargetUserName`, `TargetUserSid`, `TargetDomainName`, `UserID`, `User`, `username`, `MemberSid`, `TargetSid` | principal/account strings hoặc SID được event ghi | SID/name đã resolve đúng, account là attacker, hoặc target là canonical graph node |
| Logon/authentication | `LogonType`, `LogonGuid`, `SubjectLogonId`, `TargetLogonId`, `AuthenticationPackageName`, `LogonProcessName`, `IpAddress`, `IpPort`, `WorkstationName`, `RestrictedAdminMode`, `TargetInfo` | thuộc tính của một logon/authentication record | session kéo dài, RDP/WinRM cụ thể nếu qualifier không khớp, credential compromise |
| Process execution | `NewProcessName`, `NewProcessId`, `ProcessName`, `ProcessId`, `Image`, `CommandLine`, `ParentImage`, `ParentCommandLine`, `ProcessGuid`, `ParentProcessGuid`, `NewProcessId`, `TokenElevationType`, `IntegrityLevel`, `OriginalFileName` | process creation/context hoặc process identity | execution success, maliciousness, privilege escalation, hay parent-child correlation nếu thiếu time/GUID/context |
| Sysmon process/network/file/registry | `SourceImage`, `TargetImage`, `GrantedAccess`, `SourceProcess*`, `TargetProcess*`, `SourceIp`, `DestinationIp`, `SourcePort`, `DestinationPort`, `Protocol`, `TargetFilename`, `TargetObject`, `EventType`, `Details`, `ImageLoaded`, `Hashes`, `Signature*` | Sysmon provider payload về process access, network, file, registry, image, signature | technique/attack outcome từ Event ID; `GrantedAccess` một mình không xác nhận credential theft |
| Security object/access | `ObjectName`, `ObjectDN`, `ObjectType`, `ObjectServer`, `HandleId`, `AccessList`, `AccessMask`, `AccessReason`, `Properties`, `RelativeTargetName`, `ShareName`, `ShareLocalPath` | object/access request hoặc directory/file-share audit | ACL đã bị sửa, effective access, hay successful file/AD modification nếu event chỉ là access/check |
| AD directory change | `AttributeLDAPDisplayName`, `AttributeSyntaxOID`, `AttributeValue`, `OperationType`, `ObjectClass`, `ObjectGUID`, `DSType`, `DSName`, `OpCorrelationID`, `AppCorrelationID` | directory object/attribute change context | mọi `5136` là ACL change; phải kiểm tra attribute (`nTSecurityDescriptor`) và operation pair |
| Group/account management | `MemberName`, `MemberSid`, `TargetUserName`, `TargetSid`, `UserAccountControl`, `PasswordLastSet`, `ServicePrincipalNames`, `SidHistory`, `AllowedToDelegateTo`... | fields của event account/group change | membership closure, effective privilege, credential validity |
| PowerShell | `ScriptBlockId`, `ScriptBlockText`, `MessageNumber`, `MessageTotal`, `Path`, `param1`, `param2` | PowerShell provider payload; script block content khi logging bật | script đã chạy thành công, payload độc hại, hay credential access chỉ vì provider là PowerShell |
| WinRM | `authenticationMechanism`, `username`, `EventPayload`, `ErrorCode`, `UserID` | WinRM/WSMAN lifecycle/auth payload trong những event có field | remote command đã thành công nếu chỉ có error/payload; WinRM access chỉ từ Event ID |
| RDP | `{Event_NS}Param1..3`, `ClientIP`, `ConnType`, `ConnectionName`, `ServerName`, `GfxChannelOpened`, `FirstGraphicsReceived`, `PromptForCredentials*`, `listenerName` | RDP listener/auth/connection/core-session observations tùy provider/event | một event đơn lẻ chứng minh đầy đủ user session, credential exposure, hay sustained access |
| Services/tasks/WMI/BITS/application | `ServiceName`, `AccountName`, `ImagePath`, `StartType`, `TaskName`, `TaskContent`, `Consumer`, `Filter`, `Operation`, `jobId`, `url`, `Installer`, `LSPName`... | provider-specific persistence/application/transfer/WMI data | ATT&CK technique hoặc confirmed attack |
| Namespace/payload variants | mọi tên bắt đầu bằng `{Event_NS}` hoặc `{http://...}` | field name gốc/namespace được exporter giữ | field giống tên không namespace là cùng một source/meaning |

## 4. Event-specific qualifiers đã thật sự tồn tại

Các số dưới đây là count của raw rows trong snapshot, không phải count entity, relationship hay successful attack.

### 4.1 RDP / Remote Interactive

| Evidence layer | Raw observation | Có thể support | Không thể support một mình |
| --- | --- | --- | --- |
| RCM `1149` | `11` rows; provider `Microsoft-Windows-TerminalServices-RemoteConnectionManager`; `{Event_NS}Param1` user, `Param2` domain, `Param3` client address | RDP listener authentication-shaped observation có user/domain/client tuple | không tự chứng minh Security logon/session đã được tạo, access thành công đến desktop, hay credential exposure |
| RDP Core `131` | `22` rows; `ClientIP`, `ConnType` | RDP core network/connection observation | không có user identity trong row này; không tự join với user của row khác |
| Security `4624` | `69` rows; `LogonType`: 3 (44), 5 (13), 2 (4), 9 (3), 10 (2), 0/7/11 mỗi loại 1 | chỉ 2 rows có qualifier `LogonType=10` (RemoteInteractive); kèm target account, logon IDs, auth package, source address khi present | `4624` nói chung không đồng nghĩa RDP; type 3 là Network, type 5 là Service; type 10 vẫn không chứng minh maliciousness |
| RDP Core `68/168/104` | graphics/monitor/session metadata ở các row có field tương ứng | connection/session lifecycle evidence khi correlation đầy đủ | không suy ra một `HasSession` graph edge hoặc session persistence |

Microsoft mô tả `4624` là event tạo logon session trên máy đích và `LogonType=10` là RemoteInteractive/Terminal Services hoặc Remote Desktop; do đó discriminator là tổ hợp provider + `LogonType` + target/source context, không phải `EventID=4624` đơn độc ([4624](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4624)).

### 4.2 PowerShell và WinRM

| Evidence layer | Raw observation | Diễn giải tối thiểu |
| --- | --- | --- |
| PowerShell `4104` | `3` rows, channel `Microsoft-Windows-PowerShell/Operational`, `ScriptBlockId`, `MessageNumber/Total`, `ScriptBlockText`; cả 3 có text | script-block logging đã ghi nội dung PowerShell; nội dung là discriminator mạnh hơn Event ID |
| Sysmon process creation `1` | `841` rows do Sysmon; `CommandLine`, `Image`, parent/process GUID có mặt | process create record; chỉ row có `Image`/`CommandLine` PowerShell mới là PowerShell process evidence |
| WinRM `169` | `3` rows, `authenticationMechanism=NTLM`, `username=iewin7\\ieuser` | WinRM authentication/lifecycle payload có cơ chế và username |
| WinRM `193` | `3` rows | WinRM provider lifecycle payload nhưng row không có username/authentication field |
| WinRM `91` | `1` row, `ErrorCode=15005`, base64-like `EventPayload` | WinRM event có payload/error; cần decode/schema và status interpretation trước khi gọi là command/session success |

PowerShell `4104` là Script Block Logging theo Microsoft, nhưng logging chỉ cho biết script block được ghi; không tự chứng minh lệnh chạy thành công hoặc độc hại ([PowerShell logging](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_logging?view=powershell-5.1)).

### 4.3 Credential-access-shaped evidence

Dataset có discriminator, nhưng không có một cột `CredentialAccess=true`:

- Sysmon `10` có `140` rows với `SourceImage`, `TargetImage`, `GrantedAccess`,
`CallTrace`, process GUID/PID.
Đây là process-access evidence; các row target vào `lsass.exe`, quyền truy cập và source process phải được kiểm tra cùng nhau.
- PowerShell `4104` có `3` script blocks; raw text chứa nội dung cụ thể khác nhau.
Text là evidence content, không phải outcome.
- Security `4672` có `12` rows về special privileges; nó mô tả privilege assignment
cho logon, không chứng minh credential access.
- Security `4648` có `7` rows về explicit credentials; nó là explicit-credential
use attempt/context, không chứng minh credential bị đánh cắp.
- Security `4624` có nhiều logon types; `LogonType`, auth package, account and source
context cần được lọc.
Một `4624` không phải credential access finding.

Microsoft mô tả Sysmon `10` là process mở process khác và lưu ý nó có thể hỗ trợ phát hiện đọc memory của LSASS, nhưng cũng có thể noisy; vì vậy `EventID=10` không đủ ([Sysmon events](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon)).

### 4.4 Group modification

Raw snapshot chỉ có `4732` với `2` rows.
Cả hai có: `SubjectUser*`, `TargetDomainName`, `TargetUserName`, `TargetSid`, `MemberSid` và `MemberName`.
Đây là discriminator đầy đủ để nói “member được thêm vào security-enabled local group” ở event layer; phải giữ `Target*` và `Member*` để biết group/member nào.

Các Event ID group-change khác được kiểm tra nhưng không xuất hiện: `4728`, `4729`, `4733`, `4756`.
Sự vắng mặt đó chỉ là absence trong corpus, không phải negative fact về môi trường Windows.

Microsoft phân biệt `4728` (global group) với `4732` (local group), và mô tả chúng là member added events ([Security Group Management](https://learn.microsoft.com/zh-tw/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/audit-security-group-management)).

### 4.5 ACL / directory permission modification

`5136` có `42` rows.
Trong đó:

- `AttributeLDAPDisplayName=versionNumber`: `22` rows, `ObjectClass=groupPolicyContainer`;
- `AttributeLDAPDisplayName=nTSecurityDescriptor`: `20` rows, `ObjectClass=domainDNS`;
- `OperationType` được xuất ở cả hai giá trị encoded `%%14674` và `%%14675`, mỗi loại
`21` rows;
- `AttributeValue`, `ObjectDN`, `ObjectGUID`, `SubjectUser*` đều có trong `42` rows.

Do đó `5136 + nTSecurityDescriptor + ObjectDN + OperationType + AttributeValue` là ACL-change-shaped directory evidence.
Nó chưa phải effective ACL, canonical edge, hay attack success; cần decode operation/resource semantics và ghép value deleted/value added theo correlation/time nếu muốn xác định một change.

`4662` có `33` rows với `ObjectName`, `ObjectType`, `AccessList`, `AccessMask`, `OperationType`, `Properties`, `SubjectUser*`; đây là object-access evidence.
Nó không tự chứng minh ACL bị sửa.
`4670` — event Windows có nghĩa “permissions on an object were changed” — không xuất hiện trong snapshot, nên không được viết rằng corpus đã quan sát 4670.

Microsoft tách `4662` (operation performed on an AD object), `5136` (directory object modified), và `4670` (permissions changed); cả ba đều phụ thuộc audit/SACL context ([4662](https://learn.microsoft.com/ja-jp/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4662), [5136](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-5136), [4670](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4670)).

### 4.6 Session observation

Session-shaped discriminators thật sự có trong dữ liệu:

- `4624`: `TargetLogonId`, `LogonGuid`, `LogonType`, target account và host;
- `4634`: `1` logoff row với `TargetLogonId`/target account;
- RDP `1149`, `131`, `68`, `168`, `104`: listener/client/core/graphics fields;
- Sysmon process rows có `LogonId` và `TerminalSessionId` ở nơi provider ghi.

Các field này support “một logon/connection/session-related observation trên host tại thời điểm event”.
Chúng không support `User U HasSession Computer C` như một relationship tĩnh nếu chưa có event correlation, identity resolution, time window, logoff handling và source/target policy.
`UserID=S-1-5-20` trên RDP/WinRM provider không phải user login identity; đó là identity/context mà provider ghi cho event.

### 4.7 Account/password management

Security `4724` xuất hiện `1` row trong verified snapshot.
Event này là password-reset-attempt/activity evidence và phải được đọc cùng provider/channel, subject/target identity, host/time và outcome fields nếu provider cung cấp.
Nó không chứng minh structural `ForceChangePassword` right, không chứng minh reset thành công, và không phải prerequisite để một ACE reset-password tồn tại.
`audit_windows_telemetry_raw.py` đưa `4724` vào `selected_event_profiles` để các qualifier thực sự present có thể được đo lại từ manifest-verified corpus.
Structural capability và observed password-reset activity vì vậy phải được giữ ở hai semantic layer riêng.

## 5. Những gì một Event ID đứng một mình không chứng minh được

| Chỉ nhìn | Có thể nói tối đa | Không được nói |
| --- | --- | --- |
| `4624` | Windows ghi successful logon event | “đây là RDP”, “đây là lateral movement”, “đã có credential exposure” |
| `4624 + LogonType=10` | remote-interactive logon-shaped event; RDP/Terminal Services context | malicious RDP, persistence, graph edge, hay attack success |
| `1149` | RDP listener authentication-shaped event | session desktop đã established, user có quyền RDP, credential đã bị lấy |
| `4104` | PowerShell script block được logging | PowerShell attack/WinRM/credential access đã thành công |
| `1` | Sysmon/process provider ghi process-create-shaped record khi provider là Sysmon | execution thành công, malicious process, hay technique |
| `10` | Sysmon process-access record | credential theft; phải inspect target/source/access/correlation |
| `4662` | object operation/access được audit | ACL modification; `AccessMask` không tự là effective permission |
| `5136` | AD object/attribute modification được audit | mọi row là ACL change; cần `AttributeLDAPDisplayName=nTSecurityDescriptor` |
| `4732` | member added vào security-enabled local group | membership closure/effective admin path/attack outcome |
| `5145` | network share access check | RDP, file modification success, hay relationship |
| `EVTX_Tactic` | upstream corpus label | Windows generated tactic, ground truth, confirmed technique |

Event ID còn không globally unique về semantics: `EventID=1` xuất hiện `843` lần, trong đó `841` từ Sysmon và `2` từ `Microsoft-Windows-Winsock-WS2HELP`; `EventID=3` có cả Sysmon (`150`) và BITS (`3`).
Vì vậy provider + channel là discriminator tối thiểu trước khi đọc Event ID.

## 6. Evidence policy cho các phase sau

Telemetry row nên được giữ theo tầng:

```text
raw CSV cell
  -> event/provider interpretation
  -> event-specific qualifier set
  -> correlated observation (nếu đủ host/time/identity evidence)
  -> descriptive audit signal
```

Không thực hiện bước cuối thành graph relationship trong Phase 2.
Đặc biệt:

- không entity-join telemetry với SEAMLESS chỉ vì tên/SID trông giống nhau;
- không coi corpus annotation là observed activity;
- không dùng missing/empty Event ID hoặc field để kết luận “không xảy ra”;
- không dùng `EventID -> technique`, `EventID -> relationship`, hoặc
`EventID -> confirmed attack` như transformation rule;
- mọi claim RDP, PowerShell/WinRM, credential access, group/ACL modification và
session phải trích dẫn raw discriminator tương ứng và nêu rõ giới hạn.

## 7. Reproduce

```bash
python scripts/audit_windows_telemetry_raw.py
pytest -q tests/test_audit_windows_telemetry_raw.py
```

Script bắt buộc verify toàn bộ snapshot bằng `data/samples/manifests/telemetry-raw-v1.json` trước khi parse.
Report không ghi script/command/payload dài; nó chỉ phát hành safe categorical values và thống kê field/value-shape để tránh biến audit inventory thành bản sao của sensitive event content.
