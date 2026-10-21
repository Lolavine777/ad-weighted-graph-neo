# Query contract Week 4 - yêu cầu handoff A1

Ngày 06/10/2026; TTS A chủ trì yêu cầu/oracle, TTS B chủ trì schema/catalog/state/search/API.
Refs [#205](https://github.com/nairyuuu/ad-weighted-graph/issues/205), [#204](https://github.com/nairyuuu/ad-weighted-graph/issues/204); kế hoạch, owner và dependencies ở [Week 4 plan](../reports/week4-plan.md).
Đối chiếu source tại `a9fa71784513155496fcb4ee0f4367d25389d80d`; contract 1.3.0, catalog 0.3.
Các Q/E bên dưới là nhãn ca nghiệm thu, không là API/schema mới hoặc danh sách query IDs bắt buộc trong production.
Chưa chạy ca mới, chưa có B confirmation cho mapping/entry point Week 4.

## Đầu vào, alias và hai mục tiêu

Người dùng chọn nguồn/đích, khai báo initial capability và context; hệ thống tự tìm đường, không nhận ordered path làm điều kiện sử dụng.
Alias X/Y chỉ Computer foothold, U/V chỉ principal, G-DA chỉ nhóm DA đúng scope, C0/C1 chỉ asset Computer, H0/H1 chỉ authentication context.
C0 trong synthetic fixture và C0 trong SEAMLESS là alias thuộc hai input bindings riêng, không được coi là cùng định danh.
Mapping private identities/raw locators giữ trong inputs local có digest; public docs/evidence dùng alias.
Không infer G-DA/C0 từ display name; resolve theo ID/role/provenance trong local manifest.

| Đầu vào phải pin | Ý nghĩa / mapping hiện có | Điều kiện kiểm |
| --- | --- | --- |
| Snapshot, graph, contract/catalog, revision | Canonical graph đã validate; input/raw/graph digests và version | Không trộn snapshots hoặc nâng assumption thành dataset provenance |
| Source X / target | X có kind Computer và foothold khai báo; target là G-DA hoặc asset cụ thể theo goal | Node tồn tại; source Y dùng cùng entry point; không chọn sẵn ordered path |
| Initial host control | Mức quyền trên X khai báo riêng; `admin_control(X)` chỉ khi có evidence/assumption tương ứng | `control(U)` không mặc định bằng host admin hoặc usable identity |
| Initial usable identity | Principal U cùng context H0; current `usable_identity={(U,H0)}` nếu thực sự khai báo đủ | X có quyền không tự sinh U; secret/material cũng không tự là usable identity |
| Runtime/context/horizon | Typed `RuntimeFact`, `RuntimeContext.authentication_context`, phạm vi/time window trong scenario ledger | Không hardcode horizon 10 giờ; đổi time/context phải rebuild state/context |
| Owners/techniques | Subset được review của 13 owner catalog 0.3; fixture/request ledger nêu owner IDs thực tế và digest | Không sinh kỹ thuật ngoài supported scope; không collapse các bucket theo vocabulary #203 |
| Goal predicate | Predicate node và success-state riêng; DA checkpoint tách asset action | Chạm node hoặc membership không tự chứng minh quyền asset |
| Budgets | `SearchBudget(max_paths, max_steps, max_expansions)` | Số nguyên dương pin trước chạy; cả ba cap và counter/lý do xuất hiện trong evidence |
| Ranking/basis | Exact `(technique_id, actor, source, target)` action bindings; work units/release/policy digests | Không dùng supplied candidate envelope thay output generator; thiếu basis/binding phải có disposition |

Goal DA của Q-DA là có principal U/V với usable identity trong đúng H0 và effective entitlement tới G-DA trong scope được kiểm, rồi Min-Effort tới checkpoint đó.
Goal asset của Q-ASSET là `C0 in final_state.admin_control`; `remote_command_execution(actor,C0)` hoặc `interactive_session(actor,C0)` không tự đủ.
Predicate tới DA cần B xác nhận mapping với terminal-node rule của generator và metadata asset trong ranking; đây là yêu cầu riêng, chưa là accepted API.
Không chấm impact của asset nếu chưa có asset value basis được review.

## Policy facts, assumptions và chưa chấm

Fact đáng tin, applicable trong scope được dùng cùng provenance; không tạo assumption cho chính fact đó.
Thiếu required runtime/environment fact và chưa có assumption thì giữ `indeterminate`.
Assumption đúng scope có thể cho kết quả đủ điều kiện trong scenario, không chứng minh observed success ngoài đời.
Known-false hoặc evidence conflict theo accepted fact-resolution policy; assumption true không được ghi đè known-false cùng scope.
Nếu evidence/assumption xung đột, giữ observed fact và báo conflict/reject theo interface, không thay record trong mapping để làm đường chạy được.
Q-GATES/F phải giữ known-false authoritative để evaluator trả blocked, đồng thời ghi assumption true bị từ chối ở ledger riêng.
Current `RuntimeContext` reject duplicate keys trái giá trị trước evaluation; exception constructor riêng lẻ chưa là bằng chứng đạt demo blocked, mapping/normalization này cần B xác nhận.
Counterfactual dùng view riêng có nhãn, trace và binding riêng, không sửa raw/canonical facts.

Mỗi assumption ghi predicate/giá trị, subject/target, context/scope, horizon khi relevant, người/nguồn khai báo và lý do.
Reuse `RuntimeFact(predicate, subject, target, value, origin, scope, rationale, provenance_reference, assumption_metadata)` cùng scenario ledger hiện có; B quyết định mapping metadata/API, A1 không invent schema.
`FactOrigin.DECLARED_ASSUMPTION` khác `OBSERVED_EVIDENCE`; bool legacy `UNSPECIFIED` không là fact authoritative cho generator hiện hành.
Facts/assumptions và branch-local derived state giữ riêng với structural graph.
Không bịa quan hệ X→U, SPN/pre-auth hoặc quyền host trong canonical graph; unknown không là positive traversal edge.
Chỉ `APPLICABLE` mới apply success effects; false/unknown attempts vẫn giữ diagnostics.

Applicability không tự tạo C/P/I; missing probability/effort/impact basis giữ `unrated` hoặc dùng judgment/fixture được review và gắn nhãn theo governance hiện hành.
Unbound transition được giữ trong search audit/binding diagnostics, không coi nó là numeric ranked result.
Kết quả cần giữ riêng semantic status, checkpoint/goal, scoring status và coverage.
Một query không có rated result chưa chứng minh không có semantic path.

## Thiết kế tìm đường và mức bảo đảm

Giữ [search của B](../../src/engine/search.py) và [orchestration hiện hành](../../src/engine/ranking/orchestration.py).
`shortest_path` là Dijkstra tham chiếu cho finite non-negative additive structural cost; kết quả topology không chứng minh semantic applicability hoặc Min-Effort toàn chương trình.
`generate_attack_paths` nhận graph, actor, initial state, runtime context, target predicate, budget và optional success-state predicate; giữ state/derived relationships trong branch, đánh giá từng owner theo catalog.
`generate_and_evaluate_attack_paths` tự sinh candidates rồi nối exact action bindings và whole-path evaluator, không phát lại ordered candidates do query cung cấp như search output.
Current orchestration yêu cầu actor trùng `query_metadata.foothold_node_id`; không mặc định đã có public CLI mapping mọi X/initial usable U hoặc goal DA.
B cần review mapping đó, không đổi thiết kế search của B trong A1.

Finite complete scope phải pin snapshot, states/capabilities, owner subset, context/horizon, allowed action reuse và work-unit rules; A2 oracle duyệt độc lập toàn bộ programs hợp lệ trong scope nhỏ.
Generator hiện giới hạn reuse qua action key `(relationship, technique, actor)` trong từng branch; đây là phạm vi coverage, không là mọi attack program ngoài đời.
`complete = not truncated` chỉ mô tả generator đã hết candidates trong supported scope đó.
Min-Effort được claim trong finite complete scope khi tập programs và effort basis được đối chiếu oracle, bindings không thiếu, không có candidate unrated chưa so sánh được.
Nếu rating/binding còn thiếu, chỉ nói minimum trong rated comparable subset và nêu phần bị loại; không claim minimum toàn bộ đường khả thi.
SEAMLESS hoặc search truncated chỉ được nói minimum trong generated/rated subset, với caps/coverage và exclusions rõ.
Không dùng kết quả bị cắt để chứng minh global optimum hoặc no-path.
No-path chỉ được claim trong finite complete supported scope đã kiểm oracle và không bị unresolved gate che khuất; unknown thì nói chưa xác định dưới dữ kiện hiện tại.
`max_paths=K` là cap số paths được sinh, không chứng minh K-best.
Top-K deferred/stretch; nếu sau này nhận, K là số chương trình theo effort ordering, báo ties ở biên K và tie-break deterministic, yêu cầu coverage/proof riêng trước claim K-best.
Không thêm Top-K/global optimum hoặc thuật toán mới làm blocker core.

## Danh mục query nhỏ và verification độc lập

Tất cả ca dùng alias/bindings và policy chung ở trên; A2 freeze concrete owner IDs, input digests, facts và caps sau B scope review.
Không đưa số effort giả vào A1; A3 cung cấp synthetic basis được review hoặc disposition unrated.
Caps cho fixture nhỏ được chọn đủ để duyệt hết scope oracle, rồi pin thành input trước chạy; không tăng cap sau chạy để che truncation.
Baseline đề nghị reuse từ `tests/fixtures/attack_scenarios/suite.json`: `max_paths=1000`, `max_steps=12`, `max_expansions=100000`; ca cần 15 steps reuse budget tương ứng trong suite thay vì gọi 12 steps complete.
Đây là cấu hình kiểm chứng có sẵn, chưa chứng minh đủ cho delta mới; A2/B phải đối chiếu oracle scope trước freeze.
Q-COVER/P, E, S giảm riêng cap tương ứng xuống 1 trên fixture có continuation độc lập đã biết để chủ động kiểm lý do cắt.
Caps SEAMLESS reuse [gói Week 3](../reports/week3-final-handoff.md) hoặc cấu hình B đã review với digest mới; chưa có giá trị Week 4 accepted.
Các expected output là yêu cầu để #206/#207/#208 tạo evidence, không là claims đã chạy.

Owner IDs dùng vocabulary [catalog hiện hành](../../configs/attack_semantics.yml), không lấy tên proposed của #203 thay ID runtime.
Q-ASSET/Q-DA/Q-CHECKPOINT/Q-INPUT xét subset cần thiết của `propagate_group_entitlement`, `scenario_reset_password`, `acquire_reset_identity`, `scenario_winrm_admin`; nhánh ACL thêm `genericall_reset_password`, `reset_target_password`, `genericall_grant_write_dacl`, `grant_new_object_right` khi oracle/input có support.
Q-MULTI/Q-COVER reuse chính owner list của fixture tương ứng; Q-GATES dùng `open_winrm_remote_session` để cô lập `winrm_available`, với goal remote execution riêng, không đòi admin.
Q-SCORE/Q-REPLAY thừa hưởng owner set của positive query được chọn; mọi scope cuối cùng phải pin list/digest trong manifest, B review nếu mapping cần delta.

| Query / mục tiêu | Đầu vào, facts/assumptions và owner scope | Expected output | Verification / chủ trì |
| --- | --- | --- | --- |
| Q-ASSET: từ X tới C0 | Computer X controlled theo khai báo; U usable tại H0 riêng; reuse `acl-auth-host`/ca SEAMLESS nền với owner reset/activation/host đã accepted; quyền C0 source-backed, runtime gates explicit | Đường tự sinh đến `admin_control(C0)` khi đủ điều kiện; checkpoint DA báo riêng nếu xuất hiện; điểm chỉ có basis | A2 kiểm prerequisites, state cuối/trace/provenance; B input/auth/asset mapping; A4 chạy thật |
| Q-DA: công sức nhỏ nhất tới G-DA | X + initial U/H0; membership closure gồm inherited scope theo input; finite fixture có ít nhất hai programs tới usable effective DA; owner subset core | Minimum effort tới DA trong complete oracle scope; không gắn asset success; missing effort giữ unrated | A2 oracle membership/identity/programs độc lập; A3 ledger tổng effort; B goal interface |
| Q-MULTI: nhiều đường tới C0 | Reuse `two-routes` và delta core cần thiết; cùng X/U/H0/C0, route khác prefix/work units; mọi fact/applicability đủ và synthetic basis được review | Tập paths và effort đúng oracle; work unit lặp xử lý theo model; tie được báo; ranking toàn đường giữ C/P/I riêng | A2 duyệt scope độc lập; A3 kiểm ledger/dedup/ordering, so Dijkstra chỉ trên additive baseline; B binding/evaluator |
| Q-GATES: U/A/F cùng query | U: thiếu một runtime gate; A: assumption true đúng scope thay unknown; F: giữ gate known-false và ledger assumption true bị từ chối; tất cả gate khác thỏa; reuse C5 #203 và `psremote-command` với goal remote execution riêng | U indeterminate; A có thể applicable dưới assumption; F blocked cùng conflict diagnostic, không advance; remote execution không tự thành admin | A2 so prerequisite decisions/success effects/digests; B resolution; A4 demo bộ ba |
| Q-CHECKPOINT: DA đạt, asset chưa đạt | U/V usable H0 và effective G-DA; giữ asset authorization/runtime gate false (F) hoặc missing (U), không thêm AdminTo từ membership | DA checkpoint đạt; final asset blocked/indeterminate; không claim final success hoặc impact đã chấm | A2 kiểm cả hai predicates và quyền provenance; B state/asset gate |
| Q-INPUT: thay đổi source/capability | Cùng public entry point; S đổi X→Y; I bỏ/đổi initial usable U; H giữ U nhưng chuyển H0→H1 không phù hợp; graph không đổi | Paths/status đổi theo input; không actor-switch bằng identity context sai; không mặc định host control cấp U | A2 chạy cùng entry point, đổi đúng một input, so trace; B mapping/CLI; chưa có executable handoff |
| Q-COVER: complete và truncated | N reuse `no-route` finite complete, không unresolved gates; P/E/S lần lượt cap paths/expansions/steps thấp trên ca nhiều đường; owners/context giữ nguyên | N no-path chỉ scope fixture; P/E/S partial với lý do tương ứng; không optimum/no-path từ partial | A2 oracle; A4 so `expansions`, `truncated`, `truncation_reason` với ranking coverage/caps và exclusions; B search |
| Q-SCORE: semantic khác scoring | Reuse positive query; lần một thiếu basis C/P/I, lần hai thiếu exact action binding; không thay facts | Semantic giữ nguyên; basis thiếu unrated; binding thiếu diagnostic/exclusion; không invent score hoặc suy no-path | A3 so work-unit/release/trace và adapter diagnostics; B consume |
| Q-REPLAY: gói tích hợp | Reuse Q-ASSET/Q-DA/Q-GATES/Q-COVER; cùng exact head/runtime/input/config/digest; private requirements thật đầy đủ | Hai lượt xác định, B tái lập; report/demo dùng output thật và limitations | A4 lưu commands/exit/output digests/diff ledger; B executable package; synthetic run ghi đúng nhãn |

Q-GATES là bộ ba bắt buộc trong demo: cùng query thiếu fact → indeterminate, assumption phù hợp → có thể đủ điều kiện, known-false → vẫn blocked dù assumption true.
Mỗi biến thể đổi một chiều dữ kiện để oracle không vô tình kiểm một lỗi khác; số điểm chỉ hiện khi basis tương ứng có thật.
Golden nền trong [attack scenarios](attack-scenarios.md) và `tests/fixtures/attack_scenarios/` được reuse, không sửa expected để chạy qua.
Source A Week 3 positive đã chạm 60.000 expansions theo handoff lịch sử; đó là evidence bounded, không bảo đảm Week 4 optimum hoặc lần chạy mới.

## E-ASREP: extension riêng, deferred

Reuse [evidence #200/#201](week4-prediction-evidence.md) và [proposal](week4-prediction-proposal.md): candidate V_A và asset C0 chỉ là alias của local bindings đã truy nguồn.
Expected chain là material để dò → recovered secret → usable V_A/H0 → effective DA checkpoint → quyền asset C0.
Không coi request được AS-REP/Kerberoast ciphertext hoặc `credential_material` legacy là recovered credential/usable identity.
Synthetic success-branch test được khai báo recovery succeeds để kiểm bước sau, gắn nhãn synthetic và không tự gán P=1.
SEAMLESS phải ghi recovery còn thiếu và final asset gate conditional/unknown; không claim observed final success.
Source X→V_A không có structural edge bắt buộc để trigger AS-REP; B cần owner/attribute hoặc capability trigger riêng nếu extension mở, không tạo fake edge.
Action names như `activate_identity` hoặc future roast/recover APIs giữ proposed tới accepted interface implementation.
Gate mở extension: scope/evidence/abstraction được nhận theo #192/#200, B tự nhận projection/trigger/state/search work, A có oracle/basis hoặc unrated, cross-review/checks đạt.
Kerberoasting dự phòng; RBCD chưa cam kết; core không chờ mentor hoặc extension implementation.

## Gói evidence bàn giao và giới hạn

Mỗi ca lưu local input manifest/digests, alias mapping, source/target/state/context/horizon, owner subset, caps, fact/assumption ledger và oracle độc lập.
Mỗi output cần paths/attempts, transition IDs/actors, structural edge hoặc derived-state origins, prerequisite decisions, checkpoint và asset goal, score/binding diagnostics cùng search/ranking coverage.
Pin exact code head, runtime, commands, exit codes, config/release/policy digests và hai output digests/diff khi chạy tái lập.
Public report chỉ dùng alias và evidence summaries; raw locators/private inputs không commit.
Official mechanism sources và limitations được reuse từ [#203 research](attack-semantics-predictive-state-transitions.md) và #201; A1 không bổ sung claim cơ chế mới hoặc coi research acceptance là code.
B review handoff/mapping/caps và task triển khai còn pending; A1 completion không thay A2/A3/A4 evidence.
CE validation deferred trong roadmap sau core, cần evidence riêng; không là gate query contract hoặc claim CE parity.
