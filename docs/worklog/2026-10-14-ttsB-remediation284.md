# Worklog — 2026-10-14 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #284 / parent #265 / stacked trên #283, PR #285
- Thời gian thực tế ước lượng: Một phiên triển khai/kiểm chứng local; không quy đổi runtime thành attacker C.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Before/replay/rediscovery | [Runner](../../src/engine/remediation_runner.py), [guide](../research/remediation/runner-guide.md) | Native public query + effective views #283, strict reports 1.1.0, full native proof reproduction |
| Finite oracle | CLI `--finite` | Membership: 3/4 programs cut, 1/2 pairs disconnected, Alice bypass giữ lại; channel: 4/4 cut, 2/2 disconnected |
| Controls và resume | [Tests](../../tests/test_remediation_runner.py) | Native completeness, bypass identity, proof audit, timeout, resume, fresh C, priority counterexample/ties: final suite PASS |
| CLI và individual edits | [CLI tests](../../tests/test_remediation_runner_cli.py) | One command xuất strict reports/native artifacts; selected set và individual controls chạy riêng; actual timeout không tạo false negative |
| Numeric guard | Native automatic rating resolver | Synthetic C 1 → 4, exact delta 3; capped C giữ incumbent/no delta; P/I comparison pending, không numeric adoption |
| Raw pilot | CLI `--seamless-raw-dir` | PASS: sáu files verified trước/sau; 704.525 s, peak RSS 586,801,152 bytes; one source/one host. Channel 1/1 cut và disconnect; ineffective membership giữ bypass; unknown/capped không disconnect |

## Điều học được / quyết định

Content hashes không tự chứng minh search completeness. Runner audit actual native
search/replay và rejects fabricated/borrowed proofs hoặc thiếu after witnesses.
Checkpoint completed cells re-execute để audit; chưa tối ưu caching. Native caps,
unknown feasibility, adapter exclusions và retained replay successes không bị mất.

Verifier 1.1 đã cho enum `unsupported` nhưng unapplied-overlay guard bỏ sót status
này; bổ sung empty unsupported disposition, không nới success/negative proof rules.
Budget reserve full per-cell caps, charge failed workers theo worst-case reservation.
Source order canonicalize; các edit sets/cells giữ state độc lập.

Policy priority là đề xuất deterministic có explicit uncertainty/counterexample,
chờ A review. Historical acceptance/oracle bytes không sửa; current source inventory
cần record version mới vì thêm module runner. Đây không phải search optimizer,
defender-cost optimizer hoặc campaign probability calculation.

## Trở ngại và việc kế tiếp

Raw pilot hoàn tất trước thay đổi cuối chỉ normalize code-pin path separators;
không claim exact-final-head raw reproduction. Public evidence:
[finite summary](../../reports/research/issue284-finite-summary.json),
[finite table](../../reports/research/issue284-finite-table.md),
[raw summary](../../reports/research/issue284-seamless-summary.json),
[raw table](../../reports/research/issue284-seamless-table.md). Chỉ public aggregate
labels, không raw IDs/traces. Bảy finite selected-set/individual runs: 34.110 s,
peak process RSS 62,676,992 bytes.

Final clean-source full suite tại `d5006f2`: **2876 passed, 55 skipped,
48 subtests passed**, 1155.74 s. Skips là explicit optional private-data/platform
prerequisites; raw pilot riêng phía trên đã chạy thật. Ruff check/format, yamllint,
repository checker (740 files), contract checker và Compose config với CI placeholder
PASS. A remediation validator: 11 catalog entries/8 oracle cases PASS.
[Current v4 acceptance record](../../reports/research/week4-maintainer-acceptance-manifest-v4.json):
36 automated PASS, 1 manual NOT EXECUTED, 1 dataset prerequisite BLOCKED RUN tại
default worktree path; frozen semantic payload và source pins khớp, determinism
verified. Historical v2/v3 records và frozen fixtures giữ nguyên.

Remote CI giữ pending theo yêu cầu user vì
GitHub account billing/spending gate; không thử numeric approval hoặc claim remote
PASS. A exact-head review/cross-reproduction và policy review chưa có; #283 vẫn là
implementation prerequisite, không tự đóng parent hoặc các contract issues.
