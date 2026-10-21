# SEAMLESS v1 Scope Identity Evidence Audit

Status: the exact snapshot has no authoritative Domain objectGUID, but its observed AD Domain SID supplies typed Domain scope under Contract 1.3.0. The complete fail-fast canonical graph passes Contract validation; its structural nodes and edges were imported into project Neo4j. Three canonical assessments remain in the validated JSON. PR #148 is under review for #138 acceptance.

Related: [#134](https://github.com/nairyuuu/ad-weighted-graph/issues/134), [#135](https://github.com/nairyuuu/ad-weighted-graph/issues/135), [snapshot manifest](../../data/samples/manifests/seamless-raw-v1.json), [provenance audit](provenance-audit.md), [SEAMLESS raw-field audit](seamless-raw-field-audit.md).

## Snapshot and provenance chain

- Dataset: `seamless-v1`
- Snapshot: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`
- Manifest: `data/samples/manifests/seamless-raw-v1.json`; it covers six JSON files and 11,371,828 uncompressed bytes.
- Upstream repository: [`mike-nolan-councilman/Bloodhound_Data`](https://github.com/mike-nolan-councilman/Bloodhound_Data)
- Pinned upstream commit: [`8c3107421bb910e5e2b4d16631e243ddb0756ca5`](https://github.com/mike-nolan-councilman/Bloodhound_Data/commit/8c3107421bb910e5e2b4d16631e243ddb0756ca5), whose commit message says it adds all raw JSON and a BloodHound-importable ZIP and attributes DC configuration to [BadBlood](https://github.com/davidprowe/BadBlood).
- Upstream archive: `20210920185958_BloodHound.zip`, SHA-256 `b8e9f003dd51a98838be86d8f98b0844a19a7876aad0a81b525f19e110105813`, matching the hash already recorded in [the provenance audit](provenance-audit.md#21-seamlessinternal-snapshot-seamless-v1).

The upstream archive was downloaded to a temporary location and inspected without extracting into or modifying `data/raw/`. Its ZIP directory contains exactly these six files: `computers`, `domains`, `gpos`, `groups`, `ous`, and `users` JSON exports. There is no seventh metadata or identity file. The upstream Domain JSON at the pinned commit has Git blob SHA `942657e475d90632da40deb716069c2c15324c6a`, matching the local file's `git hash-object` result. The local manifest independently pins the exact bytes of all six local exports.

This establishes that the documented upstream archive and the tracked snapshot share the same six-file export population. It does not establish an objectGUID from the original AD database or from an independently reconstructed BadBlood environment.

## Scope-identity search

The exact manifest-verified local files were searched recursively, including nested `Properties`, relationship objects, and metadata, for GUID-shaped fields and names including `ObjectGUID`, `ObjectGuid`, `objectguid`, `object_guid`, `GUID`, `Guid`, `guid`, `DomainGUID`, `DomainGuid`, `domain_guid`, and `scope_guid`.

| Evidence location | Observation | Why it cannot scope domain-relative SIDs |
| --- | --- | --- |
| Domain record and `Properties` | `ObjectIdentifier` / `Properties.objectid` are `S-1-5-21-1271839998-3495686680-2211690266`; `Properties.name` and `.domain` are `SEAMLESS.INTERNAL`; DN is `DC=seamless,DC=internal`. | The domain SID and DNS name are not the Domain object's stable GUID. No `objectGUID` is present. |
| Computer and DC records | `ObjectIdentifier` / `Properties.objectid` are SIDs, including DC `BADBLOOD.SEAMLESS.INTERNAL`; nested properties have no objectGUID field. | A Computer object identity is not the containing Domain object's GUID. |
| OU records | Object identifiers are OU GUIDs; no Domain objectGUID field is present. | An OU GUID identifies an OU, not the Domain scope. |
| GPO records | Object identifiers are GPO GUIDs; distinguished names and policy paths also expose policy identifiers. | A GPO GUID identifies a policy object, not the Domain scope. |
| All GUID-shaped nested fields | The two exact `Links[].Guid` values are references to the two GPO objects (also present as GPO `ObjectIdentifier`s). | These are GPO link targets, not a domain identity. |
| Collector envelope metadata | All six envelopes have only `count`, `type`, and schema `version: 3`. | No collector or snapshot scope GUID metadata is present. |

The full raw-field audit reports the same schema boundary: [all six envelopes and record shapes](seamless-raw-field-audit.md#3-cau-truc-envelope-json-chung); its inventory also notes that `Properties.domainsid` is absent, while the Domain record's top-level identity is the known SID above. This exact observed `S-1-5-21-1271839998-3495686680-2211690266` is accepted as Domain scope when no objectGUID exists; it is not transformed into or represented as a GUID.

## Decision and safe remediation

No authoritative, snapshot-attributable Domain objectGUID was found in the exact six-file export or its upstream ZIP. The snapshot does contain the Domain object's authoritative SID, which contract 1.3.0 can use as a typed stable Domain scope for namespace-relative domain identities. The DNS name is not used as identity, and host-relative SIDs still require a stable host GUID. The builder resolves the two missing, authoritative Windows well-known principals as explicit boundary nodes and still rejects unsupported references.

If a future collection seeks first-class records for these currently boundary principals, retain:

- the Domain object's observed domain SID and DNS name, plus `objectGUID` if available, all bound to the same collection;
- BloodHound/SharpHound schema and collector metadata;
- source/collection provenance and an immutable archive or snapshot digest;
- an explicit association between the evidence and the exact raw snapshot ID used by the parser.

Recollection is not required solely because Domain objectGUID is absent. If Domain objectGUID evidence for the existing snapshot is later recovered, it should take precedence through an explicit snapshot-scoped evidence record. Keep the raw files immutable.

`S-1-5-32-*` is native to the Windows well-known Builtin domain (`S-1-5-32`). AD DS exposes Builtin groups beneath each domain's `CN=Builtin` container. The key `domain:sid:<AD-domain-sid>:S-1-5-32-544` is this project's composite canonical namespace key for an observed object in a particular AD domain; it does not claim that Windows prefixes the Builtin SID with the AD Domain SID. Domain-relative security principals whose object SID is derived from the domain SID and a RID are a separate case. See Microsoft [MS-ADTS Builtin Container](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/64f3fef0-61c1-4b45-9407-5ccfb5385450), [Well-known SIDs](https://learn.microsoft.com/en-us/windows/win32/secauthz/well-known-sids), and [MS-ADTS Well-Known Domain-Relative Security Principals](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/06bf7793-8480-4a86-bf28-74f1d62f6955).

## Validation status

- Evidence investigation: complete; no authoritative domain GUID found.
- Adapter/normalizer safety: Domain SID fallback is implemented with GUID precedence, typed `domain:sid:<domain-sid>:<sid>` canonical IDs, and host-scope separation.
- Focused parser/builder tests: 213 passed. Full suite: 728 passed, 2 Windows-specific skips; 48 subtests passed. Contract validation passes. The old `674 passed, 1 skipped` note was stale before this work.
- Fail-fast canonical CLI: complete, 3,370 nodes, 53,774 edges, 3 unknown assessments, zero warnings. No `skip_record` graph was used for acceptance.
- Diagnostic `skip_record` graph: 3,366 nodes, 53,703 edges, contract-valid, 27 Domain-SID-scoped IDs, zero bare `S-1-5-32-*` IDs. It is diagnostic only and was not imported.
- Neo4j structural projection/count/query: project Compose `neo4j:2026.08.1` imported the nodes and edges of the validated PR-head JSON using explicit `--structural-projection`. Queries returned 3,370 nodes, 53,774 relationships, two boundary nodes, zero relationships with missing logical endpoints, zero duplicate edge IDs, and provenance on every edge. Every imported node and relationship carries the graph file digest; the exact current digest is recorded in PR #148's import evidence. The three non-traversable `unknown` assessments were **not** imported; they remain in canonical JSON. The importer reports their count, statuses, and digest.
- #135: its missing objectGUID observation remains true; Contract 1.3 Domain-SID scope resolves identity. Final issue acceptance remains open pending PR #148 cross-review and merge, coordinated through #138.

## Well-known boundary principal resolution

The loader produced 3,369 raw records and reconciliation/normalization produced 3,368 collected canonical nodes. Before the builder change, a full candidate inventory found exactly two unresolved direct relationship references among 53,929 candidates. Both are in `20210920185958_groups.json`: `#/groups/6/Members/3/MemberId` is `SEAMLESS.INTERNAL-S-1-5-4`, and `#/groups/8/Members/1/MemberId` is `SEAMLESS.INTERNAL-S-1-5-17`; both have `MemberType = Group`. The duplicate Group at `#/groups/549` has an empty `Members` array and was reconciled with Group `#/groups/6`; its representative record locator must not be mistaken for the member observation's origin. The adapter yields bare canonical SID references. There is no collected first-class object for either.

The builder first checks collected canonical IDs and aliases. Only the explicit, documented SID set `S-1-5-4` and `S-1-5-17` can then materialize a boundary endpoint; unsupported SIDs, malformed identifiers, incompatible kinds, and scoped Builtin/host-local SIDs still fail. The two boundary nodes have IDs `S-1-5-4` (INTERACTIVE) and `S-1-5-17` (IUSR), `kind=Group`, `domain=NT AUTHORITY`, and `is_boundary=true`. The graph kind records the collector's Group membership endpoint role; IUSR is a Windows account and is **not** claimed to be a collected AD Group. The IUSR Group-shaped boundary rule applies only to a `Members[].MemberId` source of `MemberOf` with `MemberType=Group`; an unresolved IUSR ACE principal cannot use it. Its Microsoft-described membership in the IIS_IUSRS group and the snapshot's `MemberType=Group` support this limited structural representation. The DNS prefix is context, not native SID identity or canonical scope. Edge provenance points to the observed `Members[].MemberId` occurrence; no objectGUID, DN, or first-class object evidence was manufactured.

Microsoft documents [INTERACTIVE as `S-1-5-4`](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/81d92bba-d22b-4a8c-908a-554ab29148ab), [IUSR as `S-1-5-17` and an IIS identity](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-special-identities-groups), and [NT AUTHORITY\\IUSR membership in IIS_IUSRS](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6108abed-3fb7-4c6a-b5fc-a755d60922f4). This narrow policy does not alter the Contract 1.3 Domain-SID rule for `S-1-5-32-*` or host requirements for `S-1-5-18/19/20`.

Canonical totals: User 2,493; Group 551 (549 collected, two boundary); Computer 100; OU 223; GPO 2; Domain 1. Edges: GenericAll 37,044; MemberOf 13,324; WriteDacl 3,395; AdminTo 9; CanPSRemote 2. Three assessments are `unknown` because required UserRights evidence is incomplete. There are 29 `domain:sid:` IDs, zero `domain:guid:` IDs, zero unsafe bare `S-1-5-32-*` IDs, and zero missing edge endpoints. Raw EDA's 66,374 reference observations and 66,371 materialized entries count a broader, differently shaped set of raw fields; they are not canonical edge counts. Canonical edges deduplicate logical triples and emit only contract-supported relationships.
