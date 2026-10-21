# Worklog - 2026-10-02 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #143/#158/#171 / [PR #173](https://github.com/nairyuuu/ad-weighted-graph/pull/173) / M2; công cụ riêng ở PR #172.
- Người chấm: @Lolavine777, TTS A.
- Nhánh: research/143-week3-independent-ratings; base develop 12a221fb401d9ce0a38e008168dc0b62f116792d.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Nộp phiếu A | [Phiếu A](../research/ratings/week3-2026-10-02/rater-A.json), [hướng dẫn](../research/ratings/week3-2026-10-02/README.md) | 21 mục được người dùng chốt; AI assistance khai báo rõ |
| Kiểm tra phiếu A với mẫu B trống | reconcile_rating_sheets.py; lệnh trong hướng dẫn | 21 matched, 0 unmatched, 21 pending; không có đồng thuận A/B |
| Kiểm tra cập nhật từ B | [Bản nháp công sức](../research/seamless-ai-assisted-effort-draft.md), head 8fd2eb5 | 9 điểm đề xuất khớp A; chưa phải phiếu B hoàn chỉnh |
| Sửa lỗi tài liệu của CI | validate_worklog và broken_links trên worklog A/B, bản nháp B và README phiếu | 4 file PASS kiểm tra tương ứng; chưa chạy lại toàn bộ pytest |

Đã giải thích và ghi nhận 21 lựa chọn được người dùng xác nhận trong hội thoại: 1 mức tác động, 9 bộ điểm công sức và 11 khoảng xác suất có điều kiện. Người dùng khai báo chấm riêng rồi sẽ yêu cầu B chấm; phiếu ghi rõ AI hỗ trợ nghiên cứu/giải thích/đề xuất, không có hiệu chuẩn thực nghiệm. Dùng tên hiển thị tài khoản, không bịa năng lực chuyên gia. `rated_at` lấy từ tin nhắn xác nhận nhóm điểm cuối lúc 12:21:07 UTC+07, không phải thời điểm nghiệm thu.

Biên soạn phiếu thật vào `docs/research/ratings/week3-2026-10-02/rater-A.json`. Giữ đủ bindings, lý do, nguồn, rubric, khai báo và dấu vết xác nhận. Không thay đổi mẫu trống hoặc bộ/oracle nghiên cứu; không sửa engine/parser của B. Theo yêu cầu lúc 13:33:34 UTC+07, công bố phiếu A lên PR để B bổ sung phiếu riêng vào cùng branch. Khai báo độc lập của B phải phản ánh đúng việc đã/chưa tiếp xúc điểm A.

Đã kiểm tra cấu trúc/bindings bằng `reconcile_rating_sheets.py` với A đã chấm và mẫu B trống: 21 matched, 0 unmatched, 0 fully rated pairs, 21 pending. Đây là kiểm tra A, không phải đồng thuận A/B. Runtime tại lượt kiểm tra: Python 3.12.14/Linux, khác Python 3.14 baseline của dự án.

Phép tính phân số độc lập đã khớp canonical engine tại baseline nêu trên: Lidia `[42/125,171/250]`/C=2, Josefa → Ollie `[588/3125,29241/50000]`/C=3, Source B Ollie `[42/125,171/250]`/C=2; impact High. Hai ứng viên Source A incomparable/frontier, Min-Effort trong supplied set chọn Lidia. Phạm vi không phải toàn bộ search space.

SHA-256 phiếu A được công bố: `47ca08e828f765ddbd3ed388a22c039c46c3b5cea84a265cc38effa76b6926c0`.

B tiếp tục chấm riêng, nộp `rater-B.json` và worklog B vào cùng branch. Khi đủ hai phiếu mới chạy đối soát và ghi các quyết định cuối. Review/CI, B ratings, final dispositions, parameter acceptance và integrated Week 3 acceptance vẫn pending; không tự merge hoặc đóng #143/#158/#48.


## Điều học được / quyết định

Phiếu thật được nộp riêng với mẫu trống/tests để không thay oracle nghiên cứu. Nỗ lực, likelihood và tác động là ba đại lượng riêng; chỉ công sức 9/9 khớp một bản nháp AI không chứng minh đồng thuận của hai người. B cần khai báo đúng việc tiếp xúc điểm A, chốt các lựa chọn và ghi lý do thay vì nhận điểm do AI tự nộp.

CI head 8fd2eb5 (run 36974973695) phát hiện worklog A do mình thêm thiếu đúng title/metadata/sections/table theo validator, và link release guide trong bản nháp B trỏ tới file chưa merge. Cập nhật này sửa cấu trúc worklog và dùng URL tài liệu ở revision #172 đã tham chiếu, giữ nguyên phiếu A và các điểm đề xuất. Sửa câu trạng thái để phân biệt hai mẫu fixture trống với phiếu A thật đã nộp. Không sửa validators để bỏ qua lỗi.

## Trở ngại và việc kế tiếp

B vẫn cần xác nhận/điều chỉnh 9 điểm công sức và overlap, chấm 11 likelihood cùng 1 impact rồi nộp rater-B.json trên cùng branch. Chưa có final reconciliation/decisions/parameter acceptance. PR #173 giữ draft, không merge hoặc đóng #143/#158/#48; #172 có vòng review công cụ riêng. CI của revision sửa này cần được đọc lại, không sử dụng kết quả failed head trước làm kết quả head mới.

## Cập nhật sau xác nhận chung lúc 14:05:23 UTC+07

Các mô tả B chưa chấm/chưa xác nhận ở trên là trạng thái lịch sử khi worklog được lập. A hiện chuyển đạt B đang cùng làm việc và xác nhận, đồng thời ủy quyền thống nhất tài liệu. Nguồn sự thật hiện tại là [bộ phiếu và hướng dẫn](../research/ratings/week3-2026-10-02/README.md), [xác nhận chung](../research/ratings/week3-2026-10-02/shared-review-confirmation.json) và [worklog cập nhật](2026-10-02-ttsA-shared-rating-review.md). Giữ điểm nguồn, thống nhất retry/deadline; B đã được tiếp nhận qua A nhưng không gọi chấm mù độc lập. Chưa có final parameter dispositions hoặc integrated acceptance.
