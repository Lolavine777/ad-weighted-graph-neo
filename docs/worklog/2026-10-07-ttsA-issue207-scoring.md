# Worklog - 2026-10-07 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#207](https://github.com/nairyuuu/ad-weighted-graph/issues/207) / M3, Week 4
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Cập nhật baseline và đọc hướng dẫn | Nhánh `docs/207-week4-scoring-handoff` từ `develop@4c1f805` | Xác nhận sạch; đọc toàn bộ #207, ADR-0013, Week 4 scenarios và ranh giới scope |
| Xây dựng công cụ kiểm chứng chấm điểm | `scripts/research/week4_scoring_eval.py` | Tạo công cụ tạo gói và đánh giá qua PathRankingEngine v1.0.0; hỗ trợ `--verify` |
| Tạo các gói rating có version/digest | `docs/research/ratings/week4/` | 5 tập tin JSON chuẩn hóa: `synthetic-a2-e.json`, `synthetic-a2-t.json`, `synthetic-a2-ties.json`, `synthetic-a2-diagnostics.json`, `week4-seamless-disposition.json` |
| Tính toán độc lập và chạy Evaluator thật | `actual-evaluator-results.json` và `validation-summary.json` | Canonical evaluator chạy thành công 4 gói; đối chiếu kết quả khớp tuyệt đối giữa tính tay và evaluator |
| Tạo SHA-256 manifest | `docs/research/ratings/week4/manifest.sha256` | 7 bản ghi byte-level SHA-256; kiểm tra bằng `sha256sum -c` đạt PASS 100% |
| Viết tài liệu hướng dẫn gói chấm | `docs/research/ratings/week4/README.md` | Bảng kết quả định lượng, phân tích nguyên lý, hướng dẫn tái lập |
| Bàn giao chi tiết Week 4 scoring | `docs/research/week4-scoring-handoff.md` | Đầy đủ 11 phần: mapping action sang work units, tính toán C/P/I, chống tính lặp, phân vùng chẩn đoán fail-closed, rà soát SEAMLESS và kế hoạch độ nhạy |
| Viết bộ kiểm thử pytest chuyên biệt | `tests/test_week4_scoring.py` | 14 bài kiểm thử bao phủ toàn bộ các bất biến của Issue #207 (bao gồm giả định runtime mở cổng nhưng unrated basis, chống tính lặp, unrated effort bảo tồn tính không so sánh được, kiểm tra read-only và phát hiện drift) |
| Xử lý review PR #220 từ TTS B | Nhánh `docs/207-week4-scoring-handoff` | Tách biệt hoàn toàn `--verify` (read-only) và `--generate`; chuẩn hóa work units riêng cho OtherHost X (`w-auth-otherhost`, `w-direct-admin-otherhost`); bổ sung test invariance tách/gộp, replay M/D/I ra effort 6 thay vì 7, negative control đa ngữ cảnh |
| Chạy kiểm thử tự động Week 4 | `./.venv/bin/pytest -v tests/test_week4_scoring.py` | 14 passed trong 0,62s |
| Kiểm tra định dạng và quy tắc repo | Ruff format/check, kiểm tra không dùng em dash, kiểm tra xuống dòng câu trong Markdown | Tuân thủ tuyệt đối các quy tắc kỹ thuật |

## Điều học được / quyết định

- Không gộp ba trục công sức C, xác suất P và tác động I thành một điểm số vô hướng.
- Min-Effort là truy vấn riêng tìm đường có tổng ma sát công việc nhỏ nhất, độc lập với biên rủi ro Pareto.
- Biên rủi ro Pareto bảo thủ bảo toàn tính không so sánh được khi các khoảng xác suất giao nhau.
- Cơ chế phá hòa bằng công sức C theo ADR-0013 Mục 4 chỉ kích hoạt trong điều kiện hẹp khi xác suất là điểm duy nhất bằng nhau và tác động bằng nhau.
- Phân vùng chẩn đoán fail-closed loại bỏ rủi ro tự ý điền số mặc định khi dữ liệu thực nghiệm chưa đầy đủ.
- Bảo tồn nguyên vẹn 21 tham số Week 3 đã được phê duyệt và giữ trạng thái unrated minh bạch cho các kỹ thuật mới.
- Lệnh `--verify` phải thuần túy là thao tác đọc (read-only), không được tự ý ghi đè làm che giấu tình trạng sai lệch hoặc hỏng tệp trên đĩa.
- Các máy đích khác nhau có ngữ cảnh bảo mật và work units độc lập, không được gộp chung dẫn đến tính sai công sức Min-Effort.
- Chuỗi thực thi phức hợp nhiều bước replaying các thao tác có chung ngữ cảnh xác thực phải được loại trừ tính lặp chính xác ở cấp độ toàn bộ chuỗi hành động.

## Trở ngại và việc kế tiếp

- Trở ngại: Giao diện truy vấn máy tính công khai (Computer X sang Y) và dữ liệu bẻ khóa hash ngoại tuyến cho AS-REP roasting/Kerberoasting chưa có sẵn trong SEAMLESS.
- Việc kế tiếp: Đẩy commit cập nhật lên PR #220 và phản hồi chi tiết 3 góp ý của TTS B (@nairyuuu); không tự sáp nhập nhánh hoặc tuyên bố hoàn tất Week 4.
