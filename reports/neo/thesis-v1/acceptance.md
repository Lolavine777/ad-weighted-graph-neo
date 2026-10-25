# Nghiệm thu Neo cho khóa luận, 25/10/2026

Mã sản phẩm được kiểm: `6fb88e05b4c835b1645a8cf9ac2fc7a6acb539c6`; thay đổi bàn giao chỉ bổ sung archive/helper, kiểm hash và tài liệu/evidence.
SHA commit bàn giao và CI được ghi tại [issue #4](https://github.com/Lolavine777/ad-weighted-graph-neo/issues/4).
**Chưa freeze/tag** vì phần nhập file trong trình duyệt thật còn chưa kiểm được, như nêu bên dưới.
[Biên bản máy đọc được](verification.json) giữ hash HTML, screenshot và kết quả mới.

## Hai use case và demo

1. **Một nguồn bị lộ:** mở viewer, chọn đường và bước để đọc C, ledger và giả định; demo SEAMLESS có ba đường C=4/5/5.
   Query CLI chạy với fixture phân phối trong repo theo mục “Query nhỏ có chi phí” của README; `toy-query.json` mở ở màn này.
2. **Khảo sát/can thiệp:** lọc nguồn trong survey, chọn DA/EA để đọc C trước/sau; demo cắt 15/30 chương trình nhưng 0/10 cặp bị ngắt.
   Mở remediation để xem ba ca WRAITH, chọn strategy/đích rồi chuyển Trước/Sau; summary không chứa witness bypass để vẽ thêm đường.

Build từ repo root bằng `.venv/bin/python web/neo-viewer/build.py --output reports/generated/neo-viewer-v1.html` rồi mở HTML.
Tên output phải mới vì builder từ chối ghi đè.
Không cần backend/CDN/Docker để xem demo; engine chạy CLI.
`neo_domain` xuất brief/`cells.jsonl`, không phải JSON query cho viewer.
Lệnh dựng WRAITH trong README tải 31 file public có manifest pin; raw và outputs chỉ lưu local, không nằm trong gói Git.

## Kiểm thực tế trong lượt này

| Phép kiểm | Kết quả mới |
| --- | --- |
| Viewer Node adapter/DOM | 20 pass, 0 skip; kiểm import/metadata/assumptions/lỗi ở DOM, không tính là kiểm browser |
| Archive GoodHound | 2 pytest pass; hai manifest khớp hash công bố và tám helper nguyên bytes khớp manifest |
| Quality | Ruff check/format và yamllint pass; contract và hai synthetic fixture hợp lệ |
| Checkout mới, Python 3.14.7 | `uv venv` + `uv pip sync` lock thành công; toy query CLI, brief và standalone build thành công |
| WRAITH từ checkout mới | Download/manifest 31 file, import và runner theo README; 24 lượt, 200 witness replay/ledger hợp lệ; baseline giữ nguyên |
| GoodHound từ checkout mới | Tải ZIP pin, dựng input và ba manifest khớp lịch sử; import 1.387 nodes/24.781 edges; controls 40 witness replay/ledger, ranking chạy lại khớp IDs/C, Top-3=3/4/4 |

Brave **152.1.94.119 trên macOS**, viewport **1366×768** và **720×900**: đã xem cả paths/survey/remediation, chọn đường/cạnh/nút, lọc nguồn/đích, chuyển trước/sau/strategy, kéo node, zoom/vừa khung, cuộn và dùng Enter/Space.
Đã phân biệt demo có đường, còn bypass, no-path trong scope và cap có witness; không thấy lỗi che kết luận trên hai viewport này.
Tên máy dài trong survey được đọc đầy đủ ở chi tiết; inspector cuộn riêng, và chuyển xuống dưới workspace ở viewport hẹp.
[Screenshot paths/assumptions](screenshots/paths-assumptions.jpg), [survey laptop](screenshots/survey-laptop.jpg), [survey hẹp](screenshots/survey-narrow.jpg), [remediation chặn](screenshots/remediation-blocked.jpg), [bypass và cap](screenshots/remediation-bypass-cap.jpg).
HTML không có script/CSS ngoài; các demo vẫn đổi view và tương tác khi DevTools đặt mạng của tab ở offline.
Công cụ chặn giao thức `file:` nên HTML được phục vụ tĩnh chỉ qua `127.0.0.1` để kiểm browser; chưa coi đó là đã kiểm double-click file trên máy người dùng.

## Hoàn tất, giới hạn và phần còn mở

**Hoàn tất:** A/B của issue, kiểm demo trực quan/tương tác nêu trên, cài mới/build và WRAITH CLI, thu hồi đúng helper lịch sử và kiểm input/native controls GoodHound.
Không thay core/search, semantics, bảng C, budget, dataset/backend hoặc số liệu lịch sử; không chạy Docker hoặc đổi volume cũ.
[Recipe GoodHound](../../../docs/research/evidence/goodhound-20261024/README.md) phân biệt helper gốc với yêu cầu môi trường và bản sao cho lượt chạy mới.
Hai matrix cohort lịch sử được sao chép chỉ để tính hash trong freeze controls; full cohort, remediation và CE không chạy lại trong wrap-up.
**Giới hạn chấp nhận của D:** GoodHound có helper và input/native controls đã kiểm, nhưng chưa tái lập đầy đủ toàn nghiên cứu từ checkout; CE cần project/volume riêng và paths/ports trên bản sao driver.
Điều này hạn chế tuyên bố về khả năng tái lập nghiên cứu GoodHound, không làm thay kết luận demo chính.

**Còn chặn nghiệm thu C/E:** extension Brave chưa cấp quyền chọn file cho công cụ, nên chưa kiểm thực tế import JSON hợp lệ/sai, native thiếu trace, native hết budget/thiếu điều kiện và metadata ngoài demo.
Các trường hợp đó có DOM tests pass nhưng chưa được đánh dấu browser pass.
Giữ issue #4 mở và chưa tạo `neo-thesis-v1` cho đến khi khép phép kiểm này; chưa phát hiện lỗi sản phẩm mới từ phần browser đã chạy.

Đề gốc yêu cầu minimum-C từ node bất kỳ; hiện **chưa đạt bảo đảm đó trên dữ liệu thật**.
C là effort theo rubric `neo-c-v1`, kết quả là best-found trong tập đã tìm trừ khi engine có proof trong scope.
Không diễn giải C thành thời gian thực hoặc tuyên bố hơn BloodHound nói chung.
Có thể viết các chương thiết kế/thực nghiệm theo phạm vi này; bản freeze sản phẩm còn đợi hoàn tất kiểm import browser nêu trên.
