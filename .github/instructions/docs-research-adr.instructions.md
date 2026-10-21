---
applyTo: "docs/research/**, docs/adr/**"
---
# Review Checklist: Research Docs & ADRs (`docs/research/`, `docs/adr/`)

When reviewing changes to `docs/research/` or `docs/adr/`, verify the following requirements:

1. **Alignment with Contract & Code**:
   - Technical specifications, node/edge naming, and formulas must strictly match `configs/contract.yml` and implementation in `src/`.
   - Any proposed change in data structures or weighting logic must note the corresponding contract version update.

2. **Explicit Assumptions**:
   - Rigorously differentiate between theoretical hypotheses, synthetic simulation baselines, and empirical production findings.
   - Any claim regarding Active Directory internals, BloodHound collector mechanics, or Windows security behaviors must cite
     official documentation, research papers, or reproducible test methodology.

3. **ADR Structure & Standards**:
   - New ADRs must follow `docs/templates/adr.md` (Title, Status, Context, Decision, Consequences, Alternatives Considered).
   - Invariants and trade-offs must be clearly articulated.

4. **Issue Acceptance Criteria Alignment**:
   - Ensure the documentation directly addresses the goals and acceptance criteria of the referenced GitHub issue.
