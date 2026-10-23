"""Narrow #175 SEAMLESS traceability check using accepted #181/#182 inputs.

Raw identifiers and full traces stay in an ignored output. This entry point uses
real search; it does not use Week 3 numeric ratings as a reachability oracle.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.attack_scenarios import (  # noqa: E402
    file_digest,
    keys,
    validate_catalog_binding,
)
from scripts.research.reviewed_parameter_release import verify_release  # noqa: E402
from scripts.research.week3_semantic_bridge_probe import (  # noqa: E402
    PLAN,
    load_acceptance_inputs,
    overlay,
)
from src.data.manifest import (  # noqa: E402
    raw_file_reference,
    read_verified_snapshot_file,
    verify_manifest,
)
from src.engine import EngineGraph, SearchBudget, generate_attack_paths  # noqa: E402
from src.engine.semantics import load_catalog  # noqa: E402
from src.engine.semantics.evidence_view import digest  # noqa: E402
from src.engine.semantics.week3 import runtime_for_projection  # noqa: E402

DEFAULT = ROOT / "tests/fixtures/attack_scenarios/seamless.json"


def load_binding(path=DEFAULT):
    binding = json.loads(path.read_text(encoding="utf-8"))
    keys(
        binding,
        {
            "schema_version",
            "case_id",
            "source",
            "accepted_revision",
            "snapshot_id",
            "graph_digest",
            "input_pins",
            "expected_techniques",
            "terminal_predicate",
            "scope",
        },
    )
    if (
        binding["schema_version"] != "1.0.0"
        or binding["terminal_predicate"] != "admin_control(target)"
    ):
        raise ValueError("unsupported SEAMLESS trace contract")
    if binding["case_id"] != "w3-source-b-positive" or binding["source"] != "source_b":
        raise ValueError("only narrow accepted Source B positive case is declared")
    for pin in binding["input_pins"]:
        keys(pin, {"path", "file_digest"})
        path = (ROOT / pin["path"]).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("integration binding file digest mismatch")
        if pin["path"] == "configs/attack_semantics.yml":
            validate_catalog_binding(
                {
                    "bindings": {"catalog_digest": pin["file_digest"]},
                    "scenarios": [{"oracle_scope": {"techniques": binding["expected_techniques"]}}],
                },
                path,
            )
        elif file_digest(path) != pin["file_digest"]:
            raise ValueError("integration binding file digest mismatch")
    if set(binding["expected_techniques"]) - {t.id for t in load_catalog()}:
        raise ValueError("unknown integration technique")
    if binding["scope"] != "reviewed_source_b_programs_in_bounded_search":
        raise ValueError("unsupported integration scope")
    return binding


def resolve(payload, pointer):
    value = payload
    for token in pointer.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def raw_edge_trace(graph, candidate, raw_dir, manifest):
    """Verify exact reviewed locators against raw and canonical edge provenance."""
    edges = {e["id"]: e for e in graph["edges"]}
    rows = []
    for route in candidate["structural_routes"]:
        if len(route["edge_ids"]) != len(route["provenance_locators"]):
            raise ValueError("route locator count differs from edge count")
        for index, (edge_id, locator) in enumerate(
            zip(route["edge_ids"], route["provenance_locators"], strict=True)
        ):
            edge = edges[edge_id]
            if (edge["source"], edge["target"]) != tuple(route["node_ids"][index : index + 2]):
                raise ValueError("route edge direction mismatch")
            filename, pointer = locator.split("#", 1)
            raw = json.loads(
                read_verified_snapshot_file(
                    raw_dir, manifest, raw_file_reference(manifest, filename)
                ).decode("utf-8-sig")
            )
            raw_value = resolve(raw, pointer)
            field = "Members" if edge["kind"] == "MemberOf" else "Aces"
            tokens = pointer.strip("/").split("/")
            record = resolve(raw, "/".join(tokens[: tokens.index(field)]))
            if record.get("ObjectIdentifier") != edge["target"]:
                raise ValueError("raw record differs from edge target")
            if field == "Aces":
                valid = (
                    raw_value.get("PrincipalSID") == edge["source"]
                    and raw_value.get("RightName") == edge["kind"]
                )
            else:
                valid = (
                    raw_value.get("MemberId", raw_value.get("ObjectIdentifier")) == edge["source"]
                )
            if not valid:
                raise ValueError("raw locator does not prove canonical relationship")
            provenance = [
                p
                for p in edge["provenance"]
                if p["raw_file"].endswith("/" + filename)
                and p.get("record_id") == edge["target"]
                and p.get("attribute", "").startswith(field)
            ]
            if not provenance:
                raise ValueError("canonical provenance does not bind raw record/attribute")
            rows.append(
                {
                    "raw_locator": locator,
                    "edge_id": edge_id,
                    "relationship": edge["kind"],
                    "provenance": provenance,
                }
            )
    return rows


def run(graph_path, raw_dir, binding_path=DEFAULT):
    binding = load_binding(binding_path)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    manifest, pins = load_acceptance_inputs(ROOT, plan)
    release_path = ROOT / manifest["release"]["path"]
    release = verify_release(json.loads(release_path.read_text(encoding="utf-8")))
    raw_manifest = json.loads(
        (ROOT / manifest["release"]["raw_manifest"]["path"]).read_text(encoding="utf-8")
    )
    if digest(raw_manifest) != manifest["release"]["raw_manifest"]["canonical_digest"]:
        raise ValueError("raw manifest canonical pin mismatch")
    if verify_manifest(raw_dir, raw_manifest):
        raise ValueError("raw dataset differs from accepted manifest")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    EngineGraph.from_canonical(graph)
    if (
        graph["metadata"]["snapshot_id"] != binding["snapshot_id"]
        or raw_manifest["snapshot_id"] != binding["snapshot_id"]
    ):
        raise ValueError("snapshot differs from accepted binding")
    baseline_digest = digest(graph)
    if baseline_digest != binding["graph_digest"]:
        raise ValueError("canonical graph differs from pinned integration input")
    case = next(c for c in manifest["cases"] if c["case_id"] == binding["case_id"])
    config = plan["cases"][case["case_id"]]
    source = plan["sources"][binding["source"]]
    projection = overlay(release["query_projections"][binding["source"]], case["overlay"])
    if digest(projection) != case["input"]["overlaid_digest"]:
        raise ValueError("accepted projection overlay mismatch")
    state, context = runtime_for_projection(projection["query"], source, config)
    generated = generate_attack_paths(
        EngineGraph.from_canonical(graph),
        source["actor"],
        initial_state=state,
        runtime_context=context,
        target_predicate=lambda n: n["id"] == source["target"],
        success_state_predicate=lambda s: source["target"] in s.admin_control,
        budget=SearchBudget(**source["budget"]),
        catalog=tuple(t for t in load_catalog() if t.id in source["semantic_catalog"]),
        scenario_reference=case["case_id"],
    )
    action_bindings = {
        tuple(b[k] for k in ("technique_id", "actor", "source", "target")): b["action_id"]
        for b in source["transition_action_bindings"]
    }
    reviewed = {tuple(c["bound_action_ids"]): c for c in projection["candidates"]}
    programs = []
    for path in generated.paths:
        sequence = tuple(
            action_bindings.get(
                tuple(
                    getattr(s.result.request, k)
                    for k in ("technique_id", "actor", "source", "target")
                )
            )
            for s in path.transition_history
        )
        if sequence not in reviewed:
            raise ValueError("generated program outside narrow reviewed scope")
        if [s.result.technique.id for s in path.transition_history] != binding[
            "expected_techniques"
        ]:
            raise ValueError("generated techniques differ from explicit accepted trace")
        raw_trace = raw_edge_trace(graph, reviewed[sequence], raw_dir, raw_manifest)
        by_edge = {r["edge_id"]: r for r in raw_trace}
        steps = []
        for step in path.transition_history:
            result = step.result
            if result.status.value != "applicable":
                raise ValueError("unconfirmed transition in demonstrated path")
            steps.append(
                {
                    "request": vars(result.request),
                    "edge_id": step.edge_id,
                    "raw_binding": by_edge.get(step.edge_id),
                    "derived_from_step": step.derived_from_step,
                    "state_additions": {
                        f: sorted(getattr(result.additions, f))
                        for f in result.additions.__dataclass_fields__
                        if getattr(result.additions, f)
                    },
                    "runtime_predicates": [
                        {
                            "predicate": d.predicate,
                            "origin": d.origin.value,
                            "value": d.fact.value if d.fact else None,
                            "subject": d.fact.subject if d.fact else None,
                            "target": d.fact.target if d.fact else None,
                            "scope": d.fact.scope if d.fact else None,
                        }
                        for d in result.decisions
                    ],
                }
            )
        if source["target"] not in path.final_state.admin_control:
            raise ValueError("terminal security goal not satisfied")
        programs.append(
            {"action_ids": sequence, "steps": steps, "terminal": "admin_control(target)"}
        )
    if not programs or {tuple(p["action_ids"]) for p in programs} != set(reviewed):
        raise ValueError("search did not discover required reviewed program")
    if digest(graph) != baseline_digest:
        raise ValueError("canonical snapshot mutated")
    report = {
        "case_id": case["case_id"],
        "status": "passed",
        "programs": programs,
        "complete": generated.complete,
        "truncated": generated.truncated,
        "truncation_reason": generated.truncation_reason,
        "expansions": generated.expansions,
        "bounds": source["budget"],
        "candidate_source": "generate_attack_paths",
        "pins": {
            **pins,
            "accepted_revision": binding["accepted_revision"],
            "revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "graph_digest": baseline_digest,
            "graph_file_digest": file_digest(graph_path),
            "raw_manifest_digest": digest(raw_manifest),
            "snapshot_id": binding["snapshot_id"],
            "catalog_digest": file_digest(ROOT / "configs/attack_semantics.yml"),
            "harness_digest": file_digest(Path(__file__)),
            "initial_state_digest": digest(
                {f: sorted(getattr(state, f)) for f in state.__dataclass_fields__}
            ),
            "runtime_context_digest": digest(
                {
                    "authentication_context": context.authentication_context,
                    "facts": [vars(context.facts[k]) for k in sorted(context.facts)],
                }
            ),
            "python": sys.version,
        },
        "non_claim": (
            "Integration trace only; no numeric ratings or global exhaustive reachability claim."
        ),
    }
    report["report_digest"] = digest(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--binding", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.output.resolve().is_relative_to((ROOT / "reports/generated").resolve()):
        parser.error("full AD trace must stay in ignored reports/generated")
    report = run(args.graph, args.raw_dir, args.binding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "case_id",
                    "status",
                    "complete",
                    "truncated",
                    "expansions",
                    "report_digest",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
