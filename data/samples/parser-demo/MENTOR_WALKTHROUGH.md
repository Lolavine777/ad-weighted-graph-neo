# Mentor walkthrough: raw evidence to canonical graph

Use this as a 6–8 minute live walkthrough of the [synthetic parser demo](README.md).
It shows what to put on screen and what each result means. These records are invented;
they demonstrate parser behavior, not findings about a real AD environment.

## Prepare the screen

Run the happy-path command in the [demo README](README.md#run-the-happy-path) before the
meeting. It writes `data/processed/graphs/parser-demo-rich.json` and prints **6 nodes,
10 edges, 1 unknown assessment**. Open the raw files and that output side by side. The graph
JSON is compact; use an editor's JSON formatter or make a local display copy:

```bash
python -m json.tool data/processed/graphs/parser-demo-rich.json > data/processed/graphs/parser-demo-rich.pretty.json
```

The display copy is for reading only. The CLI output is the canonical file. In the graph,
find an edge by its `source`, `target`, and `kind`; the short names below save reading the
full SIDs aloud.

| Short name | SID suffix |
| --- | --- |
| Alice | `1101` |
| Bob | `1102` |
| Helpdesk | `2101` |
| Operators | `2102` |
| WS01 | `3101` |

## Walk through the happy path

1. **Start with the trusted input (about 30 seconds).** Show the rich [manifest](../manifests/parser-demo-rich-v1.json): four raw files are pinned by size and hash, and `collected_at` is `null`. Show [time-policy.json](time-policy.json): the demo supplies an **assumed** collection time. In the graph `metadata`, `created_at` is a separate export time. Say: “The parser knows which bytes it read and does not invent an observed collection timestamp.”

2. **Reconcile repeated observations (about 1 minute).** Put [groups.json](../parser-demo-rich-input/groups.json) and [groups-repeat.json](../parser-demo-rich-input/groups-repeat.json) side by side. Both contain Helpdesk (`...2101`) and Alice (`...1101`); the second also contains Bob (`...1102`). In `nodes[]`, find **one** Helpdesk node. In `edges[]`, find Alice → Helpdesk `MemberOf`: there is **one edge ID** whose `provenance[]` names both group files. Bob → Helpdesk comes from the repeat file. Say: “The second observation adds evidence and Bob; it does not erase Alice or create another logical Helpdesk.”

3. **Resolve the group and host path (about 2 minutes).** In `groups.json`, Operators (`...2102`) contains Helpdesk. In [computers.json](../parser-demo-rich-input/computers.json), WS01's `LocalGroups[].Results[]` puts Operators in local Administrators. Point to the direct edges Alice → Helpdesk `MemberOf`, Helpdesk → Operators `MemberOf`, and Operators → WS01 `AdminTo`. Then find Alice → WS01 `AdminTo` and expand `derivation.paths[0].steps`:

   | Order | Operation | Source → target | Raw support |
   | --- | --- | --- | --- |
   | 0 | `effective_membership` | Alice → Helpdesk | Both group files |
   | 1 | `effective_membership` | Helpdesk → Operators | `groups.json` |
   | 2 | `host_local_membership` | Operators → WS01 | `computers.json` |

   Each step has `evidence_refs` pointing to that edge's `provenance[]`. Say: “The parser can explain *why* it emitted Alice → WS01. It keeps the direct membership topology; it does not add a transitive `MemberOf` shortcut.” Bob has the same derived route. The graph also emits `AdminTo` for Helpdesk and Operators, so four `AdminTo` edges is expected.

4. **Translate object-centric ACL and session evidence (about 1 minute).** In [users.json](../parser-demo-rich-input/users.json), Bob's object contains `Aces[]` naming Alice as principal for `GenericAll` and `ForceChangePassword`. In the graph, point to **two distinct** Alice → Bob edges, one per right. Back in `computers.json`, `Sessions[]` names Bob; the graph has WS01 → Bob `HasSession`. Say: “The raw object holding the observation does not always become the edge source. Direction follows the graph contract.”

5. **Show a decision the parser refuses to overstate (about 1 minute).** In `computers.json`, `RemoteDesktopUsers[]` names Alice. Find the graph's `CanRDP` assessment with `subject` Alice, `target` WS01, and `status: unknown`. Its reason is `required UserRights evidence is incomplete`. Search `edges[]` for `CanRDP`: there is none. Say: “Membership alone does not establish effective RDP access; unknown evidence stays outside traversable edges.”

6. **Show canonical identity (about 30 seconds).** In `groups.json`, the built-in Administrators SID `S-1-5-32-544` has an explicit host scope with the GUID shown on WS01. In `nodes[]`, find `host:a1b2c3d4-1111-4222-8333-abcdef012345:S-1-5-32-544`. Say: “A host-local SID needs a stable scope, and the canonical ID normalizes the GUID to lowercase.” The scope fields are synthetic parser context, not native collector proof.

## Optional: malformed-record policy (about 1 minute)

Show [error-input/users.json](../parser-demo-error-input/users.json): a valid user, one missing a stable SID/GUID, then another valid user. Use the three commands in the [error-policy section](README.md#compare-error-policies), each with its own output path. `fail_fast` stops with a nonzero exit and no new graph; `log_warning` reports the bad record and exports two valid nodes; `skip_record` exports those same nodes quietly. The valid manifest ensures the failure is the record, not a corrupted snapshot.

## Close

The demonstration is about reconciliation, canonical direction, evidence lineage, and honest uncertainty. The `unit` edge weights are a baseline for graph structure; this fixture does not validate attack likelihood, production weighting, or real-world host access. The exact expectations are protected by [test_parser_demo.py](../../../tests/test_parser_demo.py).
