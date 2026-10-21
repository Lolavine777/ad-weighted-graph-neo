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

Lệnh tải hoặc kiểm tra SEAMLESS theo manifest, dựng snapshot, khai báo machine foothold và scenario assumptions, đối chiếu FIFO/goal-guided/neo-guided qua CLI, rồi kiểm native replay và parity API/CLI.
Scenario mặc định là `neo-standard-v1`: nhóm thiếu thuộc tính loại được giả định là
security group, kể cả tên DISTLIST; thuộc tính non-security và fact False vẫn chặn.
Các giả định được ghi rõ trong trace. Dùng `--scenario-policy seamless-standard-v1`
để tái lập scenario thận trọng của baseline cũ.
Dùng output directory mới cho mỗi lượt để giữ kết quả cũ.
Đọc `summary.json`; `neo_guided.json` giữ đầy đủ witness, assumptions, C ledger, Top-K và giới hạn.
Mở `neo_guided.md` để đọc bản tóm tắt tiếng Việt: nguồn–đích, hành động, C và giả định đã dùng.
Đây là benchmark một machine-to-DA query với ba techniques và cap 6.000 expansions.
Không phải chứng minh an toàn toàn miền hoặc phép so sánh BloodHound.

Runner mặc định dùng bảng `neo-c-v1`. Để đối chiếu bảng reset cũ:

```sh
.venv/bin/python -m scripts.neo_baseline --effort-profile reset-activation-c-v2 \
  --output-dir reports/generated/neo-reset-001
```

`neo-c-v1` gán C theo hành động reset, thêm membership, sửa ACL và thực thi host/WinRM,
kể cả khi quyền đến từ nhóm hoặc danh tính thu được giữa đường.
Membership có sẵn không thêm công sức; P/I không bắt buộc để có C.
Runner trên vẫn chỉ bật ba techniques của benchmark cũ;
dùng `scripts.exposure --effort-profile neo-c-v1` cho truy vấn nhiều techniques.
Profile neo mặc định xuất Top-3 theo C; thiếu P/I không loại đường đủ C.
Exposure chọn `neo_guided` khi dùng profile neo; catalog ngoài nhóm techniques hỗ trợ
sẽ ghi rõ fallback FIFO. `--search-order fifo` giữ cách tìm cũ.
Xem [bảng C và giới hạn](docs/neo.md#chi-phi-c-cho-neo).

Đối chiếu bộ 10 query trên snapshot vừa dựng; đổi `--max-paths 1` thành `3` để khảo sát nhiều đường:

```sh
.venv/bin/python -m scripts.neo_cohort \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --output-dir reports/generated/neo-cohort-001 --max-paths 1
```

## Query nhỏ có chi phí

```sh
.venv/bin/python -m src.engine query \
  --query tests/fixtures/query_cli/two-routes-query.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json \
  --ranking-query docs/research/ratings/week4/synthetic-a2-e.json \
  --label synthetic --output reports/generated/toy-query.json \
  --brief reports/generated/toy-query.md
```

## Các use case tiếp theo

Khảo sát mọi User/Computer đủ điều kiện của SEAMLESS tới DA/EA, mỗi nguồn là một
scenario độc lập có danh tính mạng dùng được (không gộp quyền):

```sh
.venv/bin/python -m scripts.neo_domain \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --output-dir reports/generated/neo-domain-001 --workers 4
```

Mặc định 1.024 expansions, 12 bước và một witness mỗi cặp; hết cap không phải
no-path. Thêm `--resume` để tiếp tục cùng scope, hoặc dùng `--max-cells` để chia lượt.
Đổi độ sâu bằng `--max-steps`; giới hạn quá ngắn có thể bỏ sót chuỗi hợp lệ.
`scope.json` giữ recipe/profile/source pins; `cells.jsonl` giữ kết quả và witness
với các facts đã dùng, được native replay kiểm tra. Không lưu lặp toàn bộ graph/facts
cho hàng nghìn query. Cần output directory mới khi đổi budget hoặc code.

- Một foothold → tự chọn mục tiêu quan trọng: [demo exposure](docs/research/awg-r04/DEMO.md).
- Nhiều nguồn độc lập → ưu tiên rủi ro, thử can thiệp và tìm bypass: [runner remediation](docs/research/awg-r04/DEMO.md).
- Thiết kế và giới hạn hiện tại, datasets, số đo và ưu tiên nghiên cứu: [ghi chú neo](docs/neo.md).
- [Đề bài gốc](docs/00_todo.md), [quy ước dữ liệu](data/README.md), [đóng góp và kiểm thử](CONTRIBUTING.md).

Raw data và output dẫn xuất nằm local trong `data/raw`, `data/processed`, `reports/generated` và không được commit.
Tài liệu cũ ghi nhận các giai đoạn nghiên cứu trước; không tự chuyển các approval hoặc số đo đó thành kết luận mới của neo.
