# Review tuần 01 - M0

- Khoảng ngày / người tổng hợp / mentor: Tổng hợp hồi cứu ngày 2026-09-22 cho phạm vi M0/Week 1; TTS A (@Lolavine777).
  Kế hoạch không chốt khoảng ngày lịch của M0; không suy ra khoảng tuần từ ngày ghi log hoặc ngày merge.
  Không có biên bản mentor riêng đủ để xác nhận nghiệm thu trong lần tổng hợp này.
- Link log ngày / issues / PRs: [A 15/09](2026-09-15-ttsA.md), [A 16/09](2026-09-16-ttsA.md), [B 14/09](2026-09-14-ttsB.md), [B 16/09](2026-09-16-ttsB.md), [A 17/09](2026-09-17-ttsA.md), [B 17/09](2026-09-17-ttsB.md).
  Các log này là bằng chứng thực hiện, không phải khẳng định mọi công việc diễn ra trong một tuần lịch duy nhất.

| Cam kết đầu tuần | Bằng chứng | Đạt / chưa đạt | Việc còn lại và người phụ trách |
| --- | --- | --- | --- |
| Hiểu AD objects, domain/OU/GPO, ACL và group nesting | [Inventory](../research/data-inventory.md), [taxonomy lịch sử](../research/taxonomy.md), [#20](https://github.com/nairyuuu/ad-weighted-graph/issues/20), [PR #26](https://github.com/nairyuuu/ad-weighted-graph/pull/26) | Có nghiên cứu và inventory đã merge; phân biệt raw records, unique identity và loại đối tượng thuộc core graph | A: áp dụng amendments #79/#80 trước khi dùng làm đặc tả M2 |
| Mapping bằng chứng của tám quan hệ, giới hạn collector và dữ liệu thiếu | Inventory mục 6-9; [A 16/09](2026-09-16-ttsA.md); [PR #26](https://github.com/nairyuuu/ad-weighted-graph/pull/26) | Có so sánh NORTH/GOADv2 và enterprise-style multi-domain lab `ad_sampledata`; ghi unknown/not-collected/insufficient evidence | A/B: không nâng raw RDU membership thành verified CanRDP; #94 đã cung cấp raw evidence, #79/#80 còn remediation |
| Provenance, phiên bản, file inventory và checksum | [Snapshot manifest](../snapshot-manifest.md), [#27](https://github.com/nairyuuu/ad-weighted-graph/issues/27), [PR #31](https://github.com/nairyuuu/ad-weighted-graph/pull/31), [data policy](../../data/README.md) | Cơ chế manifest deterministic và verify đã merge; raw bytes không commit | Amendment integrity #85/PR #88 đã merge vào develop; #85 đã đóng |
| Môi trường tái lập và kiểm tra CI | [Môi trường](../02_environment.md), [CI](../../.github/workflows/ci.yml), [#18](https://github.com/nairyuuu/ad-weighted-graph/issues/18), [PR #19](https://github.com/nairyuuu/ad-weighted-graph/pull/19), [B 14/09](2026-09-14-ttsB.md) | Runtime Python 3.14 và kiểm tra Ubuntu/Windows được tích hợp; log ghi riêng kết quả cục bộ và CI | B: giữ version pin và dùng môi trường ảo |
| BloodHound observational baseline | [Baseline](../research/bloodhound-import-baseline.md), [#32](https://github.com/nairyuuu/ad-weighted-graph/issues/32), [PR #33](https://github.com/nairyuuu/ad-weighted-graph/pull/33), [PR #36](https://github.com/nairyuuu/ad-weighted-graph/pull/36), [deployment](../../deploy/bloodhound/compose.yml) | Báo cáo A/B, import protocol, counts và ảnh minh chứng đã merge; #32 có comment nghiệm thu/review | B: SEAMLESS same-snapshot baseline là #82, chưa hoàn tất |
| Quyết định evaluation setup | [ADR-0006 lịch sử](../adr/ADR-0006-two-dataset-evaluation-framework.md), [PR #26](https://github.com/nairyuuu/ad-weighted-graph/pull/26) | Đã chốt A/B first-class inputs trong bối cảnh lịch sử; hiện bị supersede | A/B: nguồn chuẩn tắc hiện tại là ADR-0007, không tiếp tục dùng A/B như primary evaluation |

## Demo và phản hồi mentor

Bằng chứng demo đã có nằm trong báo cáo BloodHound và các ảnh được bổ sung qua PR #36.
Báo cáo phân biệt raw occurrences, unique relations và BloodHound-ingested relations; ảnh hỗ trợ quan sát, không thay thế truy vấn/count audit.
Không chạy lại import BloodHound hoặc đo lại historical counts trong phiên tổng hợp này.
Không có cơ sở tuyên bố parity cho SEAMLESS từ các kết quả A/B.
Không cộng số giờ giữa các log, suy diễn ngày demo, hoặc tạo lời nhận xét mentor mới.

| Quyết định / phản hồi | Issue hành động | Owner | Hạn |
| --- | --- | --- | --- |
| Quyết định A/B lịch sử đã được ADR-0007 thay thế bằng SEAMLESS topology và telemetry độc lập | [#55](https://github.com/nairyuuu/ad-weighted-graph/issues/55), [PR #69](https://github.com/nairyuuu/ad-weighted-graph/pull/69) | A/B | Đã merge; không suy diễn ngày mentor họp |
| Giữ provenance trung thực khi không có timezone hoặc collector-version evidence | [#78](https://github.com/nairyuuu/ad-weighted-graph/issues/78), [PR #89](https://github.com/nairyuuu/ad-weighted-graph/pull/89) | A | Đã merge |
| Sửa bốn hash Dataset B bằng canonical bytes, không thay counts hay raw data | [#85](https://github.com/nairyuuu/ad-weighted-graph/issues/85), [PR #88](https://github.com/nairyuuu/ad-weighted-graph/pull/88) | A; B review được yêu cầu | PR #88 đã merge, #85 đã đóng; không có submitted independent approval trước merge |
| Chứng minh baseline SEAMLESS cùng snapshot | [#82](https://github.com/nairyuuu/ad-weighted-graph/issues/82) | B; A review | Trước nghiệm thu đối soát #47 |

### Amendments sau baseline lịch sử

[ADR-0007](../adr/ADR-0007-enterprise-topology-independent-telemetry-evaluation.md) là chiến lược hiện hành: SEAMLESS là primary structural/topology dataset; Windows telemetry là nguồn độc lập cho nghiên cứu semantics/observability.
A/B vẫn hữu ích cho regression, so sánh collector, multi-domain và parser robustness.
[Group-nesting findings](../research/group-nesting-findings.md) và [PR #54](https://github.com/nairyuuu/ad-weighted-graph/pull/54) bổ sung bằng chứng sau baseline M0; direct-only storage và transitive traversal hiện theo ADR-0009.
Không gán lại các kết quả đó thành đầu ra đã có ở thời điểm M0.

#85/PR #88 là integrity amendment về bốn SHA-256 trong inventory Dataset B, không phải thay chiến lược dữ liệu hay revalidation toàn bộ historical counts.
Cập nhật cuối phiên ngày 2026-09-22: PR #88 đã merge vào `develop` tại `ebe92e6`; #85 đã đóng.
Amendment xác minh extracted-file bytes, không chứng minh archive ZIP hash hoặc revalidate historical counts.
Phần provenance SEAMLESS/telemetry của #78/PR #89 đã merge và là công việc khác.
PR #96 đã merge vào `develop` tại `a90a57c` và #83 đã đóng; boundary cost và RODC/DCSync hiện theo ADR-0008/PR #96.

### Process exception

PR #88 đã được technical-rereview và CI xanh nhưng không có submitted independent approval từ người còn lại trước merge, nên không được dùng như bằng chứng process-complete cross-review.
Closure này giữ nguyên sự kiện đó và yêu cầu post-merge cross-audit nếu muốn khép khoảng trống review-evidence.

## Tuần tới và rủi ro

M0 có bằng chứng nghiên cứu và deliverables lịch sử đã tích hợp; tài liệu review tuần được bổ sung hồi cứu trong PR hiện tại và chưa đồng nghĩa mentor sign-off mới.
[Audit closure](../research/week-01-02-closure-audit.md) ghi disposition của các issue cũ và successor.
M1 tiếp nhận inventory để chốt structural schema và nguồn bằng chứng; không coi edge là technique hoặc suy thiếu dữ liệu thành false.
M2 đã nhận #94 raw-field audit qua PR #99 tại `e4b7a1e`; #79/#80 còn phải áp dụng findings vào behavior và reporting.
#81 semantic provenance, #82 baseline và #92/#97 canonical representation decisions vẫn mở theo phạm vi tương ứng.

## Current-state amendment - 2026-09-23

M0 / Week 1 được coi là technically complete theo phạm vi lịch sử: môi trường Python/CI, data inventory, deterministic snapshot manifest và historical BloodHound A/B baseline đều có artifact tái lập và evidence merge.
Mentor feedback sau đó làm ADR-0007 supersede A/B như primary M2 evaluation strategy; thay đổi này tạo successor work chứ không reopen M0.
SEAMLESS hiện là primary structural/topology dataset cho M2+, còn A/B giữ vai trò regression, collector-comparison và historical BloodHound reference.
#82 vẫn open để tạo SEAMLESS BloodHound CE same-snapshot baseline trước các parity/reconciliation claims trong M2; đây là M2 evaluation gap, không phải M0 failure.
#79, #80 và #81 hiện đã closed sau các truth-migration/remediation follow-up.
#44 cũng đã closed sau final acceptance audit của merged PR #104.
Các process exception đã ghi cho PR #88 vẫn được giữ nguyên; amendment này không tạo retroactive approval hoặc mentor sign-off.
