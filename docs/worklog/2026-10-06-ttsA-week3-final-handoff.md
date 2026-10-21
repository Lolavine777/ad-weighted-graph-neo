# Worklog - 2026-10-06 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #48 #158 #143 #42; M2 / Week 3; nhánh `docs/48-week3-final-handoff`.
- Người chuẩn bị: @Lolavine777 (TTS A); reviewer được yêu cầu: @nairyuuu (TTS B).
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

### Historical checkpoint A trước B final replay/acceptance

Bắt đầu từ fetched `origin/develop@891bda0001b9958e712cff54045f651273b43fd0`, đọc CONTRIBUTING/instructions và live #48/#158/#143/#42/#186.
Live #47/#196 đã closed, #155/#180 đã closed; #186 vẫn `CHANGES_REQUESTED`, required checks của integrated SHA xanh.
Audit giữ accepted #165 model/interface, #176 scoped human-reviewed AI-assisted parameters, #182 final integration, #197 comparison contract và #198/#199 A/B reproduction.
Không chọn lại tham số hoặc sửa parser/engine/comparator/ranking; không kéo Week 4 #192/#200 vào closeout.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Raw E2E | `week3_engine_acceptance.py --require-complete` | 8 cases × 2 fresh runs passed; từng cặp report byte-identical |
| Parser CLI | `src.parser.cli`, fail-fast | 3.370 nodes, 56.367 edges, 3 unknown CanRDP assessments; graph bytes `c10c45a1c60e722404f921e8e559de3e8fe79efe5baf11b95bee9f1e5c8cc09d` |
| Release validate/replay | `reviewed_parameter_release.py validate`, `tests/test_week3_acceptance_manifest.py` | Release digest giữ nguyên; validation file `99ea60c98a4d1ed06e7feb8d436135d3298b458c26ea3fee4a213049fb4ec912`; 21 probes/24 outcomes |
| Synthetic CLI | Existing rich/error fixtures và tampered copy | Happy: 6 nodes/10 edges/1 unknown; fail-fast/tamper exit 1/no output; warning/skip tạo đúng 2 valid nodes |
| Full tests | `.venv/bin/python -m pytest -q` | 1.821 passed, 1 skipped (Windows junction trên Linux), 48 subtests passed |
| Quality | Ruff lint/format, yamllint, repository/contract, Compose config, diff | Passed |
| Source equality | `git diff --exit-code` ở các scopes ghi trong manifest | Không có delta với accepted #196 revisions |

Runtime thực chạy: CPython 3.14.2, Linux x86_64; dependencies đúng requirements, Ruff 0.16.8 sau cài lại pinned dev requirements.
[Final handoff](../reports/week3-final-handoff.md) và [computed sanitized manifest](../../reports/research/week3-final-handoff.json) lưu commands, pins, output digests, gates và limitations.
README, plan/backlog, report/matrix/status, disposition và reproduction handoff được reconcile bằng current amendments, giữ historical checkpoints riêng.
Full ignored outputs/logs ở `.cache/week3-closeout-891bda0`; không publish raw identities hoặc Legacy exports.
Docs được sửa trong lúc chạy sau checkout clean ban đầu; source/runtime inputs không đổi và không có independent B reproduction mới trong lượt này.

## Điều học được / quyết định

Source equality giúp reuse accepted evidence, nhưng không thay một fresh replay/final SHA binding.
Giữ measured runtime/SHA của từng run và scoped acceptance riêng; không chuyển technical component acceptance thành milestone completion.

## Trở ngại và việc kế tiếp

Checkout hiện có raw SEAMLESS nhưng không có private Legacy exports/mapping/importer prerequisites.
Không tạo fresh comparator evidence hoặc gọi accepted #196 runs là chạy trên `891bda0`.
B cần dùng existing replay harness và checksum-pinned private prerequisites để ghi final revision binding của #48, rồi review/accept closeout trên exact head.
#143/#42 có scoped closure evidence sau acceptance; #48/#158 giữ open cho gate thực tế này và human review/checks.
#186 chờ #48/#158 accepted, latest release SHA/checks/full diff review và xử lý outstanding review; không tự merge hoặc claim milestone complete.
Bounded/truncated search không chứng minh global optimum; full Legacy comparator giữ `NOT_MEASURABLE` / exit 2; không claim full BloodHound/CE parity hoặc empirical calibration.

## Current-state amendment sau B acceptance và review #202

B đã [technically accept package #48/#158](https://github.com/nairyuuu/ad-weighted-graph/pull/202#issuecomment-6008927093) sau fresh Legacy replay trên clean measured revision `891bda0001b9958e712cff54045f651273b43fd0`: PASS, exact sets/difference ledger khớp accepted #196; comparator CLI thật `NOT_MEASURABLE` / exit 2.
Package head `3c3566769432ed3b6fb5e36ac0284cc69306920c` có CI/branch policy success; B yêu cầu sửa current-state docs/manifest còn pending cũ trước approval merge.
A đã đối chiếu live PR #202/#201/#186 và issues #48/#158/#143/#42/#192/#200, đồng bộ manifest, README, plan/backlog, disposition và final handoff/status/matrix.
Historical checkpoints và measured A/B revisions giữ riêng; không đổi parser/engine/ranking/comparator, actual ratings hoặc generated runtime outputs.
Manifest ghi CI success tại exact evidence head và link runs; head docs mới cần checks/rereview riêng trên PR trước merge, không giả làm measured SHA.
Còn merge #202 sau B rereview/checks, re-fetch và đóng #48/#143/#42/#158 theo evidence, final release review #186 rồi promote `develop → main` bằng merge commit nếu approval/checks đạt.
#201 chỉ audit checkpoint/asset consistency và request B rereview; không mở research/implementation mới hoặc đóng #192/#200/#174.
Kiểm tra bản sửa current state: repository 425 tracked/unignored files, contract và 2 synthetic fixtures, 171 tests repository/contract/acceptance-manifest, Ruff lint/format, yamllint, Compose config với placeholder password và diff check đều đạt.
Audit xác minh 18 input byte pins, 2 accepted evidence byte pins, measured tree, 8 case boundaries, exact M1 sets/digests và 20-entry ledger của accepted #196; source scopes `src/configs/requirements/scripts/tests` không có delta với `891bda0`.
Không chạy lại raw E2E, private Legacy replay hoặc full engine suite trong lượt sửa tài liệu này; kết quả A/B ở historical checkpoints là evidence đã được dẫn rõ theo revision/runtime.
Source A positive vẫn bounded/truncated 60.000 expansions; full Legacy comparator `NOT_MEASURABLE` / exit 2; không claim CE parity/global optimum/calibrated probability/independent human reliability/live attack.
