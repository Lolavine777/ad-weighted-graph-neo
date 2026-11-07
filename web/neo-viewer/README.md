# Giao diện neo

Giao diện có hai cách chạy:

- **Ứng dụng phân tích:** `.venv/bin/python -m scripts.neo_app` phục vụ giao diện kèm màn hình **Phân tích** từ `workspace.js`, trả lời bằng bộ máy phân tích ngay trên máy.
- **Bản chỉ đọc:** mở `index.html` trực tiếp, hoặc dùng bản trên GitHub Pages. Bản này không tải `workspace.js`, không gửi request nào và chỉ đọc kết quả có sẵn.

## Các màn hình

- **Phân tích:** mở dữ liệu, tìm đối tượng, tìm đường, gỡ thử một quan hệ, tìm điểm nghẽn. Chỉ có trong ứng dụng.
- **Một nguồn bị lộ:** chọn đường, xem các bước và C.
- **Khảo sát nhiều nguồn:** bảng các cặp nguồn và đích trước và sau khi gỡ một quan hệ.
- **Chi tiết can thiệp:** chọn can thiệp, chuyển giữa trước và sau khi gỡ.

## Trạng thái kết quả

| Trên giao diện | Ý nghĩa |
| --- | --- |
| Có đường | Đường đã qua kiểm tra lại từng bước |
| Còn đường vòng | Sau khi gỡ, vẫn tới được mục tiêu theo đường khác |
| Đã chặn, Không có đường | Đã duyệt hết các kỹ thuật đang xét mà không có đường |
| Chưa kết luận | Hết ngân sách tìm kiếm, hoặc còn điều kiện chưa rõ |
| C tốt nhất đã tìm, C nhỏ nhất | C nhỏ nhất chỉ có khi đã duyệt hết; còn lại là mức tốt nhất đã tìm |

## Tệp mở được bằng nút Mở JSON

| Tệp | Màn hình |
| --- | --- |
| Kết quả `src.engine query`, ví dụ `neo_guided.json` của `neo_baseline` | Một nguồn bị lộ |
| Tệp tải từ nút **Tải kết quả JSON** của ứng dụng, khi có đường | Một nguồn bị lộ |
| `reports/neo/decision-sample.json` | Khảo sát nhiều nguồn |
| `results.json` của `neo_remediation`, `reports/neo/remediation-rediscovery-results.json` | Chi tiết can thiệp |

Tối đa 128 MB mỗi tệp, 200 đường mỗi truy vấn và 120 bước mỗi đường.
Tệp không đúng định dạng sẽ báo lỗi và giữ nguyên kết quả đang xem.

## Đóng gói một tệp HTML

```sh
.venv/bin/python web/neo-viewer/build.py --output reports/generated/neo-viewer.html
```

Tệp này mở được không cần mạng, dùng để mang đi trình bày.
Builder không ghi đè tệp cũ, nên mỗi lần cần một tên mới.

## Kiểm thử

```sh
npm ci --prefix web/neo-viewer --ignore-scripts
npm test --prefix web/neo-viewer
```
