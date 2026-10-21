# ADR-0013: Mô hình xếp hạng đường tấn công Pareto bảo thủ và đặc tả giao diện bàn giao

- Ngày: 2026-09-30 (Cập nhật quyết định chấp thuận: 2026-10-02)
- Trạng thái: Accepted by TTS A and TTS B for PR #165 scope (Approval #5387665338, commit fdf5928; pending human ratings and subsequent #143/#158 integration/acceptance gates stay separate)
- Người đề xuất: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #143, Refs #158, Refs #165, Refs #162, Refs #163, Refs #42, Refs #140, Refs #141, Refs #142, Refs #150, Refs #151

## Bối cảnh

Quyết định kiến trúc ban đầu ADR-0001 (2026-09-14) đã thiết kế mô hình trọng số 4D MAUT gắn trên từng cạnh cấu trúc đồ thị với profile thực nghiệm `maut_v1`, sử dụng thuật toán Dijkstra để tìm đường có chi phí cộng dồn nhỏ nhất.
Quá trình chuẩn hóa kiến trúc M1 và M2 tại Issue #83 và ADR-0008 đã tách rời đồ thị cấu trúc (Structural Graph) khỏi tầng ngữ nghĩa tấn công (Attack Semantics Layer).
ExpectedTelemetry và các yếu tố chi phí được xác định thuộc về kỹ thuật hoặc bước chuyển ngữ nghĩa, không thể gắn trực tiếp cố định lên từng quan hệ cấu trúc tĩnh.
Do đó, profile `maut_v1` đã được xếp vào diện `production_ready: false` và chỉ đóng vai trò đối chứng lịch sử.
Profile `unit` ($W=1.0$) là baseline duy nhất được chấp thuận cho kiểm thử hồi quy thuật toán ở Milestone 2.
Quyết định kế thừa mô hình trọng số sản phẩm được mở độc lập tại Issue #42.

Trong giai đoạn nghiên cứu M2-A, các yêu cầu về mô hình hóa đường tấn công đã được định hình lại qua các đợt làm rõ với mentor (ngày 2026-09-25 và 2026-09-29) và chuỗi nghiên cứu kỹ thuật:
1. Scenario contract #140 phân định nguồn snapshot và giả thiết runtime; interface dùng bốn evidence buckets độc lập với ba authoritative predicate layers.
2. Bản nháp mô hình xếp hạng và rubric rút gọn được đề xuất tại #141 (path-ranking-model.md).
3. Bộ kiểm chứng worked example và phân tích độ nhạy tại #142 (PR #149, path-ranking-validation.md) đã đưa ra kết luận kiểm chứng tổng thể là **Needs Revision**.
Kết quả thực nghiệm đã chứng minh các giới hạn nghiêm trọng của cách tiếp cận cũ:
- Trọng số cố định theo cạnh không phản ánh được chuỗi hành động có điều kiện tích lũy, các bước chuẩn bị dùng chung (shared preparation), hoặc các bước trung gian xác thực.
- Hai chiều Detectability và Reliability trong mô hình 4D MAUT có nguy cơ đếm trùng (double-count) và thiếu hoàn toàn cơ sở hiệu chuẩn thực nghiệm (empirical calibration).
- Thuật toán Dijkstra trên chi phí cộng dồn đơn trục không thể đồng thời tối ưu hóa xác suất thành công và mức độ thiệt hại nghiệp vụ.
- Thực nghiệm 1 và 2 cho thấy sự xung đột nghiêm trọng giữa chính sách lexicographic (ưu tiên mức độ hậu quả Critical tuyệt đối) và ma trận rủi ro định tính (risk matrix), trong khi dự án chưa có căn cứ khoa học nào để chấp thuận một tỷ lệ đánh đổi (exchange rate) cố định giữa xác suất và tác động.
4. Issue #150 và PR #151 đã hiệu chỉnh và bảo vệ thành công đề xuất xếp hạng Pareto bảo thủ có phạm vi (scoped conservative Pareto proposal).
Reviewer (@nairyuuu) đã chấp thuận đề xuất có phạm vi này tại review PR #151 (pullrequestreview-5362415389).
Đồng thời, phán quyết kiểm chứng cho xếp hạng dự đoán trên snapshot SEAMLESS tiếp tục được giữ nguyên là **Insufficient Evidence**.

Cần có một Architecture Decision Record kế thừa (Successor ADR) chính thức để thay thế phần production weighting của ADR-0001, định hình nguyên tắc xếp hạng Pareto bảo thủ trong phạm vi đã được chấp thuận, và bàn giao interface cho B bounded integration Week 3 theo #158; scalable search thuộc scope sau.

## Các phương án

| Phương án | Lợi ích | Chi phí / hạn chế | Bằng chứng |
| --- | --- | --- | --- |
| 1. Mô hình chi phí cộng dồn theo cạnh (ADR-0001 / Dijkstra) | Đơn giản, tương thích trực tiếp với engine tìm đường Dijkstra hiện có của Milestone 2 | Bỏ qua ngữ cảnh chuỗi tấn công; thất bại trước shared preparation; gộp rủi ro đa chiều thành một giá trị vô hướng duy nhất | ADR-0001, ADR-0008, nghiên cứu #141 |
| 2. Thứ tự từ điển ưu tiên hậu quả tuyệt đối (Impact-first Lexicographic) | Dễ kiểm toán; luôn ưu tiên chặn các hậu quả Critical bất kể xác suất | Dự án chưa có căn cứ phê chuẩn quyền ưu tiên tuyệt đối của hậu quả; che giấu độ bất định (uncertainty) của xác suất | Counterexample thí nghiệm 1 (#142 / #149) |
| 3. Ma trận rủi ro định tính và hàm điểm hữu dụng (Qualitative Risk Matrix / Cardinal Utility) | Cho phép xếp hạng toàn phần (total order); trực quan cho báo cáo ban đầu | Các ngưỡng ô và trọng số đánh đổi là tùy ý, chưa có cơ sở thực nghiệm; tạo ra ranh giới nhạy cảm giả tạo giữa các ô liền kề | Phân tích độ nhạy #142, NIST SP 800-30 Rev. 1 |
| 4. Xếp hạng Pareto bảo thủ trên khoảng xác suất và tác động đích, tie-break bằng nỗ lực định mức (Chọn trong phạm vi này) | Giữ nguyên trade-off và độ bất định; không ép buộc thứ tự toàn phần khi thiếu bằng chứng; phân định rõ ràng giữa các ứng viên đủ bằng chứng và danh sách chẩn đoán | Trả về thứ tự bán phần (partial order), có thể có nhiều ứng viên đồng thời trên biên Pareto; đòi hỏi thuật toán tìm kiếm phù hợp hơn Dijkstra đơn giản | Nghiên cứu #150, kết quả kiểm chứng PR #151 |

## Quyết định và hệ quả

Chúng ta chọn **Phương án 4: Mô hình xếp hạng Pareto bảo thủ trên khoảng xác suất có điều kiện và tác động nghiệp vụ, phân giải tie-break bằng nỗ lực định mức có điều kiện**.

### 1. Phạm vi áp dụng và định nghĩa ranh giới (Scoped Boundary)

Mô hình xếp hạng này được áp dụng chặt chẽ trong phạm vi một truy vấn xác định (Fixed Query Scope):
- Một foothold ban đầu đã được kiểm soát.
- Một bộ kịch bản cụ thể kèm theo các giả thiết runtime có lý do rõ ràng.
- Một mục tiêu xác định (ví dụ S2: usable identity và entitlement DA dùng được).
- Một chân trời thời gian (horizon) và biên công việc (work boundary) cố định.
- Mỗi chương trình ứng viên (candidate program) là một chuỗi tuần tự các hành động cho tới lần đầu tiên đạt được mục tiêu.
- Dữ kiện tích lũy mang tính đơn điệu trong chân trời; chưa mô hình hóa việc thử lại (retry), hiệu ứng xóa (delete effect), hết hạn (expiry), chạy song song (concurrency) hoặc biến đổi chiến thuật sau thất bại.
- Không so sánh các ứng viên thuộc hai scenario khác nhau, hoặc trộn lẫn ứng viên quan sát được với ứng viên synthetic như hai tùy chọn tương đương.

### 2. Hai trục xếp hạng Pareto cốt lõi

Mỗi ứng viên đủ điều kiện được đánh giá trên hai trục rủi ro độc lập:
1. **Tác động nghiệp vụ của sự kiện thành công ($I$):**
- Thang đo gồm 4 bậc xếp hạng thứ tự: $\text{Low} < \text{Medium} < \text{High} < \text{Critical}$.
- Thang đo này phản ánh mức độ hậu quả thiệt hại nghiệp vụ nếu sự kiện tấn công thành công.
- Đánh giá tác động phải được xác lập độc lập với các nhãn bản đồ cấu trúc.
- Theo identity-asset ontology §5, `Tier0` mô tả ranh giới kiểm soát AD, còn `CrownJewel` mô tả giá trị nghiệp vụ.
- Hai nhãn này trực giao nhau; tuyệt đối không tự động đồng nhất `Tier0`, `Domain Admin`, `KRBTGT` hoặc `CrownJewel` thành mức tác động `Critical` nếu không có giải trình hậu quả nghiệp vụ đi kèm.
- Nếu thiếu đánh giá hậu quả nghiệp vụ, ứng viên được gán trạng thái `impact_unrated` và không được đưa vào so sánh rủi ro.

2. **Khoảng xác suất thành công có điều kiện ($P \in [l, u]$):**
- Xác suất thành công của toàn bộ chương trình tấn công được tính theo quy tắc chuỗi (chain rule) trên toàn bộ lịch sử tiền tố thành công:
  $$P(\text{success} \mid F, S, \text{program}) = \prod_{i=1}^k P(E_i \mid F, S, E_1, \ldots, E_{i-1})$$
- Tuyệt đối không nhân các xác suất biên (marginal probabilities) độc lập vì các bước tấn công AD luôn phụ thuộc chặt chẽ vào lịch sử xác thực và đặc quyền trước đó.
- Khi các xác suất thành phần được cấp dưới dạng khoảng chặn $[l_i, u_i]$ cho đúng tiền tố đầy đủ, khoảng bao đóng của toàn chương trình là:
  $$[\prod_{i=1}^k l_i, \prod_{i=1}^k u_i]$$
- Nếu bất kỳ tiền tố nào có giới hạn trên bằng 0 ($u_i = 0$), xác suất toàn chương trình bằng $[0, 0]$ và quá trình tính toán dừng lại mà không cần giải thích các bước sau.
- Nếu thiếu khoảng điều kiện cho bất kỳ tiền tố nào, ứng viên được gán trạng thái `likelihood_unrated` và không được tự ý điền giá trị mặc định.

### 3. Quy tắc ưu thế Pareto bảo thủ (Conservative Pareto Dominance)

Chỉ thực hiện so sánh ưu thế trên các ứng viên đã thỏa mãn điều kiện rủi ro (risk-eligible candidates: trạng thái `feasible`, có đủ `impact` hợp lệ và có đủ khoảng `likelihood_interval`).
Với hai ứng viên A có $(I_A, [l_A, u_A])$ và B có $(I_B, [l_B, u_B])$:
- A ưu thế B (A dominates B) khi và chỉ khi:
  $$I_A \ge I_B \quad \text{và} \quad l_A \ge u_B$$
  đồng thời có ít nhất một bất đẳng thức nghiêm ngặt: $I_A > I_B$ hoặc $l_A > u_B$.
- Quy tắc này bảo đảm tính ưu thế trên mọi điểm giá trị bên trong khoảng bất định; nó bảo thủ và chặt chẽ hơn việc so sánh điểm giữa (midpoint) hoặc so sánh hai cận dưới.
- Nếu hai khoảng giao nhau ($l_A < u_B$ và $l_B < u_A$) hoặc một ứng viên vượt trội ở một trục nhưng kém hơn ở trục kia, hai ứng viên được giữ nguyên trạng thái không so sánh được (`incomparable`).

### 4. Phân giải tie-break bằng nỗ lực định mức có điều kiện (Conditional Effort Tie-Break)

Nỗ lực ($C$) không phải là một trục ưu thế rủi ro chính mà chỉ đóng vai trò tie-break trong trường hợp cực kỳ hẹp:
- Chỉ khi hai ứng viên có **cùng mức tác động** ($I_A = I_B$), **cùng xác suất điểm chính xác** ($l_A = u_A = l_B = u_B$), và **nỗ lực của cả hai ứng viên đều đã được định mức** (`effort_status == "rated"`).
- Khi đó, ứng viên có nỗ lực $C$ thấp hơn sẽ được xếp trước; nếu bằng nhau về $C$ thì kết luận là `tie`.
- Nếu xác suất là khoảng không phải điểm ($l < u$), dù hai khoảng trùng nhau hoàn toàn vẫn không chứng minh xác suất ẩn (latent probability) bằng nhau; do đó phải giữ `incomparable` mà không được dùng nỗ lực để phá vỡ bất định.
- Nếu nỗ lực của một trong hai ứng viên chưa được định mức (`effort is None` hoặc `effort_status == "unrated"`), kết quả giữ `incomparable`.

### 5. Sổ cái công việc chuẩn tắc và tách biệt vết đường cấu trúc (Work Ledger & Route Traces)

- Mỗi đơn vị công việc chủ động (active work unit) có định danh chuẩn tắc duy nhất gồm kỹ thuật, chủ thể thực hiện, đích, ngữ cảnh, biên và phiên bản sổ cái (`technique:actor:target:context:boundary:ledger_version`).
- Nỗ lực được tính theo quy ước rubric nghiên cứu $T_1, T_2 \in \{1, 2, 3\}$ với công thức cơ sở $C = T_1 + T_2 - 2$ ($0 \le C \le 4$ cho đơn vị chủ động, $C = 0$ cho đồng bộ thụ động); đây là quy ước xếp hạng tương đối trong nghiên cứu, không phải giờ công lao động thực nghiệm đã được hiệu chuẩn.
- Các đơn vị công việc đã hoàn thành được lưu trong sổ cái kiên trì (persistent ledger); một lần chuẩn bị dùng chung không bị tính lại nhiều lần.
- Đơn vị công việc đóng vai trò tính nỗ lực và tra cứu tiền tố xác suất.
- **Yêu cầu kiến trúc bắt buộc cho engine:** Hệ thống sản phẩm phải lưu giữ riêng biệt các vết đường cấu trúc và bằng chứng (distinct structural route/evidence traces gồm danh sách node IDs, edge IDs, occurrence locators) tách khỏi danh tính sổ cái công việc.
- Tuyệt đối không dùng số lượng chương trình (program count) thay cho số lượng đường đi (path count).
- Điều này bảo đảm duy trì đầy đủ tính audit và phục vụ chính xác phép phân tích nút thắt cổ chai (choke point) và đối chứng BloodHound ở các mốc sau.

### 6. Duy trì độc lập bài toán Min-Effort-to-DA

- Yêu cầu gốc của đề tài về tìm đường chi phí thấp nhất tới Domain Admin được duy trì dưới dạng một truy vấn riêng biệt (Separate Min-Effort-to-DA Query).
- Truy vấn này sử dụng cùng ngữ nghĩa hành động, cùng sổ cái công việc và điều kiện lọc, nhằm tìm chương trình có tổng nỗ lực nhỏ nhất, sau đó ghi chú xác suất và trạng thái bằng chứng đi kèm.
- Kết quả Min-Effort-to-DA là một baseline độc lập, tuyệt đối không bị đánh đồng hay gộp chung với biên Pareto rủi ro.
- Nếu còn đơn vị công việc chưa được định mức nỗ lực, kết quả phải công bố rõ giới hạn bao phủ (coverage disclosure) và không được tuyên bố là cực tiểu toàn cục.

### 7. Phân vùng chẩn đoán cho dữ kiện thiếu hoặc bị chặn

Mỗi ứng viên không thỏa mãn điều kiện rủi ro phải được phân vùng vào tập chẩn đoán (`diagnostics`) kèm theo toàn bộ lý do:
- `blocked`: do có vị từ thực thi bị xác nhận là False (gating phủ định withholding tính toán xác suất và nỗ lực, chẩn đoán kèm `likelihood_unrated`).
- `unknown`: do thiếu dữ kiện runtime bắt buộc hoặc Gate O chưa có bằng chứng phân quyền (gating bất định withholding tính toán xác suất và nỗ lực, chẩn đoán kèm `likelihood_unrated`).
- `likelihood_unrated`: do thiếu khoảng xác suất có điều kiện cho đúng tiền tố đầy đủ.
- `impact_unrated`: do thiếu đánh giá hậu quả nghiệp vụ cho sự kiện thành công.
Các ứng viên trong tập chẩn đoán giữ nguyên đánh giá nỗ lực định mức (nominal effort) để phục vụ kiểm toán nhưng không bao giờ được tham gia vào biên Pareto.
Quan hệ so sánh trả về `not_eligible`, phân biệt rõ ràng với trạng thái `incomparable` của hai ứng viên đã đủ điều kiện.

### 8. Hợp đồng độ chính xác số học và tuần tự hóa

- Để ngăn chặn lỗi làm tròn dấu phẩy động tạo ra quan hệ ưu thế giả mạo (false dominance), mọi giá trị đầu vào thập phân phải được phân tích chính xác bằng kiểu phân số stdlib `Fraction`.
- Phép nhân khoảng và phép so sánh bất đẳng thức được thực hiện trên miền số hữu tỷ chính xác tuyệt đối.
- Khi tuần tự hóa ra JSON, các giá trị xác suất phải được lưu dưới dạng chuỗi số hữu tỷ bảo toàn thông tin (lossless rational strings, ví dụ `"81/125"`), không làm tròn rồi đưa ngược trở lại hàm so sánh.

### 9. Bàn giao hợp đồng hành vi (Behavioral Oracle Conformance)

- B sở hữu bounded search/evaluator integration #145/#155 theo #158; A cung cấp reviewed scenario/parameters và oracle; scalable search thuộc scope sau.
- TTS A cung cấp bộ đặc tả giao diện, bộ kiểm thử hợp đồng và các synthetic oracles làm tiêu chuẩn nghiệm thu hành vi, không bắt buộc TTS B phải import mã nguồn nghiên cứu vào hệ thống sản phẩm.

### Thay thế ADR-0001 (Supersedes ADR-0001 in part)

Quyết định này thay thế toàn bộ phần thiết kế mô hình trọng số sản phẩm và cơ chế cộng dồn chi phí trên cạnh của ADR-0001:
- Bác bỏ việc sử dụng profile cố định theo cạnh `maut_v1` cho mục đích xếp hạng dự đoán sản phẩm.
- Bác bỏ việc sử dụng thuật toán Dijkstra trên một giá trị chi phí vô hướng duy nhất để đại diện cho rủi ro đường tấn công.
- Giữ nguyên vai trò của profile `maut_v1` như một cơ sở đối chứng thực nghiệm lịch sử.
- Giữ nguyên profile `unit` ($W=1.0$) như một baseline kiểm thử hồi quy kỹ thuật cho engine và contract ở Milestone 2.

## Các cổng chưa giải quyết (Unresolved Gates)

Quyết định Proposed này đề xuất khung thiết kế và interface; các cổng tham số/tích hợp sau vẫn độc lập và pending:
1. **Cổng tham số và định mức độc lập (Parameters Gate):**
- Đánh giá xác suất và nỗ lực trong các ví dụ synthetic hiện tại là các fixture được thiết kế cho mục đích kiểm thử toán học, không phải là tham số sản phẩm.
- A/B hoặc hai người phù hợp trong nhóm có thể đánh giá độc lập và đối soát theo cùng rubric, ghi năng lực/phạm vi thực tế; chuyên gia ngoài, chứng chỉ và chữ ký là tùy chọn, không phải dependency của cổng.
- Research/LLM-assisted scenario estimates được phép dưới declared assumptions với verified sources, đúng conditional quantity, basis/scope/uncertainty/sensitivity và A/B review; nguồn kỹ thuật không tự chứng minh numeric probability.
- Human ratings/agreement chưa thực hiện giữ pending; không dùng hai prompts/models làm hai raters hoặc gọi scenario estimates là empirical calibration.
- Implementation/conformance dưới assumptions có thể tiếp tục khi human agreement pending; final numeric acceptance xét reviewed basis, parameter validation/sensitivity và evidence trong scope theo #143/#158.
2. **Cổng tích hợp và tìm kiếm engine của TTS B (Engine Integration Gate):**
- Thuật toán duyệt mẫu (bounded candidate enumerator) chỉ phục vụ kiểm chứng trên đồ thị nhỏ.
- B sở hữu bounded integration #145/#155 trong Week 3; scalable search/performance mở rộng không phải điều kiện của design acceptance hoặc PR #159.
3. **Cổng kiểm thử cấu trúc, demo và đối chứng (#47, #48, #82):**
- Kiểm thử cấu trúc synthetic và đối soát SEAMLESS vs Legacy 4.0.3 thuộc phạm vi nghiệm thu #47.
- Kịch bản demo synthetic và SEAMLESS kèm báo cáo sai lệch đối soát (#47, #82, #139) thuộc phạm vi bàn giao M2 (#48).
- Thiết lập baseline cấu trúc trên cùng snapshot phục vụ nghiệm thu M2 và mở đường cho so sánh đối chứng mở rộng với BloodHound CE tại Milestone 4 (#82).
4. **Phán quyết về độ hỗ trợ dữ liệu:**
- Phán quyết khoa học trên snapshot SEAMLESS tiếp tục là **Insufficient Evidence** cho đến khi toàn bộ các khoảng xác suất tiền tố và đánh giá tác động có đầy đủ căn cứ kiểm chứng.

## Tiêu chí chuyển trạng thái sang Accepted (Acceptance Disposition Checklist)

Việc merge PR #152 vào develop tại commit `4325ae0` là sự chấp thuận đối với bản đề xuất nghiên cứu (Reviewed Research Proposal) và bản dự thảo đặc tả giao diện 1.0.0-draft ở trạng thái Proposed.
Việc merge PR #154 tại commit `afbc1c7` phê chuẩn gói định mức độc lập và công cụ quản trị đối soát, nhưng vẫn giữ trạng thái ADR-0013 là Proposed.
Báo cáo đánh giá chi tiết từng tiêu chí nghiệm thu được lưu vết tại [path-ranking-acceptance-disposition.md](../research/path-ranking-acceptance-disposition.md).
Tại PR #165, Reviewer TTS B (@nairyuuu) đã chính thức phê duyệt disposition tại review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338) trên exact head `dd662f5`, và PR #165 đã được merge vào develop tại commit `fdf5928`.
Checklist nghiệm thu chuyển trạng thái sang Accepted cho phạm vi PR #165:

| Hạng mục xem xét | Điều kiện nghiệm thu để chuyển Accepted | Trạng thái hiện tại |
| --- | --- | --- |
| 1. Khung lý thuyết Pareto bảo thủ | Chấp thuận nguyên tắc so sánh trên khoảng xác suất có điều kiện và tác động nghiệp vụ, phân giải tie-break bằng nỗ lực định mức trong phạm vi hẹp. | Đã review qua PR #151 và PR #152; thống nhất nguyên tắc. TTS A và TTS B đã chính thức chấp thuận (Accepted by TTS A & TTS B tại #5387665338, commit fdf5928). |
| 2. Đặc tả giao diện v1.0.0 | Khóa hợp đồng dữ liệu đầu vào, đầu ra, chuẩn hóa phân số Fraction và các mã lỗi chẩn đoán khi chuyển Accepted. | Đã review bản draft qua #152 và #154; được kiểm chứng độc lập bởi conformance tests của TTS B tại PR #156; adapter migration đã merge tại PR #163. TTS A và TTS B đã chính thức chấp thuận 1.0.0 quy chuẩn (Accepted by TTS A & TTS B tại #5387665338, commit fdf5928). |
| 3. Tách biệt cấu trúc và sổ cái | Engine của TTS B cam kết lưu giữ vết đường cấu trúc (node IDs, edge IDs) độc lập với định danh sổ cái công việc (work ledger). | Đã quy định trong đặc tả giao diện; TTS B đã hiện thực hóa `RouteEdgeSegment` và `StructuralRouteTrace` tại PR #156 (head `fdf7139`). TTS A và TTS B đã chính thức chấp thuận (Accepted by TTS A & TTS B tại #5387665338, commit fdf5928). |
| 4. Gói định mức độc lập | Chuẩn bị đầy đủ tài liệu scenario hẹp, tài sản đích, căn cứ kỹ thuật, hai phiếu chấm trống độc lập và quy trình đối soát. | Đã phát hành Scoped Parameter Bundle 1.0.0 (digest `sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`); xác thực giải tích và kiểm thử độ nhạy chạy sạch. TTS B đã chấp thuận trong phạm vi PR #165 (#5387665338); bảng điểm con người tiếp tục bảo lưu pending. Bundle: Released; Ratings: Pending. |
| 5. Phán quyết dữ liệu SEAMLESS | Chấp thuận boundary giữa declared scenario estimates, human agreement và empirical calibration; numerical verdict theo reviewed basis/validation trong scope, không yêu cầu external panel/signature/live attack. | Hiện Insufficient Evidence cho xếp hạng dự đoán sản phẩm vì chưa có căn cứ đã review, đánh giá độc lập của con người và validation trong scope; empirical calibration là hạng mục tùy chọn/tương lai, không phải cổng chặn bắt buộc; design acceptance không chờ ratings. |
| 6. Phê duyệt chính thức từ Reviewer | Reviewer (@nairyuuu) thực hiện review disposition chính thức trên Issue #143 hoặc PR chuyển trạng thái. | Reviewer (@nairyuuu) đã hoàn tất phê duyệt chính thức tại review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338) trên head `dd662f5`, merged tại commit `fdf5928`. Accepted by TTS A & TTS B cho phạm vi PR #165. |

Design acceptance hoàn tất trong phạm vi đã phê duyệt của PR #165 theo [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158).
Status/gates dùng chung là [acceptance disposition Mục 2](../research/path-ranking-acceptance-disposition.md).
Compatibility review của B hỗ trợ design decision, không phải prerequisite engine đã tích hợp.
ADR và interface đã được TTS A và TTS B chấp thuận chính thức cho phạm vi PR #165; các cổng actual ratings, empirical calibration, engine integration #145/#155, Legacy reconciliation #47 và product E2E #48 tiếp tục giữ nguyên ranh giới độc lập và mở.


## Kiểm chứng và điều kiện xem lại

- **Kiểm thử hiện có:** Bộ kiểm thử nghiên cứu tại `tests/test_worked_example_validation.py` (38/38 tests passed) và CLI kiểm chứng tại `scripts/research/worked_example_validation.py` (Experiment 6 overall PASS, model verdict Insufficient Evidence).
- **Kiểm thử giao diện mới:** Bộ kiểm thử đặc tả giao diện tại `tests/test_path_ranking_interface.py` kiểm tra đầy đủ các ràng buộc hợp đồng, phân vùng chẩn đoán, phép so sánh Pareto, tie-break nỗ lực và tính toàn vẹn số học.
- **Điều kiện xem lại:**
- Khi nhận được phản hồi disposition từ @nairyuuu để chuyển trạng thái sang Accepted theo quy trình.
- Khi có kết quả từ quy trình đối soát định mức độc lập cho các tham số kiểu sản phẩm.
- Khi B review compatibility hoặc chạy bounded integration #145/#155 và phát hiện interface gaps; không đợi completed engine để nghiệm thu thiết kế.
