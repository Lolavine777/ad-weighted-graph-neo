# Worklog - 2026-10-02 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #143/#158/#48 / [PR #173](https://github.com/nairyuuu/ad-weighted-graph/pull/173) / M2.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng.
- Nhánh: research/143-week3-independent-ratings.
- Người thực hiện: Codex AI theo yêu cầu finalize của @nairyuuu; không là lời khai human rating B.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Hoàn thiện assessment | [Bản B AI gốc](../research/ratings/week3-2026-10-02/rater-B-ai-draft.json) | Đủ 1 impact, 11 likelihood và 9 effort; identity AI/exposure công bố |
| Đối soát | python scripts/research/reconcile_rating_sheets.py --sheet1 docs/research/ratings/week3-2026-10-02/rater-A.json --sheet2 docs/research/ratings/week3-2026-10-02/rater-B.json --output reports/generated/week3-A-vs-ai-B.json --summary | Exit 0; 21 matched/rated, 0 unmatched, 21 proposals |
| Tính đường | fractions.Fraction trên factor B | Tính exact products trong terminal; không claim canonical engine replay |
| Provenance | Phiếu A raw digest | 47ca08e828f765ddbd3ed388a22c039c46c3b5cea84a265cc38effa76b6926c0 giữ nguyên |

Runtime Python 3.12.14/Linux. Source files dùng từ PR head 0d615760373097a3bdcc415fa27c9eed25187b17, CLI/helpers tải đúng head vào scratch; không là full git checkout hoặc full pytest/CI.
Phiếu B raw digest e06dbbf8ddb2f8a88fd79182739fc9bb73ca158a9080e1d19d67fbe92f046d79. Mean IoU 0.5813099943534726, max/mean effort delta 0, Kappa null (degenerate_zero_variance), observed agreement 1. Không suy metrics này là human inter-rater agreement.

## Điều học được / quyết định

High là judgment về hậu quả trong declared business scenario. Các cận B reset [3/5,19/20], activation [3/4,49/50], WinRM [1/2,9/10] là AI scenario assumptions, không measured frequencies hay statistical confidence intervals. Nguồn kỹ thuật đã đối chiếu về reset/Kerberos/WinRM quotas và DC compromise; không cung cấp numeric bounds. Không thêm retry/deadline phút ngoài scope.

Phiếu dùng AI evaluator, công bố đã xem A, human_review pending. Giữ 9 effort trước đó; không tạo hai chuyên gia giả hoặc user confirmation giả. Hoàn thiện artifact theo yêu cầu không tự tạo final consensus.

## Trở ngại và việc kế tiếp

Người thật cần review/điều chỉnh assumptions, numeric basis và overlap, ghi dispositions có identity/exposure trung thực. Exporter #172 không có evidence class AI assessment; không relabel phiếu này thành independent human input. Chưa export final release, empirical calibration, approve/merge PR hoặc đóng issues. CI head mới theo dõi riêng.

## Cập nhật sau xác nhận chung lúc 14:05:23 UTC+07

Các mô tả B chưa chấm/chưa xác nhận ở trên là trạng thái lịch sử khi worklog được lập. A hiện chuyển đạt B đang cùng làm việc và xác nhận, đồng thời ủy quyền thống nhất tài liệu. Nguồn sự thật hiện tại là [bộ phiếu và hướng dẫn](../research/ratings/week3-2026-10-02/README.md), [xác nhận chung](../research/ratings/week3-2026-10-02/shared-review-confirmation.json) và [worklog cập nhật](2026-10-02-ttsA-shared-rating-review.md). Giữ điểm nguồn, thống nhất retry/deadline; B đã được tiếp nhận qua A nhưng không gọi chấm mù độc lập. Chưa có final parameter dispositions hoặc integrated acceptance.
