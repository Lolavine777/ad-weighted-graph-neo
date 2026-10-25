# AD Weighted Graph neo

Từ một User hoặc Computer bị chiếm, tìm đường tấn công có điều kiện tới tài sản quan trọng, giải thích công sức C và kiểm tra đường thay thế sau remediation.
Repo này dùng lịch sử Git mới và workflow cá nhân.
Parser, taxonomy, semantic planner và nghiên cứu AD được tái sử dụng; evidence lịch sử được giữ nguyên để đối chiếu.

Hướng khóa luận: phân tích đường leo thang đặc quyền có xét chi phí và kiểm chứng
biện pháp giảm thiểu. Phần neo bổ sung để đối chiếu là cách giải thích công việc/C
và kết quả tìm lại sau can thiệp; chưa có kết luận tốt hơn BloodHound nói chung.

## Demo visual

Mở [viewer](web/neo-viewer/index.html) bằng trình duyệt từ checkout: graph hành động,
Top-3/C/ledger, bảng khảo sát nhiều nguồn và trước/sau remediation. Không cần cài thêm dependencies hoặc Docker.
Có playback SEAMLESS/WRAITH và nút đọc JSON query CLI từ máy; dữ liệu không upload.
[Phạm vi, định dạng input và nguồn demo](web/neo-viewer/README.md).

Để mang đi trình bày, chạy `.venv/bin/python web/neo-viewer/build.py --output reports/generated/neo-viewer-v1.html` rồi mở file HTML đó.
UI đọc kết quả đã chạy; chưa khởi chạy engine từ trình duyệt.

### Bắt đầu với hai use case

| Câu hỏi | Thao tác trong demo | Đọc kết luận |
| --- | --- | --- |
| Một nguồn bị lộ có thể tới đâu, tốn bao nhiêu công sức? | Mở **Một nguồn bị lộ**, chọn một đường rồi bấm từng bước | C và các công việc ở bảng bên phải; mở **Giả định chương trình** để biết điều kiện đã dùng |
| Can thiệp có giảm khả năng tiếp cận từ nhiều nguồn không? | Mở **Khảo sát nhiều nguồn**, lọc nguồn và chọn hàng; mở **Chi tiết can thiệp** để xem ví dụ WRAITH trước/sau | Phân biệt số đường mẫu bị cắt với số cặp nguồn–đích bị ngắt; còn đường vòng hoặc hết budget chưa phải đã chặn |

Để xem kết quả mới, dùng **Mở JSON** với output query CLI có `semantic.candidates`
(ví dụ `neo_guided.json` từ baseline bên dưới), hoặc `results.json` của demo
`neo_remediation`. Bảng khảo sát demo đọc từ `reports/neo/decision-sample.json`.
`neo_domain` xuất `cells.jsonl` và brief, không xuất JSON query CLI cho viewer;
đọc brief cho lượt này. Snapshot và JSON query **đầu vào** cũng không phải kết quả để mở.
[Bảng định dạng và hướng dẫn viewer](web/neo-viewer/README.md).

### Trạng thái bàn giao

- **Đã có:** pipeline CLI, bảng C, đối chứng CE theo scope, ví dụ can thiệp và viewer offline.
- **Bàn giao:** [nghiệm thu và screenshot Brave](reports/neo/thesis-v1/acceptance.md), cùng trạng thái đóng gói tại [issue #4](https://github.com/Lolavine777/ad-weighted-graph-neo/issues/4).
- **Giới hạn đã biết:** dữ liệu thật chủ yếu cho C tốt nhất trong tập tìm được, chưa đáp ứng bảo đảm minimum-C từ node bất kỳ của đề gốc. GoodHound chưa tái lập trọn lượt chỉ từ checkout. Phạm vi và mức bằng chứng của từng bộ được giữ riêng bên dưới.
- **Add-on sau bàn giao:** mở rộng kỹ thuật/dataset, search mới và điều khiển engine từ trình duyệt. Giữ core và bảng C cho đợt hoàn thiện hiện tại.

## Kết quả đã kiểm chứng

Các bộ dữ liệu kiểm những phần khác nhau; không gộp chúng thành một tỷ lệ thành công chung.

| Bộ dữ liệu / phép kiểm | Kết quả | Phạm vi |
| --- | --- | --- |
| [SEAMLESS, khảo sát danh tính mạng](reports/neo/domain-discovery-fix.json) | 5.171/5.180 cặp có witness và C; 9 hết budget | Mỗi nguồn độc lập có danh tính mạng dùng được; không đại diện preset Computer chỉ có local admin |
| [Bộ đối chứng CE cố định, sau sửa LocalGroup](reports/neo/localgroup-fix.md) | Neo và CE đều có đường cho 22/24 cặp | Cùng bộ cặp đã chốt; [báo cáo gốc](reports/neo/bloodhound-comparison.md) giữ kết quả trước sửa |
| [WRAITH, remediation](reports/neo/remediation-rediscovery-results.json) | Hai can thiệp còn bypass; một can thiệp chặn trong scope | Tìm mới từ foothold ban đầu; witness được replay và kiểm ledger C |
| [GoodHound, đánh giá công khai](reports/neo/goodhound-evaluation.md) | 10 cặp ban đầu: 0 witness, 4 hết budget, 2 no-path, 4 blocked, ở mỗi mode | Cần adaptation đầu vào; không có session; giữ đủ các kết quả bất lợi |
| [GoodHound, positive control riêng](reports/neo/goodhound-positive-control-results.json) | User đã thuộc Administrators: C best-found=3, Top-3=3/4/4; 40 witness replay hợp lệ | Không gộp vào 10 cặp ban đầu; tìm lại sau can thiệp hết budget, chưa kết luận ngắt đường |

[Bảng C và lý do chọn mức](docs/neo.md#chi-phi-c-cho-neo) giữ `neo-c-v1`;
[độ nhạy](reports/neo/cost-sensitivity.md) đã đo trên candidate set cố định.
GoodHound là đánh giá công khai sau adaptation, không phải blind holdout.
Ba file báo cáo GoodHound được giữ nguyên từ nhánh đánh giá tại `74cb3ab`.
[Helper GoodHound gốc và recipe](docs/research/evidence/goodhound-20261024/README.md) đã được thu hồi, khớp hash công bố.
Đã tái lập input và native controls/ranking; toàn bộ cohort/remediation/CE lịch sử chưa được chạy lại từ checkout trong wrap-up.
Không coi việc thu hồi helper là đã tái lập trọn nghiên cứu GoodHound.
Demo WRAITH bên dưới có hướng dẫn tải input đã pin và không cần Docker.

[Kiểm thử hồi quy](reports/neo/full-suite-validation.md) và
[kiểm chứng cài mới](reports/neo/clean-checkout-results.json) ghi rõ revision và môi trường;
[CI tại mốc rubric](https://github.com/Lolavine777/ad-weighted-graph-neo/actions/runs/40116555549) đã pass trên Ubuntu/Windows.

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

- Một foothold → DA/EA, hoặc khảo sát nhiều nguồn độc lập: [runner neo_domain](scripts/neo_domain.py), theo các lệnh phía trên.
- Sửa record và tìm lại bypass: [demo neo_remediation](scripts/neo_remediation.py), theo ba ca WRAITH phía trên.
- Thiết kế và giới hạn hiện tại, datasets, số đo và ưu tiên nghiên cứu: [ghi chú neo](docs/neo.md).
- [Đề bài gốc](docs/00_todo.md), [quy ước dữ liệu](data/README.md), [đóng góp và kiểm thử](CONTRIBUTING.md).

Raw data và output dẫn xuất nằm local trong `data/raw`, `data/processed`, `reports/generated` và không được commit.
Tài liệu cũ ghi nhận các giai đoạn nghiên cứu trước; không tự chuyển các approval hoặc số đo đó thành kết luận mới của neo.

