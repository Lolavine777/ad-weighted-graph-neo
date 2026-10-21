# Worklog - 2026-10-12 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#264 Phase 1](https://github.com/nairyuuu/ad-weighted-graph/issues/264), [#259](https://github.com/nairyuuu/ad-weighted-graph/issues/259), [#265](https://github.com/nairyuuu/ad-weighted-graph/issues/265); [PR #266](https://github.com/nairyuuu/ad-weighted-graph/pull/266); Week 5; nhánh `research/264-asrep-expert-basis`.
- Thời gian thực tế ước lượng: khoảng 60 phút.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Audit develop và closure | `da21fbb`, issues #264/#259/#265 | Frozen C=3 / High / P=0/4 và Source A 2/24 giữ nguyên |
| Scenario/basis mới | [asrep-expert-v1](../research/ratings/asrep-expert-v1/README.md) | Method etype23, 2^19..2^20 guesses, 20h job / 24h campaign; uniform24 chỉ là counterfactual |
| Independent oracle | Commit `027c2f8`, [oracle](../research/ratings/asrep-expert-v1/oracle.json) | Product [9/1024,21609/400000]; freeze trước flow mới |
| Public generated flow | [evidence](../../reports/research/issue264-asrep-expert-v1-verification.json), execution `b2adb73` | 16 CLI processes; API/CLI/orchestration khớp; sáu negative/control cases đúng oracle |
| Coverage | Mẫu số một valid/conditioned-feasible program | Raw pending P=0/4; synthetic gate copy P=4/4, C=3, High, một Pareto member chỉ để kiểm wiring |
| Historical preservation | 58 byte pins; diff không đổi `src`/`configs` | PASS; không sửa frozen Week 3/4 artifacts |
| Full regression | `.venv/bin/python -m pytest -q` | 2.632 passed, 9 skipped, 48 subtests; launched `488d0bc`; final wrapper có focused rerun riêng |
| Final focused suite | `.venv/bin/python -m pytest -q tests/test_asrep_expert_basis.py` | 30 passed trên `b2adb73`, gồm snapshot CLI regression |
| Quality | Ruff, format, YAML, contract, repository, diff, Compose config | PASS locally; remote CI không start runner vì billing/spending limit |

## Điều học được / quyết định

Ba interval vận hành là pending expert-transfer hypotheses từ câu hỏi lịch sử q2/q3, chưa phải numeric acceptance trong history AS-REP mới.
Recovery [1/32,1/16] có phép suy finite-model rõ nhưng không dùng cho mật khẩu thật chưa biết population/etype/compute floor.
AI advisory review đã giúp bổ sung validation full history, committed-source pins và tách raw/synthetic view digests; không thay human B review.
Research wrapper cần `--snapshot` độc lập nhãn evidence để giữ static facts; không sửa B-owned public implementation.

## Trở ngại và việc kế tiếp

B cần review riêng từng interval/context, uniform24/compute commitment và C/I applicability trong scenario mới; tất cả numeric records vẫn pending, không self-activate.
B-owned delta: public output giữ `estimated_expert_scenario` và actual review disposition/reference bên cạnh native `scenario_assumption`.
Natural-password recovery và Phase 2 broad coverage còn gap; không close #264 hoặc claim Week 4 có thêm P.

B review đã được yêu cầu trên PR #266; [remote evidence](../research/ratings/asrep-expert-v1/remote-ci.json) ghi zero executed steps cho CI và Branch policy, không claim CI PASS.
