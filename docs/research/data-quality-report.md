# Báo cáo Chất lượng Dữ liệu, Dữ liệu Thiếu và Độ Bao phủ

Tài liệu này thực hiện đánh giá chất lượng dữ liệu, kiểm toán dữ liệu thiếu (missingness audit) và phân loại ngữ nghĩa dữ liệu (missingness taxonomy) cho bộ dữ liệu Active Directory `SEAMLESS.INTERNAL` kết hợp dữ liệu nhật ký bảo mật (Windows Security Telemetry).
Báo cáo giải quyết toàn diện yêu cầu tại [Issue #56](https://github.com/nairyuuu/ad-weighted-graph/issues/56) (M2-10) và phản hồi kỹ thuật từ đồng đội tại [PR #59](https://github.com/nairyuuu/ad-weighted-graph/pull/59).

## Current evidence boundary after #79 B1 and #80

**Canonical integration checkpoint (2026-09-29):** manifest-verified fail-fast parsing yields 3,368 collected nodes plus two explicit `NT AUTHORITY` boundary Groups (INTERACTIVE and IUSR), for 3,370 canonical nodes. Its 53,774 edges and three unknown assessments pass Contract 1.3. The 3,370 structural nodes and 53,774 edges match the project Neo4j projection; the assessments remain in canonical JSON. PR #148 awaits #138 review acceptance. Raw/reference EDA's 66,374 observations use different field and multiplicity rules. See [scope identity evidence audit](seamless-scope-identity.md).

Các số liệu dưới đây là quan sát trên snapshot đã manifest-verify, không phải chứng nhận collection completeness hoặc canonical graph output của #44/#45.
[Phase A matrix](m1-evidence-audit.md), [#94 raw-field audit](claim-to-field-traceability.md) và [#80 host-access semantics](host-access-semantics-audit.md) xác định cách diễn giải chúng.
Đặc biệt, raw `RemoteDesktopUsers[]` không chứng minh composite CanRDP, Event 4624 riêng lẻ không chứng minh RDP, Sysmon 10 riêng lẻ không chứng minh truy cập LSASS, và upstream tactic labels không phải Windows-native ground truth.
PR #101 đã hoàn tất #80 EDA raw-versus-canonical remediation; PR #102 đã bỏ relationship-to-EventID matrix khỏi generator và report.
Independent telemetry không bổ sung SEAMLESS structural edges, không chứng minh exploit đã xảy ra trên topology đó và không calibration production weights.

---

## 1. Bối cảnh và Nguồn gốc Dữ liệu (Provenance)

Bộ dữ liệu Active Directory `SEAMLESS.INTERNAL` được thu thập từ môi trường kiểm thử BadBlood chạy trên Domain Controller thực tế thông qua SharpHound v3.
Dữ liệu được quản lý bằng snapshot manifest bất biến tại [data/samples/manifests/seamless-raw-v1.json](../../data/samples/manifests/seamless-raw-v1.json).

Dữ liệu telemetry được quản lý tại [data/samples/manifests/telemetry-raw-v1.json](../../data/samples/manifests/telemetry-raw-v1.json), trích xuất từ kho mẫu tấn công EVTX của SecOps.
Toàn bộ số liệu trong báo cáo này được tái lập tự động thông qua script [scripts/eda_dataset_analysis.py](../../scripts/eda_dataset_analysis.py).

---

## 2. Mô hình Phân tầng Bằng chứng (Evidence Stratification)

Khi xây dựng đồ thị tấn công có trọng số, việc phân biệt nguồn gốc và độ tin cậy của dữ liệu là nguyên tắc sống còn.
Dự án phân tách ranh giới rõ ràng giữa ba loại bằng chứng:

1. **Bằng chứng Quan sát (Observed Evidence)**:
   Các thuộc tính và phân quyền cấu hình xuất hiện trong SharpHound JSON của snapshot được kiểm tra theo raw field và manifest.
   Nhóm này bao gồm danh sách người dùng, nhóm, cấu trúc đơn vị tổ chức (OU) và các danh sách điều khiển truy cập tùy ý (DACL/ACE).
   Đây là observation bị giới hạn bởi snapshot, collector và khả năng thu thập; không phải ground truth tuyệt đối hoặc bằng chứng completeness.

2. **Bằng chứng Không quan sát được / Chưa rõ (Unknown Evidence)**:
   Các raw host arrays `Sessions[]`, `LocalAdmins[]`, `RemoteDesktopUsers[]` và `PSRemoteUsers[]` có thể rỗng hoặc thiếu mà không chứng minh quan hệ âm.
   Canonical `CanRDP` còn yêu cầu UserRights allow/deny evidence theo [host-access semantics audit](host-access-semantics-audit.md).
   Collection có thể thiếu bằng chứng session hoặc local authorization; network/service reachability thuộc runtime, không quyết định structural-edge existence.
   Offline host, firewall và access denied là các khả năng chưa đo được trong snapshot, không phải nguyên nhân đã xác nhận.
   Nguyên tắc then chốt: Tuyệt đối không diễn giải việc không quan sát được dữ liệu như việc không tồn tại rủi ro.

3. **Expected và observed telemetry ở semantic/evaluation layer**:
   Technique expectations lấy từ catalog; event corpus chỉ cung cấp descriptive signals trong population của chính nó.
   Không bổ sung structural relationships hay dynamic weights từ independent Windows logs.
   Event 4624/4634 cần identity/time/qualifier evidence để nghiên cứu session activity và không chứng minh HasSession của SEAMLESS.

---

## 3. Hệ Thống Phân Loại Ngữ Nghĩa Dữ Liệu Thiếu (Missingness Taxonomy)

Để đảm bảo downstream pipeline dựng đồ thị và gán trọng số không bị sai lệch, dự án thiết lập hệ thống phân loại 7 trạng thái ngữ nghĩa cho dữ liệu vắng mặt:

| Phân loại (Taxonomy Class) | Định nghĩa Ngữ nghĩa | Ví dụ trong Dataset | Xử lý trong Graph Pipeline |
| --- | --- | --- | --- |
| **`structurally unavailable`** | Thuộc tính không tồn tại trong schema định nghĩa của lớp đối tượng này | Trường `operatingsystem` trên User hoặc Group | Bỏ qua hoàn toàn; không sinh node/edge |
| **`synthetic artifact`** | Causal explanation cần bằng chứng về cách tạo bản ghi, không suy từ một field rỗng | 99/100 `operatingSystem` không populated là quan sát; nguyên nhân chưa xác minh từ field đó | Giữ giả thuyết riêng khỏi raw fact |
| **`never materialized`** | Causal explanation cần lifecycle/activity evidence | 2.492/2.493 `lastLogonTimestamp` rỗng hoặc zero; không chứng minh chưa từng logon | Giữ activity unknown |
| **`collector-unobservable`** | Collector không thể thăm dò endpoint, cần status/error evidence | Host arrays rỗng hoặc unobserved; không có `.errors` trong snapshot | Giữ completeness unknown, không tự gắn nguyên nhân offline |
| **`permission-filtered`** | Collector bị từ chối truy cập, cần access-denied evidence | Snapshot không có metadata để đếm trường hợp này | Không gán `insufficient_privilege` cho bản ghi khi thiếu evidence |
| **`actual empty/false`** | Giá trị raw false được quan sát; completeness/effective state cần đánh giá riêng | 100/100 Computer records có `haslaps = false` theo collector | Ghi `collector observed false`; không suy deployment state |
| **`unknown/unmeasured`** | Mandatory evidence hoặc collection-result metadata vắng mặt | Raw host arrays empty/unobserved; UserRights không có trong SEAMLESS v3 export | Giữ assessment và collection completeness là unknown; không suy canonical absence |

---

## 4. Phân Tích Chuyên Sâu Ngữ Nghĩa Cho Từng Thuộc Tính

### 4.1. Ngữ nghĩa của `lastLogonTimestamp`

Thống kê EDA ghi nhận **99.96% tài khoản (2.492 / 2.493 users)** có giá trị `lastLogonTimestamp` rỗng hoặc bằng 0.
Ngữ nghĩa Active Directory:
- `lastLogonTimestamp` không phải là audit trail thời gian thực cho từng lần đăng nhập.
- Thuộc tính này được Microsoft thiết kế với cơ chế đồng bộ trễ giữa các Domain Controllers (chu kỳ ngẫu nhiên từ 9 đến 14 ngày, kiểm soát bởi tham số `ms-DS-Logon-Time-Threshold`) nhằm giảm tải lưu lượng nhân bản LDAP.
- Phân biệt với `lastLogon`: Thuộc tính `lastLogon` chỉ được ghi nhận cục bộ trên Domain Controller trực tiếp xử lý xác thực và không bao giờ được đồng bộ sang các DC khác.
- Phân biệt với `Event ID 4624`: Đây là Windows Security audit event của một logon được ghi nhận; cần provider, channel, host, LogonType và time correlation trước khi liên hệ với một session cụ thể.
- **Kết luận ngữ nghĩa**: 99.96% records có giá trị zero hoặc absent trong snapshot.
  Không suy rằng các tài khoản chưa từng xác thực hoặc collector đầy đủ chỉ từ trường này.

#### 4.2. Ngữ nghĩa của `operatingSystem` trên Computer Objects

Thống kê EDA ghi nhận **99.0% máy tính (99/100 missing, 1 populated DC endpoint: `BADBLOOD.SEAMLESS.INTERNAL`)** thiếu thông tin hệ điều hành trong snapshot.
Ngữ nghĩa Active Directory:
- Trong Active Directory, sự tồn tại của một computer object trong cơ sở dữ liệu LDAP hoàn toàn không đồng nghĩa với việc có một máy trạm Windows thực sự tồn tại và đã gia nhập miền (Domain Join).
- Script PowerShell của BadBlood gọi hàm `New-ADComputer` để tạo nhanh 100 đối tượng máy tính trực tiếp vào cơ sở dữ liệu NTDS.dit.
- Trường `operatingSystem` chỉ được tự động điền (populate) bởi tiến trình `NetJoinDomain` khi hệ điều hành Windows thực sự kết nối với Domain Controller lúc gia nhập miền.
- **Kết luận ngữ nghĩa**: 99/100 records không có `operatingSystem` populated.
  BadBlood-generated endpoint là một giả thuyết về nguyên nhân, không chứng minh tất cả endpoint là ảo hay collector không bỏ sót gì.

### 4.3. Ngữ nghĩa của `HasLAPS` (Áp dụng nguyên tắc `not observed != false`)

Thống kê EDA ghi nhận giá trị `haslaps` tuân theo phân loại missingness 3 trạng thái: `observed_false: 100`, `observed_true: 0`, `missing_or_absent: 0` (`percentage_observed_false: 100.0%`).
Trường này được phân loại chính xác là `collector observed false; deployment state not independently established`.
Ngữ nghĩa Active Directory:
- Giá trị `haslaps=false` cho biết collector SharpHound không quan sát thấy trạng thái LAPS-positive theo các thuộc tính mở rộng schema mà công cụ thăm dò.
- Snapshot không cung cấp bằng chứng độc lập về schema, chính sách hoặc trạng thái endpoint để quy nguyên nhân của giá trị này cho LAPS deployment.
- Dữ liệu này không tự chứng minh một chính sách LAPS trước đó đã được triển khai rồi bị gỡ bỏ.
- **Kết luận ngữ nghĩa**: Giữ nguyên fact khách quan ở mức `percentage_observed_false: 100.0%` và phân loại `collector observed false; deployment state not independently established` trong missingness taxonomy của snapshot mà không suy diễn trạng thái triển khai trước đó khi thiếu bằng chứng schema độc lập.

### 4.4. Directory State so với Operational / Local State (`HasSession` & `LocalAdmins`)

Đây là sự phân định cốt lõi giữa hai tầng dữ liệu trong Active Directory:
- **Directory State (Trạng thái Thư mục tĩnh)**:
  Bao gồm User, Group, Computer, OU, GPO và các danh sách phân quyền DACL/ACE.
  Đây là các directory attributes và references tại thời điểm snapshot; một raw record không chứng minh tính bất biến hoặc completeness của môi trường.
  Field presence trong JSON không chứng nhận LDAP collection completeness; snapshot không có collector-result metadata để tính tỷ lệ này.
- **Operational / Local State (Trạng thái Vận hành & Cục bộ)**:
  Bao gồm các phiên đăng nhập tương tác (`HasSession`) và danh sách thành viên nhóm quản trị cục bộ (`LocalAdmins`).
  Phiên làm việc là dữ liệu tạm thời (ephemeral), còn local group authorization là host-bound evidence được collector biểu diễn trong các mảng endpoint.
  Vị trí lưu trữ và phương thức thu thập tùy host/schema; không suy collector success từ field presence.
- `LocalAdmins`: Raw array empty/unobserved trên 99/100 Computer records, với 5 positive references trên 1 host; `Sessions[]` empty/unobserved trên 100/100 Computer records.
- `RemoteDesktopUsers[]` có 3 raw membership observations trên 1 host; snapshot không có UserRights/completeness evidence nên không đo được verified `CanRDP`.
- Dữ liệu snapshot cho thấy các mảng thu thập endpoint này unpopulated/empty, nhất quán với giả thuyết các máy trạm mô phỏng (synthetic endpoints) không thực sự hiện diện trên mạng để collector thực hiện thăm dò RPC/SMB (hoặc nếu có máy trạm thì bị ngoại tuyến/chặn tường lửa); tuy nhiên do snapshot thiếu metadata lỗi (.errors/access-denied), nguyên nhân ngoại tuyến chỉ được xem là giả thuyết nhất quán (consistent hypothesis), không phải sự kiện đo lường trực tiếp từ JSON.
- **Kết luận ngữ nghĩa**: Computer object vẫn tồn tại hợp lệ trong LDAP, nhưng raw arrays empty/unobserved trên các máy trạm thuộc nhóm `unknown` về mặt completeness. Không được mô tả chúng là canonical relationship absence.
  Đây chính là lý do cần khảo sát thêm bằng chứng vận hành độc lập.

### 4.5. Raw host primitives và canonical relationships

EDA xuất riêng `RemoteDesktopUsers_raw_memberships`, `LocalAdmins_raw_memberships`,
`PSRemoteUsers_raw_memberships` và `Sessions_raw_observations`. Raw counts là số quan sát
trong snapshot, không phải một phép đổi tên cho canonical edge.

Đặc biệt, verified `CanRDP` chỉ có thể là positive khi effective RDU membership, allow
right và known-negative deny right đều đầy đủ. Trong SEAMLESS hiện tại, kết quả là
`unknown`/không materialize; không báo `CanRDP=0` và không dùng raw RDU count làm
`CanRDP` count. Positive `LocalAdmins[]` vẫn là host-bound structural evidence cho
`AdminTo`; positive `PSRemoteUsers[]` là BloodHound-modeled evidence cho `CanPSRemote`,
trong khi WinRM/runtime endpoint authorization nằm ngoài edge existence. `Sessions[]`
chỉ là session observation/opportunity và không chứng minh credential dumping.

---

## 5. Kiểm toán Độ đầy đủ và Dữ liệu Thiếu (Completeness & Missingness)

### 5.1. Thống kê theo Loại Đối tượng

Tổng số đối tượng được định danh trực tiếp trong snapshot `SEAMLESS.INTERNAL` là **3.368 snapshot nodes** (3.369 bản ghi raw, 1 dropped, 0 malformed, 1 duplicate OID).
Khi dựng đồ thị, 2 nút biên well-known ngoại vi (`SEAMLESS.INTERNAL-S-1-5-4` [INTERACTIVE] và `SEAMLESS.INTERNAL-S-1-5-17` [IUSR]) được hiện thực hóa khi có tham chiếu, đưa tổng số đỉnh đồ thị lên **3.370 materialized graph nodes**.

| Loại đối tượng (Kind) | Số lượng bản ghi | Trường định danh chuẩn | Tỷ lệ bản ghi lỗi / loại bỏ | Phân loại Ngữ nghĩa Dữ liệu Thiếu chính |
| --- | --- | --- | --- | --- |
| User | 2.493 | SID (`S-1-5-21-...`) | 0.0% (0/2493) | 99.96% `lastLogonTimestamp` zero/absent; activity unknown |
| Group | 549 | SID (`S-1-5-21-...`) | 0.2% (1/550 dropped) | 4/549 `Members[]` empty/unobserved; completeness unknown |
| Computer | 100 | SID (`S-1-5-21-...`) | 0.0% (0/100) | 99% `operatingSystem` và `LocalAdmins[]` unpopulated; 100% `Sessions[]` empty/unobserved |
| OrganizationalUnit (OU) | 223 | GUID | 0.0% (0/223) | 223 records observed; collection completeness unknown |
| GPO | 2 | GUID | 0.0% (0/2) | 2 records observed; applicability/effective state separate |
| Domain | 1 | SID (`S-1-5-21-...`) | 0.0% (0/1) | 1 record observed; collection completeness unknown |

### 5.2. Tính Toàn vẹn Tham chiếu (Referential Integrity & Dangling References)

Kiểm toán toàn vẹn tham chiếu được tính toán trực tiếp từ `audit_data_quality` trong [scripts/eda_dataset_analysis.py](../../scripts/eda_dataset_analysis.py) trên tập byte đã xác thực:
- Tổng số tham chiếu cạnh (Total edge references): 66.374.
- Tham chiếu thực thể thu thập được (Collected entity resolutions): 66.372 / 66.374 (99.997%) giải quyết trực tiếp tới các principal hạng nhất trong snapshot.
- Tham chiếu nút biên ngoại vi (Boundary stub resolutions): 2 / 66.374 (0.003%) trỏ tới các định danh well-known ngoài biên (`SEAMLESS.INTERNAL-S-1-5-4` cho `INTERACTIVE` và `SEAMLESS.INTERNAL-S-1-5-17` cho `IUSR`), được khởi tạo dưới dạng nút biên (boundary stubs).
- Tham chiếu mồ côi / treo chưa giải quyết (Unresolved dangling references): 0 / 66.374 (0.0%).
- **Tỷ lệ toàn vẹn tham chiếu (Referential integrity percentage)**: **100.0%** khi tính cả các nút biên hợp lệ được sinh ra.

66.374 là số raw/reference-shaped observations trong audit này; EDA graph materialize 66.371 entries vì 3 raw RDU-only references không được coi là verified `CanRDP`.
Cả hai số đều không phải canonical output của #44/#45.

Báo cáo EDA đếm một tập con reference theo các field mà parser hiện duyệt; 100.0% trong phép đếm này không chứng nhận mọi raw reference đã resolve.
[#94 raw-field audit](seamless-raw-field-audit.md) kiểm tra phạm vi rộng hơn: 71.786 reference-shaped observations, trong đó 2 `Group.Members[].MemberId` chưa exact-match và phải giữ unresolved cho #44.

### 5.3. Tách biệt Ngữ nghĩa: Tỷ lệ Tồn tại Trường, Raw Observation và Độ Đầy đủ Thu thập (Field Presence, Raw Observation & Collection Completeness)

Theo yêu cầu của [Issue #56](https://github.com/nairyuuu/ad-weighted-graph/issues/56), báo cáo tách field presence, positive raw observation và collection completeness:
1. **Tỷ lệ hiện diện trường trong lược đồ (Field Presence Rate)**:
   Kiểm tra sự tồn tại của khóa/trường thuộc tính (`"Members"`, `"Aces"`, `"LocalAdmins"`, `"RemoteDesktopUsers"`, `"PSRemoteUsers"`, `"Sessions"`) trong cấu trúc bản ghi JSON.
   Tỷ lệ này chỉ có mẫu số là records đã thu thập, không đại diện cho toàn bộ environment.
2. **Tỷ lệ quan sát raw dương (Positive Raw Evidence Rate)**:
   Đo tỷ lệ records có ít nhất một raw member/ACE/host reference theo đúng field được EDA duyệt.
   Tỷ lệ không quan sát được raw entry không phải canonical relationship absence hoặc bằng chứng collection complete.
3. **Độ đầy đủ thu thập thực tế (True Collection Completeness / Unknown Rate)**:
   Được xác định là `not_measurable_from_snapshot` trên toàn bộ 8 loại quan hệ, do snapshot tĩnh không chứa tệp nhật ký lỗi collector (`.errors`) hay dữ liệu đo lường yêu cầu bị từ chối truy cập (Access-Denied telemetry).

| Loại Bằng chứng | Bề mặt Thu thập | Quần thể Đối tượng | Hiện diện Trường (Field Presence) | Positive raw/evidence hosts | Empty/missing/unobserved hosts | Raw/evidence observations | Độ đầy đủ Thu thập (Completeness) | Trạng thái & Ghi chú Phân tích |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `MemberOf` raw references | Directory LDAP | 549 Groups | 100.0% (549/549) | 99.27% (545/549) | 0.73% (4/549) | 13.324 | `not_measurable_from_snapshot` | 4 `Members[]` empty/unobserved; 2 member references unresolved theo #94 |
| `GenericAll` | Directory DACL | 3.368 Objects | 100.0% (3.368/3.368) | 99.47% (3.350/3.368) | 0.53% (18/3.368) | 37.208 | `not_measurable_from_snapshot` | Phổ biến trên 99.47% đối tượng Active Directory |
| `WriteDacl` | Directory DACL | 3.368 Objects | 100.0% (3.368/3.368) | 99.91% (3.365/3.368) | 0.09% (3/3.368) | 3.397 | `not_measurable_from_snapshot` | Phổ biến trên 99.91% đối tượng Active Directory |
| `ForceChangePassword` explicit `RightName` | Directory DACL | 3.368 Objects | 100.0% (3.368/3.368) | 0.0% (0/3.368) | 100.0% (3.368/3.368) | 0 | `not_measurable_from_snapshot` | Không có explicit label; ExtendedRight GUID/collection completeness chưa đủ để kết luận canonical absence |
| `LocalAdmins_raw_memberships` / `AdminTo` evidence | Endpoint RPC/SAM | 100 Computers | 100.0% (100/100) | 1.0% (1/100) | 99.0% (99/100) | 5 raw observations | `not_measurable_from_snapshot` | Positive host-bound evidence trên DC; các host còn lại empty/unobserved, không kết luận AdminTo absence |
| `RemoteDesktopUsers_raw_memberships` | Endpoint RPC/SAM | 100 Computers | 100.0% (100/100) | 1.0% (1/100) | 99.0% (99/100) | 3 raw observations | `not_measurable_from_snapshot` | Raw RDU membership only; không phải verified `CanRDP` |
| `CanRDP` (verified effective) | RPC/SAM + UserRights | 100 Computers | UserRights unavailable | — | 100 unknown | 0 materialized; verified count unmeasurable | `not_measurable_from_snapshot` | Thiếu allow/deny/completeness evidence; canonical absence không thể kết luận |
| `PSRemoteUsers_raw_memberships` / modeled `CanPSRemote` | Endpoint RPC/SAM | 100 Computers | 100.0% (100/100) | 1.0% (1/100) | 99.0% (99/100) | 2 raw observations | `not_measurable_from_snapshot` | Modeled structural evidence; WinRM availability/endpoint ACL là runtime/endpoint predicates |
| `Sessions_raw_observations` / `HasSession` | Endpoint NetSessionEnum | 100 Computers | 100.0% (100/100) | 0.0% (0/100) | 100.0% (100/100) | 0 observations | `not_measurable_from_snapshot` | Empty/unobserved; không kết luận session absence hoặc credential outcome |

### 5.4. Kiểm toán Tập trung Dữ liệu Thiếu (Missingness Concentration)

Nghiên cứu tiến hành phân tích sự tập trung của dữ liệu thiếu theo vai trò hệ thống, cấp bậc đặc quyền và đơn vị tổ chức:
- **Theo Ranh giới Tier và Vai trò Hệ thống (Tier-0 / Domain Controllers vs Workstations)**:
  - Domain Controller (`BADBLOOD.SEAMLESS.INTERNAL`, PrimaryGroupSid `-516`): Tỷ lệ raw field không populated cho `operatingSystem`, `LocalAdmins`, `lastlogontimestamp` = 0.0% trong record này.
  - Workstations (99 máy trạm): Tỷ lệ raw field không populated cho ba field trên = 100.0% trong các records này.
  - **Kết luận**: Raw fields không populated tập trung tại workstation records; DC record có positive values, nhưng collection completeness của cả hai nhóm vẫn chưa đo được.
- **Theo Cấp bậc Đặc quyền Tài khoản (Privileged Accounts vs Standard Accounts)**:
  - Tài khoản quản trị (`adminCount=true`, 2 users): 1 tài khoản có `lastLogonTimestamp` dương (Administrator: 1632186767), 1 tài khoản thiếu (Krbtgt: -1), đạt tỷ lệ thiếu 50.0%.
  - Tài khoản thông thường (`adminCount=false`, 2.491 users): 100.0% thiếu `lastLogonTimestamp`.
  - **Kết luận**: Giá trị `lastLogonTimestamp` zero/absent phổ biến trong snapshot; không chứng minh không có đăng nhập thực tế.
- **Theo Đơn vị Tổ chức (Domain / OU Distribution)**:
  Phân tích tổng hợp trên toàn bộ 79 đơn vị tổ chức cha (parent OUs) có chứa máy tính:
  - `OU=Domain Controllers`: Chứa 2 máy tính gồm 1 Domain Controller (`BADBLOOD.SEAMLESS.INTERNAL`, 0% raw field không populated) và 1 máy trạm (`HREWLPT1000001.SEAMLESS.INTERNAL`, 100% raw field không populated), đạt tỷ lệ chung 50.0% trong nhóm field được EDA xét.
  - 78 OU còn lại (bao gồm các OU phân cấp như `OU=Groups,OU=AWS,OU=Tier 1`, `OU=ServiceAccounts,OU=ITS,OU=Tier 2`, `OU=Devices,OU=HRE,OU=Stage`): Chứa 98 máy trạm với tỷ lệ raw field không populated là 100.0% trong nhóm field được EDA xét.
  - **Kết luận**: Sự không populated của raw fields tập trung ở các Computer records ngoài DC; không suy tỷ lệ collector success từ phân bố OU.

---

## 6. Phân tích Sai lệch trên Vùng Đặc quyền Cao (Tier-0 Bias)

Dữ liệu thiếu có làm sai lệch phân tích trên các mục tiêu trọng yếu (Tier-0) hay không?

### 6.1. Độ Bao phủ trên Domain Controllers và Nhóm Quản trị Tối cao

- Domain Controller record `BADBLOOD.SEAMLESS.INTERNAL` có positive raw `LocalAdmins[]`, `RemoteDesktopUsers[]` và `PSRemoteUsers[]` observations.
  Đây là positive field evidence trong snapshot, không chứng nhận LDAP/RPC collection complete hoặc effective `CanRDP`.
- Các nhóm đặc quyền tối cao (High-Value Targets):
  - Tám group records được EDA chọn làm Tier-0 reference gồm Domain Admins, Enterprise Admins, Schema Admins, Administrators, Account Operators, Backup Operators, Print Operators và Server Operators.
  - 11 group records có `adminCount=1`; cờ này không tự chứng minh effective protection hoặc collector completeness.
  - Raw ACL/reference counts ở các hub có thể lớn; đây là topology observations, không phải số attack techniques đã thực hiện.

### 6.2. Kết luận về Vùng Mù và Giới hạn Bộ Dữ liệu (Blind Spots & Dataset Limitations)

- **Phạm vi Cấu hình Thư mục Tập trung (Directory Configuration Scope)**:
  Snapshot chứa directory ACE, owner và direct group membership references được EDA trích xuất theo raw fields đã thấy.
  Các transition như thay đổi DACL, reset password hoặc lạm dụng group membership không phải sự kiện đã quan sát chỉ vì structural evidence có mặt.
- **Giới hạn Bộ Dữ liệu về Nhật ký Lỗi và Quyền Truy cập (Access-Denied & Collector Error Limitation)**:
  Snapshot thô của BloodHound chỉ chứa các phong bì đối tượng JSON đã phân tích thành công mà không bao gồm tệp nhật ký lỗi của bộ thu thập (`.errors`) hoặc dữ liệu đo lường các yêu cầu bị từ chối truy cập (Access-Denied telemetry).
  Do đó, tiêu chí này được ghi nhận trạng thái tái lập là `not_measurable_from_snapshot`.
  Nghiên cứu **không khẳng định 100% khả năng quan sát hay hoàn toàn không có vùng mù (No Blind Spots)**; tỷ lệ lỗi thu thập và khả năng tồn tại các đối tượng bị che khuất là một giới hạn khách quan của snapshot tĩnh này.
- **Vùng Mù Thu thập trên Endpoint (Collector Endpoint Blind Spot)**:
  Raw session observations, RDU/RMU membership và local-admin evidence để trống trên 99 máy trạm (chỉ có positive raw evidence trên DC). Verified `CanRDP` không đo được vì thiếu UserRights/completeness evidence.
  Điều này nhất quán với giả thuyết các endpoint mô phỏng trong môi trường lab chưa từng được khởi chạy hoặc không thể thăm dò qua RPC/SMB trong quá trình thu thập.

---

## 7. Telemetry độc lập và giới hạn của EDA

Telemetry độc lập mô tả hoạt động trong corpus riêng; nó không tự lấp vùng mù thu thập của snapshot SEAMLESS.
Attack Semantics Layer chỉ định expected evidence cho từng transition, còn correlation với ObservedActivity cần kiểm chứng môi trường, định danh và thời gian theo #81.

### 7.1. Hồ sơ Đặc trưng của Bộ Nhật ký An ninh (Telemetry Profile)

Kiểm toán trên bộ dữ liệu `EVTX-ATTACK-SAMPLES` ghi nhận:
- Tổng số dòng trong corpus đã xác thực: 4.633; trường `EVTX_Tactic` chứa 8 nhãn upstream, không phải Windows-native ground truth.
- Độ phủ hệ thống: 19 máy tính khác nhau và 35 tài khoản người dùng mục tiêu.
- Cửa sổ thời gian: Từ 2017-06-09 đến 2021-06-09.
- Phân bố nhãn `EVTX_Tactic`: Lateral Movement (1.288 dòng), Privilege Escalation (1.088 dòng), Execution (533 dòng), Credential Access (283 dòng).

`corpus_event_id_distribution` và `top_event_ids` chỉ đếm dòng theo EventID trong corpus độc lập, không đo số attack, canonical relationships, hay mức đáp ứng ExpectedTelemetry.
EDA không đánh giá provider/channel/qualifier hoặc correlation identity, environment, time nên không suy ra ObservedActivity cho graph SEAMLESS từ các phân bố này.
`telemetry_evidence_inventory` ghi rõ ranh giới đó và trỏ tới [runtime semantic catalog](../../configs/attack_semantics.yml) duy nhất.

### 7.2. Descriptive inventory: tham chiếu technique thay vì edge-event equivalence

[configs/attack_semantics.yml](../../configs/attack_semantics.yml) là authoritative runtime semantic catalog duy nhất.
[Ma trận sáu lớp #79 Phase A](m1-evidence-audit.md) ghi sources, population, confidence và consumer của từng claim; không duy trì một Event ID mapping độc lập tại đây.

| Structural context | Technique catalog reference | Boundary của descriptive inventory |
| --- | --- | --- |
| MemberOf | `propagate_group_entitlement` | Passive traversal có `expected_telemetry: []`; 4728/4729 là group modification, không phải passive membership |
| AdminTo | `obtain_admin_execution_on_host` | ExpectedTelemetry phụ thuộc management channel/audit configuration; không cố định một Event ID |
| GenericAll | `genericall_reset_password`, `genericall_add_member`, `genericall_grant_write_dacl` | Tách password reset, group modification và DACL mutation; không coi mọi quyền là cùng một action |
| WriteDacl | `grant_new_object_right` | DACL mutation là technique; evidence về quyền không chứng minh mutation đã xảy ra |
| ForceChangePassword | `reset_target_password` | Password-reset expectation khác observed event và khác structural right |
| CanRDP | `open_remote_interactive_session` | RDP attribution cần qualifiers; không claim LogonType 10 availability khi chưa xác minh snapshot |
| CanPSRemote | `open_winrm_remote_session` | PowerShell event presence không tự chứng minh WinRM transport |
| HasSession | `recover_session_credential_material` | Session opportunity khác credential extraction; Sysmon 10 cần process context trước LSASS attribution |

Các references là pointers tới catalog đã accepted, không phải mapping evidence schema mới của #81.
Corpus signal availability vẫn phải được phân biệt với authoritative expectation và illustrative hypothesis; #94/PR #99 cung cấp field-level verification, #81 sở hữu structured provenance.
Ngay cả khi có cùng môi trường, identity namespace và time window, correlation chỉ là candidate evidence, không tự tạo ConfirmedAttack.
Hai corpus hiện hành độc lập nên không entity-level join hoặc gắn telemetry làm structural edge provenance.

---

## 8. Tiêu chí Nghiệm thu và Tái lập (Reproducibility)

Báo cáo này ghi nhận deliverable lịch sử tại [Issue #56](https://github.com/nairyuuu/ad-weighted-graph/issues/56):
- Các số liệu có đường tái lập từ snapshot manifest; #80 đã hoàn tất raw host-access remediation và #79 B1 đã tách descriptive telemetry inventory.
  #79 B2 kiểm toán các current-state narrative còn lại theo accepted #94 evidence.
- Script tái lập độc lập:
  ```bash
  uv run python scripts/eda_dataset_analysis.py
  ```
- Khi các archive lịch sử NORTH/ad_sampledata không có trong workspace, dùng đường dẫn bảo toàn
  xác định tường minh để không biến mất dữ liệu baseline:
  ```bash
  uv run python scripts/eda_dataset_analysis.py \
    --preserve-historical-from-ref 275a721 \
    --output reports/eda_summary.json
  ```
  Báo cáo ghi provenance riêng cho các section được generate hiện tại, section lịch sử được
  preserve, và phép so sánh được tính lại từ các section đã assemble; không dùng một revision
  generator duy nhất để mô tả sai toàn bộ hybrid report.
  Ref `275a721` được pin tới báo cáo gốc của phần lịch sử để nguồn preservation không thay đổi khi `develop` tiến lên.
- Dữ liệu kết quả đầu ra được lưu trữ tại [reports/eda_summary.json](../../reports/eda_summary.json).
