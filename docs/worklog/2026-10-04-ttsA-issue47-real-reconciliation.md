# Worklog - 2026-10-04 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #47 / [PR #184](https://github.com/nairyuuu/ad-weighted-graph/pull/184); downstream #48/#158; handoff #82/#183; merged #182/#183; M2.
- Thời gian thực tế ước lượng: Không đo tổng thời lượng phiên; app IngestTime của lần import mới được đo riêng, không dùng làm thời lượng công việc.

Base: `develop@6fbb410`, with full revision recorded in the evidence artifact.
Owner: @Lolavine777; reviewer: @nairyuuu.

## Plan and constraints

- [x] Read CONTRIBUTING, repository instructions, #47/#48/#158 and #183 handoff before changes.
- [x] Create isolated worktree from latest develop; branch `docs/47-real-legacy-reconciliation` follows CONTRIBUTING.
- [x] Verify unchanged six-file SEAMLESS manifest and reproduce current project CLI.
- [x] Recreate official Legacy 4.0.3 / Neo4j 4.1.13 baseline locally because B's retained files are on the teammate's machine.
- [x] Export all identities/directed rows/multiplicity and compare handoff SHA-256 digests.
- [x] Preserve the full comparator gate; use its existing validated extraction helpers for exact observation differences.
- [x] Trace differences and matching samples with raw pointers and code rules; preserve unknowns.
- [x] Publish per-relation common semantics, sanitized evidence, reproduction commands and B review handoff.
- [x] Run required checks, open PR into develop and request @nairyuuu review.

Do not modify B's parser, engine, rating model, exporter or comparator.
Do not extend CE/M3, close #47/#48 or declare product parity.
Full AD identities/output/logs stay in ignored `.cache/issue47/`.
The approved approach is a read-only research audit using existing extraction, mapping, query and serialization helpers.
The smallest new check must distinguish evidence-backed classifications from an unsupported same-name/self-loop guess.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Input/project | Manifest verification + parser CLI fail_fast | 3.370 nodes, 53.774 edges, 3 unknown CanRDP assessments, 0 warning/error |
| Native Legacy recreation | Official app 4.0.3 + new Neo4j 4.1.13 DB; [report](../research/issue-47-seamless-legacy-403-reconciliation.md) | Pre-import 0/0; six uploads complete; three full export digests match #183 |
| Exact observations | [Audit](../../scripts/research/reconcile_seamless_legacy.py), ignored evidence.json | Identity/kind sets equal; M1 17 project-only + 2.596 Legacy-only; 15.243 outside M1 |
| Priority decomposition | Members union PrimaryGroupSid; raw ACL self/non-self sets | 2.593 primary memberships missing in project; 10 GenericAll + 3 WriteDacl self-ACE filtered by Legacy |
| Provenance | Raw array pointers + B's raw locator helper | 5 matching samples + discrepancy samples; 8 project edges / 9 provenance records located; Legacy operation provenance null |
| Common semantics | Five explicit raw source-rule views | Exact raw/project/Legacy equality; narrower views pending B review, full M1 gate unchanged |
| Published evidence | [Sanitized artifact](../../reports/research/issue-47-seamless-legacy-403-reconciliation.json) | Counts/digests, 11 hashed sample entries, runtime/input bindings and unknowns |
| Focused tests | `python -m pytest tests/test_reconcile_seamless_legacy.py -q` via venv | 5 passed, including assessment/gate validation and every resolved ignored path |

### Actual execution

The same raw manifest verified with no issues.
Project CLI at the integrated base produced 3,370 nodes, 53,774 edges and 3 unknown CanRDP assessments.
Focused pre-change suite: 87 passed.
New local container `issue47-legacy-403-a` uses the exact #183 Neo4j image digest, localhost ports 47474/47687 and no reused data volume.
Pre-import queries measured Neo4j 4.1.13, zero nodes and zero relationships.
Official Darwin x64 release 4.0.3 was downloaded and digest-pinned.
All six original files were selected in filename order using the app's Upload Data control; all showed Upload Complete / 100%.
An initial click on Import Graph rejected the computers file as BAD JSON FILE before any raw upload; this was the wrong control, was corrected, and is excluded from the measured raw import interval.
Electron console capture ran from app startup through all uploads.
The new run's complete node table, relationship table and mapping are byte-identical to the three #183 handoff digests.
This binds exact observations to B's handoff without claiming that the new container is one of B's historical runs.
Historical importer write errors/rejections/duration remain unknown.
The new run measures 6 Processing events, 6 IngestTime events totaling 49.40560791015625 seconds, and zero caught write-error console events during the measured interval.
New rejected-record count remains null; UI completion is not record acceptance proof.
Read-only capture was rerun through the new audit command; the exact evidence digest remained `1a69f73961823077c692d4211445548fa1b26d75b6e61325e702e48e86862b2f`.
Existing comparator ran on actual inputs and returned exit 2 / NOT_MEASURABLE; full differences are a separate observation audit using its validated extraction helpers.

### Verification and review

Initial full suite: 1.631 passed, 11 skipped, 48 subtests passed, one failure because this new worklog did not yet follow the repository template.
The worklog format was corrected before final verification.
Ruff import-order feedback was corrected; all-source ruff check and format check pass.
Yamllint, contract validation, Compose config and git diff whitespace checks passed.
Internal read-only review found evidence/privacy boundary issues: assessments needed full contract validation, full comparator gate could be lifted, and output checks/summary lists could expose identities in alternate destinations.
These were corrected with canonical validation, the exact pending-gate requirement, checks of every resolved destination including symlinks, and recursive count/digest summaries; focused tests and the real audit were rerun.
Re-review also caught synthetic metadata relabeling in capture and ambiguity between historical B-bundle replay and the new candidate binding.
Capture now validates the original project before enrichment and refuses declared synthetic data; reproduction explicitly distinguishes historical replay from capture into a new scratch bundle.
Final current-code full suite: 1.632 passed, 11 skipped, 48 subtests passed.
The 11 skips were unavailable telemetry/dataset-B/SEAMLESS raw at worktree-relative paths and platform-specific filesystem cases.
To exercise the two real SEAMLESS loader tests, an ignored raw copy was added to the worktree after a symlink attempt was correctly refused by the manifest's symlink/junction-root policy.
`python -m pytest tests/test_parser_loader.py -q` then passed all 58 tests, including those two real raw tests.
No parser change was needed.
Final ruff check/format, yamllint, repository/contract checks and diff whitespace checks pass; Compose configuration validates.
The documentation's project trace snippet was executed and reproduced the pinned 8-edge/9-record trace digest.
All newly published files were scanned against every authentic raw/canonical identity in the mapping and the disposable credential; none are present.
PR #184 targets develop and has a confirmed review request for @nairyuuu; exact-head CI status is recorded in the PR handoff.

## Điều học được / quyết định

Primary-group membership is direct membership represented separately from Members; it must not be dismissed as closure or a harmless boundary delta.
GenericAll raw duplicates and Legacy self-ACE filtering explain different measurement layers; delta counts alone cannot distinguish them.
Direct AdminTo evidence may coexist with a coalesced nested derivation, so the direct view retains edges supported by LocalAdmins even when they carry lineage.
Keep the accepted comparator unchanged and preserve full differences while proposing only explicit, source-rule subsets for B review.
Full Legacy per-edge operation provenance cannot be recreated by read-only queries; raw rules and observed triples remain a separately described evidence chain.

## Trở ngại và việc kế tiếp

B reviews full local difference sets, identity mapping/direction, raw pointers, common semantics and classifications.
The primary-group input gap needs B disposition or an explicit reviewed scope decision; no parser/engine/model fix is included here.
CanRDP runtime permission remains unknown; no ForceChangePassword/HasSession observations means no decoder/session parity claim.
For #48, rerun on the final integrated develop revision and perform clean-checkout cross-reproduction after scoped correctness and B review are accepted.
#47/#48 stay open; this analysis does not mark Week 3 complete.
