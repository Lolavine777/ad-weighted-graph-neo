# AD Weighted Graph neo

neo cho biết từ một tài khoản hoặc máy bị chiếm, kẻ tấn công đi tới Domain Admins theo những đường nào, tốn bao nhiêu công sức, và gỡ quan hệ nào thì đường đó hết.
Đầu vào là dữ liệu BloodHound thu bằng SharpHound hoặc BloodHound.py.

> **English summary.** neo finds attack paths in Active Directory from BloodHound data, scores each path by attacker effort (C), and tests a remediation by searching again from scratch.
> Run the local app with `.venv/bin/python -m scripts.neo_app`, or [open the read-only demo](https://lolavine777.github.io/ad-weighted-graph-neo/).
> This is my undergraduate thesis project; the documentation is in Vietnamese.

## Dùng thử

[Bản xem mẫu](https://lolavine777.github.io/ad-weighted-graph-neo/) chạy ngay trên trình duyệt, không cần cài đặt.

Để phân tích dữ liệu của bạn, cần Python 3.14 và [uv](https://docs.astral.sh/uv/):

```sh
uv venv --python 3.14 .venv
uv pip sync --python .venv/bin/python requirements-neo.lock
.venv/bin/python -m scripts.download_ad_sampledata
.venv/bin/python -m scripts.neo_app
```

Lệnh cuối mở ứng dụng trong trình duyệt.
Ứng dụng chỉ chạy trên máy này và không kết nối tới Active Directory.
Trên Windows, thay `.venv/bin/python` bằng `.venv\Scripts\python`.

## Cách dùng

1. Chọn một bản xuất trong `data/raw`, hoặc mở tệp `.zip` của BloodHound. Phần bên phải cho biết những gì đã đọc và đã bỏ qua.
2. Tìm tài khoản, máy hoặc nhóm theo tên. Bấm đúp một đối tượng để mở rộng các quan hệ quanh nó.
3. Chọn **Xuất phát từ đây**, chọn giả định và mục tiêu, rồi bấm **Tìm đường**.
4. Bấm một bước trên đường rồi chọn **Gỡ thử quan hệ này**. neo dựng lại đồ thị, tìm lại từ đầu và cho biết còn đường vòng hay đã chặn.
5. Bấm **Tìm điểm nghẽn** để xem quan hệ nào nằm trên nhiều đường nhất, và gỡ nó thì được bao nhiêu nguồn.

Ví dụ trên WRAITH: từ `EXTCA01` tới Domain Admins có đường C=2 qua phiên của `BM`.
Gỡ `BM` khỏi Domain Admins thì vẫn còn đường vòng với C=5; gỡ phiên của `BM` trên `EXTCA01` thì `EXTCA01` hết đường.

## C là gì

C cộng điểm các việc kẻ tấn công phải chủ động làm: đặt lại mật khẩu, sửa danh sách quyền, thêm thành viên nhóm, thực thi trên máy, dùng lại phiên đăng nhập.
Quyền có sẵn nhờ thuộc nhóm không tốn điểm.
C dùng để so sánh các đường với nhau; nó không phải số phút hay xác suất.
[Bảng điểm và lý do chọn mức](docs/neo.md#chi-phi-c-cho-neo) nằm trong ghi chú thiết kế.

## Kết quả

| Bộ dữ liệu | Kết quả | Số liệu |
| --- | --- | --- |
| SEAMLESS, 2.590 nguồn tới DA và EA | 5.171/5.180 cặp có đường và C | [domain-discovery-fix.json](reports/neo/domain-discovery-fix.json) |
| Đối chứng với BloodHound CE, 24 cặp | Cùng có đường ở 22/24 cặp | [localgroup-fix.md](reports/neo/localgroup-fix.md) |
| WRAITH, ba can thiệp | Hai còn đường vòng, một chặn được nguồn đang xét | [remediation-rediscovery-results.json](reports/neo/remediation-rediscovery-results.json) |
| GoodHound, 10 cặp | Không cặp nào có đường | [goodhound-evaluation.md](reports/neo/goodhound-evaluation.md) |
| WRAITH, NORTH và SEAMLESS trên ứng dụng | Điểm nghẽn, C so với số bước, hiệu năng | [workspace-evaluation.json](reports/neo/workspace-evaluation.json) |

## Dòng lệnh

Các lệnh dưới đây tái lập số liệu trong khóa luận.
Chúng đọc nghiêm ngặt: bản ghi lạ làm dừng lượt chạy, nên cần bản kê dữ liệu đã có trong repo.

```sh
# Một nguồn trên SEAMLESS, tải dữ liệu nếu chưa có
.venv/bin/python -m scripts.neo_baseline --output-dir reports/generated/neo-run-001

# Mọi nguồn SEAMLESS tới DA và EA
.venv/bin/python -m scripts.neo_domain --snapshot reports/generated/neo-run-001/snapshot.json \
  --output-dir reports/generated/neo-domain-001 --workers 4

# Ba can thiệp trên WRAITH
.venv/bin/python -m scripts.neo_import --raw-dir data/raw/ad_sampledata \
  --manifest data/samples/manifests/ad-sampledata-v1.json \
  --time-policy data/samples/time-policies/ad-sampledata-v1.json \
  --export-prefix 20240305111414 --output-dir reports/generated/neo-inputs/wraith
.venv/bin/python -m scripts.neo_remediation \
  --snapshot reports/generated/neo-inputs/wraith/snapshot.json \
  --output-dir reports/generated/neo-remediation-001

# Đánh giá ứng dụng: điểm nghẽn, C so với số bước, hiệu năng
.venv/bin/python -m scripts.neo_evaluation
```

Kết quả dòng lệnh dạng JSON mở được bằng nút **Mở JSON**; [hướng dẫn](web/neo-viewer/README.md) ghi rõ định dạng nào mở được.

## Phạm vi

neo xét 11 kỹ thuật chủ động trong một miền, trên ảnh chụp dữ liệu tĩnh.
Ủy quyền Kerberos, AD CS, GPO và đường qua nhiều miền chưa nằm trong danh mục.
Khi hết ngân sách tìm kiếm, C là mức tốt nhất đã tìm; nó chỉ được gọi là nhỏ nhất khi đã duyệt hết.
Bản dùng trong khóa luận được đánh dấu bằng tag; số liệu và phiên bản mã của từng lượt chạy nằm trong tệp kết quả tương ứng.

## Tài liệu

- [Ghi chú thiết kế](docs/neo.md): mô hình, bảng C và dữ liệu.
- [Hướng dẫn giao diện](web/neo-viewer/README.md): các màn hình và định dạng tệp.
- [Đóng góp và kiểm thử](CONTRIBUTING.md), [quy ước dữ liệu](data/README.md), [đề bài gốc](docs/00_todo.md).
- [Nghiên cứu nền](docs/research/) và [số liệu các lượt chạy](reports/neo/).

## Giấy phép

Mã nguồn phát hành theo [giấy phép MIT](LICENSE).
Các bộ dữ liệu bên thứ ba (SEAMLESS, WRAITH, GoodHound, NORTH) thuộc giấy phép của nguồn gốc.
NORTH là bản xuất của lab GOADv2 lấy từ [m4lwhere/Bloodhound-CE-Sample-Data](https://github.com/m4lwhere/Bloodhound-CE-Sample-Data) (Unlicense).
