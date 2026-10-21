# #264 Phase 1 - thiết kế và kế hoạch

Owner A; reviewer B; base develop `da21fbb`.
User đã yêu cầu làm tự chủ tới một PR, nên các lựa chọn thiết kế thường lệ được xử lý trong phạm vi đó.

Chọn registry mới theo scenario/context/full successful history, dùng nguyên provider và public API/CLI/orchestration.
Không chọn packet chấm từng path vì caller phải tự viết đường và khó tái sử dụng.
Không sửa frozen basis vì method, compute policy và population mới không tương đương Week 4.

- [x] Đọc #264/#259/#265, instructions, develop và closure Week 4.
- [x] Freeze proposal, independent Fraction oracle và historical byte pins trước engine run mới.
- [x] Viết test trước cho public generated flow, pending gate, exact arithmetic và refusal matrix.
- [x] Thêm research consumer tối thiểu, dựng registry bằng identity formula từ declarative event inventory, không lấy keys từ engine output.
- [x] Chạy baseline frozen và scenario mới bằng API, hai CLI processes và orchestration.
- [x] Báo coverage thực pending riêng với bản sao engineering test gate; không self-activate.
- [x] Kiểm tra historical bytes, full pytest, lint, repository checks; bàn giao B và mở một PR.

Mô hình recovery là counterfactual uniform24, không khẳng định mật khẩu thật V_A là uniform24.
Ba interval vận hành là đề xuất chuyển giao expert scenario đã có, cần B quyết định từng context/history.
Nếu B không chấp thuận population/compute floor/transfer hypothesis, prefix tương ứng giữ unrated theo blocker đã ghi, không nới interval tùy ý.
