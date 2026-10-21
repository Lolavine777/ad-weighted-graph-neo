# Executor replay nền — #283

API công khai tại `src.engine.remediation` nhận request 1.1.0, chạy baseline từ
public query và replay đúng thứ tự native transitions bằng evaluator hiện hành.
Đầu ra `remediation-replay/1` dành cho consumer #284: `rediscovery.status=not_run`,
không có kết luận disconnected, tỷ lệ giảm exposure hoặc giá trị C/P tự suy diễn.

## Cách chạy

Từ repository/worktree dùng Python 3.14 với `requirements-tests.txt`:

```powershell
$env:PYTHONUTF8 = "1"
python -m scripts.research.remediation_replay_probe
python -m scripts.research.remediation_replay_probe --seamless-raw-dir <private-raw-dir>
python -m pytest tests/test_remediation_executor.py tests/test_remediation_contract.py tests/test_remediation_identity.py -q
```

Probe chỉ xuất alias, số lượng và disposition tổng hợp. Tùy chọn `--output` lưu
chính summary này. Raw SEAMLESS phải khớp manifest sáu file trước và sau chạy.
Không ghi private ID/graph/query/trace vào artifact công khai. Muốn bật raw test,
đặt `REMEDIATION_SEAMLESS_RAW_DIR` đến thư mục được phép đọc. Thiếu raw thì test
skip với reason rõ ràng; synthetic không thay thế nghiệm thu raw.

## Tích hợp API

```python
from src.engine.remediation import (
    prepare_baseline,
    request_for_baseline,
    replay_baseline,
)

cells = [{"source_id": "source-label", "goal_id": "goal-label", "query": public_query}]
baseline = prepare_baseline(graph, cells, run_id="native-before")
request = request_for_baseline(baseline, edits, request_id="intervention-1")
artifact = replay_baseline(request, graph, baseline)
```

`graph` là `EngineGraph`; `public_query` dùng nguyên public query contract, gồm
typed goal, declared foothold/profile, initial state, assumptions và budget.
`source_id`/`goal_id` là nhãn manifest; actor và asset canonical được bind riêng
từ materialization. Không tự lấy terminal state làm initial state. Một cohort
dùng chung budget và evaluation mode; mỗi cell giữ query, state và context riêng.

Baseline giữ immutable JSON và digest native corpus. Replay tái lập public query,
kiểm exact paths/transitions, attempts, completeness và status trước execution
counterfactual. Cache/input khác bị từ chối. Cách này ưu tiên kiểm chứng; có chi
phí chạy baseline lần nữa, chưa tối ưu cache hay rediscovery toàn cohort.

Scope pins dùng canonical JSON SHA-256, riêng semantic catalog dùng file hash:

| Pin | Nội dung bind |
| --- | --- |
| graph/snapshot facts | Canonical graph đầy đủ provenance; toàn bộ facts/evidence hoặc `[]` nếu không có |
| source manifest | Nhãn source, initial actor canonical, initial AttackState mỗi cell |
| goal manifest | Nhãn goal, target canonical, target_goal và semantic_goal materialized |
| query profile | Toàn bộ danh sách cell/public query, gồm aliases/context/assumptions/basis |
| rating inputs | Các public query fields chứa `rating` hoặc `ranking`; full query vẫn được bind |
| revision/model/budget | Git HEAD worktree, file catalog semantics, evaluation mode và native budget |

Request fixture lịch sử chỉ cung cấp ví dụ edit. Phải tạo request pin đúng
baseline hiện tại; không tái dùng các scope digest fixture cho corpus khác.

## Phạm vi adapter và provenance

Hỗ trợ bốn catalog entries: `group-membership`, `admin-channel`, `admin-revoke`,
`asrep-preauth`. Các entry còn lại trả `UnsupportedIntervention(edit_id, reason)`;
chưa claim coverage 11 entries. AS-REP preauth là static gate thật; runtime override
không thể sửa gate này. SPN, generic ACL, session và RBCD interventions chưa có adapter.
Native witnesses của các technique đó vẫn có thể được extract từ public results.

Relationship denial bind exact edge/endpoints/kind và digest toàn bộ provenance;
chỉ loại positive relationship trong branch-local effective view. Không dùng
`withheld_relationships` để giả permission denial. Initial token membership,
permission, admin/session/material đã khai báo vẫn giữ nguyên; derived rights có
thể được tạo lại bởi producer thành công. Không mô phỏng thu hồi token/session
hoặc lifecycle AD nằm ngoài current model.

Runtime replacement kiểm exact predicate/subject/target/authentication context,
`expected_before` trên mọi cell chứa key đó, rồi tạo blocked runtime fact kèm
`counterfactual_intervention` metadata/reference. Không nhập fact từ source khác.
Binding ID khác null chưa hỗ trợ. Static replacement kiểm known value và digest
`canonical_value(fact.evidence)`, rồi dùng immutable effective lookup. Không tạo
collector evidence giả hoặc sửa `SnapshotFacts` lịch sử.

Mỗi replay decision giữ native `origin` của evaluator để audit, bổ sung
`effective_origin=counterfactual_intervention` và exact intervention refs khi gate
bị sửa. Vì evaluator dùng vocabulary origin sẵn có, consumer phải đọc
`effective_origin` để phân biệt scenario với observed evidence.

`retained` yêu cầu từng transition applicable và final goal thật sự đạt. `cut`
yêu cầu native BLOCKED và exact failed step/prerequisites. Unknown trả indeterminate;
evaluator ValueError/TypeError/KeyError trả error, không thành cut. Failed producer
không sinh effects/material/identity; replay dừng tại bước thất bại đầu tiên.

## Semantic witnesses và consumer #284

Extractor kiểm lại exact native transitions/final state, giữ ordered requests,
passive actions, actor/source/target, RBCD participants, exact runtime metadata,
mọi native prerequisite, snapshot/canonical/runtime/initial/artifact support.
Producer indices bind các earlier additions của capability fields mà native gates
đọc, cộng derived-edge parent. Nếu có nhiều artifact phù hợp, giữ support của tất
cả lịch sử phù hợp; chưa thu hẹp thành một minimal support set.

Identity dùng duy nhất `normalized_program_identity` của verifier #274, không có
normalizer thứ hai. Generated native IDs chỉ là observation-qualified trace refs.
Zero-action success vẫn bind comparison scope/source/goal. Dedup theo normalized
identity, giữ ordered/evidence histories khác nhau. Schema action 1.1 được kiểm
trong tests trên actual extracted witnesses, không chỉ fixture tự khai.

Artifact giữ full native transition history/final state cạnh witness để cross-check
binding. `ordered-observed-edges/1` chỉ hash ordered non-null canonical edge IDs;
route không có observed edge được ghi rõ `empty_nonstructural`, không gọi là
structural path. Baseline query và scope/corpus digest cũng đi kèm artifact local.

Full API artifact có dữ liệu theo input và chỉ nên lưu local với private raw.
Consumer #284 phải chạy after-search riêng, bind proof và đầy đủ bypass/new witnesses
trước khi tạo complete result 1.1.0 hoặc disconnected-pair metrics.

## Bằng chứng và gate còn lại

[Summary alias-only](../../../reports/research/issue283-replay-evidence.json) ghi
finite Alice/Bob, membership bypass và manifest-verified SEAMLESS one-source/host
channel replay. Raw/snapshot hashes không đổi trong mọi case. Đây là prediction
conditional trên declared scenario, không phải observed exploit hay mitigation
đã triển khai. Remote CI và A exact-head review phải báo riêng khi thực sự có.
