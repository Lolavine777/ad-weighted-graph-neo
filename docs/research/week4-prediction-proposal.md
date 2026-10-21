# Phản hồi feedback: từ dữ liệu AD tới các đường tấn công có điều kiện

TTS A, cập nhật 07/10/2026. B đã approve nghiên cứu ở PR #217 và PR đã merge; [bộ ca/ranh giới tích hợp](week4-extension-scenario-handoff.md) đang để review tiếp. Bản sửa này chưa gửi mentor, chưa chốt triển khai.
Nguồn: [sàng lọc 40 dòng](week4-field-driven-screening.md), [đối chiếu raw](week4-screening-raw-verification.md), [lịch sử nghiên cứu](week4-prediction-evidence.md).

## Bản nhắn đề xuất

Dạ thưa các anh, từ feedback vừa rồi, nhóm Identity Asset Graph chúng em hiểu rằng cần xuất phát từ dữ liệu AD đang có để tìm những hành động có thể mở thêm đường tấn công. Mục tiêu là dự đoán chuỗi từ khả năng ban đầu tới tài sản; một bước có thể tạo quyền hoặc danh tính mới để dùng ở bước sau.

Nhóm đã mở rộng task hai roasting thành **sàng lọc kỹ thuật từ field AD**: kiểm tài khoản, nhóm, ACL, quyền trên máy, delegation và GPO; GPT hỗ trợ đề xuất, nhóm đối chiếu nguồn kỹ thuật và dữ liệu. Nhóm đã tải lại đủ sáu file SEAMLESS từ GitHub, kiểm checksum, chạy lại pipeline và sàng lọc bảng 40 kỹ thuật. Bảng có bước thu thông tin và mục trùng, nên mỗi dòng chưa tương ứng một cạnh mới.

Đề xuất hiện tại:

- **AS-REP Roasting trước:** có tài khoản không yêu cầu pre-auth, thuộc nhóm quản trị miền và được parser nối quyền tới DC; phù hợp kiểm chuỗi từ chưa có credential/control AD dùng được tới tài sản, với account đích biết hoặc đoán được và KDC kết nối được.
- **RBCD để review kế tiếp:** cùng một user có GenericAll trên máy đích và trên tài khoản đang bật, có SPN; có thể nghiên cứu dùng bước reset đã có để lấy tài khoản dịch vụ rồi tạo quan hệ delegation mới. Chưa coi quyền này là đã chiếm tài khoản hoặc thực hiện thành công.
- **Kerberoasting vẫn giữ trong danh sách:** có SPN và đường quyền downstream, nhưng ca đã chọn dùng quyền mà nhiều user ban đầu cũng tới được, nên cần đối chứng hoặc đổi ca trước khi khẳng định mở đường mới. Owner/GPO hiện chỉ thấy holders đặc quyền; DCOM có nhánh riêng nhưng còn phải xác định quyền thực thi và tác động trên máy.

Các bước mới khi sinh trên đồ thị sẽ là cạnh hành động có điều kiện. Ví dụ, nhận AS-REP → khôi phục được bí mật → xác thực thành tài khoản → dùng quyền trên tài sản. Nhóm ghi rõ dữ kiện, quy tắc và giả định còn thiếu; thiếu điều kiện không tự tạo quyền thành công. Quản trị miền là mốc trung gian, vẫn phải kiểm bước tới tài sản đích.

C/P/I vẫn đánh giá toàn đường. Công sức và xác suất tính theo công việc mới thực sự cần làm, có điều kiện các bước trước đã thành công; quan hệ nhóm thụ động và cùng bí mật đã lấy không bị tính lặp. Thêm hành động có thể thất bại làm P giảm là phù hợp; số cạnh riêng lẻ không quyết định mức giảm. Chưa có căn cứ về khả năng dò thì để chưa chấm hoặc phân tích theo giả định được ghi rõ.

Nhóm dự kiến chốt 1–2 chuỗi để tích hợp, kiểm ca đủ điều kiện, bị chặn và chưa biết; so trước/sau trên cùng điểm xuất phát, đích và giả định để biết có mở thêm khả năng tới tài sản hay chỉ thêm cách đi. Công việc lõi Week 4 tiếp tục song song.

Các anh nhận định cách giải quyết này đã bám đúng bài toán predict attack chưa ạ? Có lỗ hổng nào trong cách suy từ dữ liệu sang hành động, nối tới tài sản hoặc đánh giá toàn đường mà nhóm cần sửa trước khi chốt phạm vi tích hợp không ạ?
