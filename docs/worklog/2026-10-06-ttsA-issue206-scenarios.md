# Worklog - 2026-10-06 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#206](https://github.com/nairyuuu/ad-weighted-graph/issues/206) / [PR #214](https://github.com/nairyuuu/ad-weighted-graph/pull/214), nhánh `docs/206-week4-scenarios` → `develop`, reviewer yêu cầu `nairyuuu` / M3, Week 4.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.
- Baseline input/oracle: `develop@15720560cfc2ea03a3350335042f704751c83253`, contract 1.3.0, catalog 0.3; PR #209 merged và #205 closed được kiểm live.
- Owner A chuẩn bị đầu vào/kỳ vọng; B review vẫn pending, chưa nghiệm thu runtime Week 4.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Đọc scope và cập nhật baseline | Toàn bộ #206, CONTRIBUTING/repo instructions, Week 4 plan/query contract; `git fetch`, `git pull --ff-only origin develop` | Nhánh riêng từ develop mới nhất; không thực hiện #207/#208/engine của B |
| Audit reuse/gap | [Ma trận và oracle](../research/week4-scenarios.md) | Reuse core golden, false/unknown, cycle/parallel, scoped identity và no-path; chỉ thêm exact programs/state set, initial entitlement/host-only, target delta và semantic caps trên fixture nhỏ |
| Expected package v1.0.0 | [Suite](../../tests/fixtures/attack_scenarios/week4-v1.json), [digest manifest](../../tests/fixtures/attack_scenarios/week4-v1.sha256) | Schema golden 1.0.0 hiện hành; hai scenarios, bốn variants, graph/facts reuse; expected authored trước actual, không schema/harness delta |
| Manual oracle | Proof finite scope và ledger E/T trong tài liệu | Exact successful programs D, M/D, M/I; S0/S1/S2/S3; minimum E=2 theo ledger synthetic, tie T=2 với cả ba programs; numeric bindings/rating #207 pending |
| Delta real CLI hai lượt | `.venv/bin/python -m scripts.research.attack_scenarios --suite tests/fixtures/attack_scenarios/week4-v1.json --output reports/generated/issue206/delta-1.json`, lặp với `delta-2.json`; `cmp` | Cả hai PASS 4 variants, byte equality; report digest `sha256:fa4885a65d3324aa3e86108c90686862dc1fced30fda5f30916b9df9e2963165` |
| Test consumer A2 | [test_week4_scenarios.py](../../tests/test_week4_scenarios.py) dùng runner/schema hiện có | Full state equality thay vì chỉ reachable projections, exact programs, file-byte pins và ba caps riêng; không implement query mapping hoặc score model |
| Suite nền targeted | `.venv/bin/python -m pytest -q tests/test_attack_scenarios.py tests/test_attack_scenarios_seamless.py tests/test_engine.py tests/test_week3_engine_acceptance.py` | 188 passed; không dùng số test để claim query Week 4 mới chạy |
| Raw snapshot thật | `verify_manifest(Path('data/raw/SEAMLESS'), manifest)` | Không lỗi; sáu raw files khớp snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; raw/full mappings giữ local |
| Canonical parser CLI current | Lệnh cụ thể phía dưới, `fail_fast`, `unit`, fixed time policy/export time | 3.370 nodes, 56.367 edges, 3 unknown assessments, 0 warning/error; graph digest `sha256:09b117c2db7c4a6433aea0ca83a47190112099eb492f14cda50a1869f7c41561` |
| Narrow historical SEAMLESS runner | `attack_scenarios_seamless --graph data/processed/issue206-seamless.json --raw-dir data/raw/SEAMLESS --output reports/generated/issue206/seamless-trace-1.json` | Exit 1: current graph khác pin `41fdff96…`, do metadata revision nằm trong graph digest; giữ fail-closed, không thay expected/pin hoặc giả code_version |
| Current raw trace helper | `raw_edge_trace(current_graph, verified_release.query_projections.source_b.candidates[0], raw_dir, raw_manifest)` | PASS ba structural bindings; local `current-raw-trace.json`, trace digest `sha256:31f9cd7cd53c9889d52e27bc0688562775ed31642c87c4b52b0edaa12c7ae9ca`; không gọi narrow runner đã PASS |
| Fresh accepted Source B | Current `week3_engine_acceptance.py`, raw/parser thật, `--require-complete` | PASS; report digest `sha256:ae6d6f17b0f65deb8ebfc2e477ea42fac34a9f83b5bb97e9ab258336cdd2f313`; chỉ replay nền accepted, không query Week 4 mới |
| Required local checks | Ruff check/format, yamllint, repository/contract scripts, SHA manifest, `git diff --check` | Exit 0; 307 Python files formatted; 434 tracked/unignored files checked; 17/17 pins OK |
| Compose config | `NEO4J_PASSWORD=ci-validation-placeholder docker compose --env-file .env.example --profile graph config --quiet` | Exit 0; chỉ validate config, không chạy services |
| Full suite | `.venv/bin/python -m pytest -q` | 1.829 passed, 1 skipped (Windows junction), 48 subtests passed; không chứng minh API Week 4 mới |
| Final docs/contract/A2 targeted | `.venv/bin/python -m pytest -q tests/test_week4_scenarios.py tests/test_repository.py tests/test_contract.py` | 174 passed; A2 riêng 8 passed |
| Review hỗ trợ độc lập | Rà oracle/reuse/AC/provenance; reviewer chạy relevant suites và manifest | Không phát hiện Critical/Important; 196 tests passed và 17/17 pins OK; không thay human B acceptance |
| Deliberate oracle counterexample | Bản sao memory bỏ M/D khỏi expected successful set | Exact-set harness reject như dự kiến; file expected không đổi |

Các counts/digests raw kể trên đo tại baseline input `1572056`; code_version của graph là baseline thực, không ép thành revision của binding lịch sử.
Graph cũ local digest `5781a365…` cũng không khớp narrow binding; việc rebuild current không phải sửa parser hoặc thay raw snapshot.

Lệnh tái lập parser và accepted query nền:

```bash
mkdir -p .cache/issue206 reports/generated/issue206
.venv/bin/python - <<'PY'
from pathlib import Path
from scripts.research.reproduce_seamless_legacy import TIME_POLICY
Path('.cache/issue206/time-policy.json').write_bytes(TIME_POLICY.encode())
PY
.venv/bin/python -m src.parser.cli \
  --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 \
  --raw-dir data/raw/SEAMLESS --manifest-dir data/samples/manifests \
  --profile unit --error-policy fail_fast --created-at 2026-10-01T00:00:00Z \
  --time-policy .cache/issue206/time-policy.json \
  --output data/processed/issue206-seamless.json --summary
.venv/bin/python scripts/research/week3_engine_acceptance.py \
  --case-id w3-source-b-positive --raw-dir data/raw/SEAMLESS \
  --manifest-dir data/samples/manifests --profile unit \
  --created-at 2026-10-01T00:00:00Z --time-policy .cache/issue206/time-policy.json \
  --require-complete --output reports/generated/issue206/source-b-current-1.json
```

Raw trace current tái lập riêng, không bypass pin của narrow runner:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from scripts.research.attack_scenarios import digest
from scripts.research.attack_scenarios_seamless import raw_edge_trace
from scripts.research.reviewed_parameter_release import verify_release
raw = json.loads(Path('data/samples/manifests/seamless-raw-v1.json').read_text())
graph = json.loads(Path('data/processed/issue206-seamless.json').read_text())
release = verify_release(json.loads(Path(
    'docs/research/ratings/week3-closeout/reviewed-release.json').read_text()))
rows = raw_edge_trace(graph, release['query_projections']['source_b']['candidates'][0],
                      Path('data/raw/SEAMLESS'), raw)
report = {'graph_digest': digest(graph), 'snapshot_id': raw['snapshot_id'], 'trace': rows}
Path('reports/generated/issue206/current-raw-trace.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print({'bindings': len(rows), 'trace_digest': digest(report)})
PY
```

## Điều học được / quyết định

Oracle được lập bằng quyền/state và duyệt toàn bộ history trong scope finite trước khi đọc actual output.
Không lấy expected từ implementation mới, không dùng C/P/I để chọn allowed path, không reset provenance/digest để làm test qua.
Membership passive có thể tạo history dư hợp lệ; không xóa history khỏi tie set chỉ vì cùng final state hoặc effort.
Additive Dijkstra và whole-program effort là hai bài toán được báo riêng; no-path khác truncated và khác missing gate.
Test consumer A2 chỉ nối artifact vào CI hiện có; không tạo bộ harness song song hoặc nhận API/parser/engine work của B.

## Trở ngại và việc kế tiếp

B cần nhận mapping Computer source→initial usable identity/context, predicate DA/terminal rule và rejected-assumption ledger trước freeze executable query cases W4-X/DA/C/G-conflict.
Ledger numeric synthetic còn chờ B review và #207 nối scoring; chưa có claim numeric ranking delta đã chạy.
SEAMLESS query Week 4 mới **chưa chạy, pending mapping/interface**; raw verified và trace nền không thay evidence runtime A4.
Narrow SEAMLESS historical binding không nhận metadata revision mới; chuyển B review binding update nếu cần tích hợp tại head mới, không sửa schema/harness trong #206.
Cross-review B và remote CI chờ PR; không tự merge, close #206 hoặc claim Week 4 complete.
CE/roasting deferred theo #205; không mở extension hay converter.

## Cập nhật mở PR

[PR #214](https://github.com/nairyuuu/ad-weighted-graph/pull/214) đã mở với base `develop`, request reviewer `nairyuuu`; commit gói input/oracle là `c4103dd`.
#206 vẫn OPEN; remote CI và human B review chưa hoàn tất tại lúc mở PR.
Commit bổ sung worklog chỉ ghi link/trạng thái bàn giao, không đổi expected package hoặc các SHA pins.
