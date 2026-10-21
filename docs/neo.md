# AWG neo: baseline và hướng nghiên cứu

## Phạm vi

Neo là repo cá nhân có lịch sử mới, được dựng từ nội dung upstream `main` ngày 2026-10-21.
Rework và đơn giản hóa trong planner hiện hữu; không rewrite parser hoặc bỏ semantic checks.
Hai use case là một foothold tới tài sản quan trọng và nhiều compromises độc lập để khảo sát rủi ro, can thiệp, rồi tìm đường thay thế.

## Migration

- Source chỉ đọc: `https://github.com/nairyuuu/ad-weighted-graph`.
- Đích private: `https://github.com/Lolavine777/ad-weighted-graph-neo`.
- `main`: `49dfa2a78614220dfd092b0fd3e5c585992a0484`.
- `develop`: `ba3fcaa8f6d85c181d8a7f657eae112607fd22cb`.
- Cùng tree: `dde43cad3e8e91314bd5ecc4dc1194ac2295596a`.
- Clone upstream đầy đủ để kiểm tra; neo dùng root commit mới theo lựa chọn của chủ repo, không nhập các commit hoặc nhánh PR cũ.
- Không có LFS pointer hoặc submodule trong baseline.
- `upstream` trong checkout neo có push URL `disabled://upstream-read-only`; `remote.pushDefault=origin`.
- Neo được kiểm private và không có ref trước lần push đầu; các lần sau chỉ push fast-forward.

Tám file log evidence vốn được upstream track nhưng khớp `.gitignore` đã được đưa lại nguyên bytes vào commit tiếp theo root commit.
Không có thay đổi nào được ghi vào working tree hoặc push tới repo gốc.

Gitleaks 8.30.1 được tải từ release chính thức và kiểm checksum binary trước khi chạy.
134 cảnh báo ban đầu đã được kiểm tra: 129 source/file hashes, bốn định danh `host-access` có hash và một dòng văn bản về auth context.
Đó là false positives; không có credential thật được nhận diện trong snapshot chuyển sang neo.
Đây là kết quả quét snapshot hiện tại, không phải bảo đảm cho mọi dữ liệu hoặc thay đổi về sau.

## Dataset trên máy

Raw và derived outputs vẫn ở local, được ignore bởi Git theo quy ước dữ liệu hiện hữu.

| Dataset | Cách lấy và xác minh |
| --- | --- |
| SEAMLESS | Tải public archive tại commit pin trong `scripts/download_seamless.py`, xác minh archive SHA-256 và manifest sáu file |
| NORTH | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| NORTH_CE_PYTHON | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| ad_sampledata | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| telemetry | Sao chép CSV local và xác minh manifest `telemetry-raw-v1.json` |

Đã lấy 60 file, 23.577.814 bytes, không tính README.
`data/processed/neo-datasets.json` ghi checksum từng file và cách lấy trên máy migration.
Mọi file sao chép đều được so hash với bản nguồn.
Ba archive NORTH/NORTH_CE_PYTHON/ad_sampledata còn được so với hash công bố trong [data inventory](research/data-inventory.md).
Không khẳng định đã tải mới từ Internet các dataset được sao chép local.
Một clone neo mới chỉ tự tải được SEAMLESS bằng runner; các dataset phụ cần lấy từ kho dữ liệu đã kiểm checksum trên máy này hoặc nguồn được data inventory chỉ định.
Telemetry là corpus độc lập; không entity-join với SEAMLESS hoặc coi là observed activity trên topology này.

## Chạy baseline

Từ repo root, sau bước cài đặt trong [README](../README.md):

```sh
.venv/bin/python -m scripts.neo_baseline --output-dir reports/generated/neo-run-001
```

Runner từ chối ghi đè directory đã tồn tại.
Snapshot có 3.370 nodes và 56.367 edges.
Máy nguồn là SID kết thúc `-4157`; Domain Admins được tìm theo domain SID và RID 512.
Capability `computer_usable_identity` được khai báo tường minh tại context chính máy đó với provenance scenario, không suy ra từ host control.
Policy là `seamless-standard-v1`; C-only profile là `reset-activation-c-v2`.
Chỉ cho phép `scenario_reset_password`, `acquire_reset_identity` và `propagate_group_entitlement`.
Budget là một witness, ba semantic steps và 6.000 expansions.

`query.json` giữ assumptions, profile, source, context và goal chính xác.
`snapshot.json` giữ structural graph cùng facts và code version.
`fifo.json`/`goal_guided.json` giữ full audit, attempts, C ledger, witness và engine guarantees.
`summary.json` ghi các lệnh CLI, phiên bản Python/platform, thời gian, input hashes, semantic hashes, native replay và parity API/CLI.
Thời gian CLI bao gồm load/validate snapshot, search, ranking, serialize và ghi output; thời gian chuẩn bị được ghi riêng.
Không dùng runtime của phiên trước làm số đo của máy này.

FIFO ở cap này chưa tìm witness, không chứng minh no-path.
Guided tìm một conditional witness C=1 sau 4.995 expansions, nhưng bị candidate cap và không chứng minh minimum.
C=1 là union-work ordinal của reset/activation; P/I vẫn chưa chấm.
`goal_guided` hiện là membership heuristic cho một số chain, chưa phải cost-guided search tổng quát.

## Cải tiến nhỏ và evidence

Không tìm thấy `AWG-v2-start.zip`, `AWG-neo-direction.md` hoặc patch tối ưu C cũ trên máy.
Không áp hoặc tái tạo patch đó dựa trên mô tả.
Profiling workload hiện tại phát hiện CLI gọi `wire()` lại trên kết quả mà `execute()` đã chuyển sang JSON-safe values.
Bỏ lượt duyệt thừa này là thay đổi một dòng trong CLI, giữ nguyên toàn bộ audit và định dạng kết quả.
Các phép đo và hash đối chiếu nằm ở [benchmark neo](../reports/neo/benchmark.json).
Không suy rộng kết quả của query này thành tốc độ cho mọi graph hoặc planner.

## Kiểm thử và evidence lịch sử

Fixtures cũ có một số giả định không còn phù hợp với ranh giới danh tính máy.
Các positive tests dùng scenario test riêng khai báo danh tính mạng và bind lại registry trước khi mô phỏng review; không chuyển numeric approval cũ sang context mới.
Queries lịch sử thiếu danh tính mạng vẫn phải bị chặn rõ ràng.
Evidence và numeric releases cũ giữ nguyên bytes.

Baseline integrity của code neo được sinh riêng trong `reports/neo/source-manifest.json`.
Các hash này kiểm thay đổi source hiện hành; không cấp numeric authority hay chứng minh kết quả lịch sử đúng với code mới.
Khi chủ động đổi source được pin, sinh lại baseline bằng công cụ đã cung cấp và chạy kiểm thử trước khi commit.
Không sửa checksum lịch sử để che drift.

## Ba ưu tiên tiếp theo

1. Xây cost-guided search C-first trong planner stateful hiện hữu, tái dùng preparation giữa queries, với oracle finite kiểm work deduplication, zero-cost actions và bằng chứng optimality dưới budget.
2. Mở rộng benchmark nguồn/goal/technique trên cùng snapshot, kiểm replay và chất lượng đường; đối chứng BloodHound trên cùng scope, tách hop count, C ordinal, semantic feasibility và runtime.
3. Hoàn thiện cohort nhiều nguồn và remediation: báo riêng phần chưa chạy, quan sát đường thay thế sau can thiệp và kiểm độ nhạy của assumptions/C trước khi xếp hạng rủi ro cho thesis.

Để cập nhật integrity baseline neo sau một thay đổi source có chủ đích:

```sh
.venv/bin/python -c 'from scripts.research.scenario_rating_pack import write_source_manifest; write_source_manifest()'
```

Để đo lại thay đổi CLI, dùng snapshot/query do runner vừa tạo và một checkout baseline tách biệt:

```sh
git worktree add --detach /tmp/awg-neo-before e96c1c0
.venv/bin/python -m scripts.research.benchmark_neo_cli \
  --baseline-root /tmp/awg-neo-before \
  --query-dir reports/generated/neo-run-001 \
  --output-dir reports/generated/neo-benchmark-001 \
  --report reports/generated/neo-benchmark-001-summary.json
git worktree remove /tmp/awg-neo-before
```

Harness dùng `/usr/bin/time -l` trên macOS, ba trials mỗi variant/search-order, đổi thứ tự before/after giữa các trials và từ chối semantic hash drift.
Nó không thay source hoặc bỏ bớt audit fields.
Report ghi hash của query, snapshot và CLI source của hai variants.
Report đo trước khi commit implementation nên revision Git của variant after vẫn là root commit; hash CLI source phân biệt đúng code đã đo.

Kết quả ba trials xen kẽ mỗi variant/search-order trên macOS arm64, Python 3.14.7:

| Chế độ | Median wall trước | Median wall sau | Peak RSS trước | Peak RSS sau |
| --- | --- | --- | --- | --- |
| fifo | 5.506s | 4.596s | 978.1 MiB | 1051.5 MiB |
| goal_guided | 6.648s | 5.744s | 1141.5 MiB | 1142.1 MiB |

Cả 12 trials giữ nguyên hash của toàn bộ semantic output theo từng search-order, gồm witness, C, attempts, assumptions và guarantees.
FIFO nhanh hơn khoảng 16,5% và guided nhanh hơn khoảng 13,6% trên workload này.
Peak RSS FIFO tăng khoảng 7,5%; guided gần như không đổi.
Đây là tradeoff thời gian/bộ nhớ quan sát được; không phải cải thiện RAM hoặc speedup phổ quát.
