# Nghiên cứu & Kiểm chứng Issue #187: Xử lý PrimaryGroupSid và Gap Direct MemberOf

- **Mục tiêu**: Kiểm chứng độc lập giả thuyết về `PrimaryGroupSid` được báo cáo trong PR #184 / Issue #187, phân tích nguyên nhân gốc trong pipeline của `ad-weighted-graph`, triển khai giải pháp parser/inference tuân thủ contract, kiểm thử hồi quy và đối chiếu với snapshot SEAMLESS.
- **Phạm vi**: Parser adapter, DirectGraphBuilder, InferenceEngine, regression tests, tài liệu kiểm chứng.
- **Quy tắc an toàn**: Không đưa định danh thực (authentic AD SIDs, real hostnames, raw credentials, PII) vào báo cáo; sử dụng canonical digests, generic labels và sanitized representations.

---

## 1. Phát hiện (Findings)

### 1.1. Đối chiếu Semantics Microsoft Active Directory & BloodHound Legacy

1. **Active Directory `primaryGroupID` vs `memberOf`**:
   - Trong kiến trúc Microsoft Active Directory (Windows NT / 2000 trở đi), mỗi tài khoản User hoặc Computer đều có một thuộc tính số nguyên `primaryGroupID` (chỉ chứa RID, ví dụ `513` cho Domain Users, `515` cho Domain Computers, `516` cho Domain Controllers).
   - Vì lý do hiệu năng và tương thích ngược của POSIX/Mac OS clients, Windows SAM/AD **không** lưu Primary Group trong thuộc tính backlink `memberOf` của đối tượng User/Computer (xem tài liệu Microsoft [MS-ADTS] section 3.1.1.4.5.19 `memberOf` và KB275523).
   - Thuộc tính `memberOf` trên LDAP chỉ phản ánh các group membership thông thường (ngoài primary group).

2. **Cấu trúc BloodHound v3 JSON**:
   - Khi BloodHound collector (SharpHound) thu thập thông tin User và Computer, collector đọc `primaryGroupID` (RID) từ LDAP, ghép với Domain SID của object để tạo thành full SID hoàn chỉnh của nhóm chính, và lưu vào trường `PrimaryGroupSid` (chuỗi SID dạng `S-1-5-21-...-513`).
   - Trường này xuất hiện ở root của record hoặc trong `Properties.primarygroupsid`.

3. **Xử lý của BloodHound Legacy (bản pinned 4.0.3)**:
   - Truy nguyên mã nguồn `newingestion.js` (BloodHound Legacy 4.0.3, dòng 62-68 và 162-168):
     ```javascript
     if (user.PrimaryGroupSid) {
         driver.createRelationship(user.ObjectIdentifier, user.PrimaryGroupSid, "MemberOf", ...);
     }
     ...
     if (computer.PrimaryGroupSid) {
         driver.createRelationship(computer.ObjectIdentifier, computer.PrimaryGroupSid, "MemberOf", ...);
     }
     ```
   - BloodHound Legacy trực tiếp bổ sung quan hệ `(User) -[:MemberOf]-> (Group)` và `(Computer) -[:MemberOf]-> (Group)` từ `PrimaryGroupSid`.
   - Do đó, trong đồ thị Neo4j của Legacy 4.0.3, các quan hệ xuất phát từ `PrimaryGroupSid` được lưu trữ dưới dạng quan hệ trực tiếp `MemberOf`.

4. **Tuân thủ Architectural Decision Records (ADR)**:
   - Theo ADR-0002 và ADR-0009: quan hệ `MemberOf` trong contract đồ thị cấu trúc chỉ biểu diễn **membership trực tiếp** (direct membership), có hướng xác định từ thành viên đến nhóm (`Member -> Group`).
   - Việc User/Computer trực thuộc Primary Group là một quan hệ thành viên trực tiếp trong Active Directory (chính là primary group membership).
   - Theo mô hình phân quyền và an toàn thông tin: thành viên của một Group (kể cả Primary Group) chỉ kế thừa các quyền (rights/ACEs) mà Group đó nắm giữ; việc là member không tự động suy ra quyền khai thác nếu nhóm không có privilege hay local access.

### 1.2. Truy nguyên Pipeline ad-weighted-graph

Kiểm tra luồng dữ liệu từ raw files đến canonical graph trong `src/parser`:

```
Raw JSON Files (users.json, computers.json)
       │
       ▼
src/parser/loader.py: BloodHoundLoader
   - Đọc bản ghi, giữ nguyên `PrimaryGroupSid` trong Record.properties.
       │
       ▼
src/parser/adapters/bloodhound_v3.py: BloodHoundV3Adapter
   - Thiếu "primarygroupsid" / "primary_group_sid" trong `_ID_KEYS`
     -> không chuyển đổi domain-qualified SID nếu gặp format tiền tố.
       │
       ▼
src/parser/normalizer.py: IdentityNormalizer
   - Nhận diện User/Computer và Group, chuyển giao properties nguyên vẹn.
       │
       ▼
src/parser/builder.py: DirectGraphBuilder._prepare()
   - [ĐIỂM GÃY CHÍNH]: Phương thức `_prepare()` chỉ duyệt qua các collection
     như `Aces`, `Members`, `AllowedToDelegate`, `HasSIDHistory`.
   - Hoàn toàn KHÔNG kiểm tra trường `PrimaryGroupSid` trên User hay Computer.
   - Hậu quả: Toàn bộ thông tin `PrimaryGroupSid` bị bỏ rơi, không được tạo candidate edge.
       │
       ▼
src/parser/inference.py: InferenceEngine
   - Phương thức `_membership_graph` chỉ đọc `Members[]` từ Group.
   - Khi `evaluate_host_access` tính toán quyền admin cục bộ gián tiếp qua nhóm,
     các thành viên thông qua Primary Group bị bỏ sót hoàn toàn khỏi membership closure.
```

---

## 2. Ảnh hưởng (Impact)

### 2.1. Định lượng trên Snapshot SEAMLESS (`seamless-raw-v1`)

Đã tiến hành thẩm định độc lập trên snapshot SEAMLESS có hash SHA-256 khớp 100% với manifest `seamless-raw-v1.json`:
- **Số lượng Users**: 2.493 bản ghi User. Toàn bộ 2.493 Users đều có trường `PrimaryGroupSid` hợp lệ (trỏ đến Group tồn tại trong tập dữ liệu thu thập).
- **Số lượng Computers**: 100 bản ghi Computer. Toàn bộ 100 Computers đều có trường `PrimaryGroupSid` hợp lệ.
- **Tập cạnh MemberOf từ Groups.Members**: Chính xác 13.324 cạnh.
- **Độ giao thoa (Overlap)**: Kiểm tra tập hợp giữa `(source, target)` từ `Groups.Members` và `(source, PrimaryGroupSid)`:
  $$\text{Overlap} = \emptyset \quad (\text{đúng 0 cạnh giao thoa})$$
  Lý do: Active Directory không ghi nhận Primary Group vào thuộc tính `member` của nhóm hay `memberOf` của user. Collector chỉ thu thập danh sách `Members` từ LDAP `member` attribute của Group, nên các thành viên chỉ có Primary Group ID sẽ không nằm trong mảng `Members` của Group đó.
- **Tổng số cạnh MemberOf sau khi xử lý**:
  $$13.324 + 2.493 + 100 = 15.917 \text{ cạnh}$$
- **So khớp với Baseline Legacy 4.0.3**:
  - Legacy 4.0.3 count: 15.917 cạnh `MemberOf`.
  - Project count sau khi fix: 15.917 cạnh `MemberOf`.
  - Phép trừ tập hợp: $\text{Set}_{\text{Legacy}} \setminus \text{Set}_{\text{Project}} = \emptyset$ và $\text{Set}_{\text{Project}} \setminus \text{Set}_{\text{Legacy}} = \emptyset$.
  - Khớp 100% tập hợp cạnh có hướng.

### 2.2. Đánh giá ảnh hưởng tới các Edge Kinds khác và Inference

- **Trên snapshot SEAMLESS**:
  - Trong snapshot SEAMLESS, các Primary Group (như Domain Users RID 513) không được gán quyền local administrator hoặc remote access privileges trực tiếp trên các host máy chủ.
  - Do đó, số lượng cạnh `AdminTo` (9), `CanPSRemote` (2), `CanRDP` assessments (3), `GenericAll` (37.044), `WriteDacl` (3.395) **hoàn toàn giữ nguyên**, không bị biến động ngoài ý muốn.
- **Trên mô hình suy diễn tổng quát (Generalized Inference)**:
  - Khi một Primary Group (hoặc nhóm lồng phía trên Primary Group) được cấp quyền local admin trên Computer (ví dụ gán vào local Administrators group), việc bổ sung `PrimaryGroupSid` vào `_membership_graph` đảm bảo User/Computer đó được suy diễn chính xác quyền `AdminTo` với đầy đủ các bước giải trình (derivation steps) trong provenance audit.

---

## 3. Xử lý (Implementation)

### 3.1. Cập nhật Parser Adapter
Tại [src/parser/adapters/bloodhound_v3.py](../../src/parser/adapters/bloodhound_v3.py):
- Bổ sung `"primarygroupsid"` và `"primary_group_sid"` vào tập khóa định danh `_ID_KEYS` để adapter nhận diện và chuẩn hóa SID nếu có tiền tố domain (`DOMAIN-S-1-5-...`).

### 3.2. Cập nhật DirectGraphBuilder & InferenceEngine qua Shared Validation Path
Tại [src/parser/inference.py](../../src/parser/inference.py) và [src/parser/builder.py](../../src/parser/builder.py):
- Chuẩn hóa việc trích xuất và xác thực qua hàm dùng chung `extract_primary_group_entry(data, record_kind=...)`.
- Thu thập cả hai vị trí: root-level (`PrimaryGroupSid`) và nested (`Properties.primarygroupsid`).
- Xác thực loại record: chỉ chấp nhận khi record kind là `"User"` hoặc `"Computer"`.
- Kiểm tra kiểu dữ liệu: từ chối các giá trị số nguyên RID trần (ví dụ `513`), tuân thủ contract không tự tiện suy diễn domain suffix để ghép SID.
- Kiểm tra SID format thông qua `_is_plausible_group_sid` kết hợp `is_valid_sid`, `parse_scoped_sid`, `boundary_group`, `parse_qualified_sid`.
- Phát hiện xung đột (conflict detection): nếu cả root và nested đều có giá trị non-null nhưng khác nhau, hàm lập tức báo lỗi xung đột (`conflicting PrimaryGroupSid evidence in record`).
- Chọn thuộc tính bảo toàn provenance một cách tất định (deterministic precedence): ưu tiên root-level attribute nếu có (`"PrimaryGroupSid"`), nếu root null thì dùng nested attribute (`"Properties.primarygroupsid"`).
- Khởi tạo `_EdgeCandidate("MemberOf", record.id, target_ref, record.kind, "Group", field_name, value, record_id)`.
- **Dedup và Provenance Multiplicity**:
  - Khi một đối tượng vừa xuất hiện trong `Groups.Members` vừa có `PrimaryGroupSid`, cơ chế hash canonical edge ID `sha256(source, target, "MemberOf")` sẽ gộp thành một cạnh duy nhất trong đồ thị.
  - Danh sách `EdgeProvenance` của cạnh được tự động bảo toàn cả hai nguồn: `attribute="Members[].MemberId"` và `attribute="PrimaryGroupSid"` (hoặc `"Properties.primarygroupsid"`).
- **Đồng bộ với Host-Access Inference**:
  - `InferenceEngine._membership_graph()` và `evaluate_host_access()` dùng chung `extract_primary_group_entry()`.
  - Không còn hiện tượng lệch pha (inconsistency): nếu root null và nested valid, cả direct graph lẫn inference đều nhận diện; nếu conflicting, cả hai đều phát hiện xung đột và từ chối.

---

## 4. Bằng chứng kiểm chứng (Evidence)

### 4.1. Unit & Regression Test Suite
Đã bổ sung 11 unit & regression tests chuyên sâu:
1. `test_user_primary_group_sid_creates_memberof`: Happy path cho User -> Primary Group.
2. `test_computer_primary_group_sid_creates_memberof`: Happy path cho Computer -> Primary Group.
3. `test_primary_group_sid_dedup_with_members_array_preserves_provenance`: Kiểm tra dedup khi có đồng thời trong `Members[]` và `PrimaryGroupSid`, chứng minh bảo toàn 2 provenance records với 2 thuộc tính nguồn khác nhau.
4. `test_primary_group_sid_null_or_empty_ignored`: Kiểm tra field null/rỗng được bỏ qua an toàn.
5. `test_primary_group_sid_malformed_string_policy`: Kiểm tra xử lý `fail_fast` và `skip_and_log` khi SID sai cú pháp.
6. `test_primary_group_sid_integer_rid_rejected`: Chứng minh không chấp nhận integer RID trần theo contract.
7. `test_primary_group_sid_wrong_record_kind_ignored`: Chứng minh bỏ qua nếu field xuất hiện trên Group/Domain.
8. `test_primary_group_sid_unresolvable_target_policy`: Kiểm tra behavior khi target group không nằm trong snapshot.
9. `test_bloodhound_v3_adapter_primary_group_sid_qualified`: Kiểm tra adapter chuẩn hóa qualified SID.
10. `test_reconciliation_primary_group_sid_conflict_handling`: Kiểm tra va chạm dữ liệu giữa các record trùng lặp.
11. `test_evaluate_host_access_infers_admin_via_primary_group`: Kiểm tra suy diễn quyền `AdminTo` và derivation step qua `PrimaryGroupSid`.

### 4.2. Kết quả kiểm tra toàn hệ thống (Repository Suite)
- `python -m pytest`: Toàn bộ 1.649 unit & integration tests đều PASSED (không có regression).
- `python -m ruff check .`: PASSED (zero lint errors).
- `python -m ruff format --check .`: PASSED (zero format diffs).
- `python scripts/check_contract.py`: PASSED (tuân thủ contract schemas).
- `python scripts/check_repository.py`: PASSED (tuân thủ repo hygiene, không có file thừa hay vi phạm).
- `python -m yamllint .`: PASSED.

---

## 5. Giới hạn & Quyết định bảo toàn (Scope & Governance Limitations)

1. **Không can thiệp cờ `export_complete` của Comparator**:
   - `export_complete` trong `seamless-legacy-403-reconciliation-handoff.json` vẫn giữ nguyên giá trị `false`.
   - Theo phân công phân nhiệm giữa các issue: Issue #187 chịu trách nhiệm kiểm chứng và khắc phục parser coverage gap cho `PrimaryGroupSid`. Việc kết luận tương đương toàn bộ (MATCH) thuộc thẩm quyền của Issue #47 sau khi đã thẩm định đầy đủ 15 observed kinds (bao gồm 10 cạnh chênh lệch của `GenericAll`).
2. **Không đóng các Issue mức tổng thể**:
   - PR mở ra sẽ dùng cú pháp `Fixes #187, Refs #47, Refs #184`.
   - Tuyệt đối không đóng #47 hay #48.
3. **Bảo mật dữ liệu (Data Sanitization)**:
   - Toàn bộ commit message, tài liệu và PR description đều sử dụng sanitized representations, generic names và SHA-256 digests; không có bất kỳ tên miền nội bộ, SID nguyên bản hay thông tin nhạy cảm nào bị đưa lên repository công khai.
