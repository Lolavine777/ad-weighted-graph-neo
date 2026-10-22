"""Five independent SEAMLESS footholds: native C ranking and one membership intervention."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path

from scripts.defender_brief import remediation_outcome
from scripts.neo_domain import TECHNIQUES, build_survey, compact_witness, scenario_profile
from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine.batch import _atomic_json, _query_for_cell, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import digest
from src.engine.query_report import render_query_brief
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.remediation import ReplayBaseline, prepare_baseline, request_for_baseline
from src.engine.remediation_runner import inventory_interventions, run_remediation

SEED = "neo-decision-v1"


def select_sources(sources):
    """Choose identities before looking at reachability or C."""
    return [
        source
        for kind, count in (("User", 3), ("Computer", 2))
        for source in sorted(
            (s for s in sources if s["node_kind"] == kind),
            key=lambda s: canonical_digest([s["node_id"], SEED]),
        )[:count]
    ]


def membership_points(rows, graph, privileged_groups):
    """Count observed positive-C programs and pairs separately; skip preexisting access."""
    support, pairs = defaultdict(set), defaultdict(set)
    for row in rows:
        for program in row["programs"]:
            if program["effort"] in (None, 0):
                continue
            index = int(program["candidate_id"].rsplit("_", 1)[1]) - 1
            for step in row["paths"][index]["transition_history"]:
                edge_id = step["edge_id"]
                if edge_id is None:
                    continue
                edge = graph.edge(edge_id)
                if edge["kind"] == "MemberOf" and edge["target"] in privileged_groups:
                    pair = (row["source"], row["target"])
                    pairs[edge_id].add(pair)
                    support[edge_id].add((*pair, program["program_id"]))
    return [
        {"edge": graph.edge(edge), "programs": len(support[edge]), "pairs": sorted(pairs[edge])}
        for edge in sorted(support, key=lambda e: (-len(pairs[e]), -len(support[e]), e))
    ]


def route_count(row):
    # Same ordered observed-edge identity used by the native remediation witness.
    return len(
        {
            canonical_digest([s["edge_id"] for s in p["transition_history"] if s["edge_id"]])
            for p in row["paths"]
        }
    )


def _cells(folder):
    return sorted(
        (json.loads(p.read_text()) for p in folder.glob("query-*.json")),
        key=lambda cell: (cell["source_id"], cell["goal_id"]),
    )


def _baseline(graph, cells, cache, index):
    if cache.exists():
        baseline = ReplayBaseline(**json.loads(cache.read_text()))
        if baseline.scope["query_profile_digest"] != canonical_digest(cells):
            raise ValueError("Prepared baseline query inputs changed")
        return baseline
    baseline = prepare_baseline(graph, cells, run_id=f"neo-decision-source-{index}")
    _atomic_json(cache, asdict(baseline))
    return baseline


def _intervene(snapshot, root, index):
    """Each source is independently replayed and verified against the same graph edit."""
    root = Path(root)
    output = root / "remediation"
    candidate = json.loads((output / "intervention.json").read_text())
    edit_digest = canonical_digest(candidate["technical_edits"])
    result_path = output / f"outcome-{index}.json"
    if result_path.exists():
        cached = json.loads(result_path.read_text())
        if cached["edit_digest"] != edit_digest or cached["package_sha256"] != digest(
            (output / f"package-{index}.json").read_bytes()
        ):
            raise ValueError("Intervention outcome checkpoint changed")
        return cached
    graph = EngineGraph.from_snapshot(Path(snapshot).read_text())
    cells = _cells(root / "discovery" / f"source-{index}")
    baseline = _baseline(graph, cells, output / f"baseline-{index}.json", index)
    request = request_for_baseline(
        baseline, candidate["technical_edits"], request_id=f"neo-decision:{index}"
    )
    package = run_remediation(request, graph, baseline)
    _atomic_json(output / f"package-{index}.json", package)
    result = {
        "source_index": index,
        "edit_digest": edit_digest,
        "outcome": remediation_outcome(graph, package),
        "cells": package["report"]["cells"],
        "package_sha256": digest((output / f"package-{index}.json").read_bytes()),
        "independent_verifier_passed": True,
    }
    _atomic_json(result_path, result)
    return result


def aggregate(outcomes):
    """Sum disjoint source-goal scopes; never rank source shards as interventions."""
    sources = [o["source_index"] for o in outcomes]
    if len(set(sources)) != len(sources):
        raise ValueError("Duplicate source outcome")
    values = [o["outcome"] for o in outcomes]
    return {
        "sources": len(sources),
        "pairs": sum(len(o["cells"]) for o in outcomes),
        "programs_cut": sum(o["programs_cut"]["numerator"] for o in values),
        "baseline_programs": sum(o["programs_cut"]["denominator"] for o in values),
        "pairs_disconnected": sum(o["pairs_disconnected"]["numerator"] for o in values),
        "reachable_before": sum(o["reachable_before"] for o in values),
        "reachable_after": sum(o["reachable_after"] for o in values),
        "unresolved_after": sum(o["unresolved_after"] for o in values),
        "new_after_programs": sum(o["new_after_programs"] for o in values),
    }


def render_report(rows, graph, outcomes, selected):
    lines = [
        "# Năm foothold SEAMLESS: đường đi, C và can thiệp",
        "",
        "Mỗi nguồn bị chiếm độc lập; 12 bước, 1.024 expansions, tối đa 3 chuỗi/cặp.",
        "C xếp trong các chuỗi tìm được; đồng C giữ nguyên, chưa chứng minh minimum.",
        "Một tuyến có thể có nhiều chuỗi thao tác. Không đếm chúng thành nhiều tuyến.",
        "",
        "| Nguồn | Đích | Chuỗi | Tuyến | C tăng dần |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        source = graph.node(row["source"])["label"]
        target = "DA" if row["target"].endswith("-512") else "EA"
        costs = ", ".join(str(p["effort"]) for p in row["programs"])
        lines.append(
            f"| {source} | {target} | {len(row['paths'])} | {route_count(row)} | {costs} |"
        )
    edge = selected["edge"]
    lines.extend(
        [
            "",
            "Can thiệp mô phỏng: gỡ membership "
            + graph.node(edge["source"])["label"]
            + " → "
            + graph.node(edge["target"])["label"]
            + ".",
            f"Hỗ trợ quan sát: {selected['programs']} chuỗi / {len(selected['pairs'])} cặp.",
        ]
    )
    totals = aggregate(outcomes)
    lines.extend(
        [
            "",
            f"Đã replay và tìm lại trên đủ {totals['pairs']} cặp, "
            f"mỗi nguồn được native verifier kiểm độc lập.",
            f"Cắt {totals['programs_cut']}/{totals['baseline_programs']} chuỗi gốc; "
            f"ngắt kết nối được chứng minh: {totals['pairs_disconnected']}/"
            f"{totals['reachable_before']} cặp trước đó reachable.",
            f"Sau sửa: {totals['reachable_after']} cặp còn đường, "
            f"{totals['unresolved_after']} cặp chưa kết luận; "
            f"tìm thêm {totals['new_after_programs']} chuỗi mới.",
            "",
            "## C trước và sau trên các đường tìm được",
            "",
            "| Nguồn | Đích | C trước | C sau | Trạng thái sau |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for outcome in sorted(outcomes, key=lambda o: o["source_index"]):
        source = next(
            r["source"] for r in rows if r["source_id"] == outcome["cells"][0]["source_id"]
        )
        for cell in outcome["cells"]:
            row = next(
                r
                for r in rows
                if r["source_id"] == cell["source_id"] and r["goal_id"] == cell["goal_id"]
            )
            effort = cell["effort"]
            lines.append(
                f"| {graph.node(source)['label']} | "
                f"{'DA' if row['target'].endswith('-512') else 'EA'} | "
                f"{effort.get('before')} | {effort.get('after')} | "
                f"{cell['after']['reachability']} |"
            )
    lines.extend(
        [
            "",
            "C trước/sau là incumbent nếu search còn giới hạn; chênh lệch C "
            "không tự chứng minh can thiệp làm tăng/giảm minimum.",
            "Chỉ thử membership trong mô hình; chi phí và ảnh hưởng vận hành chưa chấm.",
            "Các bản brief theo từng cặp giữ hành động, ledger C và giả định đã dùng.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    graph = EngineGraph.from_snapshot(args.snapshot.read_text())
    _, request = build_survey(graph)
    raw = request.to_dict()
    raw["sources"] = select_sources(raw["sources"])
    if len(raw["sources"]) != 5:
        raise ValueError("Expected at least 3 User and 2 Computer sources")
    raw["common_budget"]["max_paths"] = 3
    request = BatchQueryRequest.from_dict(raw)
    root = args.output_dir
    discovery, output = root / "discovery", root / "remediation"
    scope = {
        "request": raw,
        "source_pins": execution_source_pins(),
        "snapshot_sha256": digest(args.snapshot.read_bytes()),
        "selection_seed": SEED,
        "runner_sha256": digest(Path(__file__).read_bytes()),
    }
    if args.resume:
        if json.loads((discovery / "scope.json").read_text()) != scope:
            raise ValueError("Decision scope/code/snapshot changed")
    else:
        root.mkdir(parents=True, exist_ok=False)
        discovery.mkdir()
        _atomic_json(discovery / "scope.json", scope)
    output.mkdir(exist_ok=True)
    rows = []
    for index, source in enumerate(request.sources):
        folder = discovery / f"source-{index}"
        folder.mkdir(exist_ok=True)
        for goal in request.resolve_target_goals():
            target = goal.target_node_id.rsplit("-", 1)[-1]
            saved = folder / f"result-{target}.json"
            if saved.exists():
                rows.append(json.loads(saved.read_text()))
                continue
            query, error = _query_for_cell(
                request,
                source,
                goal,
                graph,
                TECHNIQUES,
                request.common_budget,
                scenario_policy=scenario_profile(graph),
                effort_profile=load_effort_profile("neo-c-v1"),
                search_order="neo_guided",
            )
            if error is not None:
                raise ValueError(str(error))
            query["top_k"] = 3
            result = run_attack_query(query, graph)
            _atomic_json(
                folder / f"query-{target}.json",
                {
                    "source_id": source.source_id,
                    "goal_id": goal.goal_id,
                    "query": query,
                },
            )
            row = {
                "source": source.node_id,
                "source_id": source.source_id,
                "source_kind": source.node_kind,
                "target": goal.target_node_id,
                "goal_id": goal.goal_id,
                "status": result.status,
                "reached": result.final_goal_reached,
                "expansions": result.expansions,
                "truncated": result.truncated,
                "minimum_proven": result.is_minimum_proven_over_scope,
                "unknown_attempts": sum(len(a.unknown) for a in result.attempts),
                "programs": result.top_k_result["programs"],
                "paths": [
                    compact_witness(p, graph, result.materialized_query.catalog)
                    for p in result.paths
                ],
            }
            _atomic_json(saved, row)
            (folder / f"brief-{target}.md").write_text(render_query_brief(result, graph))
            rows.append(row)
            print(
                json.dumps({"discovered": len(rows), "C": [p["effort"] for p in row["programs"]]}),
                flush=True,
            )
    _atomic_json(
        discovery / "summary.json",
        [{k: v for k, v in row.items() if k not in ("paths", "programs")} for row in rows],
    )
    # Keep editable privileged membership points; avoid universal implicit groups.
    privileged = {t.target_node_id for t in request.resolve_target_goals()}
    privileged.update(
        n["id"] for n in graph.nodes() if n["kind"] == "Group" and n["id"].endswith(":S-1-5-32-544")
    )
    points = membership_points(rows, graph, privileged)
    if not points:
        raise ValueError("No observed positive-C privileged membership point")
    _atomic_json(output / "observed-points.json", points)
    selected = points[0]
    chosen_source = sorted(selected["pairs"])[0][0]
    source_index = next(i for i, s in enumerate(request.sources) if s.node_id == chosen_source)
    if not (output / "intervention.json").exists():
        cells = _cells(discovery / f"source-{source_index}")
        baseline = _baseline(graph, cells, output / f"baseline-{source_index}.json", source_index)
        inventory = inventory_interventions(graph, baseline)
        _atomic_json(output / "native-inventory.json", inventory)
        candidate = next(
            c
            for c in inventory["candidates"]
            if c["status"] == "supported"
            and c["catalog_entry_id"] == "group-membership"
            and any(
                e.get("edge_id") == selected["edge"]["id"] and e["kind"] == "deny_relationship"
                for e in c["technical_edits"]
            )
        )
        _atomic_json(output / "intervention.json", candidate)
    candidate = json.loads((output / "intervention.json").read_text())
    edits = candidate["technical_edits"]
    if len(edits) != 1 or edits[0].get("edge_id") != selected["edge"]["id"]:
        raise ValueError("Intervention checkpoint does not match selected membership")
    outcomes = []
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=get_context("spawn")) as pool:
        futures = [
            pool.submit(_intervene, str(args.snapshot.resolve()), str(root.resolve()), i)
            for i in range(len(request.sources))
        ]
        for future in as_completed(futures):
            outcomes.append(future.result())
            print(json.dumps({"verified_sources": len(outcomes)}), flush=True)
    summary = {
        "scope": scope,
        "selected_point": selected,
        "totals": aggregate(outcomes),
        "outcomes": sorted(outcomes, key=lambda o: o["source_index"]),
    }
    _atomic_json(root / "summary.json", summary)
    (root / "report.md").write_text(render_report(rows, graph, outcomes, selected))
    print(json.dumps(summary["totals"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
