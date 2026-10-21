# Phơi nhiễm từ các kịch bản compromise độc lập

Inventory: 2590 nguồn, 12 mục tiêu; đã chọn 1 × 12 = 12 cặp.
Ngoài cohort: 31068 cặp ứng viên. Trong cohort chưa chạy: 0 cặp.

Mục tiêu được chọn theo tiêu chí kỹ thuật, không phải business impact đã chấm. Có witness nghĩa là đạt theo model/facts/giả định đã khai báo; thiếu kết quả không phải an toàn.

Trạng thái: {"complete_success": 2, "truncated_incomplete": 10}

Có witness: 2 cặp. Bảng hiển thị tối đa 100; result.json giữ đủ cells, traces, assumptions, witnesses và proof flags.

| Nguồn | Mục tiêu | Trạng thái | C tìm thấy | Kỹ thuật trong witness |
| --- | --- | --- | --- | --- |
| S-1-5-21-1271839998-3495686680-2211690266-2799 | BADBLOOD.SEAMLESS.INTERNAL | complete_success | chưa chấm | obtain_admin_execution_on_host |
| S-1-5-21-1271839998-3495686680-2211690266-2799 | DOMAIN ADMINS@SEAMLESS.INTERNAL | complete_success | chưa chấm | propagate_group_entitlement |

C là union work-unit effort nếu có basis áp dụng; không lấy số bước làm C. Best found không tự có nghĩa global minimum. P chưa chấm không phải P=0.

Nếu bật remediation, summary.json trỏ tới full verified packages. Program elimination và source–goal disconnection là hai đại lượng riêng; cohort can thiệp có thể hẹp hơn cohort discovery.
