# Worklog - 2026-10-12 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #226 / PR implementation chờ cross-review / M3 follow-up
- Thời gian thực tế ước lượng: Không đo thời gian thao tác liên tục; full suite đo 417.79 s.

Refs #226; base develop `7368cac505b3d19331cb8a688114107e91134f25`.
Published executable source: `70bd4c0e9346755b17999f7c71edae74126b2cb1`.
Implementation/evidence bàn giao cho A review; không tự nghiệm thu numeric basis,
đóng #226 hoặc merge PR từ việc tests pass.

## Đã triển khai

- `AttackQuery.top_k`, materialized query và `AttackQueryResult.top_k_result`; CLI
  `--top-k K` trên generator/binding/evaluator hiện có, transport 0.4 và strict schema.
- K độc lập search caps; C-rated/P-I-unrated vẫn được chọn. Ledger lấy từ evaluator,
  không chấm lại bằng hops/edge weights hoặc cộng C/P/I thành weighted score.
- Identity giữ ordered actions, context, branch state, exact edge IDs và causal parents;
  terminal dedup không chỉ theo request sequence. Canonical graph contract không đổi.
- Min-Effort/Top-K dùng cùng canonical tie choice. Inactive extension/zero-work giữ
  payload shape và semantic evidence của bộ fixture đã freeze.
- Truncation, unknown, binding/adapter/C gaps hạ guarantee. Initial goal chỉ có một
  empty program C=0, không tạo P/I/Pareto giả; checkpoint và asset success giữ riêng.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Top-K public query/CLI | `python -m pytest tests/test_top_k_search.py -q` | 34 PASS |
| Migration source pins | `tests/test_rating_source_successors.py`, likelihood/scenario/AS-REP tests | 68 PASS / 2 SKIP |
| Full integrated suite | `python -m pytest -q` | 2641 PASS / 46 SKIP / 48 subtests PASS |
| Reproduction | Public CLI commands trong contract và sanitized evidence | Ba processes mỗi ca khớp semantic/pins |

- Python 3.14.8, dependencies theo `requirements-tests.txt`.
- Full suite: **2641 passed, 46 skipped, 48 subtests passed**, 417.79 s.
  Executable/config/test bytes được đối chiếu với published source commit ở trên;
  final handoff chỉ bổ sung docs/evidence và refresh runtime/source metadata.
- Migration-focused suite: **68 passed, 2 skipped**, gồm immutable AS-REP history,
  source-pin omission, successor historical binding và current-source tamper.
- Ruff check/format, yamllint, repository checks, contract checks và diff whitespace PASS.
- Public CLI chạy ba processes cho mỗi ca E/K=2, T/ties, K=8 và path cap=1;
  semantic outputs và reproducibility pins khớp trong từng ca. C lần lượt `[2,5]`,
  `[2,2]`, `[2,5,5]`, `[5]`. Ca cuối giữ incumbent và không claim K-best.
- CLI measured duration median: 0.1314 / 0.1300 / 0.1395 / 0.1244 s tương ứng.
  Đây là fixture ba programs trên một runtime, không là scalability benchmark.
- Existing acceptance runner chạy hai lần deterministic, 36 PASS / 1 manual NOT EXECUTED /
  1 raw-prerequisite BLOCKED RUN / 0 unexpected FAIL. Frozen semantic digest giữ nguyên
  `sha256:3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d`.

[Contract/commands](../research/week4-top-k-search.md),
[sanitized CLI evidence](../../reports/research/issue226-top-k-synthetic-evidence.json).
Source/input/config/runtime/digests và effective caps được giữ trong evidence package.
Same-machine processes không thay human-independent reproduction.

## Điều học được / quyết định

Maintainer chọn **gộp migration source pins vào #226**, giữ nguyên artifact lịch sử.
Ba files frozen bởi #264 (`likelihood-v1/catalog.json`, `likelihood-v1/manifest.json`,
`scenario-basis-v1/source-manifest-v2.json`) khớp byte-for-byte với baseline.
Successor likelihood source v2 và scenario source v3 bind historical digests và pin
current source, gồm query/identity/Top-K dependencies. Verifier kiểm coverage/tamper;
numeric proposals, adoption gates, oracles và frozen semantic fixtures không đổi.

## Trở ngại và việc kế tiếp

Không có authorized pinned SEAMLESS raw trong checkout, nên private Top-K probe NOT EXECUTED.
46 skips chủ yếu là private/raw prerequisites và Windows-only junction test; không
gọi những ca đó PASS. Local Compose chưa chạy vì không có Docker; remote CI/human
review còn chờ. Baseline finite exhaustive không tối ưu scale hoặc chứng minh toàn graph.
Optimization qua #227; Top-K footholds/destinations và source aggregation qua #265/#268.
