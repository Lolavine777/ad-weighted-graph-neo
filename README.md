# AD Weighted Graph

**Với một User hoặc Computer đã bị chiếm, tài sản nào bị phơi nhiễm, đi tới đó bằng cách nào và can thiệp nào thực sự giảm exposure?**

AWG dựng graph có provenance từ snapshot AD, sinh chương trình tấn công có điều kiện, đánh giá effort theo work units và kiểm chứng remediation bằng replay cùng tìm kiếm lại. [Đề bài gốc](docs/00_todo.md).

Core AWG-R04 được phát hành từ [PR #298](https://github.com/nairyuuu/ad-weighted-graph/pull/298), với local validation được lưu khi CI không khả dụng. [Checkpoint](docs/research/awg-r04/CONTINUE.md) ghi revision và phạm vi đã kiểm chứng; các báo cáo tuần cũ giữ nguyên theo mốc thực hiện.

Tải ZIP hoặc dùng dữ liệu riêng: xem [cài đặt, snapshot và parser trên Windows/Linux](docs/setup-from-zip.md). Gói core chạy bằng CLI; giao diện tương tác được phát triển riêng tại [PR #279](https://github.com/nairyuuu/ad-weighted-graph/pull/279).

[Demo local và lệnh tái lập](docs/research/awg-r04/DEMO.md) gồm một foothold→auto goals và hai compromise độc lập→mined intervention→replay/rediscovery.
[Fresh BloodHound CE 9.8.0 đã chạy bằng Docker](docs/research/awg-r04/ITERATION-18.md): raw được chuyển schema riêng có kiểm bảo toàn, CE/Cypher và raw oracle cùng cho 4→3 direct routes mỗi nguồn khi loại OLLIE→DA, cả hai vẫn reachable.

[Phép đo counterfactual mới](docs/research/awg-r04/ITERATION-4.md): trên cùng full-SEAMLESS snapshot và một declared source–goal, median 155,90 → 62,09s, giữ decision-package parity; không phải cam kết tăng tốc mọi truy vấn hay domain-wide risk reduction.

## Chạy thử

Cần Python **3.14.x**. Từ thư mục repository:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-tests.txt
```

Trên Bash, chạy `source .venv/bin/activate` trước các lệnh `python` bên dưới. Trên Windows, thay `python` bằng `.venv\Scripts\python.exe`.

### Query có effort và witness

```sh
python -m src.engine query \
  --query tests/fixtures/query_cli/two-routes-query.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json \
  --ranking-query docs/research/ratings/week4/synthetic-a2-e.json \
  --label synthetic --output reports/generated/demo-query.json
```

Fixture có đường trực tiếp và đường qua group; lượt mới tái hiện `minimum_effort_value=2`. Model synthetic này có giá khai báo, không phải thời gian khai thác AD. Dijkstra với đúng cost cộng được cũng chọn được đường rẻ; stateful search cần thiết khi prerequisites/cost không còn edge-local.

Thêm `--compact-output` cho native query CLI để bỏ whitespace và giữ đủ audit/semantic digest. [Đối chứng mới](docs/research/awg-r04/ITERATION-8.md) trên một full-SEAMLESS C-rated query: median10,04→9,56s ở format mặc định, compact9,08s; output90,49→59,80MB, peak RSS giảm~13%. Chín trials giữ nguyên toàn semantic/package sau explicit physical-metadata normalization; đây là một workload, không phải speedup mọi query hoặc thay đổi search coverage.

[Batch nhiều đích đã đo](docs/research/awg-r04/ITERATION-9.md):1User×3auto goals, shared-wire median35,44→33,18s trong6trials. Thí nghiệm writer riêng giảm~16,7%peak RAM, thời gian gần như bằng nhau; giữ full decisions/checkpoint/Unknown, không đổi output format. Một C1success và hai truncated goals không chứng minh full-system safety hoặc minimum.

### Một foothold → các đích quan trọng

```sh
python -m src.engine batch \
  --batch-request tests/fixtures/batch_contracts/batch_request_example.json \
  --graph tests/fixtures/attack_scenarios/graphs/two-routes.json \
  --source src-alice-usable --discover --label synthetic \
  --output reports/generated/one-source.json
```

`--source` chọn đúng một `source_id` đã khai báo, giữ profile, auth context, assumptions, budgets và rating scope. `--goal GOAL_ID` dùng để drilldown; bỏ `--source` để chạy cả ma trận. Discovery thông thường không yêu cầu ordered paths hoặc action mappings viết tay.

### Tự đề xuất rồi kiểm chứng remediation

```sh
python -m scripts.research.remediation_runner \
  --finite --fix direct-admin --discover-interventions 6 \
  --output-dir reports/generated/remediation-demo
```

Runner lấy đề xuất từ quyền/prerequisites của witness, chạy counterfactual và tìm đường thay thế. Đọc `table.md`, `summary.json`, `study.json`. Trong fixture này, bỏ quyền trực tiếp loại **50% programs nhưng ngắt 0% source–goal pairs** vì còn đường qua group. Coverage chỉ sắp thứ tự thử; hiệu quả đến từ replay/rediscovery. Không chứng minh can thiệp tối ưu hay tự suy chi phí vận hành defender.

## Một foothold: đọc đường đi và C thay vì audit JSON lớn

`python -m scripts.exposure` nay sinh **defender-brief.md/json**: tự chọn đích kỹ thuật, trình bày ai thực hiện từng bước, authentication context, C theo work units, assumptions và quyền cần kiểm tra. [Mở kết quả full-SEAMLESS đã chạy](docs/research/awg-r04/examples/defender-brief.md) · [Lệnh demo và giới hạn](docs/research/awg-r04/ITERATION-13.md).

Opt-in `--effort-profile reset-activation-c-v2` dùng rubric reset/activation cũ cho direct effective User/Computer principal rights; Computer cần machine identity usable được khai báo đúng context. Case FINWVIR→DENA→DA hiện có C tìm thấy1, bảy runtime assumptions;11đích còn truncated/incomplete. Không thêm đường, P/I hoặc claim global minimum. V1 giữ nguyên; full audit vẫn được lưu.

## Dùng scenario để có câu trả lời thực dụng

Chọn `--scenario-policy seamless-standard-v1` để áp dụng giả định toàn cục; CLI tự chọn scenario mode. Các điều kiện đã được profile chấp nhận có hiệu lực trong tìm đường, không tiếp tục bị coi là thiếu observation. [Lỗi đã sửa và execution evidence](docs/research/awg-r04/ITERATION-14.md): trên cùng12queries full-SEAMLESS, indeterminate transitions giảm99,883%→0,067%.

Dùng **C-first/Top-K** làm khuyến nghị đường đi; P overlap hoặc chưa chấm không ngăn chọn đường có C. Pareto là đối chiếu bổ sung. Khi global assumptions mở nhiều nhánh, FIFO có thể hết budget. Nay có opt-in **`--search-order goal_guided`** trong query/exposure CLI: giữ semantic planner, ưu tiên witness tới group trong catalog reset/activation/membership; goal/catalog khác ghi rõ FIFO fallback. [Đối chứng full-SEAMLESS và lệnh demo](docs/research/awg-r04/ITERATION-15.md): cùng2nguồn×3đích/caps, FIFO0witness và guided2DA witnesses C1; một Computer×12auto goals có4witnesses C1/8truncated. Không có global-minimum hoặc speedup claim.

`discovery-progress.jsonl` trả witness/C sau mỗi goal trước khi chờ toàn batch/audit; cuối lượt đọc [brief chạy thật](docs/research/awg-r04/examples/guided-defender-brief.md). Đây là per-goal search, chưa shared traversal; group DOMAIN CONTROLLERS entitlement không đồng nghĩa điều khiển DC host.

## Can thiệp có thực sự giảm exposure?

[Phép thử full-SEAMLESS mới](docs/research/awg-r04/ITERATION-16.md): inventory chọn bỏ OLLIE_LONG khỏi DA. Replay cắt **2/2 programs cũ**, nhưng rediscovery tìm **hai đường khác qua DENA**, cả hai nguồn vẫn tới DA với C tìm thấy1. [Brief thực thi](docs/research/awg-r04/examples/remediation-defender-brief.md) nay ghi rõ edit có labels, reachable trước→sau, cặp ngắt và đường mới; không suy giảm reachability từ tỷ lệ cắt đường mẫu.

## Bảo vệ cách tiếp cận bằng đối chứng

[Ba phép thử native](docs/research/awg-r04/ITERATION-17.md): hop/BFS chọn directC5, Dijkstra và AWG đầy đủ cùng chọn groupC2; native max_paths1 trảC5 với minimumFalse.
Graph đã condition và native cùng chặn authenticationFalse.
Fresh CE đã được đối chiếu trong [iteration18](docs/research/awg-r04/ITERATION-18.md), riêng với historical Legacy/import parity.
Trong cohort direct/additive đã condition, weighted graph đơn giản cũng đủ; chưa có global-minimum trên full graph dưới caps hoặc bằng chứng AWG vượt CE về performance.

## Toàn bộ SEAMLESS public

```sh
python -m scripts.download_seamless
python -m scripts.research.run_source_goal_batch_pilot \
  --raw-dir data/raw/SEAMLESS \
  --target-manifest configs/targets/seamless-v2.json \
  --output-dir data/processed/awg-r04/full \
  --sanitized-report reports/generated/awg-r04-pilot.json
```

Downloader pin commit của [Bloodhound_Data](https://github.com/mike-nolan-councilman/Bloodhound_Data/tree/3febc4089421725f9527c187f78d064ad09d5158), kiểm SHA-256 archive và cả sáu file theo [manifest](data/samples/manifests/seamless-raw-v1.json). Có thể dùng `--archive PATH.zip` để cài offline. Directory có dữ liệu khác manifest bị từ chối ghi đè.

Lượt mới dựng **3.370 nodes, 56.367 edges** từ toàn snapshot. Pilot chạy năm source profiles độc lập × ba đích DA/EA/DC, riêng scenario và evidence-only. Scope là bốn techniques và caps được công bố, không phải full-source scan hay toàn catalog. Pilot cố ý không nạp numeric registries: C thiếu giữ `null`, P giữ `unrated`.

HasSession là cơ hội thu material, không tự cấp password hoặc danh tính. Khi material chưa rõ loại đã reachable nhưng mục tiêu cần usable identity, query trả `unsupported` (batch `unsupported_semantics`, result1.1); Unknown và truncated giữ riêng. Không dùng ca đó làm bằng chứng no-path hoặc disconnect. [Hai ví dụ chạy lại](docs/research/awg-r04/ITERATION-12.md) tách material và password được khai báo đúng owner/context; SEAMLESS hiện có0Sessions.

[Independent raw audit](docs/research/awg-r04/evidence/iteration-4-direct-raw.json) đối chiếu 46.109 direct edges với raw fields và provenance, không dùng AWG parser làm oracle; scope/exclusions và exact harness có trong [báo cáo](docs/research/awg-r04/ITERATION-4.md). Raw này có 100 máy nhưng chỉ một máy có LocalAdmins không rỗng, không có Sessions. “Full SEAMLESS” không chứng minh coverage lateral movement/session của doanh nghiệp.

Drilldown một User trong request vừa sinh:

```sh
python -m src.engine batch \
  --batch-request data/processed/awg-r04/full/request.json \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --prerequisite data/samples/manifests/seamless-raw-v1.json \
  --label seamless --source user-identity --discover \
  --technique activate_recovered_identity \
  --technique propagate_group_entitlement \
  --technique obtain_admin_execution_on_host \
  --technique scenario_winrm_admin \
  --output reports/generated/seamless-one-user.json
```

Đổi foothold bằng source/profile/capabilities trong request. `control(Computer)` không cấp sẵn usable domain identity. DA/EA entitlement và admin trên DC là goals khác nhau. SEAMLESS là public lab snapshot; kết quả còn phụ thuộc assumptions đã khai báo.

[Computer boundary đã kiểm chứng](docs/research/awg-r04/ITERATION-10.md): local shell không được dùng ACL của machine principal khi chưa có `usable_identity` đúng context. Fullraw regression giữ witness Computer→reset DENA→activate→DA khi khai báo machine identity riêng; C/P/I unrated và path-limit truncated. Profile hiện gộp local admin/SYSTEM nên vẫn cần declaration identity tường minh; đây không phải khẳng định SYSTEM không có machine credentials.

Hai exact public inputs để đối chứng: [machine identity](docs/research/awg-r04/examples/computer-explicit_machine_identity.json) và [local shell](docs/research/awg-r04/examples/computer-local_shell.json). Ví dụ sau khi dựng snapshot ở trên:

```sh
python -m src.engine query \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --query docs/research/awg-r04/examples/computer-explicit_machine_identity.json \
  --prerequisite data/samples/manifests/seamless-raw-v1.json \
  --label seamless --compact-output \
  --output reports/generated/computer-identity-query.json
```

Thay query bằng local-shell control sẽ bị chặn trong scope ba techniques này. HasSession hiện chưa nối untyped material thành identity; `no_path` trong model chưa phải chứng minh host an toàn.

Discovery/batch nay có profile **`computer_usable_identity`** để khai báo network identity của tài khoản máy, có context và provenance riêng. Profile này không cấp local shell/admin hoặc danh tính User. Request mới dùng1.1; request/profile cũ giữ1.0. Đây là giả thiết đầu vào có nguồn khai báo, không phải bằng chứng snapshot đã xác minh authentication.

```sh
python -m scripts.exposure \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --source S-1-5-21-1271839998-3495686680-2211690266-4157 \
  --authentication-context S-1-5-21-1271839998-3495686680-2211690266-4157 \
  --computer-profile computer_usable_identity \
  --machine-identity-provenance scenario://awg-r04/machine-identity/FINWVIR-4157 \
  --evaluation-mode scenario \
  --assumptions docs/research/awg-r04/examples/machine-identity-assumptions.json \
  --technique scenario_reset_password --technique acquire_reset_identity \
  --technique propagate_group_entitlement \
  --max-sources 0 --max-targets 3 --max-paths 1 --max-steps 3 \
  --max-expansions 10000 --global-max-expansions 30000 --max-cells 3 \
  --output-dir reports/generated/exposure-machine-identity
```

[Fullraw run](docs/research/awg-r04/ITERATION-11.md) tự chọn DC/DA/EA: một conditional witness tới DA, hai goals truncated/incomplete; C/P/I chưa chấm và không có minimum proof. Bỏ `--machine-identity-provenance` và đổi profile thành `computer_control_user` để đối chứng local shell bị chặn trong cùng scope. Context/provenance không hợp lệ bị từ chối; thay provenance không reuse checkpoint cũ.

Manifest v2 yêu cầu **cùng một danh tính dùng được trong auth context của query** có membership DA/EA; danh tính đó có thể được lấy trong chuỗi tấn công. Goal `usable_identity_entitlement` không cấp ngầm credential. Goal actor-specific và manifest v1 vẫn dùng được cho đối chiếu lịch sử. Impact rating của goal cũ không tự chuyển sang goal mới; thiếu reviewed binding giữ unrated/refused rõ ràng.

### Discovery tự tạo nguồn và đích

Không cần viết target manifest hoặc danh sách đường đi. CLI mới nhận snapshot, tự tìm các đích theo role SID, DC membership và Group admincount marker. `--target-scope all` mở rộng tới mọi Group/Computer không boundary. Marker chỉ chọn nơi cần kiểm tra; business impact giữ `Unknown` qua target-manifest/1.2.0.

```sh
python -m scripts.exposure \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --source S-1-5-21-1271839998-3495686680-2211690266-2799 \
  --authentication-context S-1-5-21-1271839998-3495686680-2211690266-1000 \
  --user-profile user_usable_identity --max-sources 0 --max-targets 0 \
  --technique propagate_group_entitlement --technique obtain_admin_execution_on_host \
  --output-dir reports/generated/exposure-one-user
```

Mặc định evidence-only. Đọc `overview.md`, `summary.json`; `result.json` giữ full audit. Thêm `--evaluation-mode scenario --scenario-policy seamless-standard-v1` để dùng profile snapshot-bound có sẵn, không cần tự viết assumptions JSON. Mỗi query giữ assumptions/rejections/provenance; evidence False vẫn chặn giả định True. `--assumptions PATH.json` vẫn dùng được cho declarations cụ thể, standard policy từ chối forbidden predicates hoặc contradictions. C thiếu basis giữ unrated, không lấy hop count làm cost. User profile/context là giả thiết compromise được khai báo; Computer control không cấp ngầm domain identity.

[Đối chứng profile trên nguyên SEAMLESS](docs/research/awg-r04/ITERATION-6.md): một User ×12 auto goals, evidence-only không witness; standard tìm 3 conditional witnesses, cả ba truncated. User đó vốn có membership DA, không chứng minh ordinary-user escalation. Cohort 2 User+1 Computer đã chạy 36 cells; một intervention cut 80% observed programs nhưng không chứng minh disconnect và vẫn có bypass. Profile không phải observation hoặc P=1.

Opt-in `--effort-profile reset-activation-c-v1` dùng native resolver để chấm **C-only** cho direct User-owned GenericAll reset và activation cùng owner/context. Đây là applicability mới của rubric ordinal cũ, được chọn tường minh; P/I không được chuyển sang. Các source/goal/work khác vẫn search và giữ unrated. Không dùng chung với `--rating-resolution`.

```sh
python -m scripts.research.identity_effort_pilot \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --raw-dir data/raw/SEAMLESS \
  --output-dir reports/generated/identity-effort-demo
```

Helper tự chọn User chưa có DA membership, khai báo runtime assumptions, chạy trước/sau C, batch và exact public-query CLI. Trên full snapshot, OLA_CARSON → reset DENA → activation → DA entitlement có **C=1**, hai work units (1+0), P/I unrated. OLA có ACL mạnh/usable identity khai báo, không phải ordinary low-privilege user. **Native minimum proof vẫn false**: best found. [Kết quả và independent oracle](docs/research/awg-r04/ITERATION-7.md). Auto hai goals cũng đã chạy: một C-rated success, một truncated/unrated; mục tiêu chưa kết luận không được coi an toàn.

Bỏ `--source` để tạo các nguồn tự động; `--max-sources 0 --max-targets 0` chọn cả inventory. Dùng `--max-cells`/`--global-max-expansions` để giới hạn thực thi; phần không chọn/chưa chạy được đếm riêng. Chạy lại cùng lệnh với `--resume` để chạy thêm cell sau cache hits; report cũ được archive theo hash, request/source mismatch bị từ chối. Thêm `--remediate N` để thử mined interventions trên subcohort có `--remediation-sources`/`--remediation-targets` riêng.

Full SEAMLESS đã tự nhận diện 2.590 nguồn, 649 all targets/12 important targets. Important matrix có 31.080 cặp; **đã thực thi 1.600**, còn 29.480 chưa chạy. Chưa gọi full-system nghiệm thu hoặc shared traversal: planner vẫn chạy riêng mỗi goal. [Kết quả, commands và giới hạn](docs/research/awg-r04/ITERATION-5.md).

Tái hiện khác biệt goal trên nguyên full snapshot, với runtime gates được khai báo rõ:

```sh
python -m scripts.research.compare_identity_goals \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --output-dir data/processed/awg-r04/identity-goal-comparison
```

Lượt đã chạy tìm được chương trình ba bước qua User khác có DA. Old actor-specific run bị cắt tại budget; kết quả đó không chứng minh unreachable. Đây là so sánh cách diễn giải mục tiêu, không phải benchmark tốc độ giữa hai thuật toán.

Remediation trên cùng raw snapshot:

```sh
python -m scripts.research.remediation_runner \
  --seamless-raw-dir data/raw/SEAMLESS --discover-interventions 6 \
  --checkpoint-dir data/processed/awg-r04/remediation-checkpoints \
  --output-dir data/processed/awg-r04/remediation
```

Lượt đã chạy mất khoảng **327 giây**, kiểm raw trước/sau: bốn controls và ba mined candidates trên cohort AS-REP có giới hạn. Không phải remediation tối ưu cho cả domain. Unknown, truncation và bypass được giữ trong report.

## Đọc kết quả và giới hạn

| Thành phần | Ý nghĩa |
| --- | --- |
| Structural BFS/Dijkstra | Đường trên projection cố định. Dijkstra tối ưu với cost cộng được, không âm; không tự chứng minh prerequisites. |
| Semantic planner | Kiểm capability, actor/context, AND prerequisites và artifacts bằng evaluator hiện có; search có budget. |
| C / Min-Effort | Union work units trong model/basis được cung cấp. Có thể dùng C khi P/I chưa rated. |
| P | Conditional model/estimate theo scope và lịch sử; không mặc định là xác suất thực nghiệm đã calibrate. Không lấy midpoint phá tie. |
| Impact | Consequence của goal, tách khỏi reachability và cost. |
| Remediation | Replay cùng rediscovery trên counterfactual; program elimination tách khỏi source–goal disconnection. |

`truncated` không có nghĩa unreachable. `complete` một mình chưa chứng minh an toàn khi còn Unknown hoặc kỹ thuật ngoài model. Đọc proof flags cùng scope, facts, rating coverage và budgets. ForceChangePassword → usable identity và HasSession → typed password còn khoảng trống composition; không tự cấp credential để nối đường.

Hướng hiện tại: giữ native planner, tối ưu reuse trước. Đo tuần tự một User × ba goals trên SEAMLESS giảm median warm **5,80 → 0,51 giây**, giữ exact trace parity; setup và toàn remediation không nằm trong tỷ số này. Chưa đủ bằng chứng để thay bằng AND–OR engine production. [F1 độc lập](docs/research/awg-r03/AWG-R02_Bao_cao_thuc_nghiem.md) chỉ ra nơi conditional graph đủ và nơi cần AND/state.

AWG bổ sung cost/evidence/counterfactual cho câu hỏi defender. Fresh CE đã được đối chiếu trên cùng raw và direct DA cohort ở iteration18; chưa có bằng chứng vượt BloodHound về coverage, UI hoặc performance. Không suy đoán approach của mentor.

## Kiểm tra local

```sh
python -m ruff check .
python -m ruff format --check .
python -m yamllint .
python scripts/check_repository.py
python scripts/check_contract.py
python -m pytest
```

| Cần làm | Tài liệu |
| --- | --- |
| Parser, manifest và collection-time policy | [Môi trường](docs/02_environment.md), [snapshot manifest](docs/snapshot-manifest.md) |
| Query, Min-Effort và proof scope | [Query CLI](docs/research/week4-query-cli.md), [Min-Effort](docs/research/week4-min-effort-search.md) |
| Batch, profiles, resume | [Batch runner](docs/research/week5-source-goal-batch-runner.md) |
| Remediation, bypass và audit package | [Runner guide](docs/research/remediation/runner-guide.md) |
| Probe action, assumptions, structural fallback | [Guided exploration](docs/guided-exploration.md) |
| Tiếp tục từ đúng state | [AWG-R04 checkpoint](docs/research/awg-r04/CONTINUE.md) |

`src/parser/` giữ normalization/lineage; `src/engine/` giữ graph, semantics, search, ranking, remediation; `configs/` giữ contracts/catalog. Raw và outputs lớn nằm trong directory gitignored. Numeric/source manifests lịch sử được bảo toàn; thay code cần kiểm tra attestation và compatibility tương ứng.
