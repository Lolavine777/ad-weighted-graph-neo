# So sánh để bảo vệ đề tài: lợi thế có điều kiện, không phóng đại

**Đã chạy ba đối chứng native mới trên fixture sẵn có. C-first giải được nhược điểm đếm hop; Dijkstra cũng giải được khi C cộng được và cùng conditioning. Chưa có bằng chứng AWG vượt BloodHound CE.** [Execution evidence](evidence/iteration-17-comparison.json) · [Harness chính xác](evidence/run_fair_comparison.txt).

## Kết quả đã thực thi

Engine source `183ca90125d23be0a09d9d62b2d0b08745a81654`, Python3.14.8. Khi chạy v3 đang soạn docs/evidence; recorder giữ nguyên danh sách working changes, còn toàn bộ source files được đối chiếu exact với Git revision và current bytes. Dùng nguyên `two-routes-query.json`, `two-routes.json` và ledger synthetic `synthetic-a2-e.json` đã có; không sửa production code hoặc đặt giá mới. Direct admin: shared authentication1 + direct work4 = **C5**. Qua group: passive membership0 + shared authentication1 + inherited work1 = **C2**. Canonical edge weight1 là structural default, không phải C được dùng cho đối chứng này.

| Thí nghiệm | BFS/hop | Dijkstra với cùng C | AWG native CLI |
| --- | --- | --- | --- |
| Hai routes, điều kiện hợp lệ, native duyệt đầy đủ scope hữu hạn | Direct1hop, C5 | Qua group2hops, C2 | **C2**, minimum proofTrue trong declared scope |
| Giữ input/C, native max_paths=1 | Direct1hop, C5 | C2 khi giải projection đầy đủ | **C5**, truncated, minimum proofFalse |
| Authentication explicitFalse | Graph đã condition: không có đường | Graph đã condition: không có đường | **blocked**, scoped no-path proofTrue |

Không dùng hàng max_paths1 để tuyên bố Dijkstra và native có cùng execution budget: Dijkstra giải đầy đủ projection3edges; native bị giới hạn một program. Hàng này kiểm giới hạn output/guarantee của native, không phải benchmark tốc độ hoặc lỗi correctness.

Oracle riêng dùng Python stdlib: BFS, Dijkstra và union các work-unit IDs lấy trực tiếp từ ledger/action bindings. Không import candidate generator, semantic evaluator hoặc cost compiler AWG. Ba programs native trong case complete đều được đối chiếu union-C độc lập; best program có cùng edge IDs với Dijkstra. CaseFalse chỉ thay authentication fact/origin/rationale và bỏ ranking input vì không có witness cần chấm; không tái dùng packet khẳng định factsTrue. So với graph chưa condition sẽ là so khác semantics.

Ba native CLI calls và independent assertions đều PASS; ghi command, input/output SHA, source/config pins, full native guarantees, revision và working changes trong evidence. Full outputs giữ tại `reports/generated/awg-r04-comparison-v3`. Harness đặt cạnh checkout tên `repo`, chạy bằng Python của venv; output namespace phải mới. Không cộng ba case thành một test-suite count hoặc nhận là full-SEAMLESS benchmark.

## Liên hệ kết quả SEAMLESS đã chạy

[Iteration16](ITERATION-16.md) cho case direct/additive thực: cả native và projection BFS/Dijkstra đều có C1, trước/sau bỏ membership OLLIE; hai nguồn vẫn tới DA qua DENA. Independent raw subset có4→3routes mỗi nguồn, trong khi baseline max_paths1 chỉ trả một route mỗi nguồn. Không có lợi thế thuật toán của planner được chứng minh trong subset này.

Lợi ích sản phẩm đã giao nằm ở chuỗi **foothold → auto goals → chương trình với actor/context/điều kiện → C/work ledger → can thiệp → replay/rediscovery/bypass**, có nguồn gốc kết luận. Capability tích lũy, identity switching và shared work có các finite controls; chúng cần mô hình tương đương nếu dùng conditional graph/AND–OR. Chưa có đối chứng đủ để kết luận full state planner là cách duy nhất hay nhanh nhất.

## BloodHound: đã kiểm gì, thiếu gì

Ngày19/10/2026 kiểm môi trường hiện tại: không có executable Docker, Podman hoặc Neo4j; compose ports7474/8080 đều connection-refused; còn dưới100MiB đĩa lúc kiểm. **Fresh BloodHound CE: NOT_EXECUTED.** Có Java không đồng nghĩa có stack CE. Không đổi raw, phá captures hoặc dựng một hệ thống thay thế rồi gọi là BloodHound.

`scripts/run_bloodhound_baseline.py` hiện có các DatasetA/B, **không có SEAMLESS snapshot entry**. [Baseline CE A/B](../bloodhound-import-baseline.md) nói rõ SEAMLESS ngoài scope. [Legacy4.0.3 reconciliation](../seamless-legacy-403-final-reproduction.md) là bằng chứng lịch sử về cấu trúc/import; không phải fresh CE hoặc cùng-workload path/ranking benchmark. Không tự tạo BloodHound exports từ graph AWG để làm comparator.

Nguồn chính thức SpecterOps mô tả [BloodHound Query Library](https://specterops.io/blog/2025/06/17/introducing-the-bloodhound-query-library/) hỗ trợ custom Cypher cho cả CE/Enterprise và các truy vấn identity phức tạp. [OpenAPI guide](https://github.com/SpecterOps/BloodHound/wiki/OpenAPI-Spec-Guide) cũng mô tả API/spec của sản phẩm. Vì vậy **không mô tả BloodHound như chỉ có BFS hoặc không thể diễn đạt prerequisites**. Bảng trên là baseline thuật toán độc lập, không đại diện toàn bộ sản phẩm BloodHound.

## Cách trình bày ngắn khi bảo vệ

“Đề tài dùng C theo work units để xếp hạng thay cho chỉ đếm hop; ví dụ kiểm thử có đường2hop/C2 rẻ hơn1hop/C5. Với chi phí cộng được, Dijkstra cũng chọn đúng C2. AWG cung cấp workflow có điều kiện, typed actor/context và kiểm chứng remediation có tìm đường thay thế; kết quả hiện tại chưa chứng minh vượt BloodHound, global minimum dưới truncation hoặc tập sửa tối ưu.”

**Giữ planner và MVP đã có; chưa rewrite AND–OR.** Chuỗi demo và lời giải thích giờ có đối chứng cụ thể. Hai giới hạn đối với nghiệm thu trọn đề bài vẫn là fresh BloodHound cùng dữ liệu/semantics và minimum từ nguồn bất kỳ khi tìm kiếm chưa đầy đủ. Lượt này chỉ thêm evidence/tài liệu; giữ nguyên engine, numeric, source authorities và acceptancev16.
