# Worklog - 2026-10-13 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #277 / PR #277 / historical milestone not recorded
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

# #277 P1: checkpoint scope integrity, version 2

Review finding: https://github.com/nairyuuu/ad-weighted-graph/pull/277#discussion_r4256475237
Reviewed head: 26892011a9c5a75ca5844ad4cc9cc8d0fd70a11c.

The v1 aggregator checked a non-adopted saved query only against its own checkpoint.
Changing a supplementary case's supported flag, selector or budget could reuse old
counts under a new cohort digest. Source/runtime changes with unchanged query bytes
could also reuse results. The maintainer's numeric adoption remains unchanged.

Every newly produced checkpoint now carries `final-cpi-checkpoint-scope/2.0.0`:
- exact cohort and case digests, including denominator membership, selectors and budgets;
- release digest and adoption-domain identity, for adopted and non-adopted cases alike;
- manifest-verified raw graph identity and snapshot-fact digest;
- actual case graph/snapshot identity, before-release query and consumed query digests;
- complete executable/source content identity: repository Python code, runtime configs,
  rating/scenario JSON, consumed manifest/fixture JSON, dependency content/version pins
  and the Python executable digest/version.

Aggregation requires `--raw-dir`. It re-verifies the raw manifest and independently
re-derives every current query and graph, including roasting and supplementary cases.
It compares all scope pins and graph summary/membership before adding any counts.
Executable/source and release changes during a replay or aggregation also fail closed.
No legacy checkpoint is upgraded by adding current pins after the fact.

The new report is `reports/research/issue277-adopted-replay-v2.json`, using fresh
checkpoints under ignored `reports/generated/issue277-adoption-v2`. The v1 report
and all historical/proposal/release files are preserved; v1 is legacy evidence,
not the acceptance artifact for the new checker.

Regression coverage includes old files retained while changing supported, selector,
budget or cohort metadata; graph/snapshot or executable/runtime identity drift;
legacy checkpoints without scope metadata; changed consumed queries and reviews;
and incomplete cohorts that must not pass the returned-sample gate. Thirteen
scope/accounting tests pass. The 44 other focused tests and seven raw regressions
also pass (64 unique tests across these suites). A separate production-path probe
confirmed an actual v1 projection checkpoint is refused and no report is written.

The replay reuses the native API, two native CLI processes, exposed orchestration
comparison and independent C/Fraction oracle. Numeric values, original/supplementary
cohorts, caps, initial states, selectors, retry budgets and denominators are unchanged.
The source map is published once in the report; each checkpoint pins that entire
map's identity, plus its runtime/dependency summary, without repeating the full map.

Ruff lint/format and whitespace checks pass. This remains a connector-materialized
partial checkout; no full repository pytest or remote CI success is claimed.
The P1 fix does not widen numeric adoption, merge the PR or close #267.

Fresh replay completed for all eight original and six supplementary queries,
with 28 native CLI processes and API/orchestration/oracle checks. The original
returned-sample result remains 48/50 (full-raw subset 24/26); supported supplement
remains 0/7, with no scope expansion or denominator pooling. Four original and
three supplementary queries remain truncated; global coverage is not established.
