# Độ nhạy C trong tập chương trình đã tìm được

Ngày 23/10/2026, từ main `6645cda`, theo [protocol chốt trước khi chạy](cost-sensitivity-protocol.md) tại commit `0e1d8c3`.
Không sửa engine, parser, scenario, search mặc định hoặc bảng C production.
[Summary có hash evidence](cost-sensitivity-results.json) giữ các biến thể và số đo.

**Trong 220 pair-program observations, mọi chương trình rẻ nhất ở baseline vẫn thuộc tập rẻ nhất dưới cả 17 biến thể; điều này chưa chứng minh độ bền với alternative chưa tìm được.**
C tuyệt đối thay đổi đáng kể, Top-3 nhạy với ties, và hai joint stress đảo thứ tự một số alternative đắt hơn trên EXTDC01.

## Scope đã chạy

Dùng cùng raw/snapshot và 26 lượt của cohort BloodHound cố định: SEAMLESS 10, WRAITH chính 10, session 6.
37 file raw đã kiểm manifest; WRAITH giữ đúng export `20240305111414` và 22 AdminTo sau sửa LocalGroup.
Discovery giữ neo_guided, 10 programs, 12 semantic steps và 4.096 expansions/query.
Tất cả 26 query hoàn tất không lỗi hoặc Unknown attempt; SEAMLESS 10/10, WRAITH 8/10 và session 6/6 có witness.
Sau khử trùng hai cặp EXTDC01, còn 24 cặp, gồm 22 cặp có witness và hai cặp TARGETCOMPUTERC chưa có witness trong preset local-admin-only.
Hai cặp này không được chấm C=0 hoặc tính vào mẫu stability.

Có 240 chương trình theo 26 lượt query, tương ứng 220 quan sát chương trình theo cặp sau khử trùng strata.
Đây không phải 220 tuyến AD độc lập: program identity giữ thứ tự semantic, actor, state và context; nhiều chương trình dùng cùng cấu trúc quyền hoặc họ công việc.
Mọi path đã native replay; tổng theo work-unit IDs duy nhất khớp C của public scorer trước khi reprice.
Tập candidate và feasibility giữ nguyên trong sensitivity; không chạy search dưới bảng giá mới.

18 bảng giá gồm baseline, 15 phép đổi T2 một mức trong một họ action và hai joint stress đã khai báo.
T1/T2 luôn trong {1,2,3}; activation T2=1 không có probe giảm.
Đây là giả thuyết trên rubric ordinal, không phải khoảng sai số thực nghiệm hoặc rating được expert phê duyệt.
P/I không được bổ sung hoặc suy thành xác suất.

## Kết quả theo cặp có witness

Các số đếm dưới đây dùng mẫu 22 cặp, không cộng hai lần session stratum.
“Đổi tập tốt nhất” gồm mở rộng hoặc thu hẹp tie; không đồng nghĩa đường tốt nhất cũ bị thay thế.
Top-3 dùng cùng tie policy theo canonical program key của sản phẩm.

| Probe T2 | C tốt nhất đổi | Tập tốt nhất đổi | Top-3 set đổi | Cặp có strict reversal |
| --- | ---: | ---: | ---: | ---: |
| Reset −1 / +1 | 10 / 10 | 0 / 0 | 0 / 0 | 0 / 0 |
| Activation +1 | 10 | 0 | 0 | 0 |
| Membership −1 / +1 | 7 / 7 | 0 / 0 | 0 / 0 | 0 / 0 |
| DACL control −1 / +1 | 0 / 0 | 12 / 0 | 4 / 7 | 0 / 0 |
| ACL grant −1 / +1 | 7 / 7 | 0 / 0 | 7 / 2 | 0 / 0 |
| Host execution −1 / +1 | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| WinRM command −1 / +1 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Session credential −1 / +1 | 8 / 8 | 0 / 0 | 2 / 0 | 0 / 0 |
| Reset/activation đắt hơn, ACL/membership rẻ hơn | 9 | 0 | 7 | 2 |
| Host/session đắt hơn, directory rẻ hơn | 20 | 12 | 4 | 2 |

Không probe nào làm mất một chương trình thuộc tập minimum baseline của cặp đó; hai joint stress vẫn giữ điểm này.
Ở 12 cặp, giảm DACL control từ C=1 xuống 0 khiến một số thao tác bổ sung trở thành tie rẻ nhất, trong khi minimum C không đổi.
Những thay đổi Top-3 của single-family probes đều không có đảo thứ tự nghiêm ngặt: chúng liên quan việc tạo tie hoặc phá tie cũ.
Không dùng sự ổn định của minimum để tự nhận Top-3 duy nhất hoặc toàn bộ thứ hạng ổn định.

### Ví dụ đảo thứ hạng nhưng không thay minimum

EXTDC01→DA có hai alternative đã tìm được:

| Công việc duy nhất | Baseline | Joint reset/ACL | Joint session/directory |
| --- | ---: | ---: | ---: |
| Hai work units dùng session credential | 4 | 4 | 6 |
| Một session credential + ACL grant + membership mutation | 5 | 3 | 4 |
| Minimum trong candidate set | 2 | 2 | 3 |

Alternative 5 trở nên rẻ hơn alternative 4 ở cả hai stress, nhưng một chương trình rẻ hơn vẫn giữ minimum của cặp.
EA có cùng hiện tượng; tổng có hai strict inversions ở stress thứ nhất và 12 ở stress thứ hai, đều trên hai cặp EXTDC01.
Không nhầm số cặp AD có thay đổi với số cặp chương trình bị đảo thứ tự.
Các lần lấy credential khác host/context là work units khác nhau; không gộp chỉ vì cùng technique.

Control synthetic two_routes cho ACL C=3 và reset C=1 ở baseline; joint reset/ACL đổi thành ACL C=1 và reset C=3, đúng oracle tính tay.
Control xác nhận phép đo phát hiện được đảo minimum khi candidate set thực sự có tradeoff đó; không cộng vào bảng AD.

## Giới hạn quan trọng

Cả 22 query có witness vẫn bị cap 10 chương trình, nên mọi minimum được báo ở đây là minimum trong tập đã tìm được, chưa phải minimum toàn scope.
RODCMANAGER có nhiều program ID nhưng mười candidate baseline đều dùng họ ACL; chúng chưa bao gồm bypass host/session đã tìm được sau can thiệp ở [lượt remediation](remediation-post-localgroup.md).
Vì vậy kết quả này không kiểm tra được việc reprice làm đường host/session thắng ACL trong graph nguyên vẹn.
Không gọi các candidate này là tất cả alternative hoặc dùng stability để chứng minh bảng C đúng.

WinRM command không xuất hiện trong các chương trình đã tìm được.
Hai probe của họ này thay bảng giá thật nhưng không tác động candidate nào, nên không tạo bằng chứng thực nghiệm về độ bền WinRM.
Giá 0 trong một giả thuyết ordinal cũng không xóa hành động active, không biến công việc đó thành entitlement đã có hoặc chứng minh nó không tốn thời gian.
Không tự áp dụng các giá giả thuyết vào production.

SEAMLESS và WRAITH từng được dùng để phát triển/chẩn đoán, không phải test mù hoặc hai mẫu forest đại diện.
Lượt này không đo source ranking toàn miền, sensitivity của lựa chọn intervention, elapsed-time effort hay ưu thế so với BloodHound.
Không chạy Docker/CE mới, không thay database hoặc gỡ session trong lượt sensitivity.
[Protocol holdout](holdout-evaluation-protocol.md) đã ghi điều kiện và quy trình; chưa có export mới đủ điều kiện được đánh giá theo protocol đó.

## Tái lập và validation

Dùng snapshot sau LocalGroup và pack được tạo bởi `scripts.neo_bloodhound`; runner từ chối scope hoặc scenario bị đổi, snapshot hash không khớp, class bị thiếu và rubric không hợp lệ.
Ví dụ với input local còn giữ, từ repo root và output directory mới:

```sh
.venv/bin/python -m scripts.neo_cost_sensitivity \
  --pack reports/generated/neo-C-sensitivity-20261023/prepared/comparison.json \
  --seamless-snapshot reports/generated/localgroup-fix-20261022/after/inputs/seamless/snapshot.json \
  --wraith-snapshot reports/generated/neo-remediation-post-localgroup-20261023/inputs/wraith/snapshot.json \
  --output-dir reports/generated/neo-C-sensitivity-repeat
```

Input lớn không trong Git; để dựng lại từ raw, dùng lệnh import/pack trong [recipe LocalGroup](localgroup-fix.md#kiểm-chứng-và-tái-lập), rồi truyền các đường dẫn tương ứng.
Evidence cuối nằm ở `reports/generated/neo-C-sensitivity-20261023/analysis-verified/`; lần chạy trước guard fix và một lần dừng trước discovery được giữ riêng, không thay thế kết quả cuối.
Runner cuối được chạy lại đủ cohort sau sửa scope guard; program-set hashes và mọi sensitivity metric khớp lượt canonical đầu.
171 tests liên quan pass, gồm 11 test mới cho rubric, dedup, zero-cost, no-witness, tie, strict reversal và scope/JSON boundary.
Các kiểm tra chất lượng, source/profile/protocol pins và evidence manifest nằm trong summary; chưa chạy full suite hoặc holdout mới.
