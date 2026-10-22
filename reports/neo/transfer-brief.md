# Ngoài SEAMLESS và đối chứng BloodHound

## Mục tiêu khóa luận

Phân tích đường leo thang đặc quyền trong Active Directory có xét chi phí
và kiểm chứng biện pháp giảm thiểu. Phạm vi chính: snapshot tĩnh, phân tích
từng miền, nguồn User/Computer độc lập, đích DA và EA nếu có trong miền.

Neo phải nhận dataset mới qua cùng pipeline, không sửa SID, tên miền, điểm C
hay thứ tự tìm kiếm riêng cho từng môi trường để tạo kết quả đẹp.

## Chia dữ liệu và tiêu chí

| Vai trò | Dữ liệu | Cách sử dụng |
| --- | --- | --- |
| Phát triển | SEAMLESS | Sửa lỗi, chọn cấu hình và phân tích ví dụ |
| Kiểm tra ngoài SEAMLESS | ad_sampledata, sau đó NORTH | Giữ bảng C và ngân sách chung; công bố cả ca không chạy được |
| Test cuối | Một môi trường chưa dùng để điều chỉnh neo | Chốt nguồn, đích và cấu hình trước khi chạy; không tách ngẫu nhiên các node SEAMLESS để gọi là dataset độc lập |

ad_sampledata/NORTH từng được khảo sát ở dự án cũ: gọi là kiểm tra ngoài SEAMLESS,
không gọi là test mù. Test cuối chưa được chọn. Dữ liệu lab không chứng minh
hiệu quả trên mọi AD đang vận hành.

## Đo ưu thế thay vì giả định ưu thế

Đối chứng BloodHound phải pin phiên bản, dùng cùng byte nguồn, cùng miền,
cùng nguồn–đích và công bố các loại quan hệ/kỹ thuật nằm trong phạm vi so sánh.
Đối chiếu node/cạnh trước, giải thích chênh lệch rồi mới đối chiếu đường.

| Điều muốn chứng minh | Phép đo |
| --- | --- |
| C hữu ích hơn số cạnh để chọn đường | Tìm ca thứ hạng khác nhau; giải thích công việc và C của cả hai; kiểm tra độ nhạy của điểm |
| Theo dõi quyền phát sinh có giá trị | Đối chiếu chuỗi hành động và điều kiện trên cùng ca; xác minh bằng lab/ca có đáp án biết trước |
| Can thiệp có hiệu quả | Tách số chuỗi cũ bị cắt, số cặp thực sự mất đường, C trước/sau và đường vòng |
| Sản phẩm dùng được trên dataset mới | Tỉ lệ nhập thành công, lỗi nhập, witness kiểm chứng được, ca hết budget, thời gian và RAM |

Một lượt BFS trên canonical graph chỉ là baseline theo số cạnh, không được ghi
thành kết quả chạy BloodHound. Số expansions của hai loại engine không cùng đơn vị.
C của đường BloodHound phải được chuyển thành hành động và chấm bằng cùng rubric;
không gán C theo số cạnh rồi gọi là so sánh chi phí. Chưa có chứng minh tối ưu toàn cục.

BloodHound đã có phân tích điều kiện, cạnh suy diễn và quản lý/khắc phục đường tấn công.
Vì vậy, riêng “gắn trọng số” hay “tìm choke point” chưa đủ để tuyên bố tính mới.
Đóng góp dự kiến của neo là mô hình trạng thái và công việc có giải thích,
kèm đánh giá can thiệp tái lập; mức cải thiện phải được thực nghiệm xác nhận.
Nguồn đối chiếu: [logic cạnh suy diễn](https://specterops.io/blog/2024/01/24/adcs-attack-paths-in-bloodhound-part-1/)
và [phân biệt Community/Enterprise](https://specterops.io/platform/bloodhound-community-edition/).

## Kiểm tra đầu vào đã chạy

Đã tải và kiểm SHA-256 của đủ **31 file / 3.518.594 bytes** từ
[mirror được pin](https://github.com/SquidSec/BloodBash/tree/a465568cc9058d2faa8d04c2dd3e600c68e9d2c7/SampleSharphoundADData).
Đây là hash file JSON giải nén, không phải khẳng định về archive ZIP lịch sử.

Đã sửa hai lỗi hẹp: nhận diện ID có tiền tố miền trong export hiện đại, và
không dùng cờ ACL mặc định của bản ghi bổ sung rỗng để phủ định bản ghi đầy đủ.
Mọi biểu diễn gốc vẫn được giữ; xung đột giữa các bản ghi đầy đủ vẫn báo lỗi.

| Export | Kết quả hiện tại |
| --- | --- |
| PHANTOM | Lỗi nhập: quan hệ local SID thiếu host GUID để xác định phạm vi |
| GHOST | Lỗi nhập: NETWORK SERVICE được gắn tiền tố miền nhưng thiếu host GUID |
| WRAITH | Lỗi nhập: quan hệ local SID thiếu host GUID để xác định phạm vi |

Chưa export nào trong ba export này qua được đầu vào; chưa chạy search hay chấm C
trên chúng. Những lỗi này không được cộng vào query Unknown hoặc no-path.
Ngoài ra, raw PHANTOM có SID `...-2186` xuất hiện với hai tên tài khoản,
trạng thái enabled và container khác nhau; chưa có cơ sở tự chọn một bản ghi.

Lệnh nhập chung đã dựng lại SEAMLESS và được đối chiếu với snapshot trước.
292 test parser/neo liên quan pass; chưa chạy full suite. Bằng chứng:
[audit máy đọc được](transfer-audit.json).

## Tái lập kiểm tra ngoài SEAMLESS

```sh
.venv/bin/python -m scripts.download_ad_sampledata
.venv/bin/python -m scripts.neo_import \
  --raw-dir data/raw/ad_sampledata \
  --manifest data/samples/manifests/ad-sampledata-v1.json \
  --time-policy data/samples/time-policies/ad-sampledata-v1.json \
  --export-prefix 20240305110427 \
  --output-dir reports/generated/neo-ghost-import
```

Lệnh thứ hai hiện trả mã 2 với `import_error`, chưa tạo snapshot. Prefix là
`20240305110018` cho PHANTOM và `20240305111414` cho WRAITH. Manifest vẫn
kiểm toàn bộ 31 file; các Domain record được giữ làm ngữ cảnh định danh.
`scripts.neo_domain --domain-sid ...` đã cho chọn miền, và chỉ chọn DA/EA
thực sự quan sát được, không bắt miền con phải có Enterprise Admins.

Việc tiếp theo: xử lý phạm vi định danh của các export này với báo cáo rõ phần
phân tích được; sau đó khóa cấu hình và chạy đối chứng. BloodHound live chưa chạy
trong vòng đánh giá này; môi trường hiện tại chưa có Docker.
