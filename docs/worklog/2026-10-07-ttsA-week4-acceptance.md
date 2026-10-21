# Worklog - 2026-10-07 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#208](https://github.com/nairyuuu/ad-weighted-graph/issues/208) / Nhánh `feat/208-week4-acceptance` -> `develop`, reviewer yêu cầu `nairyuuu` / M3, Week 4.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.
- Baseline: `develop@adee0896009d6180e68fc3d911a4d21aa22c9713` sau khi merge các PR #221 (Query API), PR #222 (Snapshot facts), PR #225 (Core mapping), PR #220 (Scoring).

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Khởi tạo nhánh làm việc độc lập | `git checkout -b feat/208-week4-acceptance upstream/develop` | Tạo nhánh trên nền commit `adee0896009d6180e68fc3d911a4d21aa22c9713` |
| Rà soát và đính chính tài liệu A | `docs/research/week4-query-scenario-mapping.md`, `docs/worklog/2026-10-07-ttsA-issue206-query-mapping.md` | Đính chính nhận định sai: DA checkpoint là mốc đặc quyền cao hoặc nhánh rẽ thay thế, không phải điều kiện bắt buộc mọi đường tới tài sản phải qua |
| Xây dựng runner nghiệm thu 30 ca | `scripts/research/week4_acceptance_runner.py` | Tạo bộ thực thi kiểm chứng 30 ca độc lập bao phủ toàn bộ ma trận nghiệm thu; hỗ trợ kiểm tra tính tất định và lọc theo mã ca |
| Xuất bản kê bằng chứng nghiệm thu | `reports/research/week4-acceptance-manifest.json`, `tests/fixtures/ranking/week4_acceptance_cases.json` | Hai lượt chạy sạch cho ra kết quả băm JSON đồng nhất tuyệt đối từng byte (SHA-256: `2b1c81ab80f756e6c8e92557ef102f1b133f9662d3d33bb771681f82c22cf6a8`) |
| Xây dựng bài kiểm thử tự động | `tests/test_week4_acceptance_manifest.py` | 3 bài kiểm tra xác minh mã băm tập tin cấu hình, tính tất định hai lượt chạy và tính toàn vẹn của kết luận nghiệm thu |
| Soạn ma trận nghiệm thu tuần 4 | `docs/reports/week4-acceptance-matrix.md` | Tài liệu ma trận 30 ca chi tiết, phân định rõ kết quả kỳ vọng độc lập và kết quả thực tế của engine, kèm phân tích lỗi biên |
| Soạn báo cáo nghiệm thu tuần 4 | `docs/reports/week4-report.md` | Báo cáo 1-3 trang bằng tiếng Việt, phân tách rõ đóng góp A/B, ví dụ tính C/P/I trực quan, phản ánh trung thực lỗi biên và các mục chờ xử lý; không chứa mã số issue/PR |
| Soạn kịch bản trình diễn tuần 4 | `docs/reports/week4-demo.md` | Kịch bản demo tiếng Việt với lệnh cụ thể, đầu vào/đầu ra thực tế cho 4 nhóm kịch bản và xác nhận mã băm; không chứa mã số issue/PR |
| Soạn tài liệu bàn giao tuần 5 | `docs/reports/week5-handoff.md` | Xác định cặp điểm xuất phát/đích, 3 đường đi ứng viên điển hình và định nghĩa can thiệp điểm nghẽn dự kiến; không triển khai giải pháp trong tuần 4 |
| Kiểm tra chất lượng mã nguồn | `.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .` | Tất cả kiểm tra lint và format đều vượt qua thành công |
| Kiểm tra repository và contract | `.venv/bin/python scripts/check_repository.py && .venv/bin/python scripts/check_contract.py` | Kiểm tra thành công trên toàn bộ tập tin được theo dõi; hợp đồng dữ liệu hợp lệ |
| Kiểm tra toàn bộ test suite | `.venv/bin/python -m pytest` | 1.926 passed, 12 skipped (theo chính sách dữ liệu), 48 subtests passed |

## Điều học được / quyết định

- Việc nghiệm thu tuần 4 phải phản ánh trung thực trạng thái thực tế của hệ thống; không được tuyên bố hoàn thành toàn diện khi các điều kiện nghiệm thu cốt lõi còn phụ thuộc vào các module chưa hoàn tất của đồng nghiệp.
- Ghi nhận và phân loại rõ ba lỗi biên tích hợp đã tái hiện thành công trên nhánh phát triển chính:
  - Lỗi bộ điều phối giữ nguyên phạm vi tìm kiếm toàn diện (`exhaustive_within_scope`) và cờ tối ưu chứng minh được (`is_minimum_proven_over_scope=True`) dù ứng viên đã bị bộ chuyển đổi đánh giá loại bỏ; trạng thái đúng phải hạ cấp sang `best_in_bound_subset` và `False`.
  - Lỗi bộ chuyển đổi ném ngoại lệ xác thực khi gặp đường đi 0 bước (điểm xuất phát trùng hoặc đã đạt mục tiêu không cần chuyển tiếp) do kiểm tra cứng phần tử đầu tiên của danh sách nút.
  - Lệch cấu trúc dữ liệu giữa tài liệu kịch bản và mã nguồn engine: giá trị nỗ lực tối thiểu nằm trong từ điển con `min_effort` thay vì trường phẳng.
- Kỹ thuật mở rộng Kerberoasting đã được TTS B gửi PR #230 kèm bằng chứng tái lập hai lượt đồng nhất; TTS A ghi nhận trạng thái chờ phản biện chéo và hợp nhất chính thức trước khi khép lại nghiệm thu.
- Các kỹ thuật AS-REP Roasting (Issue #228) và RBCD (Issue #229) cùng gói công cụ giao diện dòng lệnh (Issue #213) chưa có mã nguồn hoàn thiện, query API hiện từ chối an toàn đóng; các mục này được ghi nhận trạng thái PENDING B.
- Việc tuân thủ chính sách bảo mật dữ liệu đối với bộ dữ liệu nội bộ SEAMLESS được kiểm chứng chặt chẽ: mã nguồn kiểm thử không chứa dữ liệu thô nhạy cảm, tự động phát hiện và kích hoạt trạng thái bỏ qua hợp lệ với mã thoát quy định, không thay thế bằng dữ liệu giả lập tùy tiện.
- Toàn bộ tài liệu báo cáo và kịch bản trình diễn tuân thủ nghiêm ngặt quy định không đề cập tới mã số định danh issue/PR hay nền tảng GitHub nhằm đảm bảo tính khách quan và tính độc lập của văn bản nghiên cứu.

## Trở ngại và việc kế tiếp

- Trở ngại: Các lỗi biên của Issue #212 cần được TTS B chỉnh sửa trong mã nguồn engine; các kỹ thuật #228, #229 và CLI #213 cần được bàn giao và tích hợp đầy đủ.
- Việc kế tiếp: Đẩy commit lên nhánh `feat/208-week4-acceptance`, tạo PR gửi TTS B (`@nairyuuu`) làm người phản biện, liên kết tới Issue #208.
- Tiếp tục giữ trạng thái MỞ (OPEN) cho Issue #208 cho đến khi các lỗi biên được khắc phục và các kỹ thuật mở rộng được bàn giao hoàn tất.

## Đính chính ngày 08/10/2026 sau review

Các dòng ngày 07/10 ở trên được giữ làm lịch sử, không phải chứng nhận hiện hành.
Review PR #231 tại head `21846233fdc270df212e38a85678d6b6b07c61f0` phát hiện baseline PASS vô điều kiện, metadata runtime hardcode, prerequisite demo sai và ví dụ điểm số không có binding.
Tái hiện first-call mutation trả no_path/0 paths/goal false vẫn PASS; ba test cũ xanh nên không chứng minh predicate acceptance độc lập.
Runtime macOS/Python 3.14.7 và giờ/evaluator cố định trong runner cũ không phải quan sát của lượt chạy mới.
Các claim probe SKIP/exit 2, trạng thái remote và audit tài liệu trước đây chưa được runner thực thi; không dùng làm evidence mới.

Bản sửa tách oracle assertions khỏi output baseline, so mọi normative field, ghi runtime/source/input hashes thực tế và so semantic payload riêng metadata.
Hai lỗi engine được xác nhận có điều kiện theo observed signature; thay đổi bất ngờ trả FAIL/exit 1, không giữ nhãn lỗi vô điều kiện.
Adapter defect được tái hiện qua public query thật: sinh 3 đường, đánh giá 2, đường effort 2 bị loại nhưng incumbent effort 5 vẫn mang proof toàn scope.
Zero-action giữ semantic goal true nhưng mất candidate ở adapter; yêu cầu công khai zero new work không cho phép tự tạo canonical P/I ratings.
Báo cáo/demo/handoff dùng D/M-D/M-I và Ledger E thật của fixture tổng hợp, bỏ các số roasting không có căn cứ.
Chuỗi roasting phải có request, secret recovery, activation đúng context rồi entitlement/resource; không suy usable identity từ ticket material.
Chi tiết validation, source freeze và phụ thuộc có ngày nằm trong [worklog sửa review](2026-10-08-ttsA-week4-review.md).
Không nhận các claim A hoàn tất 100%, policy certification, private-run acceptance hoặc full-week acceptance từ evidence cũ.
