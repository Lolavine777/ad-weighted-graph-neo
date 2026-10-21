# Wave 2 release candidate for #267/#271

`decisions.pending.json` is a review candidate, with no new production adoption.
It reuses the numbers in [B's numeric decision](https://github.com/nairyuuu/ad-weighted-graph/issues/267#issuecomment-6142406787), the existing finite-history compiler and native providers.
The actual Wave 1 release remains unchanged and continues to govern its five Source A queries.
B's 17 class values are already accepted and are not being submitted for another numeric vote.
The unresolved authority is the exact finite context/history domain; the existing comment explicitly requires separate validation and does not adopt history invariance universally.

The pending candidate binds eight existing query contexts before search.
It does not select candidate paths, change cohort membership, change search/attack/retry budgets, invent edges or introduce a scoring system.
Public metadata contains typed goal field names and a digest; canonical actor/target/state identities stay in private query artifacts.
Production `apply_release` refuses pending status, missing reviewer authority, unadopted contexts/history, changed input/query/registry domains, changed numbers and unsupported typed impact.
The release CLI refuses overwriting an existing artifact.

| Context | Declared C records | Exact P records | Typed I | B decision needed |
| --- | ---: | ---: | --- | --- |
| winrm-command | 1 | 1 | Medium | Non-admin WinRM context, one conditional event and bounded retries |
| acl-group-host | 7 | 212 | High | Exact rights/membership/SMB-RPC context and every listed full history |
| rbcd-scoped | 5 | 14 | High | Exact controller/principal/host/HTTP service binding and preparation/descriptor/delegation histories |
| acl-group-projection | 7 | 212 | High | Same selector, separately pinned induced graph diagnostic context |
| acl-group-all-generator | 7 | 212 | High | Same inventory with all-generator caps; uncovered owners remain unrated |
| kerberoast-material | 1 | 1 | Low | Material request only, supplied usable identity and exact SPN-bearing target |
| asrep-natural-password | 4 | 3 | High | Request and recovery C-only; recovery P and recovered activation remain withheld |
| kerberoast-identity | 3 | 2 | Medium | Request and recovery C-only; no numeric adoption of recovered activation or missing recovery P |

Record counts describe the declarative registry, not generated paths or adopted observations.
P records include pending classes excluded from adoption; the preview explicitly restores their unresolved records.
The unassumed RBCD control is outside the candidate domain.
Projection, all-generator and unassumed controls stay outside the supported raw supplement denominator.
RBCD service/SPN and runtime conditions remain named scenario declarations, without observed exploitation or raw SPN proof.

## Reproduce

Use the repository virtual environment and authorized manifest-verified raw input.
Generate a separate candidate file to compare with the committed pending artifact:

```sh
.venv/bin/python -m scripts.research.final_cpi_release --template --wave2 --raw-dir data/raw/SEAMLESS --output /tmp/wave2-pending.json
.venv/bin/python -m scripts.research.final_cpi_wave2_replay --group supplementary --case winrm-command --raw-dir data/raw/SEAMLESS
.venv/bin/python -m scripts.research.final_cpi_wave2_replay --group supplementary --case acl-group-host --raw-dir data/raw/SEAMLESS
.venv/bin/python -m scripts.research.final_cpi_wave2_replay --group supplementary --case rbcd-scoped --raw-dir data/raw/SEAMLESS
```

Repeat `--group original --case ID` for all eight IDs in `../final-cpi-v1/cohort.json`, and `--group supplementary --case ID` for all six IDs in `../final-cpi-v1/supplementary-cohort.json`.
Then aggregate:

```sh
.venv/bin/python -m scripts.research.final_cpi_wave2_replay --aggregate --raw-dir data/raw/SEAMLESS
.venv/bin/python -m pytest tests/test_final_cpi_wave2_release.py tests/test_final_cpi_wave2_replay.py tests/test_final_cpi_profiles.py tests/test_final_cpi_release.py -q
```

Private graphs, queries and normalized native results remain under ignored `reports/generated/issue267-wave2-replay-v2`.
The current sanitized report is `reports/research/issue267-wave2-replay-v2.json`, including native step-level blocker ledgers.
The earlier `issue267-wave2-replay.json` remains preserved with its original executable pins.
Native CLI repetition verifies determinism and full program identity; it never adds attacks to a denominator.
API/CLI comparison covers exposed semantic outcomes, caps, guarantees, ranking, coverage and ordered full programs.
Orchestration comparison covers its exposed search/program/ranking fields.
Independent arithmetic sums C once per canonical work identity and multiplies exact full-history conditional bounds with `Fraction`.

## Decisions requiring B approval

One consolidated packet covers reusable profiles, not one approval per returned path.

1. Priority group: approve or withhold the exact WinRM command, ACL/Group/SMB-RPC host-admin and RBCD controller/principal/HTTP-service context and finite history domains already enumerated here.
2. State whether the unchanged `stable-no-depletion-distinct-work-v1` judgment applies to those exact inventories, including distinct rights/preparation work and the three RBCD event orderings, without secret invalidation or retry depletion.
3. Secondary group: approve or withhold the existing roasting request/C-only contexts and the two separately pinned ACL diagnostic controls.
   This does not ask for recovery P or recovered-identity activation approval without new evidence.
4. Apply the existing typed consequence decision to those exact terminal goals: command capability Medium, material Low and configured host administrative control High.
5. Record one actual context/history decision reference and its timestamp/confirmation in a new adopted artifact, with withheld contexts marked `needs_evidence` or `reject`.
   Class values/dispositions reuse the existing numeric decision unchanged.

No repeated numeric elicitation or per-path hand-written rating packets are required.
The native release overlay is implemented and tested; activation and a new production replay require the real context/history decision.

The candidate replay command intentionally consumes the existing Wave 1 production artifact and the pending Wave 2 preview.
It cannot validate a future adopted release without an explicit production integration and new evidence namespace.

The current pending file must remain as the proposal record.
Synthetic candidate wiring is engineering evidence and cannot count as production adoption or satisfy the production coverage gate.
The class-family tables count program occurrences containing each family and overlap; never sum them into cohort totals.
Truncated samples, the User-goal endpoint gap, unsupported RDP/session binding, natural-password recovery and wider source/batch/chokepoint sensitivity remain explicit limitations.
The exact current inventories exclude alternative reset methods that would invalidate an already activated secret; adding such a domain requires explicit invalidation handling or a history split.
No self-merge or closure of #267 is authorized.

The final acceptance gate remains open: the current production original cohort is 48/50 and the supported raw supplement is 0/7.
Candidate wiring reaches 49/50 and 7/7 with recovery P and recovered activation still unresolved, but these are explicitly synthetic engineering results.
The three raw ACL/host paths do not exercise membership mutation or grant-WriteDacl; those actions appear only in the separately disclosed diagnostic inventory.
The Kerberoast usable-identity case still reports native `no_path` despite a successful goal-state activation attempt; B owns the User-goal endpoint/state attribution decision.
