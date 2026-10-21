# Báo cáo tuần 4 - Nghiệm thu trong phạm vi đã kiểm chứng

## Current-state amendment - 11/10/2026

Scoped Week 4 technical acceptance now passes under A maintainer weekend disposition / self-verification.
See the [final closure report](week4-maintainer-closure-2026-10-11.md) for exact revisions, commands, C/P/I coverage, generated C=2/C=3 comparison and Pareto evidence.
Frozen SEAMLESS has C=4/4, P=0/4 and I=1/1; C=3 and High impact are adopted only for exact identities and the typed same-asset terminal goal.
Source A retains its two fully rated historical-prefix chains and 22 P-unrated paths; broad pending proposals remain unchanged.
The full raw-present suite passes 2,603 tests with nine skips and 48 subtests; no independent B review or remote CI PASS is claimed.
#237 and #259 remain Week 5 work; the dated pending statements below are historical snapshots.

## Kết quả mới - 09/10/2026

Core và ba kỹ thuật Kerberoasting/AS-REP/RBCD đã có implementations được nhận.
[Scenario SEAMLESS](../research/week4-seamless-scenario.md) mới dùng verified snapshot 3.370 nodes/56.367 edges, source X khác tài sản C0 và known V_A và chỉ có initial request capability, không host control/usable AD identity.
Engine tự sinh một program request -> recovery -> activation -> direct AdminTo, đạt `admin_control(C0)` dưới tám assumptions đã khai báo; DA checkpoint false, C/P/I unrated.
Independent expectations được freeze trước execution `983ce542edad80d5b38d1cce97c7ca5db3b77cb5`; source/config bytes bằng baseline `be64798c89235f53c5c205894a7bac0f96437ce4`.
RAW và missing recovery giữ indeterminate; false admin_channel phủ quyết assumption true; OFF/capability/cap controls khớp oracle, không thêm cạnh vào canonical graph.
Hai process semantic-equal và public evaluator replay khớp mỗi state; [public evidence](../research/scenarios/week4-seamless-v1-actual.json) pin input/config/source/runtime và assumptions actually-used.
B clean-checkout cross-reproduction và audit đầy đủ docs/API vẫn pending; local validation không là human acceptance hoặc CI PASS, Actions billing chặn trước runner.
Các số 35/38, kỹ thuật pending và raw unavailable ở phần ngày 08/10 dưới đây là lịch sử; accepted synthetic package hiện 36/38 PASS, còn một manual audit và một prerequisite observation của checkout baseline không raw.
Không gọi prediction dưới assumptions là observed exploit, calibrated probability hoặc global optimum.

Cập nhật ngày 08/10/2026, thay các nhận định nghiệm thu và ví dụ điểm số ngày 07/10/2026.
Kết quả dưới đây là mô phỏng trên fixture tổng hợp, không phải bằng chứng tấn công thực tế hoặc xác suất đã hiệu chỉnh.

## Kết quả và đóng góp

A xây dựng oracle độc lập, đối chiếu từng trường kỳ vọng với engine, kiểm tra provenance, phân tích C/P/I và đóng gói báo cáo/demo.
B triển khai engine trạng thái, tìm kiếm, adapter, xếp hạng, CLI xuất kết quả tái lập và Kerberoasting. Hai lỗi về proof và zero-action đã được sửa trên nền tích hợp.
Trong 38 hàng của ma trận, 35 hàng đạt đối chiếu tổng hợp, 1 hàng kỹ thuật chưa được hỗ trợ, 1 hàng chưa thực hiện kiểm tra đầy đủ và 1 hàng thiếu đầu vào riêng tư.
Không còn lỗi đã biết trong các ca đã chạy; tuần 4 vẫn chưa nghiệm thu đầy đủ.

Engine sinh ba chương trình trên fixture nhỏ khi quyền và runtime gates thỏa mãn.
Quyền kiểm soát máy bàn đạp khác usable identity; context không phù hợp bị chặn.
Dữ kiện false phủ quyết giả định true; dữ kiện thiếu giữ indeterminate; giả định khai báo được ghi riêng trong trace.
Checkpoint nhóm đặc quyền và mục tiêu tài sản được kiểm riêng, không bắt mọi đường tới tài sản đi qua checkpoint.
Nhóm `Admins` trong fixture chỉ là đại diện tổng hợp cho checkpoint, không chứng minh danh tính Domain Admins thực tế.

## Ví dụ C/P/I tái lập được

Nguồn đầu vào là `tests/fixtures/attack_scenarios/graphs/two-routes.json` và `docs/research/ratings/week4/synthetic-a2-e.json`.
Oracle định nghĩa độc lập ba chương trình first-success: D, M/D và M/I.
D là `obtain_admin_execution_on_host` trực tiếp; M là `propagate_group_entitlement`; I là thực thi quản trị qua quyền kế thừa từ nhóm.
M biểu diễn bao đóng quyền nhóm sẵn có, không phải thao tác gia nhập nhóm hoặc ủy quyền tài nguyên.
Các kỹ thuật được phép trong ca này không gồm đổi mật khẩu, lấy vé hoặc WinRM cụ thể.

| Chương trình | Work units duy nhất | C | P toàn chương trình | I |
| --- | --- | --- | --- | --- |
| D | `w-auth-context`, `w-direct-admin` | 1 + 4 = 5 | [2/5, 27/40] | High |
| M/D | Cùng tập work units như D | 5 | [2/5, 27/40] | High |
| M/I | `w-auth-context`, `w-inherited-admin` | 1 + 1 = 2 | [12/25, 18/25] | High |

P của D là [4/5 × 1/2, 9/10 × 3/4]; P của M/I là [4/5 × 3/5, 9/10 × 4/5].
Đây là tích các khoảng điều kiện theo lịch sử công việc, không giả định các bước độc lập thống kê.
I được gắn với sự kiện quản trị Host C0 và lý giải nghiệp vụ giả lập trong ledger.
M không thêm work unit; công việc dùng chung chỉ được tính một lần.
Toàn bộ định mức là `synthetic_test_only`, không chuyển sang dữ liệu thật hoặc kỹ thuật khác.

Trong fixture hữu hạn này, cả ba đường qua adapter và có định mức công sức, M/I có C nhỏ nhất là 2.
Ledger T giữ ba ứng viên hòa C = 2.
Điều này không chứng minh minimum cho môi trường thực hoặc tập đường chưa được đánh giá.
Các khoảng P của Ledger E giao nhau; minimum effort không đồng nghĩa ưu thế Pareto rủi ro.

Chuỗi Kerberoasting cần `kerberoast_request` -> `recover_ticket_secret` -> activation đúng context -> entitlement/resource action.
Ticket material không tự tạo secret hoặc usable identity.
Chuỗi này đã được sinh và đối chiếu đủ 5 chuyển tiếp, 6 trạng thái trên fixture tổng hợp, gồm checkpoint nhóm và mục tiêu tài sản.
Tắt phần mở rộng trên cùng đầu vào thì không có đường; thiếu recovery chỉ đạt ticket material; SPN/KDC false chặn và thiếu dữ kiện giữ indeterminate; auth deny giữ secret nhưng chưa usable identity.
Adapter nhận chương trình, nhưng thiếu định mức riêng nên C/P/I giữ unrated/null, không tuyên bố minimum.
Ở ca có sẵn đường reset, bật Kerberoasting vẫn tới cùng tài sản; không tăng asset coverage đã chứng kiến. Ca này chạm cap số bước, nên chỉ kết luận trong phạm vi đường đã sinh.

## Giới hạn còn mở và khả năng tái lập

Ca binding sai vẫn sinh ba đường và loại một đường ở adapter, nhưng engine đã hạ scope xuống `best_in_bound_subset`, proof false; C = 5 chỉ là incumbent của tập đã đánh giá.
Ca mục tiêu đã đạt ban đầu giữ đường 0 bước và công khai zero new work = 0. Canonical ranking không áp dụng, P/I null, không có ứng viên xếp hạng hoặc Pareto.

AS-REP đã có chương trình thực thi tổng hợp qua exact owners `asrep_request` và
`recover_asrep_secret`; kiểm tra scoped PASS, domain mapping và private replay
vẫn pending. RBCD còn chờ chương trình thực thi; validator từ chối kỹ thuật này.
CLI đã chạy từ query khai báo, sinh đúng ba chương trình và reachable states theo oracle; C/P/I khớp Ledger E. Hai process và hai cách xuất stdout/file khớp; input state rỗng hoặc ranking null bị từ chối. Đối soát đầy đủ tài liệu/API chưa thực hiện.
Dữ liệu SEAMLESS riêng tư vắng mặt trong checkout nghiệm thu; chỉ kiểm tra prerequisite, chưa chạy probe hoặc nghiệm thu dữ liệu thật.
Thiếu rating giữ unrated; chạm cap giữ truncated và không được suy thành no-path hoặc minimum toàn phạm vi.

Bản kê bằng chứng lưu runtime, thời điểm, commit, hash byte của nguồn/input/catalog/contracts, các gates, trạng thái nhánh và diagnostics thực tế.
Hai lượt chạy so sánh payload semantic riêng; metadata thực thi được quan sát từng lượt và không phải dữ liệu cần giống từng byte.
Lệnh và checksums nằm trong [kịch bản trình diễn](week4-demo.md); assertions và phạm vi từng hàng nằm trong [ma trận nghiệm thu](week4-acceptance-matrix.md).
Phản biện chéo bản cập nhật, bàn giao AS-REP/RBCD và chạy lại với đầu vào riêng tư được phép vẫn là điều kiện để nghiệm thu đầy đủ.

Bằng chứng CI nguồn trước đã đạt trên Linux/Windows. Bản ghép CLI được chạy lại theo các lệnh và bộ kiểm thử ghi trong bản kê; hai lượt từ cùng nguồn sạch cho cùng payload semantic, nhưng chưa thay tái lập độc lập của B.
