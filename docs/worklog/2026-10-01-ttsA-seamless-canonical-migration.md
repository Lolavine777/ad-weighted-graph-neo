# Worklog - 2026-10-01 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#162](https://github.com/nairyuuu/ad-weighted-graph/issues/162), [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [#155](https://github.com/nairyuuu/ad-weighted-graph/issues/155), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) / PR branch `fix/162-seamless-canonical-migration` / M2 Week 3
- Thời gian thực tế ước lượng: Không đo thời lượng phiên sửa; không suy giờ làm từ số lệnh hoặc thời gian test.

## Kết quả và bằng chứng

Worklog này ghi nhận kết quả thực hiện của TTS A (@Lolavine777) cho Issue #162 sau khi tích hợp PR #156 (commit `4788139`) và PR #161 (commit `952a58b`) từ `develop`.
Worklog cũng ghi nhận việc hoàn thiện khắc phục toàn diện 5 phát hiện từ review round 1 và 3 phát hiện từ review round 2 trên PR #163.
Công việc bao gồm: tái lập lỗi packet -> engine (exit code 2), kiểm kê toàn diện các khác biệt giữa wire schema và Specification 1.0.0 chuẩn tắc của TTS B.
Công việc bao gồm xây dựng và làm dày (hardening) bộ chuyển dịch có phiên bản (versioned migration adapter) trong `scripts/research/path_ranking_wire_adapter.py`.
Công việc bao gồm đồng bộ 4 fixture input và 4 fixture output, bổ sung kiểm thử tích hợp CLI và fail-closed, kiểm chứng sạch qua CLI/API của B.
Công việc bao gồm sửa nit link review #161 trong worklog cũ và đính chính attribution của các đợt review nội bộ.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| 1. Tái lập lỗi packet -> engine (Issue #162) | `.venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_proposed_query_input.json` | Tái lập chính xác mã thoát 2: `ValidationError: query.work_units_ledger.reset_password...: invalid overlap_state: 'distinct_work'`. |
| 2. Kiểm kê khác biệt cấu trúc wire vs canonical schema | [path-ranking-acceptance-disposition.md Mục 5.7](../research/path-ranking-acceptance-disposition.md) | Xác định 4 điểm khác biệt: overlap_state (distinct_work vs independent), technique_name, referenced_work_unit_ids rỗng trên đóng thụ động, scope_binding 7 trường bắt buộc, và provenance_locators cho từng cạnh route. |
| 3. Xây dựng adapter chuyển dịch có phiên bản | `scripts/research/path_ranking_wire_adapter.py` | Hiện thực từ điển `SEAMLESS_CANONICAL_EDGE_LOCATORS` và hàm `migrate_wire_payload_to_canonical(payload, target_version="1.0.0")` thực hiện chuyển đổi tự động với phiên bản; hỗ trợ tương thích ngược technique/technique_name. |
| 4. Đồng bộ 4 fixture đầu vào chuẩn tắc | `tests/fixtures/ranking/seamless_proposed_query_input.json`, `seamless_source_b_proposed_query_input.json`, `seamless_query_input.json`, `seamless_source_b_query_input.json` | Cập nhật overlap_state="independent", bổ sung technique_name, gán scope_binding 7 trường, và bổ sung provenance_locators khớp 100% với Specification 1.0.0. |
| 5. Đồng bộ 4 fixture kết quả đầu ra chuẩn tắc | `tests/fixtures/ranking/seamless_proposed_expected_output.json`, `seamless_source_b_proposed_expected_output.json`, `seamless_expected_diagnostics.json`, `seamless_source_b_expected_diagnostics.json` | Common projection khớp chính xác với research oracle; canonical-only audit fields (parameter_audit, work_unit_basis, conditional_bounds_basis, diagnostic_reasons) được đối chiếu riêng rẽ. |
| 6. Sửa nit review ID #161 | `docs/worklog/2026-10-01-ttsA-seamless-parameter-proposal.md` dòng 9 và dòng 62 | Sửa `review 3290616335` thành link review chính thức `https://github.com/nairyuuu/ad-weighted-graph/pull/161#pullrequestreview-5380395316`. |
| 7. Kiểm chứng thực thi CLI Engine B | `.venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_proposed_query_input.json --output /tmp/seamless-a-ranking.json` và `.venv/bin/python -m src.engine.ranking.cli --input tests/fixtures/ranking/seamless_source_b_proposed_query_input.json --output /tmp/seamless-b-ranking.json` | Cả hai lệnh thoát với mã 0 sạch sẽ; kết quả xuất ra có common projection khớp chính xác với research oracle và giữ nguyên vẹn toàn bộ audit/basis. |
| 8. Bổ sung kiểm thử chuyên biệt và kiểm thử hồi quy | `tests/test_seamless_parameter_proposal.py` | 24/24 tests pass, bao gồm các bài kiểm thử hồi quy fail-closed cho cost mismatch, invalid types, version dispatch (bắt buộc non-empty string, từ chối null/missing), scope_binding (bắt buộc đủ 7 trường nếu dictionary đã tồn tại, từ chối rỗng/thiếu), canonical projection đối chiếu 4 flows, và false/unknown gating cho cả hai nguồn A và B. |
| 9. Bảo toàn phiếu đánh giá con người | `tests/fixtures/ranking/seamless_rater_1.json`, `tests/fixtures/ranking/seamless_rater_2.json` | Hai phiếu duy trì nguyên vẹn ở trạng thái pending/unrated; không tự ý điền thông tin hay điểm số. |
| 10. Kiểm tra chất lượng toàn diện | `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/yamllint`, `scripts/check_contract.py`, `scripts/check_repository.py`, `git diff --check` | Toàn bộ 1089 tests pass (11 tests skip hợp lệ do môi trường raw data); ruff check và format clean; yamllint clean; contract và repository checks pass sạch. |

### Khắc phục chi tiết 5 phát hiện từ Review Round 1 (PR #163)

1. **[P1] Lỗi giải mã UTF-8 trên môi trường Windows CI:**
   - Nguyên nhân: Việc mở file bằng `Path.read_text()` hoặc `open()` mà không khai báo tường minh `encoding="utf-8"` khiến môi trường Windows mặc định sử dụng codepage `cp1252`, dẫn đến lỗi `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81`.
   - Khắc phục: Bổ sung tường minh `encoding="utf-8"` vào tất cả các điểm đọc ghi file trong `scripts/research/seamless_parameter_validation.py`, `scripts/research/seamless_packet_evidence.py`, `tests/test_seamless_packet.py`, và `tests/test_seamless_parameter_proposal.py`.
   - Kiểm chứng: Chạy kiểm thử giả lập giải mã với codec `cp1252` và xác nhận đã xử lý triệt để nguyên nhân gốc rễ.
   - Kết quả CI: Toàn bộ kiểm thử trên Windows CI đã chạy thành công trong 1 phút 13 giây.

2. **[P1] Tránh ghi đè chi phí đã khai báo và che giấu xung đột tham số:**
   - Nguyên nhân: Trước đó hàm migration tự động tính toán lại và gán đè `effort_cost` / `computed_cost` theo công thức rubric `t1 + t2 - 2`, khiến các trường hợp dữ liệu khai báo sai lệch cố ý (như `effort_cost: 3` hoặc `999`) bị ghi đè ngầm thay vì từ chối an toàn.
   - Khắc phục: Cập nhật `migrate_wire_payload_to_canonical` từ chối fail-closed (`ValueError`) khi có xung đột chi phí trong dải (within-scale: khai báo 3 vs kỳ vọng 1), ngoài dải (out-of-scale: 999), hoặc xung đột bí danh (`effort_cost != computed_cost` hoặc `rubric.computed_cost != effort_cost`); hàm chỉ tự động suy dẫn và điền chi phí khi các trường này vắng mặt hoặc mang giá trị `None`.
   - Kiểm chứng: Bổ sung test case `test_migration_cost_mismatch_and_contradictory_aliases_fail_closed` xác nhận fail-closed qua chuỗi `migration -> engine`.

3. **[P1] Xác thực kiểu dữ liệu nghiêm ngặt và từ chối bí danh mâu thuẫn:**
   - Nguyên nhân: Trước đó các kiểu dữ liệu sai (ví dụ `technique_name=123`) bị ép kiểu ngầm bằng `str()`, các trường boolean giả (`scope_binding=False`, `provenance_locators=False`) bị coi là vắng mặt do kiểm tra falsy, và các bí danh mâu thuẫn (`technique_name="reset_password"` vs `technique="other"`) bị ghi đè im lặng.
   - Khắc phục: Bổ sung kiểm tra kiểu dữ liệu nghiêm ngặt (chuỗi không rỗng cho kỹ thuật, từ điển cho `scope_binding`, mảng chuỗi cho `provenance_locators`), từ chối fail-closed (`TypeError` hoặc `ValueError`) khi kiểu dữ liệu sai hoặc bí danh xung đột, và chỉ tiêm cấu trúc mặc định khi khóa hoàn toàn vắng mặt.
   - Kiểm chứng: Bổ sung test case `test_migration_invalid_types_and_conflicting_aliases_fail_closed`.

4. **[P2] Điều phối phiên bản và giới hạn phạm vi bảng locator mặc định:**
   - Nguyên nhân: Trước đó hàm migration chấp nhận ghi đè bất kỳ phiên bản nào thành `1.0.0` mà không kiểm tra tính tương thích, và gắn bảng locator mặc định của SEAMLESS cho mọi snapshot bất kể SHA.
   - Khắc phục: Khai báo tường minh ma trận phiên bản được hỗ trợ (`SUPPORTED_SOURCE_VERSIONS = {"legacy_draft", "1.0.0-draft", "1.0.0"}`, `SUPPORTED_TARGET_VERSIONS = {"1.0.0"}`); giới hạn bảng locator mặc định `SEAMLESS_CANONICAL_EDGE_LOCATORS` đúng cho snapshot đã kiểm định `AUDITED_SEAMLESS_SNAPSHOT_ID = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"`; với snapshot khác, yêu cầu phải truyền `edge_locators_table` tường minh hoặc từ chối fail-closed; kiểm tra và từ chối xung đột ánh xạ locator.
   - Kiểm chứng: Bổ sung test case `test_migration_version_dispatch_and_snapshot_pinning`.

5. **[P2] Bằng chứng kết quả chuẩn tắc và làm rõ biên Pareto:**
   - Nguyên nhân: Mô tả trong PR body và worklog trước đó gây hiểu nhầm về số lượng ứng viên trên biên Pareto; đồng thời các fixture mong muốn của nhóm nghiên cứu khớp với `execute_ranking_roundtrip` (vốn không chứa các trường kiểm định nội bộ của engine B).
   - Khắc phục: Làm rõ kết quả frontier: Source A có HAI ứng viên trên biên Pareto (`cand_seamless_01_direct_lidia` và `cand_seamless_02_alt_vajer_ollie`), Min Effort = 2 (`cand_seamless_01_direct_lidia`).
   - Khắc phục: Source B có MỘT ứng viên trên biên Pareto (`cand_seamless_source_b_01_ollie`), Min Effort = 2.
   - Khắc phục: Phân định rõ hai tầng kết quả: Fixture mong muốn của nghiên cứu đại diện cho oracle giao diện roundtrip; còn engine chuẩn tắc B qua `PathRankingEngine.evaluate()` và CLI xuất đầy đủ `parameter_audit` ở tầng gốc cùng `work_unit_basis`, `conditional_bounds_basis`, `diagnostic_reasons` bên trong từng ứng viên.
   - Khắc phục: Hiệu chỉnh milestone chính xác là `M2 Week 3` (không phải "M3").
   - Kiểm chứng: Bổ sung test cases `test_canonical_engine_proposal_a_and_b_full_audit_contract` và `test_canonical_engine_pending_and_gating_behavior`.

### Khắc phục chi tiết 3 phát hiện từ Review Round 2 (PR #163)

1. **[P2] Bắt buộc source version tường minh, từ chối null và missing version:**
   - Nguyên nhân: Trước đó biểu thức `source_version = meta.get("version")` kết hợp với `if source_version is not None:` khiến `version: null` hoặc payload vắng mặt khóa `version` bỏ qua hoàn toàn bước kiểm tra tính hợp lệ và bị tự động gán thành `1.0.0`.
   - Khắc phục: Cập nhật `migrate_wire_payload_to_canonical` yêu cầu khóa `version` bắt buộc phải hiện diện và không mang giá trị `None` (từ chối fail-closed với `ValueError("Missing required query_metadata field: 'version'")`); yêu cầu `version` phải là chuỗi ký tự không rỗng thuộc tập `SUPPORTED_SOURCE_VERSIONS` (từ chối kiểu sai với `TypeError`, chuỗi rỗng hoặc phiên bản không hỗ trợ với `ValueError`).
   - Kiểm chứng: Bổ sung các bài kiểm tra trong `test_migration_version_dispatch_and_snapshot_pinning` xác nhận cả direct engine và migration đều từ chối an toàn khi thiếu phiên bản, phiên bản rỗng, phiên bản null, hoặc phiên bản không phải dạng chuỗi.

2. **[P2] Xác thực nghiêm ngặt scope_binding đã tồn tại và chỉ suy dẫn khi hoàn toàn vắng mặt:**
   - Nguyên nhân: Trước đó nhánh xử lý từ điển `scope_binding` đã khai báo tiếp tục tự động bổ sung mọi required field còn thiếu, khiến payload chứa `scope_binding: {}` hoặc dictionary chỉ có `query_id` bị lấp đầy ngầm thành 7 trường mà không chứng minh được ứng viên thuộc về snapshot/scenario/foothold/horizon nào.
   - Khắc phục: Cập nhật `migrate_wire_payload_to_canonical` quy định rõ: nếu khóa `scope_binding` đã hiện diện trong candidate, bắt buộc phải là dictionary và phải chứa đủ tất cả 7 trường bắt buộc (`query_id`, `scenario_id`, `scenario_version`, `snapshot_id`, `work_boundary`, `horizon`, `foothold_node_id`) với giá trị dạng chuỗi không rỗng khớp hoàn toàn với `query_metadata`; từ chối fail-closed (`ValueError`) nếu rỗng hoặc thiếu bất kỳ trường nào; hàm CHỈ tự động suy dẫn và tiêm template 7 trường khi khóa `scope_binding` hoàn toàn vắng mặt trong cấu trúc dữ liệu legacy được hỗ trợ.
   - Kiểm chứng: Bổ sung các bài kiểm tra trong `test_migration_invalid_types_and_conflicting_aliases_fail_closed` xác nhận fail-closed cho dictionary rỗng, dictionary từng phần, kiểu sai, và xung đột giá trị, đồng thời bảo toàn positive regression cho trường hợp legacy không chứa khóa `scope_binding`.

3. **[P2] Bổ sung hàm chiếu canonical projection, đối chiếu giá trị audit và bao phủ gating hai nguồn:**
   - Nguyên nhân: Các bài kiểm tra trước đó chủ yếu xác nhận sự hiện diện của audit keys và tính không rỗng của basis, chưa đối chiếu giá trị audit/basis với dữ liệu đầu vào và chưa so sánh toàn bộ common result với research oracle trên cả 4 fixtures thực tế; bài kiểm tra pending trước đó sử dụng biến thể mock thay vì chạy fixtures pending A/B thực tế; và các ca false/unknown mới chỉ bao phủ Source A.
   - Khắc phục: Xây dựng hàm trợ giúp `project_canonical_to_common` phân tách 4 trường audit chỉ có ở tầng canonical (`parameter_audit`, `work_unit_basis`, `conditional_bounds_basis`, `diagnostic_reasons`) và chuẩn hóa thứ tự danh sách lý do chẩn đoán; thực hiện so sánh chính xác tuyệt đối toàn bộ kết quả chung (`search_metadata`, `eligible_candidates` với khoảng xác suất/nỗ lực/tác động/routes/gates/coverage, `pareto_frontier`, `min_effort_to_da_baseline`) với research oracle fixtures cho cả 4 luồng thực tế (Proposal A/B và Pending A/B).
   - Khắc phục: Đối chiếu bảo toàn giá trị chính xác của `parameter_audit` (khớp hoàn toàn với metadata, sổ cái work units, bảng điều kiện biên, và đánh giá tác động) và các bản ghi basis của từng ứng viên.
   - Khắc phục: Mở rộng kiểm thử phủ kín cả hiện tượng phủ quyết sự kiện sai (false fact veto) và cổng sự kiện chưa biết (unknown fact gating) cho cả Source A và Source B.
   - Khắc phục: Đồng bộ bảng worklog dòng 18 và 20 từ việc tuyên bố "full-match 100% expected output" thành "common projection khớp; canonical audit được đối chiếu riêng" để khớp chính xác giữa bằng chứng kiểm thử và tài liệu diễn giải.

### Khắc phục chi tiết 2 blocker và 1 nit từ Review Round 3 (PR #163)

1. **[Blocker 1] Từ chối fail-closed khi thiếu `requires` hoặc `adds` thay vì silently heal thành `[]`:**
   - Nguyên nhân: Trước đó adapter sử dụng `act.setdefault("requires", [])` và `act.setdefault("adds", [])`.
   - Cơ chế này có thể biến một action bị lỗi malformed hoặc thiếu trường thành action không có prerequisite hoặc effect, khiến engine canonical phía sau vô tình chấp nhận.
   - Đây chính là lớp lỗi false-positive mà TTS B đã siết chặt trong PR #156, đòi hỏi danh sách rỗng hợp lệ phải được khai báo tường minh.
   - Khắc phục: Xóa bỏ hoàn toàn việc dùng `setdefault` rỗng ngầm trong adapter.
   - Bắt buộc cả hai trường `requires` và `adds` phải hiện diện tường minh dưới dạng danh sách (list) các chuỗi không rỗng (`str`) trên mọi layout (cả canonical và legacy draft).
   - Thiếu trường hoặc mang giá trị `None` sẽ kích hoạt `ValueError` fail-closed; sai kiểu dữ liệu sẽ kích hoạt `TypeError`.
   - Kiểm chứng: Thêm các ca kiểm thử hồi quy xóa trường `requires` khỏi action và xóa trường `adds` khỏi action trong `test_migration_invalid_types_and_conflicting_aliases_fail_closed`.
   - Xác nhận cả adapter migration và direct `PathRankingEngine.evaluate` đều từ chối an toàn fail-closed.

2. **[Blocker 2] Phân biệt rõ rệt layout canonical 1.0.0 thực thụ so với draft/precanonical layout:**
   - Nguyên nhân: Trước đó tập `SUPPORTED_SOURCE_VERSIONS` chứa cả `1.0.0`, và adapter cho phép một payload tự khai là `1.0.0` nhưng thiếu `scope_binding` hoặc `provenance_locators` được tự động chắp vá rồi nạp vào engine.
   - Điều này làm mất ý nghĩa fail-closed của phiên bản canonical: các lỗi chính tả hoặc thiếu trường bắt buộc trong payload canonical có thể bị bỏ qua như thể một bản nháp legacy.
   - Khắc phục: Bổ sung tham số cấu hình `source_layout: str | None = None` cùng tập layout hợp lệ `SUPPORTED_SOURCE_LAYOUTS = frozenset({"legacy_draft", "1.0.0-draft", "1.0.0", "canonical"})`.
   - Đối với canonical 1.0.0 thực thụ (`effective_source_layout in ("1.0.0", "canonical")`): Adapter thực hiện kiểm định nghiêm ngặt (identity/strict validation).
   - Bất kỳ sự thiếu sót nào của các trường bắt buộc (`scope_binding`, `provenance_locators`, `technique_name`, `referenced_work_unit_ids`, `rating_status`) hoặc việc sử dụng enum legacy (`overlap_state: "distinct_work"`) đều bị từ chối dứt khoát fail-closed (`ValueError`), tuyệt đối không tự chắp vá hoặc tiêm trường.
   - Đối với layout nháp/legacy (`effective_source_layout in ("legacy_draft", "1.0.0-draft")`): Adapter thực hiện chuyển đổi tương thích ngược: tự động suy dẫn và tiêm `scope_binding` từ metadata, tra cứu và bổ sung `provenance_locators` từ bảng locators được ghim, ánh xạ `distinct_work` sang `independent`, ánh xạ `technique` sang `technique_name`, gán `referenced_work_unit_ids: []` cho passive closure hoặc sao chép từ `bound_work_units`, và chuẩn hóa `status` sang `rating_status`.
   - Lưu trữ đầy đủ bằng chứng machine-readable trong `query_metadata`: bổ sung các trường `source_version`, `source_layout`, và `migration_audit = {"source_version": ..., "source_layout": ..., "target_version": "1.0.0", "migrated": is_legacy}` để tầng audit và người kiểm tra biết rõ đường dẫn chuyển dịch nào đã được kích hoạt.
   - Kiểm chứng: Cập nhật và bổ sung các bài kiểm tra trong `test_migration_invalid_types_and_conflicting_aliases_fail_closed` và `test_migration_version_dispatch_and_snapshot_pinning`.
   - Phân biệt rõ: canonical 1.0.0 thiếu trường bắt buộc hoặc chứa enum legacy sẽ fail closed; trong khi draft/legacy layout thiếu trường hoặc dùng bí danh sẽ chuyển dịch thành công và chạy mượt mà qua canonical engine.

3. **[Nit tài liệu] Cập nhật số liệu kiểm thử trong PR #163 body:**
   - Đồng bộ số lượng bài test trong phần mô tả của PR #163 (24 proposal tests, 229 focused tests, 1089 local full-suite / 1091 Ubuntu CI passed) và phân định rõ ràng giữa kết quả chạy cục bộ của tác giả và kết quả CI runner.

4. **Đính chính attribution cho các đợt review:**
   - Lưu ý rằng đợt review round 1, round 2, round 3 và round 4 đều là self-review do TTS A (@Lolavine777) thực hiện.
   - Hiện tại danh sách formal review độc lập từ vai trò TTS B (@nairyuuu) vẫn đang mở và chờ phản hồi chính thức.

5. **[Review Round 4 Blocker] Bảo đảm tính toàn vẹn bằng chứng trong điều phối layout (Layout Declaration Precedence & Conflict Rejection):**
   - Vấn đề: Trước đó tham số `source_layout=` ưu tiên đè lên khai báo layout đã có trong `query_metadata` (`payload_layout = meta.get("source_layout") or meta.get("layout")`).
   - Nếu caller truyền `source_layout="1.0.0-draft"` cho một payload đã tự khai `source_layout: "canonical"`, adapter sẽ coi payload như legacy draft, tự chắp vá các trường bắt buộc, rồi ghi đè `query_metadata.source_layout` và `migration_audit` thành draft.
   - Hành vi này làm mất dấu vết khai báo canonical ban đầu và bỏ qua bảo đảm fail-closed của canonical layout.
   - Đồng thời, cách kiểm tra bằng truthiness fallback (`or`) bỏ sót các giá trị giả như `""` hay `False`, và không phát hiện xung đột khi cả `source_layout` lẫn bí danh legacy `layout` cùng tồn tại nhưng mang giá trị khác nhau.
   - Khắc phục:
     - Kiểm tra sự hiện diện của `source_layout` và `layout` trong `query_metadata` mà không dùng truthiness fallback.
     - Validate dứt khoát kiểu chuỗi không rỗng thuộc danh mục layout hợp lệ (`SUPPORTED_SOURCE_LAYOUTS`), từ chối dứt khoát các giá trị rỗng hoặc sai kiểu (`TypeError`, `ValueError`).
     - Phát hiện và từ chối xung đột fail-closed (`ValueError`) nếu cả `source_layout` và `layout` cùng được khai báo nhưng có giá trị chuẩn hóa khác nhau.
     - Kiểm tra xung đột thứ tự ưu tiên: nếu caller truyền tham số `source_layout=` và payload cũng tự khai layout, từ chối fail-closed nếu hai giá trị chuẩn hóa khác nhau (`ValueError: Conflicting source_layout argument ... with declared payload layout ...`).
     - Chỉ cho phép override thành draft đối với các payload lịch sử bị dán nhãn nhầm 1.0.0 khi payload đó hoàn toàn chưa có khai báo layout trong metadata.
     - Mở rộng `migration_audit` để ghi nhận đầy đủ `source_version`, `declared_layout` (hoặc `None`), `source_layout` (profile hiệu dụng), `target_version`, và `migrated`.
   - Kiểm chứng:
     - Bổ sung bài kiểm thử hồi quy chuyên biệt `test_migration_layout_declaration_precedence_and_conflicts_fail_closed` trong `tests/test_seamless_parameter_proposal.py`.
     - Phủ toàn bộ các trường hợp: caller truyền tham số sai kiểu hoặc rỗng, payload tự khai sai kiểu hoặc rỗng, payload khai báo xung đột giữa `source_layout` và `layout`, payload khai canonical bị caller ép override draft (fail-closed), và payload lịch sử không khai layout được phép override draft thành công kèm audit đầy đủ.
     - Toàn bộ suite 25 proposal tests, 230 focused ranking tests và 1090 full-suite tests đều passed sạch sẽ cục bộ.

## Điều học được / quyết định

1. **Phân định ranh giới giữa Wire Protocol và Internal Engine Boundary:**
   - Trong quá trình cộng tác độc lập giữa hai vai trò (TTS A nghiên cứu mô hình hóa và ký kết hợp đồng, TTS B xây dựng engine tìm kiếm), việc phát sinh sai lệch nhỏ giữa wire protocol linh hoạt và parser nghiêm ngặt là điều tự nhiên.
   - Việc bổ sung một hàm chuyển dịch có phiên bản (`migrate_wire_payload_to_canonical`) tại ranh giới adapter thuộc sở hữu của A giúp bảo vệ tính toàn vẹn của engine B mà không cần sửa đổi mã nguồn engine của B.

2. **Tính phân biệt trong kế toán nỗ lực so với độc lập xác suất:**
   - Việc chuyển đổi từ `distinct_work` sang `independent` trong `work_units_ledger` chỉ mang ý nghĩa kế toán nỗ lực không trùng lặp (effort non-overlap accounting).
   - Quyết định này không làm thay đổi hay suy diễn bất kỳ điều gì về tính độc lập thống kê của các biến cố xác suất, vốn luôn được điều kiện hóa theo toàn bộ lịch sử tiền tố.

3. **Nguyên tắc an toàn fail-closed:**
   - Việc engine B trả về mã lỗi exit code 2 khi gặp schema sai lệch là hành vi chính xác và bảo đảm an toàn theo nguyên tắc fail-closed.
   - Các bài kiểm thử mới đã bao phủ cả trường hợp thành công (exit 0) và các trường hợp thất bại có chủ đích (exit 2) để ngăn chặn hồi quy.

## Trở ngại và việc kế tiếp

1. **Trở ngại đã giải quyết:**
   - Đã khắc phục hoàn toàn lỗi exit code 2 khi nạp fixtures SEAMLESS vào CLI của engine B.
   - Đã xử lý triệt để 5 vấn đề từ review round 1 (mã hóa UTF-8 Windows, kiểm tra chi phí fail-closed, xác thực kiểu dữ liệu, điều phối phiên bản và giới hạn snapshot, chuẩn hóa bằng chứng kết quả).
   - Đã xử lý triệt để 3 vấn đề từ review round 2 (bắt buộc source version tường minh, xác thực nghiêm ngặt scope_binding hiện hữu, bổ sung projection helper đối chiếu 4 fixtures và phủ gating hai nguồn).
   - Đã xử lý triệt để 2 blocker và 1 nit từ review round 3 (loại bỏ silent healing cho missing requires/adds, tách biệt profile canonical 1.0.0 strict identity khỏi draft layout migration, lưu machine-readable migration audit, và cập nhật số liệu kiểm thử).
   - Đã xử lý triệt để 1 blocker evidence-integrity cuối từ review round 4 (bảo đảm thứ tự ưu tiên khai báo layout fail-closed, từ chối xung đột giữa tham số và metadata, xác thực falsy/type, và lưu trữ declared_layout trong migration_audit).
   - Đã cập nhật đúng liên kết review PR #161 trong worklog cũ, đính chính attribution, và định danh milestone M2 Week 3.

2. **Việc kế tiếp:**
   - Cập nhật Pull Request #163 vào nhánh `develop` với đầy đủ liên kết và mô tả kiểm chứng.
   - Chờ TTS B (@nairyuuu) thực hiện review độc lập cho các thay đổi mới này.
   - Tiếp tục duy trì các phiếu rater con người ở trạng thái unrated/pending cho đến khi có nhân sự đánh giá độc lập.
   - Không tự ý merge PR và không tuyên bố Week 3 hoàn tất.
