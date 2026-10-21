# Supplementary native coverage v1.1

Consumer `0ef3ffd2f52859916d78d0b1070ab15c8df7a28d` preserves the original eight-query packet at `4452ca1f25a637b484193a3dc5d6272163d546af`.
The original accepted 0/50 and synthetic 49/50 counts are unchanged and are not pooled with this extension.
All new numeric/context records remain pending B cross-review/adoption.

| Supplementary query | Graph | Generated / feasible | Accepted full | Synthetic full | Native limit/status |
| --- | --- | --- | --- | --- | --- |
| rbcd-unassumed | Full raw | 0 / 0 | 0 | 0 | indeterminate |
| rbcd-scoped | Full raw | 3 / 3 | 0 | 3 | success |
| acl-group-host | Full raw | 3 / 3 | 0 | 3 | expansion_limit_reached |
| acl-group-projection | 4 nodes / 12 edges induced projection | 100 / 100 | 0 | 100 | path_limit_reached |
| acl-group-all-generator | Full raw | 2 / 2 | 0 | 2 | expansion_limit_reached |
| winrm-command | Full raw | 1 / 1 | 0 | 1 | success |

The three supported raw supplementary queries return 7 conditioned-feasible programs: accepted full 0/7, synthetic wiring full 7/7.
The unassumed, induced-projection and all-generator controls remain visible in the table and are outside that supported subtotal.
Zero-program fractions are undefined and do not establish safety.
The projection and raw variants repeat some programs; class exposure and query counts are not a statistically representative all-source fraction.

The combined diagnostic queries expose 17/20 active classes in goal-reaching programs; full-raw returned programs expose 15/20.
Exposure includes the still-unrated AS-REP recovery class and does not mean those classes have adopted likelihood values.
HasSession, CanRDP and ForceChangePassword have zero observed raw edges; no unsupported demonstration edge is inserted.
The frozen Kerberoast usable-identity goal still has the B-owned endpoint/state attribution gap, and natural-password recovery still has no defensible numeric rank/compute basis.

All six supplementary cases match full selected API/CLI fields and exposed orchestration search/ranking/programs, with 24 successful CLI processes and two normalized native runs per mode.
Independent Fraction/C oracles verify every synthetic eligible program; 47 historical files are byte-preserved.
Final local full suite: 2626 passed, 9 skipped, 48 subtests passed in 523.10s.
Ruff/format/contract/repository/privacy/diff checks are reported with the worklog.
Remote CI at the prior head did not start because of GitHub billing; remote verification is not reported PASS.

## Worked supplementary programs

| Query / candidate | Native generated program | C | Conditional P | Typed I |
| --- | --- | --- | --- | --- |
| rbcd-scoped / generated_0001 | rbcd_configure_descriptor -> rbcd_acquire_secret -> rbcd_prepare_service -> rbcd_delegate_service -> rbcd_service_admin | 9 | [504/3125,15760899/20000000] | High |
| acl-group-host / generated_0001 | obtain_admin_execution_on_host | 1 | [3/5,19/20] | High |
| acl-group-projection / generated_0005 | propagate_group_entitlement -> grant_new_object_right -> genericall_grant_write_dacl -> obtain_admin_execution_on_host | 4 | [147/500,17689/20000] | High |
| winrm-command / generated_0001 | open_winrm_remote_session | 1 | [7/10,19/20] | Medium |

The RBCD product uses five event-specific class questions across each exact successful ordering, not an AS-REP probability transfer.
The ACL inventory includes existing administrative shortcuts and both observed/derived permission producers.
Mutation and passive token closure do not become the same event, and granted directory rights do not themselves imply host control.
The command-session goal retains Medium and cannot borrow administrative High.

## B handoff

Review the exact class/context/history envelopes produced before search and record actual numeric adoption references per defensible group.
Retain `estimated_expert_scenario` and truthful review disposition in public output.
Decide the User-goal endpoint/state contract and integrate broader source/profile/batch/remediation support in B-owned #265 code.
Source ranking and choke-point sensitivity are still unmeasured and cannot be replaced by query-local bounds checks.
The production 80% gate remains unachieved.
B merged the original #266 at `5a2615c` through develop `7368cac`; the separate verifier follow-up #272 and taxonomy PR #271 remain draft/unmerged.

[Frozen supplementary cohort](supplementary-cohort.json), [scope/audit](supplementary-audit.md), [sanitized native evidence](../../../../reports/research/issue267-final-cpi-v1-supplement-verification.json).

```sh
.venv/bin/python -m scripts.research.final_cpi_extension --raw-dir data/raw/SEAMLESS --output reports/generated/issue267-supplement/verification.json
```
