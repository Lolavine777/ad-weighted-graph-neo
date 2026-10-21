# Iteration 10 — ranh giới Computer foothold và danh tính domain

**Đã sửa một false positive thực tế: shell thường trên máy không đủ để dùng ACL của tài khoản máy.** Native implementation/captures sạch tại `3480f745fb664415f1c414586696e841be415026`, parent iteration9 `055f2d68fc13e589446cb2c7ffb119b9723a5a0f`. [Machine evidence](evidence/iteration-10-computer.json) chứa exact inputs, before/after revisions, raw/native hashes, proof flags và witness requests. Không sửa planner, cost, catalog, binding hoặc numeric basis.

## Lỗi nào đã được xác nhận

**Verified:** `computer_control_user` chỉ khai báo host control/command execution, không có `usable_identity`. Trước đây evaluator chấp nhận `actor_controlled` và `source_authorized` chỉ vì Computer là actor/source. Với GenericAll của machine principal, nó vẫn reset User khác, activate User đó rồi đạt DA. Khai báo machine identity ở context khác cũng không ngăn được đường này. Đây là lỗi composition giữa profile và evaluator; không phải thiếu một heuristic tìm kiếm.

Sửa nhỏ trong `src/engine/semantics/evaluator.py`: Computer actor dùng techniques có `source_authorized` phải có `(Computer, authentication_context)` trong `usable_identity`. Thiếu context hoặc có `authentication_unknown` đúng scope giữ indeterminate. Runtime fact mang tên giống gate không tạo capability; danh tính ở context khác không dùng được. Gate technical mới xuất hiện trong decisions/replay. User semantics và HasSession host-admin gates giữ nguyên.

**Lựa chọn contract, không phải một khẳng định AD:** profile hiện gộp local administrator/SYSTEM, chưa tách machine network identity. Bản sửa yêu cầu khai báo capability riêng cả cho profile đó. [Microsoft mô tả LocalSystem có thể trình computer credentials cho remote server](https://learn.microsoft.com/en-us/windows/win32/services/localsystem-account); [LocalService dùng anonymous credentials trên network](https://learn.microsoft.com/en-us/windows/win32/services/localservice-account). Vì vậy không thể bảo vệ kết luận “SYSTEM không dùng được machine account”. Cách dùng hiện tại: nếu scenario đã xác nhận machine identity, khai báo nó riêng trong public query. Chưa tự suy credential hoặc grant một domain User.

## 12 ca Computer mới, oracle độc lập

Đây là 12 ca chuyên biệt mới, **không phải** matrix F1 lịch sử. Oracle closure ba action với AND prerequisites dùng các atom riêng cho network identity, ACL, reset control, usable User và entitlement. Nó không gọi AWG candidate/evaluator/AttackState/cost. Chạy closure với definite facts và thêm possible Unknown facts để phân biệt blocked/indeterminate. Đây là oracle contract hữu hạn, không phải đo accuracy trên AD thật.

| Ca | Oracle | Trước | Sau |
| --- | --- | --- | --- |
| Local shell, không network identity | blocked | success | blocked |
| Local admin, chưa khai báo network identity | blocked theo contract | success | blocked |
| Machine identity đúng context | success | success | success |
| Machine identity ở context khác | blocked | success | blocked |
| Machine identity Unknown | indeterminate | success | indeterminate |
| Thiếu authentication context | indeterminate | no_path | indeterminate |
| RPC False, identity hợp lệ | blocked | blocked | blocked |
| RPC Unknown, identity hợp lệ | indeterminate | indeterminate | indeterminate |
| Target disabled, assumption enabled=True | blocked | blocked | blocked |
| Runtime fact giả lập identity gate=True | blocked | success | blocked |
| Unknown identity chỉ ở context khác | blocked | success | blocked |
| User khác đã có usable identity, chuyển actor | success | success | success |

Baseline clean `668bf5f`: **5/12 khớp**, evaluator bytes bằng iteration9 `055f2d6`. After clean `3480f74`: **12/12 khớp**, cùng case-module SHA/query/graph. Không gọi bảy khác biệt là bảy bug độc lập: local-admin và missing-context có phần là lựa chọn contract bảo thủ. Native witness positive vẫn reset→activate→membership, actor chuyển đúng owner, replay pass. C/P/I không chấm trong thí nghiệm này.

Ba test riêng giữ HasSession: có host-admin và đủ ba gates mới sinh `credential_material`; shell thường không sinh, gates thiếu giữ Unknown. Material này chưa phải typed password, không tự activate hoặc thỏa DA goal. Đây vẫn là **unsupported composition**, không được trình bày là hệ thống thực tế không thể tiến tiếp.

## Tái hiện trên full public SEAMLESS

Sáu raw files được hash-check với manifest cũ; snapshot vẫn 3.370 nodes/56.367 edges. Source Computer `FINWVIR1000001` (`...-4157`), User DENA (`...-2799`), DA (`...-512`). Independent stdlib lookup đọc đúng raw User ACE `PrincipalSID=...4157, RightName=GenericAll, IsInherited=True` và DA `Members[].MemberId=...2799`, không gọi parser/generator làm oracle. Provenance thời gian vẫn assumed theo filename, không đổi thành observed.

Cùng **bảy runtime assumptions**, ba techniques, max1path/3steps/10.000exp; chỉ đổi declared capability. Đây là một source–goal pair với ba declarations, không phải sáu pairs từ hai revisions.

| Declaration | Trước | Sau |
| --- | --- | --- |
| Local shell | witness/4.996exp, truncated | blocked/2.494exp, exhaustive trong scope |
| Local admin chưa khai báo machine identity | witness/4.996exp, truncated | blocked/2.494exp, exhaustive trong scope |
| Machine usable identity đúng context | witness/4.996exp, truncated | cùng witness/4.996exp, truncated |

Positive requests, before states và effects bằng nhau trước/sau; technical guard decisions mới khác có chủ đích. Public CLI adapter và API candidates bằng nhau, một native replay pass. Positive vẫn `minimum_proven=False`, `path_limit_reached`, C/P/I unrated. Negative `is_no_path_proven_over_scope=True` chỉ trong initial capabilities, ba techniques và budgets đã khai báo. Không chứng minh physical safety, không giảm exposure hay tăng performance; ít expansions ở ca bị chặn là thay đổi semantics đúng, không phải benchmark speedup.

Full audits/local first attempts giữ nguyên và được hash-pin; public evidence khai báo projection bỏ verbose path lineage/failed attempts. First raw runner dùng nhầm key `search` của CLI adapter, đã sửa harness và chạy v2; partial capture giữ riêng, không dùng làm baseline chính.

## Đối chiếu đề bài và architecture

| Yêu cầu gốc | Kết quả hiện tại | Gap còn lại |
| --- | --- | --- |
| Máy bị chiếm → DA | Native fullraw witness khi machine identity được khai báo; local-only false positive bị chặn | Profile local admin/SYSTEM/machine identity chưa được tách ở discovery CLI |
| Chi phí thấp nhất | User reset/activation C-only ở iteration7 vẫn giữ; lần này không có basis cho Computer | Không transfer C/P/I sang machine work; không global optimum khi truncated |
| Choke point | Replay/rediscovery và pair-reduction riêng với path cuts đã có | Chưa có số remediation/reachability mới ở iteration10 |
| So sánh BloodHound | Structural/raw evidence và các comparator cũ được giữ | Fresh BloodHound CE run vẫn chưa có; không đoán approach mentor |

**Giữ planner, sửa semantic boundary trước khi mở rộng discovery.** BFS/hop hoặc Dijkstra trên structural chain Computer→User→DA cũng sẽ thấy cạnh; tự chúng không kiểm chứng network identity/activation gates. Conditional/AND–OR có thể biểu diễn đúng ba actions này nếu giữ các prerequisites riêng. Thí nghiệm không chứng minh cần full planner cho mọi query, nhưng cũng không chỉ ra bottleneck bắt buộc production AND–OR; lỗi nằm ở capability contract, không ở thứ tự traversal. Không viết một engine thứ hai chỉ để lặp lại catalog.

## Validation và tái hiện

- **217 selected PASS/8,60s**: 18 boundary/CLI/session checks cùng native engine/transitions, identity goals, exposure, batch/worker/resume, R1/R2/R3 và source authority. Overlap với248checks iteration9; không whole-suite claim. Positive Computer membership fixture cũ nay khai báo identity/context rõ ràng, expected closure không đổi.
- Clean Week4 hai lần **36PASS/2NOT_EXECUTED/0FAIL**, frozen semantic digest không đổi `e4f9a3f1779753650a45dbf4c671c8cf68363e100c4a9bc861850a0cb2cbbbec`. Append [v12](../../../reports/research/week4-guided-exploration-acceptance-manifest-v12.json), SHA-256 `d7e0705fe2f67ea81ec846f1676ea52243eba132dc306cc37abaca9e2754aaf4`; giữv11. Likelihood source successor v12 ghi drift có chủ đích; scenario successor/numeric/history không đổi.
- Ruff579files/contractpass. Repository links vẫn đúng một gap historical R03ZIP. **Final clean `69f2093`: 425/425 PASS/121.81s**, zero skip; native/v12 pins khớp actual files. [Closeout/JUnit](evidence/iteration-10-closeout.json). Fresh executable fullraw CLI giữ entire underlying adapter package; bốn envelope fields về label/snapshot được xác minh riêng, gồm toàn7.479facts/provenance/giá trị. Mọi jobs complete, không pending. Closeout descendant chỉ docs/evidence, không thay native code.

Oracle executable: [harness](evidence/computer-oracle-harness.txt), chọn `--repo`, `--case-module tests/test_computer_foothold_boundary.py`, `--output` mới. Fullraw executable: [harness](evidence/computer-raw-harness.txt), thêm `--snapshot`, `--raw`, `--reference-query` là iteration7 public query, `--manifest` cũ; code không có AD/network operation. [Machine query](examples/computer-explicit_machine_identity.json) và [local-shell control](examples/computer-local_shell.json) là exact public inputs đã chạy. Bảy assumptions không phải observations; declarations không phải credentials thật.

**P0 tiếp theo:** pilot một profile machine identity tường minh cho exposure/batch, giữ local-shell/local-admin profiles, valid Computer context và provenance. Oracle/case này là acceptance; dừng nếu auto-grant User identity, sai context hoặc fixture không có evidence. Sau đó mới thử typed HasSession credential activation trên synthetic fixtures; raw có0Sessions nên không thể giả fullraw session coverage. Safe source/preparation reuse làP1; chưa production AND–OR, narrow P hoặc scan Unknown để tăng counts.
