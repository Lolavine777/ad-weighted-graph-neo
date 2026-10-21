# Backlog khởi đầu

Danh sách này là nội dung để tạo GitHub issues, chưa phải issues đã được mở. Mã Wxx dùng liên kết phụ thuộc trước khi có số issue thật. Sau khi tạo, ghi `#số` vào cột cuối và đưa vào [Project Board (Kanban)](https://github.com/users/nairyuuu/projects/3/views/1?system_template=kanban) để theo dõi luồng thực hiện; tiêu chí dưới đây dùng làm acceptance criteria. A/B là vai trò trong kế hoạch.

## Ghi chú chiến lược hiện hành

Bảng backlog bên dưới là kế hoạch khởi đầu và được lưu giữ như tài liệu lịch sử của Tuần 1.
Theo [ADR-0007](adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md), W02/W03 và các công việc phụ thuộc không còn được xem là dữ liệu đánh giá chính của A/B.
SEAMLESS đóng vai trò là tập dữ liệu cấu trúc tô-pô thô và EDA chính cho mốc M2 trở đi.
Telemetry là nguồn độc lập phục vụ ngữ nghĩa tấn công (Attack Semantics) và khả năng quan sát (observability).
Dữ liệu A/B tiếp tục phục vụ kiểm thử hồi quy (regression), so sánh collector, độ bền bỉ đa miền/parser và làm mốc đối chứng chuẩn cho BloodHound.
Contract 1.3 chấp thuận Domain SID quan sát được làm phạm vi định kiểu (typed scope) dù thiếu Domain objectGUID.
Quá trình khởi tạo đồ thị fail-fast và kiểm tra Contract đã hoàn tất thành công; phép chiếu cấu trúc đỉnh và cạnh đã được kiểm chứng trên Neo4j.
PR #148 giải quyết [#138](https://github.com/nairyuuu/ad-weighted-graph/issues/138) đã được nghiệm thu và merge vào nhánh `develop` ngày 2026-09-29; xem chi tiết tại [báo cáo kiểm toán định danh phạm vi](research/seamless-scope-identity.md).
W12 chỉ có thể kết luận mức độ tương đương (parity) với BloodHound cho SEAMLESS sau khi thực hiện import và đối chiếu trên cùng một snapshot và phạm vi.
Hiện tại không có mức độ tương đương nào của SEAMLESS được suy diễn từ bằng chứng A/B sẵn có.

| Mã | Mốc / chủ trì | Tiêu đề issue | Nghiệm thu | Phụ thuộc | Issue |
| --- | --- | --- | --- | --- | --- |
| W01 | M0 / B | Setup Python, CI, GitHub rules | Cả hai chạy checks; PR thử vào develop; main nhận từ develop | - | Chưa tạo |
| W02 | M0 / A | Inventory dữ liệu AD | Format/version/checksum; thống kê node/edge; trường thiếu; mô tả ẩn danh | - | Chưa tạo |
| W03 | M0 / B | Import BloodHound baseline | Ghi edition/version, lệnh import, counts và lỗi; tái lập được | W02 | Chưa tạo |
| W04 | M1 / A | Taxonomy cạnh và điều kiện | Mapping thuộc tính → hướng chuyển quyền; nguồn; điều kiện; phạm vi loại trừ | W02, W03 | #1, #2, #3, #4, #5 |
| W05 | M1 / B | Chốt schema node/edge | ID, cạnh song song, provenance, policy lỗi; fixture; A review | W02, W04 | #6, #7, #8, #9, #10 |
| W06 | M2 / A | Rubric và profile trọng số | Hai người chấm độc lập; công thức có lập luận; ADR; version profile | W04 | Chưa tạo |
| W07 | M2 / B | Parser raw → graph | Một lệnh tái lập; validation; báo lỗi; đối chiếu counts; tests raw tổng hợp | W05, W06 | Chưa tạo |
| W08 | M3 / A | Bộ ca kiểm chứng đường đi | Source/targets, oracle, điều kiện từng bước; no-path và ties | W05, W06 | Chưa tạo |
| W09 | M3 / B | Dijkstra engine | Đúng hướng/edge IDs/chi phí; source=target; no-path; CLI và tests | W07, W08 | Chưa tạo |
| W10 | M3 / B | Top-K đường đơn | Chốt nghĩa K và ties; cạnh song song; đối chiếu oracle nhỏ | W09 | Chưa tạo |
| W11 | M4 / A+B | Choke point và tác động loại bỏ | Định nghĩa tập đường; ranking; đo lại reachability/chi phí sau loại bỏ | W09 | Chưa tạo |
| W12 | M4 / B | So sánh BloodHound, timing | Cùng snapshot/scope; bảng chênh lệch giải thích được; timing lặp lại | W03, W09, W11 | Chưa tạo |
| W13 | M4 / A | Độ nhạy và đồng thuận trọng số | Perturbation có seed; top-K overlap/rank; thống kê chấm độc lập | W06, W11 | Chưa tạo |
| W14 | M5 / A | Báo cáo và khuyến nghị | Đủ tiêu chí đề bài; bảng/hình có nguồn; giới hạn và tính khả thi | W12, W13 | Chưa tạo |
| W15 | M5 / B | Demo và README tái lập | Checkout sạch; dữ liệu tổng hợp; hướng dẫn dữ liệu riêng; recording nếu cần | W09, W11 | Chưa tạo |
| W16 | M5 / A+B | Slide và diễn tập bảo vệ | Hai người giải thích taxonomy/trọng số/thuật toán; mentor feedback | W14, W15 | Chưa tạo |

W10 có thể thu hẹp sau khi trao đổi mentor nếu ảnh hưởng shortest path bắt buộc. Với W11/W16, vẫn chọn một assignee chịu trách nhiệm điều phối; người kia là đồng thực hiện/reviewer.

## Current-state amendment - 2026-10-06

Nguồn trạng thái cuối Week 3 là [final handoff](reports/week3-final-handoff.md) và #158, measured integrated `develop@891bda0001b9958e712cff54045f651273b43fd0`.
Model/interface và reviewed scoped release, parser/demo, semantic bridge/search/ranking integration đã accepted; #47/#196 đã closed sau fix PrimaryGroupSid và clean A/B reproduction.
B đã technically accept #48/#158 sau fresh Legacy replay PASS trên `891bda0`; final binding hoàn tất, exact sets/difference ledger khớp accepted #196 và comparator CLI thật `NOT_MEASURABLE` / exit 2.
Exact package head `3c35667` có CI/branch policy success; xem [B acceptance](https://github.com/nairyuuu/ad-weighted-graph/pull/202#issuecomment-6008927093).
Còn merge #202 sau B rereview sửa current state, đóng #48/#143/#42/#158 theo scoped closure evidence, final release review #186 rồi promote `develop → main` bằng merge commit nếu approval/checks đạt.
Bounded/truncated search, Source A positive 60.000 expansions và hạn chế global optimum/parity/calibration/independent-rating reliability/live attack giữ nguyên.
Week 4 #192/#200 giữ ngoài scope; các checkpoint dưới đây là lịch sử.

## Closure và amendments hiện hành

[Week 1 review](worklog/week-01-review.md), [Week 2 review](worklog/week-02-review.md) và [closure audit](research/week-01-02-closure-audit.md) ghi evidence cùng successor ownership.
Bảng W01-W16 phía trên là kế hoạch khởi đầu được giữ như lịch sử và các ô `Chưa tạo` không còn là live issue tracker.
M0 / Week 1 và M1 / Week 2 đã hoàn thành về technical deliverables.
ADR-0007/0008/0009/0010 và các accepted truth-migration issues là nguồn quyết định hiện hành khi chúng supersede mô tả lịch sử.

### Live checkpoint sau Week 2 - 2026-09-23

| Phạm vi | Live state | Ý nghĩa |
| --- | --- | --- |
| M0 / Week 1 | Technical deliverables complete | Historical A/B inventory/BloodHound baseline vẫn là regression evidence; ADR-0007 chuyển primary M2 topology sang SEAMLESS |
| M1 / Week 2 | Technical deliverables complete | Taxonomy, graph schema, parser interfaces, fixtures và CI đã được review; #79, #80 và #81 đã đóng sau truth-migration |
| Direct graph builder | #44 closed sau PR #104 | Năm direct/source-backed relationship đã có builder; không đồng nghĩa host-derived M2 scope hoàn tất |
| Weighting | #42 open | Historical double-blind MAUT body không phải implementation authority; successor cost-ownership decision còn cần chốt |
| Host-access / derived lineage | #45 và #92 open; PR #107 đang xử lý | Đây là M2 implementation/contract work, không phải missing M1 deliverable |
| Collection-time canonical status | #97 open | Successor serialization scope; loader-level policy #91 đã đóng |
| SEAMLESS BloodHound baseline | #82 open | M2 same-snapshot evaluation gap; không làm mất historical M0 closure |
| SEAMLESS canonical identity scope | Đã đóng (#138 merged qua PR #148) | The pinned snapshot lacks Domain objectGUID, but its observed Domain SID supplies typed scope under Contract 1.3. Full fail-fast graph and structural Neo4j projection are verified locally; final acceptance closed following PR #148 review and merge on 2026-09-29. |
| M2 integration | #46, #47 và #48 open | CLI/weighted output, reconciliation/evaluation và midterm handoff chưa hoàn tất |

#42 không còn bị #79 chặn vì #79 đã đóng.
#82, #92 và #97 là các successor gate hiện hành cho M2 theo phạm vi riêng.
Không dùng bảng historical Wxx để suy ra live completion nếu GitHub issue/accepted ADR hiện hành đã supersede nó.

### Live checkpoint sau mentor feedback - 2026-09-29

Feedback mentor ngày 2026-09-29 định hướng mô hình weighting chuyển sang dự đoán đường tấn công và xếp hạng đường theo khả năng thành công cùng tác động tới tài sản đích trong kịch bản.
Khối việc M2-A của TTS A (@Lolavine777) có checkpoint hiện hành sau PR #151 (giải quyết #150) ngày 2026-09-30:
- [#140](https://github.com/nairyuuu/ad-weighted-graph/issues/140): Cập nhật hướng prediction, tài sản đích và hợp đồng kịch bản (P0, M2-A; nghiệm thu qua PR #144).
- [#141](https://github.com/nairyuuu/ad-weighted-graph/issues/141): Thiết kế bản nháp mô hình trọng số / rubric rút gọn và quy tắc kết hợp (P0, M2-A; xem [path-ranking-model.md](research/path-ranking-model.md); nghiệm thu qua PR #147).
- [#142](https://github.com/nairyuuu/ad-weighted-graph/issues/142): Research testbed và counterexamples (P0, M2-A; xem [path-ranking-validation.md](research/path-ranking-validation.md); nghiệm thu qua PR #149).
- [#150](https://github.com/nairyuuu/ad-weighted-graph/issues/150): Hiệu chỉnh và bảo vệ proposal Pareto bảo thủ có phạm vi hẹp sau #142 (P0, M2-A; nghiệm thu qua PR #151; kết luận SEAMLESS là Insufficient Evidence).
- [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143): Soạn thảo successor ADR-0013 (Proposed), đặc tả giao diện v1.0.0 ([path-ranking-interface-specification.md](research/path-ranking-interface-specification.md)), bộ ví dụ synthetic kiểm thử được, và quy chế quản trị định mức/bằng chứng ([evidence-rating-governance.md](research/evidence-rating-governance.md)); tách biệt vết đường cấu trúc và Min-Effort-to-DA; bàn giao cho TTS B review (P0, M2-A). Bộ tham số, tích hợp và E2E tiếp tục pending.
Các mục tiêu kế tiếp M3 (Dijkstra và tìm đường), M4 (Choke points và đối chứng BloodHound), M5 (Báo cáo và demo) giữ nguyên lộ trình theo đề bài gốc.

## Phân rã công việc M1 (~1 ngày/issue)

Mốc M1 (Tuần 2, hạn nghiệm thu `2026-09-18`) được chia nhỏ thành các issue độc lập, hoàn thành trong tầm 1 ngày làm việc:
- **Thực tập sinh A**: `@Lolavine777` (Taxonomy, ngữ nghĩa quan hệ AD, nghiên cứu mô hình)
- **Thực tập sinh B**: `@nairyuuu` (Schema contract, kiến trúc parser, testing & CI)

| Mã | Issue | Phụ trách | Hạn (Due) | Tiêu đề issue | Tiêu chí nghiệm thu | Phụ thuộc |
| --- | --- | --- | --- | --- | --- | --- |
| M1-A1 | #1 | @Lolavine777 | 2026-09-14 | `[Research] Taxonomy: Ngữ nghĩa & điều kiện cho MemberOf và HasSession` | Hướng cạnh, điều kiện kích hoạt HasSession (cần local admin dump LSASS); đối chiếu BloodHound | W02, W03 |
| M1-A2 | #2 | @Lolavine777 | 2026-09-15 | `[Research] Taxonomy: Điều kiện kỹ thuật cho AdminTo, CanRDP, CanPSRemote` | Ma trận port/service/chính sách UAC; xác định node nguồn/đích hợp lệ | W02, W03 |
| M1-A3 | #3 | @Lolavine777 | 2026-09-16 | `[Research] Taxonomy: Hướng chuyển quyền nhóm ACL (GenericAll, WriteDacl, ForceChangePassword)` | Cơ chế leo quyền lên User/Group/Computer; cách mô hình hóa cạnh trực tiếp vs trung gian | W02, W03 |
| M1-A4 | #4 | @Lolavine777 | 2026-09-17 | `[Research] Taxonomy: Chính sách lọc ngoại lệ và biên đồ thị (Pruning Policy)` | Quy tắc lọc tài khoản disabled/expired; self-loop; blacklist/whitelist object đặc biệt | M1-A1..A3 |
| M1-A5 | #5 | @Lolavine777 | 2026-09-18 | `[Task] Tổng hợp Taxonomy v1.0 và review chéo với B` | Hoàn thiện `docs/research/taxonomy.md` theo template; @nairyuuu approve để khóa contract | M1-A4 |
| M1-B1 | #6 | @nairyuuu | 2026-09-14 | `[Task] Contract: Chuẩn hóa Schema Node và định danh Canonical ID` | Format ID duy nhất/bất biến (SID/GUID/hash); thuộc tính bắt buộc vs tùy chọn; cập nhật check_contract | W02 |
| M1-B2 | #7 | @nairyuuu | 2026-09-15 | `[Task] Contract: Chuẩn hóa Schema Edge, Multigraph và Provenance` | ID cạnh duy nhất; hỗ trợ đa cạnh song song giữa 2 node; lưu thông tin nguồn audit | M1-B1 |
| M1-B3 | #8 | @nairyuuu | 2026-09-16 | `[Task] Parser: Thiết kế kiến trúc module Parser & Error Handling Policy` | Interface DataLoader, Normalizer, GraphBuilder; policy lỗi (SKIP, FAIL, WARN) | M1-B2 |
| M1-B4 | #9 | @nairyuuu | 2026-09-17 | `[Task] Testing: Xây dựng Synthetic Fixtures chi tiết cho 8 loại cạnh M1` | Tạo `data/samples/` fixture có chu trình, cạnh song song, node cô lập; test contract pass 100% | M1-B2 |
| M1-B5 | #10 | @nairyuuu | 2026-09-18 | `[Task] CI: Mở rộng kiểm thử tự động toàn vẹn đồ thị và CI contract M1` | Chặn cạnh mồ côi (dangling edges), trùng ID; CI test pass trên Windows và Ubuntu | M1-B4, M1-A5 |
