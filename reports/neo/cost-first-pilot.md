# C-first thuần chưa phù hợp để thay search neo

Ngày 2026-10-23, từ `main@f8e6aaf`. **Giữ nguyên engine và mặc định trên main.**
Pilot tìm đúng đường rẻ trước trong mô hình nhỏ, nhưng làm mất witness trong budget
trên dữ liệu thật. Không đưa thuật toán thử nghiệm vào core chỉ vì kết quả toy tốt.

Code được giữ tại [commit thử nghiệm 7a85f09](https://github.com/Lolavine777/ad-weighted-graph-neo/commit/7a85f09abd8e24beeda287182124a76ff6b06d0f),
nhánh `experiment/neo-cost-first-20261023`; [summary có checksum](cost-first-pilot.json)
ghi đủ các lượt đo và source pin. Đây là kết quả âm của một pilot, không phải regression của main.

## Đã thử gì

Thêm thứ tự `neo_cost` riêng trên nhánh thử nghiệm, dùng đúng techniques và rubric
`neo-c-v1` hiện có. Ưu tiên tổng C của tập công việc đã trả; topology chỉ phá hòa.
Hành động C=0 vẫn được xét. Witness được lấy khỏi hàng đợi theo C, không trả ngay
khi vừa sinh ra một đích có giá cao hơn nhánh còn chờ.

Planner, gates, AttackState, preset, raw importer và giá từng hành động không được
nới để cải thiện kết quả. Query tự sửa bảng C hoặc thêm work/preparation registry
không được dùng chế độ thử nghiệm này. Không gộp các trạng thái chỉ theo AD node.
Các witness sinh được đều qua native replay và bộ chấm C công khai hiện tại.
Nhánh thử nghiệm vẫn giữ mặc định cũ; muốn dùng C-first phải chọn rõ `neo_cost`.

## Mô hình có đáp án tính tay

| Ca, cap 1 witness | Neo guided | C-first |
| --- | --- | --- |
| Hai đường, minimum C=1 | C=3, 3 expansions | **C=1, 5 expansions** |
| Membership có sẵn, minimum C=0 | C=3, 3 expansions | **C=0, 3 expansions** |
| Authentication False trên nhánh rẻ | C=3 | C=3; giữ veto |
| Authentication Unknown trên nhánh rẻ | C=3, chưa chứng minh minimum | C=3, chưa chứng minh minimum |

Ở cap đủ duyệt hết, cả hai giữ nguyên tập chương trình và C:
56 chương trình/110 expansions cho ca hai đường; 20/68 cho từng ca authentication;
20/38 cho membership miễn phí. C của từng chương trình khớp phép tính độc lập.
Ca Unknown vẫn không có chứng minh minimum. Khi còn nhánh chưa xét do cap,
engine không nâng kết quả thành minimum đã chứng minh dù witness đầu khớp đáp án.

## Dữ liệu thật: cùng scope và ngân sách

Giữ source/target và scenario của bộ đối chứng đã công bố. Thử cap **1 và 10 witness**,
cùng 12 bước semantic và 4.096 expansions/query. Không chạy lại BloodHound/Docker.

| Phạm vi pilot | Neo guided | C-first | C khi cả hai cùng có witness |
| --- | --- | --- | --- |
| SEAMLESS: cặp đầu cố định SCOTTY_HARTMAN→DA | 1/1, C=2 | 0/1, hết cap | Không so được |
| WRAITH chính: 10 cặp | **8/10** | **6/10** | Giữ nguyên |
| WRAITH session: 6 cặp | **6/6** | **6/6** | Giữ nguyên |

Bảng đúng ở cả hai cap witness. WRAITH session trùng hai cặp EXTDC01 với nhóm chính;
không cộng trực tiếp thành số cặp duy nhất. Đây không phải một lần khảo sát SEAMLESS
toàn miền hoặc phép đo mới cho toàn bộ cohort 24 cặp lịch sử.

SEAMLESS SCOTTY→DA: guided cần 20 expansions ở cap 1, 109 ở cap 10, đều có C=2.
C-first dùng đủ 4.096 expansions nhưng chưa có witness ở cả hai cap; **không có
Unknown attempt**. Đây là vấn đề thứ tự tìm kiếm trong ngân sách, không phải thiếu RAM
hoặc không tồn tại đường. Các lượt này đều kết thúc theo expansion cap.

WRAITH: C-first bỏ lỡ hai cặp RODCMANAGER→DA/EA mà guided tìm C=3 sau 7 expansions
ở cap 1, 35 ở cap 10. Mỗi query C-first hết 4.096 expansions và gặp 210 lần thử
`directory_write_allowed` Unknown ở nhánh phụ. Cả hai query guided không có Unknown.
Hai cặp TARGETCOMPUTERC vẫn không có witness ở cả hai cách theo preset local-admin-only.
Nhóm session giữ C=2; TRUSTER giữ C=3. Không có ca thật cả hai cùng tìm được mà C-first
cho C tốt hơn trong lượt đo này; cũng không có lỗi rating hay witness replay.

Nguyên nhân: tổng C đã trả là cận dưới hữu ích trên ca nhỏ, nhưng nhiều nhánh chi phí
thấp chưa dẫn tới mục tiêu được xét trước một đường hữu ích có giá cao hơn. Pilot
chưa có cơ chế loại các tổ hợp tương đương; không thêm một mô hình state mới để cứu
kết quả trong lượt này. Kết quả đã đủ để bác bỏ việc thay mặc định bằng C-first thuần.
Batch SEAMLESS rộng hơn được dừng sau khi thấy hồi quy; các dòng partial không được
trộn vào summary chính. Lần tái lập hoàn chỉnh chỉ lấy đúng cặp đầu đã nêu.

## Kiểm tra và tái lập

**430 tests liên quan pass**, gồm 14 test mới cho cost order, gates, zero-cost,
program-set parity, host/session, cap và profile không khớp. Ruff, kiểm tra repository
và contract pass. Chưa chạy full suite; không sửa các pin/catalog lịch sử để làm xanh suite.
Đã nhập lại 37 file raw theo manifest: WRAITH có 150 nodes/770 edges, AdminTo=22;
SEAMLESS có 3.370 nodes/56.367 edges. Summary giữ hash snapshot và report từng run.

Checkout commit thử nghiệm, cài theo README, rồi chạy từ repo root:

```sh
.venv/bin/python -m scripts.neo_cost_probe --output-dir reports/generated/cost-finite-repeat
.venv/bin/python -m scripts.neo_cost_probe \
  --seamless-snapshot PATH_TO_SEAMLESS_SNAPSHOT --pair-limit 1 \
  --output-dir reports/generated/cost-seamless-repeat
.venv/bin/python -m scripts.neo_cost_probe \
  --wraith-snapshot PATH_TO_CURRENT_WRAITH_SNAPSHOT \
  --output-dir reports/generated/cost-wraith-repeat
```

Snapshot phải được dựng bằng importer hiện tại; WRAITH chọn export `20240305111414`
như [recipe LocalGroup](localgroup-fix.md#kiểm-chứng-và-tái-lập).
Runner lưu query, hash, C từng candidate và witness tốt nhất trong output; replay
từng chương trình sinh được. Dùng output directory mới. Evidence lớn và raw không commit.
Thời gian là đo đơn lẻ trên môi trường hiện tại, không dùng để kết luận hiệu năng
ổn định hay so tốc độ với BloodHound.

Hướng kế tiếp nếu tiếp tục minimum-C: giữ witness của guided làm kết quả ban đầu,
rồi thử tìm đường rẻ hơn trong ngân sách còn lại. Chỉ chấp nhận vào core nếu giữ được
các witness đã có và đem lại lợi ích trên dữ liệu thật. Yêu cầu minimum trên dữ liệu
thật hiện vẫn chưa khép; kết quả capped trên main tiếp tục là best-found.
