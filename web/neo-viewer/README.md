# neo graph viewer

Mở `index.html` trực tiếp trong trình duyệt. Không cần cài dependencies, server, Docker hoặc kết nối AD.
Viewer chỉ đọc kết quả; không chạy query, sửa graph, chấm lại C hoặc thực thi remediation.

- **Một nguồn bị lộ:** chọn đường, đọc C và các công việc ở bảng bên phải; mở **Giả định chương trình**, rồi bấm cạnh/nút để xem chi tiết. Kéo nút hoặc nền để bố trí, dùng zoom và Vừa khung.
- **Chi tiết can thiệp:** chọn can thiệp, strategy và mục tiêu; chuyển Trước/Sau để xem quan hệ bị gỡ và kết luận tìm lại. Đường cũ bị cắt chưa có nghĩa mọi đường đã bị chặn.
- **Khảo sát nhiều nguồn:** bảng 10 cặp từ 5 nguồn độc lập; lọc một nguồn để xem DA/EA, chọn hàng để xem C trước/sau và số chương trình bị cắt. Cohort công bố cắt 15/30 chương trình nhưng 0/10 cặp bị ngắt. Không tự suy đường từ ledger.
- **Mở JSON:** đọc file trên máy, không upload hoặc lưu trình duyệt. File nhập có nhãn nguồn chưa xác minh; tiêu đề do file cung cấp, nếu thiếu thì dùng “Báo cáo đã nhập”. Nút ↺ trở về demo.

## Chọn đúng file

| File / định dạng | Màn hình và nội dung |
| --- | --- |
| Output query CLI có `semantic.materialized` và `semantic.candidates`, ví dụ `neo_guided.json` của `neo_baseline` | Một nguồn bị lộ: đồ thị và công sức theo kết quả engine |
| `reports/neo/decision-sample.json`, schema `neo-decision-sample/1.0.0` | Khảo sát nhiều nguồn: bảng cặp trước/sau, không có trace để vẽ đường |
| `results.json` của `neo_remediation`, version `neo-remediation-rediscovery/1` | Chi tiết can thiệp: ghép đúng trước/sau theo case, strategy, nguồn và đích; giữ C và kết luận gốc |
| `reports/neo/remediation-rediscovery-results.json`, version `neo-remediation-rediscovery-summary/1` | Chi tiết can thiệp: summary đã công bố |

`neo_domain` xuất `cells.jsonl` và brief; viewer chưa đọc định dạng này. Đọc brief cho lượt đó.
Snapshot, JSON query đầu vào, `summary.json` bất kỳ và output riêng của `neo_decision` cũng không tự trở thành một trong các định dạng trên.
C/ledger của query được đọc từ `semantic.top_k`; gói legacy chỉ có `ranking_result` hiện chưa chấm C trong viewer, nên đọc C ở brief CLI của gói đó.
Nếu file không được hỗ trợ, viewer báo lỗi và giữ kết quả đang xem. Xem [README gốc](../../README.md) để dùng các lệnh CLI hiện có.

## Hiểu kết luận

- **Đường đã tìm được / Còn đường vòng:** có đường trong kết quả; C vẫn tốt nhất trong tập đã tìm, trừ khi engine báo chứng minh minimum.
- **Chặn / Không có đường trong phạm vi xét:** báo cáo có proof tương ứng; kết luận chỉ áp dụng scope của lượt chạy.
- **Chưa kết luận:** đọc lý do hết ngân sách hoặc thiếu điều kiện nếu file có ghi. Không đổi thành “đã chặn”.
- **Chưa chấm C:** khác C=0. Giả định được đếm theo điều kiện `(predicate, subject, target, value)`, khử trùng giữa các bước; trace từng bước vẫn giữ đủ facts. Thiếu danh sách kiểm tra điều kiện ở một bước được hiện “chưa đầy đủ”, không phải 0 giả định.

Quyền ban đầu của nguồn khảo sát được đọc từ source profile khớp ID trong báo cáo; chỉ biết node là Computer không đủ để khẳng định đã có danh tính mạng. Khi summary không có scenario hoặc nguồn ban đầu, viewer ghi thiếu thông tin.

Tối đa 128 MB/file, 200 candidates/query và 120 bước/chương trình. Top-K giữ nguyên thứ tự của engine; thiếu ledger/C không được suy thành 0. Đồ thị biểu diễn **request source → target**, không phải canonical BloodHound edges; actor/context được giữ riêng trong chi tiết. Khi JSON không kèm nhãn/type, viewer dùng ID và ký hiệu đối tượng chưa rõ type.

Đây là UI đọc kết quả đã chạy, chưa khởi chạy engine hoặc quét một dataset mới qua trình duyệt.

Đóng gói một file HTML để mang đi demo (Python stdlib, dùng venv của repo):

```sh
.venv/bin/python web/neo-viewer/build.py --output reports/generated/neo-viewer-v1.html
```

Mở file HTML vừa tạo bằng Chrome/Safari/Firefox. Builder từ chối ghi đè output cũ; dùng tên mới cho mỗi bản. Có thể mở `index.html` trực tiếp nếu giữ đủ các file cùng thư mục.

## Demo và nguồn

`demo.js` chứa playback của evidence đã công bố, không phải kết quả tìm kiếm mới:

- Ba đường C=4/5/5 được chép có cấu trúc từ [ranking-C-example.md](../../reports/neo/ranking-C-example.md) tại `f0e6899`; giữ thứ tự bước, ledger, giả định và cap. Đây là brief-level playback, không giữ toàn bộ trace gốc. Source SHA256 nằm trong payload. Tọa độ chỉ phục vụ trình bày.
- Summary WRAITH được giữ nguyên từ [remediation-rediscovery-results.json](../../reports/neo/remediation-rediscovery-results.json) tại cùng revision. Summary chỉ có quan hệ bị gỡ và số liệu trước/sau, **không có witness của bypass**; viewer không tự dựng đường đó. Giữ cả kết quả `neo_refine` hết cap.
- Khảo sát nhiều nguồn giữ nguyên [decision-sample.json](../../reports/neo/decision-sample.json): 5 nguồn độc lập, 10 cặp, cắt 15/30 đường mẫu nhưng 0/10 cặp bị ngắt. Các file demo được kiểm khớp nguồn đã công bố trong tests.

Kiểm adapter và tương tác DOM bằng Node 24.15+ (chỉ phục vụ phát triển, không cần để mở viewer):

```sh
npm ci --prefix web/neo-viewer --ignore-scripts
npm test --prefix web/neo-viewer
```

`jsdom` là dependency kiểm thử đã khóa phiên bản; không được đưa vào HTML hoặc cần cho người xem demo. CI chạy các kiểm tra này và build một file HTML.

Mã UI sử dụng DOM `textContent` và SVG thuộc tính số cho nội dung file; không render HTML từ JSON, không gọi tài nguyên ngoài. Dữ liệu nhập được xem như báo cáo do người dùng cung cấp, không được UI chứng thực provenance/replay.

Đã kiểm demo ba view trong Brave 152.1.94.119 ở 1366×768 và 720×900, gồm chọn đường/cạnh/nút, lọc nguồn, chuyển phase/strategy, kéo node, zoom, vừa khung, cuộn và bàn phím.
HTML tự chứa không có script/CSS ngoài; các demo vẫn thao tác được khi ngắt mạng của tab bằng DevTools.
Chi tiết input, giới hạn kiểm trình duyệt, screenshot và revision nằm trong [nghiệm thu](../../reports/neo/thesis-v1/acceptance.md).
[Helper GoodHound](../../docs/research/evidence/goodhound-20261024/README.md) đã được thu hồi đúng hash; không tuyên bố toàn bộ nghiên cứu đã tái lập.
Các mở rộng engine/dataset/backend là add-on sau bàn giao.
