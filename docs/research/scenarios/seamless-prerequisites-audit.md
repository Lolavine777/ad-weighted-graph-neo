# SEAMLESS Runtime Prerequisites Audit and Policy Classification

- Author: TTS A (@Lolavine777)
- Issue: #290 (SEAMLESS-wide Scenario Assumption Profile)
- References: #259, #265, #287, #211, #275
- Bound Snapshot ID: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`

## 1. Executive Summary

This audit establishes the rigorous, four-tier classification of all Active Directory attack technique runtime prerequisites in SEAMLESS.
It provides the objective boundary between safe environment conditions and assumptions requiring explicit evidence or opt-in.
The policy guarantees that unrated conditions do not silently fabricate attack capabilities or distort reachability.

| Classification | Count | Description |
| --- | --- | --- |
| `observed` | 13 | Derived strictly from graph structure, evaluator state, or snapshot facts |
| `safely_conditionable` | 22 | Standard AD intranet environment conditions safely conditionable in `seamless_standard_scenario` |
| `needs_scoped_override` | 5 | Specific conditions requiring explicit user opt-in (password cracking, distribution groups, RBCD) |
| `cannot_default` | 4 | Strictly forbidden from defaulting; attacker capabilities and fictitious edges |
| **Total** | **44** | Full active catalog predicate coverage |

## 2. Detailed Prerequisites Classification Matrix

| Predicate | Classification | Category | Description | Policy & Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| `actor_controlled` | `observed` | evaluator_state | Attacker has active control over the executing actor | Evaluated strictly from branch AttackState.control or usable_identity. Never an external assumption. |
| `actor_authenticated` | `observed` | evaluator_state | Actor identity is usable within the current authentication context | Evaluated from branch AttackState.usable_identity matching context.authentication_context. |
| `source_authorized` | `observed` | evaluator_state | Source principal is either actor itself or a group of which actor is an effective member | Evaluated dynamically from branch AttackState.effective_member. |
| `source_admin_control` | `observed` | evaluator_state | Source computer host is under administrative control | Evaluated from branch AttackState.admin_control. |
| `reset_password_control` | `observed` | evaluator_state | Actor holds capability to reset passwords on target | Evaluated from branch AttackState.reset_password_control. |
| `authentication_context_matches` | `observed` | evaluator_state | Target matches the authentication context of the query | Evaluated by comparing target node ID with context.authentication_context. |
| `known_identity` | `observed` | evaluator_state | Target identity is known to the attacker through discovery or initial state | Evaluated from AttackState.known_identity. |
| `asrep_request_capability` | `observed` | evaluator_state | Foothold has capability to send raw AS-REQ packets | Evaluated from AttackState.asrep_request_capability. |
| `dontreqpreauth` | `observed` | snapshot_attribute | User account has Kerberos preauthentication disabled (DONT_REQ_PREAUTH UAC flag) | Authoritative property collected in BloodHound v3 snapshot facts. |
| `has_spn` | `observed` | snapshot_attribute | User account has one or more Service Principal Names registered | Authoritative property from users.json serviceprincipalnames array. |
| `service_principal_names` | `observed` | snapshot_attribute | List of SPNs registered on the user object | Authoritative property from snapshot facts. |
| `actor_enabled` | `observed` | snapshot_attribute | Actor object enabled status in Active Directory | Authoritative property from snapshot. If enabled=False, triggers known-false veto. |
| `target_enabled` | `observed` | snapshot_attribute | Target object enabled status in Active Directory | Authoritative property from snapshot. If enabled=False, triggers known-false veto. |
| `network_kdc_reachable` | `safely_conditionable` | environment_network | Kerberos Key Distribution Center (port 88) is reachable over network | Standard Active Directory domain intranet condition; DCs are reachable from domain members. |
| `network_rpc_reachable` | `safely_conditionable` | environment_network | MS-RPC port 135 and dynamic RPC ports reachable for SAMR operations | Standard AD condition for directory management and password reset operations. |
| `network_winrm_reachable` | `safely_conditionable` | environment_network | WinRM HTTP/HTTPS ports (5985/5986) reachable on target computers | Standard condition for remote management in enterprise Windows environments. |
| `service_winrm_running` | `safely_conditionable` | environment_service | WinRM management service is active and listening on target computer | Expected state for remote administration targets under management policy. |
| `asrep_request_accepted` | `safely_conditionable` | protocol_acceptance | KDC accepts AS-REQ for accounts with preauth disabled | Standard RFC 4120 behavior implemented by Active Directory KDC. |
| `service_ticket_request_accepted` | `safely_conditionable` | protocol_acceptance | KDC issues TGS service ticket for valid registered SPN | Standard RFC 4120 Kerberos behavior for authenticated domain users. |
| `kerberos_authentication_usable` | `safely_conditionable` | protocol_acceptance | Kerberos authentication package is operational on client workstation | Standard condition on Windows domain member systems. |
| `kerberos_actor_authenticated` | `safely_conditionable` | protocol_acceptance | Logon session holds valid initial Kerberos TGT | Standard condition for authenticated domain user logon. |
| `admin_channel` | `safely_conditionable` | administrative_access | Administrative protocol channel (SMB/WMI/WinRM) open for local administrators | Standard condition for hosts where identity possesses AdminTo rights. |
| `admin_execution_context` | `safely_conditionable` | administrative_access | Host execution environment allows administrative command execution | Standard condition for local administrator sessions. |
| `endpoint_authorized` | `safely_conditionable` | administrative_access | Target endpoint authorizes management connections from designated administrators | Corresponds to local administrator rights on target system. |
| `host_admin_mapping` | `safely_conditionable` | administrative_access | Local administrator group mapping corresponds to AdminTo entitlement | Standard mapping of Domain Admins or delegated local admins. |
| `authentication_accepted` | `safely_conditionable` | authentication | Target accepts valid domain credentials for authentication | Standard Active Directory domain member authentication behavior. |
| `winrm_authentication_accepted` | `safely_conditionable` | authentication | WinRM listener validates administrative domain credentials | Standard behavior for remote management users. |
| `rdp_available` | `safely_conditionable` | administrative_access | Remote Desktop service is enabled and accepting connections | Standard condition for CanRDP edge targets in enterprise environments. |
| `winrm_available` | `safely_conditionable` | administrative_access | WinRM PowerShell remoting endpoint is available on target host | Standard condition for CanPSRemote edge targets. |
| `directory_write_allowed` | `safely_conditionable` | directory_dacl | Directory modification allowed under granted GenericAll or WriteDacl ACE | Standard AD DACL semantics: object ACE grants modification rights. |
| `password_policy_accepts` | `safely_conditionable` | directory_dacl | Password reset complies with domain password length and complexity policy | Attacker can generate passwords that conform to known domain policy. |
| `membership_change_allowed` | `safely_conditionable` | directory_dacl | Adding members to group is permitted under GenericAll on Group | Standard AD object control behavior for security groups. |
| `membership_usable` | `safely_conditionable` | token_propagation | Group SID is incorporated into access token upon session logon | Standard Kerberos/NTLM PAC authorization token construction. |
| `secret_valid` | `safely_conditionable` | credential_activation | Recovered or reset password matches directory hash and is unexpired | Once secret is recovered or set, authentication succeeds. |
| `security_group` | `safely_conditionable` | group_type_boundary | Target group is a security group (not a distribution list) capable of token authorization | Safely conditionable for recognized security groups (Domain Users, Admins, etc.). STRICTLY FORBIDDEN from defaulting to True for groups named DISTLIST or DISTRIBUTION. Distribution groups require an explicit scoped override. |
| `recovery_success` | `needs_scoped_override` | password_cracking | Offline password recovery successfully cracks ticket or AS-REP response | Depends on password complexity, hashcat dictionary, GPU budget, and time horizon. STRICTLY FORBIDDEN from defaulting to True in seamless_standard_scenario. Must NEVER be assumed without explicit recovery_opt_in specifying target, budget, and method. Never implies P=1; likelihood remains governed by rating basis. |
| `session_fresh` | `needs_scoped_override` | credential_dumping | Cached logon session in LSASS is unexpired and active | Requires live telemetry or explicit scoped override. Not present in SharpHound raw data. |
| `session_present` | `needs_scoped_override` | credential_dumping | Target user session currently exists in LSASS memory | Requires live telemetry or explicit scoped override. |
| `credential_accessible` | `needs_scoped_override` | credential_dumping | LSASS memory is readable (Credential Guard not enforcing isolation) | Requires endpoint security configuration evidence. |
| `rbcd_delegation_gates` | `needs_scoped_override` | rbcd_delegation | RBCD delegation gates (s4u_request_accepted, delegation_policy_allows, etc.) | Requires specific RBCD recipe bindings and explicit delegation opt-in. |
| `usable_identity` | `cannot_default` | attacker_capability | Attacker holds credentials and interactive logon rights for user identity | Attacker capability must come strictly from declared foothold or valid technique effects (activate_recovered_identity, acquire_reset_identity). Never granted by assumption. |
| `admin_control` | `cannot_default` | attacker_capability | Attacker holds elevated code execution on target computer host | Goal/consequence capability must be attained through applicable technique chain (obtain_admin_execution_on_host, scenario_winrm_admin). Never granted by assumption. |
| `control` | `cannot_default` | attacker_capability | Direct administrative control over object | Must come from initial foothold. Never assumed by policy. |
| `relationship_exists` | `cannot_default` | structural_boundary | Structural relationship exists in the Active Directory directory | Canonical graph structure is immutable; policy cannot invent edges. |

## 3. Deep Dive into Critical Security Boundaries

### 3.1 Group Type Boundary (`security_group`)

In Active Directory, only security-enabled groups (security groups) generate SIDs in access tokens for DACL authorization.
Distribution groups (distribution lists) are purely email routing artifacts and cannot grant permissions.
Because BloodHound v3 raw data does not collect the `groupType` attribute, naive assumptions would treat distribution lists as security groups.
Under the SEAMLESS policy profile, groups containing `DISTLIST`, `DISTRIBUTION`, or `DL` in their naming are classified as `needs_scoped_override`.
They are strictly forbidden from defaulting to True in `seamless_standard_scenario`.
Standard security groups (`DOMAIN USERS`, `DOMAIN ADMINS`, `AUTHENTICATED USERS`, `PRE-WINDOWS 2000 COMPATIBLE ACCESS`, `*ADMINGROUP*`) are safely conditioned as True.

### 3.2 Offline Password Recovery Restriction (`recovery_success`)

Password cracking success depends on password complexity, hashcat rule dictionaries, GPU resources, and time horizon.
In accordance with Issue #290 and #259, `recovery_success` is strictly classified as `needs_scoped_override` and cannot default to True in standard mode.
Replaying an AS-REP or Kerberoasting attack path in standard mode halts with `indeterminate` at the recovery step.
Evaluating a successful recovery requires an explicit `recovery_opt_in` override specifying target user, budget, and cracking method.
Even when assumed True under an explicit override, `recovery_success` never implies probability P=1.
Numerical rating remains unrated without an adopted empirical or expert rating basis.

### 3.3 Attacker Capability Invariant

Attacker capabilities (`control`, `usable_identity`, `admin_control`) cannot be assumed by policy.
Initial capabilities arise solely from the declared foothold.
Downstream capabilities arise solely as the verified state effects of APPLICABLE technique execution.
Any override attempting to assert `usable_identity` or `admin_control` directly is rejected with `override_violates_non_negotiable_security_boundary`.

### 3.4 Known-False Veto Invariant

Authoritative evidence in the snapshot (such as `enabled=False` on an account) or in query runtime facts always overrides scenario assumptions.
When conflicting evidence exists, the assumption is rejected with reason `known_false_veto` and the state decision evaluates to `BLOCKED`.
