# Worklog - 2026-10-13 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#268](https://github.com/nairyuuu/ad-weighted-graph/issues/268), Week 5 source/goal/batch contract; B consumer [#276](https://github.com/nairyuuu/ad-weighted-graph/pull/276).
- Thời gian thực tế ước lượng: khoảng 30 phút.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Read closure audit and accepted contract before editing | [Latest #268 audit](https://github.com/nairyuuu/ad-weighted-graph/issues/268#issuecomment-6136479282), merged [#270](https://github.com/nairyuuu/ad-weighted-graph/pull/270), isolated `fix/268-ea-provenance` from `develop` `28236f234a8eba40db0a0f47b70034f27543e063` | Verified sole gap: EA locator `/groups/41` resolves to `-527`, whereas `/groups/18` resolves to `-519`. |
| Independent raw-backed red/green regression | [Raw binding tests](../../tests/test_source_goal_batch_raw_binding.py), using the project venv with `SEAMLESS_RAW_ROOT=<private-six-file-root>` | Before correction: 1 failed / 4 passed, failing on EA raw ID mismatch; after correction: 5 passed, covering DA, EA, DC-admin, DC-session and rejection of old EA locator. |
| Correct current live contract | [Target manifest](../../tests/fixtures/batch_contracts/target_manifest_seamless.json), [contract section 8](../research/week5-source-goal-batch-contract.md), existing pin assertion | Only EA provenance changes; target IDs, kinds, states, version and snapshot identity preserved. |
| Focused source/goal contract suite | Project venv `python -m pytest tests/test_source_goal_batch_contract.py tests/test_source_goal_batch_raw_binding.py -q -p no:cacheprovider` with private raw root | 49 passed; private raw tests executed without skips. |
| Six-file raw immutability | Project venv `python scripts/snapshot_manifest.py verify <private-six-file-root> data/samples/manifests/seamless-raw-v1.json` and raw fixture before/after verification | All six file sizes and SHA-256 hashes match snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`. |
| Manifest/auditor regression support | Project venv `python -m pytest tests/test_manifest.py tests/test_audit_seamless_raw.py -q -p no:cacheprovider` | 64 passed, 3 platform skips (Windows junction and filesystem name collisions). |
| Quality checks | Project venv Ruff lint and format across repo, yamllint, `scripts/check_repository.py`, `scripts/check_contract.py`, `git diff --check` | PASS; existing formatting violations in A reference/tests normalized with AST equality verified. |
| Week 4 acceptance checkout gate | Project venv `python -m pytest tests/test_week4_acceptance_manifest.py -q -p no:cacheprovider` | Dirty-checkout runs failed only `W4-CLI-PACKAGE.clean_tracked_source`; behavioral assertions and file-pin check passed; this gate requires testing the committed checkout. |
| B consumption audit only | Read #276 exact head `a564a6540940088502b82b98457b72458c0bb964`, manifest, pilot and digest/resume boundaries | Consumed manifest is byte-identical to the old live contract; no B runner code edited; refresh instructions in contract section 8.1. |

## Điều học được / quyết định

The regression derives target identity from raw `ObjectIdentifier` and kind from raw collection metadata, independently of the production normalizer and target display names.
Each referenced file is read through the existing manifest-verified byte reader after verifying the whole six-file snapshot.
Private data is never copied into versioned fixtures; absent default raw data is explicitly skipped, while an explicitly supplied root must verify successfully.
No frozen artifact in current `develop` embeds the exact incorrect EA locator; older raw audit references to `/groups/414` are distinct and preserved.
The merged #270 history and B's frozen pilot remain unchanged, and contract section 8.1 documents supersession.
Existing finite synthetic oracles and current Week 4 evidence pins do not depend on this locator and need no refresh.
Formatter-only changes to the A reference preserve its AST and introduce no new source/goal or runner semantics.

## Trở ngại và việc kế tiếp

B must merge the accepted correction from `develop` into #276 without rewriting its shared history, bringing the manifest, documentation, pin assertion and raw regression forward.
Any current request embedding the SEAMLESS manifest must refresh its EA locator and request/scope digests; previous request checkpoints must be replaced because resume rejects the changed scope.
Keep `reports/research/issue275-seamless-pilot.json` as historical evidence from `2e4790bb9ad1a62f244275c24862712ef7e9a3b1`; a current raw batch acceptance claim requires separately named fresh evidence with the corrected request and digests.
Request @nairyuuu exact-head review and consumption acknowledgement on the fix PR and #268.
Per [CONTRIBUTING](../../CONTRIBUTING.md), #268 stays open until the correction is reviewed, CI passes, the PR is merged into `develop` and acceptance is satisfied.
No merge is authorized by this task.
No full suite, full raw batch pilot, numeric adoption, Top-K, viewer or remediation acceptance is claimed.
