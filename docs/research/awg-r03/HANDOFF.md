# AWG-R03 — Implement the validated planner fixes

Repository: https://github.com/nairyuuu/ad-weighted-graph

Audited baseline: `develop@340e8e526e1e693d4c4b55635c459985eb08fa49`.

## Mission and authorized scope

Implement the first bounded engineering slice following AWG-R02. Research and
the initial semantic/performance experiments are complete. The current decision
is **keep and optimize the existing planner**, with its evaluator, typed state,
credential/RBCD bindings, provenance, replay, and shared-work assessor retained.

Complete the following three changes, in order:

1. Fix same-scenario, same-context actor scheduling/composition.
2. Fix CLI compatibility for omitted versus null `graph`/`catalog` fields.
3. Reuse validated catalog data through search and replay without weakening
   recipe validation or allowing stale/cross-query data.

This is an implementation task. Inspect, reproduce, implement, test, profile,
self-review, and return a reviewable result. Do not stop at another research
plan. No new product decision or raw SEAMLESS input is required for this slice.

Work in an isolated feature branch/worktree. Preserve existing user changes.
After validation, push only the implementation feature branch and open a draft
PR against develop, linking the AWG-R03 issue. Do not merge or directly modify
main/develop, alter unrelated issues, or contact others. No teammate-review
dependency or old internship acceptance process is required. Read applicable repository instructions and `docs/00_todo.md` before
editing. If your current checkout differs from the audited SHA, record the
actual HEAD and inspect the differences; do not reset it or assume the findings
are still unfixed. Use the audited baseline as the comparison reference.

## Supplied context and data

This handoff is committed at `docs/research/awg-r03/HANDOFF.md` on branch
`docs/awg-r03-planner-handoff`. Read the adjacent README and R02 report. Run
`python docs/research/awg-r03/prepare_evidence.py --output /tmp/awg-r03-evidence`
to extract the unchanged R02 archive; the paths below are beneath the resulting
`AWG-R02/` directory. No external attachment is required. Inspect the relevant
inputs/results rather than repeating the architectural audit.

| Path beneath `AWG-R02/` | Purpose |
| --- | --- |
| `AWG-R02_Bao_cao_thuc_nghiem.md` | Full Vietnamese findings, limits, comparison and backlog |
| `README.md` | Environment setup and baseline reproduction commands |
| `evidence/environment.json`, `requirements-frozen.txt` | Executed environment and dependencies |
| `evidence/source-provenance.json`, `audited-source-files.json` | Exact revision and 126-file audited source subset |
| `experiments/cases.py`, `oracle.py`, `alternatives.py` | Manually grounded finite cases and independent correctness oracle |
| `experiments/run_ablation.py`, `evidence/f1-results.json`, `evidence/f1-inputs/` | 78 variants covering 12 semantic groups, inputs and witnesses |
| `experiments/reproduce_actor_gap.py`, `evidence/actor-gap-public-api.json` | Minimal public-API actor-composition reproducer |
| `experiments/run_baseline_probes.py`, `evidence/f0-probes.json` | CLI null-key bug and truncation controls |
| `experiments/run_cost_probe.py`, `evidence/f1-shared-work-native-rating.json` | Native shared-work minimum-C regression |
| `experiments/profile_pipeline.py`, `profile_rating.py` | Phase-timing and profiler harnesses, including experimental-only monkeypatches |
| `evidence/f2-results.json`, `f2-profile-*.json/.pstats` | Retained timing trials, output digests and measured hotspots |
| `MANIFEST-SHA256.txt` | Integrity of the original R02 files |

R02 used CPython **3.14.8**, `networkx==3.7`, `PyYAML==6.0.3`,
`pytest==9.1.1`, `jsonschema==4.26.0`. Install the repository's pinned
`requirements-tests.txt`; the frozen environment is supplied for comparison.
The original source repository and venv are intentionally not duplicated in
this package. Repository access and a compatible Python environment are the
only setup prerequisites.

## Established evidence — do not misinterpret it

- 310 selected existing tests passed. This was a focused nine-module suite,
  not the entire repository test suite and not proof of real-world AD coverage.
- 78 finite F1 variants ran. Native reachability matched the independent oracle
  on 77; the mismatch is the actor-composition case below. All 67 native
  witnesses returned at that baseline passed the independent finite-model
  checker and native semantic replay.
- AS-REP, Kerberoasting, RBCD conjunction/reuse, unknown/False handling, and
  artifact/context boundaries worked in the executed models. RBCD's three
  valid orderings are not three independent exposures.
- The shared-work counterexample is already handled correctly by native
  ranking: prefix A costs 2; prefix B costs 5; suffix reuses B. Totals are
  A=7, B=5. Native minimum is **5**, with P/I unrated. The lightweight AND-OR
  first-support witness costs 7 and is not an optimal-C replacement.
- ForceChangePassword produces an authentication-control marker without the
  reset-credential activation bridge. HasSession produces untyped credential
  material without a recovery-to-password bridge. These are confirmed coverage
  gaps, not evidence that primitive transitions should grant usable identities.
- An immutable-catalog monkeypatch preserved exact output digests on four
  fixtures. Measured warm pipeline medians were RBCD 2.803 -> 0.332 seconds and
  padded RBCD 3.872 -> 1.585 seconds. Cache setup was recorded separately.
  These are evidence of avoidable work, not production speedup promises.
- A narrow passive-membership queue merge reduced expansions 11,742 -> 384
  while preserving 63 terminal state sets and fixture C. It did **not** preserve
  all ordered programs. Do not ship that merge as general Top-K/P dominance.

The oracle is independent of AWG candidate/transition/cost code but specialized
to small, deterministic, add-only grounded fixtures. Constant True guards are
specialized away. It is not a second implementation of the full AD rule system.

## Change 1 — Correct actor scheduling

Confirmed input, all within ONE scenario and authentication context X:

- U@X and V@X are initially usable.
- Structural permissions: `U AdminTo H1`, `V AdminTo H2`, `U AdminTo H3`.
- Runtime gates are explicitly True with declared-assumption provenance.
- Target is H3; typed goal requires `admin_control={H1,H2,H3}`.

The independent oracle finds cost 3. Evaluating these existing requests in order
with the repository evaluator gives APPLICABLE at every step:

1. `obtain_admin_execution_on_host(U, U, H1)`
2. `obtain_admin_execution_on_host(V, V, H2)`
3. `obtain_admin_execution_on_host(U, U, H3)`

The baseline public API instead returns `no_path`, `complete=true`, after five
expansions. Search starts separate actor branches and does not compose their
valid actions into one accumulated branch state.

Likely files: `src/engine/search.py`, query/goal integration in
`src/engine/query.py`, and relevant search/exploration regression tests.

Implement actual scheduling of eligible actors from each branch-local state.
Account for initially usable and newly activated identities in the matching
context, and the original actor wherever the existing evaluator permits it.
Keep using the existing evaluator and authorization rules. Choosing an already
usable actor must not fabricate credentials, re-execute activation just to
switch actors, invent a new rated action, or double-count its work/P.

Preserve initial-actor/source attribution, request actors, target/goal metadata,
first-goal semantics, used-action restrictions, budget accounting and truthful
truncation. Avoid zero-action actor-switch cycles and duplicate programs caused
solely by scheduler bookkeeping. Do not union states from separate searches,
footholds or authentication contexts. Do not evade the defect by rejecting this
otherwise accepted typed goal or relaxing its required capabilities.

Regression coverage must include the confirmed cumulative-goal case, ordinary
single-goal behavior, eligible initially usable identities, switching after a
real activation, and negative wrong-context/uncontrolled-identity cases. Use
existing recipes; do not invent a new AD mutation technique for a test.

Important limit: R01's exact example "Bob creates a new permission only Alice
can use, forcing a return to Alice" was not expressed by the current catalog.
The confirmed R02 reproducer uses two initially usable identities and a typed
cumulative goal. Keep these claims distinct.

## Change 2 — Normalize null versus omitted CLI fields

The same query with an external graph returns three paths through the API.
CLI succeeds when `graph`/`catalog` keys are omitted, but exits 1 if either is
present with JSON null. The CLI checks key presence before materialization.

Likely files: `src/engine/query_cli.py`, relevant export/serialization code in
`src/engine/batch.py` or research scripts if needed, and CLI transport tests.

Make null `graph`/`catalog` mean no embedded override, consistently with the
API/typed serialization. Keep rejecting genuinely supplied embedded graph,
catalog or candidate data outside the CLI contract. Do not broaden this into
accepting arbitrary user-supplied semantic catalogs/candidates.

Test omitted, each null separately and both null together against the same
external graph; compare normalized semantic outcomes. Retain negative tests
for real unsupported payloads. Preserve schema, provenance, labels and
truncation controls.

## Change 3 — Reuse the validated catalog through search and replay

Measured search profile: `evaluate_rbcd` was called 14 times and loaded/parses
the default YAML catalog 14 times. Catalog cumulative time was about 96% of
that profile. Replay also reloads catalog data when not supplied a reusable
validated context. This is the first optimization to implement.

Likely files:

- `src/engine/semantics/catalog.py`
- `src/engine/semantics/rbcd.py`
- `src/engine/semantics/evaluator.py`
- `src/engine/semantics/credentials.py`
- `src/engine/ranking/verification.py`
- query/search plumbing as needed to carry the validated catalog identity

Choose the smallest sound implementation. Reuse immutable validated data for
an unchanged catalog/content identity and pass it through the relevant replay
paths. Maintain strict recipe equality/gate validation. Do not turn the
profiler's monkeypatches into production code, bypass `evaluate`, skip replay,
or cache runtime facts, applicability results, AttackState or evidence across
queries under an insufficient key.

Tests must cover an unchanged catalog, distinct custom/default catalogs,
modified/custom recipes that must still be rejected, and stale-data prevention
when catalog content changes between queries. A prepared query may explicitly
freeze its catalog context; a later query must not silently inherit a different
catalog's content. Avoid an unbounded or permanently stale path-only global
cache. Verify unknown/False behavior and per-query context isolation.

Show that default catalog parse/validation work no longer scales with RBCD
transition/replay count for an unchanged query context. Do not require a
hardware-specific speedup threshold to pass; require structural work reduction
and comparable timing evidence with semantic parity.

## Validation and comparison rules

Keep the supplied R02 evidence immutable. Write new results separately with
actual commit/tree/patch identity, environment and commands.

1. Reproduce the actor and CLI defects on the audited baseline. Use the
   supplied existing evidence as the reference; do not rerun the entire R01
   research process.
2. Add durable repository regression tests for the fixed contracts. Run the
   focused F0 suite from the supplied README and any broader checks required
   by the repository or touched modules.
3. Run the 78-case independent ablation against the implementation. The actor
   goal must now be reachable with an independently valid witness. All other
   reachable/unreachable/Unknown/False/type/context and minimum-C outcomes must
   remain correct. Re-run the native shared-work ranking probe: minimum 5,
   proper proof/truncation flags, P/I still unrated.
4. Separate correctness changes from performance-only comparison. Actor
   scheduling can legitimately add applicable attempts or valid ordered
   programs. Do not demand the old total witness count or blindly update
   goldens. Explain each semantic delta. Compare catalog optimization against
   the **same post-correctness implementation without that optimization**;
   that comparison should preserve normalized full outputs.
5. Profile stock/native code before and after optimization on the same
   two-routes, AS-REP, RBCD and padded-RBCD fixtures. Report graph preparation,
   query preparation, search, rating, internal replay and serialization
   separately without double-counting replay. Report setup cost, repeated
   samples/ranges and catalog load counts. Keep timing trials sequential and
   cProfile separate from benchmark timing.
6. Inspect your complete diff and test results. Fix problems found in this
   scoped work before handing back the result. Keep independently correct
   expected outcomes; do not replace the oracle with native generated output.

### Frozen harness traps

Several scripts deliberately assert the OLD baseline behavior:

- `reproduce_actor_gap.py` asserts that native search fails while evaluator
  replay succeeds. After the fix, create a positive regression rather than
  preserving this old assertion.
- `run_baseline_probes.py` expects CLI exit 1 for null fields. Its assertions
  need a separate post-fix counterpart.
- `verify_evidence.py` verifies immutable historical evidence: one mismatch,
  67 native witnesses, 126 original source hashes and a clean baseline. It is
  not a new-implementation acceptance runner and must not be made to pass by
  restoring known defects or overwriting the historical record.
- `profile_pipeline.py` compares native code with an experimental catalog
  monkeypatch. After implementing catalog reuse, its label "stock" means the
  new native implementation. Use a revision-aware native-to-native comparison
  for your improvement claim; do not count the monkeypatch twice.
- The scripts anchor inputs/imports to `AWG-R02/baseline`. Use separate
  baseline and implementation worktrees or an explicit scratch harness copy
  pointing at the implementation. Preserve the original evidence and make
  new output paths explicit.

## Explicitly deferred

- Production AND-OR discovery, a new rule compiler/DSL/planner framework,
  graph-database migration, or an architectural rewrite.
- General state merging/dominance, A*, all-target shared traversal, Top-K
  semantic redesign or full-history probability optimization.
- ForceChangePassword/HasSession recovery bridges or automatic promotion of
  marker/material to usable identity.
- Broad prepared-graph/index/rebuild refactoring. Record the residual profile
  after catalog reuse so this can be the next bounded task if justified.
- New P values, narrower intervals, probability midpoints, C/P/I rubric changes
  or assumptions presented as observed/calibrated probability.

Raw SEAMLESS was unavailable in R02. Do not block this slice on it, invent a
full-dataset result, or compare small-fixture seconds directly with historical
SEAMLESS benchmarks. If manifest-verified raw data is available in your actual
environment, an additional explicitly labeled validation run is useful, but it
does not replace the small independent correctness oracles.

## Return to the user

Provide a concise Vietnamese completion report containing:

- Actual baseline/implementation revision or patch identity and changed files.
- The three final behaviors and the root cause/fix for each.
- Regression and F1 outcomes, including the actor witness and shared-work C=5.
- Comparable native-before/native-after phase timings and catalog load counts;
  identify any semantic output differences separately from timing.
- A reviewable local diff/patch, exact reproduction commands, remaining limits
  and the next smallest justified task.

Finish the implementation and verification within this scope. Do not substitute
another architecture proposal or a passing test count for evidence that the
reported defects are fixed.
