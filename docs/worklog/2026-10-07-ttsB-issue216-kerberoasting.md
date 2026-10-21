# Worklog — 2026-10-07 — ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: [#216](https://github.com/nairyuuu/ad-weighted-graph/issues/216) / `feature/216-kerberoasting` → `develop`, reviewer @Lolavine777 / M3-B5 Week 4 theo issue (GitHub milestone chưa gán)
- Thời gian thực tế ước lượng: khoảng 65–70 phút triển khai, validation và bàn giao

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Baseline/dependencies | Worktree riêng từ ae778cd; đọc #216/handoff, #215/#222, #211/#221, #174, #212/#223, #213, #206/#207, #218 | Consume develop adee089 sau upstream merge #223/#225; không merge/cherry-pick PR khác |
| Semantic contract / AC | [Matrix và API](../research/kerberoasting-216.md) | Material/recovery/activation/context riêng; downstream asset bắt buộc; AS-REP/RBCD ngoài scope |
| Public generation | known_identity + SnapshotFacts + branch state + catalog/runtime | Không ordered path/roast request/structural edge giả; false/missing auditable; owner scope/caps giữ nguyên |
| Replay/ranking | Typed artifact lineage; public query #223 giữ sidecar; canonical evaluator | Missing graph/facts fail closed; 4/3/2/1 active units khi reuse; C/P/I unrated; no minimum proof |
| Focused validation | `pytest tests/test_kerberoasting.py tests/test_path_ranking_interface.py tests/test_week4_min_effort_search.py tests/test_week4_query_scenario_mapping.py -q` | 132 passed; Kerberoasting module 38 cases, Week 3/4 oracle/replay/binding regressions reused |
| Full clean source | `python -m pytest`, Python 3.14.7, afd0f680fa9a327f4c1236c93fa9876accb1031e | 1977 passed, 11 skipped, 268.42s; skips/commands có trong evidence README |
| Reproduction / SEAMLESS | [Hai outputs/digests](../research/evidence/kerberoasting-216/README.md) | Hai lượt actual manifest-verified PASS và byte-identical; raw request unknown; full assumed witness tới C0 |
| Baseline delta | K-OVERLAP + same-input SEAMLESS off/on | Baseline đã tới C0; không new asset coverage; truncated scopes chỉ báo generated routes |
| Repository checks | Ruff check/format, yamllint, check_repository/check_contract, Compose placeholder, diff check | PASS trên source pin; artifact/doc commit sẽ chạy checks trước push; remote exact-head CI ghi trong PR |

## Điều học được / quyết định

SPN evidence chỉ cho phép xét request. Ticket material không là password, recovered
password chưa là usable identity, usable identity chưa là admin asset. Reuse
SnapshotFacts envelope để graph→query→ranking không mất evidence. Các nhãn nghiên
cứu K-* là oracle expectations; exact implemented owners nằm trong catalog 0.4.

Đối chiếu 13 entries cũ và evidence registry: structural equality với ae778cd;
chỉ thêm 3 owners/version. Expected programs/states/ratings Week 3/4 giữ nguyên,
chỉ rebind version/digest metadata. Không copy numeric basis sang event mới.
Source index giảm full-edge scan theo authorization filter hiện hành; không đổi
topology, sorting, branch-local gates hoặc provenance. Recovery/activation artifact
boundary có thể reuse cho AS-REP sau này; trigger đó chưa được implement.

CI đầu (e6a9943) chỉ fail Week 4 SHA pin trên cả Ubuntu/Windows: manifest tính
hash từ CRLF working files trong khi Git lưu LF. Rebind bốn pins theo committed
blobs và normalize working files theo LF policy; không đổi expected semantics.
Hai reproduction outputs dùng `-text` để giữ exact bytes/digests Windows.

## Trở ngại và việc kế tiếp

1. A (@Lolavine777) cross-review exact owner/context/event binding và independent
   executable mapping của #218; chưa coi issue đã nghiệm thu hoặc tự đóng/merge.
2. #213 consume snapshot/query CLI và commands ở evidence README; private raw giữ
   local. Các runtime/recovery outcomes SEAMLESS còn unknown nếu bỏ assumptions.
3. Numeric recovery/effort/likelihood/impact và complete coverage chưa có basis;
   giữ unrated/caps. CI final head và reviewer request được ghi trong PR khi tạo.

### Follow-up review #230 — 2026-10-08

Đã sửa hai blockers: snapshot-fact roots chỉ được ranking sau typed replay với bound
SnapshotFacts; secondary usable identity được ranking trong cùng query foothold U,
không đổi initial_actor để né validator. Binding bất biến trong process được truyền
qua mọi lần validation/assessment/replay, reject wire assertions và modified
lineage/scope. Initial actor audit ghi foothold, first actor, authentication context
và declared actor set. Reused password activation cũng giữ query U. Missing enabled
được audit UNKNOWN; serialized path cũ thiếu actor tiếp tục dùng source fallback.

Kiểm chứng follow-up trên Python 3.14: **1983 passed, 10 skipped, 48 subtests passed,
87.89s**; focused Kerberoasting + ranking conformance **190 passed** (Kerberoasting
43 cases). Skips là private datasets/raw roots; không chạy lại actual SEAMLESS vì
private raw không có tại môi trường follow-up. Ruff check/format, repository check,
contract check (hai synthetic fixtures) và diff check PASS. Evidence/CI/source pins
ở phần trước là lịch sử của original implementation, không thay thế validation
cho follow-up revision. Cross-review vẫn cần được nghiệm thu trước merge.
