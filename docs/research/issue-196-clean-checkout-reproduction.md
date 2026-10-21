# #196 clean-checkout reproduction package - TTS A

## Closure amendment - 2026-10-06

#196 và #47 đã closed theo [A/B reproduction acceptance](https://github.com/nairyuuu/ad-weighted-graph/issues/196#issuecomment-6008002642) và [reconciliation closure](https://github.com/nairyuuu/ad-weighted-graph/issues/47#issuecomment-6008006657).
A package #198 được B approve và merge `8535d44771ec9ec1960b4e883103f83654cc1d4f`; independent B #199 được A approve exact head `fd82e84b80cd5491da21a30c66702a7671a35d71`, merge `891bda0001b9958e712cff54045f651273b43fd0`.
[B final reproduction](seamless-legacy-403-final-reproduction.md) và [sanitized artifact](../../reports/research/issue-196-final-cross-reproduction.json) bổ sung accepted exact-set proofs; full comparator vẫn `NOT_MEASURABLE` / exit 2.
`cross-reproducer pending` và yêu cầu giữ #196/#47 mở phía dưới là checkpoint A ngày 2026-10-05 đã superseded, không phải gate hiện hành.
[Final Week 3 package](../reports/week3-final-handoff.md) giữ riêng current raw E2E trên `891bda0`, inherited measured SHAs của #196 và final package acceptance #48/#158.

## Historical A run - 2026-10-05

Ngày: 2026-10-05, Asia/Ho_Chi_Minh; A: @Lolavine777; cross-reproducer/reviewer B: @nairyuuu, pending.
Refs #196 #47 #48 #158 #195.
[#195 đã accepted qua PR #197](https://github.com/nairyuuu/ad-weighted-graph/issues/195#issuecomment-5992312624).
A tạo worktree mới từ exact `develop@cc5f971435dc7d14476d6055024f441e398a4ff8`; `git status --porcelain=v1` rỗng trước cả hai runs.
Đây là revision được đo, không phải tuyên bố revision nghiệm thu cuối cho Week 3.
[Manifest A](../../reports/research/issue-196-ttsa-clean-reproduction.json) được sinh bởi [replay harness](../../scripts/research/reproduce_seamless_legacy.py), không hand-edit output để khớp.
[Worklog](../worklog/2026-10-05-ttsA-issue196-clean-reproduction.md) ghi checks và phần B còn lại.

## Boundary và prerequisites

Chỉ reuse sáu raw SEAMLESS files đúng [manifest](../../data/samples/manifests/seamless-raw-v1.json), ba pinned Legacy exports/mapping dưới đây, và [accepted contract #195](seamless-legacy-403-comparison-contract.md).
Time policy accepted được dựng lại bằng exact UTF-8 bytes, digest `3540afa5ff3f4affd9deddd75f3da43409c5885af4ab9b7b2d17a97aac3a2e7b`.
Timestamp là `2026-10-01T00:00:00Z`, status `assumed`; collection time vẫn unknown.
Không đọc canonical/comparator/reconciliation/proof output lịch sử trong replay.
Không cần importer source, Docker, Legacy application, database credentials hoặc hidden scratch scripts để replay các pinned observations.
Không import/capture Legacy mới; Legacy 4.0.3 full exports và mapping là external prerequisites riêng tư, không phải output independently reproduced trong #196.
Nguồn/pinning của chúng là accepted #183/#184/#194 và [handoff manifest](../../reports/baselines/seamless-legacy-403-reconciliation-handoff.json).

| External prerequisite | SHA-256 bytes |
| --- | --- |
| Raw manifest | `a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d` |
| `legacy-nodes.json` | `ed4a6aa7775a4bfb5994875243eaf11588cf03cf4301acc1f23ce62fae11839c` |
| `legacy-relationships.json` | `4071dd8747a18aef4f30b074eeac163cbc7454cfe42a234367e81f8c488cdbf6` |
| `identity-mapping.json` | `202a91b951ff9292f57eeb535c65f02bb7063f5c28a6b27589acdc4ae45c570b` |
| Accepted comparison contract | `6a0bce271788560f3b9b32f5a15b824d6db17a874f95bb8a38b968f1714f2ac6` |

Các raw bytes và Legacy files phải được người có quyền cung cấp qua authorized local/private storage; public repository không chứa chúng.
Harness verify raw manifest, từng external digest, exact revision, clean status, Python/dependencies và contract trước khi tạo output.
Nó từ chối output directory đã tồn tại và resolved destination không git-ignored.
Mapping được dựng lại độc lập từ raw adapter/normalizer, rồi kiểm tra exact one-to-one equality với pinned mapping và typed/boundary population.
Legacy domain/boundary metadata của exports bắt nguồn từ raw/project mapping, không phải independent Legacy metadata measurement.

## Commands chạy từ checkout sạch

Harness thuộc reproduction package, còn measured code thuộc SHA `cc5f971`.
Chạy harness từ bên ngoài measured checkout để không làm dirty checkout hoặc đổi CLI `code_version`.
Final evidence A được chạy trong managed worktree mới thứ hai `issue196-ttsa-final-clean-replay`, với venv và raw copy riêng, không có generated output cũ.
Harness chạy từ package worktree bên ngoài measured checkout, đúng workflow B dưới đây; mọi output destinations được kiểm tra git-ignore trước khi tạo directory.
Sau khi checkout PR này để review package, B có thể dùng file harness từ package checkout và tạo measured checkout riêng như sau.
`PACKAGE_ROOT` phải là checkout của reviewed PR head; ghi lại SHA bằng `git rev-parse HEAD` và kiểm tra harness hash với manifest A.

```bash
# Start in the reviewed package checkout, not the measured checkout.
PACKAGE_ROOT="$PWD"
PACKAGE_SHA=$(git rev-parse HEAD)
REPLAY_ROOT=/absolute/path/to/new/issue196-replay-b
RAW_ROOT=/absolute/path/to/authorized/SEAMLESS
LEGACY_DIR=/absolute/path/to/authorized/pinned-legacy-exports

git worktree add --detach "$REPLAY_ROOT" cc5f971435dc7d14476d6055024f441e398a4ff8
cd "$REPLAY_ROOT"
uv venv --python 3.14.7 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
PY="$REPLAY_ROOT/.venv/bin/python"
git rev-parse HEAD
git status --porcelain=v1
"$PY" "$PACKAGE_ROOT/scripts/research/reproduce_seamless_legacy.py" \
  --raw-root "$RAW_ROOT" --legacy-dir "$LEGACY_DIR" \
  --output-dir .cache/issue196-run-b
```

PowerShell equivalent, cũng bắt đầu ở reviewed package checkout:

```powershell
$PackageRoot = (Get-Location).Path
$PackageSha = git rev-parse HEAD
$ReplayRoot = 'C:\authorized\new-issue196-replay-b'
$RawRoot = 'C:\authorized\SEAMLESS'
$LegacyDir = 'C:\authorized\pinned-legacy-exports'
git worktree add --detach $ReplayRoot cc5f971435dc7d14476d6055024f441e398a4ff8
Set-Location $ReplayRoot
uv venv --python 3.14.7 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-dev.txt
$Py = Join-Path $ReplayRoot '.venv/Scripts/python.exe'
git rev-parse HEAD
git status --porcelain=v1
& $Py "$PackageRoot/scripts/research/reproduce_seamless_legacy.py" `
  --raw-root $RawRoot --legacy-dir $LegacyDir `
  --output-dir .cache/issue196-run-b
```

Harness exit 0 nghĩa là reproduction checks đạt; subprocess full comparator vẫn phải exit 2 và verdict `NOT_MEASURABLE`.
Không dùng harness exit 0 để claim comparator `MATCH` hoặc full M1 parity.
Các exact subprocess argv, exit codes và log digests được ghi trong `manifest.json`; `<PY>`, `<RAW_ROOT>`, `<OUTPUT>` là path bindings do người chạy cung cấp, không chứa AD identities.
Mọi JSON/log được sinh trong ignored output directory; chỉ `manifest.json` chứa sanitized evidence để publish sau privacy review.
Nếu run fail, giữ outputs/log để điều tra, chọn directory mới cho lần thử tiếp; không hand-edit graph/proof/ledger.

Legacy comparator JSON được dựng mới từ pinned node table và directed relationship rows, giữ stored multiplicity và `export_complete=false`.
Full exports không có historical `isacl` query attribute, nên representation mới chỉ chứa `(source,kind,target)` cùng repeated rows cho multiplicity.
Không đoán hoặc thêm `isacl`; thuộc tính này không tham gia directed-set comparison contract.
Vì vậy byte digest của rebuilt Legacy comparator khác historical wrapper, còn exact observation evidence digest khớp #194.

## Hai lớp evidence của A

Full comparator vẫn `NOT_MEASURABLE`/exit 2: `legacy-comparison: export_complete is not verified true`.
Machine scope vẫn `m1-structural-v1`; Graph Contract `1.3.0`, weight profile `unit`.
CLI fail-fast sinh 3.370 nodes, 56.367 stored/unique edges, 3 unknown assessments, warnings/errors = 0.
Legacy observations là 3.370 nodes và 71.596 stored/unique triples; provenance occurrences của Legacy vẫn not measurable.

Các slices dưới đây là `equivalent_in_accepted_scope` theo #195, với project, Legacy và raw independently selected sets đều bằng nhau.
Mọi project-only, Legacy-only, raw-missing và unexpected sets đều rỗng, digest `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

| Accepted slice | Exact triples | Project = Legacy = raw set SHA-256 |
| --- | ---: | --- |
| Full direct `MemberOf` | 15.917 | `049130749db9649e7352a6061841c521098331899e7522ac4ddb3519e47aefc7` |
| Non-self `GenericAll` | 37.034 | `66b27d7990b7dcb10805f69301e321d36c2151835ec51fb7bf1bf59334b7fd27` |
| Non-self `WriteDacl` | 3.392 | `f53b9b23cc41eeb66d8b15f52d5f0b32655ec4c95f4fa987c289de38de2bb9a1` |
| Direct `AdminTo` | 5 | `7a62fcf4ef9211829050a5ead2fb4aeafad9ba5009e376e3cbf37b5e180b4683` |
| Direct structural `CanPSRemote` | 2 | `3bd8da26d86dbf6200673c043b48b182c844c6d43748edc8cabd37fc0a26ea68` |

Full direct MemberOf = 13.324 explicit Members + 2.593 PrimaryGroupSid, overlap 0; toàn bộ 2.493 User và 100 Computer primary edges có positive direct raw provenance.
Primary set digest `b5430bf7724fb1521337c99d43abd8d0e208de59a27cb41f02f00f2662d80f66`.
AdminTo direct selection giữ edge có direct LocalAdmins support dù edge cũng có nested derivation; không chọn intersection để tạo equality.
Historical audit Members-only view vẫn có trong private `evidence.json`; authoritative proof là `accepted_slices.MemberOf`, không đổi audit lịch sử.

Full M1 ledger giữ 17 project-only và 3 Legacy-only, đủ 20 hashed entries cùng raw pointers trong manifest A.
GenericAll 10 và WriteDacl 3 self-ACE, AdminTo 4 derived-only, CanRDP 3 Legacy-only đều giữ `accepted_policy_difference`.
Raw ACE duplicates là tầng đo riêng: GenericAll 164, WriteDacl 2; không giải thích self-edge delta bằng duplicate removal.
Canonical nodes/edges/assessments hashes không đổi khi thêm comparison metadata.
Ba CanRDP assessments khớp đúng raw RemoteDesktopUsers memberships, status `unknown`, reason thiếu UserRights, và project vẫn 0 CanRDP traversal edges.
Assessment digest `1add6bcc161969be35f7b9f921dcc2a0ba9a18d823d186338f7e63268effc28c` giống cả hai runs A.
Đây không phải false/deny evidence; missing, unknown và negative-known vẫn theo contract/ADR hiện có.
ForceChangePassword và HasSession 0/0, raw session rows 0; disposition `not_measurable`, không suy decoder/session/absence/runtime equivalence.
Chín observed Legacy kinds ngoài M1 giữ đầy đủ count/set digests trong `by_kind`, không remap để bù counts.

## Output bindings và cách B đối chiếu

| Fresh generated output A | SHA-256 bytes |
| --- | --- |
| `project.json` | `ad5e5dbb0a1e9ad826180f177025ea086a0209f463d000ac2a3c34ee736af365` |
| `project-comparison.json` | `2883186bffaa791a29e1ecb0cc8c1032a5704aadbdf465a8f03b0d5638429d01` |
| Rebuilt `legacy-comparison.json` | `a59d5d8373572198a8891e18b7dd673d31e8064879793f001ad1732a0ac5d660` |
| Full observation `evidence.json` | `f96479391987327e719607037ecb0c2579574fd39e48aa137c2ba017c8746242` |
| Full `slice-proofs.json` | `178bab8278f59cd134c6f03e8608a9783a05990c4d5e774b5d6daa2f24a9325e` |
| `comparator-stable.json` | `c6a796ff72c55862eda8189c3f67c091d8cc176c96fa977ec79e5594fe42cc2e` |
| Public `manifest.json` / committed artifact | `9c2529fb619a2c6f2a4f7787bc4b2a51fce3303baba1e5b016e5a77575616c49` |

Comparator original output digest và timestamp của từng run được lưu nguyên trong manifest.
`comparator-stable.json` serialize comparator report bằng deterministic UTF-8 JSON của existing exporter, bỏ duy nhất `reconciliation_timestamp`; verdict, eligibility, input digests, counts và scope giữ nguyên.
Parser log có absolute output path nên log digest phụ thuộc local path; manifest cũng có runtime/platform/timestamp nên không yêu cầu toàn bộ manifest B byte-identical với A.
Canonical/comparison/audit/proof/stable-comparator bytes và per-slice/difference/assessment digests là bindings cần B đối chiếu.
Nếu OS newline handling làm original CLI/comparator byte digest khác, ghi discrepancy và kiểm tra decoded payload cùng deterministic set digests; không sửa output để khớp.
[A repeat check](../../reports/research/issue-196-ttsa-repeat-check.json) xác nhận sáu stable output digests, slices và full M1 ledger bằng nhau ở fresh second destination.
Đây là repeat của A, không thay independent B reproduction.
B cần ghi package SHA/harness hash, measured SHA, prerequisites, runtime, commands, own output digests và verdict trong report riêng, hoặc xác nhận cụ thể limitation nếu private inputs không truy cập được.
#196/#47/#48/#158 giữ mở; không claim Week 3 complete.
