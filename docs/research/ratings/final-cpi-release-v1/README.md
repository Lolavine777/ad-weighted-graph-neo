# B adoption đợt 1 cho #267

Trạng thái: **B đã adopt C/P/I và bounded full-history model** theo
[quyết định maintainer ngày 2026-10-13](https://github.com/nairyuuu/ad-weighted-graph/pull/277#issuecomment-6138267056).
Release thật nằm trong `decisions.adopted.json`, reviewer `nairyuuu`, thời điểm
`2026-10-13T04:30:57Z`. File `decisions.pending.json` giữ nguyên hồ sơ đề xuất;
profile, inventory, cohort và các query pins lịch sử cũng giữ nguyên.
Implementation approval của #271/#266 không phải authority cho adoption này.

Replay mới được ghi riêng tại `reports/research/issue277-adopted-replay-v2.json`.
Đã replay đủ 8 query gốc và 6 query supplement qua 28 native CLI processes,
API và orchestration. Cohort gốc từ 0/50 lên 48/50 full C/P/I (96%); phần
full-raw riêng 24/26. Supplement supported vẫn 0/7 vì nằm ngoài adoption.
Bốn query gốc và ba query supplement truncated; chưa có coverage toàn generator.
Không thay số liệu frozen cũ hoặc đổi synthetic wiring thành actual evidence.
Báo cáo v1 giữ nguyên làm hồ sơ legacy; bản v2 thay thế nó cho acceptance evidence.
Mọi checkpoint v2 pin cohort/case (kể cả supported/selector/budget), release,
raw graph/snapshot facts, case graph, source-file contents, Python executable
và dependency contents. Aggregator bắt buộc raw manifest-verified để dựng lại
cả query/graph chưa adopt; mismatch hoặc checkpoint legacy phải replay mới.
Không bổ sung pins hồi tố vào kết quả v1 để nâng claim bằng chứng.
Query supplement, natural-password recovery và các class khác chưa được adopt.

## Những quyết định đã chốt

| Nhóm | C (T1,T2) | Conditional P | Câu hỏi được giới hạn |
| --- | --- | --- | --- |
| Directory password reset | 1 (1,2) | [3/5,19/20] | 3 attempts/15m; quyền ghi, policy và reachability là prerequisites đã được xét |
| Reset-derived Kerberos activation | 0 (1,1) | [3/4,49/50] | 3 attempts/10m; đúng account và successful reset lineage; không cộng lại công reset |
| Elevated WinRM execution | 1 (1,2) | [1/2,9/10] | 3 attempts/30m; đúng usable identity, endpoint và administrative execution context |
| Typed administrative control of pinned DC | High | Không có P riêng | Hậu quả kỹ thuật admin_control(DC), không đổi thành Critical vì nhãn DC |

Rationale: ba nhóm đầu giữ các giá trị lịch sử, nhưng mở rộng từ những câu hỏi
đã review sang các identities/full histories được compiler kê rõ. Đây là
**AI-assisted expert scenario estimates**, không là số đo thực nghiệm hoặc
statistical confidence intervals. C=0 vẫn là active event có conditional P.

Quyết định còn bao gồm giả định `stable-no-depletion-distinct-work-v1`: trong
các histories hữu hạn được pin, những thành công trước đó không thay đổi
secret/account/resource/policy hoặc tiêu hao retry budget của event hiện tại.
Giữ cùng interval ở các histories khác nhau là một lựa chọn mô hình cần chốt;
không phải kết luận các event độc lập. Nếu không chấp nhận invariance này,
chọn `needs_evidence` hoặc đề xuất profile/history split rồi chạy lại.

## Giới hạn release đợt 1

Chỉ năm query Source A đã pin trong cohort gốc: projection, full-raw-four,
full-generator và hai User footholds. Pin toàn bộ query trước search bao gồm
initial capability, runtime declarations, exact C/P/I envelopes, policy,
retry/horizon, inventory/history domain, target và caps. Không tạo candidate
lists, per-path packets, q mặc định, estimator hoặc search engine mới.

Mỗi nhóm có quyết định C và P riêng: `adopt`, `reject`, `needs_evidence`.
Impact có quyết định riêng. Recovery AS-REP/TGS tự nhiên và mọi class khác
không được release này adopt. Không nhận số mới qua sửa `values` tại chỗ:
cần revised proposal/versioned release để có review rõ ràng.

`apply_release` từ chối pending release, thiếu actual reviewer/time/reference/
confirmation, PR implementation approvals, thay đổi proposal/history/query
pins, thêm class, sửa số hoặc dùng synthetic provider policy. Review declarations
và references là hồ sơ quyết định, không tự xác thực người đứng sau reference.
Một accepted fixture trong test không phải quyết định thật của B.

## Chạy qua native API/CLI

Từ repository root, dùng file release thật và original bound query:

```sh
python -m scripts.research.final_cpi_release --release docs/research/ratings/final-cpi-release-v1/decisions.adopted.json --query bound-query.json --output released-query.json
python -m scripts.research.final_cpi_adoption_replay --group original --case source-a-projection --raw-dir data/raw/SEAMLESS
python -m scripts.research.final_cpi_adoption_replay --aggregate --raw-dir data/raw/SEAMLESS
```

Replay từng `--case` trong `cohort.json` với `--group original`, và từng case
trong `supplementary-cohort.json` với `--group supplementary`. Supplement giữ
pending vì không thuộc exact adopted query domain; compiler phải từ chối áp dụng
release ở các context đó. Aggregator công bố query thiếu, không tính chúng là
zero-path, không chứng nhận ngưỡng 80% nếu cohort chưa replay đủ.
`--timeout-seconds` mặc định 600 chỉ thay thời gian chờ process CLI, không đổi
search caps, attack/retry budget, target hoặc các query pins đã chốt.

Chuẩn bị query bằng `bind_source_a(case_id)` như #271. Với file
`decisions.adopted.json` đã có actual reference, API dùng
`scripts.research.final_cpi_release.apply_release(query, release)` rồi gọi
`run_attack_query` bình thường.

```sh
python -m scripts.research.final_cpi_release --template --output pending-release.json
python -m scripts.research.final_cpi_release --release adopted-release.json --query bound-query.json --output released-query.json
python -m src.engine.query_cli --query released-query.json --graph source-a-graph.json --label seamless --prerequisite data/samples/manifests/seamless-raw-v1.json --output result.json
```

Không đổi `decisions.pending.json` thành adopted để mô phỏng human acceptance.
Sau quyết định thật, lưu một file release mới với confirmation chính xác.
Public rating_audit giữ `estimated_expert_scenario`, actual review reference,
review_status và provider disposition; provider policy/known-FALSE checks vẫn
được thực hiện bởi native resolver.

## Verifier và bằng chứng

Verifier mới `final-cpi-public-comparison/2.0.0` so ordered canonical
`wire(PathResult)` cho API/CLI và orchestration/CLI, chỉ bỏ transport
`candidate_id`. Nodes/edges/provenance, requests/actors/bindings, before/additions,
causal lineage, final state, scenario/context đều thuộc identity. Tên kỹ thuật
trong summary chỉ dùng trình bày. Attempt traces/diagnostics không thuộc phép so.

Các reports #271 đã publish giữ nguyên bytes. Phép so program theo tên kỹ thuật
ở những reports đó không chứng minh full program identity; replay mới phải dùng
version 2 và report mới, không sửa frozen reports để nâng cấp claim cũ.

Kiểm thử mô phỏng adoption trên Source A projection giữ 24 programs được native
generator tự sinh; C/P/I đủ cho 24/24 chỉ khi dùng test-only decision declaration.
Ví dụ đầu: C=2, P=[9/40,8379/10000], I=High; Fraction/C oracle kiểm toàn bộ.
Kết quả này không đóng #267 hoặc chứng minh >=80% production coverage.

Sau adoption thật cần replay cohort gốc và raw supplement riêng, báo đầy đủ
C/P/I/full/Pareto counts, truncations và mẫu số; không gộp projection/raw repeats.
Source/batch ranking, User-goal attribution và chokepoint sensitivity vẫn là
các bước tích hợp riêng. Bước đầu này chưa hoàn tất tất cả acceptance gates #267.
