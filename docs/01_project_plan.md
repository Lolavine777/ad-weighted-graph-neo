# Kế hoạch và tiêu chí nghiệm thu

## Current-state amendment - 2026-10-09

Core query/search/CLI, Kerberoasting, AS-REP và RBCD đã được nhận; RBCD merge tại `be64798c89235f53c5c205894a7bac0f96437ce4`.
Scope mandatory Week 4 hiện gồm core và ba kỹ thuật; roasting deferred/RBCD stretch trong các checkpoint cũ là lịch sử, không là phạm vi hiện hành.
A đã [freeze và chạy scenario SEAMLESS](research/week4-seamless-scenario.md) qua public CLI: một generated program tới final asset goal dưới assumptions tường minh, với independent oracle/đối chứng và unrated.
Human-independent reproduction, B review và full manual docs/API audit còn pending trong #206/#239/#208; #204 chưa complete, #235 vẫn draft.
Actions billing/spending-limit chặn trước runner; infrastructure exception của RBCD không là CI PASS.
#237/#238 là P2 riêng; Top-K/viewer/Travel/housekeeping không tự thêm gate mandatory acceptance.
Week 5 giữ choke-point/remediation/sensitivity/BloodHound/metrics; CE validation cần scope/evidence riêng, không claim parity.
Các bảng/checkpoint phía dưới giữ làm lịch sử.

Nguồn yêu cầu: [đề bài](00_todo.md). Tài liệu này tổ chức thực hiện; các nhận định nghiên cứu phải có bằng chứng riêng.

Phạm vi cơ sở: snapshot tĩnh, đơn miền, phân tích dữ liệu được cung cấp. Mục tiêu mặc định là Domain Admins; Enterprise Admins/DC là tập đích bổ sung, cần định nghĩa rõ điều kiện kiểm soát. Không suy ra tên nhóm bằng chuỗi hiển thị nếu dữ liệu đã ẩn danh; lưu ID đích trong manifest thực nghiệm.

## Chien luoc du lieu va danh gia hien hanh

[ADR-0007](adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md) la nguon quyet dinh hien hanh.
SEAMLESS la primary raw structural/topology dataset va EDA source cho M2+.
Contract 1.3 accepts the observed AD Domain SID as typed Domain scope when objectGUID is absent.
The complete fail-fast canonical graph passes Contract validation; its structural node/edge projection was imported into project Neo4j while assessments remain in canonical JSON.
Historical checkpoint before 2026-09-29: PR #148 was under review for #138 acceptance.
Current closure: PR #148 was accepted and merged into develop on 2026-09-29; #138 is closed.
See [scope identity evidence audit](research/seamless-scope-identity.md).
A/NORTH va B/`ad_sampledata` duoc giu lam historical baseline cho regression, collector comparison, multi-domain/parser robustness va BloodHound reference.
Security logs la independent telemetry research source cho Attack Semantics va observability, khong duoc entity-level join voi SEAMLESS khi khac environment.
Structural graph van static va telemetry nam o semantic/evaluation layer.
BloodHound parity/reconciliation cho SEAMLESS la gioi han mo, khong phai evidence da co.

## Mốc M0–M5

Đề bài nhắc M0–M5 nhưng chưa đặt tên; bảng sau là cách ánh xạ của repo. Ngày bắt đầu và hạn lịch được điền khi nhóm chốt với mentor.

| Mốc | Thời điểm | A (@Lolavine777) | B (@nairyuuu) | Bằng chứng nghiệm thu |
| --- | --- | --- | --- | --- |
| M0 | Cuối tuần 1; nửa đầu dành setup | Khảo sát AD, ACL, group nesting, thống kê | Setup, import BloodHound, kiểm tra CI | Historical A/B baseline; SEAMLESS/telemetry manifests va EDA; CI xanh |
| M1 | Cuối tuần 2 | Taxonomy và nguồn, điều kiện từng cạnh | Schema và thiết kế parser | Review chung taxonomy/contract; mapping thuộc tính nguồn |
| M2 | Cuối tuần 3, giữa kỳ | Attack Semantics, rubric va danh gia rieng cho weighting | Pipeline structural graph tu SEAMLESS | ADR trọng số; graph và provenance; demo raw → graph |
| M3 | Cuối tuần 4 | Bộ ca xuất phát/đích, xác minh đường đi | Dijkstra, truy vấn, Top-K nếu đủ thời gian | Kết quả oracle, không có đường, đường song song, tổng chi phí |
| M4 | Cuối tuần 5 | Xếp hạng choke point, khuyến nghị | Tính metric, đối chứng BloodHound, timing | Bảng chênh lệch có giải thích; độ nhạy; tác động loại bỏ |
| M5 | Cuối tuần 6 | Phân tích và khuyến nghị báo cáo | Demo, tái lập, ghép báo cáo | Báo cáo, slide, demo từ checkout sạch, cả hai bảo vệ |

Top-K có trong phân công tuần 4 nhưng không nằm trong danh sách nghiệm thu bắt buộc; ưu tiên shortest path trước, báo mentor nếu cần điều chỉnh. RBCD, delegation, AD CS, tối ưu tập sửa và ước lượng thời gian là phần mở rộng sau các tiêu chí bắt buộc.

## Ma trận yêu cầu → bằng chứng

| Yêu cầu bắt buộc | Đầu ra cần tạo | Cách xác minh |
| --- | --- | --- |
| Mô tả dữ liệu và taxonomy | `docs/research/data-inventory.md`, `docs/research/taxonomy.md` | Thống kê theo loại; mẫu cạnh truy ngược nguồn; review A/B |
| Trọng số có lập luận, pipeline tự động | `docs/research/weight-model.md`, `configs/contract.yml`, `src/parser/` | Chấm độc lập; profile có version; raw → graph qua một lệnh |
| Đường chi phí nhỏ nhất tới DA | `src/engine/`, bộ ca và oracle | Test dữ liệu tổng hợp; đối chiếu chi phí; giải thích từng bước |
| Choke point và đối chứng | `docs/experiments/`, bảng metric | Cùng snapshot/tập đích/quan hệ; ghi mọi chênh lệch |
| Báo cáo, demo, tái lập | `reports/final-report.md`, README, slide | Người còn lại chạy theo README từ môi trường sạch |

Ma trận trên ghi kế hoạch đầu ra ban đầu theo [templates](templates/README.md), không phản ánh trạng thái hoàn thành hiện tại.

## Current-state amendment - 2026-09-23

M0 / Week 1 và M1 / Week 2 đã hoàn thành về technical deliverables theo [Week 1 review](worklog/week-01-review.md), [Week 2 review](worklog/week-02-review.md) và [closure audit](research/week-01-02-closure-audit.md); checkpoint này không tạo mentor sign-off mới.
Trong ma trận, data inventory, taxonomy, graph contract và parser foundation đã có; parser hiện gồm manifest-backed loader, canonical normalizer, reconciliation và direct-edge builder cho năm quan hệ source-backed.
Đây là một phần nền tảng M2 được triển khai sớm, nhưng M2 end-to-end chưa hoàn thành: host-derived graph, production weighting, CLI/integration và SEAMLESS same-snapshot evaluation còn các gate riêng.
Dijkstra và choke-point analysis thuộc các mốc M3/M4 và cũng chưa hoàn tất.
Xem [live checkpoint trong backlog](05_backlog.md) để biết issue ownership và trạng thái từng gate tại thời điểm này; các mốc M0–M5 và tiêu chí nghiệm thu phía trên vẫn là kế hoạch lịch sử.

## Current-state amendment - 2026-09-29

Feedback mentor ngày 2026-09-29 làm rõ định hướng đánh giá đường tấn công: dự đoán đường tấn công dựa trên cấu trúc, kỹ thuật và giả định kịch bản.
Xếp hạng cả đường đi theo khả năng thành công và tác động/rủi ro tới tài sản quan trọng; không yêu cầu thực nghiệm tấn công thật trên hệ thống.
Định hướng này không thay đổi các yêu cầu bắt buộc và tiêu chí nghiệm thu cốt lõi của [đề bài gốc](00_todo.md).
Các mục tiêu tìm đường chi phí thấp nhất tới Domain Admin / tài sản đích, so sánh kết quả và đối chứng với BloodHound, cùng phân tích nút thắt cổ chai (choke points) vẫn được bảo toàn trong roadmap M2-M5.
Quyền kiểm soát Domain Admin (hoặc usable identity S2) đóng vai trò proxy hoặc checkpoint đặc quyền cao nhất trong snapshot Active Directory, trong khi kịch bản mở rộng mô hình hóa đường tới các tài sản đích cụ thể (Domain Controller, tài nguyên Tier-0).
Để triển khai định hướng trên theo quy trình phân vai, khối việc weighting của TTS A được phân rã thành các issue độc lập: [#140](https://github.com/nairyuuu/ad-weighted-graph/issues/140) (scope, prediction orientation, target asset và scenario contract), [#141](https://github.com/nairyuuu/ad-weighted-graph/issues/141) (bản nháp mô hình rút gọn và rubric), [#142](https://github.com/nairyuuu/ad-weighted-graph/issues/142) (thử nghiệm và kiểm chứng worked example để hiệu chỉnh mô hình), và [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143) (successor ADR sau review và bàn giao interface cho B).

## Current-state amendment - 2026-10-06

[Final Week 3 handoff](reports/week3-final-handoff.md) pin measured integrated `develop@891bda0001b9958e712cff54045f651273b43fd0`, runtime, inputs/contracts/release và lệnh demo/tái lập.
Scoped model/interface/parameters, parser/demo và final search/semantic bridge/ranking integration đã accepted; #47 và #196 đã closed với exact-set evidence A/B.
B đã technically accept package #48/#158 sau fresh Legacy replay PASS trên `891bda0`; exact sets/difference ledger khớp accepted #196, final revision binding và cross-review kỹ thuật đã hoàn tất.
Exact package head `3c35667` có CI/branch policy success; [acceptance của B](https://github.com/nairyuuu/ad-weighted-graph/pull/202#issuecomment-6008927093) là evidence riêng với CI.
Còn merge #202 sau B rereview sửa current state, đóng #48/#143/#42/#158 theo closure evidence, final release review #186 rồi promote `develop → main` bằng merge commit nếu approval/checks đạt.
PrimaryGroupSid gap đã fix; comparator CLI thật giữ `NOT_MEASURABLE` / exit 2, search bounded/truncated với Source A positive 60.000 expansions và không claim global optimum/full BloodHound/CE parity.
Week 4 #192/#200, Top-K/scalable search và choke points không thuộc closeout này.
Các bảng/checkpoint trước là lịch sử kế hoạch, không phải blocker hiện hành hoặc yêu cầu làm lại rating research.

## Bổ sung kế hoạch M3 hiện hành - 06/10/2026 sau #205

Các checkpoint phía trên được giữ nguyên làm lịch sử.
Theo trạng thái GitHub đối chiếu tại `develop@a9fa71784513155496fcb4ee0f4367d25389d80d`, #201/#202/#186 đã merge; #42/#143/#48/#158/#47/#196 đã đóng.
#203 đã được A approve exact head `cfec850` rồi merge research; không còn hai blocker context/compatibility, chưa là implementation Week 4.
[Kế hoạch Week 4 đang dùng](reports/week4-plan.md) và [query contract](research/week4-query-contract.md) thực hiện scope core theo #204/#205, tách máy xuất phát, usable identity, DA checkpoint và quyền trên asset đích.
Người dùng khai báo nguồn/đích, khả năng ban đầu/context; hệ thống tự sinh đường trong supported scope.
Giữ riêng Min-Effort tới DA, reuse Dijkstra additive reference và bounded stateful search/whole-path evaluator của B; truncated không chứng minh global optimum/no-path hoặc K-best.
Missing runtime có thể dùng assumption tường minh đúng scope; không override known-false, không thêm fake canonical relationship, thiếu scoring basis giữ unrated.
Thứ tự A là #205 → #206/#207 → #208; B tự chia implementation, handoff khả thi/dependencies Week 4 đang chờ B xác nhận.
Roasting deferred riêng theo #192/#200; CE sau core giữ yêu cầu validation cuối trong roadmap Week 5-6, không là gate A1 hoặc core #205-#208 và không claim CE parity.
Không làm lại Week 3; A1 acceptance không thay implementation B hoặc nghiệm thu toàn tuần.

## Lịch phối hợp

Mỗi ngày ghi một worklog ngắn. Đầu tuần chọn issue trên [Project Board](https://github.com/users/nairyuuu/projects/3/views/1?system_template=kanban) có thể hoàn thành trong tuần, tối đa 1–2 việc đang làm mỗi người. Cuối tuần review với mentor: kết quả, demo, rủi ro, quyết định, tuần tới. Giữa kỳ và cuối kỳ dùng tiêu chí M2/M5 làm checklist nghiệm thu.

Rủi ro cần theo dõi: thiếu thuộc tính AD; khác phiên bản BloodHound; cạnh có nhiều điều kiện không biểu diễn được bằng một bước; trọng số thiếu căn cứ; phạm vi vượt 6 tuần. Ghi người xử lý và phương án thu hẹp trong issue, không tự điền giả định thành dữ kiện.
