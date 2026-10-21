# Worklog - 2026-10-02 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [#155](https://github.com/nairyuuu/ad-weighted-graph/issues/155), [#165](https://github.com/nairyuuu/ad-weighted-graph/pull/165), [#166](https://github.com/nairyuuu/ad-weighted-graph/pull/166), [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) / PR branch `docs/143-reproducible-b-handoff-sync` / M2 Week 3
- Thời gian thực tế ước lượng: Không đo thời lượng phiên sửa; không suy giờ làm từ số lệnh hoặc thời gian test.

## Kết quả và bằng chứng

Worklog này ghi nhận kết quả thực hiện của TTS A (@Lolavine777) tiếp nối sau khi PR #165 được hợp nhất vào nhánh `develop` tại commit `fdf5928`.
TTS B (@nairyuuu) đã phê duyệt chính thức PR #165 tại review #5387665338 cho phạm vi Scoped Parameter Bundle 1.0.0, Interface 1.0.0, ADR-0013 và hồ sơ disposition tương ứng.
Sau khi hoàn tất round 1 (#5387814852), phiên review round 2 (#5387893883) trên PR #166 đã chỉ ra 3 điểm kỹ thuật cần tiếp tục chấn chỉnh và 1 lỗi điều hướng anchor.
Công việc này tiếp thu và xử lý toàn diện các phát hiện ở cả hai vòng review.
Thứ nhất, sửa ví dụ Python gọi Canonical Engine: dùng đúng module `from src.engine.ranking import PathRankingEngine` và đối số keyword `query_payload` (không dùng `query`), đã kiểm chứng thực tế với fixture `tests/fixtures/ranking/seamless_proposed_query_input.json`.
Thứ hai, cập nhật quy trình clean checkout trong biên bản bàn giao: hướng dẫn checkout detached trực tiếp tại pinned commit `fdf59285f5af095733b816cc0e76400471b00c4f` và kiểm tra HEAD, tách biệt revision engine/artifacts khỏi revision docs của PR #166.
Thứ ba, phân biệt rõ bản chất độc lập nỗ lực (non-duplication of effort) với quan hệ thứ tự tiên quyết trong chuỗi tấn công, bổ sung ví dụ minh họa cụ thể cho cặp `reset_password` và `acquire_ticket`.
Thứ tư, thay cú pháp anchor bằng thẻ chuẩn HTML `<a id="sec-independent-rating-instructions"></a>` để tương thích hoàn toàn với GitHub Markdown.
Cả hai bảng chấm điểm của con người tiếp tục được giữ nguyên trạng thái pending, không tạo lập danh tính giả hay số liệu giả.
Không chỉnh sửa mã nguồn engine/parser của TTS B và không đóng các issue cha khi các cổng nghiệm thu sau còn đang mở.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| 1. Đồng bộ hóa quyết định ADR-0013 | `docs/adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md` | Chuyển trạng thái sang Accepted by TTS A & TTS B cho phạm vi PR #165; ghi nhận review #5387665338 và commit `fdf5928`; cập nhật bảng checklist nghiệm thu cho từng cổng. |
| 2. Đồng bộ hóa hồ sơ nghiệm thu | `docs/research/path-ranking-acceptance-disposition.md` | Cập nhật ma trận trạng thái (Gate 1, 2, 3, 4 bundle, 6 được chấp thuận cho phạm vi PR #165; Gate 4 human ratings giữ pending; Gate 5 giữ Insufficient Evidence); cập nhật 26 giả thiết runtime; đồng bộ trạng thái governance 1.0.0. |
| 3. Đồng bộ hóa đặc tả giao diện 1.0.0 | `docs/research/path-ranking-interface-specification.md` | Chuyển trạng thái sang Accepted by TTS A & TTS B cho phạm vi PR #165; ghi nhận phê duyệt giao diện và ranh giới chuyển dịch chuẩn tắc. |
| 4. Bổ sung hướng dẫn đánh giá và luồng helper | `docs/research/evidence-rating-governance.md` | Đặt HTML anchor `<a id="..."></a>`; hướng dẫn đúng schema 21 bản ghi; giải thích $q_i$ theo từng bước; phân biệt overlap nỗ lực với prerequisite; sửa ví dụ Python import và keyword `query_payload`. |
| 5. Đồng bộ hóa gói kịch bản SEAMLESS | `docs/research/seamless-scenario-rating-packet.md` | Cập nhật trạng thái và bảng ma trận Mục 9; tách rõ kiểm chứng bundle giả thiết với nghiệm thu tham số cuối cùng; dẫn chiếu đúng anchor governance Mục 3.5. |
| 6. Tổng hợp gói bàn giao tái lập cho B | `docs/research/engine-path-ranking-mapping.md` | Cập nhật Mục 8: đặt Python 3.14 làm baseline; quy định checkout detached tại pinned commit `fdf5928`; gỡ lệnh Source B `--input` không hỗ trợ; cung cấp lệnh CLI độc lập. |
| 7. Cập nhật định hướng trọng số | `docs/research/weighting-direction.md` | Cập nhật điểm kiểm soát Checkpoint 8 và bảng bàn giao phản ánh PR #165 merge tại `fdf5928`, phê duyệt #5387665338 và trạng thái đã rà soát của kịch bản. |
| 8. Kiểm tra chất lượng và an toàn | `.venv/bin/pytest`, `.venv/bin/ruff`, `scripts/check_contract.py`, `scripts/check_repository.py` | 208 ranking tests pass; 1121 toàn bộ tests pass; ruff check và format clean; contract check và repository check pass 100%. |

## Rà soát luồng công cụ và đối chiếu API thực tế (Helpers Audit & API Reality)

Đã rà soát toàn bộ các công cụ và cấu trúc dữ liệu hiện có trong kho mã liên quan đến quy trình đánh giá tham số:
1. **Dữ liệu thô từ người chấm:**
   - Hai tệp `tests/fixtures/ranking/seamless_rater_1.json` và `tests/fixtures/ranking/seamless_rater_2.json` chứa cấu trúc chuẩn tắc của phiếu chấm điểm.
   - Cả hai bảng hiện tại đều giữ nguyên trạng thái pending, không có danh tính rater và không có điểm số giả định.
   - Phiếu gồm 1 bản ghi `impact_rating`, 11 bản ghi `conditional_likelihood` và 9 bản ghi `work_unit_effort`.
2. **API đối soát thực tế (`scripts/research/path_ranking_wire_adapter.py`):**
   - Hàm đối soát thực tế là `reconcile_expert_ratings(r1, r2, work_unit_registry=None)`.
   - Hàm nhận **hai bản ghi đơn lẻ có cùng `record_type`**, không nhận cả hai tệp JSON phiếu chấm.
   - Người đối soát phải kiểm tra bối cảnh cấp phiếu (`query_id`, `snapshot_id`, `foothold_node_id`, `scenario_version`) trước khi gọi helper.
   - Hàm kiểm tra tính hợp lệ của người chấm (phải khác nhau và không chứa `"PENDING"`).
   - Hàm ghép cặp theo định danh: `target_asset_id` + `success_event` cho tác động; `scenario_id` + `ordered_work_prefix` cho xác suất; `work_unit_id` cho nỗ lực.
   - Hàm tính Rational IoU qua `compute_interval_iou(b1, b2)`, trả về khoảng hòa giải $[\min(l_1, l_2), \max(u_1, u_2)]$ khi $\text{IoU} \ge 0.50$, và cảnh báo qua `check_epistemic_uncertainty` nếu độ rộng $> 0.50$.
   - Hàm tính nỗ lực từ rubric, kiểm tra chênh lệch $\Delta = |C_1 - C_2| \le 1$, và chọn nỗ lực bảo thủ $\max(C_1, C_2)$.
   - Hệ số Cohen's Kappa được tính qua hàm độc lập `compute_kappa_with_fallback(ratings1, ratings2)` trên danh sách nhãn tác động thô, không nằm trong nhánh đối soát bản ghi đơn lẻ.
   - Các phán quyết `proposal_verdict` (`proposed_consensus` hoặc `requires_reconciliation_panel`) là số đo và đề xuất kỹ thuật cho con người xem xét, không phải phán quyết tự động và không đặt ra điều kiện tuyển hội đồng ngoài.
3. **Khoảng trống công cụ hiện có (Codebase Gaps):**
   - Hiện tại codebase chưa có công cụ CLI đối soát tự động toàn bộ phiếu (bulk sheet reconciliation) và chưa có công cụ xuất tự động từ phiếu thô sang bundle hoàn chỉnh.
   - Hàm `verify_parameter_bundle` trong `scripts/research/seamless_parameter_validation.py` hiện được thiết kế riêng để xác thực gói giả thiết kịch bản có hỗ trợ nghiên cứu với điều kiện bắt buộc `raters=[]`.
   - Khi có bảng chấm từ hai người thật, việc đưa kết quả đối soát vào gói tham số hoàn chỉnh sẽ cần quy trình xem xét thủ công hoặc xây dựng thêm công cụ xuất riêng.
4. **API đánh giá của Canonical Engine và kiểm chứng thực tế:**
   - Trong mã nguồn Python:
     ```python
     import json
     from src.engine.ranking import PathRankingEngine

     with open("tests/fixtures/ranking/seamless_proposed_query_input.json") as f:
         payload = json.load(f)

     engine = PathRankingEngine(version="1.0.0")
     result = engine.evaluate(
         query_payload=payload["query"],
         candidates=payload["candidates"],
     )
     pareto_frontier = result["roundtrip_result"]["pareto_frontier"]
     ```
   - Đoạn mã trên đã được thực thi kiểm chứng trực tiếp trong terminal với Python 3.12/3.14 và trả về chính xác `pareto_frontier: ['cand_seamless_01_direct_lidia', 'cand_seamless_02_alt_vajer_ollie']`.
   - Trong giao diện dòng lệnh: `python -m src.engine.ranking.cli --input <file_chua_query_va_candidates> --output <file_ket_qua>`.

## Gói bàn giao kỹ thuật tái lập cho TTS B (Reproducible Handoff)

Đã cập nhật biên bản bàn giao tại Mục 8 của `docs/research/engine-path-ranking-mapping.md`:
- **Git revision:** Nhánh `develop` tại commit `fdf59285f5af095733b816cc0e76400471b00c4f`.
- **Môi trường Python:** Python **3.14.x** là baseline chuẩn tắc của kho mã (theo `.python-version`, `README.md`, và GitHub CI). Môi trường Python 3.12 được sử dụng cục bộ trong quá trình đánh giá và đã xác nhận vượt qua toàn bộ các kiểm thử tương thích.
- **Khởi tạo môi trường sạch tại pinned commit:**
  ```bash
  git fetch origin
  git checkout fdf59285f5af095733b816cc0e76400471b00c4f
  git rev-parse HEAD
  python3.14 -m venv .venv
  .venv/bin/python -m pip install -r requirements-dev.txt
  ```
- **Tách biệt Revision:** Cam kết `fdf59285f5af095733b816cc0e76400471b00c4f` là revision tái lập engine và artifacts tham số (hậu PR #165), tách riêng với revision tài liệu đồng bộ của PR #166.
- **Tính tự chứa của Engine:** Mã nguồn engine chuẩn tắc (`src/engine/ranking/`) là hoàn toàn tự chứa, không phụ thuộc vào `scripts/research/`.
- **Gói tham số chuẩn tắc:** `tests/fixtures/ranking/seamless_parameter_bundle.json`.
- **Bundle Digest:** `sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`.
- **Lệnh kiểm chứng gói tham số (Bao phủ cả Source A và Source B):**
  `.venv/bin/python scripts/research/seamless_parameter_validation.py --bundle tests/fixtures/ranking/seamless_parameter_bundle.json`.
- **Lệnh thực thi độc lập qua Canonical Engine CLI:**
  `.venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_proposed_query_input.json --output /tmp/seamless_output_a.json`
  `.venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_source_b_proposed_query_input.json --output /tmp/seamless_output_b.json`
- **Lệnh kiểm thử:** `.venv/bin/pytest tests/test_seamless_parameter_proposal.py tests/test_engine_path_ranking_conformance.py tests/test_seamless_packet.py -q`.
- **Kết quả kỳ vọng:** Toàn bộ 208 bài kiểm thử xếp hạng đường đi thành công; script kiểm chứng xác nhận 7/7 probe và trace giải tích khớp 100% với đường cơ sở; các lệnh CLI chạy thành công và xuất kết quả xếp hạng.

## Hướng dẫn đánh giá độc lập khớp schema (Independent Rating Instructions)

Đã chuẩn hóa hướng dẫn tại Mục 3.5 của `docs/research/evidence-rating-governance.md` (`<a id="sec-independent-rating-instructions"></a>`):
1. Hai người chấm độc lập tải bảng chấm tương ứng `seamless_rater_1.json` và `seamless_rater_2.json`.
2. Người chấm điền thông tin danh tính thật, vai trò và dấu thời gian thực tế ở cấp phiếu và từng bản ghi.
3. Người chấm đánh giá độc lập 1 bản ghi tác động đích đối với Domain Controller theo rubric tại Mục 3.1 (`Low`, `Medium`, `High`, `Critical`), kèm `business_rationale` và dịch vụ ảnh hưởng; cho phép giữ unrated nếu thiếu căn cứ.
4. Người chấm đánh giá độc lập 11 bản ghi khoảng xác suất có điều kiện $[l_i, u_i]$ với $0 \le l_i \le u_i \le 1$ theo từng bước đơn lẻ $q_i = P(E_i \text{ succeeds} \mid \text{history})$, không nhầm lẫn với xác suất tích lũy toàn đường đi; cho phép giữ unrated nếu thiếu căn cứ.
5. Người chấm đánh giá độc lập 9 bản ghi nỗ lực theo rubric $T_1, T_2$ và công thức `"base"`.
6. Phân tích chồng lấn nỗ lực trong `overlap_analysis`:
   - Bắt buộc đánh giá thực tế tính độc lập về nỗ lực (non-duplication of effort) và các phụ thuộc tiên quyết; tuyệt đối không tự động mặc định công việc là độc lập.
   - `is_independent`: điền `true` nếu chi phí nỗ lực của công việc là độc lập (không bị tính trùng nỗ lực chuẩn bị với các bước khác). Điền `false` nếu có phần công sức chuẩn bị bị trùng lặp chưa được khấu trừ.
   - Lưu ý bản chất: Tính độc lập ở đây là độc lập về chi phí nỗ lực được tính, không phải độc lập về mặt xác suất hay không có bước đi trước trong chuỗi tấn công.
   - `prerequisite_dependencies`: liệt kê danh sách định danh đơn vị công việc tiên quyết bắt buộc phải hoàn thành trước theo chuỗi tấn công (ví dụ `acquire_ticket` phụ thuộc vào `reset_password`). Việc có bước tiên quyết không đồng nghĩa với việc bị trùng nỗ lực; không suy ra unresolved overlap chỉ từ việc tồn tại prerequisite.
   - `shared_preparation_tags`: liệt kê các thẻ chuẩn bị dùng chung (ví dụ quyền truy cập foothold, phiên làm việc) đã được phân bổ hoặc cần khấu trừ.
   - Ví dụ minh họa: Bước 1 `reset_password` ($C=1$) và Bước 2 `acquire_ticket` ($C=0$) có quan hệ thứ tự tiên quyết (`prerequisite_dependencies` của Bước 2 chứa Bước 1). Tuy nhiên, chi phí nỗ lực của hai bước là riêng biệt vì Bước 1 là tương tác RPC đặt lại mật khẩu, còn Bước 2 là tương tác Kerberos độc lập. Do đó Bước 2 có `is_independent: true`, nỗ lực hai bước được cộng dồn mà không bị đếm trùng công sức.
   - Chỉ đặt `"unrated"` và giữ điểm `null` khi phần công sức chuẩn bị bị trùng lặp thực sự chưa được giải quyết hoặc thiếu căn cứ kỹ thuật.
7. Tuyệt đối không trao đổi hoặc đối chiếu kết quả giữa hai người chấm trong suốt quá trình đánh giá độc lập.
8. Sau khi nộp phiếu, thực hiện ghép cặp bản ghi và chạy hàm `reconcile_expert_ratings` cùng `compute_kappa_with_fallback` để hỗ trợ đối soát các điểm bất đồng giữa người với người.

## Cam kết quản trị và ranh giới trách nhiệm

- **Bảo lưu bảng chấm điểm:** Tiếp tục giữ `tests/fixtures/ranking/seamless_rater_1.json` và `seamless_rater_2.json` ở trạng thái pending với toàn bộ trường rỗng cho đến khi có dữ liệu đánh giá thực tế từ người thật.
- **Không giả mạo dữ liệu:** Tuyệt đối không tự bịa đặt điểm số, danh tính người chấm hay dấu thời gian.
- **Phán quyết khoa học:** Tiếp tục duy trì phán quyết `Insufficient Evidence` cho xếp hạng dự đoán sản phẩm trên snapshot SEAMLESS; hiệu chuẩn thực nghiệm là hạng mục bằng chứng tùy chọn trong tương lai, không phải cổng chặn bắt buộc.
- **Không can thiệp mã nguồn của B:** Tuyệt đối không chỉnh sửa mã nguồn engine hoặc parser của TTS B trong `src/engine/` và `src/parser/`.
- **Không đóng issue cha:** Giữ nguyên các issue #143, #158, #155, #48 vì các cổng tích hợp và đối soát di sản vẫn đang được thực hiện.

## Điều học được / quyết định

1. **Đối soát mã nguồn và API thực tế trước khi viết tài liệu:**
   - Việc kiểm tra kỹ lưỡng các định nghĩa hàm (`reconcile_expert_ratings` thay vì tên hàm giả định), đối số thực tế (`evaluate(query_payload, candidates)`), và cấu trúc module (`src.engine.ranking`) giúp bảo đảm tính chính xác kỹ thuật 100% của tài liệu hướng dẫn.
2. **Khớp đúng schema phiếu chấm và phân định rõ bản chất overlap:**
   - Hướng dẫn chấm điểm phải phản ánh đúng các trường có trong schema JSON thực tế.
   - Cần phân định rõ ràng giữa quan hệ thứ tự tiên quyết (prerequisite) trong chuỗi tấn công với tính độc lập nỗ lực (effort non-duplication). Việc có predecessor không làm mất tính độc lập chi phí của công việc riêng rẽ.
3. **Thực thi và xác nhận từng lệnh bàn giao tại pinned revision:**
   - Hướng dẫn bàn giao phải sử dụng checkout detached tại đúng pinned revision (`fdf5928`) để bảo đảm tính bất biến khi nhánh develop dịch chuyển.
   - Mọi lệnh CLI đưa vào tài liệu bàn giao phải được thực chạy trực tiếp trong terminal để đảm bảo exit code bằng 0.
4. **Phân định rõ ràng giữa Gói giả thiết nghiên cứu và Nghiệm thu tham số cuối cùng:**
   - Việc xác thực gói tham số 1.0.0 trong PR #165 áp dụng cho các giả thiết nghiên cứu và tính toán giải tích; việc nghiệm thu tham số sản phẩm cuối cùng chỉ diễn ra sau khi có đánh giá thực tế từ con người.

## Trở ngại và việc kế tiếp

1. **Trở ngại đã giải quyết:**
   - Tiếp thu và xử lý toàn diện các phát hiện từ round 1 (#5387814852) và round 2 (#5387893883) trên PR #166.
   - Sửa ví dụ Python gọi Engine chuẩn: dùng đúng module `src.engine.ranking`, keyword `query_payload`, và trích xuất đúng `result["roundtrip_result"]`.
   - Cập nhật quy trình checkout detached tại pinned commit `fdf59285f5af095733b816cc0e76400471b00c4f` trong biên bản bàn giao.
   - Làm rõ bản chất overlap nỗ lực trong rubric governance, bổ sung ví dụ minh họa cụ thể cho chuỗi `reset_password` và `acquire_ticket`.
   - Thay custom anchor bằng thẻ HTML `<a id="..."></a>` chuẩn cho GitHub Markdown.
   - Chạy kiểm tra toàn diện: 208 ranking tests pass, 1121 tests pass, contract check và repository check pass, ruff clean.
2. **Việc kế tiếp:**
   - Đẩy commit cập nhật lên nhánh `docs/143-reproducible-b-handoff-sync` của PR #166.
   - Cập nhật mô tả PR #166 phản ánh đầy đủ các chỉnh sửa tiếp thu từ round 2.
   - TTS B tiếp tục thực hiện review và phê duyệt chính thức.
