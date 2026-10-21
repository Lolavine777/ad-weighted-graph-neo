# Worklog - 2026-10-14 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Issue #290 / parent #265
- Thời gian thực tế ước lượng: Phiên đặc tả và hiện thực SEAMLESS-wide Scenario Assumption Profile

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Policy Core Module | [scenario_policy.py](../../src/engine/semantics/scenario_policy.py) | Hiện thực bộ giải định ngữ cảnh phân tầng, ràng buộc snapshot ID, veto chứng cứ âm và cấm mặc định nhóm phân phối |
| Schema & Profile | [Profile](../../docs/research/scenarios/seamless-policy-profile-v1.json), [Schema](../../docs/research/scenarios/seamless-policy.schema.json) | Đặc tả JSON profile và Draft 2020-12 schema chuẩn hóa toàn bộ 44 vị từ runtime |
| Prerequisites Audit | [Audit Document](../../docs/research/scenarios/seamless-prerequisites-audit.md), [Report](../../reports/research/seamless-prerequisites-audit.json) | Phân loại toàn bộ 44 vị từ vào 4 nhóm: observed (13), safely_conditionable (22), needs_scoped_override (5), cannot_default (4) |
| Test Suite | [Tests](../../tests/test_scenario_policy.py) | Comprehensive unit/integration tests bao phủ đa nguồn, missing condition, veto enabled=False, distribution lists, recovery opt-in và bảo vệ biên an ninh |
| Acceptance Funnel | [Acceptance Script](../../scripts/research/seamless_policy_acceptance.py), [Summary](../../reports/research/issue290-seamless-policy-summary.json) | Chạy native trên SEAMLESS raw data; đo lường funnel across C0, JEANNE_YANG (Kerberoast SPN), GINO_ROSS, BORIS_DILLARD (HO-170-DISTLIST1); phân biệt rõ search blocker và no-path |
| A/B Handoff | [Handoff Document](../../docs/research/scenarios/issue290-a-b-handoff.md) | Tài liệu hợp đồng tích hợp chi tiết cho TTS B trên Query CLI, Batch Engine và Interactive Viewer |

## Điều học được / quyết định

Phân tầng giả định 4 lớp tách biệt dứt khoát giữa điều kiện môi trường an toàn và các giả định xâm nhập cần bằng chứng cụ thể.
Không bao giờ tự ý chuyển trạng thái Unknown thành True khi chưa có quy tắc chính thức trong policy profile.
Snapshot property enabled=False hoặc runtime fact mang giá trị False luôn có quyền phủ quyết (known_false_veto) với mọi giả định.
Nhóm có tiền tố hoặc hậu tố DISTLIST, DISTRIBUTION, hoặc DL tuyệt đối không được mặc định coi là security group vì BloodHound v3 bỏ qua groupType.
Thao tác bẻ khóa mật khẩu ngoại tuyến (recovery_success) bắt buộc phải có scoped override chỉ định phương pháp và ngân sách trong chế độ what-if.
Thành công của giả định không bao giờ đồng nghĩa với xác suất P=1; các trường điểm số tiếp tục giữ trạng thái unrated khi thiếu cơ sở thẩm định.
Hiện tượng bùng nổ tìm kiếm của GINO_ROSS tại nút DOMAIN USERS chạm ngưỡng max_expansions phải được ghi nhận là search blocker thay vì kết luận sai là không có đường đi.

## Trở ngại và việc kế tiếp

Hợp đồng tích hợp A/B đã hoàn tất và sẵn sàng để TTS B kết nối vào giao diện dòng lệnh query CLI và batch runner.
Cần theo dõi quá trình review PR #287 của TTS B để tránh xung đột manifest lịch sử giữa các nhánh tính năng.
Các bộ thử nghiệm độc lập đã được xác minh cục bộ trên tập dữ liệu BloodHound v3 thực tế.
