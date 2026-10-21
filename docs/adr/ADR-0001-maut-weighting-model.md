# ADR-0001: Mo hinh trong so 4D MAUT va co che chi phi heuristic cong don cho Dijkstra

- Ngay: 2026-09-14 (Cap nhat trang thai: 2026-09-25)
- Trang thai: Historical / Superseded in part (Experimental baseline only; production weighting deferred to Issue #42)
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #5, Refs #1, Refs #2, Refs #3, Refs #83, Refs #42

> [!NOTE]
> **Reclassification & Governance Boundary (Reconciled under Issue #83):**
> ADR-0001 tài liệu hóa thiết kế ban đầu cho mô hình trọng số 4D MAUT trên từng cạnh cấu trúc ($W(e) = 0.25 P + 0.40 D + 0.20 C + 0.15 R^*$) như một heuristic thử nghiệm.
> Trong Graph Contract 1.0.0 (`configs/contract.yml`), profile `maut_v1` được ấn định rõ ràng `production_ready: false`, chỉ giữ vai trò so sánh thực nghiệm và đối sánh lịch sử.
> Profile `unit` ($W=1.0$) là baseline duy nhất được chấp thuận cho kiểm thử hồi quy và tính đúng đắn thuật toán của Milestone 2 (#44).
> Đề xuất PR #51 (`maut_v2`) đã bị supersede và không được áp dụng.
> Theo ADR-0008, kiến trúc hệ thống đã tách rời đồ thị cấu trúc Active Directory khỏi tầng Attack Semantics; ExpectedTelemetry gắn với kỳ vọng của technique/semantic transition, không phải trực tiếp với quan hệ cấu trúc.
> `cost_factors` chỉ là descriptive research input; production cost ownership giữa structural relationship, semantic transition hoặc composition vẫn chưa được quyết định và thuộc quyết định kế thừa #42.
> Quyết định kế thừa chính thức cho mô hình trọng số sản phẩm (production weighting) được mở và theo dõi độc lập tại Issue #42.
> ADR này được lưu giữ như tài liệu đối chứng lịch sử cho profile thực nghiệm `maut_v1`.
>
> **Post-report limitation clarification (2026-09-25):**
> Mentor feedback xác nhận rằng production rubric không được mặc định tái sử dụng bốn dimension lịch sử bên dưới.
> Detectability phụ thuộc audit/EDR/SOC và environment context, nên nếu được giữ phải có contextual hoặc knowledge-based rubric cùng limitation rõ.
> Reliability/success probability có nguy cơ double-count nếu nó chỉ là outcome của prerequisites, complexity và runtime controls; khi chưa có independent evidence/calibration, nó không phải independent production dimension.
> #42 phải chốt cost ownership, criterion independence/overlap và unknown policy trước numeric scoring.
> Clarification này không rewrite quyết định lịch sử; successor ADR sẽ thay thế production phần của ADR-0001 sau khi #42 được accepted.

## Boi canh

Mô hình đồ thị mặc định của BloodHound là đồ thị không trọng số (unweighted graph với chi phí mỗi cạnh bằng 1).
Cách tiếp cận này coi mọi bước nhảy đều có chi phí và độ khó như nhau, dẫn đến việc chỉ tìm đường có số bước ít nhất.
Trong thực tế, một bước tấn công có thể đòi hỏi kỹ thuật cao, dễ thất bại hoặc tạo tiếng ồn lớn kích hoạt EDR/SOC.
Ngược lại, một chuỗi gồm nhiều bước kế thừa nhóm tự nhiên lại diễn ra trong im lặng và đảm bảo thành công tuyệt đối.
Chúng ta cần một hàm chi phí định lượng phản ánh đúng mức độ cản trở, nỗ lực và rủi ro thực tế mà vẫn tương thích với thuật toán Dijkstra.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| 1. BFS khong trong so (BloodHound) | Don gian, khong can tham so hoa | Bo qua do on telemetry va ti le that bai | BloodHound default |
| 2. Bang diem tinh chu quan (Static Matrix) | De cai dat nhanh | Thieu co so toan hoc va thieu tinh nhat quan | Prototype so bo |
| 3. Mo hinh 4D MAUT (Chi phi heuristic cong don) | Da chieu, phan anh no luc va rui ro, tuong thich Dijkstra | Can xay dung rubric chuyen gia de dinh luong tham so | NIST CVSS v3.1, Phillips & Swiler (1998) |

## Quyet dinh va he qua

Chúng ta chọn phương án 3: Mô hình Hữu dụng Đa thuộc tính (MAUT) dựa trên vector 4 chiều:
$$\vec{x}(e) = [P(e), D(e), C(e), R^*(e)]^T$$

Trong đó:
- $P(e) \in [1, 5]$: Điều kiện tiên quyết (Prerequisites).
- $D(e) \in [1, 5]$: Khả năng bị phát hiện / Tiếng ồn telemetry (Detectability).
- $C(e) \in [1, 5]$: Độ phức tạp kỹ thuật (Complexity).
- $R(e) \in [1, 5]$: Độ tin cậy thành công (Reliability), với $R^*(e) = 6 - R(e)$.

Hàm chi phí MAUT được định nghĩa:
$$W(e) = 0.25 \cdot P(e) + 0.40 \cdot D(e) + 0.20 \cdot C(e) + 0.15 \cdot R^*(e)$$

Hệ số $\beta = 0.40$ dành cho Detectability phản ánh bản chất bất đối xứng khi chiến dịch của kẻ tấn công có chủ đích bị phát hiện.

Cơ sở lý thuyết toán học và mối liên hệ với Dijkstra:
Nghiên cứu của Phillips & Swiler (1998) chỉ ra rằng nếu một đường đi được đánh giá bằng xác suất thành công độc lập $P_s(e) \in (0, 1]$, bài toán cực đại hóa xác suất $\max \prod P_s(e)$ có thể chuyển đổi thành cực tiểu hóa tổng chi phí $\min \sum (-\ln P_s(e))$.
Ý tưởng này cung cấp cơ sở lý thuyết chứng minh rằng việc mô hình hóa đồ thị tấn công bằng các trọng số cộng dồn không âm là hoàn toàn phù hợp để tìm kiếm đường đi tối ưu bằng thuật toán Dijkstra.
Tuy nhiên, trong mô hình hiện tại, hàm $W(e)$ được định nghĩa như một **chỉ số chi phí heuristic có tính cộng dồn** (additive heuristic effort/risk cost index), phản ánh tổng hòa mức độ cản trở, độ ồn và nguy cơ thất bại.
Chúng ta không tuyên bố rằng việc cực tiểu hóa $\sum W(e)$ tương đương với việc tối đa hóa xác suất thành công toàn cục $\prod P_s(e)$, bởi vì hiện tại dự án chưa thiết lập hàm ánh xạ hay thực hiện đo kiểm hiệu chuẩn thực nghiệm (empirical calibration) giữa $W(e)$ và $P_s(e)$.
Với tính chất $W(e) \ge 1.0 > 0$, hàm chi phí đảm bảo tuyệt đối điều kiện trọng số không âm, loại bỏ hoàn toàn chu trình âm và đảm bảo thuật toán Dijkstra luôn tìm được con đường có tổng chi phí nỗ lực/rủi ro nhỏ nhất.

Hệ quả:
- Schema đồ thị lưu trữ thuộc tính `weight` kiểu số thực không âm cho mỗi cạnh.
- Engine tìm đường Dijkstra sử dụng trực tiếp `weight` để tính khoảng cách tích lũy chi phí nỗ lực và rủi ro.
- Đảm bảo tính chặt chẽ về mặt khoa học, tránh tuyên bố chưa được kiểm chứng về mặt xác suất thực nghiệm trong luận văn.

## Kiem chung va dieu kien xem lai

- Lệnh kiểm tra: `python scripts/check_contract.py` và `pytest`.
- Tiêu chí thành công: Profile `maut_v1` được nạp vào contract và toàn bộ trọng số là số thực hữu hạn không âm, Dijkstra tìm đường thành công theo chi phí tích lũy nhỏ nhất.
- Điều kiện xem lại: Khi có số liệu đo đạc thực nghiệm từ phòng lab thực tế để xây dựng hàm ánh xạ hiệu chuẩn chính thức giữa $W(e)$ và xác suất thành công $P_s(e)$.
