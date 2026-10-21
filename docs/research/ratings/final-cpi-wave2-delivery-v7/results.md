# Wave 2 native production acceptance baseline

This immutable baseline consumes B's four-context decision and precedes the broader [human-user delegated approval](https://github.com/nairyuuu/ad-weighted-graph/issues/267#issuecomment-6166280449).
Its source head is `0b23392f4aff3b12f487377717d7c4a0e25e07ec`.
Source-content digest: `sha256:6634940934fea4aa2702d23020ed094c59aae1b9db3e60b65ef1778a478b3452`.
The generated [public report](../../../../reports/research/issue267-wave2-delivery-v7.json) records the full source/runtime/dependency identity, unchanged releases, exact query/cohort/graph pins and per-action ordered histories.

## Actual production coverage

Each C/P/I numerator below requires the whole returned path to be rated in that dimension.
All three dimension counts, full C/P/I and Pareto eligibility equal the listed full-rated counts in this baseline.
Denominators are frozen query-program occurrences, with projection/raw overlap retained and CLI repeats excluded.

| Cohort | Generated / feasible | Before full C/P/I | After full C/P/I | Truncated queries |
| --- | ---: | ---: | ---: | ---: |
| Original, all | 50 / 50 | 48/50 | 49/50 | 4 |
| Original, raw subset | 26 / 26 | 24/26 | 25/26 | 4 |
| Supplement, supported raw | 7 / 7 | 0/7 | 7/7 | 1 |
| Supplement, all diagnostics | 109 / 109 | 0/109 | 7/109 | 3 |
| Supplement, raw subset | 9 / 9 | 0/9 | 7/9 | 2 |

The wider 102-path deficit consists of 100 ACL projection paths and two raw ACL all-generator paths in the two context/history domains withheld by B at this baseline.
It is a real full-path ranking gap rather than 102 missing numeric classes.
The later delegated approval authorizes an explicitly versioned successor; this frozen report is not relabeled with that authority.
Capped samples do not establish whole-graph coverage or a global optimum.
Node/edge coverage and path-rating coverage are different measures.

## Representative native paths and ranking

| Case | Full-rated before -> after | Independently checked native C / P / I |
| --- | ---: | --- |
| Reset, Source A projection | 24 -> 24 | C=2; first reset/activation/passive membership/elevated WinRM program P=[9/40,8379/10000], High |
| ACL/Group host administration | 0 -> 3 | Direct/passive host programs C=1, P=[3/5,19/20], High; grant-right program C=3, P=[21/50,361/400], High |
| RBCD, three generated orders | 0 -> 3 | Each consumes all five events; C=9, P=[504/3125,15760899/20000000], High |
| WinRM command | 0 -> 1 | C=1, P=[7/10,19/20], Medium; no administrative control granted |
| Kerberoast material | 0 -> 1 | C=1, P=[17/20,49/50], Low |
| AS-REP natural-password control | 0 -> 0 | Recovery C=2 bound; recovery P has no matching population/work-floor basis; other history bindings withheld at this baseline |
| Kerberoast User identity control | No returned path | Successful activation state exposes the existing User-goal attribution defect; recovery P lacks basis and activation/history bindings are withheld |

The native conservative Pareto frontier retains the three ACL programs because their P intervals overlap.
Effort is a separate minimum-effort baseline; it does not break overlapping-interval ties.
RBCD's three event orderings have equal C/P/I and remain incomparable under the existing interval contract.
API, two CLI processes and orchestration agree on their exposed full programs, coverage and rankings.
Independent `Fraction` arithmetic checks all 56 eligible query-program occurrences.
Recomputation using the existing native frontier helper matches every saved frontier.

Source A's query-local widening test preserves its frontier.
Removing its terminal declaration, supplying authoritative FALSE, or imposing the two-step cap yields no returned goal path.
This test does not measure B-owned source aggregation, remediation counterfactuals or chokepoint sensitivity.
Unassumed RBCD remains not generated with unresolved policy/runtime prerequisites.
RDP/HasSession have no supported raw relations/policy in this snapshot and do not enter the frozen path denominators.

## Reproduction and regression verification

All fourteen native cases completed, with 28 public CLI processes and 159 returned query-program occurrences.
Aggregation independently reconstructs every scope, rereads both consumed queries and both normalized repetitions, and recounts native ledgers before publishing.
The final self-review confirms current source/runtime pins, unchanged programs, exact native frontiers, arithmetic oracle counts and zero public matches against all 3,370 canonical raw node IDs.
Private exact queries/snapshots/native programs remain ignored.

Six real-checkpoint corruption cases reproduce the prior aggregate defects: changed before query, changed after query, missing repetition, different repetition, boolean effort replacing integer effort, and boolean process codes.
All seven native aggregate regressions pass after the fix, including the positive control.
Stable full regression: **3,105 passed, 12 skipped, 59 subtests**, in 1,204.79 seconds with Python 3.14.7.
An earlier interrupted run differed only in Git revision/working-tree metadata because a commit occurred between its two CLI captures.
The affected CLI regression passed with a stable checkout, followed by the complete stable suite above.

Ruff lint/format, YAML, repository/contract and whitespace checks passed.
The independent reviewer cleared the aggregate fixes at `0b23392`; the completed report received author self-review.
Remote #289 checks were absent at this head, so no remote CI PASS is claimed.
Prior #271 CI billing failures remain separate from this executed local evidence.
Final integration/code review and issue closure are separate gates.
No merge or closure of #267 was performed.
