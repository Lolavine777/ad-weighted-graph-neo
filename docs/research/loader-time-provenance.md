# Loader Time-Provenance Policy and Graph Contract Incompatibility Analysis

References: Refs #91, #97; follows ADR-0007, Issue #78, PR #89, and [docs/snapshot-manifest.md](../snapshot-manifest.md).
Status: Normative technical policy for Milestone 2 snapshot loaders.
Maintainers: @Lolavine777 (Author), @nairyuuu (Reviewer).

---

## 1. Context and Problem Statement

The `SEAMLESS.INTERNAL` snapshot provides the primary enterprise-scale synthetic Active Directory topology for Milestone 2.
Under PR #89 and [docs/research/provenance-audit.md](provenance-audit.md), source metadata was audited against raw bytes.
SharpHound formats JSON export filenames using the local system clock (`DateTime.Now.ToString("yyyyMMddHHmmss")`) of the collection host.
Because the raw JSON export envelopes contain no timezone offset or UTC declaration, the exact UTC collection time is unverified.
Per [docs/snapshot-manifest.md](../snapshot-manifest.md), filename timestamps must never be assumed as UTC without explicit timezone evidence.
Consequently, `seamless-raw-v1.json` accurately set `collected_at: null` to represent this unknown collection time.

However, the graph contract requires every traversable edge to carry an audit provenance timestamp matching UTC regex `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`.
Prior to this policy, `ManifestRawDataLoader` raised `ManifestError` whenever `collected_at` was null.
This prevented downstream parser and graph builder tasks (#44, #45, #47) from ingesting SEAMLESS while respecting manifest-backed provenance.
This document formalizes the loader time-provenance policy, records the design choices, and logs the architectural incompatibility with Graph Contract 1.0.0.

---

## 2. Core Invariants

The loader time-provenance policy strictly preserves eight core invariants:

1. `collected_at: null` in a snapshot manifest means collection time is unknown.
2. Never invent a UTC timestamp and write it back into raw manifest truth.
3. Graph Contract 1.0.0 requires a provenance timestamp, so the loader boundary needs an explicit policy.
4. Unknown provenance information must remain distinguishable from known provenance.
5. Policy must be explicit, deterministic, and auditable.
6. No silent fallback based on current clock, file mtime, git commit timestamp, or arbitrary epoch.
7. A caller that has no approved policy for unknown collection time must fail closed.
8. Any adapter or default policy must make its provenance semantics explicit rather than pretending it is the original collection timestamp.

---

## 3. Technical Policy Design

### 3.1. Explicit `TimeProvenancePolicy`

`ManifestRawDataLoader` accepts an optional `time_policy` parameter of type `TimeProvenancePolicy`:

- **Fail-closed default:** When `time_policy` is `None`, any snapshot envelope with missing collection time raises `ManifestError`.
- **Fixed policy (`TimeProvenancePolicy.fixed`):** Uses an explicit, caller-provided UTC timestamp.
- **Semantic calendar validation:** Timestamps are validated against UTC regex `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` and verified as real calendar dates via `datetime.strptime(..., "%Y-%m-%dT%H:%M:%SZ")`.
  Syntactically valid but impossible dates (such as `2021-02-30T25:99:99Z` or `2021-04-31T00:00:00Z`) are strictly rejected.
- **Bounded status vocabulary (`TimeProvenanceStatus`, `TimeProvenanceStatusLiteral`):** Free-form caller tokens are forbidden.
  Status must belong to `TimeProvenanceStatus`: `observed`, `externally_evidenced`, `derived`, or `assumed`.
  The public typed dictionary `RawProvenance` strictly types `time_provenance` as `TimeProvenanceStatusLiteral` to prevent arbitrary strings.
- **Auditability requirement for stronger statuses:** Policy declarations with `externally_evidenced` or `derived` status represent stronger evidentiary claims than `assumed`.
  They strictly require a non-empty `reason` or evidence reference upon instantiation, supported by dedicated factory methods `TimeProvenancePolicy.externally_evidenced` and `TimeProvenancePolicy.derived`.
- **Anti-masquerading invariant:** A policy status cannot be `observed`.
  Normalization trims whitespace and casefolds before checking, preventing bypasses such as `Observed`, `OBSERVED`, or ` observed `.
- **Deterministic identity token:** Policy identity in `ManifestRawDataLoader.execution_identity["time_policy"]` reflects policy parameters (`fixed:<status>:<timestamp>[:<reason>]`), ensuring distinct policies produce distinct execution identities.

### 3.2. Distinguishable Occurrence Provenance and Clean Model Boundary

In `src/parser/__init__.py`, raw occurrence provenance and canonical graph provenance are strictly decoupled:
- `RawProvenance`: Retains loader metadata before assessment and normalization, including `snapshot_id`, `record_locator`, and `time_provenance: NotRequired[TimeProvenanceStatusLiteral]`.
- `Provenance`: Models canonical edge and assessment evidence. In Contract 1.2.0 it preserves `timestamp_status` and an optional policy-supplied `time_provenance_reason` in addition to the audit fields.
- `Provenance` does not inherit from `RawProvenance`, ensuring that raw loader fields (`snapshot_id`, `record_locator`, `time_provenance`) cannot leak into serialized graph edges.
- When collection time is evidenced directly by the manifest, `time_provenance` is set to `TimeProvenanceStatus.OBSERVED.value`.
- When collection time is resolved through a policy, `time_provenance` is set to the policy status (for example, `TimeProvenanceStatus.ASSUMED.value`).
- Callers and normalizers can unambiguously inspect `record.provenance["time_provenance"]` to determine if the timestamp is verified source truth or an assumed baseline.

### 3.3. Collector Envelope and Encoding Tolerance

To allow robust ingestion of real BloodHound v3 snapshots (including SEAMLESS):
- `ManifestRawDataLoader._read_json` strips UTF-8 byte-order marks (`\xef\xbb\xbf`) prior to JSON deserialization.
- `ManifestRawDataLoader._validate_envelope` accepts both BloodHound v4/v6 layouts (`payload["data"]`) and BloodHound v3 layouts (`payload[meta["type"]]`).
- Occurrence locators reflect the envelope layout: `#/data/{index}` for v4/v6 or `#/{kind}/{index}` for v3.

---

## 4. Architectural Incompatibility with Graph Contract 1.0.0

An architectural limitation exists at the boundary between raw occurrences and serialized graph edges:

1. `Graph Contract 1.0.0` (`configs/contract.yml`) froze the original schema for edge provenance:
   - Required fields: `raw_file`, `collector`, `timestamp`, `evidence_type`.
   - Optional fields: `record_id`, `attribute`.
   - Schema validator (`scripts/check_contract.py`) rejects any undeclared fields on serialized edge provenance.
2. Graph Contract 1.0.0 and 1.1.0 have no declared field on edge provenance to indicate whether an edge timestamp was assumed rather than observed.
3. A builder that omitted this distinction could make an assumed timestamp from a snapshot like SEAMLESS look observed.
4. Contract 1.2.0 / ADR-0012 resolve this gap with per-record `timestamp_status` and an optional supplied `time_provenance_reason`.

### Decision on Schema Integrity and Scope

Per guidance for Issue #91, Graph Contract 1.0.0 was not silently stretched. Successor #97 adds an explicit, versioned canonical representation:
- The distinction is captured at the loader boundary in `RawProvenance.time_provenance` and copied into canonical provenance as `timestamp_status`.
- A policy's supplied reason is preserved as `time_provenance_reason`; it is not synthesized. `derived` and `externally_evidenced` require a non-empty reason, while `assumed` may omit one under #91 policy.
- Each provenance record keeps its own status so edge aggregation cannot merge observed and assumed times into a single edge-level value.
- Graph Contract 1.0.0 and 1.1.0 remain loadable. If their provenance records lack time status, that absence means `unknown_legacy`; it never means observed.
- Merged [PR #95](https://github.com/nairyuuu/ad-weighted-graph/pull/95) satisfies the original loader acceptance criteria of [#91](https://github.com/nairyuuu/ad-weighted-graph/issues/91).
- Canonical serialization of time status was not an acceptance criterion of #91; the earlier requirement to keep #91 open for a contract revision expanded its scope.
- #97 owns canonical time-status serialization and coordinates its successor version with ordered derivation lineage in #92. Time status stays outside `edge.derivation`.
- #91 is closed in its original loader scope. Completion of #97's implementation does not by itself declare #44/#47 E2E ready; other gates remain.

---

## 5. Verification Summary

Regression and acceptance coverage in `tests/test_parser_loader.py` and `tests/test_parser.py` validates:
- Known valid `collected_at` produces `time_provenance: "observed"`.
- Missing `collected_at` without policy fails closed with `ManifestError`.
- Missing `collected_at` with `TimeProvenancePolicy.fixed` marks provenance as `assumed`.
- Anti-masquerading checks reject `observed` under any casing or whitespace variant.
- Unsupported status strings are rejected.
- Stronger statuses (`externally_evidenced`, `derived`) strictly require a non-empty reason or evidence reference upon instantiation.
- Dedicated factory methods `TimeProvenancePolicy.externally_evidenced` and `TimeProvenancePolicy.derived` produce verified, parameter-sensitive identity tokens.
- `TimeProvenanceStatusLiteral` exactly matches the enum vocabulary of `TimeProvenanceStatus`.
- Syntactically valid but impossible calendar timestamps (e.g. Feb 30, April 31, hour 24) are rejected with `ValueError`.
- Malformed timestamps in manifests raise `ManifestError`.
- Repeated loader runs under policy are completely deterministic.
- Execution identity differentiates policies with distinct timestamps or reasons.
- Manifest-to-raw loader integration of `data/samples/manifests/seamless-raw-v1.json` against verified local `data/raw/SEAMLESS` parses 3,369 records across all 6 BloodHound v3 files from manifest-verified bytes; collection time remains explicitly marked `assumed`.
- Local verified execution of SEAMLESS is cleanly distinguished from portable CI coverage via skip guards when gitignored raw bytes are absent.
- Canonical `Provenance` keeps loader-only fields (`snapshot_id`, `record_locator`, and raw `time_provenance`) out of the graph; the canonical status is named `timestamp_status` and carries the loader classification forward.
- Wholesale copying of `RawProvenance` into canonical edge provenance is explicitly detected and rejected by contract validation rules.
