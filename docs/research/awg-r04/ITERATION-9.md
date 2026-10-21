# Iteration 9 — batch nhiều đích và giảm RAM khi ghi audit

**Đã kiểm chứng lợi ích của shared wire trên batch và sửa một copy lớn trong atomic writer.** Batch1User×3auto goals giữ toàn bộ quyết định, traces và checkpoint. Writer mới giảm peak RSS16,72%, thời gian gần như không đổi; không đổi search, scoring hoặc cache authority.

Native writer/captures sạch tại **`acf4a0fea8c9bee0477110f1f505f33242149f3d`**, parent **`668bf5f6cb70c5c14397b11967adb920d0e15278`**. Thí nghiệm shared-wire cũ dùng baseline2708100; thí nghiệm writer dùng baseline668bf5f. [Machine evidence](evidence/iteration-9-batch.json) ghi riêng source revisions, toàn trial rows/commands/hashes và normalization. Không gộp hai giai đoạn thành một before–after hoặc cộng phần trăm.

## Workload và tính đúng

Nạp toàn snapshot SEAMLESS3.370nodes/56.367edges, sáu raw files khớp manifest. Source OLA_CARSON (`...-1395`) có ACL mạnh và usable identity tại context Computer `...-1000`; chưa có DA membership. Đây không phải ordinary low-privilege hoặc password-only source. Dùng đúng bảy runtime assumptions, ba techniques reset/activation/member, caps10paths/4steps/10.000exp mỗi query, global30.000. Các đích do inventory tự chọn, không nhập ba paths viết tay.

| Auto goal | Kết quả mỗi run | Expansions/attempts | C |
| --- | --- | ---: | ---: |
| DC `...-1000` | truncated_incomplete | 10.000 | chưa chấm |
| DA `...-512` | complete_success; reset DENA→activation→membership | 7.490 | 1 |
| EA `...-519` | truncated_incomplete | 10.000 | chưa chấm |

Một User×3goals là **3 distinct pairs**, không phải30distinct pairs từ10reruns. Cả ba minimum/no-path proof flags False; P/I chưa chấm. C=1 là ordinal scenario effort/best found.31.077inventory pairs ngoài cohort; không cộng vào historical1.600cells khác scope. Không có remediation/reachability-reduction result mới ở lượt này.

Comparator standard-library độc lập kiểm **toàn result/checkpoint/summary**, cùng byte-identical inventory/request/selection/overview. Trước normalization, nó tự tính lại scope digest từ request/graph/sourcepins/policy, từng trace digest và checkpoint payload hash/fingerprint; kiểm source pins bằng đúng frozen checkout. Sau đó chỉ loại revision, elapsed/phase times, đúng một changed source pin và các hashes dẫn xuất từ physical scope. Summary result SHA được kiểm với file bytes trước khi loại. Paths, attempts, decisions, Unknown, provenance, ranking và guarantees không bị loại. Đây là parity với incumbent, không phải independent AD correctness oracle cho hai goals còn Unknown.

## Hai thí nghiệm riêng

| Phase | Trials | Wall median trước→sau | Peak RSS median trước→sau |
| --- | --- | --- | --- |
| Shared wire:2708100→668bf5f | 6ABBAAB,3/mode | 35,442→33,183s (-6,37%) | 2.786.472→2.786.428KiB, gần như bằng nhau |
| Atomic writer:668bf5f→acf4a0f | 4ABBA,2/mode | 29,612→29,557s, không meaningful speedup | 2.787.308→2.321.284KiB (-16,72%) |

Các subprocess tuần tự, fresh small supervisor đo wall/RSS để tránh inherited parent high-water đã phát hiện ở iteration8. Heavy parity chạy riêng sau child, không nằm trong timer; không có test/profiler đồng thời. Thời gian bao gồm graph load, inventory, search/rating/replay/audit, checkpoint và serialize full result. Dùng cùng logical budgets, không có wall cutoffs. Shared OS cache và số samples ít: ranges có overlap, không confidence interval hoặc general SLA.

Full result khoảng**476.356.988bytes**, checkpoint**126.209.561bytes**; triage overview chỉ1.700bytes. Writer không giảm dung lượng hoặc cắt audit. Native output vẫn cần lưu trữ lớn; dùng overview/summary để triage, giữ full result cho drilldown/audit.

## Sửa gì và vì sao

`src/engine/batch.py::_atomic_json` trước đây ghép `json.dumps(...) + newline` thành chuỗi lớn rồi ghi. Nay ghi JSON và newline riêng trong cùng temporary file, đóng thành công rồi mới replace. Giữ ensure_ascii=False/sort_keys/indent2 và định dạng UTF-8, không thêm flag, framework hoặc dependency. Atomic replace và source-bound cache checks giữ nguyên.

**Verified:** bốn native exposure runs mới giữ full package/checkpoint parity; RSS giảm466.024KiB (~455MiB), xấp xỉ một bản serialized result. **Strong inference:** tránh giant-string concatenation giải thích gain này; các thay đổi production chỉ nằm ở writer. Không quảng cáo speedup từ chênh0,19% wall. Test bổ sung kiểm TypeError trong serialization không thay thế checkpoint cũ.

Profile riêng trên clean668bf5f:62,038s instrumented/130,60triệu calls. Wire21,227s cumulative, deepcopy14,222s, atomic writer6,794s; generator3calls3,149s, rating resolution2calls1,797s, graph identity2calls4,027s. Cumulative scopes overlap; không cộng hoặc dùng ratio này làm unprofiled speedup. **Verified trong scope này:** enumeration chưa phải nút thắt lớn nhất. **Hypothesis requiring experiment:** repeated direct-ACL inventory/graph copies có thể reuse hoặc đọc theo source qua API an toàn; chưa triển khai cache mới hay bỏ binding guards.

## Validation và giới hạn

- **109 selected PASS/10,89s**: batch/resume/worker, exposure/scenario-policy, binding/reuse R1/R2/R3, source-history và checkpoint rollback khi serialization lỗi. Không whole-suite claim.
- Clean native Week4 hai lần: **36PASS/2NOT_EXECUTED/0FAIL**, frozen semantic digest vẫn `e4f9a3f1779753650a45dbf4c671c8cf68363e100c4a9bc861850a0cb2cbbbec`. Append [v11](../../../reports/research/week4-guided-exploration-acceptance-manifest-v11.json), SHA-256 `5d273d2f7a95d265d6f6912a283422f689b4774735128da7adfb559f565ff513`; giữ v10/frozen assertions. Hai manual checks vẫn chưa executed.
- **Final clean `47d039e7bf86ed05c0a8006ab6d27b219324aecd`: 248/248 PASS, 115,34s, zero skip**, gồm query CLI, C-only/reset, exposure/policy, native batch/resume/worker, identity goals, binding/reuse R1/R2/R3, source-history và ba Week4 modules. Native writer bytes bằng measured implementation; mọi v11 file pins bằng actual files. [Closeout/JUnit](evidence/iteration-9-closeout.json). Các tests trước có overlap; không whole-suite/AD coverage claim. Không thay numeric/history hoặc nới guard. Mọi job đã complete, không pending.

**Giữ planner và tối ưu có kiểm chứng.** Bằng chứng mới nói về vận hành batch, không chứng minh AWG tốt hơn BFS/Dijkstra/AND–OR trên mọi bài toán. Techniques vẫn chỉ ba, planner vẫn tìm riêng mỗi goal. Original Computer→DA, typed FCP/HasSession composition và fresh BloodHound CE comparator còn open. Raw có0Sessions/1host nonempty LocalAdmins, không giả coverage lateral movement toàn doanh nghiệp.

## Tái hiện và việc tiếp

Exact harnesses được lưu byte-for-byte trong [wire benchmark](evidence/batch-audit-wire-benchmark.txt) và [writer benchmark](evidence/batch-audit-writer-benchmark.txt). Chạy bằng Python từ repository root, truyền `--before`, `--after` là clean frozen checkouts; `--snapshot`, `--assumptions`, `--raw` là paths có đúng pins trong machine evidence, `--output` là namespace chưa tồn tại. Harness dùng Linux wait4, không phải runtime requirement mới của AWG. Toàn native JSON/checkpoints/profiler giữ local, hashes công bố; projection không thay full decision package. Các tests cuối dùng fixtures nhỏ, không duplicate thêm những full audits lớn.

**Next P0: quay về gap chức năng của đề bài — Computer foothold.** Audit supported initial capabilities, dựng independent oracle phân biệt local control/usable domain identity, rồi chạy case có evidence hợp lệ; không seed credential ngầm hoặc bù Sessions không có trong raw. Source prep/profile reuse là P1 sau correctness/coverage case đó, giữ R1/R2/R3. Chưa triển khai production AND–OR, probability narrowing hay quét hàng chục nghìn Unknown chỉ để tăng counts.
