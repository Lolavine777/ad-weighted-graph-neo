# Nghiệm thu Neo cho khóa luận, 25/10/2026

Phiên bản bàn giao: **neo-thesis-v1**, commit được xác định bởi annotated tag cùng tên và [tổng kết issue #4](https://github.com/Lolavine777/ad-weighted-graph-neo/issues/4).
Core/search, semantics, bảng C, budget và dependencies giữ nguyên baseline `6fb88e05b4c835b1645a8cf9ac2fc7a6acb539c6`.
[Biên bản máy đọc được](verification.json) giữ hash HTML, source viewer, screenshots và kết quả mới; CI đúng SHA nằm trong issue.

## Hai use case và demo

1. **Một nguồn bị lộ:** mở viewer, chọn đường và bước để đọc C, ledger và giả định; demo SEAMLESS có ba đường C=4/5/5.
   Chạy `scripts.neo_baseline` theo README để tạo kết quả mới, rồi nhập trực tiếp `neo_guided.json`.
2. **Khảo sát/can thiệp:** lọc nguồn trong survey, chọn DA/EA để đọc C trước/sau; demo cắt 15/30 chương trình nhưng 0/10 cặp bị ngắt.
   Mở remediation để xem ba ca WRAITH, chọn strategy/đích rồi chuyển Trước/Sau; nhập trực tiếp `results.json` từ `scripts.neo_remediation`.

Build từ repo root bằng `.venv/bin/python web/neo-viewer/build.py --output reports/generated/neo-thesis-v1.html` rồi mở HTML.
Tên output phải mới vì builder từ chối ghi đè.
Không cần backend/CDN/Docker để xem demo; engine chạy CLI.
`neo_domain` xuất brief/`cells.jsonl`, không phải JSON query cho viewer; summary cũng không chứa witness bypass để vẽ thêm đường.
SEAMLESS và WRAITH trong README tải từ nguồn public có manifest pin; raw và outputs chỉ lưu local, không nằm trong Git.
Fixture “Query nhỏ có chi phí” dùng ranking legacy: kiểm đọc đường trong viewer, C đọc từ brief CLI; viewer lấy C/ledger từ `semantic.top_k` của neo.

## Kiểm thực tế trong lượt này

| Phép kiểm | Kết quả mới |
| --- | --- |
| Viewer Node adapter/DOM | 22 pass, 0 skip; có hồi quy cú pháp JSON và giới hạn file, không thay thế browser |
| Archive GoodHound | 3 pytest pass, gồm Git checkout `core.autocrlf=true`; hai manifest và tám helper/time policy khớp hash công bố |
| Quality | Ruff check/format, yamllint, repository và contract pass |
| Checkout mới, Python 3.14.7 | `uv venv` + `uv pip sync` lock, npm ci, query fixture + brief và standalone build thành công |
| SEAMLESS baseline | Tải/kiểm 6 file, chạy đúng recipe README, native replay/API-CLI parity pass; neo-guided C=1, 6 expansions, best-found |
| WRAITH | Tải/kiểm 31 file, import và runner đúng README; 24 lượt, 200 witness replay/ledger hợp lệ; C/outcomes khớp bản công bố, baseline giữ nguyên |
| GoodHound | Tải ZIP pin, dựng ba manifest khớp lịch sử; import 1.387 nodes/24.781 edges; controls 40 witness replay/ledger, ranking rerun khớp IDs/C và Top-3=3/4/4 |

Brave **152.1.94.119 trên macOS**, viewport **1366×768** và **720×900**: đã kiểm paths/survey/remediation, chọn đường/cạnh/nút, lọc nguồn/đích, trước/sau/strategy, kéo node/nền, zoom/vừa khung, cuộn và Enter/Space.
Đã nhập query CLI, survey/remediation thiếu metadata và `results.json` WRAITH vừa chạy; file nhập giữ nhãn trung tính, không tự nhận dataset/scenario demo.
Native thiếu decisions hiện “chưa đầy đủ”, khác danh sách assumptions rỗng; đã kiểm riêng C=0, chưa chấm C, có đường, bypass, no-path trong scope, hết budget và thiếu điều kiện.
Các ca native thiếu trace/C=0/hết budget/thiếu điều kiện/no-path và ID rất dài dùng fixture synthetic kiểm UI, không phải kết quả thực nghiệm AD mới.
JSON sai cú pháp/schema giữ nguyên báo cáo đang xem; cú pháp sai có thông báo tiếng Việt.
Đã tái hiện và sửa tiêu đề ID dài đẩy kết luận ra ngoài workspace; browser assert/screenshot sau sửa xác nhận status trong khung ở cả hai viewport.
Đã tái hiện và sửa giới hạn 25 MB chặn `neo_guided.json` mặc định khoảng 95 MB; giới hạn mới 128 MB, chính file thật đã nhập thành công với C=1, ledger và 7 assumptions.
Giữ giới hạn 200 candidates/query và 120 bước/chương trình; file trên 128 MB bị từ chối trước khi đọc.
Đã sửa rule Git sau khi tái hiện manifest đổi newline trên checkout `core.autocrlf=true`; không sửa bytes helper/manifest lịch sử.

[Ảnh demo](screenshots/paths-assumptions.jpg), [survey hẹp](screenshots/survey-narrow.jpg), [bypass/cap](screenshots/remediation-bypass-cap.jpg), [native CLI thật](screenshots/import-native-baseline.jpg), [ID dài sau sửa](screenshots/import-long-narrow.jpg), [lỗi JSON](screenshots/import-invalid-json.jpg).
HTML không có script/CSS ngoài và thao tác demo/import vẫn chạy khi DevTools đặt mạng của tab ở offline.
Công cụ chặn giao thức `file:` nên kiểm browser qua server tĩnh chỉ bind `127.0.0.1`; không tuyên bố đã kiểm thao tác double-click file.
Đây là giới hạn phương pháp kiểm, không phải phụ thuộc backend của artifact.

## Hoàn tất và giới hạn chấp nhận

A–C và phần đóng gói E đã có bằng chứng; không còn lỗi chặn đã biết trong hai use case đã chốt.
Phát triển engine/dataset/backend mới thuộc add-on sau baseline này.
Repo gốc, thay đổi có sẵn và volume Docker giữ nguyên; không gộp PR dependency.
[Helper/recipe GoodHound](../../../docs/research/evidence/goodhound-20261024/README.md) được phục hồi nguyên bản.
**D khép theo ngoại lệ minh bạch:** input/native controls đã kiểm; hai matrix cohort cũ chỉ làm đầu vào hash freeze, full cohort/remediation/CE không chạy lại trong wrap-up.
CE driver còn phụ thuộc paths/project/ports lịch sử; cần project/volume mới và ghi nhận sửa portability trên bản sao cho lượt mới.
Vì vậy chưa tuyên bố tái lập đầy đủ toàn nghiên cứu GoodHound từ checkout; điều này không thay kết luận demo chính.

Đề gốc yêu cầu minimum-C từ node bất kỳ; hiện **chưa đạt bảo đảm đó trên dữ liệu thật**.
C là effort theo rubric `neo-c-v1`, kết quả là best-found trong tập đã tìm trừ khi engine có proof trong scope.
Không diễn giải C thành thời gian thực hoặc tuyên bố hơn BloodHound nói chung.
Đủ chuyển sang viết luận theo phạm vi phân tích có xét công sức và kiểm tra biện pháp giảm thiểu, với các giới hạn trên.
