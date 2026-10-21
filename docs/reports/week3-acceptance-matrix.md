# Ma trận nghiệm thu Week 3 - TTS A / TTS B

## Current-state amendment - 2026-10-06

Final release-consuming raw search/bridge/ranking đã accepted qua #182; #155/#180 đã closed.
Lượt A dùng integrated `develop@891bda0001b9958e712cff54045f651273b43fd0`, CPython 3.14.2/Linux, existing harness `--require-complete` cho cùng 8 case IDs, hai lượt fresh outputs.
Lượt B dùng cùng integrated `develop@891bda0001b9958e712cff54045f651273b43fd0`, CPython 3.14.7/Windows, existing harness `reproduce_legacy_reconciliation.py` trên checkout sạch để hoàn thành fresh Legacy replay và final revision binding (exit code 0 PASS, comparator CLI exit 2, exact sets khớp tuyệt đối accepted #196).
[Final handoff](week3-final-handoff.md) và [manifest actual E2E](../../reports/research/week3-final-handoff.json) lưu verdict, exact output digests, designated decisions, oracle/frontier/Min-Effort, Legacy replay binding và caps.
Search A positive vẫn truncated tại 60.000 expansions; không claim exhaustive/global optimum.
Reconciliation #47 và clean A/B reproduction #196 đã accepted/closed; final package binding #48/#158 đã hoàn tất và B đã chấp thuận package.
Các cột `not_run` và catalog 0.2 dưới đây ghi đúng lượt supplied replay ngày 2026-10-03, không phải trạng thái current harness.

## Checkpoint supplied replay - 2026-10-03, historical

Refs #177, #155, #48, #158; reviewer: @nairyuuu (B).
Đây là kiểm chứng release/supplied candidates trên engine hiện hành và kỳ vọng để B chạy search E2E.
Không có verdict toàn luồng raw → parser → bounded search → adapter → rank trong lượt A này.

## Revision, đầu vào và tái lập

- Engine revision: `d8e0b28be2afd5b1807082283efd4db01fad3240`, fetched từ `origin/develop` trước khi tạo branch.
- Runtime thực chạy: CPython 3.14.7, macOS arm64; dependencies theo `requirements-dev.txt` và `requirements.txt`.
- Graph Contract 1.3.0; semantic catalog 0.2; ranking/release schema 1.0.0; scenario 1.1.0.
- Release bất biến: [reviewed-release.json](../research/ratings/week3-closeout/reviewed-release.json), canonical digest `sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358`.
- Snapshot: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; raw manifest [seamless-raw-v1.json](../../data/samples/manifests/seamless-raw-v1.json).
- Oracle đã pin: [validation-summary.json](../research/ratings/week3-closeout/validation-summary.json); manifest pin canonical digest của object này.
- [Machine-readable manifest](../../tests/fixtures/ranking/week3_acceptance_cases.json) chứa case IDs, query/scenario, bindings/locators, input/overlay/output digests, expected/actual và boundary B cần chạy.
- [Runnable check](../../tests/test_week3_acceptance_manifest.py) kiểm SHA-256 byte của release/requirements/dependencies và canonical digest của raw manifest/oracle, rồi verify release trước khi copy từng projection, apply named overlays và gọi canonical engine.

`recorded_provenance` giữ base revision, Python/platform và installed distributions của lần nghiệm thu gốc; replay không xác minh chúng với checkout/runtime hiện tại.
Các digest ngoài `recorded_provenance` được runnable check xác minh từ file hiện có.
`.gitattributes` cố định LF cho release và requirements để byte pins nhất quán trên Linux/macOS/Windows; đổi nội dung cần cập nhật pin sau khi review.

Chạy từ root repo với `.venv` Python 3.14; tạo thư mục ignored trước lệnh validate:

```bash
mkdir -p reports/generated/week3-177
.venv/bin/python scripts/research/reviewed_parameter_release.py validate \
  --release docs/research/ratings/week3-closeout/reviewed-release.json \
  --output reports/generated/week3-177/validation.json
.venv/bin/python tests/test_week3_acceptance_manifest.py
.venv/bin/python -m pytest tests/test_week3_acceptance_manifest.py -q
for case_input in reports/generated/week3-177/w3-*-input.json; do
  .venv/bin/python -m src.engine.ranking.cli --input "$case_input" \
    --output "${case_input%-input.json}-cli-result.json"
done
.venv/bin/python -m pytest tests/test_engine_path_ranking_conformance.py -q
```

`validate` đi qua `verify_release` → `export_release` replay declarations → `evaluate_selected` → `analytical_expectations` và `PathRankingEngine.evaluate`, rồi chạy 21 probes/24 outcomes.
Runnable check dùng trực tiếp `query_projections.source_a/source_b`, kiểm oracle/manifest, ordered actions/routes, work program/basis, target/success event và JSON rational roundtrip.
CLI đi qua `src.engine.ranking.cli.run_ranking_cli` → cùng `PathRankingEngine.evaluate`; không gọi generator.
Full inputs/results ở `reports/generated/week3-177/` ignored; repo chỉ lưu references và sanitized summaries.

## Expected và actual positive

| Query / chương trình | P expected = actual | C | I | Kết quả supplied set |
| --- | --- | ---: | --- | --- |
| Source A / `cand_seamless_01_direct_lidia` | `[9/40,8379/10000]` | 2 | High | Frontier; Min-Effort winner |
| Source A / `cand_seamless_02_alt_vajer_ollie` | `[81/800,7800849/10000000]` | 3 | High | Frontier; incomparable với Lidia |
| Source B / `cand_seamless_source_b_01_ollie` | `[9/40,8379/10000]` | 2 | High | Frontier; Min-Effort winner của query riêng |

Source A/B là điểm xuất phát, khác người chấm A/B.
Query A có foothold SID suffix `4131`, B có suffix `4157`; cùng target suffix `1000`, success event `terminal_compromise_seamless_dc`, goal predicate `admin_control_badblood`.
Ordered action IDs/programs được pin trong manifest; full actor/target, scope binding, structural edge IDs/locators và parameter basis dẫn về projection bất biến.
Passive closure không tạo work unit; persistent units được đếm một lần dù nhiều actions cùng tham chiếu.

| Artifact | Digest thực chạy |
| --- | --- |
| Source A canonical result | `sha256:65a0f10588a783a72b4d77a6e1901cf22e9d3e8463bc35b9d7485d280fad1680` |
| Source B canonical result | `sha256:95377e1c907b1964f039b9c961d0d105a38e2de5f9c11e18bad02ec46c7c4a02` |
| Validation report content (loại trường `report_digest`) | `sha256:4906ed68baae9ee86db297dae71cf70e1a39520c828cdce0a6c31f877d3bc834` |
| Full validation file bytes | `sha256:99ea60c98a4d1ed06e7feb8d436135d3298b458c26ea3fee4a213049fb4ec912` |

Validation report content/file bytes khớp pins khi phát hành; không có numeric hoặc wire/metadata delta.
Canonical digest dùng `scripts.research.reviewed_parameter_release.digest` với JSON sorted keys/compact separators.
Trường self-digest `report_digest` băm report content trước khi thêm chính trường này; full report object gồm trường đó có digest `sha256:06679b3ece0a00a82f953f7b5b90b5964a0adb48e7042cf62519f4473e09c096`.
File-byte SHA-256 có thể đổi khi newline/format đổi.
21 probes/24 outcomes vẫn có 0 đổi frontier, 0 đổi relations, 0 đổi winner identity; 6 outcomes đổi giá trị Min-Effort.

## False, missing và unknown

Overlay áp dụng RFC 6902 add/remove vào deep copy sau `verify_release`; không sửa/reseal release gốc, không thêm structural evidence hoặc ratings.
`case_id` và `overlaid_digest` định danh variant; query/scenario/rating bindings gốc giữ nguyên để xác định giả định bị rút/phủ định.
Variants là counterfactual kiểm nghiệm, không phải quan sát SEAMLESS về quyền hoặc dịch vụ thật.

| Case ID | Predicate / authoritative layer / overlay | Expected = actual replay | Search E2E |
| --- | --- | --- | --- |
| `w3-source-a-positive` | Projection A nguyên bản | 2 eligible; frontier cả hai; Min-Effort Lidia, C=2 | **not_run** |
| `w3-source-b-positive` | Projection B nguyên bản | 1 eligible; Min-Effort Ollie, C=2 | **not_run** |
| `w3-source-a-known-false` | `directory_write_allowed_lidia`, L3; thêm false, giữ true assumption | Lidia blocked, C/P=null; alternative eligible; Min-Effort alternative, C=3 | **not_run** |
| `w3-source-b-known-false` | `directory_write_allowed_ollie`, L3; thêm false, giữ true assumption | Ollie blocked, C/P=null; frontier rỗng; Min-Effort=null | **not_run** |
| `w3-source-a-runtime-unknown` | `directory_write_allowed_lidia`, L3; bỏ assumption, thêm unknown | Lidia unknown, C/P=null; alternative eligible, C=3 | **not_run** |
| `w3-source-b-runtime-unknown` | `directory_write_allowed_ollie`, L3; bỏ assumption, thêm unknown | Ollie unknown, C/P=null; frontier rỗng; Min-Effort=null | **not_run** |
| `w3-source-a-structural-missing` | `genericall_tstwvir_lidia`, L1; bỏ provenance reference của observed true | Lidia unknown với `missing_structural_provenance`; alternative eligible | **not_run** |
| `w3-source-a-telemetry-missing` | `enabled_lidia`, L2; bỏ observed enabled | Lidia unknown với `missing_telemetry`; alternative eligible | **not_run** |

False có disposition `observed_false_veto`; runtime unknown có `declared_unknown_fact`.
Affected candidates có diagnostic `blocked`/`unknown` và `likelihood_unrated`, effort/likelihood null; rated impact High vẫn giữ làm basis, không làm candidate eligible.
Negative eligibility kiểm riêng theo authoritative layer/veto/unknown contract; không lấy positive arithmetic oracle để suy eligibility.

Manifest có `search_binding` cho `directory_write_allowed` của `genericall_reset_password` trong [catalog thật](../../configs/attack_semantics.yml).
Tuple key dùng actor/target của `action_reset_lidia` ở A, `action_reset_ollie_from_b` ở B; full SIDs, scope, origin/value/rationale đã có.
B resolve false trước `RuntimeContext`: context từ chối duplicate keys mâu thuẫn, nên giữ ledger true/false gốc trong audit rồi truyền một typed `RuntimeFact(False, blocked_evidence)` đã phân giải vào search.
Unknown dùng typed `RuntimeFact(None, unknown)` hoặc bỏ key có trace lý do; không đổi thành false/default true.
Search có thể prune related transition blocked/indeterminate; lưu đúng predicate/reason, không tạo candidate giả chỉ để có diagnostic.

Với missing structural/telemetry, B phải rút evidence tương ứng ở graph/fact context của search và lưu exact locator/digest của delta.
Query thiếu provenance nhưng graph đầy đủ có thể tái xác lập evidence hợp lệ, nên query-only overlay không đủ để gọi missing-evidence E2E passed.
Lưu base snapshot, variant ID và derived graph digest riêng, không che delta bằng snapshot identity mới.

## Regressions và handoff #155/#48

`regression_references` dẫn 15 pytest node IDs trong [canonical conformance suite](../../tests/test_engine_path_ranking_conformance.py): false/unknown, invalid ordered binding, sparse derived lineage, first-goal/suffix, dominance/tie/incomparability, work dedup/overlap, exact edge hydration và truthful caps/truncation.
`regression_execution` ghi rõ replay không collect/execute chúng; chạy bằng lệnh pytest riêng ở trên hoặc full pytest/CI.
Đó là synthetic regressions, không thay raw/release-consuming E2E.
Chỉ thêm một runnable check nối manifest release vào implementation hiện có; không viết lại evaluator, validator hoặc oracle.

B dùng `generate_attack_paths` với actual `AttackState`/typed `RuntimeContext`, bind ordered actions theo từng step, lấy `coverage_from_search_result`, rồi gọi `evaluate_search_candidates`.
Manifest ghi boundary/CLI bridge; B cung cấp command executable từ raw/parser, actual từng case, output locator/digest và integrated revision.
Candidate IDs của generator có thể khác supplied IDs; so ordered program, actor/target, evidence/scope trước C/P/I/frontier/Min-Effort.
Path mới thiếu full-history rating phải giữ unrated; không gán khoảng của supplied path có prefix khác.

Replay hiện có `search_algorithm=provided_candidate_assessment`, completeness `unspecified_subset`, budget 6; search caps khác null, không có upstream search coverage.
B ghi actual max_paths/max_steps/max_expansions, counters/cap hits/truncation reasons và kiểm cả ranking metadata lẫn Min-Effort coverage.
Empty bounded result không chứng minh toàn đồ thị không có đường; truncated frontier/Min-Effort chỉ mô tả tập đã đánh giá.
Historical replay boundary ở phần này đã được bổ sung bởi final raw E2E hai deterministic runs và clean-checkout reproduction trên `891bda0` trong [final handoff](week3-final-handoff.md).
#47/#196 đã accepted/closed; fresh Legacy replay/final binding và technical acceptance #48/#158 của B đã hoàn tất, comparator CLI thật giữ `NOT_MEASURABLE` / exit 2.
