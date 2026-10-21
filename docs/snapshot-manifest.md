# Snapshot manifest v1

Refs #27; follows the inventory in PR #26. A manifest identifies local input bytes.
It does not validate AD records, collection completeness, or normalized graph edges.

## Schema and identity

The implementation is [src/data/manifest.py](../src/data/manifest.py). The CLI is
[scripts/snapshot_manifest.py](../scripts/snapshot_manifest.py). No additional dependency
is required. Unknown fields, duplicate JSON keys, invalid types, invalid summaries,
noncanonical paths, unsupported versions, and inconsistent snapshot IDs are rejected.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `dataset_id` | Opaque lowercase slug, 1-64 ASCII letters/digits/underscore/hyphen; starts with letter/digit |
| `snapshot_id` | `sha256:` followed by 64 lowercase hexadecimal digits |
| `collector.name` | Nonempty NFC string without control characters or path separators; use `synthetic` for examples |
| `collector.version` | String under the same rules as name, or JSON `null` if unknown |
| `collected_at` | Collection time in UTC `YYYY-MM-DDTHH:MM:SSZ`, or JSON `null` if unknown |
| `files` | Nonempty list sorted by normalized `relative_path` in Unicode code point order |
| `files[].relative_path` | NFC-normalized path relative to snapshot root, with `/` separators |
| `files[].size_bytes` | Nonnegative integer byte count |
| `files[].sha256` | SHA-256 of original file bytes, 64 lowercase hexadecimal digits |
| `files[].collector`, `files[].collected_at` | Optional paired overrides with the same validation as root metadata; required on every file when root collector is `mixed` |
| `summary.file_count` | Number of file entries |
| `summary.total_size_bytes` | Sum of file sizes |

Canonical serialization uses UTF-8 without BOM, literal Unicode, sorted object keys,
compact JSON separators (`,` and `:`), and exactly one final LF. The snapshot ID is
SHA-256 of that serialization with the entire `snapshot_id` field omitted. The final
manifest uses the same serialization with the ID present. Metadata changes produce
a new ID. Absolute root location, file modification times, and generation time are
excluded. Raw bytes are never normalized, including line endings.

Null metadata explicitly means unknown. The CLI requires callers to supply `unknown`
for those values; it never silently invents a version or timestamp. Export schema
version is not collector version. Do not interpret a filename timestamp as UTC unless
the dataset inventory establishes its timezone.

## Snapshot boundaries and portability

Snapshot the original raw directory directly; copying or splitting it is unnecessary.
Dataset A has two collectors and Dataset B has three collection-time groups. For these
mixed collections, set root collector name to `mixed`, version/time to `null`, and
include the actual collector and collection time on every file entry. Per-file metadata
takes precedence over root metadata; never use `mixed` as an edge's collector.
Every regular file under the chosen root is included, irrespective
of extension. An empty directory alone is not an input file; a zero-byte file is valid.

Filesystem paths are converted to `/` and Unicode NFC. Actual filenames containing a
literal backslash are rejected because they are ambiguous across operating systems.
Casefold and NFC collisions are rejected, including directory-prefix collisions.
Absolute/drive/UNC paths, `.`/`..`, empty components, Windows reserved names, trailing
spaces/dots, control characters, invalid Unicode, and Windows-forbidden punctuation
are rejected. Manifest references must already be canonical. Symlinks and Windows
junctions are rejected at the root, in root ancestors, and inside the snapshot.
Non-regular files (for example FIFOs) are rejected.

Generation and verification require an immutable snapshot with no concurrent writers.
Files are read in 1 MiB chunks. File identity, size, and modification time are checked
before and after hashing, and a final traversal detects changes to file membership or
stats. Creation/change time is deliberately excluded because Windows can update that
metadata when a file is opened.
These checks detect ordinary concurrent modifications; they are not a filesystem
snapshot or an access-control boundary against an attacker racing filesystem changes.

## Commands and diagnostics

Run from the repository root using Python 3.14:

```bash
python scripts/snapshot_manifest.py generate data/samples/snapshot-input --output data/processed/demo-manifest.json --dataset-id synthetic-v1 --collector-name synthetic --collector-version 1.0 --collected-at 2026-01-01T00:00:00Z
python scripts/snapshot_manifest.py verify data/samples/snapshot-input data/processed/demo-manifest.json
```

The first command reproduces [the committed synthetic manifest](../data/samples/manifests/synthetic-v1.json)
byte-for-byte on Windows and Linux. Parent output directories must already exist.
Output must be outside the snapshot root. Generation writes a temporary sibling file,
flushes and fsyncs it, and publishes with atomic replacement. Failures before replacement
preserve existing output and clean up the temporary file. This guarantees atomic visibility,
not durability of a directory entry across power loss on every filesystem.

For a mixed raw root, use `--collector-name mixed --collector-version unknown
--collected-at unknown --file-metadata <local-metadata.json>`. The metadata input is a
JSON object mapping every canonical relative path to
`{"collector":{"name":"synthetic","version":"1.0"},"collected_at":"2026-01-01T00:00:00Z"}`.
Missing files, extra paths, and unsupported metadata fields are errors. Keep this input
outside raw roots in ignored storage. It is needed only for generation; verification
uses the metadata already embedded in the manifest. The same information can be passed
as `file_metadata` to `generate_manifest()`.

The CLI emits JSON. Exit `0` means generated/verified, `1` means verification found
discrepancies, and `2` means invalid input, unsafe paths, or an operational error.
Argument usage errors also exit `2` through argparse. Verification reports:

| Status | Meaning |
| --- | --- |
| `added` | File is absent from the manifest |
| `removed` | Manifest file is absent from the root |
| `size_changed` | Byte length differs |
| `checksum_changed` | Original bytes differ, even if size is unchanged |
| `unreadable` | File cannot be opened/read |
| `unstable` | File changed identity or metadata while being read |

A file can have both size and checksum discrepancies. Directory traversal failures
are fatal; inaccessible subtrees are never silently skipped. Diagnostics contain only
relative paths, which can themselves be sensitive and should remain local.

## Parser and provenance boundary

Keep a local registry from `snapshot_id` to the manifest and its local root. Verify
the snapshot before loading it, and keep it immutable throughout parsing. Use
`raw_file_reference(manifest, relative_path)` to construct:

```text
snapshot:<64 lowercase hexadecimal digits>/<canonical relative path>
```

`resolve_reference(manifest, reference)` validates the snapshot ID and file membership
and returns the canonical relative path. This is an opaque audit reference, not a URL;
do not percent-decode it. Use `resolve_snapshot_file(root, manifest, reference)` to
map the canonical reference to the actual filesystem spelling and recheck the selected
file's bytes. For a parser that needs the payload, use
`read_verified_snapshot_file(root, manifest, reference)` so hashing and reading happen
on the same file descriptor and the returned bytes are exactly the bytes checked.
This matters for filenames stored with decomposed Unicode. Keep the root immutable
between whole-snapshot verification and parsing; the helper also detects ordinary
changes while reading.
No absolute root belongs in graph JSON. The existing `Provenance.raw_file` string
supports this form without adding fields to `configs/contract.yml`.

Retain the existing required `collector` and `timestamp` fields in edge provenance.
The timestamp is the known collection time, not manifest generation time.
A manifest with unknown collection time can establish file identity but cannot by itself provide the required edge timestamp.
Manifest schema v1 permits `collected_at: null` when collection metadata is unevidenced.
However, `ManifestRawDataLoader` enforces a stricter consumer requirement on AD JSON export envelopes: a non-null collection timestamp is required to satisfy graph edge provenance.
Non-AD collections, such as independent telemetry CSV event logs, are verified for byte integrity under manifest schema v1 and analyzed without passing through `ManifestRawDataLoader`.
The future collector adapter must obtain that evidence or fail under the parser's file/metadata error policy, never invent a timestamp.

### Activity-level references

Issue #81 keeps telemetry record provenance in the semantic layer. An
`ObservedActivity` uses `TelemetryRecordRef` to retain the manifest dataset ID,
snapshot ID, `raw_file_reference()` result, and a record locator. For the current
CSV corpus, `csv_row` is a 1-based row in the immutable file; a native Windows
EventRecordID is not fabricated when the corpus does not contain one. The
reference is validated against the manifest before it is accepted. This record
reference is not a structural edge provenance record and must not be copied into
`configs/contract.yml` edges.

The activity factory also reads the manifest-selected file through the verified
snapshot helper. A `csv_row` locator must be within the parsed data rows; a
`content_hash` locator is calculated from the canonical parsed row and must match
exactly one row. A syntactically valid but nonexistent or ambiguous locator is
not accepted as activity provenance.

## Privacy and verification scope

Operational manifests default to the ignored `data/processed/` area outside raw roots.
Use opaque dataset IDs and inspect every field before sharing. Filenames can contain
domains/usernames, and metadata may expose internal details; a hash does not sanitize
them. The CLI does not claim to detect all sensitive strings. Do not rename raw files
in place to make a manifest shareable. Keep a sensitive manifest local and share only
an independently reviewed safe artifact. Never commit absolute paths, access locations,
tokens, real identifiers, raw records, or private manifests. Only the synthetic example
and synthetic tests are committed by this change.

Current local bytes establish a new baseline when intentional differences from the
PR #26 inventory are accepted. Generating a manifest records that baseline; it does
not prove identity with the old archive. Preserve the old baseline for historical
comparisons and record the new snapshot ID locally. Verification subsequently checks
the new manifest, rather than silently updating it when inputs change.

Tests reproduce the same committed bytes in the existing Windows/Linux CI matrix.
No raw datasets or private manifests are needed in CI or uploaded as artifacts.
