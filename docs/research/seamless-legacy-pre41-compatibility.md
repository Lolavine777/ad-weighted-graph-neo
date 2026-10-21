# Unchanged SEAMLESS on BloodHound Legacy before 4.1

Official BloodHound Legacy **4.0.3** reported file-level completion for all six canonical SEAMLESS schema-v3 files unchanged against Neo4j **4.1.13**. This records file-level importer acceptance and reproducible aggregate graph counts; it does not establish error-free writes or complete record acceptance, and #121 is not declared resolved here. The same outcome and aggregate graph counts were observed in two independent clean databases on 2026-09-27. The [sanitized result](../../reports/baselines/seamless-legacy-403-unchanged.json) records each file and both runs.

This is a historical importer compatibility result. It is separate from the converted `seamless-legacy-v4` experiment, the CE 9.7 baseline, and the parity requirements of #82. The 4.3.1 rejection remains valid for that version. No 3.x version was tested because 4.0.3 accepted the input; this experiment does not establish the oldest compatible release.

## Inputs and runtime

- Dataset `seamless-v1`; manifest snapshot ID `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
- Six manifest-bound files under `data/raw/SEAMLESS`, selected directly in the official app's file upload input. No envelope, metadata, field, array, filename, or record transformation was made. The separate derived Legacy-v4 files were not used.
- Official [Legacy 4.0.3 Linux x64 release](https://github.com/SpecterOps/BloodHound-Legacy/releases/tag/4.0.3), asset `BloodHound-linux-x64.zip`, SHA-256 `2321bcf59fc695ef50c4c540af7c4f76343e9ea8d1989ed0d30f33b705147d25`. The upstream source at commit `b54c418ef83fe5856ae3fe6317a20f2368a6378c` identifies its package version as 4.0.3. Its [initial version guard](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/components/Menu/MenuContainer.jsx#L259) rejects metadata versions below 3.
- Official Neo4j Docker image `neo4j:4.1.13`, resolved to `neo4j@sha256:1f08dd79d877776e2501ba77d8b4c5354e8953d603fcae31df6b7b2c61685bc0` in both runs.
- Host: Windows `10.0.26200.0`, WSL2 Ubuntu 26.04 LTS, Linux `6.18.33.1-microsoft-standard-WSL2`; BloodHound ran as the official Linux Electron app under WSLg. Neo4j ran in Docker Desktop.

## Procedure

From the repository root, first verify the committed manifest against the canonical files:

```powershell
python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
```

The command returned `{"issues": [], "status": "verified"}` before each import. Confirm that the snapshot ID in the manifest matches the ID above. Download the pinned official release and compare its SHA-256 before extraction. For a clean Neo4j database, use a new container with no mounted or reused database volume (choose unused localhost ports):

```powershell
docker run -d --name bh-legacy-403-neo4j -p 127.0.0.1:17474:7474 -p 127.0.0.1:17687:7687 -e NEO4J_AUTH=neo4j/<local-test-password> neo4j@sha256:1f08dd79d877776e2501ba77d8b4c5354e8953d603fcae31df6b7b2c61685bc0
docker exec bh-legacy-403-neo4j cypher-shell -u neo4j -p <local-test-password> 'MATCH (n) RETURN count(n) AS nodes'
docker exec bh-legacy-403-neo4j cypher-shell -u neo4j -p <local-test-password> 'MATCH ()-[r]->() RETURN count(r) AS relationships'
```

Both pre-import queries returned `0`. Launch the extracted official `BloodHound` Linux executable, connect to `bolt://localhost:17687`, select the six original JSON files in manifest order, and wait until every entry in **Upload Progress** reads `Upload Complete` and `100%`. In this experiment the file input was driven through the Electron DevTools protocol; it delivered the original Linux file paths to the app's unmodified upload control. The ordinary file picker provides the same importer path. For the repeat, launch a second new Neo4j container on separate ports, verify the manifest again, confirm both zero counts, reconnect the app, and import the same six files.

Query aggregate results in each database:

```cypher
MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY labels;
MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY type;
MATCH (n) RETURN count(n) AS nodes, count(DISTINCT n.objectid) AS unique_objectids;
MATCH (n:Base) WHERE size(labels(n)) = 1 RETURN count(n) AS base_only_nodes;
MATCH ()-[r]->() RETURN count(r) AS relationships,
  sum(CASE WHEN r.isacl = true THEN 1 ELSE 0 END) AS acl_relationships;
```

## Observations

| File kind | First run | Clean rerun | Nodes with corresponding label |
| --- | --- | --- | ---: |
| Computers | Upload Complete, 100% | Upload Complete, 100% | 100 |
| Domains | Upload Complete, 100% | Upload Complete, 100% | 1 |
| GPOs | Upload Complete, 100% | Upload Complete, 100% | 2 |
| Groups | Upload Complete, 100% | Upload Complete, 100% | 551 |
| OUs | Upload Complete, 100% | Upload Complete, 100% | 223 |
| Users | Upload Complete, 100% | Upload Complete, 100% | 2,493 |

Both runs produced **3,370 nodes**, **3,370 distinct stored `objectid` values**, **0 `Base`-only nodes**, **71,596 relationships**, and **52,850 relationships with `isacl = true`**. Per-type relationship counts are in the result artifact; `MemberOf` was 15,917, `Contains` 2,816, and `GenericAll` 37,034 in each run. The UI displayed no warnings or file failures. It did not expose a rejected-record counter, so record-level rejection is unknown. Import duration was not captured.

The raw snapshot contains 550 Group records but 549 unique Group ObjectIdentifiers. The later #139 identity reconciliation, measured on 2026-10-01 against both retained #130 databases, found every raw Group identity and exactly two additional membership-reference placeholders. Thus 550 records − 1 duplicate representation + 2 placeholders = 551 stored Group identities. This explanation uses measured identity sets, not count equality. The absence of `Base`-only nodes does not prove every raw reference resolved as intended. These graph counts must not be treated as expected values derived from raw-first observations (3,369 records, 3,368 unique ObjectIdentifiers, 13,324 direct membership observations, and 53,040 ACE observations). Those observations use a different counting layer.

## Evidence revalidation on 2026-10-04

This update reuses the committed [#139 measurement](../../reports/research/issue-139-seamless-boundary-legacy-403.json) and [query package](../../reports/research/issue-139-seamless-boundary-legacy-403-queries.json), read from develop commit `6d06dc7bb9352db568eb7dc6deb92285a8d32489`. No database query or new import was run in this update. The measurement binds the same manifest snapshot, Legacy artifact digest, Neo4j image and the two retained initial/rerun containers; its observations were collected on 2026-10-01.

The PR branch subsequently merged `develop` at `8a1ce0c28b7491fa2266314c56bbb03035bf1ab7` on 2026-10-04 without conflicts in this report, the baseline artifact, or the #139 source evidence. The `source_revision` in the artifact identifies the earlier evidence read; it is not the current integration revision.

- Full Group set reconciliation reports `raw_minus_legacy = []` and exactly two `legacy_minus_raw` identities, the qualified well-known INTERACTIVE and IUSR membership references. Exact queries returned one `Base, Group` node for each, with only `objectid` in properties. Both retained databases have equal Group identity sets. Input and set digests are recorded under `group_identity_reconciliation`; no local exports are newly committed here.
- The complete recorded label population totals 3,370 nodes and contains only `Base` plus one typed label. It therefore independently implies zero nodes whose sole label is `Base`. Together with the matching initial/rerun Group sets and historical equal per-label populations, this revalidates the reported zero from label-population evidence. The corrected query above was not rerun here; the original single-label expression was not a valid definition of this metric.
- Import-time Electron console and Neo4j write-error evidence was not captured in the original result and is not supplied by #139. The pinned importer can catch write errors and still mark uploads complete; see [the reviewed upstream write path](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/components/Menu/MenuContainer.jsx#L356-L380). Write-error count remains unknown, as does record rejection. A later database query cannot retrospectively establish zero import-time failures.

For a new clean run, attach Electron console capture before uploading, keep it active through completion of all writes, retain Neo4j logs locally, and publish only a sanitized error summary bound to the manifest, runtime, clean-run ID and capture interval. Record zero only when the entire interval was captured and inspected.

The Group evidence resolves the identity discrepancy within its measured scope. The later [#82 reconciliation handoff](seamless-legacy-403-reconciliation-handoff.md) supplies complete retained-database node/relationship exports and a full local mapping. Semantic classification and the real #47 difference verdict remain open; neither this compatibility experiment nor the export demonstrates full graph/CE parity.
