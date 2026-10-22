# Khép lỗi LocalGroup theo SID của host

Từ mốc `main@5c6f7c2`, parser nay nhận `LocalGroups[].ObjectIdentifier = <ComputerSID>-544` đúng trên Computer sở hữu SID đó.
**Hai cặp TRUSTER→DA/EA đã có witness, C=3; neo đạt 22/24 cặp, không mất kết quả cũ.**
[Summary và hash evidence](localgroup-fix-results.json) giữ kết quả trước/sau; [đối chứng CE trước sửa](bloodhound-comparison.md) được giữ nguyên như baseline lịch sử.

## Sửa đúng ngữ cảnh

Helper dùng riêng tại ba đường đọc LocalGroups: membership dương, trạng thái collection và assessment thất bại.
Dạng mới chỉ nhận từ ObjectIdentifier khi host có kind Computer, SID hợp lệ và toàn bộ ID khớp chính xác `<SID của host>-544`, có chuẩn hóa hoa/thường và khoảng trắng ngoài.
Không nhận SID của host khác, SID miền kết thúc bằng RID 544, chuỗi hỏng, số 544, hậu tố 0544/544-1 hoặc trường Name/GroupSID cho dạng rút gọn này.
Các SID builtin đầy đủ, scoped SID và dạng lịch sử tiếp tục qua parser cũ.
Không mở rộng cách nhận dạng RID 555/580 hoặc suy machine network identity.
Collection thiếu vẫn unknown; collection/group lỗi giữ assessment unknown và không phát AdminTo.
Thêm chốt bỏ qua Results con khi chính collection LocalGroups báo thất bại; không làm mất bằng chứng LocalAdmins độc lập đã đọc trước đó.
Search engine, attack state, preset và bảng C giữ nguyên; source pin thực thi chỉ thay đổi `src/parser/inference.py`.

## Raw → snapshot → cohort

Trước sửa đã tái hiện bằng importer và query native thật: thiếu bốn AdminTo trực tiếp, TRUSTER trả no_path cho cả DA/EA.
31/31 file raw ad_sampledata đúng manifest; cả trước và sau chỉ chọn prefix `20240305111414`.
Snapshot giữ nguyên 150 node, assessments và toàn bộ cạnh cũ; tổng AdminTo tăng **10→22**:

- Bốn cạnh trực tiếp: TRUSTER và Domain Admins, mỗi nguồn tới EXTCA01 và UNCON.
- Tám cạnh suy diễn: ADMINISTRATOR, BM, JACK, XADMIN tới hai host trên, do resolver membership hiện có.

Bốn cạnh trực tiếp có `evidence_type=positive`, `record_id` đúng SID host, `attribute=LocalGroups[].Results[]`, nguồn `20240305111414_computers.json`.
Đã đối chiếu từng cạnh với Results của đúng LocalGroup `<host SID>-544` có Collected=true trong raw.
Graph parity trên inventory CE đã lưu không còn AdminTo chỉ CE giữa các node chung.
11 AdminTo chỉ neo là cạnh membership suy diễn; self-ACE, boundary và hai MemberOf bổ sung của CE vẫn là các khác biệt đã giải thích ở baseline.
Raw manifest và hash inventory/query/checkpoint CE được xác minh lại; không chạy lại CE hoặc đụng Docker/database trong lượt sửa này.

| Cohort cố định | Neo trước | Neo sau | CE đã lưu |
| --- | ---: | ---: | ---: |
| SEAMLESS chính | 10/10 | 10/10 | 10/10 |
| WRAITH chính | 6/10 | 8/10 | 8/10 |
| WRAITH session | 6/6 | 6/6 | 6/6 |
| Khử trùng | **20/24** | **22/24** | **22/24** |

Đủ 26 lượt, cùng source/target, request, scenario policy, techniques và budget 10 chương trình, 12 bước semantic, 4.096 expansions/query; EXTDC01 bị trùng giữa hai nhóm WRAITH nên còn 24 cặp duy nhất.
Các cặp trước đây có witness giữ nguyên C, candidate/program ID, số bước của từng candidate và Top-3; không chỉ giữ nguyên số lượng đạt đích.
Scope/query hash và audit binding thay đổi theo snapshot/parser mới; chương trình và thứ hạng cũ giữ nguyên.
Không có error, Unknown attempt hoặc cặp mới âm tính do expansion cap.
TARGETCOMPUTERC vẫn bị chặn bởi thiếu danh tính mạng của máy trong preset local-admin-only.

Chỉ hai cặp TRUSTER thay đổi: `no_path → success`, C trống→3, 24 expansions/query, mỗi query tìm được 10 chương trình.
Witness tốt nhất đi qua **TRUSTER → admin execution trên EXTCA01 → session BM → entitlement DA/EA**.
Witness tới EA có thêm entitlement DA với C=0 trước EA; đây là chương trình semantic được replay, không phải đường tối thiểu số hops.
C=3 gồm thực thi admin C=1, lấy/dùng credential session C=2, membership có sẵn C=0; không lấy số cạnh làm công sức.
CE đã lưu chọn nhánh UNCON, còn neo chọn EXTCA01: raw có cả hai quyền AdminTo và cả hai session BM, nên khác host trung gian vẫn phù hợp cùng scenario và C=3.
Native replay độc lập cả **20/20 chương trình TRUSTER** đều khớp final state; Top-3 có C=3,3,5 và toàn bộ 10 candidate có C từ 3 đến 9.
Các chương trình tốn hơn dùng thêm thao tác trong catalog hiện có; không đổi rubric hoặc lọc cohort để cải thiện kết quả.

## Kiểm chứng và tái lập

**228 tests pass**, Ruff pass; 20 case mới tập trung vào ownership, ID sai/hỏng, trường dữ liệu, provenance và trạng thái thất bại, cùng các test định dạng cũ/missing collection.
Review độc lập không có phát hiện cần sửa.
Evidence lớn nằm local ở `reports/generated/localgroup-fix-20261022/`, gồm snapshot trước/sau, 26 checkpoint có checksum, graph delta, parity CE, query/ledger và replay TRUSTER; không commit raw/generated.

Để tái lập, chạy từ repo root với output directory mới:

```sh
run=reports/generated/localgroup-fix-repeat
.venv/bin/python -m scripts.neo_import --raw-dir data/raw/ad_sampledata \
  --manifest data/samples/manifests/ad-sampledata-v1.json \
  --time-policy data/samples/time-policies/ad-sampledata-v1.json \
  --export-prefix 20240305111414 --output-dir "$run/inputs/wraith"
.venv/bin/python -m scripts.neo_import --raw-dir data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --time-policy tests/fixtures/ranking/seamless_time_policy.json \
  --output-dir "$run/inputs/seamless"
.venv/bin/python -m scripts.neo_bloodhound \
  --seamless-snapshot "$run/inputs/seamless/snapshot.json" \
  --wraith-snapshot "$run/inputs/wraith/snapshot.json" --output-dir "$run/native"
sh "$run/native/neo-commands.sh"
```

C vẫn best-found trong budget, dưới giả định session/credential dùng được; 22/24 không chứng minh ngang toàn bộ tính năng BloodHound.
Chưa chạy full suite hoặc chạy lại remediation; các kết quả remediation trước vẫn thuộc mốc đối chứng cũ.
Các ràng buộc hash/catalog lịch sử được giữ ngoài scope, không sửa hàng loạt để làm xanh suite.
