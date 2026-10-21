# Wave 2 production acceptance successor

This acceptance follows [B's draft #288](https://github.com/nairyuuu/ad-weighted-graph/pull/288), implementation head `d441e13cab347d8b0bb61b1ab50bc0c4242a5ca7`, stacked on [#271](https://github.com/nairyuuu/ad-weighted-graph/pull/271).
It consumes [B's actual four-context decision](https://github.com/nairyuuu/ad-weighted-graph/pull/271#issuecomment-6163909537) without another numeric vote.
The adopted release, exact query/history pins, scoped recovery C-only artifact, engine providers, search and goals remain unchanged.

The delivery aggregator now rereads the saved before/after consumed queries, compares canonical digests of both normalized CLI repetitions and requires integer-zero process codes.
Six corruption regressions use a genuinely generated native SEAMLESS WinRM checkpoint.
The previous aggregator accepted all six corruptions; the successor must reject each before publishing.
The fresh v7 namespace preserves v5 artifacts, partial v6 checkpoints and every earlier release and report.

## Reproduce

Use the repository Python 3.14 virtual environment and the authorized manifest-verified `data/raw/SEAMLESS` directory.
Run from the repository root, with the frozen cohorts, query inputs, budgets and caps unchanged.

```sh
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group original
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --group supplementary
.venv/bin/python -m scripts.research.final_cpi_delivery_replay --raw-dir data/raw/SEAMLESS --aggregate
.venv/bin/python -m pytest -q tests/test_final_cpi_delivery_replay.py
.venv/bin/python -m pytest -q
```

Public acceptance is `reports/research/issue267-wave2-delivery-v7.json`.
Ignored private artifacts in `reports/generated/issue267-wave2-delivery-v7` retain exact queries, snapshots and normalized native results.
Existing verified checkpoints and public reports are refused rather than overwritten.
API/CLI/orchestration parity, independent rational arithmetic, exact ordered history digests and native ledger recount reuse the existing harness.
CLI repeats never enter cohort denominators.

The [results](results.md) distinguish original query-program occurrences, supported raw supplement and broader diagnostics.
The [existing consolidated B packet](../final-cpi-wave2-delivery-v5/B-decision-packet.md) remains the precise list of withheld applicability/history and missing-basis decisions.
No further approval is needed to use the four adopted domains.
Final exact-head code review, integration/merge and broader Week 5 acceptance remain separate from numeric adoption.
No merge or closure of #267 is authorized by this evidence.
