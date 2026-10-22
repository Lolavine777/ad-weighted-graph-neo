# Kết quả tìm đường

**Nguồn:** EXTCA01.WRAITH.CORP → **Đích:** DOMAIN ADMINS@WRAITH.CORP.
**Mục tiêu:** Danh tính dùng được có quyền thành viên nhóm đích.
**Context xác thực:** EXTCA01.WRAITH.CORP.
**Kỹ thuật trong scope:** Dùng danh tính vừa reset; Thêm thành viên nhóm; Cấp quyền sửa DACL; Sửa DACL để cấp quyền; Thực thi với quyền quản trị host; Mở phiên lệnh WinRM (không tự cấp admin); Dùng quyền thành viên nhóm; Reset mật khẩu; Reset mật khẩu; Lấy và dùng danh tính từ session trên máy đã kiểm soát.

Tìm được **1 chương trình**; hiển thị 1. Đạt đích theo facts và giả định của query.
Ưu tiên C thấp hơn trong các đường đã tìm và chấm được; đồng C không có nghĩa một đường tốt hơn. Thiếu P/I không chặn xếp hạng C.
Kết quả best-found; chưa chứng minh C nhỏ nhất trong toàn scope.
Giới hạn: 1 đường, 12 bước, 1024 lần mở rộng; đã dùng 2 lần.
C là công sức tương đối theo scenario, không phải số phút hay xác suất thành công.
Tìm kiếm bị giới hạn: `path_limit_reached`.

## Đường 1 — C=2

1. Lấy và dùng danh tính từ session trên máy đã kiểm soát: EXTCA01.WRAITH.CORP → BM@WRAITH.CORP.
2. Dùng quyền thành viên nhóm: BM@WRAITH.CORP → DOMAIN ADMINS@WRAITH.CORP.

C tính trên các công việc khác nhau, khử trùng theo ledger:

- Lấy và dùng danh tính từ session trên máy đã kiểm soát: C=2 (đích: BM@WRAITH.CORP).

P: chưa chấm; I: chưa chấm.

Giả định đã dùng trên đường này (không phải quan sát):

- Xác thực được chấp nhận (`authentication_accepted`): BM@WRAITH.CORP → EXTCA01.WRAITH.CORP = đúng.
- Có thể truy cập credential trên host (`credential_accessible`): EXTCA01.WRAITH.CORP → BM@WRAITH.CORP = đúng.
- Membership có hiệu lực (`membership_usable`): BM@WRAITH.CORP → DOMAIN ADMINS@WRAITH.CORP = đúng.
- Kết nối tới KDC (`network_kdc_reachable`): BM@WRAITH.CORP → EXTCA01.WRAITH.CORP = đúng.
- Nhóm dùng để cấp quyền bảo mật (`security_group`): BM@WRAITH.CORP → DOMAIN ADMINS@WRAITH.CORP = đúng.
- Session còn mới trong kịch bản snapshot tĩnh (`session_fresh`): EXTCA01.WRAITH.CORP → BM@WRAITH.CORP = đúng.
- Credential trong session dùng được để xác thực trong miền (`session_identity_usable`): EXTCA01.WRAITH.CORP → BM@WRAITH.CORP = đúng.
- Session vẫn còn trên host (`session_present`): EXTCA01.WRAITH.CORP → BM@WRAITH.CORP = đúng.

JSON đầy đủ giữ trace, provenance, ledger và các giới hạn để kiểm chứng.
