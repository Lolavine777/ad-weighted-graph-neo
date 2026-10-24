# Đánh giá công khai GoodHound / WINDOMAIN.LOCAL

Ngày 24/10/2026, đã chạy đánh giá ngoài các dataset cũ trên bản input dẫn xuất có audit, giữ nguyên core `2566a96`, bảng `neo-c-v1` và budget đã chốt.
Đây là external validation kèm input adaptation, không phải blind holdout.
[Kết quả máy đọc được, hashes và lệnh chạy](goodhound-evaluation-results.json) giữ đầy đủ các lượt lỗi và kết quả bất lợi.

## Dữ liệu và khả năng nhập

Nguồn là [sample GoodHound từ DetectionLab có BadBlood](https://github.com/idnahacks/GoodHound/tree/c2d8915619d54c752425e6e3fdee3ac8499b32f2/Sample%20SharpHound%20Output), được tác giả cung cấp để import thử; repo có [GPLv3](https://github.com/idnahacks/GoodHound/blob/c2d8915619d54c752425e6e3fdee3ac8499b32f2/LICENSE).
Raw chỉ dùng local, không phân phối lại.
ZIP đã pin Git blob và SHA256, chứa schema v3, 6 file, 1.386 record; phiên bản SharpHound, thời điểm thu thập và timezone chưa xác nhận.
Timestamp trong tên file chỉ làm reference time có nhãn assumed, không phải thời điểm quan sát được.

| Lượt | Kết quả nhập neo |
| --- | --- |
| Raw nguyên bản | Input error: membership tham chiếu NETWORK SERVICE theo miền nhưng thiếu host GUID |
| Adaptation v1 | Input error: một membership khác có kiểu Unknown và không có object tương ứng |
| Adaptation v2 | Nhập được 1.387 node, 24.781 cạnh; gồm một Group boundary do cơ chế hiện có tạo |

Bản v2 giữ đủ 1.386 record và mọi thuộc tính/ACE khác; chỉ giữ riêng ngoài projection hai membership chưa xác định được của Event Log Readers.
Audit có toàn bộ giá trị đã loại để phục hồi chính xác parsed JSON nguyên bản; raw được giữ bất biến.
Không thay parser, engine, search, preset hoặc bảng C.
CE 9.8.0 cũng từ chối cả 6 file v3 nguyên bản với lỗi upload `no data tag found`; không coi job báo Complete với 0 file là nhập thành công.
Lượt CE tiếp theo dùng cùng adaptation v2 qua converter v3 sang schema 6 hiện có; kiểm conservation giữ 1.386 record, 26.251 ACE và 3.044 explicit membership trước khi upload thành công 6/6 file.

## Cohort và kết quả

Chọn bằng seed `neo-decision-v1`, không lọc theo kết quả: 3 User có danh tính mạng dùng được và 2 Computer chỉ có local admin, mỗi nguồn độc lập tới DA/EA.
Primary `neo_guided` và secondary `neo_refine` đều giữ 10 programs, 12 semantic steps, 4.096 expansions và Top-3 C.
Snapshot không có session; stratum Computer có session rỗng.

| Nguồn | Cả hai đích DA/EA, cả guided/refine | Expansions mỗi cặp | CE structural/enabled |
| --- | --- | ---: | --- |
| REGINA_COMBS | Hết budget, chưa kết luận | 4.096 | Không có đường trong scope |
| BRENT_DAUGHERTY | No-path được engine chứng minh trong scope | 112 | Không có đường trong scope |
| FREDA_CAMPOS | Hết budget, chưa kết luận | 4.096 | Không có đường trong scope |
| FINWVIR1000001 | Blocked: chưa có danh tính máy được xác thực | 1 | Không có đường trong scope |
| AWSWWKS1000000 | Blocked: chưa có danh tính máy được xác thực | 1 | Không có đường trong scope |

Mỗi mode chạy đủ 10 cặp, không có query error hoặc cặp bị loại: 0 witness, 4 cap, 2 no-path và 4 blocked.
Engine cũng đặt proof no-path trong scope cho 4 cặp blocked; báo riêng vì nguyên nhân là giới hạn foothold/scenario.
Primary không có Unknown; sensitivity evidence-only cho 6 cặp User ra indeterminate do thiếu `security_group`/`membership_usable`, 4 cặp Computer vẫn blocked.
CE chạy đủ 20 request cho 10 cặp với hai variant, trả 404 và được kiểm lại bằng truy vấn database rỗng.
Giới hạn CE là 12 graph hops trên tập cạnh cố định, khác 12 semantic steps của neo; không suy các âm tính này thành an toàn toàn miền.

## Đối chiếu và giới hạn sử dụng

Hai bên khớp 1.387 ID core, type, enabled và cả 597 primary-group references; CE có thêm 4 node ADLocalGroup ngoài sáu loại core.
Trong HOST_EDGES có 24.762 triple chung; 19 triple chỉ có ở neo gồm 14 GenericAll self-loop, 3 WriteDacl self-loop và 2 AdminTo suy diễn từ membership.
Hai AdminTo có đường MemberOf rồi AdminTo tương đương trong CE, đã kiểm bằng query lưu trong evidence.
Giữ nguyên chênh lệch, không sửa graph để làm bằng nhau.
Scope không bao phủ mọi ACE/kỹ thuật có trong raw, như Owns, WriteOwner, GenericWrite hoặc DCSync; đây không phải đánh giá toàn bộ khả năng BloodHound.

Neo dùng được để chạy cohort, lưu provenance, phân biệt cap/Unknown/blocked/no-path và đối chiếu input sau adaptation được công bố.
Neo chưa nhập trực tiếp được export nguyên bản này; mẫu cố định cũng chưa cho witness để đánh giá lợi ích xếp hạng C.
Không có chương trình để replay hoặc kiểm ledger C trên dữ liệu này, không tính C thiếu thành 0; fixed-program C sensitivity không áp dụng.
Selector `membership_points` không có membership C>0 đủ điều kiện, nên không chạy remediation hoặc thay bằng can thiệp khác.
Không có kết luận ưu thế, speedup hay minimum-C từ lượt này.

## Kiểm chứng và evidence

145 tests pass, 9 skip, có JUnit XML; skips gồm kiểm tra filesystem khác nền tảng và raw SEAMLESS opt-in, không phải kết quả GoodHound bị bỏ.
Đã tái lập hai lỗi import, kiểm manifest nguyên bản/dẫn xuất/CE, dựng lại byte-identical ba manifest và xác minh core/config không đổi.
Database dùng project `neo-goodhound-20261024-adaptation-v2`, image digest đã pin và volume mới; 37 volume có sẵn được giữ, không gắn vào project mới.
Raw, requests/responses, audit, scripts tái lập và log/JUnit nằm local tại `reports/generated/goodhound-evaluation-20261024-v1/`; summary JSON pin evidence manifest SHA256.
