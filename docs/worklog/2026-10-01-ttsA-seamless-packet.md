# Worklog - 2026-10-01 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) / [PR #159](https://github.com/nairyuuu/ad-weighted-graph/pull/159), branch `docs/143-seamless-calibration-packet` / M2-A Week 3
- Thời gian thực tế ước lượng: Không đo thời lượng phiên sửa; không suy giờ làm từ số lệnh hoặc thời gian test.

## Kết quả và bằng chứng

Worklog này sửa mô tả của lượt trước theo artifacts và kết quả đã thực chạy.
Review cần xử lý là [sáu findings tại reviewed head](https://github.com/nairyuuu/ad-weighted-graph/pull/159#issuecomment-5927446107) `4822e95045e7ebbe99316ddb56ac1b1d4e2dc30f`.
Đã đọc CONTRIBUTING, instructions docs/tests, #143/#158 và comments, governance/interface/catalog, current PR metadata và remote develop.
`git fetch origin develop docs/143-seamless-calibration-packet` xác nhận develop `8c15993b2ac2ed491eda5dc4655e08e2eb478ec1`, PR head đúng reviewed head lúc bắt đầu.
Merge #157 là `8c15993`; `49f591f` là merge develop vào branch structural-validation, không phải merge PR #157.
Bảng kết quả đầu ghi lượt repair sáu findings tại commits `ceb2233`/`8880c77`; lượt review tiếp theo được ghi riêng phía dưới.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Reproduce trước sửa qua wire flow | `.venv/bin/python` probe gọi `execute_ranking_roundtrip`; local `reports/generated/pr159-review-reproduction.json` | Base và synthetic false authentication/endpoint probe đều trả cả hai candidates feasible, frontier rỗng; xác nhận missing action prerequisites |
| Red/green regression | `.venv/bin/python -m pytest tests/test_seamless_packet.py -q`; local red log | 37 cases ban đầu failed vì required runtime gates bị bỏ qua và session falsely negative; sau binding/session fix cùng 37 cases passed; bộ cuối thêm route/sheets/conditional/positive checks |
| 1. Correct conditional questions | [packet Mục 6](../research/seamless-scenario-rating-packet.md), [rater 1](../../tests/fixtures/ranking/seamless_rater_1.json), [rater 2](../../tests/fixtures/ranking/seamless_rater_2.json) | Mọi row có outcome, previous-success history và F/S binding; prefix là lookup key cho q_i; Source B query riêng; ví dụ synthetic `4/5 * 3/4 * 1/2 = 3/10`, không nhân cumulative thành `18/125` |
| 2. Complete action bindings | [Source A query](../../tests/fixtures/ranking/seamless_query_input.json), [Source B query](../../tests/fixtures/ranking/seamless_source_b_query_input.json), packet Mục 3-4 | Primary Microsoft sources, structure/rule/requires/adds/work/route table; reset policy/write, token/security-group/scope usability, KDC/auth, WinRM auth/endpoint/admin context; computer GenericAll không suy host execution |
| 3. Facts and layers | Packet Mục 3, scenario/session tests | Bỏ `session_badblood=false` unsupported; runtime session unknown Layer 3; buckets tách khỏi 3 authoritative layers; enabled Layer 2, ACE/member Layer 1; synthetic negatives có provenance/classification riêng |
| 4. Agreement policy | [governance 1.0.0 Proposed](../research/evidence-rating-governance.md), packet Mục 7, disposition | Kappa reference 0.70 khi defined; observed agreement/confusion/raw ratings, small-sample/degenerate disposition; likelihood IoU 0.50/width warning; effort delta <=1/rubric/overlap; không dùng consensus che raw disagreement |
| 5. Separate gates | [acceptance disposition Mục 2](../research/path-ranking-acceptance-disposition.md), [ADR-0013](../adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md), [weighting-direction](../research/weighting-direction.md) | Cùng status matrix; design/interface Proposed chờ explicit A/B sign-off, có thể accept trước ratings/engine; parameters/integration/reconciliation/E2E độc lập; scalable search ngoài scope lượt này |
| 6. Canonical evidence and handoff | [evidence helper](../../scripts/research/seamless_packet_evidence.py), [manifest](../../tests/fixtures/ranking/seamless_evidence_manifest.json), packet Mục 2/8 | 6 raw files manifest-verified; 3 routes với 3/5/3 structural edges; 14 raw locators và positive canonical provenance verified; 78 expected/actual scenario cases PASS; hai sheets độc lập đầy đủ records |
| Independent code review | Read-only reviewer và swapped-locator regression tests | Review tìm ra helper chưa khóa predicate với actor/target/property-owning node; thêm explicit predicate bindings; hai cases swapped ACE/enabled ban đầu failed DID NOT RAISE, sau sửa passed; re-review xác nhận không còn technical blockers trong repair, B review/acceptance vẫn pending |
| Focused checks | `.venv/bin/python -m pytest tests/test_seamless_packet.py tests/test_path_ranking_interface.py -q` | 87 passed; synthetic sheet completion kiểm tra existing reconciliation functions, không thay pending sheets |
| Full suite | `.venv/bin/python -m pytest -q` | 941 passed, 1 skipped (Windows junction test), 48 subtests passed, 32.32s |
| Quality/contract/repository | `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/yamllint .`, `.venv/bin/python scripts/check_contract.py`, `.venv/bin/python scripts/check_repository.py`, `git diff --check` | PASS; 183 Python files formatted; contract + 2 synthetic fixtures valid; repository 256 tracked/unignored files; không sửa CHANGELOG/generated source hoặc engine/parser B |

### Code, graph và policy pins

Parser code pin là reviewed head `4822e95045e7ebbe99316ddb56ac1b1d4e2dc30f`; src/parser, src/data, contract và research adapter không bị sửa trong repair.
Canonical pipeline dùng manifest-backed loader -> BloodHound v3 adapter -> identity normalization/reconciliation -> direct builder/inference -> unit weights -> Graph Contract validation/serialization.
Export có 3,370 nodes, 53,774 edges và 3 unknown assessments, warnings/errors 0; đây là observation của run, không phải acceptance criterion hoặc search completeness.
`created_at=2026-10-01T00:00:00Z` cố định; [collection-time policy](../../tests/fixtures/ranking/seamless_time_policy.json) dùng `2021-09-20T18:59:58Z` với status assumed từ filename convention.
Manifest collection time vẫn null; không gọi filename/export time là collection observation.
Canonical graph byte digest `sha256:5781a365b3a44c57bc2b30f11a98d1f60242ca515ceca411e9c6e34cefd5518a`.
Hai exports cùng pin/policy/time byte-identical qua `cmp`; đã chạy thêm export từ clean detached worktree ở parser pin và có cùng bytes.
Graph/raw outputs chỉ nằm ở ignored local directories.
Evidence manifest ghi execution code revision, file digests của helper/adapter/queries/expected/sheets/dependencies/policy và case matrix; GitHub final head chứa artifact được request B re-review.

### Reproduction commands đã thực chạy

```bash
.venv/bin/python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
.venv/bin/python -m src.parser.cli \
  --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 \
  --raw-dir data/raw/SEAMLESS --profile unit --error-policy fail_fast \
  --time-policy tests/fixtures/ranking/seamless_time_policy.json \
  --created-at 2026-10-01T00:00:00Z \
  --output data/processed/pr159-canonical-graph.json --summary
.venv/bin/python -m scripts.research.seamless_packet_evidence \
  --graph data/processed/pr159-canonical-graph.json --raw-dir data/raw/SEAMLESS \
  --output reports/generated/pr159-packet-evidence.json
.venv/bin/python -m pytest tests/test_seamless_packet.py tests/test_path_ranking_interface.py -q
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/yamllint .
.venv/bin/python scripts/check_contract.py
.venv/bin/python scripts/check_repository.py
git diff --check
```

Parser command đầu đã chạy khi HEAD còn ở parser pin; để tái lập sau repair dùng exact clean-worktree commands trong [packet Mục 8](../research/seamless-scenario-rating-packet.md).
Đã chạy đúng workflow checkout riêng với venv/root raw/time policy của PR và compare output, không chỉ viết commands đề xuất.
`raw_path_probe.py` là research projection ba files, không phải verification đủ computer-target ACL; full-route evidence của lượt sửa đến từ canonical pipeline.

### Luồng kỹ thuật: người làm và hàm/script

| Bước | Phần người làm / còn pending | Phần tự động đã thực chạy |
| --- | --- | --- |
| Scope và action mapping | A chuẩn bị routes/bindings/assumptions; B review pending | Fixture metadata/canonical aliases/record bindings được kiểm tra qua replay |
| Structure | Không thêm missing edge để tạo đường | Verify toàn manifest, official parser export, raw locators/provenance và route segments |
| Feasibility | Declared scenario assumptions là hypotheses chưa có sign-off | Sequential requires/effects replay; false/missing variants blocked/unknown, evidence_only disallows assumptions |
| Ratings | A/B hoặc hai người phù hợp đánh giá độc lập impact/conditional/effort, năng lực/phạm vi, rationale và review trace; actual ratings chưa thực hiện, chữ ký tùy chọn | Chỉ kiểm tra cơ chế bằng synthetic copies; helpers không xác minh chữ ký/chứng chỉ hoặc competence |
| Parameters | Accepted design + adequate ratings/basis + overlap/reconciliation và B review; chưa thực hiện | Không tạo bundle, sensitivity trên SEAMLESS ratings hoặc calibrated flag |
| Integration | B sở hữu final #145->#155 adapter/runtime; A/B nghiệm thu #48 còn pending | Research roundtrip có expected/actual; không gọi nó là integrated product E2E |

## Điều học được / quyết định

Likelihood row là `q_i = P(E_i succeeds | foothold, scenario, all previous events succeeded)`.
Prefix chứa current work ID để lookup factor, không phải xác suất tích lũy của prefix.
`scenario-seamless-host-to-dc` và `terminal_compromise_seamless_dc` là IDs đúng của Source A fixture; Source B có `scenario-seamless-source-b-to-dc` riêng.
Cả hai scope cùng terminal DC event nhưng không cùng foothold hoặc conditional history.

Có 9 unique canonical active work IDs, không phải 5 ID placeholder hoặc psexec units.
Consequence scale là Low/Medium/High/Critical với business rationale pending, không phải CIA supremum C0-C3.
Source A Candidate 1 có 3 active units/4 bound actions/3 structural edges; Candidate 2 có 5 active units/7 bound actions/5 structural edges; Source B có 3/4/3 tương ứng.
Group closures có conditional applicability; không cho probability/effort mặc định để che false/unknown prerequisite.
Computer-object GenericAll giữ trong evidence trace, không là WinRM authorization.

Sự thiếu collected HasSession chỉ hạn chế structural materialization, không phủ định runtime session.
Kappa của synthetic single-target `['Critical']` / `['Critical']` thực trả null, `degenerate_zero_variance`, observed agreement 1.0 và small-sample warning; không phải kết quả ratings thật.
Governance references 0.70/0.50/delta1 là Proposed policy, không tạo hard gate Kappa defined cho mọi dataset.

Design/interface Proposed vì chưa explicit accepted, không vì phải chờ completed engine hoặc real ratings.
SEAMLESS predictive verdict hiện Insufficient Evidence vì numeric basis thiếu; xem lại theo scope/gates khi evidence thay đổi.
Không tự tick parent gates, close issues, merge hoặc triển khai B-owned engine/search.

## Trở ngại và việc kế tiếp

- B @nairyuuu review exact repaired PR head, technical rules/assumptions và design/interface disposition.
- A/B hoặc hai người phù hợp điền independent sheets độc lập và ghi đúng competence/scope; identity/time/ratings/rationale vẫn null, organization/signature là metadata tùy chọn.
- A + raters + B review raw agreement/overlap/reconciliation và business basis; giữ unrated nếu không đủ căn cứ.
- A tạo versioned bundle, manual/oracle validation và sensitivity sau accepted design + ratings/basis, không dùng synthetic test values làm tham số.
- B hoàn thiện bounded integration #145/#155; A/B nghiệm thu product E2E/reconciliation/clean-checkout package #48 riêng.
- #143/#42/#48 tiếp tục mở tới parent hard gates; request B review, không merge.

## Lượt xử lý review vòng 2 - workflow nội bộ

Đã đọc [B request changes](https://github.com/nairyuuu/ad-weighted-graph/pull/159#pullrequestreview-5377136373), [review vòng 2 tại head 8880c77](https://github.com/nairyuuu/ad-weighted-graph/pull/159#issuecomment-5928362061) và current #143/#158.
Clarification được ghi [tại PR](https://github.com/nairyuuu/ad-weighted-graph/pull/159#issuecomment-5927555315): không có dependency tuyển panel ngoài, chứng chỉ hoặc chữ ký; A/B được đánh giá độc lập theo cùng rubric và ghi năng lực/phạm vi thật.
Reproduce qua `execute_ranking_roundtrip`/`decode_ranking_query` xác nhận Query A có 9, Query B có 4 unrated records ghi `pending_expert_panel`; tổng 13 reasons mô tả sai dependency, dù cả ba candidates vẫn feasible dưới assumptions và frontier rỗng.
Hai regression cases mới trên wire-decoded impact và effort inputs failed trên reasons cũ, sau sửa thành `pending_independent_ratings` passed.

Đồng bộ governance 1.0.0 Proposed, ADR-0013, acceptance matrix, SEAMLESS brief, linked synthetic template, weighting-direction, worklog, query fixtures và hai pending sheets.
Sheets khai báo A/B hoặc hai người phù hợp, `external_panel_required=false`, `signature_required=false`; actual rater identity/time/ratings/rationale/signature vẫn null.
Research/LLM-assisted scenario estimates cần verified sources, đúng conditional quantity, basis/provenance/scope/uncertainty/sensitivity và A/B review; technical sources/model confidence không tự chứng minh numeric probability.
Hai prompts/models không là human raters hoặc human agreement; implementation/tests dưới declared assumptions có thể tiếp tục khi human agreement pending.
Lượt này không điền estimates, actual ratings, consensus, signatures hoặc Accepted; không sửa B-owned parser/engine hoặc generated CHANGELOG.

| Kiểm chứng lượt review vòng 2 | Kết quả thực chạy |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_seamless_packet.py tests/test_path_ranking_interface.py -q` | 89 passed, gồm hai red/green workflow regressions và synthetic unsigned-record reconciliation |
| `.venv/bin/python -m pytest -q` | 943 passed, 1 skipped (Windows junction), 48 subtests passed, 33.03s |
| `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/yamllint .`, `.venv/bin/python scripts/check_contract.py`, `.venv/bin/python scripts/check_repository.py`, `git diff --check` | PASS; 183 Python files formatted, contract + 2 synthetic fixtures valid, 256 tracked/unignored files checked |
| `.venv/bin/python -m scripts.research.seamless_packet_evidence --graph data/processed/pr159-canonical-graph.json --raw-dir data/raw/SEAMLESS --output reports/generated/pr159-workflow-evidence.json` | PASS: 3 routes, 14 exact observed locators, 78 expected/actual cases; graph digest không đổi; chạy lại sau commit để pin source và regenerate manifest |
| Content audit | 13 neutral basis reasons; hai sheets giữ actual identity/evaluator/numeric fields null và optional-signature/panel flags false; không có changes trong src/raw/processed/generated CHANGELOG |
| Read-only agent code review | Không còn critical/important blockers trong source diff; reviewer chạy độc lập 89 focused tests và diff check PASS; đây là code review, không phải human rating/agreement hoặc B approval |

Execution manifest pin committed source của lượt này riêng với parser revision/graph digest không đổi; artifact commit sau đó chỉ cập nhật manifest đã regenerate bằng helper, không sửa tay.
Request B re-review exact repaired head; #143/#42/#48 giữ open và PR không merge.
