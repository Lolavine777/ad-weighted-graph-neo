# Top-K chương trình tấn công theo công sức C

Refs #226; consume query/Min-Effort #212, CLI/result package #213 và rating integration #250.
Bản đầu dùng exhaustive finite baseline trên public query path. Human cross-review và
independent reproduction của #226 còn pending; implementation không tự đóng issue.

## Contract và phạm vi

Caller khai báo source/actor, initial AttackState, context, target/goal, techniques,
facts/assumptions và search budget như public query hiện có; thêm `top_k: K`.
API nhận `AttackQuery`, mapping hoặc `MaterializedQuery`; CLI thêm `--top-k K`.
K phải là số nguyên dương, từ chối boolean, float, string và explicit null trong JSON.
K không thay `max_paths`, `max_steps` hoặc `max_expansions`.

Pipeline giữ generator → binding/automatic rating resolution → whole-path evaluator.
Selector chỉ đọc C đã đánh giá: không chấm lại, cộng edge weights, dùng hop count hoặc
tạo weighted sum C/P/I. Feasible program có C rated vẫn được chọn nếu P/I unrated.
Risk/Pareto tiếp tục có eligibility riêng. Thiếu C/binding hoặc adapter refusal được
giữ trong diagnostics và hạ guarantee, không mặc định cost=0.

Objective là tổng C của unique active work units trong accepted bindings/context.
Shared preparation tính một lần; passive membership không tự thêm active work.
Assessment active-work budget là một phần phạm vi eligibility và được xuất cùng
search metadata. Không claim K-best cho toàn snapshot, mọi goal hoặc mọi khả năng ban đầu.

## Program identity, ties và stopping

`attack-program-identity/1` dùng canonical JSON của ordered semantic requests (bao gồm
actor/source/target và RBCD binding), canonical initial actor/source scope kể cả zero-work,
auth context, before/additions/final AttackState,
exact edge IDs, causal parent indices, projected node sequence và scenario reference.
Định danh áp dụng trong query/snapshot/environment đã pin; không dùng để gộp results
ở các snapshots/goals khác nhau. Numeric rating và enumeration IDs không định nghĩa
program equivalence. `program_id` là SHA-256 của key; **sort theo key, không theo hash**.
Path API giữ `initial_actor` riêng; zero-action `nodes` vẫn là singleton terminal asset.
Candidate transport giữ legacy shape vì source đã có ở `materialized.initial_actor` và key.

Không dedup chỉ theo node sequence, final actor, C hoặc work-unit set. Prefix/history
khác vẫn có thể mở continuations khác, hoặc là alternative program dù cùng active work.
Alias được resolve trước generation. Duplicate cùng semantic identity bị gộp; các
candidate IDs bị gộp vẫn được audit. Equivalent programs có C mâu thuẫn là lỗi run.

Canonical graph contract hiện đặt edge ID theo `(source, target, kind)` và reconcile
records trùng triple. Parallel edges hợp lệ là những relationship kinds khác nhau;
không tạo thêm IDs cho raw records trùng. Identity giữ exact canonical evidence route.
Generator terminal dedup dùng identity này thay vì chỉ chuỗi `TransitionRequest`.
Không đổi raw/provenance hoặc semantics của graph contract.

Default trả tối đa K distinct eligible programs, sort `(C, canonical_program_key)`.
Min-Effort trên public query dùng cùng selection/tie policy; K=1 cùng winner và C.
Legacy supplied-packet assessment không có generated program identity vẫn giữ contract riêng.
Không có `include_ties` trong bản đầu. `boundary_ties` ghi cutoff C, observed/omitted
tie counts và liệu đã chứng minh đầy đủ. Khi có ít hơn K, cutoff là program cuối trả về.

Giữ first-goal stopping của generator: không mở rộng suffix sau khi đạt goal.
Initial goal trả đúng một empty program C=0, ledger rỗng, P/I null theo semantic
zero-work disposition; không tạo canonical assessment/Pareto giả.
Passive/no-op actions giữ identity/history nhưng mỗi relationship/technique/actor action
chỉ dùng một lần trong branch. Return-to-node với AttackState mới vẫn được phép;
không dùng node-simple-path rule. Đây là supported finite program universe, không
cam kết enumerate mọi chuỗi lặp hành động tùy ý. Caps có thể cắt exploration.

## Guarantee và coverage

| Hành vi thực tế | Guarantee |
| --- | --- |
| Exhausted exploration; không còn unknown transitions; mọi candidate liên quan được bind/assess, feasible candidates đủ C; evaluator không bị cắt | `exact_k_best_within_scope` |
| Search đầy đủ nhưng thiếu binding, adapter/assessment hoặc C | `best_in_eligible_subset` với exclusion reasons |
| Search/evaluator bị cắt dù đã tìm đủ K | Incumbents trong `best_in_eligible_subset`; không có K-best certificate |
| Unknown transition chưa chứng minh không thể tạo alternative | Downgrade bảo thủ; không biến unknown thành successful program |
| Ít hơn K eligible distinct programs trong exact scope | `fewer_than_k_proven=true` |
| Không trả program vì thiếu C/binding hoặc bị cắt | Không suy no-path từ returned_count=0 |

`no_path_proven` dùng semantic no-path predicate hiện có: complete, không unknown,
không đạt final goal. DA checkpoint không thay asset goal. Known FALSE veto được giữ.
Min-Effort proof cũng không nhận unknown transitions hoặc evaluator truncation.
Unknown diagnostics hiện không có branch IDs; vì vậy downgrade toàn query khi có
indeterminate attempt là bảo thủ, có thể chưa chứng minh dù unknown không liên quan goal.

Không early-stop khi đã đủ K và không thêm state dominance pruning. Một prefix
không cần cho top-1 vẫn có thể thuộc top-2; tối ưu mới cần proof/oracle qua #227.

## Result package

`AttackQueryResult.top_k_result` và CLI `semantic.top_k` gồm objective, K/counts,
identity/tie versions, selected program IDs/keys/candidate references, C và work-unit
ledger, associated P/I hoặc null, boundary ties, coverage counts/exclusions/caps và
guarantee reasons. Full candidates/ordered trace/binding/rating diagnostics vẫn có trong
public result; selected references không thay trace bằng graph route summary.

Top-K CLI dùng transport `week4-query-result/0.4.0`, cho explicit packet, automatic
rating hoặc semantic-only. Các mode không yêu cầu Top-K giữ transport 0.2/0.3.
Schema: [Top-K](effort-top-k.schema.json), [envelope 0.4](week4-query-result-0.4.schema.json).
Acceptance metadata giữ nguyên dependency/pending lineage của mode explicit/automatic,
rồi thêm #226 human review/independent reproduction. Các gate kế thừa là provenance
của base transport; không diễn giải việc giữ lineage là mở lại issues đã đóng.

## Worked example và oracle

Independent Week 4 Ledger E: auth preparation=1, direct admin=4, inherited admin=1;
membership là passive. Expected này có trước Top-K implementation và không lấy actual
output làm oracle. [Frozen Top-K expectations](../../tests/fixtures/query_cli/top-k-oracle.json)
chỉ bổ sung K/count/tie expectations bằng tính tay từ basis đó; A cross-review còn pending.

| Program | Active work units | C |
| --- | --- | --- |
| D: direct admin | auth + direct admin | 5 |
| M/D: membership rồi direct admin | auth + direct admin | 5 |
| M/I: membership rồi inherited admin | auth + inherited admin | 2 |

FIFO sinh D trước; K=1 vẫn chọn M/I. K=2 trả M/I và D theo canonical key, báo hai
programs hòa C=5 tại cutoff và một program bị bỏ do K. K=8 trả ba programs và chứng
minh fewer-than-K khi scope complete. D và M/D dùng cùng work-unit set nhưng khác history.
Tất cả con số ở ví dụ là **synthetic_test_only**, không là numeric basis production.

## Lệnh tái lập

Từ repo root, Python 3.14 và dependencies trong `requirements-tests.txt`:

```text
python -c "from pathlib import Path; Path('reports/generated/top-k').mkdir(parents=True, exist_ok=True)"
python -m src.engine.query_cli --query tests/fixtures/query_cli/two-routes-query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --ranking-query docs/research/ratings/week4/synthetic-a2-e.json --top-k 2 --label synthetic --output reports/generated/top-k/first.json
python -m src.engine.query_cli --query tests/fixtures/query_cli/two-routes-query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --ranking-query docs/research/ratings/week4/synthetic-a2-e.json --top-k 2 --label synthetic --output reports/generated/top-k/second.json
python -m scripts.research.compare_query_runs reports/generated/top-k/first.json reports/generated/top-k/second.json
python -m src.engine.query_cli --query tests/fixtures/rating_resolution/query.json --graph tests/fixtures/attack_scenarios/graphs/two-routes.json --rating-resolution tests/fixtures/rating_resolution/complete.json --top-k 2 --label synthetic
python -m pytest tests/test_top_k_search.py tests/test_week4_min_effort_search.py tests/test_query_cli.py tests/test_public_rating_integration.py -q
```

Các tests kiểm complete oracle, invalid K, aliases, repeated runs, exact parallel
relationships, context/history/evidence identity, shared work, ties/dedup, initial goal,
false/unknown/checkpoint, C/P/I gaps, adapter exclusions và ba search caps.
Không chỉ kiểm top-1: ca initial entitlement giữ cả I và M/I với cùng final state/work.
Trước khi dùng explicit packet ở ca đó, packet phải khai báo cùng initial entitlement.

SEAMLESS Top-K chưa được đo trong thay đổi này: không có pinned private input handoff
trong checkout. Không dùng historical single-path probe để claim Top-K toàn snapshot.
Private inputs/output vẫn theo data policy. Performance baseline exponential; K không
giảm enumeration cost. Tối ưu scale/certificates là follow-up #227, không gate baseline nhỏ.

## Handoff và scope tiếp theo

### Migration source manifests

Maintainer chọn gộp migration source pins vào #226. Gói AS-REP #264 đã freeze
`likelihood-v1/catalog.json`, `likelihood-v1/manifest.json` và
`scenario-basis-v1/source-manifest-v2.json`; ba files đó giữ nguyên bytes.
Verifier dùng successor [likelihood source v2](ratings/likelihood-v1/source-manifest-v2.json)
và [scenario source v3](ratings/scenario-basis-v1/source-manifest-v3.json) để pin
executable hiện tại, gồm program identity và Top-K. Successor bind exact historical
manifest/catalog digests, kiểm đủ source coverage và từ chối tamper. Numeric records,
review/adoption gates, independent oracles và historical evidence không được đổi để pass.

B implementation, A cross-review contract/independent expected/reproduction.
Viewer #224 có thể consume selected candidate references, ledger và guarantee; không
tự tính lại scores. Report/demo #208 và README consume actual scope sau review.
Batch và cross-source/target aggregation thuộc #265/#268: #226 chỉ rank programs
trong từng query/goal, không triển khai Top-K footholds hoặc destinations.
