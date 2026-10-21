# AWG-R03 - Kết quả triển khai #294

Ngày kiểm chứng: 2026-10-16 UTC.
Đã hoàn thành ba thay đổi trong [handoff](../awg-r03/HANDOFF.md): phối hợp actor trong state của từng nhánh, tương thích CLI với trường null, và tái dùng catalog đã xác thực qua search/replay.
Gemini `gemini-3.8-flash-high` thực hiện implementation qua CLI `agy`, được yêu cầu đọc bản hướng dẫn AGENTS.md kế thừa từ user.
Codex kiểm tra reproducer, diff, oracle, kết quả chạy và bằng chứng benchmark; một reviewer độc lập kiểm tra tĩnh và các sửa đổi sau review.
Đây là bằng chứng kỹ thuật trong phạm vi fixture hữu hạn, chưa phải nghiệm thu dữ liệu riêng hoặc phê duyệt tham số C/P/I.

## Revision và tính toàn vẹn

| Vai trò | Revision |
| --- | --- |
| Baseline đã audit, cũng là `origin/develop` lúc bắt đầu | `340e8e526e1e693d4c4b55635c459985eb08fa49` |
| Handoff đã fetch | `f18e7af33584c1cc1c35b7b4fb208daf3c649769` |
| Native-before: cùng sửa lỗi actor/CLI, chưa tối ưu catalog | `d9ab2e143a4264132ce280b58b50b298b4ed5d15` |
| Native-after: revision chạy toàn bộ test, F1 và benchmark | `d729a7031350edcb7af3ac5a3d6e1e266a2394cc` |
| Công cụ đóng gói phân biệt test/subtest, đã chạy positive/negative controls | `d09cf2b` |

Native-before được tạo từ `55365a1` và bản sửa bảo toàn withheld relationships, có trong `correctness-before/native-before.bundle` của gói kiểm chứng.
Bundle có prerequisite `55365a1186ccb000480bb399ea5cb85a2f6df158`, là ancestor của nhánh implementation.
Production, config và test source không đổi sau revision native-after; commit tiếp theo chỉ sửa cách đếm JUnit trong công cụ đóng gói và thêm báo cáo/bằng chứng.
Mọi record đo giữ revision/tree, trạng thái dirty, patch hash, interpreter, dependencies, lệnh chạy và hash của runner/input.

Sáu file công bố dưới `docs/research/awg-r03/` giữ nguyên byte so với handoff.
Archive R02 vẫn có SHA-256 `9f0180fce0db17902e361857262a89ac6e89391df6460bf8b41812f082b1d64a`.
Runner kiểm tra lại 147 checksum entries trước mỗi lần chạy.
Các rating/acceptance artifact lịch sử cũng được giữ nguyên; source successors và acceptance v5/cases v3 được sinh vào tên mới bằng generator hiện có.

## Hành vi sau sửa

1. `search.py` chọn lại actor đủ điều kiện từ accumulated state của từng nhánh và đúng authentication context.
   Case U@X/V@X có đủ sáu thứ tự hợp lệ, bao gồm chính xác `U:H1 -> V:H2 -> U:H3` với typed goal yêu cầu cả ba host.
   Chọn actor không tạo transition, credential hoặc activation giả; request giữ actor thật và path giữ initial actor/source.
   Evaluator, first-goal termination và used-action restrictions được giữ nguyên.
   Cùng một iterator điều khiển expansion và kiểm tra còn việc khi chạm cap, kể cả actor khác.
   Withheld HasSession vẫn tạo chẩn đoán indeterminate và không trở thành bằng chứng no-path.
2. `query_cli.py` bỏ riêng `graph:null` và `catalog:null` trước kiểm tra unsupported embedded payload.
   Omitted, null-graph, null-catalog và cả hai null đều exit 0 với external graph và có toàn bộ semantic payload bằng nhau.
   Baseline tái hiện exit codes `0,1,1,1`; implementation là `0,0,0,0`.
   Embedded graph/catalog thật và candidate payload vẫn bị từ chối.
3. `catalog.py` dùng `lru_cache(maxsize=32)` theo đúng bytes của file, trả tuple Technique bất biến đã validate.
   File vẫn được đọc lại để thay đổi nội dung không bị che bởi path/mtime; default/custom catalogs có identity theo nội dung.
   Credential/RBCD reference lookup vẫn lấy recipe mặc định authoritative và kiểm tra toàn bộ recipe/gate.
   Catalog đã chuẩn bị được truyền qua query/ranking verification tới semantic replay.
   Không cache AttackState, runtime facts, applicability hoặc rating.
   `load_catalog("")` tiếp tục fallback về catalog mặc định như API trước đây.

Các thay đổi production nằm ở `search.py`, `query.py`, `query_cli.py`, ranking orchestration/verification và semantics catalog/credentials/RBCD.
Regression mới tập trung ở `test_search_actor_scheduling.py`, `test_catalog_reuse.py` và test CLI; các test rating/acceptance hiện có được cập nhật theo oracle độc lập và successor artifact.
Ruff chỉ loại trừ đúng extraction helper đã công bố để giữ nguyên evidence lịch sử.

## Kiểm chứng và semantic deltas

- Toàn bộ suite ở native-after: **3.146 test PASS, 99 subtest PASS, 140 SKIP, 0 failure/error**.
- Bốn nhóm test rời nhau bao phủ đúng 3.286 collected cases, gồm đủ chín module F0; lệnh, collection, logs và JUnit được giữ trong archive.
- Skip theo prerequisite raw/telemetry hoặc nền tảng, gồm hai raw-only test trước đây thiếu guard khi thư mục SEAMLESS vắng mặt.
- Ruff check/format, yamllint, contract/repository checks, Compose config với mật khẩu placeholder, diff check và integrity check đều exit 0.
- F1 đạt **78/78** trên 12 nhóm finite-model độc lập; **99 witness** đều hợp lệ, so với 67 ở baseline.
- Shared-work native ranking vẫn chứng minh minimum **C=5**, Top-K proof đúng; P/I vẫn `unrated` khi thiếu basis.
- Cả 78 normalized native outputs trước/sau tối ưu catalog bằng nhau, chỉ loại các trường thời gian khỏi so sánh này.
- Cả bốn full public semantic payload benchmark bằng nhau theo bytes trước/sau, gồm materialization, attempts, candidates, ranking, provenance và guarantee flags; chỉ outer CLI runtime metadata nằm ngoài payload.

Actor scheduling mở thêm chương trình hợp lệ, vì vậy không giữ path count của planner cũ làm golden:

| F1 case / variant | Baseline paths | Sau sửa |
| --- | ---: | ---: |
| 3 / true, declared reset-credential control | 2 | 4 |
| 4 / true, declared password control | 7 | 31 |
| 9 / actor composition | 0 | 6 |

Các variant khác giữ path count; reachability, Unknown/False/context và minimum-C đều khớp oracle.
Fixture source-A hiện có 330 first-goal programs trong cap 10 bước thay vì 24, được đối chiếu bằng mô hình độc lập trên inventory khai báo và ba membership steps, không lấy output planner làm expected.
24 witness lịch sử vẫn được kiểm tra theo ordered semantic program thay vì candidate ID đã dịch vị trí.
Trong bản sao mô phỏng review của historical rating probe vẫn chỉ hai chương trình đủ rating và 328 chương trình P-unrated; không thêm evidence hay phê duyệt số mới.
Acceptance overlap hiện chạm `path_limit_reached` ở đúng 50 paths thay vì step limit cũ; mọi normative assertion và verdict khác giữ nguyên.
AS-REP một chương trình duy nhất có thể complete khi vừa đạt `max_paths=1` và không còn candidate hợp lệ; điều đó không tạo minimum/no-path proof khi chưa có basis.
Ca R01 nguyên văn về tạo quyền mới riêng cho Alice vẫn chưa được catalog biểu diễn; không nhận là đã triển khai ca đó.

## Benchmark native trước/sau

Cả hai revision dùng cùng CPython **3.14.2**, pinned `requirements-tests.txt`, runner, input và budget.
R02 lịch sử dùng 3.14.8; số dưới đây là phép so mới trong cùng môi trường 3.14.2, không trộn với timing R02.
Mỗi fixture/revision chạy trong process mới: một pipeline đầu và ba pipeline warm, tuần tự sau khi toàn bộ test kết thúc.
cProfile chạy bằng invocation riêng sau các trial timing.
Các số là native API pipeline, không gồm interpreter startup.
Không bật catalog/state-merge monkeypatch thử nghiệm; instrumentation trial chỉ tách phase, đưa search result đã đo vào rating để tránh chạy search hai lần, và đo internal replay riêng.
Một execution native không instrument, nằm ngoài timing/profile, giữ full public semantic output để so sánh.

Đơn vị giây; warm là median của ba trial, khoảng là min-max của ba trial đó.

| Fixture | First pipeline B -> A | Warm median B -> A | Warm range B -> A | B/A |
| --- | ---: | ---: | --- | ---: |
| two-routes | 0.456 -> 0.124 | 0.351 -> 0.100 | 0.349-0.368 -> 0.093-0.105 | 3,50x |
| AS-REP | 0.579 -> 0.178 | 0.425 -> 0.165 | 0.422-0.445 -> 0.155-0.195 | 2,58x |
| RBCD | 2.290 -> 0.363 | 2.289 -> 0.340 | 2.287-2.342 -> 0.335-0.358 | 6,74x |
| RBCD + padding | 3.559 -> 1.533 | 3.545 -> 1.462 | 3.542-3.585 -> 1.454-1.475 | 2,43x |

Padding thêm 1.001 group và 1.000 edge; không thêm exposure độc lập cho ba thứ tự RBCD.
Catalog setup được đo trước khi fixture factory có thể làm ấm catalog; chi phí factory là chi phí tạo input/graph/packet riêng.
First pipeline phía trên chạy sau hai bước setup đó, không phải end-to-end cold CLI latency.

| Fixture | Catalog setup B/A | Fixture factory B/A | First pipeline + catalog B/A |
| --- | ---: | ---: | ---: |
| two-routes | 0.053 / 0.050 | 0.080 / 0.061 | 0.509 / 0.175 |
| AS-REP | 0.050 / 0.050 | 0.218 / 0.080 | 0.629 / 0.227 |
| RBCD | 0.050 / 0.053 | 0.151 / 0.082 | 2.340 / 0.416 |
| RBCD + padding | 0.054 / 0.052 | 0.725 / 0.620 | 3.612 / 1.585 |

Phase của chính trial warm có total ở median, đơn vị ms.
Rating exclusive không chứa replay; rating inclusive trong JSON bằng exclusive cộng internal replay, không cộng replay hai lần vào total.

| Fixture | Rev | Graph prep | Query prep | Search | Replay | Rating exclusive | Serialize | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| two-routes | B | 14.442 | 43.437 | 1.432 | 217.372 | 67.501 | 6.701 | 350.885 |
| two-routes | A | 14.537 | 0.346 | 1.376 | 1.458 | 75.911 | 6.669 | 100.297 |
| AS-REP | B | 71.712 | 43.173 | 17.000 | 232.573 | 52.002 | 8.506 | 424.966 |
| AS-REP | A | 58.284 | 0.491 | 16.189 | 16.347 | 63.812 | 9.481 | 164.604 |
| RBCD | B | 57.807 | 43.183 | 653.950 | 1341.195 | 142.875 | 50.142 | 2289.153 |
| RBCD | A | 58.785 | 0.539 | 26.954 | 51.027 | 146.115 | 56.313 | 339.734 |
| RBCD + padding | B | 305.196 | 61.058 | 783.224 | 1668.958 | 676.755 | 50.295 | 3545.485 |
| RBCD + padding | A | 294.666 | 11.054 | 128.949 | 339.863 | 635.955 | 51.437 | 1461.923 |

Số lần parse YAML catalog và validate catalog bằng nhau trong từng scope dưới đây; không phải tổng mọi YAML load của toàn pipeline.

| Fixture | Catalog setup B -> A | First pipeline B -> A | Warm pipeline B -> A | Search B -> A |
| --- | ---: | ---: | ---: | ---: |
| two-routes | 1 -> 1 | 6 -> 0 | 6 -> 0 | 0 -> 0 |
| AS-REP | 1 -> 1 | 9 -> 0 | 6 -> 0 | 0 -> 0 |
| RBCD | 1 -> 1 | 45 -> 0 | 45 -> 0 | 14 -> 0 |
| RBCD + padding | 1 -> 1 | 45 -> 0 | 45 -> 0 | 14 -> 0 |

Sau tối ưu, padded profile còn nổi bật graph validation/conversion, snapshot binding/digest/serialization và deepcopy.
Trong fixture nhỏ, YAML graph-contract của `src/parser/serialization.py::_contract` vẫn chiếm chi phí; đó không phải catalog YAML đã cache.
Bước nhỏ tiếp theo có căn cứ là đo và giới hạn việc tải/parse graph contract bất biến, rồi đánh giá riêng các lần validate/convert graph lặp lại.
Chưa triển khai cache graph/runtime state hoặc prepared-graph refactor trong scope này.
Không đặt ngưỡng speedup theo hardware, không coi ba warm samples là chứng minh tốc độ production, và không suy rộng sang full SEAMLESS khi chưa có raw manifest-verified.

## Bằng chứng và tái chạy

[summary.json](summary.json) giữ raw trial/profile records và provenance.
[AWG-R03_Verification.zip](AWG-R03_Verification.zip) chứa F1, shared-work, input snapshots, full semantic outputs, pstats/JSON, JUnit/logs, review, CLI reproducer, negative controls và Git bundle native-before.
[manifest.json](manifest.json) giữ SHA-256 archive; `MANIFEST-SHA256.json` trong archive pin từng entry.
Công cụ đóng gói đã nhận dữ liệu hợp lệ và từ chối cả profile sai revision lẫn file semantic bị sửa.
Toàn bộ 78 outputs được so exact native semantics và bốn payload benchmark được so exact bytes trước khi đóng gói.

Từ repository checkout đã có nhánh implementation và `.venv` với pinned requirements, dùng các output path mới:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m yamllint .
.venv/bin/python scripts/check_contract.py
.venv/bin/python scripts/check_repository.py
NEO4J_PASSWORD=ci-validation-placeholder docker compose --env-file .env.example --profile graph config --quiet
.venv/bin/python docs/research/awg-r03/prepare_evidence.py --output /tmp/awg-r03-original
unzip docs/research/awg-r03-implementation/AWG-R03_Verification.zip -d /tmp/awg-r03-verified
git fetch /tmp/awg-r03-verified/correctness-before/native-before.bundle refs/heads/validation/294-native-before
git worktree add --detach /tmp/awg-r03-before FETCH_HEAD
git worktree add --detach /tmp/awg-r03-after d729a7031350edcb7af3ac5a3d6e1e266a2394cc
.venv/bin/python scripts/research/awg_r03_validation.py --repo /tmp/awg-r03-after --evidence-root /tmp/awg-r03-original/AWG-R02 --output /tmp/awg-r03-f1-new --mode correctness
for awg_revision in before after; do
  for awg_fixture in two-routes asrep rbcd rbcd-padding-1000; do
    .venv/bin/python scripts/research/awg_r03_validation.py --repo "/tmp/awg-r03-$awg_revision" --evidence-root /tmp/awg-r03-original/AWG-R02 --output "/tmp/awg-r03-time-$awg_revision-$awg_fixture" --mode benchmark --fixture "$awg_fixture"
  done
done
for awg_revision in before after; do
  for awg_fixture in two-routes asrep rbcd rbcd-padding-1000; do
    .venv/bin/python scripts/research/awg_r03_validation.py --repo "/tmp/awg-r03-$awg_revision" --evidence-root /tmp/awg-r03-original/AWG-R02 --output "/tmp/awg-r03-profile-$awg_revision-$awg_fixture" --mode profile --fixture "$awg_fixture"
  done
done
```

Các loop benchmark/profile chạy tuần tự, sau khi test kết thúc.
Archive giữ các lệnh thực tế và bốn nhóm test rời nhau đã chạy; lệnh pytest ở trên là cách chạy toàn bộ collection tương đương trong một process.
Kết quả local không thay thế trạng thái CI remote hoặc human acceptance.
Nhánh implementation được chuẩn bị cho draft PR vào `develop`; không merge, không đóng các scope rộng hơn của #292/#293.
