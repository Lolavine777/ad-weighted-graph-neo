# Worklog — 2026-10-14 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #283 / W5-4 / parent #265
- Thời gian thực tế ước lượng: Một phiên triển khai và kiểm chứng local; không quy đổi thành effort C.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Immutable boundary và native replay | [API](../../src/engine/remediation.py), [guide tiếng Việt](../research/remediation/executor-guide.md) | Scope/native corpus pins, exact expected_before/evidence, per-cell initial state, bốn catalog adapters |
| Finite public baseline | [Probe](../../scripts/research/remediation_replay_probe.py), [summary](../../reports/research/issue283-replay-evidence.json) | Alice 3, Bob 1; membership giữ Alice direct bypass; shared channel cut 3+1; raw graph/facts không đổi |
| Manifest-verified SEAMLESS | `python -m scripts.research.remediation_replay_probe --seamless-raw-dir <private-dir>` | Sáu file verify trước/sau; declared requester/host goal; 1 baseline program, replay cut tại channel; chỉ xuất aliases/counts |
| Contract/verifier | `python -m scripts.research.remediation_acceptance` | Passed: 11 catalog entries, 8 oracle cases; không sửa frozen artifacts |
| Local static checks | Ruff check/format, yamllint, check_contract.py, check_repository.py, Compose config | Passed; 460 files formatted, 728 tracked/unignored files checked |
| Local focused tests | `python -m pytest tests/test_remediation_executor.py tests/test_remediation_contract.py tests/test_remediation_identity.py -q` | 96 passed, gồm hai manifest-backed SEAMLESS tests; sau final validation guards, executor-only: 26 passed, 1 raw test deselected |
| Nonstructural route regression | `test_wholly_nonstructural_route_is_explicitly_empty` | Passed; route chỉ hash non-null observed edges; empty nonstructural route được gắn nhãn rõ |
| Repository-wide regression | `PYTHONUTF8=1 python -m pytest -q --tb=short` | 2840 passed, 52 skipped, 48 subtests passed, 6 failures khi checkout còn thay đổi và inventory source mới chưa được version |
| Clean-commit failure reruns | `PYTHONUTF8=1 python -m pytest --lf -q --tb=short` | Cả 6 passed trong 424.95s; gồm raw executor, pin inventory, semantic reproduction, independent verdicts, mutation regression và documented CLI smoke |
| Current checkout byte pins | `test_acceptance_pins_survive_autocrlf_checkout` | Passed trên manifest v3; v2 và frozen oracles giữ nguyên |
| Week 4 current source evidence | [Manifest v3](../../reports/research/week4-maintainer-acceptance-manifest-v3.json) | Hai actual runs deterministic; clean source commit `ab492ff`, 123 file pins; 36 automated cases pass, 1 manual not executed, 1 dataset prerequisite blocked trong worktree; không thay raw gate của #283 |
| Remote CI | PR #285 / GitHub Actions | Job không được start vì account billing/spending restriction; theo yêu cầu user giữ pending, không claim remote PASS |

## Điều học được / quyết định

Replay chỉ chứng minh chương trình baseline retained/cut/indeterminate/error.
Giữ `rediscovery=not_run` và transport riêng `remediation-replay/1` cho consumer #284;
không phát hành complete result 1.1.0 hoặc disconnected metrics khi after-search chưa chạy.
Không đổi evaluator, raw provenance, frozen oracle hay numeric adoption.

Runtime false scenario dùng native blocked vocabulary nhưng decision audit bổ sung
explicit effective intervention origin. Static preauth dùng immutable lookup riêng,
không tạo observed collector evidence giả. Initial membership/admin/material/token
giữ nguyên; không diễn giải relationship removal thành thu hồi mọi capability.

## Trở ngại và việc kế tiếp

Lần chạy đầu dùng CP1252 mặc định Windows gặp UnicodeDecodeError ở existing likelihood
tests; đã dừng lần chạy đó và xác nhận file test này đạt 25 passed, 2 raw skips khi bật UTF-8.
Full run tiếp theo overlap các lần sửa/commit của phiên này, nên reproducibility guards
đã fail đúng; không gọi full run đó là green. Các failure được rerun trên clean commit và
đạt. Manifest v3 là record mới cho expanded source inventory; không sửa historical v2
hoặc expectation fixtures. Public v3 chỉ redact local executable/temp command paths,
khai báo tại `execution.publication_redactions`; semantic evidence và pins không đổi.

A exact-head review chưa chạy, chưa claim approval. Các adapters ngoài bốn entries, token/session lifecycle,
rediscovery và batch metrics giữ ngoài phạm vi phiên executor này.
