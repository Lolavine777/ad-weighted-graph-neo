# Worklog — 2026-10-08 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #229 / PR #236; M3 / Week 4; PR vào develop sau checks.
- Thời gian thực tế ước lượng: khoảng 45 phút triển khai/checks/evidence tự động; chưa tính domain review và CI remote.

Refs #229, Refs PR #236; handoff #218/#206, nghiệm thu độc lập #208.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Implementation và oracle projection | `python -m pytest tests/test_rbcd.py` | 24 PASS: 3 minimal programs, 8 projected states, cutoffs, reuse, regressions |
| Replay trust boundary & Binding fixes | `orchestration.py`, `validation.py`, `verification.py`, `query.py` | Blockers P1 từ Lolavine777 resolved: RBCD buộc qua typed semantic replay; 1 binding/query; lineage trỏ đúng parent |
| Acceptance runner | `python -m scripts.research.week4_acceptance_runner --check-determinism` | W4-TECH-RBCD PASS; determinism PASS |
| Hai run CLI ON/OFF/RAW | Existing CLI schema 0.2 + compare contract #213 | Semantic/ordering deterministic (`sha256:8cbe84fd...`); ON asset reached conditional, OFF no path, RAW indeterminate |
| Private SEAMLESS | `seamless_inputs` | Pending authorized manifest-verified raw inputs |

## Điều học được / quyết định

1. **Ranh giới Replay và Lineage:**
   - Candidate validation yêu cầu các bước chuyển tiếp có cạnh cấu trúc (`GenericAll`) phải mang `origin="observed_edge"` và `derived_from_step=None`. Các bước sinh dẫn xuất (`RBCDPrepare`, `RBCDDelegate`, `RBCDAsset`) không có cạnh phải liên kết chính xác tới chỉ số bước cha sản sinh prerequisite (`origin="derived_transition"`).
   - Trong `adapter_145.py`, chỉ gắn `origin="snapshot_fact"` khi bước đó không có cạnh cấu trúc và không có bước cha dẫn xuất, tránh ghi đè sai lineage của bước có cạnh hoặc bước dẫn xuất.
2. **Nguyên tắc Replay Trust Boundary:**
   - Các kỹ thuật mở rộng credential và delegation (`OWNERS | RBCD_OWNERS`) bắt buộc phải được thẩm định qua tiến trình replay nội bộ đã xác thực (`SemanticReplayBinding`). Candidate envelope tự khai authoritative facts qua JSON sẽ bị từ chối fail-closed.
   - Mỗi query giới hạn tối đa 1 delegation binding để bảo toàn tính nhất quán của metadata xác thực và tránh xung đột ledger.
3. **Bảo toàn tính bất biến và unrated disposition:**
   - Canonical graph và SnapshotFacts hoàn toàn bất biến. Các quyền hay quan hệ sinh ra chỉ nằm trong AttackState cục bộ của nhánh duyệt.
   - Chưa có dữ liệu thực nghiệm về nỗ lực và xác suất trong Week 4 nên các work units của RBCD giữ nguyên disposition `unrated`.

## Trở ngại và việc kế tiếp

- Cập nhật nhánh PR #236 lên `origin/feature/229-rbcd` và yêu cầu `@Lolavine777` review lại sau khi đã giải quyết triệt để 4 blockers.
- Bàn giao kết quả thực nghiệm và oracle cho TTS A (#206) để phục vụ domain review và tích hợp nghiệm thu tổng thể (#208).
- Không tự merge PR vào develop hoặc đóng issue #229.

## Chi tiết giải quyết Review Blockers trên PR #236 (@Lolavine777)

1. **[P1] Replay trust boundary:**
   - Trong `src/engine/ranking/orchestration.py`, `replay_required` bao gồm `(OWNERS | RBCD_OWNERS)`.
   - Trong `src/engine/ranking/validation.py`, `validate_candidate_envelope` bắt buộc typed semantic replay cho RBCD. Envelope tự khai JSON mà không có verified binding sẽ bị reject (`RankingValidationError`).
2. **[P1] Binding identity:**
   - `adapter_145.py` serialize `request.rbcd_binding` vào `lineage_record["rbcd_binding"]`.
   - `verification.py` đối chiếu `rbcd_binding` trong lineage với `bound_rbcd_binding` trong query metadata.
   - `query.py` giới hạn `len(rbcd_bindings) <= 1` trong `materialize_query`; reject 2 colliding bindings.
3. **[P1] Lineage linking:**
   - Trong `search.py`, `TransitionStep` gắn đúng `derived_from_step` cho `RBCDPrepare`, `RBCDDelegate`, và `RBCDAsset`.
   - Trong `adapter_145.py`, chỉ gắn `origin = "snapshot_fact"` khi step không có edge và không có parent, giữ nguyên `origin = "derived_transition"` cho các derived steps.
4. **CI & Catalog Version Rebinding:**
   - Nâng catalog lên `0.6` sau khi tích hợp RBCD. Cập nhật digests trong suite fixtures và manifests.
   - Toàn bộ checks `ruff check .` đạt 100% clean.
