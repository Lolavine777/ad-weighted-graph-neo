# Worklog - 2026-10-04 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #155, #180, #48 / final integration
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng.
- Nguồn: develop 4d96bcfda8cb8ac3700431975690de8ce90dfccf (sau merge PR #183).

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Reconcile acceptance plan | `docs/research/ratings/week3-closeout/search-integration-plan.json` | Cập nhật schema 1.3.0, catalog 0.3, toàn bộ 15 action owners map `catalog_transition`, missing cases map `evidence_view` |
| Reconcile bridge plan | `docs/research/ratings/week3-closeout/semantic-bridge-plan.json` | Ghi nhận status `accepted_pr181`, reference PR #181 approval và search binding `mapped` |
| Final acceptance harness | `scripts/research/week3_engine_acceptance.py` | Hợp nhất semantic bridge và evidence view thật vào real-search acceptance harness; verify đủ 8 cases |
| Engine ranking orchestration | `src/engine/ranking/orchestration.py` | Tách rời hoàn toàn oracle IDs khỏi evaluator; candidate ID giữ danh tính generator `generated_{index:04d}`; audit counters `expansions`/`truncated` |
| Regression test oracle decoupling | `tests/test_engine_path_ranking_conformance.py` | `test_equal_effort_generated_candidates_independent_of_oracle_naming` chứng minh equal-effort tie breaking không bị ảnh hưởng bởi oracle naming |
| Projection runtime safety | `src/engine/semantics/week3.py` | An toàn hóa `runtime_for_projection` khi vắng ledger/authentication_context |
| Acceptance tests | `tests/test_week3_engine_acceptance.py` | 18 unit tests passed, cover closed ownership, missing evidence views, và designated decisions |
| Full Week 3 acceptance suite | `reports/generated/week3-acceptance/acceptance_summary.json` | Chạy đủ 8 cases × 2 runs (`PYTHONHASHSEED=0`) trên raw SEAMLESS; toàn bộ passed và khớp byte 100% |
| Documentation update | `docs/research/engine-ranking-integration.md` | Dọn sạch mâu thuẫn narrative: phân định rõ superseded historical checkpoints vs trạng thái tích hợp hoàn tất cuối cùng |

## Điều học được / quyết định

Sau khi PR #181 được A chấp thuận trên `develop`, semantic bridge và counterfactual evidence views đã trở thành normative implementation. Việc giữ hai plan riêng rẽ (`search-integration-plan.json` với gap cũ và `semantic-bridge-plan.json` với bridge mới) đã được giải quyết bằng cách hợp nhất:
1. Không dựng thêm harness thứ ba: toàn bộ luồng acceptance chạy duy nhất qua `scripts/research/week3_engine_acceptance.py`.
2. Giữ nguyên ranh giới cấu trúc/khả năng: không materialize các quan hệ capability (`AuthenticationControl`, `DeclaredHostAdmin`) thành cạnh cấu trúc canonical, không bịa đặt cạnh `AdminTo` hay `CanPSRemote`.
3. Bounded search trung thực: không replay/inject candidate oracle vào search output; candidate envelopes của release chỉ dùng làm oracle so sánh. Case Source A positive chạm `expansion_limit_reached` ở 60.000 expansions được ghi nhận minh bạch và không coi là lỗi.
4. Độc lập định danh đánh giá: Generator candidate IDs (`generated_{index:04d}`) được giữ nguyên qua toàn bộ quá trình evaluation, Pareto frontier và Min-Effort tie-breaking. Oracle naming chỉ được ánh xạ hậu ranking trong acceptance audit và report, đảm bảo không thể bẻ cong thứ tự xếp hạng do tên chuỗi oracle.
5. Designated decision matching: các case negative/unknown/missing kiểm tra chặt chẽ đúng technique, actor, target, predicate, status `blocked`/`indeterminate`, origin, value, scope và rationale.

## Trở ngại và việc kế tiếp

- Đã giải quyết triệt để cả 3 Change Request blockers từ reviewer @Lolavine777 trên PR #182.
- Đồng bộ merge latest `develop` (commit `4d96bcfda8cb8ac3700431975690de8ce90dfccf` chứa handoff Legacy #183).
- Toàn bộ 8 acceptance cases đã passed và khớp determinism tuyệt đối trên HEAD mới.
- Không tự ý đóng Issue #48 (E2E acceptance / product closeout); PR này đóng #155/#180 và hoàn tất handoff cho #48.
