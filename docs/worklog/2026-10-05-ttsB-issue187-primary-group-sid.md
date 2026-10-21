# Worklog - 2026-10-05 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #187, #184, #47 / parser PrimaryGroupSid direct MemberOf fix
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng.
- Nguồn: develop 6fbb410db9b2371fbe6ce3149fe484c2de306da3 (HEAD mới nhất của develop).

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Kiểm chứng Semantics & Legacy | `docs/research/issue-187-primary-group-sid-audit.md` | Đối chiếu AD `primaryGroupID` vs `memberOf`, BloodHound v3 format và mã nguồn BloodHound Legacy 4.0.3 (`newingestion.js` lines 62-68, 162-168); xác nhận `PrimaryGroupSid` là direct `MemberOf` |
| Thẩm định raw SEAMLESS dataset | `data/samples/manifests/seamless-raw-v1.json` | Hash SHA-256 khớp 100%; xác nhận 2.493 Users và 100 Computers có `PrimaryGroupSid`, 0 overlap với `Groups.Members` (13.324); tổng khớp đúng 15.917 cạnh Legacy (`difference = set()`) |
| Pipeline root-cause analysis | `src/parser/builder.py`, `src/parser/inference.py` | Xác định điểm gãy: `_prepare` trong `DirectGraphBuilder` và `_membership_graph` trong `InferenceEngine` bỏ qua trường `PrimaryGroupSid` |
| Parser adapter enhancement | `src/parser/adapters/bloodhound_v3.py` | Thêm `primarygroupsid` và `primary_group_sid` vào `_ID_KEYS` để chuẩn hóa qualified SID |
| Direct graph builder resolution | `src/parser/builder.py` | Xử lý `PrimaryGroupSid` cho User/Computer, kiểm tra SID hợp lệ, chặn integer RID trần, tạo `_EdgeCandidate`, bảo toàn dual provenance khi dedup với `Members[]` |
| Inference engine integration | `src/parser/inference.py` | Bổ sung `_primary_group_entry` vào `_membership_graph` và `evaluate_host_access` để suy diễn đầy đủ transitive admin access |
| Regression & unit test suite | `tests/test_builder_direct.py`, `tests/test_inference.py`, `tests/test_bloodhound_v3_adapter.py`, `tests/test_parser_reconciliation.py` | Bổ sung 11 tests kiểm thử happy path, dedup dual provenance, null/malformed/RID-only policy, unresolvable target, qualified SID, host-access derivation |
| Repository & contract hygiene | `scripts/check_contract.py`, `scripts/check_repository.py`, `ruff`, `yamllint` | Toàn bộ checks đều PASSED, không có cảnh báo hay lỗi cấu trúc |
| Nghiên cứu chi tiết Issue #187 | `docs/research/issue-187-primary-group-sid-audit.md` | Tài liệu phân tích tiếng Việt: phát hiện → ảnh hưởng → xử lý → evidence → giới hạn; sửa links tương đối repo |
| Xử lý review PR #189 (@Lolavine777) | `src/parser/inference.py`, `src/parser/builder.py`, `tests/` | Thống nhất `extract_primary_group_entry()` dùng chung; phát hiện xung đột root vs nested; ưu tiên tất định; thêm 5 regression tests |

## Điều học được / quyết định

1. **Active Directory `primaryGroupID` & BloodHound v3**:
   - `primaryGroupID` là số nguyên RID lưu trong AD object của User/Computer và không sinh ra backlink `memberOf` tương ứng trên LDAP.
   - Collector BloodHound (SharpHound) đã chuyển đổi RID này thành full SID string trong `PrimaryGroupSid`.
   - Contract của `ad-weighted-graph` không cho phép đoán mò prefix domain hay ghép chuỗi; do đó parser chỉ chấp nhận chuỗi SID hợp lệ, từ chối số nguyên RID trần và báo lỗi theo `error-policy`.
2. **Direct Membership Semantics & Unified Extraction**:
   - Quan hệ giữa User/Computer và Primary Group của nó là quan hệ thành viên trực tiếp, phù hợp với định nghĩa `MemberOf` trong ADR-0002 và ADR-0009.
   - Tránh việc parser builder và inference engine xử lý trường dữ liệu này lệch pha: toàn bộ logic trích xuất, kiểm tra SID format, phát hiện xung đột và ưu tiên vị trí được thống nhất qua hàm `extract_primary_group_entry()`.
   - Khi root null và nested `Properties.primarygroupsid` hợp lệ, cả direct graph lẫn inference đều đồng nhất ghi nhận thành viên và thuộc tính provenance.
   - Khi root và nested có giá trị non-null khác nhau, hệ thống phát hiện xung đột và báo lỗi `conflicting PrimaryGroupSid evidence`.
3. **Dedup & Provenance Dual-Sourcing**:
   - Trong trường hợp một User vừa có `PrimaryGroupSid` vừa nằm trong mảng `Members[]` của nhóm (mặc dù SEAMLESS có 0 overlap, nhưng về mặt lý thuyết hoàn toàn có thể xảy ra ở các domain AD khác), builder giữ nguyên 1 cạnh logic duy nhất với ID xác định theo hàm băm `(source, target, "MemberOf")` và gom cả hai bản ghi provenance (`attribute="Members[].MemberId"` và `attribute="PrimaryGroupSid"`).
4. **Bảo toàn phạm vi của Issue #47 và #48**:
   - Issue #187 tập trung giải quyết triệt để coverage gap của `PrimaryGroupSid` cho `MemberOf`.
   - Giữ nguyên `export_complete=false` trong handoff manifest; không tự ý chỉnh sửa comparator để ép kết quả `MATCH`.
   - PR mở ra sẽ dùng `Fixes #187, Refs #47, Refs #184` và không tự ý đóng #47 hay #48.

## Trở ngại và việc kế tiếp

- Toàn bộ các yêu cầu trong review của @Lolavine777 trên PR #189 đã được giải quyết triệt để (blocker shared validation path và secondary docs hygiene).
- Đẩy commit cập nhật lên branch `fix/187-primary-group-sid` và phản hồi trên PR #189.
