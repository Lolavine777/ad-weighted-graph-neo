# Wave 2 state-goal review fixes

This packet addresses [B's review 5519963510](https://github.com/nairyuuu/ad-weighted-graph/pull/289#pullrequestreview-5519963510) of PR #289 at `c42350074ecb8dbb754d614ef04992067961b30a`.
The executable fixes are committed in `b4ae7e9d4e8dbc9c9fc98e5c979a90b2beae05e2`; the matching checkout test reference is committed in `7bdea13abbfb39ee99e93f1b7287e8f36e8b3af0`.
No approved C/P/I records, numeric assumptions, context/history inventories, frozen cohorts, prior releases or prior reports changed.

The [ordinary-technique finding](https://github.com/nairyuuu/ad-weighted-graph/pull/289#discussion_r4272440030) reproduces with the two-routes fixture, an Alice goal requiring `effective_member(Alice, Admins)` and only `propagate_group_entitlement` allowed.
Search returns the valid path with actual endpoint Admins and `goal_target=Alice`, but the reviewed head rejects ranking because it never mints native semantic proof.
Orchestration now requires native replay for every non-null `goal_target`, in addition to its existing credential, RBCD and initial-actor checks.
The automatic-resolution regression verifies semantic feasibility, admission, retained missing numeric basis and public API/CLI parity.

The [suffix-trimming finding](https://github.com/nairyuuu/ad-weighted-graph/pull/289#discussion_r4272440051) reproduces with a generated `activate_recovered_identity -> propagate_group_entitlement` path and an Alice goal requiring both usable identity and effective membership.
A manual ranking packet selecting only the activation effect incorrectly accepts the shorter prefix on the reviewed head.
Native verification now records immutable typed-goal satisfaction for the initial state and every replayed action prefix.
After first-hit selection, ranking checks the retained prefix against that process-local proof before trimming routes or granting endpoint exemptions.
Conflicting manual packets raise `RankingValidationError`; candidate JSON still cannot mint native proof.
The regressions reject invalid zero-step and activation-only prefixes, accept the complete two-step goal and preserve legitimate suffix trimming when the retained activation satisfies the declared typed goal.

Before the fix, the focused regressions produce three expected failures and two positive-control passes.
After the fix, all five pass.

```sh
.venv/bin/python -m pytest -q tests/test_public_rating_integration.py -k 'ordinary_state_goal or manual_state_goal'
```

On Python 3.14.7, 772 distinct tests passed across the following local groups; the 42 public-integration tests occur in both of the first two groups.
Manifest-verified SEAMLESS inputs were available for the raw-dependent tests.

| Local group | Modules | Passed |
| --- | --- | ---: |
| Public boundaries | public_rating_integration, engine_path_ranking_conformance, query_boundary_regressions, week4_query_materialization | 238 |
| Current-source contracts | public_rating_integration, rating_source_successors, likelihood_catalog_v1, scenario_rating_pack | 115 |
| Recovery and profiles | final_cpi_delegated_release, final_cpi_profiles, asrep, kerberoasting, rbcd | 167 |
| Integration | path_ranking_interface, source_goal_batch_contract, query_cli, asrep_basis_audit, asrep_expert_basis, final_cpi_delivery_replay | 227 |
| Release compatibility | final_cpi_release, final_cpi_wave2_release, final_cpi_adopted_subset | 63 |
| Acceptance byte pins | week4_acceptance_manifest, week4_acceptance_checkout_bytes | 4 |

Each module above names `tests/test_<module>.py` and can be reproduced with `.venv/bin/python -m pytest -q` followed by its paths.
The existing raw-backed regressions retain the approved recovery intervals, exact full-history binding, visible unknown-basis controls and refusal to transfer P to a changed reused-secret history.
Ruff lint/format, YAML, contract, repository and whitespace checks passed.
Author self-review checked the exact incremental diff, the process-local proof boundary, action/prefix indexing, source pins and preservation of every historical JSON artifact.

New generated source successors are likelihood v5 and scenario-basis v6, with strict predecessor-chain, current-source and historical-byte checks.
The [new Week 4 acceptance manifest](../../../reports/research/week4-maintainer-acceptance-manifest-v8.json) records clean revision `7bdea13abbfb39ee99e93f1b7287e8f36e8b3af0`, source digest `sha256:c09a76235b4f3bc000201404140634a2136f7e9863ca40bc18f83df0eb93cd07`, deterministic semantic digest `sha256:d6330d9d397a7a9a68c50a70508595a603d8c6e55283f8ce1a5406e39159744e`, 36 passed, 2 explicitly not executed and zero failures.

```sh
.venv/bin/python scripts/research/week4_acceptance_runner.py --output /tmp/state-goal-acceptance.json --check-determinism
```

The earlier full suite and native v9 cohort report remain evidence for their recorded historical source revisions.
This fix reran the relevant local suites and native regression checks, without rerunning the entire repository suite or all sixteen v9 cohort/CLI repetitions.
GitHub CI was excluded at the user's request because billing is broken.
Viewer, remediation and source aggregation remain untouched, and no merge or closure of #267 was performed.
