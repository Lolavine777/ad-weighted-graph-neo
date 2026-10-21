# Worklog — 2026-10-14 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #287 backend acceptance; refs #279, #224
- Thời gian thực tế ước lượng: hai lượt nghiệm thu local và validation trong phiên 14/10.

Refs #224, #279. Bổ sung backend cho luồng structural route → exact-state
diagnostics → chọn reviewed assumptions → engine rerun. Không sửa frontend #279.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Triển khai ban đầu | Các lệnh và môi trường ghi bên dưới | 94 synthetic tests PASS; thời điểm đó chưa có SEAMLESS |
| Nghiệm thu SEAMLESS thật | [Runner](../../scripts/research/guided_exploration_acceptance.py), [summary cuối](../../reports/research/issue287-guided-exploration-acceptance-v2.json) | Revision cuối ebffa1e: 24/24 PASS, 225.526s; trước đó c85a77a: optional-data pytest 3 passed in 245.01s |
| RAW / proposal rerun A | Public materializer + `run_attack_query` qua `query_cli.execute` | RAW/none: indeterminate, 0 candidates; full: success, 3; drop recovery: indeterminate, 0 |
| Structural B | Exact-snapshot name resolution; private bindings/traces trong `reports/generated/issue287/` | 1 route, 2 edges (GenericAll, AdminTo); cap 5000 expansions, truncated |
| Negative controls | Scope/IDs, isolated runtime False veto, tiny budget | Lượt đầu PASS; không thay raw hoặc facts |
| Raw integrity / privacy | Official verifier trước/sau; 6 raw SHA-256; 32 local evidence digests | Raw không đổi; summary scan có 0 matches với canonical IDs/labels/domains private |
| Repo checks | Ruff check/format toàn repo, yamllint, check_contract, check_repository, Compose config | PASS local; không manual rerun remote CI |
| Focused tests revision cuối | `python -m pytest tests/test_exploration.py tests/test_engine.py tests/test_asrep.py -q` | 96 passed in 21.24s |
| Expanded full suite | `python -m pytest -q` | 2830 passed, 5 failed, 54 skipped, 48 subtests passed in 876.53s; chưa PASS |
| Fix source-pin integration gate | [Week4 v3](../../reports/research/week4-guided-exploration-acceptance-manifest-v3.json); manifest, checkout-bytes, mutation và demo smoke tests | 7 passed in 323.94s; strict pins và normative expectations giữ nguyên; không rerun full suite lần nữa |
| Historical evidence | Regression checksum v2; [summary trước](../../reports/research/issue287-guided-exploration-acceptance.json) | Giữ nguyên bytes, không ghi đè manifest/summary lịch sử |

Lượt nghiệm thu dùng worktree `.worktrees/pr-287-acceptance`, đọc raw từ checkout
gốc; không thay checkout/viewer đang chạy. Head ban đầu `be684d8cf2856737941879fde79e8f1b0ce75ec9`.
Không có AGENTS.md trong checkout hoặc các thư mục cha đã kiểm tra. Tại lần đọc
đầu, #287 chưa có review/comment; đã đọc clarification mới nhất trên #279. Manifest verifier và
`seamless_inputs()` chính thức được dùng, không thay evaluator/search.

Trong lúc nghiệm thu, review mới của Lolavine777 lúc `2026-10-14T03:24:51Z`
APPROVE exact head `be684d8` cho backend contract/API; đã đọc lại review.
Review không claim SEAMLESS hoặc UI acceptance, không là approval tự tạo cho
commit harness/evidence mới. Code revision nghiệm thu đầu:
`c85a77ad2e0f85f9a96d1286e96e83dd802770cd`; evidence của lượt đó đã commit
`1f1c4114bb72dab40311bebd30fd2ec3ddc3bb5a` và giữ nguyên.
Code revision cuối `ebffa1e6687b78030ea37b0f94602f38be45f4e6`; publication
evidence cuối là commit docs/report kế tiếp, ghi SHA riêng trên PR và bàn giao.

Expanded suite có một frozen Week4 source-list gate không chấp nhận module
`src/engine/exploration.py` thêm vào: 122 pins cũ đều khớp, nhưng tập file khác.
Đã tái hiện gate này trên detached worktree đúng head `be684d8`; không chỉnh
historical manifest/fixtures. Probe Week4 baseline sạch có 36 PASS, 0 unexpected
failures. Trong expanded run, cập nhật worklog giữa lượt chạy làm
`W4-CLI-PACKAGE.clean_tracked_source=False`, gây thêm failures và demo cascade;
không là lỗi evaluator. Trace local `reports/generated/issue287/full-suite-tail.txt`
và `week4-expanded-probe.json` giữ kết quả gốc. Nhóm failures được rerun sau
commit docs/evidence, với checkout sạch: 3 PASS, còn source-pin FAIL và demo
cascade FAIL. Sửa bằng bản kê v3 **mới**, không đổi v2: hai test consumers trỏ
sang v3 cho current-source identity; thêm checksum regression bảo vệ v2. Không
relax equality hoặc normative expectations. Rerun bảy affected tests sau sửa đều
PASS; SEAMLESS chạy lại trên code revision cuối vào `reports/generated/issue287/final-v2/`
(24 PASS). Full suite ban đầu vẫn được ghi là FAIL, không đổi thành full-suite
PASS từ kết quả focused rerun. [Validation ledger](../../reports/research/issue287-guided-exploration-validation.json).

Các phần dưới ghi lại điều kiện của **lượt triển khai ban đầu**; hạn chế không có
dataset của lượt đó được giải quyết bởi nghiệm thu riêng ở bảng trên, không sửa
historical outputs để tạo kết quả mới.

## Baseline và phạm vi

- Base develop: `ac1a61f14f1134bf49335935f55f62a6aed8aee7`.
- Đã khảo sát viewer head `94d4e4fac2f62a5a59b0de2c6583fc632b93cd28`.
- Các source/config/fixtures backend đã dùng có cùng blob SHA giữa hai refs.
- Checkout Git trực tiếp không truy cập được repo; lấy source/fixtures cần thiết
  qua GitHub connector và kiểm tra trên workspace subset. Không claim full repo
  checks hoặc remote CI PASS. Tree commit dựa trên develop đầy đủ; chỉ bốn file
  mới được xuất bản.
- Không có AGENTS.md trong cây baseline đã kiểm tra; đọc CONTRIBUTING và PR template.

## Thay đổi

- `src/engine/exploration.py`: bounded structural transport độc lập candidate;
  direct edge/catalog inspection và explicit request probe dùng evaluator hiện hành.
- Prefix replay giữ exact before/after/context/decisions, chỉ apply APPLICABLE;
  Unknown/blocked prefix dừng, không tạo giả state cho suffix. Giữ probe budgets.
- Scoped scenario template pin graph + snapshot facts và query scope; proposals
  mặc định chưa chọn; giữ rejected-assumption ledger. Selected IDs tạo fresh
  public query, consumer phải rerun engine thật. Không phát minh fact scope.
- `docs/guided-exploration.md`: contract, ví dụ synthetic, handoff và giới hạn.
- `tests/test_exploration.py`: 13 cases gồm bounded structural paths khi zero
  semantic candidates, exact-state replay, GenericAll nhiều choices, scope mismatch,
  template rerun/drop recovery và authoritative False veto.

## Kiểm chứng thực tế

CPython 3.14.8; pytest 9.1.1, networkx 3.7, PyYAML 6.0.3, ruff 0.17.0.

```text
.venv/bin/python -m pytest tests/test_exploration.py tests/test_engine.py tests/test_asrep.py -q
94 passed in 12.80s
python -m ruff check src/engine/exploration.py tests/test_exploration.py
All checks passed!
python -m ruff format --check src/engine/exploration.py tests/test_exploration.py
2 files already formatted
```

Public synthetic fixtures có sẵn; không có private SEAMLESS inputs trong workspace.
Không nghiệm thu số đường, toàn chain hoặc chín assumptions trên SEAMLESS thật.
Không sửa source/fixtures baseline để vượt qua checks.

## Điều học được / quyết định

Case A giữ đúng Computer C0 / known V_A / target C0, checkpoint G_DA và chín
assumptions của helper. Chọn đủ tạo thành công có điều kiện; không phải observed
attack success. Bỏ recovery không có bypass trong bounded scope đã chạy; action
recovery vẫn Unknown và prefix không cấp recovered secret/identity cho suffix.

Case B dùng cặp tên được yêu cầu, resolve duy nhất từ exact graph; public query
khai báo duy nhất control(B_SOURCE), không có usable identity/password, auth context C0,
goal admin_control(B_TARGET), mọi catalog techniques, không runtime facts hay
assumptions. Canonical bindings/provenance chỉ lưu local. GenericAll không bị gán
AS-REP; AdminTo ở state chưa đạt bị blocked. Không dựng template mới cho B.

Không có numeric basis: C/P/I/ranking giữ `unrated`; True assumption không cấp P.
Không claim all-source coverage, complete exploration hoặc global optimum từ B.
Template helper là declared scenario có provenance trong code; maintainer adoption
vẫn pending. Veto chỉ nằm trong runtime view control riêng, không là evidence SEAMLESS.

## Phiên bổ sung — Khảo sát và bổ sung Case SEAMLESS nhiều bước phức tạp

Thực hiện theo yêu cầu bổ sung case phức tạp hơn cho nghiệm thu #287 và demo #279 (thay thế/mở rộng Case B 2 cạnh baseline `GenericAll` → `AdminTo`).

### 1. Khảo sát hệ thống trên exact SEAMLESS snapshot

- Dữ liệu: `data/raw/SEAMLESS` xác minh khớp 100% với `data/samples/manifests/seamless-raw-v1.json` (`discrepancies: []`).
- Phạm vi: Khảo sát 2.493 users trong snapshot tới đích quan trọng `BADBLOOD.SEAMLESS.INTERNAL` (Domain Controller Computer, `admin_control`).
- Phân bố khoảng cách:
  - dist 1: 12 users
  - dist 2: 30 users
  - dist 3: 375 users
  - dist 4: 357 users
  - dist 5: 1.718 users
  - dist 6: 5 users
  - dist 7: 1 user
  - dist 8: 1 user
- Sàng lọc khoảng cách ≥ 4 cạnh: 2.075 users. Trong đó, có **1.859 candidates** sở hữu ≥ 3 relationship kinds khác nhau trên đường đi.
- So sánh các ứng viên tiêu biểu:
  - *Candidate 1*: `GINO_ROSS@SEAMLESS.INTERNAL` → `BADBLOOD.SEAMLESS.INTERNAL` (5 cạnh, 6 nodes, 4 nodes trung gian, 3 relationship kinds: `MemberOf` x3, `GenericAll` x1, `AdminTo` x1).
  - *Candidate 2*: `ALFONSO_COLEMAN@SEAMLESS.INTERNAL` → `BADBLOOD.SEAMLESS.INTERNAL` (5 cạnh, `MemberOf` x3, `WriteDacl` x1, `AdminTo` x1).
  - *Candidate 3*: `ELIZABETH_RAMOS@SEAMLESS.INTERNAL` → `BADBLOOD.SEAMLESS.INTERNAL` (5 cạnh, `MemberOf` x3, `ForceChangePassword` x1, `AdminTo` x1).
- **Lý do chọn Case chính (`GINO_ROSS`)**:
  - Chuỗi chuyển giao quyền tự nhiên và giàu tính giải thích: Token membership propagation qua các built-in security groups (`DOMAIN USERS` → `AUTHENTICATED USERS` → `PRE-WINDOWS 2000 COMPATIBLE ACCESS`) dẫn đến quyền quản trị đối tượng tài khoản (`GenericAll` trên User `KATRINA_GREEN`).
  - Đòi hỏi chuyển đổi rõ ràng giữa quyền cấu trúc và khả năng hành động: `GenericAll` cần quyền ghi thư mục và kỹ thuật password reset; tiếp đó cần action chuyển đổi dẫn xuất `acquire_reset_identity` (AuthenticationControl) để đổi actor/capability thực thi sang `KATRINA_GREEN` (`usable_identity`).
  - Cuối cùng, `KATRINA_GREEN` thực hiện `AdminTo` trên Domain Controller host `BADBLOOD` để chiếm `admin_control`.

### 2. Bảng chẩn đoán từng bước (RAW probe vs Evaluator thật)

| Bước | Cạnh & Quan hệ | Technique options | Actor / State trước | Prerequisites (RAW) | Effects nếu applicable | Blocker |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `GINO_ROSS` → `DOMAIN USERS` (`MemberOf`) | `propagate_group_entitlement` | Actor: `GINO_ROSS`; State: `control(GINO_ROSS)` | `source_authorized`: True, `security_group`: Unknown, `membership_usable`: Unknown | Thêm membership `DOMAIN USERS` | Thiếu `security_group`, `membership_usable` (indeterminate) |
| 2 | `DOMAIN USERS` → `AUTHENTICATED USERS` (`MemberOf`) | `propagate_group_entitlement` | Replay prefix [bước 1]: dừng ngay do bước 1 indeterminate | RAW không prefix: `source_authorized`: False | Thêm membership `AUTHENTICATED USERS` | Dừng prefix tại bước 1; không prefix thì blocked |
| 3 | `AUTHENTICATED USERS` → `PRE-WIN2K` (`MemberOf`) | `propagate_group_entitlement` | Chưa tới (suffix chưa đánh giá tại state này) | RAW không prefix: `source_authorized`: False | Thêm membership `PRE-WIN2K` | Dừng prefix; không prefix thì blocked |
| 4 | `PRE-WIN2K` → `KATRINA_GREEN` (`GenericAll`) | `scenario_reset_password` | Chưa tới (suffix chưa đánh giá tại state này) | RAW không prefix: `source_authorized`: False, `directory_write_allowed`: Unknown | Password reset trên `KATRINA_GREEN` | Dừng prefix; thiếu quyền/write |
| 4b | Derived action (AuthenticationControl) | `acquire_reset_identity` | Đổi actor/capability từ `GINO_ROSS` sang `KATRINA_GREEN` | RAW không prefix: `usable_identity`: False | `usable_identity(KATRINA_GREEN)` | Cần bước 4 hoàn thành |
| 5 | `KATRINA_GREEN` → `BADBLOOD` (`AdminTo`) | `obtain_admin_execution_on_host` | Chưa tới (suffix chưa đánh giá tại state này) | RAW không prefix: `source_authorized`: False, `host_session_available`: Unknown | `admin_control(BADBLOOD)` (đạt Goal) | Dừng prefix; chưa có identity/admin |

### 3. Scenario Proposal và Negative Veto Control

- Khai báo 13 assumptions độc lập cho case `seamless-287-gino-ross` (Provenance: `scenario://287/gino-ross-proposal`):
  - 3 nhóm điều kiện cho 3 bước Group propagation (`security_group`, `membership_usable`).
  - Điều kiện cho bước 4 Password Reset (`directory_write_allowed`, `ad_password_reset_allowed`, `account_active`, `target_not_sensitive_protected`).
  - Điều kiện cho bước 4b Identity acquisition (`credential_material_usable`, `network_authentication_allowed`).
  - Điều kiện cho bước 5 Host Execution (`host_session_available`, `smb_admin_execution_allowed`, `host_network_accessible`).
- Replay từng bước qua `inspect_transition`: Cả 5 bước + 1 derived action đều đạt `applicable`, dẫn đến `admin_control(BADBLOOD)`.
- **Negative Veto Control**: Loại bỏ 1 assumption cốt lõi (`directory_write_allowed` ở bước 4) khiến bước 4 thành `indeterminate`, và probe bước 5 tiếp sau dừng ngay với `prefix_status: indeterminate`, `options: []`.

### 4. Kết quả nghiệm thu và ranh giới tìm kiếm (Search Horizon)

- Chạy Acceptance Runner:
  `python -m scripts.research.guided_exploration_acceptance --raw-dir data/raw/SEAMLESS --source-label GINO_ROSS --target-label BADBLOOD --output-dir reports/generated/issue287/gino-ross-acceptance --sanitized-report reports/generated/issue287/gino-ross-summary.json`
- **Kết quả: 24/24 PASS** trong 276.666s.
  - `B_real_multistep_structure`: PASS (đúng 1 path, 5 cạnh, complete=False do chạm cap khi duyệt toàn đồ thị, nhưng path cấu trúc được trích xuất chính xác).
  - `B_exact_edge_catalog`: PASS (tất cả direct catalog options khớp 100% với bindings).
  - `B_unknown_structural_prefix`: PASS (prefix dừng chuẩn xác tại unknown edge đầu tiên).
  - `raw_integrity`: PASS (toàn bộ 6 file snapshot SHA-256 không thay đổi).
- **Ranh giới tìm kiếm (Search Horizon Truncation)**:
  - Khi chạy semantic search tự do `execute()` trên SEAMLESS toàn cục với assumed query, group `DOMAIN USERS` có fan-out rất lớn dẫn tới việc vượt trần mở rộng trạng thái 5.000 (`expansions: 5000`, `status: truncated`, 0 candidates).
  - Ngược lại, explicit prefix probe (`inspect_transition`) chứng minh chuỗi 5 bước cấu trúc hoàn toàn khả thi về mặt ngữ nghĩa và đạt goal. Báo cáo trung thực giới hạn mở rộng trạng thái mà không thay đổi thuật toán search hay artificially nâng budget.
- C/P/I/ranking giữ nguyên `unrated`.

## Nghiệm thu Kịch bản Kerberoasting Thực tế (Realistic Kerberoasting Case)

### 1. Mục tiêu và Narrative
- Dựng kịch bản Kerberoasting hoàn chỉnh trên exact SEAMLESS snapshot phục vụ demo #279 và nghiệm thu backend #287 (refs #224).
- Câu chuyện: Nhân viên thường `ALEXANDRIA_WALSH` bị lộ mật khẩu qua phishing. Attacker xác thực vào máy trạm `AWSWWKS1000000` (`usable_identity(ALEXANDRIA_WALSH, AWSWWKS1000000)`). Foothold **không cấp quyền kiểm soát máy trạm (`control(Workstation)`) hay domain privilege**.
- Identity có SPN: `AVIS_SWEET` (`MSSQL/GOOWWEBS1000000`), phát hiện qua LDAP directory enumeration (`known_identity` khai báo trong initial state).
- Mục tiêu: Domain Controller `BADBLOOD`, đạt `admin_control(BADBLOOD)` (quyền thực thi mã với đặc quyền quản trị trên host DC theo mô hình ngữ nghĩa).

### 2. Xác minh Group Type và Phân quyền DACL
- Nhóm trung gian `HO-170-DISTLIST1` nắm quyền `GenericAll` trên `AVIS_SWEET`.
- Kiểm tra file raw `data/raw/SEAMLESS/20210920185958_groups.json`: SharpHound v3 chỉ dump 7 thuộc tính (`description`, `name`, `objectid`, `highvalue`, `admincount`, `distinguishedname`, `domain`), **hoàn toàn không có thuộc tính `groupType`**.
- Nguyên tắc AD: Chỉ có Mail-Enabled Security Groups mới là security principal hợp lệ trong DACL; Distribution Groups thuần túy không dùng để ủy quyền DACL.
- Ghi nhận minh bạch: `security_group=True` là **Unverified Runtime Assumption** do giới hạn thu thập dữ liệu gốc. Phương án thay thế sạch: `SHERRIE_SOTO` $\to$ `VA-JER-ADMINGROUP1` $\to$ `OLLIE_LONG` $\to$ `BADBLOOD`.

### 3. Chuỗi Semantic Actions và Bảng Chẩn đoán
- 3 cạnh cấu trúc, 7 semantic actions:
  1. `kerberoast_request` (Alexandria @ Workstation)
  2. `recover_ticket_secret` (Alexandria @ Workstation)
  3. `activate_recovered_identity` (Alexandria @ Workstation $\to$ Avis)
  4. `propagate_group_entitlement` (Avis @ Workstation)
  5. `scenario_reset_password` (Avis @ Workstation $\to$ Ollie)
  6. `acquire_reset_identity` (Ollie @ Workstation)
  7. `obtain_admin_execution_on_host` (Ollie @ Workstation $\to$ BADBLOOD)
- Phân định rõ cổng chẩn đoán: Khi `actor == source`, `source_authorized` luôn là True; cổng chặn khi chưa có identity là `actor_controlled: False`.

### 4. Kiểm chứng Độc lập: DROP-RECOVERY vs True Known-False VETO
- **DROP-RECOVERY (Unknown Prefix Halt)**: Bỏ assumption `recovery_success` $\to$ Bước 2 indeterminate $\to$ Probe bước 3 dừng với `prefix_status: indeterminate`, `options: []`. Không tạo effect giả mạo.
- **True Known-False VETO (Ledger Rejection)**: Khai báo fact phủ định `recovery_success = False` với origin `blocked_evidence` $\to$ `scenario_proposals()` ghi nhận vào sổ cái: `rejected_assumptions: [{"reason": "known_false_veto"}]` $\to$ Veto probe bước 3 bị chặn với `prefix_status: "blocked"`.

### 5. Kết quả Runner và Đính chính Tính Tối ưu
- Runner: `python -m scripts.research.kerberoasting_seamless_acceptance`
- Kết quả: **PASS** (146.849s). Toàn bộ 7 bước replay đều đạt `applicable`.
- Engine search tự do tìm thấy **9 candidates**. Candidate 0 khớp với chuỗi thiết kế giải thích.
- Báo cáo trung thực: `truncated: true`, `truncation_reason: "expansion_limit_reached"`, `expansions: 5000`, `is_minimum_proven_over_scope: false`, `unrated`. **Không tuyên bố Candidate 0 là chương trình tối ưu**.
- Báo cáo đã khử định danh lưu tại: `reports/research/issue287-kerberoasting-seamless-acceptance.json`.

## Trở ngại và việc kế tiếp

- #279 cần endpoint wrappers và adapter source/profile → public query, structural
  selection riêng candidate, UI checkbox, rerun và live before/after compare.
- Inspect edge chỉ là direct catalog options; credential/compound/derived actions
  dùng explicit requests/bindings. Chưa có automatic whole-route planner/recommender.
- Case SEAMLESS từ `seamless_inputs()` pin actor Computer C0, known identity V_A,
  target C0; không tự dùng template đó cho query OLA_CARSON hoặc GINO_ROSS khác scope.
- Draft để review; không merge/đóng #224 hoặc claim hoàn tất guided demo.

