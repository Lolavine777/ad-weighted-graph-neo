# Remediation comparison contract 1.1.0

Refs [PR #274](https://github.com/nairyuuu/ad-weighted-graph/pull/274) and [#269](https://github.com/nairyuuu/ad-weighted-graph/issues/269).
This revision addresses B's bypass completeness and cross-run identity findings on `c9a27172a851696b929ed2cf8347813d3a16cdd2`.
A owns the semantic contract and acceptance verifier; B still owns counterfactual execution, rerun/search, batch, Top-K, metrics production and viewer integration.
The [v1 definitions](contract-v1.md), [catalog 1.0.0](catalog-v1.json), frozen finite oracle and SEAMLESS scope remain applicable except for the superseded comparison identity and bypass rules below.
Existing v1 schemas and oracle artifacts remain unchanged historical baselines; they cannot pass the current acceptance gate.

## Current transport

Use [request-v1.1.schema.json](request-v1.1.schema.json) and [result-v1.1.schema.json](result-v1.1.schema.json), with `schema_version=1.1.0` and `program_identity_version=semantic-program/1`.
The catalog stays at version 1.0.0; no technique, intervention, raw graph or numeric adoption is changed.
Updated examples are [common-channel request](../../../tests/fixtures/remediation/request-v1.1.json), [common-channel result](../../../tests/fixtures/remediation/result-v1.1.json), [shared-membership request](../../../tests/fixtures/remediation/request-bypass-v1.1.json), and [shared-membership result](../../../tests/fixtures/remediation/result-bypass-v1.1.json).
New ACL and preauth request examples use the same v1.1 schema.
`validate_request`, `validate_result` and the CLI checker accept this current protocol only.
There is no inference-based adapter for old results: callers must supply the full semantic witness bindings and rerun evidence.

## Semantic identity

Each `trace_refs` entry retains its generated `program_id`, `trace_ref` and stable evidence `route_id`, and adds a structured `semantic_program` array.
Generated program/action IDs, run/query IDs, trace locations, timestamps, ratings and remediation request IDs are not semantic identity inputs.
A generated ID is a reference local to one observation; the same string in another run need not describe the same program.

The verifier computes the identity itself:

```text
SHA-256(canonical_json({
  version: "semantic-program/1",
  comparison_scope_digest,
  source_id,
  goal_id,
  actions: normalized_ordered_semantic_program
}))
```

`comparison_scope_digest` binds the fixed snapshot, graph/facts, source/goal cohorts, declared initial capabilities, typed goal, baseline query profile, model/catalog, ratings and search budgets through the request scope.
Before and after use that common comparison scope; their independently generated query digests remain reproducibility references, not cross-run identity keys.
B must resolve those pins and validate each structured binding against the exact native trace and input before publication.
A self-declared binding or digest alone cannot substantiate the underlying observation.

Each ordered action contains:

- `technique_id`, canonical `actor`, authorization `source` and `target`.
- `participants`: role-keyed canonical binding values for any additional actors/resources, including all applicable RBCD controller, service account, impersonated identity, resource/SPN and authentication-context participants.
  Do not copy a generated binding ID in place of these participants.
- `context`: exact authentication/resource context, method, budget, horizon and policy reference relevant to this action, with explicit null for an inapplicable field.
  The existing typed input values are retained; do not derive a probability or new option from them.
- `prerequisites`: every required catalog prerequisite and any additional evaluated technical gates, each with predicate, subject, target, origin, satisfied=true and its stable evidence bindings.
- `evidence_bindings`: stable canonical edge IDs, snapshot record/attribute bindings, runtime declaration keys, initial-state or artifact lineage references.
  Use scoped canonical/raw evidence references or digests of their typed bindings; never native candidate/action IDs or run-specific evidence labels.
- `producer_action_indices`: prior action positions supporting derived capabilities or artifact consumption.
  Positions must precede the consumer; initial capabilities are bound through the fixed initial state and evidence references.

Preserve action order, repetitions, passive authorization steps and participant roles.
Sort unordered prerequisite records, evidence-binding sets and producer-index sets using the existing canonical digest encoding; object key order does not matter.
Changing only a generated ID or set presentation order keeps identity stable.
Changing action order, participant, prerequisite key/support, relevant context, evidence binding or producer lineage changes identity.
All catalog prerequisites must be present; dropping a gate to force an identity match is invalid.
Every action and prerequisite requires nonempty stable evidence bindings, including explicit scoped initial-state/technical/artifact support for computed gates.
Empty support cannot collapse distinct evidence histories.
The structured successful witness has no false/unknown prerequisite; unresolved candidates belong in diagnostics and unknown dispositions.
For an initial-goal success, `semantic_program=[]` is valid and remains bound to source, goal and initial-state scope.

There is one witness representative per normalized semantic program per observation.
Duplicate normalized representatives are rejected rather than inflating program denominators; additional native aliases can remain in the referenced full trace artifact.
Different evidence routes or causal histories remain separate identities even when node sequences or final capabilities match.
This identity is for semantic comparison, not the work ledger or C/P rating lookup identity.

## Complete bypass and new-program reporting

For one source-goal cell, let B and A be normalized before and after successful witness sets.
`bypass_program_ids` contains the after-observation generated reference for every member of A, including retained programs, newly discovered programs and witnesses found by a truncated rerun.
Here bypass means any remaining successful continuation under the intervention, not only a route avoiding a named node or a newly generated route.
The field is required even for an ineffective intervention; if after remains reachable, the bypass list cannot be empty.
It is exactly equal to the full after witness reference set after normalization and deduplication, not a caller-selected subset.

`new_program_ids` contains precisely those after-observation references whose normalized semantic identity is absent from B.
A retained program with a changed generated ID is not new.
A different semantic program that reuses a before generated ID is new.
`cut_program_ids` identifies baseline-observation replay failures; no cut normalized identity may also occur in A, regardless of generated ID churn.
`affected_program_ids` and `replay_failures` continue to reference the baseline observation, while bypass/new fields reference the after observation.
Always qualify generated references by their observation/run when linking traces.

An empty bypass list means no successful witness was found in that after observation.
It is not proof that no bypass exists when rerun discovery was incomplete, unknown, not run or errored.
B must rerun semantic discovery including nonstructural producers; replay of baseline programs alone cannot support a remediation-success claim.

## Rediscovery and metrics

Every after observation includes `rediscovery={status, run_id, proof_ref}`.
Complete/truncated statuses must identify that exact after run and its discovery evidence, not a baseline replay artifact.
`after.complete=true` if and only if rediscovery status is `complete`, with matching after-run and proof references.
`after.truncated=true` if and only if rediscovery status is `truncated`, with matching after-run and proof references.
Rediscovery `not_run`, `unknown` or `error` requires both flags false; retained witnesses can still show reachability without certifying a complete search.
A `proven_unreachable` after cell requires complete rediscovery plus the existing complete feasibility proof, no unresolved continuation and zero successful witnesses.
An applied overlay, before success and that after negative proof are required for `disconnected=true`.
Unknown, not-run and error rediscovery cannot create a negative proof.
Complete search with unresolved feasibility remains unknown even when no witness was found.
Global `complete_declared_scope` percentages also require complete after rediscovery for every declared cell.
The verifier checks references and consistency; B must substantiate the actual search/proof artifacts when integrating the executor.

The existing denominators remain unchanged and refer to normalized semantic programs and distinct evidence traces.
The shared-membership fixture independently expects 3/4 programs cut (75%), 1/2 source-goal pairs disconnected (50%), Alice still exposed and Bob disconnected.
Alice's direct successful continuation is a mandatory bypass even though two of her three baseline programs were cut.
A capped baseline corpus can report 100% of its observed programs cut while a newly discovered after program preserves source-goal exposure; that percentage remains `observed_corpus_only`.
Neither reduced path counts, generated ID differences nor an empty incomplete bypass list imply risk reduction.
Comparable conditional P must bind its `comparison_scope_digest` exactly to the result-level digest, even when both intervals and selected witnesses are valid.
Unrated P remains valid and no new numeric values or adoption are introduced.
C/P nulls, rated comparability, source isolation, immutable evidence and defender-cost distinctions from v1 remain mandatory.

## Independent acceptance and B handoff

`tests/test_remediation_identity.py` exercises an omitted surviving bypass, an omitted new bypass, ID churn, ID reuse, semantic binding changes, set ordering, missing prerequisite bindings, legacy rejection and incomplete rediscovery.
Its ID-reuse case intentionally uses a capped baseline witness corpus: the reused reference was M/D before and direct admin after, so the after program is new while the source remains exposed.
The unchanged finite engine oracles still verify complete exact ordered request/evidence sets independently of these transport mutations.
The unchanged SEAMLESS acceptance verifies the six-file manifest before and after evaluation and retains raw-backed scope limitations.
No test changes a raw snapshot, the production engine or a frozen oracle expectation.

B should build the semantic binding records from actual transitions and full lineage, normalize/deduplicate, retain native trace references, replay baseline programs and independently rediscover after witnesses.
Classify cuts/new programs by semantic identity and populate bypass references from every after success.
Keep unknown/truncated dispositions and show cut-program percentages alongside disconnected-pair counts and remaining bypasses in the eventual viewer.
The verifier refuses partial witness/bypass reporting; it does not implement B's executor, discovery or UI.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.research.remediation_acceptance
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_remediation_contract.py tests/test_remediation_identity.py -q -p no:cacheprovider
REMEDIATION_SEAMLESS_RAW_DIR=/absolute/path/to/verified/SEAMLESS \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_remediation_contract.py::test_manifest_verified_seamless_runtime_controls -q -p no:cacheprovider
```

[Recorded local verification](review-v1.1-actual.json): 55 tests passed, including manifest-verified SEAMLESS and frozen file pins; contract checker and repository-wide static checks passed.
[Round 2 correction evidence](review-round2-fixes.json) records the completeness/scope guard regressions and 70 passing focused checks.
B exact-head Round 3 approval and executor/metrics/viewer integration remain pending.
This update does not merge PR #274 or close #269.
