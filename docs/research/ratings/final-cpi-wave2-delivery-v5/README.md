# Wave 2 adopted subset and native delivery

Refs #267, #271, #277, #282, #281. This delivery consumes the actual
[B context/history decision](https://github.com/nairyuuu/ad-weighted-graph/pull/271#issuecomment-6163909537),
dated 2026-10-14 08:11:04 UTC, against candidate head
`b91a787ef2a59247536452cfeb8ebbf3f15963d4`.
The [17 numeric class values](https://github.com/nairyuuu/ad-weighted-graph/issues/267#issuecomment-6142406787)
remain unchanged. Provenance is `estimated_expert_scenario` throughout.

## Production authority

The new [adopted Wave 2 artifact](../final-cpi-release-v2/decisions.adopted.json)
adopts exactly `winrm-command`, `acl-group-host`, `rbcd-scoped`, and
`kerberoast-material`, with their existing typed consequences and exact finite
history inventories. The pending candidate, Wave 1 release, prior replays,
cohorts, raw manifest and archived ratings remain preserved.

The [dimension-scoped effort artifact](../final-cpi-release-v3/decisions.adopted-c-scoped.json)
records the existing C decision separately from P/I/history authority. The final
delivery runner uses that overlay only for the two withheld roasting identity
contexts, preserving approved recovery C=2/3 without approving recovered activation
or recovery P. It leaves both withheld ACL diagnostic contexts unchanged.
The effort-only artifact cannot accept a changed query or grant P/I authority.
The earlier `decisions.adopted-c.json` remains preserved as a preparation artifact;
the current validator refuses it. The scoped 1.1.0 successor is the active C-only
artifact and direct CLI calls cannot bypass the withheld diagnostic boundary.

Existing `final_cpi_release.apply_release` overlays native registry envelopes
before search. Both the release CLI and Python callers consume these envelopes;
`run_attack_query`, `src.engine.query_cli`, and native orchestration perform the
actual search, replay, scoring and ranking. No candidate lists are supplied.
The new code adds no transition evaluator, search algorithm, observed edge or
capability. Canonical work identity deduplication, policy/transport/lineage
checks and native known-FALSE vetoes remain effective.

Conditional intervals cover the whole bounded event under the reviewed 24h
campaign horizon, class-specific retries/deadlines and stop rules. They are not
independent trial probabilities. SMB/RPC host administration, elevated WinRM,
non-admin command execution and RBCD service lineage stay distinct.
Directory mutation alone does not grant a usable token or host control.
RBCD must complete all five events before its administrative consequence.

## Reproduce

Use Python 3.14 with the repository requirements and the authorized, manifest-verified
SEAMLESS directory. Replay v5 in a fresh detached worktree at its executable
implementation `c1e2cb2` so no retained checkpoint or published report is present.
In PowerShell, replace `$taskPython` and `$taskRaw` with the authorized environment
paths. The commands preserve the frozen cohort selectors, source/target/profile,
budgets and caps.

```powershell
git worktree add --detach ../issue267-v5-reproduce c1e2cb2
Set-Location ../issue267-v5-reproduce
$taskPython = 'E:/copy-ad-weighted-graph/ad-weighed-graph/.venv/Scripts/python.exe'
$taskRaw = 'E:/copy-ad-weighted-graph/ad-weighed-graph/data/raw/SEAMLESS'
& $taskPython -m scripts.research.final_cpi_delivery_replay --raw-dir $taskRaw --group original
& $taskPython -m scripts.research.final_cpi_delivery_replay --raw-dir $taskRaw --group supplementary
& $taskPython -m scripts.research.final_cpi_delivery_replay --raw-dir $taskRaw --aggregate
```

For a single case, add `--case winrm-command`, `--case acl-group-host`, or
`--case rbcd-scoped` to the supplementary command. Existing verified checkpoint
and report destinations are refused; preserve published evidence and choose a
new namespace for another complete replay. A partially executed case without a
verified checkpoint can be rerun. Aggregation re-derives every query and graph,
checks source/runtime/dependency/release/cohort/snapshot identity, verifies public
transport success and independently recounts saved native ledgers before publishing.

The private artifacts in `reports/generated/issue267-wave2-delivery-v5` include
exact before/after queries, canonical graph/snapshot facts and normalized native
CLI programs/ratings. Public evidence uses hashes for raw actor/resource/target
identities and ordered full histories. A native P prefix includes the outcome
work identity as its final element; preceding elements are the conditioning H.
CLI repetitions verify determinism and never enter a coverage denominator.

API/CLI parity compares exposed semantic outcomes, goal flags, caps, guarantees,
ordered full programs, ranking and coverage. Orchestration parity compares its
exposed search/program/ranking fields. Independent arithmetic sums C once per
canonical work unit and multiplies exact conditional bounds with `Fraction`;
it verifies native output without implementing another evaluator.

## Coverage and evidence interpretation

The original, seven-path supported raw supplement and 109-path supplementary
diagnostic scope retain their own frozen denominators. Family counts overlap.
The original cohort deliberately contains projection/raw overlap; these are
query-program occurrences, not independent observed attacks.
Results, five worked programs, acceptance table and validation are published in
[results.md](results.md). The v5 retained files pass a separate read-only audit;
the aggregation corruption-guard review and fresh successor evidence are tracked
in stacked [#289](https://github.com/nairyuuu/ad-weighted-graph/pull/289).
Use that successor for acceptance after its replay completes. V5 remains frozen
evidence of the original execution and does not claim those guards were present.

Raw-backed topology is separate from declared runtime scenario conditions.
In particular, RBCD HTTP/SPN/runtime conditions remain scenario declarations,
not observed raw SPN proof or observed exploitation. RDP/HasSession have no
supported policy binding or raw edges in this snapshot. Their numeric proposals
do not create paths. `not_generated`, `truncated`, `unrated`, and known-FALSE
`not feasible` outcomes are distinct in the native blocker matrix.

The [remaining grouped packet](B-decision-packet.md) contains only withheld
context/history and missing-basis questions. The adopted four-context subset
requires neither another numeric vote nor per-path approval. Natural-password
recovery P, recovered activation, User-goal attribution and broader source/batch
or chokepoint sensitivity remain explicit limitations. No global optimum is
claimed from capped search. This delivery does not merge or close #267.
