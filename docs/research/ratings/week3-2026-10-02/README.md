# Phiếu chấm Week 3 — A và B

Refs #143, #158, #48; đối soát dùng công cụ đã merge từ #170. Bộ phiếu hiện tại đã được tiếp nhận trong lượt xác nhận chung của A/B. B đang làm việc cùng A và được A chuyển đạt xác nhận lúc 14:05:23 UTC+07 ngày 2026-10-02, đồng thời ủy quyền sửa và thống nhất tài liệu. Đây là review có AI hỗ trợ và công bố việc tiếp xúc điểm A; không khai báo chấm mù độc lập.

## Nguồn sự thật và trạng thái

| Tài liệu | Vai trò hiện tại |
| --- | --- |
| [rater-A.json](rater-A.json) | 21 lựa chọn A đã chốt trước đó; cập nhật metadata lượt review chung, giữ nguyên điểm và xác nhận ban đầu |
| [rater-B.json](rater-B.json) | 21 giá trị của bản AI được B tiếp nhận qua xác nhận do A chuyển đạt; đã thống nhất điều kiện thực hiện |
| [shared-review-confirmation.json](shared-review-confirmation.json) | Phạm vi ủy quyền, cách chuyển đạt, thời điểm, exposure và nguồn gốc hai phiếu |
| [execution-policy.json](execution-policy.json) | Chính sách chung có phiên bản, được cả hai phiếu tham chiếu bằng SHA-256 |
| [rater-B-ai-draft.json](rater-B-ai-draft.json) | Bản AI gốc nguyên byte; chỉ là lịch sử, không đưa vào đối soát thay phiếu B hiện tại |
| [verification-summary.json](verification-summary.json) | Kết quả kiểm tra hiện tại cùng digest đầu vào, phép tính và giới hạn kiểm chứng |

Không còn chờ B chấm/xác nhận nguồn điểm cho lượt này. Còn quyết định tham số cuối, hỗ trợ phân loại bằng chứng trong exporter #171 / [PR #172](https://github.com/nairyuuu/ad-weighted-graph/pull/172), kiểm tra độ nhạy và nghiệm thu tích hợp. Việc tiếp nhận hai phiếu không tự đóng #143/#158/#48.

## Chính sách thực hiện chung

Horizon toàn chiến dịch là 24 giờ; thời hạn dưới đây áp dụng cho từng bước, tính từ lần thử đầu tiên. Tối đa 3 lần thử tổng cộng. Success event phải hoàn tất trước thời hạn; không chuyển một bước hết hạn thành thành công chỉ vì campaign còn thời gian.

| Cơ chế | Số lần thử tối đa | Thời hạn bước | Số bản ghi likelihood |
| --- | ---: | ---: | ---: |
| Reset mật khẩu | 3 | 15 phút | 4 |
| Lấy vé Kerberos | 3 | 10 phút | 4 |
| Thực thi quản trị qua WinRM | 3 | 30 phút | 3 |

Chính sách nối với [đề xuất cơ sở tham số](../../seamless-parameter-basis-proposal.md) và bounded retry trong [governance](../../evidence-rating-governance.md). Đây là điều kiện của câu hỏi chấm. Engine hiện nhận các q_i đã được điều kiện hóa theo chính sách; không mô phỏng lịch retry hoặc timeout. Phần packet giữ mô hình monotonic/horizon 24h không mâu thuẫn với thời hạn cho câu hỏi chấm.

Mỗi q_i vẫn giữ đầy đủ query, scenario/version, foothold, snapshot, lịch sử và hành động kết quả. Không dùng lại prerequisite đã conditioning true làm nguồn thất bại. Khoảng bằng nhau giữa các ngữ cảnh vẫn là các nhận định riêng; không dùng xác suất biên theo loại cạnh.

B giữ các khoảng rộng ban đầu sau khi áp dụng điều kiện chung theo phạm vi ủy quyền. Đây là việc tiếp nhận một nhận định kịch bản, không phải công thức chuyển xác suất 24 giờ sang xác suất 10/15/30 phút. Không có dữ liệu hiệu chuẩn; nguồn Microsoft/RFC chỉ hỗ trợ cơ chế. Cần kiểm tra độ nhạy của các khoảng này khi đánh giá bộ tham số cuối.

## Đối soát và các khác biệt được giữ

| Nhóm | A | B |
| --- | --- | --- |
| Tác động mục tiêu | High | High |
| Reset, khoảng q_i | [7/10, 9/10] | [3/5, 19/20] |
| Lấy vé, khoảng q_i | [4/5, 19/20] | [3/4, 49/50] |
| WinRM, khoảng q_i | [3/5, 4/5] | [1/2, 9/10] |
| Công sức reset / lấy vé / WinRM | C = 1 / 0 / 1 | C = 1 / 0 / 1 |

Đối soát hiện tại: 21 cặp khớp và đủ điểm, 0 unmatched, 21 đề xuất đồng thuận, 0 bất đồng theo ngưỡng của helper, 0 overlap withheld. Mean IoU = 0.5813099943534726, effort delta = 0. Một cặp impact cùng High làm Kappa không xác định (`degenerate_zero_variance`); không diễn giải thành độ tin cậy hoàn hảo.

Các chỉ số mô tả hai artifacts đã được tiếp nhận; không đo độ tin cậy của hai người chấm mù. `complete_all_reconciled` và danh sách pending rỗng không thay cho quyết định tham số cuối. Không tự hợp nhất các cận số trong source sheets để làm chúng giống nhau.

## Cách kiểm tra lại

Chạy từ root repository:

```bash
python scripts/research/check_week3_rating_policy.py
python scripts/research/reconcile_rating_sheets.py --sheet1 docs/research/ratings/week3-2026-10-02/rater-A.json --sheet2 docs/research/ratings/week3-2026-10-02/rater-B.json --output reports/generated/week3-ratings-reconciliation.json --summary
```

Lệnh đầu so sánh chính sách cho đủ 11 câu hỏi, kiểm digest policy và bản B gốc. Lệnh thứ hai kiểm cấu trúc/bindings, đối soát số và tạo proposals. Reconciler hiện chưa so sánh `execution_policy`, nên cần preflight trước; preflight không xác minh danh tính hoặc sự hiện diện của B. Bằng chứng xác nhận là thông tin A cung cấp trong phiên này, được ghi trung thực tại confirmation record.

## Kỹ thuật tính và luồng công việc

Con người tiếp nhận/chọn nhận định; AI hỗ trợ đọc tài liệu, giải thích và biên soạn. Script kiểm bindings và chính sách, helper tính IoU/chênh lệch công sức và đề xuất; các hàm không tìm ra xác suất thực nghiệm từ snapshot AD. Dữ liệu cấu trúc → attack semantics → kịch bản và outcome → câu hỏi q_i/công sức/impact → phiếu chấm → đối soát → dispositions có lý do → bundle có phiên bản → độ nhạy và canonical engine → báo cáo/slide nghiệm thu.

Công sức tính `C = T1 + T2 - 2`, cộng các work units riêng sau foothold, không tính lại setup chung hoặc passive membership closure. Số units là 9 (4 reset, 3 lấy vé, 2 WinRM); số câu hỏi likelihood là 11 (4/4/3), do ngữ cảnh query/history khác nhau. `prerequisite_dependencies_by_query` của lấy vé Ollie giữ hai reset thay thế theo query, không phải hai prerequisite đồng thời. Đây là chú thích phạm vi, không đổi schema/engine.

Xác suất đường dùng chain rule với mọi bước trước đã thành công, không giả định các bước độc lập. `fractions.Fraction` nhân cận chính xác và được đối chiếu canonical engine trên baseline `12a221fb401d9ce0a38e008168dc0b62f116792d`.

| Đường | Khoảng từ A | Khoảng từ B | C | Impact |
| --- | --- | --- | ---: | --- |
| Source A, qua Lidia | [42/125, 171/250] | [9/40, 8379/10000] | 2 | High |
| Source A, qua Josefa → Ollie | [588/3125, 29241/50000] | [81/800, 7800849/10000000] | 3 | High |
| Source B, qua Ollie | [42/125, 171/250] | [9/40, 8379/10000] | 2 | High |

Source B là foothold/query, không phải người chấm B. Hai query không xếp hạng chung. Trong Source A, hai đường vẫn ở frontier bảo thủ vì khoảng chồng lấn; đường Lidia ít công sức nhất trong tập ứng viên được đưa vào. Không suy tối ưu toàn đồ thị hoặc thực thi tấn công từ kết quả này.

## Bàn giao cho xuất bộ tham số

Phân loại nguồn hiện tại là `human_reviewed_ai_assisted_ratings`; công bố AI/exposure và `independent_inter_rater_agreement_eligible: false`. Đây là review chung có hai người được chuyển đạt, không phải hai lần chấm độc lập. Governance về chấm độc lập vẫn áp dụng cho các claim đo độ tin cậy độc lập; lượt này không đáp ứng claim đó và không dùng tên `declared_independent_ratings` để che giới hạn.

Exporter #172 ở head đã kiểm tra `b779916892e3741d36686439067c2596e20ea033` chỉ hỗ trợ `synthetic_test_only` / `declared_independent_ratings`. Việc tiếp theo cho coding agent: hỗ trợ nguồn human-reviewed có exposure được khai báo, giữ metadata/provenance/policy ở source và release boundary; có test từ chối AI chưa xác nhận hoặc đổi nhãn synthetic/AI thành independent. Đây là điều chỉnh hợp đồng công cụ theo evidence thật, không yêu cầu thêm chuyên gia ngoài hoặc xác nhận lại B.

Sau đó dùng hai source sheets hiện tại, chạy preflight và reconciliation, ghi 21 dispositions riêng với lý do, xuất bundle rồi chạy validator/độ nhạy/engine trước khi tổng hợp báo cáo Week 3. Các fixture trống, research bundle, oracle và synthetic demo giữ nguyên. PR #173 chưa được merge hoặc nghiệm thu tích hợp trong lượt cập nhật này.
