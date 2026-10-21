# Wave 2 integrated native acceptance

This successor preserves the frozen v5 and v7 evidence and applies the [delegated v4 production release](../final-cpi-release-v4/README.md).
It compares the previous scoped releases with the newly adopted bindings through the corrected native state-goal engine.
The newly returned Kerberoast User-goal history stays unbound under the old receipt; a changed history is not silently granted historical authority.
The original fourteen query selectors, actors, targets, owners, budgets and caps are retained.
Two explicit #281 recovery scenarios form their own cohort and never replace the frozen unknown-basis controls.

## Reproduce

From a stable checkout with Python 3.14 and the authorized manifest-verified `data/raw/SEAMLESS`:

```sh
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group original
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group supplementary
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group declared_recovery
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --aggregate
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m yamllint .
.venv/bin/python scripts/check_contract.py
.venv/bin/python scripts/check_repository.py
```

Private queries, graph snapshots and native outputs remain ignored under `reports/generated/issue267-wave2-delivery-v8`.
Existing checkpoints and reports are refused instead of overwritten.
Replay in a fresh detached checkout of the implementation head when the committed report already exists.
Only fresh complete checkpoints can be aggregated.
Aggregation rereads both actual consumed queries and both normalized CLI results, verifies integer-zero exit codes and literal public success flags, reconstructs exact release/query/cohort/graph/source/runtime scope, and independently recounts the native C/P/I ledgers.
CLI repetitions do not enter path denominators.

The arithmetic oracle reuses the existing independent C sums and `Fraction` chain products with only the two reviewed model intervals substituted for the unknown recovery entries.
Ranks use the existing conservative interval Pareto contract; overlapping intervals remain incomparable, and minimum effort stays a separate measure.
Per-action blockers distinguish missing numeric basis, missing policy, mismatched context/history, known-FALSE semantic prerequisites, goal attribution and search truncation.
The [results](results.md) state the measured coverage, ranking evidence and remaining limits.

GitHub CI is excluded from acceptance at the human user's request because billing is broken.
Local verification remains required.
Final B code review is requested on the exact delivered head; numeric adoption is already authorized within the receipt's scope.
No merge or closure of #267 is performed.
