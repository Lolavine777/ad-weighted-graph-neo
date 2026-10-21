# Tuần 3: Kịch bản, chi phí và bằng chứng tái lập

## Báo cáo triển khai hiện hành sau PR #151 (2026-09-30)

Báo cáo này kết nối liền mạch từ cấu trúc thô -> ngữ nghĩa -> kịch bản -> đánh giá -> xếp hạng -> kiểm chứng theo đề xuất [Pareto bảo thủ](path-ranking-model.md).
Các nội dung ghi ngày 26-28/9 ở Phần 2 bên dưới là bằng chứng lịch sử của Phase A, không phải hướng dẫn tạo trọng số sản phẩm hay quyết định cuối cùng cho Issue #143.
Đề xuất mô hình và mã nguồn nghiên cứu mẫu thử thuộc trách nhiệm của TTS A; module parser chuẩn tắc, engine đồ thị và hiệu năng tìm kiếm thuộc trách nhiệm của TTS B.

| Công đoạn | Diễn giải phân tích của TTS A | Script, hàm và dữ liệu | Điều chưa được phép suy diễn |
| --- | --- | --- | --- |
| Cấu trúc thô (Raw structure) | Chọn lọc dữ kiện có nguồn gốc kiểm chứng (provenance) và bảo đảm đúng chiều quan hệ | `verify_snapshot_data()` kiểm tra toàn bộ manifest; `raw_path_probe.py` quét cấu trúc kèm locator | Đường đi cấu trúc không đồng nghĩa với chuỗi tấn công thực thi được |
| Ngữ nghĩa (Semantics) | Phân biệt rõ vật liệu mật khẩu, định danh sử dụng được, quyền hạn hiệu lực và thao tác đích | Catalog ngữ nghĩa kết hợp logic kiểm tra cổng `AttackPath._evaluate_gates()`; các tiền đề và hiệu ứng do kịch bản khai báo | Đổi mật khẩu không tự trở thành phiên đăng nhập; tư cách thành viên nhóm không tự tương đương quyền DCSync |
| Kịch bản (Scenario) | Cố định điểm xuất phát (foothold), chân trời quan sát, ràng buộc actor/target, dữ kiện ban đầu và biên chi phí | Chế độ thuần dữ kiện không suy diễn S1/S2 từ snapshot; chế độ kịch bản yêu cầu khai báo rõ các vị từ vận hành | Giả định kịch bản tuyệt đối không được ghi đè dữ kiện phủ định (False) hoặc bỏ qua cổng cấp quyền Gate O |
| Đánh giá (Assessment) | Thiết lập sổ cái công việc không trùng lặp và khoảng chặn xác suất theo đúng lịch sử tiền tố thành công | `assess_scoped_program(packets, units, conditional_bounds, gates)` tính tổng nỗ lực và khoảng xác suất | Hàm đánh giá không tự ý gán điểm hành động và không tự chuyển đổi thang thứ bậc sang xác suất |
| Tìm kiếm ứng viên (Candidate search) | Sử dụng không gian trạng thái đơn điệu hữu hạn và ngân sách công việc tích cực | `ResearchAction` kết hợp `bounded_programs(initial, goal, actions, max_work_units)` lưu vết dữ kiện và lịch sử | Không được cắt tỉa một nút chỉ dựa trên tiền tố chi phí nhỏ nhất hoặc chỉ đếm số lượng packet |
| Xếp hạng (Ranking) | Phân vùng trạng thái dữ kiện trước khi đưa vào so sánh Pareto | `risk_ineligibility()` và `scoped_frontier()`; `scoped_preference(a, b)` chỉ so sánh các ứng viên đủ điều kiện | Các ứng viên ở mục chẩn đoán không được lọt vào frontier; trạng thái không đủ điều kiện khác với không so sánh được |
| Kiểm chứng (Validation) | Tính toán trước đáp án bằng tay, đọc kỹ output và đối chiếu các phản ví dụ | Thí nghiệm 6, `exhaustive_search()` và oracle hoán vị; các thí nghiệm 1-5 dùng để kiểm tra hồi quy | Kết quả PASS trên fixture kiểm thử không đồng nghĩa với việc đã hiệu chuẩn thực nghiệm hay đạt tối ưu toàn cục |

Mức tác động (`Impact`) sử dụng 4 mức `Low`, `Medium`, `High`, `Critical` cho hậu quả nghiệp vụ của biến cố thành công, có căn cứ giải trình riêng trong truy vấn hoặc kịch bản.
Theo [bản thể học định danh §5](identity-asset-ontology.md), `Tier0` là nhãn thuộc mặt bằng kiểm soát kỹ thuật, còn `CrownJewel` là nhãn định giá trị nghiệp vụ; hai nhãn này độc lập và có thể cùng xuất hiện.
Không dùng các nhãn phân loại kỹ thuật này để thay thế cho mức đánh giá tác động nghiệp vụ, và không tự ý suy diễn mức `Critical` từ tài khoản DA hay KRBTGT.
Nếu thiếu đánh giá tác động, hàm `scoped_preference()` trả về `not_eligible` và hàm `scoped_frontier()` giữ ứng viên trong danh mục chẩn đoán (`diagnostics`).
Thí nghiệm 1 khai báo độc lập các mức `Critical` và `High`, tách biệt hoàn toàn metadata phân tầng khỏi điểm số; việc thay đổi metadata khi mức tác động giữ nguyên sẽ không làm thay đổi thứ tự ưu tiên.
Toàn bộ đánh giá `Critical` trong các ví dụ tính tay và Thí nghiệm 6 là giả định mô phỏng, chưa phải là hậu quả nghiệp vụ được xác nhận trên môi trường SEAMLESS.

### Hướng dẫn 8 bước tự kiểm tra

1. Đọc kỹ các quan sát thực tế về quan hệ `GenericAll` và `MemberOf` cùng locator tương ứng; không tự thêm cạnh `HasSession` nếu dữ liệu snapshot không ghi nhận.
2. Thiết lập danh sách dữ kiện bắt buộc đúng và mục tiêu sau khi kích hoạt danh tính; nếu ngữ cảnh thiếu dữ kiện hoặc có dữ kiện phủ định, giữ nguyên trạng thái chẩn đoán `unknown` hoặc `blocked` trước khi xếp hạng.
3. Thiết lập sổ cái nỗ lực cho chuỗi `reset` và `activate`, tái sử dụng định mức mô phỏng $(T_1, T_2) = (1, 3)$ và $(1, 2)$ với tổng nỗ lực quy ước là $2 + 1 = 3$.
4. Kiểm tra việc phân tách các gói hành động: tách thành `[('reset',), ('activate',), ()]` hoặc gộp thành `[('reset', 'activate')]` trên cùng một sổ cái nỗ lực; không chấm điểm nỗ lực lần thứ hai cho gói gộp.
5. Khai báo khoảng chặn xác suất mô phỏng cho tiền tố `('reset',)` là $[0.8, 0.9]$ và cho tiền tố `('reset', 'activate')` là $[0.6, 0.7]$; tính tay khoảng bao đóng tích lũy $[0.48, 0.63]$.
6. Sử dụng hàm `assess_scoped_program()` để đối chiếu kết quả; thử chỉ khai báo xác suất biên cho `('activate',)` để kiểm chứng việc thiếu tiền tố đầy đủ sẽ khiến toàn bộ xác suất nhận giá trị `None` và được gán lý do chẩn đoán `likelihood_unrated`.
7. Thử nghiệm thay thế một bước bao đóng rỗng bằng ba bước bao đóng rỗng liên tiếp; kiểm chứng rằng tổng nỗ lực, khoảng xác suất và ngân sách vẫn giữ nguyên, không bị suy giảm theo số lượng gói hành động.
8. Chạy Thí nghiệm 6 và quan sát 8 chương trình tấn công được sinh ra tại ngân sách bằng 4 cùng đường biên Pareto của hai oracle; hạ ngân sách xuống 3 để thấy hệ thống báo cờ cắt cụt (`truncated = True`) và loại bỏ hai chuỗi chia sẻ thứ tự.

Các nguyên tắc bổ trợ cần lưu ý:
- Các khoảng chặn xác suất do người thiết kế fixture chủ động đặt để kiểm thử thuật toán, không lấy từ dữ liệu SEAMLESS hay tài liệu Microsoft.
- Khi áp dụng trên cặp nguồn và đích khác nhau, định danh đơn vị công việc trong sổ cái bắt buộc phải gắn liền với thực thể mới; không được gộp chi phí chuẩn bị chỉ vì trùng tên kỹ thuật.
- Quy luật xác suất có điều kiện của một tiền tố không áp dụng cho tiền tố khác; script luôn tra cứu theo toàn bộ lịch sử hành động có thứ tự.
- Khi không có căn cứ xác thực cho khoảng chặn xác suất, hệ thống ghi nhận lý do loại trừ chẩn đoán `likelihood_unrated` (`likelihood_interval = None`) và không xuất thứ hạng rủi ro dự báo; đặc tả nỗ lực có điều kiện vẫn có thể được kiểm toán riêng.
- Một tiền tố thành công có chặn trên xác suất bằng 0 là đủ để chứng minh toàn bộ chuỗi có xác suất bằng 0, không cần thu thập thêm dữ liệu điều kiện cho các bước sau.
- Hàm hỗ trợ sử dụng lớp `Fraction` để duy trì tính đẳng thức và quan hệ bao đóng chính xác; file JSON kết quả lưu trữ chuỗi số hữu tỉ (như `'81/125'`), cho phép đọc lại trực tiếp bằng `Fraction(value)` thay vì làm tròn số học.
- Nếu một đơn vị công việc có mặt trong sổ cái nhưng giá trị nỗ lực là `None` (chưa giải quyết xong định mức hoặc sự chồng lấn), toàn bộ nỗ lực của chương trình sẽ nhận giá trị `None`; không lấy tổng từng phần làm đại diện cho tổng nỗ lực.
- Khi hai ứng viên có cùng mức tác động và cùng điểm xác suất, hòa điểm chỉ được giải quyết bằng nỗ lực nếu cả hai đều có nỗ lực hợp lệ; nếu không, hai ứng viên giữ trạng thái không so sánh được (`incomparable`).
- Thí nghiệm 6 cung cấp fixture dữ kiện hỗn hợp để kiểm tra phân vùng chẩn đoán và cơ chế xử lý hòa điểm khi thiếu nỗ lực qua CLI.
- Hàm `bounded_programs()` chuẩn hóa các lộ trình có cùng chuỗi đơn vị công việc có thứ tự; khi tích hợp vào sản phẩm, hệ thống bắt buộc phải lưu vết cấu trúc và bằng chứng riêng biệt để phục vụ kiểm toán, truy xuất nguồn gốc và đối chứng điểm nghẽn với BloodHound.

### Ranh giới bàn giao dữ liệu và logic cho TTS B sau quyết định chính thức

TTS A có trách nhiệm cung cấp query/version, dữ kiện ban đầu kèm danh sách chẩn đoán phủ định (`False`) và chưa rõ (`Unknown`), ràng buộc thực thể của hành động kèm tiền đề và hiệu ứng, danh mục đơn vị công việc trong sổ cái cùng nguồn gốc định mức, và khoảng chặn xác suất theo tiền tố có điều kiện cùng nguồn gốc đánh giá tác động.
Kết quả đầu ra của module đánh giá phải bảo toàn chuỗi hành động và lịch sử, nỗ lực danh định và nỗ lực đủ điều kiện, khoảng chặn xác suất hoặc lý do chưa đánh giá, thứ tự ưu tiên rủi ro hoặc kết luận không so sánh được, cùng thông tin chẩn đoán về ngân sách và độ bao phủ.
Đây là nội dung giao diện **đề xuất nghiên cứu**, chưa tự ý thay đổi file cấu hình `configs/contract.yml`, catalog tấn công hay mã nguồn engine hiện hành.
TTS B không được tiếp nhận các con số trong các fixture thử nghiệm này như là các trọng số sản phẩm chính thức.
Không được giả định trạng thái đồ thị chỉ gồm bộ đôi `(node, accumulated_active_steps)`; dữ kiện và lịch sử điều kiện có thể khác nhau dù nút đích và số bước bằng nhau.
Chỉ số nỗ lực tối thiểu tới Domain Admins (S2 min-effort-to-DA) là một luồng đầu ra độc lập trên cùng ngữ nghĩa, mục tiêu, cổng kiểm soát và sổ cái nỗ lực; chỉ số này không bị thay thế bởi phương án thắng giải trên đường biên Pareto.
Các yêu cầu so sánh điểm nghẽn với BloodHound và kiểm thử hiệu năng tìm kiếm cần có quy trình nghiệm thu độc lập; việc CI vượt qua kiểm thử không đồng nghĩa với việc các cổng kiểm chuẩn đó đã được nghiệm thu.
Trình tự làm việc hiện hành của dự án: Testbed #142 đã hoàn tất -> Hiệu chỉnh mô hình #150 và merge PR #151 -> Ban hành successor ADR và giao diện bàn giao tại #143 -> Khảo sát bộ tham số và kiểm chuẩn thực nghiệm -> TTS B tích hợp vào engine tìm đường.
Việc reviewer phê duyệt đề xuất nghiên cứu có phạm vi hẹp không làm thay đổi kết luận: bài toán xếp hạng dự báo trên snapshot SEAMLESS hiện tại vẫn giữ kết luận **Insufficient Evidence** (Chưa đủ bằng chứng).
Để tái lập và kiểm chứng các kết quả nghiên cứu, người đọc thực hiện theo các hướng dẫn trong [báo cáo kiểm chứng mục 0.6](path-ranking-validation.md) và tham khảo nhật ký làm việc tương ứng.

---

## Bằng chứng lịch sử Phase A (2026-09-28)

### Trạng thái và mục đích nghiên cứu

Nghiên cứu cho [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), bổ sung bằng chứng Phase A cho [weighting direction](weighting-direction.md).
Tài liệu được tổng hợp ngày 2026-09-28 từ phiên làm việc ngày 26, 27 và 28/9, có AI hỗ trợ đọc code, tạo script và diễn giải.
Các giả thuyết và kết quả dưới đây chưa phải mentor sign-off, production weights, quyết định ADR hay nghiệm thu toàn bộ #42.
Audit semantics dựa trên `develop` tại `a0f84d66959247767af242fcdf5303d98489f4a2`; đóng gói trên `86261cb804b36ca6dfc7839576b68ae058a1e55f`, đã gồm parser demo của PR #129.
Hai probe độc lập phục vụ nghiên cứu, không thay parser/engine thuộc phạm vi B.

Mục tiêu thực tế: kiểm tra liệu đường đi nhìn thấy trong dữ liệu có đủ ý nghĩa để chấm cost hay chưa, và giữ lại cách suy ra kết luận để người thực hiện tự chạy, sửa và giải thích được.

### Báo cáo kỹ thuật: phân tích thủ công kết hợp kiểm chứng bằng hàm

Có cả hai: đọc tài liệu/code và chọn giả thuyết là phần phân tích; kiểm tra dữ liệu, tìm đường và đối chiếu kết quả được thực hiện bằng hàm Python.
Không dùng mô hình AI để tự gán số production rồi coi đó là kết quả đo.

| Công đoạn | Cách thực hiện | Đầu ra kiểm tra được |
| --- | --- | --- |
| Đọc semantics | Đọc catalog, hàm đánh giá/apply và test; đối chiếu tài liệu chính thức | Phân biệt control, authentication, material, session và admin |
| Đặt câu hỏi | Thiết kế thủ công 15 tình huống và tính đáp án nhỏ | Đáp án nằm cạnh fixture trong `semantics_probe.py` |
| Tìm cost nhỏ nhất | `solve()` dùng uniform-cost search trên tập fact tích lũy | Cost và chuỗi action cho từng tình huống |
| Kiểm tra lại phép tìm kiếm | `exhaustive_cost()` duyệt mọi chuỗi làm tăng state trên fixture nhỏ | So sánh với đáp án tính tay; dùng chung specification nên không phải oracle AD độc lập |
| So sánh mô hình đơn giản | `capability_graph_cost()` làm AND reachability closure rồi Dijkstra trên fact node trong phạm vi được hỗ trợ | 14 ca khớp, một ca trả `unsupported` |
| Xác thực input | `read_verified()` kiểm tra kích thước byte và SHA-256 | Ba file đúng manifest trước khi parse JSON |
| Trích quan hệ | `build_projection()` dùng dictionary/set và giữ raw locator | Hướng quan hệ, evidence và số endpoint bị bỏ qua |
| Tìm ứng viên trực tiếp | `find_direct_candidates()` nối Computer, ACL, User và membership của group đích | Ứng viên thuần cấu trúc; enabled facts của cả hai đầu được xuất riêng |
| Tìm đường cấu trúc | `shortest_hops()` dùng BFS, hàng đợi và visited set | Đường ít hop nhất; không phải đường tấn công đã khả thi |
| Diễn giải insight | Đối chiếu kết quả script với điều kiện hành động và mục tiêu scenario | Kết luận có giới hạn, các assumption cần review |

Đọc script theo thứ tự: dữ liệu vào, cấu trúc trung gian, thuật toán, assertion, rồi JSON đầu ra.
Muốn đổi một giả thuyết, hãy sửa fixture và đáp án tính tay trước, chạy lại, sau đó kiểm tra liệu kết luận còn giữ được không.
Với dữ liệu raw, phải kiểm tra locator của cạnh trong input đã xác thực trước khi gán một ý nghĩa hành động cho cạnh đó.

### Liên kết với quy trình nghiên cứu tổng thể

| Giai đoạn | Vai trò | Liên hệ với phần này |
| --- | --- | --- |
| Week 1: manifest và EDA | Biết nguồn, định dạng, phạm vi và giới hạn snapshot | Probe kiểm tra ba input theo manifest; thống kê không tự trở thành bằng chứng khả thi |
| Week 2: canonical parser | Chuẩn hóa identity, hướng, reconciliation và provenance | Probe dùng raw projection hẹp, không thay contract canonical |
| Week 2: attack semantics | Xác định prerequisite, effect và state | Phân biệt quyền có trong snapshot với hành động có thể thực hiện |
| Week 3: weighting | Chọn cost ownership, construct và rubric | Dùng fixture để kiểm tra phép cộng và baseline trước khi rating |
| Week 4: search | Tìm đường trên mô hình đã thống nhất | Chỉ chọn thuật toán production sau khi biết cần biểu diễn state nào |
| Week 5: evaluation | Đo đúng đắn, sensitivity, hiệu năng và remediation | Probe chưa chứng minh scalability, parity hoặc hiệu quả can thiệp |

### Các kết quả đã được kiểm chứng trong prototype

[Semantics probe](../../scripts/research/semantics_probe.py) có 15/15 ca khớp đáp án tính tay và exhaustive search.
Fact và cost đều là giả lập; các số dưới đây không phải xác suất, thời gian thực hay mức khó đã hiệu chỉnh.

- Đổi actor cần một cầu nối authentication rõ ràng: fixture reset rồi truy cập admin có cost `2 + 3 = 5`.
- Thiếu điều kiện authentication hoặc bằng chứng reset thì mục tiêu bị chặn trong fixture.
- RDP tạo interactive session có cost 3 trong fixture, không tự đạt mục tiêu admin.
- Credential material chưa được xác định loại không tự trở thành password dùng được.
- Chuẩn bị chung cho hai điều kiện AND có cost `3 + 2 + 2 + 1 = 8`; cộng hai nhánh độc lập sẽ đếm chuẩn bị hai lần và ra 11.
- Membership trực tiếp và lồng nhau cùng cost 4 khi truyền entitlement là closure thụ động cost 0; vòng closure không làm search lặp vô hạn.
- Weighted chọn hai action `2 + 2 = 4`, trong khi baseline đếm action chọn một action trực tiếp; đây là fixture được thiết kế để kiểm tra ranking, không phải phát hiện trên SEAMLESS.

Projection đơn giản hỗ trợ và khớp 14/15 ca, từ chối ca AND có chuẩn bị chung.
Nó chỉ nhận action có tối đa một prerequisite chưa đúng ở initial state và đúng một effect sau bước lọc reachability.
`Unsupported` khác với `no path`; 14/15 không phải coverage dữ liệu hay độ chính xác production.
Kết quả không chứng minh mọi graph đơn giản đều thất bại, cũng không chứng minh cần xây ngay một full state-space planner.
Các mô hình đều đang giả định context cố định, quyền tích lũy, cost cố định không âm và không có delete effect hoặc expiry.

### Kiểm tra mã nguồn hiện có

State hiện phân biệt chín tập: `control`, `effective_member`, `permission`, `admin_control`, `interactive_session`, `remote_command_execution`, `credential_material`, `authentication_control` và `relationship_added`.
Hàm đánh giá yêu cầu tất cả prerequisite; `actor_controlled` kiểm tra actor trong `control`.
`apply` tích lũy effect và membership closure có chống vòng lặp.
`authentication_control` và `credential_material` không tự nâng thành actor `control`; material reuse được để lại cho bước thiết kế tiếp theo.

Đây là khoảng trống cần thiết kế cho composition nhiều hành động, chưa phải bằng chứng implementation hiện tại sai contract.
Code hiện đã phân biệt RDP/WinRM với admin và kiểm tra các điều kiện riêng của HasSession.
Một chuỗi WriteDacl, GenericAll rồi reset có thể tạo effect trong mô hình hiện có nhưng chưa tự chứng minh actor mới đăng nhập được và hoàn tất mục tiêu tiếp theo.
Không dùng một numeric penalty để lấp khoảng trống semantics đó.

### Khảo sát dữ liệu thô và nhận diện ứng viên kịch bản

[Raw path probe](../../scripts/research/raw_path_probe.py) đã chạy trên ba file computers/groups/users được đối chiếu kích thước và SHA-256 với manifest `seamless-raw-v1.json`.
Probe không kiểm tra toàn bộ sáu file và không tự tính lại snapshot ID; ID trong output là khai báo từ manifest.
Projection chỉ giữ User/Group/Computer, MemberOf và GenericAll/WriteDacl có target User hoặc Group.
Nó không thực hiện đầy đủ SID normalization, inheritance, access check hay reconciliation canonical.

Kết quả aggregate của lần chạy ngày 28/9:

| Quan sát | Kết quả | Giới hạn |
| --- | --- | --- |
| Projection được chọn | 3.142 node, 51.288 cạnh phân biệt | Không phải tổng canonical graph |
| Reference thiếu endpoint bị bỏ qua | 2 occurrence | Không được chuyển thành một quyền suy đoán |
| Computer GenericAll tới User thuộc trực tiếp group DA | 5 cặp, từ 2 computer tới 4 user | Discovery không lọc enabled; cả source và target của 5 cặp này có observed enabled=true |
| Source A tới group đích | 2 hop | Một ACL và một membership |
| Source A khi bỏ cạnh đầu của đường vừa tìm | 4 hop | Một đường thay thế tránh cạnh đó, không phải Top-K |
| Source B khi bỏ cạnh đầu | Vẫn có đường 2 hop | Không chứng minh thứ hạng weighted thay đổi |

Tên source và user được thay bằng alias trong tài liệu; output chứa identity và locator chỉ giữ ở vùng ignored theo chính sách dữ liệu của repo.
`Group.Members` được đọc theo hướng member tới group.
ACE nằm trên record target T cho quan hệ principal tới T, không phải T tới principal.
Các occurrence trùng cạnh vẫn giữ đủ locator.
BFS sắp thứ tự cạnh để tie-break ổn định và dùng visited set để chống cycle.
Chạy lại BFS bỏ một cạnh không tái dựng quyền suy diễn, nên không được gọi là thí nghiệm remediation.

Nếu chỉ tính reset với cùng một cost dương `c` và membership là closure cost 0, ứng viên trực tiếp có cost `c`, ứng viên hai reset có cost `2c` trong abstraction đó.
Ví dụ này không tạo ra ranking reversal.
Không tự gán cost khác nhau chỉ để làm biểu đồ weighted trông khác shortest-hop.

### Các yếu tố kịch bản cần thống nhất trước khi tính chi phí

| Thành phần | Bằng chứng hoặc giả định | Cách xử lý |
| --- | --- | --- |
| Foothold | Candidate: LocalSystem trên một domain member, không phải DC | Giả định scenario cần duyệt; không suy ra SYSTEM chỉ từ admin |
| Network identity | Microsoft mô tả LocalSystem trên domain member dùng computer account khi truy cập mạng | Cần nối điều này với action/context cụ thể; không suy ra domain admin |
| Structural permission | ACL và membership trong snapshot | Chỉ là evidence ứng viên; cần semantics và effective access phù hợp |
| Source/target account | `enabled_facts` ghi riêng trạng thái và raw locator cho cả hai đầu | Không lọc structural candidates; enabled không đủ chứng minh applicability |
| Runtime predicates | Snapshot chưa đủ service, reachability, policy và freshness | Unknown không cho traverse; giữ lý do unknown, không gán penalty thay gating |
| Goal | Khả năng thực hiện hành động đặc quyền đã định nghĩa | Chạm node group DA không tự là đạt mục tiêu |
| Cost boundary | Candidate: bắt đầu sau foothold | Phải công bố phần chuẩn bị nào nằm ngoài phép đo |

Audit snapshot trước đó thấy HasSession bằng 0 và thiếu groupType; không suy ra security group chỉ từ tên có chữ ADMINGROUP hay DISTLIST.
Các reference RDP/AdminTo/WinRM thưa không cung cấp đầy đủ allow/deny, service hoặc runtime context.
Catalog có 10 technique cần ít nhất một điều kiện ngoài raw evidence; context rỗng không đủ cho action applicability.
Các quan sát audit này không phải output được tái tạo bởi raw path probe hẹp bên trên.

### Đánh giá các phương án phân định chi phí và mô hình đối chứng

| Phương án | Điểm cần kiểm tra trước khi chọn |
| --- | --- |
| Cost gắn relationship | Một GenericAll có thể hỗ trợ nhiều technique và target kind; một số duy nhất che khuất khác biệt |
| Cost gắn transition | Tách được reset, thêm member hoặc sửa ACL; vẫn phải định nghĩa construct và cách cộng |
| Transition cộng context | Có thể diễn đạt cản trở theo scenario; phải tránh đếm đôi và trộn applicability vào cost |

Transition là ứng viên đáng thử, chưa được chọn thay các phương án còn lại.
Gating phải diễn ra trước tính cost; không dùng cost lớn để giả vờ một action thiếu điều kiện vẫn khả thi.
Baseline đếm action phải dùng cùng action set, goal và gating với weighted, action thực cost 1 và closure thụ động cost 0 trong prototype này.
Structural hop baseline đếm mọi quan hệ là 1 có ý nghĩa khác; không thay đổi ngầm profile `unit` hiện có của repo.
`maut_v1` là bối cảnh lịch sử, không được thăng thành production bằng các kết quả này.

### Hướng dẫn tái lập và kiểm chứng

Từ root repo, không cần package bên ngoài cho hai probe và bộ test này:

```bash
python scripts/research/semantics_probe.py
python -m unittest discover -s tests -p test_research_probes.py -v
mkdir -p reports/generated
python scripts/research/raw_path_probe.py \
  --raw-dir data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --discover \
  > reports/generated/week3-raw-probe.json
```

Cần ba file raw đúng manifest tại đường dẫn đã chọn; không commit input hoặc JSON output có identity.
`--discover` không cần biết trước source/target ID.
Sau khi xác thực ba input, tool chọn target là Group duy nhất có domain SID dạng `S-1-5-21-a-b-c-512`, với a/b/c là các thành phần số.
RID 512 xác định Domain Admins theo [Microsoft Security Identifiers](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-identifiers); quy tắc này chỉ chọn identity, không xác nhận membership usable hoặc runtime quyền.
Nếu không có hoặc có nhiều target khớp, tool dừng và yêu cầu `--target`; không chọn âm thầm theo tên hay thứ tự file.
Lấy tất cả Computer source của direct structural candidates, loại ID trùng và sắp raw ID tăng dần theo thứ tự từ điển Python.
Source đầu là `Source A`, source thứ hai là `Source B`, tiếp theo là `Source 3`, `Source 4`, ...; không sắp theo tên hoặc enabled.
Output `selection` ghi quy tắc, `sources` ghi alias/rank/ID và hai đường BFS cho từng source.
Trên snapshot pinned, quy tắc tái tạo đúng Source A có 2/4 hop và Source B có 2/2 hop; đường và locator Source A khớp output lịch sử.
Alias chỉ ổn định theo quy tắc trên tập candidate của cùng snapshot; thay snapshot có thể đổi alias.

Mode cũ vẫn dùng được với `--source` và `--target`; `--discover --target '<group-id>'` cho phép chọn target rõ khi ambiguous.
`--discover` không nhận cùng `--source`.
Không có direct candidate thì output count 0 và `sources: []`.

Research JSON hiện là `format_version: 2`: key count đổi từ `direct_computer_to_enabled_target_member_count` sang `direct_computer_to_target_member_count` để phản ánh structural-only discovery.
Mỗi candidate có `enabled_facts.source` và `enabled_facts.target_user`, gồm status và mọi observation với file, pointer tới Properties, field `enabled` và cờ `present`.
Thiếu/không đúng kiểu boolean được ghi unknown; observed true/false trái nhau được ghi conflicting; mọi trường hợp đều giữ structural candidate.
Đây không phải thay đổi Graph Contract hoặc kết luận reset applicable.
Tests dùng identity giả, kiểm tra hướng/locator, tách enabled facts, evidence trùng, endpoint thiếu, conflict, cycle, đường thay thế và từ chối input bị thay đổi cùng độ dài.
Checkpoint đầu có 5 test đạt, gồm toàn bộ 15 ca semantics.
Phần [scenario contract tiếp nối](week3-scenario-contract.md) bổ sung handoff, scoped goal và truth table; checkpoint scenario có 12 test research đạt local trên Python 3.12.14.
[Đợt kiểm tra Phase A tiếp nối](week3-cost-ownership-comparison.md) bổ sung ba counterexample, nâng checkpoint Phase A lên 15 test.
Sau xử lý review, tổng hiện tại là 20 test với CLI discovery E2E, alias khi đổi thứ tự record/ACE, target missing/ambiguous, enabled hai đầu và hash mismatch.
Python 3.14 theo CI của repo vẫn là gate trước merge.
Ruff check/format áp dụng cho các Python file mới; không coi test research là nghiệm thu toàn bộ parser/engine.

### Kế hoạch tiếp nối và các điểm nợ tài liệu

1. Review scenario: initial capability, actor handoff, goal và danh sách runtime assumptions được phép dùng.
2. Review cost ownership, construct, rubric và baseline; chỉ sau đó mới independent rating/reconciliation.
3. Chạy sensitivity trên cùng mô hình khả thi, ghi cả trường hợp ranking không đổi; đo scale trước khi chọn search production.

Ví dụ đường 11 hop trong tài liệu representativeness cần được rà lại trước khi dùng làm executable demo: GenericAll tới Computer hiện không tự cho host control trong catalog.
Đính chính ngày 28/9 sau khi đối chiếu lại [dataset representativeness](dataset-representativeness.md): chênh lệch 66.374 raw references và 66.371 EDA entries đã được giải thích bởi 3 raw RDU-only references không đủ tạo verified CanRDP.
Đây không phải nợ count chưa giải quyết; raw path probe không tính canonical count.
Điểm còn cần rà là diễn giải executable của ví dụ 11 hop, không phải phần giải thích chênh lệch count.

### Tài liệu tham khảo và giới hạn áp dụng

- [Microsoft: LocalSystem account trong AD](https://learn.microsoft.com/en-us/windows/win32/ad/the-localsystem-account) và [LocalSystem service account](https://learn.microsoft.com/en-us/windows/win32/services/localsystem-account): ngữ cảnh identity trên mạng, không xác nhận chuỗi cụ thể của snapshot.
- [SpecterOps: ForceChangePassword](https://bloodhound.specterops.io/resources/edges/force-change-password): ý nghĩa quyền reset và điều kiện sử dụng.
- [SpecterOps: CanRDP](https://bloodhound.specterops.io/resources/edges/can-rdp), [HasSession](https://bloodhound.specterops.io/resources/edges/has-session), [AdminTo](https://bloodhound.specterops.io/resources/edges/admin-to): phân biệt session, credential access và quyền admin.
- [MulVAL, USENIX Security 2005](https://static.usenix.org/publications/library/proceedings/sec05/tech/full_papers/ou/ou_html/index.html): tham khảo suy diễn điều kiện logic; không dùng làm chứng minh phép cộng min-cost của prototype.

Các nguồn hỗ trợ diễn giải semantics, không cung cấp integer cost trong fixture và không xác thực runtime state của dữ liệu.

## Luồng phân tích End-to-End: Từ dữ liệu thô tới xếp hạng đường tấn công

Để phục vụ công tác bàn giao và giải trình bảo vệ, quy trình phân tích và xếp hạng đường tấn công được chuẩn hóa thành 7 giai đoạn liên hoàn:

```text
┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│ 1. Dữ liệu thô (Raw)   ├─────►│ 2. Cấu trúc chuẩn tắc  ├─────►│ 3. Ngữ nghĩa tấn công  │
│ (Active Directory AD)  │      │ (Canonical Multigraph) │      │ (Attack Semantics)     │
└────────────────────────┘      └────────────────────────┘      └───────────┬────────────┘
                                                                            │
┌────────────────────────┐      ┌────────────────────────┐      ┌───────────▼────────────┐
│ 6. Xếp hạng Pareto     │◄─────┤ 5. Tính toán số học    │◄─────┤ 4. Kịch bản & Định mức │
│ (Frontier & Diag)      │      │ (Fraction & Ledger)    │      │ (Scenario Contract)    │
└───────────┬────────────┘      └────────────────────────┘      └────────────────────────┘
            │
            ▼
┌────────────────────────┐
│ 7. Kiểm chứng & Độ nhạy│
│ (Validation & Parity)  │
└────────────────────────┘
```

1. **Dữ liệu thô (Raw Ingest):** Nhận snapshot dữ liệu Active Directory đã ẩn danh; xác thực checksum SHA-256 đối chiếu manifest.
2. **Cấu trúc chuẩn tắc (Canonical Multigraph):** Chuẩn hóa danh tính (SID, GUID), phân giải hướng quan hệ thực tế, bảo toàn đa cạnh song song và vết nguồn gốc (provenance locators).
3. **Ngữ nghĩa tấn công (Attack Semantics):** Ánh xạ cấu trúc sang các kỹ thuật leo thang đặc quyền tương ứng kèm điều kiện tiên quyết, hiệu ứng và cơ chế telemetry.
4. **Kịch bản và định mức (Scenario Contract & Expert Rating):** Xác lập điểm xuất phát (foothold), tài sản đích, phân tầng dữ kiện và thực hiện quy trình định mức chuyên gia độc lập.
5. **Tính toán số học chính xác (Arithmetic & Ledger Composition):** Tính tích khoảng xác suất tiền tố theo quy tắc chuỗi bằng phân số Fraction; tổng hợp nỗ lực trên sổ cái công việc chống đếm trùng.
6. **Xếp hạng Pareto bảo thủ (Conservative Pareto Ranking):** Áp dụng quy tắc ưu thế Pareto trên hai trục tác động và khoảng xác suất; phân giải tie-break nỗ lực trong phạm vi hẹp; phân vùng chẩn đoán các ứng viên chưa đủ điều kiện.
7. **Kiểm chứng và phân tích độ nhạy (Validation & Sensitivity):** Chạy kiểm thử tự động, phân tích độ ổn định của biên Pareto và đối chứng kết quả với đường đi của BloodHound.

### Phân định giữa suy luận thủ công của con người và tự động hóa của script/hàm

Hệ thống phân định rạch ròi trách nhiệm giữa chuyên gia an toàn thông tin và thuật toán tự động:

| Công việc | Con người thực hiện (Thủ công / Định mức) | Script và Hàm thuật toán (Tự động hóa) |
| --- | --- | --- |
| **Xác lập kịch bản** | Lựa chọn tài sản đích phù hợp với bối cảnh nghiệp vụ; khai báo các giả định runtime có lý do kỹ thuật. | Kiểm tra tính hợp lệ cú pháp kịch bản; nạp danh sách giả định vào sổ cái facts. |
| **Đánh giá tác động** | Phân tích thiệt hại vận hành thực tế để chọn mức Low, Medium, High, Critical; giải trình nghiệp vụ. | Kiểm tra tính hợp lệ của thang đo thứ tự; ánh xạ nhãn tác động sang miền so sánh. |
| **Ước lượng xác suất** | Định mức khoảng cận dưới $l$ và cận trên $u$ cho đúng tiền tố chuỗi hành động dựa trên năng lực phòng thủ. | Kiểm tra tính hợp lệ $[l, u] \subset [0, 1]$; nhân chuỗi xác suất chính xác tuyệt đối bằng stdlib `Fraction`. |
| **Định mức nỗ lực** | Chấm điểm độ phức tạp $T_1$ và ma sát $T_2$ theo rubric nghiên cứu; ghi nhận bước chuẩn bị dùng chung. | Tính $C = T_1 + T_2 - 2$; cấp mã định danh chuẩn tắc và lưu vào sổ cái kiên trì; trừ trùng chi phí. |
| **Gating điều kiện** | Cung cấp bằng chứng snapshot hoặc giả thiết runtime. | Kiểm tra vị từ nghiêm ngặt; chặn ứng viên nếu có điều kiện False; gán Unknown nếu thiếu dữ kiện. |
| **Xếp hạng và So sánh** | Phê duyệt chính sách quản trị và xem xét các ca không so sánh được. | So sánh bất đẳng thức Pareto $I_A \ge I_B$ và $l_A \ge u_B$; dựng biên Pareto; xuất chẩn đoán. |

### Ví dụ tính tay mẫu tổng hợp từng bước (Step-by-Step Synthetic Worked Hand Calculation)

Ví dụ dưới đây là một ví dụ mẫu tổng hợp (Synthetic Worked Example) nhằm minh họa chi tiết từng bước tính toán số học, quy tắc nhân khoảng xác suất tiền tố và cơ chế loại trừ ưu thế Pareto bảo thủ.
Các số liệu xác suất và chi phí trong ví dụ này thuần túy là dữ liệu thử nghiệm giải thuật, không phải là tham số vận hành của sản phẩm.

Xét hai chương trình tấn công ứng viên cùng xuất phát từ foothold máy trạm hướng tới tài sản đích Domain Controller (`DC01$`):

- **Chương trình 1 ($P_1$):** Chuỗi 3 hành động: Đổi mật khẩu tài khoản đích ($A_1$) $\to$ Xác thực mạng Kerberos ($A_2$) $\to$ Thực thi lệnh từ xa WinRM ($A_3$).
- **Chương trình 2 ($P_2$):** Chuỗi 2 hành động: Khai thác lỗ hổng dịch vụ từ xa ($B_1$) $\to$ Leo quyền cục bộ ($B_2$).

#### Bước 1: Thu thập đánh giá tác động nghiệp vụ ($I$)
- Cả hai chương trình đều nhắm tới tài sản đích `DC01$` với mục tiêu chiếm quyền kiểm soát hoàn toàn hệ thống định danh.
- Chuyên gia nghiệp vụ định mức mức độ hậu quả:
  $$I(P_1) = \text{Critical}, \quad I(P_2) = \text{Critical}$$

#### Bước 2: Tính toán khoảng xác suất có điều kiện ($P \in [l, u]$)
- Với Chương trình 1, chuyên gia định mức xác suất theo đúng tiền tố chuỗi hành động:
  - Hành động 1 ($A_1$): $[l_1, u_1] = [4/5, 9/10]$
  - Hành động 2 ($A_2 \mid A_1$): $[l_2, u_2] = [3/4, 9/10]$
  - Hành động 3 ($A_3 \mid A_1, A_2$): $[l_3, u_3] = [5/6, 1/1]$
  - Nhân khoảng xác suất toàn bộ chuỗi $P_1$:
    $$l(P_1) = \frac{4}{5} \times \frac{3}{4} \times \frac{5}{6} = \frac{4 \times 3 \times 5}{5 \times 4 \times 6} = \frac{60}{120} = \frac{1}{2} = 0.50$$
    $$u(P_1) = \frac{9}{10} \times \frac{9}{10} \times \frac{1}{1} = \frac{81}{100} = 0.81$$
    $$\implies P(P_1) \in \left[\frac{1}{2}, \frac{81}{100}\right] = [0.50, 0.81]$$

- Với Chương trình 2, chuyên gia định mức xác suất theo tiền tố:
  - Hành động 1 ($B_1$): $[l_1', u_1'] = [1/5, 2/5]$
  - Hành động 2 ($B_2 \mid B_1$): $[l_2', u_2'] = [1/2, 1/2]$
  - Nhân khoảng xác suất toàn bộ chuỗi $P_2$:
    $$l(P_2) = \frac{1}{5} \times \frac{1}{2} = \frac{1}{10} = 0.10$$
    $$u(P_2) = \frac{2}{5} \times \frac{1}{2} = \frac{2}{10} = \frac{1}{5} = 0.20$$
    $$\implies P(P_2) \in \left[\frac{1}{10}, \frac{1}{5}\right] = [0.10, 0.20]$$

#### Bước 3: Tính toán tổng nỗ lực trên sổ cái ($C$)
- Với Chương trình 1:
  - $A_1$: $T_1 = 1, T_2 = 2 \implies C_1 = 1 + 2 - 2 = 1$
  - $A_2$: $T_1 = 2, T_2 = 2 \implies C_2 = 2 + 2 - 2 = 2$
  - $A_3$: $T_1 = 2, T_2 = 3 \implies C_3 = 2 + 3 - 2 = 3$
  - Tổng nỗ lực $C(P_1) = 1 + 2 + 3 = 6$.
- Với Chương trình 2:
  - $B_1$: $T_1 = 2, T_2 = 1 \implies C_1' = 2 + 1 - 2 = 1$
  - $B_2$: $T_1 = 2, T_2 = 2 \implies C_2' = 2 + 2 - 2 = 2$
  - Tổng nỗ lực $C(P_2) = 1 + 2 = 3$.

#### Bước 4: So sánh ưu thế Pareto bảo thủ
- So sánh trên trục tác động: $I(P_1) = \text{Critical} \ge I(P_2) = \text{Critical}$ (Thỏa mãn điều kiện $\ge$).
- So sánh trên trục xác suất thành công:
  - Cận dưới của $P_1$ là $l(P_1) = 1/2 = 0.50$.
  - Cận trên của $P_2$ là $u(P_2) = 1/5 = 0.20$.
  - Ta có bất đẳng thức nghiêm ngặt: $l(P_1) = 0.50 > u(P_2) = 0.20$.
- Kết luận so sánh:
  Vì $I(P_1) \ge I(P_2)$ và $l(P_1) > u(P_2)$, theo đúng định nghĩa Pareto bảo thủ, **$P_1$ ưu thế tuyệt đối trước $P_2$ ($P_1 \succ P_2$)**.
- Kết quả biên Pareto:
  - Biên Pareto chỉ chứa: `[P_1]`.
  - $P_2$ bị loại khỏi biên Pareto dù có nỗ lực nhỏ hơn ($3 < 6$), bởi vì xác suất thành công của $P_2$ kém hơn $P_1$ trên toàn bộ khoảng bất định.
- Kết quả tính tay mẫu tổng hợp này khớp chính xác 100% với giải thuật thực thi trong `path_ranking_wire_adapter.py`, `scripts/research/worked_example_validation.py` và bài kiểm thử chuyên biệt [`test_synthetic_hand_worked_example_in_brief()`](../../tests/test_path_ranking_interface.py).
