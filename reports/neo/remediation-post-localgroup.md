# Remediation WRAITH sau sửa LocalGroup

Ngày 23/10/2026, chạy lại từ code `e22fd59` với parser LocalGroup đã sửa, raw WRAITH prefix `20240305111414` đúng manifest và graph có 150 node, 770 cạnh, gồm 22 AdminTo.
Engine, policy, preset và bảng C không đổi về ngữ nghĩa.
Một lỗi indentation YAML có sẵn trong catalog được sửa; đã kiểm parsed YAML trước/sau giống hệt nhau.
[Summary và hash evidence](remediation-post-localgroup-results.json) giữ kết quả có cấu trúc.

**Ba can thiệp cũ giữ nguyên kết quả và C; với TRUSTER, bỏ riêng session EXTCA01 không đủ vì còn bypass qua UNCON.**
Đây là phân tích mô phỏng trên snapshot và database BloodHound CE thí nghiệm, không phải thay đổi AD thật.

## Kết quả đã kiểm

Cùng cohort, scenario host/session và budget 10 programs, 12 semantic steps, 4.096 expansions/query của [đối chứng cố định](bloodhound-comparison.md).
Mỗi can thiệp độc lập bắt đầu từ graph nguyên vẹn và cùng foothold ban đầu.

| Nguồn và can thiệp | Neo tới DA / EA | BloodHound CE tới DA / EA | Diễn giải |
| --- | --- | --- | --- |
| RODCMANAGER, gỡ membership Administrators | Có / Có, C=3 / 3 | Có / Có | Quyền AdminTo trực tiếp tới EXTDC01 và session BM vẫn còn |
| EXTCA01, bỏ session BM trên EXTCA01 | Không / Không, 3 expansions/đích | Không / Không, 404 và database xác nhận rỗng | Native no-path proof trong scope local-admin-only |
| EXTCA01, gỡ BM→DA | Có / Có, C=5 / 2 | Có / Có | DA còn bypass qua EA→WriteDacl→DA |
| TRUSTER, bỏ session BM trên EXTCA01 | Có / Có, C=3 / 3 | Có / Có | Chuyển sang UNCON→BM, 23 expansions/đích |
| TRUSTER, bỏ session BM trên cả EXTCA01 và UNCON | Không / Không, 34 expansions/đích | Không / Không, 404 và database xác nhận rỗng | Native no-path proof chỉ cho TRUSTER trong catalog/scenario này |

Hai can thiệp TRUSTER là chẩn đoán bổ sung sau khi xem graph đã sửa, không nhập vào cohort cố định hoặc gọi là test mù.
Không còn đường cho TRUSTER không có nghĩa mọi nguồn đều bị ngắt: session BM trên EXTDC01 vẫn giữ nguyên và vẫn dùng được cho nguồn có quyền tới host đó.
Tất cả witness được giữ đều qua native replay khi ghi, cùng kiểm tra program identity của helper `compact_witness`.
Những query thành công vẫn chạm cap 10 chương trình, nên C=3 và C=5 là best-found, chưa phải minimum toàn cục.
Không có execution error hoặc Unknown attempt trong năm can thiệp.

Đã query lại CE thật cho WRAITH chính và session: 32 request gồm hai biến thể của 16 lượt, 28 response có đường.
WRAITH chính vẫn 8/10 và session 6/6, khớp kết quả sau LocalGroup; không chạy lại SEAMLESS trong lượt này.
Node/edge inventory CE khớp multiset lịch sử; thứ tự trả về có thể đổi sau restore.
Parity không còn AdminTo chỉ CE giữa các node chung; hai MemberOf bổ sung CE, self-ACE, boundary và 11 AdminTo membership suy diễn của neo giữ cách giải thích cũ.

## Khôi phục và giới hạn diễn giải

Cả năm can thiệp đều xác minh cùng digest của toàn bộ relationship triples và properties trước/sau restore.
Không xóa volume, không import lại CE và không đụng stack ngoài project `neo-bh-wraith-20261022-verified`.
Mỗi lần DELETE có journal trước, restore bằng MERGE để không nhân đôi cạnh khi trạng thái commit chưa rõ.
Diagnostic hai session đăng ký toàn bộ restore trước DELETE bằng ExitStack, nên một request restore lỗi không ngăn các restore khác và kiểm digest cuối.
Nếu restore hoặc kiểm digest thất bại, command báo lỗi và journal được giữ để phục hồi; không ghi thành công giả.
Trong diagnostic TRUSTER, các guard snapshot/endpoint/journal và kết quả dùng exception tường minh, vẫn chạy với Python `-O`.

Đây là fresh-foothold rediscovery sau sửa graph.
Bỏ session không tự thu hồi credential đã bị đánh cắp trước đó; lượt này không mô phỏng attacker giữ credential qua can thiệp.
Preset host-compromise chỉ khai báo local admin, chưa cấp danh tính mạng tài khoản máy; không mô tả như mô hình SYSTEM đầy đủ.
No-path chỉ có nghĩa không có chương trình trong snapshot, catalog và scenario đã khai báo, không chứng minh AD an toàn trước mọi kỹ thuật.
Không suy thành giảm rủi ro toàn miền hoặc ưu thế độc quyền của neo: BloodHound cũng tìm ra bypass khi query lại.

## Tái lập

Từ repo root, chạy recipe đối chứng với tag/cổng mới theo [hướng dẫn BloodHound](bloodhound-comparison.md#tái-lập-và-evidence), hoặc dùng project WRAITH thí nghiệm đang có nếu input vẫn đúng manifest.
Không chạy diagnostic trên database AD thật hoặc một project không dành cho thử nghiệm.
Lệnh dưới đây dùng input và project còn giữ trên máy này; output directory phải mới:

```sh
run=reports/generated/neo-remediation-post-localgroup-20261023
unset BLOODHOUND_URL NEO4J_URL NEO4J_USER NEO4J_SECRET
export BLOODHOUND_PORT=38080 NEO4J_WEB_PORT=37474 NEO4J_BOLT_PORT=37687
.venv/bin/python -m scripts.neo_bloodhound_live --dataset wraith --remediation \
  --project-name neo-bh-wraith-20261022-verified \
  --pack "$run/native-integrated/comparison.json" \
  --snapshot "$run/inputs/wraith/snapshot.json" \
  --output-dir "$run/live-remediation-repeat"
.venv/bin/python -m scripts.neo_truster_remediation \
  --project-name neo-bh-wraith-20261022-verified \
  --pack "$run/native-integrated/comparison.json" \
  --snapshot "$run/inputs/wraith/snapshot.json" \
  --output-dir "$run/truster-repeat"
```

Với project mới từ recipe đầy đủ, đổi `run`, tên project và cổng theo lần tạo đó; không thay URL để lách kiểm tra ownership.
Raw/generated và journal lớn giữ local trong evidence root ghi ở summary, không commit.

Validation sau integration: 193 tests của parser/inference, host/session, BloodHound, remediation, diagnostic, catalog reuse và minimum/refinement pass; ba test diagnostic kiểm restore lỗi trước/sau commit và endpoint guard với optimized Python.
Sau khi tích hợp ba commit remote tới `ec4bfdf`, đã chạy lại cả năm can thiệp trên code kết hợp, diagnostic dùng Python `-O`; kết quả và digest khôi phục giữ nguyên.
Opt-in refinement của remote không được bật trong đối chứng này.
Các kiểm tra chất lượng được ghi trong summary.
Chưa chạy full suite, toàn miền mới, độ nhạy bảng C hoặc đánh giá mù trên môi trường mới.

## Công việc tiếp theo

Giữ cohort hiện tại làm regression, không dùng tiếp để tự nhận là tập đánh giá chưa từng thấy.
Ưu tiên chốt protocol đánh giá và chạy trên môi trường AD chưa dùng để điều chỉnh neo, gồm kết quả bất lợi, Unknown, no-path theo scope và độ nhạy điểm C.
Chưa có bằng chứng neo tìm nhiều đường hơn, chọn C tối ưu hơn hoặc nhanh hơn BloodHound.
Mục tiêu khóa luận vẫn còn phần đánh giá đó; lượt này khép kiểm chứng remediation sau sửa nhập liệu.
