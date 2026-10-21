# Predictive state transitions cho Attack Semantics

Trạng thái: **Research decision proposal cho #174; chưa phải implementation contract**.  
Refs: #58, #70, #145, #174, #180, PR #173, ADR-0008.  
Mục tiêu: chốt abstraction tối thiểu để path prediction giải thích được chuỗi từ quyền kiểm soát identity tới hành động trên host mà không biến engine thành Kerberos simulator hoặc detection engine.

## 1. Decision summary

Đề xuất mặc định là **layered capability model**:

```text
structural fact
  -> semantic transition
  -> attacker capability state
  -> candidate transition
  -> path search
  -> whole-path evaluator/ranking
```

State vocabulary khái niệm tối thiểu cần cho nhánh authentication:

```text
AccountControl(principal)
RecoverableAuthMaterial(principal, kind, acquisition_context)   # pre-secret material
CredentialPossession(principal, form)                           # auth-usable secret/material
UsableIdentity(principal, authentication_context)               # scoped actor capability
HostExecution(host, privilege)                                  # conceptual umbrella only
```

Trong đó:

- `RecoverableAuthMaterial` là **pre-secret acquisition material** như AS-REP/Kerberoast ciphertext có thể đem đi recovery/crack. Nó chưa phải password/hash/key dùng để xác thực và **không được actor-switch**. Đây là vocabulary khái niệm cho Week 4; current `AttackState` chưa có bucket typed tương ứng.
- `CredentialPossession` mô tả attacker đã nắm material **đủ dùng cho một authentication attempt**, ví dụ password, NT hash, Kerberos key hoặc ticket đã thu được. Roast response chỉ trở thành `CredentialPossession` sau một transition recovery thành công và có provenance/basis phù hợp.
- `UsableIdentity(principal, authentication_context)` là capability **có scope**. `authentication_context` là opaque scenario/runtime scope hiện được giữ bởi `RuntimeContext.authentication_context` (Week 3 thường dùng target host/context), không phải synonym của Kerberos/NTLM. Capability này không có nghĩa đăng nhập chắc chắn thành công vào mọi target; transition tiếp theo vẫn kiểm tra target/service-specific predicates.
- `HostExecution(host, privilege)` chỉ là **conceptual umbrella** để nói về execution capability trong research. Current implementation vẫn giữ `admin_control`, `remote_command_execution` và `interactive_session` riêng; không collapse chúng thành một bucket trong #174.
- Principal tiếp tục dùng canonical identity hiện hành. Local identity phải giữ host scope theo identity contract; không làm phẳng local account thành domain-wide identity.

### Compatibility rule với engine hiện hành

Normative scope của identity là `UsableIdentity(principal, authentication_context)`. Mọi chỗ viết rút gọn `UsableIdentity(principal)` trong discussion cũ chỉ là shorthand, **không** cho phép bỏ dimension `authentication_context`.

Current engine representation vẫn authoritative:

```python
usable_identity: frozenset[tuple[str, str]]
# element = (principal_id, authentication_context)
```

Evaluator chỉ coi actor authenticated khi đúng tuple `(actor, RuntimeContext.authentication_context)` tồn tại. Search/membership closure cũng chỉ dùng usable identity có context khớp. Vì vậy actor switching không bao giờ biến một identity acquired cho context A thành global actor capability cho context B.

### Quyết định về `acquire_ticket`

`acquire_ticket` **không là persistent semantic state và không là transition bắt buộc của mọi lateral-movement path**.

Trong semantics, bridge mặc định là một **derived state operation**:

```text
CredentialPossession(user, form)
        |
        v
activate_identity(user, authentication_context)
        |
        v
UsableIdentity(user, authentication_context)
```

`activate_identity` là normalization step của semantic engine, không khẳng định rằng ngoài đời luôn tồn tại đúng một network action cùng tên. Kerberos AS/TGS exchange, NTLM negotiation hoặc reuse token/session là cơ chế cụ thể nằm dưới abstraction này.

Để bảo toàn provenance của Week 3, work-unit ID `acquire_ticket` trong PR #173/release/rating artifacts **được giữ nguyên như compatibility/ranking alias**. Không rewrite lịch sử rating. Mapping được document như sau:

```text
ranking work unit "acquire_ticket"
    -> semantic owner: activate_identity / authentication-capability activation
    -> no persistent has_tgt/has_service_ticket requirement in default state
```

Nếu một technique tương lai thực sự phụ thuộc artifact cụ thể, ví dụ pass-the-ticket hoặc delegation research, catalog có thể dùng một `CredentialPossession(..., form=ticket)` specialization. Artifact-specific state không trở thành prerequisite toàn cục cho remote execution.

## 2. Vì sao không materialize TGT/service ticket mặc định

Ba abstraction được xem xét:

| Option | Ưu điểm | Vấn đề | Disposition |
| --- | --- | --- | --- |
| A. `has_tgt` / `has_service_ticket` | Fidelity cao cho Kerberos-specific technique | Protocol coupling, state explosion theo principal × service/host, làm NTLM/session paths khó biểu diễn | Không dùng làm default |
| B. Một `usable_authentication_context` duy nhất | Nhỏ, protocol-neutral | Dễ che mất distinction giữa material và actor capability | Dùng ý tưởng nhưng tách 2 tier |
| C. Không có intermediate capability | State nhỏ nhất | Tạo magic jump từ account/object control sang host action; audit kém | Bác bỏ |
| D. `CredentialPossession -> UsableIdentity(principal, authentication_context)` | Giữ được bridge cần cho prediction, protocol-neutral, audit được và giữ scope hiện hành | Cần target-specific predicates ở bước sau | **Chọn** |

Độ chi tiết mặc định phải dừng ở mức mà path applicability cần. RFC/MS-KILE protocol state không được kéo vào `AttackState` nếu không làm thay đổi quyết định applicability của use case.

## 3. Technical corrections so với bản research dài ban đầu

Các điểm sau là normative cho quyết định #174 và supersede wording rộng hơn trong bản nháp deep-research:

1. **Administrative password reset không yêu cầu target account đang enabled.** Microsoft [MS-ADTS `unicodePwd`](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6e803168-f140-4d23-b2d3-c3a8ab5917d2) quy định reset thành công dựa trên `User-Force-Change-Password` control access right. Trạng thái disabled/expired/logon-hours thuộc bước dùng identity, không phải blanket veto cho thao tác reset.
2. **`WriteDacl` không phải direct reset evidence.** `WriteDacl` có thể cho phép một transition sửa ACL, từ đó sinh capability/right mới trong derived scenario state. Phải có transition ACL-modification riêng; không gộp `WriteDacl -> reset_password` thành một bước.
3. **`adminCount=1` / AdminSDHolder không phải blanket reset blocker.** Protected-object behavior có thể ảnh hưởng việc ACL bị kế thừa/ghi đè, nhưng không chứng minh một `User-Force-Change-Password` right hiện hữu là unusable.
4. **Remote Management Users không đồng nghĩa local administrator.** Output privilege của WinRM transition phải dựa trên effective endpoint/token authorization hoặc explicit scenario predicate; nếu chỉ chứng minh remote session thì không được emit `HostExecution(..., local_admin)`.
5. **RDP deny-right không được dùng như alias cho WinRM denial.** WinRM cần predicate riêng về listener/service/network, authentication acceptance và endpoint/session-configuration authorization.
6. **Không có invariant "mọi path nằm trong 10 giờ".** Kerberos ticket lifetime có policy và account-specific variation; password/hash/token capability cũng không có cùng lifetime. Core semantics không model timestamp mặc định; horizon/retry/deadline của Week 3 tiếp tục thuộc scenario/evaluator contract. Microsoft documentation cho phép TGT lifetime được điều chỉnh bằng domain/authentication policy, vì vậy 10 giờ không phải semantic constant.
7. **Telemetry/event IDs không tạo numeric detection weight.** Event mapping có thể là evidence feature cho evaluator/calibration, nhưng probability/detection penalty chỉ được gán khi có model/evidence được accept.

## 4. Canonical concept taxonomy

| Concept | Owner | Ý nghĩa |
| --- | --- | --- |
| Structural fact | Canonical graph/snapshot | Quan hệ/thuộc tính có provenance từ snapshot |
| Initial attacker state | Scenario | Capability ban đầu được khai báo |
| Runtime/scenario assumption | RuntimeContext | Điều snapshot không chứng minh nhưng scenario cho phép giả định tường minh |
| Predicted action | Attack Semantics | Transition được xem xét |
| Resulting attacker state | AttackState | Capability derived sau transition applicable |
| Observed telemetry | Telemetry/evaluation | Bằng chứng runtime quan sát được; không là prerequisite bắt buộc của prediction |
| Likelihood/cost/duration/risk | Whole-path evaluator | Quantity dùng ranking, không do semantics tự invent |

Invariant:

```text
Structural fact != successful attack step
Observed telemetry != required proof that a predicted transition may occur
Runtime assumption != structural evidence
Derived attacker state != mutation of canonical snapshot
```

## 5. State-transition matrix

### 5.1. `reset_password(target, actor)`

| Field | Decision |
| --- | --- |
| Structural evidence | Direct `ForceChangePassword(actor, target)`, hoặc một catalog-owned object-control technique đã chứng minh equivalent control access right. `WriteDacl` tự nó không đủ. |
| Required attacker state | Actor/capability cho phép exercise structural right. |
| Runtime assumptions | DC/directory write path reachable nếu snapshot không chứng minh; password-policy constraints nếu model cần biết. |
| Predicted action | `reset_password(target, actor)` |
| Resulting state | `CredentialPossession(target, form=password)` hoặc compatibility effect `authentication_control(target)` mapped sang possession capability. |
| Known-false -> blocked | Right không tồn tại/đã bị explicit deny theo policy; directory write path known unavailable; password reset bị policy known-reject. Disabled target **không** tự block reset. |
| Missing evidence -> indeterminate | Required ACL/effective authorization hoặc runtime write condition không có evidence và không có approved assumption. |
| Ranking boundary | Retry/deadline, time, success likelihood, operational/detection cost. |

Primary basis: Microsoft [User-Force-Change-Password](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/ea48e638-1bad-4663-a492-8e078f2d42c7) và [MS-ADTS `unicodePwd`](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6e803168-f140-4d23-b2d3-c3a8ab5917d2).

### 5.2. `activate_identity(user)` — derived state operation

| Field | Decision |
| --- | --- |
| Structural evidence | Principal/account tồn tại và các account-policy facts đã thu thập. |
| Required attacker state | `CredentialPossession(user, form)` hoặc compatible existing session/token capability. Pre-secret roast material không đủ. |
| Runtime assumptions | Chỉ dùng cho predicates không có trong snapshot, ví dụ authentication infrastructure reachable; phải có declared `authentication_context`. |
| Predicted/derived operation | `activate_identity(user, authentication_context)` |
| Resulting state | `UsableIdentity(user, authentication_context)` |
| Known-false -> blocked | Account/authentication policy được snapshot chứng minh là không cho capability đó dùng trong scope đang xét, ví dụ disabled/expired/logon-hours/policy-silo restriction khi relevant. |
| Missing evidence -> indeterminate | Một prerequisite bắt buộc cho declared scope không được thu thập và không có scenario assumption. |
| Ranking boundary | Work-unit alias `acquire_ticket`, protocol-specific time/cost/retry, numeric likelihood. |

Microsoft [MS-KILE account-policy checks](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/beb74443-2e5e-4cfa-917e-46ef701a5cb5) chứng minh disabled/expired/locked/logon-hours có thể làm Kerberos authentication bị từ chối. [Authentication policies and silos](https://learn.microsoft.com/en-us/windows-server/security/credentials-protection-and-management/authentication-policies-and-authentication-policy-silos) cho thấy authentication còn có thể bị giới hạn theo user/device/service scope. Vì vậy `UsableIdentity` không phải blanket guarantee cho mọi target.

### 5.3. `remote_exec_winrm(target_host, actor)`

| Field | Decision |
| --- | --- |
| Structural evidence | Catalog/scenario owner chứng minh actor có remote-management/host authorization phù hợp; không invent `CanPSRemote`/`AdminTo` edge chỉ để pass. |
| Required attacker state | `UsableIdentity(actor, authentication_context)` với context khớp transition/runtime đang xét. |
| Runtime assumptions | Network/listener/service/authentication/endpoint predicates chưa có trong snapshot có thể được supplied qua `RuntimeContext`, nhưng known-false veto không được override. |
| Predicted action | `remote_exec_winrm(target_host, actor)` |
| Resulting state | `HostExecution(target_host, privilege)` với privilege được chứng minh bởi endpoint/token/scenario evidence. |
| Known-false -> blocked | Listener/service/network known unavailable, authentication policy rejects actor, endpoint/session configuration denies actor, hoặc required execution context known unavailable. |
| Missing evidence -> indeterminate | Runtime predicate bắt buộc không được thu thập và không có approved assumption. |
| Ranking boundary | Time, likelihood, detection/operational cost. |

Microsoft [WinRM remote authentication](https://learn.microsoft.com/en-us/windows/win32/winrm/authentication-for-remote-connections) mô tả Negotiate/Kerberos/NTLM behavior và cho thấy protocol/path phụ thuộc environment; vì vậy TGT không thể là universal prerequisite.

## 6. Actor switching rule

Engine chỉ được dùng `target_user` làm actor của transition tiếp theo khi attacker state chứa capability actor tương ứng:

```text
CredentialPossession(B)
  -- activate_identity(context=H1) -->
UsableIdentity(B, H1)
  -- actor switch permitted only in matching context H1 -->
candidate action with actor=B
```

Actor switching **không** tự làm target action applicable và không bỏ scope. Search chỉ được dùng B như actor khi `(B, current authentication_context)` có trong state. Transition kế tiếp vẫn phải đánh giá:

- structural authorization của B đối với target;
- target/service-specific runtime predicates;
- known-false veto;
- explicit scenario assumptions cho missing evidence.

Rule này tránh cả hai lỗi:

- giữ foothold actor cho mọi bước dù đã takeover identity mới;
- coi possession của password/hash/ticket là bằng chứng rằng mọi service sẽ chấp nhận identity.

## 7. Counterfactual traces

### C1 — cùng graph, khác initial state

```text
Graph: A --ForceChangePassword--> B
       B --declared host authorization--> H

S0: control(A)
-> reset_password(B) candidate/applicable
-> CredentialPossession(B,password)
-> activate_identity(B, context=H)
-> UsableIdentity(B, H)
-> H transition có thể được xét

S0': no control(A)
-> reset_password(B) blocked
-> không sinh B capabilities
```

### C2 — disabled account

```text
reset_password(B) có thể vẫn applicable
-> CredentialPossession(B,password)

activate_identity(B, context=H)
+ B disabled known true
-> blocked
```

Đây là lý do account-disabled check nằm ở activation/authentication, không phải blanket reset veto.

### C3 — NT hash, không có TGT

```text
CredentialPossession(B, nt_hash)
-> activate_identity(B, context=H) có thể tạo UsableIdentity(B, H)
-> target-specific transition chọn authentication path phù hợp
```

Không được block chỉ vì state không có `has_tgt(B)`.

### C4 — existing session/token

```text
existing usable session/token capability for B trong context H
-> UsableIdentity(B, H) / compatible scoped actor capability
-> không bắt buộc acquire_ticket
```

### C5 — thiếu trạng thái WinRM

```text
UsableIdentity(B, H)
+ host authorization known
+ WinRM listener/service unknown
-> indeterminate

same graph/state
+ RuntimeContext assumption explicitly permits reachable WinRM
-> applicable nếu không có known-false veto
```

## 8. Lifetime boundary

Default core model: **không materialize timestamps/ticket expiry trong AttackState**.

Lý do:

- input chính là snapshot tĩnh;
- default path applicability không cần mô phỏng AS/TGS clock;
- ticket lifetime có thể bị domain/authentication policy thay đổi;
- các credential forms khác nhau không dùng cùng lifetime model.

Microsoft [How to Configure Protected Accounts](https://learn.microsoft.com/en-us/windows-server/security/windows-authentication/how-to-configure-protected-accounts) cho phép cấu hình TGT lifetime và mô tả các trường hợp khác default domain policy. Vì vậy không hardcode 10h trong semantics.

Nếu một future use case thực sự phụ thuộc expiry, artifact specialization có thể mang coarse validity metadata ở **scenario/evaluator** hoặc technique-specific state. Việc đó cần research/ADR riêng; không mở rộng default #174.

## 9. Boundary với #145 và canonical provenance

Decision này đi qua boundary đã đặt trong #145, không rewrite graph loader/search foundation:

```text
canonical graph (immutable)
    -> transition/applicability boundary
       input: edge/fact + AttackState + RuntimeContext
       output: applicable | blocked | indeterminate
               + derived effects/capabilities
               + assumptions/evidence/rationale
    -> candidate path
    -> whole-path evaluator
```

Bất biến bắt buộc:

- effect chỉ thêm/đổi **derived AttackState** hoặc scenario overlay;
- không sửa canonical graph bytes, canonical edge provenance hoặc raw snapshot;
- assumption không sinh structural fact giả;
- known-false structural/runtime evidence không bị optimistic assumption override;
- path giữ exact structural evidence + semantic decision + assumption trace để audit;
- semantics không tự invent probability, duration, impact hoặc detection weight.

## 10. Semantics vs evaluator/ranking

Semantics sở hữu:

```text
applicable / blocked / indeterminate
derived capabilities
reason / evidence / assumptions used
```

Evaluator/ranking sở hữu:

```text
conditional success likelihood
retry/deadline/horizon policy
time/cost
target impact
risk/detection features and calibrated penalties
whole-path comparison/ranking
```

Event IDs hoặc expected telemetry có thể được giữ làm feature/evidence reference. Chúng **không tự suy ra numeric probability hoặc detection penalty**.

Compatibility với PR #173:

- `acquire_ticket` work unit và rating IDs giữ nguyên;
- evaluator có thể hạch toán q/time/cost theo work unit cũ;
- semantic owner mới giải thích capability bridge mà không đổi historical oracle/rating provenance;
- migration implementation sau #174 phải preserve exact rating/release bindings.

## 11. Action ownership disposition

| Production-candidate action/work unit | Semantic owner sau #174 | State effect | Ghi chú |
| --- | --- | --- | --- |
| `reset_password` | Catalog transition theo direct/equivalent reset right | `CredentialPossession(password)` | Không dùng WriteDacl như direct evidence |
| `acquire_ticket` | **Ranking compatibility alias** -> derived `activate_identity` | `UsableIdentity(principal, authentication_context)` | Không materialize TGT mặc định; giữ scope hiện hành |
| `remote_exec_winrm` | Catalog/scenario remote-exec transition | `HostExecution(privilege)` | Privilege phải được evidence/assumption chứng minh |
| Kerberos-specific abuse future | Technique-specific catalog owner | optional ticket/key possession | Chỉ materialize artifact khi technique thật sự cần |

## 12. Compatibility / migration với current `AttackState`

#174 **không đổi schema runtime trong PR research này**. Current implementation có 11 immutable buckets; bảng dưới là disposition bắt buộc để follow-up không tự suy migration:

| Current bucket | Current representation / meaning | Quan hệ với vocabulary #174 | Disposition |
| --- | --- | --- | --- |
| `control` | principal IDs; trusted/declared initial control | gần `AccountControl` nhưng rộng hơn "ACL account control" | **Retain**, semantically distinct from `UsableIdentity`; không auto-convert |
| `effective_member` | `(principal, group)` | entitlement state | **Retain**; ngoài auth-material vocabulary |
| `permission` | derived `StructuralRelationship` | derived authorization capability | **Retain**; không mutate canonical graph |
| `relationship_added` | derived relationships created by semantic action | scenario overlay capability | **Retain**; không mutate canonical graph/provenance |
| `credential_material` | User IDs only; current HasSession recovery output, không lưu form/context | coarse legacy material bucket | **Retain as coarse/legacy representation**; **không alias trực tiếp** sang `CredentialPossession` và không actor-switch; future typed migration phải xác định material/form/validity |
| `authentication_control` | User IDs; generic compatibility effect của account-control/reset techniques | evidence rằng attacker có một authentication-control capability, nhưng chưa scoped usable actor | **Retain**; không đủ một mình để sinh `UsableIdentity` |
| `reset_password_control` | User IDs; reset-specific provenance/capability | current bridge-specific proof that reset path created a known password-control outcome | **Retain** cho Week 3 compatibility; current `acquire_reset_identity` dùng bucket này làm trigger. Có thể map conceptually tới `CredentialPossession(user,password)` chỉ trong transition reset đã chứng minh, không phải schema alias toàn cục |
| `usable_identity` | `(principal, authentication_context)` | **exact implementation representation** của `UsableIdentity(principal, authentication_context)` | **Retain authoritative**; không bỏ context dimension |
| `admin_control` | Computer IDs | privileged host-control terminal capability | **Retain semantically distinct**. Có thể xem như conceptual projection của `HostExecution(host, administrative)`, nhưng không replace/rename trong #174 vì current terminal semantics phụ thuộc bucket này |
| `remote_command_execution` | `(principal, computer)` | remote execution/session capability với actor, không tự nói privilege | **Retain semantically distinct**; conceptual `HostExecution` không được nâng nó thành admin |
| `interactive_session` | `(principal, computer)` | interactive access/session capability | **Retain semantically distinct**; không collapse với remote command/admin control |

### Roasting / recovery compatibility

Week 4 phải giữ tối thiểu bốn phase khác nhau:

```text
RecoverableAuthMaterial(V, as_rep_or_tgs_ciphertext, acquisition_context)
    -- offline recovery succeeds -->
CredentialPossession(V, password_or_key)
    -- activate_identity(V, auth_context=H) -->
UsableIdentity(V, H)
    -- entitlement/resource transition -->
asset capability
```

Rules:

- AS-REP/Kerberoast response/ciphertext **không** map vào current `credential_material`, `authentication_control`, `reset_password_control` hoặc `usable_identity` chỉ vì đã request được material.
- Current `credential_material(user)` cũng không tự tương đương `CredentialPossession(user, form)` vì bucket không ghi form/validity/context. Follow-up implementation phải either introduce typed state hoặc một explicit validation/recovery transition trước actor activation.
- `reset_password_control` là provenance qualifier riêng của reset path; recovered roast secret không được reuse bucket này để đi tắt qua `acquire_reset_identity`.
- Một future generic activation bridge có thể accept typed `CredentialPossession`, nhưng phải emit context-scoped `usable_identity=(principal, authentication_context)` và preserve current false/unknown rules.

### Host execution compatibility

`HostExecution` trong research là umbrella để reasoning, không phải replacement bucket:

```text
remote_command_execution(actor, host)
    -> execution/session exists under actor
    -> privilege is not implied

admin_control(host)
    -> administrative host-control capability
    -> current Week 3 terminal meaning remains unchanged
```

Không có reversible 1:1 mapping từ current state sang `HostExecution(host, privilege)`: `admin_control` hiện không lưu actor, còn `remote_command_execution` không lưu privilege. Vì vậy migration chỉ được làm khi schema/terminal contract được review riêng; #174 không đổi Week 3 terminal semantics.

## 13. Follow-up implementation after research approval

#180 đã giải quyết bridge bounded cho Week 3 và không cần mở lại. Sau khi #174 được review, M3 implementation nên được tách nhỏ và giữ compatibility:

1. Preserve current `AttackState` compatibility table above; any typed `CredentialPossession`/roast-material extension must not collapse legacy buckets or remove `authentication_context` from `usable_identity`.
2. Reconcile reset predicates: disabled account không là blanket reset blocker; `WriteDacl` phải đi qua explicit ACL-mutation transition.
3. Reconcile remote-exec resulting privilege để không suy local-admin từ Remote Management Users hoặc generic remoting access.
4. Document/migrate `acquire_ticket` work-unit alias mà không đổi Week 3 rating/release IDs.
5. Add counterfactual regression tests C1-C5 và invariants canonical graph/provenance immutable.
6. Chỉ thêm ticket-specific/lifetime state qua follow-up ADR nếu một use case chứng minh nó thay đổi applicability.

## 14. Closure checklist cho #174

- [x] Mỗi production-candidate action/work unit có semantic owner rõ.
- [x] Chuỗi reset/control -> authentication capability -> host action không còn magic jump.
- [x] Known-false -> `blocked`; missing required evidence -> `indeterminate`.
- [x] Structural relationship không tự đồng nghĩa attack success.
- [x] Prediction không yêu cầu observed attack telemetry.
- [x] Cùng graph nhưng initial state/context khác có thể đổi transition applicability.
- [x] Semantics không tự gán numeric probability/duration.
- [x] Effect không mutate canonical snapshot/provenance.
- [x] Boundary với #145 và whole-path evaluator được map rõ.
- [x] `acquire_ticket`, authentication capability, actor switching và lifetime có disposition cụ thể.
- [x] `UsableIdentity` preserves current `authentication_context` scope.
- [x] Current `AttackState` buckets have explicit retain/alias/distinct/migration dispositions, including roast-material vs recovered-secret and host-execution compatibility.

Các checkbox trên là **research disposition**. Implementation follow-ups vẫn cần PR/test riêng nếu current catalog/state chưa khớp decision này.
