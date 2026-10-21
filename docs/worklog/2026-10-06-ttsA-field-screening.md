# Worklog - 2026-10-06 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#200](https://github.com/nairyuuu/ad-weighted-graph/issues/200), [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192), [PR #217](https://github.com/nairyuuu/ad-weighted-graph/pull/217); M3, feedback đầu Week 4.
- Thời gian thực tế ước lượng: khoảng 30 phút sàng lọc ban đầu, thêm khoảng 90 phút raw/tái lập/truy chuỗi/sửa kết luận; lượt khôi phục workspace thêm khoảng 20 phút. Không gồm audit #201, không dùng thời gian này làm attack effort C.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Sàng lọc từ field | [Phụ lục](../research/week4-field-driven-screening.md) | Đủ 40 dòng conditions/effects/dispositions; thêm owner/DCOM/LAPS/mapping ExtendedRight, không biến thành 40 cạnh |
| Raw và pipeline | [Nguồn/checksum/lệnh](../research/week4-screening-raw-verification.md) | Sáu raw files từ GitHub khớp manifest, issues=[]; audit 195 fields; parser 3.370 nodes/56.367 edges, 3 unknown assessments, 0 warnings/errors |
| Truy holders/prefix/scope | [Probe read-only](../../scripts/research/field_screening_probe.py) | 15.917 membership pairs khớp canonical, giữ duplicate records; AS-REP AdminTo C0, RBCD SPN acquisition prefix, Kerb baseline overlap, GPO/owner/DCOM/DCSync/delegation |
| Narrative và ưu tiên | [Bản ngắn](../research/week4-prediction-proposal.md), [amendment](../research/week4-prediction-evidence.md) | AS-REP trước, RBCD review kế tiếp; Kerb cần đối chứng/đổi ca; chưa gửi bản sửa cho mentor |
| Scope prediction/ranking | Phụ lục mục 5–6, raw verification | Initial state → tự sinh bước → asset; unknown/blocked và unique work units; chưa đo extension coverage hoặc recovery probability |
| Kiểm chứng local cuối | Ruff check/format, yamllint, check_repository/check_contract, pytest; probe guards/privacy; git diff --cached --check | PASS: 1.823 tests, 7 skipped (telemetry raw, Windows junction, dataset khác); assertions raw/privacy và 3 negative guards PASS. CI kiểm head cuối trên PR, không dùng run của head cũ |

## Điều học được / quyết định

Không dừng ở evidence cũ khi raw tải lại được từ nguồn đã biết. RBCD có candidate lấy SPN principal từ quyền thật; ca Kerberoasting chưa chứng minh mở đường mới vì nhiều initial users có cùng prefix reset. Mapping AdminTo của AS-REP tới DC đã có, nhưng cấu trúc không thay thành công thực thi.

Owner/GPO holders đã đặc quyền, DCOM còn COM context/authorization; AllExtendedRights là mapping gap cho quyền sẵn có. Field/edge count không thay counterfactual trên cùng initial state và asset goal.

## Trở ngại và việc kế tiếp

Raw verification đã xong; runtime/auth/recovery/delegation/endpoint facts còn unknown hoặc giả định cần review. Workspace bị thay thế trước khi push; đã khôi phục source đúng pin/hash, lấy lại raw và rerun probe. Không chạy exploit/crack hoặc sửa engine/parser/catalog/ratings.

1. B review conditions/state/effect và AS-REP/RBCD; #174 vẫn thuộc B.
2. A/B chốt 1–2 chuỗi có input/oracle/asset goal, tách integration tasks theo ownership; đo coverage sau implementation.
3. Core #204, A #206–#208 và B #211–#213 tiếp tục song song; CI không là acceptance kỹ thuật mới.
