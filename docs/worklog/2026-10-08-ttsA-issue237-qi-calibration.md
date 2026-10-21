# Worklog - 2026-10-08 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#237](https://github.com/nairyuuu/ad-weighted-graph/issues/237), PR [#238](https://github.com/nairyuuu/ad-weighted-graph/pull/238), nhánh `research/237-evidence-qi-calibration` -> `develop`, reviewer `nairyuuu` / Research M3.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.
- Baseline rà soát: `develop@32ffd62ce9e65c20ccb032143bb8c8cb3dae259a` (gồm AS-REP #234).
- Phân vai sở hữu: TTS A sở hữu phương pháp luận, estimator thực nghiệm, benchmark prototype, holdout đối chứng, worklog và báo cáo nghiên cứu; không sửa engine ranking hoặc catalog/search của TTS B.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Audit dữ liệu và implementation Chặng 1 | [Báo cáo nghiên cứu](../research/evidence-qi-calibration-237.md), Mục 2 | Xác lập ma trận 5 chiều; ranh giới Layer 1 (facts), Layer 3 (assumed), và thực nghiệm đo lường; khuyến nghị pilot hẹp cho bẻ khóa ngoại tuyến |
| Estimator thực nghiệm prototype Chặng 2 | `scripts/research/empirical_qi_estimator.py` | Cài đặt khoảng tin cậy Wilson 95% (NIST PRC 2.4.1), làm tròn bảo thủ ra ngoài sang Fraction, điều kiện hóa chuỗi tiền tố nghiêm ngặt (full-history conditioning), đối sánh tham số i.i.d., chặn rò rỉ censored runs, chặn empty provenance, khử trùng lặp và từ chối contradictory duplicates không phụ thuộc thứ tự, loại bỏ lỗ hổng wildcard prefix bằng explicit manifest binding, xác thực target_complexity_class và actor_capability, chặn domain shift (case-insensitive SEAMLESS, unseen domains), và 16 quy tắc từ chối fail-closed |
| Benchmark Prototype và Holdout đối chứng Chặng 3 | `tests/fixtures/empirical_calibration/`, `reports/research/evidence-qi-calibration-237.json` | 100 mẫu prototype (60 train, 40 holdout) có `evidence_manifest` và `artifact_digest`; chặn leakage giữa train/holdout (bao gồm cả stable identity và artifact_digest); chẩn đoán tính tương thích trên 1 split đơn lẻ đạt yêu cầu (`holdout_rate_in_interval_diagnostic: true`, rate 35.00% nằm trong [32/125, 247/500]); Brier score 0.2279; Log loss 0.6484; từ chối 100% ca kiểm thử fail-closed (16/16 ca); baseline comparison ghi nhận `unavailable` do Week 3 không có baseline cho AS-REP recovery |
| Kiểm thử đơn vị và tích hợp Chặng 4 | `tests/test_empirical_qi_estimator.py` | 41 passed: toán học Wilson, bảo toàn độ bao phủ phân số, từ chối fail-closed (16 ca), kiểm tra tiền tố rỗng/sai lệch/thiếu prerequisite/unseen history, chặn mixed-case SEAMLESS, chặn wildcard lab prefix, chặn unseen domain, chặn censored runs, chặn empty provenance/trial/hash ID, từ chối contradictory duplicates độc lập thứ tự, chặn rò rỉ hash ID và artifact digest train/holdout, xác thực dữ liệu holdout, chẩn đoán tương thích holdout, tích hợp `assess_candidate_program` nhân dồn Fraction, và bảo toàn nguyên vẹn 21 tham số Week 3 (digest `sha256:20f67e...`) |
| Suite hồi quy tập trung | `.venv/bin/pytest tests/test_empirical_qi_estimator.py tests/test_asrep.py tests/test_week3_scope_and_types.py -q` | 140 passed / 14.58s |
| Kiểm tra chất lượng repo | `ruff check`, `ruff format --check`, `yamllint`, `check_repository.py`, `check_contract.py` | Toàn bộ kiểm tra đạt yêu cầu |

| Xử lý Change Request review commit `70b3dd2` | `scripts/research/empirical_qi_estimator.py`, `tests/fixtures/empirical_calibration/refusal_cases.json`, `tests/test_empirical_qi_estimator.py`, `reports/research/evidence-qi-calibration-237.json` | Giải quyết triệt để 3 findings của owner `@nairyuuu`: [P1] Bảo toàn phân loại prototype và cách ly khỏi production ranking; [P1] Thực thi nghiêm ngặt ranh giới evidence manifest (chặn union alias, chặn standalone prefix không hỗ trợ, ràng buộc actor capability); [P2] Báo cáo holdout an toàn không ném KeyError khi bị từ chối; mở rộng bộ kiểm thử lên 19 ca refusal (100% pass) và 43 unit tests |
| Xử lý Change Request review commit `b0cf006` | `scripts/research/empirical_qi_estimator.py`, `tests/test_empirical_qi_estimator.py`, `docs/research/evidence-qi-calibration-237.md` | Giải quyết dứt điểm finding [P1] về cơ chế promote evidence: manifest là nguồn chân lý bất biến không cho phép caller override; ràng buộc disposition `production_empirical_calibration` và cổng `for_production_ranking=True` vào gói bằng chứng được review (`is_reviewed_evidence_package`); cách ly unreviewed caller string vào `quarantined_unverified_evidence`; bổ sung 5 negative promotion probes; suite hồi quy tập trung đạt 141 passed |

## Điều học được / quyết định

Không thể suy diễn xác suất thành công từ đồ thị Active Directory tĩnh của SEAMLESS nếu thiếu hoàn toàn dữ liệu phân phối độ mạnh mật khẩu và telemetry mạng thực tế.
Mọi nỗ lực gán xác suất cho kịch bản SEAMLESS hiện tại mà không có đo lường đều là phán đoán chủ quan hoặc số liệu giả tạo; chính sách đúng đắn là duy trì trạng thái `unrated` fail-closed cho SEAMLESS.
Khoảng tin cậy tỷ lệ nhị thức Wilson score interval cấp 95% theo chuẩn NIST là phương pháp defensible để lượng hóa độ bất định khi có mẫu số và số lần thành công thực tế.
Làm tròn bảo thủ ra ngoài (outer conservative rationalization) sang phân số tối giản giúp bảo toàn hoàn toàn cận tin cậy và tích hợp an toàn với công thức nhân phân số của động cơ xếp hạng mà không gây sai số dấu phẩy động.
Phải xác thực đầy đủ provenance và completed outcomes (`success`/`failure`); không được ép các lượt chạy bị censored hoặc invalid thành failure.
Phải xử lý duplicate mâu thuẫn một cách nhất quán và fail-closed; không để kết quả ước lượng phụ thuộc vào thứ tự đưa dữ liệu vào.
Phải kiểm tra chống rò rỉ dữ liệu (leakage interception) giữa tập train và holdout bằng stable identity và ma băm `artifact_digest` trước khi đánh giá chất lượng dự báo.
Chẩn đoán trên một split đơn lẻ (single-split diagnostic) chỉ xác nhận tính tương thích tại thời điểm đó, không phải là bằng chứng đo lường độ bao phủ lấy mẫu lặp lại (repeated-sampling coverage) hay xác nhận hiệu chuẩn toàn diện.
Không so sánh khập khiễng khoảng tin cậy của thao tác bẻ khóa ngoại tuyến với nhận định chuyên gia của thao tác đặt lại mật khẩu trực tuyến Week 3; ghi nhận trung thực `baseline_comparison: unavailable`.
Loại bỏ hoàn toàn cơ chế kiểm tra tiền tố lỏng lẻo (wildcard prefix bypass); chỉ chấp nhận các kịch bản lab được xác minh tường minh trong evidence manifest.
Ràng buộc chặt chẽ phân lớp độ phức tạp mục tiêu (`target_complexity_class`) và năng lực tác nhân (`actor_capability`) để tránh trộn lẫn các quần thể quan sát không tương thích.
Giữ nguyên vẹn bộ tham số Week 3 và các kịch bản synthetic của Week 4; pilot thực nghiệm được đóng gói độc lập và chỉ áp dụng cho Lab Context có cùng điều kiện đo đạc.
Tuyệt đối không thăng hạng (promote) benchmark prototype fixture thành bằng chứng thực nghiệm cho production ranking; phân định rạch ròi `dataset_classification: "controlled_lab_benchmark_prototype"` và `evidence_disposition: "quarantined_prototype_not_for_production_ranking"`.
Chặn xuất bản prototype qua cổng kiểm tra `for_production_ranking=True` trong `export_bounds_table_entry` để đảm bảo prototype không bao giờ vô tình trở thành căn cứ thực nghiệm trong production ranking.
Không gộp (union) danh sách kịch bản trong evidence manifest với các alias kịch bản kiểm thử mặc định; alias kiểm thử như `lab-scenario` phải bị từ chối fail-closed.
Ràng buộc chuỗi tiền tố nghiêm ngặt theo `supported_prefix_sequences` của manifest; từ chối kịch bản bẻ khóa đứng độc lập (`initial_material_present=True`) nếu manifest không hỗ trợ chuỗi đơn lẻ không có bước thu thập tiền quyết.
Bắt buộc định danh rõ `actor_capability` khi có manifest; từ chối dứt khoát `actor_capability=None` hoặc các năng lực chưa được xác minh.
Xử lý an toàn các kết quả từ chối holdout (censored, rò rỉ, rỗng); không truy cập các trường chỉ số chưa được tính toán để tránh ngoại lệ `KeyError: 'holdout_sample_size'`, bảo toàn mã chẩn đoán và đặt các chỉ số là `None`.
Xử lý nghiêm ngặt các danh sách rỗng (`[]`) trong manifest bằng cách kiểm tra sự hiện diện của khóa; ngăn chặn việc danh sách rỗng bị coi là falsy rồi tự động rơi về các hằng số mặc định cho phép.
Làm sạch ngữ cảnh cơ sở trong bộ ca kiểm thử từ chối `refusal_cases.json`; loại bỏ các nguyên nhân lỗi trùng lặp vô tình để mỗi ca kiểm thử cô lập chính xác một chiều thất bại duy nhất.
Xuất minh bạch trường `production_ranking_bounds_table_entry: null` trong báo cáo tự động để kiểm toán trực quan việc cách ly prototype khỏi engine xếp hạng.
Khóa chặt ranh giới thăng hạng bằng chứng: manifest là nguồn chân lý bất biến cho phân loại dữ liệu, ngăn chặn hoàn toàn việc caller tự ý truyền chuỗi `dataset_classification='empirical_measurement'` qua constructor hoặc `fit()` để biến fixture prototype thành căn cứ thực nghiệm production.
Từ chối dứt khoát và fail-closed mọi trường hợp thiếu manifest (`missing_evidence_manifest`) hoặc phân loại dữ liệu mâu thuẫn giữa caller và manifest (`conflicting_dataset_classification`).
Ngăn chặn triệt để việc thăng hạng các quan sát mang nguồn gốc prototype (`lab://`) thành bằng chứng thực nghiệm (`unverified_prototype_provenance`).
Khóa/trì hoãn (defer/disable) tính năng xuất bản production ranking trong phạm vi phần mềm prototype của Issue #237 theo đúng chỉ đạo của reviewer; `export_bounds_table_entry(..., for_production_ranking=True)` luôn trả về `None`.
Làm rõ nguyên nhân lỗi CI remote tại head là do hạn mức tài khoản / thanh toán GitHub Actions của repository owner ("The job was not started because recent account payments have failed or your spending limit needs to be increased"), không phải lỗi kiểm thử mã nguồn.

## Trở ngại và việc kế tiếp

- SEAMLESS AD snapshot hiện không có hash mật khẩu hoặc nhật ký telemetry thực tế; tiếp tục giữ SEAMLESS là `unrated` cho tới khi có bộ dữ liệu đo lường đại diện được phê chuẩn.
- Bộ dữ liệu `lab_benchmark_dataset.json` là prototype fixture; các chiến dịch đo lường thực nghiệm trên môi trường lab/production có audit artifacts độc lập được ghi nhận là DEFERRED theo đúng Mục 5 của Issue #237.
- Không tự merge PR và không tuyên bố hoàn tất toàn bộ master issue #237 trước khi có sự đồng thuận từ reviewer và thỏa mãn toàn bộ tiêu chí nghiệm thu.
