# Week 1 / Week 2 closure and successor ownership audit

Audit date: 2026-09-22.
Scope: original GitHub acceptance criteria, merged PR evidence, repository artifacts and accepted successor decisions.
This is a retrospective audit, not a new mentor sign-off or proof of M2 end-to-end readiness.
See [Week 1](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/week-01-review.md) and [Week 2](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/week-02-review.md) for the weekly template summaries.

## Historical issue disposition

All issues in this table were already closed when audited.
Unchecked boxes left in old issue bodies are not treated as evidence of either completion or failure on their own.
The disposition uses deliverables and review/acceptance evidence, and preserves superseded decisions as history.

| Issue / acceptance scope | Evidence inspected | Disposition and current source of truth |
| --- | --- | --- |
| [#20](https://github.com/nairyuuu/ad-weighted-graph/issues/20): A/B inventory, coverage, provenance, missing evidence and evaluation decision | [PR #26](https://github.com/nairyuuu/ad-weighted-graph/pull/26), [inventory](data-inventory.md), ADR-0006, A 15/09 and 16/09 logs | Preserve historical closure; ADR-0007 supersedes A/B primary strategy, #85/PR #88 completed the hash integrity amendment, and #79 consumes closed #94 evidence for semantic remediation |
| [#18](https://github.com/nairyuuu/ad-weighted-graph/issues/18): Python environment | [PR #19](https://github.com/nairyuuu/ad-weighted-graph/pull/19), ADR-0005, B 14/09 log, CI workflow | Preserve closure; Python 3.14 remains the baseline |
| [#27](https://github.com/nairyuuu/ad-weighted-graph/issues/27): deterministic manifest and verification | [PR #31](https://github.com/nairyuuu/ad-weighted-graph/pull/31), [manifest specification](../snapshot-manifest.md), tests/test_manifest.py | Preserve closure; #78/PR #89 later hardened honest null metadata and verified execution; #91/PR #95 handles loader policy |
| [#32](https://github.com/nairyuuu/ad-weighted-graph/issues/32): historical BloodHound imports | [PR #33](https://github.com/nairyuuu/ad-weighted-graph/pull/33), [PR #36](https://github.com/nairyuuu/ad-weighted-graph/pull/36), issue closure comment, [baseline](bloodhound-import-baseline.md) | Preserve A/B closure; #82 owns SEAMLESS experiment and cannot be closed from A/B evidence |
| [#1](https://github.com/nairyuuu/ad-weighted-graph/issues/1): MemberOf/HasSession direction and prerequisites | [PR #17](https://github.com/nairyuuu/ad-weighted-graph/pull/17), taxonomy, review approval | Preserve historical closure; ADR-0008/0009, #80 and #79 distinguish direct membership, passive traversal and session opportunity from credential extraction |
| [#2](https://github.com/nairyuuu/ad-weighted-graph/issues/2): host-access matrix | PR #17, ADR-0003, [PR #90](https://github.com/nairyuuu/ad-weighted-graph/pull/90) | Preserve closure with amendment: network/service gates are runtime predicates, CanRDP is composite authorization, missing required evidence is unknown |
| [#3](https://github.com/nairyuuu/ad-weighted-graph/issues/3): ACL relationships and effects | PR #17, [semantic catalog](../../configs/attack_semantics.yml), [Phase A matrix](m1-evidence-audit.md) | Preserve historical research; edge kind does not imply one guaranteed technique, and #79 owns narrative cleanup |
| [#4](https://github.com/nairyuuu/ad-weighted-graph/issues/4): pruning and exceptions | PR #17, #80/PR #90, host-access audit | Preserve historical decision record; disabled-terminal pruning is superseded, and #83/PR #96 corrects unconditional RODC/DCSync wording |
| [#5](https://github.com/nairyuuu/ad-weighted-graph/issues/5): taxonomy consolidation and B approval | PR #17 approval by @nairyuuu, issue closure comment | Original document/review scope satisfied; #79 Phase B remains open for present-day alignment |
| [#6](https://github.com/nairyuuu/ad-weighted-graph/issues/6): node IDs and schema | [PR #24](https://github.com/nairyuuu/ad-weighted-graph/pull/24), configs/contract.yml, tests/test_contract.py, B 15/09 review log | Preserve closure; current normative schema is Graph Contract 1.0.0; ADR-0010 facets do not add node kinds |
| [#7](https://github.com/nairyuuu/ad-weighted-graph/issues/7): edge identity, multigraph and provenance | [PR #25](https://github.com/nairyuuu/ad-weighted-graph/pull/25), validator/tests, B 15/09 log | Preserve original closure; ordered derived lineage (#92) and serialized time status (#97) need successor decisions |
| [#8](https://github.com/nairyuuu/ad-weighted-graph/issues/8): parser interfaces/error policy | [PR #28](https://github.com/nairyuuu/ad-weighted-graph/pull/28), parser types/tests, B 16/09 log | Interfaces and policies delivered; not evidence that #44/#45 graph builder implementation is done; old inference comments are amended by ADR-0003/#80 |
| [#9](https://github.com/nairyuuu/ad-weighted-graph/issues/9): eight-kind synthetic fixture, cycles, parallel edges, isolated nodes | [PR #29](https://github.com/nairyuuu/ad-weighted-graph/pull/29), m1-fixtures.json, tests/test_m1_fixtures.py | Preserve closure; accepted PR #90 intentionally supersedes disabled-terminal fixture behavior |
| [#10](https://github.com/nairyuuu/ad-weighted-graph/issues/10): dangling/duplicate validation and CI | tests/test_contract.py, issue acceptance comment at ea8fa7a, linked Ubuntu/Windows CI run | Preserve evidence-backed closure; local tests in this session do not substitute for historical CI |
| [#30](https://github.com/nairyuuu/ad-weighted-graph/issues/30) / [#40](https://github.com/nairyuuu/ad-weighted-graph/issues/40): template validation and M1 rollover decision | [PR #35](https://github.com/nairyuuu/ad-weighted-graph/pull/35) merged, scripts/check_repository.py, tests/test_repository.py, [PR #39](https://github.com/nairyuuu/ad-weighted-graph/pull/39) merged | Integration route completed; no unresolved #30 rollover inferred from old log text |

No historical issue was newly closed merely because code exists.
No completed issue is reopened solely because its accepted decision later acquired a separately tracked successor.
Weekly reviews are added in the current PR and require normal review/merge before being called integrated bookkeeping.

## #91 original scope versus canonical serialization

[#91](https://github.com/nairyuuu/ad-weighted-graph/issues/91) asks for a loader policy for null collection time, valid SEAMLESS ingestion, unchanged raw manifests, tests for valid/null-with-policy/null-without-policy, and passing repository checks.
Merged [PR #95](https://github.com/nairyuuu/ad-weighted-graph/pull/95) supplies those deliverables.
The loader retains explicit assumed/derived/externally_evidenced status and audit rationale in RawProvenance; canonical Provenance remains restricted to Graph Contract 1.0.0.
[Loader policy](loader-time-provenance.md) now corrects the later scope expansion that treated canonical serialization as a prerequisite to closing #91.
#91 is now closed in its original scope after the acceptance audit; canonical serialization remains open in #97.

[#97](https://github.com/nairyuuu/ad-weighted-graph/issues/97) owns the versioned representation, migration, validation and round-trip preservation of time status in canonical graph output.
It coordinates with #92 without conflating timestamp provenance with ordered derivation lineage.
Neither a silent new field nor silent loss of assumed-time status is authorized by #91.

## Amendment status and M2 gates

| Owner | Issue | Remaining acceptance / dependency |
| --- | --- | --- |
| A, B review requested | [#83](https://github.com/nairyuuu/ad-weighted-graph/issues/83) / [PR #96](https://github.com/nairyuuu/ad-weighted-graph/pull/96) | PR #96 merged at `a90a57c` and #83 closed; technical rereview/CI passed, but submitted independent pre-merge approval is missing |
| A, B review requested | [#85](https://github.com/nairyuuu/ad-weighted-graph/issues/85) / [PR #88](https://github.com/nairyuuu/ad-weighted-graph/pull/88) | PR #88 merged at `ebe92e6` and #85 closed; extracted-file integrity amendment technically rereviewed, but submitted independent pre-merge approval is missing |
| A, B review | [#79](https://github.com/nairyuuu/ad-weighted-graph/issues/79) | Phase A accepted through PR #93; Phase B can now consume merged #94 raw findings for EDA/report remediation, while #81 owns structured semantic provenance |
| B, A review | [#80](https://github.com/nairyuuu/ad-weighted-graph/issues/80) | PR #90 semantics accepted; schema/raw-field mapping and raw RDU versus verified CanRDP EDA/regression work remain |
| B, A review | [#94](https://github.com/nairyuuu/ad-weighted-graph/issues/94) / [PR #99](https://github.com/nairyuuu/ad-weighted-graph/pull/99) | Research accepted and issue closed after merge at `e4b7a1e`; raw-field, completeness, identity and telemetry evidence is input to #79/#80/#81/#44/#45/#47, not completion of those issues |
| B, A review | [#81](https://github.com/nairyuuu/ad-weighted-graph/issues/81) | Immutable ObservedActivity references and structured semantic-mapping evidence with expected/observed/correlated boundaries |
| B, A review | [#92](https://github.com/nairyuuu/ad-weighted-graph/issues/92) | Approved canonical ordered derivation representation before derived-edge output in #45 |
| B, A review | [#97](https://github.com/nairyuuu/ad-weighted-graph/issues/97) | Approved canonical time-status representation before policy-resolved snapshot output in #44/#47 |
| B, A review | [#82](https://github.com/nairyuuu/ad-weighted-graph/issues/82) | Manifest-bound SEAMLESS BloodHound CE experiment and explained discrepancies before #47 parity/reconciliation claims |
| A, B review | [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42) | #83 is closed; #79 Phase B remains open, then a successor decision must choose cost ownership; historical PR #51/body is not implementation authority |

The #94 raw-field research gate is complete; #44 direct-edge builder can begin on synthetic/reconciled records with the `unit` baseline and accepted #80 semantics.
Policy-resolved canonical collection-time output still waits for #97.
#45 additionally needs #92; #47 needs #82 and the pipeline evidence; #48 follows the completed integration work.
#81 is the gate for deeper telemetry evidence/evaluation, not a reason to mix telemetry into structural provenance.
This session does not start #44, #45, #47, #48 or production weighting.

## Latest-update check

PR #96 was refreshed on develop at `ebe92e6` in `f59dfa6`, preserving PR #88 and resolving the worklog conflict, then merged at `a90a57c`; #83 is closed.
Its rereview fixes make DCSync modeling prospective and restore the inherited 5.5-hour estimate.
PR #98 merged `develop` again after #99; independent cross-review and current-head CI remain required before merge.
Local agent/self-review is not a submitted GitHub approval. PR #88 and PR #96 therefore retain an explicit process exception until independent post-merge cross-audit is recorded.

[#99](https://github.com/nairyuuu/ad-weighted-graph/pull/99) was independently approved on head `a1a04ab` and merged into `develop` at `e4b7a1e`; #94 was then closed as completed.
Its raw-field and claim-traceability evidence is now accepted input for #79 Phase B and #80 schema/EDA closure.
The earlier failing [CI run 35756866344](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/35756866344) is historical; #99 passed the final CI and branch-policy gates on its approved head.

## Post-audit state reconciliation - 2026-09-23

Phần audit phía trên ghi state tại thời điểm 2026-09-22 và được giữ nguyên như historical evidence.
Các live-state references sau đây supersede những câu current-status đã cũ mà không rewrite lịch sử:

- #79 đã hoàn tất taxonomy/telemetry evidence remediation và được closed sau final audit trên `develop`.
- #80 đã closed sau accepted host-access/raw-field remediation.
- #81 đã closed sau PR #106 và locator repair PR #108; semantic/ObservedActivity provenance boundary hiện có acceptance evidence.
- #44 direct-edge builder đã merge qua PR #104, được exact-head approve, final-audit và closed.
- #42 vẫn open cho weighting successor/cost-ownership decision; historical fixed edge-level MAUT plan không phải implementation authority.
- #45 và #92 vẫn là M2 host-access/derived-lineage scope; PR #107 đang xử lý scope này và chưa được coi là accepted chỉ vì code tồn tại.
- #97 vẫn open cho canonical collection-time status serialization.
- #82 vẫn open cho SEAMLESS BloodHound CE same-snapshot baseline và là M2 evaluation dependency, không phải lý do reopen historical #32/M0 closure.
- #46, #47 và #48 vẫn là M2 integration/evaluation/handoff work.

Checkpoint kết luận: M0 và M1 đã complete về technical deliverables; repository đang có một phần M2 foundation đã triển khai sớm nhưng M2 end-to-end chưa complete.
README và backlog phải dùng checkpoint này thay vì suy live state từ historical Wxx cells hoặc retrospective text cũ.
