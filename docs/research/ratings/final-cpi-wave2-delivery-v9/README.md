# Wave 2 final integrated native replay

This successor verifies the [v5 production receipt](../final-cpi-release-v5/README.md), preserves the intermediate v8 report, and retains the original fourteen selectors plus two separately declared recovery scenarios.
It uses the existing production resolver, semantic replay, exact rational chain and conservative interval Pareto ranking.
The original actors, targets, owners, budgets and caps remain unchanged.
CLI repeats and projection/raw overlap are disclosed explicitly.

Use Python 3.14 through the repository virtual environment and authorized manifest-verified `data/raw/SEAMLESS` inputs.
Existing receipts, checkpoints and reports are refused instead of overwritten.
For a committed report, reproduce in a fresh detached checkout of its implementation head.

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

Private exact queries, snapshots and normalized native results remain ignored under `reports/generated/issue267-wave2-delivery-v9`.
Aggregation reconstructs release/query/cohort/graph/source/runtime scope, reads both actual consumed queries and both CLI repetitions, rejects boolean process codes and counts, and independently recounts native C/P/I ledgers.
The arithmetic oracle and native frontier recomputation require every eligible result to agree with the reviewed values and ordered full histories.
The [results](results.md) record final verification and remaining limitations.
GitHub CI is excluded at the user's request because billing is broken.
Final exact-head B code review, merge and closure remain separate from numeric adoption.
No merge or closure of #267 is performed.
