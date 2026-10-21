# Cách ghi worklog

Mỗi người ghi cuối buổi, khoảng 5 phút. Worklog phản ánh bằng chứng và điều học được; số giờ chỉ là ước lượng thực tế, không dùng thay chất lượng đầu ra.

Đường dẫn: `docs/worklog/YYYY-MM-DD-ttsA.md`, `YYYY-MM-DD-ttsB.md`. Mỗi người một file/ngày để giảm xung đột. Copy [mẫu ngày](../templates/daily-worklog.md), giữ người viết, issue/PR, kết quả, trở ngại và việc kế tiếp. Dùng ngày ISO và múi giờ `Asia/Ho_Chi_Minh` (UTC+07:00).

Ghi worklog trong PR công việc hiện tại. Nếu chỉ có nghiên cứu/chưa có mã, mở PR `docs/worklog-YYYY-MM-DD-ttsA` vào develop. PR chưa merge vẫn là bằng chứng tiến độ; không cần đợi tính năng hoàn thành mới ghi log.

Cuối tuần A/B luân phiên tổng hợp `docs/worklog/week-01-review.md` theo [mẫu tuần](../templates/weekly-review.md), dẫn link các log ngày, demo và issue đã đạt nghiệm thu. Mentor feedback được ghi thành quyết định, người xử lý và hạn; chuyển việc mới thành issue.

Một mục kết quả tốt: “Đối chiếu 20 cạnh tổng hợp, phát hiện 2 cạnh bị đảo hướng; fixture và PR #...; còn thiếu trường session timestamp.” Tránh chỉ ghi “đọc AD”, “code parser” hoặc số giờ không kèm đầu ra. Ví dụ này là minh họa, không phải kết quả đã thực hiện.

Issue lưu nhiệm vụ/trạng thái; PR lưu thay đổi/review; worklog lưu hoạt động/học hỏi; ADR lưu quyết định dài hạn; experiment lưu phép đo tái lập. Dùng liên kết giữa chúng, không sao chép toàn bộ nội dung.

## Reviews tuần và closure audit

- [Week 1 / M0](week-01-review.md): retrospective evidence, historical A/B và amendments sau baseline.
- [Week 2 / M1](week-02-review.md): taxonomy/schema/parser review và carry-over truth migration.
- [Closure audit](../research/week-01-02-closure-audit.md): acceptance, supersession và successor ownership tại ngày 2026-09-22.

Các review không thay thế nghiệm thu issue hoặc mentor sign-off.
