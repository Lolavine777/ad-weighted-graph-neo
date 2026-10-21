# ADR-0008: Structural graph, Attack Semantics va observed activity layering

- Ngay: 2026-09-21
- Trang thai: Accepted
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #58, #63, #70, PR #66, PR #69

## Boi canh

Structural graph canonical cua M1 luu relationship AD va provenance cua snapshot.
Mot structural relationship co the ho tro nhieu ky thuat, runtime predicate, effect va telemetry khac nhau.
Issue #58 da nghien cuu ranh gioi nay va #63/PR #66 da implement semantic catalog va transition model ma khong doi `configs/contract.yml`.
ADR-0007 so huu data/telemetry evaluation strategy, con ADR nay so huu execution va layering decision.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| Coi structural edge la attack step | Truy van path don gian | Mat nhieu ky thuat, predicate, effect va telemetry; de suy dien attack khong co evidence | #58 |
| Gan technique, state va telemetry vao edge canonical | Tat ca metadata nam cung mot record | Lam drift structural contract va tron snapshot fact voi runtime scenario | #63, PR #66 |
| Tach structural graph, semantic catalog, runtime state va observed activity | Giu provenance va contract on dinh, dong thoi danh gia transition minh bach | Can explicit request, predicate va state context | #58, #63, PR #66 |

## Quyet dinh va he qua

Chon phuong an 3.

1. Canonical structural graph chi luu M1 relationship, node, weight profile va provenance theo `configs/contract.yml`.
   Technique, runtime predicate, effect, observed activity va confirmed-attack field khong nam tren structural edge instance.
2. `Structural Relationship != Attack Technique != Observed Activity` la invariant kien truc.
   Mot relationship co the co nhieu candidate techniques.
   Candidate khong dong nghia ky thuat da duoc chon, kha dung, thuc hien hay quan sat.
3. Attack Semantics catalog anh xa relationship sang semantic transition.
   Transition chi duoc danh gia khi caller chon explicit technique/request va cung cap runtime context.
   Predicate thieu evidence phai tra ve `indeterminate`/`unknown`, khong gia dinh success hay failure.
4. Effect duoc ap dung vao immutable runtime attack state cua mot scenario.
   Effect va derived capability khong tao, sua hay xoa structural topology, provenance snapshot, hoac observed activity.
5. `ExpectedTelemetry` la expectation cua technique.
   No khong dong nghia `ObservedActivity` hay `ConfirmedAttack`.
   Entity-level telemetry correlation chi hop le khi co cung environment, identity namespace va time context theo ADR-0007.
6. `cost_factors` trong catalog la descriptive research input.
   ADR nay khong chot production weighting, khong thay `maut_v1`, va khong quyet dinh ownership cuoi cung cua cost giua relationship, transition hay composition.
   Redesign nay thuoc #42 va ADR/quy trinh rieng.

He qua:

- Engine co the mo hinh hoa possible transition ma khong khang dinh attack da xay ra.
- Missing telemetry khong phu dinh technique, va telemetry doc lap khong xac nhan path tren snapshot khac environment.
- Contract structural, parser va weighting implementation hien hanh khong doi.

## Kiem chung va dieu kien xem lai

- Kiem chung bang unit tests semantic catalog/transition, `uv run pytest`, Ruff, yamllint, `uv run python scripts/check_contract.py`, `uv run python scripts/check_repository.py` va `git diff --check`.
- Tieu chi thanh cong: catalog va transition giu snapshot immutable, tra ve blocked/indeterminate khi predicate khong dat/khong biet, va khong suy dien observed activity tu expected telemetry.
- Dieu kien xem lai: #42 co production weighting design duoc chap thuan, hoac co operational data co cung environment/identity/time context de formalize correlation policy.
