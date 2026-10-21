# Bàn giao tuần 5 - Ca nghiên cứu và can thiệp điểm nghẽn dự kiến

## Current-state amendment - 11/10/2026

Scoped Week 4 technical acceptance now passes under A maintainer weekend disposition / self-verification.
See the [final closure report](week4-maintainer-closure-2026-10-11.md) for exact revisions, commands, C/P/I coverage, generated C=2/C=3 comparison and Pareto evidence.
Frozen SEAMLESS has C=4/4, P=0/4 and I=1/1; C=3 and High impact are adopted only for exact identities and the typed same-asset terminal goal.
Source A retains its two fully rated historical-prefix chains and 22 P-unrated paths; broad pending proposals remain unchanged.
The full raw-present suite passes 2,603 tests with nine skips and 48 subtests; no independent B review or remote CI PASS is claimed.
#237 and #259 remain Week 5 work; the dated pending statements below are historical snapshots.

## Current-state amendment - 09/10/2026

AS-REP và RBCD đã có accepted implementations/gates/bindings; các câu chờ triển khai trong snapshot 08/10 phía dưới là lịch sử.
Reuse [RBCD handoff](../research/rbcd-229.md) và [scenario SEAMLESS đã chạy](../research/week4-seamless-scenario.md): X request capability -> AS-REP material -> recovered secret -> usable V_A -> admin_control(C0).
Đây là generated prediction trên verified raw dưới tám assumptions, chưa observed exploit; missing/false/cap controls đã đối chiếu oracle, C/P/I giữ unrated.
Can thiệp Week 5 có thể xét runtime `admin_channel` hoặc provenance-backed AdminTo trong view riêng, không sửa snapshot gốc và không coi remediation optimum đã implement.
B clean-checkout reproduction, full manual docs/API audit và Week 4 final acceptance còn pending; CE/metrics/choke-point scope vẫn giữ roadmap riêng.

Cập nhật ngày 08/10/2026, thay các chuỗi và điểm số chưa có căn cứ trong bản ngày 07/10/2026.
Tuần 4 chỉ bàn giao ca và định nghĩa can thiệp, chưa triển khai độ đo hoặc thuật toán phòng thủ.

## Ca đã có bằng chứng tổng hợp

Cặp nguồn/tài sản là OtherHost/Host; Alice được khai báo usable tại Host trong context Host.
Đây là mô hình tổng hợp, không chứng minh vượt phân vùng mạng thực tế.
Baseline sinh ba chương trình D, M/D và M/I, tương ứng thực thi quản trị trực tiếp, membership rồi trực tiếp, và membership rồi quản trị kế thừa.
Membership là bao đóng quyền sẵn có, không phải thêm thành viên nhóm hoặc RBCD.

| Chương trình | C theo Ledger E | P theo Ledger E | I |
| --- | --- | --- | --- |
| D | 5 | [2/5, 27/40] | High |
| M/D | 5 | [2/5, 27/40] | High |
| M/I | 2 | [12/25, 18/25] | High |

Nguồn định mức là `docs/research/ratings/week4/synthetic-a2-e.json`, chỉ có giá trị kiểm thử tổng hợp.
Query minimum-effort dùng Alice là actor/foothold theo binding của ledger; ca OtherHost/Alice kiểm source và identity riêng, không suy equivalence scoring giữa hai query.
Chuỗi Kerberoasting đã sinh thành công trong fixture tổng hợp: request -> `recover_ticket_secret` -> scoped usable identity -> entitlement/resource action.
C/P/I riêng còn unrated; ticket material không đủ cho activation. Đối chứng reset cùng đầu vào chưa chứng minh thêm tài sản, và extension bị giới hạn số bước.
AS-REP và RBCD cũng chờ chương trình/gates/bindings cụ thể.

## Nghĩa can thiệp dự kiến

Can thiệp thay đổi một quan hệ, quyền hoặc runtime predicate được xác định rõ trong cùng snapshot/query/state để đánh giá biến động tập đường tới cùng goal.
Ví dụ nghiên cứu là loại quyền AdminTo hoặc thay gate `admin_channel` trong view giả định, giữ đồ thị gốc và provenance bất biến.
Không đồng nhất gate trừu tượng với một giao thức cụ thể chưa được model xác nhận.
So sánh phải giữ cùng caps và định mức, ghi các đường còn đủ điều kiện, blocked, indeterminate và unrated.
Giảm số đường hoặc tăng effort trong một tập con không tự chứng minh choke-point tối ưu.
Chi phí can thiệp, tác động nghiệp vụ và tiêu chí tối ưu chưa có định mức được chấp thuận.

## Điều kiện trước khi đánh giá

Hai hồi quy proof/zero-action đã đạt oracle trên nền tích hợp; giữ các ca này khi đổi search hoặc ranking.
CLI tổng hợp đã chạy hai process, khớp oracle và Ledger E; giữ ca từ chối input sai. Bàn giao AS-REP và RBCD; thu bằng chứng dữ liệu riêng tư được phép và phản biện chéo độc lập.
Không lấy kết quả tổng hợp thay nghiệm thu môi trường thật hoặc tuyên bố hoàn tất tuần 4.
