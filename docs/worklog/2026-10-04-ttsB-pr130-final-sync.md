# Worklog — 2026-10-04 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#121](https://github.com/nairyuuu/ad-weighted-graph/issues/121), [PR #130](https://github.com/nairyuuu/ad-weighted-graph/pull/130); historical compatibility follow-up
- Thời gian thực tế ước lượng: không ghi nhận

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Sync shared PR branch | `git merge --no-ff origin/develop`; base `8a1ce0c28b7491fa2266314c56bbb03035bf1ab7` | Merge commit `bd5b33ae6b3df50564e3479b0795c795cf68ba3a`; no conflicts; #130 report, baseline, and #139 source evidence preserved |
| Recheck machine-readable evidence | Parse baseline and #139 JSON; compare snapshot/manifest/runtime pins, Group counts and digests, discrepancy sets, label/type sums, corrected Base-only predicate, and unknown counters | Both runs retain 3,370 nodes, 71,596 relationships, 551 Groups and Base-only zero; 550 raw Group records / 549 IDs plus two measured placeholders; write-error and rejection counts remain `null` |
| Local repository checks | `.venv` Python 3.14: `python -m ruff check .`, `python -m ruff format --check .`, `python -m yamllint .`, `python scripts/check_repository.py`, `python scripts/check_contract.py`, `git diff --check` | All passed; Ruff format checked 262 files, repository checker checked 365 files after adding this worklog, contract checker validated 2 synthetic fixtures |
| Local Python suite | `.venv` Python 3.14: `python -m pytest -q` | 1,622 passed, 10 skipped, 48 subtests passed in 250.34 s; skips concern unavailable local raw telemetry/SEAMLESS data and Windows filename behavior |
| GitHub Actions checkpoint | Head `e5e22e4be75b00307c4b858b9ee01f9d6aa4ce2a`; [CI run 37200525571](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/37200525571) and [Branch policy run 37200525505](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/37200525505) | Ubuntu tests, Windows tests, Quality, Compose, and Branch policy all passed. This worklog status update creates a subsequent docs-only head; its exact CI result is shown on PR #130. |

## Điều học được / quyết định

The earlier `6d06dc7` source revision in the baseline identifies when the #139 evidence was read. It is a historical provenance pin; current integration is the merge from `8a1ce0c`. No Legacy import or database query was repeated for this sync. The prior reviewer found the evidence-integrity issues resolved within the historical scope.

## Trở ngại và việc kế tiếp

Importer console/Neo4j write-error evidence, rejected-record counts and duration were not captured in the original run. #121 remains open for exact failure observation if required. Full same-snapshot graph exports and parity for #82/#47 remain separate. Human final re-review and approval remain pending.
