# Báo cáo Audit Bộ Test Suite: Quy mô, Giá trị Regression, Chi phí CI và Kế hoạch Tinh gọn

- Ngày thực hiện: 2026-10-05
- Người thực hiện: @nairyuuu (TTS B)
- Người review: @Lolavine777 (TTS A)
- Tham chiếu: Issue #190, liên quan #175, #187, #155, #180, #82, #47, #48
- Mốc: M3 / Week 4

---

## 1. Mục tiêu và Nguyên tắc Audit

Audit bộ test hiện tại trên nhánh `develop` nhằm:
1. **Đo lường baseline định lượng, tái lập được**: Thu thập số lượng file, số hàm test, số collected test cases sau parametrization, runtime và trạng thái pass/fail/skip gắn với exact commit SHA và môi trường thực thi.
2. **Đánh giá giá trị thực tế của từng nhóm test**: Xác định mỗi nhóm test bảo vệ hợp đồng (contract), bất biến (invariant), hành vi public hay regression nào; không kết luận cảm tính hay đặt chỉ tiêu giảm test tùy ý.
3. **Bảo vệ tuyệt đối các regression tối thiểu**: Đảm bảo các đặc tính an toàn hệ thống (canonical identity, SID scope, collision, reconciliation, order invariance, provenance/lineage, edge direction, known-false/unknown/assumptions, fail-closed validation, search/ranking semantics) luôn có test bảo vệ rõ ràng.
4. **Nhận diện bottlenecks và chi phí CI**: Phân tích nguyên nhân gốc rễ khiến suite chạy chậm, nhận diện các test trùng lặp, assertions yếu, fixtures copy-paste và kiểm tra lặp trong CI.
5. **Đề xuất có bằng chứng và kế hoạch khả thi**: Lập bảng quyết định chi tiết, thực hiện kiểm chứng có mục tiêu (targeted fault injection), triển khai một cleanup nhỏ ít rủi ro trong PR này và phân kỳ các bước tối ưu tiếp theo thành các PR nhỏ.

---

## 2. Thông số Môi trường và Lệnh Tái lập Baseline

- **Repository**: `nairyuuu/ad-weighted-graph`
- **Commit SHA audited**: `6fbb410db9b2371fbe6ce3149fe484c2de306da3` (latest `develop` tại thời điểm audit)
- **Hệ điều hành**: Windows 11 Pro (win32, x64, NTFS)
- **Python Version**: Python 3.14.7 (`C:\Users\LENOVO\AppData\Local\Programs\Python\Python314\python.exe`)
- **Pytest Version**: pytest 9.1.1, pluggy 1.6.0
- **Dependencies chính**:
  - `networkx`: 3.7
  - `pyyaml`: 6.0.3
  - `ruff`: 0.16.8
  - `yamllint`: 1.38.0
  - `typing-extensions`: 4.16.0
  - `iniconfig`: 2.3.0
  - `packaging`: 26.3

### Các lệnh đo lường baseline:

```powershell
# 1. Thu thập danh sách test cases sau parametrization
python -m pytest --collect-only -q

# 2. Đo runtime và top 30 test chạy chậm nhất
python -m pytest --durations=30

# 3. Thu thập dữ liệu thời gian chi tiết theo testcase/file
python -m pytest --junitxml=baseline.xml -q
```

---

## 3. Thống kê Baseline Định lượng theo Module và Toàn Suite

Bộ test suite bao gồm **45 file test**, **909 hàm test** (unique test functions/methods), sinh ra **1.638 collected test cases** sau parametrization.

### 3.1. Bảng phân bố theo 6 Phân hệ Kiến trúc (Module Breakdown)

| Phân hệ / Module | Số File | Số Hàm Test | Collected Cases | Passed | Skipped | Failed | Runtime (s) | Tỷ lệ Thời gian |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Parameters, Ratings & Release Governance** | 6 | 138 | 416 | 416 | 0 | 0 | 150.48s | 69.8% |
| **Parser & Graph Ingestion** | 17 | 250 | 428 | 428 | 0 | 0 | 33.51s | 15.5% |
| **Dataset EDA & Raw Telemetry Audit** | 5 | 44 | 51 | 51 | 0 | 0 | 15.21s | 7.0% |
| **Attack Semantics & Fact Resolution** | 8 | 80 | 198 | 198 | 0 | 0 | 7.23s | 3.4% |
| **Contract, Repository & Integrity** | 5 | 146 | 258 | 256 | 2 | 0 | 5.38s | 2.5% |
| **Path Search & Ranking Engine** | 4 | 251 | 287 | 287 | 0 | 0 | 3.91s | 1.8% |
| **TỔNG CỘNG (FULL SUITE)** | **45** | **909** | **1.638** | **1.636** | **2** | **0** | **215.70s** | **100.0%** |

*Ghi chú*: Runtime toàn suite ghi nhận 210.66s – 218.25s (~3 phút 35 giây).

### 3.2. Giải trình Trạng thái Skipped (2 cases)

Baseline ghi nhận đúng 2 cases skipped tại `tests/test_manifest.py`:
1. `tests/test_manifest.py:166`: `test_filesystem_normalization_collisions[names0]` — lý do: *"filesystem already aliases the two names"*. Trên hệ thống tập tin NTFS (Windows), các tên file như `"A"` và `"a"` mặc định coi là trùng nhau (case-insensitive), nên test kiểm tra va chạm tên trên hệ thống tập tin phân biệt chữ hoa/thường tự động skip hợp lệ.
2. `tests/test_manifest.py:201`: `test_nonportable_physical_filename_and_fifo_rejected` — lý do: *"Windows already rejects these filenames"*. Ký tự phân cách đường dẫn ngược trong tên file vật lý và cơ chế named pipe (`os.mkfifo`) không áp dụng cho Windows POSIX API.

**Kết luận baseline**: 100% test cases thực thi đều passed (1.636 passed, 2 skipped hợp lệ do nền tảng OS, 0 failed, 0 errors). Baseline hoàn toàn "xanh" và phản ánh trung thực môi trường thực thi.

---

## 4. Phân tích Bottlenecks và Top 30 Slowest Tests

Phân tích dữ liệu từ `baseline.xml` và `--durations=30` làm rõ một phát hiện quan trọng: **Số lượng test không phải là nguyên nhân gây chậm CI; nguyên nhân chính nằm ở việc lặp lại việc gọi tiến trình con OS (`subprocess.run([sys.executable, ...])`) trong các test CLI của các script nghiên cứu.**

### 4.1. Danh sách Top 30 Test Chậm nhất

| STT | Thời gian | Trạng thái | Test ID | Bản chất kỹ thuật |
| :---: | :---: | :---: | :--- | :--- |
| 1 | 5.77s | PASSED | `tests/test_ai_assisted_reviewed_release.py::test_ai_context_cli_and_offline_replay_preserve_sources` | Chạy 6 lần `subprocess.run` liên tiếp |
| 2 | 3.60s | PASSED | `tests/test_seamless_parameter_proposal.py::test_parameter_validation_cli_regressions` | Chạy nhiều lần `subprocess.run` |
| 3 | 2.65s | PASSED | `tests/test_seamless_parameter_proposal.py::test_parameter_validation_cli_negative_cases` | Chạy CLI qua subprocess |
| 4 | 2.51s | PASSED | `tests/test_seamless_parameter_proposal.py::test_canonical_engine_cli_fails_closed_on_legacy_or_malformed_inputs` | Chạy CLI qua subprocess |
| 5 | 2.38s | PASSED | `tests/test_eda_cli.py::test_deterministic_output_across_repeated_runs` | Chạy EDA script 2 lần qua subprocess |
| 6 | 1.98s | PASSED | `tests/test_reviewed_parameter_release.py::test_synthetic_demo_cli_produces_reviewable_inputs_and_cannot_overwrite` | Subprocess CLI export + overwrite check |
| 7 | 1.89s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[decision_reference]` | 2 lần subprocess / test case |
| 8 | 1.89s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[business_rationale]` | 2 lần subprocess / test case |
| 9 | 1.85s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[uncertainty_rationale]` | 2 lần subprocess / test case |
| 10 | 1.85s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[basis_category]` | 2 lần subprocess / test case |
| 11 | 1.83s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[source_references]` | 2 lần subprocess / test case |
| 12 | 1.82s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[effort_rationale]` | 2 lần subprocess / test case |
| 13 | 1.78s | PASSED | `tests/test_seamless_parameter_proposal.py::test_root_bundle_required_false_fact_rejected_and_canonical_blocked` | Subprocess canonical engine CLI |
| 14 | 1.66s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[resolution]` | 2 lần subprocess / test case |
| 15 | 1.62s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-effort]` | 2 lần subprocess / test case |
| 16 | 1.62s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-sources]` | 2 lần subprocess / test case |
| 17 | 1.59s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-basis]` | 2 lần subprocess / test case |
| 18 | 1.58s | PASSED | `tests/test_seamless_parameter_proposal.py::test_canonical_engine_cli_evaluates_proposed_fixtures_cleanly` | Subprocess CLI evaluation |
| 19 | 1.57s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-impact]` | 2 lần subprocess / test case |
| 20 | 1.57s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-uncertainty]` | 2 lần subprocess / test case |
| 21 | 1.56s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-reference]` | 2 lần subprocess / test case |
| 22 | 1.55s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-resolution]` | 2 lần subprocess / test case |
| 23 | 1.51s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[PENDING-rationale]` | 2 lần subprocess / test case |
| 24 | 1.50s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence[rationale]` | 2 lần subprocess / test case |
| 25 | 1.46s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_export_validate_and_failure_preserves_files` | Subprocess CLI export + validation |
| 26 | 1.40s | PASSED | `tests/test_eda_cli.py::test_cli_scoped_historical_preservation_is_explicit_and_recomputes_comparison` | Subprocess EDA CLI |
| 27 | 1.26s | PASSED | `tests/test_eda_cli.py::test_cli_successful_run_and_provenance_output` | Subprocess EDA CLI |
| 28 | 1.20s | PASSED | `tests/test_reconcile_graph_baseline.py::test_cli_accepts_actual_parser_lineage_and_exports_its_difference` | Subprocess reconcile CLI |
| 29 | 1.09s | PASSED | `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_rater_metadata[Unresolved-1]` | Subprocess CLI export |
| 30 | 1.09s | PASSED | `tests/test_audit_windows_telemetry_raw.py::test_verified_csv_inventory_is_stable` | Setup fixture đọc CSV 4.633 dòng x 326 cột |

### 4.2. Nhận xét Cốt lõi về Hiệu năng

1. **Sự tập trung runtime**: 5 file test (`test_reviewed_parameter_release.py`: 74.31s, `test_rating_sheet_reconciliation_review.py`: 49.20s, `test_reconcile_graph_baseline.py`: 24.62s, `test_seamless_parameter_proposal.py`: 17.90s, `test_eda_cli.py`: 10.71s) chiếm **176.74s / 215.70s (82% tổng thời gian)**.
2. **Đối nghịch với Core Engine & Parser**:
   - Toàn bộ 17 file của phân hệ Parser chỉ tốn **33.51s** (trong đó riêng file script so sánh baseline `test_reconcile_graph_baseline.py` đã chiếm 24.62s; 16 file core parser còn lại chỉ chạy trong **8.89s** cho 352 test cases).
   - Toàn bộ 4 file của phân hệ Search & Ranking Engine (`test_engine.py`, `test_engine_path_ranking_conformance.py`, `test_path_ranking_interface.py`, `test_worked_example_validation.py`) chạy 287 cases chỉ trong **3.91s**.
   - Toàn bộ 8 file của Semantics & Fact Resolution chạy 198 cases chỉ trong **7.23s**.
   - Toàn bộ Contract, Repo & Integrity chạy 258 cases chỉ trong **5.38s**.
3. **Cơ chế gây chậm**: Khởi tạo tiến trình Python mới (`python.exe`) trên Windows tốn khoảng 120ms–200ms mỗi lần. Khi một hàm test parametrize 16 hoặc 32 tổ hợp và mỗi tổ hợp gọi 2 lần `subprocess.run`, riêng chi phí khởi động process đã ngốn 5–10 giây cho một hàm test đơn lẻ.

---

## 5. Audit Giá trị Thực tế (8 Danh mục Đánh giá)

### Danh mục 1: Trùng input–hành vi–assertion
- **Phát hiện**: Trong `tests/test_contract.py`, hàm `test_zero_cost_is_rejected` gán `weights["MemberOf"] = 0` và assert `ValueError, match="finite and >= 1.0"`. Ngay phía trên nó là hàm `test_invalid_cost_is_rejected` parametrize `[-0.1, float("nan"), float("inf"), True, "1.0", None]` với cùng assertion. Cả hai đều kiểm tra cùng một nhánh điều kiện `value >= 1.0` trong `scripts/check_contract.py:1007`.
- **Hành động**: Đã gộp `0` vào danh sách parametrize của `test_invalid_cost_is_rejected` và loại bỏ hàm `test_zero_cost_is_rejected` thừa (đã kiểm chứng mutation).

### Danh mục 2: Mirror implementation hoặc khóa chi tiết nội bộ
- **Phát hiện**: Một số test trong `test_path_ranking_interface.py` kiểm tra các helper chuyển đổi số hữu tỉ (`parse_rational`, `format_rational`). Tuy nhiên, do interface wire adapter được phát triển độc lập bởi TTS A như một specification/oracle trước khi TTS B hiện thực hóa `src/engine/ranking/`, các helper này đóng vai trò chốt chặn tương thích giữa 2 thành viên và chạy cực nhanh (0.15s cho 72 cases), không tạo gánh nặng CI.
- **Quyết định**: Giữ nguyên vì có giá trị cross-review giữa A và B, không gây chậm.

### Danh mục 3: Assertions quá yếu
- **Phát hiện qua phân tích AST toàn bộ suite**: Phát hiện 16 vị trí assertion có thể yếu, ví dụ:
  - `test_engine.py:590`: `assert len(res_observed.evidence_backed_facts) > 0` và line 592 `assert len(res_observed.decisions) > 0`. Mặc dù dòng tiếp theo có kiểm tra `all(f.origin is FactOrigin.OBSERVED_EVIDENCE ...)`, việc chỉ assert độ dài `> 0` thay vì kiểm tra chính xác tập hợp fact names tạo nguy cơ bỏ sót nếu một fact mong đợi bị thiếu nhưng có một fact rác xuất hiện.
  - `test_seamless_parameter_proposal.py:1484` và `1503`: `assert len(c['work_unit_basis']) > 0`.
  - `test_structural_boundary_cases.py:301`: `assert len(edge['provenance']) >= 1`.
- **Khuyến nghị**: Trong các PR hoàn thiện engine, cần siết chặt các assertion này thành exact set/count matching.

### Danh mục 4: Fixtures & Helpers copy-paste gây chi phí bảo trì
- **Phát hiện**: Repository hiện **hoàn toàn chưa có `tests/conftest.py`**.
  - Định nghĩa hằng số `ROOT = Path(__file__).resolve().parents[1]` bị lặp lại độc lập ở **21 file test khác nhau**.
  - Các helper tạo dữ liệu thô `_raw`, `_builder`, `_record` bị copy-paste với cấu trúc gần như giống hệt nhau ở `test_builder_direct.py`, `test_graph_lineage.py`, `test_inference.py`, và `test_structural_boundary_cases.py`.
- **Hệ quả**: Khi schema `RawRecord` hoặc `provenance` thay đổi, maintainer phải sửa thủ công ở 4–5 file khác nhau.
- **Kế hoạch**: Tạo `tests/conftest.py` và module `tests/helpers/` trong follow-up PR để dùng chung fixtures.

### Danh mục 5: Parametrization có tổ hợp dư thừa không thêm semantics
- **Phát hiện điển hình**:
  1. `tests/test_reviewed_parameter_release.py`:
     - `test_cli_refuses_placeholder_rater_metadata`: Parametrize `sheet_number (2) x field (4) x sentinel (4) = 32 cases`. Mỗi case gọi `subprocess.run` OS! Tổng cộng 32 tiến trình OS chỉ để kiểm tra xem rater metadata có placeholder thì CLI có báo lỗi không.
     - `test_cli_refuses_placeholder_decisions_and_final_evidence`: Parametrize `8 field x 2 sentinel = 16 cases`. Mỗi case chạy subprocess 2 lần = 32 tiến trình OS (~23.5s). Bản chất chỉ kiểm tra hàm validator ném lỗi.
  2. `tests/test_rating_sheet_reconciliation_review.py`:
     - Hàm `assert_invalid` chạy `run_cli` 2 lần qua subprocess (check file tồn tại và unlinked). Được gọi trong hàng chục test cases (tổng cộng 121 cases ngốn 49.2s).
- **Giải pháp**: Giữ ma trận giá trị đầy đủ ở tầng Unit/API test (chạy trong bộ nhớ < 10ms); ở tầng CLI chỉ cần 1–2 test đại diện để xác nhận exit code và stderr.

### Danh mục 6: Checks docs/repository chạy lặp trong CI
- **Phát hiện trong `.github/workflows/ci.yml`**:
  - Job `quality` chạy: `python scripts/check_repository.py` (kiểm tra toàn bộ private paths, links markdown, định dạng worklog và ADR).
  - Job `tests` chạy ma trận trên cả 2 OS (`ubuntu-latest` và `windows-latest`):
    - Cả 2 OS đều chạy: `python scripts/check_contract.py`
    - Cả 2 OS đều chạy: `python -m pytest`
    - Trong `pytest`, file `tests/test_repository.py` lại chạy lại `test_all_existing_adrs_pass()`, `test_all_existing_worklogs_pass()`, và `test_all_markdown_files_have_valid_local_links()`.
- **Hệ quả**: Cùng một tập file tài liệu Markdown và ADR được đọc và kiểm tra cú pháp **3 lần riêng biệt** trong mỗi lần CI commit.
- **Kế hoạch**: Đưa việc kiểm tra committed docs vào duy nhất job `quality`; giữ trong `tests/test_repository.py` các unit test kiểm tra validator với dummy inputs.

### Danh mục 7: Test chậm có thể thu nhỏ fixture mà vẫn giữ hành vi
- **Phát hiện**: `tests/test_audit_windows_telemetry_raw.py` mất 1.18s trong setup để parse file CSV thực tế. Tuy nhiên tác giả đã dùng hợp lý `@pytest.fixture(scope="module")`, nên chi phí chỉ phát sinh một lần cho cả 4 tests trong file. Đây là thiết kế chấp nhận được.

### Danh mục 8: Gaps quan trọng dù số lượng test cao
- **Khoảng trống 1: PrimaryGroupSid và direct MemberOf gap (#187)**:
  - Báo cáo PR #184 chỉ ra chênh lệch 2.593 cạnh MemberOf giữa project parser và Legacy BloodHound 4.0.3 trên snapshot SEAMLESS. Toàn bộ bắt nguồn từ `PrimaryGroupSid` (2.493 User + 100 Computer).
  - Trên `develop`, parser chưa xử lý trường này thành direct membership. Branch `fix/187-primary-group-sid` đang xử lý riêng. Suite trên `develop` hiện chỉ có nhắc tới `PrimaryGroupSid` trong `test_eda_analysis.py`. Cần đảm bảo khi #187 merge, có đủ synthetic edge-case tests (RID vs full SID, boundary/missing scope, conflict dedup).
- **Khoảng trống 2: Golden Counterfactual Attack Scenarios (#175)**:
  - Hiện tại Week 3 có 8 acceptance cases trong `test_week3_engine_acceptance.py`. Tuy nhiên, các scenarios này phục vụ integration release của Week 3, chưa tạo thành bộ oracle độc lập chuẩn hóa cho bài toán dự đoán tương lai (future state prediction).
  - Branch `origin/feat/175-golden-attack-scenarios` đang bổ sung 25 files (12 golden attack graphs, `test_attack_scenarios.py`, `test_attack_scenarios_seamless.py`). Đây là regression tests cần thiết cho M3, tuyệt đối không được xóa hoặc gộp làm mất tính độc lập.

---

## 6. Bảo vệ Các Regression Tối thiểu (Traceability Matrix)

Bảng đối chiếu đảm bảo toàn bộ các bất biến tối thiểu theo yêu cầu đều có vị trí bảo vệ cụ thể:

| Trụ cột Invariant / Regression | Mã nguồn Production | Các Test Files & Test Cases Chủ chốt Bảo vệ | Khả năng Bắt lỗi (Fault Detection) |
| :--- | :--- | :--- | :--- |
| **1. Canonical Identity, SID Scope & Collision** | `src/parser/scopes.py`<br>`src/parser/normalizer.py`<br>`src/parser/well_known_principals.py` | `test_normalizer.py` (`test_local_sid_is_scoped`, `test_same_local_sid_in_two_scopes_never_collides`, `test_domain_sid_is_typed_stable_scope_and_separates_domains`)<br>`test_structural_boundary_cases.py`<br>`test_compare_group_identity_sets.py` | Ngăn chặn việc trộn lẫn các đối tượng cùng RID khác Domain SID; bắt lỗi đoán scope tùy tiện; chuẩn hóa uppercase canonical SID. |
| **2. Reconciliation, Order Invariance & Bảo toàn Raw Observations** | `src/parser/reconciliation.py`<br>`src/parser/lineage.py` | `test_parser_reconciliation.py` (`test_order_invariance_under_permutations`, `test_supplemental_records_retain_raw_representations`)<br>`test_normalizer.py` (`test_duplicate_merge_is_order_invariant_and_empty_stub_cannot_erase_data`)<br>`test_reconcile_graph_baseline.py` | Đảm bảo hoán vị thứ tự đọc record thô không làm đổi kết quả canonical graph; bảo toàn đầy đủ các raw representations và locator phục vụ audit. |
| **3. Provenance/Derivation/Lineage & Hướng Cạnh (Edge Direction)** | `src/parser/builder.py`<br>`src/parser/adapters/bloodhound_v3.py`<br>`src/parser/lineage.py`<br>`src/engine/semantics/transitions.py` | `test_graph_lineage.py` (`test_edge_direction_invariants`, `test_provenance_roundtrip`)<br>`test_m1_fixtures.py` (`test_fixture_edge_directions`)<br>`test_semantic_provenance.py`<br>`test_attack_semantics_transitions.py` | Kiểm soát chặt chẽ hướng cạnh theo ADR-0002 (`MemberOf`: User $\to$ Group; ACL: Principal $\to$ Target; `AdminTo`: Principal $\to$ Host). Truy vết 1-1 về raw source byte hash. |
| **4. Known-False, Unknown & Explicit Assumptions** | `src/engine/ranking/facts.py`<br>`src/engine/semantics/evaluator.py`<br>`src/engine/semantics/week3.py` | `test_engine.py` (`test_known_false_snapshot_evidence_blocks_despite_optimistic_runtime_fact`)<br>`test_week3_semantic_bridge.py` (`test_snapshot_false_vetoes_optimistic_enabled_fact`, `test_each_declared_gate_vetoes_or_stays_unknown`)<br>`test_worked_example_validation.py` | Ngăn chặn hiện tượng assumption ghi đè (override) dữ liệu known-false từ snapshot; phân định rõ giữa trạng thái blocked vs indeterminate khi thiếu thông tin. |
| **5. Fail-Closed Validation & Error Policies** | `src/parser/loader.py`<br>`src/parser/builder.py`<br>`scripts/check_contract.py`<br>`src/engine/ranking/validation.py` | `test_contract.py` (`test_invalid_cost_is_rejected`, `test_duplicate_identifiers_are_rejected`, `test_dangling_edge_is_rejected`)<br>`test_parser.py` (`test_default_fail_fast_stops_before_next_record`)<br>`test_parser_loader.py` (`test_snapshot_integrity_failures_ignore_skip_record`)<br>`test_manifest.py` | Từ chối ngay lập tức khi phát hiện dữ liệu hỏng, hash sai, dangling endpoint hoặc tham số vô lý, tuân thủ đúng chính sách `fail_fast` và `skip_record`. |
| **6. Search Budgets, State Transitions & Ranking Semantics** | `src/engine/search.py`<br>`src/engine/ranking/orchestration.py`<br>`src/engine/ranking/frontier.py` | `test_engine.py` (`test_semantic_cycle_is_finite_and_obeys_required_expansion_budget`, `test_shortest_path_uses_edge_local_additive_costs_and_exact_parallel_edge`)<br>`test_engine_path_ranking_conformance.py` (51 conformance tests)<br>`test_path_ranking_interface.py` (11 ranking tests) | Bảo vệ tính hữu hạn của đồ thị có chu trình; thuật toán Dijkstra với chi phí không âm; tính toán điểm Pareto frontier bảo thủ và tách biệt Min-Effort-to-DA. |

---

## 7. Bảng Quyết định Tinh gọn Cụ thể (Decision Table)

Theo đúng quy chuẩn: `test/group → hành vi bảo vệ → vấn đề/overlap → quyết định → rationale → test còn bảo vệ/thay thế → khả năng bắt lỗi có thể mất`.

| Test / Nhóm Test | Hành vi Bảo vệ | Vấn đề / Overlap | Quyết định | Rationale | Test còn Bảo vệ / Thay thế | Khả năng Bắt lỗi Mất |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: |
| `tests/test_contract.py::test_zero_cost_is_rejected` | Chặn trọng số cạnh bằng 0 trong profile contract | Trùng lặp hoàn toàn với `test_invalid_cost_is_rejected` (cùng assert `ValueError, match="finite and >= 1.0"`) | **Gộp (Consolidate)** | Đưa `0` vào `@pytest.mark.parametrize` của `test_invalid_cost_is_rejected`. Giảm 1 hàm test thừa mà không giảm collected case hay boundary. | `test_invalid_cost_is_rejected[0]` | **0%** (Đã chứng minh bằng fault injection) |
| `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_rater_metadata` | Chặn rater metadata chứa placeholder khi export release | Parametrize 32 tổ hợp (2 sheets x 4 fields x 4 sentinels), mỗi case chạy `subprocess.run` OS, ngốn ~15s | **Viết lại (Rewrite / In-process)** *(PR follow-up)* | Chuyển sang gọi `tool.main(...)` in-process với `capsys` hoặc test trực tiếp hàm API `export_release`. Giảm 15s runtime mà vẫn test đủ 32 trường hợp. | Giữ nguyên logic test, đổi runner từ OS subprocess sang Python call | **0%** |
| `tests/test_reviewed_parameter_release.py::test_cli_refuses_placeholder_decisions_and_final_evidence` | Chặn decision records chứa placeholder khi export release | Parametrize 16 tổ hợp x 2 lần chạy `subprocess.run` = 32 tiến trình OS (~23.5s) | **Tinh giản ma trận + In-process** *(PR follow-up)* | Giữ 1–2 test đại diện ở tầng CLI; toàn bộ 8 fields x 2 sentinels chuyển sang test qua hàm API `validate_decisions`. | `test_api_refuses_normalized_placeholder_disposition` + focused CLI test | **0%** |
| `tests/test_rating_sheet_reconciliation_review.py::assert_invalid` | Kiểm tra CLI báo lỗi và không ghi đè file output khi input rater sheet sai | Chạy 2 lần `subprocess.run` OS cho mỗi test case; lặp lại qua 121 cases ngốn 49.2s | **Chuyển tầng sang in-process** *(PR follow-up)* | Thay `subprocess.run` trong `run_cli` bằng `tool.main(cli(...))` (đã hỗ trợ sẵn trong script). Tiết kiệm ~45s runtime. | Giữ nguyên 121 cases, chạy in-process | **0%** |
| `tests/test_repository.py` (`test_all_existing_adrs_pass`, `test_all_existing_worklogs_pass`, `test_all_markdown_files_have_valid_local_links`) | Kiểm tra tính hợp lệ của các file Markdown/ADR đã commit trong repo | Chạy lặp lại tới 3 lần trong CI (job `quality`, job `tests (ubuntu)` và job `tests (windows)`) | **Phân tầng CI (CI Workflow Refactor)** *(PR follow-up)* | Giữ việc quét committed docs ở job `quality`. Trong `test_repository.py` chỉ giữ unit tests kiểm tra validator với dummy inputs. | `scripts/check_repository.py` trong job `quality` | **0%** |
| `tests/test_path_ranking_interface.py` (72 cases) vs `tests/test_engine_path_ranking_conformance.py` (147 cases) | `test_path_ranking_interface.py` bảo vệ contract wire adapter độc lập của A; `test_engine_path_ranking_conformance.py` bảo vệ engine conformance của B | Nhìn bề ngoài có vẻ cùng test ranking | **Giữ nguyên (Keep)** | Hai file kiểm tra hai ranh giới kiến trúc khác nhau (research adapter contract vs production engine). Cả hai chạy cực nhanh (0.15s và 0.65s). Giữ vai trò kiểm chứng độc lập giữa 2 maintainer. | Cả hai file được giữ nguyên | **0%** |
| `tests/test_inference.py` (`test_domain_admin_rid_alone_does_not_create_adminto` vs `test_domain_admin_rid_is_not_local_administrators_sid`) | Phân biệt Domain Admins RID 512 với Local Administrators SID 544 | Tên và setup fixture có vẻ giống nhau | **Giữ nguyên (Keep)** | Bảo vệ 2 boundary bảo mật Windows khác biệt: (1) DA không tự có AdminTo nếu thiếu local group; (2) RID 512 không bị nhầm lẫn với Builtin SID 544. | Cả hai test được giữ nguyên | **0%** |
| Các test fixtures/helpers trong `tests/test_builder_direct.py`, `test_graph_lineage.py`, `test_inference.py` | Cung cấp đối tượng đồ thị và raw records mẫu | Copy-paste helper `_raw`, `_builder`, `_record` ở 4 file | **Tái cấu trúc Fixture (Refactor Helpers)** *(PR follow-up)* | Tạo `tests/conftest.py` và module helpers chung, loại bỏ code trùng lặp mà không thay đổi bất kỳ test assertion nào. | Fixture dùng chung qua `pytest` | **0%** |
| Nhóm test Dataset EDA & Raw Telemetry Audit (`test_audit_*.py`, `test_eda_*.py`) | Kiểm tra tính toàn vẹn và tính tái lập của phân tích EDA | Runtime ~15s do xử lý CSV và so sánh lặp | **Đánh dấu Chưa kết luận (Inconclusive)** | Hiện tại là chốt chặn duy nhất đảm bảo tính tái lập của dữ liệu nghiên cứu; chưa có bằng chứng dư thừa về mặt nghiệp vụ. | Giữ nguyên | **0%** |

---

## 8. Bằng chứng Thực nghiệm và Kiểm chứng có Mục tiêu (Targeted Verification)

Để chứng minh rằng việc gộp `test_zero_cost_is_rejected` vào `test_invalid_cost_is_rejected[0]` không làm mất khả năng phát hiện lỗi, một thử nghiệm mutation có chủ đích đã được thực hiện:

1. **Gây lỗi đại diện**: Tạm thời sửa `scripts/check_contract.py:1007` từ điều kiện nghiêm ngặt:
   ```python
   and value >= 1.0,
   ```
   thành điều kiện nới lỏng cho phép trọng số bằng 0:
   ```python
   and value >= 0.0,
   ```
2. **Chạy kiểm tra lại**: Chạy `python -m pytest tests/test_contract.py -k "test_invalid_cost_is_rejected"`.
3. **Kết quả thu được**:
   ```text
   FAILED tests/test_contract.py::test_invalid_cost_is_rejected[0] - Failed: DID NOT RAISE ValueError
   ================= 1 failed, 6 passed, 117 deselected in 0.39s =================
   ```
4. **Kết luận**: Test case `test_invalid_cost_is_rejected[0]` ngay lập tức bắt được lỗi nới lỏng kiểm tra hợp đồng khi giá trị 0 bị lọt qua. Khả năng bảo vệ regression hoàn toàn tương đương 100% so với hàm độc lập cũ.
5. **Hoàn nguyên**: Đã hoàn nguyên lại điều kiện `value >= 1.0` trong `scripts/check_contract.py` và toàn bộ 124 tests của `test_contract.py` passed hoàn toàn.

---

## 9. Kết quả Đợt Cleanup Nhỏ trong PR Hiện tại

Trong phạm vi PR này, theo đúng hướng dẫn: *"Có thể thực hiện một nhóm cleanup nhỏ, rõ ràng, ít rủi ro trong cùng PR. Giữ cleanup lớn hoặc thay đổi chiến lược CI thành follow-up riêng"*:

- **Thay đổi thực hiện**: Gộp `test_zero_cost_is_rejected` vào `test_invalid_cost_is_rejected` trong `tests/test_contract.py`.
- **So sánh số lượng Trước và Sau**:
  - Số file test: **45** $\to$ **45** (giữ nguyên).
  - Số hàm test: **909** $\to$ **908** (giảm 1 hàm test trùng lặp code).
  - Số collected cases: **1.638** $\to$ **1.638** (giữ nguyên 100% các ca kiểm thử biên).
  - Kết quả pass/fail/skip: **1.636 passed, 2 skipped, 0 failed** (không đổi).
- **Runtime**: Dao động tự nhiên trong khoảng 210s – 218s (trung thực báo cáo, không khẳng định tăng tốc giả tạo từ dao động nhỏ vì cleanup lớn được tách ra follow-up).
- **Semantics**: Giữ nguyên 100% production semantics, không sửa expected output, không tạo test giả.

---

## 10. Tiêu chí Thêm Test Mới (Policy for Adding New Tests)

Để ngăn chặn việc test suite tiếp tục phình không kiểm soát trong tương lai, đề xuất áp dụng các tiêu chí sau trong Code Review:

1. **Nguyên tắc "Contract & Behavior First"**:
   - Mọi test mới phải chứng minh bảo vệ một contract, invariant hoặc regression bug có ý nghĩa (gắn kèm Issue ID / ADR).
   - Tuyệt đối không viết test chỉ để mirror các private helpers hoặc khóa chi tiết nội bộ dễ thay đổi mà không mang giá trị ngữ nghĩa an toàn AD.
2. **Quy tắc phân tầng kiểm thử CLI vs Unit**:
   - Kiểm thử logic xử lý nghiệp vụ, kiểm tra schema, validation giá trị và ma trận tổ hợp (sentinel, field list) phải được thực hiện ở tầng **Unit / in-process API test**.
   - Kiểm thử CLI (`cli.py`, `argparse`, subprocess) chỉ kiểm tra: (a) parse đúng cờ lệnh; (b) kết nối đúng luồng; (c) trả về exit code 0 khi thành công và exit code khác 0 khi thất bại; (d) atomic write / bảo vệ file ghi đè. Không lặp lại ma trận hàng chục tổ hợp field qua OS subprocess.
3. **Nguyên tắc Parametrization có Chọn lọc**:
   - Chỉ thêm tổ hợp tham số khi mỗi tổ hợp kích hoạt một nhánh logic (`if/else`), một boundary điều kiện (`< 1.0`, `NaN`, `Inf`) hoặc một ngữ nghĩa bảo mật khác nhau.
   - Tránh việc lấy tích Descartes ($N \times M \times K$) của các chuỗi tương đương nhau khi logic xử lý của chúng là chung một hàm chuẩn hóa.
4. **Tái sử dụng Fixtures qua `conftest.py`**:
   - Khi cần dữ liệu mẫu cho parser hoặc engine, sử dụng các fixture chuẩn hóa đã có thay vì copy-paste hàm sinh dữ liệu thô cục bộ.
5. **Không dùng Test Suite để thay thế Static Linter / CI Quality Checks**:
   - Các kiểm tra định dạng tài liệu, liên kết Markdown, cấu trúc worklog nên nằm trong script kiểm tra chất lượng repository chạy độc lập ở `quality` gate, tránh nhồi nhét vào `pytest` khiến runner chạy lặp lại trên mọi matrix OS.

---

## 11. Kế hoạch Các PR Tiếp theo theo Thứ tự Ưu tiên (Prioritized PR Plan)

| Ưu tiên | PR Dự kiến | Nội dung Kỹ thuật | Lợi ích Kỳ vọng | Checks cần Chạy |
| :---: | :--- | :--- | :--- | :--- |
| **P0 (PR này)** | PR Audit & Baseline Consolidation | Báo cáo audit #190, baseline đầy đủ, gộp `test_zero_cost_is_rejected` | Hoàn thành mục tiêu nghiệm thu #190; thiết lập baseline chuẩn | `check_contract.py`<br>`check_repository.py`<br>`pytest` |
| **P1 (Tiếp theo)** | In-process Review CLI Optimization | Chuyển đổi `run_cli` trong `test_rating_sheet_reconciliation_review.py` sang gọi trực tiếp `tool.main(...)` in-process | **Giảm ~45 giây runtime CI** (từ 49s xuống < 2s) mà giữ nguyên toàn bộ 121 cases | `pytest tests/test_rating_sheet_reconciliation_review.py`<br>Full test suite |
| **P2 (Tiếp theo)** | Streamline Reviewed Release CLI Matrix | Tinh giản ma trận subprocess trong `test_reviewed_parameter_release.py` (chuyển ma trận field sang unit test API) | **Giảm ~50–60 giây runtime CI** (từ 74s xuống < 15s) | `pytest tests/test_reviewed_parameter_release.py`<br>Full test suite |
| **P3** | Centralize Test Fixtures & Helpers | Tạo `tests/conftest.py`, module hóa các helper `_raw`, `_builder`, `_record` | Giảm nợ kỹ thuật và chi phí bảo trì; chuẩn hóa fixtures | Full test suite |
| **P4** | Streamline CI Repository Checks | Bỏ việc chạy kiểm tra docs/ADR trong `tests/test_repository.py` trên runner test matrix, chỉ chạy 1 lần ở job `quality` | Tránh lặp 3 lần kiểm tra docs trên Ubuntu và Windows | CI workflow run |
| **P5** | PrimaryGroupSid (#187) & Golden Scenarios (#175) | Tích hợp các regression tests cho #187 và #175 khi các branch này sẵn sàng | Bổ sung chốt chặn đúng chỗ mà không làm phình test suite vô căn cứ | Target acceptance tests |

