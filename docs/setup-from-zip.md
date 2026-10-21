# Cài đặt từ ZIP và dựng snapshot

Hướng dẫn cài đặt được giữ từ `main@fb3d2b8`; các lệnh chạy từ thư mục gốc repository. Xem [README](../README.md) cho core và demo AWG-R04 hiện hành.

Dựng đồ thị Active Directory từ dữ liệu JSON, tìm đường tấn công theo trạng thái và đánh giá đường bằng Effort (C), Likelihood (P), Impact (I).

Hướng dẫn này dành cho người **tải mã nguồn dạng ZIP**, chạy trên Windows PowerShell hoặc Linux (Bash) và có bộ dữ liệu riêng. Các lệnh chạy từ thư mục gốc chứa `README.md`, `src/`, `scripts/` và `configs/`.

Quy trình: **giải nén mã nguồn → tạo commit Git cục bộ → cài môi trường → đặt JSON nguồn → tạo và verify snapshot manifest → xuất graph JSON → chạy demo**.

## 1. Chuẩn bị mã nguồn và Git

Cài **Python 3.14.x** và **Git**. Docker/Neo4j chỉ cần nếu muốn xem đồ thị qua Neo4j; pipeline xuất graph JSON không cần chúng.

Tải ZIP của nhánh hoặc phiên bản cần sử dụng từ [repository](https://github.com/nairyuuu/ad-weighted-graph). Các lệnh snapshot và parser được đối chiếu với `main` tại commit `16b09c7b70adc251c921608f0d7026058c7c0aee`. Phần Viewer đang được cập nhật trong [PR #279](https://github.com/nairyuuu/ad-weighted-graph/pull/279); xem điều kiện chạy ở mục 6.

Giải nén rồi mở PowerShell (Windows) hoặc terminal Bash (Linux) trong thư mục dự án. Ví dụ nếu tải ZIP của `main`:

**Windows (PowerShell):**

```powershell
cd C:\Projects\ad-weighted-graph-main
git --version
py -3.14 --version
```

**Linux (Bash):**

```bash
cd ~/Projects/ad-weighted-graph-main
git --version
python3.14 --version
```

ZIP không có lịch sử Git. Parser yêu cầu một commit cục bộ để ghi `code_version` vào graph và kiểm tra mã nguồn parser/contract đã được commit. Khởi tạo trước khi chép dữ liệu riêng:

**Windows (PowerShell):**

```powershell
git init
git config user.name "Local User"
git config user.email "local@example.invalid"
git add .
git diff --cached --stat
git commit -m "Initialize source from downloaded ZIP"
git rev-parse HEAD
```

**Linux (Bash):**

```bash
git init
git config user.name "Local User"
git config user.email "local@example.invalid"
git add .
git diff --cached --stat
git commit -m "Initialize source from downloaded ZIP"
git rev-parse HEAD
```

Có thể thay tên/email bằng thông tin của bạn; cấu hình trên chỉ áp dụng cho repo này. **Không cần `git remote add`, tài khoản GitHub hay `git push` để chạy.** Commit vừa tạo là phiên bản Git cục bộ, không phải SHA gốc trên GitHub; nên ghi lại nhánh/commit hoặc tên ZIP đã tải để đối chiếu sau này.

Nếu thư mục đã được clone bằng Git và có `HEAD`, bỏ qua bước khởi tạo. Nếu sửa `src/parser/`, `src/data/`, `configs/` hoặc `scripts/check_contract.py`, cần commit các thay đổi trước khi xuất graph.

## 2. Cài môi trường Python

**Windows (PowerShell):**

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/snapshot_manifest.py --help
.\.venv\Scripts\python.exe -m src.parser.cli --help
```

**Linux (Bash):**

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/snapshot_manifest.py --help
.venv/bin/python -m src.parser.cli --help
```

Các lệnh gọi trực tiếp Python trong `.venv`, không cần activate môi trường hoặc thay Execution Policy của PowerShell.

Các khối **Linux (Bash)** bên dưới dùng `.venv/bin/python`, không cần activate môi trường. Python 3.14 và module `venv` phải được cài trước khi tạo môi trường.

## 3. Chép dữ liệu vào đâu?

Ví dụ dùng mã dataset `seamless-v1`. Tạo thư mục:

**Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force -Path data/raw/seamless-v1, data/processed/manifests/seamless-v1, data/processed/graphs, reports/generated | Out-Null
```

**Linux (Bash):**

```bash
mkdir -p data/raw/seamless-v1 data/processed/manifests/seamless-v1 data/processed/graphs reports/generated
```

Giải nén bộ dữ liệu riêng và **chép các file JSON export vào `data/raw/seamless-v1/`**. Giữ nguyên nội dung và tên file nguồn. Có thể giữ các thư mục con; công cụ snapshot quét đệ quy.

Ví dụ bố trí file (tên JSON thực tế có thể khác):

```text
data/
  raw/
    seamless-v1/
      users.json
      groups.json
      computers.json
      domains.json
  processed/
    manifests/
      seamless-v1/
        manifest.json            # tạo ở bước 4
    seamless-v1-time-policy.json  # chỉ cần nếu chưa biết thời gian thu thập
    graphs/
      seamless-v1-unit.json       # tạo ở bước 5
reports/
  generated/                     # kết quả phân tích/demo
```

| Nội dung | Vị trí |
| --- | --- |
| JSON nguồn của một dataset/run | `data/raw/<dataset-id>/` |
| Manifest checksum của snapshot | `data/processed/manifests/<dataset-id>/` |
| Time policy và metadata vận hành | `data/processed/` |
| Graph đã chuẩn hóa | `data/processed/graphs/` |
| Kết quả truy vấn, báo cáo chạy | `reports/generated/` |
| Dữ liệu tổng hợp đi kèm repo | `data/samples/` |

Đầu vào parser là JSON export có envelope `meta` và danh sách record (`data` hoặc khóa theo loại đối tượng); không đưa trực tiếp `.dit`, ZIP chưa giải nén, graph JSON đầu ra hoặc JSON cấu hình vào thư mục nguồn. Schema không tương thích có thể cần bước chuyển đổi trước.

Snapshot sẽ ghi checksum **mọi file** dưới thư mục nguồn, kể cả file không phải JSON; parser chỉ đọc các JSON export. Vì vậy đặt manifest, time policy và output **bên ngoài** `data/raw/seamless-v1/`.

`data/raw/`, `data/processed/` và `reports/generated/` đã được ignore, ngoại trừ README của từng thư mục. Không force-add dữ liệu riêng. Kiểm tra trước khi commit; Git ignore không gỡ bỏ file đã được track.

## 4. Tạo snapshot trước khi dựng đồ thị

Snapshot manifest ghi danh sách file, kích thước, SHA-256 và metadata thu thập để các lần chạy dùng cùng đầu vào. Công cụ này không tạo bản sao dữ liệu; cần giữ thư mục raw bất biến trong lúc generate, verify và parse.

### 4.1. Generate manifest

Ví dụ sau dùng metadata chưa biết. Nếu biết collector, phiên bản và thời gian thu thập thật, thay `unknown` bằng thông tin tương ứng; thời gian phải ở UTC dạng `YYYY-MM-DDTHH:MM:SSZ`. Phiên bản schema export không phải phiên bản collector.

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe scripts/snapshot_manifest.py generate data/raw/seamless-v1 --output data/processed/manifests/seamless-v1/manifest.json --dataset-id seamless-v1 --collector-name unknown --collector-version unknown --collected-at unknown
if ($LASTEXITCODE -ne 0) { throw "Snapshot generation failed" }
```

**Linux (Bash):**

```bash
.venv/bin/python scripts/snapshot_manifest.py generate data/raw/seamless-v1 --output data/processed/manifests/seamless-v1/manifest.json --dataset-id seamless-v1 --collector-name unknown --collector-version unknown --collected-at unknown || { echo "Snapshot generation failed" >&2; exit 1; }
```

Thư mục output phải tồn tại. Lệnh thành công in JSON chứa `status: generated` và `snapshot_id: sha256:...`. `unknown` của phiên bản/thời gian được lưu thành `null` trong manifest.

Nếu bộ dữ liệu gồm nhiều collector hoặc nhiều lần thu thập, dùng metadata theo từng file thay vì gán một thời gian chung cho cả bộ; xem [snapshot manifest](../docs/snapshot-manifest.md).

### 4.2. Verify dữ liệu

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe scripts/snapshot_manifest.py verify data/raw/seamless-v1 data/processed/manifests/seamless-v1/manifest.json
if ($LASTEXITCODE -ne 0) { throw "Snapshot verification failed; check the raw files" }
```

**Linux (Bash):**

```bash
.venv/bin/python scripts/snapshot_manifest.py verify data/raw/seamless-v1 data/processed/manifests/seamless-v1/manifest.json || { echo "Snapshot verification failed; check the raw files" >&2; exit 1; }
```

Kết quả mong đợi:

```json
{"issues": [], "status": "verified"}
```

Nếu có file thêm, thiếu hoặc đổi checksum, giải quyết khác biệt trước khi dựng graph. Khi muốn sử dụng dữ liệu mới, tạo một dataset/run và manifest mới, giữ snapshot cũ để đối chiếu.

### 4.3. Lấy snapshot ID

Trong cùng cửa sổ PowerShell hoặc terminal Bash:

**Windows (PowerShell):**

```powershell
$SnapshotId = (Get-Content -Raw data/processed/manifests/seamless-v1/manifest.json | ConvertFrom-Json).snapshot_id
$SnapshotId
```

**Linux (Bash):**

```bash
SnapshotId=$(.venv/bin/python -c 'import json; from pathlib import Path; print(json.loads(Path("data/processed/manifests/seamless-v1/manifest.json").read_text(encoding="utf-8"))["snapshot_id"])')
printf '%s\n' "$SnapshotId"
```

Truyền **toàn bộ** chuỗi `sha256:` và 64 ký tự hex cho parser; không dùng dataset ID hoặc đường dẫn manifest thay cho snapshot ID.

### 4.4. Nếu chưa biết thời gian thu thập

Manifest có thể ghi `collected_at: null`, nhưng graph cần timestamp cho provenance. Khi thiếu thời gian thu thập, phải cung cấp time policy tường minh.

Repo đã có sẵn policy **collection timestamp assumed** tại [`data/samples/parser-demo/time-policy.json`](../data/samples/parser-demo/time-policy.json):

```json
{
  "timestamp": "2026-09-24T00:00:00Z",
  "status": "assumed",
  "reason": "Fixed illustrative collection time for synthetic parser demo snapshots; not an observed collection timestamp."
}
```

Với dữ liệu demo tổng hợp, có thể truyền trực tiếp `--time-policy data/samples/parser-demo/time-policy.json` ở bước 5; không cần tự tạo file. Fixture [`tests/fixtures/parser-cli-time-policy.json`](../tests/fixtures/parser-cli-time-policy.json) cũng dùng cùng timestamp và status, dành cho kiểm thử CLI.

Nếu dùng mốc giả định này cho dữ liệu riêng, tạo bản local bên dưới để giữ timestamp/status nhưng ghi đúng lý do áp dụng cho dataset của bạn. Không sửa policy mẫu đã commit, và không coi mốc này là thời gian thu thập SEAMLESS đã được xác minh. Manifest vẫn giữ `collected_at: null` nếu thời gian thật chưa biết.

**Windows (PowerShell):**

```powershell
$TimePolicy = Get-Content -Raw data/samples/parser-demo/time-policy.json | ConvertFrom-Json
$TimePolicy.reason = "Explicitly reuse the demo timestamp for this local dataset; actual collection time is unknown."
$TimePolicy | ConvertTo-Json | Set-Content -Encoding ascii data/processed/seamless-v1-time-policy.json
```

**Linux (Bash):**

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

policy = json.loads(Path("data/samples/parser-demo/time-policy.json").read_text(encoding="utf-8"))
policy["reason"] = "Explicitly reuse the demo timestamp for this local dataset; actual collection time is unknown."
Path("data/processed/seamless-v1-time-policy.json").write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
PY
```

Sau đó chạy nguyên lệnh bước 5 với `--time-policy data/processed/seamless-v1-time-policy.json`. Nếu muốn chọn mốc giả định khác, dùng ví dụ tạo policy mới bên dưới thay cho cách tái sử dụng trên.

Ví dụ dưới đây dùng **mốc giả định minh họa**, không phải thời gian thu thập đã xác minh. Thay bằng mốc giả định bạn chọn và ghi rõ lý do; nếu chưa thể chấp nhận giả định này, cần bổ sung bằng chứng thời gian trước khi parse.

**Windows (PowerShell):**

```powershell
@'
{
  "timestamp": "2026-10-14T00:00:00Z",
  "status": "assumed",
  "reason": "Illustrative timestamp chosen for a local run; actual collection time is unknown."
}
'@ | Set-Content -Encoding ascii data/processed/seamless-v1-time-policy.json
```

**Linux (Bash):**

```bash
cat > data/processed/seamless-v1-time-policy.json <<'JSON'
{
  "timestamp": "2026-10-14T00:00:00Z",
  "status": "assumed",
  "reason": "Illustrative timestamp chosen for a local run; actual collection time is unknown."
}
JSON
```

Policy này đánh dấu timestamp là `assumed`; không tự lấy thời gian tải ZIP, thời gian file hoặc giờ hiện tại làm thời gian thu thập. `--created-at` là thời gian **xuất graph**, không thay thế time policy.

Nếu manifest đã có thời gian thu thập trên tất cả JSON đầu vào, bỏ bước này và bỏ `--time-policy` ở lệnh tiếp theo.

## 5. Dựng và xuất đồ thị

Sau khi verify thành công, dùng snapshot ID vừa đọc:

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe -m src.parser.cli --snapshot-id $SnapshotId --raw-dir data/raw/seamless-v1 --manifest-dir data/processed/manifests/seamless-v1 --profile unit --time-policy data/processed/seamless-v1-time-policy.json --output data/processed/graphs/seamless-v1-unit.json --summary
if ($LASTEXITCODE -ne 0) { throw "Graph export failed" }
```

**Linux (Bash):**

```bash
.venv/bin/python -m src.parser.cli --snapshot-id "$SnapshotId" --raw-dir data/raw/seamless-v1 --manifest-dir data/processed/manifests/seamless-v1 --profile unit --time-policy data/processed/seamless-v1-time-policy.json --output data/processed/graphs/seamless-v1-unit.json --summary || { echo "Graph export failed" >&2; exit 1; }
```

`--manifest-dir` nhận **thư mục**, không phải đường dẫn file. Dùng thư mục riêng cho dataset để tránh manifest trùng snapshot ID hoặc manifest khác không hợp lệ. Parser kiểm tra lại dữ liệu theo manifest trước khi đọc, chuẩn hóa danh tính, dựng cạnh và xuất canonical Graph JSON.

`unit` là profile trọng số cấu trúc cơ sở; các trọng số này không phải bộ điểm C/P/I của toàn đường tấn công. Ranking đường thuộc bước phân tích sau.

Khi thành công, `--summary` in số node, edge, assessment, snapshot ID và đường dẫn output. Kiểm tra file:

**Windows (PowerShell):**

```powershell
$Graph = Get-Content -Raw data/processed/graphs/seamless-v1-unit.json | ConvertFrom-Json
$Graph.nodes.Count
$Graph.edges.Count
$Graph.assessments.Count
```

**Linux (Bash):**

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

graph = json.loads(Path("data/processed/graphs/seamless-v1-unit.json").read_text(encoding="utf-8"))
for key in ("nodes", "edges", "assessments"):
    print(f"{key}: {len(graph[key])}")
PY
```

Graph JSON có thể được dùng trực tiếp cho engine; không bắt buộc import Neo4j. Assessment thể hiện các đánh giá/điều kiện còn bất định, cần giữ cùng graph khi phân tích kết quả.

Nếu mở PowerShell hoặc terminal mới, đọc lại biến snapshot ID ở bước 4.3 trước khi chạy parser.

## 6. Chạy giao diện sử dụng

**Lệnh khởi chạy Viewer giữ nguyên.** Các lệnh dưới đây áp dụng cho bản mã nguồn đã có `scripts/viewer/` và `requirements-viewer.txt` (hiện ở [PR #279](https://github.com/nairyuuu/ad-weighted-graph/pull/279)). Nếu ZIP `main` chưa có hai đường dẫn này, cần bản ZIP của nhánh Viewer hoặc đợi phần Viewer được merge vào `main`.

Từ thư mục gốc, với môi trường Python đã tạo ở bước 2:

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-viewer.txt
.\.venv\Scripts\python.exe -m scripts.viewer --demo
```

**Linux (Bash):**

```bash
.venv/bin/python -m pip install -r requirements-viewer.txt
.venv/bin/python -m scripts.viewer --demo
```

Mở trình duyệt tại **http://127.0.0.1:8765**. Giữ cửa sổ PowerShell đang chạy server; nhấn `Ctrl+C` để dừng. `--demo` chuẩn bị bộ demo tổng hợp đi kèm, không tự nạp bộ dữ liệu SEAMLESS riêng đã chép vào `data/raw/`.

> **TODO — Luồng sử dụng/demo đang được hoàn thiện.** Danh sách dưới đây là placeholder cho giao diện mục tiêu sau khi chốt các nút và kịch bản; chưa phải xác nhận mọi chức năng đã có trên `main`.

Luồng sử dụng dự kiến:

1. Nạp graph/snapshot hoặc chọn preset demo: Source A, Source B/two-routes và một kịch bản kỹ thuật AS-REP/Kerberoasting/RBCD.
2. Chọn node nguồn, node đích và foothold/scenario profile; chỉnh budget và Top-K rồi chạy truy vấn. Với cặp node tùy chọn, xem đường cấu trúc, điều kiện cần và các giả định của scenario.
3. Chọn đường trong Top-K để highlight graph, xem từng bước AttackState, bảng giải trình C/P/I và provenance.
4. Thử các case không có đường, bị giới hạn tìm kiếm và fact False; đọc trạng thái, lý do chặn và phạm vi bảo đảm của kết quả.
5. Mở phần đối chiếu đường theo số hop với đường theo effort/risk, choke point/khắc phục và thời gian dựng graph/truy vấn khi các phần này được nối lên giao diện.

Đầu vào riêng đã chuẩn bị từ hướng dẫn này: `data/processed/graphs/seamless-v1-unit.json`, manifest tương ứng và JSON raw đã verify. Hướng dẫn nạp SEAMLESS/preset, các nút cụ thể và kết quả mong đợi sẽ được bổ sung sau khi chốt demo.

## 7. Lỗi thường gặp

| Lỗi/triệu chứng | Cách xử lý |
| --- | --- |
| Không resolve được Git commit | Chạy `git init`, `git add .`, `git commit` ở gốc dự án; kiểm tra `git rev-parse HEAD`. Chỉ `git init` chưa đủ. |
| Parser source/contract có uncommitted changes | Kiểm tra `git status`, review và commit các thay đổi nguồn liên quan trước khi export. |
| Không tìm thấy snapshot | Đọc lại ID từ manifest, truyền đúng `--manifest-dir` và đầy đủ tiền tố `sha256:`. |
| Multiple manifests resolve snapshot ID | Chỉ giữ một manifest cho ID đó trong thư mục truyền vào parser. |
| Snapshot verification failed | Kiểm tra file thêm/thiếu/đổi checksum; bảo đảm raw không bị sửa trong khi chạy. |
| Missing collection timestamp | Cung cấp time policy tường minh cho metadata chưa biết, hoặc bổ sung thời gian có bằng chứng. |
| Malformed/empty JSON envelope | Kiểm tra đây là JSON export đúng schema; bỏ cấu hình/output khỏi raw và xử lý file export lỗi. Không chỉ generate lại manifest để khắc phục lỗi schema. |
| Không tạo được manifest output | Tạo thư mục cha trước; không đặt output bên trong snapshot root. |

## Tài liệu thêm

- [Quy ước dữ liệu](../data/README.md) và [snapshot manifest](../docs/snapshot-manifest.md).
- [Môi trường, Neo4j và BloodHound](../docs/02_environment.md).
- [Kiến trúc và contract](../docs/03_architecture.md).
- [Query CLI](../docs/research/week4-query-cli.md).
- [Quy trình đóng góp](../CONTRIBUTING.md).

Nếu phát triển hoặc chạy test, cài thêm `requirements-tests.txt`; việc dựng graph chỉ cần `requirements.txt`.
