# Worklog - 2026-10-01 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#143](https://github.com/nairyuuu/ad-weighted-graph/issues/143), [#42](https://github.com/nairyuuu/ad-weighted-graph/issues/42), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48) / PR [#161](https://github.com/nairyuuu/ad-weighted-graph/pull/161) branch `docs/143-seamless-parameter-proposal` / M2-A Week 3
- Thời gian thực tế ước lượng: Không đo thời lượng phiên sửa; không suy giờ làm từ số lệnh hoặc thời gian test.

## Kết quả và bằng chứng

Worklog này ghi nhận kết quả thực hiện và hoàn thiện slice kỹ thuật của TTS A theo checkpoint sau merge PR #159 tại commit `f92ed75`, các điều chỉnh kỹ thuật sau các vòng tự rà soát (self-review rounds) của TTS A (@Lolavine777) tại PR [#161 (comment 5929312919)](https://github.com/nairyuuu/ad-weighted-graph/pull/161#issuecomment-5929312919), [comment 5929703729](https://github.com/nairyuuu/ad-weighted-graph/pull/161#issuecomment-5929703729), [comment 5930832730](https://github.com/nairyuuu/ad-weighted-graph/pull/161#issuecomment-5930832730), và [comment 5932097631](https://github.com/nairyuuu/ad-weighted-graph/pull/161#issuecomment-5932097631), và xử lý phản hồi formal review chính thức từ TTS B (@nairyuuu) tại [review 5380395316](https://github.com/nairyuuu/ad-weighted-graph/pull/161#pullrequestreview-5380395316).
Công việc bao gồm: xác lập bản ghi quyết định thiết kế/phiên bản/chuyển dịch tường minh, xây dựng hồ sơ căn cứ tham số có giải trình độ bất định dư thừa, chuẩn hóa rubric nỗ lực không phụ thuộc vào logging, khắc phục lỗi entrypoint CLI, triển khai phân tích độ nhạy lân cận quanh đề xuất, chuẩn hóa chính sách thử lại có giới hạn và bảng nguồn kỹ thuật chính thức, thống nhất định nghĩa khả dụng liên tục của kênh mạng và giải trình bất định dư thừa thuần túy trên tranh chấp máy chủ, và kiểm thử hồi quy toàn diện.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| 1. Quyết định thiết kế, phiên bản và chuyển dịch (A2.1) | [path-ranking-acceptance-disposition.md Mục 5](../research/path-ranking-acceptance-disposition.md) | Ghi nhận quyết định tường minh cho từng hàng disposition: ADR-0013 (Gate 1), Interface 1.0.0 và migration boundary (Gate 2), Route/Work identity separation (Gate 3), Scenario bindings và 25 runtime assumptions (Gate 4), SEAMLESS predictive verdict Insufficient Evidence (Gate 5), và Official disposition pending B review (Gate 6); chuẩn hóa phạm vi known-false veto vào required predicates và xác lập canonical enum independent kèm wire alias distinct_work. |
| 2. Hồ sơ căn cứ và đề xuất tham số SEAMLESS (A2.2) | [seamless-parameter-basis-proposal.md](../research/seamless-parameter-basis-proposal.md) | Xây dựng dossier cho Source A và Source B; đánh giá tác động High cho DC BADBLOOD; định mức rubric T1/T2/C (C=T1+T2-2) cho 9 đơn vị công việc chuẩn tắc dựa trên ma sát tương tác (loại bỏ Event 4724); giải trình độ bất định dư thừa sau khi điều kiện hóa S và trích dẫn Open Specs Microsoft cho 11 câu hỏi q_i; gắn nhãn minh bạch research-assisted scenario estimates. |
| 3. Khắc phục entrypoint CLI và xuất báo cáo di động | `scripts/research/seamless_parameter_validation.py`, `reports/research/seamless-parameter-validation-report.json` | Đưa bootstrap sys.path lên trước các local imports; lệnh `python scripts/research/seamless_parameter_validation.py` chạy thành công từ thư mục gốc trong môi trường sạch; trường input_file được chuẩn hóa đường dẫn tương đối di động. |
| 4. Phân tích độ nhạy lân cận và kiểm tra tuân thủ | `scripts/research/seamless_parameter_validation.py`, `reports/research/seamless-parameter-validation-report.json` | Thực thi phân tích độ nhạy lân cận (tăng T2 cho Lidia khiến Min-Effort đổi sang Candidate 2 nhưng biên Pareto giữ nguyên; thu hẹp khoảng lồng nhau tạo ưu thế Pareto tuyệt đối; quét khoảng cách giao nhau Delta=0.21633) và 6 probes tuân thủ bất biến (tie-break, impact shift, fail-closed, known-false veto, irrelevant false no-op, unknown gating). |
| 5. Kiểm thử tự động chuyên biệt | `tests/test_seamless_parameter_proposal.py` | 15/15 tests PASSED; kiểm tra tính hợp lệ của fixtures, roundtrip Source A/B, vết tính phân số, phân tích độ nhạy lân cận, executed sweep flip (-10% upper bounds), wire adapter independent/unrated, các probes tuân thủ bất biến, kiểm toán an toàn phiếu rater con người, và thực thi CLI qua subprocess sạch. |
| 6. Bảo toàn các phiếu đánh giá độc lập | `tests/fixtures/ranking/seamless_rater_1.json`, `tests/fixtures/ranking/seamless_rater_2.json` | Hai sheets duy trì 100% trường rater identity, thời điểm, chữ ký, điểm số, và rationale ở giá trị null; trạng thái giữ nguyên `pending_independent_ratings`. |
| 7. Kiểm tra chất lượng và hồi quy toàn bộ | `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/yamllint`, `scripts/check_contract.py`, `scripts/check_repository.py`, `git diff --check` | Toàn bộ test suite đạt kết quả pass sạch; ruff check và format 100% clean; yamllint clean; git diff sạch hoàn toàn. |

### Khắc phục 5 findings rà soát kỹ thuật chi tiết (Iteration 2 - Self-review round 2)

Nhằm đáp ứng các phát hiện qua đợt tự rà soát kỹ thuật chi tiết tại comment 5929703729, TTS A đã thực hiện chuỗi điều chỉnh đồng bộ:
1. **Chuẩn hóa locator provenance:** Sửa toàn bộ 5 locator trỏ nhầm sang cấu trúc container máy tính/nhóm trong `seamless-parameter-basis-proposal.md` để khớp chính xác với snapshot JSON và `seamless_proposed_query_input.json`.
2. **Hiệu chỉnh conditioning và retry policy:** Loại bỏ clock skew drift khỏi residual uncertainty của Kerberos AS-REQ do `network_kdc_reachable` đã giả định valid time context; bổ sung tuyên bố horizon 24h và active work budget 6 với bounded retry policy trước lỗi mạng tạm thời; định nghĩa rõ cổng Gate 5 (effective access permit) và Gate 6 (authentication permit) trong disposition.
3. **Phân tích độ nhạy kép (Dual Analysis) và xóa overclaim:** Bổ sung kịch bản executed sweep với Candidate 2 upper bounds giảm $10\%$ đưa $u_2 \approx 0.32615 < l_1 = 0.336$, minh chứng sự đảo chiều của biên Pareto rủi ro khi chuỗi tham số suy giảm đồng thời; xóa bỏ khẳng định cứng nhắc về mọi biến động $\pm 5/10/15\%$.
4. **Chuẩn hóa căn cứ Open Specifications:** Cập nhật tham chiếu chuẩn `[MS-SAMR] Section 3.1.5.6.4 (SamrSetInformationUser2, Opnum 58)` cho các câu hỏi đặt lại mật khẩu; loại bỏ trích dẫn `MS-DRSR 4.1.10.5.2` (vốn là `GetReplChanges`).
5. **Minh định hợp đồng `independent`/`unrated`:** Xác nhận `distinct_work` là bí danh tương thích ngược của `independent`; làm rõ `rating_status == "unrated"` với `rubric_scores: null` và `computed_cost: null` là hoàn toàn hợp lệ khi thiếu cơ sở định mức hoặc withholding.

### Khắc phục các yêu cầu về Bounded Retry Policy, Bảng nguồn chuẩn tắc và Minh định Attribution (Iteration 3 - Self-review round 3)

Nhằm giải quyết triệt để các phát hiện tại comment 5930832730 trước khi bước vào formal review của TTS B, TTS A đã hoàn thiện các nội dung sau:
1. **Chính sách thực thi và thử lại có giới hạn (Bounded Retry Policy):**
Quy định chi tiết chính sách thử lại theo từng nhóm hành động (SAMR reset $N=3$, deadline $\le 15$ phút; Kerberos ticket $N=3$ kèm UDP-to-TCP fallback theo RFC 4120 Section 7.2.1, 7.2.2, 8.1, deadline $\le 10$ phút; WinRM elevated session $N=3$, deadline $\le 30$ phút) trong khung thời gian chiến dịch chung 24h tại Mục 5.2 của dossier.
Định nghĩa tường minh $q_i$ là xác suất hoàn thành hành động sau khi thực hiện đầy đủ chính sách thử lại có giới hạn trong thời hạn của hành động.
Làm rõ cận trên và cận dưới phản ánh rủi ro thất bại dai dẳng không thể phục hồi (unrecovered persistent failures) sau khi đã thử lại hết số lượt cho phép.
Làm rõ ngân sách công việc tích cực 6 đơn vị công việc chuẩn tắc là giới hạn số đơn vị công việc phân biệt (distinct active work units), không phải giới hạn số lượt thử lại của cùng một đơn vị.
2. **Bảng ánh xạ nguồn kỹ thuật chuẩn tắc toàn diện (Consolidated Primary Source Mapping Table):**
Thiết lập bảng tham chiếu tập trung tại Mục 5.1 của dossier với đầy đủ URL Microsoft Learn / IETF RFC, số mục và tên mục chính thức (Official Section Titles):
`SRC-SAMR` ([MS-SAMR 3.1.5.6.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/99ee9f39-43e8-4bba-ac3a-82e0c0e0699e)), `SRC-RFC4120` ([RFC 4120 Section 3.1, 7.2.1, 7.2.2, 8.1](https://datatracker.ietf.org/doc/html/rfc4120)), `SRC-KILE` ([MS-KILE 3.3.5.1](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-kile/f5993d64-a280-4555-9fcc-922fb934fc27)), `SRC-WSMV` ([MS-WSMV 3.1.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wsmv/568385a0-0676-493f-bcd7-380b6e7cb7ee)), `SRC-PSRP` ([MS-PSRP 3.1.5.3](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-psrp/01b38726-b7d8-4c72-a924-a7168ce2f1d0)), và `SRC-PAC` ([MS-PAC 2.5](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-pac/69e86ccc-85e3-41b9-b514-7d969cd0ed73)).
Ánh xạ đồng bộ toàn bộ 11 câu hỏi tiền tố tới bảng nguồn này và phân định rõ ranh giới giữa cơ chế kỹ thuật và giả định kịch bản.
3. **Minh định Attribution và đồng bộ PR body:**
Đính chính attribution trong worklog và PR body, xác nhận rõ các đợt rà soát (comments 5929312919, 5929703729, 5930832730, 5932097631) là self-review rounds của TTS A, trong khi formal review từ TTS B (@nairyuuu) vẫn đang pending.
Đồng bộ mô tả phân tích độ nhạy trong PR body theo kết quả thực tế của executed sweep khi Candidate 2 giảm 10% cận trên làm sụp đổ biên Pareto về Candidate 1, và làm rõ phạm vi giả định cố định $u_2$ của khoảng cách đơn biến.
Cập nhật số liệu kiểm thử chính xác: 15/15 tests proposal, 104/104 focused ranking tests, 964 tests toàn repo pass sạch.

### Khắc phục chuẩn hóa cơ chế RFC 4120 và Handoff Scope Alignment (Iteration 4 - Self-review round 4)

Nhằm giải quyết triệt để phát hiện tại comment 5932097631 trước khi bước vào formal review của TTS B, TTS A đã hoàn thiện các nội dung sau:
1. **Chuẩn hóa cơ chế truyền vận và nguồn RFC 4120:**
Cập nhật bảng nguồn chuẩn tắc Mục 5.1 và chính sách thử lại Mục 5.2: dẫn chiếu chính xác RFC 4120 tới các mục §3.1 (*The Authentication Service Exchange*), §7.2.1 (*UDP/IP transport*), §7.2.2 (*TCP/IP Transport*), và §8.1 (*Specification 2*).
Phân định rõ ràng: RFC 4120 bắt buộc client và KDC hỗ trợ cả hai giao thức TCP và UDP (§8.1), quy định chuyển sang TCP khi gói tin UDP quá lớn hoặc KDC trả mã `KRB_ERR_RESPONSE_TOO_BIG` (§7.2.1), và cho phép client lựa chọn gửi thử UDP trước (§7.2.2).
Quy định client thử UDP trước với timeout 5 giây và tự động chuyển sang TCP khi gặp timeout hoặc mất gói là lựa chọn kịch bản được khai báo của nghiên cứu, không đồng nhất với quy chuẩn bắt buộc của RFC.
Đồng bộ căn cứ nguồn tại toàn bộ 4 câu hỏi liên quan ($q_2, q_5, q_7, q_{10}$).
2. **Minh định phạm vi đóng góp và trạng thái bàn giao (Handoff Scope Alignment):**
Làm rõ PR #161 là slice đóng góp giải quyết và đề xuất căn cứ kỹ thuật cho các parent issues #143, #42, #158, #48; các parent issues tiếp tục giữ trạng thái mở cho đến khi hoàn tất nghiệm thu toàn diện Week 3.
Xác nhận thiết kế và căn cứ tham số duy trì ở trạng thái Proposed / Insufficient Evidence, đang chờ formal review và phê duyệt độc lập từ TTS B (@nairyuuu).

### Khắc phục phản hồi review của TTS B: Thống nhất nghĩa của Network Reachability và Residual Uncertainty (Iteration 5 - Formal Review B)

Nhằm giải quyết triệt để phản hồi formal review của TTS B (@nairyuuu) tại [review 5380395316](https://github.com/nairyuuu/ad-weighted-graph/pull/161#pullrequestreview-5380395316) về tính nhất quán ngữ nghĩa giữa giả thiết `network_*_reachable` trong $S$ và căn cứ độ bất định dư thừa cho các cận có điều kiện $q_i$, TTS A đã lựa chọn phương án thống nhất chuẩn tắc:
1. **Minh định ngữ nghĩa của Network Reachability trong $S$:**
Các vị từ `network_rpc_reachable`, `network_kdc_reachable`, và `network_winrm_reachable` trong $S$ bảo đảm tính khả dụng liên tục của kênh truyền mạng tới Domain Controller và KDC xuyên suốt khung thời gian 24h của kịch bản.
Mọi rủi ro vật lý như đứt cáp mạng, phân vùng mạng (network partition), hay gián đoạn kết nối socket mạng kéo dài đã bị triệt tiêu và loại trừ hoàn toàn khỏi không gian điều kiện hóa dưới $S$.
2. **Loại bỏ sự cố mạng khỏi Residual Uncertainty:**
Rà soát và thanh lọc toàn bộ các giải trình độ bất định dư thừa trong dossier (`seamless-parameter-basis-proposal.md`) và bản ghi disposition (`path-ranking-acceptance-disposition.md`).
Tuyệt đối không sử dụng lại sự cố mạng, ngắt kết nối socket RPC hoặc mất kết nối mạng UDP/TCP để biện minh cho các cận thất bại $q_i < 1$ hay ranh giới 5% rủi ro tại cận trên của Kerberos.
3. **Căn cứ thuần túy trên tranh chấp tài nguyên máy chủ và tải hàng đợi:**
Toàn bộ các cận xác suất có điều kiện $[l_i, u_i]$ được neo vững chắc trên các rủi ro xử lý nội bộ phía máy chủ chưa bị $S$ loại trừ:
- Giao dịch SAMR RPC ($q_1, q_4, q_6, q_9$): Tranh chấp khóa ghi cơ sở dữ liệu NTDS/ESE trên DC hoặc cạn kiệt luồng worker của dịch vụ RPC máy chủ kéo dài vượt quá thời hạn 15 phút ($N=3$ lần thử).
- Giao dịch Kerberos AS ($q_2, q_5, q_7, q_{10}$): Tắc nghẽn hàng đợi xử lý yêu cầu của KDC hoặc cạn kiệt luồng worker của tiến trình KDC/LSASS khi giải mã pre-auth và dựng PAC dưới tải cao đột biến kéo dài vượt quá thời hạn 10 phút ($N=3$ lần thử qua UDP kèm TCP fallback).
- Phiên WinRM ($q_3, q_8, q_{11}$): Cạn kiệt hạn ngạch phiên làm việc máy chủ (`MaxShellsPerUser`, `MaxConcurrentUsers`) hoặc lỗi cấp phát bộ nhớ desktop heap cho tiến trình con `wsmprovhost.exe` kéo dài vượt quá thời hạn 30 phút ($N=3$ lần thử).
4. **Bảo toàn tính toán và giao diện:**
Các cận khoảng phân số $[l_i, u_i]$ và chi phí rubric $C$ giữ nguyên 100% giá trị số học, không làm thay đổi kết quả kiểm chứng roundtrip hay cấu trúc giao diện phân hạng.

### Luồng kỹ thuật: phân định thao tác thủ công so với hàm/script

Nhằm bảo đảm tính kiểm toán và phân định rõ ranh giới trách nhiệm, bảng dưới đây mô tả chi tiết phần việc đòi hỏi tư duy phân tích kỹ thuật của người chuẩn bị so với các bước thực thi tự động qua mã lệnh:

| Bước | Thao tác thủ công / Tư duy phân tích (TTS A) | Hàm / Script / Lệnh tự động đã thực thi |
| --- | --- | --- |
| Khởi tạo nhánh | Kiểm tra lịch sử git, xác nhận develop tại commit f92ed75 sau merge PR #159; tạo nhánh mới `docs/143-seamless-parameter-proposal`. | `git checkout -b docs/143-seamless-parameter-proposal develop` |
| Rà soát và cập nhật căn cứ kỹ thuật | Đối chiếu Open Specifications của Microsoft ([MS-SAMR], [MS-KILE], [MS-WSMV], [MS-PSRP]); phân tích các nguyên nhân bất định dư thừa sau khi đã điều kiện hóa các giả thiết S (lock contention, RPC timeout, clock skew, WinRM quota); loại bỏ việc dùng Event 4724 để tăng nỗ lực. | So sánh tham chiếu tài liệu nguồn mở với [attack_semantics.yml](../../configs/attack_semantics.yml) và catalog vị từ hiện có. |
| Bản ghi chuyển dịch thiết kế | Soạn thảo và chuẩn hóa Section 5 trong acceptance disposition; giới hạn phạm vi known-false veto vào required predicates; xác định danh mục canonical enum `independent` và wire alias `distinct_work`; phân loại chuẩn xác 25 giả thiết kịch bản. | Cập nhật tập tin [path-ranking-acceptance-disposition.md](../research/path-ranking-acceptance-disposition.md). |
| Xây dựng hồ sơ tham số | Soạn thảo hồ sơ căn cứ kỹ thuật toàn diện; tính toán tích khoảng phân số chính xác; giải trình chi tiết từng câu hỏi trong số 11 câu hỏi tiền tố; phân bổ chuẩn bị chung cho các đơn vị công việc; loại bỏ giả thiết tác động lan tỏa theo lộ trình. | Cập nhật tập tin [seamless-parameter-basis-proposal.md](../research/seamless-parameter-basis-proposal.md). |
| Sửa đổi công cụ kiểm chứng | Sửa vị trí bootstrap sys.path trước local imports; thiết kế phân tích độ nhạy lân cận (friction shift, strictly nested narrowing, overlap margin sweep) và các conformance probes; xuất đường dẫn tương đối di động. | Cập nhật và chạy `python scripts/research/seamless_parameter_validation.py --output reports/research/seamless-parameter-validation-report.json`. |
| Viết kiểm thử tự động | Bổ sung kiểm thử cho các kịch bản độ nhạy lân cận, probe dữ kiện sai không liên quan (irrelevant false no-op), và kiểm thử CLI entrypoint qua subprocess độc lập từ môi trường sạch. | Cập nhật `tests/test_seamless_parameter_proposal.py` và chạy qua `.venv/bin/pytest tests/test_seamless_parameter_proposal.py`. |
| Kiểm toán an toàn dữ liệu người chấm | Rà soát thủ công hai tệp JSON `seamless_rater_1.json` và `seamless_rater_2.json` để bảo đảm không có bất kỳ trường nào bị điền trước giá trị danh tính hay điểm số. | Hàm kiểm thử `test_actual_human_sheets_remain_untouched_and_pending()` tự động xác nhận 100% các trường đánh giá và danh tính đều mang giá trị null. |

## Điều học được / quyết định

1. **Nguyên tắc giải trình độ bất định dư thừa (Residual Uncertainty Principle):**
   - Khi các điều kiện tiên quyết đã được giả định là đúng trong $S$ (như tài khoản không bị khóa, Kerberos pre-auth được chấp nhận, kênh mạng khả dụng liên tục xuyên suốt horizon 24h, WinRM service đang chạy), không thể dùng lại chính các điều kiện này để giải thích vì sao xác suất $q_i < 1$.
   - Độ bất định dư thừa hợp lệ phải bắt nguồn từ các yếu tố ngẫu nhiên runtime chưa bị triệt tiêu bởi $S$: tranh chấp khóa ghi cơ sở dữ liệu NTDS/ESE hoặc cạn kiệt luồng RPC máy chủ, tắc nghẽn hàng đợi xử lý KDC hoặc cạn kiệt luồng LSASS dưới tải cao, cạn kiệt hạn ngạch phiên WinRM (`MaxShellsPerUser`), hoặc lỗi cấp phát bộ nhớ worker process (`wsmprovhost.exe`).
   - Các yếu tố như đứt cáp mạng, phân vùng mạng, ngắt kết nối socket RPC hoặc lệch pha đồng hồ (clock skew drift) không được dùng lại làm rủi ro dư thừa khi `network_*_reachable` đã giả định kênh truyền mạng khả dụng xuyên suốt khung thời gian 24h và bối cảnh thời gian hợp lệ.

2. **Chuẩn hóa neo ma sát tương tác ($T_2$) và tách biệt ghi nhận nhật ký:**
   - Theo đặc tả Interface 1.0.0 Mục 2.4, ma sát $T_2$ thuần túy đo lường thời gian và thao tác tương tác của kẻ tấn công (thao tác trực tiếp tức thì, session xác thực đa bước, hay tương tác người dùng).
   - Sự xuất hiện của nhật ký (như Event 4724 khi reset password) không chứng minh kẻ tấn công phải tốn thêm công sức, trừ khi có cơ chế phòng vệ tương tác chủ động cản trở.
     Do đó, việc loại bỏ nhật ký khỏi căn cứ tính $T_2$ bảo đảm tính nhất quán của rubric.

3. **Phân biệt giữa phân tích độ nhạy lân cận (Neighborhood Sensitivity) và kiểm tra bất biến (Conformance Probes):**
   - Kiểm tra bất biến ép xác suất điểm, ép ưu thế, hoặc thử veto là để xác nhận thuật toán hoạt động đúng đặc tả.
   - Phân tích độ nhạy thực sự quanh đề xuất đòi hỏi nghiên cứu sự biến thiên của kết quả khi nhiễu loạn các tham số lân cận: việc tăng ma sát $T_2$ trên đường Lidia làm đảo chiều kết quả Min-Effort-to-DA từ Candidate 1 sang Candidate 2, trong khi biên Pareto bảo thủ vẫn giữ nguyên tính chất không so sánh được.
   - Nhận định "ALL PASSED" chỉ chứng minh tính đúng đắn của vết tính toán và kiểm tra hành vi, không chứng minh tính vững chắc hay độ tin cậy tuyệt đối của tham số khi chưa có đánh giá thực nghiệm.

4. **Giới hạn phạm vi phủ quyết (Scoped Veto Invariant):**
   - Quyền phủ quyết của dữ kiện sai (`false_facts`) và withholding của dữ kiện thiếu (`unknown_facts`) chỉ áp dụng trên tập các vị từ tiên quyết bắt buộc (required predicates) của từng ứng viên cụ thể.
   - Sự tồn tại của các vị từ sai hoặc thiếu không liên quan trong facts ledger không áp đặt phủ quyết toàn cục lên toàn bộ truy vấn.

5. **Tính di động của công cụ CLI và kiểm thử entrypoint:**
   - Đặt bootstrap `sys.path` trước các local imports là bắt buộc để hỗ trợ chạy script trực tiếp (`python script.py`) từ môi trường chưa cài đặt repo như một package.
   - Kiểm thử unit test gọi trực tiếp `main()` không kiểm tra được luồng import ở cấp module; kiểm thử qua `subprocess.run()` là tiêu chuẩn bắt buộc để phát hiện lỗi entrypoint.

6. **Độ nhạy lũy tích của chuỗi hành động nhiều bước (Compound Sensitivity):**
   - Phân tích đơn biến khi giữ cố định $u_2 = 0.55233$ cho thấy $l_1$ cần tăng $+64.4\%$ ($+0.21633$) để phá vỡ thế giao nhau.
   - Tuy nhiên, khi toàn bộ 5 bước của Candidate 2 cùng giảm $10\%$ cận trên, cận trên lũy tích $u_2$ sụt giảm từ $0.55233$ xuống $0.32615$, rơi xuống thấp hơn $l_1 = 0.336$.
   - Biên Pareto lập tức đảo chiều (flip) và sụp đổ về chỉ còn Candidate 1.
   - Việc tránh các tuyên bố tổng quát hóa quá mức và thực thi kiểm thử quét kịch bản thực tế là tối quan trọng để phản ánh trung thực đặc tính nhạy cảm của mô hình.

7. **Tính nhất quán giữa giả thiết kịch bản và không gian điều kiện hóa xác suất:**
   - Xác suất $q_i$ được điều kiện hóa trên $S$ ($q_i = P(E_i \mid F, S, \dots)$), do đó mọi sự kiện đã bị $S$ loại trừ thì không thể đồng thời xuất hiện trong không gian mẫu của residual uncertainty.
   - Khi $S$ tuyên bố kênh mạng khả dụng xuyên suốt horizon 24h, việc sử dụng mất kết nối mạng để giải thích cận thất bại của $q_i$ sẽ vi phạm nguyên lý điều kiện hóa toán học.
   - Việc quy chuẩn các căn cứ thất bại về nội bộ máy chủ (server-side contention, queue exhaustion, heap exhaustion) khép kín tính nhất quán logic mà vẫn phản ánh đúng thực tế vận hành phức tạp của Active Directory.

## Trở ngại và việc kế tiếp

- Cập nhật commit mới lên nhánh `docs/143-seamless-parameter-proposal` và đẩy lên origin.
- Cập nhật mô tả PR [#161](https://github.com/nairyuuu/ad-weighted-graph/pull/161) với commit head mới và tóm tắt Iteration 5.
- Phản hồi chi tiết bằng chứng khắc phục review của TTS B tại PR [#161](https://github.com/nairyuuu/ad-weighted-graph/pull/161).
- Kính mời TTS B (@nairyuuu) tái rà soát exact head mới.
- Giữ nguyên trạng thái mở cho các Issue cha (#143, #42, #48), không tự ý merge PR.
