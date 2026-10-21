# Wave 2 delivery v11 reproduction

This successor addresses review 5521576917 on PR #289.
The declared typed semantic goal accompanies every generated ranking candidate, including RBCD paths whose terminal action endpoint equals the goal asset.
Native replay verifies the complete state and records exact typed-goal satisfaction for every prefix; first-hit ranking rejects a retained prefix that fails that goal.
Declared relationship state accepts both the existing triples and the engine's canonical `source/kind/target` wire objects, with extra fields rejected.
Approved numeric assumptions and all historical releases, receipts, cohorts and v9 artifacts remain frozen.

The implementation and acceptance plan is:

1. Reproduce the same-endpoint RBCD failure at descriptor and delegated-context prefixes, then verify the complete admin goal as a positive control.
2. Bind the materialized descriptor at the manual and automatic packet boundaries, require native typed proof at adaptation/validation, and retain all existing fail-closed checks.
3. Generate new current-source and Week 4 acceptance successors without rewriting earlier artifacts.
4. Commit the corrected executable, then replay all sixteen original, supplementary and separately declared recovery cases through 32 public CLI processes plus API/orchestration checks.
5. Aggregate by re-reading consumed queries, both normalized repetitions, exact integer exit codes and numerical ledgers; audit source/runtime, histories, frontiers, denominators and frozen artifacts.
6. Publish the new evidence pinned to that executable revision, reply to every current finding and request B rereview on the final exact head.

Use a clean checkout of the executable revision recorded in the v11 report with an existing virtual environment and authorized manifest-verified SEAMLESS inputs.
The public runner refuses dirty tracked source, existing checkpoints and an existing output report.

```sh
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group original
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group supplementary
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group declared_recovery
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --aggregate
.venv/bin/python -m pytest -q tests/test_rbcd.py tests/test_public_rating_integration.py tests/test_final_cpi_delivery_replay.py
```

Local private queries, graph bindings and normalized repetitions are retained in ignored `reports/generated/issue267-wave2-delivery-v11`.
The successor report records the actual executable checkout and its complete source/runtime identity.
Inherited #288 checks verify both consumed query files, both normalized repetitions, exact integer `[0, 0]` CLI exit codes and native ledger denominators.
Their corruption regressions remain active, with a new wrong-revision refusal check.
GitHub CI is excluded because billing is broken, as requested by the user.
No merge or closure of #267 is authorized by this packet.

The final fix also binds the typed descriptor and conjoins its state requirements in the manual generation wrapper.
Partial v10 checkpoints from the earlier executable remain preserved privately; they are not final acceptance evidence.
The Week 4 semantic evidence successor changes exactly nine output digests while preserving every frozen normative field and the original fixture byte-for-byte.
