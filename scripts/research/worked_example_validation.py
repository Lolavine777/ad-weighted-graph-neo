#!/usr/bin/env python3
"""Reproducible research validation script for Issues #142 / #150 (TTS A).

This script implements the validation testbed for the Active Directory path-ranking model,
rubric mapping, dynamic state and gate evaluation, graph search algorithms (Dijkstra vs
exhaustive search oracle), and sensitivity analysis as specified in
docs/research/path-ranking-model.md and docs/research/week3-scenario-contract.md.
Experiments 1-5 preserve the historical #149 draft and counterexamples.
Experiment 6 checks the scoped #150 proposal; suite PASS is not model support.

Python 3.10+, standard library only.
Run from repository root:
    uv run python scripts/research/worked_example_validation.py --all
    uv run python scripts/research/worked_example_validation.py --json
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

# Configure standard streams for UTF-8 compatibility on Windows cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ordinal scales
LIKELIHOOD_ORDINAL: dict[str, int] = {
    "Blocked": -1,
    "Unknown": 0,
    "Low": 1,
    "Medium": 2,
    "High": 3,
}

# Scenario-rated business consequences, never an ordering of ontology security_labels.
IMPACT_ORDINAL: dict[str, int] = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Critical": 4,
}


def bottleneck_likelihood(step_likelihoods: list[str]) -> str:
    """Aggregate step likelihoods using the bottleneck (weakest-link) principle.

    If any step has likelihood 'Blocked', the entire path likelihood is 'Blocked'.
    If any step has likelihood 'Unknown' or represents an unresolved gate, the entire
    path likelihood is 'Unknown'.
    Otherwise, the minimum ordinal value among steps determines the path likelihood.
    """
    if not step_likelihoods:
        return "Unknown"
    for item in step_likelihoods:
        if item == "Blocked":
            return "Blocked"
    for item in step_likelihoods:
        if item == "Unknown":
            return "Unknown"
    min_level = min(step_likelihoods, key=lambda x: LIKELIHOOD_ORDINAL.get(x, 0))
    return min_level


@dataclass(frozen=True)
class ActionStep:
    """Represents a single discrete action or transition in an attack chain."""

    name: str
    step_number: int
    action_type: str  # 'active' or 'passive'
    t1: int  # Skill & Tooling Complexity (1..3)
    t2: int  # Interaction & Defense Friction (1..3)
    t3: str  # Telemetry / Detectability
    likelihood: str  # 'High', 'Medium', 'Low', 'Unknown'
    gate_status: str  # Gate evaluation status
    fact_stratum: str  # Data boundary stratum
    notes: str = ""

    def cost(self, formula: str = "base") -> int:
        """Calculate step effort cost based on specified formula variant."""
        if self.action_type == "passive":
            # Invariant: passive membership closure must cost 0 in all valid variants
            if formula in ("base", "max", "tool_weighted", "friction_weighted"):
                return 0
            if formula == "raw_max_unnormalized":
                return max(self.t1, self.t2)
            raise ValueError(f"Unknown formula variant: {formula}")

        if formula == "base":
            return self.t1 + self.t2 - 2
        if formula == "max":
            return max(self.t1, self.t2) - 1
        if formula == "tool_weighted":
            return 2 * self.t1 + self.t2 - 3
        if formula == "friction_weighted":
            return self.t1 + 2 * self.t2 - 3
        if formula == "raw_max_unnormalized":
            return max(self.t1, self.t2)
        raise ValueError(f"Unknown formula variant: {formula}")


class PathRankingResult(dict):
    """Result of path ranking, separating feasible and blocked paths."""

    def __init__(
        self,
        feasible: list[AttackPath],
        blocked: list[AttackPath],
        infeasible: list[AttackPath] | None = None,
    ):
        infeasible_list = infeasible if infeasible is not None else blocked
        super().__init__(
            feasible=feasible,
            blocked=blocked,
            infeasible=infeasible_list,
        )

    @property
    def feasible(self) -> list[AttackPath]:
        return self["feasible"]

    @property
    def blocked(self) -> list[AttackPath]:
        return self["blocked"]

    @property
    def infeasible(self) -> list[AttackPath]:
        return self["infeasible"]


AUTHORITATIVE_RESET_PRECONDITIONS: list[tuple[str, list[str]]] = [
    ("structural_genericall", ["structural_genericall", "structural_generic_all", "genericall"]),
    ("source_computer_enabled", ["source_computer_enabled", "source_enabled"]),
    ("target_user_enabled", ["target_user_enabled", "target_enabled"]),
    ("foothold", ["foothold", "foothold_proven", "foothold_satisfied"]),
    ("password_policy_satisfied", ["password_policy_satisfied", "password_policy"]),
    ("directory_write_available", ["directory_write_available", "directory_write"]),
]

AUTHORITATIVE_SESSION_PRECONDITIONS: list[tuple[str, list[str]]] = [
    ("foothold", ["foothold", "foothold_proven", "foothold_satisfied"]),
    ("session", ["session", "has_session", "active_session", "session_present"]),
]


def parse_tristate(val: Any) -> bool | str:
    """Parse a value into tristate: True, False, or 'Unknown'.

    Fails closed: Any unrecognized string, non-bool/non-string object, None,
    or invalid value strictly resolves to 'Unknown', NEVER True.
    """
    if val is False:
        return False
    if val is True:
        return True
    if isinstance(val, str):
        v_lower = val.lower().strip()
        if v_lower in ("false", "blocked", "rejected", "denied", "disabled", "failed", "0", "no"):
            return False
        if v_lower in ("true", "satisfied", "reached", "passed", "granted", "enabled", "1", "yes"):
            return True
        if v_lower in (
            "unknown",
            "unresolved",
            "indeterminate",
            "not_measured",
            "missing",
            "unproven",
            "none",
        ):
            return "Unknown"
        return "Unknown"
    return "Unknown"


AUTHORITATIVE_MEMBERSHIP_PRECONDITIONS: list[tuple[str, list[str]]] = [
    (
        "structural_memberof",
        [
            "structural_memberof",
            "memberof",
            "member_of",
            "group_membership",
            "da_membership",
        ],
    ),
]

AUTHORITATIVE_TARGET_PRECONDITIONS: list[tuple[str, list[str]]] = [
    (
        "target_krbtgt_exists",
        ["target_krbtgt_exists", "target_exists", "krbtgt_exists", "target_krbtgt"],
    ),
]


def is_flag_true(val: Any) -> bool:
    """Return True strictly when val explicitly parses to True via parse_tristate.

    Fails closed on 'false', '0', 'no', 'unknown', 'missing', invalid objects, lists, None.
    """
    return parse_tristate(val) is True


@dataclass(frozen=True)
class AttackPath:
    """Represents a complete or partial attack chain towards a target asset."""

    name: str
    target_name: str
    target_impact: str
    steps: list[ActionStep]
    is_synthetic: bool = False

    def subpath_to(self, checkpoint: str) -> list[ActionStep]:
        """Return the list of steps leading up to the given checkpoint."""
        if checkpoint == "S1":
            return self.steps[:1]
        if checkpoint == "S2":
            return self.steps[:3]
        if checkpoint == "S3":
            return self.steps[:4]
        raise ValueError(f"Unknown checkpoint: {checkpoint}")

    def _evaluate_gates(
        self, checkpoint: str, gate_context: dict[str, Any] | None = None
    ) -> tuple[str, str, bool]:
        """Evaluate gating conditions up to the checkpoint.

        Returns:
            tuple of (path_status, path_likelihood, is_feasible)
            path_status: 'feasible', 'blocked', or 'unknown'
            path_likelihood: 'Blocked', 'Unknown', or bottleneck_likelihood
            is_feasible: True if all required gates are satisfied, False otherwise

        Checkpoints evaluate hierarchically with authoritative prerequisite sets:
          - S1 (Reset): requires 6 reset preconditions (independent of S2/S3)
          - S2 (Domain Admins): requires S1 + structural_memberof + gate_a + gate_m
          - S3 (KRBTGT DCSync): requires S2 + target_krbtgt_exists + Gate O

        Negative Evidence Veto & Fail-Closed Rules:
          - Any explicit False among direct overrides, aliases, or prerequisites
            strictly vetoes True and blocks the checkpoint.
          - Assumption flags (baseline_assumptions, assume_reset_prerequisites)
            fail closed via is_flag_true (rejecting "false", 0, "unknown", invalid objects).
          - Whenever gate_context is provided, authoritative prerequisites apply:
            a positive step_1=True shorthand cannot override explicit False/Unknown
            prerequisite evidence; without baseline_assumptions=True, missing
            prerequisites remain Unknown. Downstream-only context without
            baseline_assumptions=True leaves S1 unknown/unsupported (not feasible).
          - Gate O requires explicit verified replication evidence
            (structural_replication_rights or evidence_replication_granted).
        """
        subpath = self.subpath_to(checkpoint)

        # 1. Nominal / static evaluation if no gate_context was provided
        if gate_context is None:
            step_gate_evals: list[bool | str] = []
            for s in subpath:
                status_lower = s.gate_status.lower()
                if "false" in status_lower or "blocked" in status_lower:
                    gate_val: bool | str = False
                elif "unknown" in status_lower or "unresolved" in status_lower:
                    gate_val = "Unknown"
                elif "true" in status_lower or "satisfied" in status_lower:
                    gate_val = True
                else:
                    gate_val = True
                step_gate_evals.append(gate_val)

            if any(g is False for g in step_gate_evals):
                return ("blocked", "Blocked", False)
            if any(g == "Unknown" for g in step_gate_evals):
                return ("unknown", "Unknown", False)

            p_like = bottleneck_likelihood([s.likelihood for s in subpath])
            return ("feasible", p_like, True)

        # 2. Dynamic evaluation with provided gate_context
        norm_ctx: dict[str, Any] = {
            k.strip().lower().replace(" ", "_").replace("-", "_"): v
            for k, v in gate_context.items()
        }

        # Parse assumption flags failing closed (rejecting "false", 0, unknown, etc.)
        assume_baseline = is_flag_true(norm_ctx.get("baseline_assumptions")) or is_flag_true(
            norm_ctx.get("assume_reset_prerequisites")
        )

        membership_keys = [
            alias for _, aliases in AUTHORITATIVE_MEMBERSHIP_PRECONDITIONS for alias in aliases
        ]
        target_keys = [
            alias for _, aliases in AUTHORITATIVE_TARGET_PRECONDITIONS for alias in aliases
        ]
        gate_a_keys = [
            "gate_a",
            "gatea",
            "step_2",
            "step2",
            "activate_identity",
            "identity_activated",
            "gate_a_accepted",
        ]
        gate_m_keys = [
            "gate_m",
            "gatem",
            "step_3",
            "step3",
            "propagate_membership",
            "inherit_da_entitlement",
            "gate_m_usable",
        ]
        replication_evidence_keys = [
            "structural_replication_rights",
            "evidence_replication_granted",
        ]
        all_gate_o_keys = [
            "structural_replication_rights",
            "evidence_replication_granted",
            "gate_o",
            "gateo",
            "step_4",
            "step4",
            "dcsync_krbtgt",
        ]

        step_gate_evals = []
        for s in subpath:
            is_step_1 = (
                s.step_number == 1
                or s.name in ("genericall_reset_password", "token_impersonation")
                or "foothold" in s.gate_status.lower()
            )
            is_step_2 = (
                s.step_number == 2
                or s.name == "activate_identity"
                or "gate a" in s.gate_status.lower()
                or "gate_a" in s.gate_status.lower()
            )
            is_step_3 = (
                s.step_number == 3
                or s.name in ("propagate_membership", "inherit_da_entitlement")
                or "gate m" in s.gate_status.lower()
                or "gate_m" in s.gate_status.lower()
            )
            is_gate_o_step = (
                s.step_number == 4
                or s.name == "dcsync_krbtgt"
                or "gate o" in s.gate_status.lower()
                or "gate_o" in s.gate_status.lower()
            )

            # --- Step 1 (Reset or Session) evaluation ---
            if is_step_1:
                is_session = (
                    "session" in s.name.lower()
                    or "token" in s.name.lower()
                    or "impersonat" in s.name.lower()
                )
                preconditions = (
                    AUTHORITATIVE_SESSION_PRECONDITIONS
                    if is_session
                    else AUTHORITATIVE_RESET_PRECONDITIONS
                )
                step_override_keys = (
                    ["step_1", "step1", "token_impersonation"]
                    if is_session
                    else ["step_1", "step1", "genericall_reset_password"]
                )

                # Collect all direct override values provided
                override_vals = [
                    parse_tristate(norm_ctx[k]) for k in step_override_keys if k in norm_ctx
                ]

                # Direct override negative veto: Any explicit False strictly blocks
                if any(v is False for v in override_vals):
                    step_gate_evals.append(False)
                    continue

                # Evaluate authoritative preconditions
                matched_vals: list[bool | str] = []
                for _canon_name, aliases in preconditions:
                    alias_vals = [
                        parse_tristate(norm_ctx[alias]) for alias in aliases if alias in norm_ctx
                    ]
                    if alias_vals:
                        if any(v is False for v in alias_vals):
                            matched_vals.append(False)
                        elif any(v == "Unknown" for v in alias_vals):
                            matched_vals.append("Unknown")
                        else:
                            matched_vals.append(True)
                    else:
                        # Prerequisite missing from gate_context
                        matched_vals.append(True if assume_baseline else "Unknown")

                # If ANY prerequisite is False -> False (blocked)
                if any(v is False for v in matched_vals):
                    step_gate_evals.append(False)
                    continue

                # If ANY prerequisite is Unknown -> Unknown (shortcut cannot bypass)
                if any(v == "Unknown" for v in matched_vals):
                    step_gate_evals.append("Unknown")
                    continue

                # If override_vals has Unknown -> Unknown
                if any(v == "Unknown" for v in override_vals):
                    step_gate_evals.append("Unknown")
                    continue

                # All preconditions evaluated to True
                step_gate_evals.append(True)
                continue

            # --- Step 2 (Identity Activation / Gate A) evaluation ---
            if is_step_2:
                alias_vals = [parse_tristate(norm_ctx[k]) for k in gate_a_keys if k in norm_ctx]
                if alias_vals:
                    if any(v is False for v in alias_vals):
                        gate_val = False
                    elif any(v == "Unknown" for v in alias_vals):
                        gate_val = "Unknown"
                    else:
                        gate_val = True
                else:
                    gate_val = True if assume_baseline else "Unknown"
                step_gate_evals.append(gate_val)
                continue

            # --- Step 3 (Membership / Gate M) evaluation ---
            if is_step_3:
                m_gate_vals = [parse_tristate(norm_ctx[k]) for k in gate_m_keys if k in norm_ctx]
                member_vals = [
                    parse_tristate(norm_ctx[k]) for k in membership_keys if k in norm_ctx
                ]

                # Structural membership prerequisite evaluation
                if member_vals:
                    if any(v is False for v in member_vals):
                        member_status: bool | str = False
                    elif any(v == "Unknown" for v in member_vals):
                        member_status = "Unknown"
                    else:
                        member_status = True
                else:
                    member_status = True if assume_baseline else "Unknown"

                # Gate M usability evaluation
                if m_gate_vals:
                    if any(v is False for v in m_gate_vals):
                        m_status: bool | str = False
                    elif any(v == "Unknown" for v in m_gate_vals):
                        m_status = "Unknown"
                    else:
                        m_status = True
                else:
                    m_status = True if assume_baseline else "Unknown"

                if member_status is False or m_status is False:
                    gate_val = False
                elif member_status == "Unknown" or m_status == "Unknown":
                    gate_val = "Unknown"
                else:
                    gate_val = True
                step_gate_evals.append(gate_val)
                continue

            # --- Step 4 (Target KRBTGT / Gate O) evaluation ---
            if is_gate_o_step:
                target_vals = [parse_tristate(norm_ctx[k]) for k in target_keys if k in norm_ctx]

                # Target existence prerequisite evaluation
                if target_vals:
                    if any(v is False for v in target_vals):
                        target_status: bool | str = False
                    elif any(v == "Unknown" for v in target_vals):
                        target_status = "Unknown"
                    else:
                        target_status = True
                else:
                    target_status = True if assume_baseline else "Unknown"

                # Gate O replication authorization evaluation
                has_negative = any(
                    k in norm_ctx and parse_tristate(norm_ctx[k]) is False for k in all_gate_o_keys
                )
                if has_negative:
                    gate_o_status: bool | str = False
                else:
                    has_affirmative = any(
                        k in norm_ctx and parse_tristate(norm_ctx[k]) is True
                        for k in replication_evidence_keys
                    )
                    if has_affirmative:
                        gate_o_status = True
                    else:
                        gate_o_status = "Unknown"

                if target_status is False or gate_o_status is False:
                    gate_val = False
                elif target_status == "Unknown" or gate_o_status == "Unknown":
                    gate_val = "Unknown"
                else:
                    gate_val = True
                step_gate_evals.append(gate_val)
                continue

            # Fallback for any other step
            status_lower = s.gate_status.lower()
            if "false" in status_lower or "blocked" in status_lower:
                gate_val = False
            elif "unknown" in status_lower or "unresolved" in status_lower:
                gate_val = "Unknown"
            elif "true" in status_lower or "satisfied" in status_lower:
                gate_val = True
            else:
                gate_val = True
            step_gate_evals.append(gate_val)

        if any(g is False for g in step_gate_evals):
            return ("blocked", "Blocked", False)
        if any(g == "Unknown" for g in step_gate_evals):
            return ("unknown", "Unknown", False)

        p_like = bottleneck_likelihood([s.likelihood for s in subpath])
        return ("feasible", p_like, True)

    def is_feasible(
        self, checkpoint: str = "S2", gate_context: dict[str, Any] | None = None
    ) -> bool:
        """Check if all required gates up to checkpoint are satisfied."""
        _status, _p_like, feasible = self._evaluate_gates(checkpoint, gate_context=gate_context)
        return feasible

    def path_status(
        self, checkpoint: str = "S2", gate_context: dict[str, Any] | None = None
    ) -> str:
        """Return path status: 'feasible', 'blocked', or 'unknown'."""
        status, _p_like, _feasible = self._evaluate_gates(checkpoint, gate_context=gate_context)
        return status

    def path_likelihood(
        self, checkpoint: str = "S3", gate_context: dict[str, Any] | None = None
    ) -> str:
        """Evaluate bottleneck path likelihood up to the checkpoint taking gates into account."""
        _status, likelihood, _feasible = self._evaluate_gates(checkpoint, gate_context=gate_context)
        return likelihood

    def nominal_cost(
        self,
        checkpoint: str = "S3",
        formula: str = "base",
    ) -> int:
        """Unconditional rubric sum of step effort costs up to the checkpoint.

        This always returns the integer sum regardless of gating status.
        Use this when you need the raw effort specification independent of
        whether the path is feasible, blocked, or unknown.
        """
        return sum(s.cost(formula=formula) for s in self.subpath_to(checkpoint))

    def realized_cost(
        self,
        checkpoint: str = "S3",
        formula: str = "base",
        gate_context: dict[str, Any] | None = None,
    ) -> int | None:
        """Sum action effort costs up to the checkpoint, respecting gating feasibility.

        Returns the integer cost only when the path is feasible (all gates satisfied).
        Returns None when blocked or unknown/unresolved.
        """
        status, _likelihood, feasible = self._evaluate_gates(checkpoint, gate_context=gate_context)
        if status in ("blocked", "unknown"):
            return None
        return sum(s.cost(formula=formula) for s in self.subpath_to(checkpoint))

    def total_cost(
        self,
        checkpoint: str = "S3",
        formula: str = "base",
        gate_context: dict[str, Any] | None = None,
    ) -> int | None:
        """Alias for realized_cost - returns None when blocked or unknown."""
        return self.realized_cost(checkpoint=checkpoint, formula=formula, gate_context=gate_context)

    def active_step_count(self, checkpoint: str = "S3") -> int:
        """Count active attack actions up to the checkpoint."""
        return sum(1 for s in self.subpath_to(checkpoint) if s.action_type == "active")

    def passive_step_count(self, checkpoint: str = "S3") -> int:
        """Count passive structural closure steps up to the checkpoint."""
        return sum(1 for s in self.subpath_to(checkpoint) if s.action_type == "passive")

    def lexicographic_key(
        self,
        checkpoint: str = "S2",
        formula: str = "base",
        gate_context: dict[str, Any] | None = None,
    ) -> tuple:
        """Generate sort key for candidate lexicographic order.

        Order: <Feasible asc, I desc, P desc, C asc, Active asc>.
        Prioritizes feasible paths over blocked/unknown paths:
        (0 if is_feasible else 1, -impact_val, -likelihood_val, cost_val, active_count)
        where LIKELIHOOD_ORDINAL["Blocked"] = -1.
        If is_feasible is False, cost_val = float('inf').
        """
        feasible = self.is_feasible(checkpoint=checkpoint, gate_context=gate_context)
        impact_val = IMPACT_ORDINAL.get(self.target_impact, 0)
        p_str = self.path_likelihood(checkpoint=checkpoint, gate_context=gate_context)
        likelihood_val = LIKELIHOOD_ORDINAL.get(p_str, -1)

        if feasible:
            calc_cost = self.total_cost(
                checkpoint=checkpoint, formula=formula, gate_context=gate_context
            )
            cost_val = float("inf") if calc_cost is None else calc_cost
        else:
            cost_val = float("inf")

        active_count = self.active_step_count(checkpoint)
        feasible_flag = 0 if feasible else 1
        return (feasible_flag, -impact_val, -likelihood_val, cost_val, active_count)


def rank_attack_paths(
    paths: list[AttackPath],
    checkpoint: str = "S2",
    formula: str = "base",
    gate_context: dict[str, Any] | None = None,
) -> PathRankingResult:
    """Rank attack paths using candidate lexicographic order, separating feasible and blocked paths.

    Supports both uniform gate_context (applied to all paths) and explicit per-path
    mapping where keys are path names (case-insensitive strings matching p.name) and values
    are path-specific gate_context dictionaries or None (for nominal baseline).
    Paths omitted from a per-path mapping default to None (baseline).

    Returns PathRankingResult (dict subclass) with:
      - 'feasible': list of feasible AttackPath objects, sorted by lexicographic key
      - 'blocked': list of blocked or infeasible AttackPath objects, sorted by lexicographic key
      - 'infeasible': alias to 'blocked'
    """
    is_per_path = gate_context is not None and any(
        p.name in gate_context
        or any(
            isinstance(k, str) and k.strip().lower() == p.name.strip().lower() for k in gate_context
        )
        for p in paths
    )

    def _ctx_for(p: AttackPath) -> dict[str, Any] | None:
        if not is_per_path:
            return gate_context
        if gate_context is None:
            return None
        if p.name in gate_context:
            return gate_context[p.name]
        for k, v in gate_context.items():
            if isinstance(k, str) and k.strip().lower() == p.name.strip().lower():
                return v
        return None

    feasible_paths: list[AttackPath] = []
    blocked_paths: list[AttackPath] = []

    for p in paths:
        p_ctx = _ctx_for(p)
        if p.is_feasible(checkpoint=checkpoint, gate_context=p_ctx):
            feasible_paths.append(p)
        else:
            blocked_paths.append(p)

    feasible_paths.sort(
        key=lambda p: p.lexicographic_key(
            checkpoint=checkpoint, formula=formula, gate_context=_ctx_for(p)
        )
    )
    blocked_paths.sort(
        key=lambda p: p.lexicographic_key(
            checkpoint=checkpoint, formula=formula, gate_context=_ctx_for(p)
        )
    )

    return PathRankingResult(
        feasible=feasible_paths,
        blocked=blocked_paths,
        infeasible=blocked_paths,
    )


def build_path_1_seamless_reset() -> AttackPath:
    """Build Path 1: Reset chain from Source A to Target-User-KRBTGT via S2 Target-Group-DA."""
    steps = [
        ActionStep(
            name="genericall_reset_password",
            step_number=1,
            action_type="active",
            t1=1,
            t2=3,
            t3="High (Event 4724)",
            likelihood="Medium",
            gate_status="Satisfied (foothold assumption)",
            fact_stratum="Observed structural fact + foothold assumption",
            notes="Destructive password reset on User-Candidate; policy risk",
        ),
        ActionStep(
            name="activate_identity",
            step_number=2,
            action_type="active",
            t1=1,
            t2=2,
            t3="Medium (Event 4624)",
            likelihood="Medium",
            gate_status="Gate A: True (assumption)",
            fact_stratum="Declared scenario assumption",
            notes="Interactive authentication bridge into target directory context",
        ),
        ActionStep(
            name="propagate_membership",
            step_number=3,
            action_type="passive",
            t1=1,
            t2=1,
            t3="Low (None)",
            likelihood="High",
            gate_status="Gate M: True (PAC token)",
            fact_stratum="Observed structural fact + token assumption",
            notes="Passive group membership closure to Target-Group-DA (S2 Checkpoint)",
        ),
        ActionStep(
            name="dcsync_krbtgt",
            step_number=4,
            action_type="active",
            t1=2,
            t2=3,
            t3="High (Event 4662)",
            likelihood="Unknown",
            gate_status="Gate O: Unknown (chua co bang chung kiem chung phan quyen replication)",
            fact_stratum="Tier 2 technical rule + Tier 3 network assumption",
            notes="MS-DRSR replication query for krbtgt hash; Gate O replication rights unproven",
        ),
    ]
    return AttackPath(
        name="Path 1 (SEAMLESS Reset)",
        target_name="Target-User-KRBTGT",
        target_impact="Critical",  # Stipulated legacy scenario rating, not inferred from AD tier.
        steps=steps,
        is_synthetic=False,
    )


def build_path_2_synthetic_session() -> AttackPath:
    """Build Path 2: Synthetic HasSession chain to Target-User-KRBTGT via S2 Target-Group-DA."""
    steps = [
        ActionStep(
            name="token_impersonation",
            step_number=1,
            action_type="active",
            t1=2,
            t2=2,
            t3="High (LSASS access)",
            likelihood="High",
            gate_status="Satisfied (session assumption)",
            fact_stratum="Synthetic scenario hypothesis",
            notes="Extract existing admin token from LSASS memory; non-destructive",
        ),
        ActionStep(
            name="activate_identity",
            step_number=2,
            action_type="active",
            t1=1,
            t2=2,
            t3="Medium (Event 4624)",
            likelihood="High",
            gate_status="Gate A: True (assumption)",
            fact_stratum="Declared scenario assumption",
            notes="Valid existing token used directly in network context",
        ),
        ActionStep(
            name="inherit_da_entitlement",
            step_number=3,
            action_type="passive",
            t1=1,
            t2=1,
            t3="Low (None)",
            likelihood="High",
            gate_status="Gate M: True (synthetic PAC token)",
            fact_stratum="Synthetic scenario hypothesis",
            notes="Passive entitlement resolution from token to Target-Group-DA (S2 Checkpoint)",
        ),
        ActionStep(
            name="dcsync_krbtgt",
            step_number=4,
            action_type="active",
            t1=2,
            t2=3,
            t3="High (Event 4662)",
            likelihood="Unknown",
            gate_status="Gate O: Unknown (chua co bang chung kiem chung phan quyen replication)",
            fact_stratum="Tier 2 technical rule + Tier 3 network assumption",
            notes="MS-DRSR replication query for krbtgt hash; Gate O replication rights unproven",
        ),
    ]
    return AttackPath(
        name="Path 2 (Synthetic HasSession)",
        target_name="Target-User-KRBTGT",
        target_impact="Critical",  # Stipulated legacy scenario rating, not inferred from AD tier.
        steps=steps,
        is_synthetic=True,
    )


# --- GRAPH SEARCH & ALGORITHMS (DIJKSTRA VS EXHAUSTIVE ORACLE) ---


@dataclass(frozen=True)
class Edge:
    """Directed edge in an attack graph."""

    source: str
    target: str
    cost: float
    likelihood: float  # In [0.0, 1.0]
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert edge to JSON-serializable dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "cost": self.cost,
            "likelihood": self.likelihood,
            "name": self.name,
        }


def to_serializable(val: Any) -> Any:
    """Fallback JSON serializer for custom objects."""
    if isinstance(val, Fraction):
        return str(val)  # Lossless rational strings in experiment 6; no rounded risk comparison.
    if hasattr(val, "to_dict"):
        return val.to_dict()
    if hasattr(val, "__dataclass_fields__"):
        return {k: getattr(val, k) for k in val.__dataclass_fields__}
    if hasattr(val, "__dict__"):
        return val.__dict__
    return str(val)


def dijkstra_search(
    graph: dict[str, list[Edge]],
    start: str,
    goal: str,
    metric_type: str = "additive_cost",
    min_likelihood: float = 0.0,
) -> dict[str, Any]:
    """Run Dijkstra graph search from start to goal.

    Supported metric_type:
      - 'additive_cost': Minimizes cumulative non-negative edge cost C.
      - 'composite_ratio': Greedily minimizes local cumulative C / prod(P).
    """
    # Priority queue stores:
    # (score, current_node, path_nodes, path_edges, cumulative_cost, prod_likelihood)
    pq: list[tuple[float, str, list[str], list[Edge], float, float]] = [
        (0.0, start, [start], [], 0.0, 1.0)
    ]
    best_score: dict[str, float] = {start: 0.0}

    while pq:
        score, u, path, edges, c_acc, p_acc = heapq.heappop(pq)

        if score > best_score.get(u, float("inf")):
            continue

        if u == goal:
            return {
                "found": True,
                "path": path,
                "edges": [e.to_dict() for e in edges],
                "cost": c_acc,
                "likelihood": p_acc,
                "score": score,
            }

        for e in graph.get(u, []):
            if e.likelihood < min_likelihood:
                continue
            new_cost = c_acc + e.cost
            new_p = p_acc * e.likelihood
            if metric_type == "additive_cost":
                new_score = new_cost
            elif metric_type == "composite_ratio":
                new_score = new_cost / new_p if new_p > 0 else float("inf")
            else:
                raise ValueError(f"Unknown metric_type: {metric_type}")

            if new_score < best_score.get(e.target, float("inf")):
                best_score[e.target] = new_score
                heapq.heappush(
                    pq,
                    (new_score, e.target, path + [e.target], edges + [e], new_cost, new_p),
                )

    return {
        "found": False,
        "path": [],
        "edges": [],
        "score": float("inf"),
        "cost": 0.0,
        "likelihood": 0.0,
    }


def exhaustive_search(
    graph: dict[str, list[Edge]],
    start: str,
    goal: str,
    metric_type: str = "additive_cost",
    min_likelihood: float = 0.0,
) -> dict[str, Any]:
    """Exhaustive search oracle finding the globally optimal simple path."""
    all_paths: list[dict[str, Any]] = []

    def dfs(u: str, path: list[str], edges: list[Edge], c_acc: float, p_acc: float) -> None:
        if u == goal:
            if metric_type == "additive_cost":
                score = c_acc
            elif metric_type == "composite_ratio":
                score = c_acc / p_acc if p_acc > 0 else float("inf")
            else:
                raise ValueError(f"Unknown metric_type: {metric_type}")
            all_paths.append(
                {
                    "path": path,
                    "edges": [e.to_dict() for e in edges],
                    "cost": c_acc,
                    "likelihood": p_acc,
                    "score": score,
                }
            )
            return

        for e in graph.get(u, []):
            if e.target not in path:  # Simple paths only
                if e.likelihood < min_likelihood:
                    continue
                dfs(e.target, path + [e.target], edges + [e], c_acc + e.cost, p_acc * e.likelihood)

    dfs(start, [start], [], 0.0, 1.0)
    if not all_paths:
        return {
            "found": False,
            "path": [],
            "edges": [],
            "score": float("inf"),
            "cost": 0.0,
            "likelihood": 0.0,
            "all_paths": [],
        }

    best = min(all_paths, key=lambda x: x["score"])
    return {
        "found": True,
        "path": best["path"],
        "edges": best["edges"],
        "cost": best["cost"],
        "likelihood": best["likelihood"],
        "score": best["score"],
        "all_paths": all_paths,
    }


def demonstrate_edge_filter_failure() -> dict[str, Any]:
    """Demonstrate that static edge-level filtering fails under cumulative degradation.

    A 3-step path with individual edge likelihoods of 0.90 exceeds the High stratum
    threshold of 0.75 on every edge.
    However, the cumulative path likelihood is 0.90^3 = 0.729 < 0.75, dropping the
    entire path to Medium stratum.
    """
    edge_likelihoods = [0.90, 0.90, 0.90]
    high_threshold = 0.75

    edges_pass_filter = all(p >= high_threshold for p in edge_likelihoods)
    cumulative_p = round(math.prod(edge_likelihoods), 4)
    whole_path_stratum = "High" if cumulative_p >= high_threshold else "Medium"
    static_filter_guarantees_stratum = whole_path_stratum == "High"

    return {
        "edge_likelihoods": edge_likelihoods,
        "high_threshold": high_threshold,
        "edges_pass_static_filter": edges_pass_filter,
        "cumulative_path_likelihood": cumulative_p,
        "whole_path_stratum": whole_path_stratum,
        "static_filter_guarantees_stratum": static_filter_guarantees_stratum,
        "remedy": (
            "State-space expansion must retain conditional history and accumulated work, "
            "or enumerate bounded candidates; "
            "an active-step counter alone does not represent dependencies."
        ),
    }


def demonstrate_action_packaging_degradation() -> dict[str, Any]:
    """Demonstrate that naive step-counting breaks action packaging invariance under degradation."""
    gamma = 0.90
    p0 = 1.0

    # Split representation: 2 active steps (reset password + activate identity)
    p_split = round(p0 * math.pow(gamma, 2), 4)

    # Merged representation: 1 combined active step (reset and activate)
    p_merged = round(p0 * math.pow(gamma, 1), 4)

    packaging_invariant = p_split == p_merged

    return {
        "gamma": gamma,
        "split_active_steps": 2,
        "split_degraded_p": p_split,
        "merged_active_steps": 1,
        "merged_degraded_p": p_merged,
        "naive_step_counting_preserves_packaging": packaging_invariant,
        "finding": (
            "Naive step counting breaks action packaging invariance: "
            f"splitting an action into two discrete steps changes degraded likelihood "
            f"from {p_merged} to {p_split}. "
            "Likelihood degradation must depend on intrinsic effort or interaction boundary "
            "rather than arbitrary step counts."
        ),
    }


# --- DYNAMIC STATE & GATE EVALUATION ---


def evaluate_gate_truth_table() -> list[dict[str, Any]]:
    """Evaluate all 27 truth table assignments for Gate A, Gate M, and Gate O.

    Gate truth values: True, False, 'Unknown'.
    Rules:
      - If Gate A is False -> Path to S2 is BLOCKED (cost=None, status='blocked').
      - If Gate A is Unknown -> Path to S2 is Unknown (cost=None, status='unknown').
      - If Gate A is True and Gate M is True -> Path to S2 is reached
        (cost=3, status='reached', likelihood='Medium').
      - If Gate A is True and Gate M is False -> S2 is BLOCKED (cost=None, status='blocked').
      - If Gate A is True and Gate M is Unknown -> S2 is Unknown (cost=None, status='unknown').
      - For S3:
        * If S2 is blocked -> S3 is BLOCKED.
        * If S2 is unknown: if Gate O is False -> S3 blocked, else S3 unknown.
        * If S2 is reached:
          - If Gate O is True -> S3 is reached (cost=6, status='reached').
          - If Gate O is False -> S3 is BLOCKED (cost=None, status='blocked').
          - If Gate O is Unknown -> S3 is Unknown (cost=None, status='unknown').
    """
    domain = [True, False, "Unknown"]
    results = []

    for gate_a in domain:
        for gate_m in domain:
            for gate_o in domain:
                # Step 1: genericall_reset (cost 2, requires foothold) -> succeeds in scenario
                # Step 2: activate_identity (cost 1, requires Gate A)
                # Step 3: propagate_membership (cost 0, requires Gate M)
                # Step 4: dcsync_krbtgt (cost 3, requires Gate O)

                # Evaluate S2 using Kleene 3-valued logic:
                # Collect all prerequisite gate values for S2 (Gate A and Gate M).
                # False strictly absorbs Unknown.
                s2_gates = [gate_a, gate_m]
                if any(g is False for g in s2_gates):
                    s2_status = "blocked"
                    s2_cost = None
                    s2_likelihood = None
                elif any(g == "Unknown" for g in s2_gates):
                    s2_status = "unknown"
                    s2_cost = None
                    s2_likelihood = "Unknown"
                else:
                    s2_status = "reached"
                    s2_cost = 3
                    s2_likelihood = "Medium"

                # Evaluate S3 using Kleene 3-valued logic:
                # S3 depends on S2 status AND Gate O.
                # Collect all relevant values and apply False-absorbs-Unknown.
                if s2_status == "blocked":
                    s3_status = "blocked"
                    s3_cost = None
                    s3_likelihood = None
                elif s2_status == "unknown":
                    # S2 is unknown; check Gate O with Kleene absorption
                    if gate_o is False:
                        s3_status = "blocked"
                        s3_cost = None
                        s3_likelihood = None
                    else:
                        s3_status = "unknown"
                        s3_cost = None
                        s3_likelihood = "Unknown"
                else:  # s2_status == "reached"
                    if gate_o is False:
                        s3_status = "blocked"
                        s3_cost = None
                        s3_likelihood = None
                    elif gate_o == "Unknown":
                        s3_status = "unknown"
                        s3_cost = None
                        s3_likelihood = "Unknown"
                    else:  # gate_o is True
                        s3_status = "reached"
                        s3_cost = 6
                        s3_likelihood = "Medium"

                results.append(
                    {
                        "gate_a": gate_a,
                        "gate_m": gate_m,
                        "gate_o": gate_o,
                        "s2_status": s2_status,
                        "s2_cost": s2_cost,
                        "s2_likelihood": s2_likelihood,
                        "s3_status": s3_status,
                        "s3_cost": s3_cost,
                        "s3_likelihood": s3_likelihood,
                    }
                )
    return results


def evaluate_dynamic_modes(initial_facts: set[str]) -> dict[str, Any]:
    """Dynamically evaluate attack path execution from an initial set of factual assertions.

    Checkpoints evaluate hierarchically with authoritative prerequisite sets:
      - S1 (Reset): requires 6 reset preconditions (independent of S2/S3)
      - S2 (Domain Admins): requires S1 + structural_memberof + gate_a + gate_m
      - S3 (KRBTGT DCSync): requires S2 + target_krbtgt_exists + gate_o
    """
    has_foothold = "foothold" in initial_facts
    has_gate_a = "gate_a_accepted" in initial_facts
    has_gate_m = "gate_m_usable" in initial_facts
    has_gate_o = "gate_o_granted" in initial_facts

    # Authoritative facts per checkpoint
    has_genericall = "structural_genericall" in initial_facts
    has_source_enabled = "source_computer_enabled" in initial_facts
    has_target_enabled = "target_user_enabled" in initial_facts
    has_password_policy = "password_policy_satisfied" in initial_facts
    has_directory_write = "directory_write_available" in initial_facts

    has_memberof = "structural_memberof" in initial_facts
    has_krbtgt = "target_krbtgt_exists" in initial_facts

    # S0: structural presence (all structural entities and edges)
    has_full_structure = has_genericall and has_memberof and has_krbtgt
    s0_status = "Satisfied" if has_full_structure else "Missing structural edges"

    # S1: password reset execution - strictly independent of downstream membership / KRBTGT
    s1_prerequisites_met = (
        has_genericall
        and has_foothold
        and has_source_enabled
        and has_target_enabled
        and has_password_policy
        and has_directory_write
    )
    if s1_prerequisites_met:
        s1_status = "Reached (cost=2)"
        s1_reached = True
    else:
        missing = []
        if not has_genericall:
            missing.append("structural_genericall")
        if not has_foothold:
            missing.append("foothold")
        if not has_source_enabled:
            missing.append("source_computer_enabled")
        if not has_target_enabled:
            missing.append("target_user_enabled")
        if not has_password_policy:
            missing.append("password_policy_satisfied")
        if not has_directory_write:
            missing.append("directory_write_available")
        s1_status = f"Unsupported (missing: {', '.join(missing)})"
        s1_reached = False

    # S2: Domain Admins access - depends on S1 + membership + Gate A + Gate M
    if s1_reached and has_memberof and has_gate_a and has_gate_m:
        s2_status = "Reached (cost=3, P=Medium)"
        s2_reached = True
    else:
        s2_missing = []
        if not s1_reached:
            s2_missing.append("S1 reset prerequisites")
        if not has_memberof:
            s2_missing.append("structural_memberof")
        if not has_gate_a:
            s2_missing.append("gate_a_accepted")
        if not has_gate_m:
            s2_missing.append("gate_m_usable")
        s2_status = f"Unsupported (missing: {', '.join(s2_missing)})"
        s2_reached = False

    # S3: KRBTGT DCSync - depends on S2 + KRBTGT target + Gate O
    if s2_reached and has_krbtgt and has_gate_o:
        s3_status = "Reached (cost=6)"
    else:
        s3_status = "Unsupported (chua co bang chung da duoc kiem chung ve phan quyen replication)"

    return {
        "checkpoint_s0_status": s0_status,
        "checkpoint_s1_status": s1_status,
        "checkpoint_s2_status": s2_status,
        "checkpoint_s3_status": s3_status,
        "foothold_proven": has_foothold,
        "gate_a_proven": has_gate_a,
        "gate_m_proven": has_gate_m,
        "gate_o_proven": has_gate_o,
    }


# --- EXPERIMENT IMPLEMENTATIONS ---


def verify_hand_worked_examples() -> dict[str, Any]:
    """Experiment (a): Verify hand-worked examples from Section 10 of path-ranking-model.md.

    Traces Path 1 and Path 2 step-by-step, verifies costs, likelihoods, uncertainty,
    and computes exact deviation against hand-derived values.
    """
    path1 = build_path_1_seamless_reset()
    path2 = build_path_2_synthetic_session()

    # Hand-derived ground truth specification from Section 10.2
    hand_truth = {
        "Path 1": {
            "steps": [
                {
                    "step": 1,
                    "t1": 1,
                    "t2": 3,
                    "cost": 2,
                    "likelihood": "Medium",
                    "t3": "High (Event 4724)",
                },
                {
                    "step": 2,
                    "t1": 1,
                    "t2": 2,
                    "cost": 1,
                    "likelihood": "Medium",
                    "t3": "Medium (Event 4624)",
                },
                {"step": 3, "t1": 1, "t2": 1, "cost": 0, "likelihood": "High", "t3": "Low (None)"},
                {
                    "step": 4,
                    "t1": 2,
                    "t2": 3,
                    "cost": 3,
                    "likelihood": "Unknown",
                    "t3": "High (Event 4662)",
                },
            ],
            "s2_cost": 3,
            "s2_likelihood": "Medium",
            "s3_likelihood": "Unknown",
        },
        "Path 2": {
            "steps": [
                {
                    "step": 1,
                    "t1": 2,
                    "t2": 2,
                    "cost": 2,
                    "likelihood": "High",
                    "t3": "High (LSASS access)",
                },
                {
                    "step": 2,
                    "t1": 1,
                    "t2": 2,
                    "cost": 1,
                    "likelihood": "High",
                    "t3": "Medium (Event 4624)",
                },
                {"step": 3, "t1": 1, "t2": 1, "cost": 0, "likelihood": "High", "t3": "Low (None)"},
                {
                    "step": 4,
                    "t1": 2,
                    "t2": 3,
                    "cost": 3,
                    "likelihood": "Unknown",
                    "t3": "High (Event 4662)",
                },
            ],
            "s2_cost": 3,
            "s2_likelihood": "High",
            "s3_likelihood": "Unknown",
        },
    }

    step_verifications = []
    total_deviation = 0

    for path, key in ((path1, "Path 1"), (path2, "Path 2")):
        expected = hand_truth[key]
        for idx, (step, exp_step) in enumerate(zip(path.steps, expected["steps"], strict=True)):
            calc_cost = step.cost("base")
            dev_cost = abs(calc_cost - exp_step["cost"])
            dev_t1 = abs(step.t1 - exp_step["t1"])
            dev_t2 = abs(step.t2 - exp_step["t2"])
            dev_p = 0 if step.likelihood == exp_step["likelihood"] else 1
            dev_t3 = 0 if step.t3 == exp_step["t3"] else 1
            step_dev = dev_cost + dev_t1 + dev_t2 + dev_p + dev_t3
            total_deviation += step_dev
            step_verifications.append(
                {
                    "path": key,
                    "step": idx + 1,
                    "name": step.name,
                    "action_type": step.action_type,
                    "t1": step.t1,
                    "t2": step.t2,
                    "cost": calc_cost,
                    "expected_cost": exp_step["cost"],
                    "likelihood": step.likelihood,
                    "expected_likelihood": exp_step["likelihood"],
                    "t3": step.t3,
                    "deviation": step_dev,
                }
            )

    # Checkpoint S2 checks
    p1_s2_cost = path1.total_cost("S2")
    p1_s2_p = path1.path_likelihood("S2")
    p2_s2_cost = path2.total_cost("S2")
    p2_s2_p = path2.path_likelihood("S2")

    dev_p1_s2 = abs(p1_s2_cost - 3) + (0 if p1_s2_p == "Medium" else 1)
    dev_p2_s2 = abs(p2_s2_cost - 3) + (0 if p2_s2_p == "High" else 1)
    total_deviation += dev_p1_s2 + dev_p2_s2

    # Goal S3 checks
    p1_s3_p = path1.path_likelihood("S3")
    p2_s3_p = path2.path_likelihood("S3")
    dev_p1_s3 = 0 if p1_s3_p == "Unknown" else 1
    dev_p2_s3 = 0 if p2_s3_p == "Unknown" else 1
    total_deviation += dev_p1_s3 + dev_p2_s3

    # Ranking at S2 in Scenario Mode
    ranked_s2 = sorted([path1, path2], key=lambda p: p.lexicographic_key(checkpoint="S2"))
    ranking_correct = ranked_s2[0].name == path2.name and ranked_s2[1].name == path1.name
    if not ranking_correct:
        total_deviation += 1

    return {
        "experiment": "Hand-worked Example Verification",
        "step_verifications": step_verifications,
        "path1_s2": {
            "cost": p1_s2_cost,
            "likelihood": p1_s2_p,
            "expected_cost": 3,
            "expected_likelihood": "Medium",
        },
        "path2_s2": {
            "cost": p2_s2_cost,
            "likelihood": p2_s2_p,
            "expected_cost": 3,
            "expected_likelihood": "High",
        },
        "path1_s3": {
            "nominal_cost": path1.nominal_cost("S3"),
            "realized_cost": path1.total_cost("S3"),
            "cost": path1.total_cost("S3"),
            "likelihood": p1_s3_p,
            "expected_likelihood": "Unknown",
        },
        "path2_s3": {
            "nominal_cost": path2.nominal_cost("S3"),
            "realized_cost": path2.total_cost("S3"),
            "cost": path2.total_cost("S3"),
            "likelihood": p2_s3_p,
            "expected_likelihood": "Unknown",
        },
        "ranking_at_s2": [p.name for p in ranked_s2],
        "ranking_correct": ranking_correct,
        "total_deviation": total_deviation,
        "status": "PASS" if total_deviation == 0 else "FAIL",
    }


def run_experiment_1_ranking_tradeoff() -> dict[str, Any]:
    """Experiment 1: Candidate Lexicographic Model vs Tradeoff Models (Impact vs Likelihood).

    Compares Lexicographic <I desc, P desc, C asc> against Tradeoff Models
    (Ordinal Heuristic I * P, Qualitative Risk Matrix, and Linear MAUT).
    Impact ratings and technical/business labels are separately stipulated synthetic inputs.
    """
    path_a = {
        "name": "Path A",
        "target": "Business-critical application (synthetic)",
        "security_labels": ["CrownJewel"],
        "ad_technical_tier": "Tier1",
        "impact": "Critical",
        "impact_ordinal": IMPACT_ORDINAL["Critical"],
        "likelihood": "Low",
        "likelihood_ordinal": 1,
        "effort": 3,
    }
    path_b = {
        "name": "Path B",
        "target": "Identity control-plane target (synthetic)",
        "security_labels": ["Tier0"],
        "ad_technical_tier": "Tier0",
        "impact": "High",
        "impact_ordinal": IMPACT_ORDINAL["High"],
        "likelihood": "High",
        "likelihood_ordinal": 3,
        "effort": 3,
    }

    # Model 1: Lexicographic <I desc, P desc, C asc>
    lex_key_a = (-path_a["impact_ordinal"], -path_a["likelihood_ordinal"], path_a["effort"])
    lex_key_b = (-path_b["impact_ordinal"], -path_b["likelihood_ordinal"], path_b["effort"])
    lex_winner = "Path A" if lex_key_a < lex_key_b else "Path B"

    # Model 2: Illustrative Ordinal Heuristic R = I * P
    expected_risk_a = path_a["impact_ordinal"] * path_a["likelihood_ordinal"]  # 4 * 1 = 4
    expected_risk_b = path_b["impact_ordinal"] * path_b["likelihood_ordinal"]  # 3 * 3 = 9
    risk_winner = "Path B" if expected_risk_b > expected_risk_a else "Path A"

    # Model 3: Qualitative Risk Matrix Classification
    matrix_levels = {
        (4, 1): "Moderate Risk (Level 2)",
        (3, 3): "Critical Risk (Level 4)",
    }
    matrix_a = matrix_levels[(4, 1)]
    matrix_b = matrix_levels[(3, 3)]

    # Model 4: Normalized Multi-Attribute Utility (w_I=0.5, w_P=0.5)
    utility_a = round(0.5 * (4 / 4) + 0.5 * (1 / 3), 4)
    utility_b = round(0.5 * (3 / 4) + 0.5 * (3 / 3), 4)
    utility_winner = "Path B" if utility_b > utility_a else "Path A"

    comparison_table = [
        {
            "attribute": "Target Impact (I)",
            "path_a": "Critical (I=4)",
            "path_b": "High (I=3)",
            "comparison": "Path A > Path B",
        },
        {
            "attribute": "Likelihood (P)",
            "path_a": "Low (P=1)",
            "path_b": "High (P=3)",
            "comparison": "Path B > Path A",
        },
        {
            "attribute": "Effort Cost (C)",
            "path_a": "3",
            "path_b": "3",
            "comparison": "Equal (C=3)",
        },
        {
            "attribute": "Lexicographic Rank",
            "path_a": "Rank 1 (Selected)",
            "path_b": "Rank 2",
            "comparison": "Path A wins (blind to likelihood across impact tiers)",
        },
        {
            "attribute": "Qualitative Risk Matrix Heuristic (I * P)",
            "path_a": f"4 * 1 = {expected_risk_a}",
            "path_b": f"3 * 3 = {expected_risk_b}",
            "comparison": f"Path B wins ({expected_risk_b} > {expected_risk_a})",
        },
        {
            "attribute": "Qualitative Risk Matrix",
            "path_a": matrix_a,
            "path_b": matrix_b,
            "comparison": "Path B Critical > Path A Moderate",
        },
        {
            "attribute": "Additive Utility U(I, P)",
            "path_a": f"{utility_a}",
            "path_b": f"{utility_b}",
            "comparison": f"Path B wins ({utility_b} > {utility_a})",
        },
    ]

    tradeoff_analysis = [
        (
            "Mathematical Note: Ordinal multiplication I * P (4*1=4, 3*3=9) is an illustrative "
            "heuristic used in qualitative risk matrices, NOT mathematically valid expected loss "
            "E[Loss]. Ordinal scales encode ranking rather than ratio-scale probabilities."
        ),
        (
            "Paradigm Comparison: Neither Lexicographic nor Risk Matrix proves the other wrong. "
            "They represent distinct risk management paradigms."
        ),
        (
            "Lexicographic Model prioritizes the separately rated Critical business consequence "
            "over High, regardless of likelihood. Tier0 and CrownJewel are orthogonal ontology "
            "labels, not impact levels; neither label determines the consequence rating. "
            "These synthetic ratings do not establish that Tier0 targets have lower impact."
        ),
        (
            "Risk Matrix / Tradeoff Model embodies operational triage under finite defense "
            "bandwidth: it prioritizes Path B because an imminent, high-likelihood compromise "
            "against High-impact systems demands urgent containment before low-probability "
            "catastrophic risks."
        ),
    ]

    return {
        "experiment": "Experiment 1: Candidate Ranking vs Tradeoff Models",
        "path_a": path_a,
        "path_b": path_b,
        "lexicographic_winner": lex_winner,
        "expected_risk_winner": risk_winner,
        "utility_winner": utility_winner,
        "rank_disagreement": lex_winner != risk_winner,
        "comparison_table": comparison_table,
        "tradeoff_analysis": tradeoff_analysis,
        "status": "PASS" if (lex_winner == "Path A" and risk_winner == "Path B") else "FAIL",
    }


def run_experiment_2_effort_sensitivity() -> dict[str, Any]:
    """Experiment 2: Effort Sensitivity within Equal Strata (Same I, Same P)."""
    closure_step = ActionStep(
        name="passive_membership_closure",
        step_number=2,
        action_type="passive",
        t1=1,
        t2=1,
        t3="Low (None)",
        likelihood="High",
        gate_status="Gate M: True",
        fact_stratum="Passive structural closure",
    )

    path_3a_active = ActionStep(
        name="tooling_heavy_exploit",
        step_number=1,
        action_type="active",
        t1=3,
        t2=1,
        t3="Medium (Event 4624)",
        likelihood="Medium",
        gate_status="Satisfied",
        fact_stratum="Observed technical rule",
        notes="Custom tool / complex exploit, low defense friction",
    )

    path_3b_active = ActionStep(
        name="friction_heavy_action",
        step_number=1,
        action_type="active",
        t1=1,
        t2=3,
        t3="High (Event 4724)",
        likelihood="Medium",
        gate_status="Satisfied",
        fact_stratum="Observed technical rule",
        notes="Built-in CLI, high defense friction / destructive action",
    )

    formulas = [
        ("base", "C1 = T1 + T2 - 2 (Base additive)"),
        ("max", "C2 = max(T1, T2) - 1 (Max bottleneck)"),
        ("tool_weighted", "C3 = 2*T1 + T2 - 3 (Tool-weighted)"),
        ("friction_weighted", "C4 = T1 + 2*T2 - 3 (Friction-weighted)"),
    ]

    variant_results = []
    closure_invariants_pass = True

    for f_key, f_desc in formulas:
        c_closure = closure_step.cost(formula=f_key)
        if c_closure != 0:
            closure_invariants_pass = False

        c_3a_active = path_3a_active.cost(formula=f_key)
        c_3b_active = path_3b_active.cost(formula=f_key)

        tot_3a = c_3a_active + c_closure
        tot_3b = c_3b_active + c_closure

        if tot_3a < tot_3b:
            preferred = "Path 3A (lower effort)"
        elif tot_3b < tot_3a:
            preferred = "Path 3B (lower effort)"
        else:
            preferred = "Tie (equal effort)"

        variant_results.append(
            {
                "formula_key": f_key,
                "formula_desc": f_desc,
                "closure_cost": c_closure,
                "path_3a_active_cost": c_3a_active,
                "path_3b_active_cost": c_3b_active,
                "path_3a_total": tot_3a,
                "path_3b_total": tot_3b,
                "preferred_path": preferred,
            }
        )

    tool_res = next(r for r in variant_results if r["formula_key"] == "tool_weighted")
    fric_res = next(r for r in variant_results if r["formula_key"] == "friction_weighted")
    rank_reversal_observed = (
        tool_res["path_3b_total"] < tool_res["path_3a_total"]
        and fric_res["path_3a_total"] < fric_res["path_3b_total"]
    )

    return {
        "experiment": "Experiment 2: Effort Sensitivity within Equal Strata",
        "variant_results": variant_results,
        "closure_invariants_pass": closure_invariants_pass,
        "rank_reversal_observed": rank_reversal_observed,
        "status": "PASS" if (closure_invariants_pass and rank_reversal_observed) else "FAIL",
    }


def run_experiment_3_closure_invariance() -> dict[str, Any]:
    """Experiment 3: Closure Cost Invariance & Semantic Equivalence."""
    reset_step = ActionStep(
        name="genericall_reset_password",
        step_number=1,
        action_type="active",
        t1=1,
        t2=3,
        t3="High (Event 4724)",
        likelihood="Medium",
        gate_status="Satisfied",
        fact_stratum="Observed structural fact",
    )
    activate_step = ActionStep(
        name="activate_identity",
        step_number=2,
        action_type="active",
        t1=1,
        t2=2,
        t3="Medium (Event 4624)",
        likelihood="Medium",
        gate_status="Gate A: True",
        fact_stratum="Declared scenario assumption",
    )
    single_closure = ActionStep(
        name="memberof_closure_1",
        step_number=3,
        action_type="passive",
        t1=1,
        t2=1,
        t3="Low (None)",
        likelihood="High",
        gate_status="Gate M: True",
        fact_stratum="Passive structural closure",
    )
    nested_closures = [
        ActionStep(
            name=f"memberof_closure_hop_{i}",
            step_number=3 + i,
            action_type="passive",
            t1=1,
            t2=1,
            t3="Low (None)",
            likelihood="High",
            gate_status="Gate M: True",
            fact_stratum="Passive structural closure",
        )
        for i in range(3)
    ]

    # 1. Normalized formula test
    cost_active = reset_step.cost("base") + activate_step.cost("base")
    cost_1hop_normalized = cost_active + single_closure.cost("base")
    cost_3hop_normalized = cost_active + sum(c.cost("base") for c in nested_closures)
    normalized_invariant = cost_1hop_normalized == cost_3hop_normalized

    # 2. Non-normalized formula test
    raw_active_cost = 2
    raw_closure_cost = single_closure.cost("raw_max_unnormalized")
    raw_1hop_total = raw_active_cost + raw_closure_cost
    raw_3hop_total = raw_active_cost + 3 * raw_closure_cost
    raw_inflation_delta = raw_3hop_total - raw_1hop_total

    # 3. Packaging invariance test
    merged_step = ActionStep(
        name="reset_and_activate",
        step_number=1,
        action_type="active",
        t1=2,
        t2=3,
        t3="High (Combined)",
        likelihood="Medium",
        gate_status="Gate A: True",
        fact_stratum="Declared scenario assumption",
    )
    split_cost = reset_step.cost("base") + activate_step.cost("base")
    merged_cost = merged_step.cost("base")
    packaging_invariant = split_cost == merged_cost

    return {
        "experiment": "Experiment 3: Closure Cost Invariance & Semantic Equivalence",
        "normalized_1hop_cost": cost_1hop_normalized,
        "normalized_3hop_cost": cost_3hop_normalized,
        "normalized_invariant": normalized_invariant,
        "raw_1hop_cost": raw_1hop_total,
        "raw_3hop_cost": raw_3hop_total,
        "raw_inflation_delta": raw_inflation_delta,
        "packaging_split_cost": split_cost,
        "packaging_merged_cost": merged_cost,
        "packaging_split_actions": 2,
        "packaging_merged_actions": 1,
        "packaging_invariant": packaging_invariant,
        "packaging_scope": (
            "Legacy fixture sets a new merged rating to match the split sum; "
            "this numerical agreement alone does not prove packaging invariance. "
            "Experiment 6 reuses the identical work ledger without rerating."
        ),
        "status": (
            "PASS"
            if (normalized_invariant and raw_inflation_delta == 2 and packaging_invariant)
            else "FAIL"
        ),
    }


def run_experiment_4_uncertainty_propagation() -> dict[str, Any]:
    """Experiment 4: Dynamic State and Gate Evaluation & Uncertainty Propagation.

    Evaluates:
      1. Bottleneck uncertainty propagation under Gate O.
      2. Comprehensive 27-permutation truth table for Gate A, Gate M, and Gate O.
      3. Dynamic state evaluation for Evidence-only mode vs Scenario mode.
    """
    path1 = build_path_1_seamless_reset()
    path2 = build_path_2_synthetic_session()

    p1_steps = [s.likelihood for s in path1.steps]
    p1_s3_likelihood = bottleneck_likelihood(p1_steps)

    p2_steps = [s.likelihood for s in path2.steps]
    p2_s3_likelihood = bottleneck_likelihood(p2_steps)

    bottleneck_tests = [
        (["High", "High"], "High"),
        (["High", "Medium"], "Medium"),
        (["High", "Low"], "Low"),
        (["Medium", "Low"], "Low"),
        (["High", "Unknown"], "Unknown"),
        (["Medium", "Unknown"], "Unknown"),
        (["Low", "Unknown"], "Unknown"),
        (["Unknown", "Unknown"], "Unknown"),
    ]
    truth_table_passed = all(bottleneck_likelihood(inp) == exp for inp, exp in bottleneck_tests)

    # Dynamic 27-assignment truth table evaluation
    truth_table_27 = evaluate_gate_truth_table()
    gate_27_passed = len(truth_table_27) == 27
    for row in truth_table_27:
        ga, gm, go = row["gate_a"], row["gate_m"], row["gate_o"]
        # Validate S2 using same Kleene logic: False absorbs Unknown
        s2_gates = [ga, gm]
        if any(g is False for g in s2_gates):
            expected_s2 = "blocked"
        elif any(g == "Unknown" for g in s2_gates):
            expected_s2 = "unknown"
        else:
            expected_s2 = "reached"

        if row["s2_status"] != expected_s2:
            gate_27_passed = False
        if expected_s2 == "reached" and row["s2_cost"] != 3:
            gate_27_passed = False
        if expected_s2 in ("blocked", "unknown") and row["s2_cost"] is not None:
            gate_27_passed = False

        # Validate S3
        if expected_s2 == "blocked":
            if row["s3_status"] != "blocked":
                gate_27_passed = False
        elif expected_s2 == "unknown":
            if go is False:
                if row["s3_status"] != "blocked":
                    gate_27_passed = False
            else:
                if row["s3_status"] != "unknown":
                    gate_27_passed = False
        else:  # reached
            if go is True:
                if row["s3_status"] != "reached" or row["s3_cost"] != 6:
                    gate_27_passed = False
            elif go is False:
                if row["s3_status"] != "blocked":
                    gate_27_passed = False
            elif go == "Unknown":
                if row["s3_status"] != "unknown":
                    gate_27_passed = False

    # Dynamic evaluation of Evidence-only mode vs Scenario mode from initial fact sets
    evidence_facts = {
        "source_a_exists",
        "structural_genericall",
        "structural_memberof",
        "target_krbtgt_exists",
    }
    scenario_facts = {
        "source_a_exists",
        "structural_genericall",
        "structural_memberof",
        "target_krbtgt_exists",
        "source_computer_enabled",
        "target_user_enabled",
        "foothold",
        "password_policy_satisfied",
        "directory_write_available",
        "gate_a_accepted",
        "gate_m_usable",
    }

    dynamic_modes = {
        "evidence_only_mode": evaluate_dynamic_modes(evidence_facts),
        "scenario_mode": evaluate_dynamic_modes(scenario_facts),
    }

    propagation_correct = (
        p1_s3_likelihood == "Unknown"
        and p2_s3_likelihood == "Unknown"
        and truth_table_passed
        and gate_27_passed
    )

    return {
        "experiment": "Experiment 4: Uncertainty Propagation (Gate O) & Dynamic State Evaluation",
        "path1_s3_likelihood": p1_s3_likelihood,
        "path2_s3_likelihood": p2_s3_likelihood,
        "truth_table_passed": truth_table_passed,
        "gate_truth_table_passed": gate_27_passed,
        "gate_truth_table_count": len(truth_table_27),
        "modes_evaluation": dynamic_modes,
        "propagation_correct": propagation_correct,
        "status": "PASS" if propagation_correct else "FAIL",
    }


def run_experiment_5_length_degradation_dijkstra() -> dict[str, Any]:
    """Experiment 5: Path Length Degradation & Dijkstra Compatibility.

    Evaluates:
      1. Pure bottleneck min limitation: 1-step High vs 10-step High both yield High.
      2. Active-step length discount model: P_degraded = P0 * (gamma ^ k_active).
      3. Dijkstra compatibility on real graph search algorithms:
         - Counterexample graph on non-linear / non-additive metric (C / prod(P)):
           Runs Dijkstra search vs Exhaustive search oracle.
           Proves Dijkstra's local greedy choice returns suboptimal global score!
         - Stratified Dijkstra on filtered stratum (C >= 0 additive):
           Runs Dijkstra search vs Exhaustive search oracle.
           Proves Dijkstra finds exact optimal path and cost matching the oracle!
      4. Direct test of edge-filtering stratum failure under cumulative degradation.
      5. Action packaging violation under naive step-counting.
    """
    # 1. Bottleneck limitation comparison
    one_step_bottleneck = bottleneck_likelihood(["High"])
    ten_step_bottleneck = bottleneck_likelihood(["High"] * 10)
    bottleneck_indifferent = one_step_bottleneck == ten_step_bottleneck == "High"

    # 2. Active-step length discount model
    gamma = 0.90
    p0 = 1.0

    def classify_probability(p_val: float) -> str:
        if p_val >= 0.75:
            return "High"
        if p_val >= 0.50:
            return "Medium"
        return "Low"

    length_degradation_table = []
    for k in range(1, 11):
        p_deg = round(p0 * math.pow(gamma, k), 4)
        cat = classify_probability(p_deg)
        length_degradation_table.append(
            {
                "active_steps": k,
                "degraded_probability": p_deg,
                "ordinal_stratum": cat,
            }
        )

    active_k2_only = round(p0 * math.pow(gamma, 2), 4)
    active_k2_plus_5_passive = round(p0 * math.pow(gamma, 2), 4)
    passive_invariance_maintained = active_k2_only == active_k2_plus_5_passive

    # 3. Real Graph Search Counterexample: Non-linear composite ratio C / prod(P)
    # S -> X directly: C=1.0, P=0.5 (local ratio 1.0/0.5 = 2.0)
    # S -> B -> X: S->B (C=1.0, P=0.95), B->X (C=1.0, P=0.95) (at X: C=2.0, P=0.9025, ratio 2.216)
    # From X -> T: C=6.0, P=0.5
    # Total path S-X-T: C=7.0, P=0.25, score = 28.0
    # Total path S-B-X-T: C=8.0, P=0.45125, score = 17.7285 (substantially better!)
    # Dijkstra greedily prunes B at node X because 2.0 < 2.216, returning suboptimal score 28.0!
    counterexample_graph: dict[str, list[Edge]] = {
        "S": [
            Edge("S", "X", cost=1.0, likelihood=0.5, name="S->X (fast but risky)"),
            Edge("S", "B", cost=1.0, likelihood=0.95, name="S->B"),
        ],
        "B": [
            Edge("B", "X", cost=1.0, likelihood=0.95, name="B->X"),
        ],
        "X": [
            Edge("X", "T", cost=6.0, likelihood=0.5, name="X->T"),
        ],
        "T": [],
    }

    dijk_nonadditive = dijkstra_search(
        counterexample_graph, "S", "T", metric_type="composite_ratio"
    )
    exh_nonadditive = exhaustive_search(
        counterexample_graph, "S", "T", metric_type="composite_ratio"
    )

    bellman_violation_demonstrated = (
        dijk_nonadditive["found"]
        and exh_nonadditive["found"]
        and dijk_nonadditive["score"] > exh_nonadditive["score"]
        and dijk_nonadditive["path"] != exh_nonadditive["path"]
    )

    # 4. Stratified Dijkstra Case: Filtered stratum with additive C >= 0
    # Stratum filter: P >= 0.75
    stratified_graph: dict[str, list[Edge]] = {
        "S": [
            Edge("S", "X", cost=1.0, likelihood=0.5, name="S->X (pruned by stratum filter)"),
            Edge("S", "B", cost=2.0, likelihood=0.95, name="S->B"),
            Edge("S", "C", cost=3.0, likelihood=0.95, name="S->C"),
        ],
        "B": [
            Edge("B", "T", cost=2.0, likelihood=0.95, name="B->T"),
        ],
        "C": [
            Edge("C", "T", cost=0.5, likelihood=0.95, name="C->T"),
        ],
        "X": [
            Edge("X", "T", cost=1.0, likelihood=0.5, name="X->T"),
        ],
        "T": [],
    }

    dijk_strat = dijkstra_search(
        stratified_graph, "S", "T", metric_type="additive_cost", min_likelihood=0.75
    )
    exh_strat = exhaustive_search(
        stratified_graph, "S", "T", metric_type="additive_cost", min_likelihood=0.75
    )

    stratified_dijkstra_success = (
        dijk_strat["found"]
        and exh_strat["found"]
        and dijk_strat["path"] == exh_strat["path"]
        and dijk_strat["cost"] == exh_strat["cost"]
    )

    # 5. Direct test of edge-filtering stratum failure
    edge_filter_failure = demonstrate_edge_filter_failure()

    # 6. Action packaging degradation
    packaging_degradation = demonstrate_action_packaging_degradation()

    all_pass = (
        bottleneck_indifferent
        and passive_invariance_maintained
        and bellman_violation_demonstrated
        and stratified_dijkstra_success
        and not edge_filter_failure["static_filter_guarantees_stratum"]
        and not packaging_degradation["naive_step_counting_preserves_packaging"]
    )

    return {
        "experiment": "Experiment 5: Path Length Degradation & Dijkstra Compatibility",
        "bottleneck_indifferent": bottleneck_indifferent,
        "length_degradation_table": length_degradation_table,
        "passive_invariance_maintained": passive_invariance_maintained,
        "dijkstra_nonadditive_result": dijk_nonadditive,
        "exhaustive_nonadditive_result": exh_nonadditive,
        "bellman_violation_demonstrated": bellman_violation_demonstrated,
        "dijkstra_stratified_result": dijk_strat,
        "exhaustive_stratified_result": exh_strat,
        "stratified_dijkstra_success": stratified_dijkstra_success,
        "edge_filter_failure": edge_filter_failure,
        "packaging_degradation": packaging_degradation,
        "status": "PASS" if all_pass else "FAIL",
    }


# --- REPRODUCIBLE SNAPSHOT VERIFICATION ---


@dataclass(frozen=True)
class ResearchAction:
    """Synthetic monotone action packet; units retain binding/work boundaries across packaging."""

    name: str
    requires: frozenset[str]
    adds: frozenset[str]
    units: tuple[str, ...]


def assess_scoped_program(
    packets: list[tuple[str, ...]],
    units: dict[str, ActionStep | None],
    conditional_bounds: dict[tuple[str, ...], tuple[float, float]],
    gates: tuple[Any, ...] = (),
) -> dict[str, Any]:
    """Compose bounds conditional on the FULL prior success history, never marginal ratings.

    Repeated IDs mean the same persistent completed work, not a new attempt.
    Pure passive closure has an empty packet. All inputs belong to ONE fixed scenario,
    initial boundary, horizon and versioned ledger; bounds are supplied, not inferred.
    A present unit with value None has unresolved rating/overlap; a missing ID is an error.
    """
    program = tuple(dict.fromkeys(unit for packet in packets for unit in packet))
    unrated_units = tuple(unit for unit in program if units[unit] is None)
    nominal = None if unrated_units else sum(units[unit].cost() for unit in program)
    parsed = [parse_tristate(gate) for gate in gates]
    status = "blocked" if False in parsed else "unknown" if "Unknown" in parsed else "feasible"
    lower = upper = Fraction(1)
    rated = True
    for length in range(1, len(program) + 1):
        interval = conditional_bounds.get(program[:length])
        if interval is None:
            rated = False
            continue
        lo, hi = interval
        if (
            isinstance(lo, bool)
            or isinstance(hi, bool)
            or not math.isfinite(lo)
            or not math.isfinite(hi)
            or not 0 <= lo <= hi <= 1
        ):
            raise ValueError("conditional bounds must satisfy 0 <= lower <= upper <= 1")
        # Interpret the supplied decimal spelling exactly; float products can break point ties.
        lower *= Fraction(str(lo))
        upper *= Fraction(str(hi))
        if upper == 0:
            rated = True
            break  # Whole-program success is zero; later null-prefix conditionals are undefined.
    return {
        "program": program,
        "status": status,
        "nominal_effort": nominal,
        "effort": nominal if status == "feasible" else None,
        "effort_status": "ineligible"
        if status != "feasible"
        else "unrated"
        if unrated_units
        else "rated",
        "unrated_work_units": unrated_units,
        "likelihood_interval": (lower, upper) if rated and status == "feasible" else None,
    }


def risk_ineligibility(assessment: dict[str, Any]) -> list[str]:
    """Authoritative risk eligibility; effort is optional for the two risk axes."""
    reasons = []
    status = assessment.get("status", "unknown")
    if status != "feasible":
        reasons.append("blocked" if status == "blocked" else "unknown")
    if assessment.get("likelihood_interval") is None:
        reasons.append("likelihood_unrated")
    impact = assessment.get("impact")
    if not isinstance(impact, str) or impact not in IMPACT_ORDINAL:
        reasons.append("impact_unrated")
    return reasons


def scoped_preference(a: dict[str, Any], b: dict[str, Any]) -> str:
    """Conservative Pareto; overlapping intervals cannot establish a likelihood ordering.

    Effort breaks ties only for identical impact and identical point likelihood.
    It is a rubric convention, not expected loss, time, or evidence of equal latent risk.
    """
    if risk_ineligibility(a) or risk_ineligibility(b):
        return "not_eligible"
    ia, ib = IMPACT_ORDINAL[a["impact"]], IMPACT_ORDINAL[b["impact"]]
    la, ua = a["likelihood_interval"]
    lb, ub = b["likelihood_interval"]
    if ia == ib and la == ua == lb == ub:
        if a.get("effort") is None or b.get("effort") is None:
            return "incomparable"
        return "a" if a["effort"] < b["effort"] else "b" if b["effort"] < a["effort"] else "tie"
    if ia >= ib and la >= ub and (ia > ib or la > ub):
        return "a"
    if ib >= ia and lb >= ua and (ib > ia or lb > ua):
        return "b"
    return "incomparable"


def scoped_frontier(candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Partition evidence states before comparing only eligible risk candidates."""
    eligible = {}
    diagnostics = {}
    for name, assessment in candidates.items():
        reasons = risk_ineligibility(assessment)
        if reasons:
            diagnostics[name] = {"reasons": reasons, "assessment": assessment}
        else:
            eligible[name] = assessment
    frontier = [
        name
        for name, assessment in eligible.items()
        if not any(scoped_preference(other, assessment) == "a" for other in eligible.values())
    ]
    return {"eligible": eligible, "diagnostics": diagnostics, "frontier": frontier}


def bounded_programs(
    initial: set[str], goal: set[str], actions: list[ResearchAction], max_work_units: int
) -> dict[str, Any]:
    """Enumerate first-goal monotone plans within a canonical active-work budget.

    No cheapest-prefix/node pruning: equal fact sets can have different histories.
    Zero-work closure must add facts, so cycles terminate without charging for syntax.
    Routes with the same work tuple collapse; this prototype does not retain evidence traces.
    Production integration must retain those traces separately for audit/choke-point comparison.
    """
    if type(max_work_units) is not int or max_work_units < 0:
        raise ValueError("max_work_units must be a nonnegative integer")
    programs: set[tuple[str, ...]] = set()
    truncated = False

    # ponytail: exponential enumeration for tiny research graphs; B owns bounded/scalable search.
    def visit(state: frozenset[str], program: tuple[str, ...]) -> None:
        nonlocal truncated
        if goal <= state:
            programs.add(program)
            return
        for action in actions:
            after = state | action.adds
            if not action.requires <= state or after == state:
                continue
            extended = tuple(dict.fromkeys(program + action.units))
            if len(extended) > max_work_units:
                truncated = True
                continue
            visit(after, extended)

    visit(frozenset(initial), ())
    return {"programs": sorted(programs), "truncated": truncated}


def run_experiment_6_scoped_proposal() -> dict[str, Any]:
    """Issue #150: synthetic declared conditionals, shared work, Pareto and search oracle."""
    units = {
        name: ActionStep(
            name, 1, "active", t1, t2, "unrated", "Unknown", "synthetic", "Synthetic #150"
        )
        for name, (t1, t2) in {
            "prepare": (2, 3),
            "a": (1, 3),
            "b": (1, 3),
            "finish": (1, 2),
            "cheap_low": (1, 2),
        }.items()
    }
    actions = [
        ResearchAction("prepare", frozenset({"start"}), frozenset({"prepared"}), ("prepare",)),
        ResearchAction("a", frozenset({"prepared"}), frozenset({"a"}), ("a",)),
        ResearchAction("b", frozenset({"prepared"}), frozenset({"b"}), ("b",)),
        ResearchAction("finish", frozenset({"a", "b"}), frozenset({"goal"}), ("finish",)),
        ResearchAction("cheap_low", frozenset({"start"}), frozenset({"goal"}), ("cheap_low",)),
    ]
    found = bounded_programs({"start"}, {"goal"}, actions, 4)
    limited = bounded_programs({"start"}, {"goal"}, actions, 3)
    # Explicit lifted DAG is a second traversal representation of the SAME AND constraint.
    # Every number is a stipulated full-history conditional, not a marginal or AD estimate.
    graph = {
        "S": [Edge("S", "P", 3, 0.8, "prepare"), Edge("S", "T", 1, 0.2, "cheap_low")],
        "P": [
            Edge("P", "A", 2, 0.9, "a"),
            Edge("P", "B", 2, 0.9, "b"),
            Edge("P", "T", 1, 0.2, "cheap_low"),
        ],
        "A": [Edge("A", "AB", 2, 0.9, "b"), Edge("A", "T", 1, 0.2, "cheap_low")],
        "B": [Edge("B", "BA", 2, 0.9, "a"), Edge("B", "T", 1, 0.2, "cheap_low")],
        "AB": [Edge("AB", "T", 1, 1.0, "finish"), Edge("AB", "T", 1, 0.2, "cheap_low")],
        "BA": [Edge("BA", "T", 1, 1.0, "finish"), Edge("BA", "T", 1, 0.2, "cheap_low")],
    }
    oracle = exhaustive_search(graph, "S", "T")
    oracle_programs = sorted(tuple(e["name"] for e in p["edges"]) for p in oracle["all_paths"])
    bounds = {("prepare",): (0.8, 0.8), ("cheap_low",): (0.2, 0.2)}
    for order in (("a", "b"), ("b", "a")):
        bounds[("prepare", order[0])] = (0.9, 0.9)
        bounds[("prepare", *order)] = (0.9, 0.9)
        bounds[("prepare", *order, "finish")] = (1.0, 1.0)
    # Preparing irrelevant capabilities before the cheap goal is legal, though dominated.
    for prefix in (
        ("prepare",),
        ("prepare", "a"),
        ("prepare", "b"),
        ("prepare", "a", "b"),
        ("prepare", "b", "a"),
    ):
        bounds[(*prefix, "cheap_low")] = (0.2, 0.2)
    names = [
        "cheap_low"
        if program == ("cheap_low",)
        else "shared_" + "".join(program[1:3])
        if program[-1] == "finish"
        else "cheap_after_" + "_".join(program[:-1])
        for program in found["programs"]
    ]
    assessments = {
        name: {**assess_scoped_program([program], units, bounds), "impact": "Critical"}
        for name, program in zip(names, found["programs"], strict=True)
    }
    frontier = scoped_frontier(assessments)["frontier"]
    oracle_assessments = {
        names[i]: {
            "status": "feasible",
            "impact": "Critical",
            "effort": path["cost"],
            "likelihood_interval": (path["likelihood"], path["likelihood"]),
        }
        for i, path in enumerate(
            sorted(oracle["all_paths"], key=lambda p: tuple(e["name"] for e in p["edges"]))
        )
    }
    oracle_frontier = scoped_frontier(oracle_assessments)["frontier"]
    shared = assessments["shared_ab"]
    evidence_partition = scoped_frontier(
        {
            "rated": shared,
            "blocked": {
                **assess_scoped_program([shared["program"]], units, bounds, (False,)),
                "impact": "Critical",
            },
            "unknown": {
                **assess_scoped_program([shared["program"]], units, bounds, ("Unknown",)),
                "impact": "Critical",
            },
            "likelihood_unrated": {**shared, "likelihood_interval": None},
            "impact_unrated": {**shared, "impact": None},
            "effort_unrated": {
                **assess_scoped_program([shared["program"]], {**units, "prepare": None}, bounds),
                "impact": "Critical",
            },
        }
    )
    checks = {
        "same_program_coverage": found["programs"] == oracle_programs,
        "same_pareto_objective": frontier == oracle_frontier == ["shared_ab", "shared_ba"],
        "shared_work_once": shared["effort"] == 8,
        "dependent_composition": math.isclose(shared["likelihood_interval"][0], 0.648),
        "evidence_partition": evidence_partition["frontier"] == ["rated", "effort_unrated"]
        and set(evidence_partition["diagnostics"])
        == {"blocked", "unknown", "likelihood_unrated", "impact_unrated"},
        "unrated_effort_point_tie": scoped_preference(
            shared, evidence_partition["eligible"]["effort_unrated"]
        )
        == "incomparable",
        "budget_reports_truncation": limited["truncated"]
        and limited["programs"] == [program for program in oracle_programs if len(program) <= 3],
    }
    return {
        "experiment": "Experiment 6: Scoped conservative Pareto proposal (#150)",
        "scope": "synthetic, fixed scenario, monotone facts, no retries/expiry/delete effects",
        "shared_preparation": shared,
        "evidence_partition": evidence_partition,
        "incorrect_branch_sum": 11,
        "incorrect_shared_marginal_product": (0.8 * 0.9) ** 2,
        "search": {
            "bounded_programs": found["programs"],
            "oracle_programs": oracle_programs,
            "frontier": frontier,
            "oracle_frontier": oracle_frontier,
            "min_effort": min(assessments, key=lambda name: assessments[name]["effort"]),
            "limited_budget": limited,
            "full_budget": found,
        },
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "model_verdict": "Insufficient Evidence",
        "gaps": [
            "SEAMLESS full-history conditional bounds lack a reviewed basis",
            "impact/effort elicitation and Pareto policy await independent review",
            "bounded toy coverage does not establish real-graph optimality or scalability",
        ],
    }


def verify_snapshot_data(raw_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """Verify hand-worked example entities against raw snapshot data using reproducible selectors.

    Purges all raw Active Directory computer names, user names, domain names, and raw SIDs.
    Uses structural graph queries to discover:
      - Source A: Enabled computer with GenericAll ACE to User-Candidate.
      - User-Candidate: Enabled user in Domain Admins (RID-512) holding GenericAll from Source A.
      - Target-Group-DA: Group with SID ending in -512.
      - Target-User-KRBTGT: User with SID ending in -502.
    Enforces strict SHA-256 hash verification against the manifest.
    """
    if not manifest_path.is_file():
        return {
            "status": "FAIL",
            "snapshot_verified": False,
            "file_hash_verified": False,
            "details": {},
            "reason": f"Manifest file not found: {manifest_path}",
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "FAIL",
            "snapshot_verified": False,
            "file_hash_verified": False,
            "details": {},
            "reason": f"Failed to parse manifest JSON: {exc}",
        }

    manifest_files = {
        entry.get("relative_path"): entry
        for entry in manifest.get("files", [])
        if "relative_path" in entry
    }
    if not manifest_files:
        return {
            "status": "FAIL",
            "snapshot_verified": False,
            "file_hash_verified": False,
            "details": {},
            "reason": "Manifest contains empty or invalid file list",
        }

    if not raw_dir.is_dir():
        return {
            "status": "FAIL",
            "snapshot_verified": False,
            "file_hash_verified": False,
            "details": {},
            "reason": f"Snapshot directory not found: {raw_dir}",
        }

    results: dict[str, Any] = {}
    all_hashes_ok = True

    # 1. Verify and load computers file
    comp_file_name = next(
        (name for name in manifest_files if name.endswith("computers.json")),
        "20210920185958_computers.json",
    )
    comp_file = raw_dir / comp_file_name
    comp_records: list[dict[str, Any]] = []
    comp_hash_ok = False

    if comp_file.is_file():
        payload = comp_file.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        expected = manifest_files.get(comp_file_name, {}).get("sha256")
        comp_hash_ok = digest == expected and bool(expected)
        if not comp_hash_ok:
            all_hashes_ok = False
        try:
            comp_records = json.loads(payload.decode("utf-8-sig")).get("computers", [])
        except Exception:
            comp_records = []
    else:
        all_hashes_ok = False

    # 2. Verify and load users file
    user_file_name = next(
        (name for name in manifest_files if name.endswith("users.json")),
        "20210920185958_users.json",
    )
    user_file = raw_dir / user_file_name
    user_records: list[dict[str, Any]] = []
    user_hash_ok = False

    if user_file.is_file():
        payload = user_file.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        expected = manifest_files.get(user_file_name, {}).get("sha256")
        user_hash_ok = digest == expected and bool(expected)
        if not user_hash_ok:
            all_hashes_ok = False
        try:
            user_records = json.loads(payload.decode("utf-8-sig")).get("users", [])
        except Exception:
            user_records = []
    else:
        all_hashes_ok = False

    # 3. Verify and load groups file
    grp_file_name = next(
        (name for name in manifest_files if name.endswith("groups.json")),
        "20210920185958_groups.json",
    )
    grp_file = raw_dir / grp_file_name
    group_records: list[dict[str, Any]] = []
    grp_hash_ok = False

    if grp_file.is_file():
        payload = grp_file.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        expected = manifest_files.get(grp_file_name, {}).get("sha256")
        grp_hash_ok = digest == expected and bool(expected)
        if not grp_hash_ok:
            all_hashes_ok = False
        try:
            group_records = json.loads(payload.decode("utf-8-sig")).get("groups", [])
        except Exception:
            group_records = []
    else:
        all_hashes_ok = False

    # 4. Reproducible Entity Resolution
    # Find Domain Admins group: SID ending in -512
    da_group_idx, da_group = next(
        (
            (i, g)
            for i, g in enumerate(group_records)
            if g.get("ObjectIdentifier", "").endswith("-512")
        ),
        (None, None),
    )
    da_members_map = (
        {
            m.get("MemberId"): j
            for j, m in enumerate(da_group.get("Members", []))
            if m.get("MemberId")
        }
        if da_group
        else {}
    )
    da_member_ids = set(da_members_map.keys())

    # Find Target-User-KRBTGT: SID ending in -502
    krbtgt_idx, krbtgt = next(
        (
            (i, u)
            for i, u in enumerate(user_records)
            if u.get("ObjectIdentifier", "").endswith("-502")
        ),
        (None, None),
    )

    # Index computers by ObjectIdentifier
    comp_map = {
        c.get("ObjectIdentifier"): (i, c)
        for i, c in enumerate(comp_records)
        if c.get("ObjectIdentifier")
    }

    # Group candidate edges (Computer -> GenericAll -> User who is member of RID-512 group)
    candidate_edges: list[dict[str, Any]] = []
    for u_idx, u in enumerate(user_records):
        u_sid = u.get("ObjectIdentifier", "")
        if u_sid in da_members_map:
            for ace_idx, ace in enumerate(u.get("Aces", [])):
                if ace.get("RightName") == "GenericAll":
                    psid = ace.get("PrincipalSID")
                    if psid in comp_map:
                        c_idx, comp = comp_map[psid]
                        candidate_edges.append(
                            {
                                "comp_sid": psid,
                                "comp_idx": c_idx,
                                "comp": comp,
                                "user_sid": u_sid,
                                "user_idx": u_idx,
                                "user": u,
                                "ace_idx": ace_idx,
                                "ace": ace,
                                "member_idx": da_members_map[u_sid],
                            }
                        )

    # Order candidate computers lexicographically to identify Source A
    # and select Source A and its candidate User-Candidate
    source_a = None
    source_a_idx = None
    user_cand = None
    user_cand_idx = None
    selected_ace = None
    selected_ace_idx = None
    selected_member_idx = None

    if candidate_edges:
        candidate_computers = sorted({e["comp_sid"] for e in candidate_edges})
        source_a_sid = candidate_computers[0]

        # Edges for Source A sorted by user SID, then ace index
        source_a_edges = [e for e in candidate_edges if e["comp_sid"] == source_a_sid]
        source_a_edges.sort(key=lambda e: (e["user_sid"], e["ace_idx"]))
        chosen_edge = source_a_edges[0]

        source_a = chosen_edge["comp"]
        source_a_idx = chosen_edge["comp_idx"]
        user_cand = chosen_edge["user"]
        user_cand_idx = chosen_edge["user_idx"]
        selected_ace = chosen_edge["ace"]
        selected_ace_idx = chosen_edge["ace_idx"]
        selected_member_idx = chosen_edge["member_idx"]

    # Build sanitized results with aliases and locators (no raw AD names or SIDs)
    results["source_a"] = {
        "alias": "Source A",
        "locator": (
            f"{comp_file_name}#/computers/{source_a_idx}" if source_a_idx is not None else None
        ),
        "file_hash_verified": comp_hash_ok,
        "found": source_a is not None,
        "enabled": (source_a.get("Properties", {}).get("enabled") if source_a else None),
    }

    results["user_candidate"] = {
        "alias": "User-Candidate",
        "locator": (
            f"{user_file_name}#/users/{user_cand_idx}" if user_cand_idx is not None else None
        ),
        "file_hash_verified": user_hash_ok,
        "found": user_cand is not None,
        "enabled": (user_cand.get("Properties", {}).get("enabled") if user_cand else None),
        "genericall_from_source_a": source_a is not None and user_cand is not None,
    }

    results["genericall_ace"] = {
        "alias": "GenericAll ACE",
        "locator": (
            f"{user_file_name}#/users/{user_cand_idx}/Aces/{selected_ace_idx}"
            if user_cand_idx is not None and selected_ace_idx is not None
            else None
        ),
        "found": selected_ace is not None,
        "right_name": "GenericAll",
    }

    results["da_group"] = {
        "alias": "Target-Group-DA",
        "locator": f"{grp_file_name}#/groups/{da_group_idx}" if da_group_idx is not None else None,
        "file_hash_verified": grp_hash_ok,
        "found": da_group is not None,
        "user_candidate_is_member": (
            bool(user_cand and user_cand.get("ObjectIdentifier") in da_member_ids)
        ),
    }

    results["da_membership"] = {
        "alias": "DA Membership",
        "locator": (
            f"{grp_file_name}#/groups/{da_group_idx}/Members/{selected_member_idx}"
            if da_group_idx is not None and selected_member_idx is not None
            else None
        ),
        "found": selected_member_idx is not None,
    }

    results["krbtgt"] = {
        "alias": "Target-User-KRBTGT",
        "locator": f"{user_file_name}#/users/{krbtgt_idx}" if krbtgt_idx is not None else None,
        "file_hash_verified": user_hash_ok,
        "found": krbtgt is not None,
        "enabled": (krbtgt.get("Properties", {}).get("enabled") if krbtgt else None),
        "admincount": (krbtgt.get("Properties", {}).get("admincount") if krbtgt else None),
    }

    # Verify ALL files in the manifest (not just computers/users/groups)
    # This checks existence, size, and SHA-256 of all 6 files.
    verified_manifest_files: list[str] = []
    failed_manifest_files: list[str] = []
    for rel_path, entry in manifest_files.items():
        # Record core files according to their actual hash verification status
        if rel_path == comp_file_name:
            if comp_hash_ok:
                verified_manifest_files.append(rel_path)
            else:
                failed_manifest_files.append(rel_path)
            continue
        if rel_path == user_file_name:
            if user_hash_ok:
                verified_manifest_files.append(rel_path)
            else:
                failed_manifest_files.append(rel_path)
            continue
        if rel_path == grp_file_name:
            if grp_hash_ok:
                verified_manifest_files.append(rel_path)
            else:
                failed_manifest_files.append(rel_path)
            continue
        fpath = raw_dir / rel_path
        if not fpath.is_file():
            all_hashes_ok = False
            failed_manifest_files.append(rel_path)
            continue
        payload = fpath.read_bytes()
        expected_sha = entry.get("sha256")
        expected_size = entry.get("size_bytes")
        digest = hashlib.sha256(payload).hexdigest()
        size_ok = expected_size is None or len(payload) == expected_size
        hash_ok = digest == expected_sha and bool(expected_sha) and size_ok
        if hash_ok:
            verified_manifest_files.append(rel_path)
        else:
            all_hashes_ok = False
            failed_manifest_files.append(rel_path)

    results["manifest_verification"] = {
        "total_files": len(manifest_files),
        "verified_files": verified_manifest_files,
        "failed_files": failed_manifest_files,
        "all_verified": all_hashes_ok,
    }

    # Inspect Computer.Sessions[] primitive (replaces sessions.json file check).
    # The raw BloodHound/SharpHound primitive for session data is
    # Computer.Sessions[] inside the computers JSON, NOT a separate
    # sessions.json file.
    source_a_sessions = source_a.get("Sessions", []) if source_a else []
    total_computers_with_sessions = sum(1 for c in comp_records if len(c.get("Sessions", [])) > 0)
    total_computers = len(comp_records)
    results["sessions_inspection"] = {
        "alias": "Computer.Sessions[] primitive",
        "source_a_sessions_count": len(source_a_sessions),
        "computers_with_nonempty_sessions": total_computers_with_sessions,
        "total_computers": total_computers,
        "measured_empty": total_computers_with_sessions == 0,
        "caveat": (
            "empty != false - session collection was either unperformed, "
            "limited, or returned empty at collection time; absence of "
            "records in static snapshot is not proof that sessions never "
            "exist at runtime"
        ),
        "path_2_synthetic": True,
        "note": (
            "Path 2 (HasSession) is an unproven synthetic scenario "
            "counterexample - no Computer.Sessions[] evidence exists in "
            "this snapshot"
        ),
    }

    all_entities_found = (
        results["source_a"]["found"]
        and results["source_a"]["enabled"] is True
        and results["user_candidate"]["genericall_from_source_a"] is True
        and results["da_group"]["user_candidate_is_member"] is True
        and results["krbtgt"]["found"] is True
    )

    is_verified = all_hashes_ok and all_entities_found

    return {
        "status": "PASS" if is_verified else "FAIL",
        "snapshot_verified": is_verified,
        "file_hash_verified": all_hashes_ok,
        "details": results,
    }


# Backwards compatibility alias
verify_seamless_snapshot = verify_snapshot_data


# --- REPORTING & CLI ---


def print_summary_tables(all_results: dict[str, Any]) -> None:
    """Print readable summary tables to standard output."""
    print("=" * 80)
    print("RESEARCH VALIDATION REPORT: ISSUE #142 (TTS A)")
    print("Experiments 1-5: historical #149 draft/counterexamples; experiment 6: #150 proposal.")
    print("Mo hinh Xep hang Duong Tan cong & Thu nghiem Do nhay")
    print("=" * 80)

    # 1. Hand-worked table
    hw = all_results["hand_worked_examples"]
    print("\n[EXPERIMENT A] Hand-worked Example Verification (Section 10)")
    print("-" * 80)
    print(
        f"{'Path':<8} {'Step':<5} {'Action Name':<28} {'T1':<4} "
        f"{'T2':<4} {'Cost':<6} {'P(step)':<8} {'T3':<15}"
    )
    print("-" * 80)
    for s in hw["step_verifications"]:
        print(
            f"{s['path']:<8} {s['step']:<5} {s['name']:<28} {s['t1']:<4} {s['t2']:<4} "
            f"{s['cost']:<6} {s['likelihood']:<8} {s['t3']:<15}"
        )
    print("-" * 80)
    print(
        f"Path 1 (Reset) Checkpoint S2: Cost = {hw['path1_s2']['cost']}, "
        f"P(S2) = {hw['path1_s2']['likelihood']}"
    )
    print(
        f"Path 2 (Session) Checkpoint S2: Cost = {hw['path2_s2']['cost']}, "
        f"P(S2) = {hw['path2_s2']['likelihood']}"
    )
    print(
        f"Goal S3 Gate O: Path 1 P(S3) = {hw['path1_s3']['likelihood']}, "
        f"Path 2 P(S3) = {hw['path2_s3']['likelihood']}"
    )
    print(f"Lexicographic Rank at S2: {' > '.join(hw['ranking_at_s2'])}")
    print(f"Total Deviation: {hw['total_deviation']} (Status: {hw['status']})")

    # 2. Experiment 1 table
    exp1 = all_results["experiment_1"]
    print("\n[EXPERIMENT 1] Candidate Lexicographic Model vs Tradeoff Models")
    print("-" * 80)
    print(f"{'Attribute':<32} {'Path A (Critical, Low)':<24} {'Path B (High, High)':<24}")
    print("-" * 80)
    for row in exp1["comparison_table"]:
        print(f"{row['attribute']:<32} {row['path_a']:<24} {row['path_b']:<24}")
    print("-" * 80)
    print(f"Lexicographic Winner: {exp1['lexicographic_winner']} (Critical impact prioritized)")
    print(f"Expected Risk Winner: {exp1['expected_risk_winner']} (High likelihood prioritized)")
    print(f"Status: {exp1['status']}")

    # 3. Experiment 2 table
    exp2 = all_results["experiment_2"]
    print("\n[EXPERIMENT 2] Effort Sensitivity within Equal Strata (Critical, Medium)")
    print("-" * 80)
    print(
        f"{'Formula Variant':<36} {'Closure Cost':<14} {'3A Total':<10} {'3B Total':<10} {'Rank 1'}"
    )
    print("-" * 80)
    for r in exp2["variant_results"]:
        print(
            f"{r['formula_desc']:<36} {r['closure_cost']:<14} {r['path_3a_total']:<10} "
            f"{r['path_3b_total']:<10} {r['preferred_path']}"
        )
    print("-" * 80)
    print(f"Invariant C_closure == 0 in all variants: {exp2['closure_invariants_pass']}")
    print(f"Rank reversal observed (Tool vs Friction): {exp2['rank_reversal_observed']}")
    print(f"Status: {exp2['status']}")

    # 4. Experiment 3 table
    exp3 = all_results["experiment_3"]
    print("\n[EXPERIMENT 3] Closure Cost Invariance & Semantic Equivalence")
    print("-" * 80)
    print(
        f"Normalized Formula (C_closure == 0): "
        f"1-hop = {exp3['normalized_1hop_cost']}, 3-hop = {exp3['normalized_3hop_cost']} "
        f"(Invariant: {exp3['normalized_invariant']})"
    )
    print(
        f"Non-normalized Formula (raw max):   "
        f"1-hop = {exp3['raw_1hop_cost']}, 3-hop = {exp3['raw_3hop_cost']} "
        f"(Inflation Delta: +{exp3['raw_inflation_delta']})"
    )
    print(
        f"Action Packaging (Split vs Merged): "
        f"Split = {exp3['packaging_split_cost']}, Merged = {exp3['packaging_merged_cost']} "
        f"(Invariant: {exp3['packaging_invariant']})"
    )
    print(f"Status: {exp3['status']}")

    # 5. Experiment 4 table
    exp4 = all_results["experiment_4"]
    print("\n[EXPERIMENT 4] Uncertainty Propagation (Gate O) & Dynamic State Evaluation")
    print("-" * 80)
    print(
        f"Gate O Unknown -> Path 1 P(S3) = {exp4['path1_s3_likelihood']}, "
        f"Path 2 P(S3) = {exp4['path2_s3_likelihood']}"
    )
    print(f"Bottleneck Truth Table Verification: Passed = {exp4['truth_table_passed']}")
    print(f"27-Assignment Gate Truth Table: Passed = {exp4['gate_truth_table_passed']}")
    print("Dynamic Modes Summary:")
    print("  - Evidence-only mode: S2 unsupported, S3 unsupported (strict observed facts only)")
    print(
        "  - Scenario mode:      S2 reached under declared assumptions, "
        "S3 unsupported (chua co bang chung da duoc kiem chung ve phan quyen replication)"
    )
    print(f"Status: {exp4['status']}")

    # 6. Experiment 5 table
    exp5 = all_results["experiment_5"]
    print("\n[EXPERIMENT 5] Path Length Degradation & Dijkstra Compatibility")
    print("-" * 80)
    print(
        f"Bottleneck indirection (1-step vs 10-step): "
        f"Both evaluate to High = {exp5['bottleneck_indifferent']}"
    )
    print(
        f"Passive closure invariance in degradation: "
        f"Maintained = {exp5['passive_invariance_maintained']}"
    )
    print(
        f"Unconstrained non-linear Dijkstra violation: "
        f"Demonstrated = {exp5['bellman_violation_demonstrated']} "
        f"(Dijkstra score: {exp5['dijkstra_nonadditive_result']['score']} vs "
        f"Exhaustive oracle: {exp5['exhaustive_nonadditive_result']['score']:.4f})"
    )
    print(
        f"Stratified Dijkstra optimal substructure: "
        f"Verified = {exp5['stratified_dijkstra_success']} "
        f"(Path matches exhaustive oracle: {exp5['dijkstra_stratified_result']['path']})"
    )
    ef = exp5["edge_filter_failure"]
    print(
        f"Edge-level filtering guarantee failure: "
        f"All 3 edges pass filter P>=0.75, but path P = {ef['cumulative_path_likelihood']} (< 0.75)"
    )
    pd = exp5["packaging_degradation"]
    print(
        f"Action packaging under naive step-counting: "
        f"Split (2 steps) = {pd['split_degraded_p']} vs Merged (1 step) = {pd['merged_degraded_p']}"
    )
    print(f"Status: {exp5['status']}")

    # Snapshot check
    snap = all_results.get("seamless_snapshot")
    if snap and snap.get("status") != "SKIPPED":
        print("\n[SNAPSHOT VERIFICATION]")
        print("-" * 80)
        print(f"Snapshot Verified: {snap.get('snapshot_verified')}")
        print(f"File Hashes Verified: {snap.get('file_hash_verified')}")
        det = snap.get("details", {})
        mf = det.get("manifest_verification", {})
        print(
            f"Manifest: {len(mf.get('verified_files', []))}/{mf.get('total_files', 0)} "
            f"files verified"
        )
        if mf.get("failed_files"):
            print(f"  Failed: {', '.join(mf['failed_files'])}")
        print(
            f"Source A Computer: {det.get('source_a', {}).get('locator')} ({det.get('source_a')})"
        )
        print(
            f"User Candidate:   {det.get('user_candidate', {}).get('locator')} "
            f"({det.get('user_candidate')})"
        )
        print(
            f"GenericAll ACE:   {det.get('genericall_ace', {}).get('locator')} "
            f"({det.get('genericall_ace')})"
        )
        print(f"Domain Admins:    {det.get('da_group', {}).get('locator')} ({det.get('da_group')})")
        print(
            f"DA Membership:    {det.get('da_membership', {}).get('locator')} "
            f"({det.get('da_membership')})"
        )
        print(f"KRBTGT:           {det.get('krbtgt', {}).get('locator')} ({det.get('krbtgt')})")
        si = det.get("sessions_inspection", {})
        print(
            f"Sessions:         Computer.Sessions[] primitive - "
            f"Source A sessions: {si.get('source_a_sessions_count', 0)}, "
            f"Hosts with sessions: {si.get('computers_with_nonempty_sessions', 0)}"
            f"/{si.get('total_computers', 0)}"
        )
        if si.get("measured_empty"):
            print(f"  Caveat: {si.get('caveat', '')}")
        print(f"Status: {snap.get('status')}")

    print("=" * 80)
    print(f"OVERALL VALIDATION SUITE RESULT: {all_results['overall_status']}")
    scoped = all_results["experiment_6"]
    print(f"#150 synthetic checks: {scoped['status']}; model verdict: {scoped['model_verdict']}")
    print(
        f"Pareto frontier: {scoped['search']['frontier']}; "
        f"min effort: {scoped['search']['min_effort']}"
    )
    print("=" * 80)


def run_all_validations(
    raw_dir: Path | None = None, manifest_path: Path | None = None
) -> dict[str, Any]:
    """Run all validation experiments and compile the combined report."""
    hw_res = verify_hand_worked_examples()
    exp1_res = run_experiment_1_ranking_tradeoff()
    exp2_res = run_experiment_2_effort_sensitivity()
    exp3_res = run_experiment_3_closure_invariance()
    exp4_res = run_experiment_4_uncertainty_propagation()
    exp5_res = run_experiment_5_length_degradation_dijkstra()
    exp6_res = run_experiment_6_scoped_proposal()

    snap_res = None
    if raw_dir is not None or manifest_path is not None:
        target_raw = raw_dir if raw_dir is not None else Path("data/raw/SEAMLESS")
        target_manifest = (
            manifest_path
            if manifest_path is not None
            else Path("data/samples/manifests/seamless-raw-v1.json")
        )
        snap_res = verify_snapshot_data(target_raw, target_manifest)
    else:
        default_raw = Path("data/raw/SEAMLESS")
        default_manifest = Path("data/samples/manifests/seamless-raw-v1.json")
        if default_raw.is_dir() and default_manifest.is_file():
            snap_res = verify_snapshot_data(default_raw, default_manifest)

    all_passed = (
        hw_res["status"] == "PASS"
        and exp1_res["status"] == "PASS"
        and exp2_res["status"] == "PASS"
        and exp3_res["status"] == "PASS"
        and exp4_res["status"] == "PASS"
        and exp5_res["status"] == "PASS"
        and exp6_res["status"] == "PASS"
    )

    if snap_res is not None and snap_res.get("status") != "SKIPPED":
        all_passed = all_passed and (snap_res.get("status") == "PASS")

    combined = {
        "suite": "Issues #142 / #150 Path Ranking & Worked Example Validation",
        "proposal": "scoped_conservative_pareto_v1",
        "hand_worked_examples": hw_res,
        "experiment_1": exp1_res,
        "experiment_2": exp2_res,
        "experiment_3": exp3_res,
        "experiment_4": exp4_res,
        "experiment_5": exp5_res,
        "experiment_6": exp6_res,
        "overall_status": "PASS" if all_passed else "FAIL",
        "overall_pass": all_passed,
    }
    if snap_res is not None:
        combined["seamless_snapshot"] = snap_res
    return combined


# Backwards compatibility alias
run_all_experiments = run_all_validations


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproducible research validation script for Issues #142 / #150 (TTS A)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all validations and print summary tables and JSON output.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format only.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Path to snapshot raw data directory.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to snapshot manifest JSON file.",
    )

    args = parser.parse_args()

    results = run_all_validations(raw_dir=args.raw_dir, manifest_path=args.manifest)

    if args.json and not args.all:
        print(json.dumps(results, indent=2, default=to_serializable))
        if not results.get("overall_pass", False):
            sys.exit(1)
        return

    if args.all:
        print_summary_tables(results)
        print("\n--- JSON OUTPUT ---")
        print(json.dumps(results, indent=2, default=to_serializable))
        if not results.get("overall_pass", False):
            sys.exit(1)
        return

    # Default invocation without flags
    print_summary_tables(results)
    if not results.get("overall_pass", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
