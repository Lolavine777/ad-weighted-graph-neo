# Hồ sơ căn cứ và đề xuất tham số kịch bản SEAMLESS (SEAMLESS Parameter-Basis Proposal Dossier)

Tài liệu này ghi nhận hồ sơ căn cứ kỹ thuật, các giả thiết kịch bản nghiên cứu, và bộ tham số đề xuất cho việc xếp hạng các ứng viên tấn công trong kịch bản SEAMLESS (Source A và Source B) theo đặc tả Interface 1.0.0 và ADR-0013.

> [!IMPORTANT]
> Toàn bộ các định mức nỗ lực ($C$) và khoảng xác suất có điều kiện ($q_i$) trong hồ sơ này là **giả thiết kịch bản có hỗ trợ nghiên cứu** (research-assisted scenario hypotheses) do TTS A xây dựng phục vụ việc kiểm thử tích hợp và kiểm chứng giao diện.
> Hồ sơ này **không tự nhận** là kết quả đánh giá thực tế của con người (human agreement), không tự động suy diễn năng lực chuyên gia, và không phải là hiệu chuẩn thực nghiệm sản phẩm (empirical calibration).
> Bảng tính độc lập của con người (`seamless_rater_1.json`, `seamless_rater_2.json`) được bảo lưu nguyên vẹn ở trạng thái `pending_independent_ratings` với toàn bộ giá trị rỗng/null.

## 1. Mục tiêu và phạm vi hồ sơ căn cứ

1. **Chuẩn hóa căn cứ định tính và kỹ thuật:**
   Cung cấp nguồn gốc kỹ thuật từ tài liệu kiến trúc Windows/Active Directory và Open Specifications của Microsoft cho từng vị từ và bước chuyển dịch trong kịch bản.

2. **Xác lập hồ sơ tham số đề xuất cho Source A (Ưu tiên):**
   Xây dựng bộ tham số hoàn chỉnh cho 2 ứng viên của Source A (`cand_seamless_01_direct_lidia` và `cand_seamless_02_alt_vajer_ollie`), bao gồm:
   - Đánh giá mức độ tác động nghiệp vụ ($I$).
   - Định mức nỗ lực chuẩn hóa rubric ($T_1, T_2, C$) cho 9 đơn vị công việc chuẩn tắc.
   - Định mức khoảng xác suất có điều kiện ($q_i \in [l_i, u_i]$) cho 11 câu hỏi tiền tố.

3. **Bảo toàn tính tách biệt giữa vết cấu trúc và sổ cái công việc:**
   Đảm bảo các vết đường cấu trúc (`structural_routes`) giữ nguyên danh sách cạnh/nút/locator chuẩn tắc theo Graph Contract 1.3, độc lập với việc tính toán nỗ lực trên sổ cái công việc chuẩn tắc (`work_units_ledger`).

4. **Cung cấp bằng chứng kiểm chứng và phân tích độ nhạy:**
   Xác lập vết tính toán số học phân số chính xác tuyệt đối (stdlib `Fraction`), phân tích biên Pareto, truy vấn Min-Effort-to-DA, và kiểm thử độ nhạy lân cận quanh bộ tham số đề xuất.

## 2. Phạm vi truy vấn và cấu trúc ứng viên

### 2.1. Cấu trúc ứng viên trong Source A

- **Mục tiêu truy vấn:** Chiếm quyền kiểm soát mức Domain Admin trên Domain Controller `BADBLOOD` (`S-1-5-21-1271839998-3495686680-2211690266-1000`).
- **Điểm tựa ban đầu (Foothold):** Máy trạm `TSTWVIR$` (`S-1-5-21-1271839998-3495686680-2211690266-4131`) với quyền `LocalSystem`.
- **Ứng viên 1 (`cand_seamless_01_direct_lidia`):**
  - Vết đường cấu trúc: 3 cạnh cấu trúc (`TSTWVIR$` -> GenericAll -> `Lidia` -> MemberOf -> `Domain Admins` -> GenericAll -> `BADBLOOD`).
  - Chuỗi hành động: 4 hành động (Reset Lidia -> Activate Lidia -> Derive DA -> WinRM DC).
  - Đơn vị công việc chủ động: 3 đơn vị công việc chuẩn tắc (`WU_RESET_LIDIA`, `WU_ACTIVATE_LIDIA`, `WU_WINRM_DC_LIDIA`).
- **Ứng viên 2 (`cand_seamless_02_alt_vajer_ollie`):**
  - Vết đường cấu trúc: 5 cạnh cấu trúc (`TSTWVIR$` -> GenericAll -> `Josefa` -> MemberOf -> `VA-JER-ADMINGROUP1` -> GenericAll -> `Ollie` -> MemberOf -> `Domain Admins` -> GenericAll -> `BADBLOOD`).
  - Chuỗi hành động: 7 hành động (Reset Josefa -> Activate Josefa -> Derive VA-JER -> Reset Ollie -> Activate Ollie -> Derive DA -> WinRM DC).
  - Đơn vị công việc chủ động: 5 đơn vị công việc chuẩn tắc (`WU_RESET_JOSEFA`, `WU_ACTIVATE_JOSEFA`, `WU_RESET_OLLIE`, `WU_ACTIVATE_OLLIE`, `WU_WINRM_DC_OLLIE`).

### 2.2. Cấu trúc ứng viên trong Source B

- **Điểm tựa ban đầu (Foothold):** Máy trạm `FINWVIR$` (`S-1-5-21-1271839998-3495686680-2211690266-4157`) với quyền `LocalSystem`.
- **Ứng viên B (`cand_seamless_source_b_01_ollie`):**
  - Vết đường cấu trúc: 3 cạnh cấu trúc (`FINWVIR$` -> GenericAll -> `Ollie` -> MemberOf -> `Domain Admins` -> GenericAll -> `BADBLOOD`).
  - Chuỗi hành động: 4 hành động (Reset Ollie -> Activate Ollie -> Derive DA -> WinRM DC).
  - Đơn vị công việc chủ động: 3 đơn vị công việc chuẩn tắc (`WU_RESET_OLLIE_FROM_B`, `WU_ACTIVATE_OLLIE`, `WU_WINRM_DC_OLLIE`).

## 3. Hồ sơ đánh giá mức độ tác động nghiệp vụ (Target Impact Assessment)

### 3.1. Nhận diện tài sản đích và sự kiện thành công

- Tài sản đích: `S-1-5-21-1271839998-3495686680-2211690266-1000` (Domain Controller `BADBLOOD`).
- Sự kiện thành công: `terminal_compromise_seamless_dc`.
- Định nghĩa sự kiện: Đạt được phiên thực thi lệnh tương tác trong ngữ cảnh người dùng quản trị tối cao (Domain Administrator) trên Domain Controller đích.
- Quy tắc gắn kết tác động:
  Theo đặc tả Interface 1.0.0 Mục 2.3, mức độ tác động được gắn kết chặt chẽ vào cặp đối tượng `(target_asset_id, success_event)`.
  Tác động phản ánh tổn thất nghiệp vụ khi tài sản đích bị chiếm quyền điều khiển, không thay đổi theo lộ trình tấn công trung gian khi chưa có mô hình thiết kế tổn thất lan tỏa riêng biệt.

### 3.2. Căn cứ và lý giải mức độ tác động

Theo thang đo định tính 4 bậc của quy chế quản trị: $\text{Low} < \text{Medium} < \text{High} < \text{Critical}$.
- Căn cứ kỹ thuật:
  - Máy chủ BADBLOOD giữ vai trò Domain Controller duy nhất được quan sát trong snapshot SEAMLESS.
  - Việc chiếm quyền thực thi quản trị trên DC cho phép kẻ tấn công trích xuất toàn bộ cơ sở dữ liệu xác thực (NTDS.dit), thao túng chính sách bảo mật miền qua Group Policy Objects, và làm tổn hại tính toàn vẹn của mọi danh tính trong ranh giới bảo mật của Active Directory Forest.
- Phân tích ranh giới giữa `High` và `Critical`:
  - Trong dữ liệu snapshot SEAMLESS, không có bằng chứng chứng minh tổ chức vận hành hệ thống tài chính trọng yếu, dịch vụ y tế cứu sinh, hay cơ sở hạ tầng an ninh quốc gia.
  - Việc tự động áp đặt nhãn `Critical` cho mọi Domain Controller là vi phạm nguyên tắc phân định giữa ranh giới kiểm soát kỹ thuật Active Directory (`Tier 0`) và giá trị kinh doanh thực tế (`CrownJewel`) theo Identity-Asset Ontology §5.
  - Mức đánh giá `High` phản ánh chính xác sự gián đoạn nghiêm trọng đối với dịch vụ định danh và kiểm soát quyền truy cập toàn doanh nghiệp, mà không phóng đại mức độ thiệt hại kinh tế hoặc an toàn tính mạng con người.
- Đề xuất định mức:
  - `consequence_rating`: `"High"`.
  - `rating_status`: `"rated"` (dưới dạng giả thiết kịch bản nghiên cứu được tuyên bố).
  - `business_rationale`: "Chiếm quyền điều khiển Domain Controller dẫn đến mất hoàn toàn tính toàn vẹn và bảo mật của dịch vụ định danh Active Directory trên toàn miền; tuy nhiên, do snapshot không chứa bằng chứng về các dịch vụ kinh doanh trọng yếu cấp quốc gia hoặc an toàn tính mạng, mức đánh giá High là phù hợp và bảo thủ."
  - Mức `Critical` được xem xét trong phần phân tích độ nhạy (Sensitivity Analysis).

## 4. Hồ sơ định mức nỗ lực cho 9 đơn vị công việc chuẩn tắc

### 4.1. Quy ước rubric định mức nỗ lực và neo chuẩn tắc (Rubric Anchors)

Nỗ lực được định mức theo rubric hai chiều chuẩn hóa tại Interface 1.0.0 Mục 2.4:
- Công cụ kỹ thuật ($T_1 \in \{1, 2, 3\}$):
  - $T_1 = 1$: Sử dụng công cụ tiêu chuẩn, có sẵn (Standard built-in Windows commands, native PowerShell, standard RPC/LDAP client APIs).
  - $T_1 = 2$: Sử dụng công cụ tấn công chuyên dụng phổ biến, đòi hỏi kỹ năng trung cấp (BloodHound ingestors, Mimikatz, Rubeus, Impacket scripts).
  - $T_1 = 3$: Đòi hỏi viết mã khai thác tùy biến hoặc kỹ thuật vượt rào chuyên sâu (Custom exploit, unconstrained delegation manipulation, complex certificate relay chains).
- Độ ma sát tương tác và thời gian thực hiện ($T_2 \in \{1, 2, 3\}$):
  - $T_2 = 1$: Ma sát thấp (truy vấn mạng trực tiếp RPC/LDAP, quan sát thụ động, yêu cầu một lệnh tức thì, không yêu cầu session đăng nhập tương tác).
  - $T_2 = 2$: Ma sát trung bình (yêu cầu session đăng nhập xác thực, khởi động lại dịch vụ cục bộ, hoặc quy trình tương tác nhiều bước trên host).
  - $T_2 = 3$: Ma sát cao (yêu cầu tương tác người dùng, vượt qua ranh giới mạng phức tạp, hoặc cửa sổ thời gian chặt chẽ).
- Công thức tính nỗ lực cơ sở:
  $$C = T_1 + T_2 - 2 \quad (0 \le C \le 4).$$
- Lưu ý về ranh giới rubric:
  Quy ước ma sát $T_2$ đo lường thời gian và thao tác tương tác cần thiết của kẻ tấn công, tuyệt đối không đồng nhất mức độ ghi nhận nhật ký (detectability / Event 4724) thành chi phí nỗ lực khi chưa có hành động phòng vệ chủ động cản trở.

### 4.2. Bảng định mức chi tiết cho 9 đơn vị công việc chuẩn tắc

| STT | Đơn vị công việc chuẩn tắc (Canonical Work Unit ID) | T1 (Công cụ) | T2 (Ma sát) | Nỗ lực C | Nội dung công việc và giải trình ma sát tương tác |
| --- | --- | --- | --- | --- | --- |
| 1 | `reset_password:...-4131:...-3398:...` (WU_RESET_LIDIA) | 1 | 2 | 1 | Sử dụng API RPC/LDAP tiêu chuẩn từ máy foothold để gửi yêu cầu đặt lại mật khẩu cho Lidia; ma sát trung bình ($T_2=2$) do quy trình tương tác nhiều bước gồm thương lượng kết nối RPC bind, tạo chuỗi mật khẩu phức tạp tuân thủ chính sách, và kiểm tra mã phản hồi xác nhận từ NTDS. |
| 2 | `acquire_ticket:...-3398:...-1000:...` (WU_ACTIVATE_LIDIA) | 1 | 1 | 0 | Thực hiện gửi yêu cầu Kerberos AS-REQ tiêu chuẩn tới KDC với mật khẩu mới; yêu cầu mạng đơn lẻ, diễn ra tức thì, ma sát thấp ($T_2=1$). |
| 3 | `remote_exec_winrm:...-3398:...-1000:...` (WU_WINRM_DC_LIDIA) | 1 | 2 | 1 | Khởi tạo phiên PowerShell Remoting qua WinRM tới DC bằng tài khoản Lidia; ma sát trung bình ($T_2=2$) do yêu cầu bắt tay phiên PSRP, khởi tạo runspace từ xa, phân bổ tiến trình worker, và giám sát luồng lệnh tương tác. |
| 4 | `reset_password:...-4131:...-1766:...` (WU_RESET_JOSEFA) | 1 | 2 | 1 | Đặt lại mật khẩu Josefa từ foothold TSTWVIR qua GenericAll; công cụ chuẩn ($T_1=1$), ma sát tương tác nhiều bước của giao thức SAMR ($T_2=2$). |
| 5 | `acquire_ticket:...-1766:...-1000:...` (WU_ACTIVATE_JOSEFA) | 1 | 1 | 0 | Gửi Kerberos AS-REQ nhận TGT cho Josefa; thao tác mạng đơn lẻ tức thì ($T_1=1, T_2=1$). |
| 6 | `reset_password:...-1766:...-2014:...` (WU_RESET_OLLIE) | 1 | 2 | 1 | Đặt lại mật khẩu Ollie trong ngữ cảnh phiên xác thực của Josefa thông qua quyền GenericAll của nhóm VA-JER-ADMINGROUP1; công cụ chuẩn ($T_1=1$), tương tác RPC đa bước trên phiên người dùng trung gian ($T_2=2$). |
| 7 | `acquire_ticket:...-2014:...-1000:...` (WU_ACTIVATE_OLLIE) | 1 | 1 | 0 | Gửi Kerberos AS-REQ nhận TGT cho Ollie; thao tác tức thì ($T_1=1, T_2=1$). |
| 8 | `remote_exec_winrm:...-2014:...-1000:...` (WU_WINRM_DC_OLLIE) | 1 | 2 | 1 | Khởi tạo phiên WinRM PSRP tương tác tới DC bằng tài khoản Ollie; công cụ chuẩn ($T_1=1$), ma sát thiết lập phiên làm việc từ xa ($T_2=2$). |
| 9 | `reset_password:...-4157:...-2014:...` (WU_RESET_OLLIE_FROM_B) | 1 | 2 | 1 | Đặt lại mật khẩu Ollie trực tiếp từ máy tính foothold B qua GenericAll; công cụ chuẩn ($T_1=1$), ma sát giao thức SAMR ($T_2=2$). |

### 4.3. Xử lý trùng lặp và tính nỗ lực cộng dồn (Overlap Resolution & Work Dedup)

- **Phân bổ chuẩn bị và tiền đề chung (Preparation Sharing Disposition):**
  - Khởi tạo foothold ban đầu và môi trường thực thi (LocalSystem shell, mạng nội bộ, công cụ sẵn có) được phân bổ vào các điều kiện kịch bản ($S$), không bị tính lặp lại vào từng đơn vị công việc.
  - Mỗi đơn vị công việc đại diện cho một giao dịch tương tác độc lập trên giao thức mạng (giao dịch RPC SAMR riêng biệt, yêu cầu Kerberos TGT riêng biệt, hoặc phiên WinRM riêng biệt).
  - Hai thao tác đặt lại mật khẩu trong Candidate 2 (Josefa, sau đó Ollie) nhắm vào hai tài khoản khác nhau với hai bối cảnh xác thực khác nhau (tài khoản máy tính foothold, sau đó tài khoản người dùng trung gian), do đó không thể gộp hay chia sẻ chi phí tương tác.
- **Trạng thái trùng lặp (`overlap_state`):**
  - Mọi đơn vị công việc chủ động trong phạm vi từng ứng viên đều là công việc độc lập, phân biệt (`independent`, với bí danh wire adapter là `distinct_work`).
  - Toàn bộ 9 đơn vị công việc đều có trạng thái `rating_status: "rated"` kèm điểm rubric hợp lệ.
- **Tổng nỗ lực danh định của các ứng viên:**
  - Candidate 1 (`cand_seamless_01_direct_lidia`):
    $$C_1 = C(\text{WU\_RESET\_LIDIA}) + C(\text{WU\_ACTIVATE\_LIDIA}) + C(\text{WU\_WINRM\_DC\_LIDIA}) = 1 + 0 + 1 = 2.$$
  - Candidate 2 (`cand_seamless_02_alt_vajer_ollie`):
    $$C_2 = C(\text{RESET\_JOSEFA}) + C(\text{ACTIVATE\_JOSEFA}) + C(\text{RESET\_OLLIE}) + C(\text{ACTIVATE\_OLLIE}) + C(\text{WINRM\_OLLIE}) = 1 + 0 + 1 + 0 + 1 = 3.$$
  - Candidate B (`cand_seamless_source_b_01_ollie`):
    $$C_B = C(\text{RESET\_OLLIE\_B}) + C(\text{ACTIVATE\_OLLIE}) + C(\text{WINRM\_OLLIE}) = 1 + 0 + 1 = 2.$$

## 5. Hồ sơ định mức khoảng xác suất có điều kiện (11 Câu hỏi)

### 5.1. Bảng ánh xạ nguồn kỹ thuật chuẩn tắc (Consolidated Primary Source Mapping Table)

Nhằm bảo đảm tính kiểm toán và truy vết nguồn gốc, bảng dưới đây chuẩn hóa toàn bộ các tài liệu kỹ thuật chuẩn tắc của Microsoft Open Specifications và IETF RFC được dẫn chiếu trong hồ sơ.
Bảng phân định tường minh giữa cơ chế kỹ thuật được tài liệu bảo đảm với các giả thiết vận hành của kịch bản nghiên cứu:

| ID nguồn | Tiêu chuẩn / Giao thức | Mục (Section) | Tên mục chính thức (Official Section Title) | URL tham chiếu | Cơ chế kỹ thuật được tài liệu hỗ trợ | Ranh giới giả định kịch bản (Scenario Judgment) |
| --- | --- | --- | --- | --- | --- | --- |
| `SRC-SAMR` | [MS-SAMR] | 3.1.5.6.4 | *SamrSetInformationUser2 (Opnum 58)* | [MS-SAMR 3.1.5.6.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/99ee9f39-43e8-4bba-ac3a-82e0c0e0699e) | Đặt lại mật khẩu tài khoản qua giao thức SAMR RPC; định dạng thông điệp, kiểm tra quyền hạn và cập nhật thuộc tính người dùng trên DC. | Rủi ro tranh chấp khóa ghi NTDS, độ trễ xử lý RPC, thời gian I/O stall và phân bổ xác suất hoàn thành trong kịch bản. |
| `SRC-RFC4120` | RFC 4120 | 3.1, 7.2.1, 7.2.2, 8.1 | *The Authentication Service Exchange*, *UDP/IP transport*, *TCP/IP Transport*, *Specification 2* | [RFC 4120](https://datatracker.ietf.org/doc/html/rfc4120) | Quy chuẩn AS Exchange nhận vé TGT (§3.1); bắt buộc client và KDC hỗ trợ cả hai giao thức truyền vận TCP và UDP trên cổng 88 (§8.1); quy định chuyển sang TCP khi phản hồi UDP vượt kích thước hoặc KDC trả mã KRB_ERR_RESPONSE_TOO_BIG (§7.2.1); cho phép client lựa chọn gửi thử UDP trước hoặc kết nối TCP trực tiếp (§7.2.2). | Lựa chọn chiến lược client thử UDP trước với timeout 5 giây và tự động chuyển sang TCP khi gặp timeout hoặc nhận phản hồi kích thước trong kịch bản; tải xử lý hàng đợi KDC, độ trễ pre-auth và phân bổ xác suất hoàn thành trong kịch bản khi kết nối mạng đã được bảo đảm bởi $S$. |
| `SRC-KILE` | [MS-KILE] | 3.3.5, 3.3.5.1 | *Message Processing Events and Sequencing Rules*, *Request Flag Ticket-issuing Behavior* | [MS-KILE 3.3.5.1](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/f5993d64-a280-4555-9fcc-922fb934fc27) | Quy tắc xử lý thông điệp Kerberos trên KDC và các cờ vé xác thực mở rộng của Windows (FAST, cờ cấp vé). | Tải KDC khi giải mã pre-auth/dựng PAC và các rủi ro nghẽn hàng đợi tạm thời trong kịch bản. |
| `SRC-WSMV` | [MS-WSMV] | 3.1.4 | *Message Processing Events and Sequencing Rules* | [MS-WSMV 3.1.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wsmv/568385a0-0676-493f-bcd7-380b6e7cb7ee) | Định dạng và xử lý thông điệp SOAP/XML cho WS-Management protocol; quản lý phiên và bắt tay kết nối. | Giới hạn hạn ngạch phiên (`MaxShellsPerUser`), tải CPU/tiến trình máy chủ và phân bổ xác suất khởi tạo thành công trong kịch bản khi kết nối mạng đã được bảo đảm bởi $S$. |
| `SRC-PSRP` | [MS-PSRP] | 3.1.5.3 | *Rules for Processing WS-MAN Messages* | [MS-PSRP 3.1.5.3](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-psrp/01b38726-b7d8-4c72-a924-a7168ce2f1d0) | Khởi tạo runspace và trao đổi dữ liệu từ xa của PowerShell Remoting Protocol trên nền WS-Management. | Tranh chấp bộ nhớ heap của tiến trình con `wsmprovhost.exe` trên DC và rủi ro trễ khởi tạo trong kịch bản. |
| `SRC-PAC` | [MS-PAC] | 2.5 | *KERB_VALIDATION_INFO* | [MS-PAC 2.5](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-pac/69e86ccc-85e3-41b9-b514-7d969cd0ed73) | Cấu trúc dữ liệu xác thực PAC chứa danh sách Group SIDs của người dùng được KDC ký và nhúng vào vé xác thực. | Khả năng tương thích token tại tài nguyên đích và việc không suy diễn cấu trúc groupType trong kịch bản. |

### 5.2. Chính sách thực thi và thử lại có giới hạn (Action Execution & Bounded Retry Policy)

Để các giá trị xác suất có ý nghĩa vật lý nhất quán, toàn bộ 11 câu hỏi tiền tố được đánh giá dưới cùng một chính sách kịch bản xác định:
- **Phạm vi kịch bản (Scenario Scope):**
  Khung thời gian chiến dịch chung là 24 giờ (`horizon: "24h"`).
  Ngân sách công việc tích cực là 6 đơn vị công việc chuẩn tắc (`active_work_budget: 6`).
  Theo đặc tả Interface 1.0.0 Mục 2.4, `active_work_budget` giới hạn số lượng các đơn vị công việc phân biệt (distinct active work units), không giới hạn số lượt thử lại của cùng một đơn vị công việc.
- **Chính sách thử lại có giới hạn theo từng nhóm hành động (Per-Action Bounded Retry Policy):**
  1. *Nhóm đặt lại mật khẩu SAMR RPC (`reset_password`, gồm $q_1, q_4, q_6, q_9$):*
     - Giới hạn thử lại: Tối đa $N=3$ lần thử (1 lần thực thi ban đầu + tối đa 2 lần retry).
     - Thời hạn tối đa cho hành động (action deadline): $\le 15$ phút trong horizon 24h, áp dụng exponential backoff giữa các lần thử.
     - Điều kiện dừng: Nhận mã thành công `STATUS_SUCCESS` (hoàn tất hành động) hoặc gặp lỗi vĩnh viễn không thể retry (như tài khoản bị vô hiệu hóa, quyền bị từ chối).
     - Phạm vi fallback: Thử kết nối lại endpoint RPC SAMR trên Domain Controller đích.
     - Ràng buộc nỗ lực: Chi phí thực hiện các lần retry trong giới hạn 15 phút đã được tính trọn gói trong mức ma sát tương tác $T_2=2$ của rubric nỗ lực.
  2. *Nhóm yêu cầu vé Kerberos TGT (`acquire_ticket`, gồm $q_2, q_5, q_7, q_{10}$):*
     - Giới hạn thử lại: Tối đa $N=3$ lần thử yêu cầu AS-REQ.
     - Lựa chọn truyền vận và phạm vi fallback: Kịch bản giả định client chọn gửi thử qua UDP socket trước (timeout 5 giây cho mỗi lần gửi AS-REQ) theo quyền chọn tại RFC 4120 Section 7.2.2; nếu mất gói UDP, socket timeout hoặc nhận lỗi `KRB_ERR_RESPONSE_TOO_BIG` theo RFC 4120 Section 7.2.1, client tự động chuyển sang kết nối TCP (port 88) được hỗ trợ bắt buộc theo RFC 4120 Section 7.2.2 và Section 8.1.
     - Thời hạn tối đa cho hành động: $\le 10$ phút trong horizon 24h.
     - Điều kiện dừng: Nhận vé TGT hợp lệ (hoàn tất hành động) hoặc nhận thông báo lỗi Kerberos nghiêm trọng từ KDC.
     - Ràng buộc nỗ lực: Thao tác gửi yêu cầu và nhận vé Kerberos có ma sát thấp $T_2=1$ do thư viện client tự động xử lý quy trình kết nối UDP và fallback TCP.
  3. *Nhóm thực thi lệnh quản trị từ xa WinRM (`remote_exec_winrm`, gồm $q_3, q_8, q_{11}$):*
     - Giới hạn thử lại: Tối đa $N=3$ lần thử thiết lập phiên WS-Man / PSRP runspace.
     - Thời hạn tối đa cho hành động: $\le 30$ phút trong horizon 24h, giãn cách giữa các lần thử khi DC báo bận hoặc hết hạn ngạch shell tạm thời.
     - Điều kiện dừng: Khởi tạo thành công phiên runspace elevated trên DC đích (hoàn tất hành động) hoặc gặp lỗi cấu hình endpoint nghiêm trọng.
     - Ràng buộc nỗ lực: Ma sát trung bình $T_2=2$ đã bao hàm thời gian bắt tay phiên, khởi tạo worker process và thử lại khi gặp stall tạm thời.

### 5.3. Định nghĩa đại lượng toán học và nguyên tắc điều kiện hóa

Mỗi câu hỏi đánh giá xác suất có điều kiện thành công của hành động $E_i$ sau khi đã áp dụng đầy đủ chính sách thử lại có giới hạn trong thời hạn của hành động:

$$q_i = P(E_i \text{ hoàn thành sau bounded retry policy} \mid F, S, E_1, \ldots, E_{i-1} \text{ succeeded}).$$

- **Khoảng chặn xác suất:** $[l_i, u_i] \subset (0, 1)$, sử dụng phân số chính xác tuyệt đối (stdlib `Fraction`).
- **Nguyên tắc giải trình độ bất định dư thừa sau chính sách (Residual Uncertainty Principle):**
  Các giả thiết đã được ấn định là đúng trong $S$ (kết nối mạng tới RPC/KDC/WinRM khả dụng xuyên suốt horizon 24h, dịch vụ đang chạy, chính sách mật khẩu chấp thuận, bối cảnh thời gian hợp lệ, xác thực Kerberos được chấp nhận, và token có quyền quản trị) không được dùng lại làm nguyên nhân gây thất bại cho $q_i$.
  Vì $S$ đảm bảo tính khả dụng của kênh truyền mạng xuyên suốt khung thời gian 24h, mọi sự cố đứt cáp mạng, phân vùng mạng (network partition) hay mất kết nối mạng kéo dài đều đã bị loại trừ khỏi không gian điều kiện hóa.
  Xác suất $q_i$ không đo lường một gói tin mạng đơn lẻ mà đo lường việc hoàn thành hành động sau toàn bộ quy trình retry và fallback.
  Do đó, cận trên $u_i$ và cận dưới $l_i$ thuần túy phản ánh **rủi ro xử lý nội bộ dai dẳng không thể phục hồi (unrecovered persistent processing failures)** trên Domain Controller hoặc KDC sau khi đã thực hiện hết các lượt thử và vượt quá thời hạn hành động:
  1. Đối với SAMR: Tranh chấp khóa ghi cơ sở dữ liệu NTDS/ESE hoặc DC stall / cạn kiệt luồng xử lý RPC máy chủ kéo dài liên tục vượt quá 15 phút.
  2. Đối với Kerberos: Hàng đợi xử lý của KDC bị tắc nghẽn kéo dài, cạn kiệt luồng worker của tiến trình KDC/LSASS hoặc lỗi xử lý token/PAC nội bộ vượt quá thời hạn 10 phút (kênh mạng đã được $S$ bảo đảm khả dụng xuyên suốt horizon).
  3. Đối với WinRM: Cạn kiệt hạn ngạch phiên làm việc (`MaxShellsPerUser`, `MaxConcurrentUsers`) hoặc lỗi cấp phát desktop heap cho tiến trình worker `wsmprovhost.exe` kéo dài liên tục vượt quá 30 phút.

### 5.4. Bảng định mức chi tiết 11 câu hỏi có điều kiện

#### Câu hỏi 1: `cand_seamless_01_direct_lidia:q1`
- **Hành động đích (Outcome):** Hoàn tất đặt lại mật khẩu cho tài khoản Domain Admin `Lidia` từ máy tính `TSTWVIR` sau khi áp dụng chính sách thử lại (tối đa 3 lần thử trong thời hạn 15 phút).
- **Lịch sử tiền tố (History):** Không có bước chủ động trước đó (chỉ $F, S$).
- **Dữ kiện quan sát ($F$):** `TSTWVIR$` có ACE GenericAll trên `Lidia` (`20210920185958_users.json#/users/2310/Aces/3`); tài khoản `Lidia` kích hoạt (`enabled: true`, SID `...-3398`).
- **Giả thiết kịch bản ($S$):** `foothold_controlled_tstwvir=true`, `network_rpc_reachable=true`, `password_policy_accepts_lidia=true`, `directory_write_allowed_lidia=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-SAMR` ([MS-SAMR 3.1.5.6.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/99ee9f39-43e8-4bba-ac3a-82e0c0e0699e)).
- **Độ bất định dư thừa (Residual Uncertainty không bị triệt tiêu bởi $S$ và retry policy):**
  Dù $S$ đảm bảo kênh truyền và phân quyền cho phép ghi, và retry policy hỗ trợ tới 3 lần thử trong 15 phút, thao tác vẫn đối mặt với rủi ro thất bại dai dẳng:
  1. Tranh chấp khóa ghi cơ sở dữ liệu NTDS/ESE trên DC kéo dài liên tục vượt quá thời hạn 15 phút do các tiến trình bảo trì hoặc đồng bộ directory ngầm khác.
  2. Cạn kiệt luồng worker của dịch vụ RPC máy chủ hoặc tranh chấp commit transaction trên DC kéo dài trên toàn bộ các lượt thử (kênh mạng đã được $S$ bảo đảm khả dụng xuyên suốt horizon).
- **Phương pháp đề xuất khoảng $[l, u] = [7/10, 9/10] = [0.70, 0.90]$:**
  - Trường hợp thuận lợi ($u = 0.90$): DC tải nhẹ, giao dịch hoàn tất thành công trong các lượt thử đầu hoặc sau retry ngắn (giữ 10% cho rủi ro tranh chấp khóa ghi NTDS kéo dài vượt quá thời hạn 15 phút).
  - Trường hợp bất lợi ($l = 0.70$): DC chịu tải cao liên tục, hàng đợi trễ hoặc tranh chấp khóa ghi NTDS kéo dài làm cạn kiệt số lượt thử và vượt quá thời hạn 15 phút.

#### Câu hỏi 2: `cand_seamless_01_direct_lidia:q2`
- **Hành động đích (Outcome):** Hoàn tất nhận vé Ticket Granting Ticket (TGT) hợp lệ cho `Lidia` qua Kerberos AS Exchange sau khi áp dụng chính sách thử lại và fallback (tối đa 3 lần thử, UDP tự động fallback sang TCP trong thời hạn 10 phút).
- **Lịch sử tiền tố (History):** `WU_RESET_LIDIA` thành công.
- **Dữ kiện quan sát ($F$):** `Lidia` tồn tại, tài khoản yêu cầu Kerberos pre-authentication.
- **Giả thiết kịch bản ($S$):** `network_kdc_reachable=true`, `authentication_accepted_lidia=true`, `membership_security_group_usable_lidia_da=true`.
  *(Lưu ý: Khóa tài khoản, pre-auth credentials, valid time context và authentication controls đều đã conditioned true trong $S$).*
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-RFC4120` ([RFC 4120 Section 3.1, 7.2.1, 7.2.2, 8.1](https://datatracker.ietf.org/doc/html/rfc4120)) và `SRC-KILE` ([MS-KILE 3.3.5.1](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/f5993d64-a280-4555-9fcc-922fb934fc27)).
- **Độ bất định dư thừa (Residual Uncertainty không bị triệt tiêu bởi $S$ và retry policy):**
  Do `network_kdc_reachable` đã giả định kênh mạng tới KDC khả dụng xuyên suốt horizon 24h và bối cảnh thời gian hợp lệ (loại trừ sự cố mạng và clock skew), và retry policy đã bao hàm TCP fallback (loại trừ rủi ro mất gói UDP đơn lẻ), độ bất định dư thừa chỉ gồm các rủi ro xử lý nội bộ dai dẳng phía KDC/DC:
  1. Hàng đợi xử lý của KDC bị tắc nghẽn kéo dài liên tục trên toàn bộ thời hạn 10 phút do tải xác thực đồng thời cao khi giải mã pre-auth và dựng PAC cho tài khoản quản trị.
  2. Cạn kiệt tài nguyên xử lý hoặc nghẽn luồng worker của tiến trình KDC/LSASS trên DC làm cạn kiệt toàn bộ các lượt thử lại trong thời hạn hành động.
- **Phương pháp đề xuất khoảng $[l, u] = [4/5, 19/20] = [0.80, 0.95]$:**
  - Trường hợp thuận lợi ($u = 0.95$): KDC tiếp nhận và cấp vé thành công ngay trong các lượt thử đầu hoặc sau retry ngắn (giữ 5% cho rủi ro đột biến tải hàng đợi KDC nội bộ kéo dài vượt quá thời hạn 10 phút).
  - Trường hợp bất lợi ($l = 0.80$): KDC chịu tải xác thực dồn dập kéo dài làm tắc nghẽn hàng đợi xử lý KDC nội bộ trên toàn bộ thời hạn 10 phút.

#### Câu hỏi 3: `cand_seamless_01_direct_lidia:q3`
- **Hành động đích (Outcome):** Hoàn tất khởi tạo phiên PowerShell Remoting qua WinRM và thực thi lệnh quản trị với elevated token trên DC `BADBLOOD` sau khi áp dụng chính sách thử lại (tối đa 3 lần thử trong thời hạn 30 phút).
- **Lịch sử tiền tố (History):** `WU_RESET_LIDIA`, `WU_ACTIVATE_LIDIA` thành công.
- **Dữ kiện quan sát ($F$):** DC `BADBLOOD` kích hoạt (`20210920185958_computers.json#/computers/0/Properties/enabled`), Domain Admins có ACE GenericAll trên DC (`20210920185958_computers.json#/computers/0/Aces/1`), và `Lidia` là thành viên Domain Admins (`20210920185958_groups.json#/groups/40/Members/0`).
- **Giả thiết kịch bản ($S$):** `network_winrm_reachable=true`, `service_winrm_running=true`, `da_host_admin_mapping=true`, `winrm_authentication_accepted_lidia=true`, `endpoint_authorized_lidia=true`, `admin_execution_context_lidia=true`.
  *(Lưu ý: Tường lửa, service state, listener, endpoint authorization, và admin context đều đã assumed true trong $S$).*
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-WSMV` ([MS-WSMV 3.1.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wsmv/568385a0-0676-493f-bcd7-380b6e7cb7ee)) và `SRC-PSRP` ([MS-PSRP 3.1.5.3](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-psrp/01b38726-b7d8-4c72-a924-a7168ce2f1d0)).
- **Độ bất định dư thừa (Residual Uncertainty không bị triệt tiêu bởi $S$ và retry policy):**
  Dù $S$ đảm bảo transport thông suốt, service chạy, user được cấp quyền và context elevated:
  1. Cạn kiệt hạn ngạch phiên làm việc (WinRM Quota Exhaustion) kéo dài liên tục trên DC (`MaxShellsPerUser`, `MaxConcurrentUsers`) do các phiên nền khác chiếm giữ suốt 30 phút.
  2. Lỗi cấp phát desktop heap hoặc bộ nhớ worker process (`wsmprovhost.exe`) trên DC kéo dài dưới tải hệ thống nặng.
- **Phương pháp đề xuất khoảng $[l, u] = [3/5, 4/5] = [0.60, 0.80]$:**
  - Trường hợp thuận lợi ($u = 0.80$): Quota phiên khả dụng hoặc giải phóng kịp thời sau retry ngắn (giữ 20% cho rủi ro tranh chấp tài nguyên heap/quota kéo dài vượt quá thời hạn 30 phút).
  - Trường hợp bất lợi ($l = 0.60$): Tải DC cao liên tục, hạn ngạch shell bị chiếm dụng kéo dài làm kiệt hạn ngạch phiên trong suốt thời hạn 30 phút.

#### Câu hỏi 4: `cand_seamless_02_alt_vajer_ollie:q1`
- **Hành động đích (Outcome):** Hoàn tất đặt lại mật khẩu cho `Josefa` từ `TSTWVIR` sau khi áp dụng chính sách thử lại (tối đa 3 lần thử trong thời hạn 15 phút).
- **Lịch sử tiền tố (History):** Không có bước chủ động trước đó (chỉ $F, S$).
- **Dữ kiện quan sát ($F$):** `TSTWVIR$` có GenericAll trên `Josefa` (`20210920185958_users.json#/users/666/Aces/3`), `Josefa` enabled.
- **Giả thiết kịch bản ($S$):** `foothold_controlled_tstwvir=true`, `network_rpc_reachable=true`, `password_policy_accepts_josefa=true`, `directory_write_allowed_josefa=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-SAMR` ([MS-SAMR 3.1.5.6.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/99ee9f39-43e8-4bba-ac3a-82e0c0e0699e)).
- **Độ bất định dư thừa:** Tương tự $q_1$ về rủi ro tranh chấp khóa ghi NTDS hoặc cạn kiệt luồng xử lý RPC máy chủ kéo dài vượt quá 15 phút; do Josefa là tài khoản người dùng thông thường trong nhóm quản trị nội bộ VA-JER (không phải Domain Admin), ít chịu ảnh hưởng từ các tiến trình bảo trì tài khoản đặc quyền nền.
- **Phương pháp đề xuất khoảng $[l, u] = [3/4, 9/10] = [0.75, 0.90]$:**
  - Cận dưới $l=0.75$, cận trên $u=0.90$.

#### Câu hỏi 5: `cand_seamless_02_alt_vajer_ollie:q2`
- **Hành động đích (Outcome):** Hoàn tất nhận vé TGT cho `Josefa` qua Kerberos AS Exchange sau khi áp dụng chính sách thử lại và fallback (tối đa 3 lần thử, UDP fallback TCP trong 10 phút).
- **Lịch sử tiền tố (History):** `WU_RESET_JOSEFA` thành công.
- **Dữ kiện quan sát ($F$):** `Josefa` enabled.
- **Giả thiết kịch bản ($S$):** `network_kdc_reachable=true`, `authentication_accepted_josefa=true`, `membership_security_group_usable_josefa_vajer=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-RFC4120` ([RFC 4120 Section 3.1, 7.2.1, 7.2.2, 8.1](https://datatracker.ietf.org/doc/html/rfc4120)) và `SRC-KILE` ([MS-KILE 3.3.5.1](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/f5993d64-a280-4555-9fcc-922fb934fc27)).
- **Độ bất định dư thừa:** Tương tự $q_2$ về rủi ro tắc nghẽn hàng đợi xử lý KDC nội bộ hoặc cạn kiệt luồng LSASS kéo dài vượt quá thời hạn 10 phút.
- **Phương pháp đề xuất khoảng $[l, u] = [4/5, 19/20] = [0.80, 0.95]$:**
  - Cận dưới $l=0.80$, cận trên $u=0.95$.

#### Câu hỏi 6: `cand_seamless_02_alt_vajer_ollie:q3`
- **Hành động đích (Outcome):** Hoàn tất đặt lại mật khẩu cho `Ollie` trong ngữ cảnh `Josefa` sử dụng quyền của nhóm `VA-JER-ADMINGROUP1` sau khi áp dụng chính sách thử lại (tối đa 3 lần thử trong thời hạn 15 phút).
- **Lịch sử tiền tố (History):** `WU_RESET_JOSEFA`, `WU_ACTIVATE_JOSEFA` thành công.
- **Dữ kiện quan sát ($F$):** `Josefa` là MemberOf của `VA-JER-ADMINGROUP1` (`20210920185958_groups.json#/groups/246/Members/14`), nhóm có GenericAll trên `Ollie` (`20210920185958_users.json#/users/917/Aces/3`), `Ollie` enabled.
- **Giả thiết kịch bản ($S$):** `password_policy_accepts_ollie=true`, `directory_write_allowed_ollie=true`, `membership_security_group_usable_josefa_vajer=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-SAMR` ([MS-SAMR 3.1.5.6.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/99ee9f39-43e8-4bba-ac3a-82e0c0e0699e)) và `SRC-PAC` ([MS-PAC 2.5](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-pac/69e86ccc-85e3-41b9-b514-7d969cd0ed73)).
- **Độ bất định dư thừa:**
  Thao tác qua phiên đăng nhập trung gian yêu cầu xác thực Kerberos RPC bind và validation PAC token:
  1. Tranh chấp phiên xác thực Kerberos qua SPNEGO và xử lý quyền hạn người dùng trung gian trên DC kéo dài.
  2. NTDS lock contention trên tài khoản Ollie kéo dài vượt quá thời hạn 15 phút.
- **Phương pháp đề xuất khoảng $[l, u] = [7/10, 17/20] = [0.70, 0.85]$:**
  - Cận dưới $l=0.70$, cận trên $u=0.85$.

#### Câu hỏi 7: `cand_seamless_02_alt_vajer_ollie:q4`
- **Hành động đích (Outcome):** Hoàn tất nhận vé TGT cho `Ollie` qua Kerberos AS Exchange sau khi áp dụng chính sách thử lại và fallback (tối đa 3 lần thử, UDP fallback TCP trong 10 phút).
- **Lịch sử tiền tố (History):** 3 bước trước thành công.
- **Dữ kiện quan sát ($F$):** `Ollie` enabled.
- **Giả thiết kịch bản ($S$):** `network_kdc_reachable=true`, `authentication_accepted_ollie=true`, `membership_security_group_usable_ollie_da=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-RFC4120` ([RFC 4120 Section 3.1, 7.2.1, 7.2.2, 8.1](https://datatracker.ietf.org/doc/html/rfc4120)) và `SRC-KILE` ([MS-KILE 3.3.5.1](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/f5993d64-a280-4555-9fcc-922fb934fc27)).
- **Độ bất định dư thừa:** Tương tự $q_2$ về rủi ro tắc nghẽn hàng đợi xử lý KDC nội bộ hoặc cạn kiệt luồng LSASS kéo dài vượt quá thời hạn 10 phút.
- **Phương pháp đề xuất khoảng $[l, u] = [4/5, 19/20] = [0.80, 0.95]$:**
  - Cận dưới $l=0.80$, cận trên $u=0.95$.

#### Câu hỏi 8: `cand_seamless_02_alt_vajer_ollie:q5`
- **Hành động đích (Outcome):** Hoàn tất khởi tạo phiên WinRM elevated trên DC `BADBLOOD` qua tài khoản `Ollie` sau khi áp dụng chính sách thử lại (tối đa 3 lần thử trong thời hạn 30 phút).
- **Lịch sử tiền tố (History):** 4 bước trước thành công.
- **Dữ kiện quan sát ($F$):** `Ollie` là MemberOf của Domain Admins, DC tồn tại.
- **Giả thiết kịch bản ($S$):** `network_winrm_reachable=true`, `service_winrm_running=true`, `da_host_admin_mapping=true`, `winrm_authentication_accepted_ollie=true`, `endpoint_authorized_ollie=true`, `admin_execution_context_ollie=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-WSMV` ([MS-WSMV 3.1.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wsmv/568385a0-0676-493f-bcd7-380b6e7cb7ee)) và `SRC-PSRP` ([MS-PSRP 3.1.5.3](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-psrp/01b38726-b7d8-4c72-a924-a7168ce2f1d0)).
- **Độ bất định dư thừa:** Tương tự $q_3$ về cạn kiệt hạn ngạch phiên WinRM hoặc lỗi heap tiến trình con `wsmprovhost.exe` kéo dài vượt quá 30 phút.
- **Phương pháp đề xuất khoảng $[l, u] = [3/5, 4/5] = [0.60, 0.80]$:**
  - Cận dưới $l=0.60$, cận trên $u=0.80$.

#### Câu hỏi 9: `cand_seamless_source_b_01_ollie:q1`
- **Hành động đích (Outcome):** Hoàn tất đặt lại mật khẩu `Ollie` trực tiếp từ máy tính foothold B (`FINWVIR$`) qua quyền GenericAll sau khi áp dụng chính sách thử lại (tối đa 3 lần thử trong thời hạn 15 phút).
- **Lịch sử tiền tố (History):** Không có bước chủ động trước đó (chỉ $F_B, S_B$).
- **Dữ kiện quan sát ($F_B$):** `FINWVIR$` có GenericAll trên `Ollie` (`20210920185958_users.json#/users/917/Aces/11`), `Ollie` enabled.
- **Giả thiết kịch bản ($S_B$):** `foothold_controlled_finwvir=true`, `network_rpc_reachable=true`, `password_policy_accepts_ollie=true`, `directory_write_allowed_ollie=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-SAMR` ([MS-SAMR 3.1.5.6.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/99ee9f39-43e8-4bba-ac3a-82e0c0e0699e)).
- **Độ bất định dư thừa:** Tương tự $q_1$ về rủi ro tranh chấp khóa ghi NTDS hoặc cạn kiệt luồng xử lý RPC máy chủ kéo dài vượt quá 15 phút.
- **Phương pháp đề xuất khoảng $[l, u] = [7/10, 9/10] = [0.70, 0.90]$:**
  - Cận dưới $l=0.70$, cận trên $u=0.90$.

#### Câu hỏi 10: `cand_seamless_source_b_01_ollie:q2`
- **Hành động đích (Outcome):** Hoàn tất nhận vé TGT cho `Ollie` từ foothold B qua Kerberos AS Exchange sau khi áp dụng chính sách thử lại và fallback (tối đa 3 lần thử, UDP fallback TCP trong 10 phút).
- **Lịch sử tiền tố (History):** Bước reset Ollie từ B thành công.
- **Dữ kiện quan sát ($F_B$):** `Ollie` enabled.
- **Giả thiết kịch bản ($S_B$):** `network_kdc_reachable=true`, `authentication_accepted_ollie=true`, `membership_security_group_usable_ollie_da=true`.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-RFC4120` ([RFC 4120 Section 3.1, 7.2.1, 7.2.2, 8.1](https://datatracker.ietf.org/doc/html/rfc4120)) và `SRC-KILE` ([MS-KILE 3.3.5.1](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/f5993d64-a280-4555-9fcc-922fb934fc27)).
- **Độ bất định dư thừa:** Tương tự $q_2$ về rủi ro tắc nghẽn hàng đợi xử lý KDC nội bộ hoặc cạn kiệt luồng LSASS kéo dài vượt quá thời hạn 10 phút.
- **Phương pháp đề xuất khoảng $[l, u] = [4/5, 19/20] = [0.80, 0.95]$:**
  - Cận dưới $l=0.80$, cận trên $u=0.95$.

#### Câu hỏi 11: `cand_seamless_source_b_01_ollie:q3`
- **Hành động đích (Outcome):** Hoàn tất khởi tạo phiên WinRM elevated trên DC `BADBLOOD` qua tài khoản `Ollie` từ foothold B sau khi áp dụng chính sách thử lại (tối đa 3 lần thử trong thời hạn 30 phút).
- **Lịch sử tiền tố (History):** 2 bước trước thành công.
- **Dữ kiện quan sát ($F_B$):** DC tồn tại, Ollie có DA.
- **Giả thiết kịch bản ($S_B$):** Toàn bộ giả thiết kết nối WinRM và quyền admin tương ứng cho Source B.
- **Căn cứ cơ chế kỹ thuật:** Tham chiếu `SRC-WSMV` ([MS-WSMV 3.1.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wsmv/568385a0-0676-493f-bcd7-380b6e7cb7ee)) và `SRC-PSRP` ([MS-PSRP 3.1.5.3](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-psrp/01b38726-b7d8-4c72-a924-a7168ce2f1d0)).
- **Độ bất định dư thừa:** Tương tự $q_3$ về cạn kiệt hạn ngạch phiên WinRM hoặc lỗi heap tiến trình con `wsmprovhost.exe` kéo dài vượt quá 30 phút.
- **Phương pháp đề xuất khoảng $[l, u] = [3/5, 4/5] = [0.60, 0.80]$:**
  - Cận dưới $l=0.60$, cận trên $u=0.80$.

## 6. Vết tính toán và kết quả xếp hạng Pareto đề xuất

### 6.1. Vết tính toán tích khoảng xác suất (Calculation Traces)

Theo quy tắc chuỗi nhân phân số chính xác tuyệt đối (Lossless Rational Chain Rule):

- **Candidate 1 (`cand_seamless_01_direct_lidia`):**
  - Cận dưới:
    $$l_1 = \frac{7}{10} \times \frac{4}{5} \times \frac{3}{5} = \frac{84}{250} = \frac{42}{125} \approx 0.336.$$
  - Cận trên:
    $$u_1 = \frac{9}{10} \times \frac{19}{20} \times \frac{4}{5} = \frac{684}{1000} = \frac{171}{250} \approx 0.684.$$
  - Khoảng xác suất: $P_1 = \left[\frac{42}{125}, \frac{171}{250}\right] = [0.336, 0.684]$.
  - Tác động: $I_1 = \text{High}$.
  - Nỗ lực: $C_1 = 2$.

- **Candidate 2 (`cand_seamless_02_alt_vajer_ollie`):**
  - Cận dưới:
    $$l_2 = \frac{3}{4} \times \frac{4}{5} \times \frac{7}{10} \times \frac{4}{5} \times \frac{3}{5} = \frac{3}{5} \times \frac{7}{10} \times \frac{4}{5} \times \frac{3}{5} = \frac{21}{50} \times \frac{12}{25} = \frac{252}{1250} = \frac{126}{625} \approx 0.2016.$$
  - Cận trên:
    $$u_2 = \frac{9}{10} \times \frac{19}{20} \times \frac{17}{20} \times \frac{19}{20} \times \frac{4}{5} = \frac{171}{200} \times \frac{17}{20} \times \frac{76}{100} = \frac{2907}{4000} \times \frac{19}{25} = \frac{55233}{100000} \approx 0.55233.$$
  - Khoảng xác suất: $P_2 = \left[\frac{126}{625}, \frac{55233}{100000}\right] \approx [0.2016, 0.55233]$.
  - Tác động: $I_2 = \text{High}$.
  - Nỗ lực: $C_2 = 3$.

- **Candidate B (`cand_seamless_source_b_01_ollie`):**
  - Cận dưới: $l_B = \frac{7}{10} \times \frac{4}{5} \times \frac{3}{5} = \frac{42}{125} \approx 0.336$.
  - Cận trên: $u_B = \frac{9}{10} \times \frac{19}{20} \times \frac{4}{5} = \frac{171}{250} \approx 0.684$.
  - Khoảng xác suất: $P_B = \left[\frac{42}{125}, \frac{171}{250}\right] = [0.336, 0.684]$.
  - Tác động: $I_B = \text{High}$.
  - Nỗ lực: $C_B = 2$.

### 6.2. Phân tích quan hệ ưu thế Pareto trong Source A

- So sánh hai ứng viên:
  - Tác động: $I_1 = I_2 = \text{High}$.
  - Khoảng xác suất: $P_1 = [0.336, 0.684]$ và $P_2 \approx [0.2016, 0.55233]$.
- Kiểm tra điều kiện ưu thế Pareto bảo thủ (ADR-0013 Mục 3):
  - Ứng viên 1 ưu thế Ứng viên 2 khi và chỉ khi: $I_1 \ge I_2$ và $l_1 \ge u_2$, đồng thời có ít nhất một bất đẳng thức nghiêm ngặt ($I_1 > I_2$ hoặc $l_1 > u_2$).
  - Ta có:
    $$l_1 = 0.336 < 0.55233 \approx u_2.$$
  - Do $l_1 < u_2$, hai khoảng xác suất giao nhau trên đoạn $[0.336, 0.55233]$.
  - Tồn tại khả năng giá trị xác suất thực tế của Ứng viên 2 ($0.50$) vượt trội Ứng viên 1 ($0.35$).
  - Do đó, Ứng viên 1 **không** ưu thế Ứng viên 2.
  - Ngược lại, $l_2 \approx 0.2016 < 0.684 = u_1$, nên Ứng viên 2 cũng **không** ưu thế Ứng viên 1.
- Kết luận xếp hạng:
  - Quan hệ ưu thế: `scoped_preference == "incomparable"`.
  - Biên Pareto rủi ro: Cả hai ứng viên đều nằm trên biên Pareto:
    $$\text{Pareto Frontier} = \{\text{cand\_seamless\_01\_direct\_lidia}, \text{cand\_seamless\_02\_alt\_vajer\_ollie}\}.$$

### 6.3. Phân tích đường nỗ lực tối thiểu tới Domain Admin (Min-Effort-to-DA)

- Mục tiêu: Tìm ứng viên đạt được sự kiện mục tiêu với tổng nỗ lực chuẩn tắc $C$ nhỏ nhất.
- So sánh nỗ lực:
  - Candidate 1: $C_1 = 2$.
  - Candidate 2: $C_2 = 3$.
- Kết quả truy vấn:
  - Ứng viên được chọn: `cand_seamless_01_direct_lidia` với nỗ lực tối thiểu $C = 2$.
  - Độ bao phủ công bố (`coverage_disclosure`): Đánh giá trên tập ứng viên được sinh ra trong giới hạn ngân sách công việc (`active_work_budget: 6`); không đảm bảo tối ưu toàn cục nếu tồn tại các đơn vị công việc chưa được định mức hoặc các đường đi cấu trúc chưa được duyệt tới.
- Nhận xét kiến trúc:
  Candidate 1 là giải pháp tối ưu cho truy vấn Min-Effort-to-DA, nhưng Candidate 2 vẫn đồng thời tồn tại trên biên Pareto rủi ro do tính chất không so sánh được về mặt xác suất.
  Điều này minh chứng sự phân tách rõ ràng giữa bài toán biên Pareto rủi ro và bài toán đường nỗ lực tối thiểu theo ADR-0013 Mục 6.

## 7. Phân tích độ nhạy (Sensitivity Analysis)

Phân tích độ nhạy được chia thành hai nhóm rõ ràng: Phân tích độ nhạy lân cận quanh đề xuất (Neighborhood Sensitivity) và Kiểm tra tuân thủ bất biến và hành vi (Behavioral Conformance Probes).
Báo cáo máy đọc được ghi nhận tại `reports/research/seamless-parameter-validation-report.json`.

### 7.1. Phân tích độ nhạy lân cận quanh đề xuất (Neighborhood Sensitivity)

1. **Biến động ma sát tương tác ($T_2$) trên đường Lidia:**
   - Điều chỉnh: Giả sử ma sát tương tác của thao tác đặt lại mật khẩu Lidia và kết nối WinRM Lidia tăng từ mức trung bình lên mức cao ($T_2: 2 \to 3$), nỗ lực tương ứng cập nhật theo rubric $C = T_1 + T_2 - 2 = 1 + 3 - 2 = 2$.
   - Kết quả đầu vào: Tổng nỗ lực của Candidate 1 tăng từ 2 lên 4 ($C_1: 2 \to 4$), trong khi Candidate 2 giữ nguyên $C_2 = 3$.
   - Chẩn đoán:
     - Trên truy vấn Min-Effort-to-DA, ứng viên chiến thắng bị đảo chiều (flip) từ Candidate 1 sang Candidate 2 (`cand_seamless_02_alt_vajer_ollie`, $C=3 < 4$).
     - Trên biên Pareto, do các khoảng xác suất vẫn giao nhau ($[0.336, 0.684]$ và $[0.2016, 0.55233]$), cả hai ứng viên tiếp tục giữ trạng thái `incomparable` và cùng nằm trên biên Pareto.
     - Kết luận: Truy vấn Min-Effort-to-DA nhạy cảm với biến thiên ma sát tương tác của từng bước, trong khi biên Pareto rủi ro duy trì tính ổn định cấu trúc trước các biến động nỗ lực.

2. **Thu hẹp khoảng xác suất lồng nhau (Strictly Nested Bounds Narrowing):**
   - Điều chỉnh: Giả sử qua bằng chứng bổ sung, các khoảng xác suất của Candidate 1 được thu hẹp về các tập con thực sự bên trong khoảng đề xuất ban đầu:
     - $q_1 \in [17/20, 9/10] \subset [7/10, 9/10]$
     - $q_2 \in [9/10, 19/20] \subset [4/5, 19/20]$
     - $q_3 \in [3/4, 4/5] \subset [3/5, 4/5]$
   - Kết quả: Khoảng xác suất mới của Candidate 1 là $P_1 = [459/800, 171/250] = [0.57375, 0.684]$.
   - Chẩn đoán:
     - Cận dưới mới $l_1 = 0.57375$ vượt qua cận trên $u_2 \approx 0.55233$ của Candidate 2 ($l_1 > u_2$).
     - Điều kiện ưu thế Pareto bảo thủ được kích hoạt: Candidate 1 chiếm ưu thế tuyệt đối trước Candidate 2 (`scoped_preference == "a"`).
     - Biên Pareto rút gọn còn 1 ứng viên duy nhất: `["cand_seamless_01_direct_lidia"]`.
     - Xác định ngưỡng nhạy cảm: Ngưỡng tới hạn để phá vỡ thế bất phân thắng bại của biên Pareto là khi cận dưới của Candidate 1 được hiệu chuẩn vượt qua giá trị $0.55233$.

3. **Quét biên độ giao nhau và kiểm thử độ nhạy chuỗi tham số (Bounds Overlap Margin & Executed Sensitivity Sweep):**
   - Phân tích khoảng cách đơn biến (Single-variable analytic margin gap):
     Khoảng cách giao nhau giữa cận dưới của Candidate 1 ($l_1 = 42/125 = 0.336$) và cận trên của Candidate 2 ($u_2 = 55233/100000 \approx 0.55233$) là:
     $$\Delta = u_2 - l_1 = 0.55233 - 0.336 = 0.21633.$$
     Nếu giữ cố định cận trên $u_2$, cận dưới $l_1$ phải tăng thêm $+0.21633$ (tương đương mức tăng $+64.4\%$) để phá vỡ thế giao nhau của hai khoảng xác suất theo chiều tăng $l_1$.
   - Kiểm thử quét kịch bản thực tế (Executed multi-scenario sweep):
     Khi thực hiện kiểm thử độ nhạy đồng thời trên chuỗi tham số qua `execute_ranking_roundtrip()`, giả định các cận trên của Candidate 2 bị giảm $10\%$ qua từng bước (nhân hệ số $9/10$, tương ứng: $q_1 \in [3/4, 81/100]$, $q_2 \in [4/5, 171/200]$, $q_3 \in [7/10, 153/200]$, $q_4 \in [4/5, 171/200]$, $q_5 \in [3/5, 18/25]$).
     Tích luỹ cận trên mới của Candidate 2 qua 5 bước suy giảm xuống:
     $$u_2' = \frac{81}{100} \times \frac{171}{200} \times \frac{153}{200} \times \frac{171}{200} \times \frac{18}{25} = \frac{3261453417}{10000000000} \approx 0.3261453417.$$
     Do $u_2' \approx 0.32615 < 0.336 = l_1$, điều kiện ưu thế Pareto bảo thủ $l_1 > u_2'$ được kích hoạt.
     Biên Pareto rủi ro đảo chiều (flip) và sụp đổ từ hai ứng viên không so sánh được về chỉ còn duy nhất `['cand_seamless_01_direct_lidia']`.
   - Kết luận:
     Việc xếp hạng đảo chiều khi các cận trên của chuỗi hành động dài suy giảm đồng thời là minh chứng về độ nhạy hữu ích của mô hình tính toán.
     Biên Pareto không bị cố định cứng nhắc mà phản ánh trực tiếp sự dịch chuyển của các giả thiết tham số đầu vào.

### 7.2. Kiểm tra tuân thủ bất biến và hành vi (Behavioral Conformance Probes)

1. **Kiểm tra Tie-Break bằng nỗ lực khi xác suất điểm bằng nhau:**
   - Thiết lập xác suất điểm chính xác đồng nhất cho cả hai ứng viên: $P_1 = P_2 = [3/10, 3/10]$, cùng tác động `High`.
   - Kết quả: Candidate 1 chiến thắng tie-break nhờ nỗ lực thấp hơn ($C_1 = 2 < C_2 = 3$).
     Biên Pareto chỉ giữ Candidate 1.

2. **Kiểm tra dịch chuyển mức tác động sang Critical:**
   - Chuyển mức tác động của Domain Controller sang `Critical` cho cả hai ứng viên.
   - Kết quả: Cả hai ứng viên cùng nhận mức `Critical`, biên Pareto bảo toàn đầy đủ cả 2 ứng viên.

3. **Kiểm tra cơ chế đóng an toàn khi thiếu căn cứ tác động (Fail-Closed):**
   - Đặt `rating_status: "unrated"` cho tài sản đích.
   - Kết quả: Cả hai ứng viên bị loại khỏi tập hợp lệ, biên Pareto rỗng (`[]`), tập `diagnostics` ghi nhận 2 ứng viên thiếu căn cứ tác động.

4. **Kiểm tra quyền phủ quyết dữ kiện sai bắt buộc (Known-False Veto):**
   - Thiết lập vị từ tiên quyết bắt buộc `endpoint_authorized_lidia = False`.
   - Kết quả: Candidate 1 lập tức chuyển sang trạng thái `blocked` và bị đưa vào `diagnostics`.
     Candidate 2 là ứng viên duy nhất trên biên Pareto.

5. **Kiểm tra tính không phủ quyết của dữ kiện sai không liên quan (Irrelevant False No-op):**
   - Thêm một vị từ sai không liên quan vào `false_facts` (`synthetic_unrelated_service_reachable = False`).
   - Kết quả: Do không có ứng viên nào yêu cầu vị từ này trong chuỗi chứng minh khả thi, cả hai ứng viên đều không bị chặn và biên Pareto giữ nguyên cả hai ứng viên.
     Điều này khẳng định quyền phủ quyết chỉ tác động trên tập vị từ bắt buộc của từng ứng viên.

6. **Kiểm tra cơ chế phân vùng dữ kiện thiếu bắt buộc (Unknown-Fact Gating):**
   - Loại bỏ vị từ tiên quyết `winrm_authentication_accepted_lidia` khỏi tập `assumed_facts`.
   - Kết quả: Candidate 1 chuyển sang trạng thái `unknown` và bị đưa vào `diagnostics`.
     Biên Pareto chỉ còn Candidate 2.

## 8. Kết luận và khuyến nghị bàn giao

1. Hồ sơ căn cứ này cung cấp đầy đủ các giá trị số học, nguồn gốc kỹ thuật từ chuẩn Microsoft, và phân tích độ bất định dư thừa sau điều kiện hóa cho 11 câu hỏi có điều kiện và 9 đơn vị công việc chuẩn tắc.
2. Script kiểm chứng `scripts/research/seamless_parameter_validation.py` hỗ trợ thực thi trực tiếp từ thư mục gốc kho mã nguồn và tái lập toàn bộ vết tính toán, độ nhạy lân cận và các bất biến giao diện.
3. Toàn bộ các định mức duy trì ở trạng thái **Proposed** và phán quyết dự đoán là **Insufficient Evidence**; không tự ý suy diễn năng lực chuyên gia hay hiệu chuẩn sản phẩm khi chưa có đánh giá thực tế độc lập của con người.
