# Báo cáo tuần 3 - Mô hình đánh giá đường tấn công và quy trình dựng đồ thị

**Cập nhật kết quả ngày 06/10/2026.**
Bộ tham số đã được người phụ trách chọn; thiết kế/giao diện và tham số có phạm vi đã được tiếp nhận.
Luồng tự sinh ứng viên, semantic bridge và xếp hạng đã được nghiệm thu; đối chứng cấu trúc theo phạm vi chung và tái lập sạch hai phía đã được tiếp nhận.
Lượt kiểm chứng hiện hành dùng integrated revision `891bda0001b9958e712cff54045f651273b43fd0` (A đo E2E trên CPython 3.14.2/Linux, B đo fresh Legacy replay và comparator CLI exit 2 trên CPython 3.14.7/Windows); final revision binding đã hoàn tất và B đã chấp thuận package.

## 1. Mục tiêu và kết quả chính

Tuần 3 tập trung xây dựng quy trình chuyển dữ liệu Active Directory thành đồ thị có nguồn gốc kiểm chứng được, đồng thời định nghĩa cách đánh giá một chuỗi hành động tấn công theo công sức, khả năng thành công và tác động tới tài sản đích.

- Đã có quy trình đọc dữ liệu, xác minh bản kê toàn vẹn, chuẩn hóa danh tính, xử lý bản ghi trùng và tạo nút/cạnh theo hợp đồng dữ liệu.
- Đã tách quan hệ cấu trúc khỏi hành động: mỗi hành động có chủ thể, mục tiêu, điều kiện và hiệu ứng lên trạng thái giả định.
- Đã triển khai bộ đánh giá chuỗi hành động, phân biệt điều kiện đúng, sai, giả định và chưa biết; có giải thích các trường hợp bị loại.
- Đã có hai phiếu chấm được tiếp nhận, mỗi phiếu 21 mục, cùng chính sách thực hiện và nguồn lý giải.
  Hai phiếu có AI hỗ trợ và công bố việc đã tiếp xúc điểm nhau; không tuyên bố chấm mù độc lập.
- Đã có công cụ đối soát, xuất bộ tham số có phiên bản, kiểm tra lại nguồn và chạy phân tích độ nhạy.
  Đã chốt 21 lựa chọn, xuất bộ tham số và kiểm chứng trên ba đường ứng viên.
- Đã nối raw → đồ thị → tự sinh ứng viên có giới hạn → bound actions/scenario → đánh giá → Pareto và công sức nhỏ nhất riêng; cùng ma trận tám ca thành công, sai, chưa biết và thiếu bằng chứng.
- Đã fix PrimaryGroupSid; đồ thị hiện có 3.370 nút, 56.367 cạnh và 3 đánh giá CanRDP chưa biết.
- Đối chứng theo exact directed sets đã được tiếp nhận trong từng phạm vi; full Legacy comparator vẫn `NOT_MEASURABLE`, không tuyên bố tương đương toàn sản phẩm.

## 2. Phần TTS A: mô hình và cách tính

Mỗi đường được đánh giá bằng ba đại lượng riêng:

| Đại lượng | Cách xác định | Ý nghĩa |
| --- | --- | --- |
| Công sức C | Cộng công sức các đơn vị công việc khác nhau; mỗi đơn vị dùng C_u = T1 + T2 − 2 | Chỉ số theo bảng tiêu chí, không phải số phút hoặc xác suất |
| Khả năng thành công P | Nhân các xác suất từng bước với điều kiện mọi bước trước đã thành công | Nhận định theo kịch bản, biểu diễn bằng khoảng |
| Tác động I | Đánh giá hậu quả khi đạt sự kiện thành công lên tài sản/dịch vụ đích | Không suy trực tiếp từ nhãn máy chủ hoặc nhóm đặc quyền |

T1 là độ phức tạp kỹ thuật, T2 là mức phối hợp/thao tác cần thiết; mỗi điểm thuộc 1–3.
C của một đơn vị công việc thuộc 0–4.
Không tính lại phần chiếm điểm xuất phát, phần chuẩn bị chung hoặc công việc đã thực hiện; quan hệ nhóm thụ động không tự tạo thêm công sức.

Với F là điểm xuất phát đã bị kiểm soát, S là kịch bản và E_i là thành công của bước i:

$$P(E_1,\ldots,E_k\mid F,S)=\prod_{i=1}^{k}P(E_i\mid F,S,E_1,\ldots,E_{i-1}).$$

Đây là quy tắc chuỗi, không giả định các bước độc lập.
Các cận số hiện là nhận định dưới giả định công bố, chưa phải tần suất đo.
Nguồn kỹ thuật giải thích cơ chế và điều kiện; không cung cấp trực tiếp các con số xác suất.

Một chuỗi cần thêm bước thành công sẽ có P không tăng nếu giữ nguyên tiền tố và điều kiện.
Điều này phù hợp với định nghĩa “toàn chuỗi thành công”; không có nghĩa mọi đường dài đều kém mọi đường ngắn, vì các hành động và xác suất có điều kiện có thể khác nhau.

Xếp hạng dùng Pareto bảo thủ trên I và khoảng P, giữ các trường hợp chưa phân định được.
Công sức được báo riêng; truy vấn công sức nhỏ nhất có kết quả riêng.
Chỉ dùng công sức phá hòa trong điều kiện hẹp của mô hình đã định nghĩa, không cộng tùy ý ba đại lượng thành một điểm chung.

## 3. Kịch bản chấm và kết quả tính cụ thể

Phạm vi gồm hai điểm xuất phát trong SEAMLESS, ba đường ứng viên và đích là thực thi quản trị trên máy chủ miền.
Ba cơ chế chủ yếu là reset mật khẩu, lấy vé Kerberos và thực thi qua WinRM.

- Mỗi phiếu có 1 mức tác động, 9 định mức công sức và 11 xác suất theo đầy đủ lịch sử của từng đường.
- Tối đa 3 lần thử cho mỗi bước; thời hạn reset/lấy vé/WinRM lần lượt 15/10/30 phút; kịch bản kéo dài tối đa 24 giờ.
- A/B cùng chọn tác động Cao (`High`) và công sức reset/lấy vé/WinRM là 1/0/1.
- Đối soát khớp đủ 21 cặp; công sức không chênh lệch.
  Các khoảng P khác nhau vẫn được giữ trong hồ sơ.
  Chỉ số chồng lấn trung bình khoảng 0,5813 mô tả hai bộ phiếu; không phải bằng chứng về độ đồng thuận giữa các đánh giá độc lập của con người.

**Bộ số đã chọn:** giữ các khoảng rộng đã được B tiếp nhận qua xác nhận do A chuyển đạt, lần lượt [0,60; 0,95], [0,75; 0,98], [0,50; 0,90].
Các khoảng này chứa khoảng A tương ứng, nên người phụ trách chọn giữ bất định hiện có thay vì thu hẹp khi chưa có dữ liệu mới.

| Đường ứng viên | P từ bộ đã chọn | C | I |
| --- | --- | ---: | --- |
| Điểm xuất phát A → Lidia → đích | [22,5%; 83,79%] | 2 | High |
| Điểm xuất phát A → Josefa → Ollie → đích | [10,125%; 78,00849%] | 3 | High |
| Điểm xuất phát B → Ollie → đích | [22,5%; 83,79%] | 2 | High |

Ví dụ đường qua Lidia: cận dưới là 0,60 × 0,75 × 0,50 = 0,225; cận trên là 0,95 × 0,98 × 0,90 = 0,8379; công sức là 1 + 0 + 1 = 2.

Phép tính phân số chính xác khớp bộ đánh giá.
Hai đường từ điểm xuất phát A vẫn chưa phân định được bằng Pareto bảo thủ do các khoảng chồng lấn; đường qua Lidia có công sức thấp nhất trong tập ứng viên đủ điều kiện đã đánh giá.
Hai điểm xuất phát được xét thành hai truy vấn riêng.
Kết quả tính của supplied replay khớp các programs do generator thực sinh trong nghiệm thu có giới hạn; chưa chứng minh tối ưu toàn đồ thị.

### Kiểm chứng và độ nhạy

Công cụ đã phát lại khai báo để kiểm tra tính nhất quán của bộ tham số, rồi đối chiếu kết quả tính phân số với engine.
21 phép thử cục bộ gồm: giảm khoảng xác suất của từng mục xuống 90%, tăng một điểm tiêu chí công sức của từng đơn vị và hạ tác động từ High xuống Medium.
Có 24 kết quả truy vấn do một số tham số dùng chung giữa hai điểm xuất phát.
Không phép thử nào đổi tập Pareto, quan hệ giữa ứng viên hoặc danh tính đường công sức nhỏ nhất; sáu kết quả thay đổi giá trị công sức nhỏ nhất.

Kết luận ổn định chỉ áp dụng cho các phép thử này và ba ứng viên đã cung cấp.
Chưa kiểm tra thay đổi đồng thời nhiều tham số hoặc tìm đường toàn đồ thị.
Lượt kiểm chứng trên engine hiện hành giữ nguyên kết quả C/P/I, quan hệ Pareto, đường công sức nhỏ nhất và digest của validation report khi phát hành.
Các ca phủ định quyền ghi, chưa biết điều kiện runtime, thiếu nguồn cấu trúc và thiếu thông tin enabled đã phát lại riêng; chuỗi liên quan bị chặn hoặc giữ chưa biết, không nhận số C/P và không vào frontier.
Các ca phản thực tế này cũng đã được kiểm qua tìm kiếm thật, với exact designated decisions và evidence delta; raw observation và counterfactual variant vẫn được phân biệt.
[Hồ sơ bộ tham số](../research/ratings/week3-closeout/README.md) lưu nguồn và lựa chọn; [ma trận kiểm chứng](week3-acceptance-matrix.md) lưu expected/actual, revision, digests, bindings và lệnh chạy lại.

## 4. Phần TTS B: quy trình dựng đồ thị và bộ đánh giá

Luồng cấu trúc đã có: dữ liệu thô → bản kê/kiểm tra toàn vẹn → đọc bản ghi → chuẩn hóa và đối soát danh tính → dựng nút/cạnh → xuất đồ thị JSON có nguồn gốc.
Mỗi cạnh cần truy được về dữ liệu cấu trúc hỗ trợ nó; bằng chứng chưa đủ được báo trong chẩn đoán, không tự tạo thành kết nối quan sát được.

Bộ đánh giá đã nhận truy vấn/kịch bản và các chuỗi hành động được cung cấp, phát lại trạng thái, kiểm tra điều kiện, tính C/P/I và xuất kết quả xếp hạng cùng lý do.
Bộ tìm kiếm có giới hạn và adapter nối kết quả tìm kiếm vào bộ đánh giá đã được tích hợp.
Luồng dữ liệu thô → tự sinh ứng viên → đánh giá với bộ tham số đã chọn đã được nghiệm thu cho tám ca thành công, bị chặn, chưa biết và thiếu bằng chứng.
Generated candidate IDs giữ nguyên qua xếp hạng; mapping sang reviewed programs chỉ dùng đối chiếu sau đánh giá.
Source A positive có 23 paths sinh ra, chạm 60.000 expansions và giữ trạng thái truncated; frontier/công sức nhỏ nhất chỉ mô tả tập đủ điều kiện đã đánh giá.

Kiểm thử dữ liệu tổng hợp đã bao phủ tám loại quan hệ chính, hướng cạnh, cạnh song song, trùng lặp, một số ca thiếu/sai bằng chứng và bảo toàn nguồn.
Đối chứng cùng snapshot BloodHound Legacy 4.0.3/Neo4j 4.1.13 đã có exact-set proofs và giải thích toàn bộ 20 M1 differences theo comparison contract được tiếp nhận.

| Phạm vi | Verdict được tiếp nhận |
| --- | --- |
| MemberOf full direct | 15.917 triples bằng chính xác Members ∪ PrimaryGroupSid; không còn gap primary group |
| GenericAll / WriteDacl non-self | 37.034 / 3.392 triples bằng chính xác; self-ACE 10/3 là khác policy |
| AdminTo / CanPSRemote direct | 5 / 2 triples bằng chính xác; 4 derived-only AdminTo là khác policy |
| CanRDP | 3 unknown assessments, 0 positive edges ở project; khác với 3 Legacy structural triples theo policy đã tiếp nhận |
| ForceChangePassword / HasSession | Không có observations trong snapshot; giữ `not_measurable` |
| Full Legacy comparator | `NOT_MEASURABLE` / exit 2; không nâng thành full BloodHound/CE parity |

Hai phía đã tạo lại project graph từ raw trong checkout sạch và kiểm exact proofs bằng checksum-pinned external inputs.
Lượt fresh replay của B trên `891bda0001b9958e712cff54045f651273b43fd0` từ checkout sạch bằng harness `reproduce_legacy_reconciliation.py` đã xác nhận: graph `code_version` và report `head_commit` khớp `891bda0`, comparator API verdict `NOT_MEASURABLE` (expected exit code 2), và comparator CLI thật quan sát exit code 2.
Mọi slice exact sets, 20 sanitized difference entries và multiplicity đều trùng khớp tuyệt đối với accepted #196.
Run A/B lịch sử của #196 giữ measured SHAs riêng (`cc5f971` / `8535d4`); fresh replay trên `891bda0` hoàn thành binding cuối cùng cho package.

## 5. Phần thủ công và phần tự động

Nhóm chọn phạm vi, tài sản đích, giả định, các điểm T1/T2, khoảng xác suất và mức tác động cùng lý do; AI hỗ trợ nghiên cứu, giải thích và soạn hồ sơ.
Các giá trị đó có trong `parameter-decisions-final.json`; hàm `export_release` trong `scripts/research/reviewed_parameter_release.py` chỉ gắn lựa chọn vào đúng action/work/prefix và xuất `reviewed-release.json`.
Hàm `verify_release` phát lại declarations, so nguồn/digests và hai projections trước khi cho phép tiêu thụ; Source A và Source B luôn là hai truy vấn riêng.

Với mỗi projection, `PathRankingEngine.evaluate` trong `src/engine/ranking/__init__.py` kiểm schema/bindings và gọi `resolve_facts_ledger` để phân giải các lớp bằng chứng.
`replay_candidate_sequence` kiểm điều kiện trước hiệu ứng, giữ false veto/unknown và dừng khi đạt goal lần đầu.
`assess_candidate_program` lấy ordered work units, bỏ lần tham chiếu lặp, cộng T1+T2−2 và nhân các cận conditional bounds bằng phân số chính xác theo toàn bộ tiền tố.
Impact lấy từ record của target asset và success event đã chọn; không tự suy từ nhãn máy chủ hoặc nhóm.
`scoped_frontier` và `compute_min_effort_baseline` trong `src/engine/ranking/frontier.py` lần lượt giữ Pareto bảo thủ và tìm công sức nhỏ nhất trong tập đủ điều kiện đã đánh giá.
`analytical_expectations` là oracle số độc lập cho ba positive programs, không thay bộ phân giải false/unknown hoặc generator.

Lệnh `.venv/bin/python scripts/research/reviewed_parameter_release.py validate --release docs/research/ratings/week3-closeout/reviewed-release.json --output reports/generated/week3-177/validation.json` chạy verify, engine/oracle và sensitivity.
Lệnh `.venv/bin/python tests/test_week3_acceptance_manifest.py` phát lại hai projections và các variants có tên, kiểm ordered bindings/work basis/success event và lưu inputs/results vào thư mục ignored.
Công cụ không tự suy ra xác suất thực nghiệm từ ảnh chụp Active Directory; không mô phỏng retry/thời hạn và không dùng supplied-candidate replay làm bằng chứng tự tìm đường toàn luồng.
Lệnh raw E2E dùng `scripts/research/week3_engine_acceptance.py --require-complete`; hàm `generate_and_evaluate_attack_paths` gọi generator thật, adapter và canonical evaluator.
Harness kiểm named evidence views/overlays, ordered programs, exact metrics, frontier, Min-Effort và designated false/unknown decisions; người review đối chiếu phạm vi/rationale với evidence.
[Final handoff/brief demo](week3-final-handoff.md) lưu lệnh cụ thể và [manifest](../../reports/research/week3-final-handoff.json) lưu runtime, input/output digests và gate còn lại.

## 6. Giới hạn và công việc còn lại

- Bộ tham số được tiếp nhận cho kịch bản tuần này.
  Chưa thực hiện nghiên cứu độ đồng thuận giữa các người chấm độc lập; giới hạn đó không được suy thành độ tin cậy thống kê từ IoU.
- Luồng tìm kiếm/xếp hạng đã được nghiệm thu, vẫn bounded/truncated; không claim global optimum hoặc global absence từ empty result.
- Đối chứng/reproduction đã được tiếp nhận trong exact-set scope; full Legacy comparator vẫn `NOT_MEASURABLE`, không claim full BloodHound/CE parity.
- Fresh Legacy replay & final revision binding trên `891bda0` đã được B hoàn thành với authorized private prerequisites; package #48/#158 đã được B review và chấp thuận.
- Week 4 research giữ phạm vi riêng; không kéo tìm kiếm mở rộng/Top-K/choke points vào closeout tuần 3.
- Chưa hiệu chuẩn xác suất bằng thực nghiệm; chưa tuyên bố đã thực hiện chuỗi tấn công thật.
  Dữ liệu cấu trúc và các giả định giới hạn phạm vi kết luận.

Kết quả tuần này cung cấp mô hình, hồ sơ tham số và các thành phần thực thi để đánh giá đường tấn công trong kịch bản công bố.
Nghiệm thu package cuối #48/#158 đã được B xác nhận; việc merge PR và release promotion review cho #186 sẽ thực hiện theo quy trình repo.
