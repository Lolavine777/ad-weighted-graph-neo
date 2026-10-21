# EXP-<001>: <câu hỏi thực nghiệm>

Trạng thái: Planned / Running / Completed. Owner/reviewer: <...>. Issue/PR: <...>.

## Giả thuyết và thiết kế

<Câu hỏi, baseline, biến thay đổi, biến giữ cố định, tiêu chí đánh giá trước khi chạy.>

## Manifest tái lập

- Git commit; Python và dependency versions; OS/CPU/RAM: <...>
- Dataset ID/checksum/snapshot; schema/profile version và checksum: <...>
- BloodHound edition/version và truy vấn baseline: <...>
- Tập source/target IDs, loại cạnh được hỗ trợ, quy ước hướng: <...>
- Seed, K, số lần lặp, warm-up, dải perturbation: <...>
- Lệnh chạy nguyên văn và vị trí output local: <...>

## Kết quả

| Metric | Baseline | Weighted | Chênh lệch / giải thích |
| --- | --- | --- | --- |
| Node/edge counts theo loại | Chưa đo | Chưa đo | <...> |
| Reachable source-target pairs | Chưa đo | Chưa đo | <...> |
| Số bước / tổng chi phí trên cùng profile | Chưa đo | Chưa đo | <...> |
| Top-K hoặc choke-point overlap | Chưa đo | Chưa đo | <...> |
| Thời gian dựng graph / truy vấn (ms) | Chưa đo | Chưa đo | <median, p95 nếu đủ mẫu> |
| Tác động bỏ top N choke points | Chưa đo | Chưa đo | <...> |

Đối chiếu cùng dataset, hướng và loại cạnh; giải thích các cạnh chỉ một bên hỗ trợ. Nếu BloodHound không có phép đo choke point tương ứng, ghi N/A và mô tả baseline tự xây. Không trình bày metric tự xây như kết quả có sẵn của BloodHound.

Với tỷ lệ đường bị cắt, định nghĩa rõ mẫu số là tập đường đơn/top-K đã liệt kê trước can thiệp; nếu mẫu số 0 thì N/A. Đo thêm reachability sau khi dựng lại graph để phát hiện đường thay thế. Không kết luận phần trăm mọi đường trong graph từ một mẫu top-K.

## Kết luận, bất định và review

<Giả thuyết được ủng hộ đến đâu; hạn chế mẫu và giả định; kết quả bất thường; người tái chạy xác nhận.>
