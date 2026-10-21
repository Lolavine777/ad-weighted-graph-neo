# Worklog - 2026-10-13 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #275, parent #265; dependency #270; Week 5.
- Thời gian thực tế ước lượng: khoảng 35 phút triển khai và kiểm chứng local.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Source adapter/batch/CLI | `src/engine/batch.py`, `python -m src.engine batch` | Implementation và 77 focused tests PASS |
| Full repository tests | `python -m pytest -q` | 2677 passed, 46 skipped, 48 subtests |
| Raw-backed pilot | `reports/research/issue275-seamless-pilot.json` | Full graph, declared 5×3 pilot, checksums trước/sau khớp |
| Tài liệu và replay | `docs/research/week5-source-goal-batch-runner.md` | Commands, transport, budgets/resume và limits được công bố |

Đã triển khai source adapter → public query → destination discovery/source×goal
matrix → source priority/representative, logical/wall budgets, error isolation,
partial/not-run disclosure và digest-checked checkpoint/resume. Entrypoint:
`python -m src.engine batch`; query command chuyển tới CLI public hiện có.
Không thêm search/scoring engine, không adopt #267, không implement Top-K #226
hoặc remediation/viewer.

Executable source đã publish:
`2e4790bb9ad1a62f244275c24862712ef7e9a3b1`. Tree GitHub được đối chiếu bằng
exact Git tree SHA với local source. Base develop `7368cac`; handoff #270 exact
`9b262f9` được staged cùng implementation để chuẩn bị khi dependency chưa merge.
4 schemas, documentation, manifests và expected fixtures/oracles #268 giữ bytes;
reference module/test chỉ format bằng pinned Ruff/Python 3.14. Production runner
dùng chung reference implementation, không copy logic thành hai phiên bản.

Hướng dẫn: `docs/research/week5-source-goal-batch-runner.md`.
Evidence: `reports/research/issue275-synthetic-evidence.json` và
`reports/research/issue275-seamless-pilot.json`.

## Kiểm chứng

- 77 focused tests PASS: 44 contract + 33 runner tests.
- Full suite trên executable bytes của published source:
  **2677 passed / 46 skipped / 48 subtests passed**, 393.38 s, Python 3.14.8.
  Final local checkout chỉ thêm refreshed acceptance report, không thay executable.
- Frozen #268 matrix replay khớp; single-source/batch, source/goal order và
  completed serial/resumed matrix/diagnostics/source ordering khớp.
- Numeric oracle được bind từ declared inputs/published identity formulas trước
  search: C=1/P=3/4, shared preparation C=2/P=3/8. C/P lấy đúng selected candidate;
  rebinding scope không mở rộng stale records hoặc proposed numeric adoption.
- Password missing/wrong/valid Computer context, disabled User, unknown gate,
  authoritative FALSE veto, checkpoint khác host-admin, source/goal isolation,
  error, native truncation, timeout, not-run và invalidated/tampered resume đều PASS.
- Ruff lint/format toàn repo, yamllint, repository/privacy, canonical contract và
  diff whitespace PASS. Compose chưa chạy; remote CI báo riêng trên PR.
- Week 4 acceptance replay deterministic: **36 PASS / 1 manual NOT EXECUTED /
  1 raw-prerequisite BLOCKED RUN**, 0 unexpected FAIL. Mutable maintainer manifest
  v2 được refresh để pin ba module mới; semantic golden không đổi.
- Historical likelihood catalog/manifest và scenario source-manifest-v2 được
  kiểm byte-equal với develop. Không sửa frozen #264 baselines.

Vòng full đầu phát hiện embedded manifest của accepted fixture không có marker
standalone `schema_version`, cùng source-pin coverage của acceptance report cũ.
Đã sửa validator chỉ bổ sung marker khi vắng, vẫn reject marker/field sai;
refresh evidence sau replay thật rồi chạy lại full suite PASS. Không sửa expected.

## SEAMLESS evidence

Đã verify 6 raw files theo authorized pinned manifest trước và sau run, build
toàn graph **3370 nodes / 56367 edges** cùng snapshot facts. Snapshot:
`sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
Source/target/config/code digests và raw locators ở sanitized report; raw records,
private snapshot, requests và full native traces không được commit.

Pilot: **5 source/profile scenarios × 3 default goals = 15 cells**, gồm cả bốn
supported profiles và Group unsupported. Chỉ bốn declared techniques; mỗi cell
caps 10 paths / 6 steps / 100 expansions. Đây là full-graph pilot trên tập source
được khai báo, không phải full-source batch hoặc scalability benchmark.

| Mode | Complete success | Truncated success | Truncated incomplete | Indeterminate | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scenario | 3 | 2 | 2 | 5 | 3 |
| Evidence-only | 1 | 0 | 0 | 11 | 3 |

Scenario có 5 cells đạt goal, gồm một zero-action host-admin đã có trong initial
Computer-admin profile. Evidence-only chỉ có zero-action success đó; không phải
bằng chứng quan sát thêm takeover. C=0 của nó là semantic zero-work, không phải
numeric adoption; **P-rated = 0/15** cả hai modes. Các cells khác giữ C null và
reasons/unknown/truncation. Không gọi unrated/incomplete sources là an toàn.

Scenario 71.45 s, evidence-only 69.29 s; tổng gồm build/verify/transport 179.63 s.
Linux process peak RSS 610689024 bytes. Không claim Windows parity/performance
hoặc scalability từ một cohort nhỏ. SEAMLESS raw-backed run tách khỏi các tests
optional đã skip vì raw không được đặt tại checkout's `data/raw/SEAMLESS`.

## Điều học được / quyết định

Dùng một reference implementation của #268 cùng public query/evaluator. Scope
digest ràng buộc toàn inputs/code; chỉ query scope được bind, không rewrite native
numeric applicability/history. Native negative proof quyết định khi nào source có
thể được gọi proven no-path. Logical budgets dùng cho deterministic replay;
wall deadlines chỉ bảo vệ runtime và công bố giới hạn witness transport.

## Trở ngại và việc kế tiếp

- #270 đã merge và được tích hợp cùng #272 trên develop `28236f2`; A cross-review/cross-run.
- Remote required CI/checks và human review; không tự merge hoặc đóng #275.
- #273 Top-K integration khi available, giữ K độc lập caps và native guarantees.
- Wall timeout dùng isolated worker, không có streaming partial witnesses trước
  khi worker gửi result. Native logical truncation vẫn giữ đầy đủ partial witnesses.
- Engine endpoint/state limitation cho một số User usable-identity goals vẫn được
  công bố trong guide; runner không mở rộng technique/search semantics để che gap.
- Parallel scheduling chưa hỗ trợ; không claim serial/parallel execution parity.

Theo contract, metadata dùng các extensible fields của request/result API hiện có;
execution/checkpoint metadata được versioned riêng. A cần review row-disposition
guard, native negative proof guard và trace transport khi integration acceptance.

## Cập nhật: xử lý conflict PR #276

Đã merge develop `28236f234a8eba40db0a0f47b70034f27543e063` (chứa #270/#272)
vào PR #276 bằng merge commit `43f965a0d634dc3a458b4014586d1542b111885c`;
không rewrite lịch sử nhánh. Hai add/add conflicts là
`scripts/research/source_goal_batch.py` và `tests/test_source_goal_batch_contract.py`.
Đối chiếu AST với develop bằng Python 3.14 xác nhận cùng logic; giữ Ruff formatting
của PR. Schemas, manifests và independent oracles giữ bytes của #270.

Verification sau merge: **99 passed / 1 skipped**, 34.42 s, gồm contract, runner,
AS-REP identity verifier mới #272 và Week 4 acceptance/checkout pins. Skip cần raw
SEAMLESS tại checkout; không thay bằng synthetic PASS. Ruff lint/format toàn repo,
yamllint, repository/contract/whitespace checks PASS. Batch executable/source pins
byte-equal với tested source `2e4790b`; full-suite/raw evidence phía trên vẫn là
evidence của lần chạy trước, không claim fresh full-suite hoặc raw rerun ở bước này.

Evidence tích hợp: `reports/research/issue275-conflict-integration.json`.
Guide/README/PR description đã chuyển trạng thái #270 từ pending merge sang
integrated; giữ các gate còn lại, gồm A cross-run, Top-K khi available và remote CI.

## Cập nhật: review P1/P2 của A

Đã tái lập cả hai findings trên reviewed implementation trước khi sửa:

- P1: evidence-only batch với source assumptions trả indeterminate cho host/DA,
  còn helper cũ tự dựng scenario request trả success. Rating/budget/target selection
  cũng có thể bị mất. Helper mới nhận toàn `BatchQueryRequest` hoặc Mapping, chỉ
  thay source set khi chọn `source_id`, không thêm defaults cho các semantic fields.
- P2: source không có assumptions vẫn có thể success nếu supplied global runtime
  records có `origin=declared_assumption`. Boundary mới validate toàn sequence
  trước mọi query/cache; reject declared_assumption/unspecified/invalid origins.
  Observed/default origin, explicit unknown và source-local unknown-only assumptions
  vẫn dùng public fact resolver; known FALSE vẫn veto TRUE assumptions.

Thêm 15 regressions: native evidence-only/rated/shared-work/helper parity, common
và custom caps, target/source selection, Mapping/RuntimeFact origin refusals trước
cell đầu tiên, observed TRUE/FALSE, unknown/default và CLI refusal. Runner suite
**48 passed**, 13.17 s. Independent #268 fixtures/oracles và numeric expectations
không đổi.

Final fixed executable: `0ece0e5fd3e503c03b0ce813444f08e1c83d3c77` (uploaded tree
byte-equal local source). Focused public fact/query/rating regressions:
**178 passed**, 38.33 s. Fresh full suite: **2707 passed / 46 skipped /
48 subtests passed**, 500.22 s, Python 3.14.8. Ruff lint/format toàn repo,
yamllint, repository/contract/whitespace checks PASS. Mutable Week 4 source pins
được refresh sau deterministic native replay: semantic digest
`sha256:3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d`
giữ nguyên; 36 PASS / 1 manual NOT EXECUTED / 1 prerequisite BLOCKED RUN.

`reports/research/issue275-review-evidence.json` ghi native before/after trên exact
reviewed source `26aa779`: evidence-only batch indeterminate khác old helper success;
old rated helper mất C/P; global assumptions trước sửa được chấp nhận. Fixed helper
giữ full semantic result và C=1/P=3/4; global declared/unspecified bị từ chối trước
cell, được regression kiểm tra với cả Mapping và RuntimeFact. Không claim fresh
SEAMLESS pilot cho lượt review fix này; raw evidence trước đó vẫn được giữ và pin
theo source đã chạy. Giữ review threads mở cho A xác nhận, không tự approve/merge.

## Cập nhật: tích hợp develop mới và hoàn tất rereview

A đã approve head `a564a65`, resolve P1/P2. Develop mới `8de3e04` chứa #278
(EA provenance `/groups/18`), #274 và public Top-K #273. Merge bằng
`e0279df43da5f94d967021390fd69630b14e4a2a`, giữ lịch sử nhánh; conflict duy nhất
ở mutable Week 4 manifest, được replay từ source tích hợp thay vì chọn hash cũ.

Hai test runner phát hiện lỗi tích hợp thật: serializer của typed AttackQuery gửi
`top_k: null` tới Mapping boundary mới, khiến worker có timeout trả error.
Fixed source `bb5f335fb385d2d73aac85807d35193eee7fa903` bỏ typed default absent
ở worker và trace; explicit null từ public Mapping vẫn bị reject. Thêm hai
regressions scenario/evidence-only có rating, direct/worker/native replay parity.
Runner **50 PASS** (9.68 s). Focused contract/runner/raw binding/Top-K/Week 4:
**137 PASS** (28.97 s), gồm đủ 5 actual-raw binding tests, không raw skip.

Fresh pilot `reports/research/issue275-seamless-corrected-pilot.json` dùng đúng
source `bb5f335`, full graph 3370 nodes/56367 edges, 5×3 cells, bốn techniques,
caps 10/6/100, verify sáu raw files trước/sau. Scenario statuses 3 complete-success,
2 truncated-success, 2 truncated-incomplete, 5 indeterminate, 3 unsupported;
evidence-only 1 zero-work success, 11 indeterminate, 3 unsupported. P-rated 0/15;
C=0 duy nhất là capability có sẵn của Computer-admin, không numeric adoption.
Scenario 55.51 s, evidence-only 57.99 s, tổng 142.58 s, peak RSS 610893824 bytes.
Pilot chạy cùng tests trên shared host, không dùng timings làm scalability claim.

Manifest đúng được embed trong request mới; request/scope digests được đối chiếu
và khác historical report. Replay riêng trên cùng executable/graph chứng minh
locator-only change từ `/groups/18` về `/groups/41` bị từ chối khi resume với
`CHECKPOINT_SCOPE_MISMATCH`. Raw/private requests và traces ở reports/generated.
Historical pilot/synthetic report và ba frozen rating baselines giữ nguyên bytes.

Week 4 deterministic replay: 36 PASS / 1 manual NOT EXECUTED / 1 prerequisite
BLOCKED RUN; digest `3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d`
không đổi. Full run: 2815 PASS / 52 skips / 48 subtests / 4 FAIL, 330.63 s.
Bốn FAIL đều phát sinh từ `W4-CLI-PACKAGE.clean_tracked_source=false` vì tài liệu
được sửa trong khi tests đang chạy; các semantic assertions khác khớp. Không sửa
oracle hoặc giảm clean-check. Commit tài liệu/evidence rồi rerun nhóm Week 4
trên checkout sạch; kết quả rerun ghi tiếp bên dưới.

Ruff lint/format (455 files), yamllint, repository/privacy, contract và whitespace
PASS. Batch request chưa expose per-cell K hay Top-K source/destination dù public
Top-K đã tích hợp; không tự gọi max_paths là K-best. Head mới cần A rereview và
remote required checks; chưa merge PR hoặc đóng #275.

Clean-checkout rerun: `python -m pytest tests/test_week4_acceptance_checkout_bytes.py
tests/test_week4_acceptance_manifest.py tests/test_week4_acceptance_review_regressions.py -q`
**14 PASS**, 137.70 s, bao gồm cả bốn ca fail trước đó và tất cả lệnh demo.
Không thay executable giữa full run và rerun. Tổng coverage đã chạy: 2819 test cases
pass qua full run + clean rerun, 52 optional/platform skips, 48 subtests; không
claim một full run sạch duy nhất. Raw-binding 5/5 đã chạy riêng trong focused set.
