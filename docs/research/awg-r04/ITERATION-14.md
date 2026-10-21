# Dùng giả định để có câu trả lời, không để demo mắc kẹt ở Unknown

**Giả định là đầu vào hợp lệ của sản phẩm.** Khi đã chọn một scenario, engine phải áp dụng các điều kiện đó, tìm và xếp hạng đường trong scenario. Không cần có telemetry cho mọi điều kiện mới được đưa ra khuyến nghị. Provenance giúp biết kết luận dựa vào đâu; không phải một cổng bắt người dùng chứng minh lại từng giả định.

## Lỗi thật đã sửa

Profile `seamless-standard-v1` lọc cạnh trước khi tạo assumptions cho đồ thị trên 200 cạnh. Bảng ánh xạ còn tên technique cũ, thiếu `scenario_reset_password` và bốn tên canonical cho permission mutation/RDP/WinRM. Vì vậy chọn đúng profile vẫn không tạo ba điều kiện reset cho demo hiện tại.

Oracle nhỏ, độc lập về expected outcome: Computer có GenericAll trên User, User là thành viên DA. Không khai báo riêng runtime facts. Đồ thị hai cạnh có witness; thêm 201 cạnh từ các User không bị kiểm soát thì mất witness/indeterminate. Sau sửa, cả hai giữ nguyên chuỗi reset → activation → membership, C=1. Thêm các controls không có quyền/observed-False: profile không tự tạo quyền hoặc ghi đè False. Kiểm tra toàn bộ tên canonical thuộc sáu nhóm quan hệ mà policy đã hỗ trợ để tránh tái diễn.

CLI nay chỉ cần chọn `--scenario-policy seamless-standard-v1` là chọn scenario mode. Nếu không chọn profile, mặc định evidence-only cũ giữ nguyên. Chỉ định rõ evidence-only cùng scenario profile vẫn bị từ chối vì hai yêu cầu mâu thuẫn.

## Chạy thật trên full SEAMLESS

Snapshot 3.370 nodes/56.367 edges, một explicit machine identity FINWVIR, **cả 12 đích quan trọng tự inventory**, ba techniques reset/activation/membership. Không nhập owner trung gian hoặc đường đi. Request trước/sau giống hệt byte; không có bảy assumptions viết tay của iteration13. Cùng standard profile, 1path/3steps/6.000exp mỗi query/global72.000exp.

| Lượt xét transition trong 12 queries | Trước sửa | Sau sửa |
| --- | ---: | ---: |
| Indeterminate | 71.916 | **48** |
| Tỷ lệ indeterminate | 99,883% | **0,067%** |
| Applicable | 36 | **71.904** |
| Blocked | 48 | 48 |
| Goals có witness với FIFO/budget này | 0/12 | 0/12 |

**Giảm Unknown không đồng nghĩa tự giải được việc tìm đường.** Sau khi nhiều hành động hợp lệ cùng mở ra, FIFO tốn budget vào các nhánh trước khi đến mục tiêu. Cả 12 cells vẫn truncated, không phải no_path. Bốn indeterminate mỗi query còn lại không phủ nhận hàng nghìn hành động đã được conditioning thành công.

Đây là so cùng global-profile input trước/sau sửa, khác scenario bảy facts chọn riêng ở iteration13. Không dùng hai scope để quảng cáo tăng/giảm reachability. Native batch/audit đơn lượt 78,82s trước và140,59s sau: số hành động applicable và lượng assumptions thay đổi lớn; **không có speedup claim**. Full native dictionaries được giữ lossless trong gzip, CRC/byte-count/SHA-256 được kiểm độc lập; source pins đối chiếu Git objects của từng revision.

[Execution evidence](evidence/iteration-14-global-policy.json) giữ từng goal, status counts, assumptions digests, actual source pins và đường dẫn/hash full captures. Captures native ở clean `133517f` và `e5b6381`; không sửa source khi chạy.

## Thí nghiệm chỉ đổi queue: tìm được DA với global assumptions

Một prototype **ngoài production** dùng chính candidate generator, evaluator, state transitions và C compiler hiện có. Nó chỉ ưu tiên queued states theo reverse MemberOf distance của identity đã reset/dùng được tới goal; không xóa candidate/state, không có owner DENA viết sẵn, không thêm quy tắc AD.

Trên cùng full graph và cùng logical budget cho một DA goal tự chọn từ inventory: **FIFO không có witness ở6.000exp; prototype có witness ở4.995exp, C=1**. Đường FINWVIR→DENA→DA được replay riêng bằng native transitions, final state khớp và goal predicate đúng. Profile toàn cục thay cho facts viết tay. Không có minimum proof; đây không phải A* admissible, cost-optimal search hoặc kết quả cho cả12goals. Prototype/harness và witness/effects/digests được pin trong evidence.

Kết quả này xác định ưu tiên tiếp: **đưa thứ tự tìm witness theo goal vào sản phẩm có opt-in**, kiểm finite full-enumeration parity/alternative route/actor switching rồi đo multi-goal. Chưa cần production AND–OR hay rewrite planner. Hiện CLI production vẫn dùng FIFO; không quảng cáo prototype như tính năng đã giao.

## Ranking thực dụng khi P overlap

**C-first là lựa chọn chính cho câu hỏi “đi đường nào với ít công sức”.** P và impact có thể bổ sung ngữ cảnh khi có basis phù hợp; chúng không chặn việc dùng một witness có C. Strict Pareto giữ vai trò đối chiếu quan hệ ưu thế, không phải tiêu chí bắt buộc phải loại được candidate mới có khuyến nghị.

Control mới dùng native three-route fixture: đặt mọi conditional interval thành [0,1] trong **synthetic test**, Pareto giữ cả ba, native Top-K vẫn xếp C=[2,5,5] và đề xuất C=2. Không siết interval hoặc thay bằng midpoint. Đây là xác nhận policy đã có, không phải gán P=[0,1] cho SEAMLESS hay một thuật toán ranking mới.

Để tái lập global policy bằng CLI, dùng lệnh trong [iteration13](ITERATION-13.md), **bỏ `--assumptions ...machine-identity-assumptions.json`**, thay bằng `--scenario-policy seamless-standard-v1` và chọn output-dir mới. Có thể bỏ `--evaluation-mode scenario` vì profile đã chọn mode. Với FIFO/budget trên, dự kiến12truncated cells; để tái lập queue experiment, dùng [harness nghiên cứu](evidence/probe_goal_queue.txt), không gọi đó là production.

Week4 native chạy hai lần:36PASS/2NOT_EXECUTED/0FAIL, frozen semantic giữ nguyên. Append acceptancev15, v14/numeric/catalog/history giữ bytes; hai source-authorityv13 vẫn strictPASS vì source thuộc scope các authority đó không đổi. Bộ selected ban đầu35PASS; control ranking lần đầu sai representation kỳ vọng float thay vì rational string, đã sửa fixture assertion, không sửa engine. **Final clean `48c3dee6`:570/570 selectedPASS/156,60s/zero skip**. [Closeout/JUnit](evidence/iteration-14-closeout.json) kiểm current70sourcepins/127v15pins và byte equality với native source capture. Scope comparator xác nhận nguyên public query của FIFO và queue prototype giống hệt, SHA513b881939d642805ec654b433a096b8044bacd8f6e89f47d8972324294c1eec, không chỉ normalized subset. Mọi jobs đã complete.

**Không làm tiếp:** thêm xác suất tùy tiện để Pareto trông đẹp; coi assumption là observation; gọi truncated là unreachable; mở rộng session thiếu data khi chưa chặn demo. **Làm tiếp:** queue ưu tiên witness, rồi giảm preparation/serialization theo profile. Quy tắc giả định phải hỗ trợ câu trả lời có điều kiện, không làm sản phẩm tê liệt.
