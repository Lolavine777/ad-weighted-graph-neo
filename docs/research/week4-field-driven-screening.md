# Từ dữ liệu AD tới các bước tấn công có thể dự đoán

Ngày: 06/10/2026, Asia/Ho_Chi_Minh. Owner: TTS A; reviewer: TTS B. Refs [#200](https://github.com/nairyuuu/ad-weighted-graph/issues/200), [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192).
Baseline mã/tài liệu: `0c44e84b5e7718d71fafe07abb0eb03998dfbacb`, contract 1.3.0, catalog 0.3. Trạng thái: nghiên cứu bổ sung để review; chưa thay engine, contract, catalog hoặc điểm số.

## 1. Kết luận để đọc trước

**Feedback mới yêu cầu sàng lọc từ những gì dữ liệu có thể hỗ trợ, rồi chọn các bước mở đường tới tài sản.** Nhóm đã nghiên cứu sáu họ cơ chế trong [đợt đầu](week4-prediction-evidence.md). Bảng 40 dòng mentor gửi ngày 06/10 là đầu vào để kiểm rộng hơn: có bước tìm thông tin, bước lấy bí mật, bước sử dụng bí mật, bước sửa quyền và bước duy trì truy cập. Không chuyển mỗi dòng thành một cạnh có thể đi qua.

Đợt bổ sung này đối chiếu đủ 40 dòng rồi [tải raw và truy trực tiếp chuỗi](week4-screening-raw-verification.md). **AS-REP giữ ca đầu, RBCD có căn cứ để review kế tiếp**: cùng actor có quyền trên máy đích và enabled SPN User để nghiên cứu lấy service principal. Ca Kerberoasting đã chọn có prefix reset mà 2.490 enabled Users cũng tới được, nên chưa chứng minh mở thêm đường. DCOM có nhánh protocol tới DC chưa được projection; owner/GPO chỉ thấy holders đã đặc quyền. Chưa cam kết integration hoặc đo coverage mới.

**Số cạnh mới không phải tiêu chí nghiệm thu prediction.** Một bước mới chỉ mở thêm khả năng hành động. Nó có thể trùng đường đã biết hoặc không nối tới đích. Giá trị cần kiểm là: từ một điểm xuất phát và năng lực ban đầu, hệ thống tự sinh chuỗi có điều kiện tới tài sản, giải thích khả năng mới sau từng bước và giữ rõ phần chưa biết. Phải đo phần coverage mới trên cùng input/scope; chưa có kết quả đo trong PR tài liệu này.

## 2. Bằng chứng được dùng và giới hạn của lượt kiểm

**Đã tải sáu raw files từ GitHub, verify manifest và chạy lại official audit/parser/probe.** Có 195 field paths, 3.370 nodes, 56.367 edges, 3 assessments unknown, 0 warnings/errors. Pin thực chạy `18887eaacbad18e95938978f7070c820ef1c31fd`; parser/engine/catalog không đổi so với baseline trên. [Raw verification](week4-screening-raw-verification.md) ghi source/checksum/lệnh/locators; không thực hiện exploit hoặc crack.

| Nguồn tại baseline | Dùng để kết luận | Giới hạn |
| --- | --- | --- |
| [Manifest SEAMLESS](../../data/samples/manifests/seamless-raw-v1.json) | Sáu file User/Group/Computer/Domain/OU/GPO, snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` | Đã verify size/hash toàn bộ sáu files; snapshot không là runtime evidence |
| [Kiểm kê raw đã merge](seamless-raw-field-audit.md) | Field, kiểu, missing/null/empty, nhãn ACL, số container có dữ liệu | Audit đã rerun; container có mặt không là điều kiện khai thác |
| [Nghiên cứu đợt đầu](week4-prediction-evidence.md) | Locators/identity closure của AS-REP, Kerberoasting, DCSync và RBCD; vai trò DC | Đã verify lại và bổ sung trace ở raw verification; không là attack success hoặc full access check |
| [Normalizer tại pin](https://github.com/nairyuuu/ad-weighted-graph/blob/0c44e84b5e7718d71fafe07abb0eb03998dfbacb/src/parser/normalizer.py), [builder](https://github.com/nairyuuu/ad-weighted-graph/blob/0c44e84b5e7718d71fafe07abb0eb03998dfbacb/src/parser/builder.py) | Projection node chỉ giữ enabled/admincount/distinguishedname; schema 8 loại quan hệ | Thuộc tính còn trong raw/reconciled không đồng nghĩa evaluator dùng được |
| [Catalog](../../configs/attack_semantics.yml), [search](../../src/engine/search.py), [state](../../src/engine/semantics/state.py) | 13 mục catalog gồm quy tắc thụ động và biến thể scenario; nền đổi DACL, reset, actor handoff, host actions | Không phải 13 kỹ thuật ATT&CK độc lập; chưa có owner/trigger cho roasting hoàn chỉnh |
| [Query contract Week 4](week4-query-contract.md), [scenarios](week4-scenarios.md) | Source/initial identity/context, asset goal, fact-resolution, oracle và coverage | Core vẫn cần implementation/handoff B; không thay bằng demo supplied path |
| Nguồn Microsoft, MITRE và SpecterOps dưới từng mục | Cơ chế/điều kiện để nhóm kiểm ý tưởng do GPT đề xuất | Nguồn cơ chế không cung cấp xác suất, tần suất hay ground truth khai thác SEAMLESS |

Bảng mentor là tài liệu làm việc người dùng chuyển trong phiên 06/10, gồm 40 dòng. Tên dòng và số thứ tự được giữ trong mục 4 để truy ngược; mô tả, ATT&CK mapping và telemetry trong bảng đó chưa được coi là authoritative evidence. Không cần public raw identities, DN, SPN hoặc bí mật để trình bày phép sàng lọc.

## 3. Đi từ field, không từ tên kỹ thuật

**Tách ba câu hỏi: field có mặt không, có dữ liệu có ích không, và engine đã dùng chưa?** Dữ liệu dưới đây đã đối chiếu raw/pipeline trực tiếp; bộ lọc DA/EA/Administrators/DC/RODC/EnterpriseDC không chứng minh ít đặc quyền tuyệt đối nếu actor nằm ngoài; field rỗng/thiếu không là chứng minh khả năng đó không tồn tại ngoài collection scope.

| Nhóm field thực trong input | Quan sát có ích / giới hạn | Các bước có thể đề xuất và phần cần kiểm |
| --- | --- | --- |
| F1: ObjectIdentifier, name/domain, enabled, admincount, PrimaryGroupSid; Group.Members | Có identity/membership để resolve đích; admincount không là đặc quyền hiệu lực | Tìm account/group; nối quyền sau khi có danh tính. Biết account không đồng nghĩa kiểm soát account |
| F2: User.hasspn, serviceprincipalnames | 51 User records có SPN; chưa được projection thành node facts | Request dữ liệu Kerberoasting; cần initial Kerberos auth, KDC/policy và recovery. SPN không chứng minh dịch vụ online |
| F3: User.dontreqpreauth | 176 true; một enabled User tới DA và có canonical derived AdminTo tới DC C0 | Request AS-REP không cần TGT ban đầu ở nhánh này; recovery/validity/auth vẫn riêng |
| F4: Aces[].PrincipalSID/PrincipalType/RightName/AceType/IsInherited | Có GenericAll, GenericWrite, WriteDacl, WriteOwner, Owner và ExtendedRight; nhãn collector không là raw access mask/deny đầy đủ | Sửa quyền/member/password/SPN/owner/thuộc tính cụ thể. Kiểm quyền hiệu lực cùng actor, object type, attribute/policy và actor usable |
| F5: Computer.LocalAdmins/RemoteDesktopUsers/PSRemoteUsers/DcomUsers | Host-access có bằng chứng để infer theo policy; DcomUsers có dữ liệu ở 1/100 Computer | Host actions theo giao thức, không đồng nhất remote access với admin execution. DCOM còn thiếu COM/application permissions và runtime |
| F6: Computer.Sessions; User/Computer.AllowedToDelegate; Computer.AllowedToAct; User.HasSIDHistory/sidhistory | Các mảng này rỗng trong kiểm kê hiện hành | Không có session/delegation/history quan sát để dùng trực tiếp. Có thể nghiên cứu hành động tạo cấu hình mới từ ACL, không tự thêm quan hệ quan sát |
| F7: unconstraineddelegation, sensitive | Một Computer delegation=true được đợt đầu xác minh là DC; User delegation đều false | Thu TGT cần máy nhận do attacker kiểm soát, victim authentication/coercion và policy. Cờ riêng chưa mở đường nâng quyền |
| F8: GPO.Aces, Properties.gpcpath; OU/Domain.Links, ChildOus/Users/Computers | Có 2 GPO, ACL GPO có GenericWrite/WriteDacl/WriteOwner; một OU và Domain có Links; gpcpath là reference GPT | Đã resolve holders chỉ DA/EA; raw containment Domain link GPO0 gồm 100 Computer, OU0 link GPO1 gồm C0/C8. Còn SYSVOL write/policy processing/filtering/final effect |
| F9: Domain.Trusts | Container rỗng | Không sinh đường cross-domain từ container rỗng hoặc domain label |
| F10: pwdlastset/pwdneverexpires/passwordnotreqd, userpassword | User.userpassword đều null; passwordnotreqd=true có 2 User records | Không suy password rỗng/yếu, hoặc crack probability từ tuổi mật khẩu/cờ. Cần hypothesis và evidence riêng |

Sáu file không cung cấp fact về LSASS/SAM/SECURITY contents, hash/key/ticket do attacker có, nội dung XML GPP/cpassword, CA/templates, PKINIT readiness, LDAP/SMB signing, dịch vụ coercion, lockout/guess budget hoặc endpoint authorization hiện tại. Chúng là dữ liệu cần thêm hoặc giả định runtime phải khai báo; không dùng OS label hay bảng log thay cho chúng.

## 4. Đối chiếu đủ 40 dòng mentor gửi

**Một kỹ thuật có thể liên quan nhiều bước và nhiều nguồn dữ liệu.** Trạng thái dưới đây là disposition nghiên cứu, không là verdict của một engine run.

- **Thông tin:** hỗ trợ xác định facts/targets; không tự tạo quyền mới. Chưa mô hình hóa tri thức attacker nên không claim discovery đã là action owner.
- **Đã có một phần:** có action/quy tắc tương ứng trong catalog; chưa bao phủ toàn bộ mọi biến thể.
- **Ứng viên:** có điểm xuất phát từ field/ACL; còn cần kiểm chuỗi, runtime và tích hợp.
- **Thiếu đầu vào:** snapshot chưa hỗ trợ phần quyết định; có thể dùng synthetic để kiểm logic, không xác nhận đường từ SEAMLESS.
- **Sau mục tiêu:** thường cần quyền mạnh đã có hoặc mô hình persistence/time; chưa ưu tiên cho lát dự đoán tới tài sản đầu tiên.

| # | Kỹ thuật và nguồn cơ chế | Dữ liệu AD liên quan | Điều kiện/state → kết quả cần phân biệt | Disposition |
| --- | --- | --- | --- | --- |
| 1 | [Domain account enumeration](https://attack.mitre.org/techniques/T1087/002/) | F1, danh sách User/Computer | Query/đọc được thông tin → biết account; không tạo usable identity | Thông tin |
| 2 | [Permission/group discovery](https://attack.mitre.org/techniques/T1069/002/) | F1/F4 | Đọc membership/ACL → biết quyền; muốn dùng quyền vẫn cần actor/context | Thông tin; group discovery và ACL discovery không là một quyền mới |
| 3 | [Domain trust discovery](https://attack.mitre.org/techniques/T1482/) | F9 | Biết trust direction/type và policy → chọn scope tiếp; chưa là cross-domain authentication | Thông tin; Trusts rỗng |
| 4 | SPN enumeration; [Microsoft SPN](https://learn.microsoft.com/en-us/windows/win32/ad/service-principal-names) | F2 | Đọc SPN → biết account/service mapping; không có secret | Thông tin để roasting |
| 5 | [Password policy discovery](https://attack.mitre.org/techniques/T1201/) | F10 không thay policy | Đọc policy/lockout → chọn guess budget; không biết password | Thiếu đầu vào policy |
| 6 | Attack-path enumeration; [SharpHound](https://bloodhound.specterops.io/collect-data/ce-collection/sharphound) | F1/F4/F5/F8 | Thu thập/đọc snapshot → xây facts; không phải hành động chiếm đích | Thông tin/ingestion; không thêm cạnh takeover |
| 7 | [Password spraying](https://attack.mitre.org/techniques/T1110/003/) | F1/F10 | Endpoint chấp nhận auth, guess set/lockout/budget → secret/identity chỉ nếu trúng | Thiếu đầu vào; account list chưa chứng minh xác suất |
| 8 | [Brute force](https://attack.mitre.org/techniques/T1110/001/) | F1/F10 | Guess budget và policy → recovery nếu đúng; online guessing khác offline recovery | Thiếu đầu vào; chưa ưu tiên |
| 9 | [Kerberoasting](https://attack.mitre.org/techniques/T1558/003/) | F2 và downstream F1/F4 | Usable Kerberos auth + KDC/policy → material; recovery → secret; activation → identity | Giữ ứng viên; ca đã trace có reset holder chung với 2.490 enabled Users, cần counterfactual/đổi ca |
| 10 | [AS-REP Roasting](https://attack.mitre.org/techniques/T1558/004/) | F3 và downstream F1 | Account biết + no-preauth + KDC/policy → material; recovery/activation mới mở danh tính | Ứng viên ca đầu; chưa xác nhận recovery/asset success |
| 11 | [Forced authentication](https://attack.mitre.org/techniques/T1187/) | F5/F7 chỉ là nền đối tượng | Service/coercion reachable, victim/listener/auth policy → auth attempt; capture/relay cần bước riêng | Thiếu đầu vào coercion và relay; không gộp mọi exploit spooler |
| 12 | [LSASS dumping](https://attack.mitre.org/techniques/T1003/001/) | F5/F6 | Admin/process access + live session/protection facts → credential material, không tự usable identity | Đã có một phần abstraction HasSession; Sessions rỗng, không claim LSASS implementation đầy đủ |
| 13 | [SAM dumping](https://attack.mitre.org/techniques/T1003/002/) | F5 chỉ là nền host | Host quyền đủ + hive access → local hashes; khác domain password và logon được | Thiếu đầu vào hive/local account semantics |
| 14 | [NTDS.dit extraction](https://attack.mitre.org/techniques/T1003/003/) | F1/F5 có thể xác định DC | Quyền đọc database/backup trên DC → secret records; phải xét việc dùng chúng | Sau mục tiêu/thiếu đầu vào; kiểm prefix nếu nghiên cứu sau |
| 15 | [LSA secrets](https://attack.mitre.org/techniques/T1003/004/) | F5 chỉ là nền host | Quyền SECURITY/LSA phù hợp → secret có owner/type; chưa có secret contents | Thiếu đầu vào |
| 16 | [Cached domain credentials](https://attack.mitre.org/techniques/T1003/005/) | F5 | Cache có thật + quyền đọc → verifier để dò; DCC2 không là NTLM hash dùng trực tiếp | Thiếu cache/recovery evidence |
| 17 | [DCSync](https://attack.mitre.org/techniques/T1003/006/); [BloodHound](https://bloodhound.specterops.io/resources/edges/dc-sync) | F4 + F1 | Cùng usable actor có quyền replication kết hợp trên domain + RPC → hash/key; protocol use riêng | Ứng viên để sau; holders đã kiểm chủ yếu đặc quyền/DC, không chứng minh mọi prefix đều bị loại |
| 18 | [GPP cpassword](https://attack.mitre.org/techniques/T1552/006/) | F8 chỉ có gpcpath | Đọc XML thật có cpassword → recovered password; reference đường dẫn không là nội dung | Thiếu XML; không suy mọi GPO có cpassword |
| 19 | [Certificate theft](https://attack.mitre.org/techniques/T1649/) | Không có certificate/key/store facts | Đọc/export cert + private key → auth material; validity/mapping/policy quyết định dùng được | Thiếu đầu vào; khác vulnerable enrollment |
| 20 | [Pass-the-Hash](https://attack.mitre.org/techniques/T1550/002/) | F1/F5; hash không có | Có NTLM hash đúng owner + endpoint cho phép NTLM + authorization → scoped identity/action | Thiếu material/protocol bridge; không lấy material generic làm hash |
| 21 | [Pass-the-Ticket](https://attack.mitre.org/techniques/T1550/003/) / Overpass-the-Hash | F1/F2; ticket/key không có | Ticket dùng lại phải đúng chủ thể/service/lifetime; hash/key đổi lấy ticket là nhánh khác | Thiếu artifact; tách hai cơ chế trước khi chốt mapping/action |
| 22 | [Golden Ticket](https://attack.mitre.org/techniques/T1558/001/) | Domain/identity facts, không có krbtgt key | Có key krbtgt + domain/PAC facts + policy → forged ticket; authorization vẫn phải xét | Thiếu key; thường sau domain compromise, chưa ưu tiên |
| 23 | [Silver Ticket](https://attack.mitre.org/techniques/T1558/002/) | F2, không có service key | Service key + chủ thể/service + policy → ticket scope dịch vụ; không identity toàn miền | Thiếu key và ticket semantics |
| 24 | Diamond/Sapphire; [T1558 family](https://attack.mitre.org/techniques/T1558/) | F1/F2 chỉ nền directory | Khóa, ticket/PAC và điều kiện của từng biến thể → ticket dùng được trong scope | Thiếu đầu vào; mapping/biến thể cần research riêng, không nhận tính stealth chung |
| 25 | Unconstrained delegation; [CoerceToTGT](https://bloodhound.specterops.io/resources/edges/coerce-to-tgt) | F7 | Controlled receiver + delegated victim auth + ticket access → TGT, rồi dùng theo scope | Ứng viên để sau; receiver có cờ đã kiểm là DC |
| 26 | Constrained delegation; [Microsoft](https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-constrained-delegation-overview) | F6/F2 | Controlled service account/key + allowed service/delegation policy → service identity P | Thiếu relation observed; AllowedToDelegate rỗng; xét tạo relation phải có write right riêng |
| 27 | RBCD; [AddAllowedToAct](https://bloodhound.specterops.io/resources/edges/add-allowed-to-act) | F4/F6 | Write đúng descriptor + controlled service M/SPN/key + S4U/policy → delegated service identity, rồi endpoint action | Đề xuất review kế tiếp; cùng User có GenericAll trên Computer và enabled SPN User. Còn reset/acquisition/key/descriptor/asset gates |
| 28 | AD CS escalation; [ESC1](https://bloodhound.specterops.io/resources/edges/adcs-esc1) | Không có CA/template/trust/mapping | Enrollment/template/CA/policy theo từng ESC → cert/key; activation và final rights riêng | Thiếu đầu vào; không gộp ESC1–ESC16 thành cùng một condition |
| 29 | Shadow Credentials; [AddKeyCredentialLink](https://bloodhound.specterops.io/resources/edges/add-key-credential-link), [research gốc](https://eladshamir.com/2021/06/21/Shadow-Credentials.html) | F4 trên User/Computer | Write attribute phù hợp + PKINIT/DC certificate/support → key credential, rồi authentication | Ứng viên để sau; không cần relation tồn tại trước, thiếu PKINIT readiness và exact access-check |
| 30 | [SID History injection](https://attack.mitre.org/techniques/T1134/005/) | F6/F4 không thay specialized rights | Quyền/cơ chế thay history + token/trust filtering → thêm SID có thể hiệu lực | Thiếu đầu vào; sidhistory rỗng không chứng minh ghi được |
| 31 | [Token impersonation/theft](https://attack.mitre.org/techniques/T1134/001/) | F5/F6 | Token hiện diện, process privileges/access → local security context; không tự toàn miền | Thiếu token/process facts; HasSession không là token handle |
| 32 | [Malicious GPO modification](https://attack.mitre.org/techniques/T1484/001/), [GenericWrite](https://bloodhound.specterops.io/resources/edges/generic-write) | F4/F8 | Write policy/GPT phù hợp + scope/filter/process conditions → predicted effect trên máy | Để sau: holders DA/EA và raw scope đã trace; còn SYSVOL/process gates. Inference GPO không là malicious-write action |
| 33 | [Create domain account](https://attack.mitre.org/techniques/T1136/002/) | F1/F4 | Effective create-child right + directory/policy → account; create computer không thay bằng default quota | Ứng viên để sau; chưa có create-right trace, không tự gán quyền cho account mới |
| 34 | [Add privileged group member](https://attack.mitre.org/techniques/T1098/) | F1/F4 | Usable actor + GenericAll hoặc write-member hiệu lực + directory gates → branch membership; token usability riêng | Đã có một phần qua genericall_add_member; chưa mọi delegate right |
| 35 | ACL/DACL backdoor; [WriteDacl](https://bloodhound.specterops.io/resources/edges/write-dacl) | F4 | WriteDacl + directory gates → quyền branch mới; sử dụng quyền cần action/context tiếp | Đã có một phần grant_new_object_right; chưa mô hình durability/persistence đầy đủ |
| 36 | AdminSDHolder; [Microsoft](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/security-best-practices/appendix-c--protected-accounts-and-groups-in-active-directory) | F4/admincount chỉ tín hiệu | Exact object write + protected membership + SDProp processing → ACL propagation | Thiếu object/access/propagation trace; admincount không thay AdminSDHolder evidence |
| 37 | DSRM abuse; [Microsoft về tài khoản DSRM](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/reset-directory-services-restore-mode-admin-pwd) | DC role không là DSRM state | DSRM secret + chế độ/điều kiện logon → local DC access | Thiếu secret/runtime; nguồn xác nhận tài khoản/reset, biến thể abuse ngoài DSRM cần research riêng; sau mục tiêu nếu phải chiếm DC trước |
| 38 | [Skeleton Key](https://attack.mitre.org/techniques/T1556/001/) | F5/DC role chỉ nền | Quyền sửa authentication process trên DC + protection/runtime → altered auth behavior | Sau mục tiêu và thiếu process facts; chưa ưu tiên |
| 39 | [Custom SSP](https://attack.mitre.org/techniques/T1547/005/) | F5 chỉ nền host | Registry/load rights + LSA policy + subsequent auth → captured credentials/persistence | Thiếu process/time facts; ngoài lát tới tài sản đầu tiên |
| 40 | Golden Ticket persistence; cùng nguồn dòng 22 | Như 22 | Dùng lại/duy trì ticket cần lifetime/key rollover/horizon | Gộp với 22; không thêm một cạnh kỹ thuật độc lập chỉ vì tactic khác |

### Các tín hiệu ngoài bảng vẫn phải được xét

**Bảng mentor không khóa tập ứng viên.** Đã kiểm thêm theo raw, chưa là commitment implementation:

- Owner/WriteOwner: holders chỉ DA/EA/Administrators; mọi WriteOwner ACE có cùng pair WriteDacl, Owner chỉ 38/3.363. [WriteOwnerRaw](https://bloodhound.specterops.io/resources/edges/write-owner-raw) còn owner restrictions; chưa thấy prefix ngoài bộ lọc để ưu tiên trước.
- DcomUsers: record duy nhất nối User2201 tới DC C0, không có canonical edge cùng pair. [ExecuteDCOM](https://bloodhound.specterops.io/resources/edges/execute-dcom) cần COM permissions/execution identity/network/auth; chưa proof admin_control hoặc asset mới.
- ExtendedRight/AceType=All: 2.497 User ACEs, holders chỉ DA/EA/Administrators. [Legacy importer pin](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js#L583) ánh xạ AllExtendedRights; candidate mapping cho reset đã có bị parser bỏ qua, chưa là đường ít quyền mới.
- haslaps=false ở 100/100 Computer, thiếu password/read-LAPS evidence; giữ giới hạn collection cho [ReadLAPSPassword](https://bloodhound.specterops.io/resources/edges/read-laps-password).

Shadow Credentials/GPO đã có ở dòng 29/32; không đếm lại. Relay phải xét [destination-specific gates](https://bloodhound.specterops.io/resources/edges/coerce-and-relay-ntlm-to-ldap).

## 5. Chọn chuỗi tích hợp và kiểm đúng prediction

**Đề xuất AS-REP trước, RBCD kế tiếp có gate; Kerberoasting cần đối chứng/đổi ca.** AS-REP kiểm từ chưa có AD credential/control dùng được nhưng biết hoặc đoán được V_A, tới V_A với AdminTo C0 hiện có; RBCD kiểm tạo relation mới bằng ACL và lấy SPN principal qua reset. GPO/owner đã trace nhưng holders đặc quyền, DCOM còn protocol/context riêng. Đây là đề xuất phạm vi, không là ranking phổ biến/nguy hiểm hoặc commitment. Sau B approval và merge #217, [bộ ca/handoff](week4-extension-scenario-handoff.md) cung cấp positive/blocked/unknown/counterfactual và ranh giới A/B để review tiếp.

| Chuỗi và căn cứ | Initial state/facts/assumptions | Kết quả bước/đích | Ca quyết định |
| --- | --- | --- | --- |
| AS-REP: User1700/C0 | X chưa có AD credential/control dùng được, biết hoặc đoán được target; pre-auth off/enabled; KDC/recovery/secret validity/auth; canonical AdminTo; host gates | material → recovered secret → scoped usable V_A → DA checkpoint → admin_control(C0) nếu đủ gates | Pre-auth required blocked; recovery missing không apply identity; AdminTo có nhưng asset unknown/false không success |
| RBCD: User1580/User2075/Computer27 | Usable U_R; GenericAll tới M và C_R; reset/acquisition/key bridge của M; exact descriptor write; delegation P/KDC/service/P authorization | controlled M/SPN/key → descriptor branch mới → delegated service context P → asset action | Không cần default quota/tạo máy cho nhánh này; raw right không tự là controlled M; thiếu P quyền trên asset giữ unknown, không cấp P identity toàn miền |
| Kerberoasting: User11→User917→C0 | Initial U có Kerberos auth; SPN/KDC/recovery/reset/activation/host gates; so U có cùng reset holder | material → secret → usable V_K → reset/usable V_D → checkpoint → asset | Kiểm U đã reset V_D trước roasting được chưa; không claim mới vì thêm acquisition; group hops không thêm crack events |
| DCOM User2201→C0; owner/GPO | Actor/target/holders/links/containment đã resolve; còn COM permissions/execution identity hoặc runtime/prefix mới | DCOM có thể mở protocol/action, chưa measured coverage/asset success; owner/GPO để sau | Container/link không là execution; synthetic chỉ kiểm rule, không thay raw/runtime evidence |

Tên material/secret/service context trong bảng là mô tả khái niệm, không API/schema mới đã accepted. B chọn owner/state/trigger theo [#174](https://github.com/nairyuuu/ad-weighted-graph/issues/174), tái sử dụng reset bridge khi đúng semantics, không giả recovered secret là reset_password_control.

Nghiệm thu extension phải có:

1. Query khai báo source/asset/initial capability/context; hệ thống tự sinh bước từ facts/state, không nhận sẵn ordered path làm sản phẩm.
2. Cùng graph đổi initial state hoặc accepted runtime assumption thì tập bước khả dụng thay đổi; known-false trong cùng scope không bị assumption override.
3. Chuỗi positive dưới giả định có trace fact/rule/assumption/effect; missing không tạo success effect; graph gốc và provenance không mutate.
4. Oracle độc lập cho reachable states/path sets; kiểm asset success tách DA checkpoint, no-path chỉ trong finite complete scope; truncation không là chứng minh absence/optimal.
5. So baseline và extension trên cùng source/target/assumptions/catalog scope, giữ cả routes cũ và routes mới có nghĩa; báo unknown/unrated riêng. Một candidate edge mà không mở route tới asset vẫn được báo đúng, không gọi là một attack path mới đã xác nhận.
6. Synthetic dùng để kiểm logic; SEAMLESS dùng để kiểm dữ liệu/trace. Không cần attack telemetry đã xảy ra để predict action, không thực hiện exploit hoặc crack trong task nghiên cứu.

## 6. Chấm điểm không làm thay đổi việc có đường hay không

**Trước tiên sinh và kiểm đường theo ngữ nghĩa; sau đó mới đánh giá C/P/I nếu có căn cứ.** Missing scoring basis không làm một bước có thể thực hiện biến thành blocked; ngược lại điểm cao không làm unresolved step thành thành công.

C là công sức các công việc mới; P là khả năng toàn chuỗi đạt đúng asset goal trong horizon/kịch bản; I là hậu quả tại asset success có căn cứ nghiệp vụ. DA là checkpoint, không tự là I=Critical hoặc final asset compromise. Các số Week 3 không mặc nhiên phù hợp cracking hoặc các cơ chế mới.

Theo [ADR-0013](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md), `P(E1,…,Ek | F,S) = ∏ P(Ei | F,S,E1,…,Ei−1)`. Đây là xác suất của một chương trình tuần tự, không xác suất “domain sẽ bị compromise qua ít nhất một đường”. Không giả các bước độc lập, không cộng các đường chung tiền tố như độc lập.

- Gắn work-unit/event theo bí mật/chủ thể/đích/context/budget/causal parent. Nhiều SPN cùng khóa không tự là nhiều lần crack; sử dụng lại secret không tính lại recovery. Một lần authentication mới ở context khác có thể là công việc/rủi ro mới.
- MemberOf/ACL propagation thụ động không thêm một lần khai thác ngẫu nhiên; chia/gộp cùng công việc không làm P thay đổi giả tạo. Code chỉ khử trùng ID, A/B vẫn phải review sự tương đương về nghĩa.
- Xác suất giảm khi thêm sự kiện thành công bắt buộc là đúng; đường nhiều hop không tự có P thấp. Không dùng trung bình hình học hoặc sàn P để làm số đẹp rồi gọi là whole-path probability.
- Cận điều kiện phải đúng tiền tố và scope. Fact chưa biết khác chance thất bại; không tự đặt P=0.5. Missing bounds giữ likelihood_unrated; effort/impact thiếu cũng giữ unrated theo interface.
- Scenario estimates có thể dùng dưới giả định được ghi, nguồn/căn cứ/uncertainty và A/B review. Synthetic success outcome hoặc fixture số chỉ kiểm logic/toán, không là crack measurement hoặc hiệu chuẩn thực nghiệm. Retry/expiry/adaptive attack chưa được nhận trong model hiện hành; không claim rủi ro của mọi chiến dịch ngoài scope đó.

## 7. Kiểm lại bảng tactic/log trước khi tái sử dụng

**Telemetry gợi ý hỗ trợ quan sát, không là prerequisite cho prediction hoặc proof of success.** Bảng người dùng gửi chưa có nguồn theo từng claim; không chép nguyên thành authoritative catalog.

| Điểm cần sửa hoặc giữ giới hạn | Nguồn / cách xử lý |
| --- | --- |
| Delegation không tự ánh xạ chung T1134 | [MITRE T1134](https://attack.mitre.org/techniques/T1134/) là Access Token Manipulation; dùng nguồn cơ chế Microsoft/SpecterOps cho delegation, giữ mapping chưa chốt nếu không khớp |
| 4799 không là tín hiệu chung cho mọi lần đọc nhóm/ACL AD | [Microsoft 4799](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4799) mô tả local-group enumeration và nêu giới hạn sinh event |
| RC4/4769 không là điều kiện bắt buộc hoặc chứng minh Kerberoasting | [MITRE Kerberoasting](https://attack.mitre.org/techniques/T1558/003/) có AES-related procedure example; etype/request bất thường là signal cần context, không proof crack |
| 4624 NTLM không đủ chứng minh Pass-the-Hash; thiếu 4768 không đủ proof Golden Ticket | Nguồn MITRE dòng 20/22; auth hợp lệ cũng có log, cần source/identity/time/audit coverage; không suy acquisition method chỉ từ protocol |
| Chứng chỉ bị đánh cắp khác enrollment abuse, và mỗi ESC có gates riêng | [T1649](https://attack.mitre.org/techniques/T1649/), [Certified Pre-Owned](https://specterops.io/blog/2021/06/17/certified-pre-owned/); CA issuance log không tự chứng minh theft hoặc private key access |
| Dòng 21 gộp ticket reuse và key/hash-to-ticket; dòng 24 gộp hai biến thể | Tách cơ chế trước thiết kế action/work units; mapping cụ thể còn cần review, không gán tên ghép làm một event |
| Golden Ticket và Golden Ticket persistence không là hai kỹ thuật độc lập | Cùng T1558.001; khác mục tiêu/horizon, không nhân lại cùng acquisition |
| PrintNightmare trong dòng coercion chưa được verify là cùng primitive | Bảng trộn tên exploit/tool với cơ chế ép xác thực; chỉ dùng T1187 nếu step thực sự là forced authentication, chưa copy tên đó vào rule |

## 8. Handoff và việc tiếp theo

**Hoàn tất sàng lọc để chọn phạm vi; giữ core Week 4 chạy song song.** Đợt này cung cấp phân loại đủ bảng mentor và field-led candidates, chưa nghiệm thu kỹ thuật mới hoặc đóng research.

| Phần việc | Owner / đầu ra tiếp theo | Điều kiện chốt |
| --- | --- | --- |
| Sàng lọc và đề xuất | A: đủ 40 dòng, bản ngắn, raw verification/probe; B review | Review field/disposition/conditions/effects; không hiểu 40 dòng là 40 cạnh |
| Raw trace | A đã verify sáu files, rerun audit/parser và resolve roasting/RBCD/GPO/owner/DCOM/DCSync/delegation | Hoàn tất raw/reference; runtime/access check và extension path generation còn mở |
| Chọn extension đầu | A/B review 1–2 chuỗi: AS-REP trước, RBCD kế tiếp có gate; Kerberoasting cần counterfactual/đổi ca | Input/oracle/asset goal/C/P/I để tách tasks; chưa là mentor approval |
| Tích hợp state/parser/search | B theo scope tự nhận từ #174 | API/owner/trigger/outcome cụ thể được review; A handoff expectation và scoring boundary |
| Core Week 4 | [#204](https://github.com/nairyuuu/ad-weighted-graph/issues/204), A #206/#207/#208 và B #211/#212/#213 | Tiếp tục query/search/scoring/acceptance; không chờ research extension, không claim extension đã triển khai |
| Week 5–6 | Reuse core và scope extension đã accepted | Đối chứng path-level/choke points rồi demo/report; không kéo tất cả persistence/ticket simulation vào Week 4 |

Bản ngắn cho mentor nằm ở [week4-prediction-proposal.md](week4-prediction-proposal.md). Cần phản hồi vào phương pháp: từ field tới bước, từ bước tới asset, giữ điều kiện/giả định, rồi kiểm coverage và ranking. Không xin mentor duyệt mặc định tất cả kỹ thuật; các task tích hợp sau phải giữ ownership và scope riêng.
