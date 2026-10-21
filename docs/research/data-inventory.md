# Data inventory - Enterprise topology va independent telemetry evaluation

Trạng thái: Active reference cho M2+; A/B duoc giu lam historical baseline.
Người lập: @Lolavine777 (Thực tập sinh A).
Người review: @nairyuuu (Thực tập sinh B).
Liên kết nhiệm vụ: Refs #20, Refs #1, Refs #2, Refs #3, Refs #4, Refs #5, Refs #6, Refs #7, Refs #8.
Quyết định kiến trúc liên quan: [ADR-0007](../adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md); [ADR-0006](../adr/ADR-0006-two-dataset-evaluation-framework.md) la lich su.
Mã nguồn kiểm chứng độc lập: `scripts/verify_data_inventory.py`.

---

## 1. Chien luoc du lieu hien hanh

Sau mentor review Week 1, SEAMLESS la primary raw structural/topology dataset cho M2+ va raw EDA. The snapshot lacks Domain objectGUID, but Contract 1.3 accepts its observed Domain SID as typed Domain scope. Complete fail-fast canonical construction and Contract validation pass; the structural node/edge projection was verified in project Neo4j. Assessments remain in canonical JSON and PR #148 awaits #138 acceptance; see the [scope identity evidence audit](seamless-scope-identity.md).
Phần A/B dưới đây giữ nguyên số đo lịch sử; các kết luận hiện hành phải đọc cùng [#79 evidence audit](m1-evidence-audit.md), [#94 raw-field audit](claim-to-field-traceability.md) và [#80 host-access audit](host-access-semantics-audit.md).
Các tổng EDA là raw/extracted observations, không phải canonical graph của #44/#45; field rỗng không chứng minh collection completeness hoặc canonical absence.
A/NORTH va B/`ad_sampledata` khong dat quy mo va tinh dai dien de lam primary evaluation datasets, nhung duoc giu lam historical baseline de regression, collector comparison, multi-domain/parser robustness va BloodHound reference.
Telemetry la nguon nghien cuu doc lap cho Attack Semantics va observability, khong phai nguon topology hay entity-level join voi SEAMLESS khi khac environment.
`Structural Relationship != Attack Technique != Observed Activity`.

Chi tiet cac nguon du lieu duoc giu lai de co provenance day du:
1. **Dataset A (Benchmark Lab - GOADv2 NORTH):** Môi trường phòng thí nghiệm Game of Active Directory v2 chuẩn hóa đơn miền (`NORTH.SEVENKINGDOMS.LOCAL`).
   Tập dữ liệu này cung cấp hai bản trích xuất song song từ SharpHound C# (12 tệp, 347 bản ghi thô, 320 ID duy nhất) và BloodHound-Python (7 tệp, 94 bản ghi thô, 94 ID duy nhất).
   Dataset A đóng vai trò là tập dữ liệu tham chiếu (benchmark / reference dataset) phục vụ so sánh sự sai khác giữa các công cụ thu thập và kiểm thử hồi quy dựa trên kịch bản lab biết trước.
2. **Dataset B (Enterprise Multi-Domain - `ad_sampledata`):** Tập dữ liệu môi trường phòng thí nghiệm mô phỏng doanh nghiệp đa miền quy mô lớn (enterprise-style multi-domain lab dataset), bao gồm 3 miền được xuất khẩu (`PHANTOM.CORP`, `GHOST.CORP`, `WRAITH.CORP`), tổng cộng 31 tệp JSON với 1.718 bản ghi thô, 1.469 ObjectIdentifier duy nhất, và 407 ID duy nhất thuộc 6 loại đối tượng M1.
   Tập dữ liệu này cung cấp cấu trúc quan hệ tin cậy liên miền (Trusts), máy chủ điều khiển miền chỉ đọc (RODC), hạ tầng chứng chỉ doanh nghiệp đa tầng (AD CS), và cấu trúc phân quyền cục bộ chuyên sâu (`LocalGroups`, `UserRights`).
   Dataset B đóng vai trò là bộ kiểm chuẩn quy mô, độ bền vững (robustness), và kiểm tra khả năng xử lý ranh giới miền.
3. **Dataset C (Synthetic Enterprise-scale Benchmark - `SEAMLESS.INTERNAL`):** Tập dữ liệu môi trường phòng thí nghiệm mô phỏng doanh nghiệp quy mô lớn được sinh bằng BadBlood trên Domain Controller thực tế (BloodHound v3 schema).
   Tập dữ liệu gồm 3.369 raw records (2.493 Users, 550 Groups, 100 Computers, 223 OUs, 2 GPOs, 1 Domain).
   Sau quá trình xử lý EDA, hệ thống ghi nhận 3.368 unique snapshot ObjectIdentifiers (Groups: 549 unique sau khi loại bỏ 1 duplicate group OID).
   Data-quality audit đếm 66.374 raw/reference-shaped observations; EDA graph materialize 66.371 entries vì 3 raw RDU references không được nâng thành verified `CanRDP`.
   Khi dựng đồ thị, 2 nút biên well-known ngoại vi (`INTERACTIVE` và `IUSR`) được hiện thực hóa khi có tham chiếu, nâng tổng số đỉnh đồ thị lên 3.370 materialized graph nodes (3.368 snapshot nodes + 2 external well-known nodes).
   Dataset C la primary raw structural/topology va EDA dataset cho M2+. The missing Domain objectGUID is an observed source fact; the Domain SID now supplies typed scope. Canonical fail-fast graph and structural Neo4j projection are verified locally; acceptance is pending PR #148 review. Raw EDA metrics are not canonical graph results. See [scope identity evidence audit](seamless-scope-identity.md).
   BloodHound parity/reconciliation cho SEAMLESS chua duoc thuc hien va khong duoc suy dien tu baseline A/B.
4. **Telemetry Dataset (Descriptive Corpus Inventory - `evtx_data.csv`):** Tập dữ liệu nhật ký sự kiện bảo mật Windows Security Event Logs và Sysmon gồm 4.633 rows và 8 nhãn `EVTX_Tactic` upstream (con số 6.432 rows và 11 nhãn là tuyên bố bên ngoài từ kho lưu trữ nguồn), bao phủ 19 máy tính và 35 tài khoản người dùng.
   Tập dữ liệu này đóng vai trò là danh mục bằng chứng kiểm toán mô tả (descriptive candidate audit evidence) độc lập cho 8 loại cạnh Milestone 1, tuân thủ nghiêm ngặt ranh giới Attack Semantics cua #58/#63.

## 1.1. Pham vi lich su cua Dataset A va B

Muc 2 va Muc 3 luu evidence Week 1 va cac baseline A/B da kiem chung.
Chung khong dinh nghia quy mo hay tinh dai dien cua primary evaluation tu M2+.

---

## 2. Ho So Chi Tiet Dataset A: GOADv2 NORTH (Doi Sanh Collector)

### 2.1. Thong tin luu tru va ma bam
- Miền mục tiêu: `NORTH.SEVENKINGDOMS.LOCAL`.
- **Bản trích xuất 1 (SharpHound C# 2.3.3):**
  - Tệp lưu trữ: `NORTH_20240410083414_BloodHound-2.3.3.zip`.
  - Thời điểm snapshot: `2024-04-10T08:34:14Z`.
  - Dung lượng file nén: 31.438 bytes.
  - Mã băm SHA-256: `9f4482553b3d6b20df16e2fd615d543ac267f0e9a062ec4578d517548b4c666c`.
  - Cấu hình: Schema v6, cờ phương thức `meta.methods = 521215`.
  - Số lượng tệp: 12 tệp JSON (7 tệp AD cốt lõi và 5 tệp AD CS).
- **Bản trích xuất 2 (BloodHound-Python CE):**
  - Tệp lưu trữ: `ce_branch_bloodhoundpy_north_20240411011008_bloodhound.zip`.
  - Thời điểm snapshot: `2024-04-11T01:10:08Z`.
  - Dung lượng file nén: 177.910 bytes.
  - Mã băm SHA-256: `806fa21cc61b73c74a52126b0441ae633f6c6b6784731f5f16060b10c08e0e39`.
  - Cấu hình: Schema v6, cờ phương thức `meta.methods = 0` (truy vấn LDAP tiêu chuẩn).
  - Số lượng tệp: 7 tệp JSON.

### 2.2. Bang doi sanh so luong ban ghi Dataset A
| Loại dữ liệu | Số bản ghi SharpHound (1) | Số bản ghi BloodHound.py (2) | Độ lệch (2 - 1) | Nguyên nhân kỹ thuật |
| :--- | :---: | :---: | :---: | :--- |
| **Domains** | 1 | 1 | 0 | Đồng nhất miền `NORTH.SEVENKINGDOMS.LOCAL`. |
| **Users** | 16 | 17 | +1 | BloodHound.py trích xuất thêm SID dịch vụ hệ thống `NETWORK SERVICE` (`S-1-5-20`). |
| **Computers** | 2 | 2 | 0 | `WINTERFELL` (DC) và `CASTELBLACK` (Member Server). |
| **Groups** | 84 | 51 | -33 | SharpHound duyệt cả container `CN=Builtin` và sinh ra 27 ID nhóm trùng lặp (xem Mục 2.3). |
| **OUs** | 1 | 1 | 0 | Đồng nhất cấu trúc OU. |
| **GPOs** | 3 | 3 | 0 | Đồng nhất các chính sách miền. |
| **Containers** | 203 | 19 | -184 | SharpHound đệ quy sâu toàn bộ cây hệ thống LDAP; BloodHound.py chỉ lấy container cấp cao. |
| **AD CS Files** | 37 (5 files) | 0 | -37 | Chỉ SharpHound hỗ trợ cờ thu thập dịch vụ chứng chỉ Active Directory Certificate Services. |
| **Tổng số bản ghi** | **347** | **94** | **-253** | Phản ánh sự khác biệt về chiến lược truy vấn của hai công cụ. |
| **Số ID duy nhất** | **320** | **94** | **-226** | 27 ID nhóm bị lặp trong bản SharpHound. |
| **Số ID thuộc 6 loại M1** | **80** | **75** | **-5** | Lọc theo 6 loại: User, Computer, Group, Domain, GPO, OU. |

### 2.3. Hien tuong trung lap nhom trong Dataset A va nguy co ghi de (Last-Write-Wins)
Trong tệp `NORTH_20240410083414_groups.json` của SharpHound, có đúng **27 ObjectIdentifier bị xuất hiện 2 lần**:
- Lần xuất hiện thứ nhất: Bản ghi chứa đầy đủ các thuộc tính `Properties`, `Members`, `Aces`.
- Lần xuất hiện thứ hai: Bản ghi dạng stub chỉ chứa `ObjectIdentifier` và các mảng rỗng.
- **Rủi ro kiến trúc cho Parser (Refs #8):**
  Nếu module parser sử dụng chiến lược ghi đè bản ghi đơn giản (last-write-wins dictionary mapping), bản ghi stub đọc sau sẽ xóa sạch toàn bộ danh sách thành viên `Members[]` đã đọc trước đó.
  Parser bắt buộc phải triển khai cơ chế hợp nhất thông minh (merge attributes) để bảo toàn dữ liệu quan hệ.

### 2.4. Tham chieu ngoai pham vi xuat ban (Referenced Topology vs Export Scope)
Trong tệp `domains.json` của Dataset A:
- Miền `NORTH.SEVENKINGDOMS.LOCAL` chứa một quan hệ tin cậy:
  - Mục tiêu: `SEVENKINGDOMS.LOCAL`
  - Loại tin cậy: `ParentChild`, hai chiều (`Bidirectional`), `SidFilteringEnabled: False`.
- Tuy nhiên, trong tập tệp nén của Dataset A, hoàn toàn không có các tệp dữ liệu của miền cha `SEVENKINGDOMS.LOCAL`.
- Đây là một tham chiếu biên (Dangling Trust Reference).
  Parser phải ghi nhận `SEVENKINGDOMS.LOCAL` như một nút biên (Boundary Node) và không được coi việc thiếu tệp là lỗi phân tích.

---

## 3. Ho So Chi Tiet Dataset B: Enterprise ad_sampledata (Rung Da Mien Doanh Nghiep)

### 3.1. Thong tin luu tru va ma bam tong the
- Nguồn gốc: Tệp nén trích xuất môi trường phòng thí nghiệm mô phỏng doanh nghiệp đa miền `ad_sampledata` (enterprise-style multi-domain lab dataset).
- Tệp lưu trữ gốc: `a8bfbcf9-4226-40ed-a0c4-a2cc05dbc708.zip`.
- Dung lượng file nén: 3.524.044 bytes (~3.5 MB).
- Mã băm SHA-256: `2adb4bd1a7286869c00b0e2698dc5275b9520178fd8a07ead4cdcdb5159161ba`.
- Công cụ thu thập: SharpHound v2.3.3 (Schema v6, `meta.methods = 521215`).
- Thời điểm thu thập: Ngày 2024-03-05 (từ 11:00:18 đến 11:14:14 UTC).
- Tổng số tệp dữ liệu: 31 tệp JSON phân bổ theo 3 miền xuất khẩu.
- Tổng số bản ghi thô: **1.718 bản ghi**.
- Tổng số ObjectIdentifier duy nhất trên toàn bộ 31 tệp: **1.469 ID**.
- Tổng số ObjectIdentifier duy nhất thuộc 6 loại đối tượng cốt lõi M1: **407 ID**.
  *(Lưu ý: 1.718 là số bản ghi thô, 1.469 là số đối tượng AD duy nhất, và 407 là số đỉnh tiềm năng của đồ thị M1; không đánh đồng 1.718 là số đỉnh đồ thị).*
- **Chứng cứ độc lập và giới hạn nguồn (Provenance Witness & Limitations):**
  Tệp nén cục bộ lịch sử `a8bfbcf9-4226-40ed-a0c4-a2cc05dbc708.zip` không được lưu trữ trực tiếp trong repository.
  Mã băm SHA-256 của 4 tệp giải nén được hiệu chỉnh (`aiacas.json`, `certtemplates.json`, `computers.json`, `containers.json` thuộc miền `PHANTOM.CORP`) được kiểm chứng độc lập từ 2 nguồn công khai tại các commit cố định:
  - `SquidSec/BloodBash@a465568cc9058d2faa8d04c2dd3e600c68e9d2c7` (đường dẫn `SampleSharphoundADData/`).
  - `dogwynn/bloodhound-networkx@d80dd88936fbb59b3fe791a7f375528e55276639` (đường dẫn `tests/data/ad_sampledata/20240305110018/`).
  Hai nguồn trên lưu trữ các byte nhị phân giữ nguyên ký tự xuống dòng CRLF và khớp mã băm SHA-256 chính xác của 4 tệp trích xuất.
  Các mirror công khai này chỉ xác thực tính toàn vẹn byte của từng tệp JSON riêng lẻ sau giải nén, không chứng minh mã băm của tệp nén ZIP lịch sử.

### 3.2. Bang thong ke chi tiet 31 tep du lieu Dataset B
| Tên tệp | Miền | Loại dữ liệu | Kích thước (B) | Số bản ghi (`data`) | Meta Count | Lệch | Mã băm SHA-256 |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `20240305110018_aiacas.json` | `PHANTOM.CORP` | AIA CAs | 10.521 | 4 | 4 | 0 | `496652c54a75859279566839131cbdbe067adb1d15789fd833ac26797f6de11d` |
| `20240305110018_certtemplates.json` | `PHANTOM.CORP` | CertTemplates | 209.820 | 63 | 63 | 0 | `1e096aafed6ab53c8cac9ee7cca0fc02d413e4e9c08a5d5dc0c4536edfff0725` |
| `20240305110018_computers.json` | `PHANTOM.CORP` | Computers | 93.716 | 21 | 20 | +1 | `1b4190f67802fb0069df4306edbde1a66973f0dcddfd97647719c67e6cd10300` |
| `20240305110018_containers.json` | `PHANTOM.CORP` | Containers | 349.309 | 208 | 208 | 0 | `21ff9990576a176c5378d8adffdf88520ef5ae5580db68962140f55a880baeea` |
| `20240305110018_domains.json` | `PHANTOM.CORP` | Domains | 8.053 | 1 | 1 | 0 | `b399adb88e991aa587b6891ccdaa8c0317d5e6a1d843aa81efe15942a4dd05f7` |
| `20240305110018_enterprisecas.json` | `PHANTOM.CORP` | Enterprise CAs | 16.731 | 2 | 2 | 0 | `a8fc814e89f4920ad9612b75d6ea63b6d57c8d9ea8094be7f921b72e480645d8` |
| `20240305110018_gpos.json` | `PHANTOM.CORP` | GPOs | 43.667 | 22 | 22 | 0 | `20e642963970ca6e287c3b37a5677c5eb35287454e0818870bfbe25b6154e414` |
| `20240305110018_groups.json` | `PHANTOM.CORP` | Groups | 156.154 | 115 | 113 | +2 | `f54b90adc6e7c116681fc462c1e4c61f0f49d41994767ea699b861f8251c9cb3` |
| `20240305110018_ntauthstores.json` | `PHANTOM.CORP` | NTAuthStores | 2.190 | 1 | 1 | 0 | `a9695c87188e69e36de0e79d678c0ef1bf7afa8b26b34955e570788d159bc145` |
| `20240305110018_ous.json` | `PHANTOM.CORP` | OUs | 24.097 | 13 | 13 | 0 | `5dc5ad12d6f95dc68fc292e6ec725dd4348f14c95238e86a6c2b95c6c4e88391` |
| `20240305110018_rootcas.json` | `PHANTOM.CORP` | Root CAs | 10.471 | 4 | 4 | 0 | `aa29fd53820d57064d4881b1e62c9053dc2c0435c5b9f3d06ee429ce7533e13a` |
| `20240305110018_users.json` | `PHANTOM.CORP` | Users | 181.760 | 53 | 49 | +4 | `d226d444835cbe66da700e7ea7936713dcd665e0da47e86bb14486f86d11d9fc` |
| `20240305110427_computers.json` | `GHOST.CORP` | Computers | 4.354 | 1 | 1 | 0 | `0408539a96d2b40061b38d1a00d3e236f96c85b9dcf805eefc1e1496e69e793b` |
| `20240305110427_containers.json` | `GHOST.CORP` | Containers | 344.807 | 206 | 206 | 0 | `78032d49f434341261812f4a24a2a405c2da577da08525199fb2bab58918b457` |
| `20240305110427_domains.json` | `GHOST.CORP` | Domains | 3.862 | 1 | 1 | 0 | `292345960ed054ebba8223091eafcb41856bcb81d8162779d2e1e77ecbeffb76` |
| `20240305110427_gpos.json` | `GHOST.CORP` | GPOs | 5.810 | 3 | 3 | 0 | `f5bd6f137f0a7c927373712c5b5019c45ba095bea19158ff68543cd96a8f9a20` |
| `20240305110427_groups.json` | `GHOST.CORP` | Groups | 96.038 | 58 | 58 | 0 | `3f24a349a7fc2b885262d21415f2c393897147f4d55d185264b4ab804e70fe2d` |
| `20240305110427_ous.json` | `GHOST.CORP` | OUs | 2.096 | 1 | 1 | 0 | `5d89ba741928d244bd8ce4eaa02fccb1d3e3becaeb92bb72c4f3b699bd3719f2` |
| `20240305110427_users.json` | `GHOST.CORP` | Users | 22.192 | 7 | 5 | +2 | `7bf1f8f3e699e13058cbf4b8e512da7fa17e6933ad2847e3bef54acec96150a7` |
| `20240305111414_aiacas.json` | `WRAITH.CORP` | AIA CAs | 5.005 | 2 | 2 | 0 | `62c83528c736d235ba485fcd67f4a2646ab6b41360bfe41063e077fb148d19d3` |
| `20240305111414_certtemplates.json` | `WRAITH.CORP` | CertTemplates | 137.279 | 43 | 43 | 0 | `18f5b86a0c1173d62ae189aee4a72e6fea0ab44cdc0ccb57a94df66d08129b24` |
| `20240305111414_computers.json` | `WRAITH.CORP` | Computers | 69.576 | 12 | 11 | +1 | `6ca6c9180ce5fa714a25711897ba37c3e12a00434693e0d1438379c74db06884` |
| `20240305111414_containers.json` | `WRAITH.CORP` | Containers | 1.315.277 | 707 | 707 | 0 | `edb73a7eb36fe53a496f4036f9b9894b9adf6e7c1bdf7ab319f033ffd41b5537` |
| `20240305111414_domains.json` | `WRAITH.CORP` | Domains | 5.598 | 1 | 1 | 0 | `70b32fa0e0132fb76156d0d43383e1323879ec721a847557749af26f919a8282` |
| `20240305111414_enterprisecas.json` | `WRAITH.CORP` | Enterprise CAs | 19.476 | 2 | 2 | 0 | `bb19365e969565f25f1cdd55d19cfa5b41199894c0592794320c66a887d57c8b` |
| `20240305111414_gpos.json` | `WRAITH.CORP` | GPOs | 14.511 | 7 | 7 | 0 | `6828bc60f91c23e0aaf9cdf4848e8b368ccdb1a830ef1a262d14b148474db25d` |
| `20240305111414_groups.json` | `WRAITH.CORP` | Groups | 200.519 | 112 | 112 | 0 | `d7af691de5143bb204d1a7e1831b0f8cd69a6a1c838a39ac3b57688830a0d4ce` |
| `20240305111414_ntauthstores.json` | `WRAITH.CORP` | NTAuthStores | 2.194 | 1 | 1 | 0 | `a255193cf52e65b7519401e74cbcbc212eff154bb99fdb0f112e67dcc46fa43a` |
| `20240305111414_ous.json` | `WRAITH.CORP` | OUs | 10.965 | 6 | 6 | 0 | `2173ae69a0f9f63d0c4d250316c18184567d6968317d28c62320029d31fff6f0` |
| `20240305111414_rootcas.json` | `WRAITH.CORP` | Root CAs | 2.541 | 1 | 1 | 0 | `42b37a8cf728da25a32db76561037b8ebf45591bb08019cbc18be6d5ea5727d0` |
| `20240305111414_users.json` | `WRAITH.CORP` | Users | 150.005 | 40 | 39 | +1 | `ce87f3688dcea6cf8df7a461d5ec24696056e2a10c533a546c3c9739b7839750` |

### 3.3. Phan tich sai lech metadata va trung lap ID trong Dataset B
1. **Sai lệch giữa `data` array length và `meta.count`:**
   - Tại `PHANTOM.CORP`: `users.json` có 53 bản ghi thực tế so với `meta.count = 49` (chênh lệch +4).
     Sự khác biệt gồm SID `NETWORK SERVICE` (`S-1-5-20`), tài khoản nhân đôi bản ghi, và các tài khoản dịch vụ được xuất hiện nhiều lần.
   - Tại `GHOST.CORP`: `users.json` có 7 bản ghi so với `meta.count = 5` (+2).
   - Tại `WRAITH.CORP`: `users.json` có 40 bản ghi so với `meta.count = 39` (+1).
   - **Kết luận cho Parser:** Parser tuyệt đối không sử dụng `meta.count` để cấp phát bộ nhớ mảng hoặc kiểm tra điều kiện lặp; phải duyệt độ dài thực tế của mảng `data`.
2. **Hiện tượng trùng lặp ObjectIdentifier trong Dataset B:**
   - Trong `groups.json` của `PHANTOM.CORP`: Có đúng 28 ID nhóm bị lặp lại, cộng với 1 ID lặp trong `users.json` thành 29 ID trùng lặp.
   - Trong `groups.json` của `GHOST.CORP`: Có 6 ID nhóm bị lặp lại.
   - Trong `groups.json` của `WRAITH.CORP`: Có 28 ID nhóm bị lặp lại.
   - Tổng cộng: Có 62 ID nhóm trùng lặp (và 1 ID user trùng lặp, tổng 63 ID trùng lặp trên Dataset B).
   - **Yêu cầu đối với Parser:** Không được ghi đè (last-write-wins) mà phải hợp nhất (merge) các mảng quan hệ `Members` và `Aces` của các bản ghi cùng `ObjectIdentifier`.

### 3.4. Ranh gioi xuat ban va cac mien duoc tham chieu (Referenced Trust Targets)
Khi phân tích các tệp `domains.json` trong Dataset B:
- `PHANTOM.CORP` có 3 quan hệ tin cậy:
  - Tới `GHOST.CORP`: `ParentChild`, `Bidirectional`, `SidFilteringEnabled: False` (Miền con trong tập tệp xuất).
  - Tới `WRAITH.CORP`: `External`, `Bidirectional`, `SidFilteringEnabled: True` (Miền ngoài trong tập tệp xuất).
  - Tới `REVENANT.CORP`: `External`, `Inbound`, `SidFilteringEnabled: False` (**Ngoại vi: không có tệp dữ liệu**).
- `WRAITH.CORP` có 2 quan hệ tin cậy:
  - Tới `PHANTOM.CORP`: `External`, `Bidirectional`, `SidFilteringEnabled: True` (Trong tập tệp xuất).
  - Tới `CHILD.WRAITH.CORP`: `ParentChild`, `Bidirectional`, `SidFilteringEnabled: False` (**Ngoại vi: không có tệp dữ liệu**).
- `GHOST.CORP` có 1 quan hệ tin cậy:
  - Tới `PHANTOM.CORP`: `ParentChild`, `Bidirectional`, `SidFilteringEnabled: False`.
- **Nguyên tắc xử lý của Parser:** Các miền tham chiếu ngoại vi (`REVENANT.CORP`, `CHILD.WRAITH.CORP`) phải được parser khởi tạo dưới dạng các nút biên (Boundary/Stub Nodes) để không làm gãy đồ thị khi biểu diễn cấu trúc tin cậy.

### 3.5. Danh muc tham chieu doi tuong treo cap ban ghi (Dangling Object-level References)
Bên cạnh các miền tin cậy ngoại vi, dữ liệu còn chứa các tham chiếu cấp đối tượng (Object-level References) trỏ tới các SID hoặc DN không nằm trong danh mục định danh của tập tệp xuất bản:
1. **Dataset A (12 tham chiếu ngoại vi):**
   - Cả 12 tham chiếu trong ACE và Member đều trỏ tới các định danh thuộc miền cha chưa được xuất khẩu `SEVENKINGDOMS.LOCAL` (tiền tố SID `S-1-5-21-1032618810-739172636-1489167904-...`).
   - Các đối tượng này bao gồm `Enterprise Admins` (RID 519), `Schema Admins` (RID 518), `Domain Admins` gốc (RID 512), và các tài khoản dịch vụ/quản trị cấp rừng được gán quyền hoặc làm thành viên nhóm cục bộ trong `NORTH`.
2. **Dataset B (3 tham chiếu ngoại vi):**
   - 1 tham chiếu thành viên nhóm theo định danh DistinguishedName thay vì SID chuẩn: `CN=ENTERPRISE ADMINS,OU=GROUPS,OU=TIER0,DC=PHANTOM,DC=CORP`.
   - 2 tham chiếu trong danh sách quyền ACE trỏ tới các đối tượng ngoại miền hoặc không tồn tại trong danh mục users/groups xuất bản: `S-1-5-21-428050025-2300188546-864808017-1000` và `S-1-5-21-2697957641-2271029196-387917394-2213`.
- **Khuyến nghị cho Parser:** Parser cần ghi log cảnh báo và xử lý các tham chiếu ngoại vi này dưới dạng các đỉnh biên có nhãn rõ ràng hoặc bỏ qua an toàn theo chính sách lỗi `ErrorPolicy.SKIP_RECORD` thay vì gây lỗi dừng pipeline.

---

## 4. Ho So Chi Tiet Dataset C: SEAMLESS.INTERNAL (Synthetic Enterprise-scale Benchmark)

### 4.1. Thong tin luu tru va ma bam
- Mien muc tieu: `SEAMLESS.INTERNAL`.
- Nguon goc: Du lieu phong thi nghiem mo phong doanh nghiep duoc sinh bang cong cu BadBlood tren Domain Controller thuc te.
- Cong cu thu thap: SharpHound v3 (Schema v3).
- Snapshot manifest bat bien: `data/samples/manifests/seamless-raw-v1.json`.
- Tep luu tru tho: `data/raw/SEAMLESS/` gom 6 tep JSON (`seamless_users.json`, `seamless_groups.json`, `seamless_computers.json`, `seamless_ous.json`, `seamless_gpos.json`, `seamless_domains.json`).
- Tong so ban ghi tho (Raw records): **3.369 ban ghi** (2.493 Users, 550 Groups, 100 Computers, 223 OUs, 2 GPOs, 1 Domain).
- Tong so unique snapshot ObjectIdentifiers: **3.368 nodes** (Groups: 549 unique after deduplicating 1 duplicate group OID).
- Tong so materialized graph nodes: **3.370 nodes** (3.368 snapshot nodes + 2 external well-known nodes: `SEAMLESS.INTERNAL-S-1-5-4` [INTERACTIVE] va `SEAMLESS.INTERNAL-S-1-5-17` [IUSR]).
- Tong so raw/reference-shaped observations trong data-quality audit: **66.374** (66.372 internal + 2 boundary).
- Tong so EDA graph entries materialized: **66.371** (loại 3 raw RDU-only references; tỷ lệ 19.71 trên 3.368 snapshot IDs; chưa phải canonical graph của #44/#45).

### 4.2. Bang thong ke chi tiet ban ghi va kiem toan chat luong du lieu (Data Quality Audit)
Du lieu chat luong duoc tai lap tu dong qua ham `audit_data_quality` trong `scripts/eda_dataset_analysis.py`:

| Loai thuc the (Kind) | So ban ghi tho | Ban ghi loi (Malformed) | Ban ghi bi bo (Dropped) | ID trung lap (Duplicate) | Phan loai ngu nghia du lieu thieu chinh |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Users** | 2.493 | 0 | 0 | 0 | 2.492/2.493 `lastLogonTimestamp` zero/absent; logon activity unknown |
| **Groups** | 550 | 0 | 0 | 0 | 4/549 unique `Members[]` empty/unobserved; completeness unknown |
| **Computers** | 100 | 0 | 0 | 0 | 99/100 `operatingSystem` unpopulated; 100/100 `haslaps=false` observed; cause and effective state unknown |
| **OUs** | 223 | 0 | 0 | 0 | 223 records observed; collection completeness unknown |
| **GPOs** | 2 | 0 | 0 | 0 | 2 records observed; collection completeness unknown |
| **Domains** | 1 | 0 | 0 | 0 | 1 record observed; collection completeness unknown |
| **Tong cong** | **3.369** | **0** | **0** | **0** | EDA subset: 66.372 internal, 2 external, 0 dangling; #94 broader raw audit has 2 unresolved references |

### 4.3. Dac trung cau truc do thi va be mat tan cong (Graph Attack Surface)
Các metrics dưới đây tính trên preliminary EDA graph với 66.371 entries, không phải canonical graph, effective authorization hoặc observed attack.
- **Do ket noi (Connectivity)**: 1 thanh phan lien thong yeu (WCC) duy nhat bao phu 100% (3.370 nodes).
- **Giant SCC**: Chua 1.172 nodes (chiem 34.78% tong do thi), phan anh loi ket noi phan quyen chat che giua cac thuc the dac quyen.
- **He so tap trung (Clustering Coefficient)**: Dat `0.6231` tren hinh chieu vo huong, cho thay muc do ket cum quyen han cuc ky cao.
- **Duong kinh do thi (Diameter)**: Dat `4` tren giant component cua hinh chieu vo huong (duong kinh do thi co huong la vo cung do su hien dien cua cac sink nodes).
- **Kha nang tiep can Tier-0 (Reachability to Tier-0)**:
  - Ty le tren security principals khong thuoc muc tieu: **1.170 / 3.141 = 37.25%** (Users: 1.085 / 2.493 = 43.52%; Groups: 70 / 551 = 12.70%; Computers: 15 / 100 = 15.00%).
  - Ty le tren toan bo nut do thi: **1.170 / 3.370 = 34.72%**.
  - So muc tieu Tier-0 tiep can trung binh theo lop: User dat 1.31, Group dat 0.39, Computer dat 0.45.
- **Phan bo bac va do lech (Privilege Concentration)**:
  - Do thi the hien dac tinh phan bo duoi nang (heavy-tailed / highly concentrated synthetic enterprise benchmark) voi Gini out-degree dat `0.8944`.
  - Top 1% nodes chiem 75.76% raw outgoing EDA entries; không chứng minh quyền khai thác hiệu lực.
  - Trung tam quyen han tap trung cao nhat tai `Builtin Administrators` (12.383 canh ra) va `Domain Admins` (6.753 canh ra).
- **Do du thua duong di (Path Redundancy Capping)**:
  - Cac truy van duong di thay the duoc gioi han chan o nguong 20 paths (`capped_at: 20`, `truncated: True` khi cham nguong).
  - Vi du: tai khoan `ARMAND_ROSE` va `ANNABELLE_MEDINA` cham nguong cap 20 duong di thay the trong pham vi hop limit.

---

## 5. Ho So Chi Tiet Telemetry Dataset: evtx_data.csv (Candidate Audit Evidence Taxonomy)

### 5.1. Thong tin nguon va pham vi du lieu
- Tep du lieu: `data/raw/telemetry/evtx_data.csv`.
- Snapshot manifest bat bien: `data/samples/manifests/telemetry-raw-v1.json`.
- Tong so corpus rows: **4.633** voi 8 nhan `EVTX_Tactic` upstream; nhan khong phai Windows-native ground truth hoac confirmed attack (6.432 rows/11 nhan la thong tin boi canh ngoai snapshot chua xac minh).
- Pham vi thuc the: 19 may tinh khac nhau va 35 tai khoan nguoi dung muc tieu.
- Cua so thoi gian thuc nghiem: Tu ngay `2017-06-09` den ngay `2021-06-09`.

### 5.2. Ranh gioi kien truc voi Issue #58 (Attack Semantics Boundary)
Theo ADR-0007 va thiet ke Attack Semantics tai #58/#63:
- **Nguyen tac bat bien (Invariant)**:
  `ExpectedTelemetry != ObservedActivity != StructuralRelationship != ConfirmedAttack`
- **Descriptive inventory only**: EDA chi dem phan bo EventID va nhan upstream trong corpus doc lap; khong con ma tran edge-to-event.
  [`configs/attack_semantics.yml`](../../configs/attack_semantics.yml) la runtime semantic catalog duy nhat va ExpectedTelemetry khong phai ObservedActivity.
- **Nghiem cam phep noi thuc the truc tiep (No Entity-level Join)**: Khong duoc join truc tiep cap danh tinh (SID) giua telemetry va snapshot AD khi khong chung moi truong hoac thoi gian thu thap thuc te.
- **Khong ngoai suy trong so detectability**: Khong duoc dung su kien telemetry de suy dien thanh xac suat tan cong thanh cong, xac nhan path SEAMLESS, hoac tu dong gan trong so production cho MAUT.

---

## 6. Bang Doi Chieu 8 Loai Canh Cot Loi M1 Sang Bang Chung Du Lieu Tho

Bang duoi day la doi chieu evidence lich su cua 8 loai canh M1 tren A/B.
No khong phai la BloodHound reconciliation hay primary evaluation cua SEAMLESS.
Số liệu được kiểm chứng trực tiếp bằng script `scripts/verify_data_inventory.py`, phân định rõ ràng giữa **Raw Occurrences** (số lần xuất hiện trong tệp JSON) và **Unique Relation Pairs** (số cặp quan hệ logic duy nhất).
Các counts lịch sử không phải số canonical edges cuối cùng; identity resolution và reconciliation phải tuân theo contract hiện hành.
Theo accepted #80/PR #90, không lọc structural relationships chỉ vì `enabled: false`; account applicability thuộc semantic/runtime layer.

| Loại cạnh M1 | Nguồn bằng chứng thô (Raw Evidence Source) | Dataset A: NORTH (SharpHound / Python) | Dataset B: `ad_sampledata` (PHANTOM + GHOST + WRAITH) | Mức độ tin cậy và Rào cản kỹ thuật |
| :--- | :--- | :---: | :---: | :--- |
| **`MemberOf`** | Thuộc tính `Members[]` trong `groups.json` | **42** raw / **42** unique (SH)<br/>**42** raw / **42** unique (Py) | **161** raw / **161** unique pairs<br/>(PHANTOM: 78, GHOST: 25, WRAITH: 58) | **Độ tin cậy: Rất cao.** Bằng chứng LDAP tĩnh trực tiếp. Parser phải xử lý hợp nhất các nhóm bị lặp ID để không mất membership. |
| **`AdminTo`** | Mảng `LocalGroups[]` (SID `-544`) và `LocalAdmins[]` trong `computers.json` | **7** raw / **7** unique (SH)<br/>**0** raw / **0** unique (Py) | **13** raw / **13** unique pairs<br/>(PHANTOM: 2, GHOST: 0, WRAITH: 11) | **Độ tin cậy: Có điều kiện.** Đánh giá tính đầy đủ theo từng primitive thu thập qua `Collected` và `FailureReason`. Trạng thái `Status.Connectable` chỉ là tín hiệu kết nối mạng, không được dùng làm cổng phủ quyết toàn cục đối với evidence đã thu thập thành công. Host có lỗi truy cập RPC/SAMR (`StatusAccessDenied`) được gán `unknown`. |
| **`GenericAll`** | Mảng quyền `Aces[]` với `RightName == "GenericAll"` | **383** raw / **378** unique (SH)<br/>**177** raw / **177** unique (Py) | **3.500** raw / **3.293** unique pairs<br/>(PHANTOM: 451, GHOST: 331, WRAITH: 2.718) | Bằng chứng ACE dương tính; `adminCount=1` không tự chứng minh trạng thái bảo vệ hoặc thay đổi quyền trong snapshot. |
| **`WriteDacl`** | Mảng quyền `Aces[]` với `RightName == "WriteDacl"` | **573** raw / **570** unique (SH)<br/>**138** raw / **136** (Py) | **2.603** raw / **2.229** unique pairs<br/>(PHANTOM: 880, GHOST: 488, WRAITH: 1.235) | ACE là structural evidence; tự cấp quyền là semantic transition riêng, phụ thuộc runtime predicates. |
| **`ForceChangePassword`** | Mảng quyền `Aces[]` (`RightName == "ForceChangePassword"`) | **0** raw / **0** unique (SH)<br/>**0** raw / **0** unique (Py) | **52** raw / **52** unique pairs<br/>(PHANTOM: 5, GHOST: 0, WRAITH: 47) | **Độ tin cậy: Rất cao.** Hoàn toàn vắng mặt trong Dataset A; chỉ xuất hiện phong phú trong Dataset B. |
| **`CanRDP`** | `LocalGroups[]` (SID `-555`) kết hợp `UserRights` allow/deny | **1** raw membership / verified unknown (SH)<br/>**0** raw (Python) | **1** raw membership / effective assessment phụ thuộc UserRights completeness (DC01.PHANTOM.CORP) | Raw membership không đồng nghĩa verified `CanRDP`; WINTERFELL (A) có `StatusAccessDenied` cho UserRights và assessment unknown; DC01 (B) chỉ thấy allow-right cho local Administrators `-544`, không cho `-555`; kết luận effective cần completeness và deny-right evidence. |
| **`CanPSRemote`** | `LocalGroups[]` (SID `-580`) hoặc positive effective RMU membership | **0** raw / **0** unique (SH)<br/>**0** (Python) | **0** raw memberships trong phạm vi khảo sát | Raw non-observation không chứng minh canonical absence; WinRM service/network/authentication/custom endpoint là runtime/endpoint evidence riêng. |
| **`HasSession`** | Mảng `Sessions[]`, `PrivilegedSessions[]`, `RegistrySessions[]` | **9** raw / **4** unique (SH)<br/>**0** (Python) | **60** raw / **29** unique pairs<br/>(Raw: PHANTOM: 51, GHOST: 0, WRAITH: 9;<br/>Unique: PHANTOM: 26, GHOST: 0, WRAITH: 3) | Session observation là ephemeral opportunity và không chứng minh credential possession; collection-time policy theo #91, canonical time-status serialization chờ #97; `Connectable: False` không phủ quyết positive session evidence trên `JONAS-TEST-MS01` tại PHANTOM. |

---

## 6.1. Bang Kiem Ke Bang Chung Mo Rong va Dinh Huong Phat Trien (Extension Evidence / Future Work)

Bên cạnh 8 loại cạnh cốt lõi M1, khảo sát dữ liệu thô ghi nhận sự hiện diện của các quan hệ và thực thể mở rộng. Nhằm tuân thủ nguyên tắc không tự ý mở rộng phạm vi triển khai của Milestone M1 theo Issue #20, bảng dưới đây định rõ hiện trạng quan sát và định hướng xử lý cho từng loại bằng chứng:

| Quan hệ / Đối tượng (Relation / Object) | Bằng chứng thô (Raw Evidence Source) | Quan sát Dataset A | Quan sát Dataset B | Tình trạng M1 (M1 Status) | Định hướng xử lý (Disposition) |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Trust Topology** (`ParentChild`, `External`) | Mảng `Trusts[]` trong `domains.json` kèm cờ `TrustDirection`, `TrustType`, `SidFilteringEnabled` | **1** quan hệ `ParentChild` hai chiều tới `SEVENKINGDOMS.LOCAL` | **6** quan hệ trên 3 miền (`ParentChild` và `External`) kèm 2 miền stub | Ngoài core M1 | **Future work (M2+).** Parser M1 chỉ khởi tạo Stub/Boundary nodes cho các miền tham chiếu để bảo toàn cấu trúc tin cậy; không sinh cạnh tấn công trong M1. |
| **Constrained Delegation** (`AllowedToDelegate`) | Mảng `AllowedToDelegate[]` (`msDS-AllowedToDelegateTo`) trong `computers.json` và `users.json` | **2** quan sát (Py: `CASTELBLACK$` và user `...-1118` trỏ tới `WINTERFELL$`); **0** (SH) | **1** quan sát (PHANTOM: máy trạm `...-2171` trỏ tới `...-1000`) | Ngoài core M1 | **Future work (M2+).** Parser ghi nhận schema và bảo toàn trường dữ liệu nếu có; không tạo cạnh ủy thác trong đồ thị M1. |
| **Resource-Based Constrained Delegation (RBCD)** | Mảng `AllowedToAct[]` (`msDS-AllowedToActOnBehalfOfOtherIdentity`) trong `computers.json` | **0** quan sát (mảng rỗng trên cả SH và Py) | **1** quan sát (WRAITH: `EXTCA01.WRAITH.CORP` cho phép `EXTCA02.WRAITH.CORP$`) | Ngoài core M1 | **Future work (M2+).** Giữ nguyên thuộc tính trong raw record của adapter; không sinh cạnh tấn công trong M1. |
| **Active Directory Certificate Services (AD CS)** | 5 tệp cấu trúc AD CS (`aiacas`, `certtemplates`, `enterprisecas`, `ntauthstores`, `rootcas`) và quyền cấp phát `Enroll` | **5** tệp, **37** bản ghi trong SH; **0** trong Py (không thu thập) | **10** tệp trên 2 miền xuất bản (**74** bản ghi tại PHANTOM, **49** tại WRAITH, tổng **123** bản ghi; GHOST không hiện diện trong export này) | Ngoài core M1 | **Future work (M3+).** Tạm thời bỏ qua các thực thể và cạnh liên quan đến PKI/AD CS tại M1 để tập trung chuẩn hóa 6 loại node và 8 loại edge cốt lõi. Tách bạch với Shadow Credentials (`AddKeyCredentialLink`). |
| **Read-Only Domain Controller (RODC) / PRP** | `PrimaryGroupSID` kết thúc bằng RID 521 (`S-1-5-21-...-521` theo MS-ADTS 6.1.1.3.2), vị trí dưới `OU=DOMAIN CONTROLLERS` và nhóm `Denied RODC Password Replication Group` trong `groups.json` (Lưu ý: thuộc tính `Properties.isdc` trong export báo `false` do dị biệt công cụ thu thập SharpHound) | **0** (không có máy chủ RODC) | **2** máy chủ RODC (`RODC01.PHANTOM.CORP` và `EXTRODC01.WRAITH.CORP`) có `PrimaryGroupSID` kết thúc bằng RID 521, nằm dưới `OU=DOMAIN CONTROLLERS`, mang cờ `isdc: false` | Ngoài core M1 | **Ranh giới an ninh / Bằng chứng xác thực (Boundary limitation / Verified evidence).** Phân loại chính xác RODC dựa trên `PrimaryGroupSID` (RID 521) và OU thay vì hostname prefix hay cờ `isdc`. Không có cạnh cấu trúc `DCSync`/`ControlsDomain`; applicability semantic/runtime phụ thuộc effective replication rights, PRP và bằng chứng snapshot/runtime, thiếu bằng chứng là `unknown`/`indeterminate`. |

---

## 7. Danh Muc Phat Hien An Ninh Chuyen Sau (Observation - Interpretation - Confidence - Verification)

Các phát hiện an ninh trọng yếu được cấu trúc chuẩn hóa theo tiêu chí của Issue #20:

### 7.1. Phat hien 1: Quan he thanh vien Local Administrator xuyen mien tren EXTDC01
- **Observation (Quan sát):**
  Trong tệp `20240305111414_computers.json` của miền `WRAITH.CORP`, nhóm Administrators cục bộ (`LocalGroups` kết thúc bằng `-544`) trên máy chủ điều khiển miền `EXTDC01.WRAITH.CORP` chứa thành viên:
  `S-1-5-21-2697957641-2271029196-387917394-2113`.
  Định danh này thuộc về miền `PHANTOM.CORP`.
- **Interpretation (Diễn giải):**
  Đây là một bằng chứng phân quyền tài nguyên xuyên miền (Cross-domain Resource Assignment).
  Kẻ tấn công nếu kiểm soát được tài khoản `...-2113` tại `PHANTOM.CORP` sẽ có quyền quản trị cục bộ trên Domain Controller của miền `WRAITH.CORP`.
- **Confidence (Mức độ tin cậy):**
  Trung bình đến Cao.
  Bằng chứng thành viên trong JSON là xác thực.
  Tuy nhiên, việc thực thi tấn công còn phụ thuộc vào trạng thái kết nối mạng và tường lửa giữa hai miền.
- **Need to verify (Cần xác minh):**
  Cần kiểm chứng máy `EXTDC01` có trạng thái `Connectable: True` hay không, tài khoản `...-2113` có đang ở trạng thái `enabled: true` hay không, và cổng SMB/RPC giữa hai vùng mạng có mở không.
  Không gọi đây là "hành vi di chuyển ngang đã thành công" mà chỉ là "vector tiềm năng".

### 7.2. Phat hien 2: Sai lech thu thap uy thac Kerberos co rang buoc tren CASTELBLACK$
- **Observation (Quan sát):**
  Tệp SharpHound của Dataset A để trống trường `AllowedToDelegate: []` trên máy trạm `CASTELBLACK$`.
  Trong khi đó, tệp BloodHound-Python trích xuất được `CASTELBLACK$` ủy thác tới `WINTERFELL$`.
- **Interpretation (Diễn giải):**
  SharpHound phiên bản cũ có thể đã bỏ qua thuộc tính LDAP `msDS-AllowedToDelegateTo` khi không được cấp đủ cờ hoặc gặp lỗi truy vấn.
  Kỹ thuật S4U2self và S4U2proxy cho phép leo quyền từ máy trạm lên Domain Admin trong kịch bản lab GOADv2.
- **Confidence (Mức độ tin cậy):**
  Rất cao (Kịch bản ủy thác Kerberos có ràng buộc đã được tài liệu hóa trong thiết kế lab GOADv2).
- **Need to verify (Cần xác minh):**
  Kiểm tra thuộc tính `servicePrincipalName` và `msDS-AllowedToDelegateTo` trên tệp raw để hướng dẫn parser nạp đúng quan hệ dù sử dụng nguồn trích xuất nào.

### 7.3. Phat hien 3: May chu Read-Only Domain Controller (EXTRODC01 va RODC01) va Chinh sach PRP
- **Observation (Quan sát):**
  Trong miền `WRAITH.CORP` và `PHANTOM.CORP`, xuất hiện hai máy chủ `EXTRODC01.WRAITH.CORP` và `RODC01.PHANTOM.CORP` có thuộc tính `PrimaryGroupSID` kết thúc bằng RID 521 (`S-1-5-21-...-521`), nằm dưới container `OU=DOMAIN CONTROLLERS`.
  Tuy nhiên, trong tệp `computers.json` của cả hai miền, trường `Properties.isdc` lại ghi nhận giá trị `false` (trong khi các Writeable DC như `EXTDC01` và `DC01` có `PrimaryGroupSID` kết thúc bằng RID 516 và `isdc: true`).
  Đồng thời, các tài khoản quản trị miền đặc quyền (`Domain Admins`, `Enterprise Admins`, `krbtgt`) nằm trong nhóm cấm nhân bản mật khẩu (`Denied RODC Password Replication Group`).
- **Interpretation (Diễn giải):**
  Theo đặc tả MS-ADTS 6.1.1.3.2, RID 521 là nhóm well-known `Read-only Domain Controllers` của Active Directory. Căn cứ `PrimaryGroupSID` có RID 521 kết hợp cấu trúc OU là bằng chứng xác thực tuyệt đối rằng hai máy tính này là RODC.
  Việc collector SharpHound v2.3.3 gán `Properties.isdc = false` là một dị biệt ở tầng công cụ thu thập (collector anomaly), không phản ánh đúng vai trò hệ điều hành.
  Quyền Local Administrator hoặc vai trò RODC riêng lẻ không đủ chứng minh khả năng DCSync hay trích xuất bí mật toàn miền.
  Quyền nhân bản bị cấp sai có thể mở rộng khả năng sao chép mật khẩu của RODC; xem [Microsoft KB 4050867](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/rodc-replicates-passwords-grant-incorrect-permissions).
- **Confidence (Mức độ tin cậy):**
  Cao (đối với việc phân loại máy chủ là RODC dựa trên bằng chứng chuẩn MS-ADTS RID 521).
  Độ tin cậy phân loại vai trò không xác nhận effective replication rights hay PRP của snapshot.
- **Need to verify (Cần xác minh):**
  Parser và engine cần nhận diện RODC thông qua `PrimaryGroupSID` kết thúc bằng RID 521 (hoặc kết hợp OU `OU=DOMAIN CONTROLLERS`) thay vì dựa vào tiền tố tên máy tính (heuristic) hoặc cờ nhị phân `Properties.isdc`.
  Theo ADR-0008 và Graph Contract 1.0.0, đồ thị cấu trúc không chứa cạnh `ControlsDomain` hay `DCSync`.
  DCSync, nếu được mô hình hóa, thuộc tầng semantic/runtime; applicability phải dựa trên effective replication rights, PRP và bằng chứng snapshot/runtime.
  Khi thiếu bằng chứng bắt buộc, kết quả phải là `unknown` hoặc `indeterminate`, không hard-code `false` từ vai trò RODC.

### 7.4. Phat hien 4: Quyen phu quyet SeDenyRemoteInteractiveLogonRight
- **Observation (Quan sát):**
  Cấu trúc `UserRights` trong SharpHound v6 ghi nhận đồng thời các quyền cho phép và quyền từ chối đăng nhập từ xa.
- **Interpretation (Diễn giải):**
  Trong kiến trúc Windows Security, ACE Deny luôn có độ ưu tiên cao hơn ACE Allow.
  Nếu một tài khoản thuộc nhóm `Remote Desktop Users` nhưng đồng thời bị gán `SeDenyRemoteInteractiveLogonRight`, kết nối RDP sẽ bị chặn đứng tuyệt đối.
- **Confidence (Mức độ tin cậy):**
  Rất cao.
- **Need to verify (Cần xác minh):**
  Chỉ tạo `CanRDP` khi effective RDU membership và allow-right có positive evidence, deny-right được đánh giá đầy đủ và không có effective deny.
  Thiếu mandatory evidence hoặc collection completeness phải giữ `unknown`, không biến thành false.

---

## 8. Khuyen Nghi Truu Tuong Hoa (Abstraction Layer) Cho Module Parser (Refs #8)

Dựa trên kết quả khảo sát đối sánh cả hai tập dữ liệu, module Parser cần tuân thủ các quy tắc thiết kế kiến trúc sau:
1. **Bảo toàn Scope cho Canonical ID (Scope-Preserving Canonical ID):**
   - **Tuyệt đối không tách bỏ tiền tố miền/host khỏi các Well-known SIDs.**
     Nếu strip prefix toàn cục chuỗi `S-1-5-32-544`, các nhóm Administrators cục bộ của từng máy trạm và của các miền khác nhau trong Dataset B sẽ bị gộp thành một ID duy nhất, gây đụng độ đỉnh (collision) và làm sai lệch nghiêm trọng ranh giới ủy quyền.
   - **Quy tắc chuẩn hóa định danh:**
     - Các đối tượng cấp miền (Domain-scoped): Giữ nguyên định danh chuẩn của miền (`<DOMAIN-SID>-<RID>`).
     - Các nhóm cục bộ (Local groups): Giữ nguyên tiền tố chủ thể sở hữu (ví dụ `<HOST>-S-1-5-32-544` cho nhóm trên máy tính, `<DOMAIN>-S-1-5-32-544` cho nhóm của domain).
     - GUIDs: Viết thường toàn bộ (`.lower()`) để thỏa mãn chuẩn RFC 4122.
2. **Hợp nhất bản ghi trùng lặp thay vì ghi đè (Merge vs Last-Write-Wins):**
   - Do có 27 ID nhóm bị lặp trong Dataset A và 62 ID nhóm bị lặp trong Dataset B (28 tại PHANTOM, 6 tại GHOST, 28 tại WRAITH, cộng 1 user tại PHANTOM, tổng 63 bản ghi trùng lặp), parser bắt buộc phải thực hiện phép hợp nhất (merge) các mảng `Members` và `Aces` thay vì để bản ghi sau ghi đè bản ghi trước.
3. **Xử lý tham chiếu ngoài phạm vi (Boundary / Stub Nodes):**
   - Các miền được tham chiếu qua quan hệ tin cậy nhưng không có tệp dữ liệu (`SEVENKINGDOMS.LOCAL`, `REVENANT.CORP`, `CHILD.WRAITH.CORP`) phải được khởi tạo như các đỉnh biên (Stub/Boundary Nodes) để bảo toàn cấu trúc Trust Topology mà không làm sập pipeline.
4. **Bắt buộc lưu trữ thuộc tính `domain` trên mỗi Node:**
   - Trường `domain` là bắt buộc để phân tách ranh giới an ninh và áp dụng đúng chính sách lọc SID (`SidFilteringEnabled`) khi đánh giá đường đi giữa các miền.
5. **Minh bạch hóa nguồn gốc bằng chứng (Provenance Tracking):**
   - Direct structural evidence phải giữ raw source reference và collection-time policy theo #91; canonical serialization của assumed/derived/external time status thuộc #97.
   - Không bịa timestamp, không biến unknown hoặc rejected evidence thành traversable edge; ordered derived lineage thuộc #92.

---

## 9. Danh Muc Cau Hoi Mo Cho Milestone M1 va M2 (Open Questions)

Dưới đây là các vấn đề kỹ thuật và nghiên cứu cần giải quyết trong các bước tiếp theo của Milestone M1 và M2:
1. **Parser Adapter Abstraction:**
   Làm thế nào để interface `RawDataLoader` chuẩn hóa được sự khác biệt giữa cấu trúc SharpHound v6 (`LocalGroups`/`UserRights`) và BloodHound-Python (cũng như các export legacy v4/v5 với mảng phẳng `LocalAdmins`) mà không làm phình to schema của `configs/contract.yml`?
2. **Xử lý ranh giới tin cậy và lọc SID (SID Filtering):**
   Khi tính toán đường đi di chuyển ngang qua External Trust có cờ `SidFilteringEnabled: True` (như giữa `PHANTOM.CORP` và `WRAITH.CORP`), engine cần cơ chế nào để lọc bỏ các SID đặc quyền cao (ví dụ RID 500, 512, 519) khỏi danh sách token ủy quyền liên miền?
3. **Mô hình hóa cost (Issue #42):**
   Successor ADR của #42 phải quyết định cost thuộc structural relationship, semantic transition, path composition hay abstraction khác.
   `unit` là baseline correctness; không gán time-decay weight cho `HasSession` khi collection-time status và cost ownership chưa được chấp nhận.
4. **Xử lý tham chiếu đối tượng treo (Dangling Object References):**
   Đối với 12 tham chiếu trỏ sang miền gốc `SEVENKINGDOMS.LOCAL` trong Dataset A hoặc tham chiếu dạng DN trong Dataset B, parser nên tạo các nút giả lập (Boundary Stub Nodes) hay áp dụng `ErrorPolicy.SKIP_RECORD` kèm cảnh báo audit?
5. **Kế hoạch mở rộng Synthetic Fixtures:**
   Có nên trích xuất một phần topology thu nhỏ từ Dataset B (bao gồm 1 quan hệ Trust và 1 quan hệ phân quyền liên miền) để bổ sung vào bộ kiểm thử tự động của Milestone M2 hay không?
6. **SEAMLESS BloodHound parity:**
   Khi can doi chieu, can thiet lap import/reconciliation tren cung snapshot va scope nao de do chenh lech ma khong suy dien parity tu A/B?
