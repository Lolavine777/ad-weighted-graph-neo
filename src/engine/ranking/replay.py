"""Normative candidate action replay, goal first-hitting time, and route synchronization.

Implements normative replay semantics according to Specification v1.0.0 and ADR-0013:
- Replay actions sequentially: prerequisites evaluated BEFORE effects.
- Layer 1 and Layer 2 immutability: action effects ('adds') only update Layer 3 predicates.
- Hard veto and initial unknown gate status preserved across replay.
- First hitting time: execution stops at the first step satisfying target goal predicates.
- Zero-step goal satisfaction: cuts to empty action sequence, target must be foothold.
- Verified 1-to-1 mapping required for structural route synchronization upon suffix trimming.
- Target asset reachability tied to effective executed actions in the prefix.
"""

from __future__ import annotations

from typing import Any

from src.engine.ranking.models import (
    MappingSyncError,
    RankingValidationError,
)
from src.engine.ranking.validation import validate_candidate_envelope


def replay_candidate_sequence(
    decoded_query: dict[str, Any],
    candidate_envelope: dict[str, Any],
    *,
    semantic_binding=None,
) -> dict[str, Any]:
    """Replay candidate action program against resolved facts and goal constraints."""
    candidate_envelope = validate_candidate_envelope(
        candidate_envelope, decoded_query, semantic_binding=semantic_binding
    )
    candidate_id = candidate_envelope["candidate_id"]
    target_asset_id = candidate_envelope["target_asset_id"]
    structural_routes = list(candidate_envelope["structural_routes"])
    bound_action_ids = list(candidate_envelope["bound_action_ids"])

    actions_catalog = {act["action_id"]: act for act in decoded_query["bound_actions"]}
    cand_actions = [actions_catalog[aid] for aid in bound_action_ids]
    initial_cand_actions = list(cand_actions)
    # Validate this adapter locator even when first-goal replay does not trim.
    for route in structural_routes:
        if "action_step_indices" not in route:
            continue
        indices = route["action_step_indices"]
        edge_ids = route.get("edge_ids", [])
        if (
            not isinstance(indices, list)
            or len(indices) != len(edge_ids)
            or any(type(index) is not int for index in indices)
            or indices != sorted(set(indices))
            or any(index < 0 or index >= len(initial_cand_actions) for index in indices)
        ):
            raise MappingSyncError(
                f"Candidate {candidate_id} has invalid action_step_indices for route "
                f"{route.get('route_id')!r}"
            )
    foothold_id = decoded_query["query_metadata"]["foothold_node_id"]

    impact_rec = decoded_query["target_impact_assessments"][target_asset_id]
    impact = impact_rec.get("consequence_rating")
    impact_status = impact_rec.get("rating_status", "unrated")

    # 3. Sequential evaluation, Layer 1/2 immutability & first hitting time replay
    resolved_facts = decoded_query["resolved_facts"]
    current_facts: dict[str, str] = {p: v["value"] for p, v in resolved_facts.items()}
    predicate_layers: dict[str, int] = decoded_query.get("predicate_layers") or dict(
        decoded_query["facts_ledger"].get("predicate_layers", {})
    )
    for p, v in resolved_facts.items():
        if "layer" in v:
            predicate_layers[p] = v["layer"]
    gates_eval: dict[str, Any] = {}
    target_goal = decoded_query["query_metadata"].get("target_goal", {})
    goal_required = target_goal.get("required_predicates", [])
    cand_required = candidate_envelope.get("required_predicates", [])
    for req in cand_required:
        if req not in predicate_layers:
            raise RankingValidationError(
                f"Missing authoritative layer classification for predicate {req!r} in "
                f"candidate {candidate_id!r} required_predicates: authoritative layer must be "
                f"explicitly declared in predicate_layers or facts_ledger"
            )

    all_predicates_to_check = set(cand_required)
    for act in cand_actions:
        for req in act.get("requires", []):
            all_predicates_to_check.add(req)
    for gp in goal_required:
        all_predicates_to_check.add(gp)

    for p in sorted(all_predicates_to_check):
        gates_eval[p] = current_facts.get(p, "Unknown")

    def is_goal_satisfied(facts: dict[str, str]) -> tuple[bool, str]:
        st = "feasible"
        for p_goal in goal_required:
            v_goal = facts.get(p_goal, "Unknown")
            if v_goal == "False":
                return False, "blocked"
            elif v_goal == "Unknown":
                st = "unknown"
        return (st == "feasible"), st

    # Evaluate candidate's initial required predicates
    initial_gate_status = "feasible"
    for req in cand_required:
        val = current_facts.get(req, "Unknown")
        gates_eval[req] = val
        if val == "False":
            initial_gate_status = "blocked"
        elif val == "Unknown" and initial_gate_status != "blocked":
            initial_gate_status = "unknown"

    gate_status = initial_gate_status

    # Sequential action evaluation up to first hitting time
    init_sat, _init_status = is_goal_satisfied(current_facts)
    if init_sat:
        trimmed_actions: list[dict[str, Any]] | None = []
        goal_reached = True
    else:
        trimmed_actions = None
        goal_reached = False

        if gate_status != "blocked":
            for k, act in enumerate(cand_actions):
                act_blocked = False
                act_unknown = False
                for req in act.get("requires", []):
                    val = current_facts.get(req, "Unknown")
                    gates_eval[req] = val
                    if val == "False":
                        act_blocked = True
                    elif val == "Unknown":
                        act_unknown = True

                if act_blocked:
                    gate_status = "blocked"
                    break
                if act_unknown:
                    if gate_status != "blocked":
                        gate_status = "unknown"
                    break

                # Action succeeded: update current state with additions
                # CRITICAL: Only Layer 3 runtime-derived predicates can be mutated.
                # Layer 1 and Layer 2 are immutable evidence from snapshot/telemetry.
                for add_p in act.get("adds", []):
                    p_layer = resolved_facts.get(add_p, {}).get("layer")
                    if p_layer is None:
                        p_layer = predicate_layers.get(add_p)
                    if p_layer != 3:
                        continue
                    current_facts[add_p] = "True"
                    gates_eval[add_p] = "True"

                step_sat, _step_status = is_goal_satisfied(current_facts)
                if step_sat:
                    trimmed_actions = cand_actions[: k + 1]
                    goal_reached = True
                    break

        if not goal_reached:
            for gp in goal_required:
                val = current_facts.get(gp, "Unknown")
                gates_eval[gp] = val
                # Unreached derived effects are absent, not a veto on an unresolved action.
                if val == "False" and (gate_status != "unknown" or predicate_layers.get(gp) != 3):
                    gate_status = "blocked"
                elif val == "Unknown" and gate_status != "blocked":
                    gate_status = "unknown"

    # Synchronize trimmed actions, work packets, and route traces
    if goal_reached and trimmed_actions is not None:
        cand_actions = trimmed_actions
        bound_action_ids = [act["action_id"] for act in trimmed_actions]
        if candidate_envelope.get("state_goal_binding") is not None and not (
            semantic_binding.state_goal_matches_prefix(len(trimmed_actions))
        ):
            raise RankingValidationError(
                f"Candidate {candidate_id} executed prefix does not satisfy the typed semantic goal"
            )

        # Only synchronize/trim routes if a suffix of actions was actually trimmed
        if len(trimmed_actions) < len(initial_cand_actions):
            trimmed_routes = []
            for r in structural_routes:
                edge_ids = r.get("edge_ids", [])
                node_ids = r.get("node_ids", [])
                locators = r.get("provenance_locators", [])
                trimmed_r = dict(r)
                action_step_indices = r.get("action_step_indices")

                # Validate verified 1-to-1 mapping before trimming
                if action_step_indices is None:
                    for act_idx, act in enumerate(initial_cand_actions):
                        if not act.get("edge_id"):
                            raise MappingSyncError(
                                f"Candidate {candidate_id} cannot safely synchronize "
                                "structural_routes "
                                f"upon suffix trimming: missing edge_id mapping on bound action "
                                f"{act.get('action_id')!r} at step {act_idx}"
                            )

                if not edge_ids and action_step_indices is None:
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route {r.get('route_id')!r} missing edge_ids"
                    )
                if not node_ids:
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route {r.get('route_id')!r} missing node_ids"
                    )
                if not locators and action_step_indices is None:
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route {r.get('route_id')!r} missing "
                        f"provenance_locators"
                    )

                if action_step_indices is None and len(edge_ids) != len(initial_cand_actions):
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route edge count ({len(edge_ids)}) does not "
                        f"match declared action count ({len(initial_cand_actions)})"
                    )
                if action_step_indices is None and len(node_ids) != len(initial_cand_actions) + 1:
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route node count ({len(node_ids)}) must be "
                        f"{len(initial_cand_actions) + 1}"
                    )
                if action_step_indices is None and len(locators) != len(initial_cand_actions):
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route provenance_locators count ({len(locators)}) "
                        f"must be {len(initial_cand_actions)}"
                    )

                prov_lineage = r.get("provenance_lineage")
                expected_trace_count = (
                    len(edge_ids) if action_step_indices is not None else len(initial_cand_actions)
                )
                if prov_lineage is not None and len(prov_lineage) != expected_trace_count:
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route provenance_lineage count "
                        f"({len(prov_lineage)}) must be {expected_trace_count}"
                    )

                edge_prov_records = r.get("edge_provenance_records")
                semantic_lineage = r.get("semantic_lineage")
                if action_step_indices is not None:
                    if (
                        not isinstance(action_step_indices, list)
                        or len(action_step_indices) != len(edge_ids)
                        or any(type(step_idx) is not int for step_idx in action_step_indices)
                        or action_step_indices != sorted(set(action_step_indices))
                        or any(
                            step_idx < 0 or step_idx >= len(initial_cand_actions)
                            for step_idx in action_step_indices
                        )
                    ):
                        raise MappingSyncError(
                            f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                            f"upon suffix trimming: invalid action_step_indices for route "
                            f"{r.get('route_id')!r}"
                        )
                    if edge_prov_records is not None and len(edge_prov_records) != len(edge_ids):
                        raise MappingSyncError(
                            f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                            f"upon suffix trimming: route edge_provenance_records count "
                            f"({len(edge_prov_records)}) must match structural edge count "
                            f"({len(edge_ids)})"
                        )
                    for edge_idx, action_idx in enumerate(action_step_indices):
                        expected_eid = initial_cand_actions[action_idx].get("edge_id")
                        if expected_eid is not None and edge_ids[edge_idx] != expected_eid:
                            raise MappingSyncError(
                                f"Candidate {candidate_id} cannot safely synchronize "
                                "structural_routes "
                                f"upon suffix trimming: route edge {edge_ids[edge_idx]!r} does not "
                                "match bound action "
                                f"{initial_cand_actions[action_idx]['action_id']!r} "
                                f"edge_id {expected_eid!r}"
                            )
                    retained = [
                        idx
                        for idx, action_idx in enumerate(action_step_indices)
                        if action_idx < len(trimmed_actions)
                    ]
                    if edge_ids and not retained:
                        # This observed segment belongs entirely to a trimmed suffix.
                        # Drop the segment rather than emitting an empty orphan route.
                        continue
                    edge_count = len(retained)
                    trimmed_r["edge_ids"] = [edge_ids[idx] for idx in retained]
                    trimmed_r["node_ids"] = node_ids[: edge_count + 1]
                    trimmed_r["provenance_locators"] = [locators[idx] for idx in retained]
                    trimmed_r["action_step_indices"] = [
                        action_step_indices[idx] for idx in retained
                    ]
                    if prov_lineage is not None:
                        trimmed_r["provenance_lineage"] = [prov_lineage[idx] for idx in retained]
                    if edge_prov_records is not None:
                        trimmed_r["edge_provenance_records"] = [
                            edge_prov_records[idx] for idx in retained
                        ]
                    if semantic_lineage is not None:
                        trimmed_r["semantic_lineage"] = [
                            record
                            for record in semantic_lineage
                            if record["step_index"] < len(trimmed_actions)
                        ]
                    trimmed_routes.append(trimmed_r)
                    continue
                if edge_prov_records is not None and len(edge_prov_records) != len(
                    initial_cand_actions
                ):
                    raise MappingSyncError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route edge_provenance_records count "
                        f"({len(edge_prov_records)}) must be {len(initial_cand_actions)}"
                    )

                for act_idx, act in enumerate(initial_cand_actions):
                    expected_eid = act["edge_id"]
                    if edge_ids[act_idx] != expected_eid:
                        raise MappingSyncError(
                            f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                            f"upon suffix trimming: route edge {edge_ids[act_idx]!r} at position "
                            f"{act_idx} does not match bound action {act['action_id']!r} "
                            f"edge_id {expected_eid!r}"
                        )

                if len(trimmed_actions) == 0:
                    trimmed_r["edge_ids"] = []
                    trimmed_r["provenance_locators"] = []
                    trimmed_r["node_ids"] = [node_ids[0]]
                    if prov_lineage is not None:
                        trimmed_r["provenance_lineage"] = []
                    if edge_prov_records is not None:
                        trimmed_r["edge_provenance_records"] = []
                else:
                    n_trim = len(trimmed_actions)
                    trimmed_r["edge_ids"] = edge_ids[:n_trim]
                    trimmed_r["node_ids"] = node_ids[: n_trim + 1]
                    trimmed_r["provenance_locators"] = locators[:n_trim]
                    if prov_lineage is not None:
                        trimmed_r["provenance_lineage"] = prov_lineage[:n_trim]
                    if edge_prov_records is not None:
                        trimmed_r["edge_provenance_records"] = edge_prov_records[:n_trim]

                if semantic_lineage is not None:
                    trimmed_r["semantic_lineage"] = [
                        record
                        for record in semantic_lineage
                        if record["step_index"] < len(trimmed_actions)
                    ]
                trimmed_routes.append(trimmed_r)
            structural_routes = trimmed_routes

    # Verify target asset reachability on effective executed actions
    effective_targets = {act["target_id"] for act in cand_actions}
    if cand_actions:
        if (
            target_asset_id not in effective_targets
            and candidate_envelope.get("state_goal_binding") is None
        ):
            raise RankingValidationError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by effective actions in executed prefix"
            )
    else:
        if target_asset_id != foothold_id:
            raise RankingValidationError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by initial foothold"
            )

    # Derive work packets for effective actions
    canonical_packets: list[tuple[str, ...]] = []
    for act in cand_actions:
        units = act.get("referenced_work_unit_ids", [])
        if units:
            canonical_packets.append(tuple(units))
        elif act.get("is_passive_closure"):
            canonical_packets.append(())
    if not canonical_packets:
        canonical_packets = [()]

    return {
        "candidate_id": candidate_id,
        "bound_action_ids": bound_action_ids,
        "target_asset_id": target_asset_id,
        "cand_actions": cand_actions,
        "work_packets": canonical_packets,
        "structural_routes": structural_routes,
        "gate_status": gate_status,
        "gates_evaluation": gates_eval,
        "impact": impact,
        "impact_status": impact_status,
    }
