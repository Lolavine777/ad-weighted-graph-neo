# Synthetic fixtures

Các JSON trực tiếp ở đây là đồ thị chuẩn hóa giả lập, không chứa dữ liệu AD thật và không phải
export của collector. Schema validator kiểm tra cấu trúc/tham chiếu; kiểm tra fixture
không chứng minh parser đã đọc được export hoặc suy luận quan hệ từ bằng chứng thật.

## M1: bao phủ 8 loại cạnh

[m1-fixtures.json](m1-fixtures.json) phục vụ [issue #9](https://github.com/nairyuuu/ad-weighted-graph/issues/9):
18 nodes (6 User, 4 Computer, 5 Group, 1 Domain, 1 OU, 1 GPO) và 28 edges.

| Loại cạnh | Số lượng |
| --- | --- |
| MemberOf | 8 |
| AdminTo | 3 |
| GenericAll | 3 |
| WriteDacl | 3 |
| ForceChangePassword | 2 |
| CanRDP | 3 |
| CanPSRemote | 3 |
| HasSession | 3 |

Các tình huống dùng label để dễ tra cứu (mọi label có tiền tố `SYNTHETIC-`):

- Cạnh song song: `HELPDESK → WORKSTATION` có `AdminTo`, `CanRDP`, `CanPSRemote`;
  `HELPDESK-USER → SERVICE-USER` có `GenericAll` và `WriteDacl`.
- Chu trình nhóm: `NESTED-A → NESTED-B → NESTED-A`, cả hai cạnh là `MemberOf`.
  Không có self-loop.
- Node độc lập: `ISOLATED-USER` không có cạnh vào hoặc ra.
- Node kết thúc: `DISABLED-USER` có `enabled: false`, nhận `ForceChangePassword`
  từ `HELPDESK-USER` và không có cạnh ra.
- Bằng chứng lặp: `FOOTHOLD → HELPDESK` là một cạnh `MemberOf` với hai provenance
  records khác nhau. Cùng source/target/kind dùng chung một ID; các loại cạnh khác
  nhau giữa cùng hai node vẫn được giữ riêng.
- Hướng session: `WORKSTATION → HELPDESK-USER`, `APP-SERVER → TIER1-USER`,
  `FILE-SERVER → SERVICE-USER` đều là `Computer → User`.

ID node dùng SID/GUID chuẩn; ID cạnh được tạo bằng `canonical_edge_id()` trong
[validator](../../scripts/check_contract.py). Provenance dùng URI `synthetic://`
để chỉ các quan sát giả lập, không trỏ tới file collector cần tồn tại. Các cạnh
truy cập host biểu diễn quan hệ giả định đã chuẩn hóa; fixture không kiểm chứng
các điều kiện suy luận host/GPO, RDP hoặc quyền đăng nhập.

[Tests M1](../../tests/test_m1_fixtures.py) kiểm tra contract, giới hạn số nodes/edges,
đủ 8 loại cạnh, cạnh song song, chu trình nhóm, orphan, hướng cạnh, node vô hiệu hóa
và provenance gộp. Chạy từ thư mục gốc bằng Python 3.14 và dependencies development:

```bash
python scripts/check_contract.py
python -m pytest tests/test_m1_fixtures.py
```

CI hiện có tự tìm mọi JSON trực tiếp trong thư mục này và chạy toàn bộ pytest; không cần
thêm workflow. Fixture này có thể dùng làm đầu ra mong đợi khi triển khai parser;
kiểm thử parser đầy đủ cần bổ sung raw inputs tương ứng và adapter thực tế.

## Toy graph: ví dụ đường đi nhỏ

[toy-graph.json](toy-graph.json) giữ ví dụ topology nhỏ và định danh nhóm có scope.
Oracle cho engine tương lai, từ `SYNTHETIC-PC` tới `SYNTHETIC-TARGET`:

- Profile `unit`: cạnh `GenericAll` trực tiếp, cost 1, ngắn nhất theo số bước.
- Profile `illustrative`: `HasSession → MemberOf` qua `SYNTHETIC-USER`, cost 1.5;
  cạnh `GenericAll` trực tiếp cost 5.
- `SYNTHETIC-ISOLATED` không có đường tới đích; `SYNTHETIC-TARGET` không có đường
  ngược về `SYNTHETIC-PC`.

Các oracle trên chưa kiểm chứng thuật toán engine của repo; engine chưa triển khai.

## Snapshot manifest: input bytes tổng hợp

`snapshot-input/` chứa một file rỗng và một file UTF-8 nhỏ có tên Unicode/space.
[manifests/synthetic-v1.json](manifests/synthetic-v1.json) là manifest chuẩn cho input
này, được kiểm tra byte-for-byte bằng [tests](../../tests/test_manifest.py) trên cả
Windows/Linux. `.gitattributes` giữ nguyên bytes input và LF của manifest.
Manifest nằm trong thư mục con để không bị graph contract validator đọc nhầm.
Xem [quy trình tạo và verify](../../docs/snapshot-manifest.md); không cần raw AD data.

## Parser CLI: manifest-backed synthetic export

[`parser-cli-input/`](parser-cli-input/) is a compact SharpHound v3-shaped export with
plural kind-key envelopes, group membership, a host-local administrator observation, and
one unresolved RDP principal. Its manifest has unknown collection time so the CLI must use
an explicit policy. [`parser-cli-time-policy.json`](../../tests/fixtures/parser-cli-time-policy.json) supplies
an intentionally assumed timestamp for this synthetic fixture only.
[`manifests/parser-cli-seamless-v1.json`](manifests/parser-cli-seamless-v1.json) pins the
input bytes for integration coverage. The test verifies a derived `AdminTo` edge with
ordered lineage and retains the unresolved observation as an assessment.

## Rich parser semantics demo

[`parser-demo/README.md`](parser-demo/README.md) shows a separate manifest-bound synthetic
input with repeated observations, multiple provenance records on one edge, nested host-local
admin derivation, ACL and session directionality, scoped SID normalization, and unknown RDP
access. A second snapshot demonstrates all three record error policies. The page has exact
one-line commands and a raw evidence → parser decision → graph result map.
The [mentor walkthrough](parser-demo/MENTOR_WALKTHROUGH.md) gives a presentation order and
specific graph fields to show for each flow.
