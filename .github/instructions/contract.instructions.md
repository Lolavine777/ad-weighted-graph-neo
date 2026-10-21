---
applyTo: "configs/contract.yml"
---
# Review Checklist: Data Contract & Schema (`configs/contract.yml`)

When reviewing changes to `configs/contract.yml`, verify the following requirements:

1. **Schema Backward Compatibility**:
   - Verify whether schema changes break existing parsers, validators, or fixtures.
   - Any breaking schema modification requires a version bump and ADR reference.

2. **Node & Edge Kinds**:
   - Node kinds must strictly match allowed types: `[User, Computer, Group, Domain, OU, GPO]`.
   - Milestone 1 edge kinds must remain consistent: `MemberOf`, `AdminTo`, `GenericAll`, `WriteDacl`, `ForceChangePassword`,
     `CanRDP`, `CanPSRemote`, `HasSession`.
   - Any new node or edge kind must be justified with technical rationale and documented in `docs/research/taxonomy.md`.

3. **Required vs. Optional Fields**:
   - Mandatory node fields: `id`, `kind`, `label`.
   - Mandatory edge fields: `id`, `source`, `target`, `kind`, `provenance`.
   - In graph data, optional fields can be omitted entirely, but explicit `null` values are strictly rejected.

4. **Weight Profiles**:
   - All edge weights must be finite and strictly non-negative (cost >= 0.0).
   - Research/experimental profiles (e.g., `unit`, `illustrative`, `maut_v1`) must declare `production_ready: false`.
   - No weight profile may be designated as `production_ready: true` without formal empirical validation on AD graphs.
