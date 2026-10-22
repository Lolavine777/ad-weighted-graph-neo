# Ngoài SEAMLESS: nhập dữ liệu, tìm đường và thử can thiệp

Hướng khóa luận: phân tích đường leo thang đặc quyền có xét chi phí và kiểm chứng
biện pháp giảm thiểu. Phạm vi hiện tại là snapshot tĩnh, phân tích từng miền,
nguồn User/Computer độc lập và đích DA/EA thực sự có trong miền.

## Kết quả đã chạy

Cùng bảng `neo-c-v1`, cùng bộ giả định `neo-standard-v1` được gắn vào snapshot
đang xét, cùng 7 kỹ thuật và budget **1 witness / 12 bước / 1.024 expansions**.
Không sửa điểm theo từng miền hoặc lọc nguồn theo việc đã tìm thấy đường hay chưa.

| Export ngoài SEAMLESS | Node / cạnh | Cặp đã chạy | Có witness, đủ C | Không có đường trong mô hình | Chưa kết luận |
| --- | ---: | ---: | ---: | ---: | ---: |
| GHOST | 65 / 226 | 3 | 2 | 1 | 0 |
| WRAITH | 150 / 758 | 72 | 8 | 58 | 6 |
| PHANTOM | Chưa nhập được | 0 | — | — | — |

Hai export GHOST/WRAITH thuộc cùng corpus `ad_sampledata`; không tính thành hai
bộ dữ liệu độc lập. Đã kiểm checksum đủ 31 file nguồn, 3.518.594 bytes.
75 truy vấn đã chạy không có execution error. Cả 10 witness đã qua native replay:
8 trường hợp vốn đã có quyền (C=0), hai trường hợp cần hành động (C=3).

Sáu ca WRAITH chưa kết luận gồm **4 ca hết expansion budget** và **2 ca blocked
vì còn thiếu điều kiện**. Các nghìn Unknown attempts là số lần thử nhánh,
không phải số query chưa kết luận. Tám lượt dừng sau witness đầu tiên vẫn có
bằng chứng tới đích; chưa chứng minh C tối ưu.

"Không có đường" ở bảng chỉ áp dụng cho đồ thị, kỹ thuật và giả định đang xét;
không kết luận các nguồn đó an toàn trước mọi kỹ thuật AD. Giữ nguyên cả native
flags và status gốc trong JSON; không cộng hai ca blocked vào nhóm kết luận âm.

## Ví dụ mới trên WRAITH

RODCMANAGER là thành viên Administrators. Nhóm này có WriteDacl lên DA và EA.
Với từng đích, chuỗi tìm được là:

| Công việc | C |
| --- | ---: |
| Dùng membership Administrators đã có | 0 |
| Sửa DACL để cấp GenericAll trên nhóm đích | 2 |
| Thêm bản thân vào nhóm đích | 1 |
| Nhận entitlement từ membership vừa thêm | 0 |
| Tổng | **3** |

C là điểm công sức theo rubric, không phải thời gian hoặc xác suất đo thực tế.
Hai query đã được thực hiện lại và đối chiếu witness, program và ledger.

Can thiệp mô phỏng: gỡ **RODCMANAGER → Administrators**. Trên đúng một nguồn
và hai đích DA/EA, engine cắt 2/2 chương trình gốc; tìm lại hoàn tất trong scope
và không thấy bypass, cả hai đích trở thành unreachable trong mô hình.
Gói kết quả lưu trên đĩa qua verifier độc lập bằng native search và replay.
Không suy rộng thành mức giảm rủi ro toàn miền; chưa chấm ảnh hưởng vận hành.

## Các thay đổi nhập liệu

- Chỉ bỏ placeholder được đánh dấu sinh bổ sung, không chứa dữ liệu quan hệ
  và không được tham chiếu; lưu audit từng record. Không bỏ tài khoản thật cô lập.
- Danh tính ngoài miền lấy từ record đã quan sát trong corpus, giữ làm boundary
  để nối SID/DN; không mang quan hệ của export ngoài miền vào phép phân tích.
- DN phải khớp đối tượng đã quan sát; không đoán SID theo tên nhóm. Hai membership
  GHOST trỏ tới DN cũ được giữ thành assessment riêng, các quan hệ hợp lệ còn lại vẫn chạy.
- Nhóm Builtin được xác định theo phạm vi miền khi Computer có bằng chứng primary
  group của DC/RODC; member server vẫn cần đúng thông tin host. Inference đọc được
  cả ID scoped dạng canonical. [Tham chiếu nhóm AD](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-groups).

PHANTOM vẫn bị chặn bởi SID local trên member server thiếu host GUID. Raw còn
có một SID gán cho hai tài khoản khác nhau; không tự chọn một bản ghi để vượt lỗi.
SEAMLESS được nhập lại: nodes, edges, assessments và toàn bộ fact evidence
khớp snapshot trước; vẫn 3.370 node / 56.367 cạnh.

371 test liên quan pass. Full suite đã thử nhưng dừng trước khi hoàn tất;
không ghi nhận là full-suite pass. [Bằng chứng và lệnh thực tế](portability-results.json).
[Audit trước sửa](transfer-audit.json) giữ nguyên kết quả lịch sử ở commit trước.

## Chạy lại

```sh
.venv/bin/python -m scripts.download_ad_sampledata
.venv/bin/python -m scripts.neo_import \
  --raw-dir data/raw/ad_sampledata \
  --manifest data/samples/manifests/ad-sampledata-v1.json \
  --time-policy data/samples/time-policies/ad-sampledata-v1.json \
  --export-prefix 20240305111414 \
  --output-dir reports/generated/wraith-import
.venv/bin/python -m scripts.neo_domain \
  --snapshot reports/generated/wraith-import/snapshot.json \
  --domain-sid S-1-5-21-3702535222-3822678775-2090119576 \
  --output-dir reports/generated/wraith-survey --workers 2
.venv/bin/python -m scripts.neo_domain_report \
  --snapshot reports/generated/wraith-import/snapshot.json \
  --survey reports/generated/wraith-survey \
  --output-dir reports/generated/wraith-remediation --interventions 1
```

Đổi prefix thành `20240305110427` và SID thành
`S-1-5-21-2845847946-3451170323-4261139666` để chạy GHOST; dùng thư mục output mới.
JSON lưu timestamp export thực tế và đủ lệnh/input pins nếu cần tái lập đúng bytes.

## Đánh giá khóa luận tiếp theo

SEAMLESS dùng phát triển; ad_sampledata/NORTH là kiểm tra ngoài SEAMLESS, từng
được khảo sát ở dự án cũ nên không gọi là test mù. Test cuối cần một môi trường
chưa dùng để điều chỉnh neo; không chia ngẫu nhiên node SEAMLESS để thay thế.

Đối chứng BloodHound phải pin phiên bản, cùng byte nguồn và cùng phạm vi miền,
nguồn–đích, quan hệ/kỹ thuật. Đối chiếu graph trước khi so đường. Một lượt BFS
trên canonical graph không được ghi thành kết quả chạy BloodHound.
Cần đo thứ hạng theo C khác số cạnh ở đâu, điều kiện và quyền phát sinh có giá trị
gì, sau can thiệp còn bypass hay không; kèm độ nhạy điểm, thời gian và RAM.
BloodHound đã có [logic cạnh suy diễn](https://specterops.io/blog/2024/01/24/adcs-attack-paths-in-bloodhound-part-1/)
và [quản lý đường tấn công](https://specterops.io/platform/bloodhound-community-edition/).
Chưa có đối chứng live mới và chưa kết luận neo tốt hơn BloodHound.
