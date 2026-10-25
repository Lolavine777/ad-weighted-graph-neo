# AWG neo: baseline và hướng nghiên cứu

> **Hướng dẫn hiện hành:** bắt đầu từ [README](../README.md) và [viewer](../web/neo-viewer/README.md).
> Tài liệu này giữ các mốc nghiên cứu; số liệu ở mỗi mốc gắn với code, dữ liệu và scope khi đó.
> Checklist đóng gói trước khi viết luận nằm tại [issue #4](https://github.com/Lolavine777/ad-weighted-graph-neo/issues/4).

## Phạm vi

Neo là repo cá nhân có lịch sử mới, được dựng từ nội dung upstream `main` ngày 2026-10-21.
Rework và đơn giản hóa trong planner hiện hữu; không rewrite parser hoặc bỏ semantic checks.
Hai use case là một foothold tới tài sản quan trọng và nhiều compromises độc lập để khảo sát rủi ro, can thiệp, rồi tìm đường thay thế.

## Migration

- Source chỉ đọc: `https://github.com/nairyuuu/ad-weighted-graph`.
- Đích private: `https://github.com/Lolavine777/ad-weighted-graph-neo`.
- `main`: `49dfa2a78614220dfd092b0fd3e5c585992a0484`.
- `develop`: `ba3fcaa8f6d85c181d8a7f657eae112607fd22cb`.
- Cùng tree: `dde43cad3e8e91314bd5ecc4dc1194ac2295596a`.
- Clone upstream đầy đủ để kiểm tra; neo dùng root commit mới theo lựa chọn của chủ repo, không nhập các commit hoặc nhánh PR cũ.
- Không có LFS pointer hoặc submodule trong baseline.
- `upstream` trong checkout neo có push URL `disabled://upstream-read-only`; `remote.pushDefault=origin`.
- Neo được kiểm private và không có ref trước lần push đầu; các lần sau chỉ push fast-forward.

Tám file log evidence vốn được upstream track nhưng khớp `.gitignore` đã được đưa lại nguyên bytes vào commit tiếp theo root commit.
Không có thay đổi nào được ghi vào working tree hoặc push tới repo gốc.

Gitleaks 8.30.1 được tải từ release chính thức và kiểm checksum binary trước khi chạy.
134 cảnh báo ban đầu đã được kiểm tra: 129 source/file hashes, bốn định danh `host-access` có hash và một dòng văn bản về auth context.
Đó là false positives; không có credential thật được nhận diện trong snapshot chuyển sang neo.
Đây là kết quả quét snapshot hiện tại, không phải bảo đảm cho mọi dữ liệu hoặc thay đổi về sau.

## Dataset trên máy

Raw và derived outputs vẫn ở local, được ignore bởi Git theo quy ước dữ liệu hiện hữu.

| Dataset | Cách lấy và xác minh |
| --- | --- |
| SEAMLESS | Tải public archive tại commit pin trong `scripts/download_seamless.py`, xác minh archive SHA-256 và manifest sáu file |
| NORTH | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| NORTH_CE_PYTHON | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| ad_sampledata | Sao chép dữ liệu local và archive; archive SHA-256 khớp data inventory |
| telemetry | Sao chép CSV local và xác minh manifest `telemetry-raw-v1.json` |

Đã lấy 60 file, 23.577.814 bytes, không tính README.
`data/processed/neo-datasets.json` ghi checksum từng file và cách lấy trên máy migration.
Mọi file sao chép đều được so hash với bản nguồn.
Ba archive NORTH/NORTH_CE_PYTHON/ad_sampledata còn được so với hash công bố trong [data inventory](research/data-inventory.md).
Không khẳng định đã tải mới từ Internet các dataset được sao chép local.
Một clone neo mới chỉ tự tải được SEAMLESS bằng runner; các dataset phụ cần lấy từ kho dữ liệu đã kiểm checksum trên máy này hoặc nguồn được data inventory chỉ định.
Telemetry là corpus độc lập; không entity-join với SEAMLESS hoặc coi là observed activity trên topology này.

## Chạy baseline

Từ repo root, sau bước cài đặt trong [README](../README.md):

```sh
.venv/bin/python -m scripts.neo_baseline --output-dir reports/generated/neo-run-001
```

Runner từ chối ghi đè directory đã tồn tại.
Snapshot có 3.370 nodes và 56.367 edges.
Máy nguồn là SID kết thúc `-4157`; Domain Admins được tìm theo domain SID và RID 512.
Capability `computer_usable_identity` được khai báo tường minh tại context chính máy đó với provenance scenario, không suy ra từ host control.
Lượt baseline lịch sử dùng `seamless-standard-v1`; C-only profile là `reset-activation-c-v2`.
Runner hiện mặc định `neo-standard-v1`; dùng `--scenario-policy seamless-standard-v1`
để tái lập policy của lượt lịch sử này.
Chỉ cho phép `scenario_reset_password`, `acquire_reset_identity` và `propagate_group_entitlement`.
Budget là một witness, ba semantic steps và 6.000 expansions.

`query.json` giữ assumptions, profile, source, context và goal chính xác.
`snapshot.json` giữ structural graph cùng facts và code version.
`fifo.json`/`goal_guided.json` giữ full audit, attempts, C ledger, witness và engine guarantees.
`summary.json` ghi các lệnh CLI, phiên bản Python/platform, thời gian, input hashes, semantic hashes, native replay và parity API/CLI.
Thời gian CLI bao gồm load/validate snapshot, search, ranking, serialize và ghi output; thời gian chuẩn bị được ghi riêng.
Không dùng runtime của phiên trước làm số đo của máy này.

FIFO ở cap này chưa tìm witness, không chứng minh no-path.
Guided tìm một conditional witness C=1 sau 4.995 expansions, nhưng bị candidate cap và không chứng minh minimum.
C=1 là union-work ordinal của reset/activation; P/I vẫn chưa chấm.
`goal_guided` hiện là membership heuristic cho một số chain, chưa phải cost-guided search tổng quát.

## Cải tiến nhỏ và evidence

Không tìm thấy `AWG-v2-start.zip`, `AWG-neo-direction.md` hoặc patch tối ưu C cũ trên máy.
Không áp hoặc tái tạo patch đó dựa trên mô tả.
Profiling workload hiện tại phát hiện CLI gọi `wire()` lại trên kết quả mà `execute()` đã chuyển sang JSON-safe values.
Bỏ lượt duyệt thừa này là thay đổi một dòng trong CLI, giữ nguyên toàn bộ audit và định dạng kết quả.
Các phép đo và hash đối chiếu nằm ở [benchmark neo](../reports/neo/benchmark.json).
Không suy rộng kết quả của query này thành tốc độ cho mọi graph hoặc planner.

## Kiểm thử và evidence lịch sử

Fixtures cũ có một số giả định không còn phù hợp với ranh giới danh tính máy.
Các positive tests dùng scenario test riêng khai báo danh tính mạng và bind lại registry trước khi mô phỏng review; không chuyển numeric approval cũ sang context mới.
Queries lịch sử thiếu danh tính mạng vẫn phải bị chặn rõ ràng.
Evidence và numeric releases cũ giữ nguyên bytes.

Baseline integrity của code neo được sinh riêng trong `reports/neo/source-manifest.json`.
Các hash này kiểm thay đổi source hiện hành; không cấp numeric authority hay chứng minh kết quả lịch sử đúng với code mới.
Khi chủ động đổi source được pin, sinh lại baseline bằng công cụ đã cung cấp và chạy kiểm thử trước khi commit.
Không sửa checksum lịch sử để che drift.

## Chi phi C cho neo

Profile opt-in `neo-c-v1` dùng bảng công sức C cho hành động thay vì khai báo từng cặp reset của actor ban đầu.
C là **chỉ số công sức quy ước theo scenario**: dùng để so phần việc của các chương trình khả thi trong cùng phạm vi, không phải thời gian, xác suất thành công hay mức thiệt hại.
Giữ công thức mỗi work unit `C = T1 + T2 - 2`, với hai tiêu chí có trọng số bằng nhau theo lựa chọn thiết kế của neo:

- **T1 - độ phức tạp công cụ:** 1 là quy trình/công cụ chuẩn; 2 là cần tùy biến cách dùng hoặc cấu hình công cụ cho thao tác; 3 là cần nghiên cứu/triển khai mới.
- **T2 - công sức thao tác:** 1 là trao đổi đơn giản khi đã có đủ vật liệu; 2 là nhiều thao tác và xác minh thay đổi hoặc kết quả thực thi; 3 là xử lý/tính toán nặng.

T1 xét cách thực hiện, T2 xét phần việc thực hiện/xác minh; không đếm số câu lệnh, số gói tin hay số prerequisite để suy điểm.
Nhập tham số thông thường như đích hoặc credential chưa đủ để nâng T1 lên 2; mức 2 dự trù tùy biến quy trình/cấu hình ngoài thao tác chuẩn đã giả định cho action đó.
Trừ 2 đặt mức nền `(1,1)` về 0; mỗi mức tăng ở một tiêu chí thêm một điểm theo quy ước, không phải một đơn vị thời gian đo được.
11 action hiện hành chỉ dùng `(1,1)`, `(1,2)`, `(2,2)`, tương ứng C=0,1,2; mức 3 của thang chưa được gán trong profile này, còn tổng chương trình có thể lớn hơn 2.
Đây là các ước lượng được chọn cho neo từ rubric cũ, không chuyển trạng thái duyệt A/B hoặc xác suất lịch sử sang scope mới.
Nhãn metadata `estimated_expert_scenario` ghi loại cơ sở ước lượng, không chứng nhận đã có hội đồng chuyên gia độc lập.

### Lý do giữ các mức điểm

Bảng dưới chốt cách diễn giải `neo-c-v1` version `1.2.0`, ánh xạ đủ `OPERATIONS` trong [effort_profiles.py](../src/engine/ranking/effort_profiles.py), giữ nguyên giá và công thức.
Phần lý giải là phân tích của dự án có hỗ trợ LLM, đối chiếu tài liệu chính thức Microsoft ngày 24/10/2026.
**Nguồn mô tả đặc tính hành động và điều kiện áp dụng; T1/T2/C là quyết định của neo, không phải điểm được Microsoft xác nhận.**
T2=2 ở các thao tác thay đổi/thực thi dự trù cả thao tác và xác minh, kể cả khi một công cụ có thể gói chúng trong một lần gọi.

| Hành động / technique | T1 / T2 | C | Lý do chọn mức của neo | Giả định chính | Nguồn mô tả đặc tính |
| --- | --- | --- | --- | --- | --- |
| Reset mật khẩu: `genericall_reset_password`, `reset_target_password`, `scenario_reset_password` | 1 / 2 | 1 | Công cụ chuẩn, đổi mật khẩu rồi xác minh; quyền đầu vào khác nhau nhưng cùng họ công việc | Có quyền reset hiệu lực; policy chấp nhận; chưa tính việc chiếm quyền đó | [Set-ADAccountPassword](https://learn.microsoft.com/en-us/powershell/module/activedirectory/set-adaccountpassword?view=windowsserver2025-ps) |
| Dùng danh tính vừa reset: `acquire_reset_identity` | 1 / 1 | 0 | Xác thực chuẩn bằng credential vừa có, đặt ở mức sàn; không làm lại công việc reset | Đúng context, KDC tới được, danh tính được chấp nhận | [Kerberos và việc tái dùng ticket](https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-authentication-overview) |
| Thêm thành viên nhóm: `genericall_add_member` | 1 / 2 | 1 | Thao tác directory chuẩn, ghi membership rồi xác minh | Security group, quyền ghi và membership được phép; entitlement vẫn qua gate riêng | [Add-ADGroupMember](https://learn.microsoft.com/en-us/powershell/module/activedirectory/add-adgroupmember?view=windowsserver2025-ps) |
| Cấp WriteDacl: `genericall_grant_write_dacl` | 1 / 2 | 1 | Ước lượng một thao tác cấp quyền cố định bằng quy trình chuẩn khi đã có GenericAll | Quy trình cấp quyền sẵn có và quyền ghi hiệu lực; không tính lại quyền GenericAll | [Quyền AD](https://learn.microsoft.com/en-us/windows/win32/api/iads/ne-iads-ads_rights_enum), [cấu hình ACE](https://learn.microsoft.com/en-us/windows/win32/ad/setting-access-rights-on-an-object) |
| Sửa DACL để cấp GenericAll: `grant_new_object_right` | 2 / 2 | 2 | Dự trù tùy biến cấu hình ACE cho đích và xác minh quyền mới | Đã có WriteDacl; chọn đúng principal/quyền/phạm vi; không tính việc dùng quyền mới ở đây | [Quyền AD](https://learn.microsoft.com/en-us/windows/win32/api/iads/ne-iads-ads_rights_enum), [cấu hình ACE](https://learn.microsoft.com/en-us/windows/win32/ad/setting-access-rights-on-an-object) |
| Thực thi quản trị host: `obtain_admin_execution_on_host`, `scenario_winrm_admin` | 1 / 2 | 1 | Kênh quản trị chuẩn, xác thực và xác minh thực thi với quyền yêu cầu | Đã có authorization; kênh dùng được; WinRM admin cần execution context phù hợp | [WinRM: xác thực và quyền của phiên](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/winrm-security) |
| Phiên lệnh WinRM: `open_winrm_remote_session` | 1 / 2 | 1 | Cùng mức quy trình chuẩn và xác minh phiên lệnh; không tự cộng điểm theo mức đặc quyền | Endpoint cho phép; phiên chạy theo quyền danh tính, không tự cấp admin | [WinRM: xác thực và quyền của phiên](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/winrm-security) |
| Lấy credential từ session và xác thực: `use_session_identity` | 2 / 2 | 2 | Dự trù công cụ phù hợp vật liệu session, lấy danh tính tái dùng được rồi xác thực | Có host admin, session còn dùng được, credential truy cập được và được chấp nhận; không bao gồm vượt bảo vệ credential | [Credential Guard và giới hạn truy cập secret](https://learn.microsoft.com/en-us/windows/security/identity-protection/credential-guard/how-it-works) |

WinRM là ví dụ kênh chuẩn để giải thích hàng thực thi host; `obtain_admin_execution_on_host` vẫn dùng gate `admin_channel` trừu tượng, không mặc nhiên là WinRM hoặc tự xác nhận cấu hình dịch vụ.
Chênh T1 giữa hai hàng ACL là giả định về quy trình công cụ của neo, không suy ra từ tên quyền hoặc độ mạnh của GenericAll so với WriteDacl.
Cả hai đều có thể dùng API chuẩn; tài liệu không chứng minh thao tác thứ hai luôn khó hơn, nên giữ chênh lệch này như một giả định công khai của bảng giá, chưa coi là hiệu chỉnh thực nghiệm.
Tương tự, giá session chỉ áp dụng khi các gate cho phép; session có mặt không bảo đảm lấy được credential, và gặp cơ chế bảo vệ không có nghĩa tự tăng C để coi hành động khả thi.

### Cộng điểm và tránh cộng trùng

Với chương trình khả thi, `C(program) = sum(C(u) for u in U(program))`, trong đó `U` là hợp các work unit có ID duy nhất, không phải danh sách cạnh hoặc số bước.
[Resolver](../src/engine/ranking/resolver.py) tạo ID theo technique, actor, target và context gồm nguồn quyền, method, authentication/resource context, policy/scenario, kèm boundary và ledger version; [assessment](../src/engine/ranking/assessment.py) cộng mỗi ID một lần.
Cùng work unit được tham chiếu lại không tạo thêm điểm; khác actor/đích/context không tự gộp chỉ vì cùng technique hoặc cùng giá.
Gộp action trong một hàng bảng chỉ để diễn giải, không biến các technique ID khác nhau thành một work unit.
Không cộng riêng phần xác minh đã nằm trong giá action, hoặc tự thêm phí chuẩn bị chung; nếu một ledger khai báo shared preparation thì hợp work-unit IDs tính nó một lần.
Work unit chưa có giá hoặc overlap chưa giải quyết làm C thiếu, không tự nhận C=0.

Membership đã có qua `propagate_group_entitlement` là suy diễn quyền, không tạo work unit.
`acquire_reset_identity` vẫn là một active work unit C=0, phải qua semantic checks và vẫn được tính vào giới hạn work unit; điểm sàn không có nghĩa không làm gì hoặc không mất thời gian.
Thêm work unit mới có C>0 làm tổng tăng; thêm work unit C=0 hoặc dùng lại cùng ID không làm tăng tổng, nhưng có thể vẫn ảnh hưởng khả năng thực hiện và budget.

### Ví dụ đã có và giới hạn so sánh

- **Điểm bằng nhau:** S01 của [rubric review](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/d68b09a2f02c7895adb2f6462b59b6b51eff2052/reports/neo/rubric-review.md) có hai route khác nhau, mỗi chương trình gồm hai reset C=1 và hai activation C=0, cùng tổng C=2.
  Tie chỉ nói rubric chưa phân biệt công sức của hai chương trình, không nói chúng tương đương về cấu trúc hoặc mọi đặc tính thực tế.
- **Thêm việc có giá:** S02 cùng báo cáo có profile C=5 và biến thể cùng route thêm `genericall_grant_write_dacl` C=1 nên thành C=6.
  Đây là tính nhất quán của phép cộng trên phần việc công bố, không chứng minh thao tác thêm là cần thiết hoặc hai state tương đương.
- **Hai trường hợp C=0:** Q8 ở phần khảo sát SEAMLESS bên dưới có reset 1 + dùng danh tính 0 + membership passive 0 = 1, dù có hai active work units.
  T02 trong rubric review có entitlement sẵn nên không thêm work unit, tổng 0; cả hai khác hẳn C thiếu do action chưa được chấm.
- **Không cộng trùng:** [kiểm thử shared preparation hiện có](../tests/test_rating_resolver.py) cho hai action tham chiếu cùng preparation ID C=1, ledger giữ đúng một preparation C=1, không phải 2.
  Đó là minh họa cơ chế ledger chung, không bổ sung phí preparation vào neo; ngược lại, hai lần dùng session ở host/context khác nhau trong [ví dụ WRAITH đã công bố](../reports/neo/cost-sensitivity.md#ví-dụ-đảo-thứ-hạng-nhưng-không-thay-minimum) là hai work unit riêng, tổng C=4.

[Nghiên cứu rubric và JSON kèm theo](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/d68b09a2f02c7895adb2f6462b59b6b51eff2052/reports/neo/rubric-review.md) đã rà soát 9 cặp/30 summary, chưa có căn cứ đổi giá; đây là kiểm tính nhất quán có hỗ trợ AI, không phải 9 xác nhận thực nghiệm độc lập.
Giữ tổng cộng như một giả định thiết kế bán định lượng: C=4 không có nghĩa gấp đôi công sức thực tế của C=2, và thứ tự giữa các họ công việc khác nhau còn phụ thuộc bảng giá.
Chỉ so trực tiếp khi giữ cùng profile và scope/scenario thích hợp; khi đối chiếu các phương án của một bài toán cần cùng foothold, goal và context, giữ cả route và thành phần công việc để giải thích tie.
Top-K trong candidate set bị cap vẫn là best-found nếu thiếu proof; ví dụ synthetic tính từ cùng bảng giá kiểm được phép cộng, không tự xác nhận giá đúng hoặc chứng minh ưu thế BloodHound.

Scope là cùng miền, cùng authentication context, snapshot và scenario đã chọn.
Actor, nguồn quyền và đích hành động phải thuộc tập node trong miền đó, không phải boundary.
Giá áp dụng cả quyền qua nhóm, quyền vừa sửa và danh tính thu được giữa đường; việc cấp giá không cấp capability hay biến prerequisite Unknown/False thành True.
Goal vẫn phân biệt danh tính thuộc nhóm đặc quyền với quyền thực thi trên host.
Techniques ngoài bảng tiếp tục chưa chấm C, không tự nhận C=0.

API Python dùng `load_effort_profile("neo-c-v1")` và `bind_effort_profile(query, graph, profile)` tại `src.engine.ranking.effort_profiles`.
Batch/exposure nhận `--effort-profile neo-c-v1`.
Các profile reset cũ còn dùng được để tái lập benchmark; runner neo mặc định bảng C mới.
Thay đổi này mở coverage C; chưa đổi search, thêm P/I hay mở roaming context.

Ví dụ hữu hạn đã có trong [test neo C](../tests/test_neo_effort.py): quyền qua nhóm → reset → dùng danh tính → quản trị host có C=0+1+0+1=2; sửa DACL → reset → dùng danh tính → quản trị host có C=2+1+0+1=4.
[Độ nhạy đã công bố](../reports/neo/cost-sensitivity.md) chỉ reprice candidate set cố định, không xác nhận trọng số bằng đo công sức thực tế.

Kiểm tra đầu tiên với raw SEAMLESS đã kiểm manifest: baseline machine-to-DA giữ
witness C=1 sau 4.995 expansions và qua native replay/API–CLI parity.
Một query User có usable identity → host qua AdminTo, cùng scenario và goal
`admin_control`, giữ nguyên đường và 1 expansion: profile reset cũ không áp dụng,
`neo-c-v1` chấm C=1. Đây là cải thiện coverage trên một ca, chưa phải toàn SEAMLESS
hoặc cải thiện runtime. Các chain reset qua nhóm, ACL và đổi actor được kiểm riêng
bằng finite tests trong `tests/test_neo_effort.py`.
Ca AdminTo dùng source SID kết thúc `-1116`, host/context `-1000` trong miền SEAMLESS,
chỉ bật `obtain_admin_execution_on_host`, cap 100 expansions và ba steps.
550 test hồi quy engine/query/batch/scoring pass, gồm 23 test mới; lint, format,
repository và contract checks pass. Lượt full suite được dừng trước khi hoàn tất
do thời gian chạy các test lịch sử; không dùng lượt đó để tuyên bố full-suite pass.

## Trạng thái và việc còn lại

Các mục bên dưới ghi lại từng mốc nghiên cứu; hướng dẫn chạy hiện tại nằm trong [README](../README.md).
`neo_guided` và `neo_refine` đã có trong core; [pilot C-first](../reports/neo/cost-first-pilot.md) không được adopt vì giảm coverage trong budget.
[Đối chứng CE sau sửa LocalGroup](../reports/neo/localgroup-fix.md), [độ nhạy C](../reports/neo/cost-sensitivity.md) và [demo remediation WRAITH](../reports/neo/remediation-rediscovery-results.json) đã có kết quả.
[GoodHound](../reports/neo/goodhound-evaluation.md) bổ sung đánh giá công khai ngoài dữ liệu cũ: giữ riêng cohort âm và positive control, không gọi là blind holdout.

Phần còn lại để bàn giao khóa luận:

1. Hoàn tất [issue #4](https://github.com/Lolavine777/ad-weighted-graph-neo/issues/4): kiểm viewer trên trình duyệt thật, khép tình trạng tái lập GoodHound và chốt gói demo/revision. Viewer đã có kiểm hồi quy cho file nhập và đọc trực tiếp `results.json` của demo remediation; điều này không thay cho kiểm trực quan.
2. Thu hồi các helper GoodHound đang nằm trong evidence local và kiểm từ checkout mới; hiện repo mới có báo cáo/hash. Nếu chưa thu hồi được, ghi rõ ngoại lệ chưa tái lập đầy đủ khi bàn giao, không tự nhận đã kiểm lại.
3. Chuyển sang viết bài bằng kết quả đã có: giải thích C, đối chiếu CE cùng scope, phân biệt cắt đường mẫu với ngắt khả năng tiếp cận. UI đọc báo cáo offline; phần engine vẫn dùng CLI.

Giữ bảng `neo-c-v1` đã giải thích ở trên. Minimum-C trên dữ liệu thật và ưu thế tổng quát so với BloodHound chưa được chứng minh; không coi chúng là kết quả đã đạt hoặc tự mở thêm scope để đóng gói bản hiện tại.
Vì vậy chưa đáp ứng nguyên văn tiêu chí minimum-C từ node bất kỳ trong đề gốc.
Hướng luận văn là phân tích có xét công sức và kiểm tra biện pháp giảm thiểu; kỹ thuật/dataset mới, cải tiến search và backend UI là add-on sau bàn giao.

Để cập nhật integrity baseline neo sau một thay đổi source có chủ đích:

```sh
.venv/bin/python -c 'from scripts.research.scenario_rating_pack import write_source_manifest; write_source_manifest()'
```

Để đo lại thay đổi CLI, dùng snapshot/query do runner vừa tạo và một checkout baseline tách biệt:

```sh
git worktree add --detach /tmp/awg-neo-before e96c1c0
.venv/bin/python -m scripts.research.benchmark_neo_cli \
  --baseline-root /tmp/awg-neo-before \
  --query-dir reports/generated/neo-run-001 \
  --output-dir reports/generated/neo-benchmark-001 \
  --report reports/generated/neo-benchmark-001-summary.json
git worktree remove /tmp/awg-neo-before
```

Harness dùng `/usr/bin/time -l` trên macOS, ba trials mỗi variant/search-order, đổi thứ tự before/after giữa các trials và từ chối semantic hash drift.
Nó không thay source hoặc bỏ bớt audit fields.
Report ghi hash của query, snapshot và CLI source của hai variants.
Report đo trước khi commit implementation nên revision Git của variant after vẫn là root commit; hash CLI source phân biệt đúng code đã đo.

Kết quả ba trials xen kẽ mỗi variant/search-order trên macOS arm64, Python 3.14.7:

| Chế độ | Median wall trước | Median wall sau | Peak RSS trước | Peak RSS sau |
| --- | --- | --- | --- | --- |
| fifo | 5.506s | 4.596s | 978.1 MiB | 1051.5 MiB |
| goal_guided | 6.648s | 5.744s | 1141.5 MiB | 1142.1 MiB |

Cả 12 trials giữ nguyên hash của toàn bộ semantic output theo từng search-order, gồm witness, C, attempts, assumptions và guarantees.
FIFO nhanh hơn khoảng 16,5% và guided nhanh hơn khoảng 13,6% trên workload này.
Peak RSS FIFO tăng khoảng 7,5%; guided gần như không đổi.
Đây là tradeoff thời gian/bộ nhớ quan sát được; không phải cải thiện RAM hoặc speedup phổ quát.

## Xác minh bàn giao

Full suite trên commit sạch `1c52e18`: 3.618 passed, 8 skipped, 99 subtests passed trong 707,50 giây.
Các test converter/BloodHound runner với raw SEAMLESS: 47 passed.
Sau suite, bổ sung chính sách Git giữ nguyên byte của hai gói rating lịch sử trên Windows và mở rộng test checkout thực; các kiểm tra portability/source integrity pass.
Ruff check/format, yamllint, repository/contract checks và Docker Compose config validation đều pass.
Đã kiểm native replay cùng parity API/CLI ở đường dẫn bàn giao và giữ nguyên 665 blobs nghiên cứu/fixtures/dữ liệu mẫu của upstream.
Demo remediation synthetic cắt 50% programs, ngắt 0% source-goal pairs và giữ hai bypass; không suy rộng sang SEAMLESS.
Chưa chạy đối chứng BloodHound live mới hoặc chờ kết quả CI trên GitHub.
Kết quả tổng hợp ở [validation neo](../reports/neo/validation.json).


## Khảo sát 10 query SEAMLESS với neo-c-v1 (2026-10-21)

Đo tại `9ede3d8`, Python 3.14.7, trên snapshot 3.370 nodes/56.367 edges do `neo_baseline` vừa dựng từ raw đã kiểm manifest.
Chọn cohort chủ đích theo các cạnh có thật, không chọn theo kết quả search; đây không phải mẫu đại diện toàn miền.
Mọi nguồn được khai báo có usable identity tại đúng context; riêng Computer cũng là giả định compromise tường minh, không suy từ host control.
Dùng `seamless-standard-v1`, không thêm facts/assumptions thủ công, budget 1 witness/5 steps/6.000 expansions và technique scope ghi trong lệnh bên dưới.
Mục tiêu nhóm là usable-identity entitlement; host là admin control, riêng Q10 chỉ là remote command execution.
Thời gian là một lượt API gồm compile policy + bind C + query, dùng chung graph; không gồm snapshot load (1,072s), replay, CLI serialization hoặc ghi full audit.

| Query | Nguồn → mục tiêu (RID) | Scope | Witness / C đầy đủ | Expansions | Giây | Điểm vướng hoặc giới hạn |
| --- | --- | --- | --- | ---: | ---: | --- |
| Q1 | User KATRINA 1116 → host 1000 | AdminTo trực tiếp | Có / C=1 | 1 | 0,610 | Đạt goal dưới hai runtime assumptions; complete trong scope AdminTo |
| Q2 | User DENA 2799 → DA 512 | MemberOf | Có / C=0 | 8 | 0,433 | Membership đặc quyền đã có; không phải leo thang mới; cap 1 witness |
| Q3 | User OLA 1395 → DA 512 | Reset trực tiếp + đổi identity | Chưa có / chưa đánh giá C | 6.000 | 1,958 | FIFO hết cap; ordered replay 3 bước đạt goal |
| Q4 | User ROLANDO 1111 → DA 512 | Reset qua nhóm 3790 | Chưa có / chưa đánh giá C | 6.000 | 1,926 | Hết cap; đoạn membership đã kiểm còn Unknown security_group/membership_usable |
| Q5 | User MARYANNE 1269 → DA 512 | Reset qua nhóm 3610 | Chưa có / chưa đánh giá C | 6.000 | 2,161 | Hết cap; membership tới nhóm 3610 còn Unknown; tên DISTLIST không thay bằng chứng group type |
| Q6 | User KATRINA 1116 → DA 512 | Qua Administrators, WriteDacl → GenericAll → AddMember | Chưa có / chưa đánh giá C | 6.000 | 2,466 | Replay được membership + WriteDacl; AddMember còn Unknown security_group/membership_change_allowed |
| Q7 | Computer FINWVIR 4157 → DA 512 | Reset; FIFO | Chưa có / chưa đánh giá C | 6.000 | 2,414 | Hết expansion cap |
| Q8 | Computer FINWVIR 4157 → DA 512 | Cùng Q7; goal_guided | Có / C=1 | 4.995 | 3,190 | Cap 1 witness; best-found, chưa chứng minh minimum |
| Q9 | User OLA 1395 → host 1000 | Reset → identity mới → AdminTo | Chưa có / chưa đánh giá C | 6.000 | 1,561 | FIFO hết cap; ordered replay 3 bước đạt admin control |
| Q10 | User FERN 3385 → host 1000 | CanPSRemote | Có / chưa đủ C | 1 | 0,459 | open_winrm_remote_session nằm ngoài 9 techniques; không phải AdminTo/admin control |

Có 4/10 query tìm witness và 3/4 witness đủ C, gồm một đường passive C=0; sáu query truncated chưa cho phép đánh giá coverage C hoặc kết luận no-path.
Mẫu này xác nhận C cho AdminTo trực tiếp và reset/activation với actor thay đổi; chưa xác nhận coverage C của các chain qua nhóm/ACL trên SEAMLESS chỉ từ finite tests.
Q3/Q9 có chuỗi conditional khả thi dưới cùng policy nhưng FIFO chưa tìm được trong budget; Q7/Q8 cô lập khác biệt search order mà không thay query facts hoặc C.
Q4/Q5/Q6 cho thấy facts/policy cho membership và quyền phát sinh cũng là điểm vướng; chưa thể kết luận mọi đường của các query này bị chặn, hoặc chỉ cần sửa search.
Chưa đổi engine/search, mở techniques, thêm assumptions hoặc dọn repo trong lượt khảo sát này.

Đã native replay cả bốn witness và kiểm final state:

- Q1: `obtain_admin_execution_on_host` dùng AdminTo của KATRINA tới BADBLOOD, C=1; admin_channel và authentication_accepted là assumptions.
- Q2: `propagate_group_entitlement` của DENA tới DA là passive, không tạo work unit, C=0; không diễn giải thành xác suất tấn công mới.
- Q8: FINWVIR reset OLLIE C=1 → OLLIE dùng credential vừa reset tại context FINWVIR C=0 → OLLIE có entitlement DA qua MemberOf C=0; hai active work units có tổng C=1.
- Q10: `open_winrm_remote_session` của FERN đạt remote command execution, replay pass nhưng unit chưa có giá; C=None không được đổi thành 0.

Ordered replay chẩn đoán Q3/Q9 không được đưa vào discovery hoặc tính thêm vào 4 witness ở bảng.
Nó kiểm chuỗi OLA → reset DENA → activate DENA → DA hoặc AdminTo trên BADBLOOD, với cùng initial state, context và policy như query gốc.
Q6 giữ nguyên Unknown ở AddMember sau quyền GenericAll phát sinh; không tự bổ sung gate để làm đường chạy được.

Lệnh tái lập từ repo root; bỏ dòng `neo_baseline` nếu snapshot này đã tồn tại, hoặc dùng directory mới và đổi đường dẫn trong Python tương ứng:

```sh
.venv/bin/python -m scripts.neo_baseline --effort-profile neo-c-v1 --output-dir reports/generated/neo-c-001
.venv/bin/python - <<'PY'
import time
from collections import Counter
from pathlib import Path
from src.engine.graph import EngineGraph
from src.engine.query import materialize_query, run_attack_query
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.semantics import Status, TransitionRequest, apply_transition, evaluate
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.scenario_policy import apply_policy_to_query
D = 'S-1-5-21-1271839998-3495686680-2211690266'
n = lambda rid: D + '-' + str(rid)
M, R, I, A = ('propagate_group_entitlement', 'scenario_reset_password',
              'acquire_reset_identity', 'obtain_admin_execution_on_host')
W, ADD = 'grant_new_object_right', 'genericall_add_member'
families = {'A': [A], 'M': [M], 'R': [M, R, I], 'H': [M, R, I, A],
            'D': [M, W, ADD], 'W': ['open_winrm_remote_session']}
# Q, source RID, goal RID, context RID, technique family, search order.
cases = [(1,1116,1000,1000,'A','fifo'), (2,2799,512,1000,'M','fifo'),
         (3,1395,512,1000,'R','fifo'), (4,1111,512,1000,'R','fifo'),
         (5,1269,512,1000,'R','fifo'), (6,1116,512,1000,'D','fifo'),
         (7,4157,512,4157,'R','fifo'), (8,4157,512,4157,'R','goal_guided'),
         (9,1395,1000,1000,'H','fifo'), (10,3385,1000,1000,'W','fifo')]
g = EngineGraph.from_snapshot(Path('reports/generated/neo-c-001/snapshot.json').read_text())
profile = load_effort_profile('neo-c-v1')
policy = 'seamless-standard-v1'  # Đổi thành 'neo-standard-v1' để đối chiếu policy mới.
for number, source, target, context, family, order in cases:
    s, t, c = map(n, (source, target, context))
    goal = {'target': t, 'kind': 'usable_identity_entitlement'} if target == 512 else {
        'target': t, 'required_state': {'remote_command_execution': [[s,t]]}
        if family == 'W' else {'admin_control': [t]}}
    q = dict(initial_actor=s, initial_state={'control': [s], 'usable_identity': [[s,c]]},
             authentication_context=c, target=t, target_goal=goal, allowed_techniques=families[family],
             scenario_reference=f'neo-cohort/Q{number}', evaluation_mode='scenario', search_order=order,
             budget={'max_paths': 1, 'max_steps': 5, 'max_expansions': 6000})
    started = time.perf_counter()
    q = bind_effort_profile(apply_policy_to_query(q, g, policy), g, profile)
    r = run_attack_query(q, g)
    seconds = time.perf_counter() - started
    coverage = (r.rating_coverage or {}).get('candidate_summaries', {})
    print(f'Q{number}', 'paths=',len(r.paths), 'C=',(r.min_effort or {}).get('minimum_effort_value'),
          'C_complete=',[v['c_complete'] for v in coverage.values()], 's=',round(seconds,3),
          'exp=',r.expansions, 'cap=',r.truncation_reason,
          'unknown=',Counter(p for a in r.attempts for p in a.unknown).most_common(3))
    for index, path in enumerate(r.paths, 1):
        assert replay_path(path, g) == path.final_state
        assert r.materialized_query.semantic_goal.matches(path.final_state)
        units = r.rating_coverage['candidates'][f'generated_{index:04d}']['effort']['units']
        print('replay:', [a.result.request.technique_id for a in path.transition_history],
              'C units:', [(v['rating_audit']['lookup_key']['technique'], v['cost']) for v in units.values()])
    # Diagnostic ordered replay only; these requests never enter discovery/search.
    a, v, h, da = n(1395), n(2799), n(1000), n(512)
    k, admins = n(1116), 'domain:sid:' + D + ':S-1-5-32-544'
    probes = {3: [(R,a,a,v),(I,v,v,h),(M,v,v,da)],
              6: [(M,k,k,admins),(W,k,admins,da),(ADD,k,k,da),(M,k,k,da)],
              9: [(R,a,a,v),(I,v,v,h),(A,v,v,h)]}
    if number in probes:
        m = materialize_query(q, g); state = m.initial_attack_state
        for spec in probes[number]:
            step = evaluate(g.to_prepared(), state, TransitionRequest(*spec), m.runtime_context, m.catalog)
            print('ordered probe:', spec[0], step.status, 'failed=',step.failed, 'unknown=',step.unknown)
            if step.status != Status.APPLICABLE: break
            state = apply_transition(state, step)
        print('ordered goal matches:', m.semantic_goal.matches(state))
PY
```

## Scenario mặc định neo (2026-10-21)

`neo-standard-v1` tái sử dụng các rule hiện có, với giả định được chọn cho khóa luận:
nhóm thiếu group type được coi là security group trong scenario, kể cả tên DISTLIST.
Tên nhóm không phải bằng chứng về loại nhóm. `security_enabled=False`, groupType
non-security và runtime fact False vẫn chặn; không tạo cạnh, quyền hay usable identity.
Mọi fact được bổ sung mang origin `declared_assumption`, với profile/rule/provenance.
Không suy xác suất thành công từ các giả định này.

Query dùng lại `PolicyAssumptionResolver` sẵn có theo nhu cầu cho `security_group`,
`membership_usable`, `membership_change_allowed` và `directory_write_allowed`, nên các
gates này vẫn được giải quyết sau khi đổi actor hoặc tạo quyền trong một prefix hợp lệ.
Các điều kiện khác giữ scope biên dịch hiện có; không mở mặc định host-admin mapping,
endpoint authorization hoặc password recovery. Không sinh trước
Cartesian product actor × group. Các declaration tường minh được ưu tiên; các fact
thực sự dùng được ghi trong transition decisions. Metadata giữ profile đầy đủ để CLI,
batch worker và replay tái lập cùng scenario. Remediation giữ policy trên graph sau sửa.

Đối chứng cùng snapshot và cohort 10 query, cùng techniques/5 steps/6.000 expansions:

| Kiểm tra | `seamless-standard-v1` | `neo-standard-v1` |
| --- | --- | --- |
| Discovery | 4/10 witness; 3/4 đủ C | 4/10 witness; 3/4 đủ C |
| Q4: membership tới nhóm 3790 | Unknown group gates | Replay prefix 2 MemberOf steps applicable |
| Q5: membership tới nhóm 3610 (DISTLIST) | Unknown group gates | Replay prefix 1 MemberOf step applicable |
| Q6: ACL → AddMember → DA, ordered probe | Dừng ở AddMember Unknown | Cả bốn actions applicable, đạt goal |
| Q8: machine → DA, guided | C=1 sau 4.995 expansions | Giữ C=1 sau 4.995 expansions |

Replay prefix/ordered probe là chẩn đoán riêng, không được tính thêm vào witness discovery.
Sáu query vẫn chạm cap; thay đổi này sửa khả năng áp dụng scenario, chưa sửa search.
Q10 vẫn chưa có C cho WinRM command session; nó không phải quyền admin.
Không so runtime của lượt Linux này với bảng macOS ở trên.

Runner `scripts.neo_baseline` mặc định dùng policy mới; thêm
`--scenario-policy seamless-standard-v1` để chạy lại policy cũ.
Exposure nhận `--scenario-policy neo-standard-v1`.
Trong lệnh cohort phía trên, đổi biến `policy` giữa hai tên để đối chứng.
Test riêng ở `tests/test_neo_scenario_policy.py` kiểm missing type, thuộc tính/fact False,
quyền phát sinh, evidence-only, profile transport, worker/resume và counterfactual.
23 test mới pass. Các lượt test tập trung engine/query/batch/C, policy và remediation
có tổng 777 passed, 3 optional raw-remediation pilots skipped; không chạy full suite.
Runner SEAMLESS với scenario mới đã qua native replay và API–CLI parity.

## Neo search và C-first (2026-10-21)

`neo_guided` thêm thứ tự ưu tiên vào planner hiện có: khoảng cách cấu trúc tới đích,
ưu tiên kích hoạt credential đã reset, rồi theo nhánh hữu ích trước khi xét tiếp
các hành động còn lại của một state nhiều nhánh. Những hành động còn lại được giữ
trong queue; không bỏ nhánh, thêm quyền hoặc sửa evaluator/scenario/bảng C.
Đây là greedy guidance, không phải C lower bound hoặc bảo đảm minimum.
Group/host goals và nhóm reset/membership/ACL/admin/WinRM được hỗ trợ;
public query ngoài catalog đó hoặc thiếu typed goal ghi rõ fallback FIFO.
FIFO và `goal_guided` cũ giữ nguyên để đối chiếu.

`neo-c-v1` mặc định yêu cầu Top-3 theo C (giữ `top_k` tường minh của người gọi).
Tái sử dụng selector và work-unit dedup hiện có. Top-K ghi rõ `eligible_for_C_ranking`,
required dimension C, supplementary P/I; thiếu P/I không chặn selection.
Nhãn `ineligible_partially_unrated` trong audit CPI cũ chỉ nói về đủ cả ba chiều,
không phải loại khỏi Top-K theo C. Thiếu C vẫn bị loại, không biến thành C=0.

Đối chiếu cùng snapshot, facts/policy, techniques, max_steps=5, cap=6.000;
max_paths=1, Q8 dùng guided cũ ở cột baseline, các ca còn lại FIFO:

| Query | Expansions baseline | Expansions neo | C neo |
| --- | ---: | ---: | ---: |
| Q1 | 1 | 1 | 1 |
| Q2 | 8 | 1 | 0 |
| Q3 | 6.000, chưa có witness | 6 | 1 |
| Q4 | 6.000, chưa có witness | 5 | 1 |
| Q5 | 6.000, chưa có witness | 7 | 1 |
| Q6 | 6.000, chưa có witness | 4 | 3 |
| Q7 | 6.000, chưa có witness | 6 | 1 |
| Q8 | 4.995 | 6 | 1 |
| Q9 | 6.000, chưa có witness | 11 | 2 |
| Q10 | 1 | 1 | Chưa chấm |

Discovery tăng 4/10 → 10/10; query có C tăng 3/10 → 9/10.
Q2 là entitlement có sẵn; Q7/Q8 cùng nguồn–đích, khác search order baseline.
Đây là cohort chẩn đoán nhỏ, không phải 10 ca độc lập ngẫu nhiên hay toàn miền.
Tất cả witness qua native replay và declared goal; không đếm ordered probe.
Q10 vẫn thiếu C, các kết quả best-found vẫn ghi giới hạn tìm kiếm.

Với max_paths=3: baseline tìm 6 witness trên 4 query; neo tìm 24 trên 10 query.
23/24 witness đủ C. Q6 có ba chương trình C=3,5,5 và Top-K xếp 3 trước 5;
Q9 có ba đường C=2. Đồng điểm được giữ và công bố, không tự tạo khác biệt P/I.
Q4 chỉ tìm một witness rồi chạm cap; không tuyên bố đã tìm hết alternative.
Finite oracle riêng đối chiếu toàn bộ programs giữa FIFO/neo và các route C=1,2,4;
kiểm False/Unknown, identity/context boundaries, work ledger, worker/resume và remediation.

Tradeoff Linux trong lượt này: max_paths=1 tổng query time 16,62 → 20,66s;
max_paths=3 là 19,44 → 57,03s. Tổng expansions tương ứng 41.005 → 48 và
42.026 → 6.087. Mỗi phương án tìm/chấm số witness khác nhau; đây không phải
speedup runtime. Số expansions không bao gồm preparation, sinh candidate hay scoring.
Một lượt riêng Q4/max_paths=3 đo process peak RSS (gồm load snapshot/query):
FIFO 309,4 MiB, neo 405,5 MiB, tăng khoảng 31%; neo tìm một witness, FIFO không tìm
được. Đây không phải số đo RAM toàn cohort. Không so thời gian Linux với macOS baseline.

Tái lập sau khi chạy `scripts.neo_baseline` để có snapshot:

```sh
.venv/bin/python -m scripts.neo_cohort \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --output-dir reports/generated/neo-search-single --max-paths 1
.venv/bin/python -m scripts.neo_cohort \
  --snapshot reports/generated/neo-run-001/snapshot.json \
  --output-dir reports/generated/neo-search-multi --max-paths 3
```

Runner lưu public queries, witnesses/Top-K và summary; replay mọi witness ngay trong
lượt chạy. Bản neo baseline mặc định C mới, chạy cả ba orders và kiểm parity API/CLI.
Raw data và generated outputs tiếp tục không commit.

Validation thay đổi này: 487 focused tests passed, 1 optional raw-remediation test
skipped; chưa chạy full suite. Native replay/API–CLI parity gồm Top-K pass;
Ruff check/format, yamllint, repository và graph contract checks pass.

## Chốt đầu ra một foothold: WinRM, thời gian và bản đọc nhanh

`neo-c-v1` version 1.1.0 bổ sung `open_winrm_remote_session`: T1=1, T2=2,
C=1 cho công cụ chuẩn và thao tác/xác minh phiên lệnh đã xác thực. Đây là ước lượng
scenario theo rubric hiện có; chín mức C cũ không đổi. CanPSRemote chỉ đạt
`remote_command_execution`, không tự cấp `admin_control`. Thiếu/False ở
`winrm_available` hoặc `authentication_accepted` vẫn chặn đường như trước.
Config rating nhúng của lượt cũ vẫn replay được với bộ giá cũ; profile mới có digest mới.

Chạy lại max_paths=3 trên cùng 10 query: 10/10 đạt mục tiêu, 24 witness đều đủ C
(trước bổ sung là 23/24). So sánh đủ 20 cells baseline/neo với lượt trước:
witness bytes và expansions không đổi; C của Q1–Q9 không đổi, Q10 từ chưa chấm → 1.
Mọi witness được replay, không tính ordered probe vào discovery.

Profiling xác định hai phần lặp: sắp xếp quan hệ trong search và sao chép toàn graph
cho từng witness trước scoring. Search nay chuẩn bị thứ tự theo source một lần,
chèn quan hệ phát sinh của từng nhánh vào đúng thứ tự; cache tập source chỉ sống trong
mỗi search và giới hạn 32 entries. Không cache kết quả applicability hay facts.
Resolver tái sử dụng canonical graph đã được EngineGraph kiểm tra; edge đưa ra witness
vẫn được copy riêng. Catalog, số expansions, thứ tự chương trình và evaluator không đổi.

Đo riêng tuần tự bằng hai process/code tree trước (`bbc918b`) và sau thay đổi,
cùng Python/Linux, snapshot/query đã nạp. Mỗi case có một lượt cold + ba lượt warm;
thời gian dưới đây là median `run_attack_query`, không gồm ghi report hay load snapshot:

| Query, max_paths=3 | Median trước | Median sau | Peak RSS trước → sau |
| --- | ---: | ---: | ---: |
| Q4, 1 witness / 6.000 expansions | 9,503s | 4,792s | 475,1 → 474,2 MiB |
| Q9, 3 witness / 15 expansions | 3,933s | 2,626s | 429,4 → 427,4 MiB |

Tương ứng giảm khoảng 50% và 33% thời gian ở hai ca này; RAM gần như không đổi.
Không suy thành speedup toàn miền. Full semantic hashes trên hai public query cũ,
gồm paths, C/Top-K, diagnostics và proof/budget dispositions, giữ nguyên.
Không trộn số đo này với lượt cohort chạy đồng thời test hoặc benchmark macOS.

`scripts.neo_baseline` nay sinh `neo_guided.md` cạnh JSON, trình bày nguồn–đích,
scope kỹ thuật/context, hành động, work ledger C, P/I, giả định đã dùng và best-found/minimum.
`scripts.neo_cohort` sinh `brief.md` cho mỗi cell. CLI query bất kỳ nhận
`--brief reports/generated/result.md` cùng `--output reports/generated/result.json`.
Cả hai được dựng từ cùng một execution; bản đọc nhanh không tìm lại đường hay tự chấm điểm.
Thiếu C vẫn hiển thị chưa chấm; thiếu witness khi còn Unknown hoặc hết cap không kết luận an toàn.

Validation: 686 focused tests passed, 1 optional raw-remediation test skipped;
chưa chạy full suite. Native replay/API–CLI parity, Ruff, yamllint, repository và graph contract pass.

## SEAMLESS: toàn bộ nguồn đủ điều kiện → DA/EA

Lượt domain chạy trên snapshot SEAMLESS 3.370 nodes / 56.367 edges, không lọc nguồn
bằng reachability: 2.490 User và 100 Computer, mỗi nguồn là một tình huống compromise
độc lập với danh tính mạng dùng được. Không gộp quyền giữa các nguồn. Đích là hai group
DA/EA theo SID quan sát; chưa bao gồm mọi tài sản hoặc kỹ thuật AD.
Số liệu và hash tái lập nằm trong [domain-survey.json](../reports/neo/domain-survey.json).

Budget lượt rộng: `neo_guided`, 1 witness, 5 semantic steps, 256 expansions/query;
chỉ bảy kỹ thuật directory trong `scripts.neo_domain.TECHNIQUES`. Đây là budget
nhỏ hơn cohort chẩn đoán 6.000 expansions trước, không phải so sánh ngang budget.
Đã chạy đủ 5.180/5.180 cặp, không lỗi, không còn cặp chưa chạy.

| Đích | Cặp khai báo và đã chạy | Có witness và C | Chưa có witness, còn giới hạn |
| --- | ---: | ---: | ---: |
| Domain Admins | 2.590 | 248 | 2.342 |
| Enterprise Admins | 2.590 | 7 | 2.583 |
| Tổng | 5.180 | 255 | 4.925 |

User có witness trên 251/4.980 cặp; Computer 4/200. Phân bố C trên 255 witness:
C=0: 6; C=1: 233; C=2: 8; C=3: 8. C=0 là entitlement có sẵn. Điểm tập trung
ở C=1 nên chưa phân hạng chi tiết được các đường reset tương tự; không tự bổ sung
điểm P/I hoặc biến C thành xác suất. Tất cả C là best-found, chưa chứng minh minimum.
Không cặp nào được chứng minh no-path. Cờ `truncated_pairs` gồm cả query thành công
đã dừng ở path cap; số **chưa có witness và còn giới hạn** là 4.925.

Có 25.968 attempts Unknown ở mỗi gate `password_policy_accepts` và
`network_rpc_reachable`. Đây là bộ đếm nhánh đã thử, không chứng minh hai gate này
là nguyên nhân của mọi query chưa tìm được. Không thêm default mới để làm đẹp coverage.

Probe sâu hơn chọn cố định hai nguồn có SHA256 nhỏ nhất trong mỗi nhóm
User/Computer × DA/EA, dùng seed `neo-domain-probe-v1`, không lọc theo reachability.
Với 8 steps / 6.000 expansions, 3/8 cặp có witness, so với 2/8 ở lượt rộng;
5/8 vẫn hết giới hạn. Chỉ một cặp Computer → DA được tìm thêm; không ngoại suy
probe này cho 5.180 cặp. Selection, budget và từng kết quả được lưu trong evidence JSON.

Chẩn đoán riêng nguồn SID kết thúc `-1103` → DA: một đường topology 5 cạnh cần
**6 semantic steps** (ba membership, reset, acquire identity, membership).
Ordered replay đạt goal với policy hiện tại, không thêm fact. Đây là bằng chứng
budget độ sâu bỏ sót ít nhất một đường; ordered replay không tính vào 255 discovery.
Chưa có đối chứng BloodHound live mới.

Lượt 5 bước dưới đây dùng code `5f8d333` và report helper tại `3bcc1f5`.
Để tái lập số liệu lịch sử này, dùng commit `3bcc1f5`; code mới có mặc định khác.
Checkpoint chỉ resume được cùng code/snapshot/budget:

```sh
.venv/bin/python -m scripts.neo_domain \
  --snapshot reports/generated/neo-uc1/native/snapshot.json \
  --output-dir reports/generated/neo-domain-256-v2 --workers 8
# Nếu bị ngắt, chạy lại cùng lệnh và thêm --resume.
.venv/bin/python -m scripts.neo_domain_report \
  --survey reports/generated/neo-domain-256-v2 \
  --snapshot reports/generated/neo-uc1/native/snapshot.json \
  --output-dir reports/generated/neo-domain-final --interventions 1
```

Output directory mới phải chưa tồn tại. Runner dùng spawn workers; mỗi worker tái sử dụng
snapshot, mỗi query giữ state/facts riêng. Witness lưu các facts đã dùng, kiểm native
replay và program identity trước khi ghi; public query đầy đủ dựng lại từ scope/profile.
Bản đọc nhanh phân biệt witness, giới hạn, Unknown và cặp chưa chạy/lỗi.

Can thiệp đã kiểm bằng native replay và rediscovery độc lập trên **scope riêng 4 cặp**
(hai nguồn hỗ trợ cạnh MemberOf chung nhất × DA/EA): bỏ MemberOf của OLLIE_LONG
vào Domain Admins. Cạnh này xuất hiện trên 168 witness C>0 của lượt rộng;
con số 168 là hỗ trợ quan sát, không phải số cặp sẽ được ngắt kết nối.
Hai witness gốc đều bị cắt; một chương trình bypass được tìm lại. Sau can thiệp,
một cặp còn reachable, ba cặp chưa kết luận; **0/2 cặp trước đó reachable được
chứng minh disconnected**. Không báo giảm rủi ro toàn miền từ kết quả này.
Executor hiện hỗ trợ membership; revoke GenericAll/WriteDacl/ForceChangePassword
chưa được hỗ trợ, dù các cạnh đó vẫn xuất hiện trong danh sách điểm can thiệp.
Chưa đo chi phí vận hành hoặc tác động nghiệp vụ của việc gỡ membership.

Validation lượt này: 302 focused tests pass, 1 optional raw-remediation test skip;
chưa chạy full suite. Witness được native replay khi ghi; remediation package đã
qua independent verifier. Ruff, repository, contract và diff checks pass.

Ưu tiên tiếp theo: xử lý bỏ sót do độ sâu trong cùng scope bảy kỹ thuật, rồi đo lại
coverage DA/EA và khả năng phân hoá C. Những thay đổi policy/facts hoặc mở thêm
loại intervention cần được trao đổi trước; kết quả domain hiện tại là baseline
để đánh giá cải tiến, chưa phải bằng chứng hoàn thiện toàn miền.

## Sửa bỏ sót do budget và áp dụng policy cho danh tính mới

Code thực thi: `daf1c87`; snapshot, 2.590 nguồn độc lập, DA/EA và bảy kỹ thuật
không đổi. Bản sửa áp dụng hai rule **đã có** (`password_policy_accepts`,
`network_rpc_reachable`) khi engine chuyển sang danh tính vừa chiếm được.
Rule definitions, quyền quan sát và bảng C không đổi; fact False, đối tượng disabled
và evidence-only vẫn chặn như trước. Thứ tự search production không đổi.

Đường hợp lệ cần 6–9 bước bị giới hạn 5 bước cắt ngang. Mẫu cố định 80 cặp chọn
20 nguồn theo SHA256 nhỏ nhất trong mỗi nhóm User/Computer × DA/EA, không lọc
kết quả: 5 bước/256 expansions tìm được 6 cặp; 8 bước được 41; 12 bước được 70.
Sau sửa binding, 12 bước/256 expansions được 79; cặp còn lại tìm được ở expansion
364 khi cap là 1.024. Mẫu này cân bằng loại nguồn/đích, không dùng để ước lượng
prevalence toàn miền. Vì vậy đã chạy lại đủ 5.180 cặp với 12 bước/1.024 expansions.

| Đích | Cặp đã chạy | Có đường trước | Có đường và C sau | Còn hết lượt tìm |
| --- | ---: | ---: | ---: | ---: |
| DA | 2.590 | 248 | 2.588 | 2 |
| EA | 2.590 | 7 | 2.583 | 7 |
| Tổng | 5.180 | 255 | 5.171 | 9 |

Tìm thêm 4.916 cặp; giữ đủ 255 cặp đã tìm được trước. Không có lỗi thực thi và
không ghi nhận Unknown trong các nhánh đã thử. Chín cặp còn lại đều hết 1.024
expansions; chưa được native engine chứng minh no-path. Hai cặp trong số đó bắt đầu
ở DC BADBLOOD, không có đường trên projection bốn quan hệ directory đang xét;
đây là chẩn đoán cấu trúc riêng, không tự đổi trạng thái proof của query.

Ca SEAMLESS thực: nguồn `-1104` chiếm lần lượt `-1324`, `-2799` rồi đạt DA,
8 bước, C=2, 37 expansions. Đây là discovery được native replay kiểm tra,
không phải ordered probe. Nó kiểm tra cả tình huống một foothold tiếp tục chiếm
nhiều danh tính. Test hồi quy riêng kiểm chuỗi hai lần reset và từng fact False.

[Evidence JSON](../reports/neo/domain-discovery-fix.json) giữ source/snapshot pins,
phân bố C, selection, các lượt ablation và chín cặp còn lại. C vẫn là best-found;
chưa chứng minh minimum. Lượt chạy đã resume sau khi phiên xử lý dừng, kiểm
checksum trước khi nối tiếp; `elapsed_seconds` là đoạn resume cuối, không phải
tổng thời gian. Không suy speedup từ hai lượt có budget và coverage khác nhau.
Evidence remediation của lượt cũ vẫn gắn với code/budget cũ; chưa chạy lại trong lượt này.

```sh
.venv/bin/python -m scripts.neo_domain \
  --snapshot reports/generated/neo-uc1/native/snapshot.json \
  --output-dir reports/generated/neo-domain-12-1024 \
  --max-steps 12 --max-expansions 1024 --workers 8
```

Validation: 389 focused tests pass, 1 optional raw-remediation test skip; chưa chạy
full suite. Native replay, source/snapshot integrity, Ruff, repository và contract
checks pass. Dùng output directory mới; thêm `--resume` khi tiếp tục cùng scope.

