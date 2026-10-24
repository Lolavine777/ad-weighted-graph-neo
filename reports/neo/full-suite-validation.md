# Full-suite validation after the catalog extension

Recorded 2026-10-23T17:20:07.332852+00:00 from base `c0200dd`, using Python 3.14.7.
The validation changes were tested in an isolated worktree with a fixed source snapshot.
[Structured results and evidence hashes](full-suite-validation-results.json) record the tested files, diagnostic runs, and integration parent.

| Check | Result |
| --- | --- |
| Isolated full suite | 3852 passed, 8 skipped, 99 subtests passed in 739.53s (0:12:19) |
| Raw-data opt-in and new archive regressions | 58 passed in 14.60s |
| Ruff, formatting, YAML, repository, contract, Compose configuration | All passed |
| Existing runtime/configuration and frozen evidence | 387 files byte-identical to the baseline |
| Independent review | No remaining blocking findings; reconstructed receipt exactly equals the published receipt |

The baseline stopped during collection with two catalog-digest errors.
The first diagnostic run after restoring collection exposed 57 failures and 131 setup errors.
Two later diagnostic runs were intentionally interrupted once their shared scope/signature causes were confirmed; their actual counts and logs remain in the structured record.

The historical catalog and three Week 4 harness/test sources are archived with their exact published hashes.
The old suite JSON, source manifests, expected outputs, rating proposals, and numeric decisions retain their original bytes.
Historical source pins certify those archived bytes; the current tested source has a separate hash snapshot.

Golden and integration checks permit an unrelated action addition only when the selected original definitions and global catalog metadata remain unchanged.
Published rating checks derive their owner scope from the hash-verified archive and reject changes to every covered live definition.
The historical “all 23” selectors now use the frozen taxonomy instead of automatically including later actions.
The numeric receipt retains its original catalog input pin only after that compatibility check; executable replay evidence still hashes the live catalog and source code.
The reconstructed delegated receipt has the exact unchanged canonical digest `sha256:f180932d25e60108e62a5bee71daeac99f5a0657e13bd73c2fcf5dd9aa250aa0`.

The old likelihood and CPI packages cover 23 actions, including one passive action.
The current `use_session_identity` action remains outside their published rating coverage and is explicitly reported as such.
This work does not authorize a new numeric rating or establish new measured probabilities.

The local evidence namespace is `reports/generated/neo-full-suite-20261023T1606Z/`.
Reproduce the default suite with `.venv/bin/python -m pytest -q`; the structured record includes the full opt-in raw-data command and all quality commands.
The source remained unchanged during the isolated run, and all 17 validation files matched the integrated checkout before recording the result.
Concurrent remediation files from another chat were excluded from that isolated run and from this change.
For commit `0f8baf8`, Linux CI passed; Windows emitted portability failures and exceeded the 15-minute job limit.
An unseen holdout dataset and a fresh live BloodHound comparison were not evaluated in this validation run.

The Windows follow-up normalizes numeric-receipt path keys to POSIX separators, makes test file/CLI decoding explicitly UTF-8, and injects a permission error instead of relying on platform-specific chmod behavior.
Two additional frozen artifact directories now retain exact Git blob bytes during Windows checkout.
The checkout regression reproduces the original `parameter-decisions-final.json` digest mismatch before that attribute fix and passes afterward.
The test job limit is now 30 minutes; no test or semantic budget was reduced.
Follow-up checks passed: 39 native release/delivery tests, 157 affected tests, 45 public integration tests, and 29 source/archive checks; these sets overlap.
The public CLI/API comparison also passes with a simulated Windows default decoder, and the Windows-shaped receipt signature matches the original published signature.
The full-suite result above retains its original source snapshot; the follow-up has separate source and evidence hashes in the structured record.
Remote CI for the follow-up revision was pending when this record was written.

The completed [CI run on `e261412`](https://github.com/Lolavine777/ad-weighted-graph-neo/actions/runs/40057048164) passed Linux (3723 tests, 147 skips), quality, and Compose; Windows finished with 13 failures, 3709 passes, and 148 skips.
All 13 Windows failures were reproduced locally through existing offline regression tests using cp1252 defaults for file and subprocess text decoding, plus Git's actual `core.autocrlf=true` checkout conversion.
Explicit UTF-8 decoding repairs the JSON and pipe comparisons, while a `-text` attribute preserves the original pinned remediation catalog bytes.
The repaired reproduction passed all 14 cases, and the expanded affected modules passed 187 tests with one raw-data prerequisite skip under the same decoder simulation.
The current source manifest was refreshed through its generator, and independent review found no blocking findings.
These are local portability checks; updated Windows CI remains pending.

Five raw-data opt-in tests were also exercised on the six manifest-verified SEAMLESS files.
The first attempt recorded four passing tests and one assertion failure because guided acceptance returned `BLOCKED`, with 19 acceptance checks passing and no failed acceptance checks.
Case B lacked its explicitly required source and target labels; no substitute nodes were selected.
The opt-in test now requires the three inputs already documented in the guided-exploration guide before invoking acceptance.
The recheck passed four tests and explicitly skipped guided acceptance for the missing labels; that skip does not turn the retained blocked runner result into a pass.
All six raw files remained byte-identical, and the blocked evidence was preserved in the unique local namespace `reports/generated/neo-validation-20261024T0311Z/`.
Configured guided Case B acceptance and the unseen holdout evaluation remain pending.

Remote CI is now confirmed on exact commit `2566a96`: [all four jobs passed](https://github.com/Lolavine777/ad-weighted-graph-neo/actions/runs/40059055795).
Linux completed with 3723 tests passing and 147 skips in 673.25s; Windows completed with 3722 tests passing and 148 skips in 1281.77s.
These default-suite runs retain their platform and private-input prerequisite skips; they do not replace the separately recorded local raw-data checks.

The guide already provided explicit labels for its historical Baseline Case B example, which were missed in the previous prerequisite assessment.
Using that documented configuration on the pinned SEAMLESS fixture, the unchanged guided acceptance module passed all three pytest tests in 34.29s, and the runner passed all 24 acceptance checks without blocked or failed checks.
All six raw files remained byte-identical, and private artifacts were copied into the unique local namespace `reports/generated/neo-validation-20261024T0814Z/` with a complete artifact hash manifest.
This confirmation clears the current Windows CI and configured Case B blockers; earlier failures, blocked results, and source snapshots remain intact in their original evidence phases.
No production code or numeric ratings changed in this confirmation.
The unseen holdout remains pending a new authorized export; no fresh live BloodHound comparison was run in this phase.
