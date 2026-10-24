# Rà soát rubric C: giữ giá, làm rõ ý nghĩa

Ngày 24/10/2026. Review tĩnh trên các summary đã công bố, từ main `08755cfd`.
**Chưa có bằng chứng đủ để thay giá production.** Đã đối chiếu 9 cặp và kiểm
phép cộng của 30 program summaries. Đây không phải 9 xác nhận thực nghiệm độc lập.

## Phương pháp

Chốt tiêu chí trước khi tính các phân loại mới: cùng profile thì giữ tie; thêm công
việc không âm không được làm giảm C; quyền có sẵn không tạo thêm công việc;
khác họ công việc thì chưa suy ra thứ tự công sức thực tế nếu thiếu mốc độc lập.
Chọn cặp theo đặc trưng ledger/route và program ID, không chọn theo C.
Người phân tích là AI đã thấy các điểm công bố: **không phải blind rating hoặc expert panel**.

## Chín cặp đã kiểm

| Ca | C A / B | Kết quả |
| --- | --- | --- |
| S01 — SEAMLESS User 1 / DA | 2 / 2 | Cùng vector họ công việc: tie nhất quán; công sức thật chưa xác nhận |
| S02 — SEAMLESS User 1 / EA | 5 / 6 | C tăng theo phần việc công bố thêm; kiểm tính nhất quán |
| S03 — SEAMLESS User 2 / DA | 1 / 1 | Cùng vector họ công việc: tie nhất quán; công sức thật chưa xác nhận |
| S04 — SEAMLESS User 2 / EA | 4 / 5 | C tăng theo phần việc công bố thêm; kiểm tính nhất quán |
| S05 — SEAMLESS User 3 / DA | 1 / 1 | Cùng vector họ công việc: tie nhất quán; công sức thật chưa xác nhận |
| S06 — SEAMLESS User 3 / EA | 4 / 5 | C tăng theo phần việc công bố thêm; kiểm tính nhất quán |
| W01 — WRAITH / published DA family-profile tradeoff | 4 / 5 | Khác họ công việc: thiếu mốc để xác nhận thứ tự công sức |
| T01 — Synthetic / two_routes | 3 / 1 | Khác họ công việc: thiếu mốc để xác nhận thứ tự công sức |
| T02 — Synthetic / existing entitlement | 0 / 3 | Không thêm công việc theo fixture: C=0 hợp quy ước |

Ba cặp SEAMLESS tới EA là biến thể trên cùng route, không phải ba lựa chọn
cấu trúc khác nhau. Ba cặp tới DA có các route khác nhau nhưng cùng profile công việc.
Chín cặp chỉ bao phủ bốn mẫu lập luận. Bốn kiểm tra anchor/extension nhất quán,
ba tie đúng theo profile, hai tradeoff khác họ vẫn chưa có đáp án độc lập.

## Kết luận về rubric

- Chưa phát hiện mâu thuẫn số học trong summary hoặc lý do có căn cứ để đổi giá cụ thể.
- Bằng chứng trong panel này chủ yếu là diễn giải công việc và phân biệt biến thể thêm việc.
- Chưa kiểm chứng được lợi ích chọn giữa các họ phương án khác nhau. Không dùng
  đáp án synthetic tính từ cùng bảng giá để tự xác nhận giá đó đúng.
- Tie giữa các profile giống nhau là giới hạn thông tin của rubric; không tự thêm
  điểm chỉ để ép thành thứ hạng duy nhất.

## Đề xuất chỉnh định nghĩa, chưa đổi giá

Gọi C là **chỉ số công sức quy ước theo scenario**, giữ tổng cộng như một giả định
thiết kế. C=4 không có nghĩa gấp đôi thời gian/công sức thực tế của C=2.
C=0 không có nghĩa không có hành động: có thể là hành động ở mức sàn ordinal.
Khi trình bày nên giữ cả thành phần công việc, số thao tác active và route; không
diễn giải Top-3 program IDs thành ba phương án độc lập nếu chúng cùng route.
Định nghĩa T1 chỉ về mức tùy biến công cụ, T2 về thao tác/xác minh trong scenario;
không ngầm đưa xác suất thành công, tác động nghiệp vụ hoặc thời gian vào cùng C.
Đây là đề xuất diễn giải; lượt này không sửa scorer, UI, bảng giá hoặc semantic gates.

[NIST SP 800-30r1, mục 2.3.2, trang in 14](https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-30r1.pdf) phân biệt thang định
lượng với thang bán định lượng và yêu cầu giải thích ý nghĩa các mức/giả định.
Áp dụng ở đây là lập luận phương pháp; NIST không cung cấp giá AD, không phê
duyệt công thức cộng này và không xác nhận các thứ hạng của neo.

## Giới hạn và tái lập

Các summary thiếu actor/context/work-unit IDs đầy đủ. So phần việc công bố không
chứng minh state tương đương, công việc thực sự dư thừa, hoặc phép khử trùng runtime đúng.
Không chạy engine hay replay mới. Kết quả dùng các summary lịch sử, không phải
một lượt discovery mới của main. Không suy ra minimum-C hoặc ưu thế BloodHound.
Các ledger GoodHound còn ở evidence local nên không được suy đoán để đủ mẫu.

Từ repo root, chỉ cần Python với thư viện chuẩn và output directory mới:

```sh
python -m scripts.research.neo_rubric_review --output-dir reports/generated/rubric-review-repeat
```

Runner kiểm SHA256 năm input, đối chiếu giá hiện hành với hai artifact lịch sử,
kiểm 30 ledger summaries rồi dựng lại JSON và Markdown. File kết quả gốc:
[rubric-review-results.json](rubric-review-results.json). Giữ nguyên mọi evidence lịch sử.
