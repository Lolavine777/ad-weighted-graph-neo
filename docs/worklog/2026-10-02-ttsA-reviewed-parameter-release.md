# Worklog - 2026-10-02 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#171](https://github.com/nairyuuu/ad-weighted-graph/issues/171), Refs #143/#158/#48 / [PR #172](https://github.com/nairyuuu/ad-weighted-graph/pull/172) / M2; nối tiếp merged PR #170.
- Nhánh: `feature/171-reviewed-parameter-release`, base `develop` tại `12a221fb401d9ce0a38e008168dc0b62f116792d`.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Reviewed export/replay/sensitivity | [Guide](../research/reviewed-parameter-release-guide.md), `scripts/research/reviewed_parameter_release.py` | Synthetic selected-number E2E pass, actual acceptance pending |
| Preserve ownership/evidence | Diff từ base develop và byte checks | Pending sheets, research bundles/oracles và engine/parser không đổi |

Đọc CONTRIBUTING, #143/#158/#171, PR #170 và audit helper/schema/mapping hiện hành trước implementation.
Tạo exporter/validator `scripts/research/reviewed_parameter_release.py`, synthetic E2E generator riêng và regression tests.
Release yêu cầu 21 explicit reviewed dispositions bind source/report/template digests và full context; không nhận proposal tự động thành acceptance.
Replay validator kiểm tra toàn bộ root/projections/provenance, giữ raw UTF-8 bytes, declarations, nguồn/rationale/rubric/overlap và disagreement.
Scope gồm cả Source A và B; facts/actions/routes/provenance giữ nguyên, không có missing-record defaults hoặc cross-scope fallback.
Independent `Fraction` oracle đối chiếu chosen q_i products, persistent work dedup, effort, consequence, frontier/tie/incomparability và separate Min-Effort với canonical engine.
Sensitivity có 21 scoped hypothetical probes và coverage disclosures, không phải empirical calibration hoặc bằng chứng attack execution.
Cập nhật guide tiếng Việt, governance §3.5, reconciliation handoff và dated amendment của acceptance disposition.
Không sửa docs chung thuộc #167, engine/parser B, actual pending sheets, research bundle/helpers/oracles hoặc CHANGELOG.

## Evidence E2E local

Runtime local: Python 3.14.2 trong `.venv`, Linux; không dùng Python global.
Chạy từ `/workspaces/ad-weighted-graph` với source/provenance path labels của checkout này.

```bash
.venv/bin/python scripts/research/synthetic_reviewed_release_demo.py --directory reports/generated/171-reviewed-release-demo
.venv/bin/python scripts/research/reviewed_parameter_release.py export --sheet1 reports/generated/171-reviewed-release-demo/synthetic-sheet-1.json --sheet2 reports/generated/171-reviewed-release-demo/synthetic-sheet-2.json --template tests/fixtures/ranking/seamless_parameter_bundle.json --decisions reports/generated/171-reviewed-release-demo/decisions.json --output reports/generated/171-reviewed-release-demo/cli-release.json
.venv/bin/python scripts/research/reviewed_parameter_release.py validate --release reports/generated/171-reviewed-release-demo/cli-release.json --output reports/generated/171-reviewed-release-demo/cli-validation.json
```

Ba lệnh đã exit 0; report `validation_status: passed`, `human_acceptance: pending`.
Synthetic identities và dates năm 2000 là test declarations cố ý, không phải dữ kiện người thật.
Raw ratings và final selections dùng impact Critical, q_i `[1/2, 3/4]`, rubric T1=T2=2/C=2, khác research baseline.
Source A direct và Source B có `[1/8, 27/64]`, effort 6; Source A alternative có `[1/32, 243/1024]`, effort 10; tất cả Critical.
Source A giữ hai candidates incomparable; separate Min-Effort chọn direct với 6, Source B có Min-Effort 6 trong supplied subset.

| Artifact local | Raw-byte SHA-256 |
| --- | --- |
| `synthetic-sheet-1.json` | `e8053fab3de2847150d96a6ceddf9df96e3197af4cdfed10a319b87bc3457bde` |
| `synthetic-sheet-2.json` | `6234cf53b38f44cce434737a05dfcb5417039b4e9cdc7c3ddc7d1e231ed1fc75` |
| `decisions.json` | `a1304b3dc1c86b0cf590298e0958d861f907ebbcf957113e951798f79e48e1f2` |
| `cli-release.json` | `f38706c232022a570b45b6ff06c79319c7ff58e60840082a154b572d80526610` |
| `cli-validation.json` | `ad84995acf63f7855eb5a915862c6f83faa900083cbc1d73844b9530b85ffc68` |

Canonical digest của CLI release là `sha256:7eafc8fce4a9209dfe27a661800a66c51520a3412cc77ed06c6ae940bbdc2195`.
Canonical validation report digest là `sha256:cdc45c616653006fea3056397743d098223bf358cb17cd956806bd37537c88ad`.
Artifacts ở `reports/generated/171-reviewed-release-demo/` được giữ local ignored, không commit output giả làm acceptance.
Digest observations áp dụng cho input bytes/path labels của run này; Windows newline hoặc checkout khác có thể thay raw bytes/digests mà không phải tool sửa input.

Actual pending sheet hashes trước/sau test là `b409a2fff62f3036a1970eecdef5c8d886fa02aa190de338c8d7ad0435ef1e66` và `26bb9b58a3db12afa7386c114f4dca564c51f0987b7495344ade91308b32c3bf`.
Research bundle raw-byte hash là `251771f39c888d525edde10e969f481836a4c3bbc48029ec8a4ed6cdeaf4cb04`.
Git diff so với base không có thay đổi `tests/fixtures/ranking/`, `seamless_parameter_validation.py`, `path_ranking_wire_adapter.py`, `src/engine/` hoặc `src/parser/`.

## Điều học được / quyết định

Baseline targeted tests trước implementation: `186 passed` cho reconciliation/reconciliation review/research parameter proposal.
Test mới bắt đầu red vì module chưa có; các probes duplicate JSON keys, unresolved explicit basis, expected/actual relations và synthetic demo CLI được chạy red rồi green khi bổ sung behavior.
Tests dùng bản sao synthetic/tạm cho missing/duplicate/extra/stale decisions, report tampering, full bindings/history/quantity/outcome, missing basis, strict integers/rationals, overlap, root/cache mismatch, aliases và atomic temp failure.
CLI tests kiểm tra input/output bytes và cleanup; no fabricated ratings được ghi vào actual sheets.
Local Ruff lint/format, yamllint, contract/repository checks, `git diff --check` và Compose config với password placeholder đã đạt.
`.venv/bin/python -m pytest tests/test_reviewed_parameter_release.py -q` đạt `82 passed`.
`.venv/bin/python -m pytest -q` đạt `1372 passed, 1 skipped, 48 subtests passed`; skip là Windows junction test trên Linux.
Các tests mới và full suite đã chạy lại sau fixes của independent review; synthetic CLI rerun giữ đúng output digests ở bảng trên.
Required Ubuntu/Windows CI đúng pushed revision được ghi theo kết quả thực tế ở checkpoint tiếp theo; local Linux không thay Windows evidence.
Independent code review phát hiện research verifier không pin toàn bộ context template và một nhánh JSON `1e999` -> Infinity có thể gây lỗi readback sau khi đã replace output.
Đã bổ sung canonical template digest pin, finite-number decoding và serialization/digest preflight trước atomic replace; không readback để validation sau khi ghi.
Regression tests rehashed unknown rationale/prerequisites/route locators, overflowing JSON và readback unavailable kiểm chứng fixes; zero-point sensitivity có boundary probe để không đếm no-op.
Independent code review hỗ trợ kiểm tra implementation; không thay B human review hoặc parameter acceptance.

## Trở ngại và việc kế tiếp

Actual release chưa phát hành vì hai actual sheets vẫn pending và chưa có final decisions thật đủ scope.
Tool chỉ xác minh declaration/provenance, không chứng thực identity/timestamp/review thực sự.
B cần review contract/tooling của PR vào develop; chưa ghi B approval.
A/B vẫn cần actual independent ratings, reviewed dispositions và final parameter acceptance; #143/#158/#48 còn mở.
B integration, final integrated develop E2E/clean-checkout và Legacy dependencies giữ ownership/gates riêng.
Không merge PR hoặc tự đóng parent issues trong lượt này.

## CI trên source head và bàn giao PR

[CI run 36970241974](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36970241974) của source head `73c5aa9cc436acdca59251e9b4566bf9767364bf` đã SUCCESS cho Ubuntu, Windows, quality và Compose.
[Branch policy run 36970242044](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36970242044) cũng SUCCESS.
Actions checkout PR merge revision `9444412c2602f76f361a71428804f682081eee46`, kết hợp source head trên với develop `12a221fb401d9ce0a38e008168dc0b62f116792d`.
Trên Python 3.14.7/pytest 9.1.1, [Ubuntu job](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36970241974/job/110722507610) ghi `1364 passed, 9 skipped` và [Windows job](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36970241974/job/110722507687) ghi `1363 passed, 10 skipped`.
CI totals là observations của runtime đó; không thay local totals và không suy skips là tool làm thay đổi phiếu.
Lượt bổ sung này chỉ cập nhật worklog; final pushed-head checks được kiểm tra lại và ghi vào PR description để không nhầm source CI với documentation revision sau đó.
PR #172 đã mở vào develop, reviewer request tới @nairyuuu đã được read back; chưa có B approval hoặc acceptance được khai báo.
#171/#143/#158/#48 còn OPEN trong readback sau mở PR; không merge hoặc đóng issues.

## Sửa review placeholders của PR #172 - 2026-10-02

Đọc deep review COMMENT của A ở head `41fb25ac2a11e8e25ff8bb0e4cc9241667a92b2f`; đây không phải B approval hoặc parameter acceptance.
Hai blocking threads là [reviewed disposition placeholders](https://github.com/nairyuuu/ad-weighted-graph/pull/172#discussion_r4163306210) và [resolved basis](https://github.com/nairyuuu/ad-weighted-graph/pull/172#discussion_r4163306218).
Tái hiện bằng exporter subprocess trên disposable synthetic copies: literal PENDING/normalized UNRESOLVED vẫn có thể tạo release dù rationale/resolution/reference hoặc rated evidence chưa được khai báo đầy đủ.
Bộ regression bổ sung ghi `22 failed, 3 passed` trước sửa; một pending basis case đã được validator #170 chặn, hai prose/reference cases hợp lệ đã pass.
Thêm helper release-only dùng trim/casefold và sentinel set PENDING/UNRESOLVED/TBD/TODO, kiểm tra toàn bộ text thay vì substring.
Guard áp dụng cho final declarations và rated evidence của cả nguồn/final choices; raw placeholder của một nguồn không bị che bởi choice từ nguồn còn lại.
CLI regressions kiểm tra từ chối, giữ sources/output cũ và không tạo output mới khi lỗi; positive tests giữ nguyên prose/references có pending/unresolved và đi tiếp validation/engine/sensitivity.
`.venv/bin/python -m pytest tests/test_reviewed_parameter_release.py -q` đạt `107 passed`, gồm 25 cases mới.
Ruff lint/format, yamllint, contract/repository checks, `git diff --check` và Compose config đã pass trong lượt sửa.
Diff từ review head không sửa #170 reconciliation helpers, research verifier/oracles, pending sheets hoặc engine/parser của B.
PR body được làm rõ: sửa lỗi bằng serialization/digest preflight **trước** atomic replace và không đọc lại output sau replace, không gọi đây là post-write verification.
`.venv/bin/python -m pytest -q` đạt `1397 passed, 1 skipped, 48 subtests passed` trên local Python 3.14.2/Linux; skip là Windows junction test.
Required Ubuntu/Windows checks của pushed fix được xác minh và ghi vào PR description theo đúng head/run; không dùng evidence ở head cũ thay cho fix.
Independent agent code review trên diff sửa không tìm thấy blocker và chạy lại `107 passed`; đây là hỗ trợ implementation review, không thay B human approval.
Không merge, đóng issues hoặc ghi human acceptance; B review và actual rating/disposition gates vẫn pending.

## Sửa B review về metadata người chấm - 2026-10-02

Đọc [CHANGES_REQUESTED của B](https://github.com/nairyuuu/ad-weighted-graph/pull/172#pullrequestreview-5389079973) trên head `c2a6d3032b2f42b6ad5cf18714438687726f5e48`.
Đã fast-forward các commits chuyển nhầm rating draft sang #173; không rewrite lịch sử hoặc đưa draft đó trở lại #172.
Tái hiện qua export subprocess với disposable test-only copies, evidence class `declared_independent_ratings` chỉ dùng để kiểm tra boundary; đây không phải human ratings hoặc acceptance.
Trước sửa, 36 regression cases ghi `30 failed, 6 passed`: 30 metadata placeholders vẫn phát hành được, hai PENDING evaluator cases đã bị #170 chặn, bốn valid-prose cases pass.
Thêm guard dùng helper exact trim/casefold PENDING/UNRESOLVED/TBD/TODO cho `rater.evaluator`, `rater.name`, `rater.competence_and_scope`, `rater.independence_declaration` của cả hai rated source sheets và cả hai evidence classes.
Không thêm substring restriction mới; prose có các từ sentinel vẫn được giữ nguyên trong raw provenance và đi tiếp replay/engine/sensitivity.
`organization` và `signature` vẫn optional; positive cases kiểm tra absent/null và human acceptance vẫn pending.
32 CLI cases kiểm tra cả hai sheets, bốn fields, bốn normalized sentinels, từ chối export và giữ nguyên source bytes/output cũ.
`.venv/bin/python -m pytest tests/test_reviewed_parameter_release.py -q` đạt `143 passed`, gồm 36 cases bổ sung.
Ruff lint/format, yamllint, contract/repository checks, `git diff --check` và Compose config đã pass.
Diff không sửa #170 helpers, actual pending sheets, research bundles/oracles hoặc B-owned engine/parser.
Kết quả full suite và exact pushed-head Ubuntu/Windows checks được ghi theo observations thực tế bên dưới hoặc trong PR description.
B cần review lại commit sửa; CHANGES_REQUESTED không tự thành approval khi checks đạt.
Không merge, đóng parent issues hoặc khai báo human acceptance.
`.venv/bin/python -m pytest -q` đạt `1433 passed, 1 skipped, 48 subtests passed` trên local Python 3.14.2/Linux; skip là Windows junction test.
Independent agent review không tìm thấy findings và chạy lại `143 passed`; đây là hỗ trợ code review, không thay B human approval.

## Mở rộng evidence class theo bàn giao #173 - 2026-10-02

Đọc [handoff mới trên #172](https://github.com/nairyuuu/ad-weighted-graph/pull/172#issuecomment-5947382169) và packet README, hai source sheets, policy, shared confirmation, original B AI draft của [#173](https://github.com/nairyuuu/ad-weighted-graph/pull/173).
#173 đã merge tại `96fc89acc0859dd29fc17cdde57466fd8a263a01`; merge `origin/develop` vào shared branch ở `2d8c1ce`, không force push hoặc rewrite history.
B approval trên `b779916` chỉ áp dụng cho implementation trước extension; source confirmation #173 không bị yêu cầu lại hoặc viết thành lời attest riêng do B gửi.

Thêm `human_reviewed_ai_assisted_ratings` bên cạnh hai lớp cũ, với snapshots `policy`, `confirmation`, `ai_draft` trong API và CLI.
Preflight chạy trước reconciliation #170: kiểm source status/class/confirmation/eligibility, participants và relayed channel, policy id/version/raw digest, retry/deadline/horizon cho đủ likelihood records và original-input provenance.
Final likelihood decisions phải dùng đúng policy/reference, root rows giữ fields này; không dùng extra execution_policy mà reconciler cũ bỏ qua để lách boundary.
Raw current sources, confirmation, policy, B archive và AI/exposure declarations được embed lossless để offline replay; validation report giữ rating_context và independent-agreement eligibility false.
Policy/archive bytes được pin bằng references nên `.gitattributes` thêm `-text` cho sáu packet JSON files, giữ nguyên bytes trên Windows thay vì normalize input để digest khớp.
Core Git checkout probe với `core.autocrlf=true` / `core.eol=crlf` đã giữ nguyên bytes cả 6 files.

Independent agent review tìm hai provenance gaps: adopted B values chưa bind archive và record-level confirmation có thể mâu thuẫn với sheet declaration.
9 regressions đã ghi `9 failed` trước sửa, rồi pass: archive phải qua #170 validators, đủ 21 matched/rated bindings và impact/bounds/rubric/overlap values giống assessment B được tiếp nhận; B source/record confirmation phải giữ đúng relayed adoption.
Không dùng confirmation tiếp nhận số cũ để cho phép sửa source scores hoặc đổi relayed thành direct confirmation; final chosen values vẫn cần decision records riêng.
B AI-only draft không được coi là current human-reviewed sheet; synthetic/AI/exposed sources không được nâng thành declared independent evidence.
Bộ mới có 38 cases, gồm source-class promotion, unconfirmed AI, stale/mismatch policy/confirmation/archive/provenance, policy guards trước #170 và final mapping, adopted score integrity, CLI aliases/refusal/output preservation, offline replay và positive expected/actual/sensitivity.
Initial extension regressions ghi `26 failed` trước implementation; các cases bổ sung kiểm offline/alias/synthetic boundary và hai review findings sau đó được kiểm tra cùng bộ cũ.
`.venv/bin/python -m pytest tests/test_ai_assisted_reviewed_release.py tests/test_reviewed_parameter_release.py -q` đạt `181 passed` (143 cũ + 38 mới).
Independent agent re-review chạy lại `181 passed` và không tìm blocker còn lại; đây không phải B human approval của extension.

Local CLI test dùng source packet thật nhưng **21 dispositions test-only** (test-only reviewer, timestamp năm 2000, chọn source A để kiểm mapping), không ghi final decisions thật vào packet.
Inputs/decisions dùng cùng relative path labels; probe lệch absolute/relative labels bị từ chối bằng stale report digest trước khi xuất, sau đó chạy đúng labels.
Exporter và validator CLI exit 0; report `validation_status: passed`, `human_acceptance: pending`, 21 sensitivity probes.
Source A direct / Source B dùng `[42/125, 171/250]`, effort 2, High; Source A alternative dùng `[588/3125, 29241/50000]`, effort 3, High trong test-only selection.
Distinct B intervals và mọi source values vẫn giữ trong provenance, không auto union/max thành disposition.
Artifacts giữ local ignored tại `reports/generated/171-ai-reviewed-test-only/`, không commit giả làm accepted release.

| Artifact test-only | Raw-byte SHA-256 |
| --- | --- |
| `test-only-decisions.json` | `edddaae2cbab8026ec09d094a47e754dd033a1122c1f8658f222c5621c2529da` |
| `test-only-release.json` | `7999c2bc7506fd8514723eb65388eea00045f03e95eb6f988c41339f6a25d9e5` |
| `test-only-validation.json` | `dacdbda8932a3130ed7a2400075727852d01fb144f7f80596e76633bcc8aa00d` |

Canonical release digest là `sha256:df731a575d65dc24bd07ee66661b2d3c9c13c1bf9bc65926972810fbd92e07e8`; validation report digest là `sha256:314d1ae37ab1285e9b2ee826800b77a7709f212afecec39cc41f21b9a2d261c2`.
Observations áp dụng cho local Python 3.14.2/Linux và relative path labels của run; không thay actual acceptance.
Ruff lint/format, yamllint, contract/repository checks, packet policy preflight, `git diff --check` và Compose config pass.
Không sửa source scores/packet artifacts, pending fixtures, synthetic demo, research helpers/oracles hoặc B-owned engine/parser trong extension diff.
Cập nhật guide, governance và dated acceptance checkpoint; giữ historical text, phân biệt source joint review với independent reliability và numerical acceptance.
Full suite và required Ubuntu/Windows/quality/Compose/branch-policy evidence được ghi theo đúng observations dưới đây hoặc PR description trên pushed head mới.
Chưa tự tạo/approve 21 final dispositions thật, merge #172 hoặc đóng parent issues; integrated Week 3 acceptance vẫn pending.
`.venv/bin/python -m pytest -q` đạt `1471 passed, 1 skipped, 48 subtests passed` trên local Python 3.14.2/Linux; skip là Windows junction test.
