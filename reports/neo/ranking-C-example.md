# Kết quả tìm đường

**Nguồn:** QUEEN_COX@SEAMLESS.INTERNAL → **Đích:** ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
**Mục tiêu:** Danh tính dùng được có quyền thành viên nhóm đích.
**Context xác thực:** BADBLOOD.SEAMLESS.INTERNAL.
**Kỹ thuật trong scope:** Dùng danh tính vừa reset; Thêm thành viên nhóm; Cấp quyền sửa DACL; Sửa DACL để cấp quyền; Dùng quyền thành viên nhóm; Reset mật khẩu; Reset mật khẩu.

Tìm được **10 chương trình**; hiển thị 3. Đạt đích theo facts và giả định của query.
Ưu tiên C thấp hơn trong các đường đã tìm và chấm được; đồng C không có nghĩa một đường tốt hơn. Thiếu P/I không chặn xếp hạng C.
Kết quả best-found; chưa chứng minh C nhỏ nhất trong toàn scope.
Giới hạn: 10 đường, 12 bước, 4096 lần mở rộng; đã dùng 51 lần.
C là công sức tương đối theo scenario, không phải số phút hay xác suất thành công.
Tìm kiếm bị giới hạn: `path_limit_reached`.

## Đường 1 — C=4

1. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL.
2. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL qua DOMAIN USERS@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL.
3. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL qua AUTHENTICATED USERS@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL.
4. Reset mật khẩu: QUEEN_COX@SEAMLESS.INTERNAL qua PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL.
5. Dùng danh tính vừa reset: KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL.
6. Dùng quyền thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL.
7. Sửa DACL để cấp quyền: KATRINA_GREEN@SEAMLESS.INTERNAL qua ADMINISTRATORS@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
8. Thêm thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
9. Dùng quyền thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.

C tính trên các công việc khác nhau, khử trùng theo ledger:

- Dùng danh tính vừa reset: C=0 (đích: BADBLOOD.SEAMLESS.INTERNAL).
- Thêm thành viên nhóm: C=1 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Sửa DACL để cấp quyền: C=2 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Reset mật khẩu: C=1 (đích: KATRINA_GREEN@SEAMLESS.INTERNAL).

P: chưa chấm; I: chưa chấm.

Giả định đã dùng trên đường này (không phải quan sát):

- Xác thực được chấp nhận (`authentication_accepted`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.
- Cho phép sửa đối tượng AD (`directory_write_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Cho phép sửa đối tượng AD (`directory_write_allowed`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Cho phép thay đổi thành viên nhóm (`membership_change_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.
- Kết nối tới KDC (`network_kdc_reachable`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.
- Kết nối RPC tới đích (`network_rpc_reachable`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Mật khẩu mới đáp ứng policy (`password_policy_accepts`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.

## Đường 2 — C=5

1. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL.
2. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL qua DOMAIN USERS@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL.
3. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL qua AUTHENTICATED USERS@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL.
4. Reset mật khẩu: QUEEN_COX@SEAMLESS.INTERNAL qua PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL.
5. Dùng danh tính vừa reset: KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL.
6. Dùng quyền thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL.
7. Sửa DACL để cấp quyền: KATRINA_GREEN@SEAMLESS.INTERNAL qua ADMINISTRATORS@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
8. Thêm thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
9. Cấp quyền sửa DACL: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
10. Dùng quyền thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.

C tính trên các công việc khác nhau, khử trùng theo ledger:

- Dùng danh tính vừa reset: C=0 (đích: BADBLOOD.SEAMLESS.INTERNAL).
- Thêm thành viên nhóm: C=1 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Cấp quyền sửa DACL: C=1 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Sửa DACL để cấp quyền: C=2 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Reset mật khẩu: C=1 (đích: KATRINA_GREEN@SEAMLESS.INTERNAL).

P: chưa chấm; I: chưa chấm.

Giả định đã dùng trên đường này (không phải quan sát):

- Xác thực được chấp nhận (`authentication_accepted`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.
- Cho phép sửa đối tượng AD (`directory_write_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Cho phép sửa đối tượng AD (`directory_write_allowed`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Cho phép thay đổi thành viên nhóm (`membership_change_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.
- Kết nối tới KDC (`network_kdc_reachable`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.
- Kết nối RPC tới đích (`network_rpc_reachable`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Mật khẩu mới đáp ứng policy (`password_policy_accepts`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.

## Đường 3 — C=5

1. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL.
2. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL qua DOMAIN USERS@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL.
3. Dùng quyền thành viên nhóm: QUEEN_COX@SEAMLESS.INTERNAL qua AUTHENTICATED USERS@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL.
4. Reset mật khẩu: QUEEN_COX@SEAMLESS.INTERNAL qua PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL.
5. Dùng danh tính vừa reset: KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL.
6. Dùng quyền thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL.
7. Sửa DACL để cấp quyền: KATRINA_GREEN@SEAMLESS.INTERNAL qua ADMINISTRATORS@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
8. Cấp quyền sửa DACL: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
9. Thêm thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.
10. Dùng quyền thành viên nhóm: KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL.

C tính trên các công việc khác nhau, khử trùng theo ledger:

- Dùng danh tính vừa reset: C=0 (đích: BADBLOOD.SEAMLESS.INTERNAL).
- Thêm thành viên nhóm: C=1 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Cấp quyền sửa DACL: C=1 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Sửa DACL để cấp quyền: C=2 (đích: ENTERPRISE ADMINS@SEAMLESS.INTERNAL).
- Reset mật khẩu: C=1 (đích: KATRINA_GREEN@SEAMLESS.INTERNAL).

P: chưa chấm; I: chưa chấm.

Giả định đã dùng trên đường này (không phải quan sát):

- Xác thực được chấp nhận (`authentication_accepted`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.
- Cho phép sửa đối tượng AD (`directory_write_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Cho phép sửa đối tượng AD (`directory_write_allowed`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Cho phép thay đổi thành viên nhóm (`membership_change_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.
- Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.
- Kết nối tới KDC (`network_kdc_reachable`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.
- Kết nối RPC tới đích (`network_rpc_reachable`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Mật khẩu mới đáp ứng policy (`password_policy_accepts`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.

JSON đầy đủ giữ trace, provenance, ledger và các giới hạn để kiểm chứng.
