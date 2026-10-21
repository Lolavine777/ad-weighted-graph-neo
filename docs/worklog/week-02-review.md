# Review tuần 02 - M1

- Khoảng ngày / người tổng hợp / mentor: Phạm vi M1, các issue #1-#10 ghi hạn 2026-09-14 đến 2026-09-18; tổng hợp hồi cứu ngày 2026-09-22 bởi TTS A (@Lolavine777).
  Hạn kế hoạch không phải timestamp hoàn thành thực tế; không có biên bản mentor riêng để ghi nhận sign-off mới.
- Link log ngày / issues / PRs: [A 14/09](2026-09-14-ttsA.md), [B 15/09](2026-09-15-ttsB.md), [A 16/09](2026-09-16-ttsA.md), [B 16/09](2026-09-16-ttsB.md), [A 17/09](2026-09-17-ttsA.md), [B 17/09](2026-09-17-ttsB.md), [A 18/09](2026-09-18-ttsA.md).

| Cam kết đầu tuần | Bằng chứng | Đạt / chưa đạt | Việc còn lại và người phụ trách |
| --- | --- | --- | --- |
| Taxonomy đủ tám quan hệ, hướng source/target và nguồn tham chiếu | [#1](https://github.com/nairyuuu/ad-weighted-graph/issues/1), [#2](https://github.com/nairyuuu/ad-weighted-graph/issues/2), [#3](https://github.com/nairyuuu/ad-weighted-graph/issues/3), [#4](https://github.com/nairyuuu/ad-weighted-graph/issues/4), [#5](https://github.com/nairyuuu/ad-weighted-graph/issues/5), [PR #17](https://github.com/nairyuuu/ad-weighted-graph/pull/17), [taxonomy](../research/taxonomy.md) | Baseline M1 đã được review và merge; nội dung lịch sử không phải toàn bộ normative truth hiện nay | A: #79 Phase B áp dụng accepted evidence matrix; #83/PR #96 đã chuẩn hóa trạng thái ADR |
| Bảng cạnh - kỹ thuật - độ khó cho tám relationship M1 | [Artifact tổng hợp](../research/edge-technique-difficulty.md), dựa trên [taxonomy](../research/taxonomy.md), [semantic catalog](../../configs/attack_semantics.yml) và [evidence audit](../research/m1-evidence-audit.md) | Có bảng đọc độc lập, phân biệt structural relationship, transition, điều kiện và difficulty drivers; không công bố production weights | #42 sở hữu quyết định cost production |
| Mapping thuộc tính nguồn và giới hạn bằng chứng | [Inventory](../research/data-inventory.md), [PR #26](https://github.com/nairyuuu/ad-weighted-graph/pull/26), [ADR-0003 amended](../adr/ADR-0003-host-access-inference-policy.md), [host-access audit](../research/host-access-semantics-audit.md) | Có historical A/B mapping và host-bound evidence boundary | B: #80 còn schema/completeness và EDA remediation sau accepted #94; không suy verified CanRDP từ raw RDU array |
| Schema node, canonical identity, edge IDs, multigraph và provenance | [#6](https://github.com/nairyuuu/ad-weighted-graph/issues/6), [PR #24](https://github.com/nairyuuu/ad-weighted-graph/pull/24), [#7](https://github.com/nairyuuu/ad-weighted-graph/issues/7), [PR #25](https://github.com/nairyuuu/ad-weighted-graph/pull/25), [contract](../../configs/contract.yml), [validator](../../scripts/check_contract.py) | Deliverables lịch sử đã merge; contract hiện hành được freeze qua PR #67 | B: canonical ordered lineage #92 và timestamp status #97 là successor scope |
| Parser interfaces và error policy | [#8](https://github.com/nairyuuu/ad-weighted-graph/issues/8), [PR #28](https://github.com/nairyuuu/ad-weighted-graph/pull/28), [architecture](../03_architecture.md), [parser types](../../src/parser/__init__.py) | Có RawDataLoader, Normalizer, GraphBuilder interfaces và error policies; không đồng nghĩa builder M2 đã triển khai | B: #44/#45/#47 chỉ tiếp tục sau dependency gates |
| Synthetic fixtures và CI structural validation | [#9](https://github.com/nairyuuu/ad-weighted-graph/issues/9), [PR #29](https://github.com/nairyuuu/ad-weighted-graph/pull/29), [#10](https://github.com/nairyuuu/ad-weighted-graph/issues/10), [fixture](../../data/samples/m1-fixtures.json), [tests](../../tests/test_m1_fixtures.py) | Đã tích hợp; #10 có comment nghiệm thu và CI Ubuntu/Windows được dẫn nguồn | A/B: không khôi phục disabled-terminal invariant đã bị PR #90 loại bỏ |
| Cross-review và closure bookkeeping | [PR #17 reviews](https://github.com/nairyuuu/ad-weighted-graph/pull/17), [B 15/09](2026-09-15-ttsB.md), [A 16/09](2026-09-16-ttsA.md), [#30](https://github.com/nairyuuu/ad-weighted-graph/issues/30), [PR #35](https://github.com/nairyuuu/ad-weighted-graph/pull/35), [#40](https://github.com/nairyuuu/ad-weighted-graph/issues/40), [PR #39](https://github.com/nairyuuu/ad-weighted-graph/pull/39) | PR #17 có approval của B; schema/parser/fixture feedback có trong log; PR #35 và PR #39 đã merge | Review tuần bổ sung hồi cứu chờ review; không tạo mentor approval giả |

## Demo và phản hồi mentor

Bằng chứng M1 gồm contract validation, synthetic fixtures và các review có thể truy vết qua PR/log ở trên.
PR #17 có yêu cầu sửa MAUT probability claims, host-bound inference và Python baseline, sau đó được @nairyuuu approve tại commit `3196e68`.
Approval lịch sử đó bao gồm các quyết định sau này bị supersede; không dùng nó làm approval cho production weighting hoặc synthetic goal edges hiện nay.
#10 ghi nghiệm thu tại commit `ea8fa7a` với [CI run](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/35056272184).
Không chạy lại một demo M1 lịch sử hoặc ghi nhận mentor feedback mới trong phiên này.

| Quyết định / phản hồi | Issue hành động | Owner | Hạn |
| --- | --- | --- | --- |
| Tách structural relationship, attack technique và observed activity | [#70](https://github.com/nairyuuu/ad-weighted-graph/issues/70), [PR #73](https://github.com/nairyuuu/ad-weighted-graph/pull/73), [ADR-0008](../adr/ADR-0008-structural-graph-attack-semantics-layering.md) | A/B | Đã accepted/merged |
| Direct MemberOf được lưu; transitive membership giải ở traversal/query | [#71](https://github.com/nairyuuu/ad-weighted-graph/issues/71), [PR #74](https://github.com/nairyuuu/ad-weighted-graph/pull/74), [ADR-0009](../adr/ADR-0009-direct-memberof-transitive-resolution.md) | A/B | Đã accepted/merged |
| Identity/Asset/ControlPlane là semantic facets, không thêm structural node kind | [#72](https://github.com/nairyuuu/ad-weighted-graph/issues/72), [PR #75](https://github.com/nairyuuu/ad-weighted-graph/pull/75), [ADR-0010](../adr/ADR-0010-identity-asset-semantic-facets.md) | A/B | Đã accepted/merged |
| Giữ structural rights của disabled accounts; composite CanRDP và runtime separation | [#80](https://github.com/nairyuuu/ad-weighted-graph/issues/80), [PR #90](https://github.com/nairyuuu/ad-weighted-graph/pull/90) | B; A review | Semantics accepted; raw-field/EDA carry-over còn mở |
| Audit tám quan hệ theo sáu lớp, sau đó remediation | [#79](https://github.com/nairyuuu/ad-weighted-graph/issues/79), [PR #93](https://github.com/nairyuuu/ad-weighted-graph/pull/93), [evidence matrix](../research/m1-evidence-audit.md) | A; B review | Phase A accepted; Phase B chưa hoàn tất |
| Chuẩn hóa ADR legacy và cost/RODC boundaries | [#83](https://github.com/nairyuuu/ad-weighted-graph/issues/83), [PR #96](https://github.com/nairyuuu/ad-weighted-graph/pull/96) | A; B review được yêu cầu | PR #96 đã merge tại `a90a57c`, #83 đã đóng; không có submitted independent approval trước merge |

### Amendments và nguồn chuẩn tắc hiện hành

[ADR-0007](../adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md) thay ADR-0006: SEAMLESS topology cộng telemetry độc lập, không entity-level join chéo môi trường và không calibration production weight từ corpus đó.
ADR-0008 đặt [semantic catalog](../../configs/attack_semantics.yml) làm nguồn runtime semantics; expected telemetry gắn với technique/transition, không phải thuộc tính mặc định của structural edge.
Passive MemberOf không phải hành vi thêm/xóa thành viên và không có dedicated group-modification telemetry.
HasSession là session observation/opportunity, không đảm bảo credential dumping.
Theo accepted #80, disabled account không làm mất structural rights; ports/services/authentication là runtime gates.
CanRDP cần effective RDU membership AND allow-right AND NOT deny-right; raw membership không đủ.

Graph Contract 1.0.0 giữ tám structural relationships và trọng số hữu hạn tối thiểu 1.0; không có DCSync/ControlsDomain/DumpNTDS structural edges.
`unit` là baseline M2 correctness; `maut_v1` là historical experimental profile, không phải production truth.
`cost_factors` chỉ là descriptive research input; #83 đã đóng, còn #79 Phase B và successor decision về cost ownership phải hoàn tất trước #42 implementation.
PR #51 không phải implementation được chấp nhận để áp dụng lại.
ADR-0001/0002/0004 status reconciliation trong PR #96 đã merge vào `develop` tại `a90a57c`; current normative reading dùng trạng thái đã reconciled.

### Process exception

PR #96 đã được technical-rereview, resolve toàn bộ finding và CI xanh trước merge nhưng không có submitted independent approval từ người còn lại.
DoD process gap này được ghi rõ thay vì coi self-review là cross-review; cần post-merge cross-audit nếu muốn khép review-evidence.

## Tuần tới và rủi ro

M1 historical deliverables và cross-review có bằng chứng; Week 2 review hiện bổ sung phần bookkeeping còn thiếu, chưa tuyên bố truth migration hoàn tất.
[Closure audit](../research/week-01-02-closure-audit.md) giữ issue history và chỉ rõ successor ownership.
#79 Phase B còn taxonomy/narrative alignment, EDA descriptive inventory và telemetry mapping provenance; raw-field findings từ #94/PR #99 đã được accepted để dùng cho remediation, còn schema provenance mapping thuộc #81.
#80 còn raw RDU versus verified CanRDP reporting/regression và schema mapping follow-up.
#92 chặn derived-edge lineage serialization; #97 chặn canonical output cho policy-resolved collection time; #82 chặn SEAMLESS same-snapshot reconciliation.
Không bắt đầu #44/#45/#47/#48 hoặc production #42 trong phiên closure này.

Cập nhật cuối phiên 2026-09-22: #91 đã đóng theo loader scope; #94 findings khi đó còn ở PR #99 và chưa accepted.
Cập nhật 2026-09-23: PR #99 đã được independent review và merge tại `e4b7a1e`; #94 đã đóng, còn #79/#80 phải áp dụng evidence vào EDA/report và schema mapping.

## Current-state amendment - 2026-09-23

M1 / Week 2 được coi là technically complete theo deliverables của project plan: taxonomy/evidence boundaries, node/edge schema, canonical identity, provenance, parser interfaces/error policy, synthetic fixtures và CI structural validation đều đã được tích hợp.
Các truth-migration issues #79, #80 và #81 hiện đã closed; những đoạn phía trên mô tả chúng còn mở phản ánh state tại thời điểm retrospective review và không còn là live blocker list.
Direct-edge implementation #44 đã merge qua PR #104 và được final-audit/closed; đây là M2 work được hoàn thành sớm, không thay đổi mốc lịch sử của M1.
Current M2 gates gồm #42 weighting successor decision, #45 host-access inference, #92 derived-edge lineage, #97 canonical collection-time status, #82 SEAMLESS same-snapshot BloodHound baseline, rồi #46/#47/#48 integration và handoff.
PR #107 đang thuộc M2 host-access/lineage scope và không phải evidence rằng M1 còn thiếu.
Process exceptions đã ghi trong review lịch sử vẫn giữ nguyên và không được amendment này biến thành approval hồi tố.

## Định hướng trọng số / handoff Week 3 - 2026-09-24

[Weighting direction](../research/weighting-direction.md) tổng hợp trạng thái hiện hành và các quyết định cost còn thuộc #42.
