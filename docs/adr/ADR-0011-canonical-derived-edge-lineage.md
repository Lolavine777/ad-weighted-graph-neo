# ADR-0011: Canonical lineage cho cạnh cấu trúc dẫn xuất

- Ngày: 2026-09-23
- Trạng thái: Accepted
- Người đề xuất: @nairyuuu (Codex)
- Reviewer: Pending
- Issue / PR: Refs #92, #45, #80, #84, #97

## Bối cảnh

Graph Contract 1.0.0 lưu `provenance` của cạnh như một tập bản ghi bằng chứng
thô. Tập này không có thứ tự và không giải thích được chuỗi nhân quả của quyền
truy cập suy ra từ membership lồng nhau hoặc resultant GPO. Issue #45 đã giữ
ordered derivation steps nội bộ; cần đưa thông tin này vào graph canonical mà
không thay đổi semantics host-access.

## Các phương án

| Phương án | Lợi ích | Chi phí / hạn chế | Bằng chứng |
| --- | --- | --- | --- |
| Tiếp tục dùng `provenance[]` | Không đổi schema | Mất thứ tự nhân quả, không audit được đường suy luận | #92, #84 |
| Tạo graph edge riêng cho từng path | Dễ nhìn từng path | Phá logical edge ID và tạo cạnh trùng | #92, ADR-0009 |
| Thêm lineage versioned tùy chọn vào cạnh | Giữ edge ID, direct edge đơn giản, bảo toàn mọi path | Cần schema version, validator và migration | #92, ADR-0008 |

## Quyết định và hệ quả

Chọn phương án 3. Graph Contract 1.1.0 thêm field tùy chọn `edge.derivation`.
Direct edge không có field này. Derived edge chứa:

1. lineage version `1.1.0`;
2. một derivation kind (`nested_membership`, `gpo_resultant`, hoặc
   `host_access`);
3. một hoặc nhiều complete paths;
4. step order liên tục, bắt đầu từ zero;
5. operation, endpoint node tùy chọn và references tới raw provenance của
   chính edge đó.

CanRDP paths additionally list explicit path-level conditions with evidence
references for RDU membership, the effective allow right, and known absence of
the effective deny right. These named conditions complete the composite proof
without using the unordered provenance bag as an implicit derivation. Other
derived edge kinds do not carry path conditions. A GPO-derived CanRDP result
must supply the same three verified resolver conditions with supporting
evidence; a complete GPO operation list without them remains non-traversable.

Evidence reference là SHA-256 reference tới canonical provenance object trên
cùng edge. `provenance` vẫn độc lập và không được dùng ngầm để biểu diễn thứ
tự. Mỗi step phải có ít nhất một evidence reference hợp lệ.

Tất cả valid paths được giữ lại, deduplicate theo nội dung và sort theo
canonical JSON. Logical edge ID vẫn là hash của `[source, target, kind]`; thứ tự
input hoặc path không ảnh hưởng edge identity.

Chỉ positive, fully resolved derived result mới được đưa vào `edges`. Với GPO,
`resolved` và `resultant_state` không đủ; input phải cung cấp ordered resolver
steps đã được kiểm chứng theo các canonical operations. Unknown, inferred-only,
rejected hoặc insufficient assessment vẫn nằm ngoài traversable graph.
ADR-0009 vẫn giữ direct-only `MemberOf`; lineage ghi lại path nội bộ mà không
materialize transitive membership edges.

## Kiểm chứng và điều kiện xem lại

- Kiểm chứng bằng pytest, Ruff, yamllint, contract/repository checks và
  `git diff --check`.
- Fixture phải chứng minh nested path, resultant GPO path, multiple-path
  determinism, malformed-lineage rejection, legacy direct graph và JSON
  round-trip.
- Lineage 1.1.0 condition references are canonical provenance references; every
  serialized derived CanRDP path satisfies all three required predicates.
- Contract 1.0.0 vẫn load được nếu graph chỉ có direct-edge fields; Contract
  1.0.0 không được chứa `derivation`. Builder/serializer dùng 1.1.0 khi có
  derived lineage.
- Quyết định này không thay đổi #45 `CanRDP`, không serialize #81 telemetry,
  và không định nghĩa #97 collection-time status. Xem lại khi contract cần
  model mới cho các boundary đó.
