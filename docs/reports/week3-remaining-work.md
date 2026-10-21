# Kiểm kê cuối Week 3 - 2026-10-06

**Technical handoffs đã accepted; fresh Legacy replay & final revision binding đã hoàn tất bởi B; package #48/#158 đã accepted.**
Revision được đo: `develop@891bda0001b9958e712cff54045f651273b43fd0`.
[Final handoff](week3-final-handoff.md) và [manifest](../../reports/research/week3-final-handoff.json) là current source of truth cho pins, actual E2E, accepted reconciliation, fresh Legacy replay binding và demo commands.
#155/#180 integration, #47 reconciliation và #196 A/B reproduction đã closed; không giao lại model/rating/parser/engine/comparator work.

| Gate | Trạng thái | Owner / Exit evidence |
| --- | --- | --- |
| Final integrated Legacy replay/binding của #48 | **Satisfied** | B đã chạy fresh replay trên `891bda0` với authorized private prerequisites; graph `code_version` và report `head_commit` khớp `891bda0`; exact sets, 20 differences và comparator CLI exit 2 khớp tuyệt đối #196 |
| Focused closeout acceptance #48/#158 | **Accepted bởi B** | B đã review và chấp thuận package trên exact head; sẵn sàng merge vào `develop`; #48/#158 và scoped #143/#42 sẵn sàng đóng sau merge |
| Promotion #186 | **Pending merge #202** | A/B final release review trên release branch sau khi PR #202 merge vào develop; required CI, full release diff và xử lý outstanding `CHANGES_REQUESTED` |

Final binding, CI/branch policy trên package head `3c35667` và [technical acceptance của B](https://github.com/nairyuuu/ad-weighted-graph/pull/202#issuecomment-6008927093) đã hoàn tất.
Các actions còn lại: merge #202 sau rereview current state/checks của head mới; đóng #48/#143/#42/#158 theo live merged evidence; final release review #186; promote `develop → main` bằng merge commit nếu approval/checks đạt.

Full Legacy comparator vẫn `NOT_MEASURABLE` / exit 2; không claim global optimum hoặc full BloodHound/CE parity.
Week 4 #192/#200 và Top-K/scalable search/choke points nằm ngoài closeout.

<details>
<summary>Checkpoint 2026-10-03 và prompt B cũ, đã superseded; giữ để truy vết</summary>

## Kiểm kê Week 3 ngày 2026-10-03

## Trạng thái chung

**Week 3 đang nghiệm thu cuối; release/supplied-candidate replay đã có bằng chứng.**
Không cần mở lại mô hình hoặc chọn lại 21 tham số để tái lập phép tính.
[Disposition](../research/week3-rating-requirement-disposition.md) tiếp nhận cơ sở human-reviewed AI-assisted cho kịch bản Week 3; không yêu cầu thêm lượt chấm.
Full product acceptance vẫn theo [tracker #158](https://github.com/nairyuuu/ad-weighted-graph/issues/158).

Revision A fetched và thực chạy: `develop@d8e0b28be2afd5b1807082283efd4db01fad3240`, Python 3.14.7.
#176 release/báo cáo, #146 foundation/search và #167 adapter/orchestration đã merge; #145 đóng trong scope foundation, #46/#128 đã nghiệm thu parser CLI/rich synthetic demo.
Không giao lại việc review/implement các foundation đã được tiếp nhận.
#130 vẫn OPEN/CHANGES_REQUESTED tại head `32a9b49573b09431ec13f6a6e823923ed366e164` trong lần kiểm tra này; đây là gate Legacy riêng.

## Đã có bằng chứng

- Thiết kế/interface/scenario đã được tiếp nhận; Graph Contract 1.3.0, ranking 1.0.0 và semantic catalog 0.2 có implementation.
- 21 lựa chọn có actual [reviewed release](../research/ratings/week3-closeout/README.md), bindings/digests/rationale; source class/exposure giữ trung thực, không tuyên bố independent agreement.
- A #177 verify và chạy lại release trên engine hiện hành; hai query/ba chương trình khớp oracle: C=2/3/2, P exact không đổi, I=High; Pareto A incomparable, separate Min-Effort chọn Lidia trong supplied set.
- Validation report/file digests không đổi; 21 probes/24 outcomes giữ frontier/relations/winner identities, 6 outcomes đổi giá trị Min-Effort.
- [Ma trận](week3-acceptance-matrix.md) và [manifest](../../tests/fixtures/ranking/week3_acceptance_cases.json) pin 8 ca: positive A/B, false A/B, runtime unknown A/B, missing structural và missing telemetry ở A.
- Replay negative đã chạy và giữ false veto/unknown đúng layer, C/P=null cho candidate liên quan; mọi actual search E2E vẫn `not_run`.
- Synthetic regressions hiện có sở hữu mapping, sparse/derived lineage, first-goal, ranking và caps; không suy real E2E acceptance từ chúng.

## Còn việc gì, ai làm và khi nào xong

| Việc | Chủ trì | Điều kiện hoàn tất / phụ thuộc |
| --- | --- | --- |
| Review handoff #177 | B review, A xử lý | Ma trận/manifest, expected/actual/digests và report; CI/review đúng head; không chờ B xong toàn E2E mới nghiệm thu phần A |
| Release-consuming search E2E #155 → #48 | B gói chạy, A review | Raw/parser → actual bounded generator → ordered bindings → adapter → rank, verified projections/overlays, exact traces/oracle/coverage, commands và deterministic outputs |
| Accepted Legacy exports #82/#130/#139 | B | Xử lý evidence findings, importer/write-error, Group/boundary identity và Base-only query; same-snapshot node/edge exports/mapping có digest/review |
| Real reconciliation #47 | A sau handoff B, B review | Comparator hiện có; full differences/multiplicity/raw traces/dispositions; counts/synthetic coverage không thay evidence thật |
| Final reproduction #48 | A/B | Một integrated revision, runtime/dependencies/input versions; clean-checkout cross-reproduction, synthetic tự chạy, raw prerequisites rõ; checks/review đạt |
| Tài liệu/báo cáo cuối | A/B | Bổ sung actual E2E verdict/coverage và real reconciliation sau chạy; không claim complete từ release replay/CI |

#164/#171 đã đóng trong scope tooling; #143/#155/#158/#48 giữ mở cho nghiệm thu còn thiếu.
M3 #174/#175, Top-K/scalable search/choke points và CE parity không thêm vào gate Week 3.
B sở hữu `docs/research/engine-ranking-integration.md` và harness/commands; A không cùng sửa file đó.

## Ưu tiên kế tiếp

**B chạy gói #155/#48 ngay bằng ma trận/manifest đã pin; không cần đợi Legacy.**
A review gói chạy thật và tái lập chéo khi B bàn giao, rồi chạy #47 sau accepted Legacy exports.
Phần A #177 complete sau review handoff; Week 3 chưa complete trước E2E, real reconciliation và final reproduction.

### Prompt bàn giao cho agent B

```text
Repo nairyuuu/ad-weighted-graph, vai trò TTS B, branch riêng từ develop mới nhất.
Hoàn tất release-consuming #155/#48; đọc CONTRIBUTING, instructions, #158 và docs/reports/week3-acceptance-matrix.md.
Foundation #146/#167 đã merge; không viết lại evaluator/model/ratings.
Consume docs/research/ratings/week3-closeout/reviewed-release.json sau verify_release, giữ source_a/source_b thành hai query.
tests/fixtures/ranking/week3_acceptance_cases.json pin 8 ca, bindings, overlays, expected/actual replay và typed search bindings.
Không reseal overlays hoặc biến counterfactual thành observations.
Resolve false trước RuntimeContext, giữ ledger gốc trong audit; unknown không default true/điền số.
Missing evidence phải rút ở search graph/context tương ứng, có delta locator/digest.
Cung cấp executable raw/parser -> actual generate_attack_paths -> ordered binding -> evaluate_search_candidates; giữ success event, full-history ratings, exact structural/derived lineage.
Chạy positive/false/unknown, so oracle rational và program bindings; path mới thiếu rating giữ unrated.
Ghi actual caps/counters/truncation/coverage, hai deterministic runs, revision/runtime/digests và full ignored outputs.
Supplied replay không thay search E2E.
Chạy checks, ghi worklog, cập nhật integration/harness do B sở hữu và mở PR vào develop cho A review.
Legacy làm song song; #47 chờ accepted same-snapshot exports.
Không đóng #48/#158 hoặc claim Week 3 complete trước real reconciliation và clean-checkout cross-reproduction.
```

## Gói nghiệm thu cần lưu

Manifest hiện lưu expected và actual replay riêng với `actual_search_e2e.verdict=not_run`.
B lưu actual search trong gói evidence mới có command, output locator/digest, revision, caps và trace; không dùng supplied-candidate digests thay search output.
Final package cần full real Legacy differences/dispositions, hai deterministic runs và cross-reproduction từ clean checkout.

</details>
