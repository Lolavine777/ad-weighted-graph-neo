# Disposition chính thức cho thiết kế, tham số và tích hợp (A/B Acceptance Disposition Record)

- Ngày cập nhật: 2026-10-06.
- Người chuẩn bị: A @Lolavine777; reviewer: B @nairyuuu.
- Trạng thái: thiết kế/giao diện #165 và scoped parameters #176 accepted; final integration #182, reconciliation #47 và A/B reproduction #196 accepted; final package #48/#158 technically accepted bởi B, chờ merge #202 và closure issues.
- Refs [PR #165](https://github.com/nairyuuu/ad-weighted-graph/pull/165), [#163](https://github.com/nairyuuu/ad-weighted-graph/pull/163), [#162](https://github.com/nairyuuu/ad-weighted-graph/issues/162), [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [PR #159](https://github.com/nairyuuu/ad-weighted-graph/pull/159), [PR #161](https://github.com/nairyuuu/ad-weighted-graph/pull/161), #42, #48.
- Quy chiếu: [ADR-0013](../adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md), [Interface Specification 1.0.0](path-ranking-interface-specification.md), [Scoped Parameter Bundle 1.0.0](../../tests/fixtures/ranking/seamless_parameter_bundle.json), [governance 1.0.0](evidence-rating-governance.md), [SEAMLESS packet và brief](seamless-scenario-rating-packet.md).

## Current-state amendment - 2026-10-06

[Final handoff](../reports/week3-final-handoff.md) audit #143/#42 trên integrated `develop@891bda0001b9958e712cff54045f651273b43fd0` và pin current E2E cùng accepted reconciliation/reproduction.
Các gate design/interface, actual scoped parameters và final search/semantic bridge/ranking đã satisfied theo #165/#176/#182; #47/#196 đã closed.
B đã technically accept package #48/#158 sau fresh Legacy replay PASS trên `891bda0`; exact sets/difference ledger khớp accepted #196, comparator CLI thật `NOT_MEASURABLE` / exit 2.
Final binding/cross-review kỹ thuật hoàn tất; exact package head `3c35667` có CI/branch policy success; [B acceptance](https://github.com/nairyuuu/ad-weighted-graph/pull/202#issuecomment-6008927093) không bị suy từ CI.
Còn merge #202 sau B rereview sửa current state, đóng #48/#143/#42/#158 theo declared scope, final release review #186 rồi promote `develop → main` bằng merge commit nếu approval/checks đạt.
Các bảng pending integration/reconciliation bên dưới là checkpoint lịch sử; không yêu cầu làm lại ratings/model hoặc sửa pending independent-rating fixtures.
Human-reviewed AI-assisted basis, thiếu empirical calibration, bounded/truncated coverage và full Legacy `NOT_MEASURABLE` vẫn là limitations hiện hành.
Week 4 #192/#200 không thuộc closeout.

## 1. Quyết định chính thức và ranh giới chấp thuận

Tài liệu này ghi nhận các quyết định chấp thuận tường minh của TTS A đối với thiết kế xếp hạng Pareto bảo thủ của ADR-0013, Đặc tả giao diện phiên bản 1.0.0 quy chuẩn (Interface Specification 1.0.0), và Gói tham số kịch bản có phạm vi phiên bản 1.0.0 (Scoped Parameter Bundle 1.0.0).
Research acceptance ở [PR #151](https://github.com/nairyuuu/ad-weighted-graph/pull/151#pullrequestreview-5362415389) và kết quả chuyển dịch tương thích canonical engine đã merge tại [PR #163](https://github.com/nairyuuu/ad-weighted-graph/pull/163) cấu thành nền tảng kỹ thuật vững chắc cho các quyết định này.
Approval/merge PR #163 đã chứng minh rằng các fixture kịch bản của TTS A tương thích hoàn toàn và chạy sạch qua engine chuẩn tắc của TTS B mà không cần sửa đổi bất kỳ tệp nguồn nào thuộc quyền sở hữu của TTS B.
Tại PR #165, Reviewer TTS B (@nairyuuu) đã chính thức phê duyệt disposition tại review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338) trên exact head `dd662f5`, và PR #165 đã được merge vào develop tại commit `fdf5928`.

Theo quy trình phân định trách nhiệm tại #158 và #143:
- Thiết kế xếp hạng (ADR-0013), giao diện hợp đồng (Interface 1.0.0), phân định vết đường cấu trúc (Route vs. Work Identity), và các giả thiết kịch bản được TTS A và TTS B chính thức chấp thuận trong phạm vi PR #165.
- Gói tham số có phạm vi (Scoped Parameter Bundle 1.0.0) được ban hành dưới dạng các giả thiết kịch bản có hỗ trợ nghiên cứu (research-assisted scenario hypotheses) với digest `sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`, phục vụ kiểm chứng tích hợp và phân tích độ nhạy có thể tái lập 100%.
- Bảng chấm điểm thực tế của con người (`seamless_rater_1.json`, `seamless_rater_2.json`) tiếp tục duy trì nguyên vẹn ở trạng thái `pending_independent_ratings` với toàn bộ trường rỗng/null; không tự phong chuyên gia, không tạo dữ liệu giả mạo người chấm, và không tuyên bố hiệu chuẩn thực nghiệm sản phẩm (empirical calibration).
- Phán quyết khoa học trên snapshot SEAMLESS tiếp tục giữ nguyên là `Insufficient Evidence` cho xếp hạng dự đoán sản phẩm.

Current-state amendment 2026-10-06 phía trên là trạng thái hiện hành.
Các bảng tại Mục 2 và nghiên cứu tại Mục 3-4 giữ checkpoint của #165 trước actual release #176 và final integration/reproduction; pending tại checkpoint đó không phải gate hiện hành.
Research fixtures/verifier không thay actual release và không tạo gate chấm lại cho kịch bản đã có disposition.

## 2. Ma trận status/gates lịch sử tại #165

Bảng này giữ status matrix của checkpoint #165 từng được packet, weighting-direction, worklog và tracker #158 dẫn chiếu.
Các tài liệu không được đổi nghĩa hoặc gộp các cổng thành một completion state.

| Gate / owner | Tiêu chí | Evidence hiện có | Disposition tường minh của TTS A | Trạng thái TTS B / Cổng chưa mở |
| --- | --- | --- | --- | --- |
| 1. Design: scoped ranking / A+B | Independent consequence và full-history conditional likelihood; conservative dominance với ít nhất một strict inequality; preserve incomparability; narrow exact-point effort tie-break; separate Min-Effort-to-DA | ADR-0013 Mục 1-6; reviewed scoped proposal #151; worked-example và oracle tests | **Accepted** (TTS A chấp thuận tường minh tại Mục 5.1 trong phạm vi đơn điệu) | **Accepted** (TTS B phê duyệt tại #5387665338 trên head `dd662f5`, commit `fdf5928`) |
| 2. Design: interface / A+B | Authoritative layers 1/2/3 độc lập với observed/false/assumed/unknown buckets; known-false veto; exact rational factors; first-goal replay; invalid/unknown/unrated fail-closed; version/migration boundary | Interface 1.0.0 quy chuẩn; migration adapter và canonical dispatch đã merge tại PR #163; 230/230 focused tests pass | **Accepted** (TTS A chấp thuận chuẩn hóa Interface sang 1.0.0 quy chuẩn tại Mục 5.2) | **Accepted** (TTS B phê duyệt giao diện quy chuẩn 1.0.0 tại #5387665338, commit `fdf5928`) |
| 3. Design: route/work identity / A+B | Giữ structural node/edge traces riêng với work history; không dùng program count làm path count | Interface Mục 2.3/3; canonical verification đủ 3 supplied routes; canonical IDs và WU aliases map trong packet và bundle | **Accepted** (TTS A chấp thuận tường minh tại Mục 5.3) | **Accepted** (TTS B phê duyệt phân định vết đường cấu trúc tại #5387665338, commit `fdf5928`) |
| 4. Parameters / A | Reviewed basis/assumptions, rubric/overlap, versioned actual release và oracle/validation/sensitivity | [Release Week 3](ratings/week3-closeout/README.md), 21 decisions; C/P/I và 21 probes/24 outcomes khớp | **Accepted trong kịch bản Week 3** theo [disposition cơ sở tham số](week3-rating-requirement-disposition.md) | B review closeout tại #5398792824; numeric baseline giữ nguyên sau chuẩn hóa; final integration là gate riêng |
| 5. SEAMLESS assessment / A+B | Verdict theo đúng candidate scope và coverage | Ba supplied candidates có structural traces, declared runtime assumptions, reviewed actual parameters và engine/oracle matching | **Validated supplied-candidate assessment**; không claim global search/calibration | Bounded search/integration và final E2E coverage **Pending**; không chặn bằng requirement chấm lại đã có scoped disposition |
| 6. Official disposition / A+B | Explicit decision cho design/interface và bản ghi version/scope/migration | Bản ghi disposition toàn diện này cùng PR tương ứng; 46/46 tests proposal và 251 focused tests pass | **Accepted by TTS A** (Mục 5.6 hoàn tất quyết định của A) | **Accepted** (TTS B phê duyệt chính thức tại #5387665338 trên head `dd662f5` cho phạm vi PR #165, commit `fdf5928`) |

| Gate sản phẩm khác theo #158 | Owner | Trạng thái / evidence còn cần |
| --- | --- | --- |
| Bounded graph/search/evaluator integration #145/#155 | B implementation; A/B acceptance | Pending trong PR này; final adapter/API/CLI conformance, positive/false/unknown outputs và coverage trên một final integrated revision |
| Same-snapshot Legacy / structural reconciliation #82/#47 | B baseline/export; A comparison | Gate riêng; framework #157 merge ở `8c15993`, không phải completed real reconciliation |
| Product E2E / release #48 | A điều phối, B runtime, A/B review | Pending; accepted design, reviewed parameters, integration/reconciliation và clean-checkout evidence đầy đủ |

Scalable search, Top-K, choke points, full CE parity và global-optimality claims không phải yêu cầu của lượt #159; #158 đặt chúng ngoài scope Week 3 đã chọn.
CI, packet prepared hoặc blocker được ghi lại không đủ để tick Week 3 complete.

## 3. Phạm vi kiểm chứng và giới hạn

Helper [seamless_packet_evidence.py](../../scripts/research/seamless_packet_evidence.py) kiểm tra graph export từ official parser, raw locators và scenario replay qua research adapter.
[Evidence manifest](../../tests/fixtures/ranking/seamless_evidence_manifest.json) giữ code/graph/policy/input pins và expected/actual cases đã chạy.
Nó không thay search implementation của B, structural reconciliation Legacy hoặc integrated product E2E.
Graph export dùng profile `unit`; mọi numeric likelihood/impact/effort của SEAMLESS vẫn unrated.
Conditional factors được hỏi riêng cho từng outcome/history/F/S, prefix chỉ là lookup key.
Không tạo HasSession edge hoặc observed-false runtime assertion từ missing collection.

## 4. Điều kiện unblock tham số

| Missing evidence | Owner | Phương pháp / acceptance |
| --- | --- | --- |
| Technical/business scenario conditions | A đề xuất, B review | Review sources và exact action bindings; declared assumptions giữ Proposed tới explicit review; thiếu basis có thể giữ unrated |
| Hai independent rating sets | A/B hoặc hai người phù hợp trong nhóm | Actual identity/competence/scope/independence/time, raw impact/likelihood/effort, sources/rationale và review trace; signature/organization tùy chọn |
| Research/LLM-assisted estimates | A chuẩn bị, A/B review | Verified sources và conditional outcome/history/F/S; basis/scope/uncertainty/sensitivity, explicit A/B decision; có thể test khi human agreement pending, không claim human consensus/calibration |
| Agreement và overlap disposition | A+raters, B review | Governance 1.0.0: impact Kappa reference 0.70 nếu defined, observed agreement/confusion/raw ratings và small-sample/degenerate fallback; likelihood IoU reference 0.50/uncertainty widths; effort delta <=1 và rubric/overlap review |
| Validated versioned bundle | A, B review | Accepted design và adequate basis; exact query/scenario/foothold/horizon/version binding, rational bounds, manual/oracle validation và sensitivity |

Không yêu cầu Kappa defined cho mọi dataset và không dùng consensus cuối để che raw disagreement.
Với một target cùng category, null Kappa là zero-variance disposition, không phải tự động failed agreement hoặc đủ điều kiện phát hành.
Tất cả policy thresholds là các baseline references, phải công bố descriptive measures và reviewer decision.
Không tự xác nhận rater competence/chữ ký, không suy calibration hoặc production_ready từ helper/tests.
[#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) giữ mở cho parent hard gates.

## 5. Bản ghi quyết định và phân định chuyển dịch thiết kế (Design, Versioning, and Migration Disposition Record)

Mục này ghi nhận quyết định chấp thuận tường minh của TTS A cho từng cổng disposition theo yêu cầu của Issue #143 và #158.
Quyết định của TTS A có hiệu lực độc lập theo thẩm quyền nghiên cứu mô hình; phê duyệt chính thức toàn dự án vẫn chờ sự xác nhận độc lập (explicit sign-off) từ TTS B trên PR hoặc issue.

### 5.1. Quyết định thiết kế ADR-0013 (Gate 1: Scoped Ranking Model)

TTS A chính thức chấp thuận (officially accepts) khung lý thuyết xếp hạng Pareto bảo thủ có phạm vi của ADR-0013.
Khung lý thuyết bảo toàn các bất biến kiến trúc cốt lõi:
- Likelihood có điều kiện theo toàn bộ lịch sử tiền tố (full-history conditional likelihood).
- Quy tắc ưu thế Pareto bảo thủ trên hai trục độc lập: Tác động nghiệp vụ ($I$) và Khoảng xác suất thành công ($P \in [l, u]$), đòi hỏi ít nhất một bất đẳng thức nghiêm ngặt.
- Giữ nguyên trạng thái không so sánh được (`incomparable`) khi hai khoảng xác suất giao nhau hoặc khi có sự đánh đổi giữa hai trục.
- Trục tác động riêng biệt không phá vỡ điều kiện giao nhau của khoảng xác suất; khi hai khoảng xác suất giao nhau, ứng viên có tác động cao hơn vẫn không chiếm ưu thế Pareto tuyệt đối nếu cận dưới của nó không vượt quá cận trên của ứng viên còn lại.
- Tie-break bằng nỗ lực định mức ($C$) chỉ được kích hoạt trong trường hợp cực hẹp: cùng tác động, cùng xác suất điểm chính xác, và nỗ lực của cả hai ứng viên đều đã được định mức.
- Duy trì truy vấn Min-Effort-to-DA như một baseline riêng biệt, có công bố độ bao phủ và không bị đánh đồng với biên Pareto.
- Trạng thái phía TTS A: **Accepted**.
- TTS B phê duyệt độc lập trên GitHub Issue #143 hoặc PR review; quyết định này không phụ thuộc vào việc hoàn tất actual ratings hay engine integration #146/#156.

### 5.2. Quyết định giao diện, phiên bản và chuyển dịch (Gate 2: Interface 1.0.0, Versioning & Migration)

TTS A chính thức chấp thuận ban hành Đặc tả giao diện phiên bản 1.0.0 quy chuẩn (Interface Specification 1.0.0), chính thức loại bỏ hậu tố `-draft`.
Chính sách phiên bản và ranh giới chuyển dịch (Migration Boundary) được xác lập như sau:
- **Nguyên tắc tương thích ngược và chuyển dịch:**
  - Mô hình trọng số cố định theo cạnh `maut_v1` của ADR-0001 bị loại khỏi vai trò sản phẩm, chỉ duy trì làm đối chứng thực nghiệm lịch sử (`production_ready: false`).
  - Baseline Dijkstra với profile `unit` ($W=1.0$) được bảo lưu độc lập làm baseline kiểm thử hồi quy cấu trúc cho engine ở Milestone 2.
  - Các hệ thống tiêu thụ (như engine của TTS B) chuyển dịch sang tiêu thụ đối tượng `PathRankingQuery` gồm 6 thành phần hoàn chỉnh và trả về `PathRankingResult`.
  - Bốn buckets dữ kiện (`observed_facts`, `false_facts`, `assumed_facts`, `unknown_facts`) phân định rõ nguồn gốc bằng chứng, độc lập với ba tầng thẩm quyền vị từ (Layer 1, Layer 2, Layer 3).
  - Vị từ phủ định được xác nhận (`false_facts`) thực thi quyền phủ quyết (known-false veto), lập tức chuyển trạng thái ứng viên sang `blocked` và withholding tính toán xác suất/nỗ lực khi và chỉ khi vị từ đó là điều kiện tiên quyết bắt buộc (required predicate) cho chuỗi hành động tới mục tiêu đầu tiên (first goal) của ứng viên.
  - Các vị từ sai không liên quan trong facts ledger không áp đặt phủ quyết toàn cục lên các ứng viên không phụ thuộc vào chúng.
  - Vị từ thiếu bằng chứng (`unknown_facts`) chuyển trạng thái ứng viên sang `unknown` và withholding tính toán xác suất/nỗ lực khi và chỉ khi vị từ đó là điều kiện tiên quyết bắt buộc của ứng viên.
  - Các vị từ không rõ không tham gia vào chuỗi chứng minh khả thi (ví dụ: `edr_telemetry`, `session_badblood`) được bảo lưu trong facts ledger mà không gây ảnh hưởng tiêu cực lên các ứng viên hợp lệ.
  - Mọi tính toán số học trên khoảng xác suất bắt buộc sử dụng phân số chính xác tuyệt đối (stdlib `Fraction`) và tuần tự hóa dưới dạng chuỗi phân số không mất mát thông tin.
- **Quy chuẩn danh mục trạng thái trùng lặp (`overlap_state` Enum & Alias):**
  - Trong đặc tả giao diện Interface 1.0.0 Mục 2.4, hai giá trị chuẩn tắc (canonical enum values) là `independent` (đơn vị công việc độc lập/phân biệt) và `unresolved_overlap` (trùng lặp chưa xử lý).
  - Nhằm bảo toàn tính tương thích với wire adapter và fixtures nghiên cứu hiện hành (vốn chấp nhận `distinct_work` và `composite_subsumed`), `distinct_work` được xác lập là bí danh tương thích ngược (backward-compatible wire alias) của `independent`.
  - Cả `independent` và bí danh `distinct_work` đều đại diện cho công việc phân biệt không bị tính trùng; khi `rating_status == "rated"`, bắt buộc phải có điểm rubric hợp lệ ($0 \le C \le 4$).
  - Khi thiếu cơ sở định mức hoặc thực hiện withholding, `rating_status == "unrated"` với `rubric_scores: null` và `computed_cost: null` là trạng thái hợp lệ.
  - Giá trị `unresolved_overlap` bắt buộc `rating_status == "unrated"` và `computed_cost == null`.
- **Ranh giới trách nhiệm:**
  - TTS A chịu trách nhiệm về contract đặc tả giao diện, bộ oracles hành vi, fixtures kịch bản, gói tham số và công cụ đối soát nghiên cứu.
  - TTS B toàn quyền quyết định cấu trúc nội bộ của engine tìm kiếm (Graph index, state representation, search algorithm) miễn là vượt qua bộ kiểm thử hợp đồng hành vi.
- Trạng thái phía TTS A: **Accepted**.
- Ranh giới chuyển dịch canonical adapter đã được nghiệm thu kỹ thuật qua PR #163 đã merge.

### 5.3. Quyết định tách biệt vết đường cấu trúc và sổ cái công việc (Gate 3: Route vs. Work Identity)

TTS A chính thức chấp thuận thiết kế tách biệt vết đường cấu trúc khỏi sổ cái công việc.
- Engine bắt buộc phải lưu giữ riêng biệt các vết đường cấu trúc (`structural_routes`) gồm danh sách canonical node IDs, canonical edge IDs và raw provenance locators.
- Sổ cái công việc chuẩn tắc (`work_units_ledger`) chỉ đóng vai trò tính toán nỗ lực và tra cứu tiền tố xác suất.
- Tuyệt đối không dùng số lượng chương trình công việc (program count) thay cho số lượng đường đi cấu trúc (path count).
- Trạng thái phía TTS A: **Accepted**.
- TTS B đã chính thức phê duyệt tại review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338) trên head `dd662f5`, commit `fdf5928`.

### 5.4. Quyết định ràng buộc kịch bản và giả thiết runtime (Gate 4: Scenario Bindings & Assumptions)

TTS A xác nhận toàn bộ 26 giả thiết runtime độc nhất trong kịch bản (gồm 24 giả thiết trong Source A, 13 giả thiết trong Source B, hợp nhất thành 26 vị từ sau khi tách riêng `network_rpc_reachable` theo phạm vi Source A và Source B) đã được ràng buộc tường minh trong các fixture đề xuất và gói tham số chuẩn tắc:
- Nhóm 1 (Foothold LocalSystem): `foothold_controlled_tstwvir` (Source A) và `foothold_controlled_finwvir` (Source B) giả định máy tính foothold có thể sử dụng danh tính tài khoản máy tính để kết nối AD trong phạm vi kịch bản.
- Nhóm 2 (Kết nối mạng và dịch vụ khả dụng): `network_rpc_reachable` (Source A), `network_rpc_reachable_source_b` (Source B), `network_kdc_reachable`, `network_winrm_reachable`, `service_winrm_running` giả định các kênh vận chuyển mở và kết nối mạng tới DC/KDC khả dụng xuyên suốt khung thời gian 24h (loại trừ đứt cáp, phân vùng mạng, hoặc sự cố mất kết nối mạng kéo dài); dịch vụ WinRM và listener sẵn sàng.
- Nhóm 3 (Ánh xạ quản trị máy chủ đích): `da_host_admin_mapping` giả định ánh xạ mặc định từ Domain Admins vào nhóm Administrators cục bộ của Domain Controller có hiệu lực thực tế.
- Nhóm 4 (Chính sách mật khẩu hợp lệ): `password_policy_accepts_lidia`, `password_policy_accepts_josefa`, `password_policy_accepts_ollie` giả định mật khẩu mới đáp ứng độ dài và độ phức tạp tại thời điểm thực hiện thao tác ghi.
- Nhóm 5 (Quyền ghi thư mục hiệu lực): `directory_write_allowed_lidia`, `directory_write_allowed_josefa`, `directory_write_allowed_ollie` định nghĩa cổng là điều kiện cho phép ghi (effective access / policy permit), không phải trạng thái giao dịch đã được ghi nhận vào NTDS.
- Nhóm 6 (Xác thực Kerberos được chấp nhận): `authentication_accepted_lidia`, `authentication_accepted_josefa`, `authentication_accepted_ollie` định nghĩa cổng là điều kiện xác thực được chấp nhận (credentials/account controls permit ticket issuance), không phải KDC đã cấp vé Kerberos TGT.
- Nhóm 7 (Entitlement nhóm bảo mật trong runtime token): `membership_security_group_usable_lidia_da`, `membership_security_group_usable_josefa_vajer`, `membership_security_group_usable_ollie_da` giả định token xác thực chứa entitlement nhóm bảo mật tương thích tại tài nguyên đích (không suy diễn cấu trúc snapshot groupType).
- Nhóm 8 (Ngữ cảnh thực thi từ xa qua WinRM): `winrm_authentication_accepted_lidia`, `endpoint_authorized_lidia`, `admin_execution_context_lidia`, `winrm_authentication_accepted_ollie`, `endpoint_authorized_ollie`, `admin_execution_context_ollie` giả định endpoint PowerShell cho phép kết nối và tiến trình lệnh chạy dưới elevated token không bị giới hạn JEA.
- Các vị từ không rõ (`unknown_facts`): `session_badblood` và `edr_telemetry` được ghi nhận trung thực do snapshot không thu thập phiên hoạt động hay cảm biến EDR; do không nằm trong tập tiên quyết bắt buộc của các ứng viên, chúng không gây cản trở tính khả thi.
- Trạng thái phía TTS A: **Accepted** dưới dạng các giả thiết kịch bản nghiên cứu được công bố (declared research hypotheses).
- TTS B đã rà soát và phê duyệt các giả thiết này trong phạm vi PR #165 tại review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338).

### 5.5. Phán quyết kiểm chứng SEAMLESS (Gate 5: Predictive Verdict)

- Phán quyết khoa học trên snapshot SEAMLESS tiếp tục giữ nguyên là **Insufficient Evidence** cho xếp hạng dự đoán sản phẩm.
- Việc phát hành gói căn cứ tham số (parameter bundle) dưới dạng các giả thiết kịch bản có hỗ trợ nghiên cứu cho phép kiểm thử tính đúng đắn của giao diện và thuật toán, nhưng không thay thế cho sự đồng thuận của con người (human agreement) hay việc rà soát độc lập các căn cứ.
- Theo định hướng của mentor, hiệu chuẩn thực nghiệm (empirical calibration) là một hạng mục bằng chứng tùy chọn hoặc trong tương lai, không phải là cổng chặn bắt buộc đối với xếp hạng dự đoán kịch bản hay sản phẩm Week 3.
- Phán quyết Insufficient Evidence duy trì là do thiếu căn cứ tham số đã được review độc lập (reviewed basis), thiếu bộ đánh giá con người độc lập (adequate independent human ratings), và thiếu kiểm chứng phạm vi (validation in scope).
- Trạng thái khoa học: **Insufficient Evidence**.

### 5.6. Hồ sơ phê duyệt chính thức (Gate 6: Official Disposition Gate)

- TTS A: Đã hoàn tất phê duyệt disposition toàn diện cho ADR-0013, Interface 1.0.0, Scenario Bindings và Scoped Parameter Bundle 1.0.0.
- TTS B: Đã hoàn tất review và phê duyệt chính thức tại review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338) trên exact head `dd662f5`, commit `fdf5928`.
- Trạng thái phía TTS A: **Accepted**.
- Trạng thái toàn dự án: **Accepted by TTS A & TTS B** cho phạm vi PR #165.

### 5.7. Bản ghi chuyển dịch và đối chiếu ranh giới giao diện Canonical 1.0.0 (Gate 2/6: Canonical Engine Migration Record #162)

Nhằm khắc phục hoàn toàn sự sai lệch schema dẫn đến lỗi thoát exit code 2 khi nạp packet vào engine chuẩn tắc của TTS B (`src/engine/ranking/`), TTS A đã thiết lập bộ chuyển dịch có phiên bản (versioned migration adapter) và đối chiếu ranh giới giao diện theo Issue #162.
PR #163 đã được merge vào `develop` tại commit `98fb7664248310933af2fd70f06cd9185e655d6c` (head `d565e37eea9a9c19163ee25c2b5533ab08b47728`).

- **Đối chiếu khác biệt cấu trúc và ranh giới chuẩn tắc:**
  1. **Trạng thái trùng lặp đơn vị công việc (`overlap_state`):**
     Sổ cái công việc chuẩn tắc của B quy định giá trị hợp lệ là `independent` và `unresolved_overlap`.
     Định danh `independent` là xác nhận công việc phân biệt không bị tính trùng lặp nỗ lực trong sổ cái kế toán (non-overlapping effort accounting).
     Định danh này hoàn toàn tách biệt với khái niệm độc lập thống kê (statistical independence) của các biến cố xác suất.
     Bí danh `distinct_work` trong wire schema được hàm chuyển dịch tự động chuẩn hóa về `independent`.
  2. **Định danh kỹ thuật của hành động (`technique_name` vs `technique`):**
     Specification 1.0.0 của B yêu cầu trường bắt buộc `technique_name`.
     Hàm chuyển dịch sao chép `technique` sang `technique_name` và bảo lưu trường `technique` cũ để tương thích 100% với cả hai hệ thống.
     Các đóng thụ động (`is_passive_closure: True`) được chuẩn hóa danh sách `referenced_work_unit_ids: []`.
  3. **Ràng buộc phạm vi tường minh của ứng viên (`scope_binding`):**
     Engine B yêu cầu mỗi ứng viên phải mang một từ điển `scope_binding` gồm đúng 7 trường: `query_id`, `scenario_id`, `scenario_version`, `snapshot_id`, `work_boundary`, `horizon`, `foothold_node_id`.
     Hàm chuyển dịch tự động trích xuất các trường tương ứng từ `query_metadata` để tiêm vào ứng viên khi vắng mặt, và từ chối fail-closed nếu có xung đột trường.
  4. **Bộ định vị nguồn gốc cạnh cấu trúc (`provenance_locators`):**
     Engine B yêu cầu mọi vết đường cấu trúc (`structural_routes`) phải có mảng `provenance_locators` với độ dài đúng bằng số cạnh trong đường ($P = E$).
     Bảng tra cứu chuẩn tắc `SEAMLESS_CANONICAL_EDGE_LOCATORS` ánh xạ 1:1 cả 8 cạnh đã được kiểm chứng với BloodHound raw JSON pointer tương ứng, được gán phạm vi nghiêm ngặt theo SHA snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
- **Cơ chế chuyển dịch làm dày (Hardened Versioned Migration):**
  - **Điều phối phiên bản:** Khai báo ma trận hỗ trợ nguồn (`SUPPORTED_SOURCE_VERSIONS = {"legacy_draft", "1.0.0-draft", "1.0.0"}`) và đích (`SUPPORTED_TARGET_VERSIONS = {"1.0.0"}`); từ chối fail-closed (`ValueError`) khi phiên bản không được hỗ trợ.
  - **Giới hạn phạm vi snapshot:** Bảng locator mặc định chỉ áp dụng cho snapshot đã kiểm định; các snapshot khác bắt buộc phải cung cấp `edge_locators_table` tường minh, nếu thiếu sẽ từ chối fail-closed.
  - **Xác thực chi phí fail-closed:** Từ chối sai lệch chi phí trong dải (within-scale: khai báo 3 vs kỳ vọng 1), ngoài dải (out-of-scale: 999), hoặc xung đột bí danh (`effort_cost != computed_cost` hoặc `rubric.computed_cost != effort_cost`) mà không làm thay đổi giá trị số đã khai báo; chỉ tự động điền khi trường vắng mặt hoặc mang giá trị `None`.
  - **Xác thực kiểu dữ liệu nghiêm ngặt:** Từ chối kiểu sai (ví dụ `technique_name=123`, `scope_binding=False`, `provenance_locators=False`) và từ chối bí danh xung đột.
- **Hiện thực và công cụ:**
  - Triển khai hàm `migrate_wire_payload_to_canonical(payload, target_version="1.0.0", edge_locators_table=None)` tại `scripts/research/path_ranking_wire_adapter.py`.
  - Cập nhật đồng bộ 4 fixture input (`tests/fixtures/ranking/seamless_proposed_query_input.json`, `seamless_source_b_proposed_query_input.json`, `seamless_query_input.json`, `seamless_source_b_query_input.json`).
  - Cập nhật đồng bộ 4 fixture output (`seamless_proposed_expected_output.json`, `seamless_source_b_proposed_expected_output.json`, `seamless_expected_diagnostics.json`, `seamless_source_b_expected_diagnostics.json`).
- **Kiểm chứng kỹ thuật:**
  - CLI `src.engine.ranking.cli` chạy sạch mã thoát 0 với cả fixture đề xuất Source A và Source B.
  - Source A xuất HAI ứng viên trên biên Pareto (`cand_seamless_01_direct_lidia` và `cand_seamless_02_alt_vajer_ollie`), Min Effort = 2 (`cand_seamless_01_direct_lidia`).
  - Source B xuất MỘT ứng viên trên biên Pareto (`cand_seamless_source_b_01_ollie`), Min Effort = 2.
  - API `PathRankingEngine(version="1.0.0").evaluate(...)` bảo toàn đầy đủ `parameter_audit` ở tầng gốc cùng `work_unit_basis`, `conditional_bounds_basis`, `diagnostic_reasons` bên trong từng ứng viên.
  - Cơ chế fail-closed xác nhận CLI trả về exit code 2 khi nhận schema chưa chuyển dịch hoặc thiếu trường bắt buộc.
- **Trạng thái quản trị:**
  - Đã nghiệm thu kỹ thuật và hợp nhất vào nhánh `develop`.
  - Giữ nguyên các bảng xếp hạng của con người (`seamless_rater_1.json`, `seamless_rater_2.json`) ở trạng thái unrated/pending.
  - Không sửa đổi mã nguồn engine/parser của TTS B trong `src/engine/` hoặc `src/parser/`.

### 5.8. Bản ghi phát hành gói tham số có phạm vi (Gate 4: Scoped Parameter Bundle 1.0.0 Record)

TTS A chính thức phát hành Gói tham số kịch bản có phạm vi phiên bản 1.0.0 (Scoped Parameter Bundle 1.0.0) tại [tests/fixtures/ranking/seamless_parameter_bundle.json](../../tests/fixtures/ranking/seamless_parameter_bundle.json).
Gói tham số đóng gói đầy đủ và độc lập toàn bộ các tham số định mức nghiên cứu cho kịch bản SEAMLESS:

- **Thành phần gói tham số:**
  1. `bundle_metadata`:
     - Định danh: `bundle-seamless-host-to-dc-v1`.
     - Phiên bản: `1.0.0`.
     - Kịch bản: `scenario-seamless-host-to-dc` phiên bản `1.1.0`.
     - Snapshot: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
     - Biên công việc: `intra_forest`, chân trời `24h`, ngân sách công việc chủ động 6 đơn vị.
     - Mục tiêu kịch bản: `terminal_compromise_seamless_dc` trên DC `...-1000`.
  2. `governance`:
     - Phân loại căn cứ: `research_assisted_scenario_hypotheses`.
     - Trạng thái: `pending_independent_human_ratings`.
     - Đồng thuận con người: `pending`.
     - Hiệu chuẩn thực nghiệm: `none`.
     - Danh sách người chấm: `[]`.
  3. `target_impact_assessments`:
     - Đánh giá hậu quả tài sản đích BADBLOOD DC (`...-1000`): Mức `High`, trạng thái `rated`, lý giải nghiệp vụ cụ thể bảo vệ tính bảo thủ trước nhãn `Critical`.
  4. `work_units_ledger`:
     - Toàn bộ 9 đơn vị công việc chuẩn tắc (WU 1-9) với điểm rubric ($T_1, T_2$), công thức `"base"` ($C = T_1 + T_2 - 2$), chi phí nỗ lực $0 \le C \le 4$, trạng thái `independent`, và nguồn kỹ thuật Microsoft Open Specifications.
  5. `conditional_bounds_table`:
     - Toàn bộ 11 câu hỏi tiền tố có điều kiện ($q_1 \ldots q_{11}$) với chuỗi phân số chính xác tuyệt đối (stdlib `Fraction`), nguồn kỹ thuật đối chiếu và giải trình độ bất định dư thừa sau chính sách bounded retry.
  6. `facts_ledger`:
     - 14 dữ kiện quan sát (`observed_facts`), 26 giả thiết runtime đã khai báo (`assumed_facts`), 2 vị từ thiếu bằng chứng (`unknown_facts`), và bảng phân tầng thẩm quyền 51 vị từ (`predicate_layers`).
  7. `candidate_envelopes`:
     - 3 ứng viên hợp lệ (2 ứng viên Source A, 1 ứng viên Source B) với đầy đủ 7 trường `scope_binding`, các vết đường cấu trúc chuẩn tắc và mảng `provenance_locators` trỏ về BloodHound raw pointers.
  8. `analytical_baseline`:
     - Vết tính toán giải tích xác nhận Candidate 1 có xác suất $[42/125, 171/250]$, nỗ lực 2, tác động High; Candidate 2 có xác suất $[126/625, 55233/100000]$, nỗ lực 3, tác động High; Candidate B có xác suất $[42/125, 171/250]$, nỗ lực 2, tác động High.
     - Biên Pareto rủi ro bảo toàn tính không so sánh được giữa Candidate 1 và Candidate 2 trên Source A; Min-Effort-to-DA chọn Candidate 1 (nỗ lực 2 < 3).

- **Kiểm chứng phân tích độ nhạy lân cận trên gói tham số:**
  1. *Độ nhạy ma sát tương tác ($T_2$):*
     Tăng ma sát của các bước đặt lại mật khẩu Lidia và WinRM Lidia ($T_2: 2 \to 3$) làm nỗ lực Candidate 1 tăng từ 2 lên 4.
     Winner của Min-Effort-to-DA bị đảo chiều sang Candidate 2 ($C=3 < 4$), trong khi biên Pareto rủi ro vẫn giữ nguyên cả hai ứng viên do khoảng xác suất tiếp tục giao nhau.
  2. *Độ nhạy thu hẹp khoảng xác suất lồng nhau:*
     Thu hẹp khoảng xác suất của Candidate 1 về $[459/800, 171/250] = [0.57375, 0.684]$ bên trong khoảng ban đầu.
     Do $l_1 = 0.57375 > 0.55233 \approx u_2$, Candidate 1 chiếm ưu thế Pareto tuyệt đối, biên Pareto sụp đổ từ 2 ứng viên về duy nhất Candidate 1.
  3. *Độ nhạy quét chuỗi tham số (Compound 10% Upper Bound Reduction Sweep):*
     Giảm 10% cận trên của Candidate 2 đồng thời qua cả 5 bước.
     Tích lũy cận trên $u_2'$ suy giảm về $0.32615 < 0.336 = l_1$.
     Biên Pareto đảo chiều từ không so sánh được về duy nhất Candidate 1.
  4. *Kiểm tra tuân thủ hành vi và bất biến:*
     Xác nhận tie-break bằng nỗ lực khi xác suất điểm trùng nhau, duy trì biên khi chuyển tác động sang Critical, cơ chế đóng an toàn fail-closed khi thiếu căn cứ tác động, quyền phủ quyết của dữ kiện sai bắt buộc (known-false veto), tính không ảnh hưởng của dữ kiện sai không liên quan, và phân vùng dữ kiện thiếu (unknown gating).

- **Cam kết quản trị:**
  - Hai bảng chấm điểm của con người (`seamless_rater_1.json`, `seamless_rater_2.json`) được bảo lưu nguyên vẹn ở trạng thái pending với toàn bộ giá trị rỗng/null.
  - Bộ tham số phục vụ kiểm chứng giao diện và thuật toán, không tự nhận là kết quả đồng thuận của con người và không claim hiệu chuẩn thực nghiệm sản phẩm.

### 5.9. Bản ghi phê duyệt chính thức của TTS B (Gate 6: Formal Review & Approval Record #5387665338)

Tại PR #165, Reviewer TTS B (@nairyuuu) đã tiến hành rà soát kỹ thuật và ban hành phê duyệt chính thức (Formal Approval) tại review [#5387665338](https://github.com/nairyuuu/ad-weighted-graph/pull/165#pullrequestreview-5387665338) trên exact head `dd662f56609d718b264747a5fec70894ae9d4845`.
PR #165 đã được hợp nhất thành công vào nhánh `develop` tại commit `fdf59285f5af095733b816cc0e76400471b00c4f`.

Các kết luận kỹ thuật chính từ phê duyệt của TTS B:
1. **Hợp đồng khoảng xác suất:**
   Hàm `verify_parameter_bundle()` trong `scripts/research/seamless_parameter_validation.py` đã được hiệu chỉnh hoàn toàn khớp với hợp đồng canonical engine `0 <= lower <= upper <= 1`.
   Hệ thống tiếp nhận chính xác các xác suất cận hợp lệ như `["1/1", "1/1"]` và `["0/1", "0/1"]` kèm kiểm thử hồi quy đầy đủ.
2. **Tính đóng của gói tham số 1.0.0:**
   Gói tham số Scoped Parameter Bundle 1.0.0 đã khóa chặt số lượng và tập bản ghi chuẩn tắc (đúng 9 đơn vị công việc, 11 câu hỏi tiền tố có điều kiện, 12 hành động ràng buộc, 26 giả thiết runtime theo phạm vi Source A/B, và 3 ứng viên hợp lệ).
   Kiểm thử hồi quy xác nhận việc bổ sung bản ghi ngoại lai chưa kiểm chứng sẽ bị từ chối an toàn fail-closed qua cả API và CLI.
3. **Kiểm chứng CI:**
   Toàn bộ quy trình kiểm thử tự động trên GitHub Actions (Ubuntu, Windows, quality, Compose) đều đạt trạng thái xanh (green).
4. **Phạm vi và ranh giới phê duyệt:**
   Phê duyệt áp dụng cụ thể cho phạm vi PR #165 (Scoped Parameter Bundle 1.0.0, Interface 1.0.0 quy chuẩn, ADR-0013 accepted trong scope, và hồ sơ disposition).
   Hai phiếu chấm điểm của con người (`seamless_rater_1.json`, `seamless_rater_2.json`) và các cổng tích hợp/nghiệm thu còn lại của #143/#158 tiếp tục tách biệt và không được suy diễn là đã hoàn tất bởi phê duyệt này.



## Checkpoint tooling reviewed release #171 - 2026-10-02

[PR #170](https://github.com/nairyuuu/ad-weighted-graph/pull/170) đã merge công cụ đối soát tại `12a221fb401d9ce0a38e008168dc0b62f116792d`.
[Hướng dẫn reviewed release](reviewed-parameter-release-guide.md) bổ sung contract cho source ratings -> report replay -> explicit decisions -> separate versioned release -> validation/sensitivity -> canonical projections.
Research bundle và verifier/oracles cố định vẫn giữ nguyên; hai actual sheets vẫn pending.
Synthetic E2E với số khác research baseline chỉ kiểm chứng implementation và mapping, không tạo actual human ratings/acceptance.
Contract/tooling #171 đang đưa B review; implementation approval không tự nâng parameter acceptance, SEAMLESS verdict, Week 3 hoặc đóng #143/#158/#48.
Final numerical acceptance và integrated develop reproduction tiếp tục cần evidence/decisions thật đúng phạm vi.

## Checkpoint source review có AI hỗ trợ và exporter extension - 2026-10-02

[PR #173](https://github.com/nairyuuu/ad-weighted-graph/pull/173) đã merge tại `96fc89acc0859dd29fc17cdde57466fd8a263a01`; [packet hiện tại](ratings/week3-2026-10-02/README.md) có hai bộ đủ 21 ratings với shared execution policy và xác nhận nguồn được tiếp nhận.
Nguồn là `human_reviewed_ai_assisted_ratings`: B confirmation được A chuyển đạt, có prior exposure/AI assistance; không coi đây là hai bộ blind independent ratings hoặc bằng chứng independent reliability.
Hai fixtures pending/research baseline cũ vẫn bất biến; checkpoint historical ở trên không bị viết lại thành acceptance mới.
[PR #172](https://github.com/nairyuuu/ad-weighted-graph/pull/172) mở rộng exporter/replay theo [contract](reviewed-parameter-release-guide.md), giữ confirmation/policy/B AI archive bằng raw snapshots và digests; implementation extension cần review/CI trên head mới.
B approval của implementation tại `b779916` không tự bao gồm extension này.
21 proposals của reconciler vẫn là proposals; chưa có 21 final dispositions thật được phê duyệt, versioned actual release, numerical acceptance hoặc integrated Week 3 acceptance từ lượt này.
Tests dùng dispositions test-only để đi hết export/replay/engine/sensitivity; không ghi chúng thành quyết định của A/B, không nâng SEAMLESS verdict hoặc tự đóng #143/#158/#48.

## Cập nhật actual release và requirement independence — 2026-10-03

[Hồ sơ closeout](ratings/week3-closeout/README.md) đã có 21 lựa chọn thật của A, actual reviewed release và validation/sensitivity passed trên ba ứng viên. Source basis vẫn human-reviewed AI-assisted, B xác nhận qua A và có exposure; không có independent inter-rater reliability evidence.

[Disposition cơ sở tham số](week3-rating-requirement-disposition.md) ghi chấp thuận của chủ dự án dùng bộ nhận định hiện tại thay yêu cầu bổ sung chấm độc lập trong phạm vi kịch bản Week 3. Review theo workflow PR; source acceptance và lựa chọn tham số trước đó không được dùng làm quyết định thay yêu cầu; không nâng Week 3/SEAMLESS integrated verdict hoặc sửa research fixtures từ cập nhật này. Các đoạn pending/tooling ở trên là checkpoint lịch sử theo ngày, không phủ nhận actual export mới.
