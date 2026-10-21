# ADR-0006: Khung danh gia da tap du lieu song song (Dual-Dataset Evaluation Framework)

- Ngay: 2026-09-15 (Cap nhat: 2026-09-16)
- Trang thai: Superseded by ADR-0007
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #20, Refs #8, Refs #6, Refs #7, Refs #5
- Thay the boi: [ADR-0007](ADR-0007-enterprise-topology-independent-telemetry-evaluation.md)

> Ghi chu lich su: ADR nay ghi lai quyet dinh truoc mentor review Week 1.
> A/B khong con la primary evaluation datasets.
> Chien luoc hien hanh nam tai ADR-0007.

## Boi canh

Để đảm bảo mô hình đồ thị có trọng số Identity-Asset Graph đạt độ tin cậy khoa học cao và không bị thiên lệch vào một môi trường đơn lẻ, dự án tiếp nhận và tích hợp hai tập dữ liệu đánh giá có tính bổ trợ chiến lược:
1. **Dataset A (Benchmark Lab - GOADv2 NORTH):** Tập dữ liệu đơn miền chuẩn hóa `NORTH.SEVENKINGDOMS.LOCAL`.
   Dataset A cung cấp hai bản trích xuất song song từ SharpHound C# 2.3.3 (12 tệp, 347 bản ghi thô, 320 ID duy nhất) và BloodHound-Python CE (7 tệp, 94 bản ghi thô, 94 ID duy nhất).
   Tập dữ liệu này cung cấp bộ dữ liệu chuẩn hóa có quy mô vừa phải để đo lường tính bất biến đối với công cụ thu thập (Collector Invariance) và kiểm chứng thuật toán tìm đường trên kịch bản lab đã biết trước.
2. **Dataset B (Enterprise Multi-Domain - `ad_sampledata`):** Tập dữ liệu môi trường phòng thí nghiệm mô phỏng doanh nghiệp đa miền quy mô lớn (enterprise-style multi-domain lab dataset), gồm 3 miền được xuất khẩu (`PHANTOM.CORP`, `GHOST.CORP`, `WRAITH.CORP`) với 31 tệp JSON, 1.718 bản ghi thô, 1.469 ObjectIdentifier duy nhất, và 407 ID thuộc 6 loại đối tượng M1.
   Tập dữ liệu này cung cấp cấu trúc đa miền phức tạp, máy chủ điều khiển miền chỉ đọc (RODC), các mối quan hệ tin cậy liên miền (ParentChild và External Trusts), cùng cấu trúc phân quyền cục bộ chuyên sâu (`LocalGroups`, `UserRights`, trạng thái máy trạm `Status`).

Nếu chỉ sử dụng Dataset A, hệ thống sẽ gặp rủi ro bị "mù ranh giới miền" (Domain Boundary Blindness), không thể kiểm chứng khả năng mở rộng (scalability) và bỏ qua các đường tấn công leo thang xuyên biên giới miền.
Ngược lại, nếu chỉ sử dụng Dataset B, nhóm sẽ mất đi mẫu chuẩn đối sánh giữa hai công cụ thu thập phổ biến nhất của cộng đồng an ninh thông tin.
Do đó, dự án thiết lập khung đánh giá song song (Dual-Dataset Evaluation Framework) coi cả hai tập dữ liệu là đầu vào đánh giá hạng nhất cho cùng một pipeline xử lý duy nhất.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| 1. Chi dung Dataset A (GOADv2 NORTH) | Don gian, da co kich ban lab biet truoc | Khong kiem chung duoc da mien va quy mo lon | Du lieu raw NORTH |
| 2. Chi dung Dataset B (ad_sampledata) | Rung da mien quy mo phong phu | Mat doi sanh bat doi xung giua SharpHound va BloodHound.py | Du lieu raw ad_sampledata |
| 3. Khung danh gia song song hai tap du lieu (Dual-Dataset) | Toan dien: Vua kiem chung collector vua kiem chung da mien | Parser va engine can abstraction layer linh hoat | Khao sat thuc nghiem Issue #20 |

## Quyet dinh va he qua

Chúng ta chọn phương án 3: Thiết lập Khung đánh giá song song hai tập dữ liệu (Dual-Dataset Evaluation Framework).

Quy tắc kiến trúc và thực thi chi tiết:

1. **Định vị hai tập dữ liệu làm đầu vào đánh giá hạng nhất (First-class Evaluation Inputs):**
   Dự án không coi Dataset A là chính hay Dataset B là phụ về mặt thiết kế pipeline.
   Cả hai tập dữ liệu cùng đóng vai trò đầu vào kiểm thử độc lập cho cùng một mô hình đồ thị và pipeline xử lý thống nhất (`src/parser/` -> `src/engine/`).
   Tuyệt đối không xây dựng các nhánh mã nguồn (code branches) hay pipeline riêng biệt cho từng tập dữ liệu; pipeline phải tự động thích ứng với cấu trúc dữ liệu của cả hai nguồn.

2. **Phân định vai trò nghiên cứu và kiểm chứng:**
   - *Dataset A đóng vai trò "Bộ kiểm chuẩn độ đúng đắn và kiểm thử hồi quy" (Correctness & Regression Benchmark):*
     Dùng để kiểm chứng việc trích xuất và chuẩn hóa các cạnh M1 trong phạm vi raw evidence mà Dataset A cung cấp, đồng thời làm regression benchmark giữa hai collector và kiểm tra thuật toán Dijkstra so với kịch bản lab đã biết trước. Các cạnh không có positive/verified evidence (như ForceChangePassword, CanPSRemote, và CanRDP) cần synthetic fixtures hoặc evaluation evidence bổ sung.
   - *Dataset B đóng vai trò "Bộ kiểm chuẩn quy mô và độ bền vững đa miền" (Scalability & Multi-Domain Robustness Dataset):*
     Dùng để kiểm chứng hiệu năng thuật toán trên đồ thị lớn (1.469 đối tượng, hàng nghìn quan hệ), kiểm tra khả năng phân tách ranh giới miền dựa trên thuộc tính `domain`, và đánh giá các kỹ thuật leo thang đặc quyền liên miền qua cấu trúc Trust.

3. **Nguyên tắc phân định nguồn gốc sai lệch (Attribution of Divergence):**
   Khi phân tích đường đi hoặc trọng số giữa các kịch bản, sự khác biệt được quy nạp theo 4 tầng:
   - *Tầng 1 (Sai lệch công cụ thu thập):* Khác biệt giữa API Windows SAMR/LSA (SharpHound) và LDAP (BloodHound-Python).
   - *Tầng 2 (Tính biến động phiên):* Sai lệch thời điểm snapshot của các phiên đăng nhập tương tác (`Sessions`).
   - *Tầng 3 (Trạng thái thu thập):* Phân biệt rõ lỗi truy cập (`StatusAccessDenied` hoặc `FailureReason` trên từng primitive thu thập mang nghĩa `unknown`) với việc đối tượng thực sự không có quyền (mang nghĩa `false`). Trạng thái `Status.Connectable` chỉ là tín hiệu mạng tham khảo, không được dùng làm cổng phủ quyết toàn cục đối với bằng chứng đã thu thập thành công.
   - *Tầng 4 (Ranh giới miền và chính sách bảo mật):* Khác biệt giữa môi trường đơn miền và môi trường đa miền có áp dụng lọc SID (`SidFilteringEnabled: True`).

4. **Yêu cầu đối với thiết kế Parser (Refs #8):**
   Parser phải tích hợp lớp chuyển đổi (Multi-format Ingestion Adapter):
   - Nhận diện định dạng cấu trúc tệp: Hỗ trợ cấu trúc schema v6 thực tế quan sát được trong Dataset A và B (SharpHound và BloodHound-Python đều dùng `LocalGroups`/`UserRights`) và dự phòng khả năng tương thích ngược (future compatibility) cho collector legacy v4/v5 với mảng phẳng `LocalAdmins`.
   - Chuẩn hóa ID duy nhất về Canonical ID bảo toàn scope: Tuyệt đối không tách bỏ tiền tố miền/host khỏi các Well-known SIDs (`S-1-5-32-544`) nhằm tránh đụng độ đỉnh cục bộ giữa các máy trạm hoặc giữa các miền khác nhau; chuyển toàn bộ GUID về chữ thường.
   - Thực hiện hợp nhất bản ghi (merge attributes) cho các nhóm bị lặp ID (27 nhóm trong Dataset A, 62 nhóm trong Dataset B) thay vì ghi đè (last-write-wins) để tránh làm mất quan hệ thành viên.
   - Xử lý các miền được tham chiếu ngoài phạm vi xuất tệp (`SEVENKINGDOMS.LOCAL`, `REVENANT.CORP`, `CHILD.WRAITH.CORP`) như các đỉnh biên (Boundary/Stub Nodes).
   - Bắt buộc lưu trữ thuộc tính `domain` trên mỗi Node để bảo vệ tính toàn vẹn của đồ thị rừng đa miền.

Hệ quả:
- Nâng cao tính khái quát và giá trị học thuật của đề tài trong báo cáo nghiệm thu và luận văn.
- Yêu cầu toàn bộ các bài kiểm thử tự động và đo kiểm hiệu năng phải được thực thi nhất quán trên cả hai tập dữ liệu.

## Kiem chung va dieu kien xem lai

- Lệnh kiểm tra: `python scripts/verify_data_inventory.py`, `python scripts/check_contract.py` và chạy bộ test trên các fixture trích xuất từ cả hai tập dữ liệu.
- Tiêu chí thành công: Module parser dựng thành công đồ thị hợp lệ từ cả Dataset A và Dataset B, tuân thủ schema của contract mà không phát sinh lỗi dữ liệu.
- Điều kiện xem lại: Khi phát sinh định dạng thu thập mới từ BloodHound v5 API hoặc khi mở rộng bài toán sang môi trường đám mây lai (Hybrid Azure AD / Entra ID).
