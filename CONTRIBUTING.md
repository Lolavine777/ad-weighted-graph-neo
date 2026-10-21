# Làm việc với AWG neo

Dùng workflow cá nhân: thay đổi nhỏ, kiểm chứng hành vi thực tế, ghi đủ lệnh và giới hạn để tái lập.
Không cần nhánh develop, quy trình A/B hoặc nhật ký công việc cho mỗi thay đổi.
Có thể làm trên nhánh ngắn hoặc commit trực tiếp khi đã kiểm tra.

## Kiểm tra local

```sh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m yamllint .
.venv/bin/python scripts/check_repository.py
.venv/bin/python scripts/check_contract.py
.venv/bin/python -m pytest -q
```

Chạy thêm E2E hoặc benchmark phù hợp khi thay đổi parser, semantics, search, rating hoặc remediation.
Giữ các trường hợp thiếu dữ liệu, fact False và assumption tách biệt.
Không dùng truncated/no witness để kết luận không có đường.

## Dataset và evidence

Giữ raw bất biến, kiểm checksum trước xử lý và ghi output mới vào `reports/generated`.
Không commit credentials, dữ liệu AD thực hoặc logs chưa kiểm tra.
Không sửa thủ công artifact tự sinh hoặc evidence lịch sử để làm test pass.
Tạo baseline neo mới bằng công cụ sinh khi source hoặc context thay đổi; không chuyển authority của kết quả lịch sử sang context mới.

## Remote

`origin` trỏ tới repo neo private.
`upstream` chỉ dùng để đọc và có push URL `disabled://upstream-read-only` trong checkout migration.
Một clone mới cần tự cấu hình lại khóa push nếu thêm upstream.
Không force push để ghi đè thay đổi trên remote.
