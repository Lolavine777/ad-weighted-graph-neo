# Worklog — 2026-10-07 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#215](https://github.com/nairyuuu/ad-weighted-graph/issues/215) / `feat/215-snapshot-facts` → `develop`, reviewer @Lolavine777 / M3 Week 4
- Thời gian thực tế ước lượng: khoảng 60 phút triển khai, kiểm chứng và bàn giao

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Baseline/scope | Worktree riêng `feat/215-snapshot-facts` từ `origin/develop` `7f2fd72`; đọc #215/comments, #211/#221, #174, #200/#218, #216 | #211 đã merge; extraction độc lập #212/roasting; không sửa worktrees khác |
| Trace + AC mapping | [Snapshot facts API](../research/snapshot-facts-api.md) | Gap nằm ở structural projection và field origins sau normalization |
| Implementation | `build_snapshot`, `SnapshotFacts.lookup`, envelope `snapshot-facts/1`, `EngineGraph.from_snapshot`, semantic view | Không sửa GraphNode/contract/query.py/runtime assumption resolution/ranking |
| Focused tests | `python -m pytest tests/test_snapshot_facts.py -q` | 23 passed; booleans/malformed/empty, duplicates/conflict, scoped identity, origins, immutable copies, transport/binding, skipped nodes, real query/search consumer và explicit private-input SKIP |
| Actual SEAMLESS probe | `python scripts/research/snapshot_facts_probe.py --raw-dir <private-SEAMLESS-root> --code-version ece5bfcaea766257fc79bddc11fbfbe6be1ec1b0` | Hai lượt PASS/output giống nhau: 2.493 Users, 51 has_spn true, 176 dontreqpreauth true; 3.370 nodes / 56.367 edges |
| Full clean regression | `python -m pytest -q` trên Python 3.14.7, implementation commit `ece5bfc` | 1905 passed, 11 skipped, 48 subtests passed; parser/identity/reconciliation/graph contracts và Week 3/4 regressions đều included |
| Quality/contract | ruff check/format, yamllint, check_contract, check_repository, diff check; Compose config với placeholder password | PASS; contract + 2 synthetic fixtures; 463 tracked/unignored files |

## Điều học được / quyết định

Reuse reconciliation: reject known-value conflict, empty không xóa non-empty,
SPN list không tự có union policy. Giữ tất cả representations và provenance của
source có field; không gán provenance của record thiếu field cho fact đã biết.
View immutable, giữ static facts ngoài runtime/state. `enabled` reuse canonical node.

SEAMLESS probe so toàn bộ canonical records, attributes, relationships, assessments
và provenance; raw/normalized không đổi; export/load tới EngineGraph và semantic
view thành công. Digest normalize thứ tự top-level collections theo ID vì builder
và engine sắp edges khác nhau; regression kiểm cả reorder và provenance tampering.
Output chỉ aggregates/digests; private inputs/mappings và SPN values không commit.
Hai lượt tại implementation commit `ece5bfcaea766257fc79bddc11fbfbe6be1ec1b0`
cùng canonical digest `sha256:8dbd074116616a31e6c42ae9fb7f7d5b81c069067fc6d14d65a9d96ec0e500c3`.
has_spn false = 2.442, dontreqpreauth false = 2.317, SPN empty = 2.442;
ba facts đều known cho tất cả 2.493 Users. Đây là snapshot/lookup evidence,
không phải observed attack execution hay exploit-success oracle.
11 skips của full suite: telemetry raw (5), SEAMLESS paths mặc định trong worktree
(3), dataset_b/ad_sampledata (1), điều kiện filesystem Windows (2). Private SEAMLESS
probe riêng dùng explicit external raw path đã PASS; không thay skipped loader tests
bằng synthetic claim. Lần full suite trước commit có ba CLI failures do source
provenance guard; clean committed rerun ở trên đã pass cả ba, không waive guard.

Giữ [rationale Service/SPN defer](../research/snapshot-facts-api.md): snapshot chưa
có independent service/endpoint inventory. Xem xét lại khi có inventory/provenance,
shared entity policies/relations cho nhiều techniques, hoặc traversal cần service
entity. Đây là defer, không cấm vĩnh viễn.

## Trở ngại và việc kế tiếp

1. Actual probe và clean regression đã pin ở `ece5bfc`; chờ CI exact PR head và human acceptance.
2. Tạo PR base develop, Refs #215, request @Lolavine777 cross-review; chưa merge/đóng issue.
3. #216/AS-REP issue riêng consume API đã document; delegation/encryption cần review
   validator/reconciliation rule khi mở scope. Parser CLI graph-only chưa transport
   facts; persisted support qua envelope API, không claim graph-only có static facts.
