# Worklog - 2026-10-08 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #208, #206, #204 / #231 / M3, Week 4; owner @Lolavine777, reviewer/cross-reproducer @nairyuuu.
- Thời gian thực tế ước lượng: Không ghi nhận thời lượng; không ước lượng hồi tố.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Nền tích hợp | `develop@4330f35`, source freeze `06cfb0c` | Engine/parser/harness B giữ đúng byte; .gitattributes giữ cả hai policy |
| Predicate acceptance | Independent oracle, generated Kerberoasting, adapter/zero-work regression | 38 rows, 33 PASS, 0 known defects/FAIL; 2 pending, 2 not executed, 1 blocked |
| Tái lập nguồn sạch | Hai process và `reports/research/week4-reproduction.json` | Cùng semantic/source digest, observed metadata từng lượt; không là B sign-off |
| Full suite | `.venv/bin/python -m pytest -q` | 2013 passed, 10 skipped, 48 subtests passed |
| Chất lượng | Ruff, yamllint, repository/contract checks | PASS |
| Report/demo | `docs/reports/week4-report.md`, `week4-demo.md` | Tiếng Việt, không có tracker refs; 6 Bash blocks smoke PASS |


## Phạm vi và nền đo

Nền `develop@4330f35e881ebadbd524843fc3686d48a97b917f` sau #232 và #230.
Source freeze `06cfb0c0c37f5c59edc105f1456dcc964edfa810`, parents `bccedd9596bb681c76a5bf3613b40f50c454ef84` và `4330f35e881ebadbd524843fc3686d48a97b917f`.
Một conflict `.gitattributes` được giải bằng giữ cả acceptance byte pins và Kerberoasting evidence byte policies. Mã engine, parser và harness Kerberoasting giữ đúng byte develop; A chỉ cập nhật acceptance runner/oracle/tests và tài liệu.
Source freeze giữ artifacts cũ từ parent; artifact commit sau đó thay bằng evidence hiện hành. Các worklog ngày trước là lịch sử của nguồn đo riêng, không dùng làm actual của nền mới.

## Kỳ vọng độc lập và actual

- Adapter rejection: sinh 3 đường, nhận 2, loại 1; incumbent C=5, `best_in_bound_subset`, proof false. PASS theo oracle đã freeze trước sửa engine.
- Initial semantic goal: một đường 0 bước, zero new work=0, ranking `not_applicable`; canonical minimum/P/I null, eligible candidates/Pareto rỗng, candidates evaluated=0. PASS, không tạo rating hoặc action giả.
- Kerberoasting: execute B public API với fixture/harness đã nhận; independent oracle A map 5 owner IDs tới request -> recover -> activate -> passive group -> asset. Một chương trình/6 trạng thái, đúng actor/context, checkpoint/asset goal true dưới assumptions tổng hợp; adapter nhận nhưng C/P/I unrated/null và proof false.
- OFF/ON positive giữ inputs/snapshot/state/caps, chỉ đổi allowed techniques. OFF không có acquisition/asset branch nên no_path; không là denial gate blocked.
- K-MATERIAL, K-NO-AUTH, K-FACT-F/U, K-KDC-F/U, K-AUTH-F kiểm applicable prefix, không tự tạo secret hoặc usable identity.
- K-OVERLAP: cùng reset scenario/caps có witness tới tài sản ở cả hai scope; không thêm asset coverage đã chứng kiến. ON có 26 paths/182 expansions và `step_limit_reached`; existential witnesses không đòi exhaustive enumeration. Oracle không đòi exhaustive search cho ca này. Artifact lưu một witness mỗi scope, tổng số/digest toàn bộ paths/attempts, status counts và cap disclosure.
- Chữ ký known defects được giữ để test recurrence; mutation mọi normative field hoặc xóa expected fields phải FAIL. CLI mutated engine trả exit 1.

Summary: **38 rows: 33 PASS, 0 KNOWN DEFECT, 2 PENDING B, 2 NOT EXECUTED, 1 BLOCKED RUN, 0 FAIL**.
AS-REP/RBCD validation probes không là full-program acceptance. CLI và full docs/API manual audit chưa chạy. Private SEAMLESS raw vắng mặt: prerequisite observation, probe không chạy, command null; không ghi fake exit hoặc claim raw certification.

## Thực thi và tái lập

Hai clean-process runs tại cùng source freeze, output ghi ngoài checkout trước khi copy artifacts; observed metadata đều `identity=clean_commit`, `checkout_dirty=false`, `dirty_pinned_files=[]`.
Python **3.14.7**, Linux x86_64; dependencies theo `requirements-dev.txt`. Timestamp/runtime/dependency versions ghi từng lượt trong manifest/reproduction record, không hardcode.

```bash
.venv/bin/python scripts/research/week4_acceptance_runner.py --output /tmp/w4-run-1.json --semantic-output /tmp/w4-semantic-1.json
.venv/bin/python scripts/research/week4_acceptance_runner.py --output /tmp/w4-run-2.json --semantic-output /tmp/w4-semantic-2.json
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m yamllint .
.venv/bin/python scripts/check_repository.py
.venv/bin/python scripts/check_contract.py
```

Semantic digest: `sha256:b2cfb4f8a5cbb0fc462d23a17d1719d70d0af38dae77e70ff398a023df9f5da2`.
Source/input digest: `sha256:91f87594c7676be3446500849351d21fce410fc43cb53dd10d08c881ffca3bd6`.
Hai semantic files bằng byte; source/input digest bằng nhau. Full suite trên cùng source bytes và artifacts mới: **2013 passed, 10 skipped, 48 subtests passed**. Skips do private/local data và Windows junction trên Linux, không tính PASS cho private data.
Ruff check/format, yamllint, repository và contract checks PASS. Sáu Bash blocks của demo chạy qua smoke test trong full suite.
`reports/research/week4-reproduction.json` ghi execution metadata và file hashes của hai lượt. Hai process cùng máy không là B human-independent reproduction.
Artifact commit giữ pinned source/input bytes bằng source freeze; bổ sung LF policy cho stored evidence JSON để hashes không đổi trên Windows checkout.

## Điều học được / quyết định

Known defects đã sửa phải chuyển PASS bằng oracle; giữ mutation/recurrence checks để không biến nhãn lỗi thành acceptance.
Existential same-asset witnesses khác exhaustive coverage; disclose cap và không tạo C/P/I cho thiếu basis.
Source/input identity được quan sát trước khi viết artifacts; metadata execution không thuộc semantic equality.

## Trở ngại và việc kế tiếp

B approval `bccedd9` áp dụng bản trước integration; cần review lại final head và CI Ubuntu/Windows hiện hành, không self-approve PR A.
#231 là refresh scoped acceptance preparation, không đóng #208/#204 hoặc promote main. #206 còn raw/query delta và independent replay.
B tiếp tục core CLI #213/#233 (còn draft tại lần đọc này), sau đó AS-REP #228 và RBCD #229; không cần đợi đủ techniques mới hoàn thiện core CLI.
Final Week 4 còn B handoffs, authorized private runs/baselines và cross-reproduction. Report/demo tiếng Việt không chứa GitHub/PR/issue references; không chuyển synthetic numbers sang roasting hoặc môi trường thật.

## Sửa byte pins trên Windows sau CI

CI tại `10b39bf` đạt Ubuntu, quality, Compose và branch policy; Windows fail hai tests do cùng một nguyên nhân: `core.autocrlf=true` đổi fixture Kerberoasting sang CRLF. Hash query quan sát trên Windows là `fd0cefaf785bdd514207d99ff389ebbaedfa85a055e6e6c81cef53cf39cfb3b2`, khác byte pin LF `ceb89ba17d8cb3e13d01ffa25f247aaeb8c6f18ddb7094db8a037f548a2b82f4`. Semantic reproduction trên Windows vẫn khớp digest đã ghi.

Bổ sung LF policy cho `tests/fixtures/kerberoasting/*.json`. Regression mới dùng Git checkout-index với `core.autocrlf=true` để checkout và kiểm từng file trong manifest, không normalize hoặc thay kỳ vọng hash. Trước sửa, test tái hiện đúng hash query lỗi của Windows; sau sửa, **1 passed** trên Linux/Python 3.12.14. Ruff check/format và diff whitespace check PASS. Cả 85 pinned source/input files giữ nguyên byte; manifest/source freeze/digests và số ca nghiệm thu không đổi.

Full acceptance suite cần Python 3.14 theo repo; runtime Python 3.12 hiện tại không parse được syntax của engine nên không ghi nhận full rerun local cho bản sửa này. CI mới trên Ubuntu/Windows là gate xác nhận toàn bộ acceptance/demo. B cần review lại head mới trước merge; #208/#204 vẫn OPEN.
