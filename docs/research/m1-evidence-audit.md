# Milestone 1 Evidence Audit: Comprehensive Six-Layer Audit of Eight Relationship Types

References: Refs #79; follows ADR-0007, ADR-0008, ADR-0009, PR #89, and issue #80 / PR #90.
Status: Normative evidence audit for Milestone 1 relationships (Phase A Deliverable, Revised).
Maintainers: @Lolavine777 (Author), @nairyuuu (Reviewer).

---

## 1. Context, Scope, and Objectives

This audit establishes the defensible evidence baseline for all eight Active Directory attack graph relationships within Milestone 1 scope: `MemberOf`, `AdminTo`, `GenericAll`, `WriteDacl`, `ForceChangePassword`, `CanPSRemote`, `CanRDP`, and `HasSession`.
Earlier repository artifacts in `docs/research/taxonomy.md`, `docs/research/data-quality-report.md`, and `scripts/eda_dataset_analysis.py` mixed static structural topology, runtime attack techniques, environmental execution prerequisites, and telemetry observations into unified descriptions.
Furthermore, legacy experimental Multi-Attribute Utility Theory (`maut_v1`) values were presented alongside structural rules as if they were normative edge properties, and group membership modification events (4728/4729) were erroneously attributed to passive membership traversal.

Per Issue #79, maintainer guidance, and PR #90's accepted decisions, this audit records Phase A (Audit and Research).
Phase A formalizes the evidence boundaries across six distinct layers without modifying production runtime code or rewriting architectural history.
Phase B1/Phase B2 dispositions and current implementation evidence are recorded in Section 9 below.

---

## 2. The Six Evidence Layers and Categorization Standard

To eliminate conceptual conflation, every claim is classified into exactly one of six architectural layers:

1. **`structural_evidence`**:
   Static Active Directory object attributes, DACL/ACE entries, or host-bound local group memberships extracted from immutable snapshot bytes.
   Governed by Graph Contract 1.0.0 (`configs/contract.yml`).
2. **`state_transition`**:
   The formal capability transition by which an attacker controlling a principal leverages an authorization relationship to change security state.
   Modeled independently in `configs/attack_semantics.yml`.
3. **`runtime_predicate`**:
   Dynamic host, network, service, or account availability conditions required for a technique to be exercised at runtime (such as port reachability, service running state, or account enablement).
   A failed predicate blocks immediate execution but does not prune positive structural authorization.
4. **`expected_telemetry`**:
   Auditing event IDs and provider records documented by authoritative vendor specifications (Microsoft Windows Security Auditing, MITRE ATT&CK, SpecterOps) as expected signals when a specific technique is executed under active auditing.
   Expected telemetry belongs to concrete semantic transitions in `configs/attack_semantics.yml`, while relation-level groupings remain descriptive candidate inventory.
5. **`observed_telemetry`**:
   Actual empirical signals measured in the verified local candidate telemetry corpus (`data/raw/telemetry/evtx_data.csv`, 4,633 analyzed rows).
   Independent telemetry is never joined to SEAMLESS topology as entity-level proof of execution.
   Claims are strictly bounded to reproducible parser extractions.
6. **`weighting_status`**:
   The operational cost, effort, or traversal weight associated with traversing a relationship or executing a transition.
   All legacy MAUT v1 values are documented as historical/experimental; cost ownership decisions are explicitly governed by Issue #42.

### Evidence Categorization Standard

Each claim is assigned an explicit evidence category:
- `authoritative_specification`: Primary vendor documentation (Microsoft Open Specifications, MITRE ATT&CK, SpecterOps BloodHound).
- `measured_corpus_signal`: Quantitatively verified observations in local immutable datasets.
- `runtime_catalog_invariant`: Accepted domain constraints enforced by `src.engine.semantics`.
- `historical_assumption`: Legacy rationale or transitional rules slated for realignment.
- `illustrative_hypothesis`: Explanatory examples or heuristic scoring not grounded in empirical calibration.

---

## 3. Comprehensive Eight-Relationship Evidence Matrix

| Relationship | Claim | Layer | Exact Source / Reference | Source Version / Access Date | Population / Environment | Evidence Category | Confidence Rationale | Consumers | Disposition | Corrective Action (Phase B) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MemberOf` | Direct group membership is evidenced by LDAP `member` attribute on Group or `primaryGroupID` on User. | `structural_evidence` | [MS-ADA2: 2.43 Attribute member](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-ada2/763d0861-f4f6-4251-847e-7e8dedcfe73f), [MS-ADA3: 2.120 Attribute primaryGroupID](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-ada3/e12954a4-6865-4432-94e6-00c310ca87c0) | 2026-09-22 | SEAMLESS v3, A/B | `authoritative_specification` | High: Core Active Directory directory schema attributes defining static group membership. | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Retain as primary structural edge primitive under ADR-0009. |
| `MemberOf` | Disabled accounts must be pruned from structural graph with `out_degree == 0`. | `structural_evidence` | Historical M1 test suite | 2026-09-14 | Repository synthetic tests | `historical_assumption` | Unsupported: Disabled status does not alter object security descriptors or group membership in AD database (#80 C1). | `tests/test_parser.py`, `docs/research/taxonomy.md` | `stale_unsupported` | Realigned via #80 / PR #90; preserve structural edges regardless of `enabled` flag. |
| `MemberOf` | MemberOf enables entitlement inheritance (`propagate_group_entitlement`) without requiring an active attacker action (`action_required: false`). | `state_transition` | `configs/attack_semantics.yml` | v0.1 | Universal AD | `runtime_catalog_invariant` | High: Token groups are evaluated transitively by Windows LSA during authentication. | `src/engine/semantics`, `docs/research/attack-semantics.md` | `supported_normative` | Reaffirm as zero-action entitlement propagation in taxonomy. |
| `MemberOf` | Traversal requires active account state (`actor_enabled`) and security-enabled group type. | `runtime_predicate` | `configs/attack_semantics.yml` | v0.1 | Universal AD | `runtime_catalog_invariant` | High: LSA rejects logon for disabled accounts; distribution groups do not grant security tokens. | `src/engine/semantics` | `reclassified_runtime` | Move account enablement check from structural graph builder to runtime semantics engine. |
| `MemberOf` | Passive traversal along an existing MemberOf edge generates Event 4728 / 4729. | `expected_telemetry` | `scripts/eda_dataset_analysis.py::m1_edge_telemetry` | 2026-09-20 | Upstream project notes | `historical_assumption` | Unsupported: Event 4728/4729 represent active group modification, not passive token traversal. | `reports/eda_summary.json`, `docs/research/data-quality-report.md` | `stale_unsupported` | Remove 4728/4729 from MemberOf in EDA telemetry matrix; set expected telemetry in catalog to empty array `[]`. |
| `MemberOf` | Events 4728 and 4729 have zero matching EventID rows in the verified candidate telemetry corpus; passive traversal is not measured by these IDs. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv`, `reports/eda_summary.json` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | High for the scoped EventID count only: zero matching rows among 4,633; this does not establish absence of group modification or passive traversal in an environment. | `reports/eda_summary.json` | `supported_descriptive` | Report only corpus frequency; maintain zero expected telemetry for passive MemberOf; attach qualified group-modification signals to the relevant catalog transition. |
| `MemberOf` | MemberOf traversal cost is fixed at $W=1.000$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Arbitrary utility score without empirical basis. | `docs/research/taxonomy.md`, ADR-0001 | `pending_issue_42` | Mark legacy MAUT v1 score as historical; defer cost model to Issue #42 successor ADR. |
| `AdminTo` | AdminTo is evidenced by host-bound local Administrators group (`S-1-5-32-544`) or proven resultant GPO. | `structural_evidence` | [SpecterOps AdminTo](https://bloodhound.specterops.io/resources/edges/admin-to), [MS-SAMR: 3.1.5.8.1 Local Groups](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/012643a6-b51f-4ef6-829e-26f6ebf96fb2) | 2026-09-22 | SEAMLESS `LocalAdmins[]`, A/B `S-1-5-32-544` | `authoritative_specification` | High: Host-bound local administrative rights are authoritative on Windows hosts (#80 C3). | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Enforce host-bound evidence rule; reject RID 512 global inference without host evidence. |
| `AdminTo` | AdminTo represents obtaining remote administrative execution (`obtain_admin_execution_on_host`). | `state_transition` | `configs/attack_semantics.yml` | v0.1 | Windows Server / Desktop | `runtime_catalog_invariant` | High: Administrative access establishes `admin_control` on host. | `src/engine/semantics` | `supported_normative` | Maintain technique mapping in Attack Semantics catalog. |
| `AdminTo` | Structural edge creation requires TCP port 445/135 open and LanmanServer active. | `runtime_predicate` | `docs/research/taxonomy.md` line 73 | 2026-09-14 | Network environment | `historical_assumption` | Unsupported: Network port reachability is a runtime predicate, not a structural permission prerequisite (#80 C5). | `docs/research/taxonomy.md` | `reclassified_runtime` | Remove port/service availability from structural taxonomy; retain under `admin_channel` predicate. |
| `AdminTo` | Candidate descriptive signals include Security Events 4672 (Special Privileges) and 4624 (Logon). | `expected_telemetry` | [Microsoft Event 4672](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4672), [Microsoft Event 4624](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4624) | 2026-09-22 | Windows OS | `authoritative_specification` | High: Documented Windows auditing behavior upon elevated token creation. | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `supported_descriptive` | Retain as descriptive candidate inventory in EDA; catalog retains transition-attached `event_id: null` (channel dependent). |
| `AdminTo` | Events 4672 and 4624 in candidate telemetry confirm AdminTo execution on SEAMLESS hosts. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | Unsupported: Events 4672 and 4624 are present in corpus, but host-level session correlation and attribution are not extracted by current parser. | `docs/research/data-quality-report.md` | `separated_from_structural` | Remove wording claiming telemetry proves activity on synthetic SEAMLESS hosts. |
| `AdminTo` | AdminTo cost is fixed at $W=1.650$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Historical heuristic weighting. | `docs/research/taxonomy.md` | `pending_issue_42` | Label as historical illustrative cost; await Issue #42 cost ownership decision. |
| `GenericAll` | GenericAll is evidenced by an object DACL ACE granting `GENERIC_ALL` (bit `0x10000000`), expanding to object FullControl (`0xF01FF`). | `structural_evidence` | [MS-DTYP: 2.4.3 Access Mask](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/7a53f60e-e730-4dfe-aab9-e2404e7f979f), [MS-ADTS: 5.1.3.2.1 Generic Mapping](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6f654b03-5e92-4f10-911e-2ce01c69c656) | 2026-09-22 | SEAMLESS, A/B | `authoritative_specification` | High: Microsoft access mask specification defines GENERIC_ALL as 0x10000000; Active Directory GENERIC_MAPPING maps this to standard and specific rights (0xF01FF). | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Maintain standard ACE access mask validation; do not cite 0xF01FF as the GENERIC_ALL bit. |
| `GenericAll` | GenericAll represents a single unified attack step with fixed outcome. | `state_transition` | `docs/research/taxonomy.md` line 31 | 2026-09-14 | Analytical model | `historical_assumption` | Unsupported: GenericAll supports multiple distinct techniques: reset password, add member, grant DACL. | `docs/research/taxonomy.md` | `stale_unsupported` | Replace single-action taxonomy description with 3 explicit catalog transitions (#58 / #63). |
| `GenericAll` | Preconditions require directory write permissions and target enablement for authentication control. | `runtime_predicate` | `configs/attack_semantics.yml` | v0.1 | Active Directory DS | `runtime_catalog_invariant` | High: Read-only DC replica blocks writes; disabled target prevents immediate password-based logon. | `src/engine/semantics` | `supported_normative` | Maintain `directory_write_allowed` and `target_enabled` predicates. |
| `GenericAll` | Candidate descriptive signals include Event 5136 (DS Changes), Event 4662 (Operation on Object), and Event 4724 (Password Reset). | `expected_telemetry` | [Microsoft Event 5136](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-5136), [Microsoft Event 4662](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4662), [Microsoft Event 4724](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4724) | 2026-09-22 | Windows Server DC | `authoritative_specification` | High: Generated when DS audit policy and matching SACL exist on object. | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `supported_descriptive` | Retain as descriptive candidate inventory; normative telemetry is transition-attached in catalog (4724, 5136, 4728/4732/4756). |
| `GenericAll` | Event 5136 is present in verified corpus; attribute overwrite qualification is not established. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | Medium: Event 5136 is present in verified rows; target attribute and technique attribution are not extracted by current parser. | `reports/eda_summary.json` | `supported_descriptive` | Report Event 5136 corpus presence as descriptive inventory without technique attribution. |
| `GenericAll` | GenericAll cost is fixed at $W=1.850$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Historical heuristic weighting. | `docs/research/taxonomy.md` | `pending_issue_42` | Label as historical illustrative cost; await Issue #42 cost ownership decision. |
| `WriteDacl` | WriteDacl is evidenced by DACL ACE containing `WRITE_DACL` permission (`0x40000`). | `structural_evidence` | [MS-DTYP: 2.4.3 Access Mask](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/7a53f60e-e730-4dfe-aab9-e2404e7f979f), [MS-ADTS: 5.1.3.2](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6f654b03-5e92-4f10-911e-2ce01c69c656) | 2026-09-22 | SEAMLESS, A/B | `authoritative_specification` | High: Active Directory access control specification. | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Maintain standard DACL parsing in parser. |
| `WriteDacl` | WriteDacl represents mutating the security descriptor to grant attacker `GenericAll` (`grant_new_object_right`). | `state_transition` | `configs/attack_semantics.yml` | v0.1 | Active Directory DS | `runtime_catalog_invariant` | High: Discretionary ACL modification enables granting arbitrary rights. | `src/engine/semantics` | `supported_normative` | Formalize as `graph_mutation` transition in catalog. |
| `WriteDacl` | Target protection by AdminSDHolder / SDProp acts as an impact and persistence resistance condition rather than an execution blocker. | `runtime_predicate` | [MS-ADTS: 7.1.1.2.4 AdminSDHolder](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/4934d402-601e-4530-ab01-7299f43054a1) | 2026-09-22 | Active Directory Domain | `authoritative_specification` | High: SDProp executes periodically; it does not prevent DACL write operations at invocation time, but bounds their temporal persistence. | `docs/research/taxonomy.md` | `supported_normative` | Document AdminSDHolder/SDProp as a temporal persistence resistance condition; do not treat as an execution prerequisite. |
| `WriteDacl` | Candidate descriptive signals include Event 5136 on attribute `nTSecurityDescriptor` and Event 4662. | `expected_telemetry` | [Microsoft Event 5136](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-5136), [Microsoft Event 4662](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4662) | 2026-09-22 | Windows Server DC | `authoritative_specification` | High: Audited under DS Access when SACL permits. | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `supported_descriptive` | Retain as descriptive candidate inventory; catalog attaches Event 5136 directly to `grant_new_object_right`. |
| `WriteDacl` | Event 5136 is present in verified corpus; nTSecurityDescriptor attribute modification qualification is not established. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | Medium: Event 5136 is present in verified rows; nTSecurityDescriptor modification attribution is not extracted by current parser. | `reports/eda_summary.json` | `supported_descriptive` | Report Event 5136 corpus presence as descriptive inventory without technique attribution. |
| `WriteDacl` | WriteDacl cost is fixed at $W=2.250$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Historical heuristic weighting. | `docs/research/taxonomy.md` | `pending_issue_42` | Label as historical illustrative cost; await Issue #42 cost ownership decision. |
| `ForceChangePassword` | ForceChangePassword is evidenced by Extended Right `User-Force-Change-Password` (`00299570-246d-11d0-a768-00aa006e0529`). | `structural_evidence` | [MS-ADTS: Extended Rights](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/9e24696a-04a4-4f05-89f4-18c7e0c40632) | 2026-09-22 | SEAMLESS, A/B | `authoritative_specification` | High: Documented Active Directory extended right GUID. | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Enforce explicit GUID matching in parser. |
| `ForceChangePassword` | Transition resets target user password without requiring knowledge of old password (`reset_target_password`). | `state_transition` | `configs/attack_semantics.yml` | v0.1 | Active Directory User | `runtime_catalog_invariant` | High: Standard Windows password reset semantics. | `src/engine/semantics` | `supported_normative` | Maintain technique mapping in catalog. |
| `ForceChangePassword` | Target account must be enabled and new password must satisfy domain password policy. | `runtime_predicate` | `configs/attack_semantics.yml` | v0.1 | Active Directory Domain | `runtime_catalog_invariant` | High: Password filter DLLs reject non-compliant passwords; reset on disabled account yields no logon. | `src/engine/semantics` | `supported_normative` | Maintain `password_policy_accepts` and `target_enabled` predicates. |
| `ForceChangePassword` | Candidate descriptive signals include Event 4724 (Password Reset Attempt) and Event 4738 (Account Modified). | `expected_telemetry` | [Microsoft Event 4724](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4724), [Microsoft Event 4738](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4738) | 2026-09-22 | Windows Server DC | `authoritative_specification` | High: Logged on DC handling the reset request. | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `supported_descriptive` | Retain as descriptive candidate inventory; catalog attaches Event 4724 directly to `reset_target_password`. |
| `ForceChangePassword` | Event 4724 is present in verified corpus; password reset technique attribution is not established. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | Medium: Event 4724 is present in verified rows; target account and password reset attribution are not extracted by current parser. | `reports/eda_summary.json` | `supported_descriptive` | Report Event 4724 corpus presence as descriptive inventory without technique attribution. |
| `ForceChangePassword` | ForceChangePassword cost is fixed at $W=2.250$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Historical heuristic weighting. | `docs/research/taxonomy.md` | `pending_issue_42` | Label as historical illustrative cost; await Issue #42 cost ownership decision. |
| `CanPSRemote` | CanPSRemote is evidenced by host-bound membership in Remote Management Users (`S-1-5-32-580`) or scoped resultant policy. | `structural_evidence` | [SpecterOps CanPSRemote](https://bloodhound.specterops.io/resources/edges/can-ps-remote), [MS-SAMR: 3.1.5.8.1 Local Groups](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/012643a6-b51f-4ef6-829e-26f6ebf96fb2) | 2026-09-22 | SEAMLESS `PSRemoteUsers[]`, A/B `S-1-5-32-580` | `authoritative_specification` | High: BloodHound-compatible modeled authorization primitive (#80 C4). | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Maintain RMU membership evidence; document that custom endpoint ACLs may further restrict access. |
| `CanPSRemote` | CanPSRemote represents remote PowerShell execution via WinRM (`open_winrm_remote_session`, MITRE T1021.006). | `state_transition` | `configs/attack_semantics.yml` | v0.1 | Windows Host | `runtime_catalog_invariant` | High: Standard WinRM / PowerShell remoting abuse pattern. | `src/engine/semantics` | `supported_normative` | Maintain technique mapping in catalog. |
| `CanPSRemote` | Structural edge requires TCP port 5985/5986 open and WinRM service running. | `runtime_predicate` | `docs/research/taxonomy.md` line 73 | 2026-09-14 | Network environment | `historical_assumption` | Unsupported: Service listener and port reachability are runtime predicates, not structural authorization gates (#80 C5). | `docs/research/taxonomy.md` | `reclassified_runtime` | Move port/service checks to `winrm_available` runtime predicate. |
| `CanPSRemote` | Candidate descriptive signals include PowerShell Script Block Logging (Event 4104) and Security Event 4624 (LogonType 3). | `expected_telemetry` | [Microsoft PowerShell Logging](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_logging_windows), [Microsoft Tools and Logon Types](https://learn.microsoft.com/en-us/windows-server/identity/securing-privileged-access/reference-tools-logon-types), [Microsoft Event 4624](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4624) | 2026-09-22 | Windows OS | `authoritative_specification` | High: Microsoft Tools and Logon Types explicitly maps PowerShell WinRM to Network (LogonType 3), documented alongside PowerShell Script Block Logging (Event 4104). | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `supported_descriptive` | Retain as descriptive candidate inventory; catalog attaches `event_id: null` (configuration dependent) to `open_winrm_remote_session`. |
| `CanPSRemote` | Event 4104 is present in verified corpus; WinRM channel and script block execution attribution are not established. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | Medium: Event 4104 is present in verified rows; WinRM remoting channel details and script attribution are not extracted by current parser. | `reports/eda_summary.json` | `supported_descriptive` | Report Event 4104 corpus presence as descriptive inventory without technique attribution. |
| `CanPSRemote` | CanPSRemote cost is fixed at $W=2.250$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Historical heuristic weighting. | `docs/research/taxonomy.md` | `pending_issue_42` | Label as historical illustrative cost; await Issue #42 cost ownership decision. |
| `CanRDP` | Canonical CanRDP is a composite effective authorization: `effective_member(Host\Remote Desktop Users) AND effective_right(principal, host, SeRemoteInteractiveLogonRight) AND NOT effective_right(principal, host, SeDenyRemoteInteractiveLogonRight)`. | `structural_evidence` | [SpecterOps CanRDP](https://bloodhound.specterops.io/resources/edges/can-rdp), [Microsoft Allow RDS](https://learn.microsoft.com/en-us/windows/device-security/security-policy-settings/allow-log-on-through-remote-desktop-services), [Microsoft Account Rights Constants](https://learn.microsoft.com/en-us/windows/win32/secauthz/account-rights-constants) | 2026-09-22 | SEAMLESS, A/B | `authoritative_specification` | High: Required by Windows LSA interactive logon policy and SpecterOps modeling (#80 C2); Microsoft Account Rights Constants explicitly documents SeDenyRemoteInteractiveLogonRight and establishes that deny rights override allow rights. | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Enforce composite rule in parser #45; distinguish Windows OS Admin logon from repo canonical edge model. |
| `CanRDP` | Direct counting of SEAMLESS `RemoteDesktopUsers[]` constitutes verified `CanRDP` edge count. | `structural_evidence` | `scripts/eda_dataset_analysis.py` | 2026-09-20 | SEAMLESS v3 snapshot | `historical_assumption` | Unsupported: `RemoteDesktopUsers[]` is raw group membership, not verified composite authorization (#80). | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `stale_unsupported` | Remediated in the #80 EDA follow-up: report raw RDU membership separately; verified `CanRDP` remains unknown/unmeasurable without the complete allow/deny UserRights dimensions. |
| `CanRDP` | CanRDP represents opening a remote interactive desktop session (`open_remote_interactive_session`, MITRE T1021.001). | `state_transition` | `configs/attack_semantics.yml` | v0.1 | Windows Host | `runtime_catalog_invariant` | High: Standard GUI-based lateral movement channel. | `src/engine/semantics` | `supported_normative` | Maintain technique mapping in catalog. |
| `CanRDP` | Structural edge requires TCP port 3389 open and TermService active. | `runtime_predicate` | `docs/research/taxonomy.md` line 73 | 2026-09-14 | Network environment | `historical_assumption` | Unsupported: Listener reachability is a runtime predicate, not a structural permission gate (#80 C5). | `docs/research/taxonomy.md` | `reclassified_runtime` | Move port/service checks to `rdp_available` runtime predicate. |
| `CanRDP` | Candidate descriptive signals include Security Event 4624 with LogonType 10 (RemoteInteractive). | `expected_telemetry` | [Microsoft Event 4624](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4624) | 2026-09-22 | Windows OS | `authoritative_specification` | High: Authoritative Windows logon audit specification documents LogonType 10 (RemoteInteractive) for Terminal Services / Remote Desktop connections. | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `supported_descriptive` | Retain Event 4624 (LogonType 10) as descriptive candidate inventory in EDA and normative transition-attached telemetry in catalog; omit Event 1149 pending primary authoritative Microsoft specification. |
| `CanRDP` | Event 4624 is present in verified corpus; LogonType qualification (such as LogonType 10) is not established. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | Medium: Event 4624 is present in verified rows; LogonType qualification (such as LogonType 10) is not extracted or measured by the current EDA parser. | `reports/eda_summary.json` | `supported_descriptive` | Report Event 4624 corpus presence as descriptive inventory without asserting unmeasured LogonType 10 attribution. |
| `CanRDP` | CanRDP cost is fixed at $W=2.400$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Historical heuristic weighting. | `docs/research/taxonomy.md` | `pending_issue_42` | Label as historical illustrative cost; await Issue #42 cost ownership decision. |
| `HasSession` | HasSession is evidenced by host session enumeration primitives (`RegistrySessions[]`, `Sessions[]`) with directional semantics `Computer -> User`. | `structural_evidence` | [SpecterOps HasSession](https://bloodhound.specterops.io/resources/edges/has-session) | 2026-09-22 | SEAMLESS `Computer.Sessions[]` / computers export, A/B session primitives | `authoritative_specification` | High: Direction represents host possession of user session state (#80 C8). | `docs/research/taxonomy.md`, `src/parser/loader.py` | `supported_normative` | Enforce `Computer -> User` directionality; session is a time-scoped observation. |
| `HasSession` | HasSession edge existence is synonymous with guaranteed credential acquisition (LSASS dump). | `state_transition` | `docs/research/taxonomy.md` line 56 | 2026-09-14 | Analytical model | `historical_assumption` | Unsupported: Session presence is an opportunity; credential extraction requires separate technique execution (#80 C8). | `docs/research/taxonomy.md` | `stale_unsupported` | Reclassify as `credential_opportunity` in catalog; credential extraction is a candidate transition (`recover_session_credential_material`). |
| `HasSession` | Credential extraction requires local admin privilege, session freshness, and absence of Credential Guard / Protected Users. | `runtime_predicate` | `configs/attack_semantics.yml`, [Microsoft Credential Guard](https://learn.microsoft.com/en-us/windows/security/identity-protection/credential-guard/) | 2026-09-22 | Windows 10/11, Server 2016+ | `authoritative_specification` | High: VBS/LSAIso isolates NTLM hashes and TGT keys from LSASS process memory. | `src/engine/semantics` | `supported_normative` | Maintain `credential_accessible` and `session_fresh` runtime predicates. |
| `HasSession` | Candidate descriptive signals for credential access techniques include Sysmon Event 10 (ProcessAccess targeting `lsass.exe`) and Security Event 4624/4634 session boundaries. | `expected_telemetry` | [MITRE ATT&CK T1003.001](https://attack.mitre.org/techniques/T1003/001/), [Microsoft Sysmon (Event 10)](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon), [Microsoft Event 4624](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4624), [Microsoft Event 4634](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4634) | 2026-09-22 | Sysmon / Windows Security | `authoritative_specification` | High: MITRE ATT&CK T1003.001 identifies LSASS memory access as primary credential dumping technique, monitored via Sysmon Event 10 (ProcessAccess) and Security Event 4624/4634 logon session boundaries. | `scripts/eda_dataset_analysis.py`, `reports/eda_summary.json` | `supported_descriptive` | Retain as descriptive candidate inventory; catalog attaches `event_id: null` (technique/audit dependent) to `recover_session_credential_material`. |
| `HasSession` | Sysmon Event 10 is present in verified corpus; target process qualification (such as TargetImage=lsass.exe) is not established. | `observed_telemetry` | `data/raw/telemetry/evtx_data.csv` | 2021-06-09 | EVTX-ATTACK-SAMPLES | `measured_corpus_signal` | Medium: Sysmon Event 10 is present in verified rows; target process attribution (such as `TargetImage=lsass.exe`) is not extracted by the current EDA parser. | `reports/eda_summary.json` | `supported_descriptive` | Report Sysmon Event 10 corpus presence as descriptive inventory without asserting unmeasured process target attribution. |
| `HasSession` | HasSession cost is fixed at $W=3.550$ (`maut_v1`). | `weighting_status` | `docs/research/taxonomy.md`, ADR-0001 | 2026-09-14 | Theoretical rubric | `illustrative_hypothesis` | Low: Historical heuristic weighting. | `docs/research/taxonomy.md` | `pending_issue_42` | Label as historical illustrative cost; await Issue #42 cost ownership decision. |

---

## 4. Deep-Dive Section Analysis by Relationship Group

### 4.1. Identity and Object Control Group (`MemberOf`, `GenericAll`, `WriteDacl`, `ForceChangePassword`)

#### 4.1.1. `MemberOf` Passive Traversal vs Group Modification
In Active Directory, `MemberOf` represents structural membership in a security group.
During authentication, the Local Security Authority Subsystem Service (LSASS) evaluates transitive group memberships and populates the user's security token with all applicable Group SIDs.
Traversing an existing `MemberOf` relationship requires no active API call or modification of directory state: the attacker merely exercises the token privileges already issued to that principal.
Consequently:
- Passive `MemberOf` entitlement propagation has **no dedicated group-modification audit event** and the current catalog specifies `expected_telemetry: []`.
- Normal authentication or resource access performed using the resulting security token may still generate standard operational audit events (such as Kerberos TGT/ST requests or logon events).
- Windows Security Events 4728 (`A member was added to a security-enabled global group`) and 4729 (`A member was removed from a security-enabled global group`) represent administrative modifications of directory objects.
- Conflating passive traversal with group modification in early documentation created an artificial detection expectation; in Phase B, Events 4728/4729 must be associated exclusively with active group modification techniques (such as `genericall_add_member`), not with `MemberOf` traversal.
- In the verified candidate telemetry corpus (`reports/eda_summary.json`), Events 4728 and 4729 have zero recorded occurrences (0/4,633 rows), confirming no empirical corpus signal exists for either passive traversal or active group modification via those event IDs.

#### 4.1.2. Account Enablement and Structural Invariants
Prior to Issue #80, repository test fixtures enforced that a disabled account was pruned into a terminal node with `out_degree == 0`.
Audit finding C1 in #80 / PR #90 disproved this assumption:
- Active Directory database state (`ntds.dit`) preserves object attributes, group memberships, and DACL security descriptors identically whether `userAccountControl` contains `ACCOUNTDISABLE` (`0x0002`) or not.
- Pruning structural edges based on the `enabled` attribute corrupts the objective representation of Active Directory permissions.
- In accordance with ADR-0008, account enablement is a dynamic `runtime_predicate` (`actor_enabled`) evaluated by the Attack Semantics engine, not a filter for the structural graph builder.

#### 4.1.3. Object Control Disaggregation (`GenericAll`, `WriteDacl`, `ForceChangePassword`)
Early taxonomy documents treated `GenericAll` as a single monolithic attack step and cited `0xF01FF` as the `GENERIC_ALL` constant.
In standard Windows security specifications:
- The generic access-right constant is `GENERIC_ALL` (bit `0x10000000`) per [MS-DTYP: 2.4.3 Access Mask](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/7a53f60e-e730-4dfe-aab9-e2404e7f979f).
- Active Directory access check algorithms expand generic rights via `GENERIC_MAPPING` ([MS-ADTS: 5.1.3.2.1](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6f654b03-5e92-4f10-911e-2ce01c69c656)) into standard and object-specific rights, mapping `GENERIC_ALL` to `FullControl` (`0xF01FF` on standard directory objects).
- Parser and verification logic must support both the explicit generic right `GENERIC_ALL` (`0x10000000`) and the mapped FullControl mask (`0xF01FF`), without conflating the two numeric constants.

In operational reality, an attacker holding `GenericAll` over an object can execute several independent techniques depending on target object type:
1. `genericall_reset_password`: Targets User objects; resets credential; audited via Event 4724.
2. `genericall_add_member`: Targets Group objects; appends members; audited via Events 4728/4732/4756.
3. `genericall_grant_write_dacl`: Targets arbitrary directory objects; mutates DACL; audited via Event 5136.

Regarding `WriteDacl` and `AdminSDHolder`:
- The background `SDProp` task periodically (every 60 minutes) restores the security descriptors of protected administrative objects to the `AdminSDHolder` template ([MS-ADTS: 7.1.1.2.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/4934d402-601e-4530-ab01-7299f43054a1)).
- This mechanism does not prevent an attacker holding `WriteDacl` from modifying the object's DACL; the modification takes effect immediately upon write.
- Rather than an execution blocker, `AdminSDHolder` / `SDProp` acts as a temporal persistence and resistance condition, rolling back the unauthorized DACL modification at the next propagation cycle.

---

### 4.2. Host Access Authorization Group (`AdminTo`, `CanRDP`, `CanPSRemote`)

#### 4.2.1. Separation of Structural Topology from Network Reachability
A critical finding confirmed across Issue #80 and ADR-0008 is the strict separation between structural authorization and runtime reachability:
- Structural relationships (`AdminTo`, `CanRDP`, `CanPSRemote`) represent persistent access rights granted to principals on a host (e.g. membership in local Administrators, Remote Desktop Users, or Remote Management Users).
- Environmental conditions (such as open TCP ports 445/3389/5985, active system services `LanmanServer`/`TermService`/`WinRM`, firewall filtering, and NLA support) are dynamic operational states.
- Presenting open network ports as mandatory conditions for edge creation in early taxonomy was technically flawed: a server temporarily offline or firewalled does not lose its local security group configuration.
- In Phase B, network and service reachability conditions are documented strictly as `runtime_predicate` gates within the Attack Semantics catalog (`admin_channel`, `rdp_available`, `winrm_available`), leaving structural edge inference pure.

#### 4.2.2. Composite Authorization Rule for `CanRDP`
Per SpecterOps BloodHound research and Microsoft User Rights Assignment specifications (#80 C2), the canonical `CanRDP` edge in this repository requires all of the following:

```text
effective_member(principal, Host\Remote Desktop Users)
AND effective_right(principal, host, SeRemoteInteractiveLogonRight)
AND NOT effective_right(principal, host, SeDenyRemoteInteractiveLogonRight)
```

Nested security-group membership participates in evaluating effective RDU membership and user rights.
Explicit deny takes absolute precedence over allow ([Microsoft Account Rights Constants](https://learn.microsoft.com/en-us/windows/win32/secauthz/account-rights-constants)).

**Boundary Note Regarding Local Administrators:**
- Windows operating systems permit interactive remote desktop logons for members of the local `Administrators` group (`S-1-5-32-544`) by default when `SeRemoteInteractiveLogonRight` is present.
- In this repository's architectural model, local administrative authorization is strictly captured by the canonical `AdminTo` edge.
- Per accepted decision #90 C2, the capability of an administrator to log on via RDP does not justify synthesizing a canonical `CanRDP` edge from `AdminTo`.
- RDP access for administrators is modeled as an available management technique/channel under `AdminTo`, keeping the canonical `CanRDP` edge focused on non-admin Remote Desktop Users authorization.

#### 4.2.3. Host-Bound Evidence vs Domain-Wide Inference for `AdminTo`
`AdminTo(principal, host)` establishes local administrative authorization (`admin_control` effect in the Attack Semantics catalog).
Actual remote execution depends on an available administrative management channel (such as SMB, RPC, or WMI) and accepted authentication.
Possession of a privileged domain RID (such as Domain Admins `<DOMAIN-SID>-512`) does not inherently grant local administrative execution on an arbitrary computer unless that group is resolved as an effective member of the target computer's local `Administrators` group (`S-1-5-32-544`).
Parser and EDA components must enforce host-bound evidence; domain group membership alone must never synthesize an unevidenced `AdminTo` edge.

---

### 4.3. Session Opportunity Group (`HasSession`)

#### 4.3.1. Session Presence as an Opportunity vs Credential Acquisition
The relationship `Computer --HasSession--> User` records that an interactive or service logon session belonging to the user exists on the computer.
Early documentation conflated this relationship with the execution of credential dumping:
- Having a session on a computer does not automatically yield plaintext credentials or ticket material to an attacker.
- Transitioning from host access to compromised user credentials requires:
  1. Administrative control of the host (`SeDebugPrivilege`).
  2. Active technique execution (such as LSASS memory dumping via Mimikatz, MiniDumpWriteDump, or Kerberos ticket extraction).
  3. Absence of modern kernel/hypervisor mitigations: Virtualization-based Security (VBS), Credential Guard (`LSAIso.exe`), and Protected Users security group membership.
- In the Attack Semantics catalog, `HasSession` is classified as a `credential_opportunity`.
  The extraction of credential material is an active transition (`recover_session_credential_material`, MITRE ATT&CK T1003) governed by explicit runtime failure conditions.

---

## 5. Consumer Analysis and Single Source of Truth Resolution

### 5.1. Telemetry consumers at Phase A review time

At Phase A review time, the repository maintained telemetry mappings across two independent locations:
1. **`configs/attack_semantics.yml`**:
   The authoritative, machine-readable runtime semantics catalog.
   Defines transitions, prerequisites, failure conditions, and expected auditing telemetry.
2. **`scripts/eda_dataset_analysis.py::m1_edge_telemetry`**:
   An exploratory mapping matrix embedded inside the EDA analysis tool, published into `reports/eda_summary.json` and discussed in `docs/research/data-quality-report.md`.

### 5.2. Single Source of Truth Principle

Maintaining two independent mapping definitions creates severe architectural drift risks:
- In `scripts/eda_dataset_analysis.py`, `MemberOf` listed candidate events `4728` and `4729`, directly contradicting the zero-action contract in `configs/attack_semantics.yml`.
- In `docs/research/data-quality-report.md`, references were made to "dynamic edges inferred from telemetry" and "factual ground truth", which violate ADR-0007 and ADR-0008.

**Authoritative Decision:**
- [`configs/attack_semantics.yml`](../../configs/attack_semantics.yml) is the **sole authoritative Source of Truth** for Active Directory attack semantics and runtime transitions.
- The former telemetry matrix in [`scripts/eda_dataset_analysis.py`](../../scripts/eda_dataset_analysis.py) and [`reports/eda_summary.json`](../../reports/eda_summary.json) was classified as a **descriptive evidence inventory** during Phase A.
  Phase B1 removes that relationship-to-EventID matrix, leaving no independent runtime behavior or competing mapping rules in EDA output.
- Under ADR-0007, independent telemetry from EVTX-ATTACK-SAMPLES cannot be joined with SEAMLESS topology at the entity level and must not be used to calibrate production graph weights.

The preceding matrix discussion records the Phase A audit of the earlier generator state.
Current EDA output contains only independent corpus frequencies, explicitly labeled upstream tactic annotations, and a boundary pointing to the sole runtime catalog.

### 5.3. Transition-Attached Telemetry vs Descriptive Corpus Inventory

A crucial architectural distinction exists between expected telemetry at the semantic transition level and corpus statistics:
- **Transition-Level Telemetry (Normative):**
  Auditing signals are attached to concrete attack techniques in `configs/attack_semantics.yml`.
  Where telemetry depends on the operational channel, transport protocol, or endpoint auditing policy (such as in `AdminTo`, `CanPSRemote`, and `HasSession`), the catalog explicitly specifies `event_id: null` with descriptive requirement text.
  For multi-action capabilities like `GenericAll`, telemetry is segregated across specific transitions (`genericall_reset_password` -> 4724, `genericall_add_member` -> 4728/4732/4756, `genericall_grant_write_dacl` -> 5136).
- **Corpus-Level Inventory (Descriptive):**
  Phase B1 EDA reports EventID frequencies and `EVTX_Tactic` upstream annotations from the independent corpus without grouping candidate events by relationship.
  Provider/channel/event qualifiers and entity-level correlation remain unassessed, so these frequencies are not normative runtime contracts or confirmed attacks.

---

## 6. Historical Phase B remediation plan from Phase A (Task 4)

The following plan records the Phase A review disposition; current completion is assessed in Section 9 below:

| File / Component | Current State / Defect | Remediation Action in Phase B |
| --- | --- | --- |
| [`docs/research/taxonomy.md`](taxonomy.md) | Lists fixed MAUT v1 weights, presents network ports as structural prerequisites, includes stale disabled-account pruning claim. | Remove fixed weights from taxonomy table (relabel as historical illustrative); reclassify network ports as Attack Semantics runtime predicates; align disabled account handling with #80. |
| [`docs/research/attack-semantics.md`](attack-semantics.md) | Contains legacy narrative sections prior to ADR-0008/0009 finalization. | Realign narrative text to match audited six-layer boundaries; cross-reference `m1-evidence-audit.md`. |
| [`scripts/eda_dataset_analysis.py`](../../scripts/eda_dataset_analysis.py) | #80 separates raw host arrays from canonical claims; the remaining `m1_edge_telemetry` matrix still claimed relationship-to-EventID mappings before B1. | B1 removes the matrix, labels `EVTX_Tactic` as upstream annotation, and keeps EventID counts as unqualified corpus statistics. |
| [`reports/eda_summary.json`](../../reports/eda_summary.json) | #80 generated output separates raw host primitives and reports verified `CanRDP` as unmeasurable for current SEAMLESS. | B1 regenerates the current SEAMLESS/telemetry sections atomically while preserving historical sections through the documented path. |
| [`docs/research/data-quality-report.md`](data-quality-report.md) | Contains stale wording regarding "inferred/dynamic relationships from logs" and unqualified "factual ground truth". | Realign terminology with ADR-0007/0008; clarify that telemetry provides candidate validation signals, not structural graph edges. |
| [`docs/research/dataset-proposal-and-eda.md`](dataset-proposal-and-eda.md) | Mentions telemetry-driven edge weight calibration. | Update narrative to reflect that production weighting ownership is governed by Issue #42 and ADR-0008. |
| [`tests/test_eda_analysis.py`](../../tests/test_eda_analysis.py) / [`tests/test_eda_cli.py`](../../tests/test_eda_cli.py) | #80 tests protect raw RDU versus verified `CanRDP`; pre-B1 telemetry tests did not reject the stale matrix. | B1 adds CLI and parser regression tests that reject relationship-to-EventID mappings and check annotation provenance. |

---

## 7. Conclusion and Next Steps

This audit establishes a rigorous, defensible boundary across all eight Milestone 1 relationships.
It successfully separates immutable Active Directory structural topology from runtime execution predicates, disaggregates complex permissions into explicit attack transitions, and identifies the precise remediation actions required across the repository.

Phase A is complete upon review and merge of this document.
At the time of Phase A, Phase B was the next implementation step; Section 9 records the later disposition.

## 8. Phase B progress amendment (2026-09-22)

The Phase A matrix above remains the review baseline from PR #93, with the `MemberOf` zero-row inference corrected in place because absence of matching EventID rows cannot establish absence of an activity.
Documentation-only remediation now separates structural taxonomy from techniques, runtime predicates and fixed MAUT weights, and replaces duplicate narrative event mappings with catalog technique references.
The data-quality and dataset-proposal narratives no longer authorize independent telemetry to create structural edges or calibrate production weights.
The inventory no longer describes disabled-account pruning as a normalization rule.
At the time of this amendment, the taxonomy's historical RODC block still required separate PR #96 review and integration.

| Remaining deliverable | Owner / prerequisite |
| --- | --- |
| EDA raw RDU versus verified composite CanRDP reporting and regression tests | #80 and #79 consume accepted #94 field/completeness findings |
| EDA descriptive telemetry inventory with catalog references and regenerated report | #79 consumes accepted #94 qualifier/column findings; #81 owns structured mapping provenance |
| Raw-field/missingness interpretations in research tables | #79/#80 consume accepted #94 evidence; existing metrics were not remeasured in this amendment |
| Immutable ObservedActivity and structured mapping evidence | #81 |
| ADR legacy cost/RODC status cleanup integration | Completed by #83 / merged PR #96; missing independent pre-merge approval remains a documented process exception |
| Production weighting | #42 after #79 Phase B acceptance and an approved cost-ownership successor decision; #83 is closed |

At the time of this amendment, Phase B remained open; no raw-schema decision, generated report change, builder implementation or production weighting was included in that documentation-only slice.
PR #99 merged at `e4b7a1e` and #94 closed after this amendment; its findings then became available to Phase B.
PR #96 merged at `a90a57c` and #83 closed after the earlier Phase B progress note.

## 9. Phase B acceptance evidence and remaining gates

Phase B1 PR #102 is merged at `ff1b05e`; Phase B2 is the current remediation branch and remains subject to CI and independent review.
This table maps each Issue #79 acceptance criterion to the concrete repository evidence and does not imply that an unmerged branch has passed the repository Definition of Done.

| #79 criterion | Concrete evidence and disposition |
| --- | --- |
| Six-layer audit of all eight kinds | Section 3 matrix covers `MemberOf`, `AdminTo`, `GenericAll`, `WriteDacl`, `ForceChangePassword`, `CanRDP`, `CanPSRemote`, `HasSession`; ADR-0007/0008/0009 bound the layers. |
| Structural taxonomy has no normative fixed weight, technique or telemetry per edge | [Taxonomy section 1](taxonomy.md#1-bảng-tổng-hợp-8-loại-cạnh-m1-chuẩn-hóa) lists only direction, structural meaning and evidence conditions; its Phase B2 amendments identify `maut_v1` as historical and route cost ownership to #42. |
| One authoritative runtime catalog; EDA descriptive only | [`configs/attack_semantics.yml`](../../configs/attack_semantics.yml) owns transitions and ExpectedTelemetry; [`scripts/eda_dataset_analysis.py`](../../scripts/eda_dataset_analysis.py) emits corpus EventID distributions and upstream labels without edge-to-event mapping; B1 regression is `tests/test_eda_cli.py::test_event_id_counts_do_not_map_passive_membership_or_session_access`. |
| Passive `MemberOf` separated from membership modification | [Taxonomy section 2.1](taxonomy.md#21-nhom-identity-memberof-va-hassession-giai-quyet-issue-1) and catalog `propagate_group_entitlement` preserve `action_required: false` and `expected_telemetry: []`; group-modification transitions own 4728/4729-style signals. |
| `HasSession` remains session opportunity | [Taxonomy section 2.1](taxonomy.md#21-nhom-identity-memberof-va-hassession-giai-quyet-issue-1), [#94 telemetry audit](windows-telemetry-raw-field-audit.md), and B1 EDA regression reject Sysmon 10 as session evidence or credential material. |
| Telemetry mappings have source and confidence semantics | Section 3 traces claim, layer, source, population, category, confidence and consumer; [#94 claim-to-field traceability](claim-to-field-traceability.md) adds raw qualifiers; merged #81/PR #103 introduces catalog v0.2 evidence refs, but its `genericall_add_member` ref currently supports 4732 only, not the named 4728/4756 signals; final mapping-evidence acceptance remains blocked on B-owned #81 follow-up. |
| Stale taxonomy, data-quality and proposal wording realigned | [Taxonomy](taxonomy.md), [data-quality report](data-quality-report.md), [dataset proposal](dataset-proposal-and-eda.md), [dataset representativeness](dataset-representativeness.md), and [active inventory](data-inventory.md) distinguish raw positive evidence from unknown completeness and 66.374 audited references from 66.371 EDA graph entries; `tests/test_eda_analysis.py::test_audit_data_quality` guards generated-report wording. |
| Architecture changes use successor ADRs | No ADR is rewritten in B1/B2; #42 owns cost ownership, #92 ordered lineage, and #97 canonical collection-time status; #81 provenance changes were merged separately in PR #103 and remain under post-merge review. |

The regenerated EDA report is generated from its source after the B2 code commit, not edited by hand.
Issue #79 remains open after Phase B2 until independent review/merge is complete and the #81 catalog evidence gap for 4728/4756 is resolved with auditable source references or a narrowed normative claim.

## 10. Issue #81 provenance status (2026-09-23)

The accepted matrix remains the source for semantic claims and qualifiers.
The separately merged #81/PR #103 implementation records rationale for normative expected-telemetry mappings in catalog v0.2's evidence registry, while corpus availability remains a separate observed fact.
`ObservedActivity` requires a manifest-backed dataset, snapshot, raw-file reference and record locator.
This does not make independent telemetry evidence for a structural edge, and a correlation remains a candidate unless explicit confirmation evidence is supplied.
The final post-merge review of PR #103 withdrew approval and identified whole-snapshot verification, public correlation-construction, and `genericall_add_member` evidence-coverage gaps for B-owned follow-up.
The last gap directly blocks Issue #79's telemetry-mapping source criterion; B2 does not change #81 code or catalog ownership.
