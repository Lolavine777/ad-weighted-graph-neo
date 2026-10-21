# Worklog - 2026-10-12 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#267](https://github.com/nairyuuu/ad-weighted-graph/issues/267), #259, #265; [PR #271](https://github.com/nairyuuu/ad-weighted-graph/pull/271); Week 5; `feature/267-final-rating-taxonomy`.
- Thời gian thực tế ước lượng: khoảng 120 phút, gồm cohort, wrapper debugging và verification.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Taxonomy/rubric | [Audit](../research/ratings/final-cpi-v1/audit.md), [profile](../research/ratings/final-cpi-v1/profile.json) | 8 structural relations, 22 active techniques / 20 likelihood classes và passive MemberOf; numeric proposals pending B |
| Freeze trước run | Cohort/profile/inventory commit `733bf76`; [cohort](../research/ratings/final-cpi-v1/cohort.json) | 8 queries, source Computer/User, typed DC/material/identity goals, caps và unsupported groups declared trước ranked run |
| Native bindings | `scripts/research/final_cpi_profiles.py` | Full exact prefix + actor/source/target/auth/resource/method/snapshot/policy/budget/horizon; no graph evaluator or candidate injection |
| Public cohort | Consumer `3a11d6b`; [evidence](../../reports/research/issue267-final-cpi-v1-verification.json) | 32 CLI processes, hai runs/mode, normalized determinism và API/CLI/orchestration match trên cả 8 queries |
| Production coverage | 50 valid/conditioned-feasible returned programs | Accepted C/P/I=0/0/0, full/eligible=0/50; target 80% chưa đạt |
| Wiring-only potential | Synthetic derivatives, giữ graph topology và pipeline | C=50/50, P=49/50, I=50/50, full/eligible=49/50; raw-only secondary sample 25/26; không phải B adoption |
| Truncation/full-generator | Full raw có 3370 nodes/56367 edges | 4 queries truncated; Source A all-tech và Josefa đều 0 programs tại 2000 expansions; không có snapshot-wide fraction |
| Before/after oracle | Original Source A gate và new synthetic profile chạy lại | 2/24 historical scoped-copy full-rated → 24/24 test-only; canonical pending production vẫn 0/24 |
| Five worked paths | [Results](../research/ratings/final-cpi-v1/results.md) | C-Min-Effort=2 trên complete 7-node/16-edge projection; exact Fraction products; frontier 24 overlapping alternatives |
| Sensitivity | Wide bounds, missing declaration, FALSE terminal, step cap | Wide P giữ frontier 24/C=2; missing/FALSE trả 0 goal paths, native indeterminate; cap 2 bước truncated |
| Final full suite | `.venv/bin/python -m pytest -q` | 2609 passed, 9 skipped, 48 subtests passed; 441.62s |
| Final focused regressions | `tests/test_final_cpi_profiles.py` | 6 passed; graph selector/artifact mapping RED/GREEN; B-owned User-goal gap frozen as diagnostic |
| Quality/privacy/history | Ruff, format, contract, repository, diff; 47 historical file pins | PASS local; no changes to B-owned src/configs or frozen bytes |

## Điều học được / quyết định

AS-REP và TGS natural-password recovery cần conditional rank mass và achieved compatible verifier coverage; cap không tạo compute floor hoặc password success mass.
#266 sửa riêng ở worktree/branch cũ; #271 từ current develop `da21fbb`, không chứa #266 commits.
Các class khác có reasoning riêng hoặc explicit historical equivalence question, không copy AS-REP percentages.
History equivalence stable/no-depletion là một judgment thêm cần B adopt, không phải marginal fallback hoặc independence.
Native prefix bao gồm outcome như lookup identity; conditioning chỉ gồm preceding successful prefix.
C=0 activation vẫn là event; MemberOf không có C/q; không cộng trùng auth preparation đã nằm trong WinRM.
I dùng typed target technical consequence; Kerberoast material có Low trong synthetic test, không borrow DC High.

Native full-raw CLI attempt trace đạt hơn 700 MB.
Lượt comparison giữ hai full payload trong memory đã bị dừng; wrapper sửa thành streaming normalized transport, có SHA/size của native files và private normalized outputs.
Final run trên committed consumer giữ nguyên cohort/caps và hoàn tất cả 8 queries.
Wrapper selector sai `nodes_by_id` đã được reproduce qua public flow, sửa dùng `EngineGraph.nodes()`.
Artifact I mismatch tuple/list đã được sửa bằng authoritative `materialized.semantic_goal.to_dict()`.
Không có B-owned implementation fix trong PR này.

## Trở ngại và việc kế tiếp

Actual numeric adoption của B chưa có; tất cả new production records fail closed, không tự approve/merge hoặc đóng #267.
Returned sample 49/50 chỉ là synthetic wiring evidence, có duplicated projection/full-raw comparison và nhiều queries không return program trước cap.
Chỉ 8/20 active likelihood classes xuất hiện trong goal-reaching paths; raw RBCD/HasSession/ACL/group cohort coverage còn thiếu.
Group initial login và Domain/OU/GPO source profiles chưa support; không dựng capability giả để lấp mẫu số.

B-owned User-goal attribution gap: final activation đạt `usable_identity(owner, authentication Computer)` nhưng search còn yêu cầu transition endpoint trùng owner-User target, nên native no_path.
A giữ target/goal freeze và report unreturned goal-state success event; không diễn giải thành identity an toàn hoặc đổi target để tăng coverage.
Handoff đã post trên PR #271 với reproduction/regression và request B quyết định contract/fix.
B còn review/adopt endpoints + scoped history domain, giữ public estimated_expert_scenario/review references, và làm source/batch/search/chokepoint integration theo #265.
Source-risk/chokepoint sensitivity chưa đo, không thay bằng query-local frontier checks.
Remote CI được ghi riêng; không claim PASS nếu runner không start vì account billing/spending limit.


## Supplementary v1.1 continuation

The original eight-query cohort/profile/taxonomy/published evidence stays byte-frozen at `4452ca1`.
The extension reuses existing raw RBCD helpers and native providers, with a separately committed six-query cohort.
The ACL selector and caps stay fixed; observed administrative shortcuts are retained rather than suppressed.
Permission alternatives are compiled declaratively with `requires_any`, while native semantics alone determines applicability.
A four-node induced projection is a diagnostic control outside the raw supported subtotal.

| Verification | Exact result |
| --- | --- |
| Committed consumer | `0ef3ffd2f52859916d78d0b1070ab15c8df7a28d` |
| Public native processes | 24 CLI exits 0, two per mode/case; full selected API/CLI fields and exposed orchestration search/ranking/programs match all six |
| Supported raw subtotal | Accepted full 0/7; synthetic full 7/7; original 0/50 and 49/50 separate |
| Class exposure | 17/20 diagnostic and 15/20 raw goal-path classes; not adopted coverage |
| Full suite | 2626 passed, 9 skipped, 48 subtests; 523.10s |
| Historical packet | 47 historical files and original four packet files byte-preserved |

The native raw inventory has no HasSession, CanRDP or ForceChangePassword edges.
RBCD HTTP service binding and effective runtime controls remain explicit scenario assumptions, not observed success or empirical probability.
The first A inventory missed existing host routes and observed/derived permission alternatives; E2E failures were corrected at the shared binding domain.
The first projection omitted dangling-assessment filtering; its contract failure was reproduced and corrected without changing raw records.
An edit-script assertion caused one duplicate test launch; only that identified process was stopped, and interrupted output was excluded from final evidence.
Final [supplementary results](../research/ratings/final-cpi-v1/supplementary-results.md) and [sanitized evidence](../../reports/research/issue267-final-cpi-v1-supplement-verification.json) retain every denominator, cap and control.
B adoption, the User-goal contract decision, source/choke-point sensitivity and successful remote CI remain outstanding.
The new packet supersedes old broad equality flags; the original eight-query cohort also completed 32 fresh native CLI processes with corrected semantic comparisons.
A reproduced B's two P2 findings and added eleven negative cases; horizon/retry/method/lineage mismatches now refuse before binding, and semantic transport divergence refuses verification.


## Supplementary v1.1 continuation

The original eight-query cohort/profile/taxonomy/published evidence stays byte-frozen at `4452ca1`.
The extension reuses existing raw RBCD helpers and native providers, with a separately committed six-query cohort.
The ACL selector and caps stay fixed; observed administrative shortcuts are retained rather than suppressed.
Permission alternatives are compiled declaratively with `requires_any`, while native semantics alone determines applicability.
A four-node induced projection is a diagnostic control outside the raw supported subtotal.

| Verification | Exact result |
| --- | --- |
| Committed consumer | `0ef3ffd2f52859916d78d0b1070ab15c8df7a28d` |
| Public native processes | 24 CLI exits 0, two per mode/case; full selected API/CLI fields and exposed orchestration search/ranking/programs match all six |
| Supported raw subtotal | Accepted full 0/7; synthetic full 7/7; original 0/50 and 49/50 separate |
| Class exposure | 17/20 diagnostic and 15/20 raw goal-path classes; not adopted coverage |
| Full suite | 2626 passed, 9 skipped, 48 subtests; 523.10s |
| Historical packet | 47 historical files and original four packet files byte-preserved |

The native raw inventory has no HasSession, CanRDP or ForceChangePassword edges.
RBCD HTTP service binding and effective runtime controls remain explicit scenario assumptions, not observed success or empirical probability.
The first A inventory missed existing host routes and observed/derived permission alternatives; E2E failures were corrected at the shared binding domain.
The first projection omitted dangling-assessment filtering; its contract failure was reproduced and corrected without changing raw records.
An edit-script assertion caused one duplicate test launch; only that identified process was stopped, and interrupted output was excluded from final evidence.
Final [supplementary results](../research/ratings/final-cpi-v1/supplementary-results.md) and [sanitized evidence](../../reports/research/issue267-final-cpi-v1-supplement-verification.json) retain every denominator, cap and control.
B adoption, the User-goal contract decision, source/choke-point sensitivity and successful remote CI remain outstanding.
The new packet supersedes old broad equality flags; the original eight-query cohort also completed 32 fresh native CLI processes with corrected semantic comparisons.
A reproduced B's two P2 findings and added eleven negative cases; horizon/retry/method/lineage mismatches now refuse before binding, and semantic transport divergence refuses verification.


B round-2 review at `0ef3ffd` confirmed both earlier P2 reproductions are resolved and reported no new code blocker in the reviewed delta.
B did not approve final evidence or adopt numbers in that round; reviewer checks used isolated catalog/transport doubles, not the raw cohort/full suite.
A's corrected original and supplementary packets now complete all 14 queries with 56 fresh native CLI processes.
Current develop moved to `7368cac` because B merged original #266 at `5a2615c`; A did not merge it or infer numeric adoption.
The AS-REP verifier correction is isolated in draft #272, separate from #271.
B-owned src/configs remain byte-identical between the tested `da21fbb` baseline and current develop; #271 contains no #266 source changes.
