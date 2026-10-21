# Worklog - 2026-10-14 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #267, stacked on #271; Wave 2; `feature/267-wave2-delivery`.
- Thời gian thực tế ước lượng: khoảng 3 giờ gồm implementation, native replay, full suite và bàn giao; successor acceptance #289 đang chạy riêng.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Base và worktree | Base `b91a787`, chứa develop `16a3a21`; worktree riêng | #277/#282 đã merge vào nhánh #271, chưa vào develop; không đụng workspace đang chạy khác |
| Authority mới | [B decision 6163909537](https://github.com/nairyuuu/ad-weighted-graph/pull/271#issuecomment-6163909537) | Adopt đúng WinRM command, ACL/host, RBCD và Kerberoast material cùng finite-history pins; không duyệt lại số |
| Production release | [Adopted subset](../research/ratings/final-cpi-release-v2/decisions.adopted.json) | Reviewer/reference/timestamp thật; giữ pending candidate và archived releases |
| C-only scope guard | [Scoped C artifact](../research/ratings/final-cpi-release-v3/decisions.adopted-c-scoped.json) | Direct CLI từ chối withheld diagnostic contexts; roasting chỉ bind approved recovery C=2/3, không grant P/I hoặc recovered activation |
| Earlier smoke / correction | Native WinRM v4, Top-K regression | WinRM 0/1 → 1/1 C/P/I ở v4; UTF-8 subprocess test sửa và 6 focused tests PASS; v5 lặp lại vì source pins thay đổi |
| Native evidence | [Results](../research/ratings/final-cpi-wave2-delivery-v5/results.md) | 14 case, 28 after CLI runs; original 48/50 → 49/50, supported raw 0/7 → 7/7, diagnostic 0/109 → 7/109; denominator giữ nguyên |
| Tests | Clean CI worktree và focused raw | 3001 passed, 109 skipped, 59 subtests passed; focused raw 24 passed; raw-enabled full suite bị dừng không được tính PASS |
| Quality / raw integrity | Ruff lint/format, YAML, contract, repository, compose, diff; six raw byte comparisons | Local PASS; dispatch chỉ wrap line sau executable evidence c1e2cb2; không claim remote CI PASS |
| Review guard follow-up | [#289](https://github.com/nairyuuu/ad-weighted-graph/pull/289), stacked trên #288 | Review phát hiện aggregate thiếu query/run2/type guards. Read-only audit xác minh retained v5 đúng cả 14 case; successor thêm corruption tests và đang replay v7, chưa claim PASS |
| Independent successor check | Detached audit worktree tại `0b23392`; `pytest tests/test_final_cpi_delivery_replay.py -q` | 7 passed trong 197.83s với real manifest-verified raw directory; Ruff lint/format PASS; không sửa nhánh đang chạy, merge hoặc tự approve |

## Điều học được / quyết định

User báo có quyết định mới trên remote; đã fetch và đọc actual B decision thay vì
xin duyệt lại 17 numeric class. Adoption giữ nguyên exact context/history scope.
Direct effort-only CLI cũng cần tôn trọng hai diagnostic domains được B withheld;
guard được siết trước final replay, với version successor giữ artifact trước.

Một lần chuẩn bị raw qua junction tạo bản sao lồng và đầy ổ E:. Đã dừng tiến trình,
xóa riêng bản sao vừa tạo, kiểm manifest và đối chiếu byte của cả sáu raw files.
Native raw input sau đó dùng absolute authorized directory; không đổi raw evidence.
Các lượt bị dừng hoặc source-pin cũ được giữ local, không publish như final evidence.

## Trở ngại và việc kế tiếp

Đã hoàn tất mười bốn v5 native checkpoints, aggregate/recount, coverage, năm worked
paths và local required checks. #289 cần hoàn tất fresh successor acceptance và
exact-head cross-review trước khi aggregate được coi là acceptance-ready. Recovery P/recovered activation,
User-goal attribution, RDP/HasSession policy/raw absence và wider sensitivity vẫn
được bàn giao trong [grouped novelty packet](../research/ratings/final-cpi-wave2-delivery-v5/B-decision-packet.md).
Không merge, tự approve numeric extension hoặc đóng #267.
