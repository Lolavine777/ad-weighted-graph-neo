# Đối soát SEAMLESS thật với BloodHound Legacy 4.0.3

Ngày rerun: 2026-10-05; A: @Lolavine777; reviewer: @nairyuuu.
Refs [#47](https://github.com/nairyuuu/ad-weighted-graph/issues/47), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48), [#184](https://github.com/nairyuuu/ad-weighted-graph/pull/184), [#189](https://github.com/nairyuuu/ad-weighted-graph/pull/189); handoff [#183](https://github.com/nairyuuu/ad-weighted-graph/pull/183).
Project CLI được chạy lại tại latest integrated `develop@294cba3e2882e4b7a5fbd867aadb8434124612c3`, sau merge #189.
Rerun dùng nguyên raw snapshot, Legacy full exports, importer source, time policy và research/comparator/raw-locator scripts của #184.
Contract 1.3.0; PR này chỉ cập nhật report/evidence/worklog, không sửa parser/engine/comparator hoặc production code của B.

**Full MemberOf đạt exact set với Legacy: 15.917 matching, project-only và Legacy-only đều rỗng.**
Số này được đo từ directed triples và exact raw union, không hardcode từ expected count của #189.
Các delta khác giữ nguyên: 17 project-only và 3 Legacy-only trong M1.
Disposition hiện hành dùng [comparison contract #195](seamless-legacy-403-comparison-contract.md): self-ACE/nested AdminTo/CanRDP là `accepted_policy_difference`; ForceChangePassword/HasSession là `not_measurable`.
Đây là quyết định của A để B review semantics ở #195; acceptance của evidence #194 không tự thay human acceptance của contract.
Full `m1-structural-v1` comparator vẫn trả `NOT_MEASURABLE` vì Legacy giữ `export_complete=false`; acceptance của common slices/policy differences ở #195 không làm full machine scope equivalent.
Không có claim product parity hoặc Week 3 complete; #47/#48 giữ mở tới acceptance.
Fix PrimaryGroupSid của B đã được kiểm chứng trên dữ liệu thật; không loại primary memberships khỏi full MemberOf để tạo equality.

## 1. Binding của phép chạy thật

Rerun hiện hành đọc full Legacy exports trong `.cache/issue47/` của #184 và copy vào scratch `.cache/issue47-post189/`.
Docker daemon không chạy trong phiên này; không import hoặc capture database mới, không đo lại runtime/import counters.
Native import evidence dưới đây được giữ từ lần A chạy **official native Legacy Upload Data** ngày 2026-10-04 trên database mới.
Sáu file raw schema-v3 nguyên bản được verify theo [manifest](../../data/samples/manifests/seamless-raw-v1.json), không convert.

| Binding | Giá trị |
| --- | --- |
| Snapshot | `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` |
| Raw manifest SHA-256 | `a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d` |
| Official app | Legacy 4.0.3, Darwin x64 release; ZIP SHA-256 `d0aa252c1cf8232ad1fe5c59ac94962ba6d0790c333a960d3c757fb9a18f98d8` |
| Upstream tag revision | `b54c418ef83fe5856ae3fe6317a20f2368a6378c` |
| Neo4j | 4.1.13 Community, amd64 image `sha256:1f08dd79d877776e2501ba77d8b4c5354e8953d603fcae31df6b7b2c61685bc0` |
| A container của #184 | `issue47-legacy-403-a`; full ID trong machine artifact; localhost HTTP 47474 / Bolt 47687 |
| Pre-import database | 0 nodes / 0 relationships, version queried before upload |
| Import | Sáu file theo filename order; cả sáu UI statuses là Upload Complete / 100% |
| Console interval của #184 | 22:49:21.748192 tới 22:50:11.156740, UTC+07:00, ngày 2026-10-04 |
| Console measurements của #184 | 6 Processing + 6 IngestTime events, sum 49.40560791015625 seconds; caught write-error console events trong interval = 0 |

UI completion và console events không đo rejected records hoặc chứng minh từng write operation.
Rejected-record count của #184 vẫn `null`; importer write errors/rejections/duration của **hai lần lịch sử B** giữ nguyên unknown/null.
Thời gian IngestTime là tổng timer của app cho sáu file, không phải benchmark so tốc độ với project CLI.
An initial Import Graph action rejected the computers file before raw upload; worklog records this corrected action outside the measured interval.

A đã dùng B's [read-only queries](../../reports/research/issue-82-legacy-reconciliation-queries.json), mapping và serialization helpers để export full database ở #184.
Rerun verify lại ba retained files và comparator tables: khớp **đúng toàn bộ bytes và SHA-256 của #183/#184**, không chỉ counts:

| Full local export | SHA-256 trùng handoff |
| --- | --- |
| `legacy-nodes.json` | `ed4a6aa7775a4bfb5994875243eaf11588cf03cf4301acc1f23ce62fae11839c` |
| `legacy-relationships.json` | `4071dd8747a18aef4f30b074eeac163cbc7454cfe42a234367e81f8c488cdbf6` |
| `identity-mapping.json` | `202a91b951ff9292f57eeb535c65f02bb7063f5c28a6b27589acdc4ae45c570b` |

Legacy comparator JSON giữ nguyên bytes của #184; chỉ project candidate được sinh lại và thêm đúng metadata comparison scope bằng helper hiện có.
[Machine-readable evidence](../../reports/research/issue-47-seamless-legacy-403-reconciliation.json) pin revision, input/output digests, exact set digests và historical runtime/query/source bindings.
Full identity/triple/raw values/logs giữ trong ignored `.cache/issue47*`; committed artifact chỉ có counts, hashes và raw array pointers.

| Binding sau #189 | SHA-256 |
| --- | --- |
| Project CLI output | `aa9c9a6eaea39115ca6a406054bf9bcd47769cc7f4ec06f103170aca69b5a840` |
| Project comparator input | `7fe3c0ae742e7772491476d1369bb51057ab9f434184ae2560fc0eaf27527fcb` |
| Unchanged Legacy comparator input | `93a0cbf1b01550ec3443020d1e2aa4caed1b42d19ea3327decb79e914f2f9a83` |
| Full observation evidence | `f96479391987327e719607037ecb0c2579574fd39e48aa137c2ba017c8746242` |
| Full raw MemberOf proof | `1d8cbeff9bc8060db954582d6f6c16fb5d1eddff087b3e0a6f6a8593d3fdd907` |
| Audit summary | `56fe61b17d563eb2c838f412c052c7577d5d235c817a21b9ac155558b986a89f` |
| Comparator CLI output | `dc4ac9fa317832c9ac96933a7cf0ec148adefff77f9442faea850fe44699c7b3` |

## 2. Identity sets, directed sets và multiplicity

Explicit mapping là one-to-one; 259 raw IDs đổi representation, không dùng display-name hoặc SID suffix heuristic.
Exact canonical identity sets và typed-kind sets bằng nhau: 3.370 nodes, gồm Computer 100, Domain 1, GPO 2, Group 551, OU 223, User 2.493.
Population là 3.368 collected + 2 boundary, không có identity-only difference ở mỗi population.
Legacy `domain` và `is_boundary` comparison fields được gán từ project/raw mapping theo handoff, nên sự bằng nhau của hai fields này không phải phép đo Legacy metadata độc lập.
Hai boundary direct memberships của #139 cũng thuộc matching set; contribution vào MemberOf delta = 0.

Tất cả hàng sau tính từ exact mapped directed triples, không suy intersection từ tổng counts.
Đây là full observation ledger của #194; [contract #195](seamless-legacy-403-comparison-contract.md#3-source-of-truth-matrix-cho-tám-relation) quy định common slices và disposition mà không đổi các sets dưới đây.

| Kind | Project | Legacy | Matching | Project-only | Legacy-only |
| --- | ---: | ---: | ---: | ---: | ---: |
| MemberOf | 15.917 | 15.917 | 15.917 | 0 | 0 |
| GenericAll | 37.044 | 37.034 | 37.034 | 10 | 0 |
| WriteDacl | 3.395 | 3.392 | 3.392 | 3 | 0 |
| AdminTo | 9 | 5 | 5 | 4 | 0 |
| CanPSRemote | 2 | 2 | 2 | 0 | 0 |
| CanRDP | 0 | 3 | 0 | 0 | 3 |
| ForceChangePassword | 0 | 0 | 0 | 0 | 0 |
| HasSession | 0 | 0 | 0 | 0 | 0 |

Project: 56.367 stored edges = 56.367 unique triples; Legacy: 71.596 stored relationships = 71.596 unique triples; cả hai stored multiplicity ratios = 1.
M1 Legacy observations là 56.353, intersection 56.350, project-only 17, Legacy-only 3.
So với #184, project chỉ thêm đúng raw PrimaryGroupSid set gồm 2.593 triples và không mất triple nào.
Nodes, ba unknown assessments và toàn bộ non-MemberOf difference records, gồm provenance/derivation/raw pointers, bằng nguyên records của #184.
15.243 Legacy-only observations ngoài M1 được giữ nguyên trong full local ledger: AllExtendedRights 2.499, Contains 2.816, ExecuteDCOM 1, GenericWrite 3.166, GetChanges 3, GetChangesAll 2, GpLink 2, Owns 3.362, WriteOwner 3.392.
Không remap AllExtendedRights thành ForceChangePassword hoặc đưa các kinds đó vào M1 verdict.

Project export có 56.373 provenance occurrences; Legacy exported provenance occurrences = `null` / not_measurable.
Số provenance occurrences không phải raw fact count: evidence có thể được dùng lại ở derived edges, và raw ACE duplicates có thể coalesce thành một edge.
Raw GenericAll có 37.208 occurrences / 37.044 unique triples, tức 164 occurrences trùng logical triple.
Raw WriteDacl có 3.397 occurrences / 3.395 unique triples, tức 2 occurrences trùng.
Không diễn giải Legacy stored multiplicity = 1 thành Legacy không có duplicate input.

## 3. Semantics từng relation và discrepancy dispositions

Pinned [official importer source](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js), SHA-256 `01e969d83e87217318603887c7f5818a82bc044eead26502f0daf78ac55cad3b`, là rule evidence bổ sung cho exact raw/database observations.
Các source-rule views do A xác định cụ thể cho snapshot này; trạng thái historical machine artifact giữ nguyên `A_source_rule_view_pending_B_review`.
Source of truth cho raw source/direction/direct-derived/unknown-false/disposition hiện hành là [matrix #195](seamless-legacy-403-comparison-contract.md#3-source-of-truth-matrix-cho-tám-relation), thay cho candidate common-semantics table của #194.
Chúng không thay scope comparator hoặc bỏ full difference ledger.
Selection được kiểm tra độc lập với tập triples kỳ vọng từ raw; unexpected/missing triples vẫn hiển thị, không chọn intersection để tự tạo MATCH.
View MemberOf hẹp của script #184 loại PrimaryGroupSid chỉ ở Legacy, nên sau #189 vẫn báo `exact_sets_equal=false`, 2.593 project-unexpected.
Đây là selection bất đối xứng đã cũ; script và output được giữ nguyên, có annotation `historical_memberof_view_limit` trong artifact.
Current full-kind proof nằm ở `by_kind.MemberOf` và `full_memberof_proof`; bốn narrow views khác vẫn exact-equal.

Theo contract #195, full direct MemberOf, non-self GenericAll/WriteDacl, direct AdminTo và direct CanPSRemote dùng `equivalent_in_accepted_scope` cho đúng structural slices khi human acceptance hoàn tất.
Các full-kind differences vẫn được giữ như `accepted_policy_difference`, không sửa materialization để ép counts.
CanRDP không có positive-edge equality claim; hai relation zero-observation giữ `not_measurable`.
Full comparator vẫn `NOT_MEASURABLE`, không nâng thành parity từ narrow views.

### MemberOf: primary-group input gap đã được #189 giải quyết

Exact project MemberOf set = exact Legacy MemberOf set = raw `Members[]` union `PrimaryGroupSid`, với intersection của hai raw source sets rỗng.
Toàn bộ 2.593 triples mới có pointer tới `PrimaryGroupSid`: 2.493 User records + 100 Computer records.
Mỗi project edge mới không có derivation và có positive provenance với attribute `PrimaryGroupSid`, record ID và raw file đúng source record; kiểm tra trên toàn bộ set, không chỉ samples.
Legacy `buildUserJsonNew` / `buildComputerJsonNew` và project [builder direct membership](../../src/parser/builder.py) sau #189 đều materialize field này thành direct MemberOf.
Full project/Legacy/matching set SHA-256 đều `049130749db9649e7352a6061841c521098331899e7522ac4ddb3519e47aefc7`.
Hai difference sets rỗng có digest `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.
Raw primary set và added-project set đều có digest `b5430bf7724fb1521337c99d43abd8d0e208de59a27cb41f02f00f2662d80f66`.
Microsoft xác định primary group là membership được biểu diễn riêng với `primaryGroupID`; `memberOf` chứa direct memberships ngoại trừ primary group: [Security Properties](https://learn.microsoft.com/en-us/windows/win32/ad/security-properties), [Primary-Group-ID](https://learn.microsoft.com/en-us/windows/win32/adschema/a-primarygroupid).
Input gap của #184 đã được kiểm chứng là resolved ở revision này; không giải thích nó bằng transitive closure, session timing hoặc boundary placeholder.
B review User/Computer primary samples và full raw union/provenance proof; acceptance của whole M1 vẫn pending.

### GenericAll / WriteDacl: Legacy self-ACE filter

Exact project GenericAll set = raw unique GenericAll triples; exact Legacy set = cùng raw set sau bỏ self triples.
10 project-only GenericAll đều có source=target và positive raw ACE pointer: Computer 3, Group 5, User 2.
WriteDacl cũng có equality decomposition này; 3 project-only đều là Group self-ACE.
Importer `processAceArrayNew` dòng 572-574 trả null khi `objectid == PrincipalSID`, trước khi decode rights.
Classification `legacy_self_ace_filter` là evidence cho disposition `accepted_policy_difference` ở #195.
Contract chọn common non-self scope đối xứng, giữ positive self-ACE trong full project ledger và không yêu cầu xóa khỏi project hoặc kết luận exploitation value.
Không gán delta 10 cho duplicate removal: 164 GenericAll duplicate occurrences là tầng đo riêng.

### AdminTo / CanRDP và unknowns

4 project-only AdminTo có validated nested_membership derivation; mọi step resolve tới raw Members hoặc LocalAdmins occurrences.
Một matching direct AdminTo đồng thời có nested derivation được coalesce; common direct view vẫn giữ edge khi có direct raw LocalAdmins evidence.
Không drop mọi edge có derivation rồi suy direct subset thiếu cạnh.
3 Legacy-only CanRDP resolve tới RemoteDesktopUsers và đúng 3 canonical unknown assessments, reason `required UserRights evidence is incomplete`; UserRights field vắng trong records đó.
Classification `policy_difference_unknown_userrights` là evidence cho disposition `accepted_policy_difference` ở #195, không chứng minh RDP permission true/false hoặc StatusAccessDenied.
Không có unknown discrepancy category trong M1 ledger của lần đo này; runtime RDP, no-observation relations và Legacy per-edge operation origin vẫn unknown.
Không ép các input/materialization differences vào ADR collector/session-time/trust explanations khi không có evidence.

## 4. Raw trace và evidence để B review

[Research audit](../../scripts/research/reconcile_seamless_legacy.py) dùng validated comparator extraction/mapping/multiplicity helpers trên full exports.
Existing comparator được chạy thật và lưu verdict riêng; vì gate chưa accepted, research audit tính exact observation differences riêng mà không lift `export_complete`.
Full local `evidence.json` chứa mọi project-only/Legacy-only triple, classification, raw array pointers, project edge/provenance/derivation hoặc assessment khi có.
`matching_samples` chứa một sample cho mỗi observed matching M1 kind: MemberOf, GenericAll, WriteDacl, AdminTo, CanPSRemote.
Samples được chọn deterministic từ sorted triples; classification/counts không được tính từ samples.
Committed machine artifact có 11 samples dạng triple SHA-256: 5 matching + matching primary-group User/Computer + GenericAll/WriteDacl self + nested AdminTo + unknown RDP.
`m1_difference_ledger` còn lưu đủ 20 delta M1 dưới dạng triple digest/classification/raw pointers; exact identities nằm ở full local evidence.
Ví dụ review pointers, không chứa raw identities:

| Sample | Raw pointer |
| --- | --- |
| Matching MemberOf | `20210920185958_groups.json#/groups/6/Members/2` |
| Matching GenericAll | `20210920185958_users.json#/users/46/Aces/3` |
| Matching primary Computer | `20210920185958_computers.json#/computers/0/PrimaryGroupSid` |
| Project-only GenericAll self | `20210920185958_users.json#/users/290/Aces/5` |
| Project-only nested AdminTo | `20210920185958_groups.json#/groups/40/Members/3` + `20210920185958_computers.json#/computers/0/LocalAdmins/2` |
| Legacy-only CanRDP | `20210920185958_computers.json#/computers/0/RemoteDesktopUsers/0` |

B's [raw locator helper](../../scripts/research/trace_project_raw_locator.py) được chạy cho 10 project edges: 5 matching + 2 primary memberships + 3 project-only categories; 11 exported provenance records đều located tới raw record.
Trace output digest là `9377880e6b4f4d154835b862bf5d085368666aa4cf6e3565a5f136aa44564771`.
Array pointers của research audit bổ sung locator chính xác tới raw occurrence, còn helper xác nhận project provenance ở record/attribute level.
Legacy không export per-edge raw provenance: ledger giữ `legacy_import_operation_provenance=null`.
Raw occurrence + pinned importer rule + observed triple chứng minh decomposition; nó không tái tạo historical operation trace hoặc chuyển project provenance thành Legacy provenance.

## 5. Tái lập

Dùng virtual environment Python 3.14 và pinned `requirements*.txt`; phiên này dùng Python 3.14.7.
Để tái lập exact project digest, chạy CLI từ checkout `294cba3e2882e4b7a5fbd867aadb8434124612c3`.
Code revision được lưu trong output; rerun trên revision sau phải pin digests mới, không hứa cùng bytes.
Prerequisites là sáu raw files thật match manifest và retained `.cache/issue47/` bundle của #184, gồm full Legacy tables/mapping/comparator input, time policy và importer source.
Native import/capture instructions của lần gốc nằm ở [report #184 tại revision đã pin](https://github.com/nairyuuu/ad-weighted-graph/blob/cd71dd5/docs/research/issue-47-seamless-legacy-403-reconciliation.md#5-tái-lập).
Không chạy replay thẳng từ candidate lịch sử rồi gọi đó là output sau #189.

```bash
PY=/absolute/path/to/project/.venv/bin/python
export RAW_ROOT=/absolute/path/to/data/raw/SEAMLESS
mkdir -p .cache/issue47-post189 .cache/issue47-post189-analysis
"$PY" -m src.parser.cli \
  --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 \
  --raw-dir "$RAW_ROOT" --manifest-dir data/samples/manifests \
  --time-policy .cache/issue47/time-policy.json \
  --created-at 2026-10-01T00:00:00Z --error-policy fail_fast \
  --output .cache/issue47-post189/project.json --summary
"$PY" - <<'PY'
from pathlib import Path
from shutil import copyfile
from scripts.reconcile_graph_baseline import COMPARISON_SCOPE, load_input_json
from scripts.research.reconcile_seamless_legacy import validate_project, require_ignored
from scripts.research.export_legacy_reconciliation_baseline import write_json
bundle = Path('.cache/issue47-post189')
filenames = ('legacy-comparison.json', 'legacy-nodes.json', 'legacy-relationships.json', 'identity-mapping.json')
require_ignored(bundle, (*filenames, 'project-comparison.json'))
for name in filenames:
    copyfile(Path('.cache/issue47') / name, bundle / name)
project = load_input_json(bundle / 'project.json')
validate_project(project)
project['metadata'].update(synthetic=False, export_complete=True,
    source_evidence='data/samples/manifests/seamless-raw-v1.json', comparison_scope=COMPARISON_SCOPE)
write_json(bundle / 'project-comparison.json', project)
assert load_input_json(bundle / 'legacy-comparison.json')['metadata']['export_complete'] is False
PY
"$PY" scripts/research/reconcile_seamless_legacy.py \
  --export-dir .cache/issue47-post189 --raw-root "$RAW_ROOT" \
  --importer-source .cache/issue47/legacy-newingestion.js \
  --output-dir .cache/issue47-post189-analysis
"$PY" scripts/reconcile_graph_baseline.py \
  --candidate .cache/issue47-post189/project-comparison.json \
  --baseline .cache/issue47-post189/legacy-comparison.json \
  --mapping .cache/issue47-post189/identity-mapping.json \
  --output .cache/issue47-post189-analysis/comparator-cli.json --summary
# Comparator exit 2 / NOT_MEASURABLE is the expected pending semantics gate.
```

Comparator outputs có `reconciliation_timestamp` lấy từ clock của từng run; bảng digest pin retained outputs cuối của phiên này, rerun phải cập nhật bindings mới.
CLI output, candidate, exact observation evidence và full raw proof tái lập đúng bytes tại revision/input đã pin.
Time policy là nguyên bytes của #184, digest `3540afa5ff3f4affd9deddd75f3da43409c5885af4ab9b7b2d17a97aac3a2e7b`; collection time vẫn unknown và timestamp_status=assumed.
Audit verify raw/source digests, ba full export digests, comparator table/multiplicity, contract/assessment/snapshot/mapping và exact pending gate.
Mọi sensitive output destination phải ignored, kể cả resolved symlink paths.
Các snippets chỉ orchestrate helper hiện có để kiểm chứng và serialize evidence, không thêm parser/engine/comparator.

Kiểm tra full MemberOf, toàn bộ positive primary provenance và exact delta so với #184:

```bash
"$PY" - <<'PY'
import json, os
from pathlib import Path
from scripts.reconcile_graph_baseline import load_input_json
from scripts.research.reconcile_seamless_legacy import raw_index, require_ignored
from scripts.research.export_legacy_reconciliation_baseline import write_json
from src.data.manifest import load_manifest
root = Path('.cache/issue47-post189-analysis')
bundle = Path('.cache/issue47-post189')
raw_root = Path(os.environ['RAW_ROOT'])
e = load_input_json(root / 'evidence.json')
old = load_input_json(Path('.cache/issue47-analysis/evidence.json'))
graph = load_input_json(bundle / 'project-comparison.json')
previous = load_input_json(Path('.cache/issue47/project-comparison.json'))
mapping = load_input_json(bundle / 'identity-mapping.json')
manifest = load_manifest(Path('data/samples/manifests/seamless-raw-v1.json'))
raw = raw_index(raw_root, manifest, mapping)
files = {f['relative_path']: json.loads((raw_root / f['relative_path']).read_text(encoding='utf-8-sig')) for f in manifest['files']}
sets = {k: {tuple(t) for t in e['exact_triples'][k]} for k in ('project', 'legacy')}
oldsets = {k: {tuple(t) for t in old['exact_triples'][k]} for k in ('project', 'legacy')}
members = {t for t, refs in raw.items() if t[1] == 'MemberOf' and any(r['rule'] == 'Members' for r in refs)}
primary = {t for t, refs in raw.items() if t[1] == 'MemberOf' and any(r['rule'] == 'PrimaryGroupSid' for r in refs)}
full = {k: {t for t in v if t[1] == 'MemberOf'} for k, v in sets.items()}
assert full['project'] == full['legacy'] == members | primary
assert not members & primary
assert sets['project'] - oldsets['project'] == primary
assert not oldsets['project'] - sets['project'] and sets['legacy'] == oldsets['legacy']
assert graph['nodes'] == previous['nodes'] and graph['assessments'] == previous['assessments']
assert [d for d in e['differences'] if d['triple'][1] != 'MemberOf'] == [d for d in old['differences'] if d['triple'][1] != 'MemberOf']
edges = {(x['source'], x['kind'], x['target']): x for x in graph['edges']}
for t in primary:
    assert not edges[t].get('derivation')
    for ref in (r for r in raw[t] if r['rule'] == 'PrimaryGroupSid'):
        filename, pointer = ref['pointer'].split('#', 1)
        collection, index, _ = pointer.strip('/').split('/')
        record = files[filename][collection][int(index)]
        assert (mapping[record['ObjectIdentifier']], 'MemberOf', mapping[record['PrimaryGroupSid']]) == t
        assert any(p['attribute'] == 'PrimaryGroupSid' and p['record_id'] == record['ObjectIdentifier'] and p['raw_file'].endswith('/' + filename) and p['evidence_type'] == 'positive' for p in edges[t]['provenance'])
proof = {'members': sorted(members), 'primarygroup': sorted(primary),
    'members_primarygroup_overlap': sorted(members & primary),
    'project_memberof': sorted(full['project']), 'legacy_memberof': sorted(full['legacy']),
    'project_only': sorted(full['project'] - full['legacy']),
    'legacy_only': sorted(full['legacy'] - full['project']),
    'added_project': sorted(sets['project'] - oldsets['project']),
    'removed_project': sorted(oldsets['project'] - sets['project'])}
require_ignored(root, ('full-kind-proof.json',))
print('Full MemberOf:', len(full['project']), 'proof digest:', write_json(root / 'full-kind-proof.json', proof))
PY
```

Raw locator helper được chạy trên 5 matching samples, matching primary User/Computer và 3 project-only categories.
Chọn deterministic primary sample bằng `min()` của sorted full primary set theo source kind, không paste raw identities vào shell history.
Đối chiếu raw pointers, edge IDs và triple digests trong `sample_ledger` với full local traces khi B review.

## 6. Handoff cho B và #48

B review identity mapping/direction, full MemberOf union/provenance proof, per-kind source semantics và đủ 20 sanitized M1 delta entries.
Primary-group input coverage gap của #184 đã resolved theo dữ liệu thật sau fix của B ở #189.
Self-ACE/nested-admin/CanRDP dispositions theo [contract #195](seamless-legacy-403-comparison-contract.md); B review acceptance của các common slices và policy differences.
CanRDP vẫn là 3 unknown assessments và 0 traversal edges; ForceChangePassword/HasSession vẫn unknown về decoder/session equivalence.
Full MemberOf và bốn narrow views khác có exact equality; Members-only selection bất đối xứng của audit cũ được giữ nguyên và annotated.
Full M1 equivalence, product parity và Week 3 completion chưa accepted; #47/#48 không đóng.
#48 dùng evidence checkpoint integrated `294cba3` này cùng contract #195.
Clean-checkout cross-reproduction ở revision nghiệm thu cuối thuộc #196 sau khi scope #195 được accepted; không thực hiện trong PR tài liệu này.
Required checks và PR review của phép đo được ghi tại [worklog rerun](../worklog/2026-10-05-ttsA-issue47-post189-reconciliation.md); [worklog #184](../worklog/2026-10-04-ttsA-issue47-real-reconciliation.md) giữ historical import evidence.
Checks và handoff contract #195 nằm tại [worklog comparison contract](../worklog/2026-10-05-ttsA-issue195-comparison-contract.md).
