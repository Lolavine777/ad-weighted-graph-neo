# Proposed target impact equivalence decision

- Phiên bản: 1.0.0.
- Ngày: 2026-10-09.
- Trạng thái: Proposed / pending B review; không phải disposition accepted.
- Người đề xuất: TTS A @Lolavine777; reviewer được yêu cầu: TTS B @nairyuuu.
- Refs #249, parent #245; consume merged #246; public integration thuộc #250.

## Source historical basis

[Accepted Week 3 source](../week3-closeout/reviewed-release.json) giữ nguyên bytes, scope và review/provenance lịch sử.
Source I gắn asset `S-1-5-21-1271839998-3495686680-2211690266-1000` và event `terminal_compromise_seamless_dc` với High trong enterprise scenario được khai báo.
Business rationale nói khả năng can thiệp dữ liệu định danh và kiểm soát truy cập; không phải observed theft, empirical loss hoặc xác nhận đã chiếm krbtgt.
Source pair digest `sha256:553ca894c710580be597b747ff95e05e869246f419af5d7afbd52e32394377df` và full canonical release digest được pin trong registry mới.
Provider phải có source packet matching asset/event, rated consequence và immutable release digest; registry không tự chứng nhận source basis.

## Actual frozen #243 binding

[Freeze](../../scenarios/week4-seamless-v1.json) định nghĩa goal `admin_control(C0)` và bốn active operations request/recovery/activation/host-admin.
Manifest-verified locator `#/computers/0` xác nhận C0 trùng asset của Week 3.
`obtain_admin_execution_on_host` dùng abstraction `admin_channel`; không tự suy WinRM, secret extraction hoặc full DC compromise rộng hơn effect đã định nghĩa.
DA checkpoint `effective_member(V_A,G_DA)` riêng, false trong actual frozen program; không quyết định I.

Authoritative spelling hiện có trong `scripts/research/credential_bindings.py` là `admin_execution_on_C`.
Registry match event này trực tiếp; không tạo alias normalization rải rác và không đổi semantics #243.
Mapping mới directional từ Week 3 source tới event này, yêu cầu scenario `week4-seamless-v1`, same snapshot, intra_forest, goal ID `admin_control(C0)` và terminal predicate `admin` biểu diễn frozen asset state.
Các spelling cũ `admin_control_c0`, `admin_control_seamless_dc`, `terminal_compromise` vẫn là proposals riêng với explicit predicate applicability; chúng không được trình bày là actual #243 event.
Nếu #250 chọn binding khác hoặc không có declared terminal state tương đương, provider từ chối; không đổi freeze để khớp registry.

## Proposed horizon and consequence policy

Mapping khai báo `horizon_policy=independent_of_recovery_horizon`.
I là severity của hậu quả đạt được trên cùng asset trong same snapshot/scenario; không phải xác suất hoàn tất trong recovery window.
Recovery horizon `fixed-snapshot-window` và budget `unmeasured-budget` của #243 giữ nguyên.
Week 3 execution policy 24h vẫn là source lịch sử, không ép thành applicability mới cho mọi consequence equivalence.
Đây là đề xuất mở rộng applicability cần B review, không tự nhận source đã accepted ngoài original scope.
Provider vẫn hỗ trợ explicit operational_horizon restriction nếu một disposition reviewed khác thật sự yêu cầu nó.

## Governance and fail-closed behavior

Registry/mappings đều `proposed_pending_b_review`; không có fabricated reviewed_at hoặc B signature.
Pending mapping trả REFUSED/PREREQUISITE_GATE_REFUSAL, value null; không bị provider khác che bằng fallback.
Sau B disposition, từng mapping có thể chuyển reviewed với review reference chính xác và source pins nguyên vẹn.
Accepted simulation trong unit/resolver tests dùng `synthetic_test_only`; không phải review của numeric production registry.
Provider không tự load/register registry; caller phải cung cấp explicit registry/provider.
Exact explicit packet giữ precedence trong scope accepted của nó.
Same asset/different consequence, different asset, stale/missing scope, source mismatch và conflicting mappings không reuse tự động.
Không bắc cầu A-B-C; không derive từ DA/Tier0/CrownJewel label và không đổi ordinal thành tiền hoặc probability.

## Verification boundary

Real #243 probe consume frozen specification, verified raw và genuine public-generated PathResult; structural provenance giữ nguyên, non-structural actions không được gán edge giả.
Actual production proposal trả explicit refused/unrated I; accepted-test disposition chứng minh cơ chế có thể resolve High mà không đổi recovery horizon.
Coverage-only ranking budget 0 không claim eligible public ranking và không thay nonnumeric recovery budget.
Các handcrafted candidate/stub C/P tests chỉ isolate I provider và resolver; không phải generated risk-case hoặc #251 acceptance.
Generated risk-comparison I basis vẫn cần B disposition và exact scenario applicability; không tự nhận High accepted cho future case.
#250 public query/CLI integration và #251 release proof còn riêng.
