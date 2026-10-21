# ADR-0012: Canonical collection-time status

- Ngày: 2026-09-24
- Trạng thái: Accepted
- Người đề xuất: @nairyuuu (Codex)
- Reviewer: @Lolavine777
- Issue / PR: Refs #97, #91, #92

## Bối cảnh

Graph Contract 1.0.0 and 1.1.0 preserve a timestamp but do not say how that time was
established. That loses the `TimeProvenancePolicy` status produced by #91 and can make
an assumed timestamp appear observed after canonical serialization. The problem is
record-specific: one edge can aggregate evidence records with different time origins.

## Các phương án

| Phương án | Lợi ích | Chi phí / hạn chế | Bằng chứng |
| --- | --- | --- | --- |
| Để timestamp không kèm status | Không đổi schema | Giữ nguyên lỗi làm assumed trông như observed | #91, #97 |
| Một status tổng hợp ở edge | Thay đổi nhỏ | Mất status khác nhau giữa các provenance record đã aggregate | #44, builder aggregation |
| Status và reason trên từng provenance record | Bảo toàn origin cho từng evidence; tách khỏi lineage | Cần successor contract và migration | #91, #92, #97 |

## Quyết định và hệ quả

Graph Contract 1.2.0 adds `timestamp_status` to each canonical provenance record and
allows an optional `time_provenance_reason` on that same record. Timestamp status is
evidence-level, not edge-level, so duplicate edge evidence retains its own time origin.
The timestamp value remains unchanged and status is never inferred from its presence.

The accepted #91 vocabulary is retained: `observed`, `assumed`, `derived`, and
`externally_evidenced`. `derived` and `externally_evidenced` require the non-empty
reason already required by `TimeProvenancePolicy`; `assumed` may carry its supplied
reason. Reasons are copied from the actual policy input and are not fabricated.
`unknown_legacy` is a canonical migration state for records whose origin was not
serialized; it is not a loader policy status. New builder output uses this explicit
state when legacy or manually constructed raw provenance has no status.

For Contract 1.0.0 and 1.1.0 graphs, a missing `timestamp_status` remains absent on the
wire and means `unknown_legacy`. Loaders do not infer observed status. These graphs
remain loadable and serializable as their original versions; the current serializer
emits Contract 1.2.0 for newly built graphs. A 1.0.0 graph still cannot contain
`derivation`; 1.1.0 derivation remains valid and unchanged.

### Quan hệ với ADR-0011 và ranh giới

`timestamp_status` and `time_provenance_reason` are fields of each provenance record.
They do not modify `edge.derivation`, its ordered steps, IDs, or evidence references.
The combined 1.2.0 contract retains ADR-0011's 1.1.0 derivation representation as-is.
Time provenance describes collection-time origin; it does not describe whether an edge
is direct or derived. An edge may therefore have derived structural lineage and observed
source time, or be direct and have assumed source time.

This decision consumes #91/#95 loader policy without changing null-time resolution,
assumption permission, or source-manifest values. It does not add #81 telemetry,
ObservedActivity, host-access semantics, or weighting to structural edges.

## Kiểm chứng và điều kiện xem lại

- Canonical provenance validation rejects missing/invalid status in Contract 1.2.0 and
  missing reasons for `derived` or `externally_evidenced`.
- JSON serialization is deterministic; deserialization preserves status and reason.
- Independent provenance records on an aggregated edge retain separate statuses.
- The repository must keep legacy fixtures statusless and document their uncertainty.
- Cross-review is required before downstream consumers rely on this successor contract.
