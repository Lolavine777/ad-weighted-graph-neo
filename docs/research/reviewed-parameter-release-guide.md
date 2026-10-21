# Xuất và kiểm chứng tham số đã quyết định trong phạm vi SEAMLESS

Refs #171, #143, #158, #48; tiếp nối [PR #170](https://github.com/nairyuuu/ad-weighted-graph/pull/170).
TTS A triển khai tooling; TTS B review implementation và giao diện consume.
Contract release/decision dưới đây là đề xuất implementation để B review, không phải acceptance cho số liệu thực tế.

## Ranh giới và audit helper

`reconcile_rating_sheets.py` tạo report 1.1.0 với raw records, full bindings, metadata, overlap và digests; mọi verdict trong report vẫn là proposal.
`seamless_parameter_validation.py::verify_parameter_bundle` tiếp tục chỉ kiểm chứng research bundle với `raters=[]`, pending status và oracle cố định.
Tool mới `reviewed_parameter_release.py` sử dụng verifier này để audit **template nghiên cứu đầu vào**, rồi xuất một release riêng từ final records được khai báo.
Không dùng research oracle để kiểm chứng số đã chọn; không sửa research bundles, oracles hoặc phiếu pending để nhận điểm mới.
`derive_query_and_candidates_from_bundle`, `compute_bundle_digest`, validators từng record, canonical work-unit registry và atomic writer của #170 được tái sử dụng.
`src/engine/` và `src/parser/` không thay đổi.

Phạm vi cố định gồm 1 impact, 11 conditional step factors dưới full history, 9 persistent work units và hai query Source A/Source B của packet hiện hành.
`target_population` phải là `SEAMLESS v1 declared scenario only`.
Template có canonical digest pin `sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`, độc lập với newline của checkout; sửa facts/actions/routes/provenance rồi rehash không qua audit.
Scope/version/foothold/snapshot/horizon/goal phải khớp template; không fallback giữa hai queries.
Facts observed/false/assumed/unknown, predicate layers, actions, structural routes và provenance locators được sao chép nguyên trạng từ template.
Budget hiện hành tính số active work units, không phải tổng điểm nỗ lực; vì vậy effort 10 không tự vi phạm budget 6 khi candidate có 5 units.

## Phần người chấm và người quyết định

Lớp `declared_independent_ratings` yêu cầu hai người thật chấm độc lập đủ 21 records mỗi người và khai báo identity, năng lực/phạm vi, independence, rated_at, rationale và nguồn thật theo [governance §3.5](evidence-rating-governance.md).
Hai fixtures `seamless_rater_1.json` / `seamless_rater_2.json` vẫn pending và được giữ nguyên từng byte.
Hai source sheets được tiếp nhận trong [PR #173](https://github.com/nairyuuu/ad-weighted-graph/pull/173), merge `96fc89a`, thuộc lớp `human_reviewed_ai_assisted_ratings`; có AI assistance/exposure và xác nhận B được A chuyển đạt, không là blind independent scoring.
Tool hỗ trợ evidence này mà không đổi nhãn thành independent hoặc yêu cầu xác nhận lại B; việc tiếp nhận source ratings không chọn final dispositions.
Synthetic demo chỉ tạo bản sao ở thư mục output mới, không ghi điểm vào phiếu thật.

Người có thẩm quyền xem raw disagreement, likelihood IoU/width, effort delta và overlap rồi lập **một explicit disposition cho từng record**, kể cả proposal đồng thuận.
Không tự lấy max cost, union interval hoặc nhãn Tier0 làm quyết định.
`resolution` phải giải thích disposition đối với disagreement/uncertainty/overlap hoặc ghi rõ không có vấn đề cần giải quyết trong scope.
Final effort phải có rubric riêng nhất quán `computed_cost = T1 + T2 - 2`, T1/T2 là integer 1..3, cost 0..4 và overlap đã phân bổ độc lập.
Prerequisite không tự đồng nghĩa overlap; shared preparation/prerequisites và final rationale được giữ trong release.
Contract này không hỗ trợ phát hành partial release: thiếu ratings/basis hoặc unresolved overlap thì tiếp tục pending, không điền default.
Workflow thủ công có đầy đủ bằng chứng vẫn hợp lệ; không thêm external panel, tổ chức, chữ ký hoặc live-attack gate.

## Contract decision record 1.0.0

Decision document chứa `schema_version: "1.0.0"`, `release_id`, `release_version` dạng major.minor.patch, `evidence_class`, `input_digests`, `report_digest` và `decisions`.
`evidence_class` nhận `synthetic_test_only`, `declared_independent_ratings` hoặc `human_reviewed_ai_assisted_ratings`; các nguồn synthetic/AI-only không được đổi nhãn thành nguồn độc lập của người thật.
`input_digests` phải khớp toàn bộ source sheets/template và registry/report nếu cung cấp.
Digest file là SHA-256 raw UTF-8 bytes, bao gồm newline; `report_digest` và `pair_digest` là SHA-256 JSON canonical sorted keys, compact separators.
`report_digest` bind tới **report được đối soát lại từ source**; report supplied bị sửa hoặc stale bị từ chối.
Đường dẫn được giữ như nhãn provenance; offline replay không mở lại các đường dẫn source và không đổi separator theo OS.

Mỗi phần tử `decisions` chứa:

| Trường | Yêu cầu |
| --- | --- |
| `category` | `impact`, `likelihood` hoặc `effort` |
| `pair_digest` | Digest toàn bộ reconciled pair, bao gồm cả hai raw records và full context |
| `binding` | Bằng object `binding` của pair, không dùng question_id/vị trí mảng làm khóa |
| `disposition` | `reviewed`; pending/rejected/withheld không xuất thành rated parameter |
| `final_record` | Complete record theo schema phiếu; rating_status rated, evaluator bằng reviewer_identity, binding fields giữ nguyên |
| `reviewer_identity` | Identity được khai báo rõ; placeholder pending không hợp lệ |
| `declared_at` | ISO-8601 có date/time và timezone, do người khai báo cung cấp |
| `rationale`, `resolution` | Nonempty text giải trình lựa chọn và vấn đề đã review |
| `decision_reference` | Nonempty reference để audit quyết định |

Release boundary từ chối các sentinel `PENDING`, `UNRESOLVED`, `TBD`, `TODO` khi **toàn bộ giá trị** sau trim whitespace/casefold bằng sentinel.
Áp dụng cho declaration text và evidence fields của source rated records/final records: impact `business_rationale`, likelihood `basis_category`/`uncertainty_rationale` và từng `source_references`, effort `effort_rationale`.
Metadata của cả hai source raters cũng phải qua guard này: `evaluator`, `name`, `competence_and_scope`, `independence_declaration`, với mọi evidence class.
`rater.organization` và `rater.signature` vẫn optional; absent/null không ngăn phát hành nếu các declaration bắt buộc đầy đủ.
Không dùng substring guard mới cho rationale/reference: prose hoặc URL có từ pending/unresolved vẫn hợp lệ và giữ nguyên từng byte trong provenance.
Reviewer identity/binding vẫn có các restriction riêng hiện hành của #170; thay đổi này chỉ ở reviewed-release boundary, không sửa reconciliation helpers.

Organization/signature có thể bổ sung trong declaration; không bắt buộc.
Tool kiểm tra declaration, consistency và provenance, **không xác thực danh tính, thời điểm, năng lực hoặc việc review thực sự đã diễn ra**.
Digests phát hiện inconsistency/stale inputs, không phải chữ ký hoặc cơ chế chống một người thay toàn bộ nguồn lẫn declarations.

## Nguồn human-reviewed có AI hỗ trợ - cập nhật 2026-10-02

Lớp mới giữ nguyên điểm nguồn và mọi disclosure trong raw snapshots; source review, final dispositions, độc lập chấm và numerical acceptance là các trạng thái riêng.
Hai sheets phải khai báo cùng evidence class, `human_rating_status` là `confirmed_by_user` hoặc `confirmed_via_user_relay`, `human_agreement_eligible: true` cho joint judgment và `independent_inter_rater_agreement_eligible: false`.
Declaration lớp nguồn AI-only, chưa được người dùng tiếp nhận, nguồn synthetic hoặc source exposure không được phát hành thành `declared_independent_ratings`.
Khai báo này kiểm tra consistency, không xác thực người đang có mặt hoặc biến relayed confirmation thành lời attestation riêng do B viết.

API `inputs` bổ sung ba snapshots `policy`, `confirmation`, `ai_draft`; CLI nhận `--policy`, `--confirmation`, `--ai-draft`.
Biên bản review dùng `reviewed_at` (ISO-8601 có múi giờ) và `review_summary` (tóm tắt quyết định). Hai tên legacy `user_message_time`/`user_statement` vẫn đọc được để phát lại artifacts cũ; nếu cùng có hai tên mà giá trị khác nhau thì từ chối. Không bắt buộc lưu lời hội thoại để kiểm chứng release.
Với human-reviewed AI evidence, cả ba bắt buộc và cùng tham gia `input_digests`; raw UTF-8 bytes/digests/path labels được giữ trong release để replay offline.
`execution_policy_reference` của hai sheets và mỗi final/source likelihood record phải khớp policy id/version/path label/raw digest; horizon và retry/deadline phải đúng policy cho outcome mechanism.
Limits là positive integers, không chấp nhận bool; kiểm policy trước gọi #170 để extra fields không bị bỏ qua, rồi kiểm lại final decisions trước projection.
Một source có policy declaration cũng phải cung cấp policy snapshot khi reconcile/export ở boundary này, kể cả khi dùng evidence class cũ.

Confirmation phải có record id, người ghi, user statement/time có timezone, channel, participants khớp hai evaluators, scope và exposure đầy đủ.
Sheet confirmation reference và policy confirmation reference phải cùng chỉ tới snapshot; confirmation phải bind policy digest và original-input provenance A/B giống declarations của hai sheets.
B AI archive được embed nguyên byte và đối chiếu path/digest với confirmation; bản gốc giữ trạng thái AI-only chưa được xác nhận, không thay bằng phiếu human-reviewed hiện tại.
Contract confirmation hiện tại là tiếp nhận **assessment B đã có**, nên đủ 21 archive bindings/values phải khớp phiếu B được tiếp nhận: impact label, likelihood bounds, effort rubric và overlap.
Archive phải qua validators #170, không chấp nhận JSON stub chỉ có status/class hoặc số nguồn đã thay dưới confirmation cũ.
B source status phải giữ `confirmed_via_user_relay`; cả 21 records phải giữ `human_confirmation` với cùng record reference, channel `relayed_by_A` và scope `adoption_of_existing_assessment_under_shared_policy`.
Nếu thay judgment nguồn cần source confirmation/provenance đúng cho lượt thay đổi, không dùng confirmation tiếp nhận giá trị cũ; final decision lựa chọn tham số vẫn là bước riêng và có thể chọn khác sources khi có explicit disposition hợp lệ.
Original A reference/digest được giữ như provenance declaration; tool không fetch URL lịch sử để xác thực nguồn A gốc.
Tên file tương đối trong references khớp basename của snapshot path; path còn lại là nhãn provenance, không được mở lại khi replay.
Packet JSON có `.gitattributes -text` để Windows không đổi bytes đã pin bằng digest; không normalize newline của input nhằm làm digest khớp.

Release governance và validation report giữ `rating_context` với policy/reference, confirmation/channel/exposure, confirmation/archive digests và eligibility false.
Source assistance metadata, B draft và distinct A/B intervals nằm trong lossless `provenance.inputs`; Kappa/IoU/chênh lệch của #170 chỉ mô tả artifacts này, không là reliability của hai lần chấm mù.
Root likelihood rows giữ cả policy và reference; source/context/root tamper dù rehash vẫn bị replay từ chối.
Synthetic demo, research fixtures/oracles, #170 helpers và canonical engine/parser không đổi.

Khi có **21 final dispositions thật được khai báo riêng**, có thể chạy từ root:

```bash
.venv/bin/python scripts/research/reviewed_parameter_release.py export --sheet1 docs/research/ratings/week3-2026-10-02/rater-A.json --sheet2 docs/research/ratings/week3-2026-10-02/rater-B.json --policy docs/research/ratings/week3-2026-10-02/execution-policy.json --confirmation docs/research/ratings/week3-2026-10-02/shared-review-confirmation.json --ai-draft docs/research/ratings/week3-2026-10-02/rater-B-ai-draft.json --template tests/fixtures/ranking/seamless_parameter_bundle.json --decisions local/final-decisions.json --output local/reviewed-release.json
.venv/bin/python scripts/research/reviewed_parameter_release.py validate --release local/reviewed-release.json --output local/reviewed-validation.json
.venv/bin/python -m pytest tests/test_ai_assisted_reviewed_release.py tests/test_reviewed_parameter_release.py -q
```

Ví dụ test chọn source A bằng identity/timestamp/rationale test-only để kiểm tra mapping và sensitivity; không ghi chúng thành decisions thật trong packet.
Không dùng `synthetic_decisions()` hoặc test builder để tự phê duyệt source proposals; thiếu final declarations thật thì actual release/acceptance vẫn pending.

Python API chuẩn bị input/report để người quyết định đọc:

```python
from pathlib import Path
from scripts.research.reviewed_parameter_release import load_snapshot, reconcile_inputs, digest

inputs = {
    "sheet1": load_snapshot(Path("local/rater-1.json")),
    "sheet2": load_snapshot(Path("local/rater-2.json")),
    "template": load_snapshot(Path("tests/fixtures/ranking/seamless_parameter_bundle.json")),
}
report = reconcile_inputs(inputs)
report_digest = digest(report)
input_digests = {key: snapshot["digest"] for key, snapshot in inputs.items()}
# Người quyết định lập declarations từ full pair context và chọn complete final_record.
# Không sử dụng synthetic_decisions để quyết định tham số thật.
```

Không có API tự tạo quyết định thật từ proposal.
`synthetic_reviewed_release_demo.py::synthetic_decisions` chỉ tạo **test declarations** với identity/thời điểm hư cấu được gắn nhãn rõ.

## Phần script: release, validation và sensitivity

`export_release(inputs, decisions)` đối soát lại nguồn, audit template, kiểm tra declarations và map đầy đủ các root records.
Release giữ raw UTF-8 bytes trong `provenance.inputs[*].raw_utf8`, raw-byte digests, report nguyên vẹn, final decisions và canonical decision digest.
Không bỏ raw disagreement hoặc gắn rubric thô của một người vào final cost khác công thức.
Root metadata có release id/version và digest; hai `query_projections` được derive từ root và seal bằng cùng digest convention của research helper.
Research analytical baseline/sensitivity thresholds không được copy sang reviewed release.
`human_acceptance: pending`, `publication_status: not_published` và `empirical_calibration_status: none` vẫn được ghi rõ.

`verify_release(release)` xác minh digest, decode raw snapshots, đối soát lại, xuất lại từ declarations và so sánh **toàn bộ release**.
Sửa root/cache/scope/rationale/provenance rồi rehash vẫn bị từ chối nếu không khớp các nguồn và quyết định đã khai báo.
`validate_and_sensitivity(release)` gọi verifier trước execution selected parameters, rồi chạy `PathRankingEngine(version="1.0.0")` cho cả hai queries.
Independent oracle scoped dùng `Fraction` để nhân từng q_i, dedup persistent work, sum effort, đọc consequence, tính partial order/frontier và Min-Effort riêng.
Expected/actual gồm chương trình work, likelihood, effort, impact, frontier, tie/incomparability và separate Min-Effort.
Oracle chỉ hỗ trợ các positive routes của audited template; không phải search hoặc general fact replay implementation mới.

Sensitivity có 21 perturbations: mỗi step interval nhân 9/10, mỗi work-unit rubric đổi một điểm hợp lệ, impact dịch một mức ordinal.
Nếu interval là `[0,0]`, probe mở upper thành `1/100` và ghi rationale boundary riêng để không đếm no-op là parameter perturbation.
Mỗi probe chỉ chạy queries có record đó, giữ rationale/scope, expected/actual và thay đổi frontier/relations/Min-Effort.
Probe có digest riêng và governance `hypothetical_sensitivity_probe`, bind selected release digest; không giả làm reviewed disposition mới.
Coverage công bố ba supplied candidates; còn thiếu global search, joint perturbations, empirical calibration và attack execution.
Sensitivity không chứng minh empirical calibration, khả năng attack thực thi hoặc production/generalization ngoài scope.

## Lệnh E2E tái lập bằng synthetic

Yêu cầu Python theo `.python-version` và dependencies trong `requirements-dev.txt` đã cài vào venv.
Dùng `.venv/bin/python` trên Ubuntu; trên Windows dùng `.venv/Scripts/python.exe` với cùng arguments.
Các lệnh dưới chạy từ repository root và tạo artifacts local ignored.
Thư mục demo phải chưa tồn tại; rerun bị từ chối để giữ output cũ.

```bash
.venv/bin/python scripts/research/synthetic_reviewed_release_demo.py --directory reports/generated/171-reviewed-release-demo
.venv/bin/python scripts/research/reviewed_parameter_release.py export --sheet1 reports/generated/171-reviewed-release-demo/synthetic-sheet-1.json --sheet2 reports/generated/171-reviewed-release-demo/synthetic-sheet-2.json --template tests/fixtures/ranking/seamless_parameter_bundle.json --decisions reports/generated/171-reviewed-release-demo/decisions.json --output reports/generated/171-reviewed-release-demo/cli-release.json
.venv/bin/python scripts/research/reviewed_parameter_release.py validate --release reports/generated/171-reviewed-release-demo/cli-release.json --output reports/generated/171-reviewed-release-demo/cli-validation.json
.venv/bin/python -m pytest tests/test_reviewed_parameter_release.py -q
```

Demo sử dụng impact Critical, mọi q_i `[1/2, 3/4]`, mọi rubric T1=T2=2/C=2; đây là **test-only values**, khác research baseline High và các khoảng/chi phí cũ.
Identity và timestamp năm 2000 đều là synthetic test declarations, không phải sự kiện người thật.

| Candidate | Tính độc lập | Expected và engine actual |
| --- | --- | --- |
| Source A, direct Lidia | `(1/2)^3 .. (3/4)^3`, `3*2` | `[1/8, 27/64]`, effort 6, Critical |
| Source A, alternative Vajer/Ollie | `(1/2)^5 .. (3/4)^5`, `5*2` | `[1/32, 243/1024]`, effort 10, Critical |
| Source B, Ollie | `(1/2)^3 .. (3/4)^3`, `3*2` | `[1/8, 27/64]`, effort 6, Critical |

Source A giữ cả hai candidates incomparable trên frontier; Min-Effort riêng chọn direct Lidia với 6.
Source B có một candidate supplied với Min-Effort 6, không có chứng minh global optimum.
Digests trong worklog là observation của run/path labels đó; raw-byte digests có thể khác khi newline hoặc absolute path labels khác.
CLI xuất stdout JSON với output raw-byte digest, exit 0 khi ghi thành công, exit 1 khi validation/I/O thất bại và exit 2 khi arguments sai.
Output aliases/symlink/hardlink tới input bị từ chối; atomic writer tạo temp file độc quyền cùng thư mục, đóng handle trước replace để chạy Windows, cleanup temp khi lỗi.
Không ghi output trước khi kiểm chứng xong; lỗi giữ input/output cũ.

## Bàn giao và gates còn lại

B có thể consume `query_projections.source_a` / `source_b` của release **đã verify**, rồi dùng canonical engine API/CLI hiện hành.
Không consume cache từ release chưa verify hoặc gọi research verifier trên reviewed release.
Cần B review extension trên head mới; source review #173 đã được tiếp nhận, nhưng 21 final dispositions và actual parameter acceptance vẫn cần declarations/evidence riêng.
#143/#158/#48 giữ mở; SEAMLESS predictive verdict và final integrated E2E/clean-checkout acceptance không được nâng chỉ vì synthetic tooling pass.
#47 vẫn có dependency Legacy artifacts/mapping riêng; task này không lấy scope engine/parser hoặc #167.

## Cập nhật actual release và requirement independence — 2026-10-03

[Hồ sơ closeout](ratings/week3-closeout/README.md) đã có 21 lựa chọn thật của A, actual reviewed release và validation/sensitivity passed trên ba ứng viên. Source basis vẫn human-reviewed AI-assisted, B xác nhận qua A và có exposure; không có independent inter-rater reliability evidence.

[Disposition cơ sở tham số](week3-rating-requirement-disposition.md) ghi chấp thuận của chủ dự án dùng bộ nhận định hiện tại thay yêu cầu bổ sung chấm độc lập trong phạm vi kịch bản Week 3. Review theo workflow PR; source acceptance và lựa chọn tham số trước đó không được dùng làm quyết định thay yêu cầu; không nâng Week 3/SEAMLESS integrated verdict hoặc sửa research fixtures từ cập nhật này. Các đoạn pending/tooling ở trên là checkpoint lịch sử theo ngày, không phủ nhận actual export mới.
