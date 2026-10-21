# Bàn giao gói chấm điểm Week 4 và kết quả kiểm chứng Evaluator

Ngày 07/10/2026.
Tác giả: TTS A (@Lolavine777).
Người rà soát: TTS B (@nairyuuu).
Thực hiện [Issue #207](https://github.com/nairyuuu/ad-weighted-graph/issues/207), tham chiếu ADR-0013, Issue #204, #205, #206 và PR #214.

## 1. Mục tiêu và phạm vi bàn giao

Tài liệu này bàn giao toàn bộ gói chấm điểm Week 4 theo đúng hợp đồng giao diện của PathRankingEngine (Specification v1.0.0).
Mục tiêu cốt lõi là cung cấp các gói dữ liệu có định danh phiên bản, mã băm digest, kết quả tính tay độc lập và kết quả thực thi thực tế từ canonical evaluator hiện hành.
Gói bàn giao thiết lập ranh giới rõ ràng giữa truy vấn tối ưu công sức Min-Effort và biên rủi ro Pareto bảo thủ theo ADR-0013.
Tài liệu chứng minh các nguyên lý chống tính lặp, phân vùng chẩn đoán fail-closed khi thiếu dữ liệu thực nghiệm, và giữ nguyên vẹn 21 tham số Week 3 đã được phê duyệt.

## 2. Ranh giới sở hữu và Audit tái sử dụng

Tuân thủ nghiêm ngặt phân công trách nhiệm giữa TTS A và TTS B:
TTS A chịu trách nhiệm về dữ liệu kịch bản, ánh xạ công việc, luận cứ chấm điểm C/P/I và các bộ kiểm thử độc lập.
TTS B sở hữu toàn bộ mã nguồn tìm kiếm, engine xếp hạng, adapter chuyển đổi và harness đánh giá.
TTS A không thay đổi công thức xếp hạng, không can thiệp vào mã nguồn engine của TTS B và không tự tiện mở rộng phạm vi cracking ngoại tuyến khi chưa có dữ liệu thực nghiệm.

### Bảng 1: Kết quả rà soát tái sử dụng từ Week 3 và các mốc trước

| Hạng mục rà soát | Nguồn gốc | Trạng thái hiện tại | Xử lý trong Week 4 |
| --- | --- | --- | --- |
| 21 tham số SEAMLESS Week 3 | docs/research/ratings/week3-closeout | Đã được chấp thuận (digest sha256:20f67e...) | Tái sử dụng nguyên vẹn cho đúng kịch bản gốc; không thay đổi số liệu |
| Cấu trúc đồ thị hai đường đi | graphs/two-routes.json | Canonical golden fixture A2 | Tái sử dụng nguyên bản cho các gói synthetic A2 |
| Ledger công sức E và T | docs/research/week4-scenarios.md (#214) | Dữ liệu kiểm thử độc lập của A2 | Đưa vào gói dữ liệu chuẩn hóa có digest kiểm chứng |
| Giao thức PathRankingEngine v1.0.0 | src/engine/ranking/ | Đã chuẩn hóa tại Week 3 | Sử dụng nguyên bản làm canonical evaluator để chạy gói |
| Phân tích trường thuộc tính Active Directory | docs/research/week4-field-driven-screening.md | Đã sàng lọc từ dữ liệu thô | Xác định các kỹ thuật thiếu dữ liệu cracking thực nghiệm |
| Kỹ thuật AS-REP roasting và Kerberoasting | Issue #192, #200 | Thiếu dữ liệu phân phối độ mạnh mật khẩu | Giữ trạng thái explicit unrated; không tự ý gán điểm số |

## 3. Ánh xạ Action sang Work Units và Sự kiện thành công

Mỗi hành động trong gói chấm điểm được gắn kết chặt chẽ với các đơn vị công việc hữu hình và các sự kiện thành công cụ thể.

### Bảng 2: Ánh xạ hành động, công việc và sự kiện thành công trên Fixture A2

| Ký hiệu | Định danh hành động | Kỹ thuật tấn công | Nút nguồn | Nút đích | Work units tham chiếu | Sự kiện thành công | Vị trí cổng điều kiện |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D | action_direct_admin | obtain_admin_execution_on_host | Alice | Host C0 | w-auth-context, w-direct-admin | admin_execution_on_host_c0 | Layer 3 (admin_channel, authentication) |
| M | action_member_admins | propagate_group_entitlement | Alice | Admins | (không có) | effective_member_alice_admins | Layer 3 (security_group, membership_usable) |
| I | action_inherited_admin | obtain_admin_execution_on_host | Alice | Host C0 | w-auth-context, w-inherited-admin | admin_execution_on_host_c0 | Layer 3 (effective_member, admin_channel, auth) |

Nhận xét quan trọng:
Hành động M (propagate_group_entitlement) là một bao đóng thụ động (is_passive_closure = True).
Bao đóng này chỉ ghi nhận sự lan truyền quyền hạn nhóm sẵn có trong đồ thị mà không đòi hỏi kẻ tấn công phải thực hiện thao tác ma sát nào.
Do đó danh sách work units của M hoàn toàn rỗng.

## 4. Cơ sở chấm điểm và Luận cứ C/P/I

### Công sức C (Effort)
Công sức của một chương trình tấn công được tính bằng tổng chi phí ma sát của các work units duy nhất xuất hiện trong chương trình đó.
Công thức tổng quát: C(program) = sum(computed_cost(u)) với mọi u thuộc tập hợp hợp nhất các work units của chương trình.
Trên Ledger E:
- w-auth-context: computed_cost = 1 (rubric t1 = 1, t2 = 2; công việc thiết lập kênh và ngữ cảnh xác thực dùng chung).
- w-direct-admin: computed_cost = 4 (rubric t1 = 3, t2 = 3; thao tác leo thang quản trị trực tiếp đối mặt cơ chế phòng thủ máy chủ).
- w-inherited-admin: computed_cost = 1 (rubric t1 = 1, t2 = 2; thao tác quản trị kế thừa thông qua tài khoản nhóm đặc quyền).
Trên Ledger T:
- Cả ba đơn vị công việc w-auth-context, w-direct-admin và w-inherited-admin đều có computed_cost = 1.

### Xác suất điều kiện P (Conditional Likelihood)
Xác suất thành công toàn chuỗi được tính thông qua tích các khoảng xác suất điều kiện trên từng tiền tố công việc hợp lệ.
Mỗi bước điều kiện hóa trên toàn bộ tiền tố trước đó, không giả định tính độc lập thống kê:
P(program) = product(P(step_k | step_1, ..., step_{k-1})) với k chạy từ 1 đến độ dài chuỗi.
Khoảng xác suất được biểu diễn chính xác dưới dạng phân số tối giản (Rational Fraction) nhằm triệt tiêu hoàn toàn sai số dấu phẩy động.
Trên Fixture A2 (synthetic):
- Tiền tố [w-auth-context]: khoảng xác suất [4/5, 9/10] (thành công thiết lập ngữ cảnh xác thực).
- Tiền tố [w-auth-context, w-direct-admin]: khoảng xác suất điều kiện [1/2, 3/4].
Tích xác suất toàn chuỗi cho nhánh Direct: P = [4/5 * 1/2, 9/10 * 3/4] = [2/5, 27/40] (tương đương 40,0% đến 67,5%).
- Tiền tố [w-auth-context, w-inherited-admin]: khoảng xác suất điều kiện [3/5, 4/5].
Tích xác suất toàn chuỗi cho nhánh Inherited: P = [4/5 * 3/5, 9/10 * 4/5] = [12/25, 18/25] (tương đương 48,0% đến 72,0%).

### Tác động I (Impact Consequence)
Tác động được gắn chặt với hậu quả thực tế trên tài sản mục tiêu, không tự động gán nhãn Critical cho mọi vai trò Domain Admin hoặc Domain Controller.
Tại Fixture A2:
Tài sản mục tiêu Host C0 là một máy chủ ứng dụng nội bộ trong mạng giả định.
Việc chiếm quyền quản trị trên Host C0 làm lộ lọt dữ liệu cục bộ nhưng không cấp quyền điều khiển toàn miền Tier 0.
Do đó mức tác động được đánh giá là High kèm theo lý giải nghiệp vụ cụ thể trong target_impact_assessments.

## 5. Đánh giá chống tính lặp (Anti-Double-Counting)

Gói chấm điểm áp dụng các cơ chế nghiêm ngặt nhằm ngăn chặn sai lệch do tính lặp:

1. Không phạt việc phân tách bước giải thích:
Khi một hành động được giải thích chi tiết thành nhiều bước trung gian, tập hợp các work unit hợp nhất không thay đổi.
Do đó công sức tổng không bị tăng thêm nhân tạo.

2. Không tính công sức cho quyền thành viên thụ động:
Đường đi qua cạnh MemberOf (hành động M) không tạo ra ma sát công việc mới.
Kết quả tính toán trên Ledger E chứng minh:
Chương trình Direct (D) gồm 1 bước có công sức C = 1 + 4 = 5.
Chương trình Member-Direct (M/D) gồm 2 bước cạnh có công sức C = 1 + 4 = 5.
Hai chương trình này có cùng công sức C = 5 và cùng khoảng xác suất P = [2/5, 27/40].
Bước membership thụ động không làm suy giảm xác suất hay tăng công sức.

3. Tái sử dụng ngữ cảnh xác thực và bí mật:
Kẻ tấn công sau khi đã thiết lập ngữ cảnh xác thực với w-auth-context sẽ tái sử dụng ngữ cảnh đó cho các hành vi tiếp theo trên cùng mục tiêu.
Hệ thống không yêu cầu xác thực lại và không cộng thêm chi phí xác thực lần hai.

4. Công việc chủ động thực sự thay đổi đúng đại lượng:
Khi một đường đi đòi hỏi thao tác chủ động thực sự khác biệt, các đại lượng thay đổi chính xác bằng hiệu số chi phí rubric của đơn vị công việc mới.
Chương trình Direct (D) sử dụng w-direct-admin (chi phí rubric 4), trong khi chương trình Inherited (M/I) sử dụng w-inherited-admin (chi phí rubric 1).
Chênh lệch công sức giữa hai chương trình là 5 - 2 = 3, đúng bằng chênh lệch chi phí rubric 4 - 1 = 3.

5. Bất biến tách và gộp bước nội bộ chương trình:
Việc biểu diễn một thao tác dưới dạng nhiều bước hành động nhỏ mang cùng work unit không làm thay đổi tổng công sức hay phân rã xác suất.
Chương trình chia tách (Action 1 chuẩn bị xác thực w-auth-context, Action 2 thực thi quản trị tham chiếu w-auth-context và w-direct-admin) có cùng công sức C = 5 và xác suất P = [2/5, 27/40] như một bước gộp duy nhất.
Chuỗi lịch sử M/D/I từ #206 (docs/research/week4-scenarios.md dòng 115) tái sử dụng w-auth-context đúng một lần, mang lại tổng công sức ledger là 6 (1 + 4 + 1 = 6) thay vì 7.

6. Bảo tồn độc lập giữa các ngữ cảnh máy khác nhau:
Các work units gắn với các thực thể đích riêng biệt (như w-auth-context trên Host C0 so với w-auth-otherhost trên OtherHost X) đại diện cho ngữ cảnh bảo mật độc lập.
Cơ chế chống tính lặp tuyệt đối không xóa nhầm hoặc gộp chung các đơn vị thuộc hai máy đích khác nhau, đảm bảo 1 + 1 = 2 công sức khi cả hai cùng xuất hiện.

## 6. Kết quả tính toán độc lập trên Fixture A2

Các kết quả tính tay độc lập được xác lập trước khi đối chiếu với công cụ đánh giá tự động:

### Tính toán trên Ledger E
- Chương trình D: tập công việc {w-auth-context, w-direct-admin}, C = 1 + 4 = 5, P = [2/5, 27/40], I = High.
- Chương trình M/D: tập công việc {w-auth-context, w-direct-admin}, C = 1 + 4 = 5, P = [2/5, 27/40], I = High.
- Chương trình M/I: tập công việc {w-auth-context, w-inherited-admin}, C = 1 + 1 = 2, P = [12/25, 18/25], I = High.
Đánh giá Min-Effort:
Min-Effort tìm kiếm đường đi có C nhỏ nhất.
Chương trình M/I đạt C = 2, nhỏ hơn D với C = 5 và M/D với C = 5.
Đây là trường hợp tối ưu ngược cấu trúc: đường đi dài hơn về số cạnh (2 cạnh) lại có công sức nhỏ hơn đường đi ngắn (1 cạnh).
Đánh giá Pareto Frontier:
So sánh hai chương trình D và M/I:
Cả hai đều có cùng mức tác động I = High.
Khoảng xác suất của D là [0.400, 0.675].
Khoảng xác suất của M/I là [0.480, 0.720].
Vì hai khoảng xác suất này giao nhau, theo định nghĩa bảo thủ của ADR-0013, không khoảng nào trội hơn khoảng nào.
Do đó cả hai chương trình không thể so sánh được và đều phải nằm trên Pareto frontier:
Frontier = {cand_direct, cand_member_direct, cand_member_inherited}.

### Tính toán trên Ledger T
- Cả ba chương trình D, M/D và M/I đều có C = 2.
- Min-Effort ghi nhận thế hòa 3 bên: minimum_effort_value = 2.
- Pareto frontier giữ nguyên cả ba ứng viên vì không có sự áp đảo nào về I và P.

### Tính toán trên gói Tie-Break (ADR-0013 Mục 4)
- Chương trình D: P = [1/2, 1/2], C = 5, I = High.
- Chương trình M/I: P = [1/2, 1/2], C = 2, I = High.
Vì P là điểm duy nhất bằng nhau (P = 1/2) và I bằng nhau (High), quy tắc phá hòa hẹp bằng công sức C được kích hoạt.
M/I có C = 2 nhỏ hơn C = 5 của D, nên M/I áp đảo hoàn toàn D.
Pareto frontier thu hẹp còn lại duy nhất: {cand_member_inherited}.

## 7. Kết quả thực thi từ Canonical Evaluator

Toàn bộ 4 gói dữ liệu đã được nạp và thực thi qua PathRankingEngine v1.0.0.
Kết quả thực tế được ghi nhận đầy đủ trong `docs/research/ratings/week4/actual-evaluator-results.json`.

### Bảng 3: Đối chiếu giữa tính toán độc lập và kết quả thực thi của Evaluator

| Gói kiểm thử | Đại lượng đánh giá | Kết quả tính tay độc lập | Kết quả từ Canonical Evaluator | Trạng thái đối chiếu |
| --- | --- | --- | --- | :---: |
| synthetic-a2-e | Min-Effort tối ưu | cand_member_inherited (C = 2) | cand_member_inherited (C = 2) | KHỚP TUYỆT ĐỐI |
| synthetic-a2-e | Chống tính lặp | C(D) == C(M/D) == 5; P(D) == P(M/D) | C(D) == C(M/D) == 5; P(D) == P(M/D) | KHỚP TUYỆT ĐỐI |
| synthetic-a2-e | Pareto Frontier | {cand_direct, cand_member_direct, cand_member_inherited} | [cand_direct, cand_member_direct, cand_member_inherited] | KHỚP TUYỆT ĐỐI |
| synthetic-a2-t | Min-Effort hòa 3 bên | C = 2 cho cả D, M/D, M/I | minimum_effort_value = 2, hòa 3 bên | KHỚP TUYỆT ĐỐI |
| synthetic-a2-t | Pareto Frontier | Giữ nguyên cả 3 ứng viên | [cand_direct, cand_member_direct, cand_member_inherited] | KHỚP TUYỆT ĐỐI |
| synthetic-a2-ties | Điểm P phá hòa | M/I áp đảo D do C = 2 < 5 | [cand_member_inherited] | KHỚP TUYỆT ĐỐI |
| synthetic-a2-diagnostics | Phân vùng fail-closed | Phân tách blocked, unknown, unrated | 6 ứng viên được phân vùng chính xác | KHỚP TUYỆT ĐỐI |

## 8. Phân vùng chẩn đoán và Cơ chế Fail-Closed

Gói synthetic-a2-diagnostics.json kiểm chứng tính năng đóng an toàn khi dữ liệu không hoàn chỉnh:

1. Cổng điều kiện bị chặn (Blocked Gate):
Ứng viên cand_blocked_firewall yêu cầu cổng blocked_firewall_host có giá trị False trong snapshot.
Evaluator gán trạng thái blocked, công sức trở thành ineligible và thu hồi toàn bộ tính toán xác suất.
Ứng viên bị đưa vào vùng chẩn đoán với lý do ["blocked", "likelihood_unrated"].

2. Cổng điều kiện chưa rõ (Unknown Gate):
Ứng viên cand_unknown_service yêu cầu vị từ unknown_service_health được khai báo là sự thật chưa rõ.
Evaluator gán trạng thái unknown và thu hồi xác suất.
Ứng viên bị đưa vào vùng chẩn đoán với lý do ["likelihood_unrated", "unknown"].

3. Thiếu căn cứ xác suất (Missing Likelihood Basis):
Ứng viên cand_missing_likelihood_basis có các cổng điều kiện khả thi (feasible), nhưng bảng xác suất không chứa tiền tố tương ứng.
Evaluator giữ trạng thái feasible cho cổng, công sức vẫn được tính (C = 5), nhưng khoảng xác suất bị thu hồi (None).
Ứng viên bị đưa vào vùng chẩn đoán với lý do ["likelihood_unrated"].

4. Cổng giả định runtime với căn cứ xác suất chưa chấm (Assumed Gate with Unrated Basis):
Ứng viên cand_assumed_gate_unrated_basis sử dụng hành động yêu cầu vị từ runtime_session_alice được khai báo trong assumed_facts.
Trong chế độ scenario, cổng logic được thỏa mãn và đạt trạng thái feasible.
Tuy nhiên bảng xác suất không chứa tiền tố tương ứng, do đó khoảng xác suất bị thu hồi (None) và trạng thái là unrated.
Evaluator đưa ứng viên vào vùng chẩn đoán với lý do ["likelihood_unrated"].
Điều này chứng minh giả định runtime đúng chỉ mở cổng logic chứ không tự tạo ra căn cứ xác suất số học.

5. Thiếu dữ liệu ma sát công sức (Unrated Effort):
Ứng viên cand_unrated_effort sử dụng work unit w-unrated-friction có trạng thái unrated trên sổ cái.
Evaluator đánh giá effort_status là unrated và giá trị effort là None.
Ứng viên bị loại khỏi tập hợp đủ điều kiện của Min-Effort baseline (không thể được chọn làm best candidate).
Đồng thời do thiếu tiền tố xác suất, ứng viên cũng bị đưa vào vùng chẩn đoán với lý do ["likelihood_unrated"].

6. Thiếu căn cứ tác động (Unrated Impact):
Ứng viên cand_unrated_impact hướng tới tài sản OtherHost X mang đầy đủ các work units scoped riêng cho máy này (w-auth-otherhost chi phí 1 và w-direct-admin-otherhost chi phí 4).
Evaluator tính được công sức định mức là 5 và khoảng xác suất điều kiện là [1/4, 1/4], nhưng đánh giá tác động là unrated (None) kèm lý do thiếu căn cứ nghiệp vụ.
Ứng viên được phân vùng an toàn vào khu vực chẩn đoán với lý do ["impact_unrated"].
Trong truy vấn Min-Effort độc lập, cả 3 ứng viên feasible có công sức rated (cand_assumed_gate_unrated_basis, cand_missing_likelihood_basis, cand_unrated_impact) đều có công sức bằng 5; cơ chế phá hòa theo bảng chữ cái chọn cand_assumed_gate_unrated_basis (C = 5, associated_impact: High).
Ứng viên cand_unrated_effort bị loại khỏi Min-Effort vì trạng thái công sức là unrated.

Cơ chế này đảm bảo tuyệt đối không có trường hợp tự tiện điền P = 0 hoặc P = 1 hoặc gán công sức mặc định khi thiếu dữ liệu.

## 9. Xử lý SEAMLESS và Phân loại Kỹ thuật chưa chấm

Bản ghi `docs/research/ratings/week4/week4-seamless-disposition.json` thiết lập nguyên tắc kế thừa từ Week 3:

1. Tiêu chí tái sử dụng:
Các tham số từ đợt phát hành Week 3 chỉ được tái sử dụng khi thỏa mãn đồng thời 5 chiều không gian:
Đúng định danh ràng buộc, đúng sự kiện thành công, đúng ngữ cảnh thực thi, đúng khung thời gian tác chiến (24 giờ) và đúng tài sản đích.
Bất kỳ sự sai khác nào về ngữ cảnh hoặc tài sản đều buộc ứng viên phải giữ trạng thái unrated.

2. Bảo tồn 21 tham số Week 3:
Toàn bộ 21 tham số gắn với ứng viên Lidia, Josefa và Ollie trong kịch bản SEAMLESS được bảo toàn tuyệt đối theo bản phát hành lịch sử có mã băm sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358.

3. Trạng thái các kỹ thuật mới trong Week 4:
- Truy vấn nguồn máy tính (Computer X đến Y): Giữ trạng thái unrated_pending_interface do giao diện truy vấn máy tính công khai chưa được TTS B hoàn thiện.
- Tấn công AS-REP roasting: Mặc dù cờ dontreqpreauth được ghi nhận trong snapshot, nhưng tỷ lệ bẻ khóa hash ngoại tuyến trong vòng 24 giờ hoàn toàn thiếu dữ liệu thực nghiệm; giữ trạng thái unrated_pending_empirical_basis.
- Tấn công Kerberoasting: Thuộc tính ServicePrincipalName tồn tại giúp trích xuất TGS ticket, nhưng dữ liệu độ phức tạp mật khẩu tài khoản dịch vụ chưa được hiệu chuẩn; giữ trạng thái unrated_pending_empirical_basis.
- Tấn công RBCD: Quyền ghi AddAllowedToAct được phát hiện nhưng cơ chế ủy quyền S4U2self và việc tạo tài khoản máy chưa đủ căn cứ; giữ trạng thái unrated_pending_runtime_gates.
- Phân biệt điểm kiểm tra Domain Admin và chiếm giữ Domain Controller: Việc đạt được tư cách thành viên nhóm Domain Admin là một cột mốc quyền hạn trung gian, khác biệt hoàn toàn với việc kiểm soát máy chủ Domain Controller; tác động của từng sự kiện được đánh giá độc lập theo tài sản.

## 10. Kế hoạch độ nhạy và Đánh giá rủi ro

### Kế hoạch độ nhạy (Sensitivity Analysis Plan)
Khi các tham số số học mới được TTS B tiếp nhận trong các mốc tiếp theo, quy trình kiểm tra độ nhạy sẽ được thực hiện theo giao thức chuẩn:
1. Độ nhạy biên xác suất: Điều chỉnh cận trên và cận dưới của từng khoảng xác suất theo mức thay đổi +/- 10% để kiểm tra tính ổn định của Pareto frontier.
2. Độ nhạy ma sát công sức: Tăng hoặc giảm điểm rubric của từng work unit thêm 1 đơn vị để kiểm tra thứ tự ưu tiên trong Min-Effort.
3. Độ nhạy tác động: Chuyển dịch mức tác động giữa High và Medium để xác định ngưỡng chuyển đổi cấu trúc rủi ro.

### Đánh giá rủi ro kỹ thuật
- Rủi ro giả định runtime: Khai báo giả định sai có thể tạo ra các đường đi giả mạo; giải pháp là luôn thực hiện kiểm chứng chéo với snapshot thực tế.
- Rủi ro thiên kiến độ dài: Nguy cơ đánh đồng số bước cạnh với độ phức tạp tấn công; giải pháp là bám sát mô hình work unit ma sát thực tế thay vì đếm bước topo.
- Rủi ro tràn biên Pareto: Khi có quá nhiều khoảng xác suất giao nhau, biên Pareto có thể không hỗ trợ ra quyết định; giải pháp là bổ sung dữ liệu thực nghiệm để thu hẹp khoảng tin cậy.

## 11. Hướng dẫn kiểm chứng và Phụ thuộc tiếp theo

### Các lệnh kiểm chứng độc lập

```bash
# 1. Kiểm tra trạng thái git và các file bàn giao
git status

# 2. Thực thi công cụ đánh giá và kiểm tra toàn vẹn gói chấm điểm
./.venv/bin/python scripts/research/week4_scoring_eval.py --verify

# 3. Chạy toàn bộ các bài kiểm thử tự động của kịch bản và scoring
./.venv/bin/pytest -v tests/test_week4_scenarios.py tests/test_week4_scoring.py

# 4. Kiểm tra toàn vẹn mã băm SHA-256 của các artifact
sha256sum -c docs/research/ratings/week4/manifest.sha256
```

### Các phụ thuộc bàn giao tiếp theo
Gói bàn giao này được chuyển giao cho TTS B (@nairyuuu) rà soát.
TTS A không tự ý sáp nhập nhánh và không tuyên bố Week 4 hoàn tất.
Các bước tiếp theo phụ thuộc vào việc TTS B tích hợp adapter và hoàn tất giao diện truy vấn máy tính trong Issue #206 và #208.
