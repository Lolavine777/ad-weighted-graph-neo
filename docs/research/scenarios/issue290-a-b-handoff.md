# Issue #290: SEAMLESS Scenario Assumption Profile A/B Handoff Specification

- Author: TTS A (@Lolavine777)
- Reviewer: TTS B
- Date: 2026-10-14
- Bound Snapshot ID: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`
- Profile Schema: `docs/research/scenarios/seamless-policy.schema.json`
- Profile Definition: `docs/research/scenarios/seamless-policy-profile-v1.json`

## 1. Executive Summary and Deliverables

TTS A has completed the core deliverables for Issue #290 (SEAMLESS-wide Scenario Assumption Profile).
This specification replaces fragile, per-query hand-crafted assumptions with an auditable, versioned policy profile.
It establishes clear semantic boundaries across the 44 Active Directory runtime predicates in SEAMLESS.
The implementation guarantees that unrated environment assumptions do not fabricate edges or attacker capabilities.

| Deliverable | Location | Description |
| :--- | :--- | :--- |
| Core Engine Module | `src/engine/semantics/scenario_policy.py` | Profile dataclasses, rule taxonomy, resolver, on-demand cache, and query compiler |
| Policy JSON Profile | `docs/research/scenarios/seamless-policy-profile-v1.json` | Versioned SEAMLESS standard profile specification |
| Draft 2020-12 Schema | `docs/research/scenarios/seamless-policy.schema.json` | JSON Schema validating policy profiles and overrides |
| Prerequisites Audit | `docs/research/scenarios/seamless-prerequisites-audit.md` | Full 44-predicate matrix and four deep dives |
| Machine-readable Audit | `reports/research/seamless-prerequisites-audit.json` | Categorized audit report with rationale and failure modes |
| Comprehensive Test Suite | `tests/test_scenario_policy.py` | 20 independent unit and integration test oracles |
| Native Acceptance Runner | `scripts/research/seamless_policy_acceptance.py` | Funnel benchmark across C0, KERBEROAST-SPN, GINO, and BORIS-DISTLIST |
| Acceptance Summary | `reports/research/issue290-seamless-policy-summary.json` | Sanitized coverage funnel report across evaluation modes |

## 2. Shared Invariants and Non-Negotiable Boundaries

Both TTS A and TTS B must preserve the following architectural invariants without exception:

1. Never turn all Unknown facts into True blindly.
Unverifiable conditions not covered by a declared policy rule must remain indeterminate.

2. Never invent structural edges or permissions.
The canonical graph topology is immutable; scenario policy conditions only operational environment reachability.

3. Never grant attacker capabilities by policy assumption.
Capabilities (`control`, `usable_identity`, `admin_control`) originate strictly from declared footholds or valid action effects.
Overrides attempting to assert capabilities directly are rejected with `override_violates_non_negotiable_security_boundary`.

4. Authoritative False in snapshot facts or context always vetoes any assumption.
When authoritative negative evidence exists, the assumption is rejected with `known_false_veto` and the state evaluates to `blocked`.

5. Successful assumptions never imply probability P=1.
All assumption-backed paths must retain explicit unrated scoring until governed by an adopted rating basis.

6. Groups with distribution list naming or non-security groupType cannot default to security groups.
Presence of `groupType` is not proof of a security-enabled group because distribution groups also carry `groupType` attributes.
The engine decodes the Active Directory `groupType` 32-bit bitmask (`ADS_GROUP_TYPE_SECURITY_ENABLED = 0x80000000`).
If the security bit is absent or negative, DACL rights propagation along `MemberOf` and `GenericAll` is blocked unless an explicit `distribution_group_override` is declared.

7. Offline password recovery requires explicit user opt-in.
Predicate `recovery_success` cannot default to True in standard mode.
It is evaluated only in exploratory what-if mode with an explicit `recovery_opt_in` override specifying target, method, and budget.

## 3. Public Integration API Contract for TTS B

### 3.1 Resolving Policy Assumptions

The primary resolver entry point is `resolve_scenario_policy`.
It evaluates a query against a graph and produces a structured result containing applied facts and rejection audit records.

```python
from src.engine.semantics.scenario_policy import (
    PolicyOverride,
    load_policy_profile,
    resolve_scenario_policy,
)

resolution = resolve_scenario_policy(
    graph=engine_graph,
    query=attack_query,
    profile="exploratory_what_if",  # recovery_success requires exploratory what-if mode
    overrides=[
        PolicyOverride(
            predicate="recovery_success",
            subject="COMP-WS1",
            target="USER-GINO",
            value=True,
            override_type="recovery_opt_in",
            rationale="Offline dictionary attack with 48h GPU budget",
            metadata={
                "method": "offline-password-prediction",
                "budget": "48h-gpu",
                "horizon": "48h-gpu",
            },
        )
    ],
    enforce_snapshot_binding=True,
)

# Access resolution details
print(f"Assumptions generated: {len(resolution.assumptions)}")
print(f"Rejected assumptions: {len(resolution.rejected_assumptions)}")
print(f"Overrides applied: {len(resolution.applied_overrides)}")
```

### 3.2 Compiling Policy Assumptions into Queries

To integrate seamlessly with `materialize_query`, use `apply_policy_to_query`.
This helper compiles policy assumptions directly into the query dictionary.

```python
from src.engine.query import materialize_query
from src.engine.semantics.scenario_policy import apply_policy_to_query

# 1. Transform raw query dict with scenario policy
compiled_query = apply_policy_to_query(
    query=raw_query_dict,
    graph=engine_graph,
    profile="seamless_standard_scenario",
    overrides=user_overrides,
)

# 2. Materialize query using existing engine API
materialized = materialize_query(compiled_query, graph=engine_graph)

# 3. Execute search
search_result = materialized.search(engine_graph)
```

The compiled query contains `scenario_policy_metadata` with audit records, profile digest, and rejected assumption reasons.

### 3.3 On-Demand Assumption Evaluation (`PolicyAssumptionResolver`)

For high-fanout scenarios (such as `GINO_ROSS` expanding through `DOMAIN USERS`), pre-materializing all candidate assumptions can serialize tens of thousands of facts into the query dictionary.
To keep memory and serialization overhead strictly bounded, TTS B can consume `PolicyAssumptionResolver`.
`PolicyAssumptionResolver` implements `Mapping[tuple[str, str, str], RuntimeFact]` with a bounded LRU cache.
It evaluates policy rules on demand only for edges and facts queried during traversal:

```python
from src.engine.semantics.scenario_policy import (
    PolicyAssumptionResolver,
    load_policy_profile,
)

profile = load_policy_profile("seamless_standard_scenario")
resolver = PolicyAssumptionResolver(
    graph=engine_graph,
    profile=profile,
    overrides=user_overrides,
    max_cache_size=2000,
)

# On-demand lookup during search traversal:
fact = resolver.get(("security_group", "", group_node_id))
```

The resolver enforces the same snapshot bindings, authoritative vetoes, and Active Directory `groupType` bitmask decodings as the batch compiler.

## 4. Subsystem Integration Guidance for TTS B

### 4.1 Query CLI Integration (`src/engine/cli.py` or `scripts/research/query_cli.py`)

1. Add CLI flag `--scenario-profile`:
Accepts standard names (`seamless-standard-v1`, `standard`, `exploratory_what_if`, `evidence_only`) or a path to a profile JSON file.
Public and default behavior remains `evidence_only` unless the caller explicitly selects a scenario profile.
When running in `evidence_only` (the public default), search runs with strictly zero external assumptions.
A demo preset (e.g. `--demo` or `--preset demo-standard`) may explicitly select `seamless_standard_scenario` and must prominently display that active assumption-backed mode.

2. Add CLI flag `--scenario-override`:
Accepts repeatable arguments formatted as `<predicate>:<subject>:<target>=<bool>:<override_type>:<rationale>`.
Example: `--scenario-override recovery_success:WS01:GINO=true:recovery_opt_in:"48h cracking budget"`.

3. Call `apply_policy_to_query` prior to invoking `materialize_query`.
Ensure `--debug` outputs `scenario_policy_metadata` and lists any rejected assumptions.

### 4.2 Batch Engine Integration (`scripts/research/source_goal_batch.py`)

1. Support `scenario_profile` in `BatchQueryRequest`:
Allow callers to configure the profile at batch level or per source profile.
Public and default behavior remains `evidence_only` unless the caller explicitly selects a scenario profile.

2. Enforce snapshot binding once per batch execution:
Verify that `bound_snapshot_id` matches the batch graph snapshot.

3. Separate search fan-out from proven absence of path:
For sources like `GINO_ROSS` where search hits `expansion_limit_reached` due to `DOMAIN USERS` fan-out, record the disposition as `incomplete_search_truncated` or `search_fanout_blocker`.
Do not record it as `proven_no_path`.

### 4.3 Interactive Viewer UI Integration

1. Policy Profile Indicator:
Display the active policy profile (`evidence_only` by default, or opt-in `seamless_standard_scenario` / `exploratory_what_if`) with its cryptographic digest badge in the viewer header.
Public default is `evidence_only` with zero external assumptions.
A demo preset may explicitly select Standard Scenario and must clearly display that active assumption-backed mode.

2. Live Profile Switching:
Allow users to switch profiles via a dropdown.
Switching profiles recompiles assumptions and triggers a live rerun without reloading the raw graph.

3. Policy Audit and Rejection Drawer:
Provide a collapsible drawer displaying:
- Applied assumptions categorized by rule taxonomy (global, typed, specific).
- Rejected assumptions with explicit reasons (e.g. `distribution_group_cannot_default`, `known_false_veto`).
- Applied overrides and their rationale.

4. Explicit Opt-In Modal:
When a path halts at `recover_*_secret` or encounters a distribution list, present an interactive modal for explicit user opt-in.
The modal prompts for cracking method and time budget, then injects a scoped `PolicyOverride` into `exploratory_what_if` mode.

## 5. Summary of Acceptance Results for Handoff

The native SEAMLESS acceptance run (`reports/research/issue290-seamless-policy-summary.json`) verified the following metrics across 4 representative sources:

| Source | Role | Raw (Evidence Only) | Standard Scenario | Exploratory What-If | Blocker / Truncation Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SRC-C0-ASREP` | Computer X Foothold -> AS-REP Target (C0) | Indeterminate (0 paths) | Indeterminate (0 paths) | Feasible (1 path) | Standard halts at `recovery_success`; What-if succeeds with opt-in |
| `SRC-KERBEROAST-SPN` | Computer X Foothold -> JEANNE_YANG SPN Candidate -> Usable Identity | Indeterminate (0 paths) | Indeterminate (0 paths) | Feasible (1 path) | Standard halts at `recovery_success`; What-if succeeds with opt-in |
| `SRC-GINO-FANOUT` | GINO_ROSS Foothold -> Domain Users Search Fan-out -> Target C0 | Indeterminate (0 paths) | Truncated (5000 expansions) | Truncated (5000 expansions) | Hits expansion limit at `DOMAIN USERS`; reported as search blocker |
| `SRC-BORIS-DISTLIST` | BORIS_DILLARD Foothold -> HO-170-DISTLIST1 Direct Member | Indeterminate (0 paths) | Indeterminate (0 paths) | Feasible (1 path) | Standard blocked by `distribution_group_cannot_default`; What-if succeeds with override |

TTS B can proceed with query CLI, batch runner, and interactive viewer integration with confidence that the semantics layer is robust, tested, and contract-compliant.
