# Exact frozen Week 4 maintainer disposition

Role: **A maintainer weekend disposition / self-verification**.
No independent B review is claimed.
Authority and required scope are recorded in [#251 comment 6107466502](https://github.com/nairyuuu/ad-weighted-graph/issues/251#issuecomment-6107466502).

The separate [packet](frozen243-disposition.json) adopts only four exact generated work identities in `week4-seamless-v1` and the same BADBLOOD DC asset's typed terminal consequence.
The original broad work-class and impact registries remain pending, and historical Week 3/#243 bytes remain unchanged.

| Work | Semantic method | T1 | T2 | C |
| --- | --- | --- | --- | --- |
| AS-REP request | `ASRepTarget` | 1 | 1 | 0 |
| Offline secret recovery | `offline-password-prediction` | 2 | 2 | 2 |
| Recovered identity activation | `RecoveredSecret` | 1 | 1 | 0 |
| Terminal host administration | `AdminTo` | 1 | 2 | 1 |

The values use the existing integer work rubric, C=T1+T2-2.
The request and activation are bounded protocol exchanges; recovery requires specialized tooling and compute, while terminal administration requires an authenticated execution channel.
No EDR/detectability discriminator or probability is introduced.
The independently specified path total is C=3.

Each class binds exactly one technique, semantic method, active work class, scenario, snapshot and canonical work-identity digest.
`work_unit_digests` contains SHA-256 of the canonical JSON string of the work identity, using the existing canonical digest function.
That identity includes actor, target and the digest of source, method, authentication/resource context, policy and scenario.
Recovery resource context includes its declared method, unmeasured budget and fixed snapshot horizon.
The identities are derived from frozen locator-resolved inputs and the published identity formula, not chosen from ranked output.
Digests keep the new private source/target identities out of this public packet.
The new optional selectors use the existing class applicability matcher and do not alter old class serialization.

The one I mapping adopts the accepted Week 3 High consequence on the same DC asset for exact `goal_id=admin_control(C0)`, typed `admin_control` terminal goal, scenario, snapshot and `intra_forest` boundary.
Its source rating and canonical release digests remain pinned.
The existing typed-goal contract supersedes legacy predicate-only matching.
Terminal consequence severity remains independent of the recovery horizon.
Secret recovery, identity usability, DA membership, another asset or a weaker terminal goal cannot borrow this High mapping.
Native mapping status `reviewed` records the A maintainer adoption described in its provenance; it does not claim B review.

All four P prefixes remain unrated with localized missing-evidence reasons.
This frozen case supplies semantic and C/I acceptance; the separate bounded Source A historical transfer supplies differing C and exact P/I risk comparison.
Canonical Source A proposals and equal-rating synthetic integration fixtures are unchanged.
Source A acceptance remains explicitly scoped to the two frozen historical prefix chains, with 22 other generated paths P-unrated.

Run the raw-backed public reproduction from committed source:

```sh
.venv/bin/python -m scripts.research.week4_maintainer_disposition --raw-dir data/raw/SEAMLESS --output reports/generated/week4-maintainer-disposition/acceptance.json
```

The existing raw manifest verifier runs before graph construction.
The consumer checks committed source and packet bytes, all seven immutable semantic controls, two complete CLI packages per case, API equality and successful-case orchestration equality.
It asserts actual per-unit C=0,2,0,1, path C=3, High impact and C=4/4, P=0/4, I=1/1 coverage.
Full private query/process outputs remain ignored locally; only sanitized summaries and digests are published.
