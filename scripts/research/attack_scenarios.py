"""Strict golden scenario contract and public-API prediction harness (Refs #175).

Expected states are authored in fixtures; this module never manufactures an oracle
from evaluator output. No observed activity, ratings or probabilities are inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine import EngineGraph, SearchBudget, generate_attack_paths  # noqa: E402
from src.engine.semantics import (  # noqa: E402
    AttackState,
    RuntimeContext,
    RuntimeFact,
    apply_transition,
    load_catalog,
)
from src.engine.semantics.evaluator import evaluate  # noqa: E402
from src.engine.semantics.models import StructuralRelationship  # noqa: E402
from src.engine.semantics.transitions import TransitionRequest  # noqa: E402

DEFAULT = ROOT / "tests/fixtures/attack_scenarios/suite.json"
ARCHIVED_CATALOG = DEFAULT.with_name("catalog-v0.6.yml")
PAIRS = {"effective_member", "interactive_session", "remote_command_execution", "usable_identity"}
RELATIONS = {"permission", "relationship_added"}
FIELDS = set(AttackState.__dataclass_fields__)


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def file_digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional):
        raise ValueError(f"unknown fields or non-object: {value!r}")
    if set(required) - set(value):
        raise ValueError(f"missing fields: {set(required) - set(value)}")


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected nonempty string")


def array(value):
    if not isinstance(value, list):
        raise ValueError("expected array")
    return value


def state_from(spec, aliases):
    keys(spec, (), FIELDS)

    def node(value):
        if not isinstance(value, str) or value not in aliases:
            raise ValueError(f"invalid node reference: {value!r}")
        return aliases[value]

    normalized = {}
    for field, values in spec.items():
        entries = []
        for value in array(values):
            if field in PAIRS:
                if not isinstance(value, list) or len(value) != 2:
                    raise ValueError(f"{field} requires node pairs")
                entries.append(tuple(node(v) for v in value))
            elif field in RELATIONS:
                if not isinstance(value, list) or len(value) != 3:
                    raise ValueError(f"{field} requires source/kind/target triples")
                entries.append(StructuralRelationship(node(value[0]), value[1], node(value[2])))
            else:
                entries.append(node(value))
        if len(entries) != len(set(entries)):
            raise ValueError("duplicate state entry")
        normalized[field] = frozenset(entries)
    return AttackState(**normalized)


def state_json(state, aliases):
    names = {value: key for key, value in aliases.items()}
    result = {}
    for field in sorted(FIELDS):
        values = getattr(state, field)
        if values:
            result[field] = sorted(
                [names[v.source], v.kind, names[v.target]]
                if field in RELATIONS
                else [names[x] for x in v]
                if field in PAIRS
                else names[v]
                for v in values
            )
    return result


def validate_state(spec, aliases, nodes):
    state = state_from(spec, aliases)
    for field in PAIRS:
        for source, target in getattr(state, field):
            expected_kind = "Group" if field == "effective_member" else "Computer"
            if nodes[target]["kind"] != expected_kind:
                raise ValueError(f"{field} requires {expected_kind} target")
            if field == "usable_identity" and nodes[source]["kind"] != "User":
                raise ValueError("usable_identity requires a User")
    for field in {"authentication_control", "reset_password_control", "credential_material"}:
        if any(nodes[node]["kind"] != "User" for node in getattr(state, field)):
            raise ValueError(f"{field} requires User nodes")
    if any(nodes[node]["kind"] != "Computer" for node in state.admin_control):
        raise ValueError("admin_control requires Computer nodes")
    for field in RELATIONS:
        for relation in getattr(state, field):
            compatible = any(
                t.relationship == relation.kind
                and nodes[relation.source]["kind"] in t.source_kinds
                and nodes[relation.target]["kind"] in t.target_kinds
                for t in load_catalog()
            )
            if not compatible:
                raise ValueError("incompatible derived structural relationship endpoints")
    return state


def contains(state, expected):
    return all(getattr(expected, f) <= getattr(state, f) for f in FIELDS)


def forbidden(state, expected):
    return any(getattr(expected, f) & getattr(state, f) for f in FIELDS)


def materialize(case, variant):
    initial = variant.get("initial_state", case["initial_state"])
    facts = deepcopy(case["runtime_facts"])
    for change in variant["fact_changes"]:
        key = change["key"]
        matches = [f for f in facts if [f["predicate"], f["subject"], f["target"]] == key]
        if len(matches) != 1:
            raise ValueError(f"delta must reference exactly one runtime fact: {key}")
        if change["operation"] == "remove":
            facts.remove(matches[0])
        else:
            matches[0]["value"] = change["value"]
            matches[0]["origin"] = "blocked_evidence" if change["value"] is False else "unknown"
    return initial, facts


def load_suite(path=DEFAULT):
    suite = json.loads(path.read_text(encoding="utf-8"))
    validate_suite(suite, path.parent)
    return suite


def validate_catalog_binding(suite, current, archived=ARCHIVED_CATALOG):
    """Allow unreferenced additions while keeping frozen owners and catalog metadata intact."""
    expected = suite["bindings"]["catalog_digest"]
    if expected == file_digest(current):
        return
    if expected != file_digest(archived):
        raise ValueError("catalog digest mismatch; no matching archived catalog")
    old, new = (yaml.safe_load(path.read_text(encoding="utf-8")) for path in (archived, current))
    if {k: v for k, v in old.items() if k != "techniques"} != {
        k: v for k, v in new.items() if k != "techniques"
    }:
        raise ValueError("catalog metadata changed; review oracle before rebinding")
    previous = {t["id"]: t for t in old["techniques"]}
    live = {t["id"]: t for t in new["techniques"]}
    owners = {t for case in suite["scenarios"] for t in case["oracle_scope"]["techniques"]}
    if any(t not in previous or previous[t] != live.get(t) for t in owners):
        raise ValueError("catalog owner changed; review oracle before rebinding")


def validate_suite(suite, base):
    """Executable schema v1: reject every unknown field, type and broken binding."""
    keys(suite, {"schema_version", "bindings", "graphs", "evidence", "scenarios"})
    if suite["schema_version"] != "1.0.0":
        raise ValueError("unsupported golden scenario schema")
    keys(
        suite["bindings"],
        {"contract_version", "contract_digest", "catalog_version", "catalog_digest"},
    )
    bindings = suite["bindings"]
    if bindings["contract_version"] != "1.3.0" or bindings["catalog_version"] != "0.6":
        raise ValueError("incompatible semantic/graph contract version")
    for name, filename in (("contract", "contract.yml"), ("catalog", "attack_semantics.yml")):
        if name == "catalog":
            validate_catalog_binding(suite, ROOT / "configs" / filename)
            continue
        if bindings[name + "_digest"] != file_digest(ROOT / "configs" / filename):
            raise ValueError(f"{name} digest mismatch; review oracle before rebinding")
    catalog = {t.id: t for t in load_catalog()}
    keys(suite["evidence"], (), suite["evidence"])
    for row in suite["evidence"].values():
        keys(row, {"url", "section", "claim", "limit"})
        for value in row.values():
            text(value)
        if not row["url"].startswith("https://"):
            raise ValueError("evidence needs primary source URL")
    graph_data = {}
    keys(suite["graphs"], (), suite["graphs"])
    for name, binding in suite["graphs"].items():
        text(name)
        keys(binding, {"path", "digest", "snapshot_id", "aliases"})
        text(binding["path"])
        graph_path = (base / binding["path"]).resolve()
        if not graph_path.is_relative_to(base.resolve()):
            raise ValueError("fixture path escapes scenario directory")
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        EngineGraph.from_canonical(graph)
        if graph["metadata"]["contract_version"] != bindings["contract_version"]:
            raise ValueError("graph contract differs from suite")
        if not graph["metadata"].get("synthetic"):
            raise ValueError("normative suite requires synthetic fixtures")
        if (
            digest(graph) != binding["digest"]
            or graph["metadata"]["snapshot_id"] != binding["snapshot_id"]
        ):
            raise ValueError("graph/snapshot digest mismatch")
        aliases = binding["aliases"]
        keys(aliases, (), aliases)
        for alias, node in aliases.items():
            text(alias)
            text(node)
        if set(aliases.values()) != {n["id"] for n in graph["nodes"]} or len(aliases) != len(
            set(aliases.values())
        ):
            raise ValueError("aliases must bijectively name fixture nodes")
        graph_data[name] = graph
    seen = set()
    for case in array(suite["scenarios"]):
        keys(
            case,
            {
                "scenario_id",
                "version",
                "description",
                "graph",
                "initial_actor",
                "initial_state",
                "authentication_context",
                "target_goal",
                "runtime_facts",
                "steps",
                "oracle_scope",
                "variants",
                "evidence_refs",
            },
        )
        for f in ("scenario_id", "description", "graph"):
            text(case[f])
        if not re.fullmatch(r"[a-z][a-z0-9-]+", case["scenario_id"]) or case["scenario_id"] in seen:
            raise ValueError("invalid/duplicate scenario ID")
        seen.add(case["scenario_id"])
        if case["version"] != "1.0.0" or case["graph"] not in graph_data:
            raise ValueError("invalid scenario version/graph reference")
        graph = graph_data[case["graph"]]
        aliases = suite["graphs"][case["graph"]]["aliases"]
        nodes = {n["id"]: n for n in graph["nodes"]}
        if case["initial_actor"] not in aliases or case["authentication_context"] not in {
            None,
            *aliases,
        }:
            raise ValueError("invalid actor/authentication context")
        validate_state(case["initial_state"], aliases, nodes)
        goal = case["target_goal"]
        keys(goal, {"target", "required_state"})
        if goal["target"] not in aliases or not goal["required_state"]:
            raise ValueError("goal requires target and explicit security predicate")
        goal_state = validate_state(goal["required_state"], aliases, nodes)
        if not any(vars(goal_state).values()):
            raise ValueError("empty success predicate")
        target_id = aliases[goal["target"]]
        referenced = set()
        for field in FIELDS:
            for value in getattr(goal_state, field):
                if field in RELATIONS:
                    referenced.update((value.source, value.target))
                elif field in PAIRS:
                    referenced.update(value)
                else:
                    referenced.add(value)
        if target_id not in referenced:
            raise ValueError("success predicate must reference target asset")
        refs = array(case["evidence_refs"])
        if not refs or set(refs) - set(suite["evidence"]):
            raise ValueError("unknown/empty evidence references")
        scope = case["oracle_scope"]
        keys(scope, {"techniques", "budget", "completeness", "path_policy"})
        ids = array(scope["techniques"])
        if len(ids) != len(set(ids)) or set(ids) - set(catalog):
            raise ValueError("unknown/duplicate catalog owner")
        keys(scope["budget"], {"max_paths", "max_steps", "max_expansions"})
        SearchBudget(**scope["budget"])
        if scope["completeness"] != "finite_declared_catalog" or scope["path_policy"] not in {
            "exact_set",
            "causal_alternatives",
        }:
            raise ValueError("unsupported completeness/path policy")
        facts_seen = set()
        for fact in array(case["runtime_facts"]):
            keys(
                fact,
                {
                    "predicate",
                    "subject",
                    "target",
                    "value",
                    "origin",
                    "scope",
                    "rationale",
                    "evidence_ref",
                },
            )
            for field in ("predicate", "scope", "rationale"):
                text(fact[field])
            if (
                fact["subject"] not in aliases
                or fact["target"] not in aliases
                or fact["evidence_ref"] not in refs
            ):
                raise ValueError("invalid runtime/evidence reference")
            if type(fact["value"]) not in {bool, type(None)} or fact["origin"] not in {
                "declared_assumption",
                "observed_evidence",
                "blocked_evidence",
                "unknown",
            }:
                raise ValueError("invalid runtime value/origin")
            identity = fact["predicate"], fact["subject"], fact["target"]
            if identity in facts_seen:
                raise ValueError("duplicate/contradictory fact")
            facts_seen.add(identity)
        step_ids = set()
        request_ids = set()
        for step in array(case["steps"]):
            keys(
                step,
                {
                    "step_id",
                    "request",
                    "before",
                    "expected",
                    "edge_id",
                    "derived_from",
                    "explanation",
                    "evidence_refs",
                },
            )
            text(step["step_id"])
            if step["step_id"] in step_ids:
                raise ValueError("duplicate step")
            request = step["request"]
            keys(request, {"technique_id", "actor", "source", "target"})
            request_id = tuple(request[k] for k in ("technique_id", "actor", "source", "target"))
            if request_id in request_ids:
                raise ValueError("ambiguous duplicate transition binding")
            request_ids.add(request_id)
            if request["technique_id"] not in ids or any(
                request[n] not in aliases for n in ("actor", "source", "target")
            ):
                raise ValueError("invalid transition reference")
            technique = catalog[request["technique_id"]]
            if (
                nodes[aliases[request["source"]]]["kind"] not in technique.source_kinds
                or nodes[aliases[request["target"]]]["kind"] not in technique.target_kinds
            ):
                raise ValueError("incompatible transition endpoints")
            if step["edge_id"] is not None:
                support_kind = (
                    "GenericAll"
                    if technique.relationship == "DeclaredHostAdmin"
                    else technique.relationship
                )
                if not any(
                    e["id"] == step["edge_id"]
                    and (e["source"], e["kind"], e["target"])
                    == (aliases[request["source"]], support_kind, aliases[request["target"]])
                    for e in graph["edges"]
                ):
                    raise ValueError("incompatible edge/transition binding")
                if step["derived_from"] is not None:
                    raise ValueError("structural step cannot have derived parent")
            elif step["derived_from"] not in step_ids:
                raise ValueError("derived step requires earlier causal parent")
            elif step["expected"]["status"] == "applicable":
                parent = next(s for s in case["steps"] if s["step_id"] == step["derived_from"])
                additions = parent["expected"]["additions"]
                if technique.relationship == "AuthenticationControl":
                    supported = request["source"] in additions.get("reset_password_control", [])
                else:
                    relation = [request["source"], technique.relationship, request["target"]]
                    supported = relation in additions.get(
                        "permission", []
                    ) or relation in additions.get("relationship_added", [])
                if not supported:
                    raise ValueError("incompatible derived transition parent")
            step_ids.add(step["step_id"])
            validate_state(step["before"], aliases, nodes)
            validate_state(step["expected"]["additions"], aliases, nodes)
            validate_expectation(step["expected"], aliases, technique)
            text(step["explanation"])
            if not array(step["evidence_refs"]) or set(step["evidence_refs"]) - set(refs):
                raise ValueError("invalid step evidence")
        variants_seen = set()
        for variant in array(case["variants"]):
            keys(
                variant,
                {
                    "variant_id",
                    "description",
                    "fact_changes",
                    "transition_overrides",
                    "expected_search",
                },
                {"initial_state"},
            )
            text(variant["variant_id"])
            text(variant["description"])
            if variant["variant_id"] in variants_seen:
                raise ValueError("duplicate variant")
            variants_seen.add(variant["variant_id"])
            for change in array(variant["fact_changes"]):
                keys(change, {"key", "operation"}, {"value"})
                if not isinstance(change["key"], list) or tuple(change["key"]) not in facts_seen:
                    raise ValueError("invalid fact delta")
                if change["operation"] == "remove":
                    if "value" in change:
                        raise ValueError("remove cannot supply a value")
                elif change["operation"] == "set":
                    if "value" not in change or type(change["value"]) not in {bool, type(None)}:
                        raise ValueError("set requires bool/null")
                else:
                    raise ValueError("invalid delta operation")
            initial, _ = materialize(case, variant)
            validate_state(initial, aliases, nodes)
            keys(variant["transition_overrides"], (), step_ids)
            for step_id, expectation in variant["transition_overrides"].items():
                technique = catalog[
                    next(s for s in case["steps"] if s["step_id"] == step_id)["request"][
                        "technique_id"
                    ]
                ]
                validate_expectation(expectation, aliases, technique)
                validate_state(expectation["additions"], aliases, nodes)
            search = variant["expected_search"]
            keys(
                search,
                {
                    "outcome",
                    "required_reachable",
                    "forbidden",
                    "acceptable_paths",
                    "required_diagnostics",
                },
            )
            if search["outcome"] not in {"success", "no_path", "indeterminate"}:
                raise ValueError("ambiguous outcome; truncation is an actual incomplete result")
            for pattern in array(search["required_reachable"]) + [search["forbidden"]]:
                validate_state(pattern, aliases, nodes)
            paths = array(search["acceptable_paths"])
            if (search["outcome"] == "success") != bool(paths):
                raise ValueError(
                    "success requires acceptable paths; negative outcomes forbid paths"
                )
            for path in paths:
                if set(array(path)) - step_ids or len(path) != len(set(path)):
                    raise ValueError("invalid causal path reference")
                if not path and not contains(state_from(initial, aliases), goal_state):
                    raise ValueError("zero-action oracle requires initial security goal")
            for diagnostic in array(search["required_diagnostics"]):
                keys(diagnostic, {"step_id", "status", "predicates"})
                if (
                    diagnostic["step_id"] not in step_ids
                    or diagnostic["status"] not in {"blocked", "indeterminate"}
                    or not array(diagnostic["predicates"])
                ):
                    raise ValueError("invalid search diagnostic")
                owner = catalog[
                    next(s for s in case["steps"] if s["step_id"] == diagnostic["step_id"])[
                        "request"
                    ]["technique_id"]
                ]
                if set(diagnostic["predicates"]) - {
                    *owner.prerequisites,
                    "relationship_missing",
                    "relationship_exists",
                }:
                    raise ValueError("unknown diagnostic predicate reference")
            if search["outcome"] == "indeterminate" and not any(
                d["status"] == "indeterminate" for d in search["required_diagnostics"]
            ):
                raise ValueError("indeterminate outcome requires unknown transition witness")


def validate_expectation(expected, aliases, technique):
    keys(expected, {"status", "additions", "failed", "unknown"})
    state = state_from(expected["additions"], aliases)
    for field in ("failed", "unknown"):
        if any(
            not isinstance(p, str)
            or p not in {*technique.prerequisites, "relationship_missing", "relationship_exists"}
            for p in array(expected[field])
        ):
            raise ValueError("invalid predicate reference")
    status = expected["status"]
    inferred = (
        "blocked"
        if expected["failed"]
        else "indeterminate"
        if expected["unknown"]
        else "applicable"
    )
    if status != inferred or (status != "applicable" and any(vars(state).values())):
        raise ValueError("ambiguous status or non-applicable effects")


def run_case(suite, case, variant, base=DEFAULT.parent):
    binding = suite["graphs"][case["graph"]]
    aliases = binding["aliases"]
    canonical = json.loads((base / binding["path"]).read_text(encoding="utf-8"))
    graph = EngineGraph.from_canonical(canonical)
    initial, facts = materialize(case, variant)
    context = RuntimeContext(
        [
            RuntimeFact(
                **{k: v for k, v in f.items() if k != "evidence_ref"},
                provenance_reference=f["evidence_ref"],
            )
            for f in (
                {**fact, "subject": aliases[fact["subject"]], "target": aliases[fact["target"]]}
                for fact in facts
            )
        ],
        authentication_context=aliases.get(case["authentication_context"]),
    )
    catalog = tuple(t for t in load_catalog() if t.id in case["oracle_scope"]["techniques"])
    requests = {}
    replay = []
    for step in case["steps"]:
        req = step["request"]
        request = TransitionRequest(
            req["technique_id"], *(aliases[req[f]] for f in ("actor", "source", "target"))
        )
        requests[request] = step["step_id"]
        # Independently declared before state: replay correctness is separate from discovery.
        before = state_from(step["before"], aliases)
        if "initial_state" in variant:
            baseline = state_from(case["initial_state"], aliases)
            replacement = state_from(initial, aliases)
            before = AttackState(
                **{
                    f: (getattr(before, f) - getattr(baseline, f)) | getattr(replacement, f)
                    for f in FIELDS
                }
            )
        actual = evaluate(canonical, before, request, context, catalog)
        expected = variant["transition_overrides"].get(step["step_id"], step["expected"])
        # A delta can make other downstream requests unknown too. Explicit overrides
        # select the normative request-level witnesses for that counterfactual.
        if (
            variant["transition_overrides"]
            and step["step_id"] not in variant["transition_overrides"]
        ):
            continue
        assert actual.status.value == expected["status"], (
            case["scenario_id"],
            variant["variant_id"],
            step["step_id"],
            actual,
        )
        assert actual.additions == state_from(expected["additions"], aliases), (
            case["scenario_id"],
            step["step_id"],
            state_json(actual.additions, aliases),
            expected["additions"],
        )
        assert set(actual.failed) == set(expected["failed"])
        assert set(actual.unknown) == set(expected["unknown"])
        if actual.status.value != "applicable":
            assert apply_transition(before, actual) == before
        replay.append({"step": step["step_id"], "status": actual.status.value})
    state = state_from(initial, aliases)
    goal = state_from(case["target_goal"]["required_state"], aliases)
    result = generate_attack_paths(
        graph,
        aliases[case["initial_actor"]],
        initial_state=state,
        runtime_context=context,
        target_predicate=lambda n: n["id"] == aliases[case["target_goal"]["target"]],
        success_state_predicate=lambda s: contains(s, goal),
        budget=SearchBudget(**case["oracle_scope"]["budget"]),
        scenario_reference=case["scenario_id"],
        catalog=catalog,
    )
    assert digest(graph.to_canonical()) == binding["digest"] == digest(canonical)
    expected = variant["expected_search"]
    if result.truncated:
        raise AssertionError(
            f"incomplete/truncated: {case['scenario_id']} {result.truncation_reason}"
        )
    assert bool(result.paths) == (expected["outcome"] == "success")
    states = [state]
    states.extend(
        apply_transition(a.before, a) for a in result.attempts if a.status.value == "applicable"
    )
    for a in result.attempts:
        if a.status.value != "applicable":
            assert a.additions == AttackState()
            assert apply_transition(a.before, a) == a.before
    for pattern in expected["required_reachable"]:
        assert any(contains(s, state_from(pattern, aliases)) for s in states), pattern
    prohibited = state_from(expected["forbidden"], aliases)
    assert not any(forbidden(s, prohibited) for s in states)
    for d in expected["required_diagnostics"]:
        assert any(
            requests.get(a.request) == d["step_id"]
            and a.status.value == d["status"]
            and set(d["predicates"]) <= set(a.failed if d["status"] == "blocked" else a.unknown)
            for a in result.attempts
        ), d
    actual_paths = []
    for path in result.paths:
        assert contains(path.final_state, goal)
        ids = [requests.get(s.result.request) for s in path.transition_history]
        assert None not in ids, "unbound generated step outside oracle scope"
        for index, transition in enumerate(path.transition_history):
            spec = next(s for s in case["steps"] if s["step_id"] == ids[index])
            assert transition.edge_id == spec["edge_id"]
            parent = transition.derived_from_step
            assert (ids[parent] if parent is not None else None) == spec["derived_from"]
        actual_paths.append(ids)
    acceptable = expected["acceptable_paths"]
    if case["oracle_scope"]["path_policy"] == "exact_set":
        assert {tuple(p) for p in actual_paths} == {tuple(p) for p in acceptable}, actual_paths
    else:
        for causal in acceptable:
            assert any(is_subsequence(causal, p) for p in actual_paths), causal
        assert all(any(is_subsequence(causal, p) for causal in acceptable) for p in actual_paths)
    return {
        "scenario_id": case["scenario_id"],
        "variant_id": variant["variant_id"],
        "graph_digest": binding["digest"],
        "outcome": expected["outcome"],
        "complete": result.complete,
        "expansions": result.expansions,
        "paths": actual_paths,
        "transition_checks": replay,
        "reachable_states": sorted(
            {json.dumps(state_json(s, aliases), sort_keys=True) for s in states}
        ),
        "attempt_statuses": {
            status: sum(a.status.value == status for a in result.attempts)
            for status in ("applicable", "blocked", "indeterminate")
        },
    }


def is_subsequence(needle, haystack):
    iterator = iter(haystack)
    return all(any(item == wanted for item in iterator) for wanted in needle)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    suite = load_suite(args.suite)
    rows = [
        run_case(suite, c, v, args.suite.parent) for c in suite["scenarios"] for v in c["variants"]
    ]
    report = {
        "schema_version": suite["schema_version"],
        "suite_digest": digest(suite),
        "results": rows,
    }
    report["report_digest"] = digest(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {"status": "passed", "cases": len(rows), "report_digest": report["report_digest"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
