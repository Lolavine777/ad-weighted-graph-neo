"""Process-local semantic replay evidence; candidate JSON cannot assert this binding."""

import json
from dataclasses import asdict, dataclass

from src.engine.ranking.models import RankingValidationError
from src.engine.semantics.credentials import replay_path

_REPLAY_AUTHORITY = object()


def _binding_payload(candidate, query_metadata):
    return json.dumps(
        [
            query_metadata,
            {
                key: candidate.get(key)
                for key in (
                    "candidate_id",
                    "scope_binding",
                    "target_asset_id",
                    "bound_action_ids",
                    "transition_lineage",
                    "structural_routes",
                    "state_goal_binding",
                )
            },
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, init=False)
class SemanticReplayBinding:
    """Immutable process-local proof, minted only after typed semantic replay.

    Serialized envelopes (including copied snapshot digests) cannot mint this proof.
    """

    _payload: str
    _initial_actor_audit: str
    _state_goal_prefixes: tuple[bool, ...]

    def __init__(self, payload, initial_actor_audit, *, state_goal_prefixes=(), _authority=None):
        if _authority is not _REPLAY_AUTHORITY:
            raise TypeError("semantic bindings must be minted by verify_search_envelope")
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_initial_actor_audit", initial_actor_audit)
        object.__setattr__(self, "_state_goal_prefixes", tuple(state_goal_prefixes))

    @property
    def initial_actor_audit(self):
        return json.loads(self._initial_actor_audit)

    def matches(self, candidate, query_metadata):
        return self._payload == _binding_payload(candidate, query_metadata)

    def state_goal_matches_prefix(self, action_count):
        return (
            0 <= action_count < len(self._state_goal_prefixes)
            and self._state_goal_prefixes[action_count]
        )


def verify_search_envelope(path, graph, envelope, query_metadata, *, catalog=None, prepared=None):
    """Recompute typed transitions before admitting snapshot roots or initial actors."""
    graph_metadata = (
        graph.metadata
        if hasattr(graph, "metadata") and isinstance(graph.metadata, dict)
        else (
            graph.to_canonical()["metadata"]
            if hasattr(graph, "to_canonical")
            else graph.get("metadata", {})
        )
    )
    if graph_metadata.get("snapshot_id") != query_metadata["snapshot_id"]:
        raise RankingValidationError("semantic replay snapshot does not match ranking query")
    try:
        replay_path(path, graph, catalog=catalog, prepared=prepared)
    except TypeError as err:
        if "unexpected keyword argument 'prepared'" in str(
            err
        ) or "got an unexpected keyword argument" in str(err):
            replay_path(path, graph, catalog=catalog)
        else:
            raise
    state_goal_prefixes = ()
    state_goal_binding = envelope.get("state_goal_binding")
    if state_goal_binding is not None:
        from src.engine.query import (
            IdentityResolver,
            UsableIdentityEntitlementGoal,
            semantic_goal_from_dict,
        )
        from src.engine.ranking.adapter_145 import _audit_value
        from src.engine.ranking.resolution_service import canonical_digest

        goal = query_metadata.get("semantic_goal")
        target = envelope["target_asset_id"]
        if (
            not isinstance(goal, dict)
            or goal.get("target_asset_id") != target
            or (path.goal_target if path.goal_target is not None else path.nodes[-1]) != target
            or path.final_state is None
        ):
            raise RankingValidationError("State-goal replay requires the exact declared target")
        try:
            descriptor = semantic_goal_from_dict(
                goal, IdentityResolver({node["id"]: node for node in graph.nodes()})
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RankingValidationError("Malformed typed state-goal descriptor") from exc
        if (
            isinstance(descriptor, UsableIdentityEntitlementGoal)
            and descriptor.authentication_context != path.runtime_context.authentication_context
        ):
            raise RankingValidationError(
                "Identity-entitlement replay authentication context mismatch"
            )
        expected = {
            "target_asset_id": target,
            "semantic_goal_digest": canonical_digest(goal),
            "final_state_digest": canonical_digest(_audit_value(path.final_state)),
        }
        if not descriptor.matches(path.final_state) or state_goal_binding != expected:
            raise RankingValidationError("State-goal replay does not verify the final capability")
        # First-hit ranking may retain less than the full verified program.
        state_goal_prefixes = tuple(
            descriptor.matches(state)
            for state in (
                *(step.result.before for step in path.transition_history),
                path.final_state,
            )
        )
    history = path.transition_history
    lineage = envelope.get("transition_lineage", [])
    if len(lineage) != len(history):
        raise RankingValidationError("semantic replay lineage length mismatch")
    for record, step in zip(lineage, history, strict=True):
        request = step.result.request
        if any(
            record.get(key) != getattr(request, key)
            for key in ("technique_id", "actor", "source", "target")
        ) or record.get("snapshot_evidence", []) != list(step.result.snapshot_evidence):
            raise RankingValidationError("semantic replay envelope lineage mismatch")
        expected_rbcd = (
            asdict(request.rbcd_binding)
            if getattr(request, "rbcd_binding", None) is not None
            else None
        )
        if record.get("rbcd_binding") != expected_rbcd:
            raise RankingValidationError("semantic replay envelope rbcd_binding mismatch")
    bound_rbcd = query_metadata.get("bound_rbcd_binding")
    if bound_rbcd is not None:
        for step in history:
            req_rbcd = getattr(step.result.request, "rbcd_binding", None)
            if req_rbcd is not None and asdict(req_rbcd) != bound_rbcd:
                raise RankingValidationError(
                    "query bound_rbcd_binding does not match path request binding"
                )
    first = history[0].result
    foothold = query_metadata["foothold_node_id"]
    scope = path.runtime_context.authentication_context
    initial_actors = {foothold} | {
        user for user, context in first.before.usable_identity if context == scope
    }
    # A pre-existing password authorizes its owner to execute scoped activation.
    if first.request.technique_id == "activate_recovered_identity":
        initial_actors.update(
            artifact.owner
            for artifact in first.before.recovered_secret
            if artifact.context == scope and artifact.form == "password"
        )
    if first.request.actor not in initial_actors:
        raise RankingValidationError("first actor lacks a declared scoped initial capability")
    return SemanticReplayBinding(
        _binding_payload(envelope, query_metadata),
        json.dumps(
            {
                "foothold_node_id": foothold,
                "first_actor": first.request.actor,
                "authentication_context": scope,
                "declared_initial_actors": sorted(initial_actors),
                "origin": "declared_initial_state",
            },
            sort_keys=True,
        ),
        state_goal_prefixes=state_goal_prefixes,
        _authority=_REPLAY_AUTHORITY,
    )
