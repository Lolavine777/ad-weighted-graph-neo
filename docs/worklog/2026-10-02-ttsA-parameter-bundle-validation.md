# Worklog - 2026-10-02 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [#162](https://github.com/nairyuuu/ad-weighted-graph/issues/162), [#163](https://github.com/nairyuuu/ad-weighted-graph/pull/163), [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) / PR branch `feat/143-parameter-bundle-validation` / M2 Week 3
- Thời gian thực tế ước lượng: Không đo thời lượng phiên sửa; không suy giờ làm từ số lệnh hoặc thời gian test.

## Kết quả và bằng chứng

Worklog này ghi nhận kết quả thực hiện của TTS A (@Lolavine777) tiếp nối Issue #143 trên nền nhánh `develop` mới nhất sau khi PR #163 được hợp nhất tại commit `98fb766`.
Công việc bao gồm hoàn tất các quyết định thiết kế, giao diện và phiên bản tường minh (explicit decisions) từ phía TTS A.
Công việc bao gồm đóng gói và ban hành Gói tham số kịch bản có phạm vi phiên bản 1.0.0 (Scoped Parameter Bundle 1.0.0) độc lập và tự chứa.
Công việc bao gồm nâng cấp công cụ kiểm chứng để chạy trực tiếp phân tích giải tích và quét độ nhạy lân cận trên gói tham số.
Công việc bao gồm bổ sung bộ kiểm thử tự động toàn diện và đồng bộ trạng thái quản trị xuyên suốt tài liệu dự án.
Công việc tuân thủ nghiêm ngặt các ranh giới: giữ nguyên vẹn hai bảng chấm điểm của con người ở trạng thái pending, không sửa đổi mã nguồn engine/parser của TTS B, và duy trì phán quyết khoa học Insufficient Evidence cho xếp hạng dự đoán sản phẩm.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| 1. Ban hành Scoped Parameter Bundle 1.0.0 | `tests/fixtures/ranking/seamless_parameter_bundle.json` | Đóng gói tự chứa đầy đủ metadata, quản trị, đánh giá tác động High cho DC, 9 đơn vị công việc chuẩn tắc, 11 câu hỏi tiền tố có điều kiện, 26 giả thiết runtime (tách riêng hai bản ghi network_rpc_reachable theo rationale/scope của Source A và Source B), 3 ứng viên hợp lệ và đường cơ sở giải tích. |
| 2. Nâng cấp script kiểm chứng tham số | `scripts/research/seamless_parameter_validation.py` | Bổ sung hàm `verify_parameter_bundle`, `extract_query_and_candidates_from_bundle`, đối số CLI `--bundle`, in banner chuẩn tắc và xuất báo cáo `reports/research/seamless-parameter-validation-report.json`. |
| 3. Mở rộng bộ kiểm thử tự động | `tests/test_seamless_parameter_proposal.py` | Bổ sung 5 ca kiểm thử mới cho bundle schema, query projection, calculation traces, CLI execution và human sheets safeguard; 30/30 tests pass. |
| 4. Cập nhật hồ sơ chấp thuận tường minh | `docs/research/path-ranking-acceptance-disposition.md` | Hoàn tất quyết định chấp thuận của TTS A cho Gate 1, Gate 2, Gate 3, Gate 4, Gate 6, cập nhật bản ghi merge PR #163 (Mục 5.7) và bổ sung Mục 5.8 về Scoped Parameter Bundle 1.0.0. |
| 5. Chuẩn hóa quy chuẩn Đặc tả giao diện 1.0.0 | `docs/research/path-ranking-interface-specification.md` | Thăng cấp phiên bản từ `1.0.0-draft` lên `1.0.0` quy chuẩn, chuyển trạng thái sang `Accepted by TTS A`, và bổ sung Mục 6.1 ghi nhận ranh giới chuyển dịch chuẩn tắc đã nghiệm thu. |
| 6. Đồng bộ quyết định tại ADR-0013 | `docs/adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md` | Chuyển trạng thái sang `Accepted by TTS A (Chờ phê duyệt chính thức từ TTS B)`, cập nhật bảng checklist nghiệm thu cho từng cổng. |
| 7. Đồng bộ quy chế và định hướng trọng số | `docs/research/evidence-rating-governance.md`, `docs/research/weighting-direction.md` | Cập nhật ma trận trạng thái phản ánh Scoped Parameter Bundle 1.0.0 đã phát hành và quyết định chấp thuận của TTS A; duy trì ratings pending và phán quyết Insufficient Evidence. |
| 8. Kiểm tra chất lượng và an toàn mã nguồn | `.venv/bin/pytest`, `.venv/bin/ruff`, `scripts/check_contract.py`, `scripts/check_repository.py` | 235 ranking tests pass; 1095 toàn bộ tests pass; ruff check và format clean; contract và repository checks pass 100%. |

## Chi tiết Gói tham số Scoped Parameter Bundle 1.0.0

Gói tham số tại `tests/fixtures/ranking/seamless_parameter_bundle.json` đóng vai trò là nguồn chân lý duy nhất (single source of truth) cho các tham số kịch bản SEAMLESS ở giai đoạn nghiên cứu:
- **Định danh và bối cảnh:** `bundle_id: "bundle-seamless-host-to-dc-v1"`, phiên bản `1.0.0`, kịch bản `scenario-seamless-host-to-dc` v1.1.0 gắn với snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
- **Quản trị rõ ràng:** Ghi rõ `basis_category: "research_assisted_scenario_hypotheses"`, `status: "pending_independent_human_ratings"`, `human_agreement_status: "pending"`, `raters: []`.
- **Đánh giá tác động độc lập:** Tài sản đích BADBLOOD Domain Controller mang hậu quả `High` có giải trình nghiệp vụ cụ thể bảo vệ tính bảo thủ trước nhãn `Critical`.
- **9 đơn vị công việc chuẩn tắc (WU 1-9):** Định mức theo rubric chuẩn ($T_1, T_2$), công thức `"base"` ($C = T_1 + T_2 - 2$), chi phí nỗ lực $0 \le C \le 4$, trạng thái `independent`, có trích dẫn tài liệu kỹ thuật Microsoft Open Specifications.
- **11 câu hỏi tiền tố có điều kiện ($q_1 \ldots q_{11}$):** Biểu diễn bằng chuỗi phân số chính xác (stdlib `Fraction`), phân tích rõ ràng độ bất định dư thừa sau chính sách bounded retry.
- **26 giả thiết runtime đã khai báo:** Bao gồm đầy đủ các vị từ truy cập RPC (được tách riêng cho Source A và Source B theo đúng rationale và query scope), giao thức SMB/Kerberos/WinRM, và quyền Active Directory được phân tầng thẩm quyền Layer 3.
- **3 ứng viên kịch bản hợp lệ:** Gồm 2 ứng viên Source A (`cand_seamless_01_direct_lidia`, `cand_seamless_02_alt_vajer_ollie`) và 1 ứng viên Source B (`cand_seamless_source_b_01_ollie`) với đầy đủ 7 trường `scope_binding`, vết đường cấu trúc chuẩn tắc và mảng `provenance_locators`.

## Kết quả phân tích độ nhạy lân cận và thăm dò hành vi

Script `scripts/research/seamless_parameter_validation.py` chạy trực tiếp trên gói tham số xác nhận các kết quả giải tích:
1. **Đường cơ sở giải tích (Analytical Baseline):**
   - Candidate 1: Xác suất $[42/125, 171/250] = [0.336, 0.684]$, Nỗ lực 2, Tác động High.
   - Candidate 2: Xác suất $[126/625, 55233/100000] = [0.2016, 0.55233]$, Nỗ lực 3, Tác động High.
   - Candidate B: Xác suất $[42/125, 171/250] = [0.336, 0.684]$, Nỗ lực 2, Tác động High.
   - Biên Pareto rủi ro trên Source A bảo toàn tính không so sánh được giữa Candidate 1 và Candidate 2 do khoảng xác suất giao nhau $[0.336, 0.55233]$.
   - Đường cơ sở Min-Effort-to-DA chọn Candidate 1 (nỗ lực 2 < 3).
2. **Độ nhạy ma sát tương tác ($T_2$):**
   - Tăng ma sát của các bước đặt lại mật khẩu và WinRM của Lidia ($T_2: 2 \to 3$) nâng nỗ lực Candidate 1 từ 2 lên 4.
   - Min-Effort-to-DA đảo chiều lựa chọn sang Candidate 2 ($C=3 < 4$).
   - Biên Pareto tiếp tục giữ nguyên cả hai ứng viên vì khoảng xác suất không đổi.
3. **Độ nhạy thu hẹp khoảng xác suất lồng nhau:**
   - Thu hẹp khoảng xác suất của Candidate 1 về $[459/800, 171/250] = [0.57375, 0.684]$ hoàn toàn nằm trong khoảng ban đầu.
   - Cận dưới $l_1 = 0.57375$ vượt qua cận trên $u_2 \approx 0.55233$, tạo ra sự áp đảo Pareto tuyệt đối.
   - Biên Pareto sụp đổ từ 2 ứng viên về duy nhất Candidate 1.
4. **Độ nhạy quét chuỗi tham số (Compound Upper Bound Reduction Sweep):**
   - Giảm 10% cận trên đồng thời trên cả 5 bước của Candidate 2 khiến tích lũy $u_2'$ suy giảm về $0.32615 < 0.336 = l_1$.
   - Biên Pareto đảo chiều từ không so sánh được về duy nhất Candidate 1.
5. **Thăm dò tuân thủ hành vi và bất biến:**
   - Xác nhận tie-break bằng nỗ lực khi xác suất điểm trùng nhau ($[0.5, 0.5]$).
   - Xác nhận biên Pareto bảo toàn khi chuyển tác động đích sang Critical.
   - Xác nhận cơ chế fail-closed khi thiếu đánh giá tác động.
   - Xác nhận quyền phủ quyết của dữ kiện sai bắt buộc (known-false veto).
   - Xác nhận tính không ảnh hưởng của dữ kiện sai không liên quan.
   - Xác nhận phân vùng chẩn đoán của dữ kiện thiếu bằng chứng (unknown gating).

## Cam kết quản trị và ranh giới trách nhiệm

- **Bảo lưu bảng chấm điểm của con người:** Hai tệp `tests/fixtures/ranking/seamless_rater_1.json` và `tests/fixtures/ranking/seamless_rater_2.json` được giữ nguyên vẹn 100% ở trạng thái unrated/pending với toàn bộ trường rỗng/null.
- **Không tự xưng chuyên gia:** Tuyệt đối không tự điền tên người chấm giả lập, không tự tạo điểm số con người, và không tuyên bố đạt được đồng thuận con người khi chưa có hai người thật thực hiện đánh giá độc lập.
- **Phán quyết khoa học:** Tiếp tục duy trì phán quyết `Insufficient Evidence` cho xếp hạng dự đoán sản phẩm trên snapshot SEAMLESS.
- **Ranh giới sở hữu mã nguồn:** Tuyệt đối không can thiệp hoặc sửa đổi mã nguồn engine/parser của TTS B trong `src/engine/` và `src/parser/`.
- **Quy trình nghiệm thu:** TTS A hoàn tất quyết định chấp thuận tường minh từ góc độ nghiên cứu mô hình; toàn bộ các quyết định chung của dự án đang chờ TTS B (@nairyuuu) đối soát độc lập và phê duyệt chính thức trên GitHub Pull Request; tuyệt đối không tự merge.

## Điều học được / quyết định

1. **Đóng gói tham số độc lập và tự chứa (Self-Contained Parameter Bundle):**
   - Việc gom toàn bộ các căn cứ tham số (metadata, target impact, 9 work units, 11 conditional bounds, 26 runtime assumptions, 3 candidate envelopes) vào một bundle JSON chuẩn tắc giúp loại bỏ sự phụ thuộc rải rác giữa các fixture truy vấn và script nghiên cứu.
   - Bundle đóng vai trò là single source of truth; các fixture query hiện có trở thành các phép chiếu (projections) chính xác của bundle và được kiểm chứng tự động bằng test suite.

2. **Khả năng kiểm chứng giải tích và độ nhạy độc lập với người chấm:**
   - Việc xây dựng script kiểm chứng và phân tích độ nhạy lân cận cho phép kiểm tra tính vững chắc của thuật toán và các ranh giới toán học (như sự sụp đổ biên Pareto khi thu hẹp khoảng xác suất lồng nhau, hoặc sự đảo chiều Min-Effort khi tăng ma sát tương tác) mà không cần phải chờ đợi hay giả mạo kết quả đánh giá của con người.
   - Các phép kiểm chứng này xác nhận tính đúng đắn của thiết kế ADR-0013 và giao diện 1.0.0.

3. **Phân định rõ ràng giữa Quyết định thiết kế và Hiệu chuẩn thực nghiệm:**
   - TTS A có đầy đủ thẩm quyền đưa ra quyết định chấp thuận tường minh cho thiết kế xếp hạng (ADR-0013), đặc tả giao diện (Interface 1.0.0), phân định vết đường cấu trúc (Route vs. Work Identity), và phát hành gói tham số kịch bản.
   - Ngược lại, xếp hạng dự đoán sản phẩm trên snapshot SEAMLESS bắt buộc phải duy trì Insufficient Evidence cho đến khi có sự tham gia đánh giá độc lập của con người (dữ liệu hiệu chuẩn thực nghiệm là hạng mục tùy chọn trong tương lai, không phải điều kiện chặn bắt buộc).

## Trở ngại và việc kế tiếp

1. **Trở ngại đã giải quyết:**
   - Đã tích hợp thành công nhánh `develop` mới nhất sau khi merge PR #163.
   - Đã phát hành hoàn chỉnh Scoped Parameter Bundle 1.0.0 tại `tests/fixtures/ranking/seamless_parameter_bundle.json`.
   - Đã mở rộng script `seamless_parameter_validation.py` với tùy chọn `--bundle` và báo cáo JSON tự động.
   - Đã bổ sung 5 bài kiểm thử tự động nghiêm ngặt trong `test_seamless_parameter_proposal.py` với 30/30 tests pass.
   - Đã hoàn tất các hồ sơ quyết định chấp thuận tường minh trong `path-ranking-acceptance-disposition.md`, `ADR-0013`, `path-ranking-interface-specification.md`, `evidence-rating-governance.md` và `weighting-direction.md`.
   - Đã khắc phục toàn bộ các lỗi lint và định dạng của `ruff`.

2. **Việc kế tiếp:**
   - Đẩy nhánh `feat/143-parameter-bundle-validation` lên remote và tạo Pull Request mới quy chiếu Issue #143, #158, #42, #48.
   - Yêu cầu TTS B (@nairyuuu) thực hiện review độc lập cho các quyết định chấp thuận tường minh và gói tham số 1.0.0.
   - Tiếp tục bảo lưu hai bảng chấm điểm của con người ở trạng thái unrated/pending cho đến khi có người thực hiện chấm độc lập.
   - Không tự ý đóng Issue hay tự merge Pull Request.

## Xử lý phản hồi từ đợt Review tư vấn Vòng 1 của Agent qua tài khoản TTS A trên PR #165

Agent đã cung cấp phản hồi review tư vấn kỹ thuật qua tài khoản TTS A (@Lolavine777) tại PR #165 (review #5383905137 trên commit `9e0e8f5`).
Đây là review hỗ trợ của agent qua tài khoản TTS A, không phải review hoặc approval của TTS B (@nairyuuu).
TTS A đã xử lý triệt để toàn bộ các điểm phản hồi (P1, P2 và Test Note):

1. **Hiệu chỉnh Mục 6.1 Đặc tả giao diện (P1):**
Đã loại bỏ hoàn toàn mô tả về phương thức không tồn tại `PathRankingEngine.load_query(...)`.
Đã mô tả chuẩn xác phương thức thực thi của engine chuẩn tắc `PathRankingEngine(version="1.0.0").evaluate(...)` và khâu giải mã `decode_ranking_query`.
Đã chuẩn hóa tập giá trị enum của `overlap_state` thành `{"independent", "unresolved_overlap"}` (thay vì nhãn sai `overlapping`).
Đã sửa trường định danh kỹ thuật trong danh mục hành động thành `technique_name` theo đúng schema chuẩn tắc (thay vì nhãn sai `action_type`).

2. **Làm rõ bản chất của Hiệu chuẩn thực nghiệm (P1):**
Đã đồng bộ hóa tài liệu theo định hướng của mentor: hiệu chuẩn thực nghiệm (empirical calibration) là một hạng mục bằng chứng tùy chọn hoặc tương lai, không phải cổng chặn bắt buộc đối với xếp hạng dự đoán hay sản phẩm Week 3.
Phán quyết Insufficient Evidence tiếp tục duy trì do thiếu căn cứ tham số đã được review độc lập, thiếu bộ đánh giá độc lập của con người, và thiếu kiểm chứng phạm vi kịch bản.
Đã cập nhật Gate 5 và Mục 5.5 trong `path-ranking-acceptance-disposition.md`, Gate 5 trong `ADR-0013`, Mục 1.4 trong `evidence-rating-governance.md` và Mục mentor direction trong `weighting-direction.md`.

3. **Thực thi và đối soát toàn diện cả Source A và Source B qua Canonical Engine (P1):**
Đã nâng cấp script `scripts/research/seamless_parameter_validation.py` để nạp và thực thi trực tiếp cả Source A và Source B qua `PathRankingEngine("1.0.0").evaluate(...)`.
Đã xác thực và đối soát vết tính toán giải tích, biên Pareto và đường cơ sở Min-Effort-to-DA cho cả hai nguồn.
Đã bổ sung các ca kiểm thử tiêu cực (negative tests) trong `tests/test_seamless_parameter_proposal.py` kiểm tra trôi dạt phạm vi (scope drift), sai lệch cận Source B, đầu vào không chuẩn tắc, và tính bất nhất trong khai báo quản trị.

4. **Chuẩn hóa đối số dòng lệnh CLI (P2):**
Đã thiết lập nhóm đối số loại trừ lẫn nhau (`add_mutually_exclusive_group`) cho `--bundle` và `--input`.
Đã kiểm tra sự tồn tại của tệp và báo lỗi rõ ràng qua `parser.error` khi đường dẫn tệp không tồn tại, trả về exit code 2 chuẩn tắc.

5. **Lọc phạm vi thành viên chính xác qua `applicable_queries` (P2):**
Đã gắn thẻ `applicable_queries` cho toàn bộ các dữ kiện, hành động, đơn vị công việc và cận xác suất trong `seamless_parameter_bundle.json`.
Source A lọc chính xác 12 observed facts, 24 assumed facts, 8 work units, 11 actions, và 8 bounds.
Source B lọc chính xác 6 observed facts, 13 assumed facts, 3 work units, 4 actions, và 3 bounds.
Cả hai phép chiếu truy vấn đạt 100% bình đẳng từ điển (dictionary equality) với các fixture `seamless_proposed_query_input.json` và `seamless_source_b_proposed_query_input.json`.

6. **Bảo toàn kiểm toán tham số và ngăn chặn bất nhất quản trị (P2):**
Đã bổ sung trường băm toàn vẹn `bundle_digest` (`sha256:5576b487c69731fbc7ccc3c9cd2df58253c934465b92c752ea9afee32dc3c9fe`) vào metadata của bundle và metadata của các fixture truy vấn.
Đã bổ sung đầy đủ các trường tham chiếu căn cứ (`question_id`, `outcome_action_id`, `technical_source`, `basis_category`, `rationale`, `applicable_queries`) vào toàn bộ 11 cận xác suất.
Engine bảo toàn toàn vẹn các trường kiểm toán này tại `parameter_audit` ở gốc kết quả roundtrip.
Script kiểm chứng fail-closed nếu bundle tuyên bố đạt đồng thuận hoặc hiệu chuẩn trong khi danh sách `raters` rỗng.

7. **Kiểm tra an toàn cấu trúc phiếu chấm con người thực tế (Test Note):**
Đã cập nhật bài kiểm thử `test_parameter_bundle_governance_and_human_sheets_safeguard` để đọc và xác thực chính xác cấu trúc thực tế của phiếu chấm con người (`effort_ratings`, `likelihood_ratings`, `impact_ratings`).
Xác nhận toàn bộ các trường đánh giá trong cả hai phiếu chấm thực tế tiếp tục giữ giá trị rỗng/null, bảo đảm tính trung thực khoa học tuyệt đối.

## Xử lý phản hồi từ đợt Review tư vấn Vòng 2 của Agent qua tài khoản TTS A trên PR #165

Agent đã cung cấp phản hồi review tư vấn kỹ thuật Vòng 2 qua tài khoản TTS A (@Lolavine777) tại PR #165 (review #5387084156 trên commit `823930c`).
Đây là review hỗ trợ của agent qua tài khoản TTS A, không phải approval hoặc review của @nairyuuu/TTS B và phiếu chấm con người vẫn ở trạng thái pending.
TTS A đã khắc phục triệt để toàn bộ 5 nội dung tồn đọng:

1. **Khôi phục Single Source of Truth cho truy vấn và ứng viên từ Root Records (P1):**
Đã tách bạch hàm chuẩn hóa `derive_query_and_candidates_from_bundle` và `extract_query_and_candidates_from_bundle` trong `scripts/research/seamless_parameter_validation.py`.
Mọi truy vấn và ứng viên thực thi qua engine chuẩn tắc đều được suy dẫn trực tiếp từ các bản ghi gốc chuẩn tắc (`facts_ledger`, `bound_actions`, `work_units_ledger`, `conditional_bounds_table`, `candidate_envelopes`, `bundle_metadata`).
Nếu gói chứa trường `query_projections`, hệ thống thực hiện đối soát bắt buộc về tính tương đương toàn diện (semantic dictionary equality) giữa dữ liệu chiếu sẵn và phép chiếu suy dẫn từ root trước khi cho phép sử dụng.
Đã bổ sung các bài kiểm thử hồi quy CLI và unit tests xác nhận: nếu thay đổi cận Source B ở root, thay đổi `snapshot_id` ở root, hoặc thay đổi `snapshot_id` trong ứng viên root rồi tính lại digest hợp lệ, hệ thống lập tức phát hiện mâu thuẫn và báo lỗi fail-closed thay vì báo PASS trên dữ liệu cache cũ.

2. **Thi hành Quản trị Trung thực (Truthful Governance) xuyên suốt Root, Projections và Parameter Audit (P1):**
Đã siết chặt kiểm tra quản trị trong `verify_parameter_bundle`: gói nghiên cứu đang chờ đánh giá độc lập bắt buộc phải giữ `basis_category = "research_assisted_scenario_hypotheses"`, `human_agreement_status = "pending"`, `empirical_calibration_status = "none"`, danh sách `raters = []`, và `reconciliation = null`.
Nghiêm cấm và từ chối fail-closed mọi trường hợp mâu thuẫn nội tại (như tự nhận `empirical_calibration` hoặc kết luận `Consensus` khi chưa có người chấm) cũng như bất kỳ sự sai lệch nào giữa quản trị ở root records và quản trị trong `query_projections` hay `parameter_audit`.
Đã bổ sung regression tests kiểm tra cả tính tự mâu thuẫn của root governance và sự bất nhất giữa root và projected governance.

3. **Bắt buộc Content Digest Hợp lệ cho Canonical Bundle 1.0.0 (P2):**
Đã đưa `bundle_digest` vào danh sách trường bắt buộc `required_meta` và kiểm tra định dạng chặt chẽ `sha256:<64-hex>`.
Loại bỏ cơ chế bypass kiểm tra tính toàn vẹn khi digest bị xóa hoặc mang giá trị falsy (`""`, `null`, `false`).
Tất cả các negative tests đã được cập nhật để tính toán lại digest hợp lệ sau khi biến đổi ngữ nghĩa, bảo đảm kiểm tra đúng tính đúng đắn ngữ nghĩa thay vì dựa vào việc xóa digest.
Đã cập nhật digest chuẩn tắc mới của bundle 1.0.0 (`sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246`) đồng bộ trên bundle và các fixture query input.

4. **Loại bỏ Hoàn toàn Diễn đạt Hiệu chuẩn Thực nghiệm như một Điều kiện Chặn (P2):**
Đã rà soát và hiệu chỉnh đồng bộ các câu chữ trong `evidence-rating-governance.md:223`, `weighting-direction.md:180` và worklog.
Làm rõ rằng hiệu chuẩn thực nghiệm (empirical calibration) là một hạng mục bằng chứng tùy chọn trong tương lai theo định hướng của mentor, không phải là điều kiện chặn bắt buộc đối với mô hình hay xếp hạng dự đoán kịch bản Week 3 theo #143/#158.
Phán quyết Insufficient Evidence hiện tại xuất phát từ việc phiếu chấm độc lập của con người đang chờ thực hiện.

5. **Đính chính Nguồn gốc Người Review và Trạng thái Nghiệm thu (P2):**
Đã đính chính trong worklog: các đợt review #5383905137 (Round 1) và #5387084156 (Round 2) là review tư vấn kỹ thuật của agent qua tài khoản TTS A (@Lolavine777), không phải review hoặc approval của TTS B (@nairyuuu).
Trạng thái approval và review của TTS B tiếp tục được tách biệt và duy trì ở trạng thái pending.
Hai phiếu chấm của con người (`seamless_rater_1.json`, `seamless_rater_2.json`) tiếp tục được bảo lưu nguyên vẹn ở trạng thái unrated/pending.

6. **Kết quả Xác thực Thực tế trên Mã nguồn Đã sửa (Revision 72c951a):**
Đã chạy toàn bộ test suite `pytest tests/test_seamless_parameter_proposal.py` đạt 41/41 tests pass (bao gồm 6 ca hồi quy và negative tests mới).
Đã chạy toàn bộ 1117 tests trong repo đạt 1116 passed, 1 skipped (test Windows junction).
Đã tái tạo báo cáo thẩm định chuẩn tắc tại `reports/research/seamless-parameter-validation-report.json` với `bundle_digest` mới và 26 giả thiết runtime.
Đã kiểm tra lint sạch sẽ với `ruff`.

## Xử lý phản hồi từ đợt Review tư vấn Vòng 3 của Agent qua tài khoản TTS A trên PR #165

Agent đã cung cấp phản hồi review tư vấn kỹ thuật Vòng 3 qua tài khoản TTS A (@Lolavine777) tại PR #165 (review #5387481967 trên commit `72c951a`).
Đây là review hỗ trợ của agent qua tài khoản TTS A, không phải human approval hoặc review của @nairyuuu/TTS B và các phiếu chấm con người tiếp tục giữ nguyên ở trạng thái pending.
TTS A đã khắc phục triệt để lỗi P1 về phép chiếu dữ kiện âm (`false_facts`) và hoàn tất các ghi chú tài liệu:

1. **Khôi phục Đầy đủ Phép Chiếu và Bảo toàn `false_facts` từ Root Records (P1):**
Đã sửa hàm `derive_query_and_candidates_from_bundle` trong `scripts/research/seamless_parameter_validation.py` để trích xuất và lọc đầy đủ `false_facts` từ root `facts_ledger` theo phạm vi truy vấn (`applicable_queries`), thay vì đặt `false_facts: []` cố định.
Đã bảo toàn toàn bộ thuộc tính (`predicate`, `layer`, `truth_value`, `provenance_reference`/`rationale`) và đưa các vị từ âm vào tập `predicate_layers` của truy vấn suy dẫn.
Đã bổ sung cơ chế kiểm định hợp lệ cấu trúc cho `false_facts` trong `verify_parameter_bundle` (yêu cầu dạng mảng, predicate chuỗi không rỗng, `truth_value is False`, và có `applicable_queries`).

2. **Bổ sung Bộ Kiểm thử Hồi quy API và CLI Toàn diện cho Dữ kiện Âm từ Root Bundle:**
Đã bổ sung các bài kiểm thử tự động trong `tests/test_seamless_parameter_proposal.py`:
- `test_root_bundle_required_false_fact_rejected_and_canonical_blocked`: kiểm thử required false ở root bundle; khi dữ kiện âm thuộc điều kiện tiên quyết của hành động (như `endpoint_authorized_lidia: false`), hệ thống từ chối fail-closed.
Nếu cache cũ còn tồn tại, hệ thống báo lỗi không khớp phép chiếu giữa cache và root; nếu không có cache hoặc cache đồng bộ, engine chuẩn tắc chặn path (Candidate 1 chuyển sang trạng thái `blocked` trong `diagnostics`), biên Pareto chỉ còn Candidate 2, và bộ kiểm định giải tích từ chối bundle.
CLI thực thi tương ứng trả mã lỗi khác 0 và in thông báo lỗi rõ ràng.
- `test_root_bundle_irrelevant_false_fact_preserved_and_passes`: kiểm thử irrelevant false ở root bundle; dữ kiện âm không liên quan được bảo toàn nguyên vẹn trong `false_facts` và `predicate_layers` của truy vấn suy dẫn, không chặn nhầm các ứng viên hợp lệ, và quy trình kiểm định bundle trả về PASS; CLI trả mã thoát 0.
- `test_root_bundle_source_b_scoped_false_fact_isolation`: kiểm thử false fact chỉ thuộc Source B; dữ kiện âm chỉ gán cho truy vấn Source B không gây ảnh hưởng đến Source A (Source A giữ nguyên 2 ứng viên hợp lệ), trong khi ứng viên Source B bị chặn đúng chuẩn tắc trong diagnostics.

3. **Đồng bộ Tài liệu và Ghi chú Thực tế:**
Đã đồng bộ số lượng giả thiết runtime từ 25 thành 26 trong `weighting-direction.md:166` và các mục tổng quan worklog, ghi rõ lý do tách riêng hai bản ghi `network_rpc_reachable` theo rationale và phạm vi của Source A và Source B.
Đã chuẩn hóa việc ghi nhận kết quả kiểm thử theo từng revision cụ thể: revision `823930c` (1110 passed, 1 skipped), revision `72c951a` (1116 passed, 1 skipped), và revision `0dc8d15` (1119 passed, 1 skipped).
Tiếp tục giữ các issue cha (#143, #158, #48) mở cho các cổng nghiệm thu con người độc lập, hiệu chuẩn tùy chọn, và tích hợp engine của TTS B.

## Xử lý phản hồi từ đợt Review chính thức của TTS B (@nairyuuu) trên PR #165

TTS B (@nairyuuu) đã cung cấp phản hồi review chính thức tại PR #165 (reviews #5387615808 và #5387617642 trên commit `0dc8d15`).
TTS B yêu cầu sửa lỗi hợp đồng chặn (Blocking P1) về quy tắc kiểm định khoảng xác suất và điểm lưu ý về số lượng bản ghi closed-world của bundle 1.0.0.
TTS A đã xử lý triệt để toàn bộ nội dung:

1. **Hiệu chỉnh Bất biến Khoảng Xác suất Khớp với Interface 1.0.0 và Canonical Engine (P1):**
Hàm `verify_parameter_bundle()` trong `scripts/research/seamless_parameter_validation.py` trước đây kiểm tra ràng buộc ngặt `0 < lower <= upper < 1`, vô tình từ chối các xác suất tại điểm biên (endpoint probabilities) hoàn toàn hợp lệ theo Interface 1.0.0 (như `["1/1", "1/1"]` tại Mục 2.5) và engine chuẩn tắc `0 <= lower <= upper <= 1`.
Đã hiệu chỉnh điều kiện kiểm định thành `Fraction(0) <= l_frac <= u_frac <= Fraction(1)`.
Đã bổ sung bài kiểm thử hồi quy `test_parameter_bundle_probability_bounds_contract_and_endpoints` trong `tests/test_seamless_parameter_proposal.py`: xác nhận hệ thống chấp thuận các khoảng biên (`["1/1", "1/1"]`, `["0/1", "0/1"]`, `["0/1", "1/1"]`), đồng thời từ chối fail-closed các cận âm (`< 0`), cận vượt 1 (`> 1`), và cận đảo ngược (`lower > upper`) cả qua API lẫn CLI.

2. **Thi hành Ràng buộc Số lượng Bản ghi và Tập Ứng viên Closed-World của Bundle 1.0.0 (Minor):**
Nhằm ngăn chặn các bản ghi gốc mồ côi hoặc không thuộc phạm vi kịch bản lọt qua kiểm định mà không được chạy qua engine Source A/B, `verify_parameter_bundle()` đã chuyển từ kiểm tra cận dưới sang kiểm tra số lượng chính xác cho phiên bản phát hành 1.0.0:
- Chính xác 9 đơn vị công việc (`len(ledger) == 9`).
- Chính xác 11 hàng cận có điều kiện (`len(bounds) == 11`).
- Chính xác 12 hành động chuẩn tắc (`len(actions) == 12`).
- Chính xác 3 ứng viên hợp lệ (`len(cands) == 3` và `cand_ids == expected_cands`).
Đã bổ sung bài kiểm thử hồi quy `test_parameter_bundle_closed_world_cardinality_and_extension_rejection` xác nhận việc thêm bất kỳ bản ghi thừa nào ngoài danh mục chuẩn tắc 1.0.0 đều bị từ chối fail-closed cả qua API và CLI.

3. **Kết quả Xác thực Thực tế (Revision hiện hành):**
Đã chạy toàn bộ test suite `pytest tests/test_seamless_parameter_proposal.py` đạt 46/46 tests pass.
Đã chạy toàn bộ test suite repo đạt 1121 passed, 1 skipped (test Windows junction).
Báo cáo thẩm định `reports/research/seamless-parameter-validation-report.json` chạy tái lập hoàn toàn sạch sẽ và khớp nguyên vẹn.
Lint và format sạch sẽ (`ruff check`, `ruff format --check`).
Phiếu chấm của con người tiếp tục giữ nguyên unrated/pending; không tự ý merge hay đóng issue cha (#143, #158, #48).



