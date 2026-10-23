# Kiểm tra minimum-C trên ca có đáp án tính tay

Ngày 23/10/2026, từ `main@e22fd59`. Thử nghiệm synthetic dùng nguyên engine,
catalog, bảng `neo-c-v1` và Dijkstra có sẵn. Không đổi preset hoặc thuật toán chạy
thực tế. [Kết quả và input/source hashes](minimum-probe.json).

## Hai đường tới cùng nhóm đích

User nguồn đã có danh tính mạng dùng được, cùng một context xác thực.
Các điều kiện được khai báo tường minh trong fixture, không phải dữ liệu AD thật.

| Đường | Công việc | Graph hops | Bước semantic | C |
| --- | --- | ---: | ---: | ---: |
| A | WriteDacl → cấp GenericAll → thêm membership → nhận quyền | 1 | 3 | 2+1+0 = **3** |
| B | Hai membership → reset User khác → dùng danh tính → membership đích | 4 | 5 | 0+0+1+0+0 = **1** |

A ít cạnh và ít bước hơn, nhưng B ít công sức hơn theo bảng C hiện hành.
Cả hai đường đều được kiểm native replay. Với scope hữu hạn này, các tuyến chỉ
có công việc tuần tự; giá WriteDacl=3 là giá cả recipe, GenericAll→reset User=1,
MemberOf=0. Đây là mapping riêng cho fixture, không phải compiler AD tổng quát.

## Kết quả cùng fixture, chỉ đổi budget

| Search | Tối đa chương trình | C tìm được | Expansions | Minimum được chứng minh |
| --- | ---: | ---: | ---: | --- |
| FIFO | 1 | 3 | 12 | Không |
| Neo-guided | 1 | 3 | 3 | Không |
| FIFO | 10 | 1 | 45 | Không |
| Neo-guided | 10 | 1 | 30 | Không |
| FIFO / neo-guided | 1.000 | 1 | 110 mỗi bên | Có, cả hai tìm hết 56 chương trình |

Cap 1.000 chỉ là trần; engine hết không gian trước khi chạm trần.
Ở cap 10 đã tìm đúng giá trị C=1 nhưng vẫn thiếu bằng chứng đầy đủ.
Điều này phân biệt chất lượng đáp án với khả năng chứng minh minimum.
Giới hạn 3 bước giữ được A nhưng bỏ B; giới hạn 1 expansion chưa tìm được đường.
Cả hai trường hợp đều không được báo minimum.

Dijkstra theo số cạnh chọn A, ánh xạ C=3. Dijkstra theo công sức chọn B, C=1.
Tuyến weighted Dijkstra trùng tuyến của một witness đã native replay và chấm C
độc lập trong tập đầy đủ. Đây là đối chứng thuật toán synthetic, không phải lượt
chạy BloodHound hay benchmark tốc độ.

## Kiểm tra điều kiện và giá 0

- Nếu có bằng chứng xác thực của User được reset bị từ chối, B không thực hiện
  được; native search và Dijkstra đã loại tuyến đó cùng cho minimum C=3.
- Nếu chỉ thiếu thông tin xác thực, native vẫn có witness A với C=3 nhưng không
  chứng minh minimum, vì B có thể dùng được với C=1. Đồ thị chỉ giữ tuyến chắc
  chắn không được dùng để tự nhận C=3 là minimum toàn scope.
- Với tuyến membership có sẵn C=0, neo-guided dừng ở đường đầu vẫn có thể chọn
  A với C=3. Tìm đầy đủ cho C=0; membership không bị tính giá 1 theo số cạnh.

Đủ 26 query: bốn ca, hai search orders, ba path caps, thêm hai budget controls.
Mọi chương trình tìm được đều được native replay và đối chiếu C với tổng các
công việc khác nhau tính riêng từ recipe; tập chương trình/C đầy đủ giữa FIFO
và guided khớp nhau. Điều kiện thiếu không bị tự chuyển thành đúng.

## Ý nghĩa với đề bài

Thử nghiệm cho thấy C có thể chọn đường khác và rẻ hơn cách chọn ít cạnh, và
scope nhỏ có thể chứng minh minimum bằng engine hiện hữu. Việc dừng ở witness
đầu, hoặc chỉ tăng số candidate cố định, chưa bảo đảm minimum nói chung.
Dijkstra đủ cho fixture đã xử lý điều kiện này; chưa có căn cứ phải xây thêm
engine/state model. Nó không chứng minh projection đơn giản đúng cho mọi chuỗi
có quyền phát sinh, AND prerequisites hoặc dùng chung công việc.

Chưa chạy lại cohort SEAMLESS/WRAITH, chưa cải thiện search production và chưa
chứng minh neo chọn C tốt hơn BloodHound trên dữ liệu thật. Lượt này tạo ca
kiểm tra có đáp án độc lập và tiêu chí rõ để đánh giá một thay đổi search sau đó.

Tái lập từ repo root với dependencies trong README, không cần raw hoặc Docker:

```sh
.venv/bin/python -m scripts.neo_minimum_probe --output-dir reports/generated/minimum-repeat
.venv/bin/python -m pytest tests/test_neo_minimum_probe.py -q
```

Runner từ chối output directory đã có và dừng nếu oracle, native replay/C hoặc
đối chứng Dijkstra không khớp. Các giới hạn và cờ proof được giữ trong JSON.

Kiểm thử: 124 tests liên quan pass, gồm 12 test mới; Ruff pass. Hai lượt CLI ở
process riêng cho results JSON giống từng byte. Chưa chạy full suite; không
thay source pin của engine/parser hoặc cập nhật các hash kiểm chứng lịch sử.
