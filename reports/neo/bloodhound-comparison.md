# Đối chứng BloodHound: bộ nhỏ, cùng câu hỏi

Trạng thái: đã chuẩn bị query pack và chạy phía neo; **chưa chạy BloodHound live**.
Môi trường cloud không có Docker/Podman. Không cài thêm hạ tầng hoặc dùng BFS
nội bộ để thay kết quả BloodHound. Engine, kỹ thuật và bảng C không đổi.

## Bộ cố định

Mỗi dataset lấy 3 User và 2 Computer bằng hash với seed `neo-decision-v1`,
không lọc theo kết quả tìm đường. Hai đích là nhóm DA/EA quan sát được.
Đây là khảo sát khám phá, không phải blind test: cả hai dataset và một số nguồn
đã được khảo sát trước. Không đổi nguồn sau khi xem kết quả đối chứng.

| Nhóm | Nguồn | Khả năng ban đầu | Số query |
| --- | --- | --- | ---: |
| SEAMLESS chính | 3 User, 2 Computer | Danh tính mạng dùng được | 10 |
| WRAITH chính | 3 User, 2 Computer | User: danh tính mạng; Computer: local admin, không tự có danh tính máy | 10 |
| WRAITH session | Cả 3 máy đủ điều kiện có HasSession | Local admin; session còn dùng được theo giả định scenario | 6 |

EXTDC01 thuộc cả hai nhóm WRAITH: **26 lượt theo nhóm, 24 cặp nguồn–đích duy nhất**.
Nhóm session là kiểm tra khả năng của tính năng, không phải mẫu ngẫu nhiên để
suy tỷ lệ toàn miền. Các nguồn, SID, query Cypher, profile, hash input và source
pins được giữ trong [query pack](bloodhound-query-pack.json).

Phía neo: tối đa 10 chương trình/query, 12 bước semantic, 4.096 expansions,
Top-3 theo C. Witness được native replay bởi runner hiện có.

## Kết quả neo ngày 22/10/2026

| Nhóm | Có witness và C | Không đạt đích | C tốt nhất đã tìm |
| --- | ---: | ---: | --- |
| SEAMLESS chính | 10/10 | 0 | 1–5 |
| WRAITH chính | 6/10 | 4 | 0, 2, 3 |
| WRAITH session | 6/6 | 0 | 2 |

Khử trùng nguồn–đích: 20/24 cặp có witness; 2 cặp C=0 là XADMIN đã có
membership, không phải tìm được một cuộc leo thang mới. Không có error,
Unknown attempt hoặc query chưa có witness vì hết expansion cap.

Bốn cặp không đạt đích thuộc TRUSTER và TARGETCOMPUTERC tới DA/EA.
TRUSTER hết không gian hỗ trợ sau 2 expansions/query; TARGETCOMPUTERC bị
chặn `computer_actor_authenticated` sau 1 expansion/query vì chỉ khai báo
host control. Các cờ no-path chỉ có ý nghĩa trong scope kỹ thuật/giả định này,
không chứng minh an toàn ngoài đời hay BloodHound cũng không tìm được đường.

Mỗi query thành công tìm được 10 chương trình; chưa chứng minh C toàn cục.
SCOTTY_HARTMAN→EA còn ghi nhận giới hạn 12 bước; các hàng khác ghi
`path_limit_reached`. Các ứng viên có C khác nhau, nhưng **không cặp thành
công nào có C thấp hơn đường được tìm đầu tiên** trong lượt này. Không dùng
kết quả đó để tuyên bố xếp hạng C đã cải thiện lựa chọn thực tế.

[Kết quả từng cặp và hash checkpoint](bloodhound-native-results.json) giữ
candidate/program ID, C, expansions, giới hạn và scope digest. Request,
scenario policy và source pins đã được đối chiếu bằng nhau với query pack;
26 checkpoint records đều đủ newline và đúng checksum. Kiểm thử tập trung:
91 pass, gồm raw conversion self-check; Ruff pass. Chưa chạy full suite.

## Tái lập phía neo

Từ repo root, dùng Python 3.14 và dependencies trong README. Dataset raw phải
có sẵn, đúng hai manifest được version trong repo. Không commit raw/generated.
Nếu chưa có snapshot, dùng importer hiện có:

```sh
.venv/bin/python -m scripts.neo_import --raw-dir data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --output-dir reports/generated/bh-inputs/seamless
.venv/bin/python -m scripts.neo_import --raw-dir data/raw/ad_sampledata \
  --manifest data/samples/manifests/ad-sampledata-v1.json \
  --time-policy data/samples/time-policies/ad-sampledata-v1.json \
  --export-prefix 20240305111414 --output-dir reports/generated/bh-inputs/wraith
.venv/bin/python -m scripts.neo_bloodhound \
  --seamless-snapshot reports/generated/bh-inputs/seamless/snapshot.json \
  --wraith-snapshot reports/generated/bh-inputs/wraith/snapshot.json \
  --output-dir reports/generated/neo-bh-run
sh reports/generated/neo-bh-run/neo-commands.sh
```

Dùng output directory mới. Lệnh chuẩn bị chỉ kiểm input và tạo pack/query/lệnh;
không khởi động container, upload, đăng nhập hoặc sửa database. Có Docker CLI
không tự có nghĩa daemon hoạt động. Native commands là các query độc lập,
không gộp khả năng giữa các nguồn.

## Phần BloodHound còn thiếu

1. Dùng bản CE 9.8.0 đã pin bằng image digest trong
   `deploy/bloodhound/compose.seamless.yml`, database mới cô lập cho từng dataset.
   Không tự xóa volume hoặc import chồng dữ liệu cũ.
2. SEAMLESS dùng `scripts.convert_seamless_ce` và kiểm conservation/hash trước
   upload. WRAITH chỉ upload 12 file prefix `20240305111414`, không cả 3 miền.
   Importer CE nhận được dữ liệu chưa có nghĩa các graph đã tương đương.
3. Chạy hai query inventory đầu mỗi file `.cypher`, xuất ID/type/enabled và
   từng triple quan hệ để đối chiếu. Giải thích self-ACE, primary group,
   boundary và AdminTo suy diễn; không đánh đồng lệch số lượng với bug.
4. Chạy các query shortest-path đã cố định. Giữ bản cấu trúc và bản loại User
   disabled riêng. Phân loại khác biệt do input, phạm vi kỹ thuật, giả định
   hoặc budget trước khi nhận xét bên nào bỏ sót.
5. Đối chiếu một can thiệp membership: tìm lại đường sau can thiệp ở cả hai
   bên, không chỉ kiểm đường cũ đã biến mất. Hai ví dụ neo đã có ở
   [báo cáo chuyển dataset](transfer-brief.md) và
   [ví dụ host/session](host-session-example.md); chưa phải đối chứng mới.

Các query được tạo **chưa được kiểm cú pháp/thực thi bởi server BloodHound**.
Chúng là custom scoped Cypher, không đại diện cho toàn bộ tính năng hay mặc
định của BloodHound. BloodHound có shortestPath/allShortestPaths và cho phép
chọn quan hệ; tài liệu chính thức cũng nói session không bảo đảm có credential
dùng lại được:
[Cypher](https://bloodhound.specterops.io/analyze-data/explore/cypher-supported),
[HasSession](https://bloodhound.specterops.io/resources/edges/has-session).

## Không được suy quá kết quả

12 graph hops không bằng 12 bước semantic, nên không dùng hai giới hạn này
để tuyên bố nhanh hơn hoặc chứng minh bên kia không có đường. ShortestPath có
thể chọn bất kỳ đường đồng số cạnh; không chọn đường đồng hạng bất lợi để
chứng minh C của neo tốt hơn. C là công sức expert theo scenario, không phải
thời gian thực nghiệm; Top-3 là best-found. Đường cấu trúc qua kỹ thuật ngoài
scope không tự là lỗi BloodHound. Cắt witness không đồng nghĩa cắt khả năng
đạt đích. Hiện **chưa có bằng chứng mới để kết luận neo hơn BloodHound**.
