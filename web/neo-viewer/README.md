# neo graph viewer

Mở `index.html` trực tiếp trong trình duyệt. Không cần cài dependencies, server, Docker hoặc kết nối AD.
Viewer chỉ đọc kết quả; không chạy query, sửa graph, chấm lại C hoặc thực thi remediation.

- **Đường & công sức:** chọn chương trình; bấm cạnh/nút để xem actor, nguồn quyền, đích, ledger và giả định. Kéo nút hoặc nền để bố trí, dùng zoom và Vừa khung.
- **Remediation:** chọn can thiệp, strategy và DA/EA; chuyển Trước/Sau để xem quan hệ bị gỡ và kết luận tìm lại.
- **Khảo sát nhiều nguồn:** bảng 10 cặp từ 5 nguồn độc lập; lọc một nguồn để xem DA/EA, chọn hàng để xem C trước/sau và số chương trình bị cắt. Cohort công bố cắt 15/30 chương trình nhưng 0/10 cặp bị ngắt. Không tự suy đường từ ledger.
- **Mở JSON:** đọc file trên máy, không upload hoặc lưu trình duyệt. Hỗ trợ output của query CLI (`semantic.materialized`, `semantic.candidates`, optional `semantic.top_k`), `neo-decision-sample/1.0.0` và `neo-remediation-rediscovery-summary/1`. Dùng JSON của query riêng trong output `neo_domain`/`neo_baseline` để vẽ graph; không dùng snapshot hoặc `cells.jsonl`.

Tối đa 25 MB/file, 200 candidates/query và 120 bước/chương trình. Top-K giữ nguyên thứ tự của engine; thiếu ledger/C không được suy thành 0. Đồ thị biểu diễn **request source → target**, không phải canonical BloodHound edges; actor/context được giữ riêng trong chi tiết. Khi JSON không kèm nhãn/type, viewer dùng ID và ký hiệu đối tượng chưa rõ type.

Viewer cũng nhận `neo-decision-sample/1.0.0` cho bảng khảo sát; summary này không thay được JSON query đầy đủ để vẽ witness. Đây là UI đọc kết quả đã chạy, chưa khởi chạy engine hoặc quét một dataset mới qua trình duyệt.

Đóng gói một file HTML để mang đi demo (Python stdlib, không cần venv):

```sh
python web/neo-viewer/build.py --output reports/generated/neo-viewer-v1.html
```

Mở file HTML vừa tạo bằng Chrome/Safari/Firefox. Builder từ chối ghi đè output cũ; dùng tên mới cho mỗi bản. Có thể mở `index.html` trực tiếp nếu giữ đủ các file cùng thư mục.

## Demo và nguồn

`demo.js` chứa playback của evidence đã công bố, không phải kết quả tìm kiếm mới:

- Ba đường C=4/5/5 được chép có cấu trúc từ [ranking-C-example.md](../../reports/neo/ranking-C-example.md) tại `f0e6899`; giữ thứ tự bước, ledger, giả định và cap. Đây là brief-level playback, không giữ toàn bộ trace gốc. Source SHA256 nằm trong payload. Tọa độ chỉ phục vụ trình bày.
- Summary WRAITH được giữ nguyên từ [remediation-rediscovery-results.json](../../reports/neo/remediation-rediscovery-results.json) tại cùng revision. Summary chỉ có quan hệ bị gỡ và số liệu trước/sau, **không có witness của bypass**; viewer không tự dựng đường đó. Giữ cả kết quả `neo_refine` hết cap.

Để kiểm tra adapter bằng Node (chỉ phục vụ phát triển):

```sh
node --test web/neo-viewer/model.test.cjs
```

Mã UI sử dụng DOM `textContent` và SVG thuộc tính số cho nội dung file; không render HTML từ JSON, không gọi tài nguyên ngoài. Dữ liệu nhập được xem như báo cáo do người dùng cung cấp, không được UI chứng thực provenance/replay.

Đã kiểm adapter và tương tác bằng DOM unit checks (chọn đường/cạnh, chuyển phase/strategy, import, trạng thái no-path và nội dung HTML trong nhãn). Chưa kiểm layout, kéo chuột hoặc responsive bằng screenshot trình duyệt trong môi trường cloud; cần kiểm trực quan bản đầu trước khi chốt giao diện.
