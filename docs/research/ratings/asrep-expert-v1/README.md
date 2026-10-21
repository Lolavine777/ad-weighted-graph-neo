# #264 Phase 1 - đề xuất P cho AS-REP

Owner: TTS A / @Lolavine777 / Nguyễn Đăng Long.
Reviewer cần nhận numeric/context: TTS B / @nairyuuu.
Trạng thái: `proposed_pending_b_review`; chưa có B adoption hoặc lượt elicitation chuyên gia mới hoàn tất.
Đây là đề xuất có AI hỗ trợ, nhãn `estimated_expert_scenario`, không phải xác suất thực nghiệm.

## Phạm vi và quyết định

Đã đối chiếu [#264](https://github.com/nairyuuu/ad-weighted-graph/issues/264), [#259](https://github.com/nairyuuu/ad-weighted-graph/issues/259), [#265](https://github.com/nairyuuu/ad-weighted-graph/issues/265) và develop `da21fbb545061c56c6dfff6ac489e7794a53ec73`.
[Closure Week 4](../../../reports/week4-maintainer-closure-2026-10-11.md) giữ C=3, High và P=0/4 cho frozen #243; Source A giữ 2/24 P-complete trong historical-transfer review-gate scope.
Không sửa báo cáo, release, registry hoặc oracle đã freeze.

[Proposal](proposal.json) thêm scenario `week5-seamless-asrep-uniform24-v1`, basis `asrep-expert-v1`, version 1.0.0.
Scenario dùng cùng manifest-verified graph, locator X/V_A/C0, initial request capability và tám runtime declarations của frozen case, nhưng đổi method, budget, population, horizon và policy của câu hỏi numeric.
Không claim mật khẩu thật V_A có population được chọn.
Đây là một counterfactual cụ thể để B review tính hữu dụng và applicability, chưa giải quyết xác suất cho mật khẩu tự nhiên chưa biết phân bố.

Consumer chỉ tạo native registry bằng công thức work identity từ event inventory, rồi gửi declarative query vào public generator.
Không lấy keys từ engine output, không nhận ordered candidate path, không tạo ranking packet theo từng path và không thay search/provider/query/UI implementation.
Các prefix là bản ghi conditional basis cho scenario/context; candidate được engine tự sinh.
Phase 2 mới mở rộng lớp context và nhiều chương trình khác nhau, không suy broad coverage từ một chain này.

## Câu hỏi điều kiện và interval đề xuất

Mọi q_i là xác suất hoàn tất event trong policy của nó trước khi outcome được hiện thực hóa, điều kiện trên F/S, actor/target/context và toàn bộ E_1..E_(i-1) đã thành công.
Runtime outcome declarations cho phép generator dựng prediction; chúng không được đưa vào numeric câu hỏi như bằng chứng E_i đã chắc chắn xảy ra.
Known FALSE luôn veto, còn unknown thiếu declaration vẫn indeterminate.
Passive closure không tạo q.

| Event | Actor / source / target | Full ordered successful history | Method | Interval đề xuất |
| --- | --- | --- | --- | --- |
| E1 `asrep_request` | X / X / V_A | [] | `ASRepTarget` | [3/4, 49/50] |
| E2 `recover_asrep_secret` | X / X / V_A | [E1] | `offline-asrep-etype23-uniform24-enumeration-v1` | [1/32, 1/16] |
| E3 `activate_recovered_identity` | V_A / V_A / X | [E1,E2] | `RecoveredSecret` | [3/4, 49/50] |
| E4 `obtain_admin_execution_on_host` | V_A / V_A / C0 | [E1,E2,E3] | `AdminTo` | [1/2, 9/10] |

Authentication context là X ở cả bốn event.
E1 tạo encrypted material, E2 mới tạo recovered password, E3 mới tạo usable identity, E4 mới đạt typed `admin_control(C0)`; DA checkpoint vẫn false.
Snapshot, foothold, actor/source/target, method, recovery-resource digest, policy, horizon, active-work budget và exact ordered canonical identities đều phải match.
`source-records.json` pin câu hỏi gốc và digest từng source record; acceptance của source không tự chấp thuận history mới.

E1 đề xuất dùng cùng operational envelope với câu hỏi lịch sử `cand_seamless_01_direct_lidia:q2`, không coi AS-REP material request là outcome acquire-ticket lịch sử.
Giả thuyết chuyển giao cần B chấp thuận riêng: sau reachability và preauth/format compatibility được conditioning, residual request/response/parser failures nằm trong envelope này.
E3 đề xuất cùng interval lịch sử cho recovered-secret authentication, với password/account policy còn hợp lệ trong 24h.
Secret age, recovery lineage và history khác reset đều được khai báo như thay đổi, không bỏ khỏi key.
E4 đề xuất interval từ `cand_seamless_01_direct_lidia:q3` cho authenticated WinRM administration trên cùng DC và typed consequence.
WinRM là policy scenario bổ sung; semantic method của generator vẫn `AdminTo`, raw không chứng minh transport.
Không reuse cho generic transport chưa xác định, RDP/session, membership checkpoint hoặc asset khác.

Ba interval vận hành là các hypothesis chuyển giao expert scenario đã có, không phải ba số đo mới hoặc monotonicity theorem.
B cần quyết định cả residual-failure envelope và từng full-history applicability.
Không tính lại failed prior events, reachability, secret-validity policy hoặc effective permission đã nằm trong conditioning.
Nếu B không bảo vệ được một transfer, giữ prefix đó unrated theo blocker cụ thể trong proposal, thay vì tìm một tỷ lệ trông hợp lý.

## Recovery method, compute và stop

Population scenario: mật khẩu `Aa0!` cộng sáu ký tự hex thường, chọn đều từ 2^24 khả năng, conditional on E1 và context đã khai báo.
Một worker kiểm AS-REP etype23 theo thứ tự lexicographic `000000` tới `ffffff`, không lặp, không đổi dictionary thích nghi, không dùng password cá nhân hoặc actual secret bytes.
No-match compute coverage trong 20h nằm trong [2^19,2^20] distinct completed verifications, độc lập với secret rank conditional on E1.
Compute floor gồm format compatibility, verifier correctness và overhead; không có guaranteed floor thì không bảo vệ được positive lower bound này.
Không claim loại GPU, hash rate benchmark hoặc AS-REP etype đã được đo ở SEAMLESS.

Với N=2^24 và G trong [2^19,2^20], q2 nằm trong [G_min/N,G_max/N]=[1/32,1/16].
Đây là finite-model arithmetic dưới một population assumption mạnh, không phải phép đổi “budget lớn” thành cracking percentage cho human passwords.
Dừng ở match đã kiểm chứng, 20h, compute cap hoặc authoritative denial; chỉ một job, không reset budget/restart.
Coverage G được định nghĩa theo counterfactual no-match schedule để early-stop khi match không làm sai mẫu số.

Campaign horizon 24h.
E1 và E3 mỗi event tối đa ba attempts trong 10 phút; E4 tối đa ba attempts trong 30 phút; deadline tính từ attempt đầu và vẫn bị campaign deadline chặn.
Tổng deadline tuần tự tối đa 20h50 phút, không giả định retry independence hoặc nhân thành `1-(1-q)^3`.
Engine không chạy cracking, retry hay thời gian thật; nó consume interval đã conditional trên policy.

## Oracle và public verification

[Oracle độc lập](oracle.json) được commit trước flow mới ở `027c2f8`; các cận và products giữ nguyên sau review engineering.
Amendment sau đó chỉ sửa hai tên canonical class cho đúng catalog và thêm provenance/validation, không chọn lại số theo engine output.

P_path lower = 3/4 * 1/32 * 3/4 * 1/2 = 9/1024.
P_path upper = 49/50 * 1/16 * 49/50 * 9/10 = 21609/400000.
Không cần independence giữa E_i vì mỗi factor có full successful-history conditioning.
Nếu chỉ có compute cap bằng floor, upper tương ứng là 21609/800000; đây là arithmetic sensitivity, chưa là run policy variant được chấp thuận.
Thiếu bất kỳ q nào làm P_path=null, không nhân phần còn lại rồi gọi là P toàn đường.
C rubric đề xuất giữ [0,2,0,1], total 3; I đề xuất giữ High trên cùng exact typed terminal asset.
C/I numbers không đổi, nhưng applicability trong scenario/work identity mới cũng cần review; không mượn authorization Week 4 để tự activate.

```sh
.venv/bin/python -m scripts.research.asrep_expert_basis --raw-dir data/raw/SEAMLESS --output reports/generated/issue264/verification.json
.venv/bin/python -m pytest -q tests/test_asrep_expert_basis.py tests/test_rating_p_provider_chain.py tests/test_week4_maintainer_disposition.py tests/test_likelihood_catalog_v1.py
```

Ở worktree có thể dùng Python tuyệt đối của `.venv` repo chính.
Full IDs/query/process outputs và derivative graph giữ trong ignored local output; chỉ sanitized report được publish.
Consumer kiểm proposal/oracle/source/tests khớp HEAD trước chạy, pin file hashes, hai CLI processes, API và orchestration.
Raw graph và frozen baseline giữ bất biến.

Gói pending thực có 0/4 P; không coi nó tăng coverage đã chấp thuận.
Engineering gate copy chỉ dùng `synthetic_test_only`, graph derivative được đánh dấu synthetic với graph digest riêng và rebind static facts cho view đó.
Graph gốc không bị sửa; production policy từ chối synthetic numeric records.
Kết quả 4/4 và một Pareto member trên derivative chỉ chứng minh wiring, arithmetic và refusal, không phải B review, raw numeric acceptance hoặc Phase 2 risk comparison.


Kết quả thực tại execution `b2adb73` nằm trong [sanitized evidence](../../../../reports/research/issue264-asrep-expert-v1-verification.json).
Mẫu số giữ nguyên một valid và một conditioned-feasible generated program; không bỏ path để tăng tỷ lệ.

| Mode | Valid / conditioned-feasible | C-rated paths | P-rated paths | I-rated paths | Fully rated / Pareto eligible | P events |
| --- | --- | --- | --- | --- | --- | --- |
| Frozen Week 4 raw baseline | 1 / 1 | 1 | 0 | 1 | 0 / 0 | 0/4 |
| Scenario mới, raw, records pending | 1 / 1 | 0 | 0 | 0 | 0 / 0 | 0/4 |
| Synthetic engineering gate copy | 1 / 1 | 1 | 1 | 1 | 1 / 1 | 4/4 |

C/I của scenario mới cũng pending vì work identities và applicability đổi, không phải thay C=3/High đã nhận ở Week 4.
Coverage thực được chấp thuận chưa tăng; dòng 4/4 là prospective wiring evidence được quarantine rõ.
Public controls giữ raw/missing-recovery indeterminate, known-false/missing-request blocked, extension-off no_path và step-cap truncated.

## Nguồn và blockers

[MS-KILE](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/ae60c948-fda8-45c2-b1d1-a71b484dd1f7) hỗ trợ mechanics của AS exchange/password authentication, không cho q numeric.
[Hashcat format reference](https://hashcat.net/wiki/doku.php?id=example_hashes) hỗ trợ etype23 AS-REP verifier/mode, không cho password distribution hoặc throughput.
[PointerGuess research](https://www.usenix.org/conference/usenixsecurity24/presentation/xiu) phân biệt populations/side information; không chuyển số của paper vào SEAMLESS.
Các nguồn được đọc ngày 12/10/2026; numeric operational source là historical AI-assisted human-adopted scenario judgment với giới hạn provenance đã ghi, không phải tài liệu giao thức.

Đối với frozen recovery gốc `unmeasured-budget` / `fixed-snapshot-window`, blocker vẫn là password rank/population, etype compatibility và completed verifier budget/horizon không được xác định.
Đối với scenario mới, blocker adoption là B review population/compute commitment, ba transfer hypotheses và exact full-history/C/I scope.
Nếu mất floor, sai population/etype, policy/horizon hoặc auth/resource context, không reuse q2.
Prototype empirical fixture không được thay các basis này; reuse quarantine test hiện có của #248/#238.

## B handoff

B review từng event interval và applicability, ghi actual reviewer/decision/reference khi adopt; không biến checkbox PR hoặc implementation approval thành numeric acceptance.
Nếu request/activation/admin transfer không được nhận, trả lại blocker cụ thể đã nêu; chưa có bound cho natural-password scenario thì giữ gap đó.
B-owned delta cần cho public consumer: giữ nguyên native basis category tương thích và xuất thêm `numeric_basis_class=estimated_expert_scenario` cùng actual review status/reference qua coverage, API/CLI/orchestration.
Hiện native output chỉ có `scenario_assumption`; research summary gắn nhãn riêng nhưng không claim label này đã sống qua product schema.
Việc ingest/adopt và product provenance field thuộc B, không implement trong PR A này.

Không close #264 hoặc claim broad product coverage: Phase 2 vẫn cần Source A/multi-path, sensitivity, generated denominators và ít nhất hai chương trình fully rated khác nhau khi có defensible basis.
