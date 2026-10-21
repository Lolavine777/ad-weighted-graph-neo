# Báo cáo kiểm chứng thực nghiệm mô hình xếp hạng đường tấn công

Trạng thái: **Đề xuất nghiên cứu đã phê duyệt (Proposal Approved) - Chưa đủ bằng chứng thực nghiệm trên SEAMLESS (Insufficient Evidence)**.
Tác giả: Nhóm TTS A (@Lolavine777), ngày 2026-09-30.
Mã theo dõi: Issue [#150](https://github.com/nairyuuu/ad-weighted-graph/issues/150), Issue [#142](https://github.com/nairyuuu/ad-weighted-graph/issues/142), Issue [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), Pull Request [#151](https://github.com/nairyuuu/ad-weighted-graph/pull/151), Pull Request [#149](https://github.com/nairyuuu/ad-weighted-graph/pull/149).
Tài liệu tham chiếu cốt lõi: [Đặc tả mô hình Pareto bảo thủ](path-ranking-model.md), [Bản tóm tắt kịch bản và bằng chứng chi phí](week3-scenario-cost-evidence.md).

Tài liệu này tổng hợp toàn bộ kết quả kiểm chứng thực nghiệm cho bài toán xếp hạng đường tấn công trong Active Directory.
Báo cáo được cấu trúc thành hai phần rõ rệt:
- **Mục 0**: Trình bày kết quả kiểm chứng hiện hành của đề xuất mô hình Pareto bảo thủ có phạm vi xác định (Issue #150 đã được phê duyệt qua PR #151), bao gồm các thuật toán kiểm tra tính bất biến đóng gói, cơ chế tính xác suất chuỗi đầy đủ bằng số học hữu tỉ chính xác, phân vùng chẩn đoán, và đối chứng với Oracle tìm kiếm vét cạn.
- **Mục 1 đến Mục 10**: Lưu giữ toàn bộ dữ liệu lịch sử của bộ kiểm chứng Issue #142 (PR #149), bao gồm các ca tính tay đối chứng trên dữ liệu SEAMLESS, bảng chân lý 27 tổ hợp cổng theo logic Kleene, và các bằng chứng thực nghiệm dẫn tới kết luận Cần chỉnh sửa (Needs Revision) đối với bản nháp mô hình từ điển ban đầu.

---

## 0. Kết quả kiểm chứng hiện hành của đề xuất Pareto bảo thủ (#150 / PR #151)

### 0.1. Câu hỏi nghiên cứu, giải pháp đề xuất và kết luận thẩm định
Sau khi bộ thử nghiệm tại Issue #142 chỉ ra các hạn chế nghiêm trọng của mô hình phân cấp từ điển tuyệt đối và hàm phi tuyến với thuật toán Dijkstra, nhóm nghiên cứu TTS A đã đề xuất một phương án hiệu chỉnh có phạm vi xác định tại Issue #150:
1. **Lựa chọn mô hình**: Áp dụng nguyên lý ưu thế Pareto bảo thủ trên hai trục: Mức độ tác động nghiệp vụ ($I$) và Khoảng xác suất thành công có điều kiện ($[l, u]$), kết hợp với sổ cái công việc chuẩn tắc để tính chi phí nỗ lực ($C$).
2. **Lý do lựa chọn**: Dự án hiện chưa có cơ sở thực nghiệm để xác lập một tỷ lệ quy đổi số học hoặc một hàm hữu dụng duy nhất giữa mức độ thiệt hại kinh doanh và xác suất khai thác.
   Do đó, việc giữ lại sự đánh đổi và độ bất định dưới dạng quan hệ thứ tự bộ phận (partial order) phản ánh trung thực bản chất dữ liệu, giúp chuyên gia an ninh nhìn thấy các phương án tối ưu thay vì bị phụ thuộc vào thứ hạng số học áp đặt.
3. **Kết luận thẩm định**:
   - **Mã nguồn và kiểm thử logic nghiên cứu (Research checks)**: **ĐẠT (PASS 100%)**.
     Toàn bộ 38 bài kiểm thử tự động đều khớp tuyệt đối với các bất biến toán học và Oracle đối chứng.
   - **Khả năng xếp hạng dự báo trên dữ liệu thực tế SEAMLESS**: **CHƯA ĐỦ BẰNG CHỨNG (Insufficient Evidence)**.
     Việc các thuật toán nghiên cứu vượt qua bài kiểm tra logic trong môi trường giả định không đồng nghĩa với việc mô hình đã sẵn sàng đưa vào vận hành thực tế.
     Rào cản nằm ở việc snapshot tĩnh SEAMLESS chưa có bảng khoảng xác suất có điều kiện được thẩm định, mảng phiên làm việc đo lường rỗng, quyền sao chép thư mục Gate O vẫn ở trạng thái bất định (`Unknown`), và khung nỗ lực T1/T2 mới chỉ dừng lại ở quy ước rubric minh họa.

### 0.2. Danh mục các bài kiểm tra bổ sung, đáp án tính tay và đối chứng hàm
Mã nguồn nghiên cứu tại `scripts/research/worked_example_validation.py` và `tests/test_worked_example_validation.py` đã được mở rộng với Thí nghiệm 6 (Experiment 6).
Bộ kiểm thử mới bổ sung 9 ca kiểm thử trong lớp `ScopedProposalTests` (được viết theo phương pháp TDD, chạy thất bại trước khi cài đặt giải thuật), đồng thời bảo toàn nguyên vẹn 29 bài kiểm thử hồi quy lịch sử.
Đặc biệt, quá trình thẩm định độc lập đã phát hiện và xử lý hai trường hợp biên quan trọng:
- Xử lý tiền tố có xác suất bằng 0: Dừng tính toán và gán ngay khoảng bao đóng $[0, 0]$ mà không đòi hỏi thêm dữ kiện điều kiện phía sau.
- Loại bỏ ưu thế giả do sai số làm tròn số thực: Sử dụng lớp `Fraction` trong thư viện chuẩn Python cho mọi phép tính số học, đồng thời xuất dữ liệu JSON dưới dạng chuỗi phân số tối giản (ví dụ `"81/125"` thay vì số thực `0.648`).

Dưới đây là bảng đối chiếu 15 ca kiểm thử điển hình giữa đáp án tính tay lý thuyết và kết quả do hàm thực thi:

| Câu hỏi kiểm chứng | Đáp án tính tay / Quy tắc xử lý | Hàm thực thi và Bằng chứng chạy |
| :--- | :--- | :--- |
| **Đánh đổi Tác động cao / Xác suất thấp vs Tác động vừa / Xác suất cao** | Cặp ứng viên Critical $[0.1, 0.2]$ và High $[0.8, 0.9]$: Hai bên giữ trạng thái không so sánh được (`incomparable`) ở cả hai chiều. | Hàm `scoped_preference()`; test case `test_scoped_preference_tradeoff`. |
| **Xác lập ưu thế Pareto dứt khoát** | Cặp ứng viên Critical $[0.1, 0.2]$ và High $[0.05, 0.09]$: Đường Critical ưu thế tuyệt đối do tác động cao hơn và toàn bộ khoảng xác suất vượt trội ($0.1 \ge 0.09$). | Hàm `scoped_preference()`; test case `test_scoped_preference_dominance`. |
| **Phân định nhãn kỹ thuật và nhãn tác động nghiệp vụ** | Việc thay đổi nhãn `Tier0` hay `CrownJewel` không làm thay đổi thứ tự ưu tiên khi mức xếp hạng hậu quả nghiệp vụ (consequence rating) giữ nguyên. Nếu thiếu hậu quả nghiệp vụ, hàm trả về `not_eligible`. | Test case `test_impact_ordinal_independent_of_ontology_labels`. |
| **Cách ly ứng viên thiếu bằng chứng khỏi biên Pareto** | Chỉ các ứng viên đủ tư cách rủi ro mới được tham gia xây dựng biên Pareto. Các ứng viên bị chặn (`blocked`), bất định (`unknown`), hoặc thiếu đánh giá (`likelihood_unrated`, `impact_unrated`) đều bị cách ly vào `diagnostics`. | Hàm `scoped_frontier()` kết hợp `risk_ineligibility()`; test case `test_scoped_frontier_partitions_ineligible_candidates`. |
| **Bảo toàn trạng thái nỗ lực chưa đánh giá (`effort = None`)** | Một đơn vị công việc trong sổ cái có giá trị `None` khiến nỗ lực của toàn bộ chuỗi nhận giá trị `None`. Trường hợp hòa điểm xác suất điểm nhưng có nỗ lực chưa đánh giá sẽ giữ trạng thái `incomparable`. | Hàm `assess_scoped_program()`; test case `test_unrated_effort_point_tie_remains_incomparable`. |
| **Khoảng xác suất chồng lấn hoặc giống nhau nhưng không là điểm** | Trả về `incomparable`. Việc hai khoảng xác suất giống nhau nhưng có độ rộng ($l < u$) không chứng minh được xác suất tiềm ẩn bằng nhau, do đó không được tự ý dùng nỗ lực để phá vỡ hòa điểm. | Test case `test_scoped_preference_incomparable_overlapping`. |
| **Phân giải hòa điểm bằng nỗ lực khi xác suất điểm bằng nhau** | Khi hai đường có cùng mức tác động và cùng xác suất điểm $P = 0.60$, đường có nỗ lực $C = 3$ được xếp trước đường có nỗ lực $C = 4$. Nếu cùng nỗ lực thì hòa điểm (`tie`). | Test case `test_scoped_preference_point_tie_with_effort`. |
| **Nhân xác suất chuỗi đầy đủ (Full-history conditioning)** | Bước reset có khoảng $[0.8, 0.9]$, bước kích hoạt danh tính với điều kiện đã reset có khoảng $[0.6, 0.7]$. Khoảng bao đóng toàn chuỗi là $[0.8 \times 0.6, 0.9 \times 0.7] = [0.48, 0.63]$. | Hàm `assess_scoped_program()`; thiếu tiền tố đầy đủ sẽ khiến xác suất mang trạng thái `unrated`. |
| **Tính toán nỗ lực cho bước chuẩn bị dùng chung** | Chuỗi hành động gồm chuẩn bị ($c=3$), hai nhánh con ($c=2$ mỗi nhánh), và bước kết thúc ($c=1$). Tổng nỗ lực chuẩn tắc là $3 + 2 + 2 + 1 = 8$. | Hàm `assess_scoped_program()`; không cộng dồn hai nhánh độc lập thành 11. |
| **Bất biến trước cách đóng gói tách và gộp hành động** | Dạng tách `[reset, activate]` và dạng gộp `[reset_and_activate]` đều quy về hai đơn vị công việc chuẩn tắc, nhận cùng nỗ lực $C = 3$ và cùng khoảng xác suất $[0.48, 0.63]$. | Test case `test_action_packaging_invariance_split_vs_merged`. |
| **Bất biến đóng nhóm thành viên qua 1 hop và 3 hop lồng nhau** | Các gói hành động đóng nhóm thành viên thụ động có chi phí bằng 0, không làm thay đổi nỗ lực, khoảng xác suất hay ngân sách công việc chủ động. | Test case `test_passive_group_closure_invariance`. |
| **Quyền phủ quyết của bằng chứng phủ định (Negative Veto)** | Bằng chứng phủ định `False` hấp thụ trạng thái bất định `Unknown`. Bước tấn công lập tức chuyển trạng thái `blocked`, nỗ lực khả thi nhận giá trị `None`. | Test case `test_scoped_gate_evaluation_negative_veto`. |
| **Tiền tố có xác suất bằng 0** | Khi một bước trong tiền tố nhận khoảng $[0, 0]$, toàn bộ chuỗi tấn công nhận khoảng $[0, 0]$ mà không cần đòi hỏi dữ kiện điều kiện phía sau. | Test case `test_zero_probability_prefix_short_circuit`. |
| **Bảo toàn tính hòa điểm qua các hoán vị bằng số học phân số** | Tích số của ba thừa số hữu tỉ $0.2$, $0.3$, $0.4$ trên cả 6 hoán vị đều cho kết quả chính xác bằng phân số $3/125$, triệt tiêu hoàn toàn sai số dấu phẩy động. | Test case `test_rational_arithmetic_permutation_invariance`. |
| **Từ chối dữ liệu đầu vào không hợp lệ** | Các khoảng xác suất bị đảo mút (ví dụ $[0.8, 0.2]$), nhận giá trị âm, vượt quá 1.0, hoặc chứa `NaN` đều bị hàm từ chối xử lý và báo lỗi rõ ràng. | Test case `test_invalid_probability_bounds_rejection`. |

### 0.3. Hợp đồng tìm kiếm và đối chứng với Oracle vét cạn
Để kiểm chứng năng lực tìm kiếm của mô hình mà không cần can thiệp vào engine sản phẩm của TTS B, công cụ nghiên cứu xây dựng hàm `bounded_programs()`:
- **Biểu diễn trạng thái**: Mỗi trạng thái bao gồm tập dữ kiện đúng đã tích lũy và danh sách có thứ tự các đơn vị công việc chủ động đã hoàn tất.
  Ngữ cảnh truy vấn được cố định trong suốt quá trình duyệt.
- **Nguyên tắc duyệt**: Chỉ mở rộng các hành động làm xuất hiện dữ kiện mới; dừng nhánh duyệt ngay khi lần đầu tiên chạm tới mục tiêu; bỏ qua các chu trình không sinh thêm dữ kiện.
- **Ngân sách công việc chủ động ($B$)**: Giới hạn số lượng đơn vị công việc chủ động phân biệt.
  Khi có nhánh vượt quá ngân sách, công cụ công bố cờ cắt cụt (`truncated = True`).

Kết quả tìm kiếm của `bounded_programs()` được đối chứng chéo với hai Oracle độc lập:
1. `exhaustive_search()`: Thuật toán duyệt vét cạn trên đồ thị có hướng phi chu trình mở rộng (lifted DAG).
2. `permutation_program_oracle()`: Thuật toán sinh hoán vị độc lập thứ tự duyệt để kiểm tra tính đầy đủ của các chuỗi khả thi.
Hai cách duyệt đối chứng này độc lập về phương pháp triển khai thuật toán tìm kiếm nhưng dùng chung đặc tả ngữ nghĩa mô phỏng để kiểm tra chéo tính đầy đủ của thuật toán, không phải hai nguồn chứng cứ độc lập về Active Directory thực tế.

Dưới đây là kết quả đối chứng qua các mức ngân sách công việc chủ động:

| Ngân sách công việc ($B$) | Số chuỗi ứng viên sinh ra | Mức độ khớp với Oracle | Đánh giá mức độ bao phủ và Mục tiêu Pareto |
| :---: | :---: | :--- | :--- |
| **$B = 0$** | 0 | Khớp tuyệt đối với Permutation Oracle. | Bị cắt cụt (`truncated = True`); không được suy diễn là đồ thị không có đường đi. |
| **$B = 1$** | 1 (`cheap_low`) | Khớp tuyệt đối với Permutation Oracle. | Bị cắt cụt (`truncated = True`); chỉ tìm thấy đường rẻ tiền với xác suất thấp. |
| **$B = 3$** | 4 | Khớp tuyệt đối với cả hai Oracle. | Bị cắt cụt (`truncated = True`); bỏ sót hai chuỗi dùng chung có xác suất cao xuất hiện ở ngân sách đầy đủ. |
| **$B = 4$** | 8 | Khớp tuyệt đối với cả hai Oracle. | Bao phủ toàn bộ không gian trạng thái của mô hình thử nghiệm nhỏ; không bị cắt cụt. |

Phân tích kết quả tại ngân sách $B = 4$:
- Biên Pareto gồm hai đường chia sẻ công việc chuẩn bị: `shared_ab` và `shared_ba` (cùng mức tác động, cùng xác suất $P = 0.648$, cùng nỗ lực $C = 8$, hòa điểm).
- Đường nỗ lực tối thiểu tới mục tiêu (min-effort) là `cheap_low` ($P = 0.20$, $C = 1$).
  Đường này có chi phí thấp nhất nhưng bị loại khỏi biên Pareto do xác suất quá thấp.
  Thực nghiệm này một lần nữa khẳng định bài toán min-effort và bài toán tối ưu rủi ro Pareto là hai mục tiêu hoàn toàn tách biệt.

### 0.3.1. Các hiệu chỉnh xử lý phản hồi từ Maintainer trong PR #151
Trong quá trình xem xét PR #151, maintainer @nairyuuu đã đưa ra hai yêu cầu sửa đổi mức ưu tiên 1 (P1 blockers) và một khuyến nghị kiến trúc mức 2 (P2 note):
1. **Phân vùng tư cách trước khi xây dựng biên Pareto (P1)**:
   Trước khi hiệu chỉnh, hàm so sánh trả về `incomparable` cho các ứng viên thiếu dữ kiện, khiến các ứng viên này lọt vào biên Pareto chỉ vì không bị ứng viên nào lấn át.
   Nhóm nghiên cứu đã bổ sung hàm kiểm tra tư cách `risk_ineligibility()`.
   Toàn bộ các ứng viên bị chặn (`blocked`), bất định (`unknown`), hoặc thiếu đánh giá (`likelihood_unrated`, `impact_unrated`) bị cách ly vào danh mục chẩn đoán (`diagnostics`).
   Quan hệ `incomparable` chỉ được áp dụng giữa hai ứng viên đã đáp ứng đầy đủ tư cách rủi ro.
2. **Biểu diễn trạng thái nỗ lực chưa đánh giá (P1)**:
   Trước khi hiệu chỉnh, hàm tính toán luôn ép nỗ lực về một con số nguyên, gây lỗi hoặc tính toán sai lệch khi có đơn vị công việc chưa được định lượng.
   Nhóm đã cập nhật hàm `assess_scoped_program()` để bảo toàn trạng thái `effort = None` khi có đơn vị công việc chưa được đánh giá.
   Đồng thời, hàm so sánh chỉ kích hoạt quy tắc phân giải hòa điểm bằng nỗ lực khi cả hai ứng viên đều có nỗ lực hợp lệ; nếu một trong hai bên có nỗ lực mang giá trị `None`, quan hệ được giữ nguyên là `incomparable`.
3. **Bảo toàn vết đường cấu trúc trong tích hợp sản phẩm (P2)**:
   Mã nguồn nghiên cứu thực hiện thu gọn các chuỗi hành động có cùng chuỗi đơn vị công việc có thứ tự (canonical ordered work sequence) để kiểm chứng tính bất biến đóng gói.
   Theo thỏa thuận thẩm định, giới hạn này được chấp nhận cho mã nguồn mẫu thử của TTS A, nhưng tài liệu bắt buộc phải ghi rõ yêu cầu bàn giao: Khi TTS B tích hợp engine ở Milestone M3, hệ thống bắt buộc phải lưu trữ riêng biệt danh sách các đường đi cấu trúc thực tế (`structural_routes`) để phục vụ kiểm toán và đối chứng BloodHound.

### 0.4. Kiểm chứng hồi quy và ranh giới dữ liệu thực tế trên snapshot SEAMLESS
Bộ kiểm thử bảo toàn 100% các bài kiểm tra hồi quy từ Issue #142 và Issue #149:
- Kiểm tra 6 tiền điều kiện reset mật khẩu có thẩm quyền.
- Tính độc lập của Checkpoint S1 reset đối với các quan hệ cấu trúc phía sau (S2/S3).
- Cơ chế phân giải ba giá trị đóng an toàn (fail-closed).
- Quyền phủ quyết tuyệt đối của bằng chứng phủ định (`False > Unknown > True`).
- Xác thực toàn vẹn 6 file trong manifest của snapshot SEAMLESS (`seamless-raw-v1.json`).

Ranh giới dữ liệu thực tế:
- Kiểm tra thực địa trên snapshot SEAMLESS xác nhận 100/100 máy trạm đều có mảng thuộc tính `Computer.Sessions[]` rỗng.
  Do đó, Đường 2 (HasSession) thuần túy là một ví dụ phản chứng giả định nhằm kiểm tra thuật toán, không phải là đường tấn công có căn cứ chứng minh từ dữ liệu.
- Phân quyền sao chép thư mục tại Gate O vẫn ở trạng thái `Unknown`, do snapshot chưa cung cấp bằng chứng phân quyền replication trên domain naming context.
- Các mức định tính Low, Medium, High, Critical và các con số xác suất trong kiểm thử là dữ liệu giả định kịch bản, không phải là số liệu đo lường thực tế từ SEAMLESS.

### 0.5. Các khoảng trống bằng chứng chưa được giải quyết và lộ trình chuyển giao

| Khoảng trống kỹ thuật | Tác động đối với hệ thống | Kế hoạch giải quyết và Người phụ trách |
| :--- | :--- | :--- |
| **Thiếu bảng khoảng xác suất có điều kiện trên SEAMLESS** | Chưa thể xuất ra biên Pareto có độ tin cậy thực tế cho các đường tấn công trên dữ liệu SEAMLESS. | TTS A: Thiết kế phương pháp thu thập ý kiến chuyên gia có căn cứ giải trình; không bắt buộc thực thi chuỗi tấn công thật. |
| **Khung rubric nỗ lực T1/T2 chưa được thẩm định độc lập** | Phép tính nỗ lực hiện tại mới là quy ước mẫu, chưa phản ánh độ phức tạp thao tác thực tế. | TTS A: Rà soát tính độc lập của các tiêu chí, phân định ranh giới chồng lấn công việc trước khi ban hành bộ tham số sản phẩm. |
| **Quyền sao chép Gate O chưa có bằng chứng kiểm chứng** | Mục tiêu S3 (trích xuất credential store qua DCSync) chưa được hỗ trợ trong cả hai chế độ đánh giá. | Cổng kiểm chứng dữ liệu độc lập; duy trì trạng thái `Unknown` cho tới khi có dữ liệu xác thực từ môi trường AD thật. |
| **Thuật toán tìm kiếm nghiên cứu chỉ áp dụng trên đồ thị nhỏ** | Hàm `bounded_programs()` không đáp ứng được yêu cầu về hiệu năng trên đồ thị hàng triệu phần tử. | Issue #143 chốt giao diện; TTS B toàn quyền thiết kế cấu trúc dữ liệu và thuật toán tìm kiếm tối ưu tại Milestone M3. |

Trình tự chuyển giao kỹ thuật được duy trì nhất quán:
$$\text{Testbed nghiên cứu (#142)} \longrightarrow \text{Đề xuất Pareto (#150 / PR #151)} \longrightarrow \text{Successor ADR và Giao diện (#143)} \longrightarrow \text{Engine sản phẩm (TTS B / M3)}$$

### 0.6. Hướng dẫn tái lập kết quả kiểm chứng hiện hành
Để tái lập toàn bộ kết quả kiểm thử của đề xuất mô hình, thực hiện các lệnh sau từ thư mục gốc của kho lưu trữ bằng môi trường ảo Python 3.14 (`.venv`):

```bash
# 1. Chạy toàn bộ các thí nghiệm kiểm chứng và xuất báo cáo chi tiết
.venv/bin/python scripts/research/worked_example_validation.py --all

# 2. Xuất dữ liệu kiểm chứng dưới định dạng JSON máy đọc được
.venv/bin/python scripts/research/worked_example_validation.py --json

# 3. Chạy bộ kiểm thử tự động cho toàn bộ các ca thử nghiệm
.venv/bin/python -m pytest tests/test_worked_example_validation.py -v

# 4. Kiểm tra chất lượng mã nguồn, định dạng và tuân thủ hợp đồng kho lưu trữ
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m yamllint .
.venv/bin/python scripts/check_repository.py
.venv/bin/python scripts/check_contract.py
```

---

## Báo cáo lịch sử kiểm chứng Issue #142 (PR #149)

*Lưu ý lịch sử: Toàn bộ nội dung từ Mục 1 đến Mục 10 dưới đây được giữ nguyên vẹn từ báo cáo nghiệm thu của Issue #142 (sáp nhập qua PR #149).
Các mục này ghi lại quá trình thực nghiệm đối chứng trên dữ liệu SEAMLESS dẫn tới kết luận Cần chỉnh sửa (Needs Revision) đối với bản nháp mô hình từ điển ban đầu.
Các khuyến nghị lịch sử trong Mục 9 đã được hiện thực hóa và thay thế bởi đề xuất Pareto bảo thủ tại Mục 0.*

---

## 1. Mục tiêu, phạm vi và trạng thái kiểm chứng

### 1.1. Bối cảnh kỹ thuật và nhiệm vụ kiểm chứng
Trong khuôn khổ đề tài nghiên cứu đồ thị trọng số Active Directory, mô hình tại [path-ranking-model.md](path-ranking-model.md) đã đề xuất phương án chuyển dịch từ trọng số cạnh tĩnh đơn lẻ (`maut_v1`) sang mô hình phân cấp từ điển có gating $\text{Rank} = \langle I \downarrow, P \downarrow, C \uparrow \rangle$.
Đồng thời, mô hình đề xuất khung rubric 4 chiều rút gọn (T1-T4) và quy tắc ánh xạ chi phí nỗ lực $C = T1 + T2 - 2$.
Theo nhiệm vụ được giao tại Issue [#142](https://github.com/nairyuuu/ad-weighted-graph/issues/142), nhóm TTS A thực hiện kiểm chứng thực nghiệm độc lập toàn bộ các giả thuyết, công thức toán học và ca tính tay đối chứng trên dữ liệu snapshot SEAMLESS.
Mục tiêu là xác định rõ các giới hạn của mô hình, kiểm tra tính ổn định trước các biến thể tham số, và phát hiện các khiếm khuyết lý thuyết tiềm ẩn trước khi chuyển giao sang hiện thực hóa thuật toán.

### 1.2. Phạm vi và ranh giới nghiên cứu
Báo cáo kiểm chứng tập trung vào các phạm vi xác định:
1. **Kiểm chứng ca tính tay đối chứng**: Đối chiếu từng bước giữa tính toán lý thuyết trong ca tính tay đối chứng của [path-ranking-model.md](path-ranking-model.md) với script tự động hóa trên dữ liệu snapshot SEAMLESS.
2. **Đánh giá sự đánh đổi giữa Tác động đích ($I$) và Khả năng thành công ($P$)**: So sánh mô hình từ điển với mô hình rủi ro kỳ vọng tích số ($R = I \times P$) và ma trận rủi ro định tính; làm rõ bản chất heuristic của phép nhân điểm thứ bậc.
3. **Phân tích độ nhạy chi phí nỗ lực trong cùng phân tầng**: Thử nghiệm các biến thể công thức tính nỗ lực trên cặp đường có cùng mức tác động và cùng khả năng thành công.
4. **Kiểm chứng bất biến đóng nhóm thụ động ($C_{\text{closure}} \equiv 0$)**: Đánh giá tính tương đương ngữ nghĩa khi biểu diễn nhóm lồng nhau hoặc gộp/tách hành động kỹ thuật.
5. **Kiểm chứng cơ chế lan truyền bất định qua Gate O và đánh giá trạng thái động**: Xác minh việc bảo toàn trạng thái `Unknown` theo nguyên lý khâu yếu nhất và kiểm thử bảng chân lý vét cạn 27 tổ hợp cổng.
6. **Kiểm chứng hiệu ứng suy giảm theo độ dài đường và thuật toán tìm kiếm đồ thị thực tế**:
   Chỉ ra giới hạn của hàm $\min$.
   So sánh thuật toán Dijkstra thực tế với thuật toán tìm kiếm vét cạn (exhaustive search oracle) trên đồ thị phi tuyến.
   Kiểm tra tính tương thích Bellman của Stratified Dijkstra.
   Phát hiện các giới hạn kỹ thuật của bộ lọc cạnh tĩnh và cơ chế đếm bước ngây thơ.

Ranh giới kỹ thuật:
Báo cáo này không tự ý ban hành trọng số sản phẩm cố định, không ngụy tạo xác suất tần suất ngoài đời thực, và không can thiệp vào mã nguồn đồ thị runtime thuộc trách nhiệm của TTS B.
Mọi phân tích chỉ phản ánh kết quả mô phỏng trên các mô hình ứng viên và chỉ ra các rào cản toán học cần tiếp tục nghiên cứu xử lý.

---

## 2. Câu hỏi kiểm chứng, Expected Oracle, ranh giới dữ liệu và hai chế độ đánh giá

### 2.1. Năm câu hỏi kiểm chứng cốt lõi (Core Research Questions)
Để làm sáng tỏ tính đúng đắn của mô hình, bộ thử nghiệm được thiết kế xung quanh 5 câu hỏi nghiên cứu:
- **RQ1**: Mô hình phân cấp từ điển $\langle I \downarrow, P \downarrow, C \uparrow \rangle$ có gặp phải hiện tượng mù từ điển (lexicographic blindness) khi xuất hiện mối đe dọa khả thi cao trên tài sản quan trọng thứ cấp so với mối đe dọa khó xảy ra trên tài sản tối quan trọng hay không?
- **RQ2**: Hàm chi phí nỗ lực $C$ có độ nhạy thực sự hay không khi hai đường tấn công có cùng mức tác động đích và cùng phân tầng khả năng thành công (equal strata)?
- **RQ3**: Bất biến đóng nhóm thụ động $C_{\text{closure}} \equiv 0$ có bảo vệ được tính tương đương ngữ nghĩa của hệ thống trước số hop cú pháp của nhóm lồng nhau và cách phân tách bước hành động hay không?
- **RQ4**: Cơ chế lan truyền bất định theo khâu yếu nhất và cơ chế đánh giá trạng thái động có bảo toàn tính trung thực của Gate O mà không bị giả định kịch bản hay penalty ngầm làm sai lệch hay không?
- **RQ5**: Thuật toán Stratified Dijkstra có bảo toàn nguyên lý tối ưu Bellman trên không gian trạng thái phân tầng hay không, và việc gộp $P$ cùng $C$ vào một hàm phi tuyến không ràng buộc có vi phạm điều kiện này khi chạy trên thuật toán Dijkstra thực tế hay không?

### 2.2. Expected Oracle và tiêu chí chấp thuận (Acceptance Criteria)
Mỗi câu hỏi kiểm chứng được gắn với một Expected Oracle toán học xác định trước:
- **Oracle A (Hand-worked Verification)**: Độ lệch tuyệt đối giữa tính tay lý thuyết và script kiểm chứng trên mọi thuộc tính ($T1, T2, C, P, T3$) tại các bước phải bằng 0.0.
- **Oracle 1 (Impact vs Likelihood Tradeoff)**: Chỉ ra phân kỳ giữa policy ưu tiên consequence rating Critical tuyệt đối và policy heuristic tích ordinal, không suy thứ bậc hậu quả từ technical tier hoặc business labels.
- **Oracle 2 (Effort Sensitivity)**: Quan sát thấy hiện tượng đảo ngược thứ hạng (rank reversal) giữa biến thể trọng số công cụ (tool-weighted) và trọng số phòng ngự (friction-weighted) khi so sánh hai đường có $I$ và $P$ hòa điểm.
- **Oracle 3 (Closure Invariance)**: Chi phí toàn đường không đổi giữa 1-hop và 3-hop lồng nhóm dưới công thức chuẩn hóa, và chi phí bảo toàn giữa hai hành động phân tách so với một hành động gộp.
- **Oracle 4 (Uncertainty Preservation & Dynamic Gates)**: Giá trị $P$ toàn đường tới S3 phải nhận giá trị `Unknown` khi Gate O chưa được giải quyết; bảng chân lý 27 tổ hợp trạng thái cổng phải phản ánh chính xác các quy tắc chuyển đổi trạng thái động.
- **Oracle 5 (Dijkstra Compatibility & Length Decay Limits)**:
  Chạy thuật toán Dijkstra thực tế đối chiếu với Exhaustive Search Oracle để chứng minh hàm mục tiêu phi tuyến gộp $C / \prod P$ làm Dijkstra trả về đường dưới tối ưu toàn cục.
  Xác minh Stratified Dijkstra tìm đường tối ưu chính xác trên đồ thị con cộng dồn $C \ge 0$.
  Chỉ ra sự thất bại của bộ lọc cạnh tĩnh trước sự suy giảm xác suất tích lũy và sự vi phạm đóng gói hành động của cơ chế đếm bước ngây thơ.

### 2.3. Ranh giới dữ liệu và hai chế độ đánh giá (Dual Evaluation Modes)
Kiểm chứng tuân thủ nghiêm ngặt hợp đồng phân tầng 4 nhóm dữ kiện tại [week3-scenario-contract.md](week3-scenario-contract.md):
1. **Dữ kiện cấu trúc quan sát được (Observed Structural Facts)**: Được kiểm chứng từ snapshot SEAMLESS qua SHA-256 hash và JSON pointer (máy trạm nguồn `Source A`, tài khoản trung gian `User-Candidate`, nhóm đặc quyền `Target-Group-DA`, và tài khoản đích `Target-User-KRBTGT`).
2. **Quy tắc kỹ thuật (Technical Rules)**: Cơ chế giao thức MS-DRSR, Windows Kerberos PAC, và bảo vệ tài khoản Active Directory.
3. **Giả định kịch bản runtime (Declared Runtime Assumptions)**: Foothold `LocalSystem`, xác thực hợp lệ tại Gate A, và liên kết token tại Gate M.
4. **Bất định chưa giải quyết (Unresolved Uncertainty)**: Tình trạng chưa có bằng chứng đã được kiểm chứng về phân quyền replication trên domain naming context của Gate O.

Hai chế độ đánh giá được vận hành song song:
- **Chế độ thuần bằng chứng (Evidence-only mode)**:
  Chỉ chấp nhận các dữ kiện cấu trúc và quy tắc kỹ thuật có bằng chứng trực tiếp.
  Chế độ này dừng lại ở Checkpoint S0 (tồn tại các cạnh cấu trúc tiềm năng).
  Cả Checkpoint S1 (thực thi reset mật khẩu), Checkpoint S2 (danh tính và đặc quyền dùng được), và Đích S3 đều mang trạng thái không được hỗ trợ (`unsupported`) vì thiếu bằng chứng thực thi runtime trên snapshot tĩnh.
- **Chế độ kịch bản (Scenario mode)**:
  Cho phép chấp nhận các giả định kịch bản đã khai báo tường minh có căn cứ.
  Checkpoint S2 được công nhận là đạt được **dưới các giả định đã khai báo**.
  Đích S3 vẫn giữ trạng thái không được hỗ trợ (`unsupported`) do Gate O chưa có bằng chứng đã được kiểm chứng về phân quyền replication và không được phép ghi đè bằng giả định.

---

## 3. Đối chiếu và xác minh ca tính tay trên dữ liệu SEAMLESS (Hand-worked Example Verification)

### 3.1. Bảng đối chiếu chi tiết từng bước và độ lệch tuyệt đối
Thử nghiệm đã thực hiện chạy script tự động hóa `scripts/research/worked_example_validation.py` để tính toán lại toàn bộ các bước của Đường 1 (SEAMLESS Reset) và Đường 2 (Synthetic HasSession) theo đúng định nghĩa trong ca tính tay đối chứng của [path-ranking-model.md](path-ranking-model.md).

Mô hình phân tách rạch ròi hai khái niệm chi phí nỗ lực:
- **Chi phí danh nghĩa ($C_{\text{nominal}}$)**: Tổng chi phí nỗ lực không điều kiện theo thang đo rubric kỹ thuật của chuỗi hành động mẫu ($S2 = 3$, $S3 = 6$).
- **Chi phí thực tế khả thi ($C_{\text{realized}}$ hoặc `total_cost`)**: Chỉ có giá trị nguyên khi toàn bộ các cổng điều kiện tiên quyết và sự kiện kích hoạt đều đạt trạng thái khả thi (`feasible`).
  Khi đường tấn công bị chặn (`blocked`) hoặc rơi vào bất định (`unknown`), chi phí thực tế mang giá trị `None`.

Dưới đây là bảng đối chiếu chi tiết giữa giá trị tính tay lý thuyết và kết quả do script thực thi:

| Đường đi | Bước | Tên hành động | Loại bước | $T1$ | $T2$ | $C_{\text{nominal}}$ | $C_{\text{realized}}$ | $P$ (Tính tay) | $P$ (Script) | Dấu vết $T3$ | Độ lệch |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| **Đường 1 (Reset)** | 1 | `genericall_reset_password` | Active | 1 | 3 | 2 | 2 | Medium | Medium | High (Event 4724) | **0.0** |
| | 2 | `activate_identity` | Active | 1 | 2 | 1 | 1 | Medium | Medium | Medium (Event 4624) | **0.0** |
| | 3 | `propagate_membership` | Passive | 1 | 1 | 0 | 0 | High | High | Low (None) | **0.0** |
| | **S2** | **Checkpoint Domain Admins** | - | - | - | **3** | **3** | **Medium** | **Medium** | - | **0.0** |
| | 4 | `dcsync_krbtgt` | Active | 2 | 3 | 3 | None | Unknown | Unknown | High (Event 4662) | **0.0** |
| | **S3** | **Tài sản đích KRBTGT** | - | - | - | **6** | **None** | **Unknown** | **Unknown** | - | **0.0** |
| **Đường 2 (Session)** | 1 | `token_impersonation` | Active | 2 | 2 | 2 | 2 | High | High | High (LSASS access) | **0.0** |
| | 2 | `activate_identity` | Active | 1 | 2 | 1 | 1 | High | High | Medium (Event 4624) | **0.0** |
| | 3 | `inherit_da_entitlement` | Passive | 1 | 1 | 0 | 0 | High | High | Low (None) | **0.0** |
| | **S2** | **Checkpoint Domain Admins** | - | - | - | **3** | **3** | **High** | **High** | - | **0.0** |
| | 4 | `dcsync_krbtgt` | Active | 2 | 3 | 3 | None | Unknown | Unknown | High (Event 4662) | **0.0** |
| | **S3** | **Tài sản đích KRBTGT** | - | - | - | **6** | **None** | **Unknown** | **Unknown** | - | **0.0** |

Kết quả đo kiểm:
Tổng độ lệch trên toàn bộ 8 bước kiểm thử của hai đường đạt chính xác **0.0 tuyệt đối**.
Toàn bộ các thuộc tính $T1, T2, C, P, T3$ đều khớp hoàn toàn giữa đặc tả lý thuyết và mã thực thi.

### 3.2. Kết quả xếp hạng tại Checkpoint S2 trong Scenario Mode
Tại checkpoint S2 (đạt được danh tính đặc quyền nhóm `Target-Group-DA`), cả hai đường đều thỏa mãn các điều kiện tiên quyết trong Scenario mode:
- Technical checkpoint: Đều đạt quyền Domain Admins thuộc mặt phẳng điều khiển Tier0; business impact Critical được stipulate riêng trong fixture, không suy ra từ checkpoint hoặc nhãn Tier0.
- Tổng chi phí nỗ lực danh nghĩa: $C_{\text{S2}}(\text{Đường 1}) = 2 + 1 + 0 = 3$; $C_{\text{S2}}(\text{Đường 2}) = 2 + 1 + 0 = 3$ (Hòa điểm nỗ lực).
- Khả năng thành công tổng hợp theo khâu yếu nhất:
  $$P_{\text{S2}}(\text{Đường 1}) = \min(\text{Medium}, \text{Medium}, \text{High}) = \mathbf{Medium}$$
  $$P_{\text{S2}}(\text{Đường 2}) = \min(\text{High}, \text{High}, \text{High}) = \mathbf{High}$$

Áp dụng khóa sắp xếp từ điển $(-I, -P, C, \text{active\_steps})$:
Do $P_{\text{S2}}(\text{Đường 2}) = \text{High} > P_{\text{S2}}(\text{Đường 1}) = \text{Medium}$, mô hình phân giải thứ hạng dứt khoát ngay tại Tầng 2:
$$\mathbf{Rank \, 1: Đường \, 2 \, (Synthetic \, HasSession)} \succ \mathbf{Rank \, 2: Đường \, 1 \, (SEAMLESS \, Reset)}$$
Kết quả mô phỏng minh họa: Đường 2 được xếp trước Đường 1 vì kỹ thuật trích xuất token có sẵn có tính khả thi cao hơn trong mô hình, không bị phụ thuộc vào rào cản chính sách độ phức tạp mật khẩu hay nguy cơ khóa tài khoản người dùng như kỹ thuật reset mật khẩu.

### 3.3. Trạng thái tại Mục tiêu S3 và ranh giới Gate O
Tại mục tiêu cuối cùng S3 (`Target-User-KRBTGT`), cả hai đường đều thực hiện thao tác Bước 4 (`dcsync_krbtgt`).
Theo phân tích quy tắc kỹ thuật MS-DRSR, thao tác DCSync đòi hỏi quyền replication cấu trúc trên domain naming context (`DS-Replication-Get-Changes` và `DS-Replication-Get-Changes-All`).
Trong snapshot SEAMLESS, chưa có bằng chứng đã được kiểm chứng về phân quyền replication trên domain naming context cho tài khoản kiểm thử; do đó cổng Gate O mang trạng thái `Unknown`.
Theo nguyên tắc khâu yếu nhất, nếu bất kỳ bước nào trên đường đi có trạng thái `Unknown`, toàn bộ khả năng thành công của đường đi tới đích sẽ là:
$$P_{\text{S3}}(\text{Đường 1}) = \min(\text{Medium}, \text{Medium}, \text{High}, \text{Unknown}) = \mathbf{Unknown}$$
$$P_{\text{S3}}(\text{Đường 2}) = \min(\text{High}, \text{High}, \text{High}, \text{Unknown}) = \mathbf{Unknown}$$
Cả hai đường đều bị chặn ở trạng thái `unsupported` / `unknown` tại đích S3 trong cả hai chế độ đánh giá, với chi phí thực tế $C_{\text{realized}} = \text{None}$.

### 3.4. Ranh giới thực tế trên snapshot SEAMLESS
Script kiểm chứng đã trực tiếp xác minh các file dữ liệu thô của snapshot SEAMLESS dựa trên bảng manifest `data/samples/manifests/seamless-raw-v1.json`, hoàn toàn loại bỏ các định danh thô và sử dụng định danh chuẩn tắc:
- Máy trạm nguồn `Source A`: Tồn tại bản ghi máy trạm tại `20210920185958_computers.json#/computers/46` với trạng thái quan sát được `enabled = true` (SID kết thúc bằng `-4131`, là máy trạm ứng viên có SID nhỏ nhất theo thứ tự từ điển trong kết quả của `raw_path_probe.py`).
  Cần phân biệt rõ ràng với máy trạm `Source B` tại `20210920185958_computers.json#/computers/67` (SID kết thúc bằng `-4157`, cũng sở hữu ACE `GenericAll` tới một tài khoản trung gian khác tại `users/917` với ACE index 11).
- Tài khoản trung gian `User-Candidate`: Tồn tại tài khoản người dùng tại `20210920185958_users.json#/users/2310` với trạng thái quan sát được `enabled = true` (SID kết thúc bằng `-3398`), sở hữu cạnh `GenericAll` từ `Source A` tại `20210920185958_users.json#/users/2310/Aces/3` và là thành viên trực tiếp của nhóm `Target-Group-DA` tại `20210920185958_groups.json#/groups/40/Members/0`.
- Checkpoint đặc quyền `Target-Group-DA`: Tồn tại bản ghi nhóm tại `20210920185958_groups.json#/groups/40` được chọn tái lập qua regex RID-512 với `admincount = true` và `highvalue = true`.
- Tài khoản đích `Target-User-KRBTGT`: Tồn tại bản ghi tài khoản đích tại `20210920185958_users.json#/users/3` được chọn tái lập qua regex RID-502 với `admincount = true` và `enabled = false`.
- Nguyên thủy phiên đăng nhập (Computer.Sessions[] primitive): Trong chuẩn cấu trúc SharpHound và BloodHound, dữ liệu phiên làm việc được lưu trữ tại thuộc tính mảng `Computer.Sessions[]` bên trong file `20210920185958_computers.json`, không phải là file `sessions.json` độc lập.
  Kiểm tra thực địa trên máy trạm `Source A` ghi nhận mảng rỗng `Sessions = []`.
  Mở rộng rà soát toàn bộ 100 bản ghi máy trạm trong snapshot xác nhận 100/100 máy trạm đều có `Sessions = []`.
- Cảnh báo hoàn bị dữ liệu (`empty != false`): Việc mảng sessions rỗng trong snapshot tĩnh phản ánh việc thu thập phiên không được thực hiện, bị hạn chế quyền hoặc trả về rỗng tại thời điểm snapshot.
  Sự vắng mặt của bản ghi phiên trong snapshot tĩnh không đồng nghĩa với việc phiên đăng nhập không bao giờ xuất hiện trong môi trường runtime AD.
- Xác thực toàn bộ manifest: Script kiểm chứng đã xác minh 100% cả 6 file khai báo trong `seamless-raw-v1.json` (computers, users, groups, domains, ous, gpos) về sự tồn tại của file, kích thước byte và mã băm SHA-256 khớp tuyệt đối.

Cơ chế bộ chọn ứng viên tái lập:
Hàm `verify_snapshot_data()` gom cụm toàn bộ các cạnh ứng viên thỏa mãn cấu trúc `(Computer -> GenericAll -> User in RID-512 Group)`.
Sau đó, bộ chọn sắp xếp các máy trạm theo thứ tự từ điển để xác định máy trạm đầu tiên làm `Source A` (`computers/46`) và liên kết trực tiếp tới `User-Candidate` (`users/2310`, ACE 3).
Đầu ra của script xuất minh bạch toàn bộ các locator băm kiểm tra (SHA-256 hash-checked JSON pointers), loại bỏ triệt để hiện tượng lệch giữa script và tài liệu.

Kết luận ranh giới:
Trong dữ liệu quan sát được của snapshot SEAMLESS, mảng `Sessions[]` rỗng trên toàn bộ 100 máy trạm.
Do đó, Đường 2 thuần túy là một **ví dụ đối chứng kịch bản giả định chưa được chứng minh (unproven synthetic scenario counterexample)** nhằm kiểm tra cơ chế phân giải của mô hình khi có sự khác biệt về kỹ thuật, không phải là đường tấn công có căn cứ chứng minh từ dữ liệu snapshot SEAMLESS.

---

## 4. Ca đối chứng 1: Đánh đổi giữa Tác động đích (Impact) và Khả năng thành công (Likelihood)

### 4.1. Thiết lập bài toán đối chứng giữa Đường A và Đường B
Để kiểm tra tính hợp lý của mô hình Phân cấp Từ điển khi đối mặt với sự đánh đổi giữa mức độ quan trọng của tài sản và khả năng xảy ra của cuộc tấn công, Ca đối chứng 1 thiết lập hai đường tấn công cạnh tranh:
- **Đường A (Critical business consequence)**: Application giả lập thuộc technical Tier1, nhãn CrownJewel; consequence rating Critical ($I = 4$) khai báo riêng, likelihood Low ($P = 1$), effort $C = 3$.
- **Đường B (High business consequence)**: Control-plane target giả lập thuộc technical Tier0; consequence rating High ($I = 3$) khai báo riêng, likelihood High ($P = 3$), effort $C = 3$.

Đây là fixture synthetic cho arithmetic; không có quy tắc Tier1 -> Critical hoặc Tier0 -> High, cũng không kết luận control-plane compromise ngoài đời có business impact thấp hơn.

### 4.2. Bảng phân tích đa mô hình và bản chất của phép nhân thứ bậc

Bảng so sánh chi tiết giữa Đường A và Đường B dưới 4 mô hình quyết định khác nhau:

| Tiêu chí / Thuộc tính | Đường A (Critical, Khả năng thấp) | Đường B (High, Khả năng cao) | So sánh và Kết quả lựa chọn |
| :--- | :--- | :--- | :--- |
| **Mức hậu quả nghiệp vụ ($I$)** | Critical ($I = 4$) | High ($I = 3$) | Đường A > Đường B |
| **Khả năng thành công ($P$)** | Low ($P = 1$) | High ($P = 3$) | Đường B > Đường A |
| **Chi phí nỗ lực ($C$)** | 3 | 3 | Hòa điểm ($C = 3$) |
| **Mô hình Phân cấp Từ điển** | **Hạng 1 (Được chọn)** | Hạng 2 | **Đường A thắng tuyệt đối** (ưu tiên hậu quả Critical) |
| **Heuristic tích ordinal ($I \times P$)** | Điểm số: $4 \times 1 = \mathbf{4}$ | Điểm số: $3 \times 3 = \mathbf{9}$ | **Đường B thắng áp đảo** ($9 > 4$) |
| **Ma trận Rủi ro Định tính** | Mức 2 - Moderate Risk (Trung bình) | Mức 4 - Critical Risk (Nghiêm trọng) | **Đường B thuộc nhóm Khẩn cấp / Critical** |
| **Hàm Tiện ích Đa thuộc tính ($U$)** | Điểm tiện ích: $0.6667$ | Điểm tiện ích: $0.8750$ | **Đường B thắng** ($0.8750 > 0.6667$) |

Lưu ý quan trọng về mặt toán học:
Phép nhân điểm số thứ bậc $I \times P$ ($4 \times 1 = 4$ so với $3 \times 3 = 9$) thuần túy là một **chỉ báo heuristic minh họa (illustrative heuristic)** được áp dụng trong các ma trận rủi ro định tính phổ biến.
Phép toán này hoàn toàn **không phải là tổn thất kỳ vọng toán học chuẩn tắc (not mathematically valid expected loss $E[\text{Loss}]$)**.
Thang đo thứ tự định tính chỉ thể hiện thứ bậc tương đối, không mang thuộc tính tỷ lệ (ratio scale) để có thể thực hiện phép nhân đại số có ý nghĩa vật lý.

### 4.3. Đối chiếu hai trường phái phòng thủ (Defense Paradigm Comparison)
Kết quả thử nghiệm cho thấy sự phân kỳ rõ rệt giữa hai triết lý ra quyết định, và không có mô hình nào chứng minh mô hình kia là sai:
1. **Mô hình Phân cấp Từ điển (Ưu tiên hậu quả Critical tuyệt đối)**:
   Policy này ưu tiên consequence rating Critical đã được khai báo, không phải ontology label CrownJewel hoặc technical tier Tier0.
   Likelihood không đổi thứ tự khi hai consequence ratings khác nhau; đây là tradeoff của policy, không chứng minh policy khác sai.
2. **Mô hình Ma trận Rủi ro (Trường phái Phân loại Tác chiến / Operational Triage under Finite Bandwidth)**:
   Các ô matrix giả lập ưu tiên Path B vì likelihood cao dù consequence rating High thấp hơn Critical.
   Kết quả này chỉ là policy minh họa, chưa chứng minh imminence hoặc một ưu tiên SOC bắt buộc ngoài đời.

Đề xuất kiến trúc:
Hệ thống phòng thủ nên giữ mô hình Phân cấp Từ điển làm thứ tự sắp xếp cơ sở (baseline order).
Đồng thời, hệ thống bắt buộc phải xuất kèm hai góc nhìn bổ trợ: Biên Pareto (Pareto Frontier) và Cảnh báo Ma trận Rủi ro (Risk Matrix Overlay) để người ra quyết định không bị bỏ sót các nguy cơ tác chiến khẩn cấp.

---

## 5. Ca đối chứng 2: Độ nhạy hàm Chi phí nỗ lực trong cùng phân tầng (Equal Strata: Same I, Same P)

### 5.1. Thiết lập thử nghiệm trên cặp đường cùng impact Critical, cùng Likelihood Medium
Để kiểm tra độ nhạy thực sự của hàm chi phí nỗ lực $C$, Ca đối chứng 2 loại bỏ hoàn toàn ảnh hưởng của $I$ và $P$ bằng cách chọn một cặp đường tấn công có cùng $I$ và cùng $P$:
- Cả hai đường có cùng consequence rating synthetic Critical ($I = 4$), không suy rating từ ontology labels.
- Cả hai đường đều có khả năng thành công tổng hợp là Medium ($P = 2$).
- Bước đóng nhóm thụ động `propagate_membership` có $T1=1, T2=1$.
- Sự khác biệt duy nhất nằm ở cấu trúc kỹ thuật của bước hành động chủ động:
  - **Đường 3A (Tool-heavy)**: Đòi hỏi công cụ và kỹ năng rất cao nhưng rào cản phòng ngự tương tác thấp ($T1 = 3, T2 = 1$).
  - **Đường 3B (Friction-heavy)**: Sử dụng công cụ có sẵn đơn giản nhưng gặp rào cản phòng ngự tương tác rất lớn hoặc gây phá hủy ($T1 = 1, T2 = 3$).

### 5.2. Đánh giá 4 biến thể công thức chi phí nỗ lực

Bốn biến thể công thức toán học được đưa vào thử nghiệm trên hai đường:
1. **Biến thể Cơ sở (Base Additive)**: $C_1 = T1 + T2 - 2$ (Tổng tuyến tính trừ ngưỡng chuẩn hóa).
2. **Biến thể Cực đại (Max Bottleneck)**: $C_2 = \max(T1, T2) - 1$ (Khâu phức tạp nhất trừ ngưỡng).
3. **Biến thể Ưu tiên Công cụ (Tool-weighted)**: $C_3 = 2 \cdot T1 + T2 - 3$ (Nhân đôi trọng số công cụ kỹ thuật).
4. **Biến thể Ưu tiên Phòng ngự (Friction-weighted)**: $C_4 = T1 + 2 \cdot T2 - 3$ (Nhân đôi trọng số rào cản phòng ngự).

Kết quả tính toán chi tiết từ script:

| Biến thể công thức | Diễn giải toán học | Chi phí đóng nhóm ($C_{\text{closure}}$) | Chi phí chủ động 3A | Chi phí chủ động 3B | Tổng $C$(3A) | Tổng $C$(3B) | Đường được xếp ưu tiên (Hạng 1) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$C_1$ (Base)** | $T1 + T2 - 2$ | **0** | 2 | 2 | **2** | **2** | **Hòa điểm (Tie, cùng nỗ lực)** |
| **$C_2$ (Max)** | $\max(T1, T2) - 1$ | **0** | 2 | 2 | **2** | **2** | **Hòa điểm (Tie, cùng nỗ lực)** |
| **$C_3$ (Tool-weighted)** | $2 \cdot T1 + T2 - 3$ | **0** | 4 | 2 | **4** | **2** | **Đường 3B thắng** ($C=2 < 4$) |
| **$C_4$ (Friction-weighted)**| $T1 + 2 \cdot T2 - 3$ | **0** | 2 | 4 | **2** | **4** | **Đường 3A thắng** ($C=2 < 4$) |

### 5.3. Phân tích hiện tượng đảo ngược thứ hạng (Rank Reversal)
Thử nghiệm mang lại hai phát hiện quan trọng:
1. **Bảo toàn bất biến đóng nhóm**:
   Trong cả 4 biến thể công thức, chi phí của bước đóng nhóm thụ động `propagate_membership` ($T1=1, T2=1$) đều được chuẩn hóa về đúng **bằng 0 tuyệt đối** ($C_{\text{closure}} \equiv 0$).
2. **Chứng minh hiện tượng đảo ngược thứ hạng**:
   Dưới công thức $C_1$ và $C_2$, hai đường hoàn toàn hòa điểm ($C = 2$).
   Khi chuyển sang góc nhìn đánh giá kẻ tấn công ngại viết công cụ tùy biến ($C_3$ Tool-weighted), Đường 3B tốn ít công sức hơn hẳn ($C = 2 < 4$), do đó Đường 3B được xếp Hạng 1.
   Ngược lại, khi chuyển sang góc nhìn đánh giá kẻ tấn công ngại gây ồn ào và tránh làm gián đoạn hệ thống ($C_4$ Friction-weighted), Đường 3A tốn ít nỗ lực tương tác hơn ($C = 2 < 4$), do đó Đường 3A vươn lên xếp Hạng 1.
   Hiện tượng đảo ngược thứ hạng dứt khoát giữa $C_3$ và $C_4$ chứng minh rằng: **Hàm chi phí nỗ lực có độ nhạy thực sự và đóng vai trò phân giải quyết định khi các tiêu chí cấp cao ($I$ và $P$) hòa điểm**.

---

## 6. Ca đối chứng 3: Bất biến Đóng nhóm Thụ động ($C_{\text{closure}} \equiv 0$) và Tính tương đương ngữ nghĩa

### 6.1. Thử nghiệm 1-hop MemberOf so với 3-hop lồng nhau (Transitive Group Nesting)
Trong Active Directory, quan hệ thành viên nhóm thường phân cấp qua nhiều tầng lồng nhau.
Một mô hình chi phí chuẩn mực phải phản ánh đúng bản chất kỹ thuật: Dịch vụ Kerberos KDC tự động duyệt cây phân cấp và nhét toàn bộ danh sách SID vào vé PAC khi cấp quyền.
Kẻ tấn công không phải bỏ ra bất kỳ nỗ lực nào để "vượt qua" từng hop lồng nhau này.

Thử nghiệm so sánh hai cách tính chi phí:
- **Công thức chuẩn hóa (Normalized Baseline Formula)**:
  Áp dụng $C = T1 + T2 - 2$ cho hành động chủ động, và áp dụng bất biến $C_{\text{closure}} \equiv 0$ cho bước đóng nhóm.
  Chuỗi 1-hop: 2 bước chủ động ($C = 2 + 1 = 3$) + 1 hop đóng nhóm ($C = 0$) $\implies$ **Tổng $C = 3$**.
  Chuỗi 3-hop lồng nhau: 2 bước chủ động ($C = 2 + 1 = 3$) + 3 hop đóng nhóm ($C = 0 + 0 + 0 = 0$) $\implies$ **Tổng $C = 3$**.
  $\implies$ **Bất biến được bảo toàn: Chi phí không đổi giữa 1-hop và 3-hop.**
- **Công thức chưa chuẩn hóa (Unnormalized Raw Max Formula)**:
  Nếu dùng công thức thô không trừ ngưỡng (ví dụ: $C = \max(T1, T2)$ như các mô hình cũ), thì bước đóng nhóm thụ động ($T1=1, T2=1$) sẽ nhận chi phí là $C = \max(1, 1) = 1$.
  Khi đó, chuỗi 1-hop có chi phí: $2 + 1 = 3$.
  Chuỗi 3-hop lồng nhau có chi phí: $2 + 3 \times 1 = \mathbf{5}$.
  Độ chênh lệch lạm phát chi phí giả tạo: $\Delta = 5 - 3 = \mathbf{+2}$.

Hệ quả phân tích:
Việc không chuẩn hóa bước đóng nhóm về 0 sẽ phạt bất công các chuỗi tấn công đi qua cấu trúc nhóm lồng nhau.
Kẻ tấn công thực tế không tốn thêm nỗ lực nào, nhưng thuật toán tìm kiếm lại tính thêm 2 điểm phạt thuần túy do cách biểu diễn cú pháp đồ thị của người quản trị Active Directory.
Điều này khẳng định yêu cầu bắt buộc phải duy trì $C_{\text{closure}} \equiv 0$.

### 6.2. Tính tương đương khi gộp và tách hành động (Action Packaging Invariance)
Trong phân tích chuỗi tấn công, các nhà phân tích hoặc các công cụ trích xuất có thể biểu diễn chuỗi hành động theo hai cách:
- **Dạng phân tách (Split Packaging)**: Gồm 2 hành động liên tiếp: `genericall_reset_password` ($T1=1, T2=3 \implies C = 2$) và `activate_identity` ($T1=1, T2=2 \implies C = 1$).
  Tổng chi phí: $C_{\text{split}} = 2 + 1 = \mathbf{3}$.
  Số bước hành động: 2.
- **Dạng gộp (Merged Packaging)**: Gộp thành một siêu hành động duy nhất `reset_and_activate` ($T1=2, T2=3 \implies C = 2 + 3 - 2 = \mathbf{3}$).
  Tổng chi phí: $C_{\text{merged}} = \mathbf{3}$.
  Số bước hành động: 1.

Kết luận:
Tổng chi phí nỗ lực gia tăng được bảo toàn ($C_{\text{split}} = C_{\text{merged}} = 3$) bất kể hành động được mô hình hóa ở dạng tách rời hay gộp chung dưới công thức nỗ lực cộng dồn.

---

## 7. Ca đối chứng 4: Lan truyền bất định và Gating cổng Gate O

### 7.1. Bảng chân lý khâu yếu nhất (Weakest-Link Bottleneck Truth Table)
Cơ chế tổng hợp khả năng thành công của chuỗi hành động tuân thủ bảng chân lý khâu yếu nhất.
Script kiểm chứng đã thực thi kiểm thử vét cạn trên toàn bộ các cặp kết hợp khả năng thành công:

| Đầu vào bước 1 | Đầu vào bước 2 | Kết quả tổng hợp mong đợi | Kết quả Script | Trạng thái kiểm chứng |
| :---: | :---: | :---: | :---: | :---: |
| High | High | High | High | **PASS** |
| High | Medium | Medium | Medium | **PASS** |
| High | Low | Low | Low | **PASS** |
| Medium | Low | Low | Low | **PASS** |
| High | Unknown | Unknown | Unknown | **PASS** |
| Medium | Unknown | Unknown | Unknown | **PASS** |
| Low | Unknown | Unknown | Unknown | **PASS** |
| Unknown | Unknown | Unknown | Unknown | **PASS** |

### 7.2. Đánh giá trạng thái động, Tiền điều kiện Reset và Logic 3 giá trị Kleene
Thí nghiệm 4 đã mở rộng kiểm chứng cơ chế chuyển đổi trạng thái động trên hai bình diện: tiền điều kiện kỹ thuật của bước reset mật khẩu và máy trạng thái 27 tổ hợp cổng.

#### Tiền điều kiện thực thi thao tác Reset mật khẩu (Bước 1) và Tính bất biến thứ tự kiểm tra
Theo quy chuẩn kịch bản tại contract nghiên cứu, thao tác reset mật khẩu (`genericall_reset_password`) không chỉ đòi hỏi quyền cấu trúc và foothold, mà đòi hỏi đánh giá toàn diện 6 điều kiện tiên quyết:
1. `structural_genericall`: Tồn tại cạnh GenericAll cấu trúc quan sát được trong snapshot.
2. `source_computer_enabled`: Máy trạm nguồn mang cờ hoạt động `enabled = true` quan sát được trong snapshot.
3. `target_user_enabled`: Tài khoản người dùng đích mang cờ hoạt động `enabled = true` quan sát được trong snapshot.
4. `foothold`: Giả định kịch bản về quyền kiểm soát hợp lệ máy trạm nguồn (ví dụ LocalSystem context).
5. `password_policy_satisfied`: Giả định kịch bản về chính sách mật khẩu miền không từ chối giá trị mật khẩu mới.
6. `directory_write_available`: Giả định kịch bản về kênh kết nối ghi thư mục hoạt động bình thường.

Trong chế độ kịch bản chuẩn (baseline Scenario mode), toàn bộ 6 điều kiện trên được thiết lập là thỏa mãn (`True`), cho phép Bước 1 đạt trạng thái Reached với chi phí nỗ lực danh nghĩa bằng 2.
Nếu bất kỳ điều kiện nào trong số này bị thiếu hoặc nhận giá trị `False` (ví dụ `structural_genericall = False`, tài khoản đích bị vô hiệu hóa hoặc chính sách mật khẩu không thỏa mãn), Bước 1 thất bại hoàn toàn (`Unsupported` hoặc `blocked`), ngăn chặn đường tấn công tiến tới Checkpoint S2.

Mô hình thiết lập nguyên tắc phân tách ranh giới và xác lập bộ tiền điều kiện có thẩm quyền cho từng checkpoint:
- **Bước 1 (Reset - Checkpoint S1)**:
  Chỉ phụ thuộc duy nhất vào 6 tiền điều kiện reset nêu trên.
  Bước 1 hoàn toàn độc lập với các thuộc tính downstream như quan hệ thành viên nhóm DA (`structural_memberof`) hay sự tồn tại của tài sản đích KRBTGT (`target_krbtgt_exists`).
- **Checkpoint S2 (Domain Admins)**:
  Chỉ được đánh giá khi Bước 1 đã đạt được (`s1_reached = True`), kết hợp đồng thời với quan hệ thành viên cấu trúc (`structural_memberof`), kích hoạt danh tính (`gate_a_accepted`) và ủy quyền nhóm (`gate_m_usable`).
- **Checkpoint S3 (KRBTGT DCSync)**:
  Chỉ được đánh giá khi Checkpoint S2 đã đạt được (`s2_reached = True`), kết hợp đồng thời với sự tồn tại của tài sản đích (`target_krbtgt_exists`) và phân quyền replication (`gate_o_granted`).

Đối với các ngữ cảnh cung cấp một phần dữ kiện (partial context, ví dụ chỉ truyền `{"source_computer_enabled": True}`):
Các tiền điều kiện bắt buộc còn lại trong bộ 6 điều kiện reset chưa được khai báo sẽ nhận trạng thái `Unknown` (hoặc `Unsupported`) thay vì tự động ngầm định thỏa mãn.
Theo logic Kleene, sự kết hợp giữa `True` và `Unknown` dẫn tới kết quả toàn bộ Bước 1 mang trạng thái `unknown` (chưa khả thi), ngăn ngừa việc mở khóa sớm khi chưa đủ dữ kiện.
Trường hợp muốn áp dụng các giả định kịch bản cho các điều kiện còn thiếu, ngữ cảnh cần khai báo tường minh cờ `baseline_assumptions = True`.

Đặc biệt, cơ chế phân giải cờ giả định (`baseline_assumptions` và `assume_reset_prerequisites`) được xử lý đóng an toàn (fail-closed).
Cờ giả định chỉ được kích hoạt khi giá trị được phân giải tường minh thành `True`.
Các chuỗi falsy mang tính truthy trong Python (ví dụ `"false"`, `"0"`, `"no"`), trạng thái `"unknown"`, `"missing"`, hoặc các đối tượng không hợp lệ tuyệt đối không thể vô tình kích hoạt giả định kịch bản.

Nguyên tắc thẩm quyền bắt buộc của tiền điều kiện và phủ quyết dữ kiện phủ định (Authoritative Prerequisites & Negative Evidence Veto):
1. **Tiền điều kiện reset có thẩm quyền bắt buộc khi có ngữ cảnh**:
   Mỗi khi `gate_context` được cung cấp, bộ 6 tiền điều kiện reset luôn được đánh giá có thẩm quyền.
   Phím tắt `step_1 = True` không thể bỏ qua dữ kiện phủ định hoặc dữ kiện bất định còn thiếu.
   Nếu phím tắt được giữ lại, nó chỉ được chấp nhận để lấp đầy các điều kiện chưa khai báo dưới chế độ tường minh `baseline_assumptions = True`.
2. **Loại bỏ hoàn toàn bypass baseline ngầm định (implicit baseline bypass)**:
   Khi `gate_context = None`, hệ thống sử dụng trạng thái baseline danh nghĩa đã khai báo trong worked example (`s.gate_status`).
   Khi caller cung cấp `gate_context = {}` hoặc từ điển chứa các trường không được nhận diện (ví dụ `{"unknown_field": "not_measured"}`), hệ thống thực hiện đánh giá động với các tiền điều kiện còn thiếu mà không tự ý fallback về baseline danh nghĩa; kết quả S1/S2 nhận trạng thái `unknown` và chi phí trả về `None`.
   Chỉ khi khai báo tường minh `baseline_assumptions = True`, hệ thống mới áp dụng giả định baseline cho các tiền điều kiện còn thiếu (vẫn không mở Gate O nếu thiếu bằng chứng sao chép xác thực).
   Đối với hàm xếp hạng đa đường `rank_attack_paths()`, hệ thống hỗ trợ ánh xạ ngữ cảnh riêng biệt cho từng đường tấn công (per-path context mapping) qua tên đường (chuỗi ký tự, không phân biệt hoa thường, ví dụ `{p1.name: ctx1, p2.name: None}`); các đường không xuất hiện trong ánh xạ sẽ mặc định dùng baseline danh nghĩa (`None`).
3. **Phủ quyết direct override bởi dữ kiện phủ định**:
   Khi caller truyền direct override như `{"step_1": True}`, nếu ngữ cảnh đồng thời xuất hiện bất kỳ tiền điều kiện `False` nào (ví dụ `structural_genericall: False` hoặc `target_user_enabled: False`), giá trị `False` lập tức phủ quyết và đưa bước tấn công về `blocked`.
   Ngay cả khi khai báo `baseline_assumptions = True`, dữ kiện `False` vẫn phủ quyết tuyệt đối và chặn bước tấn công.
4. **Tổng hợp bí danh toàn diện**:
   Đối với các tiền điều kiện có nhiều bí danh (ví dụ `target_user_enabled` và `target_enabled`), thuật toán kiểm tra toàn bộ các bí danh xuất hiện trong ngữ cảnh thay vì dừng sớm ở bí danh đầu tiên.
   Nếu tồn tại bất kỳ bí danh nào nhận giá trị `False`, tiền điều kiện đó lập tức nhận giá trị `False`.
5. **Đồng bộ tiền điều kiện cấu trúc S2 và S3**:
   Phương thức `AttackPath._evaluate_gates()` đồng bộ 100% với `evaluate_dynamic_modes()`, kiểm tra đầy đủ quan hệ thành viên `structural_memberof` tại Checkpoint S2 và tài sản đích `target_krbtgt_exists` tại Checkpoint S3.
   Khi các thuộc tính này nhận giá trị `False`, checkpoint tương ứng bị chặn (`blocked`) và chi phí thực tế trả về `None`.
   Khi chúng mang trạng thái `Unknown` hoặc bị thiếu trong ngữ cảnh dữ kiện đầy đủ, checkpoint nhận trạng thái `unknown`.
   Đồng thời, Checkpoint S1 reset luôn độc lập tuyệt đối với các điều kiện cấu trúc downstream của S2 và S3.

Đặc biệt, thuật toán đánh giá thu thập toàn bộ các giá trị tiền điều kiện reset được cung cấp và tổng hợp theo quy tắc bất biến thứ tự (order-invariance):
Do giá trị `False` hấp thụ tuyệt đối `Unknown`, bất kể `Unknown` xuất hiện trước hay sau `False` trong từ điển ngữ cảnh (ví dụ `source_computer_enabled = Unknown` đứng trước `password_policy_satisfied = False` hoặc `foothold = False`), kết quả Bước 1 và toàn bộ đường tấn công luôn được xác định dứt khoát là `blocked`.

#### Logic 3 giá trị Kleene và Bảng chân lý 27 tổ hợp cổng
Máy trạng thái đánh giá 27 tổ hợp trạng thái ($3 \times 3 \times 3 = 27$) của ba cổng Gate A, Gate M và Gate O trong miền $\{\text{True}, \text{False}, \text{Unknown}\}$ tuân thủ nghiêm ngặt **Logic 3 giá trị Kleene (Kleene 3-valued logic)**:
Trong logic Kleene, giá trị `False` có tính chất hấp thụ tuyệt đối so với `Unknown` (`False` strictly absorbs `Unknown`).

1. **Đánh giá trạng thái Checkpoint S2 (phụ thuộc Gate A và Gate M)**:
   - Nếu bất kỳ cổng tiên quyết nào là `False` (ví dụ Gate A = False, hoặc Gate A = Unknown nhưng Gate M = False): Checkpoint S2 bị chặn hoàn toàn (`blocked`), chi phí thực tế $C_{\text{realized}} = \text{None}$.
   - Nếu không có cổng nào là `False` nhưng tồn tại cổng là `Unknown` (ví dụ Gate A = Unknown và Gate M = True): Checkpoint S2 rơi vào bất định (`unknown`), chi phí thực tế $C_{\text{realized}} = \text{None}$.
   - Nếu cả Gate A = True và Gate M = True: Checkpoint S2 đạt được thành công (`reached`) với chi phí thực tế $C_{\text{realized}} = 3$.

2. **Đánh giá trạng thái Mục tiêu S3 (phụ thuộc S2 và Gate O)**:
   - Nếu Checkpoint S2 bị chặn (`blocked`): Mục tiêu S3 bị chặn hoàn toàn (`blocked`), bất kể Gate O mang giá trị gì.
   - Nếu Checkpoint S2 ở trạng thái bất định (`unknown`):
     - Nếu Gate O = False: Giá trị `False` của Gate O hấp thụ trạng thái bất định, dẫn tới Mục tiêu S3 bị chặn (`blocked`).
     - Nếu Gate O = True hoặc Unknown: Mục tiêu S3 tiếp tục ở trạng thái bất định (`unknown`).
   - Nếu Checkpoint S2 đã đạt được (`reached`):
     - Nếu Gate O = True: DCSync thành công; S3 đạt được (`reached`) với chi phí thực tế $C_{\text{realized}} = 6$.
     - Nếu Gate O = False: DCSync bị từ chối; S3 bị chặn (`blocked`), chi phí thực tế $C_{\text{realized}} = \text{None}$.
     - Nếu Gate O = Unknown: S3 ở trạng thái bất định (`unknown`), chi phí thực tế $C_{\text{realized}} = \text{None}$.

Đặc biệt lưu ý: Nhận định "Gate O unknown khiến S3 unknown trên toàn bộ 27 tổ hợp" là không chính xác khi xét dưới logic Kleene; Gate O = Unknown chỉ dẫn tới S3 = Unknown khi toàn bộ các tiền điều kiện dẫn tới S2 không có điều kiện nào bị `False`.
Toàn bộ 27/27 tổ hợp trạng thái đều được kiểm thử tự động và đạt sự đồng bộ 100% giữa hàm `evaluate_gate_truth_table()` và phương thức `AttackPath._evaluate_gates()`.

### 7.3. Liên kết Cổng điều kiện vào Đánh giá khả thi, Phân định Chi phí và Xếp hạng Toàn đường
Nhằm giải quyết triệt để vấn đề gating chưa nối vào phép đánh giá đường tấn công và thống nhất ngữ nghĩa chi phí, mô hình lớp `AttackPath` đã tích hợp các cơ chế chuẩn hóa:
- **Phân định rạch ròi ngữ nghĩa chi phí**:
  - `nominal_cost(checkpoint, formula)`: Chi phí danh nghĩa không điều kiện, luôn trả về tổng chi phí rubric của chuỗi bước ($S2 = 3$, $S3 = 6$), phục vụ việc tra cứu độ phức tạp kỹ thuật thuần túy.
  - `realized_cost(checkpoint, formula, gate_context)` hoặc `total_cost()`: Chi phí thực tế khả thi, chỉ trả về số nguyên khi đường tấn công đạt trạng thái khả thi (`feasible`).
    Khi đường tấn công bị chặn (`blocked`) hoặc bất định (`unknown`), phương thức trả về `None`, loại bỏ hoàn toàn nghịch lý xuất hiện chi phí nguyên cho một đường tấn công chưa được mở khóa.
- **Đánh giá khả thi theo tiền điều kiện (`is_feasible`)**:
  Một đường tấn công chỉ được công nhận là khả thi (`is_feasible = True`) khi và chỉ khi toàn bộ các tiền điều kiện cấu trúc, tiền điều kiện reset và sự kiện kích hoạt cổng đều đạt trạng thái thỏa mãn (`True`).
  Nếu bất kỳ cổng hoặc tiền điều kiện nào mang giá trị `False`, đường tấn công lập tức chuyển trạng thái `path_status = 'blocked'`, khả năng thành công `path_likelihood = 'Blocked'`, và `is_feasible = False`.
  Nếu mang giá trị `Unknown`, đường chuyển trạng thái `path_status = 'unknown'`, khả năng thành công `path_likelihood = 'Unknown'`, và `is_feasible = False`.
- **Khóa sắp xếp từ điển phân vùng khả thi (`lexicographic_key`)**:
  Khóa sắp xếp từ điển được mở rộng với cờ phân vùng khả thi đứng đầu:
  $$\text{Sort Key} = (\mathbf{0 \text{ if feasible else } 1}, -I, -P, C, \text{active\_steps})$$
  Trong đó thang đo thứ tự khả năng thành công gán $\text{ORDINAL}(\text{'Blocked'}) = -1$ và chi phí đường không khả thi là $\infty$.
  Khi người dùng hoặc hệ thống thay đổi Gate A = False hoặc một tiền điều kiện reset bị vi phạm, đường tấn công lập tức bị đánh dấu `Blocked` và tự động bị đẩy xuống sau toàn bộ các đường khả thi khác.
- **Hàm phân loại thứ hạng (`rank_attack_paths`)**:
  Hàm trả về cấu trúc `PathRankingResult` phân tách rõ ràng danh sách các đường khả thi đã sắp xếp (`feasible`) và danh sách các đường bị chặn / không khả thi (`blocked` / `infeasible`), bảo đảm tính minh bạch tuyệt đối khi bàn giao sang Issue #143.

### 7.4. Lan truyền bất định tại Gate O, Bằng chứng phủ định và Xung đột dữ kiện
Tại bước cuối cùng tiếp cận tài sản KRBTGT thông qua kỹ thuật DCSync, điều kiện tiên quyết về mặt kỹ thuật là tài khoản phải có các quyền replication mở rộng trên domain naming context (Gate O).

Mô hình thiết lập nguyên tắc phân tách ranh giới và kiểm soát giả định nghiêm ngặt:
1. **Bản chất của Gate O**:
   Cổng Gate O đại diện cho quyền replication cấu trúc trên domain naming context (`DS-Replication-Get-Changes` và `DS-Replication-Get-Changes-All` theo phân tích MS-DRSR).
   Bằng chứng ủy quyền replication cấu trúc bắt buộc phải giữ trạng thái `Unknown` cho tới khi có dữ liệu kiểm chứng cụ thể trong môi trường đích.
2. **Quy tắc tổng hợp bằng chứng phủ định và xung đột dữ kiện**:
   Mô hình áp dụng nguyên tắc an ninh bảo thủ nhất quán cho cả hai khóa bằng chứng replication (`structural_replication_rights` và `evidence_replication_granted`):
   - **Phủ định dứt khoát**: Khi xuất hiện bất kỳ bằng chứng phủ định nào (`structural_replication_rights = False` hoặc `evidence_replication_granted = False`), Gate O lập tức nhận trạng thái `False`, đường tấn công bị chặn (`blocked`).
   - **Xung đột dữ kiện (Negative Veto)**: Khi dữ kiện mâu thuẫn giữa khẳng định và phủ định (ví dụ `structural_replication_rights = True` nhưng `evidence_replication_granted = False`, hoặc ngược lại), bằng chứng phủ định có quyền phủ quyết tuyệt đối, đường tấn công lập tức bị chặn (`blocked`).
   - **Khẳng định khả thi**: Cổng Gate O chỉ chuyển sang trạng thái thỏa mãn (`feasible`) khi có bằng chứng ủy quyền khẳng định (`True`) và hoàn toàn không có bất kỳ bằng chứng phủ định nào.
3. **Tách biệt giả định mạng và bằng chứng phân quyền**:
   Các giả định mạng runtime (kết nối RPC endpoint mapper TCP 135 và cổng động DRS RPC) thuộc tầng giả định vận hành mạng, hoàn toàn tách biệt và không được phép dùng để suy diễn thay thế cho bằng chứng ủy quyền replication cấu trúc.
4. **Nghiêm cấm ghi đè bằng giả định kịch bản tổng quát**:
   Hàm đánh giá `AttackPath._evaluate_gates()` chủ động từ chối các giả định kịch bản chung chung như `gate_context={"Gate O": True}`.
   Cổng Gate O chỉ có thể chuyển sang trạng thái thỏa mãn khi nhận được các khóa bằng chứng ủy quyền replication rõ ràng và đã được kiểm chứng (`structural_replication_rights` hoặc `evidence_replication_granted`).
   Khi thiếu các bằng chứng này, Gate O giữ nguyên trạng thái `Unknown`, bảo đảm DCSync không bị mở khóa tùy tiện trong các kịch bản mô phỏng.
5. **Nguyên tắc đóng an toàn (Fail-Closed) đối với giá trị không hợp lệ**:
   Hàm phân giải logic 3 trạng thái `parse_tristate()` tuân thủ nghiêm ngặt nguyên tắc đóng an toàn.
   Mọi giá trị ngoài miền khẳng định hoặc phủ định chuẩn tắc (ví dụ chuỗi lạ như `"not_measured"`, `"missing"`, hoặc các đối tượng dictionary/list/None) đều được phân giải về `Unknown`.
   Cơ chế này loại bỏ hoàn toàn nguy cơ fail-open (nơi giá trị không rỗng bị ép kiểu thành `True`), ngăn chặn tuyệt đối việc dữ liệu rác hoặc chưa đo lường vô tình mở khóa phân quyền replication.
6. **Tuân thủ triệt để Nguyên tắc Ba Không**:
   - **Không gán xác suất 0.5 bịa đặt**: Không tự ý gán giá trị 0.5 cho sự thiếu hụt bằng chứng.
   - **Không gán penalty điểm số ngầm**: Không cộng thêm chi phí phạt tùy tiện để bóp méo đường đi.
   - **Không ghi đè bằng giả định kịch bản**: Không cho phép giả định kịch bản runtime tự ý xóa bỏ sự bất định của phân quyền replication.

### 7.5. Đối chiếu hai chế độ đánh giá Evidence-only và Scenario Mode

Bảng tổng kết trạng thái các checkpoint giữa hai chế độ đánh giá:

| Checkpoint / Cổng | Chế độ thuần bằng chứng (Evidence-only) | Chế độ kịch bản (Scenario Mode) | Ý nghĩa kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Foothold** | Chưa chứng minh (Unproven) | Được khai báo (Declared LocalSystem) | Điểm xuất phát cục bộ trên máy trạm |
| **Gate A** | Chưa chứng minh (Unproven) | Được khai báo (Declared Valid Auth) | Cầu nối xác thực vào domain context |
| **Gate M** | Thỏa mãn (Proven structural edge) | Thỏa mãn (Proven + Token Assumption)| Đóng nhóm thành viên bảo mật |
| **Gate O** | Chưa có bằng chứng đã được kiểm chứng về phân quyền replication | Chưa có bằng chứng đã được kiểm chứng về phân quyền replication | Quyền DCSync trích xuất hash krbtgt |
| **S0 (Cấu trúc)** | **Đạt (Satisfied)** | **Đạt (Satisfied)** | Cạnh ACL và liên kết nhóm có thật trong snapshot |
| **S1 (Reset)** | Không hỗ trợ (Unsupported) | **Đạt (Reached)** | Reset thành công dưới giả định foothold |
| **S2 (DA Group)** | Không hỗ trợ (Unsupported) | **Đạt (Reached)** | Đạt checkpoint đặc quyền DA dưới các giả định kịch bản |
| **S3 (KRBTGT)** | **Không hỗ trợ (Unsupported)** | **Không hỗ trợ (Unsupported)** | **Gate O unknown khiến cả hai chế độ đều dừng lại** |

Kết luận:
Sự phân tách rạch ròi giữa hai chế độ bảo đảm tính trung thực khoa học: Chế độ thuần bằng chứng bảo vệ tính toàn vẹn của dữ liệu quan sát, trong khi chế độ kịch bản cho phép các chuyên gia an ninh mô phỏng các nguy cơ tiềm tàng dưới các giả định được kiểm soát chặt chẽ.

---

## 8. Ca đối chứng 5: Hiệu ứng suy giảm theo độ dài đường (Path Length Degradation) và Tính tương thích thuật toán Dijkstra

### 8.1. Giới hạn lý thuyết của hàm Bottleneck Min
Hàm khâu yếu nhất ($\min$) có ưu điểm vượt trội về tính đơn giản, dễ giải trình và tính ổn định thứ tự.
Tuy nhiên, thử nghiệm thực nghiệm đã làm rõ giới hạn cố hữu của hàm này:
- Một đường tấn công gồm **1 bước duy nhất** có mức khả năng thành công là High sẽ nhận đánh giá toàn đường là **High**.
- Một đường tấn công gồm **10 bước liên tiếp** đều có mức High cũng nhận đánh giá toàn đường là **High**.

Về mặt xác suất học, nhận định này không thực sự phản ánh đúng thực tế: Một chuỗi tấn công càng dài thì xác suất tích lũy thất bại càng lớn.

### 8.2. So sánh Thuật toán Dijkstra Thực tế với Exhaustive Search Oracle trên Hàm Phi tuyến Gộp

#### Thiết lập đồ thị phản ví dụ phi tuyến thực tế
Để kiểm chứng trực tiếp xem thuật toán Dijkstra có hoạt động đúng trên các hàm chi phí phi tuyến gộp hay không, Thí nghiệm 5 đã hiện thực hóa thuật toán Dijkstra và thuật toán tìm kiếm vét cạn (Exhaustive Search Oracle) trên đồ thị phản ví dụ:
- Điểm xuất phát: $S$, điểm trung gian: $B$ và $X$, điểm đích: $T$.
- Cạnh $S \to X$: Chi phí $C = 1.0$, Khả năng thành công $P = 0.5$.
- Cạnh $S \to B$: Chi phí $C = 1.0$, Khả năng thành công $P = 0.95$.
- Cạnh $B \to X$: Chi phí $C = 1.0$, Khả năng thành công $P = 0.95$.
- Cạnh $X \to T$: Chi phí $C = 6.0$, Khả năng thành công $P = 0.5$.
- Hàm mục tiêu phi tuyến gộp: $f(\text{Path}) = \frac{C(\text{Path})}{\prod P(e)}$.

#### Kết quả chạy thuật toán thực nghiệm
Khi chạy thuật toán Dijkstra so với Exhaustive Search Oracle trên đồ thị trên:
1. **Tại nút trung gian $X$**:
   - Nhánh trực tiếp $S \to X$: $C = 1.0, P = 0.5 \implies \text{Score} = \frac{1.0}{0.5} = \mathbf{2.0}$.
   - Nhánh gián tiếp $S \to B \to X$: $C = 1.0 + 1.0 = 2.0, P = 0.95 \times 0.95 = 0.9025 \implies \text{Score} = \frac{2.0}{0.9025} \approx \mathbf{2.216}$.
   - Cơ chế tham lam (greedy) của Dijkstra so sánh $2.0 < 2.216$, do đó Dijkstra quyết định **cố định nút $X$ theo đường $S \to X$** và vĩnh viễn loại bỏ nhánh qua $B$.
2. **Tại nút đích $T$**:
   - Đường do Dijkstra tìm được ($S \to X \to T$):
     Tổng chi phí $C = 1.0 + 6.0 = 7.0$; Xác suất tích lũy $P = 0.5 \times 0.5 = 0.25$.
     Điểm số phi tuyến gộp: $\text{Score} = \frac{7.0}{0.25} = \mathbf{28.0}$.
   - Đường do Exhaustive Search Oracle tìm được ($S \to B \to X \to T$):
     Tổng chi phí $C = 1.0 + 1.0 + 6.0 = 8.0$; Xác suất tích lũy $P = 0.95 \times 0.95 \times 0.5 = 0.45125$.
     Điểm số phi tuyến gộp: $\text{Score} = \frac{8.0}{0.45125} \approx \mathbf{17.7285}$.

Kết luận kiểm chứng:
Đường tối ưu thực sự của hệ thống là $S \to B \to X \to T$ với điểm số $17.7285 \ll 28.0$.
Tuy nhiên, thuật toán Dijkstra đã trả về đường dưới tối ưu (suboptimal path $S \to X \to T$) với điểm số tệ hơn nhiều (28.0).
Điều này chứng minh bằng thực nghiệm chạy thuật toán thực tế: **Hàm phi tuyến gộp phá vỡ cấu trúc con tối ưu Bellman và làm Dijkstra thất bại hoàn toàn!**

### 8.3. Kiểm chứng Stratified Dijkstra trên Đồ thị con Cộng dồn $C \ge 0$
Ngược lại với hàm phi tuyến gộp, giải pháp **Stratified Dijkstra** lọc trước đồ thị theo điều kiện phân tầng khả năng thành công (ví dụ $P \ge 0.75$) và chỉ tối thiểu hóa chi phí nỗ lực cộng dồn không âm $C \ge 0$ trên đồ thị con đã lọc:
- Đồ thị con gồm hai đường cạnh tranh:
  - Đường qua $B$ ($S \to B \to T$): $C = 2.0 + 2.0 = 4.0$ ($P = 0.95 \times 0.95 = 0.9025$).
  - Đường qua $C$ ($S \to C \to T$): $C = 3.0 + 0.5 = 3.5$ ($P = 0.95 \times 0.95 = 0.9025$).
- Kết quả chạy thuật toán:
  Thuật toán Dijkstra tìm ra đường tối ưu $S \to C \to T$ với tổng chi phí $C = 3.5$.
  Kết quả này khớp chính xác 100% với kết quả của Exhaustive Search Oracle ($C = 3.5$).

Sự trùng khớp chỉ xác nhận kết quả trên fixture tĩnh này; không chứng minh global path-likelihood constraints hoặc proposal #150 tương thích static filtering/Dijkstra.

### 8.4. Phát hiện Giới hạn Kỹ thuật: Thất bại của Bộ lọc Cạnh tĩnh trước Sự suy giảm Tích lũy
Mặc dù Stratified Dijkstra hoạt động trên đồ thị con, Thí nghiệm 5 đã phát hiện một rào cản kỹ thuật nghiêm trọng đối với việc áp dụng bộ lọc cạnh tĩnh (static edge filtering):
- Xét một đường tấn công gồm 3 bước chủ động liên tiếp, mỗi cạnh có khả năng thành công là $P(e) = 0.90$.
- Nếu áp dụng ngưỡng lọc cạnh tĩnh ở mức High ($P \ge 0.75$), cả 3 cạnh đều thỏa mãn điều kiện lọc ($0.90 \ge 0.75$) và được giữ lại trong đồ thị con.
- Tuy nhiên, khả năng thành công tích lũy của toàn bộ đường đi là:
  $$P_{\text{path}} = 0.90 \times 0.90 \times 0.90 = \mathbf{0.729} < \mathbf{0.75}$$
- Toàn bộ đường đi thực tế đã bị suy giảm và rơi xuống phân tầng **Medium** ($0.50 \le P < 0.75$)!

Hệ quả kỹ thuật:
**Bộ lọc cạnh tĩnh hoàn toàn không bảo đảm được phân tầng của toàn bộ đường đi khi có sự suy giảm xác suất tích lũy!**
Thuật toán tìm kiếm không thể chỉ đơn thuần lọc các cạnh trước khi chạy Dijkstra.
Để bảo đảm tính hợp lệ của phân tầng, hệ thống bắt buộc phải:
1. Mở rộng không gian trạng thái theo cặp `(node, accumulated_active_steps)` để theo dõi số bước chủ động tích lũy dọc theo đường tìm kiếm.
2. Hoặc áp dụng thuật toán tìm kiếm có ràng buộc toàn đường (path-level constrained search).

### 8.5. Phát hiện Giới hạn Kỹ thuật: Cơ chế Đếm bước Ngây thơ Vi phạm Tính tương đương Đóng gói Hành động
Thí nghiệm 5 cũng kiểm tra mô hình suy giảm khả năng thành công theo số bước chủ động $P_{\text{degraded}} = P_0 \cdot \gamma^{k_{\text{active}}}$ ($\gamma = 0.90$) và phát hiện một lỗ hổng phương pháp luận:
- Xét cùng một thao tác leo quyền kỹ thuật được biểu diễn theo hai cách:
  - **Dạng phân tách (Split representation, 2 bước chủ động)**: $P_{\text{degraded}} = 1.0 \times 0.90^2 = \mathbf{0.81}$.
  - **Dạng gộp (Merged representation, 1 bước chủ động)**: $P_{\text{degraded}} = 1.0 \times 0.90^1 = \mathbf{0.90}$.
- Cùng một bản chất khai thác thực tế, nhưng việc phân chia bước của người phân tích lại làm thay đổi khả năng thành công từ $0.90$ thành $0.81$!

Hệ quả phương pháp luận:
**Cơ chế suy giảm bằng cách đếm số bước ngây thơ (naive step counting) vi phạm trực tiếp tính tương đương đóng gói hành động (action packaging invariance) và tính tương đương ngữ nghĩa!**
Mô hình không thể chỉ đơn thuần đếm số bước hành động để suy giảm xác suất.
Sự suy giảm khả năng thành công (nếu áp dụng) phải gắn liền với ranh giới nỗ lực nội tại hoặc ngưỡng tương tác phòng ngự thực sự, chứ không thể phụ thuộc vào cách chia nhỏ bước của công cụ phân tích.

---

## 9. Verdict và khuyến nghị lịch sử #142 (đã dẫn tới đề xuất #150 / PR #151)

### 9.1. Kết luận kiểm chứng tổng thể (Validation Verdict)
Căn cứ vào kết quả thực nghiệm toàn diện trên dữ liệu snapshot SEAMLESS, mô phỏng thuật toán tìm kiếm và phân tích độ nhạy:
**Verdict: NEEDS REVISION (Bản nháp mô hình cần chỉnh sửa căn bản về cơ chế phân tầng và biểu diễn không gian trạng thái trước khi chuyển giao sang Issue #143).**

Cơ sở của kết luận:
1. **Các điểm tích cực đã được xác minh**:
   - Đối chiếu ca tính tay đạt độ lệch 0.0 tuyệt đối.
   - Bất biến đóng nhóm thụ động $C_{\text{closure}} \equiv 0$ bảo toàn tính tương đương chi phí và loại bỏ việc phạt cú pháp nhóm lồng nhau.
   - Hàm chi phí nỗ lực có độ nhạy thực sự khi xảy ra hòa điểm ở các tiêu chí cấp cao.
   - Cơ chế đánh giá cổng động và lan truyền bất định bảo vệ tính trung thực của Gate O trên bảng chân lý 27 tổ hợp.
   - Stratified Dijkstra bảo toàn tính tối ưu con Bellman trên đồ thị con cộng dồn cố định phân tầng.
2. **Các giới hạn kỹ thuật và rào cản cốt lõi cần giải quyết**:
   - Hiện tượng "mù từ điển" (lexicographic blindness) đòi hỏi phải có cơ chế hiển thị Biên Pareto và Ma trận Rủi ro đi kèm.
   - Phép nhân điểm thứ bậc $I \times P$ trong ma trận rủi ro chỉ là chỉ báo heuristic minh họa, chưa phải là cơ sở toán học để tính tổn thất kỳ vọng thực tế.
   - Bộ lọc cạnh tĩnh thất bại trong việc bảo đảm phân tầng toàn đường khi có sự suy giảm xác suất tích lũy ($0.90^3 = 0.729 < 0.75$).
   - Cơ chế suy giảm theo cách đếm bước ngây thơ vi phạm tính tương đương đóng gói hành động ($0.81$ so với $0.90$).
   - Hệ thống chưa có biểu diễn không gian trạng thái mở rộng `(node, accumulated_active_steps)` để hỗ trợ thuật toán tìm kiếm khả thi.

Do đó, bản nháp mô hình chưa đủ cơ sở toán học và thực nghiệm để ban hành thành production profile hay successor ADR chính thức.
Verdict lịch sử này đã dẫn tới #150 hiệu chỉnh proposal trước review; #142 không tiếp tục sở hữu việc sửa mô hình và #143 chưa chốt decision.

### 9.2. Danh mục 5 khuyến nghị điều chỉnh cho Mô hình và Handoff #143
Để hoàn thiện mô hình, nhóm TTS A đề xuất 5 định hướng kỹ thuật:
1. **Khuyến nghị 1 (Bổ sung Chế độ xem Biên Pareto và Ma trận Rủi ro)**:
   Giữ mô hình Phân cấp Từ điển làm baseline sắp xếp thứ tự ưu tiên, nhưng bắt buộc hệ thống phải xuất thêm hai góc nhìn song song: Biên Pareto $(I, P)$ và Cảnh báo Ma trận Rủi ro (Critical Risk Overlay) để hiển thị tradeoff với các đường likelihood cao nhưng consequence rating thấp hơn.
2. **Khuyến nghị 2 (Duy trì Bất biến Đóng nhóm Thụ động)**:
   Quy định $C_{\text{closure}} \equiv 0$ như một yêu cầu bắt buộc trong mọi hiện thực hóa mô hình tính nỗ lực để bảo vệ tính bất biến trước số hop nhóm lồng nhau.
3. **Khuyến nghị 3 (Nghiên cứu lại Cơ chế Suy giảm Xác suất Tích lũy)**:
   Bác bỏ cơ chế đếm bước ngây thơ vì vi phạm tính tương đương đóng gói hành động.
   Nghiên cứu cơ chế suy giảm dựa trên ranh giới tương tác hoặc độ phức tạp tích lũy, bảo đảm tính bất biến ngữ nghĩa.
4. **Khuyến nghị 4 (Mở rộng Không gian Trạng thái cho Thuật toán Tìm đường)**:
   Do bộ lọc cạnh tĩnh không bảo đảm được phân tầng toàn đường khi có suy giảm tích lũy, kiến trúc tìm đường của Milestone M3 bắt buộc phải thiết kế trên không gian trạng thái mở rộng `(node, accumulated_active_steps)` hoặc áp dụng thuật toán tìm đường có ràng buộc toàn chuỗi.
5. **Khuyến nghị 5 (Hiệu chuẩn Tuyên bố Khoa học và Chuẩn bị Bàn giao #143)**:
   Chưa ban hành Successor ADR hoặc trọng số sản phẩm cố định khi các vấn đề toán học trên chưa được giải quyết trọn vẹn.
   Các phát hiện trong tài liệu này đóng vai trò là bằng chứng thực nghiệm phục vụ việc hoàn thiện bản đặc tả mô hình và giao diện cho TTS B tại Issue #143.

---

## 10. Lệnh tái lập, thông số môi trường và worklog evidence

### 10.1. Môi trường thực thi kiểm chứng
- Hệ điều hành: macOS Darwin Kernel Version 24 (arm64).
- Trình quản lý môi trường và gói: `uv` (Fast Python package installer and resolver).
- Phiên bản Python: Python 3.14.7 (Virtual environment `.venv`).
- Công cụ kiểm thử: `pytest` 9.1.1, `pluggy` 1.6.0.
- Công cụ kiểm tra chất lượng mã: `ruff` 0.14.0.
- Mã nguồn kiểm chứng: `scripts/research/worked_example_validation.py` (chuẩn hóa type hints, chỉ dùng thư viện chuẩn Python, an toàn mã hóa UTF-8).
- Bộ test case tự động: `tests/test_worked_example_validation.py` (27 test cases bao phủ 100% các thí nghiệm, thuật toán tìm kiếm, phân loại gating động, xử lý CLI và kiểm tra snapshot hermetic).

### 10.2. Lệnh tái lập và kết quả kiểm tra
Để tái lập toàn bộ kết quả trong báo cáo này, chạy các lệnh sau từ thư mục gốc của kho lưu trữ:

```bash
# 1. Chạy toàn bộ bộ kiểm chứng và xuất bảng báo cáo chi tiết
uv run python scripts/research/worked_example_validation.py --all

# 2. Xuất dữ liệu kiểm chứng dưới định dạng JSON máy đọc được
uv run python scripts/research/worked_example_validation.py --json

# 3. Chạy toàn bộ test suite kiểm chứng tự động
uv run pytest tests/test_worked_example_validation.py -v

# 4. Kiểm tra tuân thủ chuẩn mã nguồn và hợp đồng kho lưu trữ
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_repository.py
uv run python scripts/check_contract.py
```

### 10.3. Bằng chứng thực thi (Worklog Evidence)
- Kiểm thử đơn vị: 27/27 test cases passed (100% pass rate) trong 0.44 giây.
- Snapshot SEAMLESS: File hash SHA-256 xác thực nghiêm ngặt thành công, đối chiếu 100% khớp với manifest `seamless-raw-v1.json`.
- Định vị chính xác các locator: `Source A` (`computers/46`), `User-Candidate` (`users/2310`), GenericAll ACE (`users/2310/Aces/3`), `Target-Group-DA` (`groups/40`), DA Membership (`groups/40/Members/0`), và `Target-User-KRBTGT` (`users/3`).
- Gating nối vào xếp hạng: Kiểm chứng tự động xác nhận Gate A = False làm thay đổi khả thi toàn đường sang `Blocked` và đẩy xuống sau toàn bộ các đường khả thi trong `lexicographic_key`.
- CLI an toàn: Truyền `--raw-dir` đơn lẻ tự động nạp manifest mặc định hoặc trả mã thoát khác 0 khi đường dẫn không hợp lệ.
- CI hermetic: Toàn bộ kiểm thử snapshot lỗi và hash sai được cô lập trong `tempfile.TemporaryDirectory`, không phụ thuộc dữ liệu snapshot cục bộ và loại bỏ hoàn toàn lỗi `KeyError: 'file_hash_verified'`.
- Độ lệch tính tay: `total_deviation = 0.0`.
- Thuật toán Dijkstra trên hàm phi tuyến gộp: Thất bại được chứng minh bằng thực nghiệm chạy thuật toán thực tế (Dijkstra score 28.0 so với Exhaustive Oracle score 17.7285).
- Tình trạng hợp đồng kho lưu trữ: Không có lỗi liên kết Markdown hỏng, không có vi phạm ranh giới dữ liệu bí mật.
