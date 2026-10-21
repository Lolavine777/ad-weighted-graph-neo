# Demo local: foothold, effort và can thiệp

Chạy từ repository root với Python 3.14 và Docker Desktop.
Nếu đã có venv3.14 hợp lệ, bỏ bước `uv venv`.
Dùng namespace output mới cho một lượt mới; giữ output cũ để đối chiếu.
Bản chạy thực tế và giới hạn ở [Iteration 18](ITERATION-18.md).

## Chuẩn bị raw và snapshot có facts

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements-tests.txt
.venv/bin/python -m scripts.download_seamless
mkdir -p reports/generated/awg-r04-ce-v1
.venv/bin/python - <<'PY'
from pathlib import Path
import subprocess
from scripts.research.asrep_inputs import seamless_inputs
from src.parser.snapshot_facts import serialize_snapshot

output = Path('reports/generated/awg-r04-ce-v1/snapshot.json')
assert not output.exists(), 'Choose a new namespace instead of replacing a snapshot'
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
graph, _, _, _ = seamless_inputs(Path('data/raw/SEAMLESS'), revision)
output.write_text(serialize_snapshot(graph.to_canonical(), graph.snapshot_facts))
print(len(list(graph.nodes())), len(list(graph.edges())))
PY
```

Kỳ vọng 3.370 nodes và 56.367 edges.
Hàm chuẩn bị chỉ dựng snapshot; các assumptions của query trả về từ helper không được dùng trong demo này.
Các lệnh exposure bên dưới tự biên dịch profile scenario đã công bố.

## Use case 1: một foothold tự tìm đích quan trọng

```sh
AWG_HOST=S-1-5-21-1271839998-3495686680-2211690266-4157
.venv/bin/python -m scripts.exposure \
  --snapshot reports/generated/awg-r04-ce-v1/snapshot.json \
  --source "$AWG_HOST" --authentication-context "$AWG_HOST" \
  --computer-profile computer_usable_identity \
  --machine-identity-provenance scenario://awg-r04/machine-identity/FINWVIR-4157 \
  --scenario-policy seamless-standard-v1 --effort-profile reset-activation-c-v2 \
  --search-order goal_guided \
  --technique scenario_reset_password --technique acquire_reset_identity \
  --technique propagate_group_entitlement \
  --max-sources 0 --max-targets 0 --max-paths 1 --max-steps 3 \
  --max-expansions 6000 --max-cells 12 --global-max-expansions 72000 \
  --output-dir reports/generated/awg-r04-ce-v1/demo-one
```

Đọc `discovery-progress.jsonl` rồi `defender-brief.md` trong output directory.
Lượt đã chạy có 4/12 goals có witness/C1, 8 goals truncated; không phải tám chứng minh no-path.
Entitlement của group DOMAIN CONTROLLERS không đồng nghĩa điều khiển host DC.

## Use case 2: hai compromise độc lập, tự mine can thiệp và tìm bypass

```sh
AWG_HOST=S-1-5-21-1271839998-3495686680-2211690266-4157
AWG_USER=S-1-5-21-1271839998-3495686680-2211690266-1395
.venv/bin/python -m scripts.exposure \
  --snapshot reports/generated/awg-r04-ce-v1/snapshot.json \
  --source "$AWG_HOST" --source "$AWG_USER" --authentication-context "$AWG_HOST" \
  --computer-profile computer_usable_identity --user-profile user_usable_identity \
  --machine-identity-provenance scenario://awg-r04/machine-identity/FINWVIR-4157 \
  --scenario-policy seamless-standard-v1 --effort-profile reset-activation-c-v2 \
  --search-order goal_guided \
  --technique scenario_reset_password --technique acquire_reset_identity \
  --technique propagate_group_entitlement \
  --max-sources 0 --max-targets 3 --max-paths 1 --max-steps 3 \
  --max-expansions 6000 --max-cells 6 --global-max-expansions 36000 \
  --output-dir reports/generated/awg-r04-ce-v1/demo-multi-corrected

.venv/bin/python docs/research/awg-r04/evidence/run_local_remediation.txt
```

Harness đọc nguyên hai public DA queries từ audit vừa tạo.
Nó chọn relationship candidate được executor hỗ trợ theo binding coverage rồi stable ID; không nhập sẵn OLLIE, DENA hoặc đường vào planner.
Native replay, rediscovery và package verifier chạy qua API hiện có.
Đọc `reports/generated/awg-r04-ce-v1/native-remediation-v2/defender-brief.md`.
Lượt thực tế chọn OLLIE→DA, cắt 2/2 programs mẫu nhưng cả hai nguồn vẫn reachable qua DENA với C tìm thấy1.
Đây là hai compromises riêng, không hợp nhất capabilities.

## Đối chứng BloodHound CE thật

Compose riêng pin ba image digests và bind localhost 18080, 17474, 17687.
Đổi project name để có volumes mới; dừng stack demo cùng ports trước khi chạy project khác.
Runner từ chối graph có sẵn dữ liệu và chỉ xóa volumes khi có `--reset-volumes` tường minh.
Không cần xóa volumes để xem hoặc query một lượt đã import.

```sh
.venv/bin/python -m scripts.convert_seamless_ce \
  --output reports/generated/awg-r04-ce-v1/converted

BLOODHOUND_PORT=18080 NEO4J_WEB_PORT=17474 \
.venv/bin/python -m scripts.run_bloodhound_baseline \
  --snapshot seamless \
  --seamless-ce-dir reports/generated/awg-r04-ce-v1/converted \
  --compose-file deploy/bloodhound/compose.seamless.yml \
  --project-name awg-r04-ce-final-v1 \
  --output reports/generated/awg-r04-ce-v1/final-import.json

.venv/bin/python docs/research/awg-r04/evidence/run_ce_comparison.txt \
  --output reports/generated/awg-r04-ce-v1/final-ce-comparison.json

docker compose -f deploy/bloodhound/compose.seamless.yml \
  -p awg-r04-ce-final-v1 logs --no-color \
  > reports/generated/awg-r04-ce-v1/final-server.log
```

Không upload `originals/` hoặc `manifest.json`; runner chỉ upload sáu file trong `inputs/` sau verify.
Converter giữ raw nguyên bytes, đổi schema có manifest riêng, kiểm ngược toàn bộ records/references và từ chối quan hệ ngoài scope.
Log startup có password quản trị local; bản evidence được publish đã che dòng đó.

Comparison harness đọc raw và query Neo4j của graph do CE import, không dùng graph/parser/evaluator AWG làm oracle.
Nó kiểm identities, direct GenericAll/MemberOf và hai nguồn tới DA trước/sau loại đúng membership OLLIE→DA bằng bộ lọc Cypher.
Graph CE lưu trữ không bị sửa bởi phép thử counterfactual này.
Hops2 trên projection, semantic actions3 của native và C1 là ba đại lượng riêng.
C1 là ordinal effort của profile; chưa có minimum proof cho full native search hoặc timing comparison giữa hai sản phẩm.

## Local validation

```sh
AWG_TEST_RAW_SEAMLESS=1 .venv/bin/python -m pytest \
  tests/test_convert_seamless_ce.py tests/test_bloodhound_baseline_runner.py -q
.venv/bin/python -m pytest tests/test_defender_brief.py tests/test_exposure.py \
  tests/test_remediation_runner.py tests/test_remediation_discovery.py \
  tests/test_remediation_prepared_reuse.py tests/test_goal_guided_search.py -q
.venv/bin/python -m ruff check .
.venv/bin/python -m yamllint deploy/bloodhound/compose.seamless.yml
.venv/bin/python -m scripts.check_contract
```

Không cần GitHub CI hoặc teammate approval cho các lệnh này.
Không chạy khai thác trên AD thật.
