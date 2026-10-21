# Week 3 / M2 - final handoff, 2026-10-06

Refs #48 #158 #143 #42; TTS A: @Lolavine777; reviewer & TTS B: @nairyuuu.
**Verdict: technical handoffs accepted; fresh Legacy replay & final revision binding completed by B; B package acceptance confirmed; ready for PR review and merge.**
Revision tích hợp được đo là `develop@891bda0001b9958e712cff54045f651273b43fd0`, sau merge #199.
PR closeout chỉ cập nhật tài liệu/evidence; SHA của PR tài liệu và SHA được đo phải được phân biệt.
Không tự merge #186 hoặc tuyên bố milestone complete từ CI hay bảng gate này.

## Gói evidence và pins

[Manifest cuối](../../reports/research/week3-final-handoff.json) lưu file-byte SHA-256, runtime/dependencies thực tế, commands, case output digests, fresh B Legacy replay binding và nguồn evidence đã accepted.
Full raw, graph, search traces và private Legacy exports tiếp tục ở authorized ignored storage.
Snapshot là `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; sáu raw files phải khớp [manifest](../../data/samples/manifests/seamless-raw-v1.json).
Runtime lượt này: CPython 3.14.2/Linux x86_64 cho E2E của A; CPython 3.14.7/Windows cho fresh Legacy replay & tests của B; dependencies cài đúng `requirements-dev.txt`, gồm `requirements.txt`.
Các lượt A/B #196 dùng CPython 3.14.7 trên macOS/Windows; không trình bày chúng như cùng runtime hoặc cùng code SHA với lượt này.

| Thành phần | Version / digest / nguồn |
| --- | --- |
| Structural graph | Graph Contract 1.3.0; profile `unit`, không nâng `production_ready` |
| Attack semantics | Catalog 0.3; capability/actor switching thuộc semantic state, không thêm structural edge kinds |
| Model/interface | ADR-0013 accepted trong scope #165; ranking/interface 1.0.0, scenario 1.1.0 |
| Actual parameters | Release 1.0.0, `sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358`; 21 choices theo #176 |
| Comparison contract | `seamless-legacy-403-m1-common-v1`, #195/#197; bytes `6a0bce271788560f3b9b32f5a15b824d6db17a874f95bb8a38b968f1714f2ac6` |
| Raw manifest | Bytes `a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d` |
| Time policy | Bytes `3540afa5ff3f4affd9deddd75f3da43409c5885af4ab9b7b2d17a97aac3a2e7b`; timestamp assumed, collection time unknown |
| Legacy private inputs | Nodes `ed4a6aa7775a4bfb5994875243eaf11588cf03cf4301acc1f23ce62fae11839c`; relationships `4071dd8747a18aef4f30b074eeac163cbc7454cfe42a234367e81f8c488cdbf6`; mapping `202a91b951ff9292f57eeb535c65f02bb7063f5c28a6b27589acdc4ae45c570b` |

Time policy bytes được dựng bằng constant `TIME_POLICY` trong existing `scripts/research/reproduce_seamless_legacy.py`.
`--created-at 2026-10-01T00:00:00Z` là fixed export timestamp, không chứng minh thời gian thu thập.
Canonical object digest và file-byte digest là hai đại lượng khác nhau; graph `code_version` thay đổi theo measured SHA nên không đòi graph bytes của revision mới khớp artifact cũ.

## Acceptance audit

| Gate | Evidence accepted / actual | Disposition cuối |
| --- | --- | --- |
| Design/interface/migration #143/#42 | #151/#163/#165, ADR-0013, interface 1.0.0 và route/work identity | Satisfied trong declared scope; không làm lại model |
| Parameters/validation | #176 B-approved, 21 decisions; release verify, rational oracle và 21 probes/24 outcomes | Satisfied theo scoped human-reviewed AI-assisted disposition; không claim independent-rating reliability hoặc empirical calibration |
| Parser/demo #46/#128 | Accepted CLI/rich fixture; current synthetic happy/error/integrity checks | Satisfied; false/unknown và atomic output giữ nguyên |
| Search/bridge/ranking #145/#155/#180 | #146/#167/#179/#181/#182; #155/#180 closed sau accepted final integration | Satisfied; actual generator, exact bindings, oracle comparison sau ranking, truthful caps |
| Reconciliation #47 | #183/#184/#189/#194/#197 và #198/#199; [closure](https://github.com/nairyuuu/ad-weighted-graph/issues/47#issuecomment-6008006657) | Satisfied theo accepted slices/dispositions; PrimaryGroupSid gap đã fix |
| Clean cross-reproduction #196 | A #198 B-reviewed và B #199 A-reviewed; [closure](https://github.com/nairyuuu/ad-weighted-graph/issues/196#issuecomment-6008002642) | Satisfied trong accepted #196 boundary; giữ measured SHAs riêng |
| Current integrated raw E2E | Existing final harness, 8 cases × 2 fresh runs trên `891bda0`, `--require-complete` | Satisfied; evidence ở manifest; B đã review và xác nhận |
| Final revision binding / #48 | Fresh Legacy replay trên `891bda0`, exact sets/differences/unknown và comparator exit 2 khớp accepted #196 | Satisfied; B đã chạy fresh replay trên checkout `891bda0` bằng authorized private prerequisites; graph `code_version` và report `head_commit` khớp `891bda0` |
| #158 package acceptance / #186 promotion | Package docs, exact-head checks, B acceptance và release review | Package #48/#158 accepted bởi B; #186 chuyển sang final-review sau khi PR #202 merge vào develop |

`git diff cc5f971435dc7d14476d6055024f441e398a4ff8 891bda0001b9958e712cff54045f651273b43fd0 -- src configs requirements.txt requirements-dev.txt docs/research/ratings/week3-closeout tests/fixtures/ranking/week3_acceptance_cases.json scripts/research/week3_engine_acceptance.py scripts/reconcile_graph_baseline.py scripts/research/reconcile_seamless_legacy.py scripts/research/export_legacy_reconciliation_baseline.py` không có delta.
Đây là evidence tương thích với run A #196, không phải một Legacy run mới trên SHA cuối.
Source/configs/requirements của run B từ `8535d4` cũng không đổi ở `891bda0`.
#196/#47 không bị mở lại; final integrated package binding của #48 đã được B hoàn thành bằng fresh replay trên `891bda0`.

## Actual E2E và reconciliation verdict

Actual raw E2E: 8 cases × 2 runs đều `passed`, từng cặp output byte-identical; [manifest](../../reports/research/week3-final-handoff.json) giữ exact digests/counters của từng case.
Các ca gồm positive/known-false/runtime-unknown ở Source A/B và structural-missing/telemetry-missing ở Source A.
Full pytest: 1.821 passed, 1 skipped (Windows junction trên Linux), 48 subtests passed; Ruff lint/format, yamllint, repository/contract, Compose config và diff checks đạt.
Lượt current A bắt đầu ở checkout clean rồi cập nhật docs trong khi chạy; parser/runtime inputs không đổi, không gọi lượt này là independent B clean reproduction.

Luồng tự động là raw checksum verification → parser fail-fast → canonical graph → case evidence view/runtime projection → bounded `generate_attack_paths` → exact ordered bindings → assessment → Pareto và separate Min-Effort.
Graph hiện có 3.370 nodes, 56.367 edges, 3 unknown CanRDP assessments; số 53.774 trước PrimaryGroupSid fix là lịch sử.
Source A positive sinh 23 paths, 60.000 expansions; eligible reviewed programs là direct/alternative, C=2/3, I=High và exact P theo [báo cáo](week3-report.md).
Source A frontier giữ hai programs incomparable; Min-Effort chọn direct program trong eligible evaluated set.
Source B là query riêng; positive program có C=2, I=High và cùng P của direct A.
False/unknown/missing cases được kiểm bằng designated decision và evidence delta, không chỉ kiểm absence hoặc counts.
Generated IDs giữ authoritative qua ranking; reviewed/oracle IDs chỉ dùng đối chiếu sau đánh giá.
Dominance/ties/incomparability, dedup/overlap, first-goal và cap propagation còn được kiểm bởi existing conformance suite.

[A reproduction](../research/issue-196-clean-checkout-reproduction.md) và [B reproduction](../research/seamless-legacy-403-final-reproduction.md) giữ full exact-set digests cùng 20 sanitized M1 difference entries.
MemberOf full direct bằng `Members[] ∪ PrimaryGroupSid`: 15.917 triples, gồm 13.324 explicit và 2.593 primary, overlap 0.
Non-self GenericAll 37.034, non-self WriteDacl 3.392, direct AdminTo 5 và CanPSRemote 2 đạt exact equality trong accepted scopes.
GenericAll/WriteDacl self-ACE 10/3, derived-only AdminTo 4 và Legacy CanRDP 3 là accepted policy differences.
CanRDP project giữ 3 unknown assessments và 0 positive traversal edges; ForceChangePassword/HasSession không có observations, giữ `not_measurable`.
Full Legacy comparator giữ `NOT_MEASURABLE` / exit 2 vì `export_complete is not verified true`; harness success không nâng verdict thành `MATCH`.
Legacy import errors/rejections/duration lịch sử vẫn unknown; không suy thành zero.

### Fresh Legacy replay & final revision binding của B (@nairyuuu)

Từ checkout sạch của measured revision `891bda0001b9958e712cff54045f651273b43fd0`, TTS B đã dùng authorized private prerequisites tại `.cache/issue196-prerequisites` (đã verify 6 files byte-for-byte theo sha256 pins) và raw SEAMLESS (6 files verified theo manifest `seamless-raw-v1.json`):

1. **Replay command:**
```bash
python scripts/research/reproduce_legacy_reconciliation.py \
  --raw-root data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --prerequisites-dir .cache/issue196-prerequisites \
  --work-dir .cache/week3-final-legacy-replay \
  --report-output .cache/week3-final-legacy-replay/reproduction-report.json
```
- Status: `PASS` (exit code 0).
- Generated canonical graph: 3.370 nodes, 56.367 edges, 3 unknown CanRDP assessments; canonical digest `c10c45a1c60e722404f921e8e559de3e8fe79efe5baf11b95bee9f1e5c8cc09d`, `code_version`: `891bda0001b9958e712cff54045f651273b43fd0`.
- Report `head_commit`: `891bda0001b9958e712cff54045f651273b43fd0`; `base_develop_revision` giữ `8535d44771ec9ec1960b4e883103f83654cc1d4f` (historical provenance #196).
- Report file SHA-256: `161ef577c259ab5caaaf604e6a0f3879507262f8d1cb1f699116036ff0f70933`.
- Comparator API gate: verdict `NOT_MEASURABLE`, summary: `Reconciliation pending: legacy-comparison: export_complete is not verified true`, expected exit code: 2.

2. **Comparator CLI real execution:**
```bash
python scripts/reconcile_graph_baseline.py \
  --candidate .cache/week3-final-legacy-replay/project-comparison.json \
  --baseline .cache/issue196-prerequisites/legacy-comparison.json \
  --mapping .cache/issue196-prerequisites/identity-mapping.json \
  --summary
```
- Observed verdict: `[NOT_MEASURABLE] Reconciliation pending: legacy-comparison: export_complete is not verified true`.
- Observed actual CLI exit code: **2**.

3. **Đối chiếu exact directed sets và difference ledger với accepted #196:**
Tất cả các slice đều đạt exact equality tuyệt đối với accepted #196:
- MemberOf: 15.917 triples (13.324 explicit + 2.593 PrimaryGroupSid, overlap 0).
- GenericAll non-self: 37.034 exact match; 10 project-only self-ACE accepted policy difference.
- WriteDacl non-self: 3.392 exact match; 3 project-only self-ACE accepted policy difference.
- AdminTo direct: 5 exact match; 4 derived-only; 1 direct-and-derived coalesced.
- CanPSRemote: 2 exact match.
- CanRDP: Legacy có 3 structural edges; project có 3 unknown assessments (userrights=false, reason=incomplete), 0 positive traversal edges.
- ForceChangePassword & HasSession: 0 observations, disposition `not_measurable`.
- Outside M1: 15.243 relationships giữ `unsupported`.
- M1 difference ledger: 20 mục sanitized differences và multiplicity hoàn toàn trùng khớp accepted #196.

## Demo và lệnh tái lập

Brief tiếng Việt: trình bày pins/phạm vi, synthetic happy/error/unknown, current raw E2E, exact Legacy slices/differences, rồi gates và limitations.
Nhóm chọn scenario, assumptions, parameter values/rationale và reviewed policy dispositions; scripts xác minh inputs, tự sinh ứng viên, tính/rank và chứng minh exact sets.
Không gọi manual decisions là measured observations hoặc gọi supplied replay là generated search.
Synthetic walkthrough có sẵn ở [parser demo](../../data/samples/parser-demo/MENTOR_WALKTHROUGH.md); assessments ở canonical JSON, Neo4j structural projection không thêm assessment traversal edges.

Từ checkout đúng SHA được đo, cài dependencies vào `.venv`, rồi chạy:

```bash
mkdir -p .cache/week3-closeout-review
.venv/bin/python - <<'PY'
from pathlib import Path
from scripts.research.reproduce_seamless_legacy import TIME_POLICY
Path('.cache/week3-closeout-review/time-policy.json').write_bytes(TIME_POLICY.encode())
PY
.venv/bin/python scripts/research/reviewed_parameter_release.py validate \
  --release docs/research/ratings/week3-closeout/reviewed-release.json \
  --output .cache/week3-closeout-review/validation.json
for run in 1 2; do
  for case_id in w3-source-a-positive w3-source-a-known-false \
    w3-source-a-runtime-unknown w3-source-a-structural-missing \
    w3-source-a-telemetry-missing w3-source-b-positive \
    w3-source-b-known-false w3-source-b-runtime-unknown; do
    .venv/bin/python scripts/research/week3_engine_acceptance.py \
      --case-id "$case_id" --raw-dir data/raw/SEAMLESS \
      --manifest-dir data/samples/manifests --profile unit \
      --created-at 2026-10-01T00:00:00Z \
      --time-policy .cache/week3-closeout-review/time-policy.json \
      --require-complete \
      --output ".cache/week3-closeout-review/run${run}-${case_id}.json" || exit "$?"
  done
done
.venv/bin/python -m pytest -q
```

Legacy replay từ checkout sạch của final revision dùng existing B harness và authorized checksum-pinned prerequisites, output directory mới:

```bash
.venv/bin/python scripts/research/reproduce_legacy_reconciliation.py \
  --raw-root data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --prerequisites-dir .cache/issue196-prerequisites \
  --work-dir .cache/week3-final-legacy-replay \
  --report-output .cache/week3-final-legacy-replay/reproduction-report.json
```

Harness A `reproduce_seamless_legacy.py` cố định `cc5f971`; không sửa pin hoặc quảng bá nó là chạy `891bda0`.
Harness B ghi actual `head_commit`; `base_develop_revision` vẫn là provenance #196, nên reviewer phải đối chiếu actual head với revision release được chốt.
Required checks theo README gồm Ruff lint/format, yamllint, repository/contract checks, pytest và exact PR-head CI/branch policy; Compose config dùng placeholder theo CI khi có Docker.

## Gate còn lại và trình tự đóng

Fresh Legacy replay/final binding, exact sets/difference ledger, comparator CLI exit 2 và technical acceptance #48/#158 đã hoàn tất theo [B acceptance](https://github.com/nairyuuu/ad-weighted-graph/pull/202#issuecomment-6008927093).
Exact package head `3c3566769432ed3b6fb5e36ac0284cc69306920c` có [CI success](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/37410384187) và [branch policy success](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/37410384144).
Measured revision giữ `891bda0`; head sửa tài liệu được kiểm CI và B rereview riêng trên PR, không đổi measured runtime hoặc biến technical acceptance thành approval merge mới.

1. Merge #202 sau B rereview sửa current state và required checks đạt trên head mới.
2. Re-fetch live merged state, đóng #48, scoped parents #143/#42 rồi #158 theo closure evidence.
3. Final release review #186 trên latest `develop`, full release diff/data policy, exact-head checks và A/B approval.
4. Promote `develop → main` bằng merge commit nếu final review/checks đạt.

Bounded/truncated search không chứng minh global optimum hoặc global absence; Min-Effort/frontier chỉ áp dụng cho eligible candidates đã đánh giá.
Không claim full Legacy/BloodHound/CE parity, calibrated probabilities, live attack hoặc independent human reliability.
Week 4 #192/#200, scalable search/Top-K và choke points giữ scope riêng; không kéo vào Week 3 closeout.
