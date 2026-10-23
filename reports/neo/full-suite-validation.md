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
The final integrated revision still needs its own remote CI result.
An unseen holdout dataset and a fresh live BloodHound comparison were not evaluated in this validation run.
