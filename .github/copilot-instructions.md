# Repository Instructions for GitHub Copilot Code Review

## Project Overview & Architecture

`ad-weighted-graph` models Active Directory (AD) attack graphs with weighted edges to compute realistic shortest attack paths and identify defensive choke points.

Key components:
- `configs/contract.yml`: Core contract defining schema versions, canonical ID formats, allowed node/edge kinds, required/optional fields, and weight profiles.
- `src/parser/`: Raw BloodHound data ingestion, canonical ID normalization, provenance preservation, and graph assembly.
- `src/engine/`: Weighted pathfinding (Dijkstra, Top-K), deterministic tie-breaking, and path reconstruction.
- `docs/research/` & `docs/adr/`: Security semantics research, taxonomy, and Architectural Decision Records (ADR-0001 through ADR-0006).
- `tests/` & `data/samples/`: Unit/contract test suite and synthetic sample fixtures.

---

## Core Review Principles (Non-Negotiable)

1. **Advisory Role Only**:
   - Copilot is an advisory assistant. Never issue a binding approval or automatically approve a PR.
   - Final review and approval authority belongs exclusively to human maintainers (@Lolavine777 for taxonomy/weights/analysis, @nairyuuu for environment/parser/engine/benchmarks).

2. **Security Semantics & Attack Paths**:
   - Prioritize identifying changes that introduce **false-positive** (non-exploitable or imaginary) or **false-negative** (missed viable transitions) attack paths.
   - Graph edges must reflect actual Windows/AD privilege transitions, not superficial LDAP relationships.

3. **CI Green != Semantic Correctness**:
   - A passing CI build only proves syntax, formatting, and basic test assertions.
   - Never assume code or weights are correct just because CI checks pass. Rigorously evaluate AD security semantics, directionality, and boundary assumptions.

4. **Contract, Taxonomy & ADR Consistency**:
   - Code, tests, and documentation must strictly align with `configs/contract.yml` and approved ADRs (`docs/adr/`).
   - Flag any schema, ID formatting, or directionality drift that lacks an accompanying contract or ADR update.

5. **Strict Data & Assumption Stratification**:
   - Explicitly distinguish between:
     - **Research Assumptions**: Theoretical or working hypotheses documented in `docs/research/`.
     - **Synthetic / Test Fixtures**: Mock data and baseline weights (`unit`, `illustrative` in `configs/contract.yml`). These must NEVER be presented as real-world production evidence.
     - **Production-Ready Semantics**: Validated on authentic AD structures with documented provenance and empirical rationale.

6. **Technical Verification & Citations**:
   - Require concrete technical rationales or authoritative references (Microsoft docs, BloodHound specifications, CVE/CVSS details) for any claims regarding Active Directory mechanics or exploitation prerequisites.

7. **PR Intent & Acceptance Criteria Verification**:
   - Cross-check every PR diff against its linked issue and acceptance criteria.
   - Flag out-of-scope modifications, missing tests, or unfulfilled acceptance criteria.

---

## High-Level Area Review Checklists

When files in the following areas are touched, verify their specific invariants (detailed path-specific instructions are located in `.github/instructions/`):

- **`configs/contract.yml`**: Verify schema backward compatibility, valid node/edge kinds, non-negative weight profiles with `production_ready: false`, and strict distinction between absent optional fields and rejected explicit `null` values.
- **`src/parser/`**: Verify canonical ID normalization (`sid_then_scoped_sid_then_guid`, lowercase GUIDs, no guessing), edge directionality per ADR-0002, provenance integrity, host access inference per ADR-0003, and `process_records` error policy compliance.
- **`src/engine/`**: Verify non-negative edge costs for Dijkstra, multigraph edge handling, deterministic tie-breaking, comprehensive path reconstruction (`node_ids`, `edge_ids`, `total_cost`, `profile`), and graceful handling of disconnected nodes/cycles.
- **`docs/research/` & `docs/adr/`**: Verify technical claim alignment with code/contract, explicitly stated assumptions, complete ADR format, and fulfillment of linked issue criteria.
- **`tests/` & `data/samples/`**: Verify coverage of the 8 Milestone 1 edge kinds, edge cases, clear labeling of synthetic fixtures, and strict absence of real AD customer data or secrets.
