# Worklog - 2026-10-04 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #180 / #181 / M2 Week 3
- Thời gian thực tế ước lượng: khoảng 30 phút

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| UTF-8 portability | Probe and three regression modules | 75 tests pass with cp1252 default |
| Accepted handoff | docs/research/week3-semantic-bridge.md | #179 merged, accepted plan consumed |
| Raw inputs | Pinned SEAMLESS manifest | Six files verified; zero mismatches |

Latest review accepts the shared runtime policy and structural/capability boundary.
The remaining Windows failures come from locale-dependent text decoding of the
reviewed UTF-8 release. The bridge probe and its three new regression modules now
read/write JSON with explicit UTF-8. Probe decision diagnostics also retain fact
value and scope, allowing designated negative decisions to be checked against the
accepted manifest without losing the shared runtime policy.

## Điều học được / quyết định

The middle handoff paragraph now reflects merged #179 and consumption of its
accepted plan. Release, manifest pins, raw graph and ratings are unchanged.

## Trở ngại và việc kế tiếp

Validation: Python 3.14.7 with pinned requirements-dev.txt; the 75 bridge/pin/scope
tests pass with Path's default text encoding forced to cp1252. Full repository
checks and current-head raw evidence are recorded in the PR body after the final
code commit. The six recovered SEAMLESS inputs match the pinned raw manifest.
Raw graphs and full generated reports remain local under ignored data/report paths.
