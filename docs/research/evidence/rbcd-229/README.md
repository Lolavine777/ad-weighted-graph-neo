# Bằng chứng RBCD #229 sau review

Actual synthetic qua existing query CLI schema 0.2, tích hợp baseline develop.
Gói này tuân thủ ranh giới độc lập: không dùng actual output làm expected oracle.
Commit evidence chỉ bổ sung docs/output, không sửa source/config/input đã cam kết.

[Run 1](run-1.json), [run 2](run-2.json), [OFF](off.json),
[runtime unresolved](unresolved.json) và [manifest](reproduction.json) lưu actual
outputs. Artifacts dùng LF; chỉ normalize CRLF→LF, giữ hash/size transport gốc
trong manifest. Runtime metadata giữ riêng theo compare contract #213.

Hai runs ON exit 0, semantic và ordering bằng nhau. Semantic SHA:
`sha256:8cbe84fd19d74d402eeb2a6af114a877a29aac567e71e13157adbc2a7d9f1792`.
Input/config/artifact digests xem manifest; source/config digests được đối chiếu
với git blobs, không chỉ tin revision label.

## Tái lập

Checkout sạch, Python 3.14 và requirements-dev:

```bash
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query.json --label synthetic --output run-1.json
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query.json --label synthetic --output run-2.json
python -m scripts.research.compare_query_runs run-1.json run-2.json
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query-off.json --label synthetic --output off.json
python -m src.engine.query_cli --snapshot tests/fixtures/rbcd/snapshot.json --query tests/fixtures/rbcd/query-raw.json --label synthetic --output unresolved.json
python -m scripts.research.week4_acceptance_runner --check-determinism --output acceptance.json
```

## Kết quả actual và giới hạn

| Ca | Kết quả |
| --- | --- |
| ON R-P | success conditional, 3 programs / 8 projected states, goal reached |
| OFF cùng input trừ technique scope | no_path trong finite declared scope |
| RAW thiếu outcomes | indeterminate; không secret/service/descriptor/delegated/asset hoặc no-path proof |
| Ranking | 5 active units, C/P/I null/unrated, minimum proof false |
| Initial declarations | assumed_facts Layer 3; không observed_true/observed_false_veto |
| Eligibility | false/missing chặn đúng bước độc lập; reuse controlled_service bỏ R1/R2 |
| Focused regression | 24 PASS ca RBCD (`tests/test_rbcd.py`) |
| Existing acceptance runner | W4-TECH-RBCD PASS |
| Required checks | ruff check, repository/contract, diff check PASS |

RBCD PASS của runner là scoped synthetic prediction. Normative expected fields
A-owned được giữ nguyên; executable mapping/domain review #206 và independent
acceptance #208 vẫn pending. Manual audit và private SEAMLESS không được đổi
thành PASS. Private reproduction cần authorized manifest-verified inputs;
không có private run, cracking hay live exploitation.
