# Từ foothold này, cần quan tâm gì?

Nguồn: **FINWVIR1000001.SEAMLESS.INTERNAL** (Computer); profile `computer_usable_identity`.
ID: `S-1-5-21-1271839998-3495686680-2211690266-4157`; context: `S-1-5-21-1271839998-3495686680-2211690266-4157`.
Initial capability là đầu vào khai báo; reference: `scenario://awg-r04/machine-identity/FINWVIR-4157`.

Đã xử lý 12/12 cặp trong cohort: **4 có witness**, 8 chưa kết luận; 0 chưa chạy. Ngoài cohort: 31068 cặp inventory.

C là mức công sức ordinal có điều kiện; chưa chấm giữ trống. Thứ tự: có witness trước, rồi tầng mục tiêu kỹ thuật và C trong cùng tầng; không phải business-impact/P ranking.

| Nguồn | Mục tiêu | Kết quả | C tìm thấy | Bằng chứng tối ưu |
| --- | --- | --- | --- | --- |
| FINWVIR1000001.SEAMLESS.INTERNAL | DOMAIN ADMINS@SEAMLESS.INTERNAL | truncated_success | 1.0 | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | ADMINISTRATORS@SEAMLESS.INTERNAL | truncated_success | 1.0 | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | DOMAIN CONTROLLERS@SEAMLESS.INTERNAL | truncated_success | 1.0 | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | READ-ONLY DOMAIN CONTROLLERS@SEAMLESS.INTERNAL | truncated_success | 1.0 | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | BADBLOOD.SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | ENTERPRISE ADMINS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | ACCOUNT OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | SCHEMA ADMINS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | REPLICATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | PRINT OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | BACKUP OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | SERVER OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |

## Đường tìm thấy tới DOMAIN ADMINS@SEAMLESS.INTERNAL

| Bước | Hành động | Danh tính thực hiện | Đối tượng / context |
| --- | --- | --- | --- |
| 1 | Đặt lại mật khẩu của User bằng quyền GenericAll | FINWVIR1000001.SEAMLESS.INTERNAL | OLLIE_LONG@SEAMLESS.INTERNAL |
| 2 | Dùng danh tính vừa reset tại authentication context | OLLIE_LONG@SEAMLESS.INTERNAL | FINWVIR1000001.SEAMLESS.INTERNAL |
| 3 | Có entitlement của security group với danh tính này | OLLIE_LONG@SEAMLESS.INTERNAL | DOMAIN ADMINS@SEAMLESS.INTERNAL |

Work units được chấm C (union, không cộng số bước):
- `scenario_reset_password`: C=1; basis `estimated_expert_scenario`.
- `acquire_reset_identity`: C=0; basis `estimated_expert_scenario`.

Đường này dùng **7 runtime assumptions**; đây là dự đoán có điều kiện, không phải quan sát đăng nhập hoặc P=1.
- `network_rpc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-2014`; reference `policy://seamless/v1/network/rpc`.
- `membership_usable`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-512`; reference `policy://seamless/v1/token/member-usable`.
- `security_group`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-512`; reference `policy://seamless/v1/token/security-group`.
- `network_kdc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/network/kdc`.
- `directory_write_allowed`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-2014`; reference `policy://seamless/v1/directory/write`.
- `authentication_accepted`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/auth/accepted`.
- `password_policy_accepts`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-2014`; reference `policy://seamless/v1/directory/password-policy`.

**Quyền nên kiểm tra trước:** GenericAll của **FINWVIR1000001.SEAMLESS.INTERNAL** trên **OLLIE_LONG@SEAMLESS.INTERNAL**. Xem toàn bộ ACE/inheritance provenance trong JSON trước khi thu hồi quyền; đây là điểm can thiệp đề xuất từ witness, chưa phải bằng chứng cắt hết đường.

Full native trace: `result.json#/reproducibility/inputs/public_queries/sha256:ed334a4ce1cabf1b2e978c54863faf139f011ef1f2fa4f86419d0f74acd68d22`. Bước dùng danh tính tại context không tự cấp quyền admin trên context đó.

## Đường tìm thấy tới ADMINISTRATORS@SEAMLESS.INTERNAL

| Bước | Hành động | Danh tính thực hiện | Đối tượng / context |
| --- | --- | --- | --- |
| 1 | Đặt lại mật khẩu của User bằng quyền GenericAll | FINWVIR1000001.SEAMLESS.INTERNAL | KATRINA_GREEN@SEAMLESS.INTERNAL |
| 2 | Dùng danh tính vừa reset tại authentication context | KATRINA_GREEN@SEAMLESS.INTERNAL | FINWVIR1000001.SEAMLESS.INTERNAL |
| 3 | Có entitlement của security group với danh tính này | KATRINA_GREEN@SEAMLESS.INTERNAL | ADMINISTRATORS@SEAMLESS.INTERNAL |

Work units được chấm C (union, không cộng số bước):
- `scenario_reset_password`: C=1; basis `estimated_expert_scenario`.
- `acquire_reset_identity`: C=0; basis `estimated_expert_scenario`.

Đường này dùng **7 runtime assumptions**; đây là dự đoán có điều kiện, không phải quan sát đăng nhập hoặc P=1.
- `password_policy_accepts`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1116`; reference `policy://seamless/v1/directory/password-policy`.
- `network_rpc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1116`; reference `policy://seamless/v1/network/rpc`.
- `network_kdc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-1116` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/network/kdc`.
- `security_group`: `S-1-5-21-1271839998-3495686680-2211690266-1116` → `domain:sid:S-1-5-21-1271839998-3495686680-2211690266:S-1-5-32-544`; reference `policy://seamless/v1/token/security-group`.
- `directory_write_allowed`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1116`; reference `policy://seamless/v1/directory/write`.
- `authentication_accepted`: `S-1-5-21-1271839998-3495686680-2211690266-1116` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/auth/accepted`.
- `membership_usable`: `S-1-5-21-1271839998-3495686680-2211690266-1116` → `domain:sid:S-1-5-21-1271839998-3495686680-2211690266:S-1-5-32-544`; reference `policy://seamless/v1/token/member-usable`.

**Quyền nên kiểm tra trước:** GenericAll của **FINWVIR1000001.SEAMLESS.INTERNAL** trên **KATRINA_GREEN@SEAMLESS.INTERNAL**. Xem toàn bộ ACE/inheritance provenance trong JSON trước khi thu hồi quyền; đây là điểm can thiệp đề xuất từ witness, chưa phải bằng chứng cắt hết đường.

Full native trace: `result.json#/reproducibility/inputs/public_queries/sha256:ee82c705e8169204ff55f7f2d8730a9d3750783cb3a810c5e3878e953889409f`. Bước dùng danh tính tại context không tự cấp quyền admin trên context đó.

## Đường tìm thấy tới DOMAIN CONTROLLERS@SEAMLESS.INTERNAL

| Bước | Hành động | Danh tính thực hiện | Đối tượng / context |
| --- | --- | --- | --- |
| 1 | Đặt lại mật khẩu của User bằng quyền GenericAll | FINWVIR1000001.SEAMLESS.INTERNAL | MICAH_BOLTON@SEAMLESS.INTERNAL |
| 2 | Dùng danh tính vừa reset tại authentication context | MICAH_BOLTON@SEAMLESS.INTERNAL | FINWVIR1000001.SEAMLESS.INTERNAL |
| 3 | Có entitlement của security group với danh tính này | MICAH_BOLTON@SEAMLESS.INTERNAL | DOMAIN CONTROLLERS@SEAMLESS.INTERNAL |

Work units được chấm C (union, không cộng số bước):
- `scenario_reset_password`: C=1; basis `estimated_expert_scenario`.
- `acquire_reset_identity`: C=0; basis `estimated_expert_scenario`.

Đường này dùng **7 runtime assumptions**; đây là dự đoán có điều kiện, không phải quan sát đăng nhập hoặc P=1.
- `authentication_accepted`: `S-1-5-21-1271839998-3495686680-2211690266-1690` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/auth/accepted`.
- `password_policy_accepts`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1690`; reference `policy://seamless/v1/directory/password-policy`.
- `network_rpc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1690`; reference `policy://seamless/v1/network/rpc`.
- `membership_usable`: `S-1-5-21-1271839998-3495686680-2211690266-1690` → `S-1-5-21-1271839998-3495686680-2211690266-516`; reference `policy://seamless/v1/token/member-usable`.
- `directory_write_allowed`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1690`; reference `policy://seamless/v1/directory/write`.
- `network_kdc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-1690` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/network/kdc`.
- `security_group`: `S-1-5-21-1271839998-3495686680-2211690266-1690` → `S-1-5-21-1271839998-3495686680-2211690266-516`; reference `policy://seamless/v1/token/security-group`.

**Quyền nên kiểm tra trước:** GenericAll của **FINWVIR1000001.SEAMLESS.INTERNAL** trên **MICAH_BOLTON@SEAMLESS.INTERNAL**. Xem toàn bộ ACE/inheritance provenance trong JSON trước khi thu hồi quyền; đây là điểm can thiệp đề xuất từ witness, chưa phải bằng chứng cắt hết đường.

Full native trace: `result.json#/reproducibility/inputs/public_queries/sha256:c2b8e295f6d51e2b1899940202565891a798dfc43631b5ed4502b0c618662b2b`. Bước dùng danh tính tại context không tự cấp quyền admin trên context đó.

## Đường tìm thấy tới READ-ONLY DOMAIN CONTROLLERS@SEAMLESS.INTERNAL

| Bước | Hành động | Danh tính thực hiện | Đối tượng / context |
| --- | --- | --- | --- |
| 1 | Đặt lại mật khẩu của User bằng quyền GenericAll | FINWVIR1000001.SEAMLESS.INTERNAL | MARCELLA_PARKER@SEAMLESS.INTERNAL |
| 2 | Dùng danh tính vừa reset tại authentication context | MARCELLA_PARKER@SEAMLESS.INTERNAL | FINWVIR1000001.SEAMLESS.INTERNAL |
| 3 | Có entitlement của security group với danh tính này | MARCELLA_PARKER@SEAMLESS.INTERNAL | READ-ONLY DOMAIN CONTROLLERS@SEAMLESS.INTERNAL |

Work units được chấm C (union, không cộng số bước):
- `scenario_reset_password`: C=1; basis `estimated_expert_scenario`.
- `acquire_reset_identity`: C=0; basis `estimated_expert_scenario`.

Đường này dùng **7 runtime assumptions**; đây là dự đoán có điều kiện, không phải quan sát đăng nhập hoặc P=1.
- `security_group`: `S-1-5-21-1271839998-3495686680-2211690266-1387` → `S-1-5-21-1271839998-3495686680-2211690266-521`; reference `policy://seamless/v1/token/security-group`.
- `authentication_accepted`: `S-1-5-21-1271839998-3495686680-2211690266-1387` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/auth/accepted`.
- `network_kdc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-1387` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/network/kdc`.
- `membership_usable`: `S-1-5-21-1271839998-3495686680-2211690266-1387` → `S-1-5-21-1271839998-3495686680-2211690266-521`; reference `policy://seamless/v1/token/member-usable`.
- `password_policy_accepts`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1387`; reference `policy://seamless/v1/directory/password-policy`.
- `directory_write_allowed`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1387`; reference `policy://seamless/v1/directory/write`.
- `network_rpc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-1387`; reference `policy://seamless/v1/network/rpc`.

**Quyền nên kiểm tra trước:** GenericAll của **FINWVIR1000001.SEAMLESS.INTERNAL** trên **MARCELLA_PARKER@SEAMLESS.INTERNAL**. Xem toàn bộ ACE/inheritance provenance trong JSON trước khi thu hồi quyền; đây là điểm can thiệp đề xuất từ witness, chưa phải bằng chứng cắt hết đường.

Full native trace: `result.json#/reproducibility/inputs/public_queries/sha256:1eb567e85a2f8ea1b616647ba8f8409cc15e9d6c231cd5a1152427f2943739e5`. Bước dùng danh tính tại context không tự cấp quyền admin trên context đó.

## Các mục tiêu chưa có witness

- BADBLOOD.SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- ENTERPRISE ADMINS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- ACCOUNT OPERATORS@SEAMLESS.INTERNAL: đã hết budget; ví dụ một transition tới đích còn thiếu `security_group`, `membership_usable`; chưa có cơ sở gọi là an toàn.
- SCHEMA ADMINS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- REPLICATORS@SEAMLESS.INTERNAL: đã hết budget; ví dụ một transition tới đích còn thiếu `security_group`, `membership_usable`; chưa có cơ sở gọi là an toàn.
- PRINT OPERATORS@SEAMLESS.INTERNAL: đã hết budget; ví dụ một transition tới đích còn thiếu `security_group`, `membership_usable`; chưa có cơ sở gọi là an toàn.
- BACKUP OPERATORS@SEAMLESS.INTERNAL: đã hết budget; ví dụ một transition tới đích còn thiếu `security_group`, `membership_usable`; chưa có cơ sở gọi là an toàn.
- SERVER OPERATORS@SEAMLESS.INTERNAL: đã hết budget; ví dụ một transition tới đích còn thiếu `security_group`, `membership_usable`; chưa có cơ sở gọi là an toàn.

Chi tiết kiểu identity, actor, nguồn quyền, raw-edge provenance và từng runtime fact nằm trong defender-brief.json. result.json giữ toàn bộ attempts/state audit. Nếu có remediation, program elimination và source–goal disconnection được báo riêng.
