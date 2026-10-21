# Iteration 8 — audit nhanh và gọn hơn, giữ đầy đủ bằng chứng

**Đã thực hiện tối ưu nhỏ và đo đối chứng:** với một query C-rated trên toàn SEAMLESS, median CLI 10,036s → 9,563s ở format cũ; opt-in compact còn 9,078s, dung lượng 90,49 → 59,80 MB và peak RSS giảm khoảng 13%. Toàn bộ semantic và package sau normalization có kiểm soát bằng nhau. Không đổi planner hoặc cắt attempts để tạo speedup.

Native code bắt đầu tại `745bbd2a206312756de024af020bb8d419b8ef98`; corrected benchmark/full captures chạy trên clean **`b605f5db596511aad40204cc62af58cb625073b5`**, baseline clean **`2708100b83549dc606d610de2c0b20e19130209d`** ở detached worktree. [Machine evidence](evidence/iteration-8-audit.json) chứa đủ chín trial rows, commands, source/config/raw/input pins, profile và lỗi instrumentation ban đầu. Main/develop không đổi.

## Điều đã xác minh

Query giữ nguyên exact batch-public-query của iteration7: OLA chưa có DA membership nhưng có ACL mạnh, usable tại Computer context khai báo; reset DENA → activation → DA entitlement. Ba techniques, caps 10 paths/4 steps/10.000 expansions, bảy assumptions. Full snapshot 3.370 nodes/56.367 edges; sáu raw files được kiểm lại manifest. Đây không phải account ít quyền, password-only source hoặc quan sát exploit thật.

**Verified:** ở baseline profile, `wire` chạy 3.961.811 lần/cumulative14,160s trong tổng24,776s instrumented; native generator1,393s. JSON bridge đang tốn công xét dataclass/Mapping/container trên các scalar đã là JSON. Bản sửa chỉ thêm fast path cho **exact** str/int/float/bool/None; subclasses, custom mappings, state/transition objects, ordering và provenance vẫn đi qua logic cũ.

Opt-in native query CLI **`--compact-output`** chỉ bỏ whitespace, giữ toàn package. Default indent2 giữ nguyên. Schema, semantic hash, attempt detail, source authority, cost và optimum flags không đổi. Không thêm framework/dependency hoặc audit sampling. Shared `wire` cũng được batch sử dụng, nhưng lượt này **không đo batch speedup** hoặc đổi batch/exposure output format.

## Phép đo công bằng

Chín subprocess chạy tuần tự theo ba cycles: before–after–compact, after–compact–before, compact–before–after. Mỗi mode ba trials, cùng interpreter, snapshot/query/raw bytes và logical budget. Không chạy test/profiler đồng thời. Mỗi mode xuất JSON đầy đủ; parsing/parity của parent nằm ngoài thời gian/RSS native child.

| Median của 3 trials/mode | Baseline pretty | New pretty | New compact |
| --- | ---: | ---: | ---: |
| Wall seconds | 10,036 | 9,563 | 9,078 |
| User CPU seconds | 9,232 | 8,435 | 8,476 |
| Peak RSS KiB | 720.272 | 719.260 | 627.856 |
| Output bytes | 90.488.235 | 90.488.361 | 59.799.180 |

**Verified trên workload này:** median wall giảm4,72% với pretty, 9,55% với compact; compact giảm33,92% bytes và12,83% peak RSS so baseline. Chênh126 bytes ở pretty là physical source metadata, không phải thêm semantic evidence. Ba trials/mode chưa cho confidence interval hoặc bảo đảm chung; ranges có overlap. Không lấy profile timing ratio làm end-to-end speedup.

Tất cả chín native outputs giữ **1 witness/7.490 expansions/7.490 attempts/7.494 diagnostics/C=1/P/I unrated**. Native minimum proof vẫn **False**, không chuyển thành optimal vì enumeration complete. So trực tiếp toàn semantic dictionaries, không chỉ witness count/C; semantic digest và normalized whole-package digest đều trùng. Chỉ normalize runtime started/duration, physical revision và đúng hai source-file pins của implementation/harness; các input/config/other source pins, acceptance và guarantee fields vẫn kiểm bằng nhau.

## Instrumentation defect đã phát hiện và sửa

Lượt v1 cũng có full parity nhưng `wait4.ru_maxrss` bị nhiễu bởi memory parent lớn trước fork. Independent probe cấp160MiB cho parent: child `/proc/self/status` VmHWM12.572KiB nhưng direct wait4 báo180.536KiB; qua fresh supervisor chỉ13.468KiB. Không gọi đây là product memory regression.

Corrected v2 dùng một supervisor nhỏ mới cho mỗi trial; native CLI start/execute/write vẫn nằm trong timer, supervisor startup/parity parsing nằm ngoài. Giữ toàn v1 và probe với hashes, không ghi đè hoặc chọn lại chỉ những trials nhanh. V2 là nguồn primary cho bảng trên. Baseline/profile/native captures và commands còn nguyên local, projection Git ghi rõ omissions.

## Profile theo subsystem

| Cumulative seconds instrumented | Before | After pretty |
| --- | ---: | ---: |
| Graph load/validation `from_snapshot` | 5,047 | 4,928 |
| Native enumeration `generate_attack_paths` | 1,393 | 1,308 |
| Rating resolution `resolve_generated_rating_inputs` | 1,459 | 1,432 |
| Candidate assessment orchestration | 0,079 | 0,073 |
| Ordered credential replay, 2 calls | 0,0011 | 0,0010 |
| Wire conversion, 3.961.811 calls | 14,160 | 9,316 |
| JSON iterencode, 76.494 calls | 1,487 | 1,466 |

Tổng profile24,776→19,198s, function calls65,84→44,34 triệu. Cumulative scopes overlap; replay trong table chỉ là named credential replay, không đại diện mọi verifier. Đây là chẩn đoán bottleneck, không cộng các dòng thành tổng hoặc suy toàn hệ thống nhanh23%. Benchmark unprofiled ở trên mới là phép đo end-to-end tương ứng.

## Correctness, yêu cầu gốc và kiến trúc

- **152 selected tests PASS, 29,846s** trước clean capture: independent synthetic ledger/ordered reachable states chạy cả pretty/compact, full-package equality cho stdout/file, native batch/worker/resume, C-only và R1/R2/R3 binding/reuse. Suites overlap các lượt cũ.
- Clean native Week4 twice **36 PASS/2 NOT EXECUTED/0 FAIL**, semantic digest vẫn `e4f9a3f1779753650a45dbf4c671c8cf68363e100c4a9bc861850a0cb2cbbbec`. Append [v10](../../../reports/research/week4-guided-exploration-acceptance-manifest-v10.json), SHA-256 `bb0905bd9d5141fa9d1eb86d31e51511fb356920aa67fe347836c4d103def353`; v9/frozen v3 giữ nguyên. Hai manual checks chưa executed, không đổi thành pass.
- First clean closeout `0ca40af`: **246 pass/1 fail** vì source-authority guard bắt đúng `query_cli.py` drift. Đã append likelihood source-manifestv11/scenario source-manifestv12 và cập nhật reader/generator; giữ mọi numeric, old manifests, previous/ancestor hash checks và current-source tamper negatives. **76 history/catalog/scenario checks PASS, 164,53s**, có raw probes và API/CLI/oracle. [Compatibility evidence và failing JUnit](evidence/iteration-8-compatibility.json). Không chuyển pending proposal thành adopted vì sửa source metadata.
- **Final clean `2eef19515a8d464860a444b67ef151ab70705fdb`: 247/247 PASS, 113,42s, zero skip**, gồm CLI/compact oracle, C-only, exposure/batch/policy/worker/resume, binding/reuse/source authority và ba Week4 modules. Native `src/` bytes vẫn bằng benchmarked revision; ba research reader/generator scripts chỉ có metadata-compatibility changes. Fresh executable CLI giữ toàn semantic và normalized package bằng benchmark; normalization chỉ đúng ba source hashes đó, physical revision và runtime. V10 byte pins không drift. [Closeout/JUnit](evidence/iteration-8-closeout.json). Ruff577 files/contractpass; link check chỉ historical R03 ZIP còn thiếu. Publication cuối chỉ docs/evidence, không relabel old captures hoặc claim whole-suite pass.

**Verified:** lượt này cải thiện chi phí xuất bằng chứng của use case1, giữ paths/C/Unknown; không mở coverage hay giải được thêm source–goal. Workflow đa nguồn/đích và remediation vẫn như iteration trước; không có reachability-reduction hoặc choke-point result mới. Máy bị chiếm→DA với C đầy đủ/minimum proven, FCP/HasSession composition và fresh BloodHound CE comparator vẫn chưa nghiệm thu chung.

**Strong inference:** tối ưu bridge/preparation trước là hướng đơn giản hơn việc thay planner, vì có measured gain nhỏ mà không nhân đôi semantic rules. BFS/weighted Dijkstra/conditional hoặc AND–OR cũng cần xuất evidence đúng khi so cùng sản phẩm. Phép đo này không so speed giữa engines và không chứng minh engine hiện tại tối ưu nhất.

**Hypothesis requiring experiment:** dư địa tiếp nằm ở full second wire traversal và repeated immutable graph/facts preparation. Trước khi bỏ một traversal phải kiểm execute() trả gì cho callers, typed facts/ranking outputs và mutation isolation; không mặc định mọi payload đã JSON-safe. Chỉ pilot AND–OR khi profiling đúng scope chỉ ra grounding/enumeration là nút thắt sau các thay đổi nhỏ.

## Tái hiện và next action

Giữ working tree sạch. Dựng baseline detached checkout tại2708100; dùng snapshot/query/raw exact pins trong machine evidence (query tạo được bằng helper iteration7). Chạy trong namespace mới:

```sh
python -m scripts.research.benchmark_query_audit \
  --before-repo ../baseline-270 \
  --snapshot data/processed/awg-r04/pilot-v2/snapshot.json \
  --query reports/generated/awg-r04-effort-pilot-v4/batch-public-query.json \
  --raw-dir data/raw/SEAMLESS \
  --output-dir reports/generated/audit-reproduce
```

Harness RSS yêu cầu Linux wait4, không phải runtime requirement của AWG. Native query thông thường chỉ thêm `--compact-output` bên cạnh các flags cũ; vẫn cần sáu prerequisites và đúng label cho SEAMLESS.

P0 tiếp: đo một pilot bounded source–goal batch cùng raw/scope bằng cùng methodology để biết shared wire gain có chuyển sang use case2 không; giữ R1/R2/R3 và whole decision-package parity. Sau đó chọn **một** repeated preparation/serialization hotspot theo profile, không mở thêm engine. P1 Computer capability oracle và typed composition/CE comparison còn trong backlog. Không expand P/I, không coi Unknown là safe, không quảng cáo domain-wide/global-optimum result từ phép đo này.
