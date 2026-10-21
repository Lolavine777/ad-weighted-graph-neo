# Worklog - 2026-10-05 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #190 / M3
- Thời gian thực tế ước lượng: 4 giờ
- Nguồn: develop 6fbb410db9b2371fbe6ce3149fe484c2de306da3 (latest develop).

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Thu thập baseline toàn suite | `python -m pytest --collect-only -q` | 45 files, 909 test functions, 1.638 collected cases |
| Đo thời gian chạy và top durations | `python -m pytest --durations=30` | 1.636 passed, 2 skipped (Windows OS alias/fifo hợp lệ), 0 failed; runtime 210.66s – 218.25s |
| Báo cáo audit chi tiết | `docs/research/test-suite-audit.md` | Báo cáo toàn diện tiếng Việt: thống kê 6 phân hệ, top 30 chậm nhất, 8 danh mục audit, bảng quyết định chi tiết và kế hoạch PR theo ưu tiên |
| Bằng chứng kiểm chứng mutation | `tests/test_contract.py` | Tạm nới lỏng validator từ `value >= 1.0` sang `value >= 0.0`; `test_invalid_cost_is_rejected[0]` FAILED ngay lập tức |
| Dọn dẹp nhỏ ít rủi ro | `tests/test_contract.py` | Gộp `test_zero_cost_is_rejected` vào `test_invalid_cost_is_rejected`; giảm 1 hàm test thừa, bảo toàn 100% collected cases và fault detection |
| Kiểm tra chất lượng repo | `python scripts/check_contract.py`<br>`python scripts/check_repository.py` | Contract và 2 synthetic fixtures hợp lệ; 375 tracked/unignored files đạt yêu cầu |
| Kiểm tra định dạng và linter | `python -m ruff check .`<br>`python -m ruff format --check .`<br>`python -m yamllint .` | Toàn bộ checks pass |

## Điều học được / quyết định

1. **Số lượng test không phải là nguyên nhân chính gây chậm CI**: 82% thời gian chạy (176.74s / 215.70s) nằm ở 5 file test của các script nghiên cứu, chủ yếu do việc gọi `subprocess.run` OS lặp đi lặp lại hàng chục lần trong các hàm test được parametrize.
2. **Core Parser và Engine cực kỳ tinh gọn và nhanh**: Toàn bộ 16 file core parser chỉ tốn 8.89s; toàn bộ 4 file search & ranking engine chỉ tốn 3.91s; toàn bộ semantics chỉ tốn 7.23s.
3. **Phân định rõ ranh giới kiểm thử**: Không nên lặp lại ma trận tổ hợp trường dữ liệu ở tầng CLI bằng subprocess. Tầng CLI chỉ nên kiểm tra kết nối, parse cờ lệnh và exit code; ma trận giá trị và điều kiện biên nên được kiểm tra ở tầng in-process unit test.
4. **Không tùy tiện xóa test**: Mọi đề xuất gộp hoặc xóa đều phải có bằng chứng chứng minh hành vi nào vẫn được bảo vệ và đã được kiểm chứng bằng fault injection.
5. **Đối chiếu #187 và #175**: Khoảng trống `PrimaryGroupSid` (#187) và golden scenarios (#175) đang được phát triển độc lập trên các branch chuyên biệt, cần tích hợp đúng thời điểm mà không làm suite phình mất kiểm soát.

## Trở ngại và việc kế tiếp

- Đã hoàn thành báo cáo audit và cleanup nhỏ ban đầu theo đúng tiêu chí của Issue #190.
- Tạo PR vào `develop` và comment tóm tắt bằng chứng vào Issue #190 (dùng `Refs #190`).
- Các bước tối ưu tiếp theo (chuyển đổi in-process cho các CLI tests chậm) được tách thành các PR tiếp theo theo thứ tự ưu tiên P1–P4 đã nêu trong báo cáo.
