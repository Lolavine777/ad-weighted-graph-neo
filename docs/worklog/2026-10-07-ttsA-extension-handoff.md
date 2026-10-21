# Worklog - 2026-10-07 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#200](https://github.com/nairyuuu/ad-weighted-graph/issues/200), [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192), [PR #217](https://github.com/nairyuuu/ad-weighted-graph/pull/217); M3 / extension research sau feedback.
- Thời gian thực tế ước lượng: khoảng 30 phút kiểm review/merge và chuẩn bị handoff; không dùng làm attack effort C.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Nghiệm thu PR nghiên cứu | [B review exact head](https://github.com/nairyuuu/ad-weighted-graph/pull/217#pullrequestreview-5431341333), GitHub reviews/check-runs/mergeability | APPROVED trên `989b09d`; tám check runs success, không review thread; merge `4c1f80511fb9ec81606622fafda563bdab4bc8ad` vào develop |
| Scenario/oracle độc lập | [Bộ ca extension](../research/week4-extension-scenario-handoff.md) | AS-REP/RBCD positive/blocked/unknown/counterfactual; finite minimal programs/states và gate/effect cutoffs; chưa chạy generator extension |
| Ownership và dependencies | #211–#216 đối chiếu issue hiện hành; handoff mục 7 | Giữ B tasks #215/#216, core song song; chưa assign B hoặc thay thứ tự triển khai; RBCD còn gate P authorization |
| Mentor narrative | [Bản ngắn](../research/week4-prediction-proposal.md) | Sửa không có AD identity thành chưa có credential/control dùng được nhưng biết/đoán target; approval research không là mentor approval |
| Validation tài liệu | `python scripts/check_repository.py`, `python scripts/check_contract.py`, `git diff --check`; kiểm oracle logic độc lập và privacy | PASS trên Python 3.12.14: repository 440 files, contract + 2 fixtures; enumeration độc lập AS-REP 1 program/6 states, RBCD 3 programs/8 states, 5 veto cutoffs giữ prefixes độc lập. Diff chỉ tài liệu/alias; CI kiểm Python 3.14 và suite toàn repo trên PR mới |

## Điều học được / quyết định

Tách review kết quả sàng lọc khỏi quyết định triển khai. AS-REP cần target knowledge và KDC dù không cần initial AD credential; RBCD cần service principal acquisition, descriptor creation, delegated context và quyền thực thi cuối riêng. Descriptor write có thể độc lập với acquisition M; oracle không chỉ có một ordered path.

Ca Kerberoasting có baseline reset overlap nên thêm route không tự mở asset mới. B đã có #215 fact layer và #216 Kerberoasting: handoff cung cấp expectations/reuse, không nhận phần implementation của B. Không copy ratings Week 3 cho recovery; exact Fraction không giải quyết concern P nhỏ về nghĩa.

## Trở ngại và việc kế tiếp

#200/#192 vẫn open: #217 chỉ được nhận research/evidence; handoff mới cần B review. Snapshot không có runtime recovery hoặc P authorization trên C_R; positive là synthetic/scenario branch. Không chạy lại raw pipeline giống lượt trước và không thay parser/engine/contract/catalog/ratings.

1. B review ca, scope và mapping/API rồi tự nhận lát integration phù hợp; A freeze executable inputs/expected sau handoff.
2. A kiểm actual và baseline delta khi có implementation; giữ unknown/unrated/truncation rõ.
3. Core #204/#206–#208 và #211–#213 tiếp tục độc lập; cập nhật bản mentor sau scope review.
