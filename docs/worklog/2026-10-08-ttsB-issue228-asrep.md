# Worklog — 2026-10-08 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #228; M3 / Week 4; PR vào develop sau checks.
- Thời gian thực tế ước lượng: khoảng 30 phút triển khai/checks/evidence tự động; chưa tính domain review và CI remote.

Refs #228; handoff #218/#206, nghiệm thu độc lập #208.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Implementation và oracle projection | `python -m pytest tests/test_asrep.py` | 44 cases; focused AS-REP/mapping 58 PASS |
| Required checks / full suite | [Evidence](../research/evidence/asrep-228/README.md) | Clean `1753a4e`: 2106 PASS / 11 SKIP / 48 subtests PASS; required local checks PASS |
| Hai run CLI ON/OFF/RAW | Existing CLI schema 0.2 + compare contract #213 | Semantic/ordering deterministic; ON asset success conditional, OFF no path trong fixture, RAW indeterminate |
| Private SEAMLESS | `seamless_inputs` | Pending authorized manifest-verified raw |

Baseline `develop@f4d1f97`, worktree riêng `issue-228`, branch
`feature/228-asrep-roasting`; không sửa worktree/dữ liệu local khác.
Đã đọc CONTRIBUTING và GitHub issues/handoff; không có AGENTS.md hoặc PR mở #228.

Triển khai hai catalog owners `asrep_request`/`recover_asrep_secret`, material form
riêng và explicit request capability; reuse shared recovery, scoped activation,
query/search, typed replay, ranking và CLI. Source Computer không cần AD credential
hay control; knowledge/request/network scope vẫn bắt buộc. Matrix và concrete
proposal mapping A1–A5 nằm ở [tài liệu](../research/asrep-228.md).

Oracle JSON viết từ logic #218 trước actual, tests so exact projected programs và
states/cutoffs, false/missing/veto/reuse/context/isolation/lineage/caps. Rebind
catalog 0.5 sau structural equality toàn bộ entries cũ; không đổi expected
programs/states/ratings. Các focused checks đã phát hiện và sửa signature test,
metadata pin/capability exclusion và CRLF gây stderr trong CLI trên Windows.
Full suite chạy trên clean commit do parser CLI yêu cầu source đã commit.

## Điều học được / quyết định

[Evidence](../research/evidence/asrep-228/README.md) ghi kết quả clean runs và
required checks sau khi thực chạy. Actual private SEAMLESS pending do thiếu bộ
raw authorized/manifest-verified; có hàm chuẩn bị RAW/ASSUMED theo locators #218.
Không chạy cracking/live request, không suy synthetic true thành P=1.

## Trở ngại và việc kế tiếp

Mapping/domain review của A và independent cross-run/acceptance #206/#208 pending;
PR vào develop request @Lolavine777, không tự merge hoặc đóng issue.


## Cập nhật theo review PR #234

Review merge-gate 14:48 ngày 08/10 tái hiện hai P1. Đã merge develop #231,
resolve duy nhất `.gitattributes` bằng cách giữ cả hai LF policies. Sửa request
eligibility bảo thủ tại A1 và giữ initial-state declarations trong assumed ledger,
kiểm cả resolved origins/evidence-only. Giữ metadata #216 qua helper parameters.
Focused regressions: **143 PASS / 29.73s**, gồm **51 AS-REP cases**.

CLI ON hai lần ở source `97aa41b` cho semantic/ordering giống nhau; ON/OFF chỉ
đổi technique scope; RAW thiếu outcomes giữ indeterminate. Refresh evidence và
actual acceptance manifest riêng với oracle normative fields không đổi.
Existing #231 runner: **35 PASS, 1 PENDING B, 1 NOT EXECUTED, 1 BLOCKED RUN**,
không unexpected failures; determinism PASS. Mapping/domain review và private
replay #206/#208 vẫn pending, không tự claim được reviewer chấp nhận.


Full suite CI Ubuntu tại `f81d739`: **2127 PASS, 10 SKIP / 331.17s**.
Stale checksum trong demo của baseline được CI phát hiện và đã rebind theo
catalog input mới; chỉ đổi pin/disposition cần thiết, không viết lại báo cáo
Week 4. Quality/Compose/branch policy PASS. Final Windows/local và exact-head
CI được cập nhật trong PR sau khi các run hoàn tất. Skips do thiếu private
datasets và platform constraints, không gọi là PASS.
