# Worklog - 2026-10-08 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #208, #206, #204 / #231, #233 / M3, Week 4; owner @Lolavine777, reviewer @nairyuuu.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Tích hợp CLI | `develop@f4d1f973`, source freeze `feaf1c093` | Giữ code B; cả CLI/schema và evidence LF policy |
| Acceptance thực | Public CLI stdout/output/compare và oracle A | 38 rows: 34 PASS, 2 pending, 1 not executed, 1 blocked; 0 FAIL |
| Hai process sạch | `reports/research/week4-reproduction.json` | Semantic bytes/digest giống nhau, 94 pins; không là human sign-off |
| Focused verification | CLI/acceptance/demo/checkout-byte pytest trên `e3204f1` | 67 passed; Ruff check/format và diff check PASS |
| Final-head CI | Checks của #231 | Quality phát hiện worklog thiếu mẫu, sửa metadata/sections; Ubuntu/Windows còn chạy tại thời điểm ghi |

## Vấn đề và kết quả

#233 đã được approve và merge tại `develop@f4d1f973ad17d1cb92723bc2243ca85942408762` trong lúc chuẩn bị merge #231. #231 trước đó có B approval đúng `2f7d1e9`, nhưng merge API trả conflict sau base drift. Giữ cả CLI/schema LF policy và acceptance/evidence LF policy; engine/parser/CLI/harness của B giữ đúng bytes nền mới.

A bổ sung W4-CLI-PACKAGE qua subprocess thực: stdout và output file; compare hai process; exact ordered paths và reachable states theo A scenario week4-v1; C/P/I theo Ledger E; empty state và null ranking bị từ chối với exit 1, stderr và không tạo output. Kỳ vọng không được sinh từ actual. Các mutation mọi normative field, missing-field, known-defect recurrence và CLI failure exit được giữ.

Ma trận hiện hành: **38 = 34 PASS, 2 PENDING B, 1 NOT EXECUTED, 1 BLOCKED RUN, 0 KNOWN DEFECT/FAIL**. Ca CLI trước đó NOT EXECUTED chuyển PASS trong phạm vi tổng hợp. AS-REP/RBCD, full docs/API manual audit, authorized private replay và human-independent cross-reproduction vẫn còn mở; #208/#204 không đóng từ scoped acceptance này.

## Nguồn đo và tái lập

Source freeze `feaf1c09340ff01d566bcfe0277eb56dab5517c2`; hai process Linux x86_64/Python 3.14.7 thực thi từ partial checkout sạch, mọi src/scripts/configs và input bắt buộc đều có mặt và được kiểm Git blob SHA. Thời điểm/runtime/revision và CLI subprocess commands/input/source hashes được quan sát riêng trong execution metadata; semantic payload không chứa timestamp hoặc revision biến động. Không coi hai process cùng máy là B human sign-off.

Hai semantic outputs bằng byte, source/input digest khớp; CLI trực tiếp sinh ba chương trình, best generated_0003 C=2, source/proof thuộc declared finite scope. Historical reproduction records được giữ trong historical_runs, không dùng làm actual của nguồn mới. Artifact/report commit giữ đúng 94 source/input pins của source freeze.

```bash
.venv/bin/python scripts/research/week4_acceptance_runner.py --output /tmp/week4-cli-run1.json --semantic-output /tmp/week4-cli-semantic1.json
.venv/bin/python scripts/research/week4_acceptance_runner.py --output /tmp/week4-cli-run2.json --semantic-output /tmp/week4-cli-semantic2.json
.venv/bin/python -m pytest -q tests/test_query_cli.py tests/test_week4_acceptance_manifest.py tests/test_week4_acceptance_review_regressions.py tests/test_week4_acceptance_checkout_bytes.py
```

CLI riêng trên integration candidate: **54 passed**. Clean artifact head `e3204f1`: **67 passed** trong 105.68s cho focused CLI/acceptance/demo/checkout-byte suite. CI cuối ghi tại PR; không nhận full local suite từ các file đã sparse-exclude. Ruff check/format và byte-policy regression được kiểm lại trên source cuối. Demo có 7 Bash blocks, gồm hai CLI runs và compare harness; report/demo giữ tiếng Việt và không chứa tracker references.

## Điều học được / quyết định

Public CLI cần được đối chiếu với expected đã accepted qua subprocess, không suy engine API PASS thành CLI PASS. Observed process metadata giữ ngoài semantic equality. Artifact/docs-only fix giữ nguyên source/input bytes và không tạo measured run mới. Worklog phải validate theo daily-worklog template trước push; CI đã phát hiện omission này và A sửa cấu trúc, không đổi evidence.

## Trở ngại và việc kế tiếp

Head #231 thay đổi source/oracle/evidence để consume #233 nên cần B review lại head mới và exact-head CI. Approval 2f7d1e9 giữ giá trị lịch sử, không tự coi là review ca CLI mới. A tiếp tục raw/query delta #206 và #208; B triển khai #228 AS-REP rồi #229 RBCD. CLI metadata thử nghiệm của B vẫn giữ conservative pending flags cho private/full acceptance; A không thay enum hoặc API của B.
