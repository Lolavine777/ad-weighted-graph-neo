# Bằng chứng AS-REP #228 sau review

Actual synthetic qua existing query CLI schema 0.2, source pin
`97aa41b153317080ef4969226312d25989026c4f`, tích hợp `develop@d96f3f6` / #231.
Gói này thay evidence cũ tại `1753a4e`; evidence cũ có initial facts bị phân loại
sai. Không dùng actual output làm expected oracle. Commit evidence sau pin chỉ
đổi docs/output, không đổi source/config/input đã pin.

[Run 1](run-1.json), [run 2](run-2.json), [OFF](off.json),
[runtime unresolved](unresolved.json) và [manifest](reproduction.json) lưu actual
outputs. Artifacts dùng LF; chỉ normalize CRLF→LF, giữ hash/size transport gốc
trong manifest. Runtime metadata giữ riêng theo compare contract #213.

Hai runs ON exit 0, semantic và ordering bằng nhau. Semantic SHA:
`sha256:7031099ab1dfc5d238b92a6d0899ea95ea542b289e9343b6574edc91e9fa5244`.
Input/config/artifact digests xem manifest; source/config digests được đối chiếu
với git blobs ở source pin, không chỉ tin revision label.

## Tái lập

Checkout sạch source pin, Python 3.14 và requirements-dev:

```bash
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query.json --label synthetic --output run-1.json
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query.json --label synthetic --output run-2.json
python -m scripts.research.compare_query_runs run-1.json run-2.json
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query-off.json --label synthetic --output off.json
python -m src.engine.query_cli --snapshot tests/fixtures/asrep/snapshot.json --query tests/fixtures/asrep/query-raw.json --label synthetic --output unresolved.json
python -m scripts.research.week4_acceptance_runner --check-determinism --output acceptance.json
```

## Kết quả actual và giới hạn

| Ca | Kết quả |
| --- | --- |
| ON A-P | success conditional, 5 steps / 6 projected states, checkpoint + asset reached |
| OFF cùng input trừ technique scope | no_path trong finite declared scope |
| RAW thiếu outcomes | indeterminate; không material/secret/identity/asset hoặc no-path proof |
| Ranking | 4 active units, membership passive, C/P/I null/unrated, minimum proof false |
| Initial declarations | assumed_facts Layer 3; không observed_true/observed_false_veto |
| Request eligibility | false chặn A1; missing giữ indeterminate; secret reuse vẫn kiểm A3 |
| Focused regression | 143 PASS, 51 ca AS-REP |
| Existing acceptance runner | 38 cases: 35 PASS, 1 PENDING B (RBCD), 1 NOT EXECUTED, 1 BLOCKED RUN; 0 unexpected failures; deterministic |
| Full suite Ubuntu tại `f81d739` | **2127 PASS, 10 SKIP / 331.17s**; Windows/local và CI final head theo PR |
| Required checks | ruff check/format, yamllint, repository/contract, Compose config, diff check PASS |

AS-REP PASS của runner là scoped synthetic prediction. Normative expected fields
A-owned được giữ nguyên; executable mapping/domain review #206 và independent
acceptance #208 vẫn pending. Manual audit và private SEAMLESS không được đổi
thành PASS. Private reproduction cần authorized manifest-verified inputs;
không có private run, cracking hay live exploitation.

Xem [thiết kế và review fixes](../../asrep-228.md) và
[worklog](https://github.com/Lolavine777/ad-weighted-graph-neo/blob/282450279ae0afa035b9597b86b2d250f6feca69/docs/worklog/2026-10-08-ttsB-issue228-asrep.md).
