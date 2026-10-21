# Worklog - 2026-10-04 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #180 / #181 / M2 Week 3
- Thời gian thực tế ước lượng: khoảng 15 phút cho lần sửa này

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Sửa báo cáo giới hạn bước | `src/engine/search.py` | Pending acquire-identity và declared-host-admin được tính vào truncation |
| Giữ bằng chứng ACE độc lập | `src/engine/semantics/evidence_view.py` | Locator khác được giữ; coarse mapping có nhiều ACE trùng fail-closed |
| Regression | `tests/test_week3_semantic_bridge.py` | 7 ca mới; 6 fail trên parent, cả 7 pass sau sửa |
| Đồng bộ develop | `63fd005c16d8cc2e7323da2ff9da1f0b836d8bb2` | Giải quyết conflict terminal condition với #179 |
| Kiểm chứng | Lệnh bên dưới | 316 tests pass; Ruff check/format pass |

- Parent PR head: `9e97c6fe75090cd77c5b17775d591cfbb26a817e`.
- Develop integration: `63fd005c16d8cc2e7323da2ff9da1f0b836d8bb2` (#179).
- Step-cap detection now uses the same structural, withheld and capability relationship set as expansion. Pending acquire-identity and declared-host-admin transitions report step_limit_reached rather than complete no-path.
- Evidence fallback retains records with independent explicit locators. Coarse raw ACL mappings with multiple matching ACEs fail closed instead of withdrawing all same-record support.
- Added seven regression cases: two capability step caps, three locator variants, ambiguous coarse ACL support, and exact same-record ACE withdrawal. On the original parent, six fail and one passes; all seven pass after the fixes.
- Resolved the search terminal-condition conflict with develop while retaining target asset + declared success state handling.

Validation: CPython 3.12.14, networkx 3.7, PyYAML 6.0.3, pytest 9.1.1, Ruff 0.16.10. The focused engine/semantics/ranking suite passed 316 tests:

```bash
python -m pytest tests/test_week3_semantic_bridge.py tests/test_attack_semantics_catalog.py tests/test_attack_semantics_transitions.py tests/test_semantic_provenance.py tests/test_engine.py tests/test_engine_path_ranking_conformance.py -q
ruff check src/engine/search.py src/engine/semantics/evidence_view.py tests/test_week3_semantic_bridge.py
ruff format --check src/engine/search.py src/engine/semantics/evidence_view.py tests/test_week3_semantic_bridge.py
```

## Điều học được / quyết định

- Kiểm tra step cap phải xét cùng tập structural/withheld/capability relationships với expansion.
- Locator chính xác có ưu tiên hơn tuple file/record/attribute; mapping coarse không đủ phân biệt nhiều ACE phải từ chối thay vì xóa support độc lập.
- Giữ target asset + declared success state của develop. Không sửa release, oracle hoặc rating để khớp output.

## Trở ngại và việc kế tiếp

- Workspace không có raw SEAMLESS; chưa chạy lại actual probe tám ca hoặc full-suite tại local.
- Historical probe pins trong PR chỉ áp dụng head gốc, không chứng nhận merge revision mới.
- Required CI, final pinned acceptance và A review semantic ownership/evidence overlays vẫn cần trước merge; không đóng issue nghiệm thu.
- CI đầu tiên phát hiện worklog mới thiếu template metadata/headings/table; lần sửa kế tiếp bổ sung cấu trúc và kiểm tra bằng validator của repo.
