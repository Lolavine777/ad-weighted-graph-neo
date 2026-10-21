# Gói bàn giao chấm điểm Week 4 (Issue #207)

Ngày 07/10/2026.
Owner: TTS A (@Lolavine777).
Reviewer: TTS B (@nairyuuu).
Thực hiện [Issue #207](https://github.com/nairyuuu/ad-weighted-graph/issues/207), tham chiếu ADR-0013 và kế hoạch Week 4.

## 1. Tổng quan gói bàn giao

Thư mục này chứa các gói chấm điểm có version, digest và kết quả kiểm chứng cho Week 4.
Các gói tuân thủ giao thức xếp hạng hiện hành của PathRankingEngine (Specification v1.0.0) và CLI.
Tất cả dữ liệu được thiết kế nhằm kiểm chứng toán học các nguyên lý xếp hạng đường dẫn, không thay đổi 21 tham số Week 3 và không tự tạo semantic mới ngoài ADR-0013.

## 2. Danh mục Artifacts

- [synthetic-a2-e.json](synthetic-a2-e.json): Gói fixture synthetic A2 dưới Ledger E, kiểm chứng Min-Effort ngược cấu trúc và Pareto không so sánh được.
- [synthetic-a2-t.json](synthetic-a2-t.json): Gói fixture synthetic A2 dưới Ledger T, kiểm chứng thế hòa 3 bên của Min-Effort.
- [synthetic-a2-ties.json](synthetic-a2-ties.json): Gói fixture synthetic A2 kiểm chứng cơ chế phá hòa công sức theo ADR-0013 Mục 4 với điểm xác suất P = 1/2.
- [synthetic-a2-diagnostics.json](synthetic-a2-diagnostics.json): Gói fixture synthetic A2 kiểm chứng phân vùng chẩn đoán fail-closed (blocked, unknown, likelihood_unrated, effort_unrated, impact_unrated).
- [week4-seamless-disposition.json](week4-seamless-disposition.json): Bản ghi rà soát tham số SEAMLESS Week 3 và tuyên bố unrated minh bạch cho các kỹ thuật Week 4.
- [actual-evaluator-results.json](actual-evaluator-results.json): Kết quả thực tế chạy qua canonical PathRankingEngine v1.0.0 cho tất cả các gói.
- [validation-summary.json](validation-summary.json): Báo cáo tóm tắt trạng thái kiểm chứng và mã băm SHA-256 của từng artifact.
- [manifest.sha256](manifest.sha256): Tập tin mã băm SHA-256 byte-level dùng để xác thực toàn vẹn bằng sha256sum.

## 3. Bảng kết quả định lượng

### Bảng 1: Kết quả đánh giá trên Ledger E (synthetic-a2-e.json)

| Ứng viên | Số bước cạnh | Các work unit | Công sức C | Khoảng xác suất P | Tác động I | Min-Effort | Pareto Frontier |
| --- | :---: | --- | :---: | :---: | :---: | :---: | :---: |
| cand_direct | 1 | w-auth-context, w-direct-admin | 5 | [2/5, 27/40] (40,0% - 67,5%) | High | Không tối ưu | Thuộc Frontier |
| cand_member_direct | 2 | w-auth-context, w-direct-admin | 5 | [2/5, 27/40] (40,0% - 67,5%) | High | Không tối ưu | Thuộc Frontier |
| cand_member_inherited | 2 | w-auth-context, w-inherited-admin | 2 | [12/25, 18/25] (48,0% - 72,0%) | High | Tối ưu (C = 2) | Thuộc Frontier |

Nhận xét:
Chương trình M/I có 2 bước cấu trúc nhưng đạt công sức 2, nhỏ hơn chương trình D chỉ có 1 bước nhưng công sức 5.
Hai khoảng xác suất [2/5, 27/40] và [12/25, 18/25] giao nhau nên không khoảng nào trội hơn khoảng kia theo định nghĩa bảo thủ.
Do đó cả 3 ứng viên cùng nằm trên Pareto frontier.
Đồng thời, cand_direct và cand_member_direct có đúng cùng giá trị C và P vì bước membership M thụ động không thêm công sức.

### Bảng 2: Kết quả đánh giá trên Ledger T (synthetic-a2-t.json)

| Ứng viên | Số bước cạnh | Các work unit | Công sức C | Khoảng xác suất P | Tác động I | Min-Effort | Pareto Frontier |
| --- | :---: | --- | :---: | :---: | :---: | :---: | :---: |
| cand_direct | 1 | w-auth-context, w-direct-admin | 2 | [2/5, 27/40] | High | Hòa (C = 2) | Thuộc Frontier |
| cand_member_direct | 2 | w-auth-context, w-direct-admin | 2 | [2/5, 27/40] | High | Hòa (C = 2) | Thuộc Frontier |
| cand_member_inherited | 2 | w-auth-context, w-inherited-admin | 2 | [12/25, 18/25] | High | Hòa (C = 2) | Thuộc Frontier |

Nhận xét:
Cả 3 chương trình đều đạt công sức bằng 2.
Baseline Min-Effort ghi nhận giá trị tối thiểu là 2 và không loại bỏ ứng viên hợp lệ nào.

### Bảng 3: Kết quả phá hòa điểm xác suất (synthetic-a2-ties.json)

| Ứng viên | Công sức C | Điểm xác suất P | Tác động I | Kết quả Pareto Frontier | Ghi chú |
| --- | :---: | :---: | :---: | :---: | --- |
| cand_direct | 5 | 1/2 | High | Bị loại bởi M/I | C lớn hơn (5 > 2) |
| cand_member_inherited | 2 | 1/2 | High | Giữ lại duy nhất | C nhỏ hơn (2 < 5) |

Nhận xét:
Khi P là điểm duy nhất bằng nhau và I bằng nhau, điều kiện phá hòa hẹp theo ADR-0013 Mục 4 kích hoạt.
Ứng viên M/I với C = 2 áp đảo hoàn toàn D với C = 5.

#### Bảng 4: Phân vùng chẩn đoán (synthetic-a2-diagnostics.json)

| Ứng viên | Cổng thực thi | Trạng thái công sức | Khoảng xác suất | Tác động | Lý do chẩn đoán |
| --- | :---: | :---: | :---: | :---: | :---: |
| cand_blocked_firewall | blocked | ineligible | Thu hồi (None) | High | blocked, likelihood_unrated |
| cand_unknown_service | unknown | ineligible | Thu hồi (None) | High | unknown, likelihood_unrated |
| cand_missing_likelihood_basis | feasible | rated (C = 5) | Thu hồi (None) | High | likelihood_unrated |
| cand_assumed_gate_unrated_basis | feasible (assumed runtime_session_alice) | rated (C = 5) | Thu hồi (None) | High | likelihood_unrated |
| cand_unrated_effort | feasible | unrated (None) | Thu hồi (None) | High | likelihood_unrated (kèm effort_status: unrated) |
| cand_unrated_impact | feasible | rated (C = 5) | [1/4, 1/4] | unrated (None) | impact_unrated |

Nhận xét:
Toàn bộ 6 ứng viên đều có ít nhất một lý do không đủ điều kiện rủi ro nên Pareto frontier rỗng.
Min-Effort hoạt động độc lập với Pareto và chọn cand_assumed_gate_unrated_basis (C = 5, associated_impact: High).
Các ứng viên feasible có công sức rated gồm cand_assumed_gate_unrated_basis (C = 5), cand_missing_likelihood_basis (C = 5) và cand_unrated_impact (C = 5).
Bộ phá hòa theo thứ tự bảng chữ cái chọn cand_assumed_gate_unrated_basis với công sức tối thiểu là 5.
Ứng viên cand_unrated_effort bị loại khỏi Min-Effort vì effort_status là unrated.
Ứng viên cand_unrated_impact nhắm đích OTHERHOST_X_ID mang đầy đủ work units scoped riêng (w-auth-otherhost: 1 và w-direct-admin-otherhost: 4) với công sức 5 và xác suất [1/4, 1/4], cách ly unrated đúng tại vị trí tác động.
Ứng viên cand_assumed_gate_unrated_basis chứng minh giả định runtime (runtime_session_alice) thỏa mãn cổng logic feasible nhưng không tự sinh xác suất.
Khi thiếu tiền tố trong bảng tra cứu, ứng viên vẫn giữ likelihood_unrated và bị cách ly vào diagnostics.

## 4. Các nguyên lý cốt lõi áp dụng

1. Chống tính lặp (Anti-double-counting):
Phép hợp các work unit duy nhất đảm bảo không nhân đôi công sức khi một đơn vị công việc được chia thành nhiều bước giải thích.
Quan hệ membership thụ động không tiêu tốn tài nguyên và không làm giảm xác suất thành công (C(D) == C(M/D) == 5, P(D) == P(M/D)).
Tái sử dụng ngữ cảnh xác thực w-auth-context không đòi hỏi thiết lập lại xác thực và chỉ tính ma sát đúng một lần (delta = 0).
Khi có công việc chủ động thực sự khác biệt, các đại lượng thay đổi đúng bằng hiệu số chi phí rubric của đơn vị công việc mới (delta = 3 giữa D và M/I).
Chuỗi lịch sử M/D/I tái sử dụng w-auth-context cho ra tổng công sức ledger là 6 thay vì 7.
Các đơn vị công việc thuộc ngữ cảnh máy đích khác nhau (w-auth-context trên Host C0 so với w-auth-otherhost trên OtherHost X) được giữ độc lập và không bị gộp trùng (1 + 1 = 2).

2. Tách bạch Min-Effort và rủi ro Pareto:
Min-Effort là truy vấn riêng biệt nhằm xác định chi phí vận hành tối thiểu của kẻ tấn công.
Risk Pareto được định nghĩa trên 2 trục chính là tác động I và xác suất P.
Công sức C tuyệt đối không được gộp với C và P thành điểm số vô hướng, mà chỉ đóng vai trò phá hòa trong điều kiện hẹp của ADR-0013.
Khi một ứng viên chưa được định mức công sức (unrated effort), quy tắc phá hòa công sức không được kích hoạt và hai ứng viên giữ nguyên trạng thái không so sánh được.

3. Phân vùng chẩn đoán an toàn (Fail-closed partitioning):
Khi thiếu bằng chứng thực nghiệm về ma sát hoặc xác suất, các ứng viên được giữ ở trạng thái unrated thay vì gán giá trị mặc định.
Giả định runtime có thể làm bước đủ điều kiện về mặt cổng logic nhưng vẫn giữ trạng thái unrated khi thiếu căn cứ chấm điểm.

4. Bảo toàn tham số SEAMLESS:
Toàn bộ 21 tham số đã được chấp thuận ở Week 3 được giữ nguyên vẹn.
Các câu hỏi về tấn công trạm làm việc nguồn và kỹ thuật cracking hash ngoại tuyến (AS-REP roasting, Kerberoasting) được phân loại minh bạch là unrated chờ dữ liệu thực nghiệm.

## 5. Hướng dẫn kiểm chứng và tái lập

Công cụ đánh giá cung cấp hai chế độ thực thi tách biệt:
Chế độ `--verify` (mặc định) là kiểm tra chỉ đọc (read-only) các artifacts hiện có trên đĩa, xác thực mã băm SHA-256 từ `manifest.sha256` và so sánh kết quả tính toán độc lập / canonical evaluator với dữ liệu đã lưu; nếu phát hiện sai khác sẽ báo lỗi và dừng mà không ghi đè bất kỳ tệp tin nào.
Chế độ `--generate` dùng khi cần phát sinh lại các tệp gói JSON, thực thi canonical evaluator và cập nhật tệp kết quả actual cũng như `manifest.sha256`.

Để chạy bộ kiểm tra toàn vẹn và thực thi engine:

```bash
# 1. Chạy kiểm chứng chỉ đọc (read-only) chuyên dụng Week 4
./.venv/bin/python scripts/research/week4_scoring_eval.py --verify

# 2. Chạy bộ kiểm thử pytest cho Week 4 scoring (bao gồm kiểm tra invariant và phát hiện drift)
./.venv/bin/pytest -v tests/test_week4_scoring.py

# 3. Kiểm tra mã băm SHA-256 của các artifact bằng công cụ hệ thống
sha256sum -c docs/research/ratings/week4/manifest.sha256
```
