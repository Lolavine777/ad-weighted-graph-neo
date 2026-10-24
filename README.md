# AD Weighted Graph neo

Từ một User hoặc Computer bị chiếm, tìm đường tấn công có điều kiện tới tài sản quan trọng, giải thích công sức C và kiểm tra đường thay thế sau remediation.
Repo này dùng lịch sử Git mới và workflow cá nhân.
Parser, taxonomy, semantic planner và nghiên cứu AD được tái sử dụng; evidence lịch sử được giữ nguyên để đối chiếu.

Hướng khóa luận: phân tích đường leo thang đặc quyền có xét chi phí và kiểm chứng
biện pháp giảm thiểu. Phải đánh giá ngoài SEAMLESS và đo ưu thế trên cùng phạm vi
với BloodHound; chưa coi “tốt hơn BloodHound” là kết luận đã có.
[Kết quả ngoài SEAMLESS và tiêu chí đánh giá](reports/neo/transfer-brief.md):
đã chạy GHOST/WRAITH với cùng bảng C; có ca C=3 và can thiệp được kiểm chứng.
PHANTOM còn lỗi đầu vào; đối chứng BloodHound CE live đã hoàn tất trên bộ nhỏ cố định.
[Bộ đối chứng cố định và cách chạy](reports/neo/bloodhound-comparison.md)
ghi nhận trước sửa: BloodHound 22/24 và neo 20/24 cặp có đường, cùng các bypass sau can thiệp.
[Bản sửa LocalGroup theo host](reports/neo/localgroup-fix.md) khép lỗi nhập liệu đã đo: neo đạt 22/24, TRUSTER→DA/EA có C=3, giữ nguyên các kết quả cũ.
[Kiểm lại remediation sau sửa](reports/neo/remediation-post-localgroup.md) xác nhận ba kết quả cũ; TRUSTER còn bypass qua UNCON khi chỉ bỏ session BM trên EXTCA01.
[Độ nhạy bảng C](reports/neo/cost-sensitivity.md) đã đo trên 220 quan sát chương trình theo cặp; Top-3 có thể đổi do ties, kết quả chỉ áp dụng trong candidate set đã tìm được.
[Protocol holdout](reports/neo/holdout-evaluation-protocol.md) chốt đánh giá trên môi trường chưa dùng để chỉnh neo; chưa có kết quả holdout.
[Kiểm tra toàn bộ regression](reports/neo/full-suite-validation.md): 3.852 tests và 99 subtests pass trong worktree cố định, 8 skips; giữ nguyên evidence và phạm vi rating lịch sử.

C là công sức ordinal theo scenario, không phải thời gian khai thác thực tế.
Kết quả bị giới hạn tìm kiếm là best-found; chỉ gọi minimum khi engine có bằng chứng trong scope đã khai báo.
[Thử nghiệm minimum-C có đáp án tính tay](reports/neo/minimum-probe.md)
cho thấy đường đầu C=3 có thể bỏ sót đường dài hơn C=1; tăng cap tìm được minimum
trong mô hình nhỏ, chưa giải yêu cầu minimum trên dữ liệu thật.
[Pilot C-first trên dữ liệu thật](reports/neo/cost-first-pilot.md) không được đưa
vào core: có cải thiện ở mô hình nhỏ nhưng làm giảm số cặp có witness trong budget.
P/I thiếu vẫn được hiển thị là chưa chấm.
Quyền điều khiển máy không tự cấp danh tính mạng của tài khoản máy.

## Cài đặt

Cần Python 3.14 và uv.

Chạy các lệnh từ thư mục gốc repo. Dùng thư mục output mới cho mỗi lượt;
raw đã đúng manifest có thể được tái sử dụng mà không tải lại.

```sh
uv venv --python 3.14 .venv
uv pip sync --python .venv/bin/python requirements-neo.lock
```

[Biên bản kiểm chứng cài mới](reports/neo/clean-checkout-results.json)
ghi môi trường, checksum, kiểm thử và các demo đã tái lập.

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

Để tìm đường rẻ hơn sau khi đã có witness, chọn `neo_refine`. Chế độ này dùng
guided trước, rồi tìm cải tiến C trong phần ngân sách còn lại; chỉ giữ cải tiến
nghiêm ngặt và không làm mất kết quả tốt nhất ban đầu. Ví dụ một nguồn SEAMLESS:

```sh
.venv/bin/python -m scripts.neo_domain \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --source S-1-5-21-1271839998-3495686680-2211690266-1815 \
  --search-order neo_refine --max-paths 10 --max-expansions 256 --workers 1 \
  --output-dir reports/generated/neo-refine-demo
```

[Kết quả kiểm chứng](reports/neo/refinement-results.json): cùng cap 256 expansions,
giữ 22/24 cặp có witness, hai cặp SEAMLESS giảm C=2→1 ở cả cap 1 và 10 witness.
451 test liên quan pass; đã replay 528 chương trình thật và chạy CLI/worker E2E.
[Lượt full suite sau đó](reports/neo/full-suite-validation.md) đã bao gồm mã refinement.
Refinement tốn thêm lượt tìm kiếm; mặc định vẫn `neo_guided`.
Chỉ áp dụng với bảng `neo-c-v1` chuẩn và techniques neo hỗ trợ. Khi còn cap/gap,
kết quả vẫn là best-found, không tự nâng thành minimum đã chứng minh.

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

## Các use case

Use case 1, một máy đã bị chiếm với quyền local admin (preset local-admin-only):

```sh
.venv/bin/python -m scripts.neo_domain \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --scenario host-compromise --source COMPUTER_ID \
  --output-dir reports/generated/neo-host-001 --workers 1
```

Thay `COMPUTER_ID` bằng ID máy trong snapshot. Neo tự tìm tới DA/EA và xuất
`goal-*.md` giải thích đường, C và các giả định. Kịch bản này giả định các session
được báo cáo còn mới và có credential dùng được; host có quyền admin mới dùng được
session. C cho lấy credential và xác thực là 2 theo rubric neo, chưa phải số đo thực tế.
Không tự biến quyền local admin thành danh tính mạng của tài khoản máy.
User source vẫn bắt đầu bằng danh tính User dùng được. Bỏ `--source` để chạy các
nguồn độc lập; giữ `--scenario identity` để tái lập cấu hình khảo sát danh tính mạng.
CLI và brief nêu quyền ban đầu cùng số cạnh session trước khi diễn giải kết quả.
Raw SEAMLESS không có session: dùng bộ này cho đường quyền/C; WRAITH kiểm chứng
nhánh host/session. [Lượt kiểm tra SEAMLESS](reports/neo/seamless-host-check.json)
giữ riêng kết quả local-admin-only và danh tính tài khoản máy.

Use case 2, sửa một membership/session rồi tìm lại bypass tới DA/EA, không cần Docker:

```sh
.venv/bin/python -m scripts.download_ad_sampledata
.venv/bin/python -m scripts.neo_import \
  --raw-dir data/raw/ad_sampledata \
  --manifest data/samples/manifests/ad-sampledata-v1.json \
  --time-policy data/samples/time-policies/ad-sampledata-v1.json \
  --export-prefix 20240305111414 --output-dir reports/generated/neo-inputs/wraith
.venv/bin/python -m scripts.neo_remediation \
  --snapshot reports/generated/neo-inputs/wraith/snapshot.json \
  --output-dir reports/generated/neo-remediation-demo-001
```

Các bước trên tải bộ lab public đã pin, kiểm 31 file theo manifest rồi dựng snapshot WRAITH bằng parser hiện tại.
Nếu đã có raw đúng manifest, downloader chỉ kiểm lại; có thể dùng `--raw-dir` khi dữ liệu nằm ở nơi khác.
Đọc `reports/generated/neo-remediation-demo-001/results.json`: mỗi hàng giữ case,
trước/sau, strategy và kết luận `bypass`, `blocked_in_scope` hoặc `inconclusive`.
Runner đối chiếu bản dựng nền với snapshot, sửa bản sao record trong bộ nhớ và dùng lại parser để cập nhật cả cạnh suy diễn.
Chạy độc lập đúng ba can thiệp với cả `neo_guided`/`neo_refine`, cùng preset host/session, techniques, bảng `neo-c-v1` và budget 10 programs / 12 steps / 4.096 expansions.
Mỗi lượt tìm mới từ foothold ban đầu; mọi witness được replay và đối chiếu C với ledger.

| Can thiệp và nguồn | C DA/EA trước | C DA/EA sau, cả hai strategy | Kết luận và giới hạn |
| --- | --- | --- | --- |
| RODCMANAGER, gỡ Administrators | 3 / 3 | 3 / 3 | Còn bypass; C best-found |
| EXTCA01, bỏ session BM | 2 / 2 | Không có / Không có | Đã chặn trong scope, 3 expansions/đích, không truncated |
| EXTCA01, gỡ BM khỏi DA | 2 / 2 | 5 / 2 | Còn bypass; refine tới DA hết 4.096 expansions, C best-found |

[Kết quả và hash evidence](reports/neo/remediation-rediscovery-results.json): 24 lượt, 200 witness replay/ledger hợp lệ.
Đã sửa cách dựng graph remediation của demo: gỡ BM→DA cũng bỏ hai AdminTo phụ thuộc và bỏ nhánh suy diễn qua DA trên EXTDC01, giữ hỗ trợ qua EA.
Session EXTCA01→BM có ba observation trùng nguồn hỗ trợ; demo bỏ cả hai PrivilegedSessions và một RegistrySessions.
Evidence lớn nằm trong `reports/generated/neo-remediation-rediscovery-20261023-verified/`; BloodHound chỉ là baseline lịch sử, không chạy lại.
Không có âm tính chưa kết luận trong ba ca này; chưa chứng minh C tối thiểu cho các ca thành công vì còn cap.
Riêng refine trước can thiệp RODCMANAGER có 210 Unknown/đích ở `directory_write_allowed`; các nhánh này còn thiếu điều kiện, witness C=3 vẫn replay hợp lệ.
No-path chỉ áp dụng snapshot/catalog/scenario local-admin-only đã khai báo, không bao phủ danh tính mạng tài khoản máy hoặc credential đã bị lấy trước can thiệp.

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
Thêm `--max-paths 10` để tìm tối đa 10 chương trình mỗi cặp và lấy Top-3 theo C.
Với một `--source`, brief hiển thị các lựa chọn; JSON giữ điểm của các candidate
và witness của Top-3. Đây là thứ hạng trong tập đã tìm được, chưa phải Top-3 toàn cục.
Neo-guided v2 giảm ưu tiên các nhánh sửa ACL trên Computer không dẫn tới danh tính
hoặc host/session trong catalog đang bật. Chỉ đổi thứ tự thử, không bỏ nhánh hoặc cấp quyền.
Trên đúng 9 ca SEAMLESS từng hết cap, 7 ca nay có witness sau 14–42 expansions
với cùng cap 1.024; hai ca BADBLOOD còn hết cap. Chưa chạy lại toàn miền để suy rộng.
[Khảo sát search và ranking C](reports/neo/search-quality.json).
[Ví dụ Top-3 theo C](reports/neo/ranking-C-example.md) giữ thao tác và ledger thực tế.
Trên SEAMLESS, cùng 5.180 cặp nguồn–đích: sau sửa tìm được đường và C cho
5.171 cặp (trước: 255); còn 9 cặp hết lượt tìm, không ghi nhận Unknown.
Số liệu và giới hạn: [kết quả discovery](reports/neo/domain-discovery-fix.json).
`scope.json` giữ recipe/profile/source pins; `cells.jsonl` giữ kết quả và witness
với các facts đã dùng, được native replay kiểm tra. Không lưu lặp toàn bộ graph/facts
cho hàng nghìn query. Cần output directory mới khi đổi budget hoặc code.

## Chọn đường theo C và thử can thiệp

```sh
.venv/bin/python -m scripts.neo_decision \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --output-dir reports/generated/neo-decision-001
```

Chọn cố định 3 User và 2 Computer, tìm tối đa 3 chuỗi tới mỗi đích DA/EA,
xếp theo C, thử gỡ một membership đặc quyền rồi tìm lại đường vòng.
Output có `report.md`, brief/ledger từng cặp và các gói kiểm chứng native.
Thêm `--resume` để nối tiếp cùng code/snapshot. Kết quả SEAMLESS:
[bản đọc ngắn](reports/neo/decision-brief.md).

- Một foothold → tự chọn mục tiêu quan trọng: [demo exposure](docs/research/awg-r04/DEMO.md).
- Nhiều nguồn độc lập → ưu tiên rủi ro, thử can thiệp và tìm bypass: [runner remediation](docs/research/awg-r04/DEMO.md).
- Thiết kế và giới hạn hiện tại, datasets, số đo và ưu tiên nghiên cứu: [ghi chú neo](docs/neo.md).
- [Đề bài gốc](docs/00_todo.md), [quy ước dữ liệu](data/README.md), [đóng góp và kiểm thử](CONTRIBUTING.md).

Raw data và output dẫn xuất nằm local trong `data/raw`, `data/processed`, `reports/generated` và không được commit.
Tài liệu cũ ghi nhận các giai đoạn nghiên cứu trước; không tự chuyển các approval hoặc số đo đó thành kết luận mới của neo.
