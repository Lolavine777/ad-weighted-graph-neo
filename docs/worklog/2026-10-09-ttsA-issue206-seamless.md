# Worklog - 2026-10-09 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #206, #239, #208, #204 / [PR #243](https://github.com/nairyuuu/ad-weighted-graph/pull/243) / M3, Week 4; owner @Lolavine777, reviewer @nairyuuu.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Phạm vi và freeze

Đọc CONTRIBUTING, instructions cho docs/research/tests/data, bodies/latest comments của #204/#206/#208/#239 và current develop.
Core/query/facts/Min-Effort/CLI, Kerberoasting, AS-REP, RBCD đã merge tại baseline `be64798c89235f53c5c205894a7bac0f96437ce4`.
Không làm #237/#238 P2 research trong PR này, không sửa B engine/parser/catalog/CLI/harness hoặc oracle core accepted.
Tạo nhánh `docs/206-seamless-freeze` từ current develop trong worktree riêng, giữ nhánh nghiên cứu #237 của repo chính.

Raw vắng ở checkout nhưng nguồn pin đã có trong repo; đã tải archive pin `3febc4089421725f9527c187f78d064ad09d5158`, SHA-256 `b8e9f003dd51a98838be86d8f98b0844a19a7876aad0a81b525f19e110105813` khớp.
`snapshot_manifest.py verify` trả `issues=[]`, `status=verified` cho đủ sáu files/11.371.828 bytes, snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
Không ghi raw unavailable sau khi nguồn đã tải/verify thành công; full IDs/raw/snapshot/query/results giữ local/ignored theo data policy.

[Scenario/oracle](../research/scenarios/week4-seamless-v1.json) được commit tại `983ce542edad80d5b38d1cce97c7ca5db3b77cb5` trước public query đầu tiên.
X là Computer1, C0 là Computer0; initial chỉ known V_A và request capability `(X,X)`, không host control/usable AD identity/material/secret/admin.
Independent oracle có bốn bước request/recovery/activation/direct AdminTo, năm projected states, asset goal true và DA checkpoint false; controls định nghĩa trước actual.
Freeze SHA-256 `66c5ffef9a10d30d685f437b10d2998b0d57b96c2151c7eb9d00a0feeb0df752` không đổi.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Freeze + public generation | [Scenario](../research/week4-seamless-scenario.md), public CLI và frozen oracle | Bảy cases khớp; một generated program đạt asset dưới assumptions |
| Local regression | `.venv/bin/python -m pytest -q tests/test_week4_scenarios.py tests/test_asrep.py tests/test_rbcd.py tests/test_query_cli.py` | 139 passed |
| Public artifact | [Actual](../research/scenarios/week4-seamless-v1-actual.json), documented audit | Semantic replay, identical-input comparison và artifact regeneration pass |
| Windows byte bindings | `git -c core.autocrlf=true checkout-index` trong temporary checkout | Frozen oracle và sanitized actual bytes/digests không đổi; explicit LF attributes |
| Full local suite | `.venv/bin/python -m pytest -q`, clean detached checkout `9a5e3219cf0d70f69d85b2a611d67e56a36c5897` | 2174 passed, 10 skipped, 48 subtests passed in 401.38s; không remote CI PASS |

[Handoff/lệnh tái lập](../research/week4-seamless-scenario.md) và [public evidence](../research/scenarios/week4-seamless-v1-actual.json) giữ exact revision/runtime/input/config/source/dependency digests.
Execution checkout sạch `983ce542...` có source/config bytes bằng baseline, snapshot envelope SHA-256 `07de85e27bee6cbbf09673e40de1d47ef2605669c8c29904246c5efbf7d97a4d`.

| Kiểm chứng | Kết quả / giới hạn |
| --- | --- |
| Public CLI ASSUMED | success; một generated program 4 steps, 5 states, 4 expansions, complete trong scope; goal true/checkpoint false; unrated |
| RAW / missing recovery | indeterminate; prefix 0/1 step, không optimistic secret/identity/asset |
| Asset false + true assumption | blocked; prefix 3 steps; `known_false_veto`, một rejected assumption |
| OFF / no request capability | no_path/blocked, 0 paths; không claim absence ngoài declared scope |
| Steps cap 3 | truncated/step_limit_reached; không no-path/optimal claim |
| Independent assertions | Cả bảy cases khớp freeze; không lấy actual làm oracle |
| Public evaluator replay | Từng before/after và final state khớp; canonical graph bất biến; provenance/causal parents kiểm được |
| Two public CLI processes | compare equal=true, semantic SHA-256 `b2e7bce6c4854f549415327e458215f65e643bbdbf75cc3d71a7d73ce7c7a86e`; không so runtime |
| Focused suite | `test_week4_scenarios`, `test_asrep`, `test_rbcd`, `test_query_cli`: 139 passed in 68.66s |
| Artifact generator | Documented audit tái tạo public artifact byte-identical; scan không chứa canonical private IDs |
| Infrastructure | Develop Actions run 37871043065: quality/Ubuntu/Windows/Compose failure, runner_id=0, 0 steps; không CI PASS |
| PR infrastructure evidence | PR head `9a5e321...`, CI run 37875437489 và branch-policy run 37875437558 | Tất cả jobs failure, runner_id=0, 0 steps; billing chặn trước execution |

Tám assumptions actually-used có declarer @Lolavine777, context X, rationale và recovery method/budget/horizon riêng; không observed exploit hoặc empirical P.
AdminTo action consume abstraction `admin_channel` đã nhận, không gọi đó là WinRM runtime verification chi tiết.
Không có ranking input/basis; bốn active operations không là số C/P/I được evaluator chấm.

## Điều học được / quyết định

Broader checks ban đầu phát hiện docs pins bị stale sau amendments và clean-source/RAW-presence observations khác committed baseline.
`test_week4_acceptance_manifest` có ba failures ở dirty checkout; không gọi chúng PASS hoặc sửa generated hashes bằng tay.
Dùng existing acceptance generator trong clean verification checkout không private raw để refresh synthetic baseline và semantic fixture; evidence SEAMLESS giữ riêng theo measured execution ở trên.
Refresh từ clean source `e7c0b917c03a21e867634a96f8a2dbd98f3b66f4` cho 38 rows = 36 PASS/1 NOT EXECUTED/1 BLOCKED RUN/0 unexpected FAIL; deterministic hai runs, source/input digest `148f10d5e4cbbb0d54baed23d325297d0a06f5fb74e0c2e6442a7cf97087863d`.
Manifest được copy từ generator output; semantic fixture bytes giữ nguyên, không sửa expected hoặc generated pins bằng tay.
Cùng source tại scenario checkout có raw cho 36 PASS/2 NOT EXECUTED/0 BLOCKED RUN; baseline filesystem prerequisite chưa làm actual private query nên không được đổi thành PASS.
Raw locators `groups/40/Members/2` và `computers/0/LocalAdmins/2` xác nhận đường derivation tới canonical AdminTo V_A -> C0.
Ruff check/format, yamllint, repository/contract checks, Compose config và diff whitespace đã PASS; Full local suite trước final checksum refresh: 2173 passed/10 skipped/48 subtests passed và một failure `test_week4_package_file_pins`, vì package SHA manifest cũ pin hai docs đã amend.
Đã regenerate SHA manifest bằng stdlib hashlib từ cùng danh sách files; oracle/graph/test bytes không đổi.
Sau checksum refresh, 17/17 package hashes khớp và tám scenario tests PASS.
Full local rerun tại clean detached checkout `9a5e3219cf0d70f69d85b2a611d67e56a36c5897` đã PASS: 2174 passed, 10 skipped, 48 subtests passed in 401.38s.
Mười skips thuộc optional raw/telemetry và Windows junction; verification checkout không private raw, còn scenario execution riêng đã verify/run pinned SEAMLESS như trên.
Chỉ thêm LF attributes cho hai public scenario JSON và ghi kết quả/worklog sau full suite; source/config/oracle/artifact bytes không đổi.
`core.autocrlf=true` checkout test xác nhận frozen oracle và actual artifact giữ đúng byte hashes; final lint/format/YAML/repository/contract/Compose/diff checks PASS.
Một invocation đầu gọi nhầm tên test file không tồn tại nên no tests ran; invocation đã sửa là suite 139 PASS ở bảng.

## Trở ngại và việc kế tiếp

Advisory read-only review xác nhận public artifact/oracle/source/config consistency và privacy; không thay B human review.
Đã sửa hai findings: chỉ rõ execution checkout chứa spec, và audit verify expected bytes đúng frozen commit cùng recorded source/config maps đúng pinned source.
Amendments ngày 09/10 refresh phạm vi core + ba techniques, status RBCD/CLI, và phân biệt accepted package counts với actual SEAMLESS mới.
Giữ snapshot lịch sử và không sửa generated acceptance artifacts bằng tay.

PR #243 base develop đã request @nairyuuu; không tự merge hoặc đóng #206/#239/#208/#204.
B review scenario/assumptions và human-independent clean-checkout reproduction còn pending; full manual docs/API audit toàn scope chưa thực hiện.
Report/demo cuối của #208 consume cùng scenario/results, không tạo runner/search thứ hai; #235 chưa promote main.
Actions billing/runner recovery là prerequisite riêng, local validation không được đổi thành remote CI PASS.
