# #82 Legacy 4.0.3 reconciliation handoff to #47

Current comparison semantics and dispositions are defined by the [#195 comparison contract](seamless-legacy-403-comparison-contract.md), using accepted [#194 evidence](issue-47-seamless-legacy-403-reconciliation.md).
The counts and candidate semantics table below retain the historical #82 checkpoint before #189/#194; they are not current unresolved findings or the source of truth for #195.
Full direct MemberOf now matches `Members[] ∪ PrimaryGroupSid`; self-ACE, derived-only AdminTo and unknown CanRDP have the proposed `accepted_policy_difference` disposition for B review.
ForceChangePassword/HasSession remain `not_measurable`.
Legacy `export_complete=false` remains required for the full `m1-structural-v1` comparator even after common-slice acceptance; a policy difference does not satisfy that machine scope.
Final clean-checkout cross-reproduction belongs to #196 after #195 acceptance.

This is B's measured export handoff, not A's reconciliation verdict. Source: unchanged six schema-v3 files of `seamless-v1`, snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`. Legacy is BloodHound 4.0.3 with Neo4j 4.1.13. [PR #130](https://github.com/nairyuuu/ad-weighted-graph/pull/130) established two clean historical DB observations and merged on 2026-10-04. [PR #160](https://github.com/nairyuuu/ad-weighted-graph/pull/160) established the Group/boundary identity interpretation. [PR #157](https://github.com/nairyuuu/ad-weighted-graph/pull/157) supplies A's comparator. #82 measures and exports; #47 owns difference analysis; #48 consumes its reviewed result. CE #111/#127 is separate.

## Measured export

The exporter queried both retained clean-run databases read-only. It checked exact container IDs, Neo4j image digest and version, all 3,370 node identities/labels, all 71,596 directed stored relationship rows and per-kind counts. Both runs returned byte-identical deterministic node and relationship observations. The raw six-file manifest verified before export; the project CLI at `develop@2c68853` produced 3,370 nodes, 53,774 edges and 3 unknown assessments. No new Legacy import occurred. The BloodHound release ZIP hash also matches #130. The [sanitized handoff manifest](../../reports/baselines/seamless-legacy-403-reconciliation-handoff.json) pins input/export/query digests and local file references.

| Population | Count |
| --- | ---: |
| Legacy nodes / unique `objectid` | 3,370 / 3,370 |
| Collected counterparts / boundary placeholders | 3,368 / 2 |
| Group collected / boundary | 549 / 2 |
| Legacy stored relationships / unique directed triples | 71,596 / 71,596 |
| Legacy `MemberOf` stored / unique | 15,917 / 15,917 |
| Legacy `GenericAll` stored / unique | 37,034 / 37,034 |
| Project direct `MemberOf` / `GenericAll` | 13,324 / 37,044 |

Full exports live under ignored `.cache/issue82-handoff/`: `legacy-nodes.json`, `legacy-relationships.json`, `identity-mapping.json`, `project-comparison.json`, `legacy-comparison.json`. They contain AD identities and must stay in authorized local storage. The committed artifact contains counts, digests, dispositions and references, not the full identities. The relationship table carries source and target identities, original kind, source/target boundary flags and `stored_multiplicity`. It groups only exact directed triples; unlike a set-only export, it can represent storage duplicates. This run had multiplicity 1 for every triple. `legacy-comparison.json` has one row per stored relationship for #157; it does not silently collapse multiplicity.

Mapping comes from manifest-bound raw `ObjectIdentifier` paired with the accepted v3 adapter and `IdentityNormalizer`, not from matching display names. It requires one-to-one targets, exact Legacy source-set coverage and equality with project node IDs/kinds. The Group target-set digest is checked against accepted #139 evidence. The 549 collected Group records and the two well-known boundary references remain distinct. `SEAMLESS.INTERNAL-S-1-5-4` maps to `S-1-5-4` / INTERACTIVE; `SEAMLESS.INTERNAL-S-1-5-17` maps to `S-1-5-17` / IUSR. Each is a Legacy `[Base, Group]` placeholder with one outgoing `MemberOf`, not proof of a collected AD Group. The other #139 scope-preserving Builtin and global SID mappings follow the same raw/adapter/normalizer chain. A Legacy `Group` label alone never decides collection status.

## Historical common-semantics handoff to A (#82)

The query package exports **all 15 observed Legacy kinds**, including out-of-scope kinds.
`m1-structural-v1` in #157 requires eight specified kinds and direct `MemberOf`.
Exporting same-name rows does not establish those meanings.
The historical manifest records candidate mapping and pending semantic review; its comparator input declares `export_complete=false` and the pre-handoff format run returns `NOT_MEASURABLE`.
The [#195 contract](seamless-legacy-403-comparison-contract.md#5-comparator-report-và-demo-phải-giữ-gate) supersedes these candidate dispositions without changing historical bytes.
Common-slice acceptance alone must not flip this flag or change comparator validation to force a match.

| Legacy kind | Project target | Current disposition |
| --- | --- | --- |
| `MemberOf` | `MemberOf` | `unknown`: only the two #139 boundary pairs have direct raw evidence; classify the other stored pairs as direct/effective/derived before a direct-only comparison. |
| `AdminTo` | `AdminTo` | `unknown`: review nested membership/materialization policy. |
| `GenericAll`, `WriteDacl` | Same names | `unknown`: ACE names and directions are exported; verify inherited/materialized treatment before asserting equivalence. |
| `CanRDP`, `CanPSRemote`, `HasSession` | Same names | `unknown`: verify project prerequisites and Legacy policy. Zero Legacy `HasSession` is an observed count, not equivalence. |
| `ForceChangePassword` | Same name | `unknown`: no Legacy stored rows; `AllExtendedRights` is not automatically this kind. |
| `Contains`, `AllExtendedRights`, `ExecuteDCOM`, `GenericWrite`, `GetChanges`, `GetChangesAll`, `GpLink`, `Owns`, `WriteOwner` | None in M1 structural contract | `out_of_scope`; retained in full observations and kind counts. |

`MemberOf` has a historical stored-count difference of 2,593; #139 already showed the two boundary memberships contribute zero to it. `GenericAll` differs by ten in the historical totals. These are **priorities for #47's exact set analysis**, not diagnosed causes. The full local exports let A form project-only and Legacy-only sets, inspect endpoint mapping, boundary contributions and multiplicity. Legacy relationship rows do not contain a raw locator or importer operation trace. Project canonical edge provenance does: [the raw locator helper](../../scripts/research/trace_project_raw_locator.py) takes an exact `(source,kind,target)` from `project-comparison.json`, validates the manifest and provenance snapshot binding, and finds raw record JSON pointers from `raw_file` and `record_id`. It retains the attribute path, including array names; it does not invent an array element index. If a record cannot be located, it returns `unknown`. Use this for both a discrepancy and a matching sample; never assign project raw provenance to a Legacy stored edge.

## Reproduce on the authorized machine

From this worktree, with the same retained containers and local raw directory:

```powershell
../../.venv/Scripts/python.exe -X utf8 scripts/snapshot_manifest.py verify ../../data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
docker start bh-legacy-403-neo4j bh-legacy-403-neo4j-rerun
../../.venv/Scripts/python.exe -X utf8 -m src.parser.cli --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 --raw-dir ../../data/raw/SEAMLESS --manifest-dir data/samples/manifests --time-policy .cache/time-policy.json --created-at 2026-10-01T00:00:00Z --error-policy fail_fast --output .cache/issue82-project.json --summary
../../.venv/Scripts/python.exe -X utf8 scripts/research/export_legacy_reconciliation_baseline.py --raw-root ../../data/raw/SEAMLESS --project .cache/issue82-project.json --time-policy .cache/time-policy.json
../../.venv/Scripts/python.exe -X utf8 scripts/reconcile_graph_baseline.py --candidate .cache/issue82-handoff/project-comparison.json --baseline .cache/issue82-handoff/legacy-comparison.json --mapping .cache/issue82-handoff/identity-mapping.json --output .cache/issue82-handoff/pre-handoff-validation.json
../../.venv/Scripts/python.exe -X utf8 scripts/research/trace_project_raw_locator.py --project .cache/issue82-handoff/project-comparison.json --raw-root ../../data/raw/SEAMLESS --source '<canonical-source>' --kind GenericAll --target '<canonical-target>'
```

Create `.cache/time-policy.json` as UTF-8 before the CLI: `{"timestamp":"2026-10-01T00:00:00Z","status":"assumed","reason":"Reproducible assumption for #82; collection time unknown."}`. This is an assumed project evidence time, not collection/import time. [The read-only query package](../../reports/research/issue-82-legacy-reconciliation-queries.json) includes runtime, labels, per-kind counts, full nodes, directed rows, multiplicity, `MemberOf`, `GenericAll`, boundary principals and exact lookup. The exporter uses the full rows and totals, then verifies both runs; the other queries support drill-down. Credentials come from `NEO4J_PASSWORD` or the retained container config and are never written to the artifact.

For #47, first review the manifest's `comparison_scope.kind_mapping` with B, determine comparable subset and exact direct/derived treatment, then use the accepted comparator contract on the authorized local files. The last command above is **pre-handoff validation only**: it proves parsing/eligibility handling, not SEAMLESS parity. A owns the full difference ledger, raw trace and final disposition. Current unknowns: importer write-error/rejected-record counts, import duration, Legacy per-edge raw provenance, full direct/effective/derived membership classification and common-semantics acceptance. Historical nulls remain null.
