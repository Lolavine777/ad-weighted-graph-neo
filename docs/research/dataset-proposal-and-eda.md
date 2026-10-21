# Báo cáo Đề xuất Nguồn Dữ liệu và Phân tích Khám phá Dữ liệu Toàn diện (EDA)

Tài liệu này tổng hợp toàn bộ kết quả phân tích khám phá dữ liệu (Exploratory Data Analysis - EDA) trên hai nguồn dữ liệu thực nghiệm mới: đồ thị Active Directory quy mô doanh nghiệp `SEAMLESS.INTERNAL` và kho mẫu nhật ký an ninh `EVTX-ATTACK-SAMPLES`.
Báo cáo đóng vai trò là bản đề xuất hoàn chỉnh gửi Mentor để chính thức khóa lựa chọn dataset cho Milestone 2, giải quyết triệt để các nhận xét trước đó về quy mô dữ liệu và bài toán "dò cấu hình sai tĩnh" (misconfiguration trap).

## Current evidence boundary after #79 B1 and #80

Đây là đề xuất dataset/EDA lịch sử, được đọc cùng [Phase A matrix](m1-evidence-audit.md), [#94 raw-field audit](claim-to-field-traceability.md) và [#80 host-access semantics](host-access-semantics-audit.md).
Các số liệu topology dưới đây là raw/extracted EDA observations trong snapshot SEAMLESS, chưa phải canonical graph output của #44/#45 hoặc same-snapshot BloodHound parity của #82.
Đặc biệt, raw `RemoteDesktopUsers[]` không chứng minh composite CanRDP, Event 4624 riêng lẻ không chứng minh RDP, Sysmon 10 riêng lẻ không chứng minh truy cập LSASS, và upstream tactic labels không phải Windows-native ground truth.
PR #101 đã hoàn tất #80 EDA host-access remediation; PR #102 đã bỏ relationship-to-EventID matrix khỏi report.
Independent telemetry không bổ sung SEAMLESS structural edges, không chứng minh exploit đã xảy ra trên topology đó và không calibration production weights.

---

## 1. Tóm tắt Đề xuất Điều chỉnh Dữ liệu (Executive Summary)

### 1.1. Tiếp thu Ý kiến Chỉ đạo của Mentor
Trong buổi đánh giá trước, Mentor đã chỉ rõ 3 giới hạn nghiêm trọng của hướng đi cũ:
1. **Dữ liệu quá nhỏ và phi thực tế**: Bộ dữ liệu `NORTH` (Game of Active Directory) chỉ có 16 tài khoản và 2 máy tính, chỉ mang tính chất phòng thí nghiệm tối thiểu, không phản ánh được quy mô và độ phức tạp của doanh nghiệp thật.
2. **Thiếu phân tích dữ liệu thực nghiệm (EDA)**: Chưa có số liệu định lượng về phân bố bậc, cấu trúc nhóm, phân cấp quản trị và kiểm toán dữ liệu thiếu.
3. **Nguy cơ rơi vào bẫy "dò cấu hình sai" (Misconfiguration Trap)**: Nếu chỉ truy vết đường đi trên đồ thị tĩnh của BloodHound, bài toán thực chất chỉ là kiểm toán quyền sai tĩnh rồi sửa lại, không phản ánh được quyết định tấn công thực tế và giá trị nghiên cứu khoa học.

### 1.2. Giải pháp Kiến trúc Đề xuất: Mô hình Lai (Hybrid Architecture)
Nhóm đề xuất chính thức chuyển đổi sang giải pháp tích hợp hai trụ cột:
- **Trụ cột Cấu trúc Đồ thị (Topology)**: Sử dụng bộ dữ liệu `SEAMLESS.INTERNAL` (2.493 users, 549 unique groups, 100 computers, 223 OUs, 2 GPOs, 1 Domain; tổng số 3.368 unique snapshot ObjectIdentifiers từ 3.369 raw records, và 3.370 materialized graph nodes).
- **Trụ cột Động lực học & Dấu vết (Telemetry)**: Sử dụng corpus độc lập `EVTX-ATTACK-SAMPLES` với 4.633 rows và 8 nhãn `EVTX_Tactic` upstream; con số 6.432 events/11 tactics là tuyên bố ngoài snapshot chưa được kiểm chứng tại đây.
- **Cầu nối Lớp Ngữ nghĩa Kỹ thuật (Attack Semantics Layer)**: Liên kết hai nguồn dữ liệu độc lập ở cấp độ lớp kỹ thuật (Technique Class Level) cho expected telemetry va observability.
  Lớp này không giải quyết `HasSession` của SEAMLESS, không entity-level join, và không tự hiệu chuẩn trọng số production.

---

## 2. Bảng Đối chiếu Chỉ số EDA: Trước và Sau Điều chỉnh

| Chỉ số Phân tích (Metric) | SEAMLESS.INTERNAL (Primary M2+) | NORTH (GOAD Lab - Historical baseline) | ad_sampledata (Historical baseline) | Đánh giá Ý nghĩa Kỹ thuật |
| --- | --- | --- | --- | --- |
| **Quy mô Thực thể (Nodes)** | **3.368 unique snapshot nodes (3.370 materialized)** | 320 unique (347 raw records) | 1.469 unique (1.718 raw records) | Đạt quy mô doanh nghiệp thực tế |
| - Users | 2.493 | 16 | 99 unique (100 raw records) | Tăng không gian tìm kiếm đường đi gấp 155 lần |
| - Groups | 549 unique (550 raw, 1 duplicate) | 57 unique (84 raw, 27 duplicates) | 219 unique (285 raw, 66 duplicates) | Hệ thống nhóm phân quyền đa dạng |
| - Computers | 100 | 2 | 34 | Mô phỏng hạ tầng mạng có máy trạm và máy chủ |
| - OUs | 223 | 1 | 20 | Đầy đủ ranh giới phân tầng quản trị |
| **Tổng EDA graph entries materialized** | **66.371 entries, chưa canonical** | 2.153 historical entries | 10.903 historical reconciled entries | Data-quality audit đếm 66.374 raw/reference-shaped observations; 3 raw RDU-only references không thành verified `CanRDP`; unresolved identity vẫn cần #44 |
| - `MemberOf` raw refs | 13.324 | 42 | 161 | 2 raw member references chưa exact-match theo #94; không đếm là canonical direct edges |
| - `GenericAll` | 37.208 | 383 | 3.315 | Quyền kiểm soát toàn diện đối tượng |
| - `WriteDacl` / `WriteOwner` | 6.794 | 1.146 | 4.438 | Quyền can thiệp cấu trúc phân quyền |
| - `AdminTo` / raw RDU memberships | 5 / 3 | historical baseline | 14 | Host-bound evidence; SEAMLESS verified `CanRDP` is unmeasurable |
| **Mật độ Cạnh / Node** | **19.71** | 6.73 | 7.42 | Không gian đồ thị dày đặc (Dense multigraph) |
| **Độ sâu Group Nesting lớn nhất** | **5 cấp độ** (119 chuỗi lồng) | 1 cấp độ (phẳng lì) | 3 cấp độ (phần lớn phẳng) | Chuẩn mô hình ủy quyền AGDLP của Microsoft |
| **Độ sâu Cây OU lớn nhất** | **3 tầng** (223 OUs, 5 root) | 1 tầng (1 OU duy nhất) | 1 tầng (OUs ngang hàng) | Phân định ranh giới Tier 0, Tier 1, Tier 2 |
| **Đặc tính Mạng (Heavy-Tailed)** | Bậc ra cực đại **12.383**, trung vị 4.0 | Cực đại 308 | Cực đại 1.625 | Phân bố đuôi nặng tập trung cao vào các administrative hubs |
| **Tính Toàn vẹn Tham chiếu** | EDA subset 66.374/66.374 resolved hoặc boundary; #94 broader audit còn 2/71.786 unresolved | Historical A/B scope | Historical A/B scope | Không tạo traversable edge từ unresolved identity |

---

## 3. Phân tích Khám phá Dữ liệu AD: SEAMLESS.INTERNAL (Topology EDA)

### 3.1. Đặc tính Phân bố Đuôi Nặng và Tập trung Đặc quyền (Heavy-Tailed Concentration)
Phân tích bậc của EDA-extracted `SEAMLESS.INTERNAL` observations cho thấy skew và hub concentration trong snapshot; chưa chứng minh quy luật power-law hoặc production graph behavior:
- Trung vị bậc ra của toàn bộ mạng chỉ là 4.0, nghĩa là phần lớn người dùng và máy tính thông thường chỉ có một vài liên kết quyền hạn hạn chế.
- Tuy nhiên, quyền kiểm soát tập trung cực lớn vào các nút trung tâm (Hubs):
  1. `SEAMLESS.INTERNAL-S-1-5-32-544` (Builtin Administrators): 12.383 cạnh ra.
  2. `S-1-5-21-...-512` (Domain Admins): 6.753 cạnh ra.
  3. `S-1-5-21-...-519` (Enterprise Admins): 3.400 EDA graph entries đi ra.
  4. `SEAMLESS.INTERNAL-S-1-5-32-548` (Account Operators): 3.125 cạnh ra.
Đặc tính này gợi ý nơi cần khảo sát topology concentration; chưa chứng minh hiệu quả của một chiến lược phòng thủ hay attack likelihood.

### 3.2. Cấu trúc Lồng ghép Nhóm (Group Nesting Architecture)
Raw group references trong `SEAMLESS.INTERNAL` cho thấy cấu trúc lồng nhau nhiều tầng trong phạm vi EDA:
- Cấp 1 (Nhóm trực tiếp): 75 chuỗi.
- Cấp 2: 24 chuỗi.
- Cấp 3: 12 chuỗi.
- Cấp 4: 6 chuỗi.
- Cấp 5: 2 chuỗi.
Tổng cộng 119 chuỗi được EDA đếm; đây không phải bằng chứng thuật toán đã được kiểm nghiệm triệt để hay cost bắc cầu đã được chốt.

### 3.3. Phân cấp Cây Đơn vị Tổ chức (Tiered OU Tree)
Với 223 OUs được phân bổ qua 3 tầng:
- 5 OU gốc (`Domain Controllers`, `Tier 0 Administration`, `Workstations`, `Servers`, `Users`) là cấu trúc raw; tên OU không tự chứng minh privilege isolation.
- 218 OU con phân bổ chi tiết theo phòng ban chức năng và vị trí địa lý.
Tier-crossing penalty là giả thuyết nghiên cứu, chưa phải yêu cầu production weighting; #42 phải quyết định cost ownership và mô hình trước implementation.

### 3.4. Ví dụ EDA raw reachability path 11 bước nhảy
EDA ghi nhận hơn 1.044 user records có raw graph reachability theo relationship assumptions của báo cáo; identity resolution, security-enabled group status, runtime applicability và canonical graph còn phải được kiểm tra riêng.
Tên nhóm trong chuỗi không chứng minh group type hoặc token entitlement.
Đây là ví dụ connectivity của EDA graph, không phải attack path đã thực thi hoặc được xác nhận bằng telemetry.

```text
[ARMAND_ROSE] (User record)
   |
   |--[MemberOf]--> [EA-NELIAZUL1-DISTLIST1] (raw membership reference)
   |--[MemberOf]--> [MA-BIDEZARRA-DISTLIST1] (raw membership reference)
   |--[GenericAll]--> [CR-SESTOSANT-DISTLIST1] (raw ACE-derived graph entry)
   |--[GenericAll]--> [GOOWCTRX1000000] (raw ACE-derived graph entry)
   |--[MemberOf]--> [LE-AZK-DISTLIST1] (raw membership reference)
   |--[MemberOf]--> [JO-SAM-DISTLIST1] (raw membership reference)
   |--[MemberOf]--> [TA-154-DISTLIST1] (raw membership reference)
   |--[GenericAll]--> [ITSWLPT1000001] (raw ACE-derived graph entry)
   |--[GenericAll]--> [DA-130-DISTLIST1] (raw ACE-derived graph entry)
   |--[GenericAll]--> [LIDIA_ALFORD] (raw ACE-derived graph entry)
   |--[MemberOf]--> [DOMAIN ADMINS] (raw membership reference)
```

Chuỗi này minh họa độ sâu raw connectivity; muốn kết luận effective entitlement hoặc khả năng tấn công phải kiểm tra group type, quyền hiệu lực và semantic predicates theo catalog.

### 3.5. Bề mặt tấn công đồ thị (Graph Attack Surface 7 Chiều)

Để lượng hóa chi tiết mức độ phức tạp của đồ thị, hệ thống phân tích bổ sung 7 chiều đánh giá bề mặt tấn công đồ thị (Graph Attack Surface EDA).
Toàn bộ quy trình đánh giá này đã được tự động hóa và có thể tái lập thông qua sổ tay thực nghiệm [notebooks/eda_dataset_analysis.ipynb](../../notebooks/eda_dataset_analysis.ipynb).
7 chiều đánh giá này bao gồm:
- **Connectivity (Tính kết nối)**: Đánh giá thành phần liên thông yếu (WCC) và mạnh (SCC).
- **Reachability to Tier-0 (Khả năng tiếp cận Tier-0)**: Đo tỷ lệ đối tượng có structural path trong EDA graph, không phải tỷ lệ attack khả thi hoặc đã xảy ra.
- **Privilege Concentration & Gini (Phân bố đặc quyền)**: Xác định mức độ tập trung quyền lực vào các tài khoản quản trị.
- **Relationship Mixing Matrix (Ma trận quan hệ)**: Thống kê các bộ ba quan hệ cấu trúc phổ biến nhất.
- **Group Nesting Pathology (Bệnh lý lồng nhóm)**: Phân tích chiều sâu lồng nhau và cấu trúc đồ thị có hướng không chu trình.
- **Path Redundancy & Choke Points (Độ dư thừa đường đi)**: Đo lường sự đa dạng đường dẫn và xác định các điểm chốt chặn cổ chai.
- **Structural Outliers (Dị biệt cấu trúc)**: Phát hiện các nút có bậc vào/ra bất thường trong hệ thống.

---

## 4. Phân tích Khám phá Dữ liệu Nhật ký: EVTX-ATTACK-SAMPLES (Telemetry EDA)

### 4.1. Hồ sơ Dữ liệu Nhật ký An ninh
Kiểm toán trên tệp dữ liệu [data/samples/manifests/telemetry-raw-v1.json](../../data/samples/manifests/telemetry-raw-v1.json):
- Số dòng đo được trong `evtx_data.csv`: **4.633** với **8 nhãn `EVTX_Tactic` upstream**; nhãn không phải Windows-native ground truth hoặc xác nhận attack.
- Bối cảnh kho lưu trữ bên ngoài: Tài liệu upstream nêu 6.432 sự kiện trên 11 chiến thuật, nhưng đây là tuyên bố bên ngoài chưa được đo lường trong snapshot cục bộ.
- Độ phủ hạ tầng: **19 máy tính khác nhau** và **35 tài khoản người dùng**.
- Cửa sổ thời gian thực tế: Từ `2017-06-09 19:21:26` đến `2021-06-09 05:18:11`.
- Phân bố theo 8 nhãn `EVTX_Tactic` trong corpus:
  - Lateral Movement: 1.288 dòng (chiếm 27.8%)
  - Privilege Escalation: 1.088 dòng (chiếm 23.5%)
  - Execution: 533 dòng (chiếm 11.5%)
  - Command and Control: 432 dòng (chiếm 9.3%)
  - Defense Evasion: 431 dòng (chiếm 9.3%)
  - Persistence: 411 dòng (chiếm 8.9%)
  - Credential Access: 283 dòng (chiếm 6.1%)
  - Discovery: 167 dòng (chiếm 3.6%)

Các phân bố EventID chỉ là thống kê dòng của corpus telemetry độc lập, không phải số canonical edges hoặc attack transitions.
EDA không thực hiện provider/channel/event-qualifier correlation, nên ExpectedTelemetry trong catalog vẫn tách khỏi ObservedActivity.

### 4.2. Descriptive telemetry inventory và nguồn chuẩn tắc

Bảng edge-to-event cũ đã được thay bằng [descriptive inventory references](data-quality-report.md#72-descriptive-inventory-tham-chiếu-technique-thay-vì-edge-event-equivalence) và [accepted evidence matrix](m1-evidence-audit.md).
[Semantic catalog](../../configs/attack_semantics.yml) là authoritative runtime source duy nhất; không định nghĩa mapping thứ hai trong proposal.
Passive MemberOf không có group-modification telemetry; HasSession observation không đồng nghĩa LSASS dump.
Telemetry qualifiers và corpus provenance chưa đủ để kết luận technique occurrence chỉ từ Event ID; #79 dùng accepted #94 evidence, #80 đã hoàn tất host-access remediation, còn #81 sở hữu provenance contract.

The SEAMLESS-v3 versus historical A/B host-access field mapping is maintained in the
accepted [host-access semantics audit, section 5](host-access-semantics-audit.md#5-schema-mapping-seamless-versus-historical-ab).
That mapping explicitly distinguishes raw primitives (`RemoteDesktopUsers[]`, `LocalAdmins[]`,
`PSRemoteUsers[]`, `Sessions[]`) from effective canonical relationships; this report does not
duplicate it or treat the raw RDU count as verified `CanRDP`.

---

## 5. Hệ Thống Phân Loại Ngữ Nghĩa Dữ Liệu Thiếu (Missingness Taxonomy)

Để đảm bảo thuật toán không hiểu sai giữa việc "thuộc tính mang giá trị False" và "thuộc tính không quan sát được", nhóm xây dựng hệ thống phân loại 7 trạng thái:

```text
                                BẢN CHẤT DỮ LIỆU THIẾU
                                          |
            +-----------------------------+-----------------------------+
            |                                                           |
    Lý thuyết / Cấu hình                                       Vận hành / Thực nghiệm
            |                                                           |
    - structurally unavailable (Không có trong schema)        - zero/absent field (Activity chưa biết)
    - observed false (Giá trị false của collector)            - empty/unobserved (Completeness chưa biết)
    - externally evidenced cause (nếu có)                    - collector error/denied (nếu có evidence)
                         \-- unknown/unmeasured khi thiếu mandatory evidence
```

1. **`lastLogonTimestamp` (99.96% zero/absent)**: Đây là raw field observation; không chứng minh các accounts chưa từng đăng nhập.
2. **`operatingSystem` (99.0% unpopulated)**: BadBlood-generated endpoint là giả thuyết nguyên nhân, không chứng minh host vắng mặt hay collector complete.
3. **`haslaps` (100/100 collector-observed false)**: Không suy LAPS deployment history hoặc schema absence từ cờ false đơn lẻ.
4. **`Sessions[]` và `LocalAdmins[]`**: Raw endpoint arrays empty/unobserved không xác định collection completeness; positive resolved `LocalAdmins[]` vẫn có thể hỗ trợ canonical `AdminTo` theo #80.

---

## 6. Cơ Chế Vận Hành Lớp Ngữ Nghĩa (Attack Semantics Mechanism)

Chính vì hai nguồn dữ liệu độc lập, hệ thống **không join thô ở mức định danh danh tính (SID)**, mà liên kết ở **cấp độ lớp kỹ thuật (Technique Class Level)**:

```text
[Đồ thị SEAMLESS]                                              [Nhật ký EVTX]
Raw GenericAll ACE                                            Independent EventID rows
        \                                                              /
         \                                                            /
          v                                                          v
    +--------------------------------------------------------------------+
    |                 LỚP NGỮ NGHĨA (Attack Semantics)                   |
    | Catalog: capability -> transition -> ExpectedTelemetry             |
    +--------------------------------------------------------------------+
                                     |
                                     v
    +--------------------------------------------------------------------+
    |           EVALUATION / WEIGHTING RIENG (NEU DUOC PHE DUYET)        |
    |   Khong duoc calibration bang entity evidence tu telemetry doc lap |
    |          Khong thay doi structural graph hay xac nhan attack       |
    +--------------------------------------------------------------------+
                                     |
                                     v
    +--------------------------------------------------------------------+
    |             STRUCTURAL PATH BASELINE: unit weighting              |
    |          Production cost ownership còn chờ #42                    |
    +--------------------------------------------------------------------+
                                     |
                                     v
    [KẾT QUẢ: structural path evaluation va observability research tach biet]
```

Phương pháp này mang lại 3 giá trị vượt trội:
1. **Lam ro observability o cap lop**: Telemetry doc lap ho tro expected evidence va detection coverage cho technique/relation class.
  No khong chung minh activity tren SEAMLESS, khong entity-level join, va khong tu dong hieu chinh trong so production.
2. **Giữ baseline tính đúng**: `unit` cho phép kiểm tra structural path behavior; production weighting còn chờ successor decision của #42.
3. **Giá trị thực tiễn cho phòng thủ**: Cho phép diễn giải riêng structural choke points va expected detection coverage, khong quy ket path nao la hanh vi da duoc quan sat.

---

## 7. Khả năng Tái lập và Nghiệm thu (Reproducibility)

Toàn bộ dữ liệu và số liệu trong báo cáo này có thể được kiểm chứng độc lập chỉ bằng một câu lệnh:

```bash
# Tái lập toàn bộ các bảng thống kê và chuỗi tấn công mẫu
uv run python scripts/eda_dataset_analysis.py

# Xác thực tính toàn vẹn snapshot manifest
uv run python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
uv run python scripts/snapshot_manifest.py verify data/raw/telemetry data/samples/manifests/telemetry-raw-v1.json

# Chạy toàn bộ bộ kiểm thử tự động
uv run pytest
```

Kết quả chi tiết được tự động xuất ra tệp JSON chuẩn hóa tại [reports/eda_summary.json](../../reports/eda_summary.json).
