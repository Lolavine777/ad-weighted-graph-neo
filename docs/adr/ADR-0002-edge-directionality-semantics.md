# ADR-0002: Chuan hoa ngu nghia huong chuyen quyen tren do thi tan cong

- Ngay: 2026-09-14 (Chuan hoa trang thai: 2026-09-22)
- Trang thai: Accepted (historical directionality decision; status reconciled in Issue #83)
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #1, Refs #5, Refs #83

> [!NOTE]
> **Acceptance Reconciliation (Issue #83):**
> Quyết định chuẩn hóa hướng cạnh theo luồng chiếm quyền (Exploit Flow $Source \to Target$) đã được nghiệm thu và áp dụng như một bất biến cốt lõi (immutable invariant) trong toàn bộ hệ thống.
> Bất biến này được ràng buộc chặt chẽ trong Graph Contract 1.0.0 (`configs/contract.yml`), mã nguồn parser (`src/parser/__init__.py`), danh mục Attack Semantics (`configs/attack_semantics.yml`), và bộ kiểm thử hồi quy (`tests/test_contract.py`, `tests/test_attack_semantics_catalog.py`).
> Trạng thái được cập nhật chính thức thành `Accepted` phản ánh thực tế triển khai và kiểm chứng.

## Boi canh

Trong cơ sở dữ liệu Active Directory và các tệp tin xuất ra từ BloodHound, dữ liệu được tổ chức theo góc nhìn quản trị đối tượng.
Ví dụ: Một đối tượng Group lưu danh sách các thành viên trong mảng `Members[]`.
Một đối tượng Computer lưu danh sách các phiên đăng nhập trong `Sessions[]` hoặc `RegistrySessions[]`.
Nếu parser nạp nguyên trạng cấu trúc này mà không chuẩn hóa ngữ nghĩa tấn công, đồ thị sẽ bị đi ngược hướng dòng điều khiển.
Chúng ta cần quy định chuẩn mực về hướng có hướng ($Source \to Target$) cho tất cả các loại cạnh.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| 1. Giu nguyen huong luu tru LDAP | Parser don gian, khong can dao chieu | Do thi sai ngu nghia tan cong, Dijkstra khong the tim dung | Kiem thu thuc te |
| 2. Chuan hoa huong theo luong chiem quyen (Exploit Flow) | Dung ban chat dot pha va leo thang dac quyen | Can viet adapter xu ly rieng cho tung loai quan he | BloodHound OpenGraph spec |

## Quyet dinh va he qua

Chúng ta chọn phương án 2: Toàn bộ cạnh trong đồ thị phải biểu diễn hướng dòng kiểm soát ($A \to B$ nghĩa là kẻ tấn công kiểm soát $A$ sẽ có khả năng kiểm soát hoặc truy cập $B$).

Quy tắc chuẩn hóa cụ thể cho 8 cạnh M1:
1. **`MemberOf` ($User/Group \to Group$):**
   Mặc dù LDAP lưu `Group.member = User`, hướng tấn công là $User \to Group$.
   Kẻ tấn công chiếm tài khoản người dùng sẽ thừa hưởng toàn bộ token và đặc quyền của nhóm đó.
2. **`HasSession` ($Computer \to User$):**
   Mặc dù máy tính ghi nhận người dùng đăng nhập, hướng tấn công là $Computer \to User$.
   Kẻ tấn công phải có quyền Local Admin / SYSTEM trên máy tính trước, sau đó trích xuất bộ nhớ LSASS hoặc mạo danh token để chiếm tài khoản người dùng đang mở phiên.
3. **Quyền truy cập máy trạm (`AdminTo`, `CanRDP`, `CanPSRemote`):**
   Hướng là $User/Group/Computer \to Computer$.
   Chủ thể nắm giữ quyền điều khiển hoặc mở phiên từ xa tới máy trạm mục tiêu.
4. **Quyền DACL (`GenericAll`, `WriteDacl`, `ForceChangePassword`):**
   Hướng là $Principal \to Target$.
   Chủ thể nắm quyền (Principal) thực thi hành vi leo quyền trên đối tượng đích (Target).

Hệ quả:
- Parser tại `src/parser/` phải ánh xạ đúng `source` và `target` theo quy tắc trên khi đọc JSON.
- Bộ test fixture tại `tests/` phải xác minh chiều của `HasSession` là từ Computer sang User.

## Kiem chung va dieu kien xem lai

- Lệnh kiểm tra: `pytest tests/test_contract.py`.
- Tiêu chí thành công: Các cạnh `HasSession` có `source.kind == "Computer"` và `target.kind == "User"`.
- Điều kiện xem lại: Khi phát hiện trường hợp leo quyền ngược từ User ép máy tính kết nối ngược lại (coercion attack như PetitPotam/PrinterBug).
