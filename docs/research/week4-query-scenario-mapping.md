# Nối các ca kịch bản #206 vào Public Query API Week 4

## Current-state amendment - 09/10/2026

Core, CLI #233, Kerberoasting #230, AS-REP #234 và RBCD #236 đã accepted/merged; baseline tích hợp `be64798c89235f53c5c205894a7bac0f96437ce4`.
Tên AS-REP đã nhận: `asrep_request`, `recover_asrep_secret`, `activate_recovered_identity`; RBCD consume đúng owners/types trong [handoff](rbcd-229.md), một binding/query và delegated service scope.
Các dòng AS-REP/RBCD pending implementation ở bảng ngày 08/10 bên dưới được giữ làm lịch sử.
[SEAMLESS mapping mới](week4-seamless-scenario.md) freeze inputs/oracle trước actual, dùng direct `obtain_admin_execution_on_host` từ canonical AdminTo, không đổi sang synthetic `scenario_winrm_admin`.
Final asset success có thể đạt khi DA checkpoint false; missing/known-false/unrated giữ theo accepted contract.
Scenario đã chạy qua public CLI; B review/cross-reproduction và final acceptance vẫn pending, không ghi CI PASS do billing.

Cập nhật 08/10/2026, Asia/Ho_Chi_Minh.
Nền tích hợp: `develop@f4d1f973ad17d1cb92723bc2243ca85942408762` sau #232, #230 và CLI #233.
Owner: TTS A (@Lolavine777); Reviewer: TTS B (@nairyuuu).
Refs [#206](https://github.com/nairyuuu/ad-weighted-graph/issues/206), [#204](https://github.com/nairyuuu/ad-weighted-graph/issues/204), [#211](https://github.com/nairyuuu/ad-weighted-graph/issues/211), PR [#221](https://github.com/nairyuuu/ad-weighted-graph/pull/221), PR [#214](https://github.com/nairyuuu/ad-weighted-graph/pull/214), PR [#220](https://github.com/nairyuuu/ad-weighted-graph/pull/220), PR [#218](https://github.com/nairyuuu/ad-weighted-graph/pull/218).

Tài liệu này nối các ca kịch bản và oracle độc lập của [#206](https://github.com/nairyuuu/ad-weighted-graph/issues/206) vào Public Query API đã được merge tại PR #221 (`src/engine/query.py`).
Bối cảnh thực thi: PR #221 đã bàn giao query engine adapter; PR #214 đã bàn giao bộ kết quả kỳ vọng độc lập gói A2 v1.0.0; PR #220 đã bàn giao mô hình scoring Week 4.
Issue #206 vẫn mở cho delta raw/query, các kỹ thuật chưa bàn giao và tái lập độc lập; core và Kerberoasting đã có cầu nối thực thi tổng hợp.
Phạm vi của TTS A: định nghĩa inputs, kỳ vọng độc lập, ánh xạ giao diện và bằng chứng kiểm chứng; không nhận phần việc triển khai engine của B (#212, #213, #215, #216).

## 1. Tách biệt máy xuất phát, danh tính dùng được và phạm vi xác thực

Kiến trúc query Week 4 phân tách ba khái niệm độc lập ở boundary:
- `source_foothold`: Điểm đứng chân ban đầu (Computer node).
- `initial_actor`: Chủ thể thực hiện hành động (User hoặc Computer).
- `usable_identity`: Danh tính Active Directory có thể dùng được, dạng cặp `(principal, authentication_context)`.
- `authentication_context`: Máy chủ hoặc phạm vi ngữ cảnh xác thực hiện hành của phiên làm việc.

Nguyên tắc bất biến:
- Kiểm soát máy (`control(Computer)`) không tự suy ra quyền danh tính người dùng miền (`usable_identity(User)`).
- Nếu máy xuất phát là Computer và actor là User, hệ thống bắt buộc phải có khai báo `usable_identity` hoặc `control` tường minh; vi phạm sẽ bị reject ngay lập tức bằng `ValueError`.
- Danh tính chỉ có hiệu lực trong đúng `authentication_context` được cấp.
- Khi truy vấn chạy trong ngữ cảnh máy khác (`authentication_context` không khớp), hành động đòi xác thực bị chặn (blocked) và hệ thống không tìm thấy đường.

Bảng ánh xạ các ca ngữ nghĩa:

| Mã ca #206 | Input Query API | Kỳ vọng thực thi | Trạng thái kiểm chứng |
| --- | --- | --- | --- |
| W4-X/S (thay nguồn) | `source_foothold="OtherHost"`, `initial_actor="Alice"`, không khai báo usable identity | `materialize_query` raise `ValueError` ("without declared usable_identity or control") | Đạt trong `test_source_computer_usable_identity_and_auth_context_separation` |
| W4-X/I (bỏ usable identity) | `source_foothold="OtherHost"`, `initial_actor="OtherHost"`, `initial_state={"control": ["OtherHost"]}` | Tìm kiếm từ Computer không thể actor-switch sang Alice; 0 paths sinh ra; status `no_path` | Đạt trong `test_source_computer_usable_identity_and_auth_context_separation` |
| W4-X/H (sai context) | `source_foothold="OtherHost"`, `usable_identity=[["Alice", "Host"]]`, `authentication_context="OtherHost"` | Alice chỉ usable tại Host; chạy tại OtherHost bị blocked; 0 paths; status `blocked` | Đạt trong `test_source_computer_usable_identity_and_auth_context_separation` |
| W4-X/H-valid (đúng context) | `source_foothold="OtherHost"`, `usable_identity=[["Alice", "Host"]]`, `authentication_context="Host"` | Khớp authentication context; sinh đủ 3 đường hợp lệ; status `success` | Đạt trong `test_source_computer_usable_identity_and_auth_context_separation` |

## 2. Tách biệt DA checkpoint và mục tiêu tài sản cuối

Đạt được quyền Domain Admin (DA checkpoint) không đồng nghĩa với việc chiếm quyền kiểm soát tài sản mục tiêu cuối cùng (Host/DC):
- `checkpoint_goal`: Mục tiêu trung gian (ví dụ đạt `effective_member(Alice, Admins)`).
- `target_goal`: Mục tiêu tài sản cuối (ví dụ đạt `admin_control(Host)`).
- `checkpoint_reached`: Trạng thái đạt mục tiêu trung gian trong quá trình tìm kiếm.
- `final_goal_reached`: Trạng thái đạt mục tiêu tài sản cuối cùng.

Hành vi đánh giá kết quả của Public Query API hiện tại (`src/engine/query.py`):
- `status="success"` phản ánh việc đạt được mục tiêu tài sản cuối cùng (`final_goal_reached=True`), tức là tìm được ít nhất một đường dẫn hợp lệ tới đích (`len(paths) > 0`).
- `checkpoint_reached` được đánh giá và báo cáo độc lập: mang giá trị `True` nếu trạng thái khởi tạo, bất kỳ bước trung gian nào trong các đường tìm được, hoặc bất kỳ bước thử nghiệm hợp lệ nào đạt được predicate của `checkpoint_goal`.
- Khi mục tiêu tài sản cuối cùng đạt được trực tiếp mà không cần đi qua checkpoint (hoặc cổng checkpoint bị chặn/chưa đạt): query trả về `status="success"`, `final_goal_reached=True`, `checkpoint_reached=False`.
- Khi checkpoint đạt được nhưng mục tiêu tài sản cuối cùng thất bại:
  - Nếu cổng tài sản cuối bị chặn bởi dữ kiện false (ví dụ `admin_channel=False`): `checkpoint_reached=True`, `final_goal_reached=False`, status là `checkpoint_reached_final_goal_blocked`.
  - Nếu cổng tài sản cuối bị thiếu dữ kiện (ví dụ `admin_channel` vắng mặt và không có assumption): `checkpoint_reached=True`, `final_goal_reached=False`, status là `checkpoint_reached_final_goal_indeterminate`.
- Làm rõ ràng buộc kiến trúc: DA checkpoint là mốc đặc quyền cao hoặc đường rẽ nhánh thay thế, không phải là điều kiện tiên quyết bắt buộc mọi đường dẫn tới tài sản đích đều phải đi qua.
Các đường tấn công trực tiếp hoặc leo quyền cục bộ (như Direct AdminTo, local admin, lateral movement hoặc ủy quyền dịch vụ) có thể đạt mục tiêu tài sản mà không cần qua Domain Admins.
API query báo cáo tách bạch độc lập giữa `checkpoint_reached` và `final_goal_reached` theo đúng thiết kế.

Bảng ánh xạ các ca checkpoint và asset goal:

| Mã ca #206 | Thiết lập cổng tài sản và checkpoint | Checkpoint reached | Final goal reached | Status trả về |
| --- | --- | --- | --- | --- |
| W4-C/F | Checkpoint đạt, `admin_channel=False` (authoritative false) | True | False | `checkpoint_reached_final_goal_blocked` |
| W4-C/U | Checkpoint đạt, `admin_channel` thiếu (missing without assumption) | True | False | `checkpoint_reached_final_goal_indeterminate` |
| W4-DA-positive | Checkpoint đạt, `admin_channel=True` (authoritative true / valid assumption) | True | True | `success` |
| W4-DA-negative-asset-positive | Checkpoint bị chặn (`membership_usable=False`), đường Direct AdminTo thành công | False | True | `success` |

## 3. Xử lý thiếu dữ kiện, giả định kịch bản và phủ quyết dữ kiện false

Quy tắc giải quyết dữ kiện và giả định tuân thủ hợp đồng Week 4:
- Thiếu dữ kiện (missing fact): Không tự động gán true hoặc false; kết quả chuyển tiếp là `INDETERMINATE`; trạng thái toàn cục là `indeterminate`.
- Giả định hợp lệ (valid declared assumption): Cần có đầy đủ `scope`, `rationale`, và nguồn gốc truy vết (`provenance_reference` hoặc metadata `declared_by`/`source`).
Hệ thống chấp nhận giả định trong chế độ `scenario` và cho phép sinh đường tấn công có điều kiện.
- Dữ kiện đã biết false (known-false veto): Dữ kiện có nguồn gốc xác thực (observed/blocked) mang giá trị `False` sẽ phủ quyết tuyệt đối giả định mang giá trị `True` trong cùng phạm vi truy vấn.
Giả định bị từ chối được lưu trong sổ cái `rejected_assumptions` của `MaterializedQuery` với lý do `known_false_veto` và giữ nguyên liên kết tới dữ kiện phủ quyết.
Dữ kiện trong `RuntimeContext` duy trì giá trị `False`, chặn đứng bước chuyển tiếp (`status="blocked"`).

Bảng ánh xạ các ca U/A/F và conflict:

| Mã ca #206 | Tình huống dữ kiện | Xử lý trong Query API | Kết quả thực thi |
| --- | --- | --- | --- |
| W4-G/U | Thiếu `winrm_available`, không có assumption | Cổng chuyển tiếp trả về `Status.INDETERMINATE`; ghi nhận predicate thiếu | `status="indeterminate"`, `final_goal_reached=False` |
| W4-G/A | Giả định `winrm_available=True` hợp lệ | Giả định được chấp nhận vào context; sinh đường thành công dưới giả định | `status="success"`, `final_goal_reached=True`, 1 path |
| W4-G/F | Dữ kiện xác thực `winrm_available=False` | Cổng chuyển tiếp bị chặn do điều kiện sai | `status="blocked"`, `final_goal_reached=False` |
| W4-G/conflict | Dữ kiện xác thực `False` cùng giả định `True` | Phủ quyết giả định; ghi nhận `rejected_assumptions` với lý do `known_false_veto`; context giữ `False` | `status="blocked"`, `len(rejected_assumptions) == 1` |

## 4. Người dùng thay đổi đầu vào và hệ thống tự động tìm đường

Public Query API nhận đặc tả bài toán (`AttackQuery`) chứ không nhận chuỗi bước định trước (`ordered paths` hay `steps`):
- Khi người dùng thay đổi khả năng ban đầu (`initial_state`): Hệ thống tự động thích ứng tập đường sinh ra và bảo toàn exact oracle từ gói kỳ vọng #214 (`week4-v1.json`).
  - W4-M (S0: chỉ có quyền kiểm soát Alice): Khớp chính xác tập chữ ký chuyển tiếp `(technique_id, actor, source, target)` của 3 acceptable paths `[['direct'], ['member', 'direct'], ['member', 'inherited']]`; khớp toàn bộ tập trạng thái đạt được `{S0, S1, S2, S3}`; `complete=True`.
  - W4-I/E (S1: có thêm quyền thành viên nhóm Admins): Khớp chính xác 4 acceptable paths `[['direct'], ['inherited'], ['member', 'direct'], ['member', 'inherited']]`; khớp tập trạng thái đạt được `{S1, S3}`; `complete=True`.
  - W4-I/H (chỉ có quyền kiểm soát OtherHost): Không có quyền Alice nên hành động bị chặn; 0 paths sinh ra (`status="blocked"`); tập trạng thái đạt được là `{"admin_control": ["OtherHost"]}`; `complete=True`.
- Khi người dùng thay đổi đích đến (`target` và `target_goal`):
  - W4-TARGET (đích đổi sang OtherHost): Alice không có đường tới OtherHost; 0 paths sinh ra (`status="no_path"`); toàn bộ tập trạng thái đạt được vẫn duyệt đủ `{S0, S1, S2, S3}`; `complete=True`.
- Giới hạn ngân sách tìm kiếm (Search Budget Caps):
  - Khi đặt `max_paths=1`: Hệ thống dừng sớm, trả về 1 đường, đánh dấu `truncated=True`, `complete=False`, `truncation_reason="path_limit_reached"`.
  Kiểm chứng độc lập chứng minh tìm kiếm bị cắt không đảm bảo tìm thấy đường có chi phí nhỏ nhất (bỏ sót đường M/I).
  - Khi mục tiêu đòi hỏi nhiều bước nhưng bị giới hạn `max_steps=1`: Không tìm thấy đường, trả về `status="truncated"`, không bao giờ được kết luận sai thành `no_path` hay `blocked`.

## 5. Rà soát AS-REP Roasting, Kerberoasting và RBCD theo Handoff #218

Tham chiếu tài liệu bàn giao nghiên cứu mở rộng [week4-extension-scenario-handoff.md](week4-extension-scenario-handoff.md) (PR #218):
TTS A đã bàn giao toàn bộ cơ chế ngữ nghĩa, ma trận ca kiểm thử, và kỳ vọng độc lập.
Kerberoasting đã tích hợp qua #230; AS-REP (#228) và RBCD (#229) còn chờ B triển khai. Tên cơ chế nghiên cứu trong handoff không tự trở thành owner ID của API.

Bảng rà soát trạng thái từng kỹ thuật:

| Kỹ thuật | Ca đã chuẩn bị đầy đủ bởi TTS A | Ca/thành phần còn thiếu | Trạng thái giao diện kỹ thuật |
| --- | --- | --- | --- |
| AS-REP Roasting | 12 ca độc lập: A-P (positive), A-PRE-F/U, A-KDC-F/U, A-REC-F/U, A-AUTH-F/U, A-ASSET-F/U, A-SECRET, A-IDENTITY, A-CONTEXT, A-VETO, A-EXT-OFF | Chưa có kỹ thuật trong catalog (`obtain_asrep_roast_material`, `recover_asrep_secret`, `activate_asrep_identity`); chưa có quy tắc chuyển tiếp trạng thái | PENDING B (#228, chưa có chương trình thực thi) |
| Kerberoasting | K-OVERLAP, K-NO-AUTH, K-MATERIAL, K-FACT và KDC/auth cutoffs | Owner IDs `kerberoast_request`, `recover_ticket_secret`, `activate_recovered_identity`; snapshot fact view SPN đã bàn giao | Đã sinh/đối chiếu chuỗi tổng hợp trên nền #230; C/P/I unrated, raw replay của A còn mở |
| RBCD | 12 ca độc lập: R-P (positive 3 programs, 8 states), R-RESET-F, R-WRITE-F/U, R-SPN-F/U, R-KEY-U, R-POLICY-F, R-DELEGATE-U, R-ASSET-F/U, R-REUSE-M, R-SCOPE, R-CF-ACL, R-EXT-OFF | Chưa có kỹ thuật trong catalog (`write_rbcd_descriptor`, `delegate_rbcd_service_ticket`); chưa có delegated service context semantics | PENDING B (#229, chưa có chương trình thực thi) |

Kiểm chứng fail-closed:
Trạng thái PENDING là phân định tại baseline handoff #218 chứ không phải bất biến bắt buộc `load_catalog()` hiện hành phải vắng mặt các kỹ thuật mở rộng (Kerberoasting đã được tích hợp tại #230).
Khi truyền một technique ID không tồn tại hoặc chưa được hỗ trợ vào `allowed_techniques`, query validator từ chối fail-closed ngay lập tức với lỗi `ValueError: unknown technique IDs in allowed_techniques`.
Cơ chế kiểm chứng fail-closed này bảo vệ tính toàn vẹn của engine, ngăn chặn việc giả lập hành vi thành công khi kỹ thuật chưa được kiểm chứng, đồng thời không áp đặt giả định sai lên catalog active khi B phát triển các kỹ thuật mới.

## 6. Ma trận tiêu chí nghiệm thu #206 và phân định ranh giới A/B

Bảng đối chiếu tiêu chí nghiệm thu của Issue #206:

| Tiêu chí nghiệm thu #206 | Phần đã đạt (TTS A) | Phần còn phụ thuộc (TTS B) | Đánh giá trạng thái |
| --- | --- | --- | --- |
| 1. Tập đường và trạng thái kỳ vọng trên đồ thị nhỏ | Đã đối chiếu exact path sets, chữ ký chuyển tiếp và tập reachable states {S0, S1, S2, S3} với oracle #214; đã kiểm chứng qua `test_week4_query_scenario_mapping.py` | Min-Effort và hai hồi quy #212 đã kiểm qua public API sau #232 | Đạt synthetic core; raw/delta còn mở |
| 2. Ma trận reuse/gap và expected-data | Gói expected A2 v1.0.0 đã merge qua PR #214; ma trận mapping API hoàn thiện tại tài liệu này | B nghiệm thu tích hợp end-to-end | Đạt phần A |
| 3. Tách biệt false, unknown, missing và unsupported | Đã kiểm chứng đầy đủ U/A/F và known-false veto qua Query API và sổ cái `rejected_assumptions` | Fact store #215 đã bàn giao; Kerberoasting dùng typed SPN facts | Đạt synthetic; raw runtime còn mở |
| 4. Giả định synthetic tường minh, dữ liệu thật có provenance | Đầy đủ metadata `declared_by`, `rationale`, `scope`, và `provenance_reference` cho assumptions | Gói dữ liệu runtime production của engine | Đạt phần A |
| 5. Bàn giao SEAMLESS và xử lý thiếu dữ kiện | Raw snapshot digest và 3 structural bindings lịch sử đã xác minh; trace A trên nền mới chưa chạy do raw riêng tư vắng mặt | Fact resolver/probe đã có; cần đầu vào được phép và independent replay | Đạt phần A; pending runtime |
| 6. Reachability không phụ thuộc C/P/I | Toàn bộ kiểm chứng đường đi chỉ dựa trên quyền và trạng thái, hoàn toàn độc lập với chi phí đánh giá | Mô hình scoring tách biệt tại PR #220 | Đạt |
| 7. Nguồn gốc cơ chế và ranh giới bất biến | Đầy đủ trích dẫn kỹ thuật (AdminTo, Access Tokens, WinRM Security); manifest SHA-256 v1.0.0 bất biến | B bảo toàn tính toàn vẹn khi tích hợp CLI | Đạt |
| 8. CI checks và kiểm thử tự động | Test suite `tests/test_week4_query_scenario_mapping.py` chạy qua 100% trong môi trường chuẩn | B review PR và CI kiểm tra | Đạt phần A |

Kết luận ranh giới:
A đã nối core/scoring và các ca Kerberoasting tổng hợp vào API hiện tại, giữ expected độc lập trong `tests/fixtures/ranking/week4_acceptance_oracle.json`.
Hai hồi quy adapter/zero-action đã đạt oracle; zero-work là semantic disposition, không là canonical P/I assessment.
Đối chứng K-OVERLAP giữ cùng input/caps, chỉ đổi allowed techniques; cả hai có witness tới cùng tài sản. Extension truncated do step limit nên không claim exhaustive coverage.
CLI #233 đã merge với schema 0.2; A chạy W4-CLI-PACKAGE qua subprocess, đối chiếu exact paths/reachable states từ week4-v1 và C/P/I từ Ledger E, kiểm stdout/output, compare hai process và malformed inputs. Source/runtime từng process ghi riêng khỏi semantic payload. AS-REP #228 và RBCD #229 còn thuộc B; private/SEAMLESS và human cross-reproduction giữ pending.
#206/#208 tiếp tục mở cho delta mappings/raw query, trace riêng tư được phép và cross-reproduction của người còn lại. Báo cáo hiện chỉ nhận scoped synthetic results.

## 7. Lệnh kiểm tra và tái lập

Thực thi kiểm tra toàn bộ suite liên quan từ root repository bằng Python trong môi trường ảo `.venv`:

```bash
# 1. Kiểm tra tính toàn vẹn manifest gói A2 v1.0.0
sha256sum -c tests/fixtures/attack_scenarios/week4-v1.sha256

# 2. Chạy kiểm thử nối kịch bản #206 vào Query API
.venv/bin/python -m pytest -v tests/test_week4_query_scenario_mapping.py

# 3. Chạy toàn bộ các test suites của Week 4
.venv/bin/python -m pytest -q tests/test_week4_query_scenario_mapping.py \
  tests/test_week4_scenarios.py \
  tests/test_week4_query_materialization.py \
  tests/test_query_boundary_regressions.py \
  tests/test_week4_scoring.py

# 4. Kiểm tra hợp đồng và tiêu chuẩn mã nguồn
.venv/bin/python scripts/check_repository.py
.venv/bin/python scripts/check_contract.py
```
