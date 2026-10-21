"""Real #243 inputs from the frozen specification and manifest-verified raw data.

This is a provider/resolver probe, not future #250 CLI integration acceptance.
Private identities remain local and are never committed as fixtures.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from src.engine.query import run_attack_query
from src.parser import IdentityNormalizer, ManifestRawDataLoader
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.cli import load_time_policy

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def frozen_program(raw_dir=None):
    raw_dir = Path(raw_dir or os.environ.get("SEAMLESS_RAW_DIR", ROOT / "data/raw/SEAMLESS"))
    spec = json.loads((ROOT / "docs/research/scenarios/week4-seamless-v1.json").read_text())
    graph, base, _, _ = seamless_inputs(raw_dir, spec["revision"])
    loader = ManifestRawDataLoader(
        ROOT / "data/samples/manifests/seamless-raw-v1.json",
        time_policy=load_time_policy(ROOT / "tests/fixtures/ranking/seamless_time_policy.json"),
    )
    records = IdentityNormalizer().normalize_records(
        adapt_bloodhound_v3_records(loader.load(raw_dir))
    )
    xs = {
        r.id
        for r in records
        if r.kind == "Computer"
        for source in r.raw_representations or (r.raw,)
        if source.provenance.get("record_locator") == spec["locators"]["X"]
    }
    assert len(xs) == 1
    ids = {"X": xs.pop(), "V_A": base["initial_state"]["known_identity"][0], "C0": base["target"]}
    query = {
        **base,
        "initial_actor": ids["X"],
        "source_foothold": ids["X"],
        "authentication_context": ids["X"],
        "allowed_techniques": spec["allowed_techniques"],
        "budget": spec["budget"],
        "evaluation_mode": spec["evaluation_mode"],
        "scenario_reference": spec["scenario_id"],
        "initial_state": {
            "control": [],
            "known_identity": [ids["V_A"]],
            "asrep_request_capability": [[ids["X"], ids["X"]]],
        },
        "assumptions": [],
    }
    for predicate, subject, target in spec["assumptions"]:
        metadata = {"declared_by": spec["declared_by"], "authentication_context": ids["X"]}
        if predicate == "recovery_success":
            metadata.update(spec["recovery_metadata"])
        query["assumptions"].append(
            {
                "predicate": predicate,
                "subject": ids[subject],
                "target": ids[target],
                "value": True,
                "scope": spec["scenario_id"],
                "rationale": "Explicit conditional prediction outcome",
                "provenance_reference": "scenario://week4-seamless-v1/explicit-outcomes",
                "assumption_metadata": metadata,
            }
        )
    result = run_attack_query(query, graph)
    assert result.final_goal_reached and not result.checkpoint_reached
    paths = result.search_result.paths
    assert len(paths) == 1
    assert [s.result.request.technique_id for s in paths[0].transition_history] == spec["expected"][
        "assumed"
    ]["programs"][0]
    # Explicit state predicates bind the four frozen active operations.
    # Preconditions come from declared initial state, pinned snapshot and runtime
    # assumptions. No runtime declaration is promoted to an observed fact.
    requires = (
        ("known", "request_capability", "preauth_off", "request_ok"),
        ("material", "recovery_ok"),
        ("secret", "activation_ok"),
        ("usable", "admin_channel", "admin_authentication"),
    )
    effects = ("material", "secret", "usable", "admin")
    initial = {
        "known": True,
        "request_capability": True,
        "request_ok": True,
        "recovery_ok": True,
        "activation_ok": True,
        "admin_channel": True,
        "admin_authentication": True,
    }
    facts = {
        "predicate_layers": {p: 3 for p in (*initial, *effects)},
        "assumed_facts": [
            {
                "predicate": p,
                "layer": 3,
                "truth_value": v,
                "provenance_reference": "scenario://week4-seamless-v1/explicit-outcomes",
                "rationale": "Frozen initial state or explicit runtime declaration",
            }
            for p, v in initial.items()
        ],
        "observed_facts": [
            {
                "predicate": "preauth_off",
                "layer": 1,
                "truth_value": True,
                "provenance_reference": "data/samples/manifests/seamless-raw-v1.json#/users/1700",
            }
        ],
    }
    facts["predicate_layers"]["preauth_off"] = 1
    assert graph.snapshot_facts.lookup(ids["V_A"], "dontreqpreauth").value is True
    scope = {
        "query_id": "provider-probe-frozen-243",
        "scenario_id": spec["scenario_id"],
        "scenario_version": "1.0.0",
        "snapshot_id": spec["snapshot_id"],
        "foothold_node_id": ids["X"],
        "work_boundary": "intra_forest",
        "evaluation_mode": "scenario",
        "horizon": spec["recovery_metadata"]["horizon"],
        "active_work_budget": 0,
        "facts_ledger": facts,
        "recovery_metadata": spec["recovery_metadata"],
        "target_goal": {
            "goal_id": "admin_control(C0)",
            "target_asset_id": ids["C0"],
            "success_event": "admin_execution_on_C",
            "required_predicates": ["admin"],
        },
    }
    bindings = {}
    for step, req, effect in zip(paths[0].transition_history, requires, effects, strict=True):
        r = step.result.request
        bindings[(r.technique_id, r.actor, r.source, r.target)] = {
            "requires": list(req),
            "adds": [effect],
            "auth_context": ids["X"],
            "method": spec["recovery_metadata"]["method"]
            if r.technique_id == "recover_asrep_secret"
            else "default",
        }
    return paths, scope, bindings
