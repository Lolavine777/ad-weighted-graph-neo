# AD Weighted Graph neo

Từ một User hoặc Computer bị chiếm, tìm đường tấn công có điều kiện tới tài sản quan trọng, giải thích công sức C và kiểm tra đường thay thế sau remediation.
Repo này dùng lịch sử Git mới và workflow cá nhân.
Parser, taxonomy, semantic planner và nghiên cứu AD được tái sử dụng; evidence lịch sử được giữ nguyên để đối chiếu.

C là công sức ordinal theo scenario, không phải thời gian khai thác thực tế.
Kết quả bị giới hạn tìm kiếm là best-found; chỉ gọi minimum khi engine có bằng chứng trong scope đã khai báo.
P/I thiếu vẫn được hiển thị là chưa chấm.
Quyền điều khiển máy không tự cấp danh tính mạng của tài khoản máy.

## Cài đặt

Cần Python 3.14 và uv.

```sh
uv venv --python 3.14 .venv
uv pip sync --python .venv/bin/python requirements-neo.lock
```

## SEAMLESS → foothold → Domain Admins → attack path

```sh
.venv/bin/python -m scripts.neo_baseline --output-dir reports/generated/neo-run-001
```

Lệnh tải hoặc kiểm tra SEAMLESS theo manifest, dựng snapshot, khai báo machine foothold và scenario assumptions, chạy FIFO/goal-guided qua CLI, rồi kiểm native replay và parity API/CLI.
Dùng output directory mới cho mỗi lượt để giữ kết quả cũ.
Đọc `summary.json`; `goal_guided.json` giữ đầy đủ witness, assumptions, C ledger, provenance và giới hạn.
Đây là benchmark một machine-to-DA query với ba techniques và cap 6.000 expansions.
Không phải chứng minh an toàn toàn miền hoặc phép so sánh BloodHound.

## Query nhỏ có chi phí

```sh
.venv/bin/python -m src.engine query \
  --query tests/fixtures/query_cli/two-routes-query.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json \
  --ranking-query docs/research/ratings/week4/synthetic-a2-e.json \
  --label synthetic --output reports/generated/toy-query.json
```

## Các use case tiếp theo

- Một foothold → tự chọn mục tiêu quan trọng: [demo exposure](docs/research/awg-r04/DEMO.md).
- Nhiều nguồn độc lập → ưu tiên rủi ro, thử can thiệp và tìm bypass: [runner remediation](docs/research/awg-r04/DEMO.md).
- Thiết kế và giới hạn hiện tại, datasets, số đo và ưu tiên nghiên cứu: [ghi chú neo](docs/neo.md).
- [Đề bài gốc](docs/00_todo.md), [quy ước dữ liệu](data/README.md), [đóng góp và kiểm thử](CONTRIBUTING.md).

Raw data và output dẫn xuất nằm local trong `data/raw`, `data/processed`, `reports/generated` và không được commit.
Tài liệu cũ ghi nhận các giai đoạn nghiên cứu trước; không tự chuyển các approval hoặc số đo đó thành kết luận mới của neo.
