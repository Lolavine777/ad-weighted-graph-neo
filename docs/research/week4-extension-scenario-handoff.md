# Bộ ca và ranh giới tích hợp extension từ field AD

Ngày 07/10/2026, Asia/Ho_Chi_Minh. Owner TTS A; reviewer TTS B. Refs [#200](https://github.com/nairyuuu/ad-weighted-graph/issues/200), [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192).

**B đã nhận kết quả sàng lọc/raw verification ở [PR #217](https://github.com/nairyuuu/ad-weighted-graph/pull/217), approve đúng `989b09d` và merge vào `develop@4c1f80511fb9ec81606622fafda563bdab4bc8ad`.** Approval giới hạn ở nghiên cứu/bằng chứng. Tài liệu này cung cấp ca và oracle đề xuất cho bước tiếp theo; chưa là API, production semantics, numeric ratings hoặc nghiệm thu extension.

## 1. Phạm vi đưa vào review

- **AS-REP → danh tính dùng được → tài sản C0:** ứng viên đầu cho việc kiểm mở đường từ source chưa có credential/control AD dùng được. Source vẫn biết hoặc đoán được identity đích; khả năng kết nối KDC được khai báo riêng.
- **RBCD → delegated service context → tài sản C_R:** ca thứ hai có gate, để kiểm hành động tạo quan hệ mới từ ACL. Quyền cuối của P trên C_R chưa có bằng chứng trong snapshot; positive bên dưới là synthetic success branch.
- **Kerberoasting:** giữ ca đối chứng và các kỳ vọng phục vụ [#216](https://github.com/nairyuuu/ad-weighted-graph/issues/216) đã do B tự nhận. Không yêu cầu đổi thứ tự hoặc dừng task này. Ca SEAMLESS đã chọn chưa chứng minh tăng asset coverage so với reset baseline.

AS-REP/RBCD là hai chuỗi nghiên cứu được đề xuất, chưa cam kết triển khai cả hai. B chọn lát triển khai và abstraction theo [#174](https://github.com/nairyuuu/ad-weighted-graph/issues/174), #215/#216; core [#204](https://github.com/nairyuuu/ad-weighted-graph/issues/204) tiếp tục độc lập. DCOM/GPO/owner/DCSync giữ disposition của [bảng 40 dòng](week4-field-driven-screening.md), relay/AD CS cần thêm đầu vào.

## 2. Input, bằng chứng và output phải giữ riêng

Đối chiếu code tại merge pin trên: contract 1.3.0/catalog 0.3. Reuse [query contract](week4-query-contract.md), [state research](attack-semantics-predictive-state-transitions.md), [raw verification](week4-screening-raw-verification.md) và [oracle core](week4-scenarios.md). Chưa chạy generator cho các extension này.

| Layer | Input/binding cụ thể | Điều không được suy |
| --- | --- | --- |
| Graph và snapshot facts | Snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; raw/graph/code digests riêng; alias resolve canonical ID ở boundary | SPN/pre-auth là static facts, không thêm HasSPN edge hoặc chuyển sang runtime để làm đường chạy |
| Source/initial state | Computer X là vị trí/khả năng thực hiện thao tác được scenario khai báo; initial usable AD identity và secret/control khai báo riêng | Host control X không tự cấp usable domain identity; X không cần có structural edge tới V_A để xét AS-REP |
| Knowledge | Identity V_A known/guessable; realm/KDC và M/P/service được resolve theo từng ca | Không có AD credential/control khác với không biết account; account discovery không tự là account control |
| Runtime/assumptions | Predicate/value, subject/target, context/service, horizon/budget, declarer/source, rationale và provenance theo contract hiện có | Missing không tự true; known-false cùng scope veto assumption true; counterfactual là view riêng có nhãn |
| Branch effects | Material, secret, scoped identity, descriptor mới và execution capability chỉ apply sau bước applicable | Derived state không mutate graph/raw; ciphertext không là secret; service context không là identity toàn miền |
| Result | Trace từng gate/effect, rejected assumptions, checkpoint, asset goal, coverage/caps và scoring disposition | Chạm node/DA không là asset success; unknown/unrated không là no-path; truncated không là complete/optimal |

[#215](https://github.com/nairyuuu/ad-weighted-graph/issues/215) đang đề xuất read-only snapshot fact view, lookup theo canonical ID và reconciliation/provenance. A không sửa GraphNode/topology hoặc invent fact API. [#211](https://github.com/nairyuuu/ad-weighted-graph/issues/211) giữ materialization/fact-resolution; nguồn Computer không yêu cầu admin privilege nếu thao tác không cần, nhưng scope khả năng thực hiện và network vẫn phải rõ.

### Alias và locators SEAMLESS

Các số record dưới đây là locators đã ẩn danh, không là production IDs. Full names/SIDs/DNs/SPNs và private input mappings giữ local, không commit.

| Alias | Bằng chứng đã verify | Gate chưa được raw xác nhận |
| --- | --- | --- |
| V_A / G-DA / C0 | User1700 enabled, pre-auth off; `groups/40/Members/2`; canonical derived AdminTo V_A→Computer0/DC có provenance Members[]/LocalAdmins[] | Known target theo scenario; KDC response/policy, recovery trong budget, secret validity/activation, endpoint/token/admin execution |
| U_R / M / C_R | User1580; GenericAll→User2075 tại `users/2075/Aces/4`, M enabled/SPN; GenericAll→Computer27 tại `computers/27/Aces/5`; AllowedToAct hiện rỗng | Exercise reset/write right, known usable key của M, descriptor write, KDC/delegation policy, P authorization và service execution |
| P | User917 chỉ là candidate identity để nghiên cứu; sensitive=false không là complete policy check | Protected/delegation restrictions, quyền P trên C_R, target-service acceptance; không có final AdminTo P→C_R evidence |
| V_K / V_D / C0 | User11 SPN; membership tới Group30; GenericAll Group30→User917 tại `users/917/Aces/8`; V_D→DA tại `groups/40/Members/3` | Request/recovery/auth/reset/host gates; 2.490 enabled Users cũng tới Group30, không suy token hoặc runtime success |

“Ngoài bộ lọc DA/EA/Administrators/DC/RODC/EnterpriseDC” chỉ mô tả role filter đã kiểm, không chứng minh ít đặc quyền tuyệt đối. Membership closure không thay Windows access check.

## 3. Chuỗi AS-REP và oracle độc lập

[MITRE T1558.004](https://attack.mitre.org/techniques/T1558/004/) hỗ trợ cơ chế lấy AS-REP material ở account không yêu cầu pre-auth rồi thử offline recovery. Nó không cung cấp recovery likelihood cho dataset. Bốn bước chủ động và closure dưới đây là nhãn semantic để review, không là owner IDs/API mới.

| Nhãn | Prerequisites/gates | Success effect | Blocked/unknown phải giữ |
| --- | --- | --- | --- |
| A1 request | V_A known/guessable, pre-auth off theo snapshot; query có khả năng gửi request; KDC/network/request-policy cho phép | Material AS-REP gắn V_A/acquisition context | Pre-auth required hoặc KDC deny: blocked; required fact missing: indeterminate; không apply material |
| A2 recovery | Material đúng V_A; recovery outcome trong declared method/budget/horizon được resolve | Secret dùng được cho một authentication attempt, có form/provenance | Recovery false trong scope này: blocked; unknown: indeterminate; không có usable V_A |
| A3 activation | Secret hoặc existing valid capability của V_A; account/policy/validity và authentication acceptance trong H0 | Usable V_A/H0 | Secret không hợp lệ hoặc auth deny: blocked; missing required gate: indeterminate; không dùng reset qualifier cho roast secret |
| A4 entitlement | Usable V_A đúng H0; effective membership G-DA và scope đã resolve | DA checkpoint cho identity/context này | Static DA membership khi chưa usable không đạt checkpoint; closure thụ động không là crack/auth event mới |
| A5 asset action | Identity/context phù hợp, quyền asset có provenance; network/service/auth/endpoint/token gates chứng minh admin execution C0 | `admin_control(C0)` là goal fixture | Asset gate false/unknown không apply admin effect, dù DA checkpoint đã đạt |

### Fixture logic nhỏ để freeze expectation trước implementation

Synthetic fixture có đúng X, V_A, G-DA và C0; chỉ cho phép A1–A5, không có reset/alternate acquisition path. Initial state có khả năng thao tác từ X và biết V_A, **không có AD secret/control/usable identity**. A-P khai báo tất cả required gates/outcomes đúng scope là true, gồm recovery success; đây không là fact SEAMLESS hoặc P=1.

Oracle xét **programs tối thiểu đủ tới goal**: mỗi action tối đa một lần, không lặp khi output đã có, dừng khi first-hit goal. A4 là closure thụ động. Với initial state rỗng về AD, duy nhất program `A1,A2,A3,A4,A5`; đúng sáu projected states là initial, material, secret, usable V_A/H0, DA checkpoint, admin C0, mỗi state giữ các effects của tiền tố. Lý do đủ: mỗi bước chỉ tạo prerequisite cho bước kế tiếp, không có rule/edge/capability khác trong fixture. Đây là oracle logic của A; generator hiện hành chưa được chứng minh có cùng transition vocabulary/scope.

Với false/missing ở bước Aj, chỉ các success prefixes trước Aj được giữ; attempted Aj có blocked/indeterminate diagnostic, không apply effect hoặc bước hậu tố phụ thuộc nó. Với A5 false/missing, checkpoint vẫn reached. Unknown không được đổi thành kết luận no-path ngoài scope. Nếu nhiều gates cùng missing/false, resolver phải giữ đầy đủ diagnostic và known-false veto; các ca đơn-gate bên dưới cô lập lỗi.

| Case | Delta so với A-P, mọi gate khác giữ nguyên | Expected oracle |
| --- | --- | --- |
| A-P | Synthetic positive | Program A1–A5; DA reached, asset reached dưới declared outcomes; score vẫn unrated |
| A-PRE-F / A-PRE-U | Separate counterfactual pre-auth required / required pre-auth fact missing | A1 blocked / indeterminate; không material/secret/usable; raw SEAMLESS không bị sửa |
| A-KDC-F / A-KDC-U | KDC request gate false / missing | A1 blocked / indeterminate; không success effect |
| A-REC-F / A-REC-U | Recovery outcome false trong budget/horizon / unknown | Giữ material sau A1; A2 blocked / indeterminate; không secret/usable/DA/asset |
| A-AUTH-F / A-AUTH-U | Activation gate deny / missing | Giữ material+secret; A3 blocked / indeterminate; không usable/DA/asset |
| A-ASSET-F / A-ASSET-U | Required asset admin-execution gate false / missing | Giữ usable V_A/H0 và DA; A5 blocked / indeterminate; không admin C0 |
| A-SECRET | Initial state có valid V_A secret và form/provenance, chưa usable | Program tối thiểu A3,A4,A5; không request/recovery hoặc charge recovery lại |
| A-IDENTITY | Initial state có usable V_A/H0; closure chưa materialized | Program tối thiểu A4,A5; không charge acquisition/activation lại |
| A-CONTEXT | Chỉ có usable V_A/H1; H1 không phù hợp H0; không có secret/renewal bridge trong fixture | Không dùng identity H1 làm H0; không DA-in-H0/admin C0 qua capability này; giữ scope diagnostic |
| A-VETO | A-KDC-F cộng declared assumption KDC=true cùng scope | Vẫn blocked; assumption bị reject/audit, không biến authoritative false thành true |
| A-EXT-OFF | Cùng A-P inputs, baseline owner scope chưa có A1–A3 | Baseline không tới usable V_A trong closed fixture; extension có program A-P; không gọi đây là measured SEAMLESS coverage |

A-CONTEXT cố ý không giữ A-P acquisition branch: initial capability khác và owner scope chỉ A4/A5 để cô lập identity reuse. Nếu chạy full scope A1–A5, AS-REP có thể là nhánh acquisition mới; không kết luận toàn query blocked chỉ từ việc H1 không dùng được.

Trên SEAMLESS thật, A-RAW giữ các snapshot facts và known target khai báo, nhưng chưa resolve KDC/recovery/auth/asset runtime: báo required gates indeterminate theo bước đã xét, không claim observed final path. A-ASSUMED dùng cùng snapshot và assumptions có metadata cho từng missing gate để kiểm scenario branch; cho kết quả conditional dưới assumptions, không đổi raw provenance hoặc tự sinh số C/P/I.

## 4. RBCD: creation, acquisition và service scope

[AddAllowedToAct](https://bloodhound.specterops.io/resources/edges/add-allowed-to-act) phân biệt khả năng ghi descriptor với quan hệ đã tồn tại. [AllowedToAct](https://bloodhound.specterops.io/resources/edges/allowed-to-act) yêu cầu controlled SPN principal và có delegation restrictions; [nghiên cứu gốc](https://eladshamir.com/2019/01/28/Wagging-the-Dog.html) phân biệt service ticket và quyền trên dịch vụ đích. Snapshot cung cấp candidate ACL; còn phải resolve effective access/runtime theo scope.

| Nhãn | Prerequisites/gates | Success effect | Ranh giới |
| --- | --- | --- | --- |
| R1 acquire M by reset | Initial usable U_R/H_R có capability exercise GenericAll→M theo accepted reset owner; directory/password-write gates thỏa | Known reset secret/control M với reset provenance | M chưa controlled chỉ vì có ACL; disabled account không tự blanket-veto thao tác reset |
| R2 prepare service capability | M SPN fact; secret/key form phù hợp, validity, derivation/auth/KDC gates thực sự cần đã resolve | Controlled service authentication capability/key M để dùng delegation | B quyết định cần activation/artifact gì; không bắt buộc usable M toàn cục hoặc tạo máy mới; không suy key từ SPN |
| R3 configure descriptor | U_R/H_R có exact effective write right trên C_R; directory write accepted; identity M known | Branch-local descriptor cho M delegate tới C_R | R3 có thể trước R1/R2; không mutate AllowedToAct rỗng trong snapshot hoặc gọi relation mới là observed |
| R4 delegate P | R2+R3, service/SPN/target binding đúng; KDC/S4U và P delegation policy cho phép | Delegated service context P/C_R/service/H_S | Không tạo global usable P hoặc DA checkpoint của P ở context khác |
| R5 asset action | R4 context phù hợp; P được target-service authorization và effective admin-execution gates | `admin_control(C_R)` nếu privilege thật sự được chứng minh | Ticket/remote command không tự admin; P authorization missing giữ unknown |

R1 reuse reset bridge khi đúng form/provenance; R2 không dùng recovered roast secret làm `reset_password_control`. R2 là capability boundary đề xuất, có thể gồm nhiều hoặc không có network action theo architecture B; số semantic labels không là số work units hay số probability factors.

### Fixture logic và thứ tự độc lập

Synthetic fixture chỉ có source Computer X, U_R, M, P, C_R và các rules R1–R5. Khả năng thao tác từ X và initial usable U_R/H_R được khai báo riêng, M SPN và hai exact rights được fixture chứng minh; chưa có secret M, descriptor, delegated context hoặc admin C_R. Positive R-P giả định các runtime outcomes và **P authorization/admin execution trên C_R** là true với synthetic rationale. Không lấy quyền giả định này từ membership DA hoặc từ SEAMLESS.

R1 trước R2; R3 độc lập với R1/R2; R4 sau cả R2 và R3; R5 sau R4. Theo quy tắc minimal/one-use/first-hit ở mục 3, có đúng ba programs tới goal: `R1,R2,R3,R4,R5`; `R1,R3,R2,R4,R5`; `R3,R1,R2,R4,R5`. Một runner chỉ replay một ordered path chưa đủ kiểm generation.

Oracle reachable states **cho R-P từ initial state chưa có capability M** dùng bitset effects `{reset_M, service_M, descriptor_M_C_R, delegated_P_C_R, admin_C_R}` cộng initial state: service_M kéo theo reset_M; delegated kéo theo service_M+descriptor; admin kéo theo delegated. Có đúng **tám** states: sáu combinations của chuỗi reset/service với descriptor độc lập, thêm delegated và admin tại full prerequisites. Đây không là invariant cho ca có initial service_M như R-REUSE-M. Không bỏ program chỉ vì cùng terminal state. Khi một rule false/missing, giữ các prefixes/rules độc lập còn applicable; không xóa reset M chỉ vì descriptor bị chặn hoặc xóa descriptor chỉ vì service key chưa biết.

| Case | Delta so với R-P | Expected oracle |
| --- | --- | --- |
| R-P | Synthetic positive | Ba terminal programs, tám states; admin C_R conditional; không global P/DA checkpoint; unrated |
| R-RESET-F | Reset write gate false | Không reset/service_M/R4/R5; R3 vẫn có thể tạo descriptor dưới các gate riêng |
| R-WRITE-F / R-WRITE-U | Exact descriptor write gate false / missing | R3 blocked / indeterminate; R1/R2 vẫn có thể đạt service_M; không delegated/admin |
| R-SPN-F / R-SPN-U | M SPN false / missing trong separate fixture/view | R2 blocked / indeterminate; không service_M/delegated/admin; R1/R3 không bị blanket-veto |
| R-KEY-U | Required usable key/derivation gate unknown | Có thể giữ reset secret+descriptor; R2 indeterminate; không delegated/admin |
| R-POLICY-F | P delegation policy known-deny | R4 blocked; service_M+descriptor có thể đạt; không delegated/admin |
| R-DELEGATE-U | Required KDC/S4U/service-binding gate missing | R4 indeterminate; không delegated/admin; static sensitive=false không lấp gate này |
| R-ASSET-F / R-ASSET-U | P admin-execution authorization false / missing | R4 service context có thể đạt; R5 blocked / indeterminate; không admin C_R/global P |
| R-REUSE-M | Initial declared valid service_M capability/key, không phải chỉ GenericAll | Bỏ R1/R2 trong minimal programs; R3,R4,R5; không charge acquisition/key preparation lại |
| R-SCOPE | Chuyển asset/service goal sang C_other, không có quyền/configuration/binding tới đó trong closed fixture | P/C_R context không thỏa C_other; không global usable P hoặc success ở C_other; không claim no-path ở snapshot lớn |
| R-CF-ACL | Separate fixture/view bỏ exact descriptor-write support; giữ M acquisition | Không R3/R4/R5; nguyên nhân là write support, không AllowedToAct snapshot đang rỗng |
| R-EXT-OFF | Cùng initial U_R/target/runtime outcomes, tắt R3/R4 owner scope | Không delegated service context trong closed fixture; baseline reset capability vẫn được giữ; asset coverage phải so mọi baseline routes |

R-RAW trên SEAMLESS giữ U_R/M/C_R raw rights, khai báo initial U_R nếu có, nhưng không invent P→C_R authorization: endpoint success còn unknown. R-ASSUMED có positive chỉ dưới explicit P authorization/service/policy/outcome assumptions. Không cần mặc định MachineAccountQuota hoặc provision machine cho candidate M sẵn có; nếu B chọn nhánh khác, cần ca/provenance riêng.

## 5. Đối chứng Kerberoasting và tiêu chí “mở đường mới”

[#216](https://github.com/nairyuuu/ad-weighted-graph/issues/216) đã có scope của B: SPN snapshot → request material → recovery → activation; không mở AS-REP/RBCD trong cùng issue. A bàn giao các expectations sau để reuse, không thay task B.

| Case | Input và đối chứng | Expected / giới hạn |
| --- | --- | --- |
| K-OVERLAP | Initial usable User1580 hoặc User2201 cùng H0, đủ baseline reset/activation/host gates; target C0; owner scope baseline so với baseline+Kerberoasting; assumptions cho shared actions giữ nguyên | Baseline đã có candidate Group30→reset V_D→activation→DA→C0 dưới gates. Extension có thể thêm acquisition route qua V_K; không được claim C0 mới reachable chỉ vì route mới dài hơn. Chưa chạy actual hoặc so số C/P/I |
| K-NO-AUTH | Known absence của required usable Kerberos auth trong scoped state, không supported acquisition branch khác; target SPN fact true | Không apply request material chỉ từ SPN. Nếu auth availability chưa biết, giữ indeterminate thay cho known-absent blocked |
| K-MATERIAL | Request gates đủ, recovery outcome missing | Có thể đạt service-ticket material; không secret/usable V_K; downstream reset không mở bằng V_K |
| K-FACT | Required SPN false / missing qua snapshot fact view | Request blocked / indeterminate; không tạo fake HasSPN edge; canonical topology giữ nguyên |

Đối chứng implementation phải dùng cùng snapshot, query source/target/initial state, runtime và shared-action assumptions, caps và goal predicate. Chỉ allowed extension owner set thay đổi; assumptions mới chỉ dành cho extension phải xuất hiện trong ledger. Lưu cả baseline routes, extension routes và asset/checkpoint outcomes; edge/action count tăng không thay asset coverage.

Ở fixture nhỏ có independent finite oracle thì so exact programs/states. Ở SEAMLESS nếu bounded/truncated, chỉ báo delta trong generated scope; baseline không tìm thấy goal không là chứng minh extension là route duy nhất. RBCD từ U_R tới C_R cũng phải đối chứng với reset/host routes đã có trước khi claim asset mới.

## 6. Work units và C/P/I: bàn giao nghĩa trước số

Reuse [ADR-0013](../adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md) và evaluator tại [assessment.py](../../src/engine/ranking/assessment.py). Evaluator dùng exact Fraction và prefix conditional bounds theo ordered **unique work-unit IDs**, khử trùng persistent units bằng ID; không nhân theo structural edge count. A/B phải chốt binding tương đương về nghĩa, không chỉ đặt cùng ID để làm số đẹp.

| Công việc cần review binding | Success event / scope | Disposition hiện tại |
| --- | --- | --- |
| AS-REP request/acquisition | Có material đúng V_A trong acquisition context | Chưa numeric effort/bounds; network/request applicability không tự là probability |
| Recovery | Secret đúng owner/form recovered trong declared method/budget/horizon sau material acquisition | Missing data; effort/likelihood unrated, không suy từ password age/flags/SPN hoặc fixture recovery=true |
| Activation/authentication | Capability được chấp nhận ở đúng principal/context sau possession | Generic non-reset bridge cần B; không copy Week 3 `acquire_ticket` numbers khi event/binding khác |
| Passive membership/ACL closure | Suy entitlement từ facts và usable scope, không một exploit mới | Không work unit/thừa số mới chỉ vì thêm hop; không fabricate P=1 rating cho closure |
| RBCD M acquisition/reset | Reset success của đúng M, rồi service capability usable theo requirement | Reuse owner/mechanism khi đúng; rating chỉ reuse nếu actor/target/event/horizon/basis đúng, chưa nhận numeric release |
| Key preparation / descriptor write / delegation | Key phù hợp; config được chấp nhận; delegated service context đúng P/C_R/service | Review cái nào là công việc mới, preparation deterministic hoặc shared; không mặc định mỗi label thêm probability factor |
| Resource execution | Asset action đạt đúng privilege/goal trên C0 hoặc C_R | Required runtime gates và numeric basis riêng; DA/ticket không thay event |
| Asset impact | Hậu quả của successful asset event có business rationale | Impact unrated; DC/DA/Tier0 không tự I=Critical |

C là tổng công sức các công việc mới khác nhau; P dùng chain rule `∏ P(Ei | facts, scenario, successful prefix)`; I gắn asset success. Thêm sự kiện thành công thật có thể làm P giảm; không thêm length penalty/sàn xác suất/trung bình hình học. Exact arithmetic tránh underflow số thực, không làm xác suất đúng về nghĩa lớn hơn. Nhận xét mentor về P rất nhỏ được trả lời bằng event definitions, reuse và bounds sensitivity có căn cứ, không bằng thay công thức.

Các oracle A-SECRET/A-IDENTITY/R-REUSE-M kiểm không tính lặp bí mật/preparation đã có. Tách một công việc thành nhiều semantic explanations hoặc thêm membership hops không được tự tăng active work units; một authentication mới khác context không mặc định dùng lại toàn bộ rủi ro của lần trước. Khác order RBCD có thể cần prefix bounds khác, không suy cả ba programs có P giống nhau. Các routes chung prefix không được cộng như độc lập.

Applicability và scoring là hai kết quả: synthetic positive dưới declared outcomes vẫn có thể `effort_unrated`, `likelihood_unrated`, `impact_unrated`; assumption true không là numeric estimate. [#207](https://github.com/nairyuuu/ad-weighted-graph/issues/207) tiếp tục gói core; ratings cho extension cần basis/binding review riêng, không mở rộng core deliverable âm thầm.

## 7. Tái sử dụng, dependencies và ownership

| Lát công việc | Đầu ra / phần reuse | Owner và gate |
| --- | --- | --- |
| A: domain handoff hiện tại | Alias/raw locators, cases trên, finite expectation/proof, work-unit meanings và mentor narrative | A cung cấp; B review scope/outcomes. Không phụ thuộc code extension để viết kỳ vọng |
| Static fact access | Reuse reconciliation/canonical-ID/provenance; SPN/pre-auth lookup, known-false/missing | B đã tự nhận #215; API/schema chưa bàn giao. A không làm parser/fact-store implementation |
| Query/context/goal | Reuse #211–#213, `RuntimeContext`, stateful generator, checkpoint/asset separation và diagnostics | B triển khai core; A map/freeze executable extension inputs sau accepted interface |
| Request/recovery/activation | Reuse abstraction research #174 và parts từ #216; AS-REP trigger không yêu cầu AD credential sẵn có; preserve reset-specific provenance | B quyết định owner/state/artifact/trigger và tự chia việc. AS-REP implementation chưa có task/scope nhận riêng |
| RBCD next slice | Reuse reset M; add branch descriptor + scoped delegated service capability khi cần cho applicability | Chờ B nhận exact attribute/write/policy/service/asset boundary; không gate core hoặc yêu cầu full Kerberos simulator |
| Numeric package | Reuse release tooling/evaluator, exact action binding và full prefix records | A basis/disposition; B cross-review/consume. Không có số mới trong handoff này |
| Integration/acceptance | Generator tự tìm từ query; case matrix/baseline delta/provenance/immutability + hai run deterministic | B harness/integration; A kiểm actual sau executable handoff. Chưa chạy, chưa claim PASS extension |

Ước lượng **phần A còn lại**: khoảng nửa ngày để map/freeze inputs và expected package sau B bàn giao API, khoảng nửa ngày kiểm actual/đối chứng một lát nhỏ khi có executable handoff; chưa gồm chờ review hoặc thu runtime/rating evidence mới. Đây là planning estimate, không attack effort C. B tự ước lượng implementation sau chốt architecture, A không gán ngày hoặc assign task B.

Week 4 giữ core và fact/recovery interface hẹp; extension được nhận lát nào thì freeze/run lát đó. Week 5 đối chứng path-level/coverage và nối work-unit basis/choke-point work theo roadmap; Week 6 dùng output thực đã accepted cho demo/report. RBCD chỉ vào lịch khi gates/API/owner được B nhận; không hứa triển khai đủ hai chuỗi trước Week 4.

## 8. Checklist đóng research và bàn giao

| Tiêu chí #200 còn lại | Đã cung cấp ở tài liệu này | Còn phải nhận/kiểm |
| --- | --- | --- |
| Chọn 1–2 chuỗi, positive/blocked/unknown/counterfactual | AS-REP và RBCD đề xuất; programs/states, cases và Kerb control; expected trước actual | B review lựa chọn/finite-scope assumptions; RBCD positive là synthetic, quyền P thật chưa biết |
| Thay đổi/reuse/dependencies/A-B/ước lượng | Mục 7, liên kết tasks B có thật và core độc lập | B chọn exact API/implementation slice và effort; A freeze executable package sau handoff |
| Technical/boundary review và #192 | #217 research acceptance; wording known target đã sửa; mentor draft cập nhật | Review handoff này chưa xong; chưa có mentor scope approval hoặc implementation acceptance |

Không đóng #200/#192 chỉ vì merge #217. Một implementation slice được nghiệm thu khi query tự sinh steps, giữ true/false/missing, không apply unresolved effects, scope identity/asset đúng, invariants graph/provenance giữ nguyên, actual khớp oracle và CI/cross-review exact head đạt. Gói ca logic này chưa chạy exploit, crack mật khẩu, đo P hoặc extension coverage.

Nguồn cơ chế truy cập lại ngày 07/10/2026; static locators/digests tái sử dụng lần raw verify 06/10, không ghi thành rerun raw mới. Source links giải thích mechanisms, không cung cấp số rating hoặc chứng minh successful exploit trên SEAMLESS.
