# Phase A: so sánh cost ownership

Trạng thái: đề xuất để review cho [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), ngày 2026-09-28.
Tiếp nối [brief phương pháp](week3-scenario-cost-evidence.md) và [scenario contract](week3-scenario-contract.md).
Đối chiếu với develop `86261cb804b36ca6dfc7839576b68ae058a1e55f` và các fixture trong draft PR #132.
Đây là lập luận thiết kế, chưa phải accepted decision, scoring rubric, production profile hoặc successor ADR.
Không sửa parser/engine của B, Graph Contract v1.2.0 hoặc semantic catalog v0.2.

## Đề xuất chính

Đề xuất **cost thuộc hành động semantic đã xác định rõ, được đánh giá trong một scenario cố định**.
Trong ba phương án của #42, đây là **transition-plus-context có phạm vi giới hạn**, với transition là đơn vị sở hữu cost.
Context trước hết quyết định applicability; chỉ làm thay đổi cost khi có một phần công việc tăng/giảm được rubric và evidence giải thích.
Không mặc định dùng công thức “base cost cộng context penalty”.
Nếu trong phạm vi đã chọn context không làm thay đổi lượng cần đo, phương án này rút về transition cost cố định.
Đây là recommendation để review, không coi sự linh hoạt lớn hơn là bằng chứng nó luôn tốt hơn hoặc tự đủ điều kiện production.

Lý do chính là một relationship có thể hỗ trợ nhiều hành động với effect khác nhau, còn chuẩn bị dùng chung hoặc authentication context không thể được xử lý đúng chỉ bằng một số gắn với tên cạnh.
Tuy nhiên, ownership chỉ xác định cost thuộc cái gì; Phase B vẫn phải xác định cost đo cái gì và phép cộng có hợp lệ không.

## Định nghĩa ba phương án cho cùng phép so sánh

Giữ cùng snapshot, initial state, goal, action granularity và applicability model khi so sánh.
Cả ba phương án đều có thể và phải dùng gating; không đánh đồng relationship cost với việc bỏ kiểm tra semantics.

| Phương án | Định nghĩa dùng trong tài liệu | Điều nó chưa tự giải quyết |
| --- | --- | --- |
| M1: relationship | Một giá trị cho relationship kind hoặc cho từng structural edge instance | Chọn technique, effect và phần việc nào được tính |
| M2: transition | Một giá trị cho hành động đã xác định technique, actor/target binding và ranh giới công việc, trong phạm vi công bố | Khi cùng hành động có phần việc khác nhau giữa các context |
| M3: transition-plus-context | Cost của hành động được xác định theo context có scope/evidence rõ | Context nào là gating, cost driver hay chuẩn bị dùng chung; nguy cơ quá nhiều tham số |

`GenericAll` cùng kind nhưng khác User/Group là phản ví dụ cho kind-only rating, chưa đủ để bác bỏ rating theo từng edge instance.
Ngay trên một edge GenericAll tới User, [catalog](../../configs/attack_semantics.yml) có thể cho xét reset password hoặc cấp WriteDacl, với effect khác nhau.
Một số của edge instance chỉ đại diện được các lựa chọn đó nếu có quy tắc gộp/đồng nhất cost được chứng minh phù hợp với construct và goal.
Chọn min cost của các technique có thể dùng làm thông tin giới hạn dưới trong một mô hình đã chứng minh điều kiện, nhưng không tự là cost của mọi hành động trên edge đó.

**Nơi lưu số không phải cost ownership.**
Transition cost vẫn có thể được lưu thành edge weight trong search graph đã mở rộng, hoặc dưới dạng bảng profile tra cứu theo action.
Điều đó không biến nó thành cost của structural relationship.
Ngược lại, Graph Contract đang có edge-kind weight không phải lý do đủ để chọn M1.

## Bằng chứng và counterexample

| Câu hỏi | Bằng chứng trong phiên nghiên cứu | Hệ quả được phép rút ra |
| --- | --- | --- |
| Có được coi quyền là hành động cuối cùng không? | Catalog phân biệt các technique/effect; scenario tách reset, identity và operation | Cost cần chỉ rõ hành động/effect được trả tiền |
| Membership có nên tăng cost theo mỗi tầng không? | Fixture direct/nested cùng cost 4 khi closure thụ động cost 0 | Không cộng phí hành động chỉ vì có thêm structural hop trong abstraction này |
| Có thể cộng chi phí hai nhánh AND độc lập không? | Fixture chuẩn bị chung: `3 + 2 + 2 + 1 = 8`, thay vì `5 + 5 + 1 = 11` | Cần tính phần chuẩn bị một lần khi cùng kết quả được tái sử dụng |
| Context thiếu có thể đổi thành penalty không? | 27 tổ hợp gate trong scenario; chỉ true cho phép transition tương ứng | Unknown applicability không được biến thành một action đắt hơn |
| Ít action hơn có luôn khách quan không? | Split/packed đạt cùng goal S2 với cost 3, nhưng action count là 2 và 1 | Phải cố định action granularity trước so sánh baseline |
| Weighted có chắc đổi ranking trên raw không? | Các ứng viên raw hiện chưa chứng minh ranking reversal | Không tạo score khác nhau chỉ để ép weighted thắng baseline |

Các integer cost đều là fixture tự chọn để kiểm tra phép cộng; không phải measurement AD hoặc numeric production rating.
Các counterexample giới hạn những phép suy luận không hợp lệ, không tự chứng minh một implementation architecture duy nhất.
Ví dụ AND chưa buộc production phải dùng full state-space planner; phải xét scenario thực sự cần hỗ trợ.

## So sánh theo năm yêu cầu của Phase A

Không gán điểm tổng hoặc trọng số cho bảng này vì chưa có cơ sở coi năm yêu cầu là các thang số có thể cộng.

| Yêu cầu | M1: relationship | M2: transition | M3: transition-plus-context giới hạn |
| --- | --- | --- | --- |
| Semantic correctness | Cần quy tắc nối số của relationship tới từng technique/effect; dễ mất khác biệt nếu một số dùng cho tất cả | Nối cost trực tiếp với hành động/effect và binding đã định nghĩa | Như M2, đồng thời công bố context mà rating áp dụng |
| Additivity | Tổng structural edge cost không tự giải thích closure, bridge hoặc chuẩn bị chung | Có thể định nghĩa incremental work; vẫn phải chống đếm đôi giữa action | Có thể tách chuẩn bị chung thành action một lần; context adjustments phải kiểm tra overlap |
| Auditability | Bảng ít dòng dễ đọc, nhưng rationale mơ hồ nếu chưa chọn technique | Có thể truy cost về technique, phạm vi công việc và evidence | Cần thêm context/assumption provenance; reviewer phải biết phần nào observed, phần nào giả định |
| Reproducibility | Tái lập phép tính đơn giản; chưa đủ để tái lập ý nghĩa rating | Cần cố định granularity, binding, rubric và profile | Cần cố định thêm scenario/context version; thiếu scope sẽ gây lệch kết quả giữa người chạy |
| Search compatibility | Thuận tiện trên structural graph nhưng không tự bảo đảm đường khả thi | Có thể dùng action/capability graph hoặc state graph tùy dependencies | Có thể đóng băng context trước search; chuẩn bị dùng chung đòi biểu diễn trạng thái phù hợp |

M1 vẫn hữu ích cho baseline cấu trúc hoặc phạm vi có đúng một phép diễn giải cost hợp lệ cho mỗi edge.
M2 là lựa chọn đủ đơn giản nếu một scenario hẹp giữ lượng công việc của từng action ổn định.
M3 được đề xuất vì cần công bố rõ giới hạn đó và xử lý ngoại lệ có bằng chứng, không phải để thêm score cho mọi thuộc tính môi trường.

## Quy tắc phân loại context

| Loại thông tin | Câu hỏi phân loại | Cách xử lý đề xuất |
| --- | --- | --- |
| Applicability predicate | Nó quyết định action hiện tại có được thực hiện không? | Gate trước cost; false/unknown không được traverse |
| Cost modifier có bằng chứng | Action vẫn applicable, nhưng lượng cần đo của chính action thay đổi? | Chỉ dùng rating/variant theo context khi rubric chỉ rõ đơn vị, phạm vi và evidence |
| Chuẩn bị có effect tái sử dụng | Phải làm thêm một việc tạo capability cho nhiều action? | Mô hình hóa công việc/effect riêng và trả cost khi thực hiện, không cộng lại trên từng consumer |
| Initial capability | Công việc đó đã được giả định hoàn thành trước điểm bắt đầu? | Ngoài cost path hiện tại; công bố biên đo thay vì tính lại |
| Khác biệt ngoài phạm vi | Time expiry, mất quyền, tài nguyên bị tiêu hao hoặc retry cần semantics chưa hỗ trợ? | Ghi unsupported cho mô hình hiện tại; không lấp bằng context penalty |

Ví dụ, service không sẵn sàng làm action dùng service đó không applicable trong scenario hiện tại.
Không được biến “service unavailable” thành cộng 5 để search vẫn đi qua.
Nếu có một hành động khác làm service khả dụng thì hành động đó cần quyền, prerequisites và effect riêng; không tự sinh nó chỉ vì muốn đường đi tồn tại.

Một yếu tố có thể ảnh hưởng nhiều lớp trong thực tế, nhưng mỗi ảnh hưởng phải có semantics riêng.
Không vừa tính toàn bộ preparation trong base rating vừa cộng lại cùng preparation ở context adjustment.
Detectability không trở thành core dimension chỉ vì nó phụ thuộc context.
Reliability/success probability cũng không trở thành independent cost chỉ vì action có nhiều prerequisite.
Các candidate criterion vẫn phải qua admissibility test và overlap review của #42.

## Hai loại thiếu thông tin cần phân biệt

| Trạng thái | Feasibility | Weighted ranking |
| --- | --- | --- |
| Applicability false | Transition bị chặn trong scenario | Không gán cost để đi vòng qua điều kiện |
| Applicability unknown | Chưa đủ điều kiện cho traverse theo evidence-only policy | Không đổi unknown thành penalty hoặc probability |
| Applicability true nhưng cost chưa được rating | Vẫn có thể ghi nhận hành động/đường khả thi theo mô hình | Chưa khẳng định minimum toàn cục nếu thiếu rating và không có chứng minh bằng bound phù hợp |
| Applicability true và cost hợp lệ | Có thể tham gia search theo semantics đã chọn | So sánh trong phạm vi profile/scenario đã công bố |

Không đồng nhất `unrated` với `unreachable`.
Nếu chỉ tìm trên phần được rating, phải ghi “tối ưu trong tập đã được rating”.
Chỉ mở rộng thành kết luận toàn cục khi đã xét đủ phần cạnh tranh, chẳng hạn bằng chứng minh lower bound ở dưới.
Có thể tiếp tục baseline đếm action khi chưa rating, nhưng baseline không được đổi tên thành production weighted result.
Đây là policy đề xuất, chưa thêm trạng thái hoặc sửa return type trong engine.

## Phép cộng và tương thích search

Với scenario cố định, một plan hợp lệ gồm các action được áp dụng theo thứ tự trên state tương ứng.
Candidate additive model chỉ cộng **incremental cost của phần việc thực sự xảy ra trong plan**.
Prerequisite đã đúng ở initial state không tự phát sinh thêm cost; prerequisite cần được tạo ra thì cost nằm ở action tạo nó.
Giữ mọi cost đưa vào Dijkstra hữu hạn, không âm theo invariant của #42.
Định nghĩa state phải đủ để biết khả năng nào đã có và phần chuẩn bị nào có thể được dùng lại.

Tính không âm chưa đủ để biện minh cho phép cộng một rubric.
Nếu các mức chỉ có ý nghĩa thứ tự, không được mặc định khoảng cách giữa các mức bằng nhau hoặc tổng số đo đúng lượng công việc.
Phase B phải đưa rationale cho đơn vị/scale và aggregation; ownership review không thay việc đó.
Với một construct không cộng được hoặc trade-off chưa được định nghĩa, chưa đưa scalar profile vào weighted shortest-path.

Research projection hiện có chỉ nhận một số dạng dependency và trả unsupported khi vượt phạm vi.
Không đề xuất sửa production engine để nhận mọi context động trong PR này.
Nếu một scenario có thể compile thành graph đơn giản mà bảo toàn applicability, goal và cost thì dùng graph đó vẫn phù hợp với transition ownership.

## Phản ví dụ kiểm tra thang điểm và cost còn thiếu

### Thứ tự khó dễ chưa xác định được tổng cost

Fixture có đường A gồm một action mức khó, đường B gồm hai action mức vừa.
Với nhãn `vừa=2, khó=3`, tổng A là 3 và tổng B là 4, nên search chọn A.
Đổi nhãn thành `vừa=2, khó=5` vẫn giữ thứ tự dễ < vừa < khó, nhưng tổng A là 5 và tổng B là 4, nên search chọn B.

Đây là hai cách biểu diễn cùng thông tin thứ tự mà cho hai lựa chọn khác nhau.
Vì vậy chỉ biết thứ tự khó dễ chưa đủ để biện minh cho tổng điểm path.
Không kết luận mọi rating chuyên gia đều vô dụng; rubric cần thêm rationale cho khoảng cách giữa mức, đơn vị cộng và đánh đổi, rồi kiểm tra sensitivity.
Thí nghiệm dùng `replace()` đổi cost trong cùng action set, sau đó gọi lại `solve()`; goal, prerequisites và effects giữ nguyên.

### Unrated có thể ảnh hưởng hoặc không ảnh hưởng lời giải tối ưu

Một đường đã rating có cost 5.
Một đường cạnh tranh có phần đã biết cost 1 và phần chưa biết cost x không âm.
Nếu x bằng 1 thì đường cạnh tranh có cost 2; nếu x bằng 10 thì cost 11.
Cùng dữ liệu đã rating nhưng hai completion hợp lệ cho kết luận khác nhau, nên kết quả 5 chưa được chứng minh là minimum toàn cục.
Hai giá trị completion chỉ là giả lập để kiểm tra lập luận, không điền vào profile thật.

Tuy nhiên, nếu phần đã biết của đường cạnh tranh là 7, tổng `7 + x >= 7` với mọi x không âm.
Khi đó đường có cost 5 vẫn tối ưu trong mô hình hai đường này, dù chưa rating x.
Đây là refinement của câu “còn unrated thì chưa thể biết optimum”: cần xét liệu đã có bound đủ mạnh hay chưa.

Trong một mô hình đã cố định feasibility, goal và action semantics, có thể kiểm tra theo nguyên tắc:

1. Lấy cost U của một plan khả thi đã được rating đầy đủ làm upper bound cho optimum.
2. Dùng lower bound hợp lệ cho mọi cost còn thiếu và tìm optimum L của mô hình optimistic đầy đủ.
3. Vì `L <= optimum <= U`, nếu chứng minh được `L = U` thì plan đã rating là tối ưu trong mô hình đó; vẫn có thể có plan đồng hạng.

Số 0 chỉ là lower bound nếu invariant không âm thực sự áp dụng; không phải rating hay bằng chứng rằng action miễn phí.
Nếu L nhỏ hơn U thì kiểm tra này chưa đủ kết luận, không chứng minh plan đã rating sai.
Phải bao gồm mọi action/đường cạnh tranh thuộc mô hình đang claim và giải đúng bài toán optimistic; bỏ phần unsupported hoặc thay feasibility sẽ làm mất bảo đảm.
Fixture chỉ dùng integer exact; chưa có policy sai số floating-point hoặc chứng minh coverage cho production.
Unknown applicability vẫn bị xử lý theo gating policy, không tự được chuyển thành applicable để lấy bound.
Không triển khai bounds engine trong PR này; test chỉ kiểm tra ví dụ hữu hạn cùng bất đẳng thức đã tính tay.

## Brief implementation và cách tự kiểm tra

Phần so sánh này được lập thủ công từ catalog, issue constraints và counterexample đã chạy; không có hàm tự chấm điểm ba architecture.
Phần kiểm tra số học dùng các hàm có sẵn: `solve()` tìm min cost trên fact state, `exhaustive_cost()` duyệt fixture nhỏ, và test split/packed đối chiếu cùng goal.
Không thêm tests chỉ để xác nhận các ô đánh giá do chính tài liệu đề xuất.

```bash
python scripts/research/semantics_probe.py
python -m unittest discover -s tests -p test_research_probes.py -v
```

Probe có 15 fixture gốc; checkpoint Phase A có 15 test, gồm 27 tổ hợp gate của scenario và ba counterexample về thang điểm/cost còn thiếu.
Sau xử lý review, tổng là 20 test với năm test bổ sung cho raw discovery/CLI và enabled-fact reporting.
Kết quả kiểm chứng logic của fixture, không đo độ khó thực tế, hiệu năng production hoặc sự đồng thuận của reviewer.
Người review có thể phản biện bằng cách đổi goal, giả định, phân rã action hoặc quyền được tái sử dụng, rồi kiểm tra kết luận nào còn giữ được.

Khi được accepted, implementation cần handoff riêng với ít nhất: action identity/binding, work boundary, scenario/profile version, nguồn rating, unknown policy và giải thích cost breakdown.
Chưa chọn format JSON/YAML hoặc sửa contract lưu trữ trong Phase A; version/migration phải được review cùng thay đổi thực tế.

## Nội dung cần reviewer quyết định

1. Có chấp nhận transition là đơn vị sở hữu cost, còn structural relationship là evidence/capability hỗ trợ hành động không?
2. Có chấp nhận phạm vi M3 giới hạn: scenario cố định, context chủ yếu là gating, modifier chỉ khi chứng minh được phần cost riêng không?
3. Có chấp nhận các invariants về closure, chuẩn bị dùng chung, action granularity và phân biệt unrated với unreachable không?
4. Sau khi các điểm trên accepted, Phase B sẽ chọn construct/criterion tối thiểu, kiểm tra scale và overlap trước rating.

Chưa đóng Phase A vì recommendation này chưa được review chấp thuận.
Không tạo successor ADR hoặc numeric production profile trong PR này.

## Bàn giao Phase A để review

| Hạng mục | Bằng chứng đã có | Còn cần quyết định |
| --- | --- | --- |
| Phạm vi scenario và goal | Scenario contract, handoff và 27 tổ hợp gate | Chấp nhận initial assumptions và goal S2 hay yêu cầu goal khác |
| Ba phương án ownership | Định nghĩa M1/M2/M3 và bảng năm yêu cầu | Chấp nhận hoặc sửa recommendation M3 giới hạn |
| Additivity và granularity | Shared preparation, free closure, split/packed, ordinal counterexample | Chốt biên hành động và yêu cầu thang đo cho Phase B |
| Unknown policy | Applicability, unrated, rated-subset optimum và bound refinement | Chấp nhận cách báo cáo thiếu rating và phạm vi bảo đảm |
| Khả năng tái lập | Hai probe, 20 test research và hướng dẫn chạy | Review logic/assumptions độc lập; CI không thay acceptance |

Bộ bằng chứng Phase A đã được đóng gói và merge vào `develop` qua PR #132; không cần thêm probe chỉ để tăng số lượng test.
Acceptance của evidence artifact và acceptance của quyết định cost ownership là hai việc riêng biệt.
Merge tài liệu nghiên cứu không tự biến mọi recommendation thành normative decision.
Sau khi reviewer xác nhận rõ scenario contract (#140), tiến hành lập bản nháp mô hình và rubric rút gọn (#141), kiểm chứng và hiệu chỉnh mô hình qua worked example (#142), trước khi review chính thức và chốt successor ADR theo quy trình #42 tại #143.

## Tiếp tục ở session khác và phân rã các issue kế tiếp

Checkpoint hiện hành ngày 2026-09-30 thay thế cho lịch trình ngày 29/9 bên dưới.
Các artifacts nghiên cứu của #140, #141, #142 và #150 đã hoàn tất và được merge qua các PR #144, #147, #149 và #151.
Đề xuất Pareto bảo thủ có phạm vi hẹp đã được maintainer phê duyệt làm cơ sở phân tích nghiên cứu, tuy nhiên kết luận cho bài toán dự báo trên SEAMLESS vẫn là Insufficient Evidence.
Sau PR #151, issue #143 kế thừa cơ sở nghiên cứu này để xem xét ban hành successor ADR (ADR-0013) và giao diện bàn giao cho TTS B.
Không tự ý biến các PR nghiên cứu đã merge hay trạng thái CI vượt qua kiểm thử thành mô hình sản phẩm hoặc bộ tham số trọng số chính thức cho engine tìm đường.

Repo và review history là nguồn bàn giao, không cần có lịch sử chat để tái lập phần nghiên cứu này.
Trước khi bắt đầu, đọc lại trạng thái mới nhất của [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), [PR #132](https://github.com/nairyuuu/ad-weighted-graph/pull/132), [#140](https://github.com/nairyuuu/ad-weighted-graph/issues/140), và feedback mentor ngày 2026-09-29.
PR #132 đã merge vào `develop`; bắt đầu từ `develop` mới nhất và kiểm tra nội dung có amendment nào tiếp nối không.
Không tự coi trạng thái CI xanh hay việc merge PR nghiên cứu là acceptance của thiết kế mô hình chính thức.

Thứ tự đọc tối thiểu:

1. [Weighting direction](weighting-direction.md) và body hiện hành của #42, #140: mục tiêu, mentor constraints ngày 29/9, thứ tự các issue M2-A.
2. [Brief E2E](week3-scenario-cost-evidence.md): đã làm gì, dùng hàm nào, bằng chứng raw và giới hạn.
3. [Scenario contract](week3-scenario-contract.md): initial state, foothold boundary, target candidate, 4 tầng dữ kiện và hai chế độ evidence-only vs scenario mode.
4. Tài liệu comparison này: recommendation, counterexamples và những quyết định cần reviewer xác nhận.
5. [Catalog](../../configs/attack_semantics.yml), [attack semantics](attack-semantics.md), hai script trong `scripts/research/` và [tests](../../tests/test_research_probes.py) khi cần kiểm tra implementation.
6. Worklog [26/9](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-09-26-ttsA.md), [27/9](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-09-27-ttsA.md), [28/9](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-09-28-ttsA.md), [29/9](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-09-29-ttsA.md) và review history để phân biệt kết quả từng checkpoint.

Tại checkpoint bàn giao ngày 2026-09-29, Phase A đã hoàn thành triển khai tài liệu và artifacts kịch bản qua issue #140, đang chờ review và nghiệm thu.
Lộ trình tiếp nối được phân chia thành các issue cụ thể:

| Giai đoạn tiếp nối | Issue và Phụ trách | Điều kiện bắt đầu | Đầu ra cần hoàn thành |
| --- | --- | --- | --- |
| 1. Scope & Scenario | [#140](https://github.com/nairyuuu/ad-weighted-graph/issues/140) (TTS A, Reviewer: TTS B) | Feedback mentor ngày 2026-09-29 | Hợp đồng kịch bản chuẩn hóa, nhận diện target candidate, phân tầng 4 nhóm dữ kiện, và định hướng prediction |
| 2. Mô hình & Rubric | [#141](https://github.com/nairyuuu/ad-weighted-graph/issues/141) (TTS A, Reviewer: TTS B) | Scenario contract ở #140 được review và accepted | Thiết kế bản nháp rubric rút gọn, định nghĩa construct khả năng thành công và tác động đích, ma trận độc lập và chống đếm trùng |
| 3. Kiểm chứng & Sensitivity | [#142](https://github.com/nairyuuu/ad-weighted-graph/issues/142) (TTS A, Reviewer: TTS B) | Bản nháp mô hình và rubric từ #141 sẵn sàng thử nghiệm | Worked example trên candidate SEAMLESS, kiểm tra độ nhạy và tính ổn định thứ hạng để phản hồi, hiệu chỉnh mô hình trước khi nghiệm thu |
| 4. Successor ADR & Handoff | [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143) (TTS A, Reviewer: TTS B) | Mô hình và kiểm chứng ở #141-#142 được review và chấp thuận | Successor ADR thay thế ADR-0001, bộ tham số tái lập được, và đặc tả giao diện bàn giao cho B ở M3 |

Những điều không được đánh mất khi chuyển session:

- TTS A phụ trách weighting/research; không tự lấy parser/engine và performance work của B.
- Recommendation hiện tại là transition-owned cost trong scenario cố định, context gating trước cost; chưa có numeric production weights.
- Số trong fixture là giả lập; raw structural paths chưa chứng minh executable chains; runtime assumptions phải được gắn nhãn minh bạch.
- `unit` giữ vai trò regression baseline của repo; action-count baseline trong probe không thay profile này.
- `maut_v1` là historical/experimental; telemetry độc lập không hiệu chỉnh xác suất thành công hoặc detectability của SEAMLESS.
- Chưa chọn rubric, chưa tạo successor ADR và chưa triển khai actor handoff hoặc bounds engine vào production trong task này.

Lệnh tái lập nằm trong brief E2E; raw probe có `--discover` nên không cần mang SID/tên máy từ chat sang session mới.
Raw input phải được lấy đúng nguồn/manifest và giữ ở vùng ignored; output có identity cũng không commit.
Mỗi session mới tiếp tục dùng branch/PR, worklog theo ngày thực tế, kiểm tra và review theo CONTRIBUTING.
