# Worklog - 2026-10-05 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #196; Refs #47 #48 #158 #195; M2; cross-reproducer/reviewer @nairyuuu.
- Thời gian thực tế ước lượng: Không đo tổng thời lượng phiên; không có Legacy import/runtime measurement mới.

## Kết quả và bằng chứng

Tạo managed worktree mới `issue196-ttsa-clean-reproduction` tại exact current `develop@cc5f971435dc7d14476d6055024f441e398a4ff8`, branch `research/196-ttsa-clean-reproduction`.
Final evidence chạy lại từ managed worktree mới thứ hai `issue196-ttsa-final-clean-replay`, detached tại cùng SHA, venv/raw copy riêng và không có prior generated artifacts.
`git status --porcelain=v1` rỗng trước cả hai final real runs; harness chạy từ public package worktree bên ngoài measured checkout như workflow B.
Workspace chính và untracked files của người dùng giữ nguyên.
Dùng skills using-git-worktrees, brainstorming, writing-plans, test-driven-development, ponytail, verification-before-completion và requesting-code-review.
Thiết kế theo boundary người dùng và accepted #195: harness chỉ orchestrate existing helpers, không đổi parser/engine/comparator/contract semantics.
Kế hoạch: checksum prerequisites, chạy raw CLI, dựng fresh comparator representations, tính exact raw-selected proofs/full differences, kiểm tests/quality/privacy, mở PR riêng vào develop và request B cross-reproduce.
Regression checks được viết và chạy red trước harness, sau đó green; harness/test nằm ignored khi đo base SHA để checkout vẫn clean.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Accepted prerequisite | #195 closed after reviewed/merged PR #197 | Accepted contract digest được pin trong harness/manifest |
| Environment | `uv venv --python 3.14 .venv`; `uv pip install --python .venv/bin/python -r requirements-dev.txt` | Fresh CPython 3.14.7 / Darwin arm64; mọi pinned dependency khớp manifest |
| Clean replay A | `PY PACKAGE_ROOT/scripts/research/reproduce_seamless_legacy.py --raw-root data/raw/SEAMLESS --legacy-dir LEGACY_DIR --output-dir .cache/issue196-run-a` | Harness exit 0; không đọc historical generated project/comparator/proof inputs |
| Raw / mapping | Manifest verifier + raw_mapping adapter/normalizer | Sáu raw checksums verified, pinned full exports/mapping verified, one-to-one typed/boundary population bằng nhau |
| Project CLI | Exact subprocess commands trong [manifest A](../../reports/research/issue-196-ttsa-clean-reproduction.json) | Fail-fast: 3.370 nodes / 56.367 edges / 3 unknown assessments, warnings/errors=0 |
| Full comparator | Fresh candidate + rebuilt Legacy comparator | `NOT_MEASURABLE`, exit 2; export_complete=false |
| Exact slices | [Replay report](../research/issue-196-clean-checkout-reproduction.md), manifest `accepted_slices` | Full MemberOf, non-self GenericAll/WriteDacl, direct AdminTo/CanPSRemote bằng raw/Legacy/project; mọi difference/missing/unexpected set rỗng |
| Full differences | Manifest `m1_difference_ledger`, private fresh `evidence.json` | 13 self-ACE + 4 derived-only AdminTo + 3 unknown CanRDP; accepted differences giữ nguyên |
| Unknown / false | Full assessments / positive primary provenance / raw session checks | Ba CanRDP unknown, 0 RDP edges; không gán false; zero relations not_measurable |
| Repeat A | Fresh `.cache/issue196-run-a-repeat`, [repeat artifact](../../reports/research/issue-196-ttsa-repeat-check.json) | Sáu stable output digests, slices và full M1 ledger identical; B vẫn pending |
| Harness regressions | `PY -m pytest tests/test_reproduce_seamless_legacy.py -q` | 6 passed; kiểm raw selection, unexpected/missing rows, mixed direct/derived, clock normalization, fresh/ignored và selectively-ignored destinations |
| Relevant tests | Venv pytest: harness, comparator, research audit, loader, structural boundary, Legacy exporter | 156 passed |
| Full suite | `PY -m pytest -q` | 1.801 passed, 9 skipped, 48 subtests passed |
| Quality | Ruff check/format, yamllint, check_repository.py, check_contract.py, Compose config, git diff --check | Pass; 293 Python files formatted, 416 tracked/unignored files, 2 synthetic fixtures |
| Privacy / bindings | Scan sáu public files against 12.672 authentic identity tokens; compare generated manifest bytes and harness hash | Pass; không AD identities/secrets/em dash/auto-close directives; public manifest byte-identical với fresh generated manifest |

`PY` là venv mới của measured worktree; `PACKAGE_ROOT` là public package worktree và `LEGACY_DIR` trỏ tới authorized retained `.cache/issue47` bundle của worktree A #184.
Raw là fresh copy sáu manifest-bound files từ authorized local storage vào ignored `data/raw/SEAMLESS`; chỉ raw/pinned full node/relationship/mapping inputs được reuse.
Time policy được dựng lại exact accepted bytes.
Historical generated comparator chỉ được kiểm tra read-only sau fresh replay để giải thích wrapper digest delta, không được dùng làm input hoặc expected triples.
Full observation evidence digest tái lập byte-identical với #194; canonical output digest đổi vì measured `code_version` là SHA mới.
Rebuilt Legacy comparator omits historical isacl attribute vì pinned full exports không chứa field này; directed triples/multiplicity giữ nguyên và không invent missing evidence.
Runtime/dependencies, per-file raw digests, script hash, contract/profile, exact commands, tất cả output digests và verdict nằm trong manifest.
Output/manifest timestamp và absolute parser log path được phân biệt rõ với stable set/payload digests.
Full suite có 9 skips: 5 telemetry raw unavailable, 1 Windows junction, 2 filesystem alias cases và 1 dataset-B raw unavailable.
Hai real SEAMLESS loader tests chạy với fresh raw copy, không skip.
Baseline trước khi copy raw có 1.793 passed/11 skipped; sau copy raw và thêm 6 harness checks đạt 1.801 passed/9 skipped.
Reviewer subagent read-only phát hiện preflight chỉ check ba filenames nên selectively-ignored directory có thể để sensitive comparison/proof outputs unignored.
Regression dùng temporary Git repo tái hiện lỗi trước fix, rồi preflight được sửa để check mọi destination trước mkdir bằng existing resolved-path helper.
Reviewer xác nhận fix, không còn blocker; manifest/harness hash và repeat evidence được sinh mới sau fix từ clean worktree thứ hai.
Technical subagent review không thay human B independent reproduction/review.

## Điều học được / quyết định

Contract #195 accepted không nâng full m1-structural-v1 eligibility thành MATCH.
Không chọn intersection làm scope; raw rules independently select Members union PrimaryGroupSid, non-self ACEs và direct host memberships.
Một AdminTo có direct evidence cùng derivation vẫn thuộc direct slice.
Canonical records không đổi khi thêm comparison metadata; unknown không trở thành edge hoặc false.
Zero observations không chứng minh decoder/session equivalence.
Không cần một live Legacy DB/import để replay pinned observations; phải ghi rõ external prerequisite này thay vì gọi nó independently reproduced.
Full private evidence giữ ignored; public artifact chỉ counts/digests/pointers và sanitized metadata.

## Trở ngại và việc kế tiếp

B independent clean checkout run/cross-check vẫn pending; request @nairyuuu cross-reproduce/review cùng workflow tại PR.
Nếu inputs/runtime chưa truy cập được, B cần ghi limitation cụ thể; nếu digests/sets khác, mở discrepancy, không sửa output cho khớp.
Đây là checkpoint A cho #196/#47/#48/#158, không tự đóng các issues và không claim Week 3 complete.
CI exact publication head và human review phải được xác nhận qua PR; CI của base hoặc head cũ không thay CI của head cuối.
