---
applyTo: "src/parser/**"
---
# Review Checklist: Parser Layer (`src/parser/`)

When reviewing changes to `src/parser/`, verify the following invariants:

1. **Canonical ID Strategy**:
   - Strictly follow the `sid_then_scoped_sid_then_guid` strategy.
   - SIDs with scope requirements (`S-1-5-18`, `S-1-5-19`, `S-1-5-20`, and `S-1-5-32-*`) must use `<scope-kind>:<scope-guid>:<sid>`.
   - All GUID characters must be converted to lowercase.
   - If an identity lacks a stable scope or valid ID, reject the record. Never guess, fallback to display names, or emit random UUIDs.

2. **Edge Directionality (ADR-0002)**:
   - Verify that edge directions reflect traversable privilege flow from controlled source to target:
     - `MemberOf`: User or Group -> Group
     - `HasSession`: Computer -> User (compromised Computer yields interactive User credentials)
     - `AdminTo`: User or Group -> Computer
   - Do not invert edge direction without an explicit ADR amendment.

3. **Host Access & Edge Inference Policy (ADR-0003)**:
   - For `CanRDP` and `CanPSRemote`, verify both explicit allow privileges and the absence of denying restrictions.
   - Any `StatusAccessDenied` or ambiguous collection state is classified as `unknown` and must NOT generate an edge.
   - Do not synthesize independent edges from co-occurring prerequisites if doing so would create false-positive paths.

4. **Provenance & Multigraph Integrity**:
   - Every edge must preserve complete provenance: `raw_file`, `collector`, and `timestamp` (UTC `YYYY-MM-DDTHH:MM:SSZ`).
   - Identical logical edges (`[source, target, kind]`) must aggregate unique provenance records instead of duplicating edges.
   - Distinct techniques between the same pair of nodes must be preserved as parallel edges in the multigraph.
   - Ensure both `source` and `target` nodes are valid and present before attaching edges; no dangling edges.

5. **Error Policy & Clean State**:
   - Conform to `process_records` error policies (`FAIL_FAST`, `SKIP_RECORD`, `LOG_WARNING`).
   - Only data validation issues at the record level may raise `RecordError`.
   - Never use blanket `except Exception: pass`. IO, JSON envelope, or parser runtime errors must halt execution.
   - Validate records before modifying shared state to ensure skipped records do not leave incomplete or orphan nodes/edges.
