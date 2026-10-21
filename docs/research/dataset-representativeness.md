# Báo cáo Phân tích Tính Đại diện của Dataset và Sai lệch do Collector

Tài liệu này đánh giá tính đại diện của các bộ dữ liệu Active Directory phục vụ bài toán phân tích đường đi tấn công có trọng số (weighted attack-path analysis).
Nghiên cứu tiến hành so sánh đối chiếu chuẩn hóa giữa ba tập dữ liệu: `SEAMLESS.INTERNAL` (Enterprise scale), `NORTH` (Game of Active Directory) và `ad_sampledata`.
Báo cáo giải quyết toàn diện yêu cầu tại [Issue #57](https://github.com/nairyuuu/ad-weighted-graph/issues/57) (M2-11) và phản hồi từ Mentor về việc lựa chọn nguồn dữ liệu có giá trị doanh nghiệp thực tế.
Theo [ADR-0007](../adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md), SEAMLESS la primary structural/topology dataset cho M2+.
NORTH va `ad_sampledata` la historical baseline cho regression, collector comparison, multi-domain/parser robustness va BloodHound reference.
Current SEAMLESS counts below distinguish 66.374 raw/reference-shaped observations in the data-quality audit from 66.371 entries materialized in the EDA graph; 3 raw RDU-only references do not become verified `CanRDP`.
EDA graph paths and metrics are descriptive, not canonical output of #44/#45 or proof of effective authorization, attack execution, or collection completeness.
Historical A/B collector counts remain reference observations and are not same-snapshot SEAMLESS evaluation.

---

## 1. Phương pháp So sánh Cấu trúc Chuẩn hóa

Thay vì chỉ so sánh kích thước file thô (dung lượng MB), nghiên cứu chuẩn hóa các đặc trưng đồ thị thành các chỉ số cấu trúc:
- Mật độ quan hệ trên nút (Edge-to-Node ratio).
- Phân bố bậc vào/ra (In/Out-degree distribution) nhằm kiểm chứng đặc tính phân bố đuôi nặng và độ tập trung đặc quyền (Privilege concentration & heavy-tailed distribution).
- Độ sâu lồng nhau của nhóm (Group nesting depth).
- Cấu trúc cây phân cấp đơn vị tổ chức (OU hierarchy depth).
- Tỷ lệ đối tượng đặc quyền (Privilege concentration) và cờ `adminCount`.
- Tương quan mật độ giữa quan hệ cấu hình (ACL density) và quan hệ vận hành động (Session density).

Toàn bộ chỉ số được tính toán tự động qua script [scripts/eda_dataset_analysis.py](../../scripts/eda_dataset_analysis.py) và lưu tại [reports/eda_summary.json](../../reports/eda_summary.json).

---

## 2. Bằng chứng định lượng: Bảng Đối chiếu Hồ sơ Cấu trúc Giữa các Bộ Dữ liệu

| Đặc trưng đồ thị chuẩn hóa | SEAMLESS.INTERNAL (Primary M2+) | NORTH (GOAD Lab - Historical baseline) | ad_sampledata (Historical baseline) |
| --- | --- | --- | --- |
| **Phiên bản Schema** | BloodHound v3 | BloodHound CE (v4) | BloodHound CE (v4) |
| **Tổng số Nodes** | 3.368 (Snapshot) / 3.370 (Graph) | 320 unique (347 raw records) | 1.469 unique (1.718 raw records) |
| - Users | 2.493 | 16 | 99 unique (100 raw records) |
| - Groups | 549 unique (550 raw, 1 duplicate) | 57 unique (84 raw, 27 duplicates) | 219 unique (285 raw, 66 duplicates) |
| - Computers | 100 | 2 | 34 |
| - OUs | 223 | 1 | 20 |
| - Containers & khác | 2 (GPO) + 1 (Domain) + 2 (External) | 244 (203 Containers + 37 AD CS + 3 GPO + 1 Domain) | 1.094 (939 Containers + 123 AD CS + 32 GPO) |
| **EDA graph entries (Multigraph; chưa canonical)** | 66.371 | 2.153 historical | 10.903 historical reconciled |
| - Simple graph entries (Chiếu đơn có hướng) | 53.751 | 862 | 5.720 |
| - MemberOf | 13.324 | 42 | 161 |
| - GenericAll | 37.208 | 383 | 3.315 |
| - WriteDacl / WriteOwner | 6.794 | 1.146 | 4.438 |
| - Host access EDA entries / historical raw host references | 7 (AdminTo 5; CanPSRemote 2; verified CanRDP unmeasurable) | 8 raw references | 14 raw references |
| - HasSession | 0 (unobserved in snapshot) | 9 | 60 |
| **Tỷ lệ Cạnh / Node (Ratio)** | **19.71** | **6.73** | **7.42** |
| **Mật độ EDA simple graph (Directed Simple Density)** | **0.004734** (53.751 / 11.353.530) | **0.008444** (862 / 102.080) | **0.002652** (5.720 / 2.156.492) |
| **Cường độ EDA multigraph (Multigraph Edge Intensity)** | **0.005853** (66.371 / 11.340.056) | **0.021091** (2.153 / 102.080) | **0.005056** (10.903 / 2.156.492) |
| **Tỷ lệ Chủ thể Đặc quyền (Privileged Principal Ratio)** | **0.41%** (13 / 3.142) | **20.00%** (15 / 75) | **23.58%** (83 / 352) |
| **Tỷ lệ EDA ACL entries (ACL Density)** | **71.07%** (47.173 / 66.371) | **92.94%** (2.001 / 2.153) | **94.79%** (10.335 / 10.903) |
| **Mật độ Phiên làm việc (Session Density)** | **0.0** (unobserved in snapshot) | **28.13%** (9 / 32) | **1.78%** (60 / 3.366) |
| **Độ sâu Group Nesting lớn nhất** | **5 cấp** (119 chuỗi lồng) | **1 cấp** (hoàn toàn phẳng) | **3 cấp** (phần lớn phẳng) |
| **Độ sâu Cây OU lớn nhất** | **3 cấp** (223 OUs, 5 root) | **1 cấp** (1 OU duy nhất) | **1 cấp** (OUs phẳng) |
| **Nhóm có adminCount=1** | 11 nhóm (8 high-value) | 9 nhóm | 43 nhóm |
| **Bậc ra cực đại (Max Out-degree)** | **12.383** (Builtin Admins) | 308 | 1.625 |
| **Phân vị Bậc ra (Median Out-degree)** | 4.0 | 2.0 | 2.0 |

The A/B host-access values in the comparison row are historical raw observations, not like-for-like canonical `CanRDP` counts.
SEAMLESS graph entries exclude the 3 raw RDU-only references, while the 66.374-reference data-quality audit retains them for raw-field inventory.

### 2.1. Phân tích bề mặt tấn công đồ thị (Graph Attack Surface EDA) trên SEAMLESS.INTERNAL

Phân tích này đo lường 7 khía cạnh của bề mặt tấn công đồ thị dựa trên kết quả kiểm thử tự động.
Mọi số liệu có thể truy vết tại sổ tay [notebooks/eda_dataset_analysis.ipynb](../../notebooks/eda_dataset_analysis.ipynb) và báo cáo [reports/eda_summary.json](../../reports/eda_summary.json).

#### 1. Tính kết nối của đồ thị (Connectivity)

- **Weakly Connected Components (WCC)**: Đồ thị gồm 1 thành phần liên thông yếu (3.370 nodes, chiếm 100.0%).
- **Strongly Connected Components (SCC)**: Đồ thị phân mảnh thành 2.197 thành phần liên thông mạnh.
- Khối SCC khổng lồ (Giant SCC) chứa 1.172 nodes (chiếm 34.78%) theo EDA graph connectivity; điều này không chứng minh movement hoặc effective authorization.
- **Hệ số kết cụm (Clustering Coefficient)**: Đạt `0.6231` trên hình chiếu vô hướng, phản ánh cấu trúc liên kết phân quyền mạng lưới cục bộ rất dày đặc.
- **Đường kính đồ thị (Diameter)**: Đạt `4` trên giant component của hình chiếu vô hướng.
  Lưu ý: đường kính trên đồ thị có hướng là vô cùng do sự hiện diện của các đỉnh đích (sink nodes) không có cạnh ra.
- **Phân loại vai trò Node**:
  - Isolated (Cô lập): 0.
  - Source (Nguồn): 2 (chiếm 0.06%).
  - Sink (Đích): 1.159 (chiếm 34.39%).
  - Transit (Trung chuyển): 2.209 (chiếm 65.55%).

#### 2. Khả năng tiếp cận Tier-0 (Reachability to Tier-0)

Đo raw graph reachability tới các nhóm gắn nhãn Tier-0 (`Domain Admins`, `Builtin Administrators`, `Enterprise Admins`) với mẫu số rõ ràng; không suy effective entitlement hoặc attack applicability:
- **Tỷ lệ trên security principals không thuộc mục tiêu (Non-target principals)**: **1.170 / 3.141 = 37.25%** (mẫu số: 3.144 principals trừ 3 nhóm đích).
- **Tỷ lệ trên các đỉnh đồ thị không thuộc mục tiêu (Non-target graph nodes)**: **1.170 / 3.367 = 34.75%** (mẫu số: 3.370 materialized nodes trừ 3 nhóm đích).
- **Tỷ lệ trên toàn bộ đỉnh đồ thị (All materialized graph nodes)**: **1.170 / 3.370 = 34.72%** (mẫu số: toàn bộ 3.370 materialized nodes bao gồm cả OUs, GPOs, Domain và các nút biên).
- **Phân tách theo loại đối tượng (By Class)**:
  - Users: 1.085 / 2.493 (43.52%), số mục tiêu Tier-0 tiếp cận trung bình là 1.31.
  - Groups: 70 / 551 (12.70%), số mục tiêu Tier-0 tiếp cận trung bình là 0.39.
  - Computers: 15 / 100 (15.00%), số mục tiêu Tier-0 tiếp cận trung bình là 0.45.
- **Phân bố độ dài đường đi ngắn nhất (Shortest-hop histogram)**:
  - 1 hop: 7.
  - 2 hops: 15.
  - 3 hops: 219.
  - 4 hops: 367.
  - 5 hops: 318.
  - 6 hops: 178.
  - 7 hops: 28.
  - 8 hops: 4.
  - 9 hops: 11.
  - 10 hops: 13.
  - 11 hops: 10.
- **Chỉ số thống kê (Metrics)**: min=1, max=11, median=4.0, mean=4.60, p25=4.0, p75=5.0, p90=6.0, p95=7.0.

#### 3. Phân bố đặc quyền và Hệ số Gini (Privilege Concentration & Gini)

- **Hệ số Gini**: Out-degree = 0.8944, In-degree = 0.2117, Total-degree = 0.5159.
- Top 1% nodes (33 nodes) chiếm 75.76% raw outgoing EDA entries (50.285 entries), không đo khả năng khai thác.
- Top 5% nodes (168 nodes) chiếm 81.43% raw outgoing EDA entries (54.045 entries), không đo khả năng khai thác.
- **Danh sách các Hubs có bậc ra cao nhất (Top out-degree hubs)**:
  - Administrators: 12.383 cạnh.
  - Domain Admins: 6.753 cạnh.
- **Đặc trưng phân bố bậc**: Được đặc tả là `heavy-tailed / highly concentrated synthetic enterprise-scale benchmark`.
  Phân bố thể hiện độ lệch đuôi nặng và mức độ tập trung quyền lực hành chính cực đoan mà không khẳng định một quy luật hàm mũ (scale-free power-law) đã được chứng minh toán học.

#### 4. Ma trận hỗn hợp quan hệ (Relationship Mixing Matrix)

- Đồ thị chứa 44 bộ ba (triplets) quan hệ phân quyền duy nhất.
- **Top các quan hệ phổ biến**:
  - Group -> GenericAll -> User: chiếm 33.32%.
  - User -> MemberOf -> Group: chiếm 19.56%.
  - User -> GenericAll -> User: chiếm 7.02%.
  - Group -> GenericAll -> Group: chiếm 5.46%.
  - Computer -> GenericAll -> User: chiếm 4.53%.

#### 5. Bệnh lý lồng nhau của nhóm (Group Nesting Pathology)

- **Đồ thị có hướng không chu trình (DAG)**: Đã xác minh là True (0 chu trình).
- Thống kê hệ số phân nhánh (Branching factor) cho thấy có 119 nhóm lồng nhau.
- Phân bố phân nhánh từ độ sâu 1 đến 5 cho thấy raw group references nhiều tầng; group type và hiệu lực token phải được đánh giá riêng.

#### 6. Độ dư thừa đường đi và Điểm chốt chặn (Path Redundancy & Choke Points)

- Kịch bản **ARMAND_ROSE**: Đường đi ngắn nhất 11 hops, 1 đường dẫn không chung node/edge, tìm kiếm đường dẫn thay thế với cutoff 12 hops bị giới hạn chặn ở ngưỡng 20 đường dẫn (`capped_at: 20`, `truncated: True`).
- Kịch bản **OLA_CARSON**: Đường đi ngắn nhất 2 hops, 5 đường dẫn không chung node, 6 đường dẫn không chung edge, 7 đường dẫn thay thế (`capped_at: 20`, `truncated: False`).
- Kịch bản **ANNABELLE_MEDINA**: Đường đi ngắn nhất 4 hops, 1 đường dẫn không chung node/edge, bị giới hạn chặn ở 20 đường dẫn (`capped_at: 20`, `truncated: True`).
- Path diversity mô tả các đường đi trong EDA graph; tính khả thi của attack path hoặc choke point phòng thủ chưa được xác nhận từ metric này.

#### 7. Dị biệt cấu trúc (Structural Outliers)

- **Out-degree**: Có 34 nodes vượt ngưỡng p99 (100.62).
- **In-degree**: Có 34 nodes vượt ngưỡng p99 (48.31).
- Đây là các dị biệt cấu trúc đồ thị (structural topological anomalies) do vai trò quản trị tập trung, không mặc định coi là hành vi độc hại (malicious).

---

## 3. Phân tích Chi tiết Tính Đại diện Doanh nghiệp

### 3.1. Quy mô và Mật độ Kết nối (Scale & Density)

Bộ dữ liệu `NORTH` (từ môi trường Game of Active Directory) chỉ có 16 tài khoản người dùng và 2 máy tính.
Quy mô này mang tính chất thao trường tối thiểu (micro-lab) nhằm trình diễn một vài kỹ thuật cụ thể (AD CS ESC1, AS-REP roasting), không phản ánh được không gian tìm kiếm đường đi trong môi trường thực tế.

Ngược lại, `SEAMLESS.INTERNAL` có 2.493 user records, 550 group records và 66.371 EDA graph entries, đạt tỷ lệ 19.71 entries trên 3.368 unique snapshot IDs.
Đây là quy mô của benchmark synthetic; metric không chứng minh mọi entry là canonical authorization hoặc yêu cầu một production weighting profile.

### 3.2. Cấu trúc Lồng nhau của Nhóm (Group Nesting Topology)

Trong mô hình kiến trúc ủy quyền doanh nghiệp chuẩn của Microsoft (AGDLP: Accounts -> Global Groups -> Domain Local Groups -> Permissions), các nhóm bảo mật luôn được lồng ghép nhiều tầng.

- Trong `NORTH`, độ sâu lồng nhau của nhóm là 1 (hoàn toàn phẳng).
- Trong `SEAMLESS.INTERNAL`, độ sâu lồng nhau đạt tới 5 cấp độ với 119 chuỗi nhóm phụ thuộc:
  - Cấp 1: 75 chuỗi.
  - Cấp 2: 24 chuỗi.
  - Cấp 3: 12 chuỗi.
  - Cấp 4: 6 chuỗi.
  - Cấp 5: 2 chuỗi.
Sự hiện diện của các chuỗi lồng 5 cấp cho phép kiểm thử tính đúng đắn của logic suy luận quyền thừa kế gián tiếp qua nhóm (transitive group closure).

### 3.3. Phân cấp Đơn vị Tổ chức (OU Tree & Tiering Boundaries)

Một lỗ hổng nghiêm trọng của cả hai bộ dữ liệu cũ (`NORTH` và `ad_sampledata`) là chỉ có 1 OU duy nhất hoặc các OU phẳng không có cấu trúc phân tầng.

`SEAMLESS.INTERNAL` mô hình hóa trọn vẹn 223 Đơn vị Tổ chức (OUs) theo kiến trúc phân tầng quản trị Tiered Administration Model (Tier 0, Tier 1, Tier 2):
- Tầng 1 (Root OUs): 5 OU gốc định hình ranh giới quản trị (ví dụ: `Domain Controllers`, `Tier 0 Administration`, `Workstations`, `Servers`, `Users`).
- Tầng 2 và 3: 218 OU con phân tách theo phòng ban, chi nhánh địa lý và vai trò vận hành.
Cấu trúc OU tạo bề mặt để khảo sát raw tier-crossing paths; tên OU không tự chứng minh một security boundary hay effective policy.

### 3.4. Đặc tính Phân bố Đuôi Nặng và Tập trung Đặc quyền (Heavy-Tailed Concentration)

Phân tích bậc của đồ thị `SEAMLESS.INTERNAL` cho thấy:
- Bậc vào trung bình là 19.69, trung vị là 17.0, cực đại là 63.
- Bậc ra trung bình là 19.69, trung vị là 4.0, nhưng cực đại lên tới 12.383.

Hiện tượng phân vị trung vị rất nhỏ (4.0) trong khi cực đại cực lớn (12.383 và 6.753) thể hiện rõ nét đặc tính phân bố đuôi nặng (heavy-tailed distribution) và độ tập trung quyền lực hành chính cao của một benchmark doanh nghiệp nhân tạo quy mô lớn.
Đồ thị phản ánh sự phân bố lệch mạnh và tập trung vào các hub quản trị mà không khẳng định một quy luật hàm mũ phi tỷ lệ (scale-free power-law) đã được chứng minh giải tích toán học.
Các nút có bậc ra khổng lồ chính là các Hubs đặc quyền trung tâm:
1. `SEAMLESS.INTERNAL-S-1-5-32-544` (Builtin Administrators): 12.383 cạnh ra.
2. `S-1-5-21-...-512` (Domain Admins): 6.753 cạnh ra.
3. `S-1-5-21-...-519` (Enterprise Admins): 3.397 cạnh ra.
4. `SEAMLESS.INTERNAL-S-1-5-32-548` (Account Operators): 3.125 cạnh ra.

Đặc tính này chứng minh tính chân thực của đồ thị: phần lớn các nút bình thường chỉ có một vài liên kết, trong khi quyền kiểm soát toàn miền tập trung vào một số lượng rất nhỏ các trung tâm đặc quyền.

### 3.5. Minh chứng Thực tế: Chuỗi Phân quyền / Kiểm soát Hành chính Mẫu 11 Bước Nhảy (Control Reachability Path)

Để chứng minh tính khả thi của thuật toán tìm đường trên quy mô lớn, kịch bản EDA đã tìm kiếm và truy vết thành công các chuỗi phân quyền kiểm soát hành chính (control reachability paths) từ người dùng thông thường không có đặc quyền tới Domain Admins.
Cần lưu ý: đây là chuỗi phân quyền / kiểm soát dựa trên quyền cấu hình và thành viên nhóm, KHÔNG phải là một chuỗi tấn công thực tế đã được khai thác hoặc xác thực qua telemetry.

Kết quả ghi nhận 1.085 người dùng thông thường sở hữu đường đi tới Domain Admins với độ dài từ 3 bước nhảy trở lên.
Dưới đây là một chuỗi kiểm soát hành chính mẫu dài 11 bước nhảy (11 hops) được trích xuất hoàn toàn tự động:

1. `ARMAND_ROSE` (Tài khoản người dùng thông thường)
2. `-[MemberOf]->` `EA-NELIAZUL1-DISTLIST1` (Nhóm người dùng cấp 1)
3. `-[MemberOf]->` `MA-BIDEZARRA-DISTLIST1` (Nhóm lồng nhau cấp 2)
4. `-[GenericAll]->` `CR-SESTOSANT-DISTLIST1` (Lạm dụng toàn quyền kiểm soát nhóm)
5. `-[GenericAll]->` `GOOWCTRX1000000` (Quyền kiểm soát máy tính trạm)
6. `-[MemberOf]->` `LE-AZK-DISTLIST1` (Nhóm dịch vụ liên kết)
7. `-[MemberOf]->` `JO-SAM-DISTLIST1` (Nhóm lồng nhau cấp 3)
8. `-[MemberOf]->` `TA-154-DISTLIST1` (Nhóm lồng nhau cấp 4)
9. `-[GenericAll]->` `ITSWLPT1000001` (Quyền kiểm soát máy tính quản trị IT)
10. `-[GenericAll]->` `DA-130-DISTLIST1` (Nhóm phân phối đặc quyền)
11. `-[GenericAll]->` `LIDIA_ALFORD` (Tài khoản người dùng nắm giữ quyền quản trị)
12. `-[MemberOf]->` `DOMAIN ADMINS` (Kiểm soát toàn miền)

Trong bộ dữ liệu cũ `NORTH`, các đường đi chỉ có 1 đến 2 bước nhảy tầm thường, không thể hiện được bài toán tối ưu hóa đa mục tiêu của thuật toán Dijkstra.
Chuỗi 11 bước nhảy kết hợp đan xen giữa thừa kế nhóm (`MemberOf`) và quyền quản trị (`GenericAll`) trên `SEAMLESS.INTERNAL` cung cấp một không gian thực nghiệm hoàn hảo cho việc đối chiếu giữa đường đi ngắn nhất về số bước (Hop count) và đường đi có chi phí tối ưu (Weighted path).

---

## 4. Phân tích Sai lệch do Bộ Thu thập (Collector Bias)

### 4.1. Khác biệt Định lượng giữa SharpHound và BloodHound.py (Dataset A: NORTH)

Để lượng hóa sai lệch do công cụ thu thập theo yêu cầu của [Issue #57](https://github.com/nairyuuu/ad-weighted-graph/issues/57), nghiên cứu đã đối sánh trực tiếp toàn bộ 2.137 cạnh thu thập bởi SharpHound C# với 742 cạnh thu thập bởi BloodHound-Python trên cùng môi trường `NORTH.SEVENKINGDOMS.LOCAL`:
- **Tổng số cạnh SharpHound C#**: 2.137 cạnh.
- **Tổng số cạnh BloodHound-Python**: 742 cạnh.
- **Số cạnh giao nhau (Intersection)**: 733 cạnh.
- **Số cạnh hợp (Union)**: 2.146 cạnh.
- **Hệ số tương đồng Jaccard tổng thể (Overall Jaccard Similarity)**: **0.3416**.

Bảng đối sánh chi tiết theo từng loại cạnh:

| Loại Cạnh (Edge Kind) | SharpHound C# | BloodHound.py | Giao nhau (Common) | Jaccard Similarity | Ghi chú Phân tích Kỹ thuật |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `MemberOf` | 42 | 42 | 41 | 0.9535 | LDAP group membership; đồng nhất cao giữa hai công cụ |
| `GenericAll` | 378 | 177 | 176 | 0.4644 | Phân rã DACL; SharpHound phân giải sâu các đối tượng hệ thống |
| `GenericWrite` | 103 | 103 | 103 | 1.0000 | Đồng nhất tuyệt đối 100% giữa hai công cụ |
| `AllExtendedRights` | 30 | 30 | 30 | 1.0000 | Đồng nhất tuyệt đối 100% |
| `AddKeyCredentialLink` | 24 | 24 | 24 | 1.0000 | Đồng nhất tuyệt đối 100% |
| `WriteDacl` | 570 | 136 | 134 | 0.2343 | SharpHound quét sâu hơn vào quyền sửa DACL trên container |
| `WriteOwner` | 570 | 136 | 134 | 0.2343 | Tương tự WriteDacl |
| `Owns` | 308 | 87 | 86 | 0.2783 | Quan hệ sở hữu đối tượng |
| `Enroll` / `ManageCA` / `ManageCertificates` | 93 | 0 | 0 | 0.0000 | Thuộc tính AD CS; BloodHound.py hoàn toàn không thu thập |
| `AdminTo` | 7 | 0 | 0 | 0.0000 | Thu thập qua LocalGroups (-544); BloodHound.py không thu thập |
| Raw RDU membership (not verified `CanRDP`) | 1 | 0 | 0 | 0.0000 | LocalGroups (-555) là primitive; A/B effective assessment phụ thuộc UserRights allow/deny và completeness |
| `HasSession` | 4 | 0 | 0 | 0.0000 | Thu thập qua NetSessionEnum; BloodHound.py không thu thập |
| `GetChanges` / `All` / `FilteredSet` | 7 | 7 | 5 | 0.5556 | Quyền sao chép danh mục thư mục (DCSync) |

**Nguyên nhân kỹ thuật của khoảng cách thu thập (Collection gap)**:
Trong phạm vi snapshot A/B lịch sử, SharpHound C# xuất thêm host-bound local-group, session và AD CS raw observations so với BloodHound.py.
Chênh lệch collector không tự chứng minh effective `CanRDP`, absence ở collector khác hoặc attack path bị bỏ sót.

### 4.2. Khác biệt Giữa Phiên bản Schema v3 và v4

- **Cấu trúc dữ liệu**: Schema v3 phân tách rõ ràng các tệp theo danh mục (`users`, `groups`, `computers`) và sử dụng khóa `MemberId` cho thành viên nhóm; Schema v4 gộp chung cấu trúc `data` và dùng `ObjectIdentifier`.
- **Độ ổn định của quan hệ ACL**: Quan hệ ACL hoàn toàn tương đồng về mặt ngữ nghĩa giữa hai phiên bản, đều trích xuất trung thực từ DACL của Active Directory.
- **Quan hệ phiên làm việc (`HasSession`)**: Positive session observations phụ thuộc phương thức và thời điểm collector; raw absence không chứng minh không có session hoặc một cổng cụ thể đóng.

---

## 5. Kết luận về Tính Đại diện và Khuyến nghị

### 5.1. Đặc điểm Ổn định (Invariants)
- Quyền hạn kiểm soát tối cao luôn hội tụ về nhóm Administrators (`-544`) và Domain Admins (`-512`).
- Phân bố quyền ACL mang đặc tính bất đối xứng mạnh mẽ (Heavy-tailed Hubs).

### 5.2. Hạn chế Cần Khắc phục (Dataset-Specific Biases)
- Snapshot `SEAMLESS.INTERNAL` la topology synthetic va khong co collector provenance chung minh endpoint availability. `HasSession` va `LocalAdmins` endpoint phai duoc coi la khong quan sat duoc/not measurable trong snapshot nay, khong suy dien thanh trang thai am.
- Nếu chỉ dùng đồ thị tĩnh, bài toán sẽ thiên lệch hoàn toàn sang phân tích cấu hình sai (Misconfiguration / ACL-only attack paths) đúng như Mentor đã cảnh báo.

### 5.3. Khuyến nghị Giải pháp
- **Khóa lựa chọn dataset**: Sử dụng `SEAMLESS.INTERNAL` làm bộ dữ liệu cấu trúc đồ thị chuẩn cho toàn bộ Milestone 2 và các mốc tiếp theo.
- **Bổ sung tầng Telemetry**: Dùng bộ nhật ký sự kiện Windows (`EVTX-ATTACK-SAMPLES`) tai Attack Semantics de nghien cuu expected telemetry va observability o cap lop. Khong entity-level join voi SEAMLESS, khong bu dap session cua SEAMLESS va khong xac nhan observed activity tren topology nay.

---

## 6. Tiêu chí Nghiệm thu và Tái lập (Reproducibility)

Báo cáo này thỏa mãn toàn bộ tiêu chí tại [Issue #57](https://github.com/nairyuuu/ad-weighted-graph/issues/57):
- So sánh các bộ dữ liệu dựa trên các metric đồ thị đã chuẩn hóa.
- Lệnh thực thi tái lập số liệu:
  ```bash
  uv run python scripts/eda_dataset_analysis.py
  ```
- Kết quả lưu trữ tại [reports/eda_summary.json](../../reports/eda_summary.json).
