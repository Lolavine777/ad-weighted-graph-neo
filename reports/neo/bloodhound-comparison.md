# Đối chứng BloodHound CE trên SEAMLESS và WRAITH

Cập nhật sau mốc bàn giao `5c6f7c2`: [bản sửa LocalGroup](localgroup-fix.md) đưa neo lên 22/24 cặp.
Số liệu bên dưới giữ nguyên lượt đối chứng trước sửa để làm baseline.

Đã chạy BloodHound CE thật ngày 22/10/2026 trên Docker Desktop local, từ `main@6d90f78`.
**BloodHound có đường cho 22/24 cặp duy nhất; neo có witness cho 20/24.**
Neo giúp diễn giải hành động, điều kiện và công sức, nhưng lượt này không chứng minh khả năng tìm đường hay chọn C tốt hơn BloodHound.
Kết quả bất lợi cho neo và bypass sau can thiệp được giữ nguyên.

## Scope và môi trường

Giữ nguyên [query pack đã chốt](bloodhound-query-pack.json): 3 User và 2 Computer/dataset, hash seed `neo-decision-v1`, hai đích DA/EA; thêm cả ba máy WRAITH có session.
Không đổi cohort sau khi xem kết quả.
Đây là khảo sát khám phá trên dữ liệu từng được xem, không phải blind test hoặc mẫu đại diện toàn miền.
EXTDC01 xuất hiện ở hai nhóm: 26 lượt theo nhóm, 24 cặp duy nhất.
Mỗi lượt chạy cả query cấu trúc và query loại User disabled, tổng 52 request tới `POST /api/v2/graphs/cypher`.
Các kết quả không có đường đều được xác nhận rỗng bằng chính query đó trên Neo4j của CE; không dùng BFS nội bộ thay BloodHound.

- CE `9.8.0`, Neo4j `4.4.42`, PostgreSQL `16-alpine`; giữ nguyên cả ba image digest trong compose.
- Hai project mới: `neo-bh-seamless-20261022` và `neo-bh-wraith-20261022`, mỗi project có hai volume riêng, không reset volume.
- SEAMLESS dùng API/HTTP/Bolt tại `28080/27474/27687`; WRAITH tại `38080/37474/37687`, chỉ bind loopback.
- Stack cũ trên `18080/17474/17687` và mọi database/volume cũ được bảo toàn.
- Raw SEAMLESS: 6/6 file đúng checksum; adapter CE bảo toàn 3.369 records, 53.040 ACE, 13.324 memberships, 2.816 containment và 11 local rights.
- Raw ad_sampledata: 31/31 file đúng manifest; CE chỉ upload 12 file prefix `20240305111414` của WRAITH, không upload hai export còn lại.
- Importer neo dùng các record ngoài miền đã quan sát trong corpus để giữ boundary identity, không lấy quan hệ ngoài export WRAITH.
- Snapshot, request, scenario policy, techniques và budget được dựng lại; request/scenario/cohort khớp pack cố định.
Engine, parser, preset và bảng C không đổi trong lượt này.

Phía neo giữ tối đa 10 chương trình/query, 12 bước semantic, 4.096 expansions và Top-3 theo C; witnesses qua native replay.
Phía BloodHound dùng custom scoped shortestPath tối đa 12 graph hops, không đại diện toàn bộ quan hệ/tính năng BloodHound.
**12 graph hops khác 12 bước semantic.**
SEAMLESS dùng `neo-standard-v1`: nhóm thiếu thuộc tính security được giả định là security group, kể cả DISTLIST; query CE ở đây chỉ kiểm cấu trúc và User disabled.

## Đối chiếu graph trước khi so đường

Chuẩn hóa GUID hoa/thường và alias SID well-known theo đúng miền, giữ danh sách alias và kiểm va chạm; không nhập hai miền làm một.
Các con số dưới đây là tập triple đã khử trùng theo `(source, kind, target)` trong scope, không phải tổng số cạnh CE.
Inventory nguyên bản, inventory theo miền từ query pack và chênh lệch từng triple được giữ riêng.

| Dataset | ID neo có đối ứng CE | Type/enabled lệch | Triple chung | Chỉ neo | Chỉ CE, hai đầu thuộc neo |
| --- | ---: | --- | ---: | ---: | ---: |
| SEAMLESS | 3.370/3.370 | 0/0 | 56.343 | 13 | 0 |
| WRAITH | 149/150 | 1/1, cùng một boundary User | 751 | 7 | 6 |

SEAMLESS có đủ 3.370 node lõi của neo trong CE; bốn node CE bổ sung là `ADLocalGroup` do adapter/schema CE tạo.
13 triple chỉ neo đều là self-ACE: 10 GenericAll và 3 WriteDacl; CE lọc các cạnh tự trỏ này.
Tất cả 2.593 primary-group memberships có trong cả hai graph; không có chênh lệch MemberOf sau chuẩn hóa.
Không có chênh lệch type/enabled trên các node chung.

WRAITH có 933 node CE mang objectid, trong đó 160 node thuộc sáu loại lõi, còn lại gồm Container, AD CS, LocalGroup và stub.
3.350 triple CE trong các loại quan hệ đã chọn có ít nhất một đầu ngoài tập node neo; chúng không bị xóa khỏi database hoặc query CE.
Khác biệt còn lại được phân loại như sau:

- Bốn self-ACE chỉ neo: 1 GenericAll và 3 WriteDacl.
- Ba AdminTo chỉ neo là cạnh suy diễn membership từ BM, XADMIN, DRAGON tới EXTDC01; CE giữ đường qua nhóm thay vì materialize ba cạnh này.
- Bốn AdminTo chỉ CE: TRUSTER và DA tới EXTCA01/UNCON.
  Raw `LocalGroups[].ObjectIdentifier` dùng dạng `<ComputerSID>-544`; `_group_sid` của neo chỉ nhận SID builtin đầy đủ hoặc hậu tố `-S-1-5-32-544`, nên chưa nhận dạng bốn quyền này.
  Đây là hạn chế nhập liệu/inference thật của neo, không phải BloodHound cấp quyền sai.
- Hai MemberOf chỉ CE là Domain Users/Domain Computers tới Authenticated Users, do CE bổ sung; toàn bộ 51 primary-group memberships raw đã có ở cả hai phía.
- Boundary JD@PHANTOM.CORP có type User và enabled=true trong corpus neo; CE chỉ có Base stub, enabled thiếu, vì chỉ nhận export WRAITH.
- Neo còn boundary Domain GHOST từ corpus, CE có CHILD.WRAITH.CORP từ Trusts và 11 well-known principals bổ sung.
  Không coi các boundary/stub khác nhau là node parity hoàn toàn.

Những khác biệt này không làm đổi node nguồn/đích đã chọn.
Riêng thiếu AdminTo giải thích trực tiếp hai kết quả TRUSTER bất lợi cho neo.
Không vá parser để cải thiện số liệu đối chứng.

## Kết quả trên cohort cố định

| Nhóm | Neo có witness | CE cấu trúc | CE loại User disabled | C neo tốt nhất đã tìm |
| --- | ---: | ---: | ---: | --- |
| SEAMLESS chính | 10/10 | 10/10 | 10/10 | 1–5 |
| WRAITH chính | 6/10 | 8/10 | 8/10 | 0, 2, 3 |
| WRAITH session | 6/6 | 6/6 | 6/6 | 2 |
| Khử trùng | **20/24** | **22/24** | **22/24** | Hai cặp C=0 là XADMIN đã có quyền |

TRUSTER có đường CE `AdminTo → UNCON → HasSession → BM → MemberOf → DA/EA`.
Neo không thấy đường vì thiếu cạnh AdminTo ở trên; không giải thích kết quả này bằng budget.
TARGETCOMPUTERC không có đường ở cả hai phía trong custom scope.
Neo chặn `computer_actor_authenticated` vì nguồn chỉ có quyền local admin; đây không phải chứng minh máy an toàn ngoài scope.
Không có query neo lỗi, Unknown attempt hoặc âm tính vì hết expansion cap.
Các ca thành công đều chạm giới hạn 10 chương trình; SCOTTY_HARTMAN→EA còn chạm 12 bước.
Vì vậy C vẫn là **best-found**, chưa phải minimum toàn cục.

### Ánh xạ C, không lấy số cạnh làm công sức

[Summary từng cặp](bloodhound-live-results.json) giữ action mapping, C, timing, giới hạn và hash evidence.
Chỉ chấm C có điều kiện cho 21/22 đường CE trả về khi ánh xạ được sang hành động tương ứng theo `neo-c-v1`:
MemberOf có sẵn C=0; reset User và xác thực C=1+0; GenericAll lên Group để thêm actor C=1; WriteDacl lên Group để cấp GenericAll rồi thêm actor C=2+1; thực thi admin C=1; lấy và dùng credential session C=2.
Các điểm này dùng cùng giả định scenario, không phải điểm do BloodHound cung cấp hoặc số đo khai thác thực tế.

Đường CE ITSWWEBS→DA đi qua GenericAll trên Computer TSTWVIR trước khi dùng quyền của máy.
Catalog cố định không có hành động tương ứng biến GenericAll trên Computer thành danh tính mạng dùng được; để C trống, không tự lấy ba cạnh GenericAll làm C=3.
Neo có một đường khác qua các User với C=2; đây là ví dụ ích lợi của việc nêu rõ hành động và giới hạn mô hình, không phải lỗi BloodHound.
Hai đường TRUSTER có action mapping C=3 dưới giả định admin execution/session dùng được từ raw, dù neo chưa nhập được cạnh mở đầu để tự tìm chúng.

Với BENNY_LONG→EA và EVAN_LOTT→EA, đường shortestPath CE trả về ánh xạ C=5 trong khi neo tìm được C=4.
Kiểm thêm allShortestPaths trên chính hai cặp đó: mỗi cặp có đủ 7 đường đồng hạng 6 hops, gồm 6 đường C=4 và 1 đường C=5, không bị cắt ở limit 1.001.
**BloodHound cũng có shortest path C=4; không dùng tie tùy ý để tuyên bố neo cải thiện lựa chọn.**
Bộ cohort không thay đổi; kiểm tie là chẩn đoán bổ sung sau khi thấy chênh C.

### Thời gian ghi nhận

Median request CE loại User disabled lần cuối: SEAMLESS 7,88 ms, WRAITH chính 5,78 ms, session 5,11 ms.
Median `query_seconds` neo tương ứng: 7,13 s, 0,216 s, 0,252 s, gồm tìm nhiều chương trình, rating và compact witness/native replay.
Đây là các lượt local có cache đã ấm, không phải benchmark tốc độ: một shortest path khác tối đa 10 chương trình semantic và replay, budgets khác đơn vị.
Lần chạy thăm dò, request/response cuối và timing riêng từng request đều được giữ trong evidence; không chỉ giữ số nhanh nhất.

## Remediation nhỏ trên WRAITH

Ba can thiệp được thử **độc lập**, mỗi lần bắt đầu từ graph nguyên vẹn và cùng foothold ban đầu, tìm mới tới cả DA và EA.
Đây là sửa graph mô phỏng trên database thí nghiệm, không thực thi thay đổi trên Active Directory.
Mỗi query khởi tạo lại foothold; không mô phỏng credential đã bị lấy từ trước, và kết thúc session không được coi là tự thu hồi credential đã đánh cắp.
Neo dựng lại facts theo graph đã sửa và replay witness mới; CE chạy lại shortestPath qua API, không chỉ kiểm đường cũ.

| Can thiệp | Neo sau can thiệp | BloodHound sau can thiệp | Diễn giải |
| --- | --- | --- | --- |
| Gỡ RODCMANAGER→Administrators | Vẫn tới DA/EA, C=3 | Vẫn tới DA/EA | Bypass AdminTo trực tiếp lên EXTDC01 → session BM → DA/EA |
| Bỏ EXTCA01→BM HasSession | Không tới cả hai, 3 expansions/đích, không truncated | Không có đường cả hai, API 404 và Neo4j xác nhận rỗng | Chặn nhánh session trong local-admin-only scope |
| Gỡ BM→DA, nguồn EXTCA01 | EA vẫn C=2; DA có bypass C=5 | Còn đường tới cả hai; DA qua EA→WriteDacl→DA | Cắt membership DA chưa loại quyền ACL từ EA |

Kết quả RODCMANAGER khác báo cáo cũ trong `transfer-brief.md`: báo cáo đó dùng scope identity/directory, không bật host/session.
Với scope host/session đã chốt ở đây, kết luận “gỡ membership là ngắt nguồn” không còn đúng.
CE journal lưu cạnh và toàn bộ properties trước mỗi lần DELETE, restore bằng MERGE, so digest toàn bộ triple+properties sau khôi phục.
Cả ba lần khôi phục đã được xác nhận; internal relationship ID có thể đổi do tạo lại cạnh.
Test lỗi DELETE trước/sau commit bảo đảm restore không nhân đôi cạnh khi trạng thái commit chưa rõ.

## Neo giúp gì, còn hạn chế gì

Neo làm rõ đường cấu trúc cần những hành động nào, đâu là membership đã có, công sức C nào được chấm và giả định nào chưa được quan sát.
Native search/replay sau can thiệp phát hiện bypass với cùng foothold, và cho thấy chi phí một đường thay thế có thể tăng từ C=2 lên C=5.
BloodHound cũng phát hiện các bypass này bằng query lại; remediation không phải khả năng riêng của neo.

Lượt này không có bằng chứng neo tìm được nhiều cặp hơn, có C minimum tốt hơn hoặc nhanh hơn BloodHound.
Ngược lại, CE phát hiện thêm hai cặp do importer neo chưa hiểu một dạng LocalGroup ID.
Phạm vi sáu loại node và catalog hiện tại của neo hẹp hơn CE; chỉ quy đổi các quan hệ đã chọn không đánh giá toàn bộ AD CS, delegation hoặc những khả năng khác.

Preset `host-compromise` hiện là **local-admin-only**, chưa khai báo danh tính mạng tài khoản máy.
Một số mô tả hiện có ghi “local admin/SYSTEM” là quá rộng: không nên diễn giải đây là mô hình SYSTEM đầy đủ.
Lượt này giữ nguyên preset/engine, không tự cấp machine identity để tăng tỷ lệ tìm đường.
Session còn mới, credential truy cập được/dùng lại được và xác thực thành công đều là giả định tĩnh của scenario.
[Tài liệu HasSession của SpecterOps](https://bloodhound.specterops.io/resources/edges/has-session) cũng nêu session không bảo đảm có credential dùng lại được.
[Cypher chính thức](https://bloodhound.specterops.io/analyze-data/explore/cypher-supported) hỗ trợ shortestPath/allShortestPaths; query scoped ở đây không đại diện cấu hình đầy đủ của sản phẩm.

## Tái lập và evidence

Từ repo root, cài Python/dependencies theo README, có Docker daemon và hai bộ raw đúng manifest:

```sh
BH_RUN_TAG=20261022-r2 sh reports/neo/reproduce-bloodhound.sh
```

Dùng tag mới, output directory mới và sáu cổng trống như script khai báo.
Script từ chối project/volume đã tồn tại, kiểm cổng trước khi tạo container, kiểm cohort trước khi query và không dùng `--reset-volumes` hoặc `down -v`.
Nếu cổng đang được chính lượt này dùng, có thể dừng riêng hai project thí nghiệm bằng `docker compose -f deploy/bloodhound/compose.seamless.yml -p PROJECT stop`; volume và stack cũ vẫn giữ nguyên.
Không đổi cổng của stack đang có để nhường chỗ.

Evidence local: `reports/generated/bh-live-20261022/`, khoảng 150 MB, không commit raw hoặc generated.
Dùng `live-seamless-final/`, `live-wraith-final/`, `live-remediation-final/` làm kết quả cuối; các lần thăm dò/bản runner trước sửa restore được giữ riêng với hash của chính chúng.
`native/*/cells.jsonl` có 26 record đầy đủ newline và checksum; `inputs/` giữ snapshot/import audit/CE conservation; các thư mục live giữ inventory, parity, response, query và timing.
`primary-groups-final.json` giữ audit 2.593/51 primary memberships; `docker-images-mounts.txt` và log CE giữ image/mount/ingest/analysis evidence.
`evidence-manifest.json` pin checksum từng file local; summary version trong Git pin hash của manifest và các file cốt lõi.

Kiểm thử liên quan: **151 pass**, Ruff pass; gồm runner, raw selection/checksum, alias/path decoding, endpoint isolation, restore khi lỗi commit, import/parser/inference, host/session và neo decision.
`sh -n reports/neo/reproduce-bloodhound.sh` và `git diff --check` pass.
Nguyên recipe đã chạy E2E với tag `20261022-verified`, exit code 0, kể cả khi môi trường ban đầu cố ý có URL/auth của stack cũ.
Lượt tái lập xác nhận cùng 26 kết quả neo, 52 trạng thái CE, số lượng parity và ba kết quả remediation.
Evidence lần tái lập ở `reports/generated/bh-live-20261022-verified/`; hai project `neo-bh-{seamless,wraith}-20261022-verified` đang chạy trên các cổng nêu trên.
Hai project của lượt chính và project SEAMLESS của lần smoke bị ngắt đã được dừng; tất cả volume của chúng vẫn được giữ.
Chưa chạy full suite; lỗi ràng buộc catalog/taxonomy lịch sử đã biết được giữ ngoài scope, không tuyên bố full suite xanh.
