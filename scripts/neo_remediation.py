"""Rediscover the three fixed WRAITH remediation cases, offline, with both neo orders."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path

from scripts.neo_domain import compact_witness, scenario_profile
from scripts.neo_import import prepare_records
from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine.batch import _atomic_json, _query_for_cell, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import digest, wire
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.credentials import replay_path
from src.engine.top_k import collect_assessments, effort_programs
from src.parser import DirectGraphBuilder, IdentityNormalizer, ManifestRawDataLoader
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.cli import canonicalize_graph, load_time_policy
from src.parser.snapshot_facts import graph_digest, serialize_snapshot

ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ("neo_guided", "neo_refine")


def edit_records(records, source, kind, target):
    """Edit copied collector support, including duplicate observations of one session."""
    if kind not in {"MemberOf", "HasSession"}:
        raise ValueError("Unsupported remediation relationship")
    changed, removed = deepcopy(records), Counter()
    for record in changed:
        data = record.data
        if kind == "MemberOf" and data["ObjectIdentifier"] == target:
            members = data.get("Members", [])
            kept = [m for m in members if m["ObjectIdentifier"] != source]
            removed["Members"] += len(members) - len(kept)
            data["Members"] = kept
        elif kind == "HasSession" and data["ObjectIdentifier"] == source:
            for field in ("Sessions", "PrivilegedSessions", "RegistrySessions"):
                collection = data.get(field)
                if collection is None:
                    continue
                sessions = collection["Results"]
                kept = [s for s in sessions if s["UserSID"] != target]
                removed[field] += len(sessions) - len(kept)
                collection["Results"] = kept
    if not sum(removed.values()):
        raise ValueError("No matching collector support for remediation")
    return changed, {k: v for k, v in removed.items() if v}


def rebuild(records, metadata):
    normalized = IdentityNormalizer().normalize_records(records)
    graph, facts = DirectGraphBuilder(
        retain_unresolved_members=True, metadata=metadata
    ).build_snapshot(normalized)
    return EngineGraph.from_snapshot(serialize_snapshot(canonicalize_graph(graph), facts))


def classify(reached, no_path, truncated, unknown):
    if reached:
        return "bypass"
    if no_path and not truncated and not unknown:
        return "blocked_in_scope"
    return "inconclusive"


def verify_result(result, graph):
    """Replay every returned path and independently sum its unique rated work ledger."""
    assessments = collect_assessments(result)
    witnesses, ledger_checks = [], []
    for index, path in enumerate(result.paths, 1):
        cid = f"generated_{index:04d}"
        state = replay_path(path, graph, result.materialized_query.catalog)
        if state != path.final_state or not result.materialized_query.is_success_state(state):
            raise AssertionError("Witness replay or goal diverged")
        assessment = assessments.get(cid, {})
        units = assessment.get("program", [])
        ledger = assessment.get("work_unit_basis", {})
        if path.transition_history and (
            assessment.get("status") != "feasible" or assessment.get("effort_status") != "rated"
        ):
            raise AssertionError("Witness has no feasible C ledger")
        if len(units) != len(set(units)) or set(units) != set(ledger):
            raise AssertionError("C ledger work set mismatch")
        total = sum(ledger[u]["effort_cost"] for u in units)
        if total != assessment.get("effort", 0):
            raise AssertionError("C differs from unique work ledger")
        ledger_checks.append({"candidate_id": cid, "C": total, "ledger": ledger})
        witnesses.append(
            {
                "candidate_id": cid,
                "path": compact_witness(path, graph, result.materialized_query.catalog),
            }
        )
    programs, exclusions = effort_programs(result)
    C = (result.min_effort or {}).get("minimum_effort_value")
    if C != min((p["effort"] for p in programs), default=None):
        raise AssertionError("Best C disagrees with program ledgers")
    unknown = Counter(k for a in result.attempts for k in a.unknown)
    row = {
        "status": result.status,
        "reached": result.final_goal_reached,
        "C": C,
        "outcome": classify(
            result.final_goal_reached,
            result.is_no_path_proven_over_scope,
            result.truncated,
            bool(unknown),
        ),
        "expansions": result.expansions,
        "truncated": result.truncated,
        "truncation_reason": result.truncation_reason,
        "caps": result.caps,
        "complete": result.complete,
        "minimum_proven": result.is_minimum_proven_over_scope,
        "no_path_proven": result.is_no_path_proven_over_scope,
        "unknown": dict(unknown),
        "failed": dict(Counter(k for a in result.attempts for k in a.failed)),
        "replayed_programs": len(witnesses),
        "ledger_checked_programs": len(ledger_checks),
        "rating_exclusions": exclusions,
    }
    return row, {"witnesses": witnesses, "ledger_checks": ledger_checks, "programs": programs}


def run(args):
    content = args.snapshot.read_bytes()
    graph = EngineGraph.from_snapshot(content.decode())
    pack_path = ROOT / "reports/neo/bloodhound-query-pack.json"
    pack = json.loads(pack_path.read_text())
    manifest = ROOT / "data/samples/manifests/ad-sampledata-v1.json"
    loader = ManifestRawDataLoader(
        manifest,
        time_policy=load_time_policy(ROOT / "data/samples/time-policies/ad-sampledata-v1.json"),
    )
    raw, _ = prepare_records(list(loader.load(args.raw_dir)), "20240305111414")
    records = adapt_bloodhound_v3_records(raw)
    # Rebuilding avoids stale derived access and ambiguous direct/derived support in projections.
    baseline = rebuild(records, graph.metadata)
    if baseline.to_canonical() != graph.to_canonical() or wire(
        baseline.snapshot_facts.facts
    ) != wire(graph.snapshot_facts.facts):
        raise ValueError("Snapshot differs from the manifest-verified post-LocalGroup WRAITH model")
    original = canonical_digest(wire(records))
    labels = {n["label"]: n["id"] for n in graph.nodes()}
    rodc, bm, admin, ca, da = (
        labels[n]
        for n in (
            "RODCMANAGER@WRAITH.CORP",
            "BM@WRAITH.CORP",
            "ADMINISTRATORS@WRAITH.CORP",
            "EXTCA01.WRAITH.CORP",
            "DOMAIN ADMINS@WRAITH.CORP",
        )
    )
    cases = (
        ("rodc-membership", rodc, rodc, "MemberOf", admin, "wraith"),
        ("extca-session", ca, ca, "HasSession", bm, "wraith-sessions"),
        ("bm-da-membership", ca, bm, "MemberOf", da, "wraith-sessions"),
    )
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "version": "neo-remediation-rediscovery/1",
        "snapshot_sha256": digest(content),
        "snapshot_id": graph.metadata["snapshot_id"],
        "raw_manifest_sha256": digest(manifest.read_bytes()),
        "fixed_pack_sha256": digest(pack_path.read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "source_pins": execution_source_pins(),
        "effort_profile": load_effort_profile("neo-c-v1"),
        "bloodhound": "historical_baseline_only_not_run",
        "intervention_semantics": "counterfactual records, independent fresh foothold per query",
        "rows": [],
        "interventions": [],
    }
    for relative in (
        "scripts/neo_domain.py",
        "scripts/neo_import.py",
        "data/samples/time-policies/ad-sampledata-v1.json",
    ):
        report["source_pins"][relative] = digest((ROOT / relative).read_bytes())
    for name, source, es, kind, et, stratum in cases:
        edited, audit = edit_records(records, es, kind, et)
        after = rebuild(edited, graph.metadata)
        before_edges = {e["id"]: e for e in graph.edges()}
        after_edges = {e["id"]: e for e in after.edges()}
        if any((e["source"], e["kind"], e["target"]) == (es, kind, et) for e in after.edges()):
            raise AssertionError("Intervention left the selected relationship intact")
        delta = {
            "case": name,
            "edit": {"source": es, "kind": kind, "target": et},
            "removed_observations": audit,
            "removed_edges": [
                before_edges[e] for e in sorted(before_edges.keys() - after_edges.keys())
            ],
            "changed_edges": [
                {"before": before_edges[e], "after": after_edges[e]}
                for e in sorted(before_edges.keys() & after_edges.keys())
                if before_edges[e] != after_edges[e]
            ],
            "added_edges": [
                after_edges[e] for e in sorted(after_edges.keys() - before_edges.keys())
            ],
            "effective_graph_digest": graph_digest(after.to_canonical()),
        }
        _atomic_json(
            args.output_dir / f"{name}-snapshot.json",
            json.loads(serialize_snapshot(after.to_canonical(), after.snapshot_facts)),
        )
        report["interventions"].append(delta)
        dataset = pack["datasets"][stratum]
        request = BatchQueryRequest.from_dict(dataset["request"])
        policy = scenario_profile(graph, dataset["scenario"])
        if graph.metadata["snapshot_id"] != dataset["snapshot_id"] or (
            policy.canonical_dict() != dataset["scenario_policy"]
        ):
            raise ValueError("Fixed scenario/snapshot identity changed")
        source_spec = next(s for s in request.sources if s.node_id == source)
        goals = request.resolve_target_goals()
        if {g.target_node_id for g in goals} != {da, labels["ENTERPRISE ADMINS@WRAITH.CORP"]}:
            raise ValueError("Fixed DA/EA goals changed")
        for goal in goals:
            base_query, error = _query_for_cell(
                request,
                source_spec,
                goal,
                graph,
                dataset["techniques"],
                request.common_budget,
                scenario_policy=policy,
                effort_profile=report["effort_profile"],
                search_order="neo_guided",
            )
            if error is not None:
                raise ValueError(str(error))
            for strategy in STRATEGIES:
                query = {**base_query, "search_order": strategy}
                query_pin = canonical_digest(query)
                for phase, model in (("before", graph), ("after", after)):
                    started = time.perf_counter()
                    result = run_attack_query(deepcopy(query), model)
                    row, evidence = verify_result(result, model)
                    if phase == "before" and row["outcome"] == "bypass":
                        row["outcome"] = "reachable"
                    row.update(
                        case=name,
                        phase=phase,
                        strategy=strategy,
                        source=source,
                        target=goal.target_node_id,
                        query_sha256=query_pin,
                        budget=wire(request.common_budget),
                        seconds=time.perf_counter() - started,
                    )
                    filename = (
                        f"{name}-{goal.target_node_id.rsplit('-', 1)[-1]}-{strategy}-{phase}.json"
                    )
                    _atomic_json(
                        args.output_dir / filename, {"row": row, "query": query, **evidence}
                    )
                    row["evidence_file"] = filename
                    report["rows"].append(row)
                    print(json.dumps(row), flush=True)
    if original != canonical_digest(wire(records)) or args.snapshot.read_bytes() != content:
        raise AssertionError("Baseline inputs were mutated")
    report["baseline_unchanged"] = True
    report["evidence_sha256"] = {
        p.name: digest(p.read_bytes()) for p in sorted(args.output_dir.glob("*.json"))
    }
    _atomic_json(args.output_dir / "results.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/ad_sampledata")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
