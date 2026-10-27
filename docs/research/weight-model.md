# Historical weight model - Profile maut_v1

Trạng thái: Historical / experimental reference; không phải production weighting specification.
Chủ trì: Thực tập sinh A (@Lolavine777).
Reviewer: Thực tập sinh B (@nairyuuu).
Liên kết: Refs #5, [ADR-0001](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0001-maut-weighting-model.md), [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42).

> [!IMPORTANT]
> Tài liệu này bảo tồn rubric và score `maut_v1` để audit lịch sử.
> Không dùng các giá trị hoặc hệ số bên dưới để tạo production profile mới.
> Post-report mentor feedback ngày 2026-09-25 yêu cầu #42 kiểm tra cost ownership, criterion independence và double-count trước khi chấm số.
> `Detectability` phụ thuộc mạnh vào environment monitoring và không còn là dimension mặc định.
> `Reliability` / success probability không được dùng như independent dimension nếu nó chỉ là kết quả tổng hợp của prerequisites, complexity hoặc runtime controls.
> Successor ADR cho production weighting chỉ được tạo sau khi design của #42 được review và accepted.

---

## 1. Muc Tieu Va Lua Chon Mo Hinh

Mô hình trọng số `maut_v1` đo lường **chi phí rủi ro và độ cản trở khai thác tương đối** của kẻ tấn công trong môi trường Active Directory.
Đơn vị của trọng số là chỉ số chi phí phi thứ nguyên (dimensionless cost metric) nằm trong khoảng $[1.0, 5.0]$.
Mô hình không quy đổi trực tiếp chỉ số chi phí thành thời gian vật lý (phút hoặc giờ) khi chưa có số liệu đo kiểm thực nghiệm trong môi trường thật.

### Tính chất cộng dồn chi phí và liên hệ với Dijkstra
Về mặt lý thuyết, Phillips & Swiler (1998) chứng minh rằng nếu đường tấn công được đánh giá theo xác suất thành công độc lập $P_s(e) \in (0, 1]$, bài toán cực đại hóa xác suất toàn cục có thể quy đổi thành bài toán cực tiểu hóa tổng chi phí:
$$\max \prod P_s(e) \iff \min \sum (-\ln P_s(e))$$
Phép biến đổi này cung cấp cơ sở lý thuyết giải thích vì sao đồ thị tấn công có thể được mô hình hóa bằng các trọng số cộng dồn không âm trên từng bước nhảy.
Tuy nhiên, trong mô hình `maut_v1`, $W(e)$ là một **chỉ số chi phí nỗ lực và rủi ro dạng heuristic** (additive heuristic effort/risk cost index) được xây dựng dựa trên rubric chuyên gia đa thuộc tính (MAUT).
Chúng ta không tuyên bố rằng đường đi có tổng $\sum W(e)$ nhỏ nhất cũng đồng thời là đường đi có xác suất thành công lớn nhất, vì dự án chưa thực hiện hiệu chuẩn thực nghiệm (empirical calibration) giữa $W(e)$ và $P_s(e)$.
Với tính chất $W(e) \ge 1.0 > 0$, hàm chi phí đảm bảo thỏa mãn điều kiện trọng số không âm, loại bỏ mọi chu trình âm và đảm bảo thuật toán Dijkstra tìm được đường đi có tổng chi phí nỗ lực và rủi ro tích lũy nhỏ nhất một cách hiệu quả.

---

## 2. Rubric Cham Diem Vector 4D MAUT

Mỗi cạnh $e$ được định lượng qua vector $\vec{x}(e) = [P(e), D(e), C(e), R^*(e)]^T$.

| Tiêu chí | Thang đo và định nghĩa từng mức | Chiều tăng | Hệ số | Nguồn chuẩn hóa |
| :--- | :--- | :---: | :---: | :--- |
| **Prerequisites $P(e)$** | 1: User thường; 2: Đọc LDAP; 3: Kiểm soát host trung gian; 4: Local Admin; 5: Phiên Admin đồng thời | Càng cao càng khó | $0.25$ | NIST CVSS v3.1 (PR) |
| **Detectability $D(e)$** | 1: Im lặng; 2: Vé Kerberos; 3: RDP/WinRM; 4: DCSync/LSASS dump; 5: Ép đổi mật khẩu | Càng cao càng ồn | $0.40$ | MITRE ATT&CK Telemetry |
| **Complexity $C(e)$** | 1: Mặc định; 2: Tool 1 lệnh; 3: Cấu hình Kerberos S4U; 4: PKINIT/Shadow Creds; 5: Coercion + Relay | Càng cao càng phức tạp | $0.20$ | NIST CVSS v3.1 (AC) |
| **Failure Penalty $R^*(e)$** | $R^*(e) = 6 - R(e)$. Với $R$: 5: 100% thành công; 4: >90%; 3: Chờ gpupdate; 2: Phụ thuộc phiên user; 1: Dễ xịt | Càng cao càng dễ xịt | $0.15$ | Phillips & Swiler (1998) |

Công thức tính trọng số chi phí:
$$W(e) = 0.25 \cdot P(e) + 0.40 \cdot D(e) + 0.20 \cdot C(e) + 0.15 \cdot R^*(e)$$

Miền giá trị hợp lệ: $W(e) \in [1.00, 5.00]$.
Trường hợp cạnh thiếu dữ liệu hoặc không xác định loại: Parser từ chối nạp và ghi nhận vào log lỗi thay vì tự gán giá trị ngầm định.

---

## 3. Bang Trong So 8 Canh M1 (Profile maut_v1)

| Loại cạnh | P | D | C | R | $R^*$ | **Chi phí $W(e)$** | Lập luận tóm tắt |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `MemberOf` | 1 | 1 | 1 | 5 | 1 | **1.000** | Kế thừa nhóm tĩnh, hoàn toàn thụ động và im lặng. |
| `AdminTo` | 2 | 2 | 1 | 5 | 1 | **1.650** | Quyền Local Admin, thực thi lệnh trực tiếp trên máy chủ. |
| `GenericAll` | 2 | 2 | 2 | 5 | 1 | **1.850** | Toàn quyền kiểm soát đối tượng AD qua giao thức LDAP. |
| `CanPSRemote` | 2 | 3 | 2 | 5 | 1 | **2.250** | WinRM thực thi lệnh dòng lệnh, sinh Event 4104. |
| `WriteDacl` | 2 | 3 | 2 | 5 | 1 | **2.250** | Sửa DACL để tự cấp GenericAll, sinh Event 5136. |
| `ForceChangePassword` | 2 | 3 | 2 | 5 | 1 | **2.250** | Ép đổi mật khẩu tài khoản người dùng, sinh Event 4724. |
| `CanRDP` | 2 | 3 | 2 | 4 | 2 | **2.400** | Kết nối giao diện RDP (Port 3389, Event 4624 Type 10). |
| `HasSession` | 3 | 4 | 3 | 2 | 4 | **3.550** | Dump LSASS trích xuất token: Rất dễ bị EDR chặn, user có thể đăng xuất. |

---

## 4. Phan Tich Do Nhay (Sensitivity Analysis)

Khi cho hệ số phát hiện $\beta$ dao động trong khoảng từ $0.20$ đến $0.50$, thứ tự ưu tiên của các cạnh thể hiện tính ổn định cao:
- Nhóm chi phí thấp (`MemberOf`, `AdminTo`) luôn giữ vị trí ưu tiên số 1 và số 2.
- Nhóm ACL và Remote Access (`GenericAll`, `CanPSRemote`, `WriteDacl`, `CanRDP`) duy trì mức chi phí cân bằng từ $1.85$ đến $2.40$.
- Cạnh `HasSession` luôn là bước đi có chi phí cao nhất do phải chịu cả hai mức phạt nặng về độ ồn ($D=4$) và độ tin cậy thấp ($R=2$).

Tính chất này đảm bảo thuật toán Dijkstra luôn ưu tiên các con đường lạm dụng phân quyền AD tự nhiên trước khi mạo hiểm thực hiện kỹ thuật dump bộ nhớ LSASS.
