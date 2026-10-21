# Quy chế quản trị định mức và bằng chứng (Evidence and Rating Governance)

- Phiên bản: 1.0.0
- Ngày: 2026-09-30 (Cập nhật quy chế đối soát tham số: 2026-10-02)
- Trạng thái: Accepted by TTS A and TTS B for PR #165 scope (Approval #5387665338, commit fdf5928; Scoped Parameter Bundle 1.0.0 phát hành có digest; bảng chấm người thật bảo lưu pending)
- Người biên soạn: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #143, Refs #158, Refs #165, Refs #162, Refs #163, Refs #42, Refs #140, Refs #141, Refs #142, Refs #150, Refs #151

## Làm rõ workflow hiện hành - 2026-10-01

Áp dụng [clarification của #143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158) và [review của B](https://github.com/nairyuuu/ad-weighted-graph/pull/159#pullrequestreview-5377136373).
Quy chế 1.0.0 đã được TTS A và TTS B chấp thuận trong phạm vi PR #165 (Approval #5387665338, commit `fdf5928`); các ngưỡng tham chiếu (policy thresholds) đóng vai trò là benchmark chuẩn tắc; việc thu thập điểm số con người và nghiệm thu tham số cuối cùng vẫn tiếp tục mở.
A/B hoặc hai người phù hợp trong nhóm có thể đánh giá độc lập theo cùng rubric, ghi danh tính, năng lực/phạm vi thực tế, thời điểm, nguồn, rationale và review trace.
Chuyên gia bên ngoài là lựa chọn hỗ trợ; không yêu cầu tuyển hội đồng, chứng chỉ hoặc chữ ký để triển khai, kiểm thử hay đối soát.
Chữ ký và tổ chức là metadata kiểm toán tùy chọn; reviewer acceptance được lưu bằng quyết định tường minh trên issue/PR, không suy từ chữ ký hoặc CI.
Tên metadata lịch sử `evaluator_panel` trong ví dụ chỉ nhóm người đánh giá; nó không đặt external-panel requirement.
Ratings và human agreement chưa thực hiện vẫn pending; không tạo danh tính, điểm hoặc đồng thuận thay người thật.

## 1. Nguyên tắc cốt lõi và phân tầng bằng chứng

Để đảm bảo tính chân thực khoa học, tính nhất quán và khả năng kiểm toán xuyên suốt quá trình phát triển dự án, quy chế này thiết lập các nguyên tắc quản trị nghiêm ngặt:

1. **Phân tầng bằng chứng rõ ràng (Evidence Stratification):**
Hệ thống phân biệt tuyệt đối giữa 3 tầng thông tin:
- **Giả thiết kịch bản và khoảng xác suất có căn cứ (Scenario Assumptions / Research-Based or Elicited Bounds):**
Là các thông tin được khai báo tường minh có giải trình khoa học; chỉ có giá trị bên trong phạm vi kịch bản được đánh giá.
- **Fixture kiểm thử tổng hợp (Synthetic Test Fixtures):**
Là các con số số học được thiết kế để kiểm thử tính đúng đắn của thuật toán và hợp đồng giao diện (ví dụ các số 0.8, 0.9, 0.648, chi phí 3, 8 trong Experiment 6).
Tuyệt đối không được đưa các con số synthetic này thành bộ tham số sản phẩm (production profile).
- **Hiệu chuẩn thực nghiệm đã được đo lường (Measured / Empirical Calibration):**
Là các thông số được đo đạc từ hệ thống thực tế, được xác thực bởi dữ liệu telemetry và nhật ký kiểm toán có provenance.
2. **Không tự động ngoại suy xác suất từ số thứ tự (No Ordinal to Probability Extrapolation):**
Tuyệt đối không tự ý chuyển đổi các mức định tính (Low, Medium, High) hoặc điểm rubric (T1, T2) thành các giá trị xác suất hoặc điểm mất mát tiền tệ nếu không có mô hình hiệu chuẩn được phê chuẩn.
3. **Chính sách fail-closed đối với dữ kiện còn thiếu (Fail-Closed Unknown Policy):**
Nếu một đơn vị công việc thiếu conditional factor theo full history hoặc thiếu đánh giá hậu quả nghiệp vụ, hệ thống bắt buộc phải giữ nguyên trạng thái `unrated`.
Tuyệt đối không tự ý điền các giá trị mặc định (ví dụ $[0, 1]$, $0.5$) hoặc dùng một điểm phạt (penalty) để biến ứng viên thiếu dữ liệu thành ứng viên đã được xếp hạng.
4. **Không bắt buộc thực nghiệm tấn công thật trên hệ thống (No Live Exploitation Requirement):**
Theo định hướng chiến lược của mentor ngày 2026-09-29, đề tài không yêu cầu thực nghiệm khai thác tấn công thực tế (live exploitation).
Các khoảng xác suất có thể là research-based scenario estimates hoặc đánh giá độc lập của A/B có căn cứ và phạm vi được review.
Đồng thời, hiệu chuẩn thực nghiệm (empirical calibration) là hạng mục bằng chứng tùy chọn hoặc trong tương lai theo định hướng của mentor, không phải cổng chặn bắt buộc của xếp hạng dự đoán hay sản phẩm Week 3.

Research/LLM có thể hỗ trợ tìm nguồn, tổng hợp prerequisites, đề xuất rubric và conditional assumptions/rationale.
Người chuẩn bị phải mở và kiểm chứng primary sources; mô tả kỹ thuật không tự chứng minh numeric probability, và model confidence không phải attack-success probability.
Mỗi estimate phải ghi `q_i = P(E_i succeeds | foothold, scenario, all previous events succeeded)`, outcome/history, basis/provenance, scope, uncertainty, sensitivity và A/B review disposition.
Prefix chỉ là lookup key cho factor này, không phải cumulative probability.
Ghi nhãn AI-assisted research/scenario assumption, không gọi là empirical calibration hoặc human rating khi chưa có bằng chứng tương ứng.
Hai prompts/models không phải hai người chấm và không chứng minh human inter-rater agreement.
Có thể triển khai, tích hợp và kiểm thử kết quả dưới assumptions được công bố khi human agreement còn pending; numerical acceptance vẫn xét reviewed basis, validation/sensitivity và coverage theo scope.

## 2. Hồ sơ định mức chuẩn tắc (Rating Records)

Mọi đánh giá về Tác động nghiệp vụ, Xác suất có điều kiện và Nỗ lực trên sổ cái công việc phải được ghi nhận dưới dạng hồ sơ có thể kiểm toán (Auditable Rating Records).

### 2.1. Hồ sơ định mức tác động nghiệp vụ (Impact Rating Record)

```yaml
# [TEMPLATE / SYNTHETIC]
schema_version: "1.0.0"
record_type: "impact_rating"
target_asset_id: "S-1-5-21-3623811015-3361044348-30300820-1000"
target_asset_label: "DC01$"
success_event: "domain_controller_full_compromise"
consequence_rating: "Critical"  # Low, Medium, High, Critical
business_rationale: >
  Chiếm quyền hoàn toàn Domain Controller cho phép giả mạo vé xác thực Kerberos (Golden Ticket),
  làm tê liệt toàn bộ hạ tầng định danh doanh nghiệp và vi phạm bảo mật dữ liệu khách hàng.
affected_business_services:
  - "Core Identity & SSO Service"
  - "Customer Portal Banking Operations"
technical_tier_metadata:
  - "Tier0"
  - "DomainController"
business_value_metadata:
  - "CrownJewel"
  - "MissionCritical"
evaluator_panel:
  primary_rater: "synthetic_rater_a"
  secondary_rater: "synthetic_rater_b"
  reconciliation_date: "2026-09-30"
  reconciliation_verdict: "Consensus"
```

**Quy tắc quản trị:**
Mức độ hậu quả (`consequence_rating`) phải được giải trình bởi thiệt hại nghiệp vụ thực tế, tách biệt hoàn toàn khỏi nhãn kỹ thuật `Tier0` và nhãn giá trị `CrownJewel`.

### 2.2. Hồ sơ định mức xác suất tiền tố có điều kiện (Conditional Likelihood Record)

```yaml
# [TEMPLATE / SYNTHETIC]
schema_version: "1.0.0"
record_type: "conditional_likelihood"
scenario_id: "scenario-corp-compromised-host"
ordered_work_prefix:
  - "pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1001:S-1-5-21-3623811015-3361044348-30300820-1000:int_net:corp_boundary:v1"
  - "token_impersonate:S-1-5-21-3623811015-3361044348-30300820-1001:S-1-5-21-3623811015-3361044348-30300820-1000:int_net:corp_boundary:v1"
conditional_bounds:
  lower: "6/10"
  upper: "7/10"
basis_category: "scenario_assumption"  # expert_elicitation remains an optional supported basis
uncertainty_rationale: >
  Sau khi password đã được reset thành công, việc trích xuất token phụ thuộc vào việc
  tài khoản đích có đang active session trên máy chủ hay không và chính sách bảo vệ LSASS.
  Khoảng [0.6, 0.7] phản ánh độ bất định trong điều kiện mạng nội bộ không có EDR ngăn chặn triệt để.
target_population: "Internal Active Directory Enterprise Topology (SEAMLESS profile)"
operational_horizon: "72h"
evaluator_panel:
  panel_id: "synthetic_rating_pair_w3"
  raters: ["synthetic_rater_a", "synthetic_rater_b"]
  inter_rater_agreement: "0.85"  # Đo bằng mức giao nhau của khoảng IoU
  status: "reconciled"
```

**Quy tắc quản trị:**
Khoảng xác suất là factor của outcome cuối với điều kiện toàn bộ previous events thành công trong đúng foothold/scenario; full-prefix chứa current work ID là lookup key.
Không nhập cumulative prefix probabilities hoặc áp dụng chung một xác suất biên cố định cho mọi bước nhảy đơn lẻ.

### 2.3. Hồ sơ định mức nỗ lực trên sổ cái công việc (Effort Rating Record)

```yaml
# [TEMPLATE / SYNTHETIC]
schema_version: "1.0.0"
record_type: "work_unit_effort"
work_unit_id: "pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1001:S-1-5-21-3623811015-3361044348-30300820-1000:int_net:corp_boundary:v1"
technique_name: "genericall_reset_password"
actor_scope: "S-1-5-21-3623811015-3361044348-30300820-1001"
target_scope: "S-1-5-21-3623811015-3361044348-30300820-1000"
rubric_evaluation:
  t1_complexity: 1  # Mức 1: Script/tooling có sẵn, mức độ tự động hóa cao
  t2_friction: 2    # Mức 2: Yêu cầu kết nối LDAP write ổn định và phiên xác thực
  formula: "base"   # T1 + T2 - 2 (Research rubric convention, not validated labor time)
  computed_cost: 1
overlap_analysis:
  prerequisite_dependencies: []
  shared_preparation_tags: ["ldap_connection"]
  is_independent: true
evaluator: "evaluator_ttsA"
review_status: "verified"
```

## 3. Quy trình đánh giá độc lập và đối soát (Independent Rating & Reconciliation Protocol)

Để công bố actual human agreement và kiểm tra double-counting, đánh giá độc lập và đối soát theo bốn bước sau.
Workflow nội bộ này có thể do A/B thực hiện; human agreement pending không chặn preparation/conformance dưới declared assumptions.

```text
Bước 1: Chuẩn bị tài liệu đánh giá và bảng rubric chuẩn
                   │
                   ▼
Bước 2: A/B hoặc hai người phù hợp đánh giá độc lập (Blind Scoring)
                   │
                   ▼
Bước 3: Đo disagreement/agreement trên raw ratings (Agreement Metric)
                   │
                   ▼
Bước 4: Đối soát có review trace, giữ cả raw và final records (Reconciliation)
```

### Bước 1: Chuẩn bị tài liệu đánh giá
TTS A chuẩn bị danh mục các đơn vị công việc, các tiền tố chương trình tấn công và danh sách tài sản đích kèm theo mô tả kỹ thuật chi tiết từ snapshot và scenario contract.

### Bước 2: Đánh giá độc lập (Blind Scoring)
A/B hoặc hai người phù hợp thực hiện chấm điểm độc lập và ghi đúng năng lực/phạm vi của mình:
- Không chia sẻ điểm số hoặc giải trình cho nhau trong quá trình chấm.
- Với Tác động: chọn mức Low, Medium, High, Critical kèm giải trình thiệt hại.
- Với Xác suất: đưa ra cận dưới và cận trên $[l, u]$ kèm căn cứ bất định.
- Với Nỗ lực: chấm điểm $T_1 \in \{1, 2, 3\}$ và $T_2 \in \{1, 2, 3\}$ theo bản rubric nghiên cứu tại #141/#147/#151:
  - $T_1$: 1 (công cụ tiêu chuẩn/có sẵn), 2 (công cụ chuyên dụng), 3 (tùy biến nâng cao/khai thác giao thức).
  - $T_2$: 1 (ma sát thấp), 2 (ma sát trung bình), 3 (ma sát cao/tương tác người dùng).
  - Công thức cơ sở: $C = T_1 + T_2 - 2$ ($0 \le C \le 4$).

### Bước 3: Đo lường độ đồng thuận (Inter-Rater Agreement Measurement)
- **Với Tác động (biến định tính):** Tính hệ số Cohen's Kappa ($\kappa$).
  - $\kappa \ge 0.70$ là proposed reference khi defined, không phải proof correctness/calibration hoặc automatic acceptance gate.
  - *Xử lý tập đánh giá rỗng ($N = 0$):* Trả về trạng thái `empty_ratings` và $\kappa = \text{None}$ để tránh lỗi chia cho 0.
  - *Xử lý biến suy biến về toán học ($1 - P_e = 0$):* Khi hai người chấm cùng một danh mục duy nhất (zero variance, ví dụ tập mẫu đều chỉ có Critical), kỳ vọng ngẫu nhiên $P_e = 1.0$ khiến mẫu số bằng 0 ($0/0$).
  Khi đó, $\kappa$ không xác định về mặt toán học; hệ thống ghi nhận $\kappa = \text{None}$, trạng thái `degenerate_zero_variance`, và bắt buộc lưu giữ tỷ lệ đồng thuận quan sát được (Observed Agreement $P_o$) cùng ma trận nhầm lẫn thô (raw confusion matrix).
  - *Xử lý cỡ mẫu nhỏ ($N < 5$):* Khi $N < 5$, nếu $P_e < 1.0$ thì $\kappa$ vẫn xác định được về mặt toán học nhưng độ mạnh thống kê không đủ để suy diễn chắc chắn.
  Hệ thống ghi nhận giá trị $\kappa$ kèm cờ cảnh báo cỡ mẫu nhỏ (`small_sample_size_warning`), đồng thời bắt buộc công bố $P_o$ và dữ liệu chấm thô để đối soát trực tiếp.
- **Với Xác suất (biến khoảng):** Tính tỷ lệ giao nhau trên hợp (Intersection over Union - IoU) của hai khoảng $[l_1, u_1]$ và $[l_2, u_2]$:
  $$L_{\cap} = \max(0, \min(u_1, u_2) - \max(l_1, l_2))$$
  $$L_{\cup} = \max(u_1, u_2) - \min(l_1, l_2)$$
  - *Trường hợp điểm giống nhau (Identical Point Bounds):* Nếu $l_1 = u_1 = l_2 = u_2$ ($L_{\cup} = 0$), quy định $\text{IoU} = 1.0$ (đồng thuận hoàn toàn về xác suất điểm; tránh lỗi chia cho 0 `ZeroDivisionError`).
  - *Trường hợp điểm khác nhau (Distinct Point Bounds):* Nếu $l_1 = u_1$ và $l_2 = u_2$ nhưng $l_1 \ne l_2$, quy định $\text{IoU} = 0.0$.
  - *Trường hợp tổng quát ($L_{\cup} > 0$):* $\text{IoU} = L_{\cap} / L_{\cup}$.
  - Nếu $\text{IoU} \ge 0.50$, khoảng bất định được coi là có sự đồng thuận căn bản.
  - *Cảnh báo bất định nhận thức quá lớn (High Epistemic Uncertainty):* Một chỉ số $\text{IoU} \ge 0.50$ giữa hai khoảng rất rộng (ví dụ $[0.0, 1.0]$ và $[0.1, 0.9]$) không chứng minh hiệu chuẩn tốt mà phản ánh độ bất định quá lớn.
  Quy chế quy định: Nếu độ rộng khoảng $u - l > 0.50$, hồ sơ phải được đánh dấu `high_epistemic_uncertainty` (cảnh báo độ bất định nhận thức cao).
  Khi đó, A/B review basis và claim limitations, bổ sung research/tinh chỉnh scenario hoặc giữ unrated khi basis thiếu; có thể nhờ người ngoài hỗ trợ nhưng không đặt dependency tuyển chuyên gia hay telemetry mặc định.
- **Với Nỗ lực:** Tính độ lệch tuyệt đối $|C_1 - C_2|$.
  Nếu chênh lệch $\le 1$ điểm, mức độ đồng thuận đạt yêu cầu.
- **Bản chất các ngưỡng đồng thuận:**
  Các ngưỡng $0.70$, $0.50$ và $\pm 1$ là các ngưỡng chính sách đề xuất (proposed policy thresholds) đóng vai trò tham chiếu kỹ thuật ban đầu, KHÔNG phải là hằng số vật lý bất biến.
  Mọi đánh giá phải lưu giữ đầy đủ các số đo mô tả và dữ liệu chấm thô.
  Một target hoặc zero variance không bắt buộc có Kappa defined; đối soát raw ratings, observed agreement/confusion, cỡ mẫu và rationale với explicit A/B disposition.

### Bước 4: Đối soát trong nhóm (Reconciliation)
- A/B xem xét các điểm bất đồng bằng issue/PR hoặc cuộc trao đổi có bản ghi; không bắt buộc họp trực tiếp.
- Nếu bất đồng về xác suất do đánh giá khác nhau về biện pháp kiểm soát, mở rộng khoảng bất định để bao gồm cả hai góc nhìn:
  $$l_{\text{final}} = \min(l_1, l_2), \quad u_{\text{final}} = \max(u_1, u_2)$$
- Lưu giữ cả điểm chấm gốc và giải trình của từng người bên cạnh khoảng thống nhất cuối cùng.
- Lưu reviewer identity, thời điểm và decision link; chữ ký tùy chọn, consensus không xóa raw disagreement và không chứng minh calibration.

<a id="sec-independent-rating-instructions"></a>
### 3.5. Hướng dẫn chấm điểm độc lập và quy trình đối soát (Independent-Rating Instructions & Reconciliation Process)

Quy trình này áp dụng khi mục tiêu là đánh giá độc lập giữa người chấm. Kịch bản Week 3 hiện tại dùng [cơ sở tiếp nhận riêng](week3-rating-requirement-disposition.md); không coi việc thực hiện lại quy trình này là dependency cho actual release đã kiểm chứng.

Mục này hướng dẫn quy trình thực tế cho hai người chấm độc lập (Rater 1 và Rater 2, có thể là TTS A và TTS B hoặc hai thành viên phù hợp trong nhóm) khi thực hiện đánh giá.
Mục này ghi nhận trung thực hiện trạng các công cụ (helpers) hiện có trong codebase, làm rõ các API thực tế và chỉ ra các khoảng trống công cụ cần thao tác thủ công.

#### 1. Nguyên tắc chấm điểm độc lập
- Hai người chấm làm việc độc lập tuyệt đối.
- Không người chấm nào được xem điểm số thô, câu trả lời đề xuất hoặc lý giải của người còn lại trước khi nộp phiếu hoàn tất.
- Rater 1 điền vào tệp `tests/fixtures/ranking/seamless_rater_1.json`.
- Rater 2 điền vào tệp `tests/fixtures/ranking/seamless_rater_2.json`.
- Bắt buộc ghi nhận trung thực thông tin định danh ở cấp phiếu (`rater`) và ở từng bản ghi (`evaluator`).
- Các trường định danh bao gồm: `evaluator` (chuỗi định danh thực tế, cấm chứa chữ "PENDING" khi nộp), `name`, `organization` (tùy chọn), `competence_and_scope` (năng lực và phạm vi thực tế), `independence_declaration` (cam kết chấm độc lập), `rated_at` (thời điểm chấm thực tế ISO-8601).
- Tuyệt đối không tự bịa đặt danh tính, chữ ký, timestamp hoặc điểm số giả mạo.
- Khi chưa có người chấm thật, cả hai phiếu tiếp tục bảo lưu nguyên vẹn ở trạng thái `pending_independent_rating` với toàn bộ trường rỗng hoặc null.

#### 2. Các bản ghi và trường dữ liệu cần chấm theo schema phiếu
Phiếu chấm gồm 3 nhóm bản ghi tương ứng với 21 hạng mục đánh giá:
1. **Đánh giá tác động đích (1 bản ghi `record_type: "impact_rating"`):**
   - Đánh giá cho cặp `target_asset_id` (DC BADBLOOD `...-1000`) và `success_event` (`terminal_compromise_seamless_dc`).
   - Điền định danh người chấm tại trường `evaluator`.
   - Chọn mức `consequence_rating` trong tập hợp bốn mức chuẩn tắc: `Low`, `Medium`, `High`, `Critical`.
   - Cung cấp `business_rationale` giải trình tổn thất nghiệp vụ thực tế độc lập với nhãn cấu trúc Tier 0 hoặc CrownJewel.
   - Liệt kê các dịch vụ nghiệp vụ bị ảnh hưởng vào mảng `affected_business_services`.
   - Đặt `rating_status` là `"rated"`. Nếu thiếu căn cứ nghiệp vụ, giữ `consequence_rating: null` và đặt `rating_status: "unrated"`.
2. **Khoảng xác suất có điều kiện (11 bản ghi `record_type: "conditional_likelihood"` cho $q_1 \ldots q_{11}$):**
   - Làm rõ định nghĩa: Mỗi câu hỏi $q_i$ đánh giá xác suất thành công có điều kiện của **riêng bước công việc $E_i$**, với điều kiện xuất phát từ foothold, bối cảnh kịch bản, và tất cả các sự kiện trước đó trong chuỗi tiền tố đều đã thành công:
     $$q_i = P(E_i \text{ succeeds} \mid F, S, \text{all previous events succeeded})$$
   - $q_i$ là xác suất của từng bước riêng rẽ, không phải là xác suất tích lũy của toàn bộ đường đi (ví dụ $[42/125, 171/250]$ là tích lũy nhiều bước của Candidate 1, trong khi $q_i$ là từng bước như $[7/10, 9/10]$ hoặc $[4/5, 19/20]$).
   - Điền định danh người chấm tại trường `evaluator`.
   - Đánh giá khoảng xác suất $[l_i, u_i]$ thỏa mãn $0 \le l_i \le u_i \le 1$, biểu diễn bằng chuỗi phân số hữu tỷ chính xác tại `conditional_bounds.lower` và `conditional_bounds.upper`.
   - Cung cấp `uncertainty_rationale` giải trình độ bất định nhận thức dư thừa sau khi đã tính đến chính sách thử lại có giới hạn (bounded retry).
   - Ghi rõ `basis_category` và các tài liệu kỹ thuật quy chiếu tại `source_references`.
   - Đặt `rating_status` là `"rated"`. Nếu thiếu căn cứ, giữ `lower: null`, `upper: null` và đặt `rating_status: "unrated"`.
3. **Định mức nỗ lực cho 9 đơn vị công việc chuẩn tắc (9 bản ghi `record_type: "work_unit_effort"`):**
   - Điền định danh người chấm tại trường `evaluator`.
   - Đánh giá rubric trong `rubric_evaluation`: `t1_complexity` $\in \{1, 2, 3\}$ (độ phức tạp kỹ thuật) và `t2_friction` $\in \{1, 2, 3\}$ (độ ma sát tương tác), áp dụng công thức `"base"` để tính `computed_cost` $= T_1 + T_2 - 2 \in \{0, 1, 2, 3, 4\}$.
   - Đánh giá phân tích chồng lấn trong `overlap_analysis`:
     - Bắt buộc đánh giá thực tế tính độc lập về nỗ lực (non-duplication of effort) và các phụ thuộc tiên quyết; tuyệt đối không tự động mặc định công việc là độc lập.
     - `is_independent`: điền `true` nếu chi phí nỗ lực của công việc là độc lập (không bị tính trùng nỗ lực chuẩn bị với các bước khác). Điền `false` nếu có phần công sức chuẩn bị bị trùng lặp chưa được khấu trừ.
     - Lưu ý bản chất: Tính độc lập ở đây là độc lập về chi phí nỗ lực được tính, không phải độc lập về mặt xác suất hay không có bước đi trước trong chuỗi tấn công.
     - `prerequisite_dependencies`: liệt kê danh sách định danh đơn vị công việc tiên quyết bắt buộc phải hoàn thành trước theo chuỗi tấn công (ví dụ `acquire_ticket` phụ thuộc vào `reset_password`). Việc có bước tiên quyết không đồng nghĩa với việc bị trùng nỗ lực; không suy ra unresolved overlap chỉ từ việc tồn tại prerequisite.
     - `shared_preparation_tags`: liệt kê các thẻ chuẩn bị dùng chung (ví dụ quyền truy cập foothold, phiên làm việc) đã được phân bổ hoặc cần khấu trừ.
     - **Ví dụ minh họa:** Bước 1 `reset_password` ($C=1$) và Bước 2 `acquire_ticket` ($C=0$) có quan hệ thứ tự tiên quyết (`prerequisite_dependencies` của Bước 2 chứa Bước 1). Tuy nhiên, chi phí nỗ lực của hai bước là riêng biệt vì Bước 1 là tương tác RPC đặt lại mật khẩu, còn Bước 2 là tương tác Kerberos độc lập. Do đó Bước 2 có `is_independent: true`, nỗ lực hai bước được cộng dồn mà không bị đếm trùng công sức.
   - Cung cấp `effort_rationale` giải trình cơ sở đánh giá độ phức tạp, ma sát và sự chồng lấn.
   - Đặt `rating_status` là `"rated"`. Chỉ đặt `"unrated"` và giữ điểm `null` khi phần công sức chuẩn bị bị trùng lặp thực sự chưa được giải quyết hoặc thiếu căn cứ kỹ thuật.

#### 3. Hiện trạng công cụ đối soát, API thực tế và các khoảng trống (Helpers Audit & Gaps)

1. **API đối soát từng bản ghi (`reconcile_expert_ratings`):**
   - Hàm đối soát thực tế trong `scripts/research/path_ranking_wire_adapter.py` là:
     ```python
     def reconcile_expert_ratings(
         r1: dict[str, Any],
         r2: dict[str, Any],
         work_unit_registry: dict[str, dict[str, Any]] | None = None,
     ) -> dict[str, Any]: ...
```
   - Hàm nhận **hai bản ghi đơn lẻ có cùng `record_type`**, không nhận toàn bộ tệp JSON phiếu chấm.
   - Trước khi gọi helper, người đối soát phải kiểm tra tính đồng nhất của bối cảnh cấp phiếu (`query_id`, `snapshot_id`, `foothold_node_id`, `scenario_version`, `target_goal`).
   - Hàm ghép cặp và đối soát theo từng định danh cấu trúc:
     - Với `impact_rating`: kiểm tra trùng `target_asset_id` và `success_event`; trả về `proposed_consensus` nếu $c_1 == c_2$, hoặc `requires_reconciliation_panel` nếu bất đồng.
     - Với `conditional_likelihood`: kiểm tra trùng `scenario_id` và `ordered_work_prefix`; gọi `compute_interval_iou(b1, b2)`; nếu $\text{IoU} \ge 0.50$ thì trả về `proposed_consensus` với khoảng hòa giải $[\min(l_1, l_2), \max(u_1, u_2)]$; gọi `check_epistemic_uncertainty` để cảnh báo nếu độ rộng $> 0.50$.
     - Với `work_unit_effort`: kiểm tra tính hợp lệ của `work_unit_id` qua registry; tính chi phí nỗ lực theo rubric; kiểm tra chênh lệch $\Delta = |C_1 - C_2| \le 1$; nếu $\le 1$ thì đề xuất đồng thuận với chi phí bảo thủ $\max(C_1, C_2)$.
2. **Chỉ số Cohen's Kappa là hàm riêng biệt:**
   - Hàm `compute_kappa_with_fallback(ratings1: list[str], ratings2: list[str])` là lời gọi hàm độc lập trên danh sách nhãn tác động thô; nó không được tính tự động bên trong `reconcile_expert_ratings`.
3. **Ý nghĩa của phán quyết đề xuất (`proposal_verdict`):**
   - Kết quả `proposed_consensus` hoặc `requires_reconciliation_panel` là số đo mô tả và khuyến nghị kỹ thuật phục vụ đối soát giữa người với người.
   - Các đề xuất này không phải là quyết định nghiệm thu tự động và không đặt ra yêu cầu tuyển hội đồng chuyên gia bên ngoài.
   - Sau khi có kết quả đối soát thô, hai người chấm hoặc người quyết định thẩm quyền xem xét trực tiếp các điểm bất đồng để thống nhất phán quyết cuối cùng.
4. **Khoảng trống công cụ từ phiếu đã chấm đến gói tham số hoàn chỉnh:**
   - Checkpoint tooling 2026-10-02: [PR #170](https://github.com/nairyuuu/ad-weighted-graph/pull/170) đã merge CLI đối soát toàn bộ phiếu `reconcile_rating_sheets.py`; report 1.1.0 giữ raw records/full bindings/digests và `human_acceptance: pending`.
   - Script `scripts/research/seamless_parameter_validation.py` và hàm `verify_parameter_bundle` hiện được thiết kế chủ đích để xác thực gói giả thiết kịch bản có hỗ trợ nghiên cứu (research-assisted scenario hypotheses bundle) với điều kiện `raters=[]` và baseline giải tích cố định.
   - [Tooling #171](reviewed-parameter-release-guide.md) bổ sung exporter/validator riêng, yêu cầu explicit decisions cho từng record và replay source reconciliation trước khi map selected parameters vào canonical engine.
   - Implementation/synthetic verification không tự nghiệm thu số liệu: actual independent ratings/dispositions và final parameter acceptance vẫn pending; workflow thủ công có đủ bằng chứng vẫn hợp lệ.
5. **Giao diện thực thi của Canonical Engine:**
   - Để đánh giá truy vấn qua Canonical Engine bằng mã Python:
     ```python
     import json
     from src.engine.ranking import PathRankingEngine

     with open("tests/fixtures/ranking/seamless_proposed_query_input.json") as f:
         payload = json.load(f)

     engine = PathRankingEngine(version="1.0.0")
     result = engine.evaluate(
         query_payload=payload["query"],
         candidates=payload["candidates"],
     )
     pareto_frontier = result["roundtrip_result"]["pareto_frontier"]
```
   - Lệnh CLI tương đương thực thi trực tiếp từ terminal:
     ```bash
     .venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_proposed_query_input.json --output /tmp/result.json
```

## 4. Bảng quản trị dữ kiện còn thiếu và điều kiện nghiệm thu (Missing Evidence Governance Table)

Bảng sau tổng hợp toàn bộ các hạng mục dữ kiện còn thiếu, người phụ trách, phương pháp thu thập/định mức và điều kiện nghiệm thu để gỡ từng cổng đánh giá:

| Hạng mục dữ kiện còn thiếu | Người phụ trách | Phương pháp bổ sung / Thu thập | Điều kiện nghiệm thu (Gate Acceptance Criteria) |
| --- | --- | --- | --- |
| Conditional factors theo full history cho SEAMLESS | A chuẩn bị, A/B review | A/B chấm độc lập hoặc lập research-assisted scenario estimates theo [SEAMLESS packet](seamless-scenario-rating-packet.md); giữ nhãn basis và human-agreement coverage đúng thực tế. | Đúng outcome/F/S/history, rationale/scope/uncertainty/sensitivity và explicit A/B basis decision; nếu có raw independent intervals thì báo IoU reference 0.50 và widths, không dùng marginal fallback hoặc panel/signature gate. |
| Đánh giá hậu quả nghiệp vụ cho tài sản SEAMLESS | A chuẩn bị, A/B review | Giải trình Low/Medium/High/Critical độc lập với Tier0/CrownJewel; A/B có thể là raters nội bộ. | Raw records/provenance và business rationale được review; Kappa/observed agreement/confusion và fallback nếu có human ratings; thiếu basis giữ unrated. |
| Định mức nỗ lực và chống đếm trùng | A chuẩn bị, A/B review | Hai người phù hợp đánh giá rubric/overlap độc lập; hoặc test research assumptions khi human agreement pending. | Rubric consistent, cost delta reference <=1 khi có hai ratings, overlap disposition/raw rationale và explicit review; không suy rated từ việc có hai outputs LLM. |
| Bằng chứng phân quyền sao chép cho Gate O (Mục tiêu S3) | TTS A & Nguồn dữ liệu | Thu thập bằng chứng phân quyền trên Domain Naming Context (DS-Replication-Get-Changes và DS-Replication-Get-Changes-All) từ snapshot. | Có ít nhất một bản ghi positive provenance trong snapshot chứng minh quyền DCSync thực tế; không dùng giả thiết runtime. |
| Bằng chứng tồn tại và tính tươi của phiên đăng nhập (Session Freshness) | TTS B (Parser / Collector) | Mở rộng bộ thu thập telemetry hoặc bộ đọc dữ liệu để ghi nhận trạng thái session thực tế trên `Computer.Sessions[]`. | Bản ghi session có đầy đủ timestamp, trạng thái phiên đang hoạt động, và không rỗng (`measured-empty != false`). |
| Kiểm chứng cấu trúc synthetic và đối soát SEAMLESS vs Legacy 4.0.3 (#47) | TTS A & TTS B | Thực hiện kiểm thử cấu trúc end-to-end cho luồng trọng số synthetic (#47) và đối soát cấu trúc giữa SEAMLESS và BloodHound Legacy 4.0.3. | Toàn bộ kiểm thử cấu trúc synthetic pass; báo cáo đối soát cấu trúc SEAMLESS vs Legacy 4.0.3 được phê duyệt. |
| Demo kịch bản Milestone 2 (#48) | TTS A & TTS B | Chuẩn bị kịch bản demo synthetic và kịch bản SEAMLESS kèm báo cáo sai lệch đối soát (#47, #82, #139) để bàn giao M2. | Kịch bản demo chạy thành công trên cả synthetic và SEAMLESS; báo cáo sai lệch được nghiệm thu. |
| Thiết lập baseline cấu trúc trên cùng snapshot (#82) | TTS B & TTS A | Xây dựng baseline cấu trúc đối chứng trên cùng snapshot phục vụ nghiệm thu M2 và mở đường cho đối chứng BloodHound CE mở rộng ở M4. | Baseline cấu trúc cùng snapshot sẵn sàng và được kiểm chứng. |
| Bounded integration #145/#155 | B implementation, A/B acceptance | Final search-to-candidate-to-evaluator adapter trong scope Week 3 theo #158; scalable search/CE export mở rộng thuộc lượt sau. | Final integrated revision với positive/false/unknown conformance, structural trace và declared coverage; không đặt enterprise benchmark/CE parity thành gate của PR #159. |

## 5. Kết luận và ranh giới nghiệm thu

Quy chế quản trị này thiết lập hàng rào bảo vệ nghiêm ngặt chống lại việc đưa các con số tùy ý vào hệ thống sản phẩm.
Design acceptance, reviewed parameters, bounded integration và product E2E có gates riêng theo [status matrix](path-ranking-acceptance-disposition.md).
[Actual release Week 3](ratings/week3-closeout/README.md) đã có lựa chọn tham số, replay/oracle/engine và sensitivity trên ba ứng viên. Cơ sở human-reviewed AI-assisted được tiếp nhận theo [disposition](week3-rating-requirement-disposition.md); không yêu cầu thêm chấm độc lập cho scope này. Phần tích hợp/đối chứng/tái lập sản phẩm vẫn pending; hiệu chuẩn là bằng chứng bổ sung, không là gate bắt buộc.
Gói tham số Scoped Parameter Bundle 1.0.0 đã được ban hành dưới dạng giả thiết nghiên cứu công bố phục vụ kiểm chứng giao diện và độ nhạy.
Implementation/testing dưới assumptions có thể tiếp tục khi human agreement pending; real ratings và acceptance chưa thực hiện không được ghi là hoàn tất.


## Cập nhật evidence class theo source review #173 - 2026-10-02

[PR #173](https://github.com/nairyuuu/ad-weighted-graph/pull/173) đã merge tại `96fc89acc0859dd29fc17cdde57466fd8a263a01`, tiếp nhận [hai source sheets và policy](ratings/week3-2026-10-02/README.md).
Hai artifacts hiện thuộc `human_reviewed_ai_assisted_ratings`, với AI assistance/exposure và B confirmation được A chuyển đạt; không dùng chúng để claim blind independent scoring hoặc independent inter-rater reliability.
Historical independent-rating protocol ở trên vẫn áp dụng cho lớp `declared_independent_ratings`; joint human review có disclosure là evidence class riêng, không cần tuyển panel ngoài hoặc xác nhận lại B.
Raw source values, original B AI archive, confirmation channel/time và policy digests được bảo toàn; không ghi điểm hoặc đổi status trong hai fixtures pending cũ.
Tooling #172 bổ sung lớp mới, kiểm policy/confirmation/provenance trước reconciliation và replay offline, từ chối unconfirmed AI hoặc đổi nhãn synthetic/AI-only thành independent evidence.
IoU/Kappa/effort delta trên cặp này chỉ mô tả hai artifacts; agreement threshold không biến proposals thành accepted parameters.
Source confirmation không chọn 21 final dispositions; final numerical acceptance và integrated #48 vẫn pending tới khi có decision records thật và evidence đúng phạm vi.
