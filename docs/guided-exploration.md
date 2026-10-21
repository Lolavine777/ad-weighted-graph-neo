# Backend khám phá có hướng dẫn — 0.1.0

Refs #224, #279. Module `src.engine.exploration` bổ sung API Python để consumer
hiển thị đường cấu trúc khi zero candidates, kiểm tra action ở state rõ ràng,
và chọn assumptions của một scenario template đã review. Không đổi public
query-result schema, thuật toán semantic search hay scoring/ranking.

## API cho consumer

| API | Input | Output / giới hạn |
| --- | --- | --- |
| `structural_exploration(query, graph)` | Public query đầy đủ, exact EngineGraph/snapshot | `structural_only`: paths với route IDs/nodes/edges/provenance, graph binding, budgets/expansions/complete/truncated. Không cần semantic candidates. |
| `inspect_structural_edge(query, graph, edge_id, actor=..., prefix=...)` | Exact edge ID, canonical actor, ordered TransitionRequests đã chọn | Các direct catalog options thực sự tương thích với kind/endpoints; prerequisites/status/before/after ở state sau replay prefix. Không tự chọn một technique cho GenericAll. |
| `inspect_transition(query, graph, request, prefix=...)` | Explicit TransitionRequest, kể cả credential/derived action không thuộc raw edge | Probe bằng evaluator hiện hành. Request RBCD giữ typed binding. Không suy ra actor/context từ tên đường. |
| `build_scenario_template(query, graph, assumptions, template_id=...)` | Reviewed assumptions từ query ASSUMED của đúng case | Template bất biến, bind với canonical graph + snapshot facts + query scope. Không tự tạo assumptions từ predicate thiếu scope. |
| `scenario_proposals(template, query, graph)` | Đúng graph/query scope | Unchecked proposals và rejected-assumption ledger từ materializer. Đây là outcomes mẫu, không phải missing facts được chứng minh cho toàn đường. |
| `query_with_proposals(template, query, graph, selected_ids)` | Các checkbox IDs duy nhất thuộc template | Fresh public query ở scenario mode; chỉ thay assumptions/evaluation mode. Consumer phải chạy lại public engine thật. |

Transport riêng `guided-exploration/0.1.0` trả dictionaries JSON-compatible.
Route/proposal IDs chỉ có nghĩa trong response/template tương ứng; không dùng để
ghép programs giữa runs. Tên hiển thị lấy từ exact graph, không phải hardcoded alias.

## Replay và điều kiện thiếu

Probe nhận prefix explicit, replay từng action bằng `evaluate()`/`apply_transition()`.
Chỉ APPLICABLE được thêm effects. BLOCKED/INDETERMINATE dừng prefix ngay; options
phía sau để rỗng. Không grant identity hoặc material để "xem thử" prerequisites
của suffix. `prefix_status`, state và transition audit cho consumer biết bước nào
đã được đánh giá thật. Giới hạn steps/expansions của public query áp dụng cả probe;
options trả thiếu do budget phải giữ `truncated`/reason.

Inspect edge chỉ trả **direct catalog options**, không là whole-route planner.
Compound recipes, DeclaredHostAdmin projection và actions tạo capability/đổi actor
cần explicit action/binding hoặc backend extension riêng. AS-REP dùng
`inspect_transition()`; không gán AS-REP cho GenericAll. Một đường cấu trúc không
bao phủ mọi attack program có derived relationships/artifacts.

Ví dụ dùng fixture synthetic hiện hành:

```python
import json
from pathlib import Path
from src.engine import EngineGraph, run_attack_query
from src.engine.exploration import (
    build_scenario_template,
    scenario_proposals,
    query_with_proposals,
    inspect_transition,
)
from src.engine.semantics.transitions import TransitionRequest

folder = Path("tests/fixtures/asrep")
graph = EngineGraph.from_snapshot((folder / "snapshot.json").read_text())
assumed = json.loads((folder / "query.json").read_text())
raw = {**assumed, "assumptions": [], "evaluation_mode": "evidence_only"}
victim = raw["initial_state"]["known_identity"][0]
first = TransitionRequest("asrep_request", raw["initial_actor"], raw["initial_actor"], victim)
diagnosis = inspect_transition(raw, graph, first)
template = build_scenario_template(
    raw, graph, assumed["assumptions"], template_id="synthetic-asrep"
)
choices = scenario_proposals(template, raw, graph)
# Consumer lấy IDs từ những checkbox người dùng thực sự chọn.
selected_ids = []
new_query = query_with_proposals(template, raw, graph, selected_ids)
result = run_attack_query(new_query, graph)
```

## Scope và veto

Binding giữ toàn bộ query ngoài assumptions/evaluation mode: source/initial state,
goal/checkpoint, aliases, auth context, runtime facts, allowed techniques,
budgets/rating scope/scenario reference. Thay một trong các input này phải dựng
template phù hợp mới. Graph binding bao gồm snapshot facts, không chỉ topology.
Input cần JSON-compatible; callback-based queries không phải template transport.

Templates không sửa snapshot hoặc thực thi action. Materializer giữ authoritative
False veto và rejected assumptions. Snapshot/state veto còn được evaluator kiểm
tra khi probe/rerun; proposals không được coi là bảo đảm thành công. UI cần hiện
ledger và status thật, không xóa rejection hoặc biến tất cả Unknown thành True.

SEAMLESS có thể dùng `raw_query`/`assumed` từ `seamless_inputs()` sau manifest
verification để dựng template local. **Case đó có initial actor là Computer C0,
known identity V_A và target C0**; không tự dùng chín assumptions đó cho source
OLA_CARSON hoặc một query Direct Query khác. Private graph, templates và outputs
chỉ lưu local theo policy của repo. Lượt triển khai ban đầu chưa có private input;
nghiệm thu SEAMLESS riêng được ghi bên dưới.

## Handoff #279

### Nghiệm thu backend SEAMLESS local - 14/10/2026 (lịch sử)

Runner dùng manifest verifier, `seamless_inputs()` và public engine hiện hành:
[runner](../scripts/research/guided_exploration_acceptance.py),
[acceptance matrix của lượt 14/10 đã lọc dữ liệu private](../reports/research/issue287-guided-exploration-acceptance-v2.json).
Code revision, source/config/runtime digests, raw checksums, graph/facts identity,
caps, counts/status và hashes của local evidence nằm trong summary. Full snapshot,
queries, templates, bindings và before/after traces chỉ lưu dưới ignored
`reports/generated/issue287/`; evidence references trong matrix tương đối với
output directory của run, không phải file được publish.

- A: scope helper C0/V_A/C0, chín proposals unchecked. RAW và none indeterminate,
  0 candidates; full rerun success, 3 candidates; drop recovery indeterminate,
  0 candidates, không có bypass đã tìm thấy. Full run có đường AdminTo trực tiếp
  bỏ checkpoint membership; không tuyên bố mọi assumption đều cần cho mọi path.
- B (Baseline): cặp tên OLA_CARSON(User) -> BADBLOOD(Computer).
  Query khai báo control(B_SOURCE), không usable identity/password; auth context C0,
  admin_control(B_TARGET), toàn catalog, không assumptions/runtime/rating inputs.
  Một structural route GenericAll → AdminTo dài 2 bước; 5.000 expansions chạm
  cap, complete=false. Semantic RAW cũng truncated, 0 candidates.
- B (Complex 5-cạnh): khảo sát hệ thống trên exact SEAMLESS snapshot (2.493 users tới
  BADBLOOD DC; 2.075 users có khoảng cách ≥ 4 cạnh; 1.859 candidates có ≥ 3 quan hệ).
  Chọn case chính GINO_ROSS(User) -> BADBLOOD(Computer), đúng 5 cạnh (6 nodes, 4 nodes
  trung gian), 3 relationship kinds (`MemberOf`, `GenericAll`, `AdminTo`):
  1. `GINO_ROSS` --[`MemberOf` / `propagate_group_entitlement`]--> `DOMAIN USERS`
  2. `DOMAIN USERS` --[`MemberOf` / `propagate_group_entitlement`]--> `AUTHENTICATED USERS`
  3. `AUTHENTICATED USERS` --[`MemberOf` / `propagate_group_entitlement`]--> `PRE-WINDOWS 2000 COMPATIBLE ACCESS`
  4. `PRE-WINDOWS 2000 COMPATIBLE ACCESS` --[`GenericAll` / `scenario_reset_password`]--> `KATRINA_GREEN` (kèm derived action `acquire_reset_identity` đổi capability/actor sang KATRINA_GREEN)
  5. `KATRINA_GREEN` --[`AdminTo` / `obtain_admin_execution_on_host`]--> `BADBLOOD` (đạt `admin_control`).
- Bảng chẩn đoán từng bước (RAW probe vs Evaluator thật):

| Bước | Cạnh & Quan hệ | Technique options | Actor / State trước | Prerequisites (RAW) | Effects nếu applicable | Blocker |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `GINO_ROSS` → `DOMAIN USERS` (`MemberOf`) | `propagate_group_entitlement` | Actor: GINO_ROSS; State: `control(GINO_ROSS)` | `source_authorized`: True, `security_group`: Unknown, `membership_usable`: Unknown | Thêm membership `DOMAIN USERS` | Thiếu `security_group`, `membership_usable` (indeterminate) |
| 2 | `DOMAIN USERS` → `AUTHENTICATED USERS` (`MemberOf`) | `propagate_group_entitlement` | Replay prefix [bước 1]: dừng ngay do bước 1 indeterminate | RAW không prefix: `source_authorized`: False | Thêm membership `AUTHENTICATED USERS` | Dừng prefix tại bước 1; không prefix thì blocked |
| 3 | `AUTHENTICATED USERS` → `PRE-WIN2K` (`MemberOf`) | `propagate_group_entitlement` | Chưa tới (suffix chưa đánh giá tại state này) | RAW không prefix: `source_authorized`: False | Thêm membership `PRE-WIN2K` | Dừng prefix; không prefix thì blocked |
| 4 | `PRE-WIN2K` → `KATRINA_GREEN` (`GenericAll`) | `scenario_reset_password` | Chưa tới (suffix chưa đánh giá tại state này) | RAW không prefix: `source_authorized`: False, `directory_write_allowed`: Unknown | Password reset trên KATRINA_GREEN | Dừng prefix; thiếu quyền/write |
| 4b | Derived action (AuthenticationControl) | `acquire_reset_identity` | Đổi actor/capability từ GINO_ROSS sang KATRINA_GREEN | RAW không prefix: `usable_identity`: False | `usable_identity(KATRINA_GREEN)` | Cần bước 4 hoàn thành |
| 5 | `KATRINA_GREEN` → `BADBLOOD` (`AdminTo`) | `obtain_admin_execution_on_host` | Chưa tới (suffix chưa đánh giá tại state này) | RAW không prefix: `source_authorized`: False, `host_session_available`: Unknown | `admin_control(BADBLOOD)` (đạt Goal) | Dừng prefix; chưa có identity/admin |

- Scenario Proposal cho case `seamless-287-gino-ross` (13 assumptions độc lập, không tái dùng 9 assumptions của C0):
  Replay từng bước qua `inspect_transition` đạt APPLICABLE cho toàn bộ 5 bước + 1 derived action, đạt goal `admin_control(BADBLOOD)`.
- Negative Veto Control: Bỏ assumption `directory_write_allowed` ở bước 4 khiến bước 4 thành `indeterminate`, và probe bước 5 tiếp sau dừng ngay với `prefix_status: indeterminate`, `options: []`.
- Search Horizon & Truncation: Trong full engine search tự do `execute()`, fan-out lớn của group `DOMAIN USERS` chạm trần `expansions: 5000` (`truncated`, 0 candidates); trong khi prefix probe trực tiếp xác nhận tính đúng đắn của chuỗi hành động. Báo cáo trung thực ranh giới mở rộng trạng thái mà không tự ý tăng budget vô hạn.
- C/P/I/ranking chưa có basis và giữ unrated. Cả baseline và complex case B đều vượt qua 24/24 acceptance checks của runner.
- C (Realistic Kerberoasting Case): Kịch bản Kerberoasting thực tế trên snapshot SEAMLESS cho demo #279 và nghiệm thu #287 (refs #224).
  - **Foothold & Narrative**: Nhân viên `ALEXANDRIA_WALSH` (`admincount=False`, thành viên `DOMAIN USERS`) lộ mật khẩu qua phishing. Attacker xác thực vào máy trạm `AWSWWKS1000000`, chỉ có `usable_identity(ALEXANDRIA_WALSH, AWSWWKS1000000)`, hoàn toàn **không cấp quyền kiểm soát máy trạm (`control(Workstation)`) hay domain privilege**.
  - **Service Account & Target**: Khám phá tài khoản có SPN `AVIS_SWEET` (`MSSQL/GOOWWEBS1000000`) qua LDAP directory enumeration (`known_identity` khai báo trong initial state). Target là Domain Controller `BADBLOOD`, typed goal: `admin_control(BADBLOOD)` (quyền thực thi mã với đặc quyền quản trị trên host DC theo mô hình ngữ nghĩa).
  - **Group Type & Phân quyền DACL**: `AVIS_SWEET` là thành viên nhóm trung gian `HO-170-DISTLIST1`, nhóm nắm quyền `GenericAll` trên `KATRINA_GREEN`.
    Dữ liệu raw BloodHound v3 chỉ thu thập 7 thuộc tính, thiếu `groupType`.
    Khai báo minh bạch `security_group=True` là **Unverified Runtime Assumption** (trong AD, chỉ Mail-Enabled Security Groups mới có hiệu lực DACL; Distribution Groups thuần túy không thể ủy quyền).
    `SHERRIE_SOTO` $\to$ `VA-JER-ADMINGROUP1` $\to$ `OLLIE_LONG` $\to$ `BADBLOOD` là đường thay thế riêng, không phải chuỗi identity được runner này thực thi.
  - **Chuỗi hành động (3 structural hops, 7 semantic actions)**:
    1. `kerberoast_request` (`ALEXANDRIA_WALSH` @ Workstation, target `AVIS_SWEET`)
    2. `recover_ticket_secret` (`ALEXANDRIA_WALSH` @ Workstation, target `AVIS_SWEET`)
    3. `activate_recovered_identity` (`AVIS_SWEET` @ Workstation)
    4. `propagate_group_entitlement` (`AVIS_SWEET` @ Workstation, nhóm `HO-170-DISTLIST1`)
    5. `scenario_reset_password` (`AVIS_SWEET` @ Workstation, `HO-170-DISTLIST1` $\to$ `KATRINA_GREEN`)
    6. `acquire_reset_identity` (`KATRINA_GREEN` @ Workstation)
    7. `obtain_admin_execution_on_host` (`KATRINA_GREEN` @ Workstation $\to$ `BADBLOOD`)
  - **Bảng chẩn đoán từng bước**:

| Bước | Kỹ thuật (`technique_id`) | Actor / Context | Prerequisites Đánh giá | Trạng thái | Cổng chặn nếu thiếu Assumption / Identity |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `kerberoast_request` | `ALEXANDRIA_WALSH` @ Workstation | `actor_controlled: True`, `known_identity: True`, `has_spn: True` | APPLICABLE | Thiếu SPN: `known_identity: False` |
| 2 | `recover_ticket_secret` | `ALEXANDRIA_WALSH` @ Workstation | `actor_controlled: True`, `ticket_granting_service: True` | APPLICABLE | Bỏ assumption: Unknown Halt; Fact False: VETO |
| 3 | `activate_recovered_identity` | `AVIS_SWEET` @ Workstation | `actor_controlled: True`, `secret_valid: Assumed` | APPLICABLE | Thiếu secret: `secret_valid: False/Unknown` |
| 4 | `propagate_group_entitlement` | `AVIS_SWEET` @ Workstation | `actor_controlled: True`, `member_of: True`, `security_group: Assumed` | APPLICABLE | Chưa kích hoạt `AVIS_SWEET`: `actor_controlled: False` |
| 5 | `scenario_reset_password` | `AVIS_SWEET` @ Workstation, target `KATRINA_GREEN` | `actor_controlled: True`, `generic_all: True` | APPLICABLE | Chưa kiểm soát `AVIS_SWEET`: `actor_controlled: False` |
| 6 | `acquire_reset_identity` | `KATRINA_GREEN` @ Workstation | `actor_controlled: True`, `secret_valid: Assumed` | APPLICABLE | Account disabled: `authentication_accepted: False` |
| 7 | `obtain_admin_execution_on_host` | `KATRINA_GREEN` @ Workstation $\to$ DC | `actor_controlled: True`, `admin_to: True`, `admin_channel: Assumed` | APPLICABLE | Thiếu channel: `admin_channel: Unknown` |

  - **Đính chính về tính tối ưu**: Candidate 0 tìm được khớp chuỗi thiết kế giải thích trong không gian tìm kiếm có giới hạn (`expansions: 5000`, `truncated: true`, `engine_reported_guarantees.is_minimum_proven_over_scope: false`, `unrated`). Không tuyên bố là chương trình tối ưu.
  - **DROP-RECOVERY vs True Known-False VETO**:
    - Bỏ giả định `recovery_success` $\to$ Unknown prefix halt (`step2: indeterminate`, `step3_suffix: []`).
    - Khai báo fact phủ định `recovery_success = False` $\to$ Sổ cái từ chối giả định (`rejected_assumptions: [{"reason": "known_false_veto"}]`) và probe bước 3 dừng với `prefix_status: "blocked"`.
  - [Báo cáo Kerberoasting Acceptance lịch sử](../reports/research/issue287-kerberoasting-seamless-acceptance.json) và [worklog 14/10](worklog/2026-10-14-guided-exploration-backend.md) giữ nguyên bytes.
    Worklog lịch sử nhầm identity cuối chuỗi chính với đường thay thế và ghi nhầm đích `GenericAll`; chuỗi executable dùng `KATRINA_GREEN` như mô tả đã đính chính ở trên.
    [Báo cáo successor v2](../reports/research/issue287-kerberoasting-seamless-acceptance-v2.json) ghi kết quả rerun với expected/observed invariants tại revision của nó; xem [ghi nhận đính chính 15/10](worklog/2026-10-15-pr287-exact-head.md).


Tái lập từ root của checkout revision trong summary, với authorized raw root:

```text
# Baseline Case B (2 cạnh)
python -m scripts.research.guided_exploration_acceptance --raw-dir <authorized-raw-root> --source-label OLA_CARSON --target-label BADBLOOD --output-dir reports/generated/issue287/reproduce --sanitized-report reports/generated/issue287/reproduce-summary.json

# Complex Case B (5 cạnh)
python -m scripts.research.guided_exploration_acceptance --raw-dir <authorized-raw-root> --source-label GINO_ROSS --target-label BADBLOOD --output-dir reports/generated/issue287/reproduce-complex --sanitized-report reports/generated/issue287/reproduce-complex-summary.json

# Case C Realistic Kerberoasting (3 cạnh cấu trúc, 7 semantic actions)
.venv/bin/python -m scripts.research.kerberoasting_seamless_acceptance --raw-dir <authorized-raw-root> --output-dir reports/generated/issue287/kerberoasting-reproduce-v2 --sanitized-report reports/generated/issue287/kerberoasting-reproduce-summary-v2.json
.venv/bin/python -m pytest tests/test_exploration.py tests/test_engine.py tests/test_asrep.py -q
```

Optional real-data regression (PowerShell); thiếu biến này test private sẽ skip,
runner thiếu raw hoặc invalid manifest sẽ báo BLOCKED, không dùng synthetic thay thế:

```powershell
$env:GUIDED_SEAMLESS_RAW_DIR = '<authorized-raw-root>'
$env:GUIDED_SEAMLESS_SOURCE_LABEL = '<private-B-source-label>'
$env:GUIDED_SEAMLESS_TARGET_LABEL = '<private-B-target-label>'
python -m pytest tests/test_guided_seamless_acceptance.py -q -s
```

Backend acceptance giới hạn ở scopes/budgets đã khai báo. HTTP/UI/live comparison
vẫn pending #279; không tự đóng #224 hoặc coi search bounded là global optimum.

Nghiệm thu lịch sử ngày 14/10 chạy trên `ebffa1e6687b78030ea37b0f94602f38be45f4e6`:
24/24 PASS trong 225.526s, raw unchanged; focused tests 96 PASS.
[Validation ledger](../reports/research/issue287-guided-exploration-validation.json)
ghi cả full-suite failure trước sửa và affected regression rerun 7 PASS.
Không claim đã rerun toàn suite sau sửa. Không đổi evaluator/search/scoring.

Lượt 14/10 sửa integration gate bằng [bản kê Week4 v3](../reports/research/week4-guided-exploration-acceptance-manifest-v3.json):
giữ strict source-pin equality cho revision có exploration và giữ nguyên bytes
manifest v2/oracles cũ. V3 là **synthetic regression only**, 36 PASS;
hai rows prerequisite/manual không chạy, không thay nghiệm thu SEAMLESS bên trên.
Full Week4 traces chỉ lưu local. Tái tạo observations bằng runner có sẵn:

```text
python -m scripts.research.week4_acceptance_runner --output reports/generated/issue287/week4-reproduce.json
```

V3 giữ `semantic_payload()` của output thật cùng execution identity/file pins;
loại full traces và command paths khỏi bản kê public. Summary SEAMLESS lượt trước
và manifest Week4 lịch sử được giữ nguyên, không cập nhật tại chỗ để pass checks.

### Nghiệm thu successor - 15/10/2026

Revision thực thi `5a923f4e84e09c8dedd9151fa0d5a04f9274bb15` đã rebase lên `develop` tại `81d37814b9544300f701822da4883bb1f0148906`.
[Kerberoasting v2](../reports/research/issue287-kerberoasting-seamless-acceptance-v2.json) đạt 8/8 PASS trong 93.701s; [guided exploration v3](../reports/research/issue287-guided-exploration-acceptance-v3.json) đạt 24/24 PASS trong 146.399s trên raw SEAMLESS đã verify.
Runner Kerberoasting suy ra verdict từ expected/observed invariants; thiếu hoặc không verify được dataset là BLOCKED, invariant sai là FAIL, cả hai đều exit khác 0.
Chuỗi executable giữ `KATRINA_GREEN`, 16 assumptions hiện có và C/P/I unrated; không đổi contract exploration hoặc thuật toán search.
[Week4 v4](../reports/research/week4-guided-exploration-acceptance-manifest-v4.json) giữ strict pin equality và các assertions mới hơn của develop, với 36 PASS và 2 manual rows không chạy.
Các artifacts lịch sử giữ nguyên bytes; [worklog successor](worklog/2026-10-15-pr287-exact-head.md) ghi việc đính chính và validation riêng.

Consumer có thể bọc API này bằng endpoint localhost với Host/Origin validation
hiện hành, map public foothold profile sang query đầy đủ trước khi gọi, và giữ
structural layer độc lập với selected candidate. Module này **chưa thêm HTTP
endpoints/checkbox UI hoặc kết nối live compare**, chưa là nghiệm thu full #224.
UI phải giữ run A/B thực tế và scope; không load demo ASSUMED thay rerun.

General-purpose recommendation và tự giải thích mọi suffix chưa được triển khai.
Đầu ra hiện tại là exact-state diagnostics và reviewed case templates để tích hợp
luồng giới hạn một cách có thể kiểm chứng.

```text
python -m pytest tests/test_exploration.py tests/test_engine.py tests/test_asrep.py -q
python -m ruff check src/engine/exploration.py tests/test_exploration.py
python -m ruff format --check src/engine/exploration.py tests/test_exploration.py
```
