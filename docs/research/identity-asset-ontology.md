# [Research] Formalize Identity and Asset Ontology for Active Directory Attack Graph

## Tiêu đề & Metadata
- **Status:** Proposed (Research v0.1)
- **Liên kết nhiệm vụ:** Refs #62
- **Quyết định kiến trúc:** [ADR-0010](../adr/ADR-0010-identity-asset-semantic-facets.md)
- **Contract tham chiếu:** `configs/contract.yml` v1.0.0
- **Phạm vi:** Toàn bộ node kinds và 8 canonical M1 edge kinds.

## 1. Bối cảnh và Đặt vấn đề
Vấn đề nhập nhằng giữa Identity và Asset thường xuyên xảy ra trong các mô hình AD truyền thống.
Ví dụ, các công cụ như BloodHound thuần túy gom nhóm theo directory schema gốc của Microsoft bao gồm `User`, `Computer`, `Group`, `OU`, `Domain`, `GPO`.
Tuy nhiên, khi xây dựng weighted attack graph kết hợp với nguồn dữ liệu telemetry, chúng ta bắt buộc phải phân định rõ ràng các khái niệm này.
Lý do đầu tiên nằm ở chi phí và độ khó (exploit cost).
Chi phí và phương thức để chiếm dụng một identity hoàn toàn khác biệt so với việc chiếm quyền điều khiển một asset.
Lý do thứ hai liên quan đến bản chất của dữ liệu telemetry.
Log xác thực (như Event ID 4624, 4768) luôn gắn liền với Identity.
Trong khi đó, log về endpoint hoặc process (như Sysmon, Event ID 4688) lại gắn với Asset.
Cuối cùng, việc phân định rõ ràng giúp làm rõ ngữ nghĩa của đường đi trên đồ thị.
Chúng ta cần biết chính xác đâu là bước credential pivot, đâu là execution substrate, và đâu là quá trình privilege aggregation.

## 2. Bốn Vai trò Ngữ nghĩa Cốt lõi (Core Semantic Roles)
Hệ thống ontology này định nghĩa chính xác, có thể kiểm chứng cho bốn vai trò cốt lõi.
- `Identity`: Chủ thể xác thực trong hệ thống.
Thực thể này mang credential hoặc key.
Nó đóng vai trò thực hiện các quá trình xác thực Kerberos hoặc NTLM.
Sau khi xác thực thành công, nó nhận access token.
Nó là đối tượng thực sự sở hữu và thực thi các quyền hạn trong AD.
- `Asset`: Bất kỳ tài nguyên tính toán hoặc cấu trúc logic nào nắm giữ giá trị bảo mật, khả năng thực thi, hoặc quản trị chính sách.
Tài sản được chia thành hai khía cạnh (facets) chính.
Khía cạnh thứ nhất là Compute / Execution Asset như Endpoints, Servers, DCs, đóng vai trò là nơi các tiến trình thực thi (runtime substrate) và lưu trữ credential.
Khía cạnh thứ hai là Control-Plane / Structural Asset như Domain, OU, GPO.
- `PrivilegeContainer`: Vùng chứa đặc quyền logic.
Đại diện tiêu biểu nhất là Group.
Nó có nhiệm vụ tổng hợp quyền từ nhiều nguồn.
Đồng thời, nó đóng vai trò lan truyền ủy quyền một cách thụ động tới các thành viên.
- `ControlPlane`: Một khía cạnh chuyên biệt của `Asset` (specialized facet of Asset).
Mặt phẳng điều khiển logic của kiến trúc mạng, bao gồm Domain, OU, và GPO.
Nó có chức năng định hình phạm vi áp dụng của các chính sách (policy).
Nó cũng phân định ranh giới quản trị trong toàn bộ hạ tầng AD.

## 3. Giải quyết Đối tượng Vai trò Kép (Multi-Role Node Semantics)
Chúng ta quyết định dứt khoát áp dụng mô hình Semantic Facets dưới dạng flat multi-label facet model: `roles: list[str]`.
Đây là Lựa chọn 1 trong các phương án thiết kế kiến trúc.
Mô hình này giúp bảo toàn 100% cấu trúc đồ thị 1 node cho mỗi thực thể AD.
Nó giữ nguyên các canonical SID/GUID đã được định nghĩa trong `configs/contract.yml`.
Thay vì phân chia thành primary và secondary role, chúng ta gộp chung thành một mảng `roles` duy nhất cho các vai trò ngữ nghĩa cốt lõi (`Identity`, `Asset`, `PrivilegeContainer`, `ControlPlane`).
Mô hình flat facet này rõ ràng, tinh gọn, và loại bỏ hoàn toàn các phân cấp vai trò tùy ý (arbitrary role hierarchies).
Các khía cạnh về tầm quan trọng và giá trị an ninh (`Tier0`, `Privileged`, `HighValue`, `CrownJewel`) được tách biệt hoàn toàn sang chiều trực giao `security_labels: list[str]`, tuyệt đối không lưu lẫn vào `roles`.
Ví dụ đối với `Computer` thông thường, roles sẽ là `[Asset, Identity]`.
Nguyên nhân là do tài khoản máy tính (ví dụ `WS01$`) cũng tham gia vào quá trình xác thực domain.

Hiện tại hợp đồng không có node kind `DomainController` riêng biệt.
Do đó, Domain Controller được định nghĩa về mặt vận hành là một node `Computer` canonical.
Về vai trò ngữ nghĩa cốt lõi, Domain Controller thực thi vai trò quản trị chính sách và mặt phẳng điều khiển, do đó nhận thêm facet `ControlPlane`, đưa tập vai trò thành `[Asset, Identity, ControlPlane]`.
Về định nghĩa vận hành và tiêu chí nhận diện (operational predicates), ontology phân biệt rạch ròi giữa Writable Domain Controller (RWDC) và Read-Only Domain Controller (RODC):
- **Writable Domain Controller (RWDC)**:
  - Nhận diện dựa trên `PrimaryGroupSID` hoặc `primaryGroupID` kết thúc bằng RID 516 (nhóm well-known `Domain Controllers` theo MS-ADTS), và/hoặc thuộc tính `userAccountControl` chứa cờ `SERVER_TRUST_ACCOUNT` (`0x2000`).
  - Về chiều giá trị an ninh (`security_labels`), RWDC nhận nhãn `Tier0` vì sở hữu toàn quyền ghi lên directory partition, lưu giữ toàn bộ bí mật miền (bao gồm khóa `krbtgt`), và tham gia trực tiếp vào tiến trình nhân bản dịch vụ thư mục (DRS `GetChangesAll`).
- **Read-Only Domain Controller (RODC)**:
  - Nhận diện dựa trên `PrimaryGroupSID` hoặc `primaryGroupID` kết thúc bằng RID 521 (nhóm well-known `Read-only Domain Controllers` theo MS-ADTS 6.1.1.3.2), và/hoặc thuộc tính `userAccountControl` chứa cờ `PARTIAL_SECRETS_ACCOUNT` (`0x04000000`), kết hợp vị trí container dưới `OU=Domain Controllers`.
  - Về vai trò ngữ nghĩa cốt lõi, RODC cũng là một máy chủ điều khiển miền nên nhận `roles: [Asset, Identity, ControlPlane]`.
  - Về chiều giá trị an ninh (`security_labels`), theo mô hình phân tầng Active Directory của Microsoft (AD tier model), toàn bộ domain controller đều thuộc ranh giới mặt phẳng điều khiển Tier-0.
  - Tuy nhiên, so với RWDC, RODC có phạm vi tác động khi bị thỏa hiệp (blast radius) hẹp hơn nhờ cơ chế bộ nhớ đệm credential được kiểm soát bởi Chính sách Nhân bản Mật khẩu (Password Replication Policy - PRP) và tài khoản `krbtgt` cục bộ riêng biệt.
  - Trong điều kiện cấu hình quyền nhân bản và PRP mặc định chuẩn của AD, tài khoản máy chủ RODC không được cấp quyền nhân bản các bí mật nhạy cảm của miền và không thể bị lạm dụng để DCSync tài khoản quản trị miền hay trích xuất khóa `krbtgt` toàn miền (trừ phi tồn tại quyền nhân bản bị cấu hình sai lệch nghiêm trọng trên ACL).
  - Do đó, để phân định chính xác tính chất phơi lộ bí mật hạn chế mà vẫn bảo toàn đúng ranh giới Tier-0 theo chuẩn Microsoft, RODC được gán nhãn xác định:
    `roles: [Asset, Identity, ControlPlane]`
    `security_labels: [Tier0, PartialSecrets]`
  - Nhãn `PartialSecrets` thể hiện rõ phạm vi phơi lộ thông tin xác thực cục bộ bị giới hạn theo chính sách PRP, trong khi nhãn `Tier0` bảo toàn vị trí của RODC trong mặt phẳng điều khiển nhận dạng.
  - Tuyệt đối không đưa khái niệm vai trò ngữ nghĩa (như `ControlPlane`) vào `security_labels`, và ontology không sử dụng các phương án phân loại tùy chọn bất định nhằm bảo đảm tính nhất quán cho schema.
- **Cảnh báo về dị biệt công cụ thu thập (Collector Anomaly Warning)**:
  - Tuyệt đối không dựa đơn thuần vào thuộc tính boolean `Properties.isdc` do collector trả về để phân loại node.
  - Như đã kiểm chứng và ghi nhận tại tài liệu kiểm kê dữ liệu (`docs/research/data-inventory.md`, Dataset B trên các miền PHANTOM và WRAITH), collector SharpHound v2.3.3 gán cờ `isdc: false` cho các máy chủ RODC (`RODC01` và `EXTRODC01`).
  - Nếu phụ thuộc vào `isdc`, ontology sẽ phân loại sai lệch cùng một đối tượng control-plane tùy thuộc vào công cụ thu thập.
  - Do đó, việc phân loại vận hành bắt buộc phải căn cứ vào bằng chứng thư mục chuẩn (RID 516 vs RID 521, cờ UAC, và phân cấp container).

## 4. Bảng Ánh xạ Toàn diện Node Kinds sang Semantic Roles
Dưới đây là ma trận đầy đủ ánh xạ 6 node kinds sang các vai trò ngữ nghĩa (roles).

| Node Kind | Roles | Semantic Description | Runtime Substrate | Ví dụ thực tế |
| :--- | :--- | :--- | :--- | :--- |
| `User` | `[Identity]` | Chủ thể con người hoặc service account thực hiện hành động. | Không | `Administrator`, `svc_sql` |
| `Computer` | `[Asset, Identity]` | Máy tính vật lý/ảo hóa, đồng thời có tài khoản xác thực riêng. | Có | `WS01`, `SRV-DB01` |
| `Group` | `[PrivilegeContainer]` | Vùng chứa gom nhóm tài khoản để cấp quyền hàng loạt. | Không | `Domain Admins`, `IT Helpdesk` |
| `Domain` | `[Asset, ControlPlane]` | Ranh giới phân vùng quản trị và mặt phẳng điều khiển trong một forest. | Không | `corp.local` |
| `OU` | `[Asset, ControlPlane]` | Đơn vị tổ chức logic dùng để nhóm và áp dụng policy. | Không | `Workstations OU` |
| `GPO` | `[Asset, ControlPlane]` | Tập hợp các cấu hình policy áp dụng cho các đối tượng trong miền. | Không | `Default Domain Policy` |

Lưu ý đối với máy chủ Domain Controller:
Node canonical `Computer` khi được xác thực là Writable DC hoặc RODC theo vị từ vận hành ở Mục 3 sẽ nhận thêm facet `ControlPlane`, đưa tập vai trò ngữ nghĩa cốt lõi thành `[Asset, Identity, ControlPlane]`.
Chiều giá trị an ninh của DC được quản lý tách biệt hoàn toàn tại `security_labels`: Writable DC nhận `[Tier0]`, trong khi RODC nhận `[Tier0, PartialSecrets]` để thể hiện vị thế ranh giới điều khiển Tier-0 kèm cơ chế giới hạn phơi lộ credential theo chính sách PRP.

## 5. Bốn Khía cạnh Đặc quyền Trực giao (Orthogonal Dimensions of Security Value)
Các khía cạnh đặc quyền này là những chiều độc lập (orthogonal facets) của giá trị bảo mật, KHÔNG PHẢI là một thang bậc phân cấp tuyến tính duy nhất.
Bốn chiều này được mô hình hóa tường minh trong thuộc tính `security_labels: list[str]`, hoàn toàn tách biệt khỏi các vai trò ngữ nghĩa cốt lõi `roles: list[str]`.
- `Tier-0 Target / Control-Plane Asset`: Ranh giới điều khiển tối cao của toàn bộ hệ thống directory theo mô hình phân tầng Active Directory.
Nhóm này bao gồm Domain Controllers (cả Writable DC và RODC), Domain Admins, Builtin Administrators, Enterprise Admins, và Default Domain Policy.
Chiếm được bất kỳ thành phần nào trong nhóm này mang lại khả năng tác động trực tiếp lên mặt phẳng điều khiển nhận dạng.
Đối với RODC, dù thuộc ranh giới Tier-0, mức độ ảnh hưởng về phơi lộ thông tin xác thực (blast radius) được thu hẹp nhờ chính sách Password Replication Policy (PRP) và tài khoản krbtgt riêng biệt.
Theo cấu hình nhân bản và phân quyền mặc định chuẩn của Active Directory, RODC không được cấp quyền nhân bản các tài khoản nhạy cảm của miền và không thể thực hiện DCSync toàn miền trừ khi bị cấu hình sai lệch ACLs nhân bản nghiêm trọng.
Vị thế đặc thù này được biểu diễn chuẩn xác qua nhãn bổ sung `PartialSecrets` trong `security_labels: [Tier0, PartialSecrets]`.
Tiêu chí kiểm soát hiệu quả (effective control criteria) đối với Tier-0 hoàn toàn dựa trên năng lực kiểm soát thực tế, không bị trói buộc vào cờ `adminCount=true` (vốn chỉ là một hệ quả SDProp cục bộ của Active Directory).
- `Privileged Identity / Principal`: Định danh hoặc vùng chứa có quyền quản trị kỹ thuật.
Quyền quản trị này có hiệu lực trên ít nhất một hệ thống, dịch vụ hoặc vùng chứa cụ thể trong hạ tầng.
Nhóm này bao gồm Server Admins, Workstation Admins, Helpdesk, và tài khoản local admin trên các máy trạm.
- `High-Value Identity`: Định danh con người có tầm quan trọng kinh doanh tối cao đối với tổ chức.
Nhóm này thường là tài khoản của CEO, CFO, kế toán trưởng, hoặc người nắm giữ khóa ký mã phần mềm.
Chúng thường có cờ `adminCount=false` và không sở hữu quyền quản trị IT, nhưng gây rủi ro thất thoát dữ liệu và thiệt hại tài chính nghiêm trọng nếu bị thỏa hiệp.
- `High-Value Asset / Crown-Jewel Target`: Tài sản lưu trữ hoặc xử lý các quy trình kinh doanh sống còn của doanh nghiệp.
Đây có thể là hệ thống Core Banking, hệ thống ERP, máy chủ cơ sở dữ liệu nhạy cảm, hoặc hệ thống chứng chỉ số PKI/CA.
Khái niệm Crown-Jewel phản ánh giá trị bảo vệ từ góc độ nghiệp vụ (business value), hoàn toàn trực giao với quyền kiểm soát hạ tầng Active Directory (Tier-0).

### Ma trận Trực giao (Orthogonality Matrix)
| Chiều đặc quyền | Trọng tâm phân loại | Phạm vi ảnh hưởng khi thỏa hiệp | Ví dụ thực tế |
| :--- | :--- | :--- | :--- |
| `Tier-0 Target` | Kiểm soát hạ tầng AD | Toàn bộ miền và mặt phẳng điều khiển | `DC01$` (Writable DC - `[Tier0]`), `RODC01$` (RODC - `[Tier0, PartialSecrets]`), `Domain Admins`, `Default Domain Policy` |
| `Privileged Identity` | Quyền hạn kỹ thuật | Máy trạm, máy chủ hoặc dịch vụ cụ thể | `IT-Helpdesk`, `SRV-Admin`, tài khoản Local Administrator |
| `High-Value Identity` | Tầm quan trọng kinh doanh | Thất thoát dữ liệu nghiệp vụ, gian lận tài chính | `ceo@corp.local`, `cfo@corp.local`, Lead Developer ký mã |
| `High-Value Asset (Crown-Jewel)` | Dữ liệu & dịch vụ cốt lõi | Ngừng trệ hoạt động doanh nghiệp, lộ bí mật kinh doanh | Hệ thống Core Banking, Cơ sở dữ liệu ERP, Máy chủ PKI/CA |

## 6. Ma trận Hướng Ngữ nghĩa của 8 Cạnh Canonical M1 (Edge Directionality Matrix)
Bảng dưới đây thiết lập ma trận ngữ nghĩa tường minh cho toàn bộ 8 cạnh Milestone 1, tuân thủ nghiêm ngặt nguyên lý định hướng của ADR-0002.

| Edge Kind | Source Role(s) | Target Role(s) | Semantic Meaning | Semantic Direction Pattern |
| :--- | :--- | :--- | :--- | :--- |
| `MemberOf` | `[Identity, PrivilegeContainer]` | `[PrivilegeContainer]` | Tập hợp đặc quyền logic và kế thừa ủy quyền thụ động (membership aggregation & passive authorization inheritance). | `Principal -> PrivilegeContainer` |
| `AdminTo` | `[Identity, PrivilegeContainer]` | `[Asset]` | Thực thi quyền quản trị cấp máy chủ, kiểm soát runtime substrate và dữ liệu SAM/lưu trữ cục bộ. | `Principal -> Execution Asset` |
| `GenericAll` | `[Identity, PrivilegeContainer]` | `[Identity, Asset, PrivilegeContainer, ControlPlane]` | Toàn quyền kiểm soát tùy ý đối với vòng đời mục tiêu, quyền sở hữu và phân quyền DACL. | `Principal -> Target` |
| `WriteDacl` | `[Identity, PrivilegeContainer]` | `[Identity, Asset, PrivilegeContainer, ControlPlane]` | Quyền sửa đổi DACL của đối tượng đích, cho phép tự cấp thêm các quyền kiểm soát hiệu lực tùy ý. | `Principal -> Target` |
| `ForceChangePassword`| `[Identity, PrivilegeContainer]` | `[Identity]` | Trực tiếp đặt lại thông tin xác thực của tài khoản người dùng đích mà không cần biết mật khẩu hiện tại. | `Principal -> Identity` |
| `CanRDP` | `[Identity, PrivilegeContainer]` | `[Asset]` | Đăng nhập giao diện tương tác và tạo nền tảng thực thi mã cũng như phiên RAM trên máy trạm/máy chủ. | `Principal -> Execution Asset` |
| `CanPSRemote` | `[Identity, PrivilegeContainer]` | `[Asset]` | Nền tảng thực thi lệnh và tương tác từ xa qua giao thức quản trị PowerShell Remoting / WinRM. | `Principal -> Execution Asset` |
| `HasSession` | `[Asset]` | `[Identity]` | Lộ lọt thông tin xác thực và token truy cập trong bộ nhớ RAM/LSASS của Asset bị thỏa hiệp (bảo toàn hướng khai thác thực tế của ADR-0002). | `Asset -> Identity` |

Bốn nhóm mẫu hình tương tác chính được phân định rõ ràng theo luồng khai thác bảo mật:
- `Principal -> PrivilegeContainer` (`MemberOf`): Tổng hợp đặc quyền từ người dùng vào nhóm hoặc giữa các nhóm lồng nhau đa tầng.
- `Principal -> Execution Asset` (`AdminTo`, `CanRDP`, `CanPSRemote`): Chuyển hóa quyền hạn của Identity thành khả năng thực thi lệnh trên tài sản tính toán (runtime substrate).
- `Principal -> Target` (`GenericAll`, `WriteDacl`, `ForceChangePassword`): Thao túng quyền hạn tùy ý trên đối tượng đích, trong đó vai trò ngữ nghĩa của đích được kế thừa động theo loại nút (`Identity`, `Asset`, `PrivilegeContainer`, hoặc `ControlPlane`).
- `Asset -> Identity` (`HasSession`): Thu hoạch thông tin xác thực và access token từ bộ nhớ RAM/LSASS của tài sản bị chiếm quyền điều khiển.

## 7. Tác động tới EDA (#55/#59) và Attack Semantics (#58/#63)
Việc hình thức hóa ontology này tác động trực tiếp và tích cực tới giai đoạn Exploratory Data Analysis (EDA).
Nó hỗ trợ EDA báo cáo chi tiết theo từng semantic profile riêng biệt.
Chúng ta có thể dễ dàng so sánh Identity profile với Asset profile.
Đồng thời, nó cho phép xây dựng ma trận tương tác chi tiết giữa Identity và Asset.
Bên cạnh đó, ontology này cung cấp nền tảng tiên quyết cho việc định nghĩa Attack Semantics.
Nó giúp xác định rõ ràng chủ thể thực thi (actor) và đối tượng chịu tác động (target) trong mọi kỹ thuật tấn công.

## 8. Điều kiện Tiến hóa Schema `configs/contract.yml`
ADR-0010 quy định ontology không được materialize vào structural contract M2 hiện tại.
Nếu M3/M4 cần materialize ontology, đó phải là một contract decision/versioned change riêng, bao gồm migration, backward compatibility, validator, fixture, parser/engine impact và acceptance tests.
Khi đó, hai trường độc lập sau có thể được xem xét trong `node_optional`.
Trường thứ nhất là `roles: list[str]`, dùng riêng cho bốn vai trò ngữ nghĩa cốt lõi: `Identity`, `Asset`, `PrivilegeContainer`, và `ControlPlane`.
Trường này phản ánh bản chất tương tác kỹ thuật của thực thể trên đồ thị: thực thể xác thực danh tính, tài nguyên thực thi mã, vùng chứa ủy quyền, hay mặt phẳng điều khiển chính sách.
Trường thứ hai là `security_labels: list[str]`, dùng riêng cho các chiều giá trị bảo mật trực giao: `Tier0`, `Privileged`, `HighValue`, `CrownJewel`, và `PartialSecrets`.
Trường này phản ánh mức độ tác động và hậu quả an ninh khi thực thể bị thỏa hiệp đối với tổ chức.
Việc phân tách tường minh giữa `roles` và `security_labels` giúp loại bỏ hoàn toàn sự nhập nhằng ngữ nghĩa, tránh việc trộn lẫn vai trò vận hành với cấp độ giá trị an ninh.

Ví dụ minh họa cụ thể cho mô hình phân tách này:
- Máy chủ Writable DC (`DC01$`): `roles: [Asset, Identity, ControlPlane]`, `security_labels: [Tier0]`.
- Máy chủ RODC (`RODC01$`): `roles: [Asset, Identity, ControlPlane]`, `security_labels: [Tier0, PartialSecrets]`.
- Nhóm quản trị miền (`Domain Admins`): `roles: [PrivilegeContainer]`, `security_labels: [Tier0, Privileged]`.
- Tài khoản quản trị viên máy chủ (`SRV-Admin`): `roles: [Identity]`, `security_labels: [Privileged]`.
- Tài khoản người dùng trọng yếu nghiệp vụ (`ceo@corp.local`): `roles: [Identity]`, `security_labels: [HighValue]`.
- Máy chủ cơ sở dữ liệu cốt lõi (`SRV-DB01$`): `roles: [Asset, Identity]`, `security_labels: [CrownJewel]`.

## 9. Nguồn Tham khảo
- [Taxonomy](./taxonomy.md)
- [ADR-0002: Edge Directionality Semantics](../adr/ADR-0002-edge-directionality-semantics.md)
- [Contract Schema](../../configs/contract.yml)
