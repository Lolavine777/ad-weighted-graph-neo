# Đánh giá lựa chọn kỹ thuật cho dự đoán Week 4

## Bổ sung sau feedback mentor ngày 06/10

**Phạm vi hiện hành là sàng lọc từ field AD rồi chọn chuỗi mở khả năng mới tới tài sản.**
Mentor đã nhận nội dung trao đổi ngắn và yêu cầu kiểm kê field → GPT hỗ trợ đề xuất → nhóm verify; chưa chấp thuận triển khai riêng hai roasting.
[Phụ lục sàng lọc từ field](week4-field-driven-screening.md) đối chiếu đủ 40 dòng trong bảng mentor gửi, gộp dòng trùng và tách thông tin/đã có một phần/ứng viên/thiếu dữ liệu/sau mục tiêu.
Số loại cạnh không thay việc kiểm đường từ initial state tới asset goal.

Đã lấy đủ sáu raw file từ GitHub theo manifest và [rerun audit/parser/probe](week4-screening-raw-verification.md) tại head tài liệu `18887eaacbad18e95938978f7070c820ef1c31fd`; parser/engine/catalog không đổi so với baseline `0c44e84`, contract 1.3.0/catalog 0.3. Manifest issues=[], 195 field paths, 3.370 nodes/56.367 edges, 3 assessments unknown, 0 warnings/errors; toàn bộ 15.917 membership pairs khớp canonical. Sửa nhận định thiếu raw ở lượt trước: nguồn truy cập được, cần tải và verify trước khi kết luận.

**Ưu tiên hiện hành để B review: AS-REP trước, RBCD kế tiếp có gate.** Canonical đã có AdminTo V_A→C0/DC, làm rõ mapping asset còn để mở ở đợt #201; runtime/endpoint success vẫn chưa quan sát. Cùng U_R có direct GenericAll trên C_R và hai enabled SPN Users, đủ candidate nghiên cứu reset/acquisition bridge cho RBCD, không tự là controlled secret/key hoặc delegation success.

Ca Kerberoasting đã chọn có reset prefix chung với 2.490 enabled Users; hạ claim coverage mới, cần counterfactual/đổi ca. Owner/WriteOwner/GenericWrite/GPO chỉ thấy holders đã đặc quyền; DCOM User2201→C0 còn COM permissions/execution identity/asset effect. DCSync không có same-actor pair ngoài bộ lọc sáu vai trò.

Các đoạn tại pin 891bda0 phía dưới giữ nguyên làm lịch sử; trạng thái hiện hành theo amendment/raw verification này. Không coi raw trace là engine-generated extension path hoặc hiệu chuẩn P. Semantics/state/ratings cần B review; core #204 tiếp tục độc lập, ownership #174 của B giữ nguyên.
[Bản ngắn cho mentor](week4-prediction-proposal.md) được cập nhật theo phương pháp này, chưa gửi bản sửa mới.
Core Week 4 theo #204 tiếp tục độc lập; nghiên cứu này không đổi ownership #174 hoặc nhận phần implementation của B.

## Đợt nghiên cứu đầu đã merge ở PR #201

Cập nhật 2026-10-06, Asia/Ho_Chi_Minh; Refs [#200](https://github.com/nairyuuu/ad-weighted-graph/issues/200), [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192).
**Đề xuất của A: ưu tiên AS-REP qua checkpoint quản trị miền tới tài sản DC cụ thể; giữ RBCD làm phương án kế tiếp có điều kiện.**
Kerberoasting vẫn có giá trị, nhưng không mặc định triển khai cả hai nhánh roasting.
Bản sơ bộ ngày 05/10 được giữ phía dưới làm lịch sử; phần ngày 06/10 này thay thế ưu tiên và mô tả trạng thái hiện hành của bản đó.
Đây là nghiên cứu để B review, chưa gửi mentor, chưa được mentor xác nhận phạm vi và chưa chấp nhận semantics/điểm số mới.
[Bản ngắn cho mentor](week4-prediction-proposal.md) chỉ giữ luận điểm và quyết định cần trao đổi.

## A. Vấn đề và giới hạn hiện tại

**Khoảng trống là thiếu một số bước tạo khả năng mới, trong khi engine đã có suy luận theo trạng thái.**
[Đề bài gốc](../00_todo.md), mục 1, 2, 5 và 6 yêu cầu dựng cạnh từ thuộc tính, tìm đường tới Domain Admin, kiểm tính hợp lý và đối chứng.
[Ghi nhận feedback 29/09](weighting-direction.md#định-hướng-mentor-ngày-2026-09-29-và-phân-biệt-tầng-quyết-định) đã thống nhất đích cuối là tài sản quan trọng; DA membership / usable identity là checkpoint hoặc proxy đặc quyền cao.
Tập kỹ thuật và cách tạo khả năng mới dưới đây vẫn là diễn giải của nhóm cần review, không phải phạm vi được mentor xác nhận.
Pin mã được đọc và pipeline được chạy là `develop@891bda0001b9958e712cff54045f651273b43fd0`, contract 1.3.0, catalog 0.3.

| Thành phần tại pin hiện hành | Đã có và có thể tái sử dụng | Giới hạn được kiểm từ mã |
| --- | --- | --- |
| [Normalizer](https://github.com/nairyuuu/ad-weighted-graph/blob/891bda0001b9958e712cff54045f651273b43fd0/src/parser/normalizer.py#L362), [builder](https://github.com/nairyuuu/ad-weighted-graph/blob/891bda0001b9958e712cff54045f651273b43fd0/src/parser/builder.py#L302) | Canonical identity, provenance, MemberOf gồm PrimaryGroupSid, ACL GenericAll/WriteDacl | Chỉ projection enabled/admincount/distinguishedname; ACE mapping không giữ GenericWrite hoặc ExtendedRight/AceType GetChanges; chưa giữ thuộc tính roasting/delegation |
| [Search](https://github.com/nairyuuu/ad-weighted-graph/blob/891bda0001b9958e712cff54045f651273b43fd0/src/engine/search.py#L336), [catalog](../../configs/attack_semantics.yml), [state](../../src/engine/semantics/state.py) | Canonical/state relationships, capability triggers; DACL-derived permission; reset → usable_identity và actor handoff | Chưa có owner/trigger cho request roasting, recovery, DCSync, RBCD hoặc coercion/relay; credential_material không phân loại artifact; reset qualifier không dùng thay recovered secret |
| [Evaluator](../../src/engine/semantics/evaluator.py), [transitions](../../src/engine/semantics/transitions.py) | False → blocked, thiếu fact → indeterminate; branch state bất biến; effects chỉ apply cho applicable | Có thể thực hiện dưới giả định không đồng nghĩa thực hiện thành công ngoài đời; outcome recovery cần B quyết định |
| [Ranking](../../src/engine/ranking/assessment.py), [golden scenarios](attack-scenarios.md) | Conditional prefix, unique work units, reachable-state oracle và counterfactuals | Không tự phát hiện hai event ID khác nhau cùng nghĩa; suite cũ không xác nhận kỹ thuật mới |

[#175 đã đóng](https://github.com/nairyuuu/ad-weighted-graph/issues/175#issuecomment-5992315230) sau golden nền; [#196 đã đóng](https://github.com/nairyuuu/ad-weighted-graph/issues/196#issuecomment-6008002642) sau cross-reproduction trên comparison contract được chấp nhận.
Không làm lại hai phần này; full comparator vẫn NOT_MEASURABLE trong boundary đã chốt, không là parity CE toàn sản phẩm.
[#174](https://github.com/nairyuuu/ad-weighted-graph/issues/174) vẫn mở và thuộc B: A đưa yêu cầu/kỳ vọng, không chọn schema, thêm catalog hoặc sửa engine trong lượt này.
[ADR-0004, amendment hiện hành](../adr/ADR-0004-synthetic-goal-edges-and-dcsync-co-occurrence.md) cũng không cho phép biến kế hoạch DCSync cũ thành implementation đã có.

## B. Vì sao khảo sát sáu cơ chế này?

**Ưu tiên khả năng nối từ điểm xuất phát tới tác động, thay vì số field hoặc tên kỹ thuật.**
Roasting kiểm bước lấy dữ liệu không cần quyền trên đích; DCSync kiểm kết hợp quyền; RBCD kiểm hành động tạo quan hệ mới; delegation kiểm thu TGT; relay và AD CS kiểm phụ thuộc môi trường/cấu hình.
Sàng lọc từng ứng viên theo cùng sáu câu hỏi: khả năng mới/tác động, cách BloodHound thể hiện, dữ liệu tới engine, điều kiện thiếu, giá trị từ xuất phát chưa đặc quyền, và công việc tích hợp.
Không có số liệu tần suất với mẫu/denominator so sánh đồng nhất trong các nguồn đã đọc, nên không xếp hạng “phổ biến nhất”.

| Ứng viên | Điều kiện đầu → hành động → kết quả → bước tiếp theo | BloodHound đã có | Dữ liệu tới engine và điều kiện thiếu | Giá trị đường / phần cần thêm / lựa chọn |
| --- | --- | --- | --- | --- |
| Kerberoasting | U có xác thực Kerberos phù hợp; V có SPN → xin service-ticket material → dò ra bí mật V nếu thành công → xác thực V rồi dùng quyền downstream [K1, K3, K4] | Legacy 4.0.3 query thuộc tính và shortest path từ User có SPN; CE/Enterprise có abuse guidance; BHE v6.3 có finding/impact analysis [B3, N8] | 51 User records có SPN; không tới canonical nodes; đã trace một route qua nhóm tới GenericAll trên User đặc quyền; thiếu KDC/policy, etype, ngân sách và recovery | Có mở đường từ U không có quyền trên V; cần material/recovery/auth bridge và projection SPN; **để sau AS-REP**, không loại vì ít tác động |
| AS-REP Roasting | Biết account V, KDC reachable, V không yêu cầu pre-auth → xin AS-REP material → khôi phục bí mật → xác thực V và dùng quyền nhóm [K2, K5] | Legacy 4.0.3 query dontreqpreauth; không suy UI Legacy thành reachability có điều kiện [B3] | 176 records true, một User enabled có MemberOf trực tiếp DA; field chưa tới engine; không có crack/validity/endpoint evidence | Chuỗi impact ngắn, dễ cô lập gate mới; cùng recovery bridge với Kerberoasting; **đề xuất chọn trước**, không cần triển khai cả hai |
| DCSync | Actor xác thực, có quyền replication kết hợp trên cùng domain → yêu cầu sao chép bí mật → có hash/key của đích → dùng theo protocol/policy riêng, không tự có DA identity [N1, N2] | Legacy 4.0.3 giữ GetChanges/GetChangesAll rời; Legacy 4.2 thêm post-processed DCSync, CE/Enterprise có cạnh kết hợp [N3] | Có nhãn ACE và membership; builder bỏ ExtendedRight; holder chủ yếu Administrators/DC; thiếu access-check đầy đủ, usable actor, RPC/network | Impact rất cao nhưng dữ liệu đã kiểm chưa cho một prefix ít đặc quyền hấp dẫn hơn lựa chọn chính; thêm permission evidence + conjunction + secret owner; **để sau**, không dùng hai ACE của hai actor riêng làm success |
| RBCD | U ghi được thuộc tính RBCD của C và kiểm soát service account M có SPN → sửa descriptor → delegation mới → S4U tới dịch vụ C dưới danh tính P → authorization/execution trên C [N4, N5] | Legacy 4.0.3 ingest AllowedToAct/AddAllowedToAct và GenericWrite; Legacy 4.2 thêm WriteAccountRestrictions; CE/Enterprise mô tả các cạnh này [N6] | AllowedToAct rỗng; GenericWrite chỉ Administrators; có GenericAll từ User ngoài nhóm đặc quyền đã sàng lọc tới Computer; ACL đó tới canonical nhưng chưa có RBCD owner | Đúng cơ chế tạo quan hệ mới; phải chứng minh M/key/SPN, thuộc tính ghi được, policy delegation của P và dịch vụ; reuse GenericAll/DACL, thêm branch delegation + scoped service identity; **phương án kế tiếp có gate**, không cam kết Week 4 |
| Unconstrained delegation / lấy TGT | Kiểm soát máy/dịch vụ có delegation, đọc được ticket; P xác thực tới đó hoặc bị coercion và được delegate → thu TGT P → dùng P theo scope/lifetime, có thể tới DCSync nếu P là DC [N7, K5, K6] | Legacy thuộc tính/query; CE/Enterprise v6.3 thêm CoerceToTGT [N8] | Một Computer true là DC theo PrimaryGroupSid và membership; không có evidence kiểm soát, dịch vụ/coercion, TGT; thuộc tính bị bỏ tại projection | Nếu phải chiếm DC trước thì không chứng minh mở đường mới tới domain; thêm artifact/time/coercion gates khá rộng; **để sau** tới khi có máy nhận chưa đặc quyền và prefix có căn cứ |
| NTLM coercion/relay | Có thể gây/chờ xác thực của P tới listener → chuyển tiếp tới dịch vụ không buộc bảo vệ phù hợp → session/quyền theo P → thao tác LDAP/SMB hoặc chứng chỉ [N9, N10] | CE/Enterprise có CoerceAndRelayNTLMToSMB/LDAP/LDAPS/ADCS, tài liệu đọc ngày 06/10; blog gốc 08/04/2025 mô tả collection/post-processing [N9] | SEAMLESS không có service/coercion result, SMB signing, LDAP signing/channel binding, outgoing NTLM restrictions; OS label không thay cấu hình | Có thể mở đường mạnh nhưng cần module environment facts và destination-specific gates; **loại khỏi tích hợp Week 4** trên input này; không gọi kỹ thuật không tồn tại |
| AD CS, đối chiếu ESC1/ESC8 | ESC1: enroll được mẫu cho xác thực và chọn identity khác, CA chấp nhận → cert/key → xác thực đúng mapping; ESC8: relay tới web enrollment không bảo vệ → cert P → dùng P [N10, N11, N12] | CE/Enterprise ADCSESC1 là cạnh suy ra và CoerceAndRelayNTLMToADCS là cạnh tổng hợp; không dùng Legacy 4.0.3 để đánh giá coverage AD CS hiện đại | Sáu file manifest không có CA/template/NTAuth, enrollment ACL/EKU/issuance/SAN, web endpoint/EPA; chưa có node kinds hoặc mapping identity chứng chỉ | Impact tiềm năng cao, nhưng cần collector/schema/trust/mapping và auth mới; **loại khỏi tích hợp Week 4**; input CA của dataset khác không được trộn vào SEAMLESS |

Tên capability/action mới trong tài liệu là yêu cầu khái niệm, không phải API đã được chấp nhận.
Không bổ sung ứng viên thứ bảy: các cơ chế đã đủ phân biệt khoảng trống; mở thêm scope hiện chưa có evidence làm đổi lựa chọn.

## C. Kiểm raw, quyền hiệu lực và nơi dữ liệu bị mất

**Snapshot có thể chứng minh thuộc tính và quan hệ; nó chưa chứng minh các điều kiện thực hiện hay kết quả khai thác.**
Đã verify trước audit và sau probe: sáu file, `issues=[]`, snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
Chạy lại official parser fail_fast trên pin hiện hành: 3.370 nodes, 56.367 edges, 3 assessments unknown, 0 warnings/errors.
Đây là kiểm đường dữ liệu, không là số đường tấn công hoặc thành công.
Canonical output local có SHA-256 `017b13a3e618e97ad20422b50f9f7bd8e89682aaaa2ee2955842856de8dbe445`; created_at bên dưới là metadata cố định để tái lập, không là thời điểm quan sát.

```bash
.venv/bin/python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
.venv/bin/python scripts/audit_seamless_raw.py --raw-dir data/raw/SEAMLESS --manifest data/samples/manifests/seamless-raw-v1.json --output reports/generated/week4-200/raw-inventory.json --markdown-output reports/generated/week4-200/raw-audit.md
.venv/bin/python -m src.parser.cli --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 --raw-dir data/raw/SEAMLESS --profile unit --error-policy fail_fast --time-policy tests/fixtures/ranking/seamless_time_policy.json --created-at 2026-10-06T00:00:00Z --output reports/generated/week4-200/canonical.json --summary
```

`unit` chỉ là profile correctness; time policy giữ thời gian thu thập assumed, không biến filename thành observed time.
Raw/graph, probe và identity bindings nằm local trong `reports/generated/week4-200/`; không commit danh tính, SPN, key hoặc exports.
Locators dưới đây là chỉ số record/field trong manifest bất biến, không chứa tên account; alias nhất quán chỉ trong tài liệu này.

### C1. DCSync: kết hợp quyền của cùng danh tính

**Không thể kết hợp GetChanges của người này với GetChangesAll của người khác.**
Tại `20210920185958_domains.json#/domains/0/Aces/8..12`, RightName đều ExtendedRight, AceType chứa nhãn quyền, không là allow/deny discriminator.
[Importer Legacy tại pin 4.0.3](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js#L563) chuyển ExtendedRight + AceType không rỗng thành quan hệ mang tên AceType.
Điều này xác nhận semantics importer của nhãn, không pin được collector binary đã thu snapshot hoặc tái dựng Windows access check.

| Alias / vai trò chuẩn được resolve theo identity | Group locator trong `20210920185958_groups.json` | Domain ACE indices | Ý nghĩa và giới hạn |
| --- | --- | --- | --- |
| R1 / Enterprise Domain Controllers | `/groups/546` | 8: GetChanges | DC C0 có membership tới R1; nhóm này riêng lẻ chưa có cặp quyền |
| R2 / Administrators | `/groups/2` | 9: GetChanges; 10: GetChangesAll | Cùng holder có cả hai; membership closure gồm 7 User; hai User không thuộc DA vẫn thuộc Administrators, không là ít đặc quyền |
| R3 / Enterprise Read-only Domain Controllers | `/groups/38` | 11: GetChanges | Không có member khác trong closure đã kiểm; không suy thêm GetChangesAll hoặc khả năng lấy mọi bí mật của RODC |
| R4 / Domain Controllers | `/groups/27` | 12: GetChangesAll | C0 có PrimaryGroupSid tới R4 và membership tới R1, nên cùng C0 có hai quyền qua hai nhóm |

Resolve identity bằng manifest loader → v3 adapter → normalizer chính thức, không dùng display name làm khóa.
Lấy directed closure của canonical MemberOf, gồm PrimaryGroupSid; với từng actor a trên cùng domain D, kiểm closure(a) giao holders(GetChanges,D) và holders(GetChangesAll,D) đều không rỗng.
Kết quả sàng lọc riêng nhãn này gồm 7 User, 1 Computer, 3 Group; Group ở đây là proxy entitlement, không là actor tự đăng nhập được.
Chưa xét GenericAll/AllExtendedRights để tuyên bố một tập effective permissions đầy đủ; không dùng kết quả như toàn bộ danh sách DCSync của domain.
Đối chiếu [Microsoft access-check](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-drsr/15bbda52-7742-4ce3-9327-018647b0fc26) và [vai trò nhóm chuẩn](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-groups) trước khi suy luận cơ chế.
Quyền trong token, scope và usable authentication vẫn là gate runtime; raw normalized labels không có access mask/deny đầy đủ.
Suy luận của A: các holders đã kiểm thiên về nhóm domain-wide privileged/DC; chưa xác nhận prefix từ ít đặc quyền tới replication entitlement mới, nên chưa ưu tiên triển khai DCSync.
Đây không là chứng minh không có prefix như vậy trong toàn graph.

### C2. RBCD và delegation: có ACL khác với chuỗi đủ điều kiện

**AllowedToAct rỗng không loại bỏ khả năng tạo delegation, nhưng quyền ghi cũng chưa đủ cho S4U.**
100/100 Computer AllowedToAct rỗng; 100 ACE GenericWrite đều trỏ tới R2, nên chỉ đếm GenericWrite sẽ phóng đại giá trị từ điểm xuất phát thấp.
Tuy nhiên U_R tại `20210920185958_users.json#/users/1580` có GenericAll trực tiếp tới C_R tại `20210920185958_computers.json#/computers/27`, ACE index 5; cả hai enabled=true.
Canonical graph giữ đúng directed GenericAll U_R → C_R và raw provenance.
U_R không có closure tới các nhóm chuẩn DA/EA/Administrators/DC/RODC/Enterprise DC trong phép sàng lọc này; đây là định nghĩa hạn chế, không chứng minh U_R không có quyền mạnh theo mọi đường khác.
Đây là candidate có giá trị để nghiên cứu **ghi descriptor tạo quan hệ mới**, không phải bằng chứng đã kiểm soát OS C_R.
Chưa có evidence U_R điều khiển account M với SPN/key, hoặc được tạo M; không giả MachineAccountQuota mặc định, quyền create computer hay KDC version/policy.
GenericAll/DACL có thể là nền quyền sửa thuộc tính [N4-N6]; tác dụng chính xác vẫn cần kiểm trong scenario và B review.

C0 tại `20210920185958_computers.json#/computers/0` là Computer duy nhất có unconstraineddelegation=true; có PrimaryGroupSid vào R4 và canonical membership tới R1/R4.
Đây là bằng chứng vai trò DC trong snapshot, không chỉ suy từ hostname hoặc SPN.
Không thấy User delegation=true hoặc Computer non-DC có cờ này trong sáu file; không suy thành absence ở môi trường thật ngoài collection scope.
Chưa có controlled receiving host/service, TGT accessibility, victim authentication/coercion hay delegation protection facts; chiếm được DC rồi mới nhận TGT không tự mở một prefix nâng quyền mới.
RBCD được giữ làm dự phòng; unconstrained delegation để sau khi có evidence receiver và prefix hữu ích.

### C3. Roasting và hai chuỗi downstream đã trace

**Chọn theo quyền sau khi có danh tính, không theo 51 hay 176 records.**
SPN xuất hiện ở 51/2.493 User records; dontreqpreauth=true ở 176; giao hai tập là 4.
Normalizer không giữ cả hai field; rebuilt canonical nodes có 0 serviceprincipalnames, 0 dontreqpreauth.
Các field vẫn còn trong raw/reconciled record nội bộ, nhưng evaluator không được projection hoặc trigger dùng chúng.
Không đọc giá trị userpassword hoặc suy mật khẩu yếu từ pwdlastset/RC4/AES.

| Alias / bằng chứng snapshot | Locator, file cố định `20210920185958_*.json` | Đường đã xác minh và giới hạn |
| --- | --- | --- |
| V_A, ứng viên AS-REP | `users#/users/1700/Properties/{dontreqpreauth,enabled,hasspn}` = true, true, false; `groups#/groups/40/Members/2/MemberId` | V_A → G_DA trực tiếp; G_DA resolve theo identity nhóm DA; target ban đầu đã đặc quyền, nhưng attacker X chưa có V_A, nên acquisition tạo khả năng mới |
| V_K, ứng viên Kerberoasting | `users#/users/11/Properties/{hasspn,enabled,dontreqpreauth}` = true, true, false; serviceprincipalnames không rỗng | V_K không là DA qua membership; có quyền downstream qua nhóm; không cần quyền U → V_K cho bước xin dữ liệu |
| Prefix quyền V_K | `users#/users/11/PrimaryGroupSid`; `groups#/groups/548/Members/1/MemberId`; `groups#/groups/30/Members/2/MemberId` | V_K → G1(`/groups/31`) → G2(`/groups/548`) → G3(`/groups/30`); canonical closure gồm PrimaryGroupSid; security/token usability chưa kiểm |
| Đích quyền của V_K | `users#/users/917/Aces/8` GenericAll của G3; `groups#/groups/40/Members/3/MemberId` | G3 → V_D GenericAll; V_D enabled, là thành viên DA; chỉ quyền directory, chưa reset/auth thành công; phải reuse reset bridge với gates riêng |

Các chuỗi này dựa trên snapshot cho **đoạn thuộc tính/quyền**, không là path roasting đã được engine sinh hoặc tấn công đã xảy ra.
Ví dụ U/V/X/H của bản ngày 05/10 là tổng hợp; không đổi nhãn nó thành quan sát SEAMLESS.
Lựa chọn hiện hành ưu tiên AS-REP vì trace trực tiếp DA tránh thêm reset, nhiều group-token gates và một lần actor handoff trong ca đầu; không vì “nhiều account hơn”.
Kerberoasting có route giá trị đã tìm thấy nên vẫn là phương án thay thế nếu yêu cầu mentor ưu tiên điểm xuất phát có xác thực miền hoặc account dịch vụ.

## D. Bằng chứng cơ chế, chiến dịch và BloodHound

**Kỹ thuật đã biết không tự là đóng góp mới; case report cũng không là xác suất hay tần suất.**
Đã đọc nguồn chính thức và báo cáo gốc ngày 06/10; pin Legacy 4.0.3 `b54c418ef83fe5856ae3fe6317a20f2368a6378c`, dùng docs CE/Enterprise theo ngày đọc cho chức năng hiện hành.
Không gọi ngày tài liệu là một CE binary pin hoặc kết quả thực nghiệm CE.

| Loại bằng chứng | Kết quả nguồn đã đối chiếu | Có thể kết luận / không thể kết luận |
| --- | --- | --- |
| Cơ chế | MITRE K1/K2/N1; Microsoft K3-K6/N2/N4/N10; research gốc Wagging the Dog, Certified Pre-Owned, forest-trust delegation và relay N5/N7/N9/N11 | Có điều kiện/kết quả kỹ thuật; không có ground truth success hay numeric bounds cho SEAMLESS |
| Chiến dịch Kerberoasting | [DFIR Ryuk's Return, 08/10/2020](https://thedfirreport.com/2020/10/08/ryuks-return/), Discovery Day 2, ghi attempted Kerberoast | Đã xuất hiện một attempt trong intrusion; không chứng minh crack thành công hoặc chính bước đó tạo DA |
| Chiến dịch DCSync | [Microsoft DEV-0537, 22/03/2022](https://www.microsoft.com/en-us/security/blog/2022/03/22/dev-0537-criminal-actor-targeting-organizations-for-data-exfiltration-and-destruction/), Reconnaissance and privilege escalation | Có quan sát sử dụng DCSync; không là prevalence trên mọi domain hoặc success rate của actor chưa đặc quyền |
| Relay/AD CS thực tế | [MSRC, 09/12/2024](https://www.microsoft.com/en-us/msrc/blog/2024/12/mitigating-ntlm-relay-attacks-by-default), Background, ghi observed LSARPC → AD CS và các relay vectors khác | Có quan sát khai thác được Microsoft báo cáo; không là số chiến dịch, tần suất hoặc mọi nhánh AD CS |
| AS-REP, RBCD, unconstrained delegation | Có primary mechanism/lab research; MITRE AS-REP dẫn Ryuk/Rubeus nhưng văn bản hai report đã đọc chỉ ghi Kerberoasting | Chưa xác nhận một chiến dịch AS-REP/RBCD/delegation riêng từ primary text đã đọc; không tự nâng tool capability hoặc demo lab thành campaign evidence |
| Tần suất | Không có tập đo chung, sample/denominator, collector coverage và thời kỳ thống nhất | Để chưa biết; không dùng số ATT&CK procedure examples hoặc raw counts để xếp thứ tự phổ biến |

Legacy PrebuiltQueries có hasspn/dontreqpreauth và đường từ account có SPN; [newingestion.js](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js) có AllowedToAct và ACL translation.
Đã tải/đọc source pin đó trong lượt này; không chạy query roasting, RBCD/DCSync hoặc import BloodHound mới.
[Legacy 4.2 announcement](https://specterops.io/blog/2022/08/03/introducing-bloodhound-4-2-the-azure-refactor/) xác nhận DCSync post-processing và WriteAccountRestrictions.
[BloodHound v6.3 announcement](https://specterops.io/blog/2024/12/12/unwrapping-bloodhound-v6-3-with-impact-analysis/) xác nhận CoerceToTGT và BHE impact-based Kerberoastable findings.
Vì BHE đã có impact/risk analysis, không tuyên bố nhóm là hệ thống đầu tiên xét impact hoặc BloodHound chỉ duyệt cạnh tĩnh.
Đóng góp dự kiến của nhóm là trace chuỗi có điều kiện từ một foothold, phân biệt material/secret/scoped identity/resource rights, giữ false/unknown, rồi đánh giá work units và cả đường theo mô hình của repo.
Đây là giả thuyết về giá trị sản phẩm cần đo, không là novelty đã chứng minh.

## E. Lựa chọn, kỳ vọng ca kiểm tra và ranh giới chấm điểm

**Làm một chuỗi đến tác động trước; các nhánh khác chỉ vào kế hoạch khi qua gate dữ liệu và kiến trúc.**
Đề xuất AS-REP trước, Kerberoasting là phương án thay thế dùng chung recovery bridge, RBCD là bước kế tiếp có điều kiện; DCSync/delegation để sau, relay/AD CS ngoài tích hợp Week 4 trên input này.
`AS-REP → recovered secret → usable V_A → effective DA` là checkpoint khả năng/đặc quyền, chưa đạt final goal; membership của V_A sẵn có nhưng attacker ban đầu không có danh tính đó.
Đề xuất tài sản đích là DC C0 đã truy nguồn ở C2 (`computers#/computers/0`), với success predicate `admin_control(C0)` trong context quản trị được chọn.
Đây là lựa chọn tài sản và sự kiện thành công để review, không phải mapping quyền hoặc kết quả đã xác minh trên SEAMLESS.
C0 có bằng chứng vai trò DC; nhãn crown jewel nghiệp vụ và mức impact vẫn cần rationale riêng theo [scenario contract](week3-scenario-contract.md), không tự suy từ Tier-0 hay DA.
Đoạn `effective DA → admin_control(C0)` phải kiểm mapping quyền hiệu lực tới C0, kênh quản trị, network/service availability, authentication và endpoint authorization/admin execution context theo gates Week 3.
Chưa kiểm chứng đủ đoạn này nên SEAMLESS chỉ có downstream có điều kiện/unknown; không biến membership DA thành observed AdminTo, admin_control(C0) hoặc final success.
Mentor cần trao đổi asset nào, mức evidence và abstraction nào phù hợp; không mở lại định hướng final target phải là tài sản.

| Chuỗi / nguồn ca | Điều kiện ban đầu và success branch cần khai báo | Kỳ vọng đủ / sai / thiếu điều kiện |
| --- | --- | --- |
| AS-REP tới checkpoint, integration trace V_A và synthetic oracle tương đương | X controlled; account identifier đã biết; không có quyền X/U → V_A, không có usable V_A; pre-auth off; KDC/policy cho request; recovery thành công trong budget; bí mật hợp lệ và auth accepted; group/token usable | Đủ: material → recovered secret → usable V_A → effective DA, chỉ đạt checkpoint; pre-auth required hoặc auth rejected: blocked tại gate tương ứng; recoverability/validity thiếu: indeterminate, không confirmed DA; chưa có admin_control(C0) |
| Đoạn cuối tới tài sản C0, synthetic oracle H_DC tương đương; SEAMLESS còn conditional | Đã đạt usable V_A/effective DA; asset C0 cố định; mapping quyền tới C0, kênh quản trị, mạng/dịch vụ, authentication và endpoint authorization/admin execution context được khai báo riêng | Đủ tất cả: admin_control(C0), đạt final goal; mapping hoặc endpoint gate known false: blocked; thiếu evidence: indeterminate; cả hai ca vẫn có thể giữ checkpoint DA nhưng không xác nhận asset success |
| AS-REP counterfactual | Giữ graph và snapshot facts; chỉ đổi KDC reachability hoặc có/không bí mật đích hợp lệ trong initial/context; variant có bí mật hợp lệ bỏ qua recovery | KDC=false: không request; KDC unknown: conditional candidate; đã có valid secret: không crack lại; known false không bị assumption override; raw observed pre-auth không tùy tiện sửa thành false/true |
| Kerberoasting dự phòng, V_K → V_D | X controlled và U có Kerberos auth đúng scope; SPN V_K; request/recovery/auth gates; group chain; GenericAll reset V_D với directory/password policy; reset identity activation; DA token; cùng đoạn asset C0 như ca chính | Không usable auth U: nhánh request bị chặn nếu known false, unknown nếu thiếu; material không tự là V_K; reset rejected: blocked; thiếu token gate: indeterminate; DA chỉ là checkpoint, còn cần asset gates để đạt final goal; không reuse numeric ratings Week 3 cho recovery |
| RBCD kế tiếp, U_R → C_R, downstream synthetic tới quản trị dịch vụ | U_R usable + ACL ghi đúng thuộc tính; M có SPN/key do attacker kiểm soát; KDC support/policy; P có quyền trên dịch vụ C_R và không bị cấm delegate; request accepted, endpoint authorization | Đủ: branch-only delegation(M,C_R) → service identity(P,C_R,s) → tác động trên dịch vụ; known deny write/delegation: blocked; thiếu M/key/SPN hoặc service/P quyền: indeterminate; không tự có identity P toàn miền hoặc DA |

Synthetic oracle là normative logic test; SEAMLESS là integration/trace, không có exploit success oracle.
Tái sử dụng accepted-path/reachable-state sets của #175; không hardcode một exact path trừ khi uniqueness là phần của ca.
Không coi engine suite cũ hoặc việc đọc source BloodHound là kiểm chứng correctness kỹ thuật mới.
Trước đối chứng mới, chốt phiên bản, snapshot, initial capability, goal và fact policy giống nhau; Legacy queries kiểm candidate account/downstream, không trực tiếp so một attribute finding với whole-path prediction.
Nếu đo CE RBCD/relay/AD CS phải pin binary/source và collector compatible riêng; comparison boundary #195/#196 hiện không đủ cho những kỹ thuật này.

Sự kiện thành công toàn chuỗi là quyền quản trị trên tài sản đã chọn; thành công tới checkpoint DA phải được báo riêng, không thay xác suất hoặc impact của final goal.
Với F là foothold đã cho, S là scenario và E_i là thành công của một công việc mới: `P(thành công chuỗi này | F,S) = ∏ P(E_i | F,S,E_1,…,E_{i-1})`.
Quy tắc chuỗi không cần độc lập; đường dài chỉ thêm rủi ro khi thêm một sự kiện thành công bắt buộc, không khi chia nhỏ cùng công việc hoặc thêm hop nhóm.
Work units đề xuất cho ca AS-REP gồm request material theo owner/context, recovery theo bí mật/algorithm/budget, activation theo identity/context và execution trên asset/context nếu là công việc mới; membership là entitlement thụ động, không một lần exploit.
Một secret dùng lại, nhiều SPN cùng key, điều kiện KDC đã nằm trong S hoặc tiền tố đều không được nhân lại; outage/retry mới thực sự cần horizon/model riêng.
Không gộp hai identity activation khác nhau hoặc mọi request tới mọi target thành một work unit; khử trùng theo ý nghĩa, scope và causal parents, không chỉ theo chuỗi ID.
Không thêm penalty chiều dài/detection nếu đã nằm trong success event; không cộng P các đường chung tiền tố như độc lập.
Hiện recovery probability, effort và impact score mới đều **chưa chấm**; ghi hậu quả định tính không là rating số, không lấy lại bounds Week 3.

## F. Tích hợp theo Week 4-6, sau khi thống nhất hướng

**Giữ phần tìm đường hiện có; mở một lát dữ liệu → hành động → đường với gate rõ ràng.**
Đây là phân chia đề xuất sau B review và trao đổi mentor, không phải giao việc thay B hoặc lịch giờ công đã cam kết.
Ước lượng phạm vi từ kiểm dữ liệu: một flag AS-REP, ba công việc chủ động tới checkpoint, một đoạn entitlement và đoạn execution tới asset dùng gates đã có; RBCD cần thêm delegation/service scope và nhiều input ngoài snapshot nên không gộp vào lát đầu.
Chưa có estimate giờ/ngày đáng tin khi #174 chưa chốt abstraction/outcome; A/B ước lượng lại tại gate kiến trúc trước khi mở implementation tasks.

| Mốc / gói việc dự kiến | Tái sử dụng | Cần sửa hoặc thêm, owner và điều kiện hoàn tất |
| --- | --- | --- |
| Week 4, luận cứ và ca đầu | Report này, raw audit, pinned route V_A; golden contract | A: handoff fact/outcome và ca phân biệt checkpoint DA với final asset success; B review lựa chọn C0/gates; mentor trao đổi asset/evidence/abstraction và impact/assumptions trước mở rộng production |
| Week 4, projection đầu vào | Manifest loader, v3 adaptation, normalizer/provenance | B: contract node fact hoặc fact adapter riêng được version hóa, giữ true/false/missing/conflict và locator; cần contract/parser checks cho field mới; không invent canonical structural edge |
| Week 4, action/state và sinh đường | Immutable branch, applicability, actor handoff; search/top-K đã có | B: owner cho request/recovery/non-reset identity activation, attribute/capability trigger, scope/outcome được #174 chốt; nối asset gate qua mapping được review; A review causal/work-unit boundary; không cấp usable identity chỉ vì cracking applicable |
| Week 4, kiểm tính hợp lý | #175 harness/oracle, Week 3 resource gates cho đoạn cuối | B: implement reviewed cases; A: so trace với kỳ vọng độc lập; đủ/sai/unknown/counterfactual/truncation, graph không mutate; thiếu recovery hoặc asset mapping/gates không xác nhận final reachability dù checkpoint có thể đã đạt |
| Week 5, đối chứng và nút thắt | Accepted Legacy input/reproduction và ranking interface | B: run comparison theo scope mới đã pin; A: phân tích khác biệt, choke point trên cùng final asset goal tại acquisition/recovery/auth, privilege downstream hoặc asset execution; unknown/unrated tách confirmed; sensitivity chỉ khi có ratings được review |
| Week 6, demo/báo cáo | CLI/visualization và evidence packaging hiện có | B: demo tái lập; A: giải thích conditions, assumptions, impact và giới hạn; không trình diễn giá trị synthetic như exploit trên SEAMLESS |

Nếu input/gate recovery hoặc #174 chưa chốt kịp Week 4, dừng ở candidate material/checkpoint + đường tới asset có điều kiện và báo indeterminate/unrated, không báo final success; không trì hoãn tìm đường/top-K hiện hành để triển khai tất cả ứng viên.
RBCD chỉ vào task riêng khi B xác nhận scenario đủ scope M/SPN/key/write/service/P và không làm trượt Week 5-6.
Relay/AD CS chỉ reconsider khi có manifest/input hợp lệ bổ sung; không mở rộng collector trong PR docs này.

## G. Nguồn và giới hạn còn lại

**Kết luận này đủ để review lựa chọn, chưa đủ để chấp nhận tham số hay tuyên bố khai thác.**
Chưa chạy request/crack/S4U/relay, chưa đo tần suất và chưa có đối chứng BloodHound cho kỹ thuật mới.
Collector binary revision, deny/access-mask đầy đủ, runtime policy và recoverability vẫn chưa biết; nguồn động pin theo ngày đọc 06/10/2026, không tự là accepted production evidence.
B cần review DCSync identity/closure, RBCD scope, lựa chọn AS-REP và giao diện; mentor cần trao đổi cách hiểu feedback, asset cụ thể, mức evidence/abstraction, target impact và mức giả định được phép; đích cuối là tài sản đã được ghi nhận trong định hướng 29/09.
Giữ #200/#192 mở chờ review/trao đổi; không đóng #174 hoặc nhận implementation của B.

| ID | Nguồn đã đọc / pin | Dùng để chứng minh |
| --- | --- | --- |
| K1 / K2 | [MITRE Kerberoasting](https://attack.mitre.org/techniques/T1558/003/), v1.3; [AS-REP](https://attack.mitre.org/techniques/T1558/004/), v1.2; đều modified 24/10/2025 | Mechanism, prerequisites/material; procedure examples không là tần suất |
| K3 / K4 | [Microsoft SPN](https://learn.microsoft.com/en-us/windows/win32/ad/service-principal-names); [Session Tickets](https://learn.microsoft.com/en-us/windows/win32/secauthn/session-tickets) | Owner service/key, ticket subject, scope và validity |
| K5 / K6 | [MS-ADTS UAC bits](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/dd302fd1-0aa7-406b-ad91-2a6b35738557), updated 08/04/2025; [Protected Accounts](https://learn.microsoft.com/en-us/windows-server/security/windows-authentication/how-to-configure-protected-accounts) | Pre-auth/delegation flags; policy gates, không infer entropy |
| B3 | [Legacy PrebuiltQueries](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/components/SearchContainer/Tabs/PrebuiltQueries.json) | Query/attribute/pathfinding source tại 4.0.3 |
| N1 / N2 | [MITRE DCSync](https://attack.mitre.org/techniques/T1003/006/), v1.1, modified 24/10/2025; [Microsoft MS-DRSR permission check](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-drsr/15bbda52-7742-4ce3-9327-018647b0fc26), updated 21/11/2025 | Replication secrets; cùng actor/NC rights, request-dependent restrictions |
| N3 | [SpecterOps DCSync](https://bloodhound.specterops.io/resources/edges/dc-sync); [4.2 announcement, 03/08/2022](https://specterops.io/blog/2022/08/03/introducing-bloodhound-4-2-the-azure-refactor/) | Post-processing và version boundary; không coi Legacy 4.0.3 là 4.2 |
| N4 / N5 | [Microsoft RBCD attribute](https://learn.microsoft.com/en-us/windows/win32/adschema/a-msds-allowedtoactonbehalfofotheridentity); [Kerberos constrained delegation](https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-constrained-delegation-overview); [Elad Shamir, Wagging the Dog, 28/01/2019](https://eladshamir.com/2019/01/28/Wagging-the-Dog.html) | Descriptor access check, resource scope, S4U prerequisites; lab mechanism không là campaign frequency |
| N6 | [AllowedToAct](https://bloodhound.specterops.io/resources/edges/allowed-to-act), [AddAllowedToAct](https://bloodhound.specterops.io/resources/edges/add-allowed-to-act), [GenericWrite](https://bloodhound.specterops.io/resources/edges/generic-write), [WriteAccountRestrictions](https://bloodhound.specterops.io/resources/edges/write-account-restrictions) | Phân biệt quyền sửa và delegation hiện có; SPN/controller/protection gates |
| N7 / N8 | [Research gốc forest trusts, 20/02/2019](https://blog.harmj0y.net/redteaming/not-a-security-boundary-breaking-forest-trusts/); [CoerceToTGT](https://bloodhound.specterops.io/resources/edges/coerce-to-tgt); [v6.3, 12/12/2024](https://specterops.io/blog/2024/12/12/unwrapping-bloodhound-v6-3-with-impact-analysis/) | TGT acquisition dưới control/coercion/delegation; BHE impact và CoerceToTGT version |
| N9 | [MITRE relay T1557.001](https://attack.mitre.org/techniques/T1557/001/), v2.0, modified 12/05/2026; [SpecterOps relay research, 08/04/2025](https://specterops.io/blog/2025/04/08/the-renaissance-of-ntlm-relay-attacks-everything-you-need-to-know/) | Destination-specific signing/channel-binding/coercion/rights; collection và CE/BHE missing-data policies khác nhau |
| N10 | [Microsoft KB5005413](https://support.microsoft.com/en-us/servicing/os/windows-server/2021/07/kb5005413-mitigating-ntlm-relay-attacks-on-active-directory-certificate-services-ad-cs); [MSRC 09/12/2024](https://www.microsoft.com/en-us/msrc/blog/2024/12/mitigating-ntlm-relay-attacks-by-default) | Web enrollment/EPA, defenses và quan sát thực tế; OS/default không thay live policy |
| N11 / N12 | [SpecterOps Certified Pre-Owned, 17/06/2021](https://specterops.io/blog/2021/06/17/certified-pre-owned/); [ADCSESC1](https://bloodhound.specterops.io/resources/edges/adcs-esc1); [CoerceAndRelayNTLMToADCS](https://bloodhound.specterops.io/resources/edges/coerce-and-relay-ntlm-to-adcs) | Enrollment/misconfiguration → cert → identity; ESC1 và ESC8 là cơ chế khác nhau, không nhãn AD CS chung |

---

## Bản sơ bộ ngày 05/10/2026 - giữ làm lịch sử

Phần dưới giữ nguyên nội dung đã merge qua #193; trạng thái issue và baseline trong phần đó là thời điểm 05/10, không là trạng thái hiện hành.
Ưu tiên Kerberoasting trong bản sơ bộ được thay bằng lựa chọn có điều kiện ở phần ngày 06/10 phía trên.
Câu hỏi lịch sử về việc kết thúc ở usable identity/DA hay tài sản cũng được thay thế: định hướng hiện hành giữ DA là checkpoint và final goal là tài sản cụ thể.

# Bằng chứng cho đề xuất Week 4 của TTS A

Ngày đối chiếu: 2026-10-05, Asia/Ho_Chi_Minh.
Refs [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192), [#174](https://github.com/nairyuuu/ad-weighted-graph/issues/174), [#175](https://github.com/nairyuuu/ad-weighted-graph/issues/175).
Đây là phụ lục nghiên cứu của [bản đề xuất ngắn](week4-prediction-proposal.md), không là ADR hoặc quyết định thay schema.
Mọi tên state/action mới trong bảng dưới là ký hiệu đề xuất, không phải API đã có.

## 1. Authority, revision và phạm vi A/B

Baseline mã nguồn là `develop` tại `83401603ccfe84dd4b99bd2fe0c14e404d30b656`, sau PR #188 cho golden scenarios.
Contract là 1.3.0, semantic catalog là 0.3.
Issue #174 và #175 vẫn mở lúc đọc; mã và tài liệu liên quan đã có trên baseline không đồng nghĩa nghiên cứu đã được nghiệm thu/đóng issue.

| Nguồn yêu cầu | Nội dung dùng trong đề xuất | Ranh giới kết luận |
| --- | --- | --- |
| [Đề bài gốc](../00_todo.md), mục 1, 2.1-2.3, 5-6 | Cạnh từ thuộc tính; kỹ thuật/điều kiện; đường chi phí thấp nhất tới DA; đối chứng; chỉ phân tích dữ liệu | Không yêu cầu mô phỏng đầy đủ Kerberos hoặc thực hiện exploit trên hệ thống thật |
| [Ghi nhận feedback](weighting-direction.md#định-hướng-mentor-ngày-2026-09-29-và-phân-biệt-tầng-quyết-định), ngày 29/09 | Dự đoán dựa vào cấu trúc/kỹ thuật/giả định; khả năng thành công và tác động toàn đường | Đây là ghi nhận trong repo, không có biên bản mentor mới trong lần nghiên cứu này; không suy thành phê duyệt công thức hay con số |
| #192 | Nghiên cứu bước tạo năng lực mới dù chưa có cạnh quyền; Kerberoasting/AS-REP là ứng viên | Đây là cách diễn giải cần trao đổi với mentor, chưa chốt phạm vi triển khai |
| #174, bình luận owner ngày 02/10 | So sánh TGT/service ticket, usable authentication context, hoặc transition không materialize ticket | B phụ trách vocabulary, predicate, effects và kiến trúc prediction; A cung cấp use case và nhận xét |
| #175, bình luận owner ngày 02/10 | Synthetic là correctness oracle; SEAMLESS là integration/evidence trace; không lấy ratings Week 3 làm golden | B phụ trách schema/harness/oracle; A đề xuất tiêu chí review, không thêm fixtures trong PR này |

Bridge #180 xử lý thiếu sót trong scenario Week 3 và đã có trong baseline qua #181/#182.
Không dùng mô tả catalog 0.2 cũ để kết luận rằng hiện chưa có actor handoff/xác thực.
Không nghiệm thu lại Week 3, chỉnh engine, hoặc đổi ownership B trong nghiên cứu này.

## 2. Đối chiếu hành vi hiện hành

Các liên kết mã dưới đây được pin theo baseline; đường dẫn local thuận tiện để đọc nhưng có thể thay đổi sau nghiên cứu.

| Thành phần | Bằng chứng mã tại revision đã pin | Kết luận có giới hạn |
| --- | --- | --- |
| Đầu vào node | [`_node_attributes`](https://github.com/nairyuuu/ad-weighted-graph/blob/83401603ccfe84dd4b99bd2fe0c14e404d30b656/src/parser/normalizer.py#L362) giữ id/kind/label/domain/is_boundary và enabled/admincount/distinguishedname | Raw SPN, hasspn, dontreqpreauth chưa được projection này giữ; raw có dữ liệu không đồng nghĩa evaluator nhận được |
| Cách sinh bước | [`generate_attack_paths`](https://github.com/nairyuuu/ad-weighted-graph/blob/83401603ccfe84dd4b99bd2fe0c14e404d30b656/src/engine/search.py#L336) lấy canonical relationships, state permissions/relationships, withheld evidence và hai capability triggers | Đã có bước suy ra quyền từ WriteDacl/GenericAll và xác thực từ reset; chưa có trigger chỉ từ SPN/pre-authentication |
| Catalog | [Catalog 0.3](../../configs/attack_semantics.yml), 13 owner; [`candidates`](https://github.com/nairyuuu/ad-weighted-graph/blob/83401603ccfe84dd4b99bd2fe0c14e404d30b656/src/engine/semantics/evaluator.py#L49) lọc theo relationship và node kinds | Không có owner xin dữ liệu roasting/dò ngoại tuyến; thiếu kỹ thuật khác với xác suất kỹ thuật bằng 0 |
| State | [`AttackState`](https://github.com/nairyuuu/ad-weighted-graph/blob/83401603ccfe84dd4b99bd2fe0c14e404d30b656/src/engine/semantics/state.py#L11) có credential_material, authentication_control, reset_password_control, usable_identity | Không có state dữ liệu để dò hoặc phân loại TGT/service ticket; credential_material chỉ là tập account IDs, chưa mô tả loại bí mật/khả năng dùng |
| Xác thực scoped | [`AuthenticationControl` gate](https://github.com/nairyuuu/ad-weighted-graph/blob/83401603ccfe84dd4b99bd2fe0c14e404d30b656/src/engine/semantics/evaluator.py#L148) kiểm reset_password_control; [bridge](week3-semantic-bridge.md) mô tả acquire_reset_identity | Không thể gán bí mật từ roasting vào reset_password_control để đi tắt; đó là qualifier dành riêng cho reset |
| Predicate/effect | [Evaluator](../../src/engine/semantics/evaluator.py), [immutable transitions](../../src/engine/semantics/transitions.py) | Known-false chặn; thiếu runtime giữ indeterminate; chỉ applicable mới apply effects; applicability không là bằng chứng thực hiện/thành công ngoài đời |
| Xếp hạng | [`assess_candidate_program`](https://github.com/nairyuuu/ad-weighted-graph/blob/83401603ccfe84dd4b99bd2fe0c14e404d30b656/src/engine/ranking/assessment.py#L39) khử trùng work units và nhân bounds theo toàn tiền tố | Có nền tảng chống đếm lặp theo ID; không tự kiểm được hai ID khác nhau có cùng ý nghĩa sự kiện; thiếu bounds hoặc unknown gate không có P hợp lệ |
| Golden hiện có | [Tài liệu #175](attack-scenarios.md), [tests](../../tests/test_attack_scenarios.py) | Bao phủ catalog 0.3 và counterfactual prediction; không xác nhận correctness của roasting chưa có |

Giới hạn cần diễn đạt chính xác: engine không chỉ đi theo cạnh có sẵn, vì đã có branch state và capability-derived transitions.
Nhưng phạm vi các trigger hiện hành chưa có thuộc tính SPN/pre-authentication, nên phần mở rộng không chỉ là thêm trọng số vào cùng graph.
Nếu không sinh được bước U → dữ liệu của V, Dijkstra/Top-K không thể tự tìm lại bước đó từ việc sửa công thức xếp hạng.

## 3. Dữ liệu đã kiểm tra, dữ liệu thiếu và provenance

Phát lại công cụ audit hiện có, không sửa parser:

```bash
.venv/bin/python scripts/audit_seamless_raw.py \
  --raw-dir data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --output reports/generated/week4-192/raw-field-inventory.json \
  --markdown-output reports/generated/week4-192/raw-field-audit.md
```

Kết quả exit 0: `status=generated`, 195 field, snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
Số liệu dưới khớp [raw-field audit đã commit](seamless-raw-field-audit.md), mục User / Properties; inventory generated giữ local theo policy repo.
Không đưa danh tính, SPN thật, bí mật hoặc raw exports vào PR.

| Dữ liệu/điều kiện | Quan sát và mức có thể dùng | Thiếu gì trước khi đưa vào prediction |
| --- | --- | --- |
| User SPN | `hasspn` và `serviceprincipalnames` có mặt 2.493/2.493 record; 51 có hasspn=true và mảng không rỗng; 2.442 mảng rỗng | Projection có provenance; đối chiếu cờ với danh sách; kiểm SPN gắn account nào, scope và completeness; chưa suy ra service sống hoặc ticket issuance |
| Pre-authentication | `dontreqpreauth` có mặt 2.493/2.493; true 176, false 2.317 | Mapping collector boolean về predicate bằng nguồn kỹ thuật; false chặn nhánh AS-REP không pre-auth khi dữ liệu đáng tin trong scope, thiếu field là unknown |
| Enabled | Có 2.490 true, 3 false; parser giữ boolean này | Enabled không chứng minh đăng nhập được, không thay account restrictions hoặc authentication policy |
| Password metadata | pwdlastset/pwdneverexpires hiện có trong audit raw | Không suy mật khẩu yếu, entropy, thuật toán ticket hoặc xác suất crack từ tuổi mật khẩu; không tái sử dụng userpassword thành credential đã xác minh |
| Quyền sau xác thực | Canonical MemberOf/AdminTo/ACL có provenance và semantics | Kiểm quyền hiệu lực đúng actor/context, endpoint và mục tiêu; chưa truy tìm chuỗi roasting thật nào từ 51 tài khoản |
| Xác thực ban đầu/KDC | Có thể khai báo initial state và runtime facts trong synthetic scenario | Snapshot không chứng minh U có xác thực dùng được, đường mạng, KDC chấp nhận cấp vé hoặc hết hạn chưa |
| Dò ngoại tuyến | Nguồn kỹ thuật xác nhận cơ chế | Chưa có dữ liệu đo entropy, etype thực tế, tập đoán, compute budget, thời hạn hay kết quả crack; không có numeric bounds đáng tin cho kỹ thuật mới |

Các số đếm User là **raw record counts**, không là số canonical principal, số đường tới DA, số host bị chiếm hoặc giao của SPN với enabled/đặc quyền.
Audit không có collection-status metadata, nên cần policy completeness; array rỗng không tự chứng minh absence ngoài phạm vi collector.
Computer cũng có SPN trong raw, nhưng phạm vi ứng viên nhỏ chỉ xét User service account; chưa mở rộng cracking computer/gMSA hoặc mọi cơ chế xác thực.

Đề xuất đầu vào giữ ba nguồn riêng: snapshot field có locator/hash, quy tắc kỹ thuật có nguồn, runtime assumption có người khai báo/scope/thời hạn.
Kết quả suy ra giữ trong branch state, truy được causal parent và các assumptions; canonical graph giữ nguyên.
Observed attack telemetry không là prerequisite bắt buộc cho prediction.

## 4. Chuỗi kỹ thuật: điều kiện và kết quả từng bước

Nguồn [K1] và [K2] xác nhận roasting là lấy dữ liệu mã hóa để thử đoán bí mật ngoại tuyến.
Nguồn Microsoft [K3]-[K6] giải thích SPN, ticket, account pre-auth và các hạn chế cấp vé.
Không suy ra cần reset/GenericAll trên V để request ticket cho SPN của V trong ví dụ Kerberoasting thông thường.
TGS/service ticket nhận bằng U xác thực U với dịch vụ; nó không phải TGT hoặc xác thực của V.

Trong ví dụ, U/V/X/H là tên **tổng hợp**, không phải danh tính trong SEAMLESS.
Graph chỉ có V → H (`AdminTo`), có thể thêm MemberOf trung gian nếu được review; không thêm U → V.
Giả định attacker điều khiển X và có usable authentication của U được khai báo riêng, không suy từ control(X).

| Kỹ thuật/bước | Structural/attribute evidence | Required state và runtime assumptions | Kết quả nếu thành công | False/unknown và ranh giới |
| --- | --- | --- | --- | --- |
| Kerberoasting: request dữ liệu service ticket | SPN đăng ký trên V; identity/domain mapping; không cần quyền U → V | X có khả năng gửi request; U có Kerberos authentication đủ cho TGS exchange; KDC reachable; request được policy chấp nhận | Dữ liệu ticket mã hóa bằng khóa dịch vụ của V để dò; ghi target V và provenance | Known-false request gate: blocked; missing: indeterminate; không suy thành credential_material(V) dùng được |
| AS-REP Roasting: request dữ liệu AS-REP | Tên account V đã biết, dontreqpreauth=true đáng tin trong scope | Khả năng gửi request tới KDC; KDC chấp nhận account/request; không đòi U có TGT ở nhánh không pre-auth | Dữ liệu phản hồi mã hóa để dò bí mật V | Pre-auth required=true chặn nhánh này; thiếu thuộc tính giữ unknown; nhận phản hồi không tự tạo usable_identity(V) |
| Dò ngoại tuyến, dùng cho cả hai ứng viên | Dữ liệu có owner và thuật toán thích hợp | Có dữ liệu để dò; mô hình tập đoán, tài nguyên và thời hạn; không cần host/service V đang online trong bước offline | Bí mật khôi phục có owner/type nếu tìm được | Có dữ liệu chỉ làm thao tác dò khả dụng; chưa biết recoverability không được apply effect “đã có bí mật”; hết ngân sách không thành công là kết quả trong horizon, không phủ định mãi mãi |
| Xác thực V sau khôi phục | Identity V, account flags/policy liên quan | Bí mật phù hợp cơ chế xác thực, còn hợp lệ; KDC/dịch vụ reachable; account được chấp nhận trong context đã chọn | usable identity/capability của V, cho phép actor handoff có nguồn causal | Disabled/rejected trong scope: blocked; thiếu validity/policy: unknown; không có host control chỉ từ authentication_control |
| Hành động quản trị H | Quyền V → H hoặc quyền nhóm hiệu lực có căn cứ | V dùng được đúng context; mạng/listener; endpoint authorization; phiên cho phép thực thi quản trị | admin_control(H) theo owner được chọn, đạt mục tiêu nếu H đúng target | AdminTo không thay mọi runtime gates; CanRDP/CanPSRemote không mặc nhiên là admin_control; quyền trên V không tự là quyền trên H |

Tên gợi ý `crackable_material(V, artifact_type)` chỉ biểu thị dữ liệu đầu vào dò; không dùng tên này như một API đã chốt.
Mô hình được review cần phân biệt ít nhất: có dữ liệu để dò, có bí mật phù hợp xác thực, có identity dùng được, có quyền/thực thi trên tài nguyên.
`authentication_control` không nên trở thành chỗ chứa mọi thứ được gọi là “credential”.
Thiếu phép chuyển từ bí mật khôi phục sang usable identity không được bù bằng cách giả nó là kết quả reset.

Với step prediction, `applicable` nghĩa có thể thực hiện dưới các điều kiện khai báo, không bảo đảm thành công.
Nếu B giữ kiến trúc apply effect khi applicable cho branch thành công giả định, phải khai báo rõ điều kiện/giả định outcome cho bước crack, hoặc thiết kế cách biểu diễn outcome riêng.
Ca không có căn cứ recoverability chỉ khẳng định đã có dữ liệu để dò; không được trả confirmed reachability tới V/H.
Quyết định chính thức về cách apply success effects là phần #174 của B.

AES không là bằng chứng roasting bất khả thi; cần thuật toán thực tế và mức khó đoán của bí mật để đánh giá ngân sách.
Ngược lại, RC4 hoặc tuổi mật khẩu cũng không là bằng chứng crack sẽ thành công.
Hết hạn ticket không tự xóa dữ liệu đã thu được để dò offline; nhưng dùng identity/ticket sau đó vẫn phải xét policy, validity và thay đổi mật khẩu trong horizon.
Current additive state chưa mô hình hóa expiry/revocation; không kéo kết luận vượt evaluation window đã khai báo.

## 5. Ba abstraction xác thực cần B review

Đối chiếu bình luận #174; không tự thêm `kerberos_ticket` vào schema.

| Lựa chọn | Fidelity cần cho prediction | Audit và evidence | Kích thước state/giới hạn | Nhận xét của A |
| --- | --- | --- | --- | --- |
| Explicit TGT/service_ticket | Phân biệt đúng issuer, chủ thể, dịch vụ, thời hạn và kiểu sử dụng | Tốt khi path phụ thuộc loại ticket; cần SPN/service scope, flags, etype, key validity, time policy | Nhiều artifact theo identity/service/context/time; dễ mở rộng thành mô phỏng protocol nếu thêm mọi chi tiết | Chỉ chọn nếu use case cần phân biệt ticket để quyết định applicability; không mặc định cần cho mọi ranking |
| Generic usable_authentication_context | Đủ để nói actor V có thể xác thực trong scope cho bước sau | Dùng state hiện hành usable_identity(V,context) làm điểm tham chiếu; ghi cơ chế/owner/assumptions trong trace | Ít state hơn; cần scope và lifetime rõ để không cho phép dùng trên mọi endpoint | Ứng viên ưu tiên của A cho scope nhỏ; vẫn tách dữ liệu để dò và bí mật khôi phục ở bước trước |
| Không materialize ticket; transition thẳng từ authentication_control sang capability của action tiếp | Đủ nếu không có action nào cần biết ticket cụ thể | Audit qua prerequisite/effect/causal parent; vẫn phải giữ gate xác thực, không gộp ngầm với quyền tài nguyên | Ít artifact, nhưng capability theo action có thể phân mảnh hoặc lặp xác thực nếu đặt ID sai | Có thể dùng nếu trace và work units giữ tương đương; credential khôi phục cần qualifier hợp lệ, không mượn reset_password_control |

Bridge #180 đã chọn `usable_identity` cho reset scenario, nhưng chưa chốt abstraction tổng quát cho mọi nguồn credential và mọi protocol.
Đề xuất của A: ưu tiên khả năng giải thích bốn giai đoạn trong mục 4; chỉ thêm chi tiết ticket khi nó thay đổi kết quả applicability hoặc khả năng audit.
Đây là input cho B, không thay catalog/schema trong PR #192.

## 6. BloodHound đã giải quyết gì, nhóm định kiểm chứng gì?

### Đối chiếu theo phiên bản/chức năng

Đã đọc source upstream **BloodHound Legacy 4.0.3**, tag revision `b54c418ef83fe5856ae3fe6317a20f2368a6378c`, trùng revision dùng trong [nghiên cứu compatibility của repo](seamless-legacy-pre41-compatibility.md).
[PrebuiltQueries.json](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/components/SearchContainer/Tabs/PrebuiltQueries.json) có:

- `List all Kerberoastable Accounts`: lọc User hasspn=true, dòng 314-320.
- `Shortest Paths to Domain Admins from Kerberoastable Users`: lấy tài khoản hasspn=true làm đầu đường, dòng 124-139.
- `Find Kerberoastable Members of High Value Groups`: lọc SPN và membership, dòng 304-310.
- `Find AS-REP Roastable Users (DontReqPreAuth)`: lọc dontreqpreauth=true, dòng 354-360.

Các query này không cần cạnh quyền từ U tới V để liệt kê V; query tìm đường bắt đầu ở V.
Chỉ từ source các query này, không kết luận rằng toàn bộ sản phẩm Legacy/CE/Enterprise không có cách khác để phân tích roasting.
Không có kết quả chạy UI/query roasting hoặc benchmark semantic prediction mới trong PR này.

[Tài liệu SpecterOps hiện hành](https://bloodhound.specterops.io/resources/edges/traversable-edges) áp dụng CE/Enterprise, mô tả traversable edges và post-processing kết hợp GetChanges/GetChangesAll thành DCSync.
[GenericAll](https://bloodhound.specterops.io/resources/edges/generic-all) mô tả nhiều cách abuse, gồm targeted Kerberoasting.
Targeted Kerberoasting có điều kiện quyền sửa SPN, khác ví dụ **SPN đã có nhưng không có quyền U → V** trong đề xuất.
Không lấy tài liệu CE hiện hành làm bằng chứng tính năng đã thử trong Legacy 4.0.3; không suy “BloodHound chỉ đi theo cạnh quyền” hoặc “nhóm phát minh Kerberoasting”.

### Đóng góp và kế hoạch kiểm chứng sau review

Đóng góp dự kiến: explanation trace từ foothold tới dữ liệu/bí mật/xác thực/quyền; ba trạng thái applicability; runtime assumptions không mutate snapshot; C/P/I theo toàn chuỗi với chống đếm lặp.
Tính mới chỉ được bảo vệ sau đối chứng chức năng cụ thể và tài liệu liên quan, chưa phải kết quả đã chứng minh.

| Kiểm chứng đề nghị với B | Oracle/đối chứng cần thấy | Không được tuyên bố |
| --- | --- | --- |
| Synthetic G không có U → V; V có SPN và quyền V → H | Với initial usable U và các gate/giả định outcome đủ, có causal trace tới dữ liệu, bí mật, usable V, rồi H | Không lấy candidate/rating Week 3 hoặc actual engine output để sinh expected |
| Same G, thay state U hoặc network/policy | Bỏ usable U chặn nhánh Kerberoasting thông thường; KDC known-false chặn request; thiếu fact giữ indeterminate | Unknown không là negative fact hay effect thành công; budget exhaustion không là no-path toàn đồ thị |
| Không biết crack outcome hoặc xác thực V bị từ chối | Có thể đến dữ liệu để dò nhưng không confirmed reachability tới usable V/H | Ticket/dữ liệu không đồng nghĩa chiếm tài khoản; crack successful không đồng nghĩa host admin |
| AS-REP comparison | dontreqpreauth=true và đủ gate không bắt buộc usable U; false chặn; missing unknown | Không nhân chung prerequisite TGT của Kerberoasting cho AS-REP |
| Split/merge action, nhiều SPN cùng V, dùng lại bí mật/context | Same success event và causal work không bị chấm lặp; phân biệt retry thật với tham chiếu state đã có | Không ép mọi valid path có cùng chuỗi ID hoặc cùng số hop |
| SEAMLESS integration | Manifest/projection/owner/predicate/assumption/effect đều truy nguồn; fields xung đột/thiếu hiện rõ | Không coi dataset synthetic là tần suất tấn công thực tế hoặc golden oracle số |
| BloodHound comparison | Pin version/collector/snapshot/target/edge filter; so tập account thuộc tính và downstream routes; ghi riêng initial foothold và giả định của nhóm | Không dùng count equality, danh sách tài khoản hay shortestPath từ V làm oracle thành công từ U |

B giữ quyền thiết kế schema/harness và cách assert accepted reachable-state/path sets ở #175.
A cung cấp luận cứ và review expected outcomes sau khi hướng được chấp thuận; chỉ tách task triển khai sau review đề xuất.

## 7. Xác suất toàn đường và chống đếm lặp

[ADR-0013](../adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md), [interface](path-ranking-interface-specification.md) và mã assessment hiện dùng conditional prefix bounds.
Gọi F là foothold đã cho, S là kịch bản cố định, Eᵢ là một thành công cần thiết mới trong chương trình công việc:

$$P(E_1,\ldots,E_k\mid F,S)=\prod_{i=1}^{k}P(E_i\mid F,S,E_1,\ldots,E_{i-1}).$$

Đây là chain rule, không là phép nhân các marginal probability độc lập.
Số kỹ thuật, số cạnh/hop và số work units không nhất thiết bằng nhau.
Nếu các bounds cùng điều kiện và có căn cứ, tích cận dưới/cận trên cho khoảng toàn chuỗi trong kịch bản đó; không gọi đây là confidence interval thống kê khi chỉ có nhận định chuyên gia.
Nguồn cơ chế AD không cung cấp bounds cho crack, reset hoặc WinRM.

### Vì sao đường dài có thể nhỏ dần?

Giữ nguyên tiền tố và bổ sung một sự kiện bắt buộc, hệ số có điều kiện thuộc [0,1] khiến xác suất không tăng.
Đây là đúng với mục tiêu “tất cả sự kiện trong chuỗi thành công”, không là lý do tự thêm penalty theo độ dài.
Hai đường khác kỹ thuật có thể có các conditional bounds khác nhau, nên đường dài không mặc nhiên kém đường ngắn.
Nếu một thao tác bị tách thành hai phần tương đương, phải có `P(E)=P(Ea)P(Eb|Ea)` dưới cùng F/S; không sao chép P(E) cho cả Ea và Eb.
Các nhãn passive/membership hoặc bước chỉ tham chiếu state không tạo một lần thành công ngẫu nhiên mới.

### Quy tắc review bảng chấm

1. Chọn success event, horizon/retry budget và initial capability trước khi chấm.
   Không nhân xác suất giành lại foothold đã nằm trong F.
2. Gắn event/work unit với owner, target, context và causal parent.
   Nhiều SPN của cùng V không tự là nhiều lần crack bí mật V; dùng lại material/secret/auth context trong scope không tự là thử lại.
3. Phân biệt uncertainty của fact với chance của một lần thử.
   Nếu availability KDC đã được giả định trong S, không nhân lại một “xác suất KDC tồn tại” cho mỗi lần request.
   Nếu thực sự có outage mới theo thời gian, cần model và evidence tương ứng, không deduplicate mọi rủi ro theo tên.
4. Chấm sau tiền tố đầy đủ; bước xác thực V phải hiểu rằng bí mật V đã khôi phục.
   Không nhân lại khả năng crack ở login hoặc quyền quản trị sau khi đã dùng như một event riêng.
5. Không thêm detection/penalty độ dài ngoài bảng nếu nó đã nằm trong định nghĩa success của các event.
   Detection chỉ là failure nếu kịch bản quy định bị phát hiện/ngăn chặn làm thất bại; telemetry tồn tại không đồng nghĩa bị chặn.
6. Không cộng P các đường chung tiền tố; muốn tính “ít nhất một đường thành công” cần mô hình union và phụ thuộc riêng.
   Không nhân P vào mỗi hop rồi lại nhân toàn đường thêm lần nữa để gọi là risk.
7. Thiếu conditional bounds giữ `unrated`; known-false gate giữ blocked và thiếu fact giữ unknown.
   Impact là hậu quả tại success event/tài sản đích; C là công sức riêng, không là thời gian đo hoặc xác suất.

Mã hiện khử trùng persistent work-unit IDs và dừng replay ở lần đầu đạt goal, nhưng chất lượng định nghĩa sự kiện/ID và bảng bounds vẫn là trách nhiệm review.
Không tái sử dụng trực tiếp khoảng xác suất Week 3 cho cracking: technique, điều kiện, dữ liệu và ngân sách khác nhau.

## 8. Nguồn kỹ thuật đã đọc

Truy cập 2026-10-05; nguồn động cần pin/review lại nếu làm triển khai sau này.
Nguồn chứng minh cơ chế, không chứng minh đường đã xảy ra trong SEAMLESS hoặc xác suất thực nghiệm.

| ID | Nguồn chính thức | Luận điểm dùng / giới hạn |
| --- | --- | --- |
| K1 | [MITRE ATT&CK T1558.003](https://attack.mitre.org/techniques/T1558/003/), phần description | Service-ticket material và offline guessing; không bảo đảm phục hồi mật khẩu |
| K2 | [MITRE ATT&CK T1558.004](https://attack.mitre.org/techniques/T1558/004/), phần description | Không pre-auth cho phép request AS-REP material; khác initial-auth prerequisite của Kerberoasting thông thường |
| K3 | [Microsoft: Service principal names](https://learn.microsoft.com/en-us/windows/win32/ad/service-principal-names) | SPN nối service instance với account; không chứng minh service đang online |
| K4 | [Microsoft: Session Tickets](https://learn.microsoft.com/en-us/windows/win32/secauthn/session-tickets) | Ticket mã hóa bằng server key, credentials/authenticator và expiry; không biến service ticket của U thành xác thực của V |
| K5 | [MS-ADTS 2.2.16 userAccountControl Bits](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/dd302fd1-0aa7-406b-ad91-2a6b35738557) | DR/ADS_UF_DONT_REQUIRE_PREAUTH 0x00400000; cần mapping collector field được review |
| K6 | [Microsoft: How to Configure Protected Accounts](https://learn.microsoft.com/en-us/windows-server/security/windows-authentication/how-to-configure-protected-accounts), Authentication policies | Tách AS/TGS exchange và restriction cấp vé; không giả mọi account có SPN đều luôn nhận ticket |
| K7 | [Microsoft: Kerberos authentication overview](https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-authentication-overview) | KDC, TGT và service authentication; không thay authorization gate trên tài nguyên |
| B1 | [SpecterOps: Traversable and Non-Traversable Edge Types](https://bloodhound.specterops.io/resources/edges/traversable-edges) | CE/Enterprise traversable/post-processing; không là kết quả benchmark Legacy |
| B2 | [SpecterOps: GenericAll](https://bloodhound.specterops.io/resources/edges/generic-all), Targeted Kerberoast | Kỹ thuật đã có trong abuse guidance; targeted SPN mutation khác ví dụ SPN đã tồn tại |
| B3 | [Legacy 4.0.3 prebuilt queries](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/components/SearchContainer/Tabs/PrebuiltQueries.json) | Pin chức năng/query cụ thể; source inspection không là execution evidence |

## 9. Kết luận và câu hỏi còn mở

Có căn cứ kỹ thuật cho việc nghiên cứu bước không cần cạnh quyền U → V, nhưng chưa có căn cứ để tuyên bố khai thác được 51/176 tài khoản hoặc gán P cho cracking.
Kerberoasting phù hợp minh họa khoảng trống attribute trigger; AS-REP là counterexample hữu ích về initial state.
Đề xuất chọn một scope hẹp sau review, giữ uncertainty và ownership B.

- Mentor có yêu cầu dự đoán bước tạo năng lực không có cạnh quyền từ foothold, hay chỉ xếp hạng downstream paths từ account đã coi là có thể chiếm?
- Chọn kỹ thuật nào trước và thành công kết thúc ở usable identity, DA checkpoint hay admin execution trên tài sản cụ thể?
- Cho phép giả định recoverability để kiểm logic tới đích tới mức nào; nếu thiếu dữ liệu crack thì sản phẩm báo unknown/unrated ra sao?
- Abstraction hiện hành usable_identity có đủ không; B có cần mở rộng credential qualifier, scope/lifetime hay outcome branching ở #174?
- Đối chứng Legacy 4.0.3 hay CE phiên bản cụ thể nào; tiêu chí khác biệt nào có thể đo và giải thích mà không overclaim novelty?

Các câu hỏi này là nội dung cần review/trao đổi; không là lý do gán mặc định, đổi catalog hoặc triển khai thay B trong PR tài liệu.
