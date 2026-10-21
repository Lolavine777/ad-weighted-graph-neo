# Scenario rating pack v1.2 - pending Owner B review

PR #260 is rebased onto `develop` at `a8e53b88`, including merged #258.
This pack retains the equal synthetic AdminTo regression and adds a bounded Source A scenario transfer proposal through native automatic resolution.
It does not establish calibrated enterprise likelihood or effort.
All published numeric records remain pending B review; numeric activation is disabled.

## Numeric decision

The graph declares Alice -> Host `AdminTo`, Admins -> Host `AdminTo`, and Alice -> Admins `MemberOf`.
Both terminal operations have the same actor, host, `AdminTo` method, authentication/resource context, and declared channel/authentication prerequisites.
Source authorization provenance alone does not support different execution effort or conditional success probability.
The former C=4 versus C=1 and separated P intervals are withdrawn.
Neither EDR nor detectability is a numeric discriminator here.

No measurement, elicitation, or explicit operational rubric calibrates absolute costs or probabilities in this scenario.
Consequently C/P values are `synthetic_test_only`, with `uncalibrated_algorithm_fixture` uncertainty.
Equality between execution branches follows the declared semantics; the absolute numbers exist only to verify aggregation and interval arithmetic.
They must not be relabeled `scenario_assumption` or used in production after a status-only promotion.

## Effort classes

| Work | T1 | T2 | C = T1 + T2 - 2 | Scope |
| --- | --- | --- | --- | --- |
| Shared authentication context | 1 | 2 | 1 | Actor source, `AdminTo`, `w4-two-routes-exact`, `intra_forest` |
| Direct admin execution | 1 | 2 | 1 | Exact Alice source, same method/scenario/boundary |
| Inherited admin execution | 1 | 2 | 1 | Exact Admins group source, same method/scenario/boundary |

The disjoint `source_ids` prevent direct/inherited C conflicts in the public loader.
Preparation and execution are additionally separated by technique and work classification.
Native effort records carry `notes`, rather than the unsupported former `rationale` field.
`propagate_group_entitlement` is passive: no C unit and no q event.
Every generated path has C=1 preparation + 1 execution = 2.
All three paths tie for Min-Effort; `generated_0001` is the stable representative.
This equal fixture remains a regression; the separate Source A proposal below supplies materially different work, pending B transfer acceptance.

## Likelihood records

| Conditional outcome | q interval | Basis |
| --- | --- | --- |
| Shared auth preparation | [4/5, 9/10] | Historical synthetic A2 arithmetic fixture only |
| Direct execution given preparation | [1/2, 3/4] | Same synthetic A2 direct interval, without an unsupported authorization discriminator |
| Inherited execution given preparation | [1/2, 3/4] | Equal fixture interval under identical execution context |

The preparation interval is not an assertion about Kerberos reliability or enterprise success rates.
The execution interval is not inferred from cost or boolean prerequisites.
The retry budget is exactly three attempts with a 120-second timeout within `fixed_snapshot_window`; these are lookup context, not calibrated success guarantees.
The ordered successful history contains preparation before execution.
Passive membership contributes no likelihood factor.
Every path has exact P=[(4/5)(1/2), (9/10)(3/4)] = [2/5, 27/40].
These identical non-degenerate intervals overlap, so all three paths are incomparable in the repository's scoped risk relation.
The frontier contains all three generated candidates and the dominated set is empty.
The oracle follows the basis decision; it does not require or manufacture strict dominance.

## Impact basis

I remains High solely for typed `admin_control` over the exact synthetic Host C0 asset and `goal_id=admin_host_c0`.
This is a bounded technical consequence fixture for a synthetic departmental host, not a general business-risk baseline.
The mapping preserves `semantic_goal/1.0.0`, exact snapshot, boundary, scenario, review reference, and source-packet digest.
The old `synthetic-a2` wildcard scope is removed from this new pack.
Legacy string `required_predicates` are absent from the public goal and mapping; #258 materializes its typed goal predicate.
Weaker session goals, other snapshots, goal IDs or scenario scopes cannot reuse High.
The source packet is the existing synthetic consequence source; the destination equivalence mapping remains pending.

## Public automatic flow and work rule

`automatic-query.json` is the exact reusable semantic query/config consumed by API and CLI.
Its `rating_resolution` uses `public-rating-resolution/1.1.0`, automatic mode, canonical-digest registry envelopes, and synthetic policy.
It publishes native `effort`, `likelihood`, `impact`, `impact_source`, and `work` roles.
It contains no candidate sequences, per-path ranking packets, action bindings, fact-ledger overrides, custom predicates, or injected preparation units.

The `work` role is the native scoped decomposition rule for `obtain_admin_execution_on_host` + `AdminTo` -> `auth_context`, with exact scenario and boundary.
Its accepted **structural synthetic protocol** references the shared-preparation regression already merged in #258.
That rule carries no numeric cost or probability and does not approve the necessity or calibration of preparation in a real environment.
B still needs to review the proposed scenario preparation semantics before any broader reuse.
The meaning is an abstract authentication-context setup before execution, not an observed separate Kerberos/SMB/RPC operation.

The merged materializer creates preparation identities from actor, host, method, auth/resource context, policy and scenario.
It creates execution identities including authorization source.
P identities in the pack are derived beforehand from those published deterministic context formulas, never copied from engine output.
Preparation is counted once per path and has one shared ledger identity across all paths.
Public scope/history guards remain in force; missing semantic scenario authority does not become a wildcard.

### Review simulation boundary

Loading the published query unchanged generates three paths with C=0/3, P=0/3, I=0/1 rated unique requests.
All numeric dimensions remain unrated because the records are pending.
The positive integration probe explicitly simulates review on copies under `synthetic_test_only` policy, changing only native review/disposition gates and rehashing affected envelopes.
It does not approve or modify canonical pending records, or substitute provider code, applicability, values, preparation packets, or ranking behavior.
CLI reproduction exports simulated envelopes to a new temporary file; their accepted/rated gate markers apply solely to that synthetic review simulation.
Its result is arithmetic and integration evidence only; it is not B approval or production readiness.
Production policy rejects the synthetic work rule before execution.
A separate negative control omits that rule and proves production policy refuses the synthetic numeric records as well.

## Coverage and remaining B gates

The positive review simulation has three genuinely generated feasible paths, each with two C units, two successful-history prefixes, and the exact High consequence.
Unique request counts are C=3/3, P=3/3, I=1/1; shared and repeated direct prefixes are deduplicated across candidates.
The pending pack has C=0/3, P=0/3, I=0/1.
The inventory is 23 techniques: 22 active and one passive.
Only one active technique has numeric fixture coverage; **21 active techniques remain unrated in this bounded case**.
`auth_context` is separate preparation inventory, not an additional catalog technique.
No repo-wide or production 100% coverage is claimed.

B review must separately decide exact applicability, preparation meaning, C fixture rubric, P fixture intervals/history, bounded I, and oracle arithmetic.
Scenario activation remains blocked on B acceptance of the scoped numeric transfer and context equivalence.
Empirical calibration is not claimed and is not substituted for declared scenario judgment.
#251 still needs B acceptance/reproduction of the different-C case and its other acceptance gates, including the private frozen #243 prerequisites.
This PR neither completes those gates nor approves records on B's behalf.
Historical Week 3 artifacts, the frozen #243 scenario, and historical oracle subsections remain byte-preserved.

## Reproduction

Use the repository virtual environment:

```sh
.venv/bin/python -m pytest tests/test_scenario_rating_pack.py tests/test_public_rating_integration.py
.venv/bin/python -m scripts.research.scenario_rating_pack
.venv/bin/python -m src.engine.query_cli \
  --query docs/research/ratings/scenario-basis-v1/automatic-query.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --label synthetic
.venv/bin/python -m scripts.research.scenario_rating_pack \
  --simulate-review --export-query /tmp/pr260-synthetic-review-query.json
.venv/bin/python -m src.engine.query_cli \
  --query /tmp/pr260-synthetic-review-query.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --label synthetic
```

The tests run API, subprocess CLI twice for determinism, and public orchestration against the same envelopes in both pending and simulated states.
They compare full ranking outputs and coverage, and exercise missing basis, conflicting C, exact P history/method/horizon/boundary/source/snapshot/retry, goal/scope spoofing, missing scenario authority, known-false semantics, and production refusal.
The manifest pins all package bytes, native #258 integration code, the synthetic graph, and historical sources.
Local checks are local evidence; they do not imply remote CI ran successfully.


## Bounded Source A scenario proposal (follow-up #6106824248)

The equal AdminTo fixture above is retained unchanged.
The separate `source-a-query.json` uses production provider policy with pending `scenario_assumption` C/P/I records.
It proposes transferring the existing Week 3 Source A judgments to current native semantic identities; it is not a new independent expert assessment or an approved numerical release.
`source-a-basis.json` retains each source effort/conditional record, question ID, original full ordered prefix, review decision, retry policy, uncertainty and governance disclosure.
The source is the pinned historical `week3-closeout/reviewed-release.json`; its bytes and #243 remain unchanged.
Historical ratings were AI-proposed and human-adopted with B adoption relayed by A, rather than authenticated blind independent ratings.
The new scope, method bindings, budget interpretation and typed impact mapping all remain pending B review.

### Observable work and numeric basis

The two rating-supported paths are actually generated, rather than supplied candidates:

| Generated ID | Ordered semantic operations | C | Exact path P | I |
| --- | --- | --- | --- | --- |
| `generated_0001` | Reset Lidia; activate Lidia; passive DA membership; WinRM admin on BADBLOOD | 1+0+1 = 2 | [(3/5)(3/4)(1/2), (19/20)(49/50)(9/10)] = [9/40,8379/10000] | High |
| `generated_0006` | Reset Josefa; activate Josefa; passive VA-JER membership; reset Ollie through VA-JER; activate Ollie; passive DA membership; WinRM admin on BADBLOOD | 1+0+1+0+1 = 3 | [(3/5)(3/4)(3/5)(3/4)(1/2), (19/20)(49/50)(19/20)(49/50)(9/10)] = [81/800,7800849/10000000] | High |

Reset uses standard authenticated SAMR/LDAP administration and a directory write, T1=1/T2=2/C=1.
Activation uses the standard automated Kerberos exchange with credentials already produced by the preceding reset, T1=1/T2=1/C=0.
WinRM includes session setup, command submission and administrative execution verification, T1=1/T2=2/C=1.
These are the existing historical rubric scores, not elapsed-time measurements or newly increased costs.
The extra reset is a distinct target operation and contributes the C difference; passive membership adds neither C nor a probability factor.
C=0 activation still performs work and has a conditional success event.
Reset excludes activation work, and WinRM already includes its session preparation, so this case has no additional `auth_context` rule or injected shared preparation.
The supplied foothold is outside the evaluated work boundary.

P preserves the source judgments without narrowing or averaging:

| Conditional operation | Interval | Explicit context and uncertainty |
| --- | --- | --- |
| Password reset | [3/5,19/20] | Standard reset under declared rights/reachability/password-policy/write conditions; residual request processing and response completion within 15 minutes and at most 3 attempts |
| Identity activation | [3/4,49/50] | All prior work succeeded and credentials exist; standard Kerberos exchange with lower coordination requirements, within 10 minutes and at most 3 attempts |
| WinRM admin execution | [1/2,9/10] | All prior work succeeded and listener/reachability/admin mapping/authorization/context are declared; residual session allocation, quota and command-completion uncertainty within 30 minutes and at most 3 attempts |

All events are conditioned on the supplied foothold, declared scenario, and their entire ordered successful active-work history within 24h.
The mechanism bounds are explicit historical scenario judgments, not probabilities derived from technical documentation, C scores, true prerequisites, EDR or detectability.
The two complete histories have eight separate native P records, including the second reset after Josefa activation and Ollie activation after both resets.
Equal mechanism bounds across those named contexts are a proposed retention of the historical scoped equivalence, not an independence assumption or fallback to marginal probabilities.
No numerical retry transformation is applied; the engine multiplies conditional bounds and does not execute retries or timeouts.
The query binds the full per-mechanism retry policy in every P lookup.

I retains the source High consequence for administrative control of the same BADBLOOD DC supporting identity, authentication and access-control services in the explicitly assumed enterprise context.
It does not infer Critical from the DC label or invent a critical SLA or single-DC dependency.
The new mapping binds the exact typed `admin_control` goal, `goal_id=bounded_source_a_admin_dc`, asset, snapshot, boundary, 24h and scenario.
A weaker goal or another asset cannot reuse it.

### Freeze, projection and actual automatic result

Commit `ce6434b` froze the basis, pending native query and graph before the first ranked Source A execution.
Its basis canonical digest is `sha256:fd709b190fc3d388f61a38cab93100f9786332e667d9b8178914dd4aeefb5ac1`.
The later oracle records the observed result against that unchanged digest.
Numbers were not selected to obtain a frontier or a cost winner.

The graph is the induced projection over all actor/source/target IDs in the historical Source A semantic bridge plan: 7 original nodes and all 16 original edges between them.
The projection is rebuilt from manifest-verified SEAMLESS raw and checked for exact node/edge equality, including unused relationship kinds.
It contains real snapshot structural evidence, with explicitly assumed collection-time provenance preserved.
The graph retains the original snapshot ID as evidence ancestry; completeness claims apply only to this declared projection and four-technique catalog, not to the whole snapshot.
The public query supplies only initial state, runtime facts, goal, search budget and native registry envelopes, with no path list, per-path ranking packet or action bindings.
All runtime prerequisites are explicitly declared and attributed to this pending context transfer; observed false evidence vetoes optimistic assumptions.

The native search cap is 10 semantic steps, 1000 paths and 60000 expansions.
This differs from the historical envelope's 6 active-unit budget because passive transitions also occupy semantic steps.
The cap permits both supported histories and all generated interleavings in this projection, without rescaling the mechanism probabilities.
B must review that search-budget/context equivalence explicitly.

The real merged #258 automatic API, subprocess CLI and orchestration produce identical rankings and coverage in pending and simulated-review states.
The unchanged canonical query produces 24 paths with C=0/8, P=0/46 and I=0/1 rated unique requests and no numeric activation.
Positive evidence changes only native review/disposition gates on copies, leaving production policy, values, applicability, prefixes and providers unchanged.
It is conditional evidence for B's decision, not a production release or B approval.
The simulated run admits all 24 candidates, with no adapter rejections, C=8/8, P=8/46 and I=1/1 unique requests.
All 24 paths have complete C and I, but only 2/24 have complete P; the remaining 22 paths contain 38 distinct unreviewed P prefixes.
The scenario covers three of 22 active catalog techniques; the other 19 remain outside this case's numeric scope.
All 24 generated action sequences and their numeric/gap outcomes are enumerated in `source-a-oracles.json`.

Min-Effort is uniquely `generated_0001`, C=2, within the complete declared projection/catalog/budget.
The scoped risk frontier contains `generated_0001` and `generated_0006`; their P intervals overlap and I is equal, so neither strictly dominates.
The 22 P-unrated paths are excluded from the risk frontier, not declared dominated or impossible.
No whole-snapshot optimum, complete predictive coverage, calibration or completion of #256/#251/#259 is claimed.
B still needs to accept the transfer rubric/overlap, eight conditional-history judgments, budget/context equivalence, exact I mapping and independent automatic-flow reproduction.
New histories remain unrated until separately reviewed.

```sh
.venv/bin/python -m scripts.research.scenario_rating_pack --case source-a
.venv/bin/python -m scripts.research.scenario_rating_pack --verify-source-raw data/raw/SEAMLESS
.venv/bin/python -m src.engine.query_cli \
  --query docs/research/ratings/scenario-basis-v1/source-a-query.json \
  --graph docs/research/ratings/scenario-basis-v1/source-a-graph.json \
  --label seamless --prerequisite data/samples/manifests/seamless-raw-v1.json
.venv/bin/python -m scripts.research.scenario_rating_pack --case source-a \
  --simulate-review --export-query /tmp/pr260-source-a-review-copy.json
.venv/bin/python -m src.engine.query_cli \
  --query /tmp/pr260-source-a-review-copy.json \
  --graph docs/research/ratings/scenario-basis-v1/source-a-graph.json \
  --label seamless --prerequisite data/samples/manifests/seamless-raw-v1.json
.venv/bin/python -m pytest tests/test_source_a_rating_pack.py tests/test_scenario_rating_pack.py
```

The CLI prerequisite hash alone does not prove raw-to-projection lineage; use the explicit raw verifier for that check.
CI can reproduce the published projection without private raw; the optional lineage test runs when raw is available.
