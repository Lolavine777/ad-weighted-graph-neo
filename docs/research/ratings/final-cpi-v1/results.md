# Final C/P/I evidence and remaining acceptance gates

Owner A / @Lolavine777; B cross-review/adoption pending.
Refs #267, #265, PR #271; AS-REP correction remains exclusively in PR #266.

**Actual accepted full-rated coverage is 0/50 (0%), so the production 80% requirement is not achieved.**
The synthetic wiring derivative reaches 49/50 (98%) among the returned programs, with four truncated queries and duplicated projection/full-raw comparisons.
The raw-only query subset contains 26 returned programs and 25 fully rated synthetic derivatives; this secondary 25/26 measure still does not establish snapshot-wide coverage.
The full raw graph contains 3370 nodes and 56367 edges, but running on the full graph does not mean the search enumerated all paths or sources.

| Frozen query | Valid / conditioned feasible | Accepted C/P/I-complete | Synthetic C/P/I-complete | Synthetic fully rated / eligible | Truncated / gap |
| --- | --- | --- | --- | --- | --- |
| `source-a-projection` | 24 / 24 | 0/0/0 | 24/24/24 | 24 / 24 | complete declared scope |
| `source-a-full-raw-four` | 23 / 23 | 0/0/0 | 23/23/23 | 23 / 23 | expansion_limit_reached |
| `source-a-full-generator` | 0 / 0 | 0/0/0 | 0/0/0 | 0 / 0 | expansion_limit_reached |
| `lidia-full-generator` | 1 / 1 | 0/0/0 | 1/1/1 | 1 / 1 | expansion_limit_reached |
| `josefa-full-generator` | 0 / 0 | 0/0/0 | 0/0/0 | 0 / 0 | expansion_limit_reached |
| `asrep-natural-password` | 1 / 1 | 0/0/0 | 1/0/1 | 0 / 0 | complete declared scope |
| `kerberoast-material` | 1 / 1 | 0/0/0 | 1/1/1 | 1 / 1 | complete declared scope |
| `kerberoast-identity` | 0 / 0 | 0/0/0 | 0/0/0 | 0 / 0 | B User-goal endpoint attribution gap |

The all-technique Source A and Josefa queries return zero programs at 2000 expansions; their rating fraction is undefined, and they are not safe/no-attack results.
The Lidia all-technique query returns one program at the same cap.
The full-raw four-technique Source A query returns 23 programs at 60000 expansions and has no global minimum certificate.
Only the seven-node, sixteen-edge projection is complete for its declared four-technique query, with 24 programs and a proven C minimum of 2 in the synthetic test.
The Kerberoast User-identity query returns no program even though native activation satisfies the requested state; its final endpoint is the authentication Computer, which differs from the declared owner-User target.
The original frozen target/goal is preserved and that B-owned attribution gap is disclosed, not hidden by retargeting.

## Before/after and five worked programs

The historical Source A transfer gate was freshly reproduced through the existing public engine: 2/24 fully rated, C complete on all 24, I=High for the same typed DC consequence.
The new finite-history domain reproduces all 24 with complete numbers only in the quarantined synthetic derivative; pending production records still yield 0/24.
Historical Week 4 AS-REP remains C=3/High/P=0/4; current #266 V2 remains raw P=0/4 and synthetic P=3/4, with no path product.

| Genuine generated program | Ordered operations | C | Exact conditional P interval | Typed I |
| --- | --- | --- | --- | --- |
| `generated_0001` | reset_lidia -> activate_lidia -> passive entitlement closure -> winrm_badblood_lidia | 2 | [9/40, 8379/10000] | High |
| `generated_0002` | reset_josefa -> reset_lidia -> activate_lidia -> passive entitlement closure -> winrm_badblood_lidia | 3 | [27/200, 159201/200000] | High |
| `generated_0004` | reset_josefa -> reset_lidia -> activate_josefa -> activate_lidia -> passive entitlement closure -> winrm_badblood_lidia | 3 | [81/800, 7800849/10000000] | High |
| `generated_0006` | reset_josefa -> activate_josefa -> passive entitlement closure -> reset_ollie -> activate_ollie -> passive entitlement closure -> winrm_badblood_ollie | 3 | [81/800, 7800849/10000000] | High |
| `kerberoast-material` | request compatible TGS material for the fixed SPN owner | 1 | [17/20, 49/50] | Low |

These are generated programs assessed under synthetic wiring gates, not observed exploitation or B-adopted probabilities.
The different reset targets and ordered histories are retained; passive closure contributes no C or q.
No per-path candidate or ranking packet was supplied.

## Sensitivity and limits

Widening all Source A intervals to [0,1] keeps all 24 on the frontier because the original intervals already overlap; C-Min-Effort remains 2.
Removing terminal declarations yields no goal-reaching programs and native indeterminate status.
Authoritative FALSE terminal facts veto every listed terminal route; global native status remains indeterminate because other attempted transitions still have unknown prerequisites.
A two-step cap yields zero returned programs with truncation, not a no-path proof.
Batch source ranking and remediation/chokepoint counterfactual sensitivity remain B-owned and were not measured here.

The generated goal-reaching paths exercise 8 of 20 active likelihood classes; taxonomy completeness is 22 active techniques plus passive MemberOf, not measured coverage of every class.
The exercised families are: asrep_material_request, asrep_password_recovery, directory_password_reset, host_admin_execution, kerberoast_material_request, recovered_identity_activation, reset_identity_activation, winrm_admin_execution.
Raw RBCD bindings, HasSession extraction and additional ACL/group cases remain unrepresented in this pilot.
Group login and Domain/OU/GPO initial-compromise profiles remain unsupported until B defines valid source capabilities.
Natural AS-REP/TGS recovery has no defensible rank/achieved-compute basis and remains specifically unrated.

## Verification and B handoff

Consumer execution commit: `3a11d6bf5c8cae6c5788316c5aaba5d50a188bf9`.
Cohort digest: `sha256:e8fc2757054890209e0ab5112f261470ecbe11f8c76cf3c0ce3c7da350819003`.
Profile digest: `sha256:0a07821f77987dadc487ebafc3de09a82a4761b9e6eaad51c63b9b35da26b3ae`.
32 successful CLI processes (two runs in each pending/synthetic mode across eight frozen queries) match normalized outcomes, ordered programs, full ranking and full coverage; API and orchestration match each case.
Native attempt traces were transient because one full-raw output exceeded 700 MB; normalized private artifacts and native-file digests are retained in ignored local output.
47 historical rating/scenario files were byte-checked before/after; Git diff confirms all other frozen and B-owned source/config bytes are unchanged.
Final full suite: **2609 passed, 9 skipped, 48 subtests passed**, 441.62s.
The six focused tests include RED/GREEN real Kerberoast wrapper regressions, native artifact Low impact, pending refusal and synthetic-production quarantine.
Ruff, format, contract, repository/privacy/link and diff checks passed locally.
Remote CI is checked separately and is not claimed successful.

B must decide numeric/context adoption per class group, the stable/no-depletion conditional-history equivalence, public basis/review labels, User-goal attribution, and wider source/search/counterfactual integration.
All numeric proposals remain pending and both PRs stay unmerged; the 80% production gate and full-generator evidence remain open.
