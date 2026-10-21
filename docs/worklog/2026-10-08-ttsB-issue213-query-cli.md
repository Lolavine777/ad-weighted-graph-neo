# Worklog — 2026-10-08 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #213; PR #233; M3-B3 / Week 4.
- Branch/worktree: `feature/213-query-cli`, `.worktrees/issue-213`; base `develop`.
- Reviewer: @Lolavine777; PR giữ draft, không tự merge hoặc đóng issue.
- Đã đọc CONTRIBUTING.md, `.github/copilot-instructions.md`, area instructions và latest review tại `e7fa6f916e894250c2ec2eb07fc62343444dfc45` trước khi sửa.
- Fetch xác nhận remote head vẫn đúng reviewed SHA; không có commit mới cần bỏ qua.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

Merge `origin/develop@4330f35e881ebadbd524843fc3686d48a97b917f` bằng merge commit
`4fadc4c`, theo CONTRIBUTING; không rewrite shared history/force-push. Conflict duy
nhất `.gitattributes`: giữ cả CLI/schema LF bindings và exact-byte #216 evidence
rules. #232 đã merge tại `1c1d0d6`, dependency correctness #212 đã giải quyết;
develop cũng có #230. Không sửa shared materializer, search hoặc ranking engine.

CLI phân biệt wrapper theo sự hiện diện của key `query`. Nested null/array/string/
number/boolean bị từ chối exit 1, stderr rõ ràng, stdout rỗng và không tạo output.
Object rỗng được truyền tới authoritative validation và bị từ chối; valid wrapped/
unwrapped PathRankingQuery vẫn chạy ranking. Bỏ input vẫn chạy semantic không scoring.
Giữ empty-state fix `e7fa6f9`: explicit `{}` bị từ chối, `{"control":[]}` là zero
capabilities và omitted state giữ documented default.

Schema `week4-query-result/0.2.0` thay acceptance contract 0.1: resolved dependency
#232 tách khỏi `experimental_pending_213_208`, pending human acceptance #213,
independent cross-reproduction #208 và actual private/SEAMLESS reproduction.
README, schema, code, tests và handoff đồng bộ. Engine scope/proof giữ tên public
API và chỉ áp dụng declared scope/assessed coverage. Synthetic PASS không là full
Week 4/SEAMLESS acceptance. CLI vẫn `materialize_query → run_attack_query`.

### Kiểm chứng revision cập nhật

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Engine/ranking focused | Pytest Week 4 Min-Effort, query boundary/materialization/scenario mapping, ranking interface/conformance | **308 passed** (7.05s) |
| CLI subprocess regressions | `python -m pytest tests/test_query_cli.py -q` | **54 passed** (69.37s); lần đầu 2 assertion diagnostic sai đã sửa, không thay validator |
| Full suite | `python -m pytest -q` | **2054 passed, 11 skipped, 48 subtests passed** (319.76s); private/default-worktree/platform skips không là actual private PASS |
| Integration suite | `python -m pytest -m integration -q` | **55 passed, 2010 deselected** (72.97s) |
| Required repository checks | Ruff check/format, yamllint, check_repository, check_contract, diff check và Compose config | PASS; 346 Python files, 488 tracked/unignored files, contract + 2 synthetic fixtures; rerun sau cập nhật worklog |
| Hai synthetic runs và compare | Commands trong handoff; `scripts.research.compare_query_runs` | **equal=true**, semantic `sha256:bb4a55a66dd5ef6a373c8b6de3bbe95ae8fe41cb75cb8a56eb30aae000b4092f`; chạy lại trên final clean revision sau commit, exact SHA trong PR description |
| Independent expectations | Oracle #206/#225 exact transition paths/reachable states; Ledger E #207/#220 | Direct effort 5, inherited effort 2. Không regenerate expected từ actual |
| Private/SEAMLESS | Actual input/bindings/verified lineage và query run | Pending; không claim PASS từ synthetic hoặc skips |

Lượt full đầu: 21 failed, 2033 passed, 11 skipped; worklog ghi bằng PowerShell gây
CRLF warning lên Git stderr (20 CLI tests) và thiếu template worklog (1 test).
Đã chuẩn hóa LF và sửa template, không nới assertion; lượt full cuối ở bảng PASS.
Compare harness cũng có regression từ chối schema 0.1 và semantic digest tampering.
Hai synthetic outputs: success, ba paths (1/2/2 steps), asset=true/checkpoint=false,
best `generated_0003` effort 2, direct effort 5, complete=true/truncated=false trong
declared synthetic scope. Runtime mỗi run giữ riêng, generated artifacts không commit.

## Điều học được / quyết định

Các assertion #212 đã thay bằng contract cụ thể: zero-action với target khác actor
phải có semantic zero-work disposition, likelihood/impact null, không ordinary
Pareto; invalid metadata/snapshot bị từ chối cả zero-action/no-path; missing P/I
không fabricate basis. Missing bindings, adapter/validator exclusions giữ counts,
diagnostics và hạ proof kể cả khi generator complete. Loại path effort 2 qua adapter
chỉ còn effort 5 trong bound subset và không chứng minh minimum trong scope.
Các caps hạ completeness/proof, không claim global optimum hoặc Top-K.

## Trở ngại và việc kế tiếp

#232/#212 đã merge; không còn dependency blocker đó. Còn human review exact head và
CLI acceptance #213, independent cross-reproduction #208, actual private/SEAMLESS
reproduction. #224 cần consume schema 0.2, ordered trace, diagnostics/unrated,
checkpoint/asset và coverage riêng. Attempts chưa có authoritative branch IDs,
checkpoint chưa có witness path ID; không tạo evidence giả. Report #208, viewer
#224, README overhaul #210, Top-K/choke-point/CE giữ scope riêng.
