# Protocol đánh giá trên môi trường AD chưa dùng để chỉnh neo

Trạng thái: protocol, chưa chạy và chưa có kết quả holdout.
Chốt trước khi nhận hoặc mở một export AD mới; không chuyển một corpus đã xem thành test mù.

[Chuẩn bị local ngày 24/10/2026](holdout-local-preparation-20261024.json) đã đối chiếu bản freeze `a4a9c5b` với main `2566a96`, xác minh các pin code/config/bảng C và giữ nguyên quy tắc đánh giá bên dưới.
CI của `2566a96` đã hoàn tất thành công trên Ubuntu, Windows, quality và Compose; trạng thái đang chạy trong bản freeze là lịch sử.
Python 3.14.7 và dependencies theo lock đã sẵn sàng; CE dùng đúng ba image digest đã pin, project/volume mới và cổng loopback riêng.
Smoke check CE thành công, chưa nạp export AD; các volume có sẵn được giữ nguyên và không gắn vào project mới.
Chưa tìm thấy export mới đủ điều kiện trong các vị trí dữ liệu đã kiểm tra, chưa mở raw mới, số lượt đánh giá holdout/remediation vẫn bằng 0.
Cần nguồn/quyền dùng, collector/schema, thời điểm và xác nhận lịch sử sử dụng trước khi xét một export là holdout.
Chuẩn bị này không khép yêu cầu minimum-C của đề gốc hoặc chứng minh ưu thế so với BloodHound.

## Điều kiện đầu vào

Môi trường holdout phải do chủ sở hữu cho phép dùng trong nghiên cứu và chưa được dùng để chỉnh parser, search, scenario hoặc bảng C của neo.
Loại khỏi holdout: SEAMLESS, NORTH, NORTH_CE_PYTHON, GHOST, WRAITH, PHANTOM trong ad_sampledata và các fixture/telemetry đã dùng ở dự án gốc hoặc neo.
Giữ nguyên một forest/export có timestamp và manifest SHA256; không chia ngẫu nhiên node trong cùng graph để giả lập dataset độc lập.
Ghi nhận nguồn, điều kiện tái sử dụng, schema collector, miền và thời điểm thu thập trước phân tích.
Nếu export chứa danh tính thật, giữ raw và evidence chứa danh tính ở local/private; không đưa credentials vào Git hoặc báo cáo.

Freeze code commit, C profile digest, semantic catalog, scenario policy, query protocol và image digest BloodHound trước khi mở raw holdout.
Mọi sửa lỗi sau khi mở holdout phải có phiên bản và báo riêng trước/sau; dataset đó chuyển thành adaptation/regression, không tiếp tục gọi là blind test của bản sửa.
Không sửa dữ liệu malformed để làm tăng coverage mà thiếu audit bảo toàn record/relationship và lý do rõ ràng.

## Cohort và scope

Dùng quy tắc chọn nguồn có sẵn trong `scripts.neo_decision.select_sources` với seed `neo-decision-v1`: ba User và hai Computer đủ điều kiện, chọn bằng hash, không lọc theo reachability hoặc C.
Mỗi nguồn là một foothold độc lập; không cộng quyền giữa các nguồn.
Đích là các nhóm DA/EA thực sự quan sát được trong miền; báo thiếu đích hoặc thiếu loại nguồn, không tự sinh đối tượng để đủ mẫu.
Thêm stratum riêng cho mọi Computer đủ điều kiện có session đã quan sát; khử trùng nguồn–đích khi tổng hợp.
Đây là mẫu chẩn đoán nhỏ theo protocol, không ước lượng prevalence toàn forest.

User bắt đầu bằng danh tính mạng dùng được; Computer host-compromise chỉ có local admin.
Không tự cấp danh tính mạng tài khoản máy hoặc credential của người dùng có session.
Giữ `neo-standard-v1`/host-session policy đúng với phiên bản đóng băng; báo assumption riêng với dữ liệu quan sát.
Chạy thêm policy thận trọng/evidence-only như sensitivity đã ghi rõ, không thay primary endpoint sau khi thấy kết quả.

Primary search giữ `neo_guided`, 10 programs, 12 semantic steps, 4.096 expansions và Top-3 C.
`neo_refine` là secondary comparison, cùng scope và ngân sách; không thay kết quả primary bằng mode có lợi hơn.
Giới hạn 12 graph hops bên BloodHound là giới hạn khác 12 semantic steps, phải luôn ghi rõ.
Quan hệ so sánh giữ đúng DIRECTORY_EDGES hoặc HOST_EDGES hiện có; không gọi scoped custom queries là toàn bộ khả năng BloodHound.

## Kiểm chứng và số đo

Trước so đường, đối chiếu ID/type/enabled, primary groups, boundary, self-ACE và từng quan hệ trong scope.
Báo đủ chênh lệch nhập liệu, không loại cặp khỏi mẫu vì công cụ nào không đọc được dữ liệu.
Chạy BloodHound CE thật trên database mới cô lập; giữ request/response, query và image/input digest.
Chỉ ánh xạ C cho đường CE khi có hành động tương ứng trong catalog, nêu cả đường không ánh xạ được.
Kiểm allShortestPaths có giới hạn ở mọi ca cần dùng khác biệt C để kết luận, để tránh ưu thế giả do shortestPath chọn một tie tùy ý.

Báo riêng: witness/replay thành công, C và ledger, Unknown/False, input error, no-path có bằng chứng trong scope, query bị cap và chương trình chưa chấm C.
Mọi witness được native replay; C từ 0 do entitlement có sẵn khác C thiếu.
Không gộp query chưa chạy, error hoặc hết budget vào no-path.
Tách C best-found với minimum được chứng minh; chỉ cho minimum khi toàn bộ điều kiện proof của native engine đạt.
Sensitivity C dùng đúng protocol fixed-program đã chốt, báo ties và alternative chưa tìm được.

Timing/RAM phải đo process riêng, gồm phân rã import/preparation/search/scoring/replay và định nghĩa workload tương đương.
Không so một shortest path CE với mười chương trình semantic rồi tự gọi là speedup.
Nếu nguồn lực không đủ để đo công bằng, chỉ ghi thời gian mô tả và không kết luận công cụ nhanh hơn.

## Remediation

Can thiệp primary dùng đúng selector `scripts.neo_decision.membership_points` đã đóng băng: chỉ tính program C>0 và membership vào DA/EA quan sát được hoặc Builtin Administrators đã scope, xếp theo số cặp được hỗ trợ, rồi số witness, rồi canonical edge ID.
Ghi lại điều kiện eligibility và mọi điểm số của selector; không đổi tiêu chí sau khi thấy holdout.
Đây là lựa chọn can thiệp phụ thuộc kết quả đã khai báo trước, không phải một hiệu ứng độc lập với cohort discovery.
Nếu không có membership đủ điều kiện, báo không chạy primary intervention; không âm thầm thay bằng loại edge khác.
Giữ các intervention khác, gồm session, thành exploratory với lý do và thời điểm chọn rõ ràng.

Từ graph nguyên vẹn và foothold ban đầu, bỏ cạnh, dựng lại facts và quan hệ suy diễn phụ thuộc cạnh đã bỏ, rồi tìm mới tới cả hai đích ở cả native và CE.
Không chỉ kiểm witness cũ bị cắt; giữ cả bypass và giá C tăng/giảm.
Journal trước mọi DELETE, bảo toàn properties, restore toàn bộ cạnh và kiểm digest; chỉ dùng database thí nghiệm.
Mỗi can thiệp fresh-foothold không mô phỏng credential đã bị lấy trước đó hoặc hiệu quả thu hồi credential ngoài AD graph.
Không suy source disconnection hoặc giảm rủi ro toàn miền từ việc cắt vài witness.

## Tiêu chí kết luận và bàn giao

Thành công kỹ thuật là tái lập được cohort đã khai báo, không mất dữ liệu/volume, replay đúng và công bố đủ trường hợp bất lợi/lỗi/giới hạn.
Một lợi ích về C chỉ được nêu trên cặp cụ thể với mapping hợp lệ và đối chiếu đầy đủ ties; không ép phải có kết quả thuận lợi cho neo.
Không tìm thấy lợi ích vẫn là kết quả nghiên cứu, không phải lý do đổi cohort, rubric hoặc primary endpoint.
Kết quả của một export chưa đủ chứng minh ưu thế tổng quát; giới hạn về kỹ thuật và scenario phải đi cùng kết luận.

Bàn giao manifest, phiên bản code/config, query pack, output/checkpoint hashes, replay audit, bảng CE/native, remediation trước/sau và lệnh tái lập.
Raw/evidence lớn giữ private/local; chỉ commit summary cần thiết và tài liệu đã kiểm tra.
Holdout chỉ có thể được đánh dấu hoàn tất sau khi có export đủ điều kiện và toàn bộ các bước trên đã chạy; protocol này không thay thế bằng chứng thực nghiệm.
