# Quy ước dữ liệu

`raw/`: JSON nguồn GOADv2/AD ẩn danh, không sửa tại chỗ. `processed/`: graph và kết quả chuẩn hóa có thể tạo lại. Cả hai được ignore, không phụ thuộc dung lượng. `samples/`: chỉ chứa dữ liệu tổng hợp nhỏ, kiểm tra bằng mắt trước khi commit.

Lưu checksum, snapshot, phiên bản export và vị trí truy cập được cấp phép trong manifest của nhóm. Không đưa tên miền, SID thật, username, session, IP hoặc bản đồ quyền thực vào fixture, notebook output, issue, PR hay ảnh chụp. Giữ kết quả dẫn xuất tại `reports/generated/` cho tới khi có bản phù hợp chia sẻ.

Git ignore không bảo vệ file đã được track hoặc bị force-add. CI chặn đường dẫn raw/processed/generated đã đưa vào repo (trừ README), nhưng không nhận diện nội dung AD ở nơi khác. Kiểm tra `git diff --cached` trước commit. Không dùng Git LFS như cách đưa dữ liệu riêng lên GitHub; thống nhất nơi lưu riêng với mentor.

## Snapshot manifest

Dùng [quy trình snapshot manifest](../docs/snapshot-manifest.md) để generate/verify
checksum và tạo tham chiếu provenance ổn định trực tiếp từ thư mục raw gốc, không cần
copy hoặc tách file. Với nhiều collector/run, đặt collector cấp snapshot là `mixed`
và dùng `--file-metadata` để ghi collector/thời gian thu thập chính xác trên từng file.

Lưu manifest vận hành trong `data/processed/`, ngoài snapshot root. Thư mục output
phải tồn tại. Ví dụ chỉ dùng [dữ liệu tổng hợp](samples/snapshot-input/nested/café%20file.txt):

```bash
python scripts/snapshot_manifest.py generate data/samples/snapshot-input --output data/processed/demo-manifest.json --dataset-id synthetic-v1 --collector-name synthetic --collector-version 1.0 --collected-at 2026-01-01T00:00:00Z
python scripts/snapshot_manifest.py verify data/samples/snapshot-input data/processed/demo-manifest.json
```

Verify trước khi parser chạy và giữ snapshot bất biến trong suốt quá trình xử lý.
Nếu dữ liệu thay đổi có chủ đích, tạo snapshot và manifest mới; không sửa raw tại chỗ
hoặc tự cập nhật manifest để che mất khác biệt. Metadata chưa biết phải ghi `unknown`
qua CLI, không lấy thời gian filesystem làm thời gian thu thập.

Chỉ chia sẻ manifest sau khi kiểm tra cả tên file và metadata không chứa định danh AD,
vị trí truy cập nội bộ hoặc token. Manifest không thay thế data inventory hoặc chính
sách cấp quyền; không tự động anonymize tên file. Manifest thật mặc định giữ local;
repo chỉ có [manifest mẫu tổng hợp](samples/manifests/synthetic-v1.json).
`raw_file` dùng `snapshot:<digest>/<relative_path>` và registry local, không lưu absolute path.
