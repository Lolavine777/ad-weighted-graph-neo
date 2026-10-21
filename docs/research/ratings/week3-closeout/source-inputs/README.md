# Đầu vào release Week 3

Các tệp này là bản dùng để phát hành từ [hai bộ đánh giá hiện tại](../../week3-2026-10-02/README.md). Giữ nguyên điểm impact/likelihood/effort, bindings, lý giải, policy và khai báo nguồn; metadata hành chính được chuẩn hóa. Không thay bằng chứng AI-assisted/exposure thành chấm độc lập.

- [rater-A.json](rater-A.json), [rater-B.json](rater-B.json): điểm nguồn không đổi.
- [execution-policy.json](execution-policy.json): nguyên byte policy hiện hành.
- [shared-review-confirmation.json](shared-review-confirmation.json): biên bản tiếp nhận dùng `reviewed_at` và `review_summary`; B được A chuyển đạt.
- [Bản đánh giá B ban đầu](../../week3-2026-10-02/rater-B-ai-draft.json): giữ nguyên archive và digest; exporter kiểm giá trị đã tiếp nhận khớp archive.

Final decisions và release bind bằng digests của chính các tệp này. Các artifacts nguồn đã tiếp nhận trước đó được giữ lịch sử; release dùng bộ đầu vào ở đây. Lệnh tái lập ở [README release](../README.md).
