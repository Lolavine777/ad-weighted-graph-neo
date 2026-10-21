# Issue #80 lineage representation boundary

> Updated by ADR-0011 / issue #92: the Contract 1.1.0 representation below
> is now implemented. The original Contract 1.0.0 restriction remains the
> migration rule for legacy direct-edge graphs.

This note narrows the serialization claims in `host-access-semantics-audit.md` after review of PR #90 against Graph Contract 1.0.0; ADR-0011 records the Contract 1.1.0 successor.

## Decision

Issue #80 establishes the **semantic requirement** that nested-membership and GPO-derived positive host-access relationships are only trustworthy when the derivation is auditable. Contract 1.0.0 could not serialize that ordered derivation path; Contract 1.1.0 now does so under ADR-0011.

Contract 1.2.0 retains the 1.1.0 derivation representation unchanged and adds the independent per-provenance collection-time status defined by ADR-0012.

Contract 1.0.0 constraints were:

- `edge_optional: []`;
- edge provenance is an unordered collection of raw evidence records;
- `NormalizedRecord.evidence_lineage` from #84 is internal normalized-record state, not a canonical Graph JSON lineage schema.

The successor Contract 1.1.0 resolves the serialization gap. Therefore:

1. An unordered edge `provenance` bag MUST NOT be described as a complete ordered derivation lineage; use `edge.derivation` for Contract 1.1.0. CanRDP lineage format 1.1.0 adds named, evidence-referenced conditions for RDU membership, effective allow, and known absence of effective deny.
2. #92 owns the versioned canonical representation for derived-edge lineage,
   now provided by Contract 1.1.0 and ADR-0011.
3. #45 may implement/retain derivation evidence internally; Contract 1.1.0
   permits emission only after the ordered lineage is serialized and validated.
4. Direct host-access edges backed by direct positive primitives are not blocked by #92.
5. All semantic conclusions from #80 remain unchanged: disabled-state preservation, `CanRDP` composite AND rule with deny precedence, tri-state collection semantics, runtime/service separation, host-bound `AdminTo`, and `HasSession` session-observation semantics.

## Supersession rule

Where `host-access-semantics-audit.md` says that a derived edge "retains complete derivation lineage" or equivalent wording, read it as:

> the inference result must retain sufficient ordered derivation evidence for auditability, while canonical Graph serialization of that ordered lineage is deferred to #92.

This note is a scope clarification, not a change to the structural relationship semantics decided by #80.

Refs #80, #90, #92, #45, #84, ADR-0003, ADR-0008, ADR-0009.
