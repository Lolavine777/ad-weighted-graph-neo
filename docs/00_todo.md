Trang 1 / 6
# IDENTITY# –# ASSET GRAPH
# VÀ PHÂN TÍCH ĐƯỜNG TẤN CÔNG
“Nếu kẻ tấn công chiếm được máy X, chúng có thể đi tới đâu và nhanh đến mức
nào?”
Hạng mục Nội dung
Tên đề tài Identity–Asset Graph và phân tích đường tấn công
Dữ liệu Dữ liệu Active Directory đã ẩn danh
Thời lượng 06 tuần (0.5 tuần đầu để setup máy móc và môi trường)
Nhân sự 02 thực tập sinh

---

Trang 2 / 6
### 1. MỤC TIÊU
Xây dựng một mô hình đồ thị biểu diễn quan hệ giữa danh tính (identity) và tài sản (asset)
trong Active Directory, trong đó mỗi cạnh mang trọng số phản ánh độ khó khai thác. Trên đồ
thị đó, trả lời câu hỏi cốt lõi: nếu một máy bị chiếm quyền, kẻ tấn công có thể leo thang tới
đâu, theo con đường nào và với chi phí thấp nhất là bao nhiêu.
Điểm khác biệt so với cách làm mặc định của BloodHound là không coi mọi bước leo thang
có chi phí như nhau: một số bước gần như miễn phí, số khác tốn nhiều thời gian và dễ thất
bại. Trọng số cho phép xếp hạng đường tấn công theo mức độ khả thi thay vì chỉ theo số
bước.
Các mục tiêu cụ thể:
• Hiểu dữ liệu AD và các kỹ thuật leo thang đặc quyền tương ứng với từng loại quan hệ.
• Đề xuất mô hình gán trọng số khai thác cho các cạnh.
• Dựng đồ thị có trọng số từ dữ liệu AD ẩn danh.
• Tìm đường tấn công chi phí thấp nhất từ một máy bị chiếm tới Domain Admin.
• Tìm nút thắt cổ chai và so sánh kết quả với BloodHound.
• Viết báo cáo và trình bày kết quả kèm khuyến nghị khắc phục.
### 2. PHẠM VI VÀ ĐƠN GIẢN HÓA
Nguyên tắc chính: đồ thị được dựng dựa trên thuộc tính có sẵn trong dữ liệu AD ẩn danh
(attribute-based edge construction), sau đó bổ sung một lớp trọng số biểu diễn khả năng khai
thác cho từng cạnh. Các chi tiết dưới đây là gợi ý; thực tập sinh tự research và đề xuất
phương án cụ thể để bảo vệ.
2.1. Xây dựng cạnh từ thuộc tính
Các loại node và cạnh cần đưa vào là hướng gợi mở. Thực tập sinh tự khảo sát dữ liệu để
chốt danh sách:
• Node gợi ý: User, Computer, Group, Domain/DC, GPO/OU (và Certificate Template
nếu dữ liệu cho phép).
• Cạnh cốt lõi gợi ý: MemberOf, AdminTo, quyền ACL nguy hiểm (GenericAll,
WriteDacl, ForceChangePassword…), quyền truy cập từ xa (CanRDP, CanPSRemote),
HasSession.
• Cạnh mở rộng (nếu còn thời gian): ReadLAPSPassword, RBCD, DCSync, các đường
qua GPO và AD CS.

---

Trang 3 / 6
→ Thực tập sinh tự research để lập bảng ánh xạ: mỗi loại cạnh tương ứng kỹ thuật khai thác
nào, điều kiện tiên quyết ra sao, khó hay dễ.
2.2. Bổ sung trọng số khả năng khai thác
Mỗi cạnh được gán một điểm/xác suất phản ánh độ khó khai thác. Thực tập sinh tự đề xuất bộ
tiêu chí chấm điểm (ví dụ: điều kiện tiên quyết, độ tin cậy của kỹ thuật, thời gian thực thi, khả
năng bị phát hiện) và cách quy đổi điểm thành trọng số cạnh sao cho có thể tính được chi phí
của cả một đường đi.
→ Việc chọn công thức trọng số và giá trị cụ thể cho từng loại cạnh là phần thực tập sinh tự
research và bảo vệ.
2.3. Các giả định đơn giản hóa
• Đồ thị tĩnh: chụp một thời điểm, không mô hình hóa thay đổi theo thời gian.
• Đơn miền: bỏ qua quan hệ trust liên miền/forest trừ khi bắt buộc.
• Mục tiêu cố định: mặc định là Domain Admins / Enterprise Admins và Domain
Controller.
• Chỉ phân tích trên dữ liệu, không khai thác thực tế trên hệ thống thật.
### 3. KẾ HOẠCH THEO TUẦN
Tổng 6 tuần, nửa tuần đầu dành cho setup máy móc và môi trường. Kế hoạch dưới đây áp
dụng chung cho cả nhóm; phần phân chia công việc cho 2 người ở Mục 4.
Tuần Trọng tâm Công việc chính
Tuần 1
(0.5 đầu) 
Setup môi trường 
Cài máy/công cụ (Neo4j, BloodHound, Python, Git); nhận
và kiểm tra dữ liệu AD ẩn danh
Tuần 1
(0.5 sau) 
Làm quen dữ liệu 
Tìm hiểu đối tượng AD, ACL, group nesting; thống kê mô
tả dữ liệu; import vào BloodHound để quan sát
Tuần 2 Kỹ thuật khai thác 
Research từng loại quan hệ AD và kỹ thuật leo thang
tương ứng; lập bảng cạnh – kỹ thuật – độ khó
Tuần 3 Trọng số & dựng đồ thị 
Chốt mô hình trọng số; viết pipeline chuyển dữ liệu AD
thành đồ thị có trọng số
Tuần 4 Tìm đường tấn công 
Cài đặt thuật toán tìm đường chi phí thấp nhất từ máy bị
chiếm tới Domain Admin
Tuần 5 Choke point & so sánh 
Tìm nút thắt cổ chai; chạy đối chứng và so sánh với
BloodHound

---

Trang 4 / 6
Tuần Trọng tâm Công việc chính
Tuần 6 Báo cáo & bảo vệ 
Hoàn thiện trực quan hóa, viết báo cáo, chuẩn bị demo và
slide
Bảng 1. Kế hoạch chung theo tuần
### 4. PHÂN CHIA CÔNG VIỆC CHO 2 NGƯỜI ### (G### ỢI ### Ý)
Nhóm gồm 2 thực tập sinh. Cách chia: một người thiên về hiểu dữ liệu và mô hình hóa AD
(thiên “domain / an ninh AD”), một người thiên về xây pipeline và thuật toán đồ thị (thiên
“kỹ thuật / graph”). Hai người vẫn cùng research và review chéo, các đầu việc dùng chung
được ghi rõ.
4.1. Vai trò
Thành viên Vai trò chính
TTS A – AD & Mô hình 
Hiểu dữ liệu AD, taxonomy kỹ thuật khai thác, đề xuất mô hình trọng
số, phân tích choke point, khuyến nghị khắc phục
TTS B – Pipeline &
Thuật toán
Setup môi trường, viết pipeline dựng đồ thị, cài đặt thuật toán tìm
đường, so sánh BloodHound, trực quan hóa
Bảng 2. Phân vai hai thành viên
4.2. Đầu việc theo tuần
Tuần TTS A – AD & Mô hình TTS B – Pipeline & Thuật toán
Tuần 1 
Nghiên cứu cấu trúc dữ liệu AD, ACL,
group nesting; thống kê mô tả dữ liệu
Setup máy móc, cài
Neo4j/BloodHound/Python/Git; import dữ
liệu vào BloodHound
Tuần 2 
Research kỹ thuật khai thác từng loại quan
hệ; lập bảng cạnh – kỹ thuật – độ khó
Thiết kế cấu trúc dữ liệu đồ thị (schema
node/edge); dựng khung parser đọc dữ liệu
thô
Tuần 3 
Đề xuất bộ tiêu chí và giá trị trọng số cho
từng loại cạnh
Hoàn thiện pipeline sinh node/edge; nạp
trọng số của A vào đồ thị
Tuần 4
Chuẩn bị tập ca kiểm thử (node xuất phát,
mục tiêu); kiểm tra tính hợp lý của đường
đi
Cài đặt thuật toán tìm đường chi phí thấp
nhất và top-K; xây truy vấn “từ máy X đến
DA”
Tuần 5 
Phân tích và xếp hạng choke point; đề xuất
khuyến nghị khắc phục
Cài đặt tính choke point; chạy đối chứng
BloodHound; dựng trực quan hóa

---

Trang 5 / 6
Tuần TTS A – AD & Mô hình TTS B – Pipeline & Thuật toán
Tuần 6 
Viết phần phân tích, khuyến nghị và so
sánh trong báo cáo
Dọn mã nguồn, viết README, hoàn thiện
demo; ghép báo cáo
Bảng 3. Đầu việc chi tiết cho hai người theo tuần
4.3. Việc làm chung
• Cùng research và thống nhất taxonomy cạnh (tuần 2) và mô hình trọng số (tuần 3).
• Review chéo mã nguồn và kết quả để giảm sai sót và tránh phụ thuộc một người.
• Cùng chuẩn bị và bảo vệ báo cáo cuối kỳ.
### 5. TIÊU CHÍ HOÀN THÀNH
Đề tài hoàn thành khi đạt các tiêu chí bắt buộc dưới đây; tiêu chí mở rộng là phần cộng điểm.
Bắt buộc:
• Có tài liệu mô tả dữ liệu AD và bảng taxonomy cạnh – kỹ thuật – độ khó.
• Có mô hình trọng số kèm lập luận, và pipeline dựng được đồ thị tự động từ dữ liệu thô.
• Truy vấn được đường tấn công chi phí thấp nhất từ node bất kỳ tới Domain Admin.
• Có danh sách choke point và bảng so sánh với BloodHound.
• Có báo cáo, demo chạy được và mã nguồn tái lập được (README).
Mở rộng (không bắt buộc):
• Mô hình hóa cạnh nâng cao (RBCD, delegation, AD CS).
• Ước lượng “thời gian tới Domain Admin” theo đơn vị thời gian.
• Gợi ý tập sửa lỗi tối ưu để cắt phần lớn đường tấn công; trực quan hóa tương tác.
### 6. ### PHƯƠNG PHÁP ĐÁNH GIÁ
Tính đúng đắn của đồ thị:
• Đối chiếu số node/cạnh với BloodHound trên cùng dữ liệu; mọi chênh lệch phải giải
thích được.
• Kiểm tra tay một mẫu ngẫu nhiên các cạnh, truy ngược về thuộc tính gốc.
• Thử trên dữ liệu có đường tấn công biết trước (lab nhỏ / dataset mẫu) để xác nhận thuật
toán đúng.
Chất lượng mô hình trọng số:

---

Trang 6 / 6
• Nhiều người chấm độc lập cùng bộ tiêu chí, đo mức đồng thuận; chênh lệch lớn nghĩa là
tiêu chí chưa rõ.
• Phân tích độ nhạy: thay đổi trọng số quanh giá trị chọn và xem top đường/choke point có
ổn định không.
Kết quả phân tích:
• So sánh với BloodHound: đường đi khác nhau ở đâu, choke point trùng bao nhiêu, và tại
sao.
• Đo mức giảm rủi ro khi loại bỏ top choke point (% đường tấn công bị cắt).
• Đo hiệu năng: thời gian dựng đồ thị và thời gian trả về một truy vấn.
Nghiệm thu:
• Review hàng tuần với mentor; nghiệm thu giữa kỳ (cuối tuần 3) và cuối kỳ (tuần 6) với
demo và bảo vệ.
### 7. ### Đ### ÁNH GIÁ N### ĂNG LỰC THỰC TẬP SINH
Hạng mục Trọng số Căn cứ đánh giá
Hiểu biết chuyên môn về AD và kỹ
thuật tấn công 
25% 
Chất lượng taxonomy, khả năng trả lời phản
biện
Chất lượng kỹ thuật của sản phẩm 30% 
Mã nguồn, kiến trúc pipeline, tính đúng đắn,
khả năng tái lập
Chất lượng phân tích và lập luận 20% 
Lập luận cho mô hình trọng số, phân tích so
sánh với BloodHound
Tiến độ và tính chủ động 10% 
Hoàn thành các mốc M0–M5 đúng hạn, chủ
động nêu vấn đề
Báo cáo và trình bày 15% 
Cấu trúc báo cáo, độ rõ ràng của hình vẽ,
chất lượng buổi bảo vệ
— Hết —
```[cite: 2]