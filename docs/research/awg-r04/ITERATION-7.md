# Iteration 7 — effort cho danh tính đặc quyền vừa lấy được

**Đã nối C-only vào discovery API/batch/CLI và chạy trên toàn snapshot SEAMLESS.** Một User chưa có membership DA lấy được danh tính khác có membership DA qua ba bước có điều kiện; witness có **C=1**, P/I chưa chấm. Đây là rubric ordinal, không phải thời gian khai thác hay tối ưu toàn cục.

Native code và các captures cuối chạy tại clean **`143dc5d833e20270a1b343124df11b95fab3f506`**, parent `6c582c581cc922d2cefd4f013da51ec3687bd968`. Report/evidence là descendant trên feature PR #298. [Machine evidence](evidence/iteration-7-effort.json) giữ source pins, provenance, assumptions và hai work-unit ledgers đầy đủ; không sửa báo cáo cũ thành kết quả mới.

## Thay đổi có phạm vi

`src/engine/ranking/reset_effort.py` biên dịch applicability vào **native rating resolver**, không thêm scoring engine. Opt-in `reset-activation-c-v1` lấy nguyên hai giá C từ release/rubric cũ: direct GenericAll password reset C=1, activation của identity vừa reset C=0. Passive membership không sinh active work; canonical union-work deduplication giữ nguyên.

Đây là **áp dụng rubric ordinal cho scope scenario mới của solo fork**, được bật tường minh. Historical review chỉ cung cấp numeric cũ, không có nghĩa reviewer đã duyệt source/goal/context mới. Các file numeric lịch sử giữ nguyên. Không import P/I, không đổi interval hoặc dùng midpoint. Một operation thành công mỗi work unit; không mô hình retries hay quy đổi C thành minutes.

Applicability dựng trước search: direct initial User-owned GenericAll → User cùng domain, activation owner-bound tại cùng Computer context. Record khóa snapshot, owner/source, method, scenario, auth context và exact work-unit digest. Other work vẫn chưa có giá. Existing membership route, second usable identity seed sẵn, Computer source, host-control goal và cross-domain ngoài profile: **vẫn search**, metadata ghi `not_applicable`. Membership check không prune hoặc kết luận safe/no_path; cũng tránh trình bày passive-only empty-product P như một adoption P mới.

Batch pin resolved profile definition/digest vào reproducibility/checkpoint/cell identity; đổi hoặc bỏ profile không reuse cache. Exposure CLI có `--effort-profile`; dùng chung với explicit `rating_resolution` bị từ chối. Không đổi candidate generator, semantic rules hay replay guard.

## Thực thi trên SEAMLESS

Raw public commit `3febc4089421725f9527c187f78d064ad09d5158`, sáu file/11.371.828 bytes khớp manifest. Snapshot **3.370 nodes/56.367 edges**, file SHA-256 `73f4380f938bf70338661c487e3c6467c4b012be1519995f4419a1143a45a9a8`. Toàn graph được nạp; techniques/cặp source–goal vẫn có scope hữu hạn.

Factory chọn deterministic một trong năm eligible pairs: **OLA_CARSON (`...-1395`) → DENA_WILLIAM (`...-2799`) → DA (`...-512`)**, context Computer `...-1000`. OLA chưa có đường membership tới DA nhưng có ACL GenericAll rộng: **không gọi đây là tài khoản ít quyền thông thường**. OLA đã usable tại context khai báo, không phải password-only; DENA chưa usable ban đầu. Bảy runtime gates là assumptions công khai, không phải quan sát thành công trong AD thật.

| Probe | Kết quả thực thi | Giới hạn |
| --- | --- | --- |
| Old actor-specific goal | 0 witness, 10.000 expansions, truncated | Không chứng minh no_path |
| Acquired-identity goal chưa C | 1 witness reset → activation → membership, 7.490 expansions | Native ordered replay hợp lệ, C chưa chấm |
| C-only cùng query | C=1, hai active units cost 1 và 0 | Full wire paths/expansions trước–sau bằng nhau |
| Exact batch query qua API/CLI | Paths, min_effort, rating_coverage, ranking_result bằng nhau | Comparator chỉ thêm documented candidate_id envelope của CLI |
| Batch một source × DA goal | 1 success/C-rated, 0 P-rated | 12 manifest goals, 1 executed/11 ngoài pilot |
| Exposure một source × hai auto goals | 1 C-rated complete_success; 1 truncated_incomplete/unrated | Host goal ngoài C scope vẫn search; 31.078 inventory pairs ngoài cohort |

**`is_minimum_proven_over_scope=False` được giữ nguyên**, dù query DA kết thúc không truncated. C=1 là best found. Không nâng thành minimum proven vì chỉ có một returned path; Unknown attempts và giới hạn phạm vi vẫn quan trọng. P/I của active witness null/unrated, impact auto goal Unknown.

## Kiểm chứng

Oracle trong `tests/test_reset_effort.py` tự xác định fact/action expectations và union operations, không gọi native generator hoặc cost/ID compiler để tính expected C. Nhiều owners/orderings kiểm reset C theo distinct operations và activation 0, không theo hops. Negative controls: missing/False prerequisites, owner/context/source/snapshot/method/unit digest, unpriced active work, truncated optimum, profile forgery/conflict, worker/resume và executable exposure CLI. Native replay là implementation under test, không thay independent expected outcome.

- **166 selected PASS, 31,140s**; sau additions chỉ ở oracle/test: **21 PASS, 1,530s**. [Selected JUnit](evidence/iteration-7-selected.xml), [oracle JUnit](evidence/iteration-7-oracles.xml). Suites overlap; không cộng thành whole-suite coverage.
- Clean native Week4 hai lần: **36 PASS/2 NOT EXECUTED/0 FAIL**, semantic digest `e4f9a3f1779753650a45dbf4c671c8cf68363e100c4a9bc861850a0cb2cbbbec`. Append [v9](../../../reports/research/week4-guided-exploration-acceptance-manifest-v9.json), SHA-256 `90be6f244fc3c7fb87659c91149752033ee1ef835ce2476b8996f9a2bc2f623e`; giữ v8/frozen assertions. Hai manual checks chưa thực thi, không biến thành pass vì có raw.
- **Final clean `7fae1ba1355f4f627e4a8cd4f5a50d4296bd2070`: 182/182 PASS, 86,669s, không skip**, gồm 21 C-only, CLI/batch/policy/worker/resume, identity goals, binding/reuse, numeric source history và ba Week4 modules. Native source/acceptance byte pins khớp. [Closeout/JUnit](evidence/iteration-7-closeout.json). Ruff check/format **575 Python files** và contract hai synthetic fixtures pass. Publication cuối chỉ đổi docs/evidence; không gán kết quả cho native code khác.

Development pilot từng thiếu CLI prerequisite flags, rồi thiếu candidate_id envelope trong comparator. Đã sửa runner, không nới CLI guard/semantics. Initial pytest failures do test fixtures/assertion shapes sai cũng được pin; không đếm là engine defects hoặc dùng captures đó thay final v4.

## Performance quan sát được

Pilot: unrated API 0,862s; C-only API 0,925s; một-cell batch 9,905s; executable CLI 10,521s. Scope/output khác nhau, **không phải paired speedup**. CLI tạo **90.488.145 bytes**, batch-result **133.066.309 bytes** dù chỉ một returned witness. Full captures/hashes giữ local; Git chứa projection/complete per-unit ledger. Inventory còn ghi một temporary checkpoint spill file, không phải completed checkpoint hoặc run khác.

Exposure hai goals: load/validate 2,537s, inventory 1,454s, compile/write request 0,545s, batch search+audit 14,615s, serialize full result 5,940s; tổng 25,437s. Chưa tách search khỏi replay/rating bên trong batch. **Verified:** output transport đáng kể. **Strong inference:** bounded audit/preparation reuse đáng pilot trước engine mới. **Hypothesis requiring experiment:** compact attempt storage giảm latency/RSS mà giữ decisions/provenance; chưa có after-run nên không claim gain.

## Đề bài và alternatives

| Yêu cầu | Sau lượt này |
| --- | --- |
| Graph AD có provenance | Verified full public raw; independent direct-edge audit ở iteration4 |
| Một compromise → các đích chưa viết tay | Workflow có; lần này hai auto goals thực thi, một C-rated |
| Máy bị chiếm → DA chi phí thấp nhất | Chưa nghiệm thu chung: Computer không cấp ngầm domain identity, C scope hẹp, native minimum proof vẫn false |
| Choke point đa nguồn/đích | Có từ lượt trước, không rerun ở đây; 80% observed programs cut cũ không phải reachability reduction |
| So BloodHound | F1/baselines có; chưa có fresh CE runtime comparator, không suy đoán approach riêng của mentor |

**Verified:** conditional graph ground đúng cũng biểu diễn được chain reset/activate/member này; BFS có thể trả reachability, không dùng hop thay C. Dijkstra trên action states/graph với prerequisites và costs đúng là baseline công bằng; structural-only graph không tự có owner/activation bridge. AND–OR biểu diễn được multiple prerequisites, nhưng một chain không chứng minh nó nhanh hơn. F1 lịch sử còn có shared work/RBCD/cycles cần đúng semantics; không tuyên bố native engine độc quyền xử lý được chúng.

**Giữ planner, tối ưu có bằng chứng.** Thay engine lúc này nhân đôi semantic maintenance trước khi xử lý output/preparation overhead đã thấy. Chỉ pilot AND–OR discovery nếu paired profile cho thấy grounding/enumeration chiếm ưu thế sau tối ưu nhỏ và oracle vẫn đúng identity/context/shared work.

## Tái hiện và backlog

Sau downloader/build trong README, chạy trên snapshot path thực tế, namespace chưa tồn tại:

```sh
python -m scripts.research.identity_effort_pilot \
  --snapshot data/processed/awg-r04/full/snapshot.json \
  --raw-dir data/raw/SEAMLESS \
  --output-dir reports/generated/identity-effort-reproduce
```

Helper tự chọn pair, tạo queries, batch và exact CLI replay với sáu raw prerequisites. [Unrated query](evidence/iteration-7-unrated-query.json), [bảy assumptions](evidence/iteration-7-assumptions.json) publish nguyên bytes. Auto discovery dùng `scripts.exposure`, source/context nêu trên, ba techniques `scenario_reset_password`, `acquire_reset_identity`, `propagate_group_entitlement`, `--evaluation-mode scenario --assumptions PATH --effort-profile reset-activation-c-v1`, caps 10 paths/4 steps/10.000 expansions, hai goals. Machine evidence giữ inputs/budgets và từng cell.

1. **P0:** paired profile exact rated query; baseline full audit so bounded/spooled prototype. Đo latency/RSS/output bytes, so full semantic decisions/per-attempt status/provenance và giữ R1/R2/R3. Chỉ ship khi parity pass và có gain thật.
2. **P1:** immutable preparation/fingerprint reuse theo profiler, không bỏ verifier. Sau đó Computer foothold profile có capabilities/facts rõ và independent oracle, không seed identity ngầm.
3. **P2:** typed FCP/HasSession composition và fresh BH comparator. Chưa mở P/I, all-catalog numeric coverage hoặc production AND–OR.

Raw có 0 Sessions/chỉ một host nonempty LocalAdmins. Historical R03 ZIP còn thiếu/link check còn gap đó. Không có whole-suite completion, whole-domain proof, real AD exploitation hoặc calibrated probability trong kết luận này.
