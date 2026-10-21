# Khảo sát thực nghiệm Group Nesting trong dữ liệu Active Directory

- Ngày: 2026-09-18
- Tác giả: Nguyễn Đăng Long (@Lolavine777, TTS A)
- Người thẩm định: Lê Long (@nairyuuu, TTS B)
- Liên kết: Refs #53, Refs #44, Refs #45, Refs #47, [taxonomy.md](taxonomy.md), [bloodhound-import-baseline.md](bloodhound-import-baseline.md)
- Chiến lược hiện hành: [ADR-0007](../adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md)
- Quyết định direct-only: [ADR-0009](../adr/ADR-0009-direct-memberof-transitive-resolution.md)

---

## 1. Tổng quan và động lực khảo sát

Trong đồ thị tấn công Active Directory (AD), quan hệ thành viên nhóm (`MemberOf`) là cơ chế cơ bản nhất để chủ thể an ninh (User, Computer, Group) kế thừa quyền hạn và đặc quyền.
Tuy nhiên, trong môi trường doanh nghiệp thực tế, các nhóm bảo mật thường được lồng vào nhau theo nhiều cấp (Group Nesting), tạo nên mạng lưới kế thừa phức tạp.

Mục tiêu của tài liệu này là khảo sát định lượng và định tính Week 1 trên Dataset A và Dataset B, làm rõ:
1. Tỷ lệ thực tế của quan hệ lồng nhóm so với quan hệ thành viên trực tiếp.
2. Độ sâu phân tầng (nesting depth) và các mẫu hình đặc thù (chu trình, đa đường kế thừa, lồng nhóm xuyên miền).
3. Cơ chế xử lý của baseline BloodHound CE khi nạp vào cơ sở dữ liệu Neo4j.
4. Cơ sở khoa học để thống nhất quy chuẩn taxonomy cho Graph Builder (M2-05) và Host-Access Inference (M2-06).

A/B la historical baseline.
SEAMLESS la primary structural/topology dataset cho M2+ theo ADR-0007.

---

## 2. Số liệu đo kiểm định lượng trên Dataset A và Dataset B

Khảo sát trực tiếp trên các tệp tin thô `*_groups.json` và đối chiếu với kết quả kiểm toán baseline tại [bloodhound-import-baseline.md](bloodhound-import-baseline.md):

| Chỉ số đo kiểm | Dataset A (GOAD NORTH) | Dataset B (ad_sampledata 3 miền) | Ý nghĩa kỹ thuật |
| :--- | :---: | :---: | :--- |
| **Số tệp nhóm thô** | 1 tệp (`NORTH...groups.json`) | 3 tệp (`PHANTOM`, `GHOST`, `WRAITH`) | Tập dữ liệu được thu thập bởi SharpHound |
| **Tổng số bản ghi nhóm** | 84 bản ghi | 148 bản ghi | Bao gồm Domain Groups, Builtin Groups và Local Groups |
| **Tổng số quan hệ thành viên thô (`Members[]`)** | **42** | **161** | Trùng khớp 100% với số cạnh `MemberOf` trên BloodHound CE |
| Thành viên là User | 24 (57.1%) | 73 (45.3%) | Quan hệ cơ bản `User -> Group` |
| Thành viên là Group (Group Nesting) | **15 (35.7%)** | **63 (39.1%)** | **Gần 40% quan hệ thành viên là nhóm lồng nhau** |
| Thành viên là Computer | 1 (2.4%) | 18 (11.2%) | Tài khoản máy tính là thành viên nhóm |
| Thành viên là Well-known SID (Base) | 2 (4.8%) | 7 (4.4%) | SID hệ thống như IUSR, Authenticated Users |
| **Số chu trình nhóm (Group Cycles)** | **0** | **0** | Không phát hiện chu trình khép kín trong dữ liệu thực tế |
| **Độ sâu lồng nhau tối đa (Max Depth)** | **1 cấp** (`G1 -> G2`) | **3 đến 4 cấp** (`G1 -> G2 -> G3 -> G4`) | Dataset B có phân cấp phức tạp vượt trội |

### 2.1. Bo sung pham vi SEAMLESS

EDA SEAMLESS ghi nhan group nesting depth toi 5 va 119 chain dai hon mot cap.
Ket qua nay cung co ung ho quy tac luu direct-only de giu provenance cua quan he thuc, nhung khong thay the bang chung A/B trong bang tren.
BloodHound parity/reconciliation cho SEAMLESS chua duoc chung minh, nen khong duoc suy dien hanh vi import BloodHound cua A/B sang SEAMLESS.

### Phát hiện quan trọng về BloodHound CE Ingestion Baseline
1. Toàn bộ 42 cạnh `MemberOf` trong Dataset A và 161 cạnh `MemberOf` trong Dataset B trên BloodHound CE **tương ứng 1:1 với các phần tử trong mảng `Members[]` thô**.
2. BloodHound CE **tuyệt đối không sinh thêm bất kỳ cạnh bắc cầu (transitive edges) nào** vào cơ sở dữ liệu lúc nạp dữ liệu (ingestion time).
3. Tính bắc cầu chỉ được tính toán động khi người dùng thực hiện truy vấn đường đi Cypher (`-[:MemberOf*1..]->`).

---

## 3. Các mẫu hình Group Nesting thực tế điển hình

### 3.1. Mẫu hình 1: Chuỗi kế thừa quyền truy cập từ xa (Remote Access via Nested Group)
Tại Dataset A (`NORTH`):
- Nhóm `REMOTE DESKTOP USERS` (`S-1-5-32-555`) **không chứa bất kỳ User trực tiếp nào**.
- Nhóm này chỉ chứa duy nhất 1 Group thành viên là `STARK` (`S-1-5-21-1252223512-2665318757-2669098637-1106`).
- Nhóm `STARK` chứa 9 tài khoản người dùng thực tế:
  - `EDDARD.STARK` (`-1111`)
  - `CATELYN.STARK` (`-1112`)
  - `ROBB.STARK` (`-1113`)
  - `SANSA.STARK` (`-1114`)
  - `BRANDON.STARK` (`-1115`)
  - `RICKON.STARK` (`-1116`)
  - `HODOR` (`-1117`)
  - `JON.SNOW` (`-1118`)
  - `ARYA.STARK` (`-1110`)

*Hệ quả*: Nếu parser hoặc bộ suy luận chỉ kiểm tra thành viên trực tiếp của `REMOTE DESKTOP USERS`, toàn bộ 9 người dùng này sẽ bị đánh giá sai là không có quyền RDP. Việc duyệt group nesting là điều kiện tiên quyết để nhận diện đúng quyền `CanRDP` trên các máy trạm trong miền.

### 3.2. Mẫu hình 2: Đa đường kế thừa (Multiple Inheritance Paths / Diamond Pattern)
Tại miền `WRAITH.CORP` thuộc Dataset B:
- Nhóm `EXCHANGE-ADMINS` (`-1170`) vừa là thành viên trực tiếp của `EXCHANGE SERVERS` (`-1138`), vừa là thành viên gián tiếp qua nhóm trung gian `$141000-LDV9MS90TKNJ` (`-1153`).
- Nhóm `EXCHANGE SERVERS` tiếp tục là thành viên của `WINDOWS AUTHORIZATION ACCESS GROUP` (`S-1-5-32-560`).

*Hệ quả*:
- Đây là mẫu hình hình thoi (Diamond inheritance) trong đồ thị AD thực tế.
- Nếu thực hiện làm phẳng đồ thị (materialize transitive closure), hệ thống sẽ phải giải quyết bài toán cạnh trùng lặp và gây nhiễu danh sách audit provenance.
- Nếu duy trì đồ thị trực tiếp (direct-only), đồ thị giữ đúng số lượng cạnh thực tế và thuật toán Dijkstra sẽ tự động chọn nhánh có chi phí tối ưu.

### 3.3. Mẫu hình 3: Kế thừa đặc quyền quản trị cao nhất (Domain Admins -> Local Administrators)
Tại cả Dataset A và Dataset B:
- Nhóm `DOMAIN ADMINS` (`RID -512`) được lồng trực tiếp vào nhóm cục bộ `ADMINISTRATORS` (`S-1-5-32-544`).
- Trong Dataset B (`PHANTOM.CORP`), còn xuất hiện nhóm `SUBDAS` (`RID -2200`) được lồng vào `DOMAIN ADMINS`.

*Hệ quả*: Người dùng chỉ cần là thành viên của nhóm cấp 3 (`SUBDAS`) là tự động sở hữu quyền quản trị cục bộ trên toàn bộ máy trạm và máy chủ thông qua chuỗi 3 bước nhảy `MemberOf`.

### 3.4. Mẫu hình 4: Lồng nhóm xuyên miền (Cross-Domain Nesting / Foreign Security Principal)
Tại Dataset A (`NORTH`):
- Nhóm `ENTERPRISE DOMAIN CONTROLLERS` của domain cha `SEVENKINGDOMS.LOCAL` (`S-1-5-9`) được thêm vào nhóm `WINDOWS AUTHORIZATION ACCESS GROUP` của domain con `NORTH.SEVENKINGDOMS.LOCAL` (`S-1-5-32-560`).
- Nhóm `SCHEMA ADMINS` của domain cha (`-518`) được lồng vào `DENIED RODC PASSWORD REPLICATION GROUP` của domain con (`-572`).

*Hệ quả*: Group nesting vượt qua ranh giới miền là cơ chế thực tế dẫn tới sự leo thang đặc quyền xuyên rừng (cross-forest/cross-domain privilege escalation).

### 3.5. Mẫu hình 5: Máy tính làm thành viên nhóm (Computer as a Group Member)
Tại Dataset A:
- Máy tính điều khiển miền `WINTERFELL.NORTH.SEVENKINGDOMS.LOCAL` (`RID -1001`) là thành viên của `ENTERPRISE DOMAIN CONTROLLERS` (`SEVENKINGDOMS.LOCAL-S-1-5-9`).
- Nhóm này tiếp tục được lồng vào `WINDOWS AUTHORIZATION ACCESS GROUP`.

*Hệ quả*: Tài khoản máy tính (Machine Account / Computer Object) là một chủ thể an ninh hợp lệ trong chuỗi `MemberOf`.

---

## 4. Kết luận kiến trúc và khuyến nghị cho pipeline

1. **Khuyến nghị lưu trữ Direct-Only**:
   - `GraphBuilder` (M2-05) chỉ lưu trữ các cạnh `MemberOf` trực tiếp có mặt trong mảng `Members[]`.
   - Giữ nguyên tính nhất quán 1:1 với 42 cạnh của Dataset A và 161 cạnh của Dataset B trên baseline BloodHound CE.
   - Mỗi cạnh giữ provenance trực tiếp tới tệp JSON nguồn.
   - Quy tắc direct-only la quyet dinh structural/provenance, khong tu xac lap trong so production hay Attack Semantics.
2. **Khuyến nghị suy luận tính bắc cầu (Transitive Resolution)**:
   - Bộ suy luận quyền máy trạm (M2-06): Duyệt ngược cây phân cấp group nesting từ các nhóm cục bộ (`S-1-5-32-544`, `S-1-5-32-555`, `S-1-5-32-580`) để xác định danh sách User có đặc quyền thực tế trước khi sinh cạnh `AdminTo`, `CanRDP`, `CanPSRemote`.
   - Traversal/query layer giải quyết closure trên chuỗi direct `MemberOf` khi cần.
     Chính sách weighting, nếu có, thuộc profile/decision riêng và không được suy ra từ direct-only.
3. **Cơ chế phòng vệ chu trình (Cycle Guard)**:
   - Mặc dù dữ liệu thực tế có 0 chu trình, thuật toán duyệt bắt buộc phải lưu trữ tập hợp các nút đã qua (`visited set`) để ngắt đệ quy ngay lập tức nếu gặp chu trình bất thường trong môi trường production.
