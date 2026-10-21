# Bảng ánh xạ kỹ thuật và tài liệu tích hợp Engine Path Ranking (Specification 1.0.0, Accepted for PR #165 scope)

- Ngày: 2026-10-01 (Cập nhật đồng bộ sau PR #165: 2026-10-02)
- Tác giả: @nairyuuu (TTS B)
- Reviewer: @Lolavine777 (TTS A)
- Tham chiếu: Issue #155, Issue #143, Issue #145, Issue #48, ADR-0013, PR #152, PR #154, PR #163, PR #165

---

## 1. Giới thiệu và mục tiêu tài liệu

Tài liệu này ghi nhận chi tiết bản ánh xạ kỹ thuật (`technical mapping note`) giữa hợp đồng giao diện xếp hạng đường tấn công Specification 1.0.0 quy chuẩn (`PathRankingQuery` và `PathRankingResult`) với kiến trúc khối engine thực tế (`src/engine/ranking/`).

Tài liệu phục vụ nghiệm thu **Giai đoạn 1 (Phase 1 / Conformance & Engine Boundary)** theo Issue #155, đồng thời thiết lập ranh giới bàn giao kỹ thuật rõ ràng với các công việc đang chờ (gated) của TTS A (Issue #143) và phần tìm kiếm multigraph của TTS B (Issue #145).

### Bảng phân định trạng thái các tầng nghiệm thu

Để tránh hiểu nhầm về mức độ sẵn sàng sản xuất (`production readiness`), dự án tách bạch nghiêm ngặt các trạng thái kiểm chứng độc lập:

| Trạng thái | Định nghĩa | Trạng thái hiện tại tại PR này | Ghi chú và căn cứ kiểm chứng |
| :--- | :--- | :--- | :--- |
| **Contract Conformance** | Mức độ tuân thủ đặc tả giao diện Specification 1.0.0 quy chuẩn, quy tắc cú pháp, định dạng phân số stdlib `Fraction`, tính bất biến của dữ kiện và phân vùng chẩn đoán. | **HOÀN THÀNH (Phase 1 Conformance & Normative 1.0.0)** | Contract conformance cho ranh giới Phase 1 đã triển khai: hoàn tất đối với Specification 1.0.0 quy chuẩn đã được TTS A và TTS B chấp thuận trong phạm vi PR #165 (116/116 tests conformance độc lập tại `tests/test_engine_path_ranking_conformance.py` đạt 100% mà không import mã nghiên cứu; wire migration adapter đã merge tại PR #163). |
| **Parameters Validated** | Mức độ kiểm chứng thực nghiệm của các bộ tham số xác suất, thang đo nỗ lực và đánh giá tác động trên dữ liệu thật. | **1.0.0 RELEASED / RATINGS PENDING #143** | Scoped Parameter Bundle 1.0.0 đã phát hành và được TTS B phê duyệt tại #5387665338 cho phạm vi PR #165 (digest `sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`). Chấm độc lập A/B bằng người thật tiếp tục pending #143. Căn cứ nghiên cứu đã review và independent human ratings A/B là hợp lệ; không có dependency bắt buộc vào hội đồng bên ngoài và chưa claim empirical calibration. |
| **Engine Integrated** | Mức độ kết nối module engine với các bao gói ứng viên tường minh (`explicit candidate envelopes`). | **HOÀN THÀNH (Phase 1)** | Engine tại `src/engine/ranking/` tiếp nhận và xử lý đầy đủ chuỗi: `wire JSON -> validation -> replay -> assessment -> ranking -> result JSON`. |
| **Search Coverage** | Thuật toán sinh ứng viên tự động duyệt cạn kiệt hoặc tìm kiếm có giới hạn trên đồ thị multigraph quy mô lớn. | **PENDING #145** | PR #146 đang trong trạng thái Changes Requested; engine hiện tại hỗ trợ adapter protocol cho #145 nhưng chưa tích hợp runtime tìm kiếm. |
| **Week 3 bounded integration / E2E** | Tích hợp thực thi graph/search -> ranking trên phạm vi giới hạn, kiểm chứng các trường hợp positive, false và unknown. | **PENDING #145 / #155 / #48** | Là điều kiện bắt buộc nghiệm thu Tuần 3 theo #155/#158 sau #159; conformance Phase 1 chưa thay thế kiểm chứng E2E này. |
| **Legacy same-snapshot reconciliation** | Đối soát đồ thị với BloodHound Legacy trên cùng snapshot. | **PENDING #82 / #47** | Đối soát quan hệ cấu trúc và giải thích sai khác; không dùng làm bằng chứng xác suất thành công đã được kiểm chứng. |
| **CE / final parity / choke-point extension** | Đối chứng CE, parity cuối cùng và mở rộng choke-point/performance. | **PENDING mốc sau / #127** | Tách khỏi yêu cầu bounded integration/E2E của Tuần 3. Phán quyết khoa học trên SEAMLESS tiếp tục duy trì **Insufficient Evidence**. |
---

## 2. Bảng ánh xạ chi tiết: Contract to Engine Mapping

Luồng xử lý hoàn chỉnh của engine:

$$\text{PathRankingQuery} \xrightarrow{\text{validate}} \text{Decoded Query} \xrightarrow{\text{replay}} \text{Effective Prefix} \xrightarrow{\text{assess}} \text{Candidate Assessment} \xrightarrow{\text{rank}} \text{PathRankingResult}$$

| Thành phần hợp đồng (`Contract Element`) | Phân loại | Vị trí triển khai trong Engine | Trạng thái & Disposition |
| :--- | :--- | :--- | :--- |
| **`query_metadata`** | Metadata | `src/engine/ranking/validation.py` (`validate_query_metadata`) | **Implemented**: Kiểm tra bắt buộc 11 trường, version `"1.0.0"`, chế độ `"evidence_only"` hoặc `"scenario"`, snapshot hash pattern, canonical node ID; kiểm thực ranh giới trường `coverage` nếu có. |
| **`candidate scope_binding`** | Ràng buộc phạm vi | `src/engine/ranking/validation.py` (`validate_scope_binding`) | **Implemented**: Bắt buộc 7 trường phạm vi (`query_id`, `scenario_id`, `scenario_version`, `snapshot_id`, `work_boundary`, `horizon`, `foothold_node_id`), so khớp tuyệt đối với query, chống trộn lẫn cross-query / cross-scenario. |
| **`contradictory aliases & IDs`** | Kiểm soát toàn vẹn | `src/engine/ranking/validation.py` | **Implemented**: Fail-closed đối với duplicate candidate/action/route IDs và các cặp alias mâu thuẫn (`actor_id`/`source_node_id`, `target_id`/`target_node_id`, `referenced_work_unit_ids`/`bound_work_units`, `rating_status`/`status`, `effort_cost`/`computed_cost`). |
| **`facts_ledger`** | Dữ liệu đầu vào | `src/engine/ranking/facts.py` (`resolve_facts_ledger`) | **Implemented**: Phân giải 4 danh sách (`observed_facts`, `false_facts`, `assumed_facts`, `unknown_facts`), đối soát quan sát xung đột, thi hành quyền phủ quyết `observed_false_veto`; `assumed_facts` bắt buộc có trường `truth_value` kiểu boolean thuần túy (cấm default ngầm `True`). |
| **`authoritative predicate layer`** | Quy tắc kiểm tra | `src/engine/ranking/validation.py` (`validate_authoritative_predicate_layers`) | **Implemented**: Bắt buộc mọi vị từ trong query, actions, goal và candidate phải có tầng (1, 2, 3) khai báo rõ; thiếu tầng fail validation `ValueError` ngay lập tức. |
| **`bound_actions`** | Danh mục hành động | `src/engine/ranking/validation.py` (`validate_bound_actions`) | **Implemented**: Bắt buộc chủ thể và đích là canonical node ID (`actor_id` và `target_id` bắt buộc có), bắt buộc trường `technique_name` là chuỗi không rỗng, `is_passive_closure` bắt buộc kiểu boolean thuần túy (cấm default False ngầm), `referenced_work_unit_ids`/alias bắt buộc khai báo tường minh (passive action phải khai báo `[]` tường minh, cấm chữa ngầm từ `None` và reject danh sách work unit không rỗng), `requires` và `adds` bắt buộc phải được khai báo tường minh là mảng các chuỗi không rỗng (cấm chữa ngầm thiếu field thành `[]`), tham chiếu đơn vị công việc hợp lệ. |
| **`work_units_ledger`** | Sổ cái công việc | `src/engine/ranking/validation.py` (`validate_work_units_ledger`) | **Implemented**: Định danh chuẩn tắc, xác thực rubric $T_1, T_2 \in \{1, 2, 3\}$, công thức $C = T_1 + T_2 - 2$; chỉ chấp nhận quy ước `formula == 'base'` và fail-closed mọi formula khác; cấm unrated unit khai báo formula; bắt buộc khai báo tường minh `overlap_state` và `rating_status`/`status` (cấm suy diễn ngầm missing state/status); `overlap_state` chỉ chấp nhận enum chuẩn tắc `independent` và `unresolved_overlap` (fail-closed các enum ngoài spec); trạng thái `unresolved_overlap` bắt buộc giữ cost `null` và `rating_status: "unrated"`. |
| **`conditional_bounds_table`** | Bảng xác suất | `src/engine/ranking/validation.py` (`validate_and_decode_bounds_table`) | **Implemented**: Bắt buộc mảng object, tiền tố duy nhất (phát hiện trùng lặp ném `DuplicatePrefixError`), khoảng phân số chính xác $0 \le l \le u \le 1$. |
| **`target_impact_assessments`** | Đánh giá tác động | `src/engine/ranking/validation.py` (`validate_target_impact_assessments`) | **Implemented**: Canonical target asset ID, bắt buộc trường `success_event` là chuỗi không rỗng trên mọi bản ghi assessment (kể cả khi goal không khai báo event), mức đánh giá thứ tự (`Low`, `Medium`, `High`, `Critical`), phân biệt rõ lỗi cú pháp với trạng thái `unrated` (kèm `missing_basis_reasons`). |
| **`candidate state replay`** | Cơ chế thực thi | `src/engine/ranking/replay.py` (`replay_candidate_sequence`) | **Implemented**: Replay tuần tự, điều kiện tiên quyết trước hiệu ứng; tính bất biến của Layer 1 và Layer 2 (bỏ qua action adds); giữ nguyên hard veto và unknown ban đầu. |
| **`goal first-hitting time`** | Cắt tỉa chương trình | `src/engine/ranking/replay.py` (`replay_candidate_sequence`) | **Implemented**: Dừng ở lần đầu tiên thỏa mãn mục tiêu; cắt tỉa các hành động hậu tố; đồng bộ cắt tỉa toàn bộ các vector bằng chứng (`edge_ids`, `node_ids`, `provenance_locators`, `provenance_lineage`, `edge_provenance_records`); xử lý bước 0 (zero-step) cắt về rỗng (`effort = 0`, xác suất `[1, 1]`). |
| **`structural_routes auditability`** | Vết đường cấu trúc | `src/engine/ranking/validation.py`, `replay.py` | **Implemented**: Bắt buộc mọi route bắt đầu từ `foothold_node_id` và kết thúc tại candidate `target_asset_id` (báo lỗi cụ thể wrong route source/target); $N = E + 1$, $P = E$; bảo tồn phân tách Route vs Work History (không ép buộc `len(bound_action_ids) == len(edge_ids)` cho mọi candidate). |
| **`target reachability`** | Ràng buộc đích | `src/engine/ranking/replay.py` (`replay_candidate_sequence`) | **Implemented**: Đích phải thực sự đạt được bởi các hành động thực thi hiệu quả trong tiền tố (sự hiện diện trên route cấu trúc không đủ); khớp `success_event` và `target_asset_id`. |
| **`likelihood assessment`** | Tính xác suất | `src/engine/ranking/assessment.py` (`assess_candidate_program`) | **Implemented**: Tích phân số chính xác stdlib `Fraction` trên toàn bộ tiền tố đầy đủ; không fallback về xác suất biên; ngắt sớm nếu $u_i = 0$ khi mọi tiền tố trước đó đều có khoảng; ngắt ngay lập tức và withholding khi thiếu bất kỳ tiền tố nào (`interval is None`), không để tiền tố sau lật ngược cờ sang rated. |
| **`work unit deduplication`** | Tính nỗ lực | `src/engine/ranking/assessment.py` (`assess_candidate_program`) | **Implemented**: Khử trùng lặp các đơn vị công việc chuẩn tắc kiên trì (bước chuẩn bị dùng chung chỉ tính một lần); kiểm tra ngân sách `active_work_budget`. |
| **`diagnostic partitioning`** | Phân vùng chẩn đoán | `src/engine/ranking/assessment.py` (`assess_candidate_program`) | **Implemented**: Giữ nguyên vẹn toàn bộ nguyên nhân thất bại (`blocked`, `unknown`, `likelihood_unrated`, `impact_unrated`, `work_budget_exceeded`); không cho lọt vào frontier. |
| **`conservative Pareto frontier`**| Xếp hạng ưu thế | `src/engine/ranking/frontier.py` (`scoped_frontier`, `scoped_preference`)| **Implemented**: So sánh bán phần trên 2 trục độc lập ($I$ và $[l, u]$); giữ nguyên `incomparable` khi giao nhau; tie-break bằng nỗ lực cực kỳ hẹp theo ADR-0013 Section 4 (cùng $I$, cùng point likelihood, và CẢ HAI candidate bắt buộc phải có `effort_status == 'rated'` cùng `effort is not None`). |
| **`Min-Effort-to-DA baseline`** | Baseline tối thiểu | `src/engine/ranking/frontier.py` (`compute_min_effort_baseline`) | **Implemented**: Tách biệt hoàn toàn khỏi biên Pareto; tìm ứng viên có `effort` nhỏ nhất trong số eligible rated; công bố độ bao phủ và giới hạn cắt xén. |
| **`search_metadata & caps`** | Báo cáo bao phủ | `src/engine/ranking/__init__.py`, `validation.py` (`validate_upstream_coverage`, `execute_ranking_roundtrip`) | **Implemented**: Kiểm thực ranh giới `upstream_coverage` fail-closed (chống mâu thuẫn như `is_truncated=False` kèm `truncation_reasons`, cấm `is_truncated=True` thiếu `truncation_reasons`, cấm scope ngoài quy cách); bảo toàn các giới hạn `caps_applied` từ upstream; chuẩn hóa `completeness_scope` thành `partial_truncated` khi bị cắt xén; cấm kết luận không có đường khi bị trần giới hạn. |
| **`#145 search adapter`** | Giao diện kết nối | `src/engine/ranking/adapter_145.py` (`convert_path_result_to_candidate_envelope`)| **Implemented (Aligned Contract)**: Đồng bộ với hình thái `PathResult`/`TransitionStep` thực tế của #145: đối soát chính xác `edge.source == nodes[idx]`, `edge.target == nodes[idx + 1]`, `request.source == edge.source`, `request.target == edge.target`, `bound_action.edge_id == step.edge_id` (khi có catalog); bảo toàn 100% provenance lineage (không collapse, không silently drop record thứ hai, delimited representation + explicit lineage & raw records); tự động gắn `scope_binding`. Runtime search **PENDING #145**. |
| **`reproducible CLI`** | Công cụ dòng lệnh | `src/engine/ranking/cli.py` (`run_ranking_cli`) | **Implemented**: Tiếp nhận wire JSON, kiểm tra, replay, xếp hạng và xuất JSON phân số không mất mát thông tin; không phụ thuộc BloodHound hay Neo4j. |

---

## 3. Kiến trúc và luồng dữ liệu của Engine (`Architecture & Data Flow`)

Toàn bộ logic đánh giá và xếp hạng được cô lập hoàn toàn bên trong package `src/engine/ranking/` với các module chuyên trách:

```text
src/engine/ranking/
├── __init__.py           # Điều phối viên luồng xếp hạng (execute_ranking_roundtrip, PathRankingEngine)
├── models.py             # Hằng số, Enum, regex Graph Contract 1.3, hàm Fraction không mất mát
├── validation.py         # Bộ kiểm tra tính hợp lệ đóng (fail-closed validator v1.0.0)
├── facts.py              # Bộ phân giải dữ kiện 3 bước, layer rules và known-false veto
├── replay.py             # Bộ tái phát chuỗi hành động, first hitting time và đồng bộ vết cấu trúc
├── assessment.py         # Đánh giá xác suất tiền tố, sổ cái công việc chuẩn tắc và phân vùng chẩn đoán
├── frontier.py           # So sánh ưu thế Pareto bảo thủ và baseline Min-Effort-to-DA độc lập
├── adapter_145.py        # Giao diện adapter và protocol kết nối với nền tảng tìm kiếm #145
└── cli.py                # Điểm vào dòng lệnh (CLI) tái lập không phụ thuộc môi trường ngoài
```

### Các nguyên tắc nghiệp vụ cốt lõi đã hiện thực:

1. **Kiểm tra tính hợp lệ đóng (`fail-closed validation`):**
   - Mọi định danh node bắt buộc tuân thủ Graph Contract 1.3: các họ SID có tính tương đối (`S-1-5-32-*` và `S-1-5-18/19/20`) bắt buộc phải có phạm vi (`domain:sid:...`, `domain:<guid>:...`, `host:<guid>:...`). Bất kỳ bare SID nào thuộc nhóm này đều bị từ chối với `RankingValidationError`.
   - Bắt buộc kiểm tra tầng thẩm quyền (`authoritative layer`) cho toàn bộ vị từ xuất hiện trong hệ thống. Tuyệt đối không suy đoán tầng mặc định.
   - Bắt buộc kiểm tra trùng lặp khóa prefix trong bảng xác suất (`DuplicatePrefixError`).

2. **Tái phát trạng thái chuẩn tắc (`candidate state replay`):**
   - Đánh giá điều kiện tiên quyết (`requires`) trước khi cập nhật hiệu ứng (`adds`).
   - **Tính bất biến của Layer 1 và Layer 2:** Hành động trong chuỗi chỉ được cập nhật các vị từ Layer 3. Mọi nỗ lực `adds` vị từ Layer 1 (quyền cấu trúc) hoặc Layer 2 (cấu hình máy chủ) đều bị bỏ qua, không thể biến thành quyền hợp lệ.
   - **Quyền phủ quyết tuyệt đối (`observed_false_veto`):** Dữ kiện quan sát False từ snapshot không thể bị ghi đè bởi bất kỳ giả thiết kịch bản nào.
   - **Cắt tỉa tại lần đầu đạt mục tiêu (`goal first-hitting time`):** Chương trình dừng ngay khi thỏa mãn toàn bộ vị từ mục tiêu. Đồng bộ hóa vết cấu trúc (`structural_routes`) bắt buộc phải có ánh xạ 1-1 đã xác thực giữa hành động và cạnh; nếu không chứng minh được, hệ thống từ chối an toàn bằng `MappingSyncError`.

3. **Số học hữu tỷ chính xác tuyệt đối (`lossless rational arithmetic`):**
   - Toàn bộ phép nhân khoảng xác suất trên tiền tố lịch sử được thực hiện qua kiểu `Fraction` của thư viện chuẩn Python.
   - Loại bỏ hoàn toàn việc ép kiểu trung gian sang `float`, ngăn ngừa hiện tượng sai số làm tròn tạo ra quan hệ ưu thế giả mạo (`false dominance`).
   - Tuần tự hóa JSON lưu trữ chuỗi phân số tối giản `"numerator/denominator"` hoặc số nguyên `"integer"`.

4. **Xếp hạng Pareto bảo thủ và tính độc lập của Min-Effort-to-DA:**
   - So sánh ưu thế trên hai trục độc lập: Tác động nghiệp vụ ($I$) và Khoảng xác suất có điều kiện ($[l, u]$).
   - Nỗ lực ($C$) chỉ được dùng để tie-break trong trường hợp cực kỳ hẹp: cùng tác động, cùng point likelihood chính xác, và cả hai đều đã định mức nỗ lực.
   - Min-Effort-to-DA được xuất thành một khối kết quả riêng biệt (`min_effort_to_da_baseline`), công bố rõ độ bao phủ và không bị đánh đồng với biên Pareto rủi ro.

5. **Ràng buộc phạm vi cố định (`Fixed query scope binding`):**
   - Mọi ứng viên bắt buộc khai báo `scope_binding` gồm 7 trường: `query_id`, `scenario_id`, `scenario_version`, `snapshot_id`, `work_boundary`, `horizon`, `foothold_node_id`.
   - Engine so khớp fail-closed từng trường với `query_metadata` của truy vấn hiện hành. Bất kỳ sự thiếu sót hoặc sai lệch nào đều bị từ chối bằng `RankingValidationError` (malformed input), ngăn chặn rủi ro trộn lẫn ứng viên từ kịch bản hoặc truy vấn khác.

6. **Xác thực fail-closed đối với alias mâu thuẫn và trùng lặp ID:**
   - Trùng lặp `candidate_id` trong danh sách ứng viên, `action_id` trong danh mục `bound_actions`, hoặc `route_id` trong `structural_routes` đều kích hoạt `RankingValidationError`.
   - Các cặp alias tương thích ngược (`actor_id` vs `source_node_id`, `target_id` vs `target_node_id`, `referenced_work_unit_ids` vs `bound_work_units`, `rating_status` vs `status`, `effort_cost` vs `computed_cost`) được kiểm tra đồng bộ: nếu cả hai cùng xuất hiện nhưng mang giá trị khác nhau, engine lập tức fail-closed thay vì âm thầm ưu tiên một trường.

7. **Tính kiểm toán và ràng buộc điểm đầu/cuối của vết đường cấu trúc (`Structural route auditability & endpoint binding`):**
   - Ứng viên có chuỗi hành động thực thi bắt buộc phải có ít nhất một vết đường cấu trúc kiểm toán được (`len(structural_routes) >= 1`).
   - Mọi bước trên vết cấu trúc non-zero bắt buộc thỏa mãn: $\text{len}(node\_ids) = \text{len}(edge\_ids) + 1$ và $\text{len}(provenance\_locators) = \text{len}(edge\_ids)$.
   - Đỉnh và cạnh phải là canonical SID/hash hợp lệ; locator phải là chuỗi không rỗng.
   - **Ràng buộc điểm đầu/cuối của vết đường:** Mọi vết đường cấu trúc non-zero (trong cả trường hợp candidate có nhiều routes) bắt buộc phải bắt đầu tại điểm tựa cố định (`node_ids[0] == foothold_node_id`, nếu sai báo lỗi `"wrong route source"`) và kết thúc tại tài sản mục tiêu của ứng viên (`node_ids[-1] == target_asset_id`, nếu sai báo lỗi `"wrong route target"`). Bất kỳ một route nào trong tập hợp không thỏa mãn đều khiến toàn bộ ứng viên bị từ chối fail-closed.
   - Ứng viên zero-step bắt buộc có $node\_ids = [foothold\_node\_id]$, $edge\_ids = []$, $provenance\_locators = []$, và $target\_asset\_id = foothold\_node\_id$.
   - **Bảo tồn phân tách Route vs Work History:** Không ép buộc cạnh cấu trúc phải trùng khớp với từng hành động khi không có cắt tỉa hậu tố, cho phép nhiều vết đường cấu trúc khác nhau cùng quy về một chương trình công việc; chỉ bắt buộc ánh xạ 1-1 chính xác khi cắt tỉa hậu tố hoặc chuyển đổi qua adapter #145.

8. **Đồng bộ Adapter #145, Đối soát chuyển bước 3 chiều & Bảo tồn toàn vẹn Provenance Lineage:**
   - **Bảo tồn toàn vẹn Provenance (Zero Evidence Dropping):** Graph Contract 1.3 cho phép một canonical edge có nhiều provenance records. Adapter tuyệt đối không collapse danh sách provenance về một record đại diện duy nhất và không silently drop record thứ hai hay bất kỳ bằng chứng aggregated nào.
     * Trong `structural_routes.provenance_locators`: mỗi cạnh được biểu diễn bằng chuỗi kết hợp ổn định (semi-colon delimited: `";".join(locators)`), cho phép khôi phục và kiểm toán đầy đủ 100% các references gốc (`.split(";")`).
     * Mở rộng cấu trúc minh bạch: mỗi route bổ sung `provenance_lineage` (danh sách locator arrays theo từng cạnh) và `edge_provenance_records` (danh sách đầy đủ các dict record gốc bao gồm `timestamp_status`, `collector`, `raw_file`, v.v.). Candidate envelope cung cấp `edge_provenance_map` đối chiếu trực tiếp từ `edge_id`.
     * Tuyệt đối không tự hash provenance record thành identifier mới nếu Graph Contract không định nghĩa reference đó (sử dụng chuẩn tắc `sha256:{hash}` theo `scripts/check_contract.py` hoặc các trường `record_locator`/`record_id` có sẵn).
   - **Đối soát chuyển bước 3 chiều (Transition Step ↔ Canonical Edge ↔ Route Segment):**
     * Với mỗi bước chuyển `idx`: bắt buộc `edge["source"] == nodes[idx]` và `edge["target"] == nodes[idx + 1]`. Bất kỳ sự lệch hướng hoặc sai đỉnh nào đều lập tức kích hoạt `RankingValidationError` fail-closed.
     * Nếu `TransitionResult.request` khai báo endpoint: bắt buộc `request.source == edge["source"]` và `request.target == edge["target"]`.
     * Nếu `bound_actions_catalog` được cung cấp và action có khai báo `edge_id`: bắt buộc `bound_action.edge_id == step.edge_id`. Nếu chưa có catalog ở mức adapter gọi độc lập, việc kiểm tra này được quản trị ở cấp runtime search integration (**PENDING #145**).
   - **Trích xuất Technique ID chuẩn tắc:** Đọc từ `step.result.request.technique_id` (ưu tiên) hoặc `step.result.technique.id`; reject nếu xung đột; cấm fallback ngầm về `step_{idx}` hay action ID.
   - **Các bước chuyển dẫn xuất (Derived Steps):** Bước chuyển có `edge_id is None` tiếp tục bị từ chối fail-closed trong Phase 1 vì thiếu cạnh cấu trúc bảo chứng.
   - `scope_binding` được tự động trích xuất trực tiếp từ `query_metadata` đã xác thực của caller.

---

## 4. Hướng dẫn sử dụng CLI và cách đọc kết quả đầu ra

### 4.1. Lệnh thực thi CLI

Module CLI cho phép kiểm chứng và chạy quy trình xếp hạng độc lập mà không cần môi trường BloodHound hay Neo4j:

```powershell
# Chạy với file kết hợp chứa cả query và danh sách candidates:
.venv\Scripts\python.exe -m src.engine.ranking.cli --input path/to/input.json --output path/to/output.json

# Hoặc chạy với file query và file candidates riêng biệt:
.venv\Scripts\python.exe -m src.engine.ranking.cli --query path/to/query.json --candidates path/to/candidates.json

# Hoặc nhận input từ stdin:
Get-Content path/to/input.json | .venv\Scripts\python.exe -m src.engine.ranking.cli --input -
```

### 4.2. Cấu trúc kết quả đầu ra JSON (`PathRankingResult`)

Kết quả đầu ra JSON bao gồm 7 trường chuẩn tắc:

```json
{
  "query_id": "query-20261001-test-001",
  "version": "1.0.0",
  "search_metadata": {
    "budget_limit": 10,
    "candidates_evaluated": 2,
    "is_truncated": false,
    "truncation_reasons": [],
    "caps_applied": {
      "max_active_work_budget": 10,
      "max_candidates": null,
      "timeout_ms": null,
      "max_expansions": null
    },
    "completeness_scope": "unspecified_subset",
    "search_algorithm": "provided_candidate_assessment"
  },
  "eligible_candidates": {
    "cand_valid": {
      "candidate_id": "cand_valid",
      "bound_action_ids": ["act_reset_pwd", "act_activate_da"],
      "target_asset_id": "S-1-5-21-3623811015-3361044348-30300820-1000",
      "program": ["unit_reset", "unit_activate"],
      "structural_routes": [
        {
          "route_id": "route_cand_valid",
          "node_ids": [
            "S-1-5-21-3623811015-3361044348-30300820-1001",
            "S-1-5-21-3623811015-3361044348-30300820-1000",
            "S-1-5-21-3623811015-3361044348-30300820-1000"
          ],
          "edge_ids": [
            "sha256:1111111111111111111111111111111111111111111111111111111111111111",
            "sha256:2222222222222222222222222222222222222222222222222222222222222222"
          ],
          "provenance_locators": ["loc:001", "loc:002"]
        }
      ],
      "status": "feasible",
      "gates_evaluation": {
        "directory_write_available": "True",
        "session_present": "True",
        "structural_genericall": "True",
        "target_controlled": "True",
        "da_entitlement_active": "True",
        "target_enabled": "True"
      },
      "nominal_effort": 3,
      "effort": 3,
      "effort_status": "rated",
      "unrated_work_units": [],
      "impact": "Critical",
      "consequence_rating": "Critical",
      "impact_status": "rated",
      "likelihood_interval": [
        "14/25",
        "18/25"
      ],
      "likelihood_status": "rated",
      "likelihood_basis_summary": "Derived from prefix conditional bounds product"
    }
  },
  "pareto_frontier": [
    "cand_valid"
  ],
  "diagnostics": {
    "cand_blocked": {
      "reasons": [
        "blocked",
        "likelihood_unrated"
      ],
      "assessment": {
        "candidate_id": "cand_blocked",
        "status": "blocked",
        "effort": null,
        "likelihood_interval": null
      }
    }
  },
  "min_effort_to_da_baseline": {
    "goal_id": "S2",
    "best_candidate_id": "cand_valid",
    "minimum_effort_value": 3,
    "associated_likelihood_interval": [
      "14/25",
      "18/25"
    ],
    "associated_impact": "Critical",
    "coverage_disclosure": "Baseline evaluated over candidate set within active work budget; does not guarantee global minimum if unrated work units or unvisited paths exist.",
    "baseline_coverage": {
      "is_truncated": false,
      "truncation_reasons": [],
      "completeness_scope": "unspecified_subset"
    }
  }
}
```

### Cách đọc các chỉ số quan trọng:
- `pareto_frontier`: Chứa các `candidate_id` tối ưu trên hai trục Rủi ro ($I$ và $[l, u]$). Không có ứng viên nào trên biên này bị ưu thế bởi ứng viên khác.
- `diagnostics`: Chứa toàn bộ ứng viên bị chặn hoặc thiếu bằng chứng kèm theo danh sách lý do `reasons`. Các ứng viên này không được lọt vào `pareto_frontier`.
- `min_effort_to_da_baseline`: Là kết quả tối ưu riêng cho mục tiêu chi phí tối thiểu, độc lập với biên Pareto rủi ro.

---

## 5. Ranh giới tích hợp với Issue #145 và Handoff Protocol

Khối tìm kiếm đồ thị multigraph của Issue #145 sở hữu việc duyệt trạng thái và sinh đường đi. Module `src/engine/ranking/adapter_145.py` thiết lập ranh giới adapter thông qua:

```python
def convert_path_result_to_candidate_envelope(
    path_result: Any,
    candidate_id: str,
    target_asset_id: str,
    query_metadata: dict[str, Any],
    action_mapping: dict[str, str],
    route_id: str = "route-001",
    *,
    bound_actions_catalog: list[dict[str, Any]] | dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]: ...
```

> [!IMPORTANT]
> **Trạng thái tương thích hợp đồng:**
> *Compatible with the current #145 PathResult shape as reviewed, while runtime search integration remains pending merge of #145.*
>
> Ranh giới adapter đã được đồng bộ chuẩn xác với hình dạng đối tượng của PR #146 (`PathResult`, `TransitionStep`, `TransitionResult`, `TransitionRequest`, `Technique`), tuy nhiên việc tích hợp runtime đầy đủ vẫn nằm ở trạng thái **PENDING #145** (chờ PR #146 hoàn tất re-review và merge vào `main`).

### Đặc tả đồng bộ hợp đồng dữ liệu thực tế từ PR #146:
1. **Trích xuất Technique ID chuẩn tắc:** Đọc kỹ thuật từ `step.result.request.technique_id` (ưu tiên theo request) hoặc fallback tương thích `step.result.technique.id`. Từ chối `RankingValidationError` nếu hai trường này xung đột. Cấm fallback ngầm về `step_{idx}` hoặc dùng technique ID làm action ID. Bắt buộc mọi `technique_id` phải tồn tại trong `action_mapping`.
2. **Đối soát chuyển bước 3 chiều (Transition Step ↔ Canonical Edge ↔ Route Segment):**
   - Với mỗi step `idx`, kiểm tra: `edge["source"] == nodes[idx]` và `edge["target"] == nodes[idx + 1]`. Nếu sai nguồn/đích ném lỗi fail-closed `RankingValidationError` (báo rõ `source mismatch` hoặc `target mismatch`).
   - Nếu `step.result.request` có `source`/`target`, đối soát thêm: `request.source == edge["source"]` và `request.target == edge["target"]`. Mâu thuẫn bất kỳ đều bị reject fail-closed.
   - Nếu `bound_actions_catalog` được cung cấp và action có `edge_id`, đối soát: `bound_action.edge_id == step.edge_id`. Nếu catalog chưa được truyền, việc kiểm tra được hoãn lại cho tới khi có search runtime (**PENDING #145**).
3. **Bảo tồn toàn vẹn Provenance Lineage (Zero Evidence Dropping):**
   - Thu thập đầy đủ mọi canonical edge records từ `path_result.edges`, trích xuất toàn bộ records trong `edge["provenance"]` theo Graph Contract 1.3 lossless (bao gồm `timestamp_status`, `collector`, `raw_file`, `record_id`, hoặc SHA-256 hash chuẩn tắc `sha256:{hash}`).
   - Tuyệt đối không collapse danh sách provenance về một record đầu tiên duy nhất và không silently drop record thứ hai.
   - Biểu diễn trong `provenance_locators` bằng chuỗi phân tách ổn định `";".join(locators)`, cho phép khôi phục và kiểm toán đầy đủ 100% bằng `.split(";")`.
   - Cung cấp cấu trúc mở rộng: `provenance_lineage` (danh sách locators/references cho từng cạnh) và `edge_provenance_records` (danh sách raw dicts cho từng cạnh) trong `structural_routes`, cùng `edge_provenance_map` trên candidate envelope.
4. **Không chế tác bằng chứng (Zero Provenance Fabrication):** Adapter từ chối triệt để việc tự sinh pseudo-provenance (`telemetry:edge:...`, `synthetic:...` hoặc `str(edge)`). Mọi bước chuyển có cạnh bắt buộc phải có canonical edge record tương ứng trong `path_result.edges`; nếu thiếu thì fail-closed.
5. **Các bước chuyển dẫn xuất (Derived Steps):** Bước chuyển có `edge_id is None` (derived semantic transitions) tiếp tục bị từ chối fail-closed trong Phase 1 vì thiếu cạnh cấu trúc bảo chứng.
6. **Ràng buộc điểm đầu/cuối của vết đường:** Đảm bảo `nodes[0] == query_metadata["foothold_node_id"]` và `nodes[-1] == target_asset_id`. Bất kỳ sự sai lệch nào đều kích hoạt lỗi fail-closed.
7. **Gắn kết phạm vi tự động:** `scope_binding` gồm 7 trường được trích xuất trực tiếp từ `query_metadata` đã xác thực của caller và gắn chặt vào bao gói ứng viên.
8. Các quan hệ dẫn xuất thời gian chạy (`derived relationships`) không mang `edge_id` cấu trúc và không được ghi đè vào `EngineGraph`.
9. Không đưa thuật toán Dijkstra chi phí cộng dồn đơn trục làm thuật toán xếp hạng toàn đường sản phẩm.

---

## 6. Kết luận và các bước tiếp theo

1. **Phần việc đã hoàn thành:** Khối engine đã có ranh giới đánh giá và xếp hạng có phiên bản độc lập, có **116 ca kiểm thử conformance độc lập pass** cho ranh giới Phase 1 đã triển khai đối với **Specification 1.0.0 quy chuẩn**. Kết quả này xác nhận các trường hợp được bao phủ, chưa xác nhận hoàn tất bounded integration/E2E hoặc kiểm chứng tham số trên dữ liệu thật.
2. **Cổng kiểm soát:**
   - **#143 (TTS A):** [Actual release Week 3](ratings/week3-closeout/README.md) có 21 tham số đã chọn và validation/sensitivity. Consume query_projections sau verify_release. Hai fixtures research/pending giữ lịch sử, không dùng làm nguồn rating sản phẩm hoặc gate chấm lại.
   - **#145 (TTS B):** Chờ xử lý re-review và merge PR #146 cho nền tảng multigraph search (`search coverage = PENDING #145`).
   - **Week 3 bounded integration/E2E:** Chờ #145/#155/#48; bắt buộc kiểm chứng graph/search -> ranking với các trường hợp positive, false và unknown trước nghiệm thu Tuần 3.
   - **Legacy same-snapshot reconciliation:** Chờ #82/#47.
   - **CE/final parity và mở rộng choke-point/performance:** Thuộc mốc sau/#127.
   - **ADR-0013 & Interface 1.0.0:** Đã được TTS A và TTS B chính thức chấp thuận cho phạm vi PR #165 (Review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338), commit `fdf5928`).
   - **Phán quyết SEAMLESS:** phép đánh giá trên ba supplied candidates đã kiểm chứng; bounded graph/search-to-rank integration và final E2E vẫn pending. Cơ sở tham số theo [disposition Week 3](week3-rating-requirement-disposition.md).

## 7. Bảo toàn metadata căn cứ của tham số

- `work_units_ledger` giữ metadata đầu vào (bao gồm `missing_basis_reasons`, `rating_provenance` và phiên bản rating) bên cạnh các trường computational đã normalize; metadata không tự nâng trạng thái `unrated` thành `rated`.
- `conditional_bounds_table` vẫn dùng tuple-keyed Fraction view cho phép tính. `conditional_bounds_records` lưu bản sao độc lập của các bản ghi đã qua validation, giữ `basis_category`, `rationale` và metadata provenance/version.
- Assessment xuất `work_unit_basis` cho các work unit thuộc chương trình hiệu lực và `conditional_bounds_basis` cho các prefix thực sự được dùng; `likelihood_basis_summary` kèm category/rationale khi có. Với prefix bị thiếu hoặc short-circuit, không gán evidence của prefix chưa dùng cho phép tính.
- `parameter_audit` trong result JSON giữ bản sao nguyên vẹn query metadata, raw work-unit ledger, bounds records và target impact assessments đã qua validation. Đây là evidence context của toàn query, bao gồm cả records không được sử dụng khi gating/goal trimming; khác với basis của chương trình hiệu lực trong từng assessment.
- Metadata optional chưa có trong các fixture Phase 1 được giữ là absent, không tự chế tạo căn cứ. Metadata có mặt nhưng sai kiểu bị reject; các record giữ độc lập với caller để mutation sau decode không sửa audit evidence.
- Ranh giới chuyển dịch wire schema: PR #163 đã được merge tại commit `98fb766`, triển khai bộ chuyển dịch `path_ranking_wire_adapter.py` tự động ánh xạ `technique` sang `technique_name`, chuẩn hóa `overlap_state` sang `independent`, và tiêm `scope_binding` cùng `provenance_locators` mà không sửa đổi mã nguồn engine của TTS B.

## 8. Biên bản bàn giao kỹ thuật tái lập cho TTS B (Consolidated Reproducible Handoff for TTS B)

Mục này tổng hợp toàn bộ thông tin bàn giao kỹ thuật để TTS B có thể tái lập 100% kết quả từ checkout sạch.
Mã nguồn engine chuẩn tắc (`src/engine/ranking/`) là hoàn toàn tự chứa và không có bất kỳ phụ thuộc nào vào thư mục `scripts/research/`.
Các lệnh xác thực giả thiết tham số và kiểm tra độ nhạy phân tích sử dụng công cụ nghiên cứu độc lập tại `scripts/research/seamless_parameter_validation.py`:

### 8.1. Pinned Revisions và các phiên bản thành phần
- **Develop commit:** `fdf59285f5af095733b816cc0e76400471b00c4f` (sau khi merge PR #165).
- **Reviewed head:** `dd662f56609d718b264747a5fec70894ae9d4845` (được TTS B phê duyệt tại review #5387665338).
- **Môi trường Python chuẩn tắc (Repository Baseline):** Python **3.14.x** theo đúng `.python-version`, `README.md`, và GitHub CI. Môi trường Python 3.12 trong môi trường ảo `.venv` được sử dụng cục bộ trong quá trình đánh giá và đã xác nhận vượt qua toàn bộ các kiểm thử tương thích.
- **Quy trình khởi tạo môi trường sạch và tái lập tại pinned commit (Clean Checkout Setup):**
  ```bash
  # Tái lập tại đúng pinned commit fdf5928 sau merge PR #165:
  git fetch origin
  git checkout fdf59285f5af095733b816cc0e76400471b00c4f
  git rev-parse HEAD  # Xác nhận đúng fdf59285f5af095733b816cc0e76400471b00c4f
  python3.14 -m venv .venv
  .venv/bin/python -m pip install -r requirements-dev.txt
  ```
  *Lưu ý: `fdf59285f5af095733b816cc0e76400471b00c4f` là revision tái lập engine và artifacts tham số (hậu PR #165), tách riêng với revision tài liệu đồng bộ của PR #166.*
- **Graph Contract:** Phiên bản `1.3.0` (`configs/contract.yml`).
- **Interface Specification:** Phiên bản `1.0.0` quy chuẩn (`docs/research/path-ranking-interface-specification.md`).
- **Scenario ID:** `scenario-seamless-host-to-dc` phiên bản `1.1.0`.
- **Snapshot ID:** `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
- **Parameter Bundle ID:** `bundle-seamless-host-to-dc-v1` phiên bản `1.0.0`.
- **Bundle Content Digest:** `sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`.

### 8.2. Tập tin đầu vào (Tái sử dụng Artifacts hiện có)
- Gói tham số chuẩn tắc: `tests/fixtures/ranking/seamless_parameter_bundle.json`.
- Truy vấn đề xuất Source A: `tests/fixtures/ranking/seamless_proposed_query_input.json`.
- Truy vấn đề xuất Source B: `tests/fixtures/ranking/seamless_source_b_proposed_query_input.json`.
- Truy vấn wire thô Source A: `tests/fixtures/ranking/seamless_query_input.json`.
- Truy vấn wire thô Source B: `tests/fixtures/ranking/seamless_source_b_query_input.json`.
- Bản kê chứng cứ kỹ thuật: `tests/fixtures/ranking/seamless_evidence_manifest.json`.

### 8.3. Lệnh tái lập kiểm chứng
1. **Xác thực toàn diện gói tham số và phân tích độ nhạy (Kiểm chứng cả Source A và Source B):**
   ```bash
   .venv/bin/python scripts/research/seamless_parameter_validation.py --bundle tests/fixtures/ranking/seamless_parameter_bundle.json
   ```
2. **Kiểm tra chuyển dịch wire và đánh giá Source A qua công cụ nghiên cứu:**
   ```bash
   .venv/bin/python scripts/research/seamless_parameter_validation.py --input tests/fixtures/ranking/seamless_proposed_query_input.json
   ```
   *Lưu ý: Tùy chọn `--input` của script nghiên cứu hiện được thiết kế riêng cho bộ phân tích độ nhạy Source A. Để kiểm chứng kịch bản Source B độc lập, sử dụng tùy chọn `--bundle` ở trên hoặc thực thi trực tiếp qua Canonical Engine CLI dưới đây.*
3. **Thực thi trực tiếp và độc lập qua Canonical Engine CLI (Không phụ thuộc mã nghiên cứu):**
   ```bash
   .venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_proposed_query_input.json --output /tmp/seamless_output_a.json
   .venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_source_b_proposed_query_input.json --output /tmp/seamless_output_b.json
   ```
4. **Chạy toàn bộ các bộ kiểm thử liên quan:**
   ```bash
   .venv/bin/pytest tests/test_seamless_parameter_proposal.py -q
   .venv/bin/pytest tests/test_engine_path_ranking_conformance.py -q
   .venv/bin/pytest tests/test_seamless_packet.py -q
   ```

### 8.4. Kết quả kỳ vọng và chẩn đoán
- **Source A (`tests/fixtures/ranking/seamless_proposed_expected_output.json`):**
  - Biên Pareto rủi ro: `["cand_seamless_01_direct_lidia", "cand_seamless_02_alt_vajer_ollie"]` (giữ nguyên không so sánh được).
  - Candidate 1: Xác suất `[42/125, 171/250]`, Nỗ lực 2, Tác động `High`.
  - Candidate 2: Xác suất `[126/625, 55233/100000]`, Nỗ lực 3, Tác động `High`.
  - Min-Effort-to-DA: Ứng viên `cand_seamless_01_direct_lidia` với nỗ lực cực tiểu bằng 2.
- **Source B (`tests/fixtures/ranking/seamless_source_b_proposed_expected_output.json`):**
  - Biên Pareto rủi ro: `["cand_seamless_source_b_01_ollie"]`.
  - Candidate B: Xác suất `[42/125, 171/250]`, Nỗ lực 2, Tác động `High`.
  - Min-Effort-to-DA: Ứng viên `cand_seamless_source_b_01_ollie` với nỗ lực cực tiểu bằng 2.
- **Tệp chẩn đoán kỳ vọng:** `tests/fixtures/ranking/seamless_expected_diagnostics.json` và `seamless_source_b_expected_diagnostics.json`.
- **Báo cáo kiểm chứng:** `reports/research/seamless-parameter-validation-report.json`.

### 8.5. Ràng buộc tính đóng và phạm vi bao phủ (Coverage & Bounds Disclosures)
- **Tính đóng thế giới kín (Closed-world cardinality):** Đúng 9 đơn vị công việc, 11 câu hỏi tiền tố có điều kiện, 12 hành động ràng buộc, 26 giả thiết runtime (tách riêng cho Source A và Source B), và 3 ứng viên hợp lệ.
- **Hợp đồng xác suất:** Tuân thủ nghiệm ngặt bất biến $0 \le \text{lower} \le \text{upper} \le 1$, chấp nhận các điểm cận `["1/1", "1/1"]` và `["0/1", "0/1"]`.
- **Công bố độ bao phủ:** Kết quả được đánh giá trong phạm vi ranh giới công việc `intra_forest`, chân trời `24h`, và ngân sách công việc chủ động 6 đơn vị. Kết quả không đảm bảo cực tiểu toàn cục hoặc sự tồn tại/vắng mặt của đường đi ngoài tập ứng viên đã công bố.

