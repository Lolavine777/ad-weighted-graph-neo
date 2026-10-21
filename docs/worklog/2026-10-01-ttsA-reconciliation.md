# Worklog - 2026-10-01 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#47](https://github.com/nairyuuu/ad-weighted-graph/issues/47), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48), [#82](https://github.com/nairyuuu/ad-weighted-graph/issues/82), [#139](https://github.com/nairyuuu/ad-weighted-graph/issues/139) / [PR #157](https://github.com/nairyuuu/ad-weighted-graph/pull/157) / M2.
- Thời gian thực tế ước lượng: Phiên đầu ghi khoảng 60 phút có AI hỗ trợ; lượt sửa review không có phép đo thời lượng riêng.

## Kết quả và bằng chứng

Nhánh được tạo từ `4325ae0e125d7e633beeb0ad74d11509a85c8fa1` bằng worktree độc lập khi #154 còn mở.
Đây là lịch sử bắt đầu nhánh, không đổi thành trạng thái hiện tại.
Checkpoint lượt sửa: #154 đã merge vào develop `afbc1c74a81d3b9643551fcde642ab9e63b0c032`; #157 merge checkpoint này tại `49f591fa4feef390e62252509352ac2d8a5f7a88`.
Sau merge, bộ kiểm thử nền đạt 821 passed, 9 skipped, 48 subtests passed.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Đọc review và trạng thái mới | [Review chín findings](https://github.com/nairyuuu/ad-weighted-graph/pull/157#issuecomment-5926075277), gh pr view/api; head được review 18e86ba | Không có review/comment mới khác; #157 mở, cùng nhánh, tài khoản Lolavine777 |
| Tái hiện CLI trước sửa | Subprocess comparator với bản sao fixture: hai scoped node, snapshot khác, đổi kind/domain, malformed records, Contains, 12 MemberOf, thiếu provenance | Mất scope và các input sai trả MATCH; Contains gây discrepancy chung; sổ 12 chỉ có 10; baseline không provenance bị gán count=13 |
| Regression đầu tiên | `tests/test_reconcile_graph_baseline.py` chạy trên mã cũ | 54 failed, 12 passed; xác nhận assertion bắt được các lỗi cần sửa |
| Comparator | [scripts/reconcile_graph_baseline.py](../../scripts/reconcile_graph_baseline.py) | Giữ scoped ID, kiểm tra mapping/collision/conflicts; điều kiện snapshot/scope; kind/domain/boundary vào verdict; input lỗi bị từ chối |
| Phạm vi quan hệ và sổ sai lệch | Full differences / refs; out_of_scope và all_observed | Contains và kind ngoài M1 được ghi riêng; JSON không cắt ở 10; stderr/exit code rõ khi input lỗi |
| Đếm bội số và bằng chứng | Fixture multiplicity: 17 stored / 13 unique = 1.3077 | Candidate có 14 exported provenance occurrences; baseline thiếu provenance giữ null/not_measurable, không suy raw evidence từ stored edges |
| Tái hiện claim coverage/provenance | Parser CLI thật trên rich và raw M1 fixture; output tại `/tmp/pr157-before/` | Rich: 6 nodes, 10 edges, 1 unknown; M1 mới: 6 nodes, 9 edges, 0 assessments; Domain output không giữ Trusts/SidFilteringEnabled |
| Kiểm thử từ raw | [test_structural_boundary_cases.py](../../tests/test_structural_boundary_cases.py) | Hai ca CLI với kỳ vọng literal: đủ 8 kind M1; StatusAccessDenied thực sinh 1 unknown, không cạnh CanRDP; assertions snapshot/time binding |
| Sửa diễn giải năm test ban đầu | Cùng file boundary tests và [báo cáo](../research/reconciliation-report.md) | Ghi đúng builder-only; FSP/Domain boundary đã được fixture gán trước; missing UserRights không được gọi là denied |
| Rà soát độc lập | Agent chỉ đọc diff và tái hiện qua CLI, theo skill requesting-code-review | Phát hiện thêm derivation/provenance sai, reason không phải string gây traceback và boundary alias 0; regression chạy đỏ cả 6 ca trước sửa |
| Sửa lỗi bổ sung từ review độc lập | Tái sử dụng validate_provenance / validate_derivation trong check_contract | Provenance khai báo cần hợp lệ và positive; lineage direct-only bị từ chối; reason/alias kiểm tra kiểu, không traceback |
| Pin provenance thật | [parser_cli_evidence.json](../../tests/fixtures/reconciliation/parser_cli_evidence.json), source revision 49f591f | MemberOf hash `1298fa6f...c4de55bd`, attribute `Members[].MemberId`; giữ nguyên MemberOf/AdminTo/CanRDP unknown từ output, không viết hash giả |
| Sửa trạng thái Legacy | [Artifact #130 tại 32a9b495](https://github.com/nairyuuu/ad-weighted-graph/blob/32a9b49573b09431ec13f6a6e823923ed366e164/reports/baselines/seamless-legacy-403-unchanged.json) | Hai clean runs đã có 3.370 nodes / 71.596 relationships; export/mapping/điều tra/nghiệm thu vẫn pending |

Các lệnh Python trong lượt này dùng `/workspaces/ad-weighted-graph/.venv/bin/python`, không dùng Python global.
Lệnh tái lập CLI và ma trận input/expected/actual/source nằm trong [báo cáo đối soát](../research/reconciliation-report.md).

### Kiểm chứng cuối lượt sửa

| Lệnh (virtual environment của checkout gốc) | Kết quả |
| --- | --- |
| `/workspaces/ad-weighted-graph/.venv/bin/python -m pytest -q` | 888 passed, 9 skipped, 48 subtests passed trong 28,00 giây |
| `.../.venv/bin/python -m ruff check .` | All checks passed |
| `.../.venv/bin/python -m ruff format --check .` | 178 files already formatted |
| `.../.venv/bin/python -m yamllint .` | PASS |
| `.../.venv/bin/python scripts/check_contract.py` | Contract và 2 synthetic fixtures validated |
| `.../.venv/bin/python scripts/check_repository.py` | 242 tracked/unignored files, PASS |
| `NEO4J_PASSWORD=ci-validation-placeholder docker compose --env-file .env.example --profile graph config --quiet` | Exit 0; chỉ validate cấu hình |
| `git diff --check`; JSON parse và kiểm tra em/en dash trên 16 file thay đổi | PASS |

Suite cuối bao gồm 76 ca comparator và 7 ca boundary, cùng các ca E2E/negative đã có của repository.
Chín skip gồm năm ca thiếu telemetry raw, hai ca thiếu SEAMLESS raw, một Windows junction và một ca thiếu dataset_b/ad_sampledata.
Không chuyển các skip thành kết quả đo đạc hoặc parity.

## Điều học được / quyết định

MATCH cần cả dữ liệu hợp lệ và phạm vi chung đã khai báo, không thể suy từ các tập hợp sau khi mất bản ghi.
Scope của ID phải giữ ở cả node lẫn endpoint, kể cả khi SID cuối giống nhau.
Stored multiplicity, occurrence provenance được export và số raw facts độc lập là các đại lượng khác nhau.
Nguyên nhân sai lệch giữ unresolved tới khi có evidence, không mặc định do importer nhân bản hoặc parser mất dữ liệu.
Các ca từ NormalizedRecord kiểm tra preservation; chỉ ca đi qua raw loader/normalizer mới chứng minh hành vi tương ứng từ raw.
Trusts/SidFilteringEnabled chưa được serialize theo contract hiện tại; không mở rộng model để hợp thức hóa claim coverage.

## Trở ngại và việc kế tiếp

Đối soát SEAMLESS vẫn PENDING / NOT_MEASURABLE vì chưa có export danh tính/cạnh và mapping được kiểm toán, không phải vì Legacy chưa từng chạy hoặc đo được.
B giữ ownership runtime/import/export/identity evidence #82/#139 và parser/engine fixes.
A bàn giao comparator, coverage theo ca và giải thích; chờ exports để điều tra full difference sets và nghiệm thu #47.
Không thay raw bất biến, trọng số/model hoặc trạng thái ADR.
Cập nhật cùng PR #157, phản hồi từng finding, yêu cầu @nairyuuu review.
Không merge PR và không đóng #47/#48.
