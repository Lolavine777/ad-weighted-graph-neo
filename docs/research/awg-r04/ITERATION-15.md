# MVP: từ foothold tự tìm đích, trả witness và C sớm

**Đã đưa ưu tiên tìm witness theo mục tiêu vào planner thật, có opt-in và kết quả full-SEAMLESS.** Giữ planner/evaluator/C hiện có; chưa có bằng chứng cần xây production AND–OR. [Kết quả đọc được](examples/guided-defender-brief.md) · [JSON/provenance](examples/guided-defender-brief.json) · [execution evidence](evidence/iteration-15-guided.json).

## Đã thay đổi gì

- Query và exposure CLI nhận `--search-order goal_guided`. FIFO vẫn mặc định. Trong catalog reset → activation → group entitlement, queue ưu tiên state chứa identity gần group đích theo reverse observed MemberOf, rồi identity đã dùng được. Không hardcode owner/đường, không loại state/candidate hoặc thay prerequisites/giá C.
- Goal/catalog khác dùng FIFO và ghi rõ effective strategy/fallback. Đích host-control không được diễn giải lại thành group entitlement. Đây là heuristic tìm witness, không phải A* với lower bound chi phí.
- Batch phát `discovery-progress.jsonl` và dòng trạng thái stderr sau mỗi cặp source–goal, trước khi hoàn thành toàn ma trận/serialize audit lớn. Event có witness thực, C, expansions và proof flag. Không phải streaming từng transition hoặc shared traversal. Với max_paths=1, query dừng ở witness đầu rồi tiếp tục goal sau.
- Search order nằm trong query/cell/checkpoint/replay scope; đổi order không được dùng nhầm checkpoint cũ. Callback chỉ nhận bản sao gọn, không sửa native trace. Resume bị từ chối không xóa journal đã có. Định dạng FIFO cũ được giữ.

## Đã chạy trên dữ liệu thật

Sáu raw public SEAMLESS đã kiểm manifest, upstream `3febc4089421725f9527c187f78d064ad09d5158`. Snapshot **3.370 nodes / 56.367 edges**, ID `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`. Code/captures sạch `29e52c4c3939b278537a53b61fc021cc65829b9d`.

Hai nguồn độc lập: machine identity FINWVIR1000001 và User OLA_CARSON, usable tại context FINWVIR. Đây là các nguồn có ACL mạnh; không đại diện máy bất kỳ. Không hợp nhất capabilities của hai compromises. Standard scenario profile `seamless-standard-v1`, C-only `reset-activation-c-v2`, ba techniques reset/activation/membership; **không dùng bảy runtime facts viết tay của iteration13**, không chỉ định owner trung gian, target IDs hoặc đường.

| Workload | FIFO | Goal-guided |
| --- | ---: | ---: |
| Cùng 2 nguồn × 3 đích tự inventory (DC/DA/EA) | 6 cặp | 6 cặp |
| Cặp có witness / có C | 0 / 0 | **2 / 2**, đều tới DA, C=1 |
| Chưa có witness, hết budget | 6 | 4 |
| Tổng expansions | 36.000 | 33.990 |
| Native batch + audit, một lần | 63,96s | 72,58s |
| Native replay witness | không có witness | **2 PASS** |

Cùng revision, byte-identical request, toàn bộ 70 source pins, initial states, assumptions, caps1path/3steps/6.000exp mỗi query. Cả sáu public queries bằng nhau sau khi chỉ bỏ requested order và scenario/rating binding đã kiểm riêng. **Có lợi về witness trong cùng budget; không có speedup claim**: chỉ một timing mỗi mode, guided còn thực hiện rating/audit cho witness. First witness được journal ở31,14s, trước full-result serialization.

Một Computer × **cả12đích quan trọng tự inventory**, cùng profile/caps: **4witness/C-rated, 8truncated-incomplete**, 67.989exp; native batch/audit132,66s. First witness ở30,35s. Cả bốn C=1 và native replay PASS:

- DOMAIN ADMINS;
- ADMINISTRATORS;
- DOMAIN CONTROLLERS;
- READ-ONLY DOMAIN CONTROLLERS.

Hai mục cuối là **entitlement của group**, không chứng minh điều khiển host/DC. Các positive cũng truncated vì max_paths=1: C là **best found**, tất cả minimum/no-path proof flags đều False. P/I không chấm mới. Có15cặp phân biệt trong hai cohorts, vì ba cặp Computer ở bảng đối chứng trùng cohort12; không cộng thành18cặp coverage.

Full audit lossless được giữ local gzip: FIFO578.154.011bytes, guided2×3 693.596.375bytes, guided1×12 1.304.550.209bytes trước nén. Kiểm độc lập gzip CRC, toàn byte-count/SHA-256 và70source pins so Git objects/current bytes. [Harness chính xác](evidence/run_guided_product.txt) và evidence giữ request, per-goal/query/state digests, events, actual action requests, native replay và independent reset-work count. Brief/journal nhỏ được publish; không bỏ audit để tạo số đẹp.

## Lệnh demo tối thiểu

Sau bước tải raw/dựng snapshot theo [README](../../../README.md), chạy tại repository root, đổi snapshot path nếu cần:

```sh
AWG_FOOTHOLD=S-1-5-21-1271839998-3495686680-2211690266-4157
python -m scripts.exposure \
  --snapshot data/processed/awg-r04/pilot-v2/snapshot.json \
  --source "$AWG_FOOTHOLD" --authentication-context "$AWG_FOOTHOLD" \
  --computer-profile computer_usable_identity \
  --machine-identity-provenance scenario://awg-r04/machine-identity/FINWVIR-4157 \
  --scenario-policy seamless-standard-v1 --effort-profile reset-activation-c-v2 \
  --search-order goal_guided \
  --technique scenario_reset_password --technique acquire_reset_identity \
  --technique propagate_group_entitlement \
  --max-sources 0 --max-targets 0 --max-paths 1 --max-steps 3 \
  --max-expansions 6000 --max-cells 12 --global-max-expansions 72000 \
  --output-dir reports/generated/demo-guided
```

Đọc `discovery-progress.jsonl` khi đang chạy, rồi `defender-brief.md` khi hoàn tất. Với User, chọn đúng User source và `--user-profile user_usable_identity`, giữ context khai báo. Có thể giới hạn max-targets để demo nhanh. Assumptions là đầu vào hợp lệ; chúng có provenance và không ghi đè observed False hoặc tự tạo quyền. C=1 là rubric ordinal một reset work unit, activation0, không phải một phút hoặc xác suất thành công1.

## Kiểm đúng và compatibility

23checks mới PASS: exhausted finite full-program-set parity với FIFO, hai owner/alternative routes/actor switching, shared reset-work oracle C={1,2}; cap1/truncated không nhận minimum. Thêm11identity/context/False/Unknown controls, invalid order, fallback, worker/resume/checkpoint, replay scope và executable exposure CLI/journal. Control callback sửa event không làm đổi native trace. Không nhân đôi semantic rule system.

Nghiệm thu native phát hiện `search_order=fifo` lọt vào evidence cũ qua dataclass fields, dù outcome không đổi. Sửa **reporter** để bỏ đúng inactive default, không đổi expected outcomes/frozen oracle. Lượt trước giữ local; clean reporter capture `829965b34e4e75ffc5ff927d8839edcd042b120b` chạy hai lần **36PASS/2NOT_EXECUTED/0FAIL**, frozen semantic digest `e4f9a3f1779753650a45dbf4c671c8cf68363e100c4a9bc861850a0cb2cbbbec` giữ nguyên. Append [acceptancev16](../../../reports/research/week4-guided-exploration-acceptance-manifest-v16.json), giữv15 và toàn history/numeric/catalog. Strict source authorities14 cập nhật source pins, không thay số hoặc coi scope mới là calibration. **Final clean `a846394dea000d54b66a1a9616373eef00a7cb99`: 593/593 selected checks PASS trong164,74s, zero skip**, gồm23checks mới; không cộng với81/23lượt trước hoặc gọi whole-suite. [Closeout/JUnit](evidence/iteration-15-closeout.json) ghi các module và dependencies. Cả70native sourcepins và127v16pins bằng current bytes; strictauthority14PASS, v15/historical numeric+catalog giữbytes. Ruffcheck/format, contract2fixturesPASS; repository-links chỉ thiếu historical R03ZIP đã biết. Mọi jobs/captures/replays complete; finaldescendant chỉdocs/evidence, khôngsourcechange.

## Đối chiếu đề bài: đã đủ gì, còn gì thực sự quan trọng

| Yêu cầu gốc | Trạng thái MVP | Phần chưa chứng minh |
| --- | --- | --- |
| Raw AD → graph, taxonomy, provenance | Có pipeline, full raw manifest và independent direct-edge audit các iteration trước | Coverage toàn kỹ thuật/mọi loại derived edge |
| Máy/User bị chiếm → tới đâu, theo đường nào | Có workflow auto-inventory, witness, actor/context, brief; lần này có4/12goals trong scenario | Nguồn/catalog rộng; host-control ngoài catalog này |
| Trọng số và chi phí thấp nhất | C-first, union work units; finite oracles/minimum khi search thực sự đầy đủ | **Chưa đảm bảo minimum từ node bất kỳ trên full graph dưới caps** |
| Choke point và khuyến nghị | Có mined candidates + counterfactual replay/rediscovery, report cut-programs riêng reachability | Chưa có full-domain/cost-constrained optimum hoặc đo can thiệp mới trong iteration này |
| So với BloodHound/alternative | Có topology/semantic controls, historical baseline và matched FIFO đối chứng mới | Fresh BloodHound CE cùng snapshot và workload/caps chưa hoàn tất |
| Demo/README/báo cáo tái lập | CLI, exact harness, brief/progress, raw/source hashes và báo cáo này | Chưa gọi toàn đề bài nghiệm thu xong |

**Verified:** cách tiếp cận hiện có đã cho câu trả lời hữu ích hơn sau một đổi queue nhỏ, không cần engine mới. **Strong inference:** giữ planner và tối ưu phần đo được có tỷ lệ giá trị/chi phí tốt hơn rewrite AND–OR lúc quota thấp. **Hypothesis requiring experiment:** heuristic có ích với nguồn/catalog rộng; benchmark hiện chỉ có ba techniques và nguồn ACL mạnh.

Hop/BFS phù hợp câu hỏi topology; Dijkstra phù hợp edge costs cộng được, cùng projection/cost phải cho cùng optimum. Không nên so raw-edge shortest path với semantic program rồi quy khác biệt thành chất lượng thuật toán: identity switching, nhiều prerequisites và shared-work union cần state/conditioning hoặc mô hình tương đương. Queue mới không giải bài toán minimum tốt hơn Dijkstra; nó tìm witness sớm hơn FIFO trong caps đã đo. Chưa có fresh full-state Dijkstra timing hoặc lợi ích AND–OR đủ để biện hộ overhaul. Không biết approach mentor nên không gán quan điểm cho mentor.

## Chốt phạm vi khi quota ít

**P0 đã làm:** giao opt-in + progress + fullraw comparison + demo đọc được + checkpoint, chạy hồi quy. MVP có giá trị là trả được “đích nào, đường nào, C bao nhiêu, quyền nào cần xem” trong scenario công bố. Không cần P được hiệu chuẩn để demo này dùng được.

**P0 tiếp theo nếu chỉ còn một lượt:** chọn một witness/candidate remediation có sẵn, chạy replay **và rediscovery alternative routes** trên cùng declared source–goals, xuất bảng còn reachable/chưa kết luận; kèm một bảng topology/hop/weighted baseline cùng dữ liệu cho bảo vệ. Dừng khi đủ minh họa một quyết định defender; không quét hết31.080pairs chỉ để tăng số.

**P1:** chỉ tối ưu repeated preparation/C/serialization hoặc shared traversal sau profile riêng, giữ whole-package parity. Mở rộng nguồn/catalog nhỏ rồi quyết định có bật heuristic mặc định không. Stop nếu exhaustive parity sai hoặc matched scope không thêm witness.

**Chưa xây:** production AND–OR/rewrite, policy/framework mới, P hẹp giả tạo/midpoint để ép Pareto, UI lớn, thêm session/FCP thiếu data khi không chặn demo. Quyết định hiện tại: **keep + simplify/optimize**.


Backlog cụ thể: P0 dùng `scripts/exposure.py` và `src/engine/remediation_runner.py` để chạy một intervention đã mined, báo counterfactual reachability/bypass; dùng `scripts/run_bloodhound_baseline.py` cho bảng baseline cùng scope, không đổi semantics để làm comparator dễ thắng. P1 chỉ mở `src/engine/search.py`, `src/engine/batch.py` khi profile hoặc cohort rộng hơn cho thấy bottleneck.
