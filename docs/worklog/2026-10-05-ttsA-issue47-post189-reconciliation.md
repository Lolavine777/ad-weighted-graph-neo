# Worklog - 2026-10-05 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #47 / [PR #194](https://github.com/nairyuuu/ad-weighted-graph/pull/194); Refs #48 #184 #189; M2; reviewer @nairyuuu.
- Thời gian thực tế ước lượng: Không đo tổng thời lượng phiên; không có import/runtime measurement mới.

## Kết quả và bằng chứng

Tái sử dụng isolated worktree và toàn bộ raw/Legacy bundle của #184, tạo branch `docs/47-post189-real-reconciliation` từ latest `origin/develop@294cba3e2882e4b7a5fbd867aadb8434124612c3` sau merge #189.
Workspace chính và untracked files của người dùng không được đổi.
Chỉ cập nhật hai reports, sanitized machine evidence và worklog này; không sửa parser/engine/comparator/exporter hoặc production code của B.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Project E2E | `python -m src.parser.cli` qua venv, raw manifest, policy #184, fail_fast | 3.370 nodes, 56.367 edges, 3 unknown CanRDP assessments; warnings/errors=0 |
| Input binding | [Report/reproduction](../research/issue-47-seamless-legacy-403-reconciliation.md), [artifact](../../reports/research/issue-47-seamless-legacy-403-reconciliation.json) | Sáu raw files verified; node/relationship/mapping export bytes khớp #183/#184; Legacy comparator input giữ nguyên |
| MemberOf | Reuse raw_index/exact triples; full-kind-proof.json ignored | Project = Legacy = Members union PrimaryGroupSid: 15.917 triples, 0/0 differences; 13.324 Members + 2.593 primary, overlap 0 |
| Primary provenance | Toàn bộ primary set, source record/raw pointer/positive provenance | 2.493 Users + 100 Computers; mọi edge direct, không derivation; chỉ thêm đúng primary set so với #184 |
| Remaining M1 ledger | Same unchanged audit script and full difference records | 10 GenericAll self + 3 WriteDacl self + 4 nested AdminTo project-only; 3 CanRDP Legacy-only/unknown; không có category unknown mới |
| Exact delta from #184 | So cả triples lẫn full discrepancy records | Không mất project triple; nodes, assessments, Legacy triples và mọi non-MemberOf difference record/provenance/derivation/raw pointer không đổi |
| Direct/derived distinction | LocalAdmins source-rule view + validated lineage | 5 direct matching, 4 derived-only AdminTo; 1 direct matching edge cũng có derivation được coalesce, không drop theo flag |
| Unknown/absence | CanRDP assessments + ForceChangePassword/HasSession observations | CanRDP 0 edges/3 unknown; hai relations kia 0 stored observations, decoder/runtime/session equivalence unknown |
| Comparator | Existing CLI trên new candidate + pinned Legacy | Exit 2 / NOT_MEASURABLE; export_complete=false không thay đổi |
| Multiplicity | Existing graph_multiplicity helper | Project 56.367 stored/unique, 56.373 provenance occurrences; Legacy 71.596 stored/unique, evidence count null |
| Raw locator | Existing trace_project_raw_locator helper | 10 project edges / 11 provenance records located, gồm primary User/Computer samples |
| Focused tests | Venv pytest: research audit, comparator, boundary, builder, inference, demo, reconciliation, loader, Legacy exporter | 283 passed |
| Full suite | Venv `python -m pytest -q` trên integrated code | 1.795 passed, 9 skipped, 48 subtests passed |
| Quality | Ruff check/format, yamllint, check_repository.py, check_contract.py, Compose config | Pass; không có production-code thay đổi |

### Revision/input/output digests

Full SHA-256 không được viết bằng expected counts; lấy từ actual file bytes hoặc canonical sorted sets qua existing serialization helpers.
Các bindings còn lại, per-kind project/Legacy/matching/difference hashes và 20 hashed delta entries nằm trong [machine artifact](../../reports/research/issue-47-seamless-legacy-403-reconciliation.json).

| Artifact | SHA-256 |
| --- | --- |
| Raw manifest | `a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d` |
| Project CLI output | `aa9c9a6eaea39115ca6a406054bf9bcd47769cc7f4ec06f103170aca69b5a840` |
| Project comparator input | `7fe3c0ae742e7772491476d1369bb51057ab9f434184ae2560fc0eaf27527fcb` |
| Unchanged Legacy comparator input | `93a0cbf1b01550ec3443020d1e2aa4caed1b42d19ea3327decb79e914f2f9a83` |
| Full exact difference evidence | `f96479391987327e719607037ecb0c2579574fd39e48aa137c2ba017c8746242` |
| Full raw MemberOf proof | `1d8cbeff9bc8060db954582d6f6c16fb5d1eddff087b3e0a6f6a8593d3fdd907` |
| Full MemberOf project/Legacy/matching set | `049130749db9649e7352a6061841c521098331899e7522ac4ddb3519e47aefc7` |
| Added-project / raw PrimaryGroupSid set | `b5430bf7724fb1521337c99d43abd8d0e208de59a27cb41f02f00f2662d80f66` |
| Either empty MemberOf difference set | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Project raw locator output | `9377880e6b4f4d154835b862bf5d085368666aa4cf6e3565a5f136aa44564771` |

### Execution disclosures

Docker daemon không chạy, nên không lặp native import/read-only database capture hoặc đo runtime mới.
Run mode là new real project CLI với unchanged pinned Legacy exports; audit verify cả full tables và comparator input rows/multiplicity.
Native import evidence/runtime/app/query bindings của #184 vẫn thuộc ngày 2026-10-04; các historical unknowns/null được giữ nguyên.
Time policy bytes giữ nguyên, collection time unknown và timestamp_status=assumed.
Một local provenance-check snippet ban đầu dùng comparator JSON loader cho raw BOM files và bị từ chối đúng encoding.
Snippet được đổi sang đọc raw bằng utf-8-sig như raw_index hiện có, cache parsed files, rồi kiểm tra toàn bộ primary set thành công; không đổi source/helper.
Full suite có 9 skips: 5 telemetry raw unavailable, 1 Windows junction, 2 filesystem alias cases và 1 dataset-B raw unavailable.
Hai real SEAMLESS loader tests chạy với raw copy đã giữ từ #184, không skip.
Không thêm synthetic tests trùng với regressions đã có của #189; các focused/full tests và real CLI/raw union là verification cho rerun này.
Hai bash snippets trong report được trích và chạy thật: snippet replay trả expected exit 2 của comparator, snippet raw proof trả 0; CLI/candidate/evidence/proof digests tái lập đúng.
Bốn public files được scan đối chiếu toàn bộ authentic raw/canonical identities trong mapping; không có identity thực hoặc em dash.
Reviewer subagent kiểm tra read-only report/evidence và xác nhận exact raw/provenance/delta claims.
Review phát hiện hai comparator output digests cũ sau rerun vì reconciliation_timestamp đổi; đã pin lại retained output bytes/timestamps và ghi giới hạn tái lập, không đổi comparator.
Human review của @nairyuuu vẫn bắt buộc và chưa được thay thế.

## Điều học được / quyết định

Full MemberOf input gap đã resolved ở #189; dữ liệu thật xác nhận exact set, directness và positive provenance.
Audit #184 có Members-only view lọc PrimaryGroupSid chỉ ở Legacy; sau fix, view cũ báo false equality và 2.593 project-unexpected.
Đã truy nguyên từ selection/raw pointers: đây là diagnostic bất đối xứng cũ, không phải production discrepancy mới.
Giữ nguyên script/output, annotate historical_memberof_view_limit và cung cấp authoritative full-kind/raw union proof riêng bằng helper hiện có.
Không nâng comparator gate, không biến unknown thành edge và không sửa B's materialization policies.
Counts không chứng minh parity; exact observation sets cũng không thay common-semantics acceptance hoặc active privilege validation.

## Trở ngại và việc kế tiếp

B review mapping/direction, resolved primary membership proof và các self-ACE/nested/unknown dispositions còn lại.
#48 dùng rerun integrated 294cba3 này, rồi còn clean-checkout cross-reproduction ở final accepted revision và yêu cầu nghiệm thu khác.
PR #194 đã mở vào develop từ branch docs/47-post189-real-reconciliation; GitHub xác nhận review request cho @nairyuuu.
Publication commit đầu ec3fe102aecbe0f81c9941cb51f67b196f9cd86b: branch-policy và compose checks success, quality/Linux/Windows tests còn chạy tại checkpoint ghi worklog.
Các checks trên head mới nhất và kết quả review tiếp tục theo dõi tại [PR #194](https://github.com/nairyuuu/ad-weighted-graph/pull/194), không dùng CI của head cũ làm kết quả head cuối.
#47/#48 giữ mở; không claim product parity hoặc Week 3 complete.
