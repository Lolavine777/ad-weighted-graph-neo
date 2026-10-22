# Năm foothold SEAMLESS: đường đi, C và can thiệp

Chọn cố định 3 User và 2 Computer theo hash, trước khi xem kết quả; đây là 5 ca minh họa.
Mỗi nguồn bị chiếm độc lập; 12 bước, 1.024 expansions, tối đa 3 chuỗi/cặp.
C xếp trong các chuỗi tìm được; đồng C giữ nguyên, chưa chứng minh minimum.
Một tuyến có thể có nhiều chuỗi thao tác. Không đếm chúng thành nhiều tuyến.

| Nguồn | Đích | Chuỗi | Tuyến | C tăng dần |
| --- | --- | ---: | ---: | --- |
| SCOTTY_HARTMAN@SEAMLESS.INTERNAL | DA | 3 | 3 | 2, 2, 2 |
| SCOTTY_HARTMAN@SEAMLESS.INTERNAL | EA | 3 | 1 | 5, 6, 6 |
| BENNY_LONG@SEAMLESS.INTERNAL | DA | 3 | 3 | 1, 1, 1 |
| BENNY_LONG@SEAMLESS.INTERNAL | EA | 3 | 1 | 4, 5, 5 |
| EVAN_LOTT@SEAMLESS.INTERNAL | DA | 3 | 3 | 1, 1, 1 |
| EVAN_LOTT@SEAMLESS.INTERNAL | EA | 3 | 1 | 4, 5, 5 |
| OGCWAPPS1000000.SEAMLESS.INTERNAL | DA | 3 | 3 | 1, 1, 1 |
| OGCWAPPS1000000.SEAMLESS.INTERNAL | EA | 3 | 1 | 4, 5, 5 |
| ITSWWEBS1000000.SEAMLESS.INTERNAL | DA | 3 | 2 | 2, 3, 3 |
| ITSWWEBS1000000.SEAMLESS.INTERNAL | EA | 3 | 1 | 5, 6, 6 |

Can thiệp mô phỏng: gỡ membership KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL.
Hỗ trợ quan sát: 15 chuỗi / 5 cặp.

Đã replay và tìm lại trên đủ 10 cặp, mỗi nguồn được native verifier kiểm độc lập.
Cắt 15/30 chuỗi gốc; ngắt kết nối được chứng minh: 0/10 cặp trước đó reachable.
Sau sửa: 10 cặp còn đường, 0 cặp chưa kết luận; tìm thêm 15 chuỗi mới.

## C trước và sau trên các đường tìm được

| Nguồn | Đích | C trước | C sau | Trạng thái sau |
| --- | --- | ---: | ---: | --- |
| SCOTTY_HARTMAN@SEAMLESS.INTERNAL | DA | 2 | 2 | reachable |
| SCOTTY_HARTMAN@SEAMLESS.INTERNAL | EA | 5 | 5 | reachable |
| BENNY_LONG@SEAMLESS.INTERNAL | DA | 1 | 1 | reachable |
| BENNY_LONG@SEAMLESS.INTERNAL | EA | 4 | 4 | reachable |
| EVAN_LOTT@SEAMLESS.INTERNAL | DA | 1 | 1 | reachable |
| EVAN_LOTT@SEAMLESS.INTERNAL | EA | 4 | 4 | reachable |
| OGCWAPPS1000000.SEAMLESS.INTERNAL | DA | 1 | 1 | reachable |
| OGCWAPPS1000000.SEAMLESS.INTERNAL | EA | 4 | 4 | reachable |
| ITSWWEBS1000000.SEAMLESS.INTERNAL | DA | 2 | 2 | reachable |
| ITSWWEBS1000000.SEAMLESS.INTERNAL | EA | 5 | 5 | reachable |

C trước/sau là mức thấp nhất tìm được trong giới hạn chạy, chưa chứng minh tối ưu.
Chỉ thử membership trong mô hình; chi phí và ảnh hưởng vận hành chưa chấm.
Các bản brief theo từng cặp giữ hành động, ledger C và giả định đã dùng.

## Vì sao C=5 được xếp trước C=6?

Ví dụ SCOTTY → EA, chuỗi C=5 có hai lần reset mật khẩu (1 + 1),
một lần cấp quyền lên đối tượng đích (2), và một lần thêm thành viên (1).
Hai thao tác nhận danh tính sau reset được bảng C hiện tại tính 0: tổng 5.
Hai biến thể C=6 thêm thao tác `genericall_grant_write_dacl` có C=1;
cả ba dùng cùng một tuyến quan hệ. Chuỗi đồng C được giữ đồng hạng.
C là điểm công việc theo bảng `neo-c-v1`, không phải thời gian hay xác suất đo thực tế.

## Ý nghĩa kết quả

Gỡ membership đã chọn cắt 5/19 tuyến quan sát ban đầu (15/30 chuỗi thao tác),
nhưng tìm lại được 5 tuyến thay thế. Cả 10 cặp vẫn có đường với C không đổi.
Ví dụ SCOTTY vẫn đi qua TERRA_MCBRIDE → OLLIE_LONG → Domain Admins để tới EA,
không cần membership KATRINA vừa gỡ. Vì vậy, riêng thay đổi này chưa chặn được
việc tới DA/EA trong mô hình.
Đây là kết quả trên snapshot SEAMLESS tĩnh, không phải kiểm tra AD đang vận hành.

## Chạy lại

Sau khi tạo snapshot bằng lệnh baseline trong README:

```bash
.venv/bin/python -m scripts.neo_decision \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --output-dir reports/generated/neo-decision-001
```

Output giữ brief/ledger từng cặp và gói kiểm chứng độc lập của engine cho từng nguồn.
Dùng `--workers 1` nếu cần giảm RAM; `--resume` nối tiếp cùng code và snapshot.
[Bằng chứng gọn: scope, C, edit và kết quả kiểm chứng](decision-sample.json).
Kiểm tra CLI/báo cáo liên quan: 17 test pass; cả 5 gói can thiệp qua verifier độc lập.
