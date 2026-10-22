"""Summarize a native domain survey and verify a small observed remediation scope."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.defender_brief import remediation_outcome
from scripts.neo_domain import (
    compact_witness,
    load_records,
    scenario_profile,
    summarize,
    techniques_for,
)
from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine.batch import _atomic_json, _query_for_cell, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.remediation import prepare_baseline, request_for_baseline
from src.engine.remediation_runner import (
    inventory_interventions,
    rank_interventions,
    run_remediation,
)


def observed_interventions(rows, graph):
    """Count observed C>0 witness support, never infer domain-wide disconnection."""
    support = defaultdict(set)
    for pair, row in rows.items():
        if not row.get("reached") or row.get("C") in (None, 0):
            continue
        for step in row["witness"]["transition_history"]:
            edge_id = step["edge_id"]
            if edge_id is not None:
                edge = graph.edge(edge_id)
                if edge["kind"] in {"MemberOf", "GenericAll", "WriteDacl", "ForceChangePassword"}:
                    support[edge_id].add(pair)
    return [
        {
            "edge_id": edge,
            "relationship": graph.edge(edge),
            "observed_pairs": len(pairs),
            "observed_sources": len({p[0] for p in pairs}),
            "pairs": sorted(pairs),
            "executor_supported": graph.edge(edge)["kind"] == "MemberOf",
        }
        for edge, pairs in sorted(support.items(), key=lambda item: (-len(item[1]), item[0]))
    ]


def verify_interventions(graph, request, rows, inventory, *, output, limit, scenario="identity"):
    if limit < 1:
        raise ValueError("Intervention limit must be positive")
    supported = [c for c in inventory if c["executor_supported"]]
    if not supported:
        return {"status": "not_executed", "reason": "No supported observed intervention"}
    # Select a small rectangular product from the most shared supported witness edge.
    source_ids = sorted({pair[0] for pair in supported[0]["pairs"]})[:2]
    sources = {s.node_id: s for s in request.sources}
    policy, effort = scenario_profile(graph, scenario), load_effort_profile("neo-c-v1")
    cells = []
    for source in source_ids:
        for goal in request.resolve_target_goals():
            row = rows[(source, goal.target_node_id)]
            query, error = _query_for_cell(
                request,
                sources[source],
                goal,
                graph,
                techniques_for(scenario),
                request.common_budget,
                scenario_policy=policy,
                effort_profile=effort,
                search_order="neo_guided",
            )
            if error is not None:
                raise ValueError(str(error))
            result = run_attack_query(query, graph)
            if result.final_goal_reached != row["reached"]:
                raise ValueError("Survey query reproduction changed reachability")
            if result.paths:
                path = result.best_path or result.paths[0]
                if (
                    compact_witness(path, graph, result.materialized_query.catalog)
                    != row["witness"]
                ):
                    raise ValueError("Survey query reproduction changed witness")
            cells.append(
                {"source_id": sources[source].source_id, "goal_id": goal.goal_id, "query": query}
            )
    _atomic_json(output / "remediation-cells.json", cells)
    baseline = prepare_baseline(graph, cells, run_id="neo-domain-observed-remediation")
    native = inventory_interventions(graph, baseline)
    priorities = {c["edge_id"]: c["observed_pairs"] for c in supported}
    candidates = sorted(
        (c for c in native["candidates"] if c["status"] == "supported" and c["technical_edits"]),
        key=lambda c: (
            -max((priorities.get(e.get("edge_id"), 0) for e in c["technical_edits"]), default=0),
            -len(c["observed_bindings"]),
            c["candidate_id"],
        ),
    )[:limit]
    _atomic_json(output / "native-intervention-inventory.json", native)
    packages, outcomes = [], []
    for index, candidate in enumerate(candidates):
        experiment = request_for_baseline(
            baseline,
            candidate["technical_edits"],
            request_id=f"domain-observed:{candidate['candidate_id']}",
        )
        package = run_remediation(experiment, graph, baseline)
        _atomic_json(output / f"intervention-{index}.json", package)
        packages.append(package)
        outcomes.append(remediation_outcome(graph, package))
    return {
        "status": "executed",
        "sources": len(source_ids),
        "pairs": len(cells),
        "scope": "Selected observed witness support only; not all domain pairs",
        "ranking": rank_interventions(packages),
        "outcomes": outcomes,
    }


def render_report(summary, rows, inventory, graph, remediation):
    unresolved = sum(
        not r.get("reached", False) and r.get("truncated", False) for r in rows.values()
    )
    lines = [
        "# Khảo sát: nguồn độc lập → DA/EA",
        "",
        f"Nguồn: {summary['eligible_sources']}; cặp khai báo: {summary['declared_pairs']}; "
        f"đã ghi kết quả: {summary['recorded_pairs']}; chưa chạy: {summary['not_run_pairs']}.",
        f"Có witness: {summary['reached_pairs']}; đủ C: {summary['C_rated_reached_pairs']}; "
        f"chưa có witness và còn giới hạn: {unresolved}; lỗi: {summary['errors']}.",
        "Kết quả có witness cũng dừng ở path cap; C là best-found, chưa chứng minh minimum.",
        "Mỗi nguồn là một giả định compromise riêng; "
        "quyền ban đầu và giả định session theo scope.json.",
        "Đích là DA/EA theo SID quan sát. Không bao gồm toàn bộ tài sản hoặc mọi kỹ thuật AD.",
        "Budget mỗi query: " + json.dumps(summary.get("budget", {}), ensure_ascii=False) + ".",
        "",
        "| Đích | Cặp đã chạy | Có witness | Có C | Chưa có witness, còn giới hạn |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for target in sorted({pair[1] for pair in rows}):
        subset = [r for r in rows.values() if r["target"] == target]
        label = graph.node(target)["label"].replace("|", "\\|")
        lines.append(
            f"| {label} | {len(subset)} | {sum(r.get('reached', False) for r in subset)} | "
            f"{sum(r.get('reached', False) and r.get('C') is not None for r in subset)} | "
            f"{sum(not r.get('reached', False) and r.get('truncated', False) for r in subset)} |"
        )
    lines.extend(["", "Điều kiện Unknown trong các nhánh đã thử:", ""])
    lines.extend(
        f"- {name}: {count} attempts."
        for name, count in Counter(summary["unknown_attempts"]).most_common()
    )
    lines.extend(
        [
            "",
            "Unknown ở một attempt không làm mất witness khả thi ở nhánh khác. "
            "Chưa tìm được trong budget không chứng minh no-path hoặc an toàn.",
            "",
            "## Điểm can thiệp quan sát được",
            "",
            "Xếp theo số cặp có witness dùng cạnh, chỉ trên đường C>0 đã tìm thấy. "
            "Đây là hỗ trợ quan sát, không phải hiệu quả remediation đã chứng minh.",
            "",
            "| Quan hệ | Nguồn quyền → đích | Cặp hỗ trợ | Executor |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for candidate in inventory[:10]:
        edge = candidate["relationship"]
        label = (
            graph.node(edge["source"])["label"] + " → " + graph.node(edge["target"])["label"]
        ).replace("|", "\\|")
        lines.append(
            f"| {edge['kind']} | {label} | {candidate['observed_pairs']} | "
            f"{'hỗ trợ' if candidate['executor_supported'] else 'chưa hỗ trợ'} |"
        )
    lines.extend(["", "## Replay và tìm bypass", ""])
    if remediation.get("status") == "executed":
        lines.append(
            f"Scope riêng: {remediation['sources']} nguồn × DA/EA = {remediation['pairs']} cặp."
        )
        for outcome in remediation["outcomes"]:
            cut, disconnected = outcome["programs_cut"], outcome["pairs_disconnected"]
            lines.extend(
                [
                    "",
                    "; ".join(outcome["edits"]),
                    f"Programs cut: {cut['numerator']}/{cut['denominator']}; "
                    f"pairs disconnected: {disconnected['numerator']}/"
                    f"{disconnected['denominator']}; "
                    f"còn reach: {outcome['reachable_after']}; "
                    f"chưa kết luận: {outcome['unresolved_after']}; "
                    f"chương trình mới: {outcome['new_after_programs']}.",
                ]
            )
    else:
        lines.append(remediation.get("reason", "Chưa thực hiện remediation."))
    lines.extend(
        [
            "",
            "Không suy tỉ lệ giảm rủi ro toàn miền từ scope remediation nhỏ "
            "hoặc số witness bị cắt.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interventions", type=int, default=2)
    args = parser.parse_args(argv)
    if args.interventions < 0:
        parser.error("--interventions must be nonnegative")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    scope = json.loads((args.survey / "scope.json").read_text())
    if scope["scope_digest"] != canonical_digest(
        {key: value for key, value in scope.items() if key != "scope_digest"}
    ):
        raise ValueError("Survey scope integrity mismatch")
    if scope["source_pins"] != execution_source_pins():
        raise ValueError("Survey source pins changed; reproduce with the pinned code")
    from src.engine.query_cli import digest

    if scope["runner_sha256"] != digest(Path(__file__).with_name("neo_domain.py").read_bytes()):
        raise ValueError("Survey runner changed; reproduce with the pinned code")
    if scope["snapshot_sha256"] != digest(args.snapshot.read_bytes()):
        raise ValueError("Survey snapshot bytes differ")
    request = BatchQueryRequest.from_dict(scope["request"])
    rows, _ = load_records(args.survey / "cells.jsonl")
    summary = summarize(rows, request, 0)
    summary["budget"] = {
        "max_paths": request.common_budget.max_paths,
        "max_steps": request.common_budget.max_steps,
        "max_expansions": request.common_budget.max_expansions,
    }
    graph = EngineGraph.from_snapshot(args.snapshot.read_text())
    inventory = observed_interventions(rows, graph)
    _atomic_json(args.output_dir / "observed-interventions.json", inventory)
    remediation = (
        verify_interventions(
            graph,
            request,
            rows,
            inventory,
            output=args.output_dir,
            limit=args.interventions,
            scenario=scope.get("scenario", "identity"),
        )
        if args.interventions
        else {"status": "not_executed", "reason": "Report only; interventions=0"}
    )
    _atomic_json(args.output_dir / "summary.json", {"survey": summary, "remediation": remediation})
    (args.output_dir / "report.md").write_text(
        render_report(summary, rows, inventory, graph, remediation), encoding="utf-8"
    )
    print(json.dumps({"survey": summary, "remediation": remediation}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
