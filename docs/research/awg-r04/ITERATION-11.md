# Iteration 11 — danh tính máy tường minh trong discovery/batch

**Đã đưa machine identity vào workflow tự chọn đích, giữ ranh giới với quyền trên host.** Native integration/captures sạch tại `4c920a1f0f2997dd4b6f26320fc2819d3ac3a07d`, parent `dafde9b1c8e768d18492425ed278a83155197350`. [Evidence](evidence/iteration-11-machine-profile.json), [exact harness](evidence/machine-discovery-harness.txt). Search/evaluator/replay/cost không đổi.

## Hành vi mới và contract

`--computer-profile computer_usable_identity` khai báo tài khoản máy đã có network identity dùng được tại một Computer context cụ thể. Initial state chỉ có `known_identity(machine)` và `usable_identity(machine, context)`. Nó không cấp local shell/admin, credential artifact hay danh tính User. Đây là đầu vào giả thiết của analyst, không phải snapshot tự xác minh đăng nhập hoặc P=1.

Bắt buộc `--authentication-context` và `--machine-identity-provenance`. Factory kiểm source/context tồn tại, đều là Computer không boundary, cùng domain xác định; source snapshot `enabled=False` bị veto. Context/provenance thiếu hoặc sai không tạo capability. Khi source enabled Unknown, runtime guard vẫn Unknown; declaration không tự sửa snapshot.

`batch-query-request/1.1.0` và `foothold-profiles/1.1.0` nhận profile mới;1.0 từ chối nó. Legacy request serialization giữ1.0 và không thêm field provenance=null. `identity_provenance_reference` được giữ trong request của result, source/cell/scope fingerprints; thay reference khiến resume bị từ chối và scenario identity đổi. Worker và public query giữ đúng identity/context. URI là nguồn khai báo, không xác thực sự kiện bên ngoài.

Profile local shell/admin vẫn giữ nguyên và không tự activate machine identity. Nếu cần đồng thời local admin và network identity, public query vẫn có thể khai báo hai capability riêng; profile mới không đại diện mọi dạng compromise Computer. HasSession untyped material→identity vẫn unsupported.

## Full-SEAMLESS đã thực thi

Hash-check đủ6raw files theo manifest cũ; snapshot vẫn3.370nodes/56.367edges. Independent stdlib đọc raw ACE của FINWVIR (`...4157`) trên DENA (`...2799`) và membership DENA→DA (`...512`). Cùng7runtime assumptions như iteration10, ba techniques, max1path/3steps/10.000exp mỗi query, global30.000exp/3cells. Inventory tự chọn DC/DA/EA, không nhập target hoặc path cho CLI.

| Auto goal | Local shell | Machine identity khai báo |
| --- | --- | --- |
| DC `...1000` | blocked,2.494exp | truncated_incomplete,7.490exp |
| DA `...512` | blocked,2.494exp | truncated_success,4.996exp,1witness |
| EA `...519` | blocked,2.494exp | truncated_incomplete,7.490exp |

Hai runs có inventory/selection byte-identical:2.590eligible sources,12important targets; chọn1×3pairs,31.077pairs ngoài cohort. Đây là **ba distinct pairs với hai capability declarations**, không phải sáu distinct pairs. Machine profile không được quảng cáo làm tăng reachability từ cùng một initial state: nó giúp khai báo một initial capability khác qua workflow chuẩn. Code core trước đó đã biểu diễn được identity này bằng query thủ công.

**Verified:** native API và batch paths của ca DA bằng nhau, một native replay pass. Source/context identity đúng; initial host control/admin/password và User identity đều rỗng. C/P/I không được adopt;0effort-rated/0likelihood-rated cells, technical target impact vẫn Unknown. Positive native minimum/no-path proofFalse, path-limit truncated. Hai đích còn lại chưa được kết luận. Local blocked/no_path proof chỉ áp dụng trong capabilities/ba techniques/budgets đã khai báo, không phải host an toàn.

Full result/checkpoint được giữ, lần lượt local~139,94/132,12MB và machine~361,78MB/156bytes. Machine checkpoint chưa có reusable completed cell vì cả ba đều truncated; resume behavior được kiểm trên finite completed fixture. Không claim cache hit trên fullraw. Public evidence bỏ verbose cell diagnostics, ghi exact counts và pin cả full native captures/full experiment. Không so tốc độ hai profiles vì capabilities khác nhau; không có performance hoặc remediation gain mới.

## Validation và compatibility

- **227 selected PASS/13,85s**, trong đó35checks mới: capability separation, versioned schema/legacy refusal, context/domain/boundary/provenance validation, disabled/Unknown account, worker/API/CLI/resume, source isolation và provenance-driven cache refusal. Có overlap với suites trước; không whole-suite claim.
- Existing12-case Computer oracle vẫn pass; local-only false positive không quay lại. R1/R2/R3, source authority, native C-only và old batch contracts nằm trong selected run.
- **V12 acceptance file pins vẫn bằng current files.** Không thay `src/`, numeric, catalog hoặc acceptance-pinned files, nên không tạo source/acceptance successor chỉ để tăng version. Final clean test sẽ tái chạy các Week4 assertions.
- Ruff581files/contractpass. First development failures thuộc fixture mới thiếu Domain node và kỳ vọng sai về disabled-source inventory exclusion. Đã sửa fixture/expectation, không nới production guards.
- **Final clean `7119371`: 504/504 PASS/123.56s, zero skip**, gồm các Week4 assertions/source-history/CLI/worker/binding/C-only/AS-REP/RBCD và old/new source contracts. [Closeout/JUnit](evidence/iteration-11-closeout.json). Captured code/schema và v12 pins bằng current bytes; mọi jobs complete, không pending. Historical R03ZIP là known inaccessible artifact; không coi đây là regression mới.

## Đối chiếu mục tiêu và việc tiếp

| Mục tiêu | Tiến bộ vòng này | Giới hạn |
| --- | --- | --- |
| Computer→đích quan trọng | Một CLI profile mới, mục tiêu tự chọn, fullraw conditional witness/replay | Chưa tự chứng minh machine credentials, HasSession composition còn thiếu |
| Chi phí thấp nhất | Shared-work/scoring guards giữ nguyên | Machine C chưa có applicable basis, không transfer C/P/I của User |
| Nhiều nguồn–đích/choke point | Source isolation, worker và transport đã kiểm | Không có số remediation hoặc full-system coverage mới |
| So sánh alternative | Không thêm engine hay rule system; tái dùng native semantics | Fresh BloodHound CE comparator vẫn open |

**Giữ planner; hoàn thiện semantics trước.** P0 tiếp là một oracle nhỏ cho typed HasSession composition: opaque material không phải password, owner/context/host-admin phải đủ, Unknown/False không tạo identity. Raw có0Sessions nên thí nghiệm đầu dùng synthetic fixtures, không giả fullraw acceptance. ForceChangePassword composition tiếp theo; source/preparation reuse làP1. Chưa production AND–OR, chưa invent P hoặc global optimum.

Tái hiện: chạy harness với `--repo`, `--snapshot`, `--raw`, `--manifest`, `--reference-query` là [public query iteration10](examples/computer-explicit_machine_identity.json), `--output` mới. Actual commands và hashes nằm trong evidence; harness không có AD/network operation. README có lệnh discovery trực tiếp và [request1.1 đã sinh](examples/machine-discovery-request.json).
