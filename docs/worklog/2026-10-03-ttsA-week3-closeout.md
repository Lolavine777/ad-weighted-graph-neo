# Worklog - 2026-10-03 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #143/#158/#48; PR #176 / M2.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng.
- Nguồn: develop bd2a4cf43dd539443a67ba20655cca800f38d65c; tiếp nối tooling #172.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Chốt tham số | [Lựa chọn](../research/ratings/week3-closeout/parameter-selection.md), [21 decisions](../research/ratings/week3-closeout/parameter-decisions-final.json) | High, effort 1/0/1, các khoảng B rộng trong cùng policy |
| Chuẩn hóa đầu vào release | [Source inputs](../research/ratings/week3-closeout/source-inputs/README.md) | Giữ nguyên toàn bộ rating records/policy, digest bindings tái lập được |
| Tương thích biên bản review | reviewed_parameter_release.py; tests/test_ai_assisted_reviewed_release.py | Nhận reviewed_at/review_summary; giữ compatibility legacy và từ chối aliases mâu thuẫn |
| Xuất và kiểm chứng | [Actual release](../research/ratings/week3-closeout/reviewed-release.json), [validation](../research/ratings/week3-closeout/validation-summary.json) | Export/replay/engine/oracle passed; 21 probes/24 outcomes |
| Đối chiếu trước/sau chuẩn hóa | sources, sensitivity, stability trong hai validation summaries | Tất cả C/P/I/frontier/relations/Min-Effort và probe outcomes giữ nguyên |
| Cập nhật báo cáo | [Báo cáo Week 3](../reports/week3-report.md), [remaining work](../reports/week3-remaining-work.md) | Tiếng Việt, công thức, ví dụ số, cách triển khai và giới hạn |
| Xử lý findings | [Disposition](../research/week3-rating-requirement-disposition.md), #143/#158 | Cơ sở tham số được tiếp nhận cho kịch bản Week 3; IoU và B provenance diễn giải đúng |

Local Python 3.12.14 trên text snapshot; không gọi đó là full-suite/clean-checkout verification. CI theo exact head được kiểm tra riêng. Full CLI report tái lập bằng lệnh ở README; summary lưu digests và mọi expected/actual.

## Điều học được / quyết định

Cơ sở tham số là nhận định theo kịch bản; các nguồn kỹ thuật hỗ trợ cơ chế và điều kiện, không tự suy xác suất thực nghiệm. Khoảng rộng giữ bất định; 21 local probes không chứng minh global/multivariate robustness. Disposition Week 3 không làm thay đổi evidence class hoặc tự hoàn tất các gates chất lượng còn lại.

## Trở ngại và việc kế tiếp

Hoàn tất #146/#167 để tìm đường và đánh giá dùng cùng release/bindings. B bàn giao accepted Legacy baseline/exports; A chạy real reconciliation #47. Audit demo/parser hiện có, rồi nghiệm thu #48 trên final integrated revision với positive/false/unknown, deterministic runs và clean-checkout reproduction. Không giao thêm research/chấm lại chỉ để thay tên trạng thái.
