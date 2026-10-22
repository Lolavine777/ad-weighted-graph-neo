"""Inventory snapshot-derived goals and independent compromise scenarios, then assess them.

This command composes the existing batch planner and verified remediation runner.
Selection criteria are technical triage, never business-impact or probability ratings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from jsonschema.exceptions import ValidationError

from scripts.research.source_goal_batch import (
    BatchQueryRequest,
    TargetManifest,
)
from src.engine.batch import (
    BatchExecutionBudget,
    _atomic_json,
    run_source_goal_batch,
    validate_schema,
)
from src.engine.graph import EngineGraph
from src.engine.query_cli import digest, read_input
from src.engine.ranking.resolution_service import canonical_digest
from src.parser.snapshot_facts import graph_digest

VERSION = "exposure-inventory/1.0.0"
DOMAIN_SID = re.compile(r"S-1-5-21-\d+-\d+-\d+$")
SID_REFERENCE = (
    "https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/"
    "understand-security-identifiers"
)


def inventory_exposure(graph, *, target_scope="important", domain_sid=None):
    """Enumerate candidates without reachability prefilters or inferred credentials.

    Important = observed DA/EA role SIDs, direct DC/RODC membership, or a Group's
    admincount marker (which may be stale). All = every non-boundary Group/Computer.
    Other technical/business goals remain outside this explicitly declared universe.
    """
    if target_scope not in {"important", "all"}:
        raise ValueError("target_scope must be important or all")
    nodes = graph.nodes()
    domains = [n for n in nodes if n["kind"] == "Domain" and DOMAIN_SID.fullmatch(n["id"])]
    if domain_sid is None:
        if len(domains) != 1:
            raise ValueError("Select --domain-sid from observed canonical Domain SID nodes")
        domain = domains[0]
    else:
        domain = next((n for n in domains if n["id"] == domain_sid), None)
        if domain is None:
            raise ValueError("domain_sid must identify an observed canonical Domain SID node")
    domain_sid = domain["id"]
    scoped = [n for n in nodes if n["domain"].casefold() == domain["domain"].casefold()]
    dc_support = {}
    for edge in graph.edges():
        if edge["kind"] == "MemberOf" and edge["target"] in {
            domain_sid + "-516",
            domain_sid + "-521",
        }:
            dc_support.setdefault(edge["source"], []).append(edge["id"])
    sources, targets, exclusions = [], [], Counter()
    for node in sorted(scoped, key=lambda n: n["id"]):
        kind, node_id = node["kind"], node["id"]
        if kind in {"User", "Computer"} and not node["is_boundary"]:
            if node.get("enabled") is False:
                exclusions["source_disabled"] += 1
            else:
                sources.append(
                    {
                        "node_id": node_id,
                        "node_kind": kind,
                        "label": node["label"],
                        "enabled_status": "known_true"
                        if node.get("enabled") is True
                        else "unknown",
                    }
                )
        else:
            exclusions["source_boundary_or_unsupported_kind"] += 1
        if kind not in {"Group", "Computer"} or node["is_boundary"]:
            exclusions["target_boundary_or_unsupported_kind"] += 1
            continue
        reason, priority, support = "all_supported_targets", 2, []
        category = "custom"
        if kind == "Group" and node_id in {domain_sid + "-512", domain_sid + "-519"}:
            reason, priority, category = "well_known_privileged_group_sid", 0, "tier_0_identity"
        elif kind == "Computer" and node_id in dc_support:
            reason, priority, category = "observed_dc_group_membership", 0, "tier_0_host"
            support = sorted(dc_support[node_id])
        elif kind == "Group" and node.get("admincount") in (True, 1):
            reason, priority, category = (
                "admincount_marker_not_privilege_proof",
                1,
                "high_value_asset",
            )
        elif target_scope == "important":
            exclusions["target_not_selected_by_important_criteria"] += 1
            continue
        goal_id = f"auto-{priority}-" + canonical_digest([node_id, kind]).removeprefix("sha256:")
        goal = {
            "goal_id": goal_id,
            "category": category,
            "target_node_id": node_id,
            "target_node_kind": kind,
            "display_name": node["label"],
            "technical_consequence": (
                "attacker_usable_group_entitlement" if kind == "Group" else "host_admin_execution"
            ),
            "impact_rating": "Unknown",
            "required_control_level": "admin_entitlement"
            if kind == "Group"
            else "host_admin_execution",
            "required_state": {} if kind == "Group" else {"admin_control": [node_id]},
            "provenance_locator": f"canonical-node:{node_id}",
            "description": "Automatically selected technical goal; business impact is unreviewed.",
        }
        if kind == "Group":
            goal["goal_kind"] = "usable_identity_entitlement"
        targets.append(
            {
                "goal": goal,
                "selection_reason": reason,
                "technical_priority": priority,
                "supporting_edge_ids": support,
            }
        )
    sources.sort(key=lambda s: (s["node_kind"], s["node_id"]))
    targets.sort(key=lambda t: (t["technical_priority"], t["goal"]["goal_id"]))
    return {
        "schema_version": VERSION,
        "snapshot_id": graph.metadata["snapshot_id"],
        "graph_sha256": graph_digest(graph.to_canonical()),
        "domain_sid": domain_sid,
        "target_scope": target_scope,
        "sources": sources,
        "targets": targets,
        "counts": {
            "eligible_sources": len(sources),
            "eligible_targets": len(targets),
            "potential_pairs": len(sources) * len(targets),
        },
        "exclusions": dict(sorted(exclusions.items())),
        "source_semantics": (
            "Independent hypothetical compromise per source, never pooled capabilities"
        ),
        "target_semantics": (
            "Group entitlement requires the same usable identity in source Computer context; "
            "Computer requires admin_control"
        ),
        "criteria_reference": SID_REFERENCE,
        "implementation_sha256": digest(Path(__file__).read_bytes()),
        "limitations": [
            "Single selected domain; trusts and cross-domain goals are outside this inventory.",
            "admincount can be stale; it selects a candidate, never proves current privilege.",
            "No label-based role detection or structural reachability pruning.",
            "User credential goals, GPO/OU and business assets need other explicit goal types.",
            "Important criteria are incomplete; all expands only the Group/Computer goal universe.",
        ],
    }


def build_request(
    graph,
    inventory,
    *,
    source_ids=None,
    authentication_context=None,
    user_profile="user_leaked_password",
    computer_profile="computer_control_user",
    machine_identity_provenance=None,
    max_sources=20,
    max_targets=50,
    evaluation_mode="evidence_only",
    assumptions=(),
    budget=None,
    rating_resolution=None,
):
    """Compile an auditable bounded cohort; no target IDs or paths need be supplied."""
    if inventory["graph_sha256"] != graph_digest(graph.to_canonical()):
        raise ValueError("Inventory belongs to another graph projection")
    if user_profile not in {"user_leaked_password", "user_usable_identity"}:
        raise ValueError("Invalid user compromise profile")
    if computer_profile not in {
        "computer_control_user",
        "computer_control_admin",
        "computer_usable_identity",
    }:
        raise ValueError("Invalid computer compromise profile")
    if machine_identity_provenance is not None and computer_profile != "computer_usable_identity":
        raise ValueError("Machine identity provenance requires computer_usable_identity profile")
    if any(type(n) is not int or n < 0 for n in (max_sources, max_targets)):
        raise ValueError("Selection caps must be nonnegative integers; 0 means all")
    candidates = inventory["sources"]
    if source_ids is not None:
        requested = set(source_ids)
        if not requested or requested - {s["node_id"] for s in candidates}:
            raise ValueError("Every --source must be an eligible User/Computer node ID")
        candidates = [s for s in candidates if s["node_id"] in requested]
    selected = candidates[:max_sources] if max_sources else candidates
    targets = inventory["targets"][:max_targets] if max_targets else inventory["targets"]
    if not selected or not targets:
        raise ValueError("No eligible sources or goals in the selected scope")
    sources = []
    for candidate in selected:
        node_id, kind = candidate["node_id"], candidate["node_kind"]
        machine_identity = kind == "Computer" and computer_profile == "computer_usable_identity"
        if machine_identity and (
            not isinstance(machine_identity_provenance, str)
            or not machine_identity_provenance.strip()
        ):
            raise ValueError("computer_usable_identity requires --machine-identity-provenance")
        context = authentication_context if kind == "User" or machine_identity else node_id
        if context is None or graph.node(context)["kind"] != "Computer":
            raise ValueError(
                "Identity profiles require explicit --authentication-context Computer ID"
            )
        source = {
            "source_id": "source-" + kind.lower() + "-" + canonical_digest(node_id)[7:],
            "node_id": node_id,
            "node_kind": kind,
            "profile_kind": user_profile if kind == "User" else computer_profile,
            "authentication_context": context,
            "declared_assumptions": list(assumptions),
            "description": "Independent declared compromise scenario; not observed compromise",
            **(
                {"identity_provenance_reference": machine_identity_provenance}
                if machine_identity
                else {}
            ),
        }
        sources.append(source)
    manifest = TargetManifest.from_dict(
        {
            "manifest_id": "auto-exposure-targets",
            "version": "1.0.0",
            "snapshot_id": inventory["snapshot_id"],
            "domain_sid": inventory["domain_sid"],
            "targets": [t["goal"] for t in targets],
            "description": "Snapshot-derived technical candidates; impact remains Unknown",
        }
    ).to_dict()
    validate_schema(manifest, "target-manifest")
    request = {
        "schema_version": (
            "batch-query-request/1.1.0"
            if any(s["profile_kind"] == "computer_usable_identity" for s in sources)
            else "batch-query-request/1.0.0"
        ),
        "batch_id": "auto-exposure",
        "snapshot_id": inventory["snapshot_id"],
        "target_manifest": manifest,
        "sources": sources,
        "target_goal_ids": None,
        "evaluation_mode": evaluation_mode,
        "common_budget": budget or {"max_paths": 5, "max_steps": 4, "max_expansions": 100},
    }
    if rating_resolution is not None:
        request["rating_resolution"] = rating_resolution
    # Native decoding validates declared profiles/budgets without mutating registries.
    request = BatchQueryRequest.from_dict(request).to_dict()
    validate_schema(request, "batch-query-request")
    selected_pairs = len(sources) * len(targets)
    selection = {
        **inventory["counts"],
        "source_selector": "all_eligible" if source_ids is None else sorted(set(source_ids)),
        "selected_sources": len(sources),
        "selected_targets": len(targets),
        "selected_pairs": selected_pairs,
        "inventory_pairs_outside_selected_cohort": inventory["counts"]["potential_pairs"]
        - selected_pairs,
        "max_sources": max_sources,
        "max_targets": max_targets,
        "all_inventory_pairs_selected": selected_pairs == inventory["counts"]["potential_pairs"],
        "selection_policy": (
            "deterministic technical priority then stable IDs; no reachability or risk assertion"
        ),
    }
    return request, selection


def remediation_cells(result, *, max_sources=2, max_targets=0):
    """Select a rectangular executed subset, preserving every query exactly."""
    queries = result["reproducibility"]["inputs"]["public_queries"]
    goals = sorted({g for row in result["source_goal_matrix"].values() for g in row})
    if max_targets:
        goals = goals[:max_targets]
    rows = []
    for sid in sorted(result["source_goal_matrix"]):
        row = []
        for gid in goals:
            trace = queries[canonical_digest([sid, gid])]
            if "query" not in trace:
                break
            row.append({"source_id": sid, "goal_id": gid, "query": trace["query"]})
        else:
            rows.append(row)
    if max_sources:
        rows = rows[:max_sources]
    return [cell for row in rows for cell in row]


def evaluate_interventions(
    graph, result, *, limit, max_sources, output_dir, execution_budget, max_targets=0
):
    """Compose existing replay/rediscovery; observed path frequency is not effectiveness."""
    from scripts.defender_brief import remediation_outcome
    from src.engine.remediation import prepare_baseline
    from src.engine.remediation_runner import (
        inventory_interventions,
        rank_interventions,
        requests_from_inventory,
        run_remediation,
    )

    cells = remediation_cells(result, max_sources=max_sources, max_targets=max_targets)
    if not cells:
        return {"status": "not_executed", "reason": "No complete executed query row", "pairs": 0}
    _atomic_json(output_dir / "remediation-cells.json", cells)
    baseline = prepare_baseline(graph, cells, run_id="auto-exposure-remediation")
    inventory = inventory_interventions(graph, baseline)
    _atomic_json(output_dir / "intervention-inventory.json", inventory)
    requests = requests_from_inventory(baseline, inventory, limit=limit)
    packages = []
    references = []
    for i, request in enumerate(requests):
        package = run_remediation(request, graph, baseline, execution_budget=execution_budget)
        path = output_dir / f"intervention-{i}.json"
        _atomic_json(path, package)
        references.append({"path": path.name, "sha256": digest(path.read_bytes())})
        packages.append(package)
    return {
        "status": "executed",
        "pairs": len(cells),
        "sources": len({c["source_id"] for c in cells}),
        "goals": len({c["goal_id"] for c in cells}),
        "scope": "Rectangular executed query subset only; never domain-wide risk reduction",
        "discovery_pairs_outside_remediation": result["summary"]["declared_cells"] - len(cells),
        "inventory_candidates": len(inventory["candidates"]),
        "evaluated_interventions": len(requests),
        "packages": references,
        "ranking": rank_interventions(packages) if packages else None,
        "outcomes": [remediation_outcome(graph, package) for package in packages],
        "optimal_intervention_claim": False,
    }


def overview_report(request, result, selection):
    """Readable triage with exact trace references kept in the full result package."""
    sources = {s["source_id"]: s["node_id"] for s in request["sources"]}
    goals = {g["goal_id"]: g["display_name"] for g in request["target_manifest"]["targets"]}
    successes = [
        (sid, gid, cell)
        for sid, row in sorted(result["source_goal_matrix"].items())
        for gid, cell in sorted(row.items())
        if cell["final_goal_reached"]
    ]
    policy = result["reproducibility"]["inputs"].get("scenario_policy")
    policy_description = (
        f"Scenario profile: {policy['profile']['profile_id']} ({policy['digest']}). "
        "Mỗi query giữ assumptions/rejections và provenance riêng trong trace."
        if policy is not None
        else "Không tự biên dịch scenario assumptions khi chưa chọn profile."
    )
    effort = result["reproducibility"]["inputs"].get("effort_profile")
    lines = [
        "# Phơi nhiễm từ các kịch bản compromise độc lập",
        "",
        f"Inventory: {selection['eligible_sources']} nguồn, {selection['eligible_targets']} "
        f"mục tiêu; đã chọn {selection['selected_sources']} × {selection['selected_targets']} "
        f"= {selection['selected_pairs']} cặp.",
        f"Ngoài cohort: {selection['inventory_pairs_outside_selected_cohort']} cặp ứng viên. "
        f"Trong cohort chưa chạy: {len(result['summary']['not_run_cells'])} cặp.",
        "",
        "Mục tiêu được chọn theo tiêu chí kỹ thuật, không phải business impact đã chấm. "
        "Có witness nghĩa là đạt theo model/facts/giả định đã khai báo; "
        "thiếu kết quả không phải an toàn.",
        f"Evaluation mode: {request['evaluation_mode']}. "
        "Scenario assumptions là giả định có điều kiện, không phải quan sát hoặc P=1.",
        policy_description,
        (
            f"C profile: {effort['profile_id']}; ordinal scenario effort, không phải thời gian. "
            + (
                "Reset, membership, ACL và thực thi host/WinRM trong scope profile; P/I bổ trợ."
                if effort["profile_id"] == "neo-c-v1"
                else "Chỉ reset trực tiếp/activation đúng owner/context; không adoption P/I."
            )
            if effort is not None
            else "C cần basis áp dụng; chưa chấm không phải C=0."
        ),
        *(
            [
                "Local Computer profiles chỉ khai báo quyền trên host; sử dụng ACL/group của "
                "tài khoản máy cần usable_identity đúng context. computer_usable_identity "
                "khai báo riêng network identity có provenance; "
                "không cấp host admin hoặc danh tính User.",
                "recover_session_credential_material chỉ tạo material chưa định kiểu. "
                "use_session_identity cần quyền admin trên host và giả định/evidence về "
                "session còn dùng được. no_path chỉ có hiệu lực trong scope đã khai báo.",
            ]
            if any(s["node_kind"] == "Computer" for s in request["sources"])
            else []
        ),
        "",
        "Trạng thái: " + json.dumps(result["summary"]["status_counts"], sort_keys=True),
        "",
        f"Có witness: {len(successes)} cặp. Bảng hiển thị tối đa 100; "
        "result.json giữ đủ cells, traces, assumptions, witnesses và proof flags.",
        "",
        "| Nguồn | Mục tiêu | Trạng thái | C tìm thấy | Kỹ thuật trong witness |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sid, gid, cell in successes[:100]:
        witness = cell.get("min_effort_path") or {}
        steps = ", ".join(witness.get("steps", [])) or "initial capability / xem trace"
        values = [
            sources[sid],
            goals[gid],
            cell["status"],
            str(cell["min_effort"]) if cell["min_effort"] is not None else "chưa chấm",
            steps,
        ]
        lines.append(
            "| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in values) + " |"
        )
    lines += [
        "",
        "C là union work-unit effort nếu có basis áp dụng; không lấy số bước làm C. "
        "Best found không tự có nghĩa global minimum. P chưa chấm không phải P=0.",
        "",
        "Nếu bật remediation, summary.json trỏ tới full verified packages. "
        "Program elimination và source–goal disconnection là hai đại lượng riêng; "
        "cohort can thiệp có thể hẹp hơn cohort discovery.",
    ]
    return "\n".join(lines) + "\n"


def archive_outputs(folder):
    """Preserve previous output bytes with a hash index before an explicit resume."""
    names = {
        "inventory.json",
        "request.json",
        "selection.json",
        "result.json",
        "summary.json",
        "overview.md",
        "checkpoint.json",
        "defender-brief.json",
        "defender-brief.md",
        "discovery-progress.jsonl",
        "remediation-cells.json",
        "intervention-inventory.json",
    }
    paths = {folder / name for name in names} | set(folder.glob("intervention-*.json"))
    history = folder / "history"
    history.mkdir(exist_ok=True)
    saved = []
    for path in sorted(paths):
        if not path.exists():
            continue
        raw = path.read_bytes()
        sha256 = digest(raw)
        destination = history / (path.stem + "-" + sha256[7:] + path.suffix)
        if destination.exists():
            if digest(destination.read_bytes()) != sha256:
                raise ValueError("Historical output bytes changed")
        else:
            destination.write_bytes(raw)
        saved.append(
            {
                "original": path.name,
                "archive": destination.relative_to(folder).as_posix(),
                "sha256": sha256,
                "bytes": len(raw),
            }
        )
    _atomic_json(history / (canonical_digest(saved)[7:] + "-index.json"), saved)
    return saved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--snapshot")
    inputs.add_argument("--graph")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue the same generated request; preserve prior reports by hash",
    )
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--domain-sid")
    parser.add_argument(
        "--source", action="append", help="Compromised node ID; omit for all eligible sources"
    )
    parser.add_argument(
        "--authentication-context", help="Declared Computer context for User or machine identities"
    )
    parser.add_argument("--target-scope", choices=("important", "all"), default="important")
    parser.add_argument(
        "--user-profile",
        choices=("user_leaked_password", "user_usable_identity"),
        default="user_leaked_password",
    )
    parser.add_argument(
        "--computer-profile",
        choices=("computer_control_user", "computer_control_admin", "computer_usable_identity"),
        default="computer_control_user",
    )
    parser.add_argument(
        "--machine-identity-provenance",
        help="Required declaration reference for computer_usable_identity; not observed proof",
    )
    parser.add_argument(
        "--evaluation-mode",
        choices=("scenario", "evidence_only"),
        help="Defaults to scenario when a scenario policy is selected; otherwise evidence_only",
    )
    parser.add_argument(
        "--assumptions", help="Explicit RuntimeFact declarations, never fabricated from inventory"
    )
    parser.add_argument(
        "--scenario-policy",
        choices=("neo-standard-v1", "seamless-standard-v1"),
        help="Compile the existing snapshot-bound assumptions and select scenario mode",
    )
    parser.add_argument("--runtime-facts")
    parser.add_argument("--rating-resolution")
    parser.add_argument(
        "--effort-profile",
        choices=("reset-activation-c-v1", "reset-activation-c-v2", "neo-c-v1"),
        help="Opt-in C-only effort; neo-c-v1 covers reset, membership, ACL and host execution",
    )
    parser.add_argument("--technique", action="append")
    parser.add_argument("--search-order", choices=("fifo", "goal_guided", "neo_guided"))
    parser.add_argument(
        "--max-sources", type=int, default=20, help="0 selects all eligible/explicit sources"
    )
    parser.add_argument(
        "--max-targets", type=int, default=50, help="0 selects all inventory targets"
    )
    parser.add_argument("--max-paths", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--max-expansions", type=int, default=100)
    parser.add_argument("--max-cells", type=int, default=100)
    parser.add_argument("--global-max-expansions", type=int, default=10000)
    parser.add_argument(
        "--global-seconds",
        type=float,
        help="Optional wall deadline; native isolation reloads a graph per worker",
    )
    parser.add_argument("--query-seconds", type=float)
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=25,
        help=(
            "Flush every N newly cacheable cells, plus a final flush; interruption may repeat "
            "up to N cacheable cells. Incomplete cells always need re-execution."
        ),
    )
    parser.add_argument(
        "--remediate", type=int, default=0, help="Evaluate up to N mined interventions"
    )
    parser.add_argument(
        "--remediation-sources", type=int, default=2, help="0 uses all executed full rows"
    )
    parser.add_argument(
        "--remediation-targets", type=int, default=2, help="0 uses all selected goals"
    )
    args = parser.parse_args(argv)
    args.search_order = args.search_order or (
        "neo_guided" if args.effort_profile == "neo-c-v1" else "fifo"
    )
    args.evaluation_mode = args.evaluation_mode or (
        "scenario" if args.scenario_policy else "evidence_only"
    )
    references = {}
    started = time.perf_counter()
    try:
        if args.output_dir.exists() and not args.resume:
            raise ValueError(
                "Output directory exists; preserve prior run and choose a new directory"
            )
        if args.scenario_policy is not None and args.evaluation_mode != "scenario":
            raise ValueError("--scenario-policy requires explicit --evaluation-mode scenario")
        if args.effort_profile and args.rating_resolution:
            raise ValueError("--effort-profile conflicts with --rating-resolution")
        if args.resume and (
            args.inventory_only
            or not (args.output_dir / "checkpoint.json").is_file()
            or not (args.output_dir / "request.json").is_file()
        ):
            raise ValueError("Resume requires an existing request/checkpoint, not inventory-only")
        if args.remediate < 0 or args.remediation_sources < 0 or args.remediation_targets < 0:
            raise ValueError("Remediation limits must be nonnegative")
        payload = read_input(
            args.snapshot or args.graph, references, "snapshot" if args.snapshot else "graph"
        )
        graph = (
            EngineGraph.from_snapshot(json.dumps(payload))
            if args.snapshot
            else EngineGraph.from_canonical(payload)
        )
        graph_loaded = time.perf_counter()
        inventory = inventory_exposure(
            graph, target_scope=args.target_scope, domain_sid=args.domain_sid
        )
        inventory_done = time.perf_counter()
        args.output_dir.mkdir(parents=True, exist_ok=args.resume)
        if args.inventory_only:
            _atomic_json(args.output_dir / "inventory.json", inventory)
            print(json.dumps(inventory["counts"], sort_keys=True))
            return 0
        request, selection = build_request(
            graph,
            inventory,
            source_ids=args.source,
            authentication_context=args.authentication_context,
            user_profile=args.user_profile,
            computer_profile=args.computer_profile,
            machine_identity_provenance=args.machine_identity_provenance,
            max_sources=args.max_sources,
            max_targets=args.max_targets,
            evaluation_mode=args.evaluation_mode,
            assumptions=read_input(args.assumptions, references, "assumptions")
            if args.assumptions
            else (),
            budget={
                "max_paths": args.max_paths,
                "max_steps": args.max_steps,
                "max_expansions": args.max_expansions,
            },
            rating_resolution=read_input(args.rating_resolution, references, "rating_resolution")
            if args.rating_resolution
            else None,
        )
        limits = BatchExecutionBudget(
            args.max_cells, args.global_max_expansions, args.global_seconds, args.query_seconds
        )
        previous_artifacts = []
        if args.resume:
            previous_request = json.loads((args.output_dir / "request.json").read_text())
            if request != previous_request:
                raise ValueError("Generated request changed; choose a new cohort/output directory")
            previous_artifacts = archive_outputs(args.output_dir)
        else:
            _atomic_json(args.output_dir / "inventory.json", inventory)
            _atomic_json(args.output_dir / "request.json", request)
            _atomic_json(args.output_dir / "selection.json", selection)
        request_done = time.perf_counter()
        progress_path = args.output_dir / "discovery-progress.jsonl"
        progress_written = False
        source_nodes = {s["source_id"]: s["node_id"] for s in request["sources"]}
        goal_nodes = {
            g["goal_id"]: g["target_node_id"] for g in request["target_manifest"]["targets"]
        }

        def report_cell(event):
            nonlocal progress_written
            event["elapsed_seconds"] = time.perf_counter() - started
            with progress_path.open("a" if progress_written else "w", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            progress_written = True
            source_label = graph.node(source_nodes[event["source_id"]])["label"]
            goal_label = graph.node(goal_nodes[event["goal_id"]])["label"]
            status = "đã có đường" if event["reached"] else event["status"]
            cost = event["C"] if event["C"] is not None else "chưa chấm"
            print(
                f"{source_label} → {goal_label}: {status}; C tìm thấy={cost}",
                file=sys.stderr,
                flush=True,
            )

        result = run_source_goal_batch(
            request,
            graph,
            allowed_techniques=args.technique,
            runtime_facts=read_input(args.runtime_facts, references, "runtime_facts")
            if args.runtime_facts
            else (),
            execution_budget=limits,
            checkpoint=args.output_dir / "checkpoint.json",
            checkpoint_interval=args.checkpoint_interval,
            resume=args.resume,
            scenario_policy=args.scenario_policy,
            effort_profile=args.effort_profile,
            search_order=args.search_order,
            on_cell=report_cell,
        ).to_dict()
        if not progress_written:
            progress_path.write_text("", encoding="utf-8")
        search_done = time.perf_counter()
        if args.resume:
            _atomic_json(args.output_dir / "inventory.json", inventory)
            _atomic_json(args.output_dir / "request.json", request)
            _atomic_json(args.output_dir / "selection.json", selection)
        _atomic_json(args.output_dir / "result.json", result)
        serialized = time.perf_counter()
        counts = {k: v for k, v in result["summary"].items() if k != "not_run_cells"}
        counts["not_run_cells_count"] = len(result["summary"]["not_run_cells"])
        summary = {
            "version": VERSION,
            "selection": selection,
            "batch": counts,
            "execution_budget": asdict(limits),
            "input_files": references,
            "implementation_sha256": digest(Path(__file__).read_bytes()),
            "resume": {"enabled": args.resume, "previous_artifacts": previous_artifacts},
            "search_strategy": (
                f"Per-source/per-goal {args.search_order}; prepared reuse, not shared traversal; "
                "unsupported goal/catalog falls back to FIFO"
            ),
            "progress": {"path": progress_path.name, "sha256": digest(progress_path.read_bytes())},
            "impact": "Unknown unless separately bound by an applicable numeric registry",
            "evaluation_mode": request["evaluation_mode"],
            "scenario_policy": result["reproducibility"]["inputs"].get("scenario_policy"),
            "effort_profile": result["reproducibility"]["inputs"].get("effort_profile"),
            "elapsed_seconds": time.perf_counter() - started,
            "phase_seconds": {
                "load_and_validate_graph": graph_loaded - started,
                "inventory": inventory_done - graph_loaded,
                "compile_and_write_request": request_done - inventory_done,
                "batch_search_and_audit": search_done - request_done,
                "serialize_full_result": serialized - search_done,
            },
            "result": {
                "path": "result.json",
                "sha256": digest((args.output_dir / "result.json").read_bytes()),
            },
        }
        (args.output_dir / "overview.md").write_text(
            overview_report(request, result, selection), encoding="utf-8"
        )
        if args.remediate:
            remediation_started = time.perf_counter()
            summary["remediation"] = evaluate_interventions(
                graph,
                result,
                limit=args.remediate,
                max_sources=args.remediation_sources,
                max_targets=args.remediation_targets,
                output_dir=args.output_dir,
                execution_budget=limits,
            )
            summary["phase_seconds"]["remediation_including_independent_verification"] = (
                time.perf_counter() - remediation_started
            )
        from scripts.defender_brief import build_defender_brief, render_defender_brief

        brief_started = time.perf_counter()
        brief = build_defender_brief(
            graph, inventory, request, result, remediation=summary.get("remediation")
        )
        _atomic_json(args.output_dir / "defender-brief.json", brief)
        (args.output_dir / "defender-brief.md").write_text(
            render_defender_brief(brief), encoding="utf-8"
        )
        summary["defender_brief"] = {
            name: {"path": name, "sha256": digest((args.output_dir / name).read_bytes())}
            for name in ("defender-brief.json", "defender-brief.md")
        }
        summary["phase_seconds"]["build_defender_brief"] = time.perf_counter() - brief_started
        summary["elapsed_seconds"] = time.perf_counter() - started
        _atomic_json(args.output_dir / "summary.json", summary)
        print(json.dumps({"selection": selection, "batch": counts}, sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ValidationError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
