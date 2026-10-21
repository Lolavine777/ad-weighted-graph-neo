# Synthetic parser semantics demo

This fixture illustrates how the parser turns raw, object-centric observations into a
canonical graph under Graph Contract 1.2.0. All names, SIDs, GUIDs, and timestamps here are
invented. The envelopes use parser-supported SharpHound v3-style fields; they are illustrative
inputs, not a claim that a real collector produced these exact records.

For a live presentation, follow the [mentor walkthrough](MENTOR_WALKTHROUGH.md). It gives the
screen order, talking points, and expected output for each raw-to-graph transformation.

## Run the happy path

From the repository root, with the development requirements installed:

```bash
python -m src.parser.cli --snapshot-id sha256:1f76e5bdeffbc474fa55872fe328806faf35a23f29525d8adfeecc1f6484a5d4 --raw-dir data/samples/parser-demo-rich-input --manifest-dir data/samples/manifests --time-policy data/samples/parser-demo/time-policy.json --created-at 2026-09-25T00:00:00Z --output data/processed/graphs/parser-demo-rich.json --summary
```

Expected summary: 6 nodes, 10 edges, and 1 unknown assessment. The output is a canonical graph
JSON file under the ignored `data/processed/` directory. The manifest pins every raw input byte;
`time-policy.json` supplies an **assumed** collection time because the synthetic manifest has
`collected_at: null`. `--created-at` is the separate graph export time.

The short names below refer to these IDs:

| Name | Canonical ID |
| --- | --- |
| Alice | `S-1-5-21-4100-4200-4300-1101` |
| Bob | `S-1-5-21-4100-4200-4300-1102` |
| Helpdesk | `S-1-5-21-4100-4200-4300-2101` |
| Operators | `S-1-5-21-4100-4200-4300-2102` |
| WS01 | `S-1-5-21-4100-4200-4300-3101` |
| WS01 Administrators | `host:a1b2c3d4-1111-4222-8333-abcdef012345:S-1-5-32-544` |

## Follow the evidence

| Raw observation | Parser decision | Canonical result |
| --- | --- | --- |
| `groups.json`: Helpdesk contains Alice. `groups-repeat.json`: Helpdesk contains Alice and Bob. | Reconcile the two Helpdesk records; union the `Members` evidence. | One Helpdesk node; Alice → Helpdesk and Bob → Helpdesk `MemberOf` edges. Alice's edge has one ID and two provenance records with different `raw_file` values. Bob's evidence comes from `groups-repeat.json`. |
| `groups.json`: Operators contains Helpdesk. `computers.json`: WS01's local Administrators group contains Operators. | Resolve nested membership for host access. | Direct Helpdesk → Operators `MemberOf` and Operators → WS01 `AdminTo`; derived Alice → WS01 and Bob → WS01 `AdminTo` edges (and Helpdesk → WS01). No transitive `MemberOf` shortcut. |
| Bob's `Aces[]` in `users.json` names Alice as principal for `GenericAll` and `ForceChangePassword`. | Read the ACE from the target object and reverse its object-centric layout into privilege-flow direction. | Two parallel Alice → Bob edges, one per right. |
| WS01's `Sessions[]` in `computers.json` names Bob. | Treat the host as the source of the session observation. | WS01 → Bob `HasSession`. |
| WS01's `RemoteDesktopUsers[]` names Alice; effective `UserRights` allow/deny evidence is absent. | Preserve the unknown access decision. | One `CanRDP` assessment for Alice and WS01, with `status: unknown`; no traversable `CanRDP` edge. |
| WS01 carries a synthetic `host_guid` context; the built-in Administrators group record has SID `S-1-5-32-544` and an explicit host scope with that GUID. | Scope the namespace-relative SID and lowercase the GUID. | The `host:...:S-1-5-32-544` Group node shown above. The `host_guid` and `scope` fields are synthetic parser context fields, not collector-native claims. |

For Alice → WS01, inspect `edges[]` where `kind` is `AdminTo` and `source` is Alice's SID.
Its `derivation.paths[0].steps` show this ordered proof:

1. `effective_membership`: Alice → Helpdesk, backed by both group files.
2. `effective_membership`: Helpdesk → Operators, backed by `groups.json`.
3. `host_local_membership`: Operators → WS01, backed by `computers.json`.

Each step's `evidence_refs` resolves to a record in that edge's `provenance` array. The two
group files are intentional: exported provenance identifies a raw file and logical record,
while a record locator is only available inside the parser. Two identical occurrences in
the same file would not produce two distinct exported provenance records.

## Compare error policies

The independent error snapshot has a valid user, then a user without a stable SID/GUID, then
another valid user. Its manifest is valid, so this tests record handling rather than snapshot
integrity or JSON parsing. Run each command with a fresh output path:

```bash
python -m src.parser.cli --snapshot-id sha256:b7ac113cf44525d3c638eb8a29dc219257a142a8d2c0debb4764d580c7a9183c --raw-dir data/samples/parser-demo-error-input --manifest-dir data/samples/manifests --time-policy data/samples/parser-demo/time-policy.json --created-at 2026-09-25T00:00:00Z --error-policy fail_fast --output data/processed/graphs/parser-demo-error-fail.json --summary
python -m src.parser.cli --snapshot-id sha256:b7ac113cf44525d3c638eb8a29dc219257a142a8d2c0debb4764d580c7a9183c --raw-dir data/samples/parser-demo-error-input --manifest-dir data/samples/manifests --time-policy data/samples/parser-demo/time-policy.json --created-at 2026-09-25T00:00:00Z --error-policy log_warning --output data/processed/graphs/parser-demo-error-warn.json --summary
python -m src.parser.cli --snapshot-id sha256:b7ac113cf44525d3c638eb8a29dc219257a142a8d2c0debb4764d580c7a9183c --raw-dir data/samples/parser-demo-error-input --manifest-dir data/samples/manifests --time-policy data/samples/parser-demo/time-policy.json --created-at 2026-09-25T00:00:00Z --error-policy skip_record --output data/processed/graphs/parser-demo-error-skip.json --summary
```

`fail_fast` exits nonzero without writing a new graph. `log_warning` emits a warning and writes
both valid users; `skip_record` writes the same two users without a warning. Neither successful
run creates an edge from the malformed record.

The executable expectations are in [test_parser_demo.py](../../../tests/test_parser_demo.py).
