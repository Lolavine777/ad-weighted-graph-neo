# Bản nháp nỗ lực SEAMLESS có hỗ trợ AI và đối chiếu PR #173

- Ngày lập tài liệu: 2026-10-02; đây không phải thời điểm chấm của một người thật.
- Loại đánh giá tại lúc lập: AI-assisted assessment; trạng thái lịch sử: draft_pending_human_review. Trạng thái hiện tại theo [bộ phiếu A/B](ratings/week3-2026-10-02/README.md).
- Phạm vi: 9 đơn vị công việc trong scenario SEAMLESS 1.1.0, Source A và Source B, horizon 24h, boundary intra_forest.
- Head phiếu A đã đối chiếu: `773f529cbacba0184a29d43db48a6f4576c3111b`; source review tooling #172 ở `2c477912996b13470540a57a02c6171ba6424b11`.
- Refs [PR #173](https://github.com/nairyuuu/ad-weighted-graph/pull/173), tooling #172/#171, #143, #158, #48.
- [Packet](seamless-scenario-rating-packet.md), [rubric/governance](evidence-rating-governance.md), [hướng dẫn xuất tham số tại revision #172 đã tham chiếu](https://github.com/nairyuuu/ad-weighted-graph/blob/2c477912996b13470540a57a02c6171ba6424b11/docs/research/reviewed-parameter-release-guide.md).

## Điểm đề xuất

Đây là đề xuất từ trợ lý AI theo yêu cầu của người dùng, chưa phải phiếu người thật B, quyết định đồng thuận hay tham số được nghiệm thu. Không khai báo danh tính, năng lực, tính độc lập hoặc timestamp thay người thật. Hai mẫu fixture vẫn là mẫu trống; phiếu A thật đã nộp đủ 21 mục trong #173. B chưa nộp phiếu thật; 11 likelihood và 1 impact chưa được chấm trong bản nháp này.

T1/T2 là điểm nguyên 1..3; C = T1 + T2 - 2. C=0 biểu thị mức thấp nhất của rubric, không có nghĩa không cần thao tác. Nỗ lực chỉ đo phần công việc sau foothold, không là thời gian lao động, xác suất hoặc mức thiệt hại.

| Work alias | T1 | T2 | C | Lý do đề xuất |
| --- | --- | --- | --- | --- |
| WU_RESET_LIDIA | 1 | 2 | 1 | Reset qua cơ chế tiêu chuẩn; cần chọn đúng actor, target, kênh ghi và tham số mật khẩu. |
| WU_ACTIVATE_LIDIA | 1 | 1 | 0 | Xác thực tiêu chuẩn bằng credentials mới dưới assumptions KDC/authentication đã khai báo. |
| WU_WINRM_DC_LIDIA | 1 | 2 | 1 | Remoting tiêu chuẩn; chọn endpoint/context và xác nhận outcome quản trị. |
| WU_RESET_JOSEFA | 1 | 2 | 1 | Cùng cơ chế reset; chưa có căn cứ cho độ khó khác Lidia. |
| WU_ACTIVATE_JOSEFA | 1 | 1 | 0 | Xác thực tiêu chuẩn sau reset; không có tùy biến giao thức trong packet. |
| WU_RESET_OLLIE | 1 | 2 | 1 | Reset dưới Josefa/entitlement VA-JER; không cộng lại công sức kiểm soát Josefa. |
| WU_ACTIVATE_OLLIE | 1 | 1 | 0 | Xác thực tiêu chuẩn; không tính lại công sức reset/lấy credentials. |
| WU_WINRM_DC_OLLIE | 1 | 2 | 1 | Cùng cơ chế và mục tiêu endpoint quản trị như Lidia. |
| WU_RESET_OLLIE_FROM_B | 1 | 2 | 1 | Actor khác nhưng chưa có căn cứ tăng độ khó cơ chế reset. |

Nguồn kỹ thuật đã mở để đối chiếu:
- [Microsoft SetPassword](https://learn.microsoft.com/en-us/windows/win32/api/iads/nf-iads-iadsuser-setpassword): API tiêu chuẩn, quyền reset và kênh thực hiện.
- [Microsoft Kerberos overview](https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-authentication-overview): quy trình xác thực/cấp ticket tiêu chuẩn.
- [Microsoft remote requirements](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_remote_requirements): nguồn packet cho prerequisites remoting; không cung cấp điểm nỗ lực.

Nguồn xác lập cơ chế, không xác lập con số 1/2/0. T1/T2 là phán đoán ordinal của AI theo rubric và scope đã khai báo. T2=2 của reset/WinRM là quy ước đề xuất về phối hợp tham số/context và kiểm tra outcome; cần người chấm review. Không tăng điểm theo số prerequisite, thiếu evidence, nguy cơ bị phát hiện hoặc hypothetical bypass. Nếu người chấm coi thao tác đó có ma sát thấp trong cùng scope, T2=1 cũng là khả năng cần đối soát.

## Phân bổ chuẩn bị và dependencies

Đề xuất loại phần chiếm foothold và setup công cụ chung khỏi biên tính của cả 9 mục. Mỗi mục chỉ tính tương tác riêng; việc chọn actor/context và kiểm tra outcome cục bộ thuộc mục đó. Đây là đề xuất phân bổ, chưa tự ghi `is_independent: true` vào phiếu người thật.

- ACTIVATE_LIDIA phụ thuộc RESET_LIDIA; WINRM_DC_LIDIA phụ thuộc ACTIVATE_LIDIA và closure DA.
- ACTIVATE_JOSEFA phụ thuộc RESET_JOSEFA.
- RESET_OLLIE phụ thuộc ACTIVATE_JOSEFA và closure VA-JER.
- ACTIVATE_OLLIE phụ thuộc RESET_OLLIE trong Source A hoặc RESET_OLLIE_FROM_B trong Source B.
- WINRM_DC_OLLIE phụ thuộc ACTIVATE_OLLIE và closure DA.
- RESET_LIDIA, RESET_JOSEFA và RESET_OLLIE_FROM_B xuất phát sau foothold tương ứng, không có active work unit trước đó trong route.

Prerequisite không đồng nghĩa trùng chi phí. Passive membership closures không tạo active effort. Ticket acquisition thuộc activation; WinRM chỉ tính phần mở phiên/thực thi và service authentication chưa được phân bổ ở activation. Nếu implementation gộp lại ticket/session preparation, phải review và phân bổ lại trước khi chốt overlap.

ACTIVATE_OLLIE và WINRM_DC_OLLIE dùng chung canonical work IDs giữa A/B; tái dùng định mức chỉ khi actor/target/context/boundary và cách phân bổ tương thích. Không tái dùng likelihood giữa hai footholds/history.

## Đối chiếu với phiếu A trong PR #173

Phiếu A tại [rater-A.json](ratings/week3-2026-10-02/rater-A.json), head `773f529cbacba0184a29d43db48a6f4576c3111b`, có đủ 21 mục. Điểm đề xuất trong bản nháp này được đưa ra trong hội thoại trước khi mở #173; sau khi người dùng sửa số PR, trợ lý đã xem phiếu A để đối chiếu. Phần đối chiếu hiện tại không là chấm mù và không thay khai báo của người thật B.

| Nhóm | Đề xuất AI T1/T2/C | Phiếu A T1/T2/C | Số mục khớp |
| --- | --- | --- | --- |
| Reset | 1/2/1 | 1/2/1 | 4/4 |
| Activation | 1/1/0 | 1/1/0 | 3/3 |
| WinRM | 1/2/1 | 1/2/1 | 2/2 |

9/9 alias có cùng T1/T2/C; delta cost bằng 0 cho cả 9 mục. Tổng mỗi route đều 2/3/2. Đây là đối chiếu giữa phiếu A và đề xuất AI, không phải đo human inter-rater agreement hoặc final consensus.

Phiếu A chọn High và có 11 khoảng likelihood; bản nháp B chưa chấm các mục đó. Không sao chép điểm A để điền phần thiếu, không tính IoU/Kappa khi chưa có điểm B. Cách khai báo dependency của ACTIVATE_OLLIE theo query trong A phù hợp với hai reset thay thế; không yêu cầu thực hiện cả hai. Các đề xuất overlap trong bản nháp vẫn cần con người quyết định.

## Liên hệ với tooling #172

#172 là PR exporter/validator riêng, không phải nơi nộp phiếu. Source review ở `2c477912996b13470540a57a02c6171ba6424b11` cho thấy exporter yêu cầu hai source sheets rated, đủ 21 matched rated pairs và explicit dispositions. Bản nháp AI 9 mục chưa đủ điều kiện đó.

Synthetic demo #172 dùng C=2 ở mọi unit, cho tổng 6/10/6; đây là test-only values, không là phiếu A. Không thay demo hoặc research bundle để làm khớp bản nháp.

Sau khi người thật review/điều chỉnh nỗ lực và overlap, cần chấm riêng likelihood/impact, hoàn thành hai phiếu với khai báo AI assistance/exposure trung thực, chạy reconciliation và ghi final decisions riêng trước khi export. Không dùng null/default hoặc giả identity để đi qua release boundary.

## Kiểm chứng và giới hạn

Đã đối chiếu đủ 9 alias với mẫu B và phiếu A trong #173, kiểm công thức/miền điểm và các tổng 2/3/2. Static check tooling #172 tập trung vào release eligibility, mapping effort, evidence classes và nguồn synthetic demo; đây không phải full independent code review hoặc approval toàn PR.

GitHub CI của head `2c47791`: run [36973578988](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/36973578988) completed/success; branch policy completed/success. Đây là evidence từ CI đã đọc, không phải pytest chạy lại local hoặc checks của commit tài liệu mới.

Cập nhật được chuyển từ nhánh #172 sang #173 sau khi người dùng sửa số PR. Không thay phiếu A, engine/parser, mẫu source sheets, research bundle, synthetic scores hoặc acceptance status. Không phát hành bộ tham số, merge PR hoặc đóng issue trong cập nhật này.

## Cập nhật trạng thái hiện tại

A chuyển đạt B đang có mặt xác nhận và ủy quyền thống nhất lúc 14:05:23 UTC+07 ngày 2026-10-02. B đã tiếp nhận đủ 21 điểm từ assessment AI và chính sách retry/deadline chung, giữ khai báo tiếp xúc A. Các đoạn “chưa nộp/chờ review” ở trên là lịch sử bản nháp 9 công sức; không còn là trạng thái của phiếu B hiện tại. Xem [hướng dẫn nguồn hiện tại](ratings/week3-2026-10-02/README.md) và [confirmation record](ratings/week3-2026-10-02/shared-review-confirmation.json). Không suy chấm mù độc lập hoặc final acceptance từ xác nhận này.
