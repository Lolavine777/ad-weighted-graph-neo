# Đối chiếu trực tiếp SEAMLESS sau sàng lọc Week 4

Ngày 06/10/2026, Asia/Ho_Chi_Minh. Owner TTS A; reviewer TTS B. Refs [#200](https://github.com/nairyuuu/ad-weighted-graph/issues/200), [#192](https://github.com/nairyuuu/ad-weighted-graph/issues/192), [PR #217](https://github.com/nairyuuu/ad-weighted-graph/pull/217).

## Nguồn và kết quả tái lập

**Đã tải đủ raw từ GitHub và verify bytes.** Nhận định thiếu raw ở lượt trước là do chưa tải nguồn đã biết, không phải dataset không truy cập được. Kết quả dưới đây thay trạng thái chưa trace; [nghiên cứu #201](week4-prediction-evidence.md) giữ riêng làm lịch sử. Chưa chạy khai thác, dò mật khẩu hoặc extension search.

- Nguồn [Bloodhound_Data](https://github.com/mike-nolan-councilman/Bloodhound_Data/tree/3febc4089421725f9527c187f78d064ad09d5158), pin `3febc4089421725f9527c187f78d064ad09d5158`; [archive](https://raw.githubusercontent.com/mike-nolan-councilman/Bloodhound_Data/3febc4089421725f9527c187f78d064ad09d5158/20210920185958_BloodHound.zip) 268.200 bytes, SHA-256 `b8e9f003dd51a98838be86d8f98b0844a19a7876aad0a81b525f19e110105813`.
- Sáu files khớp size/hash trong [manifest](../../data/samples/manifests/seamless-raw-v1.json), tổng 11.371.828 bytes; snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; official verify `issues=[]`.
- Code thực chạy: head tài liệu `18887eaacbad18e95938978f7070c820ef1c31fd`, contract 1.3.0/catalog 0.3. Parser/engine/catalog không đổi so với baseline `0c44e84b5e7718d71fafe07abb0eb03998dfbacb`.
- Raw audit: 195 field paths, 3.369 records (User 2.493, Group 550, Computer 100, Domain 1, OU 223, GPO 2). Parser: 3.370 nodes, 56.367 edges, 3 assessments unknown, 0 warnings/errors. Canonical Group 551 sau reconciliation/boundary handling, khác số raw records.
- Schema 8 loại quan hệ; snapshot chỉ 5 loại không rỗng: GenericAll 37.044, MemberOf 15.917, WriteDacl 3.395, AdminTo 9, CanPSRemote 2. 13 catalog entries không là 13 kỹ thuật độc lập.

Canonical SHA-256 tại pin này: `cc7926c588620dc9f7c57594dd06b06d95b0685506a53a2d60ab1bad72b3a55a`. created_at cố định để tái lập; time policy là assumed, không là collection time quan sát. Rerun trên commit khác ghi code pin/hash mới; metadata khác không chứng minh graph semantics thay đổi.

```bash
.venv/bin/python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
.venv/bin/python scripts/audit_seamless_raw.py --raw-dir data/raw/SEAMLESS --manifest data/samples/manifests/seamless-raw-v1.json --output reports/generated/week4-200/raw-inventory.json --markdown-output reports/generated/week4-200/raw-audit.md
.venv/bin/python -m src.parser.cli --snapshot-id sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812 --raw-dir data/raw/SEAMLESS --profile unit --error-policy fail_fast --time-policy tests/fixtures/ranking/seamless_time_policy.json --created-at 2026-10-06T00:00:00Z --output reports/generated/week4-200/canonical.json --summary
.venv/bin/python scripts/research/field_screening_probe.py
```

[Probe read-only](../../scripts/research/field_screening_probe.py) cố định snapshot, xuất locators/roles/counts và hash script/graph; không tên account, SID, DN, SPN hoặc bí mật. Raw và reports/generated ignored, không commit. Locators `users#/users/1700` tương ứng file `20210920185958_users.json`, record `/users/1700`.

Membership hợp Group.Members và PrimaryGroupSid, resolve theo production normalizer/boundary policy; giữ cả hai duplicate Group records 6/549, không ghi đè memberships/ACEs. Toàn bộ 15.917 cặp membership khớp canonical. Bộ lọc vai trò gồm DA/EA/Administrators/DC/RODC/EnterpriseDC; **ngoài bộ lọc không chứng minh ít đặc quyền tuyệt đối**. Closure không là Windows token/access check.

Lần kiểm cuối: probe SHA-256 `ad680ae79d1f30c307879f471cc55fb79ac5c21ce82bb882998c158fc81329fa`, sanitized report SHA-256 `5cfd7c8869761fcd44d1aefcdda88b363827cbf12e81cf155d1242bfcf0b371c`. Raw/reference assertions và privacy scan PASS; probe từ chối manifest sai pin, graph sai snapshot, graph thiếu membership. Guard kiểm bằng chứng không là oracle extension attack paths.

## Chuỗi và lựa chọn từ bằng chứng mới

| Ca | Locators/bằng chứng | Kết luận và phần còn thiếu |
| --- | --- | --- |
| AS-REP | 176 pre-auth off, 51 SPN, giao 4; chỉ User1700 enabled/pre-auth off tới DA qua `groups/40/Members/2` | Giữ ca đầu từ attacker chưa có AD identity; cần KDC, recovery, secret validity/auth, asset gates |
| AS-REP tới DC | Computer0 có vai trò DC/EnterpriseDC; canonical có AdminTo User1700→Computer0, provenance Members[]/LocalAdmins[], derivation v1.1.0 effective_membership/host_local_membership | Mapping asset mà đợt #201 còn để mở nay đã có theo parser policy; không thay endpoint/network/auth/token checks hoặc proof of execution |
| Kerberoasting | User11 enabled/SPN → PrimaryGroup Group31 → Group548 → Group30; `users/917/Aces/8` cho Group30 GenericAll trên User917; `groups/40/Members/3` nối target DA | Downstream có thật nhưng 2.490 enabled Users cũng tới holder Group30, gồm Users1580/2201. Baseline reset→DA→C0 có thể đã khả dụng với initial authenticated actor; hạ claim coverage mới, cần counterfactual/đổi ca |
| RBCD target | User1580 enabled, ngoài bộ lọc; direct GenericAll tới Computer27 tại `computers/27/Aces/5`, canonical giữ edge | Có candidate ghi descriptor; AllowedToAct rỗng không loại creation; exact attribute/directory gates vẫn riêng |
| RBCD service principal | Cùng User1580 direct GenericAll tới enabled SPN User2075 tại `users/2075/Aces/4`, và User1212 tại `users/1212/Aces/3`; canonical giữ cả hai, targets ngoài bộ lọc | Có candidate reset→known secret/key→controlled SPN principal. Không mặc định M đang controlled; nhánh này không cần default MachineAccountQuota/tạo máy mới |
| DCOM | `computers/0/DcomUsers/0` resolve enabled User2201 ngoài bộ lọc → DC C0; canonical không có loại edge nào cùng pair | Nhánh protocol mới, chưa proof COM execution/admin_control hoặc asset mới; user này cũng có reset prefix baseline |
| Owner | 3.363 ACEs; chỉ DA40/Administrators2; 38 có cùng pair WriteDacl | Không thấy prefix ngoài bộ lọc; không gọi tất cả Owner trùng WriteDacl |
| WriteOwner/GenericWrite | 3.397/3.171 ACEs; holders DA40/EA18/Administrators2, 0 unresolved/ngoài bộ lọc; tất cả có cùng pair WriteDacl | Chưa ưu tiên trước, không loại toàn kỹ thuật; còn exact owner/attribute restrictions nếu dùng về sau |
| GPO | Hai GPO: tổng Owner2/WriteDacl6/WriteOwner6/GenericWrite6, holders chỉ DA40/EA18. Domain0 link GPO0: containment 100 computers; OU0 link GPO1: C0/C8; IsEnforced=false | Có raw scope tới máy nhưng holder đã đặc quyền; gpcpath không là GPT contents/SYSVOL write, containment không là resultant policy |
| DCSync | Domain0 ACE8–12; 11 objects có same-actor GetChanges/GetChangesAll qua closure, đều trong bộ lọc; Group38 riêng GetChanges chưa đủ cặp | Chưa thấy prefix sớm hơn; không ghép quyền của hai actor độc lập. Tạo quyền qua DACL là nhánh nghiên cứu khác |
| Observed delegation/session/trust/history | User/Computer AllowedToDelegate, Computer AllowedToAct/Sessions, User HasSIDHistory, Domain Trusts đều present/0 nonempty; unconstrained receiver duy nhất là C0/DC | Không tự thêm observed relations. Tạo delegation từ ACL vẫn có thể xét; thu TGT còn receiver controlled/victim auth |
| LAPS và password flags | haslaps=false 100/100 computers, không password/read-LAPS evidence; passwordnotreqd=true 2 Users, userpassword đều null | Thiếu căn cứ từ collection cho LAPS; không suy password rỗng/yếu hoặc recovery probability |

RBCD là **ứng viên thứ hai để B review**, chưa là commitment/engine-generated path. Chuỗi đề xuất: usable User1580 → reset/activate M dưới gates hiện có → secret/key phù hợp của M → ghi descriptor Computer27 → delegation/S4U theo policy → scoped service context P → action nếu P được authorization trên asset. Snapshot chưa cung cấp quyền cuối của P trên Computer27; ticket không tự là admin_control hoặc P usable toàn miền.

Nguồn RBCD: [AddAllowedToAct](https://bloodhound.specterops.io/resources/edges/add-allowed-to-act), [AllowedToAct](https://bloodhound.specterops.io/resources/edges/allowed-to-act), [Elad Shamir](https://eladshamir.com/2019/01/28/Wagging-the-Dog.html). DCOM cần COM/application permissions và execution identity: [ExecuteDCOM](https://bloodhound.specterops.io/resources/edges/execute-dcom) nêu execution có điều kiện, có thể chạy dưới caller, logged-on user hoặc identity của process khác. LAPS: [ReadLAPSPassword](https://bloodhound.specterops.io/resources/edges/read-laps-password); flag collection không chứng minh mọi biến thể ngoài scope vắng.

Khoảng trống mapping quyền sẵn có: 2.497 User ACEs `ExtendedRight/AceType=All`, parser bỏ ExtendedRight; holders chỉ DA40/EA18/Administrators2, không pair trùng GenericAll. [Legacy importer pin 4.0.3](https://github.com/SpecterOps/BloodHound-Legacy/blob/b54c418ef83fe5856ae3fe6317a20f2368a6378c/src/js/newingestion.js#L583) đổi All thành AllExtendedRights; [tài liệu hiện hành](https://bloodhound.specterops.io/resources/edges/all-extended-rights) hỗ trợ password reset trên User. Đây là candidate mapping cho reset đã có, chưa là kỹ thuật/đường ít quyền mới hoặc full access check.

## Handoff và phần còn mở

1. A/B review AS-REP trước, RBCD kế tiếp có gate; Kerberoasting cần đối chứng/đổi ca, DCOM cần COM context/asset goal; owner/GPO/DCSync để sau trong scope đã kiểm.
2. B quyết định state/owner/trigger/outcome theo #174; A đưa facts/assumptions/effects, positive/blocked/unknown expectations và scoring boundary. PR nghiên cứu không đổi parser/engine/catalog/ratings.
3. Sau integration, so baseline/extension trên cùng source, asset, initial capability và assumptions; đo reachable states/routes/effects mới. Raw route, field count hay edge count không là số coverage tăng.
4. C/P/I theo toàn đường/công việc mới có điều kiện; snapshot không cung cấp recovery probability. Missing giữ unrated hoặc scenario bounds có căn cứ, không điền số tùy ý.

Raw verification đã hoàn tất; runtime/integration/review còn mở. Core #204 tiếp tục song song. CI đạt không thay semantics acceptance hoặc attack success.
