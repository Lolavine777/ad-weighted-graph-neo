# AWG neo: baseline và hướng nghiên cứu

## Phạm vi

Neo là repo cá nhân có lịch sử mới, được dựng từ nội dung upstream `main` ngày 2026-10-21.
Rework và đơn giản hóa trong planner hiện hữu; không rewrite parser hoặc bỏ semantic checks.
Hai use case là một foothold tới tài sản quan trọng và nhiều compromises độc lập để khảo sát rủi ro, can thiệp, rồi tìm đường thay thế.

## Migration

- Source chỉ đọc: `https://github.com/nairyuuu/ad-weighted-graph`.
- Đích private: `https://github.com/Lolavine777/ad-weighted-graph-neo`.
- `main`: `49dfa2a78614220dfd092b0fd3e5c585992a0484`.
- `develop`: `ba3fcaa8f6d85c181d8a7f657eae112607fd22cb`.
- Cùng tree: `dde43cad3e8e91314bd5ecc4dc1194ac2295596a`.
- Clone upstream đầy đủ để kiểm tra; neo dùng root commit mới theo lựa chọn của chủ repo, không nhập các commit hoặc nhánh PR cũ.
- Không có LFS pointer hoặc submodule trong baseline.
- `upstream` trong checkout neo có push URL `disabled://upstream-read-only`; `remote.pushDefault=origin`.
- Neo được kiểm private và không có ref trước lần push đầu; các lần sau chỉ push fast-forward.

Tám file log evidence vốn được upstream track nhưng khớp `.gitignore` đã được đưa lại nguyên bytes vào commit tiếp theo root commit.
Không có thay đổi nào được ghi vào working tree hoặc push tới repo gốc.

Gitleaks 8.30.1 được tải từ release chính thức và kiểm checksum binary trước khi chạy.
134 cảnh báo ban đầu đã được kiểm tra: 129 source/file hashes, bốn định danh `host-access` có hash và một dòng văn bản về auth context.
Đó là false positives; không có credential thật được nhận diện trong snapshot chuyển sang neo.
Đây là kết quả quét snapshot hiện tại, không phải bảo đảm cho mọi dữ liệu hoặc thay đổi về sau.

## Dataset trên máy

Raw và derived outputs vẫn ở local, được ignore bởi Git theo quy ước dữ liệu hiện hữu.

| Dataset | Cách lấy và xác minh |
| --- | --- |
| SEAMLESS | Tải public archive tại commit pin trong `scripts/download_seamless.py`, xác minh archive SHA-256 và manifest sáu file |
| NORTH | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| NORTH_CE_PYTHON | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| ad_sampledata | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| telemetry | Sao chép CSV local và xác minh manifest `telemetry-raw-v1.json` |

Đã lấy 60 file, 23.577.814 bytes, không tính README.
`data/processed/neo-datasets.json` ghi checksum từng file và cách lấy trên máy migration.
Mọi file sao chép đều được so hash với bản nguồn.
Ba archive NORTH/NORTH_CE_PYTHON/ad_sampledata còn được so với hash công bố trong [data inventory](research/data-inventory.md).
Không khẳng định đã tải mới từ Internet các dataset được sao chép local.
Một clone neo mới chỉ tự tải được SEAMLESS bằng runner; các dataset phụ cần lấy từ kho dữ liệu đã kiểm checksum trên máy này hoặc nguồn được data inventory chỉ định.
Telemetry là corpus độc lập; không entity-join với SEAMLESS hoặc coi là observed activity trên topology này.

## Chạy baseline

Từ repo root, sau bước cài đặt trong [README](../README.md):

```sh
.venv/bin/python -m scripts.neo_baseline --output-dir reports/generated/neo-run-001
```

Runner từ chối ghi đè directory đã tồn tại.
Snapshot có 3.370 nodes và 56.367 edges.
Máy nguồn là SID kết thúc `-4157`; Domain Admins được tìm theo domain SID và RID 512.
Capability `computer_usable_identity` được khai báo tường minh tại context chính máy đó với provenance scenario, không suy ra từ host control.
Lượt baseline lịch sử dùng `seamless-standard-v1`; C-only profile là `reset-activation-c-v2`.
Runner hiện mặc định `neo-standard-v1`; dùng `--scenario-policy seamless-standard-v1`
để tái lập policy của lượt lịch sử này.
Chỉ cho phép `scenario_reset_password`, `acquire_reset_identity` và `propagate_group_entitlement`.
Budget là một witness, ba semantic steps và 6.000 expansions.

`query.json` giữ assumptions, profile, source, context và goal chính xác.
`snapshot.json` giữ structural graph cùng facts và code version.
`fifo.json`/`goal_guided.json` giữ full audit, attempts, C ledger, witness và engine guarantees.
`summary.json` ghi các lệnh CLI, phiên bản Python/platform, thời gian, input hashes, semantic hashes, native replay và parity API/CLI.
Thời gian CLI bao gồm load/validate snapshot, search, ranking, serialize và ghi output; thời gian chuẩn bị được ghi riêng.
Không dùng runtime của phiên trước làm số đo của máy này.

FIFO ở cap này chưa tìm witness, không chứng minh no-path.
Guided tìm một conditional witness C=1 sau 4.995 expansions, nhưng bị candidate cap và không chứng minh minimum.
C=1 là union-work ordinal của reset/activation; P/I vẫn chưa chấm.
`goal_guided` hiện là membership heuristic cho một số chain, chưa phải cost-guided search tổng quát.

## Cải tiến nhỏ và evidence

Không tìm thấy `AWG-v2-start.zip`, `AWG-neo-direction.md` hoặc patch tối ưu C cũ trên máy.
Không áp hoặc tái tạo patch đó dựa trên mô tả.
Profiling workload hiện tại phát hiện CLI gọi `wire()` lại trên kết quả mà `execute()` đã chuyển sang JSON-safe values.
Bỏ lượt duyệt thừa này là thay đổi một dòng trong CLI, giữ nguyên toàn bộ audit và định dạng kết quả.
Các phép đo và hash đối chiếu nằm ở [benchmark neo](../reports/neo/benchmark.json).
Không suy rộng kết quả của query này thành tốc độ cho mọi graph hoặc planner.

## Kiểm thử và evidence lịch sử

Fixtures cũ có một số giả định không còn phù hợp với ranh giới danh tính máy.
Các positive tests dùng scenario test riêng khai báo danh tính mạng và bind lại registry trước khi mô phỏng review; không chuyển numeric approval cũ sang context mới.
Queries lịch sử thiếu danh tính mạng vẫn phải bị chặn rõ ràng.
Evidence và numeric releases cũ giữ nguyên bytes.

Baseline integrity của code neo được sinh riêng trong `reports/neo/source-manifest.json`.
Các hash này kiểm thay đổi source hiện hành; không cấp numeric authority hay chứng minh kết quả lịch sử đúng với code mới.
Khi chủ động đổi source được pin, sinh lại baseline bằng công cụ đã cung cấp và chạy kiểm thử trước khi commit.
Không sửa checksum lịch sử để che drift.

## Chi phi C cho neo

Profile opt-in `neo-c-v1` dùng bảng công sức C cho hành động thay vì khai báo từng cặp
reset của actor ban đầu. C là điểm tương đối theo scenario, không phải thời gian hay P.
Giữ công thức `C = T1 + T2 - 2`: T1 là độ phức tạp công cụ (1: chuẩn, 2: tùy biến,
3: cần nghiên cứu); T2 là công sức thao tác (1: trao đổi đơn giản, 2: nhiều thao tác
và xác minh, 3: xử lý/tính toán nặng). Đây là các ước lượng được chọn cho neo từ rubric
cũ; không chuyển trạng thái duyệt A/B hay xác suất lịch sử sang scope mới.

| Hành động | Techniques | T1 / T2 | C |
| --- | --- | --- | --- |
| Reset mật khẩu | `genericall_reset_password`, `reset_target_password`, `scenario_reset_password` | 1 / 2 | 1 |
| Dùng danh tính vừa reset | `acquire_reset_identity` | 1 / 1 | 0 |
| Thêm thành viên nhóm | `genericall_add_member` | 1 / 2 | 1 |
| Cấp quyền sửa DACL | `genericall_grant_write_dacl` | 1 / 2 | 1 |
| Sửa DACL để cấp GenericAll | `grant_new_object_right` | 2 / 2 | 2 |
| Thực thi quản trị host | `obtain_admin_execution_on_host`, `scenario_winrm_admin` | 1 / 2 | 1 |

Membership đã có là suy diễn quyền, không tạo work unit. Hành động C=0 vẫn cần qua
semantic checks. Tổng C tính trên hợp các work unit, giữ nguyên cách khử trùng hiện có;
không cộng riêng một bước chuẩn bị chung khi thao tác đã bao gồm nó.

Scope là cùng miền, cùng authentication context, snapshot và scenario đã chọn.
Actor, nguồn quyền và đích hành động phải thuộc tập node trong miền đó, không phải boundary.
Giá áp dụng cả quyền qua nhóm, quyền vừa sửa và danh tính thu được giữa đường;
việc cấp giá không cấp capability hay biến prerequisite Unknown/False thành True.
Goal vẫn phân biệt danh tính thuộc nhóm đặc quyền với quyền thực thi trên host.
Techniques ngoài bảng tiếp tục chưa chấm C, không tự nhận C=0.

API Python dùng `load_effort_profile("neo-c-v1")` và `bind_effort_profile(query, graph, profile)`
tại `src.engine.ranking.effort_profiles`. Batch/exposure nhận `--effort-profile neo-c-v1`.
Các profile reset cũ và mặc định runner được giữ để tái lập benchmark.
Thay đổi này mở coverage C; chưa đổi search, thêm P/I hay mở roaming context.

Ví dụ kỳ vọng trên mô hình hữu hạn: quyền qua nhóm → reset → dùng danh tính →
quản trị host có C=2; sửa DACL → reset → dùng danh tính → quản trị host có C=4.
Độ nhạy của các mức điểm và coverage nhiều nguồn trên SEAMLESS cần đo riêng.

Kiểm tra đầu tiên với raw SEAMLESS đã kiểm manifest: baseline machine-to-DA giữ
witness C=1 sau 4.995 expansions và qua native replay/API–CLI parity.
Một query User có usable identity → host qua AdminTo, cùng scenario và goal
`admin_control`, giữ nguyên đường và 1 expansion: profile reset cũ không áp dụng,
`neo-c-v1` chấm C=1. Đây là cải thiện coverage trên một ca, chưa phải toàn SEAMLESS
hoặc cải thiện runtime. Các chain reset qua nhóm, ACL và đổi actor được kiểm riêng
bằng finite tests trong `tests/test_neo_effort.py`.
Ca AdminTo dùng source SID kết thúc `-1116`, host/context `-1000` trong miền SEAMLESS,
chỉ bật `obtain_admin_execution_on_host`, cap 100 expansions và ba steps.
550 test hồi quy engine/query/batch/scoring pass, gồm 23 test mới; lint, format,
repository và contract checks pass. Lượt full suite được dừng trước khi hoàn tất
do thời gian chạy các test lịch sử; không dùng lượt đó để tuyên bố full-suite pass.

## Ba ưu tiên tiếp theo

1. Xây cost-guided search C-first trong planner stateful hiện hữu, tái dùng preparation giữa queries, với oracle finite kiểm work deduplication, zero-cost actions và bằng chứng optimality dưới budget.
2. Mở rộng benchmark nguồn/goal/technique trên cùng snapshot, kiểm replay và chất lượng đường; đối chứng BloodHound trên cùng scope, tách hop count, C ordinal, semantic feasibility và runtime.
3. Hoàn thiện cohort nhiều nguồn và remediation: báo riêng phần chưa chạy, quan sát đường thay thế sau can thiệp và kiểm độ nhạy của assumptions/C trước khi xếp hạng rủi ro cho thesis.

Để cập nhật integrity baseline neo sau một thay đổi source có chủ đích:

```sh
.venv/bin/python -c 'from scripts.research.scenario_rating_pack import write_source_manifest; write_source_manifest()'
```

Để đo lại thay đổi CLI, dùng snapshot/query do runner vừa tạo và một checkout baseline tách biệt:

```sh
git worktree add --detach /tmp/awg-neo-before e96c1c0
.venv/bin/python -m scripts.research.benchmark_neo_cli \
  --baseline-root /tmp/awg-neo-before \
  --query-dir reports/generated/neo-run-001 \
  --output-dir reports/generated/neo-benchmark-001 \
  --report reports/generated/neo-benchmark-001-summary.json
git worktree remove /tmp/awg-neo-before
```

Harness dùng `/usr/bin/time -l` trên macOS, ba trials mỗi variant/search-order, đổi thứ tự before/after giữa các trials và từ chối semantic hash drift.
Nó không thay source hoặc bỏ bớt audit fields.
Report ghi hash của query, snapshot và CLI source của hai variants.
Report đo trước khi commit implementation nên revision Git của variant after vẫn là root commit; hash CLI source phân biệt đúng code đã đo.

Kết quả ba trials xen kẽ mỗi variant/search-order trên macOS arm64, Python 3.14.7:

| Chế độ | Median wall trước | Median wall sau | Peak RSS trước | Peak RSS sau |
| --- | --- | --- | --- | --- |
| fifo | 5.506s | 4.596s | 978.1 MiB | 1051.5 MiB |
| goal_guided | 6.648s | 5.744s | 1141.5 MiB | 1142.1 MiB |

Cả 12 trials giữ nguyên hash của toàn bộ semantic output theo từng search-order, gồm witness, C, attempts, assumptions và guarantees.
FIFO nhanh hơn khoảng 16,5% và guided nhanh hơn khoảng 13,6% trên workload này.
Peak RSS FIFO tăng khoảng 7,5%; guided gần như không đổi.
Đây là tradeoff thời gian/bộ nhớ quan sát được; không phải cải thiện RAM hoặc speedup phổ quát.

## Xác minh bàn giao

Full suite trên commit sạch `1c52e18`: 3.618 passed, 8 skipped, 99 subtests passed trong 707,50 giây.
Các test converter/BloodHound runner với raw SEAMLESS: 47 passed.
Sau suite, bổ sung chính sách Git giữ nguyên byte của hai gói rating lịch sử trên Windows và mở rộng test checkout thực; các kiểm tra portability/source integrity pass.
Ruff check/format, yamllint, repository/contract checks và Docker Compose config validation đều pass.
Đã kiểm native replay cùng parity API/CLI ở đường dẫn bàn giao và giữ nguyên 665 blobs nghiên cứu/fixtures/dữ liệu mẫu của upstream.
Demo remediation synthetic cắt 50% programs, ngắt 0% source-goal pairs và giữ hai bypass; không suy rộng sang SEAMLESS.
Chưa chạy đối chứng BloodHound live mới hoặc chờ kết quả CI trên GitHub.
Kết quả tổng hợp ở [validation neo](../reports/neo/validation.json).


## Khảo sát 10 query SEAMLESS với neo-c-v1 (2026-10-21)

Đo tại `9ede3d8`, Python 3.14.7, trên snapshot 3.370 nodes/56.367 edges do `neo_baseline` vừa dựng từ raw đã kiểm manifest.
Chọn cohort chủ đích theo các cạnh có thật, không chọn theo kết quả search; đây không phải mẫu đại diện toàn miền.
Mọi nguồn được khai báo có usable identity tại đúng context; riêng Computer cũng là giả định compromise tường minh, không suy từ host control.
Dùng `seamless-standard-v1`, không thêm facts/assumptions thủ công, budget 1 witness/5 steps/6.000 expansions và technique scope ghi trong lệnh bên dưới.
Mục tiêu nhóm là usable-identity entitlement; host là admin control, riêng Q10 chỉ là remote command execution.
Thời gian là một lượt API gồm compile policy + bind C + query, dùng chung graph; không gồm snapshot load (1,072s), replay, CLI serialization hoặc ghi full audit.

| Query | Nguồn → mục tiêu (RID) | Scope | Witness / C đầy đủ | Expansions | Giây | Điểm vướng hoặc giới hạn |
| --- | --- | --- | --- | ---: | ---: | --- |
| Q1 | User KATRINA 1116 → host 1000 | AdminTo trực tiếp | Có / C=1 | 1 | 0,610 | Đạt goal dưới hai runtime assumptions; complete trong scope AdminTo |
| Q2 | User DENA 2799 → DA 512 | MemberOf | Có / C=0 | 8 | 0,433 | Membership đặc quyền đã có; không phải leo thang mới; cap 1 witness |
| Q3 | User OLA 1395 → DA 512 | Reset trực tiếp + đổi identity | Chưa có / chưa đánh giá C | 6.000 | 1,958 | FIFO hết cap; ordered replay 3 bước đạt goal |
| Q4 | User ROLANDO 1111 → DA 512 | Reset qua nhóm 3790 | Chưa có / chưa đánh giá C | 6.000 | 1,926 | Hết cap; đoạn membership đã kiểm còn Unknown security_group/membership_usable |
| Q5 | User MARYANNE 1269 → DA 512 | Reset qua nhóm 3610 | Chưa có / chưa đánh giá C | 6.000 | 2,161 | Hết cap; membership tới nhóm 3610 còn Unknown; tên DISTLIST không thay bằng chứng group type |
| Q6 | User KATRINA 1116 → DA 512 | Qua Administrators, WriteDacl → GenericAll → AddMember | Chưa có / chưa đánh giá C | 6.000 | 2,466 | Replay được membership + WriteDacl; AddMember còn Unknown security_group/membership_change_allowed |
| Q7 | Computer FINWVIR 4157 → DA 512 | Reset; FIFO | Chưa có / chưa đánh giá C | 6.000 | 2,414 | Hết expansion cap |
| Q8 | Computer FINWVIR 4157 → DA 512 | Cùng Q7; goal_guided | Có / C=1 | 4.995 | 3,190 | Cap 1 witness; best-found, chưa chứng minh minimum |
| Q9 | User OLA 1395 → host 1000 | Reset → identity mới → AdminTo | Chưa có / chưa đánh giá C | 6.000 | 1,561 | FIFO hết cap; ordered replay 3 bước đạt admin control |
| Q10 | User FERN 3385 → host 1000 | CanPSRemote | Có / chưa đủ C | 1 | 0,459 | open_winrm_remote_session nằm ngoài 9 techniques; không phải AdminTo/admin control |

Có 4/10 query tìm witness và 3/4 witness đủ C, gồm một đường passive C=0; sáu query truncated chưa cho phép đánh giá coverage C hoặc kết luận no-path.
Mẫu này xác nhận C cho AdminTo trực tiếp và reset/activation với actor thay đổi; chưa xác nhận coverage C của các chain qua nhóm/ACL trên SEAMLESS chỉ từ finite tests.
Q3/Q9 có chuỗi conditional khả thi dưới cùng policy nhưng FIFO chưa tìm được trong budget; Q7/Q8 cô lập khác biệt search order mà không thay query facts hoặc C.
Q4/Q5/Q6 cho thấy facts/policy cho membership và quyền phát sinh cũng là điểm vướng; chưa thể kết luận mọi đường của các query này bị chặn, hoặc chỉ cần sửa search.
Chưa đổi engine/search, mở techniques, thêm assumptions hoặc dọn repo trong lượt khảo sát này.

Đã native replay cả bốn witness và kiểm final state:

- Q1: `obtain_admin_execution_on_host` dùng AdminTo của KATRINA tới BADBLOOD, C=1; admin_channel và authentication_accepted là assumptions.
- Q2: `propagate_group_entitlement` của DENA tới DA là passive, không tạo work unit, C=0; không diễn giải thành xác suất tấn công mới.
- Q8: FINWVIR reset OLLIE C=1 → OLLIE dùng credential vừa reset tại context FINWVIR C=0 → OLLIE có entitlement DA qua MemberOf C=0; hai active work units có tổng C=1.
- Q10: `open_winrm_remote_session` của FERN đạt remote command execution, replay pass nhưng unit chưa có giá; C=None không được đổi thành 0.

Ordered replay chẩn đoán Q3/Q9 không được đưa vào discovery hoặc tính thêm vào 4 witness ở bảng.
Nó kiểm chuỗi OLA → reset DENA → activate DENA → DA hoặc AdminTo trên BADBLOOD, với cùng initial state, context và policy như query gốc.
Q6 giữ nguyên Unknown ở AddMember sau quyền GenericAll phát sinh; không tự bổ sung gate để làm đường chạy được.

Lệnh tái lập từ repo root; bỏ dòng `neo_baseline` nếu snapshot này đã tồn tại, hoặc dùng directory mới và đổi đường dẫn trong Python tương ứng:

```sh
.venv/bin/python -m scripts.neo_baseline --effort-profile neo-c-v1 --output-dir reports/generated/neo-c-001
.venv/bin/python - <<'PY'
import time
from collections import Counter
from pathlib import Path
from src.engine.graph import EngineGraph
from src.engine.query import materialize_query, run_attack_query
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.semantics import Status, TransitionRequest, apply_transition, evaluate
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.scenario_policy import apply_policy_to_query
D = 'S-1-5-21-1271839998-3495686680-2211690266'
n = lambda rid: D + '-' + str(rid)
M, R, I, A = ('propagate_group_entitlement', 'scenario_reset_password',
              'acquire_reset_identity', 'obtain_admin_execution_on_host')
W, ADD = 'grant_new_object_right', 'genericall_add_member'
families = {'A': [A], 'M': [M], 'R': [M, R, I], 'H': [M, R, I, A],
            'D': [M, W, ADD], 'W': ['open_winrm_remote_session']}
# Q, source RID, goal RID, context RID, technique family, search order.
cases = [(1,1116,1000,1000,'A','fifo'), (2,2799,512,1000,'M','fifo'),
         (3,1395,512,1000,'R','fifo'), (4,1111,512,1000,'R','fifo'),
         (5,1269,512,1000,'R','fifo'), (6,1116,512,1000,'D','fifo'),
         (7,4157,512,4157,'R','fifo'), (8,4157,512,4157,'R','goal_guided'),
         (9,1395,1000,1000,'H','fifo'), (10,3385,1000,1000,'W','fifo')]
g = EngineGraph.from_snapshot(Path('reports/generated/neo-c-001/snapshot.json').read_text())
profile = load_effort_profile('neo-c-v1')
policy = 'seamless-standard-v1'  # Đổi thành 'neo-standard-v1' để đối chiếu policy mới.
for number, source, target, context, family, order in cases:
    s, t, c = map(n, (source, target, context))
    goal = {'target': t, 'kind': 'usable_identity_entitlement'} if target == 512 else {
        'target': t, 'required_state': {'remote_command_execution': [[s,t]]}
        if family == 'W' else {'admin_control': [t]}}
    q = dict(initial_actor=s, initial_state={'control': [s], 'usable_identity': [[s,c]]},
             authentication_context=c, target=t, target_goal=goal, allowed_techniques=families[family],
             scenario_reference=f'neo-cohort/Q{number}', evaluation_mode='scenario', search_order=order,
             budget={'max_paths': 1, 'max_steps': 5, 'max_expansions': 6000})
    started = time.perf_counter()
    q = bind_effort_profile(apply_policy_to_query(q, g, policy), g, profile)
    r = run_attack_query(q, g)
    seconds = time.perf_counter() - started
    coverage = (r.rating_coverage or {}).get('candidate_summaries', {})
    print(f'Q{number}', 'paths=',len(r.paths), 'C=',(r.min_effort or {}).get('minimum_effort_value'),
          'C_complete=',[v['c_complete'] for v in coverage.values()], 's=',round(seconds,3),
          'exp=',r.expansions, 'cap=',r.truncation_reason,
          'unknown=',Counter(p for a in r.attempts for p in a.unknown).most_common(3))
    for index, path in enumerate(r.paths, 1):
        assert replay_path(path, g) == path.final_state
        assert r.materialized_query.semantic_goal.matches(path.final_state)
        units = r.rating_coverage['candidates'][f'generated_{index:04d}']['effort']['units']
        print('replay:', [a.result.request.technique_id for a in path.transition_history],
              'C units:', [(v['rating_audit']['lookup_key']['technique'], v['cost']) for v in units.values()])
    # Diagnostic ordered replay only; these requests never enter discovery/search.
    a, v, h, da = n(1395), n(2799), n(1000), n(512)
    k, admins = n(1116), 'domain:sid:' + D + ':S-1-5-32-544'
    probes = {3: [(R,a,a,v),(I,v,v,h),(M,v,v,da)],
              6: [(M,k,k,admins),(W,k,admins,da),(ADD,k,k,da),(M,k,k,da)],
              9: [(R,a,a,v),(I,v,v,h),(A,v,v,h)]}
    if number in probes:
        m = materialize_query(q, g); state = m.initial_attack_state
        for spec in probes[number]:
            step = evaluate(g.to_prepared(), state, TransitionRequest(*spec), m.runtime_context, m.catalog)
            print('ordered probe:', spec[0], step.status, 'failed=',step.failed, 'unknown=',step.unknown)
            if step.status != Status.APPLICABLE: break
            state = apply_transition(state, step)
        print('ordered goal matches:', m.semantic_goal.matches(state))
PY
```

## Scenario mặc định neo (2026-10-21)

`neo-standard-v1` tái sử dụng các rule hiện có, với giả định được chọn cho khóa luận:
nhóm thiếu group type được coi là security group trong scenario, kể cả tên DISTLIST.
Tên nhóm không phải bằng chứng về loại nhóm. `security_enabled=False`, groupType
non-security và runtime fact False vẫn chặn; không tạo cạnh, quyền hay usable identity.
Mọi fact được bổ sung mang origin `declared_assumption`, với profile/rule/provenance.
Không suy xác suất thành công từ các giả định này.

Query dùng lại `PolicyAssumptionResolver` sẵn có theo nhu cầu cho `security_group`,
`membership_usable`, `membership_change_allowed` và `directory_write_allowed`, nên các
gates này vẫn được giải quyết sau khi đổi actor hoặc tạo quyền trong một prefix hợp lệ.
Các điều kiện khác giữ scope biên dịch hiện có; không mở mặc định host-admin mapping,
endpoint authorization hoặc password recovery. Không sinh trước
Cartesian product actor × group. Các declaration tường minh được ưu tiên; các fact
thực sự dùng được ghi trong transition decisions. Metadata giữ profile đầy đủ để CLI,
batch worker và replay tái lập cùng scenario. Remediation giữ policy trên graph sau sửa.

Đối chứng cùng snapshot và cohort 10 query, cùng techniques/5 steps/6.000 expansions:

| Kiểm tra | `seamless-standard-v1` | `neo-standard-v1` |
| --- | --- | --- |
| Discovery | 4/10 witness; 3/4 đủ C | 4/10 witness; 3/4 đủ C |
| Q4: membership tới nhóm 3790 | Unknown group gates | Replay prefix 2 MemberOf steps applicable |
| Q5: membership tới nhóm 3610 (DISTLIST) | Unknown group gates | Replay prefix 1 MemberOf step applicable |
| Q6: ACL → AddMember → DA, ordered probe | Dừng ở AddMember Unknown | Cả bốn actions applicable, đạt goal |
| Q8: machine → DA, guided | C=1 sau 4.995 expansions | Giữ C=1 sau 4.995 expansions |

Replay prefix/ordered probe là chẩn đoán riêng, không được tính thêm vào witness discovery.
Sáu query vẫn chạm cap; thay đổi này sửa khả năng áp dụng scenario, chưa sửa search.
Q10 vẫn chưa có C cho WinRM command session; nó không phải quyền admin.
Không so runtime của lượt Linux này với bảng macOS ở trên.

Runner `scripts.neo_baseline` mặc định dùng policy mới; thêm
`--scenario-policy seamless-standard-v1` để chạy lại policy cũ.
Exposure nhận `--scenario-policy neo-standard-v1`.
Trong lệnh cohort phía trên, đổi biến `policy` giữa hai tên để đối chứng.
Test riêng ở `tests/test_neo_scenario_policy.py` kiểm missing type, thuộc tính/fact False,
quyền phát sinh, evidence-only, profile transport, worker/resume và counterfactual.
23 test mới pass. Các lượt test tập trung engine/query/batch/C, policy và remediation
có tổng 777 passed, 3 optional raw-remediation pilots skipped; không chạy full suite.
Runner SEAMLESS với scenario mới đã qua native replay và API–CLI parity.
