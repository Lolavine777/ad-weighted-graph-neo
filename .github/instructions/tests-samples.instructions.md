---
applyTo: "tests/**, data/samples/**"
---
# Review Checklist: Tests & Sample Data (`tests/`, `data/samples/`)

When reviewing changes to `tests/` or `data/samples/`, verify the following requirements:

1. **Milestone 1 Coverage**:
   - Test cases and sample fixtures must cover all 8 Milestone 1 edge kinds: `MemberOf`, `AdminTo`, `GenericAll`,
     `WriteDacl`, `ForceChangePassword`, `CanRDP`, `CanPSRemote`, `HasSession`.
   - Both node kinds and scoped/unscoped canonical IDs must have adequate test representation.

2. **Negative & Edge Cases**:
   - Ensure negative scenarios are explicitly tested: malformed SIDs, unresolvable scoped identities, cycle detection,
     missing provenance fields, disconnected source/target pairs, and conflicting attributes.

3. **Synthetic Data Hygiene**:
   - Fixtures and sample graphs must be explicitly labeled as synthetic baselines.
   - Never describe synthetic samples or test graph outputs as production AD evidence or real-world security conclusions.

4. **Zero Sensitive Data Leak**:
   - Verify that test files, fixtures, and manifests contain no authentic Active Directory production data, real user names,
     internal domain secrets, or credentials.
   - Verify compliance with repository privacy checks (`scripts/check_repository.py`).
