# Worklog - 2026-10-12 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #264, #259, #265, #267; PR #266; Week 5.
- Thời gian thực tế ước lượng: khoảng 50 phút cho audit, sửa và verification.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Audit/basis | [V2](../research/ratings/asrep-expert-v2/README.md) | Recovery numeric absent; request transfer withdrawn; operational proposals pending |
| Public flow | [Evidence](../../reports/research/issue264-asrep-expert-v2-verification.json) | 16 CLI processes; API/CLI/orchestration match; raw P=0/4, test-only P=3/4 |
| Full verification | `.venv/bin/python -m pytest -q` | 2637 passed, 9 skipped, 48 subtests |
| Quality/privacy | Ruff, format, contract, repository and diff | PASS locally |

## Điều học được / quyết định

Ngày 12/10/2026; owner A / @Lolavine777; B / @nairyuuu cross-review.
Worktree riêng `tts-a-266-revision`, detached từ head #266 `fa3a2d1`; push vào đúng branch remote `research/264-asrep-expert-basis`.
Không sửa checkout hiện tại của người dùng, B engine/search/UI, configs hoặc frozen Week 3/4.

V2 rút numeric recovery của mật khẩu tự nhiên vì thiếu conditional rank mass và completed compatible compute coverage.
V1 và toàn bộ oracle cũ được giữ để regression counterfactual; CLI mặc định chọn V2, chỉ dùng `--basis-version v1` khi tái lập fixture cũ.
Compute floor/cap cũ trong 20h tương ứng khoảng 7,28-14,56 checks/s, không phải benchmark hoặc đặc tính AS-REP.
Benchmark do tác giả công bố với RTX 4090/hashcat v6.2.6 chỉ dùng kiểm tra scale; không chuyển H/s thành distinct guesses hoặc password probability.
Request có đề xuất residual-workflow riêng [9/10,99/100], không transfer từ reset activation.
Activation và WinRM giữ interval nguồn như pending equivalence questions với full successful history, secret age và transport cụ thể.
Không có elicitation mới hoàn tất, B adoption, tự approve hoặc merge.

Regression mới đã RED 4/4 trước implementation và GREEN 4/4 sau sửa.
Focused kiểm tra cũ trước sửa: 30 passed.
Probe cuối chạy trên consumer commit `6577a96`, 16 CLI processes, hai runs/case, API/CLI/orchestration khớp ở hai positive modes; controls raw/unknown/false/off/no-request/step-cap đúng oracle.
Raw V2 sinh 1 program, P=0/4, C/P/I complete=0/0/0, fully-rated=0.
Synthetic wiring copy sinh cùng 1 program, C=3/High, P=3/4, fully-rated=0, Pareto=0, path product absent.
Frozen raw baseline giữ C=3/High/P=0/4; 58 historical byte pins giữ nguyên.
Report sanitized: `reports/research/issue264-asrep-expert-v2-verification.json`; full private outputs chỉ nằm ignored `reports/generated/issue264`.

Full suite trên final consumer: **2637 passed, 9 skipped, 48 subtests passed**, 507,82s.
Ruff check, format check (426 files), contract (2 synthetic fixtures), repository/privacy/link checks và diff check đạt local.
Full suite không phải evidence remote CI; remote CI sẽ được kiểm riêng sau push.
Probe baseline đầu tiên bị vô hiệu vì tôi sửa wrapper trong lúc subprocess còn chạy; final probe chạy sau freeze commit và qua determinism.
Không dùng probe vô hiệu làm bằng chứng thành công.

Automatic approval review ban đầu từ chối publish vì chưa thấy payload của generated report.
Payload được đọc trực tiếp, kiểm no raw canonical IDs/graph records, bỏ absolute local paths và chạy repository/privacy validation trước retry.

## Trở ngại và việc kế tiếp

B review cần quyết định request judgment, activation/WinRM exact-history equivalence, C/I applicability và public numeric-basis/review labels.
Recovery vẫn là gap có tên, không tăng coverage raw được adopt và không đóng #264.
Phần taxonomy đa kỹ thuật/cohort/broad coverage nằm ở branch/PR riêng cho #267.


## Verification-scope correction after B review of #271

The same overly broad API_CLI_orchestration_equal flag existed in this A-owned wrapper.
Consumer `2d57946` now checks all selected API/CLI semantic outcomes, caps/guarantees, Min-Effort, ranking/coverage and ordered programs for both positive modes and all six controls.
Orchestration assertions cover only its exposed search completeness/truncation/reason/expansions, programs and ranking in the two positive modes.
The previous report remains frozen; its broad equality flag is superseded by [corrected evidence](../../reports/research/issue264-asrep-expert-v2-review-verification.json).

| Verification | Exact result |
| --- | --- |
| Focused preserved oracle/audit tests | 35 passed in 199.46s |
| Fresh public probe | 16 native CLI processes, two each case, all exits 0; exact semantic controls/API comparisons pass |
| Historical bytes | 58 pins preserved; v1/v2 numeric model and old oracle bytes unchanged |
| Quality | Ruff/format/repository/diff checks pass |

The earlier full suite of 2637 passed / 9 skipped / 48 subtests remains evidence for the unchanged numeric model at the earlier consumer.
No new full-suite claim is made for this verifier-only correction.
Natural-password recovery remains unrated, pending numbers stay inactive, B numeric adoption is absent, and the verifier correction stays isolated.
B merged original #266 at `5a2615c` through develop `7368cac` while the verifier correction was in progress.
[Follow-up #272](https://github.com/nairyuuu/ad-weighted-graph/pull/272) contains the post-merge correction on the same branch.
An ancestry-only merge of current develop preserved the entire verified tree byte-for-byte and removed duplicate original #266 changes from the PR diff.
No merge or numeric adoption was performed by A.

## PR #272 P2: full public program identity

The latest remote head before this correction was `08b3324`; inline [P2 discussion](https://github.com/nairyuuu/ad-weighted-graph/pull/272#discussion_r4248712835) was confirmed unresolved.
The old comparator falsely accepted a genuine CLI candidate whose actor changed while technique names, status, ranking and coverage stayed identical.
Nine mutation regressions failed with `DID NOT RAISE` before the correction.
A further regression substitutes one genuinely generated two-route branch for another with the same technique sequence but different source and canonical edge evidence.
That regression also failed against the old `08b3324` comparator and passes with the correction.

Consumer `ce85478e904437915d462e4fef28a27fe28b368f` uses one shared comparator for API/CLI and orchestration/CLI.
Program identity is the ordered canonical public `wire(PathResult)` record, excluding only the CLI transport `candidate_id`.
It preserves nodes, complete structural edge records/provenance and cost, ordered transition requests/results including actor/source/target and bindings, before/additions/after state and evidence, edge IDs, causal `derived_from_step`, final state, scenario and runtime context.
The native serializer sorts unordered state/fact collections while preserving candidate and transition order.
Ranking identifiers remain checked through the separate ranking comparison.
Missing edge evidence and reordered candidates/transitions are refused.

API/CLI comparison still covers selected outcomes, caps/guarantees, Min-Effort, ranking and coverage in both positive modes and all six controls.
Orchestration comparison covers only exposed search completeness/truncation/reason/expansions, full program identity and ranking in the two positive modes.
Attempts and diagnostics are outside this comparator's declared scope.
No orchestration status/goal/caps/guarantees/Min-Effort/coverage equality is inferred.
Technique-name lists in report summaries are display summaries, not the identity proof.

| Verification | Command or evidence | Exact result |
| --- | --- | --- |
| Preserved AS-REP and identity tests | `.venv/bin/python -m pytest -q tests/test_asrep_basis_audit.py tests/test_asrep_expert_basis.py` | 49 passed in 179.57s; 35 existing cases and 14 new cases |
| Public query regressions | `.venv/bin/python -m pytest -q tests/test_query_cli.py tests/test_query_boundary_regressions.py tests/test_week4_query_materialization.py tests/test_week4_query_scenario_mapping.py` | 108 passed in 12.32s |
| Fresh frozen-consumer probe | `.venv/bin/python -m scripts.research.asrep_expert_basis --raw-dir data/raw/SEAMLESS --output reports/generated/issue264/program-identity-verification.json --basis-version v2` | Exit 0; 16 native CLI processes, two per case; 8 API/CLI and 2 orchestration comparisons pass |
| Model and historical boundaries | Native v2 oracle, frozen baseline and byte checks | Raw P=0/4; synthetic wiring P=3/4; both fully-rated=0; 58 historical pins and all three earlier reports unchanged |
| Quality and privacy | Ruff check/format, yamllint, contract, repository and diff checks | PASS; 427 Python files formatted, 2 synthetic fixtures validated, 648 tracked/unignored files checked |

[New sanitized evidence](../../reports/research/issue264-asrep-expert-v2-program-identity-verification.json) declares `asrep-public-comparison/2.0.0`, its exact comparison limits and the pinned new regression file.
It supersedes the technique-only program-equality flags in the earlier packets, which remain frozen.
The generated publication replaces only the local repository path prefix in command strings; no private program records or participant IDs are published.
No fresh whole-suite claim is made for this verifier-only correction.
AS-REP v1/v2 numerical files, old oracles/tests, pending numeric-adoption boundaries, B-owned source/configs, #271 and the user's current checkout remain unchanged.
Natural-password recovery stays `UNRATED_NO_BASIS` and no numeric adoption, self-approval or merge is performed.
B / @nairyuuu is requested to rereview the exact final remote head before resolving the P2 discussion.

The final fixture runner explicitly decodes UTF-8, matching the public CLI's output contract for Windows redirected streams.
Final frozen consumer/test commit: `f64681e1395c73d8b58b28ccb55c793294fe4031`.
The only executable/test delta from `ce85478` is this one test-fixture encoding setting; verifier, engine/configs, basis files and old oracle tests are byte-identical.
A fresh focused run at the final consumer passed **49 tests in 178.04s**.
The fresh final-consumer v2 probe again exited 0 with **16 CLI processes**, eight API/CLI and two orchestration comparisons, and the same exact semantic controls, numeric coverage and frozen baseline counts.
The current generated identity packet pins that final consumer and test hash; the initial P2 packet remains available at immutable [commit 956c69f](https://github.com/nairyuuu/ad-weighted-graph/blob/956c69f025919d63c1f53bb8ea3ae50857d2acc6/reports/research/issue264-asrep-expert-v2-program-identity-verification.json).
The three earlier frozen packets and 58 historical pins remain unchanged.
Ruff/format/yamllint/contract/repository/privacy/diff checks pass again; Windows CI execution itself is not claimed.
