---
applyTo: "src/engine/**"
---
# Review Checklist: Engine Layer (`src/engine/`)

When reviewing changes to `src/engine/`, verify the following invariants:

1. **Dijkstra Preconditions**:
   - Edge weights must be strictly non-negative (cost >= 0.0). Flag any negative weights immediately.
   - If log-transformed probabilities (-log(p)) are used, verify that 0 < p <= 1 and that independence assumptions are documented.
   - Costs without time units must not be interpreted as physical time (minutes/hours).

2. **Multigraph Semantics**:
   - The engine operates on directed multigraphs. Parallel edges between the same source and target represent distinct
     attack techniques and must not be collapsed or overwritten.
   - Path traversal must explicitly record which edge instance was chosen.

3. **Deterministic Behavior & Tie-Breaking**:
   - Shortest path calculations must produce deterministic output.
   - When multiple paths or edges share identical weights, tie-breaking must use a stable, deterministic rule
     (e.g., lexical ordering by edge ID / node ID) rather than non-deterministic hash iteration.

4. **Path Reconstruction**:
   - Output paths must return complete structures: ordered `node_ids`, ordered `edge_ids`, `total_cost`, `profile_name`,
     and `contract_version`.
   - When no path exists between source and target, return an explicit structured result indicating the disconnection reason
     rather than throwing unhandled exceptions.

5. **Graph Edge Cases**:
   - Verify graceful handling of disconnected subgraphs, isolated nodes, cycles, and self-loops.
   - Ensure performance benchmarks or algorithm implementations do not degrade catastrophically on dense or cyclic AD graphs.
