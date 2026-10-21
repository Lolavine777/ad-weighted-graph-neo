# ADR-0005: Chuan hoa moi truong runtime tren Python 3.14

- Ngay: 2026-09-14
- Trang thai: Accepted
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #18, Refs #10, Refs #5

## Boi canh

Repository ban đầu được cấu hình với Python 3.11 trong file `.python-version` và workflow CI `.github/workflows/ci.yml`.
Tuy nhiên, trong triển khai thực tế của dự án, danh mục phần mềm do IT quản lý (IT-managed software catalog) không cung cấp Python 3.11.
Điều này khiến các thành viên trong nhóm sử dụng máy tính do IT quản lý không thể cài đặt hoặc khởi tạo môi trường ảo theo baseline 3.11 cũ.
Đồng thời, Python 3.14 (`cpython-3.14.7`) cung cấp các cải tiến đáng kể về hiệu năng thông dịch, tối ưu hóa bộ nhớ và khả năng tương thích lâu dài.
Do đó, nhóm cần thống nhất nâng chuẩn runtime của dự án lên Python 3.14 để tháo gỡ rào cản môi trường và đồng bộ toàn bộ quy trình phát triển.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| 1. Giu nguyen bat buoc Python 3.11 | Khong can sua file cau hinh CI ban dau | Thanh vien dung may IT khong the dung moi truong do thieu package | Bao cao moi truong thanh vien |
| 2. Ho tro song song da phien ban (3.11 va 3.14) | Linh hoat tam thoi | Tang chi phi bao tri ma tran CI va tiem an sai lech hanh vi giua cac phien ban | Thao luan nhom |
| 3. Chuan hoa Python 3.14 lam baseline thong nhat duy nhat | Thao go dut diem rao can cap phat package cua IT, dong bo toan bo cong cu | Can cap nhat cau hinh repo, CI va toolchain | Kiem thu cuc bo 32/32 tests dat tren 3.14.7 |

## Quyet dinh va he qua

Chúng ta chọn phương án 3: Chuẩn hóa Python 3.14 làm runtime baseline thống nhất duy nhất của dự án.

1. **Lý do chính:**
   Ràng buộc cấp phát phần mềm từ danh mục do IT quản lý và định hướng sử dụng runtime hiện đại.
2. **Phân định phạm vi thực hiện (Scope Allocation):**
   Trong phạm vi PR #17, tài liệu ADR này ghi nhận quyết định thống nhất baseline Python 3.14.
   Việc triển khai kỹ thuật bao gồm cập nhật `.python-version`, `.github/workflows/ci.yml`, `pyproject.toml` (target Python 3.14, cấu hình Ruff, ghim phiên bản phụ thuộc) và tài liệu hướng dẫn môi trường được giao cho @nairyuuu thực hiện trong PR riêng theo Issue #18 để tránh xung đột nhánh.
3. **Đánh giá trạng thái kiểm thử và CI (Đã hoàn thành qua PR #19):**
   Toàn bộ bộ kiểm thử tự động (32 unit tests) cùng các công cụ kiểm tra chất lượng mã nguồn (`ruff check`, `yamllint`, `check_contract.py`, `check_repository.py`) đã được kiểm chứng chạy thành công 100% trên môi trường cục bộ Python 3.14.7.
   Phần triển khai kỹ thuật hạ tầng đã được @nairyuuu hoàn tất thông qua PR #19 (Refs #18) và đã chính thức sáp nhập vào nhánh `develop`.
   File `.python-version` của repository đã chuyển sang `3.14` và toàn bộ 5 workflow CI trên GitHub Actions (bao gồm runner Ubuntu và Windows) đã được xác nhận chạy kiểm thử trực tiếp trên Python 3.14 đạt trạng thái xanh 100%.
4. **Quản lý môi trường cục bộ:**
   Khuyến nghị toàn bộ thành viên sử dụng công cụ `uv` (`uv python install 3.14`, `uv venv`) để khởi tạo và quản lý môi trường ảo độc lập.

Hệ quả:
- Định hướng kỹ thuật của dự án hoàn toàn rõ ràng, loại bỏ tình trạng phân mảnh môi trường.
- Tránh được xung đột nhánh khi phát triển song song giữa hai thành viên.

## Kiem chung va dieu kien xem lai

- Lệnh kiểm tra cục bộ: `uv run pytest` và `uv run python scripts/check_repository.py`.
- Tiêu chí thành công: Đã đạt hoàn toàn (PR #19 đã được sáp nhập vào `develop` và toàn bộ workflow CI trên GitHub Actions chạy trực tiếp trên Python 3.14 đạt 100% xanh ở cả Ubuntu và Windows).
- Điều kiện xem lại: Khi có phiên bản Python mới hơn được hạ tầng IT phê duyệt hoặc khi phát sinh vấn đề tương thích thư viện trong các mốc tiếp theo.
