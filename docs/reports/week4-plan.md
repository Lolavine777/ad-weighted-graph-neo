# Kế hoạch Week 4 / M3 - handoff A1

## Trạng thái hiện hành - 09/10/2026

Core query/facts/Min-Effort/CLI cùng Kerberoasting, AS-REP, RBCD đã merge; mandatory scope hiện gồm core và ba techniques.
RBCD được nhận tại `be64798c89235f53c5c205894a7bac0f96437ce4`; không giao lại implementation cho B.
A đã [freeze scenario và đối chiếu public SEAMLESS generation](../research/week4-seamless-scenario.md), đạt asset dưới explicit assumptions và giữ RAW/false/unknown/unrated.
Remaining acceptance là B review/cross-reproduction và full manual docs/API audit trong #206/#239/#208; #204 OPEN, promotion #235 DRAFT.
Actions chưa chạy do billing, không claim CI PASS; #237/#238 P2 research không là gate mới.
Các mục kế hoạch A1 và wording deferred/stretch phía dưới là snapshot 06/10/2026, giữ để truy vết.

Ngày cập nhật: 06/10/2026; owner TTS A; reviewer TTS B.
Phạm vi thực hiện của tài liệu là [#205](https://github.com/nairyuuu/ad-weighted-graph/issues/205), theo quyết định của A trong [tracker #204](https://github.com/nairyuuu/ad-weighted-graph/issues/204).
Baseline đọc source: `develop@a9fa71784513155496fcb4ee0f4367d25389d80d`, contract 1.3.0, catalog 0.3.
Đây là kế hoạch và yêu cầu kiểm chứng, chưa là kết quả chạy các query Week 4 hoặc xác nhận B đã nhận dependency.

## Phạm vi đang dùng

Người dùng khai báo máy xuất phát, đích, khả năng ban đầu và context; hệ thống tự sinh đường trong phạm vi hỗ trợ.
Không yêu cầu người dùng nhập ordered attack path hoặc query ID đã chọn sẵn trong production.
Bộ query nhỏ trong [query contract](../research/week4-query-contract.md) chỉ là bằng chứng kiểm chứng chức năng tổng quát đó.

| Phạm vi | Nội dung | Điều kiện nhận / giới hạn |
| --- | --- | --- |
| Core bắt buộc | Source/target tùy khai báo; host control và usable identity riêng; tìm Min-Effort tới DA; goal quyền trên asset riêng; blocked/indeterminate; ranking toàn đường; oracle và tái lập | Tái sử dụng nền Week 3; B review scope/interface; số điểm chỉ có khi basis/bindings phù hợp |
| Extension deferred | Một AS-REP chain theo #192/#200/#201; Kerberoasting dự phòng | Research đã review nội bộ; mentor chưa xác nhận asset/evidence/abstraction; B chưa bàn giao implementation; không chặn core |
| Stretch | Top-K, ticket/lifetime chi tiết, RBCD | Chưa cam kết; chỉ nhận sau review scope/proof/coverage riêng; không chặn core |
| Roadmap sau core | CE validation; Week 5 choke points/đối chứng/sensitivity; Week 6 demo và bảo vệ cuối | CE không là gate #205-#208; chưa giao converter, chưa có CE parity |

Giữ riêng yêu cầu gốc công sức nhỏ nhất tới DA và mục tiêu đạt quyền trên tài sản cụ thể.
DA entitlement hoặc usable DA identity là checkpoint khi truy vấn tới asset, không tự tạo `AdminTo` hoặc chứng minh `admin_control(C0)`.
Giả định dùng đúng policy trong query contract, không sửa raw/canonical graph; thiếu cơ sở C/P/I thì để `unrated`.
Không triển khai parser/engine/catalog, chấm lại Week 3, chạy exploit hoặc nhận việc B trong #205.

## Ma trận yêu cầu, query và người chủ trì

Expected output dưới đây là mục tiêu nghiệm thu; hiện chưa chạy các ca mới.
Tất cả query thừa hưởng bindings, caps, policy và gói evidence chung của query contract.

| Yêu cầu | Query / case | Dữ kiện / giả định chính | Kết quả cần đạt | Verification / evidence | Chủ trì |
| --- | --- | --- | --- | --- | --- |
| Máy xuất phát tới tài sản | Q-ASSET | X là Computer; usable U/context khai báo riêng; quyền và runtime đủ theo scenario | Đường tự sinh; goal `admin_control(C0)` đạt dưới giả định đã dùng | Oracle semantic độc lập, trace từng bước và final state | A2 #206; B nối input/search |
| Min-Effort tới DA | Q-DA | Membership/provenance và identity usable trong đúng context; fixture effort được review | Min-Effort tới checkpoint DA; không gắn nhãn asset success | Duyệt hết không gian nhỏ, đối chiếu chi phí toàn chương trình, không dùng ranking làm oracle | A2 #206 + A3 #207; B mapping goal |
| Nhiều đường và ranking | Q-MULTI | Hai route khác work units/prefix; bindings và basis rõ | Min-Effort theo effort, ranking toàn đường; không chọn theo số cạnh | Tập chương trình/chi phí kỳ vọng độc lập; ties, ledger và dedup | A2/A3; B evaluator |
| Giả định và false veto | Q-GATES / U, A, F | Cùng query; chỉ đổi một runtime gate, các gate khác thỏa mãn | Unknown → indeterminate; assumption → có thể applicable; known-false → blocked | So sánh prerequisite decisions, không success effect ở unresolved/false gate | A2; B fact-resolution |
| DA chưa là quyền asset | Q-CHECKPOINT / F, U | DA checkpoint đạt; asset gate false hoặc missing | Checkpoint đạt nhưng final goal blocked/indeterminate | Check cả checkpoint và asset predicate; graph digest không đổi | A2; B auth/asset |
| Đổi đầu vào qua cùng entry point | Q-INPUT / S, I, H | Đổi X→Y, usable U→V hoặc auth context H0→H1 riêng | Kết quả theo state/context; không có actor switching ngoài scope | Cùng public entry point do B bàn giao, không hardcode case ID | A2; B entry point |
| No-path và giới hạn search | Q-COVER / N, P, E, S | Fixture finite đầy đủ và ba biến thể chạm từng cap | No-path chỉ trong scope complete; truncated ghi lý do, không claim optimum | Oracle independent, caps/counters, search audit và ranking coverage khớp | A2/A4 #208; B search |
| Chưa chấm và provenance | Q-SCORE | Thiếu một basis hoặc binding; không thêm rating từ applicability | `unrated` / diagnostic; không bịa giá trị hoặc dùng điểm Week 3 cho action mới | Ledger, release/policy digests, binding diagnostics | A3; B consume |
| Gói tích hợp tái lập | Q-REPLAY | Cùng revision/input/config/scope; private prerequisites sẵn có | Hai lượt xác định và người còn lại tái lập | Lệnh thật, digests, diff ledger, report/demo | A4; B executable handoff |
| Extension recovery | E-ASREP | Evidence #201; runtime/recovery/auth/asset còn điều kiện | Material, recovered secret, usable identity, asset tách riêng | Chỉ mở ca implementation khi extension được nhận; không dùng để đóng core | A nghiên cứu; B state/trigger; deferred |

## Phân công, phụ thuộc và thứ tự

| Gói | A phụ trách | Dependency B cần review/bàn giao | Trạng thái |
| --- | --- | --- | --- |
| A1 #205 | Plan, query contract, disposition #203 và checklist | Khả thi của handoff; scope/goal/source mapping và entry point | Đang chờ B xác nhận kế hoạch này |
| A2 #206 | Reuse golden nền, delta ca/oracle độc lập, evidence/alias | Owner/trigger/state/input/harness còn thiếu trong scope nhận | Chưa giao task B mới; B tự chia và liên kết issue/PR |
| A3 #207 | Work-unit ledger, C/P/I basis hoặc disposition unrated; kiểm tính lặp | Consume evaluator/bindings, không đổi provenance/release accepted | Chưa có xác nhận B cho delta Week 4 |
| A4 #208 | Nghiệm thu tích hợp, trace/coverage, report tiếng Việt 1-3 trang, demo | Code đã review, commands/CLI/harness, fixes thuộc parser/engine | Chờ A1, A2/A3 và B executable handoff |

Thứ tự là #205 → #206 và #207 song song sau khi scope/interface ổn → #208.
A2 có thể audit/reuse nền trước; freeze delta sau A1; A3 không chặn B làm semantic correctness.
Mỗi người giữ tối đa 1-2 việc đang làm.
Ước lượng lập kế hoạch theo #204: A1 0,5-1 ngày; A2 khoảng 1 ngày; A3 khoảng 1 ngày; A4 khoảng 1 ngày sau B handoff.
Đây không là thời lượng đã làm, deadline hay cam kết lịch của B/mentor.
Không tự tạo hoặc assign issue B; B cần trả lời phạm vi nhận, interface dùng, giới hạn và liên kết task triển khai do B chủ trì.

## Disposition PR #203 đối chiếu interface thật

[PR #203](https://github.com/nairyuuu/ad-weighted-graph/pull/203) đã merge ngày 06/10/2026 tại `a9fa71784513155496fcb4ee0f4367d25389d80d`.
[Review đầu của A](https://github.com/nairyuuu/ad-weighted-graph/pull/203#pullrequestreview-5424573544) nêu hai blocker tại `ea205a6`: thiếu context của usable identity và thiếu bảng compatibility.
[B sửa tại cfec850](https://github.com/nairyuuu/ad-weighted-graph/pull/203#issuecomment-6010767431), rồi [A approve exact head](https://github.com/nairyuuu/ad-weighted-graph/pull/203#pullrequestreview-5425259538); hai blocker nghiên cứu đã giải quyết.
Review đó được tái sử dụng, không yêu cầu review lại quyết định đã accepted.

| Quyết định được nhận | Interface tại baseline | Disposition / phần còn lại |
| --- | --- | --- |
| `UsableIdentity(principal, authentication_context)` | [AttackState/RuntimeContext](../../src/engine/semantics/state.py); [evaluator](../../src/engine/semantics/evaluator.py) kiểm tuple đúng context | Retain authoritative; actor switching phải giữ scope; không nâng identity thành bảo đảm toàn dịch vụ |
| Giữ bucket khác nghĩa | `credential_material`, `authentication_control`, `reset_password_control`, `usable_identity`, `admin_control`, `remote_command_execution` đang riêng | Nhận bảng retain/distinct/migration #203; không collapse hoặc đổi schema ở A1 |
| Bridge không mô phỏng ticket mặc định | [Search](../../src/engine/search.py) sinh `AuthenticationControl` từ `reset_password_control`; catalog vẫn bounded | `activate_identity`, `CredentialPossession`, `HostExecution` là vocabulary nghiên cứu; tên action/API tương lai là proposed, không mặc định đã có callable/typed bucket |
| Giữ work-unit lịch sử | `acquire_ticket` là compatibility alias trong rating/work-unit, không là chứng cứ request TGT | Không đổi IDs/ratings/release Week 3; B quyết định mapping/migration riêng khi cần |
| Whole-path và coverage | [Orchestration](../../src/engine/ranking/orchestration.py) nối generate → exact action bindings → evaluator | Reuse; unbound transition có diagnostic và bị loại khỏi ranking; phải đối chiếu search audit trước claim |
| Recovery extension | Catalog/search hiện chưa có roast/recover chain; generator xét relationships và reset bridge | `RecoverableAuthMaterial → CredentialPossession → scoped usable identity → asset` được nhận ở research; cần B trigger/projection/typed state nếu extension mở |

Không còn yêu cầu B sửa blocker research #203.
Follow-up core thực sự cần B review là mapping X/usable U và DA goal qua entry point, fact-resolution/provenance, auth/asset semantics cùng coverage/bindings cho delta ca.
`generate_and_evaluate_attack_paths` hiện buộc `actor == query_metadata.foothold_node_id`; `generate_attack_paths` khởi đầu từ actor được truyền và đổi actor qua reset bridge, chưa chứng minh mọi usable identity có sẵn được chọn làm actor từ Computer X.
DA goal cần B đối chiếu với điều kiện terminal theo node đích của generator và target-asset metadata của ranking; A không invent API để đi vòng.
Nếu source hiện hành khác research về reset/activation hoặc remote privilege, B đánh giá và tách fix/regression theo scope nhận, không mở lại Week 3 acceptance.
Ticket artifact/service scope chỉ cần khi ảnh hưởng applicability; ca C5 giữ các predicate khác thỏa mãn để cô lập unknown/assumption như lưu ý non-blocking của review.
Chưa có B confirmation cho những follow-up Week 4 này.

## Tái sử dụng nghiên cứu và roadmap

[#200](https://github.com/nairyuuu/ad-weighted-graph/issues/200) và [PR #201](https://github.com/nairyuuu/ad-weighted-graph/pull/201) cung cấp [sàng lọc/evidence](../research/week4-prediction-evidence.md) và [bản đề xuất](../research/week4-prediction-proposal.md).
B đã approve #201 sau khi tách DA checkpoint khỏi final `admin_control(C0)`; research merge không là scope mentor accepted hoặc implementation.
Tái sử dụng revision/limitation và nguồn cơ chế đã dẫn trong #201/#203; không khảo sát lại toàn bộ kỹ thuật hoặc thêm claim cơ chế mới ở A1.
Roasting deferred riêng theo [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192)/#200; không chờ mentor để nghiệm thu core #205-#208.
CE deferred sau core: #127 `not_planned` không bỏ yêu cầu đối soát cuối; cần scope/snapshot/version và evidence riêng trong roadmap Week 5-6.
Không claim Legacy reconciliation là CE parity, không yêu cầu CE probe/mentor/converter để đóng A1.

## Checklist toàn bộ AC #205

| AC của issue | Bằng chứng A1 | Trạng thái nghiệm thu |
| --- | --- | --- |
| Mỗi yêu cầu có query/case, output, verification, owner; core/extension/stretch riêng | Ma trận phía trên và danh mục query | Đã document; chưa chạy delta Week 4 |
| B xác nhận handoff khả thi và dependencies B | Bảng phân công, disposition và yêu cầu review trong PR | Đang chờ B; task B mới chưa giao |
| Tách host control, usable identity, DA checkpoint, asset goal | Query contract mục đầu vào/goals và Q-CHECKPOINT | Đã document |
| Nghĩa optimal/no-path/Top-K đúng coverage | Query contract mục search; Q-MULTI/Q-COVER | Đã document; không nhận thuật toán/scope mới |
| Disposition #203 cụ thể; API/action proposed tới accepted interface | Bảng disposition với source/review exact head | Research accepted; follow-up implementation chưa xác nhận |
| Reuse #192/#200/#201; roasting/CE deferred; input/generation/assumptions rõ | Phạm vi, roadmap, policy và interface mapping | Đã document; research không là code |
| A2/A3 → A4; gate A/toàn tuần; B review và checks exact PR head | Checklist dưới đây; worklog/PR ghi lệnh và CI/head thực tế | Chờ B review; checks ghi theo kết quả thật |

## Điều kiện hoàn tất A và toàn tuần

A1 có thể được B nghiệm thu trước implementation khi scope/query/interface/dependencies đã review rõ và required checks đạt trên exact PR head.
Điều đó chỉ chứng minh handoff A1, không chứng minh query đã chạy hoặc tracker Week 4 complete.

- [ ] A1: đầy đủ AC #205; B xác nhận khả thi/dependencies, approval và checks exact head.
- [ ] A2: oracle độc lập và delta ca đủ coverage; reuse golden nền, không lấy ratings/ranking làm oracle.
- [ ] A3: work units/basis/bindings được review hoặc unrated đúng phạm vi; không trình bày synthetic ratings như đo thực tế.
- [ ] A4: report/demo dùng output thật; commands/input/config/revision pin; hai lượt xác định và người còn lại tái lập.
- [ ] B: task triển khai do B tự nhận đã liên kết; code/interface/CLI/harness được review và bàn giao evidence.
- [ ] Tích hợp: ít nhất một Computer foothold → asset đủ điều kiện theo giả định; checkpoint DA báo riêng.
- [ ] Min-Effort: đúng oracle trong finite complete scope; SEAMLESS báo caps, coverage và giới hạn tối ưu.
- [ ] Negative coverage: false veto, indeterminate, no-path complete và truncation; không success effect ở unresolved gates hoặc thêm fake canonical edge.
- [ ] Required CI/checks và cross-review exact head đạt; các issue con/PR đã được tiếp nhận.

Thiếu private inputs, mapping quyền hoặc runtime basis là blocker của ca chạy thật tương ứng, không được thay bằng output synthetic rồi gọi SEAMLESS thành công.
Tracker #204 chỉ complete khi cả đầu ra A, dependency B và gói tích hợp core đạt; extension/CE deferred được report riêng.
