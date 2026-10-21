# Worklog - 2026-10-04 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #82; downstream #47/#48; source #121/#130/#139/#160; M2.
- Thời gian thực tế ước lượng: Không đo thời lượng phiên; không suy từ thời gian import lịch sử.

Branch `feat/82-legacy-reconciliation-handoff` from latest `develop@2c688536780240fb71985db8a200fd2b06401e26`. Read CONTRIBUTING, #82/#47/#48/#139/#158, merged #130/#157/#160 and accepted reports. #130 merged on 2026-10-04 after A approval; #160/#157 were already accepted. Did not repeat their research or import.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Verify raw/runtime | Manifest verifier, Docker inspect/runtime, ZIP SHA-256 | Six raw files verified; exact two retained Legacy runs and pinned runtime matched |
| Project baseline | Parser CLI `fail_fast`, Graph Contract 1.3.0 | 3,370 nodes; 53,774 edges; 3 unknown assessments |
| Legacy export | Read-only query package and exporter | 3,370 node identities; 71,596 directed stored rows; two run outputs equal |
| Mapping and boundary | Accepted #139 mapping procedure and digest | 3,368 collected plus 2 boundary identities; 549+2 Group |
| Handoff | Sanitized manifest, local ignored full exports, guide | #47 can inspect triples, multiplicity and project provenance; semantics pending |
| Validation | Focused pytest and comparator format run | 19 focused tests pass; comparator `NOT_MEASURABLE` as intended |

### Source and execution

- Raw: `../../data/raw/SEAMLESS`, six unchanged schema-v3 files; `snapshot_manifest.py verify` returned `verified` and no issues. Snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; manifest byte SHA-256 is pinned in the committed handoff artifact.
- Legacy ZIP SHA-256 independently checked as `2321bcf59fc695ef50c4c540af7c4f76343e9ea8d1989ed0d30f33b705147d25`. Retained DBs `bh-legacy-403-neo4j` and `bh-legacy-403-neo4j-rerun` match #139 container IDs and Neo4j image `sha256:1f08dd79d877776e2501ba77d8b4c5354e8953d603fcae31df6b7b2c61685bc0`; runtime query returned 4.1.13. Containers were started, never reset or reimported.
- Project CLI at current revision used fail_fast and the same manifest/raw, with fixed `created_at` and explicit **assumed** time policy, giving 3,370 nodes, 53,774 edges, 3 unknown assessments, warnings/errors 0. Assumed timestamp is not an observed collection time.
- The [query package](../../reports/research/issue-82-legacy-reconciliation-queries.json) is read-only and sorted; it includes full node and directed relationship rows, per-label/per-kind counts, multiplicity, MemberOf, GenericAll, boundary and exact lookup. The [exporter](../../scripts/research/export_legacy_reconciliation_baseline.py) checks raw, runtime, run identity, count/kind distributions, full source mapping, endpoint closure, #139 Group set digest and both boundary memberships. Two retained DBs yielded equal full sorted rows: 3,370 nodes and 71,596 stored/unique triples each.
- Mapping pairs every collected raw ObjectIdentifier with the accepted adapter/normalizer result, then adds only two #139 boundary references after confirming absence among first-class raw objects. It is one-to-one and covers all Legacy/project node identities. 549 collected Group identities plus INTERACTIVE/IUSR placeholders reproduce accepted #139 Group digest. `Group` label does not imply collected AD Group.

### Artifacts, validation and limits

Committed: [sanitized manifest](../../reports/baselines/seamless-legacy-403-reconciliation-handoff.json), [handoff guide](../research/seamless-legacy-403-reconciliation-handoff.md), query package, exporter and focused tests. Full AD identities, directed rows, mapping, project Graph JSON and comparator inputs are local and ignored under `.cache/issue82-handoff/`; SHA-256 digests and population/kind counts in manifest bind them. Full project provenance remains local. No credentials or full AD IDs are committed.

`MemberOf` 15,917 and `GenericAll` 37,034 are observed stored counts; project direct counts 13,324 and 37,044. The exporter does **not** attribute the gaps. It preserves exact directed triples and multiplicity. Legacy raw provenance and import-time operation traces are unavailable; write-error count, rejected records and duration remain null. #139 proves only two boundary memberships common and zero contribution to the MemberOf aggregate delta. `Contains` and eight other Legacy-only kind names are out of M1 scope; same-name kinds still need semantic review. Comparator format validation returned `NOT_MEASURABLE` because `export_complete=false` for unaccepted full `m1-structural-v1` equivalence. This is pre-handoff validation only, not A's real #47 reconciliation.

Commands and reproducibility details are in the handoff guide. Local focused tests: 19 passed (exporter and existing #139 Group helper). Full suite/lint/CI result to be recorded in PR after completion.

## Điều học được / quyết định

Same-snapshot and same-name relationship rows are insufficient evidence for common semantics. Preserve full observations and their multiplicity, but keep the accepted comparator eligibility closed until A/B review direct/effective/derived classification. Keep collected Group separate from materialized boundary placeholders.

## Trở ngại và việc kế tiếp

Legacy import-time error/rejection counters and per-edge raw provenance were never captured; a read-only DB query cannot recreate them. Downstream A can access or reproduce local full exports with authorized raw/retained DB access, review common semantics, then run exact difference/provenance analysis for #47. #82 should remain open until this PR passes CI and A reviews/merges it.
