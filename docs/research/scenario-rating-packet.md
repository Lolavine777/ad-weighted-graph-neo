# Gói đánh giá độc lập cho kịch bản mẫu tổng hợp (Independent Rating Packet)

- Phiên bản: 1.0.0
- Ngày ban hành: 2026-10-01
- Phân loại kịch bản: **Synthetic Template Scenario for Independent Rating Elicitation** (Kịch bản mẫu tổng hợp cho quy trình định mức độc lập)
- Kịch bản định danh: `scenario-corp-compromised-host-to-dc`
- Mục tiêu kịch bản: `terminal_compromise_dc01` (RCE với quyền quản trị trên Domain Controller `DC01` qua WinRM)
- Trạng thái gói định mức: Prepared (Hai người phù hợp trong nhóm có thể đánh giá độc lập; actual ratings PENDING, chữ ký tùy chọn)
- Người biên soạn: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Tài liệu quy chuẩn đi kèm: [ADR-0013](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/adr/ADR-0013-scoped-path-ranking-and-pareto-frontier.md), [evidence-rating-governance.md](evidence-rating-governance.md), [path-ranking-interface-specification.md](path-ranking-interface-specification.md)
- Issue / PR: Refs #143, Refs #42, Refs #48

## Làm rõ workflow hiện hành - 2026-10-01

Áp dụng [clarification #143/#158](https://github.com/nairyuuu/ad-weighted-graph/pull/159#issuecomment-5927555315) và [governance hiện hành](evidence-rating-governance.md).
A/B hoặc hai người phù hợp trong nhóm có thể chấm độc lập, ghi đúng năng lực/phạm vi thực tế; không yêu cầu người ngoài, chứng chỉ, họp trực tiếp hoặc chữ ký.
Các placeholder signatures phía dưới là metadata kiểm toán tùy chọn; actual reviewer decision/provenance/time/rationale được lưu bằng review trace.
Research/LLM-assisted scenario estimates phải có verified sources, đúng conditional quantity `q_i = P(E_i succeeds | foothold, scenario, all previous events succeeded)`, basis/scope/uncertainty/sensitivity và A/B review.
Nguồn mô tả cơ chế và model confidence không tự chứng minh numeric success probability; hai prompts/models không là hai human raters.
Implementation/tests dưới assumptions có thể tiếp tục khi human agreement pending; không bịa actual ratings/consensus hoặc gọi scenario estimates là empirical calibration.
Template synthetic này giữ các ví dụ kiểm thử lịch sử; packet operational cho SEAMLESS và canonical wire mappings nằm tại [seamless-scenario-rating-packet.md](seamless-scenario-rating-packet.md).

## 1. Mục đích và phạm vi áp dụng

Tài liệu này cung cấp một gói định mức hoàn chỉnh, chuẩn hóa và có thể kiểm toán để chuyển giao cho các người đánh giá an toàn thông tin độc lập thực hiện quy trình đánh giá (Independent Rating & Reconciliation Protocol).
Gói định mức tập trung vào một kịch bản mẫu tổng hợp (synthetic template scenario), cụ thể và có ranh giới rõ ràng nhằm giải quyết Cổng tham số (Parameters Gate) của ADR-0013 mà không yêu cầu thực nghiệm tấn công trực tiếp trên hệ thống thật.
Kịch bản này sử dụng không gian định danh tổng hợp (`S-1-5-21-3623811015-3361044348-30300820-...`) để phục vụ kiểm thử giải thuật và đối soát quy trình quản trị, không phải là dữ liệu cấu trúc quan sát thực tế từ snapshot SEAMLESS (theo tài liệu kiểm toán được ghim tại [seamless-scope-identity.md](seamless-scope-identity.md), domain SID chính thức của SEAMLESS là `S-1-5-21-1271839998-3495686680-2211690266`).
SEAMLESS hiện Insufficient Evidence cho numerical predictive ranking vì numeric basis/validation chưa đủ; verdict xét lại theo reviewed evidence/scope, không yêu cầu collection hoặc external panel mặc định.

### Ranh giới nguyên tắc bắt buộc

1. **Không bịa đặt danh tính người đánh giá hoặc điểm chấm:**
Actual identity, điểm số, rationale và raw disagreement giữ `PENDING` tới khi A/B hoặc hai người phù hợp đánh giá độc lập; chữ ký/tổ chức là audit metadata tùy chọn.
2. **Không dùng AI làm người chấm độc lập:**
Tuyệt đối không sử dụng hai lần sinh của mô hình ngôn ngữ lớn (LLM / Agent) để giả lập hai người đánh giá chấm điểm độc lập.
3. **Không lấy số liệu synthetic làm tham số sản phẩm:**
Các con số số học (0.8, 0.9, 0.648, chi phí 3, 8) trong các fixture kiểm thử nghiên cứu (Experiment 6) thuần túy phục vụ kiểm tra tính đúng đắn của giải thuật toán học và không được đưa vào bộ tham số sản phẩm.
4. **Chuẩn bị gói định mức không đồng nghĩa với đã đạt yêu cầu:**
Việc ban hành tài liệu này là điều kiện cần để tổ chức phiên chấm; nó không đóng Cổng tham số và không thay đổi trạng thái của ADR-0013 từ Proposed sang Accepted.

---

## 2. Mô tả kịch bản hẹp và sự kiện thành công

### 2.1. Nhận diện Foothold và Tài sản đích

- **Kịch bản định danh:** `scenario-corp-compromised-host-to-dc`
- **Tài khoản foothold xuất phát:**
  - Định danh canonical: `S-1-5-21-3623811015-3361044348-30300820-1002` (Account: `ALICE@CORP.LOCAL`)
  - Máy trạm ban đầu bị kiểm soát: `S-1-5-21-3623811015-3361044348-30300820-1101` (Computer: `WS01.CORP.LOCAL`)
- **Tài sản đích (Target Asset):**
  - Định danh canonical: `S-1-5-21-3623811015-3361044348-30300820-1000` (Computer / Domain Controller: `DC01.CORP.LOCAL`)
  - Nhóm đặc quyền đích liên quan: `domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-549` (Group: `Server Operators`; theo Graph Contract 1.3.0, nhóm Builtin Server Operators S-1-5-32-549 được định danh chuẩn tắc dưới dạng scoped ID gắn với domain SID)
- **Sự kiện thành công đơn nhất (Terminal Success Event):**
  - Ký hiệu: `terminal_compromise_dc01`
  - Định nghĩa: Kẻ tấn công thực thi mã từ xa thành công với quyền quản trị cục bộ hoặc đặc quyền SYSTEM trên Domain Controller `DC01.CORP.LOCAL` thông qua dịch vụ Windows Remote Management (WinRM / PSRemoting) với tư cách thành viên nhóm `Server Operators`.
  - Giới hạn ranh giới: Hành vi sao chép cơ sở dữ liệu thư mục (DCSync) không thuộc phạm vi chuỗi tấn công này do đòi hỏi quyền sao chép thư mục riêng biệt (Replication Rights / Gate O).

### 2.2. Tiêu chuẩn đánh giá hậu quả nghiệp vụ (Business Consequence Rationale)

Hậu quả nghiệp vụ được định mức độc lập trên thang đo thứ tự: $\text{Low} < \text{Medium} < \text{High} < \text{Critical}$.
Tiêu chí đánh giá hậu quả dựa trên mức độ gián đoạn hoạt động, nguy cơ tổn thất dữ liệu và khả năng phục hồi của doanh nghiệp:

| Bậc tác động | Tiêu chí thiệt hại nghiệp vụ | Dịch vụ và dữ liệu chịu ảnh hưởng |
| --- | --- | --- |
| **Low** | Ảnh hưởng cục bộ tới tài khoản người dùng thông thường; không gián đoạn dịch vụ; dễ dàng khắc phục bằng quy trình vận hành chuẩn. | Dịch vụ trạm làm việc cá nhân, thư điện tử cá nhân. |
| **Medium** | Ảnh hưởng tới máy chủ ứng dụng nội bộ hoặc nhóm người dùng phòng ban; gián đoạn công việc trong thời gian ngắn; không ảnh hưởng dữ liệu mật cốt lõi. | Ứng dụng quản lý tài liệu nội bộ, máy in chia sẻ. |
| **High** | Chiếm quyền máy chủ dịch vụ quan trọng (ERP, cổng thanh toán); có nguy cơ rò rỉ dữ liệu nhạy cảm; đòi hỏi cô lập hệ thống để điều tra sự cố. | Cơ sở dữ liệu nghiệp vụ chính, hệ thống giao dịch khách hàng. |
| **Critical** | Chiếm quyền hoàn toàn Domain Controller hoặc giả mạo vé xác thực Kerberos (Golden Ticket); làm sụp đổ toàn bộ ranh giới tin cậy và định danh doanh nghiệp; có khả năng truy cập mọi bí mật dữ liệu. | Dịch vụ định danh trung tâm (AD / SSO / KDC), hạ tầng kiểm soát truy cập toàn doanh nghiệp. |

**Nguyên tắc phân định ranh giới:**
Theo ontology danh tính - tài sản, nhãn `Tier0` phản ánh ranh giới kiểm soát kỹ thuật AD, còn nhãn `CrownJewel` phản ánh giá trị tài sản nghiệp vụ.
Hai nhãn này trực giao nhau.
Tuyệt đối không tự động quy đổi `Tier0` thành `Critical` nếu người đánh giá không đưa ra giải trình thiệt hại nghiệp vụ cụ thể.

---

## 3. Tách bạch giữa cấu trúc quan sát và giả thiết runtime

Theo quy chuẩn hợp đồng kịch bản 4 tầng dữ kiện (`week3-scenario-contract.md`), gói định mức phân định rõ ràng giữa thông tin cấu trúc kịch bản và các giả thiết vận hành:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Tầng 1: Cấu trúc kịch bản mẫu (Synthetic Structural Fixture)           │
│   - Nguồn gốc: Fixture chuẩn hóa cho hai người chấm độc lập            │
│   - Quan hệ: GenericAll, MemberOf, AdminTo                             │
│   - Tính chất: Cố định cho quy trình đối soát gói định mức             │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│ Tầng 2: Năng lực điểm xuất phát (Host / Identity Capabilities)         │
│   - Quyền thực thi lệnh trên foothold, tài khoản người dùng ALICE      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│ Tầng 3: Giả thiết kịch bản runtime (Runtime Scenario Assumptions)      │
│   - Khai báo tường minh trong assumption ledger kèm lý do kỹ thuật     │
│   - Cổng mạng SMB/SAMR (445), Kerberos (88), WinRM (5985/5986)         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│ Tầng 4: Mục tiêu kịch bản (Scenario Goal Predicates)                   │
│   - terminal_compromise_dc01 (RCE trên DC01 qua WinRM)                 │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1. Dữ kiện cấu trúc trong kịch bản mẫu tổng hợp

Các quan hệ cấu trúc sau đây là fixture mẫu phục vụ đối soát quy trình, có mã định danh cạnh chuẩn tắc (Canonical Edge ID):

1. **Cạnh 1 (GenericAll):**
   - Nguồn: `S-1-5-21-3623811015-3361044348-30300820-1002` (`ALICE`)
   - Đích: `S-1-5-21-3623811015-3361044348-30300820-1003` (`BOB`)
   - Loại quan hệ: `GenericAll`
   - Provenance locator: `synthetic_fixture:edges:genericall:alice_to_bob`
2. **Cạnh 2 (MemberOf):**
   - Nguồn: `S-1-5-21-3623811015-3361044348-30300820-1003` (`BOB`)
   - Đích: `domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-549` (`Server Operators`)
   - Loại quan hệ: `MemberOf`
   - Provenance locator: `synthetic_fixture:edges:memberof:bob_to_serverops`
3. **Cạnh 3 (AdminTo):**
   - Nguồn: `domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-549` (`Server Operators`)
   - Đích: `S-1-5-21-3623811015-3361044348-30300820-1000` (`DC01$`)
   - Loại quan hệ: `AdminTo`
   - Provenance locator: `synthetic_fixture:edges:adminto:serverops_to_dc01`

### 3.2. Giả thiết runtime được khai báo có lý do

Để chuỗi hành động có thể thực thi, các giả thiết runtime sau được đưa vào sổ cái giả định (Assumption Ledger):

1. `network_reachable_samr(WS01, DC01)`: Máy trạm foothold có thể kết nối mạng tới cổng 445 (SMB/RPC) của DC01 để gọi thủ tục MS-SAMR (Lý do: máy trạm cùng phân vùng mạng nội bộ có quyền kết nối tới bộ điều khiển miền).
2. `network_reachable_winrm(WS01, DC01)`: Máy trạm foothold có thể kết nối mạng tới cổng 5985 (HTTP) hoặc cổng 5986 (HTTPS) của DC01 cho giao thức WinRM.
3. `service_running(DC01, MS-SAMR)`: Dịch vụ SAM Remote Protocol đang hoạt động bình thường trên DC01.
4. `service_running(DC01, WinRM)`: Dịch vụ Windows Remote Management đang hoạt động trên DC01, WinRM listener đang lắng nghe và tường lửa cho phép lưu lượng từ mạng nội bộ.
5. `authorization_winrm_server_operators`: Chính sách điều khiển truy cập WinRM trên DC01 cho phép thành viên nhóm tích hợp `Server Operators` đăng nhập và thực thi lệnh từ xa.
6. `no_edr_blocking_network_logon`: Cơ chế giám sát hành vi tại trạm làm việc và bộ điều khiển miền không ngăn chặn ngay lập tức hành vi xác thực mạng của tài khoản BOB sau khi đổi mật khẩu.

---

## 4. Danh mục hành động đóng gói và sổ cái công việc chuẩn tắc

### 4.1. Quy tắc định danh đơn vị công việc chuẩn tắc

Mỗi đơn vị công việc chủ động mang một mã định danh duy nhất theo định dạng:
`technique:actor:target:context:boundary:ledger_version`
Quy tắc này bảo đảm không đếm trùng chi phí khi nhiều bước trung gian tái sử dụng chung một kết quả chuẩn bị.

### 4.2. Danh mục hành động đóng gói (Bound Actions Catalog)

| Mã hành động | Kỹ thuật áp dụng | Chủ thể thực hiện | Đích tác động | Thẻ chuẩn bị dùng chung | Mã đơn vị công việc chuẩn tắc |
| --- | --- | --- | --- | --- | --- |
| `action_pwd_reset` | `genericall_reset_password` | `ALICE` (SID `...-1002`) | `BOB` (SID `...-1003`) | `samr_rpc_session` | `pwd_reset:...-1002:...-1003:corp_net:ad_boundary:v1` |
| `action_network_auth` | `kerberos_network_logon` | `BOB` (SID `...-1003`) | `DC01` (SID `...-1000`) | `kerberos_ticket_granting` | `net_auth:...-1003:...-1000:corp_net:ad_boundary:v1` |
| `action_winrm_exec` | `psremote_execute` | `BOB` (SID `...-1003`) | `DC01` (SID `...-1000`) | `winrm_connection` | `winrm_exec:...-1003:...-1000:corp_net:ad_boundary:v1` |

*Ghi chú về ranh giới:*
Hành động `dcsync_replicate` không nằm trong chuỗi hành động này.
Việc khai thác DCSync đòi hỏi quyền đồng bộ thư mục riêng biệt (Replication Rights) và thuộc phạm vi Gate O.

### 4.3. Phân tích phụ thuộc và chống đếm trùng (Anti-Overlap Rules)

1. **Bước chuẩn bị dùng chung (Shared Preparation):**
   - Nếu hai hành động cùng yêu cầu mở phiên kết nối RPC hoặc phiên xác thực mạng, chi phí thiết lập kết nối chỉ được tính một lần vào đơn vị công việc đầu tiên.
   - Các hành động tiếp theo sử dụng lại phiên kết nối có chi phí ma sát giảm trừ tương ứng.
2. **Đồng bộ thụ động (Passive Closure):**
   - Các bước chuyển quyền tự động do cấu trúc đồ thị (ví dụ: quan hệ kế thừa nhóm `MemberOf`) được coi là đồng bộ thụ động với chi phí nỗ lực $C = 0$.

---

## 5. Nguồn tài liệu kỹ thuật quy chuẩn (Primary References with Locators)

Các cơ chế kỹ thuật và điều kiện tiên quyết trong kịch bản này dựa trên tài liệu chính thức từ nhà sản xuất hệ điều hành và tổ chức tiêu chuẩn an ninh:

1. **Giao thức quản lý tài khoản từ xa SAMR (MS-SAMR):**
   - Nguồn: Microsoft Open Specifications, *[MS-SAMR]: Security Account Manager (SAM) Remote Protocol*.
   - Bộ định vị: Section [3.1.5.6.4](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-samr/99ee9f39-43e8-4bba-ac3a-82e0c0e0699e) `SamrSetInformationUser2` (Password Reset Mechanism).
   - Nội dung kỹ thuật: Quyền `GenericAll` hoặc quyền `User-Force-Change-Password` cho phép gọi thủ tục RPC để đặt lại mật khẩu của đối tượng User mà không cần biết mật khẩu cũ.
2. **Dịch vụ quản trị từ xa Windows Remote Management (WinRM):**
   - Nguồn: Microsoft Learn Documentation, *[Authentication for Remote Connections](https://learn.microsoft.com/en-us/windows/win32/winrm/authentication-for-remote-connections)*.
   - Bộ định vị: Sections *Kerberos Authentication* và *Default WinRM Configuration*.
   - Nội dung kỹ thuật: WinRM lắng nghe trên cổng 5985 (HTTP) hoặc cổng 5986 (HTTPS), hỗ trợ xác thực Kerberos qua Negotiate SSP. Thành viên thuộc nhóm quản trị được phân quyền truy cập listener qua SDDL / Local Security Policy để khởi tạo phiên PowerShell Remoting.
3. **Mô hình phân tầng quản trị Active Directory:**
   - Nguồn: Microsoft Learn Documentation, *Active Directory Administrative Tier Model*.
   - Bộ định vị: Section *Tier 0: Control Plane Security Boundary*.
   - Nội dung kỹ thuật: Xác định Domain Controller và các nhóm quản trị tích hợp sẵn (`Server Operators`, `Domain Admins`) thuộc ranh giới điều khiển Tier 0. Thành viên nhóm `Server Operators` có quyền đăng nhập và thực thi lệnh quản trị trên Domain Controller.
4. **MITRE ATT&CK Knowledge Base:**
   - Kỹ thuật [T1098](https://attack.mitre.org/techniques/T1098/): Account Manipulation (Thay đổi thông tin tài khoản qua password reset).
   - Kỹ thuật [T1078.002](https://attack.mitre.org/techniques/T1078/002/): Valid Accounts: Domain Accounts (Xác thực mạng bằng tài khoản miền với mật khẩu mới).
   - Kỹ thuật [T1021.006](https://attack.mitre.org/techniques/T1021/006/): Remote Services: Windows Remote Management (Thực thi lệnh từ xa trên DC01 qua WinRM).

*Ghi chú phân định kỹ thuật:*
Kỹ thuật T1003.001 (OS Credential Dumping qua LSASS) không nằm trong chuỗi hành động tối thiểu do kẻ tấn công đã đặt lại mật khẩu trực tiếp qua MS-SAMR RPC.
Kỹ thuật T1003.006 (DCSync) đòi hỏi quyền đồng bộ thư mục riêng biệt và thuộc Gate O, không nằm trong chuỗi hành động này.

**Lưu ý quan trọng cho A/B hoặc hai người đánh giá phù hợp:**
Các tài liệu quy chuẩn trên chứng minh tính hợp lệ về mặt kỹ thuật và điều kiện tiên quyết của các bước tấn công.
Tuy nhiên, chúng **không** chứa và không tự chứng minh các con số xác suất cụ thể.
Nhiệm vụ của A/B hoặc hai người đánh giá phù hợp là định mức khoảng xác suất có điều kiện và mức độ ma sát nỗ lực dựa trên kinh nghiệm thực tế và bối cảnh phòng thủ của kịch bản.

---

## 6. Tiêu chí chấm điểm và Rubric nghiên cứu

### 6.1. Rubric chấm nỗ lực trên sổ cái công việc

Nỗ lực ($C$) được đánh giá dựa trên hai tiêu chí $T_1$ (Độ phức tạp kỹ thuật) và $T_2$ (Ma sát vận hành và phòng thủ):

| Mức điểm | Tiêu chí $T_1$ (Độ phức tạp kỹ thuật và công cụ) | Tiêu chí $T_2$ (Ma sát vận hành và phòng thủ) |
| --- | --- | --- |
| **Mức 1** | Có sẵn công cụ tự động hóa chuẩn (PowerView, Mimikatz, Impacket); chỉ cần gọi lệnh trực tiếp. | Ma sát thấp; không yêu cầu quyền đặc biệt tại điểm xuất phát; ít phụ thuộc vào tương tác người dùng. |
| **Mức 2** | Đòi hỏi công cụ chuyên dụng hoặc tùy biến tham số; cần duy trì kết nối mạng ổn định. | Ma sát trung bình; yêu cầu tài khoản dịch vụ đang hoạt động hoặc cấu hình dịch vụ tương thích. |
| **Mức 3** | Đòi hỏi khai thác lỗ hổng giao thức tùy biến; cần tương tác sâu với bộ nhớ hệ thống hoặc giải mã gói tin. | Ma sát cao; đối mặt với cơ chế phát hiện hành vi nâng cao (EDR memory protection); đòi hỏi thời điểm phù hợp. |

**Công thức tính nỗ lực cơ sở:**
$$C = T_1 + T_2 - 2 \quad (0 \le C \le 4)$$

### 6.2. Tiêu chí chấm khoảng xác suất có điều kiện

Khoảng xác suất thành công $[l, u] \subset [0, 1]$ được chấm cho **đúng toàn bộ tiền tố chuỗi hành động** ($P(E_k \mid F, S, E_1, \ldots, E_{k-1})$):
- Cận dưới $l$: Khả năng thành công trong điều kiện phòng thủ cảnh giác, mạng chập chờn hoặc có cơ chế giám sát cơ bản.
- Cận trên $u$: Khả năng thành công trong điều kiện thuận lợi, tài khoản không bị khóa và không có phản ứng tức thời từ SOC.
- Bất định nhận thức: Nếu khoảng quá rộng ($u - l > 0.50$), hệ thống sẽ đánh dấu cảnh báo độ bất định cao và yêu cầu rà soát lại căn cứ.

---

## 7. Phiếu chấm độc lập số 1 (Blank Rating Sheet - Rater 1)

```text
================================================================================
PHIẾU CHẤM ĐỊNH MỨC ĐỘC LẬP SỐ 1
Mã định danh người đánh giá: PENDING_RATER_1
Họ và tên người đánh giá:    [PENDING]
Đơn vị công tác:         [PENDING]
Ngày chấm:               [PENDING]
Trạng thái phiếu:        PENDING (Chờ actual independent rating; chữ ký tùy chọn)
================================================================================

1. ĐÁNH GIÁ TÁC ĐỘNG NGHIỆP VỤ (IMPACT RATING)
Tài sản đích: DC01.CORP.LOCAL (SID: S-1-5-21-3623811015-3361044348-30300820-1000)
Sự kiện thành công: terminal_compromise_dc01 (RCE quản trị trên DC01 qua WinRM)

[ ] Mức tác động đề xuất (chọn 1): [ ] Low  [ ] Medium  [ ] High  [ ] Critical
Căn cứ thiệt hại nghiệp vụ cụ thể:
................................................................................
................................................................................
Dịch vụ / Dữ liệu nghiệp vụ bị ảnh hưởng trực tiếp:
................................................................................

--------------------------------------------------------------------------------
2. ĐÁNH GIÁ NỖ LỰC CÔNG VIỆC TRÊN SỔ CÁI (WORK UNIT EFFORT)
(Người đánh giá chấm T1, T2 thuộc tập {1, 2, 3}; Tính C = T1 + T2 - 2)

Hành động A1 (pwd_reset: alice -> bob):
  - T1 (Độ phức tạp kỹ thuật): [ ]    - T2 (Ma sát vận hành): [ ]
  - Nỗ lực tính toán (C):       [ ]
  - Giải trình căn cứ:
    ............................................................................

Hành động A2 (network_auth: bob -> dc01):
  - T1 (Độ phức tạp kỹ thuật): [ ]    - T2 (Ma sát vận hành): [ ]
  - Nỗ lực tính toán (C):       [ ]
  - Giải trình căn cứ:
    ............................................................................

Hành động A3 (winrm_exec: bob -> dc01):
  - T1 (Độ phức tạp kỹ thuật): [ ]    - T2 (Ma sát vận hành): [ ]
  - Nỗ lực tính toán (C):       [ ]
  - Giải trình căn cứ:
    ............................................................................

--------------------------------------------------------------------------------
3. ĐÁNH GIÁ KHOẢNG XÁC SUẤT CÓ ĐIỀU KIỆN THEO TIỀN TỐ (FULL-PREFIX LIKELIHOOD)

Tiền tố 1: [A1 (pwd_reset)]
  - Cận dưới (l1): [  /  ]     - Cận trên (u1): [  /  ]
  - Căn cứ xác định khoảng và độ bất định:
    ............................................................................

Tiền tố 2: [A1, A2 (network_auth | pwd_reset thành công)]
  - Cận dưới (l2): [  /  ]     - Cận trên (u2): [  /  ]
  - Căn cứ xác định khoảng và độ bất định:
    ............................................................................

Tiền tố 3: [A1, A2, A3 (winrm_exec | pwd_reset & network_auth thành công)]
  - Cận dưới (l3): [  /  ]     - Cận trên (u3): [  /  ]
  - Căn cứ xác định khoảng và độ bất định:
    ............................................................................

Chữ ký tùy chọn của người đánh giá 1: [PENDING SIGNATURE]
```

---

## 8. Phiếu chấm độc lập số 2 (Blank Rating Sheet - Rater 2)

```text
================================================================================
PHIẾU CHẤM ĐỊNH MỨC ĐỘC LẬP SỐ 2
Mã định danh người đánh giá: PENDING_RATER_2
Họ và tên người đánh giá:    [PENDING]
Đơn vị công tác:         [PENDING]
Ngày chấm:               [PENDING]
Trạng thái phiếu:        PENDING (Chờ actual independent rating; chữ ký tùy chọn)
================================================================================

1. ĐÁNH GIÁ TÁC ĐỘNG NGHIỆP VỤ (IMPACT RATING)
Tài sản đích: DC01.CORP.LOCAL (SID: S-1-5-21-3623811015-3361044348-30300820-1000)
Sự kiện thành công: terminal_compromise_dc01 (RCE quản trị trên DC01 qua WinRM)

[ ] Mức tác động đề xuất (chọn 1): [ ] Low  [ ] Medium  [ ] High  [ ] Critical
Căn cứ thiệt hại nghiệp vụ cụ thể:
................................................................................
................................................................................
Dịch vụ / Dữ liệu nghiệp vụ bị ảnh hưởng trực tiếp:
................................................................................

--------------------------------------------------------------------------------
2. ĐÁNH GIÁ NỖ LỰC CÔNG VIỆC TRÊN SỔ CÁI (WORK UNIT EFFORT)
(Người đánh giá chấm T1, T2 thuộc tập {1, 2, 3}; Tính C = T1 + T2 - 2)

Hành động A1 (pwd_reset: alice -> bob):
  - T1 (Độ phức tạp kỹ thuật): [ ]    - T2 (Ma sát vận hành): [ ]
  - Nỗ lực tính toán (C):       [ ]
  - Giải trình căn cứ:
    ............................................................................

Hành động A2 (network_auth: bob -> dc01):
  - T1 (Độ phức tạp kỹ thuật): [ ]    - T2 (Ma sát vận hành): [ ]
  - Nỗ lực tính toán (C):       [ ]
  - Giải trình căn cứ:
    ............................................................................

Hành động A3 (winrm_exec: bob -> dc01):
  - T1 (Độ phức tạp kỹ thuật): [ ]    - T2 (Ma sát vận hành): [ ]
  - Nỗ lực tính toán (C):       [ ]
  - Giải trình căn cứ:
    ............................................................................

--------------------------------------------------------------------------------
3. ĐÁNH GIÁ KHOẢNG XÁC SUẤT CÓ ĐIỀU KIỆN THEO TIỀN TỐ (FULL-PREFIX LIKELIHOOD)

Tiền tố 1: [A1 (pwd_reset)]
  - Cận dưới (l1): [  /  ]     - Cận trên (u1): [  /  ]
  - Căn cứ xác định khoảng và độ bất định:
    ............................................................................

Tiền tố 2: [A1, A2 (network_auth | pwd_reset thành công)]
  - Cận dưới (l2): [  /  ]     - Cận trên (u2): [  /  ]
  - Căn cứ xác định khoảng và độ bất định:
    ............................................................................

Tiền tố 3: [A1, A2, A3 (winrm_exec | pwd_reset & network_auth thành công)]
  - Cận dưới (l3): [  /  ]     - Cận trên (u3): [  /  ]
  - Căn cứ xác định khoảng và độ bất định:
    ............................................................................

Chữ ký tùy chọn của người đánh giá 2: [PENDING SIGNATURE]
```

---

## 9. Mẫu hồ sơ định mức thô (Raw Rating Records Template)

Các hồ sơ định mức thô sau khi thu thập từ người đánh giá sẽ được chuẩn hóa thành các bản ghi YAML theo đúng đặc tả quản trị:

### 9.1. Hồ sơ Tác động nghiệp vụ thô (Template)

```yaml
schema_version: "1.0.0"
record_type: "impact_rating"
target_asset_id: "S-1-5-21-3623811015-3361044348-30300820-1000"
target_asset_label: "DC01.CORP.LOCAL"
success_event: "terminal_compromise_dc01"
consequence_rating: "PENDING"  # Low, Medium, High, Critical
business_rationale: "PENDING_RATER_RATIONALE"
affected_business_services:
  - "PENDING_SERVICE_1"
technical_tier_metadata:
  - "Tier0"
business_value_metadata:
  - "CrownJewel"
evaluator: "PENDING_RATER_1"
rating_date: "PENDING_DATE"
status: "pending_review"
```

### 9.2. Hồ sơ Xác suất tiền tố có điều kiện thô (Template)

```yaml
schema_version: "1.0.0"
record_type: "conditional_likelihood"
scenario_id: "scenario-corp-compromised-host-to-dc"
ordered_work_prefix:
  - "pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1002:S-1-5-21-3623811015-3361044348-30300820-1003:corp_net:ad_boundary:v1"
conditional_bounds:
  lower: "PENDING_RATIONAL"  # Ví dụ "1/2"
  upper: "PENDING_RATIONAL"  # Ví dụ "3/4"
basis_category: "scenario_assumption"
uncertainty_rationale: "PENDING_RATER_UNCERTAINTY_EXPLANATION"
target_population: "Internal Active Directory Enterprise Topology"
operational_horizon: "72h"
evaluator: "PENDING_RATER_1"
rating_date: "PENDING_DATE"
status: "pending_review"
```

### 9.3. Hồ sơ Nỗ lực công việc thô (Template)

```yaml
schema_version: "1.0.0"
record_type: "work_unit_effort"
work_unit_id: "pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1002:S-1-5-21-3623811015-3361044348-30300820-1003:corp_net:ad_boundary:v1"
technique_name: "genericall_reset_password"
actor_scope: "S-1-5-21-3623811015-3361044348-30300820-1002"
target_scope: "S-1-5-21-3623811015-3361044348-30300820-1003"
rubric_evaluation:
  t1_complexity: 0  # PENDING {1, 2, 3}
  t2_friction: 0    # PENDING {1, 2, 3}
  formula: "base"   # T1 + T2 - 2
  computed_cost: 0  # PENDING {0, 1, 2, 3, 4}
overlap_analysis:
  prerequisite_dependencies: []
  shared_preparation_tags: ["samr_rpc_session"]
  is_independent: true
evaluator: "PENDING_RATER_1"
rating_date: "PENDING_DATE"
status: "pending_review"
```

---

## 10. Mẫu biên bản đối soát và quy trình thống nhất (Reconciliation Record Template)

```text
================================================================================
BIÊN BẢN ĐỐI SOÁT ĐỊNH MỨC TRONG NHÓM (RECONCILIATION RECORD)
Mã phiên đối soát:    RECON_2026_SCENARIO_CORP_01
Kịch bản:             scenario-corp-compromised-host-to-dc
Người đánh giá:       Rater 1: [PENDING], Rater 2: [PENDING]
Chủ trì phiên họp:    TTS A (@Lolavine777), Giám sát: TTS B (@nairyuuu)
Ngày đối soát:        [PENDING]
Trạng thái biên bản:  PENDING (Chờ phiên đối soát thực tế)
================================================================================

1. ĐỐI CHIẾU TÁC ĐỘNG NGHIỆP VỤ (IMPACT CONGRUENCE)
  - Sự kiện thành công:        terminal_compromise_dc01
  - Điểm Rater 1: [PENDING]   - Điểm Rater 2: [PENDING]
  - Thống kê đồng thuận:
    + Observed Agreement (Po): [PENDING]
    + Cohen's Kappa (kappa):   [PENDING] (Trạng thái: PENDING)
  - Kết luận Tác động:         [PENDING CONSENSUS / DISAGREEMENT]
  - Đề xuất kỹ thuật:          [proposed_consensus / requires_reconciliation_panel]
  - Tên status API lịch sử:   requires_reconciliation_panel là cần đối soát A/B,
                              không yêu cầu tuyển hội đồng bên ngoài.
  - Giải trình thống nhất:
    ............................................................................

2. ĐỐI CHIẾU NỖ LỰC CÔNG VIỆC (EFFORT CONGRUENCE)
  - Hành động A1 (pwd_reset):
    + Rater 1: C1 = [ ] | Rater 2: C2 = [ ] | Delta = |C1 - C2| = [ ]
    + Trạng thái (Delta <= 1): [PENDING PASS / FAIL]
    + Nỗ lực giải quyết bảo thủ (max(C1, C2)): [ ]

  - Hành động A2 (network_auth):
    + Rater 1: C1 = [ ] | Rater 2: C2 = [ ] | Delta = |C1 - C2| = [ ]
    + Trạng thái (Delta <= 1): [PENDING PASS / FAIL]
    + Nỗ lực giải quyết bảo thủ (max(C1, C2)): [ ]

  - Hành động A3 (winrm_exec):
    + Rater 1: C1 = [ ] | Rater 2: C2 = [ ] | Delta = |C1 - C2| = [ ]
    + Trạng thái (Delta <= 1): [PENDING PASS / FAIL]
    + Nỗ lực giải quyết bảo thủ (max(C1, C2)): [ ]

3. ĐỐI CHIẾU KHOẢNG XÁC SUẤT CÓ ĐIỀU KIỆN (LIKELIHOOD BOUNDS CONGRUENCE)
  - Tiền tố 1 [A1]:
    + Khoảng R1: [l1, u1] = [   ,   ] | Khoảng R2: [l2, u2] = [   ,   ]
    + Chỉ số IoU: [PENDING] (Yêu cầu IoU >= 0.50)
    + Khoảng hợp nhất mở rộng: [min(l1, l2), max(u1, u2)] = [   ,   ]
    + Cảnh báo bất định nhận thức (u - l > 0.50): [PENDING YES / NO]

  - Tiền tố 2 [A1, A2]:
    + Khoảng R1: [l1, u1] = [   ,   ] | Khoảng R2: [l2, u2] = [   ,   ]
    + Chỉ số IoU: [PENDING] (Yêu cầu IoU >= 0.50)
    + Khoảng hợp nhất mở rộng: [min(l1, l2), max(u1, u2)] = [   ,   ]
    + Cảnh báo bất định nhận thức (u - l > 0.50): [PENDING YES / NO]

  - Tiền tố 3 [A1, A2, A3]:
    + Khoảng R1: [l1, u1] = [   ,   ] | Khoảng R2: [l2, u2] = [   ,   ]
    + Chỉ số IoU: [PENDING] (Yêu cầu IoU >= 0.50)
    + Khoảng hợp nhất mở rộng: [min(l1, l2), max(u1, u2)] = [   ,   ]
    + Cảnh báo bất định nhận thức (u - l > 0.50): [PENDING YES / NO]

4. REVIEW TRACE VÀ METADATA KIỂM TOÁN TÙY CHỌN
  - Chữ ký Rater 1 (tùy chọn):                 [PENDING SIGNATURE]
  - Chữ ký Rater 2 (tùy chọn):                 [PENDING SIGNATURE]
  - Xác nhận của Reviewer (@nairyuuu): [PENDING APPROVAL]
```

---

## 11. Hướng dẫn thực hiện kiểm tra độ nhạy (Sensitivity Analysis Protocol)

Sau khi nhóm đối soát A/B hoàn tất và cung cấp các khoảng xác suất có điều kiện và mức nỗ lực chính thức, nhóm nghiên cứu sẽ thực hiện kiểm tra độ nhạy theo quy trình chuẩn:

1. **Lệnh thực thi kiểm tra trên testbed giải thuật và quy tắc quản trị:**
   ```bash
   .venv/bin/python scripts/research/worked_example_validation.py --all
   .venv/bin/python -m pytest tests/test_path_ranking_interface.py
   ```
   *Lưu ý rõ ràng về phân định phạm vi thực thi:*
   Lệnh `worked_example_validation.py --all` thực thi toàn bộ Thí nghiệm 1 đến 6 (tìm kiếm có giới hạn budget, tính hợp lệ rủi ro đơn điệu, quan hệ trội Pareto trên đồ thị đồ chơi tổng hợp, và kiểm chứng manifest/phiên snapshot SEAMLESS).
   Các hàm hỗ trợ quản trị đối soát (`compute_interval_iou`, `check_epistemic_uncertainty`, `compute_kappa_with_fallback`, `reconcile_expert_ratings`), các quy tắc phủ quyết nghiêm ngặt khi đối soát (rater trống/khoảng trắng, bất đồng định danh, sai lệch công thức rubric) và phép tính tay mẫu được kiểm chứng độc lập bởi bộ kiểm thử tự động `pytest tests/test_path_ranking_interface.py`.
   B có thể chuẩn bị và kiểm thử CLI dynamic rating ingestion dưới declared assumptions khi human agreement còn pending; actual numerical acceptance xét reviewed basis/validation trong scope.
2. **Kiểm tra độ ổn định của biên Pareto:**
   - Thay đổi các giá trị bên trong khoảng bất định $[l, u]$ của từng tiền tố tới các giá trị biên ($l$, midpoint, $u$).
   - Kiểm tra xem biên Pareto có bị đảo lộn thứ tự ưu thế bất thường hay không.
3. **Phân tích trường hợp cỡ mẫu nhỏ hoặc suy biến zero-variance:**
   - Trong các đợt thử nghiệm pilot nhỏ ($N < 5$), hệ thống sử dụng hàm chuẩn hóa `compute_kappa_with_fallback()`:
     - Nếu $P_e = 1.0$ (toàn bộ rater cùng chấm một mức duy nhất), hệ thống giữ trạng thái `degenerate_zero_variance` và công bố tỷ lệ quan sát được $P_o = 1.0$ cùng ma trận nhầm lẫn thô.
     - Tuyệt đối không dùng các ngưỡng giả định để chứng nhận hiệu chuẩn khi chưa đủ dữ liệu thực nghiệm.
