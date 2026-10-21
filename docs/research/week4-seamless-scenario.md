# Scenario SEAMLESS và handoff nghiệm thu - 09/10/2026

Owner TTS A (@Lolavine777), reviewer/cross-reproducer TTS B (@nairyuuu).
Refs #206, #239, #208, #204.
[Freeze độc lập](scenarios/week4-seamless-v1.json) được commit trước lượt public query đầu tiên.
Source baseline là `be64798c89235f53c5c205894a7bac0f96437ce4`; execution revision sạch là `983ce542edad80d5b38d1cce97c7ca5db3b77cb5`.
Source/config bytes của execution revision bằng baseline; các commit đóng gói tài liệu phía sau có revision riêng.
Không sửa engine/parser/catalog/CLI, oracle tổng hợp đã nhận hoặc pin lịch sử.

## Lựa chọn và bằng chứng

Chọn AS-REP vì snapshot đã có V_A enabled/pre-auth off và canonical AdminTo V_A -> C0, không cần đặt thêm structural relationship.
Kerberoasting cần initial authenticated identity và ca đã khảo sát có reset baseline trùng quyền; RBCD còn cần khai báo authorization của P trên tài sản.
Không ghép ba kỹ thuật vào cùng program.
C0 được chọn làm tài sản quản trị theo scenario; giá trị nghiệp vụ/impact chưa có basis, giữ unrated.

| Alias/layer | Input/bằng chứng | Nghĩa và giới hạn |
| --- | --- | --- |
| X / source | Computer record `#/computers/1`, canonical ID resolve qua normalizer | Context thực hiện request được scenario khai báo; không chứng minh host đang controlled |
| V_A / static | User `#/users/1700`, `Properties.enabled`, `Properties.dontreqpreauth` | Enabled/pre-auth off phải known true từ verified raw/SnapshotFacts |
| G_DA / structural | Group `#/groups/40`, `Members/2` chứa V_A | Membership snapshot; không tự tạo effective token hoặc DA checkpoint |
| C0 / asset | Computer `#/computers/0`; canonical AdminTo V_A -> C0 | Raw `#/groups/40/Members/2` + `#/computers/0/LocalAdmins/2` resolve membership/local-admin derivation; không thay runtime admin/auth gates |
| Initial / declaration | `control=[]`, known V_A, request capability `(X,X)` | Không initial material/secret/usable AD identity/admin_control; X khác C0 |
| Derived / branch | material -> secret -> usable `(V_A,X)` -> admin_control(C0) | Effects chỉ sau applicable action, không mutate canonical graph |
| Runtime / RAW | Không khai báo outcomes | KDC/recovery/auth/channel chưa được raw chứng minh, giữ unknown |
| Runtime / ASSUMED | Tám predicate/subject/target trong freeze | True dưới scenario, có declarer/rationale/context; không observed exploit hoặc P=1 |
| Ratings | Không ranking query, không numeric basis | CLI giữ `ranking_disposition=unrated`, `ranking_result=null` |

Snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` gồm sáu files, 11.371.828 bytes.
[Archive đã pin](https://raw.githubusercontent.com/mike-nolan-councilman/Bloodhound_Data/3febc4089421725f9527c187f78d064ad09d5158/20210920185958_BloodHound.zip) có 268.200 bytes, SHA-256 trong freeze.
[Manifest](../../data/samples/manifests/seamless-raw-v1.json) phải verify đủ files trước normalization/build.
Time policy [hiện có](../../tests/fixtures/ranking/seamless_time_policy.json) là filename-based assumed time, không observed collection time.
Builder dùng created_at cố định `2026-10-08T00:00:00Z` theo accepted `seamless_inputs`; không gọi đó là runtime timestamp.
Raw, snapshot envelope, queries và full results giữ ignored/local; public package chỉ có aliases/locators/digests.

## Kỳ vọng trước actual

Allow-list chỉ gồm request, recovery, activation và direct AdminTo action.
Independent proof: initial chỉ request được; material chỉ mở recovery; secret chỉ mở activation; usable V_A mới mở AdminTo tới C0.
Group propagation bị loại khỏi scope, nên không có effective membership và checkpoint phải false dù asset goal true.
Có một direct AdminTo V_A -> C0 trong canonical projection; successful first-goal program kỳ vọng là bốn bước, năm projected states trong freeze.
Expected program thuộc oracle, không được truyền như ordered path vào query.
Không dùng C/P/I để quyết định applicability hoặc sửa expected theo output.

RAW giữ indeterminate ngay request; thiếu recovery chỉ đạt material; known-false admin_channel trong scenario context phủ quyết assumption true và dừng trước asset effect.
Fact false của control là khai báo ca đối chứng, không giả thành observed SEAMLESS fact.
OFF chỉ bỏ request technique, no-request chỉ bỏ initial capability, step-cap chỉ giảm max_steps xuống 3.
Cùng snapshot/assumptions khác giữ nguyên cho mỗi đối chứng.
Coverage/caps phải đọc từ actual; oracle không tự cam kết complete/global minimum từ giới hạn search.

## Chuẩn bị và freeze private input

Dùng checkout sạch tại execution/freeze commit `983ce542edad80d5b38d1cce97c7ca5db3b77cb5`, Python 3.14 trong `.venv`, dependencies theo `requirements-dev.txt`.
Baseline `be64798c` chỉ là code-equivalence pin, chưa chứa document/spec của scenario.
Input preparation ở freeze commit đã đủ để chạy CLI; lấy code audit bổ sung ở PR tài liệu này và chạy trong cùng environment, không sửa tracked files của execution checkout.
Ở worktree có thể dùng Python của venv repo chính với đường dẫn tuyệt đối.
Chạy từ repo root sau khi đặt sáu verified files vào `data/raw/SEAMLESS`.
Code sau chỉ materialize inputs, không chạy engine và không nhận ordered attack path.

```python
import copy
import json
from pathlib import Path
from scripts.research.asrep_inputs import seamless_inputs
from src.parser import IdentityNormalizer, ManifestRawDataLoader
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.cli import load_time_policy
from src.parser.snapshot_facts import serialize_snapshot

spec = json.loads(Path("docs/research/scenarios/week4-seamless-v1.json").read_text())
folder = Path("reports/generated/issue206")
folder.mkdir(parents=True, exist_ok=True)
engine, base, _, trace = seamless_inputs("data/raw/SEAMLESS", spec["revision"])
loader = ManifestRawDataLoader(
    Path("data/samples/manifests/seamless-raw-v1.json"),
    time_policy=load_time_policy(Path("tests/fixtures/ranking/seamless_time_policy.json")),
)
records = IdentityNormalizer().normalize_records(
    adapt_bloodhound_v3_records(loader.load(Path("data/raw/SEAMLESS")))
)
x_ids = {
    r.id
    for r in records
    if r.kind == "Computer"
    for source in r.raw_representations or (r.raw,)
    if source.provenance.get("record_locator") == spec["locators"]["X"]
}
assert len(x_ids) == 1
ids = {
    "X": x_ids.pop(),
    "V_A": base["initial_state"]["known_identity"][0],
    "G_DA": base["checkpoint_goal"]["target"],
    "C0": base["target"],
}
assert ids["X"] != ids["C0"]
raw = copy.deepcopy(base)
raw.update(
    source_foothold=ids["X"],
    initial_actor=ids["X"],
    authentication_context=ids["X"],
    allowed_techniques=spec["allowed_techniques"],
    budget=spec["budget"],
    evaluation_mode=spec["evaluation_mode"],
    scenario_reference=spec["scenario_id"],
)
raw["initial_state"] = {
    "control": [],
    "known_identity": [ids["V_A"]],
    "asrep_request_capability": [[ids["X"], ids["X"]]],
}
assumed = copy.deepcopy(raw)
assumed["assumptions"] = []
for predicate, subject, target in spec["assumptions"]:
    metadata = {"declared_by": spec["declared_by"], "authentication_context": ids["X"]}
    if predicate == "recovery_success":
        metadata.update(spec["recovery_metadata"])
    assumed["assumptions"].append(
        {
            "predicate": predicate,
            "subject": ids[subject],
            "target": ids[target],
            "value": True,
            "scope": spec["scenario_id"],
            "rationale": "Explicit conditional prediction outcome; snapshot lacks runtime evidence",
            "provenance_reference": "scenario://week4-seamless-v1/explicit-outcomes",
            "assumption_metadata": metadata,
        }
    )
variants = {"raw": raw, "assumed": assumed}
for name in ("missing_recovery", "asset_veto", "off", "no_request", "step_cap"):
    variants[name] = copy.deepcopy(assumed)
variants["missing_recovery"]["assumptions"] = [
    f for f in assumed["assumptions"] if f["predicate"] != "recovery_success"
]
variants["asset_veto"]["runtime_facts"] = [
    {
        "predicate": "admin_channel",
        "subject": ids["V_A"],
        "target": ids["C0"],
        "value": False,
        "origin": "blocked_evidence",
        "scope": spec["scenario_id"],
        "rationale": "Declared negative control; not an observed SEAMLESS outcome",
        "provenance_reference": "scenario://week4-seamless-v1/negative-control",
    }
]
variants["off"]["allowed_techniques"].remove("asrep_request")
variants["no_request"]["initial_state"]["asrep_request_capability"] = []
variants["step_cap"]["budget"]["max_steps"] = 3
(folder / "snapshot.json").write_text(
    serialize_snapshot(engine.to_canonical(), engine.snapshot_facts), encoding="utf-8"
)
for name, value in {**variants, "aliases-private": ids, "input-trace": trace}.items():
    (folder / f"{name}.json").write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
```

Freeze SHA-256 bytes của snapshot/query/spec và source/config trước CLI run.
Giữ cả raw manifest verification output; CLI `--prerequisite` chỉ ghi bytes, không thay raw lineage audit.

## Public execution và cross-reproduction

```bash
.venv/bin/python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
sha256sum reports/generated/issue206/snapshot.json reports/generated/issue206/*.json docs/research/scenarios/week4-seamless-v1.json
for case in assumed raw missing_recovery asset_veto off no_request step_cap; do
  .venv/bin/python -m src.engine.query_cli \
    --snapshot reports/generated/issue206/snapshot.json \
    --query "reports/generated/issue206/$case.json" --label seamless \
    --prerequisite data/samples/manifests/seamless-raw-v1.json \
    --prerequisite data/raw/SEAMLESS/20210920185958_users.json \
    --output "reports/generated/issue206/$case-result.json"
done
.venv/bin/python -m src.engine.query_cli \
  --snapshot reports/generated/issue206/snapshot.json \
  --query reports/generated/issue206/assumed.json --label seamless \
  --prerequisite data/samples/manifests/seamless-raw-v1.json \
  --prerequisite data/raw/SEAMLESS/20210920185958_users.json \
  --output reports/generated/issue206/assumed-result-2.json
.venv/bin/python -m scripts.research.compare_query_runs \
  reports/generated/issue206/assumed-result.json reports/generated/issue206/assumed-result-2.json
```

## Actual và disposition - 09/10/2026

[Public evidence](scenarios/week4-seamless-v1-actual.json) được sinh từ full local results bằng code audit bên dưới.
Kỳ vọng SHA-256 `66c5ffef9a10d30d685f437b10d2998b0d57b96c2151c7eb9d00a0feeb0df752` giữ nguyên sau các lượt chạy.

| Case | Actual / verdict | Phạm vi |
| --- | --- | --- |
| ASSUMED | success, một program bốn bước/năm projected states, asset true, checkpoint false | Complete trong allow-list, 4 expansions; conditional, unrated |
| RAW | indeterminate, 0 paths, 1 expansion | Request có KDC/response unknown, không material |
| Missing recovery | indeterminate, 0 paths, 2 expansions | Material có; secret/usable/admin chưa có |
| Asset veto | blocked, 0 paths, 4 expansions | Ba bước prefix; `known_false_veto`, admin false, assumption bị từ chối |
| Extension OFF | no_path, 0 paths, 0 expansions | Scope hẹp, không request producer; không kết luận absence trong AD |
| No request capability | blocked, 0 paths, 1 expansion | Same source/snapshot, chỉ bỏ initial request capability |
| Step cap = 3 | truncated, 0 paths, `step_limit_reached` | Không kết luận no-path hoặc optimal |

All seven rows khớp các trường normative của freeze, bao gồm states, program, prefix/cutoff, veto reason và unrated.
Public evaluator replay từ materialized initial state khớp before/after của từng action do CLI sinh và final state; canonical graph không thay đổi.
Hai process CLI positive có semantic SHA-256 `b2e7bce6c4854f549415327e458215f65e643bbdbf75cc3d71a7d73ce7c7a86e`; compare harness trả equal=true, không so runtime.
Tám assumptions thực sự được dùng được liệt kê bằng alias trong evidence, không chỉ dump tất cả declarations.
Request gắn SnapshotFacts pre-auth evidence; recovery/activation gắn causal parents 0/1; asset action gắn canonical AdminTo và hai provenance records.
Có bốn active operations theo program; không có numeric work-unit ratings/ranking package nên không claim evaluator đã chấm C/P/I hoặc chứng minh Min-Effort.
Gate `admin_channel` là abstraction đã nhận; không gọi actual này là WinRM service-by-service verification.

## Audit và sinh public artifact

Chạy code sau từ root, sau tất cả CLI runs, để kiểm freeze và xuất `reports/generated/issue206/public-summary.json`.
Code chỉ consume outputs, so independent expectations và replay program đã sinh qua public evaluator; không sinh đường hoặc tạo query/search/CLI mới.
Full private IDs không được đưa vào public artifact.
Artifact committed là bản sao bytes của output này; nếu chạy lại, runtime/output byte hashes đổi được, semantic phải giữ đúng compare contract.

```python
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from src.engine.graph import EngineGraph
from src.engine.query import materialize_query
from src.engine.query_cli import wire
from src.engine.semantics.evaluator import PreparedSemanticGraph, evaluate
from src.engine.semantics.transitions import Status, TransitionRequest, apply_transition

folder = Path("reports/generated/issue206")
spec_path = Path("docs/research/scenarios/week4-seamless-v1.json")
frozen_commit = "983ce542edad80d5b38d1cce97c7ca5db3b77cb5"
frozen_bytes = subprocess.check_output(["git", "show", f"{frozen_commit}:{spec_path.as_posix()}"])
assert spec_path.read_bytes() == frozen_bytes
spec = json.loads(frozen_bytes)
ids = json.loads((folder / "aliases-private.json").read_text())
aliases = {value: key for key, value in ids.items()}


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def projection(state):
    fields = [
        ("material", "asrep_material"),
        ("secret", "recovered_secret"),
        ("usable", "usable_identity"),
        ("admin", "admin_control"),
    ]
    return [name for name, field in fields if state[field]]


rows = {}
for name, expected in spec["expected"].items():
    path = folder / f"{name}-result.json"
    result = json.loads(path.read_text())
    actual = result["semantic"]
    prefixes = [projection(a["after"]) for a in actual["attempts"] if a["status"] == "applicable"]
    programs = [
        [t["result"]["request"]["technique_id"] for t in p["transition_history"]]
        for p in actual["candidates"]
    ]
    observed = {
        **{
            k: actual[k]
            for k in [
                "status",
                "final_goal_reached",
                "checkpoint_reached",
                "complete",
                "truncated",
                "truncation_reason",
                "expansions",
                "caps",
                "ranking_disposition",
                "ranking_result",
                "engine_reported_guarantees",
            ]
        },
        "path_count": len(programs),
        "programs": programs,
        "maximum_successful_prefix_steps": max(map(len, prefixes), default=0),
        "rejected_assumption_reasons": [
            r["reason"] for r in actual["materialized"]["rejected_assumptions"]
        ],
    }
    if name == "assumed":
        p = actual["candidates"][0]
        observed["projected_states"] = [projection(p["transition_history"][0]["result"]["before"])]
        observed["projected_states"] += [
            projection(t["result"]["after"]) for t in p["transition_history"]
        ]
    for key, value in {**expected, **spec["rating_expectation"]}.items():
        assert type(observed[key]) is type(value) and observed[key] == value, (name, key)
    rep = result["reproducibility"]
    assert rep["tracked_changes"] == []
    for section in ("source_files", "config_files"):
        for filename, recorded_sha in rep[section].items():
            assert recorded_sha == sha(Path(filename))
            pinned_bytes = subprocess.check_output(
                ["git", "show", f"{spec['revision']}:{filename}"]
            )
            assert recorded_sha == "sha256:" + hashlib.sha256(pinned_bytes).hexdigest()
    assert rep["inputs"]["graph_input"]["sha256"] == sha(folder / "snapshot.json")
    assert rep["inputs"]["query"]["sha256"] == sha(folder / f"{name}.json")
    rows[name] = {
        "oracle_match": True,
        "actual": observed,
        "query_sha256": sha(folder / f"{name}.json"),
        "output_sha256": sha(path),
        "semantic_sha256": rep["semantic_sha256"],
        "effective_config_sha256": rep["effective_config_sha256"],
        "revision": rep["revision"],
        "runtime": result["runtime"],
        "attempt_status_counts": dict(Counter(a["status"] for a in actual["attempts"])),
        "failed_predicates": sorted({p for a in actual["attempts"] for p in a["failed"]}),
        "unknown_predicates": sorted({p for a in actual["attempts"] for p in a["unknown"]}),
    }

primary = json.loads((folder / "assumed-result.json").read_text())
graph = EngineGraph.from_snapshot((folder / "snapshot.json").read_text())
canonical = graph.to_canonical()
query = json.loads((folder / "assumed.json").read_text())
materialized = materialize_query(query, graph)
state = materialized.initial_attack_state
prepared = PreparedSemanticGraph(canonical, snapshot_facts=graph.snapshot_facts)
trace = []
used = set()
for step in primary["semantic"]["candidates"][0]["transition_history"]:
    recorded = step["result"]
    assert wire(state) == recorded["before"]
    request = TransitionRequest(**recorded["request"])
    replay = evaluate(prepared, state, request, materialized.runtime_context, materialized.catalog)
    assert replay.status is Status.APPLICABLE
    state = apply_transition(state, replay)
    assert wire(state) == recorded["after"]
    used |= {
        (f["predicate"], aliases[f["subject"]], aliases[f["target"]])
        for f in recorded["assumption_backed_facts"]
    }
    support = []
    if step["edge_id"] is not None:
        edge = next(e for e in canonical["edges"] if e["id"] == step["edge_id"])
        assert edge["source"] == request.source and edge["target"] == request.target
        support = [
            {k: p[k] for k in ["attribute", "record_locator"] if k in p} for p in edge["provenance"]
        ]
    trace.append(
        {
            "technique": request.technique_id,
            "actor": aliases[request.actor],
            "source": aliases[request.source],
            "target": aliases[request.target],
            "projected_before": projection(recorded["before"]),
            "projected_after": projection(recorded["after"]),
            "derived_from_step": step["derived_from_step"],
            "edge_sha256": step["edge_id"],
            "structural_provenance": support,
            "snapshot_evidence_count": len(recorded["snapshot_evidence"]),
            "decisions": [
                {"predicate": d["predicate"], "origin": d["origin"], "satisfied": d["satisfied"]}
                for d in recorded["decisions"]
            ],
        }
    )
assert state.admin_control == frozenset({ids["C0"]})
assert not state.effective_member
assert wire(state) == primary["semantic"]["candidates"][0]["final_state"]
assert graph.to_canonical() == canonical
assert used == {tuple(f) for f in spec["assumptions"]}
rep = primary["reproducibility"]
second = json.loads((folder / "assumed-result-2.json").read_text())
assert second["semantic"] == primary["semantic"]
assert second["reproducibility"] == rep
subprocess.run(
    ["git", "diff", "--exit-code", spec["revision"], "--", "src", "scripts", "configs"], check=True
)
summary = {
    "scenario_id": spec["scenario_id"],
    "expectations_sha256": sha(spec_path),
    "expectations_frozen_commit": frozen_commit,
    "source_baseline": spec["revision"],
    "execution_revision": rep["revision"],
    "source_equivalence_to_baseline": True,
    "snapshot_id": spec["snapshot_id"],
    "snapshot_envelope_sha256": sha(folder / "snapshot.json"),
    "raw_manifest_sha256": sha(Path("data/samples/manifests/seamless-raw-v1.json")),
    "archive_sha256": sha(Path("data/raw/seamless-pinned.zip")),
    "raw_files": json.loads(Path("data/samples/manifests/seamless-raw-v1.json").read_text())[
        "files"
    ],
    "graph_sha256": json.loads((folder / "snapshot.json").read_text())["graph_sha256"],
    "snapshot_metadata": canonical["metadata"],
    "nodes": len(canonical["nodes"]),
    "edges": len(canonical["edges"]),
    "source_files": rep["source_files"],
    "config_files": rep["config_files"],
    "dependency_files": {
        p: sha(Path(p)) for p in ["requirements.txt", "requirements-dev.txt", ".python-version"]
    },
    "installed_packages": json.loads(
        subprocess.check_output(
            [__import__("sys").executable, "-m", "pip", "list", "--format=json"]
        )
    ),
    "cases": rows,
    "generated_program_trace": trace,
    "actually_used_assumptions": [list(f) for f in sorted(used)],
    "semantic_replay": "all generated before/after states match public evaluator replay",
    "two_process_semantic_equality": True,
    "second_run_runtime": second["runtime"],
    "second_run_output_sha256": sha(folder / "assumed-result-2.json"),
    "cross_reproduction": "pending B human-independent clean-checkout reproduction",
    "remote_ci": "billing blocked before runner execution; no CI PASS",
    "limits": spec["claim_limits"],
}
text = json.dumps(summary, sort_keys=True, indent=2) + "\n"
for private in ids.values():
    assert private not in text
(folder / "public-summary.json").write_text(text, encoding="utf-8")
print("Seven frozen expectations match; semantic replay and identical-input comparison pass")
```

Human-independent cross-reproduction/B review còn pending; hai process cùng máy không thay acceptance đó.
Actions billing/spending-limit chặn trước runner, không ghi CI PASS.
#206/#239/#208/#204 giữ OPEN tới khi các evidence/review gates tương ứng được nhận.
#237/#238 tiếp tục P2 riêng, không lấy prototype làm numeric basis cho scenario.
