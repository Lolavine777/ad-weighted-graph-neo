# RBCD → delegated service context → tài sản C_R (#229)

## 1. Baseline và phạm vi bàn giao

Nhánh `feature/229-rbcd` xuất phát từ `develop@32ffd62` (đã merge #234 AS-REP,
#231 acceptance package, #230 kerberoasting/replay binding, #232 min-effort,
#233 CLI schema 0.2, #222 snapshot facts, #221 query materialization).
Đã đọc `CONTRIBUTING.md`, issue #229, comments mới nhất của `@Lolavine777` trên PR #236,
handoff #218 mục 4 và trạng thái #206/#208. Worktree riêng bảo toàn thay đổi của người khác.

Đây là triển khai predictive attack path search cho Resource-Based Constrained Delegation
(RBCD) trên public query contract và CLI schema `week4-query-result/0.2.0`. Engine tự động sinh
chuỗi tấn công theo stateful search thật mà không nhận đường đi có sẵn từ caller. Tuyệt đối
không thực thi Kerberos S4U live, không crack mật khẩu, không provision máy mới.

Cơ sở kỹ thuật:
- [AddAllowedToAct](https://bloodhound.specterops.io/resources/edges/add-allowed-to-act): Phân biệt quyền ghi thuộc tính với quan hệ ủy quyền đã tồn tại.
- [AllowedToAct](https://bloodhound.specterops.io/resources/edges/allowed-to-act): Yêu cầu principal có SPN và thỏa mãn hạn chế ủy quyền.
- [Wagging the Dog (Elad Shamir, 2019)](https://eladshamir.com/2019/01/28/Wagging-the-Dog.html): Ranh giới giữa service ticket và quyền thực thi trên dịch vụ đích.

---

## 2. Matrix field / gate / owner / effect

Ký hiệu:
- `X`: Computer foothold/authentication context (`10000000-0000-4000-8000-000000000001`).
- `U_R`: Controller User ban đầu (`S-1-5-21-1000-2000-3000-1580`).
- `M`: Principal User/Service account có SPN (`S-1-5-21-1000-2000-3000-2075`).
- `C_R`: Computer mục tiêu (`10000000-0000-4000-8000-000000000027`).
- `P`: Principal bị mạo danh (`S-1-5-21-1000-2000-3000-917`).
- `SPN`: `http/computer27.example.test`, `service`: `winrm`.

| Projection / Owner | Nguồn fact / prerequisite | Runtime gate (subject, target) | Effect & Artifact | Ranh giới |
| --- | --- | --- | --- | --- |
| **R1 — Acquire control/secret of M** (`rbcd_acquire_secret`) | Edge `GenericAll`/`ForceChangePassword` U_R→M; usable U_R/X | `effective_reset_right(U_R, M)`, `directory_write_allowed(U_R, M)`, `password_policy_accepts(U_R, M)` | `rbcd_secret`: `DelegationArtifact(b, provenance, form="password")` | M chưa kiểm soát chỉ vì có ACL; disabled account không tự blanket-veto reset. |
| **R2 — Prepare controlled service capability** (`rbcd_prepare_service`) | `rbcd_secret` của M; `SnapshotFacts` `has_spn`, `service_principal_names`; `target_enabled(M)` | `secret_valid(U_R, M)`, `key_derivation_accepted(U_R, M)`, `key_encryption_compatible(U_R, M)`, `service_authentication_accepted(U_R, M)`, `network_kdc_reachable(U_R, M)` | `controlled_service`: `DelegationArtifact(b, provenance, form="password")` | Không cấp global usable identity cho M; không suy key từ SPN; SPN missing giữ indeterminate. |
| **R3 — Configure descriptor** (`rbcd_configure_descriptor`) | Edge `GenericAll` U_R→C_R; usable U_R/X; `known_identity(M)` | `effective_descriptor_write(U_R, C_R)`, `directory_write_allowed(U_R, C_R)` | `rbcd_descriptor`: `DelegationArtifact(b, provenance)` | R3 độc lập với R1/R2; descriptor là branch-local; không mutate `AllowedToAct` trong snapshot. |
| **R4 — Obtain delegated service context** (`rbcd_delegate_service`) | `controlled_service(M)`; `rbcd_descriptor(M, C_R)`; `known_identity(P)` | `target_spn_binding(U_R, C_R)`, `delegation_policy_allows(U_R, C_R)`, `network_kdc_reachable(U_R, C_R)`, `s4u_request_accepted(U_R, C_R)` | `delegated_context`: `DelegationArtifact(b, provenance)` | Không tạo global usable P; không cấp DA checkpoint cho P ở context khác. |
| **R5 — Reach final asset** (`rbcd_service_admin`) | `delegated_context(P, C_R, WinRM)`; `target_enabled(C_R)` | `target_spn_binding(P, C_R)`, `network_winrm_reachable(P, C_R)`, `service_winrm_running(P, C_R)`, `endpoint_authorized(P, C_R)`, `winrm_authentication_accepted(P, C_R)`, `admin_execution_context(P, C_R)` | `admin_control(C_R)` (Goal reached) | Ticket/remote command không tự thành admin; P authorization missing giữ unknown. |

---

## 3. Mapping độc lập R1–R5 và API tái sử dụng / mới

### Tái sử dụng (Reuse)
1. **Query & Search Engine:** `run_attack_query`, `materialize_query`, `generate_attack_paths`, `AttackState`, `TransitionStep`, `AttackQuery`.
2. **Snapshot facts & Provenance:** `SnapshotFacts.lookup`, `serialize_snapshot`, `graph_digest`.
3. **Semantic Replay & Ranking:** `evaluate_search_candidates`, `PathRankingEngine`, `validate_candidate_envelope`, `SemanticReplayBinding`, `verify_search_envelope`.
4. **CLI & Result Package:** `src.engine.query_cli.execute`, `compare_query_runs`.

### API mới
1. **Delegation Types (`src/engine/semantics/rbcd_types.py`):**
   - `DelegationBinding`: Typed dataclass frozen chứa `controller`, `principal`, `impersonated`, `target`, `authentication_context`, `service_context`, `service="winrm"`, `spn="http/..."`.
   - `DelegationArtifact`: Typed artifact frozen chứa binding và provenance.
2. **AttackState Extensions (`src/engine/semantics/state.py`):**
   - Bổ sung 4 state fields: `rbcd_secret`, `controlled_service`, `rbcd_descriptor`, `delegated_context`.
3. **RBCD Semantics & Evaluator (`src/engine/semantics/rbcd.py`):**
   - 5 catalog recipes: `rbcd_acquire_secret`, `rbcd_prepare_service`, `rbcd_configure_descriptor`, `rbcd_delegate_service`, `rbcd_service_admin`.
   - Stateful producer `producers(nodes, state, actor, context)` tạo candidate transitions tự động.
   - Evaluator `evaluate_rbcd` kiểm tra exact technical, snapshot, và runtime gates.
4. **Transition Lineage & Replay Boundary:**
   - `TransitionStep` liên kết đúng `derived_from_step`: R2 trỏ về R1, R4 trỏ về `max(parent(service), parent(descriptor))`, R5 trỏ về R4.
   - `adapter_145.py` ghi nhận `rbcd_binding` trong `transition_lineage`.
   - `validation.py` & `verification.py` cưỡng chế typed semantic replay cho toàn bộ RBCD candidates. Candidate JSON giả mạo không thể tự khai authoritative facts.
   - Giới hạn query contract: tối đa 1 delegation binding cho mỗi query (`len(rbcd_bindings) <= 1`).

---

## 4. Ranh giới State, Context và Evidence

- **Canonical Snapshot vs Branch State:** Canonical graph và `SnapshotFacts` là bất biến (immutable). Các biến đổi descriptor hay credential chỉ tồn tại cục bộ trong `AttackState` bất biến của từng nhánh tìm kiếm.
- **Controlled Secret vs Service Key:** `rbcd_secret` chỉ là password credential của M; nó không tự biến thành khả năng xác thực dịch vụ nếu thiếu SPN, key derivation hoặc KDC acceptance.
- **Service Key vs Delegated Ticket:** Khả năng xác thực của M chỉ dùng để yêu cầu vé ủy quyền qua S4U; không tự động cấp danh tính dùng được toàn cục cho M.
- **Delegated Context vs Global Identity:** Vé ủy quyền cho P chỉ có hiệu lực trên tài nguyên `C_R` với dịch vụ `WinRM`. P không trở thành Domain Admin và không có usable credential trên các máy tính khác.
- **Command Execution vs Admin Control:** Việc kết nối WinRM không mặc định cấp quyền quản trị; chỉ khi `admin_execution_context` và `endpoint_authorized` được chứng minh, trạng thái `admin_control(C_R)` mới được thiết lập.

---

## 5. So sánh Oracle: Expected vs Actual và giải thích mapping

Dựa trên độc lập oracle tại [#218, mục 4](week4-extension-scenario-handoff.md) và `tests/fixtures/rbcd/oracle.json`:

### 5.1. Ba thứ tự tối thiểu hợp lệ (3 minimal programs)
Oracle quy định R3 độc lập với R1/R2, dẫn đến đúng 3 thứ tự khả thi:
1. `R1 → R2 → R3 → R4 → R5` (`rbcd_acquire_secret` → `rbcd_prepare_service` → `rbcd_configure_descriptor` → `rbcd_delegate_service` → `rbcd_service_admin`)
2. `R1 → R3 → R2 → R4 → R5` (`rbcd_acquire_secret` → `rbcd_configure_descriptor` → `rbcd_prepare_service` → `rbcd_delegate_service` → `rbcd_service_admin`)
3. `R3 → R1 → R2 → R4 → R5` (`rbcd_configure_descriptor` → `rbcd_acquire_secret` → `rbcd_prepare_service` → `rbcd_delegate_service` → `rbcd_service_admin`)

**Actual:** Engine sinh ra đúng 3 paths tương ứng với 3 thứ tự này, không thiếu và không thừa.

### 5.2. Tám trạng thái chiếu (8 projected states)
Từ bitset `{reset_M, service_M, descriptor_M_C_R, delegated_P_C_R, admin_C_R}`:
1. `()` (ban đầu)
2. `('descriptor_M_C_R',)` (sau R3)
3. `('reset_M',)` (sau R1)
4. `('reset_M', 'descriptor_M_C_R')` (sau R1 & R3)
5. `('reset_M', 'service_M')` (sau R1 & R2)
6. `('reset_M', 'service_M', 'descriptor_M_C_R')` (sau R1, R2, R3)
7. `('reset_M', 'service_M', 'descriptor_M_C_R', 'delegated_P_C_R')` (sau R4)
8. `('reset_M', 'service_M', 'descriptor_M_C_R', 'delegated_P_C_R', 'admin_C_R')` (sau R5 - goal)

**Actual:** Tất cả 3 programs chỉ duyệt qua các tập con của đúng 8 trạng thái này.

### 5.3. Các điểm cắt (Cutoffs) và tính độc lập nhánh
- `R-RESET-F`: Khi quyền reset M thất bại, R1/R2 bị chặn, nhưng R3 (cấu hình descriptor) vẫn thực hiện được độc lập.
- `R-WRITE-F / R-WRITE-U`: Khi quyền ghi descriptor trên C_R thất bại/unknown, R3 bị chặn, nhưng R1/R2 vẫn hoàn thành để chuẩn bị service capability.
- `R-SPN-F / R-SPN-U`: Khi SPN của M thiếu hoặc false, R2 bị chặn, nhưng R1 và R3 vẫn thành công.
- `R-KEY-U`: Key validity của M unknown, R2 dừng ở indeterminate; không sinh delegated context.
- `R-POLICY-F`: Delegation policy của P deny, R4 bị chặn.
- `R-DELEGATE-U`: S4U request missing, R4 dừng ở indeterminate.
- `R-ASSET-F / R-ASSET-U`: Quyền thực thi admin của P trên C_R thiếu/deny, R4 vẫn đạt được delegated context, nhưng R5 bị chặn.
- `R-REUSE-M`: Khi initial state đã có sẵn `controlled_service`, engine tự động bỏ qua R1 và R2, sinh ra program tối thiểu 3 bước: `R3 → R4 → R5`.
- `R-SCOPE`: Đổi target sang host khác không có cấu hình ủy quyền, không tái sử dụng vé.
- `R-CF-ACL`: Thu hồi quyền GenericAll tới C_R, R3 bị chặn.
- `R-EXT-OFF`: Tắt kỹ thuật RBCD, không có đường nào tới mục tiêu.

---

## 6. Work Units, C/P/I Disposition và Evaluator Integration

Theo ADR-0013 và quy chuẩn Week 4:
- RBCD gồm 5 active work units tương ứng 5 actions:
  - `work_rbcd_acquire_secret`
  - `work_rbcd_prepare_service`
  - `work_rbcd_configure_descriptor`
  - `work_rbcd_delegate_service`
  - `work_rbcd_service_admin`
- C/P/I chưa có cơ sở số liệu (numeric basis) trong Week 4:
  - `effort_status: "unrated"`, `effort: None`
  - `likelihood_interval: None`
  - `impact: None`
- Không tự ý sao chép số liệu từ các kỹ thuật khác hoặc bịa đặt P=1.
- Toàn bộ candidates đều là `feasible`, được gắn cờ `unrated`, và `is_minimum_proven_over_scope: False`.
- Trường hợp zero-work (initial goal satisfied) giữ nguyên disposition `semantic_initial_goal_zero_work`.

---

## 7. CLI, Determinism và So sánh Baseline

### Commands
```bash
# Chạy ON (R-P positive)
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query.json --label synthetic --output run-1.json
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query.json --label synthetic --output run-2.json

# So sánh tính tất định
python -m scripts.research.compare_query_runs run-1.json run-2.json

# Chạy OFF (Tắt kỹ thuật)
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query-off.json --label synthetic --output off.json

# Chạy RAW (Thiếu assumptions)
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query-raw.json --label synthetic --output unresolved.json
```

### So sánh Baseline: ON vs OFF vs RAW
- **ON (R-P):** Sinh ra 3 paths, đạt mục tiêu `admin_control(C_R)`, status `success`.
- **OFF:** 0 paths, status `no_path_found`.
- **RAW:** 0 paths, status `unresolved` (các runtime gates dừng ở `indeterminate`, không áp dụng optimistic effects).
- **Tính tất định:** Hai lần chạy ON độc lập cho ra kết quả đồng nhất 100%:
  `semantic_sha256: sha256:8cbe84fd19d74d402eeb2a6af114a877a29aac567e71e13157adbc2a7d9f1792`.

---

## 8. Giới hạn (Remaining Unsupported Scope) và Handoff

### Phạm vi chưa hỗ trợ (Out of Scope)
- Không hỗ trợ khởi tạo máy tính mới qua `MachineAccountQuota` (MAQ).
- Không mô hình hóa Cross-forest hoặc Resource Domain khác realm.
- Dịch vụ ủy quyền hiện cố định ở `WinRM` với SPN HTTP.
- Key forms chỉ hỗ trợ `password`; không hỗ trợ NT hash hoặc Kerberos ticket thô.
- Không có live Kerberos simulator hoặc S4U traffic emitter.

### Handoff cho #206 và #208
- Mã nguồn và tests đã hoàn thành tại branch `feature/229-rbcd`.
- Toàn bộ 24 test ca RBCD tại `tests/test_rbcd.py` đều PASS.
- Acceptance runner case `W4-TECH-RBCD` chuyển sang trạng thái PASS dựa trên independent expected.
- Handoff cho TTS A (@Lolavine777) phục vụ review độc lập (#206) và tích hợp nghiệm thu tổng thể (#208).
