# Ma trận nghiệm thu tuần 4

## Current-state amendment - 09/10/2026

Accepted integrated source là `be64798c89235f53c5c205894a7bac0f96437ce4`, đủ core/CLI/Kerberoasting/AS-REP/RBCD.
[Manifest được bàn giao](../../reports/research/week4-acceptance-manifest.json) và cases fixture đều ghi 38 rows = 36 PASS, 0 PENDING, 1 docs/API audit NOT EXECUTED, 1 private-input BLOCKED RUN, 0 unexpected FAIL.
Baseline đã được regenerate bằng existing runner trong clean verification checkout `e7c0b917c03a21e867634a96f8a2dbd98f3b66f4`, không private raw; hai runs semantic/source deterministic.
Lượt chạy cùng runner trong checkout scenario có raw ghi 36 PASS/2 NOT EXECUTED/0 BLOCKED RUN/0 unexpected FAIL, vì prerequisite observation chỉ đổi availability, chưa làm private query trong runner.
W4-TECH-RBCD đã PASS trong package dựa trên generated programs/independent oracle; dòng PENDING B và tổng 35 PASS phía dưới là snapshot 08/10 trước RBCD.

[Evidence SEAMLESS mới](../research/week4-seamless-scenario.md) tách riêng bảy ca: ASSUMED asset success, RAW unknown, missing recovery, asset known-false veto, technique OFF, initial capability change, step cap.
Cả bảy khớp freeze độc lập tại clean execution `983ce542edad80d5b38d1cce97c7ca5db3b77cb5`, source/config bytes bằng baseline tích hợp.
Input đã tải và verify đủ manifest; private-data blocked row của manifest lịch sử không mô tả availability lượt mới và không được đổi sang PASS chỉ từ probe.
Public generated program đạt final asset, hai processes semantic-equal, từng state/effect đã replay; source/data/evidence hashes ở [public artifact](../research/scenarios/week4-seamless-v1-actual.json).
Focused local suite: 139 passed; không suy thành full suite rerun hoặc human-independent reproduction.
Full manual docs/API audit và B clean-checkout cross-reproduction còn pending; các sửa status/mapping ở PR này chỉ là focused documentation audit.
Actions tại develop run 37871043065 có runner_id=0 và 0 steps ở quality/Ubuntu/Windows/Compose; billing outage, không CI PASS.
Bảng actual và counts phía dưới giữ làm lịch sử, không thay generated manifest/fixture bằng tay.

Cập nhật ngày 08/10/2026, thay cách gán PASS và metadata tham chiếu trong bản ngày 07/10/2026.
Kỳ vọng độc lập nằm trong `tests/fixtures/ranking/week4_acceptance_oracle.json`, dựa trên scenario mapping, phép liệt kê fixture nhỏ và scoring handoff của A.
Runner không tạo expected từ output engine; từng assertion có expected, actual, actual-present và passed.
Bản kê `reports/research/week4-acceptance-manifest.json` lưu hash byte nguồn/input/contracts/catalog, revision/runtime thực tế và trace.
Payload trong `tests/fixtures/ranking/week4_acceptance_cases.json` chỉ là baseline tái lập bổ sung, không thay oracle.

## Quy tắc đọc

PASS yêu cầu mọi trường normative của hàng đã chạy đều khớp.
KNOWN DEFECT nghĩa là normative sai nhưng actual khớp đầy đủ chữ ký lỗi đã khai báo; không tính là đạt.
PENDING B chỉ áp dụng khi kết quả validation/catalog khớp chữ ký unsupported đã khai báo.
Kết quả khác chữ ký ấy là FAIL, không tự động giữ pending hoặc nhận tính năng mới.
NOT EXECUTED và BLOCKED RUN không có acceptance; mọi trường chưa đo giữ null.
Runner trả exit 1 khi có FAIL bất ngờ; exit 0 vẫn có thể chứa lỗi đã biết, pending và chưa chạy.
Chữa lỗi đúng oracle chuyển hàng thành PASS; disposition được tính lại, không dùng nhãn lỗi cố định.

## Kỳ vọng và kết quả hiện tại

Các hàng dưới đây là kiểm thử tổng hợp, trừ hai hàng nhóm prerequisite/manual đã ghi rõ.
D/M/I là direct-admin, passive membership và inherited-admin; tất cả đều là chương trình trạng thái first-success trong fixture nhỏ.
M không phải hành động thêm thành viên hoặc RBCD; checkpoint Admins không chứng minh nhóm Domain Admins thật.

| Ca | Kỳ vọng độc lập | Actual tại nguồn đo | Kết luận / phạm vi |
| --- | --- | --- | --- |
| W4-M-POSITIVE | success, 3 chương trình D/M-D/M-I, goal true, checkpoint false | Khớp toàn bộ trường và thứ tự technique | PASS; checkpoint không được yêu cầu |
| W4-X-S | ValueError chứa lỗi thiếu usable identity/control | Đúng loại và thông điệp | PASS; input validation |
| W4-X-I | no_path, 0 đường, goal false | Khớp | PASS; finite supported fixture |
| W4-X-H-WRONG | blocked, 0 đường, goal false | Khớp | PASS; sai auth context |
| W4-X-H-VALID | success, 3 đường, goal true | Khớp | PASS; context phù hợp |
| W4-C-F | checkpoint true, asset false, 0 đường, final blocked | Khớp | PASS; không gộp checkpoint với asset |
| W4-C-U | checkpoint true, asset false, 0 đường, final indeterminate | Khớp | PASS; missing gate |
| W4-DA-NEG-ASSET-POS | checkpoint false, asset true, 1 đường, success | Khớp | PASS; direct route không qua checkpoint |
| W4-DA-POS | checkpoint true, asset true, 3 đường, success | Khớp | PASS; hai goal được báo riêng |
| W4-G-U | indeterminate, 0 đường, goal false | Khớp | PASS; không mặc định unknown=true |
| W4-G-A | success, 1 đường, goal true | Khớp; trace có declared assumption | PASS; assumption-backed synthetic |
| W4-G-F | blocked, 0 đường, goal false | Khớp | PASS; false gate |
| W4-G-VETO | blocked, goal false, 1 rejected assumption, known_false_veto | Khớp cả reason | PASS; false veto |
| W4-MIN-EFFORT-E | C = 5/5/2, P = [2/5,27/40]/[2/5,27/40]/[12/25,18/25], I=High; best M/I, proof true | Khớp mọi score và scope | PASS; chỉ fixture đầy đủ có binding/rating |
| W4-MIN-EFFORT-T | C=2, tie=3, đủ ba ID tốt nhất | Khớp | PASS; deterministic ties |
| W4-MIN-EFFORT-TIES | Frontier chỉ M/I với P=1/2 và cùng I | Khớp | PASS; supplied scoring control, không thay generation |
| W4-REUSE-ANTI-DOUBLE-COUNTING | C(D)=C(M/D)=5 | Khớp | PASS; passive closure thêm 0 công việc |
| W4-REUSE-CONTEXT-SEPARATION | OtherHost ledger effort=5/rated, impact=unrated | Khớp | PASS; chỉ assessment một target, chưa chứng minh multi-context dedup |
| W4-CAP-PATHS | truncated/path_limit, best_in_generated_subset, proof false | Khớp | PASS; không chứng minh minimum toàn scope |
| W4-CAP-EXP | truncated/expansion_limit, proof false | Khớp | PASS; giới hạn expansions |
| W4-CAP-STEPS | truncated/step_limit, proof false | Khớp | PASS; giới hạn steps |
| W4-SCORE-DIAGNOSTICS | 6 diagnostics, frontier rỗng, các effort/P/I thiếu basis giữ null | Khớp | PASS; không bịa score hoặc P từ assumption |
| W4-DEFECT-ADAPTER-REJECT | 3 đường, 2 adapted, 1 rejected; bound-subset, proof false; incumbent C=5 | 3/2/1, C=5; bound-subset/proof false | PASS; hồi quy bản sửa tích hợp |
| W4-DEFECT-ZERO-ACTION | 1 đường 0 bước, goal true, adapter không reject, công khai 0 công việc mới | Goal true, 0 bước, zero work=0; ranking not_applicable, P/I null, assessed/Pareto rỗng | PASS; không tạo canonical rating |
| W4-DEFECT-DOCS-SHAPE | Tài liệu public khớp API | Field API có mặt; audit toàn tài liệu chưa chạy | NOT EXECUTED; không suy lỗi tài liệu từ field presence |
| W4-TECH-KERBEROASTING | OFF không có đường; ON 1 chương trình request/recovery/activation/membership/asset, 6 trạng thái; C/P/I unrated | Khớp chuỗi, actor, milestones, goals, adapter và null ratings | PASS; chương trình tổng hợp đã sinh |
| W4-K-MATERIAL | Request thành công; thiếu recovery giữ indeterminate, chỉ ticket material | Khớp prefix 1 bước; không secret/usable V | PASS |
| W4-K-KDC-F | KDC false chặn request; không material/secret/usable V | Khớp blocked | PASS |
| W4-K-KDC-U | KDC thiếu giữ indeterminate; không material/secret/usable V | Khớp | PASS |
| W4-K-AUTH-F | Request/recovery thành công; activation denied | Prefix 2 bước, có secret, chưa usable V | PASS |
| W4-K-NO-AUTH | Foothold không tự cấp usable Kerberos identity | Request blocked, không material | PASS |
| W4-K-FACT-F | SPN false chặn request; topology bất biến | Khớp | PASS |
| W4-K-FACT-U | SPN unknown giữ indeterminate; topology bất biến | Khớp | PASS |
| W4-K-OVERLAP | OFF/ON cùng inputs/caps đều chứng kiến cùng tài sản; không tăng asset coverage | Khớp; ON truncated/step_limit_reached | PASS; existential generated scope, không exhaustive |
| W4-TECH-ASREP | Catalog và search hỗ trợ, validation không lỗi | Exact owners hỗ trợ; public query đạt asset trong fixture tổng hợp | PASS scoped synthetic; domain mapping/private acceptance pending |
| W4-TECH-RBCD | Catalog và search hỗ trợ, validation không lỗi | Catalog false, search null, unknown technique | PENDING B; chưa thử full program |
| W4-CLI-PACKAGE | CLI 0.2 sinh đúng 3 chương trình/reachable states, Ledger E C/P/I, best C=2; hai process khớp; input sai bị từ chối | Chạy stdout/output và compare harness, empty state/null ranking exit 1, không tạo artifact | PASS; chỉ phạm vi CLI tổng hợp, không nghiệm thu riêng tư |
| W4-SEAMLESS-DATASET-GATE | Trace riêng tư được cấp phép và xác minh | Không có raw prerequisite; probe chưa chạy | BLOCKED RUN; không phải policy certification |

## Lệnh, digest và provenance

Để chạy một hàng, dùng `.venv/bin/python scripts/research/week4_acceptance_runner.py --case-id <mã-ca>`.
Hai mã defect ngắn trong bảng là aliases được runner hỗ trợ.
Mỗi hàng có `command` API đã dùng và `output_digest` của toàn bộ actual, không phải một phần score/status.
Các hàng chưa chạy có command null; không ghi mã thoát hoặc output giả.
Trace query đã chạy có input đầy đủ, caps, expansions, transitions, gate decisions/origins, trạng thái trước/additions/cuối, rejected assumptions và ranking diagnostics.
Riêng K-OVERLAP lưu một goal witness mỗi scope; số đường, digest toàn bộ đường/attempts và tổng trạng thái attempts được ghi rõ, không trình bày như full trace của mọi đường.
Observed/false facts trong các ca tổng hợp có provenance fixture, không chứng minh quan sát AD thật.

`--revision` chỉ là assertion bằng đúng HEAD đang thực thi; giá trị khác bị từ chối.
`execution.source.dirty_pinned_files` và `file_sha256` phân biệt source commit với working-tree bytes.
Metadata thời gian/runtime không thuộc payload semantic so sánh; catalog version và technique IDs được lấy từ source thực.
Hai lượt chỉ được gọi deterministic khi semantic payload và source/input digest đều khớp.
Nguồn lịch sử với runtime hardcode không được dùng làm bằng chứng môi trường mới.

## Disposition còn mở

Ca adapter thực thi public query với binding inherited-admin sai target/technique, không dùng DummyPath hoặc mock engine.
Engine hiện hạ scope/proof đúng oracle; giữ chữ ký lỗi lịch sử để nhận ra lỗi tái xuất hiện.
Zero-action công khai semantic zero work = 0, nhưng canonical baseline minimum/P/I null và không đánh giá Pareto.

Kerberoasting đã có full-program acceptance tổng hợp và đối chứng K-MATERIAL/K-NO-AUTH/K-FACT/K-OVERLAP.
Hai ca ON/OFF dùng cùng inputs/caps, chỉ thay owner scope. Ca overlap chạm giới hạn bước; việc cả hai có witness tới cùng tài sản không cần liệt kê hết đường và không chứng minh global coverage/minimum.
AS-REP/RBCD, audit đầy đủ tài liệu/API, dữ liệu riêng tư và tái lập độc lập của người còn lại còn mở. CLI đã có kiểm chứng tổng hợp qua giao diện công khai.
Tổng hiện tại: 38 hàng, 35 PASS, 0 KNOWN DEFECT, 1 PENDING B, 1 NOT EXECUTED, 1 BLOCKED RUN, 0 FAIL.
Đủ report/demo và kiểm thử xanh không tự đóng nghiệm thu toàn tuần.
