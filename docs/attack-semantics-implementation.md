# Attack Semantics implementation

Refs [issue #63](https://github.com/nairyuuu/ad-weighted-graph/issues/63).
Authority: [ADR-0008](adr/ADR-0008-structural-graph-attack-semantics-layering.md),
[research #58](research/attack-semantics.md), [ADR-0007](adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md),
[M1 contract](../configs/contract.yml), and existing tests. Catalog version: `0.2`.

## Architecture and public API

`configs/attack_semantics.yml` contains ten representative techniques covering all
eight M1 relationships. Frozen `Technique` and `ExpectedTelemetry` records are loaded
by `load_catalog(path=None)`. `validate_catalog(mapping)` rejects missing/extra fields,
unknown vocabulary, incompatible effects/targets, omitted safety predicates, malformed
telemetry, duplicate IDs and incomplete M1 coverage. Both return a tuple sorted by ID.
The catalog uses the existing PyYAML dependency and standard-library types.

`candidates(relationship, source_kind, target_kind, catalog=None)` returns compatible
techniques in ID order. It does not select one automatically.

`evaluate(graph, state, request, context, catalog=None)` reads a normalized,
contract-validated parser graph. Call the existing `validate_graph` at the ingestion
boundary; evaluation does not repeatedly validate canonical IDs and provenance.
`TransitionRequest(technique_id, actor, source, target)` selects a specific relationship
and technique. The relationship kind comes from the technique. Together source, target
and kind uniquely identify an M1 edge by the contract's canonical edge ID rule, including
parallel relationships. The same tuple can select an explicitly derived relationship.
An inherited permission retains the controlled actor separately from the source group.

`TransitionResult` contains the request, complete technique metadata, before-state,
additions, failed predicates, unknown predicates and one of:

| Status | Meaning |
| --- | --- |
| `applicable` | All modeled prerequisites hold; additions describe a hypothetical action result |
| `blocked` | At least one modeled prerequisite is false; no additions |
| `indeterminate` | No false prerequisite, but some are unknown; no additions |

Neither `blocked` nor `indeterminate` is a statement about historical attack occurrence.
`apply_transition(state, result)` explicitly unions applicable additions into a new
immutable state. Applying against a different before-state raises `ValueError`.
Blocked/indeterminate results return the input state. Unknown technique IDs raise
`ValueError`; missing graph endpoints, relationships or incompatible kinds are blocked.

`propagate_membership(graph, state, context, catalog=None)` returns `MembershipResult`
with the resulting state and deterministic transition diagnostics. It follows only
MemberOf edges, keeps a visited actor/relationship set, and terminates on cycles,
diamonds and self-loops. It does not acquire control of a group. It can use derived
membership only after explicit `membership_usable` evidence (including token refresh).

## State vocabulary and lifetime

`AttackState` has nine independent immutable sets:

| Field | Representation |
| --- | --- |
| `control` | Principal IDs explicitly supplied as initial control |
| `effective_member` | `(principal, group)` pairs |
| `permission` | Derived `StructuralRelationship(source, kind, target)` values |
| `admin_control` | Computer IDs |
| `interactive_session` | `(principal, computer)` pairs |
| `remote_command_execution` | `(principal, computer)` pairs |
| `credential_material` | User IDs |
| `authentication_control` | User IDs |
| `relationship_added` | Derived `StructuralRelationship(source, kind, target)` values |

`StructuralRelationship` is a relationship key, not a replacement canonical edge
record or evidence of an observed event. Placement in `relationship_added` marks it
as hypothetical/derived. DACL effects also add usable `permission` keys. They never
modify snapshot edges or manufacture provenance.

State is one modeled scenario for one validated snapshot and evaluation time window.
Callers own this scope and must rebuild state/context when it changes; there is no
cross-snapshot merge or automatic expiration/revocation service. The model is additive
within that scope, not a production simulator of account/session lifecycle.
Authentication control and credential material do not implicitly become `control`.
Identity/Asset ontology materialization from #62 remains independent.

## Runtime predicates

`RuntimeContext(facts)` copies a mapping from `(predicate, subject, target)` to strict
booleans. For `session_fresh`, `session_present` and `credential_accessible`, subject
is the source computer and target is the session user. These facts cannot be reused
across source hosts, and actor-scoped facts do not provide a fallback. Other external
predicates use the actor as subject. Missing entries mean unknown.
For nested membership, actor remains the
original controlled principal and target is each destination group.

`actor_controlled`, `source_authorized`, and `source_admin_control` are computed from
state and cannot be overridden by context facts. The relationship must exist in the
graph or derived state. `actor_enabled` and `target_enabled` can use the canonical
node's enabled field; explicit snapshot false blocks even if context claims true.
An absent enabled value requires explicit runtime evidence.

| Predicate | Caller must establish |
| --- | --- |
| `security_group` | Destination is a security authorization group, not a distribution group |
| `membership_usable` | Membership applies to the actor's token, group scope and domain context now |
| `admin_channel` | A supported privileged execution channel is reachable and permitted, including endpoint/UAC restrictions |
| `authentication_accepted` | Target accepts this actor's current authentication context |
| `rdp_available` | RDP is enabled, reachable, and logon is allowed without an applicable deny |
| `winrm_available` | WinRM is reachable/configured and its endpoint permits this actor |
| `target_enabled` | Target account is enabled and authentication-usable |
| `password_policy_accepts` | The proposed reset satisfies password policy |
| `directory_write_allowed` | The selected directory operation is permitted and can complete in this environment |
| `membership_change_allowed` | The selected group modification is permitted |
| `session_fresh` | Session observation remains fresh under caller-selected timing policy |
| `session_present` | Session is still present at evaluation time |
| `credential_accessible` | Useful material is accessible despite protection/endpoint controls |

Failure-condition labels are explanatory catalog metadata; executable checks use the
bounded prerequisite vocabulary. Unknown predicates/effects cannot run arbitrary code.

## Technique boundaries and remaining ambiguity

MemberOf is passive and carries no telemetry or ATT&CK action reference. AdminTo
produces host admin control only after runtime checks. RDP and WinRM produce their
specific session/execution capabilities and never add admin control.

GenericAll/User offers password reset or DACL manipulation. GenericAll/Group offers
membership addition or DACL manipulation. Computer/Domain/OU/GPO currently offer
only the generic DACL operation. This deliberately leaves specialized computer,
delegation, GPO, account-attribute and SPN abuse techniques unimplemented: research
does not define enough prerequisites/effects to implement them here.
The representative DACL operations grant WriteDacl from GenericAll and GenericAll
from WriteDacl. Narrower selectable rights need a future technique definition.

ForceChangePassword produces authentication control only. HasSession requires admin
control of the source computer plus all three freshness/presence/accessibility guards;
it produces only credential material. Material reuse into authentication control is
deferred because the research does not specify a reusable-material test. There are
no invented freshness durations, success probabilities or selected admin channels.

`ExpectedTelemetry`, `ObservedActivity`, `StructuralRelationship` and `ConfirmedAttack`
are distinct types. Evaluation neither consumes nor creates observed events or
confirmation. Expected events are conditional hints (4724 describes an attempt,
5136 needs auditing/SACL configuration). Missing expected events cannot block a
transition or prove absence of an attack.

`correlate_activity(activity, context, actor, target)` allows entity comparison only
after explicit matching nonempty environment ID and identity namespace, timezone-aware
timestamps and a compatible time window. A mismatch or missing context raises
`ValueError` before comparing entities. Even a match is only a candidate activity;
it does not create a relationship or ConfirmedAttack. Independent datasets can supply
generic telemetry taxonomy but cannot be joined by matching usernames/SIDs alone.
Callers must substantiate the supplied context; this API cannot establish provenance
from environment labels alone.

## Provenance contract (#81)

Every non-empty expected-telemetry mapping points through `evidence_refs` to the
catalog's `evidence_registry`, whose entries carry the supported claim, source
locator, rationale and confidence. These references explain why a transition
predicts a signal; they do not assert that the local telemetry corpus contains
that signal. The passive `MemberOf` transition remains telemetry-free.

`ObservedActivity` requires an immutable `TelemetryRecordRef` containing the
manifest `dataset_id`, `snapshot_id`, existing `snapshot:<hash>/<file>` reference,
and a repository-defined record locator. Construction receives the manifest root,
re-reads the selected file through the verified-snapshot helper, and checks CSV
row bounds or a unique canonical-row content hash. The current telemetry corpus
uses a 1-based CSV row locator when that is the available record identity.
Mismatched datasets, snapshots, files, nonexistent rows, unmatched hashes and
ambiguous duplicate hashes are rejected; no placeholder source is accepted.

`CorrelationRecord` is explicitly `candidate` or `rejected`; compatibility
requires environment, identity namespace and time-window evidence. Candidate
construction also validates that the technique exists in the semantic catalog
and that its relationship matches the structural relationship. A candidate does
not become `ConfirmedAttack` unless an explicit `ConfirmationBasis` is provided
by the caller. Telemetry provenance is never structural edge provenance, and no
field was added to `configs/contract.yml`.

Cost factors are descriptive names in `result.technique.cost_factors`, not calibrated
weights, probabilities or durations. No existing weighting interface or `maut_v1`
profile changes. A future scoring integration requires its own research/ADR.

## Acceptance criteria to tests

Tests are in [catalog tests](../tests/test_attack_semantics_catalog.py) and
[transition tests](../tests/test_attack_semantics_transitions.py), with the
[#81 provenance tests](../tests/test_semantic_provenance.py).

| #63 criterion (issue order) | Regression coverage |
| --- | --- |
| 1. Typed catalog/validator | `test_all_fields_required`, `test_invalid_field_values_rejected`, `test_telemetry_event_id_is_typed` |
| 2. Preserve canonical M1 fields | `test_catalog_covers_contract_without_runtime_fields`, existing `test_contract.py` |
| 3. Cover all eight relationships | `test_catalog_covers_contract_without_runtime_fields`, `test_missing_edge_duplicate_id_and_unknown_fields` |
| 4. Nested/cyclic membership | `test_nested_membership_cycles_silent_and_inherited_admin` (User/Computer/Group) |
| 5. No traversal telemetry | Same nested test; `test_passive_membership_cannot_claim_attack_or_telemetry` |
| 6. RDP never implies admin | `test_remote_sessions_do_not_grant_admin` |
| 7. WinRM/runtime false fails | `test_host_runtime_false_blocks_unknown_is_indeterminate` |
| 8. HasSession requires host control | `test_hassession_requires_host_admin_not_merely_a_session_or_principal_control` |
| 9. Session freshness/access; no identity takeover | `test_hassession_freshness_availability_and_accessibility`, `test_hassession_only_recovers_material` |
| 10. WriteDacl derived capability | `test_write_dacl_derives_right_and_next_action_uses_it_without_graph_mutation` |
| 11. GenericAll dispatch | `test_genericall_dispatches_by_target_and_explicit_technique`, group and non-user transition tests |
| 12. Missing telemetry is not disproof | `test_telemetry_absence_does_not_change_applicability_or_infer_observation` |
| 13. Independent dataset isolation | `test_independent_telemetry_cannot_entity_join_and_matching_activity_is_not_confirmation` |
| 14. Unit/regression coverage | Both new test modules plus the complete existing suite |
| 15. Architecture documentation | This document and link from `docs/03_architecture.md`; canonical/weight interfaces unchanged |

Additional coverage checks password-reset semantics, disabled accounts, unknown runtime
facts, token refresh after group changes, immutable snapshots/state, stale branch
application, and deterministic behavior on the existing M1 fixture.
`test_hassession_runtime_facts_are_scoped_to_source_host` covers two computers sharing
one session user with distinct true/false/unknown facts for all three session predicates,
an actor distinct from both hosts, and independent source-admin checks (PR #66 review).

Run the repository's CI commands: `python -m pytest`, `python -m ruff check .`,
`python -m ruff format --check .`, `python -m yamllint .`,
`python scripts/check_contract.py`, `python scripts/check_repository.py`, and
`NEO4J_PASSWORD=ci-validation-placeholder docker compose --env-file .env.example --profile graph config --quiet`
(Bash; CI supplies the same environment variable).

Verification on Linux / Python 3.14.2: full pytest suite **316 passed, 1 skipped**
(the existing Windows junction test); both new modules **86 passed**. Ruff check,
Ruff format check, YAML lint, contract validation (two fixtures), repository validation
and Compose configuration validation passed. `git diff --check` passed. Windows CI
was not executed locally. Contract, existing tests and dependency files are unchanged.
