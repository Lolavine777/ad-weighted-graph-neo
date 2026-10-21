# Hướng dẫn đối soát phiếu chấm điểm độc lập (Rating Sheet Reconciliation Guide)

- Phiên bản báo cáo: 1.1.0; schema phiếu và governance được hỗ trợ: 1.0.0
- Ngày: 2026-10-02
- Tác giả: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #143, #158, #168, #166, #48; `docs/research/evidence-rating-governance.md` §3.5

## 1. Mục đích và ranh giới quản trị

Tài liệu này hướng dẫn sử dụng công cụ đối soát phiếu chấm điểm độc lập `scripts/research/reconcile_rating_sheets.py`.
Công cụ này được phát triển nhằm tự động hóa việc kiểm tra tính hợp lệ của các ràng buộc nghiệp vụ, ghép cặp bản ghi và tính toán các số đo đối soát mô tả giữa hai phiếu đánh giá độc lập.

> [!IMPORTANT]
> Đây là công cụ hỗ trợ người đối soát kỹ thuật, không phải là một cổng nghiệm thu tự động mới.
> Công cụ không tự tạo điểm số, không xác nhận năng lực người chấm và không tự duyệt tham số sản phẩm.
> Mọi đề xuất đồng thuận (`proposed_consensus`) hoặc bất đồng (`requires_reconciliation_panel`) là khuyến nghị kỹ thuật phục vụ người đối soát/A/B xem xét.
> Enum lịch sử `requires_reconciliation_panel` được giữ tương thích, không đặt dependency vào hội đồng ngoài.
> Trường `human_acceptance: "pending"` vẫn giữ nguyên ngay cả khi `processing_status` là `complete_all_reconciled`.
> Cả hai phiếu chấm điểm thực tế của dự án (`tests/fixtures/ranking/seamless_rater_1.json` và `tests/fixtures/ranking/seamless_rater_2.json`) tiếp tục được bảo lưu nguyên trạng ở trạng thái `pending_independent_rating`.
> Các bộ dữ liệu thử nghiệm tổng hợp (`tests/fixtures/ranking/synthetic/`) chỉ phục vụ kiểm thử phần mềm; tuyệt đối không coi là dữ liệu con người hay dùng làm tham số sản phẩm.

## 2. Nguyên tắc ghép cặp và kiểm tra ràng buộc

Công cụ kiểm tra các trường khai báo theo `docs/research/evidence-rating-governance.md` §3.5:

1. **Kiểm tra phạm vi truy vấn (Query Scopes Alignment):**
Hai phiếu chấm phải khai báo tập truy vấn đồng nhất.
Hệ thống kiểm tra cấu trúc phạm vi và đối chiếu `query_id`, `version`, `snapshot_id`, `scenario_id`, `scenario_version`, `evaluation_mode`, `work_boundary`, `foothold_node_id`, `target_goal`, `horizon` và `active_work_budget`.
Mọi sai lệch về phạm vi sẽ lập tức bị từ chối với mã lỗi 1 (fail-closed).

2. **Ghép cặp theo danh tính cấu trúc đầy đủ:**
Hệ thống không ghép cặp chỉ dựa vào mã câu hỏi (`question_id`) hoặc chỉ số mảng:
- Với Đánh giá Tác động (`impact_rating`): ghép theo cặp khóa `(target_asset_id, success_event)`.
- Với Xác suất có điều kiện (`conditional_likelihood`): ghép theo `(scenario_id, scenario_version, query_id, foothold_node_id, snapshot_id, operational_horizon, target_population, ordered_work_prefix, outcome_action_id, outcome_work_unit_id, conditioning_previous_successes, quantity)`.
`scenario_version` và outcome phải tồn tại; mỗi phần tử prefix là chuỗi định danh work unit có định nghĩa hợp lệ.
`outcome_work_unit_id` phải là phần tử cuối prefix, `conditioning_previous_successes` phải bằng toàn bộ phần trước outcome, và `quantity` phải đúng chuỗi schema 1.0.0 `q_i = P(E_i succeeds | foothold, scenario, all previous events succeeded)`.
Đại lượng tích lũy đường đi bị từ chối.
- Với Nỗ lực công việc (`work_unit_effort`): ghép theo định danh chuẩn tắc `work_unit_id` và đối chiếu metadata (`technique_name`, `actor_scope`, `target_scope`, `context_scope`, `boundary_scope`, `ledger_version`) với định nghĩa chuẩn tắc hoặc registry.
Xung đột registry với canonical ID bị từ chối trước khi ghép cặp.
Các kiểm tra binding chạy cả với bản ghi rated, pending và unmatched; boundary của prefix cũng phải khớp `work_boundary` của query scope.

3. **Phát hiện trùng lặp và thiếu sót:**
Hệ thống phát hiện và báo lỗi ngay nếu phát hiện hai bản ghi trùng khóa trong cùng một phiếu chấm.
Nếu một bản ghi xuất hiện ở phiếu 1 nhưng thiếu ở phiếu 2 (hoặc ngược lại), công cụ ghi nhận vào danh sách `unmatched_records` và cập nhật trạng thái xử lý `complete_with_unmatched_records`, không bao giờ âm thầm bỏ qua hay tự lấy bản ghi cuối cùng.

4. **Phân biệt trạng thái cấp phiếu và cấp bản ghi:**
`schema_version` và `governance_version` của phiếu phải là `1.0.0`; các phiên bản khác bị từ chối.
`rater` phải là object có các trường `evaluator`, `name`, `competence_and_scope`, `independence_declaration` và `rated_at`.
Phiếu ở trạng thái `pending_independent_rating` cho phép các trường này là null và chỉ chứa bản ghi unrated.
Phiếu ở trạng thái `rated` yêu cầu các trường trên là chuỗi không rỗng, evaluator không chứa `PENDING`, với `rated_at` là thời điểm ISO-8601 có ngày và giờ.
`organization` và `signature` vẫn tùy chọn; công cụ không tự xác nhận năng lực, sự độc lập thực tế hoặc tính xác thực của thời điểm đã khai báo.
Hai evaluator cấp phiếu phải khác nhau nếu đã khai báo; evaluator từng bản ghi khi có giá trị phải khớp cấp phiếu.
Bản ghi ở trạng thái `rating_status: "unrated"` được giữ nguyên là chưa đối soát (`unreconciled_pending`).
Phiếu đã nộp (`status: "rated"`) có thể còn bản ghi unrated với điểm null; công cụ báo đầy đủ phần chưa chấm.
Hệ thống không đưa giá trị null vào tính toán số học và không tự điền giá trị mặc định.
`record_type` phải đúng nhóm bản ghi và `rating_status` chỉ nhận `rated` hoặc `unrated`; typo, evaluator null trong bản ghi rated hoặc thiếu căn cứ chấm là lỗi validation, không được chuyển thành pending.
Impact rated cần `business_rationale` và danh sách `affected_business_services` hợp lệ.
Likelihood rated cần `basis_category`, `uncertainty_rationale` và `source_references` là danh sách chuỗi không rỗng.
Effort rated cần `effort_rationale`, rubric và cấu trúc `overlap_analysis` hợp lệ.
Rationale, nguồn và mô tả năng lực/độc lập được giữ nguyên văn; từ `pending` trong giải trình hoặc URL hợp lệ không bị coi là placeholder evaluator.

5. **Kiểm soát kiểu dữ liệu và rubric:**
Điểm rubric nỗ lực (`t1_complexity`, `t2_friction`, `computed_cost`) bắt buộc là số nguyên trong phạm vi quy chế.
Các kiểu số thực (`float`) hoặc boolean (`bool`) đều bị từ chối bằng `TypeError`.
Khoảng xác suất bắt buộc biểu diễn bằng phân số hữu tỷ chính xác thỏa mãn $0 \le l \le u \le 1$.

6. **Phân tích chồng lấn nỗ lực (Overlap Analysis):**
Trường `is_independent` trong `overlap_analysis` phải là boolean khi đã chấm điểm.
Với cặp đã chấm đủ, nếu một trong hai người chấm khai báo `is_independent: false` (chưa khấu trừ nỗ lực chuẩn bị dùng chung), bản ghi được đánh dấu `status: "overlap_withheld"` và chuyển sang danh sách chờ người xem xét.
Với cặp còn pending, báo cáo giữ nguyên phân tích overlap thô và trạng thái chưa đối soát.

7. **Bảo vệ chống ghi đè (Path Aliasing Protection):**
Tùy chọn `--output` được kiểm tra bằng đường dẫn đã resolve để từ chối việc trỏ trùng vào `--sheet1`, `--sheet2` hoặc `--registry`, kể cả symlink.
Writer dùng `tempfile.NamedTemporaryFile` tạo độc quyền tệp có tên duy nhất trong thư mục output, ghi qua handle vừa tạo, đóng handle rồi replace.
Writer chỉ dọn tệp tạm do chính nó tạo; không mở hoặc truncate tên tạm đoán trước.
Các tests mô phỏng lỗi tạo/ghi/replace kiểm tra input và output cũ không đổi, không để lại report mới khi validation thất bại.
Kiểm thử bất biến lấy byte trước/sau khi chạy CLI trên bản sao LF/CRLF; digest của CLI vẫn là SHA-256 của raw bytes, không normalize newline.

8. **Báo cáo kiểm toán không mất dữ liệu:**
Mỗi matched pair giữ hai bản ghi nguyên gốc tại `raw_records`, cùng `binding` đã kiểm tra và các số đo/đề xuất riêng biệt.
`unmatched_records` giữ `record` nguyên gốc và `validated_binding`; pending effort giữ cả `overlap_details`.
`input_metadata` lưu envelope, rater và provenance khai báo của từng phiếu; `scope_summary.query_scopes` giữ toàn bộ scope, `snapshot_ids` liệt kê các snapshot và `snapshot_id` là null nếu có nhiều snapshot.
Báo cáo không tự thêm thời điểm chấm hay quyết định nghiệm thu.

## 3. Các số đo đối soát được tổng hợp

Báo cáo đối soát tổng hợp các số đo mô tả theo quy chế quản trị:
- **Tác động (Impact):** Tính hệ số Cohen's Kappa qua hàm `compute_kappa_with_fallback`.
Nếu tập mẫu chỉ có một mức tác động (zero variance), hệ thống bảo lưu `status: "degenerate_zero_variance"`, `kappa: None`, và ghi nhận tỷ lệ đồng thuận quan sát được `observed_agreement` kèm ma trận nhầm lẫn thô.
- **Xác suất (Likelihood):** Tính hệ số giao trên hợp (Rational IoU).
Nếu $\text{IoU} \ge 0.50$, đề xuất khoảng đồng thuận $[\min(l_1, l_2), \max(u_1, u_2)]$.
Nếu độ rộng khoảng $> 0.50$, gắn cờ cảnh báo độ bất định nhận thức cao (`high_epistemic_uncertainty`).
- **Nỗ lực (Effort):** Tính độ lệch chi phí $\Delta = |C_1 - C_2|$.
Nếu $\Delta \le 1$, đề xuất chi phí bảo thủ $\max(C_1, C_2)$.
Nếu $\Delta > 1$ hoặc có phân tích chồng lấn chưa giải quyết, đề xuất người đối soát/A/B xem xét.

## 4. Hướng dẫn lệnh thực thi CLI

### 4.1. Cú pháp cơ bản

```bash
.venv/bin/python scripts/research/reconcile_rating_sheets.py \
  --sheet1 <ĐƯỜNG_DẪN_PHIẾU_1> \
  --sheet2 <ĐƯỜNG_DẪN_PHIẾU_2> \
  [--registry <ĐƯỜNG_DẪN_REGISTRY>] \
  [--output <ĐƯỜNG_DẪN_XUẤT_BÁO_CÁO>] \
  [--summary]
```

### 4.2. Các mã thoát (Exit Codes)
- `0`: Tạo được báo cáo xử lý, bao gồm pending, unmatched và bất đồng; không có nghĩa đã nghiệm thu.
- `1`: Lỗi validation, binding, trùng bản ghi, sai kiểu, aliasing hoặc lỗi đọc/tạo/ghi/replace tệp; output cũ được giữ lại.
- `2`: `argparse` từ chối cú pháp CLI, ví dụ thiếu `--sheet1` hoặc `--sheet2`.

### 4.3. Ví dụ 1: Đối soát hai phiếu mẫu đang pending

Chạy đối soát trực tiếp hai phiếu chấm pending thực tế trong kho mã:

```bash
.venv/bin/python scripts/research/reconcile_rating_sheets.py \
  --sheet1 tests/fixtures/ranking/seamless_rater_1.json \
  --sheet2 tests/fixtures/ranking/seamless_rater_2.json \
  --summary
```

Kết quả tóm tắt gửi về `stderr` (giúp `stdout` giữ nguyên định dạng JSON nếu cần dẫn xuất luồng):
- Trạng thái xử lý: `complete_with_pending_records`.
- 21 cặp bản ghi được ghép cặp chính xác.
- 0 cặp đã chấm, 21 cặp ở trạng thái chờ chấm (`pending_unrated_pairs_count: 21`).
- Mã thoát: `0`.

### 4.4. Ví dụ 2: Đối soát hai phiếu thử nghiệm tổng hợp đã chấm đủ

Chạy đối soát với cặp phiếu synthetic có độ đồng thuận cao:

```bash
.venv/bin/python scripts/research/reconcile_rating_sheets.py \
  --sheet1 tests/fixtures/ranking/synthetic/synthetic_rater_1_rated.json \
  --sheet2 tests/fixtures/ranking/synthetic/synthetic_rater_2_rated.json \
  --output reports/generated/reconciliation_report.json \
  --summary
```

Kết quả:
- Trạng thái xử lý của cặp fixture này: `complete_with_disagreements`.
- 21/21 cặp được đối soát đầy đủ.
- 17 đề xuất đồng thuận, 4 bất đồng likelihood; `human_acceptance` tiếp tục `pending`.
- Báo cáo chi tiết được ghi tại `reports/generated/reconciliation_report.json`.

### 4.5. Ví dụ 3: Kiểm tra cơ chế chống ghi đè đầu vào

Thử ghi đè tệp đầu vào bằng cờ `--output`:

```bash
.venv/bin/python scripts/research/reconcile_rating_sheets.py \
  --sheet1 tests/fixtures/ranking/seamless_rater_1.json \
  --sheet2 tests/fixtures/ranking/seamless_rater_2.json \
  --output tests/fixtures/ranking/seamless_rater_1.json
```

Kết quả:
- Lệnh bị từ chối với thông báo `Path aliasing detected` và `cannot overwrite an input sheet`, kèm đường dẫn đã resolve.
- Raw bytes của tệp đầu vào không đổi.
- Mã thoát: `1`.

## 5. Quy trình tiếp theo sau khi có báo cáo đối soát

1. Sau khi A/B hoặc hai người phù hợp trong nhóm hoàn thành đánh giá độc lập và nộp phiếu, người đối soát chạy công cụ để tạo báo cáo.
2. Người đối soát và các bên liên quan mở mục `decisions_pending_human_review` trong báo cáo để thảo luận các điểm bất đồng.
3. Việc thống nhất phán quyết cuối cùng được ghi nhận bằng văn bản hoặc quyết định trên issue/PR có kiểm toán.
4. Chặng chuyển dịch từ biên bản đối soát con người sang gói tham số chính thức và nghiệm thu tham số được thực hiện riêng theo lộ trình #143, không thuộc phạm vi tự động của công cụ này.

## Bàn giao sang reviewed release - 2026-10-02

Report 1.1.0 của #170 là đầu vào review, không phải quyết định cuối hoặc bộ tham số accepted.
[Hướng dẫn #171](reviewed-parameter-release-guide.md) mô tả explicit decisions bind sheet/report/template digests, exporter riêng, lossless replay validator và sensitivity trên số được chọn.
Mọi proposal, kể cả đồng thuận, cần disposition được khai báo trước khi xuất.
Actual sheets vẫn pending; synthetic demo không thay chấm thật, acceptance hoặc final integrated E2E.
