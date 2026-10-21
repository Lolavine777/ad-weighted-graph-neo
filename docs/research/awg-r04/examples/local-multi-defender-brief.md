# Từ foothold này, cần quan tâm gì?

Nguồn: **FINWVIR1000001.SEAMLESS.INTERNAL** (Computer); profile `computer_usable_identity`.
ID: `S-1-5-21-1271839998-3495686680-2211690266-4157`; context: `S-1-5-21-1271839998-3495686680-2211690266-4157`.
Initial capability là đầu vào khai báo; reference: `scenario://awg-r04/machine-identity/FINWVIR-4157`.
Nguồn: **OLA_CARSON@SEAMLESS.INTERNAL** (User); profile `user_usable_identity`.
ID: `S-1-5-21-1271839998-3495686680-2211690266-1395`; context: `S-1-5-21-1271839998-3495686680-2211690266-4157`.
Initial capability là đầu vào khai báo; reference: `None`.

Đã xử lý 6/6 cặp trong cohort: **2 có witness**, 4 chưa kết luận; 0 chưa chạy. Ngoài cohort: 31074 cặp inventory.

C là mức công sức ordinal có điều kiện; chưa chấm giữ trống. Thứ tự: có witness trước, rồi tầng mục tiêu kỹ thuật và C trong cùng tầng; không phải business-impact/P ranking.

| Nguồn | Mục tiêu | Kết quả | C tìm thấy | Bằng chứng tối ưu |
| --- | --- | --- | --- | --- |
| FINWVIR1000001.SEAMLESS.INTERNAL | DOMAIN ADMINS@SEAMLESS.INTERNAL | truncated_success | 1.0 | chưa có |
| OLA_CARSON@SEAMLESS.INTERNAL | DOMAIN ADMINS@SEAMLESS.INTERNAL | truncated_success | 1.0 | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | BADBLOOD.SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | ENTERPRISE ADMINS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| OLA_CARSON@SEAMLESS.INTERNAL | BADBLOOD.SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| OLA_CARSON@SEAMLESS.INTERNAL | ENTERPRISE ADMINS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |

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

## Đường tìm thấy tới DOMAIN ADMINS@SEAMLESS.INTERNAL

| Bước | Hành động | Danh tính thực hiện | Đối tượng / context |
| --- | --- | --- | --- |
| 1 | Đặt lại mật khẩu của User bằng quyền GenericAll | OLA_CARSON@SEAMLESS.INTERNAL | OLLIE_LONG@SEAMLESS.INTERNAL |
| 2 | Dùng danh tính vừa reset tại authentication context | OLLIE_LONG@SEAMLESS.INTERNAL | FINWVIR1000001.SEAMLESS.INTERNAL |
| 3 | Có entitlement của security group với danh tính này | OLLIE_LONG@SEAMLESS.INTERNAL | DOMAIN ADMINS@SEAMLESS.INTERNAL |

Work units được chấm C (union, không cộng số bước):
- `scenario_reset_password`: C=1; basis `estimated_expert_scenario`.
- `acquire_reset_identity`: C=0; basis `estimated_expert_scenario`.

Đường này dùng **7 runtime assumptions**; đây là dự đoán có điều kiện, không phải quan sát đăng nhập hoặc P=1.
- `membership_usable`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-512`; reference `policy://seamless/v1/token/member-usable`.
- `network_rpc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-1395` → `S-1-5-21-1271839998-3495686680-2211690266-2014`; reference `policy://seamless/v1/network/rpc`.
- `password_policy_accepts`: `S-1-5-21-1271839998-3495686680-2211690266-1395` → `S-1-5-21-1271839998-3495686680-2211690266-2014`; reference `policy://seamless/v1/directory/password-policy`.
- `security_group`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-512`; reference `policy://seamless/v1/token/security-group`.
- `network_kdc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/network/kdc`.
- `authentication_accepted`: `S-1-5-21-1271839998-3495686680-2211690266-2014` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `policy://seamless/v1/auth/accepted`.
- `directory_write_allowed`: `S-1-5-21-1271839998-3495686680-2211690266-1395` → `S-1-5-21-1271839998-3495686680-2211690266-2014`; reference `policy://seamless/v1/directory/write`.

**Quyền nên kiểm tra trước:** GenericAll của **OLA_CARSON@SEAMLESS.INTERNAL** trên **OLLIE_LONG@SEAMLESS.INTERNAL**. Xem toàn bộ ACE/inheritance provenance trong JSON trước khi thu hồi quyền; đây là điểm can thiệp đề xuất từ witness, chưa phải bằng chứng cắt hết đường.

Full native trace: `result.json#/reproducibility/inputs/public_queries/sha256:effae186a96280cde41a0228a056b9128216fbfc41d06f53d3885c19bd5ad1f9`. Bước dùng danh tính tại context không tự cấp quyền admin trên context đó.

## Các mục tiêu chưa có witness

- BADBLOOD.SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- ENTERPRISE ADMINS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- BADBLOOD.SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- ENTERPRISE ADMINS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.

Chi tiết kiểu identity, actor, nguồn quyền, raw-edge provenance và từng runtime fact nằm trong defender-brief.json. result.json giữ toàn bộ attempts/state audit. Nếu có remediation, program elimination và source–goal disconnection được báo riêng.
