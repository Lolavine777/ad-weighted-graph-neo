"""Review-only #264 basis consumer; no search/provider implementation or adoption.

Native registries are constructed from declarative event/context identities before
search. Engineering gate copies are synthetic_test_only and remain ignored locally.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from scripts.research.issue250_public_probe import (
    ROOT,
    assert_frozen_semantics,
    envelope,
    frozen_inputs,
    read,
    save,
    summary,
)
from scripts.research.week4_maintainer_disposition import PACKET as FROZEN_PACKET
from scripts.research.week4_maintainer_disposition import frozen_case
from src.engine import materialize_query, run_attack_query
from src.engine.graph import EngineGraph
from src.engine.query_cli import wire
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.ranking.resolver import generate_rating_lookup_key_p, generate_work_unit_id
from src.parser.snapshot_facts import graph_digest, serialize_snapshot

PACKAGE = ROOT / "docs/research/ratings/asrep-expert-v1"


def verify_historical():
    for name, expected in read(PACKAGE / "historical-pins.json").items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen artifact changed: {name}")


def validate_proposal(proposal):
    """Reject a different documented conditional question before materialization."""
    program = [e["technique"] for e in proposal["events"]]
    catalog = read(ROOT / "docs/research/ratings/likelihood-v1/catalog.json")
    classes = {a["technique_id"]: a["canonical_class"] for a in catalog["actions"]}
    if program != proposal["program"]:
        raise ValueError("Program/event inventory mismatch")
    for index, event in enumerate(proposal["events"]):
        if event["history"] != program[:index]:
            raise ValueError("Documented full successful history mismatch")
        if event["canonical_class"] != classes[event["technique"]]:
            raise ValueError("Canonical likelihood class mismatch")
        if event["lower"] is None or event["upper"] is None:
            if (event["lower"], event["upper"]) != (None, None) or event.get(
                "numeric_disposition"
            ) != "UNRATED_NO_BASIS":
                raise ValueError("Missing interval needs explicit unrated disposition")
            continue
        if not Fraction(0) <= Fraction(event["lower"]) <= Fraction(event["upper"]) <= Fraction(1):
            raise ValueError("Invalid interval")
    population = proposal["target_population"]
    recovery = next(e for e in proposal["events"] if e["technique"] == "recover_asrep_secret")
    if proposal["schema_version"] == "asrep-expert-proposal/2.0.0":
        if (
            recovery["lower"] is not None
            or recovery["upper"] is not None
            or population["compute_floor"] is not None
        ):
            raise ValueError("Natural-password recovery lacks reviewed rank/compute basis")
        return
    expected = [
        Fraction(population[k], population["population_size"])
        for k in ("compute_floor", "compute_cap")
    ]
    if [Fraction(recovery[k]) for k in ("lower", "upper")] != expected:
        raise ValueError("Recovery bounds do not follow the declared finite model")


def build_inputs(raw_dir: Path, revision: str, *, package: Path = PACKAGE):
    """Build pending registries without invoking search or consuming generated keys."""
    verify_historical()
    proposal = read(package / "proposal.json")
    if proposal["status"] != "proposed_pending_b_review" or proposal["independent_b_review"]:
        raise ValueError("This research consumer requires a pending, unadopted proposal")
    validate_proposal(proposal)
    graph, query, frozen_spec = frozen_inputs(raw_dir, revision)
    if (
        proposal["semantic_assumptions"] != frozen_spec["assumptions"]
        or proposal["budget"] != query["budget"]
        or proposal["snapshot_id"] != graph.metadata["snapshot_id"]
    ):
        raise ValueError("Inherited assumptions, budget or snapshot differ from declared inventory")
    identities = {
        "X": query["initial_actor"],
        "V_A": query["initial_state"]["known_identity"][0],
        "C0": query["target"],
    }
    query["scenario_reference"] = proposal["scenario_id"]
    for fact in query["assumptions"]:
        fact["scope"] = proposal["scenario_id"]
        fact["provenance_reference"] = f"scenario://{proposal['basis_id']}/conditional-declarations"
        if fact["predicate"] == "recovery_success":
            fact["assumption_metadata"].update(proposal["recovery_metadata"])
    scope = {
        "query_id": "issue264-" + proposal["basis_id"],
        "scenario_id": proposal["scenario_id"],
        "scenario_version": proposal["scenario_version"],
        "snapshot_id": proposal["snapshot_id"],
        "foothold_node_id": identities["X"],
        "work_boundary": "intra_forest",
        "horizon": proposal["horizon"],
        "active_work_budget": query["budget"]["max_steps"],
        "evaluation_mode": "scenario",
        "policy_id": proposal["policy_id"],
        "target_goal": {
            "goal_id": "admin_control(C0)",
            "target_asset_id": identities["C0"],
            "success_event": "admin_execution_on_C",
        },
        **{
            name: proposal[name]
            for name in (
                "actor_capability",
                "control_scope",
                "retry_policy",
                "target_population",
                "recovery_metadata",
            )
        },
    }
    frozen = read(FROZEN_PACKET)
    effort, likelihood, prefix = [], [], []
    for event, old in zip(proposal["events"], frozen["effort"], strict=True):
        actor, source, target = (identities[event[k]] for k in ("actor", "source", "target"))
        resource = (
            canonical_digest(proposal["recovery_metadata"])
            if event["technique"] == "recover_asrep_secret"
            else None
        )
        context = {
            "source_id": source,
            "method": event["method"],
            "auth_context": identities["X"],
            "resource_context": resource,
            "policy_id": proposal["policy_id"],
            "scope": proposal["scenario_id"],
        }
        uid = generate_work_unit_id(
            event["technique"],
            actor,
            target,
            "ctx-" + canonical_digest(context).removeprefix("sha256:"),
            "intra_forest",
        )
        prefix.append(uid)
        key = generate_rating_lookup_key_p(
            scope["scenario_id"],
            scope["scenario_version"],
            scope["snapshot_id"],
            identities["X"],
            tuple(prefix),
            uid,
            event["technique"],
            actor,
            target,
            source_id=source,
            method=event["method"],
            budget=scope["active_work_budget"],
            horizon=scope["horizon"],
            boundary="intra_forest",
            scope=scope["scenario_id"],
            auth_context=identities["X"],
            resource_context=resource,
            policy_id=scope["policy_id"],
        ).to_dict()
        key.pop("dimension")
        if event["lower"] is not None:
            likelihood.append(
                {
                    **key,
                    **{
                        name: scope[name]
                        for name in (
                            "actor_capability",
                            "control_scope",
                            "retry_policy",
                            "target_population",
                            "recovery_metadata",
                        )
                    },
                    "lower": event["lower"],
                    "upper": event["upper"],
                    "basis_category": "scenario_assumption",
                    "numeric_basis_class": proposal["numeric_basis_class"],
                    "review_status": "pending",
                    "disposition": "unrated",
                    "review_reference": proposal["review_reference"],
                    "provenance_digest": canonical_digest({"proposal": proposal, "event": event}),
                    "rationale": event["derivation"],
                }
            )
        cls = copy.deepcopy(old)
        cls.pop("computed_cost")
        cls.update(
            class_id="proposed264-" + event["canonical_class"],
            basis_category="scenario_assumption",
            review_status="pending",
            disposition="unrated",
            review_reference=proposal["review_reference"],
            provenance_digest=canonical_digest({"proposal": proposal, "rubric": old}),
            notes="Proposed same rubric values in new context; no Week 4 authority transfer.",
        )
        cls["applicability"].update(
            scopes=[proposal["scenario_id"]],
            methods=[event["method"]],
            work_unit_digests=[canonical_digest(uid)],
        )
        effort.append(cls)
    impact = copy.deepcopy(frozen["impact"])
    impact.update(registry_id="proposed264-exact-impact-v1", status="proposed_pending_b_review")
    for mapping in impact["mappings"]:
        mapping.update(
            mapping_id="proposed264-same-asset-typed-admin",
            status="pending",
            review_reference=proposal["review_reference"],
            provenance={"proposed_by": "TTS A", "independent_b_review": False},
        )
        mapping["applicability"]["scenario_id"] = [proposal["scenario_id"]]
    query["rating_resolution"] = {
        "version": "public-rating-resolution/1.1.0",
        "mode": "automatic",
        "policy": "production",
        "scope": scope,
        "registries": {
            "effort": envelope(effort),
            "likelihood": envelope(likelihood),
            "impact": envelope(impact),
            "impact_source": envelope(
                read(ROOT / "docs/research/ratings/week3-closeout/reviewed-release.json")
            ),
        },
    }
    return graph, query, proposal


def engineering_graph_copy(graph):
    """Explicit synthetic derivative for gate tests; keep the original graph/facts intact."""
    canonical = graph.to_canonical()
    canonical["metadata"]["synthetic"] = True
    canonical["metadata"]["description"] = (
        "Issue264 synthetic engineering gate view; not raw rating acceptance"
    )
    facts = replace(graph.snapshot_facts, graph_sha256=graph_digest(canonical))
    return EngineGraph.from_canonical(canonical, snapshot_facts=facts)


def engineering_review_copy(query):
    """Disposable gate test, refused by production policy; never an expert adoption."""
    copied = copy.deepcopy(query)
    config = copied["rating_resolution"]
    config["policy"] = "synthetic_test_only"
    for role in ("effort", "likelihood"):
        env = config["registries"][role]
        for record in env["data"]:
            record.update(
                review_status="accepted",
                disposition="rated",
                basis_category="synthetic_test_only",
                numeric_basis_class="synthetic_test_only",
                review_reference="test://issue264/engineering-gate-copy-not-adoption",
            )
        env["sha256"] = canonical_digest(env["data"])
    env = config["registries"]["impact"]
    env["data"]["status"] = "accepted"
    env["data"]["evidence_class"] = "synthetic_test_only"
    for mapping in env["data"]["mappings"]:
        mapping["status"] = "reviewed"
        mapping["numeric_basis_class"] = "synthetic_test_only"
        mapping["review_reference"] = "test://issue264/engineering-gate-copy-not-adoption"
    env["sha256"] = canonical_digest(env["data"])
    return copied


def coverage_counts(result):
    summaries = result.rating_coverage["candidate_summaries"].values()
    return {
        "valid_generated_paths": len(result.search_result.paths),
        "conditioned_feasible_paths": sum(s["semantic_status"] == "feasible" for s in summaries),
        **{
            label: sum(s[field] for s in summaries)
            for label, field in (
                ("C_rated", "c_complete"),
                ("P_rated", "p_complete"),
                ("I_rated", "i_complete"),
                ("fully_rated", "numeric_complete"),
            )
        },
        "Pareto_eligible": len(result.ranking_result["eligible_candidates"]),
        "P_events_rated": result.rating_coverage["numeric_requests"]["P"]["rated"],
        "P_events_required": result.rating_coverage["numeric_requests"]["P"]["required"],
    }


def run_snapshot_case(name, query, config, snapshot, local, *, label):
    """Snapshot transport is independent of numeric evidence label."""
    query_path, config_path = local / f"{name}.query.json", local / f"{name}.config.json"
    save(query_path, query)
    save(config_path, config)
    command = [
        sys.executable,
        "-m",
        "src.engine.query_cli",
        "--query",
        str(query_path),
        "--rating-resolution",
        str(config_path),
        "--snapshot",
        str(snapshot),
        "--label",
        label,
    ]
    if label == "seamless":
        command += ["--prerequisite", str(ROOT / "data/samples/manifests/seamless-raw-v1.json")]
    outputs = []
    for index in (1, 2):
        destination = local / f"{name}.run{index}.json"
        process = subprocess.run(
            command + ["--output", str(destination)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if process.returncode:
            (local / f"{name}.stderr.txt").write_text(process.stderr, encoding="utf-8")
            raise ValueError(f"{name}: CLI failed; diagnostic retained in ignored local output")
        output = read(destination)
        output.pop("runtime")
        outputs.append(output)
    if outputs[0] != outputs[1]:
        raise ValueError(f"{name}: two-process determinism mismatch")
    return {
        "case": name,
        "command": subprocess.list2cmdline(command),
        "exit_codes": [0, 0],
        "two_runs_equal": True,
        "status": "PASS",
        "evidence_class": "actual_private_dataset_conditional_prediction"
        if label == "seamless"
        else "synthetic_test_only",
        "actual": summary(outputs[0]["semantic"]),
    }, outputs[0]["semantic"]


def compare_api_cli(api, semantic):
    """Compare every selected public outcome rather than infer it from ranking."""
    actual = {
        f: wire(getattr(api, f))
        for f in (
            "status",
            "checkpoint_reached",
            "final_goal_reached",
            "caps",
            "complete",
            "truncated",
            "truncation_reason",
            "expansions",
            "ranking_result",
            "rating_coverage",
            "min_effort",
        )
    }
    actual["engine_reported_guarantees"] = {
        "optimization_scope": api.optimization_scope,
        "is_minimum_proven_over_scope": api.is_minimum_proven_over_scope,
        "is_no_path_proven_over_scope": api.is_no_path_proven_over_scope,
    }
    if any(value != semantic[f] for f, value in actual.items()):
        raise ValueError("API/CLI selected semantic/caps/guarantees/ranking/coverage mismatch")
    compare_programs(api.paths, semantic["candidates"], interface="API/CLI")


def compare_programs(paths, candidates, *, interface):
    """Compare ordered canonical wire(PathResult) records, excluding only candidate_id.

    Identity includes nodes, observed edge records/provenance, cost, ordered
    requests/results (participants, bindings, state/evidence, edge_id and causal
    derived_from_step), final state, scenario and runtime context. The public
    serializer sorts unordered state/fact collections and preserves program order.
    Ranking candidate identifiers are compared separately from program identity.
    """
    expected = [
        {key: value for key, value in candidate.items() if key != "candidate_id"}
        for candidate in candidates
    ]
    if wire(paths) != expected:
        raise ValueError(f"{interface} ordered semantic program identity mismatch")


def probe(raw_dir, output, *, package=PACKAGE):
    """Read-only proposal verification plus ignored public CLI engineering evidence."""
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    pins = {}
    for path in (
        package / "proposal.json",
        package / "oracle.json",
        PACKAGE / "historical-pins.json",
        package / "source-records.json",
        Path(__file__),
        ROOT / "tests/test_asrep_expert_basis.py",
        ROOT / "tests/test_asrep_basis_audit.py",
    ):
        if path.read_bytes() != subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT)}"], cwd=ROOT
        ):
            raise ValueError("Commit basis/oracle/consumer/tests before running the engine")
        pins[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if subprocess.check_output(
        ["git", "diff", "HEAD", "--name-only", "--", "src", "configs", "scripts", "tests"], cwd=ROOT
    ):
        raise ValueError("Executable/test source must be committed before the public probe")
    graph, pending, proposal = build_inputs(raw_dir, revision, package=package)
    graph_before = graph.to_canonical()
    local = ROOT / "reports/generated/issue264"
    local.mkdir(parents=True, exist_ok=True)
    snapshot = local / "snapshot.json"
    snapshot.write_text(serialize_snapshot(graph_before, graph.snapshot_facts), encoding="utf-8")
    oracle = read(package / "oracle.json")
    cases = []
    for label, query in (
        ("pending", pending),
        ("engineering_copy", engineering_review_copy(pending)),
    ):
        active_graph = engineering_graph_copy(graph) if label == "engineering_copy" else graph
        snapshot = local / f"{label}.snapshot.json"
        snapshot.write_text(
            serialize_snapshot(active_graph.to_canonical(), active_graph.snapshot_facts),
            encoding="utf-8",
        )
        config = query["rating_resolution"]
        cli_query = copy.deepcopy(query)
        cli_query.pop("rating_resolution")
        cli, semantic = run_snapshot_case(
            label,
            cli_query,
            config,
            snapshot,
            local,
            label="seamless" if label == "pending" else "synthetic",
        )
        api = run_attack_query(query, active_graph)
        assert_frozen_semantics(semantic, oracle["semantic_cases"]["assumed"])
        compare_api_cli(api, semantic)
        materialized = materialize_query(query, active_graph)
        orchestration = generate_and_evaluate_attack_paths(
            {},
            active_graph.to_canonical(),
            snapshot_facts=active_graph.snapshot_facts,
            actor=materialized.initial_actor,
            initial_state=materialized.initial_attack_state,
            runtime_context=materialized.runtime_context,
            budget=materialized.budget,
            catalog=materialized.catalog,
            scenario_reference=materialized.scenario_reference,
            success_state_predicate=materialized.success_state_predicate,
            semantic_goal=materialized.semantic_goal,
            rating_resolution=config,
        )
        search = orchestration["search_result"]
        assert wire(orchestration["roundtrip_result"]) == semantic["ranking_result"]
        assert all(
            getattr(search, f) == semantic[f]
            for f in ("truncated", "truncation_reason", "complete", "expansions")
        )
        compare_programs(search.paths, semantic["candidates"], interface="orchestration/CLI")
        counts = coverage_counts(api)
        expected = oracle["pending" if label == "pending" else "review_gate_test_copy_only"]
        assert counts == expected, (counts, expected)
        if label == "engineering_copy" and oracle["path_product"] is not None:
            assessment = api.ranking_result["eligible_candidates"]["generated_0001"]
            assert [str(p) for p in assessment["likelihood_interval"]] == oracle["path_product"]
            assert assessment["effort"] == oracle["effort"]
            assert assessment["impact"] == oracle["impact"]
        cases.append(
            {
                "mode": label,
                "counts": counts,
                "cli": cli,
                "API_CLI_selected_semantic_ranking_coverage_programs_equal": True,
                "orchestration_search_ranking_programs_equal": True,
                "orchestration_comparison_scope": (
                    "search completeness/truncation/reason/expansions, "
                    "canonical full PathResult identities excluding candidate_id, and ranking only"
                ),
                "graph_view": "original_verified_raw"
                if label == "pending"
                else "explicit_synthetic_derivative",
                "graph_sha256": graph_digest(active_graph.to_canonical()),
            }
        )
    controls = []
    for name, expected in oracle["semantic_cases"].items():
        if name == "assumed":
            continue
        variant = copy.deepcopy(pending)
        if name == "raw":
            variant["assumptions"] = []
        elif name == "missing_recovery":
            variant["assumptions"] = [
                f for f in variant["assumptions"] if f["predicate"] != "recovery_success"
            ]
        elif name == "asset_veto":
            fact = next(f for f in variant["assumptions"] if f["predicate"] == "admin_channel")
            variant["runtime_facts"] = [{**fact, "value": False, "origin": "blocked_evidence"}]
        elif name == "off":
            variant["allowed_techniques"] = ["obtain_admin_execution_on_host"]
        elif name == "no_request":
            variant["initial_state"]["asrep_request_capability"] = []
        elif name == "step_cap":
            variant["budget"]["max_steps"] = 3
            variant["rating_resolution"]["scope"]["active_work_budget"] = 3
        config = variant.pop("rating_resolution")
        result, semantic = run_snapshot_case(
            name, variant, config, local / "pending.snapshot.json", local, label="seamless"
        )
        assert_frozen_semantics(semantic, expected)
        api_query = {**variant, "rating_resolution": config}
        compare_api_cli(run_attack_query(api_query, graph), semantic)
        result["API_CLI_selected_semantic_ranking_coverage_programs_equal"] = True
        controls.append(result)

    _, frozen, _ = frozen_case(raw_dir, revision)
    baseline = run_attack_query(frozen, graph)
    assert (
        baseline.rating_coverage["numeric_requests"]
        == read(FROZEN_PACKET)["oracle"]["numeric_requests"]
    )
    assert graph.to_canonical() == graph_before
    verify_historical()
    report = {
        "issue": 264,
        "phase": 1,
        "revision": revision,
        "verification_contract": "asrep-public-comparison/2.0.0",
        "program_identity_scope": (
            "Ordered canonical wire(PathResult) records: nodes, edge records/provenance, cost, "
            "ordered transition requests/results including actor/source/target/bindings, "
            "state/evidence, edge_id/derived_from_step, final state, scenario and runtime context"
        ),
        "program_identity_excludes": ["candidate_id"],
        "comparison_limits": (
            "API/CLI selected outcomes/caps/guarantees/Min-Effort/ranking/coverage/programs only; "
            "attempts and diagnostics are not compared. Orchestration exposes only search and "
            "ranking; no status/goal/caps/guarantees/Min-Effort/coverage equality is inferred. "
            "Summary programs list technique names for display, not the identity proof."
        ),
        "committed_input_consumer_test_hashes": pins,
        "original_graph_sha256": graph_digest(graph_before),
        "proposal_status": proposal["status"],
        "independent_b_review": False,
        "numeric_basis_class": proposal["numeric_basis_class"],
        "native_output_label_gap_for_B": (
            "scenario_assumption does not distinguish estimated_expert_scenario; "
            "engineering copy uses synthetic_test_only"
        ),
        "snapshot_id": proposal["snapshot_id"],
        "scenario_id": proposal["scenario_id"],
        "frozen_baseline": coverage_counts(baseline),
        "semantic_controls": controls,
        "cases": cases,
        "proposal_sha256": canonical_digest(proposal),
        "oracle_sha256": canonical_digest(oracle),
        "historical_files_byte_preserved": len(read(PACKAGE / "historical-pins.json")),
        "conditional_assumptions": proposal["semantic_assumptions"],
        "expected_product_if_reviewed": oracle["path_product"],
        "numeric_activation_permitted": False,
        "remaining_gaps": [e["blocker_if_rejected"] for e in proposal["events"]]
        + [
            "B numeric/context review and C/I applicability adoption pending",
            "Natural password rank/completed-compute evidence remains absent",
            "Phase 2 Source A 2/24 and broader generator coverage are unchanged",
        ],
    }
    # CLI commands contain ignored local paths only; summaries contain no new private IDs.
    save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--basis-version", choices=("v1", "v2"), default="v2")
    args = parser.parse_args()
    report = probe(
        args.raw_dir,
        args.output,
        package=ROOT / ("docs/research/ratings/asrep-expert-" + args.basis_version),
    )
    print("Pending proposal preserved; public engineering gate checks passed; no B adoption.")
    print("Evidence:", args.output, "Historical pins:", report["historical_files_byte_preserved"])


if __name__ == "__main__":
    main()
