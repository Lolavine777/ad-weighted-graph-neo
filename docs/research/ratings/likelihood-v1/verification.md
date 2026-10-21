# Likelihood Catalog v1 verification

This is a sanitized local verification record for #256, not B numeric acceptance or final Week 4 acceptance.
Private raw inputs, full coverage traces and runtime identities are not committed.

## Freeze and execution provenance

- Develop baseline after #254 merge: `94db074b5cd5c74b76b5e2555d59c5a952153b7e`.
- Initial independent input/basis/oracle freeze: `9a197e8`.
- Complete dependency freeze and runner committed before first demo execution: `8fa2ba4`.
- Exact context/provenance negative checks: `e7bd7ce`.
- Final executable revision tested after rebase: `0df96a1fef4fae93d1e42bbfe53a7aec1c74d85c`.

Rebasing refreshed the resolver/provider source pins and added the merged #254 proposal pin.
The active action definitions, eight binding identities, source q records and frozen oracle bytes did not change.
The final follow-up commit contains only documentation and this report.
All checks ran with the existing checkout's `.venv` Python 3.14.7 on macOS.

## Checks

- Complete suite with private #256/#254 inputs: **2,508 passed, 12 skipped, 48 subtests passed** in 236.46s.
- New package tests with manifest-verified private inputs: **27 passed**.
- Focused package and merged P provider regressions: **137 passed**.
- All three frozen generated demo probes passed at the final executable revision.
- Ruff lint and format checks: passed for all 401 Python files.
- YAML lint, repository checks, contract plus two synthetic fixtures, Compose configuration and `git diff --check`: passed.

The 12 skips cover unavailable worktree-local telemetry/legacy raw datasets and macOS/Windows filesystem differences.
The private #256 Source-A/#243 and #254 regression cases used `SEAMLESS_RAW_DIR` and executed successfully.

An earlier full run with uncommitted tracked changes failed four existing CLI acceptance assertions because `clean_tracked_source` was false.
The public CLI reproduced that exact packaging gate; semantic results matched.
Committing the package restored clean-source eligibility without rewriting the acceptance manifest or product code.
The final full-suite result above supersedes that run.
An older-base rerun was stopped when #254 merged and was not recorded as passing.

## Generated results

| Frozen package | Observed result | Numeric status |
| --- | --- | --- |
| Synthetic-a2 Min-Effort | Three generated candidates; C multiset `[2,5,5]`; minimum 2; one shared preparation; passive closure creates no active work or q | Scoped test-only acceptance simulation; actual pending C remains null |
| Source-A risk | 23 generated candidates; two exact historical programs found after generation; 21 unreviewed; 60,000 expansions; `expansion_limit_reached` | Original accepted #181 bridge evaluates the generated reviewed subset; all eight expanded pending bindings refused |
| Frozen #243 | Original four active events, unchanged false DA checkpoint and unmeasured recovery budget; proposed C `[0,2,0,1]` | All four P events remain unrated; scoped C/I proposals pending |

The independent risk expectations are `[9/40,8379/10000]` and `[81/800,7800849/10000000]` with High impact.
The canonical adapter matches both exact Fraction products and the frozen nondominated set.
Their intervals overlap, so neither dominates; the C=2 versus C=3 minimum applies only to the reviewed subset.
No engine result authored or rewrote the candidate-independent input or oracles.
No exhaustive search, global Min-Effort or global Pareto claim follows from the capped Source-A run.

Every pending expanded prefix matches its frozen lookup-key digest and reports the merged provider's explicit pending-review refusal, not merely a missing interval.
This confirms non-activation; it does not certify accepted-record runtime applicability.
#250 must supply independently validated per-event provider scope for capability, target class, control scope, retry policy and population after B decisions.
The pending proposal is not a source of runtime truth.
The default providers and accepted release are unchanged.

## Review and remaining gates

Self-review checked the complete inventory, canonical events, producer ownership, exact full-history keys, untouched historical evidence, C/I scope and generated provenance.
Independent read-only review reproduced the package and generated cases and found no concrete issue.
Its recommendation to assert the precise pending-review provider trace was implemented and verified.

B review is still needed for eight P equivalence/applicability proposals, ten scoped C recommendations and the directional same-asset #243 I decision.
#250 owns public automatic consumption and validated runtime context; #251 owns independent generated CLI cross-reproduction and final acceptance.
Frozen #243 can remain P-unrated.
Neither numerical activation, merge, remote CI PASS nor Windows execution is claimed here.

## #250 integration amendment — 10/10/2026

PR #258 consumes develop after #257 at `036255ecd4b738f9e571cdb36dacdb49a25907f5`.
The only catalog source-pin change is `src/engine/ranking/resolver.py`:
`sha256:862346916655085b1c64427146aa080b18838839ed7dbf72d079a7334e09f1ea`
is replaced by the #250 resolver source from `09d6f9ae32e1219b283d0bd5bd3c33b2700dbb68`.
Its delta adds `(candidate_id, step_index)` binding lookup before the existing
four-part transition identity fallback, and extends the corresponding type hints.
The catalog file digest in `manifest.json` is updated for that explicit source-pin amendment.

Action definitions, all eight proposed P bindings, numeric intervals, release
dispositions, independent oracles and min-effort input bytes are unchanged.
The package still activates zero numeric records and refuses pending provider records.
This amendment is integration provenance, not a new numeric acceptance or a
rewrite of the historical verification results above. Exact-head checks for
this integration are recorded on PR #258.
