# Đề xuất xếp hạng đường tấn công theo nguyên lý Pareto bảo thủ

Trạng thái: **Đề xuất nghiên cứu có phạm vi hẹp đã được phê duyệt (Proposal Approved) - Chưa đủ bằng chứng thực nghiệm trên SEAMLESS (Insufficient Evidence)**.
Tác giả: Nhóm TTS A (@Lolavine777), ngày 2026-09-30.
Mã theo dõi: Issue [#150](https://github.com/nairyuuu/ad-weighted-graph/issues/150), Issue [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), Pull Request [#151](https://github.com/nairyuuu/ad-weighted-graph/pull/151).
Tài liệu liên quan: [Báo cáo kiểm chứng thực nghiệm](path-ranking-validation.md), [Bản tóm tắt kịch bản và bằng chứng chi phí](week3-scenario-cost-evidence.md), [Hợp đồng kịch bản tuần 3](week3-scenario-contract.md).

Tài liệu này trình bày đề xuất mô hình xếp hạng đường tấn công được thẩm định và phê duyệt ở phạm vi nghiên cứu mẫu thử (research prototype) trong PR #151.
Phê duyệt trong PR #151 chấp thuận đề xuất nghiên cứu có phạm vi hẹp làm cơ sở phân tích ban đầu, không đưa ra bảo đảm tổng quát cho mọi nguồn dữ liệu, quy mô hay thuật toán tìm kiếm sản phẩm.
Kết luận đối với bài toán xếp hạng dự báo trên dữ liệu thực tế SEAMLESS vẫn giữ nguyên ở mức **Chưa đủ bằng chứng (Insufficient Evidence)**.
Việc xác định bộ tham số sản phẩm, kiểm chuẩn thực nghiệm quy mô lớn và tích hợp engine chính thức thuộc về các cổng kiểm chuẩn độc lập tại Issue #143 và Milestone M3 do TTS B phụ trách.

---

## 1. Tổng quan qua ví dụ xuyên suốt

Để giúp người đọc dễ tiếp cận trước khi đi vào công thức toán học, phần này giải thích toàn bộ quy trình xếp hạng qua một ví dụ cụ thể xuyên suốt tài liệu.

### 1.1. Dữ liệu quan sát được trong snapshot
Giả sử trên snapshot dữ liệu Active Directory, bộ phân tích quan sát được hai cạnh quan hệ cấu trúc:
- Máy trạm `Computer-A` có quyền kiểm soát `GenericAll` tới tài khoản người dùng `User-Target`.
- Tài khoản `User-Target` là thành viên `MemberOf` của nhóm quản trị `Group-DA` (Domain Admins).
Đồng thời, mảng phiên làm việc `Computer.Sessions[]` trên máy trạm này hoàn toàn rỗng.
Các cạnh trên chỉ là dữ kiện tĩnh trong cơ sở dữ liệu.
Chúng cho thấy có mối liên hệ cấu trúc, nhưng chưa chứng minh kẻ tấn công đang đứng tại `Computer-A` có thể tự động biến các quyền đó thành một chuỗi leo quyền thực thi được.

### 1.2. Điều kiện vận hành và giả định kịch bản
Để biến quyền `GenericAll` thành việc kiểm soát danh tính và sử dụng được quyền hạn của `User-Target`, kịch bản khai thác cần thực hiện hai bước:
1. Đặt lại mật khẩu của `User-Target` (hành động `reset`).
2. Xác thực để có danh tính và quyền nhóm sử dụng được trong ngữ cảnh đã chọn (hành động `activate`).
Cần nhấn mạnh rằng hành động `activate` ở đây là một giả định kịch bản để có danh tính sử dụng được (`usable_identity`), không mặc nhiên là mở phiên làm việc mới và không tự tạo ra quan hệ `HasSession` trong dữ liệu quan sát.
Các hành động này phụ thuộc vào các điều kiện vận hành trong thực tế:
- Nếu dịch vụ hoặc kết nối mạng bị chặn hoàn toàn, dữ kiện được đánh dấu là `False`.
  Theo nguyên tắc phủ quyết (Negative Veto), đường tấn công này nhận trạng thái bị chặn (`blocked`) và khoảng xác suất là `None`, bị đưa vào danh mục chẩn đoán.
- Nếu dữ liệu snapshot không ghi nhận thông tin về dịch vụ hoặc chính sách (ví dụ chưa rõ cổng mạng có mở hay không), dữ kiện được giữ ở trạng thái chưa rõ (`unknown`).
- Tuyệt đối không được gán một mức chi phí phạt tùy tiện để ép một bước thiếu điều kiện trở thành khả thi.

### 1.3. Chuỗi hành động và sổ cái nỗ lực
Chương trình tấn công được biểu diễn bằng chuỗi các đơn vị công việc chuẩn tắc có thứ tự.
Kẻ tấn công thực hiện hai hành động `reset` và `activate`.
Trong sổ cái nỗ lực (work ledger), hai hành động này được gán các định danh đơn vị công việc tương ứng là `prep_reset` và `prep_activate`:
- Các định danh này đại diện cho đơn vị công việc gắn liền với thực thể cụ thể, không phải là các hành động chuẩn bị bổ sung phát sinh ngoài kịch bản.
- Mỗi đơn vị công việc chỉ được tính chi phí một lần duy nhất, tránh việc đếm trùng nỗ lực khi nhiều bước dùng chung một tiền đề.
- Bước kế thừa quyền qua quan hệ thành viên nhóm `MemberOf` thụ động trong kịch bản không đòi hỏi nỗ lực hành động của kẻ tấn công, được tính chi phí chuyển tiếp bằng 0 ($C_{\text{closure}} \equiv 0$).

### 1.4. Khả năng thành công và nỗ lực
Xác suất thành công của cả chuỗi không được tính bằng cách nhân các xác suất biên độc lập $P(A) \times P(B)$.
Lý do là bước sau phụ thuộc trực tiếp vào việc bước trước đã hoàn thành.
Gọi $F$ là điểm bàn đạp ban đầu, $S$ là kịch bản cố định, và $E_i$ là biến cố bước thứ $i$ thành công.
Mô hình sử dụng khoảng chặn xác suất có điều kiện theo toàn bộ tiền tố các bước đã thành công trước đó:
- Biến cố bước 1 (`reset`) thành công có khoảng xác suất $P(E_1 \mid F, S) \in [0.8, 0.9]$.
- Biến cố bước 2 (`activate`) thành công sau khi bước 1 đã xong có khoảng xác suất $P(E_2 \mid F, S, E_1) \in [0.6, 0.7]$.
- Khoảng xác suất tích lũy của toàn chuỗi là tích các khoảng chặn $[0.8 \times 0.6, 0.9 \times 0.7] = [0.48, 0.63]$.
Nếu thiếu khoảng chặn có điều kiện cho một tiền tố, toàn bộ xác suất nhận giá trị `None` và được gắn lý do chẩn đoán `likelihood_unrated`, không tự điền một con số mặc định.

### 1.5. So sánh hai đường theo nguyên lý Pareto bảo thủ
Xét hai đường tấn công ứng viên hợp lệ:
- **Đường 1**: Hướng tới tài sản có mức tác động nghiệp vụ `High`, khoảng xác suất thành công là $[0.7, 0.8]$.
- **Đường 2**: Hướng tới tài sản có mức tác động nghiệp vụ `Critical`, nhưng khoảng xác suất thành công chỉ là $[0.3, 0.5]$.
Vì Đường 2 có tác động cao hơn nhưng xác suất lại thấp hơn Đường 1, hai đường này rơi vào thế đánh đổi (trade-off) và không thể lấn át lẫn nhau.
Hai đường được đánh dấu là không so sánh được (`incomparable`), và cả hai đều được giữ lại trên đường biên Pareto (`frontier`).
Đường biên Pareto chứa các ứng viên đủ điều kiện mà không bị bất kỳ ứng viên đủ điều kiện nào khác lấn át.
Nỗ lực tấn công chỉ đóng vai trò phân giải hòa điểm khi hai đường có cùng mức tác động và cùng một điểm xác suất chính xác.
Các ứng viên bị chặn (`blocked`), chưa rõ điều kiện (`unknown`), thiếu khoảng xác suất (`likelihood_unrated`), hoặc thiếu đánh giá tác động (`impact_unrated`) bị coi là không đủ điều kiện và chuyển sang danh mục chẩn đoán (`diagnostics`), không được xuất hiện trên đường biên Pareto.

### 1.6. Điều chưa đủ bằng chứng trên SEAMLESS
Toàn bộ các con số định mức và khoảng xác suất trong ví dụ trên là số liệu mô phỏng do người thiết kế kịch bản đặt ra để kiểm thử tính đúng đắn của logic thuật toán.
Dữ liệu SEAMLESS thực tế chưa có các tham số này, và chưa có đủ bằng chứng thực nghiệm để khẳng định thứ hạng dự báo phản ánh đúng rủi ro trong môi trường thật.

---

## 2. Phạm vi áp dụng và mô hình toán học

### 2.1. Đánh giá tác động độc lập với nhãn kiểm soát kỹ thuật
Mức độ tác động (`Impact`) phản ánh hậu quả đối với hoạt động nghiệp vụ nếu mục tiêu của đường tấn công bị xâm nhập thành công.
Mô hình sử dụng 4 mức định tính mang thang đo thứ bậc:
$$\text{Low} < \text{Medium} < \text{High} < \text{Critical}$$
Mỗi đánh giá tác động bắt buộc phải đi kèm căn cứ nghiệp vụ (rationale) rõ ràng trong truy vấn kịch bản.
Theo bản thể học định danh (§5 trong `identity-asset-ontology.md`):
- `Tier0` là nhãn phân loại thuộc mặt bằng kiểm soát kỹ thuật (control-plane).
- `CrownJewel` là nhãn định giá trị nghiệp vụ (business-value).
Hai hệ thống nhãn này độc lập với nhau và có thể cùng xuất hiện trên một đối tượng.
Tuyệt đối không sử dụng nhãn kỹ thuật để tự động gán mức tác động nghiệp vụ.
Hệ thống không được tự suy diễn mức `Critical` chỉ vì đích đến là Domain Admins (RID 512) hoặc tài khoản KRBTGT (RID 502).
Nếu một ứng viên thiếu căn cứ đánh giá tác động nghiệp vụ, ứng viên đó nhận giá trị `impact = None`, được gắn lý do loại trừ `impact_unrated` và không đủ điều kiện tham gia đường biên Pareto.

### 2.2. Phạm vi truy vấn và lý do lựa chọn nguyên lý Pareto
Mọi so sánh và xếp hạng trong mô hình chỉ có giá trị trong phạm vi của **cùng một truy vấn (query)** với các yếu tố được cố định:
1. Điểm bàn đạp ban đầu ($F$ - foothold).
2. Kịch bản và phiên bản kịch bản ($S$ - scenario and version).
3. Năng lực giả định của kẻ tấn công (attacker capability).
4. Chân trời thời gian (horizon).
5. Ranh giới đo lường công việc (work boundary).

Các giả định biên quan trọng về động lực mô hình:
- Mỗi ứng viên là một chuỗi hành động kết thúc ngay tại **lần đầu tiên đạt được mục tiêu** (first-time goal reach).
- Dữ kiện và sự chuẩn bị tích lũy đơn điệu trong phạm vi truy vấn (monotone facts and preparation).
- Mô hình hiện tại **chưa hỗ trợ** các động lực phức tạp: cơ chế thử lại (retries), sự hết hạn của phiên hoặc quyền (expiry), hiệu ứng thu hồi hoặc xóa quyền (delete effects), hành vi đồng thời (concurrency), hay việc kẻ tấn công tự thích ứng sau thất bại.
- Tuyệt đối không so sánh chéo giữa hai truy vấn có kịch bản hoặc phạm vi công việc khác nhau.

Lý do lựa chọn nguyên lý Pareto thay vì các mô hình khác:
- **Không chọn phân cấp từ điển tuyệt đối (Impact-first)**: Cách tiếp cận này luôn ưu tiên tác động trước xác suất, dẫn đến hiện tượng bỏ qua các mối đe dọa có khả năng thành công rất cao nhắm vào các tài sản quan trọng thứ cấp.
- **Không chọn tích số ma trận rủi ro ($I \times P$)**: Các mức tác động định tính chỉ mang thang đo thứ bậc (ordinal), không có thang đo tỷ lệ (ratio scale).
  Phép nhân đại số $I \times P$ thuần túy là chỉ báo phỏng đoán (heuristic), không tương đương với tổn thất kỳ vọng toán học ($E[\text{Loss}] = \text{Loss} \times P$).
- **Chọn nguyên lý Pareto bảo thủ**: Giữ nguyên vẹn sự đánh đổi giữa tác động và khả năng thành công, minh bạch hóa độ bất định của khoảng xác suất mà không ngụy tạo các con số vô hướng.
- **Đường biên Pareto không tự nó là lịch ưu tiên khắc phục**: Đường biên Pareto cung cấp tập hợp các phương án không bị lấn át để hỗ trợ phân tích; việc lựa chọn phương án khắc phục cụ thể đòi hỏi quyết định chính sách phòng thủ của tổ chức.

### 2.3. Khả năng thành công theo toàn bộ lịch sử tiền tố ($E_i, F, S$)
Gọi $F$ là điểm bàn đạp ban đầu và $S$ là kịch bản cố định với các giả định đã khai báo.
Với một chuỗi hành động gồm $k$ bước công việc, gọi $E_i$ là biến cố bước công việc thứ $i$ thành công.
Xác suất có điều kiện của bước thứ $i$ được định nghĩa dựa trên toàn bộ tiền tố các bước đã thành công trước đó:
$$q_i = P(E_i \mid F, S, E_1, \dots, E_{i-1})$$
Theo công thức nhân xác suất chuỗi (chain rule), xác suất thành công của toàn bộ chuỗi là:
$$P(\text{success} \mid F, S, \text{program}) = \prod_{i=1}^k q_i$$
Khi mỗi bước có khoảng chặn xác suất có căn cứ $q_i \in [\underline{p}_i, \overline{p}_i]$, khoảng bao đóng (interval enclosure) của toàn chuỗi là:
$$P(\text{success} \mid F, S, \text{program}) \in \left[\prod_{i=1}^k \underline{p}_i, \prod_{i=1}^k \overline{p}_i\right]$$
Phân định rõ hai trường hợp liên quan đến giá trị 0:
1. **Phủ quyết bởi bằng chứng phủ định (Negative Veto)**:
   Khi một điều kiện tiên quyết bắt buộc bị vi phạm (`False`), hàm `assess_scoped_program()` trả về `status = "blocked"` và `likelihood_interval = None`.
   Ứng viên này nhận lý do chẩn đoán `blocked`, không đủ điều kiện tham gia so sánh Pareto (`not_eligible`) và không được cấp một khoảng xác suất $[0, 0]$.
2. **Tiền tố có xác suất bằng 0 ($\overline{p}_i = 0$)**:
   Đối với một chuỗi hành động thỏa mãn điều kiện tiên quyết (`feasible`), nếu một bước thành công có chặn trên xác suất bằng 0, thì toàn chuỗi nhận khoảng xác suất $[0, 0]$ theo phép nhân số học mà không cần thu thập thêm dữ liệu điều kiện cho các bước sau.

Các trường hợp bất định và thiếu dữ kiện khác:
- Nếu điều kiện tiên quyết có trạng thái `Unknown`, chuỗi nhận `status = "unknown"` và `likelihood_interval = None`, đồng thời được gắn lý do chẩn đoán `unknown`.
- Trật tự ưu tiên kiểm soát cổng: $\text{False} > \text{Unknown} > \text{True}$.
- Nếu chuỗi thỏa mãn điều kiện tiên quyết (giữ `status = "feasible"`), nhưng thiếu khoảng xác suất có điều kiện cho bất kỳ tiền tố nào (`likelihood_interval = None`), chuỗi được gắn lý do loại trừ `likelihood_unrated` trong danh mục chẩn đoán và không đủ điều kiện xếp hạng rủi ro.

### 2.4. Sổ cái nỗ lực và quy tắc chuyển tiếp thụ động miễn phí
Để tránh đếm trùng chi phí khi nhiều hành động dùng chung bước chuẩn bị, mô hình quản lý nỗ lực qua sổ cái công việc chuẩn tắc.
Mỗi đơn vị công việc chuẩn bị $u$ có định danh duy nhất gắn với thực thể nguồn, đích và kỹ thuật (ví dụ `prep_reset:CompA->UserB`).
Tổng nỗ lực của chương trình tấn công là tổng các đơn vị công việc riêng biệt trong sổ cái:
$$C(\sigma) = \sum_{u \in \text{Ledger}(\sigma)} \text{cost}(u)$$
Quy tắc chuyển tiếp thụ động miễn phí:
- Việc truyền quyền qua quan hệ thành viên nhóm lồng nhau `MemberOf` thụ động trong kịch bản có chi phí bằng 0 ($C_{\text{closure}} \equiv 0$).
- Quy tắc này chỉ áp dụng cho bao đóng `MemberOf` thụ động đã được kiểm chứng; các hình thức chuyển quyền khác như kế thừa ACL hay cấp quyền có điều kiện không được mặc định coi là miễn phí.
- Nếu một đơn vị công việc trong sổ cái chưa có định mức nỗ lực, toàn bộ nỗ lực của chuỗi nhận giá trị `None`.
  Không dùng tổng từng phần để thay thế cho tổng nỗ lực.

### 2.5. Quan hệ Pareto bảo thủ, đường biên Pareto và phân vùng chẩn đoán
Hàm `risk_ineligibility(a)` kiểm tra tính đủ điều kiện tham gia so sánh rủi ro của ứng viên $a$:
- Trả về danh sách lý do không hợp lệ gồm: `blocked`, `unknown`, `likelihood_unrated`, `impact_unrated`.
- Nếu danh sách này không rỗng, hàm so sánh `scoped_preference(a, b)` trả về `not_eligible`.
  Ứng viên bị chuyển sang danh mục chẩn đoán (`diagnostics`) và không được xét vào đường biên Pareto.

Đối với hai ứng viên đủ điều kiện $a$ và $b$ với mức tác động $I_a, I_b$ và khoảng xác suất $[\underline{P}_a, \overline{P}_a], [\underline{P}_b, \overline{P}_b]$:
1. $a$ lấn át $b$ ($a \succ b$) khi và chỉ khi:
   $$I_a \ge I_b \quad \text{và} \quad \underline{P}_a > \overline{P}_b$$
   hoặc
   $$I_a > I_b \quad \text{và} \quad \underline{P}_a \ge \overline{P}_b$$
2. Hai ứng viên hòa điểm ($a \sim b$) khi có cùng mức tác động ($I_a = I_b$) và khoảng xác suất thu hẹp thành cùng một điểm chính xác ($\underline{P}_a = \overline{P}_a = \underline{P}_b = \overline{P}_b$).
   Khi hòa điểm, nếu cả hai đều có giá trị nỗ lực hợp lệ, ứng viên có nỗ lực thấp hơn sẽ được ưu tiên.
   Nếu một trong hai bên thiếu nỗ lực (`effort = None`), hai ứng viên giữ trạng thái không so sánh được.
3. Trong mọi trường hợp còn lại (có sự đánh đổi giữa $I$ và $P$, hoặc các khoảng xác suất chồng lấn $[\underline{P}, \overline{P}]$), hai ứng viên là không so sánh được (`incomparable`).

Đường biên Pareto (`frontier`) tập hợp tất cả các ứng viên đủ điều kiện mà không bị bất kỳ ứng viên đủ điều kiện nào khác lấn át.

---

## 3. Không gian tìm kiếm và ranh giới tích hợp cho TTS B

### 3.1. Hợp đồng tìm kiếm và giới hạn ngân sách
Mã nguồn nghiên cứu sử dụng hàm `bounded_programs()` để tìm kiếm các chương trình tấn công trong giới hạn ngân sách công việc tích cực (`max_work_units`).
Các nguyên tắc tìm kiếm cần tuân thủ:
- Không được cắt tỉa một nút chỉ dựa trên tiền tố chi phí nhỏ nhất (cheapest prefix), vì chi phí và xác suất phụ thuộc vào lịch sử chuỗi hành động phía trước.
- Khi một nhánh tìm kiếm chạm giới hạn ngân sách, công cụ kích hoạt cờ cắt cụt (`truncated = True`) trong metadata để thông báo kết quả tìm kiếm chưa bao phủ toàn bộ không gian trạng thái.

### 3.2. Phân biệt bài toán nỗ lực tối thiểu tới Domain Admins và mục tiêu Pareto
Hệ thống phân biệt rõ ràng hai bài toán tìm kiếm:
1. **Bài toán nỗ lực tối thiểu tới Domain Admins (min-effort-to-DA)**:
   Tìm chuỗi hành động tốn ít nỗ lực nhất từ điểm bàn đạp ban đầu tới Checkpoint S2.
   Đây là bài toán đơn mục tiêu, nhưng **không thể áp dụng trực tiếp thuật toán Dijkstra trên đồ thị cấu trúc đơn giản**.
   Lý do là chi phí thuộc quyền sở hữu của các đơn vị công việc, có tiền điều kiện kích hoạt, có bước chuẩn bị dùng chung và có thể chứa các trạng thái chưa được định mức.
   Chỉ có thể xem xét áp dụng thuật toán Dijkstra sau khi đã xây dựng được mô hình không gian trạng thái đầy đủ với chi phí bảo đảm tính cộng dồn và chứng minh được các điều kiện áp dụng.
2. **Bài toán biên rủi ro Pareto tới tài sản đích**:
   Tìm tập hợp các đường tấn công tối ưu trên hai trục tác động nghiệp vụ ($I$) và khoảng xác suất ($P$).
   Kết quả trả về là danh sách các phương án không bị lấn át trên đường biên Pareto, hoàn toàn độc lập và không thể thay thế bằng đường có nỗ lực nhỏ nhất.

### 3.3. Bảo toàn vết đường cấu trúc (Provenance Retention)
Mã nguồn nghiên cứu mẫu thử thực hiện thu gọn các chuỗi hành động có cùng chuỗi đơn vị công việc có thứ tự (canonical ordered work sequence) để kiểm chứng tính bất biến của việc đóng gói hành động.
Tuy nhiên, khi TTS B tích hợp engine chính thức tại Milestone M3, hệ thống bắt buộc phải lưu trữ riêng biệt danh sách các đường đi cấu trúc thực tế (`structural_routes`) kèm theo định danh chuẩn tắc và vị trí trích xuất (locator).
Yêu cầu lưu vết này nhằm phục vụ công tác kiểm toán an ninh, phân tích điểm nghẽn phòng thủ và đối chứng độ bao phủ với BloodHound.

---

## 4. Khoảng trống bằng chứng và điều kiện chuyển giao sang Issue #143

Toàn bộ các phân tích và thực nghiệm trong tài liệu này được xác định rõ các ranh giới:
1. **Kết luận về dữ liệu SEAMLESS**:
   Bài toán xếp hạng dự báo trên snapshot SEAMLESS vẫn giữ kết luận **Chưa đủ bằng chứng (Insufficient Evidence)**.
   Mọi con số xác suất, nỗ lực và mức tác động trong các ví dụ mẫu là giả định mô phỏng, không đại diện cho dữ liệu thực nghiệm đã được hiệu chuẩn.
2. **Ranh giới trách nhiệm**:
   TTS A chịu trách nhiệm về mô hình khái niệm, kịch bản phân tích, rubric đánh giá và các bài kiểm chứng hành vi (behavioral oracle).
   TTS B chịu trách nhiệm về canonical parser, cấu trúc dữ liệu đồ thị, thuật toán tìm kiếm và hiệu năng của engine sản phẩm.
3. **Cổng kiểm soát tiếp theo**:
   Việc chốt successor ADR (ADR-0013), bộ tham số sản phẩm và đặc tả giao diện bàn giao chính thức cho TTS B được thực hiện tại Issue #143.
   Việc nghiệm thu tài liệu nghiên cứu của PR #151 không cấu thành quyết định tự động chuyển các giả định mẫu thử thành cấu hình sản phẩm.
