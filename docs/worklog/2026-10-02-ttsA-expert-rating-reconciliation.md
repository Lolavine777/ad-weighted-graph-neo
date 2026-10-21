# Worklog - 2026-10-02 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#168](https://github.com/nairyuuu/ad-weighted-graph/issues/168), [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) / [PR #170](https://github.com/nairyuuu/ad-weighted-graph/pull/170), `feature/168-expert-rating-reconciliation` / M2
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

### Bản triển khai ban đầu tại 47a76fd (lịch sử trước review)

Worklog này ghi nhận kết quả triển khai công cụ đối soát hai phiếu chấm điểm độc lập (Issue #168) từ nhánh `develop` mới nhất tại commit `b3a57b8`.
Công việc ban đầu hướng tới quy chế quản trị tại `docs/research/evidence-rating-governance.md` §3.5; review sau đó chỉ ra các khoảng trống validation và bảo vệ tệp cần sửa.
Công cụ được xây dựng dưới dạng module CLI độc lập tại `scripts/research/reconcile_rating_sheets.py`, tái sử dụng tối đa các helper chuẩn tắc hiện có từ `scripts/research/path_ranking_wire_adapter.py`.
Cả hai phiếu chấm thực tế của dự án (`tests/fixtures/ranking/seamless_rater_1.json` và `tests/fixtures/ranking/seamless_rater_2.json`) được bảo lưu nguyên vẹn 100% từng byte ở trạng thái `pending_independent_rating`.
Gói giả thiết nghiên cứu `tests/fixtures/ranking/seamless_parameter_bundle.json` và toàn bộ mã nguồn `src/engine/`, `src/parser/` của TTS B được giữ nguyên không chỉnh sửa.
Bộ ban đầu gồm 18 tests tại `tests/test_rating_sheet_reconciliation.py`, chỉ cung cấp bằng chứng cho các trường hợp đã chạy, chưa bao phủ năm findings trong review #5388173479.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| 1. Kiểm tra hiện trạng và khởi tạo nhánh | `git fetch origin develop`, `git checkout -b feature/168-expert-rating-reconciliation origin/develop` | Nhánh được tạo từ đúng HEAD `develop` tại commit `b3a57b8970d4d6c8d4dc30d1ecb894da9c0a49c6`. |
| 2. Chuẩn bị bộ fixture synthetic kiểm thử | `tests/fixtures/ranking/synthetic/*.json` | Tạo 4 phiếu synthetic gắn nhãn rõ ràng: 2 phiếu chấm đủ có đồng thuận cao, 1 phiếu bất đồng, 1 phiếu giữ lại do chồng lấn nỗ lực (`is_independent: false`). |
| 3. Xây dựng công cụ đối soát toàn diện | `scripts/research/reconcile_rating_sheets.py` | Kiểm tra schema, digest SHA-256 đầu vào; đối chiếu query scopes; ghép cặp 21 bản ghi theo khóa định danh cấu trúc; tái sử dụng `reconcile_expert_ratings` và `compute_kappa_with_fallback`; tích hợp cơ chế chống ghi đè đầu vào và xuất tệp nguyên tử. |
| 4. Xây dựng bộ kiểm thử tự động | `tests/test_rating_sheet_reconciliation.py` | 18 tests kiểm tra: tính bất biến của phiếu thật, đối soát phiếu pending, đối soát phiếu synthetic, phát hiện bất đồng, cảnh báo bất định nhận thức, phát hiện chồng lấn nỗ lực, chống ghi đè đường dẫn, và thực thi CLI. |
| 5. Soạn thảo tài liệu hướng dẫn tiếng Việt | `docs/research/rating-sheet-reconciliation-guide.md` | Hướng dẫn chi tiết cú pháp CLI, ý nghĩa các số đo, phân biệt trạng thái pending với lỗi, bảo vệ an toàn tệp và các lệnh copy-paste chạy được ngay. |
| 6. Kiểm tra an toàn và chất lượng mã | `.venv/bin/pytest tests/test_rating_sheet_reconciliation.py`, `.venv/bin/ruff`, `scripts/check_contract.py`, `scripts/check_repository.py` | 18/18 tests đối soát pass; ruff check và format sạch sẽ; contract check và repository check pass 100%. |
| 7. Kiểm tra tính bất biến của phiếu thật | `sha256sum tests/fixtures/ranking/seamless_rater_*.json` | Khớp chính xác với hash trong `seamless_evidence_manifest.json`: `b409a2fff6...` (phiếu 1) và `26bb9b58a3...` (phiếu 2). |

## Điều học được / quyết định

Thứ nhất, việc phân biệt rạch ròi giữa trạng thái cấp phiếu (`sheet.status: "pending_independent_rating"`) và trạng thái cấp từng bản ghi (`record.rating_status: "unrated"`) là chìa khóa để hỗ trợ các mẫu phiếu chưa chấm mà không vi phạm nguyên tắc quản trị.
Khi hai phiếu ở trạng thái pending, thông tin định danh người chấm có thể để trống hoặc null mà không bị xem là dữ liệu không hợp lệ.
Đồng thời, công cụ tuyệt đối không đưa các giá trị null này vào các phép toán số học như IoU hay Kappa, và không tự tiện sinh điểm mặc định để biến bản ghi chưa chấm thành đã chấm.

Thứ hai, việc ghép cặp bản ghi phải dựa trên toàn bộ các ràng buộc cấu trúc (full structural bindings) thay vì dựa vào thứ tự mảng hay chỉ số câu hỏi.
Đối với xác suất có điều kiện, phải kiểm tra cả outcome, conditioning history, quantity và scenario version bên cạnh các trường ngữ cảnh, kể cả khi bản ghi pending hoặc unmatched.

Thứ ba, kiểm tra output bằng `Path.resolve()` không bảo vệ tên tệp tạm cố định có thể đụng input hoặc symlink.
Writer phải tạo tệp tạm độc quyền, giữ handle của tệp vừa tạo, đóng handle trước khi replace trên Windows và chỉ cleanup tệp mình sở hữu.

Thứ tư, khi người dùng gọi cờ `--summary` mà không chỉ định `--output`, báo cáo JSON chuẩn được xuất ra `stdout` trong khi bản tóm tắt thân thiện với con người được chuyển hướng về `stderr`.
Điều này giúp giữ nguyên tính toàn vẹn của luồng đầu ra JSON để các script tự động khác có thể pipe trực tiếp mà không bị lỗi cú pháp.

Thứ năm, provenance của registry cần được minh bạch hóa hoàn toàn.
Khi người dùng không cung cấp tệp registry tùy chọn, hệ thống tự động sử dụng danh mục dự phòng `PINNED_WORK_UNIT_CATALOG` và tính toán mã băm SHA-256 xác định để ghi vào báo cáo kiểm toán, ngăn ngừa việc thay đổi ngầm định nghĩa đơn vị công việc.

## Cập nhật 2026-10-02: address review #5388173479

Đã fetch và kiểm tra PR #170 vẫn OPEN trên nhánh hiện có tại head `47a76fdb084b760b252dda9cbdf12851ed6c86d9` trước lượt sửa.
Đã đọc [issue #168](https://github.com/nairyuuu/ad-weighted-graph/issues/168) và [review #5388173479](https://github.com/nairyuuu/ad-weighted-graph/pull/170#pullrequestreview-5388173479).
Review là advisory COMMENT qua tài khoản A, không phải human approval hoặc nghiệm thu của B.
Các probes và regression tests dùng bản sao tạm; điểm synthetic được gắn nhãn và không ghi vào phiếu thật.

| Finding | Tái hiện và thay đổi | Bằng chứng local |
| --- | --- | --- |
| P1: tên tệp tạm cố định | CLI cũ làm mất bản sao input hoặc sửa input qua symlink tại `.report.json.tmp.<pid>`; writer chuyển sang `NamedTemporaryFile` tạo độc quyền cùng thư mục output. | Tests collision input/sentinel/symlink và lỗi create/write/replace kiểm tra byte đầu vào, output cũ và cleanup. |
| P1: envelope, identity, version, status | Synthetic copies với thiếu envelope, version `99.0.0`, evaluator cùng tên hoặc rated thiếu identity/basis từng được chấp nhận; nay validation chạy trước helper. | CLI từ chối input sai, giữ output cũ và không tạo report mới; template pending với identity/điểm null vẫn hợp lệ. |
| P1: binding likelihood/effort | Quantity tích lũy, outcome/history sai, scenario version thiếu và scope effort pending mâu thuẫn từng đi qua; nay kiểm tra đủ định nghĩa và canonical/registry conflicts trước pairing. | Regression tests chạy cả rated/pending/unmatched, prefix IDs và opaque registry metadata. |
| P2: audit mất dữ liệu | Helper result thiếu raw sources/rationale/rubric và full scopes; báo cáo 1.1.0 thêm raw records, full bindings, metadata và scopes. | CLI audit tests khôi phục đúng từng bản ghi ở rated, disagreement, overlap, pending và unmatched; kết quả deterministic và `human_acceptance: "pending"`. |
| P2: Windows immutability | Chuyển LF sang CRLF trên bản sao tái hiện đúng hash lỗi `125106249d0...`; không có bằng chứng tool sửa phiếu thật từ lỗi hash này. | Tests lấy raw bytes/hash trước và sau CLI trên bản sao LF/CRLF; giữ nguyên thuật toán digest của CLI. |

Lượt red đầu của bộ regression mới ghi nhận `80 failed, 6 passed` trên implementation cũ, đúng các khoảng trống validation, writer và audit đã nêu.
Bổ sung probes sau đó phát hiện prefix canonical thiếu context/ledger và envelope pending thiếu trường bắt buộc; từng nhóm được chạy red rồi green.
Independent code review bổ sung một lỗi trong lượt sửa: cấm chuỗi `PENDING` quá rộng làm từ chối rationale/URL hợp lệ có từ `pending`.
Sáu CLI regression tests tái hiện lỗi này red rồi green; restriction được tách riêng cho evaluator/binding, giữ nguyên văn rationale, nguồn và mô tả người chấm.
Trên Python 3.14.2, `.venv/bin/python -m pytest tests/test_rating_sheet_reconciliation.py tests/test_rating_sheet_reconciliation_review.py -q` đạt `140 passed`.
`.venv/bin/python -m pytest -q` đạt `1261 passed, 1 skipped, 48 subtests passed`; skip là Windows junction test trên Linux.
Local Linux không thay cho required Windows CI ở đúng pushed head.
`ruff check .`, `ruff format --check .`, `yamllint .`, `check_contract.py`, `check_repository.py` và Compose config với `NEO4J_PASSWORD` placeholder đều pass.
Các lệnh CLI trong guide được chạy để đối chiếu behavior; synthetic pair có 21 cặp đã chấm, 17 proposals và 4 bất đồng likelihood, không phải human consensus.
Git diff so với head trước sửa xác nhận actual sheets, research bundle, `src/engine/`, `src/parser/` và `path_ranking_wire_adapter.py` không đổi.
Hash raw bytes local của hai phiếu thật vẫn là `b409a2fff62f3036a1970eecdef5c8d886fa02aa190de338c8d7ad0435ef1e66` và `26bb9b58a3db12afa7386c114f4dca564c51f0987b7495344ade91308b32c3bf`.
Verification Git/blob được tách khỏi tests runtime để newline của checkout Windows không bị hiểu nhầm là thay đổi do CLI.

### CI sau push code fix

[CI run 36964396200](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36964396200) của head `8f308de14001e0baa281b93dc2e5b81b801be6c3` đã SUCCESS cho Ubuntu, Windows, quality và Compose.
GitHub Actions checkout PR merge revision `68761a8`, kết hợp head trên với `develop` tại `63f3ce582d6be01f810061a8b15897e44d84805f`; đây là snapshot khác local branch, không thay số đếm local bằng số đếm CI.
Trên Python 3.14.7, [Ubuntu job](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36964396200/job/110704861024) ghi `1282 passed, 9 skipped`, và [Windows job](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36964396200/job/110704860921) ghi `1281 passed, 10 skipped`.
[Branch policy run 36964396231](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36964396231) cũng SUCCESS.
Lượt bổ sung bằng chứng này chỉ sửa worklog; required CI ở final pushed head được kiểm tra lại và liên kết trong address comment của PR #170.

## Trở ngại và việc kế tiếp

CI Windows cũ thất bại do test hash cố định với newline khác checkout; lượt sửa này thay bằng kiểm tra bất biến qua thực thi CLI và raw-byte digest.
Kết quả Ubuntu/Windows CI của code fix đã được ghi nhận ở mục trên, tách biệt với local Linux và với lượt push worklog sau đó.

PR #170 và issue #168 chưa được đóng hoặc merge trong lượt sửa này.
Address comment liên kết từng finding với tests và kết quả required CI ở đúng final head; CI không thay human acceptance.
TTS B/A/B tiếp tục review và ghi quyết định thật; human acceptance, final parameter bundle và nghiệm thu #143/#158/#48 vẫn pending theo phạm vi tương ứng.
