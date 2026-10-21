# Worklog - 2026-10-05 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #195 / [PR #197](https://github.com/nairyuuu/ad-weighted-graph/pull/197); Refs #47 #48 #194; M2; reviewer @nairyuuu.
- Thời gian thực tế ước lượng: Không đo tổng thời lượng phiên; không có import/runtime/reconciliation measurement mới.

## Kết quả và bằng chứng

Tạo isolated worktree từ latest `origin/develop@f1c4fcaeea6c012a9b381b3937a80db281e5b33f`, branch `docs/195-m1-comparison-contract`.
Scope và thiết kế theo yêu cầu #195: contract Markdown là source of truth, reuse nguyên accepted evidence #194, cập nhật các report/comparison entry points và giữ machine eligibility gate.
Không thêm machine policy song song hoặc comparator scope mới vì phần A cần chốt semantics/dispositions, chưa cần logic projection tự động.
Workspace chính và hai untracked files của người dùng được giữ nguyên.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Source-of-truth matrix | [Comparison contract](../research/seamless-legacy-403-comparison-contract.md) | Đủ tám relations với raw source, direction, direct/derived, unknown/false và disposition |
| Direct membership | Evidence #194 `full_memberof_proof`, `raw_set_proofs` | Chọn full direct Members union PrimaryGroupSid; 15.917 exact matching là phép đo #194, không chạy lại |
| Self-ACE / AdminTo | Evidence #194 full raw decomposition + delta ledger | Chọn non-self ACE/direct LocalAdmins common slices; giữ self-ACE và derived-only delta như accepted policy differences để B review |
| CanPSRemote / CanRDP | Evidence #194 structural triples / unknown assessments | Structural-only PSRemote equality; RDP membership materialization khác project unknown, không ép positive-edge equality |
| Zero observations / outside M1 | Evidence #194 `no_observation_limits` và full kind ledger | ForceChangePassword/HasSession not_measurable; chín observed Legacy kinds ngoài M1 explicit out-of-scope |
| Consumers | [Real report](../research/issue-47-seamless-legacy-403-reconciliation.md), [reconciliation report](../research/reconciliation-report.md), [handoff](../research/seamless-legacy-403-reconciliation-handoff.md), [CE comparison entry](../research/bloodhound-import-baseline.md) | Dùng cùng contract; phân biệt historical evidence, current disposition và full machine scope |
| Existing regressions | Venv `python -m pytest tests/test_reconcile_graph_baseline.py tests/test_reconcile_seamless_legacy.py tests/test_structural_boundary_cases.py -q` | 88 passed; exact-input ineligible gate vẫn NOT_MEASURABLE / exit 2, không hiển thị parity |
| Repository / contract | Venv `python scripts/check_repository.py`, `python scripts/check_contract.py` | Pass: 407 tracked/unignored files và 2 synthetic fixtures |
| Quality | Venv Ruff check/format và yamllint | Pass; 286 Python files đã formatted |
| Diff / evidence / privacy | `git diff --check`, UTF-8/added-text scan và byte equality với base | Pass; đúng sáu Markdown files, không đổi code/config/tests/reports, không thêm em dash/AD SID/domain/auto-close directives |

Các checks trên chạy bằng `/Users/nguyendanglong/Documents/ad-weighted-graph/.venv/bin/python` tại worktree #195; synthetic regressions không phải phép đo SEAMLESS mới.
Sanitized artifact #194 giữ byte-identical với base, SHA-256 `797a541e649a43ad1aa71c127124943ac973a880369f4d2600950f5912e80ec9`.
Repository check ban đầu phát hiện table header worklog không đúng template; đã sửa header và chạy lại thành công.
Không thêm tests mirror Markdown vì không có machine-readable policy hoặc logic mới.
Không chạy raw CLI, Legacy native import, database queries hoặc clean-checkout cross-reproduction #196.
Evidence JSON, raw/input/output hashes, script/code/configs và historical reconciliation measurements giữ nguyên.

## Điều học được / quyết định

Evidence acceptance của #194 không phải human acceptance của comparison contract #195.
TTS A chốt dispositions để @nairyuuu review; shared A/B acceptance vẫn cần human approval.
Một edge AdminTo có direct evidence và derivation vẫn thuộc direct slice; không lọc tất cả edges có derivation.
Unknown/negative-known/positive là các trạng thái evidence khác nhau; không nâng unknown thành false hoặc edge.
Zero observations không kiểm chứng decoder/session equivalence.
Accepted policy differences không làm Legacy thỏa full machine `m1-structural-v1`; giữ `export_complete=false` và tổng `NOT_MEASURABLE`.

## Trở ngại và việc kế tiếp

Đã mở [PR #197](https://github.com/nairyuuu/ad-weighted-graph/pull/197) riêng vào `develop` và request @nairyuuu review contract/matrix cùng các dispositions.
PR dùng `Refs #195 #47 #48 #194`; không có auto-close directives.
Cross-link contract và results qua reports/worklog/PR cho #47/#48.
Sau acceptance #195, final clean-checkout cross-reproduction thuộc #196 tại revision nghiệm thu cuối.
Không tự đóng #47/#48/#158, không làm #196 và không claim Week 3 complete.
