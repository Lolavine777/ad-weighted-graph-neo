Bạn là một người chấm độc lập cho một nghiên cứu phòng thủ về Active Directory.
Hãy chấm công sức của 11 hành động dưới đây theo đúng thang đo cho trước.
Chỉ dựa vào nội dung trong tin nhắn này: không mở tệp nào, không dùng công cụ, không tìm trên mạng.

Bối cảnh chung:
- Một miền Active Directory duy nhất, mọi đối tượng cùng miền.
- Người thực hiện là người kiểm thử xâm nhập có kinh nghiệm, dùng công cụ công khai phổ biến.
- Quyền nêu trong mô tả đã có sẵn và mọi điều kiện cần thiết đều đúng.
- Chỉ chấm riêng hành động được mô tả, không tính bước dò tìm hay các bước trước đó.

Thang đo, mỗi tiêu chí là số nguyên từ 1 đến 3:
- T1, độ phức tạp công cụ: 1 = dùng công cụ chuẩn có sẵn; 2 = cần tùy biến cấu hình hoặc khuôn mẫu dữ liệu; 3 = phải phát triển hoặc biên dịch kỹ thuật mới.
- T2, công sức thao tác và xác minh: 1 = trao đổi đơn giản khi đã đủ dữ liệu; 2 = gồm thực thi và kiểm tra kết quả; 3 = xử lý nặng.

Các hành động:
1. genericall_reset_password: đặt lại mật khẩu của một tài khoản người dùng khi đang có quyền GenericAll trên tài khoản đó.
2. reset_target_password: đặt lại mật khẩu của một tài khoản người dùng khi có quyền ForceChangePassword trên tài khoản đó.
3. scenario_reset_password: đặt lại mật khẩu qua quyền GenericAll, với ý định ngay sau đó đăng nhập bằng mật khẩu mới.
4. acquire_reset_identity: xác thực bằng mật khẩu vừa đặt lại để dùng danh tính của tài khoản đó.
5. genericall_add_member: thêm một thành viên vào một nhóm khi có quyền GenericAll trên nhóm, rồi kiểm tra thay đổi.
6. genericall_grant_write_dacl: dùng quyền GenericAll trên một đối tượng để cấp cho mình quyền WriteDacl trên đối tượng đó.
7. grant_new_object_right: dùng quyền WriteDacl trên một đối tượng để thêm một mục ACE cấp toàn quyền (GenericAll) cho mình.
8. obtain_admin_execution_on_host: dùng quyền quản trị cục bộ trên một máy để xác thực và thực thi lệnh quản trị trên máy đó.
9. scenario_winrm_admin: thực thi lệnh qua WinRM trên một máy mà mình có quyền quản trị.
10. open_winrm_remote_session: mở một phiên lệnh WinRM tới máy khi danh tính thuộc nhóm Remote Management Users, không có quyền quản trị.
11. use_session_identity: đã có quyền quản trị trên một máy đang có phiên đăng nhập của tài khoản khác; lấy thông tin xác thực dùng lại được của phiên đó rồi xác thực bằng danh tính ấy.

Trả lời bằng đúng một khối JSON, không kèm chữ nào khác, theo dạng:
{"ratings": {"genericall_reset_password": {"t1": 1, "t2": 2, "why": "dưới 20 chữ"}, ...}}
Phải có đủ 11 khóa đúng như tên ở trên.
