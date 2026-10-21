# Phạm vi đánh giá tham số Week 3

Trạng thái: Accepted cho cơ sở tham số kịch bản Week 3. Ngày: 2026-10-03. Phụ trách: TTS A.

[Kế hoạch gốc, Mục 6](../00_todo.md) đề xuất nhiều người chấm độc lập để đo mức đồng thuận. Trong kịch bản Week 3 hiện tại, tiếp nhận bộ nhận định có AI hỗ trợ đã được A/B review làm cơ sở tham số. Không yêu cầu bổ sung lượt chấm độc lập để hoàn tất bộ tham số của kịch bản này.

Phạm vi gồm cùng snapshot/scenario/policy, hai điểm xuất phát, ba ứng viên và 21 tham số trong [release](ratings/week3-closeout/README.md). Canonical digest: `sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358`.

Cơ sở tiếp nhận: lý giải và nguồn của từng giá trị, giữ hai bộ nhận định, chọn khoảng rộng để bảo toàn bất định, kiểm bindings/replay, đối chiếu Fraction/canonical engine và chạy sensitivity. Mục tiêu là mô hình và phép tính đúng dưới giả định đã khai báo; các kiểm tra này không đo independent inter-rater reliability hoặc hiệu chuẩn xác suất.

Nguồn giữ lớp `human_reviewed_ai_assisted_ratings`, exposure và xác nhận B qua A; IoU chỉ mô tả mức chồng lấn. Nghiên cứu độ đồng thuận độc lập chưa được thực hiện. Việc tiếp nhận có giới hạn này không được trình bày là đã đáp ứng phương pháp độc lập của kế hoạch gốc hoặc áp dụng mặc định cho mọi kịch bản.

Giữ nguyên các yêu cầu chất lượng: known-false/unknown đúng ngữ nghĩa, provenance, tích hợp, đối chứng Legacy và tái lập sạch. Disposition này giải quyết cơ sở tham số; các tiêu chí nghiệm thu còn lại theo [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143) và [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158).
