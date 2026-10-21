# Wave 2 production replay results

Actual B adoption improves the frozen original cohort and supported raw supplement.
Both withheld ACL diagnostic domains remain unrated. All results below are native
`estimated_expert_scenario` ratings, not observed exploitation or empirical probabilities.

Base: `b91a787ef2a59247536452cfeb8ebbf3f15963d4` (stacked on #271), containing
develop `16a3a214f51c79957a151469af3da3c8bc7a2a19`. Executable implementation:
`c1e2cb2`; exact source/runtime/dependency content identity is in the report.
No AGENTS.md was present in the repository or checked workspace ancestors.

[Native report](../../../../reports/research/issue267-wave2-delivery-v5.json) ·
[reproduce/authority](README.md) · [blocker guide](blocker-guide.md) ·
[remaining B packet](B-decision-packet.md).

## Before / after coverage

| Scope / phase | Valid | Feasible | C | P | I | Full | Pareto eligible | Truncated queries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Original / before | 50 | 50 | 48 | 48 | 48 | 48 | 48 | 4 |
| Original / after | 50 | 50 | 49 | 49 | 49 | 49 | 49 | 4 |
| Supported raw supplement / before | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 1 |
| Supported raw supplement / after | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 1 |
| All supplementary diagnostics / before | 109 | 109 | 0 | 0 | 0 | 0 | 0 | 3 |
| All supplementary diagnostics / after | 109 | 109 | 7 | 7 | 7 | 7 | 7 | 3 |
| Original full-raw subset / before | 26 | 26 | 24 | 24 | 24 | 24 | 24 | 4 |
| Original full-raw subset / after | 26 | 26 | 25 | 25 | 25 | 25 | 25 | 4 |
| Supplementary full-raw subset / before | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 2 |
| Supplementary full-raw subset / after | 9 | 9 | 7 | 7 | 7 | 7 | 7 | 2 |

The original, supported supplement and broader diagnostic denominators remain
50, 7 and 109. These are frozen query-program occurrences, including the declared
projection/raw overlap. CLI repetitions never add attacks to a denominator.
Returned representative full coverage is 49/50 and 7/7;
overall supplementary coverage is 7/109. The >=80% returned-sample
gate does not establish >=80% of arbitrary sources, the full generator or the full snapshot.
The diagnostic projection (100 programs) and all-generator control (2) are not
silently moved into the seven-path supported denominator.

| Query | Native status | Generated / feasible | Full before → after | Truncated |
| --- | --- | ---: | ---: | --- |
| source-a-projection | success | 24 / 24 | 24 → 24 | False |
| source-a-full-raw-four | success | 23 / 23 | 23 → 23 | True |
| source-a-full-generator | truncated | 0 / 0 | 0 → 0 | True |
| lidia-full-generator | success | 1 / 1 | 1 → 1 | True |
| josefa-full-generator | truncated | 0 / 0 | 0 → 0 | True |
| asrep-natural-password | success | 1 / 1 | 0 → 0 | False |
| kerberoast-material | success | 1 / 1 | 0 → 1 | False |
| kerberoast-identity | no_path | 0 / 0 | 0 → 0 | False |
| rbcd-unassumed | indeterminate | 0 / 0 | 0 → 0 | False |
| rbcd-scoped | success | 3 / 3 | 0 → 3 | False |
| acl-group-host | success | 3 / 3 | 0 → 3 | True |
| acl-group-projection | success | 100 / 100 | 0 → 0 | True |
| acl-group-all-generator | success | 2 / 2 | 0 → 0 | True |
| winrm-command | success | 1 / 1 | 0 → 1 | False |

Unrated returned programs are feasible minus fully rated. Empty truncated queries
are not proven no-path. The unassumed RBCD control is indeterminate, with missing
policy/conditions. Kerberoast identity preserves native no_path and the separate
successful-but-unreturned User-goal state diagnosis. Known-FALSE blocked attempt
counts and Unknown predicates are nonexclusive native diagnostics in the matrix,
not successful-path denominators. Unsupported Group login and RDP/HasSession
policy/raw absence remain outside the predeclared supported cohort.

## Native path-family acceptance

| Family | Generated evidence and exact remaining status |
| --- | --- |
| Reset → activation → elevated WinRM | 48 original returned programs retain Wave 1 C/P/I; passive MemberOf is not a P event. |
| ACL / Group → host-admin | Three raw ACL/host programs fully rated. Broader group mutation / grant-WriteDacl occurrences remain in the separately withheld 100 + 2 diagnostic programs. Mutation does not automatically grant a token or control. |
| RBCD | Three orderings of five successful events, exact controller/principal/HTTP-service lineage; C=9, conditional P=[504/3125,15760899/20000000], typed administrative consequence High. HTTP/SPN/runtime conditions remain scenario declarations. |
| AS-REP | One native request → recovery → recovered activation → host-admin path. Recovery C=2 is rated; recovery P has no basis; other withheld-context ratings remain unresolved. Whole path remains unrated. |
| Kerberoast material | One request/material path, C=1, P=[17/20,49/50], typed I=Low. No password recovery or activation is implied. |
| Kerberoast identity | Native no_path plus successful goal-state activation attempts; B-owned User-goal endpoint attribution remains unresolved. Recovery C=3 is retained in the scoped registry, without claiming a returned/rated path. |
| WinRM command | One full-rated path, C=1, P=[7/10,19/20], I=Medium; no host admin_control is inferred. |
| RDP / HasSession | not_generated / raw data absent / unsupported policy. No invented raw edges or capability. |

## Five worked native programs

| Case / candidate | Native program | Typed goal | C | Conditional P | Typed I | Ranking |
| --- | --- | --- | ---: | --- | --- | --- |
| source-a-projection / generated_0001 | scenario_reset_password → acquire_reset_identity → propagate_group_entitlement → scenario_winrm_admin | `admin_control` on pinned target | 2 | [9/40,8379/10000] | High | Pareto member; native C-Min-Effort=2 |
| acl-group-host / generated_0003 | propagate_group_entitlement → grant_new_object_right → obtain_admin_execution_on_host | `admin_control` on pinned target | 3 | [21/50,361/400] | High | Pareto member; native C-Min-Effort=1 |
| rbcd-scoped / generated_0001 | rbcd_configure_descriptor → rbcd_acquire_secret → rbcd_prepare_service → rbcd_delegate_service → rbcd_service_admin | `admin_control` on pinned target | 9 | [504/3125,15760899/20000000] | High | Pareto member; native C-Min-Effort=9 |
| kerberoast-material / generated_0001 | kerberoast_request | `service_ticket_material` on pinned target | 1 | [17/20,49/50] | Low | Pareto member; native C-Min-Effort=1 |
| winrm-command / generated_0001 | open_winrm_remote_session | `remote_command_execution` on pinned target | 1 | [7/10,19/20] | Medium | Pareto member; native C-Min-Effort=1 |

The independent arithmetic oracle checks every eligible native program, summing
unique canonical C work and multiplying exact full-history conditional bounds.
The chain rule does not assume event independence. Step C/P/missing reasons and
ordered history/lookup digests are published for all 159 returned occurrences.
I belongs to the successful typed terminal consequence, not each intermediate step.

## Source, policy and history pins

- Source content: `sha256:ff04cfc07cc054b445be00ae3f3c8bbab57a696203af0b483b33cb8a4d0bf2f3`.
- Raw graph: `sha256:473c0dd49efcc189ea75d16ba721d31632f08b9afc023b29a9d1d2604799c8ea`.
- Raw snapshot: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
- Snapshot facts: `sha256:974765c2d2eb4ba0eb141ba375540c7905e23e18a126e484bdd089e89055b833`.
- Profile: `sha256:0a07821f77987dadc487ebafc3de09a82a4761b9e6eaad51c63b9b35da26b3ae`.
- Exact class/work/history/typed-goal/retry domains are in the adopted release and
  each report case scope; private before/after query files preserve identities.
- Horizon remains 24h; class-specific bounded whole-event retries, deadlines,
  transports, auth/secret lineage and stop rules are unchanged.

| Query | Steps / expansions / paths cap | Exact consumed query digest |
| --- | --- | --- |
| source-a-projection | 10 / 60000 / 1000 | `sha256:596db8589ccbe5727f1bb20b1e18d81898b550e56e9b456c86733b6fa9370f8e` |
| source-a-full-raw-four | 10 / 60000 / 1000 | `sha256:9ea9bf0da493014e1fbec1a2be60b8ba3f744fd268e8b4e232852ee6210a820a` |
| source-a-full-generator | 10 / 2000 / 250 | `sha256:792b96eb045e7f1416b4d462e6c94b228e34a3114463c31c7f6a54338d9640bd` |
| lidia-full-generator | 8 / 2000 / 250 | `sha256:e1c949541644f7723f58538dad87ed05ea24561b372eb11979f3c883e0bdd6c9` |
| josefa-full-generator | 8 / 2000 / 250 | `sha256:ceb04415364c75c69ef85a3817b3d554d5108f43ad076987ac0b2721963635ee` |
| asrep-natural-password | 6 / 1000 / 10 | `sha256:d07175042452dbaa8fb01160129280d5b86af792a7e6bacd3bf815dd2ce4a1f1` |
| kerberoast-material | 4 / 1000 / 50 | `sha256:cca1848c41bc45102700995fc4cc740c8fb5bbc7f29152f0a9468e2aee0b7747` |
| kerberoast-identity | 4 / 1000 / 50 | `sha256:deec151637a7ef6d6a601f5eb94b0fe806ba6a8a8078175163eda0a8535ebb69` |
| rbcd-unassumed | 6 / 5000 / 50 | `sha256:4b6418efb137e5f13e0f288607c39f31d16760da140fa07658c562e30d7175a9` |
| rbcd-scoped | 6 / 5000 / 50 | `sha256:f63044f29cf2a583eb90a4d787c938c2948808126bdb4b3bb1bc78ababe6173a` |
| acl-group-host | 8 / 5000 / 100 | `sha256:323c6322ef6cbdb416e5a7c49f86aacea10e8fd95c112a5ef4970c3aba1c24b4` |
| acl-group-projection | 8 / 5000 / 100 | `sha256:56a7acd5fec5e1c0ff95d117737894208ec78d5e042bc71fd093ea31c6d1fabe` |
| acl-group-all-generator | 8 / 2000 / 100 | `sha256:12d151749597834c544794e4bc6a8d8fb0c13e0639ed2127268960070a6a6881` |
| winrm-command | 4 / 1000 / 50 | `sha256:12e254e9f06ae8fc7b07868bde151dde4a04c54396a27d06566bfb5ae5f14ded` |

## Ranking, sensitivity and validation

Applicable Source A P-bound perturbation to [0,1] changed the native Pareto frontier: **False**.
This demonstrates stability only for that declared query-local counterfactual.
Perturbed endpoints are test-only, not newly adopted expert values, and never
enter production coverage or release authority. Missing/FALSE terminal
conditions and a smaller step cap remove eligible results in native controls.
Native Top-K selects three reviewed Source A results while retaining complete
generated programs and coverage; its two subprocess CLI comparisons pass.
Source-ranking/chokepoint sensitivity is unmeasured. Capped searches establish
no global optimum or full-generator coverage.

Fourteen verified cases include 28 fresh after-release native CLI processes,
API/CLI outcomes/caps/guarantees/full-program/ranking/coverage parity and
orchestration search/program/ranking parity over the fields it exposes.
Changed before-release questions are freshly evaluated by the native API;
unchanged questions share their identical execution. Before CLI authority is
also preserved in the separate frozen Wave 1 report, not relabeled here.
Release CLI/API binding parity and six focused authority/recount/Top-K tests pass.

Full clean-CI suite: **3001 passed, 109 skipped, 59 subtests passed** on Python
3.14.7 (1250.41s); private/optional inputs are absent in that clean worktree.
Focused raw release/scope regressions: **24 passed** (273.69s). The earlier
raw-enabled full-suite run was interrupted and is not counted as a pass.
The existing batch scope-refusal regression also passes; broader batch ranking
acceptance is not claimed. Local validation does not imply remote CI PASS.
Final local Ruff lint/format, YAML, contract, repository, Compose configuration
and `git diff --check` pass. Six source raw files retain their manifest and exact
bytes; a scan of 3370 raw node identifiers found no occurrences in the new public
report, release artifacts or delivery documents.

## Retained-artifact check and follow-up review

[Review on #288](https://github.com/nairyuuu/ad-weighted-graph/pull/288#issuecomment-6165613747)
identified missing corruption guards in the v5 aggregation tool: it did not
reread consumed query files or the second normalized CLI output and accepted
boolean zero-like process codes. This limits the tool's acceptance robustness;
the actual retained v5 files were independently reread after that review.
[The read-only audit](../../../../reports/research/issue267-wave2-delivery-v5-retained-artifacts.json)
confirms all 14 before/after query digests match their pinned scopes, both CLI
outputs have identical typed canonical digests, and process codes are integer 0.
The historical v5 report and checkpoints remain unchanged.

[Stacked #289](https://github.com/nairyuuu/ad-weighted-graph/pull/289)
adds the guards and seven native acceptance/corruption tests, with fresh v7
evidence in its own namespace. At publication of this v5 handoff its full v7
replay is still running; this document does not claim it passed. That follow-up
is required before treating the aggregation tool as acceptance-ready. The
delivery head also wraps the release dispatch line to satisfy Ruff; this is a
format-only difference from the recorded executable implementation `c1e2cb2`.

Independent validation of #289 at
`0b23392f4aff3b12f487377717d7c4a0e25e07ec` in a separate detached worktree:
`python -m pytest tests/test_final_cpi_delivery_replay.py -q` gives **7 passed in
197.83s** with six real, manifest-verified SEAMLESS files. Ruff lint/format also
pass there. An initial fixture setup using a junction was rejected by the
manifest's root validation; the successful run uses a real directory containing
exactly those six copied files. No source or fixtures were changed for this test.
This validates the focused successor regressions, not its still-running whole
cohort replay or full suite. Neither PR was merged or approved by this check.

No observed raw edge, cohort selector/denominator, archived release or frozen
report was rewritten. Two ACL diagnostic contexts, recovery P, recovered
activation, User-goal attribution and unsupported RDP/session policy remain
open in the grouped packet. Final exact-head B code review remains required;
this delivery does not merge or close #267.
