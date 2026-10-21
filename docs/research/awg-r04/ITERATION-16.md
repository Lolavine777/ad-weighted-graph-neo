# Một can thiệp thật: cắt hết đường mẫu, cả hai nguồn vẫn tới DA

**Đã kiểm chứng một khuyến nghị từ inventory trên full SEAMLESS: bỏ OLLIE_LONG khỏi Domain Admins cắt2/2programs cũ, nhưng cả hai nguồn vẫn tới DA qua DENA_WILLIAM với C tìm thấy1.** Sản phẩm đã phân biệt đúng hai đại lượng; bản tóm tắt nay trình bày rõ quyền đã thử sửa và exposure còn lại. [Kết quả đọc được](examples/remediation-defender-brief.md) · [JSON evidence](evidence/iteration-16-remediation.json).

## Đo cái quan trọng

Dùng **nguyên hai public DA queries** của iteration15, kiểm exact query hashes từ full audit gzip; không đổi foothold, assumptions, C profile hoặc budget để làm case dễ hơn. Một machine identity FINWVIR và một User OLA_CARSON là hai compromise độc lập, cùng context FINWVIR. Full graph3.370nodes/56.367edges, standard scenario profile, ba techniques reset/activation/membership, max_paths1/max_steps3/max_expansions6000/query.

Native inventory sinh4candidates. Chọn candidate quan hệ được executor hỗ trợ, ưu tiên observed binding coverage rồi stable ID: **MemberOf của OLLIE_LONG→Domain Admins**. Không viết sẵn cạnh hoặc path vào truy vấn. Đây là thứ tự chọn thí nghiệm, không phải bằng chứng candidate tối ưu hoặc chi phí defender thấp nhất.

| Kết quả | Trước can thiệp | Sau can thiệp |
| --- | ---: | ---: |
| Cặp nguồn–DA có witness | 2/2 | **2/2** |
| Danh tính trung gian trong witness | OLLIE_LONG | **DENA_WILLIAM** |
| C tìm thấy cho mỗi cặp | 1 | **1** |
| Programs cũ bị cắt qua replay | — | **2/2 (100% corpus đã trả về)** |
| Programs mới tìm qua rediscovery | — | **2** |
| Cặp chứng minh bị ngắt | — | **0/2** |
| Cặp chưa xác định reachability sau sửa | — | **0** |

Cả hai query vẫn truncated bởi max_paths1; positive witnesses xác nhận reachability dù enumeration chưa đầy đủ. Native minimum proof không có; không gọi C1 là minimum toàn graph hoặc khẳng định effort không thể tăng ở mọi đường. `effort.status=incumbent`, không có proven numeric delta. P/I không thêm mới. Membership edit là counterfactual trên effective graph, raw graph/facts giữ nguyên; không tác động AD thật.

Native `run_remediation` đã chạy replay, rediscovery và verifier tái thực thi, **cả hai after cells được chạy**, không timeout/error/unrun. Native remediation+verification214,97s, setup/inventory62,97s trong một lượt; không có speedup claim. Full package375.800.973bytes, giữ lossless gzip10.622.371bytes; CRC/byte-count/SHA được kiểm riêng. Bốn outputs lớn giữ nguyên byte qua gzip kèm storage index khi thiếu đĩa; không bỏ audit/raw/captures.

## Oracle độc lập và baseline đơn giản

[Oracle](evidence/check_guided_remediation_raw.txt) chỉ dùng Python stdlib đọc sáu raw files, kiểm manifest và raw ACE/member locators; không import parser/generator/evaluator/cost compiler AWG. Cả4native witnesses trước/sau đều có direct GenericAll của đúng source trên User trung gian và raw User→DA membership; after không dùng membership đã bỏ. Đếm độc lập một reset work unit mỗi witness.

Trong **tiểu bài toán đã condition** gồm direct GenericAll(source, enabled User), reset+activation gộp C1 và direct User→DA membership C0, mỗi nguồn có **4route trước/3route sau**:8→6routes trong subset này, giảm25%. Không coi8route này là toàn bộ native programs. Con số100% ở bảng trên chỉ có denominator2programs đã lấy mẫu bằng max_paths1.

| Cách giải cùng tiểu bài toán direct đã condition | Trước | Sau | Giới hạn |
| --- | --- | --- | --- |
| BFS trên projection | Tìm route2hops, C1 | Tìm route khác2hops, C1 | Chỉ tối thiểu hop |
| Weighted Dijkstra, reset+activation1/membership0 | MinimumC1 | MinimumC1 | Minimum **của projection này** |
| Native planner và counterfactual verifier | Witness3actions/C1 | Witness thay thế3actions/C1 | Best found dưới caps, có typed identity/context/provenance |

**Weighted graph đơn giản đã đủ cho phần direct/additive này.** Không dùng phép đo trên projection nhỏ để tuyên bố native nhanh hơn hoặc vượt BloodHound. Phần cần bảo vệ của AWG là các semantics/prerequisites/identity switching/shared-work và kiểm chứng can thiệp trong scope đã công bố; không phải mọi case đều cần full stateful planning. Fresh BloodHound CE và benchmark toàn catalog chưa chạy trong iteration này. Không biết approach mentor nên không gán quan điểm cho mentor.

## Cải thiện nhỏ trong sản phẩm

`scripts/exposure.py` nay đưa outcome từ **package đã verify** vào brief. `scripts/defender_brief.py` hiển thị mô tả edit có labels, programs-cut denominator, reachable trước→sau, cặp ngắt, cặp chưa kết luận và programs mới. Ví dụ thực: **“Cắt2/2programs; cặp còn reachable2→2; chứng minh ngắt0/2; tìm lại2programs mới.”** Giữ ranking cũ và đọc được old summary không có outcomes. Không đổi planner, cost, pruning, remediation executor/verifier hoặc source authority.

86selected checks ban đầu PASS/24,59s gồm integration output, bounded-baseline bypass, CLI/exposure, remediation/discovery/reuse và goal-guided bindings. Một control mới xác nhận cắt100%old corpus nhưng brief vẫn báo1→1reachable/0disconnect/newbypass; old summary vẫn render. **Final clean `986c278f89699bf9336a8e2029af6dee1206e932`:86/86selectedPASS/25,21s/zeroskip**; [closeout/JUnit](evidence/iteration-16-closeout.json). Hai lượt86overlap, không cộng hoặc gọi whole-suite.75native sourcepins đối chiếu actualGitobjects/currentsource,127v16pins exact; strictauthority14/Ruff3files/contract2fixturesPASS, chỉ historicalR03ZIPlinkgap. Mọi native/verifier/oracle/test jobs complete. Không thay engine/numeric/history; finaldescendant chỉdocs/evidence. Các75native source pins/127acceptancev16pins không chứa hai presentation scripts; giữ exact source bytes và các history/numeric/catalog. Không tạo acceptance successor chỉ vì thay lời trình bày.

## Khuyến nghị tiếp theo

**Không coi bỏ riêng membership OLLIE là biện pháp đủ cho hai footholds này.** Kiểm các quyền GenericAll của nguồn trên các User có DA entitlement và nguồn kế thừa của chúng; inventory/selection frequency không thay thế counterfactual. Chưa có basis chi phí vận hành để kết luận tập sửa tối ưu.

MVP hiện có một chuỗi demo hoàn chỉnh: foothold→auto goals/witness/C→mined intervention→replay→đường thay thế→khuyến nghị có giới hạn. Khi quota ít, ưu tiên đóng gói/bảo vệ chuỗi này và phạm vi original requirements; dừng mở catalog/framework. Chưa đủ evidence cho AND–OR rewrite, global minimum hoặc scan toàn domain. Nếu còn một việc kỹ thuật: baseline BloodHound trên cùng snapshot/query semantics; nếu môi trường không hỗ trợ, trình bày rõ reduced projection comparator ở trên.

Native captures sạch tại `09686f1c66944b7c5fa51c77f29a785535729632`. [Harness chính xác](evidence/run_guided_remediation.txt): đặt cạnh thư mục checkout tên `repo`, dùng môi trường Python3.14 và snapshot/raw theo README; chạy trong output namespace mới. `check_guided_remediation_raw.txt` hỗ trợ witness plain/gzip. Full generated captures local, bounded evidence và brief publish cùng PR298; không sửa main/develop/parent hoặc merge.
