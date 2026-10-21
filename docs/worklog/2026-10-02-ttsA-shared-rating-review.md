# Worklog - 2026-10-02 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #143/#158/#171/#48 / [PR #173](https://github.com/nairyuuu/ad-weighted-graph/pull/173) / M2.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.
- Nhánh: research/143-week3-independent-ratings; source head 9b8aed43b8dd9f69efb338020f832c9c0b207b6d.
- Người thực hiện: Codex thay A sửa tài liệu/metadata theo ủy quyền của A, với xác nhận B được A chuyển đạt; không viết lời khai giả do B trực tiếp phát biểu.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Thống nhất điều kiện chấm | [Policy](../research/ratings/week3-2026-10-02/execution-policy.json), [confirmation](../research/ratings/week3-2026-10-02/shared-review-confirmation.json) | 3 lần thử; reset 15 phút, ticket 10 phút, WinRM 30 phút; horizon 24h |
| Tiếp nhận B và cập nhật A | [Hai phiếu](../research/ratings/week3-2026-10-02/README.md), [B AI gốc](../research/ratings/week3-2026-10-02/rater-B-ai-draft.json) | 42 giá trị nguồn giữ nguyên; công bố AI/exposure/relay, không claim blind independence |
| Kiểm policy và đối soát | check_week3_rating_policy.py; reconcile_rating_sheets.py | 11 câu hỏi đồng chính sách; 21 cặp matched/rated, 0 unmatched, 21 proposals, 0 overlap withheld |
| Tính lại hai phiếu | Fraction và canonical engine trên baseline 12a221f | Tích cận/C/impact và frontier trong supplied sets khớp; chi tiết trong verification summary |
| Đồng nhất tài liệu | README, bản nháp B, 3 worklogs lịch sử có amendment | Ghi rõ trạng thái B đã tiếp nhận; phân biệt lịch sử và hiện tại |

Các lệnh kiểm tra và digest được lưu trong [verification-summary.json](../research/ratings/week3-2026-10-02/verification-summary.json). Runtime Python 3.12.14/Linux; đây là snapshot text files, không phải full git checkout. Kiểm validator link/worklog trên các tài liệu đổi; không claim full pytest hoặc CI của commit mới trước khi có kết quả GitHub. Baseline screenshots chưa tải không được tính thành PASS kiểm toàn repository.

## Điều học được / quyết định

Reconciler không kiểm execution_policy; chỉ khớp scenario/query không đủ đảm bảo cùng đại lượng. Bổ sung preflight riêng, chưa đổi schema/engine. Giữ khoảng B rộng dưới điều kiện chung như nhận định được tiếp nhận, không dùng công thức chuyển horizon thành deadline. Sửa dependency Ollie theo query để hai reset không trở thành AND prerequisites.

Xác nhận chung dùng tin nhắn A lúc 14:05:23 UTC+07, không phải lời khai B trực tiếp hay chấm mù mới. Điểm nguồn đã được tiếp nhận nhưng metric chỉ mô tả artifacts có exposure. Phân loại human_reviewed_ai_assisted_ratings công bố đúng giới hạn; không relabel thành declared_independent_ratings để qua exporter.

## Trở ngại và việc kế tiếp

PR #172 ở head b779916892e3741d36686439067c2596e20ea033 chưa hỗ trợ phân loại nguồn hiện tại. Cần cập nhật hợp đồng exporter/guard/provenance phù hợp trước khi xuất final bundle. Sau đó ghi 21 dispositions có lý do, chạy release validator/độ nhạy/engine và tổng hợp Week 3. Không yêu cầu xác nhận lại B, hội đồng ngoài hoặc thực nghiệm ngoài scope. Không tự merge hoặc đóng #143/#158/#48 trong lượt sửa này.
