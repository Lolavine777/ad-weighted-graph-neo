# Issue #80 audit: disabled-account pruning and host-access semantics

Status: accepted research decision for M2 truth migration Issue: #80 Primary structural dataset: SEAMLESS (`BloodHound v3`-style SharpHound export) Historical regression/reference datasets: A/NORTH and B/`ad_sampledata` Architecture boundary: ADR-0008 (`Structural Relationship != Attack Technique != Observed Activity`)

## 1. Decision summary

The structural graph MUST preserve source-backed authorization/topology evidence even when the principal is currently disabled or a runtime transport/service is unavailable.
Runtime usability belongs to Attack Semantics predicates.
Missing or failed collection is tri-state `unknown`, never an implicit `false`.

The only deliberately hybrid area in this audit is GPO-derived host access: a policy setting/link alone is non-traversable assessment evidence, while a fully resolved resultant/effective host state may be promoted to positive **derived structural** evidence with complete provenance.

The following current invariants are rejected:

1. `enabled == false => out_degree == 0`.
2. `RemoteDesktopUsers[] => verified CanRDP`.
3. `RDU membership OR SeRemoteInteractiveLogonRight => CanRDP`.
4. `Connectable/service/port state => structural edge existence`.
5. `StatusAccessDenied` or a missing field => negative evidence.
6. `HasSession` means credential dumping is possible or happened.
7. Any scoped GPO reference is automatically either a traversable edge or permanently non-traversable solely because it was derived.

## 2. Normative layer model

| Layer | Meaning | Examples in this audit |
| --- | --- | --- |
| `structural` | Direct snapshot-backed relationship/authorization evidence | direct `MemberOf`, direct local-admin membership, observed session |
| `derived structural` | Relationship derived from complete structural primitives while retaining the derivation chain | effective nested local-group membership, fully resolved resultant GPO state, effective `CanRDP` composite |
| `runtime` | Scenario-dependent condition required to exercise a relationship | `actor_enabled`, `rdp_available`, `winrm_available`, `authentication_accepted`, `session_fresh` |
| `assessment/unknown` | Evidence is incomplete, simulated, rejected, or collection status prevents a conclusion | `StatusAccessDenied`, missing UserRights, unresolved GPO applicability |

A runtime predicate MUST NOT create, mutate, or delete canonical structural topology.
A disabled account is therefore not pruned from the graph merely because a fresh authentication attempt would currently fail.

## 3. Authoritative conclusions

### C1. Disabled principals retain structural relationships

**Claim.** Disabling an account changes account usability, not the existence of source-backed directory ACLs, group memberships, local-group assignments, or previously observed session relationships.
Structural evidence is preserved.
Technique-specific use of the account is evaluated separately with runtime predicates such as `actor_enabled` when fresh authentication is actually required.

- **Layer:** structural + runtime
- **Authoritative sources:**
  - Microsoft `userAccountControl` / `ACCOUNTDISABLE`: https://learn.microsoft.com/troubleshoot/windows-server/active-directory/useraccountcontrol-manipulate-account-properties
  - Microsoft `memberOf`: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-ada2/cc24555b-61c7-49a2-9748-167b8ce5a512
  - ADR-0008 runtime-state separation.
- **Applicable population/schema:** all snapshots and all canonical edge kinds; account-enabled state is a node/runtime fact, not a collector-specific edge primitive.
- **Confidence:** High.
- **Direct consequence for #44/#45:** #44 MUST NOT filter nodes/edges by `enabled`; #45 MUST retain host-access evidence for disabled principals. Attack Semantics MAY require `actor_enabled` for a specific transition.
- **Regression counterexample:** disabled User A has a positive `GenericAll` ACE on User B. `GenericAll(A,B)` remains structural; a transition requiring A to perform a fresh authenticated write may be blocked.

Note: `actor_enabled` is not a universal retroactive invalidator.
Existing sessions/tokens and other technique-specific contexts must be evaluated by the chosen transition rather than by a blanket graph rule.

### C2. Canonical `CanRDP` is a composite effective authorization

**Claim.** The repo's canonical BloodHound-compatible `CanRDP` edge requires all of:

```text
effective_member(principal, Host\\Remote Desktop Users)
AND effective_right(principal, host, SeRemoteInteractiveLogonRight)
AND NOT effective_right(principal, host, SeDenyRemoteInteractiveLogonRight)
```

Nested security-group membership participates in effective membership/right evaluation.
Any unknown required dimension prevents a positive traversable edge.
An explicit effective deny overrides allow.

- **Layer:** derived structural
- **Authoritative sources:**
  - SpecterOps `CanRDP`: https://bloodhound.specterops.io/resources/edges/can-rdp
  - Microsoft Allow RDS logon right (`SeRemoteInteractiveLogonRight`): https://learn.microsoft.com/en-us/windows/device-security/security-policy-settings/allow-log-on-through-remote-desktop-services
  - Microsoft Deny RDS logon right (`SeDenyRemoteInteractiveLogonRight`): https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/security-policy-settings/deny-log-on-through-remote-desktop-services
  - Microsoft User Rights Assignment: https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/dn221963(v=ws.11)
- **Applicable population/schema:** Windows hosts represented by SEAMLESS v3 or historical A/B host-local-group/UserRights primitives. The exact raw field differs by collector; the effective Windows authorization rule does not.
- **Confidence:** High.
- **Direct consequence for #44/#45:** #45's current `membership OR allow-right` wording MUST be replaced by the composite rule above. The adapter must resolve nested membership and deny precedence with provenance.
- **Regression counterexample:** A is in Remote Desktop Users and has the allow right, but A is also transitively in a group granted `SeDenyRemoteInteractiveLogonRight`; no `CanRDP` edge is emitted.

Windows also permits RDP authorization through local Administrators when the effective allow right exists.
This does not justify synthesizing the repo's canonical `CanRDP` edge from `AdminTo`; `AdminTo` remains the structural admin relationship and RDP may be selected later as an Attack Semantics technique/channel.

### C3. `AdminTo` requires host-bound effective local-administrator evidence

**Claim.** `AdminTo(principal, host)` means the principal is an effective local administrator on that host.
The relationship requires positive host-bound evidence: direct local Administrators membership, a retained nested membership derivation to `S-1-5-32-544`, or fully resolved resultant policy producing that state.
A domain group RID such as `-512` alone does not establish local administration on an arbitrary host.

- **Layer:** structural / derived structural
- **Authoritative source:** SpecterOps `AdminTo`: https://bloodhound.specterops.io/resources/edges/admin-to
- **Applicable population/schema:** SEAMLESS `LocalAdmins[]`; historical A/B `LocalGroups[]` Administrators (`S-1-5-32-544`); equivalent positive host-bound primitives.
- **Confidence:** High.
- **Direct consequence for #44/#45:** #45 MUST infer from host-bound local-admin state, not from globally recognized privileged group names/RIDs. Network channels are not edge-creation requirements.
- **Regression counterexample:** `<DOMAIN-SID>-512` exists and is high value, but no target-host evidence assigns it to Host X's local Administrators group; do not emit `AdminTo(Domain Admins, X)`.

### C4. `CanPSRemote` distinguishes BloodHound modeling from full Windows endpoint authorization

**Claim.** Effective host-bound membership in Remote Management Users (`S-1-5-32-580`) is valid BloodHound-compatible `CanPSRemote` structural evidence.
Actual Windows PowerShell remoting authorization can be further constrained by endpoint/session-configuration security descriptors.
WinRM listener/service/network availability is runtime, not structural edge existence.

- **Layer:** structural / derived structural + runtime
- **Authoritative sources:**
  - SpecterOps `CanPSRemote`: https://bloodhound.specterops.io/resources/edges/can-ps-remote
  - Microsoft PowerShell session configuration / remoting security documentation: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_session_configuration_files
  - Microsoft `Enable-PSRemoting`: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/enable-psremoting
- **Applicable population/schema:** SEAMLESS `PSRemoteUsers[]`; historical A/B local group `S-1-5-32-580`; explicit endpoint ACL evidence when available.
- **Confidence:** High for the BloodHound/runtime split; Medium-High for claims of independently verified endpoint access when endpoint ACLs were not collected.
- **Direct consequence for #44/#45:** #45 may emit BloodHound-modeled `CanPSRemote` from positive effective RMU membership, but MUST NOT require WinRM availability to preserve the edge and MUST NOT label the edge as independently verified custom-endpoint authorization without endpoint ACL evidence.
- **Regression counterexample:** A is in Remote Management Users, but a custom PowerShell endpoint security descriptor excludes that group. Preserve the modeled authorization evidence but do not claim verified endpoint execution from RMU membership alone.

### C5. Network and service availability are runtime predicates

**Claim.** `Connectable`, RDP service/port state, WinRM listener/service/firewall state, NLA compatibility, management-channel reachability, and authentication acceptance determine whether a technique can be exercised now.
They do not erase positive authorization topology.

- **Layer:** runtime
- **Authoritative sources:**
  - Microsoft Remote Desktop access prerequisites: https://learn.microsoft.com/en-us/windows-server/remote/remote-desktop-services/remotepc/remote-desktop-allow-access
  - Microsoft `Enable-PSRemoting`: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/enable-psremoting
  - SpecterOps `AdminTo`, `CanRDP`, `CanPSRemote` abuse sections.
- **Applicable population/schema:** all collectors/snapshots.
- **Confidence:** High.
- **Direct consequence for #44/#45:** do not gate edge materialization on ports/services/`Connectable`. Feed these facts into `admin_channel`, `rdp_available`, `winrm_available`, `authentication_accepted`, or other explicit runtime predicates.
- **Regression counterexample:** positive local-admin membership was collected, but `Connectable=false` at a later observation; `AdminTo` remains structural while a remote-admin transition may be blocked.

### C6. Missing collection is `unknown`, not false

**Claim.** `StatusAccessDenied`, method-not-run, a schema field that is absent without completeness evidence, unresolved identifiers, or otherwise incomplete collection cannot prove absence.
Only successful complete collection for the exact primitive can support a known negative.
Positive evidence remains valid even when other primitives are incomplete.

- **Layer:** assessment/unknown
- **Authoritative sources:**
  - SpecterOps data-quality/completeness model: https://bloodhound.specterops.io/reference/data-quality/get-database-completeness-stats
  - Repo snapshot manifest explicitly does not prove collection completeness.
- **Applicable population/schema:** all schemas; particularly endpoint RPC/SAM/LSA and session collection.
- **Confidence:** High.
- **Direct consequence for #44/#45:** introduce tri-state primitive handling (`positive`, `negative-known`, `unknown`). A composite edge is emitted only when all mandatory positive/negative dimensions are known sufficiently.
- **Regression counterexample:** RDU membership is present but UserRights collection returned `StatusAccessDenied`; `CanRDP` is `unknown`, not `true` and not `false`.

### C7. GPO-derived host access uses a hybrid promotion rule

**Claim.** A GPO setting or link is not by itself a traversable host-access edge.
A fully resolved resultant/effective host state may be promoted to positive **derived structural** evidence when the derivation proves the setting applies after scope, filtering, inheritance, ordering and relevant client-side extension semantics.
Partial/static/simulated applicability remains `inferred` or `unknown` assessment.

- **Layer:** derived structural OR assessment/unknown depending on evidence completeness
- **Authoritative sources:**
  - Microsoft Group Policy processing: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing
  - Microsoft Group Policy Modeling/Results: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-modeling-results
- **Applicable population/schema:** any dataset exposing GPO and target-scope primitives; not specific to SEAMLESS/A/B.
- **Confidence:** High for the classification rule; Medium-High for any custom resolver claiming equivalence to actual resultant policy across all CSEs.
- **Direct consequence for #44/#45:** replace blanket `inferred:scoped_gpo` treatment. Traversable derived edges require a positive provenance chain; incomplete policy applicability stays in `assessments`.
- **Regression counterexample:** a Restricted Groups GPO is linked to the target OU, but a security/WMI filter excludes Host X; do not emit host-access edges for X.

Minimum positive derivation lineage:

```text
GPO setting
-> active link
-> target scope
-> security filtering
-> WMI filtering (if configured)
-> inheritance / Enforced / Block Inheritance / link order
-> relevant client-side extension semantics
-> resultant host-local group or user-right state
-> derived host-access edge
```

### C8. Raw collector arrays are evidence primitives, not universal Windows truth

**Claim.** SEAMLESS v3 specialized arrays and historical SharpHound/BloodHound.py representations are schema-specific primitives.
They must be normalized by semantic meaning before producing canonical relationships.
In particular, `RemoteDesktopUsers[]` is membership evidence and MUST NOT be labeled a verified `CanRDP` relationship without the user-right/deny dimensions.

- **Layer:** structural primitive / assessment depending on completeness
- **Authoritative source:** SpecterOps `CanRDP` plus repo raw-schema inventory.
- **Applicable population/schema:** SEAMLESS BloodHound v3 and A/B historical exports.
- **Confidence:** High for the identified direct-mapping defect; Medium for any unverified raw field not present in committed operational archives.
- **Direct consequence for #44/#45:** adapters must expose primitives with collection status. EDA may report raw membership counts, but verified access counts must use the composite rule.
- **Regression counterexample:** `RemoteDesktopUsers=[A]`, with no UserRights evidence. Report one RDU membership primitive and `CanRDP=unknown`; do not report one verified `CanRDP`.

### C9. `HasSession` is an observed session relationship, not credential dumping

**Claim.** `HasSession(host,user)` means a qualifying user session was observed on the host at collection time.
Credential availability, LSASS/token access, administrator foothold, protection mechanisms, and freshness at exploitation time are technique/runtime semantics.

- **Layer:** structural observation + runtime exploitation conditions
- **Authoritative source:** SpecterOps `HasSession`: https://bloodhound.specterops.io/resources/edges/has-session
- **Applicable population/schema:** SEAMLESS `Sessions[]`; historical A/B `Sessions`, `PrivilegedSessions`, `RegistrySessions` where those primitives are present.
- **Confidence:** High.
- **Direct consequence for #44/#45:** #44 keeps direction `Computer -> User`, timestamps and source kind; remove wording that equates the edge itself with successful credential extraction.
- **Regression counterexample:** a user session is observed but Credential Guard prevents credential recovery. `HasSession` remains; the credential-recovery transition is blocked.

## 4. `CanRDP` decision table

| Effective RDU membership | Allow right | Deny right | Completeness | Canonical result |
| --- | --- | --- | --- | --- |
| yes | yes | no | complete | positive `CanRDP` edge |
| yes | yes | yes | complete | known denied; no edge |
| yes | no | no | complete | known insufficient; no edge |
| no | yes | no | complete | no canonical `CanRDP` edge; other structural relationships such as `AdminTo` may still exist |
| no | no | no | complete | no edge |
| yes | unknown | unknown | incomplete | `unknown`; no traversable edge |
| unknown | yes | no | incomplete | `unknown`; no traversable edge |
| any | any | unknown | deny collection incomplete | `unknown`; no traversable edge |
| unknown | unknown | unknown | access denied/not run | `unknown`; no traversable edge |

## 5. Schema mapping: SEAMLESS versus historical A/B

The repo's committed raw operational archives are intentionally absent.
Therefore this mapping distinguishes **repo-established snapshot facts** from universal Windows semantics.
Dataset files establish what a snapshot contains; they do not define Windows authorization behavior.

| Primitive / relation | SEAMLESS BloodHound v3-style | Historical A/B SharpHound / BloodHound.py | Normalized meaning |
| --- | --- | --- | --- |
| `LocalAdmins` | flat `Computer.LocalAdmins[]` consumed by current EDA | historical collectors may expose flat local-admin arrays in addition to local-group structures | positive host-local Administrators membership primitive when collected |
| `RemoteDesktopUsers` | flat `Computer.RemoteDesktopUsers[]` | historical SharpHound represents local group `S-1-5-32-555` through `LocalGroups[]` | RDU membership primitive only; not verified `CanRDP` alone |
| `PSRemoteUsers` | flat `Computer.PSRemoteUsers[]` | historical SharpHound represents `S-1-5-32-580` through `LocalGroups[]` | BloodHound-compatible Remote Management Users membership primitive |
| `LocalGroups` | do not assume A/B-shaped coverage merely because a similarly named concept exists | core historical host-local-group representation including `-544`, `-555`, `-580` plus result/status metadata where collected | adapter primitive; resolve full SID, host scope, nesting and status |
| `UserRights` | current SEAMLESS EDA does not establish sufficient UserRights coverage for verified RDP authorization | A/B inventory reports UserRights and collection failures such as `StatusAccessDenied` | mandatory input to effective `CanRDP`; missing/inaccessible => unknown |
| `Sessions` | `Computer.Sessions[]`; SEAMLESS report currently has no observed sessions | available in historical collectors depending on method | time-stamped `HasSession` evidence |
| `PrivilegedSessions` | not normalized by current v3 EDA | present in some historical SharpHound shapes | session-evidence subtype; retain source/provenance |
| `RegistrySessions` | not normalized by current v3 EDA | present in some historical SharpHound shapes | session-evidence subtype; retain source/provenance and completeness separately |
| collection status | v3 static snapshot may lack enough error/completeness metadata to interpret empty arrays as known negatives | A/B can expose richer per-primitive status/failure details | missing/not-run/access-denied => unknown; `success + empty` may be negative for that exact primitive |

## 6. Required repo changes

### Remove/change

1. Remove the test/invariant `disabled account => terminal structural node`.
2. Remove any future #44/#45 pruning based only on `enabled == false`.
3. Replace #45 `RDU membership OR allow-right` with the `CanRDP` composite AND + deny-precedence rule.
4. Stop treating SEAMLESS `RemoteDesktopUsers[]` counts as verified `CanRDP` counts.
5. Keep network/service/`Connectable` conditions out of structural edge existence.
6. Map `StatusAccessDenied`, missing required fields and incomplete collection to `unknown`.
7. Replace blanket GPO `inferred` handling with the hybrid promotion rule.
8. Define `HasSession` as a time-stamped observation, not a credential-dumping guarantee.
9. Preserve session source kind (`Sessions`, `PrivilegedSessions`, `RegistrySessions`) and collection time/provenance.
10. Do not call RMU membership independently verified custom PowerShell endpoint access without endpoint ACL evidence.

### Keep

1. Full well-known SID matching (`S-1-5-32-544`, `-555`, `-580`).
2. RID `-512` alone does not create `AdminTo`.
3. `Connectable=false` never vetoes already collected positive authorization evidence.
4. Direct `MemberOf` remains canonical; transitive/effective membership is resolved for query/inference with the derivation chain retained.
5. Traversable derived edges require positive provenance; unresolved/inferred/unknown assessments remain non-traversable.

## 7. Consequence for #44

#44 may proceed under these invariants:

- node `enabled` is preserved as state but does not prune direct structural relationships;
- `HasSession` is `Computer -> User` session observation with timestamp/source provenance;
- direct relationships are built from positive evidence regardless of whether a later Attack Semantics transition can currently use them;
- no runtime transport/service predicates belong in direct graph assembly.

## 8. Consequence for #45

#45 implementation is blocked on the old wording and MUST use this audit instead:

- tri-state primitive evaluation;
- host-bound evidence;
- full SID matching;
- nested/effective membership resolution with provenance;
- `CanRDP = RDU membership AND allow AND NOT deny`;
- positive `AdminTo` from effective local Administrators state;
- BloodHound-modeled `CanPSRemote` from effective Remote Management Users state while endpoint ACL limitations remain explicit;
- runtime network/service state outside edge existence;
- hybrid GPO promotion only when resultant/effective host state is proven.

## 9. Regression counterexample matrix

| Case | Expected result |
| --- | --- |
| disabled user has positive `GenericAll` | edge preserved; runtime transition may be blocked |
| disabled user is direct member of security group | `MemberOf` preserved |
| RDU member + allow + no deny | positive `CanRDP` |
| RDU member + allow + effective deny | no `CanRDP` |
| RDU member + missing UserRights | `unknown`; no traversable edge |
| allow-right only, no RDU membership | no canonical `CanRDP` |
| nested group reaches RDU + allow + no deny | positive derived `CanRDP` with membership chain provenance |
| local admin evidence + `Connectable=false` | `AdminTo` preserved; runtime channel may be unavailable |
| `StatusAccessDenied` for local group/UserRights | `unknown`, not false |
| empty result after explicitly successful complete primitive collection | known negative for that primitive |
| GPO linked but WMI/security filter excludes host | assessment/no edge |
| fully resolved resultant GPO creates local admin/RDU/right state | positive derived structural evidence |
| observed session + Credential Guard | `HasSession` preserved; credential-recovery runtime transition blocked |
| RMU membership + WinRM stopped | `CanPSRemote` structural evidence preserved; runtime `winrm_available=false` |

## 10. Final decision table

| Topic | Final invariant | Layer | Confidence | #44/#45 action |
| --- | --- | --- | --- | --- |
| disabled account | preserve source-backed relationships; evaluate usability per technique | structural + runtime | High | remove pruning |
| `AdminTo` | positive effective local Administrators state bound to target host | structural / derived structural | High | host evidence resolver |
| `CanRDP` | effective RDU membership AND allow AND NOT deny; unknown required input => unknown | derived structural | High | rewrite #45 + regression matrix |
| `CanPSRemote` | effective RMU membership is BloodHound-compatible structural evidence; endpoint ACL may further restrict actual Windows endpoint access | structural / derived structural | High / Medium-High | separate authorization evidence from WinRM runtime |
| network/service availability | operational condition for exercising an edge | runtime | High | Attack Semantics only |
| `Connectable` | collection/runtime context, never global structural veto | runtime/collection metadata | High | keep non-veto rule |
| access denied/missing field | cannot prove absence | assessment/unknown | High | tri-state handling |
| scoped GPO | only proven resultant/effective state becomes positive derived structural evidence | derived structural or assessment | High | hybrid resolver |
| nested membership | resolve effective membership for inference while retaining direct chain | derived structural | High | preserve provenance |
| v3 `RemoteDesktopUsers` | membership primitive, not verified `CanRDP` | schema primitive | High | rename/reclassify EDA metric |
| `HasSession` | observed `Computer -> User` session at collection time | structural | High | remove credential-dump claim |

## 11. Verification expectation

Truth-migration changes are complete when:

1. no test requires disabled nodes to be structural terminals;
2. a regression graph with a disabled source and a positive outgoing edge validates successfully;
3. #44 and #45 bodies reference this audit/ADR-0003 amendment;
4. EDA/reporting distinguishes raw RDU membership from verified `CanRDP`;
5. future #45 tests implement the `CanRDP` truth table, tri-state collection, nested membership, GPO promotion and runtime/service separation.
