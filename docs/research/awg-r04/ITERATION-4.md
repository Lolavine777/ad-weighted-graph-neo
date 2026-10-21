# Iteration 4 — giảm preparation của counterfactual, giữ replay độc lập

## Closeout compatibility và raw audit

Clean published `633bfaf6d5cc8d3dc1c610e4d39abfff3e92b353`: cả ba Week 4 modules **15/15 PASS**, 52,24s, gồm mutation/CRLF/source-pin/demo guards. Exact node-ID đối chiếu với core-before-compat cho thấy cả 14 failed nodes đã pass ở targeted reruns (113 compatibility hoặc 15 Week 4). Không chạy lại mọi test và không gọi whole suite PASS. [Machine closeout](evidence/iteration-4-closeout.json), [JUnit](evidence/iteration-4-week4.xml). Các trạng thái pending cũ bên dưới được supersede bởi kết quả này.

Để kiểm một phần yêu cầu raw → graph, chạy [independent direct-field harness](evidence/direct-raw-audit.txt), chỉ standard library, không gọi AWG parser/evaluator/cost. [Report](evidence/iteration-4-direct-raw.json) pin đủ sáu raw hashes và snapshot file hash. Forward census kiểm **46.109 unique directed edges từ 46.254 raw references**: 30.244 GenericAll, 15.843 MemberOf (explicit + primary), 15 WriteDacl, 5 direct AdminTo và 2 CanPSRemote. Tất cả có đúng raw record/attribute và assumed-time provenance; 0 failures. Ba controls xóa cạnh/đảo chiều/xóa provenance đều được phát hiện. Deterministic seed 297 giữ mẫu truy vết, nhưng assertions chạy toàn subset, không chỉ mẫu.

Giới hạn được đếm rõ: 10.275 raw references có DOMAIN-prefix alias hoặc GUID endpoint không nằm trong oracle này; không kiểm reverse false-positive extras hoặc nested/GPO derivation. Builtin SID scope dùng raw Domain ObjectIdentifier theo contract 1.3. Lượt oracle đầu giả định sai rằng S-1-5-32-581/582 globally unique, sinh 19 missing candidates; sau đối chiếu scoped nodes/edges, chỉ sửa oracle scoping, graph không đổi. First failed report giữ local và hash trong closeout. Không gọi đó là parser defect.

**Verified coverage limit của dataset:** 100 máy nhưng chỉ 1 có LocalAdmins không rỗng (5 entries), 1 có PSRemoteUsers (2), 0 Sessions; 3 RemoteDesktopUsers entries chỉ có CanRDP Unknown vì UserRights không đủ, không có positive CanRDP edges. Vì vậy full-SEAMLESS ở đây là full input, không phải full enterprise/session/lateral coverage. Audit không thay được fresh BloodHound comparator hoặc Windows lab.

## Kết luận có bằng chứng

**Verified:** trên cùng full-SEAMLESS snapshot (3.370 nodes / 56.367 edges), cùng một query AS-REP đến admin của một host và cùng một can thiệp runtime, median local của `prepare_baseline + run_remediation` giảm **155,897 → 62,093 giây** (2,51×; giảm 60,17%). Ba lượt trước: 141,731 / 181,811 / 155,897 giây; ba lượt sau: 56,496 / 70,455 / 62,093 giây. Đây không phải benchmark mọi source–goal hay mức tăng tốc của toàn sản phẩm. Host không được pin CPU; không suy diễn ý nghĩa thống kê từ ba lượt.

**Verified:** cả sáu decision packages bằng nhau theo full normalized dictionary, không chỉ so số lượng paths. Chỉ loại `execution.started_at`, `execution.elapsed_seconds`, `execution.source_pins`; giữ nguyên và so sánh run/request IDs, proofs, coverage, witnesses và denominator. Exact source pins trước/sau vẫn nằm trong evidence. Hash normalized chung: `sha256:36aedfa5dd4d3aba3a9fc8c2551c664ad9d652cad2385cb9745b45cbc7e5b097`.

**Verified:** tìm thêm lỗi public Python API trong prepared cache của baseline `6e68621`: thay `nodes_by_id` của graph có account disabled bằng index của graph enabled có thể làm `verify_search_envelope` cấp replay binding không đúng canonical projection. Fix getter-only cho `nodes_by_id` và `relationships`; negative test vừa từ chối replacement vừa kiểm replay của disabled graph vẫn thất bại. Đây không phải remote exploit, không phải biện pháp chống arbitrary Python/private-attribute mutation. Hai regression R1/R2 trước đó vẫn phải giữ.

## Thay đổi nhỏ, không đổi engine

- Runtime-only edit tạo RuntimeContext mới, giữ provenance intervention và dùng graph-owned static/prepared views. Không tạo canonical copy, EffectiveSnapshotFacts hay EngineGraph mới khi static graph/facts không đổi.
- Structural/static edits vẫn tạo projection riêng và kiểm binding. Không dùng điều kiện `snapshot_facts is ...` để quyết định reuse: cả hai có thể là `None` dù graph khác.
- Witness extraction dùng bound prepared view; structural edit lookup dùng endpoint index thay whole-edge copy/scan.
- Không bỏ independent `verify_package`, không cache digest qua public mutable data, không đổi semantic gates, search budget, cost/ranking hay P/I.

## Thiết kế phép đo và tái chạy

Baseline: clean isolated worktree `6e68621a83749b24170b9ab44b8e1368909123e6`. Candidate: chính baseline cộng hai source files có exact hashes trong [machine evidence](evidence/iteration-4-counterfactual.json); publication successor được ghi tại checkpoint/PR. Không đổi HEAD giữa sáu lượt để giữ nguyên engine revision trong decision package; code changes được phân biệt bằng source pins, không giả là clean baseline.

Input: snapshot SHA `73f4380f938bf70338661c487e3c6467c4b012be1519995f4419a1143a45a9a8`, cùng [pilot request](evidence/counterfactual-pilot-request.json). Bốn techniques; cap 10 paths / 6 steps / 1.000 expansions; chín runtime assumptions khai báo, không phải observations. Can thiệp duy nhất đặt admin channel thành False. Không chạy khai thác AD.

[Exact harness đã chạy](evidence/counterfactual-harness.txt) là Python, SHA `c15f651d67a6c100f3370af7e1f816b48e6bed654f52b8ad1be0118fcee489b3`; đuôi `.txt` giữ nguyên historical measured bytes. Có thể thực thi trực tiếp:

```bash
python docs/research/awg-r04/evidence/counterfactual-harness.txt \
  --repo /absolute/path/to/checkout \
  --snapshot /absolute/path/to/pilot-v2/snapshot.json \
  --pilot-request docs/research/awg-r04/evidence/counterfactual-pilot-request.json \
  --output /absolute/path/to/new-output --trials 3
```

Output directory phải mới. Harness chỉ cố định UUID run labels; không patch evaluator, generator, cost hoặc verifier. Graph loading và serialization/comparison được đo riêng ngoài pipeline. Snapshot/parser metadata cũng được giữ nguyên giữa before/after. Khi tái dựng snapshot mới, digest file có thể khác do metadata; không được bỏ binding để ép khớp historical package.

## Correctness và giới hạn sản phẩm

Selected regression suite hoàn tất: **101 passed, 2 skipped** (raw opt-ins), 39,46 giây; [JUnit](evidence/iteration-4-selected.xml). F1 chạy lại trên candidate: **12 nhóm / 78 biến thể, không mismatch** với frozen independent oracle. Raw follow-up và core/targeted closure có kết quả riêng bên dưới; không gọi whole-suite PASS.

Một cặp bị disconnect trong declared finite AS-REP scope; đây không phải domain-wide reachability reduction. Bài nhiều goals v2 và acquired-identity witness của iteration 3 là evidence khác, không cộng vào phép đo này. P/I vẫn chưa được đánh giá bằng benchmark này. ForceChangePassword/HasSession composition và fresh BloodHound head-to-head chưa được giải quyết bởi tối ưu preparation. Source compatibility đã đóng riêng; fresh numeric chỉ mới hoàn tất một projected case.

**Quyết định:** tiếp tục giữ và tối ưu planner. Đã có một thay đổi nhỏ, kiểm được decision parity, cho cải thiện thực tế; chưa có bằng chứng đủ để xây production AND–OR discovery. AND–OR chỉ nên thử nghiệm nếu profile sau preparation vẫn cho thấy repeated reachability grounding là bottleneck và oracle cho accumulated prerequisites giữ nguyên semantics.

## Kiểm chứng nối tiếp: raw và numeric

[Follow-up execution evidence](evidence/iteration-4-followup.json) ghi đúng phần đã hoàn tất, không thay frozen delivery-v11:

- Raw executor pytest pass; raw CLI pytest đầu trả exit 1 nhưng traceback không giữ stderr của subprocess. Không đủ evidence để kết luận nguyên nhân. Chạy CLI độc lập trên stable `ca3eceef` sau đó **exit 0**, 333,299s trong môi trường có concurrent validations (không dùng thời gian này làm benchmark trước/sau). Lặp lại toàn bộ assertions của raw CLI test và strict schema validation của cả bốn reports đều pass.
- Đủ sáu raw checksums, không đổi raw. `shared-channel`: 1/1 pair disconnected trong complete declared scope; sửa membership: 0/1, còn bypass; thiếu recovery evidence: Unknown, denominator 0, percentage null; step cap: truncated, denominator 0, percentage null. Không biến Unknown/truncated thành an toàn.
- Fresh numeric v5 delivery hoàn tất **một case projected** `source-a-projection`: 330/330 feasible và fully rated; native programs không đổi khi áp release; hai CLI subprocess, API và orchestration khớp semantic/ranking/coverage. Independent oracle kiểm 2.190 C units; min C trong candidate set là 2, `minimum_proven=False` trong public verification. Không phải 16-case/full-raw numeric acceptance, không phải new v2 goal adoption, và không phải C theo phút/giờ.
- **330/330 vẫn trên Pareto frontier.** Ví dụ chương trình ngắn nhất có P interval `[9/40, 8379/10000]` trong expert/model scope cũ. Đây là bằng chứng ranking chưa chọn lọc trong case này, không phải lý do tự thu hẹp P hay coi midpoint là risk score. Nên trình bày C-first + impact + evidence/assumptions, giữ interval và frontier như thông tin bổ sung; thuật toán Top-K hiện có vẫn phải công bố guarantee scope.
- Mỗi native CLI transport khoảng **311 MB**, normalized khoảng **273 MB**, dù graph projection chỉ khoảng 20 KB. Parent replay process từng có VmHWM khoảng 2,16 GiB theo `/proc`; không phải isolated CLI memory benchmark. Đây là volume đo được, **chưa đủ để gán CPU bottleneck** cho serializer. Profile có kiểm soát trước khi đổi transport; default full audit contract không được âm thầm mất witnesses/provenance.

Core-before-compat đã có final JUnit: **14 fail, 3.145 pass, 11 skip, 88 subtests pass**; loại riêng 193 final-CPI tests, không phải whole suite. Tám failure là stale likelihood/scenario source manifests; sáu Week 4 failures gồm hai source-byte pin checks và dirty-checkout observations, không phải chứng cứ engine/C/P/I thay đổi. Diagnostic so sánh cho thấy chỉ W4-CLI-PACKAGE `clean_tracked_source=False` và raw-prerequisite observation khác frozen cases. Không nới guard. Append likelihood v10 / scenario v11 giữ cả 35 file cũ, thêm graph.py vào authoritative pins; **113 delta checks pass**, 4 heavy transport checks đã pass trong core không chạy lại. [Compatibility evidence](evidence/iteration-4-compatibility.json) giữ failed nodes, full JUnit hash và history hashes.

**Fresh clean capture đã thực hiện** trên `b2db836bdc784473556678dfe99e5f30805130dd`: runner hai lần deterministic, **36 PASS / 2 NOT EXECUTED / 0 FAIL**. Đây là recapture sau POSIX path portability correction của test, không patch source pins bằng tay. Compact v6 (330.431 bytes, SHA-256 `eb919132cabcaf9c974bd6bfcb6dcb1938bb5ec74f992cced2984ce540d84548`) giữ nguyên semantic payload của full 3,5MB capture; sau existing prerequisite normalization bằng nguyên frozen cases-v3. V5/source history không đổi. Capture đầu d3b và full capture mới giữ ở hai namespace riêng. Ba modules đã chạy lại trên clean published 633bfaf6: **15/15 PASS**. Đây là source-compatibility/legacy synthetic acceptance, không phải full raw/current whole-suite nghiệm thu.

Các artifacts numeric lớn giữ local có hash; public follow-up là compact projection với omissions khai báo, không giả là nguyên 6,2 MB checkpoint. Không suy fresh BloodHound superiority, không biết approach riêng của mentor, và chưa nghiệm thu hoàn tất đề bài. `discover_source` hiện vẫn là batch loop từng goal, **không phải shared single-pass traversal**; gain chuẩn bị không được đổi tên thành cải tiến thuật toán multi-goal.

## Đối chứng kiến trúc đã chạy lại, không dựng ba engine production

F1 dùng cùng manually grounded finite actions và independent expected outcomes, không dùng candidate generator/cost của AWG để tạo oracle. Kết quả compact đầy đủ 78 biến thể ở [iteration-4-f1.json](evidence/iteration-4-f1.json); native attempts/paths lớn không nằm trong projection public và đã có hash của full local output.

| Semantics trong thí nghiệm | Planner hiện có | Conditional graph nhẹ | AND–OR first-support |
| --- | --- | --- | --- |
| Unary additive cycle/diamond | Reachability/C khớp oracle | Đủ, có exact C trong domain này | Reachability đúng; không phải optimizer C |
| Accumulated prerequisites/RBCD | Full case C=9; thiếu service không reach | Báo unsupported, không giả là tìm đủ | Reachability đúng trên finite grounding |
| Trở lại actor dùng được trước đó | Witness hợp lệ, C=3 | Báo unsupported trong prototype | Reachability đúng trên finite grounding |
| Shared-work case 10 | Min C=5, oracle độc lập xác nhận | Edge-local witness C=7; chủ động không claim exact shared C | First witness C=7, không claim min C |
| ForceChangePassword/HasSession composition | Không tự cấp usable identity/secret | Cũng không được tự bù prerequisite | Cũng không được tự bù prerequisite |

Đây là correctness/scope comparison, **không phải production performance benchmark** giữa ba kiến trúc hoặc BloodHound. Kết quả ủng hộ dùng BFS/Dijkstra cho đúng projection đơn giản, giữ native evaluator/union-work ledger khi cần semantics; AND–OR discovery đáng pilot khi có repeated-grounding bottleneck đo được, không thay planner chỉ vì tên thuật toán. Fresh controlled counterfactual gain đến từ preparation reuse, không từ thay search.
