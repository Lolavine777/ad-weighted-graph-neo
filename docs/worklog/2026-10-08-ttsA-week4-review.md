# Worklog - 2026-10-08 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#208](https://github.com/nairyuuu/ad-weighted-graph/issues/208) / [#231](https://github.com/nairyuuu/ad-weighted-graph/pull/231), nhánh `feat/208-week4-acceptance` -> `develop`, reviewer `nairyuuu` / M3, Week 4.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.
- Baseline review: `21846233fdc270df212e38a85678d6b6b07c61f0`; engine/catalog được đo giữ trên nền `develop@adee0896009d6180e68fc3d911a4d21aa22c9713`.
- Phân vai: A sửa oracle, runner nghiệm thu, regression, provenance và báo cáo; không sửa `src/engine/` hoặc `src/parser/` của B.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Tái hiện feedback | First-call mutation trên public query; ba test cũ | no_path/0 đường/goal false vẫn PASS; test cũ 3 passed |
| Predicate độc lập | `tests/fixtures/ranking/week4_acceptance_oracle.json`, `tests/test_week4_acceptance_review_regressions.py` | So toàn bộ normative fields; mutation từng field và missing field thành FAIL; defect repaired thành PASS, signature lạ thành FAIL |
| Lỗi coverage B | `--case-id W4-DEFECT-ADAPTER-REJECT` | Public query sinh 3, adapted 2, rejected 1; incumbent C=5 nhưng proof true; normative scope phải bound subset/proof false |
| Zero-action B | `--case-id W4-DEFECT-ZERO-ACTION` | Goal true, 1 đường 0 bước, adapter rejected, no_rated_candidates; không giả công việc hoặc P/I |
| Provenance | Runner v2, file-byte pins, runtime/catalog/source observations | Linux x86_64/Python 3.14.2; revision caller sai bị từ chối; nguồn working-tree được ghi dirty thay vì gán nhãn commit sạch |
| Probe/manual checks | Hàng dataset, CLI và public docs audit | Probe không chạy, command null, không ghi exit code giả; statuses remote không nằm trong output executable |
| Tài liệu | Bốn tài liệu trong `docs/reports/` và amendment worklog ngày trước | Tiếng Việt, mỗi câu một dòng; report/demo không nhắc tracker; D/M-D/M-I với Ledger E thay số roasting không có binding |
| Regression và demo | `.venv/bin/python -m pytest tests/test_week4_acceptance_manifest.py tests/test_week4_acceptance_review_regressions.py -q` | 11 passed trên working tree; smoke chạy mọi khối bash của demo, kiểm checksum và CLI mutation trả exit 1 |
| Semantic determinism | Runner `--check-determinism` | 30 hàng: 22 PASS, 2 KNOWN DEFECT, 3 PENDING B, 2 NOT EXECUTED, 1 BLOCKED RUN, 0 unexpected failures; metadata từng lượt được quan sát riêng |

## Điều học được / quyết định

Baseline equality không là acceptance oracle; mọi normative claim phải có predicate và regression thay actual.
Known defects và dependencies vẫn là non-acceptance, dù runner trả exit 0 vì không có sai lệch bất ngờ.
C/P/I trong Ledger E là synthetic_test_only; không hiệu chỉnh xác suất môi trường thật hoặc định mức roasting.
Zero new work không tương đương canonical ranking fully rated; phải giữ nhãn và P/I disposition rõ khi consume bản sửa.
Giữ worklog cũ kèm amendment, không biến các số lịch sử/runtime hardcode thành evidence mới.
Không có human cross-reproduction hoặc private SEAMLESS run trong phiên này.
Source freeze và validation checkout sạch sẽ được ghi bằng amendment sau khi đo, không điền commit hoặc checksum dự kiến.

## Trở ngại và việc kế tiếp

- #212 vẫn OPEN; PR [#232](https://github.com/nairyuuu/ad-weighted-graph/pull/232) OPEN tại head `7b4129d98a7f01aa2bdb42469895f6b9b1488afb` khi kiểm ngày 08/10, có revision sửa review nhưng chưa được phiên này nghiệm thu hoặc merge.
- PR [#230](https://github.com/nairyuuu/ad-weighted-graph/pull/230) OPEN tại head `4e5328284967c8002f5fab809c76bddd0b6f6254` khi kiểm ngày 08/10; body khai báo sửa blockers, reviewDecision còn CHANGES_REQUESTED, chưa được phiên này xác minh semantics của head mới.
- #228/#229 và CLI #213 vẫn OPEN khi kiểm remote; không suy trạng thái task thành catalog/search/CLI đã triển khai.
- Thiếu authorized raw SEAMLESS và cross-review độc lập; giữ #208/#204 OPEN và không tự merge #231.
- Việc kế tiếp: freeze source, đo hai lượt từ checkout sạch, xuất evidence qua generator rồi đẩy bản sửa và phản hồi từng review thread.

## Amendment đo sau source freeze

Source/input đã chốt tại `eb552af033b1e417c8f8874b841e9886fe0e4ec6`; bản kê mới được generator chạy từ clone sạch, không sửa nhãn revision bằng tay.
Hai tiến trình độc lập ghi thời điểm quan sát `2026-10-08T01:50:20.362600+00:00` và `2026-10-08T01:50:22.328453+00:00`, cùng Linux x86_64/Python 3.14.2.
Cả hai có `checkout_dirty=false`, `dirty_pinned_files=[]` và source/input digest `sha256:3ed34f44e38211b43e4d57bc572ffcaed401ea16415b8eac394580c34c1f6077`.
Semantic digest là `sha256:92c5454eab9cb002e31c01d2ccb88f51bfc9c8b81d3f335c9b6d46abd9bee465`; SHA-256 của file semantic đã serialize là `199a90a9907d44b19d095fecb37c5ae71bf9c52a10ab3b423ef01246a333fb95`.
Hai file semantic giống từng byte và khớp fixture đã lưu; timestamp/runtime không bị cố định để tạo equality.
Năm khối bash của demo chạy nguyên văn từ clone sạch đều exit 0; checkout còn sạch sau smoke.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Full suite trên source freeze | `.venv/bin/python -m pytest -q` tại clone `eb552af` | 1939 passed, 10 skipped, 48 subtests passed; 167.60s |
| Lý do skip | pytest short summary | 9 skips cần raw/private inputs; 1 Windows junction test không áp dụng Linux; không coi skips là acceptance |
| Quality trên clone | Ruff check/format, yamllint, contract, repository, diff check | Tất cả qua; contract xác minh 2 synthetic fixtures |
| Compose config | `NEO4J_PASSWORD=ci-validation-placeholder docker compose --env-file .env.example --profile graph config --quiet` | Exit 0; chỉ kiểm cấu hình, không khởi động services |
| Source equivalence | File pins của commit nguồn so với package evidence sau đo | Commit evidence tiếp theo chỉ cập nhật manifest metadata và worklog; không thay executable/input bytes đã đo |

PR #231 còn OPEN, chờ B rereview và CI tại head sau push; kết quả CI của head cũ không được dùng cho bản sửa mới.
Hai lỗi #212 vẫn hiện diện ở nguồn đo, dù #232 có proposed fixes chưa merge; #230 có head mới chưa được phiên này nghiệm thu.
Không tự merge PR hoặc đóng #208/#204; validation xanh không xóa các blockers về implementation, private inputs và human cross-reproduction.

## Follow-up CI Windows

CI tại `e6952a0` có Ubuntu, quality, Compose và branch policy xanh nhưng Windows smoke thất bại.
Log job `113110054279` của run `37715227440` xác nhận PATH chọn launcher WSL thay Git Bash, báo không có Linux distribution; acceptance/provenance tests trên Windows vẫn qua.
Đây là lỗi chọn shell trong test mới của A, không phải lỗi engine B.
Sửa test để lấy Bash từ installation của Git trên Windows, giữ smoke chạy thật thay vì skip; thêm regression giả lập layout Git/cmd và Git/bin để tránh chọn WSL từ PATH.
Demo ghi rõ Bash/POSIX và đường Python venv tương ứng khi chạy Windows/Git Bash.
Source/test pins thay đổi nên evidence được chạy lại qua generator; không giữ nhãn clean source hoặc source/input digest của lượt trước cho test mới.
Các kết quả source `eb552af` ở amendment trước được giữ là evidence lịch sử của revision đó.

## Đo lại sau sửa chọn shell

Source/test freeze mới là `e38e0af824e256dfb2a7b7bc04aa8f808d5bb885`; engine B và toàn bộ oracle/scoring inputs giữ nguyên.
Hai tiến trình từ clone sạch ghi thời điểm `2026-10-08T02:04:20.914943+00:00` và `2026-10-08T02:04:22.835910+00:00`, cùng source/input digest `sha256:748bd7dd71896f7b7a961f92ca27088e741313b723742fb9a27967e54a1f8824`.
Cả hai ghi checkout sạch, không có dirty pinned files; semantic digest vẫn `sha256:92c5454eab9cb002e31c01d2ccb88f51bfc9c8b81d3f335c9b6d46abd9bee465`, file semantic vẫn giống từng byte với fixture.
Full pytest tại source freeze mới: 1940 passed, 10 skipped, 48 subtests passed trong 163.68s; các skips giữ lý do đã nêu ở trên.
Focused acceptance/regression/demo sau sửa: 12 passed, gồm regression chọn Git Bash; full Linux suite chạy smoke thật các lệnh demo.
Ruff check/format, yamllint, repository/contract checks, diff check và Compose config tại clone sạch đều qua.
Commit evidence sau source freeze mới chỉ cập nhật metadata manifest và worklog; Windows CI cho head mới chờ sau push, không nhận kết quả Windows cũ là xanh.
Rà lại remote sau CI follow-up: #230/#232 vẫn OPEN ở cùng heads nêu trên; develop vẫn `adee0896009d6180e68fc3d911a4d21aa22c9713`.
