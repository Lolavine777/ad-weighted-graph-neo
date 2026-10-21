# Scenario tối thiểu: từ quyền reset đến identity dùng được

Trạng thái: đề xuất kịch bản và hợp đồng dữ kiện cho [#140](https://github.com/nairyuuu/ad-weighted-graph/issues/140) và [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), cập nhật ngày 2026-09-29 sau feedback mentor.
Tiếp nối [brief E2E](week3-scenario-cost-evidence.md) và kết quả nghiên cứu PR #132 đã merge vào `develop`.
Đây là scenario contract ở mức đặc tả phân tích, chưa phải schema/API, catalog mới hoặc quyết định production profile.
Không sửa đổi phá vỡ Graph Contract v1.3.0 hoặc semantic catalog v0.2; mọi thay đổi triển khai sau review phải đánh giá version/migration của lớp tương ứng.
Các tên fact trong fixture dưới đây là ký hiệu cục bộ, không phải field được bổ sung vào `src/`.
Hiệu chỉnh sau PR #151 (giải quyết #150) ngày 2026-09-30: `designated_crown_jewel` chỉ là giả định về nhãn giá trị nghiệp vụ (business-value label), độc lập với nhãn mặt bằng kiểm soát kỹ thuật Tier0 và không tự cấp mức đánh giá tác động.
Các mức tác động Low, Medium, High, Critical cần có căn cứ nghiệp vụ (rationale) riêng cho hậu quả của biến cố thành công theo [path-ranking-model §2.1](path-ranking-model.md).
Mức đánh giá Critical trong các fixture nghiên cứu thuần túy là giả định mô phỏng (synthetic assumption), chưa phải là mức tác động được xác nhận trên môi trường SEAMLESS.

## Câu hỏi cần trả lời và định nghĩa mục tiêu

Ứng viên raw `Computer -> GenericAll -> User -> MemberOf -> Group` mới chứng minh có một đường cấu trúc trong projection.
Để dùng nó đánh giá khả năng thành công và chi phí, phải xác định rõ:
1. **Starting capability của máy bị chiếm (foothold)**: Điểm xuất phát của kẻ tấn công có những quyền năng và giới hạn gì.
2. **Target asset (tài sản đích)**: Tài sản hoặc thực thể trọng yếu nào cần bảo vệ.
3. **Thao tác / tác động đích (target operation / impact)**: Kẻ tấn công muốn thực hiện hành động cụ thể nào lên tài sản đích.
4. **Success event cho cả đường (end-to-end path success event)**: Biến cố thành công xảy ra khi chuỗi hành động hoàn tất thao tác đích dưới các giả định kịch bản.

| Mức | Điều kiện đạt | Không được suy thêm |
| --- | --- | --- |
| S0: cấu trúc | Có reference ACL và membership hợp lệ trong mô hình đầu vào | Chưa biết reset hoặc authentication có thực hiện được |
| S1: reset | Transition reset tạo `authentication_control` của user | Chưa có session/token sử dụng được ở mọi dịch vụ |
| S2: identity và entitlement dùng được | Identity user dùng được tại context đã chọn, cùng membership có hiệu lực tại context đó | Chưa chứng minh host admin, domain compromise hoặc một thao tác đặc quyền cụ thể |
| S3: thao tác đích | Action có resource, quyền cần thiết, channel và context rõ ràng đạt effect đã định nghĩa | Không mở rộng thành mọi quyền trong domain |

Vai trò của DA membership / S2:
- Việc đạt được quyền thành viên Domain Admins (hoặc S2: usable identity) chỉ đóng vai trò là **proxy hoặc intermediate checkpoint** đặc quyền cao trên đường tấn công.
- Trừ khi chính việc kiểm soát tài khoản DA là mục tiêu duy nhất của kịch bản, việc chạm tới nhóm DA không tự đồng nghĩa là đã hoàn thành mục tiêu tác động đích cuối cùng.
- Nếu kịch bản yêu cầu tác động phá hoại cụ thể (như DCSync hoặc can thiệp DC), mục tiêu phải được mở rộng lên S3 với thao tác rõ ràng.

## Starting capability của máy bị chiếm (Foothold boundary)

Điểm bắt đầu của mọi đường tấn công trong đồ thị nội bộ yêu cầu một định nghĩa foothold tường minh:
- **Ngữ cảnh thực thi cục bộ**: Kẻ tấn công được giả định đã có quyền kiểm soát máy tính bị chiếm (source computer).
- **Ranh giới tài khoản**: Trường hợp tiêu biểu là ngữ cảnh dịch vụ `LocalSystem` (hoặc local admin) trên máy trạm tham gia domain (domain-joined workstation).
- [Microsoft mô tả LocalSystem](https://learn.microsoft.com/en-us/windows/win32/ad/the-localsystem-account) khi truy cập tài nguyên mạng trong domain sẽ sử dụng danh tính tài khoản máy (`DOMAIN\COMPUTER$`).
- Khả năng này chỉ cung cấp network identity của computer account; nó không tự động cấp quyền admin trên máy khác hay quyền đặc quyền trên domain.
- **Biên đo lường chi phí**: Chi phí ban đầu để kẻ tấn công chiếm được máy tính xuất phát (ví dụ phishing, exploit lỗ hổng dịch vụ ngoài) được giả định đã hoàn thành và nằm ngoài phạm vi tính toán của đồ thị tấn công nội bộ (internal lateral movement graph).

## Nhận diện Target Candidate cụ thể từ snapshot SEAMLESS

Trong snapshot SEAMLESS (xác thực theo manifest `seamless-raw-v1.json`), quy trình phát hiện cấu trúc ([raw_path_probe.py](../../scripts/research/raw_path_probe.py)) và phân tích thực thể đã xác định các ứng viên trong chuỗi kịch bản:

1. **Tài sản đích ứng viên (Target Asset Candidate - Crown Jewel)**:
   - **Bản ghi và Locator quan sát được**: Bản ghi tại array index 3 trong file `20210920185958_users.json` với JSON pointer: `#/users/3`.
   - **Quy trình chọn tái lập (Reproducible Selector)**: Tìm kiếm tài khoản duy nhất trong đồ thị có Domain SID khớp mẫu regex `S-1-5-21-[0-9]+-[0-9]+-[0-9]+-502` (RID 502, tài khoản `krbtgt`).
   - **Đặc tính quan sát được**: Bản ghi có `admincount: true`, `enabled: false` (cấu hình mặc định của Windows Active Directory ngăn đăng nhập tương tác với tài khoản KDC) và `highvalue: false`.
   - **Alias quy ước**: `Target-User-KRBTGT`.
   - **Lý do quan trọng và gán nhãn kịch bản (Criticality Rationale)**:
     Tài khoản `krbtgt` quản lý khóa bí mật Kerberos Key Distribution Center (KDC) của toàn miền Active Directory; việc sở hữu credential hash của tài khoản này cho phép tạo vé Kerberos giả mạo (Golden Ticket attack).
     Do snapshot SharpHound đặt `highvalue: false` và thiếu các nhãn phân loại tài sản nghiệp vụ/kinh doanh, mức độ tài sản trọng yếu của đích đến được khai báo tường minh dưới dạng giả định kịch bản: `scenario_assumption: designated_crown_jewel`.
     Nhãn này được gắn trực tiếp cho tài sản đích `Target-User-KRBTGT`, cung cấp chủ thể rõ ràng cho việc tính điểm tác động đích (target impact) tại #141.

2. **Checkpoint đặc quyền trung gian (Intermediate Privilege Checkpoint Candidate - S2)**:
   - **Bản ghi và Locator quan sát được**: Bản ghi tại array index 40 trong file `20210920185958_groups.json` với JSON pointer: `#/groups/40`.
   - **Quy trình chọn tái lập (Reproducible Selector)**: Hàm `select_target()` trong [raw_path_probe.py](../../scripts/research/raw_path_probe.py) tìm kiếm nhóm duy nhất có Domain SID khớp mẫu regex `S-1-5-21-[0-9]+-[0-9]+-[0-9]+-512` (RID 512, nhóm Domain Admins).
   - **Đặc tính quan sát được**: Bản ghi có `admincount: true` và `highvalue: true`.
   - **Alias quy ước**: `Target-Group-DA`.
   - **Vai trò trong mô hình**:
     Đóng vai trò là checkpoint đặc quyền S2 trung gian trong chuỗi leo quyền; không mang nhãn crown jewel thay thế cho tài sản đích cuối cùng.

3. **Đề xuất máy chủ chưa xác minh**:
   - Máy chủ Domain Controller (`Target-DC-Computer`) được ghi nhận rõ ràng là **đề xuất kịch bản chưa xác minh bằng probe** (an unverified scenario candidate proposal), cần được chứng minh bằng locator cụ thể trong các bước tiếp theo nếu muốn đưa vào mô hình hóa.

## Kịch bản thành công đề xuất cho #141 (Concrete Proposed Success Scenario)

Để làm đầu vào cụ thể cho việc thiết kế mô hình và rubric ở [#141](https://github.com/nairyuuu/ad-weighted-graph/issues/141), kịch bản tấn công thành công được chốt với các thông số sau:

1. **Điểm xuất phát (Foothold)**:
   - Máy tính nguồn `Source A` (máy trạm được xác định qua `raw_path_probe.py` từ `20210920185958_computers.json`, có observed `enabled=true`).
   - Giả định chạy dưới ngữ cảnh `LocalSystem` / local admin, sở hữu network identity của computer account trên domain.
2. **Checkpoint đặc quyền trung gian (Privilege Checkpoint S2)**:
   - `Target-Group-DA` (nhóm Domain Admins, locator `20210920185958_groups.json#/groups/40` tại array index 40).
   - Snapshot xác minh chuỗi quan hệ cấu trúc tới nhóm DA.
   - S2 chỉ khả thi trong mô hình dưới các giả định foothold, reset, authentication và membership đã khai báo; chưa được xác minh thực thi.
3. **Tài sản đích (Target Asset) và Thao tác trên tài sản**:
   - **Tài sản đích (Target Asset)**: `Target-User-KRBTGT` (kho khóa danh tính cốt lõi của miền, locator `20210920185958_users.json#/users/3` tại array index 3, mang nhãn `scenario_assumption: designated_crown_jewel`).
   - **Thao tác trên tài sản đích (Operation on Target Asset)**: Yêu cầu replication trích xuất credential hash (NTLM hash) của tài khoản `krbtgt` qua giao thức [Microsoft MS-DRSR](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-drsr/) (kỹ thuật DCSync).
   - Thao tác DCSync là **quy tắc kỹ thuật đề xuất mở rộng nghiên cứu** (chưa có trong catalog [`configs/attack_semantics.yml`](../../configs/attack_semantics.yml)), thuộc tầng quy tắc kỹ thuật (Tier 2 - Technical Rules), tách biệt hoàn toàn với các giả định runtime môi trường (Tier 3 - Runtime Assumptions).
4. **Chuỗi hành động và trạng thái các cổng (Attack Chain & Gate Statuses)**:
   - *Bước 1 (Reset)*: `Source A` lạm dụng quyền `GenericAll` trên tài khoản `User-Candidate` (`20210920185958_users.json#/users/2310/Aces/3`) để thực hiện `genericall_reset_password`, tạo `authentication_control` (quan sát được cạnh ACL trong snapshot; khả năng reset phụ thuộc giả định foothold và policy).
   - *Bước 2 (Authentication)*: Kích hoạt `usable_identity` của `User-Candidate` trong context `directory-example` (Gate A thỏa mãn theo giả định kịch bản).
   - *Bước 3 (Membership closure)*: Kích hoạt `effective_member` trong `Target-Group-DA` qua liên kết thành viên `20210920185958_groups.json#/groups/40/Members/0` (Gate M thỏa mãn; đạt checkpoint đặc quyền S2 trong mô hình dưới các giả định đã khai báo).
   - *Bước 4 (DCSync - Bước mở rộng nghiên cứu)*: Kêu gọi replication tới dịch vụ thư mục domain (Gate O).
   - Trên snapshot SEAMLESS hiện tại, chưa có bằng chứng đã được kiểm chứng về phân quyền replication trên domain naming context; do đó Gate O giữ trạng thái `unknown` và S3 chưa được hỗ trợ vì thiếu bằng chứng phân quyền.
5. **Biến cố thành công (Path Success Event)**:
   - Kẻ tấn công trích xuất thành công credential hash của tài khoản `krbtgt` từ dịch vụ thư mục domain qua DCSync.
   - Kết luận của biến cố thành công được giới hạn chặt chẽ ở việc thu thập credential hash của tài khoản `krbtgt`; không tự suy diễn thành chiếm quyền kiểm soát toàn miền (Domain Compromise) vì việc kiểm soát toàn miền còn phụ thuộc vào các bước khai thác tiếp theo nằm ngoài đường đi được mô hình hóa.
6. **Giới hạn dữ liệu và phân tầng giả định (Limitations & Assumptions)**:
   - **Dữ kiện cấu trúc quan sát được có chứng cứ (Observed structural facts)**:
     Snapshot xác minh chuỗi quan hệ cấu trúc tới nhóm DA (gồm cạnh `GenericAll`, liên kết `MemberOf` và trạng thái `enabled=true`).
     S2 chỉ khả thi trong mô hình dưới các giả định foothold, reset, authentication và membership đã khai báo; chưa được xác minh thực thi.
   - **Quy tắc kỹ thuật có nguồn tài liệu (Technical rules)**:
     Theo chuẩn [Microsoft MS-DRSR](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-drsr/), thao tác DCSync yêu cầu các quyền phân quyền cấu trúc trên domain naming context (`DS-Replication-Get-Changes` và `DS-Replication-Get-Changes-All`).
     Trên snapshot SEAMLESS hiện tại, chưa có bằng chứng đã được kiểm chứng về các quyền này cho principal; theo nguyên tắc phân tầng, việc thiếu bằng chứng phân quyền không được ghi đè bằng assumption, do đó Gate O giữ trạng thái `unknown` / `indeterminate` và S3 chưa được hỗ trợ vì thiếu bằng chứng phân quyền.
   - **Giả định kịch bản runtime (Declared runtime assumptions)**:
     Khả năng kết nối mạng RPC tới RPC Endpoint Mapper (cổng TCP 135) cùng cổng RPC động được thương lượng (hoặc cổng RPC cố định được cấu hình) của dịch vụ Directory Replication Service (DRS) trên Domain Controller (Gate O network assumption).
     Tránh coi cổng TCP 445 là điều kiện tiên quyết bắt buộc của DCSync.

## Phân tầng 4 nhóm dữ kiện (Strict 4-Tier Fact Stratification)

Để ngăn chặn việc nhầm lẫn giữa dữ liệu thực tế và các giả thuyết, mọi thông tin trong scenario contract được phân định vào 4 tầng độc lập:

1. **Observed Structural Facts (Dữ kiện cấu trúc quan sát được)**:
   - Dữ liệu thực tế được trích xuất từ snapshot Active Directory với đầy đủ thông tin nguồn (file, JSON pointer, hash-verified).
   - Ví dụ: Cạnh `Computer -> GenericAll -> User`, `User -> MemberOf -> Group`, và cờ `enabled` của các thực thể nguồn và đích.
2. **Technical Rules (Quy tắc kỹ thuật Active Directory)**:
   - Cơ chế bảo mật và giao thức của Windows/AD được mô hình hóa trong [catalog ngữ nghĩa](../../configs/attack_semantics.yml) và tài liệu chính thức của Microsoft.
   - Ví dụ: Reset mật khẩu yêu cầu quyền `GenericAll` hoặc `ForceChangePassword`; thành viên nhóm gián tiếp được suy diễn qua transitive closure.
3. **Declared Runtime Assumptions (Giả định runtime được khai báo tường minh)**:
   - Các điều kiện môi trường cần thiết để kỹ thuật thực thi được nhưng không thể quan sát thấy trong snapshot AD tĩnh.
   - Ví dụ: Máy nguồn có kết nối mạng RPC tới Endpoint Mapper (cổng TCP 135) và cổng dịch vụ DRS trên Domain Controller; chính sách mật khẩu không chặn việc reset; tài khoản máy tính ban đầu hoạt động bình thường.
4. **Unresolved Uncertainty (Bất định chưa được giải quyết)**:
   - Các yếu tố môi trường chưa có dữ liệu và không được đưa vào giả định kịch bản.
   - Ví dụ: Sự hiện diện của EDR ngăn chặn truy cập bộ nhớ LSASS; chính sách giám sát của SOC; tài khoản honeypot.

**Nguyên tắc bất di bất dịch**: Dữ kiện sai (`false evidence`) tuyệt đối không bị giả định kịch bản âm thầm ghi đè.
Nếu một tài khoản được quan sát thấy `enabled = false` trong snapshot, giả định kịch bản không được phép biến nó thành `enabled = true`.
Nếu một cạnh không có trong snapshot, giả định kịch bản không được phép tự ý sinh ra cạnh cấu trúc đó.

## Biên đầu vào và assumption ledger

Chọn một directory authentication context duy nhất, ký hiệu `directory-example` trong test.
Initial state giả định đã sử dụng được computer identity ở context cần cho reset; chi phí giành foothold và thiết lập khả năng ban đầu nằm ngoài phép đo này.
LocalSystem trên domain member là một cách giải thích foothold có thể xét, không phải điều đã được snapshot xác nhận.
[Microsoft mô tả LocalSystem](https://learn.microsoft.com/en-us/windows/win32/ad/the-localsystem-account) có network access theo quyền của computer account trên domain member; điều đó không tự xác nhận channel hoặc quyền đặc quyền ở đích.

| Đầu vào | Nguồn cần ghi | Trong fixture | Với SEAMLESS hiện tại |
| --- | --- | --- | --- |
| Source và target identity, kind, ACL, membership | Snapshot và locator; qua chính sách/parser canonical trước production | Fact synthetic explicit | Raw probe có ứng viên, chưa thay canonical acceptance |
| Source/target enabled | Field và policy diễn giải | Fact synthetic explicit | Probe xuất observed enabled facts của cả source/target riêng; discovery không lọc theo enabled |
| Initial computer identity dùng được | Assumption scenario hoặc evidence runtime gắn context | Giả định true | Chưa được raw probe chứng minh |
| Password policy và directory write | Runtime predicates của catalog | Giả định true | Phải ghi assumption nếu chưa có evidence |
| Authentication của user mới được chấp nhận | User, credential mechanism, service/context và thời điểm | Gate A | Không suy từ reset thành công |
| Group là security group và membership dùng được | Group kind, scope/token context | `security_group` và gate M | Không suy từ tên group; thiếu groupType phải ghi rõ |
| Operation đích được phép thực hiện (DCSync) | Quyền replication trên naming context theo [Microsoft MS-DRSR](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-drsr/); channel RPC tới DRS endpoint | Gate O synthetic | DCSync là quy tắc kỹ thuật đề xuất mở rộng nghiên cứu (Tier 2, chưa có trong catalog); chưa có bằng chứng đã được kiểm chứng về quyền replication trên snapshot nên Gate O giữ trạng thái unknown (S3 chưa được hỗ trợ vì thiếu bằng chứng phân quyền); mạng RPC tới DRS endpoint là runtime assumption (Tier 3) |

Mỗi assumption cần lưu value, origin, scope và rationale trong đề xuất scenario; `true` từ giả định không được đổi nhãn thành `observed`.
Thiếu structural evidence thì không tự tạo cạnh.
Runtime chưa biết thì không traverse trong chế độ chỉ dùng evidence.
Một chế độ thí nghiệm có assumption chỉ được kết luận “khả thi trong mô hình dưới các giả định đã liệt kê”, không xác nhận tấn công thực tế.
Ledger này là cấu trúc review được đề xuất, chưa có serializer hoặc runtime assumption loader.

## Hai chế độ đánh giá: Evidence-only mode vs Scenario mode

Nhóm đề xuất hai chế độ đánh giá rạch ròi (đây là quy chuẩn kịch bản, chưa triển khai runtime assumption loader trong repo):
1. **Evidence-only mode (Chế độ thuần bằng chứng)**:
   - Chỉ sử dụng các dữ kiện cấu trúc quan sát được (`observed structural facts`) và quy tắc kỹ thuật (`technical rules`).
   - Mọi điều kiện runtime thiếu bằng chứng đều giữ nguyên trạng thái `unknown` hoặc `indeterminate`.
   - Thuật toán tìm kiếm không traverse qua các transition thiếu điều kiện; không gán penalty điểm số để ép đường đi tồn tại; không tự sinh cạnh cấu trúc.
2. **Scenario mode (Chế độ kịch bản)**:
   - Cho phép áp dụng các giả định runtime được khai báo tường minh (`declared runtime assumptions`) theo policy của kịch bản đã được phê duyệt.
   - Mọi kết quả tìm đường, tính chi phí và xếp hạng đều phải kèm theo nhãn cảnh báo: *"Khả thi trong mô hình dưới các giả định kịch bản đã khai báo"*.
   - Khả năng thành công được tính toán là xác suất có điều kiện theo kịch bản: $P(\text{Path Success} \mid \text{Foothold, Scenario})$; không đại diện cho xác suất bị tấn công ngoài đời thực.

## Cầu nối giữa reset và actor tiếp theo

[Catalog hiện hành](../../configs/attack_semantics.yml) cho `genericall_reset_password` effect `authentication_control`.
`actor_controlled` trong evaluator hiện đọc `state.control`; vì vậy không có phép tự chuyển toàn bộ authentication effect thành actor control.
Đây là ranh giới composition cần thiết kế, không phải bug được chứng minh ở contract hiện tại.

Trong fixture, dùng ba bước rõ ràng:

1. Reset theo điều kiện catalog, tạo fact `reset_authentication_control:user-example` có nguồn gốc từ reset.
2. Chỉ khi authentication được chấp nhận ở context đã chọn mới tạo `usable_identity:user-example:directory-example`.
3. Chỉ khi security-group và membership predicates thỏa mới tạo `effective_member:user-example:group-example:directory-example` bằng closure thụ động.

Bước 2 là bridge đề xuất trong fixture, chưa tồn tại như technique mới trong catalog.
Fact có tiền tố `reset_` chỉ để test không nhận nhầm credential material chưa xác định loại; không khẳng định generic `authentication_control` luôn tương đương password.
Các điều kiện của bước 1 vẫn gồm actor controlled/enabled, quyền phù hợp, target enabled, password policy và directory write.
Một identity dùng được ở `other-service` không được tự tái sử dụng tại `directory-example`.
Giữ actor ban đầu trong state tích lũy; không mô hình hóa việc “đổi actor” bằng cách xóa mọi khả năng đã có.

[Microsoft Access Tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-tokens) mô tả token mang identity, group và privilege của security context.
[SID Attributes](https://learn.microsoft.com/en-us/windows/win32/secauthz/sid-attributes-in-an-access-token) phân biệt SID enabled với deny-only trong access check.
Các nguồn hỗ trợ việc giữ context và membership usability riêng; chúng không xác nhận token hoặc runtime state của SEAMLESS.
Fixture chỉ dùng một predicate tổng hợp cho membership usability, không mô phỏng giao thức hoặc Windows access check đầy đủ.

## Phép thử tái lập và kết quả mong đợi

[Test research](../../tests/test_research_probes.py) thêm `handoff_fixture()` và `ScenarioHandoffTests`, tái sử dụng `action()`, `solve()` và `exhaustive_cost()` của probe cũ.
Không thêm search engine thứ hai hoặc import production implementation để ngầm coi đề xuất đã được accepted.

Ba gate A, M, O nhận lần lượt `true`, `false`, `unknown`, tạo `3^3 = 27` tổ hợp.
Mỗi tổ hợp kiểm tra bốn mục tiêu reset, usable identity, effective membership và operation.
Khi chuyển vào tập fact, chỉ `true` được thêm; `false` và `unknown` đều chặn nhưng vẫn là hai nhãn riêng trong input test.
Solver này không cung cấp diagnostic phân biệt chúng; implementation tương lai cần giữ lý do ngoài tập true facts.

| Mục tiêu | Điều kiện, với các prerequisite cố định còn lại true | Cost fixture |
| --- | --- | --- |
| Reset | Không phụ thuộc A, M, O | 2 |
| Usable identity | A true | 3 |
| S2: effective membership trong context | A và M true | 3 |
| S3: operation synthetic | A, M và O true | 4 |

Cost `reset=2`, `activate=1`, `closure=0`, `operation=1` là số tự chọn để kiểm tra cộng cost, không phải rating AD.
Đáp án được tính theo chuỗi phụ thuộc duy nhất trước khi đối chiếu uniform-cost search và exhaustive search.
Hai thuật toán dùng chung specification nên không xác minh độc lập semantics ngoài thực tế.
Các test còn kiểm tra mất prerequisite reset, thiếu bridge, thiếu membership/group kind, identity sai context và material không đủ qualifier.
Baseline đếm action dùng cùng gating, active action cost 1 và passive closure cost 0.

```bash
python -m unittest discover -s tests -p test_research_probes.py -v
```

Kết quả local tại checkpoint scenario ngày 28/9: 12 test đạt, gồm 15 fixture cũ và truth table 27 tổ hợp mới.
Đây là regression cho đề xuất nghiên cứu, không thay suite acceptance của parser/engine hoặc kiểm chứng thực thi trong AD.

## Insight bổ sung: đếm action phụ thuộc cách chia bước

Cùng một hành vi đạt S2 có thể được biểu diễn bằng `reset` rồi `activate_identity`, hoặc một action gộp `reset_and_activate`.
Test gộp yêu cầu cả hai tập prerequisite và đặt cost bằng tổng `2 + 1 = 3`, nên cost tới S2 vẫn là 3; khi authentication bị thiếu, cả hai biểu diễn đều không đạt S2.
Nhưng baseline đếm active action cho kết quả 2 ở biểu diễn tách và 1 ở biểu diễn gộp.
Vì thế phải cố định đơn vị hành động trước khi dùng “ít action hơn” để đánh giá chất lượng weighting.

Hai biểu diễn không tương đương ở mọi intermediate goal: nếu authentication bị chặn, mô hình tách vẫn có thể đạt reset, mô hình gộp không tạo effect đó.
Phép so sánh ở đây chỉ kiểm tra goal S2 và cost đã quy định, không chứng minh có thể tùy ý gộp transition production.
Bridge semantics rõ ràng cũng chưa buộc bridge phải nhận một khoản cost riêng: nếu rubric của reset đã bao gồm authentication setup, cộng thêm cùng khoản ở bridge sẽ double-count.
Đây là yêu cầu về cost boundary và additivity cho #42, chưa chọn relationship, transition hoặc transition-plus-context làm model chính thức.

## Đề xuất để review tiếp và liên kết các bước tiếp theo

Checkpoint hiện hành ngày 2026-09-30: Các artifacts nghiên cứu của #140, #141, #142 và #150 đã hoàn tất và được merge qua các PR #144, #147, #149 và #151.
Đề xuất Pareto bảo thủ có phạm vi hẹp đã được maintainer phê duyệt làm cơ sở phân tích nghiên cứu, tuy nhiên kết luận cho bài toán dự báo trên SEAMLESS vẫn là Insufficient Evidence.
Sau PR #151, issue #143 kế thừa cơ sở này để xem xét successor ADR (ADR-0013) và giao diện bàn giao cho TTS B.
Các bước lịch sử dưới đây không chuyển quyền sửa đổi mô hình sang #143 trước khi có quyết định chính thức.

1. **Nghiệm thu hợp đồng kịch bản (#140)**:
   - Thống nhất mục tiêu proxy S2 (usable identity) cho các thử nghiệm ban đầu và kịch bản DCSync S3 cụ thể cho các bước tiếp theo.
   - Thống nhất định nghĩa foothold của máy bị chiếm; xác định tài sản đích ứng viên `Target-User-KRBTGT` (locator `20210920185958_users.json#/users/3` tại array index 3, regex RID 502) mang nhãn `scenario_assumption: designated_crown_jewel`; xác định checkpoint đặc quyền trung gian `Target-Group-DA` (locator `20210920185958_groups.json#/groups/40` tại array index 40, regex RID 512); ghi nhận `Target-DC-Computer` là đề xuất kịch bản chưa xác minh bằng probe.
   - Áp dụng nguyên tắc phân tầng 4 nhóm dữ kiện: false evidence tuyệt đối không bị assumption ghi đè; đề xuất hai chế độ evidence-only và scenario mode.
2. **Chuyển tiếp sang thiết kế bản nháp mô hình và rubric (#141)**:
   - Dựa trên kịch bản đã chốt, xây dựng bản nháp mô hình trọng số rút gọn và rubric đánh giá khả năng thành công (success probability / difficulty) kết hợp với tác động đích.
   - Kiểm tra tính độc lập của các tiêu chí và chống đếm trùng (overlap review).
3. **Kiểm chứng worked example và hoàn thiện mô hình (#142)**:
   - Thử nghiệm ngay trên bản nháp mô hình của #141 bằng worked example trên snapshot SEAMLESS.
   - Kiểm tra độ nhạy và tính ổn định thứ hạng của các đường tấn công để phản hồi, hiệu chỉnh mô hình trước khi chính thức review và chấp thuận.
4. **Chốt successor ADR và handoff cho B (#143)**:
   - Sau khi mô hình và kết quả kiểm chứng được review và chấp thuận, ban hành successor ADR thay thế ADR-0001 và bàn giao interface specification cho TTS B để tích hợp thuật toán tìm đường tại M3.

[So sánh Phase A](week3-cost-ownership-comparison.md) dùng các ràng buộc này để đánh giá ba phương án cost ownership về correctness, additivity, auditability, reproducibility và search compatibility.
Không cần tự triển khai phần parser/engine của B để hoàn thành so sánh thiết kế đó.
