# Helper GoodHound lịch sử, 24/10/2026

Các file trong `evaluation/` và `suitability/` được thu hồi nguyên bytes từ checkout holdout local ngày 25/10/2026.
Hai `evidence-manifest.json` khớp SHA256 đã công bố trong [evaluation summary](../../../../reports/neo/goodhound-evaluation-results.json) và [positive-control summary](../../../../reports/neo/goodhound-positive-control-results.json).
`tests/test_goodhound_archive.py` kiểm tiếp hash từng helper với manifest đó; không format hoặc sửa script lịch sử.
Ngoài bảy helper trong issue #4, giữ `prepare-comparison.py` vì CE driver cần comparison pack, cùng time policy gốc vì thời gian thu thập chưa xác nhận.
Không kèm raw, credential, database hoặc output lớn.

## Tái lập input từ checkout mới

Dùng Python 3.14 trong `.venv` theo README repo và chạy từ repo root.
Các lệnh shell dưới đây dành cho macOS/Linux; mọi thư mục output phải chưa tồn tại.
ZIP public được pin ở commit `c2d8915619d54c752425e6e3fdee3ac8499b32f2`, Git blob `d7bb8cd6ed79796e6413d9d3a3ca45892b70dfdd`, SHA256 `8477a020eb9312ce469177500941f23f13563bdae3f2a4813370c174e72dc4ed`.
Helper tự kiểm SHA256 trước khi đọc ZIP.

```sh
mkdir -p reports/generated
curl --fail --location 'https://raw.githubusercontent.com/idnahacks/GoodHound/c2d8915619d54c752425e6e3fdee3ac8499b32f2/Sample%20SharpHound%20Output/20211017151337_BloodHound.zip' --output reports/generated/goodhound-source.zip
PYTHONPATH=. .venv/bin/python docs/research/evidence/goodhound-20261024/evaluation/reproduce-inputs.py reports/generated/goodhound-source.zip reports/generated/goodhound-inputs
.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib, json, shutil
report = json.loads(Path('reports/neo/goodhound-evaluation-results.json').read_text())
inputs = Path('reports/generated/goodhound-inputs')
for name, key in [('original', 'raw'), ('adapted', 'adapted'), ('ce6', 'ce')]:
    actual = 'sha256:' + hashlib.sha256((inputs / (name + '-manifest.json')).read_bytes()).hexdigest()
    assert actual == report['input'][key + '_manifest_sha256']
old = Path('reports/generated/goodhound-evaluation-20261024-v1')
old.mkdir(exist_ok=False)
shutil.copytree(inputs / 'adapted', old / 'adapted-input-v2')
shutil.copyfile(inputs / 'adapted-manifest.json', old / 'adapted-manifest-v2.json')
shutil.copyfile('docs/research/evidence/goodhound-20261024/evaluation/time-policy.json', old / 'time-policy.json')
print('Three manifest hashes match the published report.')
PY
.venv/bin/python -m scripts.neo_import --raw-dir reports/generated/goodhound-evaluation-20261024-v1/adapted-input-v2 --manifest reports/generated/goodhound-evaluation-20261024-v1/adapted-manifest-v2.json --time-policy reports/generated/goodhound-evaluation-20261024-v1/time-policy.json --export-prefix 20211017151337 --output-dir reports/generated/goodhound-evaluation-20261024-v1/import-adaptation-v2
```

Kỳ vọng 1.387 nodes và 24.781 edges; original/adapted/CE6 manifests phải khớp ba hash trong report.
Adaptation giữ riêng hai membership chưa giải được, không sửa raw hoặc core.
Snapshot mới có metadata thời điểm dựng hiện tại; không tuyên bố toàn bộ snapshot byte-identical với snapshot lịch sử.

## Native cohort và controls, khi cần tái lập nghiên cứu

Không cần chạy phần này để mở viewer hoặc demo hai use case.
Các helpers suitability có `OUT` là thư mục chứa script và `OLD` cố định tại `reports/generated/goodhound-evaluation-20261024-v1`.
Để có hai matrix đầu vào cho freeze, chạy nguyên hai command từ report, không đổi nguồn/budget/scenario:

```sh
.venv/bin/python - <<'PY'
import json, subprocess
from pathlib import Path
recipe = json.loads(Path('reports/neo/goodhound-evaluation-results.json').read_text())['reproduction']
for key in ('primary_native_command', 'secondary_native_command'):
    subprocess.run(recipe[key], check=True)
PY
mkdir reports/generated/goodhound-controls-new
cp docs/research/evidence/goodhound-20261024/suitability/*.py reports/generated/goodhound-controls-new/
PYTHONPATH=. .venv/bin/python reports/generated/goodhound-controls-new/run-controls.py
PYTHONPATH=. .venv/bin/python reports/generated/goodhound-controls-new/check-ranking.py
```

`run-controls.py` freeze trước khi query; `check-ranking.py` chạy lại và assert candidate IDs/C, Top-3 trong tập trả về và recipe C=3.
Hai bước dưới là tùy chọn để tái lập remediation lịch sử, có thể sinh gần 2 GB evidence:

```sh
PYTHONPATH=. .venv/bin/python reports/generated/goodhound-controls-new/run-remediation.py
PYTHONPATH=. .venv/bin/python reports/generated/goodhound-controls-new/rebuild-counterfactual.py
```

Cần giữ `membership-points.json` từ `run-remediation.py` trước bước rebuild.
Chỉ dùng thư mục output mới; nhiều file lịch sử dùng `write_text` và không tự chống ghi đè.
Đây là phục hồi script gốc, không thêm runner hoặc sửa portability ngầm.

## CE và mức kiểm chứng thực tế

Hai CE driver và `prepare-comparison.py` được lưu để đối chiếu lịch sử, chưa phải recipe CE tự chứa an toàn để chạy trên máy có database cũ.
Chúng hard-code project `neo-goodhound-20261024-adaptation-v2`, các cổng 48080/48474/48687 và một số đường dẫn evidence; CE driver còn cần `input-metadata.json`, manifests, comparison pack và dữ liệu đã ingest.
`run-ce-controls.py` có DELETE/restore membership trong database đó.
Không chạy trực tiếp các driver này trên project/volume có sẵn.
Muốn chạy lại CE phải dùng project và volume mới, đối chiếu image digests trong report, sửa rõ project/ports/paths trên **bản sao dùng cho lượt mới**, rồi ghi diff portability; không gọi bản sửa là helper lịch sử nguyên bản.
Lượt wrap-up không chạy CE, không khởi động Docker và không thay các volume cũ.

Đã kiểm trên checkout sạch: cài dependencies khóa phiên bản, tải ZIP đã pin, chạy helper input, khớp cả ba manifest và nhập snapshot.
Đã chạy `run-controls.py` và `check-ranking.py` trên snapshot vừa dựng, dùng bản sao hai matrix lịch sử chỉ làm đầu vào hash của freeze; không tính chúng là cohort vừa chạy lại.
Kết quả controls/ranking mới và phạm vi kiểm nằm trong [nghiệm thu](../../../../reports/neo/thesis-v1/acceptance.md).
Full cohort, remediation và CE lịch sử không chạy lại trong wrap-up.
Vì thế GoodHound có helper gốc và tái lập input/native controls đã kiểm, nhưng **chưa tái lập đầy đủ toàn bộ nghiên cứu từ checkout**.
