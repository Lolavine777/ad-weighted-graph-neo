# Architecture Decision Records (ADRs)

Thư mục này lưu trữ các Quyết định Kiến trúc (ADR) của dự án.
Các quyết định ghi nhận bối cảnh, các phương án cân nhắc, quyết định được chọn và hệ quả kiến trúc xuyên suốt quá trình phát triển.

## Ranh giới Chuẩn tắc Hiện hành (Normative Sources of Truth)

Theo các đợt rà soát và chuẩn hóa kiến trúc M1/M2 (Issue #83, ADR-0007, ADR-0008):

- **Đồ thị Cấu trúc (Structural Graph):** [configs/contract.yml](../../configs/contract.yml) (Graph Contract 1.2.0, trạng thái `accepted`, giữ nguyên 8 loại cạnh cấu trúc, trọng số $W \ge 1.0$; lineage dẫn xuất tùy chọn và timestamp status theo từng provenance record; tương thích ngược với 1.0.0/1.1.0).
- **Tầng Ngữ nghĩa Tấn công (Attack Semantics Layer):** [configs/attack_semantics.yml](../../configs/attack_semantics.yml) là Single Source of Truth duy nhất cho các bước chuyển trạng thái ngữ nghĩa, vị từ thực thi và telemetry kiểm toán kỳ vọng (ADR-0008).
- **Khung Đánh giá Dữ liệu & Telemetry:** [ADR-0007](ADR-0007-enterprise-topology-independent-telemetry-evaluation.md) và hệ thống manifest tại `data/samples/manifests/`.
- **Mô hình Trọng số (Weighting):** Profile `unit` ($W=1.0$) là baseline duy nhất được chấp thuận cho kiểm thử hồi quy và tính đúng đắn thuật toán của Milestone 2; profile `maut_v1` là thử nghiệm lịch sử (`production_ready: false`); mô hình trọng số sản phẩm chờ quyết định kế thừa chính thức tại Issue #42.

## Danh mục Quyết định Kiến trúc

| ADR | Tiêu đề | Ngày | Trạng thái | Nguồn chuẩn tắc hiện hành / Ghi chú |
| --- | --- | --- | --- | --- |
| [ADR-0001](ADR-0001-maut-weighting-model.md) | Mô hình trọng số 4D MAUT và cơ chế chi phí heuristic cộng dồn cho Dijkstra | 2026-09-14 | **Historical / Superseded in part** | Profile `maut_v1` là thử nghiệm lịch sử (`production_ready: false`); `unit` là baseline hồi quy; mô hình chi phí sản phẩm chờ quyết định kế thừa tại #42. |
| [ADR-0002](ADR-0002-edge-directionality-semantics.md) | Chuẩn hóa ngữ nghĩa hướng chuyển quyền trên đồ thị tấn công | 2026-09-14 | **Accepted** | Hướng cạnh theo luồng chiếm quyền ($Source \to Target$); chuẩn hóa bất biến cho toàn bộ 8 cạnh trong Graph Contract 1.0.0 và `configs/attack_semantics.yml`. |
| [ADR-0003](ADR-0003-host-access-inference-policy.md) | Chính sách suy luận cạnh truy cập máy chủ từ dữ liệu thu thập thô | 2026-09-15 | **Accepted (Amended)** | Tiếp thu sửa đổi từ Issue #80 / PR #90; phân định quyền cấu trúc và vị từ thực thi mạng/dịch vụ. |
| [ADR-0004](ADR-0004-synthetic-goal-edges-and-dcsync-co-occurrence.md) | Xử lý Synthetic Goal Edge và Điều kiện kép DCSync | 2026-09-14 | **Rejected / Superseded** | Bác bỏ cạnh $W=0$ và cạnh cấu trúc DCSync/ControlsDomain; DCSync nếu được mô hình hóa thuộc semantic/runtime theo ADR-0008, chưa có transition trong catalog; $W \ge 1.0$ theo Graph Contract 1.0.0. |
| [ADR-0005](ADR-0005-python-3-14-environment-standardization.md) | Chuẩn hóa môi trường Python 3.14 | 2026-09-15 | **Accepted** | Cố định môi trường runtime Python 3.14.x trên toàn repository. |
| [ADR-0006](ADR-0006-two-dataset-evaluation-framework.md) | Khung đánh giá đa tập dữ liệu song song | 2026-09-15 | **Superseded** | Thay thế hoàn toàn bởi ADR-0007. |
| [ADR-0007](ADR-0007-enterprise-topology-independent-telemetry-evaluation.md) | Khung đánh giá phối hợp: Topology doanh nghiệp SEAMLESS và Telemetry độc lập | 2026-09-16 | **Accepted** | Sử dụng topology quy mô doanh nghiệp SEAMLESS và tập telemetry Windows độc lập; phân định ranh giới kiểm toán. |
| [ADR-0008](ADR-0008-structural-graph-attack-semantics-layering.md) | Phân tầng Đồ thị Cấu trúc và Tầng Ngữ nghĩa Tấn công | 2026-09-22 | **Accepted** | Đồ thị cấu trúc lưu quan hệ AD có bằng chứng; tầng Attack Semantics (`configs/attack_semantics.yml`) mô tả transition và ExpectedTelemetry; `cost_factors` chỉ là descriptive research input, còn cost ownership giữa relationship, transition hoặc composition chờ quyết định kế thừa #42. |
| [ADR-0009](ADR-0009-direct-memberof-transitive-resolution.md) | Quyết định lưu trữ Direct-Only cho MemberOf và giải quyết quan hệ bắc cầu | 2026-09-22 | **Accepted** | Đồ thị chỉ lưu direct `MemberOf`; quan hệ thành viên bắc cầu được giải quyết ở tầng traversal/query. |
| [ADR-0010](ADR-0010-identity-asset-semantic-facets.md) | Định hình khía cạnh ngữ nghĩa Identity-Asset tách biệt khỏi node kind | 2026-09-22 | **Accepted** | Phân tách các chiều ngữ nghĩa khỏi schema cấu trúc của Graph Contract 1.0.0. |
| [ADR-0011](ADR-0011-canonical-derived-edge-lineage.md) | Canonical lineage cho cạnh cấu trúc dẫn xuất | 2026-09-23 | **Accepted** | Graph Contract 1.1.0; lineage có thứ tự, versioned, tham chiếu provenance; giữ ổn định edge ID và tương thích cạnh trực tiếp 1.0.0. |
| [ADR-0012](ADR-0012-canonical-collection-time-status.md) | Canonical collection-time status | 2026-09-24 | **Accepted** | Graph Contract 1.2.0; giữ status timestamp theo từng provenance record và legacy uncertainty, tách khỏi derivation lineage của #92. |
| [ADR-0013](ADR-0013-scoped-path-ranking-and-pareto-frontier.md) | Mô hình xếp hạng đường tấn công Pareto bảo thủ và đặc tả giao diện bàn giao | 2026-09-30 | **Proposed** | Thay thế phần production weighting của ADR-0001; xếp hạng Pareto bảo thủ trên khoảng xác suất có điều kiện và tác động nghiệp vụ, tie-break nỗ lực có điều kiện; giữ min-effort-to-DA và vết đường cấu trúc riêng; Insufficient Evidence trên SEAMLESS. |
