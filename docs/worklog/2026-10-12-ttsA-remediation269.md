# Worklog - 2026-10-12 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #269, parent #265, Week 5; B reviewer @nairyuuu.
- Thời gian thực tế ước lượng: không có timer; không báo effort đã đo.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Isolated branch | `feat/269-chokepoint-remediation` from develop `7368cac505b3d19331cb8a688114107e91134f25` | Main checkout and other worktrees untouched |
| Semantics and B handoff | [Contract](../research/remediation/contract-v1.md), [B handoff](../research/remediation/B-handoff.md) | Version 1.0.0, pending B review/adoption |
| Catalog/contracts | [Catalog](../research/remediation/catalog-v1.json), strict catalog/request/result schemas | Acceptance checker passes, 11 mappings and 8 oracle categories |
| Independent finite checks | `tests/test_remediation_contract.py` | Exact ordered request/evidence oracles, bypass/choke/ineffective/multiple-source/nonstructural/false/unknown/truncated controls |
| Relevant tests | Venv `python -m pytest` on remediation, catalog, transitions, public ratings, AS-REP, Kerberoasting and RBCD | 278 passed in 45.75s, including raw-backed case |
| SEAMLESS | [Alias-only actual](../research/remediation/seamless-actual-v1.json) | Six raw files verified before/after; 3,370 nodes/56,367 edges; one declared source/host scope |
| Quality | Repository-wide Ruff check and format check; `scripts/check_repository.py`; `scripts/check_contract.py` | Passed; 432 Python files formatted; 664 repository paths checked before this worklog |
| Independent advisory review | Local review and failure-then-success regressions | All reported acceptance guard issues resolved; no remaining must-fix; does not replace B approval |
| Frozen acceptance | Clean-commit manifest and review-regression checks at `9966681` | 13 passed in 99.42s; frozen pins unchanged |

## Điều học được / quyết định

Cutting a large fraction of programs is different from eliminating source-goal exposure.
Alice's membership denial removes two of three programs but preserves direct admin access; shared membership denial disconnects Bob while Alice survives.
A common admin-channel denial disconnects both sources in the finite declared scope.
SEAMLESS membership-only remains ineffective for the direct AdminTo host chain; missing recovery and capped search cannot prove disconnection.
Static preauth/SPN gates need B's effective fact view; runtime overrides cannot replace observed SnapshotFacts.
Every numeric C/P value requires a witnessed successful program and applicable basis; absence of a path is not P=0 or numeric C=0.
No frozen baseline, raw graph, existing fixture, `src/` implementation or numeric adoption was changed.

## Trở ngại và việc kế tiếp

B must review #269 and pending source/goal PR #270 head `690fbd678db4e6cf194e43c4a455bfbc046fff43`.
B owns effective static/authorization/runtime overlays, replay/rerun integration, metrics/proofs and viewer #224; search guarantees #226/#227 and numeric adoption #267 remain separate gates.
No full-snapshot exposure, deployed remediation, production numeric reduction, independent B cross-reproduction or remote CI PASS is claimed.

## PR #274 review follow-up - comparison contract 1.1.0

Addressed B's two findings on `c9a27172a851696b929ed2cf8347813d3a16cdd2`.
Bypass references now include every normalized after success; omitted surviving and new bypasses are rejected.
Cross-run comparisons compute `semantic-program/1` from ordered actions, participants, all prerequisites, relevant context and nonempty evidence/producer bindings; generated IDs remain observation-local references.
ID churn is retained, reused IDs cannot hide new programs, and negatives require explicit complete rediscovery evidence.
New 1.1 schemas/examples preserve all old 1.0 artifacts, graph and finite oracle baselines.

Verification: contract checker passed; 55 tests passed in 30.20s, including finite/identity regressions, six-file manifest-verified SEAMLESS and frozen file pins.
Repository-wide Ruff lint/format, yamllint, repository and canonical contract checks passed.
Independent advisory re-review has no remaining must-fix; it does not replace B approval.
See [comparison contract](../research/remediation/contract-v1.1.md) and [versioned evidence](../research/remediation/review-v1.1-actual.json).
Full repository pytest and Compose were not rerun; B must substantiate native trace binding and rerun/proof artifacts during integration.
No engine, batch, Top-K, viewer, raw graph or numeric adoption changes; PR #274 and #269 remain open for B review.
