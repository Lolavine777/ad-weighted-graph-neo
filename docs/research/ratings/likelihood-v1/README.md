# Likelihood Catalog v1 - #256

This package inventories every technique in the current executable Week 4 catalog and the structural, credential-artifact, reset-capability and RBCD producers in `generate_attack_paths`.
It supplies release decisions and independent oracles for #250/#251; it changes no provider, search, state, evaluator, Pareto or public CLI behavior.

## Coverage and numeric eligibility

There are **22 active techniques**, mapped to **20 canonical likelihood classes**, plus one passive membership class.
There are **11 REQUIRES_CONTEXT**, **11 UNRATED_NO_BASIS**, **0 RATED**, and **0 OUT_OF_SCOPE** active defaults.
The supported inventory is independent of the selected demo subset.
`OUT_OF_SCOPE` applies to unsupported techniques and boundary changes, not to inconvenient supported techniques.
The passive technique and derived membership/token closure are `NO_Q_EVENT`.
An active operation with a derived relationship or C=0 still requires q.
Successful initial-goal/zero-work queries are not fake q events.

| Active technique | Canonical likelihood class | Default disposition | Generator input |
| --- | --- | --- | --- |
| genericall_reset_password | directory_password_reset | REQUIRES_CONTEXT | GenericAll to User |
| reset_target_password | directory_password_reset | REQUIRES_CONTEXT | ForceChangePassword to User |
| scenario_reset_password | directory_password_reset | REQUIRES_CONTEXT | GenericAll to User plus reset-capability guards |
| acquire_reset_identity | reset_identity_activation | REQUIRES_CONTEXT | reset_password_control and authentication context |
| activate_recovered_identity | recovered_identity_activation | REQUIRES_CONTEXT | password-form recovered artifact |
| asrep_request | asrep_material_request | REQUIRES_CONTEXT | known user and scoped AS-REP request capability |
| recover_asrep_secret | asrep_password_recovery | UNRATED_NO_BASIS | scoped AS-REP material |
| kerberoast_request | kerberoast_material_request | REQUIRES_CONTEXT | known SPN-bearing user and scoped TGS request capability |
| recover_ticket_secret | kerberoast_password_recovery | UNRATED_NO_BASIS | scoped TGS material |
| obtain_admin_execution_on_host | host_admin_execution | REQUIRES_CONTEXT | AdminTo to Computer |
| scenario_winrm_admin | winrm_admin_execution | REQUIRES_CONTEXT | declared Group-to-Computer administrative mapping |
| open_winrm_remote_session | winrm_command_session | REQUIRES_CONTEXT | CanPSRemote to Computer |
| open_remote_interactive_session | rdp_interactive_session | REQUIRES_CONTEXT | CanRDP to Computer |
| genericall_add_member | group_membership_mutation | UNRATED_NO_BASIS | GenericAll to Group |
| genericall_grant_write_dacl | grant_write_dacl | UNRATED_NO_BASIS | GenericAll to each supported object kind |
| grant_new_object_right | grant_generic_all | UNRATED_NO_BASIS | WriteDacl to each supported object kind |
| recover_session_credential_material | session_credential_material | UNRATED_NO_BASIS | HasSession from controlled host to User |
| rbcd_acquire_secret | rbcd_secret_acquisition | UNRATED_NO_BASIS | exact RBCD binding and reset right |
| rbcd_prepare_service | rbcd_service_preparation | UNRATED_NO_BASIS | scoped RBCD secret and existing SPN |
| rbcd_configure_descriptor | rbcd_descriptor_mutation | UNRATED_NO_BASIS | exact RBCD binding and descriptor right |
| rbcd_delegate_service | rbcd_service_delegation | UNRATED_NO_BASIS | service + descriptor artifacts and impersonated identity |
| rbcd_service_admin | rbcd_admin_execution | UNRATED_NO_BASIS | exact delegated service context |

`propagate_group_entitlement` follows existing or branch-added MemberOf and adds no active work.
All source/target kinds, exact gates and effects are recorded per technique in `catalog.json`, including the six DACL target kinds.
Structural `GenericAll`/`WriteDacl` permissions and branch-added permission relationships use the same action candidates.
The five credential and five RBCD producer owners are checked against executable owner sets.
Shared authentication preparation is a resolver work class, not another generated technique.
If explicitly executed, it requires its own q basis once per distinct work identity; reuse creates no new q event.
Catalog v1 has no accepted likelihood basis for such preparation.

`REQUIRES_CONTEXT` means a context-specific event assessment or equivalence could be sought; it does not promise a number merely after filling metadata.
`UNRATED_NO_BASIS` additionally identifies a missing numeric event basis or representative population.
All class records define success event, required active work and non-applicability.
The global context contract includes actor/source capability, target class, method, authentication/resource context, boundary, retry/execution policy, budget, horizon and the full ordered prior-success history.
Null binds absence and is never a wildcard.
Missing any required q leaves P(path) null.
No difficulty-to-probability, C-to-P, impact/CVSS/MAUT, LLM-confidence or assumption-to-q conversion is permitted.
The #238 empirical prototype remains quarantined.

## Exact Source-A binding proposal

`bindings.json` contains eight proposed contextual bindings for the two historical Source-A programs, covering only `scenario_reset_password`, `acquire_reset_identity`, and `scenario_winrm_admin`.
Each pins its unchanged Week 3 q record, review pair, interval, canonical generated lookup key, all ordered work identities, source, actor, target, authentication context, resource absence and bounded retry policy.
The full keys are re-derived independently from the accepted #181 bridge, without running search.
These are the same generated-key digests proposed by #254 on head `2ee8a1fb123bbf82d2ee0026c0965d0ca1ac89d5`.
No alias mapper or fuzzy name matching is introduced.
Each record remains `proposed_pending_b_review`, with `numeric_reuse_permitted=false`.
The checker cannot accept or auto-load them.
`proposed_provider_records()` exposes validated exact records through the merged #254 API while preserving pending status and unrated disposition.
The generated probe explicitly supplies these records to #254 and checks that every matching pending prefix is refused without numeric output.

The semantic equivalence proposal is narrow: reset produces reset-secret control, activation uses that reset secret in the exact authentication context, passive groups supply the accepted authorization source, and WinRM produces administrative execution on the exact DC asset.
The full historical retry policy allows at most three attempts per event, with reset/ticket/WinRM deadlines of 15/10/30 minutes within the 24h campaign horizon.
The engine does not simulate retries; the historical intervals already condition on this policy.
B must accept or reject expanded contextual identity and applicability per record.
#254 implementation approval does not grant numeric reuse.
Generic password-control, recovered-password activation, RBCD delegation, CanPSRemote command execution and transport-unspecified AdminTo are not accepted aliases.

No new interval is proposed beyond copies of unchanged accepted historical bounds.
For other classes, an honest gap is preferable to an unreviewed probability guess.
For recovery, a defensible new record needs material/encryption/password population, actual method/resource limits, operational horizon and an eligible judgment or representative evidence campaign.
The unmeasured #243 budget and `recovery_success=true` cannot provide that basis.

## C/I release decisions

`release-dispositions.json` covers all 23 pending C classes by source digest and rubric.
Ten are recommended `ACCEPT_SCOPED` for the exact Source-A, frozen #243 or synthetic-a2 recipes.
Eleven stay `HOLD_UNRATED`; unconstrained delegation stays `KEEP_UNRATED` and cross-forest stays `KEEP_OUT_OF_SCOPE`, both outside the supported-action denominator.
No wildcard class is activated and no existing C provider is rewritten.
The source catalog's direct/inherited friction assumptions remain synthetic-a2-specific.
The #243 recovery cost is an explicit work-rubric judgment, not measured compute effort or a P basis.
The generic LSASS/session mapping needs an extraction-method assessment.
The RBCD secret/preparation descriptions must be reviewed against existing-user reset and key derivation/authentication, without claiming account creation or SPN registration.

For Source-A, retain the accepted High consequence on the same canonical asset and exact `terminal_compromise_seamless_dc` event with `admin_control_badblood` predicate.
That historical comparison needs no impact event equivalence.
For #243, recommend only directional mapping `eq-seamless-frozen-admin-execution-004`: same C0 asset, `admin_execution_on_C`, `admin_control(C0)` and `admin` predicate.
Its consequence can be independent of recovery horizon while P remains horizon-bound.
Unqualified terminal events, DA membership, different host assets and transitive event equivalence remain excluded.
Both expanded release decisions remain pending B review.

## Frozen independent demos

`min-effort-input.json` is a declarative query with no candidates, ordered paths, action IDs, ranking packet or q values.
`oracles.json` freezes expectations before the demo runner's first execution.
The frozen-input/oracle commit is recorded in `verification.md` after execution.
The runner reads expectations and never rewrites them.

The synthetic-a2 Min-Effort case must generate three alternatives with C multiset `[2,5,5]` under an isolated test-only acceptance simulation of scoped C classes.
Shared preparation costs 1 once, direct active work costs 4 and inherited active work costs 1.
The winner uses passive membership and inherited authorization in two steps.
Actual pending-provider C remains null; simulated acceptance is not B acceptance or public CLI integration.

The risk case must generate at least the two historical Source-A programs through the current generator and manifest-verified private raw inputs.
Only after generation may exact transition identities be matched to accepted historical labels.
The original #181 bridge and existing canonical adapter can evaluate these generated programs under the unchanged accepted historical C/P/I basis.
Independent expected P intervals are `[9/40,8379/10000]` and `[81/800,7800849/10000000]`, from three and five full-history q events respectively.
Both have High impact and overlapping intervals, so neither dominates; effort 2 versus 3 does not resolve overlapping risk intervals.
The direct program minimizes C within this reviewed subset.
The source search reaches its expansion cap, so no exhaustive, K-best, global minimum or global Pareto claim is permitted.
The expanded resolver keys still have null P until B review and #250 activation.

Frozen #243 is consumed from its original specification and manifest-verified raw via the existing frozen-input helper.
It must generate exactly request, recovery, recovered-identity activation and generic host administration, preserve the false DA checkpoint and all four P gaps, and preserve `fixed-snapshot-window`/`unmeasured-budget`.
Proposed C is `[0,2,0,1]`, total 3, and proposed I is the scoped directional High equivalence.
The coverage helper's numeric work-budget-zero field is only an audit sentinel and cannot satisfy recovery-budget applicability or establish ranked eligibility.
Raw inputs, full generated traces and local identities remain local; the committed verification report is sanitized.

## Merged dependency compatibility

#254 merged as develop `94db074b5cd5c74b76b5e2555d59c5a952153b7e` during this work.
The branch was rebased onto that commit and the resolver/provider source pins were refreshed.
The supported actions, eight binding identities, numeric source records and frozen oracle bytes did not change.
The package now checks the merged provider API directly, including refusal of every pending matching record.
This is a non-activation check, not certification of accepted-record applicability.
#250 must derive and supply validated per-event provider scope for capability, target class, control scope, retry policy and population; the proposal alone is not runtime evidence.

## Reproduction and remaining gates

```sh
./.venv/bin/python -m scripts.research.likelihood_catalog
./.venv/bin/python -m scripts.research.likelihood_demo_probe --raw-dir /path/to/manifest-verified/SEAMLESS --output /tmp/likelihood-v1-private.json
./.venv/bin/python -m pytest tests/test_likelihood_catalog_v1.py
```

Use the existing checkout's virtual-environment executable when this isolated worktree has no `.venv`.
The generated probe verifies the package byte pins before running search.
Relevant changed authoritative bytes require explicit re-inventory/refreeze, not an automatic manifest rewrite.
No private input or generated result is used to author an oracle.

Before #250/#251: B must accept exact P bindings, scoped C subsets and the #243 I equivalence; B must implement automatic public-flow catalog consumption; public generated CLI coverage/ranking and independent cross-reproduction must then pass.
Frozen #243 may remain P-unrated even after the other gates.
No review decision, issue closure, CI PASS, final Week 4 acceptance or merge is implied by this package.
