# Final taxonomy and rating audit v1

This is a reviewable final taxonomy proposal for #267, pending B numeric adoption.
It is not a declaration that production majority coverage has been achieved.
A owns the taxonomy/rubric; B cross-reviews each numeric/context group and the consumer contract.

All endpoints are exact rational expert scenario proposals.
Historical accepted values retain their source authority only for the original questions; broader identities/histories are additional pending equivalence judgments.
The new residual-workflow allowances are explicitly proposed scenario parameters, not inferred statistical measurements.

| Active event class | T1 | T2 | C | Conditional P proposal |
| --- | --- | --- | --- | --- |
| `directory_password_reset` | 1 | 2 | 1 | [3/5,19/20] |
| `reset_identity_activation` | 1 | 1 | 0 | [3/4,49/50] |
| `recovered_identity_activation` | 1 | 1 | 0 | [3/4,49/50] |
| `winrm_admin_execution` | 1 | 2 | 1 | [1/2,9/10] |
| `host_admin_execution` | 1 | 2 | 1 | [3/5,19/20] |
| `asrep_material_request` | 1 | 1 | 0 | [9/10,99/100] |
| `kerberoast_material_request` | 1 | 2 | 1 | [17/20,49/50] |
| `asrep_password_recovery` | 2 | 2 | 2 | UNRATED: conditional rank/compute basis absent |
| `kerberoast_password_recovery` | 2 | 3 | 3 | UNRATED: conditional rank/compute basis absent |
| `group_membership_mutation` | 1 | 2 | 1 | [4/5,49/50] |
| `grant_write_dacl` | 1 | 2 | 1 | [7/10,49/50] |
| `grant_generic_all` | 2 | 2 | 2 | [7/10,19/20] |
| `rdp_interactive_session` | 1 | 2 | 1 | [3/5,19/20] |
| `winrm_command_session` | 1 | 2 | 1 | [7/10,19/20] |
| `session_credential_material` | 2 | 3 | 3 | [1/4,4/5] |
| `rbcd_secret_acquisition` | 1 | 2 | 1 | [7/10,19/20] |
| `rbcd_service_preparation` | 2 | 2 | 2 | [4/5,49/50] |
| `rbcd_descriptor_mutation` | 2 | 2 | 2 | [4/5,99/100] |
| `rbcd_service_delegation` | 2 | 2 | 2 | [3/5,9/10] |
| `rbcd_admin_execution` | 2 | 2 | 2 | [3/5,19/20] |

Passive MemberOf has no active work unit, no C and no q.
One structural edge may support several explicit actions; AS-REP, TGS and RBCD stages may be capability/material transitions without a corresponding observed graph edge.
The complete evidence/action/prerequisite/effect mapping is in [taxonomy.json](taxonomy.json).
Every active row has technique-specific rationale in [profile.json](profile.json).

## Historical numeric audit

| Source judgment | Audit result | Current applicability |
| --- | --- | --- |
| Reset C=1, q=[3/5,19/20] | Standard authenticated directory reset with response verification; activation work excluded; three attempts/15m | Pending finite-history equivalence, no default for arbitrary LDAP mutation |
| Reset-derived activation C=0, q=[3/4,49/50] | Automated Kerberos exchange remains an active event despite zero ordinal cost; three attempts/10m | Exact reset lineage and valid account/context required; AS-REP/TGS recovered-secret lineage needs separate equivalence |
| Elevated WinRM C=1, q=[1/2,9/10] | Includes session setup, submission and elevated command verification; three attempts/30m | Same unrestricted endpoint/policy; cannot certify generic AdminTo transport, RDP or a non-admin session |
| AS-REP uniform24 [1/32,1/16] | Exact finite-model arithmetic for assumed 2^19..2^20 completed guesses, not natural-password probability | Withdrawn from current recovery profile; #266 V2 keeps archived oracle only |
| AS-REP acquisition historical q2 transfer | Reset-derived credential activation differs from compatible encrypted material acquisition | Replaced with a distinct request-event proposal; no automatic source authority |
| High on same historical DC | Typed administrative control threatens domain identity/authentication/access-control services | Exact admin_control(DC) mapping remains pending in each new scenario; session/material goals cannot borrow High |

A cap is a stop policy, not achieved compute coverage.
The 24h campaign and per-event retry/deadline policies form the question; they do not numerically transform a 24h probability into a minutes-scale rate.
For the named Source A inventory the sum of all eight event deadlines is at most 135 minutes, within the 24h horizon.
Passive steps consume the semantic search cap but contribute no active effort/event; the historical six-active-unit envelope and current ten-semantic-step cap require explicit scope review.
There is no independent-retry or independent-event assumption.
The path product uses q_i conditioned on every previous successful active work unit in its exact ordered history.

## Full-history equivalence and work overlap

The compiler emits all explicit exact prefixes in a finite causal rating domain before invoking search.
No generated lookup keys, candidate lists, graph-state evaluator or per-path rating packets are used to construct the registry.
The additional stable/no-depletion equivalence assumes that unrelated earlier successful operations do not invalidate the current secret, consume its exclusive event retry budget or change the named resource/account policy.
That is an expert scenario invariance assumption requiring B adoption, not a theorem or a marginal probability fallback.
Interleaved success can select latent reliability conditions; B may reject or split that equivalence instead of accepting equal endpoints across all histories.
Unlisted operations, repeated canonical work, different actors/auth context, secret invalidation, changed snapshot/horizon/policy and over-cap expansion are refused.

Shared preparation is counted once by canonical identity when an applicable decomposition rule exists.
The Source A workflow adds no generic auth_context preparation because reset activation and WinRM already contain their declared operations.
No new work decomposition rule is installed in B-owned code.
Offline C measures handling/tooling friction, not guessed entropy or GPU seconds; increasing the cap does not mechanically increase C or lower P.

## Typed technical impact

| Successful target consequence | Proposed I | Boundary |
| --- | --- | --- |
| Administrative DC identity/authentication/access-control control | High | Exact asset, snapshot, scenario, horizon and typed admin_control goal |
| Administrative control of a configured technical host | High | Separate scoped asset mapping; no DC-label inference |
| Usable identity or interactive/command session | Medium | No demonstrated administrative target control |
| Encrypted/credential material | Low | Intermediate material opportunity; no automatic logon/control |
| Usable Domain Admin entitlement checkpoint | High | Typed effective_member goal with token/role assumptions; not DC admin execution |

The core taxonomy uses technical consequences and creates no new business-valuation dependency.
Historical High does not become Critical from a DC/Tier0 label.
The existing provider may retain legacy business_rationale source fields; that source schema is not rewritten here.
The material side probe binds exact artifact lineage through the existing single-event semantic API before generation because the current typed goal contract compares full artifact provenance.
A general owner/context-only material goal requires B-owned goal-contract review; no wildcard or supplied ordered path is introduced.
The frozen Kerberoast User-identity goal exposes another B-owned attribution gap: activation satisfies usable_identity(owner, authentication Computer), but search also requires the final transition endpoint to equal the owner User.
A preserves that target/goal and reports native no_path plus the unreturned goal-state success event, rather than silently retargeting the Computer or declaring the identity safe.

## Coverage and integration limits

The frozen cohort reports per-query denominators, graph scope, source kind, goal, action family, caps and actual truncation.
The complete projection is distinct from capped full-raw runs.
Pooled projection/full-raw comparisons repeat some programs and are not independent snapshot-wide evidence.
The broader all-technique Source A control remains visible even where its classes/histories lack bindings.
Unsupported Group initial login, other node-kind footholds and missing raw RBCD-binding cases are explicitly reported.
A 100% synthetic wiring result can prove that native records are consumed correctly; it cannot establish B adoption, empirical calibration or production coverage.
A/B batch source ranking, shortest-path guarantees under truncation and remediation counterfactual/chokepoint sensitivity remain B-owned #265 integrations.
Query-local bound/assumption sensitivity is reported separately and cannot substitute for those product checks.

B receives the native envelopes generated by the existing resolver contract, profile/cohort digests, exact history-domain digest and class-specific refusal reasons.
B must record actual per-group adoption references and preserve estimated_expert_scenario plus truthful review disposition in public API/CLI output.
Until then, all new production records remain fail-closed and #267 stays open.

The native ordered_work_prefix includes the named outcome unit as a lookup identity.
Probability conditioning uses the preceding prefix only; the current outcome is not included as a numerical fact.
