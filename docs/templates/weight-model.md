# Mô hình trọng số — <profile/version>

Trạng thái: Proposed / Accepted / Superseded. Issue và ADR: <...>.

## Mục tiêu và lựa chọn mô hình

Trọng số đo điều gì: <chi phí tương đối / xác suất / thời gian>? Đơn vị: <...>. Vì sao cộng được trên một đường? So sánh phương án thay thế. Ghi giả định, nguồn và giới hạn; không quy chi phí tương đối thành thời gian nếu chưa hiệu chuẩn.

## Rubric

| Tiêu chí | Thang đo và định nghĩa từng mức | Chiều tăng | Hệ số | Nguồn |
| --- | --- | --- | --- | --- |
| <điều kiện / độ tin cậy / thời gian / phát hiện> | <...> | <...> | Chưa chọn | <...> |

Công thức: <...>. Miền giá trị hợp lệ: <...>. Policy cạnh thiếu/không đủ điều kiện: <...>. Chứng minh hoặc giải thích vì sao trọng số hữu hạn, không âm và phù hợp thuật toán.

## Chấm độc lập và hiệu chuẩn

| Loại cạnh | Điểm A | Điểm B | Bất đồng | Điểm chốt / trọng số | Lập luận |
| --- | --- | --- | --- | --- | --- |
| <...> | Chưa chấm | Chưa chấm | Chưa đo | Chưa chốt | <...> |

Chọn chỉ số đồng thuận phù hợp loại thang đo; báo số mẫu và cách giải quyết chênh lệch. Không báo chỉ số thống kê không phù hợp chỉ để đủ bảng.

## Độ nhạy và phê duyệt

Ghi dải perturbation, seed, số lần chạy, tập nguồn/đích, overlap/rank của đường và choke point. Link experiment và giới hạn. Chỉ chuyển profile sang `accepted` sau review; giữ profile cũ để tái lập.
