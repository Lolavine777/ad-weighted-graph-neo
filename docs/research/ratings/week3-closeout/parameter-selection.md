# Bộ tham số Week 3

Ngày lựa chọn: 2026-10-03. Phụ trách: TTS A. Phạm vi: kịch bản SEAMLESS hiện tại, hai điểm xuất phát và ba ứng viên; cùng chính sách thực hiện.

| Thành phần | Giá trị chọn | Số bản ghi |
| --- | --- | ---: |
| Tác động đích | High | 1 |
| Công sức reset / lấy vé / WinRM | C=1 / 0 / 1 | 9 |
| Xác suất có điều kiện reset | [3/5, 19/20] | 4 |
| Xác suất có điều kiện lấy vé | [3/4, 49/50] | 4 |
| Xác suất có điều kiện WinRM | [1/2, 9/10] | 3 |

Hai nguồn cùng mức tác động và rubric công sức. Chọn các khoảng xác suất rộng của B vì chúng chứa các khoảng A tương ứng; giữ mức bất định khi chưa có dữ liệu phân biệt hai bộ số. Mỗi bản ghi vẫn gắn với đầy đủ query, lịch sử thành công và đơn vị công việc; không dùng một xác suất biên chung cho loại cạnh.

[21 quyết định](parameter-decisions-final.json) lưu giá trị, bindings, người phụ trách, ngày, lý do và xử lý sai khác. [Nguồn sử dụng](source-inputs/README.md) giữ nguyên điểm/rationale/chính sách, chuẩn hóa metadata hành chính. [Kiểm chứng](validation-summary.json) đối chiếu engine/oracle và toàn bộ probes. [Cơ sở tiếp nhận](../../week3-rating-requirement-disposition.md) quy định phạm vi đánh giá.
