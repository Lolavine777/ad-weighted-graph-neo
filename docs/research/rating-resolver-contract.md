# Hợp đồng Rating Resolver và Định danh công việc chuẩn tắc (Rating Resolver Contract)

- Phiên bản hợp đồng: `1.0.0`
- Ngày: 2026-10-09
- Trạng thái: Proposed (A/B Review Gate cho Issue #246, trực thuộc release blocker #245)
- Chủ trì hợp đồng / provenance / basis: TTS A (@Lolavine777)
- Phụ trách tích hợp materialization / reviewer: TTS B (@nairyuuu)
- Tham chiếu: Issue #245, Issue #246, ADR-0013, Specification v1.0.0, Week 3 Reviewed Release

## 1. Mục tiêu và bối cảnh

Trong hệ thống xếp hạng đường tấn công Active Directory, các đường tấn công ngữ nghĩa được sinh tự động bởi engine tìm kiếm (multigraph search và `AttackState`).
Trước Issue #246, hệ thống yêu cầu người gọi phải chuẩn bị sẵn `bound_actions`, `action_bindings` và wire query `PathRankingQuery` cho từng đường đi cụ thể.
Thiếu một hợp đồng chuẩn tắc để tự động kết nối các bước chuyển ngữ nghĩa (semantic transitions) sang cơ sở định mức (rating basis) và báo cáo độ bao phủ (rating coverage).

Mục tiêu của Issue #246 là định nghĩa và hiện thực hóa **Rating Resolver Contract** tối thiểu.
Hợp đồng này đóng vai trò cầu nối trung gian giữa chuỗi chuyển đổi trạng thái do tìm kiếm sinh ra và bộ đánh giá xếp hạng chuẩn tắc `PathRankingEngine`.
Hợp đồng cung cấp ranh giới cho các bước tích hợp tiếp theo của điểm nghẽn P0 Tuần 4.
Chưa coi đây là hoàn tất luồng truy vấn tự động; tích hợp orchestration/CLI và đối chứng độc lập vẫn thuộc các nhiệm vụ kế tiếp.

### Nguyên tắc ranh giới bất biến (Boundary Invariants)
1. Giữ nguyên vẹn thuật toán tìm kiếm đa đồ thị, `AttackState`, semantic replay, công thức tích chuỗi $P(path) = \prod q_i$, biên Pareto bảo thủ và bộ đánh giá chuẩn tắc `PathRankingEngine`.
2. Tuyệt đối không dùng trọng số cấu trúc đơn vị (`unit` $W=1.0$) hoặc profile lịch sử `maut_v1` làm số mặc định khi thiếu dữ liệu định mức.
3. Tuyệt đối không tự ý biến các giả định runtime boolean (`RuntimeFact.origin == DECLARED_ASSUMPTION`) thành xác suất số học.
4. Giữ nguyên vẹn 21 tham số đã được duyệt của bản phát hành SEAMLESS Tuần 3 và oracle ngữ nghĩa của Issue #243.
5. Khi thiếu cơ sở số học, hệ thống áp dụng nguyên tắc đóng lỗi (fail-closed) và xuất ra gói tin unrated có lý do chẩn đoán rõ ràng, được bộ kiểm tra chuẩn tắc chấp nhận.

## 2. Ranh giới kiến trúc và trách nhiệm A / B

Hệ thống phân định nghiêm ngặt quyền sở hữu và ranh giới trách nhiệm giữa hai kỹ sư TTS A và TTS B:
- **TTS A (@Lolavine777):** Chủ trì định nghĩa hợp đồng, chuẩn hóa các định danh versioned, phân tầng nguồn gốc bằng chứng, quy tắc quản trị từ chối (refusal governance), và kiểm thử độc lập.
- **TTS B (@nairyuuu):** Chủ trì thiết kế cấu trúc materialization tương thích với engine sản phẩm, tích hợp vào orchestration/CLI và rà soát giao diện tiêu thụ.

Đầu ra của Rating Resolver đi qua trực tiếp bộ giải mã và kiểm tra chuẩn tắc `decode_ranking_query` cùng `validate_candidate_envelope` trong `src/engine/ranking/validation.py`.
Không xây dựng bộ đánh giá (evaluator) thứ hai chạy song song.

## 3. Tách biệt ba lớp định danh chuẩn tắc

Để ngăn ngừa lỗi đếm trùng và xung đột ngữ cảnh, hợp đồng phân định rõ 3 lớp định danh độc lập:

### 3.1. Định danh hành động ràng buộc (Bound Action Identity - `action_id`)
Đại diện cho một thể hiện hành động cụ thể trong chuỗi thực thi của ứng viên.
Định danh được sinh tất định theo cấu trúc có phiên bản:

`act:{version}:{technique_id}:{actor_id}:{target_id}:{context_digest}`

Trong đó:
- `version`: Phiên bản hợp đồng (`1.0.0`).
- `technique_id`: Định danh kỹ thuật chuẩn tắc từ catalog (ví dụ: `obtain_admin_execution_on_host`).
- `actor_id`: Định danh nút chủ thể chuẩn tắc theo Graph Contract 1.3 (SID hoặc GUID có phạm vi).
- `target_id`: Định danh nút đích chuẩn tắc theo Graph Contract 1.3.
- `context_digest`: Mã băm SHA-256 (16 ký tự đầu) của đối tượng JSON chứa: danh sách tiền đề (`requires`), hiệu ứng (`adds`), cờ bao đóng thụ động (`is_passive_closure`), phương thức thực thi (`method`), ngữ cảnh xác thực (`auth_context`), ngữ cảnh tài nguyên (`resource_context`) và cạnh cấu trúc (`edge_id`).

Quy tắc này bảo đảm hai hành động cùng kỹ thuật và cùng máy chủ đích nhưng khác phương thức (ví dụ WinRM so với WMI), token xác thực hoặc `policy_id` sẽ có `action_id` khác nhau. Nguồn cấu trúc `source_id` cũng tham gia mã băm.

### 3.2. Định danh đơn vị công việc chuẩn tắc (Canonical Work Unit Identity - `work_unit_id`)
Đại diện cho khối lượng công việc thực tế kẻ tấn công phải vượt qua, dùng để tính công sức ($C$) và tra cứu tiền tố xác suất ($P$).
Tuân thủ nghiêm ngặt định dạng chuẩn tắc quy định tại ADR-0013 Mục 5:

`{technique}:{actor_id}:{target_id}:{context}:{boundary}:{ledger_version}`

Ví dụ thực tế từ bản phát hành Tuần 3:
`reset_password:S-1-5-21-1271839998-3495686680-2211690266-4131:S-1-5-21-1271839998-3495686680-2211690266-3398:default:intra_forest:1.0.0`

### 3.3. Khóa tra cứu định mức (Rating Lookup Keys)
Khi resolver tự sinh work unit, trường `context` là `ctx-{sha256}`, băm toàn bộ
`source_id/method/auth_context/resource_context/policy_id/scenario_id` trước khi gộp.
Không đưa provenance định mức vào identity: hai nguồn chấm cùng một công việc không làm tăng công sức.
Nếu caller dùng lại một ID tường minh cho ngữ cảnh không tương thích, resolver báo lỗi;
không giữ metadata của candidate xuất hiện đầu tiên. Chuẩn bị dùng chung giữ phương thức riêng của nó,
và chỉ được tái sử dụng khi ngữ cảnh xác thực/tài nguyên/chính sách tương thích.

Khóa tra cứu tham số từ các provider định mức độc lập theo từng chiều đánh giá, bảo tồn đầy đủ các chiều ảnh hưởng:

1. **Khóa tra cứu Công sức (Effort Lookup Key - C):**
Bao gồm: `work_unit_id`, `technique`, `actor_id`, `target_id`, `work_class`, `method`, `boundary`, `scope`, `auth_context`, `resource_context`, `policy_id`.
Khóa này cho phép provider công sức xác định đúng ma sát theo phương thức và ngữ cảnh bảo mật.

2. **Khóa tra cứu Xác suất (Likelihood Lookup Key - P):**
Bao gồm: `scenario_id`, `scenario_version`, `snapshot_id`, `foothold_node_id`, `ordered_work_prefix` (danh sách có thứ tự các work unit chủ động đã hoàn thành trước đó), `outcome_work_unit_id`, `outcome_technique`, `actor_id`, `target_id`, `method`, `budget`, `horizon`, `boundary`, `scope`, `auth_context`, `policy_id`.
Khóa này bảo đảm tính chuỗi và điều kiện hóa chặt chẽ trên toàn bộ lịch sử thành công trước đó.

3. **Khóa tra cứu Tác động (Impact Lookup Key - I):**
Bao gồm: `target_asset_id`, `success_event`, `consequence_scope`, `boundary`, `scenario_id`, `policy_id`.
Khóa này ràng buộc trực tiếp vào hậu quả kinh doanh của sự kiện đích, không gộp chung với quyền hạn kỹ thuật Tier 0.

## 4. Phân loại công việc và cơ chế chống tính trùng (Anti-Double-Counting)

Hợp đồng phân chia mỗi bước chuyển đổi thành một trong ba nhóm công việc:

1. **Đơn vị công việc chủ động (Active Work Unit):**
Các hành động đòi hỏi thao tác kỹ thuật, tạo ra ma sát và rủi ro bị phát hiện (ví dụ: đặt lại mật khẩu, yêu cầu vé Kerberos, thực thi từ xa).
Các bước này được cấp `work_unit_id` chuẩn tắc, tính điểm rubric $T_1, T_2 \in \{1, 2, 3\}$ với chi phí $C = T_1 + T_2 - 2$ ($0 \le C \le 4$), và yêu cầu tra cứu khoảng xác suất điều kiện.

2. **Bao đóng thụ động (Passive Closure):**
Các bước mở rộng quyền hạn tự nhiên theo cấu trúc đồ thị (ví dụ: kế thừa thành viên nhóm `propagate_group_entitlement`).
Hành động được gán `is_passive_closure: true`, danh sách `referenced_work_unit_ids: []`.
Bao đóng thụ động không sinh ra bản ghi nào trong sổ cái `work_units_ledger`, chi phí công sức bổ sung bằng 0, và không tạo câu hỏi xác suất trong `conditional_bounds_table` ($q = 1$).

3. **Chuẩn bị kiên trì dùng chung (Shared Persistent Preparation):**
Các công việc chuẩn bị tạo ra năng lực dùng chung duy trì lâu dài (ví dụ: thiết lập ngữ cảnh xác thực `w-auth-context` hoặc chuẩn bị token).
Khi nhiều hành động trong cùng một đường dẫn (hoặc giữa các ứng viên khác nhau) cùng dùng chung sự chuẩn bị này, tất cả các hành động đều tham chiếu tới cùng một `work_unit_id` duy nhất.
Trong sổ cái kiên trì, công việc này chỉ xuất hiện một lần và công sức chỉ được cộng đúng một lần trong tổng nỗ lực của ứng viên ($C(\text{program}) = \sum_{u \in \text{distinct}(units)} C(u)$).

## 5. Quy tắc bảo toàn tiền tố đầy đủ cho Xác suất (Full-History P Conditioning)

Theo ADR-0013 Mục 2, xác suất thành công của một chương trình tấn công phải tuân thủ quy tắc nhân xác suất có điều kiện:
$P(\text{success} \mid F, S, \text{program}) = \prod_{i=1}^k P(E_i \mid F, S, E_1, \ldots, E_{i-1})$.

Hợp đồng Rating Resolver quy định:
- Tiền tố điều kiện hóa `ordered_work_prefix` được xây dựng từ chuỗi các đơn vị công việc chủ động duy nhất theo đúng thứ tự xuất hiện lần đầu trong quá trình thực thi:
  `program = tuple(dict.fromkeys(u for packet in work_packets for u in packet))`.
- Bước thứ $k$ có tiền tố tra cứu đầy đủ là `program[:k]`.
- Thứ tự của các bước quyết định danh tính khóa tra cứu xác suất: chuỗi $[A, B]$ và chuỗi $[B, A]$ có khóa tiền tố cho bước 2 hoàn toàn khác nhau.
- Báo cáo độ bao phủ phải kiểm tra và ghi nhận toàn bộ các tiền tố từ độ dài 1 đến $k$; không được dừng ghi nhận lỗi tại tiền tố thiếu đầu tiên.

## 6. Trạng thái phân giải (Dispositions) và Mã lý do có cấu trúc

Mỗi yêu cầu định mức cho một đơn vị công việc, tiền tố xác suất hoặc tác động tài sản sẽ nhận một trong 5 trạng thái phân giải chuẩn tắc:

| Trạng thái (Disposition) | Ý nghĩa nghiệp vụ | Hành vi hệ thống |
| --- | --- | --- |
| `rated` | Có căn cứ định mức hợp lệ từ provider hoặc gói phát hành được duyệt. | Điền giá trị số nguyên ($C$), phân số hữu tỷ ($P$) hoặc mức thứ tự ($I$). |
| `unrated` | Không tìm thấy bằng chứng hoặc cơ sở định mức (thiếu dữ liệu). | Giữ giá trị null; ghi mã lý do vào `missing_basis_reasons`; cách ly fail-closed. |
| `unsupported` | Kỹ thuật, biên hoặc phạm vi nằm ngoài năng lực đánh giá của provider. | Ghi nhận trace và thử provider kế tiếp trong chuỗi. |
| `refused` | Provider chủ động từ chối đánh giá do vi phạm cổng tiên quyết hoặc ranh giới holdout. | Ghi nhận từ chối; **dừng chuỗi provider ngay lập tức**, không chuyển tiếp fallback. |
| `conflicting` | Nhiều provider trả về kết quả mâu thuẫn mà không có chính sách hòa giải thống nhất. | Ghi nhận mâu thuẫn; giữ trạng thái unrated hoặc báo lỗi, không tự ý lấy trung bình. |

### Các mã lý do có cấu trúc (Structured Reason Codes)
- `MISSING_EVIDENCE`: Thiếu dữ liệu thực nghiệm hoặc nhận định kịch bản.
- `OUT_OF_SCOPE`: Yêu cầu nằm ngoài phạm vi hoạt động của provider.
- `UNSUPPORTED_TECHNIQUE`: Provider không hỗ trợ kỹ thuật tấn công này.
- `PREREQUISITE_GATE_REFUSAL`: Provider từ chối do điều kiện tiên quyết không thỏa mãn.
- `HOLDOUT_ISOLATION_REFUSAL`: Provider từ chối nhằm bảo vệ tính cô lập của tập dữ liệu kiểm thử.
- `CONFLICTING_PROVIDER_BASIS`: Cơ sở dữ liệu giữa các nguồn xung đột nhau.
- `MALFORMED_INPUT`: Đầu vào không đúng chuẩn tắc Graph Contract 1.3 hoặc sai cấu trúc.
- `EXPLICIT_UNRATED_DISPOSITION`: Hồ sơ nguồn công bố tường minh trạng thái chưa định mức.
- `ZERO_ACTION_GOAL`: Mục tiêu đã đạt ngay tại foothold ban đầu; không phát sinh công việc mới.
- `PASSIVE_CLOSURE`: Bước lan truyền tự nhiên, không tính ma sát.
- `SHARED_PREPARATION_REUSED`: Tái sử dụng bước chuẩn bị đã có trong sổ cái.
- `REVIEWED_PACKET_MATCH`: Khớp chính xác với bản ghi đã được người kiểm duyệt phê chuẩn.

### Nguyên tắc bảo toàn từ chối (Refusal Integrity)
Nếu một provider trả về `REFUSED` (ví dụ do rò rỉ dữ liệu holdout hoặc thiếu cổng tiên quyết), Resolver bắt buộc phải tôn trọng phán quyết đó.
Hệ thống nghiêm cấm việc bỏ qua `REFUSED` để nhảy sang provider dự phòng (fallback) nhằm tạo ra số liệu giả.

## 7. Phân tầng nguồn gốc và Quản trị bằng chứng (Basis Governance)

Mọi giá trị được gán nhãn phải ghi rõ nguồn gốc thuộc một trong các nhóm phân tầng:
1. `empirical_evidence`: Dữ liệu đo đạc thực nghiệm từ phòng thí nghiệm hoặc đo đếm telemetry.
2. `human_reviewed_ai_assisted_ratings`: Điểm số do AI đề xuất và đã được hai kỹ sư A/B rà soát, phê chuẩn dưới chính sách kịch bản xác định.
3. `declared_independent_ratings`: Điểm số do chuyên gia đánh giá độc lập theo rubric.
4. `scenario_assumption`: Giả định kịch bản có giải trình kỹ thuật trong phạm vi cố định.
5. `synthetic_test_only`: Fixture tổng hợp phục vụ kiểm thử thuật toán và hợp đồng.

Tuyệt đối cấm sử dụng trọng số cạnh cấu trúc cũ hoặc profile `maut_v1` để suy diễn ra chi phí công sức hoặc xác suất chuỗi.

## 8. Lược đồ báo cáo độ bao phủ định mức (Rating Coverage Schema)

Mỗi lần thực thi resolve sinh ra một báo cáo JSON có cấu trúc hoàn chỉnh phục vụ kiểm toán:

```json
{
  "coverage_version": "1.0.0",
  "query_id": "query-resolved-001",
  "scenario_id": "scenario-enterprise-01",
  "snapshot_id": "sha256:...",
  "providers_attempted": [
    "explicit_packet_provider",
    "empirical_provider",
    "fallback_unrated_provider"
  ],
  "aggregate_summary": {
    "total_candidates": 2,
    "fully_rated_candidates": 1,
    "partially_rated_candidates": 1,
    "unrated_candidates": 0,
    "total_unresolved_gaps": 2
  },
  "candidate_summaries": {
    "Candidate_1": {
      "c_complete": true,
      "p_complete": true,
      "i_complete": true,
      "eligibility": "eligible"
    },
    "Candidate_2": {
      "c_complete": true,
      "p_complete": false,
      "i_complete": true,
      "eligibility": "ineligible_partially_unrated"
    }
  },
  "candidates": {
    "Candidate_1": {
      "candidate_id": "Candidate_1",
      "is_zero_action": false,
      "rating_eligibility": "eligible",
      "effort": {
        "all_rated": true,
        "total_units": 2,
        "rated_units": 2,
        "unrated_units": 0,
        "units": { ... },
        "gaps": []
      },
      "likelihood": {
        "all_rated": true,
        "total_prefixes": 2,
        "rated_prefixes": 2,
        "unrated_prefixes": 0,
        "prefixes": [ ... ],
        "gaps": []
      },
      "impact": {
        "target_asset_id": "...",
        "success_event": "...",
        "disposition": "rated",
        "consequence_rating": "High",
        "reason_code": "reviewed_packet_match",
        "provider_trace": [ ... ]
      }
    }
  },
  "unresolved_gaps": [
    {
      "dimension": "P",
      "target_id": "[\"wu_prep\", \"wu_crack\"]",
      "prefix": ["wu_prep", "wu_crack"],
      "outcome_unit": "wu_crack",
      "disposition": "unrated",
      "reason_code": "missing_evidence",
      "reason_detail": "No empirical distribution found for offline hash cracking",
      "affected_candidates": ["Candidate_2"],
      "provider_trace": [ ... ]
    }
  ]
}
```

Báo cáo liệt kê tường minh toàn bộ các khoảng trống (`unresolved_gaps`), chỉ rõ chiều dữ liệu bị thiếu (C, P hoặc I), các ứng viên bị ảnh hưởng và vết lịch sử các provider đã thử.

## 9. Khả năng tương thích ngược và các ca biên (Compatibility & Edge Cases)

### 9.1. Tương thích với gói Tuần 3 và Fixture Tuần 4
Nếu người gọi cung cấp một gói định mức đã được duyệt (`explicit_packet`, ví dụ `reviewed-release.json` của SEAMLESS hoặc `synthetic-a2-e.json` của Tuần 4):
- Resolver bảo toàn nguyên vẹn mọi giá trị $C$, khoảng $P$, mức $I$, và giải trình đã có.
- Không tự ý ghi đè hay làm tròn số liệu.
- Các hành động trùng khớp nhận mã lý do `REVIEWED_PACKET_MATCH`.

Việc tái sử dụng yêu cầu khớp phạm vi packet: scenario/version, snapshot, foothold,
biên, horizon, budget, chế độ đánh giá, chính sách và mục tiêu/sự kiện thành công.
Record phải khớp `applicable_queries`, `scope_binding`, `rating_context` nếu đã khai báo.
Record công sức cũ chưa có `rating_context` chỉ dùng trong ngữ cảnh mặc định và phải có
action được duyệt ràng buộc đúng kỹ thuật/chủ thể/đích. Với P, kiểm tra toàn bộ prefix,
kể cả applicability của công việc trước đó. I phải khớp success event và consequence scope.
Sai phạm vi trả `refused/out_of_scope` và dừng chuỗi; không fallback để thay packet đã cung cấp.
Bundle có `query_projections` được chọn theo `query_scope.query_id`; phải có đúng một
projection khớp. Query không có trong bundle hoặc nhiều projections cùng query ID
đều bị từ chối. Có thể truyền riêng
`bundle["query_projections"]["source_a"]["query"]` để chọn projection tường minh.
Scope của projection được kiểm tra như packet thường; không dùng bundle metadata
chung để thay thế scope riêng của source B. Các giá trị reviewed release được giữ nguyên.
Alias mơ hồ bị từ chối. Bộ thử fixture không xác nhận gói SEAMLESS là dữ liệu thực nghiệm.

### 9.4. Ánh xạ ngữ nghĩa tường minh và nguồn gốc cạnh

Với `PathResult/TransitionStep` thật, caller phải cung cấp `transition_bindings`:
khóa `(technique_id, actor, source, target)`, giá trị chứa `requires/adds` cùng ngữ cảnh thực thi.
Thiếu ánh xạ thì báo `RankingValidationError`; resolver không tự tạo
`predicate_req_*` hoặc `predicate_add_*`. Facts ledger và lớp predicate vẫn do caller
khai báo theo dữ liệu quan sát/giả định có nguồn gốc, không suy ra fact chỉ vì transition applicable.
Resolver dùng `resolve_facts_ledger` chuẩn để thu thập layer từ map và cả bốn buckets;
không ghi đè Layer 1/2 trong records. Predicate chỉ xuất hiện trong requires/adds/goal
phải có layer trong facts hoặc `transition_bindings[key]["predicate_layers"]` (dictionary
step cũng nhận trường này). Thiếu authority hoặc layer mâu thuẫn bị từ chối; không mặc định layer 3.

Shared preparation được normalize/validate trước khi parse candidates. Hai declarations
cùng UID phải nhất quán về rating/rubric/cost và toàn bộ applicability/provenance.
Prep giữ technique/actor/source/target/method/auth/resource/policy riêng; có thể khai báo
các trường này trực tiếp. Method mặc định của prep là `default`, auth/resource mặc định
là rỗng, policy thiếu dùng query policy, không lấy context từ action sử dụng prep.
Actor/target thiếu dùng binding của caller, source thiếu dùng actor của prep;
nếu các binding tái sử dụng xung đột thì từ chối. Không chọn declaration đầu tiên theo thứ tự candidate.

Adapter chuẩn giữ `request/before/additions/decisions` trong `transition_audit`.
Observed edge phải có record và provenance thật trong `PathResult.edges`;
đầu vào dictionary có thể cung cấp `edges` hoặc provenance tường minh ở từng step.
Derived step giữ `edge_id=None` và `derived_from_step` gốc; không tạo cạnh SHA-256 giữ chỗ.
Các tuyến chỉ gồm observed edges, có thể chia thành nhiều đoạn rời nhau.
Đường chỉ gồm derived steps có tuyến rỗng và lineage ngữ nghĩa đầy đủ.

Mỗi dimension giữ `rating_audit` trong wire record và coverage; từng lần gọi provider
cũng giữ audit trong trace. Audit gồm provider name/version, basis category,
provenance digest, review reference, lookup key và scope binding đã dùng.
Packet ưu tiên basis trên record, sau đó `query_metadata.governance.basis_category`;
chỉ dùng `synthetic_test_only` khi cả hai thiếu. Digest dùng record hoặc bundle digest
đã khai báo, nếu thiếu thì hash query để định danh nội dung (không phải chứng nhận review).
Review reference dùng khai báo riêng hoặc decision reference của reviewed disposition,
không biến technical source/business rationale thành bằng chứng người review.

Coverage chỉ chứng minh độ đầy đủ của cơ sở số học C/P/I (`rating_eligibility`).
Nó không thay thế replay, prerequisite gates, budget hoặc quyết định eligible của evaluator.
Khi cần bằng chứng replay có thẩm quyền cho snapshot roots/actor handoff, dùng
`verify_search_envelope` hiện có ở orchestration; resolver không tự cấp thẩm quyền này.

Provider công sức được định mức phải cung cấp rubric đã chấm với số nguyên chính xác
`t1,t2 ∈ {1,2,3}` và `C=t1+t2−2`. Thiếu rubric, cost sai kiểu hoặc rubric mâu thuẫn
đều bị validator chuẩn từ chối. Không suy rubric từ tổng cost, không dùng `int()` để ép kiểu.

### 9.2. Xử lý mục tiêu ban đầu không cần hành động (Zero-Action Initial Goal)
Khi mục tiêu đã đạt ngay tại nút foothold ban đầu (số bước chuyển đổi bằng 0):
- Nút đích bắt buộc phải trùng với nút foothold; nếu khác hệ thống báo lỗi `RankingValidationError`.
- Danh sách hành động là rỗng `bound_action_ids: []`.
- Danh sách gói công việc là `work_packets: [()]`.
- Không phát sinh đơn vị công việc nào trong sổ cái; tổng công sức chuẩn tắc $C = 0$.
- Không phát sinh câu hỏi tiền tố nào trong bảng xác suất; không làm tăng xác suất giả tạo.
- Tác động được đánh giá đúng trên tài sản mục tiêu.
- Payload hợp lệ đi qua bộ kiểm tra chuẩn tắc và nhận trạng thái `zero_work_disposition`.

### 9.3. Xử lý đầu vào sai định dạng (Fail-Closed on Malformed Input)
Mọi đầu vào không thỏa mãn Graph Contract 1.3:
- Nút không phải SID hoặc GUID chuẩn tắc (hoặc SID namespace-relative chưa có scope).
- Cạnh không khớp mẫu mã băm SHA-256 (`^sha256:[0-9a-f]{64}$`).
- Cạnh cấu trúc không bảo toàn tính liên tục nguồn - đích.
Đều bị từ chối lập tức với ngoại lệ `RankingValidationError`.

## 10. Ví dụ minh họa (Worked Examples)

### Ví dụ 1: Ứng viên được định mức đầy đủ (Fully Rated Candidate)
Ứng viên gồm 2 bước: thiết lập kênh quản trị và leo thang trên Host C0.
- `bound_actions`: 2 hành động liên kết với `w-auth-context` ($C=1$) và `w-direct-admin` ($C=4$).
- `work_units_ledger`: Cả 2 đơn vị đều có `rating_status: "rated"`, tổng $C = 5$.
- `conditional_bounds_table`: Tiền tố `[w-auth-context]` có khoảng $[4/5, 9/10]$; tiền tố `[w-auth-context, w-direct-admin]` có khoảng $[1/2, 3/4]$.
- Tích xác suất toàn chuỗi: $P = [2/5, 27/40]$.
- `target_impact_assessments`: Mức tác động `High`.
- Kết quả: Đủ điều kiện tham gia biên Pareto và đánh giá Min-Effort.

### Ví dụ 2: Ứng viên thiếu dữ liệu một phần (Mixed Unrated Candidate)
Ứng viên thực hiện Kerberoasting có dữ liệu công sức ($C=2$) nhưng chưa có dữ liệu đo đạc thời gian bẻ khóa ngoại tuyến ($P$ của bước crack ticket bị thiếu).
- `work_units_ledger`: Đơn vị công việc có `rating_status: "rated"`, $C=2$.
- `conditional_bounds_table`: Tiền tố crack ticket không có trong bảng; provider trả về `unrated` kèm `ReasonCode.MISSING_EVIDENCE`.
- `target_impact_assessments`: Mức tác động `High`.
- Báo cáo độ bao phủ: Ghi nhận lỗ hổng tại tiền tố crack ticket, nêu rõ provider đã thử và lý do thiếu.
- Kết quả Evaluator: Ứng viên bị chuyển vào phân vùng `diagnostics` với lý do `likelihood_unrated`.
- Giá trị công sức định mức $C=2$ vẫn được lưu giữ phục vụ kiểm toán độc lập Min-Effort.

### Ví dụ 3: Ứng viên bị từ chối do vi phạm cổng tiên quyết (Refused Disposition)
Provider đo lường thực nghiệm phát hiện chuỗi hành động vi phạm ranh giới holdout hoặc điều kiện kích hoạt.
- Provider trả về `ResolverDisposition.REFUSED` kèm mã lý do `PREREQUISITE_GATE_REFUSAL`.
- Resolver không tìm kiếm provider thay thế; đánh dấu tiền tố là `refused`.
- Gói tin wire query phát hành không chứa tiền tố này, đẩy ứng viên vào `diagnostics` fail-closed.

## 11. Bàn giao triển khai cho các Issue kế tiếp (Implementation Handoff)

Hợp đồng Issue #246 bàn giao giao diện chuẩn tắc cho các nhiệm vụ tiếp theo trong chuỗi blocker #245:

| Issue | Trách nhiệm | Giao diện tiêu thụ từ #246 |
| --- | --- | --- |
| **#247** (C Rubric & Classes) | Chuẩn hóa các lớp đơn vị công việc và rubric tính công sức $T_1, T_2$, chống đếm trùng. | Triển khai `EffortRatingProvider`; nhận `EffortLookupKey`; trả về `ResolutionResult` với `rubric_scores` và `computed_cost`. |
| **#248** (P Provider Chain) | Tích hợp adapter thực nghiệm #238, fallback kịch bản có rà soát và xác định khoảng trống chính xác. | Triển khai `LikelihoodRatingProvider`; nhận `LikelihoodLookupKey` kèm tiền tố đầy đủ; trả về `ResolutionResult` với cận phân số `Fraction`. |
| **#249** (I Equivalence) | Chuẩn hóa chính sách tương đương tài sản/hậu quả và provider tác động. | Triển khai `ImpactRatingProvider`; nhận `ImpactLookupKey`; trả về `ResolutionResult` với mức thứ tự `ConsequenceRating`. |
| **#250** (Query / CLI Integration) | Tích hợp Rating Resolver vào public query API và CLI orchestration tự động. | Gọi `RatingResolver.resolve()`; nhận wire query và candidate envelopes; chuyển sang `PathRankingEngine.evaluate()`. |
| **#251** (Independent Proof) | Kiểm chứng độc lập trên ca tự sinh và tái lập chéo hai chiều A/B. | Kiểm tra tính nhất quán của `coverage_report` và xác minh toàn vẹn digest. |

Mã nguồn hợp đồng nằm tại `src/engine/ranking/resolver.py`; kiểm thử gốc và các regression review
nằm ở `tests/test_rating_resolver.py` và `tests/test_rating_resolver_review_regressions.py`.
Gate A/B chỉ chốt sau khi reviewer kiểm tra bản sửa; bản triển khai không tự phê duyệt gate.
# Phần mở rộng public integration #250

Contract/reference implementation #246 đã accepted qua PR #252, merge
`af28ccc88fa8512da8d1e5c7523f791817167844`; nhãn Proposed lịch sử bên dưới
không thay thế disposition accepted trên issue.

Public integration giữ contract `1.0.0` cho numeric providers, canonical keys,
ledger, decoder/evaluator. Thêm envelope `public-rating-resolution/1.0.0` và
`public-rating-coverage/1.0.0` để tách search/binding coverage khỏi numeric coverage.
Native `transition_bindings` nhận thêm locator `(candidate_id, step_index)`;
locator này ưu tiên binding tuple technique/actor/source/target cũ. Đây chỉ là
locator nội bộ được engine assemble từ typed history, không là rating identity:
cùng transition tuple ở hai branch có before-state khác nhau vẫn cần predicates
khác nhau. Bound-action/work IDs vẫn theo hàm identity #246.

Optional `ClassApplicability.source_ids` giới hạn exact source IDs trong JSON
registry; absent giữ hành vi và serialization/digest cũ. Không sửa numeric catalog.

`rating_eligibility`/`candidate_summaries.eligibility` native là numeric disposition;
public `semantic_status` lấy từ canonical assessment, `numeric_complete` chỉ nói
đủ C/P/I. Public counts C/P deduplicate toàn query theo work ID/full ordered prefix;
per-candidate counts giữ denominator trong contract. Passive steps không tạo event;
không diễn giải việc không có event thành một numeric q mới bằng 1.

Tham chiếu [API](week4-query-api.md), [schema](public-rating-coverage.schema.json),
[bảng quyết định](issue-250-public-rating-integration-decisions.md).

### Amendment public 1.1 — pending A cross-review (#258)

Public configuration/coverage nâng lên `public-rating-resolution/1.1.0` và
`public-rating-coverage/1.1.0`; native contract/providers vẫn 1.0.0. Loader đọc
config public 1.0.0 nhưng automatic I mapping phải chứng minh typed terminal
capabilities: `applicability.semantic_goal` là descriptor `semantic-goal/1.0.0`
chuẩn hóa từ required AttackState, kèm exact snapshot/goal ID và review reference.
Provider chọn mapping theo contract trước; public guard kiểm tra đúng selected
mapping qua provenance digest, không chọn lại basis hoặc ghi đè refusal native.
Opaque callable không có descriptor nên I unverifiable; typed goal có callable
bổ sung vẫn chứng minh necessary capabilities bằng conjunction.

Coverage mới thêm descriptor/digest và `scenario_authority`. Semantic reference
vắng không authorize scoped numeric reuse, nhưng không chặn search hoặc basis
reviewed unscoped. Không đổi denominators, passive/shared-work rules, q product,
canonical validation, Pareto hay acceptance của numeric catalogs. Schema đọc
coverage public 1.0 lịch sử và yêu cầu fields mới khi xuất 1.1. Đây là đề xuất
boundary đã implement/test, không tự phê duyệt policy #249/#259 hoặc gate #251.
