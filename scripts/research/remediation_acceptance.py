"""Validate #269 contracts and independent expected outputs; executes no search/overlay."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics import load_catalog

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/research/remediation"
FIX = ROOT / "tests/fixtures/remediation"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def schema_validate(name, value, version="v1"):
    schema = read(DOC / f"{name}-{version}.schema.json")
    Draft202012Validator.check_schema(schema)
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as error:
        raise ValueError(error.message) from error


def validate_request(request):
    schema_validate("request", request, "v1.1")
    catalog = read(DOC / "catalog-v1.json")
    require(request["catalog_digest"] == sha(DOC / "catalog-v1.json"), "catalog pin mismatch")
    entries = {e["id"]: e for e in catalog["entries"]}
    keys, ids = set(), set()
    for edit in request["edits"]:
        entry = entries.get(edit["catalog_entry_id"])
        require(
            entry is not None and entry["support"] == "executable_semantics",
            "unsupported intervention",
        )
        require(edit["edit_id"] not in ids, "duplicate edit ID")
        ids.add(edit["edit_id"])
        kind = edit["kind"]
        if kind == "runtime_fact_replace":
            key = edit["key"]
            require(key["predicate"] in entry["predicates"], "gate not in mapping")
            require(
                (entry["layer"] == "runtime" or entry["id"] == "group-membership"),
                "wrong overlay layer",
            )
            require(edit["expected_before"] is not False, "already false is an ineffective fix")
            identity = (
                kind,
                key["predicate"],
                key["subject"],
                key["target"],
                key["authentication_context"],
                key["binding_id"],
            )
        elif kind == "deny_relationship":
            require(entry["layer"] == "relationship", "wrong relationship layer")
            require(
                edit["relationship"]["kind"] in entry["relationships"],
                "relationship not in mapping",
            )
            identity = (kind, edit["edge_id"])
        else:
            require(
                entry["layer"] == "snapshot_fact" and edit["name"] in entry["predicates"],
                "wrong fact layer",
            )
            if edit["name"] == "service_principal_names":
                require(
                    isinstance(edit["expected_before"], list) and edit["after"] == [],
                    "SPN list required",
                )
            else:
                require(
                    edit["expected_before"] is True and edit["after"] is False,
                    "strict boolean fact required",
                )
            identity = (kind, edit["subject"], edit["name"])
        require(identity not in keys, "duplicate or conflicting edit key")
        keys.add(identity)
    # SPN predicates are a coupled configuration, never contradictory independent facts.
    spn = {}
    for edit in request["edits"]:
        if edit["kind"] == "snapshot_fact_replace" and edit["name"] != "dontreqpreauth":
            spn.setdefault(edit["subject"], set()).add(edit["name"])
    require(
        all(names == {"has_spn", "service_principal_names"} for names in spn.values()),
        "SPN edit requires both fact bindings",
    )


def normalized_program_identity(cell, comparison_scope_digest, trace):
    """Hash semantic bindings, never native IDs or run-specific trace locations."""
    actions = []
    for index, action in enumerate(trace["semantic_program"]):
        technique = next((t for t in load_catalog() if t.id == action["technique_id"]), None)
        require(
            technique is not None
            and set(technique.prerequisites) <= {p["predicate"] for p in action["prerequisites"]},
            "semantic identity requires every technique prerequisite",
        )
        require(
            all(parent < index for parent in action["producer_action_indices"]),
            "producer must precede consumer",
        )
        prerequisites = [
            {**p, "evidence_bindings": sorted(p["evidence_bindings"], key=canonical_digest)}
            for p in action["prerequisites"]
        ]
        actions.append(
            {
                **action,
                "prerequisites": sorted(prerequisites, key=canonical_digest),
                "evidence_bindings": sorted(action["evidence_bindings"], key=canonical_digest),
                "producer_action_indices": sorted(action["producer_action_indices"]),
            }
        )
    return canonical_digest(
        {
            "version": "semantic-program/1",
            "comparison_scope_digest": comparison_scope_digest,
            "source_id": cell["source_id"],
            "goal_id": cell["goal_id"],
            "actions": actions,
        }
    )


def validate_result(result):
    schema_validate("result", result, "v1.1")
    keys = set()
    cohort = {(s, g) for s in result["declared_source_ids"] for g in result["declared_goal_ids"]}
    for cell in result["cells"]:
        identity = (cell["source_id"], cell["goal_id"])
        require(
            identity in cohort and identity not in keys, "unknown or duplicate source-goal cell"
        )
        keys.add(identity)
        semantic_ids = {}
        for side in ("before", "after"):
            row = cell[side]
            semantic_ids[side] = {
                ref["program_id"]: normalized_program_identity(
                    cell, result["comparison_scope_digest"], ref
                )
                for ref in row["trace_refs"]
            }
            require(
                len(set(semantic_ids[side].values())) == len(semantic_ids[side]),
                "duplicate normalized program witness",
            )
            require(not (row["complete"] and row["truncated"]), "truncated is not complete")
            require(
                len(row["witness_program_ids"]) == row["program_count"]
                and len(row["route_ids"]) == row["route_count"],
                "witness count mismatch",
            )
            require(
                {v["program_id"] for v in row["trace_refs"]} == set(row["witness_program_ids"]),
                "program trace coverage mismatch",
            )
            require(
                len(row["trace_refs"]) == row["program_count"]
                and {v["route_id"] for v in row["trace_refs"]} == set(row["route_ids"]),
                "route/program association mismatch",
            )
            if row["reachability"] != "reachable":
                require(
                    row["program_count"] == row["route_count"] == 0,
                    "non-reachable cell contains success witnesses",
                )
            if row["reachability"] == "proven_unreachable":
                require(
                    row["complete"]
                    and not row["truncated"]
                    and not row["unresolved_feasibility"]
                    and row["scope_proof_ref"] is not None
                    and row["program_count"] == 0,
                    "negative requires complete feasibility proof",
                )
            if row["reachability"] == "reachable":
                require(
                    row["program_count"] > 0 and row["witness_program_ids"],
                    "reachable requires witness",
                )
        rediscovery = cell["after"]["rediscovery"]
        if rediscovery["status"] in {"complete", "truncated"}:
            require(
                rediscovery["run_id"] == cell["after"]["run_id"] and rediscovery["proof_ref"],
                "rediscovery needs exact rerun proof",
            )
        require(
            cell["after"]["complete"] == (rediscovery["status"] == "complete")
            and cell["after"]["truncated"] == (rediscovery["status"] == "truncated"),
            "after completeness/truncation must match rediscovery status",
        )
        if cell["after"]["reachability"] == "proven_unreachable":
            require(rediscovery["status"] == "complete", "negative needs bypass rediscovery")
        if cell["disconnected"]:
            require(
                result["overlay_disposition"] == "applied"
                and cell["before"]["reachability"] == "reachable"
                and cell["after"]["reachability"] == "proven_unreachable",
                "unproven disconnection",
            )
        before_ids, after_ids = (
            set(cell[side]["witness_program_ids"]) for side in ("before", "after")
        )
        require(
            set(cell["cut_program_ids"]) <= before_ids
            and set(cell["affected_program_ids"]) <= before_ids,
            "unknown baseline program",
        )
        require(
            {semantic_ids["before"][pid] for pid in cell["cut_program_ids"]}.isdisjoint(
                semantic_ids["after"].values()
            ),
            "cut semantic program survived",
        )
        require(
            set(cell["bypass_program_ids"]) == after_ids,
            "bypass list must include every normalized after witness",
        )
        require(
            set(cell["new_program_ids"])
            == {
                pid
                for pid, identity in semantic_ids["after"].items()
                if identity not in semantic_ids["before"].values()
            },
            "new programs must use normalized semantic identity",
        )
        require(set(cell["cut_route_ids"]) <= set(cell["before"]["route_ids"]), "unknown cut route")
        require(
            {v["program_id"] for v in cell["replay_failures"]} == set(cell["cut_program_ids"]),
            "cut requires replay decision lineage",
        )
        require(cell["affected"] == bool(cell["affected_program_ids"]), "affected flag mismatch")
        require(
            set(cell["cut_program_ids"]) <= set(cell["affected_program_ids"]),
            "cut program must be affected",
        )
        expected_cut_routes = {
            rid
            for rid in cell["before"]["route_ids"]
            if rid not in cell["after"]["route_ids"]
            and all(
                ref["program_id"] in cell["cut_program_ids"]
                for ref in cell["before"]["trace_refs"]
                if ref["route_id"] == rid
            )
        }
        require(
            set(cell["cut_route_ids"]) == expected_cut_routes,
            "route cut needs all associated programs invalidated",
        )
        if result["overlay_disposition"] != "applied":
            require(
                not cell["affected"] and not cell["cut_program_ids"] and not cell["disconnected"],
                "unapplied overlay cannot claim effect",
            )
        effort = cell["effort"]
        for side in ("before", "after"):
            if effort[side] is not None:
                require(
                    effort[side] >= 0
                    and cell[side]["reachability"] == "reachable"
                    and effort["basis_refs"]
                    and effort["unit"],
                    "numeric C needs a rated witnessed program",
                )
        if effort["status"] == "unrated":
            require(
                all(effort[v] is None for v in ("before", "after", "delta")),
                "unrated C must stay null",
            )
        if cell["after"]["reachability"] != "reachable":
            require(
                effort["after"] is None and effort["delta"] is None,
                "no numeric C without after witness",
            )
        if effort["status"] == "exact":
            require(
                effort["basis_refs"]
                and effort["proof_refs"]
                and effort["unit"]
                and all(
                    effort[side] is not None
                    and effort[side] >= 0
                    and cell[side]["reachability"] == "reachable"
                    and cell[side]["complete"]
                    and not cell[side]["truncated"]
                    and not cell[side]["unresolved_feasibility"]
                    for side in ("before", "after")
                ),
                "exact C needs complete rated witnessed minima",
            )
        if effort["delta"] is not None:
            require(effort["status"] == "exact", "effort delta needs rated certified minima")
            require(effort["delta"] == effort["after"] - effort["before"], "effort delta mismatch")
        probability = cell["conditional_p"]
        for side in ("before", "after"):
            interval = probability[f"{side}_interval"]
            if interval is not None:
                require(
                    0 <= interval[0] <= interval[1] <= 1
                    and probability[f"{side}_program_id"] in cell[side]["witness_program_ids"]
                    and cell[side]["reachability"] == "reachable"
                    and probability["basis_refs"],
                    "numeric P needs a rated witnessed program",
                )
        if probability["status"] == "unrated":
            require(
                probability["before_interval"] is None and probability["after_interval"] is None,
                "unrated P must stay null",
            )
        if probability["status"] != "comparable":
            require(probability["delta_interval"] is None, "unrated/incomparable P delta forbidden")
        else:
            require(
                probability["comparison_scope_digest"] == result["comparison_scope_digest"],
                "comparable P must match the result comparison scope",
            )
            require(
                probability["comparison_scope_digest"]
                and probability["basis_refs"]
                and probability["before_program_id"]
                and probability["after_program_id"],
                "P comparability lineage required",
            )
            require(
                probability["before_program_id"] in before_ids
                and probability["after_program_id"] in after_ids
                and all(cell[side]["reachability"] == "reachable" for side in ("before", "after")),
                "P needs exact successful programs",
            )
            before, after = probability["before_interval"], probability["after_interval"]
            require(
                before is not None
                and after is not None
                and all(0 <= v[0] <= v[1] <= 1 for v in (before, after)),
                "invalid P intervals",
            )
            require(
                probability["delta_interval"] == [after[0] - before[1], after[1] - before[0]],
                "P delta interval mismatch",
            )
    summary = result["summary"]
    if result["overlay_disposition"] != "applied":
        require(
            not summary["fully_disconnected_sources"]
            and all(
                c["after"]["reachability"] in {"unknown", "error", "not_evaluated", "unsupported"}
                for c in result["cells"]
            ),
            "unapplied overlay has no after exposure proof",
        )
    require(summary["requested_pairs"] == len(cohort), "declared cohort denominator mismatch")
    for side in ("before", "after"):
        require(
            set(summary[f"exposed_sources_{side}"])
            == {c["source_id"] for c in result["cells"] if c[side]["reachability"] == "reachable"},
            "exposed source summary mismatch",
        )
    require(
        set(summary["affected_sources"])
        == {c["source_id"] for c in result["cells"] if c["affected"]},
        "affected source summary mismatch",
    )
    require(
        set(summary["goals_still_reachable"])
        == {c["goal_id"] for c in result["cells"] if c["after"]["reachability"] == "reachable"},
        "reachable goal summary mismatch",
    )
    require(
        set(summary["fully_disconnected_sources"])
        == {
            s
            for s in summary["exposed_sources_before"]
            if all(
                any(
                    c["source_id"] == s
                    and c["goal_id"] == g
                    and c["after"]["reachability"] == "proven_unreachable"
                    for c in result["cells"]
                )
                for g in result["declared_goal_ids"]
            )
        },
        "fully disconnected source proof mismatch",
    )
    require(
        summary["unknown_pairs"]
        == len(cohort - keys)
        + sum(
            any(
                c[side]["reachability"] in {"unknown", "error", "not_evaluated"}
                for side in ("before", "after")
            )
            for c in result["cells"]
        ),
        "unknown coverage mismatch",
    )
    require(
        summary["unsupported_pairs"]
        == sum(
            any(c[side]["reachability"] == "unsupported" for side in ("before", "after"))
            for c in result["cells"]
        ),
        "unsupported coverage mismatch",
    )
    require(
        summary["truncated_pairs"]
        == sum(any(c[side]["truncated"] for side in ("before", "after")) for c in result["cells"]),
        "truncation coverage mismatch",
    )
    for metric_name, numerator, denominator in [
        (
            "programs_cut",
            sum(len(c["cut_program_ids"]) for c in result["cells"]),
            sum(c["before"]["program_count"] for c in result["cells"]),
        ),
        (
            "routes_cut",
            sum(len(c["cut_route_ids"]) for c in result["cells"]),
            sum(c["before"]["route_count"] for c in result["cells"]),
        ),
        (
            "pairs_disconnected",
            sum(c["disconnected"] for c in result["cells"]),
            sum(c["before"]["reachability"] == "reachable" for c in result["cells"]),
        ),
    ]:
        require(
            (summary[metric_name]["numerator"], summary[metric_name]["denominator"])
            == (numerator, denominator),
            "metric witness denominator mismatch",
        )
    require(
        summary["evaluated_pairs"] == len(keys) <= summary["requested_pairs"],
        "pair denominator mismatch",
    )
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        metric = summary[name]
        require(metric["numerator"] <= metric["denominator"], "invalid metric fraction")
        if metric["scope"] == "unknown":
            require(metric["percent"] is None, "unknown scope cannot claim percentage")
        elif metric["percent"] is not None:
            require(
                metric["denominator"] > 0
                and metric["percent"] == 100 * metric["numerator"] / metric["denominator"],
                "percentage denominator mismatch",
            )
        if metric["scope"] == "complete_declared_scope":
            require(
                result["overlay_disposition"] == "applied"
                and summary["requested_pairs"] == len(keys)
                and all(c["after"]["rediscovery"]["status"] == "complete" for c in result["cells"])
                and all(
                    cell[side]["complete"]
                    and cell[side]["reachability"] in {"reachable", "proven_unreachable"}
                    and not cell[side]["truncated"]
                    and not cell[side]["unresolved_feasibility"]
                    for cell in result["cells"]
                    for side in ("before", "after")
                ),
                "global percentage requires complete comparable cohort",
            )
    actual_disconnected = {
        (c["source_id"], c["goal_id"]) for c in result["cells"] if c["disconnected"]
    }
    require(
        actual_disconnected
        == {(p["source_id"], p["goal_id"]) for p in summary["proven_disconnected_pairs"]},
        "pair proof list mismatch",
    )


def check():
    from scripts.research.attack_scenarios import validate_catalog_binding

    catalog = read(DOC / "catalog-v1.json")
    schema_validate("catalog", catalog)
    validate_catalog_binding(
        {
            "bindings": {"catalog_digest": catalog["semantic_catalog_sha256"]},
            "scenarios": [
                {"oracle_scope": {"techniques": entry["techniques"]}}
                for entry in catalog["entries"]
            ],
        },
        ROOT / "configs/attack_semantics.yml",
    )
    techniques = {t.id: t for t in load_catalog()}
    ids = [e["id"] for e in catalog["entries"]]
    require(len(ids) == len(set(ids)), "duplicate catalog ID")
    for entry in catalog["entries"]:
        require(set(entry["techniques"]) <= techniques.keys(), "unknown mapped technique")
        prerequisites = {p for t in entry["techniques"] for p in techniques[t].prerequisites}
        require(set(entry["predicates"]) <= prerequisites, "invented prerequisite")
    for example in FIX.glob("request-*-v1.1.json"):
        validate_request(read(example))
    binding = read(DOC / "seamless-v1.json")
    for pin in (binding["raw_manifest"], binding["scenario_pin"]):
        require(sha(ROOT / pin["path"]) == pin["sha256"], "SEAMLESS binding drift")
    validate_result(read(FIX / "result-bypass-v1.1.json"))
    request = read(FIX / "request-v1.1.json")
    validate_request(request)
    result = read(FIX / "result-v1.1.json")
    validate_result(result)
    require(
        result["comparison_scope_digest"] == canonical_digest(request["scope"])
        and result["overlay_digest"] == canonical_digest(request["edits"]),
        "comparison/overlay digest mismatch",
    )
    require(
        result["request_id"] == request["request_id"]
        and result["catalog_digest"] == request["catalog_digest"]
        and result["baseline_input_digest_after"] == request["scope"]["graph_digest"],
        "request/result binding mismatch",
    )
    return {
        "status": "passed",
        "catalog_entries": len(ids),
        "oracle_cases": len(read(FIX / "finite-v1.json")["cases"]),
    }


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
