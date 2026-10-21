# Đặc tả giao diện xếp hạng đường tấn công (Path Ranking Interface Specification)

- Phiên bản: 1.0.0
- Ngày: 2026-10-03 (Cập nhật tương thích additive cho bounded search #146; kế thừa chuẩn hóa 1.0.0 ngày 2026-10-02)
- Trạng thái: Accepted by TTS A and TTS B for PR #165 scope (Approval #5387665338, commit fdf5928; pending human ratings and subsequent #143/#158 integration/acceptance gates stay separate)
- Người biên soạn: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #143, Refs #158, Refs #165, Refs #162, Refs #163, Refs #42, Refs #140, Refs #141, Refs #142, Refs #150, Refs #151; kế thừa ADR-0013

## 1. Mục tiêu và nguyên tắc thiết kế

Tài liệu này đặc tả chi tiết giao diện hợp đồng phiên bản 1.0.0 giữa khối nghiên cứu mô hình/trọng số (TTS A) và khối engine tìm đường/phân tích đồ thị (TTS B).
Giao diện định nghĩa rõ ràng cấu trúc đầu vào (Inputs), cấu trúc đầu ra (Outputs), hợp đồng độ chính xác số học và tuần tự hóa, cũng như các ví dụ synthetic chuẩn xác có thể kiểm thử lặp lại.

Các nguyên tắc kiến trúc bắt buộc:
1. **Bảo tồn phạm vi cố định (Fixed Query Scope):**
Mọi đánh giá và xếp hạng chỉ có giá trị trong phạm vi một truy vấn duy nhất với foothold, scenario, chân trời thời gian, biên công việc và phiên bản xác định.
Không so sánh chéo giữa các scenario hoặc trộn lẫn ứng viên synthetic với quan sát thực tế.
2. **Xếp hạng Pareto bảo thủ (Conservative Pareto Ranking):**
Kết quả xếp hạng trên hai trục độc lập: Tác động nghiệp vụ ($I \in \{\text{Low, Medium, High, Critical}\}$) và Khoảng xác suất có điều kiện trên toàn bộ tiền tố lịch sử ($P \in [l, u]$).
Không gộp hai trục thành một điểm vô hướng duy nhất hoặc ép buộc thứ tự toàn phần khi thiếu căn cứ.
3. **Nỗ lực là tie-break có điều kiện rất hẹp (Conditional Effort Tie-Break):**
Nỗ lực trên sổ cái công việc chỉ phân giải khi hai ứng viên có cùng mức tác động và cùng xác suất điểm chính xác đã được định mức.
Nếu một trong hai ứng viên chưa định mức nỗ lực hoặc xác suất là khoảng, giữ nguyên trạng thái không so sánh được (`incomparable`).
4. **Tách biệt vết đường cấu trúc khỏi sổ cái công việc (Route Traces vs. Work History):**
Sổ cái công việc chuẩn tắc dùng để tính nỗ lực và tra cứu tiền tố xác suất.
Engine bắt buộc phải lưu giữ riêng biệt danh sách các vết đường cấu trúc và bằng chứng (node IDs, edge IDs, provenance locators) cho từng ứng viên.
Tuyệt đối không đánh đồng số lượng chương trình công việc (program count) với số lượng đường tấn công (path count).
5. **Duy trì truy vấn nỗ lực tối thiểu riêng biệt (Separate Min-Effort-to-DA Query):**
Tìm đường chi phí thấp nhất tới DA là một baseline độc lập có công bố độ bao phủ, không phải là thành viên duy nhất hay được đồng nhất với biên Pareto.
6. **Phân vùng chẩn đoán chặt chẽ (Partitioned Diagnostics):**
Các ứng viên bị chặn hoặc thiếu bằng chứng phải được giữ trong danh sách chẩn đoán với đầy đủ lý do, không được lọt vào biên Pareto.
7. **Độ chính xác số học tuyệt đối (Lossless Arithmetic):**
Sử dụng số hữu tỷ chính xác (stdlib `Fraction`) và chuỗi phân số không mất mát thông tin trong JSON để loại bỏ hoàn toàn lỗi làm tròn dấu phẩy động.

## 2. Đặc tả hợp đồng đầu vào (Input Contract Specification)

Hợp đồng đầu vào bao gồm 6 thành phần bắt buộc trong một đối tượng `PathRankingQuery`:

```text
PathRankingQuery
├── query_metadata: Thông tin phiên bản, scenario, foothold, mục tiêu, ngân sách
├── facts_ledger: Bảng dữ kiện được phân loại có provenance và trạng thái chẩn đoán
├── bound_actions: Danh mục hành động đã ràng buộc chủ thể, điều kiện và hiệu ứng
├── work_units_ledger: Sổ cái các đơn vị công việc kiên trì và trạng thái định mức
├── conditional_bounds_table: Bảng tra cứu khoảng xác suất theo tiền tố đầy đủ
└── target_impact_assessments: Đánh giá hậu quả nghiệp vụ độc lập cho từng tài sản đích
```

### 2.1. Thông tin truy vấn (Query Metadata)

Mỗi yêu cầu xếp hạng phải chứa đầy đủ các trường định danh và giới hạn phạm vi:
- `query_id` (string): Định danh duy nhất của truy vấn, ví dụ `"query-20260930-s2-da-001"`.
- `version` (string): Phiên bản của hợp đồng đặc tả giao diện, ví dụ `"1.0.0"`.
- `scenario_id` (string): Định danh kịch bản runtime được tham chiếu từ catalog, ví dụ `"scenario-corp-compromised-host"`.
- `scenario_version` (string): Phiên bản kịch bản cụ thể được gắn kết với truy vấn, ví dụ `"1.0.0"`.
- `snapshot_id` (string): Định danh snapshot bất biến theo Graph Contract 1.3, ví dụ `"sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"`.
- `evaluation_mode` (string): Chế độ đánh giá dữ kiện, nhận một trong hai giá trị: `"evidence_only"` (chỉ chấp nhận quan sát snapshot, vô hiệu hóa mọi giả thiết runtime) hoặc `"scenario"` (cho phép giả thiết runtime có giải trình cho vị từ Layer 3 khi không có phủ định).
- `work_boundary` (string): Ranh giới biên công việc được kiểm soát, ví dụ `"corp_boundary"`.
- `foothold_node_id` (string): Canonical ID của node khởi đầu bị chiếm quyền theo Graph Contract 1.3, ví dụ `"S-1-5-21-3623811015-3361044348-30300820-1001"`.
Định danh node phải tuân thủ nghiêm ngặt Graph Contract 1.3: các họ SID có tính tương đối theo namespace (`S-1-5-32-*`) hoặc tương đối theo máy chủ (`S-1-5-18/19/20`) bắt buộc phải được gắn phạm vi xác định (`domain:sid:...`, `domain:<guid>:...`, hoặc `host:<guid>:...`); dạng bare/unscoped của các họ này đều bị từ chối xác thực.
Các tên gọi trực quan như `"host:comp1"` hoặc `"dc01"` chỉ được coi là alias và bắt buộc phải nằm trong trường `label` hoặc bảng ánh xạ alias riêng, không được thay thế canonical ID.
- `target_goal` (object): Định nghĩa mục tiêu kịch bản:
  - `goal_id` (string): ví dụ `"S2"`, `"S3"`.
  - `description` (string): ví dụ `"Usable domain identity with active Domain Admin entitlement"`.
  - `required_predicates` (array of strings): ví dụ `["target_controlled", "da_entitlement_active"]`.
- `horizon` (string): Chân trời thời gian và ngữ cảnh hoạt động, ví dụ `"business_hours_72h"`.
- `active_work_budget` (integer): Ngân sách tối đa cho số đơn vị công việc chủ động phân biệt ($B \ge 0$).

### 2.2. Bảng dữ kiện phân tầng và chế độ đánh giá (Typed Facts Ledger & Evaluation Modes)

Dữ kiện đầu vào được quản lý chặt chẽ qua chế độ đánh giá và phân tầng vị từ (predicate layering) để ngăn chặn việc giả lập tùy tiện các đặc quyền cấu trúc.

#### 2.2.1. Chế độ đánh giá (Evaluation Modes)
- `evidence_only`: Chế độ chỉ chấp nhận bằng chứng quan sát thực tế từ snapshot AD.
Mọi giả thiết runtime đều bị vô hiệu hóa hoặc bị từ chối.
- `scenario`: Chế độ cho phép khai báo giả thiết runtime có giải trình kiểm toán cho các vị từ ngữ cảnh, nhưng vẫn phải tuân thủ tuyệt đối yêu cầu bằng chứng cấu trúc và quyền phủ quyết của dữ kiện sai.

#### 2.2.2. Phân tầng vị từ (Predicate Layers)
1. **Layer 1: Vị từ ủy quyền cấu trúc (Structural Authorization Predicates - Immutable from Snapshot):**
- Các vị từ thể hiện quyền hạn AD thực tế: `structural_genericall`, `replication_authorization` (DS-Replication-Get-Changes-All / Gate O), `member_of_group`.
- Yêu cầu nghiêm ngặt: Bắt buộc phải được chứng minh bởi bản ghi positive provenance trong snapshot AD.
- Tuyệt đối không cho phép đặt vào `assumed_facts` để tự ý thỏa mãn điều kiện.
- Nếu snapshot thiếu bản ghi, vị từ bắt buộc phải giữ trạng thái `Unknown`.
- Nếu snapshot ghi nhận rõ ràng không có quyền, vị từ là `False`.
2. **Layer 2: Vị từ khả năng và vệ sinh hệ thống (Host Capability & Hygiene Predicates):**
- Các vị từ về cấu hình host và dịch vụ: `smb_signing_enabled`, `spn_configured`, `laps_enabled`.
- Được trích xuất từ telemetry hệ thống.
- Nếu snapshot xác nhận dịch vụ tắt hoặc không có, dữ kiện `False` này đóng vai trò quyền phủ quyết tuyệt đối (hard veto), không thể bị ghi đè bởi giả thiết.
3. **Layer 3: Vị từ ngữ cảnh runtime (Runtime Context Predicates):**
- Các vị từ về trạng thái vận hành nhất thời: `session_present`, `password_policy_satisfied`, `directory_write_available`.
- Trong chế độ `scenario`, các vị từ này được phép khai báo trong `assumed_facts` kèm theo giải trình nghiệp vụ khi snapshot không có quan sát phủ định.

#### 2.2.3. Cấu trúc bản ghi dữ kiện
Dữ kiện đầu vào được tổ chức vào 4 danh sách chẩn đoán:
- `observed_facts` (array): Dữ kiện có bằng chứng dương hợp lệ trong snapshot AD.
- `assumed_facts` (array): Giả thiết về môi trường runtime có nguồn giải trình trong chế độ `scenario`.
- `false_facts` (array): Dữ kiện được xác định là sai (tài khoản disabled, cổng bị chặn, quyền bị phủ quyết).
- `unknown_facts` (array): Dữ kiện thiếu bằng chứng thu thập hoặc chưa được đo lường.

Mỗi phần tử dữ kiện phải tuân thủ cấu trúc:
```json
{
  "predicate": "session_present",
  "layer": 3,
  "truth_value": true,
  "category": "assumed",
  "rationale": "Active administrator logon session is assumed present on compromised workstation during business hours",
  "provenance_reference": null
}
```

**Yêu cầu tầng thẩm quyền bắt buộc (Authoritative Layer Requirement):**
Mọi vị từ xuất hiện trong truy vấn và đánh giá ứng viên (bao gồm các danh sách trong `facts_ledger`, `bound_actions.requires`, `bound_actions.adds`, `target_goal.required_predicates`, và `candidate.required_predicates`) bắt buộc phải có tầng phân loại thẩm quyền rõ ràng (Layer 1, 2, hoặc 3), được khai báo tập trung trong `predicate_layers` hoặc trực tiếp tại trường `layer` của từng bản ghi dữ kiện.
Hệ thống tuyệt đối không suy đoán tầng mặc định (chẳng hạn không được mặc định về Layer 3) khi thiếu metadata.
Bất kỳ vị từ nào xuất hiện trong các danh sách dữ kiện (`observed_facts`, `false_facts`, `assumed_facts`, `unknown_facts`), trong hành động (`requires`/`adds`), trong mục tiêu (`target_goal`), hoặc trong yêu cầu ứng viên (`candidate.required_predicates`) mà thiếu khai báo tầng thẩm quyền đều lập tức bị từ chối bằng lỗi xác thực (`ValueError`).
Quy định này loại bỏ hoàn toàn nguy cơ một vị từ ủy quyền cấu trúc (Layer 1 như `replication_authorization`) hoặc cấu hình máy chủ (Layer 2) bị bỏ sót phân tầng để vô tình mặc định thành Layer 3 cho phép hành động tự do mutate trong quá trình replay.

#### 2.2.4. Quy trình phân giải vị từ và đánh giá chân thực (Resolution Pipeline & Precedence)
Với mỗi vị từ $P$ cần đánh giá, hệ thống thực hiện phân giải theo 3 bước tuần tự:

**Bước 1: Đối soát và phân giải quan sát thực tế (Observation Reconciliation):**
- Thu thập toàn bộ các quan sát thô từ snapshot và telemetry cho vị từ $P$.
- *Xử lý xung đột quan sát (Conflicting Observations):* Nếu snapshot chứa đồng thời cả quan sát khẳng định (True) và quan sát phủ định (False) từ các nguồn thu thập khác nhau, $P$ rơi vào trạng thái xung đột và lập tức nhận giá trị $\text{Unknown}$ kèm lý do chẩn đoán `contradictory_telemetry`.
- *Quan sát phủ định đồng nhất:* Nếu các quan sát đồng nhất là False (không có True), $P$ được ghi nhận là quan sát phủ định (observed False).
- *Quan sát khẳng định đồng nhất:* Nếu có quan sát True và không có False, $P$ được ghi nhận là quan sát khẳng định (observed True).
- *Thiếu quan sát:* Nếu không có bất kỳ quan sát nào, $P$ là quan sát còn thiếu (missing observation).

**Bước 2: Áp dụng quy tắc phân tầng vị từ và quyền phủ quyết (Layer Rules & Precedence):**
- *Quy tắc Xung đột (Conflict Sanctity):* Xung đột quan sát (`contradictory_telemetry`) không thể bị ghi đè bởi bất kỳ giả thiết nào; vị từ giữ nguyên $\text{Unknown}$.
- *Quy tắc Quyền phủ quyết (Known-False Veto):* Quan sát phủ định đồng nhất (observed False không xung đột) đóng vai trò quyền phủ quyết tuyệt đối; $P$ nhận giá trị $\text{False}$ (`observed_false_veto`), bất kể $P$ có được khai báo trong `assumed_facts` hay không.
- *Quy tắc Tầng 1 (Structural Authorization Sanctity):* Với vị từ Layer 1, bắt buộc phải có quan sát khẳng định (observed True) trong snapshot; mọi khai báo trong `assumed_facts` đều bị vô hiệu hóa; nếu thiếu quan sát thì $P$ giữ nguyên $\text{Unknown}$ (`missing_structural_provenance`).
- *Quy tắc Tầng 2 (Host Capability & Hygiene):* Phân giải theo quan sát thực tế: True nếu có quan sát khẳng định, False nếu có quan sát phủ định (`observed_false_veto`), Unknown nếu thiếu quan sát (`missing_telemetry`).
- *Quy tắc Tầng 3 (Runtime Context):*
  - Trong chế độ `evidence_only`: Giả thiết bị vô hiệu hóa; nếu thiếu quan sát khẳng định thì $P$ nhận giá trị $\text{Unknown}$ (`evidence_only_disallows_assumptions`).
  - Trong chế độ `scenario`: Nếu thiếu quan sát khẳng định (và không bị xung đột hay phủ định), nếu $P \in \text{assumed\_facts}$ có giải trình hợp lệ thì $P$ nhận giá trị $\text{True}$ (`permitted_runtime_assumption`). Nếu không được khai báo thì là $\text{Unknown}$ (`missing_runtime_context`).

**Bước 3: Thứ tự hội chân thực tổng thể của chương trình:**
$$\text{False} > \text{Unknown} > \text{True}$$
- Nếu có bất kỳ vị từ nào mang giá trị `False`, chương trình lập tức bị đánh dấu là `blocked`.
- Nếu không có `False` nhưng có ít nhất một vị từ `Unknown`, chương trình mang trạng thái `unknown`.
- Chỉ khi toàn bộ các vị từ bắt buộc đều là `True`, chương trình mới là `feasible`.

**Ràng buộc phạm vi và phiên bản (Scope & Version Binding):**
Tập dữ kiện và các bảng định mức được gắn chặt với `query_id`, `snapshot_id`, `scenario_id`, `scenario_version` và `work_boundary`.
Tuyệt đối không tái sử dụng các giả thiết hoặc khoảng xác suất qua các phiên bản kịch bản hoặc biên công việc khác nhau mà không được đối soát lại.

#### 2.2.5. Các ví dụ phân giải cụ thể
- *Ví dụ xung đột quan sát:* Snapshot vừa có bản ghi cho thấy cổng LDAP mở vừa có bản ghi firewall chặn cổng -> phân giải thành $\text{Unknown}$ (`contradictory_telemetry`), giả thiết không thể ghi đè.
- *Ví dụ observed false veto:* Tài khoản đích được snapshot ghi nhận `enabled: false` (Layer 2) -> dù `assumed_facts` có khai báo `target_user_enabled: true`, vị từ vẫn bị phân giải thành $\text{False}$ (chương trình bị `blocked`).
- *Ví dụ ủy quyền cấu trúc không thể giả định:* Vị từ Gate O `replication_authorization` (Layer 1) không có bản ghi provenance trong snapshot -> dù được đặt vào `assumed_facts`, hệ thống vẫn từ chối và giữ nguyên $\text{Unknown}$ (chương trình mang trạng thái `unknown`).
- *Ví dụ chế độ evidence_only:* Vị từ `session_present` (Layer 3) được khai báo trong `assumed_facts` nhưng truy vấn đặt `evaluation_mode: "evidence_only"` -> vị từ bị phân giải thành $\text{Unknown}$ do không có quan sát telemetry.
- *Ví dụ runtime assumption hợp lệ trong chế độ scenario:* Vị từ `session_present` (Layer 3) chưa có trong telemetry, không có phủ định hay xung đột, được khai báo trong `assumed_facts` ở chế độ `scenario` -> phân giải thành $\text{True}$ (thỏa mãn Gate A).

### 2.3. Danh mục hành động đã ràng buộc (Bound Actions Catalog)

Mỗi hành động tấn công đại diện cho một bước chuyển trạng thái nghiệp vụ đã được gắn chủ thể, đích và ngữ cảnh:
- `action_id` (string): Định danh hành động, ví dụ `"action_reset_admin_user"`.
- `technique_name` (string): Tên kỹ thuật AD theo catalog, ví dụ `"genericall_reset_password"`.
- `actor_id` (string): Canonical ID của chủ thể thực hiện.
- `target_id` (string): Canonical ID của đối tượng đích.
- `requires` (array of strings): Tập các vị từ bắt buộc phải có trong tập dữ kiện trước khi thực hiện.
- `adds` (array of strings): Tập các vị từ mới được bổ sung vào tập dữ kiện sau khi thực hiện thành công.
- `referenced_work_unit_ids` (array of strings): Danh sách các định danh đơn vị công việc mà hành động này yêu cầu hoàn thành.
- `is_passive_closure` (boolean): `true` nếu đây là bước đóng bao đóng entitlements thụ động (ví dụ phân giải MemberOf), không tạo thêm nỗ lực chủ động.

**Tính bất biến của ủy quyền cấu trúc và năng lực máy chủ (Layer 1 & Layer 2 Immutability under Action Effects):**
Các hiệu ứng bổ sung (`adds`) của hành động trong chuỗi chỉ được phép cập nhật các vị từ trạng thái dẫn xuất thời gian chạy (Layer 3).
Tuyệt đối không cho phép `adds` của hành động ghi đè hoặc tự khẳng định vị từ ủy quyền cấu trúc snapshot (Layer 1, ví dụ quyền nhân bản `replication_authorization`) hoặc vị từ năng lực và cấu hình vệ sinh máy chủ (Layer 2, ví dụ `firewall_port_open`, `smb_signing_enabled`).
Vị từ Layer 1 và Layer 2 mang giá trị phủ định (`False`) hoặc thiếu căn cứ (`Unknown`) theo bằng chứng snapshot và telemetry bắt buộc phải bất biến giữ nguyên giá trị `False` hoặc `Unknown`.
Mọi nỗ lực của hành động nhằm `adds` vị từ Layer 1 hoặc Layer 2 đều bị bỏ qua (không mutate trạng thái dữ kiện); hành động kế tiếp đòi hỏi vị từ đó vẫn tuân thủ đúng quy tắc chân thực tại Mục 2.2.4 (mang trạng thái `blocked` nếu vị từ là `False`, hoặc `unknown` nếu vị từ là `Unknown`).

**Quy tắc điểm dừng ở lần đầu đạt mục tiêu (Goal First-Hitting Time Conformance - ADR-0013):**
Theo ADR-0013 mục 1, chuỗi chương trình kết thúc ngay ở lần đầu tiên toàn bộ các vị từ mục tiêu (`target_goal.required_predicates`) được thỏa mãn (kể cả tại trạng thái ban đầu step 0).
Các hành động hậu tố (suffix actions) sau điểm này sẽ được cắt tỉa (trimmed).
Nỗ lực (`effort`), khoảng xác suất (`likelihood_interval`), gói công việc (`work_packets`), định danh hành động (`bound_action_ids`) cùng vết đường cấu trúc (`structural_routes`) chỉ được tính và đồng bộ cho tiền tố đạt mục tiêu theo quy tắc an toàn đồng bộ vết tại Mục 3.2.
Các điều kiện tiên quyết của hành động hậu tố bị cắt tỉa sẽ không được đánh giá và không làm chặn tính khả thi (`feasible`) của tiền tố đã hoàn thành mục tiêu.
Nếu mục tiêu đã được thỏa mãn ngay tại trạng thái ban đầu của snapshot, chương trình được cắt tỉa về chuỗi rỗng (`nominal_effort = 0`, `effort = 0`, xác suất `[1, 1]`).

**Tính bảo toàn của điều kiện ban đầu chưa thỏa (Persistence of Unsatisfied Initial Requirements):**
Việc đạt mục tiêu tại một bước sau trong chuỗi không được phép xóa bỏ hoặc ghi đè trạng thái `Unknown` của các điều kiện tiên quyết ban đầu (`candidate.required_predicates`).
Nếu điều kiện ban đầu đánh giá ra `Unknown`, trạng thái kiểm soát thực thi (`gate_status`) bắt buộc phải duy trì là `unknown`, toàn bộ nỗ lực hợp lệ (`effort`) và khoảng xác suất (`likelihood_interval`) phải bị khấu trừ (withheld thành `null`), và ứng viên phải được phân vùng vào `diagnostics` với lý do `["unknown", "likelihood_unrated"]`.
Nếu một điều kiện chỉ cần được tạo ra ở bước sau bởi hành động đi trước, điều kiện đó phải được đặt trong `requires` của bước tương ứng, không được coi là điều kiện ban đầu của ứng viên.

### 2.4. Sổ cái đơn vị công việc chuẩn tắc (Canonical Work Units Ledger)

Đơn vị công việc là phần việc chủ động kiên trì (persistent active work unit):
- `work_unit_id` (string): Định danh chuẩn tắc theo định dạng bất biến:
  `technique:actor_id:target_id:context:boundary:ledger_version`
  Ví dụ: `"pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1001:S-1-5-21-3623811015-3361044348-30300820-1000:int_net:corp_boundary:v1"`.
- `rating_status` (string): `"rated"` hoặc `"unrated"`.
- `rubric_scores` (object hoặc null):
  - `t1` (integer): Độ phức tạp kỹ thuật và công cụ ($T_1 \in \{1, 2, 3\}$):
    - Mức 1: Công cụ tiêu chuẩn, có sẵn (built-in Windows commands, standard LDAP queries, native PowerShell).
    - Mức 2: Công cụ tấn công chuyên dụng, kỹ năng trung cấp (BloodHound ingestors, Mimikatz, Rubeus, Impacket scripts).
    - Mức 3: Công cụ tùy biến nâng cao, thao tác giao thức chuyên sâu (custom shadow credentials, complex ESC certificate relay chains, unconstrained delegation manipulation).
  - `t2` (integer): Độ ma sát tương tác và thời gian thực hiện ($T_2 \in \{1, 2, 3\}$):
    - Mức 1: Ma sát thấp (truy vấn mạng trực tiếp RPC/LDAP, quan sát thụ động, không yêu cầu session đăng nhập tương tác).
    - Mức 2: Ma sát trung bình (yêu cầu session đăng nhập xác thực, khởi động lại dịch vụ cục bộ, hoặc logon trên host).
    - Mức 3: Ma sát cao (yêu cầu tương tác người dùng, vượt qua ranh giới tường lửa/mạng phức tạp, hoặc cửa sổ thời gian chặt chẽ).
  - `formula` (string): Quy ước tính nỗ lực cơ sở, ví dụ `"base"` ($T_1 + T_2 - 2$).
  - `computed_cost` (integer): Giá trị nỗ lực quy ước ($0 \le C \le 4$ cho đơn vị chủ động; $C = 0$ cho đồng bộ thụ động).
- `overlap_state` (string): `"independent"` hoặc `"unresolved_overlap"`.
  Nếu `unresolved_overlap`, giá trị `computed_cost` phải là `null` và `rating_status` phải là `"unrated"`.

**Lưu ý về ranh giới rubric:**
Công thức cơ sở $C = T_1 + T_2 - 2$ với $T_1, T_2 \in \{1, 2, 3\}$ là quy ước rubric nghiên cứu (research rubric convention) đã được rà soát và thống nhất tại các nghiên cứu #141, #147 và PR #151.
Quy ước này phục vụ xếp hạng tương đối và kiểm thử mô hình synthetic, KHÔNG phải là số đo giờ công thực tế đã được hiệu chuẩn sản phẩm.
Việc mở rộng thang đo (như 1-5) hoặc đề xuất rubric mới đòi hỏi một tài liệu riêng có đầy đủ anchors, giải trình ranh giới và kế hoạch migration được review độc lập.

### 2.5. Bảng tra cứu khoảng xác suất tiền tố đầy đủ và Wire Contract (Conditional Bounds Table & Wire Format)

Bảng tra cứu xác suất có điều kiện ánh xạ từ toàn bộ chuỗi tiền tố các đơn vị công việc đã hoàn thành sang khoảng xác suất hợp lệ.
Do định dạng JSON không cho phép dùng tuple làm khóa, wire contract quy định `conditional_bounds_table` được biểu diễn dưới dạng danh sách các đối tượng (array of objects):

```json
[
  {
    "prefix": ["prep_kerberoast"],
    "lower": "1/10",
    "upper": "2/10",
    "basis_category": "expert_elicitation",
    "rationale": "Ticket extraction rate given kerberoastable service accounts"
  },
  {
    "prefix": ["prep_kerberoast", "crack_ticket"],
    "lower": "1/1",
    "upper": "1/1",
    "basis_category": "expert_elicitation",
    "rationale": "Cracking success given offline dictionary capture"
  }
]
```

**Chính sách kiểm tra hợp lệ đầu vào và trùng lặp khóa (Input Validation & Duplicate Key Policy):**
- Mỗi `prefix` trong danh sách phải là duy nhất trên toàn bộ bảng.
- Nếu một truy vấn truyền hai đối tượng có cùng chuỗi `prefix` nhưng mang khoảng xác suất khác nhau, hệ thống phải lập tức báo lỗi hợp lệ (`DuplicatePrefixError`, HTTP 400).
- Adapter phía nghiên cứu / engine sẽ phân tích danh sách này thành bảng tra cứu bộ nhớ với khóa là tuple `tuple(item["prefix"])` và chuỗi phân số thành đối tượng `Fraction`.
- **Yêu cầu chặt chẽ:** Không cho phép fallback về xác suất biên đơn lẻ (marginal probability) nếu thiếu khóa tiền tố đầy đủ.
Mọi sự thiếu hụt đều khiến xác suất của toàn chương trình trở thành `likelihood_unrated`.

### 2.6. Đánh giá hậu quả nghiệp vụ và ràng buộc mục tiêu (Target Impact Assessment & Candidate Binding)

Đánh giá tác động nghiệp vụ được thực hiện cho sự kiện thành công tới đích và gắn với từng tài sản đích trong truy vấn:
- Trong `PathRankingQuery`, thành phần này có thể được biểu diễn qua `target_impact_assessments: dict[str, TargetImpactAssessment]` (ánh xạ từ canonical ID của tài sản đích sang hồ sơ đánh giá) hoặc `target_impact_assessment` khi toàn bộ ứng viên cùng hướng tới một đích duy nhất.
- Cấu trúc `TargetImpactAssessment`:
  - `target_asset_id` (string): Canonical ID của tài sản đích theo Graph Contract 1.3, ví dụ `"S-1-5-21-3623811015-3361044348-30300820-1000"`.
  - `success_event` (string): Sự kiện thành công cụ thể, ví dụ `"domain_controller_full_compromise"`.
  - `rating_status` (string): `"rated"` hoặc `"unrated"`.
  - `consequence_rating` (string hoặc null): Một trong bốn mức hợp lệ khi `rating_status == "rated"`: `"Low"`, `"Medium"`, `"High"`, `"Critical"`.
    Bắt buộc phải là `null` khi `rating_status == "unrated"`.
  - `missing_basis_reasons` (array of strings): Bắt buộc khi `rating_status == "unrated"`, ví dụ `["missing_crown_jewel_assessment", "unrated_target_asset"]`.
  - `business_rationale` (string hoặc null): Giải trình chi tiết về thiệt hại nghiệp vụ nếu đã định mức.
  - `technical_tier_labels` (array of strings): Danh sách các nhãn kỹ thuật thông tin (ví dụ `["Tier0", "DomainController"]`), hoàn toàn không tham gia tính toán trực tiếp vào giá trị `consequence_rating`.
  - `business_value_labels` (array of strings): Danh sách các nhãn giá trị nghiệp vụ (ví dụ `["CrownJewel", "CustomerPII"]`).
  - `rating_provenance` (object hoặc null): Người đánh giá, ngày đánh giá và phiên bản phê duyệt.

**Phân biệt lỗi cú pháp với bằng chứng chưa định mức:**
- Truyền một chuỗi không hợp lệ như `"Tier0"` hoặc `"Level1"` vào trường `consequence_rating` là một lỗi vi phạm hợp đồng dữ liệu (schema validation error, HTTP 400), chứ không phải trạng thái chưa đánh giá hợp lệ.
- Để biểu diễn hợp lệ một tài sản chưa được đánh giá hậu quả, input phải khai báo `rating_status: "unrated"`, `consequence_rating: null` và cung cấp `missing_basis_reasons`.
- Khi đó, ứng viên đạt tới mục tiêu này sẽ được đánh dấu là `impact_unrated` trong phần chẩn đoán với lý do `["impact_unrated"]`.

**Ràng buộc tầm với tài sản đích và sự kiện mục tiêu (Target Asset Reachability & Success Event Binding):**
Định danh `target_asset_id` của ứng viên bắt buộc phải là tài sản thực sự đạt tới thông qua các hành động thực thi thực tế trong tiền tố tại điểm dừng (effective executed actions at termination point) hoặc tài sản bàn đạp ban đầu (`foothold_node_id` khi chuỗi hành động rỗng).
Khi chuỗi hành động thực thi rỗng (ví dụ mục tiêu đạt được ngay tại bước 0 hoặc ứng viên khai báo mảng hành động rỗng), tài sản đích hợp lệ duy nhất là tài sản bàn đạp ban đầu (`foothold_node_id`).
Một hành động không thực thi (ví dụ nằm trong hậu tố bị cắt tỉa hoàn toàn) tuyệt đối không thể làm thay đổi bằng chứng đạt đích ở bước 0.
Do đó, ứng viên khai báo mảng rỗng và ứng viên có toàn bộ hành động bị cắt tỉa đều tuân thủ chính sách nhất quán này và sẽ bị từ chối với `ValueError` nếu `target_asset_id != foothold_node_id`.
Sự hiện diện của một nút trong vết đường cấu trúc (`node_ids` của `structural_routes`) không chứng minh việc đã xâm phạm hoặc đạt tới mục tiêu trên tài sản đó.
Do đó, kiểm tra tầm với tài sản đích không sử dụng các nút trên vết cấu trúc (`route_nodes`).
Nếu hành động nhắm tới `target_asset_id` chỉ nằm trong phần hậu tố bị cắt tỉa (trimmed suffix) mà không xuất hiện trong tiền tố thực thi, ứng viên bị coi là chưa đạt tới tài sản đích và bị từ chối với `ValueError`.
Tuyệt đối cấm gán `target_asset_id` tùy ý cho một tài sản không liên quan để hưởng đánh giá tác động không tương ứng.
Mọi vi phạm về tính đạt tới sẽ bị từ chối với `ValueError`.
Đồng thời, nếu `query_metadata.target_goal` có chỉ định `target_asset_id` hoặc `success_event`, các giá trị này phải khớp tuyệt đối với `target_asset_id` của ứng viên và `success_event` trong `target_impact_assessments`.
Trường `success_event` là bắt buộc phải có mặt và được kiểm tra nghiêm ngặt trong `target_impact_assessments` khi `target_goal` có chỉ định `success_event`.
Tuyệt đối không bỏ qua kiểm tra sự kiện thành công khi bản ghi đánh giá tác động thiếu trường này.

## 3. Đặc tả hợp đồng đầu ra (Output Contract Specification)

Hợp đồng đầu ra `PathRankingResult` phải trả về đầy đủ các trường được phân vùng rõ ràng:

```text
PathRankingResult
├── query_id: Định danh truy vấn được phản hồi
├── version: Phiên bản hợp đồng
├── search_metadata: Thông tin về phạm vi tìm kiếm, số ứng viên, cờ cắt xén
├── eligible_candidates: Danh sách các ứng viên thỏa mãn điều kiện rủi ro
├── pareto_frontier: Danh sách các ứng viên nằm trên biên Pareto bảo thủ
├── diagnostics: Danh sách các ứng viên không đủ điều kiện kèm theo nguyên nhân
└── min_effort_to_da_baseline: Kết quả truy vấn nỗ lực tối thiểu độc lập
```

### 3.1. Thông tin phạm vi và cắt xén (Search Metadata)

- `budget_limit` (integer): Ngân sách đơn vị công việc đã sử dụng.
- `candidates_evaluated` (integer): Tổng số chương trình ứng viên đã duyệt.
- `is_truncated` (boolean): `true` nếu quá trình tìm kiếm bị dừng lại trước khi duyệt toàn bộ không gian trạng thái khả thi; `false` nếu đã duyệt cạn kiệt trong phạm vi.
Khi `is_truncated == true`, hệ thống tuyệt đối không được kết luận là không có đường hoặc biên Pareto là tối ưu toàn cục.
- `truncation_reasons` (array of strings): Danh sách tất cả các lý do cắt xén hoặc chạm điểm dừng:
  - `"work_budget_exceeded"`: Vượt quá ngân sách đơn vị công việc chủ động `active_work_budget`.
  - `"candidate_limit_reached"`: Chạm trần số ứng viên tối đa `max_candidates`.
  - `"timeout_exceeded"`: Quá giới hạn thời gian xử lý `timeout_ms`.
  - `"expansion_limit_reached"`: Chạm trần số bước mở rộng trạng thái `max_expansions`.
  - `"step_limit_reached"`: Chạm trần độ sâu semantic/path `max_steps` do bounded search áp dụng.
  - Mảng rỗng `[]` nếu quá trình tìm kiếm là toàn diện trong phạm vi (`exhaustive_within_scope`).
- `caps_applied` (object): Các giới hạn kiểm soát thực tế đã được áp dụng:
  - `max_active_work_budget` (integer hoặc null).
  - `max_candidates` (integer hoặc null).
  - `max_steps` (integer hoặc null): trần số bước semantic/path của upstream bounded search.
  - `timeout_ms` (integer hoặc null).
  - `max_expansions` (integer hoặc null).
- `completeness_scope` (string):
  - `"exhaustive_within_scope"`: Đã duyệt cạn kiệt không gian trạng thái trong phạm vi ràng buộc.
  - `"budget_bounded"`: Duyệt hết không gian trong ngân sách nhưng bị chặn bởi `active_work_budget`.
  - `"partial_truncated"`: Dừng sớm do chạm trần ứng viên, độ sâu `max_steps`, timeout, giới hạn mở rộng hoặc vượt ngân sách công việc.
  - `"unspecified_subset"`: Tập ứng viên cung cấp đầu vào là một tập con nghiên cứu chưa được chứng minh duyệt cạn kiệt không gian trạng thái.
- `search_algorithm` (string): Thuật toán đã sử dụng, ví dụ `"bounded_candidate_enumerator"`.

**Bảo toàn Caps và Chuẩn hóa Scope khi Cắt xén (Upstream Caps Preservation & Truncation Normalization):**
Khi adapter nhận `upstream_coverage`, các giới hạn kiểm soát thực tế đã được công bố từ upstream (`max_candidates`, `max_steps`, `timeout_ms`, `max_expansions`) phải được bảo toàn nguyên vẹn trong `search_metadata.caps_applied` thay vì bị đặt thành `null`. Nếu upstream dùng tên `max_paths` cho cùng trần số lượng ứng viên hoàn tất, mọi ingress path (API object, raw JSON và CLI `--coverage`) bắt buộc chuẩn hóa tên đó thành `max_candidates` trước khi đi vào hợp đồng ranking; không được xuất đồng thời hai alias. Nếu cả `max_paths` và `max_candidates` cùng xuất hiện với giá trị khác nhau, validation phải fail closed thay vì chọn một giá trị ngầm định.
Khi cờ `is_truncated` mang giá trị `true` (dù do upstream dừng sớm hay do phát hiện ứng viên vượt `active_work_budget` cục bộ), trường `completeness_scope` bắt buộc phải được chuẩn hóa nhất quán thành `"partial_truncated"`.
Tuyệt đối không được giữ nhãn `"exhaustive_within_scope"` hay `"budget_bounded"` khi đã bị cắt xén.
Trường `baseline_coverage` trong `min_effort_to_da_baseline` tiếp tục phản ánh trung thực toàn bộ metadata đã được chuẩn hóa này, bao gồm cùng `caps_applied`.

**Disposition tương thích bounded-search (2026-10-03):**
`step_limit_reached` và `max_steps` là phần mở rộng additive của metadata độ bao phủ cho hợp đồng 1.0.0 nhằm bảo toàn nguyên nhân cắt xén mà engine search #146 đã công bố tường minh. Quyết định này không thay đổi cấu trúc bắt buộc của `PathRankingQuery`, không đổi semantics của Pareto/effort/likelihood và không làm payload 1.0.0 cũ mất hợp lệ; consumer không biết hai giá trị mới vẫn có thể bỏ qua metadata tùy chọn, nhưng producer 1.0.0 khi nhận bounded-search coverage mới bắt buộc phải giữ nguyên chúng. Vì vậy top-level `version` vẫn là `1.0.0`; thay đổi này được xem là clarification/additive interoperability update, không phải thay đổi scoring contract. Refs #146, #155, #167.

### 3.2. Cấu trúc đánh giá ứng viên (Candidate Assessment Structure)

Mỗi ứng viên (dù nằm trong `eligible_candidates` hay `diagnostics`) đều phải có cấu trúc đánh giá nhất quán:
- `candidate_id` (string): Định danh duy nhất của ứng viên.
- `program` (array of strings): Danh sách các `work_unit_id` chủ động duy nhất theo thứ tự thực hiện.
- `transition_lineage` (array of objects, tùy chọn): Vết step-indexed đầy đủ do search adapter cung cấp khi chương trình semantic không bảo đảm là một topology walk liên tục. Mỗi record ràng buộc `step_index`, `action_id`, `technique_id`, actor/source/target, `edge_id` (canonical hoặc null), `derived_from_step`, `origin` và `status=applicable`. Khi trường này hiện diện, record cuối phải đi tới `target_asset_id`; mọi observed edge record phải được cover đúng một lần bởi `structural_routes.action_step_indices`.
- `structural_routes` (array of objects): Danh sách các vết/segment cấu trúc và bằng chứng phân biệt tương ứng với chương trình công việc này:
  - `route_id` (string): Định danh vết đường.
  - `node_ids` (array of strings): Chuỗi các canonical node ID đi qua theo Graph Contract 1.3.
  - `edge_ids` (array of strings): Chuỗi các canonical edge ID đã duyệt theo Graph Contract 1.3 với định dạng bắt buộc `^sha256:[0-9a-f]{64}$`.
  - `provenance_locators` (array of strings): Vị trí bằng chứng thô trong snapshot.
  - `action_step_indices` (array of integers, tùy chọn): Ánh xạ từng observed edge trong segment tới step semantic tương ứng.
  - `semantic_lineage` (array of objects, tùy chọn): Bằng chứng liên kết cho các transition hợp lệ không có canonical edge. Mỗi record phải ràng buộc `step_index`, `action_id`, `technique_id`, actor/source/target, `edge_id: null`, `derived_from_step`, `origin` và trạng thái `applicable`. Với route hoàn toàn semantic (`edge_ids: []`), lineage phải bao phủ mọi bound action theo thứ tự, bắt đầu từ quan hệ có nguồn `initial_attack_state` hoặc từ các transition dẫn xuất hợp lệ, và record cuối phải đi tới `target_asset_id`. Chỉ `action_step_indices: []` không được coi là bằng chứng semantic-only.
- `status` (string): `"feasible"`, `"blocked"`, hoặc `"unknown"`.
- `gates_evaluation` (object): Chi tiết đánh giá từng vị từ, ví dụ `{"directory_write": true, "session": "Unknown"}`.
- `nominal_effort` (integer hoặc null): Tổng nỗ lực quy ước của toàn bộ các đơn vị công việc trong chương trình bất kể trạng thái feasibility.
- `effort` (integer hoặc null): Giá trị nỗ lực hợp lệ để so sánh; bằng `nominal_effort` nếu `status == "feasible"` và tất cả đơn vị công việc đều đã `rated`; bằng `null` khi bị chặn, unknown, hoặc có đơn vị chưa định mức.
- `effort_status` (string): `"rated"`, `"unrated"`, hoặc `"ineligible"` (khi status != feasible).
- `unrated_work_units` (array of strings): Danh sách các đơn vị công việc chưa được định mức.
- `impact` (string hoặc null): Mức hậu quả nghiệp vụ (`"Low"`, `"Medium"`, `"High"`, `"Critical"`) nếu đã định mức; `null` nếu chưa định mức.
- `likelihood_interval` (array of 2 strings hoặc null): Cặp chuỗi số hữu tỷ `[lower, upper]` nếu chương trình `feasible` và đầy đủ căn cứ tiền tố; `null` nếu chương trình bị `blocked`, `unknown`, hoặc thiếu căn cứ xác suất.
- `likelihood_basis_summary` (string): Mô tả nguồn căn cứ của xác suất hoặc lý do withholding do gating.

**Biểu diễn sparse/segmented cho search #146:**
Khi `transition_lineage` không hiện diện, mỗi `structural_routes` tiếp tục tuân thủ dạng legacy: một route liên tục từ foothold tới target. Khi `transition_lineage` hiện diện, observed canonical edges có thể được tách thành nhiều segment nội bộ liên tục vì semantic program của #146 không bảo đảm source của transition kế tiếp bằng target của transition trước. Mỗi segment vẫn phải thỏa `len(node_ids) = len(edge_ids) + 1`, giữ exact edge/provenance, có `action_step_indices` 1-1, và endpoints của từng edge phải khớp record `transition_lineage` tương ứng. Hợp các segment phải cover đúng một lần toàn bộ observed-edge steps; semantic steps được chứng minh bởi lineage và không được gán canonical edge giả.

**Bảo toàn vết cấu trúc và an toàn đồng bộ khi cắt tỉa (Structural Route Preservation & Trimming Sync Safety):**
Theo ADR-0013, các vết đường cấu trúc (`structural_routes`) được tách biệt độc lập khỏi chương trình công việc.
Khi toàn bộ các hành động khai báo ban đầu được giữ nguyên (mục tiêu đạt được tại bước cuối cùng của chuỗi, không có hậu tố bị cắt tỉa), toàn bộ các nút (`node_ids`), cạnh (`edge_ids`) và vị trí bằng chứng (`provenance_locators`) của vết đường cấu trúc bắt buộc phải được bảo toàn nguyên vẹn 100%, tuyệt đối không được cắt xén dựa trên số bước hành động.
Khi một hậu tố hành động thực sự bị cắt tỉa (`len(trimmed_actions) < len(initial_cand_actions)`), việc đồng bộ hóa vết cấu trúc chỉ được thực hiện an toàn khi có ánh xạ 1-1 đã xác thực (verified 1-to-1 mapping) giữa các hành động và vết đường cấu trúc, chứ không chỉ đơn thuần là cùng số lượng (equal cardinality).
Toàn bộ các hành động khai báo ban đầu bắt buộc phải có thuộc tính `edge_id` rõ ràng khớp đúng thứ tự với `edge_ids` trên vết đường, đồng thời vết đường phải cung cấp đầy đủ chuỗi `node_ids` và `provenance_locators`.
Nếu thiếu ánh xạ cạnh, sai lệch thứ tự, hoặc cấu trúc vết đường có số lượng cạnh không khớp 1-1 với số lượng hành động khai báo (ví dụ một hành động tương ứng nhiều cạnh hoặc vết đường chứa các bước chuyển tiếp không gắn hành động), adapter phải từ chối an toàn bằng `ValueError` ("cannot safely synchronize structural_routes upon suffix trimming") để ngăn chặn việc cắt xén sai lệch làm mất mát chứng cứ cấu trúc.

### 3.3. Phân vùng ứng viên và biên Pareto (Eligible, Frontier, Diagnostics)

1. **`eligible_candidates` (map of objects):**
Chỉ chứa các ứng viên có `status == "feasible"`, `impact` hợp lệ thuộc 4 mức đánh giá, và `likelihood_interval` hợp lệ.
2. **`pareto_frontier` (array of strings):**
Danh sách các `candidate_id` thuộc `eligible_candidates` không bị bất kỳ ứng viên eligible nào khác ưu thế theo quy tắc Pareto bảo thủ.
3. **`diagnostics` (map of objects):**
Chứa toàn bộ các ứng viên không thỏa mãn điều kiện rủi ro kèm theo lý do chi tiết:
- `reasons` (array of strings): Danh sách các lý do không đủ điều kiện.
  - Với ứng viên bị `blocked`: Do gating phủ định chặn thực thi, hệ thống withholding phép tính xác suất và nỗ lực hợp lệ, nên lý do chẩn đoán là `["blocked", "likelihood_unrated"]` (kèm thêm `"impact_unrated"` nếu chưa có đánh giá tác động).
  - Với ứng viên bị `unknown`: Do gating thiếu thông tin chặn thực thi, lý do chẩn đoán là `["unknown", "likelihood_unrated"]` (kèm thêm `"impact_unrated"` nếu chưa có đánh giá tác động).
  - Với ứng viên `feasible` nhưng thiếu xác suất tiền tố đầy đủ: Lý do là `["likelihood_unrated"]`.
  - Với ứng viên `feasible` có xác suất nhưng thiếu đánh giá hậu quả: Lý do là `["impact_unrated"]`.
- `assessment` (object): Toàn bộ cấu trúc đánh giá ứng viên như mô tả ở mục 3.2.

### 3.4. Kết quả truy vấn Min-Effort-to-DA riêng biệt (Min-Effort-to-DA Baseline)

Đối tượng độc lập bao gồm:
- `goal_id` (string): ví dụ `"S2"`.
- `best_candidate_id` (string hoặc null): Ứng viên có `effort` nhỏ nhất trong số các ứng viên `feasible` và `effort_status == "rated"`.
- `minimum_effort_value` (integer hoặc null): Giá trị nỗ lực nhỏ nhất.
- `associated_likelihood_interval` (array of 2 strings hoặc null): Khoảng xác suất của ứng viên này (nếu có).
- `associated_impact` (string hoặc null): Mức tác động của ứng viên này.
- `coverage_disclosure` (string): Thông báo rõ về phạm vi: nếu còn ứng viên `unrated` về nỗ lực, kết quả này chỉ là cực tiểu trên tập đã được đánh giá, không phải toàn cục.
- `baseline_coverage` (object): Khai báo coverage cho truy vấn baseline:
  - `is_truncated` (boolean).
  - `truncation_reasons` (array of strings).
  - `completeness_scope` (string).
  - Khi baseline được đánh giá trên cùng tập ứng viên của lượt chạy, `baseline_coverage` phản ánh cùng các giới hạn cắt xén như `search_metadata`.
  - Trường hợp thực hiện truy vấn baseline độc lập với cấu hình caps riêng, metadata này mới mang giá trị phân tách độc lập.

## 4. Hợp đồng độ chính xác số học và tuần tự hóa (Precision & Serialization Contract)

Để đảm bảo tính đúng đắn toán học và khả năng tái lập 100%:
1. **Phân tích đầu vào (Input Parsing):**
Mọi chuỗi số thập phân đầu vào (ví dụ `"0.8"`) phải được chuyển đổi trực tiếp sang đối tượng `Fraction(str(val))` của stdlib Python.
Tuyệt đối không ép kiểu sang `float` trước khi tạo `Fraction` để tránh lỗi sai số nhị phân (ví dụ `0.024` bị biến thành `0.024000000000000004`).
2. **Phép toán khoảng (Interval Arithmetic):**
Tích khoảng được tính bằng phép nhân phân số chính xác:
$$lower = \prod_{i=1}^k Fraction(l_i), \quad upper = \prod_{i=1}^k Fraction(u_i)$$
3. **Phép so sánh ưu thế (Dominance Comparison):**
Phép so sánh bất đẳng thức $l_A \ge u_B$ được thực hiện trực tiếp giữa các đối tượng `Fraction`.
4. **Tuần tự hóa JSON (JSON Serialization):**
Đầu ra JSON phải lưu giữ các giá trị phân số dưới dạng chuỗi không mất mát thông tin:
- Nếu số nguyên: xuất chuỗi số nguyên, ví dụ `"0"`, `"1"`.
- Nếu phân số: xuất chuỗi dạng `"tu_so/mau_so"`, ví dụ `"81/125"`, `"12/25"`.
- Khi đọc lại từ JSON, hệ thống tái tạo bằng `Fraction(val_str)`.
5. **Ranh giới phân tích và bộ chuyển đổi hợp đồng dây truyền (Wire Parsing & Adaptation Boundary):**
Các bản ghi wire contract JSON truyền nhận chuỗi số hữu tỷ (như `"1/10"`, `"12/25"`), mảng prefix danh sách trong `conditional_bounds_table`, và bảng ánh xạ đánh giá hậu quả nghiệp vụ.
Việc truyền trực tiếp các chuỗi phân số này vào các helper tính toán số thực mà không qua adapter chuyển đổi sẽ gây ra lỗi `TypeError`.
Hợp đồng giao diện quy định rõ ràng: Engine hoặc Adapter phía nhận có trách nhiệm decode đầy đủ các chuỗi phân số sang kiểu số hữu tỷ chính xác (`Fraction` hoặc tương đương) trước khi tính toán, và encode trở lại chuỗi phân số hợp lệ khi trả về kết quả.

## 5. Các ví dụ Synthetic chuẩn xác và đầu ra kỳ vọng

Dưới đây là các kịch bản ví dụ synthetic đặc thù được thiết kế làm bộ kiểm thử hành vi (behavioral oracle) để kiểm chứng mọi khía cạnh của hợp đồng giao diện.

### Ví dụ 1: Sự không so sánh được giữa Tác động cao / Xác suất thấp và Tác động thấp / Xác suất cao

**Đầu vào (Inputs):**
- Truy vấn `PathRankingQuery` chứa đánh giá tác động theo từng tài sản đích:
  - `target_impact_assessments`:
    - `"S-1-5-21-3623811015-3361044348-30300820-1000"` (DC): `rating_status: "rated"`, `consequence_rating: "Critical"`.
    - `"S-1-5-21-3623811015-3361044348-30300820-2000"` (Server): `rating_status: "rated"`, `consequence_rating: "High"`.
  - `conditional_bounds_table` (Wire list of objects):
    - `prefix: ["prep_kerberoast"]` -> `lower: "1/10"`, `upper: "2/10"`
    - `prefix: ["prep_kerberoast", "crack_ticket"]` -> `lower: "1/1"`, `upper: "1/1"`
    - `prefix: ["prep_session_hijack"]` -> `lower: "8/10"`, `upper: "9/10"`
    - `prefix: ["prep_session_hijack", "pivot_dc"]` -> `lower: "1/1"`, `upper: "1/1"`
- Candidate A (đạt tới DC):
  - `impact`: `"Critical"`
  - `program`: `["prep_kerberoast", "crack_ticket"]`
  - Tích lũy xác suất: $[1/10 \times 1/1, 2/10 \times 1/1] = [1/10, 2/10] = [0.1, 0.2]$
  - `effort`: 3
- Candidate B (đạt tới Server):
  - `impact`: `"High"`
  - `program`: `["prep_session_hijack", "pivot_dc"]`
  - Tích lũy xác suất: $[8/10 \times 1/1, 9/10 \times 1/1] = [8/10, 9/10] = [0.8, 0.9]$
  - `effort`: 3

**Đầu ra kỳ vọng (Expected Outputs):**
- `scoped_preference(A, B)`: `"incomparable"`
- Giải thích: A thắng về trục Tác động ($Critical > High$), nhưng B thắng về trục Xác suất ($[0.8, 0.9] > [0.1, 0.2]$).
Không có căn cứ tỷ lệ đánh đổi nên hệ thống giữ nguyên tính bất định.
- `pareto_frontier`: `["Candidate_A", "Candidate_B"]` (cả hai cùng xuất hiện trên biên Pareto).

### Ví dụ 2: Ưu thế tuyệt đối (Strict Dominance)

**Đầu vào (Inputs):**
- Candidate A: `impact`: `"Critical"`, `likelihood_interval`: `["1/10", "2/10"]`, `effort`: 3
- Candidate C: `impact`: `"High"`, `likelihood_interval`: `["1/20", "9/100"]` ($[0.05, 0.09]$), `effort`: 2

**Đầu ra kỳ vọng (Expected Outputs):**
- `scoped_preference(A, C)`: `"a"` (A ưu thế C).
- Giải thích: $Critical > High$ và $1/10 \ge 9/100$ ($0.10 \ge 0.09$, cận dưới của A cao hơn hoàn toàn cận trên của C).
A vượt trội trên cả hai trục rủi ro; dù C có nỗ lực nhỏ hơn ($2 < 3$), nỗ lực không thể bù đắp cho rủi ro.
- `pareto_frontier`: Chỉ giữ `"Candidate_A"`, Candidate C bị loại khỏi biên Pareto.

### Ví dụ 3: Điểm trùng xác suất và phân giải tie-break bằng nỗ lực

**Đầu vào (Inputs):**
- Candidate D1: `impact`: `"High"`, `likelihood_interval`: `["6/10", "6/10"]` (Point likelihood P=0.6), `effort`: 3
- Candidate D2: `impact`: `"High"`, `likelihood_interval`: `["6/10", "6/10"]` (Point likelihood P=0.6), `effort`: 5
- Candidate D3: `impact`: `"High"`, `likelihood_interval`: `["6/10", "6/10"]` (Point likelihood P=0.6), `effort`: 3

**Đầu ra kỳ vọng (Expected Outputs):**
- `scoped_preference(D1, D2)`: `"a"` (D1 được xếp trước D2 vì cùng impact, cùng point likelihood và $effort=3 < effort=5$).
- `scoped_preference(D1, D3)`: `"tie"` (Cùng impact, cùng point likelihood và cùng effort=3).
- `pareto_frontier`: Giữ `["Candidate_D1", "Candidate_D3"]` nếu không có ứng viên khác ưu thế; D2 bị loại bỏ.

### Ví dụ 4: Point-tie nhưng nỗ lực chưa được định mức (Unrated Effort)

**Đầu vào (Inputs):**
- Candidate E1: `impact`: `"High"`, `likelihood_interval`: `["6/10", "6/10"]`, `effort`: 3
- Candidate E2: `impact`: `"High"`, `likelihood_interval`: `["6/10", "6/10"]`, `effort`: null (`effort_status == "unrated"`, có 1 work unit chưa có điểm rubric)

**Đầu ra kỳ vọng (Expected Outputs):**
- `scoped_preference(E1, E2)`: `"incomparable"`.
- Giải thích: Vì E2 chưa xác định được nỗ lực, hệ thống không tự tiện gộp hoặc đoán số để hạ E2 xuống; hai ứng viên giữ trạng thái không so sánh được.
- Cả E1 và E2 vẫn đủ điều kiện rủi ro và cùng có thể xuất hiện trên biên Pareto.

### Ví dụ 5: Phân vùng chẩn đoán cho dữ kiện thiếu hoặc bị chặn qua Gate Evaluator

**Đầu vào (Inputs):**
- Candidate F1: Có vị từ bị `False` (đánh giá qua gate evaluator với vị từ phủ định, ví dụ `target_enabled: false`).
- Candidate F2: Có vị từ bị `Unknown` (đánh giá qua gate evaluator với vị từ chưa xác định, ví dụ Gate O missing provenance).
- Candidate F3: Feasible nhưng thiếu khoảng xác suất tiền tố đầy đủ (`conditional_bounds_table` không bao phủ toàn bộ tiền tố).
- Candidate F4: Feasible, có đầy đủ khoảng xác suất, nhưng đánh giá hậu quả đích có `rating_status: "unrated"`, `consequence_rating: null`, kèm `missing_basis_reasons: ["unrated_target_asset"]`.

**Đầu ra kỳ vọng (Expected Outputs):**
- `eligible_candidates`: Rỗng (không có ứng viên nào lọt vào tập eligible).
- `pareto_frontier`: Rỗng.
- `diagnostics`:
  - `F1`: `status: "blocked"`, `likelihood_interval: null`, `effort: null`, `reasons: ["blocked", "likelihood_unrated"]` (gating phủ định withholding tính toán xác suất và nỗ lực).
  - `F2`: `status: "unknown"`, `likelihood_interval: null`, `effort: null`, `reasons: ["unknown", "likelihood_unrated"]` (gating bất định withholding tính toán xác suất và nỗ lực).
  - `F3`: `status: "feasible"`, `likelihood_interval: null`, `effort: 3`, `reasons: ["likelihood_unrated"]`.
  - `F4`: `status: "feasible"`, `likelihood_interval: ["5/10", "6/10"]`, `impact: null`, `effort: 3`, `reasons: ["impact_unrated"]`.
- `scoped_preference(F1, F2)`: `"not_eligible"` (phân biệt tuyệt đối với `incomparable`).
- Mỗi ứng viên vẫn giữ đầy đủ `nominal_effort` để phục vụ kiểm toán quy mô công việc dự kiến.

### Ví dụ 6: Sổ cái công việc chuẩn tắc và đồng nhất hành động tách/gộp

**Đầu vào (Inputs):**
- Program Split: Gồm 2 hành động `reset` rồi `activate`:
  - Packets: `[("unit_reset",), ("unit_activate",)]`
  - Sổ cái: `{"unit_reset": cost 2, "unit_activate": cost 1}`
- Program Merged: Gồm 1 hành động gộp `reset_and_activate`:
  - Packets: `[("unit_reset", "unit_activate")]`
  - Sổ cái: Tham chiếu đúng 2 unit trên, không tạo rubric mới.
- Các khoảng tiền tố xác suất:
  - `("unit_reset",)`: `["8/10", "9/10"]`
  - `("unit_reset", "unit_activate")`: `["6/10", "7/10"]`

**Đầu ra kỳ vọng (Expected Outputs):**
- Cả hai chương trình đều rút gọn về cùng một bộ đơn vị công việc chuẩn tắc: `("unit_reset", "unit_activate")`.
- `nominal_effort` và `effort` của cả hai: $2 + 1 = 3$.
- `likelihood_interval` của cả hai: $[8/10 \times 6/10, 9/10 \times 7/10] = [48/100, 63/100] = [12/25, 63/100]$.
- `scoped_preference(Split, Merged)`: `"incomparable"`.
- Giải thích: Hai khoảng giống nhau nhưng không phải là điểm ($l < u$) không thể chứng minh xác suất ẩn (latent probability) bằng nhau, nên quan hệ giữa chúng là không so sánh được (`incomparable`).
Tuy nhiên, do cả hai có cùng assessment về mặt toán học và không ứng viên nào ưu thế ứng viên kia, cả hai đều cùng xuất hiện trên biên Pareto (`pareto_frontier`), bảo toàn tính tương đương của việc đóng gói (packaging equivalence).

### Ví dụ 7: Tách biệt giữa Min-Effort-to-DA và Biên Pareto

**Đầu vào (Inputs):**
- Scenario S2 có hai ứng viên đạt mục tiêu:
  - Candidate Cheap: `impact`: `"High"`, `likelihood_interval`: `["2/10", "2/10"]`, `effort`: 1.
  - Candidate Shared: `impact`: `"High"`, `likelihood_interval`: `["648/1000", "648/1000"]`, `effort`: 8.

**Đầu ra kỳ vọng (Expected Outputs):**
- Biên Pareto (`pareto_frontier`): Chỉ có `"Candidate_Shared"` (vì cùng impact High nhưng xác suất $0.648 > 0.20$ vượt trội).
- Baseline Min-Effort-to-DA (`min_effort_to_da_baseline`):
  - `best_candidate_id`: `"Candidate_Cheap"`
  - `minimum_effort_value`: 1
  - `associated_likelihood_interval`: `["2/10", "2/10"]`
  - `associated_impact`: `"High"`
- Nhận xét: Candidate Cheap có nỗ lực tối thiểu nhưng bị loại khỏi biên Pareto do xác suất quá thấp.
Hai kết quả tách rời hoàn toàn và không xung đột.

## 6. Ranh giới hợp đồng hành vi và bàn giao kỹ thuật cho TTS B (Behavioral Conformance & Architecture Handoff)

Tại Milestone 3, TTS B chịu trách nhiệm thiết kế và triển khai engine với các nguyên tắc hợp đồng hành vi (behavioral conformance contracts) sau:
1. **TTS B sở hữu thuật toán và triển khai (Engine Implementation Ownership):**
TTS B toàn quyền lựa chọn kiến trúc tìm kiếm, cấu trúc chỉ mục đồ thị, biểu diễn không gian trạng thái và kỹ thuật cắt tỉa phù hợp để đạt hiệu năng trên đồ thị thực tế.
TTS A không áp đặt thuật toán duyệt mẫu (`bounded_programs()` chỉ là research reference harness), cũng không bắt buộc TTS B phải import mã nguồn Python nghiên cứu vào hệ thống sản phẩm.
2. **Hợp đồng kiểm thử và chân lý hành vi (Oracle Conformance):**
Bất kể engine sử dụng thuật toán tìm kiếm nào, kết quả trả về phải vượt qua bộ kiểm thử hợp đồng hành vi:
- Tuân thủ tuyệt đối quy tắc ưu thế Pareto bảo thủ trên khoảng xác suất và mức độ tác động.
- Bảo toàn độ chính xác số hữu tỷ không làm tròn.
- Bảo toàn đầy đủ và riêng biệt các vết đường cấu trúc (`structural_routes`) kèm canonical node/edge IDs và provenance locators.
- Thực thi phân vùng chẩn đoán nghiêm ngặt (`diagnostics`), không để lọt ứng viên thiếu căn cứ hoặc bị chặn vào biên Pareto.
3. **Báo cáo độ bao phủ và cắt xén minh bạch:**
Engine phải cung cấp đầy đủ các chỉ số phạm vi (`search_metadata`) bao gồm toàn bộ lý do cắt xén (`truncation_reasons`), các cap đã áp dụng (`caps_applied`), và phạm vi bao phủ (`completeness_scope`), không được kết luận không có đường khi bị dừng sớm do giới hạn tài nguyên.

### 6.1. Bản ghi tích hợp và ranh giới chuyển dịch chuẩn tắc (Canonical Migration & Scoped Bundle 1.0.0)

Để đảm bảo tính tương thích tuyệt đối giữa hợp đồng giao diện của TTS A và engine chuẩn tắc của TTS B (`src/engine/ranking/`), ranh giới chuyển dịch đã được hiện thực hóa qua Issue #162 và hợp nhất tại PR #163.
1. **Thực thi và giải mã truy vấn chuẩn tắc (Canonical Query Execution & Decoding):**
Engine chuẩn tắc `PathRankingEngine(version="1.0.0")` cung cấp phương thức `evaluate(query_payload, candidates, upstream_coverage=None)` để đánh giá và xếp hạng ứng viên trực tiếp.
Khâu giải mã truy vấn được thực hiện qua `decode_ranking_query(query_payload)`, xác thực nghiêm ngặt cấu trúc `PathRankingQuery` chuẩn tắc.
Hàm chuyển dịch `migrate_wire_payload_to_canonical(...)` tại `scripts/research/path_ranking_wire_adapter.py` hỗ trợ chuyển dịch các payload wire nghiên cứu sang schema chuẩn tắc trước khi nạp vào engine.
Tất cả các tệp fixture đề xuất mới đều mang phiên bản hợp đồng `1.0.0` với đầy đủ các trường kiểm toán và ràng buộc phạm vi.
2. **Chuẩn hóa giá trị trường và danh mục chuẩn tắc:**
Trường `overlap_state` trong sổ cái đơn vị công việc chuẩn tắc bắt buộc thuộc tập giá trị lõi `{"independent", "unresolved_overlap"}`.
Bí danh `distinct_work` trong wire schema nghiên cứu được hàm chuyển dịch tự động chuẩn hóa về `independent`.
Trong danh mục hành động ràng buộc (`bound_actions`), trường định danh kỹ thuật bắt buộc là `technique_name` mang chuỗi không rỗng (ví dụ `"generic_all_user_reset_password"`, `"generic_all_group_add_member"`).
Mỗi ứng viên bắt buộc mang từ điển `scope_binding` gồm đúng 7 trường phạm vi (`query_id`, `scenario_id`, `scenario_version`, `snapshot_id`, `work_boundary`, `horizon`, `foothold_node_id`).
Mọi vết đường cấu trúc (`structural_routes`) giữ nguyên vẹn danh sách các phân đoạn quan hệ cấu trúc (`RouteEdgeSegment`) và mảng con trỏ nguồn gốc thô (`provenance_locators`) có số phần tử khớp 1:1 với số cạnh.
Engine bảo toàn toàn vẹn `parameter_audit` tại gốc kết quả để phục vụ truy xuất nguồn gốc tham số.
3. **Phát hành gói tham số kịch bản có phạm vi 1.0.0 (Scoped Parameter Bundle 1.0.0):**
Toàn bộ căn cứ tham số kịch bản SEAMLESS được đóng gói độc lập tại [seamless_parameter_bundle.json](../../tests/fixtures/ranking/seamless_parameter_bundle.json) với 9 đơn vị công việc chuẩn tắc, 11 câu hỏi tiền tố có điều kiện, 25 giả thiết runtime, và 3 ứng viên hợp lệ.
Mọi phép tính toán phân tích và kiểm thử độ nhạy đều được kiểm chứng tự động qua `scripts/research/seamless_parameter_validation.py`.

