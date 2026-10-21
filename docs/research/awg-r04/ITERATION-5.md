# Iteration 5 — tự tạo nguồn–đích và chạy đánh giá exposure

## Sản phẩm đã thay đổi gì

Trước đây discovery cần một request chứa danh sách nguồn và manifest mục tiêu viết sẵn. Nay `python -m scripts.exposure` đọc snapshot, tự lập inventory và sinh request cho planner hiện có. Người dùng có thể chọn một foothold hoặc đánh giá các kịch bản compromise độc lập của nhiều nguồn; không cần nhập trước ID của các đích.

Native implementation/capture được thực thi tại **`74166e7c7438153f2d882901426272ebb78e8a7b`**, preparation `bc7da0d86ddf6a88a594d1f38d5ccad7eeb6c78e`. CLI resume được bổ sung sau đó, giữ nguyên native source bytes; [machine evidence](evidence/iteration-5-exposure.json) pin cả code mới và từng capture. Không đổi search semantics, C/P/I basis, hay quyền mà foothold được cấp.

| Thành phần | Hành vi mới |
| --- | --- |
| Inventory nguồn | User/Computer trong domain đã chọn, không boundary, không known-disabled; nguồn có enabled chưa biết được ghi rõ. Mỗi nguồn là một giả thiết compromise riêng, không cộng capabilities giữa nguồn. |
| Important targets | Group có SID DA/EA, Computer có MemberOf tới group DC/RODC, hoặc Group có admincount=1. SID/edge/marker đều được lưu làm căn cứ; không nhận diện role bằng tên hiển thị. |
| All targets | Mọi Group/Computer không boundary trong domain đã chọn, kể cả ngoài important set. Không phải mọi loại tài sản hoặc business objective. |
| Impact | `Unknown` qua target-manifest/1.2.0; không ép gán High/Catastrophic để vượt schema. Legacy 1.0/1.1 và serialization cũ giữ nguyên. Source có witness nhưng impact chưa biết không bị xếp thành `None`/an toàn. |
| Kết quả | `overview.md` và `summary.json` dễ đọc; `result.json` giữ đủ query, assumptions, attempts, witnesses và guarantees. Phần ngoài cohort/chưa chạy được đếm riêng. |
| Remediation | Tự mine candidates rồi gọi executor, independent verifier và rediscovery hiện có trên một rectangular subcohort được công bố. Không coi witness frequency là effectiveness. |
| Checkpoint | Native default interval=1 giữ behavior cũ; exposure chọn 25, có final flush. Resume giữ request/source bindings và archive report cũ theo hash. |

DA/EA và DC/RODC RID dựa trên [Microsoft Security Identifiers](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-identifiers). `admincount` chỉ là marker chọn nơi cần kiểm tra, có thể stale; nó không chứng minh quyền hiện tại. Không suy business criticality từ marker, role hoặc tên máy. Mục tiêu Group vẫn yêu cầu **cùng identity** usable trong Computer context của nguồn và có entitlement; Computer vẫn yêu cầu admin_control, không chỉ đi tới node.

## Kết quả thực thi trên nguyên SEAMLESS

Đủ sáu raw hashes được kiểm lại. Snapshot giữ SHA-256 `73f4380f938bf70338661c487e3c6467c4b012be1519995f4419a1143a45a9a8`, 3.370 nodes / 56.367 edges. Inventory tự tìm **2.590 nguồn**, **649 all targets**, **12 important targets**; important product có **31.080 cặp ứng viên**. Đây là candidate universe, không phải số cặp đã tìm được attack path.

| Lượt đã hoàn tất | Kết quả | Giới hạn cần đọc cùng |
| --- | --- | --- |
| Một User × 12 auto important goals, scenario | 2 complete-success, 10 truncated-incomplete | Bốn assumptions được giữ từ pilot cũ, không phải observations. C/P chưa chấm; 100 expansions/4 steps/5 paths mỗi cell. |
| Cùng User × 12 goals, evidence-only | 12 indeterminate, không witness | Không biến thiếu runtime evidence thành no_path hoặc P=0. |
| Toàn important matrix, lượt đầu | 1.500 cell thực thi, 125 nguồn: 100 Computers + 25 Users | Hai techniques; các nguồn là hypothetical compromise profiles, không phải đồng thời bị chiếm. |
| Resume thật | Reuse 1.500, chạy thêm 100; tổng **1.600 cell / 134 nguồn** | **29.480 cell chưa chạy**. Prefix deterministic, không đại diện ngẫu nhiên cho domain. Report gốc đã archive và hash. |
| Một mined intervention trên 1 User × 1 DC-admin goal | Loại 3/3 chương trình quan sát; **0 cặp đã chứng minh disconnect**, after còn Unknown | 11 goals discovery khác không thuộc cohort can thiệp. Không kết luận rủi ro giảm 100% hoặc can thiệp vô hiệu 0%. |

Trong system evidence-only, 1/1.600 cell có witness là **DC admin_control đã được khai báo sẵn**, zero actions/C=0. Không phải một đường leo thang mới. 1.599 cell đã chạy còn indeterminate; 29.480 unrun được giữ riêng dù cùng dùng cell status indeterminate. Không có claim full-system completion, domain safe, global minimum hoặc all-catalog coverage.

[Ví dụ overview thật](evidence/iteration-5-one-source.md), [full intervention package](evidence/iteration-5-intervention.json), [scopes/hashes/timings/targets/omissions](evidence/iteration-5-exposure.json). Native captures lớn giữ local và pin trong evidence; compact projection không giả là full trace. Original packet/source revision giữ nguyên; khi thay code làm source pins khác, phải tạo fresh package, không relabel attestation.

## Chi phí checkpoint đã đo

Lượt per-cell system cũ được **chủ động ngắt exit130** sau 675 cacheable cells; checkpoint 14,90 MB được giữ nguyên, không có final result và không cộng vào số cell unique. Không resume nó dưới native source pins mới.

Sau đó đo tuần tự ABBA trên **cùng 20 sources × 12 goals = 240 cells**, cùng snapshot/request/native code/budgets, hai techniques, không wall deadline; chỉ đổi interval 1/25. Không chạy AWG benchmark/test khác cùng lúc.

| | Interval 1 | Interval 25 |
| --- | ---: | ---: |
| Hai pipeline trials, s | 48,846; 47,796 | 44,294; 41,961 |
| Median, s | 48,321 | 43,127 |
| Số lần ghi checkpoint/lượt | 241 | 10 |
| Logical checkpoint bytes/lượt | 949.767.430 | 44.074.731 |

Observed reduction khoảng **10,75%**, ratio 1,12× trong đúng cohort này. Cả bốn **full normalized decision dictionaries bằng nhau**; chỉ loại `reproducibility.runtime.elapsed_seconds` và `checkpoint_interval`, giữ source pins và mọi query/proof/coverage. [Exact harness](evidence/checkpoint-benchmark.txt), [machine measurement](evidence/iteration-5-checkpoint-benchmark.json).

Graph loading/preparation warmup và serialization kết quả so sánh ở ngoài timing. Hai trials/setting, không CPU affinity/host isolation, không suy ý nghĩa thống kê hoặc tỷ số mọi workload. Logical bytes không phải physical storage traffic. Với wall deadline, giảm overhead có thể làm thay đổi coverage thực thi; parity ở đây dùng cùng logical caps và không wall timeout.

Batch vẫn lặp từng source/goal. Checkpoint không phải toàn bộ bottleneck; phần thời gian còn lại chưa được tách bằng profile thành indexing/materialization/evaluation. Chưa có bằng chứng để gọi đây là shared search hay thay bằng AND–OR.

## Chạy hai use cases

Snapshot được dựng theo phần SEAMLESS trong README. Lệnh dưới dùng file snapshot đã có tại `data/processed/awg-r04/full/snapshot.json`; thí nghiệm thực tế dùng cùng dữ liệu tại `pilot-v2/snapshot.json`.

Một foothold, không nhập trước đích:

```bash
python -m scripts.exposure \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --source S-1-5-21-1271839998-3495686680-2211690266-2799 \
  --authentication-context S-1-5-21-1271839998-3495686680-2211690266-1000 \
  --user-profile user_usable_identity --evaluation-mode scenario \
  --assumptions docs/research/awg-r04/evidence/exposure-user-assumptions.json \
  --max-sources 0 --max-targets 0 \
  --technique propagate_group_entitlement --technique obtain_admin_execution_on_host \
  --remediate 1 --remediation-sources 1 --remediation-targets 1 \
  --output-dir reports/generated/exposure-one-user
```

Bỏ assumptions và dùng `--evaluation-mode evidence_only` để chạy đối chứng. `--target-scope all --inventory-only` xuất catalog 649 targets; không cần auth context khi chỉ inventory. `--target-scope all` không structural-prune các kỹ thuật phi cạnh, nhưng coverage còn phụ thuộc catalog và initial capability profile đã chọn.

Nhiều nguồn, nhiều đích tự sinh:

```bash
python -m scripts.exposure \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --authentication-context S-1-5-21-1271839998-3495686680-2211690266-1000 \
  --user-profile user_usable_identity --computer-profile computer_control_admin \
  --max-sources 0 --max-targets 0 --max-cells 1500 --global-max-expansions 150000 \
  --technique propagate_group_entitlement --technique obtain_admin_execution_on_host \
  --output-dir reports/generated/exposure-system
```

Chạy lại **chính lệnh đó**, thêm `--resume` và đổi `--max-cells` thành 100, sẽ chạy tối đa 100 cell mới sau cache hits. Giữ các input/logic parameters; request khác bị từ chối, native source/facts/scope pin checks vẫn giữ. Các output cũ được lưu ở `history/` theo hash và có archive index. Abrupt interruption có thể cần chạy lại tối đa N cacheable cells, kể cả flush bị ngắt; incomplete cells vốn không được cache như negative proof. Native worker wall deadline là tùy chọn và có chi phí reload graph mỗi worker.

## Kiểm chứng và việc còn lại

- **171 selected integration/legacy acceptance tests PASS** trên clean 74166e7; **16 binding/reuse checks PASS**. Resume extension: **69 checks PASS**, gồm current exposure tests, native runner và executable CLI. Các suites overlap, không cộng thành whole-suite total.
- Independent finite expectations kiểm SID/label spoof, source isolation, Computer không tự có domain identity, observed-False veto, Unknown/unrun/caps, full checkpoint equality, interruption/resume và scope refusal. Mined counterfactual có cả bypass (program cut nhưng pair không disconnect) và actual finite disconnection.
- Native Week4 v7: **36 PASS / 2 NOT EXECUTED / 0 FAIL**, hai lần deterministic, compact/full semantic equality và frozen v3 equality sau existing environment normalization. V5/V6/oracles cũ không đổi. [Selected JUnit](evidence/iteration-5-selected.xml), [binding JUnit](evidence/iteration-5-binding.xml), [resume JUnit](evidence/iteration-5-resume.xml).
- Final Ruff check/format (569 Python files), contract check và ba source/history pin checks đều pass. Repository link check còn đúng historical R03 archive không materialize được; không tạo archive giả để làm xanh.
- Raw vẫn chỉ có một host với nonempty LocalAdmins và không Sessions. Fresh BloodHound comparator, FCP/HasSession typed composition, đủ numeric acceptance và C-only portability không được giải quyết bằng inventory.

**P0 tiếp theo:** nối optional scenario-policy compiler hiện có vào workflow, giữ observed-False/forbidden-predicate gates, để không cần viết assumptions JSON cho từng cohort. Hiện CLI hỗ trợ explicit JSON, chưa tự compile profile chuẩn. Không dùng blanket True để làm coverage đẹp.

**P1:** profile repeated static preparation/candidate indexing trên batch trước khi thử shared grounding; bổ sung capability profiles/coverage cho catalog rộng hơn, C-only applicability cho acquired goals và fresh BloodHound comparator. Full native JSON vẫn lớn (system capture đầu khoảng 122 MB); overview nhỏ giải quyết việc đọc, chưa tối ưu full audit transport.

**Quyết định:** giữ planner và mở rộng workflow có kiểm chứng. Hai use cases đã có entry point tự tạo input/goal inventory và counterfactual; nghiệm thu toàn domain/all-catalog vẫn còn giới hạn cụ thể nêu trên. Không xây thêm production engine chỉ để thay tên thuật toán.
