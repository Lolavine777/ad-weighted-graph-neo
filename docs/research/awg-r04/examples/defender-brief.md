# Từ foothold này, cần quan tâm gì?

Nguồn: **FINWVIR1000001.SEAMLESS.INTERNAL** (Computer); profile `computer_usable_identity`.
ID: `S-1-5-21-1271839998-3495686680-2211690266-4157`; context: `S-1-5-21-1271839998-3495686680-2211690266-4157`.
Initial capability là đầu vào khai báo; reference: `scenario://awg-r04/machine-identity/FINWVIR-4157`.

Đã xử lý 12/12 cặp trong cohort: **1 có witness**, 11 chưa kết luận; 0 chưa chạy. Ngoài cohort: 31068 cặp inventory.

C là mức công sức ordinal có điều kiện; chưa chấm giữ trống. Thứ tự: có witness trước, rồi tầng mục tiêu kỹ thuật và C trong cùng tầng; không phải business-impact/P ranking.

| Nguồn | Mục tiêu | Kết quả | C tìm thấy | Bằng chứng tối ưu |
| --- | --- | --- | --- | --- |
| FINWVIR1000001.SEAMLESS.INTERNAL | DOMAIN ADMINS@SEAMLESS.INTERNAL | truncated_success | 1.0 | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | BADBLOOD.SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | ENTERPRISE ADMINS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | ACCOUNT OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | ADMINISTRATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | SCHEMA ADMINS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | DOMAIN CONTROLLERS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | REPLICATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | PRINT OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | READ-ONLY DOMAIN CONTROLLERS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | BACKUP OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |
| FINWVIR1000001.SEAMLESS.INTERNAL | SERVER OPERATORS@SEAMLESS.INTERNAL | truncated_incomplete | chưa chấm | chưa có |

## Đường tìm thấy tới DOMAIN ADMINS@SEAMLESS.INTERNAL

| Bước | Hành động | Danh tính thực hiện | Đối tượng / context |
| --- | --- | --- | --- |
| 1 | Đặt lại mật khẩu của User bằng quyền GenericAll | FINWVIR1000001.SEAMLESS.INTERNAL | DENA_WILLIAM@SEAMLESS.INTERNAL |
| 2 | Dùng danh tính vừa reset tại authentication context | DENA_WILLIAM@SEAMLESS.INTERNAL | FINWVIR1000001.SEAMLESS.INTERNAL |
| 3 | Có entitlement của security group với danh tính này | DENA_WILLIAM@SEAMLESS.INTERNAL | DOMAIN ADMINS@SEAMLESS.INTERNAL |

Work units được chấm C (union, không cộng số bước):
- `scenario_reset_password`: C=1; basis `estimated_expert_scenario`.
- `acquire_reset_identity`: C=0; basis `estimated_expert_scenario`.

Đường này dùng **7 runtime assumptions**; đây là dự đoán có điều kiện, không phải quan sát đăng nhập hoặc P=1.
- `membership_usable`: `S-1-5-21-1271839998-3495686680-2211690266-2799` → `S-1-5-21-1271839998-3495686680-2211690266-512`; reference `scenario://awg-r04/computer-boundary`.
- `directory_write_allowed`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-2799`; reference `scenario://awg-r04/computer-boundary`.
- `network_kdc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-2799` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `scenario://awg-r04/computer-boundary`.
- `security_group`: `S-1-5-21-1271839998-3495686680-2211690266-2799` → `S-1-5-21-1271839998-3495686680-2211690266-512`; reference `scenario://awg-r04/computer-boundary`.
- `password_policy_accepts`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-2799`; reference `scenario://awg-r04/computer-boundary`.
- `network_rpc_reachable`: `S-1-5-21-1271839998-3495686680-2211690266-4157` → `S-1-5-21-1271839998-3495686680-2211690266-2799`; reference `scenario://awg-r04/computer-boundary`.
- `authentication_accepted`: `S-1-5-21-1271839998-3495686680-2211690266-2799` → `S-1-5-21-1271839998-3495686680-2211690266-4157`; reference `scenario://awg-r04/computer-boundary`.

**Quyền nên kiểm tra trước:** GenericAll của **FINWVIR1000001.SEAMLESS.INTERNAL** trên **DENA_WILLIAM@SEAMLESS.INTERNAL**. Xem toàn bộ ACE/inheritance provenance trong JSON trước khi thu hồi quyền; đây là điểm can thiệp đề xuất từ witness, chưa phải bằng chứng cắt hết đường.

Full native trace: `result.json#/reproducibility/inputs/public_queries/sha256:ed334a4ce1cabf1b2e978c54863faf139f011ef1f2fa4f86419d0f74acd68d22`. Bước dùng danh tính tại context không tự cấp quyền admin trên context đó.

## Các mục tiêu chưa có witness

- BADBLOOD.SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- ENTERPRISE ADMINS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- ACCOUNT OPERATORS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- ADMINISTRATORS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- SCHEMA ADMINS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- DOMAIN CONTROLLERS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- REPLICATORS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- PRINT OPERATORS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- READ-ONLY DOMAIN CONTROLLERS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- BACKUP OPERATORS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.
- SERVER OPERATORS@SEAMLESS.INTERNAL: đã hết budget; chưa có cơ sở gọi là an toàn.

Chi tiết kiểu identity, actor, nguồn quyền, raw-edge provenance và từng runtime fact nằm trong defender-brief.json. result.json giữ toàn bộ attempts/state audit. Nếu có remediation, program elimination và source–goal disconnection được báo riêng.
