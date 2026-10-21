# Worklog - 2026-10-14 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #284 / PR #286 / historical milestone not recorded
- Thời gian thực tế ước lượng: historical duration not recorded; metadata normalization only

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Normalize historical worklog metadata | `docs/templates/daily-worklog.md` | Metadata structure normalized; original historical narrative retained verbatim. |

## Điều học được / quyết định

This header records repository-format normalization only.
The original narrative below retains its historical outcomes without new implementation verification.

## Trở ngại và việc kế tiếp

Historical duration was not recorded.
Original limitations and follow-up work remain in the preserved record below.

## Preserved historical record

# PR #286 — priority-policy blocker fix — 2026-10-14

Review: https://github.com/nairyuuu/ad-weighted-graph/pull/286#discussion_r4265813117

## Change

Policy `defensive-complete-scope-first/2` minimizes unresolved after source×goal
pairs before proven remaining exposure and observed program cuts. Unknown/error/
unsupported/not-evaluated outcomes cannot gain priority merely by losing a witness.
Reachable cells remain proven exposure even when search is incomplete. Count each
unresolved goal separately, including sources reachable at another goal.

The report's factual exposure and native disconnection proofs are unchanged.
Historical /1 summaries and v4 acceptance evidence remain preserved.

## Validation

Python 3.14.8, exact pinned requirements-tests.txt. Source commit:
`a8d077dc2e70e5841694703d56986a0b636dfbbc`.

- 13 new priority regressions passed. All 10 equal-incomplete adversarial ordering
  cases fail against the original /1 function and pass against /2.
- 30 remediation runner tests passed.
- CLI: 1 passed; 1 explicit optional private-raw-data skip. No raw pilot rerun.
- Week 4 acceptance deterministic reproduction: 36 PASS, 1 manual NOT EXECUTED,
  1 default-path private-dataset prerequisite BLOCKED RUN; no unexpected failures.
- 4 acceptance manifest/pin/Windows checkout regression tests passed.
- Current v5 record pins the changed source and test references. Frozen semantic
  expectations are unchanged. The executed source/input pins are clean; the
  untracked generated record makes the overall checkout dirty.
- Ruff check and format passed for all four changed Python files.
- Remediation acceptance oracle passed: 11 catalog entries, 8 cases.

The checkout was reconstructed from authorized GitHub blobs because ordinary git
clone could not authenticate in this environment. All downloaded blobs and Git
tree/commit objects were verified against GitHub hashes. Files outside this
focused checkout were marked as sparse entries. No full-suite, remote-CI, or
exact-head private raw reproduction claim is made for this change.

Reviewer approval on the new head and the existing stacked #285/acceptance gates
remain pending; this fix does not merge the PR or grant numeric adoption.
