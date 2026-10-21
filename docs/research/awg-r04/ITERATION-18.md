# Fresh BloodHound CE và demo nghiệm thu local

**Đã chạy BloodHound CE thật bằng Docker, import SEAMLESS qua converter có kiểm bảo toàn và đối chiếu hai footholds tới DA.**
CE và AWG cùng xác nhận bỏ OLLIE khỏi DA vẫn còn bypass.
Không có bằng chứng cần thay engine; giới hạn minimum trên full graph dưới caps vẫn còn.

[Chạy lại hai use cases và CE](DEMO.md) · [CE/Cypher evidence](evidence/iteration-18-final-ce-comparison.json) · [Local closeout](evidence/iteration-18-closeout.json).

## Nguồn và môi trường

Fetch xác nhận checkpoint `89620794c0c46c5985100b98bca8b9dc43863259` vẫn là head PR #298.
Code importer/compose/tests được commit tại **`2e4b05dd6b72a657aecda46be1f91968b14b9291`**; final CE import chạy từ revision đó.
Follow-up `84dd61e` giữ `--all` tương thích sáu Dataset A/B cũ; explicit SEAMLESS vẫn dùng lệnh riêng.
Python local là **3.14.7**, dependencies theo requirements hiện có.
Sáu raw files khớp manifest, upstream `3febc4089421725f9527c187f78d064ad09d5158`, raw snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`.
Raw, snapshot và full captures được giữ local; [index SHA-256](evidence/iteration-18-local-captures.json) cho phép kiểm đúng bytes.
Không reset hay stage PDF, `uv.lock` hoặc nội dung báo cáo local khác.

Stack final có project `awg-r04-ce-final-v1`, localhost ports 18080/17474/17687 và volumes riêng.
Hai project thử trước đã dừng, giữ nguyên volumes và logs; stack khác không bị xóa.
[Compose](../../../deploy/bloodhound/compose.seamless.yml) pin các image thực sự chạy:

| Image | Digest |
| --- | --- |
| BloodHound CE 9.8.0 | `sha256:88aeb60228d8ad09a8ac1cdcea8218b4aabe3d9ac642f2f66d50a6b144f4d301` |
| Neo4j 4.4.42 | `sha256:73b5a47eb9952f47fcc42fcc80bdd6bd0d6b71eea9a1a345c216675498c790e4` |
| Postgres 16-alpine | `sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685` |

[Actual container/image/volume bindings](evidence/iteration-18-final-container-bindings.txt) và [runtime version](evidence/iteration-18-docker-version.json) được lưu riêng.
Tag `v9.7.0` trong compose cũ không có trên Docker registry; tag release dùng dạng không có `v`.
Pull Postgres18 gặp TLS timeout; dùng image16 đã có sẵn, pin digest thực tế.
Docker credential helper bị treo; public pulls dùng client config tạm, không thay cấu hình hoặc credentials của người dùng.
Không dùng các vướng mắc môi trường này làm lý do dừng công việc độc lập.
Logs publish che password và bỏ trailing whitespace; full original bytes/hash giữ local, phép biến đổi ghi trong closeout.

## Compatibility: job Complete chưa đủ

Lần đầu upload **nguyên sáu raw files** trả HTTP500, `no data tag found`.
[Failure JSON](evidence/iteration-18-raw-import-failure.json) và [server log đã che password](evidence/iteration-18-raw-import-server.log) giữ nguyên nguyên nhân.
Raw v3 có BOM và envelope theo collection như `users`, `computers`, thay vì `data`.

Probe chỉ đổi envelope, giữ nguyên records/meta, được HTTP202 cả sáu file và job Complete/0 failed.
Tuy vậy log có **546 lỗi Owner + 7 lỗi ExtendedRight**, và các trường Members/LocalGroups/ChildObjects chưa khớp schema.
Đây là **baseline không hợp lệ**, không dùng để tuyên bố import thành công.
[Probe response](evidence/iteration-18-envelope-response.json) và [log](evidence/iteration-18-envelope-server.log) được giữ để không che lần thử sai.

Converter mới đổi envelope/schema, typed references, containment, tên ACE và computer local groups; không đi qua graph/parser/evaluator AWG.
Nó dùng manifest reader chung để verify raw bytes, giữ bản sao nguyên bytes và manifest chuyển đổi riêng.
Kiểm ngược toàn bộ row multisets bảo toàn **3.369 records, 53.040 ACEs, 13.324 membership refs, 2.816 containment refs và 11 local-right refs**.
Properties và identifiers gốc giữ nguyên; LocalGroup là artifact biểu diễn mới của CE.
Unknown fields, nonempty unsupported relations, thay identities/properties/refs, hash sai và output tồn tại đều bị từ chối.
Review phát hiện kiểm role chưa chặn duplicate LocalAdmins thay các role khác; đã sửa exact role coverage/cardinality và thêm hai regressions.
[Converted manifest](evidence/iteration-18-converted-manifest.json) có paired hashes; artifact ID `sha256:7f8493c7596d50f3478a52af16bfd9eb24eb27bf312b3585b3422d6d58e6c404` được tách khỏi raw snapshot ID.

## Fresh CE: đã kiểm gì

Final import **6/6 HTTP202, job Complete/0 failed, 0 ERROR trong server log**.
CE có **3.374 nodes / 78.363 relationships**; [metrics](evidence/iteration-18-final-import.json), [import log](evidence/iteration-18-final-import.log), [server log đã che password](evidence/iteration-18-final-server.log).
Graph được dựng bởi importer CE từ raw đã chuyển schema, không upload graph AWG vào Neo4j.

Audit stdlib độc lập xác nhận đủ **3.368 unique raw identifiers**; raw có 3.369 records nên không dùng record count làm unique count.
So 50.368 unique raw GenericAll/MemberOf triples tìm thấy **50.358 nonself triples**, không có unexpected missing.
Mười self-GenericAll bị CE bỏ đúng theo [ParseACEData v9.8.0](https://github.com/SpecterOps/BloodHound/blob/v9.8.0/packages/go/ein/ad.go#L465).
Lượt audit đầu đã fail ở mười cạnh này, được giữ [riêng](evidence/iteration-18-first-relationship-audit.json); không sửa raw hoặc AWG để ép totals bằng nhau.
CE còn 2.593 additional triples trong hai loại quan hệ đó và thêm các node biểu diễn/analysis; full totals không phải hợp đồng parity giữa hai sản phẩm.

Phạm vi kiểm semantic parity là direct GenericAll(source, enabled User) rồi direct MemberOf(DA), conditioned trên cùng usable source/context và scenario profile.
Cypher chạy trên graph do CE import, qua Neo4j HTTP; đây không phải benchmark shortest-path UI mặc định của BloodHound.
Counterfactual CE dùng bộ lọc loại đúng OLLIE→DA membership, không sửa persistent graph.

| Nguồn độc lập | CE/raw routes trước → sau | Hops projection | Native actions | Native C tìm thấy trước → sau | Reachable sau |
| --- | ---: | ---: | ---: | ---: | --- |
| FINWVIR machine identity | 4 → 3 | 2 | 3 | 1 → 1 | Có |
| OLA_CARSON usable identity | 4 → 3 | 2 | 3 | 1 → 1 | Có |

Projection gộp reset1 + activation0 thành một cạnh, membership0; đây là C ordinal do profile công bố, không phải metric mặc định của CE.
C1 là minimum của projection hữu hạn này; native vẫn truncated/minimumFalse.
BFS và weighted Dijkstra đều đủ cho tiểu bài toán direct/additive này, như oracle iteration16 đã chỉ ra.
BloodHound hỗ trợ custom Cypher; không mô tả nó như chỉ biết BFS hoặc không thể diễn đạt điều kiện.
Không gộp import/preparation/audit vào search time để so lệch; lượt này không đưa speedup claim giữa hai sản phẩm.
Chưa audit semantic equivalence toàn taxonomy; ví dụ CE chỉ derive 0 CanRDP dù raw có 3 RDP local memberships, còn các local-group references được bảo toàn trong schema chuyển đổi.
Không invent user-right facts để làm CE có thêm đường; nguyên nhân derived-edge chi tiết ngoài cohort DA không được nhận là đã giải quyết.

## Hai use cases đã chạy lại local

Use case một: FINWVIR ×12 auto goals, standard profile/C-v2/goal-guided, caps1path/3steps/6.000exp mỗi query.
Kết quả **4 witness/C1, 8 truncated-incomplete**; [brief](examples/local-one-defender-brief.md), [summary](evidence/iteration-18-local-one-summary.json).
Group entitlement DC/RODC không được đổi thành host control.

Use case nhiều compromise: FINWVIR và OLA ×3 auto goals, giữ hai trạng thái compromise độc lập, **2 DA witnesses/C1 và 4 truncated-incomplete**.
Harness lấy nguyên hai public DA queries, mine bốn candidates rồi chọn supported relationship theo binding coverage/stable ID.
Native chọn OLLIE→DA; replay cắt **2/2 programs mẫu**, rediscovery thực thi đủ hai after cells và tìm **2 bypasses qua DENA**.
**Reachable 2→2, proven disconnected0/2, unresolved-after0; minimumFalse giữ nguyên.**
[Brief có labels, actors/context, assumptions và can thiệp](examples/local-remediation-defender-brief.md) · [verified native report](evidence/iteration-18-local-remediation-report.json).
Bốn witnesses trước/sau được kiểm lại bằng raw ACE/member records và một reset work unit mỗi witness, không gọi evaluator/cost compiler AWG làm oracle.
Full package gzip kiểm CRC, decompressed byte-count và SHA độc lập; không bỏ full audit để làm demo đẹp.

Native captures có parent Git revision89620794 và working changes của importer/local files được ghi trong metadata, không gọi là clean-tree captures.
Toàn **75 native source pins** khớp actual Git objects ở parent và current bytes.
Hai harness lỗi ban đầu do chọn nhầm source SID và đường dẫn pilot cũ đã dừng/lưu riêng; namespace corrected không ghi đè chúng.
Brief Markdown publish thay dấu gạch dài bằng dấu ASCII; JSON/audit nguồn giữ nguyên.

## Validation và mức đáp ứng đề bài

**47 import/converter checks PASS**, gồm raw opt-in, hash/provenance tampering và duplicate-role regression.
**86 workflow checks PASS**, gồm CLI/exposure, native capped remediation/bypass, inventory/reuse và goal-guided bindings.
[JUnits](evidence/iteration-18-adapter-tests.xml) / [workflow JUnit](evidence/iteration-18-workflow-tests.xml) là selected suites; không gọi whole-suite pass hoặc dùng count thay product coverage.
Ruff toàn repository, format bốn Python files, YAML lint và contract hai synthetic fixtures PASS.
Cả **127 acceptance-v16 pins** giữ nguyên; không đổi engine/catalog/numeric/history nên không chạy lại benchmark nặng hoặc tạo successor dư thừa.

| Tiêu chí gốc | Kết luận hiện tại |
| --- | --- |
| Raw AD, taxonomy, mô hình C, pipeline | Đã có; raw public/assumptions và boundaries được công bố |
| Foothold → đích/đường/effort | Có demo tự inventory, witness, C ledger và brief |
| Chi phí thấp nhất từ node bất kỳ tới DA | **Chưa hoàn thành đầy đủ** trên full graph dưới truncation; C trả về là best found |
| Choke point và khuyến nghị | Có mined intervention/replay/rediscovery; thấy rõ bỏ riêng OLLIE chưa đủ |
| Đối chiếu BloodHound | Fresh CE import + independent direct-edge audit và matched DA cohort đã hoàn tất; chưa full-catalog/performance equivalence |
| Báo cáo/demo/tái lập | Có [lệnh cụ thể](DEMO.md), exact inputs/digests, logs, bounded evidence và full local captures |

Giá trị có bằng chứng của AWG là workflow điều kiện với actor/context, union work costs và kiểm chứng can thiệp có tìm bypass.
Đồ thị có trọng số đơn giản đã đủ cho cohort direct/additive này; không cần ba engines, fast path hoặc rewrite AND–OR để làm kết quả đẹp.
**Đề tài có MVP demo được và đối chứng CE thật; chưa đạt trọn yêu cầu minimum từ nguồn bất kỳ.**
P/I thiếu basis vẫn optional/unrated; không ép interval hoặc midpoint để thay đổi Pareto.
Không có kết luận tối ưu tập sửa, toàn domain, xác suất thành công hoặc thời gian tới DA.
