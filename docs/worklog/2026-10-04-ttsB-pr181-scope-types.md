# Worklog - 2026-10-04 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #180 / #181 / M2 Week 3; reviewer blockers 2 và 3
- Thời gian thực tế ước lượng: khoảng 10 phút cho lần sửa scope/types

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Runtime builder chung | `projection_runtime.context_for_projection` | Probe và harness #179 dùng chung resolver/origin/scope policy |
| Scope parity | `tests/test_week3_scope_and_types.py` | Horizon cho assumption, scenario cho false/unknown, None cho observed |
| Known-false veto | Shared release resolver | False ưu tiên khi overlay giữ true assumption; override không nâng false |
| Structural/capability boundary | `models.py`, `state.py`, `search.py`, `evaluator.py` | Structural vocabulary đúng 8 kinds; capability trigger riêng; state/evidence từ chối capability |
| Actual release projections | 8 cases trong pinned manifest | Facts/scope của probe và harness khớp trên cả tám ca |
| Regression và kiểm chứng | Lệnh bên dưới | 368 passed; 26 scope/type cases; Ruff check/format pass |

Parent head: `97e537c794e9c178b78dc228397f5e7e671c2d9b`.
Local runtime: Python 3.12.14, networkx 3.7, PyYAML 6.0.3, pytest 9.1.1, Ruff 0.16.8.

```bash
python -m pytest tests/test_week3_scope_and_types.py tests/test_week3_engine_acceptance.py tests/test_week3_bridge_pins.py tests/test_week3_semantic_bridge.py tests/test_attack_semantics_catalog.py tests/test_attack_semantics_transitions.py tests/test_semantic_provenance.py tests/test_engine.py tests/test_engine_path_ranking_conformance.py -q
```

## Điều học được / quyết định

- Reuse runtime builder giữ scope/origin policy không drift giữa probe và final harness.
- Known-false overlays có thể giữ optimistic assumption cũ; resolver ưu tiên explicit false, các duplicate khác fail-closed.
- Technique có semantic trigger rộng hơn structural taxonomy; capability không phải structural evidence hoặc derived structural permission.
- Mixed search triggers sắp xếp theo source/kind/target để giữ deterministic traversal.
- Không đổi release, oracle, work/rating bindings hoặc canonical contract/raw data.

## Trở ngại và việc kế tiếp

- Actual release projection parity không thay actual raw SEAMLESS search/probe rerun; workspace không có raw để thực hiện tám actual search cases.
- Chờ full CI và A review exact head về semantic owners/evidence mappings; không tự đóng #180/#155/#48 hoặc merge PR.
