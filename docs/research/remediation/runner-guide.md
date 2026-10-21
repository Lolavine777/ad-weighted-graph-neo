# Runner before/after — #284

Runner B consume executor [#283](executor-guide.md), request/result 1.1.0 và
`semantic-program/1`. Sau replay, runner chạy lại native `MaterializedQuery.run`
trên effective views từ cùng executor, gồm nonstructural producers. Không dùng
structural reachability để loại source hoặc suy ra mất mọi đường.

## Tái lập finite bằng một lệnh

Python 3.14, dependencies trong `requirements-tests.txt`; Windows bật UTF-8:

```powershell
$env:PYTHONUTF8 = "1"
python -m scripts.research.remediation_runner --finite --include-individuals --output-dir reports/generated/remediation284/finite
```

Các selected edit sets mặc định: shared membership, shared channel, direct admin.
`--include-individuals` chạy thêm mỗi edit riêng biệt, cùng baseline và cohort;
không cộng các kết quả riêng để giả lập kết quả edit set. Dùng `--fix` lặp lại để
chọn một phần trong ba sets. Mỗi report luôn chứa đủ declared source×goal cells.

| Case | Alice before → after | Bob before → after | Programs cut | Pairs disconnected |
| --- | --- | --- | --- | --- |
| Shared membership | 3 → 1 | 1 → 0 | 3/4 = 75% | 1/2 = 50% |
| Shared channel | 3 → 0 | 1 → 0 | 4/4 = 100% | 2/2 = 100% |
| Direct admin denial | 3 → 1 | 1 → 1 | 2/4 = 50% | 0/2 = 0% |

Đây là finite declared scope, không phải full-source scan hoặc risk/probability
reduction. Native negative proof chỉ đúng cho cùng initial state, typed goal,
profile, model/catalog, snapshot/facts và search caps đã pin.

## Result package và API

Output directory chứa `report-N.json` strict 1.1.0, `package-N.json` với native
artifacts/proofs, `study.json` cho consumer/viewer, `summary.json` và bảng tiếng
Việt `table.md`. Summary/table không có private node IDs. Full package giữ exact
queries, states, decisions và provenance; private inputs chỉ lưu local/ignored.

```python
from src.engine.remediation import prepare_baseline, request_for_baseline
from src.engine.remediation_runner import run_remediation, verify_package

baseline = prepare_baseline(graph, cells, run_id="declared-native-before")
request = request_for_baseline(baseline, selected_edits, request_id="fix-1")
package = run_remediation(request, graph, baseline)
verify_package(package, graph)
```

`cells` là full product của declared source/goal IDs, mỗi cell chứa exact public
query. Source/goal order được canonicalize trước pinning. Initial states được
materialize lại per cell; không lấy terminal state của baseline và không import
facts/effects từ cell hoặc intervention khác. Không nhận fixture result làm
executor output. Invalid pins/preconditions là input errors trước intervention.

CLI cho inputs riêng:

```powershell
python -m scripts.research.remediation_runner --snapshot snapshot.json --cells cells.json --request request-1.1.json --label private --output-dir reports/generated/remediation284/private
```

Có thể dùng `--graph` nếu không cần static facts. `--request` lặp lại cho selected
fixes/edit sets. Requests phải pin baseline hiện tại, gồm actual code revision.
Không tái dùng scope digests của fixture lịch sử.

## Native proof audit

Artifacts là content-addressed `artifact:sha256:...`; trace refs chỉ observation-local,
đi kèm actual native histories và initial/runtime bindings. After proof có exact
after run, query digest, overlay identity, caps, attempts, unresolved feasibility,
native completion/truncation và native no-path guarantee.

`verify_package` tái chạy native discovery và #283 replay rồi đối chiếu reports,
mọi witness, cuts, route cuts, denominators và artifact contents. Self-declared
booleans/digests hoặc proof mượn từ baseline/fix khác không đủ. Mỗi after success
đều phải nằm trong bypass list; new chỉ khi semantic identity chưa có ở before.

`after.complete`/`after.truncated` map đúng native discovery; search exhausted vẫn
có thể unresolved. Zero witnesses + exhausted search chưa đủ disconnected nếu
còn unknown feasibility. Unknown/error/not-run không có negative proof; các
retained replay witnesses hợp lệ vẫn được giữ khi worker timeout/chưa chạy.

Raw collector origin và native evaluator origin được giữ để audit. After proof
bổ sung explicit effective decision audit/intervention refs từ #283, tách scenario
khỏi observed historical facts và derived branch effects.

## Budget, checkpoint và isolation

Dùng `BatchExecutionBudget` và atomic checkpoint machinery của public batch.
`--max-cells`, `--max-expansions`, `--max-seconds`, `--per-query-seconds` áp dụng
cho after workers của từng intervention. Validation, baseline replay và independent
proof audit ngoài worker deadline; elapsed time thực tế có thể dài hơn deadline.

Scheduler reserve nguyên per-cell expansion cap để không thay scope caps giữa
before/after. Automatic rating fallback reserve hai caps. Failed workers không có
expansion count thật nên bị charge toàn reservation; `new_after_expansions` chỉ
đếm completed native results và `charged_expansion_budget` ghi logical accounting.
Remaining budget không đủ reservation thì cell not-run, không bị bỏ denominator.

```powershell
python -m scripts.research.remediation_runner --finite --fix shared-channel --max-cells 1 --checkpoint-dir reports/generated/remediation284/cache --output-dir reports/generated/remediation284/partial
python -m scripts.research.remediation_runner --finite --fix shared-channel --checkpoint-dir reports/generated/remediation284/cache --resume --output-dir reports/generated/remediation284/resumed
```

Cache scope chứa full request, baseline/native corpus, profile/budget/model/code/
runtime pins và intervention identity. Không reuse baseline làm after hoặc fix khác.
Completed cached cells được **re-execute để audit native proof**, ghi riêng trong
`cache_audit_reexecuted_cells`; chưa claim cache tăng tốc. Incomplete/error cells
không cache thành complete negatives. Wall boundaries phụ thuộc máy; chỉ logical
scope và completed semantic outputs có deterministic parity.

Transport `summary.evaluated_pairs` theo verifier nghĩa là represented matrix rows.
Package analytics tách declared/evaluated-after/not-run, completion, unresolved
feasibility, unknown replay và actual worker coverage. Unsupported edits giữ đủ
cells với typed diagnostics, không giả apply hoặc disconnect.

## Inventory, priority và numeric availability

`inventory_interventions` lấy candidates từ observed canonical edges **và** actual
semantic prerequisites/artifacts, gồm preauth cho path không có structural producer
edges. Mỗi candidate có technical edits, exact evidence/dependency scope, native
prerequisites và supported/unsupported reason. Inventory chỉ observed corpus, không
claim exhaustive fixes/global choke points. Không đề xuất mặc định xóa node.

Policy đề xuất `defensive-complete-scope-first/2` sort lexicographic: ít incomplete
observations hơn; nhiều proven disconnected pairs hơn; ít source×goal pairs chưa
xác định after reachability hơn; ít exposed sources còn lại hơn; nhiều observed
cuts hơn; tie bằng intervention ID. Unknown/error/unsupported/not-evaluated không
được coi như an toàn vì thiếu witness. Reachable vẫn là bằng chứng exposure khi
search incomplete; proven-unreachable phải có native proof. Đếm uncertainty per
pair, kể cả source đã reachable với goal khác. Bản /1 trong historical summaries
giữ nguyên; không dùng để claim thứ hạng hiện tại. Chỉ rank cùng comparison
scope/configured goals. Counterexample trong tests: capped/not-run run có 100%
observed cuts vẫn xếp sau complete run có 75% cuts. Same-quantity ties ổn định theo
ID. Policy/ties chờ A review, không claim operational optimum hoặc budget optimizer.

Automatic C được resolve lại bằng native accepted providers với fresh query scope,
giữ registry releases/model. Delta chỉ khi cả hai native minima certified, cùng typed
goal/context và không capped/unknown; incumbent không có exact delta. Explicit old
ranking packets bị refuse cho after. Synthetic test 1 → 4 không phải numeric adoption.
P/I cross-intervention comparability chưa được reviewed adapter chứng minh nên giữ
incomparable/unrated null. Không tổng route P, không P=0 do hardening, không lấy
attacker C hoặc runtime làm defender cost/operational impact.

## Bounded SEAMLESS pilot

```powershell
python -m scripts.research.remediation_runner --seamless-raw-dir <authorized-private-directory> --output-dir reports/generated/remediation284/seamless
```

Verify sáu raw files trước/sau. Pilot có one declared requester, one host goal,
four-technique allow-list, native caps 10 paths/6 steps/1000 expansions. Cases:
channel denial; membership-only ineffective fix với retained direct bypass; missing
recovery; step cap 3. Unknown/capped controls không chứng minh disconnect. Public
summary ghi elapsed runtime và observed process peak RSS (gồm loading/audit), không
private graph/IDs/traces hoặc claim full-source scan.

Opt-in raw test: đặt `REMEDIATION284_RUN_RAW_PILOT` đến authorized raw directory.
Thiếu raw là explicit skip/pending; không thay bằng synthetic gắn nhãn raw.
Remote CI giữ pending theo yêu cầu user. A exact-head review/cross-run và policy
review vẫn là acceptance gates; không tự đóng #265/#269/#283.

Public local evidence: [finite table](../../../reports/research/issue284-finite-table.md),
[bounded raw table](../../../reports/research/issue284-seamless-table.md). Raw pilot
704.525 s, peak process RSS 586,801,152 bytes; private native packages giữ local.
Pilot trước thay đổi cuối chỉ normalize code-pin path separators; A exact-head
cross-reproduction vẫn pending.

