# Worklog - 2026-10-06 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #48 #158 #143 #42; M2 / Week 3; PR #202; nhánh `docs/48-week3-final-handoff`.
- Người chuẩn bị: @nairyuuu (TTS B); reviewer/tác giả PR: @Lolavine777 (TTS A).
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

Bắt đầu từ fetched `origin/develop@891bda0001b9958e712cff54045f651273b43fd0` và PR #202 head `8bcaa4837a62d9ba526504de543ad956d2c84796`.
Đã đọc AGENTS/CONTRIBUTING, data policies, PR #202 description/comments/reviews, báo cáo Week 3 và các artifacts liên quan.
Tạo worktree riêng cho `docs/48-week3-final-handoff` để bảo đảm an toàn và không ghi đè thay đổi.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Verify raw SEAMLESS | `src.data.manifest.verify_manifest` với `data/samples/manifests/seamless-raw-v1.json` | 6 raw files khớp manifest, 0 issues, snapshot ID `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` |
| Verify private prerequisites | Checksum audit 6 files trong `.cache/issue196-prerequisites` | 6/6 file khớp byte-for-byte sha256 pins theo existing harness |
| Fresh Legacy replay | `scripts/research/reproduce_legacy_reconciliation.py` trên clean checkout `891bda0` | Status PASS, exit code 0; graph `code_version` và report `head_commit` đều là `891bda0001b9958e712cff54045f651273b43fd0`; canonical graph digest `c10c45a1c60e722404f921e8e559de3e8fe79efe5baf11b95bee9f1e5c8cc09d`; report SHA-256 `161ef577c259ab5caaaf604e6a0f3879507262f8d1cb1f699116036ff0f70933` |
| Comparator API gate | Replay harness step 3 comparator gate check | Verdict `NOT_MEASURABLE`, summary `Reconciliation pending: legacy-comparison: export_complete is not verified true`, expected exit code 2 |
| Comparator CLI execution | `scripts/reconcile_graph_baseline.py --candidate ... --baseline ... --mapping ... --summary` | Observed verdict `[NOT_MEASURABLE] Reconciliation pending: legacy-comparison: export_complete is not verified true`, observed actual exit code 2 |
| Exact-set verification vs #196 | So sánh `reproduction-report.json` với accepted `issue-196-final-cross-reproduction.json` | Match True toàn bộ slices: MemberOf (15.917), GenericAll (37.034 non-self, 10 self), WriteDacl (3.392 non-self, 3 self), AdminTo (5 direct, 4 derived, 1 coalesced), CanPSRemote (2), CanRDP (3 legacy, 3 project unknown), FCP/HasSession (0, `not_measurable`), outside-M1 (15.243, `unsupported`), 20 difference ledger items và multiplicity trùng khớp 100% |
| Full tests | `.venv/bin/python -m pytest -q` trên Windows (CPython 3.14.7) | 1.820 passed, 2 skipped (Windows junction/filename semantics), 48 subtests passed in 271s |
| Quality & contract | Ruff check/format, yamllint, repository/contract checks, Compose config, diff check | Passed; repository checks 421 files passed; Compose config passed với placeholder `NEO4J_PASSWORD` |

Runtime thực chạy: CPython 3.14.7, Windows AMD64; dependencies đúng `requirements-dev.txt`.
[Final handoff](../reports/week3-final-handoff.md) và [manifest](../../reports/research/week3-final-handoff.json) đã được cập nhật đầy đủ thông tin fresh replay, execution command, output digest, comparator exit code và B package acceptance.
Outputs được lưu tại thư mục ignored `.cache/week3-final-legacy-replay`; không commit private exports hoặc identities.

## Điều học được / quyết định

Fresh Legacy replay trên clean checkout của measured revision `891bda0` cùng comparator CLI exit code 2 hoàn thành binding kỹ thuật cuối cùng cho package.
Phân biệt rõ: measured runtime revision (`891bda0`), package/docs revision (PR #202 branch), historical provenance #196 (`8535d4`/`cc5f971`).
Toàn bộ exact directed sets và difference ledger bất biến hoàn toàn giữa các platforms (macOS/Linux/Windows).

## Trở ngại và việc kế tiếp

Harness thành công exit code 0 vì đã xác nhận đúng verdict `NOT_MEASURABLE` (expected exit code 2); full Legacy comparator vẫn `NOT_MEASURABLE` / exit 2 vì snapshot thiếu verified complete export. Không claim full BloodHound/CE parity.
Package #48/#158 đã được TTS B review và chấp thuận; PR #202 sẵn sàng cho final review và merge vào `develop`.
Sau khi PR #202 merge vào `develop`:
- Đóng #48 và #158.
- Đóng scoped parent issues #143 và #42 theo declared closure evidence.
- Chuyển sang final release review cho #186 trên release branch theo quy trình merge commit của repo.
