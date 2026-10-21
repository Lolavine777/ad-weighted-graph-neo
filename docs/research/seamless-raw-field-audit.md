# SEAMLESS Raw Field Audit

## 1. Phạm vi và phương pháp

Đây là Phase 1 của #94: giải phẫu corpus raw và khảo cổ schema theo từng field của snapshot SEAMLESS đã được xác minh.
Auditor chỉ đọc bytes sau khi kiểm tra manifest; phát hiện field đệ quy; đo `missing`, `null`, container rỗng, container không rỗng; và chỉ phát hành dạng giá trị/categorical value an toàn.
Auditor không import hoặc thay đổi parser, graph builder hay attack semantics.

Mỗi giải thích dưới đây tách ba tầng: (1) biểu diễn raw, (2) ý nghĩa mà collector thường gắn cho cấu trúc đó, và (3) mức diễn giải mà project có thể dùng sau khi bổ sung policy/semantics.
Tên field không tự trở thành canonical relationship.

## 2. Nguồn gốc snapshot

- Dataset ID: `seamless-v1`
- Snapshot ID: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`
- Trạng thái xác minh: `verified`
- Kích thước snapshot: `11371828` bytes
- Commit của generator: `d82dd6888c16288b3a1bf51164a6ba25db0b7e40`
- SHA-256 generator: `49567eb71ad0a38d1222cae774f0e4e1ca588f7f51d63fcc7f6bad4d936f9415`
- Raw provenance dùng dạng `snapshot:<digest>/<relative_path>`; không ghi absolute path hay raw identity.

Thứ tự evidence của tài liệu là: raw record thực tế → schema/collector SharpHound → tài liệu Windows/AD có thẩm quyền khi field phản ánh Windows semantics → ADR/research đã chấp nhận trong repository → consumer hiện tại chỉ để biết code đang dùng field ở đâu, không dùng làm source-of-truth cho ý nghĩa raw.

Nguồn giải thích: [raw snapshot và manifest trong repository](../../data/samples/manifests/seamless-raw-v1.json); [mã nguồn SharpHound](https://github.com/SpecterOps/SharpHound); [SharpHound technical details](https://specterops.io/blog/2017/10/14/sharphound-technical-details/); [Microsoft ACE](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-entries); [Microsoft ACCESS_MASK](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-mask); [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing); [Microsoft gPCFileSysPath](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-ada1/6eb770b7-0c89-4a3e-a41e-2807d46880d8); [Microsoft Group Policy storage](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/policy/group-policy-storage); [Microsoft trust direction](https://learn.microsoft.com/en-us/windows/win32/api/ntsecapi/ns-ntsecapi-trusted_domain_information_ex); [Microsoft account rights](https://learn.microsoft.com/en-us/windows/win32/secauthz/account-rights-constants).

## 3. Cấu trúc envelope JSON chung

Cả sáu file là JSON object mã hóa UTF-8 có `meta` và một collection key dạng số nhiều.
`meta` thực tế chỉ có `count`, `type`, `version`; `meta.count` khớp độ dài collection ở cả sáu file.
Snapshot không có field status/error cho collection.

| Loại object | Tệp | Khóa collection | Khóa top-level | Số record | Field trong meta |
| --- | --- | --- | --- | ---: | --- |
| `Computer` | `20210920185958_computers.json` | `computers` | computers, meta | 100 | count, type, version |
| `Domain` | `20210920185958_domains.json` | `domains` | domains, meta | 1 | count, type, version |
| `GPO` | `20210920185958_gpos.json` | `gpos` | gpos, meta | 2 | count, type, version |
| `Group` | `20210920185958_groups.json` | `groups` | groups, meta | 550 | count, type, version |
| `OU` | `20210920185958_ous.json` | `ous` | meta, ous | 223 | count, type, version |
| `User` | `20210920185958_users.json` | `users` | meta, users | 2493 | count, type, version |

Kiểu mã hóa và key-set chính xác của record nằm trong inventory máy đọc được: `reports/generated/seamless-raw-field-inventory.json`.

## 4. Quy ước đọc các field quan trọng

### 4.1 `ObjectIdentifier`

`ObjectIdentifier` nằm ở top-level của record và là định danh mà output của BloodHound/SharpHound dùng để nhận diện object hiện tại.
Trong snapshot này, auditor quan sát 3369 record, 3368 giá trị unique; shape gồm SID-like (3113), GUID-like (225) và domain/composite-like (31).

Cách đọc: đây là object identifier ở output collector, được các field reference khác dùng để trỏ tới object trong cùng snapshot.
Nó không nên được gọi ngay là canonical project identity: snapshot có một duplicate Group identifier, có reference chưa resolve, và scope/external policy vẫn là câu hỏi riêng.

Nếu một record có `ObjectIdentifier = G` thì chỉ có thể kết luận collector đã xuất record đó dưới identifier G.
Việc G có phải một object AD duy nhất, một boundary, hay một identity canonical sau reconciliation là interpretation downstream.

### 4.2 `Properties`

`Properties` là object gom các thuộc tính descriptive/state mà collector xuất cho object.
Một số field gần với thuộc tính directory; một số field là cờ/nhãn hoặc kết quả normalize của collector.
Không được giả định mọi key trong `Properties` là raw LDAP attribute nguyên bản.

Các subfield được giải thích theo từng loại object trong các phần tiếp theo; bảng đo lường vẫn giữ toàn bộ path, type, present/missing/null/empty/non-empty và value shape.
`Properties.domainsid` không xuất hiện trong verified snapshot hiện tại.

### 4.3 `Aces[]` dùng chung cho các object kind

Khi `Aces[]` xuất hiện trong một record, mỗi element phải được đọc theo hướng: trustee/principal P — được collector phân loại và gắn một nhãn quyền — trên object hiện tại O.
`PrincipalSID` là reference-shaped identity của trustee, `PrincipalType` là nhãn object kind, `RightName` là nhãn quyền đã được collector normalize, còn `IsInherited` là cờ inherited do collector xuất.
`AceType` được inventory riêng vì snapshot cho thấy value behavior không đồng nhất giữa các object kind.

Tầng raw là một mảng ACE-shaped object; tầng collector là diễn giải trustee/quyền trên object O; tầng project chỉ nên xem đây là candidate permission evidence sau khi đối chiếu Windows security descriptor/DACL và policy.
Không được coi `RightName` là raw access mask hoặc tự dựng canonical edge/attack technique từ field name.

## 5. `users.json` — User

### File này biểu diễn cái gì?

File này chứa các object mà collector phân loại là User trong snapshot Active Directory.
Mỗi record đại diện cho một User object được collector quan sát tại thời điểm collection.
Record có thể chứa thuộc tính descriptive/state cùng các cấu trúc ACL, delegation và reference đã được collector tổng hợp; không phải field nào cũng là LDAP raw attribute.

### Cấu trúc envelope và một record

File được đọc qua `snapshot:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812/20210920185958_users.json`, mã hóa `UTF-8 with BOM`, collection key `users`, gồm `2493` record.
Top-level keys: `meta, users`.

Một User record biểu diễn một account/object ở directory snapshot.
`Properties` mô tả account, còn `Aces`, `PrimaryGroupSid`, `AllowedToDelegate`, `SPNTargets` và `HasSIDHistory` là các primitive/reference được collector đưa vào cùng record.

### Các field chính

`ObjectIdentifier` và container `Properties` dùng quy ước semantic chung ở §4; phần này tập trung vào các subfield và primitive có ý nghĩa riêng cho object kind này.

### Các `Properties.*` quan trọng

Bảng dưới đây là phần giải thích ngữ nghĩa cấp Tier B; mọi con số vẫn lấy từ inventory đã xác minh.

| Field con | Quan sát | Ý nghĩa được dùng trong tài liệu | Không được suy ra |
| --- | --- | --- | --- |
| `admincount` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false; boolean: true | Cờ thuộc tính mà collector xuất ra cho trạng thái `adminCount` của object. Nó là tín hiệu directory/collector, không phải bản đồ đầy đủ về đặc quyền hiệu lực. | Không tự chứng minh object là quản trị viên hay mọi quyền của object đã được thu thập. |
| `description` | kiểu `string`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; composite/domain-like string: <redacted>; string | Thuộc tính mô tả của object; giá trị có thể là chuỗi hoặc `null` trong snapshot. | Không phải bằng chứng về trạng thái vận hành hay quyền hạn. |
| `displayname` | kiểu `null, string`, có mặt 2493/2493 record gốc, thiếu 0, `null` 4, rỗng 0, không rỗng 2489; null; string | Tên hiển thị được collector xuất; snapshot có cả giá trị chuỗi và `null`. | Không nên dùng làm khóa tham chiếu vì có thể thiếu hoặc không duy nhất. |
| `distinguishedname` | kiểu `string`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; DN-like string: <redacted distinguished name> | Tên phân biệt (DN) mà collector xuất cho object trong namespace directory. | Không tự chứng minh object còn tồn tại, có thể truy cập, hay DN là định danh canonical của project. |
| `domain` | kiểu `string`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; composite/domain-like string: <redacted> | Thông tin domain gắn với object trong output của collector. | Không tự chứng minh trust, membership, hay hướng trust giữa các domain. |
| `dontreqpreauth` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false; boolean: true | Cờ thuộc tính account do collector xuất ra liên quan tới yêu cầu pre-authentication. | Không tự chứng minh một kỹ thuật tấn công, khả năng khai thác, hay trạng thái runtime. |
| `email` | kiểu `null`, có mặt 2493/2493 record gốc, thiếu 0, `null` 2493, rỗng 0, không rỗng 0; null | Ý nghĩa collector của subfield này chưa được xác minh đầy đủ; hiện chỉ ghi nhận như thuộc tính descriptive/state. | Không suy ra canonical edge hoặc trạng thái runtime. |
| `enabled` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false; boolean: true | Cờ enabled/disabled được collector lấy từ thuộc tính account hoặc object. | Không đồng nghĩa với việc account đang đăng nhập được, service đang chạy, hay network path hoạt động. |
| `hasspn` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false; boolean: true | Cờ collector cho biết có dấu hiệu SPN theo record hay không. | Không tự chứng minh service đang chạy hoặc authentication sẽ thành công. |
| `highvalue` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false | Nhãn phân loại giá trị cao mà BloodHound/collector gắn cho object. | Không phải bằng chứng độc lập về quyền Windows hay khả năng khai thác. |
| `homedirectory` | kiểu `null`, có mặt 2493/2493 record gốc, thiếu 0, `null` 2493, rỗng 0, không rỗng 0; null | Thuộc tính mô tả home directory của account; trong snapshot hiện tại là `null`. | Không nên diễn giải `null` thành trạng thái không tồn tại ngoài directory. |
| `lastlogon` | kiểu `integer`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; integer | Giá trị integer timestamp-like do collector xuất cho lần logon cục bộ/được quan sát theo schema. | Auditor chưa xác minh unit/timezone; không được tự quy đổi hoặc coi `0` là `never`. |
| `lastlogontimestamp` | kiểu `integer`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; integer | Giá trị integer timestamp-like tương ứng với thuộc tính logon timestamp mà collector xuất. | Không đủ để khẳng định thời điểm đăng nhập chính xác; unit, replication lag và `0` cần evidence riêng. |
| `name` | kiểu `string`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; composite/domain-like string: <redacted> | Tên hoặc display identity mà collector dùng để mô tả object; giá trị thực tế được auditor redacted. | Không nên dùng làm identity key, vì có thể chứa tên hiển thị, format composite hoặc không duy nhất. |
| `objectid` | kiểu `string`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; SID-like string: S-<redacted> | Bản sao identity property do collector đặt trong `Properties`; trong nhiều record tương ứng với định danh object. | Không nên gộp mặc định với top-level `ObjectIdentifier` mà bỏ qua duplicate/scope behavior. |
| `passwordnotreqd` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false; boolean: true | Cờ account do collector xuất về thuộc tính password requirement. | Không tự chứng minh mật khẩu yếu, có thể đăng nhập, hoặc kỹ thuật tấn công cụ thể. |
| `pwdlastset` | kiểu `integer`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; integer | Giá trị integer timestamp-like mà collector xuất cho lần đặt mật khẩu. | Auditor chưa xác minh unit/timezone và không suy diễn `0`, stale hay khả năng đăng nhập. |
| `pwdneverexpires` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false; boolean: true | Cờ account do collector xuất về chính sách hết hạn mật khẩu. | Không tự chứng minh mật khẩu hiện tại hợp lệ hay một attack path. |
| `sensitive` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false | Cờ thuộc tính account do collector xuất về trạng thái nhạy cảm của object. | Không thay thế kiểm tra kỹ thuật/runtime khác và không tự gắn ATT&CK technique. |
| `serviceprincipalnames` | kiểu `array`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 2442, không rỗng 51; array | Mảng các SPN string mà collector quan sát trên object; có thể rỗng hoặc không rỗng. | Không tự chứng minh service đang chạy, ticket có thể lấy được, hay account có thể bị compromise. |
| `sidhistory` | kiểu `array`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 2493, không rỗng 0; array | Mảng SID history do collector xuất; snapshot hiện tại không có phần tử. | Mảng rỗng không phân biệt không có dữ liệu, collector không thu được, hay schema không áp dụng. |
| `title` | kiểu `null`, có mặt 2493/2493 record gốc, thiếu 0, `null` 2493, rỗng 0, không rỗng 0; null | Thuộc tính mô tả title của user; snapshot hiện tại là `null`. | Không phải identity key hay evidence về quyền. |
| `unconstraineddelegation` | kiểu `boolean`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493; boolean: false | Cờ delegation do collector xuất cho object. | Không tự chứng minh một ticket, session, hay attack đã xảy ra. |
| `userpassword` | kiểu `null`, có mặt 2493/2493 record gốc, thiếu 0, `null` 2493, rỗng 0, không rỗng 0; null | Field password-related được output dưới dạng `null` trong snapshot. | Không được diễn giải thành password không tồn tại hoặc được bảo vệ theo một cách cụ thể. |

#### `PrimaryGroupSid`

**Quan sát từ snapshot**

- `User.PrimaryGroupSid` có kiểu `string`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493.
- Dạng giá trị đại diện đã sanitize: SID-like string: S-<redacted> (2493).

**Tầng 1 — Biểu diễn raw**

Chuỗi SID-like ở top-level record; trong snapshot field này có mặt ở User và Computer.

**Tầng 2 — Ý nghĩa ở collector**

Collector xuất SID của primary group gắn với object theo schema.

**Tầng 3 — Diễn giải của project**

Đây là primary-group reference evidence, không phải danh sách toàn bộ group membership.

**Field này chứng minh:** một reference-shaped SID tới primary group của object.

**Field này không chứng minh:** membership đầy đủ, quyền hiệu lực, hay canonical `MemberOf` closure.

**Mức độ chắc chắn:** Cao cho raw reference; semantics membership cần policy AD riêng.

**Nguồn giải thích:** Raw snapshot; Windows/AD primary-group semantics cần đối chiếu riêng.

#### `Aces[]`

**Quan sát từ snapshot**

- `User.Aces` có kiểu `array`, có mặt 2493/2493 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2493.
- Dạng giá trị đại diện đã sanitize: array (2493).

**Tầng 1 — Biểu diễn raw**

Mảng trong object record; element shape quan sát được là object gồm `AceType`, `IsInherited`, `PrincipalSID`, `PrincipalType`, `RightName`.

**Tầng 2 — Ý nghĩa ở collector**

Collector biểu diễn trustee/principal nào có nhãn quyền nào trên object hiện tại.
`RightName` là collector/BloodHound normalization, không phải raw Windows access mask.

**Tầng 3 — Diễn giải của project**

ACE-shaped evidence → candidate permission evidence.
Project phải tách Windows security descriptor/DACL → collector interpretation → canonical relationship.

**Field này chứng minh:** Ví dụ `PrincipalSID=P`, `RightName=GenericAll` được đọc là collector đang biểu diễn P có một quyền được normalize thành `GenericAll` trên object hiện tại.

**Field này không chứng minh:** effective access, thứ tự allow/deny đầy đủ, exploitability, canonical edge, hay attack technique.

**Mức độ chắc chắn:** Cao cho cấu trúc ACE; trung bình cho semantics quyền hiệu lực.

**Nguồn giải thích:** Raw snapshot; [Microsoft Access Control Entries](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-entries); [Microsoft DACLs and ACEs](https://learn.microsoft.com/en-us/windows/win32/secauthz/dacls-and-aces).

**Các subfield của `Aces[]`:**

Một element ACE phải được đọc theo hướng: principal/trustee P — được collector phân loại và gắn một nhãn quyền — trên object hiện tại O.
Chuỗi diễn giải này không đồng nghĩa với việc raw JSON chứa nguyên Windows security descriptor hoặc access mask.

| Đường dẫn field | Quan sát đo được | Field biểu diễn gì | Chứng minh được | Không chứng minh được | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| `Aces[].PrincipalSID` | kiểu `string`, đã kiểm tra 42268 array element; field có mặt trong 42268/42268 element; field thiếu trong 0 element; parent records có element: 2493/2493; parent records không có element: 0/2493, `null` 0, rỗng 0, không rỗng 42268; SID-like string: S-<redacted>; composite/domain-like string: <redacted> | SID-like hoặc reference-shaped string của trustee/principal trong ACE. | ACE đang gắn evidence quyền với principal P trên object hiện tại. | principal đã resolve đầy đủ, effective access, hoặc target không nằm ngoài scope. | Exact-match và unresolved count được đo ở phần reference archaeology. |
| `Aces[].PrincipalType` | kiểu `string`, đã kiểm tra 42268 array element; field có mặt trong 42268/42268 element; field thiếu trong 0 element; parent records có element: 2493/2493; parent records không có element: 0/2493, `null` 0, rỗng 0, không rỗng 42268; category: Computer; category: Group; category: User | Nhãn object kind do collector gắn cho trustee/principal. | cách collector phân loại trustee, ví dụ `User`, `Group`, `Computer`. | SID resolution, allow/deny semantics, hoặc quyền hiệu lực. | Không thay thế việc resolve `PrincipalSID`. |
| `Aces[].RightName` | kiểu `string`, đã kiểm tra 42268 array element; field có mặt trong 42268/42268 element; field thiếu trong 0 element; parent records có element: 2493/2493; parent records không có element: 0/2493, `null` 0, rỗng 0, không rỗng 42268; category: ExtendedRight; category: GenericAll; category: GenericWrite; category: Owner; category: WriteDacl; category: WriteOwner | Nhãn quyền đã normalize; snapshot quan sát các giá trị categorical an toàn. collector diễn giải một ACE thành nhãn như `GenericAll`, `GenericWrite`, `Owner`, `WriteDacl`, `WriteOwner` hoặc `ExtendedRight`. | candidate permission evidence trên object hiện tại. | raw access mask, đầy đủ điều kiện allow/deny, exploitability, hoặc attack technique. | Chi tiết cách đọc từng giá trị nằm ngay dưới bảng này. |
| `Aces[].AceType` | kiểu `string`, đã kiểm tra 42268 array element; field có mặt trong 42268/42268 element; field thiếu trong 0 element; parent records có element: 2493/2493; parent records không có element: 0/2493, `null` 0, rỗng 39771, không rỗng 2497; category: All; empty string | Field là string; nhiều object kind có toàn bộ element rỗng, còn User có 2497 element không rỗng trong snapshot. ý nghĩa cụ thể chưa xác minh đầy đủ; không được dùng field rỗng này để đoán allow/deny. | key `AceType` tồn tại trên các ACE element được quan sát; giá trị có thể rỗng hoặc mang collector-specific label như `All`. Snapshot không tự xác định semantics allow/deny của label này. | ACE là allow hay deny, thứ tự đánh giá, hoặc DACL hiệu lực. | Đây là open question cần collector/schema evidence bổ sung. |
| `Aces[].IsInherited` | kiểu `boolean`, đã kiểm tra 42268 array element; field có mặt trong 42268/42268 element; field thiếu trong 0 element; parent records có element: 2493/2493; parent records không có element: 0/2493, `null` 0, rỗng 0, không rỗng 42268; boolean: false; boolean: true | Boolean flag trên element ACE. | collector ghi nhận trạng thái inherited của ACE theo output schema. | nguồn inheritance đầy đủ, thứ tự kế thừa, hoặc effective permission sau khi merge ACL. | Không được coi `false` là chứng minh ACE độc lập khỏi mọi policy khác. |

**Cách đọc giá trị `RightName`:**

| Giá trị quan sát | Cách đọc thận trọng |
| --- | --- |
| `ExtendedRight` | Nhãn collector cho extended/control-access right; cần object-specific GUID và security descriptor để xác định quyền cụ thể. |
| `GenericAll` | Nhãn collector cho một nhóm quyền kiểm soát rộng trên object; không phải nguyên access mask và không tự khẳng định effective access. |
| `GenericWrite` | Nhãn collector cho một nhóm quyền ghi rộng; không tự khẳng định mọi thuộc tính đều sửa được trong mọi context. |
| `Owner` | Nhãn collector liên quan tới quan hệ owner của object; không tự mô tả toàn bộ quyền thực tế của owner. |
| `WriteDacl` | Nhãn collector liên quan tới khả năng sửa DACL; không thay thế việc đánh giá ACE allow/deny và access check đầy đủ. |
| `WriteOwner` | Nhãn collector liên quan tới khả năng thay đổi owner; không tự chứng minh hành động đã xảy ra. |

**Finding về hình thái giá trị:** snapshot quan sát các giá trị non-empty `All`, `GetChanges`, `GetChangesAll` trên các object kind có `Aces[]`.
Tập giá trị này không hành xử như một discriminator Windows đơn giản kiểu `ACCESS_ALLOWED_ACE` / `ACCESS_DENIED_ACE`; đặc biệt `GetChanges` và `GetChangesAll` có hình thái giống nhãn quyền hơn là loại ACE allow/deny.

Vì vậy `AceType` phải được coi là nhãn collector/BloodHound-specific cho tới khi trace được implementation/schema tương ứng.
Không được dùng nó để suy ra allow/deny, thứ tự DACL, hoặc effective permission.

**Các giá trị `AceType` không nhạy cảm quan sát được:**

| Giá trị | Cách đọc thận trọng |
| --- | --- |
| `All` | Nhãn `AceType` do collector xuất; không đọc như Windows ACE allow/deny type nếu chưa có implementation/schema evidence. |

### Giá trị categorical và cách đọc

| Field phân loại | Giá trị quan sát | Cách đọc ở tầng raw |
| --- | --- | --- |
| `Aces[].AceType` | `All` (2497) | Giá trị phân loại an toàn được ghi nhận; ý nghĩa đầy đủ cần đọc cùng container field. |
| `Aces[].PrincipalType` | `Computer` (3007), `Group` (34599), `User` (4662) | Loại object mà collector gắn cho trustee/principal trong ACE; không thay thế việc resolve SID. |
| `Aces[].RightName` | `ExtendedRight` (2497), `GenericAll` (29787), `GenericWrite` (2497), `Owner` (2493), `WriteDacl` (2497), `WriteOwner` (2497) | Nhãn quyền đã được collector normalize; không phải raw Windows access mask. |

### Bảng kiểm kê từng field

Bảng sau là phép đo đầy đủ; nó không thay thế phần giải thích ngữ nghĩa ở trên.

| Đường dẫn field | Kiểu quan sát được | Present count | Missing count | Null count | Empty count | Non-empty count | Counting unit / scope | Dạng giá trị đại diện |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Aces | array | 2493 | 0 | 0 | 0 | 2493 | record (2493) | array (2493); array length 13–21 (mean 16.954673) |
| Aces[] | object | 2493 | 0 | 0 | 0 | 2493 | parent record; parent có element 2493/2493, parent không có element 0/2493, parent key missing 0 | object keys: [AceType, IsInherited, PrincipalSID, PrincipalType, RightName] (42268) |
| Aces[].AceType | string | 42268 | 0 | 0 | 39771 | 2497 | array element; examined 42268, parent có element 2493/2493, parent không có element 0/2493 | category: All (2497); empty string (39771) |
| Aces[].IsInherited | boolean | 42268 | 0 | 0 | 0 | 42268 | array element; examined 42268, parent có element 2493/2493, parent không có element 0/2493 | boolean: false (7499); boolean: true (34769) |
| Aces[].PrincipalSID | string | 42268 | 0 | 0 | 0 | 42268 | array element; examined 42268, parent có element 2493/2493, parent không có element 0/2493 | SID-like string: S-<redacted> (27261); composite/domain-like string: <redacted> (15007) |
| Aces[].PrincipalType | string | 42268 | 0 | 0 | 0 | 42268 | array element; examined 42268, parent có element 2493/2493, parent không có element 0/2493 | category: Computer (3007); category: Group (34599); category: User (4662) |
| Aces[].RightName | string | 42268 | 0 | 0 | 0 | 42268 | array element; examined 42268, parent có element 2493/2493, parent không có element 0/2493 | category: ExtendedRight (2497); category: GenericAll (29787); category: GenericWrite (2497); category: Owner (2493); category: WriteDacl (2497); category: WriteOwner (2497) |
| AllowedToDelegate | array | 2493 | 0 | 0 | 2493 | 0 | record (2493) | array (2493); array length 0–0 (mean 0.0) |
| AllowedToDelegate[] |  | 2493 | 0 | 0 | 2493 | 0 | parent record; parent có element 0/2493, parent không có element 2493/2493, parent key missing 0 |  |
| HasSIDHistory | array | 2493 | 0 | 0 | 2493 | 0 | record (2493) | array (2493); array length 0–0 (mean 0.0) |
| HasSIDHistory[] |  | 2493 | 0 | 0 | 2493 | 0 | parent record; parent có element 0/2493, parent không có element 2493/2493, parent key missing 0 |  |
| ObjectIdentifier | string | 2493 | 0 | 0 | 0 | 2493 | record (2493) | SID-like string: S-<redacted> (2493) |
| PrimaryGroupSid | string | 2493 | 0 | 0 | 0 | 2493 | record (2493) | SID-like string: S-<redacted> (2493) |
| Properties | object | 2493 | 0 | 0 | 0 | 2493 | record (2493) | object keys: [admincount, description, displayname, distinguishedname, domain, dontreqpreauth, email, enabled, hasspn, highvalue, homedirectory, lastlogon, lastlogontimestamp, name, objectid, passwordnotreqd, pwdlastset, pwdneverexpires, sensitive, serviceprincipalnames, sidhistory, title, unconstraineddelegation, userpassword] (2493) |
| Properties.admincount | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2491); boolean: true (2) |
| Properties.description | string | 2493 | 0 | 0 | 0 | 2493 | record (2493) | composite/domain-like string: <redacted> (2472); string (21) |
| Properties.displayname | null, string | 2493 | 0 | 4 | 0 | 2489 | record (2493) | null (4); string (2489) |
| Properties.distinguishedname | string | 2493 | 0 | 0 | 0 | 2493 | record (2493) | DN-like string: <redacted distinguished name> (2493) |
| Properties.domain | string | 2493 | 0 | 0 | 0 | 2493 | record (2493) | composite/domain-like string: <redacted> (2493) |
| Properties.dontreqpreauth | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2317); boolean: true (176) |
| Properties.email | null | 2493 | 0 | 2493 | 0 | 0 | record (2493) | null (2493) |
| Properties.enabled | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (3); boolean: true (2490) |
| Properties.hasspn | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2442); boolean: true (51) |
| Properties.highvalue | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2493) |
| Properties.homedirectory | null | 2493 | 0 | 2493 | 0 | 0 | record (2493) | null (2493) |
| Properties.lastlogon | integer | 2493 | 0 | 0 | 0 | 2493 | record (2493) | integer (2493) |
| Properties.lastlogontimestamp | integer | 2493 | 0 | 0 | 0 | 2493 | record (2493) | integer (2493) |
| Properties.name | string | 2493 | 0 | 0 | 0 | 2493 | record (2493) | composite/domain-like string: <redacted> (2493) |
| Properties.objectid | string | 2493 | 0 | 0 | 0 | 2493 | record (2493) | SID-like string: S-<redacted> (2493) |
| Properties.passwordnotreqd | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2491); boolean: true (2) |
| Properties.pwdlastset | integer | 2493 | 0 | 0 | 0 | 2493 | record (2493) | integer (2493) |
| Properties.pwdneverexpires | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2490); boolean: true (3) |
| Properties.sensitive | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2493) |
| Properties.serviceprincipalnames | array | 2493 | 0 | 0 | 2442 | 51 | record (2493) | array (2493); array length 0–1 (mean 0.020457) |
| Properties.serviceprincipalnames[] | string | 2493 | 0 | 0 | 2442 | 51 | parent record; parent có element 51/2493, parent không có element 2442/2493, parent key missing 0 | string (51) |
| Properties.sidhistory | array | 2493 | 0 | 0 | 2493 | 0 | record (2493) | array (2493); array length 0–0 (mean 0.0) |
| Properties.sidhistory[] |  | 2493 | 0 | 0 | 2493 | 0 | parent record; parent có element 0/2493, parent không có element 2493/2493, parent key missing 0 |  |
| Properties.title | null | 2493 | 0 | 2493 | 0 | 0 | record (2493) | null (2493) |
| Properties.unconstraineddelegation | boolean | 2493 | 0 | 0 | 0 | 2493 | record (2493) | boolean: false (2493) |
| Properties.userpassword | null | 2493 | 0 | 2493 | 0 | 0 | record (2493) | null (2493) |
| SPNTargets | array | 2493 | 0 | 0 | 2493 | 0 | record (2493) | array (2493); array length 0–0 (mean 0.0) |
| SPNTargets[] |  | 2493 | 0 | 0 | 2493 | 0 | parent record; parent có element 0/2493, parent không có element 2493/2493, parent key missing 0 |  |

### Điều snapshot cho phép và không cho phép kết luận

Snapshot cho phép nói collector đã xuất record/field/reference với shape và cardinality đã đo.
Snapshot không tự phân biệt successful empty, access denied, method not run, schema absent hay incomplete collection khi không có status/error evidence.

## 6. `groups.json` — Group

### File này biểu diễn cái gì?

File này chứa các object mà collector phân loại là Group.
Mỗi record là một Group object và có thể bao gồm `Members` để mô tả membership trực tiếp cùng `Aces` mô tả quyền được collector normalize trên Group hiện tại.

### Cấu trúc envelope và một record

File được đọc qua `snapshot:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812/20210920185958_groups.json`, mã hóa `UTF-8 with BOM`, collection key `groups`, gồm `550` record.
Top-level keys: `groups, meta`.

Group record là parent/container ở góc nhìn của `Members`: phần tử trong `Members[]` trỏ tới principal child.
Nếu child là Group khác thì raw shape có thể biểu diễn group nesting; không tự nói về attack behavior.

### Các field chính

`ObjectIdentifier` và container `Properties` dùng quy ước semantic chung ở §4; phần này tập trung vào các subfield và primitive có ý nghĩa riêng cho object kind này.

### Các `Properties.*` quan trọng

Bảng dưới đây là phần giải thích ngữ nghĩa cấp Tier B; mọi con số vẫn lấy từ inventory đã xác minh.

| Field con | Quan sát | Ý nghĩa được dùng trong tài liệu | Không được suy ra |
| --- | --- | --- | --- |
| `admincount` | kiểu `boolean`, có mặt 546/550 record gốc, thiếu 4, `null` 0, rỗng 0, không rỗng 546; boolean: false; boolean: true | Cờ thuộc tính mà collector xuất ra cho trạng thái `adminCount` của object. Nó là tín hiệu directory/collector, không phải bản đồ đầy đủ về đặc quyền hiệu lực. | Không tự chứng minh object là quản trị viên hay mọi quyền của object đã được thu thập. |
| `description` | kiểu `string`, có mặt 546/550 record gốc, thiếu 4, `null` 0, rỗng 0, không rỗng 546; composite/domain-like string: <redacted>; string | Thuộc tính mô tả của object; giá trị có thể là chuỗi hoặc `null` trong snapshot. | Không phải bằng chứng về trạng thái vận hành hay quyền hạn. |
| `distinguishedname` | kiểu `string`, có mặt 546/550 record gốc, thiếu 4, `null` 0, rỗng 0, không rỗng 546; DN-like string: <redacted distinguished name> | Tên phân biệt (DN) mà collector xuất cho object trong namespace directory. | Không tự chứng minh object còn tồn tại, có thể truy cập, hay DN là định danh canonical của project. |
| `domain` | kiểu `string`, có mặt 550/550 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 550; composite/domain-like string: <redacted> | Thông tin domain gắn với object trong output của collector. | Không tự chứng minh trust, membership, hay hướng trust giữa các domain. |
| `highvalue` | kiểu `boolean`, có mặt 546/550 record gốc, thiếu 4, `null` 0, rỗng 0, không rỗng 546; boolean: false; boolean: true | Nhãn phân loại giá trị cao mà BloodHound/collector gắn cho object. | Không phải bằng chứng độc lập về quyền Windows hay khả năng khai thác. |
| `name` | kiểu `string`, có mặt 550/550 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 550; composite/domain-like string: <redacted> | Tên hoặc display identity mà collector dùng để mô tả object; giá trị thực tế được auditor redacted. | Không nên dùng làm identity key, vì có thể chứa tên hiển thị, format composite hoặc không duy nhất. |
| `objectid` | kiểu `string`, có mặt 546/550 record gốc, thiếu 4, `null` 0, rỗng 0, không rỗng 546; SID-like string: S-<redacted>; composite/domain-like string: <redacted> | Bản sao identity property do collector đặt trong `Properties`; trong nhiều record tương ứng với định danh object. | Không nên gộp mặc định với top-level `ObjectIdentifier` mà bỏ qua duplicate/scope behavior. |

#### `Members[]`

**Quan sát từ snapshot**

- `Group.Members` có kiểu `array`, có mặt 550/550 record gốc, thiếu 0, `null` 0, rỗng 5, không rỗng 545.
- Dạng giá trị đại diện đã sanitize: array (550).

**Tầng 1 — Biểu diễn raw**

Mảng trong record Group; mỗi phần tử là object có `MemberId` và `MemberType`.

**Tầng 2 — Ý nghĩa ở collector**

Collector ghi nhận principal là thành viên trực tiếp của Group hiện tại.
Với `MemberType=Group`, phần tử có thể là group nesting.

**Tầng 3 — Diễn giải của project**

Raw membership observation → candidate direct `MemberOf` structural evidence.
Bước project interpretation vẫn phải giữ direction và reconciliation policy.

**Field này chứng minh:** G có một reference trực tiếp tới principal P khi phần tử chứa `MemberId=P`.

**Field này không chứng minh:** transitive membership, effective authorization, attack path, hay quyền runtime.

**Mức độ chắc chắn:** Cao cho quan sát direct membership; trung bình cho semantics downstream.

**Nguồn giải thích:** Raw snapshot; group/member schema của SharpHound; [SpecterOps group members](https://bloodhound.specterops.io/reference/groups/get-group-entity-members).

**Cách đọc một phần tử:** nếu record Group có identifier `G` và `Members = [{MemberId: U, MemberType: User}]`, câu raw-data tương ứng là: “collector ghi nhận principal `U` là thành viên trực tiếp của Group `G`”.
Nếu `MemberType=Group`, câu tương ứng là “collector ghi nhận Group `U` là thành viên trực tiếp của Group `G`”, tức một nesting observation.

**Các subfield của `Members[]`:**

`MemberId` là reference tới principal child, không phải tên hiển thị.
`MemberType` là nhãn object kind do collector xuất cho reference đó.
Vì vậy raw container/reference được đọc theo hướng parent Group → member principal.
Đây không phải canonical graph direction: sau khi resolve `MemberId`, project materialize direct `MemberOf` theo `member principal → containing Group` như ADR-0009/Attack Semantics quy định.
Không được tự mở rộng thành transitive membership hay attack behavior.

| Đường dẫn field | Quan sát đo được | Field biểu diễn gì | Chứng minh được | Không chứng minh được | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| `Members[].MemberId` | kiểu `string`, đã kiểm tra 13324 array element; field có mặt trong 13324/13324 element; field thiếu trong 0 element; parent records có element: 545/550; parent records không có element: 5/550, `null` 0, rỗng 0, không rỗng 13324; SID-like string: S-<redacted>; composite/domain-like string: <redacted> | Định danh của principal được collector ghi nhận là thành viên trực tiếp của Group hiện tại. | một membership reference từ Group hiện tại tới principal P; exact-match có thể resolve P trong snapshot. | full group closure, effective authorization, hay quyền runtime. | Reference string được sanitize; unresolved reference không bị gán nhãn external. |
| `Members[].MemberType` | kiểu `string`, đã kiểm tra 13324 array element; field có mặt trong 13324/13324 element; field thiếu trong 0 element; parent records có element: 545/550; parent records không có element: 5/550, `null` 0, rỗng 0, không rỗng 13324; category: Computer; category: Group; category: User | Loại object mà collector gắn cho principal được tham chiếu. | cách phân loại principal để đọc reference, ví dụ `User`, `Group` hoặc `Computer`. | identity duy nhất hoặc sự tồn tại của target nếu không resolve được identifier. | Giá trị categorical được thống kê riêng trong inventory. |

**Bảng giá trị `MemberType`:**

| Giá trị | Cách đọc |
| --- | --- |
| `User` | reference trỏ tới object được collector phân loại là User. |
| `Group` | reference trỏ tới Group; trong `Members[]` có thể biểu diễn group nesting. |
| `Computer` | reference trỏ tới Computer object. |

### Giá trị categorical và cách đọc

| Field phân loại | Giá trị quan sát | Cách đọc ở tầng raw |
| --- | --- | --- |
| `Aces[].PrincipalType` | `Computer` (1184), `Group` (5874), `User` (459) | Loại object mà collector gắn cho trustee/principal trong ACE; không thay thế việc resolve SID. |
| `Aces[].RightName` | `GenericAll` (5269), `GenericWrite` (568), `Owner` (544), `WriteDacl` (568), `WriteOwner` (568) | Nhãn quyền đã được collector normalize; không phải raw Windows access mask. |
| `Members[].MemberType` | `Computer` (43), `Group` (295), `User` (12986) | Loại object mà collector gắn cho principal được tham chiếu; `Group` có thể là group nesting nếu nằm trong `Members[]`. |

### Bảng kiểm kê từng field

Bảng sau là phép đo đầy đủ; nó không thay thế phần giải thích ngữ nghĩa ở trên.

| Đường dẫn field | Kiểu quan sát được | Present count | Missing count | Null count | Empty count | Non-empty count | Counting unit / scope | Dạng giá trị đại diện |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Aces | array | 550 | 0 | 0 | 4 | 546 | record (550) | array (550); array length 0–19 (mean 13.667273) |
| Aces[] | object | 550 | 0 | 0 | 4 | 546 | parent record; parent có element 546/550, parent không có element 4/550, parent key missing 0 | object keys: [AceType, IsInherited, PrincipalSID, PrincipalType, RightName] (7517) |
| Aces[].AceType | string | 7517 | 0 | 0 | 7517 | 0 | array element; examined 7517, parent có element 546/550, parent không có element 4/550 | empty string (7517) |
| Aces[].IsInherited | boolean | 7517 | 0 | 0 | 0 | 7517 | array element; examined 7517, parent có element 546/550, parent không có element 4/550 | boolean: false (1713); boolean: true (5804) |
| Aces[].PrincipalSID | string | 7517 | 0 | 0 | 0 | 7517 | array element; examined 7517, parent có element 546/550, parent không có element 4/550 | SID-like string: S-<redacted> (5293); composite/domain-like string: <redacted> (2224) |
| Aces[].PrincipalType | string | 7517 | 0 | 0 | 0 | 7517 | array element; examined 7517, parent có element 546/550, parent không có element 4/550 | category: Computer (1184); category: Group (5874); category: User (459) |
| Aces[].RightName | string | 7517 | 0 | 0 | 0 | 7517 | array element; examined 7517, parent có element 546/550, parent không có element 4/550 | category: GenericAll (5269); category: GenericWrite (568); category: Owner (544); category: WriteDacl (568); category: WriteOwner (568) |
| Members | array | 550 | 0 | 0 | 5 | 545 | record (550) | array (550); array length 0–46 (mean 24.225455) |
| Members[] | object | 550 | 0 | 0 | 5 | 545 | parent record; parent có element 545/550, parent không có element 5/550, parent key missing 0 | object keys: [MemberId, MemberType] (13324) |
| Members[].MemberId | string | 13324 | 0 | 0 | 0 | 13324 | array element; examined 13324, parent có element 545/550, parent không có element 5/550 | SID-like string: S-<redacted> (13319); composite/domain-like string: <redacted> (5) |
| Members[].MemberType | string | 13324 | 0 | 0 | 0 | 13324 | array element; examined 13324, parent có element 545/550, parent không có element 5/550 | category: Computer (43); category: Group (295); category: User (12986) |
| ObjectIdentifier | string | 550 | 0 | 0 | 0 | 550 | record (550) | SID-like string: S-<redacted> (519); composite/domain-like string: <redacted> (31) |
| Properties | object | 550 | 0 | 0 | 0 | 550 | record (550) | object keys: [admincount, description, distinguishedname, domain, highvalue, name, objectid] (546); object keys: [domain, name] (4) |
| Properties.admincount | boolean | 546 | 4 | 0 | 0 | 546 | record (550) | boolean: false (535); boolean: true (11) |
| Properties.description | string | 546 | 4 | 0 | 0 | 546 | record (550) | composite/domain-like string: <redacted> (513); string (33) |
| Properties.distinguishedname | string | 546 | 4 | 0 | 0 | 546 | record (550) | DN-like string: <redacted distinguished name> (546) |
| Properties.domain | string | 550 | 0 | 0 | 0 | 550 | record (550) | composite/domain-like string: <redacted> (550) |
| Properties.highvalue | boolean | 546 | 4 | 0 | 0 | 546 | record (550) | boolean: false (538); boolean: true (8) |
| Properties.name | string | 550 | 0 | 0 | 0 | 550 | record (550) | composite/domain-like string: <redacted> (550) |
| Properties.objectid | string | 546 | 4 | 0 | 0 | 546 | record (550) | SID-like string: S-<redacted> (519); composite/domain-like string: <redacted> (27) |

### Điều snapshot cho phép và không cho phép kết luận

Snapshot cho phép nói collector đã xuất record/field/reference với shape và cardinality đã đo.
Snapshot không tự phân biệt successful empty, access denied, method not run, schema absent hay incomplete collection khi không có status/error evidence.

## 7. `computers.json` — Computer

### File này biểu diễn cái gì?

File này chứa các object mà collector phân loại là Computer.
Record có cả thuộc tính account/host và các primitive host-scoped như local-group membership, RDP/PowerShell membership-shaped arrays, ACL và session collection.

### Cấu trúc envelope và một record

File được đọc qua `snapshot:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812/20210920185958_computers.json`, mã hóa `UTF-8 with BOM`, collection key `computers`, gồm `100` record.
Top-level keys: `computers, meta`.

Computer record luôn là scope của host hiện tại.
Một principal xuất hiện trong array của Computer C trước hết phải được đọc là observation gắn với C, không phải relationship toàn cục.

### Các field chính

`ObjectIdentifier` và container `Properties` dùng quy ước semantic chung ở §4; phần này tập trung vào các subfield và primitive có ý nghĩa riêng cho object kind này.

### Các `Properties.*` quan trọng

Bảng dưới đây là phần giải thích ngữ nghĩa cấp Tier B; mọi con số vẫn lấy từ inventory đã xác minh.

| Field con | Quan sát | Ý nghĩa được dùng trong tài liệu | Không được suy ra |
| --- | --- | --- | --- |
| `description` | kiểu `null, string`, có mặt 100/100 record gốc, thiếu 0, `null` 1, rỗng 0, không rỗng 99; composite/domain-like string: <redacted>; null | Thuộc tính mô tả của object; giá trị có thể là chuỗi hoặc `null` trong snapshot. | Không phải bằng chứng về trạng thái vận hành hay quyền hạn. |
| `distinguishedname` | kiểu `string`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; DN-like string: <redacted distinguished name> | Tên phân biệt (DN) mà collector xuất cho object trong namespace directory. | Không tự chứng minh object còn tồn tại, có thể truy cập, hay DN là định danh canonical của project. |
| `domain` | kiểu `string`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; composite/domain-like string: <redacted> | Thông tin domain gắn với object trong output của collector. | Không tự chứng minh trust, membership, hay hướng trust giữa các domain. |
| `enabled` | kiểu `boolean`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; boolean: true | Cờ enabled/disabled được collector lấy từ thuộc tính account hoặc object. | Không đồng nghĩa với việc account đang đăng nhập được, service đang chạy, hay network path hoạt động. |
| `haslaps` | kiểu `boolean`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; boolean: false | Giá trị boolean được collector xuất cho field `haslaps`; snapshot này quan sát `false`. | Không đủ để kết luận trạng thái triển khai LAPS hay nguyên nhân của giá trị `false`. |
| `highvalue` | kiểu `boolean`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; boolean: false | Nhãn phân loại giá trị cao mà BloodHound/collector gắn cho object. | Không phải bằng chứng độc lập về quyền Windows hay khả năng khai thác. |
| `lastlogontimestamp` | kiểu `integer`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; integer | Giá trị integer timestamp-like tương ứng với thuộc tính logon timestamp mà collector xuất. | Không đủ để khẳng định thời điểm đăng nhập chính xác; unit, replication lag và `0` cần evidence riêng. |
| `name` | kiểu `string`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; composite/domain-like string: <redacted> | Tên hoặc display identity mà collector dùng để mô tả object; giá trị thực tế được auditor redacted. | Không nên dùng làm identity key, vì có thể chứa tên hiển thị, format composite hoặc không duy nhất. |
| `objectid` | kiểu `string`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; SID-like string: S-<redacted> | Bản sao identity property do collector đặt trong `Properties`; trong nhiều record tương ứng với định danh object. | Không nên gộp mặc định với top-level `ObjectIdentifier` mà bỏ qua duplicate/scope behavior. |
| `operatingsystem` | kiểu `null, string`, có mặt 100/100 record gốc, thiếu 0, `null` 99, rỗng 0, không rỗng 1; null; string | Chuỗi OS nếu collector quan sát được; snapshot có phần lớn giá trị `null`. | Không chứng minh host đang online hoặc endpoint đã join domain thực sự. |
| `pwdlastset` | kiểu `integer`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; integer | Giá trị integer timestamp-like mà collector xuất cho lần đặt mật khẩu. | Auditor chưa xác minh unit/timezone và không suy diễn `0`, stale hay khả năng đăng nhập. |
| `serviceprincipalnames` | kiểu `array`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 91, không rỗng 9; array | Mảng các SPN string mà collector quan sát trên object; có thể rỗng hoặc không rỗng. | Không tự chứng minh service đang chạy, ticket có thể lấy được, hay account có thể bị compromise. |
| `unconstraineddelegation` | kiểu `boolean`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100; boolean: false; boolean: true | Cờ delegation do collector xuất cho object. | Không tự chứng minh một ticket, session, hay attack đã xảy ra. |

#### `PrimaryGroupSid`

**Quan sát từ snapshot**

- `Computer.PrimaryGroupSid` có kiểu `string`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 100.
- Dạng giá trị đại diện đã sanitize: SID-like string: S-<redacted> (100).

**Tầng 1 — Biểu diễn raw**

Chuỗi SID-like ở top-level record; trong snapshot field này có mặt ở User và Computer.

**Tầng 2 — Ý nghĩa ở collector**

Collector xuất SID của primary group gắn với object theo schema.

**Tầng 3 — Diễn giải của project**

Đây là primary-group reference evidence, không phải danh sách toàn bộ group membership.

**Field này chứng minh:** một reference-shaped SID tới primary group của object.

**Field này không chứng minh:** membership đầy đủ, quyền hiệu lực, hay canonical `MemberOf` closure.

**Mức độ chắc chắn:** Cao cho raw reference; semantics membership cần policy AD riêng.

**Nguồn giải thích:** Raw snapshot; Windows/AD primary-group semantics cần đối chiếu riêng.

#### `LocalAdmins[]`

**Quan sát từ snapshot**

- `Computer.LocalAdmins[]` có kiểu `object`, parent key có mặt 100/100 record, parent key thiếu 0, parent có element 1, parent không có element 99, `null` 0, rỗng 99, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: object keys: [MemberId, MemberType] (5).

**Tầng 1 — Biểu diễn raw**

Mảng trong record Computer C; phần tử là principal reference có `MemberId` và `MemberType`.

**Tầng 2 — Ý nghĩa ở collector**

SharpHound/collector query membership của local Administrators group trên host C và xuất principal P theo primitive local-group enumeration.

**Tầng 3 — Diễn giải của project**

Raw host-scoped local Administrators membership evidence.
Theo ADR-0003/#80, positive resolved membership là canonical `AdminTo` structural evidence; network/service reachability vẫn là runtime predicate.

**Field này chứng minh:** P được collector ghi nhận trong local Administrators của C và, sau identity/host resolution, có thể materialize positive `AdminTo` theo accepted policy.

**Field này không chứng minh:** host online, một management channel đang khả dụng, arbitrary SYSTEM execution, hay attack thành công.

**Mức độ chắc chắn:** Cao cho raw membership và accepted positive `AdminTo` mapping; empty/completeness semantics vẫn cần tri-state handling.

**Nguồn giải thích:** Raw snapshot; [SpecterOps computer admins](https://bloodhound.specterops.io/reference/computers/get-computer-entity-admins) và collector implementation/schema.

#### `DcomUsers[]`

**Quan sát từ snapshot**

- `Computer.DcomUsers[]` có kiểu `object`, parent key có mặt 100/100 record, parent key thiếu 0, parent có element 1, parent không có element 99, `null` 0, rỗng 99, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: object keys: [MemberId, MemberType] (1).

**Tầng 1 — Biểu diễn raw**

Mảng nằm trong record Computer C; element là principal reference theo shape raw quan sát được.

**Tầng 2 — Ý nghĩa ở collector**

Collector ghi nhận principal trong local Distributed COM Users group của host C.

**Tầng 3 — Diễn giải của project**

Đây là host-scoped local-group membership evidence.
BloodHound có primitive/relationship tương ứng, nhưng project không coi riêng raw membership này là đủ cho canonical relationship.

**Field này chứng minh:** P được collector ghi nhận trong primitive DCOM Users của C.

**Field này không chứng minh:** DCOM service state, remote activation thành công, effective access, hay attack behavior.

**Mức độ chắc chắn:** Cao cho raw membership; canonical promotion cần structural policy.

**Nguồn giải thích:** Raw snapshot; [SpecterOps computer DCOM users](https://bloodhound.specterops.io/reference/computers/get-computer-entity-dcom-users) và collector implementation/schema.

#### `RemoteDesktopUsers[]`

**Quan sát từ snapshot**

- `Computer.RemoteDesktopUsers[]` có kiểu `object`, parent key có mặt 100/100 record, parent key thiếu 0, parent có element 1, parent không có element 99, `null` 0, rỗng 99, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: object keys: [MemberId, MemberType] (3).

**Tầng 1 — Biểu diễn raw**

Mảng nằm trong Computer C; mỗi phần tử tham chiếu principal và có `MemberType`.

**Tầng 2 — Ý nghĩa ở collector**

Collector ghi nhận membership thu được từ local Remote Desktop Users group trên host C.

**Tầng 3 — Diễn giải của project**

BloodHound truyền thống sử dụng primitive này cho `CanRDP`, nhưng project hiện tại không coi riêng membership này là đủ cho canonical `CanRDP`; cần giữ tách biệt với user-right assignment và các predicate khác.

**Field này chứng minh:** P xuất hiện trong primitive Remote Desktop Users của C.

**Field này không chứng minh:** `SeRemoteInteractiveLogonRight`, absence of `SeDenyRemoteInteractiveLogonRight`, service state, TCP reachability, authentication success, hoặc canonical `CanRDP`.

**Mức độ chắc chắn:** Cao cho raw membership/host scope; chưa đủ cho canonical access semantics.

**Nguồn giải thích:** Raw snapshot; [SpecterOps computer RDP users](https://bloodhound.specterops.io/reference/computers/get-computer-entity-rdp-users) và collector implementation/schema.
[Microsoft account rights](https://learn.microsoft.com/en-us/windows/win32/secauthz/account-rights-constants) chỉ dùng để đối chiếu các quyền Windows liên quan tới RDP.

#### `PSRemoteUsers[]`

**Quan sát từ snapshot**

- `Computer.PSRemoteUsers[]` có kiểu `object`, parent key có mặt 100/100 record, parent key thiếu 0, parent có element 1, parent không có element 99, `null` 0, rỗng 99, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: object keys: [MemberId, MemberType] (2).

**Tầng 1 — Biểu diễn raw**

Mảng nằm trong Computer C; phần tử là principal reference.

**Tầng 2 — Ý nghĩa ở collector**

Collector ghi nhận membership thu được từ local Remote Management Users group trên host C, là primitive liên quan tới PowerShell remoting.

**Tầng 3 — Diễn giải của project**

ADR-0003/#80 chấp nhận positive effective Remote Management Users membership làm BloodHound-compatible structural evidence cho `CanPSRemote`.

**Field này chứng minh:** P xuất hiện trong local Remote Management Users membership evidence của C và, sau identity/host resolution, có thể materialize modeled `CanPSRemote` theo accepted policy.

**Field này không chứng minh:** custom endpoint ACL cho phép P, WinRM service/listener đang chạy, network reachability, authentication thành công, hay remoting command thành công.

**Mức độ chắc chắn:** Cao cho raw membership và modeled structural `CanPSRemote`; custom endpoint/runtime execution cần evidence riêng.

**Nguồn giải thích:** Raw snapshot; [SpecterOps CanPSRemote](https://bloodhound.specterops.io/resources/edges/can-ps-remote) và collector implementation/schema.

#### `Sessions[]`

**Quan sát từ snapshot**

- `Computer.Sessions` có kiểu `array`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 100, không rỗng 0.
- Dạng giá trị đại diện đã sanitize: array (100).

**Tầng 1 — Biểu diễn raw**

Mảng nằm trong Computer C.
Snapshot hiện tại có field ở cả 100 Computer record nhưng không có phần tử.

**Tầng 2 — Ý nghĩa ở collector**

Collector dành field cho session-shaped observations gắn với host C; không có element thực tế để xác minh subfield/direction trong snapshot này.

**Tầng 3 — Diễn giải của project**

Không có session evidence để map thành `HasSession`; empty không được coi là negative runtime fact.

**Field này chứng minh:** snapshot không quan sát element session nào trong các record Computer.

**Field này không chứng minh:** không có session tồn tại, credential exposure, observed activity, hay absence of logon.

**Mức độ chắc chắn:** Cao cho empty measurement; Unknown cho collection completeness.

**Nguồn giải thích:** Raw snapshot; collector documentation và collector implementation/schema.

#### `AllowedToDelegate[]`

**Quan sát từ snapshot**

- `Computer.AllowedToDelegate` có kiểu `array`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 100, không rỗng 0.
- Dạng giá trị đại diện đã sanitize: array (100).

**Tầng 1 — Biểu diễn raw**

Mảng delegation-shaped; trong User và Computer snapshot đều hiện diện nhưng rỗng.

**Tầng 2 — Ý nghĩa ở collector**

Collector dành field cho delegation target/principal references; snapshot không có element để xác minh shape cụ thể.

**Tầng 3 — Diễn giải của project**

Không tạo delegation edge ở Phase 1; chỉ ghi nhận collection rỗng.

**Field này chứng minh:** field có mặt và không có element quan sát được.

**Field này không chứng minh:** delegation không tồn tại, method đã chạy đầy đủ, hay một kỹ thuật tấn công.

**Mức độ chắc chắn:** Cao cho empty; Unknown cho nguyên nhân empty.

**Nguồn giải thích:** Raw snapshot; collector documentation và collector implementation/schema.

#### `AllowedToAct[]`

**Quan sát từ snapshot**

- `Computer.AllowedToAct` có kiểu `array`, có mặt 100/100 record gốc, thiếu 0, `null` 0, rỗng 100, không rỗng 0.
- Dạng giá trị đại diện đã sanitize: array (100).

**Tầng 1 — Biểu diễn raw**

Mảng delegation-shaped trong Computer; tất cả record Computer quan sát được đều rỗng.

**Tầng 2 — Ý nghĩa ở collector**

Tên field phù hợp với primitive delegation nhưng raw snapshot rỗng nên không đủ evidence để xác minh semantics cụ thể.

**Tầng 3 — Diễn giải của project**

Không tạo RBCD/delegation edge và không sửa canonical behavior.

**Field này chứng minh:** field có mặt nhưng không có element.

**Field này không chứng minh:** RBCD không tồn tại hoặc collector đã kiểm tra đầy đủ.

**Mức độ chắc chắn:** Cao cho raw empty; Unknown cho collection status.

**Nguồn giải thích:** Raw snapshot; collector documentation và collector implementation/schema.

**Direction của `Sessions[]`:** nếu tương lai có record dạng Computer `C` chứa session reference tới User `U`, raw reading tối thiểu là “collector quan sát một session/reference liên quan tới `U` trên `C`”.
Đây là host-scoped observation; không được đọc thành “U có credential để dump” hay “đã có attack”.

`DcomUsers[]` có xuất hiện ở một Computer và đã được giải thích như host-scoped membership-shaped evidence.
`PrivilegedSessions` và `RegistrySessions` không xuất hiện trong các record Computer của verified snapshot; việc không có key này không được đọc thành collection âm hoặc chứng minh không có session tương ứng.

### Giá trị categorical và cách đọc

| Field phân loại | Giá trị quan sát | Cách đọc ở tầng raw |
| --- | --- | --- |
| `Aces[].PrincipalType` | `Computer` (312), `Group` (927), `User` (347) | Loại object mà collector gắn cho trustee/principal trong ACE; không thay thế việc resolve SID. |
| `Aces[].RightName` | `GenericAll` (1186), `GenericWrite` (100), `Owner` (100), `WriteDacl` (100), `WriteOwner` (100) | Nhãn quyền đã được collector normalize; không phải raw Windows access mask. |
| `DcomUsers[].MemberType` | `User` (1) | Loại object mà collector gắn cho principal được tham chiếu; `Group` có thể là group nesting nếu nằm trong `Members[]`. |
| `LocalAdmins[].MemberType` | `Group` (2), `User` (3) | Loại object mà collector gắn cho principal được tham chiếu; `Group` có thể là group nesting nếu nằm trong `Members[]`. |
| `PSRemoteUsers[].MemberType` | `User` (2) | Loại object mà collector gắn cho principal được tham chiếu; `Group` có thể là group nesting nếu nằm trong `Members[]`. |
| `RemoteDesktopUsers[].MemberType` | `User` (3) | Loại object mà collector gắn cho principal được tham chiếu; `Group` có thể là group nesting nếu nằm trong `Members[]`. |

### Bảng kiểm kê từng field

Bảng sau là phép đo đầy đủ; nó không thay thế phần giải thích ngữ nghĩa ở trên.

| Đường dẫn field | Kiểu quan sát được | Present count | Missing count | Null count | Empty count | Non-empty count | Counting unit / scope | Dạng giá trị đại diện |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Aces | array | 100 | 0 | 0 | 0 | 100 | record (100) | array (100); array length 13–20 (mean 15.86) |
| Aces[] | object | 100 | 0 | 0 | 0 | 100 | parent record; parent có element 100/100, parent không có element 0/100, parent key missing 0 | object keys: [AceType, IsInherited, PrincipalSID, PrincipalType, RightName] (1586) |
| Aces[].AceType | string | 1586 | 0 | 0 | 1586 | 0 | array element; examined 1586, parent có element 100/100, parent không có element 0/100 | empty string (1586) |
| Aces[].IsInherited | boolean | 1586 | 0 | 0 | 0 | 1586 | array element; examined 1586, parent có element 100/100, parent không có element 0/100 | boolean: false (299); boolean: true (1287) |
| Aces[].PrincipalSID | string | 1586 | 0 | 0 | 0 | 1586 | array element; examined 1586, parent có element 100/100, parent không có element 0/100 | SID-like string: S-<redacted> (1179); composite/domain-like string: <redacted> (407) |
| Aces[].PrincipalType | string | 1586 | 0 | 0 | 0 | 1586 | array element; examined 1586, parent có element 100/100, parent không có element 0/100 | category: Computer (312); category: Group (927); category: User (347) |
| Aces[].RightName | string | 1586 | 0 | 0 | 0 | 1586 | array element; examined 1586, parent có element 100/100, parent không có element 0/100 | category: GenericAll (1186); category: GenericWrite (100); category: Owner (100); category: WriteDacl (100); category: WriteOwner (100) |
| AllowedToAct | array | 100 | 0 | 0 | 100 | 0 | record (100) | array (100); array length 0–0 (mean 0.0) |
| AllowedToAct[] |  | 100 | 0 | 0 | 100 | 0 | parent record; parent có element 0/100, parent không có element 100/100, parent key missing 0 |  |
| AllowedToDelegate | array | 100 | 0 | 0 | 100 | 0 | record (100) | array (100); array length 0–0 (mean 0.0) |
| AllowedToDelegate[] |  | 100 | 0 | 0 | 100 | 0 | parent record; parent có element 0/100, parent không có element 100/100, parent key missing 0 |  |
| DcomUsers | array | 100 | 0 | 0 | 99 | 1 | record (100) | array (100); array length 0–1 (mean 0.01) |
| DcomUsers[] | object | 100 | 0 | 0 | 99 | 1 | parent record; parent có element 1/100, parent không có element 99/100, parent key missing 0 | object keys: [MemberId, MemberType] (1) |
| DcomUsers[].MemberId | string | 1 | 0 | 0 | 0 | 1 | array element; examined 1, parent có element 1/100, parent không có element 99/100 | SID-like string: S-<redacted> (1) |
| DcomUsers[].MemberType | string | 1 | 0 | 0 | 0 | 1 | array element; examined 1, parent có element 1/100, parent không có element 99/100 | category: User (1) |
| LocalAdmins | array | 100 | 0 | 0 | 99 | 1 | record (100) | array (100); array length 0–5 (mean 0.05) |
| LocalAdmins[] | object | 100 | 0 | 0 | 99 | 1 | parent record; parent có element 1/100, parent không có element 99/100, parent key missing 0 | object keys: [MemberId, MemberType] (5) |
| LocalAdmins[].MemberId | string | 5 | 0 | 0 | 0 | 5 | array element; examined 5, parent có element 1/100, parent không có element 99/100 | SID-like string: S-<redacted> (5) |
| LocalAdmins[].MemberType | string | 5 | 0 | 0 | 0 | 5 | array element; examined 5, parent có element 1/100, parent không có element 99/100 | category: Group (2); category: User (3) |
| ObjectIdentifier | string | 100 | 0 | 0 | 0 | 100 | record (100) | SID-like string: S-<redacted> (100) |
| PSRemoteUsers | array | 100 | 0 | 0 | 99 | 1 | record (100) | array (100); array length 0–2 (mean 0.02) |
| PSRemoteUsers[] | object | 100 | 0 | 0 | 99 | 1 | parent record; parent có element 1/100, parent không có element 99/100, parent key missing 0 | object keys: [MemberId, MemberType] (2) |
| PSRemoteUsers[].MemberId | string | 2 | 0 | 0 | 0 | 2 | array element; examined 2, parent có element 1/100, parent không có element 99/100 | SID-like string: S-<redacted> (2) |
| PSRemoteUsers[].MemberType | string | 2 | 0 | 0 | 0 | 2 | array element; examined 2, parent có element 1/100, parent không có element 99/100 | category: User (2) |
| PrimaryGroupSid | string | 100 | 0 | 0 | 0 | 100 | record (100) | SID-like string: S-<redacted> (100) |
| Properties | object | 100 | 0 | 0 | 0 | 100 | record (100) | object keys: [description, distinguishedname, domain, enabled, haslaps, highvalue, lastlogontimestamp, name, objectid, operatingsystem, pwdlastset, serviceprincipalnames, unconstraineddelegation] (100) |
| Properties.description | null, string | 100 | 0 | 1 | 0 | 99 | record (100) | composite/domain-like string: <redacted> (99); null (1) |
| Properties.distinguishedname | string | 100 | 0 | 0 | 0 | 100 | record (100) | DN-like string: <redacted distinguished name> (100) |
| Properties.domain | string | 100 | 0 | 0 | 0 | 100 | record (100) | composite/domain-like string: <redacted> (100) |
| Properties.enabled | boolean | 100 | 0 | 0 | 0 | 100 | record (100) | boolean: true (100) |
| Properties.haslaps | boolean | 100 | 0 | 0 | 0 | 100 | record (100) | boolean: false (100) |
| Properties.highvalue | boolean | 100 | 0 | 0 | 0 | 100 | record (100) | boolean: false (100) |
| Properties.lastlogontimestamp | integer | 100 | 0 | 0 | 0 | 100 | record (100) | integer (100) |
| Properties.name | string | 100 | 0 | 0 | 0 | 100 | record (100) | composite/domain-like string: <redacted> (100) |
| Properties.objectid | string | 100 | 0 | 0 | 0 | 100 | record (100) | SID-like string: S-<redacted> (100) |
| Properties.operatingsystem | null, string | 100 | 0 | 99 | 0 | 1 | record (100) | null (99); string (1) |
| Properties.pwdlastset | integer | 100 | 0 | 0 | 0 | 100 | record (100) | integer (100) |
| Properties.serviceprincipalnames | array | 100 | 0 | 0 | 91 | 9 | record (100) | array (100); array length 0–22 (mean 0.3) |
| Properties.serviceprincipalnames[] | string | 100 | 0 | 0 | 91 | 9 | parent record; parent có element 9/100, parent không có element 91/100, parent key missing 0 | composite/domain-like string: <redacted> (16); string (14) |
| Properties.unconstraineddelegation | boolean | 100 | 0 | 0 | 0 | 100 | record (100) | boolean: false (99); boolean: true (1) |
| RemoteDesktopUsers | array | 100 | 0 | 0 | 99 | 1 | record (100) | array (100); array length 0–3 (mean 0.03) |
| RemoteDesktopUsers[] | object | 100 | 0 | 0 | 99 | 1 | parent record; parent có element 1/100, parent không có element 99/100, parent key missing 0 | object keys: [MemberId, MemberType] (3) |
| RemoteDesktopUsers[].MemberId | string | 3 | 0 | 0 | 0 | 3 | array element; examined 3, parent có element 1/100, parent không có element 99/100 | SID-like string: S-<redacted> (3) |
| RemoteDesktopUsers[].MemberType | string | 3 | 0 | 0 | 0 | 3 | array element; examined 3, parent có element 1/100, parent không có element 99/100 | category: User (3) |
| Sessions | array | 100 | 0 | 0 | 100 | 0 | record (100) | array (100); array length 0–0 (mean 0.0) |
| Sessions[] |  | 100 | 0 | 0 | 100 | 0 | parent record; parent có element 0/100, parent không có element 100/100, parent key missing 0 |  |

### Điều snapshot cho phép và không cho phép kết luận

Snapshot cho phép nói collector đã xuất record/field/reference với shape và cardinality đã đo.
Snapshot không tự phân biệt successful empty, access denied, method not run, schema absent hay incomplete collection khi không có status/error evidence.

## 8. `ous.json` — OU

### File này biểu diễn cái gì?

File này chứa các object mà collector phân loại là Organizational Unit (OU).
Record mô tả container trong hierarchy, các object member/reference, GPO link và ACL của OU.

### Cấu trúc envelope và một record

File được đọc qua `snapshot:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812/20210920185958_ous.json`, mã hóa `UTF-8 with BOM`, collection key `ous`, gồm `223` record.
Top-level keys: `meta, ous`.

OU record là một node/container directory.
`ChildOus`, `Users`, `Computers` và `Links` là các reference/hierarchy evidence; chúng không tự tạo resultant policy hoặc quyền hiệu lực.

### Các field chính

`ObjectIdentifier` và container `Properties` dùng quy ước semantic chung ở §4; phần này tập trung vào các subfield và primitive có ý nghĩa riêng cho object kind này.

### Các `Properties.*` quan trọng

Bảng dưới đây là phần giải thích ngữ nghĩa cấp Tier B; mọi con số vẫn lấy từ inventory đã xác minh.

| Field con | Quan sát | Ý nghĩa được dùng trong tài liệu | Không được suy ra |
| --- | --- | --- | --- |
| `blocksinheritance` | kiểu `boolean`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 223; boolean: false | Cờ mô tả trạng thái chặn kế thừa chính sách trên OU theo dữ liệu collector xuất ra. | Không tự tạo ra resultant policy và không thay thế việc tính thứ tự/enforced của GPO. |
| `description` | kiểu `null, string`, có mặt 223/223 record gốc, thiếu 0, `null` 172, rỗng 0, không rỗng 51; null; string | Thuộc tính mô tả của object; giá trị có thể là chuỗi hoặc `null` trong snapshot. | Không phải bằng chứng về trạng thái vận hành hay quyền hạn. |
| `distinguishedname` | kiểu `string`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 223; DN-like string: <redacted distinguished name> | Tên phân biệt (DN) mà collector xuất cho object trong namespace directory. | Không tự chứng minh object còn tồn tại, có thể truy cập, hay DN là định danh canonical của project. |
| `domain` | kiểu `string`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 223; composite/domain-like string: <redacted> | Thông tin domain gắn với object trong output của collector. | Không tự chứng minh trust, membership, hay hướng trust giữa các domain. |
| `highvalue` | kiểu `boolean`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 223; boolean: false | Nhãn phân loại giá trị cao mà BloodHound/collector gắn cho object. | Không phải bằng chứng độc lập về quyền Windows hay khả năng khai thác. |
| `name` | kiểu `string`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 223; composite/domain-like string: <redacted> | Tên hoặc display identity mà collector dùng để mô tả object; giá trị thực tế được auditor redacted. | Không nên dùng làm identity key, vì có thể chứa tên hiển thị, format composite hoặc không duy nhất. |
| `objectid` | kiểu `string`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 223; GUID-like string | Bản sao identity property do collector đặt trong `Properties`; trong nhiều record tương ứng với định danh object. | Không nên gộp mặc định với top-level `ObjectIdentifier` mà bỏ qua duplicate/scope behavior. |

#### `ChildOus[]`

**Quan sát từ snapshot**

- `OU.ChildOus` có kiểu `array`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 179, không rỗng 44.
- Dạng giá trị đại diện đã sanitize: array (223).

**Tầng 1 — Biểu diễn raw**

Mảng các identifier/reference tới OU con trong record OU/Domain.

**Tầng 2 — Ý nghĩa ở collector**

Collector biểu diễn hierarchy reference; nếu O có `ChildOus=[O2]`, raw reading là O2 được ghi nhận là OU con trực tiếp của O.

**Tầng 3 — Diễn giải của project**

Candidate directory hierarchy evidence; không tự tính full transitive containment.

**Field này chứng minh:** reference/hierarchy observation giữa parent record và child OU.

**Field này không chứng minh:** mọi descendant, inheritance policy, hay effective permission.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

#### `Users[]`

**Quan sát từ snapshot**

- `OU.Users` có kiểu `array`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 223.
- Dạng giá trị đại diện đã sanitize: array (223).

**Tầng 1 — Biểu diễn raw**

Mảng identifier/reference tới User trong OU/Domain record.

**Tầng 2 — Ý nghĩa ở collector**

Collector xuất các User reference thuộc scope container đó.

**Tầng 3 — Diễn giải của project**

Candidate containment/scope evidence; không tự chứng minh logon, policy application hoặc privilege.

**Field này chứng minh:** record container chứa reference User.

**Field này không chứng minh:** User đang active, toàn bộ membership, hay resultant GPO.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

#### `Computers[]`

**Quan sát từ snapshot**

- `OU.Computers` có kiểu `array`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 144, không rỗng 79.
- Dạng giá trị đại diện đã sanitize: array (223).

**Tầng 1 — Biểu diễn raw**

Mảng identifier/reference tới Computer trong OU record; Domain array hiện diện nhưng rỗng.

**Tầng 2 — Ý nghĩa ở collector**

Collector xuất Computer reference gắn với container.

**Tầng 3 — Diễn giải của project**

Candidate OU/container scope evidence; không tự chứng minh host online hay policy hiệu lực.

**Field này chứng minh:** Computer được snapshot biểu diễn trong collection của container.

**Field này không chứng minh:** network reachability, current OU membership ngoài snapshot, hay resultant policy.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

#### `Links[]`

**Quan sát từ snapshot**

- `OU.Links` có kiểu `array`, có mặt 223/223 record gốc, thiếu 0, `null` 0, rỗng 222, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: array (223).

**Tầng 1 — Biểu diễn raw**

Mảng object gồm `Guid` và `IsEnforced` trong OU/Domain record.

**Tầng 2 — Ý nghĩa ở collector**

Collector biểu diễn GPO link gắn với container; `Guid` là reference-shaped GPO identifier và `IsEnforced` là thuộc tính link được xuất.

**Tầng 3 — Diễn giải của project**

Candidate link/scope evidence; cần tách GPO tồn tại, link, policy settings và resultant policy.

**Field này chứng minh:** container có một link object tới GPO theo GUID đã quan sát.

**Field này không chứng minh:** policy setting cụ thể đã áp dụng lên User/Computer hay thứ tự xử lý đầy đủ.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

### Giá trị categorical và cách đọc

| Field phân loại | Giá trị quan sát | Cách đọc ở tầng raw |
| --- | --- | --- |
| `Aces[].PrincipalType` | `Computer` (227), `Group` (1388), `User` (21) | Loại object mà collector gắn cho trustee/principal trong ACE; không thay thế việc resolve SID. |
| `Aces[].RightName` | `GenericAll` (965), `Owner` (223), `WriteDacl` (224), `WriteOwner` (224) | Nhãn quyền đã được collector normalize; không phải raw Windows access mask. |

### Bảng kiểm kê từng field

Bảng sau là phép đo đầy đủ; nó không thay thế phần giải thích ngữ nghĩa ở trên.

| Đường dẫn field | Kiểu quan sát được | Present count | Missing count | Null count | Empty count | Non-empty count | Counting unit / scope | Dạng giá trị đại diện |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| ACLProtected | boolean | 223 | 0 | 0 | 0 | 223 | record (223) | boolean: false (223) |
| Aces | array | 223 | 0 | 0 | 0 | 223 | record (223) | array (223); array length 7–10 (mean 7.336323) |
| Aces[] | object | 223 | 0 | 0 | 0 | 223 | parent record; parent có element 223/223, parent không có element 0/223, parent key missing 0 | object keys: [AceType, IsInherited, PrincipalSID, PrincipalType, RightName] (1636) |
| Aces[].AceType | string | 1636 | 0 | 0 | 1636 | 0 | array element; examined 1636, parent có element 223/223, parent không có element 0/223 | empty string (1636) |
| Aces[].IsInherited | boolean | 1636 | 0 | 0 | 0 | 1636 | array element; examined 1636, parent có element 223/223, parent không có element 0/223 | boolean: false (447); boolean: true (1189) |
| Aces[].PrincipalSID | string | 1636 | 0 | 0 | 0 | 1636 | array element; examined 1636, parent có element 223/223, parent không có element 0/223 | SID-like string: S-<redacted> (1190); composite/domain-like string: <redacted> (446) |
| Aces[].PrincipalType | string | 1636 | 0 | 0 | 0 | 1636 | array element; examined 1636, parent có element 223/223, parent không có element 0/223 | category: Computer (227); category: Group (1388); category: User (21) |
| Aces[].RightName | string | 1636 | 0 | 0 | 0 | 1636 | array element; examined 1636, parent có element 223/223, parent không có element 0/223 | category: GenericAll (965); category: Owner (223); category: WriteDacl (224); category: WriteOwner (224) |
| ChildOus | array | 223 | 0 | 0 | 179 | 44 | record (223) | array (223); array length 0–14 (mean 0.955157) |
| ChildOus[] | string | 223 | 0 | 0 | 179 | 44 | parent record; parent có element 44/223, parent không có element 179/223, parent key missing 0 | GUID-like string (213) |
| Computers | array | 223 | 0 | 0 | 144 | 79 | record (223) | array (223); array length 0–3 (mean 0.44843) |
| Computers[] | string | 223 | 0 | 0 | 144 | 79 | parent record; parent có element 79/223, parent không có element 144/223, parent key missing 0 | SID-like string: S-<redacted> (100) |
| DcomUsers | array | 223 | 0 | 0 | 223 | 0 | record (223) | array (223); array length 0–0 (mean 0.0) |
| DcomUsers[] |  | 223 | 0 | 0 | 223 | 0 | parent record; parent có element 0/223, parent không có element 223/223, parent key missing 0 |  |
| Links | array | 223 | 0 | 0 | 222 | 1 | record (223) | array (223); array length 0–1 (mean 0.004484) |
| Links[] | object | 223 | 0 | 0 | 222 | 1 | parent record; parent có element 1/223, parent không có element 222/223, parent key missing 0 | object keys: [Guid, IsEnforced] (1) |
| Links[].Guid | string | 1 | 0 | 0 | 0 | 1 | array element; examined 1, parent có element 1/223, parent không có element 222/223 | GUID-like string (1) |
| Links[].IsEnforced | boolean | 1 | 0 | 0 | 0 | 1 | array element; examined 1, parent có element 1/223, parent không có element 222/223 | boolean: false (1) |
| LocalAdmins | array | 223 | 0 | 0 | 223 | 0 | record (223) | array (223); array length 0–0 (mean 0.0) |
| LocalAdmins[] |  | 223 | 0 | 0 | 223 | 0 | parent record; parent có element 0/223, parent không có element 223/223, parent key missing 0 |  |
| ObjectIdentifier | string | 223 | 0 | 0 | 0 | 223 | record (223) | GUID-like string (223) |
| PSRemoteUsers | array | 223 | 0 | 0 | 223 | 0 | record (223) | array (223); array length 0–0 (mean 0.0) |
| PSRemoteUsers[] |  | 223 | 0 | 0 | 223 | 0 | parent record; parent có element 0/223, parent không có element 223/223, parent key missing 0 |  |
| Properties | object | 223 | 0 | 0 | 0 | 223 | record (223) | object keys: [blocksinheritance, description, distinguishedname, domain, highvalue, name, objectid] (223) |
| Properties.blocksinheritance | boolean | 223 | 0 | 0 | 0 | 223 | record (223) | boolean: false (223) |
| Properties.description | null, string | 223 | 0 | 172 | 0 | 51 | record (223) | null (172); string (51) |
| Properties.distinguishedname | string | 223 | 0 | 0 | 0 | 223 | record (223) | DN-like string: <redacted distinguished name> (223) |
| Properties.domain | string | 223 | 0 | 0 | 0 | 223 | record (223) | composite/domain-like string: <redacted> (223) |
| Properties.highvalue | boolean | 223 | 0 | 0 | 0 | 223 | record (223) | boolean: false (223) |
| Properties.name | string | 223 | 0 | 0 | 0 | 223 | record (223) | composite/domain-like string: <redacted> (223) |
| Properties.objectid | string | 223 | 0 | 0 | 0 | 223 | record (223) | GUID-like string (223) |
| RemoteDesktopUsers | array | 223 | 0 | 0 | 223 | 0 | record (223) | array (223); array length 0–0 (mean 0.0) |
| RemoteDesktopUsers[] |  | 223 | 0 | 0 | 223 | 0 | parent record; parent có element 0/223, parent không có element 223/223, parent key missing 0 |  |
| Users | array | 223 | 0 | 0 | 0 | 223 | record (223) | array (223); array length 2–21 (mean 11.161435) |
| Users[] | string | 223 | 0 | 0 | 0 | 223 | parent record; parent có element 223/223, parent không có element 0/223, parent key missing 0 | SID-like string: S-<redacted> (2489) |

### Điều snapshot cho phép và không cho phép kết luận

Snapshot cho phép nói collector đã xuất record/field/reference với shape và cardinality đã đo.
Snapshot không tự phân biệt successful empty, access denied, method not run, schema absent hay incomplete collection khi không có status/error evidence.

## 9. `gpos.json` — GPO

### File này biểu diễn cái gì?

File này chứa Group Policy Object mà collector quan sát trong AD.
Record mô tả GPO object, ACL và một số thuộc tính như `gpcpath`; việc link tới domain/OU được thể hiện ở container record.

### Cấu trúc envelope và một record

File được đọc qua `snapshot:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812/20210920185958_gpos.json`, mã hóa `UTF-8 with BOM`, collection key `gpos`, gồm `2` record.
Top-level keys: `gpos, meta`.

GPO tồn tại, GPO được link, nội dung policy và resultant policy trên host là bốn khái niệm khác nhau.
Snapshot Phase 1 chỉ chứng minh phần record/reference đã xuất.

### Các field chính

`ObjectIdentifier` và container `Properties` dùng quy ước semantic chung ở §4; phần này tập trung vào các subfield và primitive có ý nghĩa riêng cho object kind này.

### Các `Properties.*` quan trọng

Bảng dưới đây là phần giải thích ngữ nghĩa cấp Tier B; mọi con số vẫn lấy từ inventory đã xác minh.

| Field con | Quan sát | Ý nghĩa được dùng trong tài liệu | Không được suy ra |
| --- | --- | --- | --- |
| `description` | kiểu `null`, có mặt 2/2 record gốc, thiếu 0, `null` 2, rỗng 0, không rỗng 0; null | Thuộc tính mô tả của object; giá trị có thể là chuỗi hoặc `null` trong snapshot. | Không phải bằng chứng về trạng thái vận hành hay quyền hạn. |
| `distinguishedname` | kiểu `string`, có mặt 2/2 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2; DN-like string: <redacted distinguished name> | Tên phân biệt (DN) mà collector xuất cho object trong namespace directory. | Không tự chứng minh object còn tồn tại, có thể truy cập, hay DN là định danh canonical của project. |
| `domain` | kiểu `string`, có mặt 2/2 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2; composite/domain-like string: <redacted> | Thông tin domain gắn với object trong output của collector. | Không tự chứng minh trust, membership, hay hướng trust giữa các domain. |
| `gpcpath` | kiểu `string`, có mặt 2/2 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2; composite/domain-like string: <redacted> | Đường dẫn UNC tới Group Policy Template (GPT) của GPO trong SYSVOL; đây là phần filesystem của GPO, không phải đường dẫn tới Group Policy Container (GPC) trong Active Directory. | Collector xuất reference tới vị trí GPT mà GPO dùng để lưu policy files; field này không tự chứa toàn bộ policy settings. |
| `highvalue` | kiểu `boolean`, có mặt 2/2 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2; boolean: false | Nhãn phân loại giá trị cao mà BloodHound/collector gắn cho object. | Không phải bằng chứng độc lập về quyền Windows hay khả năng khai thác. |
| `name` | kiểu `string`, có mặt 2/2 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2; composite/domain-like string: <redacted> | Tên hoặc display identity mà collector dùng để mô tả object; giá trị thực tế được auditor redacted. | Không nên dùng làm identity key, vì có thể chứa tên hiển thị, format composite hoặc không duy nhất. |
| `objectid` | kiểu `string`, có mặt 2/2 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 2; GUID-like string | Bản sao identity property do collector đặt trong `Properties`; trong nhiều record tương ứng với định danh object. | Không nên gộp mặc định với top-level `ObjectIdentifier` mà bỏ qua duplicate/scope behavior. |

**Phân biệt bốn khái niệm:** record GPO tồn tại trong AD; `Links[]` ở OU/Domain ghi nhận scope link; policy settings là nội dung policy; resultant policy là kết quả sau hierarchy, inheritance, enforced/blocking và xử lý trên client.
Snapshot Phase 1 chỉ đo hai lớp đầu khi reference có mặt.

### Giá trị categorical và cách đọc

| Field phân loại | Giá trị quan sát | Cách đọc ở tầng raw |
| --- | --- | --- |
| `Aces[].PrincipalType` | `Group` (20) | Loại object mà collector gắn cho trustee/principal trong ACE; không thay thế việc resolve SID. |
| `Aces[].RightName` | `GenericWrite` (6), `Owner` (2), `WriteDacl` (6), `WriteOwner` (6) | Nhãn quyền đã được collector normalize; không phải raw Windows access mask. |

### Bảng kiểm kê từng field

Bảng sau là phép đo đầy đủ; nó không thay thế phần giải thích ngữ nghĩa ở trên.

| Đường dẫn field | Kiểu quan sát được | Present count | Missing count | Null count | Empty count | Non-empty count | Counting unit / scope | Dạng giá trị đại diện |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Aces | array | 2 | 0 | 0 | 0 | 2 | record (2) | array (2); array length 10–10 (mean 10.0) |
| Aces[] | object | 2 | 0 | 0 | 0 | 2 | parent record; parent có element 2/2, parent không có element 0/2, parent key missing 0 | object keys: [AceType, IsInherited, PrincipalSID, PrincipalType, RightName] (20) |
| Aces[].AceType | string | 20 | 0 | 0 | 20 | 0 | array element; examined 20, parent có element 2/2, parent không có element 0/2 | empty string (20) |
| Aces[].IsInherited | boolean | 20 | 0 | 0 | 0 | 20 | array element; examined 20, parent có element 2/2, parent không có element 0/2 | boolean: false (20) |
| Aces[].PrincipalSID | string | 20 | 0 | 0 | 0 | 20 | array element; examined 20, parent có element 2/2, parent không có element 0/2 | SID-like string: S-<redacted> (20) |
| Aces[].PrincipalType | string | 20 | 0 | 0 | 0 | 20 | array element; examined 20, parent có element 2/2, parent không có element 0/2 | category: Group (20) |
| Aces[].RightName | string | 20 | 0 | 0 | 0 | 20 | array element; examined 20, parent có element 2/2, parent không có element 0/2 | category: GenericWrite (6); category: Owner (2); category: WriteDacl (6); category: WriteOwner (6) |
| ObjectIdentifier | string | 2 | 0 | 0 | 0 | 2 | record (2) | GUID-like string (2) |
| Properties | object | 2 | 0 | 0 | 0 | 2 | record (2) | object keys: [description, distinguishedname, domain, gpcpath, highvalue, name, objectid] (2) |
| Properties.description | null | 2 | 0 | 2 | 0 | 0 | record (2) | null (2) |
| Properties.distinguishedname | string | 2 | 0 | 0 | 0 | 2 | record (2) | DN-like string: <redacted distinguished name> (2) |
| Properties.domain | string | 2 | 0 | 0 | 0 | 2 | record (2) | composite/domain-like string: <redacted> (2) |
| Properties.gpcpath | string | 2 | 0 | 0 | 0 | 2 | record (2) | composite/domain-like string: <redacted> (2) |
| Properties.highvalue | boolean | 2 | 0 | 0 | 0 | 2 | record (2) | boolean: false (2) |
| Properties.name | string | 2 | 0 | 0 | 0 | 2 | record (2) | composite/domain-like string: <redacted> (2) |
| Properties.objectid | string | 2 | 0 | 0 | 0 | 2 | record (2) | GUID-like string (2) |

### Điều snapshot cho phép và không cho phép kết luận

Snapshot cho phép nói collector đã xuất record/field/reference với shape và cardinality đã đo.
Snapshot không tự phân biệt successful empty, access denied, method not run, schema absent hay incomplete collection khi không có status/error evidence.

## 10. `domains.json` — Domain

### File này biểu diễn cái gì?

File này chứa object domain mà collector phân loại là Domain.
Record gom thông tin domain, ACL, user/OU references, GPO links và trust collection nếu có.

### Cấu trúc envelope và một record

File được đọc qua `snapshot:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812/20210920185958_domains.json`, mã hóa `UTF-8 with BOM`, collection key `domains`, gồm `1` record.
Top-level keys: `domains, meta`.

Domain record là source scope cho các array như `ChildOus`, `Users`, `Links`, `Trusts`.
Trong snapshot này `Trusts` có mặt nhưng rỗng, nên không có trust element để diễn giải.

### Các field chính

`ObjectIdentifier` và container `Properties` dùng quy ước semantic chung ở §4; phần này tập trung vào các subfield và primitive có ý nghĩa riêng cho object kind này.

### Các `Properties.*` quan trọng

Bảng dưới đây là phần giải thích ngữ nghĩa cấp Tier B; mọi con số vẫn lấy từ inventory đã xác minh.

| Field con | Quan sát | Ý nghĩa được dùng trong tài liệu | Không được suy ra |
| --- | --- | --- | --- |
| `description` | kiểu `null`, có mặt 1/1 record gốc, thiếu 0, `null` 1, rỗng 0, không rỗng 0; null | Thuộc tính mô tả của object; giá trị có thể là chuỗi hoặc `null` trong snapshot. | Không phải bằng chứng về trạng thái vận hành hay quyền hạn. |
| `distinguishedname` | kiểu `string`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1; DN-like string: <redacted distinguished name> | Tên phân biệt (DN) mà collector xuất cho object trong namespace directory. | Không tự chứng minh object còn tồn tại, có thể truy cập, hay DN là định danh canonical của project. |
| `domain` | kiểu `string`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1; composite/domain-like string: <redacted> | Thông tin domain gắn với object trong output của collector. | Không tự chứng minh trust, membership, hay hướng trust giữa các domain. |
| `functionallevel` | kiểu `string`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1; string | Mức chức năng domain được collector xuất trong record Domain. | Không phải một edge hoặc bằng chứng về quyền của principal. |
| `highvalue` | kiểu `boolean`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1; boolean: true | Nhãn phân loại giá trị cao mà BloodHound/collector gắn cho object. | Không phải bằng chứng độc lập về quyền Windows hay khả năng khai thác. |
| `name` | kiểu `string`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1; composite/domain-like string: <redacted> | Tên hoặc display identity mà collector dùng để mô tả object; giá trị thực tế được auditor redacted. | Không nên dùng làm identity key, vì có thể chứa tên hiển thị, format composite hoặc không duy nhất. |
| `objectid` | kiểu `string`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1; SID-like string: S-<redacted> | Bản sao identity property do collector đặt trong `Properties`; trong nhiều record tương ứng với định danh object. | Không nên gộp mặc định với top-level `ObjectIdentifier` mà bỏ qua duplicate/scope behavior. |

#### `ChildOus[]`

**Quan sát từ snapshot**

- `Domain.ChildOus` có kiểu `array`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: array (1).

**Tầng 1 — Biểu diễn raw**

Mảng các identifier/reference tới OU con trong record OU/Domain.

**Tầng 2 — Ý nghĩa ở collector**

Collector biểu diễn hierarchy reference; nếu O có `ChildOus=[O2]`, raw reading là O2 được ghi nhận là OU con trực tiếp của O.

**Tầng 3 — Diễn giải của project**

Candidate directory hierarchy evidence; không tự tính full transitive containment.

**Field này chứng minh:** reference/hierarchy observation giữa parent record và child OU.

**Field này không chứng minh:** mọi descendant, inheritance policy, hay effective permission.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

#### `Users[]`

**Quan sát từ snapshot**

- `Domain.Users` có kiểu `array`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: array (1).

**Tầng 1 — Biểu diễn raw**

Mảng identifier/reference tới User trong OU/Domain record.

**Tầng 2 — Ý nghĩa ở collector**

Collector xuất các User reference thuộc scope container đó.

**Tầng 3 — Diễn giải của project**

Candidate containment/scope evidence; không tự chứng minh logon, policy application hoặc privilege.

**Field này chứng minh:** record container chứa reference User.

**Field này không chứng minh:** User đang active, toàn bộ membership, hay resultant GPO.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

#### `Computers[]`

**Quan sát từ snapshot**

- `Domain.Computers` có kiểu `array`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 1, không rỗng 0.
- Dạng giá trị đại diện đã sanitize: array (1).

**Tầng 1 — Biểu diễn raw**

Mảng identifier/reference tới Computer trong OU record; Domain array hiện diện nhưng rỗng.

**Tầng 2 — Ý nghĩa ở collector**

Collector xuất Computer reference gắn với container.

**Tầng 3 — Diễn giải của project**

Candidate OU/container scope evidence; không tự chứng minh host online hay policy hiệu lực.

**Field này chứng minh:** Computer được snapshot biểu diễn trong collection của container.

**Field này không chứng minh:** network reachability, current OU membership ngoài snapshot, hay resultant policy.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

#### `Links[]`

**Quan sát từ snapshot**

- `Domain.Links` có kiểu `array`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 0, không rỗng 1.
- Dạng giá trị đại diện đã sanitize: array (1).

**Tầng 1 — Biểu diễn raw**

Mảng object gồm `Guid` và `IsEnforced` trong OU/Domain record.

**Tầng 2 — Ý nghĩa ở collector**

Collector biểu diễn GPO link gắn với container; `Guid` là reference-shaped GPO identifier và `IsEnforced` là thuộc tính link được xuất.

**Tầng 3 — Diễn giải của project**

Candidate link/scope evidence; cần tách GPO tồn tại, link, policy settings và resultant policy.

**Field này chứng minh:** container có một link object tới GPO theo GUID đã quan sát.

**Field này không chứng minh:** policy setting cụ thể đã áp dụng lên User/Computer hay thứ tự xử lý đầy đủ.

**Mức độ chắc chắn:** Cao cho raw reference; trung bình cho hierarchy/policy semantics.

**Nguồn giải thích:** Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).

#### `Trusts[]`

**Quan sát từ snapshot**

- `Domain.Trusts` có kiểu `array`, có mặt 1/1 record gốc, thiếu 0, `null` 0, rỗng 1, không rỗng 0.
- Dạng giá trị đại diện đã sanitize: array (1).

**Tầng 1 — Biểu diễn raw**

Mảng nằm trong Domain record; snapshot hiện tại có field nhưng độ dài bằng 0.

**Tầng 2 — Ý nghĩa ở collector**

Khi có element, collector thường dùng cấu trúc này để xuất trust relationship giữa source domain hiện tại và target domain/reference; nhưng snapshot này không có element để xác minh key/value cụ thể.

**Tầng 3 — Diễn giải của project**

Không dựng trust edge, không đoán direction/type/SID filtering từ field name hoặc empty array.

**Field này chứng minh:** chỉ chứng minh field Trusts hiện diện và không có trust element được quan sát trong bytes này.

**Field này không chứng minh:** không có trust, trust bị disabled, method không chạy, hay collection thành công rỗng.

**Mức độ chắc chắn:** Cao cho empty measurement; Unknown cho trust completeness.

**Nguồn giải thích:** Raw snapshot; [Microsoft trusted domain information](https://learn.microsoft.com/en-us/windows/win32/api/ntsecapi/ns-ntsecapi-trusted_domain_information_ex); [MS-ADTS trustDirection](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/5026a939-44ba-47b2-99cf-386a9e674b04).

**Direction semantics cần giữ cho phase sau:** nếu Trusts có source domain `D1` và target `D2`, các nhãn inbound/outbound phải được đọc tương đối với phía đang chứa record; `inbound` và `outbound` không phải nhãn tuyệt đối độc lập với source.
Microsoft mô tả `bidirectional` là cả hai chiều.
Vì snapshot hiện tại không có element, đây là policy đọc cho dữ liệu tương lai, không phải observation của SEAMLESS.

### Giá trị categorical và cách đọc

| Field phân loại | Giá trị quan sát | Cách đọc ở tầng raw |
| --- | --- | --- |
| `Aces[].AceType` | `All` (2), `GetChanges` (3), `GetChangesAll` (2) | Giá trị phân loại an toàn được ghi nhận; ý nghĩa đầy đủ cần đọc cùng container field. |
| `Aces[].PrincipalType` | `Group` (13) | Loại object mà collector gắn cho trustee/principal trong ACE; không thay thế việc resolve SID. |
| `Aces[].RightName` | `ExtendedRight` (7), `GenericAll` (1), `Owner` (1), `WriteDacl` (2), `WriteOwner` (2) | Nhãn quyền đã được collector normalize; không phải raw Windows access mask. |

### Bảng kiểm kê từng field

Bảng sau là phép đo đầy đủ; nó không thay thế phần giải thích ngữ nghĩa ở trên.

| Đường dẫn field | Kiểu quan sát được | Present count | Missing count | Null count | Empty count | Non-empty count | Counting unit / scope | Dạng giá trị đại diện |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Aces | array | 1 | 0 | 0 | 0 | 1 | record (1) | array (1); array length 13–13 (mean 13.0) |
| Aces[] | object | 1 | 0 | 0 | 0 | 1 | parent record; parent có element 1/1, parent không có element 0/1, parent key missing 0 | object keys: [AceType, IsInherited, PrincipalSID, PrincipalType, RightName] (13) |
| Aces[].AceType | string | 13 | 0 | 0 | 6 | 7 | array element; examined 13, parent có element 1/1, parent không có element 0/1 | category: All (2); category: GetChanges (3); category: GetChangesAll (2); empty string (6) |
| Aces[].IsInherited | boolean | 13 | 0 | 0 | 0 | 13 | array element; examined 13, parent có element 1/1, parent không có element 0/1 | boolean: false (13) |
| Aces[].PrincipalSID | string | 13 | 0 | 0 | 0 | 13 | array element; examined 13, parent có element 1/1, parent không có element 0/1 | SID-like string: S-<redacted> (6); composite/domain-like string: <redacted> (7) |
| Aces[].PrincipalType | string | 13 | 0 | 0 | 0 | 13 | array element; examined 13, parent có element 1/1, parent không có element 0/1 | category: Group (13) |
| Aces[].RightName | string | 13 | 0 | 0 | 0 | 13 | array element; examined 13, parent có element 1/1, parent không có element 0/1 | category: ExtendedRight (7); category: GenericAll (1); category: Owner (1); category: WriteDacl (2); category: WriteOwner (2) |
| ChildOus | array | 1 | 0 | 0 | 0 | 1 | record (1) | array (1); array length 10–10 (mean 10.0) |
| ChildOus[] | string | 1 | 0 | 0 | 0 | 1 | parent record; parent có element 1/1, parent không có element 0/1, parent key missing 0 | GUID-like string (10) |
| Computers | array | 1 | 0 | 0 | 1 | 0 | record (1) | array (1); array length 0–0 (mean 0.0) |
| Computers[] |  | 1 | 0 | 0 | 1 | 0 | parent record; parent có element 0/1, parent không có element 1/1, parent key missing 0 |  |
| DcomUsers | array | 1 | 0 | 0 | 1 | 0 | record (1) | array (1); array length 0–0 (mean 0.0) |
| DcomUsers[] |  | 1 | 0 | 0 | 1 | 0 | parent record; parent có element 0/1, parent không có element 1/1, parent key missing 0 |  |
| Links | array | 1 | 0 | 0 | 0 | 1 | record (1) | array (1); array length 1–1 (mean 1.0) |
| Links[] | object | 1 | 0 | 0 | 0 | 1 | parent record; parent có element 1/1, parent không có element 0/1, parent key missing 0 | object keys: [Guid, IsEnforced] (1) |
| Links[].Guid | string | 1 | 0 | 0 | 0 | 1 | array element; examined 1, parent có element 1/1, parent không có element 0/1 | GUID-like string (1) |
| Links[].IsEnforced | boolean | 1 | 0 | 0 | 0 | 1 | array element; examined 1, parent có element 1/1, parent không có element 0/1 | boolean: false (1) |
| LocalAdmins | array | 1 | 0 | 0 | 1 | 0 | record (1) | array (1); array length 0–0 (mean 0.0) |
| LocalAdmins[] |  | 1 | 0 | 0 | 1 | 0 | parent record; parent có element 0/1, parent không có element 1/1, parent key missing 0 |  |
| ObjectIdentifier | string | 1 | 0 | 0 | 0 | 1 | record (1) | SID-like string: S-<redacted> (1) |
| PSRemoteUsers | array | 1 | 0 | 0 | 1 | 0 | record (1) | array (1); array length 0–0 (mean 0.0) |
| PSRemoteUsers[] |  | 1 | 0 | 0 | 1 | 0 | parent record; parent có element 0/1, parent không có element 1/1, parent key missing 0 |  |
| Properties | object | 1 | 0 | 0 | 0 | 1 | record (1) | object keys: [description, distinguishedname, domain, functionallevel, highvalue, name, objectid] (1) |
| Properties.description | null | 1 | 0 | 1 | 0 | 0 | record (1) | null (1) |
| Properties.distinguishedname | string | 1 | 0 | 0 | 0 | 1 | record (1) | DN-like string: <redacted distinguished name> (1) |
| Properties.domain | string | 1 | 0 | 0 | 0 | 1 | record (1) | composite/domain-like string: <redacted> (1) |
| Properties.functionallevel | string | 1 | 0 | 0 | 0 | 1 | record (1) | string (1) |
| Properties.highvalue | boolean | 1 | 0 | 0 | 0 | 1 | record (1) | boolean: true (1) |
| Properties.name | string | 1 | 0 | 0 | 0 | 1 | record (1) | composite/domain-like string: <redacted> (1) |
| Properties.objectid | string | 1 | 0 | 0 | 0 | 1 | record (1) | SID-like string: S-<redacted> (1) |
| RemoteDesktopUsers | array | 1 | 0 | 0 | 1 | 0 | record (1) | array (1); array length 0–0 (mean 0.0) |
| RemoteDesktopUsers[] |  | 1 | 0 | 0 | 1 | 0 | parent record; parent có element 0/1, parent không có element 1/1, parent key missing 0 |  |
| Trusts | array | 1 | 0 | 0 | 1 | 0 | record (1) | array (1); array length 0–0 (mean 0.0) |
| Trusts[] |  | 1 | 0 | 0 | 1 | 0 | parent record; parent có element 0/1, parent không có element 1/1, parent key missing 0 |  |
| Users | array | 1 | 0 | 0 | 0 | 1 | record (1) | array (1); array length 4–4 (mean 4.0) |
| Users[] | string | 1 | 0 | 0 | 0 | 1 | parent record; parent có element 1/1, parent không có element 0/1, parent key missing 0 | SID-like string: S-<redacted> (4) |

### Điều snapshot cho phép và không cho phép kết luận

Snapshot cho phép nói collector đã xuất record/field/reference với shape và cardinality đã đo.
Snapshot không tự phân biệt successful empty, access denied, method not run, schema absent hay incomplete collection khi không có status/error evidence.

## 11. Khảo cổ identity/reference giữa các file

Có `3369` record và `3368` identifier unique; không có record thiếu `ObjectIdentifier`, không có identifier xuất hiện ở nhiều object kind khác nhau.
Có một duplicate identifier group trong Group, được giữ lại bằng safe locator chứ không merge.

Auditor nhận diện `71786` scalar observation có hình dạng reference; `71784` exact-match một `ObjectIdentifier` trong snapshot và `2` chưa match.
Hai observation unresolved đều nằm ở `Group.Members[].MemberId`; chúng được gọi là unresolved, không tự gắn nhãn external, boundary, dangling hay invalid.

Các reference được đo gồm `Members[].MemberId`, ACE principal, `PrimaryGroupSid`, host-local membership references, `ChildOus[]`, `Users[]`, `Computers[]` và `Links[].Guid`.
Matching là exact string matching trên snapshot; chưa có canonicalization hay identity resolution.

### Dạng `ObjectIdentifier` theo object kind

| Object kind | Dạng | Số record | Số identifier unique | Unique ID được reference | Unique ID chưa được reference |
| --- | --- | ---: | ---: | ---: | ---: |
| `Computer` | `sid-like` | 100 | 100 | 100 | 0 |
| `Domain` | `sid-like` | 1 | 1 | 0 | 1 |
| `GPO` | `guid-like` | 2 | 2 | 2 | 0 |
| `Group` | `domain-like` | 31 | 30 | 8 | 22 |
| `Group` | `sid-like` | 519 | 519 | 154 | 365 |
| `OU` | `guid-like` | 223 | 223 | 223 | 0 |
| `User` | `sid-like` | 2493 | 2493 | 2493 | 0 |

Matching vẫn là exact string matching trên các raw references đã được auditor nhận diện; nó không phải canonicalization hay identity resolution.

### Khảo cổ 31 `Group.ObjectIdentifier` dạng domain-like

Snapshot có `31` record Group dạng domain-like; inventory identity cho thấy `30` identifier unique, trong đó `8` unique ID đã được reference exact-match và `22` chưa được reference bởi field reference candidate.

Có `4` record dạng stub chỉ có `Properties.domain` và `Properties.name`; các record còn lại có tập `Properties` đầy đủ hơn.
Đây là pattern biểu diễn cần giữ lại trong reconciliation, không được tự coi domain-like ID là SID của Group, boundary identity hay invalid record.

| Record index an toàn | Dạng identifier | Tập key `Properties` | Độ dài `Members` | Độ dài `Aces` |
| ---: | --- | --- | ---: | ---: |
| 0 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 1 | 10 |
| 1 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 10 |
| 2 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 5 | 10 |
| 3 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 10 |
| 4 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 5 | 12 |
| 5 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 1 | 12 |
| 6 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 4 | 12 |
| 7 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 1 | 12 |
| 8 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 2 | 12 |
| 9 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 1 | 12 |
| 10 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 2 | 12 |
| 11 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 12 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 13 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 14 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 15 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 1 | 12 |
| 16 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 19 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 2 | 12 |
| 21 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 22 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 2 | 12 |
| 26 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 2 | 12 |
| 30 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 33 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 2 | 10 |
| 34 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 10 |
| 36 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 2 | 12 |
| 37 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 39 | `composite/domain-like string: <redacted>` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 3 | 12 |
| 546 | `composite/domain-like string: <redacted>` | `domain, name` | 1 | 0 |
| 547 | `composite/domain-like string: <redacted>` | `domain, name` | 2 | 0 |
| 548 | `composite/domain-like string: <redacted>` | `domain, name` | 2 | 0 |
| 549 | `composite/domain-like string: <redacted>` | `domain, name` | 0 | 0 |

Các index trong bảng là locator an toàn, không phải identity value.
Snapshot quan sát 30 identifier unique, trong đó 8 identifier có exact-reference và 22 identifier chưa được reference bởi các field candidate; pattern này vẫn không giải quyết được nguồn gốc identity.
Cần đối chiếu collector implementation, object class và boundary policy ở phase sau.

### Khảo cổ duplicate representation

#### Duplicate `Group.ObjectIdentifier` — 2 occurrences

| Record index | Dạng identifier | Tập key record | Tập key `Properties` | Độ dài `Members` | Độ dài `Aces` |
| ---: | --- | --- | --- | ---: | ---: |
| 6 | `composite/domain-like string: <redacted>` | `Aces, Members, ObjectIdentifier, Properties` | `admincount, description, distinguishedname, domain, highvalue, name, objectid` | 4 | 12 |
| 549 | `composite/domain-like string: <redacted>` | `Aces, Members, ObjectIdentifier, Properties` | `domain, name` | 0 | 0 |

Diễn giải: hai record dùng cùng collector identifier nhưng biểu diễn không tương đương về anatomy.
Vì vậy auditor không dùng last-write-wins và không tự merge chúng.

## 12. Missing / null / empty và giới hạn collection

`missing`, `null`, array rỗng và array không rỗng được đo riêng.
Với path là phần tử của array, inventory thêm `parent_records_with_elements`, `parent_records_without_elements`, `parent_records_missing` và một `presence_scope` rõ ràng.
Vì vậy `Computer.LocalAdmins[]` không báo thiếu ở 99 host; nó báo parent array có mặt, có element ở 1 host và không có element ở 99 host.

Không có status/error/access-denied metadata trong raw snapshot.
Vì vậy không được đọc array rỗng thành negative fact.
Đặc biệt, không thể phân biệt “không có quan hệ” với “collector không quan sát được quan hệ” chỉ bằng field hiện tại.

## 13. Consumer hiện tại và phần remediation có giới hạn

`scripts/eda_dataset_analysis.py` hiện đọc `Members`, `Aces`, `LocalAdmins`, `RemoteDesktopUsers`, `PSRemoteUsers` và `Sessions`.
EDA hiện báo cáo `RemoteDesktopUsers[]`, `LocalAdmins[]`, `PSRemoteUsers[]` và `Sessions[]` như các raw/evidence primitive riêng, giữ trạng thái completeness unknown và không dùng `RemoteDesktopUsers[]` để đếm verified `CanRDP`.
Verified `CanRDP` vẫn cần effective RDU membership, `SeRemoteInteractiveLogonRight` và known-negative `SeDenyRemoteInteractiveLogonRight`.
Positive `LocalAdmins[]` và `PSRemoteUsers[]` là host-bound structural evidence theo accepted #80; empty/unobserved arrays không chứng minh relationship absence.
Production parser/builder canonicalization vẫn thuộc #44/#45 và không được triển khai trong remediation EDA này.

## 14. Đầu vào cho các phase tiếp theo của #94

- Dùng manifest và raw bytes này làm source-of-truth bất biến.
- Giữ unresolved member references cho identity/boundary policy riêng.
- Bổ sung collector status/error evidence trước khi diễn giải completeness.
- Đưa các primitive host-scoped vào review #79/#80 nhưng không biến chúng thành canonical edge ở Phase 1.
- Để #44/#45 xử lý parser/host-access semantics sau khi có policy approved; không bypass loader time-provenance decision.
- Dùng #47 cross-dataset comparison chỉ khi provenance, collector scope và semantics được căn chỉnh.
- Windows telemetry, #79 Phase B và remediation graph builder/parser nằm ngoài phạm vi.

## 15. Tái tạo kết quả

```bash
python scripts/audit_seamless_raw.py \
  --raw-dir data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --output reports/generated/seamless-raw-field-inventory.json
```

JSON generated nằm local-only trong `reports/generated/` theo convention repository; tài liệu này chỉ chứa observation đã sanitize và phần giải thích ngữ nghĩa, không chứa raw AD identity.
