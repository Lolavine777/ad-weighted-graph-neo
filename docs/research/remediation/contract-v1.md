# Chokepoint and remediation semantics 1.0.0

The current comparison/acceptance protocol is [version 1.1.0](contract-v1.1.md).
Its semantic identity, complete bypass and rediscovery rules supersede the comparison rules in this historical specification.

Refs [#269](https://github.com/nairyuuu/ad-weighted-graph/issues/269), parent [#265](https://github.com/nairyuuu/ad-weighted-graph/issues/265).
Owner: A / @Lolavine777; reviewer and implementation consumer: B / @nairyuuu.
Status: proposed semantic contract, pending B cross-review and execution integration.
Base: `7368cac505b3d19331cb8a688114107e91134f25`, latest `origin/develop` fetched on 12/10/2026.
Source/goal dependency: [PR #270](https://github.com/nairyuuu/ad-weighted-graph/pull/270) at `690fbd678db4e6cf194e43c4a455bfbc046fff43`, still pending B approval.
This branch does not merge that PR or wait for #267 numeric adoption.

## Scope and authority

A owns this contract, remediation mapping, independent literal oracles and acceptance analysis.
B owns counterfactual execution, batch scheduling, search, Top-K, metrics production and viewer integration.
No file under `src/`, no existing baseline, no canonical graph contract and no raw AD data is changed.
The acceptance checker validates supplied artifacts; it neither runs queries nor builds metrics or overlays.
Tests call the existing public `run_attack_query` for explicit finite negative controls.
The tests use the existing `blocked_evidence` runtime vocabulary with an explicitly synthetic/scenario rationale, not evidence of a deployed fix.
B must retain `counterfactual_origin=declared_intervention_not_observation` when transporting any effective values to the evaluator.
Approval of this specification does not prove B's executor exists or that a mitigation has been deployed.

## Definitions and identities

A structural evidence dependency is a canonical edge ID plus every provenance occurrence supporting the effective relationship.
A node is an inspection/aggregation participant, not an intervention: deleting the compromised source or target cannot count as remediation.
An action dependency is an exact ordered transition occurrence with technique, actor, authorization source, target, authentication/resource context and binding participants.
A prerequisite dependency is the exact satisfied decision key and its origin: observed structural/static evidence, declared runtime assumption, technical rule or earlier capability/artifact.
An artifact dependency includes its owner, form, scope and producer/causal parents.
Producer and consumer dependencies are transitive: a fix at request time can invalidate downstream recovery and activation, but cannot erase a credential already declared initially.
A source-goal pair is one independently compromised source profile and one typed final success predicate.
DA entitlement is a separate identity goal/checkpoint, not host admin execution; use PR #270's source and target manifest meanings.

`ordered-action-evidence/1` identifies a program by the ordered full transition tuples, canonical evidence IDs, binding/context and stable artifact-parent references.
Distinct action histories, including D versus M/D, remain distinct programs even if their final state or work ledger is equal.
Do not include C/P values, execution timestamps or overlay/run IDs in the cross-run identity.
Exact regenerated candidate IDs remain trace references; match before/after by the normalized identity as well as replaying baseline programs.
`ordered-observed-edges/1` identifies a route trace by the ordered non-null observed evidence IDs per source-goal cell; it need not be a continuous graph walk.
Nonstructural/derived actions carry null canonical edge IDs and their producer lineage, never a fabricated raw relationship.
For a wholly nonstructural program, the route trace is empty and must be labeled as such, not called a structural path to the goal.
Work-program identity and shared work ledger are a third concept; neither replaces program or route denominators.

A coverage chokepoint has a high declared fraction of baseline programs or evidence traces that depend on it.
A source-goal choke is a valid intervention on a dependency that leaves a previously reachable pair proven unreachable after complete semantic rerun in the declared scope.
A cohort choke disconnects all baseline-exposed pairs in that fixed cohort.
A minimum cut or globally optimal remediation is not claimed by this package.
Node centrality, Top-K frequency and elimination of every displayed path generate candidates only.
A candidate becomes a recommendation with demonstrated effect only after a valid overlay, baseline-program replay and a search for bypasses.
A high program cut fraction may coexist with zero disconnected pairs or zero fully disconnected sources.

## Catalog and evidence binding

[catalog-v1.json](catalog-v1.json) contains 11 mappings pinned to the byte digest of `configs/attack_semantics.yml`.
[catalog-v1.schema.json](catalog-v1.schema.json) is its strict Draft 2020-12 schema.
Each mapping states intervention meaning, supported technique/gate, evidence requirement, applicability layer, limitations and technical references.
`executable_semantics` means the current evaluator has the mapped gate, not that an overlay adapter is already implemented.
`requires_new_basis` is advisory only and cannot produce an executable edit or numeric reduction.
Bindings use canonical IDs and complete raw provenance where available; public SEAMLESS examples use aliases that must be resolved locally through verified locators.
Missing, ambiguous or conflicting support makes a candidate unresolved, not applied or proven effective.
An edge with multiple contributing ACEs requires all grant origins and effective-right verification; removal of one duplicate occurrence is insufficient.
An inherited or group grant can bypass a revoked direct ACE; retained WriteDacl/GenericAll or membership-write rights can recreate rights in a new branch.
No relationship is invented because a technique name resembles a BloodHound edge.
Current RBCD exact descriptor support reads observed GenericAll; WriteDacl-derived rights are not accepted by its exact-right gate, so that expansion remains unsupported.

| Candidate | Effective change | Main bypass or limit |
| --- | --- | --- |
| ACL control | Revoke effective GenericAll, WriteDacl or reset right on the exact object | Other ACEs, inherited grants, membership or remaining DACL control can restore permission |
| Admin authorization | Remove effective AdminTo authorization | Existing initial host control; other authorized identities or delegated service routes |
| Admin channel | `admin_channel=false` for exact actor/host | Abstraction includes supported privileged channels; protocol-specific inference is invalid |
| Membership | Remove MemberOf or declare token membership unusable after refresh | Current token rights and later membership additions need explicit handling |
| AS-REP | Clear DONT_REQ_PREAUTH; `dontreqpreauth=false` | Existing material/password/usable identity survives |
| Kerberoasting | Decommission unnecessary SPNs with paired static facts, or strengthen account secrets | Required SPNs must remain; stronger secrets alone cannot prove failed recovery |
| RBCD | Deny effective descriptor write or bound delegation policy | Cleanup alone is ineffective while attacker can rewrite the descriptor |
| Session | End exact host/user session or verify useful material inaccessible | Other hosts/sessions, preexisting material and unsupported reuse remain |

AD access checks depend on security descriptors and ACEs; changing a single displayed canonical edge is only a model of an effective permission change when its complete support is bound.
See [Microsoft AD access control](https://learn.microsoft.com/en-us/windows/win32/ad/how-access-control-works-in-active-directory-domain-services).
DONT_REQ_PREAUTH is an account flag; requiring preauthentication targets the AS-REP request condition.
See [Microsoft account flags](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/useraccountcontrol-manipulate-account-properties).
Managed service accounts can manage service credentials, but the engine needs a new exact recovery basis to quantify a change.
See [Microsoft gMSA guidance](https://learn.microsoft.com/en-us/entra/architecture/service-accounts-group-managed).
RBCD resource authorization is configured on the resource account; this repo's RBCD service/WinRM model still requires its own explicit binding and runtime gates.
See [Microsoft RBCD configuration](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/ps-remoting-second-hop).
Credential Guard does not protect every material form, including Kerberos service tickets, so installing it cannot automatically set a universal inaccessible predicate.
See [Microsoft Credential Guard boundaries](https://learn.microsoft.com/en-us/windows/security/identity-protection/credential-guard/credential-guard-how-it-works).

## Immutable counterfactual request

[request-v1.schema.json](request-v1.schema.json) and [the finite request](../../../tests/fixtures/remediation/request-v1.json) define the executor input.
The request pins snapshot, canonical graph, SnapshotFacts, source/goal manifests, query profile, ratings, semantics, engine revision and caps.
All JSON-value digests use existing `canonical_digest`; catalog/config files use SHA-256 bytes.
Before values and provenance digests are checked against the resolved input by B; schema validation or an `effective_right_verified` assertion alone cannot establish them.
`query_profile_digest` covers the resolved ordered baseline cell requests, including facts, assumptions, initial state, allow-list, authentication contexts, horizon and work budget.
An absent SnapshotFacts view has canonical digest of `[]`; an absent rating configuration has canonical digest of `null`.
The goal/source manifest digests in the finite example refer to its explicit alias cohorts; production uses PR #270 manifest content.

Three bounded operations are specified:

1. `deny_relationship`: bind an existing canonical edge ID, exact tuple and complete provenance digest; suppress its effective authorization in a read-only semantic evidence view.
   Keep the base edge/provenance available for inspection and do not delete or rewrite the canonical graph.
   This does not suppress independently derived rights or initial permissions; the rerun must discover them.
2. `snapshot_fact_replace`: bind a known static value and evidence digest; expose the changed value in a separate effective counterfactual fact view.
   `dontreqpreauth` changes true to false.
   SPN decommission requires both `has_spn=true -> false` and `service_principal_names=nonempty -> []` for the same subject.
   Never construct new `FactEvidence(value_json=false, old observed provenance)` or serialize a hypothetical value as a newly observed SnapshotFacts record.
3. `runtime_fact_replace`: bind `(predicate, subject, target, authentication_context, binding_id)` and the expected resolved value, then expose false with intervention lineage.
   The engine currently keys runtime facts by only the first three fields; B must reject incompatible scopes and same-key bindings it cannot distinguish, rather than silently broadening them.
   AS-REP/SPN facts cannot be replaced through this operation.
   A missing runtime fact can be a declared conditional policy change, but support remains conditional, not an observed remediation result.

Resolve evidence and compare expected-before values before any run.
Reject unknown catalog versions, wrong scope/digest, nonexistent edges, duplicate or conflicting edit keys, incompatible bindings and partial SPN changes.
Already-false gates are ineffective fixes, not newly disconnected exposure.
Keep unknowns unknown and known-false vetoes active within each view; a declared change is not an assumption that overrides baseline false evidence.
Use a new effective overlay view with explicit intervention origin; preserve the original observed value and its support as `before`.
Effective precedence is selected overlay binding, then baseline resolution for untouched keys; a mismatch with the pinned before value rejects the edit.
No real LDAP, host policy or credential changes are performed.

Rebuild each before/after query from the same declared initial foothold, capabilities and artifacts.
Never reuse a baseline final state, derived rights, previous source credentials or prior source runtime context.
Do not revoke initial capabilities implicitly; choose a separately declared source-profile change if the intended question changes the compromise condition.
Apply all validated edits atomically; an unresolved edit makes the request unresolved and blocks effective-reduction claims.
Hash the overlay independently; verify baseline canonical and static/runtime inputs remain byte/value equivalent afterwards.
Only the changed effective predicates/authorization and overlay/run IDs vary; cohort, target success, catalog, model, ratings, context/horizon policies and budgets stay pinned.

## Before/after result and denominators

[result-v1.schema.json](result-v1.schema.json) defines per-cell observations, proofs, cuts, bypasses, new programs, numeric comparisons and summary coverage.
[The finite result](../../../tests/fixtures/remediation/result-v1.json) is independently expected, not output of a B runner.
Its program IDs are human-readable oracle labels; B must retain exact engine candidate/action IDs in production trace references.
`declared_source_ids` and `declared_goal_ids` identify the entire comparison cohort; omitted cells count as unknown.
Each observation includes all generated witness IDs, evidence `route_ids` and `trace_refs` associating programs with routes.
Each cut program has `replay_failures` linking its intervention IDs, failed decision and replay trace; a route is cut only when all associated baseline programs fail and no after program uses the trace.
Every baseline program must be replayed under the changed effective view to determine its fate; subtraction of generated counts or candidate-hash set differences is insufficient.
Rerun generation independently to find retained or new alternatives, including active nonstructural techniques.
Store both replay failures and discovered bypass traces with the exact failed/satisfied prerequisite and intervention ID.

For baseline successful programs B and baseline programs made invalid by replay F, `% programs cut = 100 |F| / |B|`.
For distinct baseline evidence traces R, a trace is cut only when every corresponding successful program is invalidated; `% routes cut = 100 |cut R| / |R|`.
These are corpus quantities if B/R came from a capped run; label `observed_corpus_only` even when every displayed item was cut.
For an empty denominator, percentage is null, never zero or 100.
When both runs are complete, feasible/negative proofs are resolved, the cohort is fully evaluated and search/model scope is fixed, `complete_declared_scope` is permitted.
A global numerator/denominator is not inferred from Top-K or from two capped runs.
New after programs remain separate and can preserve exposure even if every baseline program is cut.

`affected_sources` means at least one exact baseline dependency/replayed program was affected; it does not mean disconnection.
`exposed_sources_before/after` are sources with at least one valid witnessed final-goal program, including witnessed successes in capped searches.
`goals_still_reachable` is the union of final goals with after witnesses, not checkpoints.
`proven_disconnected_pairs` requires a before success witness and an after complete negative proof with no unresolved viable continuation in the declared semantic scope.
`pairs_disconnected` uses baseline witnessed exposed pairs as denominator, not all source-goal combinations or only evaluated successful after pairs.
`fully_disconnected_sources` requires a baseline-exposed source and after negative proof for every declared goal, including formerly unknown or unsupported goals; otherwise omit it and retain uncertainty.
`requested_pairs`, `evaluated_pairs`, `unsupported_pairs`, `unknown_pairs` and `truncated_pairs` keep full cohort coverage visible.
Coverage counts compare both sides: unknown includes unknown/error/not_evaluated on either side plus omitted cells; unsupported includes either side, and truncated includes either side.
A witnessed truncated success is reachable but also counted as truncated; coverage counts are not mutually exclusive.
Never infer safety for an omitted, timed-out, checkpoint-only, unsupported or errored cell.
Map PR #270 cells conservatively: success with witness -> reachable; negative statuses require complete nontruncated evidence/model-scope proof; indeterminate/checkpoint-only/truncated-no-witness -> unknown; unsupported/error retain their own dispositions.
A status string `blocked` alone is insufficient without the complete feasibility/proof conditions.
Structural reachability cannot prune a source when credential/RBCD producers can create nonstructural programs.

Min-Effort is the minimum authoritative C over all successful programs in this declared scope, with unique work accounting.
If C is missing on any potentially better candidate, report unrated/incomparable or an incumbent, not a proved numeric minimum.
Exact `delta = C_after - C_before` needs comparable adopted units/context, rated minima and both optimization certificates or exhaustive complete scope with full effort coverage.
Truncated minima are incumbents unless an independent valid bound/certificate proves them; this v1 checker conservatively refuses exact deltas in capped examples.
Disconnected after C is null with `unreachable`, never fabricated infinity, zero, number of steps or removal cost.
Defender cost and operational side effects remain qualitative or null; they are not attacker C.

Conditional P compares exact selected programs under the same source/goal success event, initial compromise condition, method/retry/work boundary, budget, horizon and adopted rating policy.
Re-resolve every active required ordered prefix in the new context; copied old P is not valid simply because the registry digest is unchanged.
Both programs must be fully rated and eligible under exact applicability and full-history checks.
The comparison-scope digest and basis references certify common scope plus declared intervention difference.
For intervals `[bL,bU]` and `[aL,aU]`, the signed difference interval is `[aL-bU,aU-bL]`, not a subtraction of midpoints.
Different representative programs must be identified explicitly; this is a conditional single-program comparison, not probability that an attacker tries all routes.
Do not add P across alternatives, infer q=1 from assumptions, turn unrated into zero, or assign zero P when no after program exists.
Reachability/exposure findings remain useful without P; they are not probability-loss or risk-reduction estimates.

## Independent executable acceptance

[finite-v1.json](../../../tests/fixtures/remediation/finite-v1.json) freezes eight oracle categories before execution.
The synthetic graph extends the existing two-routes fixture with one explicitly synthetic Bob membership; no frozen fixture is edited.
Public requests have no ordered attack program input and no numeric basis.
There are four successful programs: Alice D, M/D and M/I; Bob M/I.
Each cell is executed separately from its own initial state.
The tests compare complete ordered requests and exact evidence IDs to literal expected before/after program sets, not just program counts.

| Oracle | Expected before/after | Interpretation |
| --- | --- | --- |
| Genuine choke | Alice 3 -> 0; Bob 1 -> 0 with exact admin-channel denials | Four programs cut, two pairs disconnected, two sources fully disconnected in finite scope |
| Alternative bypass | Alice 3 -> 1 after membership denial; Bob 1 -> 1 | 2/4 cohort programs cut; 0/2 pairs disconnected; direct Alice route survives |
| Ineffective fix | 3/1 -> 3/1 after RDP-only gate denial | Gate is outside AdminTo semantics; zero affected programs/pairs |
| Multiple sources | Alice 3 -> 1; Bob 1 -> 0 after shared group policy denial | Both affected, only Bob disconnected; 3/4 programs cut versus 1/2 pairs |
| Nonstructural | AS-REP request/recovery/activation/member/admin, 1 -> 0 at recovery false | Source has no outbound structural edges; first three actions have null edge IDs |
| Missing evidence | Missing admin-channel gives indeterminate, zero witnesses | Unknown, no disconnected-pair proof |
| False evidence | False admin-channel vetoes true declaration, blocked | Negative finite control, preserved rejected-assumption audit |
| Search truncation | max_steps=1 yields one direct success and truncation | Reachable witness, incomplete alternatives; no global count/minimum claim |

Additional public tests deny Kerberoast recovery, RBCD effective descriptor write and delegation policy, and verify host/user session-material scope.
The synthetic rated public fixture independently expects C=1/P=3/4 inherited versus C=4/P=1/4 direct after membership denial.
Its C delta is +3, and P difference is exactly -1/2 in that synthetic single-program comparison.
Removing rating_resolution preserves reachability and leaves scoring unrated.
No real numeric adoption or broad production rating coverage is asserted.

## SEAMLESS example and recommendation order

The [SEAMLESS binding](seamless-v1.json) pins the six-file raw manifest, four aliases/locators, eight assumptions and the existing four-technique scenario.
The executable test verifies the full raw manifest before building the full canonical graph and again after evaluation.
It resolves X at `#/computers/1`, V_A at `#/users/1700`, G_DA at `#/groups/40`, C0 at `#/computers/0` without publishing identities.
Baseline is X -> AS-REP material -> recovered password -> usable V_A -> admin_control(C0), with direct AdminTo justification.
Membership-only remediation is ineffective for this host goal because the chosen chain does not use DA entitlement.
An exact admin-channel denial cuts this one declared source-goal scope; missing recovery remains indeterminate and step cap remains truncated.
Snapshot preauth and canonical AdminTo support are real input evidence; every runtime success and negative policy control is declared, not observed deployment.
[seamless-actual-v1.json](seamless-actual-v1.json) records the alias-only measured outcome and limitations.

| Review order | Candidate and support | Expected effect in this declared scenario | Uncertainty/side effect |
| --- | --- | --- | --- |
| 1 | Require preauth for V_A; verified `Properties.dontreqpreauth=true` | Prevent new request/material; B fact-view execution required | Existing secrets/material survive; validate application compatibility |
| 2 | Revoke effective V_A AdminTo on C0; exact canonical edge and all contributing provenance | Prevent this direct host-admin continuation; B authorization view required | Other grants/producers may bypass; verify full effective rights |
| 3 | Restrict V_A/C0 privileged execution channel; declared actor/host gate | Runtime negative control leaves no host program in this allow-list | No protocol-specific observed policy proof; alternate catalogs unresolved |
| 4 | Review V_A DA membership; verified MemberOf support | Does not cut the four-action direct AdminTo host program | Relevant to distinct entitlement goal, not a substitute for host remediation |

This is an evidence-first review order, not a cost optimizer or production top-fix ranking.
The baseline has one source, one final host goal and four allowed techniques, even though the graph is built from all verified records.
It is not batch reachability across the snapshot, not a DA/EA/DC general exposure assessment and not an observed exploit.
The new run is deliberately unrated; historical frozen C=3/I=High/P=0/4 and Source A baselines remain untouched.
Snapshot-fact replacement and relationship suppression are normative B acceptance requirements, not executed features here.

## B handoff and viewer integration

Consume catalog/request/result version 1.0.0 and PR #270 manifests after its approval; reuse public `AttackQuery`, `run_attack_query`, typed goals, rating resolution and evidence lineage.
Validate pins/bindings, create separate effective authorization/static/runtime views, rebuild source states, replay baseline programs, then rerun discovery under the fixed budgets.
Produce full matrix coverage and proofs before aggregation; never derive them from source leaderboard display order.
Return `cut_program_ids`, `bypass_program_ids`, `new_program_ids`, failed-decision/intervention trace links, witness IDs, query digests and proof references from actual outputs.
The viewer can inspect the selected permission/config change, original evidence, changed effective value and conditional declaration, affected sources, goals still reachable and bypass programs.
Show program/route/pair denominators and corpus versus complete labels alongside percentages.
Show unknown/truncated/unsupported/error states and null C/P reasons prominently; do not turn them into green/safe cells.
A displayed compound technique links to exact action indices, actor/auth context, participants and causal parents; it never masquerades as an observed edge.
Render defender cost as unscored/qualitative and attacker C as rated effort only.

Unresolved dependencies: B review of #269, B exact-head approval/adoption of #270, B effective static/authorization overlay adapter, scoped runtime-binding transport, counterfactual replay/rerun and proof/coverage aggregation, and #224 viewer integration.
#226/#227 search/Top-K guarantees and #267 applicable numeric adoption remain their own integration gates; they do not block this reachability contract.
B must cross-reproduce raw-backed results from a clean checkout before claiming integrated remediation acceptance.
Remote CI and human review are separate from local tests; billing-blocked jobs cannot be called passed.

## Reproduction

Run from this worktree with its own `.venv`, or the read-only executable of the main repository venv.
All Python commands must use a venv executable or `uv run`.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.research.remediation_acceptance
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_remediation_contract.py -q -p no:cacheprovider
REMEDIATION_SEAMLESS_RAW_DIR=/absolute/path/to/verified/SEAMLESS \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_remediation_contract.py::test_manifest_verified_seamless_runtime_controls -q -p no:cacheprovider
.venv/bin/python -m ruff check scripts/research/remediation_acceptance.py tests/test_remediation_contract.py
.venv/bin/python -m ruff format --check scripts/research/remediation_acceptance.py tests/test_remediation_contract.py
.venv/bin/python scripts/check_repository.py
.venv/bin/python scripts/check_contract.py
```

Without private raw inputs, the raw-backed test explicitly skips; it cannot silently pass on synthetic replacements.
The checker should print `{"catalog_entries": 11, "oracle_cases": 8, "status": "passed"}`.
The raw-backed test saves an alias-only summary under ignored `reports/generated/remediation269/`; no raw files are copied to this worktree.
