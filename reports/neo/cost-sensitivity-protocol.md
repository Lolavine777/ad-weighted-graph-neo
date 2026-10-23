# Protocol độ nhạy C trên tập chương trình cố định

Chốt ngày 23/10/2026 trước khi chạy sensitivity, từ main `6645cda`.
Mục tiêu là kiểm tra độ bền thứ hạng C trong tập chương trình đã tìm được, không hiệu chỉnh bảng C production hoặc thay search để làm đẹp kết quả.

## Input và discovery

Dùng nguyên 26 lượt nguồn–đích của `bloodhound-query-pack.json`: SEAMLESS 10, WRAITH 10 và session 6.
Khử trùng hai cặp EXTDC01 khi tổng hợp, còn 24 cặp duy nhất; không lọc theo kết quả.
Snapshot nhập bằng parser hiện tại, raw đúng manifest; WRAITH chỉ dùng prefix `20240305111414`.
Discovery dùng `neo_guided`, `neo-c-v1`, 10 chương trình, 12 semantic steps, 4.096 expansions/query và scenario của query pack.
Mọi chương trình được native replay và baseline C được đối chiếu tổng ledger công việc duy nhất trước sensitivity.
Không dùng `neo_refine` vì giá thay đổi có thể làm đổi thứ tự discovery và gây lẫn hai câu hỏi.

## Các phép thay đổi đã khai báo

C vẫn bằng T1+T2−2, T1/T2 trong {1,2,3}; chỉ đổi T2, giữ T1.
Tám họ action bao phủ đủ 11 class của profile:

- Reset: genericall_reset_password, reset_target_password, scenario_reset_password.
- Activation: acquire_reset_identity.
- Membership mutation: genericall_add_member.
- Grant DACL control: genericall_grant_write_dacl.
- ACL grant: grant_new_object_right.
- Host execution: obtain_admin_execution_on_host, scenario_winrm_admin.
- WinRM command: open_winrm_remote_session.
- Session credential: use_session_identity.

Mỗi họ có một probe tăng T2 thêm 1 và một probe giảm 1 khi còn trong rubric.
Activation đang T2=1 nên không có probe giảm: tổng 15 probe một họ, không tính noop thành thử nghiệm.
Thành viên có sẵn và các bước passive không được thêm công sức.
Hai joint stress được khai báo riêng, không diễn giải như khoảng tin cậy:

1. `reset_dearer_acl_cheaper`: reset và activation T2+1; membership mutation và ACL grant T2−1.
2. `session_dearer_directory_cheaper`: host execution và session credential T2+1; reset, membership mutation, grant DACL control và ACL grant T2−1.

Baseline cộng 17 biến thể tạo 18 bảng giá.
Chúng là giả thuyết thăm dò trong rubric ordinal, không phải mức sai số đã đo hoặc quyết định expert được phê duyệt.
Không sửa bảng C mặc định hoặc gán xác suất cho các biến thể.

## Đo lường và kiểm tra

Giữ nguyên các program ID, work-unit IDs và feasibility; mỗi work unit duy nhất được tính đúng một lần.
Thiếu class, ledger, giá trị rubric hoặc không khớp C baseline làm runner dừng, không thay bằng 0.
Theo từng cặp, lưu minimum C trong candidate set, toàn bộ tập đồng hạng rẻ nhất, Top-3 theo tie policy hiện có và các strict rank reversals.
Phân biệt việc một đường rời tập tốt nhất với thay đổi thứ tự tường minh do phá hòa canonical.
Tổng hợp số cặp có thay đổi tập rẻ nhất, tập tốt nhất mất giao nhau hoàn toàn, C thay đổi và thứ hạng đảo chiều nghiêm ngặt.
Hai cặp không có witness được giữ trong mẫu, không chấm C hoặc tính thành thứ hạng ổn định.
Không cộng hai lần các cặp trùng giữa strata; kiểm candidate set của chúng giống nhau trước khi khử trùng.

Control synthetic dùng fixture two_routes có oracle độc lập: đường ACL C=3 và reset C=1 ở baseline; joint stress thứ nhất cho ACL C=1 và reset C=3.
Đây là kiểm tra phép tính/đảo thứ hạng; không cộng synthetic vào kết quả AD.
Kiểm lại zero-cost activation, dedup work-unit, giá âm/ngoài rubric và class bị thiếu bằng tests.
Chạy nguyên analysis hai lần chỉ khi có lỗi hoặc source thay đổi; không chọn một lần có kết quả thuận lợi hơn.

## Giới hạn và bước tiếp theo

Capped discovery không cung cấp tập alternative đầy đủ, nên độ bền trong candidate set không chứng minh optimum toàn cục hoặc độ bền với đường chưa tìm thấy.
Kết quả một miền phát triển và một corpus đã xem không phải blind evaluation.
Chưa đánh giá thay đổi source ranking toàn miền, lựa chọn intervention hoặc hiệu quả vận hành.
Không chạy lại BloodHound hoặc sửa database trong lượt sensitivity này.
Bước đánh giá mù cần một môi trường AD chưa dùng để điều chỉnh neo và protocol riêng chốt trước khi xem kết quả.
