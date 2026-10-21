# Quy chuẩn các lớp đơn vị công việc và Rubric công sức (Proposed Work-Unit Classes Specification v1.0.0)

- Ngày: 2026-10-09.
- Nhiệm vụ: Issue #247 (P0 rating effort provider / C rubric generalization), trực thuộc release blocker #245.
- Trách nhiệm nghiệp vụ / provenance / rubric: TTS A (@Lolavine777).
- Người rà soát đề xuất / reviewer: TTS B (@nairyuuu).
- Bản ghi JSON chuẩn tắc: `docs/research/ratings/week4/reviewed-work-unit-classes.json`.
- Tham chiếu: Issue #245, Issue #246, ADR-0013, Week 3 Reviewed Release, Week 4 Scoring Handoff.

## 1. Mục tiêu và phạm vi chuẩn hóa

Trong các đợt phát hành trước (Tuần 3 và synthetic Tuần 4), các giá trị công sức ($C$) được khai báo trực tiếp trên từng thể hiện đơn vị công việc (instance-specific work unit).
Cách tiếp cận này khiến mỗi kịch bản mới phải khai báo thủ công lại toàn bộ rubric $T_1$ và $T_2$, thiếu tính tái sử dụng và tiềm ẩn nguy cơ mâu thuẫn điểm số giữa các bước tương đương.
Issue #247 chuẩn hóa rubric tính công sức thành các **Lớp đơn vị công việc đề xuất, pending B review** (Reviewed Work-Unit Classes) có phạm vi áp dụng xác định (scoped applicability).
Các lớp này được hiện thực hóa qua `ReviewedWorkUnitClassEffortProvider` tuân thủ giao thức `EffortRatingProvider` được tiêu thụ trực tiếp bởi `RatingResolver` (Issue #246).

### Các nguyên tắc ranh giới bất biến (Boundary Invariants)
1. Giữ nguyên vẹn thuật toán tìm kiếm đa đồ thị, `AttackState`, semantic replay, công thức tích chuỗi $P = \prod q_i$, biên Pareto bảo thủ và bộ đánh giá chuẩn tắc `PathRankingEngine`.
2. Giữ nguyên vẹn 21 tham số đã được phê duyệt của đợt bàn giao Tuần 3 và oracle ngữ nghĩa của Issue #243.
3. Tuyệt đối không dùng trọng số cấu trúc đơn vị (`unit` $W=1.0$) hoặc profile lịch sử `maut_v1` làm số mặc định khi thiếu dữ liệu định mức.
4. Áp dụng cơ chế fail-closed chặt chẽ: khi kỹ thuật chưa được duyệt, bối cảnh vượt ranh giới bảo mật, hoặc dữ liệu chồng lấn chưa giải quyết, resolver phải từ chối hoặc trả về unrated có lý do chẩn đoán rõ ràng.

## 2. Quy chuẩn Rubric số nguyên chuẩn tắc (Exact Integer Rubric)

Mọi lớp đơn vị công việc trong danh mục đều tuân thủ nghiêm ngặt chuẩn mực số nguyên:
- Điểm độ phức tạp kỹ thuật và công cụ: $T_1 \in \{1, 2, 3\}$.
- Điểm ma sát phòng thủ và thiết lập môi trường: $T_2 \in \{1, 2, 3\}$.
- Công thức tính toán: duy nhất và nghiêm ngặt `"base"`.
- Chi phí công sức chuẩn hóa: $C = T_1 + T_2 - 2$, với giá trị thuộc tập số nguyên chính xác $C \in \{0, 1, 2, 3, 4\}$.

### Ý nghĩa các mức đánh giá thành phần
- **Thang điểm $T_1$ (Tooling & Technical Complexity):**
  - $T_1 = 1$: Sử dụng các giao thức, API chuẩn của hệ điều hành hoặc công cụ quản trị mặc định (PowerShell, SAMR RPC, LDAP query, kinit, Kerberos standard exchange).
  - $T_1 = 2$: Đòi hỏi công cụ chuyên dụng của bên thứ ba, kỹ thuật khai thác đặc thù (Hashcat, John the Ripper, Rubeus, Impacket, thao tác ACL nhị phân).
  - $T_1 = 3$: Khai thác lỗ hổng phức tạp, kỹ thuật vượt qua cơ chế phòng thủ chuyên sâu hoặc bypass cô lập đặc quyền cao.

- **Thang điểm $T_2$ (Operational Friction & Defense Posture):**
  - $T_2 = 1$: Thao tác tức thời (instantaneous), một lần trao đổi duy nhất (single round-trip), ma sát giám sát thấp.
  - $T_2 = 2$: Phiên làm việc đa bước (multi-step authenticated session), đòi hỏi ghi dữ liệu vào thư mục Active Directory, cấp phát tài nguyên tính toán hoặc quota phiên.
  - $T_2 = 3$: Ma sát phòng thủ chủ động cao, giám sát EDR nghiêm ngặt trên máy chủ đích, nguy cơ cảnh báo và ngắt kết nối lớn.

## 3. Cơ chế phân loại công việc và Chống đếm trùng (Anti-Double-Counting)

Để ngăn ngừa việc thổi phồng hoặc bóp méo chi phí thực thi, hệ thống phân định rõ ba loại công việc:

### 3.1. Đơn vị công việc chủ động (Active Work Units)
- Đại diện cho khối lượng công việc thực sự gây ra ma sát và đòi hỏi chi phí nỗ lực của kẻ tấn công.
- Được gán chi phí $C \in \{0, 1, 2, 3, 4\}$ theo rubric của lớp công việc tương ứng.
- Khi nhiều bước độc lập được thực thi trong một chương trình, tổng công sức là tổng các chi phí của các đơn vị phân biệt: $C(\text{program}) = \sum_{u \in \text{distinct}(units)} C(u)$.

### 3.2. Bao đóng thụ động (Passive Closure)
- Các bước suy diễn quyền hạn tự nhiên theo đồ thị bảo mật, chẳng hạn `propagate_group_entitlement`.
- Không tạo ra bất kỳ đơn vị công việc nào trong sổ cái `work_units_ledger` (`referenced_work_unit_ids: []`).
- Không làm tăng chi phí công sức nhân tạo và không tạo q event.

### 3.3. Chuẩn bị kiên trì dùng chung (Shared Persistent Preparation)
- Các thao tác chuẩn bị tạo ra năng lực hoặc ngữ cảnh xác thực được duy trì lâu dài (ví dụ: `class_shared_auth_preparation` / `w-auth-context`).
- Khi một chương trình có nhiều hành động cùng chia sẻ ngữ cảnh xác thực trên cùng một đích, các hành động này cùng tham chiếu tới một ID đơn vị công việc duy nhất.
- Đơn vị công việc này chỉ xuất hiện một lần trong sổ cái và chi phí chỉ được cộng đúng một lần vào tổng nỗ lực của chương trình.

### 3.4. Bảo toàn độc lập ngữ cảnh (Contextual Independence)
- Hai thao tác giống nhau về kỹ thuật nhưng thực thi trên hai máy đích khác nhau (ví dụ xác thực tới Host A so với Host B) đại diện cho hai ngữ cảnh độc lập.
- Hai đơn vị này được cấp hai định danh riêng biệt và được tính đủ chi phí độc lập, đảm bảo nguyên tắc $1 + 1 = 2$.

## 4. Danh mục 23 Lớp đơn vị công việc đề xuất (Registry Catalog)

Dưới đây là danh mục chi tiết 23 lớp đơn vị công việc được chuẩn hóa trong bản phát hành Week 4:

| STT | Class ID | Tên nghiệp vụ | $T_1$ | $T_2$ | Chi phí $C$ | Kỹ thuật áp dụng | Nguồn gốc / Luận cứ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `class_ad_password_reset_samr` | Đặt lại mật khẩu qua SAMR/LDAP | 1 | 2 | 1 | `reset_password`, `genericall_reset_password`, `reset_target_password`, `scenario_reset_password` | Tuần 3 SEAMLESS (`WU_RESET_*`). Kết nối RPC/LDAP xác thực, kiểm tra chính sách mật khẩu và ghi thư mục. |
| 2 | `class_kerberos_ticket_acquisition` | Xin vé Kerberos TGT / TGS | 1 | 1 | 0 | `acquire_ticket`, `acquire_reset_identity` | Tuần 3 SEAMLESS (`WU_ACTIVATE_*`). Trao đổi KDC chuẩn một vòng, tự động hóa hoàn toàn. |
| 3 | `class_winrm_host_admin` | Quản trị máy chủ qua WinRM | 1 | 2 | 1 | `remote_exec_winrm`, `open_winrm_remote_session`, `scenario_winrm_admin`, `obtain_admin_execution_on_host` (winrm) | Tuần 3 SEAMLESS và #243 AS-REP. Thiết lập phiên PowerShell từ xa, đàm phán quota và thực thi lệnh. |
| 4 | `class_shared_auth_preparation` | Chuẩn bị ngữ cảnh xác thực dùng chung | 1 | 2 | 1 | `auth_context`, `shared_preparation`, `w-auth-context` | Tuần 4 Fixture A2 (`w-auth-context`). Thiết lập kênh xác thực ban đầu, lưu trữ token tái sử dụng. |
| 5 | `class_direct_host_admin_execution` | Quản trị máy chủ trực tiếp (ma sát cao) | 3 | 3 | 4 | `obtain_admin_execution_on_host` (direct) | Tuần 4 Fixture A2 (`w-direct-admin`). Leo thang đặc quyền trực tiếp đối mặt giám sát EDR phòng thủ chủ động. |
| 6 | `class_inherited_host_admin_execution` | Quản trị máy chủ kế thừa qua nhóm | 1 | 2 | 1 | `obtain_admin_execution_on_host` (inherited) | Tuần 4 Fixture A2 (`w-inherited-admin`). Thực thi quản trị tận dụng quyền thành viên nhóm sẵn có, ma sát thấp. |
| 7 | `class_asrep_request` | Yêu cầu AS-REP Roasting | 1 | 1 | 0 | `asrep_request` | Đóng băng #243 AS-REP. Yêu cầu AS-REQ không cần xác thực trước (DoNotRequirePreAuth). |
| 8 | `class_asrep_offline_crack` | Bẻ khóa ngoại tuyến AS-REP | 2 | 2 | 2 | `recover_asrep_secret` | Đóng băng #243 AS-REP. Bẻ khóa mật khẩu ngoại tuyến bằng công cụ chuyên dụng (Hashcat/John). |
| 9 | `class_kerberos_identity_activation` | Kích hoạt định danh Kerberos phục hồi | 1 | 1 | 0 | `activate_recovered_identity` | Đóng băng #243 AS-REP / Kerberoasting. Xác thực định danh đã khôi phục vào phiên làm việc. |
| 10 | `class_kerberoast_request` | Yêu cầu vé Kerberoasting (TGS) | 1 | 1 | 0 | `kerberoast_request` | Kerberoasting baseline. Liệt kê SPN tài khoản dịch vụ và yêu cầu vé dịch vụ TGS. |
| 11 | `class_kerberoast_offline_crack` | Bẻ khóa ngoại tuyến vé Kerberoast | 2 | 2 | 2 | `recover_ticket_secret` | Kerberoasting (#246 Worked Example 2). Bẻ khóa ngoại tuyến vé dịch vụ bằng hạ tầng tính toán. |
| 12 | `class_rbcd_acquire_secret` | Chiếm giữ bí mật trung gian RBCD | 1 | 2 | 1 | `rbcd_acquire_secret` | RBCD Bước 1 (#229). Chiếm đoạt hoặc thiết lập tài khoản máy tính trung gian phục vụ ủy thác. |
| 13 | `class_rbcd_prepare_service` | Chuẩn bị dịch vụ cho RBCD | 1 | 1 | 0 | `rbcd_prepare_service` | RBCD Bước 2 (#229). Kiểm tra và đăng ký SPN cho tài khoản dịch vụ được ủy quyền. |
| 14 | `class_rbcd_configure_descriptor` | Cấu hình Security Descriptor RBCD | 2 | 2 | 2 | `rbcd_configure_descriptor` | RBCD Bước 3 (#229). Ghi thuộc tính msDS-AllowedToActOnBehalfOfOtherIdentity vào máy chủ đích qua LDAP. |
| 15 | `class_rbcd_delegate_service` | Thực hiện ủy thác Kerberos S4U | 2 | 2 | 2 | `rbcd_delegate_service` | RBCD Bước 4 (#229). Trao đổi mở rộng Kerberos S4U2self và S4U2proxy để lấy vé mạo danh. |
| 16 | `class_rbcd_service_admin` | Quản trị máy chủ qua vé ủy thác | 1 | 2 | 1 | `rbcd_service_admin` | RBCD Bước 5 (#229). Kết nối dịch vụ quản trị trên máy chủ đích bằng vé ủy thác đã nhận. |
| 17 | `class_ad_group_membership_add` | Thêm thành viên vào nhóm bảo mật AD | 1 | 2 | 1 | `genericall_add_member` | Semantics catalog. Thao tác ghi thư mục LDAP thêm đối tượng vào nhóm bảo mật đặc quyền. |
| 18 | `class_ad_dacl_mutation` | Sửa đổi danh sách kiểm soát truy cập (DACL) | 2 | 2 | 2 | `genericall_grant_write_dacl`, `grant_new_object_right` | Semantics catalog. Xây dựng cấu trúc ACE nhị phân và cập nhật DACL trên Active Directory. |
| 19 | `class_rdp_remote_interactive` | Mở phiên tương tác đồ họa từ xa (RDP) | 1 | 2 | 1 | `open_remote_interactive_session` | Semantics catalog. Đàm phán xác thực NLA và khởi tạo phiên tương tác màn hình từ xa. |
| 20 | `class_lsass_credential_dump` | Trích xuất bộ nhớ tiến trình LSASS | 2 | 2 | 2 | `recover_session_credential_material` | Semantics catalog. Trích xuất mật khẩu hoặc vé từ tiến trình LSASS trên máy chủ bị chiếm quyền. |
| 21 | `class_unconstrained_delegation_abuse` | Lạm dụng ủy thác không ràng buộc | - | - | Unrated | `unconstrained_delegation_abuse` | Thiếu dữ liệu đo đạc thực nghiệm về thời gian và rủi ro. Khai báo unrated tường minh. |
| 22 | `class_cross_forest_trust_hop` | Nhảy ranh giới ủy thác liên rừng | - | - | Refused | `cross_forest_trust_hop` | Vượt ngoài ranh giới nội bộ rừng (intra_forest). Từ chối đánh giá fail-closed. |

## 5. Bảng ma trận quyết định và Hành vi Fail-Closed

`ReviewedWorkUnitClassEffortProvider` tuân thủ nghiêm ngặt ma trận quyết định đóng lỗi:

1. **Dữ liệu chồng lấn chưa giải quyết (`overlap_state == "unresolved_overlap"`):**
   - Trạng thái trả về: `ResolverDisposition.UNRATED`.
   - Mã lý do: `ReasonCode.EXPLICIT_UNRATED_DISPOSITION`.
   - Ý nghĩa: Không thể gán chi phí công sức độc lập khi chưa giải tỏa chồng lấn ma sát.

2. **Vi phạm ranh giới bảo mật (ví dụ ranh giới không thuộc `intra_forest` được duyệt):**
   - Trạng thái trả về: `ResolverDisposition.REFUSED`.
   - Mã lý do: `ReasonCode.OUT_OF_SCOPE`.
   - Ý nghĩa: Bảo toàn tính toàn vẹn từ chối (refusal integrity); dừng chuỗi provider lập tức.

3. **Kỹ thuật không có trong danh mục được duyệt:**
   - Trạng thái trả về: `ResolverDisposition.UNSUPPORTED`.
   - Mã lý do: `ReasonCode.UNSUPPORTED_TECHNIQUE`.
   - Ý nghĩa: Báo cáo rõ kỹ thuật chưa có định mức, cho phép chuyển tiếp kiểm tra provider khác.

4. **Xung đột giữa nhiều lớp phù hợp:**
   - Trạng thái trả về: `ResolverDisposition.CONFLICTING`.
   - Mã lý do: `ReasonCode.CONFLICTING_PROVIDER_BASIS`.
   - Ý nghĩa: Tuyệt đối không tự ý lấy trung bình hoặc chọn ngẫu nhiên; dừng chuỗi và báo lỗi.

5. **Lớp unrated được khai báo tường minh:**
   - Trạng thái trả về: `ResolverDisposition.UNRATED`.
   - Mã lý do: `ReasonCode.MISSING_EVIDENCE`.
   - Ý nghĩa: Giữ nguyên trạng thái chưa có bằng chứng số học, cách ly fail-closed.

## 6. Tích hợp và Tiêu thụ bởi RatingResolver

Nhà phát triển tích hợp `ReviewedWorkUnitClassEffortProvider` vào `RatingResolver` thông qua chuỗi provider:

```python
from src.engine.ranking.resolver import (
    RatingResolver,
    ReviewedWorkUnitClassEffortProvider,
)

from src.engine.ranking.effort_registry import get_default_work_unit_registry

provider = ReviewedWorkUnitClassEffortProvider(get_default_work_unit_registry())
resolver = RatingResolver(effort_providers=[provider])
output = resolver.resolve(candidates, query_scope)
```

Gói tin đầu ra chứa đầy đủ `computed_cost`, `rubric_scores`, và `rating_audit` sẵn sàng nạp thẳng vào `PathRankingEngine.evaluate()`.
Không có bất kỳ trường fallback nào chứa trọng số cấu trúc $W=1.0$ hoặc profile `maut_v1`.
Mọi định danh công việc và điểm số đều được kiểm toán độc lập và lưu trữ vết nguồn gốc hoàn chỉnh.

## Amendment 2026-10-09: review gate và semantic matching

Toàn bộ generalization mới là proposed / pending B review, kể cả lớp lấy điểm từ Week 3.
Nguồn historical accepted vẫn là `docs/research/ratings/week3-closeout/reviewed-release.json`; không thay bytes hoặc mở rộng scope accepted của nguồn đó.
Provider không tự đăng ký catalog và không xuất numeric rating cho lớp pending.
Disposition accepted phải được cung cấp tường minh với review reference sau B review.
Tests dùng bản sao synthetic test only để chứng minh cơ chế consume disposition accepted, không phải B acceptance của catalog.

`class_host_admin_channel` đề xuất T1=1/T2=2/C=1 cho abstraction admin_channel transport-unspecified của #243.
Không suy WinRM hay EDR friction từ actor/source.
Direct/inherited C=4/1 chỉ tự suy từ source trong scenario synthetic-a2; method direct/inherited/WinRM tường minh là context riêng.
Shared preparation match classification riêng; alias không override technique.
Nhiều class match luôn CONFLICTING, kể cả khi numeric cost giống nhau.

Probe #243 dùng frozen specification, manifest-verified raw, public query và real PathResult; recovery horizon fixed-snapshot-window giữ nguyên.
Ranking budget 0 chỉ dành cho coverage probe không đánh giá eligibility, không thay recovery budget unmeasured-budget của freeze.
Expected C dưới disposition accepted mô phỏng là [0,2,0,1]; production catalog pending nên C vẫn unrated.
Generated two-routes Min-Effort probe có shared preparation C=1, direct C=4 và inherited C=1; winner C=2 so với C=5.
Passive closure không có active work unit và không có q event.
Đây là provider/resolver/generated-flow verification; public CLI integration #250 vẫn riêng.
