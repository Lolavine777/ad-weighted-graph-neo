# Worklog - 2026-10-07 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#206](https://github.com/nairyuuu/ad-weighted-graph/issues/206), [#204](https://github.com/nairyuuu/ad-weighted-graph/issues/204) / Nhánh `docs/206-week4-query-mapping` -> `develop`, reviewer yêu cầu `nairyuuu` / M3, Week 4.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.
- Baseline: `develop@7f2fd72` sau khi merge PR #221 (`feat/211-week4-query-materialization`), PR #220 (`docs/207-week4-scoring-handoff`), PR #218 (`docs/200-extension-scenario-handoff`), PR #214 (`docs/206-week4-scenarios`).

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Cập nhật baseline develop | `git fetch origin develop && git checkout develop && git merge --ff-only origin/develop` | Đồng bộ sạch với `7f2fd72`; kiểm tra log xác nhận #221, #220, #218, #214 đã merge |
| Kiểm tra toàn bộ test suite nền | `.venv/bin/python -m pytest -q` | 1.892 passed, 1 skipped (Windows junction), 48 subtests passed trong 124,14s |
| Kiểm tra tính toàn vẹn manifest gói A2 | `sha256sum -c tests/fixtures/attack_scenarios/week4-v1.sha256` | 17/17 tập tin khớp mã băm SHA-256 hoàn hảo |
| Xây dựng test suite nối kịch bản #206 vào Query API | `tests/test_week4_query_scenario_mapping.py` | 5 bài kiểm thử bao phủ toàn bộ 5 nhóm yêu cầu của Issue #206 |
| Kiểm chứng tách biệt máy xuất phát và danh tính | `test_source_computer_usable_identity_and_auth_context_separation` | Kiểm chứng 4 ca: Computer foothold thiếu usable identity bị reject; sai authentication context bị blocked (0 paths); đúng context sinh đủ 3 paths; chỉ có Computer foothold trả về `no_path` |
| Kiểm chứng tách biệt DA checkpoint và mục tiêu tài sản | `test_da_checkpoint_reached_separated_from_asset_target` | Kiểm chứng 4 ca: cổng tài sản blocked (`checkpoint_reached_final_goal_blocked`); cổng tài sản missing (`checkpoint_reached_final_goal_indeterminate`); cả hai đạt (`success`); và tài sản đạt trực tiếp khi checkpoint bị chặn (Case 4: `checkpoint_reached=False`, `final_goal_reached=True`, `status="success"`) |
| Kiểm chứng U/A/F và known-false veto có sổ cái giải thích | `test_missing_facts_vs_valid_assumptions_vs_known_false_veto` | Kiểm chứng 4 ca: thiếu fact trả về `indeterminate`; assumption hợp lệ trả về `success`; fact false trả về `blocked`; fact false phủ quyết assumption true và ghi nhận vào sổ cái `rejected_assumptions` với lý do `known_false_veto` |
| Kiểm chứng người dùng thay đổi đầu vào hệ thống tự tìm đường | `test_dynamic_search_driven_by_user_input_changes` | Tiêu thụ trực tiếp gói kỳ vọng #214 (`week4-v1.json`); đối chiếu exact transition signatures `(technique_id, actor, source, target)` với `acceptable_paths`; đối chiếu tập reachable states `{S0, S1, S2, S3}` cho W4-M; `{S1, S3}` cho W4-I/E; OtherHost cho W4-I/H; `{S0..S3}` cho W4-TARGET; và kiểm chứng các giới hạn ngân sách (`truncated=True`, `complete=False`) |
| Kiểm chứng validator từ chối fail-closed kỹ thuật chưa hỗ trợ | `test_query_validator_fails_closed_on_unsupported_techniques` | Sử dụng ID kỹ thuật không tồn tại để kiểm chứng fail-closed bằng `ValueError`; không ép buộc catalog active phải vắng mặt các kỹ thuật mở rộng sắp được triển khai |
| Soạn thảo tài liệu đặc tả ánh xạ kịch bản | `docs/research/week4-query-scenario-mapping.md` | Bảng ma trận ánh xạ, phân tích AS-REP/Kerberoasting/RBCD theo handoff #218, và đối chiếu 8 tiêu chí nghiệm thu |
| Chạy kiểm tra targeted và liên quan | `.venv/bin/python -m pytest -q tests/test_week4_query_scenario_mapping.py tests/test_week4_scenarios.py tests/test_week4_query_materialization.py tests/test_query_boundary_regressions.py tests/test_week4_scoring.py` | 76 passed trong 4,14s |
| Kiểm tra repository và contract | `.venv/bin/python scripts/check_repository.py && .venv/bin/python scripts/check_contract.py` | Repository checks passed cho 458 tracked files; contract validated |

## Giải quyết các ý kiến đánh giá từ PR #225 (Refs #206)

Đã tiếp nhận và xử lý đầy đủ ba điểm đánh giá P2 từ reviewer TTS B (@nairyuuu):
1. Comment ID 4205306484 (Catalog validator fail-closed):
Thay thế assertion bắt buộc `load_catalog()` active phải thiếu các extension techniques bằng việc kiểm tra fail-closed qua một ID kỹ thuật chắc chắn không tồn tại (`unsupported_extension_technique_pending_b`).
Bảo lưu trạng thái PENDING của AS-REP, Kerberoasting và RBCD như một disposition tại baseline trong tài liệu mà không khóa cứng catalog active thành một invariant sai khi B triển khai #216.
2. Comment ID 4205306492 (Exact oracle matching):
Không chỉ kiểm tra số lượng paths mà tiêu thụ trực tiếp gói kỳ vọng độc lập #214 (`tests/fixtures/attack_scenarios/week4-v1.json`).
Chuẩn hóa chữ ký chuyển tiếp `(technique_id, actor, source, target)` và đối chiếu chính xác từng tập đường với `acceptable_paths`.
Đối chiếu đầy đủ tập trạng thái đạt được (`{S0, S1, S2, S3}` cho W4-M; `{S1, S3}` cho W4-I/E; OtherHost cho W4-I/H; `{S0, S1, S2, S3}` cho W4-TARGET) cùng cờ `complete=True`.
3. Comment ID 4205306500 (Ngữ nghĩa Query Outcome và DA Checkpoint):
Sửa mô tả trong tài liệu để phản ánh đúng hành vi hiện tại của `src/engine/query.py`: `status="success"` thể hiện việc đạt được mục tiêu tài sản cuối cùng (`final_goal_reached=True`), còn `checkpoint_reached` được đánh giá và báo cáo độc lập.
Bổ sung ca kiểm thử Case 4 trong `test_da_checkpoint_reached_separated_from_asset_target`: mục tiêu tài sản đạt được trực tiếp qua đường AdminTo nhưng checkpoint bị chặn (`membership_usable=False`), kết quả trả về `status="success"`, `final_goal_reached=True`, `checkpoint_reached=False`, 1 path, `complete=True`.
Đính chính nhận định kiến trúc: DA checkpoint là mốc đặc quyền cao hoặc đường rẽ nhánh thay thế, không phải điều kiện tiên quyết bắt buộc mọi đường dẫn tới tài sản đều phải qua Domain Admins (có các đường direct/local admin không qua DA).
API query báo cáo độc lập giữa checkpoint_reached và final_goal_reached theo đúng thiết kế.

## Điều học được / quyết định

- Máy xuất phát là Computer chỉ cung cấp quyền kiểm soát cục bộ trên máy đó, tuyệt đối không tự cấp danh tính miền cho tài khoản User.
- Quyền danh tính miền phải được khai báo dạng cặp `(principal, authentication_context)` và chỉ có hiệu lực khi ngữ cảnh xác thực của truy vấn trùng khớp.
- Đạt mốc Domain Admin (DA checkpoint) chỉ chứng minh năng lực trung gian, không đại diện cho việc thỏa mãn mục tiêu xâm nhập tài sản cuối cùng (Host target goal).
- Khi cổng tài sản cuối cùng thất bại, hệ thống phân định chính xác giữa trường hợp bị chặn do dữ kiện xác thực (`checkpoint_reached_final_goal_blocked`) và trường hợp chưa biết do thiếu dữ kiện (`checkpoint_reached_final_goal_indeterminate`).
- Trong API query hiện hành, `status="success"` phản ánh việc đạt mục tiêu tài sản cuối cùng (`final_goal_reached=True`), còn `checkpoint_reached` là trường thông tin độc lập; DA checkpoint không phải là điều kiện tiên quyết bắt buộc mọi đường dẫn tới tài sản phải đi qua.
- Dữ kiện xác thực mang giá trị False có quyền phủ quyết tuyệt đối giả định mang giá trị True trong cùng phạm vi truy vấn; vết chẩn đoán và lý do phủ quyết được lưu vết đầy đủ trong sổ cái `rejected_assumptions`.
- Giới hạn ngân sách tìm kiếm khi bị chạm ngưỡng phải được báo cáo là `truncated` và không bao giờ được phép suy diễn thành `no_path` hoặc tìm kiếm tối ưu toàn cục.
- Các kỹ thuật mở rộng AS-REP Roasting, Kerberoasting, và RBCD vẫn giữ nguyên trạng thái PENDING B vì engine catalog và bộ quy tắc chuyển tiếp chưa được TTS B bàn giao; query API từ chối fail-closed các kỹ thuật này.
- Trạng thái pending là một disposition tại baseline bàn giao chứ không phải một bất biến bắt buộc catalog active phải vắng mặt các kỹ thuật mở rộng khi B phát triển tiếp các tính năng mới (#216).
- Kiểm chứng mapping giữa Query API và kịch bản bắt buộc phải bảo toàn exact oracle từ gói kỳ vọng #214 (chữ ký chuyển tiếp, tập acceptable paths, tập reachable states) chứ không chỉ dừng ở kiểm tra số lượng paths.
- TTS A chỉ chịu trách nhiệm phần A (inputs, kỳ vọng, mapping và bằng chứng kiểm chứng); các lỗi engine hoặc tính năng còn thiếu được ghi nhận thành ca kiểm thử chuyển giao cho B mà không can thiệp vào mã nguồn engine của B (#212, #213, #215, #216).

## Trở ngại và việc kế tiếp

- Trở ngại: Issue #212 (tìm kiếm Min-Effort), #213 (tích hợp CLI/evaluator), #215 (snapshot fact store), và #216 (Kerberoasting) vẫn đang mở và do TTS B chủ trì; các kỹ thuật AS-REP và RBCD chưa có issue nhận việc cụ thể từ B.
- Việc kế tiếp: Đẩy commit cập nhật lên nhánh `docs/206-week4-query-mapping`, phản hồi trực tiếp vào từng review comment thread trên PR #225.
- Giữ nguyên trạng thái OPEN cho Issue #206 cho đến khi TTS B hoàn thành phần tích hợp runtime và nghiệm thu toàn diện theo các tiêu chí còn phụ thuộc.
