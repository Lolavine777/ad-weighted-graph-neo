# Iteration 6 — scenario discovery và remediation nhiều context

## Thay đổi sản phẩm

`scripts.exposure --evaluation-mode scenario --scenario-policy seamless-standard-v1` nay gọi **scenario compiler đã tồn tại**, thay cho assumptions JSON viết tay. Evidence-only vẫn mặc định; không bật ngầm giả định. Native code được thực thi sạch tại **`9ce0703388fde6332816708289a5db0d6c47fdc8`**, parent `4dabde62223d9aeedb67fc9e4ba1ba3380058284`. Report/acceptance được append ở descendant; main/develop không đổi. [Machine evidence](evidence/iteration-6-policy.json) pin source bytes, raw, snapshot, từng capture và omissions.

| Boundary | Hành vi được kiểm |
| --- | --- |
| Query | Reuse `apply_policy_to_query`; compile riêng từng source/context/goal. Snapshot và evaluation mode phải khớp profile. |
| API/CLI | `run_source_goal_batch(..., scenario_policy=...)` dùng existing loader; CLI chỉ mở standard profile. Không chép semantic rules sang engine mới. |
| Provenance | Canonical profile + digest trong inputs; assumptions/rejections trong từng public query; worker và remediation giữ nguyên query/audit. |
| Checkpoint | Pin resolved contents, không chỉ tên/path. Alias cùng profile reuse được; đổi nội dung hoặc bỏ profile bị từ chối. Cell scenario identity cũng chứa profile digest; không chuyển numeric authority sang scope mới. |
| False/credential | Observed False chặn policy True. Standard profile không tự cấp control, usable identity hoặc recovery_success. Initial usable identity vẫn là giả thiết compromise khai báo riêng. |

**Verified — composition defect đã sửa:** inventory cũ có thể sinh runtime edit theo context của một witness dù cùng fact key hiện diện ở context khác trong baseline. Executor sau đó từ chối `runtime authentication context mismatch`; không phải invalid witness đã được chấp nhận. Khâu sinh candidate nay reuse `_check_edits` trên toàn baseline; refusal còn nguyên dưới dạng `unsupported`. Verifier và overlay guard không đổi. Regression cố ép proposal vẫn bị từ chối. Full-snapshot cohort dưới đây tái hiện một proposal như vậy trong bảy candidates.

## Thực thi trên nguyên SEAMLESS

Sáu raw files khớp manifest. Snapshot **3.370 nodes / 56.367 edges**, SHA-256 `73f4380f938bf70338661c487e3c6467c4b012be1519995f4419a1143a45a9a8`. Bốn lượt tuần tự, cùng source pins, User/context, 12 auto important goals, hai techniques; caps 5 paths / 4 steps / 100 expansions mỗi query, không wall deadline. [Exact harness](evidence/policy-discovery-experiment.txt), [một compiled query đầy đủ](evidence/iteration-6-compiled-query.json).

| Cấu hình | Kết quả | Assumptions | CLI elapsed |
| --- | --- | --- | ---: |
| Evidence-only | 12 indeterminate, không witness | 0 | 9,218s |
| Standard tự động | 3 truncated-success, 9 truncated-incomplete | 85 unique keys; 27–49/query | 16,656s |
| Bốn assumptions thủ công cũ | 2 complete-success, 10 truncated-incomplete | 4 unique keys | 10,555s |
| Standard + injected admin-channel=False | 2 truncated-success, 10 truncated-incomplete | 84 unique keys | 16,608s |

Đây là **sensitivity theo giả định**, không phải speedup hoặc ground-truth attack success. Một lượt/cấu hình không cho statistical inference. Cả bốn đều C/P unrated, không dùng hop count, midpoint hoặc P=1. False được bơm vào làm negative control, **không phải observation thu từ SEAMLESS**; provenance ghi rõ điều đó.

Nguồn là `DENA_WILLIAM`, SID `...-2799`, usable identity khai báo tại DC `...-1000`. User này **vốn có direct membership DA trong snapshot**. Standard tìm DC-admin, DA entitlement và thêm Administrators entitlement qua hai bước membership. Hai goal đầu dừng do path limit, goal thứ ba do expansion limit. Vì vậy không chứng minh ordinary-user escalation, completeness hoặc minimum C. False control loại witness DC, giữ hai Group witnesses.

## Nhiều nguồn–nhiều đích và counterfactual

Chọn độc lập DENA, `GINO_ROSS` (`...-1103`) và Computer `SECWSECS1000000` (`...-4089`), tự sinh cùng 12 goals. User usable tại DC; Computer admin tại chính host đó, không ngầm có User credentials. Không cộng capabilities giữa nguồn.

| Nguồn | 12 goals |
| --- | --- |
| DENA | 3 truncated-success, 9 truncated-incomplete |
| GINO | 12 truncated-incomplete |
| Computer | 12 indeterminate |

**36/36 selected cells executed**, 31.044 inventory pairs ngoài cohort. Khác profile/scope với historical 1.600 cells, không cộng thành domain coverage. Batch search/audit 30,014s; graph load 2,777s; inventory 1,392s; request 0,531s; serialization 0,162s. Hai techniques chưa phải all-catalog.

Remediation trên **3 sources × 1 DC goal**, 33 discovery cells ngoài cohort can thiệp. Inventory 7 candidates, một admin-channel proposal unsupported do mixed context; thử một candidate hợp lệ qua native executor và independent verifier. **4/5 observed programs cut (80%), 0 proven disconnected pairs; DENA vẫn reachable bằng bypass**, hai nguồn khác Unknown. Remediation/verification 110,449s. Không suy domain risk reduction 80%, domain safe hoặc intervention tối ưu; defender cost và operational impact chưa chấm.

## Bottleneck đã đo

Lượt `cProfile` riêng: full snapshot, discovery 1 User × 3 goals, rồi 1 candidate trên 1 User × 1 goal. Instrumented total ~120,718s; không so trực tiếp với unprofiled latency.

| Hàm/stage | Calls | Cumulative seconds |
| --- | ---: | ---: |
| `evaluate_interventions`, gồm verifier | 1 | 101,522 |
| `canonical_value` | recursive | 53,603 |
| `deepcopy` | recursive | 47,602 |
| `verify_package` | 1 | 29,546 |
| `EngineGraph.to_canonical` | 25 | 29,241 |
| `generate_attack_paths` | 12 | 4,557 |
| `apply_policy_to_query` | 3 | 3,855 |
| Policy `_extract_nodes_and_edges` | 3 | 3,609 |

**Cumulative times chồng lấn, không cộng các hàng.** Batch phase 9,820s; remediation phase 101,524s. Không có applicable numeric ratings trong workload này, nên chưa đo heavy numeric ranking cost. **Strong inference:** giảm copy/hash/materialization có cơ sở hơn thay search engine ở đây. Chưa có optimized after-run mới; iteration này không claim performance improvement. Call records/source/package hashes ở machine evidence.

## Kiểm chứng và đối chiếu đề bài

- **261 selected PASS/1 raw opt-in skip**; sau đó bật flag đúng raw inputs, **1/1 raw replay PASS**. **43 discovery/remediation PASS**, gồm ten new boundary checks. Suites overlap, không cộng thành whole-suite total. Hai lỗi keyword của test harness chỉ sửa trong test; một lỗi inventory composition sửa ở production. First-attempt hashes được giữ.
- Clean native Week4 twice: **36 PASS / 2 NOT EXECUTED / 0 FAIL**, semantic digest `e4f9a3f1779753650a45dbf4c671c8cf68363e100c4a9bc861850a0cb2cbbbec`, đúng frozen v3 sau existing environment normalization. Append v8, giữ v7/v6/v5, không đổi oracle. **Final 55/55 PASS, 58,66s** trên clean `bc2c0f3a6abdb25e6db1de4c4e036b196b660870`: ba Week4 modules, policy boundary, binding/reuse và source-history checks. Native source pins vẫn đúng captured run; [closeout/JUnit](evidence/iteration-6-closeout.json). Counts overlap các suites trước, không whole-suite claim.
- Independent finite expectations kiểm Alice/Bob, False veto, source/context isolation, leaked material không thành identity, worker/query replay parity, exact profile checkpoint binding, executable CLI resume và refused intervention.
- **“Một máy bị chiếm đi tới đâu”**: workflow/typed outcomes đã có; broad Computer lateral movement chưa được dataset chứng minh. Raw chỉ một host có nonempty LocalAdmins, không Sessions; FCP/HasSession typed composition và fresh BloodHound comparator còn open.
- **“Chi phí thấp nhất”**: union-work foundation/oracle cũ giữ nguyên; generated goals vẫn thiếu applicable **C-only basis**, nên lượt này chưa trả được minimum cost. Không chuyển P/I authority của goal cũ sang goal mới.
- **“Choke point”**: đã tự mine/thử can thiệp, có actual bypass; chưa giải global cost-constrained intervention optimization. Path cuts khác source–goal disconnection.

## Quyết định và backlog

**Giữ planner, đơn giản hóa workflow; chưa triển khai production AND–OR discovery.** Với đúng hai techniques trong demo này, conditional graph/BFS có cùng gates cũng có thể tìm witness một–hai bước; 3/12 không chứng minh lợi thế search. Fixed-weight Dijkstra phù hợp nếu C additive/context independent. Shared work, accumulated RBCD prerequisites và identity switching cần semantics đúng trước khi so cost. F1 oracle cũ vẫn là căn cứ, không phải fresh head-to-head trên snapshot này. Không biết implementation riêng của mentor và không giả định BloodHound chỉ có BFS.

1. **P0 sản phẩm:** C-only applicability trên một verified generated-goal witness bằng existing resolver và independent union-work oracle. Giữ owner/context/snapshot/work-unit pins, không tự adoption P/I. Không bind được thì giữ “chưa chấm”, không công bố minimum.
2. **P1 hiệu năng:** paired same-input experiment ở immutable graph/facts fingerprint hoặc compiler extraction. Full decisions/provenance/Unknown phải parity, R1/R2/R3 negatives phải pass. Dừng nếu gain không đáng kể; không bỏ verifier để tăng speed.
3. **P1 coverage:** Computer capability profiles theo evidence/explicit declarations; ghi rõ unsupported FCP/HasSession và data gaps. Mở cohort có mục đích, không quét hàng chục nghìn Unknown để tăng count.
4. **P2:** chỉ pilot shared discovery/AND–OR nếu measured search/grounding thành bottleneck và finite oracle vẫn đúng shared cost/actors. Chưa xây engine/rule system/policy framework thứ hai hoặc UI framework.

Reproduce: dùng command README và thêm hai flags profile ở trên. Sensitivity harness nhận `--repo . --output-base NEW_DIRECTORY`. Full captures lớn còn local và được hash; projection công bố omissions, không giả là full decision package. Historical R03 ZIP vẫn chưa materialize, link check còn gap đó.
