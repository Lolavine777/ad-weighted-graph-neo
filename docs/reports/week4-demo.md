# Demo tuần 4 - Query, gates và C/P/I trên dữ liệu tổng hợp

## Current-state amendment - 11/10/2026

Scoped Week 4 technical acceptance now passes under A maintainer weekend disposition / self-verification.
See the [final closure report](week4-maintainer-closure-2026-10-11.md) for exact revisions, commands, C/P/I coverage, generated C=2/C=3 comparison and Pareto evidence.
Frozen SEAMLESS has C=4/4, P=0/4 and I=1/1; C=3 and High impact are adopted only for exact identities and the typed same-asset terminal goal.
Source A retains its two fully rated historical-prefix chains and 22 P-unrated paths; broad pending proposals remain unchanged.
The full raw-present suite passes 2,603 tests with nine skips and 48 subtests; no independent B review or remote CI PASS is claimed.
#237 and #259 remain Week 5 work; the dated pending statements below are historical snapshots.

## Bổ sung demo SEAMLESS - 09/10/2026

[Input/commands và freeze](../research/week4-seamless-scenario.md) cùng [public output](../research/scenarios/week4-seamless-v1-actual.json) là gói demo mới.
Dùng execution/freeze checkout `983ce542edad80d5b38d1cce97c7ca5db3b77cb5` và private input đã verify; public playback phải gọi là playback của revision này.
Đây là phân tích/prediction trên snapshot AD, không thực nghiệm exploit hoặc phục hồi mật khẩu thật.

| Thời lượng trình bày dự kiến | Nội dung | Output cần chỉ |
| --- | --- | --- |
| 1 phút | Chọn X/C0; known V_A và initial request capability riêng, không initial admin/usable AD identity | Aliases/locators, verified snapshot và target predicate |
| 1 phút | Query chỉ nhận inputs/allow-list/budget/assumptions | Frozen expected độc lập, không supplied ordered path |
| 2 phút | Engine tự sinh request/recovery/activation/direct AdminTo | Bốn actions, năm states, raw/static/assumed gates, causal parents và canonical edge |
| 1 phút | Asset success riêng DA checkpoint | Goal true, checkpoint false, C/P/I unrated; bốn expansions, scope complete |
| 2 phút | RAW/missing recovery/false veto và cap controls | indeterminate/material-only/blocked, rejected assumption, step_limit_reached |
| 1 phút | Revision/input/config binding và giới hạn | Two-process equality; human cross-reproduction pending, không observed success/global optimum |

Bảng là outline 8 phút, không ghi nhận thời gian làm việc hoặc buổi demo đã diễn ra.
Raw/full mappings/results giữ local; khi không có dataset ở nơi trình bày, dùng public sanitized output làm playback dự phòng.
Các Bash blocks và ví dụ C/P/I ngày 08/10 bên dưới giữ như demo tổng hợp bổ sung, không được dùng để thay SEAMLESS result.

Cập nhật ngày 08/10/2026, thay lệnh prerequisite, checksum và ví dụ chấm điểm ngày 07/10/2026.
Chạy từ thư mục gốc của checkout đã đo, dùng môi trường ảo Python 3.14 có các dependencies trong `requirements-dev.txt`.
CLI tích hợp nhận query khai báo và xuất kết quả; runner nghiệm thu A kiểm toàn bộ ma trận và oracle.
Lệnh dùng Bash/POSIX; trên Windows dùng Git Bash và thay `.venv/bin/python` bằng `.venv/Scripts/python.exe` của môi trường ảo.

## 1. Kiểm tra input và nguồn kỳ vọng

Graph thực thi là `graphs/two-routes.json` và `graphs/psremote-command.json` dưới `tests/fixtures/attack_scenarios`.
`week4-v1.json` là nguồn oracle kịch bản; query cụ thể do runner khai báo, không nạp ordered paths làm đầu vào search.
`tests/fixtures/ranking/week4_acceptance_oracle.json` định nghĩa từng assertion độc lập, không lấy actual làm expected.
Ledger E là `docs/research/ratings/week4/synthetic-a2-e.json`.

```bash
.venv/bin/python --version
.venv/bin/python - <<'PY'
import hashlib
from pathlib import Path
pins = {
    "configs/contract.yml": "f461e6e8d8d48b9841797da41ff9cee829b979148685f6a5185db66e23d79eea",
    "tests/fixtures/attack_scenarios/graphs/two-routes.json": "982816b924a73396961a54ab5b7c2e40140941aaa9bfa99a075649dde57457e7",
    "tests/fixtures/attack_scenarios/graphs/psremote-command.json": "567f8549c031a7c982dfc6e918478bc3abc929e2f91314aacda572d411a3e601",
    "tests/fixtures/attack_scenarios/week4-v1.json": "7355d50dc288f7ca9899fcc96b9adb3cc3ba73d6b4b302e5e168239c77a93c48",
    "docs/research/ratings/week4/synthetic-a2-e.json": "007755b020417dd763e0d137a8987359c2779125222693ac4e3c48f6cbf560c1",
}
for name, expected in pins.items():
    observed = hashlib.sha256(Path(name).read_bytes()).hexdigest()
    assert observed == expected, name
    print(name, observed)
PY
```

## 2. Đường thành công, false, unknown và assumption

Baseline khai báo control tại OtherHost, Alice usable tại Host, context Host, mục tiêu `admin_control(Host)` và các runtime facts tổng hợp true.
Actual sinh ba chương trình, `success`, goal true; checkpoint false vì baseline không yêu cầu checkpoint.
Ca phủ quyết phải có `known_false_veto`; ca thiếu WinRM giữ `indeterminate`; ca khai báo assumption true sinh một đường assumption-backed.
“Observed evidence” trong trace các ca này chỉ là nhãn dữ kiện tổng hợp của fixture, không phải quan sát môi trường thật.

```bash
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-M-POSITIVE
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-G-VETO
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-G-U
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-G-A
```

## 3. Minimum effort, ties và truncation

Trong Ledger E, D và M/D có C = 5, P = [2/5, 27/40]; M/I có C = 2, P = [12/25, 18/25]; I của cả ba là High.
D/I là thực thi quản trị trực tiếp/kế thừa, M là bao đóng membership; không có đổi mật khẩu hoặc lấy vé trong query này.
Trong fixture nhỏ được đánh giá đầy đủ, `generated_0003` là M/I và có C nhỏ nhất bằng 2.
Ledger T giữ đủ ba ứng viên hòa C = 2.
Cap số đường/số bước cho `truncated=true`; cờ minimum proven phải false.

```bash
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-MIN-EFFORT-E
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-MIN-EFFORT-T
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-CAP-PATHS
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-CAP-STEPS
```

## 4. Kerberoasting và hồi quy engine

Chuỗi sinh thực tế gồm `kerberoast_request` -> `recover_ticket_secret` -> `activate_recovered_identity` -> `propagate_group_entitlement` -> `scenario_winrm_admin`.
Cùng snapshot/query/state/caps, tắt các kỹ thuật acquisition thì không có đường; bật lên sinh một chương trình tới tài sản dưới giả định tổng hợp.
Ca thiếu recovery dừng ở ticket material, chưa secret/usable identity. Ca có đường reset sẵn không chứng minh thêm tài sản; extension chạm giới hạn bước nên không claim exhaustive coverage.
C/P/I của roasting giữ unrated/null, không dùng định mức Ledger E.

```bash
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-TECH-KERBEROASTING
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-K-MATERIAL
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-K-OVERLAP
```

Hai ca hồi quy phải PASS. Binding inherited-admin không hợp lệ vẫn loại một đường, nhưng incumbent C = 5 chỉ có scope `best_in_bound_subset`, proof false.
Zero-action giữ goal true, đường 0 bước và zero new work = 0; ranking không áp dụng, P/I null, không có canonical assessed candidates hoặc Pareto.

```bash
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-DEFECT-ADAPTER-REJECT
.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id W4-DEFECT-ZERO-ACTION
```

## 5. Tái lập và đọc bản kê

```bash
.venv/bin/python scripts/research/week4_acceptance_runner.py --check-determinism
.venv/bin/python -m pytest tests/test_week4_acceptance_manifest.py
```

Expected summary: 36 PASS, 0 KNOWN DEFECT, 0 PENDING B, 1 NOT EXECUTED, 1 BLOCKED RUN, 0 unexpected failures.
Exit 0 chỉ nghĩa là không có sai lệch bất ngờ; không đồng nghĩa nghiệm thu đầy đủ.
Bất kỳ assertion sai ngoài chữ ký lỗi/pending đã khai báo trả exit 1, kể cả khi lọc một ca.
Thông báo `SEMANTIC DETERMINISM VERIFIED` so sánh semantic payload và hash nguồn/input; timestamp, platform và commit được ghi thực tế từng lượt.
Bản kê `reports/research/week4-acceptance-manifest.json` có `execution.file_sha256`, `execution.source`, runtime và từng assertion expected/actual.
`tests/fixtures/ranking/week4_acceptance_cases.json` là payload semantic đã đo, chỉ dùng kiểm tra tái lập bổ sung.
Không xem byte equality với bản kê cũ là predicate acceptance độc lập.

Dữ liệu SEAMLESS ngoài kho phải được cấp phép và xác minh bằng manifest cùng time-policy đã pin trước khi chạy probe riêng tư.
Checkout nghiệm thu hiện thiếu prerequisite; runner không chạy probe và không ghi mã thoát giả.
Đối soát đầy đủ tài liệu/API, AS-REP và RBCD vẫn giữ chưa nghiệm thu. CLI chỉ đạt phạm vi tổng hợp đã chạy, chưa là nghiệm thu SEAMLESS.

## 6. CLI công khai và kết quả tái lập

Query chọn Alice, Host và khả năng ban đầu, không cung cấp ordered attack path. Engine sinh ba chương trình; Ledger E cho minimum effort 2, goal true và checkpoint false. Hai file giữ metadata runtime riêng; harness so semantic và nguồn/input đã ghim.

```bash
mkdir -p reports/generated
.venv/bin/python -m src.engine.query_cli --query tests/fixtures/query_cli/two-routes-query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --ranking-query docs/research/ratings/week4/synthetic-a2-e.json --label synthetic --output reports/generated/week4-cli-demo-1.json
.venv/bin/python -m src.engine.query_cli --query tests/fixtures/query_cli/two-routes-query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --ranking-query docs/research/ratings/week4/synthetic-a2-e.json --label synthetic --output reports/generated/week4-cli-demo-2.json
.venv/bin/python -m scripts.research.compare_query_runs reports/generated/week4-cli-demo-1.json reports/generated/week4-cli-demo-2.json
```

Kỳ vọng compare trả equal=true và exit 0. Đây là hai process tự động, chưa thay việc người còn lại tái lập độc lập trên đầu vào riêng tư được phép.
